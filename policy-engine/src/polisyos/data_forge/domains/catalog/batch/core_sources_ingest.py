"""Stage 0b: ingest transportability sources into registry/alignment/observation tables.

Compatibility facade for the implementation split under ``core_sources``.
"""

from __future__ import annotations

import inspect
from functools import wraps
from types import ModuleType
from typing import Any, Callable

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
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
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    api as _api,
    loaders as _loaders,
    registry as _registry,
    transformers as _transformers,
    validators as _validators,
    writers as _writers,
)

logger = get_logger(__name__)

_IMPLEMENTATION_MODULES: tuple[ModuleType, ...] = (
    _writers,
    _validators,
    _loaders,
    _registry,
    _transformers,
    _api,
)

# The translated leaf group is no longer a recipient of arbitrary facade
# globals.  These are the existing compatibility seams that may still be
# overridden by facade-level monkeypatches while each leaf resolves its
# canonical owner when no override is present.
__TARGET_LEAF_COMPATIBILITY_NAMES: dict[ModuleType, frozenset[str]] = {
    _loaders: frozenset(
        {
            "_WVSObservationAccumulator",
            "_as_float",
            "_as_int",
            "_country_to_numeric",
            "_execute_source_fetch",
            "_extract_year",
            "_filters_to_tuple",
            "_load_json_dict",
            "_normalize_country_code",
            "_normalize_observation_row",
            "_shard_countries",
            "_to_iso3",
            "_wvs_bulk_csv_path",
        }
    ),
    _validators: frozenset(
        {
            "_build_observation_shards_from_sketches",
            "_build_support_sketches",
            "_canonicalize_observation_request_filters",
            "_eurostat_filters_for_countries",
            "_execute_source_fetch",
            "_filters_to_tuple",
            "_is_explicit_unsupported_error",
            "_load_json_dict",
            "_observation_frequency_rank",
            "_planner_error_status_code",
            "_policy_attr",
            "_policy_bool_attr",
            "_policy_int_attr",
            "_records_from_payload",
            "_resolve_source_execution_policy",
            "_sdmx_filters_for_countries",
            "_strip_geo_filters",
            "_to_iso3",
        }
    ),
    _writers: frozenset(
        {
            "_ensure_observation_index_compatibility",
            "_ensure_observation_provenance_columns",
            "_existing_observation_ids",
            "_iter_chunked_values",
            "_load_wvs_bulk_duckdb",
            "_load_wvs_bulk_rows",
            "_merge_observation_stats",
            "_normalize_observation_row",
            "_observation_id",
            "_records_from_payload",
            "_resolve_profile_config",
            "_upsert_catalog_alignments",
            "_wvs_legacy_indicators",
        }
    ),
}
_DELEGATES: dict[str, Callable[..., Any]] = {}
_INTERNAL_NAMES = {
    "Any",
    "Callable",
    "ModuleType",
    "_DELEGATES",
    "_IMPLEMENTATION_MODULES",
    "_INTERNAL_NAMES",
    "_make_delegate",
    "_sync_implementation_globals",
    "inspect",
    "wraps",
}


def _sync_implementation_globals() -> None:
    public_state = {
        name: value
        for name, value in globals().items()
        if name not in _INTERNAL_NAMES and not name.startswith("__")
    }
    for module in _IMPLEMENTATION_MODULES:
        allowed = __TARGET_LEAF_COMPATIBILITY_NAMES.get(module)
        if allowed is None:
            module.__dict__.update(public_state)
            continue
        module.__dict__.update(
            {name: public_state[name] for name in allowed if name in public_state}
        )


def _make_delegate(name: str, target: Callable[..., Any]) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(target):

        @wraps(target)
        async def _async_delegate(*args: Any, **kwargs: Any) -> Any:
            _sync_implementation_globals()
            return await target(*args, **kwargs)

        _async_delegate.__module__ = __name__
        return _async_delegate

    @wraps(target)
    def _delegate(*args: Any, **kwargs: Any) -> Any:
        _sync_implementation_globals()
        return target(*args, **kwargs)

    _delegate.__module__ = __name__
    return _delegate


for _module in _IMPLEMENTATION_MODULES:
    for _name, _value in vars(_module).items():
        if _name.startswith("__") or _name in _INTERNAL_NAMES:
            continue
        if inspect.isfunction(_value):
            _DELEGATES[_name] = _value
            globals()[_name] = _make_delegate(_name, _value)
        else:
            globals()[_name] = _value


def run_core_sources_ingest(config: Any) -> CoreSourcesIngestStats:
    """Run the core-source ingest stage from synchronous callers."""
    return run_coro_sync(run_core_sources_ingest_async(config))


async def run_core_sources_ingest_async(config: Any) -> CoreSourcesIngestStats:
    """Run the core-source ingest stage and publish its manifest."""
    _sync_implementation_globals()
    return await _DELEGATES["run_core_sources_ingest_async"](config)


__all__ = ["CoreSourcesIngestStats", "run_core_sources_ingest"]
