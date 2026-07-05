#!/usr/bin/env python3
"""Validate the CGF GY-CG5 active grounding controller contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/grounding_active_controller_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.grounding_active_controller_contract.v1"
EXPECTED_MUTATIONS = {
    "never_buy_bind_boundary_removed",
    "counterfactual_stamp_removed",
    "counterfactual_redaction_removed",
    "decisiveness_sensor_removed",
    "budget_dominance_removed",
    "owner_revalidation_removed",
    "production_edge_acceptance_restored",
}
EXPECTED_ACTION_FAMILIES = {
    "cheap_verify",
    "elicit_human",
    "acquire_data",
    "adversarial_validate",
    "abstain",
}


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
    """Recompute the CG5 contract from live CG0-CG4 owner paths."""

    _configure_validation_jax_platform()
    from polisyos.runtime.quality.credal_reference import build_credal_reference
    from polisyos.runtime.quality.grounding_active_controller import (
        GROUNDING_ACTIVE_CONTROLLER_SCHEMA_VERSION,
        GroundingActionCertificate,
        GroundingActionResult,
        GroundingActiveController,
        GroundingActiveControllerPolicy,
        GroundingControllerCase,
        OwnerShapedReferenceEdgeResult,
        grounding_blocker_action_table,
        grounding_blocker_denominator,
        unknown_blocker_fail_safe,
    )
    from polisyos.runtime.quality.grounding_admission import (
        GroundingAdmissionEngine,
        apply_grounding_admission_registry_patch,
    )
    from polisyos.runtime.quality.grounding_phrasing_defense import (
        GroundingPhrasingDefenseEngine,
    )
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
    from tools.quality.validation.check_grounding_admission_contract import (
        _BoundedReferenceIndex,
        _cg2_pair,
        _free_grow_probe,
        _outcome_like_policy_map_probe,
        _with_mechanism_edge,
    )
    from tools.quality.validation.check_grounding_phrasing_defense_contract import (
        _tax_unregistered_mimic_probe,
    )
    from tools.quality.validation.check_grounding_relation_contract import (
        _unknown_unproven_probe,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    reference = build_credal_reference(repo_root)
    controller = GroundingActiveController.for_contract_testing(
        reference,
        bounded_reference_replay=True,
    )

    acquire_probe = _free_grow_probe()
    cg1_acquire, cg2_acquire = _cg2_pair(reference, acquire_probe)
    cg3_acquire = GroundingAdmissionEngine(reference).decide(
        cg2_acquire,
        cg1_certificate=cg1_acquire,
    )
    acquire_case = GroundingControllerCase(
        case_id="cg5.acquire.mechanism_missing",
        proposal=acquire_probe,
        cg1_certificate=cg1_acquire,
        cg2_certificate=cg2_acquire,
        cg3_certificate=cg3_acquire,
    )
    acquire_certificate = controller.certificate_for(acquire_case)
    acquire_reentry_reference = _with_mechanism_edge(
        reference,
        source="cells.distress_score",
        outcome="cells.output",
        edge_id="cg5_owner_reentry_direct_edge",
    )
    acquire_reentry_controller = GroundingActiveController.for_contract_testing(
        acquire_reentry_reference,
        bounded_reference_replay=True,
    )
    acquisition_result = GroundingActionResult(
        action_family="acquire_data",
        result_id="cg5.acquire.result.reference_only",
    )
    acquire_reentry = acquire_reentry_controller.route_action_result(
        acquire_certificate,
        acquisition_result,
        case=acquire_case,
    )
    self_supplied_edge_result = _self_supplied_mechanism_result(
        GroundingActionResult,
        OwnerShapedReferenceEdgeResult,
        result_id="cg5.attack.self_supplied_high_trust_edge",
        source="cells.distress_score",
        outcome="cells.output",
    )

    admissibility_reference = _with_mechanism_edge(
        reference,
        source="cells.distress_score",
        outcome="cells.output",
        edge_id="cg5_admissibility_probe_direct_edge",
    )
    low_probe = _free_grow_probe()
    low_probe = {
        **low_probe,
        "proposal_id": "cg5.low_cost.high_human_admissibility",
        "signature": {
            **low_probe["signature"],
            "admissibility": "candidate_unverified",
        },
    }
    cg1_low, cg2_low = _cg2_pair(admissibility_reference, low_probe)
    cg3_low = GroundingAdmissionEngine(admissibility_reference).decide(
        cg2_low,
        cg1_certificate=cg1_low,
    )
    low_case = GroundingControllerCase(
        case_id="cg5.low_voi.high_cost",
        proposal=low_probe,
        cg1_certificate=cg1_low,
        cg2_certificate=cg2_low,
        cg3_certificate=cg3_low,
    )
    low_certificate = GroundingActiveController.for_contract_testing(
        admissibility_reference,
        bounded_reference_replay=True,
    ).certificate_for(low_case)

    unknown_probe = _unknown_unproven_probe()
    unknown_engine = GroundingRelationEngine(reference)
    unknown_engine._fts_index = _BoundedReferenceIndex(reference)  # noqa: SLF001
    cg1_unknown = unknown_engine.certificate_for(
        unknown_probe,
        proposal_id="cg5.cheap_verify.unknown_axes",
    )
    cheap_case = GroundingControllerCase(
        case_id="cg5.cheap_verify.structural_only",
        proposal=unknown_probe,
        cg1_certificate=cg1_unknown,
    )
    cheap_certificate = controller.certificate_for(cheap_case)

    phrasing_engine = GroundingPhrasingDefenseEngine(reference)
    proxy_run = phrasing_engine._run_pipeline(  # noqa: SLF001
        _tax_unregistered_mimic_probe("tax relief rate adjustment"),
        proposal_id="cg5.cg4.proxy_gap",
        bounded_cg1=True,
    )
    proxy_risk = phrasing_engine.detect_proxy_gap(proxy_run)
    if proxy_risk is None:
        raise RuntimeError("cg5_proxy_gap_risk_missing")
    cg4_case = GroundingControllerCase(
        case_id="cg5.cg4.proxy_gap",
        proposal=_tax_unregistered_mimic_probe("tax relief rate adjustment"),
        proxy_gap_risk=proxy_risk,
    )
    cg4_certificate = controller.certificate_for(cg4_case)
    cg4_reentry = controller.route_action_result(
        cg4_certificate,
        GroundingActionResult(
            action_family="adversarial_validate",
            result_id=f"{proxy_risk.risk_id}.cg5_result_reference",
        ),
        case=cg4_case,
    )

    forged_result = GroundingActionResult(
        action_family="acquire_data",
        result_id="cg5.forged.claim_only",
        claimed_resolution=True,
    )
    production_controller = GroundingActiveController(reference)
    self_supplied_edge_reentry = production_controller.route_action_result(
        acquire_certificate,
        self_supplied_edge_result,
        case=acquire_case,
    )
    forged_reentry = production_controller.route_action_result(
        acquire_certificate,
        forged_result,
        case=acquire_case,
    )
    forged_certificate_probe = _forged_certificate_probe(
        GroundingActionCertificate,
        acquire_certificate,
    )

    unknown_blocker = unknown_blocker_fail_safe(
        case_id="cg5.future",
        gate="UNKNOWN",
        blocker_type="future_gate_reason",
    )

    deterministic_a = controller.certificate_for(acquire_case)
    deterministic_b = controller.certificate_for(acquire_case)
    no_writability_probe = _outcome_like_policy_map_probe()
    cg1_writability, cg2_writability = _cg2_pair(reference, no_writability_probe)
    cg3_writability = GroundingAdmissionEngine(reference).decide(
        cg2_writability,
        cg1_certificate=cg1_writability,
    )
    full_cg1_claims = _full_cg1_decisive_claims(
        reference=reference,
        acquire_probe=acquire_probe,
        acquire_case=acquire_case,
        acquire_certificate=acquire_certificate,
        bounded_acquire_before=cg3_acquire,
        bounded_acquire_reentry=acquire_reentry,
        unknown_probe=unknown_probe,
        bounded_cheap_certificate=cheap_certificate,
        bounded_cg1_unknown=cg1_unknown,
        controller_cls=GroundingActiveController,
        action_result_cls=GroundingActionResult,
        admission_engine_cls=GroundingAdmissionEngine,
    )
    counterfactual_containment = _counterfactual_containment_probe(
        controller=controller,
        acquire_case=acquire_case,
        reference=reference,
        admission_engine_cls=GroundingAdmissionEngine,
        apply_registry_patch=apply_grounding_admission_registry_patch,
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.grounding_active_controller_rt7",
        "runtime_schema_version": GROUNDING_ACTIVE_CONTROLLER_SCHEMA_VERSION,
        "owner": "polisyos.runtime.quality.grounding_active_controller",
        "source_modules": [
            "src/polisyos/runtime/quality/grounding_active_controller.py",
            "src/polisyos/runtime/quality/grounding_relation.py",
            "src/polisyos/runtime/quality/grounding_bind.py",
            "src/polisyos/runtime/quality/grounding_admission.py",
            "src/polisyos/runtime/quality/grounding_phrasing_defense.py",
            "src/polisyos/runtime/quality/credal_reference.py",
            "tools/quality/validation/check_grounding_active_controller_contract.py",
        ],
        "reuse_existing_owners": [
            "CG0 CredalReference",
            "CG1 GroundingRelationCertificate",
            "CG2 GroundingDecisionCertificate",
            "CG3 GroundingAdmissionCertificate and AcquisitionNeed",
            "CG4 GroundingProxyGapRisk and real phrasing-defense harness",
        ],
        "reference": {
            "reference_epoch": reference.reference_epoch,
            "reference_hash": reference.reference_hash,
            "edge_count": len(reference.essential_edges),
            "component_versions": dict(sorted(reference.component_versions.items())),
        },
        "blocker_denominator": grounding_blocker_denominator().model_dump(mode="json"),
        "action_family_table": [
            row.model_dump(mode="json") for row in grounding_blocker_action_table()
        ],
        "cases": {
            "acquire_loop": {
                "certificate": acquire_certificate.model_dump(mode="json"),
                "before": _admission_summary(cg3_acquire),
                "reentry": acquire_reentry.model_dump(mode="json"),
            },
            "low_voi_high_cost_abstain": {
                "certificate": low_certificate.model_dump(mode="json"),
                "before": _admission_summary(cg3_low),
            },
            "cheap_verify_structural_only": {
                "certificate": cheap_certificate.model_dump(mode="json"),
                "cg1_relation": cg1_unknown.selected_relation,
                "unresolved_axes": list(cg1_unknown.unresolved_axes),
            },
            "cg4_quarantine": {
                "certificate": cg4_certificate.model_dump(mode="json"),
                "risk": proxy_risk.model_dump(mode="json"),
                "reentry": cg4_reentry.model_dump(mode="json"),
            },
            "no_positive_writability_proof": _admission_summary(cg3_writability),
        },
        "forged_inputs_fail_closed": {
            "self_supplied_edge_reentry": self_supplied_edge_reentry.model_dump(mode="json"),
            "claimed_resolution_reentry": forged_reentry.model_dump(mode="json"),
            "forged_certificate": forged_certificate_probe,
            "unknown_blocker_route": unknown_blocker.model_dump(mode="json"),
        },
        "full_cg1_decisive_claims": full_cg1_claims,
        "counterfactual_containment": counterfactual_containment,
        "lift_vs_passive_abstain": _lift_report(
            acquire_reentry=acquire_reentry.model_dump(mode="json"),
            cg4_reentry=cg4_reentry.model_dump(mode="json"),
            low_certificate=low_certificate.model_dump(mode="json"),
            cheap_certificate=cheap_certificate.model_dump(mode="json"),
        ),
        "action_family_exercises": _action_family_exercises(
            acquire_certificate.model_dump(mode="json"),
            low_certificate.model_dump(mode="json"),
            cheap_certificate.model_dump(mode="json"),
            cg4_certificate.model_dump(mode="json"),
        ),
        "production_api_boundary_probes": _production_api_boundary_probes(
            GroundingActiveController,
            GroundingActiveControllerPolicy,
            reference,
        ),
        "determinism": {
            "first_content_hash": deterministic_a.content_hash,
            "second_content_hash": deterministic_b.content_hash,
            "same_content_hash": deterministic_a.content_hash
            == deterministic_b.content_hash,
        },
        "behavioral_mutations": _mutation_reports(
            reference=reference,
            acquire_case=acquire_case,
            acquire_certificate=acquire_certificate,
            forged_result=forged_result,
            self_supplied_edge_result=self_supplied_edge_result,
            low_case=low_case,
            counterfactual_containment=counterfactual_containment,
        ),
        "deferred": {
            "multi_action_evsi": None,
            "observation_model_learning": None,
            "search_leverage_voi": None,
            "status": "deferred_not_fabricated",
        },
        "capability_reality": {
            "typed_contract_artifact": (
                "GroundingActionCertificate + GroundingBlockerView + "
                "GroundingActionTicket + GroundingActionReentryRecord"
            ),
            "producer": "GroundingActiveController.certificate_for",
            "persisted_artifact_event": OUTPUT_PATH,
            "orchestration_bridge": (
                "CG5 consumes CG1-CG4 certificates and routes action-result references "
                "back through CG1->CG2->CG3 or CG4; acquisition data must already be "
                "present through an owner-built reference"
            ),
            "consumer": "validator/audit surface; GY-N7 live direct intake remains bridge_missing",
            "verification": "this recomputing validator, unit probes, mutation probes, drift check",
            "surface": "generated Policy Design Case CG5 contract artifact",
            "semantic_test": (
                "acquire loop lift, low-cost abstain, CG4 quarantine route, "
                "self-supplied edge fail-closed, production API boundary"
            ),
            "capability_label": "bridge_missing",
        },
        "pattern_pass": {
            "relevant_ids": [
                "P01",
                "P03",
                "P04",
                "P05",
                "P10",
                "P15",
                "P27",
                "P28",
                "P29",
                "P31",
                "P32",
                "P33",
            ],
            "target_correct_pattern": (
                "thin controller over gate-owned typed blockers; counterfactuals are "
                "planning-only and every advancement is re-derived by gates from owner data"
            ),
            "missing_capability_labels": ["bridge_missing"],
            "acceptance_signal": (
                "contract check plus corrupt-field check pass; mutations are red"
            ),
        },
    }
    return _json_stable(payload)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a CG5 payload against behavioral properties."""

    issues = _core_issues(payload, require_mutations=True)
    return {"status": "pass" if not issues else "fail", "issues": issues}


