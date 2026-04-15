"""Typed judge stack and policy promotion coordinator for policy-mode search."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    DataReadinessReport,
    EstimationStatus,
    load_data_readiness_report,
    load_proof_bundle,
    persist_data_readiness_report,
)
from polisyos.ir.analytics.causal_discovery import LatentDiscoveryBundle
from polisyos.ir.analytics.cross_graph import CrossGraphEvidenceProfile, TransportStatus
from polisyos.ir.analytics.distributional import DistributionalReport
from polisyos.ir.analytics.partial_identification import load_bounds_bundle
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope as IRUncertaintyEnvelope
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.autotune.models import (
    BenchmarkEvaluation,
    ChampionPointer,
    PromotionDecision,
    PromotionPolicy,
)
from polisyos.scientist.discovery.priors import PriorKnowledgeBundle
from polisyos.scientist.engine.budget import BudgetState

# Governance pass implementations are lazy-imported via judge_passes to keep
# module-level cold-start time below the 15 s CI threshold.
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.replay.verification import (
    ReplayVerificationReport,
    load_replay_verification_report,
)
from polisyos.scientist.search.adversarial import PlatformMetaEvaluationReport
from polisyos.scientist.search.failure_cards import FailureSeverity, TypedFailureCard
from polisyos.scientist.search.funnel.orchestrator import FunnelOutcome
from polisyos.scientist.search.judge_passes import (
    load_benchmark_split_enum,
    load_governance_pass_factories,
    load_quality_gate_pass_type,
    load_reproducibility_pass_types,
    load_robustness_pass_types,
    load_transportability_required_pass_type,
)
from polisyos.scientist.search.judge_thresholds import (
    JudgeThresholdEntry,
    JudgeThresholdRegistry,
    JudgeThresholdSnapshot,
    ResolvedThresholdSet,
    ThresholdViolation,
    _check_threshold_violation,
)
from polisyos.scientist.search.latent_governance import (
    LatentGovernanceAssessment,
    assess_latent_governance,
)
from polisyos.scientist.search.readiness import (
    DecisionReadinessContract,
    DecisionReadinessEvaluator,
    persist_decision_readiness_contract,
)
from polisyos.scientist.search.registry_contracts import ChampionRegistryContract
from polisyos.scientist.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)

_STRICT_PROFILE = ValidationProfile.strict()
JUDGE_VERDICT_SCHEMA_NAME = "polisyos.scientist.search.JudgeVerdict"


class JudgeName(str, Enum):
    """Judge name public type."""
    STRUCTURAL = "structural"
    STATISTICAL = "statistical"
    ROBUSTNESS = "robustness"
    GOVERNANCE = "governance"
    REPRODUCIBILITY = "reproducibility"
    COMPUTE = "compute"


class SingleJudgeVerdict(BaseModel):
    """Verdict for one typed judge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    judge_name: str
    passed: bool
    is_fatal: bool
    failure_card: TypedFailureCard | None = None
    warnings: list[TypedFailureCard] = Field(default_factory=list)
    uncertainty_assessed: list[UncertaintyType] = Field(default_factory=list)
    evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)
    violations: list[str] = Field(default_factory=list)
    escalation_level: Literal["info", "warning", "error", "fatal"] = "info"
    threshold_scope: dict[str, str | None] = Field(default_factory=dict)
    threshold_registry_version: int | None = None


