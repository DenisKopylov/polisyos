"""Public decide build decision packet module API."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionTriggerRecord,
    DecisionTriggerSpec,
    DecisionTriggerType,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.core.contracts.distributional import DistributionalReportRef
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import Metrics, SimulationResult
from polisyos.core.contracts.scholar import FreshnessMetadata
from polisyos.core.contracts.scientist import (
    DecisionMonitoringContractRef,
    DecisionPacketRef,
    MetricValidationReportRef,
    SourceVerificationReportRef,
    VerifiedPolicyReportRef,
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
    load_metric_validation_report,
)
from polisyos.ir.analytics.normative_arbitration import (
    NormativeArbitrationResult,
    load_normative_arbitration_result,
)
from polisyos.ir.analytics.partial_identification import load_bounds_bundle
from polisyos.ir.analytics.sensitivity import load_sensitivity_result
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
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.ir.refs import (
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
)
from polisyos.scientist.decision_validity import DecisionValidityService
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.error_semantics import emit_degraded_path
from polisyos.scientist.feedback import (
    DecisionFeedbackService,
    build_monitoring_contract_from_packet,
)
from polisyos.scientist.governance.calibration_validation import (
    load_calibration_validation_bundle,
)
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.decide.decision_packet_support import (
    ReplayReadiness,
    _build_replay_section,
    _compute_replay_readiness,
    _dedupe_strings,
    _determine_strategy_hint,
    _extract_context_payload,
    _fingerprint_payload,
    _path_get,
    _recommended_action,
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
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_DECISION_CARD_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
    ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ARTIFACT_ECONOMETRIC_RESULT_REF,
    ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_INPUT_BINDING_REPORT_REF,
    ARTIFACT_LOWERED_IR_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF,
    ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ARTIFACT_NORM_IMPACT_REPORT_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
    ARTIFACT_POLICY_RECOMMENDATION_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_SENSITIVITY_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_NORM_PACK_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_STATE_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_CHANGE_PROPOSAL_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
    REPORT_LEGAL_REPORT_REF,
    REPORT_LINK_REPORT_REF,
)
from polisyos.scientist.policy_design.output import load_policy_artifact_bundle
from polisyos.scientist.policy_verified import (
    load_source_verification_report,
    load_verified_policy_report,
)
from polisyos.scientist.validation.metrics import describe_test_id
from polisyos.scientist.search.readiness import load_decision_readiness_contract

logger = get_logger(__name__)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_decision_packet@1.5.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Decision Packet",
    description="Create the DecisionPacket artifact from available reports and metrics.",
    tags=["builtin", "decide"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "params.random_seed",
        "params.determinism_tier",
        "execution_profile",
        "capability_manifest_ref",
        "inputs",
        "reports_index",
        "artifacts_index",
        "artifacts_index.normative_arbitration_result_ref",
        "artifacts_index.policy_output_bundle_ref",
        "artifacts_index.source_verification_report_ref",
        "artifacts_index.verified_policy_report_ref",
        "artifacts_index.bounds_bundle_ref",
        "artifacts_index.decision_readiness_contract_ref",
    ],
    state_writes=[f"artifacts_index.{ARTIFACT_DECISION_PACKET_REF}"],
    produces=[ARTIFACT_DECISION_PACKET_REF],
)


_DECISION_PACKET_LOAD_ERRORS = (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    ValidationError,
)


@dataclass(frozen=True)
class _DecisionPacketBuildRequest:
    seed: int
    inputs_section: dict[str, object]
    artifacts_section: dict[str, object]
    readiness: ReplayReadiness
    strategy_hint: str
    policy_summary: dict[str, object]
    intervention_count: int


@dataclass(frozen=True)
class BuildDecisionPacketNode:
    """Build a DecisionPacket from the engine state."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        request = _build_decision_packet_request(ctx, state)
        replay_section = _build_replay_section(
            inputs_section=request.inputs_section,
            artifacts_section=request.artifacts_section,
            readiness=request.readiness,
            strategy_hint=request.strategy_hint,
            seed=request.seed,
            determinism_tier=state.params.get("determinism_tier"),
        )

        packet_payload: dict[str, object] = {
            "schema_version": "3.4",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": state.run_id,
            "seed": request.seed,
            "policy_summary": request.policy_summary,
            "intervention_count": request.intervention_count,
            "run_record": {
                "schema_version": "3.2",
                "run_id": state.run_id,
                "seed": request.seed,
                "engine": "scientist.engine",
            },
            "simulation_results": None,
            "metric_validation_report_ref": None,
            "metric_significance": None,
            "metric_significance_summary": None,
            "metric_validation_family_adjustment": None,
            "metric_validation_comparisons": [],
            "governance": None,
            "legal_verification": None,
            "source_coverage": None,
            "policy_answer": None,
            "verified_findings": [],
            "hypotheses": [],
            "intervention_legal_basis_map": {},
            "uncertainty": None,
            "uncertainty_bounds": None,
            "causal": None,
            "abm_alignment": None,
            "abstraction_certificate": None,
            "strategic": None,
            "hte": None,
            "targeting": None,
            "backtest": None,
            "calibration_validation": None,
            "distributional": None,
            "econometrics": None,
            "norm_impact": None,
            "sensitivity": None,
            "causal_validity": None,
            "stress_test": None,
            "tradeoff_certificate": None,
            "runtime_contracts": _build_runtime_contracts_section(state),
            "inputs": request.inputs_section,
            "artifacts": request.artifacts_section,
            "replay": replay_section,
            "degraded_paths": [],
            "notes": [],
        }
        packet_payload["uncertainty"] = _build_uncertainty_section(
            ctx,
            state.inputs,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["causal"] = _build_causal_section(
            ctx,
            state,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["abm_alignment"] = _build_abm_alignment_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["abstraction_certificate"] = _build_abstraction_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["strategic"] = _build_strategic_section(
            ctx,
            state,
            packet_payload=packet_payload,
        )
        packet_payload["hte"] = _build_hte_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["targeting"] = _build_targeting_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["backtest"] = _build_backtest_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["calibration_validation"] = _build_calibration_validation_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["distributional"] = _build_distributional_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["econometrics"] = _build_econometrics_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["norm_impact"] = _build_aux_artifact_section(
            ctx,
            state.artifacts_index,
            ARTIFACT_NORM_IMPACT_REPORT_REF,
            packet_payload=packet_payload,
        )
        packet_payload["sensitivity"] = _build_sensitivity_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        packet_payload["causal_validity"] = _build_aux_artifact_section(
            ctx,
            state.artifacts_index,
            ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
            packet_payload=packet_payload,
        )
        packet_payload["stress_test"] = _build_aux_artifact_section(
            ctx,
            state.artifacts_index,
            ARTIFACT_STRESS_TEST_REPORT_REF,
            packet_payload=packet_payload,
        )
        packet_payload["tradeoff_certificate"] = _build_tradeoff_certificate_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
        if isinstance(packet_payload["backtest"], dict):
            backtest_section = packet_payload["backtest"]
            if bool(backtest_section.get("trust_eligible", True)):
                packet_payload["trust_profile"] = {
                    "backtest_trust_score": backtest_section.get("trust_score"),
                    "backtest_trust_grade": backtest_section.get("trust_grade"),
                }
            else:
                packet_payload["trust_profile"] = {
                    "backtest_trust_score": None,
                    "backtest_trust_grade": None,
                }

        metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
        if metrics_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref.artifact_id))
                metrics = Metrics.model_validate(payload)
                packet_payload["simulation_results"] = dict(metrics.values)
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                packet_payload["simulation_results"] = None
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_metrics_artifact",
                        reason="metrics_load_failed",
                        exc=exc,
                        ref=metrics_ref,
                        artifact_key=ARTIFACT_METRICS_REF,
                    ),
                )

        metric_validation_ref = state.artifacts_index.get(ARTIFACT_METRIC_VALIDATION_REPORT_REF)
        if metric_validation_ref is not None:
            try:
                report = load_metric_validation_report(
                    ctx.store,
                    MetricValidationReportRef.model_validate(metric_validation_ref.model_dump()),
                )
                packet_payload["metric_validation_report_ref"] = str(metric_validation_ref.artifact_id)
                packet_payload["metric_significance"] = _build_metric_significance_projection(report)
                packet_payload["metric_significance_summary"] = _build_metric_significance_summary(report)
                packet_payload["metric_validation_family_adjustment"] = report.family_adjustment.model_dump(
                    mode="json"
                )
                packet_payload["metric_validation_comparisons"] = _build_metric_validation_comparison_rows(
                    report
                )
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_metric_validation_report",
                        reason="metric_validation_report_load_failed",
                        exc=exc,
                        ref=metric_validation_ref,
                        artifact_key=ARTIFACT_METRIC_VALIDATION_REPORT_REF,
                    ),
                )

        governance_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
        if governance_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(governance_ref.artifact_id))
                report = GovernanceReport.model_validate(payload)
                packet_payload["governance"] = {
                    "verdict": report.verdict,
                    "issues": report.issues,
                    "links": report.links.model_dump(mode="json"),
                    "notes": report.notes,
                }
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_governance_report",
                        reason="governance_report_load_failed",
                        exc=exc,
                        ref=governance_ref,
                        artifact_key=REPORT_GOVERNANCE_REPORT_REF,
                    ),
                )
                packet_payload["governance"] = None

        source_verification_ref = state.artifacts_index.get(ARTIFACT_SOURCE_VERIFICATION_REPORT_REF)
        if source_verification_ref is not None:
            try:
                report = load_source_verification_report(
                    ctx.store,
                    SourceVerificationReportRef.model_validate(source_verification_ref.model_dump()),
                )
                packet_payload["legal_verification"] = {
                    "verified_claim_count": len(report.verified_claims),
                    "citation_coverage_pct": report.verified_claim_citation_coverage_pct,
                    "needs_expert_review": report.needs_expert_review,
                    "verification_cycles_completed": report.verification_cycles_completed,
                }
                packet_payload["source_coverage"] = {
                    "unresolved_critical_gaps": [
                        gap.model_dump(mode="json") for gap in report.unresolved_critical_gaps
                    ],
                    "verifier_calls_total": report.verifier_calls_total,
                    "adjudicator_calls_total": report.adjudicator_calls_total,
                    "verifier_disagreement_rate": report.verifier_disagreement_rate,
                }
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_source_verification_report",
                        reason="source_verification_report_load_failed",
                        exc=exc,
                        ref=source_verification_ref,
                        artifact_key=ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
                    ),
                )

        verified_policy_ref = state.artifacts_index.get(ARTIFACT_VERIFIED_POLICY_REPORT_REF)
        if verified_policy_ref is not None:
            try:
                verified_report = load_verified_policy_report(
                    ctx.store,
                    VerifiedPolicyReportRef.model_validate(verified_policy_ref.model_dump()),
                )
                packet_payload["policy_answer"] = {
                    "executive_summary": verified_report.executive_summary,
                    "missing_evidence": list(verified_report.missing_evidence),
                    "needs_expert_review": verified_report.needs_expert_review,
                }
                packet_payload["verified_findings"] = list(verified_report.verified_findings)
                packet_payload["hypotheses"] = list(verified_report.hypotheses)
                packet_payload["intervention_legal_basis_map"] = dict(
                    verified_report.intervention_legal_basis_map
                )
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_verified_policy_report",
                        reason="verified_policy_report_load_failed",
                        exc=exc,
                        ref=verified_policy_ref,
                        artifact_key=ARTIFACT_VERIFIED_POLICY_REPORT_REF,
                    ),
                )

        policy_bundle_ref = state.artifacts_index.get(ARTIFACT_POLICY_OUTPUT_BUNDLE_REF)
        if policy_bundle_ref is not None:
            try:
                policy_bundle = load_policy_artifact_bundle(ctx.store, policy_bundle_ref)
                packet_payload["policy_output_bundle"] = {
                    "bundle_ref": policy_bundle_ref.artifact_id,
                    "policy_brief_ref": policy_bundle.policy_brief_ref.artifact_id,
                    "champion_policy_dossier_ref": (
                        policy_bundle.champion_policy_dossier_ref.artifact_id
                    ),
                    "decision_readiness_contract_ref": (
                        policy_bundle.decision_readiness_contract_ref.artifact_id
                        if policy_bundle.decision_readiness_contract_ref is not None
                        else None
                    ),
                }
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_degraded(
                    packet_payload,
                    _decision_packet_degraded(
                        operation="load_policy_output_bundle",
                        reason="policy_output_bundle_load_failed",
                        exc=exc,
                        ref=policy_bundle_ref,
                        artifact_key=ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
                    ),
                )

        uncertainty_bounds = _build_uncertainty_bounds(
            ctx,
            (
                packet_payload["uncertainty"]
                if isinstance(packet_payload["uncertainty"], dict)
                else {}
            ),
            packet_payload=packet_payload,
        )
        packet_payload["uncertainty_bounds"] = uncertainty_bounds
        packet_payload["diagnostics_summary"] = _build_diagnostics_summary(
            ctx=ctx,
            packet_payload=packet_payload,
            state=state,
        )
        packet_payload["analysis_limits"] = _build_analysis_limits(packet_payload)
        validity_envelope = _build_decision_validity_envelope(
            ctx=ctx,
            state=state,
            packet_payload=packet_payload,
        )
        validity_baseline = _build_decision_validity_baseline(
            packet_payload=packet_payload,
            envelope=validity_envelope,
        )
        packet_payload["decision_validity_envelope"] = validity_envelope.model_dump(mode="json")
        packet_payload["decision_validity_baseline"] = validity_baseline.model_dump(mode="json")
        feedback_loop, monitoring_contract_ref = _build_feedback_loop(
            ctx=ctx,
            state=state,
            packet_payload=packet_payload,
            decision_lineage_key=validity_envelope.decision_lineage_key,
        )
        packet_payload["feedback_loop"] = feedback_loop
        missing_serious_contracts = _missing_serious_decision_contracts(
            state=state,
            monitoring_contract_ref=monitoring_contract_ref,
        )
        if missing_serious_contracts:
            return NodeOutcome(
                status="fail",
                state=state,
                events=[
                    NodeEvent(
                        level="error",
                        message=(
                            "Serious execution profiles require a complete decision contract; "
                            f"missing: {', '.join(missing_serious_contracts)}."
                        ),
                    )
                ],
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="Incomplete serious decision contract",
                    details={
                        "execution_profile": state.execution_profile,
                        "missing_contracts": missing_serious_contracts,
                    },
                ),
            )

        inputs = _build_manifest_inputs(packet_payload)

        packet_ref_payload = ctx.store.put_json(
            packet_payload,
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.DecisionPacket",
                    version="3.4",
                ),
                inputs=inputs or None,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        packet_ref = DecisionPacketRef(artifact_id=packet_ref_payload.artifact_id)
        DecisionValidityService(ctx.store).register_decision_packet(
            packet_ref=str(packet_ref.artifact_id),
            envelope=validity_envelope,
            baseline=validity_baseline,
            monitoring_contract_ref=monitoring_contract_ref,
        )

        new_state = branch_state(
            state,
            write_paths=("artifacts_index.decision_packet_ref",),
        ).state
        new_state.artifacts_index[ARTIFACT_DECISION_PACKET_REF] = packet_ref

        return NodeOutcome(status="ok", state=new_state, artifacts=[packet_ref])


