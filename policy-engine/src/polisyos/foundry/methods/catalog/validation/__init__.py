"""Expose validation methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.extensions.registry import bootstrap_builtin_foundry_method_family
from polisyos.foundry.methods.selection.registry import MethodRegistry

from ._registry_boot import register_validation_methods
from .diagnostics import (
    CalibrationDiagnosticEstimator,
    CrossValidationEstimator,
    WalkForwardEstimator,
)
from .scoring import ProbabilisticScoringEstimator


def ensure_validation_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with validation methods for backtests and diagnostics."""
    bootstrap_builtin_foundry_method_family("validation", registry)


__all__ = [
    "CalibrationDiagnosticEstimator",
    "CrossValidationEstimator",
    "ProbabilisticScoringEstimator",
    "WalkForwardEstimator",
    "ensure_validation_methods_registered",
    "register_validation_methods",
]
