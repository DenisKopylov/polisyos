"""Public analytics distributional module API."""
from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    ArtifactRefModel,
    DistributionalEffectBundleRef,
    DistributionalReportRef,
)

_DISTRIBUTIONAL_REPORT_SCHEMA_NAME = "ir.distributional_report"
_DISTRIBUTIONAL_REPORT_SCHEMA_VERSION = "1.0"
_DISTRIBUTIONAL_EFFECT_BUNDLE_SCHEMA_NAME = "ir.distributional_effect_bundle"
_DISTRIBUTIONAL_EFFECT_BUNDLE_SCHEMA_VERSION = "1.0"
_DISCRETE_DISTRIBUTION_SUMMARY_SCHEMA_NAME = "ir.discrete_distribution_summary"
_DISCRETE_DISTRIBUTION_SUMMARY_SCHEMA_VERSION = "1.0"
_OT_COUPLING_SUMMARY_SCHEMA_NAME = "ir.ot_coupling_summary"
_OT_COUPLING_SUMMARY_SCHEMA_VERSION = "1.0"
_QUANTILE_SHIFT_SUMMARY_SCHEMA_NAME = "ir.quantile_shift_summary"
_QUANTILE_SHIFT_SUMMARY_SCHEMA_VERSION = "1.0"
_TAIL_RISK_DELTA_SUMMARY_SCHEMA_NAME = "ir.tail_risk_delta_summary"
_TAIL_RISK_DELTA_SUMMARY_SCHEMA_VERSION = "1.0"
_SUBGROUP_DISTRIBUTION_COMPARISON_SCHEMA_NAME = "ir.subgroup_distribution_comparison"
_SUBGROUP_DISTRIBUTION_COMPARISON_SCHEMA_VERSION = "1.0"


def _ensure_finite(value: float | None, *, field_name: str) -> float | None:
    if value is None:
        return None
    casted = float(value)
    if not math.isfinite(casted):
        raise ValueError(f"{field_name} must be finite")
    return casted