def _build_decision_packet_request(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> _DecisionPacketBuildRequest:
    seed = int(state.params.get("random_seed", 0) or 0)
    inputs_section = _build_inputs_section(state.inputs, state.artifacts_index)
    artifacts_section = _build_artifacts_section(
        state.artifacts_index,
        state.reports_index,
    )
    readiness = _compute_replay_readiness(inputs_section)
    strategy_hint = _determine_strategy_hint(inputs_section, artifacts_section)
    policy_summary, intervention_count = _build_policy_summary(ctx, state.inputs)
    return _DecisionPacketBuildRequest(
        seed=seed,
        inputs_section=inputs_section,
        artifacts_section=artifacts_section,
        readiness=readiness,
        strategy_hint=strategy_hint,
        policy_summary=policy_summary,
        intervention_count=intervention_count,
    )


def _build_inputs_section(
    state_inputs: dict[str, ArtifactRef],
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, str | None]:
    return {
        INPUT_TRINITY_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_TRINITY_BUNDLE_REF),
        INPUT_DATA_SNAPSHOT_REF: _ref_from_dict(state_inputs, INPUT_DATA_SNAPSHOT_REF),
        INPUT_STATE_SNAPSHOT_REF: _ref_from_dict(state_inputs, INPUT_STATE_SNAPSHOT_REF),
        INPUT_INPUT_BINDINGS_REF: _ref_from_dict(state_inputs, INPUT_INPUT_BINDINGS_REF),
        INPUT_REGISTRY_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_REGISTRY_BUNDLE_REF),
        INPUT_NORM_PACK_REF: _ref_from_dict(state_inputs, INPUT_NORM_PACK_REF),
        INPUT_KNOWLEDGE_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_KNOWLEDGE_BUNDLE_REF),
        INPUT_RESEARCH_INTENT_REF: _ref_from_dict(state_inputs, INPUT_RESEARCH_INTENT_REF),
        ARTIFACT_ENVIRONMENT_MANIFEST_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ENVIRONMENT_MANIFEST_REF
        ),
    }


def _build_artifacts_section(
    artifacts_index: dict[str, ArtifactRef],
    reports_index: dict[str, ArtifactRef],
) -> dict[str, str | None]:
    return {
        ARTIFACT_EXEC_PLAN_REF: _ref_from_dict(artifacts_index, ARTIFACT_EXEC_PLAN_REF),
        ARTIFACT_PROGRAM_GRAPH_REF: _ref_from_dict(artifacts_index, ARTIFACT_PROGRAM_GRAPH_REF),
        ARTIFACT_LOWERED_IR_REF: _ref_from_dict(artifacts_index, ARTIFACT_LOWERED_IR_REF),
        ARTIFACT_SIMULATION_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_SIMULATION_RESULT_REF
        ),
        ARTIFACT_STATE_SNAPSHOT_REF: _ref_from_dict(artifacts_index, ARTIFACT_STATE_SNAPSHOT_REF),
        ARTIFACT_METRICS_REF: _ref_from_dict(artifacts_index, ARTIFACT_METRICS_REF),
        ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF
        ),
        ARTIFACT_METRIC_VALIDATION_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_METRIC_VALIDATION_REPORT_REF
        ),
        ARTIFACT_INPUT_BINDING_REPORT_REF: _ref_from_dict(
            artifacts_index,
            ARTIFACT_INPUT_BINDING_REPORT_REF,
        ),
        REPORT_GOVERNANCE_REPORT_REF: _ref_from_dict(reports_index, REPORT_GOVERNANCE_REPORT_REF),
        REPORT_COMPILE_REPORT_REF: _ref_from_dict(reports_index, REPORT_COMPILE_REPORT_REF),
        REPORT_LINK_REPORT_REF: _ref_from_dict(reports_index, REPORT_LINK_REPORT_REF),
        REPORT_LEGAL_REPORT_REF: _ref_from_dict(reports_index, REPORT_LEGAL_REPORT_REF),
        REPORT_CHANGE_PROPOSAL_REF: _ref_from_dict(reports_index, REPORT_CHANGE_PROPOSAL_REF),
        ARTIFACT_CAUSAL_REPORT_REF: _ref_from_dict(artifacts_index, ARTIFACT_CAUSAL_REPORT_REF),
        ARTIFACT_CAUSAL_ENVELOPE_REF: _ref_from_dict(artifacts_index, ARTIFACT_CAUSAL_ENVELOPE_REF),
        ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF
        ),
        ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF
        ),
        ARTIFACT_CAUSAL_ENSEMBLE_REF: _ref_from_dict(artifacts_index, ARTIFACT_CAUSAL_ENSEMBLE_REF),
        ARTIFACT_ABM_ALIGNMENT_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ABM_ALIGNMENT_REPORT_REF
        ),
        ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF
        ),
        ARTIFACT_ABSTRACTION_CERTIFICATE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ABSTRACTION_CERTIFICATE_REF
        ),
        ARTIFACT_STRATEGIC_SCM_REF: _ref_from_dict(artifacts_index, ARTIFACT_STRATEGIC_SCM_REF),
        ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF
        ),
        ARTIFACT_HTE_RESULT_REF: _ref_from_dict(artifacts_index, ARTIFACT_HTE_RESULT_REF),
        ARTIFACT_POLICY_RECOMMENDATION_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_POLICY_RECOMMENDATION_REF
        ),
        ARTIFACT_BACKTEST_REPORT_REF: _ref_from_dict(artifacts_index, ARTIFACT_BACKTEST_REPORT_REF),
        ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF
        ),
        ARTIFACT_DISTRIBUTIONAL_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_DISTRIBUTIONAL_REPORT_REF
        ),
        ARTIFACT_ECONOMETRIC_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ECONOMETRIC_RESULT_REF
        ),
        ARTIFACT_ECONOMETRIC_EVIDENCE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ECONOMETRIC_EVIDENCE_REF
        ),
        ARTIFACT_ECONOMETRIC_ENVELOPE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ECONOMETRIC_ENVELOPE_REF
        ),
        ARTIFACT_DECISION_CARD_REF: _ref_from_dict(artifacts_index, ARTIFACT_DECISION_CARD_REF),
        ARTIFACT_DECISION_READINESS_CONTRACT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_DECISION_READINESS_CONTRACT_REF
        ),
        ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF
        ),
        ARTIFACT_NORM_IMPACT_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_NORM_IMPACT_REPORT_REF
        ),
        ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF
        ),
        ARTIFACT_SENSITIVITY_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_SENSITIVITY_RESULT_REF
        ),
        ARTIFACT_STRESS_TEST_REPORT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_STRESS_TEST_REPORT_REF
        ),
        ARTIFACT_BOUNDS_BUNDLE_REF: _ref_from_dict(artifacts_index, ARTIFACT_BOUNDS_BUNDLE_REF),
        ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF
        ),
        ARTIFACT_TRANSPORTABILITY_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_TRANSPORTABILITY_RESULT_REF
        ),
    }


def _ref_from_dict(index: dict[str, ArtifactRef], key: str) -> str | None:
    ref = index.get(key)
    return str(ref.artifact_id) if ref is not None else None


def _build_runtime_contracts_section(state: ExperimentState) -> dict[str, object]:
    return {
        "execution_profile": state.execution_profile,
        "capability_manifest_ref": (
            str(state.capability_manifest_ref.artifact_id)
            if state.capability_manifest_ref is not None
            else None
        ),
    }


def _missing_serious_decision_contracts(
    *,
    state: ExperimentState,
    monitoring_contract_ref: str | None,
) -> list[str]:
    profile = str(state.execution_profile or state.params.get("execution_profile") or "").strip().lower()
    if profile not in {"research", "governed", "production"}:
        return []
    missing: list[str] = []
    if state.capability_manifest_ref is None:
        missing.append("capability_manifest_ref")
    if ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF not in state.artifacts_index:
        missing.append(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
    if ARTIFACT_TRANSPORTABILITY_RESULT_REF not in state.artifacts_index:
        missing.append(ARTIFACT_TRANSPORTABILITY_RESULT_REF)
    if ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF not in state.artifacts_index:
        missing.append(ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF)
    if not monitoring_contract_ref:
        missing.append("monitoring_contract_ref")
    return missing


def _build_policy_summary(
    ctx: ExecutionContext,
    state_inputs: dict[str, ArtifactRef],
) -> tuple[str, int]:
    trinity_ref = state_inputs.get(INPUT_TRINITY_BUNDLE_REF)
    if trinity_ref is None:
        return "N/A", 0

    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
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


def _build_causal_section(
    ctx: ExecutionContext,
    state: ExperimentState,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    report_ref = artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    envelope_ref = artifacts_index.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    ensemble_ref = artifacts_index.get(ARTIFACT_CAUSAL_ENSEMBLE_REF)
    evidence_ref = artifacts_index.get(ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF)
    validity_ref = artifacts_index.get(ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF)
    bounds_ref = artifacts_index.get(ARTIFACT_BOUNDS_BUNDLE_REF)
    readiness_ref = artifacts_index.get(ARTIFACT_DECISION_READINESS_CONTRACT_REF)
    if (
        report_ref is None
        and envelope_ref is None
        and ensemble_ref is None
        and evidence_ref is None
        and validity_ref is None
        and bounds_ref is None
        and readiness_ref is None
    ):
        return None

    payload: dict[str, object] = {
        "report_ref": str(report_ref.artifact_id) if report_ref is not None else None,
        "envelope_ref": str(envelope_ref.artifact_id) if envelope_ref is not None else None,
        "ensemble_ref": str(ensemble_ref.artifact_id) if ensemble_ref is not None else None,
        "causal_method_evidence_ref": (
            str(evidence_ref.artifact_id) if evidence_ref is not None else None
        ),
        "causal_validity_ref": str(validity_ref.artifact_id) if validity_ref is not None else None,
        "bounds_ref": str(bounds_ref.artifact_id) if bounds_ref is not None else None,
        "decision_readiness_contract_ref": (
            str(readiness_ref.artifact_id) if readiness_ref is not None else None
        ),
        "proof_bundle_ref": None,
        "kernel_estimator_spec_ref": None,
        "kernel_summary": None,
        "ensemble_member_count": None,
        "ensemble_methods": [],
        "ensemble_consensus_graph_ref": None,
    }

    if ensemble_ref is not None:
        try:
            ensemble = load_causal_model_ensemble(
                ctx.store,
                CausalModelEnsembleRef(artifact_id=ensemble_ref.artifact_id),
            )
            payload["ensemble_member_count"] = len(ensemble.members)
            payload["ensemble_methods"] = sorted({member.discovery_method for member in ensemble.members})
            payload["ensemble_consensus_graph_ref"] = ensemble.consensus_graph_ref
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            logger.debug(
                "Failed to parse causal model ensemble from ref %s",
                ensemble_ref,
                exc_info=True,
            )
            payload["ensemble_parse_warning"] = "causal_ensemble_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_causal_ensemble",
                reason="causal_ensemble_load_failed",
                exc=exc,
                ref=ensemble_ref,
                artifact_key=ARTIFACT_CAUSAL_ENSEMBLE_REF,
            )

    if report_ref is not None:
        try:
            report_obj = from_canonical_bytes(ctx.store.get_bytes(report_ref.artifact_id))
            report = CausalEffectReport.model_validate(report_obj)
            refutation_results = [
                item.model_dump(mode="json") for item in report.refutation_results
            ]
            refutation_tests_total = len(report.refutation_results)
            refutation_tests_passed = sum(1 for item in report.refutation_results if item.passed)
            payload.update(
                {
                    "method": report.method.value,
                    "status": report.status.value,
                    "status_reason": report.status_reason,
                    "estimand": report.estimand,
                    "point_estimate": report.point_estimate,
                    "confidence_interval": report.confidence_interval,
                    "p_value": report.p_value,
                    "placebo_p_value": report.placebo_p_value,
                    "inference_method": report.inference_method,
                    "diagnostics": [diag.model_dump(mode="json") for diag in report.diagnostics],
                    "refutation_results": refutation_results,
                    "refutation_tests_total": refutation_tests_total,
                    "refutation_tests_passed": refutation_tests_passed,
                    "refutation_robust": (
                        refutation_tests_total > 0
                        and refutation_tests_passed == refutation_tests_total
                    ),
                    "transportability_summary": _build_transportability_summary(report, state),
                }
            )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["parse_warning"] = "causal_report_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_causal_report",
                reason="causal_report_load_failed",
                exc=exc,
                ref=report_ref,
                artifact_key=ARTIFACT_CAUSAL_REPORT_REF,
            )

    if evidence_ref is not None:
        try:
            evidence_bundle = load_causal_evidence_bundle(
                ctx.store,
                EvidenceBundleRef.model_validate(evidence_ref.model_dump()),
            )
            payload["proof_bundle_ref"] = (
                str(evidence_bundle.proof_bundle_ref.artifact_id)
                if evidence_bundle.proof_bundle_ref is not None
                else None
            )
            payload["kernel_estimator_spec_ref"] = (
                str(evidence_bundle.kernel_estimator_spec_ref.artifact_id)
                if evidence_bundle.kernel_estimator_spec_ref is not None
                else None
            )
            if evidence_bundle.kernel_estimator_spec_ref is not None:
                kernel_spec = load_kernel_estimator_spec(
                    ctx.store,
                    KernelEstimatorSpecRef.model_validate(
                        evidence_bundle.kernel_estimator_spec_ref.model_dump(mode="json")
                    ),
                )
                payload["kernel_summary"] = {
                    "template": kernel_spec.template.value,
                    "target_representation": kernel_spec.target_representation.value,
                    "lowering_disposition": kernel_spec.lowering_disposition.value,
                    "consistency_claim": kernel_spec.consistency_claim.value,
                    "required_side_conditions": list(kernel_spec.required_side_conditions),
                    "blocking_reasons": list(kernel_spec.blocking_reasons),
                    "diagnostics_plan": list(kernel_spec.diagnostics_plan),
                    "output_kernel": kernel_spec.output_kernel.name,
                    "operator_ready": kernel_spec.target_representation.value == "effect_operator",
                    "non_promotable": kernel_spec.lowering_disposition.value != "ready",
                }
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_causal_method_evidence_bundle",
                reason="causal_method_evidence_load_failed",
                exc=exc,
                ref=evidence_ref,
                artifact_key=ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
            )

    if bounds_ref is not None:
        try:
            bounds_bundle = load_bounds_bundle(ctx.store, bounds_ref)
            payload["bounds_interval"] = (
                None
                if bounds_bundle.lower_bound is None or bounds_bundle.upper_bound is None
                else [bounds_bundle.lower_bound, bounds_bundle.upper_bound]
            )
            payload["bounds_warning_codes"] = list(bounds_bundle.warnings)
            payload["bounds_sharpness_status"] = bounds_bundle.sharpness_status
            dp_summary = _normalize_dp_summary(bounds_bundle.metadata)
            if dp_summary is not None:
                _merge_dp_summary_into_causal_payload(payload, dp_summary)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["bounds_parse_warning"] = "bounds_bundle_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_bounds_bundle",
                reason="bounds_bundle_load_failed",
                exc=exc,
                ref=bounds_ref,
                artifact_key=ARTIFACT_BOUNDS_BUNDLE_REF,
            )

    if readiness_ref is not None:
        try:
            readiness = load_decision_readiness_contract(ctx.store, readiness_ref)
            payload["decision_readiness_level"] = readiness.readiness_level.value
            payload["decision_readiness_cap"] = readiness.metadata.get("readiness_cap")
            if readiness.metadata.get("data_readiness_decision") is not None:
                payload["data_readiness_decision"] = readiness.metadata.get(
                    "data_readiness_decision"
                )
            dp_summary = _normalize_dp_summary(readiness.metadata)
            if dp_summary is not None:
                _merge_dp_summary_into_causal_payload(payload, dp_summary)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["decision_readiness_parse_warning"] = (
                "decision_readiness_contract_parse_failed"
            )
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_decision_readiness_contract",
                reason="decision_readiness_contract_load_failed",
                exc=exc,
                ref=readiness_ref,
                artifact_key=ARTIFACT_DECISION_READINESS_CONTRACT_REF,
            )

    return payload


