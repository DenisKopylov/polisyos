"""Flattened facade for dependence methods catalog."""

from polisyos.foundry.methods.catalog.dependence import (
    DependenceDiagnosticData,
    DependenceDiagnosticResult,
    DependenceGraphSpec,
    GraphDependenceDiagnostic,
    GraphDependenceDiagnosticEstimator,
    ensure_dependence_methods_registered,
    register_dependence_methods,
)

__all__ = (
    "DependenceDiagnosticData",
    "DependenceDiagnosticResult",
    "DependenceGraphSpec",
    "GraphDependenceDiagnostic",
    "GraphDependenceDiagnosticEstimator",
    "ensure_dependence_methods_registered",
    "register_dependence_methods",
)
