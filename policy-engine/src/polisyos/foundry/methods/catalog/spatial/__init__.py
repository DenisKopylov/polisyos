from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_spatial_methods
from .advanced import (
    GaussianProcessKrigingEstimator,
    InverseDistanceWeightingEstimator,
    MAUPSensitivityProfileEstimator,
    SpatialMicrosimulationEstimator,
    SpatialSARARPanelEstimator,
    SpatialSLXPanelEstimator,
    TwoStepFCAAccessibilityEstimator,
    ZoneBalanceDesignEstimator,
)
from .analysis import (
    AccessibilityIndexEstimator,
    GravityModelEstimator,
    GWREstimator,
    MoranIEstimator,
    SpatialDurbinEstimator,
)
from .protocols import AccessibilityData, GravityFlowData, SpatialData, SpatialResult


def ensure_spatial_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_spatial_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AccessibilityData",
    "AccessibilityIndexEstimator",
    "GravityFlowData",
    "GaussianProcessKrigingEstimator",
    "GravityModelEstimator",
    "GWREstimator",
    "InverseDistanceWeightingEstimator",
    "MAUPSensitivityProfileEstimator",
    "MoranIEstimator",
    "SpatialMicrosimulationEstimator",
    "SpatialSARARPanelEstimator",
    "SpatialSLXPanelEstimator",
    "SpatialData",
    "SpatialDurbinEstimator",
    "SpatialResult",
    "TwoStepFCAAccessibilityEstimator",
    "ZoneBalanceDesignEstimator",
    "ensure_spatial_methods_registered",
    "register_spatial_methods",
]
