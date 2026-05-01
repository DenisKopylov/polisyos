"""Expose calibration contracts, loss adapters, and the differentiable calibrator.

This package facade groups the APIs used to compare synthetic Foundry traces
against observed targets: measurement-aware target contracts, auxiliary loss
components, uncertainty adapters, and the optional JAX-backed `Calibrator`.
Imports that depend on JAX stay guarded so non-calibration environments can
still import the package and inspect the stable model contracts.
"""

from .dp_ci import (
    CIFPRInflationBound,
    CISampleSizeRequirement,
    CITestCalibration,
    CITestThresholdPolicy,
    DPContext,
    calibrate_discrete_ci,
    calibrate_kernel_ci,
    coerce_dp_context,
    effective_privacy_xi,
    required_n_chi2,
    required_n_kernel,
    resolve_ci_threshold_policy,
)
from .fabric_quality import (
    FabricCalibrationContext,
    fabric_calibration_context_from_decision_data,
    fabric_calibration_context_from_evidence_paths,
)
from .identifiability import (
    IdentifiabilityDiagnosticConfig,
    IdentifiabilityDiagnosticResult,
    IdentifiabilityDiagnosticStatus,
    IdentifiabilityMomentClass,
    IdentifiabilityReport,
    IdentifiabilityStatus,
    ParamIdentifiability,
    aggregate_moment_summary,
    attach_abm_identifiability_certificate_ref,
    attach_identifiability_diagnostic_ref,
    diagnose_identifiability,
    identifiability_diagnostic,
    load_identifiability_diagnostic_result,
)
from .report import (
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationReport,
    CalibrationSeriesComparison,
    CalibrationUncertainty,
    put_calibration_config,
    put_calibration_report,
)
from .robust_set_selector import (
    RobustSetCalibrator,
    SetSizeSelector,
    build_robust_set_spec_from_samples,
    gaussian_parametric_radius,
    select_robust_set_size,
)
from .uncertainty_adapter import envelope_from_calibration_param, envelopes_from_calibration

try:  # pragma: no cover - optional JAX dependency
    from .auxiliary import AuxLossComponent, InterferenceLossComponent
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
    from .measurement import (
        CalibrationTargetBundle,
        CalibrationTargetBundleManifest,
        DefaultMeasurementAwareLossAdapter,
        MeasurementAwareLossAdapter,
        MeasurementAwareLossConfig,
        MeasurementAwareTarget,
        compute_effective_weight,
    )
    from .multi_start import MultiStartResult, SingleRunResult
    from .pure_executor import StaticBundle, compile_program, run_pure_scan
except (ImportError, ModuleNotFoundError, SyntaxError, IndentationError):  # pragma: no cover
    Calibrator = None  # type: ignore[assignment]
    CalibratorInputs = None  # type: ignore[assignment]
    StaticBundle = None  # type: ignore[assignment]
    compile_program = None  # type: ignore[assignment]
    run_pure_scan = None  # type: ignore[assignment]
    HessianResult = None  # type: ignore[assignment]
    compute_hessian = None  # type: ignore[assignment]
    MultiStartResult = None  # type: ignore[assignment]
    SingleRunResult = None  # type: ignore[assignment]
    AuxLossComponent = None  # type: ignore[assignment]
    InterferenceLossComponent = None  # type: ignore[assignment]
    CalibrationTargetBundle = None  # type: ignore[assignment]
    CalibrationTargetBundleManifest = None  # type: ignore[assignment]
    DefaultMeasurementAwareLossAdapter = None  # type: ignore[assignment]
    MeasurementAwareLossAdapter = None  # type: ignore[assignment]
    MeasurementAwareLossConfig = None  # type: ignore[assignment]
    MeasurementAwareTarget = None  # type: ignore[assignment]
    compute_effective_weight = None  # type: ignore[assignment]
    log_bijector = None  # type: ignore[assignment]
    logit_bijector = None  # type: ignore[assignment]
    softplus_bijector = None  # type: ignore[assignment]
    affine_bijector = None  # type: ignore[assignment]
    chain_bijector = None  # type: ignore[assignment]
    inverse_bijector = None  # type: ignore[assignment]

__all__ = [
    "AuxLossComponent",
    "CIFPRInflationBound",
    "CISampleSizeRequirement",
    "CITestCalibration",
    "CITestThresholdPolicy",
    "CalibrationFitMetrics",
    "CalibrationFitQuality",
    "CalibrationReport",
    "CalibrationSeriesComparison",
    "CalibrationTargetBundle",
    "CalibrationTargetBundleManifest",
    "CalibrationUncertainty",
    "Calibrator",
    "CalibratorInputs",
    "DPContext",
    "DefaultMeasurementAwareLossAdapter",
    "FabricCalibrationContext",
    "HessianResult",
    "IdentifiabilityDiagnosticConfig",
    "IdentifiabilityDiagnosticResult",
    "IdentifiabilityDiagnosticStatus",
    "IdentifiabilityMomentClass",
    "IdentifiabilityReport",
    "IdentifiabilityStatus",
    "InterferenceLossComponent",
    "MeasurementAwareLossAdapter",
    "MeasurementAwareLossConfig",
    "MeasurementAwareTarget",
    "MultiStartResult",
    "ParamIdentifiability",
    "RobustSetCalibrator",
    "SetSizeSelector",
    "SingleRunResult",
    "StaticBundle",
    "aggregate_moment_summary",
    "attach_abm_identifiability_certificate_ref",
    "attach_identifiability_diagnostic_ref",
    "affine_bijector",
    "build_robust_set_spec_from_samples",
    "calibrate_discrete_ci",
    "calibrate_kernel_ci",
    "chain_bijector",
    "coerce_dp_context",
    "compile_program",
    "compute_effective_weight",
    "compute_hessian",
    "diagnose_identifiability",
    "effective_privacy_xi",
    "envelope_from_calibration_param",
    "envelopes_from_calibration",
    "fabric_calibration_context_from_decision_data",
    "fabric_calibration_context_from_evidence_paths",
    "gaussian_parametric_radius",
    "identifiability_diagnostic",
    "inverse_bijector",
    "load_identifiability_diagnostic_result",
    "log_bijector",
    "logit_bijector",
    "put_calibration_config",
    "put_calibration_report",
    "required_n_chi2",
    "required_n_kernel",
    "resolve_ci_threshold_policy",
    "run_pure_scan",
    "select_robust_set_size",
    "softplus_bijector",
]
