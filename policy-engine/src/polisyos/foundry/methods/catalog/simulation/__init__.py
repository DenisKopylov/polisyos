"""Public catalog simulation package API."""
from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_simulation_methods
from .dynamics import (
    AgentPopulationSimulationEstimator,
    QueueDiscreteEventEstimator,
    SEIRCompartmentalEstimator,
    SIRCompartmentalEstimator,
    StockFlowSystemDynamicsEstimator,
)
from .inference import (
    BootstrapInferenceEstimator,
    MonteCarloEstimator,
    PermutationTestEstimator,
)


def ensure_simulation_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Ensure simulation methods registered helper."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_simulation_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AgentPopulationSimulationEstimator",
    "BootstrapInferenceEstimator",
    "MonteCarloEstimator",
    "PermutationTestEstimator",
    "QueueDiscreteEventEstimator",
    "SEIRCompartmentalEstimator",
    "SIRCompartmentalEstimator",
    "StockFlowSystemDynamicsEstimator",
    "ensure_simulation_methods_registered",
    "register_simulation_methods",
]