class JudgeVerdict(BaseModel):
    """Composite verdict over all judges."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    per_judge: dict[str, SingleJudgeVerdict]
    composite_decision: str
    blocking_failures: list[TypedFailureCard] = Field(default_factory=list)
    warnings: list[TypedFailureCard] = Field(default_factory=list)
    audit_log_ref: ArtifactRef | None = None

    @property
    def is_promotable(self) -> bool:
        fatal_ok = all(
            verdict.passed for verdict in self.per_judge.values() if verdict.is_fatal
        )
        return fatal_ok and self.composite_decision == "promote"


def persist_judge_verdict(
    store: FileSystemCAS,
    verdict: JudgeVerdict,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist judge verdict helper."""
    return store.put_json(
        verdict,
        PutOptions(
            kind="scientist.judge_verdict",
            media_type="application/json",
            schema=SchemaInfo(name=JUDGE_VERDICT_SCHEMA_NAME, version="1.0"),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_judge_verdict(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> JudgeVerdict:
    """Load judge verdict."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return JudgeVerdict.model_validate(payload)


class JudgeInputBundle(BaseModel):
    """Inputs required to evaluate the typed judge stack."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    candidate: PolicyCandidateSchema
    trinity_bundle: TrinityBundle | None = None
    evaluation_vector: PolicyEvaluationVector | None = None
    funnel_outcome: FunnelOutcome | None = None
    benchmark_evaluation: BenchmarkEvaluation | None = None
    hidden_holdout_evaluation: BenchmarkEvaluation | None = None
    platform_meta_evaluation_report: PlatformMetaEvaluationReport | None = None
    distributional_report: DistributionalReport | None = None
    causal_effect_report: CausalEffectReport | None = None
    data_readiness_report: DataReadinessReport | None = None
    data_readiness_report_ref: ArtifactRef | None = None
    artifact_family: str = "causal_core"
    claim_mode: Literal["proof_only", "bounds", "estimation"] = "estimation"
    query_type: str | None = None
    estimator_name: str | None = None
    readiness_target: str | None = None
    proof_bundle_ref: ArtifactRef | None = None
    bounds_bundle_ref: ArtifactRef | None = None
    negative_certificate_ref: ArtifactRef | None = None
    replay_bundle_ref: ArtifactRef | None = None
    replay_verification_ref: ArtifactRef | None = None
    replay_verification_report: ReplayVerificationReport | None = None
    promotion_evidence_bundle_ref: ArtifactRef | None = None
    cross_graph_profile: CrossGraphEvidenceProfile | None = None
    prior_knowledge_bundle: PriorKnowledgeBundle | None = None
    governance_report: GovernanceReport | None = None
    latent_discovery_bundle: LatentDiscoveryBundle | None = None
    latent_discovery_resolution_error: dict[str, Any] | None = None
    uncertainty_envelope: UncertaintyEnvelope | IRUncertaintyEnvelope | None = None
    budget_state: BudgetState | None = None
    candidate_ref: ArtifactRef | None = None
    evaluation_ref: ArtifactRef | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    registry_bundle: object | None = None
    voi_scheduler: object | None = None
    run_id: str = Field(default="policy_judge", min_length=1)
    expected_improvement: float | None = None
    timeout_risk: float | None = None
    replay_cost_usd: float | None = None
    compute_cost_usd: float | None = None
    allow_compute_override: bool = False
    evaluation_backend_kind: str | None = None
    evaluation_fidelity_mode: str | None = None
    evaluation_promotable_source: bool = True
    evaluation_degradation_mode: str | None = None
    evaluation_provenance_notes: list[str] = Field(default_factory=list)

    def resolved_trinity_bundle(self) -> TrinityBundle:
        return self.trinity_bundle or self.candidate.trinity_bundle

    def latent_governance_assessment(self) -> LatentGovernanceAssessment | None:
        return assess_latent_governance(self.latent_discovery_bundle)

    def effective_claim_mode(self) -> Literal["proof_only", "bounds", "estimation"]:
        if (
            self.latent_discovery_bundle is not None
            or isinstance(self.latent_discovery_resolution_error, dict)
        ):
            return "proof_only"
        return self.claim_mode

    def effective_evaluation_degradation_mode(self) -> str | None:
        if isinstance(self.latent_discovery_resolution_error, dict):
            return "research_only"
        assessment = self.latent_governance_assessment()
        if assessment is not None:
            return assessment.degradation_mode
        return self.evaluation_degradation_mode

    def build_state(self) -> dict[str, Any]:
        state = dict(self.state)
        state.setdefault("policy_candidate_id", self.candidate.candidate_id)
        if self.causal_effect_report is not None:
            state.setdefault("causal_report", self.causal_effect_report)
        if self.data_readiness_report is not None:
            state.setdefault("data_readiness_report", self.data_readiness_report)
        if self.data_readiness_report_ref is not None:
            state.setdefault(
                "data_readiness_report_ref",
                self.data_readiness_report_ref.model_dump(mode="json"),
            )
        if self.proof_bundle_ref is not None:
            state.setdefault("proof_bundle_ref", self.proof_bundle_ref.model_dump(mode="json"))
        if self.bounds_bundle_ref is not None:
            state.setdefault("bounds_bundle_ref", self.bounds_bundle_ref.model_dump(mode="json"))
        if self.negative_certificate_ref is not None:
            state.setdefault(
                "negative_certificate_ref",
                self.negative_certificate_ref.model_dump(mode="json"),
            )
        if self.replay_bundle_ref is not None:
            state.setdefault(
                "replay_bundle_ref",
                self.replay_bundle_ref.model_dump(mode="json"),
            )
        if self.replay_verification_ref is not None:
            state.setdefault(
                "replay_verification_ref",
                self.replay_verification_ref.model_dump(mode="json"),
            )
        if self.promotion_evidence_bundle_ref is not None:
            state.setdefault(
                "promotion_evidence_bundle_ref",
                self.promotion_evidence_bundle_ref.model_dump(mode="json"),
            )
        if self.distributional_report is not None:
            state.setdefault("distributional_report", self.distributional_report)
        if self.governance_report is not None:
            state.setdefault("governance_report", self.governance_report)
        if self.latent_discovery_bundle is not None:
            state.setdefault(
                "latent_discovery_bundle",
                self.latent_discovery_bundle.model_dump(mode="json"),
            )
        if self.latent_discovery_resolution_error is not None:
            state.setdefault(
                "latent_discovery_resolution_error",
                dict(self.latent_discovery_resolution_error),
            )
        latent_governance = self.latent_governance_assessment()
        if latent_governance is not None:
            state.setdefault("latent_governance", latent_governance.model_dump(mode="json"))
        if self.benchmark_evaluation is not None:
            state.setdefault("benchmark_evaluation", self.benchmark_evaluation)
        if self.hidden_holdout_evaluation is not None:
            state.setdefault("hidden_holdout_evaluation", self.hidden_holdout_evaluation)
        if self.platform_meta_evaluation_report is not None:
            state.setdefault(
                "platform_meta_evaluation_report",
                self.platform_meta_evaluation_report,
            )
        if self.cross_graph_profile is not None:
            state.setdefault("cross_graph_profile", self.cross_graph_profile)
        if self.prior_knowledge_bundle is not None:
            state.setdefault(
                "prior_knowledge_bundle",
                self.prior_knowledge_bundle.model_dump(mode="json"),
            )
        if self.funnel_outcome is not None:
            state.setdefault("funnel_outcome", self.funnel_outcome)
        state.setdefault(
            "evaluation_provenance",
            {
                "backend_kind": self.evaluation_backend_kind,
                "fidelity_mode": self.evaluation_fidelity_mode,
                "promotable_source": self.evaluation_promotable_source,
                "degradation_mode": self.effective_evaluation_degradation_mode(),
                "notes": list(self.evaluation_provenance_notes),
            },
        )
        state.setdefault(
            "judge_scope",
            {
                "artifact_family": self.artifact_family,
                "claim_mode": self.effective_claim_mode(),
                "query_type": self.query_type,
                "estimator_name": self.estimator_name,
                "readiness_target": self.readiness_target,
            },
        )
        return state

    def build_pass_context(self, pass_ids: Iterable[str]) -> PassContext:
        profile = ValidationProfile(
            level=_STRICT_PROFILE.level,
            pass_ids=frozenset(pass_ids),
            thresholds=dict(_STRICT_PROFILE.thresholds),
            short_circuit_on_blocker=False,
        )
        return PassContext(
            ir=self.resolved_trinity_bundle(),
            state=self.build_state(),
            registry_bundle=self.registry_bundle,
            profile=profile,
            run_id=self.run_id,
        )

    def search_uncertainty(self) -> UncertaintyEnvelope:
        return to_search_uncertainty_envelope(
            self.uncertainty_envelope,
            causal_effect_report=self.causal_effect_report,
            cross_graph_profile=self.cross_graph_profile,
        )


class JudgeStack:
    """Composite typed judge with explicit per-judge composition."""

    def __init__(
        self,
        *,
        threshold_registry: JudgeThresholdRegistry | None = None,
        store: FileSystemCAS | None = None,
    ) -> None:
        self._threshold_registry = threshold_registry or JudgeThresholdRegistry()
        self._store = store
        self._threshold_registry.seed_defaults()

    def evaluate(
        self,
        bundle: JudgeInputBundle,
        *,
        active_judges: Iterable[JudgeName] | None = None,
    ) -> JudgeVerdict:
        explicit_active_judges = active_judges is not None
        requested = set(active_judges or _default_active_judges(bundle))
        per_judge: dict[str, SingleJudgeVerdict] = {}

        for judge_name in JudgeName:
            if judge_name not in requested:
                per_judge[judge_name.value] = (
                    _unavailable_judge_verdict(judge_name)
                    if explicit_active_judges
                    else _inactive_judge_verdict(judge_name)
                )
                continue
            per_judge[judge_name.value] = self._evaluate_single(judge_name, bundle)

        blocking_failures: list[TypedFailureCard] = []
        warnings: list[TypedFailureCard] = []
        for verdict in per_judge.values():
            if verdict.failure_card is not None and verdict.is_fatal and not verdict.passed:
                blocking_failures.append(verdict.failure_card)
            warnings.extend(verdict.warnings)

        if any(
            card.failure_type == "human_gate_required" for card in blocking_failures + warnings
        ):
            composite = "defer_to_human"
        elif any(not verdict.passed and verdict.is_fatal for verdict in per_judge.values()):
            composite = "reject"
        else:
            composite = "promote"

        return JudgeVerdict(
            per_judge=per_judge,
            composite_decision=composite,
            blocking_failures=blocking_failures,
            warnings=warnings,
        )

    def _evaluate_single(
        self,
        judge_name: JudgeName,
        bundle: JudgeInputBundle,
    ) -> SingleJudgeVerdict:
        if judge_name is JudgeName.STRUCTURAL:
            return self._structural(bundle)
        if judge_name is JudgeName.STATISTICAL:
            return self._statistical(bundle)
        if judge_name is JudgeName.ROBUSTNESS:
            return self._robustness(bundle)
        if judge_name is JudgeName.GOVERNANCE:
            return self._governance(bundle)
        if judge_name is JudgeName.REPRODUCIBILITY:
            return self._reproducibility(bundle)
        return self._compute(bundle)

    def _resolved_thresholds(
        self,
        judge_name: JudgeName,
        bundle: JudgeInputBundle,
    ) -> ResolvedThresholdSet:
        return self._threshold_registry.resolve(
            judge_name.value,
            family=bundle.artifact_family,
            query_type=bundle.query_type,
            estimator=bundle.estimator_name,
            readiness_target=bundle.readiness_target,
        )

    def _structural(self, bundle: JudgeInputBundle) -> SingleJudgeVerdict:
        evidence_refs = _evidence_refs(bundle)
        cards: list[TypedFailureCard] = []
        warnings: list[TypedFailureCard] = []
        metrics: dict[str, float] = {}
        resolved = self._resolved_thresholds(JudgeName.STRUCTURAL, bundle)
        report = bundle.causal_effect_report
        if bundle.effective_claim_mode() == "estimation" and report is None:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.STRUCTURAL.value,
                    failure_type="missing_causal_effect_report",
                    severity=FailureSeverity.BLOCKER,
                    description="StructuralJudge requires a CausalEffectReport.",
                    uncertainty_type=UncertaintyType.STRUCTURAL,
                )
            )
        elif report is not None and report.status is not EstimationStatus.SUCCESS:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.STRUCTURAL.value,
                    failure_type="identifiability_failed",
                    severity=FailureSeverity.BLOCKER,
                    description=(
                        f"Causal estimation status is '{report.status.value}', so structural "
                        "validity is not promotion-safe."
                    ),
                    uncertainty_type=UncertaintyType.STRUCTURAL,
                )
            )
        elif report is not None:
            metrics["proof_precondition_coverage"] = 1.0

        if self._store is not None and bundle.proof_bundle_ref is not None:
            proof_bundle = load_proof_bundle(self._store, bundle.proof_bundle_ref)
            proof_coverage = 1.0 if proof_bundle.completeness_regime == "complete" else 0.5
            if proof_bundle.proof_status != "identified":
                proof_coverage = min(proof_coverage, 0.5)
            metrics["proof_precondition_coverage"] = proof_coverage
            violation = _check_threshold_violation(
                resolved,
                metric_name="proof_precondition_coverage",
                observed_value=proof_coverage,
            )
            if violation is not None:
                cards.append(
                    _threshold_failure_card(
                        judge_name=JudgeName.STRUCTURAL.value,
                        failure_type="proof_precondition_coverage_below_threshold",
                        description=(
                            "Proof artifact does not meet the minimum structural coverage threshold."
                        ),
                        uncertainty_type=UncertaintyType.STRUCTURAL,
                        violation=violation,
                    )
                )

        if self._store is not None and bundle.bounds_bundle_ref is not None:
            bounds_bundle = load_bounds_bundle(self._store, bundle.bounds_bundle_ref)
            lower = bounds_bundle.lower_bound
            upper = bounds_bundle.upper_bound
            gap = 0.0
            if lower is not None and upper is not None and lower > upper:
                gap = float(lower - upper)
            metrics["bounds_consistency_gap"] = gap
            violation = _check_threshold_violation(
                resolved,
                metric_name="bounds_consistency_gap",
                observed_value=gap,
            )
            if violation is not None:
                cards.append(
                    _threshold_failure_card(
                        judge_name=JudgeName.STRUCTURAL.value,
                        failure_type="bounds_inconsistent",
                        description="Bounds artifact violates the lower <= upper invariant.",
                        uncertainty_type=UncertaintyType.STRUCTURAL,
                        violation=violation,
                    )
                )

        if bundle.funnel_outcome is not None:
            for card in bundle.funnel_outcome.failure_cards:
                if card.uncertainty_type is UncertaintyType.STRUCTURAL:
                    cards.append(card)

        if bundle.cross_graph_profile is not None:
            unsupported = [
                assessment.need.need_id
                for assessment in bundle.cross_graph_profile.needs
                if assessment.transport_status is TransportStatus.UNSUPPORTED
            ]
            if unsupported:
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.STRUCTURAL.value,
                        failure_type="structural_transport_gap",
                        severity=FailureSeverity.BLOCKER,
                        description=(
                            "StructuralJudge found unsupported evidence needs: "
                            + ", ".join(sorted(unsupported))
                        ),
                        uncertainty_type=UncertaintyType.STRUCTURAL,
                    )
                )

        return _judge_result(
            judge_name=JudgeName.STRUCTURAL,
            fatal=True,
            cards=cards,
            warnings=warnings,
            uncertainty_assessed=[UncertaintyType.STRUCTURAL],
            evidence_refs=evidence_refs,
            resolved_thresholds=resolved,
            metrics=metrics,
        )

    def _statistical(self, bundle: JudgeInputBundle) -> SingleJudgeVerdict:
        evidence_refs = _evidence_refs(bundle)
        cards: list[TypedFailureCard] = []
        warnings: list[TypedFailureCard] = []
        metrics: dict[str, float] = {}
        resolved = self._resolved_thresholds(JudgeName.STATISTICAL, bundle)
        uncertainty = bundle.search_uncertainty()
        statistical_level = uncertainty.uncertainties[UncertaintyType.STATISTICAL].level
        metrics["statistical_uncertainty_level"] = statistical_level
        violation = _check_threshold_violation(
            resolved,
            metric_name="statistical_uncertainty_level",
            observed_value=statistical_level,
        )
        if violation is not None:
            cards.append(
                _threshold_failure_card(
                    judge_name=JudgeName.STATISTICAL.value,
                    failure_type="statistical_uncertainty_high",
                    description="Statistical uncertainty exceeds the promotion-safe threshold.",
                    uncertainty_type=UncertaintyType.STATISTICAL,
                    violation=violation,
                )
            )

        report = bundle.data_readiness_report
        if (
            report is None
            and self._store is not None
            and bundle.data_readiness_report_ref is not None
        ):
            report = load_data_readiness_report(
                self._store,
                bundle.data_readiness_report_ref,
            )
        if bundle.effective_claim_mode() in {"bounds", "estimation"} and report is None:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.STATISTICAL.value,
                    failure_type="data_readiness_missing",
                    severity=FailureSeverity.BLOCKER,
                    description=(
                        "DataReadinessReport is required for bounds and estimation promotion."
                    ),
                    uncertainty_type=UncertaintyType.STATISTICAL,
                )
            )
        elif report is not None:
            if report.sample_size is not None:
                metrics["sample_size"] = float(report.sample_size)
            if report.positivity is not None:
                metrics["ess_fraction"] = float(report.positivity.ess_fraction)
                metrics["overlap_score"] = float(report.positivity.overlap_score)
            if bundle.effective_claim_mode() in {"bounds", "estimation"} and report.decision in {"block", "unknown"}:
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.STATISTICAL.value,
                        failure_type="data_readiness_blocked",
                        severity=FailureSeverity.BLOCKER,
                        description=(
                            f"Data readiness decision '{report.decision}' is not promotion-safe."
                        ),
                        uncertainty_type=UncertaintyType.STATISTICAL,
                        metadata={
                            "blocking_reasons": list(report.blocking_reasons),
                            "warnings": list(report.warnings),
                        },
                    )
                )
            elif bundle.effective_claim_mode() in {"bounds", "estimation"} and report.decision == "warn":
                warnings.append(
                    TypedFailureCard(
                        judge_name=JudgeName.STATISTICAL.value,
                        failure_type="data_readiness_warn",
                        severity=FailureSeverity.WARNING,
                        description="Data readiness is warning-capped for promotion.",
                        uncertainty_type=UncertaintyType.STATISTICAL,
                        metadata={"warnings": list(report.warnings)},
                    )
                )

        benchmark = bundle.benchmark_evaluation
        if bundle.effective_claim_mode() != "proof_only" and benchmark is None:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.STATISTICAL.value,
                    failure_type="missing_benchmark_evaluation",
                    severity=FailureSeverity.BLOCKER,
                    description="StatisticalJudge requires BenchmarkEvaluation inputs.",
                    uncertainty_type=UncertaintyType.STATISTICAL,
                )
            )
        else:
            if benchmark is not None:
                metrics["selection_sample_count"] = float(
                    benchmark.sample_count(split=benchmark_split("selection"))
                )
            if benchmark is not None and benchmark.sample_count(split=benchmark_split("selection")) <= 0:
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.STATISTICAL.value,
                        failure_type="selection_samples_missing",
                        severity=FailureSeverity.BLOCKER,
                        description="Selection benchmark split has no samples.",
                        uncertainty_type=UncertaintyType.STATISTICAL,
                    )
                )
            if (
                bundle.causal_effect_report is not None
                and bundle.causal_effect_report.sample_size < 30
            ):
                warnings.append(
                    TypedFailureCard(
                        judge_name=JudgeName.STATISTICAL.value,
                        failure_type="sample_adequacy_warning",
                        severity=FailureSeverity.WARNING,
                        description="Sample size is below 30; estimates may be unstable.",
                        uncertainty_type=UncertaintyType.STATISTICAL,
                    )
                )

        quality_state = bundle.build_state()
        if "data_quality_report" in quality_state or "evidence_bundle" in quality_state:
            pass_context = bundle.build_pass_context({"quality"})
            quality_gate_pass_type = load_quality_gate_pass_type()
            issues = quality_gate_pass_type(force_run=True).validate(pass_context)
            for issue in issues:
                card = compliance_issue_to_failure_card(
                    issue,
                    judge_name=JudgeName.STATISTICAL.value,
                )
                if card.is_blocker:
                    cards.append(card)
                else:
                    warnings.append(card)

        return _judge_result(
            judge_name=JudgeName.STATISTICAL,
            fatal=True,
            cards=cards,
            warnings=warnings,
            uncertainty_assessed=[
                UncertaintyType.STATISTICAL,
                UncertaintyType.MEASUREMENT,
            ],
            evidence_refs=evidence_refs,
            resolved_thresholds=resolved,
            metrics=metrics,
        )

    def _robustness(self, bundle: JudgeInputBundle) -> SingleJudgeVerdict:
        evidence_refs = _evidence_refs(bundle)
        cards: list[TypedFailureCard] = []
        warnings: list[TypedFailureCard] = []
        metrics: dict[str, float] = {}
        resolved = self._resolved_thresholds(JudgeName.ROBUSTNESS, bundle)
        if bundle.causal_effect_report is None:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.ROBUSTNESS.value,
                    failure_type="missing_causal_effect_report",
                    severity=FailureSeverity.BLOCKER,
                    description="RobustnessJudge requires a CausalEffectReport.",
                    uncertainty_type=UncertaintyType.MODEL,
                )
            )
        else:
            pass_context = bundle.build_pass_context({"refutation", "sutva_check"})
            refutation_pass_type, sutva_check_pass_type = load_robustness_pass_types()
            for validator in (refutation_pass_type(), sutva_check_pass_type()):
                for issue in validator.validate(pass_context):
                    card = compliance_issue_to_failure_card(
                        issue,
                        judge_name=JudgeName.ROBUSTNESS.value,
                    )
                    if card.is_blocker:
                        cards.append(card)
                    else:
                        warnings.append(card)

            if bundle.cross_graph_profile is not None:
                for assessment in bundle.cross_graph_profile.needs:
                    if assessment.transport_status is TransportStatus.UNSUPPORTED:
                        cards.append(
                            TypedFailureCard(
                                judge_name=JudgeName.ROBUSTNESS.value,
                                failure_type="transportability_required",
                                severity=FailureSeverity.BLOCKER,
                                description=(
                                    "Cross-graph evidence marks transport as unsupported for "
                                    f"need '{assessment.need.need_id}'."
                                ),
                                uncertainty_type=UncertaintyType.TRANSPORT,
                            )
                        )
            else:
                pass_context = bundle.build_pass_context({"transportability_required"})
                transportability_required_pass_type = (
                    load_transportability_required_pass_type()
                )
                for issue in transportability_required_pass_type().validate(pass_context):
                    card = compliance_issue_to_failure_card(
                        issue,
                        judge_name=JudgeName.ROBUSTNESS.value,
                    )
                    if card.is_blocker:
                        cards.append(card)
                    else:
                        warnings.append(card)

        hidden_holdout_delta = _hidden_holdout_degradation_value(bundle)
        if hidden_holdout_delta is not None:
            metrics["hidden_holdout_degradation"] = hidden_holdout_delta
        hidden_holdout_card = _hidden_holdout_degradation_card_with_threshold(
            bundle,
            resolved,
        )
        if hidden_holdout_card is not None:
            cards.append(hidden_holdout_card)
        platform_meta_card = _platform_meta_evaluation_card(bundle)
        if platform_meta_card is not None:
            cards.append(platform_meta_card)
        if bundle.platform_meta_evaluation_report is not None:
            metrics["adversarial_guard_trigger_count"] = float(
                len(bundle.platform_meta_evaluation_report.triggered_guards)
            )

        return _judge_result(
            judge_name=JudgeName.ROBUSTNESS,
            fatal=True,
            cards=cards,
            warnings=warnings,
            uncertainty_assessed=[
                UncertaintyType.MODEL,
                UncertaintyType.TRANSPORT,
            ],
            evidence_refs=evidence_refs,
            resolved_thresholds=resolved,
            metrics=metrics,
        )

    def _governance(self, bundle: JudgeInputBundle) -> SingleJudgeVerdict:
        evidence_refs = _evidence_refs(bundle)
        cards: list[TypedFailureCard] = []
        warnings: list[TypedFailureCard] = []
        latent_governance = bundle.latent_governance_assessment()
        pass_context = bundle.build_pass_context(
            {"budget", "equity", "privacy", "pii_check", "human_review_required", "legal"}
        )
        for pass_factory in load_governance_pass_factories():
            validator = pass_factory()
            for issue in validator.validate(pass_context):
                card = compliance_issue_to_failure_card(
                    issue,
                    judge_name=JudgeName.GOVERNANCE.value,
                )
                if card.failure_type == "HUMAN_REVIEW_REQUESTED":
                    cards.append(
                        card.model_copy(
                            update={
                                "severity": FailureSeverity.BLOCKER,
                                "failure_type": "human_gate_required",
                            }
                        )
                    )
                    continue
                if card.is_blocker:
                    cards.append(card)
                else:
                    warnings.append(card)

        report = bundle.governance_report
        if report is None:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.GOVERNANCE.value,
                    failure_type="missing_governance_report",
                    severity=FailureSeverity.BLOCKER,
                    description="GovernanceJudge requires GovernanceReport or equivalent pass state.",
                )
            )
        else:
            verdict = str(report.verdict).strip().lower()
            if verdict == "reject":
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.GOVERNANCE.value,
                        failure_type="governance_reject",
                        severity=FailureSeverity.BLOCKER,
                        description="GovernanceReport verdict is reject.",
                    )
                )
            elif verdict == "human_gate":
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.GOVERNANCE.value,
                        failure_type="human_gate_required",
                        severity=FailureSeverity.BLOCKER,
                        description="GovernanceReport requires human review before promotion.",
                    )
                )

        if isinstance(bundle.latent_discovery_resolution_error, dict):
            error_code = str(
                bundle.latent_discovery_resolution_error.get("error_code")
                or "latent_discovery_bundle_unreadable"
            ).strip() or "latent_discovery_bundle_unreadable"
            error_message = str(
                bundle.latent_discovery_resolution_error.get("error_message")
                or "Latent discovery bundle could not be loaded."
            ).strip() or "Latent discovery bundle could not be loaded."
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.GOVERNANCE.value,
                    failure_type="latent_discovery_bundle_unreadable",
                    severity=FailureSeverity.BLOCKER,
                    description=(
                        "Latent discovery bundle could not be loaded, so proof-only constraints "
                        "cannot be verified."
                    ),
                    remediation_hint=(
                        "Restore the discovery artifact bundle or clear the broken latent "
                        "discovery reference before promotion."
                    ),
                    metadata={
                        "error_code": error_code,
                        "error_message": error_message,
                        **dict(bundle.latent_discovery_resolution_error),
                    },
                )
            )

        if latent_governance is not None:
            if latent_governance.missing_requirements:
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.GOVERNANCE.value,
                        failure_type="latent_discovery_bundle_incomplete",
                        severity=FailureSeverity.BLOCKER,
                        description=(
                            "Latent discovery bundle is missing required governance fields: "
                            + ", ".join(latent_governance.missing_requirements)
                        ),
                        remediation_hint=(
                            "Provide assumption cards, inducing environments, "
                            "identification conditions, falsification tests, and disclosure flags."
                        ),
                        metadata={"missing_requirements": latent_governance.missing_requirements},
                    )
                )
            else:
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.GOVERNANCE.value,
                        failure_type="human_gate_required",
                        severity=FailureSeverity.BLOCKER,
                        description=(
                            "Latent discovery artifacts remain research-only and require human review."
                        ),
                        remediation_hint="Keep the artifact in proof-only mode and route through a human gate.",
                        metadata={
                            "no_promotion_reasons": latent_governance.no_promotion_reasons,
                            "not_for_decision_support": latent_governance.not_for_decision_support,
                        },
                    )
                )

        return _judge_result(
            judge_name=JudgeName.GOVERNANCE,
            fatal=True,
            cards=cards,
            warnings=warnings,
            uncertainty_assessed=[
                UncertaintyType.STRUCTURAL,
                UncertaintyType.TRANSPORT,
            ],
            evidence_refs=evidence_refs,
        )

    def _reproducibility(self, bundle: JudgeInputBundle) -> SingleJudgeVerdict:
        evidence_refs = _evidence_refs(bundle)
        cards: list[TypedFailureCard] = []
        warnings: list[TypedFailureCard] = []
        metrics: dict[str, float] = {}
        resolved = self._resolved_thresholds(JudgeName.REPRODUCIBILITY, bundle)
        state = bundle.build_state()
        if (
            "checkpoints" not in state
            and "verified_claims" not in state
            and "data_sources" not in state
            and "knowledge_metadata" not in state
        ):
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.REPRODUCIBILITY.value,
                    failure_type="missing_reproducibility_inputs",
                    severity=FailureSeverity.BLOCKER,
                    description=(
                        "ReproducibilityJudge requires checkpoints, citations, or freshness "
                        "metadata; none were provided."
                    ),
                )
            )
        pass_context = bundle.build_pass_context({"checkpoint", "citation_validator", "freshness"})
        checkpoint_pass_type, citation_validator_pass_type, freshness_pass_type = (
            load_reproducibility_pass_types()
        )
        for validator in (
            checkpoint_pass_type(),
            citation_validator_pass_type(),
            freshness_pass_type(),
        ):
            for issue in validator.validate(pass_context):
                card = compliance_issue_to_failure_card(
                    issue,
                    judge_name=JudgeName.REPRODUCIBILITY.value,
                )
                if card.is_blocker:
                    cards.append(card)
                else:
                    warnings.append(card)

        lineage_ok = state.get("audit_lineage_complete")
        metrics["lineage_complete"] = 0.0 if lineage_ok is False else 1.0
        if lineage_ok is False:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.REPRODUCIBILITY.value,
                    failure_type="lineage_incomplete",
                    severity=FailureSeverity.BLOCKER,
                    description="Audit lineage is incomplete.",
                )
            )
        if bundle.candidate_ref is None or bundle.evaluation_ref is None:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.REPRODUCIBILITY.value,
                    failure_type="artifact_refs_incomplete",
                    severity=FailureSeverity.BLOCKER,
                    description="Candidate/evaluation artifact refs are required for replayable audit.",
                )
            )
        if bundle.replay_bundle_ref is None:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.REPRODUCIBILITY.value,
                    failure_type="replay_bundle_missing",
                    severity=FailureSeverity.BLOCKER,
                    description="Replay bundle is required for promotion-grade reproducibility.",
                )
            )

        verification_report = bundle.replay_verification_report
        if (
            verification_report is None
            and self._store is not None
            and bundle.replay_verification_ref is not None
        ):
            verification_report = load_replay_verification_report(
                self._store,
                bundle.replay_verification_ref,
            )

        if bundle.effective_claim_mode() in {"bounds", "estimation"} and verification_report is None:
            cards.append(
                TypedFailureCard(
                    judge_name=JudgeName.REPRODUCIBILITY.value,
                    failure_type="replay_verification_missing",
                    severity=FailureSeverity.BLOCKER,
                    description=(
                        "Replay verification report is required for bounds and estimation promotion."
                    ),
                )
            )
        elif verification_report is not None:
            metrics["replay_match"] = float(verification_report.overall_similarity)
            metrics["replay_complete"] = 1.0 if verification_report.is_complete else 0.0
            if (
                bundle.effective_claim_mode() in {"bounds", "estimation"}
                and str(verification_report.verification_mode).strip().lower()
                in {"bundle_integrity", "artifact_snapshot", "skip"}
            ):
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.REPRODUCIBILITY.value,
                        failure_type="replay_verification_unmeasured",
                        severity=FailureSeverity.BLOCKER,
                        description=(
                            "Replay verification must be a measured rerun for bounds and estimation promotion."
                        ),
                        metadata={"verification_mode": verification_report.verification_mode},
                    )
                )
            if not verification_report.is_complete:
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.REPRODUCIBILITY.value,
                        failure_type="replay_incomplete",
                        severity=FailureSeverity.BLOCKER,
                        description="Replay verification marked the replay bundle incomplete.",
                        metric_name="replay_complete",
                        observed_value=metrics["replay_complete"],
                        threshold_value=1.0,
                        threshold_direction="min",
                        metadata={"reason_codes": list(verification_report.reason_codes)},
                    )
                )
            replay_violation = _check_threshold_violation(
                resolved,
                metric_name="replay_match",
                observed_value=metrics["replay_match"],
            )
            if replay_violation is not None:
                cards.append(
                    _threshold_failure_card(
                        judge_name=JudgeName.REPRODUCIBILITY.value,
                        failure_type="replay_match_below_threshold",
                        description="Replay similarity is below the promotion-safe threshold.",
                        violation=replay_violation,
                    )
                )
            if not verification_report.passed:
                cards.append(
                    TypedFailureCard(
                        judge_name=JudgeName.REPRODUCIBILITY.value,
                        failure_type="replay_verification_failed",
                        severity=FailureSeverity.BLOCKER,
                        description="Replay verification reported a failed verdict.",
                        metric_name="replay_match",
                        observed_value=float(verification_report.overall_similarity),
                        threshold_value=resolved.threshold_value("replay_match"),
                        threshold_direction="min",
                        metadata={"reason_codes": list(verification_report.reason_codes)},
                    )
                )

        return _judge_result(
            judge_name=JudgeName.REPRODUCIBILITY,
            fatal=True,
            cards=cards,
            warnings=warnings,
            uncertainty_assessed=[UncertaintyType.OPTIMIZATION],
            evidence_refs=evidence_refs,
            resolved_thresholds=resolved,
            metrics=metrics,
        )

    def _compute(self, bundle: JudgeInputBundle) -> SingleJudgeVerdict:
        evidence_refs = _evidence_refs(bundle)
        warnings: list[TypedFailureCard] = []
        metrics: dict[str, float] = {}
        resolved = self._resolved_thresholds(JudgeName.COMPUTE, bundle)

        if bundle.budget_state is None and bundle.compute_cost_usd is None:
            warnings.append(
                TypedFailureCard(
                    judge_name=JudgeName.COMPUTE.value,
                    failure_type="missing_compute_inputs",
                    severity=FailureSeverity.WARNING,
                    description=(
                        "ComputeJudge did not receive BudgetState or compute-cost metadata; "
                        "treating this as an observability gap instead of a promotion blocker."
                    ),
                )
            )
            return _judge_result(
                judge_name=JudgeName.COMPUTE,
                fatal=False,
                cards=[],
                warnings=warnings,
                uncertainty_assessed=[],
                evidence_refs=evidence_refs,
                resolved_thresholds=resolved,
                metrics=metrics,
            )

        if bundle.budget_state is not None and bundle.compute_cost_usd is not None:
            estimated_cost = Decimal(str(bundle.compute_cost_usd))
            if bundle.budget_state.would_exceed("run", estimated_cost):
                warnings.append(
                    TypedFailureCard(
                        judge_name=JudgeName.COMPUTE.value,
                        failure_type="compute_budget_exceeded",
                        severity=FailureSeverity.WARNING,
                        description="Compute cost would exceed run budget.",
                    )
                )

        if bundle.timeout_risk is not None:
            metrics["timeout_risk"] = float(bundle.timeout_risk)
            violation = _check_threshold_violation(
                resolved,
                metric_name="timeout_risk",
                observed_value=float(bundle.timeout_risk),
            )
            if violation is not None:
                warnings.append(
                    _threshold_failure_card(
                        judge_name=JudgeName.COMPUTE.value,
                        failure_type="timeout_risk_high",
                        description="Timeout risk exceeds the configured compute threshold.",
                        severity=FailureSeverity.WARNING,
                        violation=violation,
                    )
                )

        if (
            bundle.expected_improvement is not None
            and bundle.compute_cost_usd not in {None, 0.0}
        ):
            cost_efficiency = bundle.expected_improvement / max(bundle.compute_cost_usd or 0.0, 1e-9)
            metrics["cost_efficiency"] = float(cost_efficiency)
            violation = _check_threshold_violation(
                resolved,
                metric_name="cost_efficiency",
                observed_value=float(cost_efficiency),
            )
            if violation is not None:
                warnings.append(
                    _threshold_failure_card(
                        judge_name=JudgeName.COMPUTE.value,
                        failure_type="cost_efficiency_low",
                        description="Expected improvement per USD is below the configured threshold.",
                        severity=FailureSeverity.WARNING,
                        violation=violation,
                    )
                )

        if bundle.replay_cost_usd is not None and bundle.compute_cost_usd is not None:
            replay_ratio = bundle.replay_cost_usd / max(bundle.compute_cost_usd, 1e-9)
            metrics["replay_cost_ratio"] = float(replay_ratio)
            violation = _check_threshold_violation(
                resolved,
                metric_name="replay_cost_ratio",
                observed_value=float(replay_ratio),
            )
            if violation is not None:
                warnings.append(
                    _threshold_failure_card(
                        judge_name=JudgeName.COMPUTE.value,
                        failure_type="replay_cost_high",
                        description="Replay cost materially exceeds the configured ratio threshold.",
                        severity=FailureSeverity.WARNING,
                        violation=violation,
                    )
                )

        return _judge_result(
            judge_name=JudgeName.COMPUTE,
            fatal=False,
            cards=[],
            warnings=warnings,
            uncertainty_assessed=[],
            evidence_refs=evidence_refs,
            resolved_thresholds=resolved,
            metrics=metrics,
        )


