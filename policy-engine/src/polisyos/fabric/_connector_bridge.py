"""
Connector bridge - the ONLY public surface through which the Scientist
layer may request connector-fetched data.

This module lives in ``fabric/`` (not ``fabric/connectors/``) so that
``scientist/`` can import it without violating Law A.

All imports of connector internals are local to functions in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger

logger = get_logger(__name__)


def fabric_get_data(
    *,
    dataset_id: str,
    connector_id: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> "FetchResult[Any]":
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

    Returns
    -------
    FetchResult
        The canonical result envelope.
    """
    # --- Local imports to maintain Law A at the module graph level ---
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.ir.connectors import FetchRequest, FetchResult

    constraints = constraints or {}
    registry = ConnectorRegistry.get_instance()

    if connector_id is None:
        connector_id = _resolve_connector_for_dataset(registry, dataset_id)

    connector = registry.get(connector_id)

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

    result: FetchResult[Any] = _sync_fetch(registry, connector_id, connector, request)

    logger.info(
        "fabric_get_data: fetched %d rows from %s:%s",
        result.row_count,
        connector_id,
        dataset_id,
    )
    return result


# ---------------------------------------------------------------------------
# Helpers (private)
# ---------------------------------------------------------------------------


def _resolve_connector_for_dataset(registry: Any, dataset_id: str) -> str:
    """
    Resolve a connector capable of serving *dataset_id*.

    Strategy:
        1) Check registry metadata caches (known_datasets / descriptors).
        2) Fall back to calling list_datasets() on CATALOG_BROWSE connectors.
    """
    from polisyos.fabric.connectors.registry import ConnectorNotFoundError
    from polisyos.ir.connectors import ConnectorCapability

    candidates = list(
        registry.query_entries(capabilities=ConnectorCapability.CATALOG_BROWSE)
    )
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

    for entry in candidates:
        if _probe_catalog(registry, entry.short_id, dataset_id):
            return entry.short_id

    raise ConnectorNotFoundError(
        connector_id=dataset_id,
        available=[entry.short_id for entry in candidates],
    )


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _probe_catalog(registry: Any, connector_id: str, dataset_id: str) -> bool:
    async def _check() -> bool:
        config = _default_config(registry, connector_id)
        handle = await registry.get_connection(connector_id, config)
        connector = registry.get(connector_id)
        try:
            async for desc in connector.list_datasets(handle):
                if desc.dataset_id == dataset_id:
                    return True
        finally:
            await registry.release_connection(connector_id, handle)
        return False

    try:
        return bool(run_coro_sync(_check()))
    except Exception as exc:
        logger.warning(
            "catalog probe failed for connector '%s' dataset '%s': %s",
            connector_id,
            dataset_id,
            exc,
        )
        return False


def _sync_fetch(
    registry: Any,
    connector_id: str,
    connector: Any,
    request: Any,
) -> Any:
    async def _do() -> Any:
        config = _default_config(registry, connector_id)
        handle = await registry.get_connection(connector_id, config)
        try:
            return await connector.fetch(handle, request)
        finally:
            await registry.release_connection(connector_id, handle)

    return run_coro_sync(_do())


def _default_config(registry: Any, connector_id: str) -> Any:
    entry = registry.get_entry(connector_id)
    if entry.default_config is None:
        raise ValueError(f"No default_config registered for connector '{connector_id}'")
    return entry.default_config
