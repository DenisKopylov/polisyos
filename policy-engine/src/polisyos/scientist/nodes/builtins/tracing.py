"""Distributed tracing helpers for builtin nodes."""

from __future__ import annotations

from typing import Any

from polisyos.scientist.engine.protocol import NodeEvent


def inject_trace_context(
    events: list[NodeEvent],
    *,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> list[NodeEvent]:
    """Add ``trace_id`` and ``span_id`` to each event's ``attrs``.

    If *trace_id*/*span_id* are not provided, attempts to extract them
    from the current OpenTelemetry span (if available).

    Returns the list unchanged (mutated in place) for convenience.
    """
    if trace_id is None or span_id is None:
        detected_trace, detected_span = _current_otel_ids()
        trace_id = trace_id or detected_trace
        span_id = span_id or detected_span

    if not trace_id and not span_id:
        return events

    for event in events:
        if trace_id:
            event.attrs["trace_id"] = trace_id
        if span_id:
            event.attrs["span_id"] = span_id

    return events


def _current_otel_ids() -> tuple[str | None, str | None]:
    """Best-effort extraction of trace/span IDs from OpenTelemetry."""
    try:
        from opentelemetry import trace  # type: ignore[import-untyped]

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            tid = format(ctx.trace_id, "032x")
            sid = format(ctx.span_id, "016x")
            return tid, sid
    except Exception:  # noqa: BLE001
        pass
    return None, None


__all__ = [
    "inject_trace_context",
]