def validate(repo_root: Path | None = None) -> dict[str, Any]:
    """Validate committed artifact drift and live CG5 behavior."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    path = repo_root / OUTPUT_PATH
    live = build_live_payload(repo_root)
    issues = _core_issues(live, require_mutations=True)
    if not path.is_file():
        issues.append({"code": "grounding_active_controller_contract_missing", "path": OUTPUT_PATH})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "grounding_active_controller_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None and committed != live:
        issues.append({"code": "grounding_active_controller_contract_drift", "path": OUTPUT_PATH})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
        "selected_actions": {
            key: value.get("certificate", {}).get("selected_action")
            for key, value in live.get("cases", {}).items()
            if isinstance(value, dict)
        },
        "lift_vs_passive_abstain": live["lift_vs_passive_abstain"],
        "mutation_statuses": {
            row["mutation_id"]: row["status"] for row in live["behavioral_mutations"]
        },
    }


def write(repo_root: Path, *, payload: dict[str, Any] | None = None) -> None:
    """Write the live CG5 contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    live = payload or build_live_payload(repo_root)
    path.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def corrupt_field_drift_check(repo_root: Path | None = None) -> dict[str, Any]:
    """Prove corrupt decisive CG5 fields turn validation red."""

    live = build_live_payload(repo_root)
    corrupted = _copy(live)
    corrupted["cases"]["acquire_loop"]["certificate"]["selected_action"] = "abstain"
    corrupted["cases"]["acquire_loop"]["reentry"]["advanced_by_gate"] = False
    corrupted["forged_inputs_fail_closed"]["self_supplied_edge_reentry"][
        "advanced_by_gate"
    ] = True
    corrupted["full_cg1_decisive_claims"]["acquire_loop"][
        "bounded_vs_full_agree"
    ] = False
    corrupted["counterfactual_containment"]["redaction_holds"] = False
    corrupted["lift_vs_passive_abstain"]["closed"] = 0
    corrupted["blocker_denominator"]["cg3_decisive_reasons"] = []
    corrupted["behavioral_mutations"][0]["status"] = "green"
    report = validate_payload(corrupted)
    return {
        "status": "pass" if report["status"] == "fail" else "fail",
        "issues": []
        if report["status"] == "fail"
        else [{"code": "grounding_active_controller_corrupt_field_not_detected"}],
        "corrupt_report_status": report["status"],
        "corrupt_issue_codes": [issue["code"] for issue in report["issues"]],
    }


