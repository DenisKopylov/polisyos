"""
Rate Limiter with Token Bucket Algorithm.

Implements adaptive rate limiting with:
- Token bucket algorithm for smooth rate limiting
- Cooperative rate limiting (respects HTTP Retry-After headers)
- Adaptive rate adjustment (AIMD algorithm)
- Thread-safe for concurrent async contexts
"""

from __future__ import annotations

import asyncio
import math
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Tracer

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.fabric._adapters.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.connectors.resilience._bounded_registry import (
    BoundedResourceRegistry,
    _invalid_rate_refusal,
)
from polisyos.fabric.connectors.types.connector_types import RateLimitError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from types import TracebackType

    from polisyos.core.observability import MetricsRegistry

logger = get_logger(__name__)
DEFAULT_TRACER = trace.get_tracer(__name__)

T = TypeVar("T")


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


def _monotonic() -> float:
    return time.monotonic()


def _validate_positive_finite(value: float, field: str) -> None:
    """Reject a nonpositive, nonfinite, or nonnumeric local rate parameter."""
    try:
        valid = math.isfinite(value) and value > 0
    except (TypeError, OverflowError) as error:
        raise _invalid_rate_refusal(f"{field} must be finite and > 0") from error
    if not valid:
        raise _invalid_rate_refusal(f"{field} must be finite and > 0")


def _validate_rate_limit_rps(rate_limit_rps: float) -> None:
    """Reject a nonpositive or nonfinite configured rate."""
    _validate_positive_finite(rate_limit_rps, "rate_limit_rps")


def _limiter_key(limiter_id: str, rate_limit_rps: float) -> str:
    """Use one key for numerically identical configured rates."""
    _validate_rate_limit_rps(rate_limit_rps)
    return f"{limiter_id}:{float(rate_limit_rps).hex()}"


@dataclass
class RateLimiterConfig:
    """
    Rate limiter configuration.

    Args:
        rate_limit_rps: Maximum requests per second
        burst_size: Maximum burst size (defaults to at least one request)
        adaptive: Enable adaptive rate adjustment
        min_rate_rps: Minimum rate when adapting (defaults to rate_limit_rps / 10)
        max_rate_rps: Maximum rate when adapting (defaults to rate_limit_rps)
    """

    rate_limit_rps: float
    burst_size: float | None = None
    adaptive: bool = True
    min_rate_rps: float | None = None
    max_rate_rps: float | None = None

    def __post_init__(self) -> None:
        """Validate and set defaults."""
        _validate_rate_limit_rps(self.rate_limit_rps)

        if self.burst_size is None:
            self.burst_size = max(1.0, self.rate_limit_rps)

        if self.min_rate_rps is None:
            self.min_rate_rps = self.rate_limit_rps / 10.0

        if self.max_rate_rps is None:
            self.max_rate_rps = self.rate_limit_rps

        _validate_positive_finite(self.burst_size, "burst_size")
        _validate_positive_finite(self.min_rate_rps, "min_rate_rps")
        _validate_positive_finite(self.max_rate_rps, "max_rate_rps")
        if self.max_rate_rps < self.min_rate_rps:
            raise _invalid_rate_refusal("max_rate_rps must be >= min_rate_rps")


