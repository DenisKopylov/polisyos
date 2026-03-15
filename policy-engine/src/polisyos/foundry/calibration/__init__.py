from .report import (
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationReport,
    CalibrationSeriesComparison,
    CalibrationUncertainty,
    put_calibration_config,
    put_calibration_report,
)
from .uncertainty_adapter import envelope_from_calibration_param, envelopes_from_calibration

try:  # pragma: no cover - optional JAX dependency
    from .calibrator import Calibrator, CalibratorInputs
    from .pure_executor import StaticBundle, compile_program, run_pure_scan
except ModuleNotFoundError:  # pragma: no cover
    Calibrator = None  # type: ignore[assignment]
    CalibratorInputs = None  # type: ignore[assignment]
    StaticBundle = None  # type: ignore[assignment]
    compile_program = None  # type: ignore[assignment]
    run_pure_scan = None  # type: ignore[assignment]

__all__ = [
    "Calibrator",
    "CalibratorInputs",
    "StaticBundle",
    "compile_program",
    "run_pure_scan",
    "CalibrationReport",
    "CalibrationSeriesComparison",
    "CalibrationFitMetrics",
    "CalibrationFitQuality",
    "CalibrationUncertainty",
    "envelope_from_calibration_param",
    "envelopes_from_calibration",
    "put_calibration_config",
    "put_calibration_report",
]