def _normalize_dp_summary(payload: Any) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    candidate = payload.get("dp_robustness")
    if isinstance(candidate, dict):
        payload = candidate
    effective_status = payload.get("effective_status", payload.get("dp_effective_status"))
    if effective_status is None:
        return None
    summary: dict[str, object] = {"effective_status": str(effective_status)}
    reason = payload.get("reason")
    if reason is not None:
        summary["reason"] = reason
    block_reason = payload.get("block_reason", payload.get("dp_block_reason"))
    if block_reason is not None:
        summary["block_reason"] = block_reason
    distortion_radius = payload.get("distortion_radius", payload.get("dp_distortion_radius"))
    if distortion_radius is not None:
        summary["distortion_radius"] = distortion_radius
    mechanism_family = payload.get("mechanism_family", payload.get("dp_mechanism_family"))
    if mechanism_family is not None:
        summary["mechanism_family"] = mechanism_family
    effect_interval = payload.get("effect_interval", payload.get("dp_effect_interval"))
    if isinstance(effect_interval, (list, tuple)) and len(effect_interval) == 2:
        summary["effect_interval"] = [effect_interval[0], effect_interval[1]]
    return summary


def _merge_dp_summary_into_causal_payload(
    payload: dict[str, object],
    summary: dict[str, object],
) -> None:
    payload["dp_effective_status"] = summary["effective_status"]
    if summary.get("reason") is not None:
        payload["dp_reason"] = summary["reason"]
    if summary.get("block_reason") is not None:
        payload["dp_block_reason"] = summary["block_reason"]
    if summary.get("distortion_radius") is not None:
        payload["dp_distortion_radius"] = summary["distortion_radius"]
    if summary.get("mechanism_family") is not None:
        payload["dp_mechanism_family"] = summary["mechanism_family"]
    if summary.get("effect_interval") is not None:
        payload["dp_effect_interval"] = summary["effect_interval"]


def _build_strategic_section(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    artifacts_index = state.artifacts_index
    strategic_scm_ref = artifacts_index.get(ARTIFACT_STRATEGIC_SCM_REF)
    bundle_ref = artifacts_index.get(ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF)
    strategic_summary = state.params.get("strategic_response")
    if strategic_scm_ref is None and bundle_ref is None and not isinstance(strategic_summary, dict):
        return None

    payload: dict[str, object] = {
        "strategic_scm_ref": (
            None if strategic_scm_ref is None else str(strategic_scm_ref.artifact_id)
        ),
        "strategic_response_bundle_ref": (
            None if bundle_ref is None else str(bundle_ref.artifact_id)
        ),
    }

    if strategic_scm_ref is not None:
        try:
            strategic_scm = load_strategic_scm(
                ctx.store,
                StrategicSCMRef(artifact_id=strategic_scm_ref.artifact_id),
            )
            payload["equilibrium_concept"] = (
                None
                if strategic_scm.equilibrium_concept is None
                else strategic_scm.equilibrium_concept.value
            )
            if strategic_scm.equilibrium_descriptor is not None:
                payload["strategic_game_class"] = strategic_scm.equilibrium_descriptor.game_class.value
                payload["strategic_solution_concept"] = (
                    strategic_scm.equilibrium_descriptor.solution_concept.value
                )
                payload["strategic_fallback_default"] = (
                    strategic_scm.equilibrium_descriptor.default_fallback_mode.value
                )
            payload["strategic_agents"] = list(strategic_scm.strategic_agents)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["strategic_scm_parse_warning"] = "strategic_scm_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_strategic_scm",
                reason="strategic_scm_load_failed",
                exc=exc,
                ref=strategic_scm_ref,
                artifact_key=ARTIFACT_STRATEGIC_SCM_REF,
            )

    if bundle_ref is not None:
        try:
            bundle = load_strategic_response_bundle(
                ctx.store,
                StrategicResponseBundleRef(artifact_id=bundle_ref.artifact_id),
            )
            payload.update(
                {
                    "fallback_mode": bundle.fallback_mode.value,
                    "equilibrium_selection_dependence": bundle.equilibrium_selection_dependence,
                    "multiplicity_note": bundle.multiplicity_note,
                    "blocked_reason": bundle.blocked_reason,
                    "decomposition_status": bundle.decomposition_status.value,
                    "decomposition_semantics": bundle.decomposition_semantics.value,
                    "selected_equilibrium_ref": (
                        None
                        if bundle.selected_equilibrium_ref is None
                        else str(bundle.selected_equilibrium_ref.artifact_id)
                    ),
                    "mfg_equilibrium_ref": (
                        None
                        if bundle.mfg_equilibrium_ref is None
                        else str(bundle.mfg_equilibrium_ref.artifact_id)
                    ),
                    "performative_shift_ref": (
                        None
                        if bundle.performative_shift_ref is None
                        else str(bundle.performative_shift_ref.artifact_id)
                    ),
                    "post_adaptation_policy_value_ref": str(
                        bundle.post_adaptation_policy_value_ref.artifact_id
                    ),
                    "causal_component_ref": str(bundle.causal_component_ref.artifact_id),
                    "strategic_closure_ref": str(bundle.strategic_closure_ref.artifact_id),
                    "equilibrium_set_ref": str(bundle.equilibrium_set_ref.artifact_id),
                    "decomposition_certificate_ref": (
                        None
                        if bundle.decomposition_certificate_ref is None
                        else str(bundle.decomposition_certificate_ref.artifact_id)
                    ),
                    "decomposition_failure_card_ref": (
                        None
                        if bundle.decomposition_failure_card_ref is None
                        else str(bundle.decomposition_failure_card_ref.artifact_id)
                    ),
                    "anchor_equilibrium_ref": (
                        None
                        if bundle.anchor_equilibrium_ref is None
                        else str(bundle.anchor_equilibrium_ref.artifact_id)
                    ),
                }
            )
            if bundle.mfg_equilibrium_ref is not None:
                try:
                    mfg_certificate = load_mean_field_equilibrium_certificate(
                        ctx.store,
                        bundle.mfg_equilibrium_ref,
                    )
                    payload.update(
                        {
                            "mfg_intervention_kind": mfg_certificate.intervention_kind.value,
                            "mfg_model_class": mfg_certificate.mean_field_model_class.value,
                            "mfg_uniqueness_status": (
                                mfg_certificate.well_posedness.uniqueness_status.value
                            ),
                            "mfg_selection_rule": (
                                mfg_certificate.identification.selection_rule.value
                            ),
                            "mfg_graph_semantics": (
                                mfg_certificate.identification.graph_semantics.value
                            ),
                            "mfg_positivity_status": (
                                mfg_certificate.identification.positivity_status.value
                            ),
                            "mfg_stability_bound_type": (
                                mfg_certificate.stability.bound_type.value
                            ),
                            "mfg_solver_residual_ref": (
                                None
                                if mfg_certificate.equilibrium_solution is None
                                or mfg_certificate.equilibrium_solution.solver_residual_ref is None
                                else str(
                                    mfg_certificate.equilibrium_solution.solver_residual_ref.artifact_id
                                )
                            ),
                            "mfg_mass_conservation_ref": (
                                None
                                if mfg_certificate.equilibrium_solution is None
                                or mfg_certificate.equilibrium_solution.mass_conservation_ref is None
                                else str(
                                    mfg_certificate.equilibrium_solution.mass_conservation_ref.artifact_id
                                )
                            ),
                            "mfg_numerics_config_ref": (
                                None
                                if mfg_certificate.provenance is None
                                or mfg_certificate.provenance.numerics_config_ref is None
                                else str(mfg_certificate.provenance.numerics_config_ref.artifact_id)
                            ),
                        }
                    )
                    if (
                        mfg_certificate.provenance is not None
                        and mfg_certificate.provenance.numerics_config_ref is not None
                        and mfg_certificate.provenance.numerics_config_ref.kind
                        == "ir.mean_field_macro_simulation_config"
                    ):
                        try:
                            numerics_config = load_mean_field_macro_simulation_config(
                                ctx.store,
                                mfg_certificate.provenance.numerics_config_ref,
                            )
                            payload.update(
                                {
                                    "mfg_numerics_scheme": numerics_config.numerics_scheme.value,
                                    "mfg_fixed_point_method": (
                                        numerics_config.fixed_point_method.value
                                    ),
                                    "mfg_runtime_mode": numerics_config.runtime_mode.value,
                                }
                            )
                        except _DECISION_PACKET_LOAD_ERRORS as exc:
                            payload["mfg_numerics_parse_warning"] = (
                                "mean_field_macro_simulation_config_load_failed"
                            )
                            _record_decision_packet_section_degraded(
                                packet_payload,
                                operation="load_mean_field_macro_simulation_config",
                                reason="mean_field_macro_simulation_config_load_failed",
                                exc=exc,
                                ref=mfg_certificate.provenance.numerics_config_ref,
                                artifact_key=ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
                            )
                    if (
                        bundle.mfg_equilibrium_ref.kind
                        == "ir.mean_field_equilibrium_certificate"
                        and mfg_certificate.intervention_spec_ref.kind
                        == "ir.mean_field_perturbation_spec"
                    ):
                        try:
                            perturbation_spec = load_mean_field_perturbation_spec(
                                ctx.store,
                                mfg_certificate.intervention_spec_ref,
                            )
                            payload.update(
                                {
                                    "mfg_representative_agent_channels": [
                                        channel.value
                                        for channel in perturbation_spec.representative_agent_channels
                                    ],
                                    "mfg_population_channels": [
                                        channel.value for channel in perturbation_spec.population_channels
                                    ],
                                    "mfg_policy_kernel_overlap_required": (
                                        perturbation_spec.policy_kernel_overlap_required
                                    ),
                                }
                            )
                        except _DECISION_PACKET_LOAD_ERRORS as exc:
                            payload["mfg_perturbation_parse_warning"] = (
                                "mean_field_perturbation_spec_load_failed"
                            )
                            _record_decision_packet_section_degraded(
                                packet_payload,
                                operation="load_mean_field_perturbation_spec",
                                reason="mean_field_perturbation_spec_load_failed",
                                exc=exc,
                                ref=mfg_certificate.intervention_spec_ref,
                                artifact_key=ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
                            )
                except _DECISION_PACKET_LOAD_ERRORS as exc:
                    payload["mfg_parse_warning"] = "mean_field_equilibrium_certificate_load_failed"
                    _record_decision_packet_section_degraded(
                        packet_payload,
                        operation="load_mean_field_equilibrium_certificate",
                        reason="mean_field_equilibrium_certificate_load_failed",
                        exc=exc,
                        ref=bundle.mfg_equilibrium_ref,
                        artifact_key=ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
                    )
            if bundle.performative_shift_ref is not None:
                try:
                    shift_summary = load_performative_shift_summary(
                        ctx.store,
                        bundle.performative_shift_ref,
                    )
                    if shift_summary.performative_shift is not None:
                        payload["performative_shift"] = shift_summary.performative_shift
                    payload["performative_loop"] = _performative_loop_payload(shift_summary)
                except _DECISION_PACKET_LOAD_ERRORS as exc:
                    payload["performative_shift_parse_warning"] = (
                        "performative_shift_summary_parse_failed"
                    )
                    _record_decision_packet_section_degraded(
                        packet_payload,
                        operation="load_performative_shift_summary",
                        reason="performative_shift_summary_load_failed",
                        exc=exc,
                        ref=bundle.performative_shift_ref,
                    )
            try:
                value_summary = load_post_adaptation_policy_value_summary(
                    ctx.store,
                    bundle.post_adaptation_policy_value_ref,
                )
                payload["post_adaptation_policy_value"] = value_summary.point_value
                if (
                    value_summary.lower_bound is not None
                    and value_summary.upper_bound is not None
                ):
                    payload["post_adaptation_policy_value_bounds"] = [
                        value_summary.lower_bound,
                        value_summary.upper_bound,
                    ]
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                payload["post_adaptation_value_parse_warning"] = (
                    "post_adaptation_policy_value_parse_failed"
                )
                _record_decision_packet_section_degraded(
                    packet_payload,
                    operation="load_post_adaptation_policy_value",
                    reason="post_adaptation_policy_value_load_failed",
                    exc=exc,
                    ref=bundle.post_adaptation_policy_value_ref,
                )
            if bundle.decomposition_failure_card_ref is not None:
                try:
                    failure_card = load_strategic_decomposition_failure_card(
                        ctx.store,
                        bundle.decomposition_failure_card_ref,
                    )
                    payload["decomposition_failure_code"] = failure_card.failure_code
                    payload["decomposition_message"] = failure_card.message
                except _DECISION_PACKET_LOAD_ERRORS as exc:
                    payload["decomposition_failure_parse_warning"] = (
                        "strategic_decomposition_failure_card_parse_failed"
                    )
                    _record_decision_packet_section_degraded(
                        packet_payload,
                        operation="load_strategic_decomposition_failure_card",
                        reason="strategic_decomposition_failure_card_load_failed",
                        exc=exc,
                        ref=bundle.decomposition_failure_card_ref,
                    )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["strategic_bundle_parse_warning"] = "strategic_response_bundle_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_strategic_response_bundle",
                reason="strategic_response_bundle_load_failed",
                exc=exc,
                ref=bundle_ref,
                artifact_key=ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
            )
    elif isinstance(strategic_summary, dict):
        for key in (
            "fallback_mode",
            "equilibrium_selection_dependence",
            "multiplicity_note",
            "blocked_reason",
            "selected_equilibrium",
            "performative_shift",
            "performative_loop",
            "post_adaptation_policy_value",
            "warnings",
            "causal_component_ref",
            "strategic_closure_ref",
            "equilibrium_set_ref",
            "post_adaptation_policy_value_ref",
            "selected_equilibrium_ref",
            "performative_shift_ref",
            "decomposition_status",
            "decomposition_semantics",
            "decomposition_failure_code",
            "decomposition_message",
            "decomposition_certificate_ref",
            "decomposition_failure_card_ref",
            "anchor_equilibrium_ref",
        ):
            if strategic_summary.get(key) is not None:
                payload[key] = strategic_summary[key]
        if strategic_summary.get("bounds") is not None:
            payload["post_adaptation_policy_value_bounds"] = strategic_summary["bounds"]

    return payload


