"""Compatibility surface for a Phase 4.1 split module."""

from __future__ import annotations

from . import _interference_contracts as _contracts
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

_FACADE_METADATA_KEYS = frozenset(
    {
        "__all__",
        "__annotations__",
        "__builtins__",
        "__cached__",
        "__doc__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__path__",
        "__spec__",
        "__warningregistry__",
        "_FACADE_METADATA_KEYS",
        "_contracts",
        "BipartiteInterferenceEstimator",
        "NetworkAIPWEstimator",
        "PartialInterferenceEstimator",
        "SpatialInterferenceEstimator",
        "build_block_stratified_network_causal_data",
        "build_interference_topology_contracts",
        "identify_interference_effect",
    }
)
for _facade_name in tuple(globals()):
    if _facade_name not in _FACADE_METADATA_KEYS:
        globals().pop(_facade_name, None)
del _facade_name
del _FACADE_METADATA_KEYS

InterferenceAugmentedGraph = _contracts.InterferenceAugmentedGraph
InterferenceIdentificationResult = _contracts.InterferenceIdentificationResult
_ReductionErrorBoundPlan = _contracts._ReductionErrorBoundPlan
_SimplicialSupportGate = _contracts._SimplicialSupportGate
_TopologyCertificatePlan = _contracts._TopologyCertificatePlan

del _contracts

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
