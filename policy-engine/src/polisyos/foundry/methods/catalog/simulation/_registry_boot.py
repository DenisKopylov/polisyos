"""Public simulation registry boot module API."""

from __future__ import annotations

from polisyos.foundry.methods.catalog.simulation.coupled import (
    CoupledPairedMonteCarloEstimator,
    CoupledPolicySimulationEstimator,
    CoupledQueueMLEEstimator,
    CoupledQueueParticleFilterEstimator,
    CoupledSMMEstimator,
)
from polisyos.foundry.methods.catalog.simulation.demography import (
    StaticAgingSimulationEstimator,
)
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    AgentPopulationSimulationEstimator,
    CanonicalDynamicalSystemEstimator,
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
        CanonicalDynamicalSystemEstimator,
        QueueDiscreteEventEstimator,
        SIRCompartmentalEstimator,
        SEIRCompartmentalEstimator,
        StaticAgingSimulationEstimator,
        AgentPopulationSimulationEstimator,
        CoupledPolicySimulationEstimator,
        CoupledQueueMLEEstimator,
        CoupledSMMEstimator,
        CoupledQueueParticleFilterEstimator,
        CoupledPairedMonteCarloEstimator,
        MonteCarloEstimator,
        BootstrapInferenceEstimator,
        PermutationTestEstimator,
    )


__all__ = ["register_simulation_methods"]
