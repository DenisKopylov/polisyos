"""Public decide policy runtime support module API."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import ValidationError

from polisyos.core import components as core_components
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
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
from polisyos.runtime.quality import (
    EvalSafetyAdmissionChallenge,
    evaluation_safety_consumer_admission_is_verified,
    gy_content_hash,
    resolve_evaluation_mode,
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

if TYPE_CHECKING:
    from polisyos.runtime.quality import (
        EvalSafetyVerifierPort,
        EvaluationExecutionContext,
        WorldModelRecord,
    )
from polisyos.scientist.methods.search.adversarial import load_platform_meta_evaluation_report
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.methods.search.judge_stack import (
    PolicyPromotionCoordinator,
    PolicyPromotionResult,
    to_search_uncertainty_envelope,
)
from polisyos.scientist.methods.search.promotion_evidence import PromotionEvidenceBundle
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope, UncertaintyType

_POLICY_RUNTIME_VALIDATION_ERRORS = (TypeError, ValidationError, ValueError)
_POLICY_RUNTIME_LOAD_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)
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
    if context is None:
        return (_eval_safety_blocker("execution_context_missing"),)

    mode_resolution = resolve_evaluation_mode(context.evaluation_mode)
    if mode_resolution.status != "accepted":
        return (mode_resolution.blocker_code or _eval_safety_blocker("evaluation_mode_unknown"),)
    if context.evaluator_owner_id != PRODUCTION_POLICY_EVALUATION_BACKEND_ID:
        return (_eval_safety_blocker("evaluator_owner_mismatch"),)
    if world_model_record is None:
        return (_eval_safety_blocker("world_model_record_not_established"),)

    recomputed_wmr_hash = world_model_record_content_hash(world_model_record)
    world_model_binds = bool(
        world_model_record.content_hash == recomputed_wmr_hash
        and context.world_model_record_ref.content_hash == recomputed_wmr_hash
        and context.world_model_record_ref.artifact_id == world_model_record.world_model_record_id
        and context.world_model_record_ref.artifact_type == "world_model_record"
        and context.world_model_record_ref.schema_ref == "policyos.runtime.world_model_record.v1"
    )
    if not world_model_binds:
        return (_eval_safety_blocker("world_model_record_binding_mismatch"),)

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
    actual_hashes = tuple(
        _policy_runtime_input_hash(value) for value in actual_values if value is not None
    )
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
        and context.candidate_ref.content_hash == _policy_runtime_input_hash(candidate)
        and context.target_population_scope_ref.artifact_type == "target_population_scope"
        and context.target_population_scope_ref.content_hash
        == _policy_runtime_input_hash(candidate.target_population)
        and context.rule_version.strip()
        and context.intended_start_at.tzinfo is not None
    )
    if (
        not exact_inputs_bind
        or not exact_owner_inputs_bind
        or context.attempt_class != "non_simulation"
    ):
        return (_eval_safety_blocker("execution_context_binding_mismatch"),)
    if context.evaluation_mode == "simulate_only":
        return (_eval_safety_blocker("simulation_provenance_not_established"),)
    if verifier is None:
        return (_eval_safety_blocker("verifier_unresolved"),)

    challenge = EvalSafetyAdmissionChallenge.fresh(
        consumer_component_id=PRODUCTION_POLICY_EVALUATION_BACKEND_ID
    )
    receipt = verifier.require_admission(context, challenge)
    if not evaluation_safety_consumer_admission_is_verified(receipt, context, challenge):
        return receipt.blocker_codes or (_eval_safety_blocker("consumer_admission_blocked"),)
    return ()


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


def resolve_policy_evaluation(
    ctx: ExecutionContext,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    candidate_ref: ArtifactRef,
) -> tuple[PolicyEvaluationVector | None, ArtifactRef | None]:
    """Resolve policy evaluation."""
    parsed = _parse_policy_evaluation(state.params.get("policy_evaluation"))
    if parsed is None:
        metrics = load_simulation_metrics(ctx, state)
        if not metrics:
            return None, None
        parsed = ObjectiveStack().evaluate(
            PolicyEvaluationBundle(
                candidate=candidate,
                simulation_metrics=metrics,
                distributional_report=load_distributional_report_for_state(ctx, state),
                causal_effect_report=load_causal_report(ctx, state),
                cross_graph_profile=load_cross_graph_profile(ctx, state),
                governance_report=load_governance_report(ctx, state),
                uncertainty_envelope=load_search_uncertainty(ctx, state),
                ambiguity_certificate=load_ambiguity_certificate(ctx, state),
            )
        )
    ref = persist_policy_evaluation_vector(
        ctx,
        candidate_ref=candidate_ref,
        evaluation_vector=parsed,
    )
    return parsed, ref


def persist_policy_evaluation_vector(
    ctx: ExecutionContext,
    *,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
) -> ArtifactRef:
    """Persist policy evaluation vector helper."""
    return ctx.store.put_json(
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


def build_selection_benchmark_evaluation(
    *,
    state: ExperimentState,
    candidate_ref: ArtifactRef,
    evaluation_vector: PolicyEvaluationVector,
    runtime_artifact: PolicyRuntimeEvaluationArtifact | None = None,
    source: str = "policy_runtime_selection",
    metadata_extension: Mapping[str, Any] | None = None,
) -> BenchmarkEvaluation:
    """Build selection benchmark evaluation."""
    base_score = selection_score(evaluation_vector)
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


def build_policy_simulation_results(
    evaluation: PolicyEvaluationVector,
    *,
    fidelity: str,
    uncertainty: UncertaintyEnvelope | None,
    base_metrics: dict[str, float] | None = None,
    provenance: PolicyRuntimeProvenance | None = None,
    ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build policy simulation results."""
    metrics = dict(base_metrics or {})
    policy_value = float(
        metrics.get("policy_value", _channel_higher_is_better(evaluation, "policy_value"))
    )
    employment = float(
        metrics.get("employment", _channel_higher_is_better(evaluation, "employment"))
    )
    welfare = float(
        metrics.get(
            "welfare", _channel_higher_is_better(evaluation, "welfare", fallback=policy_value)
        )
    )
    budget_pressure = float(metrics.get("budget_penalty", _budget_pressure(evaluation)))
    gov_balance = float(metrics.get("gov_balance", -abs(budget_pressure)))
    ate = float(metrics.get("ate", policy_value))
    statistical = (
        uncertainty.uncertainties.get(UncertaintyType.STATISTICAL)
        if isinstance(uncertainty, UncertaintyEnvelope)
        else None
    )
    ci_width = 0.12 if fidelity == "selection" else 0.1
    if statistical is not None:
        ci_width = max(
            ci_width,
            float(statistical.level) * (0.22 if fidelity == "full" else 0.34),
        )
    if not evaluation.feasible:
        ci_width = max(ci_width, 0.35)
    ambiguity_payload = _ambiguity_certificate_payload(ambiguity_certificate)
    return {
        "policy_value": policy_value,
        "employment": employment,
        "welfare": welfare,
        "net_social_welfare": float(metrics.get("net_social_welfare", welfare)),
        "gdp_change": float(metrics.get("gdp_change", welfare)),
        "gov_balance": gov_balance,
        "ate": ate,
        "bootstrap": {
            "ci_width": ci_width,
            "draws": 500 if fidelity == "full" else (64 if fidelity == "medium" else 32),
            "fidelity": fidelity,
        },
        "objective_channels": {
            name: channel.value for name, channel in evaluation.all_channels().items()
        },
        "blocking_reasons": list(evaluation.blocking_reasons),
        "fidelity": fidelity,
        "evaluation_backend_kind": provenance.backend_kind if provenance is not None else "unknown",
        "promotable_source": provenance.promotable_source if provenance is not None else None,
        "evaluation_degradation_mode": (
            provenance.degradation_mode if provenance is not None else None
        ),
        "evaluation_source_components": list(provenance.source_components)
        if provenance is not None
        else [],
        "ambiguity_certificate": ambiguity_payload,
        "ambiguity_certificate_status": (
            ambiguity_payload.get("overall_status") if isinstance(ambiguity_payload, dict) else None
        ),
    }


