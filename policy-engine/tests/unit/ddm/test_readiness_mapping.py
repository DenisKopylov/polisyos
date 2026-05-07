"""Readiness mapping acceptance tests for DDM."""

from __future__ import annotations

from datetime import UTC, datetime

from polisyos.ddm.detectors import FeatureContract, adapt_shift_event, evaluate_data_quality
from polisyos.ddm.integration import (
    AffectedSlice,
    MetricDirection,
    MonitoringWindow,
    PerformanceDegradationEvent,
    ReadinessState,
    ShiftDetectedEvent,
)
from polisyos.ddm.readiness import map_readiness


def _window() -> MonitoringWindow:
    return MonitoringWindow(
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 2, tzinfo=UTC),
        n=100,
    )


def _shift(severity: float) -> ShiftDetectedEvent:
    return ShiftDetectedEvent(
        event_id="shift-1",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id="model",
        model_version="v1",
        detector_id="input_mmd_global_v3",
        detector_family="online_mmd",
        signal="input_shift",
        representation="feature_embedding_v2",
        reference_window=_window(),
        current_window=_window(),
        stationarity_regime_id="SR-1-model-v1",
        calibration_id="calib-1",
        test_statistic=0.2,
        ert=10000,
        empirical_fp_rate=0.001,
        shift_severity=severity,
        affected_slices=[AffectedSlice(slice="region=west", score=0.44)],
    )


def test_drift_only_alert_maps_to_watch_not_r0() -> None:
    readiness = map_readiness(
        model_id="model",
        model_version="v1",
        shift_events=[adapt_shift_event(_shift(0.72))],
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert readiness.readiness_state == ReadinessState.R3
    assert readiness.promotion_allowed is True
    assert readiness.affected_slices == ["region=west"]


def test_high_metric_budget_maps_to_not_ready_for_expansion() -> None:
    degradation = PerformanceDegradationEvent(
        event_id="degrade-1",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
        model_id="model",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        source="estimated_performance",
        estimator="cbpe",
        reference_value=0.90,
        minimum_acceptable_value=0.80,
        current_estimate=0.84,
        confidence_interval_95=(0.82, 0.86),
        budget_used=0.80,
    )

    readiness = map_readiness(
        model_id="model",
        model_version="v1",
        degradation_event=degradation,
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert readiness.readiness_state == ReadinessState.R1
    assert readiness.promotion_allowed is False
    assert "freeze_rollout" in readiness.required_actions


def test_hard_data_quality_failure_maps_to_r0() -> None:
    quality = evaluate_data_quality(
        records=[{"age": None}, {"age": 120.0}],
        contracts=[FeatureContract(feature="age", dtype="number", min_value=0, max_value=100)],
        model_id="model",
        model_version="v1",
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    readiness = map_readiness(
        model_id="model",
        model_version="v1",
        data_quality_signals=[quality],
        timestamp=datetime(2026, 4, 26, tzinfo=UTC),
    )

    assert quality.hard_failure is True
    assert readiness.readiness_state == ReadinessState.R0
    assert readiness.promotion_allowed is False
