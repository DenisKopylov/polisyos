"""Provider bundle helpers for connector-ingestion entrypoints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from polisyos.core.artifacts import RootedArtifactStore
from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
)
from polisyos.core.observability import MetricsRegistry, PolicyOSTracer, get_metrics, get_tracer
from polisyos.fabric.connectors.registry import ConnectorEntry, ConnectorRegistry
from polisyos.fabric.ingestion.source_progress import FiniteSourceProgressReader

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.connectors._registry_models import _ConnectorRegistrationBinding
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        ConnectionHandle,
        SourceConnectorValue,
    )
from polisyos.fabric.storage.tenant_cas import (
    TenantSidecarScope,
    tenant_scoped_cas_root,
)

ArtifactStoreFactory = Callable[[Path], RootedArtifactStore]
IngestionRegistryFactory = Callable[[], ConnectorRegistry]


def build_filesystem_artifact_store(root: Path) -> FileSystemCAS:
    """Build the default filesystem-backed CAS used by ingestion entrypoints."""
    return cast(
        "FileSystemCAS",
        build_artifact_store(
            ArtifactStoreConfig(backend="filesystem", root=str(root)),
        ),
    )


class IngestionStoreBindingError(ValueError):
    """Raised when a supplied ingestion store cannot bind the requested CAS root."""


def resolve_ingestion_sidecar_scope(
    cas_root: Path,
    *,
    sidecar_scope: TenantSidecarScope | None = None,
    tenant_id: str | None = None,
) -> TenantSidecarScope:
    """Resolve and validate per-invocation sidecar scope without changing providers."""
    from polisyos.core.security import get_current_tenant_id_or_none

    requested_root = Path(cas_root)
    active_tenant_id = get_current_tenant_id_or_none()
    if sidecar_scope is not None:
        if requested_root.resolve() != sidecar_scope.base_root.resolve():
            raise IngestionStoreBindingError("ingestion_sidecar_base_root_mismatch")
        if tenant_id is not None and tenant_id != sidecar_scope.tenant_id:
            raise IngestionStoreBindingError("ingestion_sidecar_tenant_mismatch")
        if active_tenant_id is not None and active_tenant_id != sidecar_scope.tenant_id:
            raise IngestionStoreBindingError("ingestion_sidecar_tenant_mismatch")
        return sidecar_scope

    if tenant_id is not None:
        if active_tenant_id is not None and active_tenant_id != tenant_id:
            raise IngestionStoreBindingError("ingestion_sidecar_tenant_mismatch")
        store_root = tenant_scoped_cas_root(requested_root, tenant_id)
        return TenantSidecarScope.for_pre_scoped_store_root(store_root, tenant_id)

    return TenantSidecarScope.from_current_context(requested_root)


def resolve_ingestion_store(
    cas_root: Path,
    dependencies: _BatchIngestionDependencies,
    *,
    sidecar_scope: TenantSidecarScope | None = None,
) -> RootedArtifactStore:
    """Resolve the owner's store and verify its root against the invocation scope."""
    scope = resolve_ingestion_sidecar_scope(
        cas_root,
        sidecar_scope=sidecar_scope,
    )
    store = dependencies.store_factory(scope.base_root)
    store_root = getattr(store, "root", None)
    if (
        not isinstance(store_root, (str, Path))
        or Path(store_root).resolve() != scope.base_root.resolve()
    ):
        raise IngestionStoreBindingError("ingestion_store_root_mismatch")
    return store


def resolve_ingestion_cache_namespace(
    namespace: str | None,
    *,
    sidecar_scope: TenantSidecarScope,
) -> str:
    """Qualify one logical cache namespace using its explicit scope object."""
    return sidecar_scope.cache_namespace(namespace or "connector_cache")


class _BatchConnectorRegistry(Protocol):
    """The concrete registry operations used by non-streaming ingestion."""

    def get(
        self,
        connector_id: str,
        version: str | None = None,
        *,
        enable_cache: bool = True,
        _registration_binding: _ConnectorRegistrationBinding | None = None,
    ) -> SourceConnectorValue[Any]: ...

    def get_entry(self, connector_id: str) -> ConnectorEntry: ...

    async def get_connection(
        self,
        connector_id: str,
        config: ConnectionConfig | None = None,
        *,
        _registration_binding: _ConnectorRegistrationBinding | None = None,
    ) -> ConnectionHandle: ...

    async def _get_connection_with_live_permit(
        self,
        connector_id: str,
        config: ConnectionConfig | None,
        *,
        dataset_id: str,
        permit: object,
    ) -> ConnectionHandle: ...

    async def release_connection(
        self,
        connector_id: str,
        handle: ConnectionHandle,
    ) -> None: ...


class _BatchIngestionDependencies(Protocol):
    """Read-only provider surface shared by the batch ingestion bridge."""

    @property
    def registry(self) -> _BatchConnectorRegistry: ...

    @property
    def tracer(self) -> PolicyOSTracer: ...

    @property
    def metrics(self) -> MetricsRegistry: ...

    @property
    def store_factory(self) -> ArtifactStoreFactory: ...


@dataclass(frozen=True, slots=True)
class _BatchIngestionDependenciesView:
    """Private batch-only dependency view for the cursor-aware registry facade."""

    registry: _BatchConnectorRegistry
    tracer: PolicyOSTracer
    metrics: MetricsRegistry
    store_factory: ArtifactStoreFactory


@dataclass(frozen=True, slots=True)
class IngestionDependencies:
    """Resolved provider bundle for connector ingestion entrypoints."""

    registry: ConnectorRegistry
    tracer: PolicyOSTracer
    metrics: MetricsRegistry
    store_factory: ArtifactStoreFactory = build_filesystem_artifact_store
    source_progress_readers: tuple[FiniteSourceProgressReader, ...] = ()


def resolve_ingestion_dependencies(
    *,
    registry: ConnectorRegistry | None = None,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
    store_factory: ArtifactStoreFactory | None = None,
    registry_factory: IngestionRegistryFactory | None = None,
    tracer_factory: Callable[[], PolicyOSTracer] | None = None,
    metrics_factory: Callable[[], MetricsRegistry] | None = None,
    source_progress_readers: tuple[FiniteSourceProgressReader, ...] = (),
) -> IngestionDependencies:
    """Resolve connector-ingestion dependencies once at the API boundary."""
    if any(type(reader) is not FiniteSourceProgressReader for reader in source_progress_readers):
        raise TypeError("source progress readers must use the supported finite-source adapter")
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
        source_progress_readers=source_progress_readers,
    )


def _default_registry() -> ConnectorRegistry:
    return ConnectorRegistry.get_instance()


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()
