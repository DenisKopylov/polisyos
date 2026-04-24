"""Public engine telemetry module API."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import nullcontext
from typing import Any

from polisyos.scientist.engine.protocol import NodeEvent
from polisyos.scientist.error_semantics import emit_degraded_path

NODE_SPAN_NAME = "scientist.node"
_TELEMETRY_RUNTIME_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _telemetry_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> None:
    emit_degraded_path(
        component="scientist.engine.telemetry",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
    )


def start_node_span(tracer: Any | None, attributes: dict[str, Any]) -> Any:
    """Start a node span if tracer is available; return a context manager."""
    if tracer is None:
        return nullcontext(None)
    try:
        return tracer.start_as_current_span(NODE_SPAN_NAME, attributes=attributes)
    except _TELEMETRY_RUNTIME_ERRORS as exc:
        _telemetry_degraded(
            operation="start_node_span",
            reason="telemetry_span_start_failed",
            exc=exc,
            details={"attribute_keys": sorted(attributes.keys())},
        )
        return nullcontext(None)


def set_span_attribute(span: Any, key: str, value: Any) -> None:
    """Set span attribute helper."""
    if span is None:
        return
    setter = getattr(span, "set_attribute", None)
    if callable(setter):
        try:
            setter(key, value)
        except _TELEMETRY_RUNTIME_ERRORS as exc:
            _telemetry_degraded(
                operation="set_span_attribute",
                reason="telemetry_set_attribute_failed",
                exc=exc,
                details={"key": key},
            )
            return


def add_span_events(span: Any, events: Iterable[NodeEvent]) -> None:
    """Add span events helper."""
    if span is None:
        return
    add_event = getattr(span, "add_event", None)
    if not callable(add_event):
        return
    for event in events:
        attrs: dict[str, Any] = dict(event.attrs)
        if event.code:
            attrs["code"] = event.code
        attrs["level"] = event.level
        try:
            add_event(event.message, attributes=attrs)
        except _TELEMETRY_RUNTIME_ERRORS as exc:
            _telemetry_degraded(
                operation="add_span_events",
                reason="telemetry_add_event_failed",
                exc=exc,
                details={"event_code": event.code, "event_level": event.level},
            )
            continue
