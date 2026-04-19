"""
Circuit Breaker Pattern for Fault Tolerance.

Implements a state machine that protects systems from cascade failures:

State Machine:
    CLOSED (Normal) -> failures accumulate -> OPEN (Broken)
    OPEN -> timeout expires -> HALF_OPEN (Testing)
    HALF_OPEN -> success -> CLOSED | failure -> OPEN
"""
from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Tracer

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors.resilience._bounded_registry import (
    BoundedResourceRegistry,
)
from polisyos.fabric.observability import FABRIC_TRACE_NAMES

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from polisyos.core.observability import MetricsRegistry

logger = get_logger(__name__)
DEFAULT_TRACER = trace.get_tracer(__name__)

T = TypeVar("T")


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


def _monotonic() -> float:
    return time.monotonic()


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CircuitState(Enum):
    """Circuit breaker state."""

    CLOSED = "CLOSED"  # Normal operation, requests allowed
    OPEN = "OPEN"  # Circuit tripped, requests rejected
    HALF_OPEN = "HALF_OPEN"  # Testing recovery, limited requests


class CircuitOpenError(Exception):
    """Raised when circuit is OPEN and request is rejected."""

    def __init__(self, circuit_id: str, opened_at: datetime, timeout_seconds: float) -> None:
        self.circuit_id = circuit_id
        self.opened_at = opened_at
        self.timeout_seconds = timeout_seconds

        time_remaining = timeout_seconds - (_utc_now() - opened_at).total_seconds()

        super().__init__(
            f"Circuit '{circuit_id}' is OPEN. "
            f"Opened at {opened_at.isoformat()}. "
            f"Retry in {time_remaining:.1f}s."
        )


class CircuitLeaseError(RuntimeError):
    """Raised when a half-open attempt lease is released without ownership."""


@dataclass
class CircuitBreakerConfig:
    """
    Circuit breaker configuration.

    Args:
        failure_threshold: Number of failures before opening circuit
        success_threshold: Number of successes in HALF_OPEN before closing
        timeout_seconds: Time to wait before entering HALF_OPEN from OPEN
        half_open_max_calls: Maximum concurrent calls in HALF_OPEN state
        window_size_seconds: Sliding window size for failure counting
        min_throughput: Minimum calls in window before evaluating failure threshold
    """

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 60.0
    half_open_max_calls: int = 1
    window_size_seconds: float = 60.0
    min_throughput: int = 10

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if self.half_open_max_calls < 1:
            raise ValueError("half_open_max_calls must be >= 1")
        if self.window_size_seconds <= 0:
            raise ValueError("window_size_seconds must be > 0")
        if self.min_throughput < 1:
            raise ValueError("min_throughput must be >= 1")


@dataclass(frozen=True, slots=True)
class CircuitAttemptLease:
    """Execution-boundary lease for one circuit-breaker attempt."""

    circuit_id: str
    state: CircuitState
    token: str | None = None

    @property
    def owns_half_open_slot(self) -> bool:
        return self.token is not None


