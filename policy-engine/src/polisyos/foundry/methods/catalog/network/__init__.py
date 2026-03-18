from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_network_methods
from .analysis import (
    CommunityDetectionEstimator,
    ContagionModelEstimator,
    InputOutputNetworkEstimator,
    MultiplexNetworkEstimator,
    NetworkDiffusionEstimator,
)
from .protocols import MultiplexNetworkData, NetworkData, NetworkResult


def ensure_network_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_network_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "CommunityDetectionEstimator",
    "ContagionModelEstimator",
    "InputOutputNetworkEstimator",
    "MultiplexNetworkData",
    "MultiplexNetworkEstimator",
    "NetworkData",
    "NetworkDiffusionEstimator",
    "NetworkResult",
    "ensure_network_methods_registered",
    "register_network_methods",
]
