"""Unified governance accountability artifact and threshold registry helpers."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.lex import ComplianceIssue
from polisyos.core.contracts.scientist import GovernanceAccountabilityArtifactRef
from polisyos.ir.analytics.calibration_diagnostics import CalibrationDiagnosticsReport
from polisyos.ir.analytics.distributional import DistributionalReport, TailRiskDeltaSummary
from polisyos.ir.analytics.fairness import CausalFairnessReport

_ACCOUNTABILITY_KIND = "scientist.governance_accountability_artifact"
_ACCOUNTABILITY_SCHEMA = SchemaInfo(
    name="polisyos.scientist.governance.GovernanceAccountabilityArtifact",
    version="1.0",
)
_EPSILON = 1e-12


@dataclass(frozen=True)
class _ThresholdDefinition:
    metric_id: str
    comparator: Literal["<=", ">=", "<", ">"]
    default_value: float
    severity: Literal["info", "warning", "blocker", "human_gate"]
    rationale: str
    adaptive: bool = False


_THRESHOLD_DEFINITIONS: dict[str, _ThresholdDefinition] = {
    "equity_gini_increase_max": _ThresholdDefinition(
        metric_id="equity.overall_gini_delta",
        comparator="<=",
        default_value=0.02,
        severity="warning",
        rationale="Keep inequality shifts below a material 2 percentage-point change on the default path.",
    ),
    "equity_vulnerable_loss_max_pct": _ThresholdDefinition(
        metric_id="equity.vulnerable_loss_pct",
        comparator=">=",
        default_value=-5.0,
        severity="warning",
        rationale="Prevent vulnerable cohorts from absorbing losses larger than five percentage points without explicit mitigation.",
    ),
    "equity_max_losers_share": _ThresholdDefinition(
        metric_id="equity.losers_share",
        comparator="<=",
        default_value=0.60,
        severity="warning",
        rationale="Default policy paths should not create majority-loser rollouts unless governance signs off on the transition burden.",
    ),
    "uncertainty_max_ci_width_ratio": _ThresholdDefinition(
        metric_id="uncertainty.ci_width_ratio",
        comparator="<=",
        default_value=1.0,
        severity="warning",
        rationale="Confidence intervals should not be wider than the point estimate magnitude on promotion-grade evidence.",
    ),
    "uncertainty_max_ci_width_abs": _ThresholdDefinition(
        metric_id="uncertainty.ci_width_abs",
        comparator="<=",
        default_value=float("inf"),
        severity="warning",
        rationale="Absolute CI width defaults to caller-specified domain tolerance; absent one, the bound is informational only.",
    ),
    "uncertainty_min_gate_eligible_ratio": _ThresholdDefinition(
        metric_id="uncertainty.gate_eligible_ratio",
        comparator=">=",
        default_value=0.0,
        severity="warning",
        rationale="Promotion should only rely on envelopes that actually satisfy gate semantics.",
    ),
    "impact_threshold": _ThresholdDefinition(
        metric_id="governance.impact_score",
        comparator=">=",
        default_value=0.8,
        severity="warning",
        rationale="High-impact decisions require explicit acknowledgement once impact exceeds 0.80.",
    ),
    "require_human_review_above": _ThresholdDefinition(
        metric_id="governance.impact_score",
        comparator=">=",
        default_value=0.9,
        severity="human_gate",
        rationale="Very high-impact decisions must be reviewed by a human before promotion or deployment.",
    ),
    "calibration.brier_score_max": _ThresholdDefinition(
        metric_id="calibration.brier_score",
        comparator="<=",
        default_value=0.20,
        severity="warning",
        rationale="Binary probabilistic forecasts on the default path should materially outperform an uninformed 0.25 Brier baseline.",
    ),
    "calibration.log_score_max": _ThresholdDefinition(
        metric_id="calibration.log_score",
        comparator="<=",
        default_value=0.65,
        severity="warning",
        rationale="Log score should beat the default coin-flip loss (~0.693) before claims are considered well-calibrated.",
    ),
    "calibration.ece_max": _ThresholdDefinition(
        metric_id="calibration.ece",
        comparator="<=",
        default_value=0.05,
        severity="warning",
        rationale="Expected calibration error above 5% indicates visibly miscalibrated default-path probabilities.",
    ),
    "calibration.ence_max": _ThresholdDefinition(
        metric_id="calibration.ence",
        comparator="<=",
        default_value=0.10,
        severity="warning",
        rationale="Expected normalized calibration error above 10% suggests over- or under-confident uncertainty reporting.",
    ),
    "fairness.equalized_odds_gap_max": _ThresholdDefinition(
        metric_id="fairness.equalized_odds_gap",
        comparator="<=",
        default_value=0.10,
        severity="human_gate",
        rationale="Equalized-odds gaps above 10% require human review because the operating point creates materially unequal error rates.",
        adaptive=True,
    ),
    "fairness.group_calibration_gap_max": _ThresholdDefinition(
        metric_id="fairness.group_calibration_gap",
        comparator="<=",
        default_value=0.05,
        severity="warning",
        rationale="Group-level calibration gaps above 5% indicate probability quality differs across cohorts.",
    ),
    "fairness.intersectional_positive_rate_gap_max": _ThresholdDefinition(
        metric_id="fairness.intersectional_positive_rate_gap",
        comparator="<=",
        default_value=0.15,
        severity="human_gate",
        rationale="Large intersectional positive-rate gaps require explicit sign-off because aggregated fairness can hide subgroup harm.",
        adaptive=True,
    ),
    "fairness.counterfactual_direct_discrimination_max": _ThresholdDefinition(
        metric_id="fairness.counterfactual_direct_discrimination",
        comparator="<=",
        default_value=0.05,
        severity="human_gate",
        rationale="Direct counterfactual discrimination beyond 5% is not allowed on the default path without escalation.",
    ),
    "risk.tail_exceedance_delta_max": _ThresholdDefinition(
        metric_id="risk.tail_exceedance_delta",
        comparator="<=",
        default_value=0.05,
        severity="warning",
        rationale="Tail exceedance probability should not worsen by more than five percentage points in deployment-facing scenarios.",
    ),
    "risk.cvar_delta_max": _ThresholdDefinition(
        metric_id="risk.cvar_delta",
        comparator="<=",
        default_value=0.05,
        severity="warning",
        rationale="CVaR deterioration above 5% indicates the policy shifts unacceptable mass into the worst outcomes.",
    ),
    "promotion.composite_score_min": _ThresholdDefinition(
        metric_id="promotion.composite_score",
        comparator=">=",
        default_value=0.70,
        severity="warning",
        rationale="Default-path promotion claims need a composite validation score comfortably above exploratory quality.",
    ),
}


class GovernanceThresholdEntry(BaseModel):
    """Threshold registry entry with resolved value, rationale, and evaluation state."""

    model_config = ConfigDict(extra="forbid")

    threshold_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    comparator: Literal["<=", ">=", "<", ">"]
    threshold_value: float | None = None
    severity: Literal["info", "warning", "blocker", "human_gate"]
    rationale: str = Field(min_length=1)
    source: Literal["default", "override", "adaptive"] = "default"
    adaptive: bool = False
    observed_value: float | None = None
    passed: bool | None = None


class CalibrationCurveBin(BaseModel):
    """One reliability-diagram bin."""

    model_config = ConfigDict(extra="forbid")

    lower: float = Field(ge=0.0, le=1.0)
    upper: float = Field(ge=0.0, le=1.0)
    count: int = Field(ge=0)
    mean_predicted: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_observed: float | None = Field(default=None, ge=0.0, le=1.0)
    absolute_gap: float | None = Field(default=None, ge=0.0)


class CalibrationMetricsSummary(BaseModel):
    """Probability-quality summary for governance-facing calibration review."""

    model_config = ConfigDict(extra="forbid")

    n_obs: int = Field(ge=0)
    brier_score: float | None = Field(default=None, ge=0.0)
    log_score: float | None = Field(default=None, ge=0.0)
    ece: float | None = Field(default=None, ge=0.0)
    ence: float | None = Field(default=None, ge=0.0)
    mean_predicted_score: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_observed_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    reliability_diagram: list[CalibrationCurveBin] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GroupCalibrationSummary(BaseModel):
    """Calibration and operating-point summary for one protected-group slice."""

    model_config = ConfigDict(extra="forbid")

    group_axis: str = Field(min_length=1)
    group_value: str = Field(min_length=1)
    count: int = Field(ge=0)
    positive_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_score: float | None = Field(default=None, ge=0.0, le=1.0)
    calibration_gap: float | None = None
    brier_score: float | None = Field(default=None, ge=0.0)
    log_score: float | None = Field(default=None, ge=0.0)


class ThresholdTradeoffPoint(BaseModel):
    """One deterministic operating point on the fairness-vs-accuracy frontier."""

    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(ge=0.0, le=1.0)
    accuracy: float = Field(ge=0.0, le=1.0)
    balanced_accuracy: float = Field(ge=0.0, le=1.0)
    equalized_odds_gap: float = Field(ge=0.0)
    demographic_parity_gap: float = Field(ge=0.0)
    selected: bool = False


class AdaptiveThresholdSummary(BaseModel):
    """Chosen operating threshold and the fairness/accuracy rationale behind it."""

    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(ge=0.0, le=1.0)
    source: Literal["default", "adaptive"] = "default"
    selection_objective: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    expected_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    expected_equalized_odds_gap: float | None = Field(default=None, ge=0.0)
    frontier: list[ThresholdTradeoffPoint] = Field(default_factory=list)


class FairnessAssessmentSummary(BaseModel):
    """Fairness, calibration-by-group, and counterfactual accountability summary."""

    model_config = ConfigDict(extra="forbid")

    equalized_odds_gap: float | None = Field(default=None, ge=0.0)
    demographic_parity_gap: float | None = Field(default=None, ge=0.0)
    group_calibration_gap: float | None = Field(default=None, ge=0.0)
    intersectional_positive_rate_gap: float | None = Field(default=None, ge=0.0)
    counterfactual_fairness_satisfied: bool | None = None
    counterfactual_direct_discrimination: float | None = Field(default=None, ge=0.0)
    primary_unfair_pathway: str | None = None
    group_calibration: list[GroupCalibrationSummary] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class RiskAssessmentSummary(BaseModel):
    """Tail-risk, CVaR, and stress-scenario accountability surface."""

    model_config = ConfigDict(extra="forbid")

    worst_stress_scenario: str | None = None
    stress_critical_count: int = Field(default=0, ge=0)
    stress_high_count: int = Field(default=0, ge=0)
    tail_exceedance_delta: float | None = Field(default=None, ge=0.0)
    cvar_level: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline_cvar: float | None = None
    counterfactual_cvar: float | None = None
    cvar_delta: float | None = None
    notes: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class ModelCardSection(BaseModel):
    """Compact model-card surface for accountability exports."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    intended_use: str | None = None
    evaluation_split: str | None = None
    primary_metrics: dict[str, float] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class DataSheetSection(BaseModel):
    """Compact datasheet-style surface describing the evaluated evidence slice."""

    model_config = ConfigDict(extra="forbid")

    dataset_name: str | None = None
    dataset_version: str | None = None
    sample_count: int | None = Field(default=None, ge=0)
    protected_attributes: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    known_coverage_limits: list[str] = Field(default_factory=list)


