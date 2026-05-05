"""Public decide run policy blueprint runtime module API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods.catalog.causal.strategic import (
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
    persist_strategic_solve_artifacts,
)
from polisyos.ir.artifacts import InputRef as IRInputRef
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.backtesting.adversarial import (
    ABSTRACTION_LEAKAGE_SUITE_ID,
    MULTIPLICITY_DISCLOSURE_SUITE_ID,
    PHASE_D4_ROTATION_GROUP,
    STRATEGIC_GAMING_SUITE_ID,
    run_phase_d4_challenge_suites,
)
from polisyos.scientist.doe.stress_report import StressTestReport
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.evidence.sources import (
    build_path_source_status,
)
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
    ProductionPolicyEvaluationBackend,
    build_policy_runtime_evaluation,
    build_selection_benchmark_evaluation,
    build_vulnerabilities,
    load_benchmark_evaluation,
    load_causal_report,
    load_distributional_report_for_state,
    load_governance_report,
    persist_policy_evaluation_vector,
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
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.replay.verification import ReplayRegistry, verify_and_persist_replay_bundle
from polisyos.scientist.search.actionable_side_information import resolve_actionable_store
from polisyos.scientist.search.adversarial import (
    PlatformMetaEvaluationInput,
    PlatformMetaEvaluator,
    load_platform_meta_evaluation_report,
    persist_platform_meta_evaluation_report,
)
from polisyos.scientist.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.search.calibration_report import (
    build_calibration_report,
    load_funnel_calibration_report,
    persist_funnel_calibration_report,
)
from polisyos.scientist.search.funnel.level0_static import Level0StaticValidator
from polisyos.scientist.search.funnel.level1_heuristic import Level1CheapHeuristic
from polisyos.scientist.search.funnel.level2_causal import Level2CausalPlausibility
from polisyos.scientist.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.search.funnel.level4_full import Level4FullFidelity
from polisyos.scientist.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.search.funnel.level6_promotion import Level6PromotionStage
from polisyos.scientist.search.funnel.orchestrator import FunnelOrchestrator, FunnelOutcome
from polisyos.scientist.search.lessons import LessonRegistry
from polisyos.scientist.search.promotion_evidence import (
    PromotionEvidenceBundle,
    load_promotion_evidence_bundle,
    persist_promotion_evidence_bundle,
)
from polisyos.scientist.search.stages import CorrelationTracker
from polisyos.scientist.search.voi_scheduler import persist_voi_run_report
from polisyos.scientist.workflows.engine_base import WorkflowEngine

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


@dataclass(frozen=True)
class _StrategicRuntimeOutput:
    strategic_scm_ref: ArtifactRef | None = None
    strategic_response_bundle_ref: ArtifactRef | None = None
    strategic_response_summary: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()


class _PolicyRuntimeWorkflowEngine(WorkflowEngine):
    """Workflow adapter that materializes fidelity-specific policy runtime outputs."""

    def __init__(self, *, fidelity: str, backend: ProductionPolicyEvaluationBackend) -> None:
        self._fidelity = fidelity
        self._backend = backend

    def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        candidate = initial_state.get("policy_candidate_schema")
        if not isinstance(candidate, PolicyCandidateSchema):
            raise ValueError("policy_candidate_schema is required for policy runtime workflow.")
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
        return {
            "simulation_results": runtime_artifact.simulation_results,
            "feedback": {
                "verdict": "APPROVE" if runtime_artifact.evaluation_vector.feasible else "REJECT",
                "fidelity_engine": self._fidelity,
                "blocking_reasons": list(runtime_artifact.evaluation_vector.blocking_reasons),
                "routing_source": f"policy_runtime_{self._fidelity}",
                "policy_evaluation": runtime_artifact.evaluation_vector.model_dump(mode="json"),
                "policy_runtime_fidelity": self._fidelity,
                "policy_runtime_backend_kind": runtime_artifact.provenance.backend_kind,
                "policy_runtime_promotable_source": runtime_artifact.provenance.promotable_source,
                "policy_runtime_degradation_mode": runtime_artifact.provenance.degradation_mode,
                "policy_runtime_source_components": list(
                    runtime_artifact.provenance.source_components
                ),
                "policy_runtime_notes": list(runtime_artifact.provenance.notes),
                "policy_runtime_input_signature": str(
                    initial_state.get("pinned_input_signature") or ""
                ),
            },
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
        candidate = runtime_request.candidate
        candidate_ref = runtime_request.candidate_ref
        uncertainty_envelope = runtime_request.uncertainty_envelope
        governance_report = runtime_request.governance_report
        causal_report = runtime_request.causal_report
        distributional_report = runtime_request.distributional_report
        cross_graph_profile = runtime_request.cross_graph_profile
        evidence_sources = runtime_request.evidence_sources
        runtime_source_statuses = _resolve_policy_runtime_source_statuses(
            cross_graph_profile=cross_graph_profile,
            evidence_sources=evidence_sources,
        )
        simulation_metrics = runtime_request.simulation_metrics
        ambiguity_certificate = runtime_request.ambiguity_certificate
        ambiguity_certificate_ref = runtime_request.ambiguity_certificate_ref
        runtime_backend = ProductionPolicyEvaluationBackend()
        input_signature = policy_runtime_input_signature(
            candidate_ref=candidate_ref,
            state=state,
        )
        selection_artifact = build_policy_runtime_evaluation(
            candidate,
            backend=runtime_backend,
            fidelity="selection",
            simulation_metrics=simulation_metrics,
            uncertainty=uncertainty_envelope,
            distributional_report=distributional_report,
            causal_effect_report=causal_report,
            cross_graph_profile=cross_graph_profile,
            governance_report=governance_report,
            ambiguity_certificate=ambiguity_certificate,
        )
        selection_vector = selection_artifact.evaluation_vector.model_copy(
            update={
                "metadata": {
                    **dict(selection_artifact.evaluation_vector.metadata),
                    "evidence_source_statuses": dict(runtime_source_statuses),
                }
            }
        )
        selection_vector_ref = persist_policy_evaluation_vector(
            ctx,
            candidate_ref=candidate_ref,
            evaluation_vector=selection_vector,
        )
        runtime_artifacts_index = dict(state.artifacts_index)
        if ambiguity_certificate_ref is not None:
            runtime_artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = (
                ambiguity_certificate_ref
            )
        strategic_output = _resolve_existing_strategic_output(state)
        if strategic_output is None:
            strategic_output = _persist_runtime_strategic_artifacts(
                ctx,
                state,
                candidate_ref=candidate_ref,
                selection_vector_ref=selection_vector_ref,
                selection_artifact=selection_artifact,
                artifacts_index=runtime_artifacts_index,
            )
        if strategic_output.strategic_scm_ref is not None:
            runtime_artifacts_index[ARTIFACT_STRATEGIC_SCM_REF] = strategic_output.strategic_scm_ref
        if strategic_output.strategic_response_bundle_ref is not None:
            runtime_artifacts_index[ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF] = (
                strategic_output.strategic_response_bundle_ref
            )
        abstraction_metadata = _build_runtime_abstraction_metadata(
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

        selection_evaluation = build_selection_benchmark_evaluation(
            state=state,
            candidate_ref=candidate_ref,
            evaluation_vector=selection_vector,
            runtime_artifact=selection_artifact,
            source="policy_runtime_selection",
            metadata_extension=selection_metadata_extension,
        )
        selection_ref = persist_benchmark_evaluation(
            ctx.store,
            selection_evaluation,
            inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
        )
        benchmark_scope = _resolve_benchmark_scope(
            state=state,
            candidate=candidate,
            selection_vector=selection_vector,
        )
        benchmark_registry = BenchmarkRegistry(
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
        existing_evidence = _load_existing_promotion_evidence(ctx, state)
        _register_runtime_benchmark_inputs(
            ctx,
            state,
            benchmark_registry=benchmark_registry,
            evidence_bundle=existing_evidence,
            family=benchmark_scope["artifact_family"],
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
        )
        phase_d4_suite_ids: list[str] = []
        phase_d4_warnings: tuple[str, ...] = ()
        phase_d4_rotating_refs, phase_d4_stress_refs, phase_d4_warnings = (
            _run_and_register_phase_d4_challenge_suites(
                ctx,
                state,
                benchmark_registry=benchmark_registry,
                candidate_ref=candidate_ref,
                selection_evaluation=selection_evaluation,
                benchmark_scope=benchmark_scope,
                artifacts_index=runtime_artifacts_index,
            )
        )
        if phase_d4_rotating_refs:
            phase_d4_suite_ids = [
                evaluation.suite_id
                for evaluation in (
                    _load_benchmark_if_present(ctx, ref) for ref in phase_d4_rotating_refs
                )
                if evaluation is not None
            ]
        frontier_benchmark_bundle = benchmark_registry.resolve_family_bundle(
            family=benchmark_scope["artifact_family"],
            claim_mode=benchmark_scope["claim_mode"],
            run_id=state.run_id,
            loop_id=_expected_policy_loop_id(state),
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
        )
        hidden_holdout_ref = frontier_benchmark_bundle.hidden_holdout_evaluation_ref
        rotating_refs = _dedupe_phase_d4_rotating_refs(
            ctx,
            list(frontier_benchmark_bundle.rotating_challenge_evaluation_refs),
        )
        hidden_holdout = _load_benchmark_if_present(ctx, hidden_holdout_ref)
        rotating_holdouts = [
            item
            for item in (_load_benchmark_if_present(ctx, ref) for ref in rotating_refs)
            if item is not None
        ]
        calibration_ref = _ensure_calibration_report(ctx, state)
        platform_meta_ref = _ensure_platform_meta_report(
            ctx,
            state,
            selection_ref=selection_ref,
            selection_evaluation=selection_evaluation,
            hidden_holdout=hidden_holdout,
            rotating_holdouts=rotating_holdouts,
            existing_evidence=existing_evidence,
        )
        if platform_meta_ref is not None:
            benchmark_registry.record(
                BenchmarkSplit.ADVERSARIAL.value,
                platform_meta_ref,
                run_id=state.run_id,
                family=benchmark_scope["artifact_family"],
                query_type=benchmark_scope["query_type"],
                estimator_name=benchmark_scope["estimator_name"],
                readiness_target=benchmark_scope["readiness_target"],
                produced_by_run_id=state.run_id,
                artifact_kind="scientist.platform_meta_evaluation_report",
                metadata={
                    "artifact_type": "platform_meta_evaluation",
                    "artifact_family": benchmark_scope["artifact_family"],
                    "claim_mode": benchmark_scope["claim_mode"],
                },
            )
        stress_report_ref = _ensure_stress_test_report(
            ctx,
            state,
            evaluation_vector=selection_vector,
            supplemental_reports=[
                report
                for report in (_load_stress_test_report(ctx, ref) for ref in phase_d4_stress_refs)
                if report is not None
            ],
            phase_d4_suite_ids=phase_d4_suite_ids,
        )
        if stress_report_ref is not None:
            benchmark_registry.record(
                BenchmarkSplit.ADVERSARIAL.value,
                stress_report_ref,
                run_id=state.run_id,
                family=benchmark_scope["artifact_family"],
                query_type=benchmark_scope["query_type"],
                estimator_name=benchmark_scope["estimator_name"],
                readiness_target=benchmark_scope["readiness_target"],
                produced_by_run_id=state.run_id,
                artifact_kind="scientist.stress_test_report",
                metadata={
                    "artifact_type": "stress_test_report",
                    "artifact_family": benchmark_scope["artifact_family"],
                    "claim_mode": benchmark_scope["claim_mode"],
                },
            )
        replay_bundle_ref = _resolve_replay_bundle_ref(state, existing_evidence)
        replay_verification_ref = (
            existing_evidence.replay_verification_ref if existing_evidence is not None else None
        )
        if replay_verification_ref is None and replay_bundle_ref is not None:
            replay_verification_ref = verify_and_persist_replay_bundle(
                ctx.store,
                run_id=state.run_id,
                replay_bundle_ref=replay_bundle_ref,
                candidate_ref=candidate_ref,
                evaluation_ref=selection_vector_ref,
                registry=ReplayRegistry(
                    Path(ctx.store.root) / "search_registry" / "replay_registry"
                ),
            )
        governance_ref = (
            existing_evidence.governance_report_ref
            if existing_evidence is not None and existing_evidence.governance_report_ref is not None
            else state.reports_index.get("governance_report_ref")
        )
        degradation_mode = _resolve_degradation_mode(
            state,
            hidden_holdout_ref=hidden_holdout_ref,
            replay_bundle_ref=replay_bundle_ref,
            governance_ref=governance_ref,
        )
        missing_benchmark_requirements = benchmark_registry.require_promotion_evidence(
            family=benchmark_scope["artifact_family"],
            claim_mode=benchmark_scope["claim_mode"],
            run_id=state.run_id,
            loop_id=_expected_policy_loop_id(state),
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
        )
        if missing_benchmark_requirements and degradation_mode == "normal":
            degradation_mode = "no_promotion"
        calibration_report = load_funnel_calibration_report(ctx.store, calibration_ref)

        evidence_bundle = PromotionEvidenceBundle(
            run_id=state.run_id,
            produced_by_run_id=state.run_id,
            candidate_ref=candidate_ref,
            evaluation_ref=None,
            selection_evaluation_ref=selection_ref,
            hidden_holdout_evaluation_ref=hidden_holdout_ref,
            rotating_challenge_evaluation_refs=rotating_refs,
            adversarial_meta_evaluation_ref=platform_meta_ref,
            replay_bundle_ref=replay_bundle_ref,
            replay_verification_ref=replay_verification_ref,
            calibration_report_ref=calibration_ref,
            governance_report_ref=governance_ref,
            stress_test_report_ref=stress_report_ref,
            metadata={
                "workflow_id": str(state.params.get("workflow_id") or ""),
                "cutover_mode": "hard_cutover",
                "scheduler_mode": "predictive",
                "degradation_mode": degradation_mode,
                "artifact_family": benchmark_scope["artifact_family"],
                "claim_mode": benchmark_scope["claim_mode"],
                "query_type": benchmark_scope["query_type"],
                "estimator_name": benchmark_scope["estimator_name"],
                "readiness_target": benchmark_scope["readiness_target"],
                "missing_benchmark_requirements": list(missing_benchmark_requirements),
                "evidence_source_statuses": dict(runtime_source_statuses),
                "phase_d4_suite_ids": list(phase_d4_suite_ids),
                "phase_d4_warnings": list(phase_d4_warnings),
            },
        )
        evidence_ref = persist_promotion_evidence_bundle(
            ctx.store,
            evidence_bundle,
            inputs=[
                InputRef(artifact_id=candidate_ref.artifact_id, role="candidate"),
                InputRef(artifact_id=selection_vector_ref.artifact_id, role="policy_evaluation"),
                InputRef(artifact_id=selection_ref.artifact_id, role="selection_evaluation"),
            ],
        )

        transfer_context = state.params.get("transfer_context") or {
            "task_family": "policy",
            "domain": str(
                candidate.metadata.get("domain")
                or state.params.get("policy_request_domain")
                or state.run_id
            ),
            "run_id": state.run_id,
            "tenant_hash": str(candidate.metadata.get("tenant_hash") or ""),
        }
        funnel_context = {
            "store": resolve_actionable_store(store=ctx.store),
            "transfer_context": transfer_context,
            "policy_candidate_schema": candidate,
            "policy_candidate_ref": candidate_ref,
            "simulation_metrics": simulation_metrics,
            "uncertainty_envelope": uncertainty_envelope,
            "selection_evaluation": selection_evaluation,
            "hidden_holdout_evaluation": hidden_holdout,
            "benchmark_registry": benchmark_registry,
            "platform_meta_evaluation_report": (
                None
                if platform_meta_ref is None
                else load_platform_meta_evaluation_report(ctx.store, platform_meta_ref)
            ),
            "governance_report": governance_report,
            "stress_test_report": _load_stress_test_report(ctx, stress_report_ref),
            "causal_effect_report": causal_report,
            "distributional_report": distributional_report,
            "cross_graph_profile": cross_graph_profile,
            "correlation_metrics": dict(state.params.get("correlation_metrics") or {}),
            "funnel_degradation_mode": degradation_mode,
            "promotion_evidence_bundle_ref": evidence_ref,
            "calibration_report_ref": calibration_ref,
            "calibration_report": calibration_report,
            "pinned_input_signature": input_signature,
            "lesson_registry": LessonRegistry(
                root=Path(ctx.store.root) / "search_registry" / "lessons",
                store=ctx.store,
            ),
        }
        predictive_voi = load_predictive_voi_scheduler(
            ctx,
            transfer_context=transfer_context,
        )
        predictive_voi.update_calibration_state(
            {
                **dict(state.params.get("correlation_metrics") or {}),
                "routing_mode": degradation_mode,
            }
        )
        evidence_bundle = evidence_bundle.model_copy(
            update={
                "metadata": {
                    **evidence_bundle.metadata,
                    "voi_model_status": [
                        status.model_dump(mode="json") for status in predictive_voi.model_status()
                    ],
                }
            }
        )
        evidence_ref = persist_promotion_evidence_bundle(
            ctx.store,
            evidence_bundle,
            inputs=[
                InputRef(artifact_id=candidate_ref.artifact_id, role="candidate"),
                InputRef(artifact_id=selection_vector_ref.artifact_id, role="policy_evaluation"),
                InputRef(artifact_id=selection_ref.artifact_id, role="selection_evaluation"),
            ],
        )
        funnel_context["promotion_evidence_bundle_ref"] = evidence_ref

        orchestrator = FunnelOrchestrator(
            stages=[
                Level0StaticValidator(),
                Level1CheapHeuristic(),
                Level2CausalPlausibility(),
                Level3MediumFidelity(
                    workflow_engine=_PolicyRuntimeWorkflowEngine(
                        fidelity="medium",
                        backend=runtime_backend,
                    ),
                    subsample_fraction=0.35,
                    bootstrap_draws=64,
                    estimator_tier="matching",
                    scenario_set="medium",
                    top_k_subgroups=3,
                ),
                Level4FullFidelity(
                    workflow_engine=_PolicyRuntimeWorkflowEngine(
                        fidelity="full",
                        backend=runtime_backend,
                    ),
                    estimated_cost_usd=0.20,
                ),
                Level5RefutationGovernanceStage(
                    require_hidden_holdout=True,
                    require_platform_meta=True,
                    store=ctx.store,
                ),
                Level6PromotionStage(
                    promotion_runner=lambda _candidate, context: _policy_promotion_runner(
                        ctx,
                        state,
                        candidate,
                        candidate_ref,
                        context,
                    ),
                    store=ctx.store,
                ),
            ],
            correlation_tracker=CorrelationTracker(),
            lesson_registry=LessonRegistry(
                root=Path(ctx.store.root) / "search_registry" / "lessons",
                store=ctx.store,
            ),
            voi_scheduler=predictive_voi,
        )

        ticket = orchestrator.submit(_candidate_search_payload(candidate, state), funnel_context)
        outcome = orchestrator.advance(ticket, policy="full")
        persist_predictive_voi_scheduler(
            ctx,
            transfer_context=transfer_context,
            scheduler=predictive_voi,
        )

        final_evaluation_vector, final_evaluation_ref = _resolve_runtime_policy_evaluation(
            ctx,
            candidate_ref=candidate_ref,
            outcome=outcome,
            fallback=selection_vector,
        )
        stage4_feedback = dict(
            (outcome.stage_results.get(4).feedback or {})
            if outcome.stage_results.get(4) is not None
            else {}
        )
        evidence_bundle = evidence_bundle.model_copy(
            update={
                "evaluation_ref": final_evaluation_ref,
                "metadata": {
                    **evidence_bundle.metadata,
                    "voi_model_status": [
                        status.model_dump(mode="json") for status in predictive_voi.model_status()
                    ],
                    "voi_scope": {
                        "task_family": str(transfer_context.get("task_family") or "policy"),
                        "domain": str(transfer_context.get("domain") or ""),
                        "tenant_scope": str(transfer_context.get("tenant_hash") or ""),
                    },
                    "promotion_grade_fidelity": (
                        "full" if outcome.stage_results.get(4) is not None else "selection_only"
                    ),
                    "promotion_grade_backend_kind": (
                        str(
                            stage4_feedback.get("policy_runtime_backend_kind")
                            or selection_artifact.provenance.backend_kind
                        )
                    ),
                    "promotion_grade_promotable_source": bool(
                        stage4_feedback.get(
                            "policy_runtime_promotable_source",
                            selection_artifact.provenance.promotable_source,
                        )
                    ),
                    "promotion_grade_degradation_mode": (
                        str(stage4_feedback.get("policy_runtime_degradation_mode"))
                        if stage4_feedback.get("policy_runtime_degradation_mode") is not None
                        else selection_artifact.provenance.degradation_mode
                    ),
                },
            }
        )
        evidence_ref = persist_promotion_evidence_bundle(
            ctx.store,
            evidence_bundle,
            inputs=[
                InputRef(artifact_id=candidate_ref.artifact_id, role="candidate"),
                InputRef(artifact_id=selection_ref.artifact_id, role="selection_evaluation"),
                *(
                    [
                        InputRef(
                            artifact_id=final_evaluation_ref.artifact_id, role="policy_evaluation"
                        )
                    ]
                    if final_evaluation_ref is not None
                    else []
                ),
            ],
        )
        voi_input_refs = [
            ref for ref in (candidate_ref, final_evaluation_ref, evidence_ref) if ref is not None
        ]
        voi_report = predictive_voi.report_for_decisions(
            run_id=state.run_id,
            decisions=(
                [outcome.last_scheduling_decision]
                if outcome.last_scheduling_decision is not None
                else []
            ),
            calibration_status=str(state.params.get("voi_calibration_status") or "shadow"),
            input_refs_by_candidate_id=(
                {outcome.candidate_hash: voi_input_refs}
                if outcome.last_scheduling_decision is not None
                else {}
            ),
            metadata={
                "source": "run_policy_blueprint_runtime",
                "final_action": outcome.final_action,
                "completed": outcome.completed,
                "trace_step_count": len(outcome.trace),
            },
        )
        voi_report_ref = persist_voi_run_report(ctx.store, voi_report)

        new_state = branch_state(
            state,
            write_paths=(
                "artifacts_index",
                "params.policy_candidate_ref",
                "params.policy_evaluation",
                "params.policy_evaluation_ref",
                "params.promotion_evidence_bundle_ref",
                "params.funnel_outcome",
                "params._funnel_outcome",
                "params.policy_level5_gate",
                "params.policy_runtime_source_statuses",
                "params.audit_refs",
                "params.actionable_side_information_refs",
                "params.voi_run_report_ref",
                "params.strategic_response",
                "params.strategic_response_source",
            ),
        ).state
        new_state.artifacts_index.update(runtime_artifacts_index)
        new_state.params["policy_candidate_ref"] = candidate_ref.model_dump(mode="json")
        new_state.params["policy_evaluation"] = final_evaluation_vector.model_dump(mode="json")
        if final_evaluation_ref is not None:
            new_state.params["policy_evaluation_ref"] = final_evaluation_ref.model_dump(mode="json")
        new_state.params["promotion_evidence_bundle_ref"] = evidence_ref.model_dump(mode="json")
        new_state.params["funnel_outcome"] = _serialize_funnel_outcome(outcome)
        new_state.params["_funnel_outcome"] = _serialize_funnel_outcome(outcome)
        new_state.params["policy_level5_gate"] = _extract_level5_gate(outcome)
        new_state.params["policy_runtime_source_statuses"] = dict(runtime_source_statuses)
        new_state.params["audit_refs"] = [ref.model_dump(mode="json") for ref in outcome.audit_refs]
        new_state.params["actionable_side_information_refs"] = [
            ref.model_dump(mode="json") for ref in outcome.actionable_side_information_refs
        ]
        new_state.params["voi_run_report_ref"] = voi_report_ref.model_dump(mode="json")
        if strategic_output.strategic_response_summary is not None:
            new_state.params["strategic_response"] = dict(
                strategic_output.strategic_response_summary
            )
            new_state.params.setdefault("strategic_response_source", "policy_runtime")
        new_state.artifacts_index[ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF] = evidence_ref
        new_state.artifacts_index[ARTIFACT_VOI_RUN_REPORT_REF] = voi_report_ref
        if platform_meta_ref is not None:
            new_state.artifacts_index[ARTIFACT_PLATFORM_META_EVALUATION_REPORT_REF] = (
                platform_meta_ref
            )
        if stress_report_ref is not None:
            new_state.artifacts_index[ARTIFACT_STRESS_TEST_REPORT_REF] = stress_report_ref
        if ambiguity_certificate_ref is not None:
            new_state.artifacts_index[ARTIFACT_OPTIMIZATION_AMBIGUITY_CERTIFICATE_REF] = (
                ambiguity_certificate_ref
            )

        promotion_feedback = (
            dict(outcome.final_result.feedback or {}) if outcome.final_result else {}
        )
        promotion_payload = promotion_feedback.get("promotion_result")
        if hasattr(promotion_payload, "model_dump"):
            new_state.params["policy_promotion_result"] = promotion_payload.model_dump(mode="json")
            new_state.params["judge_verdict"] = promotion_payload.judge_verdict.model_dump(
                mode="json"
            )
            new_state.params["decision_readiness_contract"] = (
                promotion_payload.readiness_contract.model_dump(mode="json")
            )
            new_state.params["promotion_decision"] = (
                promotion_payload.promotion_decision.model_dump(mode="json")
            )
            if promotion_payload.readiness_ref is not None:
                new_state.artifacts_index[ARTIFACT_DECISION_READINESS_CONTRACT_REF] = (
                    promotion_payload.readiness_ref
                )
        elif isinstance(promotion_feedback, dict):
            if "judge_verdict" in promotion_feedback:
                new_state.params["judge_verdict"] = promotion_feedback["judge_verdict"]
            if "decision_readiness_contract" in promotion_feedback:
                new_state.params["decision_readiness_contract"] = promotion_feedback[
                    "decision_readiness_contract"
                ]
            if "promotion_reason" in promotion_feedback:
                new_state.params["promotion_decision"] = {
                    "promoted": False,
                    "reason": promotion_feedback["promotion_reason"],
                }

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[
                selection_ref,
                evidence_ref,
                *([ambiguity_certificate_ref] if ambiguity_certificate_ref is not None else []),
                *(
                    [strategic_output.strategic_scm_ref]
                    if strategic_output.strategic_scm_ref is not None
                    else []
                ),
                *(
                    [strategic_output.strategic_response_bundle_ref]
                    if strategic_output.strategic_response_bundle_ref is not None
                    else []
                ),
                *([platform_meta_ref] if platform_meta_ref is not None else []),
                *([stress_report_ref] if stress_report_ref is not None else []),
                voi_report_ref,
            ],
            events=[
                NodeEvent(
                    level="info",
                    message="Blueprint-native policy runtime executed through L0-L6.",
                    attrs={
                        "final_action": outcome.final_action,
                        "completed": outcome.completed,
                        "has_hidden_holdout": hidden_holdout_ref is not None,
                    },
                ),
                *(
                    [
                        NodeEvent(
                            level="info",
                            message=(
                                "Policy runtime inferred evidence source availability from config "
                                "because no cross-graph profile artifact was available."
                            ),
                            attrs={"evidence_source_statuses": dict(runtime_source_statuses)},
                        )
                    ]
                    if cross_graph_profile is None and runtime_source_statuses
                    else []
                ),
                *(
                    [
                        NodeEvent(
                            level="warn",
                            message="Phase D.4 challenge suites emitted warnings.",
                            attrs={"warnings": list(phase_d4_warnings)},
                        )
                    ]
                    if phase_d4_warnings
                    else []
                ),
                *(
                    [
                        NodeEvent(
                            level="warn",
                            message="Strategic runtime artifact flow emitted warnings.",
                            attrs={"warnings": list(strategic_output.warnings)},
                        )
                    ]
                    if strategic_output.warnings
                    else []
                ),
            ],
        )


def _candidate_search_payload(
    candidate: PolicyCandidateSchema,
    state: ExperimentState,
) -> dict[str, Any]:
    payload = candidate.as_search_payload()
    bundle = candidate.trinity_bundle
    payload["semantic"] = {
        "interventions": [
            {
                "id": intervention.intervention_id,
                "type": intervention.kind,
                "variable": parameter.param_path or parameter.param_id,
                "parameters": intervention.params,
            }
            for intervention in bundle.policy_spec.interventions
            for parameter in bundle.policy_spec.parameters
            if parameter.intervention_id == intervention.intervention_id
        ],
        "objectives": [
            {
                "name": objective.objective_id,
                "variable": objective.metric_id,
            }
            for objective in bundle.problem_frame.objectives
        ],
        "causal_graph": state.params.get("causal_graph"),
    }
    if "causal_graph" in state.params:
        payload["causal_graph"] = state.params["causal_graph"]
    payload.setdefault("metadata", {})
    payload["metadata"]["task_family"] = "policy"
    payload["metadata"]["domain"] = str(
        candidate.metadata.get("domain")
        or state.params.get("policy_request_domain")
        or state.run_id
    )
    return payload


def _ensure_calibration_report(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> ArtifactRef:
    if (ref := state.inputs.get(INPUT_CALIBRATION_REPORT_REF)) is not None:
        return ref
    report = build_calibration_report()
    if isinstance(state.params.get("correlation_metrics"), dict):
        report = report.model_copy(
            update={
                "current_mode": str(
                    state.params["correlation_metrics"].get("routing_mode", report.current_mode)
                ),
                "routing_health": {
                    **report.routing_health,
                    **dict(state.params["correlation_metrics"]),
                },
            }
        )
    return persist_funnel_calibration_report(ctx.store, report)


def _persist_runtime_strategic_artifacts(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    candidate_ref: ArtifactRef,
    selection_vector_ref: ArtifactRef,
    selection_artifact,
    artifacts_index: dict[str, ArtifactRef],
) -> _StrategicRuntimeOutput:
    strategic_payload = state.params.get("strategic_scm")
    if strategic_payload is None:
        return _StrategicRuntimeOutput()
    inputs = _runtime_strategic_inputs(
        candidate_ref=candidate_ref,
        selection_vector_ref=selection_vector_ref,
        abstraction_certificate_ref=artifacts_index.get(ARTIFACT_ABSTRACTION_CERTIFICATE_REF),
    )
    try:
        contract = (
            strategic_payload
            if isinstance(strategic_payload, StrategicSCM)
            else StrategicSCM.model_validate(strategic_payload)
        )
        payoff_tables = _coerce_runtime_payoff_tables(state.params.get("strategic_payoff_tables"))
        macro_payload = state.params.get("macro_strategic_payoff_tables")
        macro_payoff_tables = (
            None if macro_payload is None else _coerce_runtime_payoff_tables(macro_payload)
        )
    except _POLICY_RUNTIME_VALIDATION_ERRORS as exc:
        return _StrategicRuntimeOutput(
            strategic_response_summary=_build_blocked_strategic_summary(
                blocked_reason="strategic_runtime_invalid_input",
            ),
            warnings=(f"strategic_runtime_invalid_input:{exc}",),
        )

    try:
        utility_ref_status = _compare_existing_payoff_refs(
            ctx,
            refs=contract.utility_refs,
            raw_tables=payoff_tables,
        )
        macro_ref_status = None
        if macro_payoff_tables is not None and contract.macro_utility_refs is not None:
            macro_ref_status = _compare_existing_payoff_refs(
                ctx,
                refs=contract.macro_utility_refs,
                raw_tables=macro_payoff_tables,
            )
        blocked_reason = _strategic_payoff_ref_block_reason(
            utility_ref_status=utility_ref_status,
            macro_ref_status=macro_ref_status,
        )
        if blocked_reason is not None:
            strategic_scm_ref = ArtifactRef.model_validate(
                persist_strategic_scm(ctx.store, contract, inputs=inputs).model_dump(mode="json")
            )
            return _StrategicRuntimeOutput(
                strategic_scm_ref=strategic_scm_ref,
                strategic_response_summary=_build_blocked_strategic_summary(
                    blocked_reason=blocked_reason,
                    strategic_scm_ref=strategic_scm_ref,
                ),
                warnings=(f"strategic_runtime_blocked:{blocked_reason}",),
            )
        causal_report_ref = artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
        if causal_report_ref is None:
            blocked_reason = "missing_causal_report_for_strategic_decomposition"
            strategic_scm_ref = ArtifactRef.model_validate(
                persist_strategic_scm(ctx.store, contract, inputs=inputs).model_dump(mode="json")
            )
            return _StrategicRuntimeOutput(
                strategic_scm_ref=strategic_scm_ref,
                strategic_response_summary=_build_blocked_strategic_summary(
                    blocked_reason=blocked_reason,
                    strategic_scm_ref=strategic_scm_ref,
                ),
                warnings=(f"strategic_runtime_blocked:{blocked_reason}",),
            )
        persisted_utility_refs = _persist_runtime_payoff_tables(
            ctx,
            tables=payoff_tables,
            inputs=inputs,
        )
        persisted_macro_refs = (
            None
            if macro_payoff_tables is None
            else _persist_runtime_payoff_tables(
                ctx,
                tables=macro_payoff_tables,
                inputs=inputs,
            )
        )
        normalized_contract = contract.model_copy(
            update={
                "utility_refs": persisted_utility_refs,
                "macro_utility_refs": persisted_macro_refs,
            }
        )
        strategic_scm_ref = ArtifactRef.model_validate(
            persist_strategic_scm(ctx.store, normalized_contract, inputs=inputs).model_dump(
                mode="json"
            )
        )
        abstraction_certificate = _load_runtime_abstraction_certificate(ctx, artifacts_index)
        baseline_policy_value = _selection_baseline_policy_value(selection_artifact)
        result = solve_strategic_response(
            normalized_contract,
            payoff_tables,
            baseline_policy_value=baseline_policy_value,
            abstraction_certificate=abstraction_certificate,
            macro_payoff_tables=macro_payoff_tables,
            performative_loop_spec=state.params.get("performative_loop_spec"),
            mean_field_inputs=state.params.get("mean_field_game"),
        )
        causal_component_ref = ArtifactRefModel.model_validate(
            causal_report_ref.model_dump(mode="json")
        )
        bundle, bundle_ref = persist_strategic_solve_artifacts(
            ctx.store,
            causal_component_ref=causal_component_ref,
            result=result,
            equilibrium_concept=normalized_contract.equilibrium_concept,
            equilibrium_descriptor=normalized_contract.equilibrium_descriptor,
            baseline_policy_value=baseline_policy_value,
            inputs=inputs,
            metadata={
                "run_id": state.run_id,
                "strategic_scm_ref": strategic_scm_ref.model_dump(mode="json"),
            },
            mfg_equilibrium_certificate=result.mfg_equilibrium_certificate,
            mfg_macro_simulation_config=result.mfg_macro_simulation_config,
            mfg_solver_residual_report=result.mfg_solver_residual_report,
            mfg_mass_conservation_report=result.mfg_mass_conservation_report,
        )
        strategic_response_bundle_ref = ArtifactRef.model_validate(
            bundle_ref.model_dump(mode="json")
        )
        summary = strategic_result_summary(result)
        summary.update(
            {
                "strategic_scm_ref": strategic_scm_ref.model_dump(mode="json"),
                "strategic_response_bundle_ref": strategic_response_bundle_ref.model_dump(
                    mode="json"
                ),
                "causal_component_ref": bundle.causal_component_ref.model_dump(mode="json"),
                "strategic_closure_ref": bundle.strategic_closure_ref.model_dump(mode="json"),
                "equilibrium_set_ref": bundle.equilibrium_set_ref.model_dump(mode="json"),
                "post_adaptation_policy_value_ref": bundle.post_adaptation_policy_value_ref.model_dump(
                    mode="json"
                ),
                "selected_equilibrium_ref": (
                    None
                    if bundle.selected_equilibrium_ref is None
                    else bundle.selected_equilibrium_ref.model_dump(mode="json")
                ),
                "mfg_equilibrium_ref": (
                    None
                    if bundle.mfg_equilibrium_ref is None
                    else bundle.mfg_equilibrium_ref.model_dump(mode="json")
                ),
                "performative_shift_ref": (
                    None
                    if bundle.performative_shift_ref is None
                    else bundle.performative_shift_ref.model_dump(mode="json")
                ),
            }
        )
        return _StrategicRuntimeOutput(
            strategic_scm_ref=strategic_scm_ref,
            strategic_response_bundle_ref=strategic_response_bundle_ref,
            strategic_response_summary=summary,
            warnings=tuple(str(item) for item in result.warnings),
        )
    except _POLICY_RUNTIME_LOAD_ERRORS as exc:
        return _StrategicRuntimeOutput(
            strategic_response_summary=_build_blocked_strategic_summary(
                blocked_reason="strategic_runtime_persistence_failed",
            ),
            warnings=(f"strategic_runtime_persistence_failed:{exc}",),
        )


def _runtime_strategic_inputs(
    *,
    candidate_ref: ArtifactRef,
    selection_vector_ref: ArtifactRef,
    abstraction_certificate_ref: ArtifactRef | None,
) -> list[IRInputRef]:
    inputs = [
        IRInputRef(artifact_id=candidate_ref.artifact_id, role="candidate"),
        IRInputRef(artifact_id=selection_vector_ref.artifact_id, role="policy_evaluation"),
    ]
    if abstraction_certificate_ref is not None:
        inputs.append(
            IRInputRef(
                artifact_id=abstraction_certificate_ref.artifact_id,
                role="abstraction_certificate",
            )
        )
    return inputs


def _coerce_runtime_payoff_tables(payload: Any) -> dict[str, FiniteStrategicPayoffTable]:
    if not isinstance(payload, dict) or not payload:
        raise ValueError("strategic_payoff_tables must be a non-empty mapping")
    tables: dict[str, FiniteStrategicPayoffTable] = {}
    for agent, table_payload in payload.items():
        tables[str(agent)] = (
            table_payload
            if isinstance(table_payload, FiniteStrategicPayoffTable)
            else FiniteStrategicPayoffTable.model_validate(table_payload)
        )
    return tables


def _persist_runtime_payoff_tables(
    ctx: ExecutionContext,
    *,
    tables: dict[str, FiniteStrategicPayoffTable],
    inputs: list[IRInputRef],
) -> dict[str, ArtifactRefModel]:
    return {
        agent: persist_strategic_payoff_table(ctx.store, table, inputs=inputs)
        for agent, table in tables.items()
    }


def _payoff_table_signature(table: FiniteStrategicPayoffTable) -> dict[str, Any]:
    return {
        "agent": table.agent,
        "strategic_agents": tuple(table.strategic_agents),
        "action_spaces": {agent: tuple(actions) for agent, actions in table.action_spaces.items()},
        "payoffs": {key: float(value) for key, value in table.payoffs.items()},
    }


def _strategic_payoff_ref_block_reason(
    *,
    utility_ref_status: str,
    macro_ref_status: str | None,
) -> str | None:
    statuses = (utility_ref_status, macro_ref_status)
    if "unreadable_ref" in statuses:
        return "strategic_contract_payoff_ref_unreadable"
    if "mismatch" in statuses:
        return "strategic_contract_payoff_ref_mismatch"
    return None


def _compare_existing_payoff_refs(
    ctx: ExecutionContext,
    *,
    refs: dict[str, ArtifactRefModel],
    raw_tables: dict[str, FiniteStrategicPayoffTable],
) -> str:
    loaded_tables: dict[str, FiniteStrategicPayoffTable] = {}
    try:
        for agent, ref in refs.items():
            loaded_tables[agent] = load_strategic_payoff_table(ctx.store, ref)
    except _POLICY_RUNTIME_LOAD_ERRORS:
        return "unreadable_ref"
    if set(loaded_tables) != set(raw_tables):
        return "mismatch"
    matches = all(
        _payoff_table_signature(loaded_tables[agent]) == _payoff_table_signature(raw_tables[agent])
        for agent in raw_tables
    )
    return "match" if matches else "mismatch"


def _build_blocked_strategic_summary(
    *,
    blocked_reason: str,
    strategic_scm_ref: ArtifactRef | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "fallback_mode": "blocked",
        "equilibrium_selection_dependence": "runtime_precondition_blocked",
        "multiplicity_note": None,
        "blocked_reason": str(blocked_reason),
        "closure_summary": {
            "mode": "blocked",
            "blocked_reason": str(blocked_reason),
        },
        "warnings": [],
    }
    if strategic_scm_ref is not None:
        summary["strategic_scm_ref"] = strategic_scm_ref.model_dump(mode="json")
    return summary


def _selection_baseline_policy_value(selection_artifact: Any) -> float | None:
    simulation_results = getattr(selection_artifact, "simulation_results", None)
    if isinstance(simulation_results, dict):
        raw = simulation_results.get("policy_value")
        if raw is not None:
            try:
                return float(raw)
            except _POLICY_RUNTIME_VALIDATION_ERRORS:
                return None
    return None


def _load_runtime_abstraction_certificate(
    ctx: ExecutionContext,
    artifacts_index: dict[str, ArtifactRef],
) -> AbstractionCertificate | None:
    ref = artifacts_index.get(ARTIFACT_ABSTRACTION_CERTIFICATE_REF)
    if ref is None:
        return None
    try:
        return load_abstraction_certificate(
            ctx.store,
            ref,
        )
    except _POLICY_RUNTIME_LOAD_ERRORS:
        return None


def _build_runtime_abstraction_metadata(
    ctx: ExecutionContext,
    *,
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    certificate_ref = artifacts_index.get(ARTIFACT_ABSTRACTION_CERTIFICATE_REF)
    if certificate_ref is not None:
        metadata["abstraction_certificate_ref"] = certificate_ref.model_dump(mode="json")
        certificate = _load_runtime_abstraction_certificate(ctx, artifacts_index)
        if certificate is not None:
            metadata["abstraction_preservation_type"] = certificate.preservation_type.value
    return metadata


_StrategicRuntimeOutput = _SharedStrategicRuntimeOutput
_build_blocked_strategic_summary = _shared_build_blocked_strategic_summary
_selection_baseline_policy_value = _shared_selection_baseline_policy_value
_load_runtime_abstraction_certificate = _shared_load_runtime_abstraction_certificate
_build_runtime_abstraction_metadata = _shared_build_runtime_abstraction_metadata
_resolve_existing_strategic_output = _shared_resolve_existing_strategic_output


def _persist_runtime_strategic_artifacts(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    candidate_ref: ArtifactRef,
    selection_vector_ref: ArtifactRef,
    selection_artifact,
    artifacts_index: dict[str, ArtifactRef],
) -> _SharedStrategicRuntimeOutput:
    return _shared_persist_runtime_strategic_artifacts(
        ctx,
        state,
        artifacts_index=artifacts_index,
        candidate_ref=candidate_ref,
        evidence_ref=selection_vector_ref,
        evidence_role="policy_evaluation",
        baseline_payload=selection_artifact,
    )


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


def _ensure_stress_test_report(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    evaluation_vector: PolicyEvaluationVector,
    supplemental_reports: list[StressTestReport] | None = None,
    phase_d4_suite_ids: list[str] | None = None,
) -> ArtifactRef | None:
    existing_ref = state.artifacts_index.get(ARTIFACT_STRESS_TEST_REPORT_REF)
    replacement_suite_ids = [str(item) for item in (phase_d4_suite_ids or []) if str(item).strip()]
    if existing_ref is not None and not supplemental_reports and not replacement_suite_ids:
        return existing_ref

    report = _load_stress_test_report(ctx, existing_ref)
    if report is None:
        report = StressTestReport(
            report_id=f"stress_{state.run_id}",
            total_scenarios_evaluated=1,
            vulnerabilities=build_vulnerabilities(
                evaluation=evaluation_vector,
                distributional=load_distributional_report_for_state(ctx, state),
                causal_report=load_causal_report(ctx, state),
                governance_report=load_governance_report(ctx, state),
            ),
            robustness_score=0.0,
            metadata={
                "generated_by": "run_policy_blueprint_runtime",
                "phase_d4_suite_ids": [],
                "phase_d4_suite_scenario_counts": {},
                "base_total_scenarios_evaluated": 1,
            },
        )
    report = _merge_stress_test_reports(
        report,
        supplemental_reports or [],
        replacement_suite_ids=replacement_suite_ids,
    )
    report = _recompute_stress_test_report(report)
    return ctx.store.put_json(
        report,
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _merge_stress_test_reports(
    base_report: StressTestReport,
    supplemental_reports: list[StressTestReport],
    *,
    replacement_suite_ids: list[str] | None = None,
) -> StressTestReport:
    replacement_suite_ids_set = {
        str(item).strip() for item in (replacement_suite_ids or []) if str(item).strip()
    }
    if not supplemental_reports and not replacement_suite_ids_set:
        return base_report
    replacement_suite_ids_set.update(
        str(report.metadata.get("challenge_suite_id")).strip()
        for report in supplemental_reports
        if str(report.metadata.get("challenge_suite_id") or "").strip()
    )
    vulnerabilities = [
        item
        for item in base_report.vulnerabilities
        if _phase_d4_suite_id_from_vulnerability(item) not in replacement_suite_ids_set
    ]
    suite_scenario_counts = {
        str(key): int(value)
        for key, value in dict(
            base_report.metadata.get("phase_d4_suite_scenario_counts") or {}
        ).items()
        if str(key).strip()
    }
    for suite_id in replacement_suite_ids_set:
        suite_scenario_counts.pop(suite_id, None)
    base_total_scenarios = int(
        base_report.metadata.get(
            "base_total_scenarios_evaluated",
            max(
                int(base_report.total_scenarios_evaluated) - sum(suite_scenario_counts.values()), 0
            ),
        )
    )
    for supplemental in supplemental_reports:
        vulnerabilities.extend(supplemental.vulnerabilities)
        suite_id = supplemental.metadata.get("challenge_suite_id")
        if suite_id is not None and str(suite_id).strip():
            suite_scenario_counts[str(suite_id)] = int(supplemental.total_scenarios_evaluated)
    total_scenarios = base_total_scenarios + sum(suite_scenario_counts.values())
    return base_report.model_copy(
        update={
            "total_scenarios_evaluated": total_scenarios,
            "vulnerabilities": vulnerabilities,
            "metadata": {
                **dict(base_report.metadata),
                "phase_d4_suite_ids": sorted(suite_scenario_counts),
                "phase_d4_suite_scenario_counts": suite_scenario_counts,
                "base_total_scenarios_evaluated": base_total_scenarios,
            },
        }
    )


def _phase_d4_suite_id_from_vulnerability(vulnerability) -> str | None:
    candidate = str(getattr(vulnerability, "vulnerability_id", "")).strip()
    if ":" not in candidate:
        return None
    suite_id, _, _ = candidate.partition(":")
    if suite_id in {
        STRATEGIC_GAMING_SUITE_ID,
        MULTIPLICITY_DISCLOSURE_SUITE_ID,
        ABSTRACTION_LEAKAGE_SUITE_ID,
    }:
        return suite_id
    return None


def _recompute_stress_test_report(report: StressTestReport) -> StressTestReport:
    return report.model_copy(
        update={
            "critical_count": sum(
                1 for item in report.vulnerabilities if item.severity == "critical"
            ),
            "high_count": sum(1 for item in report.vulnerabilities if item.severity == "high"),
            "medium_count": sum(1 for item in report.vulnerabilities if item.severity == "medium"),
            "robustness_score": max(
                0.0,
                1.0
                - (
                    sum(
                        1
                        for item in report.vulnerabilities
                        if item.severity in {"critical", "high"}
                    )
                    / max(len(report.vulnerabilities), 1)
                ),
            ),
        }
    )


def _resolve_policy_runtime_source_statuses(
    *,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    evidence_sources,
) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if cross_graph_profile is not None:
        statuses.update(
            {key: value.status.value for key, value in cross_graph_profile.source_statuses.items()}
        )

    inferred = {
        EvidenceSourceKind.ACADEMIC.value: build_path_source_status(
            EvidenceSourceKind.ACADEMIC,
            evidence_sources.academic_db_path,
            detail="policy_runtime_evidence_sources",
        ).status.value,
        EvidenceSourceKind.DATASETS.value: build_path_source_status(
            EvidenceSourceKind.DATASETS,
            evidence_sources.datasets_db_path,
            detail="policy_runtime_evidence_sources",
        ).status.value,
        EvidenceSourceKind.LEGAL.value: build_path_source_status(
            EvidenceSourceKind.LEGAL,
            evidence_sources.legal_db_path,
            detail="policy_runtime_evidence_sources",
        ).status.value,
    }
    benchmark_path = (
        str(evidence_sources.benchmark_report_path or "").strip()
        or str(evidence_sources.benchmark_suite_path or "").strip()
        or None
    )
    inferred[EvidenceSourceKind.BENCHMARK.value] = build_path_source_status(
        EvidenceSourceKind.BENCHMARK,
        benchmark_path,
        detail="policy_runtime_evidence_sources",
    ).status.value
    for key, value in inferred.items():
        statuses.setdefault(key, value)
    return statuses


def _register_runtime_benchmark_inputs(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    benchmark_registry: BenchmarkRegistry,
    evidence_bundle: PromotionEvidenceBundle | None,
    family: str,
    query_type: str | None,
    estimator_name: str | None,
    readiness_target: str | None,
) -> None:
    expected_loop_id = _expected_policy_loop_id(state)
    hidden_holdout_ref = (
        evidence_bundle.hidden_holdout_evaluation_ref
        if evidence_bundle is not None
        else maybe_artifact_ref(state.params.get("hidden_holdout_evaluation_ref"))
    )
    _maybe_register_benchmark_evaluation(
        ctx,
        benchmark_registry=benchmark_registry,
        ref=hidden_holdout_ref,
        split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        run_id=state.run_id,
        expected_loop_id=expected_loop_id,
        family=family,
        query_type=query_type,
        estimator_name=estimator_name,
        readiness_target=readiness_target,
    )
    rotating_refs = (
        list(evidence_bundle.rotating_challenge_evaluation_refs)
        if evidence_bundle is not None and evidence_bundle.rotating_challenge_evaluation_refs
        else [
            ref
            for ref in (
                maybe_artifact_ref(item)
                for item in (state.params.get("rotating_challenge_evaluation_refs") or [])
            )
            if ref is not None
        ]
    )
    for ref in rotating_refs:
        _maybe_register_benchmark_evaluation(
            ctx,
            benchmark_registry=benchmark_registry,
            ref=ref,
            split_type=BenchmarkSplit.ROTATING_CHALLENGE,
            run_id=state.run_id,
            expected_loop_id=expected_loop_id,
            family=family,
            query_type=query_type,
            estimator_name=estimator_name,
            readiness_target=readiness_target,
        )


def _run_and_register_phase_d4_challenge_suites(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    benchmark_registry: BenchmarkRegistry,
    candidate_ref: ArtifactRef,
    selection_evaluation: BenchmarkEvaluation,
    benchmark_scope: dict[str, str | None],
    artifacts_index: dict[str, ArtifactRef],
) -> tuple[list[ArtifactRef], list[ArtifactRef], tuple[str, ...]]:
    suite_results, warnings = run_phase_d4_challenge_suites(
        store=ctx.store,
        run_id=state.run_id,
        loop_id=selection_evaluation.loop_id,
        candidate_ref=candidate_ref,
        params=state.params,
        artifacts_index=artifacts_index,
        selection_metadata=selection_evaluation.metadata,
    )
    benchmark_refs: list[ArtifactRef] = []
    stress_refs: list[ArtifactRef] = []

    for suite_result in suite_results:
        benchmark_ref = persist_benchmark_evaluation(
            ctx.store,
            suite_result.benchmark_evaluation,
            inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
        )
        benchmark_refs.append(benchmark_ref)
        benchmark_registry.record_evaluation(
            suite_result.benchmark_evaluation,
            benchmark_ref,
            run_id=state.run_id,
            family=benchmark_scope["artifact_family"],
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
            rotation_group=PHASE_D4_ROTATION_GROUP,
            produced_by_run_id=state.run_id,
            metadata={
                "artifact_family": benchmark_scope["artifact_family"],
                "claim_mode": benchmark_scope["claim_mode"],
                "rotation_group": PHASE_D4_ROTATION_GROUP,
                **dict(suite_result.benchmark_evaluation.metadata),
            },
        )
        if suite_result.stress_test_report is None:
            continue
        stress_ref = ctx.store.put_json(
            suite_result.stress_test_report,
            PutOptions(
                kind="scientist.stress_test_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.0"),
                inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        stress_refs.append(stress_ref)
        benchmark_registry.record(
            BenchmarkSplit.ADVERSARIAL.value,
            stress_ref,
            run_id=state.run_id,
            loop_id=selection_evaluation.loop_id,
            suite_id=suite_result.suite_id,
            suite_version=suite_result.suite_version,
            family=benchmark_scope["artifact_family"],
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
            rotation_group=PHASE_D4_ROTATION_GROUP,
            produced_by_run_id=state.run_id,
            artifact_kind="scientist.stress_test_report",
            metadata={
                "artifact_type": "stress_test_report",
                "artifact_family": benchmark_scope["artifact_family"],
                "claim_mode": benchmark_scope["claim_mode"],
                "rotation_group": PHASE_D4_ROTATION_GROUP,
                **dict(suite_result.stress_test_report.metadata),
            },
        )
    return benchmark_refs, stress_refs, warnings


def _dedupe_phase_d4_rotating_refs(
    ctx: ExecutionContext,
    refs: list[ArtifactRef],
) -> list[ArtifactRef]:
    latest_by_suite: dict[str, ArtifactRef] = {}
    ordered: list[tuple[str | None, ArtifactRef]] = []
    d4_suite_ids = {
        STRATEGIC_GAMING_SUITE_ID,
        MULTIPLICITY_DISCLOSURE_SUITE_ID,
        ABSTRACTION_LEAKAGE_SUITE_ID,
    }
    for ref in refs:
        evaluation = _load_benchmark_if_present(ctx, ref)
        suite_id = None
        if evaluation is not None:
            suite_id = str(
                evaluation.metadata.get("challenge_suite_id") or evaluation.suite_id or ""
            ).strip()
            if suite_id not in d4_suite_ids:
                suite_id = None
        ordered.append((suite_id, ref))
        if suite_id is not None:
            latest_by_suite[suite_id] = ref

    deduped: list[ArtifactRef] = []
    emitted_d4_suite_ids: set[str] = set()
    for suite_id, ref in reversed(ordered):
        if suite_id is None:
            deduped.append(ref)
            continue
        if suite_id in emitted_d4_suite_ids:
            continue
        emitted_d4_suite_ids.add(suite_id)
        deduped.append(latest_by_suite[suite_id])
    deduped.reverse()
    return deduped


def _maybe_register_benchmark_evaluation(
    ctx: ExecutionContext,
    *,
    benchmark_registry: BenchmarkRegistry,
    ref: ArtifactRef | None,
    split_type: BenchmarkSplit,
    run_id: str,
    expected_loop_id: str,
    family: str,
    query_type: str | None,
    estimator_name: str | None,
    readiness_target: str | None,
) -> None:
    if ref is None:
        return
    evaluation = _load_benchmark_if_present(ctx, ref)
    if evaluation is None:
        return
    if evaluation.loop_id != expected_loop_id:
        return
    if evaluation.resolved_runtime_split_type() is not split_type:
        return
    benchmark_registry.record_evaluation(
        evaluation,
        ref,
        run_id=run_id,
        family=family,
        query_type=query_type,
        estimator_name=estimator_name,
        readiness_target=readiness_target,
        produced_by_run_id=run_id,
        metadata={
            "loop_id": evaluation.loop_id,
            "artifact_family": family,
            "claim_mode": "estimation",
        },
    )


def _resolve_replay_bundle_ref(
    state: ExperimentState,
    evidence_bundle: PromotionEvidenceBundle | None,
) -> ArtifactRef | None:
    if evidence_bundle is not None and evidence_bundle.replay_bundle_ref is not None:
        return evidence_bundle.replay_bundle_ref
    return state.artifacts_index.get(ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF)


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


def _serialize_funnel_outcome(outcome: FunnelOutcome) -> dict[str, Any]:
    return {
        "ticket_id": outcome.ticket_id,
        "candidate_hash": outcome.candidate_hash,
        "trace": [
            {
                "fidelity_level": step.fidelity_level,
                "stage_name": step.stage_name,
                "objective_value": step.objective_value,
                "is_promising": step.is_promising,
                "duration_seconds": step.duration_seconds,
                "compute_actual_usd": step.compute_actual_usd,
                "routing_decision": step.routing_decision,
                "voi_action": step.voi_action,
                "voi_priority": step.voi_priority,
                "failure_count": step.failure_count,
                "blocker_count": step.blocker_count,
            }
            for step in outcome.trace
        ],
        "stage_results": {
            str(level): {
                "stage_name": result.stage_name,
                "objective_value": result.objective_value,
                "is_promising": result.is_promising,
                "feedback": result.feedback,
                "failure_cards": [card.model_dump(mode="json") for card in result.failure_cards],
                "fidelity_level": result.fidelity_level,
                "terminal_action": result.terminal_action,
            }
            for level, result in outcome.stage_results.items()
        },
        "final_action": outcome.final_action,
        "completed": outcome.completed,
        "degradation_mode": outcome.degradation_mode,
        "audit_refs": [ref.model_dump(mode="json") for ref in outcome.audit_refs],
        "actionable_side_information_refs": [
            ref.model_dump(mode="json") for ref in outcome.actionable_side_information_refs
        ],
    }


def _extract_level5_gate(outcome: FunnelOutcome) -> dict[str, Any]:
    level5 = outcome.stage_results.get(5)
    if level5 is None:
        return {"passed": False, "reason": "level5_not_executed"}
    return {
        "passed": level5.is_promising
        and level5.terminal_action not in {"reject", "defer_to_human"},
        "terminal_action": level5.terminal_action,
        "failure_count": len(level5.failure_cards),
        "critical_failures": [
            card.failure_type for card in level5.failure_cards if card.is_blocker
        ],
    }


def _resolve_degradation_mode(
    state: ExperimentState,
    *,
    hidden_holdout_ref: ArtifactRef | None | object = _UNSET,
    replay_bundle_ref: ArtifactRef | None | object = _UNSET,
    governance_ref: ArtifactRef | None | object = _UNSET,
) -> str:
    correlation_metrics = state.params.get("correlation_metrics")
    if isinstance(correlation_metrics, dict):
        routing_mode = str(correlation_metrics.get("routing_mode") or "").strip()
        if bool(correlation_metrics.get("promotion_ban_active")):
            return "no_promotion"
        if routing_mode:
            return routing_mode
    if (
        hidden_holdout_ref is not _UNSET
        or replay_bundle_ref is not _UNSET
        or governance_ref is not _UNSET
    ) and (hidden_holdout_ref is None or replay_bundle_ref is None or governance_ref is None):
        return "no_promotion"
    if state.params.get("calibration_drift_detected") is True:
        return "conservative_routing"
    return "normal"


def _resolve_benchmark_scope(
    *,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    selection_vector: PolicyEvaluationVector,
) -> dict[str, str | None]:
    metadata = dict(selection_vector.metadata or {})
    candidate_metadata = dict(candidate.metadata or {})
    query_type = (
        str(
            state.params.get("query_type")
            or candidate_metadata.get("query_type")
            or metadata.get("query_type")
            or "policy"
        ).strip()
        or None
    )
    estimator_name = (
        str(
            state.params.get("estimator_name")
            or metadata.get("estimator_name")
            or candidate_metadata.get("estimator_name")
            or ""
        ).strip()
        or None
    )
    artifact_family = normalize_phase2_artifact_family(
        str(
            state.params.get("artifact_family")
            or candidate_metadata.get("artifact_family")
            or metadata.get("artifact_family")
            or "causal_core"
        ).strip()
        or "causal_core",
        estimator_name=estimator_name,
        query_type=query_type,
    )
    claim_mode = (
        str(
            state.params.get("claim_mode")
            or candidate_metadata.get("claim_mode")
            or metadata.get("claim_mode")
            or "estimation"
        )
        .strip()
        .lower()
        or "estimation"
    )
    readiness_target = (
        str(
            state.params.get("readiness_target")
            or candidate_metadata.get("readiness_target")
            or metadata.get("readiness_target")
            or ""
        ).strip()
        or None
    )
    return {
        "artifact_family": artifact_family,
        "claim_mode": claim_mode,
        "query_type": query_type,
        "estimator_name": estimator_name,
        "readiness_target": readiness_target,
    }


def _expected_policy_loop_id(state: ExperimentState) -> str:
    return str(state.params.get("policy_loop_id") or state.run_id)


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


def _load_benchmark_if_present(
    ctx: ExecutionContext,
    ref: ArtifactRef | None,
) -> BenchmarkEvaluation | None:
    if ref is None:
        return None
    return load_benchmark_evaluation(ctx, ref)


def _load_stress_test_report(
    ctx: ExecutionContext,
    ref: ArtifactRef | None,
) -> StressTestReport | None:
    if ref is None:
        return None
    return StressTestReport.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
    )


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
