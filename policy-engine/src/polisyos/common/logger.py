"""Provide module-scoped loggers enriched with current trace/span context.

This module is safe to import from library code. Global sink/level wiring lives
in `polisyos.common.config` to avoid circular imports and to keep process-wide
logging configuration under entrypoint control.
"""
# Logger sinks are configured in config.py to avoid circular imports.
from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from loguru import logger as _loguru_logger  # type: ignore

    _USE_LOGURU = True
except ModuleNotFoundError:  # pragma: no cover
    import logging

    _USE_LOGURU = False
    _loguru_logger = logging.getLogger("polisyos")  # type: ignore

_trace_context_configured = False
logger = _loguru_logger


def _get_trace_context() -> dict[str, Any]:
    """
    Get current trace context for log enrichment.

    Returns empty dict if OTel is not configured or no active span.
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

    def trace_context_patcher(record: dict) -> None:
        ctx = _get_trace_context()
        record["extra"]["trace_id"] = ctx.get("trace_id", "-")
        record["extra"]["span_id"] = ctx.get("span_id", "-")

    _loguru_logger.configure(patcher=trace_context_patcher)


if _USE_LOGURU:
    _configure_loguru_trace_context()
    _trace_context_configured = True


class _TraceContextFilter(logging.Filter):
    """Logging filter that adds trace context to records."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = _get_trace_context()
        record.trace_id = ctx.get("trace_id", "-")
        record.span_id = ctx.get("span_id", "-")
        return True


def get_logger(module_name: Optional[str] = None):
    """
    Return a logger bound to `module_name` and current trace context.

    Loguru is preferred when available; otherwise the standard-library logger is
    returned with a trace-context filter attached.
    """
    global _trace_context_configured

    if _USE_LOGURU:
        if not _trace_context_configured:
            _configure_loguru_trace_context()
            _trace_context_configured = True
        return _loguru_logger.bind(module=module_name or "polisyos")

    logger = logging.getLogger(module_name)
    if not any(isinstance(f, _TraceContextFilter) for f in logger.filters):
        logger.addFilter(_TraceContextFilter())
    return logger
