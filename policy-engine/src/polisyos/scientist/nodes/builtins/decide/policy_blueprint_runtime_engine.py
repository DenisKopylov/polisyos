from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import ModuleType
from typing import Any, Literal, cast

from polisyos.core.artifacts import ArtifactRef, InputRef
from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchorAssociation,
    OwnedAttemptAnchorRef,
)
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.methods.search.lessons import LessonRegistry
from polisyos.scientist.methods.search.objective import (
    SourceMetricObservation,
    objective_metrics_without_unestablished_fiscal_source,
    observe_source_government_balance,
)
from polisyos.scientist.methods.search.promotion_evidence import PromotionEvidenceBundle
from polisyos.scientist.methods.search.uncertainty import (
    _OWNER_SCOPE_UNSET,
    SearchHTESourceProjectionVerifier,
    SearchInputDependency,
    SearchOwnedAttemptAssociation,
    SearchOwnedHistoricalAttemptAssociationResolver,
    SearchOwnerSelectedSourceGraph,
    SearchRuntimeStageConfiguration,
    SearchUncertaintyOwnerTaskContext,
    _SearchOwnerCellScopeUnset,
    persist_search_uncertainty_v2,
    reconcile_search_method_selection_sources,
    resolve_search_uncertainty_store,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_state import maybe_artifact_ref
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    ProductionPolicyEvaluationBackend,
    _require_policy_runtime_registry_root,
    build_policy_runtime_evaluation,
    build_selection_benchmark_evaluation,
    persist_funnel_executed_work_packet,
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_METRICS_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
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
    runtime_request: Any
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
    method_metric_projection_identity: dict[str, Any] = field(default_factory=dict)
    method_metric_source_run_id: str | None = None
    method_metric_score_required: bool = False
    method_metric_source_request_status: str = "absent"
    source_measurement: SourceMetricObservation | None = None
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

    @property
    def method_metric_projection_basis(self) -> object | None:
        """Return the in-process admission held outside this session's dataclass fields."""
        return getattr(self.runtime_backend, "_policyos_method_metric_projection_basis", None)


def _method_metric_projection_cache_identity(
    projection: Any,
    *,
    requested_source_run_id: str | None,
    tenant_id: str | None,
    cell_id: str | None,
    request_status: str,
) -> dict[str, Any]:
    """Project only stable source identity into the funnel's cache context.

    The owner lookup runs before the funnel is submitted. A cache hit is eligible only
    for the same current resolution result and exact selected vector/profile; this
    mapping contains no observations, store, or admission capability.
    """
    identity: dict[str, Any] = {
        "request_status": request_status,
        "requested_source_run_id": requested_source_run_id,
        "resolved_status": getattr(projection, "status", "invalid"),
        "tenant_id": tenant_id,
        "cell_id": cell_id,
    }
    basis = getattr(projection, "basis", None)
    if basis is None:
        identity["limitations"] = list(getattr(projection, "limitations", ()))
        return identity

    try:
        identity["selected_source"] = {
            **basis.cache_source_identity(),
            "candidate_ref": basis.source_candidate_ref.materialize().model_dump(mode="json"),
            "experiment_state_ref": basis.source_experiment_state_ref.materialize().model_dump(
                mode="json"
            ),
            "projection_vector_ref": basis.projection_vector_ref.materialize().model_dump(
                mode="json"
            ),
            "verifier_revision": basis.verifier_revision,
            "verifier_implementation_sha256": basis.verifier_implementation_sha256,
        }
    except (AttributeError, TypeError, ValueError):
        identity["resolved_status"] = "invalid"
        identity["limitations"] = ["completed_method_metric_cache_identity_invalid"]
    return identity


def _stage_configuration_entries(
    stages: list[Any],
) -> tuple[tuple[dict[str, str | int | float | bool | None], ...], tuple[str, ...]]:
    """Read scalar configuration from the exact instantiated L0-L6 stage objects."""
    entries: list[dict[str, str | int | float | bool | None]] = []
    unresolved: set[str] = set()

    def capture_nested(
        value: object, prefix: str, entry: dict[str, str | int | float | bool | None]
    ) -> None:
        if value is None:
            entry[prefix] = None
            return
        nested = vars(value) if hasattr(value, "__dict__") else {}
        if not nested:
            unresolved.add(
                f"stage_binding:{prefix}:{type(value).__module__}.{type(value).__qualname__}"
            )
            return
        entry[f"{prefix}.class"] = f"{type(value).__module__}.{type(value).__qualname__}"
        for name, item in sorted(nested.items()):
            key = f"{prefix}.{name.lstrip('_')}"
            if name == "_store":
                entry[key] = f"{type(item).__module__}.{type(item).__qualname__}"
            elif callable(item):
                entry[key] = (
                    f"{getattr(item, '__module__', '')}.{getattr(item, '__qualname__', type(item).__qualname__)}"
                )
                unresolved.add(f"dynamic_stage_binding:{prefix}.{name}")
            elif isinstance(item, float) and not math.isfinite(item):
                entry[key] = "nonfinite:" + repr(item)
                unresolved.add(f"nonfinite_stage_binding:{key}")
            elif isinstance(item, (str, int, float, bool)) or item is None:
                entry[key] = item
            elif name in {"_engine", "_stage"}:
                capture_nested(item, key, entry)
            else:
                unresolved.add(f"unserialized_stage_config:{prefix}.{name}")

    for stage in sorted(stages, key=lambda item: int(item.fidelity_level)):
        entry: dict[str, str | int | float | bool | None] = {
            "stage_name": str(stage.stage_name),
            "fidelity_level": int(stage.fidelity_level),
            "implementation_fqn": f"{type(stage).__module__}.{type(stage).__qualname__}",
        }
        for name, value in sorted(vars(stage).items()):
            key = name.lstrip("_")
            if name == "_store":
                entry[key] = f"{type(value).__module__}.{type(value).__qualname__}"
            elif callable(value):
                entry[key] = (
                    f"{getattr(value, '__module__', '')}.{getattr(value, '__qualname__', type(value).__qualname__)}"
                )
                unresolved.add(f"dynamic_stage_binding:{stage.stage_name}.{name}")
            elif isinstance(value, float) and not math.isfinite(value):
                entry[key] = "nonfinite:" + repr(value)
                unresolved.add(f"nonfinite_stage_binding:{stage.stage_name}.{name}")
            elif isinstance(value, (str, int, float, bool)) or value is None:
                entry[key] = value
            elif name in {"_engine", "_stage"}:
                capture_nested(value, key, entry)
            else:
                unresolved.add(f"unserialized_stage_config:{stage.stage_name}.{name}")
        entries.append(entry)
    return tuple(entries), tuple(sorted(unresolved))


def _build_search_uncertainty_owner_context(
    session: _RuntimeSession,
    stages: list[Any],
) -> SearchUncertaintyOwnerTaskContext:
    """Persist owner-derived selected inputs after the real stage stack exists."""
    store = resolve_search_uncertainty_store(session.ctx.store)
    if store is None:
        raise TypeError("search_uncertainty_core_store_unavailable")
    stage_entries, unresolved_stage_bindings = _stage_configuration_entries(stages)
    stage_payload = {
        "owner_fqn": "polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine.run_runtime_funnel",
        "stages": stage_entries,
        "unresolved_bindings": unresolved_stage_bindings,
    }
    stage_digest = hashlib.sha256(
        json.dumps(stage_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    stage_configuration_ref = persist_search_uncertainty_v2(
        store,
        SearchRuntimeStageConfiguration(
            owner_fqn=stage_payload["owner_fqn"],
            stages=stage_entries,
            unresolved_bindings=unresolved_stage_bindings,
            configuration_sha256=stage_digest,
        ),
    )

    candidate_ref = session.candidate_ref
    selected_roots: dict[str, ArtifactRef] = {"candidate": candidate_ref}
    for attr, ref in (
        ("observational_data", session.state.observational_data_ref),
        ("execution_plan", session.state.execution_plan_ref),
        ("method_catalog_snapshot", session.state.method_catalog_snapshot_ref),
        ("policy_selection", session.selection_ref),
        ("stage_configuration", stage_configuration_ref),
    ):
        if isinstance(ref, ArtifactRef):
            selected_roots[attr] = ref
    for field_name in sorted(ExperimentState.model_fields):
        ref = getattr(session.state, field_name, None)
        if isinstance(ref, ArtifactRef):
            selected_roots[f"state.{field_name}"] = ref
    for group_name, values in (
        ("state_input", session.state.inputs),
        ("state_artifact", session.state.artifacts_index),
        ("state_report", session.state.reports_index),
    ):
        for name, ref in sorted(values.items()):
            if isinstance(ref, ArtifactRef):
                selected_roots[f"{group_name}.{name}"] = ref
    profiled_roots = tuple(
        SearchInputDependency(role_path=role, ref=ref)
        for role, ref in sorted(selected_roots.items())
        if ref.manifest_profile_sha256 is not None
    )
    missing: set[str] = set()
    unprofiled_roles = sorted(
        role for role, ref in selected_roots.items() if ref.manifest_profile_sha256 is None
    )
    if unprofiled_roles:
        missing.add("selected_source_ref_manifest_profile")
        missing.update(f"selected_source_ref_manifest_profile:{role}" for role in unprofiled_roles)
    source_graph_ref = None
    if profiled_roots:
        source_graph_ref = persist_search_uncertainty_v2(
            store,
            SearchOwnerSelectedSourceGraph(roots=profiled_roots),
        )
    else:
        missing.add("selected_source_graph_owner")

    plan_ref = session.state.execution_plan_ref
    selection_ref = session.selection_ref
    method_fqn = session.state.causal_method_fqn
    if not method_fqn:
        missing.add("selected_method_owner")
    tenant_id = session.ctx.run.tenant_id
    if not tenant_id:
        missing.add("owner_tenant_scope")
    if plan_ref is None or plan_ref.manifest_profile_sha256 is None:
        missing.add("selected_executable_plan_configuration_graph_rule_profile_procedure_selection")
        plan_ref = None
    if source_graph_ref is None:
        missing.add("selected_executable_plan_configuration_graph_rule_profile_procedure_selection")
    if selection_ref is None or selection_ref.manifest_profile_sha256 is None:
        missing.add("selected_executable_plan_configuration_graph_rule_profile_procedure_selection")
        selection_ref = None
    if unresolved_stage_bindings:
        missing.update(unresolved_stage_bindings)
    missing.update(
        {
            "selected_executable_plan_configuration_graph_rule_profile_procedure_selection",
            "selected_rule_owner",
            "selected_method_profile_owner",
            "selected_procedure_owner",
            "selected_method_abi_owner",
            "selected_inference_profile_owner",
            "selected_method_abi_params_profile",
            "semantic_scope_owner",
            "owned_hte_request_projection",
            "selected_method_seed",
            "selected_method_input_owner",
            "selected_method_input_content_digest",
        }
    )
    try:
        params_payload = json.dumps(
            session.state.causal_method_params,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        params_digest = None
        missing.add("selected_method_params_not_canonical")
    else:
        params_digest = hashlib.sha256(params_payload.encode("utf-8")).hexdigest()
    state_inputs = tuple(
        SearchInputDependency(role_path=role, ref=ref)
        for role, ref in sorted(selected_roots.items())
        if ref.manifest_profile_sha256 is not None
        and role not in {"candidate", "execution_plan", "policy_selection", "stage_configuration"}
    )
    missing.update(
        reconcile_search_method_selection_sources(
            store,
            expected_run_id=session.state.run_id,
            plan_ref=plan_ref,
            selected_state_input_refs=state_inputs,
            selected_method_fqn=method_fqn,
            selected_method_params=session.state.causal_method_params,
        )
    )
    return SearchUncertaintyOwnerTaskContext(
        owner_fqn="polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine.run_runtime_funnel",
        run_id=session.state.run_id,
        subject_ref=candidate_ref,
        selected_plan_ref=plan_ref,
        selected_configuration_ref=stage_configuration_ref,
        selected_source_graph_ref=source_graph_ref,
        selected_rule_ref=None,
        selected_profile_ref=None,
        selected_procedure_ref=None,
        selected_selection_ref=selection_ref,
        selected_method_fqn=method_fqn,
        selected_method_abi_version=None,
        selected_method_params_sha256=params_digest,
        selected_method_params=dict(session.state.causal_method_params),
        selected_inference_profile_id=None,
        tenant_id=tenant_id,
        cell_id=session.ctx.run.cell_id,
        semantic_scope=None,
        selected_stage_config_sha256=stage_digest,
        selected_state_input_refs=state_inputs,
        status="not_established",
        missing_slices=tuple(sorted(missing)),
    )


def prepare_runtime_session(
    ctx: ExecutionContext,
    state: ExperimentState,
    runtime_request: Any,
    owner: ModuleType,
) -> _RuntimeSession:
    """Resolve policy inputs and persist the selection evaluation in source order."""
    registry_root = _require_policy_runtime_registry_root(ctx.store)
    candidate = runtime_request.candidate
    candidate_ref = runtime_request.candidate_ref
    cross_graph_profile = runtime_request.cross_graph_profile
    evidence_sources = runtime_request.evidence_sources
    runtime_source_statuses = owner._resolve_policy_runtime_source_statuses(
        cross_graph_profile=cross_graph_profile,
        evidence_sources=evidence_sources,
    )
    method_metric_projection = owner.read_completed_admitted_method_metric_projection(
        ctx.store,
        owner=ctx.method_metric_selection_owner,
        source_run_id=runtime_request.method_metric_source_run_id,
        candidate_ref=candidate_ref,
        tenant_id=ctx.run.tenant_id,
        cell_id=ctx.run.cell_id,
        request_status=runtime_request.method_metric_source_request_status,
    )
    runtime_source_statuses["completed_method_metric_projection"] = method_metric_projection.status
    runtime_backend = owner.ProductionPolicyEvaluationBackend(
        eval_safety_execution_context=ctx.eval_safety_execution_context,
        eval_safety_verifier=ctx.eval_safety_verifier,
        world_model_record=owner._world_model_record_from_state(state),
    ).with_method_metric_projection_basis(
        basis=method_metric_projection.basis,
        candidate_ref=(candidate_ref if method_metric_projection.basis is not None else None),
    )
    method_metric_projection_identity = _method_metric_projection_cache_identity(
        method_metric_projection,
        requested_source_run_id=runtime_request.method_metric_source_run_id,
        tenant_id=ctx.run.tenant_id,
        cell_id=ctx.run.cell_id,
        request_status=runtime_request.method_metric_source_request_status,
    )
    input_signature = owner.policy_runtime_input_signature(
        candidate_ref=candidate_ref,
        state=state,
    )
    source_refs = {
        ARTIFACT_SIMULATION_RESULT_REF: owner.maybe_artifact_ref(
            state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        ),
        ARTIFACT_METRICS_REF: owner.maybe_artifact_ref(
            state.artifacts_index.get(ARTIFACT_METRICS_REF)
        ),
        ARTIFACT_STATE_SNAPSHOT_REF: owner.maybe_artifact_ref(
            state.artifacts_index.get(ARTIFACT_STATE_SNAPSHOT_REF)
        ),
    }
    source_measurement = None
    if any(ref is not None for ref in source_refs.values()):
        source_measurement = observe_source_government_balance(
            ctx.store,
            simulation_result_ref=source_refs[ARTIFACT_SIMULATION_RESULT_REF],
            metrics_ref=source_refs[ARTIFACT_METRICS_REF],
            state_snapshot_ref=source_refs[ARTIFACT_STATE_SNAPSHOT_REF],
        )
    simulation_metrics = objective_metrics_without_unestablished_fiscal_source(
        runtime_request.simulation_metrics,
        source_measurement,
    )
    selection_artifact = owner.build_policy_runtime_evaluation(
        candidate,
        backend=runtime_backend,
        fidelity="selection",
        simulation_metrics=simulation_metrics,
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
                **(
                    {}
                    if source_measurement is None
                    else {
                        "policy_runtime_source_measurement": source_measurement.model_dump(
                            mode="json", exclude_none=False
                        )
                    }
                ),
            }
        }
    )
    selection_vector_ref = owner.persist_policy_evaluation_vector(
        ctx,
        candidate_ref=candidate_ref,
        evaluation_vector=selection_vector,
        completed_projection_basis=getattr(
            runtime_backend, "_policyos_method_metric_projection_basis", None
        ),
        completed_projection_binding=selection_artifact.completed_projection_binding,
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
        return_selected_profile=True,
    )
    benchmark_scope = owner._resolve_benchmark_scope(
        state=state,
        candidate=candidate,
        selection_vector=selection_vector,
    )
    benchmark_registry = owner.BenchmarkRegistry(registry_root / "search_registry" / "benchmarks")
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
        runtime_request=runtime_request,
        candidate=candidate,
        candidate_ref=candidate_ref,
        uncertainty_envelope=runtime_request.uncertainty_envelope,
        governance_report=runtime_request.governance_report,
        causal_report=runtime_request.causal_report,
        distributional_report=runtime_request.distributional_report,
        cross_graph_profile=cross_graph_profile,
        evidence_sources=evidence_sources,
        runtime_source_statuses=runtime_source_statuses,
        simulation_metrics=simulation_metrics,
        source_measurement=source_measurement,
        ambiguity_certificate=runtime_request.ambiguity_certificate,
        ambiguity_certificate_ref=ambiguity_certificate_ref,
        runtime_backend=runtime_backend,
        input_signature=input_signature,
        method_metric_projection_identity=method_metric_projection_identity,
        method_metric_source_run_id=runtime_request.method_metric_source_run_id,
        runtime_artifacts_index=runtime_artifacts_index,
        selection_artifact=selection_artifact,
        selection_vector=selection_vector,
        selection_vector_ref=selection_vector_ref,
        strategic_output=strategic_output,
        selection_evaluation=selection_evaluation,
        selection_ref=selection_ref,
        benchmark_scope=benchmark_scope,
        benchmark_registry=benchmark_registry,
        method_metric_score_required=(
            runtime_request.method_metric_source_request_status != "absent"
        ),
        method_metric_source_request_status=(runtime_request.method_metric_source_request_status),
    )


def run_runtime_funnel(session: _RuntimeSession) -> None:
    """Build and advance the existing L0-L6 funnel without changing its stage order."""
    owner = session.owner
    ctx = session.ctx
    registry_root = _require_policy_runtime_registry_root(ctx.store)
    state = session.state
    candidate = session.candidate
    candidate_ref = session.candidate_ref
    calibration_report = session.calibration_report
    predictive_voi = session.predictive_voi
    stages = [
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
                runtime_backend=session.runtime_backend,
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
    ]
    search_uncertainty_owner_context = _build_search_uncertainty_owner_context(session, stages)

    def resolve_search_attempt_association(
        *, anchor_ref: ArtifactRef
    ) -> SearchOwnedAttemptAssociation | None:
        """Re-read the actual Runtime winner for one selected HTE anchor."""
        service = ctx.method_metric_selection_owner
        if service is None:
            return None
        resolve_association = getattr(service, "resolve_owned_attempt_anchor_association", None)
        if not callable(resolve_association):
            return None
        typed_anchor_ref = OwnedAttemptAnchorRef.model_validate(
            anchor_ref.model_dump(mode="json"), strict=True
        )
        association = resolve_association(anchor_ref=typed_anchor_ref)
        if not isinstance(association, OwnedAttemptAnchorAssociation):
            return None
        return association

    def resolve_search_historical_attempt_association(
        *,
        anchor_ref: ArtifactRef,
        expected_job_id: str,
        expected_completed_event_id: int,
        expected_tenant_id: str,
        expected_cell_id: str | None | _SearchOwnerCellScopeUnset = _OWNER_SCOPE_UNSET,
    ) -> SearchOwnedAttemptAssociation | None:
        """Resolve one exact durable Runtime completion for a Search projection row."""
        service = ctx.method_metric_selection_owner
        if service is None:
            return None
        resolve_association = getattr(
            service,
            "resolve_owned_attempt_anchor_association",
            None,
        )
        if not callable(resolve_association):
            return None
        typed_anchor_ref = OwnedAttemptAnchorRef.model_validate(
            anchor_ref.model_dump(mode="json"),
            strict=True,
        )
        selectors = {
            "anchor_ref": typed_anchor_ref,
            "expected_job_id": expected_job_id,
            "expected_completed_event_id": expected_completed_event_id,
            "expected_tenant_id": expected_tenant_id,
        }
        if expected_cell_id is _OWNER_SCOPE_UNSET:
            association = resolve_association(**selectors)
            if not isinstance(association, OwnedAttemptAnchorAssociation):
                return None
            return association
        if expected_cell_id is not None and not isinstance(expected_cell_id, str):
            return None
        association = resolve_association(
            **selectors,
            expected_cell_id=expected_cell_id,
        )
        if not isinstance(association, OwnedAttemptAnchorAssociation):
            return None
        return association

    historical_resolver: SearchOwnedHistoricalAttemptAssociationResolver = (
        resolve_search_historical_attempt_association
    )
    source_verifier: SearchHTESourceProjectionVerifier | None = None
    configured_source_verifier = getattr(
        ctx.method_metric_selection_owner, "verify_search_hte_source_projection_join", None
    )
    if callable(configured_source_verifier):
        source_verifier = cast("SearchHTESourceProjectionVerifier", configured_source_verifier)
    orchestrator = owner.FunnelOrchestrator(
        stages=stages,
        correlation_tracker=owner._resolve_runtime_correlation_tracker(calibration_report),
        lesson_registry=owner.LessonRegistry(
            root=registry_root / "search_registry" / "lessons",
            store=ctx.store,
        ),
        voi_scheduler=predictive_voi,
        search_uncertainty_attempt_association_resolver=resolve_search_attempt_association,
        search_uncertainty_historical_attempt_association_resolver=historical_resolver,
        search_uncertainty_source_projection_verifier=source_verifier,
    )
    ticket = orchestrator.submit(
        owner._candidate_search_payload(candidate, state),
        session.funnel_context,
        search_uncertainty_owner_context=search_uncertainty_owner_context,
    )
    session.outcome = orchestrator.advance(ticket, policy="full")
    owner.persist_predictive_voi_scheduler(
        ctx,
        transfer_context=session.transfer_context,
        scheduler=predictive_voi,
    )


def _exact_builtin_string(value: object) -> str | None:
    """Return a native JSON string, excluding subclasses with custom hooks."""
    return value if type(value) is str else None


def _persist_policy_runtime_work_packet(
    *,
    initial_state: Mapping[str, Any],
    fidelity: object,
    evaluation_attempt_id: str,
    runtime_artifact: PolicyRuntimeEvaluationArtifact,
    completed_projection_basis: object | None = None,
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
    run_id = _exact_builtin_string(identity.get("run_id"))
    ticket_id = _exact_builtin_string(identity.get("ticket_id"))
    candidate_hash = _exact_builtin_string(identity.get("candidate_hash"))
    attempt_id = _exact_builtin_string(evaluation_attempt_id)
    if run_id is None or not run_id.strip():
        return None, "run_ticket_or_candidate_identity_unavailable"
    if ticket_id is None or not ticket_id.strip():
        return None, "run_ticket_or_candidate_identity_unavailable"
    if candidate_hash is None or not candidate_hash.strip():
        return None, "run_ticket_or_candidate_identity_unavailable"
    if attempt_id is None or not attempt_id.strip():
        return None, "runtime_execution_binding_unavailable"
    fidelity_label = _exact_builtin_string(fidelity)
    if fidelity_label is None:
        return None, "unsupported_fidelity"
    if fidelity_label == "medium":
        selected_fidelity: Literal["medium", "full"] = "medium"
        stage_level = 3
        stage_name = "funnel_L3_medium"
    elif fidelity_label == "full":
        selected_fidelity = "full"
        stage_level = 4
        stage_name = "funnel_L4_full"
    else:
        return None, "unsupported_fidelity"

    simulation_results = runtime_artifact.simulation_results
    bootstrap = simulation_results.get("bootstrap")
    vector_metadata = runtime_artifact.evaluation_vector.metadata
    invocation = (
        vector_metadata.get("policy_runtime_invocation")
        if isinstance(vector_metadata, Mapping)
        else None
    )
    fiscal_measurement = (
        vector_metadata.get("policy_runtime_fiscal_measurement")
        if isinstance(vector_metadata, Mapping)
        else None
    )
    if not isinstance(bootstrap, Mapping) or not isinstance(invocation, Mapping):
        return None, "runtime_execution_binding_unavailable"
    bootstrap_attempt_id = _exact_builtin_string(bootstrap.get("evaluation_attempt_id"))
    invocation_attempt_id = _exact_builtin_string(invocation.get("evaluation_attempt_id"))
    requested_draw_source_raw = _exact_builtin_string(bootstrap.get("requested_draw_source"))
    invocation_draw_source_raw = _exact_builtin_string(invocation.get("requested_draw_source"))
    config_digest_raw = bootstrap.get("effective_estimation_config_sha256")
    invocation_config_digest_raw = invocation.get("effective_estimation_config_sha256")
    config_digest = _exact_builtin_string(config_digest_raw)
    invocation_config_digest = _exact_builtin_string(invocation_config_digest_raw)
    if (
        bootstrap_attempt_id is None
        or invocation_attempt_id is None
        or requested_draw_source_raw is None
        or invocation_draw_source_raw is None
        or (config_digest_raw is not None and config_digest is None)
        or (invocation_config_digest_raw is not None and invocation_config_digest is None)
    ):
        return None, "runtime_execution_binding_unavailable"
    requested_draw_count = bootstrap.get("requested_draw_count")
    if requested_draw_count is not None and (
        isinstance(requested_draw_count, bool) or not isinstance(requested_draw_count, int)
    ):
        return None, "runtime_execution_binding_unavailable"
    if requested_draw_source_raw == "effective_estimation_config":
        requested_draw_source: Literal["effective_estimation_config", "unavailable"] = (
            "effective_estimation_config"
        )
    elif requested_draw_source_raw == "unavailable":
        requested_draw_source = "unavailable"
    else:
        return None, "runtime_execution_binding_unavailable"
    invocation_requested_draw_count = invocation.get("requested_draw_count")
    if (
        bootstrap_attempt_id != attempt_id
        or invocation_attempt_id != attempt_id
        or invocation_requested_draw_count != requested_draw_count
        or invocation_draw_source_raw != requested_draw_source_raw
        or invocation_config_digest != config_digest
        or (
            requested_draw_source == "effective_estimation_config"
            and (
                not isinstance(config_digest, str)
                or len(config_digest) != 64
                or any(character not in "0123456789abcdef" for character in config_digest)
            )
        )
        or (
            requested_draw_source == "unavailable"
            and (requested_draw_count is not None or config_digest is not None)
        )
        or not isinstance(fiscal_measurement, Mapping)
    ):
        return None, "runtime_execution_binding_unavailable"
    fiscal_aliases = ("gov_balance", "government_balance", "budget_deficit", "deficit")
    expected_fiscal_measurement = {
        "usable": simulation_results.get("budget_deficit_objective_usable"),
        "normalized_value": simulation_results.get("budget_deficit_objective_value"),
        "source_values": {
            alias: simulation_results[alias]
            for alias in fiscal_aliases
            if alias in simulation_results
        },
    }
    if fiscal_measurement != expected_fiscal_measurement:
        return None, "runtime_execution_binding_unavailable"

    backend_kind = _exact_builtin_string(runtime_artifact.provenance.backend_kind)
    if backend_kind is None or not backend_kind.strip():
        return None, "runtime_execution_binding_unavailable"
    input_signature_raw = initial_state.get("pinned_input_signature")
    input_signature = _exact_builtin_string(input_signature_raw)
    if input_signature_raw is not None and input_signature is None:
        return None, "runtime_execution_binding_unavailable"

    result_ref = persist_policy_evaluation_vector_to_store(
        store,
        candidate_ref=candidate_ref,
        evaluation_vector=runtime_artifact.evaluation_vector,
        completed_projection_basis=completed_projection_basis,
        completed_projection_binding=runtime_artifact.completed_projection_binding,
    )
    packet = FunnelExecutedWorkPacket(
        run_id=run_id,
        ticket_id=ticket_id,
        candidate_hash=candidate_hash,
        candidate_ref=candidate_ref,
        stage_level=stage_level,
        stage_name=stage_name,
        fidelity=selected_fidelity,
        evaluation_attempt_id=attempt_id,
        observed_at=datetime.now(UTC),
        backend_kind=backend_kind,
        source_result_ref=result_ref,
        requested_draw_count=requested_draw_count,
        requested_draw_source=requested_draw_source,
        effective_estimation_config_sha256=config_digest,
        input_signature=input_signature or None,
    )
    return persist_funnel_executed_work_packet(store, packet), None
