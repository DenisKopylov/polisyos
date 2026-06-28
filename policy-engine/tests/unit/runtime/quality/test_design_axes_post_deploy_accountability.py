from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import polisyos.runtime.quality as runtime_quality
from polisyos.pdc import TypedDiagnosticRecord
from polisyos.runtime.quality.calibration_ledger import historical_prior_claim_evidence_issues
from polisyos.runtime.quality.case_lifecycle import validate_ex_post_learning_record

CASE_ID = "ua-msme-affordable-loans-2022"
S13_RULE_VERSION_REF = "policyos.layer2.s13.post_deploy_accountability.v1"
REPO_ROOT = Path(__file__).resolve().parents[4]
S13_FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer2/s13"

S13_REQUIRED_ARTIFACTS = (
    "DeploymentDossier",
    "DivergenceRecord",
    "LearningUpdateProposal",
    "CertifiedEnvelopeDelta",
    "EnvelopeRevision",
    "AssuranceCaseDelta",
    "PostDeployMapeKTrace",
    "PostDeployAccountabilitySummary",
)
S13_REQUIRED_HELPERS = (
    "build_deployment_dossier",
    "classify_post_deploy_divergence",
    "build_post_deploy_mape_k_trace",
    "build_learning_update_proposal",
    "build_certified_envelope_delta",
    "build_assurance_case_delta",
    "build_envelope_revision",
    "verify_post_deploy_learning_authority",
    "summarize_post_deploy_accountability",
    "build_s13_post_deploy_accountability_posture",
)
S13_DENY = (
    "production_rollout_authority",
    "recommendation_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "pre_policy_evidence",
    "current_evidence_slot",
    "preference_learning",
    "automated_value_learning",
    "naive_ml_update",
    "s14_universality",
    "llm_attribution_authority",
    "local_governance_enum_for_reissue",
)
S13_FALSE_CLEAR_FIELDS = (
    "post_policy_data_as_pre_policy_evidence",
    "learned_prior_in_current_evidence_slot",
    "unattributable_updates_model",
    "silent_closed_case_rewrite",
    "learning_without_attribution",
    "envelope_shrink_without_assurance_delta",
    "b_update_before_a_baseline",
    "implementation_failure_as_theory_refutation",
    "outcome_learning_without_counterfactual",
    "s13_as_production_or_recommendation_authority",
)


def _s13() -> Any:
    return importlib.import_module("polisyos.runtime.quality.design_axes.post_deploy_accountability")


def _authority_boundary(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "authoritative_for": [
            "post_deploy_accountability",
            "deployment_monitorability",
            "divergence_attribution",
            "learning_update_proposal",
            "post_deploy_mape_k_trace",
            "envelope_revision",
            "assurance_case_delta",
            "public_accountability_note",
        ],
        "may_not_use_for": list(S13_DENY),
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": [S13_RULE_VERSION_REF],
    }
    payload.update(overrides)
    return payload