class PolicyPromotionResult(BaseModel):
    """Coordinator output for one promotion attempt."""

    model_config = ConfigDict(extra="forbid")

    judge_verdict: JudgeVerdict
    judge_verdict_ref: ArtifactRef | None = None
    readiness_contract: DecisionReadinessContract
    readiness_ref: ArtifactRef | None = None
    promotion_decision: PromotionDecision


class PolicyPromotionCoordinator:
    """Runs judge stack, readiness evaluation, and champion promotion in order."""

    def __init__(
        self,
        *,
        champion_registry: ChampionRegistryContract,
        store,
        judge_stack: JudgeStack | None = None,
        readiness_evaluator: DecisionReadinessEvaluator | None = None,
    ) -> None:
        self._champion_registry = champion_registry
        self._store = store
        self._judge_stack = judge_stack or JudgeStack(store=store)
        self._readiness_evaluator = readiness_evaluator or DecisionReadinessEvaluator(
            store=store
        )

    def build_input_bundle(
        self,
        *,
        candidate: PolicyCandidateSchema,
        funnel_outcome: FunnelOutcome | None = None,
        benchmark_evaluation: BenchmarkEvaluation | None = None,
        hidden_holdout_evaluation: BenchmarkEvaluation | None = None,
        platform_meta_evaluation_report: PlatformMetaEvaluationReport | None = None,
        evaluation_vector: PolicyEvaluationVector | None = None,
        distributional_report: DistributionalReport | None = None,
        causal_effect_report: CausalEffectReport | None = None,
        data_readiness_report: DataReadinessReport | None = None,
        data_readiness_report_ref: ArtifactRef | None = None,
        artifact_family: str = "causal_core",
        claim_mode: Literal["proof_only", "bounds", "estimation"] = "estimation",
        query_type: str | None = None,
        estimator_name: str | None = None,
        readiness_target: str | None = None,
        proof_bundle_ref: ArtifactRef | None = None,
        bounds_bundle_ref: ArtifactRef | None = None,
        negative_certificate_ref: ArtifactRef | None = None,
        replay_bundle_ref: ArtifactRef | None = None,
        replay_verification_ref: ArtifactRef | None = None,
        replay_verification_report: ReplayVerificationReport | None = None,
        promotion_evidence_bundle_ref: ArtifactRef | None = None,
        cross_graph_profile: CrossGraphEvidenceProfile | None = None,
        prior_knowledge_bundle: PriorKnowledgeBundle | None = None,
        governance_report: GovernanceReport | None = None,
        latent_discovery_bundle: LatentDiscoveryBundle | None = None,
        latent_discovery_resolution_error: dict[str, Any] | None = None,
        uncertainty_envelope: UncertaintyEnvelope | IRUncertaintyEnvelope | None = None,
        budget_state: BudgetState | None = None,
        candidate_ref: ArtifactRef | None = None,
        evaluation_ref: ArtifactRef | None = None,
        state: dict[str, Any] | None = None,
        voi_scheduler: object | None = None,
        run_id: str = "policy_promotion",
        expected_improvement: float | None = None,
        timeout_risk: float | None = None,
        replay_cost_usd: float | None = None,
        compute_cost_usd: float | None = None,
        evaluation_backend_kind: str | None = None,
        evaluation_fidelity_mode: str | None = None,
        evaluation_promotable_source: bool = True,
        evaluation_degradation_mode: str | None = None,
        evaluation_provenance_notes: list[str] | None = None,
    ) -> JudgeInputBundle:
        return JudgeInputBundle(
            candidate=candidate,
            evaluation_vector=evaluation_vector,
            funnel_outcome=funnel_outcome,
            benchmark_evaluation=benchmark_evaluation,
            hidden_holdout_evaluation=hidden_holdout_evaluation,
            platform_meta_evaluation_report=platform_meta_evaluation_report,
            distributional_report=distributional_report,
            causal_effect_report=causal_effect_report,
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
            replay_bundle_ref=replay_bundle_ref,
            replay_verification_ref=replay_verification_ref,
            replay_verification_report=replay_verification_report,
            promotion_evidence_bundle_ref=promotion_evidence_bundle_ref,
            cross_graph_profile=cross_graph_profile,
            prior_knowledge_bundle=prior_knowledge_bundle,
            governance_report=governance_report,
            latent_discovery_bundle=latent_discovery_bundle,
            latent_discovery_resolution_error=(
                None
                if latent_discovery_resolution_error is None
                else dict(latent_discovery_resolution_error)
            ),
            uncertainty_envelope=uncertainty_envelope,
            budget_state=budget_state,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            state=dict(state or {}),
            voi_scheduler=voi_scheduler,
            run_id=run_id,
            expected_improvement=expected_improvement,
            timeout_risk=timeout_risk,
            replay_cost_usd=replay_cost_usd,
            compute_cost_usd=compute_cost_usd,
            evaluation_backend_kind=evaluation_backend_kind,
            evaluation_fidelity_mode=evaluation_fidelity_mode,
            evaluation_promotable_source=evaluation_promotable_source,
            evaluation_degradation_mode=evaluation_degradation_mode,
            evaluation_provenance_notes=list(evaluation_provenance_notes or []),
        )

    def coordinate_promotion(
        self,
        *,
        loop_id: str,
        candidate_ref: ArtifactRef,
        evaluation_ref: ArtifactRef,
        promotion_policy: PromotionPolicy,
        judge_input: JudgeInputBundle,
        active_judges: Iterable[JudgeName] | None = None,
    ) -> PolicyPromotionResult:
        data_readiness_report_ref = judge_input.data_readiness_report_ref
        if data_readiness_report_ref is None and judge_input.data_readiness_report is not None:
            persisted = persist_data_readiness_report(
                self._store,
                judge_input.data_readiness_report,
            )
            data_readiness_report_ref = _to_artifact_ref(persisted)
        judge_input = judge_input.model_copy(
            update={"data_readiness_report_ref": data_readiness_report_ref}
        )
        judge_verdict = self._judge_stack.evaluate(
            judge_input.model_copy(update={"candidate_ref": candidate_ref, "evaluation_ref": evaluation_ref}),
            active_judges=active_judges,
        )
        judge_verdict_ref = persist_judge_verdict(
            self._store,
            judge_verdict,
            inputs=[
                InputRef(artifact_id=candidate_ref.artifact_id, role="candidate"),
                InputRef(artifact_id=evaluation_ref.artifact_id, role="evaluation"),
                *(
                    [
                        InputRef(
                            artifact_id=judge_input.data_readiness_report_ref.artifact_id,
                            role="data_readiness_report",
                        )
                    ]
                    if judge_input.data_readiness_report_ref is not None
                    else []
                ),
            ],
        )
        judge_verdict = judge_verdict.model_copy(update={"audit_log_ref": judge_verdict_ref})
        readiness = self._readiness_evaluator.evaluate(
            candidate=judge_input.candidate,
            judge_verdict=judge_verdict,
            uncertainty_envelope=judge_input.search_uncertainty(),
            evaluation_vector=judge_input.evaluation_vector,
            cross_graph_profile=judge_input.cross_graph_profile,
            prior_knowledge_bundle=judge_input.prior_knowledge_bundle,
            data_readiness_report=judge_input.data_readiness_report,
            data_readiness_report_ref=judge_input.data_readiness_report_ref,
            evidence_metadata={
                "backend_kind": judge_input.evaluation_backend_kind,
                "fidelity_mode": judge_input.evaluation_fidelity_mode,
                "promotable_source": judge_input.evaluation_promotable_source,
                "degradation_mode": judge_input.effective_evaluation_degradation_mode(),
                "notes": list(judge_input.evaluation_provenance_notes),
                "latent_discovery_resolution_error": (
                    None
                    if judge_input.latent_discovery_resolution_error is None
                    else dict(judge_input.latent_discovery_resolution_error)
                ),
                "latent_governance": (
                    None
                    if judge_input.latent_governance_assessment() is None
                    else judge_input.latent_governance_assessment().model_dump(mode="json")
                ),
            },
            claim_mode=judge_input.effective_claim_mode(),
        )
        readiness_ref = persist_decision_readiness_contract(
            self._store,
            readiness,
            inputs=[
                InputRef(artifact_id=candidate_ref.artifact_id, role="candidate"),
                InputRef(artifact_id=evaluation_ref.artifact_id, role="evaluation"),
            ],
        )

        current = self._champion_registry.get(loop_id)
        if judge_verdict.composite_decision != "promote":
            promotion_decision = PromotionDecision(
                loop_id=loop_id,
                promoted=False,
                reason=f"judge_stack_{judge_verdict.composite_decision}",
                champion=current,
                previous_champion=current,
            )
            self._notify_voi_scheduler(judge_input, promoted=False)
            return PolicyPromotionResult(
                judge_verdict=judge_verdict,
                judge_verdict_ref=judge_verdict_ref,
                readiness_contract=readiness,
                readiness_ref=readiness_ref,
                promotion_decision=promotion_decision,
            )

        if not judge_input.evaluation_promotable_source:
            promotion_decision = PromotionDecision(
                loop_id=loop_id,
                promoted=False,
                reason="evaluation_source_not_promotable",
                champion=current,
                previous_champion=current,
            )
            self._notify_voi_scheduler(judge_input, promoted=False)
            return PolicyPromotionResult(
                judge_verdict=judge_verdict,
                judge_verdict_ref=judge_verdict_ref,
                readiness_contract=readiness,
                readiness_ref=readiness_ref,
                promotion_decision=promotion_decision,
            )

        decision = self._champion_registry.consider_promotion(
            loop_id,
            candidate_ref,
            evaluation_ref,
            promotion_policy,
        )
        if decision.champion is not None:
            updated = _attach_policy_metadata(
                registry=self._champion_registry,
                loop_id=loop_id,
                champion=decision.champion,
                judge_verdict=judge_verdict,
                judge_verdict_ref=judge_verdict_ref,
                readiness=readiness,
                readiness_ref=readiness_ref,
            )
            decision = PromotionDecision(
                loop_id=decision.loop_id,
                promoted=decision.promoted,
                reason=decision.reason,
                champion=updated,
                previous_champion=decision.previous_champion,
            )

        self._notify_voi_scheduler(judge_input, promoted=decision.promoted)
        return PolicyPromotionResult(
            judge_verdict=judge_verdict,
            judge_verdict_ref=judge_verdict_ref,
            readiness_contract=readiness,
            readiness_ref=readiness_ref,
            promotion_decision=decision,
        )

    def _notify_voi_scheduler(
        self,
        judge_input: JudgeInputBundle,
        *,
        promoted: bool,
    ) -> None:
        scheduler = judge_input.voi_scheduler
        if scheduler is None or not hasattr(scheduler, "observe_promotion_outcome"):
            return
        transfer_context = judge_input.state.get("transfer_context")
        candidate_metadata = getattr(judge_input.candidate, "metadata", {}) or {}
        task_family = getattr(transfer_context, "task_family", None) or str(
            candidate_metadata.get("task_family", "policy")
        )
        domain = getattr(transfer_context, "domain", None) or str(
            candidate_metadata.get("domain", "general")
        )
        tenant_hash = getattr(transfer_context, "tenant_hash", None) or str(
            candidate_metadata.get("tenant_hash", "")
        )
        frontier_position = str(judge_input.state.get("current_pareto_position", "unknown"))
        cheap_signal = None
        fidelity_level = 4
        if judge_input.funnel_outcome is not None and judge_input.funnel_outcome.final_result is not None:
            cheap_signal = judge_input.funnel_outcome.final_result.cheap_signal
            fidelity_level = judge_input.funnel_outcome.final_result.fidelity_level
        scheduler.observe_promotion_outcome(
            candidate_id=judge_input.candidate.candidate_id,
            promoted=promoted,
            task_family=task_family,
            domain=domain,
            tenant_hash=tenant_hash,
            frontier_position=frontier_position,
            cheap_signal=cheap_signal,
            stage_level=fidelity_level,
            metadata={"run_id": judge_input.run_id},
        )


