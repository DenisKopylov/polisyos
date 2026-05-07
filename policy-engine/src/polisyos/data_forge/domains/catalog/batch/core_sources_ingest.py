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


def _system_memory_bytes() -> int:
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        page_count = int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return 0
    if page_size <= 0 or page_count <= 0:
        return 0
    return page_size * page_count


def _observation_writer_memory_limit_bytes() -> int:
    total_memory = _system_memory_bytes()
    if total_memory <= 0:
        return _OBSERVATION_WRITER_MIN_MEMORY_LIMIT_BYTES
    proposed = int(total_memory * _OBSERVATION_WRITER_MEMORY_LIMIT_FRACTION)
    return max(
        _OBSERVATION_WRITER_MIN_MEMORY_LIMIT_BYTES,
        min(proposed, _OBSERVATION_WRITER_MAX_MEMORY_LIMIT_BYTES),
    )


def _format_duckdb_memory_limit(limit_bytes: int) -> str:
    limit_mb = max(int(limit_bytes // (1024 * 1024)), 512)
    return f"{limit_mb}MB"


def _observation_writer_temp_dir(db_path: Path) -> Path:
    temp_dir = db_path.parent / ".duckdb_writer_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _configure_observation_writer_connection(
    con: duckdb.DuckDBPyConnection,
    *,
    db_path: Path,
) -> None:
    statements = [
        "SET preserve_insertion_order=false",
        "SET threads=1",
    ]
    memory_limit = _observation_writer_memory_limit_bytes()
    if memory_limit > 0:
        statements.append(f"SET memory_limit='{_format_duckdb_memory_limit(memory_limit)}'")
    temp_dir = _observation_writer_temp_dir(db_path)
    temp_dir_sql = str(temp_dir).replace("'", "''")
    statements.append(f"SET temp_directory='{temp_dir_sql}'")
    for statement in statements:
        try:
            con.execute(statement)
        except Exception:
            logger.debug("DuckDB writer setting failed: {}", statement, exc_info=True)


def _iter_observation_write_item_batches(
    buffer: list[ObservationWriteItem],
    *,
    max_rows: int = _OBSERVATION_WRITER_TRANSACTION_ROWS,
    max_items: int = _OBSERVATION_WRITER_TRANSACTION_ITEMS,
) -> Any:
    current: list[ObservationWriteItem] = []
    current_rows = 0
    normalized_max_rows = max(int(max_rows), 1)
    normalized_max_items = max(int(max_items), 1)
    for item in buffer:
        projected_rows = current_rows + max(int(item.row_count), 0)
        if current and (
            projected_rows > normalized_max_rows or len(current) >= normalized_max_items
        ):
            yield current
            current = []
            current_rows = 0
        current.append(item)
        current_rows += max(int(item.row_count), 0)
    if current:
        yield current


def _log_rate_limited_warning(key: str, message: str, *args: object) -> None:
    count = int(_RATE_LIMITED_LOG_COUNTS.get(key, 0)) + 1
    _RATE_LIMITED_LOG_COUNTS[key] = count
    if count == 1 or count in {5, 10, 25, 50, 100}:
        suffix = f" [repeat_count={count}]" if count > 1 else ""
        logger.warning(message + suffix, *args)


class _ObservationFetchDeduper:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._inflight: dict[ObservationFetchKey, asyncio.Future[list[dict[str, Any]]]] = {}
        self._cache: OrderedDict[ObservationFetchKey, list[dict[str, Any]]] = OrderedDict()

    @staticmethod
    def _consume_future_exception(future: asyncio.Future[list[dict[str, Any]]]) -> None:
        try:
            future.exception()
        except (asyncio.CancelledError, Exception):
            return

    async def run(
        self,
        key: ObservationFetchKey,
        *,
        producer: Any,
    ) -> list[dict[str, Any]]:
        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return [dict(row) for row in cached]
            existing = self._inflight.get(key)
            if existing is None:
                loop = asyncio.get_running_loop()
                existing = loop.create_future()
                existing.add_done_callback(self._consume_future_exception)
                self._inflight[key] = existing
                owner = True
            else:
                owner = False
        if owner:
            try:
                rows = list(await producer())
            except Exception as exc:
                existing.set_exception(exc)
                raise
            else:
                existing.set_result(rows)
                async with self._lock:
                    self._cache[key] = [dict(row) for row in rows]
                    self._cache.move_to_end(key)
                    while len(self._cache) > _FETCH_RESULT_CACHE_SIZE:
                        self._cache.popitem(last=False)
            finally:
                async with self._lock:
                    self._inflight.pop(key, None)
        rows = await existing
        return [dict(row) for row in rows]


class _ObservationCapabilityCache:
    def __init__(self, persisted: dict[str, DatasetCapabilitySnapshot] | None = None) -> None:
        self._lock = asyncio.Lock()
        self._cache: dict[str, DatasetCapabilitySnapshot] = dict(persisted or {})
        self._inflight: dict[str, asyncio.Future[DatasetCapabilitySnapshot | None]] = {}

    @staticmethod
    def _consume_future_exception(future: asyncio.Future[DatasetCapabilitySnapshot | None]) -> None:
        try:
            future.exception()
        except (asyncio.CancelledError, Exception):
            return

    async def get(
        self,
        key: str,
        *,
        producer: Any,
    ) -> DatasetCapabilitySnapshot | None:
        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            future = self._inflight.get(key)
            if future is None:
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                future.add_done_callback(self._consume_future_exception)
                self._inflight[key] = future
                owner = True
            else:
                owner = False
        if owner:
            try:
                snapshot = await producer()
            except Exception as exc:
                future.set_exception(exc)
                raise
            else:
                future.set_result(snapshot)
                if snapshot is not None:
                    async with self._lock:
                        self._cache[key] = snapshot
            finally:
                async with self._lock:
                    self._inflight.pop(key, None)
        return await future

    async def put(self, key: str, snapshot: DatasetCapabilitySnapshot) -> None:
        async with self._lock:
            self._cache[key] = snapshot

    async def snapshot(self) -> dict[str, DatasetCapabilitySnapshot]:
        async with self._lock:
            return dict(self._cache)


@dataclass
class _WVSObservationAccumulator:
    weighted_total: float = 0.0
    weighted_value: float = 0.0
    sample_size: int = 0
    weight_field: str = ""


@dataclass
class _ConnectorSessionCache:
    worldbank: tuple[WorldBankConnector, Any] | None = None
    eurostat: tuple[EurostatConnector, Any] | None = None
    who: tuple[WHOConnector, Any] | None = None
    unpd: tuple[UNPDConnector, Any] | None = None
    unesco_uis: tuple[UNESCOUISConnector, Any] | None = None
    sdmx_by_profile: dict[str, tuple[SDMXSourceConnector, Any]] | None = None
    wvs_bulk_by_indicator: dict[str, list[dict[str, Any]]] | None = None

    def __post_init__(self) -> None:
        if self.sdmx_by_profile is None:
            self.sdmx_by_profile = {}
        if self.wvs_bulk_by_indicator is None:
            self.wvs_bulk_by_indicator = {}

    async def get_worldbank(self) -> tuple[WorldBankConnector, Any]:
        if self.worldbank is None:
            connector = WorldBankConnector()
            handle = await connector.connect(_resolve_profile_config("worldbank_wdi"))
            self.worldbank = (connector, handle)
        return self.worldbank

    async def get_eurostat(self) -> tuple[EurostatConnector, Any]:
        if self.eurostat is None:
            connector = EurostatConnector()
            handle = await connector.connect(_resolve_profile_config("eurostat_public"))
            self.eurostat = (connector, handle)
        return self.eurostat

    async def get_who(self) -> tuple[WHOConnector, Any]:
        if self.who is None:
            connector = WHOConnector()
            handle = await connector.connect(_resolve_profile_config("who_gho"))
            self.who = (connector, handle)
        return self.who

    async def get_unpd(self) -> tuple[UNPDConnector, Any]:
        if self.unpd is None:
            connector = UNPDConnector()
            handle = await connector.connect(_resolve_profile_config("unpd_dataportal"))
            self.unpd = (connector, handle)
        return self.unpd

    async def get_unesco_uis(self) -> tuple[UNESCOUISConnector, Any]:
        if self.unesco_uis is None:
            connector = UNESCOUISConnector()
            handle = await connector.connect(_resolve_profile_config("unesco_uis_public"))
            self.unesco_uis = (connector, handle)
        return self.unesco_uis

    async def get_sdmx(self, profile_id: str) -> tuple[SDMXSourceConnector, Any]:
        if profile_id not in self.sdmx_by_profile:
            connector = SDMXSourceConnector()
            handle = await connector.connect(_resolve_profile_config(profile_id))
            self.sdmx_by_profile[profile_id] = (connector, handle)
        return self.sdmx_by_profile[profile_id]

    def get_wvs_bulk_rows(
        self,
        raw_variable: str,
        *,
        country_scope: str = "full_europe",
    ) -> list[dict[str, Any]]:
        cache = self.wvs_bulk_by_indicator
        assert cache is not None
        normalized = str(raw_variable or "").strip().upper()
        key = f"{normalized}|{country_scope}"
        if key not in cache:
            try:
                cache[key] = _load_wvs_bulk_rows(normalized, country_scope=country_scope)
            except TypeError as exc:
                if "country_scope" not in str(exc):
                    raise
                cache[key] = _load_wvs_bulk_rows(normalized)
        return list(cache[key])

    async def close(self) -> None:
        if self.worldbank is not None:
            connector, handle = self.worldbank
            await connector.disconnect(handle)
        if self.eurostat is not None:
            connector, handle = self.eurostat
            await connector.disconnect(handle)
        if self.who is not None:
            connector, handle = self.who
            await connector.disconnect(handle)
        if self.unpd is not None:
            connector, handle = self.unpd
            await connector.disconnect(handle)
        if self.unesco_uis is not None:
            connector, handle = self.unesco_uis
            await connector.disconnect(handle)
        for connector, handle in self.sdmx_by_profile.values():
            await connector.disconnect(handle)


def _capability_snapshot_cache_key(plan: ObservationPlan) -> str:
    return "|".join(
        [
            str(plan.source or ""),
            str(plan.profile_id or ""),
            str(plan.request_dataset_id or ""),
        ]
    )


def _serialize_observation_plan(plan: ObservationPlan) -> dict[str, Any]:
    return {
        "dataset_id": plan.dataset_id,
        "source": plan.source,
        "raw_variable": plan.raw_variable,
        "canonical_var": plan.canonical_var,
        "connector_id": plan.connector_id,
        "profile_id": plan.profile_id,
        "request_dataset_id": plan.request_dataset_id,
        "default_filters": {
            str(key): [str(value) for value in values]
            for key, values in plan.default_filters.items()
        },
        "update_frequency": plan.update_frequency,
        "source_watermark": plan.source_watermark,
        "dataset_version": plan.dataset_version,
    }


def _deserialize_observation_plan(payload: Any) -> ObservationPlan | None:
    if not isinstance(payload, dict):
        return None
    try:
        return ObservationPlan(
            dataset_id=str(payload.get("dataset_id") or ""),
            source=str(payload.get("source") or ""),
            raw_variable=str(payload.get("raw_variable") or ""),
            canonical_var=str(payload.get("canonical_var") or ""),
            connector_id=str(payload.get("connector_id") or ""),
            profile_id=str(payload.get("profile_id") or ""),
            request_dataset_id=str(payload.get("request_dataset_id") or ""),
            default_filters={
                str(key): [str(value) for value in list(values or []) if str(value).strip()]
                for key, values in dict(payload.get("default_filters") or {}).items()
            },
            update_frequency=str(payload.get("update_frequency") or ""),
            source_watermark=str(payload.get("source_watermark") or ""),
            dataset_version=str(payload.get("dataset_version") or ""),
        )
    except Exception:
        return None


def _serialize_observation_shard(shard: ObservationShard) -> dict[str, Any]:
    return {
        "shard_id": shard.shard_id,
        "plan": _serialize_observation_plan(shard.plan),
        "country_code": shard.country_code,
        "country_codes": list(shard.country_codes),
        "start_year": int(shard.start_year),
        "end_year": int(shard.end_year),
        "filters": {
            str(key): [str(value) for value in values] for key, values in shard.filters.items()
        },
        "split_depth": int(shard.split_depth),
        "phase": str(shard.phase or "publishable_core"),
        "acquisition_method": str(shard.acquisition_method or ""),
        "source_watermark": str(shard.source_watermark or ""),
        "dataset_version": str(shard.dataset_version or ""),
        "dimension_order": [str(value) for value in shard.dimension_order],
    }


def _deserialize_observation_shard(payload: Any) -> ObservationShard | None:
    if not isinstance(payload, dict):
        return None
    plan = _deserialize_observation_plan(payload.get("plan"))
    if plan is None:
        return None
    try:
        return ObservationShard(
            shard_id=str(payload.get("shard_id") or ""),
            plan=plan,
            country_code=str(payload.get("country_code") or "").strip() or None,
            country_codes=tuple(
                str(value).strip().upper()
                for value in list(payload.get("country_codes") or [])
                if str(value).strip()
            ),
            start_year=int(payload.get("start_year")),
            end_year=int(payload.get("end_year")),
            filters={
                str(key): [str(value) for value in list(values or []) if str(value).strip()]
                for key, values in dict(payload.get("filters") or {}).items()
            },
            split_depth=max(0, int(payload.get("split_depth", 0))),
            phase=str(payload.get("phase") or "publishable_core"),
            acquisition_method=str(payload.get("acquisition_method") or ""),
            source_watermark=str(payload.get("source_watermark") or ""),
            dataset_version=str(payload.get("dataset_version") or ""),
            dimension_order=tuple(
                str(value).strip()
                for value in list(payload.get("dimension_order") or [])
                if str(value).strip()
            ),
        )
    except Exception:
        return None


def _support_sketch_id(plan: ObservationPlan) -> str:
    payload = {
        "dataset_id": plan.dataset_id,
        "source": plan.source,
        "raw_variable": plan.raw_variable,
        "canonical_var": plan.canonical_var,
        "profile_id": plan.profile_id,
        "request_dataset_id": plan.request_dataset_id,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _serialize_support_sketch(sketch: SupportSketch) -> dict[str, Any]:
    return {
        "sketch_id": sketch.sketch_id,
        "plan": _serialize_observation_plan(sketch.plan),
        "dataset_version": sketch.dataset_version,
        "supported_countries": list(sketch.supported_countries),
        "time_range": [int(sketch.time_range[0]), int(sketch.time_range[1])],
        "allowed_dimension_values": {
            str(key): [str(value) for value in values]
            for key, values in sketch.allowed_dimension_values.items()
        },
        "estimated_cardinality": int(sketch.estimated_cardinality),
        "source_watermark": sketch.source_watermark,
        "recommended_core_transport": sketch.recommended_core_transport,
        "recommended_backfill_transport": sketch.recommended_backfill_transport,
        "dimension_order": [str(value) for value in sketch.dimension_order],
    }


def _deserialize_support_sketch(payload: Any) -> SupportSketch | None:
    if not isinstance(payload, dict):
        return None
    plan = _deserialize_observation_plan(payload.get("plan"))
    if plan is None:
        return None
    try:
        raw_time_range = list(payload.get("time_range") or [])
        start_year = int(raw_time_range[0])
        end_year = int(raw_time_range[1])
        return SupportSketch(
            sketch_id=str(payload.get("sketch_id") or _support_sketch_id(plan)),
            plan=plan,
            dataset_version=str(payload.get("dataset_version") or ""),
            supported_countries=tuple(
                str(value).strip().upper()
                for value in list(payload.get("supported_countries") or [])
                if str(value).strip()
            ),
            time_range=(start_year, end_year),
            allowed_dimension_values={
                str(key): tuple(str(value) for value in list(values or []) if str(value).strip())
                for key, values in dict(payload.get("allowed_dimension_values") or {}).items()
            },
            estimated_cardinality=max(0, int(payload.get("estimated_cardinality", 0))),
            source_watermark=str(payload.get("source_watermark") or ""),
            recommended_core_transport=str(
                payload.get("recommended_core_transport")
                or payload.get("recommended_transport")
                or ""
            ),
            recommended_backfill_transport=str(
                payload.get("recommended_backfill_transport")
                or payload.get("recommended_core_transport")
                or payload.get("recommended_transport")
                or ""
            ),
            dimension_order=tuple(
                str(value).strip()
                for value in list(payload.get("dimension_order") or [])
                if str(value).strip()
            ),
        )
    except Exception:
        return None


def _load_support_sketch_state(state: dict[str, Any]) -> dict[str, SupportSketch]:
    sketches: dict[str, SupportSketch] = {}
    for key, payload in state.items():
        sketch = _deserialize_support_sketch(payload)
        if sketch is not None:
            sketches[str(key)] = sketch
    return sketches


def _serialize_support_sketch_state(
    sketches: dict[str, SupportSketch],
) -> dict[str, dict[str, Any]]:
    return {key: _serialize_support_sketch(sketch) for key, sketch in sketches.items()}


def _load_work_package_state(state: dict[str, Any]) -> dict[str, ObservationShard]:
    work_packages: dict[str, ObservationShard] = {}
    for key, payload in state.items():
        shard = _deserialize_observation_shard(payload)
        if shard is not None:
            work_packages[str(key)] = shard
    return work_packages


def _serialize_work_package_state(
    work_packages: dict[str, ObservationShard],
) -> dict[str, dict[str, Any]]:
    return {key: _serialize_observation_shard(shard) for key, shard in work_packages.items()}


def _serialize_capability_snapshot(snapshot: DatasetCapabilitySnapshot) -> dict[str, Any]:
    return snapshot.model_dump(mode="json")


def _deserialize_capability_snapshot(payload: Any) -> DatasetCapabilitySnapshot | None:
    if not isinstance(payload, dict):
        return None
    try:
        return DatasetCapabilitySnapshot.model_validate(payload)
    except Exception:
        return None


def _load_capability_snapshot_state(state: dict[str, Any]) -> dict[str, DatasetCapabilitySnapshot]:
    snapshots: dict[str, DatasetCapabilitySnapshot] = {}
    for key, payload in state.items():
        snapshot = _deserialize_capability_snapshot(payload)
        if snapshot is not None:
            snapshots[str(key)] = snapshot
    return snapshots


def _serialize_capability_snapshot_state(
    snapshots: dict[str, DatasetCapabilitySnapshot],
) -> dict[str, dict[str, Any]]:
    return {key: _serialize_capability_snapshot(snapshot) for key, snapshot in snapshots.items()}


def _normalize_dimension_order(values: Any) -> tuple[str, ...]:
    return tuple(str(value).strip() for value in list(values or []) if str(value).strip())


def _infer_ilo_dimension_order(request_dataset_id: str) -> tuple[str, ...]:
    dataset_id = str(request_dataset_id or "").strip().upper()
    if not dataset_id.startswith("DF_"):
        return ()
    parts = [part.strip().upper() for part in dataset_id.split("_") if part.strip()]
    if len(parts) < 4:
        return ()
    inferred: list[str] = ["REF_AREA", "FREQ", "MEASURE"]
    seen = set(inferred)
    for token in parts[2:-1]:
        if token not in _ILO_INFERRED_DIMENSION_TOKENS or token in seen:
            continue
        inferred.append(token)
        seen.add(token)
    return tuple(inferred)


def _infer_dimension_order_for_plan(plan: ObservationPlan) -> tuple[str, ...]:
    source = str(plan.source or "").strip().lower()
    if source == "ilo":
        return _infer_ilo_dimension_order(plan.request_dataset_id)
    return ()


def _hydrate_support_sketch_dimension_orders(
    sketches: dict[str, SupportSketch],
    *,
    capability_snapshots: dict[str, DatasetCapabilitySnapshot],
) -> tuple[dict[str, SupportSketch], int]:
    hydrated: dict[str, SupportSketch] = {}
    changes = 0
    for key, sketch in sketches.items():
        dimension_order = _normalize_dimension_order(sketch.dimension_order)
        if not dimension_order:
            snapshot = capability_snapshots.get(_capability_snapshot_cache_key(sketch.plan))
            dimension_order = _normalize_dimension_order(
                snapshot.dimension_order if snapshot is not None else ()
            )
        if not dimension_order:
            dimension_order = _infer_dimension_order_for_plan(sketch.plan)
        if dimension_order != sketch.dimension_order:
            hydrated[key] = replace(sketch, dimension_order=dimension_order)
            changes += 1
            continue
        hydrated[key] = sketch
    return hydrated, changes


def _hydrate_work_package_dimension_orders(
    work_packages: dict[str, ObservationShard],
    *,
    support_sketches: dict[str, SupportSketch],
    capability_snapshots: dict[str, DatasetCapabilitySnapshot],
) -> tuple[dict[str, ObservationShard], int]:
    hydrated: dict[str, ObservationShard] = {}
    changes = 0
    for key, shard in work_packages.items():
        dimension_order = _normalize_dimension_order(shard.dimension_order)
        if not dimension_order:
            sketch = support_sketches.get(_support_sketch_id(shard.plan))
            if sketch is not None:
                dimension_order = _normalize_dimension_order(sketch.dimension_order)
        if not dimension_order:
            snapshot = capability_snapshots.get(_capability_snapshot_cache_key(shard.plan))
            dimension_order = _normalize_dimension_order(
                snapshot.dimension_order if snapshot is not None else ()
            )
        if not dimension_order:
            dimension_order = _infer_dimension_order_for_plan(shard.plan)
        if dimension_order != shard.dimension_order:
            hydrated[key] = replace(shard, dimension_order=dimension_order)
            changes += 1
            continue
        hydrated[key] = shard
    return hydrated, changes


def _serialize_async_fetch_lease(lease: AsyncFetchLease) -> dict[str, Any]:
    return lease.model_dump(mode="json")


def _deserialize_async_fetch_lease(payload: Any) -> AsyncFetchLease | None:
    if not isinstance(payload, dict):
        return None
    try:
        return AsyncFetchLease.model_validate(payload)
    except Exception:
        return None


def _capability_snapshot_fresh(
    snapshot: DatasetCapabilitySnapshot,
    *,
    policy: SourceExecutionPolicy,
) -> bool:
    ttl_hours = max(1, int(policy.capability_cache_ttl_hours or 24))
    checked_at = snapshot.last_checked_at
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    else:
        checked_at = checked_at.astimezone(UTC)
    return checked_at + timedelta(hours=ttl_hours) >= datetime.now(UTC)


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


def _migrate_legacy_support_cache(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    unsupported: dict[str, Any] = {}
    empty: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        if bool(value.get("unsupported")):
            unsupported[key] = dict(value)
            continue
        if int(value.get("empty_hits", 0) or 0) > 0:
            empty[key] = {
                "updated_at": value.get("updated_at", ""),
                "expires_at": value.get("expires_at", ""),
            }
    return unsupported, empty


def _migrate_deferred_unsupported_results(
    completed: dict[str, Any],
    deferred: dict[str, Any],
) -> int:
    migrated = 0
    for shard_id, payload in list(deferred.items()):
        if not isinstance(payload, dict):
            continue
        error_text = str(payload.get("error") or payload.get("last_error") or "").strip()
        if not error_text or not _is_explicit_unsupported_error(RuntimeError(error_text)):
            continue
        completed[shard_id] = {
            **payload,
            "status": "complete_empty",
            "row_count": int(payload.get("row_count", 0) or 0),
            "error": error_text,
        }
        deferred.pop(shard_id, None)
        migrated += 1
    return migrated


def _migrate_dimensionless_ilo_capability_snapshots(
    capability_snapshots: dict[str, Any],
) -> int:
    migrated = 0
    for cache_key, payload in list(capability_snapshots.items()):
        if not isinstance(payload, dict):
            continue
        source = str(payload.get("source") or "").strip().lower()
        if source != "ilo":
            continue
        if tuple(
            str(value).strip()
            for value in list(payload.get("dimension_order") or [])
            if str(value).strip()
        ):
            continue
        capability_snapshots.pop(cache_key, None)
        migrated += 1
    return migrated


def _reactivate_retryable_deferred_results(
    work_packages: dict[str, Any],
    deferred: dict[str, Any],
    async_fetch_leases: dict[str, Any],
) -> int:
    migrated = 0
    for shard_id, payload in list(deferred.items()):
        if not isinstance(payload, dict):
            continue
        work_package = work_packages.get(shard_id)
        if not isinstance(work_package, dict):
            continue
        plan = work_package.get("plan")
        if not isinstance(plan, dict):
            plan = {}
        source = str(payload.get("source") or plan.get("source") or "").strip().lower()
        error_text = str(payload.get("error") or payload.get("last_error") or "").strip()
        if not error_text:
            continue
        status_code = _planner_error_status_code(RuntimeError(error_text))
        if source == "ilo" and status_code == 422:
            deferred.pop(shard_id, None)
            async_fetch_leases.pop(shard_id, None)
            migrated += 1
            continue
        if (
            source == "eurostat"
            and status_code == 405
            and str(work_package.get("acquisition_method") or "").strip().lower() == "api_async"
        ):
            work_package["acquisition_method"] = "bulk_file"
            deferred.pop(shard_id, None)
            async_fetch_leases.pop(shard_id, None)
            migrated += 1
    return migrated


def _load_observation_checkpoint_state(config: DatasetBatchConfig) -> dict[str, Any]:
    payload = load_json(config.observation_ingest_checkpoint_path, default={})
    if not isinstance(payload, dict):
        payload = {}
    completed = payload.get("completed", {})
    failed = payload.get("failed", {})
    deferred = payload.get("deferred", {})
    legacy_support_cache = payload.get("support_cache", {})
    unsupported_signatures = payload.get("unsupported_signatures", {})
    empty_signatures = payload.get("empty_signatures", {})
    if not isinstance(unsupported_signatures, dict):
        unsupported_signatures = {}
    if not isinstance(empty_signatures, dict):
        empty_signatures = {}
    if (not unsupported_signatures and not empty_signatures) and isinstance(
        legacy_support_cache, dict
    ):
        migrated_unsupported, migrated_empty = _migrate_legacy_support_cache(legacy_support_cache)
        unsupported_signatures = migrated_unsupported
        empty_signatures = migrated_empty
    inflight_leases = payload.get("inflight_leases", {})
    async_fetch_leases = payload.get("async_fetch_leases", {})
    capability_snapshots = payload.get("capability_snapshots", {})
    capability_failures = payload.get("capability_failures", {})
    source_budgets = payload.get("source_budgets", {})
    writer_state = payload.get("writer_state", {})
    support_sketches = payload.get("support_sketches", {})
    work_packages = payload.get("work_packages", {})
    planner_phase = payload.get("planner_phase", "support_sketch")
    publishable_core_complete = payload.get("publishable_core_complete", False)
    negative_cache_version = payload.get("negative_cache_version", 1)
    planner_signature = payload.get("planner_signature", "")
    completed = completed if isinstance(completed, dict) else {}
    failed = failed if isinstance(failed, dict) else {}
    deferred = deferred if isinstance(deferred, dict) else {}
    async_fetch_leases = async_fetch_leases if isinstance(async_fetch_leases, dict) else {}
    capability_snapshots = capability_snapshots if isinstance(capability_snapshots, dict) else {}
    work_packages = work_packages if isinstance(work_packages, dict) else {}
    migrated_deferred = _migrate_deferred_unsupported_results(completed, deferred)
    migrated_retryable = _reactivate_retryable_deferred_results(
        work_packages,
        deferred,
        async_fetch_leases,
    )
    migrated_capability_snapshots = _migrate_dimensionless_ilo_capability_snapshots(
        capability_snapshots
    )
    if migrated_deferred > 0 or migrated_retryable > 0 or migrated_capability_snapshots > 0:
        _write_observation_checkpoint_state(
            config,
            completed=completed,
            failed=failed,
            deferred=deferred,
            unsupported_signatures=unsupported_signatures,
            empty_signatures=empty_signatures,
            inflight_leases=inflight_leases if isinstance(inflight_leases, dict) else {},
            async_fetch_leases=async_fetch_leases,
            capability_snapshots=capability_snapshots,
            capability_failures=capability_failures
            if isinstance(capability_failures, dict)
            else {},
            source_budgets=source_budgets if isinstance(source_budgets, dict) else {},
            writer_state=writer_state if isinstance(writer_state, dict) else {},
            support_sketches=support_sketches if isinstance(support_sketches, dict) else {},
            work_packages=work_packages,
            planner_phase=str(planner_phase or "support_sketch"),
            publishable_core_complete=bool(publishable_core_complete),
            negative_cache_version=max(1, int(negative_cache_version or 1)),
            planner_signature=str(planner_signature or ""),
        )
    return {
        "completed": completed,
        "failed": failed,
        "deferred": deferred,
        "unsupported_signatures": unsupported_signatures,
        "empty_signatures": empty_signatures,
        "inflight_leases": inflight_leases if isinstance(inflight_leases, dict) else {},
        "async_fetch_leases": async_fetch_leases,
        "capability_snapshots": capability_snapshots,
        "capability_failures": capability_failures if isinstance(capability_failures, dict) else {},
        "source_budgets": source_budgets if isinstance(source_budgets, dict) else {},
        "writer_state": writer_state if isinstance(writer_state, dict) else {},
        "support_sketches": support_sketches if isinstance(support_sketches, dict) else {},
        "work_packages": work_packages,
        "planner_phase": str(planner_phase or "support_sketch"),
        "publishable_core_complete": bool(publishable_core_complete),
        "negative_cache_version": max(1, int(negative_cache_version or 1)),
        "planner_signature": str(planner_signature or ""),
    }


def _write_observation_checkpoint_state(
    config: DatasetBatchConfig,
    *,
    completed: dict[str, Any],
    failed: dict[str, Any],
    deferred: dict[str, Any],
    unsupported_signatures: dict[str, Any],
    empty_signatures: dict[str, Any],
    inflight_leases: dict[str, Any],
    async_fetch_leases: dict[str, Any],
    capability_snapshots: dict[str, Any],
    capability_failures: dict[str, Any],
    source_budgets: dict[str, Any],
    writer_state: dict[str, Any],
    support_sketches: dict[str, Any] | None = None,
    work_packages: dict[str, Any] | None = None,
    planner_phase: str = "support_sketch",
    publishable_core_complete: bool = False,
    negative_cache_version: int = 2,
    planner_signature: str = "",
) -> None:
    write_json(
        config.observation_ingest_checkpoint_path,
        {
            "completed": completed,
            "failed": failed,
            "deferred": deferred,
            "unsupported_signatures": unsupported_signatures,
            "empty_signatures": empty_signatures,
            "support_cache": unsupported_signatures,
            "inflight_leases": inflight_leases,
            "async_fetch_leases": async_fetch_leases,
            "capability_snapshots": capability_snapshots,
            "capability_failures": capability_failures,
            "source_budgets": source_budgets,
            "writer_state": writer_state,
            "support_sketches": support_sketches or {},
            "work_packages": work_packages or {},
            "planner_phase": planner_phase,
            "publishable_core_complete": bool(publishable_core_complete),
            "negative_cache_version": max(1, int(negative_cache_version)),
            "planner_signature": planner_signature,
        },
    )


def _support_cache_key(
    shard: ObservationShard,
    *,
    capability: DatasetCapabilitySnapshot | None = None,
) -> str:
    filters_json = json.dumps(
        shard.filters, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    country_codes = tuple(
        code
        for code in (shard.country_codes or ((shard.country_code,) if shard.country_code else ()))
        if str(code).strip()
    )
    countries_json = json.dumps(country_codes, ensure_ascii=False, separators=(",", ":"))
    dataset_version = (
        str(capability.version_hint or "").strip()
        if capability is not None and getattr(capability, "version_hint", None)
        else str(shard.dataset_version or shard.plan.dataset_version or "")
    )
    transport = str(
        shard.acquisition_method
        or (
            capability.preferred_transport
            if capability is not None and getattr(capability, "preferred_transport", None)
            else ""
        )
    ).strip()
    return "|".join(
        [
            str(shard.plan.source or ""),
            str(
                capability.resolved_dataset_id
                if capability is not None and capability.resolved_dataset_id
                else shard.plan.request_dataset_id or ""
            ),
            dataset_version,
            transport,
            str(shard.country_code or ""),
            countries_json,
            filters_json,
            str(capability.constraint_hash if capability is not None else ""),
        ]
    )


def _support_cache_entry_active(entry: dict[str, Any], *, now: datetime) -> bool:
    expires_at = str(entry.get("expires_at") or "").strip()
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    return expiry >= now


def _support_cache_proves_unsupported(entry: dict[str, Any], *, now: datetime) -> bool:
    if not _support_cache_entry_active(entry, now=now):
        return False
    return bool(entry.get("unsupported"))


def _empty_signature_cache_hit(entry: dict[str, Any], *, now: datetime) -> bool:
    if not entry:
        return False
    if "updated_at" not in entry and "expires_at" not in entry:
        return False
    return _support_cache_entry_active(entry, now=now)


def _update_unsupported_signature_cache(
    support_cache: dict[str, Any],
    *,
    key: str,
    policy: SourceExecutionPolicy,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    ttl = timedelta(hours=max(1, _policy_int_attr(policy, "negative_cache_ttl_hours", 24)))
    payload = {
        "unsupported": True,
        "updated_at": now.isoformat(),
        "expires_at": (now + ttl).isoformat(),
    }
    support_cache[key] = payload
    return payload


def _update_empty_signature_cache(
    empty_signatures: dict[str, Any],
    *,
    key: str,
    policy: SourceExecutionPolicy,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    ttl = timedelta(hours=max(1, _policy_int_attr(policy, "soft_negative_cache_ttl_hours", 24)))
    payload = {
        "updated_at": now.isoformat(),
        "expires_at": (now + ttl).isoformat(),
    }
    empty_signatures[key] = payload
    return payload


def _update_support_cache(
    unsupported_signatures: dict[str, Any],
    empty_signatures: dict[str, Any],
    *,
    key: str,
    policy: SourceExecutionPolicy,
    unsupported: bool = False,
    empty_result: bool = False,
    promote_empty_to_unsupported: bool = False,
) -> dict[str, Any] | None:
    if unsupported:
        empty_signatures.pop(key, None)
        return _update_unsupported_signature_cache(
            unsupported_signatures,
            key=key,
            policy=policy,
        )
    if empty_result:
        if promote_empty_to_unsupported:
            return _update_unsupported_signature_cache(
                unsupported_signatures,
                key=key,
                policy=policy,
            )
        unsupported_signatures.pop(key, None)
        return _update_empty_signature_cache(
            empty_signatures,
            key=key,
            policy=policy,
        )
    return None


def _prune_expired_support_cache(support_cache: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        key: value
        for key, value in support_cache.items()
        if isinstance(value, dict) and _support_cache_entry_active(value, now=now)
    }


def _source_completion_pct_by_phase(
    work_packages: dict[str, ObservationShard],
    *,
    completed: dict[str, Any],
    selected_phases: set[str],
) -> tuple[dict[str, float], dict[str, float]]:
    completed_ids = {str(shard_id) for shard_id in completed if str(shard_id).strip()}
    core_totals: dict[str, int] = {}
    core_done: dict[str, int] = {}
    full_totals: dict[str, int] = {}
    full_done: dict[str, int] = {}
    for shard_id, shard in work_packages.items():
        if shard.phase not in selected_phases:
            continue
        source = str(shard.plan.source or "")
        full_totals[source] = full_totals.get(source, 0) + 1
        if shard.phase == "publishable_core":
            core_totals[source] = core_totals.get(source, 0) + 1
        if shard_id in completed_ids:
            full_done[source] = full_done.get(source, 0) + 1
            if shard.phase == "publishable_core":
                core_done[source] = core_done.get(source, 0) + 1

    sources = sorted(set(full_totals) | set(core_totals))
    core_pct = {
        source: round(
            100.0 * float(core_done.get(source, 0)) / max(float(core_totals.get(source, 0)), 1.0),
            2,
        )
        for source in sources
    }
    full_pct = {
        source: round(
            100.0 * float(full_done.get(source, 0)) / max(float(full_totals.get(source, 0)), 1.0),
            2,
        )
        for source in sources
    }
    return core_pct, full_pct


def _capability_dimension_values(
    snapshot: DatasetCapabilitySnapshot | None,
    *names: str,
) -> tuple[str, ...]:
    if snapshot is None:
        return ()
    allowed = snapshot.allowed_positions or {}
    for name in names:
        values = allowed.get(name)
        if values:
            return tuple(str(value) for value in values if str(value).strip())
    lowered = {str(key).lower(): value for key, value in allowed.items()}
    for name in names:
        values = lowered.get(name.lower())
        if values:
            return tuple(str(value) for value in values if str(value).strip())
    return ()


def _shard_supported_by_capability(
    shard: ObservationShard,
    *,
    snapshot: DatasetCapabilitySnapshot | None,
) -> bool:
    if snapshot is None:
        return True
    allowed_geo = _capability_dimension_values(snapshot, "geo", "country", "ref_area")
    if allowed_geo:
        requested_countries = shard.country_codes or (
            (shard.country_code,) if shard.country_code else ()
        )
        for country_code in requested_countries:
            iso2 = str(country_code or "").strip().upper()
            iso3 = _to_iso3(iso2)
            numeric = iso2_to_numeric(iso2) or ""
            allowed = {str(value).strip().upper() for value in allowed_geo if str(value).strip()}
            if iso2 not in allowed and iso3 not in allowed and numeric not in allowed:
                return False
    return not (
        shard.country_code
        and not shard.country_codes
        and allowed_geo
        and shard.country_code not in allowed_geo
    )


def _split_shard_by_filter_values(
    shard: ObservationShard,
    *,
    split_key: str,
    values: list[str],
) -> list[ObservationShard]:
    if len(values) <= 1:
        return []
    midpoint = max(len(values) // 2, 1)
    left_filters = {key: list(current) for key, current in shard.filters.items()}
    right_filters = {key: list(current) for key, current in shard.filters.items()}
    left_filters[split_key] = values[:midpoint]
    right_filters[split_key] = values[midpoint:]
    return [
        ObservationShard(
            shard_id=_observation_shard_id(
                plan=shard.plan,
                country_code=shard.country_code,
                country_codes=shard.country_codes,
                start_year=shard.start_year,
                end_year=shard.end_year,
                filters=current_filters,
                split_depth=shard.split_depth + 1,
            ),
            plan=shard.plan,
            country_code=shard.country_code,
            country_codes=shard.country_codes,
            start_year=shard.start_year,
            end_year=shard.end_year,
            filters=current_filters,
            split_depth=shard.split_depth + 1,
            phase=shard.phase,
            acquisition_method=shard.acquisition_method,
            source_watermark=shard.source_watermark,
            dataset_version=shard.dataset_version,
            dimension_order=shard.dimension_order,
        )
        for current_filters in (left_filters, right_filters)
        if current_filters.get(split_key)
    ]


def _split_shard_by_country_group(shard: ObservationShard) -> list[ObservationShard]:
    countries = list(shard.country_codes)
    if len(countries) <= 1:
        return []
    midpoint = max(len(countries) // 2, 1)
    groups = [tuple(countries[:midpoint]), tuple(countries[midpoint:])]
    out: list[ObservationShard] = []
    for group in groups:
        if not group:
            continue
        filters = dict(shard.filters)
        if shard.plan.source == "eurostat":
            filters = _eurostat_filters_for_countries(
                group, base_filters=_strip_geo_filters(filters)
            )
        elif shard.plan.source in {"oecd", "ilo"}:
            filters = _sdmx_filters_for_countries(group, base_filters=_strip_geo_filters(filters))
        country_code = group[0] if len(group) == 1 else None
        out.append(
            ObservationShard(
                shard_id=_observation_shard_id(
                    plan=shard.plan,
                    country_code=country_code,
                    country_codes=group,
                    start_year=shard.start_year,
                    end_year=shard.end_year,
                    filters=filters,
                    split_depth=shard.split_depth + 1,
                ),
                plan=shard.plan,
                country_code=country_code,
                country_codes=group,
                start_year=shard.start_year,
                end_year=shard.end_year,
                filters=filters,
                split_depth=shard.split_depth + 1,
                phase=shard.phase,
                acquisition_method=shard.acquisition_method,
                source_watermark=shard.source_watermark,
                dataset_version=shard.dataset_version,
                dimension_order=shard.dimension_order,
            )
        )
    return out


def _time_dimension_cardinality(shard: ObservationShard) -> int:
    span_years = max(int(shard.end_year) - int(shard.start_year) + 1, 1)
    frequency_rank = _observation_frequency_rank(shard.plan.update_frequency)
    if frequency_rank >= 2:
        return span_years * 12
    if frequency_rank >= 1:
        return span_years * 4
    return span_years


def _estimate_shard_cardinality(
    shard: ObservationShard,
    *,
    snapshot: DatasetCapabilitySnapshot | None,
) -> int:
    if snapshot is None:
        return 0
    filter_map = {
        str(key): [str(value) for value in values if str(value).strip()]
        for key, values in shard.filters.items()
    }
    dimensions = tuple(snapshot.dimension_order or tuple(filter_map.keys()))
    estimate = 1
    has_signal = False
    for dimension in dimensions:
        normalized = str(dimension).strip()
        lowered = normalized.lower()
        count = 0
        if lowered in {"geo", "country", "ref_area"}:
            if shard.country_codes:
                count = len(shard.country_codes)
            elif shard.country_code:
                count = 1
            else:
                allowed = _capability_dimension_values(
                    snapshot, normalized, "geo", "country", "ref_area"
                )
                count = len(allowed)
        elif lowered in {"time", "time_period"}:
            filter_values = filter_map.get(normalized) or filter_map.get(lowered) or []
            count = len(filter_values) if filter_values else _time_dimension_cardinality(shard)
        else:
            filter_values = (
                filter_map.get(normalized)
                or filter_map.get(lowered)
                or filter_map.get(normalized.upper())
                or []
            )
            if filter_values:
                count = len(filter_values)
            else:
                allowed = _capability_dimension_values(snapshot, normalized)
                count = len(allowed)
        if count <= 0:
            continue
        has_signal = True
        estimate *= count
    if has_signal:
        return estimate
    return int(snapshot.estimated_cardinality or 0)


def _shard_prefers_async_fetch(
    shard: ObservationShard,
    *,
    snapshot: DatasetCapabilitySnapshot | None,
    policy: SourceExecutionPolicy,
    config: DatasetBatchConfig,
) -> bool:
    if shard.plan.source != "eurostat":
        return False
    if not _policy_bool_attr(policy, "supports_async_fetch", False):
        return False
    if config.is_sampled_run or config.preflight_only or config.run_profile == "preflight_core":
        return False
    estimated = _estimate_shard_cardinality(shard, snapshot=snapshot)
    max_sync = _policy_int_attr(policy, "max_sync_cells", 0)
    max_async = _policy_int_attr(policy, "max_async_cells", 0)
    if estimated <= 0 or max_sync <= 0 or max_async <= 0:
        return False
    return max_sync < estimated <= max_async


def _planner_split_shard_from_capability(
    shard: ObservationShard,
    *,
    snapshot: DatasetCapabilitySnapshot | None,
    policy: SourceExecutionPolicy,
) -> list[ObservationShard]:
    max_cells = _policy_int_attr(policy, "max_sync_cells", 0)
    if snapshot is None or max_cells <= 0:
        return [shard]
    estimated = _estimate_shard_cardinality(shard, snapshot=snapshot)
    if estimated <= 0 or estimated <= max_cells:
        return [shard]
    max_async = _policy_int_attr(policy, "max_async_cells", 0)
    if (
        _policy_bool_attr(policy, "supports_async_fetch", False)
        and max_async > 0
        and estimated <= max_async
    ):
        return [shard]
    if shard.start_year < shard.end_year:
        synthetic_413 = RuntimeError(f"payload cardinality split {estimated}>{max_cells}")
        return _split_shard_for_retry(shard, synthetic_413) or [shard]
    if len(shard.country_codes) > 1:
        split = _split_shard_by_country_group(shard)
        if split:
            return split
    preferred_dims = tuple(snapshot.dimension_order or ())
    for key in preferred_dims:
        normalized_key = str(key).strip()
        if not normalized_key or normalized_key.lower() in {
            "geo",
            "country",
            "ref_area",
            "time",
            "time_period",
        }:
            continue
        allowed = _capability_dimension_values(snapshot, normalized_key)
        if len(allowed) > 1:
            split_values = list(shard.filters.get(normalized_key) or allowed)
            split_values = [str(value) for value in split_values if str(value).strip()]
            if len(split_values) > 1:
                split = _split_shard_by_filter_values(
                    shard, split_key=normalized_key, values=split_values
                )
                if split:
                    return split
    return [shard]


def _empty_result_proves_unsupported(
    *,
    shard: ObservationShard,
    snapshot: DatasetCapabilitySnapshot | None,
) -> bool:
    del shard, snapshot
    return False


def _load_source_budget_windows(state: dict[str, Any]) -> dict[str, _SourceBudgetWindow]:
    out: dict[str, _SourceBudgetWindow] = {}
    for source, payload in state.items():
        if not isinstance(payload, dict):
            continue
        started_at = str(payload.get("window_started_at") or "").strip()
        try:
            window_started_at = (
                datetime.fromisoformat(started_at) if started_at else datetime.now(UTC)
            )
        except ValueError:
            window_started_at = datetime.now(UTC)
        out[str(source)] = _SourceBudgetWindow(
            window_started_at=window_started_at,
            requests_used=max(0, int(payload.get("requests_used", 0))),
        )
    return out


def _serialize_source_budget_windows(
    state: dict[str, _SourceBudgetWindow],
) -> dict[str, dict[str, Any]]:
    return {
        source: {
            "window_started_at": bucket.window_started_at.isoformat(),
            "requests_used": int(bucket.requests_used),
        }
        for source, bucket in state.items()
    }


def _serialize_writer_state(state: WriterFlushState) -> dict[str, Any]:
    return {
        "buffered_rows": int(state.buffered_rows),
        "buffered_bytes": int(state.buffered_bytes),
        "flush_count": int(state.flush_count),
        "last_flush_at": float(state.last_flush_at),
        "last_flush_latency_ms": float(state.last_flush_latency_ms),
    }


def _deserialize_writer_state(payload: Any) -> WriterFlushState:
    if not isinstance(payload, dict):
        return WriterFlushState(last_flush_at=time.monotonic())
    return WriterFlushState(
        buffered_rows=max(0, int(payload.get("buffered_rows", 0) or 0)),
        buffered_bytes=max(0, int(payload.get("buffered_bytes", 0) or 0)),
        flush_count=max(0, int(payload.get("flush_count", 0) or 0)),
        last_flush_at=float(payload.get("last_flush_at", 0.0) or 0.0) or time.monotonic(),
        last_flush_latency_ms=max(0.0, float(payload.get("last_flush_latency_ms", 0.0) or 0.0)),
    )


def _capability_failure_entry_active(
    entry: dict[str, Any],
    *,
    now: datetime,
) -> bool:
    expires_at = str(entry.get("expires_at") or "").strip()
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    return expiry >= now


def _prune_expired_capability_failures(capability_failures: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        key: value
        for key, value in capability_failures.items()
        if isinstance(value, dict) and _capability_failure_entry_active(value, now=now)
    }


def _serialize_capability_failure(
    *,
    plan: ObservationPlan,
    policy: SourceExecutionPolicy,
    exc: Exception,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    ttl = timedelta(hours=max(1, int(policy.capability_cache_ttl_hours or 24)))
    status_code = _planner_error_status_code(exc)
    return {
        "source": str(plan.source or ""),
        "dataset_id": str(plan.request_dataset_id or ""),
        "status_code": int(status_code) if status_code is not None else None,
        "error": str(exc),
        "updated_at": now.isoformat(),
        "expires_at": (now + ttl).isoformat(),
    }


def _capability_failure_supports_fallback(
    entry: dict[str, Any],
    *,
    now: datetime,
) -> bool:
    if not _capability_failure_entry_active(entry, now=now):
        return False
    status_code = entry.get("status_code")
    try:
        normalized = int(status_code)
    except (TypeError, ValueError):
        normalized = None
    return normalized in _CAPABILITY_NEGATIVE_STATUS_CODES


def _capability_failures_by_source(capability_failures: dict[str, Any]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for value in capability_failures.values():
        if not isinstance(value, dict):
            continue
        source = str(value.get("source") or "").strip()
        if not source:
            continue
        summary[source] = summary.get(source, 0) + 1
    return summary


def _write_core_ingest_stage_progress(
    config: DatasetBatchConfig,
    *,
    metadata: dict[str, Any],
) -> None:
    state = load_json(config.stage_state_path, default={})
    if not isinstance(state, dict):
        state = {}
    current = state.get("core_sources_ingest", {})
    if not isinstance(current, dict):
        current = {}
    state["core_sources_ingest"] = {
        "status": "running",
        "input_fingerprint": str(current.get("input_fingerprint", "")),
        "outputs": [str(config.db_path)],
        "metadata": metadata,
    }
    write_json(config.stage_state_path, state)


def _seed_alignments_path() -> Path:
    return (
        Path(__file__).resolve().parents[6]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )


def _wvs_raw_dir() -> Path:
    return Path(__file__).resolve().parents[6] / "data" / "raw" / "wvs"


def _wvs_bulk_csv_path() -> Path:
    return _wvs_raw_dir() / "WVS_Time_Series_1981-2022_csv_v5_0.csv"


def _wvs_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[6]
        / "data"
        / "dataset_catalog"
        / "wvs_indicator_registry.yaml"
    )


_wvs_registry_cache: dict[str, dict] | None = None


def _load_wvs_registry() -> dict[str, dict]:
    """Load WVS indicator registry YAML. Returns ``{code: spec}``."""
    global _wvs_registry_cache
    if _wvs_registry_cache is not None:
        return _wvs_registry_cache
    path = _wvs_registry_path()
    if not path.exists():
        _wvs_registry_cache = {}
        return _wvs_registry_cache
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        indicators = data.get("indicators", {}) if isinstance(data, dict) else {}
        _wvs_registry_cache = {
            str(k).strip().upper(): v for k, v in indicators.items() if isinstance(v, dict)
        }
    except Exception:
        logger.warning("Failed to load WVS indicator registry")
        _wvs_registry_cache = {}
    return _wvs_registry_cache


def _wvs_legacy_indicators() -> dict[str, str]:
    """Return ``{indicator_code: primary_canonical_var}`` from registry, fallback to static."""
    registry = _load_wvs_registry()
    if not registry:
        return dict(_LEGACY_WVS_INDICATORS_STATIC)
    result: dict[str, str] = {}
    for code, spec in registry.items():
        candidates = spec.get("canonical_candidates", [])
        if isinstance(candidates, str):
            candidates = [candidates]
        if candidates:
            result[code] = str(candidates[0])
    return result if result else dict(_LEGACY_WVS_INDICATORS_STATIC)


def _wvs_aggregation_method(indicator: str) -> str:
    """Return aggregation method for a WVS indicator from registry."""
    registry = _load_wvs_registry()
    spec = registry.get(indicator.upper(), {})
    if spec:
        return str(spec.get("aggregation", "weighted_mean"))
    return _WVS_SPECIAL_AGGREGATIONS_STATIC.get(indicator, "weighted_mean")


def _wvs_response_type(indicator: str) -> str:
    """Return response_type for a WVS indicator from registry."""
    registry = _load_wvs_registry()
    spec = registry.get(indicator.upper(), {})
    return str(spec.get("response_type", "continuous"))


def _load_wvs_bulk_duckdb(
    indicators: list[str],
    *,
    country_scope: str = "core_blocking",
    year_window: tuple[int, int] = (1981, 2023),
) -> dict[str, list[dict[str, Any]]]:
    """Load multiple WVS indicators in a single DuckDB pass over the CSV.

    Returns ``{indicator_code: [aggregated_rows]}`` for all requested indicators.
    Uses DuckDB's columnar CSV reader for 10x speedup vs Python csv.DictReader.
    """
    csv_path = _wvs_bulk_csv_path()
    if not csv_path.exists():
        raise RuntimeError(f"WVS bulk CSV is required: {csv_path}")
    if not indicators:
        return {}

    # Normalize indicator names
    indicators = [i.strip().upper() for i in indicators if i.strip()]
    if not indicators:
        return {}

    # Resolve target countries (ISO-3)
    target_countries = {
        iso2_to_iso3(c) for c in country_scope_members(country_scope) if iso2_to_iso3(c)
    }
    if not target_countries:
        return {indicator: [] for indicator in indicators}

    # Build DuckDB query selecting only needed columns
    # Columns: COUNTRY_ALPHA, S020 (survey_year), S002VS (wave), S017 (weight), + indicators
    select_cols = ["COUNTRY_ALPHA", "S020", "S002VS", "S017", "S018", *indicators]
    # Quote columns that might clash with reserved words
    quoted_cols = [f'"{c}"' for c in select_cols]

    con = duckdb.connect(":memory:")
    try:
        country_placeholders = ", ".join("?" for _ in sorted(target_countries))
        query = (
            f"SELECT {', '.join(quoted_cols)} "
            "FROM read_csv("
            "?, header=true, delim=',', quote='\"', escape='\"', all_varchar=true, "
            "strict_mode=false, ignore_errors=true, null_padding=true, max_line_size=2000000"
            ") "
            f'WHERE "COUNTRY_ALPHA" IN ({country_placeholders}) '
            'AND try_cast("S020" AS INTEGER) BETWEEN ? AND ?'
        )
        start_year, end_year = year_window
        rows = con.execute(
            query,
            [str(csv_path), *sorted(target_countries), int(start_year), int(end_year)],
        ).fetchall()
    except Exception as exc:
        logger.warning("DuckDB CSV read failed, falling back to per-indicator reader: {}", exc)
        con.close()
        # Fallback to single-indicator reader
        result = {}
        for ind in indicators:
            try:
                result[ind] = _load_wvs_bulk_rows(
                    ind,
                    country_scope=country_scope,
                    year_window=year_window,
                )
            except Exception:
                result[ind] = []
        return result

    con.close()

    # Column index mapping
    col_idx = {name: i for i, name in enumerate(select_cols)}

    # Aggregate per indicator
    aggregates: dict[str, dict[tuple, _WVSObservationAccumulator]] = {ind: {} for ind in indicators}

    for row in rows:
        country_iso3 = str(row[col_idx["COUNTRY_ALPHA"]] or "").strip().upper()
        if country_iso3 not in target_countries:
            continue
        country_code = _normalize_country_code(country_iso3)
        if not country_code:
            continue

        survey_year = row[col_idx["S020"]]
        if survey_year is None:
            continue
        try:
            survey_year = int(survey_year)
        except (ValueError, TypeError):
            continue
        if survey_year < year_window[0] or survey_year > year_window[1]:
            continue

        wave_raw = row[col_idx["S002VS"]]
        wave = int(wave_raw) if wave_raw is not None else None

        # Get weight
        w017 = row[col_idx["S017"]]
        w018 = row[col_idx["S018"]]
        weight_value = None
        weight_field = ""
        if w017 is not None:
            try:
                wv = float(w017)
                if wv > 0:
                    weight_value = wv
                    weight_field = "S017"
            except (ValueError, TypeError):
                pass
        if weight_value is None and w018 is not None:
            try:
                wv = float(w018)
                if wv > 0:
                    weight_value = wv
                    weight_field = "S018"
            except (ValueError, TypeError):
                pass
        if weight_value is None:
            weight_value = 1.0

        key = (country_code, survey_year, wave)

        for ind in indicators:
            raw_val = row[col_idx[ind]]
            value = _normalize_wvs_response_value_typed(ind, raw_val)
            if value is None:
                continue
            bucket = aggregates[ind].setdefault(key, _WVSObservationAccumulator())
            bucket.sample_size += 1
            bucket.weighted_total += weight_value
            bucket.weighted_value += weight_value * value
            if not bucket.weight_field:
                bucket.weight_field = weight_field

    # Build result rows
    result: dict[str, list[dict[str, Any]]] = {}
    for ind in indicators:
        agg_method = _wvs_aggregation_method(ind)
        ind_rows: list[dict[str, Any]] = []
        for (country_code, survey_year, wave), bucket in sorted(aggregates[ind].items()):
            if bucket.sample_size <= 0 or bucket.weighted_total <= 0:
                continue
            ind_rows.append(
                {
                    "country_code": country_code,
                    "survey_year": survey_year,
                    "wave": wave,
                    "value": bucket.weighted_value / bucket.weighted_total,
                    "sample_size": bucket.sample_size,
                    "weighted_sample_size": round(bucket.weighted_total, 6),
                    "sample_weight_field": bucket.weight_field,
                    "aggregation_method": agg_method,
                    "data_shape": "survey_repeated_cross_section",
                    "observation_grain": "country_survey_year_wave",
                }
            )
        result[ind] = ind_rows
    return result


def _normalize_wvs_response_value_typed(indicator: str, raw_value: Any) -> float | None:
    """Normalize a WVS response value using response_type from registry."""
    if raw_value is None:
        return None
    try:
        value = float(raw_value)
    except (ValueError, TypeError):
        return None
    # Universal: skip WVS missing codes (negative values)
    if value < 0:
        return None

    response_type = _wvs_response_type(indicator)

    if response_type == "binary_12":
        iv = int(value)
        if iv not in (1, 2):
            return None
        # For share aggregation: 1 → 1.0 (positive), 2 → 0.0
        return 1.0 if iv == 1 else 0.0

    if response_type == "binary_mentioned":
        if value not in (0.0, 1.0):
            return None
        return value

    if response_type == "likert_4":
        if value < 1 or value > 4:
            return None
        return value

    if response_type == "likert_5":
        if value < 1 or value > 5:
            return None
        return value

    if response_type == "likert_10":
        if value < 1 or value > 10:
            return None
        return value

    # continuous / unknown: any non-negative value
    if value == 0:
        return None
    return value


def _ensure_registry_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_registry_datasets (
            dataset_id    VARCHAR PRIMARY KEY,
            provider      VARCHAR NOT NULL,
            title         VARCHAR NOT NULL,
            coverage_json VARCHAR NOT NULL,
            access_json   VARCHAR NOT NULL,
            update_freq   VARCHAR NOT NULL,
            last_updated  VARCHAR NOT NULL
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_variable_alignments (
            dataset_id     VARCHAR NOT NULL,
            raw_variable   VARCHAR NOT NULL,
            canonical_var  VARCHAR NOT NULL,
            method         VARCHAR NOT NULL,
            confidence     FLOAT NOT NULL,
            evidence       VARCHAR NOT NULL,
            is_proxy       BOOLEAN DEFAULT FALSE,
            proxy_penalty  FLOAT DEFAULT 0.0,
            PRIMARY KEY (dataset_id, raw_variable, canonical_var)
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_alignment_audit (
            audit_id               VARCHAR PRIMARY KEY,
            dataset_id             VARCHAR NOT NULL,
            raw_variable           VARCHAR NOT NULL,
            canonical_variable     VARCHAR,
            method                 VARCHAR NOT NULL,
            raw_confidence         FLOAT,
            calibrated_confidence  FLOAT,
            alternatives_json      VARCHAR DEFAULT '[]',
            resolved_at            VARCHAR,
            reviewed               BOOLEAN DEFAULT FALSE,
            reviewer_override      VARCHAR DEFAULT NULL
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_observations (
            observation_id VARCHAR PRIMARY KEY,
            dataset_id     VARCHAR NOT NULL,
            raw_variable   VARCHAR NOT NULL,
            canonical_var  VARCHAR NOT NULL,
            country_code   VARCHAR NOT NULL,
            year           INTEGER,
            survey_year    INTEGER,
            wave           INTEGER,
            value          DOUBLE,
            condition_json VARCHAR DEFAULT '{}',
            acquisition_method VARCHAR DEFAULT NULL,
            source_watermark VARCHAR DEFAULT NULL,
            dataset_version VARCHAR DEFAULT NULL
        );
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_registry_provider ON ds_registry_datasets(provider)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_va_canonical ON ds_variable_alignments(canonical_var)"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_va_dataset ON ds_variable_alignments(dataset_id)")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_alignment_audit_dataset ON ds_alignment_audit(dataset_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_country_year ON ds_observations(country_code, year)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_dataset_raw "
        "ON ds_observations(dataset_id, raw_variable)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_dedup "
        "ON ds_observations(dataset_id, raw_variable, country_code, year)"
    )
    _ensure_observation_provenance_columns(con)
    _ensure_observation_index_compatibility(con)


def _ensure_observation_provenance_columns(con: duckdb.DuckDBPyConnection) -> None:
    try:
        columns = {
            str(row[1]) for row in con.execute("PRAGMA table_info('ds_observations')").fetchall()
        }
    except Exception:
        return
    for column_name in ("acquisition_method", "source_watermark", "dataset_version"):
        if column_name in columns:
            continue
        con.execute(f"ALTER TABLE ds_observations ADD COLUMN {column_name} VARCHAR DEFAULT NULL")


def _ensure_observation_index_compatibility(con: duckdb.DuckDBPyConnection) -> None:
    try:
        indexes = con.execute(
            "SELECT index_name, is_unique FROM duckdb_indexes() WHERE table_name='ds_observations'"
        ).fetchall()
    except Exception:
        return
    for index_name, is_unique in indexes:
        if str(index_name or "") != "idx_obs_dedup" or not bool(is_unique):
            continue
        con.execute("DROP INDEX IF EXISTS idx_obs_dedup")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_obs_dedup "
            "ON ds_observations(dataset_id, raw_variable, country_code, year)"
        )
        logger.warning(
            "Dropped legacy UNIQUE idx_obs_dedup to preserve condition-aware and multi-canonical observations"
        )
        break


def _load_catalog_transport_datasets(
    con: duckdb.DuckDBPyConnection,
    config: DatasetBatchConfig,
) -> list[CatalogTransportDataset]:
    tables = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }
    if "ds_datasets" not in tables:
        return []

    dataset_columns = {
        str(row[1]) for row in con.execute("PRAGMA table_info('ds_datasets')").fetchall()
    }
    distribution_columns = (
        {str(row[1]) for row in con.execute("PRAGMA table_info('ds_distributions')").fetchall()}
        if "ds_distributions" in tables
        else set()
    )

    def _dataset_expr(column: str, fallback: str) -> str:
        return f"d.{column}" if column in dataset_columns else fallback

    def _distribution_expr(column: str, fallback: str) -> str:
        return f"dist.{column}" if column in distribution_columns else fallback

    if "ds_distributions" not in tables:
        distribution_join = ""
    elif "preferred_distribution_id" in dataset_columns and "id" in distribution_columns:
        distribution_join = (
            "LEFT JOIN ds_distributions AS dist ON dist.id = d.preferred_distribution_id"
        )
    elif "dataset_id" in distribution_columns:
        distribution_join = """
        LEFT JOIN LATERAL (
            SELECT *
            FROM ds_distributions AS src
            WHERE src.dataset_id = d.id
            ORDER BY COALESCE(src.quality_score, 0.0) DESC, src.id
            LIMIT 1
        ) AS dist ON TRUE
        """
    else:
        distribution_join = ""

    if config.promoted_sources:
        source_filter = sorted(set(config.promoted_sources))
    else:
        source_filter = sorted(_TRANSPORT_SOURCES)
    source_specs = {
        str(spec.name or "").strip().lower(): spec for spec in config.load_registry().sources
    }

    placeholders = ", ".join("?" for _ in source_filter)
    query = f"""
        SELECT
            d.id,
            d.source,
            d.title,
            COALESCE(d.description, ''),
            COALESCE(NULLIF({_dataset_expr("source_dataset_id", "''")}, ''), NULLIF(d.dataset_id, ''), d.id),
            COALESCE({_dataset_expr("update_frequency", "''")}, ''),
            COALESCE({_dataset_expr("last_updated", _dataset_expr("updated_at", "CURRENT_DATE::VARCHAR"))}::VARCHAR, CURRENT_DATE::VARCHAR),
            json_object(
                'countries', COALESCE({_dataset_expr("coverage_countries", "[]")}, []),
                'regions', COALESCE({_dataset_expr("coverage_regions", "[]")}, []),
                'time_range',
                    CASE
                        WHEN COALESCE({_dataset_expr("coverage_time_start", _dataset_expr("temporal_start", "''"))}, '') != ''
                             OR COALESCE({_dataset_expr("coverage_time_end", _dataset_expr("temporal_end", "''"))}, '') != ''
                        THEN COALESCE({_dataset_expr("coverage_time_start", _dataset_expr("temporal_start", "''"))}, '')
                             || ':'
                             || COALESCE({_dataset_expr("coverage_time_end", _dataset_expr("temporal_end", "''"))}, '')
                        ELSE ''
                    END,
                'granularity', COALESCE({_dataset_expr("coverage_granularity", "''")}, 'annual')
            ) AS coverage_json,
            json_object(
                'access_type', 'open',
                'api_endpoint', COALESCE({_dataset_expr("access_api_endpoint", "''")}, ''),
                'bulk_download_url', COALESCE({_dataset_expr("access_bulk_download_url", "''")}, ''),
                'license', COALESCE({_dataset_expr("access_license", "d.license")}, d.license, ''),
                'auth_required', COALESCE({_dataset_expr("access_auth_required", "FALSE")}, FALSE)
            ) AS access_json,
            COALESCE({_dataset_expr("execution_tier", "'transport_ready'")}, 'transport_ready'),
            COALESCE(d.variables, []),
            COALESCE(d.keywords, []),
            COALESCE(d.themes, []),
            COALESCE(d.polisyos_metrics, []),
            COALESCE({_distribution_expr("connector_type", "''")}, ''),
            COALESCE({_distribution_expr("profile_id", "''")}, ''),
            COALESCE(NULLIF({_distribution_expr("source_locator", "''")}, ''), COALESCE(NULLIF({_dataset_expr("source_dataset_id", "''")}, ''), NULLIF(d.dataset_id, ''), d.id)),
            COALESCE(CAST({_distribution_expr("default_filters", "'{}'::JSON")} AS VARCHAR), '{{}}')
        FROM ds_datasets AS d
        {distribution_join}
        WHERE d.source IN ({placeholders})
    """
    rows = con.execute(query, source_filter).fetchall()
    if not rows:
        return []

    out: list[CatalogTransportDataset] = []
    for row in rows:
        source = str(row[1] or "")
        source_spec = source_specs.get(source.lower())
        execution_tier = str(
            row[9] or (source_spec.execution_tier if source_spec is not None else "transport_ready")
        )
        if execution_tier == "catalog" and source not in {"who", "unpd", "unesco_uis"}:
            continue
        coverage_json = str(row[7] or "{}")
        request_dataset_id = str(row[16] or "")
        connector_id = str(row[14] or "") or (
            str(source_spec.connector_id or "") if source_spec is not None else ""
        )
        profile_id = str(row[15] or "") or (
            str(source_spec.profile_id or "") if source_spec is not None else ""
        )
        out.append(
            CatalogTransportDataset(
                catalog_dataset_id=str(row[0]),
                source=source,
                title=str(row[2] or ""),
                description=str(row[3] or ""),
                source_dataset_id=str(row[4] or ""),
                update_frequency=_resolve_catalog_update_frequency(
                    source=source,
                    request_dataset_id=request_dataset_id,
                    title=str(row[2] or ""),
                    update_frequency=str(row[5] or ""),
                    coverage_json=coverage_json,
                ),
                last_updated=str(row[6] or ""),
                coverage_json=coverage_json,
                access_json=str(row[8] or "{}"),
                execution_tier=execution_tier,
                variables=tuple(str(value) for value in list(row[10] or [])),
                keywords=tuple(str(value) for value in list(row[11] or [])),
                themes=tuple(str(value) for value in list(row[12] or [])),
                polisyos_metrics=tuple(str(value) for value in list(row[13] or [])),
                connector_id=connector_id,
                profile_id=profile_id,
                request_dataset_id=request_dataset_id,
                default_filters=_load_json_dict(row[17]),
            )
        )
    return out


def _resolve_catalog_update_frequency(
    *,
    source: str,
    request_dataset_id: str,
    title: str,
    update_frequency: str,
    coverage_json: str,
) -> str:
    normalized_source = str(source or "").strip().lower()
    normalized_frequency = str(update_frequency or "").strip().lower()
    coverage = _load_json_dict(coverage_json)
    coverage_granularity = str(coverage.get("granularity") or "").strip().lower()
    if not normalized_frequency:
        if coverage_granularity in {
            "annual",
            "quarterly",
            "monthly",
            "weekly",
            "daily",
            "wave",
            "irregular",
        }:
            return coverage_granularity
        return ""
    if normalized_source != "eurostat" or normalized_frequency not in {"monthly", "quarterly"}:
        return normalized_frequency
    if _eurostat_request_id_suggests_subannual(request_dataset_id):
        return normalized_frequency
    lowered_title = str(title or "").strip().lower()
    if any(token in lowered_title for token in _EUROSTAT_SUBANNUAL_TITLE_TOKENS):
        return normalized_frequency
    if coverage_granularity in {"annual", "country-year", "yearly"}:
        return "annual"
    return normalized_frequency


def _eurostat_request_id_suggests_subannual(request_dataset_id: str) -> bool:
    normalized = str(request_dataset_id or "").strip().upper()
    if not normalized:
        return False
    if re.search(r"(^|[_$-])[MQ](\d+)?($|[_$-])", normalized):
        return True
    return len(normalized) >= 4 and normalized.endswith(("M", "Q"))


def _upsert_catalog_registry_datasets(
    con: duckdb.DuckDBPyConnection,
    datasets: list[CatalogTransportDataset],
) -> int:
    rows = [
        (
            item.catalog_dataset_id,
            item.source,
            item.title,
            item.coverage_json,
            item.access_json,
            item.update_frequency or "annual",
            item.last_updated or datetime.now(UTC).date().isoformat(),
        )
        for item in datasets
    ]
    if not rows:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO ds_registry_datasets "
        "(dataset_id, provider, title, coverage_json, access_json, update_freq, last_updated) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _build_catalog_alignments(
    datasets: list[CatalogTransportDataset],
    seed_path: Path,
) -> list[VariableAlignment]:
    seed_alignments = load_seed_alignments(seed_path)
    seed_by_var: dict[str, list[VariableAlignment]] = {}
    for item in seed_alignments:
        seed_by_var.setdefault(item.dataset_var.strip().upper(), []).append(item)

    best: dict[tuple[str, str, str], VariableAlignment] = {}
    for dataset in datasets:
        candidate_vars = _candidate_variables(dataset)
        dataset_text_tokens = _tokenize(
            " ".join((dataset.title, dataset.description, *candidate_vars, *dataset.keywords))
        )

        for raw_var in candidate_vars:
            for seed in seed_by_var.get(raw_var.strip().upper(), []):
                _remember_alignment(
                    best,
                    VariableAlignment(
                        canonical_var=seed.canonical_var,
                        dataset_var=raw_var,
                        dataset_id=dataset.catalog_dataset_id,
                        method=seed.method,
                        confidence=seed.confidence,
                        evidence=f"{seed.evidence};source={dataset.source}",
                        is_proxy=seed.is_proxy,
                        proxy_penalty=seed.proxy_penalty,
                    ),
                )

        for metric in dataset.polisyos_metrics:
            if metric in _CANONICAL_ROOTS:
                raw_var = dataset.source_dataset_id or (
                    candidate_vars[0] if candidate_vars else metric
                )
                _remember_alignment(
                    best,
                    VariableAlignment(
                        canonical_var=metric,
                        dataset_var=raw_var,
                        dataset_id=dataset.catalog_dataset_id,
                        method=AlignmentMethod.EXACT,
                        confidence=0.98,
                        evidence="metric_binding_direct_to_canonical_root",
                    ),
                )
            for proxy_alignment in metric_proxy_alignments(metric):
                raw_var = dataset.source_dataset_id or (
                    candidate_vars[0] if candidate_vars else metric
                )
                _remember_alignment(
                    best,
                    VariableAlignment(
                        canonical_var=proxy_alignment.canonical_var,
                        dataset_var=raw_var,
                        dataset_id=dataset.catalog_dataset_id,
                        method=AlignmentMethod.SEMANTIC,
                        confidence=proxy_alignment.confidence,
                        evidence=f"metric_binding_proxy:{metric}",
                        is_proxy=True,
                        proxy_penalty=proxy_alignment.proxy_penalty,
                    ),
                )

        semantic_candidates = [
            canonical_var
            for canonical_var in _CANONICAL_ROOTS
            if _tokenize(canonical_var.replace("_", " ")) & dataset_text_tokens
        ]
        if dataset.source in {
            "worldbank",
            "eurostat",
            "oecd",
            "ilo",
            "who",
            "unpd",
            "wvs",
            "unesco_uis",
        }:
            semantic_candidates.extend(
                metric for metric in dataset.polisyos_metrics if metric in _CANONICAL_ROOTS
            )
        semantic_candidates = sorted(set(semantic_candidates))[:20]
        for canonical_var in semantic_candidates:
            for alignment in align_semantic(
                canonical_var=canonical_var,
                dataset_id=dataset.catalog_dataset_id,
                candidates=candidate_vars,
                threshold=0.45,
                max_results=3,
            ):
                if alignment.confidence < 0.55:
                    continue
                _remember_alignment(best, alignment)

    return list(best.values())


def _candidate_variables(dataset: CatalogTransportDataset) -> list[str]:
    values: list[str] = []
    for item in (dataset.source_dataset_id, *dataset.variables):
        text = str(item or "").strip()
        if text and text not in values:
            values.append(text)
    if not values and dataset.polisyos_metrics:
        values.extend(metric for metric in dataset.polisyos_metrics if metric)
    return values or [dataset.catalog_dataset_id]


def _remember_alignment(
    best: dict[tuple[str, str, str], VariableAlignment],
    alignment: VariableAlignment,
) -> None:
    key = (alignment.dataset_id, alignment.dataset_var, alignment.canonical_var)
    current = best.get(key)
    method_rank = {
        AlignmentMethod.EXACT: 0,
        AlignmentMethod.META_ANALYTIC: 1,
        AlignmentMethod.SEMANTIC: 2,
    }
    if current is None:
        best[key] = alignment
        return
    candidate_rank = method_rank.get(alignment.method, 9)
    current_rank = method_rank.get(current.method, 9)
    if candidate_rank < current_rank or (
        candidate_rank == current_rank and alignment.confidence > current.confidence
    ):
        best[key] = alignment


def _upsert_catalog_alignments(
    con: duckdb.DuckDBPyConnection,
    alignments: list[VariableAlignment],
) -> int:
    rows = [
        (
            item.dataset_id,
            item.dataset_var,
            item.canonical_var,
            item.method.value,
            item.confidence,
            item.evidence,
            item.is_proxy,
            item.proxy_penalty,
        )
        for item in alignments
    ]
    if not rows:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO ds_variable_alignments "
        "(dataset_id, raw_variable, canonical_var, method, confidence, "
        "evidence, is_proxy, proxy_penalty) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _upsert_alignment_audit(
    con: duckdb.DuckDBPyConnection,
    alignments: list[VariableAlignment],
) -> int:
    rows = _build_alignment_audit_rows(alignments)
    if not rows:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO ds_alignment_audit "
        "(audit_id, dataset_id, raw_variable, canonical_variable, method, raw_confidence, "
        "calibrated_confidence, alternatives_json, resolved_at, reviewed, reviewer_override) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _build_alignment_audit_rows(
    alignments: list[VariableAlignment],
) -> list[tuple[object, ...]]:
    grouped: dict[tuple[str, str], list[VariableAlignment]] = {}
    for alignment in alignments:
        grouped.setdefault((alignment.dataset_id, alignment.dataset_var), []).append(alignment)

    resolved_at = datetime.now(UTC).isoformat()
    rows: list[tuple[object, ...]] = []
    for candidates in grouped.values():
        ranked = sorted(
            candidates,
            key=lambda item: (
                -calibrate_alignment_confidence(item),
                -float(item.confidence),
                item.canonical_var,
            ),
        )
        for alignment in ranked:
            alternatives = [
                {
                    "canonical_variable": candidate.canonical_var,
                    "method": candidate.method.value,
                    "raw_confidence": float(candidate.confidence),
                    "calibrated_confidence": calibrate_alignment_confidence(candidate),
                }
                for candidate in ranked
                if candidate.canonical_var != alignment.canonical_var
            ][:3]
            audit_id = hashlib.sha256(
                f"{alignment.dataset_id}|{alignment.dataset_var}|{alignment.canonical_var}".encode()
            ).hexdigest()[:24]
            rows.append(
                (
                    audit_id,
                    alignment.dataset_id,
                    alignment.dataset_var,
                    alignment.canonical_var,
                    alignment.method.value,
                    float(alignment.confidence),
                    calibrate_alignment_confidence(alignment),
                    json.dumps(alternatives, ensure_ascii=False),
                    resolved_at,
                    False,
                    None,
                )
            )
    return rows


def _build_catalog_observation_plans(
    datasets: list[CatalogTransportDataset],
    alignments: list[VariableAlignment],
    *,
    config: DatasetBatchConfig,
) -> list[ObservationPlan]:
    by_dataset = {item.catalog_dataset_id: item for item in datasets}
    plans: list[ObservationPlan] = []
    seen: set[tuple[str, str, str]] = set()
    preflight_sources = {item.strip().lower() for item in config.preflight_sources if item.strip()}
    for alignment in alignments:
        dataset = by_dataset.get(alignment.dataset_id)
        if dataset is None:
            continue
        if dataset.source not in _TRANSPORT_SOURCES:
            continue
        if preflight_sources and dataset.source.lower() not in preflight_sources:
            continue
        if not _supports_observation_ingest(dataset, alignment):
            continue
        if alignment.confidence < 0.55:
            continue
        request_dataset_id = (
            dataset.request_dataset_id or dataset.source_dataset_id or alignment.dataset_var
        )
        if not request_dataset_id:
            continue
        key = (dataset.catalog_dataset_id, alignment.dataset_var, alignment.canonical_var)
        if key in seen:
            continue
        seen.add(key)
        plans.append(
            ObservationPlan(
                dataset_id=dataset.catalog_dataset_id,
                source=dataset.source,
                raw_variable=alignment.dataset_var,
                canonical_var=alignment.canonical_var,
                connector_id=dataset.connector_id,
                profile_id=dataset.profile_id,
                request_dataset_id=request_dataset_id,
                default_filters=dataset.default_filters,
                update_frequency=dataset.update_frequency or "annual",
                source_watermark=dataset.last_updated or "",
                dataset_version=request_dataset_id,
            )
        )
    return _limit_observation_plans(plans, datasets, config=config)


def _supports_observation_ingest(
    dataset: CatalogTransportDataset,
    alignment: VariableAlignment,
) -> bool:
    source = str(dataset.source or "").strip().lower()
    if source != "worldbank":
        return True
    if dataset.connector_id and dataset.connector_id != "worldbank.wdi":
        return False
    if dataset.profile_id and dataset.profile_id != "worldbank_wdi":
        return False
    if dataset.polisyos_metrics:
        return True
    return alignment.method in {AlignmentMethod.EXACT, AlignmentMethod.META_ANALYTIC}


def _observation_plan_limit_per_source(config: DatasetBatchConfig) -> int | None:
    if config.preflight_only or config.run_profile == "preflight_core":
        return 2
    if not config.is_sampled_run:
        return None
    base = max(int(config.max_datasets_per_source), 1)
    return max(base, min(base + 2, 6))


def _observation_failure_budget_per_source(config: DatasetBatchConfig) -> int | None:
    if config.is_sampled_run:
        capped = _observation_plan_limit_per_source(config) or 1
        return max(2, min(capped, 4))
    return None


# High-coverage indicators known to have broad country/year data.
# Used to prioritise preflight plan selection so we pick indicators
# that will actually return rows, instead of sorting by hashed dataset_id
# (which is effectively random and caused WHO preflight failures).
_PREFLIGHT_HIGH_COVERAGE_INDICATORS: dict[str, frozenset[str]] = {
    "who": frozenset(
        {
            "WHOSIS_000001",  # Life expectancy at birth
            "WHOSIS_000002",  # Healthy life expectancy (HALE)
            "MDG_0000000001",  # Under-five mortality rate
            "NCD_BMI_30A",  # Prevalence of obesity
            "SA_0000001688",  # Total alcohol per capita consumption
            "WHS7_104",  # Infant mortality rate
            "WHS9_95",  # Maternal mortality ratio
            "NCD_CCS_Diab",  # Diabetes prevalence
        }
    ),
    "unesco_uis": frozenset(
        {
            "CR.1",  # Completion rate, primary
            "SE.ADT.LITR.ZS",  # Adult literacy rate
            "UIS.NERA.1",  # Net enrolment rate, primary
        }
    ),
    "wvs": frozenset(
        {
            "A165",  # Social trust (most people can be trusted)
            "E069_17",  # Confidence: Justice System/Courts
            "A009",  # State of health (subjective)
            "E117",  # Having a democratic political system
            "E035",  # Income equality
            "Y022",  # Welzel equality sub-index
        }
    ),
    "worldbank": frozenset(
        {
            "NY.GDP.PCAP.CD",  # GDP per capita
            "SP.DYN.LE00.IN",  # Life expectancy at birth
            "SE.ADT.LITR.ZS",  # Adult literacy rate
            "SL.UEM.TOTL.ZS",  # Unemployment total
            "SI.POV.GINI",  # GINI index
            "SH.XPD.CHEX.GD.ZS",  # Health expenditure (% of GDP)
        }
    ),
}


def _preflight_indicator_priority(plan: ObservationPlan) -> int:
    """Return 0 for known high-coverage indicators, 1 otherwise."""
    high_coverage = _PREFLIGHT_HIGH_COVERAGE_INDICATORS.get(plan.source)
    if high_coverage and plan.request_dataset_id in high_coverage:
        return 0
    return 1


def _limit_observation_plans(
    plans: list[ObservationPlan],
    datasets: list[CatalogTransportDataset],
    *,
    config: DatasetBatchConfig,
) -> list[ObservationPlan]:
    if not plans:
        return []

    limit = _observation_plan_limit_per_source(config)
    dataset_rank = {
        item.catalog_dataset_id: (
            0 if item.execution_tier == "transport_ready" else 1,
            0 if item.polisyos_metrics else 1,
            item.catalog_dataset_id,
        )
        for item in datasets
    }
    ordered = sorted(
        plans,
        key=lambda item: (
            item.source,
            _preflight_indicator_priority(item),
            dataset_rank.get(item.dataset_id, (9, 9, item.dataset_id)),
            _observation_frequency_rank(item.update_frequency),
            item.canonical_var,
            item.raw_variable,
        ),
    )
    if limit is None:
        return ordered

    grouped: dict[str, list[ObservationPlan]] = {}
    for plan in ordered:
        grouped.setdefault(plan.source, []).append(plan)

    # Collect canonical vars that are important for transport benchmark.
    # Prioritise plans that cover canonical vars not yet covered by other sources.
    _TRANSPORT_BENCHMARK_VARS: frozenset[str] = frozenset(
        {
            "gdp_per_capita",
            "unemployment_rate",
            "inflation",
            "migration",
            "health_outcomes",
            "education_outcomes",
            "social_trust",
            "poverty_rate",
            "labor_force_participation",
            "institutional_quality",
        }
    )
    covered_transport_vars: set[str] = set()

    out: list[ObservationPlan] = []
    trimmed = 0
    for _source, source_plans in grouped.items():
        selected: list[ObservationPlan] = []
        seen_keys: set[tuple[str, str, str]] = set()
        seen_canonical: set[str] = set()

        # First pass: prefer plans covering uncovered transport vars.
        transport_first = sorted(
            source_plans,
            key=lambda p: (
                0
                if (
                    p.canonical_var in _TRANSPORT_BENCHMARK_VARS
                    and p.canonical_var not in covered_transport_vars
                )
                else 1,
                _preflight_indicator_priority(p),
                p.canonical_var,
            ),
        )
        for plan in transport_first:
            if plan.canonical_var in seen_canonical:
                continue
            selected.append(plan)
            seen_canonical.add(plan.canonical_var)
            seen_keys.add((plan.dataset_id, plan.raw_variable, plan.canonical_var))
            if len(selected) >= limit:
                break

        if len(selected) < limit:
            for plan in source_plans:
                key = (plan.dataset_id, plan.raw_variable, plan.canonical_var)
                if key in seen_keys:
                    continue
                selected.append(plan)
                seen_keys.add(key)
                if len(selected) >= limit:
                    break

        for plan in selected:
            covered_transport_vars.add(plan.canonical_var)
        out.extend(selected)
        trimmed += max(len(source_plans) - len(selected), 0)
    if trimmed:
        logger.info(
            "Trimmed observation plans for sampled run: kept {} of {} plans (per-source limit={})",
            len(out),
            len(ordered),
            limit,
        )
    return out


def _observation_mode_phases(config: DatasetBatchConfig) -> tuple[str, ...]:
    mode = str(getattr(config, "observation_mode", "all") or "all").strip().lower()
    if mode == "core":
        return ("publishable_core",)
    if mode == "backfill":
        return ("long_tail_backfill",)
    return ("publishable_core", "long_tail_backfill")


def _source_runtime_lane_count(
    *,
    source: str,
    policy: SourceExecutionPolicy,
) -> int:
    configured = max(1, _policy_int_attr(policy, "max_concurrency", 1))
    preferred = _SOURCE_LANE_DEFAULTS.get(str(source or "").strip().lower())
    if preferred is None:
        return configured
    return max(1, min(configured, int(preferred)))


def _recommended_transport_for_plan(
    plan: ObservationPlan,
    *,
    phase: str,
    policy: SourceExecutionPolicy,
    capability: DatasetCapabilitySnapshot | None,
    config: DatasetBatchConfig,
) -> str:
    source = str(plan.source or "").strip().lower()
    preferred_transport = (
        _policy_attr(policy, "preferred_core_transport", None)
        if phase == "publishable_core"
        else _policy_attr(policy, "preferred_backfill_transport", None)
    ) or _policy_str_attr(policy, "preferred_transport", "default")
    if source == "wvs":
        return "local_bulk_file"
    if source == "worldbank":
        return str(preferred_transport or "api_grouped")
    if source == "who":
        return str(preferred_transport or "api_grouped")
    if source == "unesco_uis":
        if phase == "long_tail_backfill" and _policy_attr(policy, "bulk_download_url", None):
            return "bulk_file"
        return str(preferred_transport or "api_grouped")
    if source == "unpd":
        return str(preferred_transport or "api_grouped")
    if source in {"oecd", "ilo"}:
        if (
            source == "ilo"
            and phase == "long_tail_backfill"
            and _policy_attr(policy, "bulk_download_url", None)
        ):
            return "bulk_file"
        return str(preferred_transport or "api_grouped")
    if source == "eurostat":
        if phase == "long_tail_backfill" and _policy_attr(policy, "bulk_download_url", None):
            return "bulk_file"
        if _shard_prefers_async_fetch(
            ObservationShard(
                shard_id="transport_probe",
                plan=plan,
                country_code=None,
                country_codes=_observation_countries(source, config=config),
                start_year=config.resolved_year_window[0],
                end_year=config.resolved_year_window[1],
                filters=dict(plan.default_filters),
            ),
            snapshot=capability,
            policy=policy,
            config=config,
        ):
            return "api_async"
        if (
            _policy_bool_attr(policy, "supports_async_fetch", False)
            and source == "eurostat"
            and not config.is_sampled_run
        ):
            return str(preferred_transport or "api_sync")
    return str(
        (
            capability.preferred_transport
            if capability is not None and getattr(capability, "preferred_transport", None)
            else preferred_transport
        )
        or "default"
    )


def _transport_for_phase(sketch: SupportSketch, *, phase: str) -> str:
    if phase == "long_tail_backfill":
        return str(
            sketch.recommended_backfill_transport or sketch.recommended_core_transport or "default"
        )
    return str(
        sketch.recommended_core_transport or sketch.recommended_backfill_transport or "default"
    )


def _country_supported_by_capability(country_code: str, allowed_values: tuple[str, ...]) -> bool:
    if not allowed_values:
        return True
    iso2 = str(country_code or "").strip().upper()
    iso3 = _to_iso3(iso2)
    numeric = iso2_to_numeric(iso2) or ""
    allowed = {str(value).strip().upper() for value in allowed_values if str(value).strip()}
    return iso2 in allowed or iso3 in allowed or numeric in allowed


def _supported_countries_for_plan(
    plan: ObservationPlan,
    *,
    config: DatasetBatchConfig,
    capability: DatasetCapabilitySnapshot | None,
) -> tuple[str, ...]:
    countries = _observation_countries(plan.source, config=config)
    allowed = _capability_dimension_values(capability, "geo", "country", "ref_area")
    if not allowed:
        return countries
    return tuple(
        country for country in countries if _country_supported_by_capability(country, allowed)
    )


def _support_time_range_for_plan(
    plan: ObservationPlan,
    *,
    config: DatasetBatchConfig,
) -> tuple[int, int]:
    if plan.source == "wvs":
        return (1981, 2023)
    return config.resolved_year_window


def _build_support_sketches(
    plans: list[ObservationPlan],
    *,
    config: DatasetBatchConfig,
    plan_capabilities: dict[str, DatasetCapabilitySnapshot | None],
    source_policies: dict[str, SourceExecutionPolicy],
) -> dict[str, SupportSketch]:
    sketches: dict[str, SupportSketch] = {}
    for plan in plans:
        capability = plan_capabilities.get(_capability_snapshot_cache_key(plan))
        policy = source_policies[plan.source]
        time_range = _support_time_range_for_plan(plan, config=config)
        estimated_cardinality = (
            int(capability.estimated_cardinality or 0) if capability is not None else 0
        )
        allowed_dimension_values = (
            {
                str(key): tuple(str(value) for value in values if str(value).strip())
                for key, values in dict(capability.allowed_positions or {}).items()
            }
            if capability is not None and capability.allowed_positions
            else {}
        )
        recommended_core_transport = _recommended_transport_for_plan(
            plan,
            phase="publishable_core",
            policy=policy,
            capability=capability,
            config=config,
        )
        recommended_backfill_transport = _recommended_transport_for_plan(
            plan,
            phase="long_tail_backfill",
            policy=policy,
            capability=capability,
            config=config,
        )
        sketches[_support_sketch_id(plan)] = SupportSketch(
            sketch_id=_support_sketch_id(plan),
            plan=plan,
            dataset_version=str(
                (
                    capability.version_hint
                    if capability is not None and getattr(capability, "version_hint", None)
                    else plan.dataset_version or plan.request_dataset_id
                )
                or plan.request_dataset_id
            ),
            supported_countries=_supported_countries_for_plan(
                plan, config=config, capability=capability
            ),
            time_range=time_range,
            allowed_dimension_values=allowed_dimension_values,
            estimated_cardinality=estimated_cardinality,
            source_watermark=str(plan.source_watermark or ""),
            recommended_core_transport=recommended_core_transport,
            recommended_backfill_transport=recommended_backfill_transport,
            dimension_order=_normalize_dimension_order(
                capability.dimension_order if capability is not None else ()
            )
            or _infer_dimension_order_for_plan(plan),
        )
    return sketches


def _country_groups_for_sketch(
    sketch: SupportSketch,
    *,
    policy: SourceExecutionPolicy,
    phase: str,
) -> tuple[tuple[str, ...], ...]:
    countries = sketch.supported_countries
    if not countries:
        return ((),)
    source = str(sketch.plan.source or "").strip().lower()
    configured_group_limit = (
        _policy_optional_int_attr(policy, "core_group_limit")
        if phase == "publishable_core"
        else _policy_optional_int_attr(policy, "backfill_group_limit")
    )
    if configured_group_limit is not None:
        group_size = max(1, int(configured_group_limit))
    elif source == "unpd":
        group_size = 25
    elif source == "worldbank":
        span_years = max(int(sketch.time_range[1]) - int(sketch.time_range[0]) + 1, 1)
        max_points = _policy_int_attr(policy, "max_sync_cells", 15_000)
        group_size = max(1, max_points // span_years)
    else:
        group_size = len(countries)
    if group_size >= len(countries):
        return (tuple(countries),)
    groups: list[tuple[str, ...]] = []
    for start in range(0, len(countries), group_size):
        groups.append(tuple(countries[start : start + group_size]))
    return tuple(groups)


def _phase_windows_for_sketch(
    sketch: SupportSketch,
    *,
    config: DatasetBatchConfig,
) -> list[tuple[int, int, str]]:
    start_year, end_year = sketch.time_range
    if sketch.plan.source == "wvs":
        return [(1981, 2023, "publishable_core")]
    if config.preflight_only or config.run_profile == "preflight_core" or config.is_sampled_run:
        return [(start_year, end_year, "publishable_core")]
    if sketch.plan.source in {"eurostat", "oecd", "ilo", "unesco_uis"}:
        windows = _year_windows(
            start_year,
            end_year,
            _observation_time_window_years(
                source=sketch.plan.source,
                update_frequency=sketch.plan.update_frequency,
            ),
        )
        if len(windows) <= 1:
            return [
                (window_start, window_end, "publishable_core")
                for window_start, window_end in windows
            ]
        phased: list[tuple[int, int, str]] = []
        for index, (window_start, window_end) in enumerate(windows):
            phase = "publishable_core" if index == len(windows) - 1 else "long_tail_backfill"
            phased.append((window_start, window_end, phase))
        return phased
    return [(start_year, end_year, "publishable_core")]


def _build_observation_shards_from_sketches(
    sketches: dict[str, SupportSketch],
    *,
    config: DatasetBatchConfig,
    source_policies: dict[str, SourceExecutionPolicy],
) -> list[ObservationShard]:
    shards: list[ObservationShard] = []
    for sketch in sketches.values():
        plan = sketch.plan
        policy = source_policies[plan.source]
        for shard_start, shard_end, phase in _phase_windows_for_sketch(sketch, config=config):
            country_groups = _country_groups_for_sketch(
                sketch,
                policy=policy,
                phase=phase,
            )
            for group in country_groups:
                filters = dict(plan.default_filters)
                if group:
                    if plan.source == "eurostat":
                        filters = _eurostat_filters_for_countries(group, base_filters=filters)
                    elif plan.source in {"oecd", "ilo"}:
                        filters = _sdmx_filters_for_countries(group, base_filters=filters)
                country_code = group[0] if len(group) == 1 else None
                shards.append(
                    ObservationShard(
                        shard_id=_observation_shard_id(
                            plan=plan,
                            country_code=country_code,
                            country_codes=group,
                            start_year=shard_start,
                            end_year=shard_end,
                            filters=filters,
                            split_depth=0,
                        ),
                        plan=plan,
                        country_code=country_code,
                        country_codes=group,
                        start_year=shard_start,
                        end_year=shard_end,
                        filters=filters,
                        split_depth=0,
                        phase=phase,
                        acquisition_method=_transport_for_phase(sketch, phase=phase),
                        source_watermark=sketch.source_watermark,
                        dataset_version=sketch.dataset_version,
                        dimension_order=sketch.dimension_order,
                    )
                )
    return shards


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


def _chunked_observation_requests(
    *,
    plan: ObservationPlan,
    filters: tuple[tuple[str, tuple[str, ...]], ...],
    source: str,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[FetchRequest]:
    window_start = start_year if start_year is not None else _DEFAULT_OBSERVATION_YEAR_WINDOW[0]
    window_end = end_year if end_year is not None else _DEFAULT_OBSERVATION_YEAR_WINDOW[1]
    window_years = _observation_time_window_years(
        source=source, update_frequency=plan.update_frequency
    )
    requests: list[FetchRequest] = []
    for window_start, window_end in _year_windows(window_start, window_end, window_years):
        requests.append(
            FetchRequest(
                dataset_id=plan.request_dataset_id,
                filters=filters,
                date_start=datetime(window_start, 1, 1, tzinfo=UTC),
                date_end=datetime(window_end, 12, 31, tzinfo=UTC),
                page_size=200,
            )
        )
    return requests


def _observation_time_window_years(*, source: str, update_frequency: str) -> int:
    normalized = str(source or "").strip().lower()
    if normalized != "eurostat":
        start_year, end_year = _DEFAULT_OBSERVATION_YEAR_WINDOW
        return max((end_year - start_year) + 1, 1)
    frequency_rank = _observation_frequency_rank(update_frequency)
    if frequency_rank >= 1:
        return 1
    return 2


def _year_windows(start_year: int, end_year: int, window_years: int) -> list[tuple[int, int]]:
    if end_year < start_year:
        return []
    width = max(int(window_years), 1)
    windows: list[tuple[int, int]] = []
    current = int(start_year)
    while current <= int(end_year):
        upper = min(current + width - 1, int(end_year))
        windows.append((current, upper))
        current = upper + 1
    return windows


def _build_observation_shards(
    plans: list[ObservationPlan],
    *,
    config: DatasetBatchConfig,
) -> list[ObservationShard]:
    source_policies = {
        plan.source: _resolve_source_execution_policy(
            source=plan.source, profile_id=plan.profile_id
        )
        for plan in plans
    }
    sketches = _build_support_sketches(
        plans,
        config=config,
        plan_capabilities={},
        source_policies=source_policies,
    )
    return _build_observation_shards_from_sketches(
        sketches,
        config=config,
        source_policies=source_policies,
    )


def _observation_shard_id(
    *,
    plan: ObservationPlan,
    country_code: str | None,
    country_codes: tuple[str, ...] = (),
    start_year: int,
    end_year: int,
    filters: dict[str, list[str]],
    split_depth: int,
) -> str:
    payload = {
        "dataset_id": plan.dataset_id,
        "source": plan.source,
        "raw_variable": plan.raw_variable,
        "canonical_var": plan.canonical_var,
        "request_dataset_id": plan.request_dataset_id,
        "country_code": country_code,
        "country_codes": list(country_codes),
        "start_year": start_year,
        "end_year": end_year,
        "filters": filters,
        "split_depth": split_depth,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _split_shard_for_retry(shard: ObservationShard, exc: Exception) -> list[ObservationShard]:
    lowered = str(exc or "").lower()
    if "http 413" not in lowered and "payload" not in lowered:
        return []
    if shard.start_year < shard.end_year:
        mid = (shard.start_year + shard.end_year) // 2
        windows = ((shard.start_year, mid), (mid + 1, shard.end_year))
        return [
            ObservationShard(
                shard_id=_observation_shard_id(
                    plan=shard.plan,
                    country_code=shard.country_code,
                    country_codes=shard.country_codes,
                    start_year=window_start,
                    end_year=window_end,
                    filters=shard.filters,
                    split_depth=shard.split_depth + 1,
                ),
                plan=shard.plan,
                country_code=shard.country_code,
                country_codes=shard.country_codes,
                start_year=window_start,
                end_year=window_end,
                filters=dict(shard.filters),
                split_depth=shard.split_depth + 1,
                phase=shard.phase,
                acquisition_method=shard.acquisition_method,
                source_watermark=shard.source_watermark,
                dataset_version=shard.dataset_version,
                dimension_order=shard.dimension_order,
            )
            for window_start, window_end in windows
            if window_start <= window_end
        ]
    split_key = _largest_filter_key(shard.filters)
    if not split_key:
        return []
    values = list(shard.filters.get(split_key, ()))
    if len(values) <= 1:
        return []
    midpoint = max(len(values) // 2, 1)
    left = dict(shard.filters)
    right = dict(shard.filters)
    left[split_key] = values[:midpoint]
    right[split_key] = values[midpoint:]
    return [
        ObservationShard(
            shard_id=_observation_shard_id(
                plan=shard.plan,
                country_code=shard.country_code,
                country_codes=shard.country_codes,
                start_year=shard.start_year,
                end_year=shard.end_year,
                filters=current_filters,
                split_depth=shard.split_depth + 1,
            ),
            plan=shard.plan,
            country_code=shard.country_code,
            country_codes=shard.country_codes,
            start_year=shard.start_year,
            end_year=shard.end_year,
            filters=current_filters,
            split_depth=shard.split_depth + 1,
            phase=shard.phase,
            acquisition_method=shard.acquisition_method,
            source_watermark=shard.source_watermark,
            dataset_version=shard.dataset_version,
            dimension_order=shard.dimension_order,
        )
        for current_filters in (left, right)
        if current_filters.get(split_key)
    ]


async def _split_shard_for_retry_async(
    shard: ObservationShard,
    exc: Exception,
    *,
    cache: _ConnectorSessionCache,
    config: DatasetBatchConfig,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    budget_wait_observer: Any | None = None,
) -> list[ObservationShard]:
    status_code = _planner_error_status_code(exc)
    if (
        shard.plan.source == "eurostat"
        and status_code in {405, 413}
        and not (
            config.is_sampled_run or config.preflight_only or config.run_profile == "preflight_core"
        )
    ):
        current_transport = str(shard.acquisition_method or "").strip().lower()
        next_transport = ""
        if (
            status_code == 413
            and current_transport != "api_async"
            and _policy_bool_attr(policy, "supports_async_fetch", False)
        ):
            next_transport = "api_async"
        elif current_transport == "api_async" and _policy_attr(policy, "bulk_download_url", None):
            next_transport = "bulk_file"
        if next_transport:
            return [
                ObservationShard(
                    shard_id=shard.shard_id,
                    plan=shard.plan,
                    country_code=shard.country_code,
                    country_codes=shard.country_codes,
                    start_year=shard.start_year,
                    end_year=shard.end_year,
                    filters=dict(shard.filters),
                    split_depth=shard.split_depth,
                    phase=shard.phase,
                    acquisition_method=next_transport,
                    source_watermark=shard.source_watermark,
                    dataset_version=shard.dataset_version,
                    dimension_order=shard.dimension_order,
                )
            ]
    split_shards = _split_shard_for_retry(shard, exc)
    if split_shards:
        return split_shards
    if _planner_error_status_code(exc) != 413 or not policy.schema_preflight:
        return []
    return await _probe_shard_split_dimensions(
        shard,
        cache=cache,
        config=config,
        policy=policy,
        budget_windows=budget_windows,
        state_lock=state_lock,
        budget_wait_observer=budget_wait_observer,
    )


async def _probe_shard_split_dimensions(
    shard: ObservationShard,
    *,
    cache: _ConnectorSessionCache,
    config: DatasetBatchConfig,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    budget_wait_observer: Any | None = None,
) -> list[ObservationShard]:
    request = _build_probe_request(shard)
    if request is None:
        return []
    try:
        if shard.plan.source == "eurostat":
            connector, handle = await cache.get_eurostat()
        elif shard.plan.source in {"oecd", "ilo"}:
            profile_id = shard.plan.profile_id or (
                "oecd_sdmx" if shard.plan.source == "oecd" else "ilo_sdmx"
            )
            connector, handle = await cache.get_sdmx(profile_id)
        else:
            return []
        result = await _execute_source_fetch(
            connector,
            handle,
            request,
            source=shard.plan.source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            budget_wait_observer=budget_wait_observer,
        )
    except Exception:
        return []
    rows = _records_from_payload(result.data)
    split_key, values = _probe_dimension_split_key(rows, shard=shard)
    if not split_key or len(values) <= 1:
        return []
    midpoint = max(len(values) // 2, 1)
    left_filters = {key: list(current) for key, current in shard.filters.items()}
    right_filters = {key: list(current) for key, current in shard.filters.items()}
    left_filters[split_key] = values[:midpoint]
    right_filters[split_key] = values[midpoint:]
    return [
        ObservationShard(
            shard_id=_observation_shard_id(
                plan=shard.plan,
                country_code=shard.country_code,
                start_year=shard.start_year,
                end_year=shard.end_year,
                filters=current_filters,
                split_depth=shard.split_depth + 1,
            ),
            plan=shard.plan,
            country_code=shard.country_code,
            start_year=shard.start_year,
            end_year=shard.end_year,
            filters=current_filters,
            split_depth=shard.split_depth + 1,
            phase=shard.phase,
            acquisition_method=shard.acquisition_method,
            source_watermark=shard.source_watermark,
            dataset_version=shard.dataset_version,
            dimension_order=shard.dimension_order,
        )
        for current_filters in (left_filters, right_filters)
        if current_filters.get(split_key)
    ]


def _build_probe_request(shard: ObservationShard) -> FetchRequest | None:
    filters = _canonicalize_observation_request_filters(
        source=shard.plan.source,
        filters={key: list(values) for key, values in shard.filters.items()},
    )
    if shard.plan.source == "eurostat":
        probe_time = _eurostat_probe_time_value(shard)
        if not probe_time:
            return None
        filters["time"] = [probe_time]
        return FetchRequest(
            dataset_id=shard.plan.request_dataset_id,
            filters=_filters_to_tuple(filters),
            page_size=50,
        )
    probe_start = datetime(shard.start_year, 1, 1, tzinfo=UTC)
    probe_end = probe_start
    return FetchRequest(
        dataset_id=shard.plan.request_dataset_id,
        filters=_filters_to_tuple(filters),
        date_start=probe_start,
        date_end=probe_end,
        page_size=50,
    )


def _eurostat_probe_time_value(shard: ObservationShard) -> str:
    rank = _observation_frequency_rank(shard.plan.update_frequency)
    if rank == 0:
        return str(shard.start_year)
    if rank == 1:
        return f"{shard.start_year}-Q1"
    return f"{shard.start_year}-01"


def _probe_dimension_split_key(
    rows: list[dict[str, Any]],
    *,
    shard: ObservationShard,
) -> tuple[str, list[str]]:
    candidates: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if shard.plan.source == "eurostat":
            dimensions = _load_json_dict(row.get("dimensions_json"))
            for key, value in dimensions.items():
                normalized_key = str(key or "").strip()
                normalized_value = str(value or "").strip()
                if not normalized_key or not normalized_value:
                    continue
                if normalized_key.lower() in {"time", "geo", "country", "ref_area"}:
                    continue
                candidates[normalized_key].add(normalized_value)
            continue
        for key, value in row.items():
            normalized_key = str(key or "").strip()
            if normalized_key.lower() in {
                "value",
                "time",
                "time_period",
                "geo",
                "country",
                "ref_area",
            }:
                continue
            normalized_value = str(value or "").strip()
            if not normalized_value:
                continue
            candidates[normalized_key].add(normalized_value)
    ranked = sorted(
        (
            (len(values), key, sorted(values))
            for key, values in candidates.items()
            if len(values) > 1 and len(shard.filters.get(key, [])) <= 1
        ),
        reverse=True,
    )
    if not ranked:
        return "", []
    _, key, values = ranked[0]
    return key, values


def _largest_filter_key(filters: dict[str, list[str]]) -> str:
    ranked = sorted(
        (
            (len(values), key)
            for key, values in (filters or {}).items()
            if isinstance(values, list) and len(values) > 1
        ),
        reverse=True,
    )
    return ranked[0][1] if ranked else ""


def _shard_completed(
    config: DatasetBatchConfig,
    shard: ObservationShard,
    *,
    completed: dict[str, Any],
    failed: dict[str, Any],
    deferred: dict[str, Any],
) -> bool:
    if not config.resume or config.resume_mode == "off":
        return False
    if shard.shard_id in completed:
        return True
    return bool(
        config.resume_mode == "smart" and (shard.shard_id in failed or shard.shard_id in deferred)
    )


def _record_shard_result(
    config: DatasetBatchConfig,
    *,
    result: ObservationShardResult,
    completed: dict[str, Any],
    failed: dict[str, Any],
    deferred: dict[str, Any],
) -> None:
    _store_shard_result(
        result=result,
        completed=completed,
        failed=failed,
        deferred=deferred,
    )
    checkpoint_state = _load_observation_checkpoint_state(config)
    _write_observation_checkpoint_state(
        config,
        completed=completed,
        failed=failed,
        deferred=deferred,
        unsupported_signatures=checkpoint_state["unsupported_signatures"],
        empty_signatures=checkpoint_state["empty_signatures"],
        inflight_leases=checkpoint_state["inflight_leases"],
        async_fetch_leases=checkpoint_state["async_fetch_leases"],
        capability_snapshots=checkpoint_state["capability_snapshots"],
        capability_failures=checkpoint_state["capability_failures"],
        source_budgets=checkpoint_state["source_budgets"],
        writer_state=checkpoint_state["writer_state"],
        support_sketches=checkpoint_state["support_sketches"],
        work_packages=checkpoint_state["work_packages"],
        planner_phase=checkpoint_state["planner_phase"],
        publishable_core_complete=checkpoint_state["publishable_core_complete"],
        negative_cache_version=checkpoint_state["negative_cache_version"],
        planner_signature=checkpoint_state["planner_signature"],
    )


def _store_shard_result(
    *,
    result: ObservationShardResult,
    completed: dict[str, Any],
    failed: dict[str, Any],
    deferred: dict[str, Any],
) -> None:
    completed.pop(result.shard_id, None)
    failed.pop(result.shard_id, None)
    deferred.pop(result.shard_id, None)
    target = completed
    if result.status == "failed":
        target = failed
    elif result.status == "deferred":
        target = deferred
    target[result.shard_id] = {
        "status": result.status,
        "source": result.source,
        "dataset_id": result.dataset_id,
        "raw_variable": result.raw_variable,
        "canonical_var": result.canonical_var,
        "country_code": result.country_code,
        "start_year": result.start_year,
        "end_year": result.end_year,
        "row_count": result.row_count,
        "error": result.error,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _append_shard_result(
    *,
    result: ObservationShardResult,
    completed_results: list[dict[str, Any]],
    failed_results: list[dict[str, Any]],
    deferred_results: list[dict[str, Any]],
    source_summary: dict[str, dict[str, int]],
) -> None:
    payload = {
        "shard_id": result.shard_id,
        "status": result.status,
        "source": result.source,
        "dataset_id": result.dataset_id,
        "raw_variable": result.raw_variable,
        "canonical_var": result.canonical_var,
        "country_code": result.country_code,
        "start_year": result.start_year,
        "end_year": result.end_year,
        "row_count": result.row_count,
        "error": result.error,
    }
    if result.status.startswith("complete"):
        completed_results.append(payload)
    elif result.status == "failed":
        failed_results.append(payload)
    else:
        deferred_results.append(payload)
    summary = source_summary.setdefault(
        result.source,
        {
            "complete": 0,
            "complete_with_rows": 0,
            "complete_empty": 0,
            "failed": 0,
            "deferred": 0,
            "rows": 0,
        },
    )
    if result.status.startswith("complete"):
        summary["complete"] = int(summary.get("complete", 0)) + 1
    summary[result.status] = int(summary.get(result.status, 0)) + 1
    summary["rows"] = int(summary.get("rows", 0)) + int(result.row_count)


def _write_observation_ingest_manifests(
    *,
    config: DatasetBatchConfig,
    completed_results: list[dict[str, Any]],
    failed_results: list[dict[str, Any]],
    deferred_results: list[dict[str, Any]],
    source_summary: dict[str, dict[str, int]],
) -> None:
    write_json(config.manifests_dir / "completed_observation_shards.json", completed_results)
    write_json(config.manifests_dir / "failed_observation_shards.json", failed_results)
    write_json(config.manifests_dir / "deferred_observation_plans.json", deferred_results)
    write_json(config.manifests_dir / "observation_source_summary.json", source_summary)


async def _legacy_ingest_observations(db_path: Path) -> CoreSourcesIngestStats:
    stats = CoreSourcesIngestStats()
    wb = WorldBankConnector()
    wb_handle = None
    try:
        wb_handle = await wb.connect(_resolve_profile_config("worldbank_wdi"))

        with duckdb.connect(str(db_path)) as con:
            for country in country_scope_members("core_blocking"):
                for indicator, canonical_var in _LEGACY_WGI_INDICATORS.items():
                    try:
                        result = await wb.fetch(
                            wb_handle,
                            FetchRequest(
                                dataset_id=indicator,
                                filters=(("country", (country,)),),
                                date_start=datetime(2018, 1, 1, tzinfo=UTC),
                                date_end=datetime(2022, 12, 31, tzinfo=UTC),
                            ),
                        )
                        _merge_observation_stats(
                            stats,
                            _insert_generic_observations(
                                con=con,
                                plan=ObservationPlan(
                                    dataset_id="WB_WGI",
                                    source="worldbank",
                                    raw_variable=indicator,
                                    canonical_var=canonical_var,
                                    connector_id="worldbank.wdi",
                                    profile_id="worldbank_wdi",
                                    request_dataset_id=indicator,
                                    default_filters={},
                                    update_frequency="annual",
                                ),
                                rows=_records_from_payload(result.data),
                            ),
                        )
                    except Exception as exc:
                        stats.failures += 1
                        logger.warning(
                            "Legacy WGI ingest failed for {}/{}: {}", country, indicator, exc
                        )

                for indicator, canonical_var in _LEGACY_WDI_INDICATORS.items():
                    try:
                        result = await wb.fetch(
                            wb_handle,
                            FetchRequest(
                                dataset_id=indicator,
                                filters=(("country", (country,)),),
                                date_start=datetime(2018, 1, 1, tzinfo=UTC),
                                date_end=datetime(2022, 12, 31, tzinfo=UTC),
                            ),
                        )
                        _merge_observation_stats(
                            stats,
                            _insert_generic_observations(
                                con=con,
                                plan=ObservationPlan(
                                    dataset_id="WB_WDI",
                                    source="worldbank",
                                    raw_variable=indicator,
                                    canonical_var=canonical_var,
                                    connector_id="worldbank.wdi",
                                    profile_id="worldbank_wdi",
                                    request_dataset_id=indicator,
                                    default_filters={},
                                    update_frequency="annual",
                                ),
                                rows=_records_from_payload(result.data),
                            ),
                        )
                    except Exception as exc:
                        stats.failures += 1
                        logger.warning(
                            "Legacy WDI ingest failed for {}/{}: {}", country, indicator, exc
                        )

            wvs_indicators = _wvs_legacy_indicators()
            if wvs_indicators:
                try:
                    wvs_bulk = _load_wvs_bulk_duckdb(
                        list(wvs_indicators.keys()),
                        country_scope="core_blocking",
                        year_window=(1981, 2023),
                    )
                    logger.info(
                        "WVS DuckDB bulk load: {} indicators, {} total rows",
                        len(wvs_bulk),
                        sum(len(v) for v in wvs_bulk.values()),
                    )
                except Exception as exc:
                    logger.warning("WVS DuckDB bulk load failed: {}", exc)
                    wvs_bulk = {}

                for indicator, canonical_var in wvs_indicators.items():
                    try:
                        rows = wvs_bulk.get(indicator, [])
                        if not rows:
                            continue
                        _merge_observation_stats(
                            stats,
                            _insert_generic_observations(
                                con=con,
                                plan=ObservationPlan(
                                    dataset_id="WVS_W7",
                                    source="wvs",
                                    raw_variable=indicator,
                                    canonical_var=canonical_var,
                                    connector_id="wvs.wave7",
                                    profile_id="wvs_wave7",
                                    request_dataset_id=indicator,
                                    default_filters={},
                                    update_frequency="wave",
                                ),
                                rows=rows,
                            ),
                        )
                    except Exception as exc:
                        stats.failures += 1
                        logger.warning("Legacy WVS bulk ingest failed for {}: {}", indicator, exc)
            con.execute("CHECKPOINT")
    finally:
        if wb_handle is not None:
            await wb.disconnect(wb_handle)
    return stats


def _upsert_legacy_registry_datasets(con: duckdb.DuckDBPyConnection) -> int:
    last_updated = datetime.now(UTC).date().isoformat()
    datasets = [
        (
            "WB_WGI",
            "worldbank",
            "World Governance Indicators",
            json.dumps(
                {"countries": [], "time_range": "1996-2023", "granularity": "country-year"},
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "access_type": "open",
                    "api_endpoint": "https://api.worldbank.org/v2",
                    "license": "CC-BY-4.0",
                },
                separators=(",", ":"),
            ),
            "annual",
            last_updated,
        ),
        (
            "WB_WDI",
            "worldbank",
            "World Development Indicators",
            json.dumps(
                {"countries": [], "time_range": "1960-2023", "granularity": "country-year"},
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "access_type": "open",
                    "api_endpoint": "https://api.worldbank.org/v2",
                    "license": "CC-BY-4.0",
                },
                separators=(",", ":"),
            ),
            "annual",
            last_updated,
        ),
        (
            "WVS_W7",
            "wvs",
            "World Values Survey Time Series 1981-2022",
            json.dumps(
                {"countries": [], "time_range": "1981-2022", "granularity": "country-survey-wave"},
                separators=(",", ":"),
            ),
            json.dumps(
                {
                    "access_type": "local_bulk_file",
                    "api_endpoint": "",
                    "bulk_download_url": "data/raw/wvs/WVS_Time_Series_1981-2022_csv_v5_0.csv",
                    "license": "WVS terms",
                },
                separators=(",", ":"),
            ),
            "wave",
            last_updated,
        ),
        (
            "IMF_SHADOW",
            "imf",
            "IMF Shadow Economy Estimates",
            json.dumps(
                {"countries": [], "time_range": "1990-2022", "granularity": "country-year"},
                separators=(",", ":"),
            ),
            json.dumps(
                {"access_type": "open", "api_endpoint": "", "license": "IMF terms"},
                separators=(",", ":"),
            ),
            "annual",
            last_updated,
        ),
    ]
    con.executemany(
        "INSERT OR REPLACE INTO ds_registry_datasets "
        "(dataset_id, provider, title, coverage_json, access_json, update_freq, last_updated) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        datasets,
    )
    return len(datasets)


def _upsert_seed_alignments(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    alignments = load_seed_alignments(path)
    return _upsert_catalog_alignments(con, alignments)


def _insert_generic_observations(
    *,
    con: duckdb.DuckDBPyConnection,
    plan: ObservationPlan,
    rows: list[dict[str, Any]],
    acquisition_method: str = "",
    source_watermark: str = "",
    dataset_version: str = "",
) -> ObservationInsertStats:
    if not rows:
        return ObservationInsertStats()
    if hasattr(con, "execute"):
        _ensure_observation_provenance_columns(con)
        _ensure_observation_index_compatibility(con)
    attempted = 0
    unique_rows: dict[str, tuple] = {}
    multi_slice_groups: dict[tuple[str, int | None], set[str]] = {}
    for row in rows:
        normalized = _normalize_observation_row(row)
        if normalized is None:
            continue
        attempted += 1
        country_code, year, survey_year, wave, value, condition_json = normalized
        obs_id = _observation_id(
            plan.dataset_id,
            plan.raw_variable,
            plan.canonical_var,
            country_code,
            year=year,
            survey_year=survey_year,
            wave=wave,
            condition_json=condition_json,
        )
        unique_rows[obs_id] = (
            obs_id,
            plan.dataset_id,
            plan.raw_variable,
            plan.canonical_var,
            country_code,
            year,
            survey_year,
            wave,
            value,
            condition_json,
            acquisition_method or None,
            source_watermark or plan.source_watermark or None,
            dataset_version or plan.dataset_version or None,
        )
        multi_slice_groups.setdefault((country_code, year), set()).add(obs_id)
    if not unique_rows:
        return ObservationInsertStats()
    multi_slice_keys = sum(1 for ids in multi_slice_groups.values() if len(ids) > 1)
    if multi_slice_keys > 0:
        logger.warning(
            "Observation plan {} {} {} produced {} multi-slice country/year keys; preserving condition-aware rows",
            plan.dataset_id,
            plan.raw_variable,
            plan.canonical_var,
            multi_slice_keys,
        )
    existing_ids = _existing_observation_ids(con, unique_rows.keys())
    inserted = len(unique_rows) - len(existing_ids)
    replaced = len(existing_ids)
    insert_sql = (
        "INSERT INTO ds_observations "
        "(observation_id, dataset_id, raw_variable, canonical_var, country_code, "
        "year, survey_year, wave, value, condition_json, acquisition_method, source_watermark, dataset_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(observation_id) DO UPDATE SET "
        "value=EXCLUDED.value, "
        "condition_json=EXCLUDED.condition_json, "
        "acquisition_method=EXCLUDED.acquisition_method, "
        "source_watermark=EXCLUDED.source_watermark, "
        "dataset_version=EXCLUDED.dataset_version"
    )
    for chunk in _iter_chunked_values(unique_rows.values(), _OBSERVATION_INSERT_BATCH_SIZE):
        con.executemany(
            insert_sql,
            chunk,
        )
    return ObservationInsertStats(
        attempted=attempted,
        inserted=inserted,
        replaced=replaced,
    )


def _merge_observation_stats(
    stats: CoreSourcesIngestStats,
    inserted: ObservationInsertStats,
    *,
    source: str = "",
) -> None:
    stats.observations += inserted.inserted
    stats.observations_attempted += inserted.attempted
    stats.observations_inserted += inserted.inserted
    stats.observations_replaced += inserted.replaced
    if source and inserted.written > 0:
        stats.record_source_observations(source, inserted.written)


def _iter_chunked_values(values: Any, chunk_size: int) -> Any:
    iterator = iter(values)
    while True:
        chunk = list(islice(iterator, max(int(chunk_size), 1)))
        if not chunk:
            return
        yield chunk


def _existing_observation_ids(
    con: duckdb.DuckDBPyConnection,
    observation_ids: Any,
) -> set[str]:
    matches: set[str] = set()
    chunk_size = 512
    for chunk in _iter_chunked_values(observation_ids, chunk_size):
        placeholders = ", ".join("?" for _ in chunk)
        rows = con.execute(
            f"SELECT observation_id FROM ds_observations WHERE observation_id IN ({placeholders})",
            list(chunk),
        ).fetchall()
        matches.update(str(row[0]) for row in rows if row and row[0])
    return matches


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if hasattr(payload, "to_dict"):
        try:
            rows = payload.to_dict(orient="records")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        except Exception:
            logger.debug("Failed to convert payload frame to records", exc_info=True)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("value", "data", "items", "results", "records"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [row for row in candidate if isinstance(row, dict)]
    return []


def _safe_path_token(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    text = text.strip("._")
    return text or "unknown"


def _quote_identifier(identifier: str) -> str:
    return '"' + str(identifier or "").replace('"', '""') + '"'


def _bulk_materialization_lock(path: Path) -> asyncio.Lock:
    key = str(path)
    lock = _BULK_MATERIALIZATION_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _BULK_MATERIALIZATION_LOCKS[key] = lock
    return lock


def _bulk_dataset_version_token(shard: ObservationShard) -> str:
    return _safe_path_token(
        shard.dataset_version
        or shard.plan.dataset_version
        or shard.plan.request_dataset_id
        or "dataset"
    )


def _bulk_dataset_token(shard: ObservationShard) -> str:
    return _safe_path_token(
        shard.plan.request_dataset_id
        or shard.plan.raw_variable
        or shard.plan.dataset_id
        or "dataset"
    )


def _bulk_raw_dir(
    config: DatasetBatchConfig,
    *,
    source: str,
    dataset_version: str,
) -> Path:
    return config.raw_dir / "observations" / source / dataset_version / "bulk"


def _bulk_normalized_path(
    config: DatasetBatchConfig,
    *,
    shard: ObservationShard,
) -> Path:
    return (
        config.normalized_dir
        / "observations"
        / shard.plan.source
        / _bulk_dataset_version_token(shard)
        / f"{_bulk_dataset_token(shard)}.parquet"
    )


def _bulk_legacy_manifest_path(
    config: DatasetBatchConfig,
    *,
    source: str,
    dataset_version: str,
) -> Path:
    return config.raw_dir / source / dataset_version / "manifest.json"


def _bulk_equivalence_manifest_path(
    config: DatasetBatchConfig,
    *,
    shard: ObservationShard,
) -> Path:
    return (
        config.manifests_dir
        / "observations"
        / "bulk_equivalence"
        / shard.plan.source
        / _bulk_dataset_version_token(shard)
        / f"{_bulk_dataset_token(shard)}.json"
    )


def _bulk_parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    text = str(value).strip()
    if not text or text == ":":
        return None
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        parsed = float(match.group(0))
    except ValueError:
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _iter_batches(records: Any, *, size: int = 50_000) -> Any:
    batch: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _write_bulk_records_to_parquet(
    *,
    records: Any,
    normalized_path: Path,
    table_name: str,
) -> int:
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    temp_db_path = normalized_path.with_suffix(".duckdb")
    wal_path = Path(f"{temp_db_path}.wal")
    row_count = 0
    created = False
    table_ident = _quote_identifier(table_name)
    with duckdb.connect(str(temp_db_path)) as con:
        for batch in _iter_batches(records):
            frame = pd.DataFrame.from_records(batch)
            if frame.empty:
                continue
            con.register("bulk_batch_df", frame)
            try:
                if not created:
                    con.execute(f"CREATE TABLE {table_ident} AS SELECT * FROM bulk_batch_df")
                    created = True
                else:
                    con.execute(f"INSERT INTO {table_ident} SELECT * FROM bulk_batch_df")
            finally:
                con.unregister("bulk_batch_df")
            row_count += len(frame.index)
        if created:
            con.execute(f"COPY {table_ident} TO ? (FORMAT PARQUET)", [str(normalized_path)])
    temp_db_path.unlink(missing_ok=True)
    wal_path.unlink(missing_ok=True)
    return row_count


def _parquet_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with duckdb.connect() as con:
        row = con.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()
    return int(row[0] or 0) if row else 0


def _parquet_columns(path: Path) -> list[str]:
    if not path.exists():
        return []
    with duckdb.connect() as con:
        rows = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
    return [str(row[0]) for row in rows if row and row[0]]


def _bulk_source_columns(source: str, path: Path) -> tuple[list[str], dict[str, str]]:
    columns = _parquet_columns(path)
    return columns, {str(column).strip().lower(): str(column) for column in columns}


async def _record_bulk_download_result(
    *,
    source: str,
    record_result: Any | None,
    request_count: int,
    bytes_downloaded: int,
) -> None:
    if record_result is None:
        return
    await record_result(
        source=source,
        request_count=int(request_count),
        bytes_transferred=int(bytes_downloaded),
    )


async def _http_get_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[str, dict[str, str]]:
    timeout = aiohttp.ClientTimeout(total=120)
    request_headers = {"Accept": "text/plain, text/html, */*"}
    if headers:
        request_headers.update(headers)
    async with aiohttp.ClientSession(timeout=timeout, headers=request_headers) as session:
        async with session.get(url, params=params) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status} for {url}")
            return await resp.text(), dict(resp.headers)


async def _http_download_to_path(
    url: str,
    path: Path,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    if path.exists():
        return {
            "path": path,
            "url": url,
            "request_count": 0,
            "bytes_downloaded": 0,
            "payload_bytes": int(path.stat().st_size),
            "etag": "",
            "last_modified": "",
        }
    timeout = aiohttp.ClientTimeout(total=900)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession(timeout=timeout, headers=headers or {}) as session:
        async with session.get(url) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status} for {url}")
            bytes_downloaded = 0
            with open(path, "wb") as fh:
                async for chunk in resp.content.iter_chunked(1024 * 1024):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    bytes_downloaded += len(chunk)
            return {
                "path": path,
                "url": url,
                "request_count": 1,
                "bytes_downloaded": bytes_downloaded,
                "payload_bytes": int(path.stat().st_size),
                "etag": str(resp.headers.get("ETag") or ""),
                "last_modified": str(resp.headers.get("Last-Modified") or ""),
            }


async def _resolve_eurostat_bulk_download(
    *,
    config: DatasetBatchConfig,
    shard: ObservationShard,
) -> tuple[str, Path]:
    dataset_version = _bulk_dataset_version_token(shard)
    raw_dir = _bulk_raw_dir(config, source="eurostat", dataset_version=dataset_version)
    inventory_path = raw_dir / "inventory-data.tsv"
    inventory_url = "https://ec.europa.eu/eurostat/api/dissemination/files/inventory?type=data"
    if not inventory_path.exists():
        await _http_download_to_path(inventory_url, inventory_path)
    with open(inventory_path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if (
                str(row.get("Code") or "").strip()
                != str(shard.plan.request_dataset_id or "").strip()
            ):
                continue
            url = str(row.get("Data download url (tsv)") or "").strip()
            if url:
                return url, inventory_path
    raise RuntimeError(f"Eurostat bulk TSV URL not found for {shard.plan.request_dataset_id}")


def _iter_eurostat_bulk_records(tsv_path: Path) -> Any:
    with open(tsv_path, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader, [])
        if not header:
            return
        dimension_key = str(header[0] or "")
        dimension_names = [
            segment.strip()
            for segment in dimension_key.split("\\", 1)[0].split(",")
            if segment.strip()
        ]
        time_labels = [str(value or "").strip() for value in header[1:]]
        for row in reader:
            if not row:
                continue
            dimension_values = [segment.strip() for segment in str(row[0] or "").split(",")]
            base = {
                dimension_names[index]: dimension_values[index]
                if index < len(dimension_values)
                else ""
                for index in range(len(dimension_names))
            }
            for time_label, raw_value in zip(time_labels, row[1:], strict=False):
                value = _bulk_parse_numeric(raw_value)
                if value is None:
                    continue
                yield {
                    **base,
                    "time_period": time_label,
                    "value": value,
                }


def _iter_ilo_bulk_records(gzip_path: Path) -> Any:
    with gzip.open(gzip_path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not isinstance(row, dict):
                continue
            payload = {str(key).strip().lower(): value for key, value in row.items() if key}
            value = _bulk_parse_numeric(payload.get("obs_value"))
            if value is None:
                continue
            payload["obs_value"] = value
            yield payload


def _extract_uis_bulk_archive_links(html: str) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for match in re.finditer(r"https://download\.uis\.unesco\.org/[^\s\"']+\.zip", html or ""):
        url = str(match.group(0)).strip()
        if url in seen:
            continue
        seen.add(url)
        links.append(url)
    return links


def _uis_archive_priority(dataset_id: str, archive_url: str) -> tuple[int, str]:
    name = Path(urlparse(archive_url).path).name.upper()
    indicator = str(dataset_id or "").strip().upper()
    if indicator.startswith("SCN"):
        preferred = {
            "SCN-OPRI.ZIP": 0,
            "SCN-SDG.ZIP": 1,
            "OPRI.ZIP": 2,
            "SDG.ZIP": 3,
        }
        return preferred.get(name, 10), name
    if indicator.startswith("SDG"):
        preferred = {"SDG.ZIP": 0, "SDG11.ZIP": 1, "SCN-SDG.ZIP": 2}
        return preferred.get(name, 10), name
    if indicator.startswith("DEM"):
        preferred = {"DEM.ZIP": 0, "OPRI.ZIP": 1, "SDG.ZIP": 2}
        return preferred.get(name, 10), name
    preferred = {
        "OPRI.ZIP": 0,
        "SDG.ZIP": 1,
        "SCN-OPRI.ZIP": 2,
        "SCN-SDG.ZIP": 3,
        "DEM.ZIP": 4,
        "SDG11.ZIP": 5,
    }
    return preferred.get(name, 10), name


def _iter_uis_bulk_records(zip_path: Path, *, dataset_id: str) -> Any:
    dataset_token = str(dataset_id or "").strip().upper()
    with zipfile.ZipFile(zip_path, "r") as archive:
        members = sorted(
            (
                info.filename
                for info in archive.infolist()
                if info.filename.upper().endswith(".CSV") and "DATA" in info.filename.upper()
            ),
            key=lambda name: (
                0 if "DATA_NATIONAL" in name.upper() else 1,
                name.upper(),
            ),
        )
        for member in members:
            with archive.open(member, "r") as raw_fh:
                text_fh = io.TextIOWrapper(raw_fh, encoding="utf-8-sig", newline="")
                reader = csv.DictReader(text_fh)
                for row in reader:
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("INDICATOR_ID") or "").strip().upper() != dataset_token:
                        continue
                    country_code = _normalize_country_code(row.get("COUNTRY_ID"))
                    if not country_code:
                        continue
                    year = _extract_year(row.get("YEAR"))
                    value = _bulk_parse_numeric(row.get("VALUE"))
                    if year is None or value is None:
                        continue
                    yield {
                        "indicator_id": dataset_token,
                        "country_code": country_code,
                        "year": year,
                        "value": value,
                        "magnitude": row.get("MAGNITUDE"),
                        "qualifier": row.get("QUALIFIER"),
                    }


def _write_bulk_raw_manifest(
    *,
    config: DatasetBatchConfig,
    shard: ObservationShard,
    endpoint: str,
    payload_path: Path,
    row_count: int,
) -> None:
    manifest_path = _bulk_legacy_manifest_path(
        config,
        source=shard.plan.source,
        dataset_version=_bulk_dataset_version_token(shard),
    )
    write_raw_manifest(
        manifest_path=manifest_path,
        source=shard.plan.source,
        endpoint=endpoint,
        payload_path=payload_path,
        count=row_count,
        filters={
            "dataset_id": shard.plan.request_dataset_id,
            "dataset_version": shard.dataset_version
            or shard.plan.dataset_version
            or shard.plan.request_dataset_id,
            "acquisition_method": shard.acquisition_method,
        },
        parser_version="bulk-v1",
    )


async def _materialize_eurostat_bulk_dataset(
    *,
    shard: ObservationShard,
    config: DatasetBatchConfig,
    record_result: Any | None,
) -> dict[str, Any]:
    normalized_path = _bulk_normalized_path(config, shard=shard)
    dataset_version = _bulk_dataset_version_token(shard)
    raw_dir = _bulk_raw_dir(config, source="eurostat", dataset_version=dataset_version)
    bulk_url, inventory_path = await _resolve_eurostat_bulk_download(config=config, shard=shard)
    raw_path = raw_dir / f"{_bulk_dataset_token(shard)}.tsv"
    download = await _http_download_to_path(bulk_url, raw_path)
    inventory_bytes = int(inventory_path.stat().st_size) if inventory_path.exists() else 0
    await _record_bulk_download_result(
        source=shard.plan.source,
        record_result=record_result,
        request_count=int(download["request_count"]) + (0 if inventory_path.exists() else 0),
        bytes_downloaded=int(download["bytes_downloaded"]),
    )
    if not normalized_path.exists():
        row_count = _write_bulk_records_to_parquet(
            records=_iter_eurostat_bulk_records(raw_path),
            normalized_path=normalized_path,
            table_name=f"bulk_eurostat_{_bulk_dataset_token(shard)}",
        )
        _write_bulk_raw_manifest(
            config=config,
            shard=shard,
            endpoint=bulk_url,
            payload_path=raw_path,
            row_count=row_count,
        )
    else:
        row_count = _parquet_row_count(normalized_path)
    return {
        "normalized_path": normalized_path,
        "raw_path": raw_path,
        "bulk_url": bulk_url,
        "row_count": row_count,
        "source_watermark": str(download.get("etag") or download.get("last_modified") or ""),
        "bytes_downloaded": int(download.get("bytes_downloaded", 0) or 0) + inventory_bytes,
    }


async def _materialize_ilo_bulk_dataset(
    *,
    shard: ObservationShard,
    config: DatasetBatchConfig,
    record_result: Any | None,
) -> dict[str, Any]:
    normalized_path = _bulk_normalized_path(config, shard=shard)
    dataset_version = _bulk_dataset_version_token(shard)
    raw_dir = _bulk_raw_dir(config, source="ilo", dataset_version=dataset_version)
    raw_url = (
        f"https://rplumber.ilo.org/data/indicator?id={shard.plan.request_dataset_id}&format=.csv.gz"
    )
    raw_path = raw_dir / f"{_bulk_dataset_token(shard)}.csv.gz"
    download = await _http_download_to_path(raw_url, raw_path)
    await _record_bulk_download_result(
        source=shard.plan.source,
        record_result=record_result,
        request_count=int(download["request_count"]),
        bytes_downloaded=int(download["bytes_downloaded"]),
    )
    if not normalized_path.exists():
        row_count = _write_bulk_records_to_parquet(
            records=_iter_ilo_bulk_records(raw_path),
            normalized_path=normalized_path,
            table_name=f"bulk_ilo_{_bulk_dataset_token(shard)}",
        )
        _write_bulk_raw_manifest(
            config=config,
            shard=shard,
            endpoint=raw_url,
            payload_path=raw_path,
            row_count=row_count,
        )
    else:
        row_count = _parquet_row_count(normalized_path)
    return {
        "normalized_path": normalized_path,
        "raw_path": raw_path,
        "bulk_url": raw_url,
        "row_count": row_count,
        "source_watermark": str(download.get("etag") or download.get("last_modified") or ""),
        "bytes_downloaded": int(download.get("bytes_downloaded", 0) or 0),
    }


async def _materialize_uis_bulk_dataset(
    *,
    shard: ObservationShard,
    config: DatasetBatchConfig,
    record_result: Any | None,
) -> dict[str, Any]:
    normalized_path = _bulk_normalized_path(config, shard=shard)
    dataset_version = _bulk_dataset_version_token(shard)
    raw_dir = _bulk_raw_dir(config, source="unesco_uis", dataset_version=dataset_version)
    page_path = raw_dir / "bulk-page.html"
    bulk_page_url = "https://databrowser.uis.unesco.org/resources/bulk"
    if not page_path.exists():
        body, _headers = await _http_get_text(bulk_page_url)
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(body, encoding="utf-8")
    archive_links = _extract_uis_bulk_archive_links(page_path.read_text(encoding="utf-8"))
    if not archive_links:
        raise RuntimeError("UNESCO UIS bulk archive list is empty")
    sorted_links = sorted(
        archive_links,
        key=lambda url: _uis_archive_priority(shard.plan.request_dataset_id, url),
    )
    if normalized_path.exists():
        return {
            "normalized_path": normalized_path,
            "raw_path": next(
                (raw_dir / Path(urlparse(url).path).name for url in sorted_links), page_path
            ),
            "bulk_url": sorted_links[0],
            "row_count": _parquet_row_count(normalized_path),
            "source_watermark": "",
            "bytes_downloaded": 0,
        }

    for archive_url in sorted_links:
        archive_name = Path(urlparse(archive_url).path).name or f"{_bulk_dataset_token(shard)}.zip"
        archive_path = raw_dir / archive_name
        download = await _http_download_to_path(archive_url, archive_path)
        await _record_bulk_download_result(
            source=shard.plan.source,
            record_result=record_result,
            request_count=int(download["request_count"]),
            bytes_downloaded=int(download["bytes_downloaded"]),
        )
        row_count = _write_bulk_records_to_parquet(
            records=_iter_uis_bulk_records(archive_path, dataset_id=shard.plan.request_dataset_id),
            normalized_path=normalized_path,
            table_name=f"bulk_uis_{_bulk_dataset_token(shard)}",
        )
        if row_count > 0:
            _write_bulk_raw_manifest(
                config=config,
                shard=shard,
                endpoint=archive_url,
                payload_path=archive_path,
                row_count=row_count,
            )
            return {
                "normalized_path": normalized_path,
                "raw_path": archive_path,
                "bulk_url": archive_url,
                "row_count": row_count,
                "source_watermark": str(
                    download.get("etag") or download.get("last_modified") or ""
                ),
                "bytes_downloaded": int(download.get("bytes_downloaded", 0) or 0),
            }
        normalized_path.unlink(missing_ok=True)
    raise RuntimeError(
        f"UNESCO UIS bulk archive did not contain indicator {shard.plan.request_dataset_id}"
    )


async def _ensure_remote_bulk_materialized(
    *,
    shard: ObservationShard,
    config: DatasetBatchConfig,
    record_result: Any | None,
) -> dict[str, Any]:
    normalized_path = _bulk_normalized_path(config, shard=shard)
    async with _bulk_materialization_lock(normalized_path):
        if shard.plan.source == "eurostat":
            return await _materialize_eurostat_bulk_dataset(
                shard=shard,
                config=config,
                record_result=record_result,
            )
        if shard.plan.source == "ilo":
            return await _materialize_ilo_bulk_dataset(
                shard=shard,
                config=config,
                record_result=record_result,
            )
        if shard.plan.source == "unesco_uis":
            return await _materialize_uis_bulk_dataset(
                shard=shard,
                config=config,
                record_result=record_result,
            )
    raise RuntimeError(f"Remote bulk materialization is not implemented for {shard.plan.source}")


def _bulk_year_expression(source: str, lower_map: dict[str, str]) -> tuple[str, str | None]:
    if source == "eurostat":
        column = lower_map.get("time_period") or lower_map.get("year")
    elif source == "ilo":
        column = lower_map.get("time") or lower_map.get("year")
    else:
        column = lower_map.get("year")
    if not column:
        return "NULL", None
    quoted = _quote_identifier(column)
    return (
        f"coalesce(try_cast(regexp_extract(cast({quoted} AS VARCHAR), '(19|20)\\\\d{{2}}') AS INTEGER), try_cast({quoted} AS INTEGER))",
        column,
    )


def _bulk_country_column(source: str, lower_map: dict[str, str]) -> str | None:
    if source == "eurostat":
        return lower_map.get("geo")
    if source == "ilo":
        return lower_map.get("ref_area")
    if source == "unesco_uis":
        return lower_map.get("country_code")
    return lower_map.get("country_code")


def _bulk_country_values(source: str, country_codes: tuple[str, ...]) -> list[str]:
    normalized = [str(value).strip().upper() for value in country_codes if str(value).strip()]
    if source == "eurostat":
        return normalized
    if source == "ilo":
        return [_to_iso3(code) for code in normalized]
    return normalized


def _bulk_query_rows(
    *,
    source: str,
    normalized_path: Path,
    filters: dict[str, list[str]],
    countries: tuple[str, ...],
    year_range: tuple[int, int],
) -> list[dict[str, Any]]:
    if not normalized_path.exists():
        return []
    columns, lower_map = _bulk_source_columns(source, normalized_path)
    if not columns:
        return []
    year_expr, year_column = _bulk_year_expression(source, lower_map)
    where: list[str] = []
    params: list[Any] = [str(normalized_path)]
    country_column = _bulk_country_column(source, lower_map)
    country_values = _bulk_country_values(source, countries)
    if country_column and country_values:
        placeholders = ", ".join("?" for _ in country_values)
        where.append(
            f"upper(cast({_quote_identifier(country_column)} AS VARCHAR)) IN ({placeholders})"
        )
        params.extend(country_values)
    if year_column:
        where.append(f"{year_expr} BETWEEN ? AND ?")
        params.extend([int(year_range[0]), int(year_range[1])])
    for key, values in sorted((filters or {}).items()):
        actual = lower_map.get(str(key).strip().lower())
        if actual in (country_column, year_column) or actual is None:
            continue
        prepared = [str(value).strip().upper() for value in values if str(value).strip()]
        if not prepared:
            continue
        placeholders = ", ".join("?" for _ in prepared)
        where.append(f"upper(cast({_quote_identifier(actual)} AS VARCHAR)) IN ({placeholders})")
        params.extend(prepared)
    sql = "SELECT * FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with duckdb.connect() as con:
        frame = con.execute(sql, params).df()
    return _records_from_payload(frame)


def _bulk_equivalence_series_columns(source: str, path: Path) -> list[str]:
    columns = _parquet_columns(path)
    excluded = {"value", "obs_value"}
    if source == "eurostat":
        excluded.update({"time_period", "year"})
    elif source == "ilo":
        excluded.update({"time", "year"})
        excluded.update({column for column in columns if column.lower().startswith("note_")})
    else:
        excluded.update({"year"})
    return [column for column in columns if column not in excluded]


def _bulk_series_sample(
    *,
    source: str,
    normalized_path: Path,
) -> tuple[int, list[dict[str, Any]]]:
    series_columns = _bulk_equivalence_series_columns(source, normalized_path)
    if not series_columns:
        return 1, [{}]
    select_clause = ", ".join(_quote_identifier(column) for column in series_columns)
    hash_expr = ", ".join(
        f"coalesce(cast({_quote_identifier(column)} AS VARCHAR), '')" for column in series_columns
    )
    with duckdb.connect() as con:
        total_row = con.execute(
            f"SELECT count(*) FROM (SELECT DISTINCT {select_clause} FROM read_parquet(?))",
            [str(normalized_path)],
        ).fetchone()
        total_series = int(total_row[0] or 0) if total_row else 0
        if total_series <= 0:
            return 0, []
        sample_size = min(total_series, max(20, math.ceil(total_series * 0.01)))
        sample_size = min(sample_size, 200)
        frame = con.execute(
            f"SELECT DISTINCT {select_clause} "
            "FROM read_parquet(?) "
            f"ORDER BY hash({hash_expr}) LIMIT ?",
            [str(normalized_path), int(sample_size)],
        ).df()
    return total_series, _records_from_payload(frame)


def _bulk_series_constraints(series: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): value for key, value in dict(series or {}).items() if value not in (None, "", [])
    }


def _bulk_query_series_rows(
    *,
    source: str,
    normalized_path: Path,
    series_constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    columns, lower_map = _bulk_source_columns(source, normalized_path)
    if not columns:
        return []
    where: list[str] = []
    params: list[Any] = [str(normalized_path)]
    for key, value in sorted(series_constraints.items()):
        actual = lower_map.get(str(key).strip().lower())
        if actual is None:
            continue
        where.append(f"cast({_quote_identifier(actual)} AS VARCHAR) = ?")
        params.append(str(value))
    sql = "SELECT * FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    with duckdb.connect() as con:
        frame = con.execute(sql, params).df()
    return _records_from_payload(frame)


def _filter_rows_by_series_constraints(
    rows: list[dict[str, Any]],
    *,
    constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    if not constraints:
        return list(rows)
    filtered: list[dict[str, Any]] = []
    normalized_constraints = {
        str(key).strip().lower(): str(value).strip().upper()
        for key, value in constraints.items()
        if value not in (None, "", [])
    }
    for row in rows:
        lowered = {str(key).strip().lower(): value for key, value in row.items()}
        # Some connector payloads keep the full series signature inside a JSON
        # blob instead of exposing every dimension as a top-level column.
        for embedded_key in ("dimensions_json", "condition_json"):
            for key, value in _load_json_dict(row.get(embedded_key)).items():
                lowered.setdefault(str(key).strip().lower(), value)
        matched = True
        for key, expected in normalized_constraints.items():
            actual = lowered.get(key)
            if str(actual).strip().upper() != expected:
                matched = False
                break
        if matched:
            filtered.append(dict(row))
    return filtered


def _equivalence_signature(rows: list[dict[str, Any]]) -> tuple[int, str]:
    tuples: list[tuple[str, int | None, float, str]] = []
    for row in rows:
        normalized = _normalize_observation_row(row)
        if normalized is None:
            continue
        country_code, year, survey_year, _wave, value, condition_json = normalized
        condition = _load_json_dict(condition_json)
        unit = (
            condition.get("unit")
            or condition.get("UNIT")
            or condition.get("magnitude")
            or condition.get("MAGNITUDE")
            or ""
        )
        tuples.append(
            (
                country_code,
                year if year is not None else survey_year,
                round(float(value), 12),
                str(unit),
            )
        )
    tuples.sort()
    payload = json.dumps(tuples, ensure_ascii=False, separators=(",", ":"))
    return len(tuples), hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _series_year_bounds(rows: list[dict[str, Any]]) -> tuple[int, int] | None:
    years = []
    for row in rows:
        normalized = _normalize_observation_row(row)
        if normalized is None:
            continue
        year = normalized[1] if normalized[1] is not None else normalized[2]
        if year is not None:
            years.append(int(year))
    if not years:
        return None
    return min(years), max(years)


async def _fetch_bulk_equivalence_api_rows(
    *,
    source: str,
    shard: ObservationShard,
    series_constraints: dict[str, Any],
    year_bounds: tuple[int, int],
    cache: _ConnectorSessionCache,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    record_result: Any | None,
    budget_wait_observer: Any | None,
) -> list[dict[str, Any]]:
    filters = {
        str(key): [str(value)]
        for key, value in series_constraints.items()
        if value not in (None, "", [])
    }
    request = FetchRequest(
        dataset_id=shard.plan.request_dataset_id,
        filters=_filters_to_tuple(filters),
        date_start=datetime(int(year_bounds[0]), 1, 1, tzinfo=UTC),
        date_end=datetime(int(year_bounds[1]), 12, 31, tzinfo=UTC),
        page_size=200,
    )
    if source == "eurostat":
        connector, handle = await cache.get_eurostat()
    elif source == "ilo":
        connector, handle = await cache.get_sdmx(shard.plan.profile_id or "ilo_sdmx")
    elif source == "unesco_uis":
        connector, handle = await cache.get_unesco_uis()
        country_code = str(
            series_constraints.get("country_code") or series_constraints.get("country") or ""
        ).strip()
        request = FetchRequest(
            dataset_id=shard.plan.request_dataset_id,
            filters=(("country", (country_code,)),) if country_code else (),
            date_start=datetime(int(year_bounds[0]), 1, 1, tzinfo=UTC),
            date_end=datetime(int(year_bounds[1]), 12, 31, tzinfo=UTC),
            page_size=200,
        )
    else:
        return []
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
    api_rows = _records_from_payload(result.data)
    if source == "unesco_uis":
        post_constraints = {
            key: value
            for key, value in series_constraints.items()
            if key in {"indicator_id", "country_code", "magnitude", "qualifier"}
        }
        return _filter_rows_by_series_constraints(api_rows, constraints=post_constraints)
    return _filter_rows_by_series_constraints(api_rows, constraints=series_constraints)


def _bulk_equivalence_source_is_blocking(config: DatasetBatchConfig, source: str) -> bool:
    if source in set(config.promoted_sources):
        return True
    for spec in config.load_registry().sources:
        if spec.name == source:
            return bool(spec.publish_blocking)
    return False


async def _ensure_bulk_equivalence_manifest(
    *,
    shard: ObservationShard,
    config: DatasetBatchConfig,
    normalized_path: Path,
    raw_path: Path,
    bulk_url: str,
    cache: _ConnectorSessionCache,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    record_result: Any | None,
    budget_wait_observer: Any | None,
) -> None:
    if config.is_sampled_run or config.preflight_only or config.run_profile == "preflight_core":
        return
    manifest_path = _bulk_equivalence_manifest_path(config, shard=shard)
    if manifest_path.exists():
        return
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    total_series, sampled = _bulk_series_sample(
        source=shard.plan.source, normalized_path=normalized_path
    )
    if total_series <= 0:
        write_json(
            manifest_path,
            {
                "status": "empty",
                "source": shard.plan.source,
                "dataset_id": shard.plan.request_dataset_id,
                "dataset_version": shard.dataset_version
                or shard.plan.dataset_version
                or shard.plan.request_dataset_id,
                "series_total": 0,
                "sampled_series": 0,
                "compared_series": 0,
                "mismatches": 0,
                "mismatch_rate": 0.0,
                "blocking": False,
                "bulk_url": bulk_url,
                "raw_path": str(raw_path),
                "normalized_path": str(normalized_path),
            },
        )
        return
    compared = 0
    mismatches = 0
    sample_results: list[dict[str, Any]] = []
    try:
        for sample in sampled:
            constraints = _bulk_series_constraints(sample)
            bulk_rows = _bulk_query_series_rows(
                source=shard.plan.source,
                normalized_path=normalized_path,
                series_constraints=constraints,
            )
            year_bounds = _series_year_bounds(bulk_rows)
            if not bulk_rows or year_bounds is None:
                continue
            api_rows = await _fetch_bulk_equivalence_api_rows(
                source=shard.plan.source,
                shard=shard,
                series_constraints=constraints,
                year_bounds=year_bounds,
                cache=cache,
                policy=policy,
                budget_windows=budget_windows,
                state_lock=state_lock,
                record_result=record_result,
                budget_wait_observer=budget_wait_observer,
            )
            bulk_count, bulk_hash = _equivalence_signature(bulk_rows)
            api_count, api_hash = _equivalence_signature(api_rows)
            match = bulk_count == api_count and bulk_hash == api_hash
            compared += 1
            mismatches += int(not match)
            sample_results.append(
                {
                    "series": constraints,
                    "bulk_count": bulk_count,
                    "api_count": api_count,
                    "bulk_hash": bulk_hash,
                    "api_hash": api_hash,
                    "match": match,
                }
            )
        mismatch_rate = round((float(mismatches) / max(float(compared), 1.0)) * 100.0, 2)
        write_json(
            manifest_path,
            {
                "status": "ok",
                "source": shard.plan.source,
                "dataset_id": shard.plan.request_dataset_id,
                "dataset_version": shard.dataset_version
                or shard.plan.dataset_version
                or shard.plan.request_dataset_id,
                "series_total": int(total_series),
                "sampled_series": len(sampled),
                "compared_series": int(compared),
                "mismatches": int(mismatches),
                "mismatch_rate": mismatch_rate,
                "blocking": bool(
                    mismatches > 0
                    and _bulk_equivalence_source_is_blocking(config, shard.plan.source)
                ),
                "bulk_url": bulk_url,
                "raw_path": str(raw_path),
                "normalized_path": str(normalized_path),
                "samples": sample_results,
            },
        )
    except Exception as exc:
        logger.warning(
            "Bulk/API equivalence sampling failed for {}/{}: {}",
            shard.plan.source,
            shard.plan.request_dataset_id,
            exc,
        )
        write_json(
            manifest_path,
            {
                "status": "error",
                "source": shard.plan.source,
                "dataset_id": shard.plan.request_dataset_id,
                "dataset_version": shard.dataset_version
                or shard.plan.dataset_version
                or shard.plan.request_dataset_id,
                "series_total": int(total_series),
                "sampled_series": len(sampled),
                "compared_series": int(compared),
                "mismatches": int(mismatches),
                "mismatch_rate": round((float(mismatches) / max(float(compared), 1.0)) * 100.0, 2)
                if compared
                else 0.0,
                "blocking": False,
                "bulk_url": bulk_url,
                "raw_path": str(raw_path),
                "normalized_path": str(normalized_path),
                "error": str(exc),
            },
        )


async def _fetch_remote_bulk_rows(
    shard: ObservationShard,
    *,
    cache: _ConnectorSessionCache,
    config: DatasetBatchConfig,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    record_result: Any | None = None,
    budget_wait_observer: Any | None = None,
) -> list[dict[str, Any]]:
    materialized = await _ensure_remote_bulk_materialized(
        shard=shard,
        config=config,
        record_result=record_result,
    )
    normalized_path = Path(materialized["normalized_path"])
    raw_path = Path(materialized["raw_path"])
    await _ensure_bulk_equivalence_manifest(
        shard=shard,
        config=config,
        normalized_path=normalized_path,
        raw_path=raw_path,
        bulk_url=str(materialized.get("bulk_url") or ""),
        cache=cache,
        policy=policy,
        budget_windows=budget_windows,
        state_lock=state_lock,
        record_result=record_result,
        budget_wait_observer=budget_wait_observer,
    )
    return _bulk_query_rows(
        source=shard.plan.source,
        normalized_path=normalized_path,
        filters=shard.filters,
        countries=_shard_countries(shard, config=config),
        year_range=(int(shard.start_year), int(shard.end_year)),
    )


def _load_wvs_bulk_rows(
    raw_variable: str,
    *,
    country_scope: str = "core_blocking",
    year_window: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    indicator = str(raw_variable or "").strip().upper()
    csv_path = _wvs_bulk_csv_path()
    if not indicator:
        return []
    if not csv_path.exists():
        raise RuntimeError(f"WVS bulk CSV is required for production ingest: {csv_path}")

    target_countries = {
        iso2_to_iso3(country)
        for country in country_scope_members(country_scope)
        if iso2_to_iso3(country)
    }
    aggregates: dict[tuple[str, int, int | None], _WVSObservationAccumulator] = {}

    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            country_iso3 = str(row.get("COUNTRY_ALPHA") or "").strip().upper()
            if country_iso3 not in target_countries:
                continue
            country_code = _normalize_country_code(country_iso3)
            if not country_code:
                continue

            survey_year = _as_int(row.get("S020"))
            if survey_year is None:
                continue
            if year_window is not None and not (year_window[0] <= survey_year <= year_window[1]):
                continue
            wave = _as_int(row.get("S002VS"))
            value = _normalize_wvs_response_value(indicator, row.get(indicator))
            if value is None:
                continue
            weight_value, weight_field = _wvs_weight(row)
            if weight_value is None:
                continue

            key = (country_code, survey_year, wave)
            bucket = aggregates.setdefault(key, _WVSObservationAccumulator())
            bucket.sample_size += 1
            bucket.weighted_total += weight_value
            bucket.weighted_value += weight_value * value
            if not bucket.weight_field:
                bucket.weight_field = weight_field

    rows: list[dict[str, Any]] = []
    aggregation_method = _wvs_aggregation_method(indicator)
    for (country_code, survey_year, wave), bucket in sorted(aggregates.items()):
        if bucket.sample_size <= 0 or bucket.weighted_total <= 0:
            continue
        rows.append(
            {
                "country_code": country_code,
                "survey_year": survey_year,
                "wave": wave,
                "value": bucket.weighted_value / bucket.weighted_total,
                "sample_size": bucket.sample_size,
                "weighted_sample_size": round(bucket.weighted_total, 6),
                "sample_weight_field": bucket.weight_field,
                "aggregation_method": aggregation_method,
                "data_shape": "survey_repeated_cross_section",
                "observation_grain": "country_survey_year_wave",
            }
        )
    return rows


def _normalize_wvs_response_value(indicator: str, raw_value: Any) -> float | None:
    value = _as_float(raw_value)
    if value is None:
        return None
    if indicator == "A165":
        if int(value) not in {1, 2}:
            return None
        return 1.0 if int(value) == 1 else 0.0
    if value <= 0:
        return None
    return value


def _wvs_weight(row: dict[str, Any]) -> tuple[float | None, str]:
    for field in _WVS_WEIGHT_FIELDS:
        value = _as_float(row.get(field))
        if value is None or value <= 0:
            continue
        return value, field
    return 1.0, ""


def _normalize_observation_row(
    row: dict[str, Any],
) -> tuple[str, int | None, int | None, int | None, float, str] | None:
    payload = dict(row)
    dimensions = _load_json_dict(payload.pop("dimensions_json", None))
    condition = {**dimensions}
    country_code = _normalize_country_code(
        payload.pop("country_code", None)
        or payload.pop("country", None)
        or payload.pop("COUNTRY", None)
        or payload.pop("REF_AREA", None)
        or payload.pop("ref_area", None)
        or payload.pop("geo", None)
        or payload.pop("GEO", None)
        or payload.pop("geoUnit", None)
        or payload.pop("geography", None)
        or payload.pop("locationId", None)
        or payload.pop("LocationId", None)
        or payload.pop("GeoAreaName", None)
        or payload.pop("SpatialDim", None)
        or dimensions.get("geo")
        or dimensions.get("country")
        or dimensions.get("REF_AREA")
        or dimensions.get("ref_area")
        or dimensions.get("geoUnit")
    )
    if not country_code:
        return None

    survey_year = _as_int(payload.pop("survey_year", None) or payload.pop("SurveyYear", None))
    wave = _as_int(payload.pop("wave", None) or payload.pop("Wave", None))

    raw_year = (
        payload.pop("year", None)
        or payload.pop("Year", None)
        or payload.pop("TIME_PERIOD", None)
        or payload.pop("time_period", None)
        or payload.pop("time", None)
        or payload.pop("TimeDim", None)
        or payload.pop("timeLabel", None)
        or dimensions.get("TIME_PERIOD")
        or dimensions.get("time")
        or dimensions.get("TimeDim")
    )
    year = _extract_year(raw_year)
    if year is None and survey_year is not None:
        year = survey_year

    raw_value = None
    for key in (
        "value",
        "Value",
        "NumericValue",
        "observation",
        "Observation",
        "obs_value",
        "ObsValue",
    ):
        if key in payload:
            raw_value = payload.pop(key)
            break
    if raw_value is None:
        for key, value in list(payload.items()):
            if "value" in key.lower():
                raw_value = payload.pop(key)
                break
    value = _as_float(raw_value)
    if value is None:
        return None
    # Reject NaN/Inf and obviously invalid years
    if math.isnan(value) or math.isinf(value):
        return None
    if year is not None and (year < 1900 or year > 2030):
        return None
    if survey_year is not None and (survey_year < 1900 or survey_year > 2030):
        return None

    unit_value = (
        payload.get("unit")
        or payload.get("UNIT")
        or dimensions.get("unit")
        or dimensions.get("UNIT")
    )
    for ignored in ("dataset_id", "observation_index", "unit", "UNIT", "__country_code"):
        payload.pop(ignored, None)
    if unit_value not in (None, "", [], {}):
        condition.setdefault("unit", unit_value)
    for key, item_value in payload.items():
        if item_value in (None, "", [], {}):
            continue
        condition[key] = item_value
    return (
        country_code,
        year,
        survey_year,
        wave,
        value,
        json.dumps(condition, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


async def _fetch_who_observations(
    *,
    indicator_id: str,
    country_code: str,
    start_year: int,
    end_year: int,
) -> list[dict[str, Any]]:
    iso3 = _to_iso3(country_code)
    url = f"https://ghoapi.azureedge.net/api/{indicator_id}"
    params = {
        "$filter": f"SpatialDim eq '{iso3}' and TimeDim ge {int(start_year)} and TimeDim le {int(end_year)}",
    }
    payload = await _http_get_json(url, params=params)
    return _records_from_payload(payload)


async def _fetch_unpd_observations(
    *,
    indicator_id: str,
    country_code: str,
    start_year: int,
    end_year: int,
) -> list[dict[str, Any]]:
    token = os.getenv("POLISYOS_UNPD_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("POLISYOS_UNPD_API_TOKEN is required for UNPD observation ingest")
    location_id = _country_to_numeric(country_code)
    url = (
        "https://population.un.org/dataportalapi/api/v1/data/indicators/"
        f"{indicator_id}/locations/{location_id}/start/{int(start_year)}/end/{int(end_year)}"
    )
    payload = await _http_get_json(url, headers={"Authorization": f"Bearer {token}"})
    return _records_from_payload(payload)


async def _fetch_uis_observations(
    *,
    indicator_id: str,
    country_code: str,
    start_year: int,
    end_year: int,
) -> list[dict[str, Any]]:
    url = "https://api.uis.unesco.org/api/public/data/indicators"
    params = {
        "indicator": indicator_id,
        "geoUnit": _to_iso3(country_code),
        "start": int(start_year),
        "end": int(end_year),
    }
    payload = await _http_get_json(url, params=params)
    return _records_from_payload(payload)


async def _http_get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    timeout = aiohttp.ClientTimeout(total=60)
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    async with aiohttp.ClientSession(timeout=timeout, headers=request_headers) as session:
        async with session.get(url, params=params) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status} for {url}")
            return await resp.json(content_type=None)


def _sdmx_filters_for_country(
    country_code: str, *, base_filters: dict[str, list[str]]
) -> dict[str, list[str]]:
    iso3 = _to_iso3(country_code)
    merged = {key: list(values) for key, values in (base_filters or {}).items()}
    for key, value in (
        ("geo", country_code),
        ("country", country_code),
        ("ref_area", iso3),
        ("REF_AREA", iso3),
    ):
        merged.setdefault(key, [value])
    return merged


def _sdmx_filters_for_countries(
    country_codes: tuple[str, ...],
    *,
    base_filters: dict[str, list[str]],
) -> dict[str, list[str]]:
    merged = {key: list(values) for key, values in (base_filters or {}).items()}
    iso2_values = [str(value).strip().upper() for value in country_codes if str(value).strip()]
    iso3_values = [_to_iso3(value) for value in iso2_values]
    if iso2_values:
        merged["geo"] = iso2_values
        merged["country"] = iso2_values
    if iso3_values:
        merged["ref_area"] = iso3_values
        merged["REF_AREA"] = iso3_values
    return merged


def _eurostat_filters_for_country(
    country_code: str, *, base_filters: dict[str, list[str]]
) -> dict[str, list[str]]:
    merged = {key: list(values) for key, values in (base_filters or {}).items()}
    merged["geo"] = [country_code]
    return merged


def _eurostat_filters_for_countries(
    country_codes: tuple[str, ...],
    *,
    base_filters: dict[str, list[str]],
) -> dict[str, list[str]]:
    merged = {key: list(values) for key, values in (base_filters or {}).items()}
    values = [str(value).strip().upper() for value in country_codes if str(value).strip()]
    if values:
        merged["geo"] = values
    return merged


def _strip_geo_filters(filters: dict[str, list[str]]) -> dict[str, list[str]]:
    blocked = {"geo", "country", "ref_area", "REF_AREA"}
    return {key: list(values) for key, values in (filters or {}).items() if key not in blocked}


def _observation_countries(source: str, *, config: DatasetBatchConfig) -> tuple[str, ...]:
    countries = config.resolved_active_countries
    if config.preflight_only or config.run_profile == "preflight_core":
        return countries[:1]
    if config.is_sampled_run and source in {"eurostat", "oecd", "ilo"}:
        return countries[:1]
    return countries


def _shard_countries(shard: ObservationShard, *, config: DatasetBatchConfig) -> tuple[str, ...]:
    if shard.country_codes:
        return shard.country_codes
    if shard.country_code:
        return (shard.country_code,)
    return _observation_countries(shard.plan.source, config=config)


def _observation_frequency_rank(update_frequency: str) -> int:
    value = str(update_frequency or "").strip().lower()
    if not value:
        return 2
    if "wave" in value or "survey" in value or "annual" in value or value == "a":
        return 0
    if "quarter" in value or value.startswith("q"):
        return 1
    if "month" in value or value.startswith("m"):
        return 2
    if "week" in value or value.startswith("w"):
        return 3
    if "day" in value or value.startswith("d"):
        return 4
    return 2


def _observation_payload_row_limit(plan: ObservationPlan) -> int | None:
    source = str(plan.source or "").strip().lower()
    if source not in {"eurostat", "oecd", "ilo"}:
        return None
    frequency_rank = _observation_frequency_rank(plan.update_frequency)
    if frequency_rank >= 4:
        return 25_000
    if frequency_rank == 3:
        return 50_000
    if frequency_rank == 2:
        return 100_000
    if frequency_rank == 1:
        return 150_000
    return 200_000


def _filters_to_tuple(filters: dict[str, list[str]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple((key, tuple(values)) for key, values in sorted(filters.items()))


def _dedupe_filter_values(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _preferred_sdmx_geo_key(
    source: str,
    *,
    capability_snapshot: DatasetCapabilitySnapshot | None = None,
) -> str:
    if capability_snapshot is not None:
        for key in capability_snapshot.dimension_order or ():
            normalized = str(key or "").strip()
            if normalized.lower() in {"geo", "country", "ref_area"}:
                return normalized
    if source == "ilo":
        return "REF_AREA"
    return "geo"


def _apply_dimension_order_to_snapshot(
    *,
    source: str,
    dataset_id: str,
    capability_snapshot: DatasetCapabilitySnapshot | None,
    dimension_order: tuple[str, ...] | None = None,
) -> DatasetCapabilitySnapshot | None:
    normalized = _normalize_dimension_order(dimension_order or ())
    if not normalized and str(source or "").strip().lower() == "ilo":
        normalized = _infer_ilo_dimension_order(dataset_id)
    if not normalized:
        return capability_snapshot
    if capability_snapshot is not None:
        if _normalize_dimension_order(capability_snapshot.dimension_order) == normalized:
            return capability_snapshot
        return capability_snapshot.model_copy(update={"dimension_order": normalized})
    return DatasetCapabilitySnapshot(
        source=str(source or ""),
        dataset_id=str(dataset_id or ""),
        resolved_dataset_id=str(dataset_id or ""),
        preferred_transport="default",
        dimension_order=normalized,
        last_checked_at=datetime.now(UTC),
    )


def _canonicalize_observation_request_filters(
    *,
    source: str,
    filters: dict[str, list[str]],
    capability_snapshot: DatasetCapabilitySnapshot | None = None,
) -> dict[str, list[str]]:
    canonical = {
        str(key): _dedupe_filter_values(list(values)) for key, values in (filters or {}).items()
    }
    if source != "ilo":
        return {key: values for key, values in canonical.items() if values}

    geo_key = _preferred_sdmx_geo_key(source, capability_snapshot=capability_snapshot)
    geo_values: list[str] = []
    for key in ("REF_AREA", "ref_area"):
        geo_values.extend(
            str(value).strip().upper() for value in canonical.get(key, []) if str(value).strip()
        )
    for key in ("country", "geo"):
        geo_values.extend(
            _to_iso3(str(value).strip().upper())
            for value in canonical.get(key, [])
            if str(value).strip()
        )
    geo_values = _dedupe_filter_values(geo_values)
    for key in ("REF_AREA", "ref_area", "country", "geo"):
        canonical.pop(key, None)
    if geo_values:
        canonical[geo_key] = geo_values
    return {key: values for key, values in canonical.items() if values}


def _build_sdmx_dimension_key(
    *,
    filters: tuple[tuple[str, tuple[str, ...]], ...],
    capability_snapshot: DatasetCapabilitySnapshot | None,
) -> str | None:
    if capability_snapshot is None or not capability_snapshot.dimension_order:
        return None
    remaining = OrderedDict(
        (
            str(key),
            tuple(str(value).strip() for value in values if str(value).strip()),
        )
        for key, values in filters
        if str(key).strip()
    )
    if not remaining:
        return None
    parts: list[str] = []
    matched = False
    for dimension in capability_snapshot.dimension_order:
        match_key = next(
            (key for key in remaining if key.lower() == str(dimension or "").strip().lower()),
            None,
        )
        if match_key is None:
            parts.append("")
            continue
        values = remaining.pop(match_key)
        parts.append("+".join(values))
        matched = matched or bool(values)
    if not matched or remaining:
        return None
    return ".".join(parts)


def _rewrite_sdmx_requests_with_dimension_key(
    requests: list[FetchRequest],
    *,
    capability_snapshot: DatasetCapabilitySnapshot | None,
) -> list[FetchRequest]:
    if capability_snapshot is None or not capability_snapshot.dimension_order:
        return requests
    rewritten: list[FetchRequest] = []
    for request in requests:
        key = _build_sdmx_dimension_key(
            filters=request.filters,
            capability_snapshot=capability_snapshot,
        )
        if not key:
            rewritten.append(request)
            continue
        rewritten.append(replace(request, filters=(("key", (key,)),)))
    return rewritten


def _load_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall((text or "").lower()) if token}


def _normalize_country_code(value: Any) -> str:
    return normalize_country_code(value)


def _to_iso3(country_code: str) -> str:
    return iso2_to_iso3(country_code)


def _country_to_numeric(country_code: str) -> str:
    return iso2_to_numeric(country_code)


def _filter_wvs_bulk_rows(
    rows: list[dict[str, Any]],
    *,
    countries: tuple[str, ...],
    year_range: tuple[int, int],
) -> list[dict[str, Any]]:
    allowed = {normalize_country_code(country) for country in countries}
    start_year, end_year = year_range
    filtered: list[dict[str, Any]] = []
    for row in rows:
        country = normalize_country_code(row.get("country_code"))
        survey_year = _as_int(row.get("survey_year"))
        if allowed and country not in allowed:
            continue
        if survey_year is None or survey_year < start_year or survey_year > end_year:
            continue
        filtered.append(dict(row))
    return filtered


def _extract_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return _as_int(text)
    return int(match.group(0))


def _observation_id(
    dataset_id: str,
    raw_variable: str,
    canonical_var: str,
    country_code: str,
    *,
    year: int | None,
    survey_year: int | None,
    wave: int | None,
    condition_json: str,
) -> str:
    condition_hash = hashlib.sha256((condition_json or "{}").encode("utf-8")).hexdigest()[:12]
    text = (
        f"{dataset_id}|{raw_variable}|{canonical_var}|{country_code}|"
        f"{year}|{survey_year}|{wave}|{condition_hash}"
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["CoreSourcesIngestStats", "run_core_sources_ingest"]
