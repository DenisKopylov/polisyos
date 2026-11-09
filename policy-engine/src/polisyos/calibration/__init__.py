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


_EMPIRICAL_EVIDENCE_EXPORTS: dict[str, tuple[str, str]] = {
    "EmpiricalCalibrationContext": (
        "polisyos.calibration.forecast_bridge",
        "EmpiricalCalibrationContext",
    ),
    "EmpiricalCalibrationEvidenceRef": (
        "polisyos.calibration.forecast_bridge",
        "EmpiricalCalibrationEvidenceRef",
    ),
    "EvidenceArtifactRef": (
        "polisyos.calibration.forecast_bridge",
        "EvidenceArtifactRef",
    ),
    "REFERENCE_PROFILES": (
        "polisyos.calibration.forecast_bridge",
        "REFERENCE_PROFILES",
    ),
    "load_empirical_calibration_evidence": (
        "polisyos.calibration.forecast_bridge",
        "load_empirical_calibration_evidence",
    ),
    "persist_empirical_calibration_evidence": (
        "polisyos.calibration.forecast_bridge",
        "persist_empirical_calibration_evidence",
    ),
    "produce_empirical_calibration_evidence": (
        "polisyos.calibration.forecast_bridge",
        "produce_empirical_calibration_evidence",
    ),
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
    module_name, attr_name = _EMPIRICAL_EVIDENCE_EXPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded calibration symbols and deferred evidence bridge exports."""
    return sorted({*globals(), *_EMPIRICAL_EVIDENCE_EXPORTS})
