"""Tests for multiclass calibration diagnostics."""

from __future__ import annotations

import pytest
from polisyos.calibration import evaluate_multiclass


def test_evaluate_multiclass_returns_top_label_and_classwise_metrics() -> None:
    y_true = [0, 1, 2] * 30
    y_prob = [[0.72, 0.18, 0.10], [0.12, 0.70, 0.18], [0.10, 0.22, 0.68]] * 30
    groups = {"region": ["north", "south", "east"] * 30}

    report = evaluate_multiclass(
        y_true=y_true,
        y_prob=y_prob,
        curves={"binning": ["quantile"], "n_bins": [5]},
        tests=["spiegelhalter"],
        groups=groups,
    )

    assert report.task == "multiclass"
    assert report.primary_curve == "top_label_quantile_5"
    assert report.metrics.brier is not None
    assert report.metrics.log_loss is not None
    assert report.metrics.ece is not None
    assert report.metrics.ence is not None
    assert set(report.per_class) == {"0", "1", "2"}
    assert report.per_group
    assert report.metadata["top_label_accuracy"] == pytest.approx(1.0)


def test_evaluate_multiclass_can_repair_probability_rows() -> None:
    report = evaluate_multiclass(
        y_true=[0, 1, 2],
        y_prob=[
            [2.0, 1.0, 1.0],
            [0.4, 0.4, 0.4],
            [0.1, -0.2, 0.8],
        ],
        strict=False,
        repair_strategy="normalize_rows",
    )

    assert any(issue.code == "CALIB_INVALID_PROBABILITY_ROWS_REPAIRED" for issue in report.issues)
    assert report.metadata["repair_log"]["repair_strategy"] == "normalize_rows"
