"""Per-run state ownership for the legacy search controller."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from polisyos.scientist.methods.search.contracts import ParetoViewProjection


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
    training_evaluations: int = 0
    budget_spent: float = 0.0
    budget_available: bool = False
    budget_snapshot: dict[str, float] = field(default_factory=dict)
    budget_snapshot_source: str = "unavailable"
    budget_ledger_id: str | None = None
    budget_ledger_revision: int | None = None
    policy_evaluation_errors: int = 0
    generation_transition: GenerationTransition | None = None
    pareto_projection: ParetoViewProjection | None = None

    @property
    def history_size(self) -> int:
        """Return the number of records available to surrogate consumers."""
        return len(self.history)

    @property
    def new_evaluations(self) -> int:
        """Return ordinary evaluations from the current run.

        Warm-start records and sentinel checks are intentionally not part of
        this stopping counter.  The existing ``evaluation_iterations`` field
        remains the source of truth so a second mutable ledger is not created.
        """
        return self.evaluation_iterations

    @property
    def evaluation_count(self) -> int:
        """Return every Stage B evaluation, including sentinels."""
        return self.stage_b_evaluations

    @property
    def scientific_evaluations(self) -> int:
        """Return non-sentinel Stage B evaluations used by the search signal."""
        return max(0, self.stage_b_evaluations - self.sentinel_evaluations)

    def generation_transition_payload(self) -> dict[str, Any] | None:
        """Return a detached, typed transition payload for a public result."""
        if self.generation_transition is None:
            return None
        return {
            "kind": self.generation_transition.value,
            "generation_attempts": self.generation_attempts,
            "evaluation_iterations": self.evaluation_iterations,
            "budget_spent": self.budget_spent,
            "budget_available": self.budget_available,
            "history_size": self.history_size,
            "training_evaluations": self.training_evaluations,
            "new_evaluations": self.new_evaluations,
            "evaluation_count": self.evaluation_count,
            "scientific_evaluations": self.scientific_evaluations,
            "sentinel_evaluations": self.sentinel_evaluations,
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

    def apply_tell_transition(
        self,
        transition: _EvaluationTransition,
        *,
        stage_a_evaluated: bool,
        stage_b_evaluated: bool = True,
    ) -> None:
        """Apply one externally evaluated candidate through this state owner.

        Ask/tell adapters report evaluator feedback without invoking the
        controller's full loop.  Stage A rejection is a valid terminal path
        for the candidate and therefore must not be counted as a Stage B
        evaluation.  Counters and history still enter through the same
        transition owner used by ``SearchController.run``; adapters must not
        maintain a second mutable ledger.
        """
        if stage_a_evaluated:
            self.stage_a_evaluations += 1
        if stage_b_evaluated:
            self.stage_b_evaluations += 1
        self.apply_evaluation_transition(transition)

    def snapshot(self) -> SearchRunState:
        """Return a deep snapshot that cannot be changed by a later run."""
        return deepcopy(self)


__all__ = ["GenerationTransition", "SearchRunState"]
