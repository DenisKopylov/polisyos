"""Read retained L receipts only; reconcile identities without importing a product owner.

Exit 0 means the receipts were reconciled, not that GX or native tests passed.
Exit 1 means a contradictory receipt; exit 2 means a required receipt is unreadable.
No derived report is written. Finding bodies appear only in requested set deltas.
"""

# ruff: noqa: ANN401, T201, SIM401 - arbitrary retained JSON; field presence is explicit.

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Never

PREFIXES = ("GY_POST_OUTPUT_GX ", "GY_L_NATIVE_POPULATION ", "GY_L_NATIVE_READBACK ")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ReceiptError(ValueError):
    """Receipt cannot support the requested reconciliation."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def structural(value: Any) -> tuple:
    """Independent typed structural encoding; absence stays absent in object keys."""
    if isinstance(value, dict):
        return ("object", tuple((key, structural(item)) for key, item in sorted(value.items())))
    if isinstance(value, list):
        return ("array", tuple(map(structural, value)))
    return (type(value).__name__, repr(value))


def strict_json(raw: str | bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                raise ReceiptError("duplicate_json_key:" + key)
            result[key] = value
        return result

    def invalid(value: str) -> Never:
        raise ReceiptError("nonfinite_json_number:" + value)

    def finite(value: str) -> float:
        parsed = float(value)
        require(math.isfinite(parsed), "nonfinite_json_number:" + value)
        return parsed

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ReceiptError(reason)


def field(mapping: Any, key: str, expected: type) -> Any:
    require(isinstance(mapping, dict), "parent_not_object:" + key)
    require(key in mapping, "field_absent:" + key)
    value = mapping[key]
    require(
        type(value) is expected, "field_" + ("null" if value is None else "wrong_type") + ":" + key
    )
    return value


def unique_strings(value: Any, label: str) -> set[str]:
    require(
        isinstance(value, list) and all(type(item) is str for item in value),
        label + ":not_string_list",
    )
    result = set(value)
    require(len(result) == len(value), label + ":duplicate_identities")
    return result


def delta(before: set[str], after: set[str]) -> dict[str, Any]:
    return {"lost": sorted(before - after), "added": sorted(after - before)}


def packets(receipt: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    found = []
    for stream in ("stdout", "stderr"):
        for number, raw_line in enumerate(field(receipt, stream, str).splitlines(), 1):
            line = ANSI.sub("", raw_line)
            # Pytest -q can leave progress dots immediately before an owner print.
            match = re.match(r"^[.FEspxXS]*" + re.escape(prefix) + r"(.*)$", line)
            if match is None:
                continue
            payload = strict_json(match.group(1))
            require(isinstance(payload, dict), "packet_not_object:" + prefix.strip())
            found.append({"stream": stream, "line": number, "payload": payload})
    return found


def classify_sources(packet: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    refs = field(packet, "source_refs", dict)
    for path, value in refs.items():
        parsed = PurePosixPath(path)
        require(
            not parsed.is_absolute()
            and all(part not in {"", ".", ".."} for part in path.split("/")),
            "source_ref_not_relative:" + path,
        )
        require(
            type(value) is str and HASH.fullmatch(value) is not None,
            "source_ref_hash_invalid:" + path,
        )
    groups = {
        suffix: {path for path in refs if PurePosixPath(path).suffix == suffix}
        for suffix in (".json", ".py")
    }
    # An unknown source kind cannot silently fall out of either denominator.
    require(
        set(refs) == groups[".json"] | groups[".py"],
        "source_refs_unclassified:"
        + canonical(sorted(set(refs) - groups[".json"] - groups[".py"])),
    )
    independent = Counter(path.rsplit(".", 1)[-1] for path in refs)
    for suffix, name in (
        (".json", "complete_gx_artifact_denominator"),
        (".py", "complete_gx_python_denominator"),
    ):
        expected = field(verification, name, int)
        require(
            expected > 0 and expected == len(groups[suffix]) == independent[suffix[1:]],
            "source_denominator_mismatch:" + name,
        )
    inputs = field(verification, "input_artifact_hashes", dict)
    require(bool(inputs), "fresh_family_hashes_empty")
    for path, value in inputs.items():
        require(
            path in groups[".json"] and refs[path] == value,
            "fresh_family_source_hash_mismatch:" + path,
        )
    native = field(packet, "native_source", dict)
    path, state = field(native, "path", str), field(native, "state", str)
    require(path not in refs, "native_source_conflated_with_declared_scan:" + path)
    require("sha256" in native, "native_sha256_absent")
    require(state in {"absent", "present"}, "native_state_not_established:" + state)
    require(
        native["sha256"] is None
        if state == "absent"
        else type(native["sha256"]) is str and HASH.fullmatch(native["sha256"]) is not None,
        "native_hash_state_mismatch",
    )
    return {
        "source_ref_denominator": len(refs),
        "artifact_denominator": len(groups[".json"]),
        "python_denominator": len(groups[".py"]),
        "independent_suffix_denominators": dict(sorted(independent.items())),
        "complete_source_ref_identity_sha256": digest(sorted(refs)),
        "complete_source_ref_hashes_sha256": digest(refs),
        "fresh_family_member_denominator": len(inputs),
        "native_source": native,
        "scope": (
            "complete emitted source_refs partition; no live repository scan or authenticity claim"
        ),
    }


def reconcile_gx(item: dict[str, Any]) -> tuple[dict[str, Any], set[str] | None]:
    packet = item["payload"]
    result = {"stream": item["stream"], "line": item["line"], "packet_sha256": digest(packet)}
    if "verification" not in packet or packet["verification"] is None:
        result.update(
            {
                "measurement_state": "not_established",
                "reason": "verification_absent"
                if "verification" not in packet
                else "verification_null",
                "finding_identities": None,
            }
        )
        for key in ("child_returncode",):
            if key in packet:
                result[key] = packet[key]
        child = {"stdout": packet.get("child_stdout", ""), "stderr": packet.get("child_stderr", "")}
        if all(type(value) is str for value in child.values()):
            errors = packets(child, "GY_POST_GX_RESULT ")
            result["child_errors"] = [
                {
                    key: entry["payload"][key]
                    for key in ("error_type", "error", "denied_events", "actual_json_read_issues")
                    if key in entry["payload"]
                }
                for entry in errors
            ]
        return result, None
    verification = field(packet, "verification", dict)
    report = field(packet, "report", dict)
    issues = field(report, "issues", list)
    require(all(type(issue) is dict for issue in issues), "report_issue_not_object")
    declared = unique_strings(
        field(verification, "finding_identities", list), "verification.finding_identities"
    )
    ordered_declared = sorted(declared)
    decoded = [strict_json(identity) for identity in ordered_declared]
    require(all(type(issue) is dict for issue in decoded), "finding_identity_not_object")
    require(
        all(
            canonical(issue) == identity
            for issue, identity in zip(decoded, ordered_declared, strict=True)
        ),
        "finding_identity_not_canonical",
    )
    actual = {canonical(issue) for issue in issues}
    require(
        actual == declared, "finding_identity_set_mismatch:" + canonical(delta(actual, declared))
    )
    require(
        {structural(issue) for issue in issues} == {structural(issue) for issue in decoded},
        "independent_structural_identity_set_mismatch",
    )
    summary = field(report, "summary", dict)
    require(
        field(summary, "issue_count", int) == len(issues), "report_full_issue_denominator_mismatch"
    )
    status = field(report, "status", str)
    require(status in {"pass", "fail", "expected_red"}, "report_status_unknown")
    require(field(verification, "status", str) == status, "verification_report_status_mismatch")
    require(
        field(verification, "case_id", str) == field(report, "case_id", str),
        "verification_report_case_mismatch",
    )
    require(field(report, "write", bool) is False, "gx_was_not_read_only")
    require(status != "pass" or not actual, "gx_pass_with_findings")
    require(packet.get("child_returncode", 0) == 0, "verification_present_after_child_error")
    require(packet.get("actual_json_states_rechecked") is True, "actual_json_states_not_rechecked")
    json_states = field(packet, "actual_json_read_states", dict)
    for path, record in json_states.items():
        state = field(record, "state", str)
        require(state in {"absent", "present"}, "actual_json_state_not_established:" + path)
        require(
            "sha256" in record and "json_type" in record, "actual_json_state_fields_absent:" + path
        )
        mapping = field(record, "mapping_required", bool)
        if state == "absent":
            require(
                record["sha256"] is None and record["json_type"] is None,
                "absent_json_has_present_fields:" + path,
            )
        else:
            require(
                type(record["sha256"]) is str and HASH.fullmatch(record["sha256"]) is not None,
                "present_json_hash_invalid:" + path,
            )
            require(
                record["json_type"] in {"object", "array", "null", "scalar"},
                "present_json_type_invalid:" + path,
            )
            require(
                not mapping or record["json_type"] == "object",
                "mapping_read_admitted_nonobject:" + path,
            )
    result.update(
        {
            "measurement_state": "measured",
            "gx_status": status,
            "issue_row_denominator": len(issues),
            "finding_identity_denominator": len(actual),
            "complete_finding_identity_sha256": digest(sorted(actual)),
            "independent_structural_set_reconciled": True,
            "report_projection": "all_members_except_recomputable_artifacts",
            "full_report_hash_validation": (
                "not_recomputed: omitted artifact bodies are not in the receipt"
            ),
            "sources": classify_sources(packet, verification),
            "actual_json_read_state_denominator": len(json_states),
        }
    )
    return result, actual


def base_node(nodeid: str) -> str:
    return nodeid.split("[", 1)[0]


def reconcile_native(receipt: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str] | None]:
    populations, readbacks = packets(receipt, PREFIXES[1]), packets(receipt, PREFIXES[2])
    if not populations and not readbacks:
        return {"measurement_state": "not_established", "reason": "native_transport_absent"}, None
    require(len(populations) == len(readbacks) == 1, "native_transport_missing_or_duplicated")
    population, readback = populations[0]["payload"], readbacks[0]["payload"]
    nodes = unique_strings(field(population, "nodes", list), "native.selected_nodes")
    collected = unique_strings(field(readback, "collected", list), "native.collected")
    require(nodes and collected, "native_population_empty")
    require(
        {base_node(node) for node in collected} == nodes,
        "native_collected_selection_mismatch:"
        + canonical(delta(nodes, {base_node(node) for node in collected})),
    )
    definitions = field(population, "definition_denominator", int)
    require(
        definitions == field(population, "independent_denominator", int)
        and definitions >= len(nodes),
        "native_definition_denominators_mismatch",
    )
    is_correction = "failed_from" in population and population["failed_from"] is not None
    require(is_correction or definitions == len(nodes), "native_full_definition_population_missing")
    require(
        not is_correction or type(population["failed_from"]) is str, "native_failed_from_wrong_type"
    )
    outcomes = field(readback, "outcomes", list)
    events, status_pairs, effective = set(), set(), {}
    for row in outcomes:
        identity, when, outcome = (
            field(row, "nodeid", str),
            field(row, "when", str),
            field(row, "outcome", str),
        )
        require(
            identity in collected
            and when in {"setup", "call", "teardown"}
            and outcome in {"passed", "failed", "skipped"},
            "native_progress_identity_or_state_invalid",
        )
        event = (identity, when)
        require(event not in events, "native_duplicate_phase_event:" + canonical(event))
        events.add(event)
        status = "error" if outcome == "failed" and when != "call" else outcome
        status_pairs.add((identity, status))
        if identity not in effective or outcome != "passed":
            effective[identity] = status
    require(
        set(effective) == collected,
        "native_progress_missing_identities:" + canonical(delta(collected, set(effective))),
    )
    require(
        field(readback, "collected_denominator", int)
        == field(readback, "reported_denominator", int)
        == len(collected),
        "native_reported_denominator_mismatch",
    )
    summary_pairs = set()
    summary_rows = []
    for stream in ("stdout", "stderr"):
        for raw_line in receipt[stream].splitlines():
            line = ANSI.sub("", raw_line)
            match = re.match(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (.*)$", line)
            if match is None:
                continue
            remainder = match.group(2)
            candidates = [
                node
                for node in collected
                if remainder == node or remainder.startswith(node + " - ")
            ]
            require(len(candidates) == 1, "native_summary_identity_unresolved:" + line)
            status = {
                "PASSED": "passed",
                "FAILED": "failed",
                "ERROR": "error",
                "SKIPPED": "skipped",
                "XFAIL": "xfail",
                "XPASS": "xpass",
            }[match.group(1)]
            summary_rows.append((candidates[0], status))
            summary_pairs.add(summary_rows[-1])
    require(len(summary_rows) == len(summary_pairs), "native_summary_identity_duplicate")
    require(
        summary_pairs == status_pairs,
        "native_summary_progress_identity_mismatch:"
        + canonical(
            delta(
                {canonical(pair) for pair in status_pairs},
                {canonical(pair) for pair in summary_pairs},
            )
        ),
    )
    require(
        field(readback, "returncode", int) == field(receipt, "returncode", int),
        "native_outer_inner_exit_mismatch",
    )
    require(not receipt.get("timed_out", False), "native_outer_receipt_timed_out")
    require(
        receipt["returncode"] != 0 or all(value == "passed" for value in effective.values()),
        "native_zero_exit_with_nonpass",
    )
    require(
        not all(value == "passed" for value in effective.values()) or receipt["returncode"] == 0,
        "native_nonzero_exit_without_reported_failure",
    )
    return {
        "measurement_state": "measured",
        "status": "pass" if all(value == "passed" for value in effective.values()) else "fail",
        "source": field(population, "source", str),
        "source_sha256": field(population, "source_sha256", str),
        "definition_denominator": definitions,
        "selected_definition_denominator": len(nodes),
        "expanded_identity_denominator": len(collected),
        "progress_phase_denominator": len(events),
        "summary_identity_denominator": len(summary_pairs),
        "outcome_denominators": dict(sorted(Counter(effective.values()).items())),
        "complete_collected_identity_sha256": digest(sorted(collected)),
        "complete_progress_identity_sha256": digest(sorted(events)),
        "complete_summary_identity_sha256": digest(sorted(summary_pairs)),
        "nonpassing_identities": sorted(
            node for node, status in effective.items() if status != "passed"
        ),
        "failed_from_state": "absent"
        if "failed_from" not in population
        else "null"
        if population["failed_from"] is None
        else "present",
        "failed_from": population["failed_from"] if "failed_from" in population else None,
    }, effective


def read_receipt(
    path: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[set[str] | None], dict[str, str] | None]:
    raw = path.read_bytes()
    receipt = strict_json(raw)
    require(type(receipt) is dict, "receipt_not_object")
    field(receipt, "stdout", str)
    field(receipt, "stderr", str)
    result = {
        "receipt": str(path),
        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "original_returncode": receipt["returncode"] if "returncode" in receipt else "absent",
        "original_timed_out": receipt["timed_out"] if "timed_out" in receipt else "absent",
        "gx_packets": [],
        "errors": [],
    }
    identity_sets = []
    for index, item in enumerate(packets(receipt, PREFIXES[0])):
        try:
            packet_result, identities = reconcile_gx(item)
        except (ReceiptError, ValueError, TypeError) as error:
            packet_result, identities = (
                {"measurement_state": "not_established", "reason": str(error)},
                None,
            )
            result["errors"].append({"gx_packet_index": index, "reason": str(error)})
        result["gx_packets"].append({"index": index, **packet_result})
        identity_sets.append(identities)
    if not identity_sets:
        result["gx_measurement"] = {
            "measurement_state": "not_established",
            "reason": "post_output_gx_packet_absent",
            "finding_identities": None,
        }
    try:
        result["native"], native = reconcile_native(receipt)
    except (ReceiptError, ValueError, TypeError) as error:
        result["native"], native = (
            {"measurement_state": "not_established", "reason": str(error)},
            None,
        )
        result["errors"].append({"native": str(error)})
    require(path.read_bytes() == raw, "receipt_changed_during_read")
    return receipt, result, identity_sets, native


def chosen(sets: list[set[str] | None], index: int | None) -> set[str] | None:
    require(index is not None or len(sets) == 1, "comparison_requires_explicit_packet_index")
    selected = 0 if index is None else index
    require(0 <= selected < len(sets), "comparison_packet_index_out_of_bounds")
    return sets[selected]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument(
        "--after", type=Path, help="Optional second GX receipt; never union separate invocations"
    )
    parser.add_argument("--packet", type=int)
    parser.add_argument("--after-packet", type=int)
    parser.add_argument(
        "--correction",
        type=Path,
        action="append",
        default=[],
        help="Native correction receipts in execution order",
    )
    args = parser.parse_args()
    paths = [args.receipt, *([args.after] if args.after else []), *args.correction]
    results, read = [], {}
    try:
        for path in dict.fromkeys(paths):
            read[path] = read_receipt(path)
            results.append(read[path][1])
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        print(
            json.dumps(
                {
                    "reconciliation_status": "not_established",
                    "reason": str(error),
                    "receipts": results,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    output = {
        "scope": (
            "receipt-only reconciliation; does not rerun a gate "
            "or prove a positive status from an exit code"
        ),
        "receipts": results,
    }
    problems = []
    if args.after:
        try:
            before, after = (
                chosen(read[args.receipt][2], args.packet),
                chosen(read[args.after][2], args.after_packet),
            )
            output["gx_identity_delta"] = (
                {
                    "measurement_state": "not_established",
                    "reason": "selected_invocation_has_no_measured_finding_set",
                    "lost": None,
                    "added": None,
                }
                if before is None or after is None
                else {
                    "measurement_state": "measured",
                    "before_denominator": len(before),
                    "after_denominator": len(after),
                    "baseline_identity_loss": bool(before - after),
                    **delta(before, after),
                }
            )
        except ReceiptError as error:
            problems.append(str(error))
    if args.correction:
        effective = read[args.receipt][3]
        known = {args.receipt.resolve(): read[args.receipt]}
        correction_results = []
        for path in args.correction:
            receipt, report, _, current = read[path]
            entry = {"receipt": str(path)}
            if effective is None or current is None:
                entry.update(
                    {
                        "measurement_state": "not_established",
                        "reason": "native_identity_basis_unavailable",
                    }
                )
                effective = None
            else:
                required = {node for node, state in effective.items() if state != "passed"}
                entry.update(
                    {
                        "measurement_state": "measured",
                        "required_nonpassing_denominator": len(required),
                        "retested_denominator": len(current),
                        "uncovered_prior_nonpassing": sorted(required - current.keys()),
                        "new_outside_baseline": sorted(current.keys() - effective.keys()),
                    }
                )
                if current.keys() - effective.keys():
                    problems.append(
                        "native_correction_added_identity_outside_baseline:" + str(path)
                    )
                previous = report["native"]["failed_from"]
                if previous is None:
                    problems.append("native_correction_failed_from_not_supplied:" + str(path))
                else:
                    prior_path = Path(previous)
                    if not prior_path.is_absolute():
                        prior_path = Path(field(receipt, "cwd", str)) / prior_path
                    prior = known.get(prior_path.resolve())
                    if prior is None or prior[3] is None:
                        problems.append("native_correction_predecessor_not_supplied:" + previous)
                    else:
                        selected_bases = {
                            base_node(node)
                            for node, status in prior[3].items()
                            if status != "passed"
                        }
                        expected = {node for node in prior[3] if base_node(node) in selected_bases}
                        entry["selected_failed_predecessor_delta"] = delta(expected, set(current))
                        if expected != set(current):
                            problems.append(
                                "native_correction_selection_does_not_replay_complete_failed_definitions:"
                                + str(path)
                            )
                effective = {
                    **effective,
                    **{node: state for node, state in current.items() if node in effective},
                }
            correction_results.append(entry)
            known[path.resolve()] = read[path]
        correction_valid = effective is not None and not problems
        output["native_corrections"] = {
            "steps": correction_results,
            "measurement_state": "measured" if correction_valid else "not_established",
            "final_status": None
            if not correction_valid
            else "pass"
            if all(status == "passed" for status in effective.values())
            else "fail",
            "final_denominator": None if effective is None else len(effective),
            "remaining_nonpassing": None
            if effective is None
            else sorted(node for node, status in effective.items() if status != "passed"),
            "source_change_policy": (
                "source hashes remain visible per wave; correction overlay does not claim "
                "old passing nodes reran on the new source"
            ),
        }
    bad = problems or any(result["errors"] for result in results)
    output.update(
        {"reconciliation_status": "contradictory" if bad else "reconciled", "errors": problems}
    )
    print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except (ReceiptError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"reconciliation_status": "not_established", "reason": str(error)}))
        exit_code = 1
    raise SystemExit(exit_code)
