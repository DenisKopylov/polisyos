"""Expose validation methods and register them into the Foundry catalog."""
from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_validation_methods
from .diagnostics import (
    CalibrationDiagnosticEstimator,
    CrossValidationEstimator,
    WalkForwardEstimator,
)
from .scoring import ProbabilisticScoringEstimator


def ensure_validation_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with validation methods for backtests and diagnostics."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_validation_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "CalibrationDiagnosticEstimator",
    "CrossValidationEstimator",
    "ProbabilisticScoringEstimator",
    "WalkForwardEstimator",
    "ensure_validation_methods_registered",
    "register_validation_methods",
]
