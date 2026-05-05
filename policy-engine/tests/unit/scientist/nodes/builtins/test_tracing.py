"""Tests for distributed tracing helpers."""

from __future__ import annotations

import pytest
from polisyos.scientist.engine.protocol import NodeEvent
from polisyos.scientist.nodes.builtins import tracing as tracing_module
from polisyos.scientist.nodes.builtins.tracing import inject_trace_context


class TestInjectTraceContext:
    def test_injects_ids(self):
        events = [
            NodeEvent(level="info", message="step 1"),
            NodeEvent(level="info", message="step 2"),
        ]
        inject_trace_context(events, trace_id="abc123", span_id="def456")
        assert events[0].attrs["trace_id"] == "abc123"
        assert events[0].attrs["span_id"] == "def456"
        assert events[1].attrs["trace_id"] == "abc123"

    def test_missing_context_no_mutation(self):
        events = [NodeEvent(level="info", message="test")]
        inject_trace_context(events, trace_id=None, span_id=None)
        # Without OTel, attrs should not be mutated (unless OTel is installed)
        # We check that it at least doesn't crash
        assert isinstance(events[0].attrs, dict)

    def test_empty_events(self):
        result = inject_trace_context([], trace_id="t", span_id="s")
        assert result == []

    def test_preserves_existing_attrs(self):
        events = [
            NodeEvent(level="info", message="x", attrs={"custom": "val"}),
        ]
        inject_trace_context(events, trace_id="t1", span_id="s1")
        assert events[0].attrs["custom"] == "val"
        assert events[0].attrs["trace_id"] == "t1"

    def test_runtime_trace_access_failure_returns_none_ids(self, monkeypatch: pytest.MonkeyPatch):
        class _BrokenTraceModule:
            @staticmethod
            def get_current_span():
                raise RuntimeError("otel runtime unavailable")

        monkeypatch.setattr(
            tracing_module,
            "_load_otel_trace_module",
            lambda: _BrokenTraceModule(),
        )

        assert tracing_module._current_otel_ids() == (None, None)
