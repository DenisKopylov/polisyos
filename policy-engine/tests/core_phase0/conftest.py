from __future__ import annotations

import platform
import sys
from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from polisyos.core.artifacts.manifest import EnvInfo, GitInfo, ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS


@pytest.fixture()
def cas_root(tmp_path: Path) -> Path:
    return tmp_path / ".polisyos"


@pytest.fixture()
def store(cas_root: Path) -> FileSystemCAS:
    return FileSystemCAS(cas_root)


@pytest.fixture()
def producer() -> ProducerInfo:
    return ProducerInfo(
        component="tests.phase0",
        version="0.0.0",
        git=GitInfo(commit="0000000", dirty=False),
    )


@pytest.fixture()
def env_info() -> EnvInfo:
    return EnvInfo(
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=platform.platform(),
        deps_lock_hash="sha256:" + "0" * 64,
    )


@pytest.fixture(scope="session")
def _otel_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()

    if provider.__class__.__name__ == "ProxyTracerProvider":
        provider = TracerProvider()
        processor = SimpleSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
    elif isinstance(provider, TracerProvider):
        provider.add_span_processor(SimpleSpanProcessor(exporter))

    return exporter


@pytest.fixture()
def in_memory_exporter(_otel_exporter: InMemorySpanExporter) -> InMemorySpanExporter:
    _otel_exporter.clear()
    return _otel_exporter


@pytest.fixture()
def test_tracer_provider(in_memory_exporter: InMemorySpanExporter):
    return trace.get_tracer_provider()


@pytest.fixture()
def test_tracer(test_tracer_provider):
    return trace.get_tracer("test.polisyos")


@pytest.fixture()
def reset_singleton():
    """Reset PolicyOSTracer singleton state between tests."""
    from polisyos.core.observability.tracer import PolicyOSTracer

    # Store original state
    original_instance = PolicyOSTracer._instance
    original_initialized = PolicyOSTracer._initialized

    # Reset for test
    PolicyOSTracer._instance = None
    PolicyOSTracer._initialized = False

    yield

    # Restore original state
    PolicyOSTracer._instance = original_instance
    PolicyOSTracer._initialized = original_initialized
