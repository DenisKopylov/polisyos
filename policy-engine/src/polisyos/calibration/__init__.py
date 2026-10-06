"""Calibration diagnostics public entrypoints."""

from __future__ import annotations

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
from polisyos.calibration.forecast_bridge import (
    PREDICTIVE_AUTHORITY_DENIALS,
    REFERENCE_PROFILES,
    EmpiricalCalibrationContext,
    EmpiricalCalibrationEvidenceRef,
    EvidenceArtifactRef,
    ForecastCalibrationProfile,
    ForecastCandidateReceipt,
    ForecastCandidateReceiptRef,
    load_empirical_calibration_evidence,
    load_forecast_calibration_profile,
    persist_empirical_calibration_evidence,
    persist_forecast_candidate_receipt,
    produce_empirical_calibration_evidence,
)
from polisyos.calibration.multiclass import evaluate_multiclass
from polisyos.calibration.recalibration import (
    apply_calibrator,
    compare_calibrators,
    fit_calibrator,
)

__all__ = [
    "PREDICTIVE_AUTHORITY_DENIALS",
    "REFERENCE_PROFILES",
    "CalibrationPoint",
    "CalibrationResult",
    "EmpiricalCalibrationContext",
    "EmpiricalCalibrationEvidenceRef",
    "EvidenceArtifactRef",
    "ForecastCalibrationProfile",
    "ForecastCandidateReceipt",
    "ForecastCandidateReceiptRef",
    "apply_calibrator",
    "compare_calibrators",
    "compute_calibration_curve",
    "evaluate_binary",
    "evaluate_continuous",
    "evaluate_multiclass",
    "fit_calibrator",
    "load_continuous_evaluation",
    "load_empirical_calibration_evidence",
    "load_forecast_calibration_profile",
    "persist_continuous_evaluation",
    "persist_empirical_calibration_evidence",
    "persist_forecast_candidate_receipt",
    "produce_empirical_calibration_evidence",
    "to_validation_report",
]
