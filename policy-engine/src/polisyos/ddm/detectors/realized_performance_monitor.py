"""Realized performance monitors for delayed-label streams."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ddm.integration.events import MetricDirection, PerformanceDegradationEvent
from polisyos.ddm.readiness.readiness_mapper import MetricBudgetPolicy, metric_budget_used

if TYPE_CHECKING:
    from collections.abc import Sequence


class LabeledBinaryPrediction(BaseModel):
    """Prediction joined with a delayed binary label."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    prediction_timestamp: datetime
    label_timestamp: datetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    probability: float = Field(ge=0.0, le=1.0)
    label: int = Field(ge=0, le=1)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    slice_keys: dict[str, str] = Field(default_factory=dict)


class LabeledRegressionPrediction(BaseModel):
    """Regression prediction joined with a delayed target."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    prediction_timestamp: datetime
    label_timestamp: datetime
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    prediction: float
    label: float
    slice_keys: dict[str, str] = Field(default_factory=dict)


def monitor_realized_binary_performance(
    *,
    records: list[LabeledBinaryPrediction],
    budget: MetricBudgetPolicy,
    metric: Literal["accuracy", "precision", "recall", "brier", "roc_auc"] = "accuracy",
    corroborating_shift_event_ids: list[str] | None = None,
    calibration_id: str | None = None,
    timestamp: datetime | None = None,
) -> PerformanceDegradationEvent:
    """Measure classifier performance once labels arrive."""

    _require_records(records)
    if budget.metric != metric:
        raise ValueError("metric must match the supplied metric budget")

    current, interval = _binary_metric(records, metric)
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
        event_id=f"realized-{budget.model_id}-{budget.model_version}-{metric}-{event_time.isoformat()}",
        timestamp=event_time,
        model_id=budget.model_id,
        model_version=budget.model_version,
        metric=metric,
        metric_direction=budget.metric_direction,
        source="realized_performance",
        estimator="delayed_label_metric",
        reference_value=budget.reference_value,
        minimum_acceptable_value=budget.minimum_acceptable_value,
        maximum_acceptable_value=budget.maximum_acceptable_value,
        current_estimate=current,
        confidence_interval_95=interval,
        budget_used=budget_used,
        label_delay_days_p50=_quantile(_label_delays(records), 0.50),
        label_delay_days_p90=_quantile(_label_delays(records), 0.90),
        corroborating_shift_event_ids=list(corroborating_shift_event_ids or []),
        calibration_id=calibration_id,
    )


def monitor_realized_regression_performance(
    *,
    records: list[LabeledRegressionPrediction],
    budget: MetricBudgetPolicy,
    metric: Literal["mae", "rmse"] = "mae",
    corroborating_shift_event_ids: list[str] | None = None,
    calibration_id: str | None = None,
    timestamp: datetime | None = None,
) -> PerformanceDegradationEvent:
    """Measure regression loss once labels arrive."""

    _require_records(records)
    if budget.metric != metric:
        raise ValueError("metric must match the supplied metric budget")
    if budget.metric_direction is not MetricDirection.LOWER_IS_BETTER:
        raise ValueError("regression loss budgets must be lower-is-better")

    losses = _regression_losses(records, metric)
    current, interval = _mean_interval(losses)
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
        event_id=f"realized-{budget.model_id}-{budget.model_version}-{metric}-{event_time.isoformat()}",
        timestamp=event_time,
        model_id=budget.model_id,
        model_version=budget.model_version,
        metric=metric,
        metric_direction=budget.metric_direction,
        source="realized_performance",
        estimator="delayed_label_metric",
        reference_value=budget.reference_value,
        minimum_acceptable_value=budget.minimum_acceptable_value,
        maximum_acceptable_value=budget.maximum_acceptable_value,
        current_estimate=current,
        confidence_interval_95=interval,
        budget_used=budget_used,
        label_delay_days_p50=_quantile(_label_delays(records), 0.50),
        label_delay_days_p90=_quantile(_label_delays(records), 0.90),
        corroborating_shift_event_ids=list(corroborating_shift_event_ids or []),
        calibration_id=calibration_id,
    )


def _binary_metric(
    records: list[LabeledBinaryPrediction],
    metric: Literal["accuracy", "precision", "recall", "brier", "roc_auc"],
) -> tuple[float, tuple[float, float]]:
    labels = [record.label for record in records]
    probabilities = [record.probability for record in records]
    predictions = [1 if record.probability >= record.threshold else 0 for record in records]
    if metric == "accuracy":
        values = [
            1.0 if predicted == label else 0.0
            for predicted, label in zip(predictions, labels, strict=True)
        ]
        return _mean_interval(values, bounded=True)
    if metric == "brier":
        values = [
            (probability - label) ** 2
            for probability, label in zip(probabilities, labels, strict=True)
        ]
        return _mean_interval(values, bounded=True)
    if metric == "roc_auc":
        auc = _roc_auc(labels, probabilities)
        return auc, _bounded_interval(auc, len(records))

    true_positives = sum(
        1 for predicted, label in zip(predictions, labels, strict=True) if predicted == label == 1
    )
    if metric == "precision":
        predicted_positive = sum(predictions)
        if predicted_positive == 0:
            raise ValueError("precision is undefined with no positive predictions")
        value = true_positives / predicted_positive
        return value, _bounded_interval(value, predicted_positive)

    actual_positive = sum(labels)
    if actual_positive == 0:
        raise ValueError("recall is undefined with no positive labels")
    value = true_positives / actual_positive
    return value, _bounded_interval(value, actual_positive)


def _regression_losses(
    records: list[LabeledRegressionPrediction],
    metric: Literal["mae", "rmse"],
) -> list[float]:
    absolute_errors = [abs(record.prediction - record.label) for record in records]
    if metric == "mae":
        return absolute_errors
    mse = sum(error**2 for error in absolute_errors) / len(absolute_errors)
    return [math.sqrt(mse)]


def _roc_auc(labels: list[int], scores: list[float]) -> float:
    positive_count = sum(labels)
    negative_count = len(labels) - positive_count
    if positive_count == 0 or negative_count == 0:
        raise ValueError("roc_auc requires both positive and negative labels")

    sorted_pairs = sorted(zip(scores, labels, strict=True), key=lambda item: item[0])
    ranks = [0.0] * len(sorted_pairs)
    index = 0
    while index < len(sorted_pairs):
        next_index = index + 1
        while (
            next_index < len(sorted_pairs) and sorted_pairs[next_index][0] == sorted_pairs[index][0]
        ):
            next_index += 1
        average_rank = (index + 1 + next_index) / 2.0
        for rank_index in range(index, next_index):
            ranks[rank_index] = average_rank
        index = next_index
    positive_rank_sum = sum(
        rank for rank, pair in zip(ranks, sorted_pairs, strict=True) if pair[1] == 1
    )
    return (positive_rank_sum - positive_count * (positive_count + 1) / 2.0) / (
        positive_count * negative_count
    )


def _mean_interval(
    values: list[float],
    *,
    bounded: bool = False,
) -> tuple[float, tuple[float, float]]:
    if not values:
        raise ValueError("at least one value is required")
    n = len(values)
    mean = sum(values) / n
    if n == 1:
        return mean, (mean, mean)
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    half_width = 1.96 * math.sqrt(variance / n)
    low = mean - half_width
    high = mean + half_width
    if bounded:
        low = max(0.0, low)
        high = min(1.0, high)
    return mean, (low, high)


def _bounded_interval(value: float, n: int) -> tuple[float, float]:
    if n <= 1:
        return value, value
    half_width = 1.96 * math.sqrt(max(value * (1.0 - value), 0.0) / n)
    return max(0.0, value - half_width), min(1.0, value + half_width)


def _label_delays(
    records: list[LabeledBinaryPrediction] | list[LabeledRegressionPrediction],
) -> list[float]:
    return [
        (record.label_timestamp - record.prediction_timestamp).total_seconds() / 86400.0
        for record in records
    ]


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
        raise ValueError("at least one labeled record is required")
