"""Reconcile complete controlling and historical sets without retaining derived copies."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from polisyos.pdc import gy_content_hash


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        if key in result:
            raise ValueError(f"ambiguous_duplicate_json_key:{key}")
        result[key] = value
    return result


def _ids(values: list[str]) -> set[str]:
    if len(set(values)) != len(values):
        raise ValueError("ambiguous_duplicate_identity")
    return set(values)


def _delta(before: set[str], after: set[str]) -> dict[str, Any]:
    return {
        "before": len(before),
        "after": len(after),
        "removed": sorted(before - after),
        "added": sorted(after - before),
    }


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _parsed_mutation_ids(data: bytes) -> set[str]:
    parsed: list[str] = []

    def hook(row: dict[str, Any]) -> dict[str, Any]:
        if "mutation_id" in row:
            parsed.append(row["mutation_id"])
        return row

    json.loads(data, object_hook=hook)
    return _ids(parsed)


def main() -> int:
    """Compare every member; unreadable or duplicate input fails as ambiguous."""
    root = Path.cwd()
    base = "9619f6d2d892d7994ae3f29d3230362c41862f2d"
    report_path = Path("architecture/policy_design_case/grounding_bind_contract.json")
    before_bytes = subprocess.check_output(  # noqa: S603 -- fixed read-only git argv
        ["/usr/bin/git", "show", f"{base}:policy-engine/{report_path}"], cwd=root
    )
    after_bytes = report_path.read_bytes()
    before = json.loads(before_bytes, object_pairs_hook=_pairs)
    after = json.loads(after_bytes, object_pairs_hook=_pairs)
    sets: dict[str, Any] = {}
    for key in (
        "probes",
        "relation_outcome_map",
        "production_api_boundary_probes",
        "promotability_resolution_probes",
    ):
        sets[key] = _delta(set(before[key]), set(after[key]))
    for name, payload in (("before", before), ("after", after)):
        if set(payload["relation_outcome_map"]) != _ids(payload["relation_outcome_set"]):
            raise ValueError(f"relation_identity_independent_reconciliation_failed:{name}")
    mutation_sets: list[set[str]] = []
    for data, payload in ((before_bytes, before), (after_bytes, after)):
        walked = _ids([row["mutation_id"] for row in payload["behavioral_mutations"]])
        if walked != _parsed_mutation_ids(data):
            raise ValueError("mutation_identity_independent_reconciliation_failed")
        mutation_sets.append(walked)
    sets["behavioral_mutations"] = _delta(*mutation_sets)
    declarations = Path("architecture/policy_design_case/corr/grounding-2026-09-08")
    frame = json.loads((declarations / "frame.json").read_bytes(), object_pairs_hook=_pairs)
    suite = json.loads((declarations / "suite.json").read_bytes(), object_pairs_hook=_pairs)
    source_ref = frame["input_source_refs"]["intervention_knob_dictionary"]
    locator, expected_sha = source_ref.split("@", maxsplit=1)
    source = Path(locator.removeprefix("repo:")).read_bytes()
    decoded_source = json.loads(source, object_pairs_hook=_pairs)
    if gy_content_hash(decoded_source) != expected_sha:
        raise ValueError("owner_source_content_drift")
    raw_ids = set(decoded_source)
    frame_ids = _ids([row["input_id"] for row in frame["inputs"]])
    frame_delta = _delta(raw_ids, frame_ids)
    # Independent graph algorithms over actual supporting-source intersections.
    support = {row["input_id"]: set(row["source_units"]) for row in frame["inputs"]}
    if any(not units for units in support.values()):
        raise ValueError("ambiguous_source_independence_unit")
    unseen = set(support)
    connected: set[frozenset[str]] = set()
    while unseen:
        todo = [unseen.pop()]
        component: set[str] = set(todo)
        while todo:
            current = todo.pop()
            neighbors = {other for other in unseen if support[current] & support[other]}
            unseen -= neighbors
            component |= neighbors
            todo.extend(neighbors)
        connected.add(frozenset(component))
    parents = {key: key for key in support}

    def find(key: str) -> str:
        while parents[key] != key:
            key = parents[key]
        return key

    for left in support:
        for right in support:
            if support[left] & support[right]:
                parents[find(left)] = find(right)
    components: dict[str, set[str]] = {}
    for key in support:
        components.setdefault(find(key), set()).add(key)
    if connected != {frozenset(group) for group in components.values()}:
        raise ValueError("source_cluster_identity_independent_reconciliation_failed")
    result_path = Path("architecture/policy_design_case/corr/grounding_refusal_sensitivity.json")
    result = json.loads(result_path.read_bytes(), object_pairs_hook=_pairs)
    mismatch_ids = _ids([row["case_id"] for row in suite["mismatches"]])
    outcome_ids = _ids([row["case_id"] for row in result["outcomes"]])
    matched_ids = _ids([row["case_id"] for row in result["matched_controls_outside_denominator"]])
    if mismatch_ids != outcome_ids or mismatch_ids != matched_ids:
        raise ValueError("refusal_suite_result_identity_drift")
    if len(suite["mismatches"]) + len(suite["ambiguous_inputs"]) != len(frame_ids):
        raise ValueError("frame_suite_partition_incomplete")
    if result["predeclared_mismatches"] != len(mismatch_ids):
        raise ValueError("reported_refusal_denominator_drift")
    if result["binder_refused"] != sum(row["refused"] for row in result["outcomes"]):
        raise ValueError("reported_refusal_numerator_drift")
    failed = any(row["added"] or row["removed"] for row in [*sets.values(), frame_delta])
    payload = {
        "status": "fail" if failed else "pass",
        "source_report": f"{report_path}@{base}",
        "before_sha": _sha(before_bytes),
        "after_sha": _sha(after_bytes),
        "complete_identity_set_deltas": sets,
        "independent_crosschecks": (
            "relation declaration vs map; mutation object-hook vs list walk; "
            "strict duplicate-aware JSON"
        ),
        "frame_owner_identity_delta": frame_delta,
        "source_clusters": len(connected),
        "cluster_crosscheck": "BFS vs union-find same membership",
        "frame_declaration": f"{declarations}/frame.json@a9453f273a3462d572517a40c238cf9283f667c7",
        "suite_declaration": f"{declarations}/suite.json@a9453f273a3462d572517a40c238cf9283f667c7",
        "suite_and_all_outcome_identity_sets_equal": True,
        "ambiguous_inputs": suite["ambiguous_inputs"],
        "refusal_sensitivity": result["statement"],
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
