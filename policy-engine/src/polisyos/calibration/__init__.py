"""Calibration diagnostics public entrypoints."""

from __future__ import annotations

import importlib
from typing import Any

from polisyos.calibration.adapters import to_validation_report
from polisyos.calibration.continuous import (
    evaluate_continuous,
    load_continuous_evaluation,
    persist_continuous_evaluation,
)
from polisyos.calibration.curve import (
    CalibrationPoint,
    CalibrationResult,
    compute_calibration_curve,
)
from polisyos.calibration.diagnostics import evaluate_binary
from polisyos.calibration.multiclass import evaluate_multiclass
from polisyos.calibration.recalibration import (
    apply_calibrator,
    compare_calibrators,
    fit_calibrator,
)

_FORECAST_EXPORTS = frozenset(
    {
        "PREDICTIVE_AUTHORITY_DENIALS",
        "REFERENCE_PROFILES",
        "EmpiricalCalibrationContext",
        "EmpiricalCalibrationEvidenceRef",
        "EvidenceArtifactRef",
        "ForecastCalibrationProfile",
        "ForecastCandidateReceipt",
        "ForecastCandidateReceiptRef",
        "load_empirical_calibration_evidence",
        "load_forecast_calibration_profile",
        "persist_empirical_calibration_evidence",
        "persist_forecast_candidate_receipt",
        "produce_empirical_calibration_evidence",
    }
)


def __getattr__(name: str) -> Any:
    """Resolve the neutral predictive evidence API to its canonical owner."""
    if name not in _FORECAST_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(".forecast_bridge", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _FORECAST_EXPORTS)


__all__ = [
    "CalibrationPoint",
    "CalibrationResult",
    "apply_calibrator",
    "compare_calibrators",
    "compute_calibration_curve",
    "evaluate_binary",
    "evaluate_continuous",
    "evaluate_multiclass",
    "fit_calibrator",
    "load_continuous_evaluation",
    "persist_continuous_evaluation",
    "to_validation_report",
] + sorted(_FORECAST_EXPORTS)
