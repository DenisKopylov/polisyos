"""Public dependence registry boot module API."""
from __future__ import annotations

from typing import Sequence

from .diagnostics import GraphDependenceDiagnosticEstimator


def register_dependence_methods() -> Sequence[type]:
    """Register shared dependence diagnostics."""
    return (GraphDependenceDiagnosticEstimator,)


__all__ = ["register_dependence_methods"]
