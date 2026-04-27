"""Estimated performance-degradation monitors for delayed-label settings."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ddm_15_7.integration.events import (
    MetricDirection,
    PerformanceDegradationEvent,
)
from polisyos.ddm_15_7.readiness.readiness_mapper import MetricBudgetPolicy, metric_budget_used

if TYPE_CHECKING:
    from collections.abc import Sequence


class BinaryPredictionRecord(BaseModel):
    """Prediction-time record for calibrated binary classifiers."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    timestamp: datetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    probability: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    slice_keys: dict[str, str] = Field(default_factory=dict)


class RegressionLossEstimate(BaseModel):
    """Prediction-time DLE-style loss estimate for regression models."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    timestamp: datetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    predicted_loss: float = Field(ge=0.0)
    slice_keys: dict[str, str] = Field(default_factory=dict)


def estimate_binary_classification_degradation(
    *,
    predictions: list[BinaryPredictionRecord],
    budget: MetricBudgetPolicy,
    metric: Literal["accuracy", "error_rate", "brier"] = "accuracy",
    probabilities_calibrated: bool = True,
    label_delay_days: list[float] | None = None,
    corroborating_shift_event_ids: list[str] | None = None,
    calibration_id: str | None = None,
    timestamp: datetime | None = None,
) -> PerformanceDegradationEvent:
    """Estimate classifier performance before labels arrive.

    This is a compact CBPE-style estimator: calibrated probabilities define the
    expected correctness/loss contribution for each prediction. The function is
    intentionally explicit about the calibration assumption because uncalibrated
    scores should not be used as performance estimates.
    """

    if not probabilities_calibrated:
        raise ValueError("CBPE-style estimation requires calibrated probabilities")
    _require_records(predictions)
    if budget.metric != metric:
        raise ValueError("metric must match the supplied metric budget")

    values = [_binary_metric_contribution(record, metric) for record in predictions]
    current, interval = _mean_interval(values)
    budget_used = metric_budget_used(
        metric_direction=budget.metric_direction,
        reference_value=budget.reference_value,
        current_estimate=current,
        confidence_interval_95=interval,
        minimum_acceptable_value=budget.minimum_acceptable_value,
        maximum_acceptable_value=budget.maximum_acceptable_value,
    )
    event_time = timestamp or datetime.now(UTC)
    return PerformanceDegradationEvent(
        event_id=f"estimated-{budget.model_id}-{budget.model_version}-{metric}-{event_time.isoformat()}",
        timestamp=event_time,
        model_id=budget.model_id,
        model_version=budget.model_version,
        metric=metric,
        metric_direction=budget.metric_direction,
        source="estimated_performance",
        estimator="cbpe",
        reference_value=budget.reference_value,
        minimum_acceptable_value=budget.minimum_acceptable_value,
        maximum_acceptable_value=budget.maximum_acceptable_value,
        current_estimate=current,
        confidence_interval_95=interval,
        budget_used=budget_used,
        label_delay_days_p50=_quantile_or_none(label_delay_days, 0.50),
        label_delay_days_p90=_quantile_or_none(label_delay_days, 0.90),
        corroborating_shift_event_ids=list(corroborating_shift_event_ids or []),
        calibration_id=calibration_id,
    )


def estimate_regression_loss_degradation(
    *,
    losses: list[RegressionLossEstimate],
    budget: MetricBudgetPolicy,
    label_delay_days: list[float] | None = None,
    corroborating_shift_event_ids: list[str] | None = None,
    calibration_id: str | None = None,
    timestamp: datetime | None = None,
) -> PerformanceDegradationEvent:
    """Estimate lower-is-better regression loss before targets arrive."""

    _require_records(losses)
    if budget.metric_direction is not MetricDirection.LOWER_IS_BETTER:
        raise ValueError("DLE-style regression loss budgets must be lower-is-better")

    values = [record.predicted_loss for record in losses]
    current, interval = _mean_interval(values)
    budget_used = metric_budget_used(
        metric_direction=budget.metric_direction,
        reference_value=budget.reference_value,
        current_estimate=current,
        confidence_interval_95=interval,
        minimum_acceptable_value=budget.minimum_acceptable_value,
        maximum_acceptable_value=budget.maximum_acceptable_value,
    )
    event_time = timestamp or datetime.now(UTC)
    return PerformanceDegradationEvent(
        event_id=f"estimated-{budget.model_id}-{budget.model_version}-{budget.metric}-{event_time.isoformat()}",
        timestamp=event_time,
        model_id=budget.model_id,
        model_version=budget.model_version,
        metric=budget.metric,
        metric_direction=budget.metric_direction,
        source="estimated_performance",
        estimator="dle",
        reference_value=budget.reference_value,
        minimum_acceptable_value=budget.minimum_acceptable_value,
        maximum_acceptable_value=budget.maximum_acceptable_value,
        current_estimate=current,
        confidence_interval_95=interval,
        budget_used=budget_used,
        label_delay_days_p50=_quantile_or_none(label_delay_days, 0.50),
        label_delay_days_p90=_quantile_or_none(label_delay_days, 0.90),
        corroborating_shift_event_ids=list(corroborating_shift_event_ids or []),
        calibration_id=calibration_id,
    )


def _binary_metric_contribution(
    record: BinaryPredictionRecord,
    metric: Literal["accuracy", "error_rate", "brier"],
) -> float:
    predicted_positive = record.probability >= record.threshold
    expected_accuracy = record.probability if predicted_positive else 1.0 - record.probability
    if metric == "accuracy":
        return expected_accuracy
    if metric == "error_rate":
        return 1.0 - expected_accuracy
    return record.probability * (1.0 - record.probability)


def _mean_interval(values: list[float]) -> tuple[float, tuple[float, float]]:
    if not values:
        raise ValueError("at least one value is required")
    n = len(values)
    mean = sum(values) / n
    if n == 1:
        return mean, (mean, mean)
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    half_width = 1.96 * math.sqrt(variance / n)
    return mean, (mean - half_width, mean + half_width)


def _quantile_or_none(values: list[float] | None, q: float) -> float | None:
    if not values:
        return None
    return _quantile(values, q)


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("at least one value is required")
    position = q * (len(ordered) - 1)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    fraction = position - lower_index
    return ordered[lower_index] * (1.0 - fraction) + ordered[upper_index] * fraction


def _require_records(records: Sequence[object]) -> None:
    if not records:
        raise ValueError("at least one prediction record is required")