def _diagnostic_record(**overrides: object) -> TypedDiagnosticRecord:
    payload: dict[str, object] = {
        "diagnostic_id": "s13-diagnostic-ua-msme-divergence",
        "code": "seeded_disconfirmation_after_deploy",
        "severity": "governance_required",
        "message": "Observed post-deploy divergence requires attributed S13 accountability.",
        "authority_purpose": "post_deploy_accountability_not_claim_authority",
        "owner": "policy-design-accountability-owner",
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return TypedDiagnosticRecord(**payload)


def _deployment_dossier_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": (
            "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
        ),
        "dossier_id": "s13.deployment-dossier.ua-msme",
        "dossier_ref": "pdc://layer2/s13/ua-msme/deployment-dossier",
        "case_id": CASE_ID,
        "deployment_ref": "deployment://ua-msme/credit-guarantee/2022",
        "deployment_time": "2022-03-01T00:00:00+00:00",
        "monitoring_design_ref": "monitoring://ua-msme/outcome-fidelity",
        "implementation_monitoring_evaluation_ref": (
            "ddm://ua-msme/implementation-monitoring-evaluation"
        ),
        "signpost_refs": ["signpost://ua-msme/uptake-drop"],
        "complaint_intake_ref": "intake://ua-msme/complaints",
        "near_miss_intake_ref": "intake://ua-msme/near-misses",
        "attribution_plan_ref": "attribution-plan://ua-msme/post-deploy",
        "reissue_path_ref": "reissue://ua-msme/pdc",
        "rollback_path_ref": "rollback://ua-msme/program",
        "owner": "policy-design-accountability-owner",
        "owner_due_date": "2026-07-01",
        "readiness_disposition": "deployable",
        "monitorability_floor_passed": True,
        "learning_allowed": True,
        "mape_k_trace_ref": "mape-k://ua-msme/deployment-gate",
        "authority_boundary": _authority_boundary(),
        "may_not_use_for": list(S13_DENY),
        "replay_digest": "sha256:" + "d" * 64,
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _divergence_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": (
            "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
        ),
        "divergence_id": "s13.divergence.ua-msme.seeded-disconfirmation",
        "divergence_ref": "pdc://layer2/s13/ua-msme/divergence/seeded-disconfirmation",
        "case_id": CASE_ID,
        "deployment_dossier_ref": "pdc://layer2/s13/ua-msme/deployment-dossier",
        "diagnostic": _diagnostic_record().model_dump(mode="json"),
        "attribution_class": "design_error",
        "attribution_status": "attributed",
        "severity": "block",
        "failed_axis": "DESIGNER_ITSELF.envelope_growth",
        "failed_firewall": "a_before_b_sequence",
        "evidence_refs": ["post-policy-observation://ua-msme/default-rate-2023"],
        "attribution_owner": "policy-design-accountability-owner",
        "allowed_moves": ["envelope_shrink", "reissue_required", "public_accountability_note"],
        "learning_eligible": True,
        "authority_boundary": _authority_boundary(),
        "replay_refs": ["replay://ua-msme/s13/a-before-b"],
        "a_repair_required_before_b_learning": False,
        "action_item_owner": "policy-design-accountability-owner",
        "action_item_due_date": "2026-07-01",
        "action_item_status": "closed",
        "action_item_closure_ref": "closure://ua-msme/s13/action-item/001",
        "human_review_ref": "human-review://ua-msme/approval/001",
        "oversight_effectiveness_ref": "oversight://ua-msme/effectiveness/001",
        "effective_oversight": False,
        "rubber_stamp_risk": "high",
        "oversight_accountability_state": "rubber_stamp_divergence_review_required",
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _mape_k_trace_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": (
            "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
        ),
        "trace_id": "s13.mape-k.ua-msme",
        "trace_ref": "mape-k://ua-msme/post-deploy",
        "case_id": CASE_ID,
        "monitor_refs": [
            "outcome://ua-msme/default-rate-2023",
            "implementation-fidelity://ua-msme/lender-routing",
        ],
        "analyze_refs": ["pdc://layer2/s13/ua-msme/divergence/seeded-disconfirmation"],
        "plan_refs": ["learning-proposal://ua-msme/envelope-shrink"],
        "execute_refs": ["governance-decision://ua-msme/reissue"],
        "knowledge_refs": [
            "historical-prior-influence:ua-msme/default-risk-route",
            "envelope-revision://ua-msme/shrink/001",
        ],
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _ex_post_learning_record(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "policyos.runtime.policy_design_case.ex_post_learning.v1",
        "record_id": "s13-ex-post-learning-ua-msme",
        "case_id": CASE_ID,
        "claim_prediction_links": [
            {
                "link_id": "outcome-link-rec-1",
                "claim_id": "rec_1",
                "prediction_ref": "prediction-rec-1",
                "observed_outcome_ref": "observed-outcome-rec-1",
                "reassessment_ref": "reassessment-rec-1",
                "reassessment_status": "confirmed",
                "future_method_prior_ref": "future-prior-rec-1",
                "future_uncertainty_prior_ref": "future-prior-rec-1",
                "evidence_ref": "sha256:" + "a" * 64,
                "runtime_event_ref": "event://policy-design-case/ex-post/outcome-link",
            }
        ],
        "calibration": {
            "calibration_report_refs": ["sha256:" + "b" * 64],
            "backtesting_report_refs": ["sha256:" + "c" * 64],
            "calibration_leaderboard_ref": "sha256:" + "d" * 64,
            "track_record_ref": "sha256:" + "e" * 64,
        },
        "memory_contamination_check": {
            "status": "clean",
            "policy": {"hidden_ref_ids": [], "hidden_suite_ids": [], "canary_tokens": []},
            "findings": [],
            "evidence_ref": "sha256:" + "f" * 64,
            "runtime_event_ref": "event://policy-design-case/ex-post/memory-clean",
        },
        "learning_records": [
            {
                "learning_id": "learning-rec-1",
                "scope": "wartime_msme_support",
                "applicability": ["UA", "production_msme_panel"],
                "revocation_conditions": ["new legal regime", "data schema change"],
                "memory_contamination_controls": ["hidden_eval_scan_clean"],
                "evidence_ref": "sha256:" + "0" * 64,
            }
        ],
        "evidence_ref": "sha256:" + "1" * 64,
        "runtime_event_ref": "event://policy-design-case/ex-post",
    }
    payload.update(overrides)
    return payload


