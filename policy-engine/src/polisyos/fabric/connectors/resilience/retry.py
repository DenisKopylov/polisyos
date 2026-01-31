"""
Retry Policy with Exponential Backoff and Jitter.

Implements robust retry logic for transient failures with:
- Exponential backoff to prevent thundering herd
- Jitter to desynchronize concurrent retries
- Smart error classification (transient vs permanent)
- OpenTelemetry instrumentation
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors.types import ConnectionError as ConnectorConnectionError
from polisyos.fabric.connectors.types import RateLimitError

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

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
    """Extract Retry-After seconds from error if available."""
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
    Determine if an error is transient and worth retrying.

    Retry Policy:
        ALWAYS Retry:
            - Network errors: ConnectionError, TimeoutError, asyncio.TimeoutError
            - HTTP 429 (Rate Limited)
            - HTTP 503 (Service Unavailable)
            - HTTP 504 (Gateway Timeout)

        NEVER Retry:
            - HTTP 400 (Bad Request)
            - HTTP 401 (Unauthorized)
            - HTTP 403 (Forbidden)
            - HTTP 404 (Not Found)
            - HTTP 422 (Unprocessable Entity)
            - ValueError, TypeError (programming errors)

        CONDITIONAL Retry:
            - HTTP 500 (Internal Server Error) - retry with caution
            - HTTP 502 (Bad Gateway) - transient proxy error
    """
    # Cancellation should never be retried
    if isinstance(error, asyncio.CancelledError):
        return False

    # Explicit connector rate limit error
    if isinstance(error, RateLimitError):
        return True

    # Check for HTTP status codes if error has them
    status_code = getattr(error, "status", None) or getattr(error, "status_code", None)

    if status_code is not None:
        # Transient server errors (retry)
        if status_code in {429, 502, 503, 504}:
            return True

        # Client errors (never retry)
        if 400 <= status_code < 500:
            return False

        # Server errors (conditional retry)
        if status_code == 500:
            return True

        # Unknown 5xx errors (retry with caution)
        if 500 <= status_code < 600:
            return True

    # Network-level errors (always retry)
    if isinstance(
        error,
        (
            ConnectionError,
            ConnectorConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        ),
    ):
        return True

    # OSError subtypes (DNS, socket errors)
    if isinstance(error, OSError):
        return True

    # Programming errors (never retry)
    if isinstance(error, (ValueError, TypeError, AttributeError, KeyError)):
        return False

    # Default: Don't retry unknown errors
    return False


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """
    Retry policy configuration with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of retry attempts (including initial try)
        base_delay: Initial wait time in seconds
        backoff_factor: Exponential multiplier for wait time
        jitter_max: Maximum random jitter in seconds
        max_delay: Maximum wait time cap in seconds
        retry_on_predicate: Custom predicate for retry decisions
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    jitter_max: float = 0.5
    max_delay: float = 60.0
    retry_on_predicate: Callable[[Exception], bool] | None = None

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay <= 0:
            raise ValueError("base_delay must be > 0")
        if self.backoff_factor < 1:
            raise ValueError("backoff_factor must be >= 1")
        if self.jitter_max < 0:
            raise ValueError("jitter_max must be >= 0")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")

    def should_retry(self, error: Exception) -> bool:
        """
        Determine if we should retry after an error.

        Args:
            error: The exception that occurred

        Returns:
            True if we should retry, False otherwise
        """
        # Use custom predicate if provided
        if self.retry_on_predicate is not None:
            return self.retry_on_predicate(error)

        # Use default classification
        return is_retryable_error(error)

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt number.

        Uses exponential backoff with jitter:
            delay = min(base * (factor ** (attempt - 1)) + jitter, max_delay)

        Args:
            attempt: Attempt number (1-indexed)

        Returns:
            Delay in seconds
        """
        if attempt < 1:
            return 0.0

        # Exponential backoff
        exponential = self.base_delay * (self.backoff_factor ** (attempt - 1))

        # Add random jitter
        jitter = random.uniform(0, self.jitter_max)

        # Cap at max_delay
        return min(exponential + jitter, self.max_delay)

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments to func
            **kwargs: Keyword arguments to func

        Returns:
            Result of func

        Raises:
            RetryExhaustedError: If all attempts fail with retryable errors
        """
        attempt = 0
        total_delay = 0.0
        last_error: Exception | None = None
        connector_id = _extract_connector_id(args, kwargs)
        metrics = get_metrics()

        with tracer.start_as_current_span(
            "connector.retry",
            attributes={
                "retry.max_attempts": self.max_attempts,
                "retry.base_delay": self.base_delay,
            },
        ) as parent_span:
            while attempt < self.max_attempts:
                attempt += 1

                with tracer.start_as_current_span(
                    f"connector.retry.attempt_{attempt}",
                    attributes={"retry.attempt": attempt},
                ) as attempt_span:
                    try:
                        result = await func(*args, **kwargs)

                        # Success!
                        if attempt > 1:
                            logger.info(
                                "Retry succeeded",
                                attempt=attempt,
                                total_attempts=self.max_attempts,
                                total_delay_seconds=total_delay,
                            )
                            try:
                                from polisyos.fabric.connectors.base import FetchResult
                                from polisyos.fabric.connectors.base import ResilienceInfo

                                if isinstance(result, FetchResult):
                                    existing = result.resilience
                                    update = {"retry_attempts": attempt}
                                    if existing is not None:
                                        data = existing.model_dump()
                                        data.update(update)
                                        info = ResilienceInfo(**data)
                                    else:
                                        info = ResilienceInfo(**update)
                                    result = result.model_copy(update={"resilience": info})
                            except Exception:
                                pass

                        attempt_span.set_status(Status(StatusCode.OK))
                        parent_span.set_status(Status(StatusCode.OK))
                        parent_span.set_attribute("retry.success_attempt", attempt)

                        return result

                    except asyncio.CancelledError:
                        attempt_span.set_status(Status(StatusCode.ERROR, "Cancelled"))
                        parent_span.set_status(Status(StatusCode.ERROR, "Cancelled"))
                        raise

                    except Exception as error:
                        last_error = error

                        # Record error in span
                        attempt_span.set_status(Status(StatusCode.ERROR, str(error)))
                        attempt_span.record_exception(error)

                        # Non-idempotent or explicitly non-retryable request
                        if not _is_retry_allowed(args, kwargs):
                            logger.debug(
                                "Retry not allowed for request",
                                error_type=type(error).__name__,
                                error_message=str(error),
                                attempt=attempt,
                            )
                            parent_span.set_status(
                                Status(StatusCode.ERROR, "Retry not allowed")
                            )
                            raise

                        # Check if error is retryable
                        if not self.should_retry(error):
                            logger.debug(
                                "Error not retryable",
                                error_type=type(error).__name__,
                                error_message=str(error),
                                attempt=attempt,
                            )
                            parent_span.set_status(
                                Status(StatusCode.ERROR, "Non-retryable error")
                            )
                            raise

                        # If this was the last attempt, raise RetryExhaustedError
                        if attempt >= self.max_attempts:
                            parent_span.set_status(
                                Status(StatusCode.ERROR, "Retry exhausted")
                            )
                            raise RetryExhaustedError(
                                original_error=error,
                                attempts=self.max_attempts,
                                total_delay=total_delay,
                            )

                        # Calculate delay
                        delay = self.calculate_delay(attempt)

                        retry_after = _extract_retry_after_seconds(error)
                        if retry_after is not None and retry_after > delay:
                            delay = min(retry_after, self.max_delay)

                        total_delay += delay

                        # Log retry attempt
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

                        # Wait before next attempt
                        if delay > 0:
                            await asyncio.sleep(delay)

            # All attempts exhausted (safety net)
            if last_error is not None:
                logger.error(
                    "Retry exhausted",
                    attempts=self.max_attempts,
                    total_delay_seconds=total_delay,
                    final_error=str(last_error),
                )

                parent_span.set_status(Status(StatusCode.ERROR, "Retry exhausted"))

                raise RetryExhaustedError(
                    original_error=last_error,
                    attempts=self.max_attempts,
                    total_delay=total_delay,
                )

            raise RuntimeError("RetryPolicy.execute reached unexpected state")


def with_retry(
    policy: RetryPolicy | None = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter_max: float = 0.5,
    max_delay: float = 60.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator to add retry logic to async functions.

    Usage:
        @with_retry(RetryPolicy(max_attempts=5))
        async def fetch_data():
            ...

        # Or with inline config:
        @with_retry(max_attempts=5, base_delay=2.0)
        async def fetch_data():
            ...

    Args:
        policy: RetryPolicy instance (if None, creates one from kwargs)
        max_attempts: Maximum retry attempts (if policy is None)
        base_delay: Initial delay (if policy is None)
        backoff_factor: Exponential factor (if policy is None)
        jitter_max: Max jitter (if policy is None)
        max_delay: Max delay (if policy is None)

    Returns:
        Decorated async function
    """
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