class GovernanceAccountabilityInput(BaseModel):
    """Optional evidence inputs used to enrich the governance accountability artifact."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    candidate_id: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    intended_use: str | None = None
    evaluation_split: str | None = None
    dataset_name: str | None = None
    dataset_version: str | None = None
    data_sources: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    predicted_scores: list[float] = Field(default_factory=list)
    observed_outcomes: list[float] = Field(default_factory=list)
    protected_attributes: dict[str, list[str]] = Field(default_factory=dict)
    predicted_uncertainties: list[float] = Field(default_factory=list)
    calibration_diagnostics: CalibrationDiagnosticsReport | None = None
    distributional_report: DistributionalReport | None = None
    causal_fairness_report: CausalFairnessReport | None = None
    tail_risk_summary: TailRiskDeltaSummary | None = None
    threshold_overrides: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_lengths(self) -> GovernanceAccountabilityInput:
        n_scores = len(self.predicted_scores)
        n_outcomes = len(self.observed_outcomes)
        if n_scores != n_outcomes:
            raise ValueError("predicted_scores and observed_outcomes must have identical length")
        if self.predicted_uncertainties and len(self.predicted_uncertainties) != n_scores:
            raise ValueError("predicted_uncertainties must match predicted_scores length")
        for axis, values in self.protected_attributes.items():
            if n_scores and len(values) != n_scores:
                raise ValueError(
                    f"protected_attributes[{axis!r}] must match predicted_scores length"
                )
        return self


class ProbabilisticEscalationPolicy(BaseModel):
    """Documented escalation policy for probabilistic verdicts and fairness risks."""

    model_config = ConfigDict(extra="forbid")

    policy_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    requires_human_review: bool = False
    escalation_triggers: list[str] = Field(default_factory=list)
    recommended_action: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    documented_rules: list[str] = Field(default_factory=list)


class GovernanceAccountabilityArtifact(BaseModel):
    """Unified accountability artifact for calibration, fairness, risk, and verdict logic."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str = Field(min_length=1)
    candidate_ref: ArtifactRef
    governance_verdict: str = Field(min_length=1)
    risk_weighted_verdict: Literal["approve", "needs_revision", "reject", "human_gate"]
    promotion_safe: bool = False
    threshold_registry: list[GovernanceThresholdEntry] = Field(default_factory=list)
    calibration: CalibrationMetricsSummary | None = None
    fairness: FairnessAssessmentSummary | None = None
    risk: RiskAssessmentSummary | None = None
    adaptive_threshold: AdaptiveThresholdSummary | None = None
    model_card: ModelCardSection = Field(default_factory=ModelCardSection)
    datasheet: DataSheetSection = Field(default_factory=DataSheetSection)
    escalation_policy: ProbabilisticEscalationPolicy
    gaps: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def compact_summary(self) -> dict[str, Any]:
        """Return the dashboard-facing summary surfaced in promotion bundles and packets."""

        failed = [entry.threshold_id for entry in self.threshold_registry if entry.passed is False]
        return {
            "risk_weighted_verdict": self.risk_weighted_verdict,
            "promotion_safe": self.promotion_safe,
            "failed_thresholds": failed,
            "escalation_triggers": list(self.escalation_policy.escalation_triggers),
            "selected_threshold": (
                None if self.adaptive_threshold is None else self.adaptive_threshold.threshold
            ),
            "calibration": (
                None
                if self.calibration is None
                else {
                    "brier_score": self.calibration.brier_score,
                    "log_score": self.calibration.log_score,
                    "ece": self.calibration.ece,
                    "ence": self.calibration.ence,
                    "n_obs": self.calibration.n_obs,
                }
            ),
            "fairness": (
                None
                if self.fairness is None
                else {
                    "equalized_odds_gap": self.fairness.equalized_odds_gap,
                    "group_calibration_gap": self.fairness.group_calibration_gap,
                    "intersectional_positive_rate_gap": (
                        self.fairness.intersectional_positive_rate_gap
                    ),
                    "counterfactual_fairness_satisfied": (
                        self.fairness.counterfactual_fairness_satisfied
                    ),
                }
            ),
            "risk": (
                None
                if self.risk is None
                else {
                    "worst_stress_scenario": self.risk.worst_stress_scenario,
                    "tail_exceedance_delta": self.risk.tail_exceedance_delta,
                    "cvar_delta": self.risk.cvar_delta,
                }
            ),
            "requires_human_review": self.escalation_policy.requires_human_review,
            "gaps": list(self.gaps),
        }


