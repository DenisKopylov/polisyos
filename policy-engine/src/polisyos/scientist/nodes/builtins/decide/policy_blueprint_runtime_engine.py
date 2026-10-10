from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.methods.search.lessons import LessonRegistry
from polisyos.scientist.methods.search.promotion_evidence import PromotionEvidenceBundle
from polisyos.scientist.nodes.builtins.decide.policy_runtime_state import maybe_artifact_ref
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    ProductionPolicyEvaluationBackend,
    build_policy_runtime_evaluation,
    build_selection_benchmark_evaluation,
    persist_funnel_executed_work_packet,
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


@dataclass(slots=True)
class _RuntimeSession:
    """Carry the ordered intermediate state for one policy runtime invocation."""

    ctx: ExecutionContext
    state: ExperimentState
    owner: ModuleType
    candidate: PolicyCandidateSchema
    candidate_ref: ArtifactRef
    uncertainty_envelope: Any
    governance_report: Any
    causal_report: Any
    distributional_report: Any
    cross_graph_profile: Any
    evidence_sources: Any
    runtime_source_statuses: dict[str, str]
    simulation_metrics: Any
    ambiguity_certificate: Any
    ambiguity_certificate_ref: ArtifactRef | None
    runtime_backend: ProductionPolicyEvaluationBackend
    input_signature: str
    runtime_artifacts_index: dict[str, ArtifactRef] = field(default_factory=dict)
    selection_artifact: Any = None
    selection_vector: PolicyEvaluationVector | None = None
    selection_vector_ref: ArtifactRef | None = None
    strategic_output: Any = None
    selection_evaluation: BenchmarkEvaluation | None = None
    selection_ref: ArtifactRef | None = None
    benchmark_scope: dict[str, str | None] = field(default_factory=dict)
    benchmark_registry: BenchmarkRegistry | None = None
    existing_evidence: PromotionEvidenceBundle | None = None
    phase_d4_suite_ids: list[str] = field(default_factory=list)
    phase_d4_warnings: tuple[str, ...] = ()
    phase_d4_rotating_refs: list[ArtifactRef] = field(default_factory=list)
    phase_d4_stress_refs: list[ArtifactRef] = field(default_factory=list)
    hidden_holdout_ref: ArtifactRef | None = None
    rotating_refs: list[ArtifactRef] = field(default_factory=list)
    hidden_holdout: BenchmarkEvaluation | None = None
    calibration_ref: ArtifactRef | None = None
    calibration_report: Any = None
    platform_meta_ref: ArtifactRef | None = None
    stress_report_ref: ArtifactRef | None = None
    replay_bundle_ref: ArtifactRef | None = None
    replay_verification_ref: ArtifactRef | None = None
    governance_ref: ArtifactRef | None = None
    degradation_mode: str = "normal"
    evidence_bundle: PromotionEvidenceBundle | None = None
    evidence_ref: ArtifactRef | None = None
    transfer_context: dict[str, Any] = field(default_factory=dict)
    funnel_context: dict[str, Any] = field(default_factory=dict)
    predictive_voi: Any = None
    outcome: Any = None
    final_evaluation_vector: PolicyEvaluationVector | None = None
    final_evaluation_ref: ArtifactRef | None = None
    voi_report_ref: ArtifactRef | None = None
    new_state: ExperimentState | None = None


