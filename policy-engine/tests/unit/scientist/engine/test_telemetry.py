from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.engine.protocol import NodeEvent
from polisyos.scientist.engine.telemetry import (
    add_span_events,
    set_span_attribute,
    start_node_span,
)


def test_start_node_span_runtime_error_degrades() -> None:
    tracer = MagicMock()
    tracer.start_as_current_span.side_effect = RuntimeError("otel down")

    with patch(
        "polisyos.scientist.engine.telemetry.emit_degraded_path",
    ) as degraded:
        ctx = start_node_span(tracer, {"alias": "node_a"})

    assert hasattr(ctx, "__enter__")
    degraded.assert_called_once()


def test_set_span_attribute_runtime_error_degrades() -> None:
    span = MagicMock()
    span.set_attribute.side_effect = RuntimeError("set failed")

    with patch(
        "polisyos.scientist.engine.telemetry.emit_degraded_path",
    ) as degraded:
        set_span_attribute(span, "status", "ok")

    degraded.assert_called_once()


def test_add_span_events_runtime_error_degrades() -> None:
    span = MagicMock()
    span.add_event.side_effect = RuntimeError("event failed")
    event = NodeEvent(level="warn", message="degraded", code="node.warn", attrs={"a": 1})

    with patch(
        "polisyos.scientist.engine.telemetry.emit_degraded_path",
    ) as degraded:
        add_span_events(span, [event])

    degraded.assert_called_once()