def _performative_loop_payload(summary: Any) -> dict[str, object]:
    return {
        "analysis_scope": summary.analysis_scope.value,
        "proof_family": None if summary.proof_family is None else summary.proof_family.value,
        "stability_status": (
            None if summary.stability_status is None else summary.stability_status.value
        ),
        "reason_code": None if summary.reason_code is None else summary.reason_code.value,
        "contraction_upper_bound": summary.contraction_upper_bound,
        "local_spectral_radius_estimate": summary.local_spectral_radius_estimate,
        "witness_strength": (
            None if summary.witness_strength is None else summary.witness_strength.value
        ),
        "simulation_horizon": summary.simulation_horizon,
        "detected_cycle_period": summary.detected_cycle_period,
        "transient_gain_upper": summary.transient_gain_upper,
        "convergence_rate_upper": summary.convergence_rate_upper,
        "iterations_to_delta_bound": summary.iterations_to_delta_bound,
        "hardness_flag": bool(summary.hardness_flag),
        "recommended_action": (
            None if summary.recommended_action is None else summary.recommended_action.value
        ),
        "human_summary": summary.human_summary,
    }


def _build_transportability_summary(
    report: CausalEffectReport,
    state: ExperimentState,
) -> dict[str, object] | None:
    transport = report.transport_result
    if transport is None:
        return None
    gap_vars = [gap.required_variable for gap in transport.data_gaps]
    return {
        "status": transport.status.value,
        "transport_mode": transport.transport_mode.value,
        "final_confidence": transport.final_confidence,
        "feasible": transport.feasible,
        "algorithm_version": transport.algorithm_version,
        "identification_engine": transport.identification_engine,
        "capability_hash": state.params.get("transportability_capability_hash"),
        "degradation_policy": state.params.get("transportability_degradation_policy"),
        "unsupported_reason": transport.unsupported_reason,
        "identification_trace": list(transport.identification_trace),
        "pag_identification_policy": (
            transport.pag_identification_policy.value
            if transport.pag_identification_policy is not None
            else None
        ),
        "id_confidence_under_pag": transport.id_confidence_under_pag,
        "pag_dag_sample_size": transport.pag_dag_sample_size,
        "pag_transportable_count": transport.pag_transportable_count,
        "resolution_rounds": transport.resolution_rounds,
        "data_gaps_count": len(transport.data_gaps),
        "data_gap_variables": gap_vars,
        "unsupported_cases_count": len(transport.unsupported_cases),
        "unsupported_cases": list(transport.unsupported_cases),
        "hard_legal_constraints": list(transport.hard_legal_constraints),
        "requires_expert_review": transport.requires_expert_review,
        "expert_review_reasons": list(transport.expert_review_reasons),
        "warnings": list(transport.warnings),
    }


