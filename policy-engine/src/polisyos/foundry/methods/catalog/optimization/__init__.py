from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_optimization_methods
from .io_model import LeontiefInputOutput
from .lp import ResourceLP
from .milp import BudgetMILP
from .protocols import (
    AllocationItem,
    IOModelResult,
    InputOutputMethod,
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
    "IOModelResult",
    "InputOutputMethod",
    "LeontiefInputOutput",
    "OptimizationMethod",
    "OptimizationProblem",
    "OptimizationResult",
    "ResourceConstraint",
    "ResourceLP",
    "ensure_optimization_methods_registered",
    "register_optimization_methods",
]