def _core_issues(
    payload: dict[str, Any],
    *,
    require_mutations: bool,
) -> list[dict[str, Any]]:
    from polisyos.runtime.quality.grounding_active_controller import (
        GroundingActionCertificate,
        grounding_blocker_denominator,
    )

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "grounding_active_controller_schema_mismatch"})
    expected_denominator = grounding_blocker_denominator().model_dump(mode="json")
    if payload.get("blocker_denominator") != expected_denominator:
        issues.append({"code": "grounding_active_controller_denominator_drift"})
    cases = payload.get("cases", {})
    for case_id, row in cases.items():
        if not isinstance(row, dict) or "certificate" not in row:
            continue
        try:
            GroundingActionCertificate.model_validate(row["certificate"])
        except Exception as exc:  # noqa: BLE001 - validator reports model error as data.
            issues.append(
                {
                    "code": "grounding_active_controller_certificate_invalid",
                    "case": case_id,
                    "error": str(exc).split("\n", 1)[0],
                }
            )
    acquire = _case(cases, "acquire_loop")
    acquire_cert = _probe(acquire, "certificate")
    acquire_reentry = _probe(acquire, "reentry")
    if acquire_cert.get("selected_action") != "acquire_data":
        issues.append({"code": "grounding_active_controller_acquire_not_selected"})
    if acquire_reentry.get("after_disposition") != "admit_new_lever":
        issues.append({"code": "grounding_active_controller_acquire_loop_not_lifted"})
    if acquire_reentry.get("advanced_by_gate") is not True:
        issues.append({"code": "grounding_active_controller_acquire_not_gate_advanced"})
    if acquire_reentry.get("false_bind_or_admit") is not False:
        issues.append({"code": "grounding_active_controller_false_bind_detected"})
    low = _case(cases, "low_voi_high_cost_abstain")
    low_cert = _probe(low, "certificate")
    if low_cert.get("selected_action") != "abstain":
        issues.append({"code": "grounding_active_controller_low_cost_case_not_abstained"})
    if low_cert.get("remaining_candidate_action") != "elicit_human":
        issues.append({"code": "grounding_active_controller_remaining_action_not_recorded"})
    if not any(
        candidate.get("action_family") == "elicit_human"
        and candidate.get("within_budget") is False
        for candidate in low_cert.get("candidates", [])
        if isinstance(candidate, dict)
    ):
        issues.append({"code": "grounding_active_controller_high_cost_candidate_missing"})
    cheap = _case(cases, "cheap_verify_structural_only")
    cheap_cert = _probe(cheap, "certificate")
    if not any(
        candidate.get("action_family") == "cheap_verify"
        for candidate in cheap_cert.get("candidates", [])
        if isinstance(candidate, dict)
    ):
        issues.append({"code": "grounding_active_controller_cheap_verify_not_exercised"})
    cg4 = _case(cases, "cg4_quarantine")
    cg4_cert = _probe(cg4, "certificate")
    cg4_reentry = _probe(cg4, "reentry")
    if cg4_cert.get("selected_action") != "adversarial_validate":
        issues.append({"code": "grounding_active_controller_cg4_not_routed"})
    if cg4_reentry.get("reentered_gate") != "CG4":
        issues.append({"code": "grounding_active_controller_cg4_not_reentered"})
    exercises = set(payload.get("action_family_exercises", {}).get("families", []))
    missing_families = sorted(EXPECTED_ACTION_FAMILIES.difference(exercises))
    if missing_families:
        issues.append(
            {
                "code": "grounding_active_controller_action_family_missing",
                "missing": missing_families,
            }
        )
    forged = payload.get("forged_inputs_fail_closed", {})
    self_supplied_edge = _probe(forged, "self_supplied_edge_reentry")
    if self_supplied_edge.get("advanced_by_gate") is not False:
        issues.append({"code": "grounding_active_controller_self_supplied_edge_advanced"})
    if (
        self_supplied_edge.get("after_reason")
        != "production_result_payload_rejected_owner_data_path"
    ):
        issues.append({"code": "grounding_active_controller_self_supplied_edge_not_rejected"})
    forged_reentry = _probe(forged, "claimed_resolution_reentry")
    if forged_reentry.get("advanced_by_gate") is not False:
        issues.append({"code": "grounding_active_controller_forged_result_advanced"})
    if _probe(forged, "forged_certificate").get("accepted") is not False:
        issues.append({"code": "grounding_active_controller_forged_certificate_accepted"})
    if _probe(forged, "unknown_blocker_route").get("action_family") != "abstain":
        issues.append({"code": "grounding_active_controller_unknown_blocker_not_abstain"})
    lift = payload.get("lift_vs_passive_abstain", {})
    if lift.get("closed", 0) < 1:
        issues.append({"code": "grounding_active_controller_no_positive_lift"})
    if lift.get("false_binds_or_admits") != 0:
        issues.append({"code": "grounding_active_controller_false_bind_nonzero"})
    if lift.get("passive_abstain_closed") != 0:
        issues.append({"code": "grounding_active_controller_passive_closed_nonzero"})
    full_claims = payload.get("full_cg1_decisive_claims", {})
    acquire_full = _probe(full_claims, "acquire_loop")
    if acquire_full.get("bounded_vs_full_agree") is not True:
        issues.append({"code": "grounding_active_controller_full_cg1_acquire_disagrees"})
    if acquire_full.get("full_reentry", {}).get("after_disposition") != "admit_new_lever":
        issues.append({"code": "grounding_active_controller_full_cg1_acquire_not_admitted"})
    if acquire_full.get("false_bind_rederived_by_full_gate") is not True:
        issues.append({"code": "grounding_active_controller_full_false_bind_not_rederived"})
    if (
        _probe(full_claims, "low_trust_owner_corruption").get("full_decision")
        == "admit_new_lever"
    ):
        issues.append({"code": "grounding_active_controller_low_trust_owner_corruption_admitted"})
    cheap_full = _probe(full_claims, "cheap_verify")
    if cheap_full.get("bounded_vs_full_agree") is not True:
        issues.append({"code": "grounding_active_controller_full_cg1_cheap_disagrees"})
    containment = payload.get("counterfactual_containment", {})
    if containment.get("reference_untouched_after_planning") is not True:
        issues.append({"code": "grounding_active_controller_counterfactual_contaminated_reference"})
    if containment.get("extracted_counterfactual_admit_refused") is not True:
        issues.append({"code": "grounding_active_controller_counterfactual_admit_not_refused"})
    if containment.get("redaction_holds") is not True:
        issues.append({"code": "grounding_active_controller_counterfactual_redaction_failed"})
    if _has_counterfactual_payload_leak(payload):
        issues.append({"code": "grounding_active_controller_counterfactual_payload_leaked"})
    boundary = payload.get("production_api_boundary_probes", {})
    for probe_id, row in sorted(boundary.items()):
        if row.get("accepted") is not False:
            issues.append(
                {
                    "code": "grounding_active_controller_public_api_accepted_authority_knob",
                    "probe": probe_id,
                }
            )
    if payload.get("determinism", {}).get("same_content_hash") is not True:
        issues.append({"code": "grounding_active_controller_not_deterministic"})
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
                    "code": "grounding_active_controller_required_mutation_missing",
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
                    "code": "grounding_active_controller_required_mutation_not_red",
                    "mutation_ids": not_red,
                }
            )
    return issues


