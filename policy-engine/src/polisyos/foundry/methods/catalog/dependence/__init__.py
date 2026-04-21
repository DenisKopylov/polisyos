"""Expose dependence diagnostics and register them into the Foundry catalog."""
from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_dependence_methods
from .diagnostics import GraphDependenceDiagnosticEstimator
from .protocols import (
    DependenceDiagnosticData,
    DependenceDiagnosticResult,
    DependenceGraphSpec,
    GraphDependenceDiagnostic,
)


def ensure_dependence_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with shared dependence diagnostics."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_dependence_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "DependenceDiagnosticData",
    "DependenceDiagnosticResult",
    "DependenceGraphSpec",
    "GraphDependenceDiagnostic",
    "GraphDependenceDiagnosticEstimator",
    "ensure_dependence_methods_registered",
    "register_dependence_methods",
]