def resolve_governance_threshold(
    threshold_id: str,
    overrides: Mapping[str, Any] | None = None,
    *,
    fallback: float | None = None,
) -> float:
    """Resolve a threshold from caller overrides or the canonical registry."""

    if overrides is not None and threshold_id in overrides:
        candidate = _coerce_float(overrides[threshold_id])
        if candidate is not None:
            return candidate
    definition = _THRESHOLD_DEFINITIONS.get(threshold_id)
    if definition is not None:
        return float(definition.default_value)
    if fallback is not None:
        return float(fallback)
    raise KeyError(f"Unknown governance threshold: {threshold_id}")


def build_governance_accountability_artifact(
    *,
    run_id: str,
    candidate_ref: ArtifactRef,
    governance_verdict: str,
    governance_issues: Sequence[ComplianceIssue | Mapping[str, Any]] = (),
    adversarial_results: Sequence[Mapping[str, Any] | BaseModel] = (),
    composite_score: float | None = None,
    eligible_for_promotion: bool | None = None,
    stress_summary: Mapping[str, Any] | None = None,
    accountability_input: GovernanceAccountabilityInput | None = None,
) -> GovernanceAccountabilityArtifact:
    """Build the unified accountability artifact from validation outputs and optional raw evidence."""

    payload = accountability_input or GovernanceAccountabilityInput()
    gaps: list[str] = []
    notes: list[str] = []

    calibration = _build_calibration_summary(payload, gaps=gaps)
    fairness, adaptive_threshold = _build_fairness_summary(payload, gaps=gaps)
    risk = _build_risk_summary(payload, stress_summary=stress_summary, gaps=gaps)

    metric_values: dict[str, float] = {}
    if composite_score is not None and math.isfinite(float(composite_score)):
        metric_values["promotion.composite_score"] = float(composite_score)
    if calibration is not None:
        for metric_id in ("brier_score", "log_score", "ece", "ence"):
            value = getattr(calibration, metric_id)
            if value is not None and math.isfinite(float(value)):
                metric_values[f"calibration.{metric_id}"] = float(value)
    if fairness is not None:
        for metric_id in (
            "equalized_odds_gap",
            "group_calibration_gap",
            "intersectional_positive_rate_gap",
            "counterfactual_direct_discrimination",
        ):
            value = getattr(fairness, metric_id)
            if value is not None and math.isfinite(float(value)):
                metric_values[f"fairness.{metric_id}"] = float(value)
    if risk is not None:
        for metric_id, attr in (
            ("risk.tail_exceedance_delta", "tail_exceedance_delta"),
            ("risk.cvar_delta", "cvar_delta"),
        ):
            value = getattr(risk, attr)
            if value is not None and math.isfinite(float(value)):
                metric_values[metric_id] = float(value)

    threshold_registry = _build_threshold_registry(
        metric_values=metric_values,
        overrides=payload.threshold_overrides,
    )
    issue_codes = _issue_codes(governance_issues)
    notes.extend(f"governance_issue:{code}" for code in issue_codes)
    failed_adversarial = _failed_adversarial_aliases(adversarial_results)
    notes.extend(f"adversarial_failed:{alias}" for alias in failed_adversarial)
    if eligible_for_promotion is False:
        notes.append("promotion_gap:leaderboard_not_eligible")

    risk_weighted_verdict = _resolve_risk_weighted_verdict(
        governance_verdict=governance_verdict,
        threshold_registry=threshold_registry,
        eligible_for_promotion=eligible_for_promotion,
    )
    escalation_policy = _build_escalation_policy(
        governance_verdict=governance_verdict,
        threshold_registry=threshold_registry,
        failed_adversarial=failed_adversarial,
        gaps=gaps,
        risk_weighted_verdict=risk_weighted_verdict,
    )

    if not payload.predicted_scores or not payload.observed_outcomes:
        gaps.append("missing_probabilistic_outputs")
    if not payload.protected_attributes:
        gaps.append("missing_group_labels")
    if payload.tail_risk_summary is None:
        gaps.append("missing_tail_risk_summary")
    if payload.causal_fairness_report is None:
        gaps.append("missing_counterfactual_fairness_report")

    artifact = GovernanceAccountabilityArtifact(
        run_id=run_id,
        candidate_ref=candidate_ref,
        governance_verdict=governance_verdict,
        risk_weighted_verdict=risk_weighted_verdict,
        promotion_safe=risk_weighted_verdict == "approve" and eligible_for_promotion is not False,
        threshold_registry=threshold_registry,
        calibration=calibration,
        fairness=fairness,
        risk=risk,
        adaptive_threshold=adaptive_threshold,
        model_card=_build_model_card(
            payload,
            calibration=calibration,
            fairness=fairness,
            composite_score=composite_score,
        ),
        datasheet=_build_datasheet(
            payload, sample_count=None if calibration is None else calibration.n_obs
        ),
        escalation_policy=escalation_policy,
        gaps=sorted(set(gaps)),
        notes=sorted(set(notes)),
        metadata={
            "eligible_for_promotion": eligible_for_promotion,
            "composite_score": composite_score,
            "threshold_override_count": len(payload.threshold_overrides),
        },
    )
    return artifact