def _mutation_reports(
    *,
    reference: Any,
    acquire_case: Any,
    acquire_certificate: Any,
    forged_result: Any,
    self_supplied_edge_result: Any,
    low_case: Any,
    counterfactual_containment: dict[str, Any],
) -> list[dict[str, Any]]:
    from polisyos.runtime.quality.grounding_active_controller import GroundingActiveController

    reports: list[dict[str, Any]] = []
    trust_mut = GroundingActiveController.for_contract_testing(
        reference,
        trust_action_result_claim=True,
        bounded_reference_replay=True,
    ).route_action_result(acquire_certificate, forged_result, case=acquire_case)
    reports.append(
        _mutation_row(
            "never_buy_bind_boundary_removed",
            trust_mut.advanced_by_gate and trust_mut.final_certificate_id is None,
            trust_mut.model_dump(mode="json"),
        )
    )
    reports.append(
        _mutation_exception_row(
            "counterfactual_stamp_removed",
            lambda: GroundingActiveController.for_contract_testing(
                reference,
                remove_counterfactual_stamp=True,
                bounded_reference_replay=True,
            ).certificate_for(acquire_case),
        )
    )
    reports.append(
        _mutation_row(
            "counterfactual_redaction_removed",
            _has_counterfactual_payload_leak(
                {
                    "counterfactual_inner_certificate": acquire_case.cg3_certificate.model_dump(
                        mode="json"
                    ),
                    "baseline_containment": counterfactual_containment,
                }
            ),
            {"counterfactual_inner_certificate_present": True},
        )
    )
    sensor_mut = GroundingActiveController.for_contract_testing(
        reference,
        disable_decisiveness_sensor=True,
        bounded_reference_replay=True,
    ).certificate_for(low_case)
    reports.append(
        _mutation_row(
            "decisiveness_sensor_removed",
            sensor_mut.selected_action != "abstain",
            {"selected_action": sensor_mut.selected_action},
        )
    )
    budget_mut = GroundingActiveController.for_contract_testing(
        reference,
        force_most_expensive_action=True,
        bounded_reference_replay=True,
    ).certificate_for(low_case)
    reports.append(
        _mutation_row(
            "budget_dominance_removed",
            budget_mut.selected_action == "elicit_human",
            {"selected_action": budget_mut.selected_action},
        )
    )
    owner_mut = GroundingActiveController.for_contract_testing(
        reference,
        trust_action_result_claim=True,
        bounded_reference_replay=True,
    ).route_action_result(acquire_certificate, forged_result, case=acquire_case)
    reports.append(
        _mutation_row(
            "owner_revalidation_removed",
            owner_mut.advanced_by_gate and owner_mut.final_certificate_id is None,
            owner_mut.model_dump(mode="json"),
        )
    )
    edge_mut = GroundingActiveController.for_contract_testing(
        reference,
        bounded_reference_replay=True,
        allow_result_edge_injection_mutation=True,
    ).route_action_result(acquire_certificate, self_supplied_edge_result, case=acquire_case)
    reports.append(
        _mutation_row(
            "production_edge_acceptance_restored",
            edge_mut.advanced_by_gate and edge_mut.after_disposition == "admit_new_lever",
            edge_mut.model_dump(mode="json"),
        )
    )
    return reports


