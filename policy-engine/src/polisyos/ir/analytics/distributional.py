from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import DistributionalReportRef


class CohortDimension(str, Enum):
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
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class MetricUnit(str, Enum):
    PERCENT = "percent"
    RATIO = "ratio"
    ABSOLUTE = "absolute"


class CohortImpact(BaseModel):
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
            object.__setattr__(self, "overall_gini_delta", self.overall_gini_after - self.overall_gini_before)
        if (
            self.palma_ratio_before is not None
            and self.palma_ratio_after is not None
            and self.palma_ratio_delta is None
        ):
            object.__setattr__(self, "palma_ratio_delta", self.palma_ratio_after - self.palma_ratio_before)
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


def persist_distributional_report(
    store: ArtifactStore,
    report: DistributionalReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.distributional_report",
    schema_version: str = "1.0",
) -> DistributionalReportRef:
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
    payload = get_json_artifact(store, ref.artifact_id)
    return DistributionalReport.model_validate(payload)


__all__ = [
    "CohortDimension",
    "CohortImpact",
    "DimensionBreakdown",
    "DistributionalReport",
    "ImpactDirection",
    "MetricUnit",
    "WinnersLosersEntry",
    "WinnersLosersTable",
    "persist_distributional_report",
    "load_distributional_report",
]
