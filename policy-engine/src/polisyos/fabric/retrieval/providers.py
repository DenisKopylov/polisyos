"""Injectable provider bundle for the fabric retrieval stack."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from polisyos.core.observability import (
    MetricsRegistry,
    PolicyOSTracer,
    get_metrics,
    get_tracer,
)
from polisyos.fabric.connectors.profiles import SourceProfileRegistry
from polisyos.fabric.connectors.registry import ConnectorRegistry


@dataclass(frozen=True, slots=True)
class RetrievalProviders:
    """Bundle retrieval dependencies so services avoid ad hoc singleton lookups."""

    registry: ConnectorRegistry
    profiles: SourceProfileRegistry
    tracer: PolicyOSTracer
    metrics: MetricsRegistry


RetrievalRegistryFactory = Callable[[], ConnectorRegistry]
RetrievalProfilesFactory = Callable[[], SourceProfileRegistry]
RetrievalTracerFactory = Callable[[], PolicyOSTracer]
RetrievalMetricsFactory = Callable[[], MetricsRegistry]


def resolve_retrieval_providers(
    *,
    registry: ConnectorRegistry | None = None,
    profiles: SourceProfileRegistry | None = None,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
    registry_factory: RetrievalRegistryFactory | None = None,
    profiles_factory: RetrievalProfilesFactory | None = None,
    tracer_factory: RetrievalTracerFactory | None = None,
    metrics_factory: RetrievalMetricsFactory | None = None,
) -> RetrievalProviders:
    """Resolve the retrieval provider bundle, defaulting only at the outer boundary."""

    if registry is None:
        registry = (
            registry_factory()
            if registry_factory is not None
            else _default_registry()
        )
    if profiles is None:
        profiles = (
            profiles_factory()
            if profiles_factory is not None
            else _default_profiles()
        )
    if tracer is None:
        tracer = (
            tracer_factory()
            if tracer_factory is not None
            else _default_tracer()
        )
    if metrics is None:
        metrics = (
            metrics_factory()
            if metrics_factory is not None
            else _default_metrics()
        )
    return RetrievalProviders(
        registry=registry,
        profiles=profiles,
        tracer=tracer,
        metrics=metrics,
    )


def _default_registry() -> ConnectorRegistry:
    return ConnectorRegistry.get_instance()


def _default_profiles() -> SourceProfileRegistry:
    return SourceProfileRegistry.get_instance()


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


__all__ = ["RetrievalProviders", "resolve_retrieval_providers"]