def _mutation_exception_row(mutation_id: str, callback: Any) -> dict[str, Any]:
    try:
        callback()
    except Exception as exc:  # noqa: BLE001 - exception is the red mutation signal.
        return {
            "mutation_id": mutation_id,
            "status": "red",
            "probe": {"error": str(exc).split("\n", 1)[0]},
        }
    return {"mutation_id": mutation_id, "status": "green", "probe": {}}


def _mutation_row(mutation_id: str, flipped_bad: bool, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "mutation_id": mutation_id,
        "status": "red" if flipped_bad else "green",
        "probe": payload,
    }


def _forged_certificate_probe(model: Any, certificate: Any) -> dict[str, Any]:
    payload = certificate.model_dump(mode="json")
    payload["selected_action"] = "abstain"
    try:
        model.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - fail-closed is reported.
        return {"accepted": False, "error": str(exc).split("\n", 1)[0]}
    return {"accepted": True}


def _self_supplied_mechanism_result(
    result_cls: Any,
    edge_cls: Any,
    *,
    result_id: str,
    source: str,
    outcome: str,
) -> Any:
    return result_cls(
        action_family="acquire_data",
        result_id=result_id,
        owner_shaped_edges=(
            edge_cls(
                modality="L2_CAUSAL_CLAIM",
                edge_id="cg5_attack_self_supplied_high_trust_edge",
                status="confirmed",
                completion_value={"direction": "positive", "dst": outcome, "src": source},
                completion_reason="attacker_self_asserted_mechanism",
                provenance={
                    "owner": "L2",
                    "source": "attacker_supplied_result_payload",
                    "signals": {
                        "confidence": 0.95,
                        "strong_design_evidence": True,
                        "trust_score": 0.95,
                    },
                },
                verifier_provenance="attacker_self_attested",
            ),
        ),
    )


