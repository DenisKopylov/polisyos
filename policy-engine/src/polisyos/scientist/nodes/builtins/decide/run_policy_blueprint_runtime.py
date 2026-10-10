"""Public decide run policy blueprint runtime module API."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods.catalog.causal.strategic import (
    persist_strategic_solve_artifacts,
    solve_strategic_response,
    strategic_result_summary,
)
from polisyos.foundry.validation import normalize_phase2_artifact_family
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    load_abstraction_certificate,
)
from polisyos.ir.analytics.cross_graph import CrossGraphEvidenceProfile, EvidenceSourceKind
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicSCM,
    load_strategic_payoff_table,
    persist_strategic_payoff_table,
    persist_strategic_scm,
)
from polisyos.ir.artifacts import InputRef as IRInputRef
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.pdc import WorldModelRecord
from polisyos.scientist.evidence.sources import (
    build_path_source_status,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.backtesting.adversarial import (
    ABSTRACTION_LEAKAGE_SUITE_ID,
    MULTIPLICITY_DISCLOSURE_SUITE_ID,
    PHASE_D4_ROTATION_GROUP,
    STRATEGIC_GAMING_SUITE_ID,
    run_phase_d4_challenge_suites,
)
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.methods.search.actionable_side_information import resolve_actionable_store
from polisyos.scientist.methods.search.adversarial import (
    PlatformMetaEvaluationInput,
    PlatformMetaEvaluator,
    load_platform_meta_evaluation_report,
    persist_platform_meta_evaluation_report,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.calibration_report import (
    build_calibration_report,
    load_funnel_calibration_report,
    persist_funnel_calibration_report,
)
from polisyos.scientist.methods.search.funnel.level0_static import Level0StaticValidator
from polisyos.scientist.methods.search.funnel.level1_heuristic import Level1CheapHeuristic
from polisyos.scientist.methods.search.funnel.level2_causal import Level2CausalPlausibility
from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.funnel.level6_promotion import Level6PromotionStage
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator, FunnelOutcome
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.methods.search.lessons import LessonRegistry
from polisyos.scientist.methods.search.promotion_evidence import (
    PromotionEvidenceBundle,
    load_promotion_evidence_bundle,
    persist_promotion_evidence_bundle,
)
from polisyos.scientist.methods.search.stages import CorrelationTracker
from polisyos.scientist.methods.search.voi_scheduler import persist_voi_run_report
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    StrategicRuntimeOutput as _SharedStrategicRuntimeOutput,
)
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    build_blocked_strategic_summary as _shared_build_blocked_strategic_summary,
)
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    build_runtime_abstraction_metadata as _shared_build_runtime_abstraction_metadata,
)
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    load_runtime_abstraction_certificate as _shared_load_runtime_abstraction_certificate,
)
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    persist_runtime_strategic_artifacts as _shared_persist_runtime_strategic_artifacts,
)
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    resolve_baseline_policy_value as _shared_selection_baseline_policy_value,
)
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    resolve_existing_strategic_output as _shared_resolve_existing_strategic_output,
)
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import _is_policy_mode
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_benchmarks import (
    _dedupe_phase_d4_rotating_refs,
    _expected_policy_loop_id,
    _load_benchmark_if_present,
    _maybe_register_benchmark_evaluation,
    _register_runtime_benchmark_inputs,
    _resolve_benchmark_scope,
    _resolve_policy_runtime_source_statuses,
    _run_and_register_phase_d4_challenge_suites,
    build_runtime_funnel_context,
    prepare_runtime_benchmark_evidence,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _persist_policy_runtime_work_packet,
    prepare_runtime_session,
    run_runtime_funnel,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
    _ensure_stress_test_report,
    _extract_level5_gate,
    _load_stress_test_report,
    _merge_stress_test_reports,
    _recompute_stress_test_report,
    _serialize_funnel_outcome,
    finalize_runtime_session,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_strategy import (
    _candidate_search_payload,
    _ensure_calibration_report,
    _persist_runtime_strategic_artifacts,
    _resolve_runtime_correlation_metrics,
    _resolve_runtime_correlation_tracker,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_request import (
    resolve_policy_runtime_request,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_state import (
    load_predictive_voi_scheduler,
    maybe_artifact_ref,
    persist_predictive_voi_scheduler,
    policy_runtime_input_signature,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    ProductionPolicyEvaluationBackend,
    build_policy_runtime_evaluation,
    build_selection_benchmark_evaluation,
    build_vulnerabilities,
    load_benchmark_evaluation,
    load_causal_report,
    load_distributional_report_for_state,
    load_governance_report,
    persist_funnel_executed_work_packet,
    persist_policy_evaluation_vector,
    persist_policy_evaluation_vector_to_store,
    run_promotion_with_evidence,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF,
    ARTIFACT_PLATFORM_META_EVALUATION_REPORT_REF,
    ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF,
    ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    ARTIFACT_VOI_RUN_REPORT_REF,
    INPUT_CALIBRATION_REPORT_REF,
    INPUT_PROMOTION_EVIDENCE_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.workflows.engine_base import WorkflowEngine
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.replay.verification import ReplayRegistry, verify_and_persist_replay_bundle

_POLICY_RUNTIME_VALIDATION_ERRORS = (TypeError, ValidationError, ValueError)
_POLICY_RUNTIME_LOAD_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_policy_blueprint_runtime@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Policy Blueprint Runtime",
    description="Execute the blueprint-native L0-L6 funnel and promotion runtime for policy mode.",
    tags=["builtin", "decide", "policy_design", "funnel", "promotion"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "last_checkpoint_ref",
        "params.workflow_id",
        "params.policy_mode",
        "params.policy_candidate_schema",
        "params.policy_candidate_ref",
        "params.policy_evaluation",
        "params.policy_loop_id",
        "params.correlation_metrics",
        "params.calibration_drift_detected",
        "params.hidden_holdout_evaluation_ref",
        "params.evidence_sources",
        "params.prior_knowledge_bundle_ref",
        "params.discovery_artifact_bundle_ref",
        "params.rotating_challenge_evaluation_refs",
        "params.replay_bundle_ref",
        "params.strategic_scm",
        "params.strategic_payoff_tables",
        "params.macro_strategic_payoff_tables",
        "params.performative_loop_spec",
        "inputs.promotion_evidence_bundle_ref",
        "inputs.prior_knowledge_bundle_ref",
        "inputs.calibration_report_ref",
        "artifacts_index",
        "reports_index",
    ],
    state_writes=[
        "params.funnel_outcome",
        "params._funnel_outcome",
        "params.policy_level5_gate",
        "params.policy_evaluation",
        "params.policy_evaluation_ref",
        "params.policy_promotion_result",
        "params.judge_verdict",
        "params.decision_readiness_contract",
        "params.promotion_decision",
        "params.policy_runtime_source_statuses",
        "params.promotion_evidence_bundle_ref",
        "params.audit_refs",
        "params.actionable_side_information_refs",
        "params.voi_run_report_ref",
        "params.strategic_response",
        f"artifacts_index.{ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF}",
        f"artifacts_index.{ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_PLATFORM_META_EVALUATION_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_STRESS_TEST_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_STRATEGIC_SCM_REF}",
        f"artifacts_index.{ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_DECISION_READINESS_CONTRACT_REF}",
        f"artifacts_index.{ARTIFACT_VOI_RUN_REPORT_REF}",
    ],
    produces=[
        ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF,
        ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF,
        ARTIFACT_PLATFORM_META_EVALUATION_REPORT_REF,
        ARTIFACT_STRESS_TEST_REPORT_REF,
        ARTIFACT_STRATEGIC_SCM_REF,
        ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
        ARTIFACT_DECISION_READINESS_CONTRACT_REF,
        ARTIFACT_VOI_RUN_REPORT_REF,
    ],
)

_UNSET = object()


class _PolicyRuntimeWorkflowEngine(WorkflowEngine):
    """Workflow adapter that materializes fidelity-specific policy runtime outputs."""

    def __init__(self, *, fidelity: str, backend: ProductionPolicyEvaluationBackend) -> None:
        self._fidelity = fidelity
        self._backend = backend

    def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        candidate = initial_state.get("policy_candidate_schema")
        if not isinstance(candidate, PolicyCandidateSchema):
            raise ValueError("policy_candidate_schema is required for policy runtime workflow.")
        evaluation_attempt_id = str(uuid4())
        runtime_artifact = self._backend.evaluate(
            candidate,
            fidelity=self._fidelity,
            simulation_metrics=initial_state.get("simulation_metrics"),
            uncertainty=initial_state.get("uncertainty_envelope"),
            distributional_report=initial_state.get("distributional_report"),
            causal_effect_report=initial_state.get("causal_effect_report"),
            cross_graph_profile=initial_state.get("cross_graph_profile"),
            governance_report=initial_state.get("governance_report"),
            ambiguity_certificate=initial_state.get("ambiguity_certificate"),
        )
        work_packet_ref, work_packet_unavailability_reason = _persist_policy_runtime_work_packet(
            initial_state=initial_state,
            fidelity=self._fidelity,
            evaluation_attempt_id=evaluation_attempt_id,
            runtime_artifact=runtime_artifact,
        )
        feedback: dict[str, Any] = {
            "verdict": "APPROVE" if runtime_artifact.evaluation_vector.feasible else "REJECT",
            "fidelity_engine": self._fidelity,
            "blocking_reasons": list(runtime_artifact.evaluation_vector.blocking_reasons),
            "routing_source": f"policy_runtime_{self._fidelity}",
            "policy_evaluation": runtime_artifact.evaluation_vector.model_dump(mode="json"),
            "policy_runtime_fidelity": self._fidelity,
            "policy_runtime_backend_kind": runtime_artifact.provenance.backend_kind,
            "policy_runtime_promotable_source": runtime_artifact.provenance.promotable_source,
            "policy_runtime_degradation_mode": runtime_artifact.provenance.degradation_mode,
            "policy_runtime_source_components": list(runtime_artifact.provenance.source_components),
            "policy_runtime_notes": list(runtime_artifact.provenance.notes),
            "policy_runtime_input_signature": str(
                initial_state.get("pinned_input_signature") or ""
            ),
            "policy_runtime_work_packet_status": (
                "available" if work_packet_ref is not None else "unavailable"
            ),
        }
        if work_packet_ref is not None:
            feedback["policy_runtime_work_packet_ref"] = work_packet_ref.model_dump(mode="json")
        elif work_packet_unavailability_reason is not None:
            feedback["policy_runtime_work_packet_unavailability_reason"] = (
                work_packet_unavailability_reason
            )
        return {
            "simulation_results": runtime_artifact.simulation_results,
            "feedback": feedback,
            "policy_evaluation": runtime_artifact.evaluation_vector.model_dump(mode="json"),
        }

    def step(self, state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        return state, True

    @property
    def current_phase(self) -> str:
        return "complete"

    @property
    def current_node(self) -> str | None:
        return f"policy_runtime_{self._fidelity}"

    def reset(self) -> None:
        return None


@dataclass(frozen=True)
class RunPolicyBlueprintRuntimeNode:
    """Run policy blueprint runtime node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if not _is_policy_mode(state):
            return NodeOutcome(status="skip", state=state)

        runtime_request = resolve_policy_runtime_request(ctx, state)
        if runtime_request is None:
            return NodeOutcome(status="skip", state=state)
        owner = sys.modules[__name__]
        session = prepare_runtime_session(ctx, state, runtime_request, owner)
        prepare_runtime_benchmark_evidence(session)
        build_runtime_funnel_context(session)
        run_runtime_funnel(session)
        return finalize_runtime_session(session)


