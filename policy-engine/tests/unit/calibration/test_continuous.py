"""Tests for continuous calibration diagnostics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from polisyos.calibration import compute_calibration_curve, evaluate_continuous
from polisyos.ir.analytics.calibration_diagnostics import CalibrationDiagnosticsReport


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
    intervals = [(value - 0.1, value + 0.1) for value in y_true[:95]] + [(-1000.0, -999.0)] * 5

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


@pytest.mark.parametrize("empty_first", [True, False])
def test_incomplete_intervals_remain_unverified_after_report_readback(
    empty_first: bool,
    tmp_path: Path,
) -> None:
    y_true = np.arange(100, dtype=float).tolist()
    valid = [(value - 0.1, value + 0.1) for value in y_true[:95]] + [(-1000.0, -999.0)] * 5
    intervals = [[], valid] if empty_first else [valid, []]
    levels = [0.5, 0.95] if empty_first else [0.95, 0.5]
    report = evaluate_continuous(
        y_true=y_true,
        intervals=intervals,
        levels=levels,
        uncertainty={"bootstrap": 20, "seed": 0},
    )
    path = tmp_path / "report.json"
    path.write_text(report.model_dump_json(), encoding="utf-8")
    reopened = CalibrationDiagnosticsReport.model_validate_json(path.read_text(encoding="utf-8"))
    receipt = reopened.to_truthfulness_receipt()

    assert reopened.metrics.ece == pytest.approx(0.0)
    assert reopened.metrics.intervals == {}
    assert reopened.metadata["interval_coverage"]["status"] == "incomplete"
    assert reopened.metadata["interval_coverage"]["n_comparisons"] == 1
    assert reopened.metadata["interval_coverage"]["requested"] == 200
    assert reopened.metadata["interval_coverage"]["eligible"] == 100
    assert len(reopened.curves["interval_coverage"]) == 1
    assert reopened.curves["interval_coverage"][0].count == 100
    assert receipt.runtime_truthfulness_tier == "unverified"
    assert "interval_coverage_incomplete" in receipt.degradation_reasons


@pytest.mark.parametrize("covered", [95, 0])
def test_measured_coverage_controls_survive_report_readback(covered: int, tmp_path: Path) -> None:
    y_true = np.arange(100, dtype=float).tolist()
    intervals = [(v - 0.1, v + 0.1) for v in y_true[:covered]] + [(-1000.0, -999.0)] * (
        100 - covered
    )
    report = evaluate_continuous(
        y_true=y_true,
        intervals={0.95: intervals},
        uncertainty={"bootstrap": 100, "seed": 2718},
    )
    path = tmp_path / "report.json"
    path.write_text(report.model_dump_json(), encoding="utf-8")
    reopened = CalibrationDiagnosticsReport.model_validate_json(path.read_text(encoding="utf-8"))
    receipt = reopened.to_truthfulness_receipt()

    assert reopened.metadata["interval_coverage"]["status"] == "evaluated"
    assert reopened.metadata["interval_coverage"]["n_comparisons"] == 1
    assert reopened.metrics.ece == pytest.approx(abs(covered / 100 - 0.95))
    assert reopened.curves["interval_coverage"][0].mean_observed == pytest.approx(covered / 100)
    assert reopened.metrics.intervals["ece"].low <= reopened.metrics.ece
    assert reopened.metrics.intervals["ece"].high >= reopened.metrics.ece
    assert receipt.runtime_truthfulness_tier == "unverified"
    assert "interval_pairs_not_reconciled" in receipt.degradation_reasons
    assert receipt.truthfulness_scope == "predictive_calibration"


@pytest.mark.parametrize("level", [float("nan"), float("inf"), -0.1, 1.1])
def test_continuous_rejects_invalid_levels_even_for_skipped_sets(level: float) -> None:
    with pytest.raises(ValueError, match="levels"):
        evaluate_continuous(y_true=[1.0], intervals=[[]], levels=[level])


def test_continuous_reversed_bounds_reject_before_calculation_even_nonstrict() -> None:
    with pytest.raises(ValueError, match="lower bound"):
        evaluate_continuous(y_true=[1.0] * 100, intervals={0.95: [(2.0, 0.0)] * 100}, strict=False)


@pytest.mark.parametrize("level", [float("nan"), float("inf"), -0.1, 0.0, 1.0, 1.1])
@pytest.mark.parametrize("from_samples", [True, False])
def test_continuous_level_domain_is_independent_of_interval_source(
    level: float,
    from_samples: bool,
) -> None:
    inputs = (
        {"predictive_samples": [[0.0, 2.0]] * 100}
        if from_samples
        else {"intervals": [[(0.0, 2.0)] * 100]}
    )
    with pytest.raises(ValueError, match="levels"):
        evaluate_continuous(y_true=[1.0] * 100, levels=[level], **inputs)


def test_predictive_samples_do_not_replace_explicit_empty_levels() -> None:
    report = evaluate_continuous(
        y_true=[1.0] * 100,
        predictive_samples=[[0.0, 2.0]] * 100,
        levels=[],
    )

    assert report.metadata["nominal_levels"] == []
    assert report.metadata["interval_coverage"]["status"] == "not_evaluated"
    assert report.metadata["interval_coverage"]["n_comparisons"] == 0
    assert report.metrics.ece is None
    assert report.curves["interval_coverage"] == ()
    assert report.to_truthfulness_receipt().runtime_truthfulness_tier == "unverified"


def test_predictive_samples_retain_default_levels_when_omitted() -> None:
    report = evaluate_continuous(y_true=[1.0] * 100, predictive_samples=[[0.0, 2.0]] * 100)

    assert report.metadata["nominal_levels"] == [0.5, 0.8, 0.9]
    assert report.metadata["interval_coverage"]["status"] == "evaluated"
    assert report.metadata["interval_coverage"]["n_comparisons"] == 3
