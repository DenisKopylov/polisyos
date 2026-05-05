"""Tests for continuous calibration diagnostics."""

from __future__ import annotations

import numpy as np
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