def prepare_runtime_session(
    ctx: ExecutionContext,
    state: ExperimentState,
    runtime_request: Any,
    owner: ModuleType,
) -> _RuntimeSession:
    """Resolve policy inputs and persist the selection evaluation in source order."""
    candidate = runtime_request.candidate
    candidate_ref = runtime_request.candidate_ref
    cross_graph_profile = runtime_request.cross_graph_profile
    evidence_sources = runtime_request.evidence_sources
    runtime_source_statuses = owner._resolve_policy_runtime_source_statuses(
        cross_graph_profile=cross_graph_profile,
        evidence_sources=evidence_sources,
    )
    runtime_backend = owner.ProductionPolicyEvaluationBackend(
        eval_safety_execution_context=ctx.eval_safety_execution_context,
        eval_safety_verifier=ctx.eval_safety_verifier,
        world_model_record=owner._world_model_record_from_state(state),
    )
    input_signature = owner.policy_runtime_input_signature(
        candidate_ref=candidate_ref,
        state=state,
    )
    selection_artifact = owner.build_policy_runtime_evaluation(
        candidate,
        backend=runtime_backend,
        fidelity="selection",
        simulation_metrics=runtime_request.simulation_metrics,
        uncertainty=runtime_request.uncertainty_envelope,
        distributional_report=runtime_request.distributional_report,
        causal_effect_report=runtime_request.causal_report,
        cross_graph_profile=cross_graph_profile,
        governance_report=runtime_request.governance_report,
        ambiguity_certificate=runtime_request.ambiguity_certificate,
    )
    selection_vector = selection_artifact.evaluation_vector.model_copy(
        update={
            "metadata": {
                **dict(selection_artifact.evaluation_vector.metadata),
                "evidence_source_statuses": dict(runtime_source_statuses),
            }
        }
    )
    selection_vector_ref = owner.persist_policy_evaluation_vector(
        ctx,
        candidate_ref=candidate_ref,
        evaluation_vector=selection_vector,
    )
    runtime_artifacts_index = dict(state.artifacts_index)
    ambiguity_certificate_ref = runtime_request.ambiguity_certificate_ref
    if ambiguity_certificate_ref is not None:
        runtime_artifacts_index[owner.ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = (
            ambiguity_certificate_ref
        )
    strategic_output = owner._resolve_existing_strategic_output(state)
    if strategic_output is None:
        strategic_output = owner._persist_runtime_strategic_artifacts(
            ctx,
            state,
            candidate_ref=candidate_ref,
            selection_vector_ref=selection_vector_ref,
            selection_artifact=selection_artifact,
            artifacts_index=runtime_artifacts_index,
        )
    if strategic_output.strategic_scm_ref is not None:
        runtime_artifacts_index[owner.ARTIFACT_STRATEGIC_SCM_REF] = (
            strategic_output.strategic_scm_ref
        )
    if strategic_output.strategic_response_bundle_ref is not None:
        runtime_artifacts_index[owner.ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF] = (
            strategic_output.strategic_response_bundle_ref
        )
    abstraction_metadata = owner._build_runtime_abstraction_metadata(
        ctx,
        artifacts_index=runtime_artifacts_index,
    )
    selection_metadata_extension = {
        "evidence_source_statuses": dict(runtime_source_statuses),
        **abstraction_metadata,
    }
    if strategic_output.strategic_response_summary is not None:
        selection_metadata_extension["strategic_response"] = dict(
            strategic_output.strategic_response_summary
        )
    if strategic_output.strategic_response_bundle_ref is not None:
        selection_metadata_extension["strategic_response_bundle_ref"] = (
            strategic_output.strategic_response_bundle_ref.model_dump(mode="json")
        )
    if strategic_output.strategic_scm_ref is not None:
        selection_metadata_extension["strategic_scm_ref"] = (
            strategic_output.strategic_scm_ref.model_dump(mode="json")
        )

    selection_evaluation = owner.build_selection_benchmark_evaluation(
        state=state,
        candidate_ref=candidate_ref,
        evaluation_vector=selection_vector,
        runtime_artifact=selection_artifact,
        source="policy_runtime_selection",
        metadata_extension=selection_metadata_extension,
    )
    selection_ref = owner.persist_benchmark_evaluation(
        ctx.store,
        selection_evaluation,
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
    )
    benchmark_scope = owner._resolve_benchmark_scope(
        state=state,
        candidate=candidate,
        selection_vector=selection_vector,
    )
    benchmark_registry = owner.BenchmarkRegistry(
        Path(ctx.store.root) / "search_registry" / "benchmarks"
    )
    benchmark_registry.record_evaluation(
        selection_evaluation,
        selection_ref,
        run_id=state.run_id,
        family=benchmark_scope["artifact_family"],
        query_type=benchmark_scope["query_type"],
        estimator_name=benchmark_scope["estimator_name"],
        readiness_target=benchmark_scope["readiness_target"],
        produced_by_run_id=state.run_id,
        metadata={
            "artifact_family": benchmark_scope["artifact_family"],
            "claim_mode": benchmark_scope["claim_mode"],
            "loop_id": selection_evaluation.loop_id,
        },
    )
    return _RuntimeSession(
        ctx=ctx,
        state=state,
        owner=owner,
        candidate=candidate,
        candidate_ref=candidate_ref,
        uncertainty_envelope=runtime_request.uncertainty_envelope,
        governance_report=runtime_request.governance_report,
        causal_report=runtime_request.causal_report,
        distributional_report=runtime_request.distributional_report,
        cross_graph_profile=cross_graph_profile,
        evidence_sources=evidence_sources,
        runtime_source_statuses=runtime_source_statuses,
        simulation_metrics=runtime_request.simulation_metrics,
        ambiguity_certificate=runtime_request.ambiguity_certificate,
        ambiguity_certificate_ref=ambiguity_certificate_ref,
        runtime_backend=runtime_backend,
        input_signature=input_signature,
        runtime_artifacts_index=runtime_artifacts_index,
        selection_artifact=selection_artifact,
        selection_vector=selection_vector,
        selection_vector_ref=selection_vector_ref,
        strategic_output=strategic_output,
        selection_evaluation=selection_evaluation,
        selection_ref=selection_ref,
        benchmark_scope=benchmark_scope,
        benchmark_registry=benchmark_registry,
    )


def run_runtime_funnel(session: _RuntimeSession) -> None:
    """Build and advance the existing L0-L6 funnel without changing its stage order."""
    owner = session.owner
    ctx = session.ctx
    state = session.state
    candidate = session.candidate
    candidate_ref = session.candidate_ref
    calibration_report = session.calibration_report
    predictive_voi = session.predictive_voi
    orchestrator = owner.FunnelOrchestrator(
        stages=[
            owner.Level0StaticValidator(),
            owner.Level1CheapHeuristic(),
            owner.Level2CausalPlausibility(),
            owner.Level3MediumFidelity(
                workflow_engine=owner._PolicyRuntimeWorkflowEngine(
                    fidelity="medium",
                    backend=session.runtime_backend,
                ),
                subsample_fraction=0.35,
                bootstrap_draws=64,
                estimator_tier="matching",
                scenario_set="medium",
                top_k_subgroups=3,
            ),
            owner.Level4FullFidelity(
                workflow_engine=owner._PolicyRuntimeWorkflowEngine(
                    fidelity="full",
                    backend=session.runtime_backend,
                ),
                estimated_cost_usd=0.20,
            ),
            owner.Level5RefutationGovernanceStage(
                require_hidden_holdout=True,
                require_platform_meta=True,
                store=ctx.store,
            ),
            owner.Level6PromotionStage(
                promotion_runner=lambda _candidate, context: owner._policy_promotion_runner(
                    ctx,
                    state,
                    candidate,
                    candidate_ref,
                    context,
                ),
                promotion_owner_recheck=lambda _candidate, context: (
                    owner._policy_promotion_owner_recheck(
                        ctx,
                        state,
                        candidate_ref,
                        context,
                    )
                ),
                store=ctx.store,
            ),
        ],
        correlation_tracker=owner._resolve_runtime_correlation_tracker(calibration_report),
        lesson_registry=owner.LessonRegistry(
            root=Path(ctx.store.root) / "search_registry" / "lessons",
            store=ctx.store,
        ),
        voi_scheduler=predictive_voi,
    )
    ticket = orchestrator.submit(
        owner._candidate_search_payload(candidate, state),
        session.funnel_context,
    )
    session.outcome = orchestrator.advance(ticket, policy="full")
    owner.persist_predictive_voi_scheduler(
        ctx,
        transfer_context=session.transfer_context,
        scheduler=predictive_voi,
    )


def _persist_policy_runtime_work_packet(
    *,
    initial_state: Mapping[str, Any],
    fidelity: str,
    evaluation_attempt_id: str,
    runtime_artifact: PolicyRuntimeEvaluationArtifact,
) -> tuple[ArtifactRef | None, str | None]:
    """Persist an invocation packet only when actual runtime identity is available."""
    identity = initial_state.get("policy_runtime_work_identity")
    if not isinstance(identity, Mapping):
        return None, "execution_identity_unavailable"
    store = initial_state.get("store")
    if store is None or not hasattr(store, "put_json"):
        return None, "artifact_store_unavailable"

    candidate_ref = maybe_artifact_ref(identity.get("candidate_ref"))
    state_candidate_ref = maybe_artifact_ref(initial_state.get("policy_candidate_ref"))
    if candidate_ref is None or state_candidate_ref != candidate_ref:
        return None, "candidate_ref_unavailable_or_mismatched"
    run_id = identity.get("run_id")
    ticket_id = identity.get("ticket_id")
    candidate_hash = identity.get("candidate_hash")
    if not all(
        isinstance(value, str) and value.strip() for value in (run_id, ticket_id, candidate_hash)
    ):
        return None, "run_ticket_or_candidate_identity_unavailable"
    if fidelity not in {"medium", "full"}:
        return None, "unsupported_fidelity"

    result_ref = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate_ref,
        evaluation_vector=runtime_artifact.evaluation_vector,
    )
    bootstrap = runtime_artifact.simulation_results.get("bootstrap", {})
    requested_draw_count = (
        bootstrap.get("requested_draw_count") if isinstance(bootstrap, Mapping) else None
    )
    if isinstance(requested_draw_count, bool) or not isinstance(requested_draw_count, int):
        requested_draw_count = None
    packet = FunnelExecutedWorkPacket(
        run_id=run_id,
        ticket_id=ticket_id,
        candidate_hash=candidate_hash,
        candidate_ref=candidate_ref,
        stage_level=3 if fidelity == "medium" else 4,
        stage_name="funnel_L3_medium" if fidelity == "medium" else "funnel_L4_full",
        fidelity=fidelity,
        evaluation_attempt_id=evaluation_attempt_id,
        observed_at=datetime.now(UTC),
        backend_kind=runtime_artifact.provenance.backend_kind,
        source_result_ref=result_ref,
        requested_draw_count=requested_draw_count,
        input_signature=(
            str(initial_state["pinned_input_signature"])
            if initial_state.get("pinned_input_signature")
            else None
        ),
    )
    return persist_funnel_executed_work_packet(store, packet), None
