"""Tests for calibration curve analysis."""

from __future__ import annotations

from polisyos.scientist.backtesting.calibration_curve import (
    compute_calibration_curve,
)


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

    def test_zero_coverage(self):
        y_true = [1.0, 2.0, 3.0]
        intervals = [(-100.0, -99.0)] * 3  # no coverage
        result = compute_calibration_curve(y_true, [intervals], levels=[0.9])
        assert result.points[0].empirical_coverage == 0.0
        assert result.ece > 0

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
        assert result.ece == 0.0
        assert result.is_well_calibrated is True
