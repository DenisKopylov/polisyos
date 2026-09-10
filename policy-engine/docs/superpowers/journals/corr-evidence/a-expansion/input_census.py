"""Enumerate the complete held refusal-expansion inputs without runtime admission.

This research diagnostic compares two independent set constructions over the
same held sources. It does not make those sources independent evidence.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
FRAME = Path("architecture/policy_design_case/corr/grounding-2026-09-08/frame.json")
SUITE = Path("architecture/policy_design_case/corr/grounding-2026-09-08/suite.json")
PROOF_INPUT = Path("architecture/policy_design_case/corr/grounding_proof_world_input.json")
KNOBS = Path(
    "production_data/ukraine_agent_simulation_baseline_20260410/production_bundle/"
    "bundles/intervention_bundle_v1/intervention_knob_dictionary.json"
)


def digest(value: object) -> str:
    """Hash a canonical diagnostic identity value, not an authority receipt."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"ambiguous_duplicate_json_key:{key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    """Read complete JSON, treating duplicate keys or a non-object as ambiguous."""
    result = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
    if not isinstance(result, dict):
        raise ValueError(f"ambiguous_nonobject_json:{path}")
    return result


def blob_ref(path: Path) -> str:
    """Name tracked bytes without copying the input artifact into a receipt."""
    git = shutil.which("git")
    if git is None:
        raise ValueError("required_git_executable_absent")
    result = subprocess.run(  # noqa: S603 -- fixed read-only git command and local input path.
        [git, "hash-object", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return f"{path}@{result.stdout.strip()}"


def input_census() -> dict[str, Any]:
    """Reconcile all assignment, slot, and proposed mutation identities."""
    frame = read_json(ROOT / FRAME)
    suite = read_json(ROOT / SUITE)
    binding = read_json(ROOT / PROOF_INPUT)
    knobs = read_json(ROOT / KNOBS)
    # This path is the existing declared exact CAS byte input. The existing Core
    # loader remains the sole runtime authority for decoding/admitting the WMR.
    world_id = binding["source_ref"]["artifact_id"].removeprefix("sha256:")
    world_path = Path(binding["cas_root"]) / "artifacts/sha256" / world_id[:2] / world_id[2:4]
    world_path /= world_id + ".blob"
    world_bytes = (ROOT / world_path).read_bytes()
    if hashlib.sha256(world_bytes).hexdigest() != world_id:
        raise ValueError("declared_world_cas_byte_hash_mismatch")
    world = read_json(ROOT / world_path)
    rows = frame["inputs"]
    slots_raw = world["policy_slot_map"]
    assignments: set[tuple[str, str]] = set()
    operators: set[str] = set()
    for row in rows:
        if row["ambiguity"] is not None or len(row["signature"]["X_do"]) != 1:
            raise ValueError(f"ambiguous_assignment:{row['input_id']}")
        if row["input_id"] != row["operator_family"] or row["input_id"] in operators:
            raise ValueError("ambiguous_assignment_operator_identity")
        operators.add(row["input_id"])
        assignments.add((row["input_id"], row["signature"]["X_do"][0]))
    slots = {row["slot_id"] for row in slots_raw}
    if len(slots) != len(slots_raw):
        raise ValueError("ambiguous_duplicate_world_slot_identity")
    raw_operators = set(knobs)
    if operators != raw_operators:
        raise ValueError(f"operator_identity_delta:{sorted(operators ^ raw_operators)}")
    if not {target for _, target in assignments}.issubset(slots):
        raise ValueError("actual_assignment_outside_complete_world_slot_set")
    direct = {
        (operator, slot) for operator, actual in assignments for slot in slots if slot != actual
    }
    independent = set(itertools.product(raw_operators, slots)) - assignments
    if direct != independent:
        raise ValueError(f"transposition_identity_delta:{sorted(direct ^ independent)}")
    signs = {(case["case_id"], case["source_input_hash"]) for case in suite["mismatches"]}
    if len(signs) != len(suite["mismatches"]) or len(signs) != len(assignments):
        raise ValueError("opposite_sign_identity_partition_mismatch")
    source_units = {unit for row in rows for unit in row["source_units"]}
    return {
        "schema_version": "corr.refusal_expansion_input_census.v1",
        "synthetic": True,
        "status": "passed",
        "purpose": "pre_outcome_construction_support_only",
        "tracked_sources": [blob_ref(path) for path in (FRAME, SUITE, PROOF_INPUT)],
        "raw_knob_source": str(KNOBS),
        "raw_knob_bytes_sha256": "sha256:"
        + hashlib.sha256((ROOT / KNOBS).read_bytes()).hexdigest(),
        "world_cas_byte_identity": "sha256:" + world_id,
        "world_logical_content_hash": world["content_hash"],
        "file_type_denominators": {
            "frame": "complete JSON inputs array",
            "raw_knob_dictionary": "complete root JSON object key set",
            "world": "complete JSON policy_slot_map array",
            "suite": "complete JSON mismatches array",
        },
        "operator_count": len(operators),
        "operator_identity_hash": digest(sorted(operators)),
        "world_slot_count": len(slots),
        "world_slot_identity_hash": digest(sorted(slots)),
        "assignment_count": len(assignments),
        "assignment_identity_hash": digest(sorted(assignments)),
        "opposite_sign_count": len(signs),
        "opposite_sign_identity_hash": digest(sorted(signs)),
        "target_transposition_count": len(direct),
        "target_transposition_identity_hash": digest(sorted(direct)),
        "independent_target_transposition_identity_hash": digest(sorted(independent)),
        "proposed_case_count": len(direct) + len(signs),
        "identity_delta": [],
        "source_unit_count": len(source_units),
        "source_unit_identity_hash": digest(sorted(source_units)),
        "independence": "not_established; same held support, algorithmic set reconciliation only",
        "runtime_refusal_result": "not_established; no binder or solver invoked",
    }


def main() -> int:
    """Print the complete deciding census, without writing old artifacts."""
    sys.stdout.write(json.dumps(input_census(), indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
