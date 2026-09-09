"""Independently reconcile all emitted case identities against held raw inputs."""

from __future__ import annotations

import argparse
import copy
import importlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any

_input = importlib.import_module("docs.superpowers.journals.corr-evidence.a-expansion.input_census")
HERE = Path(__file__).resolve().parent


def reconcile(report: dict[str, Any]) -> dict[str, Any]:
    """Compare identity sets, including duplicates; never infer coverage from totals."""
    census = _input.input_census()
    frame = _input.read_json(_input.ROOT / _input.FRAME)
    binding = _input.read_json(_input.ROOT / _input.PROOF_INPUT)
    artifact_id = binding["source_ref"]["artifact_id"].removeprefix("sha256:")
    blob = (
        _input.ROOT
        / binding["cas_root"]
        / "artifacts/sha256"
        / artifact_id[:2]
        / artifact_id[2:4]
        / (artifact_id + ".blob")
    )
    world = _input.read_json(blob)
    assignments = {(row["operator_family"], row["signature"]["X_do"][0]) for row in frame["inputs"]}
    operators = {operator for operator, _target in assignments}
    slots = {slot["slot_id"] for slot in world["policy_slot_map"]}
    expected = {f"opposite_sign:{operator}" for operator in operators}
    expected |= {
        f"target_assignment:{operator}:{target}"
        for operator, target in set(itertools.product(operators, slots)) - assignments
    }
    actual_rows = report["outcomes"]
    actual = {row["case_id"] for row in actual_rows}
    control_rows = report["matched_controls_outside_negative_denominator"]
    controls = {row["source_operator"] for row in control_rows}
    issues = []
    if expected != actual:
        issues.append("complete_case_identity_delta")
    if len(actual_rows) != len(actual):
        issues.append("duplicate_emitted_case_identity")
    if controls != operators or len(control_rows) != len(controls):
        issues.append("complete_matched_control_identity_delta")
    if any(row["runtime_status"] != "executed" for row in actual_rows):
        issues.append("predeclared_executable_case_not_executed")
    proposal_hashes = {row["proposal_hash"] for row in actual_rows}
    if len(proposal_hashes) != len(actual_rows):
        issues.append("duplicate_normalized_proposal")
    if report["synthetic"] is not True or any(
        row["synthetic"] is not True for row in (*actual_rows, *control_rows)
    ):
        issues.append("own_emission_synthetic_marker_missing")
    return {
        "schema_version": "corr.refusal_expansion_identity_reconciliation.v1",
        "synthetic": True,
        "status": "passed" if not issues else "failed",
        "issues": issues,
        "denominator": (
            "complete frozen assignment JSON array x complete pinned WMR slot JSON array"
        ),
        "expected_case_count": len(expected),
        "actual_case_count": len(actual_rows),
        "expected_identity_hash": _input.digest(sorted(expected)),
        "actual_identity_hash": _input.digest(sorted(actual)),
        "missing": sorted(expected - actual),
        "unexpected": sorted(actual - expected),
        "expected_control_count": len(operators),
        "actual_control_count": len(control_rows),
        "expected_control_identity_hash": _input.digest(sorted(operators)),
        "actual_control_identity_hash": _input.digest(sorted(controls)),
        "missing_controls": sorted(operators - controls),
        "unexpected_controls": sorted(controls - operators),
        "input_census_status": census["status"],
        "independence": "algorithmic reconciliation over one shared support population",
        "correctness_or_refusal_rate_claim": "out_of_scope; this gate reconciles identities only",
    }


def main() -> int:
    """Read only the new report; the removal changes an in-memory copy."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove-one-emission", action="store_true")
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    if args.capture is not None:
        capture = _input.read_json(args.capture)
        if capture["timed_out"] is not False or capture["returncode"] not in {0, 1}:
            raise ValueError("cannot_reconcile_timed_out_or_unexecuted_capture")
        report = json.loads(capture["stdout"])
    else:
        report = _input.read_json(HERE / "2026-09-09-refusal-expansion.json")
    if args.remove_one_emission:
        report = copy.deepcopy(report)
        report["outcomes"].pop()
    result = reconcile(report)
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 1 if result["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
