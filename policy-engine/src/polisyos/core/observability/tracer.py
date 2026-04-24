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
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from importlib import import_module
from typing import TYPE_CHECKING, Any, cast

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    Decision,
    ParentBased,
    Sampler,
    SamplingResult,
    TraceIdRatioBased,
)
from opentelemetry.trace import Link, Span, SpanKind, Status, StatusCode, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.util.types import Attributes

from .config import OTelConfig, get_default_config, get_resource_config

if TYPE_CHECKING:
    from opentelemetry.sdk.trace.export import SpanExporter


class ErrorAwareSampler(Sampler):
    """
    Composite sampler that respects ratio but always samples known errors.

    Limitation: head sampling cannot see errors that happen after the decision.
    This only captures spans created with error attributes from the start.
    """

    def __init__(self, ratio: float) -> None:
        self._base = TraceIdRatioBased(ratio)
        self._description = f"ErrorAwareSampler(ratio={ratio})"

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        trace_state: Any | None = None,
    ) -> SamplingResult:
        error_value = attributes.get("error") if attributes else None
        is_error = False
        if isinstance(error_value, str):
            is_error = error_value.lower() == "true"
        elif isinstance(error_value, bool):
            is_error = error_value

        if is_error:
            return SamplingResult(
                decision=Decision.RECORD_AND_SAMPLE,
                attributes=attributes,
            )

        try:
            return self._base.should_sample(
                parent_context, trace_id, name, kind, attributes, links, trace_state
            )
        except TypeError:
            return self._base.should_sample(parent_context, trace_id, name, kind, attributes, links)

    def get_description(self) -> str:
        return self._description


class PolicyOSTracer:
    """
    Singleton tracer wrapper with lazy initialization.

    Thread-safe and designed for minimal startup overhead.
    """

    _instance: PolicyOSTracer | None = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> PolicyOSTracer:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Re-establish instance attributes even if singleton state was reset
        # while an existing object instance remained reachable.
        if not hasattr(self, "_config"):
            self._config: OTelConfig | None = None
            self._provider: TracerProvider | None = None
            self._tracer: Tracer | None = None
            self._propagator = TraceContextTextMapPropagator()
        # Guard against re-initialization
        if PolicyOSTracer._initialized:
            return

    @classmethod
    def current_instance(cls) -> PolicyOSTracer | None:
        """Return the cached singleton instance without forcing initialization."""
        return cls._instance

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

            # Configure sampler (Phase 4)
            sampler = self._create_sampler()

            # Create TracerProvider
            self._provider = TracerProvider(resource=resource, sampler=sampler)

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

    def _create_sampler(self) -> Sampler:
        """
        Create a ParentBased sampler with optional error-aware root sampling.

        Strategy:
        - Root spans: Sample based on ratio (e.g., 1% in prod)
        - Child spans: Follow parent's decision (ParentBased)
        - Errors: Best-effort always-sample when error attribute is present
        """
        ratio = self._config.sampling_ratio if self._config else 1.0

        if ratio >= 1.0:
            return ALWAYS_ON
        if ratio <= 0.0:
            return ALWAYS_OFF

        root_sampler: Sampler
        if self._config and self._config.always_sample_errors:
            root_sampler = ErrorAwareSampler(ratio)
        else:
            root_sampler = TraceIdRatioBased(ratio)

        return ParentBased(
            root=root_sampler,
            remote_parent_sampled=ALWAYS_ON,
            remote_parent_not_sampled=ALWAYS_OFF,
            local_parent_sampled=ALWAYS_ON,
            local_parent_not_sampled=ALWAYS_OFF,
        )

    def _create_otlp_exporter(self) -> SpanExporter | None:
        """Create OTLP exporter based on configuration."""
        if self._config is None or not self._config.otlp_endpoint:
            return None

        protocol = (self._config.otlp_protocol or "").lower()
        if protocol.startswith("http"):
            try:
                module = import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
                http_otlp_span_exporter = module.OTLPSpanExporter

                return cast(
                    "SpanExporter",
                    http_otlp_span_exporter(
                        endpoint=f"{self._config.otlp_endpoint}/v1/traces",
                        headers=self._config.otlp_headers or None,
                    ),
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
                module = import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
                http_otlp_span_exporter = module.OTLPSpanExporter

                return cast(
                    "SpanExporter",
                    http_otlp_span_exporter(
                        endpoint=f"{self._config.otlp_endpoint}/v1/traces",
                        headers=self._config.otlp_headers or None,
                    ),
                )
            except ImportError:
                return None

    @property
    def tracer(self) -> Tracer:
        """Get the underlying OTel Tracer instance."""
        self._ensure_initialized()
        if self._tracer is None:
            raise RuntimeError("PolicyOSTracer failed to initialize an OpenTelemetry tracer")
        return self._tracer

    @contextmanager
    def start_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
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
        attributes: dict[str, Any] | None = None,
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

    def get_current_trace_id(self) -> str | None:
        """Get the current trace ID as hex string, or None if no active span."""
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, "032x")
        return None

    def get_current_span_id(self) -> str | None:
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
_tracer_instance: PolicyOSTracer | None = None
_tracer_instance_lock = threading.Lock()


def get_tracer() -> PolicyOSTracer:
    """
    Get the global PolicyOSTracer instance.

    This is the recommended way to access the tracer.
    """
    global _tracer_instance
    current_instance = PolicyOSTracer.current_instance()
    if (
        _tracer_instance is not None
        and current_instance is not None
        and _tracer_instance is current_instance
    ):
        return _tracer_instance
    with _tracer_instance_lock:
        current_instance = PolicyOSTracer.current_instance()
        if (
            _tracer_instance is None
            or current_instance is None
            or _tracer_instance is not current_instance
        ):
            _tracer_instance = PolicyOSTracer()
    return _tracer_instance


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def get_current_trace_context() -> dict[str, str | None]:
    """
    Get current trace context for logging correlation.

    Returns:
        Dictionary with trace_id and span_id (or None if no active span)
    """
    tracer = _default_tracer()
    return {
        "trace_id": tracer.get_current_trace_id(),
        "span_id": tracer.get_current_span_id(),
    }
