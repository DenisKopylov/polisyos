"""Calibration diagnostics public entrypoints."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from polisyos.calibration.curve import (
    CalibrationPoint,
    CalibrationResult,
    compute_calibration_curve,
)
from polisyos.calibration.diagnostics import evaluate_binary
from polisyos.calibration.diagnostics.adapters import to_validation_report
from polisyos.calibration.diagnostics.continuous import (
    evaluate_continuous,
    load_continuous_evaluation,
    persist_continuous_evaluation,
)
from polisyos.calibration.diagnostics.multiclass import evaluate_multiclass
from polisyos.calibration.recalibration import (
    apply_calibrator,
    compare_calibrators,
    fit_calibrator,
)

__all__ = [
    "REFERENCE_PROFILES",
    "CalibrationPoint",
    "CalibrationResult",
    "EmpiricalCalibrationContext",
    "EmpiricalCalibrationEvidenceRef",
    "EvidenceArtifactRef",
    "apply_calibrator",
    "compare_calibrators",
    "compute_calibration_curve",
    "evaluate_binary",
    "evaluate_continuous",
    "evaluate_multiclass",
    "fit_calibrator",
    "load_continuous_evaluation",
    "load_empirical_calibration_evidence",
    "persist_continuous_evaluation",
    "persist_empirical_calibration_evidence",
    "produce_empirical_calibration_evidence",
    "to_validation_report",
]


_EMPIRICAL_EVIDENCE_EXPORTS = {
    "EmpiricalCalibrationContext": "EmpiricalCalibrationContext",
    "EmpiricalCalibrationEvidenceRef": "EmpiricalCalibrationEvidenceRef",
    "EvidenceArtifactRef": "EvidenceArtifactRef",
    "REFERENCE_PROFILES": "REFERENCE_PROFILES",
    "load_empirical_calibration_evidence": "load_empirical_calibration_evidence",
    "persist_empirical_calibration_evidence": "persist_empirical_calibration_evidence",
    "produce_empirical_calibration_evidence": "produce_empirical_calibration_evidence",
}


if TYPE_CHECKING:
    from polisyos.calibration.forecast_bridge import (
        REFERENCE_PROFILES,
        EmpiricalCalibrationContext,
        EmpiricalCalibrationEvidenceRef,
        EvidenceArtifactRef,
        load_empirical_calibration_evidence,
        persist_empirical_calibration_evidence,
        produce_empirical_calibration_evidence,
    )


def __getattr__(name: str) -> object:
    """Resolve the predictive evidence bridge only when a consumer selects it."""
    if name not in _EMPIRICAL_EVIDENCE_EXPORTS:
        raise AttributeError(f"module 'polisyos.calibration' has no attribute {name!r}")
    module = importlib.import_module("polisyos.calibration.forecast_bridge")
    value = getattr(module, _EMPIRICAL_EVIDENCE_EXPORTS[name])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded calibration symbols and deferred evidence bridge exports."""
    return sorted(set(globals()) | set(_EMPIRICAL_EVIDENCE_EXPORTS))
