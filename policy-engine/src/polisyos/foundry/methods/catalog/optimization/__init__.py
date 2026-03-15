from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from .convex import QuadraticProgramEstimator, RobustOptimizationEstimator
from ._registry_boot import register_optimization_methods
from .io_model import InputOutputLeontiefModel, LeontiefInputOutput
from .lp import LinearResourceLP, ResourceLP
from .milp import BudgetMILP, IntegerBudgetMILP
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
    reg = registry or MethodRegistry.get_instance()
    for method_class in register_optimization_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AllocationItem",
    "BudgetMILP",
    "InputOutputLeontiefModel",
    "IntegerBudgetMILP",
    "IOModelResult",
    "InputOutputMethod",
    "LinearResourceLP",
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
    "ensure_optimization_methods_registered",
    "register_optimization_methods",
]
