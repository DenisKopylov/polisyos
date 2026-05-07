"""Expose spatial-analysis methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.extensions.registry import bootstrap_builtin_foundry_method_family
from polisyos.foundry.methods.selection.registry import MethodRegistry

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
    """Populate `registry` with spatial methods for autocorrelation, access, and panel workflows."""
    bootstrap_builtin_foundry_method_family("spatial", registry)


__all__ = [
    "AccessibilityData",
    "AccessibilityIndexEstimator",
    "GWREstimator",
    "GaussianProcessKrigingEstimator",
    "GravityFlowData",
    "GravityModelEstimator",
    "InverseDistanceWeightingEstimator",
    "MAUPSensitivityProfileEstimator",
    "MoranIEstimator",
    "SpatialData",
    "SpatialDurbinEstimator",
    "SpatialMicrosimulationEstimator",
    "SpatialResult",
    "SpatialSARARPanelEstimator",
    "SpatialSLXPanelEstimator",
    "TwoStepFCAAccessibilityEstimator",
    "ZoneBalanceDesignEstimator",
    "ensure_spatial_methods_registered",
    "register_spatial_methods",
]
