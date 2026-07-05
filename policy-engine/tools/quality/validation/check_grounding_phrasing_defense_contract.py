#!/usr/bin/env python3
"""Validate the CGF GY-CG4 phrasing-invariance defense contract."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/grounding_phrasing_defense_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.grounding_phrasing_defense_contract.v1"
EXPECTED_BASE_CLASSES = {
    "admit",
    "acquire",
    "reject",
    "non_new",
    "novel",
    "bind_eligible_frozen",
}
EXPECTED_FAMILIES = {
    "synonym_alias_substitution",
    "legalistic_camouflage",
    "high_value_outcome_injection",
    "confidence_bait",
    "format_whitespace_ordering",
    "registered_lever_mimicry",
    "mechanism_changing_control",
}
EXPECTED_MUTATIONS = {
    "surface_to_decision_dependence_restored",
    "denotation_classifier_removed",
    "proxy_gap_capture_removed",
    "sensitivity_arm_removed",
    "self_vacuity_surface_channel_disconnected",
}
AUDIT_MIMIC_SURFACES = (
    "tax relief rate adjustment",
    "tax_releif_rate",
    "fiscal relief ratio",
)


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _configure_validation_jax_platform() -> None:
    """Keep validator WMR builds reproducible without runtime env mutation."""

    os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
    os.environ.setdefault("JAX_PLATFORMS", "cpu")


def build_live_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute the CG4 contract from live CG0/CG1/CG2/CG3 owner paths."""

    _configure_validation_jax_platform()
    from polisyos.runtime.quality.credal_reference import build_credal_reference
    from polisyos.runtime.quality.grounding_phrasing_defense import (
        _CAUSAL_EVIDENCE_THRESHOLD,
        _SURFACE_AFFINITY_THRESHOLD,
        GROUNDING_PHRASING_DEFENSE_SCHEMA_VERSION,
        GroundingPhrasingDefenseEngine,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    reference = build_credal_reference(repo_root)
    matrix_reference = _with_mechanism_edge(
        reference,
        source="cells.distress_score",
        outcome="cells.output",
        edge_id="cg4_distress_output_direct",
    )
    engine = GroundingPhrasingDefenseEngine(matrix_reference)
    base_cases = _base_cases(repo_root)
    transforms_by_base = engine.generate_transforms(base_cases)
    representative_transforms = _representative_transform_slice(transforms_by_base)
    certificate = engine._evaluate_attack_matrix_from_transforms(  # noqa: SLF001
        base_cases,
        representative_transforms,
        matrix_scope="representative_full_cg1_slice",
        scope_note=(
            "Full generated matrix was attempted during GY-CG4 NO-GO repair but cold "
            "live-reference/full-FTS replay did not return within a practical interval; "
            "the committed proof matrix is the allowed full-CG1 representative slice "
            "with every transform family x every base-case class covered at least once."
        ),
    )
    deterministic_transform = next(
        transform
        for transform in transforms_by_base.get(base_cases[0].case_id, ())
        if transform.family != "mechanism_changing_control"
    )
    deterministic_a = engine._evaluate_pair(  # noqa: SLF001
        base_cases[0],
        deterministic_transform,
        bounded_cg1=False,
    )
    deterministic_b = engine._evaluate_pair(  # noqa: SLF001
        base_cases[0],
        deterministic_transform,
        bounded_cg1=False,
    )

    capture_run = engine._run_pipeline(  # noqa: SLF001
        _tax_unregistered_mimic_probe("tax relief rate adjustment"),
        proposal_id="cg4.proxy_gap.capture",
        bounded_cg1=False,
    )
    capture_risk = engine.detect_proxy_gap(capture_run)
    capture_handoff = engine.quarantine_handoff(capture_risk) if capture_risk else None
    mirror_run = engine._run_pipeline(  # noqa: SLF001
        _tax_unregistered_mimic_probe("tax_credit_rate"),
        proposal_id="cg4.proxy_gap.mirror",
        bounded_cg1=False,
    )
    mirror_risk = engine.detect_proxy_gap(mirror_run)
    mirror_evidence_reference = _with_mechanism_edge(
        reference,
        source="global.tax_rate",
        outcome="government.balance",
        edge_id="cg4_tax_balance_direct",
    )
    mirror_evidence_engine = GroundingPhrasingDefenseEngine(mirror_evidence_reference)
    mirror_evidence_run = mirror_evidence_engine._run_pipeline(  # noqa: SLF001
        _tax_unregistered_mimic_probe("tax relief rate adjustment"),
        proposal_id="cg4.proxy_gap.mirror_real_evidence",
        bounded_cg1=False,
    )
    mirror_evidence_risk = mirror_evidence_engine.detect_proxy_gap(mirror_evidence_run)
    audit_mimic_probes: dict[str, dict[str, Any]] = {}
    for surface in AUDIT_MIMIC_SURFACES:
        audit_run = engine._run_pipeline(  # noqa: SLF001
            _tax_unregistered_mimic_probe(surface),
            proposal_id=f"cg4.proxy_gap.audit_mimic.{_slug(surface)}",
            bounded_cg1=False,
        )
        audit_risk = engine.detect_proxy_gap(audit_run)
        audit_handoff = engine.quarantine_handoff(audit_risk) if audit_risk else None
        audit_mimic_probes[surface] = _proxy_gap_probe_record(
            audit_run,
            audit_risk,
            handoff=audit_handoff,
            surface_affinity_threshold=_SURFACE_AFFINITY_THRESHOLD,
            causal_evidence_threshold=_CAUSAL_EVIDENCE_THRESHOLD,
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.grounding_phrasing_defense_rt5",
        "runtime_schema_version": GROUNDING_PHRASING_DEFENSE_SCHEMA_VERSION,
        "owner": "polisyos.runtime.quality.grounding_phrasing_defense",
        "source_modules": [
            "src/polisyos/runtime/quality/grounding_phrasing_defense.py",
            "src/polisyos/runtime/quality/grounding_relation.py",
            "src/polisyos/runtime/quality/grounding_bind.py",
            "src/polisyos/runtime/quality/grounding_admission.py",
            "src/polisyos/runtime/quality/credal_reference.py",
            "src/polisyos/runtime/quality/generation_cycle.py",
            "tools/quality/validation/check_grounding_phrasing_defense_contract.py",
        ],
        "reuse_existing_owners": [
            "CG0 CredalReference built from real L2/L3/L6/WMR owners",
            "CG1 GroundingRelationEngine for relation and denotation resolution",
            "CG2 GroundingBindGate for bind/abstain/novel decisions",
            "CG3 GroundingAdmissionEngine for admit/acquire/reject/non_new decisions",
            "GY-N6 generation_cycle quarantine front is named; direct CG4 intake is an honest gap",
        ],
        "pattern_pass": {
            "relevant_patterns": ["P05", "P10", "P27", "P28", "P29", "P31", "P32", "P33"],
            "target_correct_pattern": (
                "real-pipeline auditor with denotation-resolved phrasing classification, "
                "zero caller authority knobs, behavioral mutations, and honest quarantine handoff"
            ),
            "missing_capability_labels": ["bridge_missing"],
            "acceptance_signal": "WrongLift <= 0, sensitivity live, proxy-gap captured",
        },
        "reference": {
            "reference_epoch": matrix_reference.reference_epoch,
            "reference_hash": matrix_reference.reference_hash,
            "base_reference_hash": reference.reference_hash,
            "edge_count": len(matrix_reference.essential_edges),
            "component_versions": dict(sorted(matrix_reference.component_versions.items())),
            "admit_probe_edge": "L2_CAUSAL_CLAIM:cg4_distress_output_direct",
            "admit_probe_edge_scope": (
                "validator-owned direct mechanism witness using the same "
                "CredalReferenceEdge owner-lift format consumed by CG3"
            ),
        },
        "certificate": certificate.model_dump(mode="json"),
        "matrix_counts": certificate.matrix_summary.model_dump(mode="json"),
        "proxy_gap_capture_pair": {
            "capture": _proxy_gap_probe_record(
                capture_run,
                capture_risk,
                handoff=capture_handoff,
                surface_affinity_threshold=_SURFACE_AFFINITY_THRESHOLD,
                causal_evidence_threshold=_CAUSAL_EVIDENCE_THRESHOLD,
            ),
            "mirror": _proxy_gap_probe_record(
                mirror_run,
                mirror_risk,
                surface_affinity_threshold=_SURFACE_AFFINITY_THRESHOLD,
                causal_evidence_threshold=_CAUSAL_EVIDENCE_THRESHOLD,
            ),
            "mirror_real_evidence": _proxy_gap_probe_record(
                mirror_evidence_run,
                mirror_evidence_risk,
                surface_affinity_threshold=_SURFACE_AFFINITY_THRESHOLD,
                causal_evidence_threshold=_CAUSAL_EVIDENCE_THRESHOLD,
            ),
        },
        "proxy_gap_audit_mimic_probes": audit_mimic_probes,
        "production_api_boundary_probes": _production_api_boundary_probes(matrix_reference),
        "behavioral_mutations": _mutation_reports(matrix_reference, base_cases),
        "determinism": {
            "base_case_id": base_cases[0].case_id,
            "transform_id": deterministic_transform.transform_id,
            "first_evidence_hash": deterministic_a.transformed_run.evidence_signature.content_hash,
            "second_evidence_hash": deterministic_b.transformed_run.evidence_signature.content_hash,
            "same_content_hash": deterministic_a.model_dump(mode="json")
            == deterministic_b.model_dump(mode="json"),
        },
        "capability_reality": {
            "typed_contract_artifact": (
                "PhrasingDefenseCertificate + GroundingProxyGapRisk + "
                "QuarantineHandoffRecord"
            ),
            "producer": "GroundingPhrasingDefenseEngine.evaluate_attack_matrix",
            "persisted_artifact_event": OUTPUT_PATH,
            "orchestration_bridge": (
                "CG4 runs CG1/CG2/CG3 and emits an N6 quarantine handoff artifact; "
                "direct N6 intake remains bridge_missing"
            ),
            "consumer": "validator/audit surface; future GY-N6 direct intake explicitly not wired",
            "verification": "this recomputing validator, unit probes, mutation probes, drift check",
            "surface": "generated Policy Design Case CG4 contract artifact",
            "semantic_test": "WrongLift matrix, mechanism-changing sensitivity, proxy-gap capture pair",
            "capability_label": "bridge_missing",
        },
    }
    return payload


def validate_payload(
    payload: dict[str, Any],
    *,
    require_mutations: bool = True,
) -> dict[str, Any]:
    """Validate one recomputed or committed CG4 payload."""

    issues = _core_issues(payload, require_mutations=require_mutations)
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
    }


