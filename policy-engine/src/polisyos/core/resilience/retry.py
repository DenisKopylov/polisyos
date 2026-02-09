"""
Shared retry policy with exponential backoff and jitter.

This module is intentionally generic so it can be reused by core, scientist,
foundry and fabric modules.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    trace = None

    class StatusCode(str, Enum):
        OK = "OK"
        ERROR = "ERROR"

    class Status:  # type: ignore[override]
        def __init__(self, status_code: StatusCode, description: str | None = None) -> None:
            self.status_code = status_code
            self.description = description


logger = get_logger(__name__)
tracer = trace.get_tracer(__name__) if trace is not None else None

T = TypeVar("T")


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self,
        original_error: Exception,
        attempts: int,
        total_delay: float,
    ) -> None:
        self.original_error = original_error
        self.attempts = attempts
        self.total_delay = total_delay
        super().__init__(
            f"Retry exhausted after {attempts} attempts ({total_delay:.2f}s): "
            f"{type(original_error).__name__}: {original_error}"
        )


def _extract_retry_after_seconds(error: Exception) -> float | None:
    """Extract Retry-After seconds from an exception payload when available."""
    for attr in ("retry_after", "retry_after_seconds"):
        value = getattr(error, attr, None)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

    details = getattr(error, "details", None)
    if isinstance(details, dict):
        value = details.get("retry_after_seconds")
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

    return None


def _extract_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any | None:
    if "request" in kwargs:
        return kwargs["request"]
    for arg in args:
        if hasattr(arg, "cache_key") and hasattr(arg, "dataset_id"):
            return arg
    return None


def _extract_connector_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    for key in ("handle", "connection", "connection_handle"):
        handle = kwargs.get(key)
        if handle is not None and hasattr(handle, "connector_id"):
            return getattr(handle, "connector_id")
    for arg in args:
        if hasattr(arg, "connector_id"):
            return getattr(arg, "connector_id")
    return None


def _is_retry_allowed(args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
    request = _extract_request(args, kwargs)
    if request is None:
        return True

    retryable = getattr(request, "retryable", None)
    if retryable is False:
        return False

    idempotent = getattr(request, "idempotent", None)
    if idempotent is False:
        return False

    return True


def is_retryable_error(error: Exception) -> bool:
    """
    Classify transient failures.

    The policy is intentionally conservative and domain-agnostic:
    - retries network and 5xx style errors
    - does not retry programming or explicit client validation errors
    """
    if isinstance(error, asyncio.CancelledError):
        return False

    status_code = getattr(error, "status", None) or getattr(error, "status_code", None)
    if status_code is not None:
        if status_code in {429, 500, 502, 503, 504}:
            return True
        if 400 <= status_code < 500:
            return False
        if 500 <= status_code < 600:
            return True

    # Generic named checks to avoid tight coupling with module-specific classes.
    error_name = type(error).__name__
    if error_name in {"RateLimitError", "ConnectorConnectionError"}:
        return True

    if isinstance(error, (ConnectionError, TimeoutError, asyncio.TimeoutError, OSError)):
        return True

    if isinstance(error, (ValueError, TypeError, AttributeError, KeyError)):
        return False

    return False


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry policy configuration with exponential backoff and jitter."""

    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    jitter_max: float = 0.5
    max_delay: float = 60.0
    retry_on_predicate: Callable[[Exception], bool] | None = None

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be >= 0")
        if self.backoff_factor < 1:
            raise ValueError("backoff_factor must be >= 1")
        if self.jitter_max < 0:
            raise ValueError("jitter_max must be >= 0")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")

    def should_retry(self, error: Exception) -> bool:
        if self.retry_on_predicate is not None:
            return self.retry_on_predicate(error)
        return is_retryable_error(error)

    def calculate_delay(self, attempt: int) -> float:
        if attempt < 1 or self.base_delay <= 0:
            return 0.0
        exponential = self.base_delay * (self.backoff_factor ** (attempt - 1))
        jitter = random.uniform(0, self.jitter_max)
        return min(exponential + jitter, self.max_delay)

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        on_error: Callable[[Exception, int, int], None] | None = None,
        **kwargs: Any,
    ) -> T:
        attempt = 0
        total_delay = 0.0
        last_error: Exception | None = None
        connector_id = _extract_connector_id(args, kwargs)
        metrics = get_metrics()

        async def _run() -> T:
            nonlocal attempt, total_delay, last_error
            while attempt < self.max_attempts:
                attempt += 1
                try:
                    result = await func(*args, **kwargs)

                    if attempt > 1:
                        logger.info(
                            "Retry succeeded",
                            attempt=attempt,
                            total_attempts=self.max_attempts,
                            total_delay_seconds=total_delay,
                        )

                    return result
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    last_error = error

                    if on_error is not None:
                        on_error(error, attempt, self.max_attempts)

                    if not _is_retry_allowed(args, kwargs):
                        raise
                    if not self.should_retry(error):
                        raise
                    if attempt >= self.max_attempts:
                        raise RetryExhaustedError(
                            original_error=error,
                            attempts=self.max_attempts,
                            total_delay=total_delay,
                        )

                    delay = self.calculate_delay(attempt)
                    retry_after = _extract_retry_after_seconds(error)
                    if retry_after is not None and retry_after > delay:
                        delay = min(retry_after, self.max_delay)
                    total_delay += delay

                    logger.warning(
                        "Retry attempt",
                        attempt=attempt,
                        max_attempts=self.max_attempts,
                        delay_seconds=delay,
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )

                    if metrics and getattr(metrics, "connector_retry_attempts_total", None):
                        labels = {"attempt": str(attempt)}
                        if connector_id:
                            labels["connector_id"] = connector_id
                        metrics.connector_retry_attempts_total.add(1, labels)  # type: ignore[union-attr]

                    if metrics and getattr(metrics, "connector_retry_delay_seconds", None):
                        labels = {"attempt": str(attempt)}
                        if connector_id:
                            labels["connector_id"] = connector_id
                        metrics.connector_retry_delay_seconds.record(delay, labels)  # type: ignore[union-attr]

                    if delay > 0:
                        await asyncio.sleep(delay)

            if last_error is not None:
                raise RetryExhaustedError(
                    original_error=last_error,
                    attempts=self.max_attempts,
                    total_delay=total_delay,
                )

            raise RuntimeError("RetryPolicy.execute reached unexpected state")

        if tracer is None:
            return await _run()

        with tracer.start_as_current_span(
            "retry.execute",
            attributes={
                "retry.max_attempts": self.max_attempts,
                "retry.base_delay": self.base_delay,
            },
        ) as parent_span:
            try:
                result = await _run()
                parent_span.set_status(Status(StatusCode.OK))
                parent_span.set_attribute("retry.success_attempt", attempt)
                return result
            except Exception as error:
                parent_span.set_status(Status(StatusCode.ERROR, str(error)))
                parent_span.record_exception(error)
                raise


