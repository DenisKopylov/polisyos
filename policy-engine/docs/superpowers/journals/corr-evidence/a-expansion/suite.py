"""Predeclared synthetic refusal research through unchanged CG1 and CG2 owners."""

from __future__ import annotations

import argparse
import copy
import importlib
import itertools
import json
import sys
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

_input = importlib.import_module("docs.superpowers.journals.corr-evidence.a-expansion.input_census")
HERE = Path(__file__).resolve().parent
DECLARATION = HERE / "2026-09-09-declaration.json"
REPORT = HERE / "2026-09-09-refusal-expansion.json"
LIMITATION = (
    "A high refusal rate on constructed mismatches is not evidence that accepted bindings "
    "are correct."
)
RULE = HERE / "2026-09-09-construction-rule.md"


def _load_inputs() -> dict[str, Any]:
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.grounding_calibration import (
        CalibrationFrame,
        DeclaredRefusalSuite,
        build_refusal_reference_scaffold,
        load_grounding_proof_world_input,
        source_clusters,
    )
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine

    binding, world = load_grounding_proof_world_input(_input.ROOT)
    frame = CalibrationFrame.model_validate_json((_input.ROOT / _input.FRAME).read_bytes())
    original = DeclaredRefusalSuite.model_validate_json((_input.ROOT / _input.SUITE).read_bytes())
    reference = build_refusal_reference_scaffold(_input.ROOT, world)
    if reference.reference_hash != original.reference_scaffold_hash:
        raise ValueError("original_reference_input_drift")
    atoms = {atom.atom_id: atom for atom in GroundingRelationEngine(reference).reference_atoms}
    matched = {}
    for case in original.mismatches:
        atom = atoms[case.atom_id]
        if gy_content_hash(atom.signature.model_dump(mode="json")) != case.source_input_hash:
            raise ValueError("original_atom_signature_input_drift")
        if atom.signature.op in matched:
            raise ValueError("ambiguous_repeated_original_operator")
        matched[atom.signature.op] = atom
    frame_pairs = {(row.operator_family, tuple(row.signature["X_do"])) for row in frame.inputs}
    atom_pairs = {(op, tuple(atom.signature.X_do)) for op, atom in matched.items()}
    if frame_pairs != atom_pairs:
        raise ValueError("complete_original_assignment_identity_delta")
    census = _input.input_census()
    slots = {slot.slot_id for slot in world.policy_slot_map}
    if _input.digest(sorted(slots)) != census["world_slot_identity_hash"]:
        raise ValueError("owner_vs_raw_world_slot_identity_delta")
    return {
        "binding": binding,
        "world": world,
        "frame": frame,
        "original": original,
        "reference": reference,
        "matched": matched,
        "slots": slots,
        "census": census,
        "source_clusters": source_clusters(frame.inputs),
    }


