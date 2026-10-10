"""Policy-runtime artifact workflows and evidence-binding helper implementations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.contracts.scientist import DiscoveryArtifactBundleRef, PriorKnowledgeBundleRef
from polisyos.foundry.methods.catalog.optimization.protocols import AmbiguityCertificate
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.causal_discovery import LatentDiscoveryBundle
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    load_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.distributional import DistributionalReport, load_distributional_report
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.methods.discovery.output import (
    load_discovery_artifact_bundle,
    load_merged_latent_discovery_bundle,
)
from polisyos.scientist.methods.discovery.priors import (
    PriorKnowledgeBundle,
    load_prior_knowledge_bundle,
)
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.methods.search.judge_stack import to_search_uncertainty_envelope
from polisyos.scientist.nodes.builtins.decide.policy_runtime_metrics import (
    _POLICY_RUNTIME_LOAD_ERRORS,
    _POLICY_RUNTIME_VALIDATION_ERRORS,
    _parse_ambiguity_certificate,
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
from polisyos.scientist.replay.verification import ReplayRegistry

if TYPE_CHECKING:
    from polisyos.pdc import EvalSafetyVerifierPort, EvaluationExecutionContext, WorldModelRecord
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
    """Ensure policy candidate ref helper."""
    if candidate_ref is not None and candidate_ref.kind == "scientist.policy_candidate_schema":
        return candidate_ref
    return persist_policy_candidate_schema(
        ctx.store,
        candidate,
        inputs=[
            InputRef(artifact_id=ref.artifact_id, role=key) for key, ref in state.inputs.items()
        ],
    )


def _persist_policy_evaluation_vector_impl(
    ctx: ExecutionContext,
    *,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
) -> ArtifactRef:
    """Persist policy evaluation vector helper."""
    return _persist_policy_evaluation_vector_to_store_impl(
        ctx.store,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation_vector,
    )


def _persist_policy_evaluation_vector_to_store_impl(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
) -> ArtifactRef:
    """Persist a native policy-runtime evaluation vector to the supplied CAS."""
    return store.put_json(
        evaluation_vector,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                version="1.0",
            ),
            inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
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
                InputRef(artifact_id=packet.candidate_ref.artifact_id, role="candidate"),
                InputRef(artifact_id=packet.source_result_ref.artifact_id, role="source_result"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
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
    """Build selection benchmark evaluation."""
    base_score = selection_score_fn(evaluation_vector)
    return BenchmarkEvaluation(
        loop_id=str(state.params.get("policy_loop_id") or state.run_id),
        suite_id="policy_selection",
        candidate_ref=candidate_ref,
        selection_metrics={
            "score": base_score,
            **{
                name: channel.higher_is_better
                for name, channel in evaluation_vector.primary.items()
            },
        },
        holdout_metrics={"score": base_score},
        sample_counts={BenchmarkSplit.SELECTION.value: 100},
        promotable=evaluation_vector.feasible,
        runtime_split_type=BenchmarkSplit.SELECTION,
        metadata={
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
            **dict(metadata_extension or {}),
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
    distributional,
    causal_report: CausalEffectReport | None,
    governance_report: GovernanceReport | None,
) -> list[Any]:
    """Build vulnerabilities."""
    from polisyos.scientist.methods.doe.stress_report import Vulnerability, VulnerabilityType

    vulnerabilities: list[Vulnerability] = []
    if evaluation is not None:
        for name, channel in evaluation.hard_constraints.items():
            if channel.status is None or str(channel.status) not in {"violated", "near_binding"}:
                continue
            vulnerabilities.append(
                Vulnerability(
                    vulnerability_id=f"constraint_{name}",
                    vulnerability_type=VulnerabilityType.CONSTRAINT_VIOLATION,
                    severity="critical" if str(channel.status) == "violated" else "high",
                    objective_value=channel.value,
                    constraint_violated=name,
                    explanation=f"Policy constraint '{name}' is {channel.status}.",
                    source_evidence=["policy_evaluation"],
                )
            )
    if governance_report is not None:
        issues = getattr(governance_report, "issues", None) or []
        for idx, issue in enumerate(issues, start=1):
            vulnerabilities.append(
                Vulnerability(
                    vulnerability_id=f"governance_{idx}",
                    vulnerability_type=VulnerabilityType.GOVERNANCE_RISK,
                    severity="high",
                    objective_value=1.0,
                    explanation=str(getattr(issue, "summary", None) or issue),
                    source_evidence=["governance_report"],
                )
            )
    if distributional is not None:
        subgroup_count = len(getattr(distributional, "subgroup_reports", None) or [])
        if subgroup_count:
            vulnerabilities.append(
                Vulnerability(
                    vulnerability_id="distributional_shift",
                    vulnerability_type=VulnerabilityType.SUBGROUP_HARM,
                    severity="medium",
                    objective_value=float(subgroup_count),
                    explanation="Distributional analysis identified subgroup-level shifts that require review.",
                    source_evidence=["distributional_report"],
                )
            )
    if causal_report is not None and getattr(causal_report, "confidence", None) is not None:
        confidence = float(causal_report.confidence)
        if confidence < 0.5:
            vulnerabilities.append(
                Vulnerability(
                    vulnerability_id="causal_confidence_low",
                    vulnerability_type=VulnerabilityType.MODEL_RISK,
                    severity="high",
                    objective_value=confidence,
                    explanation="Causal report confidence is below promotion-grade tolerance.",
                    source_evidence=["causal_report"],
                )
            )
    return vulnerabilities


def _load_simulation_metrics_impl(
    ctx: ExecutionContext, state: ExperimentState
) -> dict[str, float]:
    """Load simulation metrics."""
    metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
    if metrics_ref is None:
        return {}
    payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref))
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


def _load_distributional_report_for_state_impl(ctx: ExecutionContext, state: ExperimentState):
    """Load distributional report for state."""
    ref = state.artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)
    return (
        None
        if ref is None
        else load_distributional_report(_ensure_ir_artifact_store(ctx.store), ref)
    )


def _load_causal_report_impl(
    ctx: ExecutionContext, state: ExperimentState
) -> CausalEffectReport | None:
    """Load causal report."""
    ref = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    if ref is None:
        return None
    return CausalEffectReport.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))


def _load_governance_report_impl(
    ctx: ExecutionContext, state: ExperimentState
) -> GovernanceReport | None:
    """Load governance report."""
    ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
    if ref is None:
        return None
    return GovernanceReport.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))


def _load_cross_graph_profile_impl(ctx: ExecutionContext, state: ExperimentState):
    """Load cross graph profile."""
    ref = state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
    return (
        None
        if ref is None
        else load_cross_graph_evidence_profile(_ensure_ir_artifact_store(ctx.store), ref)
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


def _load_search_uncertainty_impl(ctx: ExecutionContext, state: ExperimentState):
    """Load search uncertainty."""
    ref = state.artifacts_index.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    if ref is None:
        return to_search_uncertainty_envelope(None)
    return to_search_uncertainty_envelope(
        load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), ref)
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
    return BenchmarkEvaluation.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))


def _load_governance_report_from_ref_impl(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> GovernanceReport:
    """Load governance report from ref."""
    return GovernanceReport.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))


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
            payload = from_canonical_bytes(ctx.store.get_bytes(ref))
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
        [LatentDiscoveryBundle | None, dict[str, Any] | None], LatentDiscoveryBundle | None
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
