"""Adaptive iteration with convergence detection.

Provides a :class:`ConvergenceDetector` that tracks a scalar metric across
iterations and determines when to stop. Integrates optionally with
:class:`BudgetState` for budget-aware early termination.

Strategies:

* **absolute_delta** — converged when ``|v[-1] - v[-2]| < threshold``
* **relative_delta** — converged when ``|v[-1] - v[-2]| / |v[-2]| < threshold``
* **semantic_similarity** — converged when ``v > threshold`` (value *is* the
  similarity score)
* **composite** — converged when **all** sub-checks pass (absolute + relative)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from polisyos.scientist.engine.budget import BudgetState

__all__ = [
    "ConvergenceConfig",
    "ConvergenceDetector",
    "ConvergenceState",
    "ConvergenceStrategy",
]


class ConvergenceStrategy(str, Enum):
    ABSOLUTE_DELTA = "absolute_delta"
    RELATIVE_DELTA = "relative_delta"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    COMPOSITE = "composite"


class ConvergenceConfig(BaseModel):
    """Configuration for convergence detection."""

    model_config = ConfigDict(extra="forbid")

    strategy: ConvergenceStrategy = ConvergenceStrategy.ABSOLUTE_DELTA
    threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    min_iterations: int = Field(default=2, ge=1, le=50)
    max_iterations: int = Field(default=10, ge=1, le=50)
    window_size: int = Field(default=2, ge=2, le=10)
    budget_key: str | None = Field(
        default=None,
        description="If set, early-stop when remaining budget is low",
    )
    budget_headroom_ratio: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Stop when remaining budget < headroom_ratio * limit",
    )


class ConvergenceState(BaseModel):
    """Snapshot of convergence detection state after a check."""

    model_config = ConfigDict(extra="forbid")

    iteration: int = 0
    history: list[float] = Field(default_factory=list)
    converged: bool = False
    reason: str = ""


class ConvergenceDetector:
    """Stateful convergence detector.

    Call :meth:`check` after each iteration with the current metric value.
    The returned :class:`ConvergenceState` indicates whether iteration should
    stop.
    """

    def __init__(
        self,
        config: ConvergenceConfig,
        budget_state: "BudgetState | None" = None,
    ) -> None:
        self._config = config
        self._budget = budget_state
        self._history: list[float] = []
        self._iteration = 0

    @property
    def config(self) -> ConvergenceConfig:
        return self._config

    def check(self, metric_value: float) -> ConvergenceState:
        """Record *metric_value* and check convergence.

        Returns a :class:`ConvergenceState` indicating whether iteration
        should stop (``converged=True``).
        """
        self._iteration += 1
        self._history.append(metric_value)

        # Max iterations hard stop
        if self._iteration >= self._config.max_iterations:
            return self._state(converged=True, reason="max_iterations")

        # Budget pressure check
        if self._budget is not None and self._config.budget_key is not None:
            remaining = self._budget.remaining(self._config.budget_key)
            if remaining is not None and remaining >= 0:
                limit_key = f"{self._config.budget_key}"
                limit = self._budget.limits.get(limit_key)
                if limit is not None:
                    headroom = float(limit.max_usd) * self._config.budget_headroom_ratio
                    if float(remaining) < headroom:
                        return self._state(converged=True, reason="budget_pressure")

        # Minimum iterations guard
        if self._iteration < self._config.min_iterations:
            return self._state(converged=False)

        # Not enough history for window comparison
        if len(self._history) < self._config.window_size:
            return self._state(converged=False)

        # Strategy evaluation
        strategy = self._config.strategy
        if strategy == ConvergenceStrategy.ABSOLUTE_DELTA:
            converged = self._check_absolute_delta()
        elif strategy == ConvergenceStrategy.RELATIVE_DELTA:
            converged = self._check_relative_delta()
        elif strategy == ConvergenceStrategy.SEMANTIC_SIMILARITY:
            converged = self._check_semantic_similarity()
        elif strategy == ConvergenceStrategy.COMPOSITE:
            converged = self._check_absolute_delta() and self._check_relative_delta()
        else:
            converged = False

        reason = f"converged_{strategy.value}" if converged else ""
        return self._state(converged=converged, reason=reason)

    def reset(self) -> None:
        """Reset detector state for reuse."""
        self._history.clear()
        self._iteration = 0

    def _state(self, *, converged: bool, reason: str = "") -> ConvergenceState:
        return ConvergenceState(
            iteration=self._iteration,
            history=list(self._history),
            converged=converged,
            reason=reason,
        )

    def _check_absolute_delta(self) -> bool:
        window = self._history[-self._config.window_size :]
        for i in range(1, len(window)):
            if abs(window[i] - window[i - 1]) >= self._config.threshold:
                return False
        return True

    def _check_relative_delta(self) -> bool:
        window = self._history[-self._config.window_size :]
        for i in range(1, len(window)):
            denom = abs(window[i - 1])
            if denom < 1e-10:
                # Near-zero base: fall back to absolute check
                if abs(window[i] - window[i - 1]) >= self._config.threshold:
                    return False
            else:
                if abs(window[i] - window[i - 1]) / denom >= self._config.threshold:
                    return False
        return True

    def _check_semantic_similarity(self) -> bool:
        # For semantic similarity, the metric value IS the similarity.
        # Converged when latest value exceeds threshold.
        return self._history[-1] >= self._config.threshold