def _learning_proposal_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": (
            "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
        ),
        "proposal_id": "s13.learning-proposal.ua-msme.envelope-shrink",
        "proposal_ref": "learning-proposal://ua-msme/envelope-shrink",
        "case_id": CASE_ID,
        "divergence_record_ref": (
            "pdc://layer2/s13/ua-msme/divergence/seeded-disconfirmation"
        ),
        "ex_post_learning_record": _ex_post_learning_record(),
        "attribution_class": "design_error",
        "attribution_status": "attributed",
        "change_control_class": "reissue_required",
        "learning_update_target": "envelope",
        "learning_allowed": True,
        "a_before_b_status": "pass",
        "deployment_baseline_ref": "baseline://ua-msme/pre-policy",
        "post_deploy_signal_refs": ["post-policy-observation://ua-msme/default-rate-2023"],
        "governance_decision_class_ref": "GovernanceDecisionClass.reissue_required",
        "human_decision_request_refs": ["human-decision-request://ua-msme/s13/reissue"],
        "human_decision_record_refs": ["human-decision-record://ua-msme/s13/reissue"],
        "historical_prior_influence_refs": [
            "historical-prior-influence:ua-msme/default-risk-route"
        ],
        "historical_prior_provenance_ref": "provenance://ua-msme/s13/learning",
        "historical_prior_ttl": "P180D",
        "historical_prior_decay": "linear",
        "contamination_control_refs": ["memory-contamination-check://ua-msme/s13/clean"],
        "lifecycle_reissue_disposition": "reissue_required",
        "assurance_case_delta_ref": "assurance-delta://ua-msme/s13/weakened",
        "public_accountability_note_ref": "public-note://ua-msme/s13/accountability",
        "authority_boundary": _authority_boundary(),
        "may_not_use_for": list(S13_DENY),
        "replay_digest": "sha256:" + "e" * 64,
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _assurance_case_delta_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": (
            "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
        ),
        "delta_id": "s13.assurance-delta.ua-msme.weakened",
        "delta_ref": "assurance-delta://ua-msme/s13/weakened",
        "case_id": CASE_ID,
        "assurance_case_change": "weakened",
        "affected_claim_refs": ["claim://ua-msme/default-risk"],
        "unaffected_claim_refs": ["claim://ua-msme/legal-authority"],
        "public_revision_state_ref": "public-revision-state://ua-msme/s13/001",
        "closed_case_historical_meaning": "preserved",
        "silent_upgrade_allowed": False,
        "authority_boundary": _authority_boundary(),
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _certified_envelope_delta_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": (
            "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
        ),
        "delta_id": "s13.certified-envelope-delta.ua-msme.s12-growth",
        "delta_ref": "certified-envelope-delta://ua-msme/s12-growth",
        "case_id": CASE_ID,
        "s12_certified_envelope_delta_ref": "delta://layer2/open-cell-count/1-to-0",
        "materialized_from_s12_growth_entry_ref": (
            "pdc://layer2/s12/ua-msme/growth-entry/001"
        ),
        "direction": "expand",
        "certified_scope_refs": ["facet://actor", "facet://instrument"],
        "authority_boundary": _authority_boundary(),
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _envelope_revision_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": (
            "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
        ),
        "revision_id": "s13.envelope-revision.ua-msme.shrink",
        "revision_ref": "envelope-revision://ua-msme/shrink/001",
        "case_id": CASE_ID,
        "direction": "shrink",
        "reason": "Seeded disconfirmation invalidates part of the certified scope.",
        "divergence_record_ref": (
            "pdc://layer2/s13/ua-msme/divergence/seeded-disconfirmation"
        ),
        "learning_update_proposal_ref": "learning-proposal://ua-msme/envelope-shrink",
        "assurance_case_delta_ref": "assurance-delta://ua-msme/s13/weakened",
        "certified_envelope_delta_ref": None,
        "disconfirming_signal_time": "2023-05-01T00:00:00+00:00",
        "revision_effective_time": "2023-06-01T00:00:00+00:00",
        "shrink_latency_days": 31,
        "authority_boundary": _authority_boundary(),
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _summary_payload(**overrides: object) -> dict[str, object]:
    false_clear_counts = dict.fromkeys(S13_FALSE_CLEAR_FIELDS, 0)
    payload: dict[str, object] = {
        "schema_version": (
            "policyos.policy_design_case.layer2_s13_post_deploy_accountability.v1"
        ),
        "summary_id": "s13.summary.ua-msme",
        "slice": "S13",
        "cells_closed": [],
        "layer_cells_advanced": ["DESIGNER_ITSELF.envelope_growth"],
        "current_open_cell_count": 0,
        "case_count": 13,
        "monitorability_rate": 1.0,
        "a_before_b_ratio": 1.0,
        "attribution_resolution_rate": 1.0,
        "envelope_shrink_count": 1,
        "envelope_expansion_count": 1,
        "envelope_shrink_latency_recorded_count": 1,
        "unattributable_accountability_without_training_count": 1,
        "mape_k_trace_completeness_rate": 1.0,
        "action_item_closure_rate": 1.0,
        "oversight_effectiveness_link_rate": 1.0,
        "rubber_stamp_divergence_review_required_count": 1,
        "learning_without_attribution_count": 0,
        "growth_without_assurance_delta_count": 0,
        "false_clear_counts": false_clear_counts,
        "authority_boundary": _authority_boundary(),
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    for field in S13_FALSE_CLEAR_FIELDS:
        payload[f"{field}_false_clear_count"] = 0
    payload.update(overrides)
    return payload


def test_s13_contracts_are_strict_replayable_and_exported() -> None:
    module = _s13()

    assert module.LAYER2_S13_POST_DEPLOY_ACCOUNTABILITY_RULE_VERSION == S13_RULE_VERSION_REF
    assert tuple(module.S13_FALSE_CLEAR_FIELDS) == S13_FALSE_CLEAR_FIELDS
    for name in S13_REQUIRED_ARTIFACTS:
        model = getattr(module, name)
        assert model.model_config.get("extra") == "forbid", name
        assert getattr(runtime_quality, name) is model
    for helper_name in S13_REQUIRED_HELPERS:
        assert getattr(runtime_quality, helper_name) is getattr(module, helper_name)

    dossier = module.build_deployment_dossier(**_deployment_dossier_payload())
    repeated = module.build_deployment_dossier(**_deployment_dossier_payload())
    assert dossier.replay_digest == repeated.replay_digest

    with pytest.raises(ValidationError):
        module.DeploymentDossier.model_validate(
            {**_deployment_dossier_payload(), "unexpected_authority": "production"}
        )


def test_deployment_dossier_requires_monitoring_design_before_deployable() -> None:
    module = _s13()

    with pytest.raises(ValidationError, match="monitoring_design"):
        module.DeploymentDossier.model_validate(
            _deployment_dossier_payload(monitoring_design_ref=None)
        )


def test_monitorability_floor_allows_accountability_only_without_learning() -> None:
    module = _s13()

    dossier = module.DeploymentDossier.model_validate(
        _deployment_dossier_payload(
            readiness_disposition="accountability_only",
            learning_allowed=False,
            attribution_plan_ref=None,
        )
    )

    assert dossier.readiness_disposition == "accountability_only"
    assert dossier.monitorability_floor_passed is True
    assert dossier.learning_allowed is False


def test_divergence_record_requires_attribution_before_learning() -> None:
    module = _s13()

    with pytest.raises(ValidationError, match="attribution"):
        module.DivergenceRecord.model_validate(
            _divergence_payload(attribution_status="pending", learning_eligible=True)
        )


def test_divergence_record_composes_typed_diagnostic_record() -> None:
    module = _s13()

    record = module.DivergenceRecord.model_validate(_divergence_payload())

    assert isinstance(record.diagnostic, TypedDiagnosticRecord)
    assert record.diagnostic.code == "seeded_disconfirmation_after_deploy"


def test_unattributable_divergence_records_accountability_without_training() -> None:
    module = _s13()

    record = module.classify_post_deploy_divergence(
        **_divergence_payload(
            attribution_class="unattributable",
            attribution_status="unattributable",
            learning_eligible=False,
            allowed_moves=["public_accountability_note"],
        )
    )

    assert record.attribution_status == "unattributable"
    assert record.learning_eligible is False
    assert "public_accountability_note" in record.allowed_moves


def test_design_error_after_rubber_stamp_review_marks_oversight_accountability_state() -> None:
    module = _s13()

    record = module.classify_post_deploy_divergence(**_divergence_payload())

    assert record.oversight_accountability_state == (
        "rubber_stamp_divergence_review_required"
    )


def test_mape_k_trace_requires_monitor_analyze_plan_execute_knowledge_refs() -> None:
    module = _s13()

    trace = module.PostDeployMapeKTrace.model_validate(_mape_k_trace_payload())
    assert trace.monitor_refs
    assert trace.analyze_refs
    assert trace.plan_refs
    assert trace.execute_refs
    assert trace.knowledge_refs

    with pytest.raises(ValidationError, match="knowledge"):
        module.PostDeployMapeKTrace.model_validate(_mape_k_trace_payload(knowledge_refs=[]))


def test_learning_update_proposal_enforces_a_before_b_sequence() -> None:
    module = _s13()

    with pytest.raises(ValidationError, match=r"A-before-B|a_before_b"):
        module.LearningUpdateProposal.model_validate(
            _learning_proposal_payload(a_before_b_status="fail")
        )


def test_learning_update_proposal_wraps_validated_ex_post_learning_record() -> None:
    module = _s13()
    ex_post_record = validate_ex_post_learning_record(_ex_post_learning_record())

    proposal = module.build_learning_update_proposal(
        **_learning_proposal_payload(ex_post_learning_record=ex_post_record)
    )

    assert proposal.ex_post_learning_record["record_id"] == ex_post_record["record_id"]
    assert proposal.ex_post_learning_record["learning_records"]


def test_learning_update_proposal_rejects_contaminated_ex_post_learning_record() -> None:
    module = _s13()
    contaminated = _ex_post_learning_record()
    contaminated["memory_contamination_check"] = {
        "status": "clean",
        "policy": {"hidden_ref_ids": ["hidden_eval_42"], "hidden_suite_ids": [], "canary_tokens": []},
        "findings": [],
        "evidence_ref": "sha256:" + "f" * 64,
        "runtime_event_ref": "event://policy-design-case/ex-post/memory-clean",
    }
    contaminated["learning_records"] = [
        {
            "learning_id": "learning-rec-contaminated",
            "scope": "hidden_eval_42 leakage",
            "applicability": ["UA"],
            "revocation_conditions": ["new legal regime"],
            "memory_contamination_controls": ["hidden_eval_scan_clean"],
            "evidence_ref": "sha256:" + "9" * 64,
        }
    ]

    with pytest.raises((ValidationError, ValueError), match=r"contamination|hidden_eval_42"):
        module.LearningUpdateProposal.model_validate(
            _learning_proposal_payload(ex_post_learning_record=contaminated)
        )


def test_learning_update_targets_component_with_attribution_and_governance() -> None:
    module = _s13()

    proposal = module.LearningUpdateProposal.model_validate(_learning_proposal_payload())

    assert proposal.learning_update_target == "envelope"
    assert proposal.attribution_status == "attributed"
    assert proposal.human_decision_record_refs


def test_reissue_change_control_maps_to_existing_lifecycle_reissue_status() -> None:
    module = _s13()

    proposal = module.LearningUpdateProposal.model_validate(_learning_proposal_payload())

    assert proposal.change_control_class == "reissue_required"
    assert proposal.lifecycle_reissue_disposition in {
        "fail",
        "withdraw_required",
        "supersede_required",
        "reissue_required",
        "review_required",
        "pass",
    }


def test_historical_prior_influence_requires_ttl_decay_and_contamination_controls() -> None:
    module = _s13()

    proposal = module.LearningUpdateProposal.model_validate(_learning_proposal_payload())
    assert proposal.historical_prior_influence_refs[0].startswith(
        "historical-prior-influence:"
    )
    assert proposal.historical_prior_ttl
    assert proposal.historical_prior_decay
    assert proposal.contamination_control_refs

    with pytest.raises(ValidationError, match=r"ttl|decay|contamination"):
        module.LearningUpdateProposal.model_validate(
            _learning_proposal_payload(
                historical_prior_ttl=None,
                historical_prior_decay=None,
                contamination_control_refs=[],
            )
        )


def test_envelope_revision_can_shrink_on_seeded_disconfirmation() -> None:
    module = _s13()

    revision = module.build_envelope_revision(**_envelope_revision_payload())

    assert revision.direction == "shrink"
    assert revision.shrink_latency_days >= 1
    assert revision.assurance_case_delta_ref


def test_envelope_revision_can_expand_on_validated_reusable_learning() -> None:
    module = _s13()

    revision = module.build_envelope_revision(
        **_envelope_revision_payload(
            revision_id="s13.envelope-revision.ua-msme.expand",
            revision_ref="envelope-revision://ua-msme/expand/001",
            direction="expand",
            reason="Validated reusable learning expands future envelope scope.",
            certified_envelope_delta_ref="certified-envelope-delta://ua-msme/s12-growth",
            disconfirming_signal_time=None,
            revision_effective_time="2023-06-01T00:00:00+00:00",
            shrink_latency_days=None,
            assurance_case_delta_ref="assurance-delta://ua-msme/s13/strengthened",
        )
    )

    assert revision.direction == "expand"
    assert revision.certified_envelope_delta_ref


def test_certified_envelope_delta_materializes_s12_deferred_delta_ref() -> None:
    module = _s13()

    delta = module.build_certified_envelope_delta(**_certified_envelope_delta_payload())

    assert delta.s12_certified_envelope_delta_ref == "delta://layer2/open-cell-count/1-to-0"
    assert delta.materialized_from_s12_growth_entry_ref.endswith("/growth-entry/001")
    assert delta.direction == "expand"


def test_envelope_shrink_split_gated_by_assurance_delta_and_latency_not_s12_growth_entry() -> None:
    module = _s13()

    with pytest.raises(ValidationError, match=r"assurance|latency"):
        module.EnvelopeRevision.model_validate(
            _envelope_revision_payload(
                direction="split",
                assurance_case_delta_ref=None,
                shrink_latency_days=None,
                certified_envelope_delta_ref="delta://layer2/open-cell-count/1-to-0",
            )
        )


def test_assurance_case_delta_required_for_learning_update() -> None:
    module = _s13()

    with pytest.raises(ValidationError, match="assurance"):
        module.LearningUpdateProposal.model_validate(
            _learning_proposal_payload(assurance_case_delta_ref=None)
        )


def test_action_item_closure_rate_counts_owned_deadline_closure() -> None:
    module = _s13()

    summary = module.summarize_post_deploy_accountability(
        dossiers=[_deployment_dossier_payload()],
        divergences=[_divergence_payload()],
        learning_update_proposals=[_learning_proposal_payload()],
        envelope_revisions=[_envelope_revision_payload()],
        assurance_case_deltas=[_assurance_case_delta_payload()],
        certified_envelope_deltas=[_certified_envelope_delta_payload()],
    )

    assert summary.action_item_closure_rate == 1.0


def test_high_stakes_reissue_requires_human_decision_record_ref() -> None:
    module = _s13()

    with pytest.raises(ValidationError, match=r"HumanDecisionRecord|human_decision_record"):
        module.LearningUpdateProposal.model_validate(
            _learning_proposal_payload(
                human_decision_record_refs=[],
                change_control_class="reissue_required",
            )
        )


def test_post_policy_data_cannot_fill_pre_policy_evidence_slot() -> None:
    module = _s13()
    probe = json.loads(
        (
            S13_FIXTURE_DIR
            / "negative_controls/post_policy_data_as_pre_policy_evidence_probe.json"
        ).read_text(encoding="utf-8")
    )

    issues = module.verify_post_deploy_learning_authority(probe)

    assert "post_policy_data_as_pre_policy_evidence" in issues


def test_learned_prior_cannot_be_current_evidence() -> None:
    module = _s13()

    issues = module.verify_post_deploy_learning_authority(
        {
            "claim_id": "rec_1",
            "current_evidence_refs": [
                "historical-prior-influence:ua-msme/default-risk-route"
            ],
        }
    )

    assert "learned_prior_in_current_evidence_slot" in issues


def test_learned_prior_firewall_rejects_prefixed_historical_prior_refs_in_evidence_slots() -> None:
    row = {
        "claim_id": "rec_1",
        "data_refs": ["historical-prior-influence:ua-msme/default-risk-route"],
    }

    issues = historical_prior_claim_evidence_issues(row, claim_id="rec_1")

    assert issues
    assert issues[0]["code"] == "historical_prior_ref_not_admissible_as_claim_evidence"


def test_implementation_failure_does_not_refute_policy_theory() -> None:
    module = _s13()

    record = module.classify_post_deploy_divergence(
        **_divergence_payload(
            attribution_class="implementation_failure",
            allowed_moves=["capacity_repair", "public_accountability_note"],
            learning_eligible=False,
        )
    )

    assert record.policy_theory_refuted is False
    assert record.learning_eligible is False


def test_s13_summary_requires_exact_false_clear_keys() -> None:
    module = _s13()

    summary = module.PostDeployAccountabilitySummary.model_validate(_summary_payload())

    assert tuple(summary.false_clear_counts) == S13_FALSE_CLEAR_FIELDS
    assert all(count == 0 for count in summary.false_clear_counts.values())

    with pytest.raises(ValidationError, match="false_clear"):
        module.PostDeployAccountabilitySummary.model_validate(
            _summary_payload(false_clear_counts={"unexpected": 0})
        )


def test_no_preference_learning_or_production_authority_from_s13() -> None:
    module = _s13()

    issues = module.verify_post_deploy_learning_authority(
        {
            "authority_boundary": _authority_boundary(
                authoritative_for=["production_rollout_authority", "preference_learning"]
            ),
            "may_not_use_for": ["publication_authority"],
        }
    )

    assert "s13_as_production_or_recommendation_authority" in issues
    assert "preference_learning" in S13_DENY
