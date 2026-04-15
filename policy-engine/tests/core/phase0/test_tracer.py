"""Tests for the PolicyOSTracer singleton and core tracing behaviors."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, ALWAYS_ON, Decision
from opentelemetry.trace import SpanKind

from polisyos.core.observability import get_tracer
from polisyos.core.observability.config import OTelConfig
from polisyos.core.observability.tracer import ErrorAwareSampler, PolicyOSTracer


class TestPolicyOSTracer:
    """Tests for the PolicyOSTracer singleton."""

    def test_singleton_pattern(self, reset_singleton):
        """Tracer should be a singleton."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()
        assert tracer1 is tracer2

    def test_lazy_initialization(self, reset_singleton):
        """Tracer should not initialize until first use."""
        from polisyos.core.observability.tracer import PolicyOSTracer

        # Before first use
        assert not PolicyOSTracer._initialized

        # Trigger initialization
        tracer = get_tracer()
        _ = tracer.tracer  # Access property to force init

        # After first use
        assert PolicyOSTracer._initialized

    def test_span_creation(self, test_tracer_provider, in_memory_exporter):
        """Should create spans with correct attributes."""
        tracer = get_tracer()

        with tracer.start_as_current_span(
            "test_operation",
            attributes={"polisyos.phase": "EXECUTE"},
        ) as span:
            span.set_attribute("polisyos.run_id", "R_test123")

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1

        test_span = spans[0]
        assert test_span.name == "test_operation"
        assert test_span.attributes["polisyos.phase"] == "EXECUTE"
        assert test_span.attributes["polisyos.run_id"] == "R_test123"

    def test_nested_spans(self, test_tracer_provider, in_memory_exporter):
        """Child spans should be linked to parent."""
        tracer = get_tracer()

        with tracer.start_as_current_span("parent"):
            with tracer.start_as_current_span("child"):
                pass

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 2

        child = next(s for s in spans if s.name == "child")
        parent = next(s for s in spans if s.name == "parent")

        # Child should reference parent
        assert child.parent.span_id == parent.context.span_id

    def test_exception_recording(self, test_tracer_provider, in_memory_exporter):
        """Exceptions should be recorded on spans."""
        tracer = get_tracer()

        with pytest.raises(ValueError):
            with tracer.start_as_current_span("failing_operation"):
                raise ValueError("Test error")

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.status.status_code.name == "ERROR"
        assert len(span.events) == 1  # Exception event
        assert span.events[0].name == "exception"

    def test_trace_id_extraction(self, test_tracer_provider):
        """Should extract trace_id and span_id correctly."""
        tracer = get_tracer()

        # No active span
        assert tracer.get_current_trace_id() is None

        with tracer.start_as_current_span("test"):
            trace_id = tracer.get_current_trace_id()
            span_id = tracer.get_current_span_id()

            assert trace_id is not None
            assert len(trace_id) == 32  # 128-bit hex
            assert span_id is not None
            assert len(span_id) == 16  # 64-bit hex


class TestSamplerBehavior:
    """Tests for sampling configuration and error-aware behavior."""

    def test_error_aware_sampler_samples_error(self):
        sampler = ErrorAwareSampler(0.0)
        result = sampler.should_sample(
            None,
            trace_id=1,
            name="error_span",
            kind=SpanKind.INTERNAL,
            attributes={"error": "true"},
            links=[],
        )
        assert result.decision is Decision.RECORD_AND_SAMPLE

    def test_create_sampler_respects_ratio_bounds(self, reset_singleton):
        tracer = PolicyOSTracer()

        tracer._config = OTelConfig(sampling_ratio=1.0, always_sample_errors=True)
        sampler = tracer._create_sampler()
        assert sampler is ALWAYS_ON

        tracer._config = OTelConfig(sampling_ratio=0.0, always_sample_errors=True)
        sampler = tracer._create_sampler()
        assert sampler is ALWAYS_OFF

    def test_parent_based_sampler_respects_error_override(self, reset_singleton):
        tracer = PolicyOSTracer()
        tracer._config = OTelConfig(sampling_ratio=0.01, always_sample_errors=True)
        sampler = tracer._create_sampler()

        result = sampler.should_sample(
            None,
            trace_id=42,
            name="error_span",
            kind=SpanKind.INTERNAL,
            attributes={"error": "true"},
            links=[],
        )
        assert result.decision is Decision.RECORD_AND_SAMPLE

    def test_get_tracer_is_thread_safe_singleton(self, reset_singleton):
        with ThreadPoolExecutor(max_workers=8) as pool:
            instances = list(pool.map(lambda _: get_tracer(), range(32)))
        assert len({id(instance) for instance in instances}) == 1
