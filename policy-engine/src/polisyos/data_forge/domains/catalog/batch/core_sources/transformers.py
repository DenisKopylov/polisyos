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
