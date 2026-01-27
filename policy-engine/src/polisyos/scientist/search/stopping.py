from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass(frozen=True)
class StoppingCondition:
    """Result of a stopping criterion check."""

    should_stop: bool
    reason: str | None = None
    details: Dict[str, Any] = field(default_factory=dict)


class StoppingCriterion(ABC):
    """Abstract stopping criterion for search loops."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier for this criterion."""
        ...

    @abstractmethod
    def check(
        self,
        history: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> StoppingCondition:
        """
        Check if search should terminate.

        Args:
            history: List of past iteration records
            state: Current search state

        Returns:
            StoppingCondition with decision and reason
        """
        ...

    def reset(self) -> None:
        """Reset any internal state (e.g., timers)."""
        pass


class MaxIterations(StoppingCriterion):
    """Stop after a fixed number of iterations."""

    def __init__(self, max_iter: int):
        if max_iter < 1:
            raise ValueError("max_iter must be >= 1")
        self._max_iter = max_iter

    @property
    def name(self) -> str:
        return "max_iterations"

    def check(self, history: List[Dict[str, Any]], state: Dict[str, Any]) -> StoppingCondition:
        current = len(history)
        if current >= self._max_iter:
            return StoppingCondition(
                should_stop=True,
                reason=f"Maximum iterations ({self._max_iter}) reached",
                details={"iterations": current, "limit": self._max_iter},
            )
        return StoppingCondition(should_stop=False)


class MaxWallTime(StoppingCriterion):
    """Stop after elapsed wall time exceeds threshold."""

    def __init__(self, max_seconds: float):
        if max_seconds <= 0:
            raise ValueError("max_seconds must be > 0")
        self._max_seconds = max_seconds
        self._start_time: datetime | None = datetime.utcnow()

    @property
    def name(self) -> str:
        return "max_wall_time"

    def check(self, history: List[Dict[str, Any]], state: Dict[str, Any]) -> StoppingCondition:
        now = datetime.utcnow()

        if self._start_time is None:
            self._start_time = now

        elapsed = (now - self._start_time).total_seconds()

        if elapsed >= self._max_seconds:
            return StoppingCondition(
                should_stop=True,
                reason=f"Wall time limit ({self._max_seconds}s) exceeded",
                details={"elapsed_seconds": elapsed, "limit_seconds": self._max_seconds},
            )
        return StoppingCondition(
            should_stop=False,
            details={"elapsed_seconds": elapsed, "remaining_seconds": self._max_seconds - elapsed},
        )

    def reset(self) -> None:
        self._start_time = datetime.utcnow()


class ImprovementPlateau(StoppingCriterion):
    """Stop if no significant improvement for N consecutive iterations."""

    def __init__(
        self,
        patience: int = 3,
        min_improvement: float = 0.01,
        objective_key: str = "objective_value",
    ):
        if patience < 1:
            raise ValueError("patience must be >= 1")
        self._patience = patience
        self._min_improvement = min_improvement
        self._objective_key = objective_key

    @property
    def name(self) -> str:
        return "improvement_plateau"

    def check(self, history: List[Dict[str, Any]], state: Dict[str, Any]) -> StoppingCondition:
        if len(history) < self._patience + 1:
            return StoppingCondition(should_stop=False)

        values = [
            h.get(self._objective_key, float("inf"))
            for h in history
            if self._objective_key in h
        ]

        if len(values) < self._patience + 1:
            return StoppingCondition(should_stop=False)

        recent_values = values[-self._patience :]
        historical_values = values[: -self._patience]

        best_recent = min(recent_values)
        best_historical = min(historical_values)

        if abs(best_historical) < 1e-10:
            improvement = 0.0 if abs(best_recent) < 1e-10 else float("inf")
        else:
            improvement = (best_historical - best_recent) / abs(best_historical)

        if improvement < self._min_improvement:
            return StoppingCondition(
                should_stop=True,
                reason=(
                    f"No improvement above {self._min_improvement:.2%} "
                    f"for {self._patience} iterations"
                ),
                details={
                    "best_recent": best_recent,
                    "best_historical": best_historical,
                    "improvement": improvement,
                    "patience": self._patience,
                },
            )
        return StoppingCondition(should_stop=False)


class TargetAchieved(StoppingCriterion):
    """Stop when objective reaches a target value."""

    def __init__(
        self,
        target: float,
        objective_key: str = "objective_value",
    ):
        self._target = target
        self._objective_key = objective_key

    @property
    def name(self) -> str:
        return "target_achieved"

    def check(self, history: List[Dict[str, Any]], state: Dict[str, Any]) -> StoppingCondition:
        if not history:
            return StoppingCondition(should_stop=False)

        latest = history[-1].get(self._objective_key)
        if latest is not None and latest <= self._target:
            return StoppingCondition(
                should_stop=True,
                reason=f"Target objective ({self._target}) achieved",
                details={"achieved_value": latest, "target": self._target},
            )
        return StoppingCondition(should_stop=False)


class CompositeStoppingCriterion(StoppingCriterion):
    """Stop when ANY contained criterion triggers (OR logic)."""

    def __init__(self, criteria: List[StoppingCriterion]):
        if not criteria:
            raise ValueError("At least one criterion required")
        self._criteria = criteria

    @property
    def name(self) -> str:
        return "composite"

    def check(self, history: List[Dict[str, Any]], state: Dict[str, Any]) -> StoppingCondition:
        for criterion in self._criteria:
            result = criterion.check(history, state)
            if result.should_stop:
                return StoppingCondition(
                    should_stop=True,
                    reason=f"[{criterion.name}] {result.reason}",
                    details={"triggered_by": criterion.name, **result.details},
                )
        return StoppingCondition(should_stop=False)

    def reset(self) -> None:
        for criterion in self._criteria:
            criterion.reset()


# ─────────────────────────────────────────────────────────────────────────────
# Stopping Criterion Factory
# ─────────────────────────────────────────────────────────────────────────────


class StoppingPresets:
    """Pre-configured stopping criterion combinations."""

    @staticmethod
    def default(
        max_iter: int = 10,
        max_seconds: float = 300.0,
        patience: int = 3,
    ) -> CompositeStoppingCriterion:
        """Standard stopping: iterations OR time OR plateau."""
        return CompositeStoppingCriterion(
            [
                MaxIterations(max_iter),
                MaxWallTime(max_seconds),
                ImprovementPlateau(patience=patience),
            ]
        )

    @staticmethod
    def quick(max_iter: int = 5) -> MaxIterations:
        """Quick runs with fixed iteration count."""
        return MaxIterations(max_iter)

    @staticmethod
    def time_bounded(max_seconds: float) -> CompositeStoppingCriterion:
        """Time-bounded with safety iteration limit."""
        return CompositeStoppingCriterion(
            [
                MaxWallTime(max_seconds),
                MaxIterations(100),
            ]
        )
