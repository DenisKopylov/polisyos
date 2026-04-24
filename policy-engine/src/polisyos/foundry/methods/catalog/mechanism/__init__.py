"""Expose executable mechanism methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_mechanism_methods
from .runtime import (
    AdaptiveAgentMechanismMethod,
    IncomeTaxMechanismMethod,
    LaborMarketMechanismMethod,
    QueueMechanismMethod,
    TaxSubsidyMechanismMethod,
)


def ensure_mechanism_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with mechanism methods used by compile and execute pipelines."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_mechanism_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AdaptiveAgentMechanismMethod",
    "IncomeTaxMechanismMethod",
    "LaborMarketMechanismMethod",
    "QueueMechanismMethod",
    "TaxSubsidyMechanismMethod",
    "ensure_mechanism_methods_registered",
    "register_mechanism_methods",
]
