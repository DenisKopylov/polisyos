"""Expose microsimulation methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_microsim_methods
from .advanced import (
    BehavioralResponseEstimator,
    DynamicMicrosimEstimator,
    HeterogeneousBehavioralResponseEstimator,
    ImputationModelEstimator,
    TaxBenefitCalculatorEstimator,
)
from .calibration import ReweightingCalibrationEstimator
from .inverse import InverseBehavioralCalibrationEstimator
from .mnar import MNARIncomeBoundsEstimator
from .protocols import (
    BehavioralResponseResult,
    DynamicMicrosimResult,
    HeterogeneousBehavioralResponseResult,
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
    SurveyMicroData,
    TaxBenefitResult,
)
from .static import StaticMicrosimEstimator


def ensure_microsim_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with microsimulation methods and their result contracts."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_microsim_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "BehavioralResponseEstimator",
    "BehavioralResponseResult",
    "DynamicMicrosimEstimator",
    "DynamicMicrosimResult",
    "HeterogeneousBehavioralResponseEstimator",
    "HeterogeneousBehavioralResponseResult",
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
    "StaticMicrosimEstimator",
    "SurveyMicroData",
    "TaxBenefitCalculatorEstimator",
    "TaxBenefitResult",
    "ensure_microsim_methods_registered",
    "register_microsim_methods",
]
