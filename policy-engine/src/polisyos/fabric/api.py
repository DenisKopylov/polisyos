"""Explicit public Fabric API facade and connector bridge."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING, Any, Protocol, cast
from weakref import WeakKeyDictionary

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger

from . import __all__ as __all__
from . import __dir__ as __dir__
from . import __getattr__ as __getattr__

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Callable, Iterable
    from pathlib import Path

    from polisyos.fabric.connectors._registry_models import _ConnectorRegistrationBinding
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.federation.artifact import SelectedFederationInput
    from polisyos.fabric.connectors.federation.types import CompositionRequest
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.sources.sql_query import SQLQueryExecution
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


def fabric_get_fresh_registered_sql_data(
    *,
    dataset_id: str,
    connector_id: str,
    constraints: dict[str, Any] | None = None,
    registry: ConnectorRegistry,
) -> FetchResult[Any]:
    """Fetch an explicitly registered SQL query without cache or fallback.

    This compatibility view returns only data; it does not confer source
    admission. The canonical execution function binds the config and output.
    """
    return _execute_registered_sql(
        dataset_id=dataset_id, connector_id=connector_id, constraints=constraints, registry=registry
    ).result


@dataclass(frozen=True, slots=True)
class _RegisteredSQLExecution:
    registry: ConnectorRegistry
    connector_id: str
    binding: _ConnectorRegistrationBinding
    config: ConnectionConfig


_REGISTERED_SQL_EXECUTIONS: WeakKeyDictionary[SQLQueryExecution, _RegisteredSQLExecution] = (
    WeakKeyDictionary()
)
_REGISTERED_SQL_EXECUTIONS_LOCK = RLock()


def _require_registered_sql_execution(observed: SQLQueryExecution) -> _RegisteredSQLExecution:
    """Reconcile the live registered owner with a real driver observation.

    This is still candidate producer evidence, never an issuer or admission.
    """
    from polisyos.fabric.connectors.sources.sql_query import _require_sql_execution

    record = _require_sql_execution(observed)
    with _REGISTERED_SQL_EXECUTIONS_LOCK:
        selected = _REGISTERED_SQL_EXECUTIONS.get(observed)
    if selected is None:
        raise ValueError("registered_sql_execution_not_observed")
    current = selected.registry._require_registration_binding(
        selected.connector_id, selected.binding
    )
    if current.instance is not record.connector or record.config != selected.config:
        raise ValueError("registered_sql_execution_origin_not_established")
    if selected.registry.get_default_config(selected.connector_id) != selected.config:
        raise ValueError("registered_sql_effective_config_changed")
    return selected


def _execute_registered_sql(
    *,
    dataset_id: str,
    connector_id: str,
    constraints: dict[str, Any] | None = None,
    registry: ConnectorRegistry,
    expected_config_fingerprint: str | None = None,
    expected_dataset_id: str | None = None,
    expected_page_size: int | None = None,
    expected_query: str | None = None,
) -> SQLQueryExecution:
    """Execute the selected registered SQL owner with one frozen effective config.

    The returned observation is candidate data, not authorization. It includes
    sensitive query and result material and must stay in protected custody.
    Cache, discovery, resilience/fallback and retry are not used on this path.

    Raises:
        ValueError: If the selected owner, profile, or observed execution cannot
            be established.
    """
    import asyncio

    # A nested running event loop makes run_coro_sync hand SQL to a shared
    # thread which can outlive its caller after timeout. This narrow profile
    # requires a synchronous acquisition worker to retain its event fence.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise ValueError("registered_sql_async_caller_not_supported")

    from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
    from polisyos.ir.connectors import FetchRequest

    if type(registry) is not ConnectorRegistry:
        raise ValueError("registered_sql_registry_owner_not_established")
    binding = registry._capture_registration_binding(connector_id)
    if binding.connector_class is not SQLQueryConnector:
        raise ValueError("registered_sql_connector_owner_not_established")
    configured = registry.get_default_config(connector_id)
    if type(configured) is not ConnectionConfig:
        raise ValueError("registered_sql_effective_config_not_established")
    # Do not retain the registry's object as the execution profile. Even a
    # frozen dataclass can be modified by code holding that same object via
    # object.__setattr__. The selected profile is an independent frozen copy
    # with primitive, immutable values and independently copied mappings.
    if (
        type(configured.url) is not str
        or any(
            type(key) is not str or type(value) is not str
            for key, value in configured.headers.items()
        )
        or (
            configured.source_profile_fingerprint is not None
            and type(configured.source_profile_fingerprint) is not str
        )
    ):
        raise ValueError("registered_sql_connection_profile_not_supported")
    config = replace(configured)
    if (
        expected_config_fingerprint is not None
        and expected_config_fingerprint != config.cache_scope_fingerprint
    ):
        raise ValueError("registered_sql_view_not_executed")
    if expected_dataset_id is not None and expected_dataset_id != dataset_id:
        raise ValueError("registered_sql_view_not_executed")
    values = constraints or {}
    if set(values) - {"page_size"}:
        raise ValueError("registered_sql_requested_scope_not_executed")
    page_size = values.get("page_size")
    if type(page_size) is not int or page_size <= 0 or page_size > 10000:
        raise ValueError("registered_sql_page_size_invalid")
    if expected_page_size is not None and expected_page_size != page_size:
        raise ValueError("registered_sql_view_not_executed")
    if type(dataset_id) is not str or not dataset_id.strip():
        raise ValueError("registered_sql_requested_dataset_not_executed")
    configured_table = str(config.headers.get("X-SQL-Table", "")).strip()
    if configured_table and configured_table != dataset_id.strip():
        raise ValueError("registered_sql_requested_dataset_not_executed")
    configured_query = str(config.headers.get("X-SQL-Query", "")).strip()
    if configured_query and page_size is not None:
        raise ValueError("registered_sql_configured_query_ignores_page_size")
    if configured_query:
        raise ValueError("registered_sql_configured_query_not_supported")

    from os.path import isabs
    from urllib.parse import urlparse

    parsed = urlparse(config.url)
    if (
        not str(config.url).strip()
        or parsed.scheme.lower() not in {"", "sqlite"}
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not isabs(parsed.path)
        or parsed.path in {":memory:", "/:memory:"}
        or set(config.headers) - {"X-SQL-Table"}
        or config.auth_method is not None
        or bool(config.auth_credentials)
        or type(config.timeout_seconds) is not int
        or config.timeout_seconds <= 0
        or type(config.max_connections) is not int
        or config.max_connections <= 0
        or type(config.max_retries) is not int
        or config.max_retries != 3
        or type(config.retry_delay_seconds) is not float
        or config.retry_delay_seconds != 1.0
        or config.rate_limit_rps is not None
        or type(config.keepalive_seconds) is not int
        or config.keepalive_seconds != 30
        or config.verify_ssl is not True
        or config.ca_bundle_path is not None
    ):
        raise ValueError("registered_sql_connection_profile_not_supported")
    if binding.entry.metadata.resilience_config is not None:
        raise ValueError("registered_sql_execution_origin_not_established")
    connector = registry.get(connector_id, enable_cache=False, _registration_binding=binding)
    if (
        type(connector) is not SQLQueryConnector
        or getattr(connector, "resilience_config", None) is not None
        or getattr(connector, "_resilience_wrapped", False)
    ):
        raise ValueError("registered_sql_execution_origin_not_established")
    request = FetchRequest(
        dataset_id=dataset_id,
        page_size=page_size,
        include_metadata=True,
        include_schema=True,
        retryable=False,
    )
    query = SQLQueryConnector._query(connector, config, request)
    if expected_query is not None and expected_query != query:
        raise ValueError("registered_sql_view_not_executed")

    async def _execute() -> SQLQueryExecution:
        # Passing this exact frozen config prevents an A -> B -> A registry
        # default replacement from changing which SQL the driver executes.
        handle = await registry.get_connection(connector_id, config, _registration_binding=binding)
        try:
            if type(handle) is not ConnectionHandle or handle.config != config:
                raise ValueError("registered_sql_connection_config_not_established")
            observed = await SQLQueryConnector._execute_observed(
                connector, handle, request, canonical=True, canonical_query=query
            )
            if observed.config_fingerprint != config.cache_scope_fingerprint:
                raise ValueError("registered_sql_execution_config_mismatch")
            return observed
        finally:
            await registry.release_connection(connector_id, handle)

    observed = run_coro_sync(_execute())
    registry._require_registration_binding(connector_id, binding)
    if registry.get_default_config(connector_id) != config:
        raise ValueError("registered_sql_effective_config_changed")
    from polisyos.fabric.connectors.sources.sql_query import _require_sql_execution

    record = _require_sql_execution(observed)
    if (
        record.connector is not connector
        or record.config != config
        or record.request is not request
    ):
        raise ValueError("registered_sql_execution_origin_not_established")
    with _REGISTERED_SQL_EXECUTIONS_LOCK:
        _REGISTERED_SQL_EXECUTIONS[observed] = _RegisteredSQLExecution(
            registry=registry, connector_id=connector_id, binding=binding, config=config
        )
    _require_registered_sql_execution(observed)
    return observed


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
