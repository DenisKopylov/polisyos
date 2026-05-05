"""Delayed-label degradation replay tests for DDM-15.7."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from polisyos.ddm.detectors import (
    BinaryPredictionRecord,
    LabeledBinaryPrediction,
    estimate_binary_classification_degradation,
    monitor_realized_binary_performance,
)
from polisyos.ddm.integration import MetricDirection
from polisyos.ddm.readiness import MetricBudgetPolicy


def _accuracy_budget() -> MetricBudgetPolicy:
    return MetricBudgetPolicy(
        model_id="model",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.90,
        minimum_acceptable_value=0.80,
    )


def test_estimated_performance_event_uses_calibrated_probabilities_before_labels() -> None:
    predictions = [
        BinaryPredictionRecord(
            request_id=f"r-{index}",
            timestamp=datetime(2026, 4, 1, tzinfo=UTC),
            model_id="model",
            model_version="v1",
            probability=0.88,
        )
        for index in range(40)
    ]

    event = estimate_binary_classification_degradation(
        predictions=predictions,
        budget=_accuracy_budget(),
        label_delay_days=[1.0, 2.0, 3.0, 4.0, 5.0],
        calibration_id="calib-1",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert event.source == "estimated_performance"
    assert event.estimator == "cbpe"
    assert event.current_estimate == pytest.approx(0.88)
    assert event.budget_used == pytest.approx(0.2)
    assert event.label_delay_days_p50 == 3.0
    assert event.label_delay_days_p90 == 4.6


def test_realized_performance_event_reports_label_delay_and_budget() -> None:
    prediction_time = datetime(2026, 4, 1, tzinfo=UTC)
    records = [
        LabeledBinaryPrediction(
            request_id=f"ok-{index}",
            prediction_timestamp=prediction_time,
            label_timestamp=prediction_time + timedelta(days=2),
            model_id="model",
            model_version="v1",
            probability=0.9,
            label=1,
        )
        for index in range(36)
    ] + [
        LabeledBinaryPrediction(
            request_id=f"bad-{index}",
            prediction_timestamp=prediction_time,
            label_timestamp=prediction_time + timedelta(days=4),
            model_id="model",
            model_version="v1",
            probability=0.9,
            label=0,
        )
        for index in range(4)
    ]

    event = monitor_realized_binary_performance(
        records=records,
        budget=_accuracy_budget(),
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert event.source == "realized_performance"
    assert event.current_estimate == 0.9
    assert event.label_delay_days_p50 == 2.0
    assert event.label_delay_days_p90 == pytest.approx(2.2)
    assert event.budget_used >= 0.0
