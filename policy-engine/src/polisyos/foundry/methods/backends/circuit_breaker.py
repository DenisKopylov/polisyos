"""
Circuit Breaker for Foundry compute backends.

A circuit breaker wraps calls to a compute backend and prevents cascading
failures by temporarily *opening* (rejecting calls) after a threshold of
consecutive failures, then probing for recovery after a timeout.

State machine
-------------
::

    CLOSED ──(failures ≥ threshold)──► OPEN
    OPEN   ──(recovery_timeout passes)──► HALF_OPEN
    HALF_OPEN ──(success)──► CLOSED
    HALF_OPEN ──(failure)──► OPEN

Usage
-----
::

    from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreaker

    breaker = CircuitBreaker(backend="jax", failure_threshold=5)

    try:
        result = breaker.call(my_jax_fn, state, params)
    except BackendCircuitOpenError:
        # fall back to NumPy
        result = numpy_fallback(state, params)

Thread Safety
-------------
All state mutations are protected by a ``threading.Lock``.
"""

from __future__ import annotations

import enum
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from polisyos.foundry.methods._internal.logging import get_foundry_logger

_log = get_foundry_logger("foundry.backends.circuit_breaker")

__all__ = [
    "BackendCircuitOpenError",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "CircuitState",
    "get_circuit_breaker_registry",
]

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BackendCircuitOpenError(Exception):
    """
    Raised when a call is rejected because the circuit breaker is OPEN.

    Callers should catch this and apply a fallback strategy (e.g. route to
    a different backend or return a degraded result).
    """

    def __init__(self, backend: str, recovery_in: float) -> None:
        super().__init__(
            f"Circuit breaker for backend '{backend}' is OPEN. "
            f"Recovery probe in {recovery_in:.1f}s."
        )
        self.backend = backend
        self.recovery_in = recovery_in


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class CircuitState(enum.Enum):
    """States of the circuit breaker state machine."""

    CLOSED = "closed"  # Normal operation — calls pass through
    OPEN = "open"  # Failures exceeded threshold — calls rejected
    HALF_OPEN = "half_open"  # Recovery probe — next call determines state