def persist_governance_accountability_artifact(
    store: FileSystemCAS,
    artifact: GovernanceAccountabilityArtifact,
    *,
    inputs: list[InputRef] | None = None,
) -> GovernanceAccountabilityArtifactRef:
    """Persist the accountability artifact as a first-class Scientist CAS object."""

    ref = store.put_json(
        artifact,
        PutOptions(
            kind=_ACCOUNTABILITY_KIND,
            media_type="application/json",
            schema=_ACCOUNTABILITY_SCHEMA,
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return GovernanceAccountabilityArtifactRef.model_validate(ref.model_dump())


def load_governance_accountability_artifact(
    store: FileSystemCAS,
    ref: ArtifactRef | GovernanceAccountabilityArtifactRef,
) -> GovernanceAccountabilityArtifact:
    """Load a persisted accountability artifact."""

    artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ref.artifact_id
    return GovernanceAccountabilityArtifact.model_validate(
        from_canonical_bytes(store.get_bytes(artifact_id))
    )


def _build_threshold_registry(
    *,
    metric_values: Mapping[str, float],
    overrides: Mapping[str, Any] | None,
) -> list[GovernanceThresholdEntry]:
    registry: list[GovernanceThresholdEntry] = []
    for threshold_id, definition in _THRESHOLD_DEFINITIONS.items():
        threshold_value = resolve_governance_threshold(
            threshold_id,
            overrides,
            fallback=definition.default_value,
        )
        serialized_threshold = threshold_value if math.isfinite(float(threshold_value)) else None
        observed_value = metric_values.get(definition.metric_id)
        passed = (
            None
            if observed_value is None or serialized_threshold is None
            else _evaluate_threshold(observed_value, definition.comparator, serialized_threshold)
        )
        registry.append(
            GovernanceThresholdEntry(
                threshold_id=threshold_id,
                metric_id=definition.metric_id,
                comparator=definition.comparator,
                threshold_value=serialized_threshold,
                severity=definition.severity,
                rationale=definition.rationale,
                source="override" if overrides and threshold_id in overrides else "default",
                adaptive=definition.adaptive,
                observed_value=observed_value,
                passed=passed,
            )
        )
    return registry


def _build_calibration_summary(
    payload: GovernanceAccountabilityInput,
    *,
    gaps: list[str],
) -> CalibrationMetricsSummary | None:
    if payload.calibration_diagnostics is not None:
        projected = _project_calibration_summary(payload.calibration_diagnostics, gaps=gaps)
        if projected is not None:
            return projected

    if not payload.predicted_scores or not payload.observed_outcomes:
        return None

    scores = [_clip_probability(value) for value in payload.predicted_scores]
    outcomes = [_clip_probability(value) for value in payload.observed_outcomes]
    n_obs = len(scores)
    brier = sum((score - outcome) ** 2 for score, outcome in zip(scores, outcomes)) / max(n_obs, 1)
    log_score = -sum(
        outcome * math.log(score + _EPSILON) + (1.0 - outcome) * math.log(1.0 - score + _EPSILON)
        for score, outcome in zip(scores, outcomes)
    ) / max(n_obs, 1)
    bins = _build_reliability_bins(scores, outcomes)
    ece = sum((item.count / max(n_obs, 1)) * (item.absolute_gap or 0.0) for item in bins)

    uncertainties = (
        list(payload.predicted_uncertainties)
        if payload.predicted_uncertainties
        else [math.sqrt(score * (1.0 - score)) for score in scores]
    )
    ence = _compute_ence(scores, outcomes, uncertainties)
    return CalibrationMetricsSummary(
        n_obs=n_obs,
        brier_score=brier,
        log_score=log_score,
        ece=ece,
        ence=ence,
        mean_predicted_score=sum(scores) / max(n_obs, 1),
        mean_observed_rate=sum(outcomes) / max(n_obs, 1),
        reliability_diagram=bins,
        notes=[],
    )


def _project_calibration_summary(
    report: CalibrationDiagnosticsReport,
    *,
    gaps: list[str],
) -> CalibrationMetricsSummary | None:
    curve_id = report.primary_curve
    if curve_id is None and report.curves:
        curve_id = next(iter(report.curves))
    reliability_diagram = (
        []
        if curve_id is None
        else [
            CalibrationCurveBin(
                lower=item.lower,
                upper=item.upper,
                count=item.count,
                mean_predicted=item.mean_predicted,
                mean_observed=item.mean_observed,
                absolute_gap=item.absolute_gap,
            )
            for item in report.curves.get(curve_id, ())
        ]
    )

    if report.task != "binary":
        gaps.append(f"accountability_binary_projection_task:{report.task}")

    notes = list(report.warnings)
    if report.recommended_action:
        notes.append(f"recommended_action:{report.recommended_action}")
    notes.extend(f"issue:{issue.code}" for issue in report.issues)
    notes.extend(f"test_rejected:{test.test_id}" for test in report.tests if test.passed is False)

    return CalibrationMetricsSummary(
        n_obs=report.metrics.n_obs,
        brier_score=report.metrics.brier,
        log_score=report.metrics.log_loss,
        ece=report.metrics.ece,
        ence=report.metrics.ence,
        mean_predicted_score=report.metrics.mean_predicted_score,
        mean_observed_rate=report.metrics.mean_observed_rate,
        reliability_diagram=reliability_diagram,
        notes=sorted(set(notes)),
    )


def _build_fairness_summary(
    payload: GovernanceAccountabilityInput,
    *,
    gaps: list[str],
) -> tuple[FairnessAssessmentSummary | None, AdaptiveThresholdSummary | None]:
    if not payload.predicted_scores or not payload.observed_outcomes:
        fairness = _fairness_from_optional_only(payload, gaps=gaps)
        return fairness, None

    scores = [_clip_probability(value) for value in payload.predicted_scores]
    outcomes = [1 if _clip_probability(value) >= 0.5 else 0 for value in payload.observed_outcomes]
    adaptive = _select_threshold(scores, outcomes, payload.protected_attributes)
    group_calibration = _group_calibration_summaries(
        scores=scores,
        outcomes=payload.observed_outcomes,
        protected_attributes=payload.protected_attributes,
    )
    group_calibration_gap = max(
        (
            abs(item.calibration_gap)
            for item in group_calibration
            if item.calibration_gap is not None
        ),
        default=None,
    )
    equalized_odds_gap, demographic_parity_gap = _fairness_gaps_for_threshold(
        scores=scores,
        outcomes=outcomes,
        protected_attributes=payload.protected_attributes,
        threshold=adaptive.threshold,
    )
    intersectional_gap = _intersectional_positive_rate_gap(
        scores=scores,
        protected_attributes=payload.protected_attributes,
        threshold=adaptive.threshold,
    )

    notes: list[str] = []
    if (
        payload.distributional_report is not None
        and payload.distributional_report.overall_gini_delta is not None
    ):
        notes.append(
            f"distributional_overall_gini_delta={payload.distributional_report.overall_gini_delta:.4f}"
        )
    fairness = FairnessAssessmentSummary(
        equalized_odds_gap=equalized_odds_gap,
        demographic_parity_gap=demographic_parity_gap,
        group_calibration_gap=group_calibration_gap,
        intersectional_positive_rate_gap=intersectional_gap,
        counterfactual_fairness_satisfied=(
            None
            if payload.causal_fairness_report is None
            else payload.causal_fairness_report.counterfactual_fairness_satisfied
        ),
        counterfactual_direct_discrimination=(
            None
            if payload.causal_fairness_report is None
            else float(payload.causal_fairness_report.direct_discrimination)
        ),
        primary_unfair_pathway=(
            None
            if payload.causal_fairness_report is None
            else payload.causal_fairness_report.primary_unfair_pathway
        ),
        group_calibration=group_calibration,
        notes=notes,
        gaps=[],
    )
    if not payload.protected_attributes:
        fairness.gaps.append("missing_group_labels")
        gaps.append("missing_group_labels")
    if payload.causal_fairness_report is None:
        fairness.gaps.append("missing_counterfactual_fairness_report")
    return fairness, adaptive


def _fairness_from_optional_only(
    payload: GovernanceAccountabilityInput,
    *,
    gaps: list[str],
) -> FairnessAssessmentSummary | None:
    if payload.distributional_report is None and payload.causal_fairness_report is None:
        return None
    notes: list[str] = []
    if (
        payload.distributional_report is not None
        and payload.distributional_report.overall_gini_delta is not None
    ):
        notes.append(
            f"distributional_overall_gini_delta={payload.distributional_report.overall_gini_delta:.4f}"
        )
    fairness = FairnessAssessmentSummary(
        counterfactual_fairness_satisfied=(
            None
            if payload.causal_fairness_report is None
            else payload.causal_fairness_report.counterfactual_fairness_satisfied
        ),
        counterfactual_direct_discrimination=(
            None
            if payload.causal_fairness_report is None
            else float(payload.causal_fairness_report.direct_discrimination)
        ),
        primary_unfair_pathway=(
            None
            if payload.causal_fairness_report is None
            else payload.causal_fairness_report.primary_unfair_pathway
        ),
        notes=notes,
        gaps=["missing_probabilistic_group_metrics"],
    )
    gaps.append("missing_probabilistic_group_metrics")
    return fairness


def _build_risk_summary(
    payload: GovernanceAccountabilityInput,
    *,
    stress_summary: Mapping[str, Any] | None,
    gaps: list[str],
) -> RiskAssessmentSummary | None:
    if payload.tail_risk_summary is None and not stress_summary:
        return None

    notes: list[str] = []
    risk = RiskAssessmentSummary(
        worst_stress_scenario=_as_non_empty_str((stress_summary or {}).get("worst_scenario")),
        stress_critical_count=int((stress_summary or {}).get("critical_count", 0) or 0),
        stress_high_count=int((stress_summary or {}).get("high_count", 0) or 0),
        notes=notes,
        gaps=[],
    )
    if payload.tail_risk_summary is None:
        risk.gaps.append("missing_tail_risk_summary")
        gaps.append("missing_tail_risk_summary")
        return risk

    worst_entry = max(
        payload.tail_risk_summary.entries,
        key=lambda item: (
            max(0.0, float(item.expected_shortfall_delta or 0.0)),
            max(0.0, float(item.exceedance_probability_delta)),
            float(item.baseline_quantile),
        ),
    )
    cvar_level = 1.0 - float(worst_entry.baseline_quantile)
    risk.tail_exceedance_delta = max(0.0, float(worst_entry.exceedance_probability_delta))
    risk.cvar_level = cvar_level
    risk.baseline_cvar = worst_entry.baseline_expected_shortfall
    risk.counterfactual_cvar = worst_entry.counterfactual_expected_shortfall
    risk.cvar_delta = (
        None
        if worst_entry.expected_shortfall_delta is None
        else max(0.0, float(worst_entry.expected_shortfall_delta))
    )
    return risk


def _build_model_card(
    payload: GovernanceAccountabilityInput,
    *,
    calibration: CalibrationMetricsSummary | None,
    fairness: FairnessAssessmentSummary | None,
    composite_score: float | None,
) -> ModelCardSection:
    primary_metrics: dict[str, float] = {}
    if calibration is not None:
        for key in ("brier_score", "log_score", "ece", "ence"):
            value = getattr(calibration, key)
            if value is not None:
                primary_metrics[key] = float(value)
    if fairness is not None and fairness.equalized_odds_gap is not None:
        primary_metrics["equalized_odds_gap"] = float(fairness.equalized_odds_gap)
    if composite_score is not None and math.isfinite(float(composite_score)):
        primary_metrics["composite_score"] = float(composite_score)
    return ModelCardSection(
        candidate_id=payload.candidate_id,
        model_name=payload.model_name,
        model_version=payload.model_version,
        intended_use=payload.intended_use,
        evaluation_split=payload.evaluation_split,
        primary_metrics=primary_metrics,
        limitations=list(payload.known_limitations),
    )


def _build_datasheet(
    payload: GovernanceAccountabilityInput,
    *,
    sample_count: int | None,
) -> DataSheetSection:
    return DataSheetSection(
        dataset_name=payload.dataset_name,
        dataset_version=payload.dataset_version,
        sample_count=sample_count,
        protected_attributes=sorted(payload.protected_attributes.keys()),
        data_sources=list(payload.data_sources),
        known_coverage_limits=list(payload.known_limitations),
    )


def _build_escalation_policy(
    *,
    governance_verdict: str,
    threshold_registry: Sequence[GovernanceThresholdEntry],
    failed_adversarial: Sequence[str],
    gaps: Sequence[str],
    risk_weighted_verdict: str,
) -> ProbabilisticEscalationPolicy:
    triggers: list[str] = []
    if governance_verdict == "human_gate":
        triggers.append("governance_requested_human_review")
    triggers.extend(
        f"threshold_violation:{entry.threshold_id}"
        for entry in threshold_registry
        if entry.passed is False and entry.severity == "human_gate"
    )
    triggers.extend(f"adversarial_failure:{alias}" for alias in failed_adversarial)
    if "missing_group_labels" in gaps:
        triggers.append("missing_group_labels")
    if "missing_probabilistic_outputs" in gaps:
        triggers.append("missing_probabilistic_outputs")
    requires_human_review = risk_weighted_verdict == "human_gate" or bool(triggers)
    recommended_action = (
        "Require human review before promotion or deployment."
        if requires_human_review
        else "No additional probabilistic escalation is required beyond standard governance."
    )
    rationale = (
        "Escalation is triggered when fairness-sensitive thresholds fail, when governance already requested review, or when the evidence surface is incomplete for probabilistic claims."
        if requires_human_review
        else "No fairness-sensitive threshold or evidence-gap trigger required escalation."
    )
    return ProbabilisticEscalationPolicy(
        requires_human_review=requires_human_review,
        escalation_triggers=sorted(set(triggers)),
        recommended_action=recommended_action,
        rationale=rationale,
        documented_rules=[
            "Escalate when governance already returns human_gate.",
            "Escalate when human-gate fairness thresholds fail at the selected operating point.",
            "Escalate when default-path probabilistic claims lack the minimum evidence surface required for external audit.",
        ],
    )


def _build_reliability_bins(
    scores: Sequence[float],
    outcomes: Sequence[float],
    *,
    n_bins: int = 10,
) -> list[CalibrationCurveBin]:
    bins: list[CalibrationCurveBin] = []
    for index in range(n_bins):
        lower = index / n_bins
        upper = (index + 1) / n_bins
        members = [
            (score, outcome)
            for score, outcome in zip(scores, outcomes)
            if (lower <= score < upper) or (index == n_bins - 1 and lower <= score <= upper)
        ]
        if not members:
            bins.append(CalibrationCurveBin(lower=lower, upper=upper, count=0))
            continue
        mean_predicted = sum(score for score, _ in members) / len(members)
        mean_observed = sum(outcome for _, outcome in members) / len(members)
        bins.append(
            CalibrationCurveBin(
                lower=lower,
                upper=upper,
                count=len(members),
                mean_predicted=mean_predicted,
                mean_observed=mean_observed,
                absolute_gap=abs(mean_predicted - mean_observed),
            )
        )
    return bins


def _compute_ence(
    scores: Sequence[float],
    outcomes: Sequence[float],
    uncertainties: Sequence[float],
    *,
    n_bins: int = 10,
) -> float:
    ranked = sorted(zip(uncertainties, scores, outcomes), key=lambda item: item[0])
    if not ranked:
        return 0.0
    chunk_size = max(1, math.ceil(len(ranked) / n_bins))
    errors: list[float] = []
    for start in range(0, len(ranked), chunk_size):
        chunk = ranked[start : start + chunk_size]
        mean_uncertainty = sum(item[0] for item in chunk) / len(chunk)
        rmse = math.sqrt(sum((item[1] - item[2]) ** 2 for item in chunk) / len(chunk))
        if mean_uncertainty <= _EPSILON:
            continue
        errors.append(abs(mean_uncertainty - rmse) / mean_uncertainty)
    return 0.0 if not errors else sum(errors) / len(errors)


def _group_calibration_summaries(
    *,
    scores: Sequence[float],
    outcomes: Sequence[float],
    protected_attributes: Mapping[str, Sequence[str]],
) -> list[GroupCalibrationSummary]:
    summaries: list[GroupCalibrationSummary] = []
    if not protected_attributes:
        return summaries
    clipped_outcomes = [_clip_probability(value) for value in outcomes]
    for axis, values in sorted(protected_attributes.items()):
        grouped_indices: dict[str, list[int]] = defaultdict(list)
        for index, value in enumerate(values):
            grouped_indices[str(value)].append(index)
        for group_value, indices in sorted(grouped_indices.items()):
            group_scores = [scores[index] for index in indices]
            group_outcomes = [clipped_outcomes[index] for index in indices]
            count = len(indices)
            mean_score = sum(group_scores) / max(count, 1)
            positive_rate = sum(group_outcomes) / max(count, 1)
            brier = sum(
                (score - outcome) ** 2 for score, outcome in zip(group_scores, group_outcomes)
            ) / max(count, 1)
            log_score = -sum(
                outcome * math.log(score + _EPSILON)
                + (1.0 - outcome) * math.log(1.0 - score + _EPSILON)
                for score, outcome in zip(group_scores, group_outcomes)
            ) / max(count, 1)
            summaries.append(
                GroupCalibrationSummary(
                    group_axis=axis,
                    group_value=group_value,
                    count=count,
                    positive_rate=positive_rate,
                    mean_score=mean_score,
                    calibration_gap=mean_score - positive_rate,
                    brier_score=brier,
                    log_score=log_score,
                )
            )
    return summaries


def _select_threshold(
    scores: Sequence[float],
    outcomes: Sequence[int],
    protected_attributes: Mapping[str, Sequence[str]],
) -> AdaptiveThresholdSummary:
    candidate_thresholds = [round(step / 20, 2) for step in range(1, 20)]
    points: list[ThresholdTradeoffPoint] = []
    for threshold in candidate_thresholds:
        accuracy, balanced_accuracy = _classification_quality(scores, outcomes, threshold)
        equalized_odds_gap, demographic_parity_gap = _fairness_gaps_for_threshold(
            scores=scores,
            outcomes=outcomes,
            protected_attributes=protected_attributes,
            threshold=threshold,
        )
        points.append(
            ThresholdTradeoffPoint(
                threshold=threshold,
                accuracy=accuracy,
                balanced_accuracy=balanced_accuracy,
                equalized_odds_gap=equalized_odds_gap,
                demographic_parity_gap=demographic_parity_gap,
            )
        )
    selected = max(
        points,
        key=lambda item: (
            item.balanced_accuracy - 0.5 * item.equalized_odds_gap,
            item.accuracy,
            -abs(item.threshold - 0.5),
        ),
    )
    frontier = _pareto_frontier(points)
    selected_threshold = selected.threshold
    selected_frontier = []
    for point in frontier:
        selected_frontier.append(
            point.model_copy(update={"selected": abs(point.threshold - selected_threshold) < 1e-9})
        )
    return AdaptiveThresholdSummary(
        threshold=selected_threshold,
        source="adaptive" if protected_attributes else "default",
        selection_objective="maximize balanced accuracy while minimizing equalized-odds gap",
        rationale=(
            "Threshold selected from a deterministic grid to balance accuracy against fairness gaps rather than fixing an unexplained 0.5 cutoff."
        ),
        expected_accuracy=selected.accuracy,
        expected_equalized_odds_gap=selected.equalized_odds_gap,
        frontier=selected_frontier,
    )


def _classification_quality(
    scores: Sequence[float],
    outcomes: Sequence[int],
    threshold: float,
) -> tuple[float, float]:
    predictions = [1 if score >= threshold else 0 for score in scores]
    total = len(predictions)
    correct = sum(1 for pred, outcome in zip(predictions, outcomes) if pred == outcome)
    tp = sum(1 for pred, outcome in zip(predictions, outcomes) if pred == 1 and outcome == 1)
    tn = sum(1 for pred, outcome in zip(predictions, outcomes) if pred == 0 and outcome == 0)
    fp = sum(1 for pred, outcome in zip(predictions, outcomes) if pred == 1 and outcome == 0)
    fn = sum(1 for pred, outcome in zip(predictions, outcomes) if pred == 0 and outcome == 1)
    tpr = tp / max(tp + fn, 1)
    tnr = tn / max(tn + fp, 1)
    return correct / max(total, 1), (tpr + tnr) / 2.0


def _fairness_gaps_for_threshold(
    *,
    scores: Sequence[float],
    outcomes: Sequence[int],
    protected_attributes: Mapping[str, Sequence[str]],
    threshold: float,
) -> tuple[float, float]:
    if not protected_attributes:
        return 0.0, 0.0
    axis = next(iter(sorted(protected_attributes.keys())), None)
    if axis is None:
        return 0.0, 0.0
    values = protected_attributes[axis]
    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index, value in enumerate(values):
        grouped_indices[str(value)].append(index)
    tprs: list[float] = []
    fprs: list[float] = []
    positive_rates: list[float] = []
    for indices in grouped_indices.values():
        preds = [1 if scores[index] >= threshold else 0 for index in indices]
        group_outcomes = [outcomes[index] for index in indices]
        tp = sum(1 for pred, outcome in zip(preds, group_outcomes) if pred == 1 and outcome == 1)
        fp = sum(1 for pred, outcome in zip(preds, group_outcomes) if pred == 1 and outcome == 0)
        fn = sum(1 for pred, outcome in zip(preds, group_outcomes) if pred == 0 and outcome == 1)
        tn = sum(1 for pred, outcome in zip(preds, group_outcomes) if pred == 0 and outcome == 0)
        tprs.append(tp / max(tp + fn, 1))
        fprs.append(fp / max(fp + tn, 1))
        positive_rates.append(sum(preds) / max(len(preds), 1))
    equalized_odds_gap = max(max(tprs) - min(tprs), max(fprs) - min(fprs))
    demographic_parity_gap = max(positive_rates) - min(positive_rates)
    return equalized_odds_gap, demographic_parity_gap


def _intersectional_positive_rate_gap(
    *,
    scores: Sequence[float],
    protected_attributes: Mapping[str, Sequence[str]],
    threshold: float,
) -> float:
    if len(protected_attributes) < 2:
        return 0.0
    axes = sorted(protected_attributes.keys())
    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index in range(len(scores)):
        key = "|".join(str(protected_attributes[axis][index]) for axis in axes)
        grouped_indices[key].append(index)
    rates = []
    for indices in grouped_indices.values():
        preds = [1 if scores[index] >= threshold else 0 for index in indices]
        rates.append(sum(preds) / max(len(preds), 1))
    return 0.0 if not rates else max(rates) - min(rates)


def _pareto_frontier(points: Sequence[ThresholdTradeoffPoint]) -> list[ThresholdTradeoffPoint]:
    frontier: list[ThresholdTradeoffPoint] = []
    for candidate in points:
        dominated = False
        for other in points:
            if other is candidate:
                continue
            if (
                other.accuracy >= candidate.accuracy
                and other.equalized_odds_gap <= candidate.equalized_odds_gap
                and (
                    other.accuracy > candidate.accuracy
                    or other.equalized_odds_gap < candidate.equalized_odds_gap
                )
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return sorted(
        frontier,
        key=lambda item: (-item.accuracy, item.equalized_odds_gap, item.threshold),
    )


def _resolve_risk_weighted_verdict(
    *,
    governance_verdict: str,
    threshold_registry: Sequence[GovernanceThresholdEntry],
    eligible_for_promotion: bool | None,
) -> Literal["approve", "needs_revision", "reject", "human_gate"]:
    normalized = str(governance_verdict or "").strip().lower()
    if normalized in {"reject", "human_gate"}:
        return "human_gate" if normalized == "human_gate" else "reject"
    if any(
        entry.passed is False and entry.severity == "human_gate" for entry in threshold_registry
    ):
        return "human_gate"
    if any(entry.passed is False and entry.severity == "blocker" for entry in threshold_registry):
        return "reject"
    if normalized == "needs_revision":
        return "needs_revision"
    if eligible_for_promotion is False:
        return "needs_revision"
    if any(entry.passed is False for entry in threshold_registry):
        return "needs_revision"
    return "approve"


def _evaluate_threshold(
    observed_value: float,
    comparator: Literal["<=", ">=", "<", ">"],
    threshold_value: float,
) -> bool:
    if comparator == "<=":
        return observed_value <= threshold_value
    if comparator == ">=":
        return observed_value >= threshold_value
    if comparator == "<":
        return observed_value < threshold_value
    return observed_value > threshold_value


def _issue_codes(issues: Sequence[ComplianceIssue | Mapping[str, Any]]) -> list[str]:
    codes: list[str] = []
    for issue in issues:
        if isinstance(issue, ComplianceIssue):
            code = issue.code
        elif isinstance(issue, Mapping):
            code = issue.get("code")
        else:
            code = getattr(issue, "code", None)
        if code:
            codes.append(str(code))
    return sorted(set(codes))


def _failed_adversarial_aliases(results: Sequence[Mapping[str, Any] | BaseModel]) -> list[str]:
    failed: list[str] = []
    for result in results:
        alias = None
        status = None
        if isinstance(result, Mapping):
            alias = result.get("alias")
            status = result.get("status")
        else:
            alias = getattr(result, "alias", None)
            status = getattr(result, "status", None)
        if alias and status and str(status) != "passed":
            failed.append(str(alias))
    return sorted(set(failed))


def _coerce_float(value: Any) -> float | None:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(candidate):
        return None
    return candidate


def _clip_probability(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _as_non_empty_str(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


__all__ = [
    "AdaptiveThresholdSummary",
    "CalibrationCurveBin",
    "CalibrationMetricsSummary",
    "DataSheetSection",
    "FairnessAssessmentSummary",
    "GovernanceAccountabilityArtifact",
    "GovernanceAccountabilityInput",
    "GovernanceThresholdEntry",
    "GroupCalibrationSummary",
    "ModelCardSection",
    "ProbabilisticEscalationPolicy",
    "RiskAssessmentSummary",
    "ThresholdTradeoffPoint",
    "build_governance_accountability_artifact",
    "load_governance_accountability_artifact",
    "persist_governance_accountability_artifact",
    "resolve_governance_threshold",
]