_StrategicRuntimeOutput = _SharedStrategicRuntimeOutput
_build_blocked_strategic_summary = _shared_build_blocked_strategic_summary
_selection_baseline_policy_value = _shared_selection_baseline_policy_value
_load_runtime_abstraction_certificate = _shared_load_runtime_abstraction_certificate
_build_runtime_abstraction_metadata = _shared_build_runtime_abstraction_metadata
_resolve_existing_strategic_output = _shared_resolve_existing_strategic_output


def _ensure_platform_meta_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    selection_ref: ArtifactRef,
    selection_evaluation: BenchmarkEvaluation,
    hidden_holdout: BenchmarkEvaluation | None,
    rotating_holdouts: list[BenchmarkEvaluation],
    existing_evidence: PromotionEvidenceBundle | None,
) -> ArtifactRef | None:
    if (
        existing_evidence is not None
        and existing_evidence.adversarial_meta_evaluation_ref is not None
    ):
        return existing_evidence.adversarial_meta_evaluation_ref
    evaluator = PlatformMetaEvaluator()
    report = evaluator.evaluate(
        PlatformMetaEvaluationInput(
            selection_evaluation=selection_evaluation,
            rotated_hidden_holdout_evaluations=rotating_holdouts,
            base_promotion_decision=selection_evaluation.promotable,
            rotated_promotion_decisions=[item.promotable for item in rotating_holdouts],
            observed_scheduler_mode=_resolve_degradation_mode(state),
            source_refs={"selection_evaluation_ref": selection_ref},
            metadata={"run_id": state.run_id},
        )
    )
    return persist_platform_meta_evaluation_report(ctx.store, report)


