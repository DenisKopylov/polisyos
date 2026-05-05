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
* **embedding_cosine** — converged when cosine similarity between consecutive
  text embeddings exceeds threshold
* **statistical_plateau** — converged when coefficient of variation in the
  metric window is below threshold
* **budget_projection** — converged when projected improvement over remaining
  budget is below threshold
* **multi_signal** — weighted combination of numeric, budget, and semantic signals
"""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common.logger import get_logger
from polisyos.core.errors import ErrorCategory
from polisyos.scientist.engine.error_semantics import emit_degraded_path
from polisyos.scientist.engine.errors import EngineError

if TYPE_CHECKING:
    from polisyos.scientist.engine.budget import BudgetState

__all__ = [
    "ConvergenceConfig",
    "ConvergenceDetector",
    "ConvergenceState",
    "ConvergenceStrategy",
]

logger = get_logger(__name__)


class ConvergenceValidationError(EngineError):
    """Raised when convergence configuration cannot be evaluated safely."""

    default_stage = "scientist.engine.convergence"
    default_category = ErrorCategory.VALIDATION


class ConvergenceStrategy(str, Enum):
    """Named stopping heuristics supported by the Scientist convergence detector."""

    ABSOLUTE_DELTA = "absolute_delta"
    RELATIVE_DELTA = "relative_delta"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    COMPOSITE = "composite"
    EMBEDDING_COSINE = "embedding_cosine"
    STATISTICAL_PLATEAU = "statistical_plateau"
    BUDGET_PROJECTION = "budget_projection"
    MULTI_SIGNAL = "multi_signal"


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
    signal_weights: dict[str, float] = Field(
        default_factory=lambda: {"numeric": 0.5, "budget": 0.3, "semantic": 0.2},
        description="Weights for MULTI_SIGNAL strategy sub-signals",
    )

    @model_validator(mode="after")
    def _validate_window(self) -> ConvergenceConfig:
        if self.min_iterations > self.max_iterations:
            raise ValueError("min_iterations must be <= max_iterations")
        if self.window_size > self.max_iterations:
            raise ValueError("window_size must be <= max_iterations")
        return self


class ConvergenceState(BaseModel):
    """Snapshot of convergence detection state after a check."""

    model_config = ConfigDict(extra="forbid")

    iteration: int = 0
    history: list[float] = Field(default_factory=list)
    converged: bool = False
    reason: str = ""


# ---------------------------------------------------------------------------
# Pure-Python cosine similarity (avoids numpy dependency)
# ---------------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    return dot / (norm_a * norm_b)


def _linear_regression_slope(values: list[float]) -> float:
    """Ordinary least-squares slope for a sequence indexed 0..n-1."""
    n = len(values)
    if n < 2:
        return 0.0
    sum_x = n * (n - 1) / 2.0
    sum_x2 = n * (n - 1) * (2 * n - 1) / 6.0
    sum_y = sum(values)
    sum_xy = sum(i * v for i, v in enumerate(values))
    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-12:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


class ConvergenceDetector:
    """Stateful convergence detector.

    Call :meth:`check` after each iteration with the current metric value.
    The returned :class:`ConvergenceState` indicates whether iteration should
    stop.

    For embedding-based strategies, use :meth:`check_with_text` which also
    accepts the raw text output for embedding comparison.
    """

    def __init__(
        self,
        config: ConvergenceConfig,
        budget_state: BudgetState | None = None,
        embedder: Any | None = None,
    ) -> None:
        self._config = config
        self._budget = budget_state
        self._embedder = embedder
        self._history: list[float] = []
        self._iteration = 0
        self._text_embeddings: list[list[float]] = []
        self._validate_budget_configuration()

    @property
    def config(self) -> ConvergenceConfig:
        return self._config

    def check(self, metric_value: float) -> ConvergenceState:
        """Record *metric_value* and check convergence.

        Returns a :class:`ConvergenceState` indicating whether iteration
        should stop (``converged=True``).
        """
        return self._do_check(metric_value)

    def check_with_text(
        self,
        metric_value: float,
        text: str | None = None,
    ) -> ConvergenceState:
        """Like :meth:`check` but also tracks text embeddings.

        When an *embedder* was provided at construction time and *text* is not
        ``None``, the text is embedded and stored for cosine-based convergence
        strategies.
        """
        if text is not None and self._embedder is not None:
            try:
                emb = self._embedder.embed([text])[0]
                self._text_embeddings.append(emb)
            except (AttributeError, IndexError, RuntimeError, TypeError, ValueError) as exc:
                emit_degraded_path(
                    component="engine.convergence",
                    operation="embed_text",
                    reason="text_embedding_unavailable",
                    exc=exc,
                    retryable=True,
                    details={"strategy": self._config.strategy.value},
                    log=logger,
                )
        return self._do_check(metric_value)

    def reset(self) -> None:
        """Reset detector state for reuse."""
        self._history.clear()
        self._text_embeddings.clear()
        self._iteration = 0

    def _validate_budget_configuration(self) -> None:
        if self._config.budget_key is None:
            return
        if self._budget is None:
            raise ConvergenceValidationError(
                "budget_key requires a budget_state",
                code="budget_state_required",
                details={"budget_key": self._config.budget_key},
            )
        limit = self._budget.limits.get(self._config.budget_key)
        if limit is None:
            raise ConvergenceValidationError(
                f"budget_key {self._config.budget_key!r} is not present in budget_state",
                code="budget_key_missing",
                details={"budget_key": self._config.budget_key},
            )
        if limit.max_usd <= 0:
            raise ConvergenceValidationError(
                f"budget_key {self._config.budget_key!r} must have a positive limit",
                code="budget_limit_non_positive",
                details={
                    "budget_key": self._config.budget_key,
                    "max_usd": str(limit.max_usd),
                },
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _do_check(self, metric_value: float) -> ConvergenceState:
        if not math.isfinite(metric_value):
            raise ConvergenceValidationError(
                "metric_value must be finite",
                code="metric_not_finite",
                details={"metric_value": str(metric_value)},
            )
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
        elif strategy == ConvergenceStrategy.EMBEDDING_COSINE:
            converged = self._check_embedding_cosine()
        elif strategy == ConvergenceStrategy.STATISTICAL_PLATEAU:
            converged = self._check_statistical_plateau()
        elif strategy == ConvergenceStrategy.BUDGET_PROJECTION:
            converged = self._check_budget_projection()
        elif strategy == ConvergenceStrategy.MULTI_SIGNAL:
            converged = self._check_multi_signal()
        else:
            converged = False

        reason = f"converged_{strategy.value}" if converged else ""
        return self._state(converged=converged, reason=reason)

    def _state(self, *, converged: bool, reason: str = "") -> ConvergenceState:
        return ConvergenceState(
            iteration=self._iteration,
            history=list(self._history),
            converged=converged,
            reason=reason,
        )

    # -- Classic strategies ------------------------------------------------

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

    # -- New strategies (Phase 6 WS6.2) ------------------------------------

    def _check_embedding_cosine(self) -> bool:
        """Converged when consecutive text embeddings have high similarity."""
        if len(self._text_embeddings) < 2:
            return False
        sim = _cosine_similarity(
            self._text_embeddings[-1],
            self._text_embeddings[-2],
        )
        return sim >= self._config.threshold

    def _check_statistical_plateau(self) -> bool:
        """Converged when the coefficient of variation in the window is small.

        Uses CV = std / |mean|.  When mean is near zero, falls back to an
        absolute std check.
        """
        window = self._history[-self._config.window_size :]
        n = len(window)
        if n < 2:
            return False
        mean = sum(window) / n
        variance = sum((x - mean) ** 2 for x in window) / n
        std = math.sqrt(variance)
        if abs(mean) < 1e-10:
            # Near-zero mean: converge when std itself is small
            return std < self._config.threshold
        cv = std / abs(mean)
        return cv < self._config.threshold

    def _check_budget_projection(self) -> bool:
        """Converged when projected remaining improvement is below threshold.

        Fits a simple linear regression on the metric history and extrapolates
        to estimate the total remaining improvement.
        """
        if len(self._history) < 3:
            return False
        slope = _linear_regression_slope(self._history)

        # Estimate remaining iterations from budget
        remaining_iters = self._config.max_iterations - self._iteration
        if self._budget is not None and self._config.budget_key is not None:
            remaining = self._budget.remaining(self._config.budget_key)
            if remaining is not None and self._iteration > 0:
                avg_cost = (
                    float(self._budget.spent.get(self._config.budget_key, 0)) / self._iteration
                )
                if avg_cost > 0:
                    remaining_iters = min(remaining_iters, int(float(remaining) / avg_cost))

        projected_improvement = abs(slope) * remaining_iters
        return projected_improvement < self._config.threshold

    def _check_multi_signal(self) -> bool:
        """Converged when weighted sum of sub-signals exceeds threshold.

        Sub-signals (each in [0, 1]):
        - ``numeric``: 1.0 if absolute_delta converged, else 0.0
        - ``budget``: budget_spent / budget_limit (higher = more pressure)
        - ``semantic``: latest embedding cosine similarity (0 if unavailable)
        """
        weights = self._config.signal_weights

        # Numeric signal
        numeric_signal = 1.0 if self._check_absolute_delta() else 0.0

        # Budget signal
        budget_signal = 0.0
        if self._budget is not None and self._config.budget_key is not None:
            remaining = self._budget.remaining(self._config.budget_key)
            limit = self._budget.limits.get(self._config.budget_key)
            if remaining is not None and limit is not None and float(limit.max_usd) > 0:
                budget_signal = 1.0 - float(remaining) / float(limit.max_usd)

        # Semantic signal
        semantic_signal = 0.0
        if len(self._text_embeddings) >= 2:
            semantic_signal = max(
                0.0,
                _cosine_similarity(
                    self._text_embeddings[-1],
                    self._text_embeddings[-2],
                ),
            )

        total = (
            weights.get("numeric", 0.5) * numeric_signal
            + weights.get("budget", 0.3) * budget_signal
            + weights.get("semantic", 0.2) * semantic_signal
        )
        return total >= self._config.threshold
