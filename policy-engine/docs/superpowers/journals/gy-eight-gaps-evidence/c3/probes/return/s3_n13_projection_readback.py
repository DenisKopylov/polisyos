"""Compare actual N13 S3 input projections without invoking any N13 gate or writer."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

S3 = "architecture/policy_design_case/layer3_gy_intervention_substrate_contract.json"
PREVIOUS = "e2cf7f10f2853b7561034b8e0ba699e6bacd32ba"


def _hash(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _strict_object(raw: bytes) -> dict:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object key: " + key)
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=object_pairs)
    if not isinstance(value, dict):
        raise ValueError("S3 must be a JSON object; absent/null is unreadable, not zero")
    return value


def _nodes(value: object, pointer: str = "") -> dict[str, dict]:
    if isinstance(value, dict):
        rows = {pointer: {"type": "object", "keys": sorted(value)}}
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            rows.update(_nodes(child, pointer + "/" + escaped))
        return rows
    if isinstance(value, list):
        rows = {pointer: {"type": "array", "length": len(value)}}
        for index, child in enumerate(value):
            rows.update(_nodes(child, pointer + "/" + str(index)))
        return rows
    return {pointer: {"type": type(value).__name__, "value": value}}


def _stack_nodes(value: object) -> dict[str, dict]:
    result = {}
    stack = [("", value)]
    while stack:
        pointer, node = stack.pop()
        if isinstance(node, dict):
            result[pointer] = {"type": "object", "keys": sorted(node)}
            stack.extend(
                (pointer + "/" + key.replace("~", "~0").replace("/", "~1"), child)
                for key, child in node.items()
            )
        elif isinstance(node, list):
            result[pointer] = {"type": "array", "length": len(node)}
            stack.extend((pointer + "/" + str(index), child) for index, child in enumerate(node))
        else:
            result[pointer] = {"type": type(node).__name__, "value": node}
    return result


def _source_identity_arrays(value: object, pointer: str = "") -> dict[str, list[str]]:
    """Locate the existing S3 owner's explicitly sorted source-file set projection."""
    found = {}
    if isinstance(value, dict):
        denominator = value.get("source_file_denominator")
        if (
            value.get("schema_version") == "policyos.runtime.intervention_substrate_strangle.v1"
            and isinstance(denominator, dict)
            and denominator.get("file_type") == "src/**/*.py"
        ):
            rows = denominator.get("identities")
            # An unsorted, duplicate or malformed array must retain its full
            # ordered delta. It is never silently reduced to set membership.
            if (
                isinstance(rows, list)
                and all(isinstance(row, str) for row in rows)
                and rows == sorted(set(rows))
            ):
                found[pointer + "/source_file_denominator/identities"] = rows
        for key, child in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            found.update(_source_identity_arrays(child, pointer + "/" + escaped))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.update(_source_identity_arrays(child, pointer + "/" + str(index)))
    return found


def _compact_identity_sets(before: dict, after: dict) -> tuple[list[dict], set[str]]:
    left, right = _source_identity_arrays(before), _source_identity_arrays(after)
    deltas = []
    represented = set()
    for pointer in sorted(left.keys() & right.keys()):
        a, b = left[pointer], right[pointer]
        if a == b:
            continue
        a_set, b_set = set(a), set(b)
        added, lost = sorted(b_set - a_set), sorted(a_set - b_set)
        if added != [item for item in b if item not in a] or lost != [
            item for item in a if item not in b
        ]:
            raise ValueError("Independent full source-set membership delta differs")
        common = a_set & b_set
        if [item for item in a if item in common] != [item for item in b if item in common]:
            raise ValueError("Meaningful ordered change cannot be represented as set delta")
        deltas.append(
            {
                "pointer": pointer,
                "semantics": "S3 owner sorted unique src/**/*.py membership",
                "before_array_sha256": _hash(_canonical(a)),
                "after_array_sha256": _hash(_canonical(b)),
                "before_denominator": len(a),
                "independent_before_denominator": len(a_set),
                "after_denominator": len(b),
                "independent_after_denominator": len(b_set),
                "complete_added_identities": added,
                "complete_lost_identities": lost,
                "independent_membership_delta_equal": True,
                "retained_relative_order_unchanged": True,
            }
        )
        represented.add(pointer)
    return deltas, represented


