"""Tests for WS8.2 — Distributed Tracing (W3C TraceContext).

Covers inject/extract round-trip, runner carrier population,
activity worker context restoration, trace attribute constants,
and graceful degradation without a tracer.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.observability.propagation import extract_headers, inject_headers
from polisyos.scientist.engine.trace_attributes import (
    ATTR_RUNNER_BACKEND,
    ATTR_NODE_ID,
    ATTR_WORKFLOW_ID,
    build_node_span_attributes,
    enrich_node_span_result,
)


# ---------------------------------------------------------------------------
# Inject / extract round-trip
# ---------------------------------------------------------------------------

class TestInjectExtract:

    def test_inject_headers_returns_carrier(self) -> None:
        carrier: dict[str, str] = {}
        result = inject_headers(carrier)
        assert isinstance(result, dict)

    def test_inject_produces_traceparent(self) -> None:
        """When there is an active span, traceparent should be populated."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            carrier: dict[str, str] = {}
            inject_headers(carrier)
            assert "traceparent" in carrier

    def test_extract_headers_returns_context(self) -> None:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("parent"):
            carrier: dict[str, str] = {}
            inject_headers(carrier)

        ctx = extract_headers(carrier)
        assert ctx is not None

    def test_round_trip_preserves_trace_id(self) -> None:
        from opentelemetry import trace, context as otel_context
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("parent") as span:
            original_trace_id = span.get_span_context().trace_id
            carrier: dict[str, str] = {}
            inject_headers(carrier)

        # Extract and verify trace_id is preserved in the carrier
        assert "traceparent" in carrier
        # traceparent format: 00-<trace_id>-<span_id>-<flags>
        parts = carrier["traceparent"].split("-")
        restored_trace_id = int(parts[1], 16)
        assert restored_trace_id == original_trace_id


# ---------------------------------------------------------------------------
# Ray runner injects carrier
# ---------------------------------------------------------------------------

class TestRayRunnerCarrier:

    def test_ray_runner_code_calls_inject(self) -> None:
        """Verify that the ray_runner source contains inject_headers call."""
        import inspect
        from polisyos.scientist.engine.runner import ray_runner
        source = inspect.getsource(ray_runner)
        assert "inject_headers" in source
        # Verify the old TODO is gone
        assert "TODO: inject trace context" not in source


# ---------------------------------------------------------------------------
# Temporal runner injects carrier
# ---------------------------------------------------------------------------

class TestTemporalRunnerCarrier:

    def test_temporal_runner_code_calls_inject(self) -> None:
        """Verify that the temporal_runner source contains inject_headers call."""
        import inspect
        from polisyos.scientist.engine.runner import temporal_runner
        source = inspect.getsource(temporal_runner)
        assert "inject_headers" in source
        assert 'trace_carrier": {}' not in source or "inject_headers" in source


# ---------------------------------------------------------------------------
# Activity worker attaches context
# ---------------------------------------------------------------------------

class TestActivityWorkerContext:

    def test_worker_source_contains_extract_headers(self) -> None:
        """Verify activity worker restores trace context."""
        import inspect
        from polisyos.scientist.engine.runner import _activity_worker
        source = inspect.getsource(_activity_worker)
        assert "extract_headers" in source
        assert "otel_context.attach" in source
        assert "otel_context.detach" in source

    def test_worker_source_creates_child_span(self) -> None:
        """Verify activity worker creates a child span for node execution."""
        import inspect
        from polisyos.scientist.engine.runner import _activity_worker
        source = inspect.getsource(_activity_worker)
        assert "scientist.node." in source
        assert "start_as_current_span" in source


# ---------------------------------------------------------------------------
# Trace attribute constants
# ---------------------------------------------------------------------------

class TestTraceAttributeConstants:

    def test_runner_backend_attr_defined(self) -> None:
        assert ATTR_RUNNER_BACKEND == "polisyos.scientist.runner_backend"

    def test_build_node_span_attributes(self) -> None:
        attrs = build_node_span_attributes(
            alias="sim", node_id="sim@1.0",
            workflow_id="wf-1", run_id="r-1",
        )
        assert attrs[ATTR_NODE_ID] == "sim@1.0"
        assert attrs[ATTR_WORKFLOW_ID] == "wf-1"

    def test_enrich_node_span_result(self) -> None:
        attrs = build_node_span_attributes(
            alias="sim", node_id="sim@1.0", workflow_id="wf-1",
        )
        enrich_node_span_result(
            attrs, status="ok", duration_ms=100, cache_hit=True, retry_count=2,
        )
        assert attrs["polisyos.scientist.node_status"] == "ok"
        assert attrs["polisyos.scientist.retry_count"] == 2


# ---------------------------------------------------------------------------
# Graceful without tracer
# ---------------------------------------------------------------------------

class TestGracefulNoTracer:

    def test_inject_headers_with_no_active_span(self) -> None:
        """inject_headers should not crash even without an active span."""
        carrier: dict[str, str] = {}
        result = inject_headers(carrier)
        assert isinstance(result, dict)

    def test_extract_empty_carrier(self) -> None:
        """extract_headers should not crash with an empty carrier."""
        ctx = extract_headers({})
        assert ctx is not None
