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




def _seed_alignments_path() -> Path:
    return (
        Path(__file__).resolve().parents[7]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )


def _wvs_raw_dir() -> Path:
    return Path(__file__).resolve().parents[7] / "data" / "raw" / "wvs"


def _wvs_bulk_csv_path() -> Path:
    return _wvs_raw_dir() / "WVS_Time_Series_1981-2022_csv_v5_0.csv"


def _wvs_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[7]
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
