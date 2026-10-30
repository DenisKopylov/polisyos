"""Policy-runtime artifact workflows and evidence-binding helper implementations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import (
    DiscoveryArtifactBundleRef,
    Metrics,
    PriorKnowledgeBundleRef,
)
from polisyos.foundry.methods import AmbiguityCertificate
from polisyos.ir import (
    CrossGraphEvidenceProfile,
    DistributionalReport,
    LatentDiscoveryBundle,
    load_cross_graph_evidence_profile,
    load_distributional_report,
    load_uncertainty_envelope,
)
from polisyos.ir.analytics import CausalEffectReport
from polisyos.ir.registry import (
    CrossGraphEvidenceProfileRef,
    DistributionalReportRef,
    UncertaintyEnvelopeRef,
)
from polisyos.scientist.governance.report import (
    GovernanceReport,
    load_governance_report_artifact,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
)
from polisyos.scientist.methods.discovery.output import (
    load_discovery_artifact_bundle,
    load_merged_latent_discovery_bundle,
)
from polisyos.scientist.methods.discovery.priors import (
    PriorKnowledgeBundle,
    load_prior_knowledge_bundle,
)
from polisyos.scientist.methods.doe.stress_report import Vulnerability
from polisyos.scientist.methods.search.funnel.types import (
    FunnelExecutedWorkPacket,
    FunnelOutcome,
)
from polisyos.scientist.methods.search.judge_stack import to_search_uncertainty_envelope
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreStatus,
    SourceMetricObservation,
    method_metric_observation_input_refs,
    recompute_source_government_balance,
    source_observation_input_refs,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_metrics import (
    _POLICY_RUNTIME_LOAD_ERRORS,
    _POLICY_RUNTIME_VALIDATION_ERRORS,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_METRICS_REF,
    INPUT_PRIOR_KNOWLEDGE_BUNDLE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema

if TYPE_CHECKING:
    from polisyos.pdc import (
        EvalSafetyVerifierPort,
        EvaluationExecutionContext,
        WorldModelRecord,
    )
    from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        LatentDiscoveryBundleResolution,
        PolicyEvaluationBackend,
        PolicyRuntimeEvaluationArtifact,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def _ensure_policy_candidate_ref_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef | None,
) -> ArtifactRef:
    """Persist a selected candidate only from a typed candidate or selected Trinity source."""
    from polisyos.ir import TrinityBundle
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    source_ref: ArtifactRef | None = None
    if candidate_ref is not None:
        if candidate_ref.kind in {
            PolicyCandidateSchema.ARTIFACT_KIND,
            "scientist.policy_candidate_schema",
        }:
            # Keep the caller's exact candidate ref. The score reader separately checks the
            # canonical schema/profile; legacy refs remain readable candidate-only data.
            return candidate_ref
        if candidate_ref.kind != TrinityBundle.ARTIFACT_KIND:
            # Never relabel an arbitrary source body as a canonical candidate.
            return candidate_ref
        if candidate_ref.manifest_profile_sha256 is None:
            return candidate_ref
        from polisyos.core.artifacts import (
            artifact_manifest_profile_sha256,
            load_core_json_artifact,
        )

        manifest = ctx.store.get_manifest(candidate_ref)
        if (
            manifest.artifact_id != candidate_ref.artifact_id
            or manifest.kind != TrinityBundle.ARTIFACT_KIND
            or candidate_ref.kind != manifest.kind
            or manifest.media_type != TrinityBundle.ARTIFACT_MEDIA_TYPE
            or candidate_ref.media_type != manifest.media_type
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != TrinityBundle.ARTIFACT_SCHEMA_NAME
            or manifest.artifact_schema.version != TrinityBundle.ARTIFACT_SCHEMA_VERSION
            or artifact_manifest_profile_sha256(manifest) != candidate_ref.manifest_profile_sha256
        ):
            raise ValueError("candidate_source_manifest_contract_mismatch")
        source_bundle = TrinityBundle.model_validate(
            load_core_json_artifact(
                ctx.store,
                candidate_ref,
                manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
            )
        )
        if candidate.trinity_bundle != source_bundle:
            raise ValueError("candidate_source_body_mismatch")
        source_ref = candidate_ref

    inputs = [input_ref_from_artifact_ref(ref, role=key) for key, ref in state.inputs.items()]
    if source_ref is not None:
        inputs.append(input_ref_from_artifact_ref(source_ref, role="candidate_source"))
    return persist_policy_candidate_schema(
        ctx.store,
        candidate,
        inputs=inputs,
        return_selected_profile=True,
    )


def _persist_policy_evaluation_vector_impl(
    ctx: ExecutionContext,
    *,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    completed_projection_basis: object | None = None,
    completed_projection_binding: object | None = None,
) -> ArtifactRef:
    """Persist policy evaluation vector helper."""
    return _persist_policy_evaluation_vector_to_store_impl(
        ctx.store,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation_vector,
        completed_projection_basis=completed_projection_basis,
        completed_projection_binding=completed_projection_binding,
    )


def _persist_policy_evaluation_vector_to_store_impl(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    completed_projection_basis: object | None = None,
    completed_projection_binding: object | None = None,
) -> ArtifactRef:
    """Persist a native policy-runtime evaluation vector to the supplied CAS."""
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        completed_projection_input_refs,
    )

    inputs = [input_ref_from_artifact_ref(candidate_ref, role="candidate")]
    inputs.extend(
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in completed_projection_input_refs(
            evaluation_vector,
            candidate_ref=candidate_ref,
            basis=completed_projection_basis,
            store=store,
            evaluation_binding=completed_projection_binding,
        )
    )
    raw_observation = evaluation_vector.metadata.get("policy_runtime_source_measurement")
    if raw_observation is not None:
        observation = SourceMetricObservation.model_validate(raw_observation)
        if observation.source_status == "observed":
            recomputed = recompute_source_government_balance(store, observation)
            if recomputed.model_dump(mode="json", exclude_none=False) != observation.model_dump(
                mode="json", exclude_none=False
            ):
                raise ValueError("policy_runtime_source_measurement_not_recomputed")
        inputs.extend(
            input_ref_from_artifact_ref(ref, role=role)
            for role, ref in source_observation_input_refs(observation)
        )
    if evaluation_vector.method_metric_observations:
        inputs.extend(
            input_ref_from_artifact_ref(ref, role=role)
            for role, ref in method_metric_observation_input_refs(
                evaluation_vector.method_metric_observations
            )
        )
    return store.put_json(
        evaluation_vector,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                version=("1.3" if evaluation_vector.method_metric_observations else "1.2"),
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )


def _persist_funnel_executed_work_packet_impl(
    store: ArtifactStore,
    packet: FunnelExecutedWorkPacket,
) -> ArtifactRef:
    """Persist a completed policy-runtime invocation record with CAS lineage."""
    return store.put_json(
        packet,
        PutOptions(
            kind="scientist.search.funnel_native_work_packet",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.FunnelExecutedWorkPacket",
                version=packet.schema_version,
            ),
            producer=ProducerInfo(
                component="scientist.policy_runtime_work_packet",
                version="1.0.0",
            ),
            inputs=[
                input_ref_from_artifact_ref(packet.candidate_ref, role="candidate"),
                input_ref_from_artifact_ref(packet.source_result_ref, role="source_result"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _build_selection_benchmark_evaluation_impl(
    *,
    state: ExperimentState,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    runtime_artifact: PolicyRuntimeEvaluationArtifact | None = None,
    source: str = "policy_runtime_selection",
    metadata_extension: Mapping[str, Any] | None = None,
    selection_score_fn: Callable[[PolicyEvaluationVector], float],
) -> BenchmarkEvaluation:
    """Build a source-qualified selection view without promoting unscored vectors."""
    _, score_status = evaluation_vector.legacy_scalar_proxy_for_search()
    assessment = evaluation_vector.score_assessment
    limitation = assessment.limitation if assessment is not None else None
    if score_status is ObjectiveScoreStatus.AVAILABLE:
        base_score = selection_score_fn(evaluation_vector)
        selection_metrics = {
            "score": base_score,
            **{
                name: channel.higher_is_better
                for name, channel in evaluation_vector.primary.items()
            },
        }
        holdout_metrics = {"score": base_score}
        sample_counts = {BenchmarkSplit.SELECTION.value: 100}
        promotable = evaluation_vector.feasible
        status = "ok"
        notes: list[str] = []
    else:
        limitation = limitation or "policy_vector_score_assessment_missing"
        selection_metrics = {}
        holdout_metrics = {}
        sample_counts = {}
        promotable = False
        status = score_status.value
        notes = [limitation]

    return BenchmarkEvaluation(
        loop_id=str(state.params.get("policy_loop_id") or state.run_id),
        suite_id="policy_selection",
        candidate_ref=candidate_ref,
        selection_metrics=selection_metrics,
        holdout_metrics=holdout_metrics,
        sample_counts=sample_counts,
        promotable=promotable,
        status=status,
        notes=notes,
        runtime_split_type=BenchmarkSplit.SELECTION,
        metadata={
            **dict(metadata_extension or {}),
            "lineage_complete": True,
            "generated_from": source,
            "backend_kind": (
                runtime_artifact.provenance.backend_kind
                if runtime_artifact is not None
                else "unknown"
            ),
            "promotable_source": (
                runtime_artifact.provenance.promotable_source
                if runtime_artifact is not None
                else None
            ),
            "evaluation_degradation_mode": (
                runtime_artifact.provenance.degradation_mode
                if runtime_artifact is not None
                else None
            ),
            "objective_score_status": score_status.value,
            "objective_score_limitation": limitation,
        },
    )


def _build_policy_runtime_evaluation_impl(
    candidate: PolicyCandidateSchema,
    *,
    backend: PolicyEvaluationBackend,
    fidelity: str,
    simulation_metrics: dict[str, float] | None,
    uncertainty: UncertaintyEnvelope | None,
    distributional_report: DistributionalReport | None,
    causal_effect_report: CausalEffectReport | None,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    governance_report: GovernanceReport | None,
    ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
) -> PolicyRuntimeEvaluationArtifact:
    """Build policy runtime evaluation."""
    return backend.evaluate(
        candidate,
        fidelity=fidelity,
        simulation_metrics=simulation_metrics,
        uncertainty=uncertainty,
        governance_report=governance_report,
        distributional_report=distributional_report,
        causal_effect_report=causal_effect_report,
        cross_graph_profile=cross_graph_profile,
        ambiguity_certificate=ambiguity_certificate,
    )


def _build_vulnerabilities_impl(
    *,
    evaluation: PolicyEvaluationVector | None,
    distributional: DistributionalReport | None,
    causal_report: CausalEffectReport | None,
    governance_report: GovernanceReport | None,
) -> list[Vulnerability]:
    """Reuse the existing Level-5 vulnerability projection and its typed taxonomy."""
    from polisyos.scientist.nodes.builtins.decide.run_policy_funnel_level5 import (
        _build_vulnerabilities,
    )

    return _build_vulnerabilities(
        evaluation=evaluation,
        distributional=distributional,
        causal_report=causal_report,
        governance_report=governance_report,
    )


def _load_simulation_metrics_impl(
    ctx: ExecutionContext, state: ExperimentState
) -> dict[str, float]:
    """Load simulation metrics."""
    from polisyos.core.artifacts import load_core_json_artifact

    metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
    if metrics_ref is None:
        return {}
    payload = load_core_json_artifact(ctx.store, metrics_ref)
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


def _load_distributional_report_for_state_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> DistributionalReport | None:
    """Load distributional report for state."""
    ref = state.artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)
    return (
        None
        if ref is None
        else load_distributional_report(
            _ensure_ir_artifact_store(ctx.store),
            DistributionalReportRef.model_validate(ref.model_dump(mode="json")),
        )
    )


def _load_causal_report_impl(
    ctx: ExecutionContext, state: ExperimentState
) -> CausalEffectReport | None:
    """Load causal report."""
    from polisyos.core.artifacts import load_core_json_artifact

    ref = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    if ref is None:
        return None
    return CausalEffectReport.model_validate(load_core_json_artifact(ctx.store, ref))


def _load_governance_report_impl(
    ctx: ExecutionContext, state: ExperimentState
) -> GovernanceReport | None:
    """Load governance report."""
    from polisyos.scientist.governance.report_currentness import (
        load_current_governance_report,
    )

    return load_current_governance_report(ctx, state)


def _load_cross_graph_profile_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> CrossGraphEvidenceProfile | None:
    """Load cross graph profile."""
    ref = state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
    return (
        None
        if ref is None
        else load_cross_graph_evidence_profile(
            _ensure_ir_artifact_store(ctx.store),
            CrossGraphEvidenceProfileRef.model_validate(ref.model_dump(mode="json")),
        )
    )


def _load_prior_knowledge_bundle_for_state_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> PriorKnowledgeBundle | None:
    """Load prior knowledge bundle for state."""
    raw_ref = state.inputs.get(INPUT_PRIOR_KNOWLEDGE_BUNDLE_REF) or state.params.get(
        "prior_knowledge_bundle_ref"
    )
    if raw_ref is not None:
        try:
            ref = (
                raw_ref
                if isinstance(raw_ref, PriorKnowledgeBundleRef)
                else PriorKnowledgeBundleRef.model_validate(
                    raw_ref.model_dump(mode="json") if hasattr(raw_ref, "model_dump") else raw_ref
                )
            )
            return load_prior_knowledge_bundle(ctx.store, ref)
        except _POLICY_RUNTIME_LOAD_ERRORS:
            return None

    bundle_ref = state.artifacts_index.get(
        ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF
    ) or state.params.get("discovery_artifact_bundle_ref")
    if bundle_ref is None:
        return None
    try:
        discovery_ref = (
            bundle_ref
            if isinstance(bundle_ref, DiscoveryArtifactBundleRef)
            else DiscoveryArtifactBundleRef.model_validate(
                bundle_ref.model_dump(mode="json")
                if hasattr(bundle_ref, "model_dump")
                else bundle_ref
            )
        )
        bundle = load_discovery_artifact_bundle(ctx.store, discovery_ref)
        return load_prior_knowledge_bundle(ctx.store, bundle.prior_knowledge_bundle_ref)
    except _POLICY_RUNTIME_LOAD_ERRORS:
        return None


def _load_search_uncertainty_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> UncertaintyEnvelope:
    """Load search uncertainty."""
    ref = state.artifacts_index.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    if ref is None:
        return to_search_uncertainty_envelope(None)
    return to_search_uncertainty_envelope(
        load_uncertainty_envelope(
            _ensure_ir_artifact_store(ctx.store),
            UncertaintyEnvelopeRef.model_validate(ref.model_dump(mode="json")),
        )
    )


def _resolve_funnel_outcome_impl(state: ExperimentState) -> FunnelOutcome | None:
    """Resolve funnel outcome."""
    for key in ("funnel_outcome", "_funnel_outcome"):
        value = state.params.get(key)
        if isinstance(value, FunnelOutcome):
            return value
    return None


def _maybe_artifact_ref_impl(value: Any) -> ArtifactRef | None:
    """Maybe artifact ref helper."""
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict):
        try:
            return ArtifactRef.model_validate(value)
        except _POLICY_RUNTIME_VALIDATION_ERRORS:
            return None
    return None


def _load_benchmark_evaluation_impl(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> BenchmarkEvaluation:
    """Load benchmark evaluation."""
    from polisyos.core.artifacts import load_core_json_artifact

    return BenchmarkEvaluation.model_validate(load_core_json_artifact(ctx.store, ref))


def _load_governance_report_from_ref_impl(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> GovernanceReport:
    """Load governance bytes from a ref as candidate evidence only.

    Decision and promotion consumers must use the state-bound currentness resolver.
    """
    return load_governance_report_artifact(ctx.store, ref)


def _merge_proxy_boundary_into_latent_bundle_impl(
    bundle: LatentDiscoveryBundle | None,
    proxy_boundary_payload: dict[str, Any] | None,
) -> LatentDiscoveryBundle | None:
    if bundle is None or not isinstance(proxy_boundary_payload, dict):
        return bundle

    existing_payload = bundle.metadata.get("proxy_boundary")
    merged_notes: list[str] = []
    merged_reasons: list[str] = []
    merged_payload: dict[str, Any] = {}
    for payload in (
        existing_payload if isinstance(existing_payload, dict) else {},
        proxy_boundary_payload,
    ):
        for note in list(payload.get("boundary_notes", []) or []):
            note_text = str(note).strip()
            if note_text and note_text not in merged_notes:
                merged_notes.append(note_text)
        for reason in list(payload.get("no_promotion_reasons", []) or []):
            reason_text = str(reason).strip()
            if reason_text and reason_text not in merged_reasons:
                merged_reasons.append(reason_text)
        for key, value in payload.items():
            if key in {"boundary_notes", "no_promotion_reasons"}:
                continue
            merged_payload.setdefault(str(key), value)

    if merged_notes:
        merged_payload["boundary_notes"] = merged_notes
    if merged_reasons:
        merged_payload["no_promotion_reasons"] = merged_reasons

    return bundle.model_copy(
        update={
            "metadata": {
                **dict(bundle.metadata),
                "proxy_boundary": merged_payload,
            },
            "no_promotion_reasons": list(
                dict.fromkeys([*bundle.no_promotion_reasons, *merged_reasons])
            ),
        }
    )


def _load_ambiguity_certificate_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    parse_certificate: Callable[[Any], AmbiguityCertificate | None],
    artifact_ref_parser: Callable[[Any], ArtifactRef | None],
) -> AmbiguityCertificate | None:
    """Load the first valid ambiguity certificate from runtime params or artifacts."""
    from polisyos.core.artifacts import load_core_json_artifact

    for key in ("ambiguity_certificate", "moment_dro_certificate"):
        certificate = parse_certificate(state.params.get(key))
        if certificate is not None:
            return certificate

    for container_key in (
        "optimization_result",
        "moment_dro_result",
        "result",
        "simulation_results",
    ):
        container = state.params.get(container_key)
        if isinstance(container, Mapping):
            certificate = parse_certificate(container.get("ambiguity_certificate"))
            if certificate is not None:
                return certificate

    for ref_key in ("ambiguity_certificate_ref", "moment_dro_certificate_ref"):
        ref = artifact_ref_parser(state.params.get(ref_key))
        if ref is None:
            continue
        try:
            payload = load_core_json_artifact(ctx.store, ref)
        except _POLICY_RUNTIME_LOAD_ERRORS:
            continue
        certificate = parse_certificate(payload)
        if certificate is not None:
            return certificate
    return None


def _resolve_policy_evaluation_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
    *,
    parse_evaluation: Callable[[Any], PolicyEvaluationVector | None],
    load_metrics: Callable[[ExecutionContext, ExperimentState], dict[str, float]],
    objective_stack_factory: Callable[[], Any],
    bundle_factory: Callable[..., Any],
    load_distributional: Callable[[ExecutionContext, ExperimentState], Any],
    load_causal: Callable[[ExecutionContext, ExperimentState], Any],
    load_cross_graph: Callable[[ExecutionContext, ExperimentState], Any],
    load_governance: Callable[[ExecutionContext, ExperimentState], Any],
    load_uncertainty: Callable[[ExecutionContext, ExperimentState], Any],
    load_ambiguity: Callable[[ExecutionContext, ExperimentState], Any],
    persist_vector: Callable[..., ArtifactRef],
) -> tuple[PolicyEvaluationVector | None, ArtifactRef | None]:
    """Resolve, compute if needed, and persist an evaluation through injected support seams."""
    parsed = parse_evaluation(state.params.get("policy_evaluation"))
    if parsed is None:
        metrics = load_metrics(ctx, state)
        if not metrics:
            return None, None
        parsed = objective_stack_factory().evaluate(
            bundle_factory(
                candidate=candidate,
                simulation_metrics=metrics,
                distributional_report=load_distributional(ctx, state),
                causal_effect_report=load_causal(ctx, state),
                cross_graph_profile=load_cross_graph(ctx, state),
                governance_report=load_governance(ctx, state),
                uncertainty_envelope=load_uncertainty(ctx, state),
                ambiguity_certificate=load_ambiguity(ctx, state),
            )
        )
    ref = persist_vector(ctx, candidate_ref=candidate_ref, evaluation_vector=parsed)
    return parsed, ref


def _resolve_latent_discovery_bundle_for_state_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    resolution_factory: Callable[..., LatentDiscoveryBundleResolution],
) -> LatentDiscoveryBundleResolution:
    """Resolve a discovery artifact's merged latent bundle through its canonical loader."""
    bundle_ref = state.artifacts_index.get(
        ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF
    ) or state.params.get("discovery_artifact_bundle_ref")
    if bundle_ref is None:
        return resolution_factory(bundle=None, status="missing")
    discovery_ref: DiscoveryArtifactBundleRef | None = None
    try:
        discovery_ref = (
            bundle_ref
            if isinstance(bundle_ref, DiscoveryArtifactBundleRef)
            else DiscoveryArtifactBundleRef.model_validate(
                bundle_ref.model_dump(mode="json")
                if hasattr(bundle_ref, "model_dump")
                else bundle_ref
            )
        )
        bundle = load_discovery_artifact_bundle(ctx.store, discovery_ref)
        latent_bundle = load_merged_latent_discovery_bundle(ctx.store, bundle)
        return resolution_factory(
            bundle=latent_bundle,
            status="ok" if latent_bundle is not None else "missing",
            source_bundle_ref=discovery_ref,
        )
    except _POLICY_RUNTIME_LOAD_ERRORS as exc:
        return resolution_factory(
            bundle=None,
            status="unreadable",
            source_bundle_ref=discovery_ref,
            error_code=type(exc).__name__,
            error_message=str(exc),
        )


