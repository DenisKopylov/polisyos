"""Public feedback-solver helpers for fixed-point execution mode."""

from __future__ import annotations

from .config import (
    PreparedFeedbackConfig,
    prepare_feedback_config,
    project_bounds,
    snapshot_from_vector,
)
from .fixed_point import AlternativeSolution, MapEvaluation, SolveOutcome, solve_fixed_point
from .jacobian import JacobianSummary
from .multiplicity import MultiplicityExplorer, discover_equilibria

__all__ = [
    "AlternativeSolution",
    "JacobianSummary",
    "MapEvaluation",
    "MultiplicityExplorer",
    "PreparedFeedbackConfig",
    "SolveOutcome",
    "prepare_feedback_config",
    "project_bounds",
    "discover_equilibria",
    "snapshot_from_vector",
    "solve_fixed_point",
]
