"""Tests for canonical interval calibration curves."""

from __future__ import annotations

import pytest

from polisyos.calibration import compute_calibration_curve


class TestCalibrationCurve:
    def test_perfect_calibration(self):
        y_true = [1.0, 2.0, 3.0, 4.0, 5.0]
        # 50% interval that covers all values
        intervals_50 = [(0.0, 10.0)] * 5
        # 90% interval that also covers all
        intervals_90 = [(0.0, 10.0)] * 5
        result = compute_calibration_curve(
            y_true,
            [intervals_50, intervals_90],
            levels=[0.5, 0.9],
        )
        assert len(result.points) == 2
        assert result.points[0].empirical_coverage == 1.0
        assert result.points[1].empirical_coverage == 1.0

    def test_well_calibrated_flag(self):
        y_true = [1.0, 2.0, 3.0, 4.0]
        intervals = [(0.5, 4.5)] * 4  # covers all
        result = compute_calibration_curve(
            y_true,
            [intervals],
            levels=[1.0],
            tolerance=0.05,
        )
        assert result.is_well_calibrated is True

    def test_empty_intervals(self):
        result = compute_calibration_curve([1.0, 2.0], [], levels=[])
        assert result.points == []
        assert result.ece is None
        assert result.max_ce is None
        assert result.is_well_calibrated is False
        assert result.evaluation_status == "not_evaluated"
        assert result.n_comparisons == 0

    def test_ninety_five_of_one_hundred_observations_are_covered(self):
        y_true = [float(index) for index in range(100)]
        intervals = [(value - 0.1, value + 0.1) for value in y_true[:95]] + [(-1000.0, -999.0)] * 5

        result = compute_calibration_curve(y_true, [intervals], levels=[0.95])

        assert result.evaluation_status == "evaluated"
        assert result.n_comparisons == 1
        assert result.points[0].empirical_coverage == pytest.approx(0.95)
        assert result.ece == pytest.approx(0.0)
        assert result.is_well_calibrated is True

    def test_zero_coverage_is_measured_as_miscalibration(self):
        y_true = [1.0, 2.0, 3.0]
        intervals = [(-100.0, -99.0)] * len(y_true)

        result = compute_calibration_curve(y_true, [intervals], levels=[0.95])

        assert result.evaluation_status == "evaluated"
        assert result.n_comparisons == 1
        assert result.points[0].empirical_coverage == 0.0
        assert result.ece == pytest.approx(0.95)
        assert result.is_well_calibrated is False

    def test_mismatched_levels_and_intervals_are_not_silently_truncated(self):
        with pytest.raises(ValueError, match="levels and interval sets"):
            compute_calibration_curve(
                [1.0, 2.0],
                [[(0.0, 3.0), (0.0, 3.0)]],
                levels=[0.5, 0.95],
            )

    def test_misaligned_interval_observations_are_not_silently_skipped(self):
        with pytest.raises(ValueError, match="interval set must align"):
            compute_calibration_curve(
                [1.0, 2.0],
                [[(0.0, 3.0)]],
                levels=[0.5],
            )


@pytest.mark.parametrize("empty_first", [True, False])
def test_incomplete_curve_cannot_pass_even_with_zero_measured_error(empty_first: bool) -> None:
    y_true = [float(index) for index in range(100)]
    valid = [(value - 0.1, value + 0.1) for value in y_true[:95]] + [(-1000.0, -999.0)] * 5
    intervals = [[], valid] if empty_first else [valid, []]
    levels = [0.5, 0.95] if empty_first else [0.95, 0.5]

    result = compute_calibration_curve(y_true, intervals, levels=levels)

    assert result.evaluation_status == "incomplete"
    assert result.n_comparisons == 1
    assert result.points[0].n_observations == 100
    assert result.points[0].empirical_coverage == pytest.approx(0.95)
    assert result.ece == pytest.approx(0.0)
    assert result.max_ce == pytest.approx(0.0)
    assert result.is_well_calibrated is False


def test_all_skipped_interval_sets_preserve_unknown_metrics() -> None:
    result = compute_calibration_curve([1.0], [[], []], levels=[0.5, 0.95])

    assert result.evaluation_status == "incomplete"
    assert result.n_comparisons == 0
    assert result.points == []
    assert result.ece is None
    assert result.max_ce is None
    assert result.is_well_calibrated is False


@pytest.mark.parametrize("y_true", [[], [float("nan")], [float("inf")], [float("-inf")]])
def test_curve_rejects_unusable_observations(y_true: list[float]) -> None:
    with pytest.raises(ValueError, match="y_true"):
        compute_calibration_curve(y_true, [[(0.0, 2.0)] * len(y_true)], levels=[0.95])


@pytest.mark.parametrize("level", [float("nan"), float("inf"), -0.1, 1.1])
def test_curve_rejects_invalid_levels_even_for_skipped_sets(level: float) -> None:
    with pytest.raises(ValueError, match="levels"):
        compute_calibration_curve([1.0], [[]], levels=[level])


@pytest.mark.parametrize("tolerance", [float("nan"), float("inf"), -0.1])
def test_curve_rejects_unusable_tolerance(tolerance: float) -> None:
    with pytest.raises(ValueError, match="tolerance"):
        compute_calibration_curve([1.0], [[(0.0, 2.0)]], levels=[1.0], tolerance=tolerance)


@pytest.mark.parametrize("bounds", [(float("-inf"), 2.0), (0.0, float("inf")), (float("nan"), 2.0)])
def test_curve_rejects_nonfinite_bounds(bounds: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="bounds"):
        compute_calibration_curve([1.0], [[bounds]], levels=[1.0])
