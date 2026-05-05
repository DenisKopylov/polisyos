"""Tests for cross-thread/service context propagation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar

from opentelemetry.context import attach, detach
from polisyos.core.observability import (
    TracedExecutorWrapper,
    extract_headers,
    get_tracer,
    inject_headers,
    with_context_vars,
    with_trace_context,
)


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
        """with_trace_context should not freeze one stale parent trace forever."""
        tracer = get_tracer()
        results: list[str | None] = []

        def capture_trace_id() -> None:
            results.append(tracer.get_current_trace_id())

        wrapped = with_trace_context(capture_trace_id)

        with tracer.start_as_current_span("parent-one"):
            first_trace_id = tracer.get_current_trace_id()
            wrapped()

        with tracer.start_as_current_span("parent-two"):
            second_trace_id = tracer.get_current_trace_id()
            wrapped()

        assert results == [first_trace_id, second_trace_id]
        assert first_trace_id != second_trace_id

    def test_with_context_vars_wrapper_captures_each_invocation(self) -> None:
        request_var: ContextVar[str] = ContextVar("request_var", default="unset")
        seen: list[str] = []

        def capture_value() -> None:
            seen.append(request_var.get())

        wrapped = with_context_vars(capture_value)

        request_var.set("request-a")
        wrapped()
        request_var.set("request-b")
        wrapped()

        assert seen == ["request-a", "request-b"]

    def test_traced_executor_wrapper_preserves_trace_and_contextvars(self, test_tracer_provider):
        tracer = get_tracer()
        request_var: ContextVar[str] = ContextVar("request_var_executor", default="unset")
        results: list[tuple[str | None, str]] = []

        def capture() -> tuple[str | None, str]:
            current = (tracer.get_current_trace_id(), request_var.get())
            results.append(current)
            return current

        with ThreadPoolExecutor(max_workers=1) as executor:
            traced = TracedExecutorWrapper(executor)

            with tracer.start_as_current_span("parent-one"):
                trace_one = tracer.get_current_trace_id()
                request_var.set("request-a")
                assert traced.submit(capture).result() == (trace_one, "request-a")

            with tracer.start_as_current_span("parent-two"):
                trace_two = tracer.get_current_trace_id()
                request_var.set("request-b")
                assert traced.submit(capture).result() == (trace_two, "request-b")

        assert results == [(trace_one, "request-a"), (trace_two, "request-b")]