def build_vulnerabilities(
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


def selection_score(evaluation_vector: PolicyEvaluationVector) -> float:
    """Selection score helper."""
    if "policy_value" in evaluation_vector.primary:
        return float(evaluation_vector.primary["policy_value"].value)
    if evaluation_vector.primary:
        return float(next(iter(evaluation_vector.primary.values())).value)
    return 0.0


def load_simulation_metrics(ctx: ExecutionContext, state: ExperimentState) -> dict[str, float]:
    """Load simulation metrics."""
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


def load_distributional_report_for_state(ctx: ExecutionContext, state: ExperimentState):
    """Load distributional report for state."""
    ref = state.artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)
    return None if ref is None else load_distributional_report(ctx.store, ref)


def load_causal_report(ctx: ExecutionContext, state: ExperimentState) -> CausalEffectReport | None:
    """Load causal report."""
    ref = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    if ref is None:
        return None
    return CausalEffectReport.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
    )


def load_governance_report(
    ctx: ExecutionContext, state: ExperimentState
) -> GovernanceReport | None:
    """Load governance report."""
    ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
    if ref is None:
        return None
    return GovernanceReport.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
    )


def load_cross_graph_profile(ctx: ExecutionContext, state: ExperimentState):
    """Load cross graph profile."""
    ref = state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
    return None if ref is None else load_cross_graph_evidence_profile(ctx.store, ref)


