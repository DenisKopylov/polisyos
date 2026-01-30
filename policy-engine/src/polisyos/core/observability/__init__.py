"""
PolicyOS Observability Module — Production-grade telemetry.

This module provides unified observability capabilities:
- Distributed tracing with OpenTelemetry
- Prometheus-compatible metrics
- Structured logging with trace correlation

Quick Start:
    from polisyos.core.observability import (
        get_tracer,
        get_metrics,
        traced,
        configure_otel_logging_handler,
    )

    # Configure logging with trace context
    configure_otel_logging_handler()

    # Use the @traced decorator
    @traced(phase="EXECUTE", node="run_sim")
    def run_simulation(config: SimConfig) -> SimResult:
        metrics = get_metrics()
        with metrics.time_simulation({"node": "run_sim"}):
            return execute(config)

Environment Variables:
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint
    POLISYOS_OTEL_ENABLED: Enable/disable OTel (default: true)
    POLISYOS_METRICS_PORT: Prometheus metrics port (default: 9464)
    POLISYOS_OTEL_CONSOLE_EXPORT: Enable console export for debugging
    POLISYOS_TRACE_SAMPLING_RATIO: Trace sampling ratio (default: 1.0)
    POLISYOS_ALWAYS_SAMPLE_ERRORS: Force sampling for spans created as errors (default: true)
"""

from .config import OTelConfig, get_default_config
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

__all__ = [
    # Configuration
    "OTelConfig",
    "get_default_config",
    # Tracer
    "get_tracer",
    "get_current_trace_context",
    "PolicyOSTracer",
    # Metrics
    "get_metrics",
    "MetricsRegistry",
    # Decorators
    "traced",
    "traced_method",
    # Logging
    "configure_otel_logging_handler",
    "get_trace_context_dict",
    "StructuredFormatter",
    "TraceContextFilter",
    # Propagation
    "inject_headers",
    "extract_headers",
    "propagate_context",
    "with_trace_context",
    "TracedExecutorWrapper",
]