def compliance_issue_to_failure_card(
    issue: ComplianceIssue,
    *,
    judge_name: str,
) -> TypedFailureCard:
    """Compliance issue to failure card helper."""
    severity = {
        IssueSeverity.BLOCKER: FailureSeverity.BLOCKER,
        IssueSeverity.WARNING: FailureSeverity.WARNING,
        IssueSeverity.INFO: FailureSeverity.INFO,
    }[issue.severity]
    uncertainty = _issue_uncertainty_type(issue.pass_id)
    return TypedFailureCard(
        judge_name=judge_name,
        failure_type=str(issue.code or issue.pass_id),
        severity=severity,
        description=issue.message,
        uncertainty_type=uncertainty,
        remediation_hint=issue.suggestion,
        metadata={"path": list(issue.path), "pass_id": issue.pass_id},
    )


def to_search_uncertainty_envelope(
    payload: UncertaintyEnvelope | IRUncertaintyEnvelope | None,
    *,
    causal_effect_report: CausalEffectReport | None = None,
    cross_graph_profile: CrossGraphEvidenceProfile | None = None,
) -> UncertaintyEnvelope:
    """Convert to search uncertainty envelope."""
    if isinstance(payload, UncertaintyEnvelope):
        return payload

    ir_payload = payload
    if ir_payload is None and causal_effect_report is not None:
        ir_payload = causal_effect_report.to_uncertainty_envelope()

    if isinstance(ir_payload, IRUncertaintyEnvelope):
        relative = ir_payload.relative_uncertainty
        ratio = 1.0 if relative is None else max(0.0, min(1.0, float(relative)))
        transport_ratio = ratio
        if cross_graph_profile is not None and cross_graph_profile.needs:
            unsupported = sum(
                1
                for assessment in cross_graph_profile.needs
                if assessment.transport_status is TransportStatus.UNSUPPORTED
            )
            transport_ratio = max(
                transport_ratio,
                unsupported / max(len(cross_graph_profile.needs), 1),
            )
        return UncertaintyEnvelope.from_partial(
            {
                UncertaintyType.STATISTICAL: UncertaintyEstimate(
                    level=ratio,
                    source="ir_uncertainty_envelope",
                    quantification_method="relative_ci_width",
                    is_reducible=True,
                ),
                UncertaintyType.STRUCTURAL: UncertaintyEstimate(
                    level=ratio,
                    source="ir_uncertainty_envelope",
                    quantification_method="relative_ci_width",
                    is_reducible=True,
                ),
                UncertaintyType.TRANSPORT: UncertaintyEstimate(
                    level=transport_ratio,
                    source="cross_graph_profile",
                    quantification_method="unsupported_need_ratio",
                    is_reducible=True,
                ),
                UncertaintyType.MEASUREMENT: UncertaintyEstimate(
                    level=ratio,
                    source="ir_uncertainty_envelope",
                    quantification_method="relative_ci_width",
                    is_reducible=True,
                ),
                UncertaintyType.MODEL: UncertaintyEstimate(
                    level=min(1.0, ratio + 0.1),
                    source="causal_effect_report",
                    quantification_method="model_proxy",
                    is_reducible=True,
                ),
            }
        )

    return UncertaintyEnvelope.unknown()


