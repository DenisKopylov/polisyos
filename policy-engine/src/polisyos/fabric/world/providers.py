"""Provider helpers for world-store and materialization observability."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from polisyos.core.observability import (
    MetricsRegistry,
    PolicyOSTracer,
    get_metrics,
    get_tracer,
)


@dataclass(frozen=True, slots=True)
class WorldObservabilityProviders:
    """Resolved observability providers for world read/write paths."""

    tracer: PolicyOSTracer
    metrics: MetricsRegistry


WorldTracerFactory = Callable[[], PolicyOSTracer]
WorldMetricsFactory = Callable[[], MetricsRegistry]


def resolve_world_observability(
    *,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
    tracer_factory: WorldTracerFactory | None = None,
    metrics_factory: WorldMetricsFactory | None = None,
) -> WorldObservabilityProviders:
    """Resolve a world observability bundle with optional explicit overrides."""

    if tracer is None:
        tracer = tracer_factory() if tracer_factory is not None else _default_tracer()
    if metrics is None:
        metrics = metrics_factory() if metrics_factory is not None else _default_metrics()
    return WorldObservabilityProviders(
        tracer=tracer,
        metrics=metrics,
    )


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


__all__ = ["WorldObservabilityProviders", "resolve_world_observability"]
