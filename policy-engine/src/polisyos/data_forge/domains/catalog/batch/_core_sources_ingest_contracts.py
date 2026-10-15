"""Contract models for the catalog core-sources ingest stage."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Iterator, Mapping
    from datetime import datetime


# Finite compatibility surface shared by the facade and the leaf resolvers.
# The public facade name currently equals its owning leaf symbol; the key is
# the complete owner/symbol pair and the value is its immutable resolution target.
CORE_SOURCES_COMPATIBILITY_BINDINGS: Mapping[tuple[str, str], tuple[str, str]] = MappingProxyType(
    {
        ("writers", "_ConnectorSessionCache"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_ConnectorSessionCache",
        ),
        ("writers", "_capability_snapshot_cache_key"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_capability_snapshot_cache_key",
        ),
        ("writers", "_format_duckdb_memory_limit"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_format_duckdb_memory_limit",
        ),
        ("writers", "_hydrate_support_sketch_dimension_orders"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_hydrate_support_sketch_dimension_orders",
        ),
        ("writers", "_hydrate_work_package_dimension_orders"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_hydrate_work_package_dimension_orders",
        ),
        ("writers", "_infer_ilo_dimension_order"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_infer_ilo_dimension_order",
        ),
        ("writers", "_insert_generic_observations"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_insert_generic_observations",
        ),
        ("writers", "_legacy_ingest_observations"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_legacy_ingest_observations",
        ),
        ("writers", "_support_sketch_id"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_support_sketch_id",
        ),
        ("writers", "_upsert_legacy_registry_datasets"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_upsert_legacy_registry_datasets",
        ),
        ("writers", "_upsert_seed_alignments"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_upsert_seed_alignments",
        ),
        ("validators", "_append_shard_result"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
            "_append_shard_result",
        ),
        ("validators", "_build_observation_shards"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
            "_build_observation_shards",
        ),
        ("validators", "_chunked_observation_requests"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
            "_chunked_observation_requests",
        ),
        ("validators", "_load_observation_checkpoint_state"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
            "_load_observation_checkpoint_state",
        ),
        ("validators", "_record_shard_result"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
            "_record_shard_result",
        ),
        ("validators", "_split_shard_for_retry_async"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
            "_split_shard_for_retry_async",
        ),
        ("validators", "_store_shard_result"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
            "_store_shard_result",
        ),
        ("validators", "_year_windows"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
            "_year_windows",
        ),
        ("loaders", "_bulk_country_values"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_bulk_country_values",
        ),
        ("loaders", "_existing_observation_ids"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_existing_observation_ids",
        ),
        ("loaders", "_fetch_remote_bulk_rows"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_fetch_remote_bulk_rows",
        ),
        ("loaders", "_filter_rows_by_series_constraints"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_filter_rows_by_series_constraints",
        ),
        ("loaders", "_iter_eurostat_bulk_records"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_iter_eurostat_bulk_records",
        ),
        ("loaders", "_iter_ilo_bulk_records"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_iter_ilo_bulk_records",
        ),
        ("loaders", "_iter_uis_bulk_records"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_iter_uis_bulk_records",
        ),
        ("loaders", "_load_wvs_bulk_rows"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_load_wvs_bulk_rows",
        ),
        ("loaders", "_merge_observation_stats"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_merge_observation_stats",
        ),
        ("loaders", "_records_from_payload"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_records_from_payload",
        ),
        ("loaders", "_seed_alignments_path"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_seed_alignments_path",
        ),
        ("loaders", "_wvs_bulk_csv_path"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_wvs_bulk_csv_path",
        ),
        ("registry", "_build_catalog_alignments"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_build_catalog_alignments",
        ),
        ("registry", "_build_catalog_observation_plans"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_build_catalog_observation_plans",
        ),
        ("registry", "_build_support_sketches"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_build_support_sketches",
        ),
        ("registry", "_build_observation_shards_from_sketches"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_build_observation_shards_from_sketches",
        ),
        ("registry", "_ensure_registry_tables"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_ensure_registry_tables",
        ),
        ("registry", "_limit_observation_plans"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_limit_observation_plans",
        ),
        ("registry", "_load_catalog_transport_datasets"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_load_catalog_transport_datasets",
        ),
        ("registry", "_resolve_catalog_update_frequency"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_resolve_catalog_update_frequency",
        ),
        ("registry", "_upsert_catalog_alignments"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_upsert_catalog_alignments",
        ),
        ("transformers", "_as_float"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_as_float",
        ),
        ("transformers", "_as_int"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_as_int",
        ),
        ("transformers", "_canonicalize_observation_request_filters"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_canonicalize_observation_request_filters",
        ),
        ("transformers", "_eurostat_filters_for_country"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_eurostat_filters_for_country",
        ),
        ("transformers", "_filters_to_tuple"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_filters_to_tuple",
        ),
        ("transformers", "_normalize_observation_row"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_normalize_observation_row",
        ),
        ("transformers", "_observation_id"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_observation_id",
        ),
        ("transformers", "_observation_payload_row_limit"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_observation_payload_row_limit",
        ),
        ("transformers", "_rewrite_sdmx_requests_with_dimension_key"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_rewrite_sdmx_requests_with_dimension_key",
        ),
        ("transformers", "_shard_countries"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_shard_countries",
        ),
        ("transformers", "_to_iso3"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.transformers",
            "_to_iso3",
        ),
        ("api", "_fetch_observation_rows"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "_fetch_observation_rows",
        ),
        ("api", "_ingest_catalog_observations"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "_ingest_catalog_observations",
        ),
        ("api", "_ingest_catalog_observations_parallel"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "_ingest_catalog_observations_parallel",
        ),
        ("api", "_run_core_sources_ingest_async"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "_run_core_sources_ingest_async",
        ),
        ("api", "_resolve_profile_config"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "_resolve_profile_config",
        ),
        ("api", "_resolve_source_execution_policy"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "_resolve_source_execution_policy",
        ),
        ("registry", "_TRANSPORT_SOURCES"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.registry",
            "_TRANSPORT_SOURCES",
        ),
        ("writers", "_OBSERVATION_INSERT_BATCH_SIZE"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_OBSERVATION_INSERT_BATCH_SIZE",
        ),
        ("validators", "_DEFAULT_OBSERVATION_YEAR_WINDOW"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.validators",
            "_DEFAULT_OBSERVATION_YEAR_WINDOW",
        ),
        ("api", "asyncio"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "asyncio",
        ),
        ("api", "run_coro_sync"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "run_coro_sync",
        ),
        ("api", "AsyncFetchLease"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "AsyncFetchLease",
        ),
        ("api", "ConnectionConfig"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "ConnectionConfig",
        ),
        ("api", "DatasetCapabilitySnapshot"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "DatasetCapabilitySnapshot",
        ),
        ("api", "FetchRequest"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "FetchRequest",
        ),
        ("api", "SourceExecutionPolicy"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.api",
            "SourceExecutionPolicy",
        ),
    }
)


@dataclass(frozen=True, slots=True)
class CoreSourcesCompatibilityContext:
    """Immutable request-scoped bindings for the compatibility facade.

    Construction copies and freezes the mapping and validates its keys. It does
    not validate values against the owning module's callable or data contract;
    compatibility overrides are a developer seam and must be substitution-
    compatible with the owner binding. A malformed value may fail when the
    consumer uses it. This context carries no authority or evidence predicate.
    """

    bindings: Mapping[tuple[str, str], Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        copied: dict[tuple[str, str], Any] = {}
        for key, value in self.bindings.items():
            if (
                not isinstance(key, tuple)
                or len(key) != 2
                or not all(isinstance(part, str) and part for part in key)
            ):
                raise ValueError("compatibility binding keys must be (module, name) pairs")
            copied[key] = value
        object.__setattr__(self, "bindings", MappingProxyType(copied))

    def resolve(self, module_name: str, name: str) -> tuple[bool, Any]:
        """Return a scoped override and whether this context defines it."""
        key = (module_name, name)
        return (key in self.bindings, self.bindings.get(key))


_CORE_SOURCES_COMPATIBILITY_CONTEXT: ContextVar[CoreSourcesCompatibilityContext | None] = (
    ContextVar("core_sources_compatibility_context", default=None)
)


@contextmanager
def bind_core_sources_compatibility_context(
    context: CoreSourcesCompatibilityContext,
) -> Iterator[None]:
    """Bind immutable compatibility values to the current async execution context."""
    token: Token[CoreSourcesCompatibilityContext | None] = _CORE_SOURCES_COMPATIBILITY_CONTEXT.set(
        context
    )
    try:
        yield
    finally:
        _CORE_SOURCES_COMPATIBILITY_CONTEXT.reset(token)


def current_core_sources_compatibility_context() -> CoreSourcesCompatibilityContext | None:
    """Return the immutable compatibility context active in this execution context."""
    return _CORE_SOURCES_COMPATIBILITY_CONTEXT.get()


def resolve_core_sources_compatibility_binding(module_name: str, name: str) -> tuple[bool, Any]:
    """Resolve one binding from the current request context, if present."""
    context = _CORE_SOURCES_COMPATIBILITY_CONTEXT.get()
    if context is None:
        return False, None
    return context.resolve(module_name, name)


@dataclass
class CoreSourcesIngestStats:
    """Core sources ingest stats public type."""

    registry_datasets: int = 0
    variable_alignments: int = 0
    observations: int = 0
    observations_attempted: int = 0
    observations_inserted: int = 0
    observations_replaced: int = 0
    failures: int = 0
    completed_shards: int = 0
    deferred_shards: int = 0
    failed_shards: int = 0
    empty_shards: int = 0
    observations_by_source: dict[str, int] | None = None
    _progress_metadata: dict[str, Any] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.observations_by_source is None:
            self.observations_by_source = {}

    def record_source_observations(self, source: str, count: int) -> None:
        if self.observations_by_source is None:
            self.observations_by_source = {}
        self.observations_by_source[source] = self.observations_by_source.get(source, 0) + count


@dataclass(frozen=True)
class ObservationInsertStats:
    """Observation insert stats public type."""

    attempted: int = 0
    inserted: int = 0
    replaced: int = 0

    @property
    def written(self) -> int:
        return int(self.inserted + self.replaced)

    def __add__(self, other: object) -> ObservationInsertStats:
        if not isinstance(other, ObservationInsertStats):
            return NotImplemented
        return ObservationInsertStats(
            attempted=self.attempted + other.attempted,
            inserted=self.inserted + other.inserted,
            replaced=self.replaced + other.replaced,
        )

    def __radd__(self, other: object) -> ObservationInsertStats:
        if other == 0:
            return self
        return self.__add__(other)


@dataclass(frozen=True)
class CatalogTransportDataset:
    """Catalog transport dataset public type."""

    catalog_dataset_id: str
    source: str
    title: str
    description: str
    source_dataset_id: str
    update_frequency: str
    last_updated: str
    coverage_json: str
    access_json: str
    execution_tier: str
    variables: tuple[str, ...]
    keywords: tuple[str, ...]
    themes: tuple[str, ...]
    polisyos_metrics: tuple[str, ...]
    connector_id: str
    profile_id: str
    request_dataset_id: str
    default_filters: dict[str, list[str]]


@dataclass(frozen=True)
class ObservationPlan:
    """Observation plan data model."""

    dataset_id: str
    source: str
    raw_variable: str
    canonical_var: str
    connector_id: str
    profile_id: str
    request_dataset_id: str
    default_filters: dict[str, list[str]]
    update_frequency: str
    source_watermark: str = ""
    dataset_version: str = ""


@dataclass(frozen=True)
class ObservationShard:
    """Observation shard public type."""

    shard_id: str
    plan: ObservationPlan
    country_code: str | None
    start_year: int
    end_year: int
    filters: dict[str, list[str]]
    country_codes: tuple[str, ...] = ()
    split_depth: int = 0
    phase: str = "publishable_core"
    acquisition_method: str = ""
    source_watermark: str = ""
    dataset_version: str = ""
    dimension_order: tuple[str, ...] = ()


@dataclass(frozen=True)
class SupportSketch:
    """Support sketch public type."""

    sketch_id: str
    plan: ObservationPlan
    dataset_version: str
    supported_countries: tuple[str, ...]
    time_range: tuple[int, int]
    allowed_dimension_values: dict[str, tuple[str, ...]]
    estimated_cardinality: int
    source_watermark: str
    recommended_core_transport: str
    recommended_backfill_transport: str
    dimension_order: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservationShardResult:
    """Observation shard result data model."""

    shard_id: str
    status: str
    source: str
    dataset_id: str
    raw_variable: str
    canonical_var: str
    country_code: str | None
    start_year: int
    end_year: int
    row_count: int = 0
    error: str = ""


@dataclass(frozen=True)
class DeferredObservationPlan:
    """Deferred observation plan data model."""

    shard_id: str
    source: str
    dataset_id: str
    raw_variable: str
    canonical_var: str
    country_code: str | None
    start_year: int
    end_year: int
    filters: dict[str, list[str]]
    reason: str
    split_depth: int = 0


@dataclass(frozen=True)
class ObservationFetchKey:
    """Observation fetch key public type."""

    source: str
    request_dataset_id: str
    filters_json: str
    countries_json: str
    start_year: int
    end_year: int
    profile_id: str = ""
    input_basis_identity: str = ""


@dataclass(frozen=True)
class ObservationFetchPayload:
    """Observation fetch payload public type."""

    rows: list[dict[str, Any]]
    request_count: int = 0
    bytes_downloaded: int = 0
    acquisition_method: str = ""
    source_watermark: str = ""
    dataset_version: str = ""


@dataclass(frozen=True)
class ObservationWriteItem:
    """Observation write item public type."""

    shard: ObservationShard
    payload: ObservationFetchPayload
    ack: asyncio.Future[ObservationInsertStats]

    @property
    def row_count(self) -> int:
        return len(self.payload.rows)

    @property
    def estimated_bytes(self) -> int:
        if self.payload.bytes_downloaded > 0:
            return int(self.payload.bytes_downloaded)
        return len(
            json.dumps(self.payload.rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )


@dataclass(frozen=True)
class ObservationResultItem:
    """Observation result item public type."""

    result: ObservationShardResult
    support_key: str = ""
    mark_unsupported: bool = False


@dataclass
class _SourceBudgetWindow:
    window_started_at: datetime
    requests_used: int = 0


@dataclass
class _ObservationRuntimeMetrics:
    current_phase: str = "planning"
    inflight_by_source: dict[str, int] = field(default_factory=dict)
    completed_by_source: dict[str, int] = field(default_factory=dict)
    empty_by_source: dict[str, int] = field(default_factory=dict)
    rows_by_source: dict[str, int] = field(default_factory=dict)
    deferred_by_reason: dict[str, int] = field(default_factory=dict)
    queue_backlog_by_source: dict[str, int] = field(default_factory=dict)
    blocked_by_source: dict[str, int] = field(default_factory=dict)
    quota_wait_seconds_by_source: dict[str, float] = field(default_factory=dict)
    writer_backlog_rows: int = 0
    writer_flush_count: int = 0
    writer_flush_latency_ms: float = 0.0
    planner_pruned_shards: int = 0
    planned_work_packages: int = 0
    support_sketch_count: int = 0
    async_jobs_open: int = 0
    bytes_downloaded_by_source: dict[str, int] = field(default_factory=dict)
    request_count_by_source: dict[str, int] = field(default_factory=dict)


@dataclass
class WriterFlushState:
    """Writer flush state data model."""

    buffered_rows: int = 0
    buffered_bytes: int = 0
    flush_count: int = 0
    last_flush_at: float = 0.0
    last_flush_latency_ms: float = 0.0


__all__ = [
    "CatalogTransportDataset",
    "CoreSourcesCompatibilityContext",
    "CoreSourcesIngestStats",
    "DeferredObservationPlan",
    "ObservationFetchKey",
    "ObservationFetchPayload",
    "ObservationInsertStats",
    "ObservationPlan",
    "ObservationResultItem",
    "ObservationShard",
    "ObservationShardResult",
    "ObservationWriteItem",
    "SupportSketch",
    "WriterFlushState",
    "_ObservationRuntimeMetrics",
    "_SourceBudgetWindow",
    "bind_core_sources_compatibility_context",
    "resolve_core_sources_compatibility_binding",
]
