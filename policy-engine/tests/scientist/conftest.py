from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture()
def in_memory_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Reset observability singletons to pick up test provider.
    from polisyos.core.observability.tracer import PolicyOSTracer
    from polisyos.core.observability.metrics import MetricsRegistry

    PolicyOSTracer._instance = None
    PolicyOSTracer._initialized = False
    MetricsRegistry._instance = None
    MetricsRegistry._initialized = False

    yield exporter

    exporter.clear()