def _ensure_non_empty(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _validate_unique_artifact_refs(
    refs: list[ArtifactRefModel],
    *,
    field_name: str,
) -> None:
    seen: set[str] = set()
    for ref in refs:
        artifact_id = str(ref.artifact_id)
        if artifact_id in seen:
            raise ValueError(f"{field_name} contains duplicate artifact_id {artifact_id}")
        seen.add(artifact_id)


def _persist_distributional_leaf(
    store: ArtifactStore,
    payload: BaseModel,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    ref = put_json_artifact(
        store,
        payload.model_dump(mode="json"),
        kind=kind,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref)


def _load_distributional_leaf(store: ArtifactStore, ref: ArtifactRefModel, model: type[BaseModel]) -> Any:
    payload = get_json_artifact(store, ref.artifact_id)
    return model.model_validate(payload)


class DistributionalJustification(str, Enum):
    """Distributional justification public type."""
    IDENTIFIED = "identified"
    BOUNDED = "bounded"
    SCENARIO = "scenario"


class CohortDimension(str, Enum):
    """Supported axes for distributional cohort breakdowns."""

    INCOME_QUINTILE = "income_quintile"
    INCOME_DECILE = "income_decile"
    GEOGRAPHY = "geography"
    AGE_GROUP = "age_group"
    GENDER = "gender"
    ETHNICITY = "ethnicity"
    EDUCATION = "education"
    EMPLOYMENT_STATUS = "employment_status"
    CUSTOM = "custom"


class ImpactDirection(str, Enum):
    """Coarse direction of a cohort or KPI impact."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class MetricUnit(str, Enum):
    """Display semantics for primary distributional metrics."""

    PERCENT = "percent"
    RATIO = "ratio"
    ABSOLUTE = "absolute"


class CouplingDiagnostics(BaseModel):
    """Coupling diagnostics public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    mass_conservation_error: float = Field(ge=0.0)
    source_marginal_l1_error: float = Field(default=0.0, ge=0.0)
    target_marginal_l1_error: float = Field(default=0.0, ge=0.0)
    support_mismatch_note: str | None = None
    regularization_strength: float | None = Field(default=None, gt=0.0)
    sinkhorn_iterations: int | None = Field(default=None, ge=0, le=200)
    convergence_delta: float | None = Field(default=None, ge=0.0)
    weighting_mode: str = Field(default="uniform", min_length=1)
    identifiability_assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_finite_numbers(self) -> "CouplingDiagnostics":
        for field_name in (
            "mass_conservation_error",
            "source_marginal_l1_error",
            "target_marginal_l1_error",
            "regularization_strength",
            "convergence_delta",
        ):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        _ensure_non_empty(self.support_mismatch_note, field_name="support_mismatch_note")
        _ensure_non_empty(self.weighting_mode, field_name="weighting_mode")
        return self


class DistributionBin(BaseModel):
    """Distribution bin public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    lower_edge: float
    upper_edge: float
    midpoint: float
    probability: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_bin(self) -> "DistributionBin":
        lower = _ensure_finite(self.lower_edge, field_name="lower_edge")
        upper = _ensure_finite(self.upper_edge, field_name="upper_edge")
        midpoint = _ensure_finite(self.midpoint, field_name="midpoint")
        _ensure_finite(self.probability, field_name="probability")
        if upper < lower:
            raise ValueError("upper_edge must be >= lower_edge")
        if midpoint < lower or midpoint > upper:
            raise ValueError("midpoint must fall within [lower_edge, upper_edge]")
        return self


class DiscreteDistributionSummary(BaseModel):
    """Discrete distribution summary data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    outcome_name: str = Field(min_length=1)
    sample_size: int = Field(ge=1)
    total_weight: float = Field(gt=0.0)
    weighting_mode: str = Field(min_length=1)
    mean_value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    bins: list[DistributionBin] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_distribution(self) -> "DiscreteDistributionSummary":
        _ensure_non_empty(self.outcome_name, field_name="outcome_name")
        _ensure_non_empty(self.weighting_mode, field_name="weighting_mode")
        for field_name in ("total_weight", "mean_value", "min_value", "max_value"):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        total_probability = sum(bin_.probability for bin_ in self.bins)
        if abs(total_probability - 1.0) > 1e-6:
            raise ValueError(
                f"distribution probabilities must sum to 1.0, got {total_probability:.8f}"
            )
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValueError("min_value must be <= max_value")
        return self


class QuantileShiftEntry(BaseModel):
    """Quantile shift entry data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    quantile: float = Field(ge=0.0, le=1.0)
    baseline_value: float
    counterfactual_value: float
    shift: float

    @model_validator(mode="after")
    def _validate_quantile_shift(self) -> "QuantileShiftEntry":
        for field_name in ("quantile", "baseline_value", "counterfactual_value", "shift"):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        return self


class QuantileShiftSummary(BaseModel):
    """Quantile shift summary data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    outcome_name: str = Field(min_length=1)
    entries: list[QuantileShiftEntry] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_summary(self) -> "QuantileShiftSummary":
        _ensure_non_empty(self.outcome_name, field_name="outcome_name")
        quantiles = [entry.quantile for entry in self.entries]
        if quantiles != sorted(quantiles):
            raise ValueError("quantile entries must be sorted in ascending order")
        return self


class TailRiskDeltaEntry(BaseModel):
    """Tail risk delta entry data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    baseline_quantile: float = Field(ge=0.0, le=1.0)
    threshold_value: float
    baseline_exceedance_probability: float = Field(ge=0.0, le=1.0)
    counterfactual_exceedance_probability: float = Field(ge=0.0, le=1.0)
    exceedance_probability_delta: float
    baseline_expected_shortfall: float | None = None
    counterfactual_expected_shortfall: float | None = None
    expected_shortfall_delta: float | None = None

    @model_validator(mode="after")
    def _validate_tail_entry(self) -> "TailRiskDeltaEntry":
        for field_name in (
            "baseline_quantile",
            "threshold_value",
            "baseline_exceedance_probability",
            "counterfactual_exceedance_probability",
            "exceedance_probability_delta",
            "baseline_expected_shortfall",
            "counterfactual_expected_shortfall",
            "expected_shortfall_delta",
        ):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        return self


class TailRiskDeltaSummary(BaseModel):
    """Tail risk delta summary data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    outcome_name: str = Field(min_length=1)
    entries: list[TailRiskDeltaEntry] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_summary(self) -> "TailRiskDeltaSummary":
        _ensure_non_empty(self.outcome_name, field_name="outcome_name")
        return self


class OTCouplingSummary(BaseModel):
    """OT coupling summary data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    source_support: tuple[float, ...]
    target_support: tuple[float, ...]
    transport_matrix: tuple[tuple[float, ...], ...]
    regularization_strength: float = Field(gt=0.0)
    sinkhorn_iterations: int = Field(ge=1, le=200)
    convergence_delta: float = Field(ge=0.0)
    weighting_mode: str = Field(min_length=1)
    density_ratio_diagnostics: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_coupling(self) -> "OTCouplingSummary":
        _ensure_finite(self.regularization_strength, field_name="regularization_strength")
        _ensure_finite(self.convergence_delta, field_name="convergence_delta")
        _ensure_non_empty(self.weighting_mode, field_name="weighting_mode")
        if not self.source_support:
            raise ValueError("source_support must be non-empty")
        if not self.target_support:
            raise ValueError("target_support must be non-empty")
        if len(self.transport_matrix) != len(self.source_support):
            raise ValueError("transport_matrix row count must match source_support")
        total_mass = 0.0
        for row in self.transport_matrix:
            if len(row) != len(self.target_support):
                raise ValueError("transport_matrix column count must match target_support")
            for value in row:
                finite_value = _ensure_finite(value, field_name="transport_matrix")
                if finite_value is None or finite_value < 0.0:
                    raise ValueError("transport_matrix entries must be finite and non-negative")
                total_mass += finite_value
        if abs(total_mass - 1.0) > 1e-4:
            raise ValueError(f"transport_matrix must sum to 1.0, got {total_mass:.8f}")
        return self


class SubgroupDistributionComparison(BaseModel):
    """Subgroup distribution comparison public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    subgroup_dimension: CohortDimension
    subgroup_id: str = Field(min_length=1)
    subgroup_label: str = Field(min_length=1)
    baseline_distribution_ref: ArtifactRefModel
    counterfactual_distribution_ref: ArtifactRefModel
    coupling_ref: ArtifactRefModel | None = None
    coupling_diagnostics: CouplingDiagnostics
    quantile_shift_ref: ArtifactRefModel | None = None
    tail_risk_delta_ref: ArtifactRefModel | None = None
    wasserstein_distance: float | None = Field(default=None, ge=0.0)
    baseline_sample_size: int = Field(ge=1)
    counterfactual_sample_size: int = Field(ge=1)
    causal_assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_subgroup(self) -> "SubgroupDistributionComparison":
        _ensure_non_empty(self.subgroup_id, field_name="subgroup_id")
        _ensure_non_empty(self.subgroup_label, field_name="subgroup_label")
        _ensure_finite(self.wasserstein_distance, field_name="wasserstein_distance")
        return self


class DistributionalEffectBundle(BaseModel):
    """Distributional effect bundle data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    outcome_name: str = Field(min_length=1)
    justification: DistributionalJustification
    baseline_distribution_ref: ArtifactRefModel
    counterfactual_distribution_ref: ArtifactRefModel
    coupling_ref: ArtifactRefModel | None = None
    coupling_diagnostics: CouplingDiagnostics
    wasserstein_distance: float | None = Field(default=None, ge=0.0)
    quantile_shift_ref: ArtifactRefModel | None = None
    tail_risk_delta_ref: ArtifactRefModel | None = None
    subgroup_distribution_refs: list[ArtifactRefModel] = Field(default_factory=list)
    causal_assumptions: list[str] = Field(default_factory=list)
    readiness_cap: str = Field(default="simulation_ready", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bundle(self) -> "DistributionalEffectBundle":
        _ensure_non_empty(self.outcome_name, field_name="outcome_name")
        _ensure_non_empty(self.readiness_cap, field_name="readiness_cap")
        _ensure_finite(self.wasserstein_distance, field_name="wasserstein_distance")
        _validate_unique_artifact_refs(
            self.subgroup_distribution_refs,
            field_name="subgroup_distribution_refs",
        )
        return self


class CohortImpact(BaseModel):
    """Distributional impact summary for one cohort within a breakdown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cohort_id: str = Field(min_length=1)
    cohort_label: str = Field(min_length=1)
    population_share: float = Field(ge=0.0, le=1.0)
    metric_values: dict[str, float] = Field(default_factory=dict)
    metric_deltas: dict[str, float] = Field(default_factory=dict)
    impact_direction: ImpactDirection = ImpactDirection.NEUTRAL
    is_vulnerable: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_finite_numbers(self) -> "CohortImpact":
        for bucket_name, bucket in (
            ("metric_values", self.metric_values),
            ("metric_deltas", self.metric_deltas),
        ):
            for key, value in bucket.items():
                if not math.isfinite(value):
                    raise ValueError(f"{bucket_name}.{key} must be finite")
        return self


class DimensionBreakdown(BaseModel):
    """Distributional comparison grouped by one cohort dimension."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: CohortDimension
    dimension_label: str = Field(min_length=1)
    cohorts: list[CohortImpact] = Field(min_length=2)
    primary_metric: str = Field(min_length=1)
    primary_metric_unit: MetricUnit = MetricUnit.PERCENT
    gini_before: float | None = Field(default=None, ge=0.0, le=1.0)
    gini_after: float | None = Field(default=None, ge=0.0, le=1.0)
    gini_delta: float | None = None

    @model_validator(mode="after")
    def _validate_population_shares(self) -> "DimensionBreakdown":
        total = sum(cohort.population_share for cohort in self.cohorts)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Population shares must sum to ~1.0, got {total:.4f}")
        return self

    @model_validator(mode="after")
    def _validate_unique_cohort_ids(self) -> "DimensionBreakdown":
        seen: set[str] = set()
        for cohort in self.cohorts:
            if cohort.cohort_id in seen:
                raise ValueError(f"Duplicate cohort_id within dimension: {cohort.cohort_id}")
            seen.add(cohort.cohort_id)
        return self

    @model_validator(mode="after")
    def _validate_primary_metric_exists(self) -> "DimensionBreakdown":
        for cohort in self.cohorts:
            if self.primary_metric not in cohort.metric_deltas:
                raise ValueError(
                    f"Cohort {cohort.cohort_id} missing primary metric '{self.primary_metric}'"
                )
        return self

    @model_validator(mode="after")
    def _compute_gini_delta(self) -> "DimensionBreakdown":
        if (
            self.gini_before is not None
            and self.gini_after is not None
            and self.gini_delta is None
        ):
            object.__setattr__(self, "gini_delta", self.gini_after - self.gini_before)
        return self


class WinnersLosersEntry(BaseModel):
    """Flattened cohort record used in winners/losers summaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cohort_id: str
    cohort_label: str
    dimension: CohortDimension
    net_impact: float
    impact_direction: ImpactDirection
    population_share: float = Field(ge=0.0, le=1.0)
    is_vulnerable: bool = False
    key_metric: str = ""
    key_metric_delta: float = 0.0


class WinnersLosersTable(BaseModel):
    """Partition of affected cohorts into winners, losers, and neutral groups."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    winners: list[WinnersLosersEntry] = Field(default_factory=list)
    losers: list[WinnersLosersEntry] = Field(default_factory=list)
    neutral: list[WinnersLosersEntry] = Field(default_factory=list)
    canonical_dimension: CohortDimension | None = None

    @property
    def total_winners_share(self) -> float:
        return sum(entry.population_share for entry in self.winners)

    @property
    def total_losers_share(self) -> float:
        return sum(entry.population_share for entry in self.losers)

    @property
    def vulnerable_losers(self) -> list[WinnersLosersEntry]:
        return [entry for entry in self.losers if entry.is_vulnerable]


class DistributionalReport(BaseModel):
    """Top-level distributional impact report for a policy evaluation run."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "title": "DistributionalReport",
            "description": "Distributional impact analysis report for policy evaluation.",
        },
    )

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    breakdowns: list[DimensionBreakdown] = Field(min_length=1)
    winners_losers: WinnersLosersTable = Field(default_factory=WinnersLosersTable)

    overall_gini_before: float | None = Field(default=None, ge=0.0, le=1.0)
    overall_gini_after: float | None = Field(default=None, ge=0.0, le=1.0)
    overall_gini_delta: float | None = None

    palma_ratio_before: float | None = Field(default=None, ge=0.0)
    palma_ratio_after: float | None = Field(default=None, ge=0.0)
    palma_ratio_delta: float | None = None

    source_simulation_ref: str | None = None
    methodology: str = "agent_aggregation"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _compute_overall_deltas(self) -> "DistributionalReport":
        if (
            self.overall_gini_before is not None
            and self.overall_gini_after is not None
            and self.overall_gini_delta is None
        ):
            object.__setattr__(
                self,
                "overall_gini_delta",
                self.overall_gini_after - self.overall_gini_before,
            )
        if (
            self.palma_ratio_before is not None
            and self.palma_ratio_after is not None
            and self.palma_ratio_delta is None
        ):
            object.__setattr__(
                self,
                "palma_ratio_delta",
                self.palma_ratio_after - self.palma_ratio_before,
            )
        return self

    def get_breakdown(self, dimension: CohortDimension) -> DimensionBreakdown | None:
        for breakdown in self.breakdowns:
            if breakdown.dimension == dimension:
                return breakdown
        return None

    def has_equity_concerns(
        self,
        *,
        gini_threshold: float = 0.02,
        vulnerable_loss_threshold_pct: float = -5.0,
    ) -> bool:
        if self.overall_gini_delta is not None and self.overall_gini_delta > gini_threshold:
            return True
        for loser in self.winners_losers.vulnerable_losers:
            if loser.net_impact < vulnerable_loss_threshold_pct:
                return True
        return False


