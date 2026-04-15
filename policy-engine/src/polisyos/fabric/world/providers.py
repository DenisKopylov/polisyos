"""Provider helpers for world-store and materialization observability."""
from __future__ import annotations

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


def resolve_world_observability(
    *,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
) -> WorldObservabilityProviders:
    """Resolve a world observability bundle with optional explicit overrides."""

    return WorldObservabilityProviders(
        tracer=tracer or get_tracer(),
        metrics=metrics or get_metrics(),
    )


__all__ = ["WorldObservabilityProviders", "resolve_world_observability"]