def _build_abm_alignment_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    report_ref = artifacts_index.get(ARTIFACT_ABM_ALIGNMENT_REPORT_REF)
    if report_ref is None:
        return None

    payload: dict[str, object] = {"report_ref": str(report_ref.artifact_id)}
    try:
        report = load_abm_alignment_report(
            ctx.store,
            ABMAlignmentReportRef(artifact_id=report_ref.artifact_id),
        )
        status_counts: dict[str, int] = {}
        for result in report.alignment_results.values():
            key = result.status.value
            status_counts[key] = status_counts.get(key, 0) + 1

        payload.update(
            {
                "overall_consistent": report.overall_consistent,
                "n_mappings": len(report.mappings),
                "n_results": len(report.alignment_results),
                "status_counts": status_counts,
                "phase_transitions": [
                    item.model_dump(mode="json") for item in report.phase_transitions
                ],
                "warnings": list(report.warnings),
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "abm_alignment_report_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_abm_alignment_report",
            reason="abm_alignment_report_load_failed",
            exc=exc,
            ref=report_ref,
            artifact_key=ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
        )

    return payload


def _build_abstraction_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    certificate_ref = artifacts_index.get(ARTIFACT_ABSTRACTION_CERTIFICATE_REF)
    if certificate_ref is None:
        return None

    payload: dict[str, object] = {
        "certificate_ref": str(certificate_ref.artifact_id),
        "abstraction_map_ref": None,
    }
    map_ref = artifacts_index.get(ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF)
    if map_ref is not None:
        payload["abstraction_map_ref"] = str(map_ref.artifact_id)
    try:
        certificate = load_abstraction_certificate(
            ctx.store,
            AbstractionCertificateRef(artifact_id=certificate_ref.artifact_id),
        )
        payload.update(
            {
                "preservation_type": certificate.preservation_type.value,
                "preserved_queries": list(certificate.preserved_queries),
                "error_bound": certificate.error_bound,
                "validation_notes": list(certificate.validation_notes),
                "metadata": dict(certificate.metadata),
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "abstraction_certificate_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_abstraction_certificate",
            reason="abstraction_certificate_load_failed",
            exc=exc,
            ref=certificate_ref,
            artifact_key=ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
        )
    return payload


def _build_hte_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    hte_ref = artifacts_index.get(ARTIFACT_HTE_RESULT_REF)
    if hte_ref is None:
        return None
    from polisyos.core.contracts.hte import HTEResultRef

    payload: dict[str, object] = {"result_ref": str(hte_ref.artifact_id)}
    try:
        result = load_hte_result(
            ctx.store,
            HTEResultRef(artifact_id=hte_ref.artifact_id),
        )
        payload.update(
            {
                "method": result.method.value,
                "ate": result.ate,
                "ate_ci_lower": result.ate_ci_lower,
                "ate_ci_upper": result.ate_ci_upper,
                "n_samples": result.n_samples,
                "n_features": result.n_features,
                "n_subgroups": len(result.subgroup_effects),
                "top_features": [
                    item.model_dump(mode="json")
                    for item in sorted(
                        result.feature_importances, key=lambda x: x.importance_rank
                    )[:5]
                ],
                "warnings": result.metadata.get("warnings", []),
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "hte_result_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_hte_result",
            reason="hte_result_load_failed",
            exc=exc,
            ref=hte_ref,
            artifact_key=ARTIFACT_HTE_RESULT_REF,
        )
    return payload


def _build_targeting_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    recommendation_ref = artifacts_index.get(ARTIFACT_POLICY_RECOMMENDATION_REF)
    if recommendation_ref is None:
        return None
    from polisyos.core.contracts.hte import PolicyRecommendationRef

    payload: dict[str, object] = {"recommendation_ref": str(recommendation_ref.artifact_id)}
    try:
        recommendation = load_policy_recommendation(
            ctx.store,
            PolicyRecommendationRef(artifact_id=recommendation_ref.artifact_id),
        )
        payload.update(
            {
                "budget_constraint": recommendation.budget_constraint,
                "optimization_objective": recommendation.optimization_objective,
                "n_targeted_units": recommendation.n_targeted_units,
                "n_total_units": recommendation.n_total_units,
                "total_expected_effect": recommendation.total_expected_effect,
                "total_cost": recommendation.total_cost,
                "targeting_efficiency": recommendation.targeting_efficiency,
                "rules": [
                    rule.model_dump(mode="json")
                    for rule in sorted(recommendation.targeting_rules, key=lambda r: r.priority)
                ],
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "policy_recommendation_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_policy_recommendation",
            reason="policy_recommendation_load_failed",
            exc=exc,
            ref=recommendation_ref,
            artifact_key=ARTIFACT_POLICY_RECOMMENDATION_REF,
        )
    return payload


def _build_backtest_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    backtest_ref = artifacts_index.get(ARTIFACT_BACKTEST_REPORT_REF)
    if backtest_ref is None:
        return None
    from polisyos.core.contracts.backtest import BacktestReportRef


    payload: dict[str, object] = {"report_ref": str(backtest_ref.artifact_id)}
    try:
        report = load_backtest_report(
            ctx.store,
            BacktestReportRef(artifact_id=backtest_ref.artifact_id),
        )
        payload.update(
            {
                "report_id": report.report_id,
                "n_scenarios": report.n_scenarios,
                "n_metrics_evaluated": report.n_metrics_evaluated,
                "overall_rmse": report.overall_rmse,
                "overall_mae": report.overall_mae,
                "overall_mape": report.overall_mape,
                "overall_coverage_probability": report.overall_coverage_probability,
                "overall_bias_direction": report.overall_bias_direction.value,
                "detected_biases": [
                    bias.model_dump(mode="json") for bias in report.detected_biases
                ],
                "prediction_mode_requested": report.prediction_mode_requested,
                "prediction_mode_effective": report.prediction_mode_effective,
                "degraded": report.degraded,
                "degraded_reasons": list(report.degraded_reasons),
                "trust_eligible": report.trust_eligible,
                "trust_score": report.trust_score,
                "trust_grade": report.trust_grade,
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "backtest_report_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_backtest_report",
            reason="backtest_report_load_failed",
            exc=exc,
            ref=backtest_ref,
            artifact_key=ARTIFACT_BACKTEST_REPORT_REF,
        )
    return payload


def _build_calibration_validation_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    bundle_ref = artifacts_index.get(ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF)
    if bundle_ref is None:
        return None
    payload: dict[str, object] = {"ref": str(bundle_ref.artifact_id)}
    try:
        bundle = load_calibration_validation_bundle(ctx.store, bundle_ref)
        payload.update(
            {
                "status": bundle.status,
                "governance_verdict": bundle.governance_verdict,
                "summary": bundle.readout_summary(),
                "governance_accountability_ref": (
                    None
                    if bundle.governance_accountability_ref is None
                    else str(bundle.governance_accountability_ref.artifact_id)
                ),
                "governance_accountability_summary": dict(
                    bundle.governance_accountability_summary
                ),
            }
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "calibration_validation_bundle_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_calibration_validation_bundle",
            reason="calibration_validation_bundle_load_failed",
            exc=exc,
            ref=bundle_ref,
            artifact_key=ARTIFACT_CALIBRATION_VALIDATION_BUNDLE_REF,
        )
    return payload


def _build_feedback_loop(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    packet_payload: dict[str, object],
    decision_lineage_key: str,
) -> tuple[dict[str, object], str | None]:
    generated_at = packet_payload.get("generated_at")
    anchor_at = str(state.params.get("deployment_at") or generated_at or "")
    monitoring_contract_ref: str | None = None
    feedback_service = DecisionFeedbackService(ctx.store)
    contract = build_monitoring_contract_from_packet(
        run_id=state.run_id,
        decision_lineage_key=decision_lineage_key,
        anchor_at=_parse_anchor_at(anchor_at),
        packet_payload=packet_payload,
        override=(
            state.params.get("monitoring_contract_override")
            if isinstance(state.params.get("monitoring_contract_override"), dict)
            else None
        ),
    )
    if contract is not None:
        input_refs: list[InputRef] = []
        for ref in (
            state.inputs.get(INPUT_DATA_SNAPSHOT_REF),
            state.artifacts_index.get(ARTIFACT_BACKTEST_REPORT_REF),
            state.artifacts_index.get(ARTIFACT_METRICS_REF),
        ):
            if ref is not None:
                input_refs.append(InputRef(artifact_id=ref.artifact_id, role="feedback_source"))
        monitoring_contract_ref = feedback_service.persist_monitoring_contract(
            contract,
            inputs=input_refs or None,
        )

    backtest_section = packet_payload.get("backtest") if isinstance(packet_payload.get("backtest"), dict) else {}
    contract_ref_payload = (
        DecisionMonitoringContractRef(artifact_id=monitoring_contract_ref).model_dump(mode="json")
        if monitoring_contract_ref is not None
        else None
    )
    return (
        {
            "anchor_at": anchor_at,
            "monitoring_contract_ref": contract_ref_payload,
            "latest_monitoring_report_ref": None,
            "latest_compare_report_ref": None,
            "latest_reissue_plan_ref": None,
            "backtest_mode_effective": backtest_section.get("prediction_mode_effective"),
            "backtest_trust_eligible": backtest_section.get("trust_eligible"),
        },
        monitoring_contract_ref,
    )


def _parse_anchor_at(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_distributional_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    bundle_ref = artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF)
    report_ref = artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)
    if report_ref is None and bundle_ref is None:
        return None

    payload: dict[str, object] = {
        "report_ref": str(report_ref.artifact_id) if report_ref is not None else None,
        "effect_bundle_ref": str(bundle_ref.artifact_id) if bundle_ref is not None else None,
    }
    if report_ref is not None:
        try:
            report = load_distributional_report(
                ctx.store,
                DistributionalReportRef(artifact_id=report_ref.artifact_id),
            )
            payload.update(
                {
                    "overall_gini_before": report.overall_gini_before,
                    "overall_gini_after": report.overall_gini_after,
                    "overall_gini_delta": report.overall_gini_delta,
                    "palma_ratio_before": report.palma_ratio_before,
                    "palma_ratio_after": report.palma_ratio_after,
                    "palma_ratio_delta": report.palma_ratio_delta,
                    "winners_count": len(report.winners_losers.winners),
                    "losers_count": len(report.winners_losers.losers),
                    "neutral_count": len(report.winners_losers.neutral),
                    "winners_share": report.winners_losers.total_winners_share,
                    "losers_share": report.winners_losers.total_losers_share,
                    "ordinal_poverty_summary": dict(report.ordinal_poverty_summary),
                    "breakdowns": [
                        {
                            "dimension": breakdown.dimension.value,
                            "dimension_label": breakdown.dimension_label,
                            "primary_metric": breakdown.primary_metric,
                            "primary_metric_unit": breakdown.primary_metric_unit.value,
                            "gini_before": breakdown.gini_before,
                            "gini_after": breakdown.gini_after,
                            "gini_delta": breakdown.gini_delta,
                            "cohorts": [
                                {
                                    "cohort_id": cohort.cohort_id,
                                    "cohort_label": cohort.cohort_label,
                                    "population_share": cohort.population_share,
                                    "delta": cohort.metric_deltas.get(breakdown.primary_metric),
                                    "impact_direction": cohort.impact_direction.value,
                                    "is_vulnerable": cohort.is_vulnerable,
                                }
                                for cohort in breakdown.cohorts
                            ],
                        }
                        for breakdown in report.breakdowns
                    ],
                }
            )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["parse_warning"] = "distributional_report_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_distributional_report",
                reason="distributional_report_load_failed",
                exc=exc,
                ref=report_ref,
                artifact_key=ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
            )

    if bundle_ref is not None:
        try:
            bundle = load_distributional_effect_bundle(
                ctx.store,
                DistributionalEffectBundleRef.model_validate(bundle_ref.model_dump()),
            )
            proof_kernel = bundle.metadata.get("proof_kernel")
            payload.update(
                {
                    "distributional_query_kind": bundle.distributional_query_kind,
                    "justification": bundle.justification.value,
                    "marginal_law_justification": (
                        bundle.marginal_law_justification.value
                        if bundle.marginal_law_justification is not None
                        else None
                    ),
                    "coupling_justification": (
                        bundle.coupling_justification.value
                        if bundle.coupling_justification is not None
                        else None
                    ),
                    "distributional_bounds_count": len(bundle.distributional_bounds_refs),
                    "causal_assumption_count": len(bundle.causal_assumption_refs),
                    "readiness_cap": bundle.readiness_cap,
                    "marginal_law_proof_ref": (
                        str(bundle.marginal_law_proof_ref.artifact_id)
                        if bundle.marginal_law_proof_ref is not None
                        else None
                    ),
                    "distributional_proof_ref": (
                        str(bundle.distributional_proof_ref.artifact_id)
                        if bundle.distributional_proof_ref is not None
                        else None
                    ),
                    "coupling_proof_ref": (
                        str(bundle.coupling_proof_ref.artifact_id)
                        if bundle.coupling_proof_ref is not None
                        else None
                    ),
                    "proof_kernel_status": (
                        str(proof_kernel.get("status"))
                        if isinstance(proof_kernel, dict) and proof_kernel.get("status") is not None
                        else None
                    ),
                    "proof_kernel_theorem_family": (
                        str(proof_kernel.get("theorem_family"))
                        if isinstance(proof_kernel, dict) and proof_kernel.get("theorem_family") is not None
                        else None
                    ),
                    "ordinal_poverty_ref": (
                        str(bundle.ordinal_poverty_ref.artifact_id)
                        if bundle.ordinal_poverty_ref is not None
                        else None
                    ),
                }
            )
            if bundle.ordinal_poverty_ref is not None:
                try:
                    ordinal_report = load_ordinal_poverty_report(ctx.store, bundle.ordinal_poverty_ref)
                    payload.update(
                        {
                            "ordinal_poverty_methodology": ordinal_report.methodology,
                            "ordinal_poverty_deltas": dict(ordinal_report.deltas),
                        }
                    )
                except _DECISION_PACKET_LOAD_ERRORS as exc:
                    payload["ordinal_poverty_parse_warning"] = "ordinal_poverty_report_load_failed"
                    _record_decision_packet_section_degraded(
                        packet_payload,
                        operation="load_ordinal_poverty_report",
                        reason="ordinal_poverty_report_load_failed",
                        exc=exc,
                        ref=bundle.ordinal_poverty_ref,
                        artifact_key=ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
                    )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_distributional_effect_bundle",
                reason="distributional_effect_bundle_load_failed",
                exc=exc,
                ref=bundle_ref,
                artifact_key=ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
            )

    return payload


def _decision_packet_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    ref: ArtifactRef | None = None,
    artifact_id: str | None = None,
    artifact_key: str | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if ref is not None:
        details["artifact_id"] = str(ref.artifact_id)
    elif isinstance(artifact_id, str) and artifact_id:
        details["artifact_id"] = artifact_id
    if artifact_key is not None:
        details["artifact_key"] = artifact_key
    return emit_degraded_path(
        component="scientist.build_decision_packet",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )


def _record_decision_packet_degraded(
    packet_payload: dict[str, object],
    envelope: dict[str, Any],
) -> None:
    degraded_paths = packet_payload.setdefault("degraded_paths", [])
    if isinstance(degraded_paths, list):
        degraded_paths.append(envelope)
    notes = packet_payload.setdefault("notes", [])
    if isinstance(notes, list):
        reason = str(envelope.get("reason", "decision_packet_degraded"))
        message = str(envelope.get("message", reason))
        notes.append(f"{reason}: {message}")


def _record_decision_packet_section_degraded(
    packet_payload: dict[str, object] | None,
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    ref: ArtifactRef | None = None,
    artifact_id: str | None = None,
    artifact_key: str | None = None,
) -> None:
    if packet_payload is None:
        return
    _record_decision_packet_degraded(
        packet_payload,
        _decision_packet_degraded(
            operation=operation,
            reason=reason,
            exc=exc,
            ref=ref,
            artifact_id=artifact_id,
            artifact_key=artifact_key,
        ),
    )


def _build_tradeoff_certificate_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    result = _load_normative_arbitration(ctx, artifacts_index, packet_payload=packet_payload)
    if result is None:
        return None
    return {
        "selected_policy": result.tradeoff_certificate.selected_policy.value,
        "selected_option": result.tradeoff_certificate.selected_option.value,
        "winners": list(result.tradeoff_certificate.winners),
        "losers": list(result.tradeoff_certificate.losers),
        "residual_dissent": [
            item.model_dump(mode="json") for item in result.tradeoff_certificate.residual_dissent
        ],
        "rights_violations": list(result.tradeoff_certificate.rights_violations),
        "hard_constraint_violations": list(
            result.tradeoff_certificate.hard_constraint_violations
        ),
        "notes": list(result.tradeoff_certificate.notes),
    }


def _build_econometrics_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    result_ref = artifacts_index.get(ARTIFACT_ECONOMETRIC_RESULT_REF)
    evidence_ref = artifacts_index.get(ARTIFACT_ECONOMETRIC_EVIDENCE_REF)
    envelope_ref = artifacts_index.get(ARTIFACT_ECONOMETRIC_ENVELOPE_REF)
    if result_ref is None and evidence_ref is None and envelope_ref is None:
        return None

    payload: dict[str, object] = {
        "result_ref": str(result_ref.artifact_id) if result_ref is not None else None,
        "evidence_ref": str(evidence_ref.artifact_id) if evidence_ref is not None else None,
        "envelope_ref": str(envelope_ref.artifact_id) if envelope_ref is not None else None,
    }

    if result_ref is not None:
        try:
            result_obj = from_canonical_bytes(ctx.store.get_bytes(result_ref.artifact_id))
            if isinstance(result_obj, dict):
                payload["result"] = result_obj.get("result", result_obj)
                if "envelope" in result_obj:
                    payload["envelope"] = result_obj["envelope"]
            else:
                payload["result_type"] = type(result_obj).__name__
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["result_parse_warning"] = "econometric_result_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_econometric_result",
                reason="econometric_result_load_failed",
                exc=exc,
                ref=result_ref,
                artifact_key=ARTIFACT_ECONOMETRIC_RESULT_REF,
            )

    if envelope_ref is not None:
        try:
            envelope = load_uncertainty_envelope(
                ctx.store,
                UncertaintyEnvelopeRef(artifact_id=envelope_ref.artifact_id),
            )
            payload["envelope_summary"] = {
                "point_estimate": envelope.point_estimate,
                "confidence_interval": [
                    envelope.confidence_interval[0],
                    envelope.confidence_interval[1],
                ],
                "confidence_level": envelope.confidence_level,
            }
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            payload["envelope_parse_warning"] = "econometric_envelope_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_econometric_envelope",
                reason="econometric_envelope_load_failed",
                exc=exc,
                ref=envelope_ref,
                artifact_key=ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
            )

    return payload


def _load_normative_arbitration(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> NormativeArbitrationResult | None:
    ref = artifacts_index.get(ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF)
    if ref is None:
        return None
    try:
        return load_normative_arbitration_result(
            ctx.store,
            NormativeArbitrationResultRef(artifact_id=ref.artifact_id),
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        logger.debug("Failed to parse normative arbitration result from ref %s", ref, exc_info=True)
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_normative_arbitration_result",
            reason="normative_arbitration_load_failed",
            exc=exc,
            ref=ref,
            artifact_key=ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
        )
        return None


def _build_aux_artifact_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    key: str,
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    ref = artifacts_index.get(key)
    if ref is None:
        return None
    payload: dict[str, object] = {"ref": str(ref.artifact_id)}
    try:
        artifact_obj = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
        if isinstance(artifact_obj, dict):
            payload["content"] = artifact_obj
        else:
            payload["content_type"] = type(artifact_obj).__name__
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        payload["parse_warning"] = "artifact_parse_failed"
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_aux_artifact",
            reason="aux_artifact_load_failed",
            exc=exc,
            ref=ref,
            artifact_key=key,
        )
    return payload


def _build_sensitivity_section(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object] | None:
    ref = artifacts_index.get(ARTIFACT_SENSITIVITY_RESULT_REF)
    if ref is None:
        return None
    payload: dict[str, object] = {"ref": str(ref.artifact_id)}
    try:
        result = load_sensitivity_result(
            ctx.store,
            CausalSensitivityResultRef.model_validate(ref.model_dump(mode="json")),
        )
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="load_sensitivity_result",
            reason="sensitivity_result_load_failed",
            exc=exc,
            ref=ref,
            artifact_key=ARTIFACT_SENSITIVITY_RESULT_REF,
        )
        try:
            artifact_obj = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
            if isinstance(artifact_obj, dict):
                payload["content"] = artifact_obj
        except _DECISION_PACKET_LOAD_ERRORS as fallback_exc:
            payload["parse_warning"] = "artifact_parse_failed"
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_sensitivity_fallback_artifact",
                reason="sensitivity_fallback_artifact_load_failed",
                exc=fallback_exc,
                ref=ref,
                artifact_key=ARTIFACT_SENSITIVITY_RESULT_REF,
            )
        payload.setdefault("parse_warning", "sensitivity_parse_failed")
        return payload

    content = result.model_dump(mode="json")
    content["summary"] = {
        "status": "robust" if result.is_robust else "fragile",
        "e_value": result.e_value,
        "e_value_ci_lower": result.e_value_ci_lower,
        "robustness_value": result.robustness_value,
        "rosenbaum_gamma": result.rosenbaum_gamma,
        "benchmark_covariate_count": len(result.benchmark_covariates),
    }
    payload["content"] = content
    return payload

