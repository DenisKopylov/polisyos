"""Error classification for distributed runner backends.

Classifies exceptions from remote execution (Ray, Temporal) into
categories that drive retry/propagation decisions:

* ``TRANSIENT`` — retry with backoff (timeout, connection, rate-limit)
* ``FATAL`` — fail fast, no retry (bad input, OOM, validation)
* ``UNKNOWN`` — retry once, then fail
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum

from polisyos.core.errors import ErrorCategory

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Well-known transient exception type names from optional dependencies.
# We match by class name to avoid importing ray / temporalio at module level.
# ---------------------------------------------------------------------------
_TRANSIENT_TYPE_NAMES: frozenset[str] = frozenset({
    # Ray
    "RayTaskError",
    "GetTimeoutError",
    "NodeDiedError",
    "WorkerCrashedError",
    "ObjectLostError",
    # Temporal
    "ApplicationError",  # when flagged as retryable
    "CancelledError",
    "RPCError",
    # Generic
    "ConnectionRefusedError",
    "ConnectionResetError",
    "ConnectionAbortedError",
    "BrokenPipeError",
})

_FATAL_TYPE_NAMES: frozenset[str] = frozenset({
    "ValidationError",
    "PydanticValidationError",
})


class RemoteErrorCategory(str, Enum):
    """Coarser-grained category for remote execution errors."""

    TRANSIENT = "transient"
    FATAL = "fatal"
    UNKNOWN = "unknown"


def classify_remote_error(exc: BaseException) -> RemoteErrorCategory:
    """Classify a remote execution error for retry/propagation decisions.

    Parameters
    ----------
    exc:
        The exception raised during remote node execution.

    Returns
    -------
    RemoteErrorCategory
        The classification guiding the caller's retry strategy.
    """
    # --- Inherently transient ---
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError)):
        return RemoteErrorCategory.TRANSIENT

    # --- Inherently fatal ---
    if isinstance(exc, (ValueError, TypeError, MemoryError, NotImplementedError)):
        return RemoteErrorCategory.FATAL

    # --- Name-based matching for optional-dep exceptions ---
    type_name = type(exc).__name__
    if type_name in _TRANSIENT_TYPE_NAMES:
        return RemoteErrorCategory.TRANSIENT
    if type_name in _FATAL_TYPE_NAMES:
        return RemoteErrorCategory.FATAL

    # --- Check the MRO for core ErrorCategory hints ---
    category = getattr(exc, "default_category", None)
    if category is ErrorCategory.TRANSIENT:
        return RemoteErrorCategory.TRANSIENT
    if category is ErrorCategory.FATAL:
        return RemoteErrorCategory.FATAL

    return RemoteErrorCategory.UNKNOWN


def should_retry(exc: BaseException, *, attempt: int = 0) -> bool:
    """Decide whether the caller should retry after *exc*.

    TRANSIENT errors always allow retry.  UNKNOWN errors allow a single
    retry (attempt 0).  FATAL errors never allow retry.

    Parameters
    ----------
    exc:
        The exception to evaluate.
    attempt:
        Zero-based retry attempt counter (0 = first failure).
    """
    category = classify_remote_error(exc)
    if category is RemoteErrorCategory.TRANSIENT:
        return True
    if category is RemoteErrorCategory.UNKNOWN:
        return attempt < 1
    return False