def _projection(payload: dict, *, target: str) -> tuple[dict, dict]:
    from polisyos.data_forge import read_api
    from tools.quality.validation import check_layer3_gy_acquisition_executor as checker
    from tools.quality.validation import layer3_gy_acquisition_executor as executor
    from tools.quality.validation import layer3_gy_n13a_acquisition_census as census

    items = census._extract_substrate_demand_items(payload)
    binding = census._projection_binding("intervention_substrate_world_slots", S3, items)
    slots = executor._slot_units(payload)
    reentry = checker._substrate_slot_projection(payload, target_variable=target)

    # Independent whole consumed demand projection, including every source position.
    details = payload["measured_coverage"]["world_slot"]["details"]
    independent_items = []
    for detail_index in range(len(details)):
        targets = details[detail_index]["target_world_slots"]
        for target_index in range(len(targets)):
            independent_items.append(
                {
                    "source_path": (
                        "intervention_substrate.measured_coverage.world_slot.details"
                        f"[{detail_index}].target_world_slots[{target_index}]"
                    ),
                    "variable_id": targets[target_index],
                }
            )
    independent_items.sort(key=lambda item: (item["source_path"], item["variable_id"]))
    if list(items) != independent_items:
        raise ValueError("Complete N13a consumed demand identities differ")

    # Independent iterative walk of every S3 object; normalization stays owner-owned.
    independent_units: defaultdict[str, set[str]] = defaultdict(set)
    unit_occurrences = []
    stack = [("", payload)]
    while stack:
        pointer, value = stack.pop()
        if isinstance(value, dict):
            if "slot_id" in value and "unit" in value:
                slot, unit = value["slot_id"], value["unit"]
                if isinstance(slot, str) and slot.strip() and isinstance(unit, str):
                    normalized = read_api.catalog.normalize_acquisition_unit(unit)
                    if normalized:
                        independent_units[slot.strip()].add(normalized)
                        unit_occurrences.append([pointer, slot.strip(), normalized])
            stack.extend(
                (pointer + "/" + key.replace("~", "~0").replace("/", "~1"), child)
                for key, child in value.items()
            )
        elif isinstance(value, list):
            stack.extend((pointer + "/" + str(index), child) for index, child in enumerate(value))
    independent_slots = {
        key: tuple(sorted(values)) for key, values in sorted(independent_units.items())
    }
    if slots != independent_slots:
        raise ValueError("Complete N13b normalized slot/unit identities differ")
    if reentry != {"slot_id": target, "units": independent_slots[target]}:
        raise ValueError("Actual N13b re-entry target projection differs")
    recursive, iterative = _nodes(payload), _stack_nodes(payload)
    if recursive != iterative:
        raise ValueError("Complete S3 JSON node identities differ")
    projections = {
        "n13a_world_slot_demands": list(items),
        "n13a_binding": binding.model_dump(mode="json"),
        "n13b_complete_slot_units": slots,
        "n13b_reentry_target": reentry,
    }
    statistics = {
        "s3_json_node_denominator": len(recursive),
        "independent_s3_json_node_denominator": len(iterative),
        "n13a_demand_item_denominator": len(items),
        "independent_n13a_demand_item_denominator": len(independent_items),
        "n13b_slot_denominator": len(slots),
        "independent_n13b_slot_denominator": len(independent_slots),
        "n13b_slot_unit_pair_denominator": sum(map(len, slots.values())),
        "independent_n13b_slot_unit_pair_denominator": len(
            {(row[1], row[2]) for row in unit_occurrences}
        ),
        "all_complete_identity_reconciliations_equal": True,
        "projection_hashes": {key: _hash(_canonical(value)) for key, value in projections.items()},
        "actual_n13a_binding_content_sha256": binding.projection_content_sha256,
        "actual_n13b_reentry_content_sha256": checker.content_sha256(reentry),
    }
    return projections, statistics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-ref", default=PREVIOUS)
    parser.add_argument("--after", action="store_true")
    parser.add_argument("--baseline-receipt", type=Path)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    from polisyos.data_forge import read_api
    from tools.quality.validation import check_layer3_gy_acquisition_executor as checker
    from tools.quality.validation import layer3_gy_acquisition_executor as executor
    from tools.quality.validation import layer3_gy_n13a_acquisition_census as census

    owner_paths = {
        Path(inspect.getfile(value)).resolve()
        for value in (
            census._extract_substrate_demand_items,
            census._projection_binding,
            executor._slot_units,
            checker._substrate_slot_projection,
            read_api.catalog.normalize_acquisition_unit,
        )
    }
    route_path = root / executor.DEFAULT_D6_ROUTE_SELECTION
    immutable_paths = owner_paths | {route_path}
    initial = {path: path.read_bytes() for path in immutable_paths}
    route = executor.D6RouteSelection.model_validate_json(initial[route_path])
    old_raw = subprocess.run(  # noqa: S603 - fixed read-only argv, no shell
        ["git", "show", args.before_ref + ":policy-engine/" + S3],  # noqa: S607
        check=True,
        capture_output=True,
    ).stdout
    old_payload = _strict_object(old_raw)
    before, before_stats = _projection(old_payload, target=route.target_variable)
    evidence = {
        "probe": "actual_N13_consumed_S3_projection_equality",
        "mode": "after" if args.after else "before",
        "before_source": S3 + "@" + args.before_ref,
        "before_raw_sha256": _hash(old_raw),
        "owner_and_route_source_hashes": {
            path.relative_to(root).as_posix(): _hash(raw) for path, raw in sorted(initial.items())
        },
        "reentry_target_variable": route.target_variable,
        "declared_reentry_projection_sha256": route.substrate_slot_projection_sha256,
        "before": before_stats,
        "limit": (
            "Projection equality only; no N13 full gate, catalog/source check, "
            "or reissue is claimed."
        ),
    }
    if args.after:
        if args.baseline_receipt is None:
            raise ValueError("After comparison requires the complete retained before receipt")
        receipt = json.loads(args.baseline_receipt.read_bytes())
        if receipt["returncode"] != 0 or receipt["timed_out"] is not False:
            raise ValueError("Before projection command did not complete")
        baseline = json.loads(receipt["stdout"])
        for key in (
            "before_source",
            "before_raw_sha256",
            "owner_and_route_source_hashes",
            "before",
        ):
            if baseline[key] != evidence[key]:
                raise ValueError("Before projection/source changed since its receipt: " + key)
        current_raw = (root / S3).read_bytes()
        current = _strict_object(current_raw)
        after, after_stats = _projection(current, target=route.target_variable)
        projection_deltas = {}
        for key in before:
            left = _nodes(json.loads(_canonical(before[key])))
            right = _nodes(json.loads(_canonical(after[key])))
            absent = object()
            projection_deltas[key] = sorted(
                path
                for path in left.keys() | right.keys()
                if left.get(path, absent) != right.get(path, absent)
            )
        left, right = _nodes(old_payload), _nodes(current)
        absent = object()
        changed = sorted(
            path
            for path in left.keys() | right.keys()
            if left.get(path, absent) != right.get(path, absent)
        )
        set_deltas, represented = _compact_identity_sets(old_payload, current)
        residual = [
            path
            for path in changed
            if not any(path == prefix or path.startswith(prefix + "/") for prefix in represented)
        ]
        evidence.update(
            {
                "after_source": S3,
                "after_raw_sha256": _hash(current_raw),
                "after": after_stats,
                "complete_consumed_projection_node_deltas": projection_deltas,
                "consumed_projection_values_equal": before == after,
                "complete_s3_source_set_identity_deltas": set_deltas,
                "source_set_semantics_owner": (
                    "src/polisyos/runtime/quality/intervention_substrate.py"
                    "#_intervention_substrate_strangle_receipts"
                ),
                "complete_s3_residual_changed_json_nodes": [
                    {
                        "pointer": path,
                        "before": {"presence": "present", "node": left[path]}
                        if path in left
                        else {"presence": "absent"},
                        "after": {"presence": "present", "node": right[path]}
                        if path in right
                        else {"presence": "absent"},
                    }
                    for path in residual
                ],
            }
        )
        if (root / S3).read_bytes() != current_raw:
            raise ValueError("Current S3 changed during comparison")
    for path, raw in initial.items():
        if path.read_bytes() != raw:
            raise ValueError("Actual extraction owner or route changed during comparison")
    print(json.dumps(evidence, indent=2, sort_keys=True))  # noqa: T201
    if args.after and before != after:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
