"""Stage 2: Normalize raw source payloads to a DCAT-like canonical form."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.common.logger import get_logger
from polisyos.datasets.batch.ckan_curation import curate_ckan_package, guess_ckan_resource_format
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.source_registry import SourceSpec
from polisyos.datasets.knowledge.types import (
    DatasetAccess,
    DatasetCoverage,
    DatasetQuality,
    DatasetRecord,
    DistributionRecord,
)
from polisyos.datasets.metrics_map import load_metrics_map

logger = get_logger(__name__)

_INDICATOR_RE = re.compile(
    r"\b(GDP|GNP|CPI|PPI|HDI|unemployment|inflation|poverty|gini|population|fertility|mortality|"
    r"import|export|trade|debt|deficit|surplus|revenue|expenditure|literacy|enrollment|CO2|emissions|energy)\b",
    re.IGNORECASE,
)

_CONNECTOR_ALIASES = {
    "sdmx": "sdmx.source",
    "worldbank": "worldbank.wdi",
    "ukons": "ukons.datasets",
    "wvs": "wvs.wave7",
    "who": "who.indicators",
    "unpd": "unpd.data",
    "unesco_uis": "unesco_uis.data",
    "opendatasoft": "opendatasoft.ods",
    "socrata": "socrata.soda",
    "sparql": "sparql.endpoint",
    "rest_json": "rest.json",
}
_MACHINE_READABLE_FORMATS = {
    "CSV",
    "JSON",
    "SDMX-JSON",
    "XLSX",
    "XLS",
    "ODS",
    "PARQUET",
}
_PARSER_SUPPORTED_FORMATS = {"CSV", "JSON", "SDMX-JSON", "XLSX", "XLS", "ODS", "ZIP"}
_FORMAT_MEDIA_TYPES = {
    "CSV": "text/csv",
    "JSON": "application/json",
    "SDMX-JSON": "application/vnd.sdmx.data+json",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "XLS": "application/vnd.ms-excel",
    "ODS": "application/vnd.oasis.opendocument.spreadsheet",
    "ZIP": "application/zip",
}
_TIME_COLUMN_HINTS = ("time", "year", "date", "period")
_GEO_COLUMN_HINTS = ("country", "geo", "region", "territory", "area", "geography")
_HEURISTIC_METRIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gdp_per_capita", ("gdp per capita", "gross domestic product per capita", "ввп на душу")),
    ("gdp", ("gross domestic product", " gdp ", "ввп")),
    ("unemployment_rate", ("unemployment", "jobless", "безробіт", "somaj", "șomaj", "bezroboc", "rynek pracy")),
    ("inflation", ("inflation", "consumer price", "cpi", "інфляц", "inflatie", "inflație", "inflacja")),
    ("poverty_rate", ("poverty", "deprivation", "бідн", "saracie", "sărăcie")),
    ("labor_force_participation", ("labor force participation", "labour force participation", "робочій силі")),
    ("migration", ("migration", "migrant", "refugee", "міграц", "migratie", "migrație", "demograf", "demografie", "migrac", "demografi")),
    ("health_outcomes", ("life expectancy", "healthy life expectancy", "mortality", "тривалість життя", "здоров", "sanat", "sănătate", "spital", "zdrow", "szpital")),
    ("education_outcomes", ("education", "enrollment", "enrolment", "school", "literacy", "освіт", "зарахув", "educat", "școal", "scoala", "elev", "edukac", "szkol", "uczni")),
    ("social_trust", ("social trust", "trust survey", "довір")),
    ("institutional_quality", ("rule of law", "government effectiveness", "regulatory quality", "institutional quality", "guvern", "administratie", "administrație", "administrac", "rząd")),
)


def _fallback_source_spec(source: str, *, endpoint: str = "", execution_tier: str = "catalog") -> SourceSpec:
    return SourceSpec(
        name=source,
        family=source,
        wave="Z",
        endpoint=endpoint or source,
        connector_id="",
        profile_id="",
        execution_tier=execution_tier,
        run_lane="catalog" if execution_tier == "catalog" else "empirical",
        publish_blocking=False,
    )


def _stable_id(*parts: str, size: int = 20) -> str:
    canon = "|".join(parts)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:size]


def _distribution_id(dataset_id: str, url: str, fmt: str) -> str:
    return _stable_id(dataset_id, url, fmt)


def _canonical_connector_id(connector_id: str, *, spec: SourceSpec | None = None) -> str:
    candidate = (spec.connector_id if spec and spec.connector_id else connector_id or "").strip()
    return _CONNECTOR_ALIASES.get(candidate, candidate)


def _normalize_format(fmt: str, url: str = "") -> str:
    value = (fmt or "").strip().upper()
    if value:
        return value
    url_lc = (url or "").lower()
    for suffix, detected in (
        (".csv", "CSV"),
        (".json", "JSON"),
        (".xlsx", "XLSX"),
        (".xls", "XLS"),
        (".ods", "ODS"),
        (".zip", "ZIP"),
    ):
        if url_lc.endswith(suffix):
            return detected
    return ""


def _guess_media_type(fmt: str, url: str = "") -> str:
    normalized = _normalize_format(fmt, url)
    return _FORMAT_MEDIA_TYPES.get(normalized, "")


def _extract_last_updated(raw: dict) -> str | None:
    for key in (
        "metadata_modified",
        "modified",
        "updated",
        "last_updated",
        "lastDataUpdate",
        "revision_timestamp",
        "dateLastUpdated",
        "changed",
    ):
        value = raw.get(key)
        if value:
            return str(value)
    return None


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[;,|]", value) if part.strip()]
        return parts
    return []


def _infer_source_locator(
    *,
    record: DatasetRecord,
    distribution: DistributionRecord,
    connector_id: str,
) -> str:
    params = distribution.connector_params
    if distribution.source_locator:
        return distribution.source_locator
    if connector_id == "ckan.resource":
        package_id = str(params.get("package_id") or record.dataset_id or record.source_dataset_id or "").strip()
        resource_id = str(params.get("resource_id") or "").strip()
        if package_id and resource_id:
            return f"{package_id}/{resource_id}"
        if distribution.url:
            return distribution.url
    if connector_id == "worldbank.wdi":
        indicator_id = str(params.get("indicator_id") or record.dataset_id or record.source_dataset_id or "").strip()
        return indicator_id
    if connector_id in {
        "ukons.datasets",
        "eurostat.data",
        "sdmx.source",
        "wvs.wave7",
        "who.indicators",
        "unpd.data",
        "unesco_uis.data",
        "opendatasoft.ods",
        "socrata.soda",
        "sparql.endpoint",
    }:
        return str(
            params.get("dataset_id")
            or params.get("dataflow_id")
            or params.get("indicator_id")
            or params.get("location_id")
            or record.dataset_id
            or record.source_dataset_id
            or ""
        ).strip()
    if connector_id == "rest.json" and params.get("url"):
        return str(params["url"]).strip()
    return distribution.url or record.dataset_id or record.source_dataset_id or ""


def _is_machine_readable(connector_id: str, fmt: str) -> bool:
    if connector_id in {
        "worldbank.wdi",
        "ukons.datasets",
        "eurostat.data",
        "sdmx.source",
        "wvs.wave7",
        "who.indicators",
        "unpd.data",
        "unesco_uis.data",
        "opendatasoft.ods",
        "socrata.soda",
        "sparql.endpoint",
    }:
        return True
    return _normalize_format(fmt) in _MACHINE_READABLE_FORMATS


def _is_parser_supported(connector_id: str, fmt: str) -> bool:
    normalized = _normalize_format(fmt)
    if connector_id in {
        "worldbank.wdi",
        "ukons.datasets",
        "eurostat.data",
        "sdmx.source",
        "wvs.wave7",
        "who.indicators",
        "unpd.data",
        "unesco_uis.data",
        "opendatasoft.ods",
        "socrata.soda",
        "sparql.endpoint",
    }:
        return True
    if connector_id == "ckan.resource":
        return normalized in _PARSER_SUPPORTED_FORMATS
    if connector_id == "rest.json":
        return normalized == "JSON"
    return False


def _distribution_quality(
    *,
    machine_readable: bool,
    parser_supported: bool,
    fmt: str,
) -> float:
    score = 0.2
    if machine_readable:
        score += 0.3
    if parser_supported:
        score += 0.35
    if _normalize_format(fmt) in {"CSV", "JSON", "SDMX-JSON", "XLSX", "XLS", "ODS", "ZIP"}:
        score += 0.15
    return round(min(score, 1.0), 4)


def _description_score(text: str) -> float:
    return 1.0 if text.strip() else 0.0


def _freshness_score(last_updated: str | None) -> float:
    return 0.8 if last_updated else 0.35


def _source_update_frequency(source: str, spec: SourceSpec | None) -> str:
    if spec and spec.update_frequency:
        return spec.update_frequency
    defaults = {
        "worldbank": "annual",
        "wvs": "irregular",
        "eurostat": "monthly",
        "oecd": "quarterly",
        "ilo": "monthly",
        "ukons": "monthly",
        "data_gov_ua": "irregular",
        "data_gov_ua_broad": "irregular",
        "data_gov_ua_exec": "irregular",
        "data_gov_ro_broad": "irregular",
        "data_gov_ro_exec": "irregular",
        "data_gov_md_broad": "irregular",
        "data_gov_md_exec": "irregular",
        "data_gov_pl_broad": "irregular",
        "data_gov_pl_exec": "irregular",
        "opendatasoft_public": "weekly",
        "paris_opendata_exec": "weekly",
        "nyc_opendata": "weekly",
        "nyc_opendata_exec": "weekly",
        "chicago_opendata": "weekly",
        "chicago_opendata_exec": "weekly",
        "wikidata_sparql": "weekly",
        "dbpedia_sparql": "weekly",
        "openaq_v2": "daily",
        "open_meteo": "daily",
        "eia_api": "monthly",
    }
    return defaults.get(source, "")


def _canonical_countries(spatial: str) -> list[str]:
    value = (spatial or "").strip().upper()
    if not value or value in {"WORLD", "GLOBAL"}:
        return []
    if len(value) <= 3 and value.isalpha():
        return [value]
    return []


def _with_execution_metadata(
    record: DatasetRecord,
    *,
    raw: dict,
    spec: SourceSpec | None,
) -> DatasetRecord:
    distributions: list[DistributionRecord] = []
    parser_supported_total = 0
    machine_readable_total = 0
    for dist in record.distributions:
        dist_connector = _canonical_connector_id(dist.connector_type, spec=spec)
        normalized_format = _normalize_format(dist.format, dist.url)
        machine_readable = dist.machine_readable or _is_machine_readable(dist_connector, normalized_format)
        parser_supported = dist.parser_supported or _is_parser_supported(dist_connector, normalized_format)
        parser_supported_total += int(parser_supported)
        machine_readable_total += int(machine_readable)
        params = dict(dist.connector_params or {})
        if dist_connector == "ckan.resource":
            params.setdefault("package_id", record.dataset_id or record.source_dataset_id)
            params.setdefault("resource_id", params.get("resource_id", ""))
            if dist.url:
                params.setdefault("url", dist.url)
        source_locator = _infer_source_locator(record=record, distribution=dist, connector_id=dist_connector)
        distributions.append(
            dist.model_copy(
                update={
                    "format": normalized_format,
                    "connector_type": dist_connector or dist.connector_type,
                    "connector_params": params,
                    "source_locator": source_locator,
                    "profile_id": dist.profile_id or (spec.profile_id if spec else ""),
                    "media_type": dist.media_type or _guess_media_type(normalized_format, dist.url),
                    "machine_readable": machine_readable,
                    "parser_supported": parser_supported,
                    "quality_score": dist.quality_score or _distribution_quality(
                        machine_readable=machine_readable,
                        parser_supported=parser_supported,
                        fmt=normalized_format,
                    ),
                }
            )
        )

    best_distribution = None
    if distributions:
        best_distribution = sorted(
            distributions,
            key=lambda item: (
                0 if item.id == record.preferred_distribution_id else 1,
                -int(item.parser_supported),
                -int(item.machine_readable),
                -item.quality_score,
                item.id,
            ),
        )[0]

    last_updated = record.last_updated or _extract_last_updated(raw)
    description_score = _description_score(record.description)
    machine_readable_score = (machine_readable_total / len(distributions)) if distributions else 0.0
    parser_support_score = (parser_supported_total / len(distributions)) if distributions else 0.0
    freshness_score = _freshness_score(last_updated)
    execution_readiness_score = round(
        (
            description_score * 0.2
            + machine_readable_score * 0.25
            + parser_support_score * 0.35
            + freshness_score * 0.2
        ),
        4,
    )

    base_tier = (spec.execution_tier if spec else record.execution_tier or "catalog").strip() or "catalog"
    metrics_required = bool(spec.metrics_required) if spec else False
    if not distributions or not any(dist.parser_supported for dist in distributions):
        execution_tier = "catalog"
    elif metrics_required and not record.polisyos_metrics:
        execution_tier = "catalog"
    else:
        execution_tier = base_tier

    coverage = record.coverage.model_copy(
        update={
            "countries": record.coverage.countries or _canonical_countries(record.spatial),
            "time_start": record.coverage.time_start or record.temporal_start,
            "time_end": record.coverage.time_end or record.temporal_end,
            "time_range": record.coverage.time_range
            or (
                f"{record.temporal_start}:{record.temporal_end}"
                if record.temporal_start or record.temporal_end
                else ""
            ),
            "granularity": record.coverage.granularity or "annual",
        }
    )
    access = record.access.model_copy(
        update={
            "api_endpoint": record.access.api_endpoint or (spec.endpoint if spec else None),
            "bulk_download_url": record.access.bulk_download_url or (best_distribution.url if best_distribution else None),
            "license": record.access.license or record.license,
            "auth_required": record.access.auth_required,
        }
    )
    quality = record.quality.model_copy(
        update={
            "description_score": description_score,
            "machine_readable_score": round(machine_readable_score, 4),
            "parser_support_score": round(parser_support_score, 4),
            "freshness_score": freshness_score,
            "execution_readiness_score": execution_readiness_score,
        }
    )
    return record.model_copy(
        update={
            "distributions": distributions,
            "source_dataset_id": record.source_dataset_id or record.dataset_id,
            "execution_tier": execution_tier,
            "update_frequency": record.update_frequency or _source_update_frequency(record.source, spec),
            "last_updated": last_updated,
            "coverage": coverage,
            "access": access,
            "quality": quality,
            "preferred_distribution_id": record.preferred_distribution_id or (best_distribution.id if best_distribution else ""),
        }
    )


def extract_variables(raw: dict) -> list[str]:
    variables: list[str] = []
    for key in ("id", "dataset_id", "indicator_id", "indicator_code", "code", "dataflow_id"):
        value = raw.get(key)
        if value:
            variables.append(str(value))

    extras = raw.get("extras")
    if isinstance(extras, list):
        for item in extras:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).lower()
            if key in {"indicator", "variable", "measure"}:
                value = item.get("value")
                if value:
                    variables.append(str(value))

    text = (
        f"{raw.get('title', '')} "
        f"{raw.get('name', '')} "
        f"{raw.get('description', '')} "
        f"{raw.get('notes', '')}"
    )
    for match in _INDICATOR_RE.finditer(text):
        token = match.group(0).upper()
        if token not in variables:
            variables.append(token)
    return variables


def _map_metrics(raw: dict, metrics_map: dict[str, dict] | None) -> list[str]:
    if not metrics_map:
        return []
    text = " ".join(
        str(raw.get(key, "") or "")
        for key in ("title", "name", "description", "Definition", "sourceNote", "notes", "IndicatorName")
    ).lower()
    codes = {str(raw.get(k, "")).upper() for k in ("id", "dataset_id", "indicator_id", "dataflow_id") if raw.get(k)}

    matched: list[str] = []
    hinted = raw.get("harvest_metric_candidates")
    if isinstance(hinted, list):
        for metric_id in hinted:
            metric_text = str(metric_id or "").strip()
            if metric_text and metric_text in metrics_map and metric_text not in matched:
                matched.append(metric_text)
    for metric_id, spec in metrics_map.items():
        keywords = [str(v).lower() for v in spec.get("keywords", [])]
        if any(k in text for k in keywords):
            matched.append(metric_id)
            continue
        for code_key in ("sdmx_concepts", "worldbank_indicators", "eurostat_codes"):
            code_set = {str(v).upper() for v in spec.get(code_key, [])}
            if codes & code_set:
                matched.append(metric_id)
                break
    for metric_id, patterns in _HEURISTIC_METRIC_PATTERNS:
        if metric_id in matched:
            continue
        if any(pattern in text for pattern in patterns):
            matched.append(metric_id)
    return matched


def _normalize_sdmx(raw: dict, *, source: str, metrics_map: dict[str, dict] | None) -> DatasetRecord:
    dataset_id = str(raw.get("id") or raw.get("dataflow_id") or "")
    agency = str(raw.get("agencyID") or raw.get("agency_id") or "")
    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)
    dist = DistributionRecord(
        id=_distribution_id(rid, "", "SDMX-JSON"),
        format="SDMX-JSON",
        connector_type="sdmx",
        connector_params={"dataflow_id": dataset_id, "agency_id": agency},
    )
    return DatasetRecord(
        id=rid,
        title=str(raw.get("name") or dataset_id),
        description=str(raw.get("description") or ""),
        publisher=agency or source,
        variables=extract_variables(raw),
        formats=["SDMX-JSON"],
        distributions=[dist],
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        dedup_key=dedup_key,
    )


def _normalize_worldbank(raw: dict, *, metrics_map: dict[str, dict] | None) -> DatasetRecord:
    dataset_id = str(raw.get("id", ""))
    agency = "WB"
    source = "worldbank"
    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)
    dist = DistributionRecord(
        id=_distribution_id(rid, dataset_id, "JSON"),
        url=f"https://api.worldbank.org/v2/country/all/indicator/{dataset_id}?format=json",
        format="JSON",
        connector_type="worldbank",
        connector_params={"indicator_id": dataset_id},
    )
    return DatasetRecord(
        id=rid,
        title=str(raw.get("name") or dataset_id),
        description=str(raw.get("sourceNote") or ""),
        publisher="World Bank",
        themes=[str((raw.get("source") or {}).get("value", ""))] if isinstance(raw.get("source"), dict) else [],
        variables=extract_variables(raw),
        spatial="WORLD",
        license="CC-BY-4.0",
        formats=["JSON"],
        distributions=[dist],
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        dedup_key=dedup_key,
    )


def _normalize_ukons(raw: dict, *, metrics_map: dict[str, dict] | None) -> DatasetRecord:
    dataset_id = str(raw.get("id") or "")
    source = "ukons"
    agency = "ONS"
    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)
    return DatasetRecord(
        id=rid,
        title=str(raw.get("title") or dataset_id),
        description=str(raw.get("description") or ""),
        publisher="ONS",
        keywords=_coerce_string_list(raw.get("keywords") or []),
        variables=extract_variables(raw),
        formats=["JSON"],
        distributions=[
            DistributionRecord(
                id=_distribution_id(rid, dataset_id, "JSON"),
                format="JSON",
                connector_type="ukons",
                connector_params={"dataset_id": dataset_id},
            )
        ],
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        dedup_key=dedup_key,
    )


def _normalize_indicator_api(
    raw: dict,
    *,
    source: str,
    agency: str,
    endpoint: str,
    connector_type: str,
    metrics_map: dict[str, dict] | None,
) -> DatasetRecord:
    dataset_id = str(
        raw.get("id")
        or raw.get("ID")
        or raw.get("IndicatorCode")
        or raw.get("code")
        or raw.get("Code")
        or raw.get("indicator")
        or raw.get("indicatorCode")
        or ""
    )
    title = str(
        raw.get("name")
        or raw.get("Name")
        or raw.get("title")
        or raw.get("Title")
        or raw.get("IndicatorName")
        or raw.get("description")
        or dataset_id
    )
    description = str(
        raw.get("description")
        or raw.get("Description")
        or raw.get("Definition")
        or raw.get("sourceNote")
        or ""
    )
    data_availability = raw.get("dataAvailability") if isinstance(raw.get("dataAvailability"), dict) else {}
    timeline = data_availability.get("timeLine") if isinstance(data_availability.get("timeLine"), dict) else {}
    time_start = (
        raw.get("sourceStartYear")
        or raw.get("startYear")
        or timeline.get("min")
    )
    time_end = (
        raw.get("sourceEndYear")
        or raw.get("endYear")
        or timeline.get("max")
    )
    countries = _coerce_string_list(raw.get("countries") or [])
    auth_required = connector_type == "unpd"

    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)
    dist = DistributionRecord(
        id=_distribution_id(rid, endpoint, "JSON"),
        url=endpoint,
        format="JSON",
        connector_type=connector_type,
        connector_params={"indicator_id": dataset_id},
    )
    return DatasetRecord(
        id=rid,
        title=title,
        description=description,
        publisher=agency,
        variables=extract_variables(raw),
        formats=["JSON"],
        distributions=[dist],
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        source_dataset_id=dataset_id,
        dedup_key=dedup_key,
        last_updated=_extract_last_updated(raw),
        coverage=DatasetCoverage(
            countries=countries,
            time_start=str(time_start) if time_start not in (None, "") else None,
            time_end=str(time_end) if time_end not in (None, "") else None,
            granularity="annual",
        ),
        access=DatasetAccess(
            api_endpoint=endpoint or None,
            auth_required=auth_required,
        ),
    )


def _normalize_ckan(
    raw: dict,
    *,
    source: str,
    metrics_map: dict[str, dict] | None,
    spec: SourceSpec | None = None,
) -> DatasetRecord:
    curated_raw = curate_ckan_package(raw, spec) if spec is not None else raw
    if curated_raw is None:
        raise ValueError(f"CKAN package filtered out by curation rules for source {source}")
    raw = curated_raw
    dataset_id = str(raw.get("id") or raw.get("name") or "")
    org = raw.get("organization") if isinstance(raw.get("organization"), dict) else {}
    agency = str(org.get("name") or source)
    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)

    resources = raw.get("resources") if isinstance(raw.get("resources"), list) else []
    dists = [
        DistributionRecord(
            id=_distribution_id(rid, str(res.get("url", "")), str(res.get("format", ""))),
            url=str(res.get("url") or ""),
            format=guess_ckan_resource_format(res),
            name=str(res.get("name") or ""),
            connector_type="rest_json",
            connector_params={"resource_id": str(res.get("id") or "")},
        )
        for res in resources
        if isinstance(res, dict)
    ]

    tags = [str(t.get("name") or "") for t in (raw.get("tags") or []) if isinstance(t, dict)]
    return DatasetRecord(
        id=rid,
        title=str(raw.get("title") or dataset_id),
        description=str(raw.get("notes") or raw.get("description") or ""),
        publisher=agency,
        themes=[t for t in tags if t],
        keywords=_coerce_string_list(raw.get("keywords") or []),
        variables=extract_variables(raw),
        spatial=str(raw.get("spatial") or ""),
        temporal_start=raw.get("temporal_start"),
        temporal_end=raw.get("temporal_end"),
        license=str(raw.get("license_id") or ""),
        formats=[guess_ckan_resource_format(res) for res in resources if isinstance(res, dict)],
        distributions=dists,
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        dedup_key=dedup_key,
    )


def _normalize_poland_open_data(
    raw: dict,
    *,
    source: str,
    metrics_map: dict[str, dict] | None,
) -> DatasetRecord:
    dataset_id = str(raw.get("id") or raw.get("name") or "")
    org = raw.get("organization") if isinstance(raw.get("organization"), dict) else {}
    agency = str(org.get("name") or source)
    dedup_key = f"{source}|{agency}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)

    categories = _coerce_string_list(raw.get("categories") or [])
    category = str(raw.get("category") or "").strip()
    themes: list[str] = []
    for item in [*categories, category]:
        if item and item not in themes:
            themes.append(item)

    resource_url = str(raw.get("resources_related_url") or raw.get("dataset_url") or "").strip()
    distributions: list[DistributionRecord] = []
    if resource_url:
        distributions.append(
            DistributionRecord(
                id=_distribution_id(rid, resource_url, "JSON"),
                url=resource_url,
                format="JSON",
                name=str(raw.get("title") or dataset_id),
                connector_type="rest_json",
                connector_params={"url": resource_url},
            )
        )

    formats = _coerce_string_list(raw.get("formats") or [])
    if not formats and resource_url:
        formats = ["JSON"]

    return DatasetRecord(
        id=rid,
        title=str(raw.get("title") or dataset_id),
        description=str(raw.get("notes") or raw.get("description") or ""),
        publisher=agency,
        themes=themes,
        keywords=_coerce_string_list(raw.get("keywords") or []),
        variables=extract_variables(raw),
        spatial=str(raw.get("spatial") or ""),
        license=str(raw.get("license_name") or ""),
        formats=formats,
        distributions=distributions,
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=agency,
        dataset_id=dataset_id,
        source_dataset_id=dataset_id,
        dedup_key=dedup_key,
        last_updated=_extract_last_updated(raw),
    )


def _normalize_generic_endpoint(
    raw: dict,
    *,
    source: str,
    agency: str,
    connector_type: str,
    profile_id: str,
    metrics_map: dict[str, dict] | None,
) -> DatasetRecord:
    dataset_id = str(raw.get("id") or raw.get("dataset_id") or raw.get("name") or "")
    publisher = str(raw.get("publisher") or raw.get("attribution") or agency or source)
    dedup_key = f"{source}|{publisher}|{dataset_id}"
    rid = _stable_id("dataset", dedup_key)

    categories = _coerce_string_list(raw.get("categories") or [])
    category = str(raw.get("category") or raw.get("theme") or "").strip()
    themes: list[str] = []
    for item in [*categories, category]:
        if item and item not in themes:
            themes.append(item)

    formats = _coerce_string_list(raw.get("formats") or [])
    default_format = str(raw.get("format") or "").strip()
    if default_format and default_format not in formats:
        formats.append(default_format)

    distribution_url = str(
        raw.get("resource_url")
        or raw.get("resources_related_url")
        or raw.get("dataset_url")
        or raw.get("url")
        or ""
    ).strip()
    connector_params = dict(raw.get("connector_params") or {})
    default_filters = {
        str(key): [str(item) for item in value]
        for key, value in (raw.get("default_filters") or {}).items()
        if isinstance(value, list)
    }
    if dataset_id:
        connector_params.setdefault("dataset_id", dataset_id)

    distributions: list[DistributionRecord] = []
    if distribution_url or dataset_id:
        inferred_format = formats[0] if formats else (default_format or "JSON")
        distributions.append(
            DistributionRecord(
                id=_distribution_id(rid, distribution_url or dataset_id, inferred_format),
                url=distribution_url,
                format=inferred_format,
                name=str(raw.get("title") or dataset_id),
                connector_type=connector_type,
                connector_params=connector_params,
                profile_id=profile_id,
                default_filters=default_filters,
            )
        )
        if not formats:
            formats = [inferred_format]

    return DatasetRecord(
        id=rid,
        title=str(raw.get("title") or dataset_id),
        description=str(raw.get("notes") or raw.get("description") or ""),
        publisher=publisher,
        themes=themes,
        keywords=_coerce_string_list(raw.get("keywords") or raw.get("tags") or []),
        variables=_coerce_string_list(raw.get("schema_fields") or raw.get("variables") or []) or extract_variables(raw),
        spatial=str(raw.get("spatial") or ""),
        license=str(raw.get("license_name") or raw.get("license") or ""),
        formats=formats,
        distributions=distributions,
        polisyos_metrics=_map_metrics(raw, metrics_map),
        source_portal=source,
        source=source,
        agency=publisher,
        dataset_id=dataset_id,
        source_dataset_id=str(raw.get("source_dataset_id") or dataset_id),
        dedup_key=dedup_key,
        last_updated=_extract_last_updated(raw),
    )


def normalize_raw_sources(config: DatasetBatchConfig, *, metrics_map: dict[str, dict] | None = None) -> dict[str, int]:
    """Normalize latest raw snapshots to per-source JSONL files."""
    if metrics_map is None:
        metrics_map = load_metrics_map(config.resolved_metrics_map_path)

    registry = config.load_registry()
    source_specs = {spec.name: spec for spec in registry.sources}
    source_dirs = sorted([p for p in config.raw_dir.iterdir() if p.is_dir()]) if config.raw_dir.exists() else []
    counts: dict[str, int] = {}

    started_at = datetime.now(UTC).isoformat()
    artifacts: list[Path] = []
    for source_dir in source_dirs:
        latest_snapshots = sorted([p for p in source_dir.iterdir() if p.is_dir()])
        if not latest_snapshots:
            continue
        latest = latest_snapshots[-1]
        payload = latest / "payload.jsonl"
        rows = []
        if payload.exists():
            with open(payload, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))

        source = source_dir.name
        spec = source_specs.get(source) or _fallback_source_spec(source, endpoint=str(payload))
        records: list[DatasetRecord] = []
        for row in rows:
            try:
                if source in {"oecd", "imf", "ecb", "eurostat", "undata", "ilo", "unicef"}:
                    rec = _normalize_sdmx(row, source=source, metrics_map=metrics_map)
                elif source == "worldbank":
                    rec = _normalize_worldbank(row, metrics_map=metrics_map)
                elif source == "ukons":
                    rec = _normalize_ukons(row, metrics_map=metrics_map)
                elif source == "who":
                    rec = _normalize_indicator_api(
                        row,
                        source=source,
                        agency="WHO",
                        endpoint="https://ghoapi.azureedge.net/api/Indicator",
                        connector_type="who",
                        metrics_map=metrics_map,
                    )
                elif source == "unesco_uis":
                    rec = _normalize_indicator_api(
                        row,
                        source=source,
                        agency="UNESCO_UIS",
                        endpoint="https://api.uis.unesco.org/api/public/definitions/indicators",
                        connector_type="unesco_uis",
                        metrics_map=metrics_map,
                    )
                elif source == "unpd":
                    rec = _normalize_indicator_api(
                        row,
                        source=source,
                        agency="UNPD",
                        endpoint="https://population.un.org/dataportalapi/api/v1/indicators/",
                        connector_type="unpd",
                        metrics_map=metrics_map,
                    )
                elif source == "wvs":
                    rec = _normalize_indicator_api(
                        row,
                        source=source,
                        agency="WVS",
                        endpoint="https://api.worldvaluessurvey.org/v1/observations",
                        connector_type="wvs",
                        metrics_map=metrics_map,
                    )
                elif spec.family == "poland_api":
                    rec = _normalize_poland_open_data(row, source=source, metrics_map=metrics_map)
                elif spec.family == "opendatasoft":
                    rec = _normalize_generic_endpoint(
                        row,
                        source=source,
                        agency="Opendatasoft",
                        connector_type="opendatasoft",
                        profile_id=spec.profile_id,
                        metrics_map=metrics_map,
                    )
                elif spec.family == "socrata":
                    rec = _normalize_generic_endpoint(
                        row,
                        source=source,
                        agency="Socrata",
                        connector_type="socrata",
                        profile_id=spec.profile_id,
                        metrics_map=metrics_map,
                    )
                elif spec.family == "sparql":
                    rec = _normalize_generic_endpoint(
                        row,
                        source=source,
                        agency="SPARQL",
                        connector_type="sparql",
                        profile_id=spec.profile_id,
                        metrics_map=metrics_map,
                    )
                elif spec.family == "rest":
                    rec = _normalize_generic_endpoint(
                        row,
                        source=source,
                        agency=source.upper(),
                        connector_type="rest_json",
                        profile_id=spec.profile_id,
                        metrics_map=metrics_map,
                    )
                elif spec.family == "ckan":
                    rec = _normalize_ckan(row, source=source, metrics_map=metrics_map, spec=spec)
                else:
                    rec = _normalize_ckan(row, source=source, metrics_map=metrics_map, spec=spec)
                records.append(_with_execution_metadata(rec, raw=row, spec=spec))
            except Exception as exc:
                logger.debug(
                    "Skipping record in %s: %s", source, exc,
                )
                continue

        out_path = config.normalized_dir / f"{source}.jsonl"
        with open(out_path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(rec.model_dump_json() + "\n")
        counts[source] = len(records)
        artifacts.append(out_path)

    write_stage_manifest(
        manifest_path=config.manifests_dir / "normalize.json",
        stage="normalize",
        status="ok",
        metrics={"sources": len(counts), "records": sum(counts.values())},
        artifacts=artifacts,
        started_at=started_at,
    )
    return counts


# Backward-compatible API used by existing tests

def map_to_polisyos_metrics(raw: dict, metrics_map: dict[str, dict] | None = None) -> list[str]:
    return _map_metrics(raw, metrics_map)


def normalize_ckan(raw: dict, source_portal: str, metrics_map: dict | None = None) -> DatasetRecord:
    record = _normalize_ckan(
        raw,
        source=source_portal,
        metrics_map=metrics_map,
        spec=_fallback_source_spec(source_portal, endpoint=source_portal, execution_tier="catalog"),
    )
    return _with_execution_metadata(
        record,
        raw=raw,
        spec=SourceSpec(
            name=source_portal,
            family="ckan",
            wave="Z",
            endpoint=str(raw.get("url") or source_portal),
            connector_id="ckan.resource",
            execution_tier="catalog",
            update_frequency="irregular",
        ),
    )


def normalize_worldbank(raw: dict, metrics_map: dict | None = None) -> DatasetRecord:
    record = _normalize_worldbank(raw, metrics_map=metrics_map)
    return _with_execution_metadata(
        record,
        raw=raw,
        spec=SourceSpec(
            name="worldbank",
            family="worldbank",
            wave="B",
            endpoint="https://api.worldbank.org/v2/indicator",
            connector_id="worldbank.wdi",
            profile_id="worldbank_wdi",
            execution_tier="transport_ready",
            update_frequency="annual",
            metrics_required=True,
        ),
    )


def normalize_to_dcat(raw: dict, source_portal: str, connector_type: str, metrics_map: dict | None = None) -> DatasetRecord:
    if connector_type == "worldbank":
        return normalize_worldbank(raw, metrics_map=metrics_map)
    if connector_type == "wvs":
        record = _normalize_indicator_api(
            raw,
            source=source_portal,
            agency="WVS",
            endpoint="",
            connector_type="wvs",
            metrics_map=metrics_map,
        )
        return _with_execution_metadata(
            record,
            raw=raw,
            spec=SourceSpec(
                name=source_portal,
                family="wvs",
                wave="B",
                endpoint="https://api.worldvaluessurvey.org/v1/observations",
                connector_id="wvs.wave7",
                profile_id="wvs_wave7",
                execution_tier="transport_ready",
                update_frequency="irregular",
                metrics_required=True,
            ),
        )
    if connector_type in {"sdmx", "undata"}:
        return _with_execution_metadata(
            _normalize_sdmx(raw, source=source_portal, metrics_map=metrics_map),
            raw=raw,
            spec=_fallback_source_spec(source_portal, endpoint=source_portal, execution_tier="catalog"),
        )
    if connector_type in {"who", "unesco_uis", "unpd"}:
        agency_map = {"who": "WHO", "unesco_uis": "UNESCO_UIS", "unpd": "UNPD"}
        return _with_execution_metadata(
            _normalize_indicator_api(
                raw,
                source=source_portal,
                agency=agency_map.get(connector_type, source_portal.upper()),
                endpoint="",
                connector_type=connector_type,
                metrics_map=metrics_map,
            ),
            raw=raw,
            spec=_fallback_source_spec(source_portal, endpoint=source_portal, execution_tier="catalog"),
        )
    if connector_type == "rest" and source_portal == "data_gov_pl":
        return _with_execution_metadata(
            _normalize_poland_open_data(raw, source=source_portal, metrics_map=metrics_map),
            raw=raw,
            spec=SourceSpec(
                name="data_gov_pl",
                family="poland_api",
                wave="C",
                endpoint="https://api.dane.gov.pl/1.4/datasets",
                connector_id="rest.json",
                profile_id="data_gov_pl",
                execution_tier="catalog",
                update_frequency="irregular",
            ),
        )
    if connector_type == "ukons":
        return _with_execution_metadata(
            _normalize_ukons(raw, metrics_map=metrics_map),
            raw=raw,
            spec=SourceSpec(
                name="ukons",
                family="ukons",
                wave="B",
                endpoint="https://api.beta.ons.gov.uk/v1/datasets",
                connector_id="ukons.datasets",
                profile_id="ukons_public",
                execution_tier="catalog",
                update_frequency="monthly",
            ),
        )
    return normalize_ckan(raw, source_portal, metrics_map=metrics_map)
