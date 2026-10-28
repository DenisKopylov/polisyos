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
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.common.logger import get_logger
from polisyos.core.errors import ErrorCategory
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.errors import EngineError

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.budget import BudgetState

__all__ = [
    "ConvergenceConfig",
    "ConvergenceDetector",
    "ConvergenceState",
    "ConvergenceObservation",
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
        # A resource ceiling may be reached before a comparison window exists.
        # That is a resource stop, never evidence of convergence.
        return self


class ConvergenceObservation(BaseModel):
    """Content-bound candidate self-assessment observed on one actual LLM call.

    This records what the producer observed, not scientific validity or authority.
    Public round-tripped data does not make an old response a new observation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["scientist.convergence.observation.v1"] = (
        "scientist.convergence.observation.v1"
    )
    kind: Literal["llm_candidate_confidence"] = "llm_candidate_confidence"
    authority: Literal["candidate"] = "candidate"
    value_derivation: Literal["producer_self_assessment", "candidate_after_checks"] = (
        "producer_self_assessment"
    )
    subject_ref: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_ref: str = Field(pattern=r"^[a-f0-9]{64}$")
    producer_request_ref: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_ref: str = Field(pattern=r"^[a-f0-9]{64}$")
    producer_response_ref: str = Field(pattern=r"^[a-f0-9]{64}$")
    response_binding_status: Literal["same_bytes", "not_established"] = "same_bytes"
    producer_event_id: str = Field(min_length=1)
    producer_kind: Literal["provider", "reuse"] = "provider"
    model_ref: str = Field(min_length=1)
    model_version: str | None = None
    pass_number: int = Field(ge=1, strict=True)
    value: float = Field(ge=0.0, le=1.0, allow_inf_nan=False, strict=True)

    @field_validator("producer_event_id", "model_ref", "model_version")
    @classmethod
    def _nonblank_identity(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("observation identity must be nonblank and normalized")
        return value

    @model_validator(mode="after")
    def _response_byte_layer_binding(self) -> ConvergenceObservation:
        """Recompute byte equality; differing hashes do not prove restoration."""
        if (self.response_binding_status == "same_bytes") != (
            self.source_ref == self.producer_response_ref
        ):
            raise ValueError("candidate_response_byte_layer_binding_mismatch")
        return self


class ConvergenceState(BaseModel):
    """Current observation and iteration-stop snapshot.

    ``converged`` retains the legacy terminal flag for existing readers. New
    consumers use ``should_stop`` and ``stop_kind``; neither a resource ceiling
    nor an LLM self-assessment is scientific convergence.
    """

    model_config = ConfigDict(extra="forbid")

    iteration: int = 0
    history: list[float] = Field(default_factory=list)
    converged: bool = False
    reason: str = ""
    should_stop: bool = False
    stop_kind: Literal["none", "resource_limit", "heuristic_stability"] = "none"
    signal_kind: Literal["legacy_numeric", "llm_candidate_confidence", "text_embedding"] = (
        "legacy_numeric"
    )
    scientific_converged: Literal[False] = False
    observation_status: str = "not_checked"
    last_checked_observation: ConvergenceObservation | None = None
    profile: ConvergenceConfig | None = None
    raw_embedding_similarity: float | None = None
    embedding_identity_status: Literal[
        "not_applicable", "current_compatible", "not_established"
    ] = "not_applicable"


@dataclass(frozen=True, slots=True)
class _EmbeddingRecord:
    """Internal embedding observation bound to its measurement provenance."""

    iteration: int
    input_ref: str
    model_ref: str
    model_version: str
    dimension: int
    vector: tuple[float, ...]


# ---------------------------------------------------------------------------
# Pure-Python cosine similarity (avoids numpy dependency)
# ---------------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0
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
        self._config = config.model_copy(deep=True)
        self._budget = budget_state
        self._embedder = embedder
        self._history: list[float] = []
        self._iteration = 0
        self._text_embeddings: list[_EmbeddingRecord] = []
        self._signal_kind = "legacy_numeric"
        self._observation_status = "not_checked"
        self._last_checked_observation: ConvergenceObservation | None = None
        self._last_candidate_observation: ConvergenceObservation | None = None
        self._seen_observation_ids: set[str] = set()
        self._current_signal_admitted = True
        self._validate_budget_configuration()

    @property
    def config(self) -> ConvergenceConfig:
        """Return a detached profile so an observer cannot rewrite an active run."""
        return self._config.model_copy(deep=True)

    def check(self, metric_value: float) -> ConvergenceState:
        """Record *metric_value* and check convergence.

        Returns a :class:`ConvergenceState` indicating whether iteration
        should stop (``converged=True``).
        """
        if self._signal_kind != "legacy_numeric":
            self._history.clear()
            self._last_candidate_observation = None
        self._signal_kind = "legacy_numeric"
        self._observation_status = "legacy_numeric_unbound"
        self._current_signal_admitted = True
        return self._do_check(metric_value)

    def check_candidate_observation(
        self,
        observation: ConvergenceObservation | None,
        *,
        subject_ref: str | None,
        request_ref: str | None,
        source_text: str | None,
        value: float | None,
        pass_number: int,
        unavailable_reason: str = "current_observation_unavailable",
    ) -> ConvergenceState:
        """Consume the current producer observation, never a retained prior scalar.

        All expected values come from the actual executed caller/parser context.
        The source digest is recomputed from the raw response and fresh event IDs
        are single-use. Model versions absent from the producer remain unknown.
        Candidate stability may bound optional iteration; it grants no authority.
        """
        self._iteration += 1
        self._signal_kind = "llm_candidate_confidence"
        self._current_signal_admitted = False
        reason = unavailable_reason
        if type(observation) is ConvergenceObservation:
            if (
                subject_ref is None
                or observation.subject_ref != subject_ref
                or observation.request_ref != request_ref
                or observation.pass_number != pass_number
                or not isinstance(source_text, str)
                or observation.source_ref != sha256(source_text.encode("utf-8")).hexdigest()
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or observation.value != value
            ):
                reason = "current_observation_binding_mismatch"
            elif observation.producer_kind != "provider":
                reason = "reused_response_is_not_a_fresh_observation"
            elif observation.producer_event_id in self._seen_observation_ids:
                reason = "observation_event_replayed"
            else:
                self._seen_observation_ids.add(observation.producer_event_id)
                self._last_checked_observation = observation
                previous = self._last_candidate_observation
                same_basis = previous is not None and (
                    previous.subject_ref,
                    previous.model_ref,
                    previous.model_version,
                    previous.pass_number + 1,
                ) == (
                    observation.subject_ref,
                    observation.model_ref,
                    observation.model_version,
                    observation.pass_number,
                )
                if not same_basis:
                    self._history.clear()
                self._last_candidate_observation = observation
                if observation.response_binding_status != "same_bytes":
                    reason = "producer_consumer_response_relation_not_established"
                elif observation.model_version is None:
                    reason = "model_version_not_established"
                elif self._config.strategy in {
                    ConvergenceStrategy.SEMANTIC_SIMILARITY,
                    ConvergenceStrategy.EMBEDDING_COSINE,
                    ConvergenceStrategy.MULTI_SIGNAL,
                }:
                    reason = "candidate_confidence_is_not_semantic_similarity"
                else:
                    self._history.append(observation.value)
                    self._current_signal_admitted = True
                    self._observation_status = "current_candidate_observation"
                    return self._evaluate_current_state()
        self._history.clear()
        self._last_candidate_observation = None
        self._observation_status = reason
        return self._evaluate_current_state()

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
        self._signal_kind = "text_embedding"
        self._observation_status = "embedding_not_established"
        self._current_signal_admitted = True
        if text is not None and self._embedder is not None:
            try:
                model_ref, model_version = self._embedding_provenance()
                emb = self._embedder.embed([text])[0]
                vector = tuple(float(value) for value in emb)
                self._text_embeddings.append(
                    _EmbeddingRecord(
                        iteration=self._iteration + 1,
                        input_ref=sha256(text.encode("utf-8")).hexdigest(),
                        model_ref=model_ref,
                        model_version=model_version,
                        dimension=len(vector),
                        vector=vector,
                    )
                )
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
        self._last_checked_observation = None
        self._last_candidate_observation = None
        self._seen_observation_ids.clear()
        self._observation_status = "not_checked"
        self._current_signal_admitted = True

    def _embedding_provenance(self) -> tuple[str, str]:
        """Return stable model and version references for the current embedder."""
        embedder = self._embedder
        model_ref = getattr(embedder, "model_id", None)
        if model_ref is None:
            model_ref = getattr(embedder, "model_name", None)
        if model_ref is None:
            # A Python class does not identify model weights or execution version.
            model_ref = ""

        model_version = getattr(embedder, "model_version", None)
        if model_version is None:
            model_version = getattr(embedder, "version", None)

        return str(model_ref), "" if model_version is None else str(model_version)

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
        if not limit.max_usd.is_finite() or limit.max_usd <= 0:
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

        return self._evaluate_current_state()

    def _resource_stop_reason(self) -> str | None:
        if self._iteration >= self._config.max_iterations:
            return "max_iterations"
        if self._budget is not None and self._config.budget_key is not None:
            remaining = self._budget.remaining(self._config.budget_key)
            limit = self._budget.limits.get(self._config.budget_key)
            if remaining is not None and limit is not None:
                if not remaining.is_finite():
                    raise ConvergenceValidationError(
                        "remaining budget must be finite", code="budget_remaining_invalid"
                    )
                headroom = float(limit.max_usd) * self._config.budget_headroom_ratio
                if remaining <= 0 or float(remaining) < headroom:
                    return "budget_pressure"
        return None

    def _evaluate_current_state(self) -> ConvergenceState:
        resource_reason = self._resource_stop_reason()
        if resource_reason is not None:
            return self._state(converged=True, reason=resource_reason)
        if not self._current_signal_admitted:
            return self._state(converged=False, reason=self._observation_status)

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
            should_stop=converged,
            stop_kind=(
                "resource_limit"
                if converged and reason in {"max_iterations", "budget_pressure"}
                else "heuristic_stability"
                if converged
                else "none"
            ),
            signal_kind=self._signal_kind,
            observation_status=self._observation_status,
            last_checked_observation=self._last_checked_observation,
            profile=self._config.model_copy(deep=True),
            raw_embedding_similarity=self._raw_embedding_similarity(),
            embedding_identity_status=(
                "current_compatible"
                if self._current_embedding_pair() is not None
                else "not_established"
                if self._signal_kind == "text_embedding"
                else "not_applicable"
            ),
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
        pair = self._current_embedding_pair()
        if pair is None:
            return False
        previous, current = pair
        sim = _cosine_similarity(
            list(current.vector),
            list(previous.vector),
        )
        return sim >= self._config.threshold

    def _current_embedding_pair(self) -> tuple[_EmbeddingRecord, _EmbeddingRecord] | None:
        """Return the latest compatible pair or ``None`` when it is stale."""
        if len(self._text_embeddings) < 2:
            return None
        previous, current = self._text_embeddings[-2:]
        if current.iteration != self._iteration or previous.iteration != self._iteration - 1:
            return None
        if (
            not previous.input_ref
            or not current.input_ref
            or not previous.model_ref
            or not current.model_ref
            or not previous.model_version
            or not current.model_version
            or not previous.vector
            or any(not math.isfinite(value) for value in (*previous.vector, *current.vector))
            or not any(value != 0.0 for value in previous.vector)
            or not any(value != 0.0 for value in current.vector)
        ):
            return None
        if (previous.model_ref, previous.model_version) != (
            current.model_ref,
            current.model_version,
        ):
            return None
        if previous.dimension != current.dimension:
            return None
        return previous, current

    def _raw_embedding_similarity(self) -> float | None:
        """Expose a bounded diagnostic without laundering unknown model identity."""
        if self._signal_kind != "text_embedding" or len(self._text_embeddings) < 2:
            return None
        previous, current = self._text_embeddings[-2:]
        if (
            current.iteration != self._iteration
            or previous.iteration != self._iteration - 1
            or previous.dimension != current.dimension
            or not previous.vector
            or any(not math.isfinite(value) for value in (*previous.vector, *current.vector))
            or not any(value != 0.0 for value in previous.vector)
            or not any(value != 0.0 for value in current.vector)
        ):
            return None
        return _cosine_similarity(list(previous.vector), list(current.vector))

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
        pair = self._current_embedding_pair()
        if pair is not None:
            previous, current = pair
            semantic_signal = max(
                0.0,
                _cosine_similarity(
                    list(current.vector),
                    list(previous.vector),
                ),
            )

        total = (
            weights.get("numeric", 0.5) * numeric_signal
            + weights.get("budget", 0.3) * budget_signal
            + weights.get("semantic", 0.2) * semantic_signal
        )
        return total >= self._config.threshold
