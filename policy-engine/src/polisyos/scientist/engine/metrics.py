"""Stable Scientist engine metrics facade.

Provides one import surface for runtime metrics collection and exporter health
inspection so runners, workers, and CI evidence builders do not need to know
about the underlying OTel bridge layout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.core.observability import MetricsRegistry, get_metrics

from .metrics_otel import OTelEngineMetrics, TraceCorrelationRecord
from .metrics_protocol import EngineMetricsCollector, NoopEngineMetrics

__all__ = [
    "EngineMetricsCollector",
    "MetricsExporterHealth",
    "NoopEngineMetrics",
    "OTelEngineMetrics",
    "TraceCorrelationRecord",
    "build_engine_metrics",
    "get_metrics_exporter_health",
]


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


@dataclass(frozen=True, slots=True)
class MetricsExporterHealth:
    """Normalized metrics exporter readiness snapshot."""

    status: str
    failures: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "failures": list(self.failures),
            "ready": self.ready,
        }


def build_engine_metrics(
    *,
    metrics: MetricsRegistry | None = None,
    max_trace_correlations: int = 256,
) -> EngineMetricsCollector:
    """Return the default OTel-backed Scientist metrics collector."""
    return OTelEngineMetrics(
        metrics=metrics,
        max_trace_correlations=max_trace_correlations,
    )


def get_metrics_exporter_health(
    *,
    metrics: MetricsRegistry | None = None,
) -> MetricsExporterHealth:
    """Return normalized exporter health for Prometheus/OTel metrics."""
    registry = metrics if metrics is not None else _default_metrics()
    ensure_initialized = getattr(registry, "ensure_initialized", None)
    if callable(ensure_initialized):
        ensure_initialized()

    getter = getattr(registry, "get_exporter_health", None)
    if not callable(getter):
        return MetricsExporterHealth(status="unknown")

    raw = getter()
    metrics_health = raw.get("metrics") if isinstance(raw, dict) else None
    if not isinstance(metrics_health, dict):
        return MetricsExporterHealth(status="unknown")

    status = str(metrics_health.get("status") or "unknown")
    failures = metrics_health.get("failures")
    if not isinstance(failures, list):
        failures = []
    normalized_failures = tuple(
        str(item)
        for item in failures
        if isinstance(item, str) and item.strip()
    )
    return MetricsExporterHealth(status=status, failures=normalized_failures)
