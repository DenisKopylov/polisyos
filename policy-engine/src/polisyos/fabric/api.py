"""Explicit public Fabric API facade and connector bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, cast

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger

from . import __all__ as __all__
from . import __dir__ as __dir__
from . import __getattr__ as __getattr__

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Callable, Iterable
    from pathlib import Path

    from polisyos.fabric.connectors.federation.artifact import SelectedFederationInput
    from polisyos.fabric.connectors.federation.types import CompositionRequest
    from polisyos.ir.connectors import FetchRequest, FetchResult

logger = get_logger(__name__)


class DatasetDescriptorLike(Protocol):
    """Minimal dataset-descriptor shape required by the public bridge."""

    dataset_id: str


class ConnectorEntryLike(Protocol):
    """Minimal connector-registry entry shape required by the bridge."""

    short_id: str
    known_datasets: Iterable[str]
    dataset_descriptors: Iterable[DatasetDescriptorLike]
    default_config: object | None


class FetchConnectorLike(Protocol):
    """Connector surface required by the public Scientist-to-Fabric bridge."""

    def list_datasets(
        self,
        handle: object,
    ) -> object: ...

    async def fetch(
        self,
        handle: object,
        request: FetchRequest,
    ) -> FetchResult[object]: ...


class ConnectorRegistryLike(Protocol):
    """Connector-registry surface required by `fabric_get_data()`."""

    def get(self, connector_id: str) -> FetchConnectorLike: ...
    def get_entry(self, connector_id: str) -> object: ...
    def query_entries(
        self,
        *,
        capabilities: object | None = None,
    ) -> Iterable[object]: ...
    async def get_connection(self, connector_id: str, config: object) -> object: ...
    async def release_connection(self, connector_id: str, handle: object) -> None: ...


if TYPE_CHECKING:
    ConnectorRegistryFactory = Callable[[], ConnectorRegistryLike]


def resolve_connector_registry(
    registry: ConnectorRegistryLike | None = None,
    registry_factory: ConnectorRegistryFactory | None = None,
) -> ConnectorRegistryLike:
    """Resolve the connector registry, defaulting only at the public bridge boundary."""

    if registry is not None:
        return registry
    if registry_factory is not None:
        return registry_factory()
    return _default_connector_registry()


def _default_connector_registry() -> ConnectorRegistryLike:
    from polisyos.fabric.connectors.registry import ConnectorRegistry

    return cast("ConnectorRegistryLike", ConnectorRegistry.get_instance())


@dataclass(frozen=True)
class FederationFetchSource:
    """One explicitly selected connector/dataset pair, preserving caller order."""

    connector_id: str
    dataset_id: str


@dataclass(frozen=True)
class FederationFetchRequest:
    """Opt-in bounded composition; the output directory must not already exist.

    Sources may be selected by the existing FederationPlanner or explicitly by
    the caller. This object grants no source-selection authority. Only an
    explicit per-source/final-output row bound is supported; filter/date scope
    is unsupported. No capture-origin authentication is implied.
    """

    composition: CompositionRequest
    sources: tuple[FederationFetchSource | SelectedFederationInput, ...]
    output_root: Path


def fabric_get_data(
    *,
    dataset_id: str,
    connector_id: str | None = None,
    constraints: dict[str, Any] | None = None,
    registry: ConnectorRegistryLike | None = None,
    federation: FederationFetchRequest | None = None,
) -> FetchResult[Any]:
    """
    High-level data acquisition for the Scientist layer.

    Parameters
    ----------
    dataset_id : str
        Logical dataset identifier (e.g. ``"gdp_ua"``). Must match
        a registered connector's dataset catalog.
    connector_id : str | None
        Explicit connector to use. When None, the registry attempts
        catalog-based discovery (requires CATALOG_BROWSE connectors).
    constraints : dict | None
        Optional query constraints. Recognised keys:

        - ``date_start`` / ``date_end``: ISO-8601 strings for temporal bounds.
        - ``filters``: ``{field: [values]}`` dimension filters.
        - ``page_size``: int, for paginated fetches.

    federation : FederationFetchRequest | None
        Explicit opt-in ordered composition and new selected-output directory.
        Default None preserves the single-connector path.

    Returns
    -------
    FetchResult
        The canonical result envelope.
    """
    from polisyos.ir.connectors import FetchRequest

    if federation is not None:
        from polisyos.fabric.federated_fetch import fetch_federated

        if connector_id is not None:
            raise ValueError(
                "connector_id and explicit federation selections are mutually exclusive"
            )
        return fetch_federated(
            dataset_id=dataset_id,
            federation=federation,
            constraints=constraints,
            registry=resolve_connector_registry(registry),
        )

    constraints = constraints or {}
    resolved_registry = resolve_connector_registry(registry)

    if connector_id is None:
        connector_id = _resolve_connector_for_dataset(resolved_registry, dataset_id)

    connector = resolved_registry.get(connector_id)

    filters_raw: dict[str, list[str]] = constraints.get("filters", {})
    filter_tuple = tuple((k, tuple(v)) for k, v in sorted(filters_raw.items()))
    request = FetchRequest(
        dataset_id=dataset_id,
        filters=filter_tuple,
        date_start=_parse_dt(constraints.get("date_start")),
        date_end=_parse_dt(constraints.get("date_end")),
        page_size=constraints.get("page_size"),
        include_metadata=True,
        include_schema=True,
        retryable=True,
    )

    result: FetchResult[Any] = _sync_fetch(
        resolved_registry,
        connector_id,
        connector,
        request,
    )

    logger.info(
        "fabric_get_data: fetched %d rows from %s:%s",
        result.row_count,
        connector_id,
        dataset_id,
    )
    return result


def _resolve_connector_for_dataset(
    registry: ConnectorRegistryLike,
    dataset_id: str,
) -> str:
    """
    Resolve a connector capable of serving *dataset_id*.

    Strategy:
        1) Check registry metadata caches (known_datasets / descriptors).
        2) Fall back to calling list_datasets() on CATALOG_BROWSE connectors.
    """
    from polisyos.fabric.connectors.registry import ConnectorNotFoundError
    from polisyos.fabric.connectors.types import CatalogRegistrySchemaError
    from polisyos.ir.connectors import ConnectorCapability

    candidates = [
        _as_entry(entry)
        for entry in registry.query_entries(capabilities=ConnectorCapability.CATALOG_BROWSE)
    ]
    if not candidates:
        raise ConnectorNotFoundError(
            connector_id=dataset_id,
            available=[],
        )

    for entry in candidates:
        if dataset_id in entry.known_datasets:
            return entry.short_id
        for desc in entry.dataset_descriptors:
            if desc.dataset_id == dataset_id:
                return entry.short_id

    registry_failures: list[tuple[str, CatalogRegistrySchemaError]] = []
    for entry in candidates:
        try:
            matched = _probe_catalog(registry, entry.short_id, dataset_id)
        except CatalogRegistrySchemaError as exc:
            registry_failures.append((entry.short_id, exc))
            logger.warning(
                "catalog registry probe failed for connector '%s' dataset '%s': %s",
                entry.short_id,
                dataset_id,
                exc,
            )
            continue
        if matched:
            return entry.short_id

    if registry_failures:
        connector_id, cause = registry_failures[0]
        raise CatalogRegistrySchemaError(
            message=(
                f"Catalog discovery is incomplete for dataset {dataset_id!r}: "
                f"{len(registry_failures)} registry probe(s) failed and no independent "
                "connector matched"
            ),
            connector_id=connector_id,
        ) from cause

    raise ConnectorNotFoundError(
        connector_id=dataset_id,
        available=[entry.short_id for entry in candidates],
    )


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _probe_catalog(
    registry: ConnectorRegistryLike,
    connector_id: str,
    dataset_id: str,
) -> bool:
    from polisyos.fabric.connectors.types import CatalogRegistrySchemaError

    async def _check() -> bool:
        config = _default_config(registry, connector_id)
        handle = await registry.get_connection(connector_id, config)
        connector = registry.get(connector_id)
        try:
            dataset_stream = cast(
                "AsyncIterable[DatasetDescriptorLike]",
                connector.list_datasets(handle),
            )
            async for desc in dataset_stream:
                if desc.dataset_id == dataset_id:
                    return True
        finally:
            await registry.release_connection(connector_id, handle)
        return False

    try:
        return bool(run_coro_sync(_check()))
    except CatalogRegistrySchemaError:
        raise
    except Exception as exc:
        logger.warning(
            "catalog probe failed for connector '%s' dataset '%s': %s",
            connector_id,
            dataset_id,
            exc,
        )
        return False


def _sync_fetch(
    registry: ConnectorRegistryLike,
    connector_id: str,
    connector: FetchConnectorLike,
    request: FetchRequest,
) -> FetchResult[object]:
    async def _do() -> FetchResult[object]:
        config = _default_config(registry, connector_id)
        handle = await registry.get_connection(connector_id, config)
        try:
            return await connector.fetch(handle, request)
        finally:
            await registry.release_connection(connector_id, handle)

    return run_coro_sync(_do())


def _default_config(registry: ConnectorRegistryLike, connector_id: str) -> object:
    entry = _as_entry(registry.get_entry(connector_id))
    if entry.default_config is None:
        raise ValueError(f"No default_config registered for connector '{connector_id}'")
    return entry.default_config


def _as_entry(entry: object) -> ConnectorEntryLike:
    return cast("ConnectorEntryLike", entry)