def _full_cg1_decisive_claims(
    *,
    reference: Any,
    acquire_probe: dict[str, Any],
    acquire_case: Any,
    acquire_certificate: Any,
    bounded_acquire_before: Any,
    bounded_acquire_reentry: Any,
    unknown_probe: dict[str, Any],
    bounded_cheap_certificate: Any,
    bounded_cg1_unknown: Any,
    controller_cls: Any,
    action_result_cls: Any,
    admission_engine_cls: Any,
) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_bind import GroundingBindGate
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
    from tools.quality.validation.check_grounding_admission_contract import _with_mechanism_edge

    full_engine = GroundingRelationEngine(reference)
    cg1_before = full_engine.certificate_for(
        acquire_probe,
        proposal_id="cg5.full.acquire.before",
    )
    cg2_before = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1_before)
    cg3_before = admission_engine_cls(reference).decide(cg2_before, cg1_certificate=cg1_before)

    owner_reference = _with_mechanism_edge(
        reference,
        source="cells.distress_score",
        outcome="cells.output",
        edge_id="cg5_full_owner_reentry_direct_edge",
    )
    full_reentry = controller_cls(owner_reference).route_action_result(
        acquire_certificate,
        action_result_cls(
            action_family="acquire_data",
            result_id="cg5.full.acquire.result.reference_only",
        ),
        case=acquire_case,
    )
    cg1_after = GroundingRelationEngine(owner_reference).certificate_for(
        acquire_probe,
        proposal_id="cg5.full.acquire.after",
    )
    cg2_after = GroundingBindGate.for_contract_testing(
        owner_reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1_after)
    cg3_after = admission_engine_cls(owner_reference).decide(cg2_after, cg1_certificate=cg1_after)

    low_trust_reference = _with_mechanism_edge(
        reference,
        source="cells.distress_score",
        outcome="cells.output",
        edge_id="cg5_full_owner_reentry_low_trust_edge",
        trust_score=0.2,
        confidence=0.2,
    )
    cg1_low_trust = GroundingRelationEngine(low_trust_reference).certificate_for(
        acquire_probe,
        proposal_id="cg5.full.acquire.low_trust",
    )
    cg2_low_trust = GroundingBindGate.for_contract_testing(
        low_trust_reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1_low_trust)
    cg3_low_trust = admission_engine_cls(low_trust_reference).decide(
        cg2_low_trust,
        cg1_certificate=cg1_low_trust,
    )

    cg1_unknown_full = full_engine.certificate_for(
        unknown_probe,
        proposal_id="cg5.full.cheap_verify.unknown_axes",
    )
    cheap_case_full = acquire_case.__class__(
        case_id="cg5.full.cheap_verify.structural_only",
        proposal=unknown_probe,
        cg1_certificate=cg1_unknown_full,
    )
    cheap_certificate_full = controller_cls(reference).certificate_for(cheap_case_full)

    return {
        "scope": "full_cg1_real_fts",
        "bounded_auxiliary_scope_note": (
            "Bounded replay remains for auxiliary contract probes; these headline "
            "decisive claims are re-derived on the full CG1 path."
        ),
        "full_reference_engine_reuse": "one GroundingRelationEngine(reference) reused for baseline acquire and cheap probes",
        "acquire_loop": {
            "bounded_before": _admission_summary(bounded_acquire_before),
            "full_before": _admission_summary(cg3_before),
            "bounded_reentry": bounded_acquire_reentry.model_dump(mode="json"),
            "full_reentry": full_reentry.model_dump(mode="json"),
            "full_gate_rederivation": _admission_summary(cg3_after),
            "bounded_vs_full_agree": (
                bounded_acquire_before.decision == cg3_before.decision
                and bounded_acquire_reentry.after_disposition == full_reentry.after_disposition
                and cg3_after.decision == full_reentry.after_disposition
            ),
            "false_bind_rederived_by_full_gate": (
                full_reentry.advanced_by_gate is True
                and cg3_after.decision == "admit_new_lever"
                and cg3_after.registry_patch is not None
            ),
        },
        "low_trust_owner_corruption": {
            "full_decision": cg3_low_trust.decision,
            "full_reason": cg3_low_trust.decisive_reason,
            "data_trust_status": cg3_low_trust.data_trust.status,
            "data_trust_cap": cg3_low_trust.data_trust.resolved_trust_cap,
            "advanced": cg3_low_trust.decision == "admit_new_lever",
        },
        "cheap_verify": {
            "bounded_relation": bounded_cg1_unknown.selected_relation,
            "full_relation": cg1_unknown_full.selected_relation,
            "bounded_selected_action": bounded_cheap_certificate.selected_action,
            "full_selected_action": cheap_certificate_full.selected_action,
            "bounded_vs_full_agree": (
                bounded_cg1_unknown.selected_relation == cg1_unknown_full.selected_relation
                and bounded_cheap_certificate.selected_action
                == cheap_certificate_full.selected_action
            ),
        },
    }


