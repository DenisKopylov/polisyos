"""Public decide policy runtime support module API."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import ValidationError

from polisyos.core import components as core_components
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.contracts.scientist import DiscoveryArtifactBundleRef, PriorKnowledgeBundleRef
from polisyos.foundry.methods.catalog.optimization.protocols import AmbiguityCertificate
from polisyos.foundry.validation import normalize_phase2_artifact_family
from polisyos.ir.analytics.causal import CausalEffectReport, load_data_readiness_report
from polisyos.ir.analytics.causal_discovery import LatentDiscoveryBundle
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    TransportStatus,
    load_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.distributional import DistributionalReport, load_distributional_report
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.pdc import (
    EvalSafetyAdmissionChallenge,
    EvalSafetyVerifierPort,
    EvaluationExecutionContext,
    WorldModelRecord,
    evaluation_safety_consumer_admission_is_verified,
    gy_content_hash,
    world_model_record_content_hash,
)
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    MetricDirection,
    PromotionPolicy,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.discovery.output import (
    load_discovery_artifact_bundle,
    load_merged_latent_discovery_bundle,
)
from polisyos.scientist.methods.discovery.priors import (
    PriorKnowledgeBundle,
    load_prior_knowledge_bundle,
)
from polisyos.scientist.methods.search.adversarial import load_platform_meta_evaluation_report
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.methods.search.judge_stack import (
    PolicyPromotionCoordinator,
    PolicyPromotionResult,
    to_search_uncertainty_envelope,
)
from polisyos.scientist.methods.search.promotion_evidence import PromotionEvidenceBundle
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope, UncertaintyType
from polisyos.scientist.nodes.builtins.decide import (
    policy_runtime_artifacts as _runtime_artifacts,
)
from polisyos.scientist.nodes.builtins.decide import (
    policy_runtime_metrics as _runtime_metrics,
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
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import (
    ObjectiveStack,
    PolicyEvaluationBundle,
    PolicyEvaluationVector,
    _normalize_policy_evaluation_vector,
)
from polisyos.scientist.policy_design.phase3 import resolve_phase3_gate
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)
from polisyos.scientist.replay.verification import (
    ReplayRegistry,
    load_replay_verification_report,
    verify_and_persist_replay_bundle,
)

_POLICY_RUNTIME_VALIDATION_ERRORS = _runtime_metrics._POLICY_RUNTIME_VALIDATION_ERRORS
_POLICY_RUNTIME_LOAD_ERRORS = _runtime_metrics._POLICY_RUNTIME_LOAD_ERRORS
_EVAL_SAFETY_BLOCKER_PREFIX = "polisyos.eval_safety"


def _eval_safety_blocker(name: str) -> str:
    return f"{_EVAL_SAFETY_BLOCKER_PREFIX}.{name}@1.0.0"


PRODUCTION_POLICY_EVALUATION_BACKEND_ID = core_components.ComponentId.parse(
    "scientist.production_policy_evaluation_backend@1.0.0"
)


class PolicyRuntimeEvaluationSafetyError(RuntimeError):
    """Raised when direct production evaluation lacks exact safety admission."""

    def __init__(self, blocker_codes: tuple[str, ...]) -> None:
        self.blocker_codes = blocker_codes
        super().__init__(
            "Attempted-evaluation safety admission blocked policy runtime evaluation: "
            + ", ".join(blocker_codes)
        )


@dataclass(frozen=True)
class PolicyRuntimeProvenance:
    """Policy runtime provenance public type."""

    backend_kind: str
    fidelity_mode: str
    promotable_source: bool
    degradation_mode: str | None = None
    source_components: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyRuntimeEvaluationArtifact:
    """Policy runtime evaluation artifact public type."""

    simulation_metrics: dict[str, float]
    simulation_results: dict[str, Any]
    evaluation_vector: PolicyEvaluationVector
    fidelity: str
    provenance: PolicyRuntimeProvenance


@dataclass(frozen=True)
class LatentDiscoveryBundleResolution:
    """Latent discovery bundle resolution public type."""

    bundle: LatentDiscoveryBundle | None
    status: Literal["ok", "missing", "unreadable"] = "missing"
    source_bundle_ref: DiscoveryArtifactBundleRef | None = None
    error_code: str | None = None
    error_message: str | None = None

    def error_payload(self) -> dict[str, Any] | None:
        if self.status != "unreadable":
            return None
        payload: dict[str, Any] = {
            "status": self.status,
            "error_code": self.error_code or "latent_discovery_bundle_unreadable",
            "error_message": (self.error_message or "latent discovery bundle could not be loaded"),
        }
        if self.source_bundle_ref is not None:
            payload["source_bundle_ref"] = self.source_bundle_ref.model_dump(mode="json")
        return payload


class PolicyEvaluationBackend(Protocol):
    """Policy evaluation backend implementation."""

    backend_kind: str

    def evaluate(
        self,
        candidate: PolicyCandidateSchema,
        *,
        fidelity: str,
        simulation_metrics: dict[str, float] | None,
        uncertainty: UncertaintyEnvelope | None,
        distributional_report: DistributionalReport | None,
        causal_effect_report: CausalEffectReport | None,
        cross_graph_profile: CrossGraphEvidenceProfile | None,
        governance_report: GovernanceReport | None,
        ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
    ) -> PolicyRuntimeEvaluationArtifact: ...


def _policy_runtime_input_hash(value: object) -> str:
    model_dump = getattr(value, "model_dump", None)
    payload = model_dump(mode="json") if callable(model_dump) else value
    return gy_content_hash(payload)


def _production_policy_evaluation_safety_blockers(
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
) -> tuple[str, ...]:
    return _runtime_artifacts._production_policy_evaluation_safety_blockers_impl(
        context=context,
        verifier=verifier,
        world_model_record=world_model_record,
        candidate=candidate,
        simulation_metrics=simulation_metrics,
        uncertainty=uncertainty,
        distributional_report=distributional_report,
        causal_effect_report=causal_effect_report,
        cross_graph_profile=cross_graph_profile,
        governance_report=governance_report,
        ambiguity_certificate=ambiguity_certificate,
        blocker_fn=_eval_safety_blocker,
        input_hash_fn=_policy_runtime_input_hash,
        production_owner_component_id=PRODUCTION_POLICY_EVALUATION_BACKEND_ID,
        world_model_record_content_hash_fn=world_model_record_content_hash,
        challenge_factory=EvalSafetyAdmissionChallenge,
        admission_check=evaluation_safety_consumer_admission_is_verified,
    )


@dataclass(frozen=True)
class ProductionPolicyEvaluationBackend:
    """Production policy evaluation backend implementation."""

    eval_safety_execution_context: EvaluationExecutionContext | None = None
    eval_safety_verifier: EvalSafetyVerifierPort | None = None
    world_model_record: WorldModelRecord | None = None
    backend_kind: str = "production"

    def evaluate(
        self,
        candidate: PolicyCandidateSchema,
        *,
        fidelity: str,
        simulation_metrics: dict[str, float] | None,
        uncertainty: UncertaintyEnvelope | None,
        distributional_report: DistributionalReport | None,
        causal_effect_report: CausalEffectReport | None,
        cross_graph_profile: CrossGraphEvidenceProfile | None,
        governance_report: GovernanceReport | None,
        ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
    ) -> PolicyRuntimeEvaluationArtifact:
        safety_blockers = _production_policy_evaluation_safety_blockers(
            context=self.eval_safety_execution_context,
            verifier=self.eval_safety_verifier,
            world_model_record=self.world_model_record,
            candidate=candidate,
            simulation_metrics=simulation_metrics,
            uncertainty=uncertainty,
            distributional_report=distributional_report,
            causal_effect_report=causal_effect_report,
            cross_graph_profile=cross_graph_profile,
            governance_report=governance_report,
            ambiguity_certificate=ambiguity_certificate,
        )
        if safety_blockers:
            raise PolicyRuntimeEvaluationSafetyError(safety_blockers)

        metrics, source_components, notes = _build_evidence_driven_simulation_metrics(
            candidate,
            fidelity=fidelity,
            simulation_metrics=simulation_metrics,
            uncertainty=uncertainty,
            distributional_report=distributional_report,
            causal_effect_report=causal_effect_report,
            cross_graph_profile=cross_graph_profile,
            governance_report=governance_report,
        )
        source_components_list = list(source_components)
        if ambiguity_certificate is not None:
            source_components_list.append("ambiguity_certificate")
        evaluation_vector = ObjectiveStack().evaluate(
            PolicyEvaluationBundle(
                candidate=candidate,
                simulation_metrics=metrics,
                distributional_report=distributional_report,
                causal_effect_report=causal_effect_report,
                cross_graph_profile=cross_graph_profile,
                governance_report=governance_report,
                uncertainty_envelope=uncertainty,
                ambiguity_certificate=ambiguity_certificate,
                metadata={
                    "generated_by": f"policy_runtime::{self.backend_kind}::{fidelity}",
                    "source_components": list(dict.fromkeys(source_components_list)),
                },
            )
        )
        promotable_source = (
            fidelity == "full"
            and causal_effect_report is not None
            and uncertainty is not None
            and governance_report is not None
            and (bool(simulation_metrics) or "causal_effect_report" in source_components)
        )
        provenance = PolicyRuntimeProvenance(
            backend_kind=self.backend_kind,
            fidelity_mode=fidelity,
            promotable_source=promotable_source,
            degradation_mode=None if promotable_source or fidelity != "full" else "research_only",
            source_components=tuple(dict.fromkeys(source_components_list)),
            notes=notes,
        )
        return PolicyRuntimeEvaluationArtifact(
            simulation_metrics=metrics,
            simulation_results=build_policy_simulation_results(
                evaluation_vector,
                fidelity=fidelity,
                uncertainty=uncertainty,
                base_metrics=metrics,
                provenance=provenance,
                ambiguity_certificate=ambiguity_certificate,
            ),
            evaluation_vector=evaluation_vector,
            fidelity=fidelity,
            provenance=provenance,
        )


@dataclass(frozen=True)
class SyntheticPolicyEvaluationBackend:
    """Synthetic policy evaluation backend implementation."""

    backend_kind: str = "synthetic"

    def evaluate(
        self,
        candidate: PolicyCandidateSchema,
        *,
        fidelity: str,
        simulation_metrics: dict[str, float] | None,
        uncertainty: UncertaintyEnvelope | None,
        distributional_report: DistributionalReport | None,
        causal_effect_report: CausalEffectReport | None,
        cross_graph_profile: CrossGraphEvidenceProfile | None,
        governance_report: GovernanceReport | None,
        ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
    ) -> PolicyRuntimeEvaluationArtifact:
        del simulation_metrics, causal_effect_report, cross_graph_profile
        metrics = _build_runtime_simulation_metrics(
            candidate,
            fidelity=fidelity,
            governance_report=governance_report,
            distributional_report=distributional_report,
        )
        evaluation_vector = ObjectiveStack().evaluate(
            PolicyEvaluationBundle(
                candidate=candidate,
                simulation_metrics=metrics,
                distributional_report=distributional_report,
                causal_effect_report=None,
                cross_graph_profile=None,
                governance_report=governance_report,
                uncertainty_envelope=uncertainty,
                ambiguity_certificate=ambiguity_certificate,
                metadata={
                    "generated_by": f"policy_runtime::{self.backend_kind}::{fidelity}",
                    "source_components": (
                        ["synthetic_policy_runtime", "ambiguity_certificate"]
                        if ambiguity_certificate is not None
                        else ["synthetic_policy_runtime"]
                    ),
                },
            )
        )
        source_components = (
            ("synthetic_policy_runtime", "ambiguity_certificate")
            if ambiguity_certificate is not None
            else ("synthetic_policy_runtime",)
        )
        provenance = PolicyRuntimeProvenance(
            backend_kind=self.backend_kind,
            fidelity_mode=fidelity,
            promotable_source=False,
            degradation_mode="research_only",
            source_components=source_components,
            notes=("Synthetic backend is test-only and not promotion-safe.",),
        )
        return PolicyRuntimeEvaluationArtifact(
            simulation_metrics=metrics,
            simulation_results=build_policy_simulation_results(
                evaluation_vector,
                fidelity=fidelity,
                uncertainty=uncertainty,
                base_metrics=metrics,
                provenance=provenance,
                ambiguity_certificate=ambiguity_certificate,
            ),
            evaluation_vector=evaluation_vector,
            fidelity=fidelity,
            provenance=provenance,
        )


def ensure_policy_candidate_ref(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef | None,
) -> ArtifactRef:
    """Ensure a persisted policy-candidate reference is available."""
    return _runtime_artifacts._ensure_policy_candidate_ref_impl(
        ctx, state, candidate, candidate_ref
    )


def resolve_policy_evaluation(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
) -> tuple[PolicyEvaluationVector | None, ArtifactRef | None]:
    """Resolve a policy evaluation from inputs or the configured objective stack."""
    return _runtime_artifacts._resolve_policy_evaluation_impl(
        ctx,
        state,
        candidate,
        candidate_ref,
        parse_evaluation=_parse_policy_evaluation,
        load_metrics=load_simulation_metrics,
        objective_stack_factory=ObjectiveStack,
        bundle_factory=PolicyEvaluationBundle,
        load_distributional=load_distributional_report_for_state,
        load_causal=load_causal_report,
        load_cross_graph=load_cross_graph_profile,
        load_governance=load_governance_report,
        load_uncertainty=load_search_uncertainty,
        load_ambiguity=load_ambiguity_certificate,
        persist_vector=persist_policy_evaluation_vector,
    )


def persist_policy_evaluation_vector(
    ctx: ExecutionContext,
    *,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
) -> ArtifactRef:
    """Persist a policy-evaluation vector through the execution context store."""
    return _runtime_artifacts._persist_policy_evaluation_vector_impl(
        ctx, candidate_ref=candidate_ref, evaluation_vector=evaluation_vector
    )


def persist_policy_evaluation_vector_to_store(
    store: ArtifactStore,
    *,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
) -> ArtifactRef:
    """Persist a native policy-runtime evaluation vector to the supplied CAS."""
    return _runtime_artifacts._persist_policy_evaluation_vector_to_store_impl(
        store, candidate_ref=candidate_ref, evaluation_vector=evaluation_vector
    )


def persist_funnel_executed_work_packet(
    store: ArtifactStore,
    packet: FunnelExecutedWorkPacket,
) -> ArtifactRef:
    """Persist a completed policy-runtime invocation record with CAS lineage."""
    return _runtime_artifacts._persist_funnel_executed_work_packet_impl(store, packet)


def build_selection_benchmark_evaluation(
    *,
    state: ExperimentState,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    runtime_artifact: PolicyRuntimeEvaluationArtifact | None = None,
    source: str = "policy_runtime_selection",
    metadata_extension: Mapping[str, Any] | None = None,
) -> BenchmarkEvaluation:
    """Build the selection benchmark view for an evaluation vector."""
    return _runtime_artifacts._build_selection_benchmark_evaluation_impl(
        state=state,
        candidate_ref=candidate_ref,
        evaluation_vector=evaluation_vector,
        runtime_artifact=runtime_artifact,
        source=source,
        metadata_extension=metadata_extension,
        selection_score_fn=selection_score,
    )


def build_policy_runtime_evaluation(
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
    """Build a policy-runtime evaluation through its configured backend."""
    return _runtime_artifacts._build_policy_runtime_evaluation_impl(
        candidate,
        backend=backend,
        fidelity=fidelity,
        simulation_metrics=simulation_metrics,
        uncertainty=uncertainty,
        distributional_report=distributional_report,
        causal_effect_report=causal_effect_report,
        cross_graph_profile=cross_graph_profile,
        governance_report=governance_report,
        ambiguity_certificate=ambiguity_certificate,
    )


def build_policy_simulation_results(
    evaluation: PolicyEvaluationVector,
    *,
    fidelity: str,
    uncertainty: UncertaintyEnvelope | None,
    base_metrics: dict[str, float] | None = None,
    provenance: PolicyRuntimeProvenance | None = None,
    ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build metric and provenance projections for a policy-runtime result."""
    return _runtime_metrics._build_policy_simulation_results_impl(
        evaluation,
        fidelity=fidelity,
        uncertainty=uncertainty,
        base_metrics=base_metrics,
        provenance=provenance,
        ambiguity_certificate=ambiguity_certificate,
    )


