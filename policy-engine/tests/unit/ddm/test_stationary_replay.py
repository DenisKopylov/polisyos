"""Stationary replay tests for DDM calibration."""

from __future__ import annotations

from datetime import UTC, datetime

from polisyos.ddm.calibration import (
    FpTarget,
    OnlineFDRController,
    Period,
    StationarityRegime,
    allocate_conservative_budget,
    bootstrap_stationary_streams,
    build_calibration_audit,
    calibrate_detector,
    check_calibration_validity,
    moving_block_bootstrap,
    stratified_bootstrap_stationary_streams,
)
from polisyos.ddm.integration import (
    DriftAndDegradationMonitor,
    MetricDirection,
    evaluate_registry_gate,
)
from polisyos.ddm.readiness import MetricBudgetPolicy


def _regime() -> StationarityRegime:
    return StationarityRegime(
        id="SR-1-model-v1",
        model_id="model",
        model_version="v1",
        reference_period=Period(
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 2, 1, tzinfo=UTC),
        ),
        calibration_period=Period(
            start=datetime(2026, 2, 1, tzinfo=UTC),
            end=datetime(2026, 3, 1, tzinfo=UTC),
        ),
        holdout_stationary_period=Period(
            start=datetime(2026, 3, 1, tzinfo=UTC),
            end=datetime(2026, 4, 1, tzinfo=UTC),
        ),
        seasonality_strata=["day_of_week"],
        block_length=2,
        invalidation_triggers=["model_version_change"],
    )


def test_stationary_holdout_certificate_passes_when_no_false_alerts() -> None:
    calibration_streams = [[0.10, 0.12, 0.11, 0.13] for _ in range(100)]
    holdout_streams = [[0.05, 0.07, 0.08, 0.09] for _ in range(100)]

    report = calibrate_detector(
        detector_id="input_mmd_global_v3",
        stationarity_regime=_regime(),
        fp_target=FpTarget(horizon="30d", alpha=0.05, ert=10000),
        calibration_streams=calibration_streams,
        holdout_streams=holdout_streams,
    )

    assert report.threshold == 0.13
    assert report.empirical_stationary_holdout.alerts == 0
    assert report.empirical_stationary_holdout.pass_ is True
    assert report.empirical_stationary_holdout.confidence_interval_95[1] <= 0.05
    assert report.stationarity_regime_id == "SR-1-model-v1"
    assert len(report.time_varying_thresholds) == 4

    audit = build_calibration_audit(calibration_id="calib-1", report=report)
    status = check_calibration_validity(
        calibration_id="calib-1",
        report=report,
        now=datetime(2026, 4, 10, tzinfo=UTC),
    )

    assert audit.pass_ is True
    assert audit.empirical_fp_upper_95 <= 0.05
    assert status.valid is True


def test_registry_requires_checker_bound_report_and_rejects_foreign_report() -> None:
    """A checker result authorizes only the exact report it evaluated."""

    calibration_streams = [[0.10, 0.12, 0.11, 0.13] for _ in range(100)]
    holdout_streams = [[0.05, 0.07, 0.08, 0.09] for _ in range(100)]
    report_a = calibrate_detector(
        detector_id="input_mmd_global_v3",
        stationarity_regime=_regime(),
        fp_target=FpTarget(horizon="30d", alpha=0.05, ert=10000),
        calibration_streams=calibration_streams,
        holdout_streams=holdout_streams,
    )
    audit_a = build_calibration_audit(calibration_id="calib-1", report=report_a)
    metric_budget = MetricBudgetPolicy(
        model_id="model",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.90,
        minimum_acceptable_value=0.80,
    )
    monitor = DriftAndDegradationMonitor()

    accepted = monitor.evaluate_window(
        model_id="model",
        model_version="v1",
        metric_budget=metric_budget,
        calibration_audit=audit_a,
        _calibration_report=report_a,
        _observed_invalidation_triggers=[],
        timestamp=datetime(2026, 4, 10, tzinfo=UTC),
    )
    assert accepted.registry_record is not None
    assert evaluate_registry_gate(accepted.registry_record).promotion_allowed is True

    report_b = report_a.model_copy(update={"detector_id": "foreign-detector"})
    altered = monitor.evaluate_window(
        model_id="model",
        model_version="v1",
        metric_budget=metric_budget,
        calibration_audit=audit_a,
        _calibration_report=report_b,
        _observed_invalidation_triggers=[],
        timestamp=datetime(2026, 4, 10, tzinfo=UTC),
    )
    assert altered.registry_record is not None
    gate = evaluate_registry_gate(altered.registry_record)
    assert gate.promotion_allowed is False
    assert gate.reason == "calibration_report_binding_not_established"


def test_registry_rejects_calibration_report_for_foreign_target_model() -> None:
    """A valid calibration for model A must not authorize target model B."""

    calibration_streams = [[0.10, 0.12, 0.11, 0.13] for _ in range(100)]
    holdout_streams = [[0.05, 0.07, 0.08, 0.09] for _ in range(100)]
    source_regime = _regime().model_copy(
        update={
            "id": "SR-model-A-v1",
            "model_id": "model-A",
            "model_version": "v1",
        }
    )
    report_a = calibrate_detector(
        detector_id="input_mmd_global_v3",
        stationarity_regime=source_regime,
        fp_target=FpTarget(horizon="30d", alpha=0.05, ert=10000),
        calibration_streams=calibration_streams,
        holdout_streams=holdout_streams,
    )
    audit_a = build_calibration_audit(calibration_id="calib-A", report=report_a)
    target_budget = MetricBudgetPolicy(
        model_id="model-B",
        model_version="v2",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.90,
        minimum_acceptable_value=0.80,
    )

    result = DriftAndDegradationMonitor().evaluate_window(
        model_id="model-B",
        model_version="v2",
        metric_budget=target_budget,
        calibration_audit=audit_a,
        _calibration_report=report_a,
        _observed_invalidation_triggers=[],
        timestamp=datetime(2026, 4, 10, tzinfo=UTC),
    )

    assert result.registry_record is not None
    gate = evaluate_registry_gate(result.registry_record)
    assert gate.promotion_allowed is False, gate.reason


def test_moving_block_bootstrap_is_reproducible_and_preserves_length() -> None:
    values = [1.0, 2.0, 3.0, 4.0]

    sample_a = moving_block_bootstrap(values, block_length=2, sample_size=6, seed=7)
    sample_b = moving_block_bootstrap(values, block_length=2, sample_size=6, seed=7)
    streams = bootstrap_stationary_streams(
        values,
        block_length=2,
        stream_length=6,
        n_streams=3,
        seed=7,
    )

    assert sample_a == sample_b
    assert len(sample_a) == 6
    assert len(streams) == 3
    assert all(len(stream) == 6 for stream in streams)


def test_stratified_bootstrap_and_multiple_testing_controls_are_available() -> None:
    streams = stratified_bootstrap_stationary_streams(
        {"weekday": [0.1, 0.2, 0.3], "weekend": [0.4, 0.5]},
        block_length=1,
        stream_length=6,
        n_streams=2,
        seed=11,
    )
    plan = allocate_conservative_budget(
        system_alpha=0.05,
        test_ids=["feature.age", "slice.region", "feature.age"],
    )
    controller = OnlineFDRController.create(alpha=0.05)
    decision = controller.test(test_id="feature.age", p_value=0.001)

    assert len(streams) == 2
    assert set(plan.allocations) == {"feature.age", "slice.region"}
    assert sum(plan.allocations.values()) <= 0.05
    assert decision.rejected is True