def _world_model_record_from_state(state: ExperimentState) -> WorldModelRecord | None:
    raw_record = state.params.get("world_model_record")
    if isinstance(raw_record, WorldModelRecord):
        return raw_record
    if isinstance(raw_record, Mapping):
        try:
            return WorldModelRecord.model_validate(raw_record)
        except ValidationError:
            return None
    return None


def _policy_promotion_runner(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
    context: dict[str, Any],
) -> Any:
    evidence_ref = context.get("promotion_evidence_bundle_ref")
    if not isinstance(evidence_ref, ArtifactRef):
        return {
            "decision": "reject",
            "reason": "promotion_evidence_bundle_missing",
        }
    try:
        evidence_bundle = load_promotion_evidence_bundle(ctx.store, evidence_ref)
        evaluation_vector, evaluation_ref = _extract_level4_policy_evaluation(
            ctx,
            candidate_ref=candidate_ref,
            context=context,
        )
        provenance = _extract_level4_policy_runtime_provenance(context)
        if evaluation_vector is None or evaluation_ref is None:
            return {
                "decision": "reject",
                "reason": "promotion_requires_level4_evaluation",
            }
        if not provenance["promotable_source"]:
            return {
                "decision": "reject",
                "reason": "policy_runtime_source_not_promotable",
                "backend_kind": provenance["backend_kind"],
                "degradation_mode": provenance["degradation_mode"],
            }
        evidence_bundle = evidence_bundle.model_copy(update={"evaluation_ref": evaluation_ref})
        if not _policy_promotion_owner_recheck(ctx, state, candidate_ref, context):
            return {
                "decision": "defer_to_human",
                "reason": "promotion_owner_recheck_failed",
            }
        return run_promotion_with_evidence(
            ctx=ctx,
            state=state,
            candidate=candidate,
            candidate_ref=candidate_ref,
            evaluation_vector=evaluation_vector,
            evidence_bundle=evidence_bundle,
            promotion_context=context,
            evaluation_provenance=provenance,
        )
    except ValueError as exc:
        return {
            "decision": "reject",
            "reason": str(exc),
        }


