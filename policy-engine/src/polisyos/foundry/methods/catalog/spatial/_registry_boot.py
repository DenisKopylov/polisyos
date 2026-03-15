from __future__ import annotations

from typing import Sequence

from .analysis import (
    AccessibilityIndexEstimator,
    GravityModelEstimator,
    GWREstimator,
    MoranIEstimator,
    SpatialDurbinEstimator,
)

def register_spatial_methods() -> Sequence[type]:
    return (
        MoranIEstimator,
        GWREstimator,
        SpatialDurbinEstimator,
        GravityModelEstimator,
        AccessibilityIndexEstimator,
    )


__all__ = ["register_spatial_methods"]