def build_vulnerabilities(
    *,
    evaluation: PolicyEvaluationVector | None,
    distributional,
    causal_report: CausalEffectReport | None,
    governance_report: GovernanceReport | None,
) -> list[Any]:
    """Build vulnerability records from evaluation and evidence inputs."""
    return _runtime_artifacts._build_vulnerabilities_impl(
        evaluation=evaluation,
        distributional=distributional,
        causal_report=causal_report,
        governance_report=governance_report,
    )


def selection_score(evaluation_vector: PolicyEvaluationVector) -> float:
    """Return the primary policy-value score, preserving the fallback order."""
    return _runtime_metrics._selection_score_impl(evaluation_vector)


def load_simulation_metrics(ctx: ExecutionContext, state: ExperimentState) -> dict[str, float]:
    """Load normalized simulation metrics from the state artifact index."""
    return _runtime_artifacts._load_simulation_metrics_impl(ctx, state)


def load_distributional_report_for_state(ctx: ExecutionContext, state: ExperimentState):
    """Load the state-bound distributional report, when present."""
    return _runtime_artifacts._load_distributional_report_for_state_impl(ctx, state)


def load_causal_report(ctx: ExecutionContext, state: ExperimentState) -> CausalEffectReport | None:
    """Load the causal report indexed by the current state."""
    return _runtime_artifacts._load_causal_report_impl(ctx, state)