def _resolve_effective_latent_discovery_bundle_for_state_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    causal_report: CausalEffectReport | None,
    resolve_base: Callable[[ExecutionContext, ExperimentState], LatentDiscoveryBundleResolution],
    merge_proxy: Callable[
        [LatentDiscoveryBundle | None, dict[str, Any] | None],
        LatentDiscoveryBundle | None,
    ],
    resolution_factory: Callable[..., LatentDiscoveryBundleResolution],
) -> LatentDiscoveryBundleResolution:
    """Resolve the latent bundle after composing its causal proxy-boundary evidence."""
    resolution = resolve_base(ctx, state)
    if resolution.status != "ok" or resolution.bundle is None:
        return resolution
    return resolution_factory(
        bundle=merge_proxy(
            resolution.bundle,
            _proxy_boundary_payload_from_causal_report_impl(causal_report),
        ),
        status=resolution.status,
        source_bundle_ref=resolution.source_bundle_ref,
        error_code=resolution.error_code,
        error_message=resolution.error_message,
    )


def _load_latent_discovery_bundle_for_state_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    resolve_base: Callable[[ExecutionContext, ExperimentState], LatentDiscoveryBundleResolution],
) -> LatentDiscoveryBundle | None:
    """Load the bundle from a caller-resolved typed result."""
    return resolve_base(ctx, state).bundle


