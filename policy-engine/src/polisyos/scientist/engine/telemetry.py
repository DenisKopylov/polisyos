"""Public engine telemetry module API."""
from __future__ import annotations

from contextlib import nullcontext
from typing import Any, Iterable

from polisyos.scientist.engine.protocol import NodeEvent

NODE_SPAN_NAME = "scientist.node"


def start_node_span(tracer: Any | None, attributes: dict[str, Any]) -> Any:
    """Start a node span if tracer is available; return a context manager."""
    if tracer is None:
        return nullcontext(None)
    try:
        return tracer.start_as_current_span(NODE_SPAN_NAME, attributes=attributes)
    except Exception:  # noqa: BLE001 - telemetry must never crash the pipeline
        return nullcontext(None)


def set_span_attribute(span: Any, key: str, value: Any) -> None:
    """Set span attribute helper."""
    if span is None:
        return
    setter = getattr(span, "set_attribute", None)
    if callable(setter):
        try:
            setter(key, value)
        except Exception:  # noqa: BLE001 - telemetry must never crash the pipeline
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
        except Exception:  # noqa: BLE001 - telemetry must never crash the pipeline
            continue