class RateLimiter:
    """
    Token bucket rate limiter.

    Thread-safe for concurrent async usage.
    """

    def __init__(
        self,
        rate_limit_rps: float,
        burst_size: float | None = None,
        *,
        limiter_id: str | None = None,
        metrics: MetricsRegistry | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        _validate_rate_limit_rps(rate_limit_rps)
        if burst_size is not None:
            _validate_positive_finite(burst_size, "burst_size")
        self.rate_limit_rps = rate_limit_rps
        self.burst_size = max(1.0, rate_limit_rps) if burst_size is None else burst_size
        self.limiter_id = limiter_id

        # Token bucket state
        self._tokens = float(self.burst_size)
        self._last_refill = _monotonic()
        self._blocked_until: float | None = None

        # Thread safety
        self._lock = threading.Lock()

        # Statistics
        self._total_requests = 0
        self._total_wait_time = 0.0
        self._total_acquire_duration = 0.0

        self._metrics = metrics if metrics is not None else _default_metrics()
        self._tracer = tracer or DEFAULT_TRACER

        logger.debug(
            "Rate limiter initialized",
            rate_limit_rps=self.rate_limit_rps,
            burst_size=self.burst_size,
            limiter_id=self.limiter_id,
        )

    def is_quiescent(self) -> bool:
        """Return whether eviction can no longer change admission semantics.

        A limiter with a pending provider cooldown or a partially consumed
        bucket still carries mandatory admission state. Once the cooldown has
        elapsed and the bucket is full, the token state is at its neutral
        boundary and the registry may safely release the object.
        """
        with self._lock:
            now = _monotonic()
            self._refill_tokens(now)
            if self._blocked_until is not None:
                if now < self._blocked_until:
                    return False
                self._blocked_until = None
            return self._tokens >= self.burst_size

    def _refill_tokens(self, now: float) -> None:
        """Refill tokens based on elapsed time (monotonic)."""
        elapsed = max(0.0, now - self._last_refill)
        new_tokens = elapsed * self.rate_limit_rps

        self._tokens = min(self._tokens + new_tokens, self.burst_size)
        self._last_refill = now

    def _set_blocked_until(self, retry_after_seconds: float | None) -> None:
        if retry_after_seconds is None:
            return
        if not math.isfinite(retry_after_seconds):
            raise ValueError("retry_after_seconds must be finite")
        if retry_after_seconds <= 0:
            return
        with self._lock:
            now = _monotonic()
            blocked_until = now + retry_after_seconds
            if self._blocked_until is None or blocked_until > self._blocked_until:
                self._blocked_until = blocked_until

    def _acquire_or_wait_locked(self, *, tokens: float) -> tuple[bool, float, float]:
        now = _monotonic()
        self._refill_tokens(now)

        if self._blocked_until is not None:
            if now < self._blocked_until:
                return False, self._blocked_until - now, self._tokens
            self._blocked_until = None

        available_tokens = max(self._tokens, 0.0)
        if available_tokens >= tokens:
            self._tokens = max(available_tokens - tokens, 0.0)
            self._total_requests += 1
            return True, 0.0, self._tokens

        deficit = max(tokens - available_tokens, 0.0)
        return False, deficit / self.rate_limit_rps, available_tokens

    async def acquire(self, tokens: float = 1.0) -> None:
        """Acquire tokens, waiting if necessary."""
        _validate_positive_finite(tokens, "tokens")
        if tokens > self.burst_size:
            raise _invalid_rate_refusal("tokens must be <= burst_size")

        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["rate_limit_acquire"],
            attributes={
                "rate_limiter.rate_rps": self.rate_limit_rps,
                "rate_limiter.tokens_requested": tokens,
            },
        ) as span:
            start_time = _monotonic()
            total_wait = 0.0
            tokens_remaining = 0.0

            while True:
                with self._lock:
                    acquired, wait_time, tokens_remaining = self._acquire_or_wait_locked(
                        tokens=tokens
                    )
                    blocked = self._blocked_until is not None and wait_time > 0.0

                if acquired:
                    break

                if blocked:
                    logger.debug(
                        "Rate limiter cooldown",
                        wait_seconds=wait_time,
                        limiter_id=self.limiter_id,
                    )
                else:
                    logger.debug(
                        "Rate limit throttle",
                        wait_seconds=wait_time,
                        tokens_available=tokens_remaining,
                        tokens_requested=tokens,
                        limiter_id=self.limiter_id,
                    )
                await asyncio.sleep(wait_time)
                total_wait += wait_time

            acquire_duration = _monotonic() - start_time

            with self._lock:
                self._total_wait_time += total_wait
                self._total_acquire_duration += acquire_duration

            span.set_attribute("rate_limiter.wait_seconds", total_wait)
            span.set_attribute("rate_limiter.acquire_duration_seconds", acquire_duration)
            span.set_status(Status(StatusCode.OK))

            wait_metric = getattr(self._metrics, "connector_rate_limit_wait_seconds", None)
            if wait_metric is not None:
                labels = {}
                if self.limiter_id:
                    labels["connector_id"] = self.limiter_id
                wait_metric.record(total_wait, labels)

            acquire_metric = getattr(
                self._metrics,
                "connector_rate_limit_acquire_duration_seconds",
                None,
            )
            if acquire_metric is not None:
                labels = {}
                if self.limiter_id:
                    labels["connector_id"] = self.limiter_id
                acquire_metric.record(
                    acquire_duration,
                    labels,
                )

            tokens_metric = getattr(self._metrics, "connector_rate_limit_tokens", None)
            if tokens_metric is not None:
                labels = {}
                if self.limiter_id:
                    labels["connector_id"] = self.limiter_id
                with self._lock:
                    tokens_metric.set(self._tokens, labels)

    async def __aenter__(self) -> RateLimiter:
        await self.acquire()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        del exc_type, exc_val, exc_tb
        return None

    def record_rate_limit(self, retry_after_seconds: float | None = None) -> None:
        """Record a rate limit signal (e.g., HTTP 429) and apply cooldown."""
        self._set_blocked_until(retry_after_seconds)

        throttled_metric = getattr(self._metrics, "connector_rate_limit_throttled_total", None)
        if throttled_metric is not None:
            labels = {}
            if self.limiter_id:
                labels["connector_id"] = self.limiter_id
            throttled_metric.add(1, labels)

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "rate_limit_rps": self.rate_limit_rps,
                "burst_size": self.burst_size,
                "tokens_available": self._tokens,
                "total_requests": self._total_requests,
                "total_wait_time_seconds": self._total_wait_time,
                "total_acquire_duration_seconds": self._total_acquire_duration,
                "average_wait_seconds": (
                    self._total_wait_time / self._total_requests
                    if self._total_requests > 0
                    else 0.0
                ),
                "average_acquire_duration_seconds": (
                    self._total_acquire_duration / self._total_requests
                    if self._total_requests > 0
                    else 0.0
                ),
                "blocked_until": self._blocked_until,
                "limiter_id": self.limiter_id,
            }


