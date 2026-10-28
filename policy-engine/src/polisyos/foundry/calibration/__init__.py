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
    CITestThresholdPolicySet,
    DPContext,
    calibrate_discrete_ci,
    calibrate_kernel_ci,
    coerce_dp_context,
    effective_privacy_xi,
    required_n_chi2,
    required_n_kernel,
    resolve_ci_threshold_policy,
)
from .execution_basis import (
    CALIBRATION_RUNTIME_INPUT_CONTRACT,
    CALIBRATION_RUNTIME_INPUT_CONTRACT_V1_2,
    CALIBRATION_RUNTIME_INPUT_NAMES,
    CALIBRATION_RUNTIME_INPUT_NAMES_V1_2,
    RUNTIME_REGISTRY_MEMBER_CONTRACT,
    RUNTIME_REGISTRY_MEMBER_INPUT_NAMES,
    CalibrationExecutionInputBasis,
    CalibrationOrderedBatchBackendUnavailable,
    CalibrationOrderedBatchInput,
    CalibrationOrderedBatchRow,
    CalibrationParameterUnitIdentity,
    CalibrationResolvedParameterInput,
    CalibrationRuntimeInputBinding,
    CalibrationSourceRead,
    CalibrationSourceReadRefusal,
    CalibrationSourceStatus,
    CalibrationTargetInputIdentity,
    calibration_report_series_sha256,
    calibration_report_time_axis_sha256,
    canonical_input_sha256,
    classify_calibration_source_error,
    load_calibration_execution_input_basis,
    put_calibration_execution_input_basis,
    put_calibration_ordered_batch_input,
    read_calibration_execution_input_basis_source,
    read_calibration_model_source,
    read_calibration_registry_source,
    read_calibration_report_source,
    read_calibration_source,
    reconcile_ordered_batch_inputs,
    reconcile_ordered_batch_report_identity,
    reconcile_selected_runtime_input,
    record_calibration_source_error,
    replay_ordered_batch_report_projection,
    resolve_calibration_ordered_batch_input,
)
from .fabric_quality import (
    FabricCalibrationContext,
    fabric_calibration_context_from_decision_data,
    fabric_calibration_context_from_evidence_paths,
)
from .identifiability import (
    ExecuteResponseBasisCandidate,
    ExecuteResponseSourceIdentity,
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
    load_execute_response_basis_candidate,
    load_identifiability_diagnostic_result,
)
from .report import (
    CalibrationCoordinateProjection,
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationOrderedBatchReport,
    CalibrationReport,
    CalibrationSeriesComparison,
    CalibrationUncertainty,
    ordered_batch_fit_metrics,
    put_calibration_config,
    put_calibration_report,
    read_calibration_config_source,
)
from .robust_set_selector import (
    RobustSetCalibrator,
    SetSizeSelector,
    build_robust_set_spec_from_samples,
    gaussian_parametric_radius,
    select_robust_set_size,
)
from .uncertainty_adapter import (
    envelope_from_calibration_param,
    envelopes_from_calibration,
    persist_posterior_summary_from_method_evidence,
    propagate_selected_posterior_summary,
)

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
    from .calibrator import (
        Calibrator,
        CalibratorInputs,
        OrderedBatchCalibrationEvaluation,
        OrderedBatchCalibrationProfile,
        evaluate_ordered_batch_objective,
    )
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
    from .pure_executor import StaticBundle, apply_nodes_batch, compile_program, run_pure_scan