def load_prior_knowledge_bundle_for_state(
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


def resolve_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> LatentDiscoveryBundleResolution:
    """Resolve latent discovery bundle for state."""
    bundle_ref = state.artifacts_index.get(
        ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF
    ) or state.params.get("discovery_artifact_bundle_ref")
    if bundle_ref is None:
        return LatentDiscoveryBundleResolution(bundle=None, status="missing")
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
        return LatentDiscoveryBundleResolution(
            bundle=latent_bundle,
            status="ok" if latent_bundle is not None else "missing",
            source_bundle_ref=discovery_ref,
        )
    except _POLICY_RUNTIME_LOAD_ERRORS as exc:
        return LatentDiscoveryBundleResolution(
            bundle=None,
            status="unreadable",
            source_bundle_ref=discovery_ref,
            error_code=type(exc).__name__,
            error_message=str(exc),
        )


def resolve_effective_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    causal_report: CausalEffectReport | None = None,
) -> LatentDiscoveryBundleResolution:
    """Resolve effective latent discovery bundle for state."""
    resolution = resolve_latent_discovery_bundle_for_state(ctx, state)
    if resolution.status != "ok" or resolution.bundle is None:
        return resolution
    return LatentDiscoveryBundleResolution(
        bundle=_merge_proxy_boundary_into_latent_bundle(
            resolution.bundle,
            _proxy_boundary_payload_from_causal_report(causal_report),
        ),
        status=resolution.status,
        source_bundle_ref=resolution.source_bundle_ref,
        error_code=resolution.error_code,
        error_message=resolution.error_message,
    )


def load_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> LatentDiscoveryBundle | None:
    """Load latent discovery bundle for state."""
    return resolve_latent_discovery_bundle_for_state(ctx, state).bundle


def load_effective_latent_discovery_bundle_for_state(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    causal_report: CausalEffectReport | None = None,
) -> LatentDiscoveryBundle | None:
    """Load effective latent discovery bundle for state."""
    return resolve_effective_latent_discovery_bundle_for_state(
        ctx,
        state,
        causal_report=causal_report,
    ).bundle


def _proxy_boundary_payload_from_causal_report(
    report: CausalEffectReport | None,
) -> dict[str, Any] | None:
    if report is None:
        return None
    payload = report.metadata.get("proxy_boundary")
    if not isinstance(payload, dict):
        return None
    return dict(payload)


