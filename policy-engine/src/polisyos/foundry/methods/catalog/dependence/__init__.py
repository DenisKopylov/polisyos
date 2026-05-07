"""Expose dependence diagnostics and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.extensions.registry import bootstrap_builtin_foundry_method_family
from polisyos.foundry.methods.selection.registry import MethodRegistry

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
    bootstrap_builtin_foundry_method_family("dependence", registry)


__all__ = [
    "DependenceDiagnosticData",
    "DependenceDiagnosticResult",
    "DependenceGraphSpec",
    "GraphDependenceDiagnostic",
    "GraphDependenceDiagnosticEstimator",
    "ensure_dependence_methods_registered",
    "register_dependence_methods",
]