def _manifest(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Construct the full requested set without calling a solver or binder."""
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.grounding_relation import (
        MechanisticSignature,
        _population_for_slot,
        _scope_for_slot,
        _unit_for_target,
    )

    cases = []
    for operator, atom in sorted(inputs["matched"].items()):
        source = atom.signature.model_dump(mode="json")
        actual = atom.signature.X_do[0]
        if source["sign"] not in {"increase", "decrease"}:
            raise ValueError("original_definite_sign_disappeared")
        opposite = "increase" if source["sign"] == "decrease" else "decrease"
        base = {
            "source_operator": operator,
            "source_atom_id": atom.atom_id,
            "source_signature_hash": gy_content_hash(source),
            "actual_assignment": actual,
            "synthetic": True,
        }
        sign = copy.deepcopy(source)
        sign["sign"] = opposite
        cases.append(
            {
                **base,
                "case_id": f"opposite_sign:{operator}",
                "family": "opposite_sign",
                "eligibility": "executable_negative",
                "proposal": sign,
            }
        )
        for target in sorted(inputs["slots"] - {actual}):
            proposal = copy.deepcopy(source)
            proposal["X_do"] = [target]
            proposal["effect_path"] = [operator, target, *source["outcome"]]
            proposal["scope"] = _scope_for_slot(target)
            proposal["population"] = _population_for_slot(target)
            proposal["unit"] = _unit_for_target(inputs["reference"], target)
            for fields in proposal["modal_claims"].values():
                for key in ("target", "treatment_target"):
                    if key in fields:
                        if fields[key] != actual:
                            raise ValueError("original_modal_target_requires_new_classification")
                        fields[key] = target
            MechanisticSignature.model_validate(proposal)
            cases.append(
                {
                    **base,
                    "case_id": f"target_assignment:{operator}:{target}",
                    "family": "target_assignment",
                    "eligibility": "executable_negative",
                    "replacement_target": target,
                    "proposal": proposal,
                }
            )
    identities = {row["case_id"] for row in cases}
    if len(identities) != len(cases):
        raise ValueError("duplicate_case_identity")
    operators = set(inputs["matched"])
    actual_pairs = {(op, atom.signature.X_do[0]) for op, atom in inputs["matched"].items()}
    independent = {f"opposite_sign:{op}" for op in operators}
    independent.update(
        f"target_assignment:{op}:{slot}"
        for op, slot in set(itertools.product(operators, inputs["slots"])) - actual_pairs
    )
    if identities != independent:
        raise ValueError("complete_manifest_identity_delta")
    executable = [case for case in cases if case["proposal"] is not None]
    hashes = {gy_content_hash(case["proposal"]) for case in executable}
    if len(hashes) != len(executable):
        raise ValueError("duplicate_normalized_proposal_not_additional_evidence")
    return sorted(cases, key=lambda row: row["case_id"])


def _case_projection(case: dict[str, Any]) -> dict[str, Any]:
    from polisyos.pdc import gy_content_hash

    return {key: value for key, value in case.items() if key != "proposal"} | {
        "proposal_hash": gy_content_hash(case["proposal"]) if case["proposal"] else None
    }


def _declaration(inputs: dict[str, Any], declared_at: str) -> dict[str, Any]:
    cases = _manifest(inputs)
    date = datetime.fromisoformat(declared_at)
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError("declaration_requires_aware_time")
    families = sorted({case["family"] for case in cases})
    owners = [
        Path("src/polisyos/runtime/quality") / name
        for name in ("grounding_calibration.py", "grounding_relation.py", "grounding_bind.py")
    ]
    body = {
        "schema_version": "corr.refusal_expansion_declaration.v1",
        "synthetic": True,
        "declared_at": declared_at,
        "construction_rule": _input.blob_ref(RULE.relative_to(_input.ROOT)),
        "diagnostic": _input.blob_ref(Path(__file__).relative_to(_input.ROOT)),
        "existing_owner_sources": [_input.blob_ref(path) for path in owners],
        "input_sources": inputs["census"]["tracked_sources"],
        "proof_input_hash": inputs["binding"].content_hash,
        "source_cluster_count": len(inputs["source_clusters"]),
        "source_cluster_identity_hash": _input.digest(inputs["source_clusters"]),
        "reference_hash": inputs["reference"].reference_hash,
        "input_census": inputs["census"],
        "requested_manifest_count": len(cases),
        "executable_negative_count": sum(
            case["eligibility"] == "executable_negative" for case in cases
        ),
        "ambiguous_count": sum(case["eligibility"] == "ambiguous" for case in cases),
        "manifest_identity_hash": _input.digest([_case_projection(case) for case in cases]),
        "independent_identity_hash": _input.digest(sorted(case["case_id"] for case in cases)),
        "families": [
            {
                "family": family,
                "requested_count": sum(case["family"] == family for case in cases),
                "limitation": LIMITATION,
            }
            for family in families
        ],
        "provenance": {
            "denominator": "independently_reconciled",
            "case_construction": "recomputed",
            "accepted_binding_correctness": "not_established",
            "independent_adjudication": "not_established",
        },
        "correctness_bound": None,
        "limitation": LIMITATION,
    }
    return {**body, "content_hash": _input.digest(body)}


def _load_declaration(inputs: dict[str, Any]) -> dict[str, Any]:
    saved = _input.read_json(DECLARATION)
    expected = _declaration(inputs, saved["declared_at"])
    if saved != expected:
        raise ValueError("refusal_expansion_complete_declaration_drift")
    return saved


def _run(inputs: dict[str, Any], declaration: dict[str, Any], executed_at: str) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_bind import (
        GroundingBindGate,
        resolve_grounding_decision_promotability,
    )
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine

    if datetime.fromisoformat(executed_at) <= datetime.fromisoformat(declaration["declared_at"]):
        raise ValueError("declaration_must_precede_execution")
    reference = inputs["reference"]
    engine = GroundingRelationEngine(reference)
    gate = GroundingBindGate(reference)
    controls = []
    issues = []
    for operator, atom in sorted(inputs["matched"].items()):
        relation = engine.certificate_for(
            {"signature": atom.signature.model_dump(mode="json"), "synthetic": True},
            proposal_id=f"expansion-control:{operator}",
        )
        decision = gate.certificate_for(relation)
        resolution = resolve_grounding_decision_promotability(decision, reference)
        control = {
            "source_operator": operator,
            "synthetic": True,
            "relation": relation.selected_relation,
            "solver_status": relation.solver_status,
            "decision": decision.decision,
            "decision_reason": decision.decisive_reason,
            "governed_authority": resolution.promotable,
            "relation_certificate_hash": relation.content_hash,
            "decision_certificate_hash": decision.content_hash,
        }
        controls.append(control)
        if (
            relation.selected_relation not in {"exact", "certified-specialization"}
            or resolution.promotable
        ):
            issues.append(f"matched_control_or_synthetic_boundary_failed:{operator}")
    outcomes = []
    for case in _manifest(inputs):
        outcome = _case_projection(case)
        if case["eligibility"] == "ambiguous":
            outcomes.append({**outcome, "runtime_status": "not_executed_ambiguous"})
            continue
        relation = engine.certificate_for(
            {"signature": case["proposal"], "synthetic": True}, proposal_id=case["case_id"]
        )
        decision = gate.certificate_for(relation)
        resolution = resolve_grounding_decision_promotability(decision, reference)
        pair_rows = [
            row
            for row in relation.relation_set["candidate_results"]
            if row["atom_id"] == case["source_atom_id"]
        ]
        if case["family"] == "opposite_sign":
            detected = (
                bool(pair_rows)
                and relation.solver_status == "SAT"
                and all(
                    any(
                        w["axis"] == "sign" and w["relation"] == "contradiction"
                        for w in row["axis_witnesses"]
                    )
                    for row in pair_rows
                )
            )
            expected_reason = "false_analog_hard_abstain"
        else:
            op, target = case["source_operator"], case["replacement_target"]
            core = set(relation.unsat_core_if_any)
            hard = {f"knob_maps_to({op}, {target})", f"allowed_target_type({op}, {target})"}
            source_assignment = f"L6.knob:{op}.target == {case['actual_assignment']}"
            declared_targets = {f"signature.target == {target}"}
            declared_targets.update(
                f"{modality}.target == {target}"
                for modality, fields in case["proposal"]["modal_claims"].items()
                if fields.get("target") == target or fields.get("treatment_target") == target
            )
            detected = relation.solver_status == "UNSAT" and (
                bool(core & hard) or (source_assignment in core and bool(core & declared_targets))
            )
            expected_reason = "relation_not_bind_eligible"
        correct_refusal = (
            decision.decision != "bind" and decision.decisive_reason == expected_reason
        )
        outcomes.append(
            {
                **outcome,
                "runtime_status": "executed",
                "mismatch_detected": detected,
                "refused": decision.decision != "bind",
                "expected_reason": expected_reason,
                "decision_reason": decision.decisive_reason,
                "solver_status": relation.solver_status,
                "selected_relation": relation.selected_relation,
                "source_pair_witnesses": pair_rows,
                "unsat_core": list(relation.unsat_core_if_any),
                "governed_authority": resolution.promotable,
                "relation_certificate_hash": relation.content_hash,
                "decision_certificate_hash": decision.content_hash,
            }
        )
        if not detected or not correct_refusal or resolution.promotable:
            issues.append(f"intended_mismatch_refusal_not_established:{case['case_id']}")
    families = []
    for family in declaration["families"]:
        rows = [row for row in outcomes if row["family"] == family["family"]]
        executed = [row for row in rows if row["runtime_status"] == "executed"]
        refused = sum(row["refused"] for row in executed)
        families.append(
            {
                "family": family["family"],
                "requested_count": len(rows),
                "executed_negative_count": len(executed),
                "ambiguous_count": len(rows) - len(executed),
                "refused_count": refused,
                "intended_mismatch_detected_count": sum(
                    row["mismatch_detected"] for row in executed
                ),
                "statement": (
                    f"Refused {refused} of {len(executed)} executed constructed mismatches. "
                    f"{LIMITATION}"
                ),
            }
        )
    return {
        "schema_version": "corr.refusal_expansion_result.v1",
        "synthetic": True,
        "executed_at": executed_at,
        "declaration_hash": declaration["content_hash"],
        "reference_hash": reference.reference_hash,
        "proof_input_hash": inputs["binding"].content_hash,
        "requested_manifest_count": declaration["requested_manifest_count"],
        "executable_negative_count": declaration["executable_negative_count"],
        "ambiguous_count": declaration["ambiguous_count"],
        "families": families,
        "matched_controls_outside_negative_denominator": controls,
        "outcomes": outcomes,
        "issues": issues,
        "correctness_bound": None,
        "limitation": LIMITATION,
        "scope": "one held support population; structural sign and assignment sensitivity only",
        "chronology": "run-emitted time corroborated by the separate retained execution capture",
    }


def _execution_receipt(path: Path) -> dict[str, Any]:
    """Read the separately retained child output, never a caller-authored time."""
    capture = _input.read_json(path)
    expected = ["-m", "docs.superpowers.journals.corr-evidence.a-expansion.suite", "--write"]
    if (
        capture["timed_out"] is not False
        or capture["returncode"] not in {0, 1}
        or capture["argv"][-3:] != expected
    ):
        raise ValueError("refusal_expansion_execution_capture_nonreceipt")
    report = json.loads(capture["stdout"])
    if not isinstance(report, dict) or report["synthetic"] is not True:
        raise ValueError("refusal_expansion_execution_capture_invalid")
    return report


def _removal_context(stack: ExitStack, probe: str | None) -> None:
    from polisyos.runtime.quality import grounding_bind, grounding_relation

    if probe == "sign":
        original = grounding_relation._axis_relation

        def removed(axis: str, proposal: object, atom: object, **kwargs: bool) -> tuple[str, str]:
            if axis == "sign":
                return "equivalent", "sign declaration retained; substantive comparison removed"
            return original(axis, proposal, atom, **kwargs)

        stack.enter_context(patch.object(grounding_relation, "_axis_relation", removed))
    elif probe == "assignment":
        stack.enter_context(patch.object(grounding_relation, "_knob_target", lambda *_args: ""))
        stack.enter_context(patch.object(grounding_relation, "_knob_maps_to", lambda *_args: True))
    elif probe == "binder":
        stack.enter_context(
            patch.object(grounding_bind, "_has_selected_critical_veto", lambda _cert: False)
        )


def main() -> int:
    """Declare or execute only the new diagnostic artifacts in this directory."""
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--declare", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--probe", choices=("sign", "assignment", "binder"))
    parser.add_argument("--execution-receipt", type=Path)
    args = parser.parse_args()
    if args.check != (args.execution_receipt is not None):
        raise ValueError("independent_check_requires_original_execution_capture")
    inputs = _load_inputs()
    now = datetime.now(UTC).isoformat()
    if args.declare:
        if DECLARATION.exists():
            raise ValueError("preexisting_declaration_must_not_be_revised")
        declaration = _declaration(inputs, now)
        DECLARATION.write_text(json.dumps(declaration, indent=2, sort_keys=True) + "\n")
        sys.stdout.write(json.dumps(declaration, indent=2, sort_keys=True) + "\n")
        return 0
    declaration = _load_declaration(inputs)
    saved = _input.read_json(REPORT) if args.check else None
    emitted = _execution_receipt(args.execution_receipt) if args.check else None
    with ExitStack() as stack:
        _removal_context(stack, args.probe)
        result = _run(inputs, declaration, emitted["executed_at"] if emitted else now)
    if result["synthetic"] is not True:
        result["issues"].append("own_synthetic_marker_missing")
    if saved is not None and saved != result:
        result["issues"].append("refusal_expansion_saved_result_drift")
    if emitted is not None and saved != emitted:
        result["issues"].append("refusal_expansion_original_execution_capture_mismatch")
    if args.write:
        if REPORT.exists():
            raise ValueError("preexisting_result_must_not_be_revised")
        REPORT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 1 if result["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
