"""Compatibility surface for a Phase 4.1 split module."""

from __future__ import annotations

from ._interference_contracts import InterferenceAugmentedGraph, InterferenceIdentificationResult
from .api import (
    BipartiteInterferenceEstimator,
    NetworkAIPWEstimator,
    PartialInterferenceEstimator,
    SpatialInterferenceEstimator,
)
from .identification import (
    build_block_stratified_network_causal_data,
    build_interference_topology_contracts,
    identify_interference_effect,
)

__all__ = [
    "BipartiteInterferenceEstimator",
    "InterferenceAugmentedGraph",
    "InterferenceIdentificationResult",
    "NetworkAIPWEstimator",
    "PartialInterferenceEstimator",
    "SpatialInterferenceEstimator",
    "build_block_stratified_network_causal_data",
    "build_interference_topology_contracts",
    "identify_interference_effect",
]