def persist_discrete_distribution_summary(
    store: ArtifactStore,
    summary: DiscreteDistributionSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist discrete distribution summary helper."""
    return _persist_distributional_leaf(
        store,
        summary,
        kind="ir.discrete_distribution_summary",
        schema_name=_DISCRETE_DISTRIBUTION_SUMMARY_SCHEMA_NAME,
        schema_version=_DISCRETE_DISTRIBUTION_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_discrete_distribution_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> DiscreteDistributionSummary:
    """Load discrete distribution summary."""
    return _load_distributional_leaf(store, ref, DiscreteDistributionSummary)


def persist_ot_coupling_summary(
    store: ArtifactStore,
    summary: OTCouplingSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist ot coupling summary helper."""
    return _persist_distributional_leaf(
        store,
        summary,
        kind="ir.ot_coupling_summary",
        schema_name=_OT_COUPLING_SUMMARY_SCHEMA_NAME,
        schema_version=_OT_COUPLING_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_ot_coupling_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> OTCouplingSummary:
    """Load ot coupling summary."""
    return _load_distributional_leaf(store, ref, OTCouplingSummary)


def persist_quantile_shift_summary(
    store: ArtifactStore,
    summary: QuantileShiftSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist quantile shift summary helper."""
    return _persist_distributional_leaf(
        store,
        summary,
        kind="ir.quantile_shift_summary",
        schema_name=_QUANTILE_SHIFT_SUMMARY_SCHEMA_NAME,
        schema_version=_QUANTILE_SHIFT_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_quantile_shift_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> QuantileShiftSummary:
    """Load quantile shift summary."""
    return _load_distributional_leaf(store, ref, QuantileShiftSummary)


def persist_tail_risk_delta_summary(
    store: ArtifactStore,
    summary: TailRiskDeltaSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist tail risk delta summary helper."""
    return _persist_distributional_leaf(
        store,
        summary,
        kind="ir.tail_risk_delta_summary",
        schema_name=_TAIL_RISK_DELTA_SUMMARY_SCHEMA_NAME,
        schema_version=_TAIL_RISK_DELTA_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_tail_risk_delta_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> TailRiskDeltaSummary:
    """Load tail risk delta summary."""
    return _load_distributional_leaf(store, ref, TailRiskDeltaSummary)


def persist_subgroup_distribution_comparison(
    store: ArtifactStore,
    comparison: SubgroupDistributionComparison,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist subgroup distribution comparison helper."""
    return _persist_distributional_leaf(
        store,
        comparison,
        kind="ir.subgroup_distribution_comparison",
        schema_name=_SUBGROUP_DISTRIBUTION_COMPARISON_SCHEMA_NAME,
        schema_version=_SUBGROUP_DISTRIBUTION_COMPARISON_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_subgroup_distribution_comparison(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> SubgroupDistributionComparison:
    """Load subgroup distribution comparison."""
    return _load_distributional_leaf(store, ref, SubgroupDistributionComparison)


def persist_distributional_effect_bundle(
    store: ArtifactStore,
    bundle: DistributionalEffectBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> DistributionalEffectBundleRef:
    """Persist distributional effect bundle helper."""
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.distributional_effect_bundle",
        schema_name=_DISTRIBUTIONAL_EFFECT_BUNDLE_SCHEMA_NAME,
        schema_version=_DISTRIBUTIONAL_EFFECT_BUNDLE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DistributionalEffectBundleRef.model_validate(ref)


def load_distributional_effect_bundle(
    store: ArtifactStore,
    ref: DistributionalEffectBundleRef,
) -> DistributionalEffectBundle:
    """Load distributional effect bundle."""
    payload = get_json_artifact(store, ref.artifact_id)
    return DistributionalEffectBundle.model_validate(payload)


def persist_distributional_report(
    store: ArtifactStore,
    report: DistributionalReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _DISTRIBUTIONAL_REPORT_SCHEMA_NAME,
    schema_version: str = _DISTRIBUTIONAL_REPORT_SCHEMA_VERSION,
) -> DistributionalReportRef:
    """Persist distributional report helper."""
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.distributional_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DistributionalReportRef.model_validate(ref)


def load_distributional_report(
    store: ArtifactStore,
    ref: DistributionalReportRef,
) -> DistributionalReport:
    """Load distributional report."""
    payload = get_json_artifact(store, ref.artifact_id)
    return DistributionalReport.model_validate(payload)


__all__ = [
    "CohortDimension",
    "CohortImpact",
    "CouplingDiagnostics",
    "DimensionBreakdown",
    "DiscreteDistributionSummary",
    "DistributionBin",
    "DistributionalEffectBundle",
    "DistributionalJustification",
    "DistributionalReport",
    "ImpactDirection",
    "MetricUnit",
    "OTCouplingSummary",
    "QuantileShiftEntry",
    "QuantileShiftSummary",
    "SubgroupDistributionComparison",
    "TailRiskDeltaEntry",
    "TailRiskDeltaSummary",
    "WinnersLosersEntry",
    "WinnersLosersTable",
    "persist_discrete_distribution_summary",
    "load_discrete_distribution_summary",
    "persist_distributional_effect_bundle",
    "load_distributional_effect_bundle",
    "persist_distributional_report",
    "load_distributional_report",
    "persist_ot_coupling_summary",
    "load_ot_coupling_summary",
    "persist_quantile_shift_summary",
    "load_quantile_shift_summary",
    "persist_subgroup_distribution_comparison",
    "load_subgroup_distribution_comparison",
    "persist_tail_risk_delta_summary",
    "load_tail_risk_delta_summary",
]
