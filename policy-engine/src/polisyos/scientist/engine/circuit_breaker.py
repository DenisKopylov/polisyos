"""Circuit breaker for node execution in the Scientist engine.

Prevents cascading failures by short-circuiting requests to consistently
failing nodes.  State machine::

    CLOSED ──(failures >= threshold)──> OPEN
    OPEN   ──(recovery_timeout elapsed)──> HALF_OPEN
    HALF_OPEN ──(success)──> CLOSED
    HALF_OPEN ──(failure)──> OPEN
"""

from __future__ import annotations

import threading
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
]

CircuitState = Literal["closed", "open", "half_open"]


class CircuitBreakerConfig(BaseModel):
    """Configuration for :class:`CircuitBreaker`."""

    model_config = ConfigDict(extra="forbid")

    failure_threshold: int = Field(default=5, ge=1, le=50)
    recovery_timeout_s: float = Field(default=30.0, ge=1.0, le=600.0)
    half_open_max_calls: int = Field(default=1, ge=1, le=10)


class CircuitBreaker:
    """Thread-safe circuit breaker for node-level failure isolation."""

    def __init__(
        self,
        config: CircuitBreakerConfig | None = None,
        *,
        name: str = "default",
    ) -> None:
        self._config = config or CircuitBreakerConfig()
        self._name = name
        self._state: CircuitState = "closed"
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls: int = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def name(self) -> str:
        return self._name

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def allow_request(self) -> bool:
        """Return ``True`` if a request is currently allowed."""
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._state == "closed":
                return True
            if self._state == "half_open":
                if self._half_open_calls < self._config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            # open
            return False

    def record_success(self) -> None:
        """Record a successful execution.  Resets failure count."""
        with self._lock:
            if self._state == "half_open":
                self._state = "closed"
            self._failure_count = 0
            self._half_open_calls = 0

    def record_failure(self) -> None:
        """Record a failed execution.  May transition to open."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == "half_open" or (
                self._state == "closed" and self._failure_count >= self._config.failure_threshold
            ):
                self._state = "open"
                self._half_open_calls = 0

    def reset(self) -> None:
        """Force-reset to closed (testing/admin use)."""
        with self._lock:
            self._state = "closed"
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_failure_time = 0.0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_transition_to_half_open(self) -> None:
        """Caller must hold ``_lock``."""
        if self._state != "open":
            return
        elapsed = time.monotonic() - self._last_failure_time
        if elapsed >= self._config.recovery_timeout_s:
            self._state = "half_open"
            self._half_open_calls = 0
