"""Stage 0b: ingest transportability sources into registry/alignment/observation tables."""

from __future__ import annotations

import asyncio
import contextlib
import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import time
import zipfile
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import aiohttp
import duckdb
import pandas as pd

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
from polisyos.data_forge.domains.catalog.batch.checkpoints import load_json, write_json
from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
    country_scope_members,
    iso2_to_iso3,
    iso2_to_numeric,
    normalize_country_code,
)
from polisyos.data_forge.domains.catalog.knowledge.proxy_penalties import metric_proxy_alignments
from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
    AlignmentMethod,
    VariableAlignment,
    align_semantic,
    calibrate_alignment_confidence,
    load_seed_alignments,
)
from polisyos.data_forge.kernel.pipeline.manifests import write_raw_manifest, write_stage_manifest
from polisyos.data_forge.read_api.academic import CANONICAL_VARIABLES
from polisyos.fabric.connectors.base import (
    AsyncFetchLease,
    ConnectionConfig,
    DatasetCapabilitySnapshot,
    FetchRequest,
)
from polisyos.fabric.connectors.profiles.models import SourceExecutionPolicy
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.profiles.resolver import (
    resolve_connection_config,
    resolve_execution_policy,
)
from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
from polisyos.fabric.connectors.sources.sdmx_source import SDMXSourceConnector
from polisyos.fabric.connectors.sources.unesco_uis import UNESCOUISConnector
from polisyos.fabric.connectors.sources.unpd import UNPDConnector
from polisyos.fabric.connectors.sources.who import WHOConnector
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

if TYPE_CHECKING:
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig

logger = get_logger(__name__)

_TRANSPORT_SOURCES = frozenset(
    {
        "worldbank",
        "eurostat",
        "oecd",
        "ilo",
        "who",
        "unpd",
        "wvs",
        "unesco_uis",
    }
)
_LEGACY_WGI_INDICATORS: dict[str, str] = {
    "RL.EST": "institutional_quality",
    "CC.EST": "corruption_level",
    "GE.EST": "state_capacity",
}
_LEGACY_WDI_INDICATORS: dict[str, str] = {
    "NY.GDP.PCAP.PP.CD": "gdp_per_capita",
}
_LEGACY_WVS_INDICATORS_STATIC: dict[str, str] = {
    "A165": "social_trust",
    "A173": "cultural_cluster",
}
_CANONICAL_ROOTS = tuple(sorted(CANONICAL_VARIABLES.keys()))
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WVS_SPECIAL_AGGREGATIONS_STATIC: dict[str, str] = {"A165": "weighted_share_response_1"}
_WVS_WEIGHT_FIELDS: tuple[str, ...] = ("S017", "S018")
_OBSERVATION_INSERT_BATCH_SIZE = 500
_DEFAULT_OBSERVATION_YEAR_WINDOW: tuple[int, int] = (2018, 2022)
_EUROSTAT_SUBANNUAL_TITLE_TOKENS: tuple[str, ...] = (
    "month",
    "monthly",
    "quarter",
    "quarterly",
    "mensuel",
    "mensuelle",
    "monat",
    "monatlich",
    "quartal",
    "viertelj",
    "trimestr",
)
_DEFAULT_SOURCE_CONCURRENCY: dict[str, int] = {
    "eurostat": 3,
    "worldbank": 4,
    "who": 2,
    "unesco_uis": 2,
    "unpd": 1,
    "oecd": 1,
    "ilo": 1,
    "wvs": 1,
}
_SOURCE_LANE_DEFAULTS: dict[str, int] = {
    "eurostat": 1,
    "oecd": 1,
    "worldbank": 2,
    "who": 1,
    "unesco_uis": 1,
    "ilo": 1,
    "unpd": 1,
    "wvs": 1,
}
_SERIAL_HARVEST_FAMILIES: frozenset[str] = frozenset({"ckan"})
_SERIAL_HARVEST_SOURCES: frozenset[str] = frozenset(
    {
        "data_gov_ua_broad",
        "data_gov_ro_broad",
        "data_gov_md_broad",
        "data_gov_pl_broad",
    }
)
_OBSERVATION_PROGRESS_INTERVAL_SECONDS = 60.0
_FETCH_RESULT_CACHE_SIZE = 256
_OBSERVATION_UNSUPPORTED_EMPTY_THRESHOLD = 2
_OBSERVATION_WRITER_FLUSH_ROWS = 8_000
_OBSERVATION_WRITER_FLUSH_BYTES = 8 * 1024 * 1024
_OBSERVATION_WRITER_FLUSH_SECONDS = 5.0
_OBSERVATION_WRITER_IDLE_FLUSH_SECONDS = 0.25
_OBSERVATION_WRITER_CHECKPOINT_EVERY = 10
_OBSERVATION_WRITER_TRANSACTION_ROWS = 2_000
_OBSERVATION_WRITER_TRANSACTION_ITEMS = 8
_OBSERVATION_WRITER_MIN_MEMORY_LIMIT_BYTES = 4 * 1024 * 1024 * 1024
_OBSERVATION_WRITER_MAX_MEMORY_LIMIT_BYTES = 24 * 1024 * 1024 * 1024
_OBSERVATION_WRITER_MEMORY_LIMIT_FRACTION = 0.60
_CAPABILITY_NEGATIVE_STATUS_CODES = frozenset({404, 405})
_RATE_LIMITED_LOG_COUNTS: dict[str, int] = {}
_BULK_MATERIALIZATION_LOCKS: dict[str, asyncio.Lock] = {}
_ILO_INFERRED_DIMENSION_TOKENS: frozenset[str] = frozenset(
    {
        "AGE",
        "CAT",
        "CBR",
        "CCT",
        "CHL",
        "CUR",
        "DSB",
        "DUR",
        "EC2",
        "ECO",
        "EDU",
        "EST",
        "GEO",
        "HHT",
        "HOW",
        "IND",
        "INS",
        "JOB",
        "MJH",
        "MTS",
        "OC2",
        "OCU",
        "SEX",
        "STU",
    }
)




def run_core_sources_ingest(config: DatasetBatchConfig) -> CoreSourcesIngestStats:
    """Sync wrapper for ingesting registry/observation data used by DatasetRegistry."""
    return run_coro_sync(run_core_sources_ingest_async(config))


async def run_core_sources_ingest_async(config: DatasetBatchConfig) -> CoreSourcesIngestStats:
    """Async entrypoint for ingesting registry/observation data used by DatasetRegistry."""
    started_at = datetime.now(UTC).isoformat()
    stats = await _run_core_sources_ingest_async(config)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "core_sources_ingest.json",
        stage="core_sources_ingest",
        status="ok" if stats.failures == 0 else "warning",
        metrics={
            "registry_datasets": stats.registry_datasets,
            "variable_alignments": stats.variable_alignments,
            "observations": stats.observations,
            "observations_attempted": stats.observations_attempted,
            "observations_inserted": stats.observations_inserted,
            "observations_replaced": stats.observations_replaced,
            "failures": stats.failures,
            "completed_shards": stats.completed_shards,
            "deferred_shards": stats.deferred_shards,
            "failed_shards": stats.failed_shards,
            "empty_shards": stats.empty_shards,
            "observations_by_source": stats.observations_by_source or {},
        },
        artifacts=[config.db_path],
        started_at=started_at,
    )
    return stats


async def _run_core_sources_ingest_async(config: DatasetBatchConfig) -> CoreSourcesIngestStats:
    stats = CoreSourcesIngestStats()
    catalog_datasets: list[CatalogTransportDataset] = []
    catalog_alignments: list[VariableAlignment] = []
    with duckdb.connect(str(config.db_path)) as con:
        _ensure_registry_tables(con)
        catalog_datasets = _load_catalog_transport_datasets(con, config)
        if catalog_datasets:
            catalog_alignments = _build_catalog_alignments(
                catalog_datasets, _seed_alignments_path()
            )
            stats.registry_datasets = _upsert_catalog_registry_datasets(con, catalog_datasets)
            stats.variable_alignments = _upsert_catalog_alignments(con, catalog_alignments)
            _upsert_alignment_audit(con, catalog_alignments)
        else:
            stats.registry_datasets = _upsert_legacy_registry_datasets(con)
            stats.variable_alignments = _upsert_seed_alignments(con, _seed_alignments_path())
            _upsert_alignment_audit(con, load_seed_alignments(_seed_alignments_path()))

    if catalog_datasets:
        plans = _build_catalog_observation_plans(
            catalog_datasets,
            catalog_alignments,
            config=config,
        )
        ingest_stats = await _ingest_catalog_observations(config.db_path, plans, config=config)
        stats.observations += ingest_stats.observations
        stats.observations_attempted += ingest_stats.observations_attempted
        stats.observations_inserted += ingest_stats.observations_inserted
        stats.observations_replaced += ingest_stats.observations_replaced
        stats.failures += ingest_stats.failures
        stats.completed_shards += ingest_stats.completed_shards
        stats.deferred_shards += ingest_stats.deferred_shards
        stats.failed_shards += ingest_stats.failed_shards
    else:
        legacy_stats = await _legacy_ingest_observations(config.db_path)
        stats.observations += legacy_stats.observations
        stats.observations_attempted += legacy_stats.observations_attempted
        stats.observations_inserted += legacy_stats.observations_inserted
        stats.observations_replaced += legacy_stats.observations_replaced
        stats.failures += legacy_stats.failures

    return stats


def _resolve_profile_config(profile_id: str) -> ConnectionConfig:
    registry = SourceProfileRegistry.get_instance()
    profile = registry.get(profile_id)
    if profile is None:
        raise ValueError(f"Missing source profile: {profile_id}")
    config = resolve_connection_config(profile)
    if profile_id != "unpd_dataportal":
        return config
    token = str(os.getenv("POLISYOS_UNPD_API_TOKEN") or "").strip()
    if not token or config.auth_credentials.get("token"):
        return config
    auth_credentials = dict(config.auth_credentials)
    auth_credentials["token"] = token
    return ConnectionConfig(
        url=config.url,
        headers=dict(config.headers),
        auth_method=config.auth_method or "bearer",
        auth_credentials=auth_credentials,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.max_retries,
        retry_delay_seconds=config.retry_delay_seconds,
        rate_limit_rps=config.rate_limit_rps,
        max_connections=config.max_connections,
        keepalive_seconds=config.keepalive_seconds,
        verify_ssl=config.verify_ssl,
        ca_bundle_path=config.ca_bundle_path,
    )