class AdaptiveRateLimiter(RateLimiter):
    """
    Rate limiter with adaptive rate adjustment (AIMD).
    """

    def __init__(
        self,
        initial_rate_rps: float,
        config: RateLimiterConfig | None = None,
        *,
        limiter_id: str | None = None,
        metrics: MetricsRegistry | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        self.config = config or RateLimiterConfig(rate_limit_rps=initial_rate_rps)
        super().__init__(
            rate_limit_rps=initial_rate_rps,
            burst_size=self.config.burst_size,
            limiter_id=limiter_id,
            metrics=metrics,
            tracer=tracer,
        )

        self._current_rate = initial_rate_rps
        self._increase_step = 0.1
        self._decrease_factor = 0.5
        self._success_count = 0
        self._success_window = 100

    def is_quiescent(self) -> bool:
        """Return whether token and adaptive state are safe to release."""
        if not super().is_quiescent():
            return False
        with self._lock:
            return self.rate_limit_rps == self.config.rate_limit_rps and self._success_count == 0

    def adjust_rate(self, new_rate: float) -> None:
        _validate_positive_finite(new_rate, "new_rate")

        min_rate = self.config.min_rate_rps or (self.config.rate_limit_rps / 10.0)
        max_rate = self.config.max_rate_rps or self.config.rate_limit_rps
        new_rate = max(min_rate, min(new_rate, max_rate))

        with self._lock:
            old_rate = self._current_rate
            self._current_rate = new_rate
            self.rate_limit_rps = new_rate

            logger.info(
                "Rate limit adjusted",
                old_rate=old_rate,
                new_rate=new_rate,
                min_rate=self.config.min_rate_rps,
                max_rate=self.config.max_rate_rps,
                limiter_id=self.limiter_id,
            )

    def record_success(self) -> None:
        if not self.config.adaptive:
            return

        new_rate: float | None = None
        with self._lock:
            self._success_count += 1
            if self._success_count >= self._success_window:
                self._success_count = 0
                maximum = self.config.max_rate_rps
                if maximum is None:
                    raise _invalid_rate_refusal("max_rate_rps must be finite and > 0")
                _validate_positive_finite(maximum, "max_rate_rps")
                _validate_positive_finite(self._current_rate, "current_rate")
                factor = 1.0 + self._increase_step
                new_rate = (
                    maximum
                    if self._current_rate >= maximum / factor
                    else self._current_rate * factor
                )

        if new_rate is not None:
            self.adjust_rate(new_rate)

    def record_rate_limit(self, retry_after_seconds: float | None = None) -> None:
        if not self.config.adaptive:
            super().record_rate_limit(retry_after_seconds)
            return

        new_rate: float | None = None
        with self._lock:
            self._success_count = 0
            minimum = self.config.min_rate_rps
            if minimum is None:
                raise _invalid_rate_refusal("min_rate_rps must be finite and > 0")
            _validate_positive_finite(minimum, "min_rate_rps")
            _validate_positive_finite(self._current_rate, "current_rate")
            new_rate = max(minimum, self._current_rate * self._decrease_factor)

        if new_rate is not None:
            logger.warning(
                "Rate limit hit (429)",
                current_rate=self._current_rate,
                new_rate=new_rate,
                retry_after_seconds=retry_after_seconds,
                limiter_id=self.limiter_id,
            )
            self.adjust_rate(new_rate)

        super().record_rate_limit(retry_after_seconds)


async def _call_with_limiter[T](
    limiter: RateLimiter,
    func: Callable[..., Awaitable[T]],
    *args: object,
    **kwargs: object,
) -> T:
    """Apply admission and propagate typed provider cooldown to the same owner."""
    await limiter.acquire()
    try:
        return await func(*args, **kwargs)
    except RateLimitError as error:
        limiter.record_rate_limit(error.retry_after)
        raise


def with_rate_limit(
    rate_limit_rps: float | Callable[..., float | None],
    adaptive: bool = False,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Add rate limiting; a callable may resolve a per-call rate or explicit None."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        limiters = BoundedResourceRegistry[RateLimiter]()

        def _default_limiter_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
            connector_id = None
            for key in ("handle", "connection", "connection_handle"):
                handle = kwargs.get(key)
                if handle is not None and hasattr(handle, "connector_id"):
                    connector_id = handle.connector_id
                    break
            if connector_id is None:
                for arg in args:
                    if hasattr(arg, "connector_id"):
                        connector_id = arg.connector_id
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
            if domain:
                return f"{base}:{domain}"
            return base

        @wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            rate = rate_limit_rps(*args, **kwargs) if callable(rate_limit_rps) else rate_limit_rps
            if rate is None:
                return await func(*args, **kwargs)
            _validate_rate_limit_rps(rate)
            limiter_id = _default_limiter_id(args, kwargs)
            # Match apply_resilience's separation of differently configured rates.
            limiter_key = _limiter_key(limiter_id, rate)
            with limiters.lease(
                limiter_key,
                lambda: (
                    AdaptiveRateLimiter(
                        initial_rate_rps=rate,
                        config=RateLimiterConfig(rate_limit_rps=rate),
                        limiter_id=limiter_id,
                    )
                    if adaptive
                    else RateLimiter(rate_limit_rps=rate, limiter_id=limiter_id)
                ),
            ) as limiter:
                return await _call_with_limiter(limiter, func, *args, **kwargs)

        wrapper._rate_limiters = limiters  # type: ignore[attr-defined]
        return wrapper

    return decorator


def parse_retry_after_header(header_value: str | int | None) -> float | None:
    """Parse HTTP Retry-After header value."""
    if header_value is None:
        return None

    try:
        return float(header_value)
    except (ValueError, TypeError):
        pass

    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(str(header_value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        delta = (parsed - datetime.now(UTC)).total_seconds()
        return max(0.0, delta)
    except Exception:
        logger.warning(
            "Retry-After header in HTTP-date format not supported",
            header_value=header_value,
        )
        return None
