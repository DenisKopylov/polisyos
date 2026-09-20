"""Tests for continuous calibration diagnostics."""

from __future__ import annotations

import numpy as np
import pytest
from polisyos.calibration import compute_calibration_curve, evaluate_continuous


def test_evaluate_continuous_matches_existing_backtesting_curve_behavior() -> None:
    y_true = [1.0, 2.0, 3.0, 4.0]
    interval_sets = [
        [(0.5, 1.5), (1.5, 2.5), (2.5, 3.5), (3.5, 4.5)],
        [(-1.0, 10.0)] * 4,
    ]
    levels = [0.5, 0.9]

    expected = compute_calibration_curve(y_true, interval_sets, levels=levels)
    report = evaluate_continuous(
        y_true=y_true,
        intervals=interval_sets,
        levels=levels,
        uncertainty={"bootstrap": 20, "seed": 0},
    )

    assert report.task == "continuous"
    assert report.metrics.ece == expected.ece
    assert report.metrics.mce == expected.max_ce
    assert (
        report.curves["interval_coverage"][0].mean_observed == expected.points[0].empirical_coverage
    )
    assert "ece" in report.metrics.intervals


def test_evaluate_continuous_with_predictive_samples_emits_pit_and_ence() -> None:
    rng = np.random.default_rng(0)
    y_true = np.linspace(-1.0, 1.0, 40)
    predictive_samples = rng.normal(loc=y_true[:, None], scale=0.5, size=(40, 200))

    report = evaluate_continuous(
        y_true=y_true.tolist(),
        predictive_samples=predictive_samples.tolist(),
    )

    assert report.metrics.ence is not None
    assert report.metadata["pit_histogram"]["counts"]
    assert report.primary_curve == "interval_coverage"


@pytest.mark.parametrize(
    ("intervals", "levels"),
    [({}, []), ([], [])],
)
def test_empty_interval_inputs_are_not_positive_calibration_evidence(
    intervals: object,
    levels: list[float],
) -> None:
    y_true = np.arange(100, dtype=float).tolist()

    report = evaluate_continuous(
        y_true=y_true,
        intervals=intervals,  # type: ignore[arg-type]
        levels=levels,
    )
    receipt = report.to_truthfulness_receipt()

    assert report.metrics.n_obs == 100
    assert report.metrics.ece is None
    assert report.metrics.mce is None
    assert report.metrics.rmsce is None
    assert report.curves["interval_coverage"] == ()
    assert report.metadata["interval_coverage"]["n_comparisons"] == 0
    assert report.metadata["interval_coverage"]["status"] == "not_evaluated"
    issue = next(issue for issue in report.issues if issue.code == "CALIB_INTERVAL_NOT_EVALUATED")
    assert issue.actual == 0
    assert issue.severity.value == "error"
    assert receipt.runtime_truthfulness_tier == "unverified"
    assert "interval_coverage_not_evaluated" in receipt.degradation_reasons


def test_evaluate_continuous_accepts_ninety_five_percent_interval_coverage() -> None:
    y_true = np.arange(100, dtype=float).tolist()
    intervals = [
        (value - 0.1, value + 0.1) for value in y_true[:95]
    ] + [(-1000.0, -999.0)] * 5

    report = evaluate_continuous(
        y_true=y_true,
        intervals={0.95: intervals},
        levels=[0.95],
    )
    receipt = report.to_truthfulness_receipt()

    assert report.metrics.ece == pytest.approx(0.0)
    assert report.curves["interval_coverage"][0].mean_observed == pytest.approx(0.95)
    assert receipt.runtime_truthfulness_tier == "approximate_calibrated"


def test_evaluate_continuous_downgrades_zero_coverage() -> None:
    y_true = [1.0, 2.0, 3.0]
    intervals = [(-100.0, -99.0)] * len(y_true)

    report = evaluate_continuous(
        y_true=y_true,
        intervals={0.95: intervals},
        levels=[0.95],
    )
    receipt = report.to_truthfulness_receipt()

    assert report.metrics.ece == pytest.approx(0.95)
    assert report.curves["interval_coverage"][0].mean_observed == 0.0
    assert receipt.runtime_truthfulness_tier == "unverified"
    assert "ece_above_fail_threshold" in receipt.degradation_reasons


def test_evaluate_continuous_preserves_small_sample_downgrade() -> None:
    y_true = np.arange(10, dtype=float).tolist()
    intervals = [(value - 0.1, value + 0.1) for value in y_true]

    report = evaluate_continuous(
        y_true=y_true,
        intervals={0.95: intervals},
        levels=[0.95],
    )
    receipt = report.to_truthfulness_receipt()

    assert any(issue.code == "CALIB_INTERVAL_LOW_N" for issue in report.issues)
    assert receipt.runtime_truthfulness_tier == "unverified"
    assert "insufficient_holdout_sample" in receipt.degradation_reasons


def test_evaluate_continuous_rejects_mapping_level_mismatch() -> None:
    intervals = [(0.0, 2.0)] * 100

    with pytest.raises(ValueError, match="levels must match interval mapping keys"):
        evaluate_continuous(
            y_true=np.arange(100, dtype=float).tolist(),
            intervals={0.95: intervals},
            levels=[0.5],
        )