def _merge_proxy_boundary_into_latent_bundle(
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


def load_search_uncertainty(ctx: ExecutionContext, state: ExperimentState):
    """Load search uncertainty."""
    ref = state.artifacts_index.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    if ref is None:
        return to_search_uncertainty_envelope(None)
    return to_search_uncertainty_envelope(load_uncertainty_envelope(ctx.store, ref))


def load_ambiguity_certificate(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> AmbiguityCertificate | None:
    """Load a moment-DRO ambiguity certificate from runtime params or artifacts."""

    for key in (
        "ambiguity_certificate",
        "moment_dro_certificate",
    ):
        certificate = _parse_ambiguity_certificate(state.params.get(key))
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
            certificate = _parse_ambiguity_certificate(container.get("ambiguity_certificate"))
            if certificate is not None:
                return certificate

    for ref_key in ("ambiguity_certificate_ref", "moment_dro_certificate_ref"):
        ref = maybe_artifact_ref(state.params.get(ref_key))
        if ref is None:
            continue
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
        except _POLICY_RUNTIME_LOAD_ERRORS:
            continue
        certificate = _parse_ambiguity_certificate(payload)
        if certificate is not None:
            return certificate
    return None


def resolve_funnel_outcome(state: ExperimentState) -> FunnelOutcome | None:
    """Resolve funnel outcome."""
    for key in ("funnel_outcome", "_funnel_outcome"):
        value = state.params.get(key)
        if isinstance(value, FunnelOutcome):
            return value
    return None


def maybe_artifact_ref(value: Any) -> ArtifactRef | None:
    """Maybe artifact ref helper."""
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict):
        try:
            return ArtifactRef.model_validate(value)
        except _POLICY_RUNTIME_VALIDATION_ERRORS:
            return None
    return None


def load_benchmark_evaluation(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> BenchmarkEvaluation:
    """Load benchmark evaluation."""
    return BenchmarkEvaluation.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
    )


def load_governance_report_from_ref(
    ctx: ExecutionContext,
    ref: ArtifactRef,
) -> GovernanceReport:
    """Load governance report from ref."""
    return GovernanceReport.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
    )


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
                ctx.store,
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
    payload = candidate.model_dump(mode="json")
    canon = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    digest = hashlib.sha256(canon).digest()
    basis = int.from_bytes(digest[:8], byteorder="big") / float(2**64 - 1)

    interventions = list(candidate.trinity_bundle.policy_spec.interventions)
    parameters = list(candidate.trinity_bundle.policy_spec.parameters)
    objectives = list(candidate.trinity_bundle.problem_frame.objectives)
    fidelity_scale = {
        "selection": 0.78,
        "medium": 0.88,
        "full": 1.0,
    }.get(fidelity, 1.0)
    governance_issue_count = float(len(getattr(governance_report, "issues", None) or []))
    subgroup_count = float(len(getattr(distributional_report, "subgroup_reports", None) or []))

    policy_value = max(
        -1.0,
        min(
            1.5,
            (0.35 + basis)
            + (0.08 * len(interventions))
            + (0.03 * len(parameters))
            - (0.04 * governance_issue_count),
        ),
    )
    employment = max(
        -1.0,
        min(
            1.5,
            (0.25 + basis * 0.8) + (0.02 * len(objectives)) - (0.015 * subgroup_count),
        ),
    )
    welfare = (policy_value * 0.65) + (employment * 0.35)
    budget_penalty = max(0.0, (len(parameters) * 0.05) + (len(interventions) * 0.08))

    return {
        "policy_value": policy_value * fidelity_scale,
        "employment": employment * fidelity_scale,
        "welfare": welfare * fidelity_scale,
        "net_social_welfare": welfare * fidelity_scale,
        "gdp_change": welfare * fidelity_scale,
        "gov_balance": -budget_penalty * fidelity_scale,
        "budget_penalty": budget_penalty,
    }


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
    metrics = {
        key: float(value)
        for key, value in dict(simulation_metrics or {}).items()
        if isinstance(value, (int, float))
    }
    source_components: list[str] = []
    notes: list[str] = []

    if metrics:
        source_components.append("metrics_artifact")

    fidelity_scale = {
        "selection": 0.78,
        "medium": 0.86,
        "full": 1.0,
    }.get(fidelity, 1.0)

    point_estimate = None
    if (
        causal_effect_report is not None
        and getattr(causal_effect_report, "point_estimate", None) is not None
    ):
        point_estimate = float(causal_effect_report.point_estimate)
        source_components.append("causal_effect_report")
    elif "ate" in metrics:
        point_estimate = float(metrics["ate"])

    if point_estimate is None:
        point_estimate = 0.0
        notes.append("Missing causal effect report; using conservative zero-effect baseline.")

    if "policy_value" not in metrics:
        metrics["policy_value"] = point_estimate

    if "employment" not in metrics:
        metrics["employment"] = _employment_signal_from_distribution(
            distributional_report,
            fallback=point_estimate * 0.6,
        )
        if distributional_report is not None:
            source_components.append("distributional_report")

    if cross_graph_profile is not None:
        source_components.append("cross_graph_profile")

    if "welfare" not in metrics:
        inequality_penalty = _distributional_shift_penalty(distributional_report)
        governance_penalty = 0.05 * float(len(getattr(governance_report, "issues", None) or []))
        transport_penalty = _transport_penalty(cross_graph_profile)
        metrics["welfare"] = (
            metrics["policy_value"] * 0.65
            + metrics["employment"] * 0.35
            - inequality_penalty
            - governance_penalty
            - transport_penalty
        )

    budget_total = _policy_budget_total(candidate)
    budget_penalty = float(metrics.get("budget_penalty", min(1.0, budget_total / 1000.0)))
    metrics["budget_penalty"] = budget_penalty
    metrics.setdefault("gov_balance", -abs(budget_penalty))
    metrics.setdefault("net_social_welfare", metrics["welfare"])
    metrics.setdefault("gdp_change", metrics["welfare"])
    metrics.setdefault("ate", point_estimate)

    ci_width = None
    if causal_effect_report is not None and getattr(
        causal_effect_report, "confidence_interval", None
    ):
        low, high = causal_effect_report.confidence_interval
        try:
            ci_width = abs(float(high) - float(low))
        except (TypeError, ValueError):
            ci_width = None
    if ci_width is None and isinstance(uncertainty, UncertaintyEnvelope):
        ci_width = max(
            0.08,
            float(uncertainty.uncertainties[UncertaintyType.STATISTICAL].level) * 0.25,
        )
    if ci_width is not None:
        metrics["ci_width"] = float(ci_width)
    if isinstance(uncertainty, UncertaintyEnvelope):
        source_components.append("uncertainty_envelope")
    if governance_report is not None:
        source_components.append("governance_report")

    scaled = {
        key: (
            float(value) * fidelity_scale
            if key not in {"budget_penalty", "ci_width"}
            else float(value)
        )
        for key, value in metrics.items()
    }
    return scaled, tuple(dict.fromkeys(source_components)), tuple(notes)


