"""
Foundry Methods — Structured Logging Helpers.

Returns a structlog logger when structlog is installed, otherwise falls back
to a thin wrapper around the stdlib ``logging`` module so that callers never
need to guard against ImportError.

Usage::

    from polisyos.foundry.methods._logging import get_foundry_logger

    _log = get_foundry_logger(__name__)

    _log.info("method_dispatch_start", fqn="causal.did.standard@1.0.0", backend="numpy")
    _log.debug("chain_complete", total_nodes=3, elapsed_ms=42.1)
    _log.warning("circuit_opened", backend="jax", failure_count=5)
    _log.error("method_dispatch_error", fqn="...", exc=repr(exc))
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Protocol — common interface for structlog and stdlib loggers
# ---------------------------------------------------------------------------


@runtime_checkable
class FoundryLogger(Protocol):
    """Minimal structured logger interface used by Foundry backends."""

    def debug(self, event: str, **kwargs: Any) -> None: ...
    def info(self, event: str, **kwargs: Any) -> None: ...
    def warning(self, event: str, **kwargs: Any) -> None: ...
    def error(self, event: str, **kwargs: Any) -> None: ...


# ---------------------------------------------------------------------------
# Stdlib shim — converts keyword kwargs to a single formatted message
# ---------------------------------------------------------------------------


class _StdlibLoggerShim:
    """
    Wraps a stdlib ``logging.Logger`` with the structlog-compatible interface.

    Key-value pairs are appended to the log message as ``key=value`` tokens.
    """

    __slots__ = ("_logger",)

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _format(self, event: str, **kwargs: Any) -> str:
        if not kwargs:
            return event
        parts = " ".join(f"{k}={v!r}" for k, v in kwargs.items())
        return f"{event} {parts}"

    def debug(self, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(self._format(event, **kwargs))

    def info(self, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(logging.INFO):
            self._logger.info(self._format(event, **kwargs))

    def warning(self, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(logging.WARNING):
            self._logger.warning(self._format(event, **kwargs))

    def error(self, event: str, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(logging.ERROR):
            self._logger.error(self._format(event, **kwargs))


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

try:
    import structlog as _structlog

    _STRUCTLOG_AVAILABLE = True
except ImportError:
    _STRUCTLOG_AVAILABLE = False


class _StructlogAdapter:
    """Thin wrapper that satisfies the FoundryLogger Protocol at runtime."""

    __slots__ = ("_proxy",)

    def __init__(self, proxy: Any) -> None:
        self._proxy = proxy

    def debug(self, event: str, **kwargs: Any) -> None:
        self._proxy.debug(event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._proxy.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._proxy.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._proxy.error(event, **kwargs)


def get_foundry_logger(name: str) -> FoundryLogger:
    """
    Return a structured logger for the given *name*.

    When ``structlog`` is installed, returns a ``structlog`` bound logger.
    Otherwise returns a stdlib shim with the same interface.

    Args:
        name: Logger name (typically ``__name__`` of the calling module).

    Returns:
        A :class:`FoundryLogger`-compatible logger.
    """
    if _STRUCTLOG_AVAILABLE:
        return _StructlogAdapter(_structlog.get_logger(name))
    return _StdlibLoggerShim(name)


def _infer_n_obs(state: Any) -> int | None:
    """
    Infer the number of observations from a state dict.

    Tries common keys (``outcome``, ``features``, ``X``, ``endog``).
    Returns ``None`` if inference is not possible.
    """
    if not isinstance(state, dict):
        return None
    for key in ("outcome", "features", "X", "endog", "target", "y"):
        val = state.get(key)
        if val is not None:
            try:
                return len(val)  # type: ignore[arg-type]
            except (TypeError, AttributeError):
                pass
    return None