except (
    ImportError,
    ModuleNotFoundError,
    SyntaxError,
    IndentationError,
):  # pragma: no cover
    Calibrator = None  # type: ignore[assignment]
    CalibratorInputs = None  # type: ignore[assignment]
    OrderedBatchCalibrationEvaluation = None  # type: ignore[assignment]
    OrderedBatchCalibrationProfile = None  # type: ignore[assignment]
    evaluate_ordered_batch_objective = None  # type: ignore[assignment]
    StaticBundle = None  # type: ignore[assignment]
    apply_nodes_batch = None  # type: ignore[assignment]
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
    "CalibrationSourceRead",
    "CalibrationSourceReadRefusal",
    "CalibrationSourceStatus",
    "classify_calibration_source_error",
    "read_calibration_source",
    "read_calibration_config_source",
    "read_calibration_model_source",
    "read_calibration_registry_source",
    "read_calibration_execution_input_basis_source",
    "read_calibration_report_source",
    "record_calibration_source_error",
    "affine_bijector",
    "aggregate_moment_summary",
    "attach_abm_identifiability_certificate_ref",
    "attach_identifiability_diagnostic_ref",
    "apply_nodes_batch",
    "AuxLossComponent",
    "build_robust_set_spec_from_samples",
    "calibrate_discrete_ci",
    "calibrate_kernel_ci",
    "calibration_report_series_sha256",
    "calibration_report_time_axis_sha256",
    "CALIBRATION_RUNTIME_INPUT_CONTRACT",
    "CALIBRATION_RUNTIME_INPUT_CONTRACT_V1_2",
    "CALIBRATION_RUNTIME_INPUT_NAMES",
    "CALIBRATION_RUNTIME_INPUT_NAMES_V1_2",
    "CalibrationCoordinateProjection",
    "CalibrationExecutionInputBasis",
    "CalibrationOrderedBatchInput",
    "CalibrationOrderedBatchBackendUnavailable",
    "CalibrationOrderedBatchReport",
    "CalibrationOrderedBatchRow",
    "CalibrationFitMetrics",
    "CalibrationFitQuality",
    "CalibrationParameterUnitIdentity",
    "CalibrationReport",
    "CalibrationResolvedParameterInput",
    "CalibrationRuntimeInputBinding",
    "CalibrationSeriesComparison",
    "CalibrationTargetBundle",
    "CalibrationTargetBundleManifest",
    "CalibrationTargetInputIdentity",
    "CalibrationUncertainty",
    "Calibrator",
    "CalibratorInputs",
    "OrderedBatchCalibrationEvaluation",
    "OrderedBatchCalibrationProfile",
    "canonical_input_sha256",
    "chain_bijector",
    "CIFPRInflationBound",
    "CISampleSizeRequirement",
    "CITestCalibration",
    "CITestThresholdPolicy",
    "CITestThresholdPolicySet",
    "coerce_dp_context",
    "compile_program",
    "compute_effective_weight",
    "compute_hessian",
    "DefaultMeasurementAwareLossAdapter",
    "diagnose_identifiability",
    "DPContext",
    "effective_privacy_xi",
    "envelope_from_calibration_param",
    "envelopes_from_calibration",
    "evaluate_ordered_batch_objective",
    "ExecuteResponseBasisCandidate",
    "ExecuteResponseSourceIdentity",
    "fabric_calibration_context_from_decision_data",
    "fabric_calibration_context_from_evidence_paths",
    "FabricCalibrationContext",
    "gaussian_parametric_radius",
    "HessianResult",
    "identifiability_diagnostic",
    "IdentifiabilityDiagnosticConfig",
    "IdentifiabilityDiagnosticResult",
    "IdentifiabilityDiagnosticStatus",
    "IdentifiabilityMomentClass",
    "IdentifiabilityReport",
    "IdentifiabilityStatus",
    "InterferenceLossComponent",
    "inverse_bijector",
    "load_calibration_execution_input_basis",
    "load_execute_response_basis_candidate",
    "load_identifiability_diagnostic_result",
    "log_bijector",
    "logit_bijector",
    "MeasurementAwareLossAdapter",
    "MeasurementAwareLossConfig",
    "MeasurementAwareTarget",
    "MultiStartResult",
    "ParamIdentifiability",
    "persist_posterior_summary_from_method_evidence",
    "propagate_selected_posterior_summary",
    "put_calibration_config",
    "put_calibration_execution_input_basis",
    "put_calibration_report",
    "reconcile_ordered_batch_inputs",
    "put_calibration_ordered_batch_input",
    "resolve_calibration_ordered_batch_input",
    "reconcile_ordered_batch_report_identity",
    "replay_ordered_batch_report_projection",
    "ordered_batch_fit_metrics",
    "reconcile_selected_runtime_input",
    "required_n_chi2",
    "required_n_kernel",
    "resolve_ci_threshold_policy",
    "RobustSetCalibrator",
    "run_pure_scan",
    "RUNTIME_REGISTRY_MEMBER_CONTRACT",
    "RUNTIME_REGISTRY_MEMBER_INPUT_NAMES",
    "select_robust_set_size",
    "SetSizeSelector",
    "SingleRunResult",
    "softplus_bijector",
    "StaticBundle",
]
