"""Provider helpers for world-store and materialization observability."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# Keep this module available for runtime type-hint resolution.
import polisyos.core.observability as _core_observability  # noqa: TC001
from polisyos.core.observability import (
    MetricsRegistry,
    get_metrics,
    get_tracer,
)


@dataclass(frozen=True, slots=True)
class WorldObservabilityProviders:
    """Resolved observability providers for world read/write paths."""

    tracer: _core_observability.PolicyOSTracer
    metrics: MetricsRegistry


WorldMetricsFactory = Callable[[], MetricsRegistry]


def resolve_world_observability(
    *,
    tracer: _core_observability.PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
    tracer_factory: Callable[[], _core_observability.PolicyOSTracer] | None = None,
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


def _default_tracer() -> _core_observability.PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


__all__ = ["WorldObservabilityProviders", "resolve_world_observability"]