def _build_diagnostics_summary(
    *,
    ctx: ExecutionContext,
    packet_payload: dict[str, object],
    state: ExperimentState,
) -> dict[str, object]:
    governance = packet_payload.get("governance")
    governance_dict = governance if isinstance(governance, dict) else {}
    issues = governance_dict.get("issues")
    issue_summary = _summarize_governance_issues(issues if isinstance(issues, list) else [])

    causal = packet_payload.get("causal")
    causal_dict = causal if isinstance(causal, dict) else {}
    transport_summary = causal_dict.get("transportability_summary")
    transport_dict = transport_summary if isinstance(transport_summary, dict) else {}
    sensitivity = packet_payload.get("sensitivity")
    sensitivity_dict = sensitivity if isinstance(sensitivity, dict) else {}
    sensitivity_content = sensitivity_dict.get("content")
    sensitivity_content_dict = sensitivity_content if isinstance(sensitivity_content, dict) else {}
    sensitivity_summary = sensitivity_content_dict.get("summary")
    sensitivity_summary_dict = sensitivity_summary if isinstance(sensitivity_summary, dict) else {}
    causal_validity = packet_payload.get("causal_validity")
    causal_validity_dict = causal_validity if isinstance(causal_validity, dict) else {}
    validity_content = causal_validity_dict.get("content")
    validity_content_dict = validity_content if isinstance(validity_content, dict) else {}
    validity_checks = validity_content_dict.get("checks")
    validity_checks_dict = validity_checks if isinstance(validity_checks, dict) else {}

    replay = packet_payload.get("replay")
    replay_dict = replay if isinstance(replay, dict) else {}

    uncertainty = packet_payload.get("uncertainty")
    uncertainty_dict = uncertainty if isinstance(uncertainty, dict) else {}
    uncertainty_bounds = packet_payload.get("uncertainty_bounds")
    normative_result = _load_normative_arbitration(ctx, state.artifacts_index)
    degraded_paths = packet_payload.get("degraded_paths")
    degraded_path_items = [item for item in degraded_paths if isinstance(item, dict)] if isinstance(degraded_paths, list) else []

    governance_links = governance_dict.get("links")
    legal_ref = None
    if isinstance(governance_links, dict):
        legal_ref = governance_links.get("legal_report_ref")
        if isinstance(legal_ref, dict):
            legal_ref = legal_ref.get("artifact_id")
    if not isinstance(legal_ref, str):
        artifacts = packet_payload.get("artifacts")
        artifacts_dict = artifacts if isinstance(artifacts, dict) else {}
        fallback_legal_ref = artifacts_dict.get(REPORT_LEGAL_REPORT_REF)
        legal_ref = fallback_legal_ref if isinstance(fallback_legal_ref, str) else None

    has_legal_report = legal_ref is not None
    has_distributional_report = bool(packet_payload.get("distributional"))
    has_causal_report = bool(causal_dict)
    has_abstraction_certificate = bool(packet_payload.get("abstraction_certificate"))
    uncertainty_available = bool(uncertainty_dict.get("envelope_count")) or isinstance(
        uncertainty_bounds, dict
    )
    contract_warnings = _collect_contract_warnings(ctx, state)
    resolved_fidelity_level = _load_resolved_fidelity_level(ctx, state)
    requires_expert_review = bool(transport_dict.get("requires_expert_review")) or bool(
        state.params.get("needs_expert_review")
    )
    human_review_needed = bool(state.params.get("require_human_gate")) or _has_governance_issue_code(
        issues if isinstance(issues, list) else [],
        code="HUMAN_REVIEW_REQUESTED",
    ) or requires_expert_review
    rights_violation_count = 0
    residual_dissent_count = 0
    normative_model_completeness = None
    normative_selected_policy = None
    normative_selected_option = None
    if normative_result is not None:
        rights_violation_count = sum(
            1
            for item in normative_result.rights_audit
            if item.status.value == "violated" and "soft_right" not in item.notes
        )
        residual_dissent_count = len(normative_result.residual_dissent)
        normative_model_completeness = normative_result.model_completeness.value
        normative_selected_policy = normative_result.selected_policy.value
        normative_selected_option = normative_result.selected_option.value

    return {
        "governance_verdict": governance_dict.get("verdict"),
        "blocker_count": issue_summary["blocker_count"],
        "warning_count": issue_summary["warning_count"],
        "info_count": issue_summary["info_count"],
        "transport_status": transport_dict.get("status", "not_run"),
        "transport_engine": transport_dict.get("identification_engine", "not_available"),
        "sensitivity_status": sensitivity_summary_dict.get("status"),
        "sensitivity_is_robust": sensitivity_content_dict.get("is_robust"),
        "icp_status": _nested_status(validity_checks_dict, "icp_invariance"),
        "proximal_status": _nested_status(validity_checks_dict, "proximal_bridge"),
        "recoverability_status": _nested_status(validity_checks_dict, "recoverability"),
        "pag_refinement_status": _nested_status(validity_checks_dict, "pag_refinement"),
        "requires_expert_review": requires_expert_review,
        "replay_readiness": replay_dict.get("readiness"),
        "replay_missing_inputs": list(replay_dict.get("missing_refs", []))
        if isinstance(replay_dict.get("missing_refs"), list)
        else [],
        "has_legal_report": has_legal_report,
        "legal_executed": has_legal_report,
        "has_distributional_report": has_distributional_report,
        "has_causal_report": has_causal_report,
        "has_abstraction_certificate": has_abstraction_certificate,
        "uncertainty_available": uncertainty_available,
        "human_review_needed": human_review_needed,
        "has_normative_arbitration": normative_result is not None,
        "normative_selected_policy": normative_selected_policy,
        "normative_selected_option": normative_selected_option,
        "normative_model_completeness": normative_model_completeness,
        "normative_residual_dissent_count": residual_dissent_count,
        "normative_rights_violation_count": rights_violation_count,
        "determinism_tier": replay_dict.get("determinism_tier"),
        "seed_source": replay_dict.get("seed_source"),
        "resolved_fidelity_level": resolved_fidelity_level,
        "contract_warnings": contract_warnings,
        "degraded_path_count": len(degraded_path_items),
        "degraded_reasons": [
            str(item.get("reason", "decision_packet_degraded")) for item in degraded_path_items
        ],
        "has_degraded_paths": bool(degraded_path_items),
    }


def _build_analysis_limits(packet_payload: dict[str, object]) -> dict[str, object]:
    diagnostics = packet_payload.get("diagnostics_summary")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    labels: list[str] = []
    contract_warnings = diagnostics_dict.get("contract_warnings")
    normalized_contract_warnings = (
        [str(item) for item in contract_warnings if isinstance(item, str)]
        if isinstance(contract_warnings, list)
        else []
    )

    transport_engine = diagnostics_dict.get("transport_engine")
    if isinstance(transport_engine, str) and transport_engine.startswith("simplified"):
        labels.append("transportability_simplified_engine")
    if diagnostics_dict.get("legal_executed") is False:
        labels.append("legal_not_run")
    if diagnostics_dict.get("requires_expert_review") is True:
        labels.append("expert_review_required")

    replay_readiness = diagnostics_dict.get("replay_readiness")
    if replay_readiness == ReplayReadiness.PARTIAL.value:
        labels.append("partial_replay_readiness")
    elif replay_readiness == ReplayReadiness.INCOMPLETE.value:
        labels.append("incomplete_replay_readiness")

    if diagnostics_dict.get("uncertainty_available") is False:
        labels.append("missing_uncertainty_artifact")
    if diagnostics_dict.get("sensitivity_is_robust") is False:
        labels.append("causal_sensitivity_fragile")
    if packet_payload.get("causal") is None:
        labels.append("causal_not_run")
    if packet_payload.get("distributional") is None:
        labels.append("distributional_not_run")
    if packet_payload.get("abm_alignment") is None:
        labels.append("abm_alignment_not_run")
    if any(
        warning.startswith("missing_runtime_mechanism_support:")
        for warning in normalized_contract_warnings
    ):
        labels.append("missing_runtime_mechanism_support")
    if diagnostics_dict.get("has_degraded_paths") is True:
        labels.append("decision_packet_degraded")

    return {
        "labels": labels,
        "transportability_simplified_engine": "transportability_simplified_engine" in labels,
        "legal_not_run": "legal_not_run" in labels,
        "expert_review_required": "expert_review_required" in labels,
        "partial_replay_readiness": "partial_replay_readiness" in labels,
        "incomplete_replay_readiness": "incomplete_replay_readiness" in labels,
        "missing_uncertainty_artifact": "missing_uncertainty_artifact" in labels,
        "missing_runtime_mechanism_support": "missing_runtime_mechanism_support" in labels,
        "causal_sensitivity_fragile": "causal_sensitivity_fragile" in labels,
        "decision_packet_degraded": "decision_packet_degraded" in labels,
    }


def _nested_status(payload: dict[str, object], key: str) -> str | None:
    nested = payload.get(key)
    nested_dict = nested if isinstance(nested, dict) else {}
    status = nested_dict.get("status")
    return str(status) if isinstance(status, str) else None


def _build_decision_validity_envelope(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    packet_payload: dict[str, object],
) -> DecisionValidityEnvelope:
    source_context = _extract_context_payload(
        state,
        "source_context",
        "source_context_profile",
    )
    target_context = _extract_context_payload(
        state,
        "target_context",
        "target_context_profile",
        "context_profile",
    )
    source_context_fingerprint = _fingerprint_payload(source_context)
    target_context_fingerprint = _fingerprint_payload(target_context)

    normative_basis = _build_normative_basis(packet_payload)
    data_basis = _build_data_basis(ctx, packet_payload)
    knowledge_basis = _build_knowledge_basis(ctx, packet_payload)
    transportability_basis = _build_transportability_basis(
        state=state,
        packet_payload=packet_payload,
        source_context_fingerprint=source_context_fingerprint,
        target_context_fingerprint=target_context_fingerprint,
    )
    normative_frame_payload = _load_normative_frame_payload(ctx, packet_payload)
    normative_policy = _path_get(packet_payload, ("tradeoff_certificate", "selected_policy"))

    policy_fingerprint = content_hash(
        json.dumps(
            {
                "trinity_bundle_ref": _path_get(packet_payload, ("inputs", INPUT_TRINITY_BUNDLE_REF)),
                "policy_summary": packet_payload.get("policy_summary"),
                "intervention_count": packet_payload.get("intervention_count"),
                "target_context_fingerprint": target_context_fingerprint,
                "normative_frame": normative_frame_payload,
                "normative_policy": normative_policy,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    decision_lineage_key = content_hash(
        json.dumps(
            {
                "trinity_bundle_ref": _path_get(packet_payload, ("inputs", INPUT_TRINITY_BUNDLE_REF)),
                "policy_summary": packet_payload.get("policy_summary"),
                "intervention_count": packet_payload.get("intervention_count"),
                "target_context_fingerprint": target_context_fingerprint,
                "normative_frame": normative_frame_payload,
                "normative_policy": normative_policy,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    return DecisionValidityEnvelope(
        decision_lineage_key=decision_lineage_key,
        policy_fingerprint=policy_fingerprint,
        source_context_fingerprint=source_context_fingerprint,
        target_context_fingerprint=target_context_fingerprint,
        normative_basis=normative_basis,
        data_basis=data_basis,
        knowledge_basis=knowledge_basis,
        transportability_basis=transportability_basis,
        watched_triggers=_build_watched_triggers(
            normative_basis=normative_basis,
            data_basis=data_basis,
            knowledge_basis=knowledge_basis,
            transportability_basis=transportability_basis,
        ),
    )


def _build_decision_validity_baseline(
    *,
    packet_payload: dict[str, object],
    envelope: DecisionValidityEnvelope,
) -> DecisionValidityEvaluation:
    triggers: list[DecisionTriggerRecord] = []
    reasons: list[str] = []

    diagnostics = packet_payload.get("diagnostics_summary")
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    governance = packet_payload.get("governance")
    governance_dict = governance if isinstance(governance, dict) else {}

    if bool(diagnostics_dict.get("human_review_needed")) or bool(
        diagnostics_dict.get("requires_expert_review")
    ):
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.EXPERT_REVIEW,
                status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
                reason="human_or_expert_review_required",
                details={
                    "human_review_needed": bool(diagnostics_dict.get("human_review_needed")),
                    "requires_expert_review": bool(
                        diagnostics_dict.get("requires_expert_review")
                    ),
                },
            )
        )
        reasons.append("human_or_expert_review_required")

    if str(governance_dict.get("verdict", "")).strip().lower() == "human_gate":
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.HUMAN_GATE,
                status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
                reason="governance_verdict_human_gate",
            )
        )
        reasons.append("governance_verdict_human_gate")

    data_summary = envelope.data_basis.summary
    freshness_level = str(data_summary.get("freshness_level", "")).strip().lower()
    if freshness_level and freshness_level != "fresh":
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.DATASET_SUPERSEDED,
                status=DecisionValidityStatus.STALE,
                reason=f"data_freshness_{freshness_level}",
                dependency_key=data_summary.get("dataset_dependency_key"),
                details={"freshness_level": freshness_level},
            )
        )
        reasons.append(f"data_freshness_{freshness_level}")
    if bool(data_summary.get("schema_drift")) or bool(data_summary.get("contract_drift")):
        drift_reason = (
            "schema_drift_detected"
            if bool(data_summary.get("schema_drift"))
            else "contract_drift_detected"
        )
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.HISTORICAL_SEMANTIC_REVISION,
                status=DecisionValidityStatus.STALE,
                reason=drift_reason,
            )
        )
        reasons.append(drift_reason)

    knowledge_summary = envelope.knowledge_basis.summary
    knowledge_freshness = str(knowledge_summary.get("freshness_status", "")).strip().lower()
    if knowledge_freshness in {"stale", "expired"}:
        triggers.append(
            DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.CONTRADICTING_EVIDENCE,
                status=DecisionValidityStatus.WARNING,
                reason=f"knowledge_bundle_{knowledge_freshness}",
                dependency_key=knowledge_summary.get("knowledge_dependency_key"),
                details={"freshness_status": knowledge_freshness},
            )
        )
        reasons.append(f"knowledge_bundle_{knowledge_freshness}")

    status = DecisionValidityStatus.ACTIVE
    for trigger in triggers:
        status = _max_validity_status(status, trigger.status)
    normative_summary = envelope.normative_basis.summary
    if str(normative_summary.get("normative_model_completeness", "")).strip().lower() == "partial":
        status = _max_validity_status(status, DecisionValidityStatus.WARNING)
        reasons.append("normative_model_partial")
    residual_dissent_count = normative_summary.get("normative_residual_dissent_count")
    if isinstance(residual_dissent_count, int) and residual_dissent_count > 0:
        status = _max_validity_status(status, DecisionValidityStatus.WARNING)
        reasons.append("normative_residual_dissent")

    return DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=status,
        reasons=_dedupe_strings(reasons),
        triggers=triggers,
        dependency_keys=envelope.dependency_keys(),
        recommended_action=_recommended_action(status),
        review_required=status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
    )