def with_retry(
    policy: RetryPolicy | None = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter_max: float = 0.5,
    max_delay: float = 60.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator that applies retry policy to an async function."""
    if policy is None:
        policy = RetryPolicy(
            max_attempts=max_attempts,
            base_delay=base_delay,
            backoff_factor=backoff_factor,
            jitter_max=jitter_max,
            max_delay=max_delay,
        )

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await policy.execute(func, *args, **kwargs)

        return wrapper

    return decorator


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    delay_seconds: float = 0.0,
    on_error: Callable[[Exception, int, int], None] | None = None,
) -> T:
    """
    Small helper for callers that need fixed-delay retries.

    This keeps the old `core.llm.retry_async` contract and delegates to
    the shared RetryPolicy implementation.
    """
    if attempts <= 0:
        raise ValueError("attempts must be >= 1")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must be >= 0")

    policy = RetryPolicy(
        max_attempts=attempts,
        base_delay=delay_seconds,
        backoff_factor=1.0,
        jitter_max=0.0,
        max_delay=delay_seconds,
        retry_on_predicate=lambda _error: True,
    )

    try:
        return await policy.execute(operation, on_error=on_error)
    except RetryExhaustedError as error:
        raise error.original_error


async def simple_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    delay_seconds: float = 0.0,
    on_error: Callable[[Exception, int, int], None] | None = None,
) -> T:
    """Alias for retry_async for readability in non-LLM modules."""
    return await retry_async(
        operation,
        attempts=attempts,
        delay_seconds=delay_seconds,
        on_error=on_error,
    )


__all__ = [
    "RetryPolicy",
    "RetryExhaustedError",
    "is_retryable_error",
    "with_retry",
    "retry_async",
    "simple_retry",
]
