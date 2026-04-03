"""Public foundry calibration package API."""
from .identifiability import (
    IdentifiabilityReport,
    IdentifiabilityStatus,
    ParamIdentifiability,
    diagnose_identifiability,
)
from .auxiliary import AuxLossComponent, InterferenceLossComponent
from .report import (
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationReport,
    CalibrationSeriesComparison,
    CalibrationUncertainty,
    put_calibration_config,
    put_calibration_report,
)
from .measurement import (
    CalibrationTargetBundle,
    CalibrationTargetBundleManifest,
    DefaultMeasurementAwareLossAdapter,
    MeasurementAwareLossAdapter,
    MeasurementAwareLossConfig,
    MeasurementAwareTarget,
    compute_effective_weight,
)
from .uncertainty_adapter import envelope_from_calibration_param, envelopes_from_calibration

try:  # pragma: no cover - optional JAX dependency
    from .bijectors import (
        affine_bijector,
        chain_bijector,
        inverse_bijector,
        log_bijector,
        logit_bijector,
        softplus_bijector,
    )
    from .calibrator import Calibrator, CalibratorInputs
    from .hessian import HessianResult, compute_hessian
    from .multi_start import MultiStartResult, SingleRunResult
    from .pure_executor import StaticBundle, compile_program, run_pure_scan
except (ModuleNotFoundError, SyntaxError, IndentationError):  # pragma: no cover
    Calibrator = None  # type: ignore[assignment]
    CalibratorInputs = None  # type: ignore[assignment]
    StaticBundle = None  # type: ignore[assignment]
    compile_program = None  # type: ignore[assignment]
    run_pure_scan = None  # type: ignore[assignment]
    HessianResult = None  # type: ignore[assignment]
    compute_hessian = None  # type: ignore[assignment]
    MultiStartResult = None  # type: ignore[assignment]
    SingleRunResult = None  # type: ignore[assignment]
    log_bijector = None  # type: ignore[assignment]
    logit_bijector = None  # type: ignore[assignment]
    softplus_bijector = None  # type: ignore[assignment]
    affine_bijector = None  # type: ignore[assignment]
    chain_bijector = None  # type: ignore[assignment]
    inverse_bijector = None  # type: ignore[assignment]

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
    "HessianResult",
    "compute_hessian",
    "CalibrationTargetBundleManifest",
    "CalibrationTargetBundle",
    "AuxLossComponent",
    "DefaultMeasurementAwareLossAdapter",
    "IdentifiabilityReport",
    "IdentifiabilityStatus",
    "InterferenceLossComponent",
    "MeasurementAwareLossAdapter",
    "MeasurementAwareLossConfig",
    "MeasurementAwareTarget",
    "compute_effective_weight",
    "ParamIdentifiability",
    "diagnose_identifiability",
    "MultiStartResult",
    "SingleRunResult",
    "log_bijector",
    "logit_bijector",
    "softplus_bijector",
    "affine_bijector",
    "chain_bijector",
    "inverse_bijector",
]
