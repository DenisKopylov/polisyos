from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_microsim_methods
from .advanced import (
    BehavioralResponseEstimator,
    DynamicMicrosimEstimator,
    ImputationModelEstimator,
    TaxBenefitCalculatorEstimator,
)
from .calibration import ReweightingCalibrationEstimator
from .protocols import (
    BehavioralResponseResult,
    DynamicMicrosimResult,
    ImputationResult,
    MicrosimResult,
    ReweightingResult,
    SurveyMicroData,
    TaxBenefitResult,
)
from .static import StaticMicrosimEstimator


def ensure_microsim_methods_registered(registry: MethodRegistry | None = None) -> None:
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
    "ImputationModelEstimator",
    "ImputationResult",
    "MicrosimResult",
    "ReweightingCalibrationEstimator",
    "ReweightingResult",
    "StaticMicrosimEstimator",
    "SurveyMicroData",
    "TaxBenefitCalculatorEstimator",
    "TaxBenefitResult",
    "ensure_microsim_methods_registered",
    "register_microsim_methods",
]
