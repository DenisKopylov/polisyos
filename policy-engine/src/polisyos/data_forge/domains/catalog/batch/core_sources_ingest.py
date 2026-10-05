"""Compatibility facade for the canonical ``core_sources.api`` entrypoint.

The implementation modules own their dependencies.  This module keeps an
explicit, bounded set of historical bindings for callers and test seams; it
does not copy facade globals into implementation modules.
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from functools import wraps
from types import ModuleType
from typing import Any, Iterator

from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CatalogTransportDataset,
    CoreSourcesIngestStats,
    ObservationFetchKey,
    ObservationFetchPayload,
    ObservationInsertStats,
    ObservationPlan,
    ObservationShard,
    ObservationShardResult,
    ObservationWriteItem,
    SupportSketch,
    WriterFlushState,
    _ObservationRuntimeMetrics,
    _SourceBudgetWindow,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import api as _api
from polisyos.data_forge.domains.catalog.batch.core_sources import loaders as _loaders
from polisyos.data_forge.domains.catalog.batch.core_sources import registry as _registry
from polisyos.data_forge.domains.catalog.batch.core_sources import transformers as _transformers
from polisyos.data_forge.domains.catalog.batch.core_sources import validators as _validators
from polisyos.data_forge.domains.catalog.batch.core_sources import writers as _writers

# Only names still used by the compatibility window are exported.  Every
# entry names its owning leaf; no module-global census or broadcast is used.
_BINDINGS: dict[str, tuple[ModuleType, str]] = {}
for _module, _names in (
    (_writers, """
        _ConnectorSessionCache _capability_snapshot_cache_key _format_duckdb_memory_limit
        _hydrate_support_sketch_dimension_orders _hydrate_work_package_dimension_orders
        _infer_ilo_dimension_order _insert_generic_observations _legacy_ingest_observations
        _support_sketch_id _upsert_legacy_registry_datasets _upsert_seed_alignments
    """.split()),
    (_validators, """
        _append_shard_result _build_observation_shards _chunked_observation_requests
        _load_observation_checkpoint_state _record_shard_result _split_shard_for_retry_async
        _store_shard_result _year_windows
    """.split()),
    (_loaders, """
        _bulk_country_values _existing_observation_ids _fetch_remote_bulk_rows
        _filter_rows_by_series_constraints _iter_eurostat_bulk_records
        _iter_ilo_bulk_records _iter_uis_bulk_records _load_wvs_bulk_rows
        _merge_observation_stats _records_from_payload _seed_alignments_path _wvs_bulk_csv_path
    """.split()),
    (_registry, """
        _build_catalog_alignments _build_catalog_observation_plans _build_support_sketches
        _build_observation_shards_from_sketches _ensure_registry_tables
        _limit_observation_plans _load_catalog_transport_datasets
        _resolve_catalog_update_frequency _upsert_catalog_alignments
    """.split()),
    (_transformers, """
        _as_float _as_int _canonicalize_observation_request_filters
        _eurostat_filters_for_country _filters_to_tuple _normalize_observation_row
        _observation_id _observation_payload_row_limit _rewrite_sdmx_requests_with_dimension_key
        _shard_countries _to_iso3
    """.split()),
    (_api, """
        _fetch_observation_rows
        _ingest_catalog_observations _ingest_catalog_observations_parallel
        _run_core_sources_ingest_async _resolve_profile_config _resolve_source_execution_policy
        _TRANSPORT_SOURCES _OBSERVATION_INSERT_BATCH_SIZE _DEFAULT_OBSERVATION_YEAR_WINDOW
    """.split()),
):
    _BINDINGS.update({name: (_module, name) for name in _names})

# Selected imported names are part of the historical test seam as well.
for _name in (
    "asyncio",
    "run_coro_sync",
    "AsyncFetchLease",
    "ConnectionConfig",
    "DatasetCapabilitySnapshot",
    "FetchRequest",
    "SourceExecutionPolicy",
):
    _BINDINGS.setdefault(_name, (_api, _name))

_COMPATIBILITY_CALLS = frozenset(
    {
        "_bulk_country_values",
        "_fetch_observation_rows",
        "_ingest_catalog_observations",
        "_insert_generic_observations",
        "_load_wvs_bulk_rows",
        "_run_core_sources_ingest_async",
        "_wvs_bulk_csv_path",
    }
)
_LOCAL_NAMES = frozenset(
    {"run_core_sources_ingest", "run_core_sources_ingest_async", "_sync_implementation_globals"}
)


@contextmanager
def _temporary_compatibility_overrides() -> Iterator[None]:
    """Bind only supported facade overrides to this execution context."""
    overrides_by_module: dict[ModuleType, dict[str, Any]] = {}
    for name, (module, owner_name) in _BINDINGS.items():
        if name in _LOCAL_NAMES or name not in globals():
            continue
        replacement = globals()[name]
        current = getattr(module, owner_name, None)
        if replacement is current:
            continue
        overrides_by_module.setdefault(module, {})[owner_name] = replacement

    applied: list[tuple[Any, Any]] = []
    try:
        for module, overrides in overrides_by_module.items():
            context_overrides = module._COMPATIBILITY_OVERRIDES
            current = context_overrides.get() or {}
            token = context_overrides.set({**current, **overrides})
            applied.append((context_overrides, token))
        yield
    finally:
        for context_overrides, token in reversed(applied):
            context_overrides.reset(token)


def _compatibility_delegate(name: str, target: Any) -> Any:
    """Return a bounded delegate that scopes supported monkeypatch seams."""
    if not callable(target):
        return target
    if inspect.iscoroutinefunction(target):

        @wraps(target)
        async def _async_delegate(*args: Any, **kwargs: Any) -> Any:
            with _temporary_compatibility_overrides():
                return await target(*args, **kwargs)

        return _async_delegate

    @wraps(target)
    def _delegate(*args: Any, **kwargs: Any) -> Any:
        with _temporary_compatibility_overrides():
            return target(*args, **kwargs)

    return _delegate


def __getattr__(name: str) -> Any:
    """Resolve an explicit compatibility binding from its owning leaf."""
    binding = _BINDINGS.get(name)
    if binding is None:
        raise AttributeError(name)
    module, owner_name = binding
    target = getattr(module, owner_name)
    if name in _COMPATIBILITY_CALLS:
        return _compatibility_delegate(name, target)
    return target


def _sync_implementation_globals() -> None:
    """Retained as a no-op compatibility hook; no globals are broadcast."""


async def run_core_sources_ingest_async(config: Any) -> CoreSourcesIngestStats:
    """Run the canonical API while honoring bounded legacy test seams."""
    with _temporary_compatibility_overrides():
        return await _api.run_core_sources_ingest_async(config)


def run_core_sources_ingest(config: Any) -> CoreSourcesIngestStats:
    """Run the canonical API from synchronous callers."""
    from polisyos.common.async_tools import run_coro_sync

    return run_coro_sync(run_core_sources_ingest_async(config))


__all__ = ["CoreSourcesIngestStats", "run_core_sources_ingest"]