def _build_normative_basis(packet_payload: dict[str, object]) -> DecisionBasisSection:
    dependencies: list[DecisionDependencyRef] = []
    summary: dict[str, object] = {}
    norm_pack_ref = _path_get(packet_payload, ("inputs", INPUT_NORM_PACK_REF))
    legal_report_ref = _path_get(packet_payload, ("artifacts", REPORT_LEGAL_REPORT_REF))
    normative_result_ref = _path_get(
        packet_payload,
        ("artifacts", ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF),
    )
    if isinstance(norm_pack_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.NORM_PACK,
                f"norm_pack:{norm_pack_ref}",
                artifact_id=norm_pack_ref,
                label="norm_pack_ref",
            )
        )
        summary["norm_pack_ref"] = norm_pack_ref
    if isinstance(legal_report_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.LEGAL_REPORT,
                f"legal_report:{legal_report_ref}",
                artifact_id=legal_report_ref,
                label="legal_report_ref",
            )
        )
        summary["legal_report_ref"] = legal_report_ref
    if isinstance(normative_result_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.NORMATIVE_ARBITRATION,
                f"normative_arbitration:{normative_result_ref}",
                artifact_id=normative_result_ref,
                label="normative_arbitration_result_ref",
            )
        )
        summary["normative_arbitration_result_ref"] = normative_result_ref
    governance = packet_payload.get("governance")
    if isinstance(governance, dict):
        summary["governance_verdict"] = governance.get("verdict")
    diagnostics = packet_payload.get("diagnostics_summary")
    if isinstance(diagnostics, dict):
        summary["legal_executed"] = bool(diagnostics.get("legal_executed"))
        summary["normative_selected_policy"] = diagnostics.get("normative_selected_policy")
        summary["normative_selected_option"] = diagnostics.get("normative_selected_option")
        summary["normative_model_completeness"] = diagnostics.get(
            "normative_model_completeness"
        )
        summary["normative_residual_dissent_count"] = diagnostics.get(
            "normative_residual_dissent_count"
        )
        summary["normative_rights_violation_count"] = diagnostics.get(
            "normative_rights_violation_count"
        )
    return DecisionBasisSection(dependencies=dependencies, summary=summary)


def _build_data_basis(
    ctx: ExecutionContext,
    packet_payload: dict[str, object],
) -> DecisionBasisSection:
    dependencies: list[DecisionDependencyRef] = []
    summary: dict[str, Any] = {}
    data_snapshot_ref = _path_get(packet_payload, ("inputs", INPUT_DATA_SNAPSHOT_REF))
    binding_report_ref = _path_get(packet_payload, ("artifacts", ARTIFACT_INPUT_BINDING_REPORT_REF))
    if isinstance(data_snapshot_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.DATA_SNAPSHOT,
                f"data_snapshot:{data_snapshot_ref}",
                artifact_id=data_snapshot_ref,
                label="data_snapshot_ref",
            )
        )
        summary["data_snapshot_ref"] = data_snapshot_ref
    if isinstance(binding_report_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.INPUT_BINDING_REPORT,
                f"input_binding_report:{binding_report_ref}",
                artifact_id=binding_report_ref,
                label="input_binding_report_ref",
            )
        )
        summary["input_binding_report_ref"] = binding_report_ref

    snapshot_payload = _load_json_payload_by_ref(
        ctx,
        data_snapshot_ref,
        packet_payload=packet_payload,
        operation="load_decision_basis_data_snapshot",
        reason="decision_basis_data_snapshot_load_failed",
        artifact_key=INPUT_DATA_SNAPSHOT_REF,
    )
    if snapshot_payload is None:
        return DecisionBasisSection(dependencies=dependencies, summary=summary)

    try:
        snapshot = DataSnapshot.model_validate(snapshot_payload)
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        _record_decision_packet_section_degraded(
            packet_payload,
            operation="validate_decision_basis_data_snapshot",
            reason="decision_basis_data_snapshot_validate_failed",
            exc=exc,
            artifact_id=data_snapshot_ref,
            artifact_key=INPUT_DATA_SNAPSHOT_REF,
        )
        return DecisionBasisSection(dependencies=dependencies, summary=summary)

    summary["stats"] = dict(snapshot.stats)
    summary["notes"] = list(snapshot.notes)
    summary["pii_scan_summary"] = snapshot.pii_scan_summary
    if snapshot.quality_report_ref is not None:
        quality_report_ref = str(snapshot.quality_report_ref.artifact_id)
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.QUALITY_REPORT,
                f"quality_report:{quality_report_ref}",
                artifact_id=quality_report_ref,
                label="quality_report_ref",
            )
        )
        summary["quality_report_ref"] = quality_report_ref
        quality_payload = _load_json_payload_by_ref(
            ctx,
            quality_report_ref,
            packet_payload=packet_payload,
            operation="load_decision_basis_quality_report",
            reason="decision_basis_quality_report_load_failed",
            artifact_key="quality_report_ref",
        )
        if isinstance(quality_payload, dict):
            dataset_id = quality_payload.get("dataset_id")
            schema_id = quality_payload.get("schema_id")
            if isinstance(dataset_id, str) and dataset_id:
                dataset_dependency = _dependency_ref(
                    DecisionDependencyKind.DATASET,
                    f"dataset:{dataset_id}",
                    label=dataset_id,
                )
                dependencies.append(dataset_dependency)
                summary["dataset_id"] = dataset_id
                summary["dataset_dependency_key"] = dataset_dependency.key
            if isinstance(schema_id, str) and schema_id:
                dependencies.append(
                    _dependency_ref(
                        DecisionDependencyKind.DATA_SCHEMA,
                        f"data_schema:{schema_id}",
                        label=schema_id,
                    )
                )
                summary["schema_id"] = schema_id
            freshness = quality_payload.get("freshness_status")
            if isinstance(freshness, dict):
                summary["freshness_level"] = freshness.get("level")
                summary["is_fresh"] = freshness.get("is_fresh")
                summary["data_age_seconds"] = freshness.get("data_age_seconds")
                summary["freshness_message"] = freshness.get("message")
            quality_flags = quality_payload.get("quality_flags")
            if isinstance(quality_flags, list):
                summary["quality_flags"] = [str(item) for item in quality_flags]
            violations = quality_payload.get("violations")
            if isinstance(violations, list):
                messages = [
                    str(item.get("message", "")).lower()
                    for item in violations
                    if isinstance(item, dict)
                ]
                summary["schema_drift"] = any("schema drift" in msg for msg in messages)
                summary["contract_drift"] = any(
                    "contract drift" in msg or "supersed" in msg for msg in messages
                )

    return DecisionBasisSection(
        dependencies=_dedupe_dependency_refs(dependencies),
        summary=summary,
    )


def _build_knowledge_basis(
    ctx: ExecutionContext,
    packet_payload: dict[str, object],
) -> DecisionBasisSection:
    dependencies: list[DecisionDependencyRef] = []
    summary: dict[str, Any] = {}
    knowledge_bundle_ref = _path_get(packet_payload, ("inputs", INPUT_KNOWLEDGE_BUNDLE_REF))
    research_intent_ref = _path_get(packet_payload, ("inputs", INPUT_RESEARCH_INTENT_REF))
    if isinstance(knowledge_bundle_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.KNOWLEDGE_BUNDLE,
                f"knowledge_bundle:{knowledge_bundle_ref}",
                artifact_id=knowledge_bundle_ref,
                label="knowledge_bundle_ref",
            )
        )
        summary["knowledge_bundle_ref"] = knowledge_bundle_ref
        summary["knowledge_dependency_key"] = f"knowledge_bundle:{knowledge_bundle_ref}"
    if isinstance(research_intent_ref, str):
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.RESEARCH_INTENT,
                f"research_intent:{research_intent_ref}",
                artifact_id=research_intent_ref,
                label="research_intent_ref",
            )
        )
    for artifact_key in (
        ARTIFACT_CAUSAL_REPORT_REF,
        ARTIFACT_CAUSAL_ENSEMBLE_REF,
        ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ):
        artifact_ref = _path_get(packet_payload, ("artifacts", artifact_key))
        if isinstance(artifact_ref, str):
            dependencies.append(
                _dependency_ref(
                    DecisionDependencyKind.CAUSAL_EVIDENCE,
                    f"causal_evidence:{artifact_ref}",
                    artifact_id=artifact_ref,
                    label=artifact_key,
                )
            )

    bundle_payload = _load_json_payload_by_ref(
        ctx,
        knowledge_bundle_ref,
        packet_payload=packet_payload,
        operation="load_decision_basis_knowledge_bundle",
        reason="decision_basis_knowledge_bundle_load_failed",
        artifact_key=INPUT_KNOWLEDGE_BUNDLE_REF,
    )
    if isinstance(bundle_payload, dict):
        freshness_payload = bundle_payload.get("freshness")
        if isinstance(freshness_payload, dict):
            try:
                freshness = FreshnessMetadata.model_validate(freshness_payload)
                summary["freshness_status"] = freshness.compute_status().value
                summary["source_freshness_at"] = (
                    freshness.source_freshness_at.isoformat()
                    if freshness.source_freshness_at is not None
                    else None
                )
                summary["enrichment_count"] = freshness.enrichment_count
            except _DECISION_PACKET_LOAD_ERRORS as exc:
                _record_decision_packet_section_degraded(
                    packet_payload,
                    operation="validate_decision_basis_knowledge_freshness",
                    reason="decision_basis_knowledge_freshness_validate_failed",
                    exc=exc,
                    artifact_id=knowledge_bundle_ref,
                    artifact_key=INPUT_KNOWLEDGE_BUNDLE_REF,
                )
                summary["freshness_status"] = "unknown"
        notes = bundle_payload.get("notes")
        if isinstance(notes, list):
            summary["notes"] = [str(item) for item in notes]

    return DecisionBasisSection(
        dependencies=_dedupe_dependency_refs(dependencies),
        summary=summary,
    )


def _build_transportability_basis(
    *,
    state: ExperimentState,
    packet_payload: dict[str, object],
    source_context_fingerprint: str | None,
    target_context_fingerprint: str | None,
) -> DecisionBasisSection:
    dependencies: list[DecisionDependencyRef] = []
    summary: dict[str, Any] = {}
    causal = packet_payload.get("causal")
    causal_dict = causal if isinstance(causal, dict) else {}
    transport = causal_dict.get("transportability_summary")
    transport_dict = dict(transport) if isinstance(transport, dict) else {}
    if transport_dict:
        summary.update(transport_dict)
    summary["source_context_fingerprint"] = source_context_fingerprint
    summary["target_context_fingerprint"] = target_context_fingerprint
    assumptions = state.params.get("transportability_assumptions")
    if isinstance(assumptions, list):
        summary["assumptions"] = list(assumptions)
    elif isinstance(assumptions, dict):
        summary["assumptions"] = assumptions

    capability_hash = transport_dict.get("capability_hash")
    if isinstance(capability_hash, str) and capability_hash:
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.TRANSPORTABILITY,
                f"transportability_capability:{capability_hash}",
                label="transportability_capability_hash",
            )
        )
    if target_context_fingerprint is not None:
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.CONTEXT_PROFILE,
                f"context_profile:{target_context_fingerprint}",
                label="target_context",
            )
        )
    if source_context_fingerprint is not None:
        dependencies.append(
            _dependency_ref(
                DecisionDependencyKind.CONTEXT_PROFILE,
                f"context_profile:{source_context_fingerprint}",
                label="source_context",
            )
        )

    return DecisionBasisSection(
        dependencies=_dedupe_dependency_refs(dependencies),
        summary=summary,
    )