def _parse_policy_evaluation(value: Any) -> PolicyEvaluationVector | None:
    if isinstance(value, PolicyEvaluationVector):
        return value
    if isinstance(value, dict):
        try:
            return PolicyEvaluationVector.model_validate(value)
        except _POLICY_RUNTIME_VALIDATION_ERRORS:
            return None
    return None


def _parse_ambiguity_certificate(value: Any) -> AmbiguityCertificate | None:
    if isinstance(value, AmbiguityCertificate):
        return value
    if isinstance(value, Mapping):
        payload: Mapping[str, Any] = value
        nested = payload.get("ambiguity_certificate")
        if isinstance(nested, Mapping) or isinstance(nested, AmbiguityCertificate):
            nested_certificate = _parse_ambiguity_certificate(nested)
            if nested_certificate is not None:
                return nested_certificate
        try:
            return AmbiguityCertificate.from_mapping(payload)
        except _POLICY_RUNTIME_VALIDATION_ERRORS:
            return None
    return None


def _ambiguity_certificate_payload(
    value: AmbiguityCertificate | dict[str, Any] | None,
) -> dict[str, Any] | None:
    certificate = _parse_ambiguity_certificate(value)
    if certificate is not None:
        return certificate.to_payload()
    if isinstance(value, dict):
        return dict(value)
    return None


def _channel_higher_is_better(
    evaluation: PolicyEvaluationVector,
    name: str,
    *,
    fallback: float = 0.0,
) -> float:
    channel = evaluation.primary.get(name) or evaluation.secondary.get(name)
    if channel is None:
        return float(fallback)
    return float(channel.higher_is_better)


def _budget_pressure(evaluation: PolicyEvaluationVector) -> float:
    budget_channel = evaluation.hard_constraints.get("policy_budget_constraint")
    if budget_channel is None and evaluation.hard_constraints:
        budget_channel = next(iter(evaluation.hard_constraints.values()))
    if budget_channel is None:
        return 0.0
    return float(budget_channel.value)


def _employment_signal_from_distribution(
    distributional_report: DistributionalReport | None,
    *,
    fallback: float,
) -> float:
    if distributional_report is None:
        return float(fallback)
    winners_losers = getattr(distributional_report, "winners_losers", None)
    winners = list(getattr(winners_losers, "winners", None) or [])
    if not winners:
        return float(fallback)
    deltas = [float(getattr(item, "key_metric_delta", 0.0) or 0.0) for item in winners]
    if not deltas:
        return float(fallback)
    return float(sum(deltas) / max(len(deltas), 1))


def _distributional_shift_penalty(distributional_report: DistributionalReport | None) -> float:
    if distributional_report is None:
        return 0.0
    before = getattr(distributional_report, "overall_gini_before", None)
    after = getattr(distributional_report, "overall_gini_after", None)
    if before is None or after is None:
        return 0.0
    try:
        return max(0.0, float(after) - float(before))
    except (TypeError, ValueError):
        return 0.0


def _transport_penalty(cross_graph_profile: CrossGraphEvidenceProfile | None) -> float:
    if cross_graph_profile is None:
        return 0.0
    unsupported = sum(
        1
        for assessment in getattr(cross_graph_profile, "needs", None) or []
        if getattr(assessment, "transport_status", None) is TransportStatus.UNSUPPORTED
    )
    return min(0.25, unsupported * 0.05)


def _policy_budget_total(candidate: PolicyCandidateSchema) -> float:
    total = 0.0
    for allocation in candidate.budget_allocation:
        amount = getattr(allocation.amount, "amount", allocation.amount)
        try:
            total += float(amount)
        except (TypeError, ValueError):
            continue
    return total


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