@dataclass
class CircuitBreakerStats:
    """Cumulative statistics for a circuit breaker instance."""

    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_rejected: int = 0  # calls rejected while OPEN
    state_changes: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """
    A thread-safe circuit breaker for a single compute backend.

    Parameters
    ----------
    backend:
        Human-readable backend name (e.g. ``"jax"``, ``"numpy"``).
    failure_threshold:
        Number of consecutive failures that trip the circuit (default: 5).
    recovery_timeout:
        Seconds to wait in OPEN state before attempting a recovery probe
        (default: 30.0).
    success_threshold:
        Number of consecutive successes in HALF_OPEN state needed to
        transition back to CLOSED (default: 1).
    """

    def __init__(
        self,
        backend: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 1,
    ) -> None:
        self._backend = backend
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._consecutive_failures: int = 0
        self._consecutive_successes: int = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()
        self._stats = CircuitBreakerStats()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        with self._lock:
            return CircuitBreakerStats(
                total_calls=self._stats.total_calls,
                total_failures=self._stats.total_failures,
                total_successes=self._stats.total_successes,
                total_rejected=self._stats.total_rejected,
                state_changes=self._stats.state_changes,
                last_failure_time=self._stats.last_failure_time,
                last_success_time=self._stats.last_success_time,
            )

    # ------------------------------------------------------------------
    # Core call
    # ------------------------------------------------------------------

    def call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Execute *fn* through the circuit breaker.

        Parameters
        ----------
        fn:
            Callable to invoke (e.g. a backend dispatch function).
        *args, **kwargs:
            Arguments forwarded to *fn*.

        Returns
        -------
        T
            Return value of *fn*.

        Raises
        ------
        BackendCircuitOpenError
            If the circuit is OPEN and the recovery timeout hasn't elapsed.
        Exception
            Any exception raised by *fn* is re-raised after recording the
            failure.
        """
        with self._lock:
            current_state = self._check_state()

        if current_state == CircuitState.OPEN:
            with self._lock:
                self._stats.total_rejected += 1
                recovery_in = max(
                    0.0,
                    self._recovery_timeout - (time.monotonic() - self._last_failure_time),
                )
            raise BackendCircuitOpenError(self._backend, recovery_in)

        with self._lock:
            self._stats.total_calls += 1
        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    # ------------------------------------------------------------------
    # Manual state control
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Force the circuit back to CLOSED state (for testing / ops)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._stats.state_changes += 1

    def trip(self) -> None:
        """Force the circuit to OPEN state (for testing / ops)."""
        with self._lock:
            self._state = CircuitState.OPEN
            self._last_failure_time = time.monotonic()
            self._stats.state_changes += 1

    # ------------------------------------------------------------------
    # Internal state machine
    # ------------------------------------------------------------------

    def _check_state(self) -> CircuitState:
        """
        Called under lock.  Transitions OPEN → HALF_OPEN if recovery
        timeout has elapsed.
        """
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._stats.state_changes += 1
        return self._state

    def _on_success(self) -> None:
        with self._lock:
            self._stats.total_successes += 1
            self._stats.last_success_time = time.monotonic()
            self._consecutive_failures = 0

            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self._success_threshold:
                    self._state = CircuitState.CLOSED
                    self._consecutive_successes = 0
                    self._stats.state_changes += 1
                    _log.info(
                        "circuit_recovered",
                        backend=self._backend,
                        state="closed",
                    )
            elif self._state == CircuitState.CLOSED:
                self._consecutive_successes += 1

    def _on_failure(self) -> None:
        with self._lock:
            self._stats.total_failures += 1
            self._stats.last_failure_time = time.monotonic()
            self._last_failure_time = self._stats.last_failure_time
            self._consecutive_failures += 1
            self._consecutive_successes = 0

            effective_threshold = (
                1 if self._state == CircuitState.HALF_OPEN else self._failure_threshold
            )
            if self._state in {CircuitState.CLOSED, CircuitState.HALF_OPEN}:
                if self._consecutive_failures >= effective_threshold:
                    self._state = CircuitState.OPEN
                    self._stats.state_changes += 1
                    _log.warning(
                        "circuit_opened",
                        backend=self._backend,
                        failure_count=self._consecutive_failures,
                        failure_threshold=self._failure_threshold,
                    )

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker backend={self._backend!r} "
            f"state={self._state.value} "
            f"failures={self._consecutive_failures}/{self._failure_threshold}>"
        )


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry
# ---------------------------------------------------------------------------


class CircuitBreakerRegistry:
    """
    Process-wide registry of circuit breakers, one per backend.

    Provides a convenient ``get(backend_name)`` accessor and aggregated
    health reporting.
    """

    _instance: CircuitBreakerRegistry | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> CircuitBreakerRegistry:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = object.__new__(cls)
                    inst._breakers: dict[str, CircuitBreaker] = {}
                    inst._reg_lock = threading.Lock()
                    cls._instance = inst
        return cls._instance

    def get(
        self,
        backend: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> CircuitBreaker:
        """
        Get (or create) the circuit breaker for *backend*.

        If the breaker doesn't exist yet it is created with the supplied
        defaults.  Subsequent calls with the same *backend* name always
        return the same instance.
        """
        with self._reg_lock:
            if backend not in self._breakers:
                self._breakers[backend] = CircuitBreaker(
                    backend=backend,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                )
            return self._breakers[backend]

    def health(self) -> dict[str, dict[str, Any]]:
        """Return a health summary for all registered breakers."""
        with self._reg_lock:
            return {
                name: {
                    "state": breaker.state.value,
                    "stats": {
                        "total_calls": breaker.stats.total_calls,
                        "total_failures": breaker.stats.total_failures,
                        "total_rejected": breaker.stats.total_rejected,
                        "state_changes": breaker.stats.state_changes,
                    },
                }
                for name, breaker in sorted(self._breakers.items())
            }

    def reset_all(self) -> None:
        """Reset all breakers to CLOSED (for testing)."""
        with self._reg_lock:
            for breaker in self._breakers.values():
                breaker.reset()

    @classmethod
    def reset_instance(cls) -> None:
        """Destroy the singleton (for testing)."""
        with cls._lock:
            cls._instance = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global CircuitBreakerRegistry singleton."""
    return CircuitBreakerRegistry()
