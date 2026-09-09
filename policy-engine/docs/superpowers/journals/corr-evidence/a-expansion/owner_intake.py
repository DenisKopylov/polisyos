"""Measure expansion input shape through existing owners without evaluating cases."""

from __future__ import annotations

import importlib
import json
import sys

_census = importlib.import_module(
    "docs.superpowers.journals.corr-evidence.a-expansion.input_census"
)


def _numeric_paths(value: object, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if isinstance(value, dict):
        return {
            path
            for key, nested in value.items()
            for path in _numeric_paths(nested, (*prefix, str(key)))
        }
    if isinstance(value, list):
        return {
            path
            for index, nested in enumerate(value)
            for path in _numeric_paths(nested, (*prefix, str(index)))
        }
    return {prefix} if isinstance(value, int | float) and not isinstance(value, bool) else set()


def main() -> int:
    """Print the complete owner-input measurement; do not call solver or binder."""
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.grounding_calibration import (
        CalibrationFrame,
        DeclaredRefusalSuite,
        build_refusal_reference_scaffold,
        load_grounding_proof_world_input,
    )
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine

    binding, world = load_grounding_proof_world_input(_census.ROOT)
    frame = CalibrationFrame.model_validate_json((_census.ROOT / _census.FRAME).read_bytes())
    suite = DeclaredRefusalSuite.model_validate_json((_census.ROOT / _census.SUITE).read_bytes())
    reference = build_refusal_reference_scaffold(_census.ROOT, world)
    if reference.reference_hash != suite.reference_scaffold_hash:
        raise ValueError("original_scaffold_identity_changed")
    atoms = GroundingRelationEngine(reference).reference_atoms
    matched = {}
    for row in frame.inputs:
        candidates = [
            atom
            for atom in atoms
            if atom.signature.op == row.operator_family
            and set(atom.signature.X_do) == set(row.signature["X_do"])
        ]
        if len(candidates) != 1:
            raise ValueError(f"ambiguous_original_assignment_atom:{row.input_id}")
        matched[row.input_id] = candidates[0]
    suite_atoms = {case.atom_id: case.source_input_hash for case in suite.mismatches}
    owner_atoms = {
        atom.atom_id: gy_content_hash(atom.signature.model_dump(mode="json"))
        for atom in matched.values()
    }
    if suite_atoms != owner_atoms:
        raise ValueError("original_assignment_atom_identity_delta")
    numeric = set()
    domain_only = set()
    for operator, atom in matched.items():
        payload = atom.signature.model_dump(mode="json")
        paths = _numeric_paths(payload)
        numeric.update((operator, *path) for path in paths)
        domain_only.update(
            (operator, *path)
            for path in paths
            if len(path) == 3
            and path[0] in {"x_do", "params"}
            and path[1] == "domain"
            and path[2] in {"min_value", "max_value"}
        )
    if numeric != domain_only:
        raise ValueError("magnitude_intake_requires_classification_of_additional_numeric_payload")
    result = {
        "schema_version": "corr.refusal_expansion_owner_intake.v1",
        "synthetic": True,
        "status": "passed",
        "stage": "declaration_only_no_solver_no_binder",
        "proof_input_hash": binding.content_hash,
        "reference_hash": reference.reference_hash,
        "source_refs": [
            _census.blob_ref(_census.FRAME),
            _census.blob_ref(_census.SUITE),
            _census.blob_ref(_census.PROOF_INPUT),
            _census.blob_ref(_census.ROOT / "src/polisyos/runtime/quality/grounding_relation.py"),
        ],
        "original_assignment_count": len(matched),
        "original_assignment_atom_identity_hash": _census.digest(sorted(owner_atoms.items())),
        "independent_frozen_suite_identity_hash": _census.digest(sorted(suite_atoms.items())),
        "identity_delta": [],
        "all_original_numeric_leaf_count": len(numeric),
        "all_original_numeric_leaf_identity_hash": _census.digest(sorted(numeric)),
        "operator_domain_bound_leaf_count": len(domain_only),
        "operator_domain_bound_leaf_identity_hash": _census.digest(sorted(domain_only)),
        "original_effect_magnitude_status": "not_established",
        "original_effect_magnitude_reason": (
            "No original signature provides a scalar effect magnitude or an effect unit. "
            "Every numeric leaf is an operator-domain min/max bound. Those bounds cannot "
            "be relabelled as an effect estimate. Sign is categorical."
        ),
        "requested_magnitude_coordinates": len(matched) * len(range(-16, 16)),
        "magnitude_grid_executable_status": "ambiguous_original_effect_magnitude_absent",
        "no_runtime_refusal_outcomes_measured": True,
    }
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
