"""Public decide run policy promotion module API."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import Metrics
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.cross_graph import load_cross_graph_evidence_profile
from polisyos.ir.analytics.distributional import load_distributional_report
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.scientist.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
    PromotionPolicy,
)
from polisyos.scientist.autotune.registry import ChampionRegistry
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    _is_policy_mode,
    _parse_model,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    load_prior_knowledge_bundle_for_state,
    resolve_effective_latent_discovery_bundle_for_state,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_DECISION_READINESS_CONTRACT_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.policy_design.objectives import (
    ObjectiveStack,
    PolicyEvaluationBundle,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)
from polisyos.scientist.search.adversarial import load_platform_meta_evaluation_report
from polisyos.scientist.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.search.judge_stack import (
    PolicyPromotionCoordinator,
    PolicyPromotionResult,
    to_search_uncertainty_envelope,
)
from polisyos.scientist.search.promotion_evidence import PromotionEvidenceBundle

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_policy_promotion@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Policy Promotion",
    description="Execute JudgeStack, readiness evaluation, and champion consideration for policy mode.",
    tags=["builtin", "decide", "policy_design", "promotion"],
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
        "params.policy_level5_gate",
        "params.calibration_drift_detected",
        "params.promotion_evidence_bundle_ref",
        "params.funnel_outcome",
        "params._funnel_outcome",
        "inputs.promotion_evidence_bundle_ref",
        f"artifacts_index.{ARTIFACT_METRICS_REF}",
        f"artifacts_index.{ARTIFACT_DISTRIBUTIONAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENVELOPE_REF}",
        f"artifacts_index.{ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF}",
        f"artifacts_index.{ARTIFACT_STRESS_TEST_REPORT_REF}",
        "artifacts_index.promotion_evidence_bundle_ref",
        f"reports_index.{REPORT_GOVERNANCE_REPORT_REF}",
    ],
    state_writes=[
        "params.policy_candidate_ref",
        "params.policy_evaluation",
        "params.policy_evaluation_ref",
        "params.policy_promotion_result",
        "params.judge_verdict",
        "params.decision_readiness_contract",
        "params.promotion_decision",
        f"artifacts_index.{ARTIFACT_DECISION_READINESS_CONTRACT_REF}",
    ],
    produces=[ARTIFACT_DECISION_READINESS_CONTRACT_REF],
)


@dataclass(frozen=True)
class RunPolicyPromotionNode:
    """Run policy promotion node implementation."""
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        if not _is_policy_mode(state):
            return NodeOutcome(status="skip", state=state)
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(
                code=node_errors.ERROR_INVALID_INPUT,
                message=(
                    "run_policy_promotion is no longer supported as a direct runtime node. "
                    "Use run_policy_blueprint_runtime for blueprint-native promotion."
                ),
            ),
        )


def _run_promotion_with_evidence(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    evidence_bundle: PromotionEvidenceBundle,
) -> PolicyPromotionResult:
    evidence_bundle.assert_compatible_with_run(state.run_id)
    missing = evidence_bundle.missing_required_refs(
        require_hidden_holdout=True,
        require_replay_bundle=True,
        require_governance=True,
    )
    if missing:
        raise ValueError(
            "PromotionEvidenceBundle is incomplete for promotion: " + ", ".join(sorted(missing))
        )

    selection_ref = evidence_bundle.selection_evaluation_ref
    hidden_holdout_ref = evidence_bundle.hidden_holdout_evaluation_ref
    platform_meta_ref = evidence_bundle.adversarial_meta_evaluation_ref
    assert selection_ref is not None
    assert hidden_holdout_ref is not None
    assert platform_meta_ref is not None

    selection_evaluation = _load_benchmark_evaluation(ctx, selection_ref)
    hidden_holdout = _load_benchmark_evaluation(ctx, hidden_holdout_ref)
    platform_meta = load_platform_meta_evaluation_report(ctx.store, platform_meta_ref)
    governance_report = (
        _load_governance_report_from_ref(ctx, evidence_bundle.governance_report_ref)
        if evidence_bundle.governance_report_ref is not None
        else _load_governance_report(ctx, state)
    )
    if governance_report is None:
        raise ValueError("PromotionEvidenceBundle governance_report_ref could not be resolved.")
    causal_report = _load_causal_report(ctx, state)
    distributional_report = _load_distributional_report(ctx, state)
    cross_graph_profile = _load_cross_graph_profile(ctx, state)
    prior_knowledge_bundle = load_prior_knowledge_bundle_for_state(ctx, state)
    latent_resolution = resolve_effective_latent_discovery_bundle_for_state(
        ctx,
        state,
        causal_report=causal_report,
    )
    latent_discovery_bundle = latent_resolution.bundle
    uncertainty = _load_search_uncertainty(ctx, state)

    champion_registry = ChampionRegistry(
        root=Path(ctx.store.root) / "search_registry",
        store=ctx.store,
    )
    coordinator = PolicyPromotionCoordinator(
        champion_registry=champion_registry,
        store=ctx.store,
    )
    loop_id = str(state.params.get("policy_loop_id") or state.run_id)
    judge_input = coordinator.build_input_bundle(
        candidate=candidate,
        funnel_outcome=_resolve_funnel_outcome(state),
        benchmark_evaluation=selection_evaluation,
        hidden_holdout_evaluation=hidden_holdout,
        platform_meta_evaluation_report=platform_meta,
        evaluation_vector=evaluation_vector,
        distributional_report=distributional_report,
        causal_effect_report=causal_report,
        cross_graph_profile=cross_graph_profile,
        prior_knowledge_bundle=prior_knowledge_bundle,
        governance_report=governance_report,
        latent_discovery_bundle=latent_discovery_bundle,
        latent_discovery_resolution_error=latent_resolution.error_payload(),
        uncertainty_envelope=uncertainty,
        candidate_ref=candidate_ref,
        evaluation_ref=selection_ref,
        run_id=state.run_id,
        state={
            "audit_lineage_complete": (
                candidate_ref is not None
                and evidence_bundle.replay_bundle_ref is not None
                and selection_ref is not None
            ),
            "checkpoints": [str(state.last_checkpoint_ref.artifact_id)]
            if state.last_checkpoint_ref is not None
            else [],
            "data_sources": [str(ref.artifact_id) for ref in state.inputs.values()],
            "knowledge_metadata": {
                "workflow_id": str(state.params.get("workflow_id") or ""),
            },
            "current_pareto_position": "unknown",
        },
        compute_cost_usd=float(state.params.get("estimated_compute_cost_usd", 0.0) or 0.0),
        replay_cost_usd=float(state.params.get("estimated_replay_cost_usd", 0.0) or 0.0),
        timeout_risk=float(state.params.get("timeout_risk", 0.0) or 0.0),
    )
    promotion_policy = PromotionPolicy(
        loop_id=loop_id,
        primary_metric="score",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.HOLDOUT,
    )
    return coordinator.coordinate_promotion(
        loop_id=loop_id,
        candidate_ref=candidate_ref,
        evaluation_ref=selection_ref,
        promotion_policy=promotion_policy,
        judge_input=judge_input,
    )


def _ensure_candidate_ref(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef | None,
) -> ArtifactRef:
    if candidate_ref is not None and candidate_ref.kind == "scientist.policy_candidate_schema":
        return candidate_ref
    return persist_policy_candidate_schema(
        ctx.store,
        candidate,
        inputs=[InputRef(artifact_id=ref.artifact_id, role=key) for key, ref in state.inputs.items()],
    )


def _resolve_policy_evaluation(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
) -> tuple[PolicyEvaluationVector | None, ArtifactRef | None]:
    parsed = _parse_model(state.params.get("policy_evaluation"), PolicyEvaluationVector)
    if parsed is None:
        metrics = _load_simulation_metrics(ctx, state)
        if not metrics:
            return None, None
        parsed = ObjectiveStack().evaluate(
            PolicyEvaluationBundle(
                candidate=candidate,
                simulation_metrics=metrics,
                distributional_report=_load_distributional_report(ctx, state),
                causal_effect_report=_load_causal_report(ctx, state),
                cross_graph_profile=_load_cross_graph_profile(ctx, state),
                governance_report=_load_governance_report(ctx, state),
                uncertainty_envelope=_load_search_uncertainty(ctx, state),
            )
        )
    ref = ctx.store.put_json(
        parsed,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                version="1.0",
            ),
            inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
        ),
    )
    return parsed, ref


def _load_simulation_metrics(ctx: ExecutionContext, state: ExperimentState) -> dict[str, float]:
    metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
    if metrics_ref is None:
        return {}
    payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref.artifact_id))
    metrics = Metrics.model_validate(payload)
    output: dict[str, float] = {}
    for key, value in metrics.values.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            output[str(key)] = float(value)
            continue
        try:
            output[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return output


def _selection_score(evaluation_vector: PolicyEvaluationVector) -> float:
    if "policy_value" in evaluation_vector.primary:
        return float(evaluation_vector.primary["policy_value"].value)
    if evaluation_vector.primary:
        return float(next(iter(evaluation_vector.primary.values())).value)
    return 0.0


def _build_selection_benchmark_evaluation(
    *,
    state: ExperimentState,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
) -> BenchmarkEvaluation:
    base_score = _selection_score(evaluation_vector)
    return BenchmarkEvaluation(
        loop_id=str(state.params.get("policy_loop_id") or state.run_id),
        suite_id="policy_selection",
        candidate_ref=candidate_ref,
        selection_metrics={
            "score": base_score,
            **{name: channel.higher_is_better for name, channel in evaluation_vector.primary.items()},
        },
        holdout_metrics={"score": base_score},
        sample_counts={BenchmarkSplit.SELECTION.value: 100},
        promotable=evaluation_vector.feasible,
        runtime_split_type=BenchmarkSplit.SELECTION,
        metadata={"lineage_complete": True, "generated_from": "policy_evaluation_vector"},
    )


def _load_benchmark_evaluation(ctx: ExecutionContext, ref: ArtifactRef) -> BenchmarkEvaluation:
    return BenchmarkEvaluation.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id)))


def _load_distributional_report(ctx: ExecutionContext, state: ExperimentState):
    ref = state.artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)
    return None if ref is None else load_distributional_report(ctx.store, ref)


def _load_causal_report(ctx: ExecutionContext, state: ExperimentState) -> CausalEffectReport | None:
    ref = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    if ref is None:
        return None
    return CausalEffectReport.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id)))


def _load_governance_report(ctx: ExecutionContext, state: ExperimentState) -> GovernanceReport | None:
    ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
    if ref is None:
        return None
    return GovernanceReport.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id)))


def _load_governance_report_from_ref(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> GovernanceReport | None:
    return GovernanceReport.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id)))


def _load_cross_graph_profile(ctx: ExecutionContext, state: ExperimentState):
    ref = state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
    return None if ref is None else load_cross_graph_evidence_profile(ctx.store, ref)


def _load_search_uncertainty(ctx: ExecutionContext, state: ExperimentState):
    ref = state.artifacts_index.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    if ref is None:
        return to_search_uncertainty_envelope(None)
    return to_search_uncertainty_envelope(load_uncertainty_envelope(ctx.store, ref))


def _resolve_funnel_outcome(state: ExperimentState) -> FunnelOutcome | None:
    for key in ("funnel_outcome", "_funnel_outcome"):
        value = state.params.get(key)
        if isinstance(value, FunnelOutcome):
            return value
    return None


def _resolve_promotion_evidence_ref(state: ExperimentState) -> ArtifactRef | None:
    for ref in (
        state.inputs.get("promotion_evidence_bundle_ref"),
        state.artifacts_index.get("promotion_evidence_bundle_ref"),
        _maybe_artifact_ref(state.params.get("promotion_evidence_bundle_ref")),
    ):
        if ref is not None:
            return ref
    return None


def _maybe_artifact_ref(value: Any) -> ArtifactRef | None:
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict):
        try:
            return ArtifactRef.model_validate(value)
        except (TypeError, ValidationError, ValueError):
            return None
    return None


__all__ = [
    "RunPolicyPromotionNode",
    "_build_selection_benchmark_evaluation",
    "_ensure_candidate_ref",
    "_load_causal_report",
    "_load_cross_graph_profile",
    "_load_distributional_report",
    "_load_governance_report",
    "_load_search_uncertainty",
    "_resolve_funnel_outcome",
    "_resolve_policy_evaluation",
    "_run_promotion_with_evidence",
]