def benchmark_split(name: str):
    """Benchmark split helper."""
    benchmark_split_enum = load_benchmark_split_enum()
    normalized = str(name).strip().lower()
    for split in benchmark_split_enum:
        if split.value == normalized:
            return split
    return (
        benchmark_split_enum.SELECTION
        if normalized == "selection"
        else benchmark_split_enum.HOLDOUT
    )


def _benchmark_runtime_split_card(
    bundle: JudgeInputBundle,
) -> TypedFailureCard | None:
    benchmark_split_enum = load_benchmark_split_enum()
    selection = bundle.benchmark_evaluation
    holdout = bundle.hidden_holdout_evaluation
    if selection is not None and not selection.matches_runtime_split(
        benchmark_split_enum.SELECTION
    ):
        return TypedFailureCard(
            judge_name=JudgeName.ROBUSTNESS.value,
            failure_type="benchmark_split_type_mismatch",
            severity=FailureSeverity.BLOCKER,
            description=(
                "Selection benchmark evaluation must declare runtime split 'selection'."
            ),
            uncertainty_type=UncertaintyType.MODEL,
            metadata={
                "observed_split": selection.resolved_runtime_split_type().value,
                "suite_id": selection.suite_id,
            },
        )
    if holdout is not None and not holdout.matches_runtime_split(
        benchmark_split_enum.HIDDEN_HOLDOUT
    ):
        return TypedFailureCard(
            judge_name=JudgeName.ROBUSTNESS.value,
            failure_type="benchmark_split_type_mismatch",
            severity=FailureSeverity.BLOCKER,
            description=(
                "Hidden holdout benchmark evaluation must declare runtime split "
                "'hidden_holdout'."
            ),
            uncertainty_type=UncertaintyType.MODEL,
            metadata={
                "observed_split": holdout.resolved_runtime_split_type().value,
                "suite_id": holdout.suite_id,
            },
        )
    return None