def load_governance_report(
    ctx: ExecutionContext, state: ExperimentState
) -> GovernanceReport | None:
    """Load the governance report indexed by the current state."""
    return _runtime_artifacts._load_governance_report_impl(ctx, state)


def load_cross_graph_profile(ctx: ExecutionContext, state: ExperimentState):
    """Load the cross-graph evidence profile indexed by the current state."""
    return _runtime_artifacts._load_cross_graph_profile_impl(ctx, state)


def load_prior_knowledge_bundle_for_state(
    ctx: ExecutionContext, state: ExperimentState
) -> PriorKnowledgeBundle | None:
    """Load prior knowledge directly or through the discovery bundle reference."""
    return _runtime_artifacts._load_prior_knowledge_bundle_for_state_impl(ctx, state)


def resolve_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> LatentDiscoveryBundleResolution:
    """Resolve latent discovery bundle for state."""
    return _runtime_artifacts._resolve_latent_discovery_bundle_for_state_impl(
        ctx, state, resolution_factory=LatentDiscoveryBundleResolution
    )


def resolve_effective_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    causal_report: CausalEffectReport | None = None,
) -> LatentDiscoveryBundleResolution:
    """Resolve effective latent discovery bundle for state."""
    return _runtime_artifacts._resolve_effective_latent_discovery_bundle_for_state_impl(
        ctx,
        state,
        causal_report=causal_report,
        resolve_base=resolve_latent_discovery_bundle_for_state,
        merge_proxy=_merge_proxy_boundary_into_latent_bundle,
        resolution_factory=LatentDiscoveryBundleResolution,
    )


