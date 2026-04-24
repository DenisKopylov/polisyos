"""
Structured Logging with Trace Context Injection.

Provides a LoggingHandler that automatically injects trace_id and span_id
into log records, enabling correlation between logs and traces.

Integration with existing logger.py:
- Wraps existing Loguru/standard library logger
- Adds trace context as structured fields
- Maintains backward compatibility

Usage:
    from polisyos.core.observability.logs import configure_otel_logging_handler

    configure_otel_logging_handler()  # Call once at startup

    # Existing logger calls now include trace context
    from polisyos.common.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Processing policy")  # Automatically includes trace_id
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from contextlib import suppress

from opentelemetry import trace


class TraceContextFilter(logging.Filter):
    """
    Logging filter that adds trace context to log records.

    Adds trace_id and span_id fields to every log record,
    enabling correlation with distributed traces.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add trace context to the log record."""
        span = trace.get_current_span()
        ctx = span.get_span_context()

        if ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
            record.trace_sampled = ctx.trace_flags.sampled
        else:
            record.trace_id = None
            record.span_id = None
            record.trace_sampled = False

        return True


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging with trace context.

    Output format compatible with log aggregators (ELK, Loki, etc.)
    """

    def __init__(self) -> None:
        super().__init__()
        # Lazy import to avoid circular dependency
        self._json_dumps: Callable[..., str] | None = None

    def _get_json_dumps(self) -> Callable[..., str]:
        if self._json_dumps is None:
            import json

            self._json_dumps = json.dumps
        return self._json_dumps

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with trace context."""
        json_dumps = self._get_json_dumps()

        log_dict = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add trace context if available
        trace_id = getattr(record, "trace_id", None)
        span_id = getattr(record, "span_id", None)

        if trace_id:
            log_dict["trace_id"] = trace_id
        if span_id:
            log_dict["span_id"] = span_id

        # Add exception info if present
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "trace_id",
                "span_id",
                "trace_sampled",
                "message",
            ):
                with suppress(TypeError, ValueError):
                    log_dict[key] = value

        return json_dumps(log_dict, default=str)


def configure_otel_logging_handler(
    logger: logging.Logger | None = None,
    level: int = logging.INFO,
    structured: bool = True,
) -> None:
    """
    Add trace context injection to a logger.

    Args:
        logger: Logger to configure (defaults to root logger)
        level: Minimum log level
        structured: If True, use JSON formatting
    """
    if logger is None:
        logger = logging.getLogger()

    # Add trace context filter
    trace_filter = TraceContextFilter()

    # Create handler with formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.addFilter(trace_filter)

    if structured:
        handler.setFormatter(StructuredFormatter())
    else:
        # Traditional format with trace context
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s "
                "[trace_id=%(trace_id)s span_id=%(span_id)s] "
                "%(message)s"
            )
        )

    logger.addHandler(handler)
    logger.setLevel(level)


def get_trace_context_dict() -> dict[str, str | None]:
    """
    Get current trace context as a dictionary.

    Useful for passing context to external systems or adding to payloads.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()

    if ctx.is_valid:
        return {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
        }
    return {"trace_id": None, "span_id": None}