def _build_watched_triggers(
    *,
    normative_basis: DecisionBasisSection,
    data_basis: DecisionBasisSection,
    knowledge_basis: DecisionBasisSection,
    transportability_basis: DecisionBasisSection,
) -> list[DecisionTriggerSpec]:
    return [
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.LAW_CHANGE,
            dependency_keys=[item.key for item in normative_basis.dependencies],
            description="Watch norm/legal dependencies for change or hard invalidation.",
        ),
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.DATASET_SUPERSEDED,
            dependency_keys=[item.key for item in data_basis.dependencies],
            description="Watch dataset supersede and cache invalidation signals.",
        ),
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.HISTORICAL_SEMANTIC_REVISION,
            dependency_keys=[item.key for item in data_basis.dependencies],
            description="Watch schema or semantic revision of historical data.",
        ),
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.CONTRADICTING_EVIDENCE,
            dependency_keys=[item.key for item in knowledge_basis.dependencies],
            description="Watch contradictory evidence, retractions, and stale scholar bundles.",
        ),
        DecisionTriggerSpec(
            trigger_type=DecisionTriggerType.CONTEXT_PROFILE_DRIFT,
            dependency_keys=[item.key for item in transportability_basis.dependencies],
            description="Watch source/target context profile drift.",
        ),
    ]


def _dependency_ref(
    kind: DecisionDependencyKind,
    key: str,
    *,
    artifact_id: str | None = None,
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DecisionDependencyRef:
    return DecisionDependencyRef(
        kind=kind,
        key=key,
        artifact_id=artifact_id,
        label=label,
        metadata=metadata or {},
    )


def _dedupe_dependency_refs(
    values: list[DecisionDependencyRef],
) -> list[DecisionDependencyRef]:
    deduped: list[DecisionDependencyRef] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in values:
        key = (item.kind.value, item.key, item.artifact_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped

def _load_json_payload_by_ref(
    ctx: ExecutionContext,
    ref_value: str | None,
    *,
    packet_payload: dict[str, object] | None = None,
    operation: str | None = None,
    reason: str | None = None,
    artifact_key: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(ref_value, str) or not ref_value:
        return None
    try:
        artifact_id = ArtifactID.model_validate(ref_value)
        payload = from_canonical_bytes(ctx.store.get_bytes(artifact_id))
    except _DECISION_PACKET_LOAD_ERRORS as exc:
        if operation is not None and reason is not None:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation=operation,
                reason=reason,
                exc=exc,
                artifact_id=ref_value,
                artifact_key=artifact_key,
            )
        return None
    if isinstance(payload, dict):
        return payload
    if operation is not None and reason is not None:
        _record_decision_packet_section_degraded(
            packet_payload,
            operation=operation,
            reason=reason,
            exc=TypeError("artifact payload must decode to a JSON object"),
            artifact_id=ref_value,
            artifact_key=artifact_key,
        )
    return None


def _load_normative_frame_payload(
    ctx: ExecutionContext,
    packet_payload: dict[str, object],
) -> dict[str, Any] | None:
    trinity_bundle_ref = _path_get(packet_payload, ("inputs", INPUT_TRINITY_BUNDLE_REF))
    bundle = _load_json_payload_by_ref(
        ctx,
        trinity_bundle_ref,
        packet_payload=packet_payload,
        operation="load_decision_basis_trinity_bundle",
        reason="decision_basis_trinity_bundle_load_failed",
        artifact_key=INPUT_TRINITY_BUNDLE_REF,
    )
    if bundle is None:
        return None
    problem_frame = bundle.get("problem_frame")
    if not isinstance(problem_frame, dict):
        return None
    normative_frame = problem_frame.get("normative_frame")
    return normative_frame if isinstance(normative_frame, dict) else None

def _max_validity_status(
    left: DecisionValidityStatus,
    right: DecisionValidityStatus,
) -> DecisionValidityStatus:
    order = {
        DecisionValidityStatus.ACTIVE: 0,
        DecisionValidityStatus.WARNING: 1,
        DecisionValidityStatus.STALE: 2,
        DecisionValidityStatus.REQUIRES_HUMAN_REVIEW: 3,
        DecisionValidityStatus.SUPERSEDED: 4,
        DecisionValidityStatus.REVOKED: 5,
    }
    return right if order[right] > order[left] else left


def _summarize_governance_issues(issues: list[dict[str, object]]) -> dict[str, int]:
    blocker_count = 0
    warning_count = 0
    info_count = 0
    for issue in issues:
        severity = str(issue.get("severity", "")).strip().lower()
        if severity == "blocker":
            blocker_count += 1
        elif severity == "warning":
            warning_count += 1
        elif severity == "info":
            info_count += 1
    return {
        "blocker_count": blocker_count,
        "warning_count": warning_count,
        "info_count": info_count,
    }


def _has_governance_issue_code(issues: list[dict[str, object]], *, code: str) -> bool:
    for issue in issues:
        if str(issue.get("code", "")).strip() == code:
            return True
    return False


def _collect_contract_warnings(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> list[str]:
    warnings: list[str] = []
    link_report_ref = state.reports_index.get(REPORT_LINK_REPORT_REF)
    if link_report_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(link_report_ref.artifact_id))
        except _DECISION_PACKET_LOAD_ERRORS:
            payload = None
        if isinstance(payload, dict):
            for issue in payload.get("issues", []):
                if not isinstance(issue, dict):
                    continue
                if str(issue.get("severity", "")).strip().lower() != "warning":
                    continue
                code = issue.get("code")
                if isinstance(code, str):
                    _append_unique(warnings, code)

    compile_report_ref = state.reports_index.get(REPORT_COMPILE_REPORT_REF)
    if compile_report_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(compile_report_ref.artifact_id))
        except _DECISION_PACKET_LOAD_ERRORS:
            payload = None
        if isinstance(payload, dict):
            for note in payload.get("notes", []):
                if not isinstance(note, str):
                    continue
                normalized = _normalize_compile_warning(note)
                if normalized is not None:
                    _append_unique(warnings, normalized)

    return warnings


def _normalize_compile_warning(note: str) -> str | None:
    if note.startswith("link_warning:"):
        return note.split(":", 1)[1]
    if note.startswith("missing_runtime_mechanism_support:"):
        return note
    return None


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _load_resolved_fidelity_level(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> str | None:
    lowered_ir_ref = state.artifacts_index.get(ARTIFACT_LOWERED_IR_REF)
    if lowered_ir_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(lowered_ir_ref.artifact_id))
    except _DECISION_PACKET_LOAD_ERRORS:
        return None
    if not isinstance(payload, dict):
        return None
    fidelity = payload.get("policy_fidelity_level")
    return fidelity if isinstance(fidelity, str) else None


def _build_manifest_inputs(packet_payload: dict[str, object]) -> list[InputRef]:
    collected: dict[tuple[str, str], InputRef] = {}
    for section_name, prefix in (
        ("inputs", "input"),
        ("artifacts", "artifact"),
        ("runtime_contracts", "runtime_contracts"),
        ("decision_validity_envelope", "decision_validity_envelope"),
        ("decision_validity_baseline", "decision_validity_baseline"),
        ("uncertainty", "uncertainty"),
        ("hte", "hte"),
        ("targeting", "targeting"),
        ("abm_alignment", "abm_alignment"),
        ("abstraction_certificate", "abstraction_certificate"),
        ("backtest", "backtest"),
        ("distributional", "distributional"),
        ("econometrics", "econometrics"),
        ("norm_impact", "norm_impact"),
        ("sensitivity", "sensitivity"),
        ("stress_test", "stress_test"),
    ):
        section = packet_payload.get(section_name)
        _collect_manifest_refs(section, prefix, collected)
    return list(collected.values())


def _collect_manifest_refs(
    value: object,
    role_prefix: str,
    collected: dict[tuple[str, str], InputRef],
) -> None:
    if isinstance(value, str):
        try:
            artifact_id = ArtifactID.model_validate(value)
        except (ValidationError, ValueError, TypeError):
            return
        collected[(artifact_id.hex, role_prefix)] = InputRef(
            artifact_id=artifact_id,
            role=role_prefix,
        )
        return

    if isinstance(value, list):
        for idx, nested in enumerate(value):
            _collect_manifest_refs(nested, f"{role_prefix}[{idx}]", collected)
        return

    if isinstance(value, dict):
        for key, nested in value.items():
            _collect_manifest_refs(nested, f"{role_prefix}.{key}", collected)


def _build_uncertainty_section(
    ctx: ExecutionContext,
    state_inputs: dict[str, ArtifactRef],
    state_artifacts: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    envelope_refs: set[str] = set()
    legacy_bounds_refs: set[str] = set()
    output_envelope_refs: dict[str, str] = {}
    warnings: list[str] = []

    data_snapshot_ref = state_inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(data_snapshot_ref.artifact_id))
            snapshot = DataSnapshot.model_validate(payload)
            if snapshot.uncertainty_envelope_ref is not None:
                envelope_refs.add(str(snapshot.uncertainty_envelope_ref.artifact_id))
            if snapshot.uncertainty_ref is not None:
                legacy_bounds_refs.add(str(snapshot.uncertainty_ref.artifact_id))
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            warnings.append("data_snapshot_uncertainty_parse_failed")
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_uncertainty_data_snapshot",
                reason="uncertainty_data_snapshot_load_failed",
                exc=exc,
                ref=data_snapshot_ref,
                artifact_key=INPUT_DATA_SNAPSHOT_REF,
            )

    simulation_result_ref = state_artifacts.get(ARTIFACT_SIMULATION_RESULT_REF)
    if simulation_result_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(simulation_result_ref.artifact_id))
            sim_result = SimulationResult.model_validate(payload)
            if sim_result.uncertainty_envelopes:
                for metric_id, ref in sim_result.uncertainty_envelopes.items():
                    ref_str = str(ref.artifact_id)
                    output_envelope_refs[str(metric_id)] = ref_str
                    envelope_refs.add(ref_str)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            warnings.append("simulation_result_uncertainty_parse_failed")
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_uncertainty_simulation_result",
                reason="uncertainty_simulation_result_load_failed",
                exc=exc,
                ref=simulation_result_ref,
                artifact_key=ARTIFACT_SIMULATION_RESULT_REF,
            )

    causal_env_ref = state_artifacts.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    if causal_env_ref is not None:
        envelope_refs.add(str(causal_env_ref.artifact_id))
    econometric_env_ref = state_artifacts.get(ARTIFACT_ECONOMETRIC_ENVELOPE_REF)
    if econometric_env_ref is not None:
        envelope_refs.add(str(econometric_env_ref.artifact_id))

    return {
        "envelope_refs": sorted(envelope_refs),
        "legacy_bounds_refs": sorted(legacy_bounds_refs),
        "output_envelope_refs": output_envelope_refs,
        "causal_envelope_ref": str(causal_env_ref.artifact_id)
        if causal_env_ref is not None
        else None,
        "econometric_envelope_ref": str(econometric_env_ref.artifact_id)
        if econometric_env_ref is not None
        else None,
        "envelope_count": len(envelope_refs),
        "legacy_bounds_count": len(legacy_bounds_refs),
        "output_envelope_count": len(output_envelope_refs),
        "warnings": warnings,
    }


def _build_uncertainty_bounds(
    ctx: ExecutionContext,
    uncertainty_section: dict[str, object],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, float] | None:
    output_refs = uncertainty_section.get("output_envelope_refs")
    if not isinstance(output_refs, dict):
        return None

    bounds: dict[str, float] = {}
    for metric_id, ref_str in output_refs.items():
        if not isinstance(metric_id, str) or not isinstance(ref_str, str):
            continue
        try:
            ref = UncertaintyEnvelopeRef(artifact_id=ArtifactID.model_validate(ref_str))
            env = load_uncertainty_envelope(ctx.store, ref)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_uncertainty_output_envelope",
                reason="uncertainty_output_envelope_load_failed",
                exc=exc,
                artifact_id=ref_str,
                artifact_key=f"uncertainty.output_envelope_refs.{metric_id}",
            )
            continue
        bounds[f"{metric_id}_lower"] = float(env.confidence_interval[0])
        bounds[f"{metric_id}_upper"] = float(env.confidence_interval[1])
        bounds[f"{metric_id}_point"] = float(env.point_estimate)
        if env.confidence_level is not None:
            bounds[f"{metric_id}_ci_level"] = float(env.confidence_level)

    causal_ref = uncertainty_section.get("causal_envelope_ref")
    if isinstance(causal_ref, str):
        try:
            ref = UncertaintyEnvelopeRef(artifact_id=ArtifactID.model_validate(causal_ref))
            env = load_uncertainty_envelope(ctx.store, ref)
            bounds["causal_effect_lower"] = float(env.confidence_interval[0])
            bounds["causal_effect_upper"] = float(env.confidence_interval[1])
            bounds["causal_effect_point"] = float(env.point_estimate)
            if env.confidence_level is not None:
                bounds["causal_effect_ci_level"] = float(env.confidence_level)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_uncertainty_causal_envelope",
                reason="uncertainty_causal_envelope_load_failed",
                exc=exc,
                artifact_id=causal_ref,
                artifact_key="uncertainty.causal_envelope_ref",
            )

    econometric_ref = uncertainty_section.get("econometric_envelope_ref")
    if isinstance(econometric_ref, str):
        try:
            ref = UncertaintyEnvelopeRef(artifact_id=ArtifactID.model_validate(econometric_ref))
            env = load_uncertainty_envelope(ctx.store, ref)
            bounds["econometric_effect_lower"] = float(env.confidence_interval[0])
            bounds["econometric_effect_upper"] = float(env.confidence_interval[1])
            bounds["econometric_effect_point"] = float(env.point_estimate)
            if env.confidence_level is not None:
                bounds["econometric_effect_ci_level"] = float(env.confidence_level)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_uncertainty_econometric_envelope",
                reason="uncertainty_econometric_envelope_load_failed",
                exc=exc,
                artifact_id=econometric_ref,
                artifact_key="uncertainty.econometric_envelope_ref",
            )

    return bounds or None


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
            "test_label": describe_test_id(significance.test_id),
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
            "test_label": describe_test_id(significance.test_id),
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
                "test_label": describe_test_id(significance.test_id),
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
