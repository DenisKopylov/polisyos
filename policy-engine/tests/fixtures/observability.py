from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _reset_observability_singletons() -> None:
    import polisyos.core.observability.metrics_parts as metrics_parts
    import polisyos.core.observability.tracer as tracer_module
    from polisyos.core.observability._metrics_registry_base import _MetricsRegistryBase
    from polisyos.core.observability.metrics import MetricsRegistry
    from polisyos.core.observability.tracer import PolicyOSTracer

    PolicyOSTracer._instance = None
    PolicyOSTracer._initialized = False
    _MetricsRegistryBase._instance = None
    _MetricsRegistryBase._initialized = False
    MetricsRegistry._instance = None
    MetricsRegistry._initialized = False

    metrics_parts._metrics_registry = None
    tracer_module._tracer_instance = None


@pytest.fixture(scope="session")
def _otel_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()

    if provider.__class__.__name__ == "ProxyTracerProvider":
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    elif isinstance(provider, TracerProvider):
        provider.add_span_processor(SimpleSpanProcessor(exporter))

    return exporter


@pytest.fixture()
def in_memory_exporter(_otel_exporter: InMemorySpanExporter):
    _otel_exporter.clear()
    _reset_observability_singletons()

    yield _otel_exporter

    _otel_exporter.clear()
    _reset_observability_singletons()


@pytest.fixture()
def test_tracer_provider(in_memory_exporter: InMemorySpanExporter):
    return trace.get_tracer_provider()


@pytest.fixture()
def test_tracer(test_tracer_provider):
    return trace.get_tracer("test.polisyos")


@pytest.fixture()
def reset_singleton():
    from polisyos.core.observability.tracer import PolicyOSTracer

    original_instance = PolicyOSTracer._instance
    original_initialized = PolicyOSTracer._initialized

    PolicyOSTracer._instance = None
    PolicyOSTracer._initialized = False

    yield

    PolicyOSTracer._instance = original_instance
    PolicyOSTracer._initialized = original_initialized
