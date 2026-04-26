"""DES/ABM coupling runtime for policy simulations."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AdaptiveAgentABMKernel",
    "CoupledContractsExecutor",
    "CoupledRuntimeState",
    "CoupledStepResult",
    "CouplingMessage",
    "DefaultPolicyCoupler",
    "NoOpABMKernel",
    "PairedMonteCarloResult",
    "ParticleFilterResult",
    "QueueDESKernel",
    "QueueMLEEstimate",
    "SMMResult",
    "UnemploymentClaimABMKernel",
    "calibrate_coupled_smm",
    "estimate_queue_mle",
    "extract_coupled_summary",
    "filter_queue_counts",
    "paired_monte_carlo_effect",
    "summary_distance",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "AdaptiveAgentABMKernel": ("polisyos.foundry.coupling.abm_kernel", "AdaptiveAgentABMKernel"),
    "CoupledContractsExecutor": (
        "polisyos.foundry.coupling.executor",
        "CoupledContractsExecutor",
    ),
    "CoupledRuntimeState": ("polisyos.foundry.coupling.executor", "CoupledRuntimeState"),
    "CoupledStepResult": ("polisyos.foundry.coupling.executor", "CoupledStepResult"),
    "CouplingMessage": ("polisyos.foundry.coupling.messages", "CouplingMessage"),
    "DefaultPolicyCoupler": ("polisyos.foundry.coupling.coupler", "DefaultPolicyCoupler"),
    "NoOpABMKernel": ("polisyos.foundry.coupling.abm_kernel", "NoOpABMKernel"),
    "PairedMonteCarloResult": (
        "polisyos.foundry.coupling.estimation",
        "PairedMonteCarloResult",
    ),
    "ParticleFilterResult": (
        "polisyos.foundry.coupling.estimation",
        "ParticleFilterResult",
    ),
    "QueueDESKernel": ("polisyos.foundry.coupling.des_kernel", "QueueDESKernel"),
    "QueueMLEEstimate": ("polisyos.foundry.coupling.estimation", "QueueMLEEstimate"),
    "SMMResult": ("polisyos.foundry.coupling.estimation", "SMMResult"),
    "UnemploymentClaimABMKernel": (
        "polisyos.foundry.coupling.abm_kernel",
        "UnemploymentClaimABMKernel",
    ),
    "calibrate_coupled_smm": (
        "polisyos.foundry.coupling.estimation",
        "calibrate_coupled_smm",
    ),
    "estimate_queue_mle": ("polisyos.foundry.coupling.estimation", "estimate_queue_mle"),
    "extract_coupled_summary": (
        "polisyos.foundry.coupling.estimation",
        "extract_coupled_summary",
    ),
    "filter_queue_counts": ("polisyos.foundry.coupling.estimation", "filter_queue_counts"),
    "paired_monte_carlo_effect": (
        "polisyos.foundry.coupling.estimation",
        "paired_monte_carlo_effect",
    ),
    "summary_distance": ("polisyos.foundry.coupling.estimation", "summary_distance"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.coupling' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
