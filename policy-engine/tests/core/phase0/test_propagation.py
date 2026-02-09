"""Tests for cross-thread/service context propagation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from opentelemetry.context import attach, detach

from polisyos.core.observability import extract_headers, get_tracer, inject_headers, with_trace_context


class TestContextPropagation:
    """Tests for context propagation helpers."""

    def test_inject_extract_headers(self, test_tracer_provider):
        """Context should round-trip through headers."""
        tracer = get_tracer()

        with tracer.start_as_current_span("parent"):
            original_trace_id = tracer.get_current_trace_id()

            # Inject into headers
            headers: dict[str, str] = {}
            inject_headers(headers)

            assert "traceparent" in headers

        # Extract in "different service"
        ctx = extract_headers(headers)
        token = attach(ctx)

        try:
            with tracer.start_as_current_span("child"):
                child_trace_id = tracer.get_current_trace_id()
                # Same trace, different span
                assert child_trace_id == original_trace_id
        finally:
            detach(token)

    def test_with_trace_context_wrapper(self, test_tracer_provider, in_memory_exporter):
        """with_trace_context should preserve context across threads."""
        tracer = get_tracer()
        results: list[str | None] = []

        def capture_trace_id() -> None:
            results.append(tracer.get_current_trace_id())

        with tracer.start_as_current_span("parent"):
            parent_trace_id = tracer.get_current_trace_id()
            wrapped = with_trace_context(capture_trace_id)

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(wrapped)
                future.result()

        assert len(results) == 1
        assert results[0] == parent_trace_id
