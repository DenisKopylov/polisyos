"""Scientist compatibility exports for shared calibration curve diagnostics."""

from __future__ import annotations

from polisyos.calibration.curve import (
    CalibrationPoint,
    CalibrationResult,
    compute_calibration_curve,
)

__all__ = [
    "CalibrationPoint",
    "CalibrationResult",
    "compute_calibration_curve",
]
