"""Expose executable mechanism methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.extensions.registry import bootstrap_builtin_foundry_method_family
from polisyos.foundry.methods.selection.registry import MethodRegistry

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
    bootstrap_builtin_foundry_method_family("mechanism", registry)


__all__ = [
    "AdaptiveAgentMechanismMethod",
    "IncomeTaxMechanismMethod",
    "LaborMarketMechanismMethod",
    "QueueMechanismMethod",
    "TaxSubsidyMechanismMethod",
    "ensure_mechanism_methods_registered",
    "register_mechanism_methods",
]
