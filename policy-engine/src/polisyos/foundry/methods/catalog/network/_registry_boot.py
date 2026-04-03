"""Public network registry boot module API."""
from __future__ import annotations

from typing import Sequence

from .analysis import (
    CommunityDetectionEstimator,
    ContagionModelEstimator,
    InputOutputNetworkEstimator,
    MultiplexNetworkEstimator,
    NetworkDiffusionEstimator,
)

def register_network_methods() -> Sequence[type]:
    """Register network methods."""
    return (
        CommunityDetectionEstimator,
        InputOutputNetworkEstimator,
        NetworkDiffusionEstimator,
        ContagionModelEstimator,
        MultiplexNetworkEstimator,
    )


__all__ = ["register_network_methods"]