def write_payload(payload: dict[str, Any], path: Path) -> None:
    """Write a stable JSON payload."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _representative_transform_slice(
    transforms_by_base: dict[str, tuple[Any, ...]],
) -> dict[str, tuple[Any, ...]]:
    """Keep one deterministic transform per family for each base case."""

    sliced: dict[str, tuple[Any, ...]] = {}
    for case_id, transforms in sorted(transforms_by_base.items()):
        by_family: dict[str, Any] = {}
        for transform in transforms:
            by_family.setdefault(str(transform.family), transform)
        sliced[case_id] = tuple(
            by_family[family]
            for family in sorted(by_family)
        )
    return sliced


def _corrupt_field_drift_check(payload: dict[str, Any]) -> dict[str, Any]:
    corrupted = json.loads(json.dumps(payload, sort_keys=True))
    corrupted["certificate"]["matrix_summary"]["total_lifted"] = 1
    corrupted["certificate"]["matrix_summary"]["consumed_intermediate_diff_counts"][
        "retrieval"
    ] = 0
    corrupted["certificate"]["matrix_summary"]["self_vacuous"] = True
    if corrupted["proxy_gap_capture_pair"]["capture"]["risk"]:
        corrupted["proxy_gap_capture_pair"]["capture"]["risk"]["disposition"] = "ignored"
    corrupted["certificate"]["content_hash"] = "sha256:" + "0" * 64
    if corrupted.get("behavioral_mutations"):
        corrupted["behavioral_mutations"][0]["status"] = "green"
    report = validate_payload(corrupted)
    return {
        "status": "pass" if report["status"] == "fail" else "fail",
        "issues": []
        if report["status"] == "fail"
        else [{"code": "grounding_phrasing_defense_corrupt_field_not_detected"}],
        "corrupt_report_status": report["status"],
        "corrupt_issue_codes": [issue["code"] for issue in report["issues"]],
    }


def _core_issues(
    payload: dict[str, Any],
    *,
    require_mutations: bool,
) -> list[dict[str, Any]]:
    from polisyos.runtime.quality.grounding_phrasing_defense import (
        PhrasingDefenseCertificate,
    )

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "grounding_phrasing_defense_schema_mismatch"})
    try:
        certificate = PhrasingDefenseCertificate.model_validate(payload.get("certificate"))
    except Exception as exc:  # noqa: BLE001 - validator reports model error as data.
        issues.append(
            {
                "code": "grounding_phrasing_defense_certificate_invalid",
                "error": str(exc).split("\n", 1)[0],
            }
        )
        certificate = None
    if certificate is not None:
        summary = certificate.matrix_summary
        if summary.cg1_proof_mode != "full":
            issues.append({"code": "grounding_phrasing_defense_matrix_not_full_cg1"})
        if summary.matrix_scope == "representative_full_cg1_slice" and not summary.scope_note:
            issues.append({"code": "grounding_phrasing_defense_representative_scope_not_recorded"})
        if summary.self_vacuous:
            issues.append({"code": "grounding_phrasing_defense_matrix_self_vacuous"})
        if summary.consumed_intermediate_diff_counts.get("raw_text", 0) == 0:
            issues.append({"code": "grounding_phrasing_defense_raw_surface_not_varied"})
        if summary.consumed_intermediate_diff_counts.get("retrieval", 0) == 0:
            issues.append({"code": "grounding_phrasing_defense_retrieval_channel_not_exercised"})
        if summary.total_lifted != 0:
            issues.append({"code": "grounding_phrasing_defense_wrong_lift_nonzero"})
        if summary.base_case_count < len(EXPECTED_BASE_CLASSES):
            issues.append({"code": "grounding_phrasing_defense_base_denominator_too_small"})
        for family in EXPECTED_FAMILIES:
            rows = summary.family_case_denominator.get(family, {})
            missing = sorted(EXPECTED_BASE_CLASSES.difference(rows))
            if missing:
                issues.append(
                    {
                        "code": "grounding_phrasing_defense_family_case_denominator_missing",
                        "family": family,
                        "missing": missing,
                    }
                )
        if summary.mechanism_control_count == 0:
            issues.append({"code": "grounding_phrasing_defense_sensitivity_arm_missing"})
        for comparison in certificate.comparisons:
            if comparison.classification.classified_phrasing_only:
                if comparison.lifted_gate_ids:
                    issues.append(
                        {
                            "code": "grounding_phrasing_defense_phrasing_pair_lifted",
                            "transform_id": comparison.transform_id,
                            "lifted_gate_ids": list(comparison.lifted_gate_ids),
                        }
                    )
                if not comparison.evidence_signature_equal:
                    issues.append(
                        {
                            "code": "grounding_phrasing_defense_phrasing_evidence_changed",
                            "transform_id": comparison.transform_id,
                        }
                    )
            elif comparison.family == "mechanism_changing_control":
                if comparison.evidence_signature_equal:
                    issues.append(
                        {
                            "code": "grounding_phrasing_defense_dead_sensor",
                            "transform_id": comparison.transform_id,
                        }
                    )
            elif (
                comparison.family == "registered_lever_mimicry"
                and comparison.lifted_gate_ids
                and not _comparison_is_quarantined_nonbinding_mimicry(comparison)
            ):
                issues.append(
                    {
                        "code": "grounding_phrasing_defense_mimicry_lifted",
                        "transform_id": comparison.transform_id,
                        "lifted_gate_ids": list(comparison.lifted_gate_ids),
                    }
                )
        full = certificate.full_cg1_comparison
        if not full.checked or not full.bounded_not_more_permissive:
            issues.append({"code": "grounding_phrasing_defense_full_cg1_slice_failed"})
        if len(certificate.bounded_diagnostic_comparisons) < len(EXPECTED_FAMILIES) - 1:
            issues.append({"code": "grounding_phrasing_defense_bounded_diagnostic_too_narrow"})
        for diagnostic in certificate.bounded_diagnostic_comparisons:
            if not diagnostic.bounded_not_more_permissive:
                issues.append(
                    {
                        "code": "grounding_phrasing_defense_bounded_more_permissive",
                        "transform_id": diagnostic.transform_id,
                    }
                )
        if not any(
            risk.proposal_id and ".mimic." in risk.proposal_id
            for risk in certificate.proxy_gap_risks
        ):
            issues.append({"code": "grounding_phrasing_defense_mimicry_quarantine_missing"})
    capture_pair = payload.get("proxy_gap_capture_pair", {})
    capture = _probe(capture_pair, "capture")
    mirror = _probe(capture_pair, "mirror")
    mirror_real_evidence = _probe(capture_pair, "mirror_real_evidence")
    if capture.get("quarantined") is not True:
        issues.append({"code": "grounding_phrasing_defense_proxy_gap_not_quarantined"})
    if capture.get("cg3_denotation_match_kind") != "signature_only":
        issues.append({"code": "grounding_phrasing_defense_capture_not_signature_only"})
    if capture.get("cg2_decision") == "bind" or capture.get("cg3_decision") == "admit_new_lever":
        issues.append({"code": "grounding_phrasing_defense_quarantined_case_admitted_or_bound"})
    if not _probe(capture, "handoff"):
        issues.append({"code": "grounding_phrasing_defense_quarantine_handoff_missing"})
    if mirror.get("quarantined") is not False:
        issues.append({"code": "grounding_phrasing_defense_proxy_gap_mirror_quarantined"})
    if mirror.get("cg3_denotation_match_kind") != "resolved_proof":
        issues.append({"code": "grounding_phrasing_defense_mirror_not_resolved_proof"})
    if mirror_real_evidence.get("quarantined") is not False:
        issues.append({"code": "grounding_phrasing_defense_real_evidence_mirror_quarantined"})
    audit_mimics = payload.get("proxy_gap_audit_mimic_probes", {})
    if not isinstance(audit_mimics, dict):
        audit_mimics = {}
    for surface in AUDIT_MIMIC_SURFACES:
        row = audit_mimics.get(surface)
        if not isinstance(row, dict):
            issues.append(
                {
                    "code": "grounding_phrasing_defense_audit_mimic_probe_missing",
                    "surface": surface,
                }
            )
            continue
        if "surface_affinity_threshold" not in row or "above_surface_affinity_threshold" not in row:
            issues.append(
                {
                    "code": "grounding_phrasing_defense_audit_mimic_threshold_status_missing",
                    "surface": surface,
                }
            )
        if row.get("cg2_decision") == "bind" or row.get("cg3_decision") == "admit_new_lever":
            issues.append(
                {
                    "code": "grounding_phrasing_defense_audit_mimic_admitted_or_bound",
                    "surface": surface,
                }
            )
        if surface == "tax relief rate adjustment" and row.get("quarantined") is not True:
            issues.append(
                {
                    "code": "grounding_phrasing_defense_audit_mimic_capture_not_quarantined",
                    "surface": surface,
                }
            )
        if (
            row.get("above_surface_affinity_threshold") is True
            and row.get("below_causal_evidence_threshold") is True
            and row.get("cg3_denotation_match_kind") == "signature_only"
            and row.get("quarantined") is not True
        ):
            issues.append(
                {
                    "code": "grounding_phrasing_defense_audit_mimic_high_surface_not_quarantined",
                    "surface": surface,
                }
            )
    boundary = payload.get("production_api_boundary_probes", {})
    for probe_id, row in sorted(boundary.items()):
        if row.get("accepted") is not False:
            issues.append(
                {
                    "code": "grounding_phrasing_defense_public_api_accepted_authority_knob",
                    "probe": probe_id,
                }
            )
    if payload.get("determinism", {}).get("same_content_hash") is not True:
        issues.append({"code": "grounding_phrasing_defense_not_deterministic"})
    if require_mutations:
        mutations = {
            str(item.get("mutation_id")): str(item.get("status"))
            for item in payload.get("behavioral_mutations", [])
            if isinstance(item, dict)
        }
        missing = sorted(EXPECTED_MUTATIONS.difference(mutations))
        if missing:
            issues.append(
                {
                    "code": "grounding_phrasing_defense_required_mutation_missing",
                    "missing_mutations": missing,
                }
            )
        not_red = sorted(
            mutation_id
            for mutation_id in EXPECTED_MUTATIONS.intersection(mutations)
            if mutations[mutation_id] != "red"
        )
        if not_red:
            issues.append(
                {
                    "code": "grounding_phrasing_defense_required_mutation_not_red",
                    "mutation_ids": not_red,
                }
            )
    return issues


def _comparison_is_quarantined_nonbinding_mimicry(comparison: Any) -> bool:
    transformed = comparison.transformed_run
    signature = transformed.evidence_signature
    return (
        comparison.family == "registered_lever_mimicry"
        and signature.cg3_denotation_match_kind == "signature_only"
        and transformed.surface_view.max_surface_affinity >= 0.62
        and transformed.decisions.cg2_decision != "bind"
        and transformed.decisions.cg3_decision != "admit_new_lever"
        and (
            signature.cg3_mechanism_status != "closed"
            or signature.cg3_data_trust_status != "closed"
            or bool(signature.cg3_open_obligations)
        )
    )


def _mutation_reports(reference: Any, base_cases: tuple[Any, ...]) -> list[dict[str, Any]]:
    from polisyos.runtime.quality.grounding_phrasing_defense import (
        GroundingPhrasingDefenseEngine,
        PhrasingAttackTransform,
        PhrasingDefenseBaseCase,
    )

    reports: list[dict[str, Any]] = []
    surface_base = PhrasingDefenseBaseCase(
        case_id="cg4.mutation.surface_base",
        case_class="acquire",
        proposal=_surface_mutation_unrelated_probe(),
    )
    surface_transform = PhrasingAttackTransform(
        transform_id="cg4.mutation.surface_high_affinity",
        family="confidence_bait",
        declared_phrasing_only=True,
        proposal={
            **surface_base.proposal,
            "raw_text": (
                "tax relief rate tax credit rate tax relief statute lowers the "
                "global tax-rate setting."
            ),
        },
        description="Real surface-channel mutation: same signature, higher FTS affinity.",
    )
    surface_pair = GroundingPhrasingDefenseEngine.for_contract_testing(
        reference,
        allow_surface_lift=True,
    )._evaluate_pair(surface_base, surface_transform, bounded_cg1=False)  # noqa: SLF001
    reports.append(
        _mutation_row(
            "surface_to_decision_dependence_restored",
            bool(surface_pair.lifted_gate_ids),
            {
                "lifted_gate_ids": list(surface_pair.lifted_gate_ids),
                "authority_scope": "contract_testing",
                "production_authoritative": False,
            },
        )
    )

    base = base_cases[0]
    mechanism_transform = next(
        transform
        for transform in GroundingPhrasingDefenseEngine(reference)
        .generate_transforms((base,))
        .get(base.case_id, ())
        if transform.family == "mechanism_changing_control"
        and transform.declared_phrasing_only
    )
    classifier_pair = GroundingPhrasingDefenseEngine.for_contract_testing(
        reference,
        trust_declared_phrasing_only=True,
    )._evaluate_pair(base, mechanism_transform, bounded_cg1=False)  # noqa: SLF001
    mislabeled = (
        classifier_pair.classification.classified_phrasing_only
        and not classifier_pair.classification.denotation_equal
    )
    reports.append(
        _mutation_row(
            "denotation_classifier_removed",
            mislabeled,
            {"mislabeled_mechanism_control": mechanism_transform.transform_id},
        )
    )

    proxy_engine = GroundingPhrasingDefenseEngine.for_contract_testing(
        reference,
        disable_proxy_gap_capture=True,
    )
    capture = proxy_engine._run_pipeline(  # noqa: SLF001
        _tax_unregistered_mimic_probe("tax relief rate adjustment"),
        proposal_id="cg4.proxy_gap.capture.mutation",
        bounded_cg1=False,
    )
    reports.append(
        _mutation_row(
            "proxy_gap_capture_removed",
            proxy_engine.detect_proxy_gap(capture) is None,
            {
                "capture_cg2_decision": capture.decisions.cg2_decision,
                "capture_cg3_decision": capture.decisions.cg3_decision,
            },
        )
    )

    sensitivity_engine = GroundingPhrasingDefenseEngine.for_contract_testing(
        reference,
        disable_sensitivity_arm=True,
    )
    mechanism_count = sum(
        1
        for transforms in sensitivity_engine.generate_transforms(base_cases).values()
        for transform in transforms
        if transform.family == "mechanism_changing_control"
    )
    reports.append(
        _mutation_row(
            "sensitivity_arm_removed",
            mechanism_count == 0,
            {
                "mechanism_control_count": mechanism_count,
            },
        )
    )

    bounded_engine = GroundingPhrasingDefenseEngine.for_contract_testing(
        reference,
        force_bounded_matrix=True,
    )
    bounded_transforms = _representative_transform_slice(
        bounded_engine.generate_transforms(base_cases)
    )
    bounded_certificate = bounded_engine._evaluate_attack_matrix_from_transforms(  # noqa: SLF001
        base_cases,
        bounded_transforms,
        matrix_scope="representative_full_cg1_slice",
        scope_note="Self-vacuity mutation replays the committed representative matrix with FTS stubbed.",
    )
    reports.append(
        _mutation_row(
            "self_vacuity_surface_channel_disconnected",
            bounded_certificate.matrix_summary.self_vacuous,
            {
                "self_vacuous": bounded_certificate.matrix_summary.self_vacuous,
                "consumed_intermediate_diff_counts": (
                    bounded_certificate.matrix_summary.consumed_intermediate_diff_counts
                ),
            },
        )
    )
    return reports


def _mutation_row(mutation_id: str, failed_property_detected: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "mutation_id": mutation_id,
        "status": "red" if failed_property_detected else "green",
        "evidence": evidence,
    }


def _production_api_boundary_probes(reference: Any) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_phrasing_defense import (
        GroundingPhrasingDefenseEngine,
        PhrasingDefensePolicy,
    )

    probes: dict[str, dict[str, Any]] = {}
    for probe_id, kwargs in {
        "policy_surface_threshold": {"surface_threshold": 0.1},
        "policy_allow_surface_lift": {"allow_surface_lift": True},
        "policy_whitelist_transform": {"whitelisted_transform_ids": ("x",)},
        "policy_declared_not_proxy_gap": {"declared_not_proxy_gap": True},
    }.items():
        try:
            PhrasingDefensePolicy(**kwargs)
        except ValueError as exc:
            probes[probe_id] = {"accepted": False, "error": str(exc).split("\n", 1)[0]}
        else:
            probes[probe_id] = {"accepted": True}
    try:
        GroundingPhrasingDefenseEngine(reference, surface_threshold=0.1)  # type: ignore[call-arg]
    except TypeError as exc:
        probes["engine_surface_threshold_argument"] = {
            "accepted": False,
            "error": str(exc).split("\n", 1)[0],
        }
    else:
        probes["engine_surface_threshold_argument"] = {"accepted": True}
    return probes


def _base_cases(repo_root: Path) -> tuple[Any, ...]:
    from polisyos.runtime.quality.grounding_phrasing_defense import PhrasingDefenseBaseCase

    recorded = _recorded_n4_probe(repo_root)
    return (
        PhrasingDefenseBaseCase(
            case_id="cg4.base.admit",
            case_class="admit",
            proposal=_free_grow_probe(),
        ),
        PhrasingDefenseBaseCase(
            case_id="cg4.base.acquire",
            case_class="acquire",
            proposal=_tax_surface_transfer_no_evidence_probe(),
        ),
        PhrasingDefenseBaseCase(
            case_id="cg4.base.reject",
            case_class="reject",
            proposal=_self_loop_outcome_wish_probe(),
        ),
        PhrasingDefenseBaseCase(
            case_id="cg4.base.non_new",
            case_class="non_new",
            proposal=_paraphrase_probe(),
        ),
        PhrasingDefenseBaseCase(
            case_id="cg4.base.novel_recorded_n4",
            case_class="novel",
            proposal=recorded,
        ),
        PhrasingDefenseBaseCase(
            case_id="cg4.base.novel_structured",
            case_class="novel",
            proposal=_new_slot_probe(),
        ),
        PhrasingDefenseBaseCase(
            case_id="cg4.base.bind_eligible_frozen",
            case_class="bind_eligible_frozen",
            proposal=_tax_exact_probe(),
        ),
        PhrasingDefenseBaseCase(
            case_id="cg4.base.string_tax",
            case_class="bind_eligible_frozen",
            proposal=(
                "tax relief rate lowers global tax rate for government balance; "
                "average treatment effect, global population all."
            ),
        ),
    )


def _with_mechanism_edge(
    reference: Any,
    *,
    source: str,
    outcome: str,
    edge_id: str,
) -> Any:
    from polisyos.runtime.quality.credal_reference import (
        AdmissibleCompletion,
        CredalReferenceEdge,
        replace_reference_edge,
    )

    return replace_reference_edge(
        reference,
        CredalReferenceEdge(
            modality="L2_CAUSAL_CLAIM",
            edge_id=edge_id,
            status="confirmed",
            admissible_completions=(
                AdmissibleCompletion(
                    "fixed",
                    {
                        "direction": "positive",
                        "dst": outcome,
                        "source": source,
                        "src": source,
                        "target": outcome,
                    },
                    "cg4_validator_owner_evidence",
                ),
            ),
            provenance={
                "owner": "L2",
                "source": "cg4_validator_owner_evidence",
                "signals": {"confidence": 0.92, "trust_score": 0.92},
            },
        ).with_content_hash(),
    )


def _recorded_n4_probe(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
    try:
        from tools.quality.validation.check_layer3_gy_design_generation_contract import (
            first_shadow_bound_recorded_candidate,
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        candidate = first_shadow_bound_recorded_candidate(payload)
    except (AssertionError, OSError, RuntimeError, TypeError, ValueError):
        candidate = {}
    if candidate:
        candidate.setdefault("proposal_id", "cg4.recorded_n4.candidate")
        candidate.setdefault("raw_text", "recorded N4 generated candidate")
        return candidate
    return _new_slot_probe()


def _tax_exact_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg4.bind.tax_relief_exact",
        "raw_text": "tax relief rate lowers the global tax-rate setting.",
        "signature": {
            "op": "tax_relief_rate",
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.1},
            "x_do": {"rate": 0.1},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": ["tax_relief_rate", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="tax_relief_rate",
                target="global.tax_rate",
                outcome="government.balance",
                do_value={"rate": 0.1},
            ),
        },
    }


def _tax_unregistered_mimic_probe(op: str) -> dict[str, Any]:
    return {
        "proposal_id": f"cg4.tax_mimic.{op}",
        "raw_text": f"{op} lowers the global tax-rate setting.",
        "signature": {
            "op": op,
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.1},
            "x_do": {"rate": 0.1},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": [op, "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op=op,
                target="global.tax_rate",
                outcome="government.balance",
                do_value={"rate": 0.1},
            ),
        },
    }


def _surface_mutation_unrelated_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg4.mutation.surface_unrelated",
        "raw_text": "opaque adjustment writes an unowned audit slot.",
        "signature": {
            "op": "opaque_resilience_buffer",
            "target": ["audit.unowned_surface_slot"],
            "sign": "increase",
            "params": {"rate": 0.2},
            "x_do": {"rate": 0.2},
            "scope": "audit",
            "population": "audit",
            "unit": "ratio",
            "outcome": ["audit.unowned_outcome"],
            "effect_path": [
                "opaque_resilience_buffer",
                "audit.unowned_surface_slot",
                "audit.unowned_outcome",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="opaque_resilience_buffer",
                target="audit.unowned_surface_slot",
                outcome="audit.unowned_outcome",
                do_value={"rate": 0.2},
            ),
        },
    }


def _tax_surface_transfer_no_evidence_probe() -> dict[str, Any]:
    probe = _acquire_transfer_probe()
    return {
        **probe,
        "proposal_id": "cg4.proxy_gap.tax_named_transfer",
        "raw_text": (
            "tax relief rate tax relief statute tax credit exact fiscal lever for "
            "household transfer intensity"
        ),
    }


def _free_grow_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg4.admit.regional_resilience_credit",
        "raw_text": "regional resilience credit raises distress-score intervention intensity for cells.",
        "signature": {
            "op": "regional_resilience_credit",
            "target": ["cells.distress_score"],
            "sign": "increase",
            "params": {"rate": 0.4},
            "x_do": {"rate": 0.4},
            "scope": "regional_cells",
            "population": "cells",
            "unit": "ratio",
            "outcome": ["cells.output"],
            "effect_path": [
                "regional_resilience_credit",
                "cells.distress_score",
                "cells.output",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="regional_resilience_credit",
                target="cells.distress_score",
                outcome="cells.output",
                do_value={"rate": 0.4},
            ),
        },
    }


def _acquire_transfer_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg4.acquire.household_transfer",
        "raw_text": "household transfer intensity increases disposable income.",
        "signature": {
            "op": "household_transfer_adjustment",
            "target": ["household_cells.transfer_intensity"],
            "sign": "increase",
            "params": {"rate": 0.25},
            "x_do": {"rate": 0.25},
            "scope": "households",
            "population": "households",
            "unit": "ratio",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "household_transfer_adjustment",
                "household_cells.transfer_intensity",
                "household_cells.disposable_income",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="household_transfer_adjustment",
                target="household_cells.transfer_intensity",
                outcome="household_cells.disposable_income",
                do_value={"rate": 0.25},
            ),
        },
    }


def _self_loop_outcome_wish_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg4.reject.self_loop_outcome_wish",
        "raw_text": "directly raise household disposable income as its own outcome.",
        "signature": {
            "op": "raise_household_income_goal",
            "target": ["household_cells.disposable_income"],
            "sign": "increase",
            "params": {"goal": 1.0},
            "x_do": {"goal": 1.0},
            "scope": "households",
            "population": "households",
            "unit": "usd",
            "outcome": ["household_cells.disposable_income"],
            "effect_path": [
                "raise_household_income_goal",
                "household_cells.disposable_income",
                "household_cells.disposable_income",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="raise_household_income_goal",
                target="household_cells.disposable_income",
                outcome="household_cells.disposable_income",
                do_value={"goal": 1.0},
            ),
        },
    }


def _paraphrase_probe() -> dict[str, Any]:
    probe = _tax_exact_probe()
    signature = dict(probe["signature"])
    signature["op"] = "tax_support_rate"
    signature["effect_path"] = ["tax_support_rate", "global.tax_rate", "government.balance"]
    signature["modal_claims"] = _modal_claims(
        op="tax_support_rate",
        target="global.tax_rate",
        outcome="government.balance",
        do_value={"rate": 0.1},
    )
    return {
        **probe,
        "proposal_id": "cg4.non_new.tax_support_rate",
        "raw_text": "tax support rate changes the tax slot with the same do-query.",
        "signature": signature,
    }


def _new_slot_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg4.novel.new_slot",
        "raw_text": "temporary resilience buffer writes a new acquirable slot.",
        "signature": {
            "op": "temporary_resilience_buffer",
            "target": ["cells.resilience_buffer"],
            "sign": "increase",
            "params": {"rate": 0.2},
            "x_do": {"rate": 0.2},
            "scope": "regional_cells",
            "population": "cells",
            "unit": "ratio",
            "outcome": ["cells.output"],
            "effect_path": ["temporary_resilience_buffer", "cells.resilience_buffer", "cells.output"],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="temporary_resilience_buffer",
                target="cells.resilience_buffer",
                outcome="cells.output",
                do_value={"rate": 0.2},
            ),
        },
    }


def _modal_claims(
    *,
    op: str,
    target: str,
    outcome: str,
    do_value: dict[str, float],
) -> dict[str, dict[str, Any]]:
    return {
        "NL": {
            "op": op,
            "target": target,
            "outcome": outcome,
            "estimand": "average_treatment_effect",
        },
        "do_AST": {"op": op, "target": target, "do_value": do_value},
        "method": {
            "treatment_op": op,
            "treatment_target": target,
            "outcome": outcome,
            "estimand": "average_treatment_effect",
        },
    }


def _causal_evidence_score(run: Any) -> float:
    signature = run.evidence_signature
    if signature.cg1_relation_class in {"exact", "certified-specialization"}:
        return 1.0
    if signature.cg3_denotation_match_kind == "resolved_proof":
        return 1.0
    if signature.cg3_mechanism_status == "closed" and signature.cg3_data_trust_status == "closed":
        return signature.cg3_data_trust_cap
    return min(signature.cg3_data_trust_cap, 0.49)


def _proxy_gap_probe_record(
    run: Any,
    risk: Any | None,
    *,
    handoff: Any | None = None,
    surface_affinity_threshold: float,
    causal_evidence_threshold: float,
) -> dict[str, Any]:
    affinity = run.surface_view.max_surface_affinity
    evidence = _causal_evidence_score(run)
    return {
        "raw_operator_spelling": run.surface_view.raw_operator_spelling,
        "quarantined": risk is not None,
        "risk": risk.model_dump(mode="json") if risk else None,
        "handoff": handoff.model_dump(mode="json") if handoff else None,
        "cg1_relation": run.decisions.cg1_relation,
        "cg2_decision": run.decisions.cg2_decision,
        "cg3_decision": run.decisions.cg3_decision,
        "cg3_denotation_match_kind": run.evidence_signature.cg3_denotation_match_kind,
        "surface_affinity": affinity,
        "surface_affinity_threshold": surface_affinity_threshold,
        "above_surface_affinity_threshold": affinity >= surface_affinity_threshold,
        "causal_evidence_score": evidence,
        "causal_evidence_threshold": causal_evidence_threshold,
        "below_causal_evidence_threshold": evidence < causal_evidence_threshold,
        "open_obligations": list(run.evidence_signature.cg3_open_obligations),
        "not_bindable": run.decisions.cg2_decision != "bind",
        "not_admissible": run.decisions.cg3_decision != "admit_new_lever",
    }


def _slug(value: str) -> str:
    return "_".join(part for part in "".join(
        char.lower() if char.isalnum() else "_"
        for char in value
    ).split("_") if part)


def _probe(payload: Any, key: str) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get(key), dict):
        return payload[key]
    return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    output = args.output or repo_root / OUTPUT_PATH
    payload = build_live_payload(repo_root)
    report = validate_payload(payload)
    corrupt_report = None
    if args.corrupt_field_drift_check:
        corrupt_report = _corrupt_field_drift_check(payload)
        if corrupt_report["status"] != "pass":
            report["status"] = "fail"
            report["issues"].extend(corrupt_report["issues"])
    if args.check:
        if not output.exists():
            report["status"] = "fail"
            report["issues"].append({"code": "grounding_phrasing_defense_artifact_missing"})
        else:
            existing = json.loads(output.read_text(encoding="utf-8"))
            if existing != payload:
                report["status"] = "fail"
                report["issues"].append({"code": "grounding_phrasing_defense_artifact_drift"})
    if args.write:
        write_payload(payload, output)

    result = {
        "status": report["status"],
        "issues": report["issues"],
        "output": str(output),
        "corrupt_field_drift_check": corrupt_report,
        "matrix_counts": payload["matrix_counts"],
        "proxy_gap_capture_pair": payload["proxy_gap_capture_pair"],
        "behavioral_mutations": payload["behavioral_mutations"],
    }
    if args.output_format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"status={result['status']} issues={len(result['issues'])}")
        for issue in result["issues"]:
            print(json.dumps(issue, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