def _legacy_serial_mode_enabled() -> bool:
    value = str(os.getenv("POLISYOS_DATASET_LEGACY_SERIAL") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _resolve_source_execution_policy(
    *,
    source: str,
    profile_id: str,
) -> SourceExecutionPolicy:
    registry = SourceProfileRegistry.get_instance()
    profile = registry.get(profile_id) if profile_id else None
    if profile is not None:
        policy = resolve_execution_policy(profile)
        if _policy_int_attr(policy, "max_concurrency", 1) >= 1:
            return policy
    return SourceExecutionPolicy(
        profile_id=profile_id or source,
        max_concurrency=max(1, _DEFAULT_SOURCE_CONCURRENCY.get(source, 1)),
        preferred_core_transport="default",
        preferred_backfill_transport="default",
        fallback_on_capability_failure="plan_without_capability",
        negative_cache_ttl_hours=24,
        soft_negative_cache_ttl_hours=12,
    )


def _policy_attr(policy: SourceExecutionPolicy, name: str, default: Any) -> Any:
    return getattr(policy, name, default)


def _policy_str_attr(policy: SourceExecutionPolicy, name: str, default: str) -> str:
    value = _policy_attr(policy, name, default)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _policy_int_attr(policy: SourceExecutionPolicy, name: str, default: int) -> int:
    value = _policy_attr(policy, name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _policy_optional_int_attr(
    policy: SourceExecutionPolicy,
    name: str,
    default: int | None = None,
) -> int | None:
    value = _policy_attr(policy, name, default)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _policy_bool_attr(policy: SourceExecutionPolicy, name: str, default: bool = False) -> bool:
    value = _policy_attr(policy, name, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
async def _ingest_catalog_observations(
    db_path: Path,
    plans: list[ObservationPlan],
    *,
    config: DatasetBatchConfig,
) -> CoreSourcesIngestStats:
    if _legacy_serial_mode_enabled():
        logger.warning(
            "Using legacy serial observation ingest because POLISYOS_DATASET_LEGACY_SERIAL is enabled"
        )
        return await _ingest_catalog_observations_legacy(db_path, plans, config=config)
    return await _ingest_catalog_observations_parallel(db_path, plans, config=config)


async def _ingest_catalog_observations_parallel(
    db_path: Path,
    plans: list[ObservationPlan],
    *,
    config: DatasetBatchConfig,
) -> CoreSourcesIngestStats:
    stats = CoreSourcesIngestStats()
    if not plans:
        return stats

    cache = _ConnectorSessionCache()
    fetch_deduper = _ObservationFetchDeduper()
    checkpoint_state = _load_observation_checkpoint_state(config)
    completed = checkpoint_state["completed"]
    failed = checkpoint_state["failed"]
    deferred = checkpoint_state["deferred"]
    unsupported_signatures = _prune_expired_support_cache(
        checkpoint_state["unsupported_signatures"]
    )
    empty_signatures = _prune_expired_support_cache(checkpoint_state["empty_signatures"])
    inflight_leases = checkpoint_state["inflight_leases"]
    async_fetch_leases = checkpoint_state["async_fetch_leases"]
    capability_failures = _prune_expired_capability_failures(
        checkpoint_state["capability_failures"]
    )
    capability_cache = _ObservationCapabilityCache(
        _load_capability_snapshot_state(checkpoint_state["capability_snapshots"])
    )
    budget_windows = _load_source_budget_windows(checkpoint_state["source_budgets"])
    persisted_support_sketches = _load_support_sketch_state(checkpoint_state["support_sketches"])
    persisted_work_packages = _load_work_package_state(checkpoint_state["work_packages"])
    persisted_planner_phase = str(checkpoint_state["planner_phase"] or "support_sketch")
    publishable_core_complete = bool(checkpoint_state["publishable_core_complete"])
    planner_signature = str(checkpoint_state["planner_signature"] or "")
    persisted_capability_snapshots = await capability_cache.snapshot()
    persisted_support_sketches, hydrated_support_sketches = (
        _hydrate_support_sketch_dimension_orders(
            persisted_support_sketches,
            capability_snapshots=persisted_capability_snapshots,
        )
    )
    persisted_work_packages, hydrated_work_packages = _hydrate_work_package_dimension_orders(
        persisted_work_packages,
        support_sketches=persisted_support_sketches,
        capability_snapshots=persisted_capability_snapshots,
    )
    if hydrated_support_sketches > 0 or hydrated_work_packages > 0:
        _write_observation_checkpoint_state(
            config,
            completed=completed,
            failed=failed,
            deferred=deferred,
            unsupported_signatures=unsupported_signatures,
            empty_signatures=empty_signatures,
            inflight_leases=inflight_leases,
            async_fetch_leases=async_fetch_leases,
            capability_snapshots=checkpoint_state["capability_snapshots"],
            capability_failures=capability_failures,
            source_budgets=checkpoint_state["source_budgets"],
            writer_state=checkpoint_state["writer_state"],
            support_sketches=_serialize_support_sketch_state(persisted_support_sketches),
            work_packages=_serialize_work_package_state(persisted_work_packages),
            planner_phase=persisted_planner_phase,
            publishable_core_complete=publishable_core_complete,
            negative_cache_version=checkpoint_state["negative_cache_version"],
            planner_signature=planner_signature,
        )

    completed_results: list[dict[str, Any]] = []
    failed_results: list[dict[str, Any]] = []
    deferred_results: list[dict[str, Any]] = []
    source_summary: dict[str, dict[str, int]] = {}
    runtime_metrics = _ObservationRuntimeMetrics()
    runtime_lock = asyncio.Lock()
    done_event = asyncio.Event()
    writer_queue: asyncio.Queue[ObservationWriteItem | None] = asyncio.Queue()
    writer_state = _deserialize_writer_state(checkpoint_state["writer_state"])
    phase_state = {"value": "support_sketch"}
    advisory_prewarm_tasks: list[asyncio.Task[None]] = []

    source_queues: dict[str, asyncio.Queue[ObservationShard]] = {}
    source_policies: dict[str, SourceExecutionPolicy] = {
        plan.source: _resolve_source_execution_policy(
            source=plan.source, profile_id=plan.profile_id
        )
        for plan in plans
    }
    plan_capabilities: dict[str, DatasetCapabilitySnapshot | None] = {}
    support_sketches: dict[str, SupportSketch] = {}
    work_packages: dict[str, ObservationShard] = {}
    selected_work_package_ids: set[str] = set()
    pending = {"count": 0}
    core_pending = {"count": 0}
    selected_phases = set(_observation_mode_phases(config))
    start_monotonic = time.monotonic()
    phase_timings: dict[str, float | None] = {
        "support_sketch_started_at": start_monotonic,
        "publishable_core_started_at": None,
        "publishable_core_completed_at": None,
        "long_tail_backfill_started_at": None,
        "long_tail_backfill_completed_at": None,
    }

    async def _record_fetch_metrics(
        *,
        source: str,
        bytes_transferred: int = 0,
        request_count: int = 0,
    ) -> None:
        async with runtime_lock:
            runtime_metrics.request_count_by_source[source] = (
                runtime_metrics.request_count_by_source.get(source, 0) + int(request_count)
            )
            runtime_metrics.bytes_downloaded_by_source[source] = (
                runtime_metrics.bytes_downloaded_by_source.get(source, 0) + int(bytes_transferred)
            )

    async def _record_budget_block(
        *,
        source: str,
        sleep_seconds: float,
    ) -> None:
        async with runtime_lock:
            runtime_metrics.blocked_by_source[source] = (
                runtime_metrics.blocked_by_source.get(source, 0) + 1
            )
            runtime_metrics.quota_wait_seconds_by_source[source] = round(
                runtime_metrics.quota_wait_seconds_by_source.get(source, 0.0)
                + float(sleep_seconds),
                3,
            )

    def _record_initial_result(result: ObservationShardResult, *, source: str) -> None:
        _store_shard_result(
            result=result,
            completed=completed,
            failed=failed,
            deferred=deferred,
        )
        _append_shard_result(
            result=result,
            completed_results=completed_results,
            failed_results=failed_results,
            deferred_results=deferred_results,
            source_summary=source_summary,
        )
        if result.status.startswith("complete"):
            stats.completed_shards += 1
            runtime_metrics.completed_by_source[source] = (
                runtime_metrics.completed_by_source.get(source, 0) + 1
            )
            runtime_metrics.rows_by_source[source] = runtime_metrics.rows_by_source.get(
                source, 0
            ) + int(result.row_count)
            if result.status == "complete_empty":
                stats.empty_shards += 1
                runtime_metrics.empty_by_source[source] = (
                    runtime_metrics.empty_by_source.get(source, 0) + 1
                )
        else:
            stats.failures += 1
            if result.status == "failed":
                stats.failed_shards += 1
            else:
                stats.deferred_shards += 1
            reason_key = (result.error or result.status).split("\n", 1)[0][:120]
            runtime_metrics.deferred_by_reason[reason_key] = (
                runtime_metrics.deferred_by_reason.get(reason_key, 0) + 1
            )

    async def _persist_runtime_state() -> None:
        capability_state = _serialize_capability_snapshot_state(await capability_cache.snapshot())
        async with runtime_lock:
            budget_state = _serialize_source_budget_windows(budget_windows)
            leases = dict(inflight_leases)
            async_leases = dict(async_fetch_leases)
            unsupported_cache_state = dict(unsupported_signatures)
            empty_cache_state = dict(empty_signatures)
            capability_failure_state = dict(capability_failures)
            sketch_state = _serialize_support_sketch_state(support_sketches)
            work_package_state = _serialize_work_package_state(work_packages)
            source_core_completion_pct, source_full_completion_pct = (
                _source_completion_pct_by_phase(
                    work_packages,
                    completed=completed,
                    selected_phases=selected_phases,
                )
            )
            total_inflight = sum(
                int(value) for value in runtime_metrics.inflight_by_source.values()
            )
            backlog_total = sum(
                int(value) for value in runtime_metrics.queue_backlog_by_source.values()
            )
            blocked_sources = {
                key: int(value)
                for key, value in runtime_metrics.blocked_by_source.items()
                if int(value) > 0
            }
            current_phase = phase_state["value"]
            if runtime_metrics.writer_backlog_rows > 0:
                current_phase = "writing"
            elif total_inflight > 0:
                current_phase = "fetching"
            elif blocked_sources and backlog_total > 0:
                current_phase = "blocked_sources"
            elif pending["count"] <= 0 and deferred_results and not completed_results:
                current_phase = "deferred"
            runtime_metrics.current_phase = current_phase
            total_completed = max(int(sum(runtime_metrics.completed_by_source.values())), 0)
            total_empty = max(int(sum(runtime_metrics.empty_by_source.values())), 0)
            total_deferred = max(int(stats.deferred_shards + stats.failed_shards), 0)
            total_requests = max(int(sum(runtime_metrics.request_count_by_source.values())), 0)
            total_rows = max(int(sum(runtime_metrics.rows_by_source.values())), 0)
            rows_per_request = (
                round(float(total_rows) / float(total_requests), 2) if total_requests > 0 else 0.0
            )
            elapsed_total = max(time.monotonic() - start_monotonic, 0.0)
            time_to_publishable_core = (
                round(
                    float(phase_timings["publishable_core_completed_at"] or 0.0) - start_monotonic,
                    3,
                )
                if phase_timings["publishable_core_completed_at"] is not None
                else None
            )
            metadata = {
                "current_phase": runtime_metrics.current_phase,
                "observation_mode": str(getattr(config, "observation_mode", "all") or "all"),
                "planner_phase": phase_state["value"],
                "inflight_by_source": dict(runtime_metrics.inflight_by_source),
                "completed_by_source": dict(runtime_metrics.completed_by_source),
                "blocked_by_source": blocked_sources,
                "quota_wait_seconds_by_source": dict(runtime_metrics.quota_wait_seconds_by_source),
                "capability_failures_by_source": _capability_failures_by_source(
                    capability_failure_state
                ),
                "empty_ratio_by_source": {
                    source: round(
                        float(runtime_metrics.empty_by_source.get(source, 0))
                        / max(float(runtime_metrics.completed_by_source.get(source, 0)), 1.0),
                        4,
                    )
                    for source in sorted(runtime_metrics.completed_by_source)
                },
                "deferred_by_reason": dict(runtime_metrics.deferred_by_reason),
                "avg_rows_per_shard": round(
                    float(sum(runtime_metrics.rows_by_source.values()))
                    / max(float(sum(runtime_metrics.completed_by_source.values())), 1.0),
                    2,
                ),
                "queue_backlog_by_source": dict(runtime_metrics.queue_backlog_by_source),
                "writer_backlog_rows": int(runtime_metrics.writer_backlog_rows),
                "writer_flush_count": int(runtime_metrics.writer_flush_count),
                "writer_flush_latency_ms": round(float(runtime_metrics.writer_flush_latency_ms), 2),
                "planner_pruned_shards": int(runtime_metrics.planner_pruned_shards),
                "planned_work_packages": int(runtime_metrics.planned_work_packages),
                "support_sketch_count": int(runtime_metrics.support_sketch_count),
                "publishable_core_complete": bool(publishable_core_complete),
                "publishable_core_pending": int(core_pending["count"]),
                "backfill_pending": int(max(pending["count"] - core_pending["count"], 0)),
                "source_core_completion_pct": source_core_completion_pct,
                "source_full_completion_pct": source_full_completion_pct,
                "async_jobs_open": len(async_leases),
                "bytes_downloaded_by_source": dict(runtime_metrics.bytes_downloaded_by_source),
                "request_count_by_source": dict(runtime_metrics.request_count_by_source),
                "rows_per_request": rows_per_request,
                "empty_fetch_ratio": round(
                    float(total_empty) / max(float(total_completed), 1.0), 4
                ),
                "deferred_ratio": round(
                    float(total_deferred) / max(float(runtime_metrics.planned_work_packages), 1.0),
                    4,
                ),
                "time_to_publishable_core": time_to_publishable_core,
                "time_to_full_backfill": round(elapsed_total, 3) if pending["count"] <= 0 else None,
                "subphases": {
                    "support_sketch": {
                        "status": "complete" if support_sketches else "running",
                        "count": len(support_sketches),
                    },
                    "publishable_core": {
                        "status": "complete"
                        if publishable_core_complete
                        else ("running" if "publishable_core" in selected_phases else "skipped"),
                        "remaining": int(core_pending["count"]),
                    },
                    "long_tail_backfill": {
                        "status": (
                            "complete"
                            if pending["count"] <= 0 and "long_tail_backfill" in selected_phases
                            else (
                                "running" if "long_tail_backfill" in selected_phases else "skipped"
                            )
                        ),
                        "remaining": int(max(pending["count"] - core_pending["count"], 0)),
                    },
                },
            }
        _write_core_ingest_stage_progress(config, metadata=metadata)
        _write_observation_checkpoint_state(
            config,
            completed=completed,
            failed=failed,
            deferred=deferred,
            unsupported_signatures=unsupported_cache_state,
            empty_signatures=empty_cache_state,
            inflight_leases=leases,
            async_fetch_leases=async_leases,
            capability_snapshots=capability_state,
            capability_failures=capability_failure_state,
            source_budgets=budget_state,
            writer_state=_serialize_writer_state(writer_state),
            support_sketches=sketch_state,
            work_packages=work_package_state,
            planner_phase=phase_state["value"],
            publishable_core_complete=publishable_core_complete,
            negative_cache_version=2,
            planner_signature=planner_signature or config.run_signature,
        )

    async def _finalize_result(
        result: ObservationShardResult,
        *,
        support_key: str,
        source: str,
        mark_unsupported: bool = False,
        empty_result: bool = False,
        promote_empty_to_unsupported: bool = True,
    ) -> None:
        nonlocal publishable_core_complete
        async with runtime_lock:
            if support_key:
                if result.status == "complete_with_rows":
                    unsupported_signatures.pop(support_key, None)
                    empty_signatures.pop(support_key, None)
                elif mark_unsupported or empty_result:
                    _update_support_cache(
                        unsupported_signatures,
                        empty_signatures,
                        key=support_key,
                        policy=source_policies[source],
                        unsupported=mark_unsupported,
                        empty_result=empty_result,
                        promote_empty_to_unsupported=promote_empty_to_unsupported,
                    )
            _store_shard_result(
                result=result,
                completed=completed,
                failed=failed,
                deferred=deferred,
            )
            _append_shard_result(
                result=result,
                completed_results=completed_results,
                failed_results=failed_results,
                deferred_results=deferred_results,
                source_summary=source_summary,
            )
            if result.status.startswith("complete"):
                stats.completed_shards += 1
                runtime_metrics.completed_by_source[source] = (
                    runtime_metrics.completed_by_source.get(source, 0) + 1
                )
                runtime_metrics.rows_by_source[source] = runtime_metrics.rows_by_source.get(
                    source, 0
                ) + int(result.row_count)
                if result.status == "complete_empty":
                    stats.empty_shards += 1
                    runtime_metrics.empty_by_source[source] = (
                        runtime_metrics.empty_by_source.get(source, 0) + 1
                    )
            else:
                stats.failures += 1
                if result.status == "failed":
                    stats.failed_shards += 1
                else:
                    stats.deferred_shards += 1
                reason_key = (result.error or result.status).split("\n", 1)[0][:120]
                runtime_metrics.deferred_by_reason[reason_key] = (
                    runtime_metrics.deferred_by_reason.get(reason_key, 0) + 1
                )
            pending["count"] -= 1
            phase = str(
                work_packages.get(result.shard_id).phase if result.shard_id in work_packages else ""
            )
            if phase == "publishable_core":
                core_pending["count"] = max(core_pending["count"] - 1, 0)
                if core_pending["count"] <= 0 and not publishable_core_complete:
                    phase_timings["publishable_core_completed_at"] = time.monotonic()
                    if "long_tail_backfill" in selected_phases and pending["count"] > 0:
                        phase_state["value"] = "long_tail_backfill"
                        phase_timings["long_tail_backfill_started_at"] = (
                            phase_timings["long_tail_backfill_started_at"] or time.monotonic()
                        )
                    publishable_core_complete = True
            elif phase == "long_tail_backfill" and pending["count"] <= 0:
                phase_timings["long_tail_backfill_completed_at"] = time.monotonic()
            if pending["count"] <= 0:
                done_event.set()
        await _persist_runtime_state()

    async def _progress_loop() -> None:
        while not done_event.is_set():
            await asyncio.sleep(_OBSERVATION_PROGRESS_INTERVAL_SECONDS)
            if done_event.is_set():
                break
            await _persist_runtime_state()

    async def _flush_writer_buffer(
        con: duckdb.DuckDBPyConnection,
        buffer: list[ObservationWriteItem],
    ) -> None:
        if not buffer:
            return
        flush_started = time.monotonic()
        total_rows = sum(item.row_count for item in buffer)
        ack_pairs: list[tuple[ObservationWriteItem, ObservationInsertStats]] = []
        try:
            for item_batch in _iter_observation_write_item_batches(buffer):
                current_pairs: list[tuple[ObservationWriteItem, ObservationInsertStats]] = []
                try:
                    con.execute("BEGIN TRANSACTION")
                    for item in item_batch:
                        insert_stats = _insert_generic_observations(
                            con=con,
                            plan=item.shard.plan,
                            rows=item.payload.rows,
                            acquisition_method=item.payload.acquisition_method
                            or item.shard.acquisition_method,
                            source_watermark=item.payload.source_watermark
                            or item.shard.source_watermark,
                            dataset_version=item.payload.dataset_version
                            or item.shard.dataset_version,
                        )
                        current_pairs.append((item, insert_stats))
                    con.execute("COMMIT")
                except Exception:
                    try:
                        con.execute("ROLLBACK")
                    except Exception:
                        logger.debug(
                            "DuckDB rollback failed during observation writer flush", exc_info=True
                        )
                    raise
                ack_pairs.extend(current_pairs)
        except Exception as exc:
            for item in buffer:
                if not item.ack.done():
                    item.ack.set_exception(exc)
            raise

        writer_state.buffered_rows = max(writer_state.buffered_rows - total_rows, 0)
        writer_state.buffered_bytes = max(
            writer_state.buffered_bytes - sum(item.estimated_bytes for item in buffer),
            0,
        )
        writer_state.flush_count += 1
        writer_state.last_flush_at = time.monotonic()
        writer_state.last_flush_latency_ms = (writer_state.last_flush_at - flush_started) * 1000.0
        if writer_state.flush_count % _OBSERVATION_WRITER_CHECKPOINT_EVERY == 0:
            con.execute("CHECKPOINT")

        async with runtime_lock:
            runtime_metrics.writer_backlog_rows = max(
                runtime_metrics.writer_backlog_rows - total_rows, 0
            )
            runtime_metrics.writer_flush_count = writer_state.flush_count
            runtime_metrics.writer_flush_latency_ms = writer_state.last_flush_latency_ms
            for item, insert_stats in ack_pairs:
                _merge_observation_stats(stats, insert_stats, source=item.shard.plan.source)

        for item, insert_stats in ack_pairs:
            if not item.ack.done():
                item.ack.set_result(insert_stats)

    async def _writer() -> None:
        buffer: list[ObservationWriteItem] = []
        with duckdb.connect(str(db_path)) as con:
            _configure_observation_writer_connection(con, db_path=db_path)
            while True:
                timeout = 0.5
                if buffer:
                    elapsed = max(time.monotonic() - writer_state.last_flush_at, 0.0)
                    timeout = min(
                        max(_OBSERVATION_WRITER_FLUSH_SECONDS - elapsed, 0.1),
                        _OBSERVATION_WRITER_IDLE_FLUSH_SECONDS,
                    )
                try:
                    item = await asyncio.wait_for(writer_queue.get(), timeout=timeout)
                except TimeoutError:
                    item = None

                if item is None:
                    if buffer:
                        await _flush_writer_buffer(con, buffer)
                        buffer.clear()
                    if done_event.is_set() and writer_queue.empty():
                        break
                    continue

                buffer.append(item)
                writer_state.buffered_rows += item.row_count
                writer_state.buffered_bytes += item.estimated_bytes
                async with runtime_lock:
                    runtime_metrics.writer_backlog_rows += item.row_count

                should_flush = (
                    writer_state.buffered_rows >= _OBSERVATION_WRITER_FLUSH_ROWS
                    or writer_state.buffered_bytes >= _OBSERVATION_WRITER_FLUSH_BYTES
                    or (time.monotonic() - writer_state.last_flush_at)
                    >= _OBSERVATION_WRITER_FLUSH_SECONDS
                )
                if should_flush:
                    await _flush_writer_buffer(con, buffer)
                    buffer.clear()

            if buffer:
                await _flush_writer_buffer(con, buffer)
            con.execute("CHECKPOINT")

    unique_plans: dict[str, ObservationPlan] = {}
    for plan in plans:
        unique_plans.setdefault(_capability_snapshot_cache_key(plan), plan)

    persisted_capabilities = await capability_cache.snapshot()
    for key, snapshot in persisted_capabilities.items():
        plan = unique_plans.get(key)
        if plan is None:
            continue
        policy = source_policies.get(plan.source)
        if policy is None or not _capability_snapshot_fresh(snapshot, policy=policy):
            continue
        plan_capabilities[key] = snapshot

    if planner_signature and planner_signature != config.run_signature:
        persisted_support_sketches = {}
        persisted_work_packages = {}
        persisted_planner_phase = "support_sketch"
        publishable_core_complete = False
    planner_signature = config.run_signature

    if persisted_support_sketches:
        support_sketches = dict(persisted_support_sketches)
    else:
        support_sketches = _build_support_sketches(
            plans,
            config=config,
            plan_capabilities=plan_capabilities,
            source_policies=source_policies,
        )
    if persisted_work_packages:
        work_packages = dict(persisted_work_packages)
    else:
        work_packages = {
            shard.shard_id: shard
            for shard in _build_observation_shards_from_sketches(
                support_sketches,
                config=config,
                source_policies=source_policies,
            )
        }
        persisted_planner_phase = "publishable_core" if work_packages else "deferred"
        publishable_core_complete = False

    runtime_metrics.support_sketch_count = len(support_sketches)
    runtime_metrics.planned_work_packages = len(work_packages)
    phase_state["value"] = "support_sketch"
    await _persist_runtime_state()

    ordered_work_packages = sorted(
        work_packages.values(),
        key=lambda shard: (
            0 if shard.phase == "publishable_core" else 1,
            shard.plan.source,
            shard.start_year,
            shard.end_year,
            shard.shard_id,
        ),
    )
    for shard in ordered_work_packages:
        if shard.phase not in selected_phases:
            continue
        if _shard_completed(config, shard, completed=completed, failed=failed, deferred=deferred):
            continue
        source = shard.plan.source
        policy = source_policies[source]
        capability = plan_capabilities.get(_capability_snapshot_cache_key(shard.plan))
        if capability is not None and not _capability_snapshot_fresh(capability, policy=policy):
            capability = None
        if not _shard_supported_by_capability(shard, snapshot=capability):
            support_key = _support_cache_key(shard, capability=capability)
            _update_unsupported_signature_cache(
                unsupported_signatures,
                key=support_key,
                policy=policy,
            )
            _record_initial_result(
                ObservationShardResult(
                    shard_id=shard.shard_id,
                    status="complete_empty",
                    source=source,
                    dataset_id=shard.plan.dataset_id,
                    raw_variable=shard.plan.raw_variable,
                    canonical_var=shard.plan.canonical_var,
                    country_code=shard.country_code,
                    start_year=shard.start_year,
                    end_year=shard.end_year,
                    error="capability_snapshot:unsupported",
                ),
                source=source,
            )
            runtime_metrics.planner_pruned_shards += 1
            continue

        planned_shards = _planner_split_shard_from_capability(
            shard,
            snapshot=capability,
            policy=policy,
        )
        if len(planned_shards) != 1 or planned_shards[0].shard_id != shard.shard_id:
            work_packages.pop(shard.shard_id, None)
        for planned in planned_shards:
            work_packages[planned.shard_id] = planned
            source_queues.setdefault(source, asyncio.Queue()).put_nowait(planned)
            pending["count"] += 1
            selected_work_package_ids.add(planned.shard_id)
            if planned.phase == "publishable_core":
                core_pending["count"] += 1
    publishable_core_complete = core_pending["count"] <= 0
    if "publishable_core" in selected_phases and not publishable_core_complete:
        phase_state["value"] = "publishable_core"
        phase_timings["publishable_core_started_at"] = (
            phase_timings["publishable_core_started_at"] or time.monotonic()
        )
    elif "long_tail_backfill" in selected_phases:
        phase_state["value"] = "long_tail_backfill"
        phase_timings["long_tail_backfill_started_at"] = (
            phase_timings["long_tail_backfill_started_at"] or time.monotonic()
        )
    else:
        phase_state["value"] = "deferred"

    for source, queue in source_queues.items():
        runtime_metrics.queue_backlog_by_source[source] = queue.qsize()

    async def _advisory_prewarm(plan: ObservationPlan) -> None:
        key = _capability_snapshot_cache_key(plan)
        if key in plan_capabilities:
            return
        phase_state["value"] = "support_sketch"
        try:
            snapshot = await _describe_observation_plan(
                plan,
                cache,
                policy=source_policies[plan.source],
                capability_cache=capability_cache,
                capability_failures=capability_failures,
                budget_windows=budget_windows,
                state_lock=runtime_lock,
                budget_wait_observer=_record_budget_block,
            )
        except Exception as exc:
            _log_rate_limited_warning(
                f"capability-prewarm:{plan.source}:{plan.request_dataset_id}",
                "Capability preflight failed for {}/{}: {}",
                plan.source,
                plan.request_dataset_id,
                exc,
            )
            return
        if snapshot is not None:
            plan_capabilities[key] = snapshot
            support_sketches[_support_sketch_id(plan)] = _build_support_sketches(
                [plan],
                config=config,
                plan_capabilities={key: snapshot},
                source_policies=source_policies,
            )[_support_sketch_id(plan)]

    advisory_prewarm_tasks = [
        asyncio.create_task(_advisory_prewarm(plan))
        for key, plan in unique_plans.items()
        if key not in plan_capabilities
    ]
    if pending["count"] > 0 and not publishable_core_complete:
        phase_state["value"] = "publishable_core"
    elif pending["count"] > 0:
        phase_state["value"] = "long_tail_backfill"
    else:
        phase_state["value"] = "deferred"
    await _persist_runtime_state()

    if pending["count"] <= 0:
        _write_observation_checkpoint_state(
            config,
            completed=completed,
            failed=failed,
            deferred=deferred,
            unsupported_signatures=unsupported_signatures,
            empty_signatures=empty_signatures,
            inflight_leases=inflight_leases,
            async_fetch_leases=async_fetch_leases,
            capability_snapshots=_serialize_capability_snapshot_state(
                await capability_cache.snapshot()
            ),
            capability_failures=capability_failures,
            source_budgets=_serialize_source_budget_windows(budget_windows),
            writer_state=_serialize_writer_state(writer_state),
            support_sketches=_serialize_support_sketch_state(support_sketches),
            work_packages=_serialize_work_package_state(work_packages),
            planner_phase=phase_state["value"],
            publishable_core_complete=publishable_core_complete,
            negative_cache_version=2,
            planner_signature=planner_signature,
        )
        for task in advisory_prewarm_tasks:
            task.cancel()
        await cache.close()
        _write_observation_ingest_manifests(
            config=config,
            completed_results=completed_results,
            failed_results=failed_results,
            deferred_results=deferred_results,
            source_summary=source_summary,
        )
        return stats

    writer_task = asyncio.create_task(_writer())

    async def _worker(source: str) -> None:
        queue = source_queues[source]
        policy = source_policies[source]
        while True:
            if done_event.is_set() and queue.empty():
                return
            try:
                shard = await asyncio.wait_for(queue.get(), timeout=0.5)
            except TimeoutError:
                continue

            capability_key = _capability_snapshot_cache_key(shard.plan)
            capability = plan_capabilities.get(capability_key)
            if capability is not None and not _capability_snapshot_fresh(capability, policy=policy):
                capability = None
                plan_capabilities.pop(capability_key, None)
            if capability is None:
                try:
                    capability = await _describe_observation_plan(
                        shard.plan,
                        cache,
                        policy=policy,
                        capability_cache=capability_cache,
                        capability_failures=capability_failures,
                        budget_windows=budget_windows,
                        state_lock=runtime_lock,
                        budget_wait_observer=_record_budget_block,
                    )
                except Exception as exc:
                    _log_rate_limited_warning(
                        f"capability-refresh:{shard.plan.source}:{shard.plan.request_dataset_id}",
                        "Capability refresh failed for {}/{}: {}",
                        shard.plan.source,
                        shard.plan.request_dataset_id,
                        exc,
                    )
                    capability = None
                if capability is not None:
                    plan_capabilities[capability_key] = capability

            if capability is not None and not _shard_supported_by_capability(
                shard, snapshot=capability
            ):
                support_key = _support_cache_key(shard, capability=capability)
                await _finalize_result(
                    ObservationShardResult(
                        shard_id=shard.shard_id,
                        status="complete_empty",
                        source=source,
                        dataset_id=shard.plan.dataset_id,
                        raw_variable=shard.plan.raw_variable,
                        canonical_var=shard.plan.canonical_var,
                        country_code=shard.country_code,
                        start_year=shard.start_year,
                        end_year=shard.end_year,
                        error="capability_snapshot:unsupported",
                    ),
                    support_key=support_key,
                    source=source,
                    mark_unsupported=True,
                    empty_result=True,
                    promote_empty_to_unsupported=True,
                )
                async with runtime_lock:
                    runtime_metrics.planner_pruned_shards += 1
                continue

            if capability is not None:
                planned_shards = _planner_split_shard_from_capability(
                    shard,
                    snapshot=capability,
                    policy=policy,
                )
                if len(planned_shards) != 1 or planned_shards[0].shard_id != shard.shard_id:
                    async with runtime_lock:
                        work_packages.pop(shard.shard_id, None)
                        pending["count"] += len(planned_shards) - 1
                        if shard.phase == "publishable_core":
                            core_pending["count"] += len(planned_shards) - 1
                        for planned in planned_shards:
                            work_packages[planned.shard_id] = planned
                            queue.put_nowait(planned)
                            selected_work_package_ids.add(planned.shard_id)
                        runtime_metrics.queue_backlog_by_source[source] = queue.qsize()
                        runtime_metrics.planned_work_packages = len(work_packages)
                    continue

            support_key = _support_cache_key(shard, capability=capability)
            skip_result: ObservationShardResult | None = None
            async with runtime_lock:
                runtime_metrics.queue_backlog_by_source[source] = queue.qsize()
                now = datetime.now(UTC)
                cached_support = unsupported_signatures.get(support_key, {})
                cached_empty = empty_signatures.get(support_key, {})
                if isinstance(cached_support, dict) and _support_cache_proves_unsupported(
                    cached_support, now=now
                ):
                    skip_result = ObservationShardResult(
                        shard_id=shard.shard_id,
                        status="complete_empty",
                        source=source,
                        dataset_id=shard.plan.dataset_id,
                        raw_variable=shard.plan.raw_variable,
                        canonical_var=shard.plan.canonical_var,
                        country_code=shard.country_code,
                        start_year=shard.start_year,
                        end_year=shard.end_year,
                        error="support_cache:unsupported",
                    )
                elif isinstance(cached_empty, dict) and _empty_signature_cache_hit(
                    cached_empty, now=now
                ):
                    skip_result = ObservationShardResult(
                        shard_id=shard.shard_id,
                        status="complete_empty",
                        source=source,
                        dataset_id=shard.plan.dataset_id,
                        raw_variable=shard.plan.raw_variable,
                        canonical_var=shard.plan.canonical_var,
                        country_code=shard.country_code,
                        start_year=shard.start_year,
                        end_year=shard.end_year,
                        error="support_cache:empty_recent",
                    )
                else:
                    inflight_leases[shard.shard_id] = {
                        "source": source,
                        "started_at": datetime.now(UTC).isoformat(),
                    }
                    runtime_metrics.inflight_by_source[source] = (
                        runtime_metrics.inflight_by_source.get(source, 0) + 1
                    )
                    runtime_metrics.async_jobs_open = len(async_fetch_leases)

            if skip_result is not None:
                await _finalize_result(
                    skip_result,
                    support_key=support_key,
                    source=source,
                    empty_result=True,
                    promote_empty_to_unsupported=_empty_result_proves_unsupported(
                        shard=shard,
                        snapshot=capability,
                    ),
                )
                continue

            try:
                try:
                    logger.info(
                        "Fetching observation shard {}: source={}, request_dataset_id={}, country={}",
                        shard.shard_id,
                        shard.plan.source,
                        shard.plan.request_dataset_id,
                        shard.country_code,
                    )
                    rows = await _fetch_observation_rows_with_retries(
                        shard,
                        cache,
                        config=config,
                        policy=policy,
                        fetch_deduper=fetch_deduper,
                        budget_windows=budget_windows,
                        state_lock=runtime_lock,
                        capability_snapshot=capability,
                        async_fetch_leases=async_fetch_leases,
                        record_result=_record_fetch_metrics,
                        budget_wait_observer=_record_budget_block,
                    )
                    row_limit = (
                        _observation_payload_row_limit(shard.plan)
                        if config.is_sampled_run
                        else None
                    )
                    if row_limit is not None and len(rows) > row_limit:
                        split_shards = []
                        if not (
                            config.is_sampled_run
                            or config.preflight_only
                            or config.run_profile == "preflight_core"
                        ):
                            split_shards = await _split_shard_for_retry_async(
                                shard,
                                RuntimeError(f"HTTP 413 simulated for payload rows={len(rows)}"),
                                cache=cache,
                                config=config,
                                policy=policy,
                                budget_windows=budget_windows,
                                state_lock=runtime_lock,
                                budget_wait_observer=_record_budget_block,
                            )
                        if split_shards:
                            async with runtime_lock:
                                work_packages.pop(shard.shard_id, None)
                                pending["count"] += len(split_shards) - 1
                                if shard.phase == "publishable_core":
                                    core_pending["count"] += len(split_shards) - 1
                                for split in split_shards:
                                    work_packages[split.shard_id] = split
                                    queue.put_nowait(split)
                                    selected_work_package_ids.add(split.shard_id)
                                runtime_metrics.queue_backlog_by_source[source] = queue.qsize()
                                runtime_metrics.planned_work_packages = len(work_packages)
                            continue
                        await _finalize_result(
                            ObservationShardResult(
                                shard_id=shard.shard_id,
                                status="deferred",
                                source=source,
                                dataset_id=shard.plan.dataset_id,
                                raw_variable=shard.plan.raw_variable,
                                canonical_var=shard.plan.canonical_var,
                                country_code=shard.country_code,
                                start_year=shard.start_year,
                                end_year=shard.end_year,
                                row_count=len(rows),
                                error=f"oversized_payload:{len(rows)}>{row_limit}",
                            ),
                            support_key=support_key,
                            source=source,
                        )
                        continue
                except Exception as exc:
                    split_shards = await _split_shard_for_retry_async(
                        shard,
                        exc,
                        cache=cache,
                        config=config,
                        policy=policy,
                        budget_windows=budget_windows,
                        state_lock=runtime_lock,
                        budget_wait_observer=_record_budget_block,
                    )
                    if split_shards:
                        logger.warning(
                            "Splitting observation shard for {}/{} after error: {}",
                            shard.plan.source,
                            shard.plan.request_dataset_id,
                            exc,
                        )
                        async with runtime_lock:
                            work_packages.pop(shard.shard_id, None)
                            pending["count"] += len(split_shards) - 1
                            if shard.phase == "publishable_core":
                                core_pending["count"] += len(split_shards) - 1
                            for split in split_shards:
                                work_packages[split.shard_id] = split
                                queue.put_nowait(split)
                                selected_work_package_ids.add(split.shard_id)
                            runtime_metrics.queue_backlog_by_source[source] = queue.qsize()
                            runtime_metrics.planned_work_packages = len(work_packages)
                        continue
                    explicit_unsupported = _is_explicit_unsupported_error(exc)
                    status = "deferred" if config.defer_unsupported_observation_plans else "failed"
                    if _is_auth_or_env_error(exc):
                        status = "failed"
                    elif explicit_unsupported:
                        status = "complete_empty"
                    await _finalize_result(
                        ObservationShardResult(
                            shard_id=shard.shard_id,
                            status=status,
                            source=source,
                            dataset_id=shard.plan.dataset_id,
                            raw_variable=shard.plan.raw_variable,
                            canonical_var=shard.plan.canonical_var,
                            country_code=shard.country_code,
                            start_year=shard.start_year,
                            end_year=shard.end_year,
                            error=str(exc),
                        ),
                        support_key=support_key,
                        source=source,
                        mark_unsupported=explicit_unsupported,
                        empty_result=(status == "complete_empty"),
                        promote_empty_to_unsupported=explicit_unsupported,
                    )
                    continue

                ack = asyncio.get_running_loop().create_future()
                await writer_queue.put(
                    ObservationWriteItem(
                        shard=shard,
                        payload=ObservationFetchPayload(
                            rows=rows,
                            acquisition_method=shard.acquisition_method,
                            source_watermark=shard.source_watermark,
                            dataset_version=shard.dataset_version,
                        ),
                        ack=ack,
                    )
                )
                insert_stats = await ack

                shard_status = (
                    "complete_with_rows" if insert_stats.written > 0 else "complete_empty"
                )
                if shard_status == "complete_empty":
                    _log_rate_limited_warning(
                        f"observation-empty:{shard.plan.source}:{shard.plan.request_dataset_id}",
                        "Observation shard {} returned 0 rows: source={}, request_dataset_id={}, country={}",
                        shard.shard_id,
                        shard.plan.source,
                        shard.plan.request_dataset_id,
                        shard.country_code,
                    )
                await _finalize_result(
                    ObservationShardResult(
                        shard_id=shard.shard_id,
                        status=shard_status,
                        source=source,
                        dataset_id=shard.plan.dataset_id,
                        raw_variable=shard.plan.raw_variable,
                        canonical_var=shard.plan.canonical_var,
                        country_code=shard.country_code,
                        start_year=shard.start_year,
                        end_year=shard.end_year,
                        row_count=insert_stats.written,
                    ),
                    support_key=support_key,
                    source=source,
                    empty_result=(shard_status == "complete_empty"),
                    promote_empty_to_unsupported=_empty_result_proves_unsupported(
                        shard=shard,
                        snapshot=capability,
                    ),
                )
            finally:
                async with runtime_lock:
                    inflight_leases.pop(shard.shard_id, None)
                    async_fetch_leases.pop(shard.shard_id, None)
                    runtime_metrics.inflight_by_source[source] = max(
                        runtime_metrics.inflight_by_source.get(source, 1) - 1, 0
                    )
                    runtime_metrics.queue_backlog_by_source[source] = queue.qsize()
                    runtime_metrics.async_jobs_open = len(async_fetch_leases)

    progress_task = asyncio.create_task(_progress_loop())
    worker_tasks = [
        asyncio.create_task(_worker(source))
        for source, queue in source_queues.items()
        for _ in range(_source_runtime_lane_count(source=source, policy=source_policies[source]))
        if not queue.empty()
    ]
    try:
        await asyncio.gather(*worker_tasks)
    finally:
        done_event.set()
        for task in advisory_prewarm_tasks:
            task.cancel()
        await writer_queue.put(None)
        progress_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await progress_task
        if advisory_prewarm_tasks:
            await asyncio.gather(*advisory_prewarm_tasks, return_exceptions=True)
        try:
            await writer_task
        finally:
            async with runtime_lock:
                inflight_leases.clear()
                runtime_metrics.async_jobs_open = len(async_fetch_leases)
            await _persist_runtime_state()
            await cache.close()

    _write_observation_ingest_manifests(
        config=config,
        completed_results=completed_results,
        failed_results=failed_results,
        deferred_results=deferred_results,
        source_summary=source_summary,
    )
    return stats


async def _ingest_catalog_observations_legacy(
    db_path: Path,
    plans: list[ObservationPlan],
    *,
    config: DatasetBatchConfig,
) -> CoreSourcesIngestStats:
    stats = CoreSourcesIngestStats()
    cache = _ConnectorSessionCache()
    checkpoint_payload = load_json(config.observation_ingest_checkpoint_path, default={})
    completed = (
        checkpoint_payload.get("completed", {}) if isinstance(checkpoint_payload, dict) else {}
    )
    failed = checkpoint_payload.get("failed", {}) if isinstance(checkpoint_payload, dict) else {}
    deferred = (
        checkpoint_payload.get("deferred", {}) if isinstance(checkpoint_payload, dict) else {}
    )
    if not isinstance(completed, dict):
        completed = {}
    if not isinstance(failed, dict):
        failed = {}
    if not isinstance(deferred, dict):
        deferred = {}
    completed_results: list[dict[str, Any]] = []
    failed_results: list[dict[str, Any]] = []
    deferred_results: list[dict[str, Any]] = []
    source_summary: dict[str, dict[str, int]] = {}
    shard_queue = deque(_build_observation_shards(plans, config=config))
    fetch_deduper = _ObservationFetchDeduper()
    budget_windows = _load_source_budget_windows({})
    state_lock = asyncio.Lock()
    try:
        with duckdb.connect(str(db_path)) as con:
            while shard_queue:
                shard = shard_queue.popleft()
                if _shard_completed(
                    config, shard, completed=completed, failed=failed, deferred=deferred
                ):
                    continue
                try:
                    policy = _resolve_source_execution_policy(
                        source=shard.plan.source, profile_id=shard.plan.profile_id
                    )
                    logger.info(
                        "Fetching observation shard {}: source={}, request_dataset_id={}, country={}",
                        shard.shard_id,
                        shard.plan.source,
                        shard.plan.request_dataset_id,
                        shard.country_code,
                    )
                    rows = await _fetch_observation_rows_with_retries(
                        shard,
                        cache,
                        config=config,
                        policy=policy,
                        fetch_deduper=fetch_deduper,
                        budget_windows=budget_windows,
                        state_lock=state_lock,
                    )
                except Exception as exc:
                    split_shards = _split_shard_for_retry(shard, exc)
                    if split_shards:
                        logger.warning(
                            "Splitting observation shard for {}/{} after error: {}",
                            shard.plan.source,
                            shard.plan.request_dataset_id,
                            exc,
                        )
                        for split in reversed(split_shards):
                            shard_queue.appendleft(split)
                        continue
                    explicit_unsupported = _is_explicit_unsupported_error(exc)
                    status = "deferred" if config.defer_unsupported_observation_plans else "failed"
                    if _is_auth_or_env_error(exc):
                        status = "failed"
                    elif explicit_unsupported:
                        status = "complete_empty"
                    result = ObservationShardResult(
                        shard_id=shard.shard_id,
                        status=status,
                        source=shard.plan.source,
                        dataset_id=shard.plan.dataset_id,
                        raw_variable=shard.plan.raw_variable,
                        canonical_var=shard.plan.canonical_var,
                        country_code=shard.country_code,
                        start_year=shard.start_year,
                        end_year=shard.end_year,
                        error=str(exc),
                    )
                    _record_shard_result(
                        config,
                        result=result,
                        completed=completed,
                        failed=failed,
                        deferred=deferred,
                    )
                    _append_shard_result(
                        result=result,
                        completed_results=completed_results,
                        failed_results=failed_results,
                        deferred_results=deferred_results,
                        source_summary=source_summary,
                    )
                    if status.startswith("complete"):
                        stats.completed_shards += 1
                        stats.empty_shards += int(status == "complete_empty")
                    else:
                        stats.failures += 1
                        stats.failed_shards += int(status == "failed")
                        stats.deferred_shards += int(status == "deferred")
                    logger.warning("Observation shard {} failed: {}", shard.shard_id, exc)
                    continue
                row_limit = (
                    _observation_payload_row_limit(shard.plan) if config.is_sampled_run else None
                )
                if row_limit is not None and len(rows) > row_limit:
                    split_shards: list[ObservationShard] = []
                    if not (
                        config.is_sampled_run
                        or config.preflight_only
                        or config.run_profile == "preflight_core"
                    ):
                        split_shards = _split_shard_for_retry(
                            shard,
                            RuntimeError(f"HTTP 413 simulated for payload rows={len(rows)}"),
                        )
                    if split_shards:
                        for split in reversed(split_shards):
                            shard_queue.appendleft(split)
                        continue
                    result = ObservationShardResult(
                        shard_id=shard.shard_id,
                        status="deferred",
                        source=shard.plan.source,
                        dataset_id=shard.plan.dataset_id,
                        raw_variable=shard.plan.raw_variable,
                        canonical_var=shard.plan.canonical_var,
                        country_code=shard.country_code,
                        start_year=shard.start_year,
                        end_year=shard.end_year,
                        row_count=len(rows),
                        error=f"oversized_payload:{len(rows)}>{row_limit}",
                    )
                    _record_shard_result(
                        config, result=result, completed=completed, failed=failed, deferred=deferred
                    )
                    _append_shard_result(
                        result=result,
                        completed_results=completed_results,
                        failed_results=failed_results,
                        deferred_results=deferred_results,
                        source_summary=source_summary,
                    )
                    stats.deferred_shards += 1
                    stats.failures += 1
                    continue
                insert_stats = _insert_generic_observations(con=con, plan=shard.plan, rows=rows)
                _merge_observation_stats(stats, insert_stats, source=shard.plan.source)
                shard_status = (
                    "complete_with_rows" if insert_stats.written > 0 else "complete_empty"
                )
                if shard_status == "complete_empty":
                    stats.empty_shards += 1
                    logger.warning(
                        "Observation shard {} returned 0 rows: source={}, request_dataset_id={}, country={}",
                        shard.shard_id,
                        shard.plan.source,
                        shard.plan.request_dataset_id,
                        shard.country_code,
                    )
                result = ObservationShardResult(
                    shard_id=shard.shard_id,
                    status=shard_status,
                    source=shard.plan.source,
                    dataset_id=shard.plan.dataset_id,
                    raw_variable=shard.plan.raw_variable,
                    canonical_var=shard.plan.canonical_var,
                    country_code=shard.country_code,
                    start_year=shard.start_year,
                    end_year=shard.end_year,
                    row_count=insert_stats.written,
                )
                _record_shard_result(
                    config, result=result, completed=completed, failed=failed, deferred=deferred
                )
                _append_shard_result(
                    result=result,
                    completed_results=completed_results,
                    failed_results=failed_results,
                    deferred_results=deferred_results,
                    source_summary=source_summary,
                )
                stats.completed_shards += 1
            con.execute("CHECKPOINT")
    finally:
        await cache.close()
    _write_observation_ingest_manifests(
        config=config,
        completed_results=completed_results,
        failed_results=failed_results,
        deferred_results=deferred_results,
        source_summary=source_summary,
    )
    return stats


async def _fetch_observation_rows_with_retries(
    shard: ObservationShard,
    cache: _ConnectorSessionCache,
    *,
    config: DatasetBatchConfig,
    policy: SourceExecutionPolicy,
    fetch_deduper: _ObservationFetchDeduper,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    capability_snapshot: DatasetCapabilitySnapshot | None = None,
    async_fetch_leases: dict[str, Any] | None = None,
    record_result: Any | None = None,
    budget_wait_observer: Any | None = None,
) -> list[dict[str, Any]]:
    attempts = 0
    fetch_key = ObservationFetchKey(
        source=shard.plan.source,
        request_dataset_id=shard.plan.request_dataset_id,
        filters_json=json.dumps(
            shard.filters, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
        countries_json=json.dumps(
            _shard_countries(shard, config=config), ensure_ascii=False, separators=(",", ":")
        ),
        start_year=shard.start_year,
        end_year=shard.end_year,
    )
    while True:
        try:
            return await fetch_deduper.run(
                fetch_key,
                producer=lambda: _invoke_fetch_observation_rows(
                    shard,
                    cache,
                    config=config,
                    policy=policy,
                    budget_windows=budget_windows,
                    state_lock=state_lock,
                    capability_snapshot=capability_snapshot,
                    async_fetch_leases=async_fetch_leases,
                    record_result=record_result,
                    budget_wait_observer=budget_wait_observer,
                ),
            )
        except Exception as exc:
            if _is_planner_signal(exc):
                raise
            delay = _observation_retry_delay_seconds(exc, attempt=attempts)
            if delay is None:
                raise
            attempts += 1
            logger.warning(
                "Retrying observation ingest for {}/{} after transient error (sleep={}s): {}",
                shard.plan.source,
                shard.plan.request_dataset_id,
                delay,
                exc,
            )
            await asyncio.sleep(delay)


async def _invoke_fetch_observation_rows(
    shard: ObservationShard,
    cache: _ConnectorSessionCache,
    *,
    config: DatasetBatchConfig,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    capability_snapshot: DatasetCapabilitySnapshot | None = None,
    async_fetch_leases: dict[str, Any] | None = None,
    record_result: Any | None = None,
    budget_wait_observer: Any | None = None,
) -> list[dict[str, Any]]:
    try:
        return await _fetch_observation_rows(
            shard,
            cache,
            config=config,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            capability_snapshot=capability_snapshot,
            async_fetch_leases=async_fetch_leases,
            record_result=record_result,
            budget_wait_observer=budget_wait_observer,
        )
    except TypeError as exc:
        message = str(exc or "")
        unexpected_policy_args = (
            "unexpected keyword argument 'policy'" in message
            or "unexpected keyword argument 'budget_windows'" in message
            or "unexpected keyword argument 'state_lock'" in message
            or "unexpected keyword argument 'capability_snapshot'" in message
            or "unexpected keyword argument 'async_fetch_leases'" in message
            or "unexpected keyword argument 'record_result'" in message
        )
        if not unexpected_policy_args:
            raise
        return await _fetch_observation_rows(shard, cache, config=config)  # type: ignore[call-arg]


def _counts_toward_observation_failure_budget(exc: Exception) -> bool:
    text = str(exc or "").strip().lower()
    if "rate limit exceeded" in text:
        return False
    return not ("circuit" in text and "retry in" in text)


def _observation_retry_delay_seconds(exc: Exception, *, attempt: int) -> float | None:
    if attempt >= 1:
        return None
    text = str(exc or "").strip()
    lowered = text.lower()
    if "rate limit exceeded" in lowered:
        return 20.0
    if "circuit" in lowered and "retry in" in lowered:
        match = re.search(r"retry in ([0-9]+(?:\.[0-9]+)?)s?", text, re.IGNORECASE)
        if match:
            return min(max(float(match.group(1)), 1.0), 60.0)
        return 30.0
    return None


def _planner_error_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if status_code is not None:
        try:
            return int(status_code)
        except (TypeError, ValueError):
            return None
    match = re.search(r"http\s+([0-9]{3})", str(exc or ""), re.IGNORECASE)
    return int(match.group(1)) if match else None


def _is_planner_signal(exc: Exception) -> bool:
    return _planner_error_status_code(exc) in {400, 413}


def _is_explicit_unsupported_error(exc: Exception) -> bool:
    return _planner_error_status_code(exc) in {400, 404}


async def _acquire_source_budget_slot(
    *,
    source: str,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    budget_wait_observer: Any | None = None,
) -> None:
    if policy.requests_per_hour is None:
        return
    limit = max(1, int(policy.requests_per_hour))
    while True:
        async with state_lock:
            now = datetime.now(UTC)
            bucket = budget_windows.get(source)
            if bucket is None:
                bucket = _SourceBudgetWindow(window_started_at=now)
                budget_windows[source] = bucket
            if now - bucket.window_started_at >= timedelta(hours=1):
                bucket.window_started_at = now
                bucket.requests_used = 0
            if bucket.requests_used < limit:
                bucket.requests_used += 1
                return
            sleep_seconds = max(
                (bucket.window_started_at + timedelta(hours=1) - now).total_seconds(),
                1.0,
            )
        if budget_wait_observer is not None:
            await budget_wait_observer(source=source, sleep_seconds=sleep_seconds)
        await asyncio.sleep(min(sleep_seconds, 60.0))


async def _execute_source_fetch(
    connector: Any,
    handle: Any,
    request: FetchRequest,
    *,
    source: str,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    record_result: Any | None = None,
    budget_wait_observer: Any | None = None,
) -> Any:
    await _acquire_source_budget_slot(
        source=source,
        policy=policy,
        budget_windows=budget_windows,
        state_lock=state_lock,
        budget_wait_observer=budget_wait_observer,
    )
    result = await connector.fetch(handle, request)
    if record_result is not None:
        await record_result(
            source=source,
            bytes_transferred=int(getattr(result, "bytes_transferred", 0) or 0),
            request_count=1,
        )
    return result


async def _execute_source_describe(
    connector: Any,
    handle: Any,
    *,
    dataset_id: str,
    source: str,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    budget_wait_observer: Any | None = None,
) -> DatasetCapabilitySnapshot | None:
    await _acquire_source_budget_slot(
        source=source,
        policy=policy,
        budget_windows=budget_windows,
        state_lock=state_lock,
        budget_wait_observer=budget_wait_observer,
    )
    snapshot = await connector.describe_dataset(handle, dataset_id)
    if snapshot is None:
        return None
    if not snapshot.resolved_dataset_id:
        snapshot = snapshot.model_copy(update={"resolved_dataset_id": dataset_id})
    return snapshot


def _is_auth_or_env_error(exc: Exception) -> bool:
    text = str(exc or "").strip().lower()
    if not text:
        return False
    return any(
        token in text
        for token in (
            "token is required",
            "authorization",
            "auth credential",
            "auth_credentials",
            "bearer",
            "api key",
        )
    )


async def _describe_observation_plan(
    plan: ObservationPlan,
    cache: _ConnectorSessionCache,
    *,
    policy: SourceExecutionPolicy,
    capability_cache: _ObservationCapabilityCache,
    capability_failures: dict[str, Any],
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    budget_wait_observer: Any | None = None,
) -> DatasetCapabilitySnapshot | None:
    key = _capability_snapshot_cache_key(plan)
    async with state_lock:
        cached_failure = capability_failures.get(key, {})
        if (
            isinstance(cached_failure, dict)
            and _policy_str_attr(
                policy, "fallback_on_capability_failure", "plan_without_capability"
            )
            == "plan_without_capability"
            and _capability_failure_supports_fallback(cached_failure, now=datetime.now(UTC))
        ):
            return None

    async def _producer() -> DatasetCapabilitySnapshot | None:
        if plan.source == "worldbank":
            connector, handle = await cache.get_worldbank()
        elif plan.source == "eurostat":
            connector, handle = await cache.get_eurostat()
        elif plan.source in {"oecd", "ilo"}:
            profile_id = plan.profile_id or ("oecd_sdmx" if plan.source == "oecd" else "ilo_sdmx")
            connector, handle = await cache.get_sdmx(profile_id)
        elif plan.source == "who":
            connector, handle = await cache.get_who()
        elif plan.source == "unpd":
            connector, handle = await cache.get_unpd()
        elif plan.source == "unesco_uis":
            connector, handle = await cache.get_unesco_uis()
        else:
            return DatasetCapabilitySnapshot(
                source=plan.source,
                dataset_id=plan.request_dataset_id,
                resolved_dataset_id=plan.request_dataset_id,
                preferred_transport=_policy_str_attr(policy, "preferred_transport", "default"),
                last_checked_at=datetime.now(UTC),
            )
        try:
            snapshot = await _execute_source_describe(
                connector,
                handle,
                dataset_id=plan.request_dataset_id,
                source=plan.source,
                policy=policy,
                budget_windows=budget_windows,
                state_lock=state_lock,
                budget_wait_observer=budget_wait_observer,
            )
        except Exception as exc:
            status_code = _planner_error_status_code(exc)
            if status_code in _CAPABILITY_NEGATIVE_STATUS_CODES:
                async with state_lock:
                    capability_failures[key] = _serialize_capability_failure(
                        plan=plan,
                        policy=policy,
                        exc=exc,
                    )
                if (
                    _policy_str_attr(
                        policy, "fallback_on_capability_failure", "plan_without_capability"
                    )
                    == "plan_without_capability"
                ):
                    return None
            raise
        async with state_lock:
            capability_failures.pop(key, None)
        return snapshot

    snapshot = await capability_cache.get(key, producer=_producer)
    if snapshot is not None and not _capability_snapshot_fresh(snapshot, policy=policy):
        refreshed = await _producer()
        if refreshed is not None:
            await capability_cache.put(key, refreshed)
            return refreshed
        return None
    return snapshot


async def _fetch_observation_rows(
    shard: ObservationShard,
    cache: _ConnectorSessionCache,
    *,
    config: DatasetBatchConfig,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    capability_snapshot: DatasetCapabilitySnapshot | None = None,
    async_fetch_leases: dict[str, Any] | None = None,
    record_result: Any | None = None,
    budget_wait_observer: Any | None = None,
) -> list[dict[str, Any]]:
    plan = shard.plan
    start_year = shard.start_year
    end_year = shard.end_year
    if str(shard.acquisition_method or "").strip().lower() == "bulk_file" and plan.source in {
        "eurostat",
        "ilo",
        "unesco_uis",
    }:
        try:
            return await _fetch_remote_bulk_rows(
                shard,
                cache=cache,
                config=config,
                policy=policy,
                budget_windows=budget_windows,
                state_lock=state_lock,
                record_result=record_result,
                budget_wait_observer=budget_wait_observer,
            )
        except Exception as exc:
            logger.warning(
                "Bulk observation transport failed for {}/{}; falling back to API transport: {}",
                plan.source,
                plan.request_dataset_id,
                exc,
            )
    if plan.source == "worldbank":
        connector, handle = await cache.get_worldbank()
        result = await _execute_source_fetch(
            connector,
            handle,
            FetchRequest(
                dataset_id=plan.request_dataset_id,
                filters=(("country", tuple(_shard_countries(shard, config=config))),),
                date_start=datetime(start_year, 1, 1, tzinfo=UTC),
                date_end=datetime(end_year, 12, 31, tzinfo=UTC),
            ),
            source=plan.source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            record_result=record_result,
            budget_wait_observer=budget_wait_observer,
        )
        return _records_from_payload(result.data)

    if plan.source == "wvs":
        target_countries = tuple(_shard_countries(shard, config=config))
        return _filter_wvs_bulk_rows(
            cache.get_wvs_bulk_rows(
                plan.raw_variable or plan.request_dataset_id,
                country_scope=config.country_scope,
            ),
            countries=target_countries,
            year_range=(start_year, end_year),
        )

    if plan.source == "eurostat":
        connector, handle = await cache.get_eurostat()
        request_filters = _canonicalize_observation_request_filters(
            source=plan.source,
            filters=shard.filters,
            capability_snapshot=capability_snapshot,
        )
        requests = _chunked_observation_requests(
            plan=plan,
            filters=_filters_to_tuple(request_filters),
            source=plan.source,
            start_year=start_year,
            end_year=end_year,
        )
        if (
            config.is_sampled_run or config.preflight_only or config.run_profile == "preflight_core"
        ) and request_filters:
            stripped = _strip_geo_filters(request_filters)
            if stripped != request_filters:
                requests.extend(
                    _chunked_observation_requests(
                        plan=plan,
                        filters=_filters_to_tuple(stripped),
                        source=plan.source,
                        start_year=start_year,
                        end_year=end_year,
                    )
                )
        if (
            len(requests) == 1
            and async_fetch_leases is not None
            and (
                str(shard.acquisition_method or "").strip().lower() == "api_async"
                or _shard_prefers_async_fetch(
                    shard,
                    snapshot=capability_snapshot,
                    policy=policy,
                    config=config,
                )
            )
        ):
            return await _fetch_request_variants_async(
                connector,
                handle,
                requests,
                source=plan.source,
                policy=policy,
                budget_windows=budget_windows,
                state_lock=state_lock,
                async_fetch_leases=async_fetch_leases,
                lease_key=shard.shard_id,
                record_result=record_result,
                budget_wait_observer=budget_wait_observer,
            )
        return await _fetch_request_variants(
            connector,
            handle,
            requests,
            source=plan.source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            record_result=record_result,
            budget_wait_observer=budget_wait_observer,
            stop_after_first_success=bool(
                config.is_sampled_run
                or config.preflight_only
                or config.run_profile == "preflight_core"
            ),
        )

    if plan.source in {"oecd", "ilo"}:
        profile_id = plan.profile_id or ("oecd_sdmx" if plan.source == "oecd" else "ilo_sdmx")
        connector, handle = await cache.get_sdmx(profile_id)
        capability_snapshot = _apply_dimension_order_to_snapshot(
            source=plan.source,
            dataset_id=plan.request_dataset_id,
            capability_snapshot=capability_snapshot,
            dimension_order=shard.dimension_order,
        )
        request_filters = _canonicalize_observation_request_filters(
            source=plan.source,
            filters=shard.filters,
            capability_snapshot=capability_snapshot,
        )
        requests = _chunked_observation_requests(
            plan=plan,
            filters=_filters_to_tuple(request_filters),
            source=plan.source,
            start_year=start_year,
            end_year=end_year,
        )
        requests = _rewrite_sdmx_requests_with_dimension_key(
            requests,
            capability_snapshot=capability_snapshot,
        )
        if (
            config.is_sampled_run or config.preflight_only or config.run_profile == "preflight_core"
        ) and request_filters:
            stripped = _strip_geo_filters(request_filters)
            if stripped != request_filters:
                requests.extend(
                    _rewrite_sdmx_requests_with_dimension_key(
                        _chunked_observation_requests(
                            plan=plan,
                            filters=_filters_to_tuple(stripped),
                            source=plan.source,
                            start_year=start_year,
                            end_year=end_year,
                        ),
                        capability_snapshot=capability_snapshot,
                    )
                )
        return await _fetch_request_variants(
            connector,
            handle,
            requests,
            source=plan.source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            record_result=record_result,
            budget_wait_observer=budget_wait_observer,
            stop_after_first_success=bool(
                config.is_sampled_run
                or config.preflight_only
                or config.run_profile == "preflight_core"
            ),
        )

    if plan.source == "who":
        connector, handle = await cache.get_who()
        result = await _execute_source_fetch(
            connector,
            handle,
            FetchRequest(
                dataset_id=plan.request_dataset_id,
                filters=(("country", tuple(_shard_countries(shard, config=config))),),
                date_start=datetime(start_year, 1, 1, tzinfo=UTC),
                date_end=datetime(end_year, 12, 31, tzinfo=UTC),
            ),
            source=plan.source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            record_result=record_result,
            budget_wait_observer=budget_wait_observer,
        )
        return _records_from_payload(result.data)

    if plan.source == "unpd":
        connector, handle = await cache.get_unpd()
        result = await _execute_source_fetch(
            connector,
            handle,
            FetchRequest(
                dataset_id=plan.request_dataset_id,
                filters=(("country", tuple(_shard_countries(shard, config=config))),),
                date_start=datetime(start_year, 1, 1, tzinfo=UTC),
                date_end=datetime(end_year, 12, 31, tzinfo=UTC),
            ),
            source=plan.source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            record_result=record_result,
            budget_wait_observer=budget_wait_observer,
        )
        return _records_from_payload(result.data)

    if plan.source == "unesco_uis":
        connector, handle = await cache.get_unesco_uis()
        result = await _execute_source_fetch(
            connector,
            handle,
            FetchRequest(
                dataset_id=plan.request_dataset_id,
                filters=(("country", tuple(_shard_countries(shard, config=config))),),
                date_start=datetime(start_year, 1, 1, tzinfo=UTC),
                date_end=datetime(end_year, 12, 31, tzinfo=UTC),
            ),
            source=plan.source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            record_result=record_result,
            budget_wait_observer=budget_wait_observer,
        )
        return _records_from_payload(result.data)

    return []


async def _fetch_request_variants(
    connector: Any,
    handle: Any,
    requests: list[FetchRequest],
    *,
    source: str,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    record_result: Any | None = None,
    budget_wait_observer: Any | None = None,
    stop_after_first_success: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    last_exc: Exception | None = None
    for request in requests:
        try:
            result = await _execute_source_fetch(
                connector,
                handle,
                request,
                source=source,
                policy=policy,
                budget_windows=budget_windows,
                state_lock=state_lock,
                record_result=record_result,
                budget_wait_observer=budget_wait_observer,
            )
        except Exception as exc:
            last_exc = exc
            continue
        payload_rows = _records_from_payload(result.data)
        if payload_rows:
            rows.extend(payload_rows)
            if stop_after_first_success:
                break
            if request.filters:
                continue
            break
    if rows:
        return rows
    if last_exc is not None:
        raise last_exc
    return []


async def _fetch_request_variants_async(
    connector: Any,
    handle: Any,
    requests: list[FetchRequest],
    *,
    source: str,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    async_fetch_leases: dict[str, Any],
    lease_key: str,
    record_result: Any | None = None,
    budget_wait_observer: Any | None = None,
) -> list[dict[str, Any]]:
    if not requests:
        return []
    if len(requests) != 1:
        return await _fetch_request_variants(
            connector,
            handle,
            requests,
            source=source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            record_result=record_result,
            budget_wait_observer=budget_wait_observer,
        )

    request = requests[0]
    persisted = _deserialize_async_fetch_lease(async_fetch_leases.get(lease_key))
    if persisted is None:
        await _acquire_source_budget_slot(
            source=source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            budget_wait_observer=budget_wait_observer,
        )
        try:
            persisted = await connector.fetch_async(handle, request)
        except Exception as exc:
            if "Expected asynchronous Eurostat extraction response" not in str(exc):
                raise
            return await _fetch_request_variants(
                connector,
                handle,
                requests,
                source=source,
                policy=policy,
                budget_windows=budget_windows,
                state_lock=state_lock,
                record_result=record_result,
                budget_wait_observer=budget_wait_observer,
            )
        async_fetch_leases[lease_key] = _serialize_async_fetch_lease(persisted)
        if record_result is not None:
            await record_result(source=source, request_count=1)

    while True:
        await asyncio.sleep(max(float(persisted.poll_after_seconds or 0.0), 0.0))
        await _acquire_source_budget_slot(
            source=source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            budget_wait_observer=budget_wait_observer,
        )
        polled = await connector.poll_async_fetch(handle, persisted)
        if isinstance(polled, AsyncFetchLease):
            persisted = polled
            async_fetch_leases[lease_key] = _serialize_async_fetch_lease(persisted)
            if record_result is not None:
                await record_result(source=source, request_count=1)
            continue
        async_fetch_leases.pop(lease_key, None)
        if record_result is not None:
            await record_result(
                source=source,
                request_count=2,
                bytes_transferred=int(getattr(polled, "bytes_transferred", 0) or 0),
            )
        return _records_from_payload(polled.data)