class CircuitBreaker:
    """
    Circuit breaker with CLOSED/OPEN/HALF_OPEN state machine.

    Thread-safe for use in async contexts.
    """

    def __init__(
        self,
        circuit_id: str = "default",
        config: CircuitBreakerConfig | None = None,
        *,
        metrics: MetricsRegistry | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.circuit_id = circuit_id
        self.config = config or CircuitBreakerConfig()

        # State
        self._state = CircuitState.CLOSED
        self._success_count = 0
        self._opened_at: datetime | None = None
        self._opened_at_monotonic: float | None = None
        self._half_open_leases: set[str] = set()
        self._last_failure_at: datetime | None = None

        # Sliding window (monotonic timestamps)
        self._failure_timestamps: deque[float] = deque()
        self._call_timestamps: deque[float] = deque()

        # Thread safety
        self._lock = threading.Lock()

        # Metrics
        self._metrics = metrics if metrics is not None else _default_metrics()
        self._tracer = tracer or DEFAULT_TRACER
        self._set_state_metric(self._state)

        logger.info(
            "Circuit breaker initialized",
            circuit_id=self.circuit_id,
            config=self.config,
        )

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        with self._lock:
            return self._state

    @property
    def opened_at(self) -> datetime | None:
        """Timestamp when circuit opened (UTC)."""
        with self._lock:
            return self._opened_at

    def is_open(self) -> bool:
        """Check if circuit is OPEN (rejecting requests)."""
        with self._lock:
            self._check_timeout()
            return self._state == CircuitState.OPEN

    def is_half_open(self) -> bool:
        """Check if circuit is HALF_OPEN (testing recovery)."""
        with self._lock:
            return self._state == CircuitState.HALF_OPEN

    def is_closed(self) -> bool:
        """Check if circuit is CLOSED (normal operation)."""
        with self._lock:
            self._check_timeout()
            return self._state == CircuitState.CLOSED

    def _set_state_metric(self, state: CircuitState) -> None:
        metric = getattr(self._metrics, "connector_circuit_state", None)
        if metric is None:
            return
        value = {
            CircuitState.CLOSED: 0.0,
            CircuitState.OPEN: 1.0,
            CircuitState.HALF_OPEN: 2.0,
        }[state]
        metric.set(value, {"circuit_id": self.circuit_id})

    def _record_trip_metric(self) -> None:
        metric = getattr(self._metrics, "connector_circuit_trips_total", None)
        if metric is None:
            return
        metric.add(1, {"circuit_id": self.circuit_id})

    def _record_reject_metric(self) -> None:
        metric = getattr(
            self._metrics,
            "connector_circuit_rejected_requests_total",
            None,
        )
        if metric is None:
            return
        metric.add(1, {"circuit_id": self.circuit_id})

    def _evict_old(self, now: float) -> None:
        cutoff = now - self.config.window_size_seconds

        while self._failure_timestamps and self._failure_timestamps[0] < cutoff:
            self._failure_timestamps.popleft()

        while self._call_timestamps and self._call_timestamps[0] < cutoff:
            self._call_timestamps.popleft()

    def _record_call(self, now: float) -> None:
        self._call_timestamps.append(now)
        self._evict_old(now)

    def _check_timeout(self) -> None:
        """Transition OPEN -> HALF_OPEN when timeout expires."""
        if self._state != CircuitState.OPEN or self._opened_at_monotonic is None:
            return

        elapsed = _monotonic() - self._opened_at_monotonic
        if elapsed >= self.config.timeout_seconds:
            self._transition_to_half_open()

    def _transition_to_half_open(self) -> None:
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["circuit_transition"],
            attributes={
                "circuit.id": self.circuit_id,
                "circuit.from_state": CircuitState.OPEN.value,
                "circuit.to_state": CircuitState.HALF_OPEN.value,
            },
        ):
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0
            self._half_open_leases.clear()
            self._set_state_metric(self._state)

            logger.info(
                "Circuit half-opened",
                circuit_id=self.circuit_id,
                previous_state="OPEN",
            )

    def _transition_to_open(self) -> None:
        previous_state = self._state
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["circuit_transition"],
            attributes={
                "circuit.id": self.circuit_id,
                "circuit.from_state": previous_state.value,
                "circuit.to_state": CircuitState.OPEN.value,
            },
        ):
            self._state = CircuitState.OPEN
            self._success_count = 0
            self._opened_at = _utc_now()
            self._opened_at_monotonic = _monotonic()
            self._half_open_leases.clear()
            self._set_state_metric(self._state)
            self._record_trip_metric()

            logger.critical(
                "Circuit opened (tripped)",
                circuit_id=self.circuit_id,
                failure_count=len(self._failure_timestamps),
                failure_threshold=self.config.failure_threshold,
            )

    def _transition_to_closed(self) -> None:
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["circuit_transition"],
            attributes={
                "circuit.id": self.circuit_id,
                "circuit.from_state": self._state.value,
                "circuit.to_state": CircuitState.CLOSED.value,
            },
        ):
            self._state = CircuitState.CLOSED
            self._success_count = 0
            self._opened_at = None
            self._opened_at_monotonic = None
            self._half_open_leases.clear()
            self._failure_timestamps.clear()
            self._call_timestamps.clear()
            self._set_state_metric(self._state)

            logger.info(
                "Circuit closed (recovered)",
                circuit_id=self.circuit_id,
            )

    def _acquire_half_open_lease_locked(self) -> CircuitAttemptLease | None:
        if len(self._half_open_leases) >= self.config.half_open_max_calls:
            return None
        token = uuid4().hex
        self._half_open_leases.add(token)
        return CircuitAttemptLease(
            circuit_id=self.circuit_id,
            state=CircuitState.HALF_OPEN,
            token=token,
        )

    def _release_half_open_lease_locked(self, lease: CircuitAttemptLease | None) -> None:
        if lease is None or not lease.owns_half_open_slot or lease.token is None:
            raise CircuitLeaseError(
                f"Circuit '{self.circuit_id}' requires a half-open lease token for release"
            )
        if lease.token not in self._half_open_leases:
            raise CircuitLeaseError(
                f"Circuit '{self.circuit_id}' half-open lease '{lease.token}' is not owned"
            )
        self._half_open_leases.remove(lease.token)

    def _release_cancelled_lease(self, lease: CircuitAttemptLease | None) -> None:
        if lease is None or not lease.owns_half_open_slot or lease.token is None:
            return
        with self._lock:
            if lease.token in self._half_open_leases:
                self._half_open_leases.remove(lease.token)

    def acquire_attempt(self) -> CircuitAttemptLease | None:
        """Acquire an execution-boundary attempt lease if the circuit allows it."""
        with self._lock:
            self._check_timeout()

            if self._state == CircuitState.OPEN:
                return None

            if self._state == CircuitState.HALF_OPEN:
                return self._acquire_half_open_lease_locked()

            return CircuitAttemptLease(
                circuit_id=self.circuit_id,
                state=CircuitState.CLOSED,
            )

    def record_success(self, lease: CircuitAttemptLease | None = None) -> None:
        """Record a successful operation."""
        with self._lock:
            now = _monotonic()
            self._record_call(now)

            if self._state == CircuitState.HALF_OPEN:
                self._release_half_open_lease_locked(lease)
                self._success_count += 1

                logger.debug(
                    "Half-open success",
                    circuit_id=self.circuit_id,
                    success_count=self._success_count,
                    success_threshold=self.config.success_threshold,
                )

                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()

    def record_failure(self, lease: CircuitAttemptLease | None = None) -> None:
        """Record a failed operation."""
        with self._lock:
            now = _monotonic()
            self._record_call(now)
            self._last_failure_at = _utc_now()

            if self._state == CircuitState.HALF_OPEN:
                self._release_half_open_lease_locked(lease)
                self._transition_to_open()
                return

            if self._state == CircuitState.CLOSED:
                self._failure_timestamps.append(now)
                self._evict_old(now)

                failure_count = len(self._failure_timestamps)
                call_count = len(self._call_timestamps)

                logger.debug(
                    "Failure recorded",
                    circuit_id=self.circuit_id,
                    failure_count=failure_count,
                    failure_threshold=self.config.failure_threshold,
                    call_count=call_count,
                )

                if (
                    call_count >= self.config.min_throughput
                    and failure_count >= self.config.failure_threshold
                ):
                    self._transition_to_open()

    def can_attempt(self) -> bool:
        """Advisory readiness check; acquire_attempt() owns the real execution lease."""
        with self._lock:
            self._check_timeout()

            if self._state == CircuitState.OPEN:
                return False

            if self._state == CircuitState.HALF_OPEN:
                return len(self._half_open_leases) < self.config.half_open_max_calls

            return True

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute function with circuit breaker protection.

        Raises:
            CircuitOpenError: If circuit is OPEN
        """
        lease = self.acquire_attempt()
        if lease is None:
            self._record_reject_metric()
            opened_at = self._opened_at or _utc_now()
            raise CircuitOpenError(self.circuit_id, opened_at, self.config.timeout_seconds)

        with self._tracer.start_as_current_span(
            "connector.circuit_breaker.execute",
            attributes={
                "circuit.id": self.circuit_id,
                "circuit.state": lease.state.value,
            },
        ) as span:
            try:
                result = await func(*args, **kwargs)
                self.record_success(lease)
                span.set_status(Status(StatusCode.OK))
                return result

            except asyncio.CancelledError:
                # Do not count cancellations as failures
                self._release_cancelled_lease(lease)
                span.set_status(Status(StatusCode.ERROR, "Cancelled"))
                raise

            except Exception as error:
                self.record_failure(lease)
                span.set_status(Status(StatusCode.ERROR, str(error)))
                span.record_exception(error)
                raise

    def get_stats(self) -> dict[str, Any]:
        """Get current circuit statistics."""
        with self._lock:
            now = _monotonic()
            self._evict_old(now)

            return {
                "circuit_id": self.circuit_id,
                "state": self._state.value,
                "failure_count": len(self._failure_timestamps),
                "success_count": self._success_count,
                "call_count": len(self._call_timestamps),
                "opened_at": self._opened_at.isoformat() if self._opened_at else None,
                "last_failure_at": self._last_failure_at.isoformat() if self._last_failure_at else None,
                "half_open_calls": len(self._half_open_leases),
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout_seconds": self.config.timeout_seconds,
                    "half_open_max_calls": self.config.half_open_max_calls,
                    "window_size_seconds": self.config.window_size_seconds,
                    "min_throughput": self.config.min_throughput,
                },
            }


def _default_circuit_id[T](
    func: Callable[..., Awaitable[T]],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    connector_id = None
    for key in ("handle", "connection", "connection_handle"):
        handle = kwargs.get(key)
        if handle is not None and hasattr(handle, "connector_id"):
            connector_id = getattr(handle, "connector_id")
            break

    if connector_id is None:
        for arg in args:
            if hasattr(arg, "connector_id"):
                connector_id = getattr(arg, "connector_id")
                break

    dataset_id = None
    if "request" in kwargs:
        dataset_id = getattr(kwargs["request"], "dataset_id", None)
    else:
        for arg in args:
            if hasattr(arg, "dataset_id"):
                dataset_id = getattr(arg, "dataset_id")
                break

    domain = None
    handle = None
    for key in ("handle", "connection", "connection_handle"):
        handle = kwargs.get(key)
        if handle is not None:
            break
    if handle is None:
        for arg in args:
            if hasattr(arg, "config") and hasattr(arg, "connector_id"):
                handle = arg
                break

    if handle is not None and hasattr(handle, "config"):
        url = getattr(handle.config, "url", None)
        if isinstance(url, str) and "://" in url:
            try:
                from urllib.parse import urlparse

                domain = urlparse(url).netloc or None
            except Exception:
                domain = None

    base = connector_id or f"{func.__module__}.{func.__name__}"
    parts = [base]
    if domain:
        parts.append(domain)
    if dataset_id:
        parts.append(str(dataset_id))
    return ":".join(parts)


def with_circuit_breaker(
    config: CircuitBreakerConfig | None = None,
    circuit_id: str | Callable[..., str] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator to add circuit breaker to async functions.

    Usage:
        @with_circuit_breaker(CircuitBreakerConfig(failure_threshold=10))
        async def fetch_data():
            ...

    Args:
        config: Circuit breaker configuration
        circuit_id: Unique circuit identifier or callable returning one

    Returns:
        Decorated async function
    """
    breakers = BoundedResourceRegistry[CircuitBreaker]()

    def _resolve_breaker(
        func: Callable[..., Awaitable[T]],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> CircuitBreaker:
        if callable(circuit_id):
            resolved_id = circuit_id(*args, **kwargs)
        elif isinstance(circuit_id, str):
            resolved_id = circuit_id
        else:
            resolved_id = _default_circuit_id(func, args, kwargs)

        return cast(
            "CircuitBreaker",
            breakers.get_or_create(
                resolved_id,
                lambda: CircuitBreaker(circuit_id=resolved_id, config=config),
            ),
        )

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            breaker = _resolve_breaker(func, args, kwargs)
            return await breaker.execute(func, *args, **kwargs)

        wrapper._circuit_breakers = breakers  # type: ignore[attr-defined]
        return wrapper

    return decorator
