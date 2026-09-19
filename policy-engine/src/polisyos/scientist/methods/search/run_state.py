"""Per-run state ownership for the legacy search controller."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GenerationTransition(str, Enum):
    """Typed transitions emitted by the candidate-generation boundary."""

    TRANSIENT_EMPTY = "transient_empty"
    EXHAUSTED = "exhausted"


class _EvaluationDisposition(str, Enum):
    """Classify one evaluated candidate at the run-state boundary."""

    ORDINARY = "ordinary"
    SENTINEL = "sentinel"


@dataclass(frozen=True)
class _EvaluationTransition:
    """Carry one internal candidate disposition and its detached history record."""

    disposition: _EvaluationDisposition
    record: Any


@dataclass
class SearchRunState:
    """Mutable state owned by exactly one controller run."""

    search_id: str = ""
    status: Enum | None = None
    history: list[Any] = field(default_factory=list)
    best_candidate: dict[str, Any] | None = None
    best_objective: float = float("inf")
    pareto_front: list[dict[str, Any]] = field(default_factory=list)
    pareto_points: list[Any] = field(default_factory=list)
    stage_a_evaluations: int = 0
    stage_b_evaluations: int = 0
    sentinel_evaluations: int = 0
    generation_attempts: int = 0
    empty_generation_attempts: int = 0
    evaluation_iterations: int = 0
    budget_spent: float = 0.0
    generation_transition: GenerationTransition | None = None

    def generation_transition_payload(self) -> dict[str, Any] | None:
        """Return a detached, typed transition payload for a public result."""
        if self.generation_transition is None:
            return None
        return {
            "kind": self.generation_transition.value,
            "generation_attempts": self.generation_attempts,
            "evaluation_iterations": self.evaluation_iterations,
            "budget_spent": self.budget_spent,
        }

    def apply_evaluation_transition(self, transition: _EvaluationTransition) -> None:
        """Apply one candidate disposition to the sole run-state owner.

        Sentinel evaluations remain observable through their dedicated count but
        do not consume an ordinary evaluation iteration or enter ordinary
        history. Every ordinary transition updates both values together.
        """
        if transition.disposition is _EvaluationDisposition.SENTINEL:
            self.sentinel_evaluations += 1
            return
        self.history.append(transition.record)
        self.evaluation_iterations += 1

    def snapshot(self) -> SearchRunState:
        """Return a deep snapshot that cannot be changed by a later run."""
        return deepcopy(self)


__all__ = ["GenerationTransition", "SearchRunState"]
