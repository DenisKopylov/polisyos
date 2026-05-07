"""Provider bundle helpers for connector-ingestion entrypoints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.fabric.connectors.registry import ConnectorRegistry

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer

ArtifactStoreFactory = Callable[[Path], FileSystemCAS]
IngestionRegistryFactory = Callable[[], ConnectorRegistry]


def build_filesystem_artifact_store(root: Path) -> FileSystemCAS:
    """Build the default filesystem-backed CAS used by ingestion entrypoints."""
    return cast(
        "FileSystemCAS",
        build_artifact_store(
            ArtifactStoreConfig(backend="filesystem", root=str(root)),
        ),
    )


@dataclass(frozen=True, slots=True)
class IngestionDependencies:
    """Resolved provider bundle for connector ingestion entrypoints."""

    registry: ConnectorRegistry
    tracer: PolicyOSTracer
    metrics: MetricsRegistry
    store_factory: ArtifactStoreFactory = build_filesystem_artifact_store


def resolve_ingestion_dependencies(
    *,
    registry: ConnectorRegistry | None = None,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
    store_factory: ArtifactStoreFactory | None = None,
    registry_factory: IngestionRegistryFactory | None = None,
    tracer_factory: Callable[[], PolicyOSTracer] | None = None,
    metrics_factory: Callable[[], MetricsRegistry] | None = None,
) -> IngestionDependencies:
    """Resolve connector-ingestion dependencies once at the API boundary."""
    if registry is None:
        registry = registry_factory() if registry_factory is not None else _default_registry()
    if tracer is None:
        tracer = tracer_factory() if tracer_factory is not None else _default_tracer()
    if metrics is None:
        metrics = metrics_factory() if metrics_factory is not None else _default_metrics()
    return IngestionDependencies(
        registry=registry,
        tracer=tracer,
        metrics=metrics,
        store_factory=store_factory or build_filesystem_artifact_store,
    )


def _default_registry() -> ConnectorRegistry:
    return ConnectorRegistry.get_instance()


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()
