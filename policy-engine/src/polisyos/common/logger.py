"""Provide module-scoped loggers enriched with current trace/span context.

This module is safe to import from library code. Process-wide sink/level wiring
is applied explicitly through `polisyos.common.config.apply_process_bootstrap()`
so importing a helper does not mutate global logging state. See
`docs/reference/logging.md` for the operator-facing contract.
"""

# Logger sinks are configured in config.py to avoid circular imports.
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from loguru import Record


class _BindableLoggerProtocol(Protocol):
    """Minimal dynamic methods used from non-stdlib logger handles."""

    def bind(self, **kwargs: object) -> object: ...

    def configure(
        self,
        *,
        patcher: Callable[[Record], None] | None = None,
    ) -> object: ...


try:
    from loguru import logger as _imported_loguru_logger

    _loguru_logger: object
    _USE_LOGURU = True
except ModuleNotFoundError:  # pragma: no cover
    _USE_LOGURU = False
    _loguru_logger = logging.getLogger("polisyos")
else:
    _loguru_logger = _imported_loguru_logger

_trace_context_configured = False
_trace_context_lock = threading.Lock()
_stdlib_filter_lock = threading.Lock()


class _CompatLogger:
    """Compatibility shim that accepts both Loguru and stdlib `%` formatting."""

    _STDLIB_KWARGS = frozenset({"exc_info", "stack_info", "stacklevel", "extra"})
    _STDLIB_RESERVED_EXTRA = frozenset(logging.makeLogRecord({}).__dict__) | frozenset(
        {"message", "asctime"}
    )

    def __init__(
        self,
        wrapped: object,
        *,
        bound_extra: Mapping[str, object] | None = None,
    ) -> None:
        self._wrapped = wrapped
        self._bound_extra = dict(bound_extra or {})

    def bind(self, **kwargs: object) -> _CompatLogger:
        if not isinstance(self._wrapped, logging.Logger):
            dynamic_logger = cast("_BindableLoggerProtocol", self._wrapped)
            bound = dynamic_logger.bind(**kwargs)
            return _CompatLogger(bound, bound_extra=self._bound_extra)
        merged = {**self._bound_extra, **kwargs}
        return _CompatLogger(self._wrapped, bound_extra=merged)

    def _normalize_message(
        self,
        message: object,
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> tuple[object, tuple[object, ...], dict[str, object]]:
        if not isinstance(message, str) or not args:
            return message, args, kwargs
        if "{" in message:
            return message, args, kwargs
        if "%" not in message:
            return message, args, kwargs
        try:
            return message % args, (), kwargs
        except Exception:
            return message, args, kwargs

    def _normalize_kwargs(self, kwargs: dict[str, object]) -> dict[str, object]:
        if not isinstance(self._wrapped, logging.Logger):
            return kwargs

        stdlib_kwargs = {key: value for key, value in kwargs.items() if key in self._STDLIB_KWARGS}
        extra = dict(self._bound_extra)
        user_extra = stdlib_kwargs.pop("extra", None)
        if isinstance(user_extra, dict):
            extra.update(user_extra)
        structured = {key: value for key, value in kwargs.items() if key not in self._STDLIB_KWARGS}
        extra.update(structured)
        extra = {
            key: value for key, value in extra.items() if key not in self._STDLIB_RESERVED_EXTRA
        }
        if extra:
            stdlib_kwargs["extra"] = extra
        return stdlib_kwargs

    def _call(
        self,
        method_name: str,
        message: object,
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> object:
        method = cast("Callable[..., object]", getattr(self._wrapped, method_name))
        if isinstance(self._wrapped, logging.Logger):
            return method(message, *args, **self._normalize_kwargs(kwargs))
        return method(message, *args, **kwargs)

    def debug(self, message: object, *args: object, **kwargs: object) -> object:
        message, args, kwargs = self._normalize_message(message, args, kwargs)
        return self._call("debug", message, args, kwargs)

    def info(self, message: object, *args: object, **kwargs: object) -> object:
        message, args, kwargs = self._normalize_message(message, args, kwargs)
        return self._call("info", message, args, kwargs)

    def warning(self, message: object, *args: object, **kwargs: object) -> object:
        message, args, kwargs = self._normalize_message(message, args, kwargs)
        return self._call("warning", message, args, kwargs)

    def error(self, message: object, *args: object, **kwargs: object) -> object:
        message, args, kwargs = self._normalize_message(message, args, kwargs)
        return self._call("error", message, args, kwargs)

    def exception(self, message: object, *args: object, **kwargs: object) -> object:
        message, args, kwargs = self._normalize_message(message, args, kwargs)
        return self._call("exception", message, args, kwargs)

    def critical(self, message: object, *args: object, **kwargs: object) -> object:
        message, args, kwargs = self._normalize_message(message, args, kwargs)
        return self._call("critical", message, args, kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)


logger = _CompatLogger(_loguru_logger)


def _get_trace_context() -> dict[str, str]:
    """
    Get current trace context for log enrichment at call time.

    Returns empty dict if OTel is not configured or no active span, which avoids
    reusing stale context between independent requests.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
            }
    except Exception:  # pragma: no cover - optional dependency
        return {}
    return {}


def _configure_loguru_trace_context() -> None:
    """Configure Loguru to include trace context in all logs."""
    if not _USE_LOGURU:
        return

    def trace_context_patcher(record: Record) -> None:
        ctx = _get_trace_context()
        record["extra"]["trace_id"] = ctx.get("trace_id", "-")
        record["extra"]["span_id"] = ctx.get("span_id", "-")

    if not isinstance(_loguru_logger, logging.Logger):
        dynamic_logger = cast("_BindableLoggerProtocol", _loguru_logger)
        dynamic_logger.configure(patcher=trace_context_patcher)


def _ensure_loguru_trace_context_configured() -> None:
    global _trace_context_configured
    if not _USE_LOGURU or _trace_context_configured:
        return
    with _trace_context_lock:
        if _trace_context_configured:
            return
        _configure_loguru_trace_context()
        _trace_context_configured = True


if _USE_LOGURU:
    _ensure_loguru_trace_context_configured()


class _TraceContextFilter(logging.Filter):
    """Logging filter that adds trace context to records."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = _get_trace_context()
        record.trace_id = ctx.get("trace_id", "-")
        record.span_id = ctx.get("span_id", "-")
        return True


def get_logger(module_name: str | None = None) -> _CompatLogger:
    """
    Return a logger bound to `module_name` and current trace context.

    Loguru is preferred when available; otherwise the standard-library logger is
    returned with a trace-context filter attached. This helper never bootstraps
    global sinks on its own.
    """
    global _trace_context_configured

    if _USE_LOGURU:
        _ensure_loguru_trace_context_configured()
        if isinstance(_loguru_logger, logging.Logger):  # pragma: no cover - defensive
            return _CompatLogger(_loguru_logger, bound_extra={"module": module_name or "polisyos"})
        dynamic_logger = cast("_BindableLoggerProtocol", _loguru_logger)
        return _CompatLogger(dynamic_logger.bind(module=module_name or "polisyos"))

    stdlib_logger = logging.getLogger(module_name)
    with _stdlib_filter_lock:
        if not any(isinstance(f, _TraceContextFilter) for f in stdlib_logger.filters):
            stdlib_logger.addFilter(_TraceContextFilter())
    bound_extra = {"module": module_name or "polisyos"}
    return _CompatLogger(stdlib_logger, bound_extra=bound_extra)
