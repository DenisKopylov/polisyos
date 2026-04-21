"""Tests for binary calibration diagnostics."""
from __future__ import annotations

import pytest

from polisyos.calibration import evaluate_binary


def test_evaluate_binary_returns_metrics_curves_and_tests() -> None:
    y_true = [0.0, 0.0, 1.0, 1.0] * 50
    y_prob = [0.25, 0.35, 0.65, 0.75] * 50

    report = evaluate_binary(
        y_true=y_true,
        y_prob=y_prob,
        curves={"binning": ["uniform", "quantile"], "n_bins": [5]},
        tests=["spiegelhalter", "hosmer_lemeshow"],
        uncertainty={"bootstrap": 25, "seed": 0},
    )

    assert report.task == "binary"
    assert report.primary_curve == "quantile_5"
    assert report.metrics.brier is not None
    assert report.metrics.log_loss is not None
    assert report.metrics.ece is not None
    assert report.metrics.ence is not None
    assert report.metrics.intervals["brier"].low <= report.metrics.brier <= report.metrics.intervals["brier"].high
    assert len(report.curves["uniform_5"]) == 5
    assert any(item.ci_low is not None for item in report.curves["uniform_5"] if item.count > 0)
    assert {test.test_id for test in report.tests} == {"spiegelhalter", "hosmer_lemeshow"}


def test_evaluate_binary_rejects_invalid_probabilities_when_strict() -> None:
    with pytest.raises(ValueError, match="inside \\[0, 1\\]"):
        evaluate_binary(
            y_true=[0.0, 1.0],
            y_prob=[-0.2, 1.2],
            strict=True,
        )


def test_evaluate_binary_can_repair_invalid_probabilities_when_non_strict() -> None:
    report = evaluate_binary(
        y_true=[0.0, 1.0, 0.0, 1.0],
        y_prob=[-0.2, 1.2, 0.1, 0.9],
        strict=False,
        repair_strategy="clip",
    )

    assert any(issue.code == "CALIB_REPAIRED_PROBABILITIES" for issue in report.issues)
    assert report.metadata["repair_log"]["probability_repairs"] == 2


def test_hosmer_lemeshow_marks_sparse_expected_counts() -> None:
    report = evaluate_binary(
        y_true=[0.0] * 10 + [1.0] * 10,
        y_prob=[0.01] * 10 + [0.99] * 10,
        tests=["hosmer_lemeshow"],
    )

    hl = next(test for test in report.tests if test.test_id == "hosmer_lemeshow")
    assert hl.assumptions_ok is False
    assert hl.p_value is None