def _hidden_holdout_degradation_card(
    bundle: JudgeInputBundle,
) -> TypedFailureCard | None:
    return _hidden_holdout_degradation_card_with_threshold(
        bundle,
        resolved=None,
    )


def _hidden_holdout_degradation_card_with_threshold(
    bundle: JudgeInputBundle,
    resolved: ResolvedThresholdSet | None,
) -> TypedFailureCard | None:
    split_card = _benchmark_runtime_split_card(bundle)
    if split_card is not None:
        return split_card
    degradation = _hidden_holdout_degradation_details(bundle)
    if degradation is None:
        return None
    metric, sel_value, hold_value, delta = degradation
    violation = (
        _check_threshold_violation(
            resolved,
            metric_name="hidden_holdout_degradation",
            observed_value=delta,
        )
        if resolved is not None
        else None
    )
    if violation is None and delta <= 0.10:
        return None
    return TypedFailureCard(
        judge_name=JudgeName.ROBUSTNESS.value,
        failure_type="hidden_holdout_degradation",
        severity=FailureSeverity.BLOCKER,
        description=(
            f"Hidden holdout degraded on '{metric}' from {sel_value:.4f} to {hold_value:.4f}."
        ),
        uncertainty_type=UncertaintyType.MODEL,
        metric_name="hidden_holdout_degradation",
        observed_value=delta,
        threshold_value=(
            violation.threshold_value if violation is not None else 0.10
        ),
        threshold_direction="max",
        metadata={
            "selection_metric_name": metric,
            "selection_value": sel_value,
            "hidden_holdout_value": hold_value,
        },
    )


