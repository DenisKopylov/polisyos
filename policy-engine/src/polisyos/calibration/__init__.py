"""Calibration diagnostics public entrypoints."""

from __future__ import annotations

from polisyos.calibration.adapters import to_validation_report
from polisyos.calibration.continuous import evaluate_continuous
from polisyos.calibration.diagnostics import evaluate_binary
from polisyos.calibration.multiclass import evaluate_multiclass
from polisyos.calibration.recalibration import (
    apply_calibrator,
    compare_calibrators,
    fit_calibrator,
)

__all__ = [
    "apply_calibrator",
    "compare_calibrators",
    "evaluate_binary",
    "evaluate_continuous",
    "evaluate_multiclass",
    "fit_calibrator",
    "to_validation_report",
]
