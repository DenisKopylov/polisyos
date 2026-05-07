"""Expose microsimulation methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.extensions.registry import bootstrap_builtin_foundry_method_family
from polisyos.foundry.methods.selection.registry import MethodRegistry

from ._registry_boot import register_microsim_methods
from .advanced import (
    BehavioralResponseEstimator,
    DynamicMicrosimEstimator,
    HeterogeneousBehavioralResponseEstimator,
    ImputationModelEstimator,
    TaxBenefitCalculatorEstimator,
)
from .calibration import ReweightingCalibrationEstimator
from .dynamic_validation import attach_dynamic_validation, run_dynamic_validation
from .inverse import InverseBehavioralCalibrationEstimator
from .mnar import MNARIncomeBoundsEstimator
from .protocols import (
    BehavioralResponseResult,
    DynamicMicrosimResult,
    DynamicMicrosimResultV2,
    DynamicMicrosimValidationDiagnostic,
    DynamicValidationSensitivitySpec,
    DynamicValidationSpec,
    HeterogeneousBehavioralResponseResult,
    HorizonBiasEnvelope,
    ImputationResult,
    InverseBehavioralCalibrationResult,
    InverseBehavioralIdentifiedSet,
    MicrosimResult,
    MNARIncomeAssumptionVector,
    MNARIncomeBoundsDiagnostics,
    MNARIncomeBoundsInterval,
    MNARIncomeBoundsProvenance,
    MNARIncomeBoundsResult,
    MNARIncomeBoundsTarget,
    ReweightingCompatibilityReason,
    ReweightingCompatibilityStatus,
    ReweightingCompatibilityTestMethod,
    ReweightingResult,
    ReweightingTargetCompatibility,
    ReweightingTargetGap,
    ReweightingTargetKind,
    ReweightingTargetSpec,
    SensitivityRunResult,
    SurveyMicroData,
    TaxBenefitResult,
    ValidationCellResult,
    ValidationMomentSpec,
    ValidationOmnibusTest,
    upgrade_dynamic_microsim_result,
)
from .static import StaticMicrosimEstimator


def ensure_microsim_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with microsimulation methods and their result contracts."""
    bootstrap_builtin_foundry_method_family("microsim", registry)


__all__ = [
    "BehavioralResponseEstimator",
    "BehavioralResponseResult",
    "DynamicMicrosimEstimator",
    "DynamicMicrosimResult",
    "DynamicMicrosimResultV2",
    "DynamicMicrosimValidationDiagnostic",
    "DynamicValidationSensitivitySpec",
    "DynamicValidationSpec",
    "HeterogeneousBehavioralResponseEstimator",
    "HeterogeneousBehavioralResponseResult",
    "HorizonBiasEnvelope",
    "ImputationModelEstimator",
    "ImputationResult",
    "InverseBehavioralCalibrationEstimator",
    "InverseBehavioralCalibrationResult",
    "InverseBehavioralIdentifiedSet",
    "MNARIncomeAssumptionVector",
    "MNARIncomeBoundsDiagnostics",
    "MNARIncomeBoundsEstimator",
    "MNARIncomeBoundsInterval",
    "MNARIncomeBoundsProvenance",
    "MNARIncomeBoundsResult",
    "MNARIncomeBoundsTarget",
    "MicrosimResult",
    "ReweightingCalibrationEstimator",
    "ReweightingCompatibilityReason",
    "ReweightingCompatibilityStatus",
    "ReweightingCompatibilityTestMethod",
    "ReweightingResult",
    "ReweightingTargetCompatibility",
    "ReweightingTargetGap",
    "ReweightingTargetKind",
    "ReweightingTargetSpec",
    "SensitivityRunResult",
    "StaticMicrosimEstimator",
    "SurveyMicroData",
    "TaxBenefitCalculatorEstimator",
    "TaxBenefitResult",
    "ValidationCellResult",
    "ValidationMomentSpec",
    "ValidationOmnibusTest",
    "attach_dynamic_validation",
    "ensure_microsim_methods_registered",
    "register_microsim_methods",
    "run_dynamic_validation",
    "upgrade_dynamic_microsim_result",
]
