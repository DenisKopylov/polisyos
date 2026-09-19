"""Stationary replay tests for DDM calibration."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

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


@pytest.mark.parametrize(
    ("now", "observed_triggers", "expected_valid", "expected_reasons"),
    [
        (datetime(2026, 4, 10, tzinfo=UTC), [], True, []),
        (
            datetime(2026, 5, 2, tzinfo=UTC),
            [],
            False,
            ["calibration_expired"],
        ),
        (
            datetime(2026, 4, 10, tzinfo=UTC),
            ["model_version_change"],
            False,
            ["model_version_change"],
        ),
        (datetime(2026, 4, 10, tzinfo=UTC), ["unrelated_trigger"], True, []),
    ],
)
def test_calibration_validity_binds_effective_time_and_observed_triggers(
    now: datetime,
    observed_triggers: list[str],
    expected_valid: bool,
    expected_reasons: list[str],
) -> None:
    """The existing validity owner must remain the sole expiry/trigger authority."""

    calibration_streams = [[0.10, 0.12, 0.11, 0.13] for _ in range(100)]
    holdout_streams = [[0.05, 0.07, 0.08, 0.09] for _ in range(100)]
    report = calibrate_detector(
        detector_id="input_mmd_global_v3",
        stationarity_regime=_regime(),
        fp_target=FpTarget(horizon="30d", alpha=0.05, ert=10000),
        calibration_streams=calibration_streams,
        holdout_streams=holdout_streams,
    )

    status = check_calibration_validity(
        calibration_id="calib-1",
        report=report,
        now=now,
        observed_invalidation_triggers=observed_triggers,
    )

    assert status.valid is expected_valid
    assert status.reasons == expected_reasons


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
