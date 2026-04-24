"""Backward-compatible retry API for fabric connectors.

The implementation now lives in `polisyos.core.resilience.retry` so all modules
share one retry mechanism.
"""

from polisyos.core.resilience.retry import (
    RetryExhaustedError,
    RetryPolicy,
    is_retryable_error,
    retry_async,
    simple_retry,
    with_retry,
)

__all__ = [
    "RetryExhaustedError",
    "RetryPolicy",
    "is_retryable_error",
    "retry_async",
    "simple_retry",
    "with_retry",
]
