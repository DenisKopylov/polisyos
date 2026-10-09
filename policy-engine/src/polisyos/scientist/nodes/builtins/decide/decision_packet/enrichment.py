"""Decision-packet enrichment section builders."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionTriggerSpec,
    DecisionTriggerType,
)
from polisyos.core.contracts.distributional import DistributionalReportRef
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import SimulationResult
from polisyos.core.contracts.scholar import FreshnessMetadata
from polisyos.core.contracts.scientist import (
    DecisionMonitoringContractRef,
)
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef
from polisyos.ir.analytics.abm_bridge import load_abm_alignment_report
from polisyos.ir.analytics.abstraction import load_abstraction_certificate
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.causal_ensemble import load_causal_model_ensemble
from polisyos.ir.analytics.distributional import (
    load_distributional_effect_bundle,
    load_distributional_report,
    load_ordinal_poverty_report,
)
from polisyos.ir.analytics.evidence_bundle import load_causal_evidence_bundle
from polisyos.ir.analytics.hte import load_hte_result, load_policy_recommendation
from polisyos.ir.analytics.kernel_causal import load_kernel_estimator_spec
from polisyos.ir.analytics.metric_validation_report import (
    MetricValidationReport,
)
from polisyos.ir.analytics.normative_arbitration import (
    NormativeArbitrationResult,
    load_normative_arbitration_result,
)
from polisyos.ir.analytics.partial_identification import load_bounds_bundle
from polisyos.ir.analytics.sensitivity import (
    load_sensitivity_result,
    persist_sensitivity_analysis_bundle,
    sensitivity_analysis_bundle_from_result,
)
from polisyos.ir.analytics.strategic import (
    load_mean_field_equilibrium_certificate,
    load_mean_field_macro_simulation_config,
    load_mean_field_perturbation_spec,
    load_performative_shift_summary,
    load_post_adaptation_policy_value_summary,
    load_strategic_decomposition_failure_card,
    load_strategic_response_bundle,
    load_strategic_scm,
)
from polisyos.ir.analytics.uncertainty import (
    load_simulation_result_uncertainty_admission,
    load_uncertainty_envelope,
)
from polisyos.ir.analytics.welfare import (
    load_channel_decomposition_artifact,
    load_welfare_bundle,
)
from polisyos.ir.artifacts import normalize_artifact_ref
from polisyos.ir.registry.refs import (
    ABMAlignmentReportRef,
    AbstractionCertificateRef,
    CausalModelEnsembleRef,
    CausalSensitivityResultRef,
    DistributionalEffectBundleRef,
    EvidenceBundleRef,
    KernelEstimatorSpecRef,
    NormativeArbitrationResultRef,
    StrategicResponseBundleRef,
    StrategicSCMRef,
    WelfareBundleRef,
)
from polisyos.scholar.search.models import WebEvidenceBundle
from polisyos.scientist.evidence.claims.head_index import (
    ClaimLedgerIssuanceNonReceipt,
    PreparedClaimLedgerInitialization,
)
from polisyos.scientist.evidence.claims.lifecycle import CLAIM_LEDGER_V2_FLAG
from polisyos.scientist.evidence.claims.projections import project_decision_packet_claims
from polisyos.scientist.evidence.claims.readiness import summarize_ledger_readiness
from polisyos.scientist.evidence.claims.validators import (
    is_claim_spine_enabled,
    is_feature_enabled,
)
from polisyos.scientist.evidence.safe_fetch import neutralize_instruction_markers
from polisyos.scientist.feedback.core import (
    DecisionFeedbackService,
    build_monitoring_contract_from_packet,
)
from polisyos.scientist.governance.continuous.reports import load_validity_report
from polisyos.scientist.governance.human_review.decisions import load_review_decision
from polisyos.scientist.governance.human_review.oversight_policy import (
    evaluate_human_review_requirement,
    human_review_section,
    validate_human_reviewed_readiness,
)
from polisyos.scientist.governance.human_review.packets import load_review_packet
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.search.voi_scheduler import load_voi_run_report
from polisyos.scientist.nodes.builtins.decide._decision_packet_contracts import (
    _ClaimLedgerAttachment,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.basis_sections import (
    _build_aux_artifact_section,
    _build_data_basis,
    _build_diagnostics_summary,
    _build_knowledge_basis,
    _build_normative_basis,
    _build_sensitivity_section,
    _build_transportability_basis,
    _build_watched_triggers,
    _load_normative_arbitration,
    _load_normative_frame_payload,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.causal_sections import (
    _build_causal_section,
    _build_transportability_summary,
    _merge_dp_summary_into_causal_payload,
    _normalize_dp_summary,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.outcome_sections import (
    _build_abm_alignment_section,
    _build_abstraction_section,
    _build_backtest_section,
    _build_calibration_validation_section,
    _build_distributional_section,
    _build_econometrics_section,
    _build_feedback_loop,
    _build_hte_section,
    _build_phase3_section,
    _build_targeting_section,
    _build_tradeoff_certificate_section,
    _build_welfare_section,
    _parse_anchor_at,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.serialization import (
    _claim_source_artifact_refs,
    _dedupe_dependency_refs,
    _dependency_ref,
    _load_json_payload_by_ref,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.strategic_sections import (
    _build_strategic_section,
    _performative_loop_payload,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.uncertainty_sections import (
    _build_uncertainty_bounds,
    _build_uncertainty_section,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _DECISION_PACKET_LOAD_ERRORS,
    _collect_contract_warnings,
    _decision_packet_degraded,
    _has_governance_issue_code,
    _load_resolved_fidelity_level,
    _nested_status,
    _record_decision_packet_section_degraded,
    _summarize_governance_issues,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet_support import (
    _path_get,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_BACKTEST_REPORT_REF,
    ARTIFACT_BOUNDS_BUNDLE_REF,
    ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_CLAIM_LEDGER_V2_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
    ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ARTIFACT_ECONOMETRIC_RESULT_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_HUMAN_REVIEW_DECISION_REF,
    ARTIFACT_HUMAN_REVIEW_PACKET_REF,
    ARTIFACT_INPUT_BINDING_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_REISSUE_PACKET_REF,
    ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    ARTIFACT_VOI_RUN_REPORT_REF,
    ARTIFACT_WEB_EVIDENCE_BUNDLE_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    ARTIFACT_WITHDRAWAL_RECORD_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_NORM_PACK_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_LEGAL_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import (
    ClaimCapableExecutionContext,
    ExecutionContext,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.phase3 import resolve_phase3_gate

logger = get_logger(__name__)

_TEST_LABELS: dict[str, str] = {
    "delong_auc": "DeLong AUC",
    "mcnemar_exact": "McNemar exact",
    "mcnemar_chi2": "McNemar chi-square",
    "paired_t": "Paired t-test",
    "wilcoxon_signed_rank": "Wilcoxon signed-rank",
    "paired_permutation": "Paired permutation",
    "paired_bootstrap_bca": "Paired bootstrap",
}


def _describe_test_id(test_id: str) -> str:
    return _TEST_LABELS.get(test_id, test_id.replace("_", " ").title())


def _attach_human_review_projection(
    ctx: ExecutionContext,
    state: ExperimentState,
    packet_payload: dict[str, object],
    *,
    governance_report: GovernanceReport | None = None,
):
    """Attach Phase 1.6 human-review status and validate release claims."""

    review_packet_ref = state.artifacts_index.get(ARTIFACT_HUMAN_REVIEW_PACKET_REF)
    review_decision_ref = state.artifacts_index.get(ARTIFACT_HUMAN_REVIEW_DECISION_REF)
    review_packet = None
    review_decisions = None
    if review_packet_ref is not None:
        try:
            review_packet = load_review_packet(ctx.store, review_packet_ref)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_human_review_packet",
                reason="human_review_packet_load_failed",
                exc=exc,
                ref=review_packet_ref,
                artifact_key=ARTIFACT_HUMAN_REVIEW_PACKET_REF,
            )
    if review_decision_ref is not None:
        try:
            review_decisions = [load_review_decision(ctx.store, review_decision_ref)]
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            review_decisions = []
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_human_review_decision",
                reason="human_review_decision_load_failed",
                exc=exc,
                ref=review_decision_ref,
                artifact_key=ARTIFACT_HUMAN_REVIEW_DECISION_REF,
            )
    requirement = evaluate_human_review_requirement(
        params=state.params,
        governance_report=governance_report,
        packet_payload=packet_payload,
    )
    packet_payload["human_review"] = human_review_section(
        requirement=requirement,
        review_packet_ref=review_packet_ref,
        review_decision_ref=review_decision_ref,
        decisions=review_decisions,
        packet=review_packet,
    )
    validation = validate_human_reviewed_readiness(
        packet_payload,
        review_packet_ref=review_packet_ref,
        review_decision_ref=review_decision_ref,
        decisions=review_decisions,
        packet=review_packet,
        requirement=requirement,
    )
    packet_payload["human_review_validation"] = validation.model_dump(mode="json")
    artifacts = packet_payload.get("artifacts")
    if isinstance(artifacts, dict):
        if review_packet_ref is not None:
            artifacts[ARTIFACT_HUMAN_REVIEW_PACKET_REF] = str(review_packet_ref.artifact_id)
        if review_decision_ref is not None:
            artifacts[ARTIFACT_HUMAN_REVIEW_DECISION_REF] = str(review_decision_ref.artifact_id)
    return validation


def _attach_claim_ledger_to_packet(
    ctx: ExecutionContext,
    state: ExperimentState,
    packet_payload: dict[str, object],
) -> _ClaimLedgerAttachment:
    """Persist and attach the Phase 1.1 claim ledger sidecar for a packet."""

    if not is_claim_spine_enabled(state.params):
        packet_payload["claim_ledger_status"] = "disabled"
        return _ClaimLedgerAttachment()

    source_refs = _claim_source_artifact_refs(state)
    decision_readiness_ref = state.artifacts_index.get(ARTIFACT_DECISION_READINESS_CONTRACT_REF)
    ledger = project_decision_packet_claims(
        packet_payload,
        run_id=state.run_id,
        source_artifact_refs=source_refs,
        decision_readiness_ref=decision_readiness_ref,
    )
    if not isinstance(ctx, ClaimCapableExecutionContext):
        packet_payload["claim_readiness_summary"] = summarize_ledger_readiness(ledger)
        packet_payload["claim_ledger_status"] = "not_established"
        packet_payload["claim_ledger_limitation_code"] = "claim_ledger_owner_not_established"
        return _ClaimLedgerAttachment(
            authority_status="not_established",
            limitation_code="claim_ledger_owner_not_established",
        )

    claim_owner = ctx.claim_ledger_owner
    claims_ref = claim_owner.persist_candidate_ledger(
        ledger=ledger,
        inputs=tuple(
            InputRef(artifact_id=ref.artifact_id, role=f"claim_source[{index}]")
            for index, ref in enumerate(source_refs)
        ),
    )
    packet_payload["claims_ref"] = str(claims_ref.artifact_id)
    artifacts = packet_payload.get("artifacts")
    if isinstance(artifacts, dict):
        artifacts[ARTIFACT_CLAIMS_REF] = str(claims_ref.artifact_id)
    candidate_projection = claim_owner.project_candidate_ledger(ledger=ledger)
    packet_payload["claim_readiness_summary"] = summarize_ledger_readiness(ledger)
    packet_payload["claim_ledger_summary"] = candidate_projection.ledger_summary
    packet_payload["blocked_claim_summary"] = candidate_projection.blocked_summary
    if not is_feature_enabled(state.params, CLAIM_LEDGER_V2_FLAG, default=False):
        packet_payload["claim_ledger_status"] = "not_established"
        packet_payload["claim_ledger_limitation_code"] = "claim_root_issuance_not_established"
        return _ClaimLedgerAttachment(
            claims_ref=claims_ref,
            authority_status="not_established",
            limitation_code="claim_root_issuance_not_established",
        )

    prepared = claim_owner.prepare_initial_ledger(
        base_claims_ref=claims_ref,
        source_artifact_refs=source_refs,
    )
    if isinstance(prepared, ClaimLedgerIssuanceNonReceipt):
        packet_payload["claim_ledger_status"] = "not_established"
        packet_payload["claim_ledger_limitation_code"] = prepared.code
        return _ClaimLedgerAttachment(
            claims_ref=claims_ref,
            authority_status="not_established",
            limitation_code=prepared.code,
        )
    if not isinstance(prepared, PreparedClaimLedgerInitialization):
        raise ValueError("claim_root_preparation_result_invalid")
    claim_ledger_v2_ref = prepared.initial_ledger_ref
    packet_payload["claim_ledger_v2_ref"] = str(claim_ledger_v2_ref.artifact_id)
    packet_payload["claim_ledger_status"] = "prepared_not_current"
    if isinstance(artifacts, dict):
        if claim_ledger_v2_ref is not None:
            artifacts[ARTIFACT_CLAIM_LEDGER_V2_REF] = str(claim_ledger_v2_ref.artifact_id)
    return _ClaimLedgerAttachment(
        claims_ref=claims_ref,
        claim_ledger_v2_ref=claim_ledger_v2_ref,
        preparation=prepared,
        authority_status="prepared",
    )


def _build_runtime_contracts_section(state: ExperimentState) -> dict[str, object]:
    return {
        "execution_profile": state.execution_profile,
        "capability_manifest_ref": (
            str(state.capability_manifest_ref.artifact_id)
            if state.capability_manifest_ref is not None
            else None
        ),
    }


def _build_web_evidence_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    ref = artifacts_index.get(ARTIFACT_WEB_EVIDENCE_BUNDLE_REF)
    if ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(ref))
        bundle = WebEvidenceBundle.model_validate(payload)
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_web_evidence_bundle",
            reason="web_evidence_bundle_load_failed",
            exc=exc,
            ref=ref,
            artifact_key=ARTIFACT_WEB_EVIDENCE_BUNDLE_REF,
        )
        return {
            "status": "parse_failed",
            "web_evidence_bundle_ref": str(ref.artifact_id),
        }

    source_title_by_id = {
        source.source_id: source.title or source.domain for source in bundle.sources
    }
    return {
        "status": "available",
        "web_evidence_bundle_ref": str(ref.artifact_id),
        "bundle_id": bundle.bundle_id,
        "source_count": len(bundle.sources),
        "snippet_count": len(bundle.snippets),
        "claim_support_count": len(bundle.claim_supports),
        "fetch_safety_events": [
            event.model_dump(mode="json", exclude_none=True)
            for event in bundle.fetch_safety_events[:20]
        ],
        "source_quality_signals": [
            signal.model_dump(mode="json", exclude_none=True)
            for signal in bundle.source_quality_signals[:50]
        ],
        "claim_supports": [
            {
                "claim_id": support.claim_id,
                "claim_id_namespace": support.metadata.get(
                    "claim_id_namespace",
                    "legacy_local",
                ),
                "support_status": support.metadata.get("support_status"),
                "support_score": support.support_score,
                "conflict_score": support.conflict_score,
                "snippet_ids": list(support.snippet_ids),
                "source_ids": list(support.source_ids),
                "uncertainty_note": support.uncertainty_note,
            }
            for support in bundle.claim_supports[:50]
        ],
        "snippets": [
            {
                "snippet_id": snippet.snippet_id,
                "source_id": snippet.source_id,
                "source_title": source_title_by_id.get(snippet.source_id),
                "url": str(snippet.url),
                "start_char": snippet.start_char,
                "end_char": snippet.end_char,
                "text": neutralize_instruction_markers(snippet.text.replace("\n", " ").strip())[
                    :600
                ],
                "untrusted_evidence_text": True,
            }
            for snippet in bundle.snippets[:50]
        ],
        "uncertainty_notes": list(bundle.uncertainty_notes),
    }


def _build_voi_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    """Attach a compact VOI report projection without making it a release gate."""

    ref = artifacts_index.get(ARTIFACT_VOI_RUN_REPORT_REF)
    if ref is None:
        return {
            "status": "legacy_missing",
            "voi_run_report_ref": None,
            "decision_count": 0,
        }
    try:
        report = load_voi_run_report(ctx.store, ref)
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_voi_run_report",
            reason="voi_run_report_load_failed",
            exc=exc,
            ref=ref,
            artifact_key=ARTIFACT_VOI_RUN_REPORT_REF,
        )
        return {
            "status": "parse_failed",
            "voi_run_report_ref": str(ref.artifact_id),
            "decision_count": 0,
        }

    decision_type_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    mandatory_gate_override_count = 0
    for decision in report.decisions:
        decision_type_counts[decision.decision_type.value] = (
            decision_type_counts.get(decision.decision_type.value, 0) + 1
        )
        action_counts[decision.recommended_action] = (
            action_counts.get(decision.recommended_action, 0) + 1
        )
        if decision.mandatory_gate_overrides:
            mandatory_gate_override_count += 1
    return {
        "status": "available",
        "voi_run_report_ref": str(ref.artifact_id),
        "calibration_status": report.calibration_status,
        "decision_count": len(report.decisions),
        "total_expected_cost": report.total_expected_cost,
        "shadow_baseline_ref": (
            str(report.shadow_baseline_ref.artifact_id)
            if report.shadow_baseline_ref is not None
            else None
        ),
        "decision_type_counts": decision_type_counts,
        "action_counts": action_counts,
        "mandatory_gate_override_count": mandatory_gate_override_count,
    }


def _build_continuous_governance_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    """Attach continuous-governance validity links when shadow sidecars exist."""

    report_ref = artifacts_index.get(ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF)
    reissue_ref = artifacts_index.get(ARTIFACT_REISSUE_PACKET_REF)
    withdrawal_ref = artifacts_index.get(ARTIFACT_WITHDRAWAL_RECORD_REF)
    if report_ref is None:
        return {
            "status": "legacy_missing",
            "continuous_governance_report_ref": None,
            "reissue_packet_ref": str(reissue_ref.artifact_id) if reissue_ref else None,
            "withdrawal_record_ref": (str(withdrawal_ref.artifact_id) if withdrawal_ref else None),
            "event_count": 0,
            "recommendation_count": 0,
        }
    try:
        report = load_validity_report(ctx.store, report_ref)
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_continuous_governance_report",
            reason="continuous_governance_report_load_failed",
            exc=exc,
            ref=report_ref,
            artifact_key=ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF,
        )
        return {
            "status": "parse_failed",
            "continuous_governance_report_ref": str(report_ref.artifact_id),
            "reissue_packet_ref": str(reissue_ref.artifact_id) if reissue_ref else None,
            "withdrawal_record_ref": (str(withdrawal_ref.artifact_id) if withdrawal_ref else None),
            "event_count": 0,
            "recommendation_count": 0,
        }

    return {
        "status": report.status.value,
        "continuous_governance_report_ref": str(report_ref.artifact_id),
        "reissue_packet_ref": str(reissue_ref.artifact_id) if reissue_ref else None,
        "withdrawal_record_ref": str(withdrawal_ref.artifact_id) if withdrawal_ref else None,
        "event_count": len(report.monitor_events),
        "recommendation_count": len(report.recommendations),
        "affected_claim_ids": sorted(
            {claim_id for event in report.monitor_events for claim_id in event.affected_claim_ids}
        ),
        "recommended_actions": [
            recommendation.recommended_action for recommendation in report.recommendations
        ],
        "has_reissue_packet": report.reissue_packet_ref is not None or reissue_ref is not None,
        "has_withdrawal_record": report.withdrawal_ref is not None or withdrawal_ref is not None,
    }


def _build_policy_summary(
    ctx: ExecutionContext,
    state_inputs: dict[str, ArtifactRef],
) -> tuple[str, int]:
    trinity_ref = state_inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is None:
        return "N/A", 0

    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref))
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        _decision_packet_degraded(
            operation="load_policy_summary_trinity_bundle",
            reason="policy_summary_trinity_load_failed",
            exc=exc,
            ref=trinity_ref,
            artifact_key=INPUT_TRINITY_BUNDLE_REF,
        )
        return "Policy data unavailable", 0

    if not isinstance(payload, dict):
        return "Policy data attached", 0

    policy_spec = payload.get("policy_spec")
    if not isinstance(policy_spec, dict):
        return "Policy data attached", 0

    interventions = policy_spec.get("interventions")
    if isinstance(interventions, list):
        return f"Policy with {len(interventions)} intervention(s)", len(interventions)

    return "Policy data attached", 0


def _build_metric_significance_projection(
    report: MetricValidationReport,
) -> dict[str, dict[str, object]] | None:
    projections: dict[str, dict[str, object]] = {}
    duplicated_metrics: set[str] = set()
    for comparison in report.comparisons:
        metric_id = comparison.metric_id
        if metric_id in projections:
            duplicated_metrics.add(metric_id)
            projections.pop(metric_id, None)
            continue
        significance = comparison.significance
        projections[metric_id] = {
            "baseline_model_id": comparison.baseline_model_id,
            "candidate_model_id": comparison.candidate_model_id,
            "metric_direction": comparison.metric_direction,
            "baseline_value": comparison.baseline_value,
            "candidate_value": comparison.candidate_value,
            "delta_value": comparison.delta_value,
            "test_id": significance.test_id,
            "test_label": _describe_test_id(significance.test_id),
            "p_value": significance.p_value_raw,
            "p_adj": significance.p_value_adj,
            "alpha": significance.alpha,
            "significant": (
                significance.reject_null_adj
                if significance.reject_null_adj is not None
                else significance.reject_null_raw
            ),
            "effect_size": significance.effect_size,
            "assumption_warnings": list(significance.assumption_flags),
            "calibration_warnings": list(significance.calibration_flags),
        }
    for metric_id in duplicated_metrics:
        projections.pop(metric_id, None)
    return projections or None


def _build_metric_significance_summary(
    report: MetricValidationReport,
) -> dict[str, object]:
    significant_improvements: list[dict[str, object]] = []
    significant_regressions: list[dict[str, object]] = []
    for comparison in report.comparisons:
        significance = comparison.significance
        is_significant = (
            significance.reject_null_adj
            if significance.reject_null_adj is not None
            else significance.reject_null_raw
        )
        if not is_significant:
            continue
        item = {
            "baseline_model_id": comparison.baseline_model_id,
            "candidate_model_id": comparison.candidate_model_id,
            "metric_id": comparison.metric_id,
            "delta_value": comparison.delta_value,
            "p_value": significance.p_value_raw,
            "p_adj": significance.p_value_adj,
            "test_label": _describe_test_id(significance.test_id),
        }
        if _metric_delta_is_improvement(comparison.metric_direction, comparison.delta_value):
            significant_improvements.append(item)
        else:
            significant_regressions.append(item)
    return {
        "family_method": report.family_adjustment.method,
        "alpha": report.family_adjustment.alpha,
        "hypotheses_total": report.family_adjustment.hypotheses_total,
        "comparison_count": len(report.comparisons),
        "warning_count": len(report.warnings),
        "error_count": len(report.errors),
        "significant_improvements": significant_improvements,
        "significant_regressions": significant_regressions,
    }


def _build_metric_validation_comparison_rows(
    report: MetricValidationReport,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for comparison in report.comparisons:
        significance = comparison.significance
        rows.append(
            {
                "metric_id": comparison.metric_id,
                "metric_direction": comparison.metric_direction,
                "baseline_model_id": comparison.baseline_model_id,
                "candidate_model_id": comparison.candidate_model_id,
                "baseline_value": comparison.baseline_value,
                "candidate_value": comparison.candidate_value,
                "delta_value": comparison.delta_value,
                "family_id": comparison.family_id,
                "family_scope": comparison.family_scope,
                "sample_size_effective": comparison.sample_size_effective,
                "resampling_method": comparison.resampling_method,
                "test_id": significance.test_id,
                "test_label": _describe_test_id(significance.test_id),
                "statistic": significance.statistic,
                "effect_size": significance.effect_size,
                "ci_low": significance.ci_low,
                "ci_high": significance.ci_high,
                "ci_level": significance.ci_level,
                "p_value": significance.p_value_raw,
                "p_adj": significance.p_value_adj,
                "alpha": significance.alpha,
                "significant": (
                    significance.reject_null_adj
                    if significance.reject_null_adj is not None
                    else significance.reject_null_raw
                ),
                "assumption_warnings": list(significance.assumption_flags),
                "calibration_warnings": list(significance.calibration_flags),
            }
        )
    return rows


def _metric_delta_is_improvement(metric_direction: str, delta_value: float) -> bool:
    if metric_direction == "lower_is_better":
        return delta_value < 0
    return delta_value > 0


__all__ = [
    "_attach_claim_ledger_to_packet",
    "_attach_human_review_projection",
    "_build_abm_alignment_section",
    "_build_abstraction_section",
    "_build_aux_artifact_section",
    "_build_backtest_section",
    "_build_calibration_validation_section",
    "_build_causal_section",
    "_build_continuous_governance_section",
    "_build_data_basis",
    "_build_diagnostics_summary",
    "_build_distributional_section",
    "_build_econometrics_section",
    "_build_feedback_loop",
    "_build_hte_section",
    "_build_knowledge_basis",
    "_build_metric_significance_projection",
    "_build_metric_significance_summary",
    "_build_metric_validation_comparison_rows",
    "_build_normative_basis",
    "_build_phase3_section",
    "_build_policy_summary",
    "_build_runtime_contracts_section",
    "_build_sensitivity_section",
    "_build_strategic_section",
    "_build_targeting_section",
    "_build_tradeoff_certificate_section",
    "_build_transportability_basis",
    "_build_transportability_summary",
    "_build_uncertainty_bounds",
    "_build_uncertainty_section",
    "_build_voi_section",
    "_build_watched_triggers",
    "_build_web_evidence_section",
    "_build_welfare_section",
    "_describe_test_id",
    "_load_normative_arbitration",
    "_load_normative_frame_payload",
    "_merge_dp_summary_into_causal_payload",
    "_metric_delta_is_improvement",
    "_normalize_dp_summary",
    "_parse_anchor_at",
    "_performative_loop_payload",
]
