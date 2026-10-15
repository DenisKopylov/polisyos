"""Stage 0b: ingest transportability sources into registry/alignment/observation tables."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import OrderedDict
from dataclasses import replace
from datetime import UTC, datetime
from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast, overload

import aiohttp

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CORE_SOURCES_COMPATIBILITY_BINDINGS,
    resolve_core_sources_compatibility_binding,
)
from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
    iso2_to_iso3,
    iso2_to_numeric,
    normalize_country_code,
)
from polisyos.data_forge.read_api.academic import CANONICAL_VARIABLES
from polisyos.fabric.connectors.base import (
    DatasetCapabilitySnapshot,
    FetchRequest,
)

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable, Iterable, Mapping

    from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
        ObservationPlan,
        ObservationShard,
    )
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


# This finite declaration drives proxy creation, admission, and owner target identity.
__OWNER_PROXY_BINDINGS: Mapping[tuple[str, str], tuple[str, str]] = MappingProxyType(
    {
        ("loaders", "_records_from_payload"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.loaders",
            "_records_from_payload",
        ),
        ("writers", "_infer_ilo_dimension_order"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_infer_ilo_dimension_order",
        ),
        ("writers", "_normalize_dimension_order"): (
            "polisyos.data_forge.domains.catalog.batch.core_sources.writers",
            "_normalize_dimension_order",
        ),
    }
)
_P = ParamSpec("_P")
_R = TypeVar("_R")


@overload
def __resolve_implementation_dependency[DependencyValueT](
    name: str, owner: str, fallback: DependencyValueT
) -> DependencyValueT: ...


@overload
def __resolve_implementation_dependency(name: str, owner: str) -> object: ...


def __resolve_implementation_dependency(name: str, owner: str, fallback: object = None) -> object:
    """Resolve only source-declared owner dependencies.

    ``fallback`` is a static type witness only. Context and developer override
    values are not runtime-validated and must satisfy the owner contract.
    """
    binding_key = (owner, name)
    if binding_key in CORE_SOURCES_COMPATIBILITY_BINDINGS:
        target_module_name, target_name = CORE_SOURCES_COMPATIBILITY_BINDINGS[binding_key]
    elif binding_key in __OWNER_PROXY_BINDINGS:
        target_module_name, target_name = __OWNER_PROXY_BINDINGS[binding_key]
    else:
        raise LookupError(f"unsupported core-sources dependency binding: {binding_key!r}")

    if binding_key in __OWNER_PROXY_BINDINGS:
        proxy_module_name, proxy_target_name = __OWNER_PROXY_BINDINGS[binding_key]
        if (target_module_name, target_name) != (proxy_module_name, proxy_target_name):
            raise RuntimeError(f"inconsistent core-sources dependency binding: {binding_key!r}")

    has_context_override, context_override = resolve_core_sources_compatibility_binding(
        target_module_name, target_name
    )
    if has_context_override:
        return cast("object", context_override)
    if binding_key in __OWNER_PROXY_BINDINGS:
        _proxy_module_name, proxy_target_name = __OWNER_PROXY_BINDINGS[binding_key]
        override = globals().get(proxy_target_name)
        if override is not None and override is not __OWNER_BOUND_PROXIES[binding_key]:
            return override
    module = import_module(target_module_name)
    return getattr(module, target_name)


def __build_implementation_proxy(name: str, owner: str) -> Callable[_P, _R]:
    """Build a lazy callable for one source-declared owner binding."""

    def __proxy(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        target = cast("Callable[_P, _R]", __resolve_implementation_dependency(name, owner))
        return target(*args, **kwargs)

    return __proxy


__OWNER_BOUND_PROXIES: Mapping[tuple[str, str], object] = MappingProxyType(
    {
        binding_key: __build_implementation_proxy(binding_key[1], binding_key[0])
        for binding_key in __OWNER_PROXY_BINDINGS
    }
)
for __binding_key, __implementation_proxy in __OWNER_BOUND_PROXIES.items():
    __target_module, __target_name = __OWNER_PROXY_BINDINGS[__binding_key]
    globals().setdefault(__target_name, __implementation_proxy)

_records_from_payload: Callable[[object], list[dict[str, Any]]] = cast(
    "Callable[[object], list[dict[str, Any]]]",
    __OWNER_BOUND_PROXIES[("loaders", "_records_from_payload")],
)
_infer_ilo_dimension_order: Callable[[str], tuple[str, ...]] = cast(
    "Callable[[str], tuple[str, ...]]",
    __OWNER_BOUND_PROXIES[("writers", "_infer_ilo_dimension_order")],
)
_normalize_dimension_order: Callable[[Iterable[object] | None], tuple[str, ...]] = cast(
    "Callable[[Iterable[object] | None], tuple[str, ...]]",
    __OWNER_BOUND_PROXIES[("writers", "_normalize_dimension_order")],
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

    survey_year = __resolve_implementation_dependency("_as_int", "transformers", _as_int)(
        payload.pop("survey_year", None) or payload.pop("SurveyYear", None)
    )
    wave = __resolve_implementation_dependency("_as_int", "transformers", _as_int)(
        payload.pop("wave", None) or payload.pop("Wave", None)
    )

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
        for key, _value in list(payload.items()):
            if "value" in key.lower():
                raw_value = payload.pop(key)
                break
    value = __resolve_implementation_dependency("_as_float", "transformers", _as_float)(raw_value)
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
    iso3 = __resolve_implementation_dependency("_to_iso3", "transformers", _to_iso3)(country_code)
    url = f"https://ghoapi.azureedge.net/api/{indicator_id}"
    params = {
        "$filte\
r": f"SpatialDim eq '{iso3}' and TimeDim ge {int(start_year)} and TimeDim le {int(end_year)}",
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
        "geoUnit": __resolve_implementation_dependency("_to_iso3", "transformers", _to_iso3)(
            country_code
        ),
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
) -> object:
    timeout = aiohttp.ClientTimeout(total=60)
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    async with (
        aiohttp.ClientSession(timeout=timeout, headers=request_headers) as session,
        session.get(url, params=params) as resp,
    ):
        if resp.status >= 400:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return await resp.json(content_type=None)


def _sdmx_filters_for_country(
    country_code: str, *, base_filters: dict[str, list[str]]
) -> dict[str, list[str]]:
    iso3 = __resolve_implementation_dependency("_to_iso3", "transformers", _to_iso3)(country_code)
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
    iso3_values = [
        __resolve_implementation_dependency("_to_iso3", "transformers", _to_iso3)(value)
        for value in iso2_values
    ]
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
            __resolve_implementation_dependency("_to_iso3", "transformers", _to_iso3)(
                str(value).strip().upper()
            )
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


def _load_json_dict(value: object) -> dict[str, Any]:
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


def _normalize_country_code(value: object) -> str:
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
        survey_year = __resolve_implementation_dependency("_as_int", "transformers", _as_int)(
            row.get("survey_year")
        )
        if allowed and country not in allowed:
            continue
        if survey_year is None or survey_year < start_year or survey_year > end_year:
            continue
        filtered.append(dict(row))
    return filtered


def _extract_year(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return __resolve_implementation_dependency("_as_int", "transformers", _as_int)(text)
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


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