def _load_effective_latent_discovery_bundle_for_state_impl(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    causal_report: CausalEffectReport | None,
    resolve_effective: Callable[..., LatentDiscoveryBundleResolution],
) -> LatentDiscoveryBundle | None:
    """Load the effective bundle from its caller-resolved typed result."""
    return resolve_effective(ctx, state, causal_report=causal_report).bundle


def _proxy_boundary_payload_from_causal_report_impl(
    report: CausalEffectReport | None,
) -> dict[str, Any] | None:
    """Read a proxy-boundary payload when the causal report supplies one."""
    if report is None:
        return None
    payload = report.metadata.get("proxy_boundary")
    if not isinstance(payload, dict):
        return None
    return dict(payload)


def _production_policy_evaluation_safety_blockers_impl(
    *,
    context: EvaluationExecutionContext | None,
    verifier: EvalSafetyVerifierPort | None,
    world_model_record: WorldModelRecord | None,
    candidate: PolicyCandidateSchema,
    simulation_metrics: dict[str, float] | None,
    uncertainty: UncertaintyEnvelope | None,
    distributional_report: DistributionalReport | None,
    causal_effect_report: CausalEffectReport | None,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    governance_report: GovernanceReport | None,
    ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None,
    blocker_fn: Callable[[str], str],
    input_hash_fn: Callable[[object], str],
    production_owner_component_id: Any,
    world_model_record_content_hash_fn: Callable[[Any], str],
    challenge_factory: Any,
    admission_check: Callable[..., bool],
) -> tuple[str, ...]:
    if context is None:
        return (blocker_fn("execution_context_missing"),)

    mode_resolution = context.mode_resolution
    if mode_resolution.status != "accepted":
        return (mode_resolution.blocker_code or blocker_fn("evaluation_mode_unknown"),)
    if context.evaluator_owner_id != production_owner_component_id:
        return (blocker_fn("evaluator_owner_mismatch"),)
    if world_model_record is None:
        return (blocker_fn("world_model_record_not_established"),)

    recomputed_wmr_hash = world_model_record_content_hash_fn(world_model_record)
    world_model_binds = bool(
        world_model_record.content_hash == recomputed_wmr_hash
        and context.world_model_record_ref.content_hash == recomputed_wmr_hash
        and context.world_model_record_ref.artifact_id == world_model_record.world_model_record_id
        and context.world_model_record_ref.artifact_type == "world_model_record"
        and context.world_model_record_ref.schema_ref == "policyos.runtime.world_model_record.v1"
    )
    if not world_model_binds:
        return (blocker_fn("world_model_record_binding_mismatch"),)

    actual_values = (
        candidate,
        simulation_metrics,
        uncertainty,
        distributional_report,
        causal_effect_report,
        cross_graph_profile,
        governance_report,
        ambiguity_certificate,
    )
    actual_hashes = tuple(input_hash_fn(value) for value in actual_values if value is not None)
    context_hashes = tuple(ref.content_hash for ref in context.evaluation_input_refs)
    context_identities = tuple(
        (ref.artifact_id, ref.content_hash) for ref in context.evaluation_input_refs
    )
    provenance_identities = tuple(
        (row.input_ref.artifact_id, row.input_ref.content_hash)
        for row in context.evaluation_input_provenance
    )
    exact_inputs_bind = bool(
        actual_hashes
        and len(actual_hashes) == len(set(actual_hashes))
        and len(context_identities) == len(set(context_identities))
        and len(provenance_identities) == len(set(provenance_identities))
        and set(actual_hashes) == set(context_hashes)
        and set(context_identities) == set(provenance_identities)
        and all(
            row.predicate_provenance in {"recomputed", "independently_reconciled"}
            for row in context.evaluation_input_provenance
        )
    )
    exact_owner_inputs_bind = bool(
        context.candidate_ref.artifact_id == candidate.candidate_id
        and context.candidate_ref.artifact_type == "candidate"
        and context.candidate_ref.content_hash == input_hash_fn(candidate)
        and context.target_population_scope_ref.artifact_type == "target_population_scope"
        and context.target_population_scope_ref.content_hash
        == input_hash_fn(candidate.target_population)
        and context.rule_version.strip()
        and context.intended_start_at.tzinfo is not None
    )
    if (
        not exact_inputs_bind
        or not exact_owner_inputs_bind
        or context.attempt_class != "non_simulation"
    ):
        return (blocker_fn("execution_context_binding_mismatch"),)
    if context.evaluation_mode == "simulate_only":
        return (blocker_fn("simulation_provenance_not_established"),)
    if verifier is None:
        return (blocker_fn("verifier_unresolved"),)

    challenge = challenge_factory.fresh(consumer_component_id=production_owner_component_id)
    receipt = verifier.require_admission(context, challenge)
    if not admission_check(receipt, context, challenge):
        return receipt.blocker_codes or (blocker_fn("consumer_admission_blocked"),)
    return ()
