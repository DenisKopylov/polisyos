"""Adapters between existing CompositeObjective and strategy objective interfaces."""

from __future__ import annotations

from typing import Any

from polisyos.scientist.search.objective import (
    CompositeObjective,
    ObjectiveValue,
    OptimizationDirection,
)


def extract_objectives_from_results(
    results: dict[str, Any],
    composite: CompositeObjective,
) -> list[ObjectiveValue]:
    """Evaluate detailed objective values using existing composite objective."""
    return composite.evaluate_detailed(results)


def objectives_to_directions(composite: CompositeObjective) -> list[OptimizationDirection]:
    """Extract optimization direction for each objective."""
    return [objective.direction for objective in composite.objectives]


def objectives_to_names(composite: CompositeObjective) -> list[str]:
    """Extract objective names in model order."""
    return [objective.name for objective in composite.objectives]

