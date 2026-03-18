from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from .advanced_stochastic import BilevelOptimizationEstimator, ChanceConstrainedEstimator
from .combinatorial import KnapsackEstimator, VehicleRoutingEstimator
from .convex import QuadraticProgramEstimator, RobustOptimizationEstimator
from ._registry_boot import register_optimization_methods
from .game_theory import NashEquilibriumEstimator
from .io_model import LeontiefInputOutput
from .lp import ResourceLP
from .milp import BudgetMILP
from .multiobjective import MultiObjectiveNSGA2Estimator
from .sequential import (
    DynamicProgrammingEstimator,
    SecondOrderConeProgramEstimator,
    TwoStageStochasticProgramEstimator,
)
from .protocols import (
    AllocationItem,
    InputOutputMethod,
    IOModelResult,
    OptimizationMethod,
    OptimizationProblem,
    OptimizationResult,
    ResourceConstraint,
)


def ensure_optimization_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_optimization_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AllocationItem",
    "BudgetMILP",
    "IOModelResult",
    "InputOutputMethod",
    "LeontiefInputOutput",
    "MultiObjectiveNSGA2Estimator",
    "OptimizationMethod",
    "OptimizationProblem",
    "OptimizationResult",
    "QuadraticProgramEstimator",
    "RobustOptimizationEstimator",
    "SecondOrderConeProgramEstimator",
    "TwoStageStochasticProgramEstimator",
    "DynamicProgrammingEstimator",
    "ResourceConstraint",
    "ResourceLP",
    "KnapsackEstimator",
    "VehicleRoutingEstimator",
    "NashEquilibriumEstimator",
    "BilevelOptimizationEstimator",
    "ChanceConstrainedEstimator",
    "ensure_optimization_methods_registered",
    "register_optimization_methods",
]