def _policy_promotion_owner_recheck(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate_ref: ArtifactRef,
    context: Mapping[str, Any],
) -> bool:
    """Revalidate current owner inputs immediately before promotion writes."""

    if str(context.get("funnel_degradation_mode") or "normal") in {
        "no_promotion",
        "reduced_judge",
        "auto_cap",
    }:
        return False
    if context.get("promotion_write_allowed") is not True:
        return False
    context_candidate_ref = context.get("policy_candidate_ref")
    if isinstance(context_candidate_ref, ArtifactRef) and context_candidate_ref != candidate_ref:
        return False
    evidence_ref = context.get("promotion_evidence_bundle_ref")
    if not isinstance(evidence_ref, ArtifactRef):
        return False
    try:
        evidence_bundle = load_promotion_evidence_bundle(ctx.store, evidence_ref)
        evidence_bundle.assert_compatible_with_run(state.run_id)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return False
    return evidence_bundle.candidate_ref == candidate_ref


def _resolve_degradation_mode(
    state: ExperimentState,
    *,
    hidden_holdout_ref: ArtifactRef | None | object = _UNSET,
    replay_bundle_ref: ArtifactRef | None | object = _UNSET,
    governance_ref: ArtifactRef | None | object = _UNSET,
    calibration_report: Any | None = None,
) -> str:
    correlation_metrics = _resolve_runtime_correlation_metrics(state, calibration_report)
    if correlation_metrics:
        routing_mode = str(correlation_metrics.get("routing_mode") or "").strip()
        if bool(correlation_metrics.get("promotion_ban_active")):
            return "no_promotion"
        if routing_mode:
            return routing_mode
    if calibration_report is not None:
        report_health = getattr(calibration_report, "routing_health", {}) or {}
        if bool(report_health.get("promotion_ban_active")):
            return "no_promotion"
        report_mode = str(getattr(calibration_report, "current_mode", "") or "").strip()
        if report_mode:
            return report_mode
    if (
        hidden_holdout_ref is not _UNSET
        or replay_bundle_ref is not _UNSET
        or governance_ref is not _UNSET
    ) and (hidden_holdout_ref is None or replay_bundle_ref is None or governance_ref is None):
        return "no_promotion"
    if state.params.get("calibration_drift_detected") is True:
        return "conservative_routing"
    return "normal"


