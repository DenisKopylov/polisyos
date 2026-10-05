"""Compatibility identity checks for the supported Scientist calibration alias."""

from __future__ import annotations

from polisyos.calibration import (
    CalibrationPoint,
    CalibrationResult,
    compute_calibration_curve,
)
from polisyos.calibration.curve import (
    CalibrationPoint as CurveCalibrationPoint,
    CalibrationResult as CurveCalibrationResult,
    compute_calibration_curve as curve_compute_calibration_curve,
)
from polisyos.scientist.methods.backtesting.calibration_curve import (
    CalibrationPoint as ScientistCalibrationPoint,
    CalibrationResult as ScientistCalibrationResult,
    compute_calibration_curve as scientist_compute_calibration_curve,
)


def test_canonical_and_compatibility_exports_preserve_identity() -> None:
    assert CalibrationPoint is CurveCalibrationPoint is ScientistCalibrationPoint
    assert CalibrationResult is CurveCalibrationResult is ScientistCalibrationResult
    assert compute_calibration_curve is curve_compute_calibration_curve
    assert compute_calibration_curve is scientist_compute_calibration_curve
