"""
PolicyOS Observability Module — Production-grade telemetry.
"""

from __future__ import annotations

from .config import OTelConfig, get_default_config

try:
    from .decorators import traced, traced_method
    from .logs import (
        TraceContextFilter,
        StructuredFormatter,
        configure_otel_logging_handler,
        get_trace_context_dict,
    )
    from .metrics import MetricsRegistry, get_metrics
    from .propagation import (
        TracedExecutorWrapper,
        extract_headers,
        inject_headers,
        propagate_context,
        with_trace_context,
    )
    from .tracer import PolicyOSTracer, get_current_trace_context, get_tracer
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class _NoopMetric:
        def add(self, value, attrs=None) -> None:
            return None

        def record(self, value, attrs=None) -> None:
            return None

    class MetricsRegistry:  # type: ignore[override]
        def __getattr__(self, name: str):
            return _NoopMetric()

    class _NoopSpan:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def set_attribute(self, key, value) -> None:
            return None

        def set_status(self, status) -> None:
            return None

        def record_exception(self, exc) -> None:
            return None

    class PolicyOSTracer:  # type: ignore[override]
        def start_as_current_span(self, name: str, attributes=None):
            return _NoopSpan()

    def get_tracer() -> PolicyOSTracer:
        return PolicyOSTracer()

    _METRICS = MetricsRegistry()

    def get_metrics() -> MetricsRegistry:
        return _METRICS

    def traced(*args, **kwargs):
        def _decorator(func):
            return func

        return _decorator

    def traced_method(*args, **kwargs):
        def _decorator(func):
            return func

        return _decorator

    def configure_otel_logging_handler(*args, **kwargs) -> None:
        return None

    def get_trace_context_dict() -> dict[str, str]:
        return {}

    class StructuredFormatter:  # type: ignore[override]
        pass

    class TraceContextFilter:  # type: ignore[override]
        pass

    def inject_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
        return headers or {}

    def extract_headers(headers: dict[str, str] | None = None):
        return None

    def propagate_context(*args, **kwargs):
        return None

    def with_trace_context(*args, **kwargs):
        def _decorator(func):
            return func

        return _decorator

    class TracedExecutorWrapper:  # type: ignore[override]
        def __init__(self, executor):
            self._executor = executor

        def submit(self, fn, *args, **kwargs):
            return self._executor.submit(fn, *args, **kwargs)

    def get_current_trace_context() -> dict[str, str]:
        return {}


__all__ = [
    "OTelConfig",
    "get_default_config",
    "get_tracer",
    "get_current_trace_context",
    "PolicyOSTracer",
    "get_metrics",
    "MetricsRegistry",
    "traced",
    "traced_method",
    "configure_otel_logging_handler",
    "get_trace_context_dict",
    "StructuredFormatter",
    "TraceContextFilter",
    "inject_headers",
    "extract_headers",
    "propagate_context",
    "with_trace_context",
    "TracedExecutorWrapper",
]
