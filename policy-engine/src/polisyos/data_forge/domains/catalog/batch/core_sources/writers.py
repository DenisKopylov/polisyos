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
