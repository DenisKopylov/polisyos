"""Public spatial registry boot module API."""

from __future__ import annotations

from collections.abc import Sequence

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


def register_spatial_methods() -> Sequence[type]:
    """Register spatial methods."""
    return (
        MoranIEstimator,
        GWREstimator,
        SpatialDurbinEstimator,
        GravityModelEstimator,
        AccessibilityIndexEstimator,
        GaussianProcessKrigingEstimator,
        InverseDistanceWeightingEstimator,
        SpatialSLXPanelEstimator,
        SpatialSARARPanelEstimator,
        TwoStepFCAAccessibilityEstimator,
        SpatialMicrosimulationEstimator,
        ZoneBalanceDesignEstimator,
        MAUPSensitivityProfileEstimator,
    )


__all__ = ["register_spatial_methods"]