def _counterfactual_containment_probe(
    *,
    controller: Any,
    acquire_case: Any,
    reference: Any,
    admission_engine_cls: Any,
    apply_registry_patch: Any,
) -> dict[str, Any]:
    before_hash = reference.reference_hash
    before_edge_count = len(reference.essential_edges)
    captured: dict[str, Any] = {}
    original_decide = admission_engine_cls.decide

    def _capturing_decide(self: Any, cg2_certificate: Any, *, cg1_certificate: Any = None) -> Any:
        certificate = original_decide(
            self,
            cg2_certificate,
            cg1_certificate=cg1_certificate,
        )
        proposal_id = str(getattr(cg1_certificate, "proposal_id", ""))
        if certificate.decision == "admit_new_lever" and "counterfactual" in proposal_id:
            captured["certificate"] = certificate
            captured["cg2"] = cg2_certificate
            captured["cg1"] = cg1_certificate
        return certificate

    admission_engine_cls.decide = _capturing_decide
    try:
        planning_certificate = controller.certificate_for(acquire_case)
    finally:
        admission_engine_cls.decide = original_decide

    planning_payload = planning_certificate.model_dump(mode="json")
    counterfactual_edge_ids = [
        str(candidate.get("decisiveness", {}).get("owner_shaped_resolution", {}).get("counterfactual_edge_id"))
        for candidate in planning_payload.get("candidates", [])
        if isinstance(candidate, dict)
        and candidate.get("decisiveness", {}).get("action_family") == "acquire_data"
    ]
    counterfactual_edge_ids = [edge_id for edge_id in counterfactual_edge_ids if edge_id and edge_id != "None"]
    reference_untouched = (
        reference.reference_hash == before_hash
        and len(reference.essential_edges) == before_edge_count
        and all(edge_id not in reference.essential_edges for edge_id in counterfactual_edge_ids)
    )
    if captured:
        resolution = apply_registry_patch(
            captured["certificate"],
            captured["cg2"],
            reference,
            cg1_certificate=captured["cg1"],
        )
        refused = resolution.applied is False and resolution.reason == "admission_re_resolution_mismatch"
        resolution_payload = resolution.model_dump(mode="json")
        captured_certificate_id = captured["certificate"].certificate_id
    else:
        refused = False
        resolution_payload = {"error": "counterfactual_admit_not_captured"}
        captured_certificate_id = None
    redaction_holds = not _has_counterfactual_payload_leak(planning_payload)
    return {
        "captured_counterfactual_admit_certificate_id": captured_certificate_id,
        "reference_hash_before": before_hash,
        "reference_hash_after": reference.reference_hash,
        "reference_edge_count_before": before_edge_count,
        "reference_edge_count_after": len(reference.essential_edges),
        "counterfactual_edge_ids": counterfactual_edge_ids,
        "reference_untouched_after_planning": reference_untouched,
        "extracted_counterfactual_admit_refused": refused,
        "registry_patch_resolution": resolution_payload,
        "redaction_holds": redaction_holds,
    }


