"""Public simulation registry boot module API."""
from __future__ import annotations

from polisyos.foundry.methods.catalog.simulation.demography import (
    StaticAgingSimulationEstimator,
)
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    AgentPopulationSimulationEstimator,
    QueueDiscreteEventEstimator,
    SEIRCompartmentalEstimator,
    SIRCompartmentalEstimator,
    StockFlowSystemDynamicsEstimator,
)
from polisyos.foundry.methods.catalog.simulation.inference import (
    BootstrapInferenceEstimator,
    MonteCarloEstimator,
    PermutationTestEstimator,
)


def register_simulation_methods() -> tuple[type, ...]:
    """Register simulation methods."""
    return (
        StockFlowSystemDynamicsEstimator,
        QueueDiscreteEventEstimator,
        SIRCompartmentalEstimator,
        SEIRCompartmentalEstimator,
        StaticAgingSimulationEstimator,
        AgentPopulationSimulationEstimator,
        MonteCarloEstimator,
        BootstrapInferenceEstimator,
        PermutationTestEstimator,
    )


__all__ = ["register_simulation_methods"]
