"""Public catalog policy package API."""
from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_policy_methods
from .evaluation import (
    BudgetImpactEstimator,
    ExAnteSimulationEstimator,
    PolicyScorecardEstimator,
)
from .mcda import (
    AHPEstimator,
    ELECTREEstimator,
    TOPSISEstimator,
)
from .welfare import (
    AtkinsonSWFEstimator,
    CostBenefitAnalysisEstimator,
    CostEffectivenessEstimator,
    RawlsianSWFEstimator,
    SenCapabilityEstimator,
    UtilitarianSWFEstimator,
)


def ensure_policy_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Ensure policy methods registered helper."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_policy_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AHPEstimator",
    "AtkinsonSWFEstimator",
    "BudgetImpactEstimator",
    "CostBenefitAnalysisEstimator",
    "CostEffectivenessEstimator",
    "ELECTREEstimator",
    "ExAnteSimulationEstimator",
    "PolicyScorecardEstimator",
    "RawlsianSWFEstimator",
    "SenCapabilityEstimator",
    "TOPSISEstimator",
    "UtilitarianSWFEstimator",
    "ensure_policy_methods_registered",
    "register_policy_methods",
]