def load_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> LatentDiscoveryBundle | None:
    """Load latent discovery bundle for state."""
    return _runtime_artifacts._load_latent_discovery_bundle_for_state_impl(
        ctx, state, resolve_base=resolve_latent_discovery_bundle_for_state
    )


def load_effective_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    causal_report: CausalEffectReport | None = None,
) -> LatentDiscoveryBundle | None:
    """Load effective latent discovery bundle for state."""
    return _runtime_artifacts._load_effective_latent_discovery_bundle_for_state_impl(
        ctx,
        state,
        causal_report=causal_report,
        resolve_effective=resolve_effective_latent_discovery_bundle_for_state,
    )


def _proxy_boundary_payload_from_causal_report(
    report: CausalEffectReport | None,
) -> dict[str, Any] | None:
    return _runtime_artifacts._proxy_boundary_payload_from_causal_report_impl(report)


def _merge_proxy_boundary_into_latent_bundle(
    bundle: LatentDiscoveryBundle | None,
    proxy_boundary_payload: dict[str, Any] | None,
) -> LatentDiscoveryBundle | None:
    return _runtime_artifacts._merge_proxy_boundary_into_latent_bundle_impl(
        bundle, proxy_boundary_payload
    )


def load_search_uncertainty(ctx: ExecutionContext, state: ExperimentState):
    """Load the causal uncertainty envelope for search consumption."""
    return _runtime_artifacts._load_search_uncertainty_impl(ctx, state)