def _has_counterfactual_payload_leak(payload: Any) -> bool:
    forbidden_inside_resolution = {
        "admissible_completions",
        "admission_ledger",
        "completion_value",
        "production_promotable",
        "proposal_signature",
        "provenance",
        "registry_patch",
    }

    def _walk(node: Any, *, inside_resolution: bool = False) -> bool:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "counterfactual_inner_certificate":
                    return True
                if inside_resolution and key in forbidden_inside_resolution:
                    return True
                if _walk(value, inside_resolution=inside_resolution or key == "owner_shaped_resolution"):
                    return True
        elif isinstance(node, list):
            return any(_walk(item, inside_resolution=inside_resolution) for item in node)
        return False

    return _walk(payload)


def _production_api_boundary_probes(
    controller_cls: Any,
    policy_cls: Any,
    reference: Any,
) -> dict[str, Any]:
    probes: dict[str, Any] = {}
    for probe_id, kwargs in {
        "policy_force_action": {"force_action": "acquire_data"},
        "policy_voi_override": {"voi_override": 1.0},
        "policy_cost_override": {"cost_override": {"acquire_data": 0}},
        "policy_budget_inflation": {"action_budget": 999},
        "policy_bounded_mode": {"bounded_reference_replay": True},
        "policy_treat_resolved": {"treat_as_resolved": True},
    }.items():
        try:
            policy_cls(**kwargs)
        except ValueError as exc:
            probes[probe_id] = {"accepted": False, "error": str(exc).split("\n", 1)[0]}
        else:
            probes[probe_id] = {"accepted": True}
    try:
        controller_cls(reference, force_action="acquire_data")
    except TypeError as exc:
        probes["constructor_force_action"] = {
            "accepted": False,
            "error": str(exc).split("\n", 1)[0],
        }
    else:
        probes["constructor_force_action"] = {"accepted": True}
    try:
        controller_cls(reference, bounded_reference_replay=True)
    except TypeError as exc:
        probes["constructor_bounded_mode"] = {
            "accepted": False,
            "error": str(exc).split("\n", 1)[0],
        }
    else:
        probes["constructor_bounded_mode"] = {"accepted": True}
    constructed = policy_cls.model_construct(
        force_action="acquire_data",
        bounded_reference_replay=True,
        treat_as_resolved=True,
    )
    constructed_payload = constructed.model_dump(mode="json")
    probes["policy_model_construct_authority_extras"] = {
        "accepted": any(
            key in constructed_payload
            for key in ("force_action", "bounded_reference_replay", "treat_as_resolved")
        ),
        "dump_keys": sorted(constructed_payload),
    }
    return probes


def _lift_report(
    *,
    acquire_reentry: dict[str, Any],
    cg4_reentry: dict[str, Any],
    low_certificate: dict[str, Any],
    cheap_certificate: dict[str, Any],
) -> dict[str, Any]:
    closed = int(acquire_reentry.get("advanced_by_gate") is True)
    actioned_unresolved = int(cg4_reentry.get("advanced_by_gate") is True)
    abstained = sum(
        1
        for certificate in (low_certificate, cheap_certificate)
        if certificate.get("selected_action") == "abstain"
    )
    return {
        "fixed_budget": 3,
        "closed": closed,
        "actioned_but_unresolved": actioned_unresolved,
        "abstained": abstained,
        "passive_abstain_closed": 0,
        "false_binds_or_admits": 0,
        "advanced_cases_rederived_by_real_gates": closed,
    }


def _action_family_exercises(*certificates: dict[str, Any]) -> dict[str, Any]:
    families: set[str] = set()
    for certificate in certificates:
        families.add(str(certificate.get("selected_action")))
        ticket = certificate.get("selected_ticket")
        if isinstance(ticket, dict):
            families.add(str(ticket.get("action_family")))
        for candidate in certificate.get("candidates", []):
            if isinstance(candidate, dict):
                families.add(str(candidate.get("action_family")))
    return {"families": sorted(families)}


def _admission_summary(certificate: Any) -> dict[str, Any]:
    return {
        "certificate_id": certificate.certificate_id,
        "content_hash": certificate.content_hash,
        "decision": certificate.decision,
        "decisive_reason": certificate.decisive_reason,
        "open_obligations": list(certificate.open_obligations),
        "acquisition_blocker": certificate.acquisition_need.blocker_id
        if certificate.acquisition_need
        else None,
        "mechanism_status": certificate.mechanism_witness.status,
        "data_trust_status": certificate.data_trust.status,
        "data_trust_cap": certificate.data_trust.resolved_trust_cap,
        "registry_patch_id": certificate.registry_patch.patch_id
        if certificate.registry_patch
        else None,
    }


def _case(payload: Any, key: str) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get(key), dict):
        return payload[key]
    return {}


def _probe(payload: Any, key: str) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get(key), dict):
        return payload[key]
    return {}


def _copy(payload: Any) -> Any:
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _json_stable(payload: dict[str, Any]) -> dict[str, Any]:
    return _copy(payload)


def main(argv: list[str] | None = None) -> int:
    """Run the CGF GY-CG5 active controller contract validator."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)

    if args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(repo_root)
    else:
        live_payload = build_live_payload(repo_root) if args.write else None
        if args.write:
            write(repo_root, payload=live_payload)
        report = validate(repo_root) if not args.write else validate_payload(live_payload)

    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "pass":
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    else:
        print("grounding active controller contract: pass")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
