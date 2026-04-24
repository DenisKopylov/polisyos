"""Expose sensitivity-analysis methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_sensitivity_methods
from .screening import (
    FASTEstimator,
    MorrisSensitivityEstimator,
    PAWNEstimator,
)
from .sobol import SobolFirstOrderEstimator
from .specification import SpecificationCurveEstimator


def ensure_sensitivity_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with sensitivity methods for screening and specification checks."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_sensitivity_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "FASTEstimator",
    "MorrisSensitivityEstimator",
    "PAWNEstimator",
    "SobolFirstOrderEstimator",
    "SpecificationCurveEstimator",
    "ensure_sensitivity_methods_registered",
    "register_sensitivity_methods",
]