def _platform_meta_evaluation_card(
    bundle: JudgeInputBundle,
) -> TypedFailureCard | None:
    report = bundle.platform_meta_evaluation_report
    if report is None or report.promotion_safe:
        return None
    return TypedFailureCard(
        judge_name=JudgeName.ROBUSTNESS.value,
        failure_type="platform_meta_evaluation_failed",
        severity=FailureSeverity.BLOCKER,
        description=(
            "Platform meta-evaluation reported that current hidden holdout, "
            "sentinel, or calibration guards are not promotion-safe."
        ),
        uncertainty_type=UncertaintyType.MODEL,
        metadata={
            "overall_status": report.overall_status,
            "triggered_guards": list(report.triggered_guards),
        },
    )


def _judge_result(
    *,
    judge_name: JudgeName,
    fatal: bool,
    cards: list[TypedFailureCard],
    warnings: list[TypedFailureCard],
    uncertainty_assessed: list[UncertaintyType],
    evidence_refs: list[ArtifactRef],
    resolved_thresholds: ResolvedThresholdSet | None = None,
    metrics: dict[str, float] | None = None,
) -> SingleJudgeVerdict:
    blocker = next((card for card in cards if card.is_blocker), cards[0] if cards else None)
    passed = blocker is None
    metrics = dict(metrics or {})
    thresholds = {
        name: float(entry.threshold_value)
        for name, entry in (resolved_thresholds.entries.items() if resolved_thresholds is not None else [])
    }
    violations = [
        violation.metric_name
        for violation in (
            _check_threshold_violation(
                resolved_thresholds,
                metric_name=metric_name,
                observed_value=observed_value,
            )
            for metric_name, observed_value in metrics.items()
        )
        if violation is not None
    ]
    escalation_level: Literal["info", "warning", "error", "fatal"] = "info"
    if blocker is not None and fatal:
        escalation_level = "fatal"
    elif blocker is not None:
        escalation_level = "error"
    elif warnings:
        escalation_level = "warning"
    return SingleJudgeVerdict(
        judge_name=judge_name.value,
        passed=passed,
        is_fatal=fatal,
        failure_card=blocker,
        warnings=list(warnings),
        uncertainty_assessed=list(uncertainty_assessed),
        evidence_refs=list(evidence_refs),
        metrics=metrics,
        thresholds=thresholds,
        violations=violations,
        escalation_level=escalation_level,
        threshold_scope=(
            dict(resolved_thresholds.scope) if resolved_thresholds is not None else {}
        ),
        threshold_registry_version=(
            resolved_thresholds.registry_version if resolved_thresholds is not None else None
        ),
    )


