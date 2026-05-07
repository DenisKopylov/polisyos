"""Expose simulation dynamics and inference methods for synthetic runtime outputs."""

from __future__ import annotations

from polisyos.foundry.extensions.registry import bootstrap_builtin_foundry_method_family
from polisyos.foundry.methods.selection.registry import MethodRegistry

from ._registry_boot import register_simulation_methods
from .coupled import (
    CoupledPairedMonteCarloEstimator,
    CoupledPolicySimulationEstimator,
    CoupledQueueMLEEstimator,
    CoupledQueueParticleFilterEstimator,
    CoupledSMMEstimator,
)
from .demography import StaticAgingResult, StaticAgingSimulationEstimator
from .dynamics import (
    AgentPopulationSimulationEstimator,
    CanonicalDynamicalSystemEstimator,
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
    """Register built-in simulation methods into `registry` or the global singleton."""
    bootstrap_builtin_foundry_method_family("simulation", registry)


__all__ = [
    "AgentPopulationSimulationEstimator",
    "BootstrapInferenceEstimator",
    "CanonicalDynamicalSystemEstimator",
    "CoupledPairedMonteCarloEstimator",
    "CoupledPolicySimulationEstimator",
    "CoupledQueueMLEEstimator",
    "CoupledQueueParticleFilterEstimator",
    "CoupledSMMEstimator",
    "MonteCarloEstimator",
    "PermutationTestEstimator",
    "QueueDiscreteEventEstimator",
    "SEIRCompartmentalEstimator",
    "SIRCompartmentalEstimator",
    "StaticAgingResult",
    "StaticAgingSimulationEstimator",
    "StockFlowSystemDynamicsEstimator",
    "ensure_simulation_methods_registered",
    "register_simulation_methods",
]
