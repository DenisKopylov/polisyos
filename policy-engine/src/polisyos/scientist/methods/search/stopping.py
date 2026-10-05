"""Public search stopping module API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class StoppingCondition:
    """Result of a stopping criterion check."""

    should_stop: bool
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


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
        history: list[dict[str, Any]],
        state: dict[str, Any],
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

    def state_keys(self) -> tuple[str, ...]:
        """Return externally-owned state keys required by this criterion."""
        return ()


class MaxIterations(StoppingCriterion):
    """Stop after a fixed number of iterations."""

    def __init__(self, max_iter: int):
        if max_iter < 1:
            raise ValueError("max_iter must be >= 1")
        self._max_iter = max_iter

    @property
    def name(self) -> str:
        return "max_iterations"

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> StoppingCondition:
        current = int(state.get("evaluation_iterations", len(history)))
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
        self._start_time: datetime | None = datetime.now(UTC)

    @property
    def name(self) -> str:
        return "max_wall_time"

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> StoppingCondition:
        now = datetime.now(UTC)

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
        self._start_time = datetime.now(UTC)


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
        if not isfinite(min_improvement):
            raise ValueError("min_improvement must be finite")
        self._patience = patience
        self._min_improvement = min_improvement
        self._objective_key = objective_key

    @property
    def name(self) -> str:
        return "improvement_plateau"

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> StoppingCondition:
        if len(history) < self._patience + 1:
            return StoppingCondition(should_stop=False)

        values = [
            h.get(self._objective_key, float("inf")) for h in history if self._objective_key in h
        ]

        if len(values) < self._patience + 1:
            return StoppingCondition(should_stop=False)
        invalid_indices = [index for index, value in enumerate(values) if not isfinite(value)]
        if invalid_indices:
            return StoppingCondition(
                should_stop=False,
                reason="Improvement plateau unavailable: non-finite objective history",
                details={
                    "predicate_basis": "not_established",
                    "limitation": "non_finite_objective_history",
                    "objective_key": self._objective_key,
                    "invalid_indices": invalid_indices,
                },
            )

        recent_values = values[-self._patience :]
        historical_values = values[: -self._patience]

        best_recent = min(recent_values)
        best_historical = min(historical_values)
        signed_improvement = best_historical - best_recent

        if abs(best_historical) < 1e-10:
            # A zero baseline has no meaningful relative denominator.  Keep
            # the signed gain in the objective's absolute scale so a positive
            # loss remains a regression instead of becoming infinite progress.
            improvement = signed_improvement
        else:
            improvement = signed_improvement / abs(best_historical)

        if not isfinite(improvement):
            return StoppingCondition(
                should_stop=False,
                reason="Improvement plateau unavailable: non-finite derived improvement",
                details={
                    "predicate_basis": "not_established",
                    "limitation": "non_finite_derived_improvement",
                    "objective_key": self._objective_key,
                },
            )

        if improvement < self._min_improvement:
            return StoppingCondition(
                should_stop=True,
                reason=(
                    f"Improvement plateau: no improvement above {self._min_improvement:.2%} "
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

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> StoppingCondition:
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


class CostBudgetStopping(StoppingCriterion):
    """Stop when cumulative cost exceeds a USD budget."""

    def __init__(
        self,
        max_cost_usd: float,
        cost_key: str = "cumulative_cost_usd",
    ):
        if max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be > 0")
        self._max_cost = max_cost_usd
        self._cost_key = cost_key

    @property
    def name(self) -> str:
        return "cost_budget"

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> StoppingCondition:
        del history
        raw_cost = state.get(self._cost_key)
        if not isinstance(raw_cost, (int, float, Decimal)) or isinstance(raw_cost, bool):
            return StoppingCondition(
                should_stop=True,
                reason=f"Cost budget unavailable for key {self._cost_key!r}",
                details={
                    "budget": self._max_cost,
                    "cost_key": self._cost_key,
                    "budget_available": False,
                },
            )
        cost = float(raw_cost)
        if not isfinite(cost):
            return StoppingCondition(
                should_stop=True,
                reason=f"Cost budget unavailable for key {self._cost_key!r}",
                details={
                    "budget": self._max_cost,
                    "cost": raw_cost,
                    "cost_key": self._cost_key,
                    "budget_available": False,
                },
            )
        if cost >= self._max_cost:
            return StoppingCondition(
                should_stop=True,
                reason=f"Cost budget ({self._max_cost} USD) exhausted",
                details={
                    "cost": cost,
                    "budget": self._max_cost,
                    "cost_key": self._cost_key,
                    "budget_available": True,
                },
            )
        return StoppingCondition(
            should_stop=False,
            details={
                "cost": cost,
                "budget": self._max_cost,
                "cost_key": self._cost_key,
                "budget_available": True,
            },
        )

    def state_keys(self) -> tuple[str, ...]:
        """Return the exact budget key this criterion reads."""
        return (self._cost_key,)


class CompositeStoppingCriterion(StoppingCriterion):
    """Stop when ANY contained criterion triggers (OR logic)."""

    def __init__(self, criteria: list[StoppingCriterion]):
        if not criteria:
            raise ValueError("At least one criterion required")
        self._criteria = criteria

    @property
    def name(self) -> str:
        return "composite"

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> StoppingCondition:
        limitations = []
        for criterion in self._criteria:
            result = criterion.check(history, state)
            limitations.extend(_stopping_limitations(criterion.name, result))
            if result.should_stop:
                return StoppingCondition(
                    should_stop=True,
                    reason=f"[{criterion.name}] {result.reason}",
                    details={
                        "triggered_by": criterion.name,
                        **result.details,
                        "limitations": limitations,
                    },
                )
        return StoppingCondition(
            should_stop=False, details={"limitations": limitations} if limitations else {}
        )

    def reset(self) -> None:
        for criterion in self._criteria:
            criterion.reset()

    def state_keys(self) -> tuple[str, ...]:
        """Return the de-duplicated state keys required by child criteria."""
        return tuple(
            dict.fromkeys(key for criterion in self._criteria for key in criterion.state_keys())
        )


class AllStoppingCriteria(StoppingCriterion):
    """Stop only when ALL contained criteria trigger (AND logic)."""

    def __init__(self, criteria: list[StoppingCriterion]):
        if not criteria:
            raise ValueError("At least one criterion required")
        self._criteria = criteria

    @property
    def name(self) -> str:
        return "all_composite"

    def check(self, history: list[dict[str, Any]], state: dict[str, Any]) -> StoppingCondition:
        results = [c.check(history, state) for c in self._criteria]
        limitations = [
            limitation
            for criterion, result in zip(self._criteria, results, strict=True)
            for limitation in _stopping_limitations(criterion.name, result)
        ]
        if all(r.should_stop for r in results):
            reasons = [r.reason for r in results if r.reason]
            return StoppingCondition(
                should_stop=True,
                reason=" AND ".join(reasons),
                details={
                    "triggered_by": [c.name for c in self._criteria],
                    "limitations": limitations,
                },
            )
        return StoppingCondition(
            should_stop=False, details={"limitations": limitations} if limitations else {}
        )

    def reset(self) -> None:
        for criterion in self._criteria:
            criterion.reset()

    def state_keys(self) -> tuple[str, ...]:
        """Return the de-duplicated state keys required by child criteria."""
        return tuple(
            dict.fromkeys(key for criterion in self._criteria for key in criterion.state_keys())
        )


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

    @staticmethod
    def cost_bounded(
        max_cost_usd: float,
        max_iter: int = 100,
        cost_key: str = "cumulative_cost_usd",
    ) -> CompositeStoppingCriterion:
        """Cost-bounded with safety iteration limit."""
        return CompositeStoppingCriterion(
            [
                CostBudgetStopping(max_cost_usd, cost_key=cost_key),
                MaxIterations(max_iter),
            ]
        )


def _stopping_limitations(name: str, result: StoppingCondition) -> list[dict[str, Any]]:
    """Carry only declared unavailable predicates through criterion composition."""
    limitations = list(result.details.get("limitations", []))
    if result.details.get("predicate_basis") == "not_established":
        limitations.append({"criterion": name, "reason": result.reason, "details": result.details})
    return limitations