def _unavailable_judge_verdict(judge_name: JudgeName) -> SingleJudgeVerdict:
    return SingleJudgeVerdict(
        judge_name=judge_name.value,
        passed=False,
        is_fatal=True,
        failure_card=TypedFailureCard(
            judge_name=judge_name.value,
            failure_type="judge_unavailable",
            severity=FailureSeverity.BLOCKER,
            description=f"Judge '{judge_name.value}' is unavailable in reduced-judge mode.",
        ),
    )


def _inactive_judge_verdict(judge_name: JudgeName) -> SingleJudgeVerdict:
    return SingleJudgeVerdict(
        judge_name=judge_name.value,
        passed=False,
        is_fatal=False,
        escalation_level="info",
    )


def _default_active_judges(bundle: JudgeInputBundle) -> set[JudgeName]:
    if bundle.effective_claim_mode() == "proof_only":
        return {
            JudgeName.STRUCTURAL,
            JudgeName.GOVERNANCE,
            JudgeName.REPRODUCIBILITY,
        }
    if bundle.effective_claim_mode() == "bounds":
        return {
            JudgeName.STRUCTURAL,
            JudgeName.STATISTICAL,
            JudgeName.GOVERNANCE,
            JudgeName.REPRODUCIBILITY,
            JudgeName.COMPUTE,
        }
    return set(JudgeName)


def _issue_uncertainty_type(pass_id: str) -> UncertaintyType | None:
    mapping = {
        "confidence": UncertaintyType.STATISTICAL,
        "quality": UncertaintyType.MEASUREMENT,
        "refutation": UncertaintyType.MODEL,
        "transportability_required": UncertaintyType.TRANSPORT,
        "sutva_check": UncertaintyType.STRUCTURAL,
        "equity": UncertaintyType.STRUCTURAL,
    }
    return mapping.get(pass_id)


def _evidence_refs(bundle: JudgeInputBundle) -> list[ArtifactRef]:
    refs = [
        ref
        for ref in (
            bundle.candidate_ref,
            bundle.evaluation_ref,
            bundle.data_readiness_report_ref,
            bundle.proof_bundle_ref,
            bundle.bounds_bundle_ref,
            bundle.negative_certificate_ref,
            bundle.replay_bundle_ref,
            bundle.replay_verification_ref,
            bundle.promotion_evidence_bundle_ref,
        )
        if ref is not None
    ]
    return refs


def _to_artifact_ref(ref: Any) -> ArtifactRef:
    return ArtifactRef.model_validate(ref.model_dump(mode="json"))


def _attach_policy_metadata(
    *,
    registry: ChampionRegistryContract,
    loop_id: str,
    champion: ChampionPointer,
    judge_verdict: JudgeVerdict,
    judge_verdict_ref: ArtifactRef,
    readiness: DecisionReadinessContract,
    readiness_ref: ArtifactRef,
) -> ChampionPointer:
    metadata = dict(champion.metadata)
    metadata["judge_verdict"] = judge_verdict.model_dump(mode="json")
    metadata["judge_verdict_ref"] = judge_verdict_ref.model_dump(mode="json")
    metadata["decision_readiness"] = readiness.model_dump(mode="json")
    metadata["decision_readiness_ref"] = readiness_ref.model_dump(mode="json")
    updated = champion.model_copy(update={"metadata": metadata})
    registry.write_pointer(loop_id, updated)
    return updated

def _threshold_failure_card(
    *,
    judge_name: str,
    failure_type: str,
    description: str,
    violation: ThresholdViolation,
    uncertainty_type: UncertaintyType | None = None,
    severity: FailureSeverity = FailureSeverity.BLOCKER,
) -> TypedFailureCard:
    return TypedFailureCard(
        judge_name=judge_name,
        failure_type=failure_type,
        severity=severity,
        description=(
            f"{description} Observed {violation.metric_name}="
            f"{violation.observed_value:.6f} versus threshold "
            f"{violation.threshold_direction} {violation.threshold_value:.6f}."
        ),
        uncertainty_type=uncertainty_type,
        metric_name=violation.metric_name,
        observed_value=violation.observed_value,
        threshold_value=violation.threshold_value,
        threshold_direction=violation.threshold_direction,
    )


def _hidden_holdout_degradation_details(
    bundle: JudgeInputBundle,
) -> tuple[str, float, float, float] | None:
    selection = bundle.benchmark_evaluation
    holdout = bundle.hidden_holdout_evaluation
    if selection is None or holdout is None:
        return None
    shared = sorted(set(selection.selection_metrics) & set(holdout.holdout_metrics))
    if not shared:
        return None
    chosen: tuple[str, float, float, float] | None = None
    for metric in shared:
        sel_value = float(selection.selection_metrics[metric])
        hold_value = float(holdout.holdout_metrics[metric])
        if abs(sel_value) <= 1e-12:
            delta = 0.0 if abs(hold_value) <= 1e-12 else 1.0
        else:
            delta = max(0.0, (sel_value - hold_value) / abs(sel_value))
        if chosen is None or delta > chosen[3]:
            chosen = (metric, sel_value, hold_value, delta)
    return chosen


def _hidden_holdout_degradation_value(
    bundle: JudgeInputBundle,
) -> float | None:
    details = _hidden_holdout_degradation_details(bundle)
    return None if details is None else details[3]


__all__ = [
    "JudgeInputBundle",
    "JudgeName",
    "JudgeStack",
    "JudgeVerdict",
    "PolicyPromotionCoordinator",
    "PolicyPromotionResult",
    "SingleJudgeVerdict",
    "compliance_issue_to_failure_card",
    "to_search_uncertainty_envelope",
]
