"""Contract models for the catalog core-sources ingest stage."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
]
