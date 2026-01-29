"""
PolicyOS Tracer — Singleton wrapper for OpenTelemetry TracerProvider.

Key Features:
- Lazy initialization (no overhead until first span)
- Thread-safe singleton pattern
- Automatic BatchSpanProcessor for production
- Graceful fallback to NoOp tracer when disabled

Usage:
    from polisyos.core.observability import get_tracer

    tracer = get_tracer()
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("polisyos.phase", "EXECUTE")
        do_work()
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Optional

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Span, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import SpanKind, Status, StatusCode, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .config import OTelConfig, get_default_config, get_resource_config

if TYPE_CHECKING:
    from opentelemetry.sdk.trace.export import SpanExporter


class PolicyOSTracer:
    """
    Singleton tracer wrapper with lazy initialization.

    Thread-safe and designed for minimal startup overhead.
    """

    _instance: Optional["PolicyOSTracer"] = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> "PolicyOSTracer":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Guard against re-initialization
        if PolicyOSTracer._initialized:
            return

        self._config: Optional[OTelConfig] = None
        self._provider: Optional[TracerProvider] = None
        self._tracer: Optional[Tracer] = None
        self._propagator = TraceContextTextMapPropagator()

    def _ensure_initialized(self) -> None:
        """
        Lazy initialization of TracerProvider.

        Called on first span creation, not at import time.
        """
        if PolicyOSTracer._initialized:
            return

        with self._lock:
            if PolicyOSTracer._initialized:
                return

            self._config = get_default_config()

            if not self._config.enabled:
                # Use NoOp tracer when disabled
                self._tracer = trace.get_tracer("polisyos.noop")
                PolicyOSTracer._initialized = True
                return

            existing_provider = trace.get_tracer_provider()
            if existing_provider.__class__.__name__ != "ProxyTracerProvider":
                if isinstance(existing_provider, TracerProvider):
                    self._provider = existing_provider
                self._tracer = trace.get_tracer(
                    "polisyos",
                    self._config.service_version,
                )
                PolicyOSTracer._initialized = True
                return

            # Build resource
            resource_config = get_resource_config(self._config)
            resource = Resource.create(resource_config.to_attributes())

            # Create TracerProvider
            self._provider = TracerProvider(resource=resource)

            # Configure exporters
            self._configure_exporters()

            # Set as global provider
            trace.set_tracer_provider(self._provider)

            # Get tracer instance
            self._tracer = trace.get_tracer(
                "polisyos",
                self._config.service_version,
            )

            PolicyOSTracer._initialized = True

    def _configure_exporters(self) -> None:
        """Configure span exporters based on config."""
        if self._provider is None or self._config is None:
            return

        # Console exporter for debugging
        if self._config.console_export:
            self._provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

        # OTLP exporter for production
        if self._config.otlp_endpoint:
            exporter = self._create_otlp_exporter()
            if exporter:
                processor = BatchSpanProcessor(
                    exporter,
                    max_queue_size=self._config.batch_max_queue_size,
                    max_export_batch_size=self._config.batch_max_export_batch_size,
                    schedule_delay_millis=self._config.batch_schedule_delay_millis,
                    export_timeout_millis=self._config.batch_export_timeout_millis,
                )
                self._provider.add_span_processor(processor)

    def _create_otlp_exporter(self) -> Optional["SpanExporter"]:
        """Create OTLP exporter based on configuration."""
        if self._config is None or not self._config.otlp_endpoint:
            return None

        protocol = (self._config.otlp_protocol or "").lower()
        if protocol.startswith("http"):
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter as HTTPOTLPSpanExporter,
                )

                return HTTPOTLPSpanExporter(
                    endpoint=f"{self._config.otlp_endpoint}/v1/traces",
                    headers=self._config.otlp_headers or None,
                )
            except ImportError:
                return None

        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            return OTLPSpanExporter(
                endpoint=self._config.otlp_endpoint,
                headers=self._config.otlp_headers or None,
            )
        except ImportError:
            # Fallback to HTTP if gRPC not available
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter as HTTPOTLPSpanExporter,
                )

                return HTTPOTLPSpanExporter(
                    endpoint=f"{self._config.otlp_endpoint}/v1/traces",
                    headers=self._config.otlp_headers or None,
                )
            except ImportError:
                return None

    @property
    def tracer(self) -> Tracer:
        """Get the underlying OTel Tracer instance."""
        self._ensure_initialized()
        assert self._tracer is not None
        return self._tracer

    @contextmanager
    def start_span(
        self,
        name: str,
        *,
        attributes: Optional[dict[str, Any]] = None,
        kind: SpanKind = SpanKind.INTERNAL,
    ) -> Iterator[Span]:
        """
        Start a new span without setting it as current.

        Use this for spans that don't need context propagation.
        """
        self._ensure_initialized()
        span = self.tracer.start_span(
            name,
            attributes=attributes,
            kind=kind,
        )
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(status_code=StatusCode.ERROR, description=str(exc)))
            span.record_exception(exc)
            raise
        finally:
            span.end()

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        *,
        attributes: Optional[dict[str, Any]] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
    ) -> Iterator[Span]:
        """
        Start a new span and set it as the current span.

        This is the primary API for instrumentation.
        Child spans will automatically be linked to this span.
        """
        self._ensure_initialized()
        with self.tracer.start_as_current_span(
            name,
            attributes=attributes,
            kind=kind,
            record_exception=record_exception,
            set_status_on_exception=set_status_on_exception,
        ) as span:
            yield span

    def get_current_span(self) -> Span:
        """Get the current active span."""
        self._ensure_initialized()
        return trace.get_current_span()

    def get_current_trace_id(self) -> Optional[str]:
        """Get the current trace ID as hex string, or None if no active span."""
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, "032x")
        return None

    def get_current_span_id(self) -> Optional[str]:
        """Get the current span ID as hex string, or None if no active span."""
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.span_id, "016x")
        return None

    def inject_context(self, carrier: dict[str, str]) -> None:
        """
        Inject trace context into a carrier for propagation.

        Used for cross-service or cross-thread propagation.
        """
        self._propagator.inject(carrier)

    def extract_context(self, carrier: dict[str, str]) -> Context:
        """
        Extract trace context from a carrier.

        Used to continue a trace from another service/thread.
        """
        return self._propagator.extract(carrier)

    def shutdown(self) -> None:
        """
        Gracefully shutdown the tracer provider.

        Call this before process exit to flush pending spans.
        """
        if self._provider is not None:
            self._provider.shutdown()


# Module-level singleton accessor
_tracer_instance: Optional[PolicyOSTracer] = None


def get_tracer() -> PolicyOSTracer:
    """
    Get the global PolicyOSTracer instance.

    This is the recommended way to access the tracer.
    """
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = PolicyOSTracer()
    return _tracer_instance


def get_current_trace_context() -> dict[str, Optional[str]]:
    """
    Get current trace context for logging correlation.

    Returns:
        Dictionary with trace_id and span_id (or None if no active span)
    """
    tracer = get_tracer()
    return {
        "trace_id": tracer.get_current_trace_id(),
        "span_id": tracer.get_current_span_id(),
    }
