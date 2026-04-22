"""Public network registry boot module API."""
from __future__ import annotations

from typing import Sequence

from .analysis import (
    CommunityDetectionEstimator,
    ContagionModelEstimator,
    InputOutputNetworkEstimator,
    MultiplexNetworkEstimator,
    NetworkMissingnessAssessmentEstimator,
    NetworkDiffusionEstimator,
    PeerEffectDecompositionEstimator,
)
from .ergm import DiffusionNullTestEstimator, ERGMNullModelEstimator
from .sbm import SBMStratificationEstimator
from .strategic import StrategicNetworkFormationEstimator


def register_network_methods() -> Sequence[type]:
    """Register network methods."""
    return (
        CommunityDetectionEstimator,
        InputOutputNetworkEstimator,
        NetworkDiffusionEstimator,
        NetworkMissingnessAssessmentEstimator,
        PeerEffectDecompositionEstimator,
        ContagionModelEstimator,
        MultiplexNetworkEstimator,
        SBMStratificationEstimator,
        ERGMNullModelEstimator,
        DiffusionNullTestEstimator,
        StrategicNetworkFormationEstimator,
    )


__all__ = ["register_network_methods"]
