"""Canonical metric-budget contract for DDM-15.7."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ddm.contracts.events import MetricDirection


class MetricBudgetPolicy(BaseModel):
    """Primary metric budget for a deployed model version."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    metric_direction: MetricDirection
    reference_value: float
    minimum_acceptable_value: float | None = None
    maximum_acceptable_value: float | None = None

    @model_validator(mode="after")
    def _validate_floor_or_ceiling(self) -> MetricBudgetPolicy:
        if (
            self.metric_direction is MetricDirection.HIGHER_IS_BETTER
            and self.minimum_acceptable_value is None
        ):
            raise ValueError("higher-is-better budget requires minimum_acceptable_value")
        if (
            self.metric_direction is MetricDirection.LOWER_IS_BETTER
            and self.maximum_acceptable_value is None
        ):
            raise ValueError("lower-is-better budget requires maximum_acceptable_value")
        if (
            self.metric_direction is MetricDirection.HIGHER_IS_BETTER
            and self.minimum_acceptable_value is not None
            and self.reference_value <= self.minimum_acceptable_value
        ):
            raise ValueError("reference_value must be above minimum_acceptable_value")
        if (
            self.metric_direction is MetricDirection.LOWER_IS_BETTER
            and self.maximum_acceptable_value is not None
            and self.reference_value >= self.maximum_acceptable_value
        ):
            raise ValueError("reference_value must be below maximum_acceptable_value")
        return self