def load_ambiguity_certificate(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> AmbiguityCertificate | None:
    """Load an ambiguity certificate from runtime params or artifacts."""
    return _runtime_artifacts._load_ambiguity_certificate_impl(
        ctx,
        state,
        parse_certificate=_parse_ambiguity_certificate,
        artifact_ref_parser=maybe_artifact_ref,
    )


def resolve_funnel_outcome(state: ExperimentState) -> FunnelOutcome | None:
    """Resolve a typed funnel outcome from state params."""
    return _runtime_artifacts._resolve_funnel_outcome_impl(state)


def maybe_artifact_ref(value: Any) -> ArtifactRef | None:
    """Parse a canonical artifact reference when the input shape permits it."""
    return _runtime_artifacts._maybe_artifact_ref_impl(value)


def load_benchmark_evaluation(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> BenchmarkEvaluation:
    """Load a benchmark evaluation artifact."""
    return _runtime_artifacts._load_benchmark_evaluation_impl(ctx, ref)


def load_governance_report_from_ref(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> GovernanceReport:
    """Load a governance report artifact from its reference."""
    return _runtime_artifacts._load_governance_report_from_ref_impl(ctx, ref)


def run_promotion_with_evidence(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    evidence_bundle: PromotionEvidenceBundle,
    promotion_context: dict[str, Any] | None = None,
    evaluation_provenance: dict[str, Any] | None = None,
) -> PolicyPromotionResult:
    """Run promotion with evidence."""
    expected_loop_id = str(state.params.get("policy_loop_id") or state.run_id)
    selection_ref = evidence_bundle.selection_evaluation_ref
    if selection_ref is None:
        raise ValueError("PromotionEvidenceBundle selection_evaluation_ref is required.")
    verification_ref = evidence_bundle.replay_verification_ref
    verification_report = None
    if verification_ref is not None:
        verification_report = load_replay_verification_report(ctx.store, verification_ref)
    elif evidence_bundle.replay_bundle_ref is not None:
        verification_ref = verify_and_persist_replay_bundle(
            ctx.store,
            run_id=state.run_id,
            replay_bundle_ref=evidence_bundle.replay_bundle_ref,
            candidate_ref=candidate_ref,
            evaluation_ref=evidence_bundle.evaluation_ref or selection_ref,
            registry=ReplayRegistry(Path(ctx.store.root) / "search_registry" / "replay_registry"),
        )
        verification_report = load_replay_verification_report(ctx.store, verification_ref)
        evidence_bundle = evidence_bundle.model_copy(
            update={"replay_verification_ref": verification_ref}
        )
    evidence_bundle.assert_runtime_compatible(
        run_id=state.run_id,
        store=ctx.store,
        expected_loop_id=expected_loop_id,
        expected_refs={
            "candidate_ref": candidate_ref,
            "selection_evaluation_ref": selection_ref,
            "hidden_holdout_evaluation_ref": maybe_artifact_ref(
                state.params.get("hidden_holdout_evaluation_ref")
            ),
            "promotion_evidence_bundle_ref": maybe_artifact_ref(
                state.params.get("promotion_evidence_bundle_ref")
            ),
            "replay_bundle_ref": state.artifacts_index.get("replayable_audit_bundle_ref"),
            "governance_report_ref": state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF),
        },
    )
    missing = evidence_bundle.missing_required_refs(
        require_hidden_holdout=True,
        require_replay_bundle=True,
        require_replay_verification=True,
        require_governance=True,
        require_calibration=True,
    )
    if missing:
        raise ValueError(
            "PromotionEvidenceBundle is incomplete for promotion: " + ", ".join(sorted(missing))
        )

    hidden_holdout_ref = evidence_bundle.hidden_holdout_evaluation_ref
    platform_meta_ref = evidence_bundle.adversarial_meta_evaluation_ref
    assert hidden_holdout_ref is not None
    assert platform_meta_ref is not None

    selection_evaluation = load_benchmark_evaluation(ctx, selection_ref)
    hidden_holdout = load_benchmark_evaluation(ctx, hidden_holdout_ref)
    platform_meta = load_platform_meta_evaluation_report(ctx.store, platform_meta_ref)
    governance_report = (
        load_governance_report_from_ref(ctx, evidence_bundle.governance_report_ref)
        if evidence_bundle.governance_report_ref is not None
        else load_governance_report(ctx, state)
    )
    if governance_report is None:
        raise ValueError("PromotionEvidenceBundle governance_report_ref could not be resolved.")
    causal_report = load_causal_report(ctx, state)
    distributional_report = load_distributional_report_for_state(ctx, state)
    cross_graph_profile = load_cross_graph_profile(ctx, state)
    prior_knowledge_bundle = load_prior_knowledge_bundle_for_state(ctx, state)
    latent_resolution = resolve_effective_latent_discovery_bundle_for_state(
        ctx,
        state,
        causal_report=causal_report,
    )
    latent_discovery_bundle = latent_resolution.bundle
    uncertainty = load_search_uncertainty(ctx, state)
    l2_result = (
        promotion_context.get("_funnel_L2_result") if isinstance(promotion_context, dict) else None
    )
    l2_feedback = dict(getattr(l2_result, "feedback", {}) or {})
    data_readiness_report_ref = maybe_artifact_ref(l2_feedback.get("data_readiness_report_ref"))
    data_readiness_report = None
    if data_readiness_report_ref is not None:
        try:
            data_readiness_report = load_data_readiness_report(
                _ensure_ir_artifact_store(ctx.store),
                data_readiness_report_ref,
            )
        except _POLICY_RUNTIME_LOAD_ERRORS:
            data_readiness_report = None
    proof_bundle_ref = maybe_artifact_ref(l2_feedback.get("proof_bundle_ref"))
    bounds_bundle_ref = maybe_artifact_ref(l2_feedback.get("bounds_bundle_ref"))
    negative_certificate_ref = maybe_artifact_ref(l2_feedback.get("negative_certificate_ref"))
    evidence_metadata = dict(evidence_bundle.metadata)
    artifact_family = normalize_phase2_artifact_family(
        str(evidence_metadata.get("artifact_family") or ""),
        estimator_name=(
            None
            if evidence_metadata.get("estimator_name") is None
            else str(evidence_metadata.get("estimator_name"))
        ),
        query_type=(
            None
            if evidence_metadata.get("query_type") is None
            else str(evidence_metadata.get("query_type"))
        ),
    )
    claim_mode = (
        str(evidence_metadata.get("claim_mode") or "estimation").strip().lower() or "estimation"
    )
    query_type = (
        str(evidence_metadata.get("query_type"))
        if evidence_metadata.get("query_type") is not None
        else None
    )
    estimator_name = (
        str(evidence_metadata.get("estimator_name"))
        if evidence_metadata.get("estimator_name") is not None
        else None
    )
    readiness_target = (
        str(evidence_metadata.get("readiness_target"))
        if evidence_metadata.get("readiness_target") is not None
        else None
    )

    champion_registry = ChampionRegistry(
        root=Path(ctx.store.root) / "search_registry",
        store=ctx.store,
    )
    coordinator = PolicyPromotionCoordinator(
        champion_registry=champion_registry,
        store=ctx.store,
    )
    loop_id = expected_loop_id
    runtime_provenance = dict(evaluation_provenance or {})
    phase3_gate = resolve_phase3_gate(ctx, state, candidate=candidate)
    judge_input = coordinator.build_input_bundle(
        candidate=candidate,
        funnel_outcome=resolve_funnel_outcome(state),
        benchmark_evaluation=selection_evaluation,
        hidden_holdout_evaluation=hidden_holdout,
        platform_meta_evaluation_report=platform_meta,
        evaluation_vector=evaluation_vector,
        distributional_report=distributional_report,
        causal_effect_report=causal_report,
        data_readiness_report=data_readiness_report,
        data_readiness_report_ref=data_readiness_report_ref,
        artifact_family=artifact_family,
        claim_mode=claim_mode,
        query_type=query_type,
        estimator_name=estimator_name,
        readiness_target=readiness_target,
        proof_bundle_ref=proof_bundle_ref,
        bounds_bundle_ref=bounds_bundle_ref,
        negative_certificate_ref=negative_certificate_ref,
        replay_bundle_ref=evidence_bundle.replay_bundle_ref,
        replay_verification_ref=verification_ref,
        replay_verification_report=verification_report,
        promotion_evidence_bundle_ref=maybe_artifact_ref(
            state.params.get("promotion_evidence_bundle_ref")
        ),
        cross_graph_profile=cross_graph_profile,
        prior_knowledge_bundle=prior_knowledge_bundle,
        governance_report=governance_report,
        latent_discovery_bundle=latent_discovery_bundle,
        latent_discovery_resolution_error=latent_resolution.error_payload(),
        uncertainty_envelope=uncertainty,
        candidate_ref=candidate_ref,
        evaluation_ref=evidence_bundle.evaluation_ref or selection_ref,
        run_id=state.run_id,
        state={
            "audit_lineage_complete": (
                candidate_ref is not None
                and evidence_bundle.replay_bundle_ref is not None
                and verification_ref is not None
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
        evaluation_backend_kind=(
            str(runtime_provenance.get("backend_kind"))
            if runtime_provenance.get("backend_kind") is not None
            else None
        ),
        evaluation_fidelity_mode=(
            str(runtime_provenance.get("fidelity_mode"))
            if runtime_provenance.get("fidelity_mode") is not None
            else None
        ),
        evaluation_promotable_source=bool(runtime_provenance.get("promotable_source", True)),
        evaluation_degradation_mode=(
            str(runtime_provenance.get("degradation_mode"))
            if runtime_provenance.get("degradation_mode") is not None
            else None
        ),
        evaluation_provenance_notes=[
            str(item) for item in list(runtime_provenance.get("notes", []) or [])
        ],
        phase3_gate=phase3_gate,
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
        evaluation_ref=evidence_bundle.evaluation_ref or selection_ref,
        promotion_policy=promotion_policy,
        judge_input=judge_input,
    )


def _build_runtime_simulation_metrics(
    candidate: PolicyCandidateSchema,
    *,
    fidelity: str,
    governance_report: GovernanceReport | None,
    distributional_report: DistributionalReport | None,
) -> dict[str, float]:
    return _runtime_metrics._build_runtime_simulation_metrics(
        candidate,
        fidelity=fidelity,
        governance_report=governance_report,
        distributional_report=distributional_report,
    )


def _build_evidence_driven_simulation_metrics(
    candidate: PolicyCandidateSchema,
    *,
    fidelity: str,
    simulation_metrics: dict[str, float] | None,
    uncertainty: UncertaintyEnvelope | None,
    distributional_report: DistributionalReport | None,
    causal_effect_report: CausalEffectReport | None,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    governance_report: GovernanceReport | None,
) -> tuple[dict[str, float], tuple[str, ...], tuple[str, ...]]:
    return _runtime_metrics._build_evidence_driven_simulation_metrics(
        candidate,
        fidelity=fidelity,
        simulation_metrics=simulation_metrics,
        uncertainty=uncertainty,
        distributional_report=distributional_report,
        causal_effect_report=causal_effect_report,
        cross_graph_profile=cross_graph_profile,
        governance_report=governance_report,
    )


def _parse_policy_evaluation(value: Any) -> PolicyEvaluationVector | None:
    return _runtime_metrics._parse_policy_evaluation(value)


def _parse_ambiguity_certificate(value: Any) -> AmbiguityCertificate | None:
    return _runtime_metrics._parse_ambiguity_certificate(value)


def _ambiguity_certificate_payload(
    value: AmbiguityCertificate | dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _runtime_metrics._ambiguity_certificate_payload(value)


def _channel_higher_is_better(
    evaluation: PolicyEvaluationVector,
    name: str,
    *,
    fallback: float = 0.0,
) -> float:
    return _runtime_metrics._channel_higher_is_better(evaluation, name, fallback=fallback)


def _budget_pressure(evaluation: PolicyEvaluationVector) -> float:
    return _runtime_metrics._budget_pressure(evaluation)


def _employment_signal_from_distribution(
    distributional_report: DistributionalReport | None,
    *,
    fallback: float,
) -> float:
    return _runtime_metrics._employment_signal_from_distribution(
        distributional_report, fallback=fallback
    )


def _distributional_shift_penalty(distributional_report: DistributionalReport | None) -> float:
    return _runtime_metrics._distributional_shift_penalty(distributional_report)


def _transport_penalty(cross_graph_profile: CrossGraphEvidenceProfile | None) -> float:
    return _runtime_metrics._transport_penalty(cross_graph_profile)


def _policy_budget_total(candidate: PolicyCandidateSchema) -> float:
    return _runtime_metrics._policy_budget_total(candidate)


__all__ = [
    "LatentDiscoveryBundleResolution",
    "PRODUCTION_POLICY_EVALUATION_BACKEND_ID",
    "PolicyEvaluationBackend",
    "PolicyRuntimeEvaluationArtifact",
    "PolicyRuntimeEvaluationSafetyError",
    "PolicyRuntimeProvenance",
    "ProductionPolicyEvaluationBackend",
    "SyntheticPolicyEvaluationBackend",
    "build_policy_runtime_evaluation",
    "build_policy_simulation_results",
    "build_selection_benchmark_evaluation",
    "build_vulnerabilities",
    "ensure_policy_candidate_ref",
    "load_ambiguity_certificate",
    "load_benchmark_evaluation",
    "load_causal_report",
    "load_cross_graph_profile",
    "load_distributional_report_for_state",
    "load_effective_latent_discovery_bundle_for_state",
    "load_governance_report",
    "load_governance_report_from_ref",
    "load_latent_discovery_bundle_for_state",
    "load_prior_knowledge_bundle_for_state",
    "load_search_uncertainty",
    "maybe_artifact_ref",
    "persist_policy_evaluation_vector",
    "resolve_effective_latent_discovery_bundle_for_state",
    "resolve_funnel_outcome",
    "resolve_latent_discovery_bundle_for_state",
    "resolve_policy_evaluation",
    "run_promotion_with_evidence",
    "selection_score",
]