def _load_existing_promotion_evidence(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> PromotionEvidenceBundle | None:
    ref = state.inputs.get(INPUT_PROMOTION_EVIDENCE_BUNDLE_REF)
    if ref is None:
        ref = state.artifacts_index.get(ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF)
    if ref is None:
        return None
    return load_promotion_evidence_bundle(ctx.store, ref)


def _resolve_replay_bundle_ref(
    state: ExperimentState,
    evidence_bundle: PromotionEvidenceBundle | None,
) -> ArtifactRef | None:
    if evidence_bundle is not None and evidence_bundle.replay_bundle_ref is not None:
        return evidence_bundle.replay_bundle_ref
    return state.artifacts_index.get(ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF)


def _extract_level4_policy_runtime_provenance(
    context: dict[str, Any],
) -> dict[str, Any]:
    stage4 = context.get("_funnel_L4_result")
    feedback = getattr(stage4, "feedback", {}) if stage4 is not None else {}
    notes = feedback.get("policy_runtime_notes") or []
    return {
        "backend_kind": str(feedback.get("policy_runtime_backend_kind") or "unknown"),
        "fidelity_mode": str(feedback.get("policy_runtime_fidelity") or "unknown"),
        "promotable_source": bool(feedback.get("policy_runtime_promotable_source", False)),
        "degradation_mode": (
            str(feedback.get("policy_runtime_degradation_mode"))
            if feedback.get("policy_runtime_degradation_mode") is not None
            else None
        ),
        "notes": [str(item) for item in list(notes or [])],
    }


def _extract_level4_policy_evaluation(
    ctx: ExecutionContext,
    *,
    candidate_ref: ArtifactRef,
    context: dict[str, Any],
) -> tuple[PolicyEvaluationVector | None, ArtifactRef | None]:
    stage4 = context.get("_funnel_L4_result")
    if stage4 is None:
        return None, None
    feedback = getattr(stage4, "feedback", {}) or {}
    if str(feedback.get("policy_runtime_fidelity") or "") != "full":
        return None, None
    payload = feedback.get("policy_evaluation")
    if not isinstance(payload, dict):
        return None, None
    evaluation = PolicyEvaluationVector.model_validate(payload)
    ref = persist_policy_evaluation_vector(
        ctx,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation,
    )
    return evaluation, ref


def _resolve_runtime_policy_evaluation(
    ctx: ExecutionContext,
    *,
    candidate_ref: ArtifactRef,
    outcome: FunnelOutcome,
    fallback: PolicyEvaluationVector,
) -> tuple[PolicyEvaluationVector, ArtifactRef | None]:
    stage4 = outcome.stage_results.get(4)
    if stage4 is None:
        return fallback, None
    feedback = dict(stage4.feedback or {})
    payload = feedback.get("policy_evaluation")
    fidelity = str(feedback.get("policy_runtime_fidelity") or "")
    if not isinstance(payload, dict) or fidelity != "full":
        return fallback, None
    evaluation = PolicyEvaluationVector.model_validate(payload)
    ref = persist_policy_evaluation_vector(
        ctx,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation,
    )
    return evaluation, ref


__all__ = ["RunPolicyBlueprintRuntimeNode"]
