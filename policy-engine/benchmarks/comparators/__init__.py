"""Comparator scaffolding for PolicyOS benchmark acceptance runs."""

from __future__ import annotations

from .execution import execute_comparator_suite
from .forestdr import ForestDRLearnerComparator
from .stack import (
    COMPARATOR_GROUPS,
    REQUIRED_ACCEPTANCE_COMPARATORS,
    all_comparator_distribution_names,
    build_research_acceptance_comparator_status,
    comparator_degraded_reasons,
    comparator_distribution_names,
    comparator_labels_for_group,
    comparator_required_modules,
)

__all__ = [
    "COMPARATOR_GROUPS",
    "ForestDRLearnerComparator",
    "REQUIRED_ACCEPTANCE_COMPARATORS",
    "execute_comparator_suite",
    "all_comparator_distribution_names",
    "build_research_acceptance_comparator_status",
    "comparator_labels_for_group",
    "comparator_degraded_reasons",
    "comparator_distribution_names",
    "comparator_required_modules",
]
