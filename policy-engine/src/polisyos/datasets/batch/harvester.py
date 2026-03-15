"""Stage 1: source-driven harvest with wave support and raw manifests."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp

from polisyos.batch_common.manifest import write_raw_manifest, write_stage_manifest
from polisyos.common.logger import get_logger
from polisyos.datasets.batch.ckan_curation import curate_ckan_package
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.normalizer import map_to_polisyos_metrics
from polisyos.datasets.metrics_map import load_metrics_map
from polisyos.datasets.batch.source_registry import SourceSpec

logger = get_logger(__name__)
_SMOKE_PRIORITY_METRICS: tuple[str, ...] = (
    "gdp_per_capita",
    "gdp",
    "unemployment_rate",
    "inflation",
    "poverty_rate",
    "migration",
    "health_outcomes",
    "education_outcomes",
    "social_trust",
    "labor_force_participation",
    "institutional_quality",
)
_SOURCE_PRIORITY_METRICS: dict[str, tuple[str, ...]] = {
    "worldbank": (
        "gdp_per_capita",
        "poverty_rate",
        "health_outcomes",
        "institutional_quality",
        "education_outcomes",
        "labor_force_participation",
        "migration",
    ),
    "ilo": (
        "labor_force_participation",
        "unemployment_rate",
        "migration",
        "inflation",
        "gdp_per_capita",
        "education_outcomes",
    ),
    "who": (
        "health_outcomes",
        "poverty_rate",
        "education_outcomes",
        "gdp",
    ),
    "wvs": ("social_trust",),
    "data_gov_ro_broad": (
        "municipal_budget",
        "education_outcomes",
        "health_outcomes",
        "unemployment_rate",
        "migration",
        "demography",
    ),
    "data_gov_ro": (
        "municipal_budget",
        "education_outcomes",
        "health_outcomes",
        "unemployment_rate",
        "migration",
        "demography",
    ),
    "data_gov_ro_exec": (
        "municipal_budget",
        "education_outcomes",
        "health_outcomes",
        "unemployment_rate",
        "migration",
        "demography",
    ),
    "data_gov_md_broad": (
        "municipal_budget",
        "education_outcomes",
        "health_outcomes",
        "unemployment_rate",
        "migration",
        "demography",
    ),
    "data_gov_md": (
        "municipal_budget",
        "education_outcomes",
        "health_outcomes",
        "unemployment_rate",
        "migration",
        "demography",
    ),
    "data_gov_md_exec": (
        "municipal_budget",
        "education_outcomes",
        "health_outcomes",
        "unemployment_rate",
        "migration",
        "demography",
    ),
    "data_gov_pl_broad": (
        "municipal_budget",
        "education_outcomes",
        "health_outcomes",
        "unemployment_rate",
        "migration",
        "demography",
    ),
    "data_gov_pl": (
        "municipal_budget",
        "education_outcomes",
        "health_outcomes",
        "unemployment_rate",
        "migration",
        "demography",
    ),
    "data_gov_pl_exec": (
        "municipal_budget",
        "education_outcomes",
        "health_outcomes",
        "unemployment_rate",
        "migration",
        "demography",
    ),
    "paris_opendata_exec": (
        "health_outcomes",
        "education_outcomes",
        "unemployment_rate",
        "migration",
    ),
    "nyc_opendata": ("health_outcomes", "education_outcomes", "migration"),
    "nyc_opendata_exec": ("health_outcomes", "education_outcomes", "migration"),
    "chicago_opendata": ("health_outcomes", "education_outcomes", "migration"),
    "chicago_opendata_exec": ("health_outcomes", "education_outcomes", "migration"),
    "opendatasoft_public": ("health_outcomes", "education_outcomes", "migration"),
}
_PRIORITY_PATTERNS: dict[str, tuple[str, ...]] = {
    "gdp_per_capita": ("gdp per capita", "gross domestic product per capita", "ввп на душу"),
    "gdp": ("gross domestic product", " gdp ", "ввп"),
    "unemployment_rate": ("unemployment", "jobless", "безробіт", "somaj", "șomaj", "bezroboc", "rynek pracy"),
    "inflation": ("inflation", "consumer price", "cpi", "інфляц", "inflatie", "inflație", "inflacja"),
    "poverty_rate": ("poverty", "deprivation", "бідн"),
    "migration": ("migration", "migrant", "refugee", "міграц", "migratie", "migrație", "migrac", "demografi"),
    "health_outcomes": ("life expectancy", "healthy life expectancy", "mortality", "тривалість життя", "здоров", "sanat", "sănătate", "spital", "zdrow", "szpital"),
    "education_outcomes": ("education", "enrollment", "enrolment", "school", "literacy", "освіт", "зарахув", "educat", "scoala", "școal", "elev", "edukac", "szkol", "uczni"),
    "social_trust": ("social trust", "values survey", "довір"),
    "labor_force_participation": ("labor force participation", "labour force participation", "робочій силі"),
    "institutional_quality": ("rule of law", "government effectiveness", "regulatory quality", "institutional quality"),
    "municipal_budget": ("budget", "municipal budget", "local budget", "buget", "buget local", "venituri", "cheltuieli", "budzet", "budżet", "dochody", "wydatki"),
    "demography": ("demography", "population", "birth", "death", "demograf", "populatie", "populație", "nasteri", "nașteri", "decese", "ludnosc", "ludność", "urodzenia", "zgony"),
}
_PRIORITY_BLACKLIST: tuple[str, ...] = (
    "climate",
    "wildfire",
    "flood",
    "drought",
    "academic school year",
    "start month",
    "end month",
)
_WVS_STATIC_INDICATORS: tuple[dict[str, str], ...] = (
    {
        "id": "A165",
        "name": "Most people can be trusted",
        "description": "World Values Survey Wave 7 social trust question",
        "wave": "7",
    },
    {
        "id": "A173",
        "name": "Trust in civil service",
        "description": "World Values Survey Wave 7 institutional trust question",
        "wave": "7",
    },
)
_SPARQL_SOURCE_TEMPLATES: dict[str, tuple[dict[str, Any], ...]] = {
    "wikidata_sparql": (
        {
            "id": "country_entities",
            "title": "Wikidata country entities for comparator alignment",
            "description": "Entity resolution for countries, regions, and comparator panels.",
            "keywords": ["entity resolution", "country", "region", "wikidata", "migration", "population"],
            "format": "JSON",
        },
        {
            "id": "indicator_topics",
            "title": "Wikidata policy indicator topics",
            "description": "Ontology enrichment for policy topics, metrics, and indicator concepts.",
            "keywords": ["indicator", "taxonomy", "policy", "concept", "gdp", "unemployment", "inflation", "health", "education"],
            "format": "JSON",
        },
    ),
    "dbpedia_sparql": (
        {
            "id": "country_labels",
            "title": "DBpedia country labels and aliases",
            "description": "Alternative labels and aliases for country/entity matching.",
            "keywords": ["alias", "labels", "country", "entity resolution", "migration", "population"],
            "format": "JSON",
        },
        {
            "id": "policy_taxonomy",
            "title": "DBpedia policy taxonomy hints",
            "description": "Taxonomy enrichment for policy domains and linked concepts.",
            "keywords": ["taxonomy", "policy", "concept", "dbpedia", "gdp", "health", "education"],
            "format": "JSON",
        },
    ),
}
_REST_SOURCE_TEMPLATES: dict[str, tuple[dict[str, Any], ...]] = {
    "openaq_v2": (
        {
            "id": "openaq_air_quality_city_day",
            "title": "OpenAQ city-day air quality aggregates",
            "description": "Rolling-window air quality measurements for UA, PL, RO, MD, and DE city-day comparator panels.",
            "keywords": ["air quality", "pollution", "environment", "city", "daily"],
            "formats": ["JSON"],
            "default_filters": {"country": ["UA", "PL", "RO", "MD", "DE"]},
        },
    ),
    "open_meteo": (
        {
            "id": "open_meteo_country_daily",
            "title": "Open-Meteo country daily weather aggregates",
            "description": "Rolling-window daily weather covariates for canonical country coordinates.",
            "keywords": ["weather", "temperature", "precipitation", "daily"],
            "formats": ["JSON"],
        },
    ),
    "eia_api": (
        {
            "id": "eia_energy_monthly",
            "title": "EIA monthly energy series",
            "description": "Monthly energy indicators and prices for compact policy covariates.",
            "keywords": ["energy", "electricity", "gas", "monthly"],
            "formats": ["JSON"],
        },
    ),
}


def _utc_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _latest_snapshot_dir(source_root: Path) -> Path | None:
    if not source_root.exists():
        return None
    dirs = sorted([p for p in source_root.iterdir() if p.is_dir()])
    return dirs[-1] if dirs else None


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _apply_limit(rows: list[dict], limit: int) -> list[dict]:
    capped = max(int(limit), 0)
    return rows[:capped] if capped else rows


def _harvest_limit_for_source(spec: SourceSpec, config: DatasetBatchConfig) -> int:
    limit = max(int(config.max_datasets_per_source), 0)
    if limit <= 0 or not config.is_sampled_run:
        return limit
    if spec.family == "poland_api":
        return max(limit * 150, 1200)
    if spec.family == "ckan":
        return max(limit * 50, 200)
    if spec.family == "worldbank":
        return max(limit * 40, 250)
    if spec.family == "who":
        return max(limit * 50, 250)
    if spec.family in {"uis", "unpd"}:
        return max(limit * 25, 120)
    if spec.family == "wvs":
        return max(limit * 10, 25)
    if spec.family == "opendatasoft":
        return max(limit * 20, 200)
    if spec.family == "socrata":
        return max(limit * 20, 200)
    if spec.family == "sparql":
        return max(limit, 10)
    if spec.family == "rest":
        return max(limit, 5)
    return limit


async def harvest_sources(config: DatasetBatchConfig) -> dict[str, list[dict]]:
    """Harvest all enabled sources in selected wave."""
    registry = config.load_registry()
    specs = registry.enabled_sources(wave=config.wave, run_profile=config.run_profile)
    metrics_map = load_metrics_map(config.resolved_metrics_map_path)

    started_at = datetime.now(UTC).isoformat()
    out: dict[str, list[dict]] = {}

    # Wave C is intentionally serial-only and heavy (CKAN data.gov.ua).
    for spec in specs:
        rows = await harvest_one_source(spec, config, harvested=out, metrics_map=metrics_map)
        out[spec.name] = rows

    stage_manifest = config.manifests_dir / "harvest.json"
    write_stage_manifest(
        manifest_path=stage_manifest,
        stage="harvest",
        status="ok",
        metrics={"wave": config.wave or "ALL", "sources": len(specs), "records": sum(len(v) for v in out.values())},
        artifacts=[],
        started_at=started_at,
    )
    return out


async def harvest_one_source(
    spec: SourceSpec,
    config: DatasetBatchConfig,
    *,
    harvested: dict[str, list[dict]] | None = None,
    metrics_map: dict[str, dict] | None = None,
) -> list[dict]:
    """Harvest one source with optional resume from latest raw snapshot."""
    source_root = config.raw_dir / spec.name
    latest_dir = _latest_snapshot_dir(source_root)
    latest_payload = latest_dir / "payload.jsonl" if latest_dir else None

    if config.resume and latest_payload and latest_payload.exists():
        logger.info("Using cached raw snapshot for {}: {}", spec.name, latest_payload)
        rows = _read_jsonl(latest_payload)
        rows = _prioritize_rows_for_sampling(rows, spec=spec, config=config, metrics_map=metrics_map)
        return _apply_limit(rows, config.max_datasets_per_source)

    logger.info("Harvesting source {} ({})", spec.name, spec.endpoint)
    harvest_limit = _harvest_limit_for_source(spec, config)
    if spec.seed_from:
        rows = _harvest_from_seed_source(spec, config, harvested=harvested)
    elif spec.family == "ckan":
        rows = await _harvest_ckan(spec.endpoint, harvest_limit, config.harvest_timeout)
    elif spec.family == "poland_api":
        rows = await _harvest_poland_open_data(spec.endpoint, harvest_limit, config.harvest_timeout)
    elif spec.family == "opendatasoft":
        rows = await _harvest_opendatasoft(spec.endpoint, harvest_limit, config.harvest_timeout)
    elif spec.family == "socrata":
        rows = await _harvest_socrata(spec.endpoint, harvest_limit, config.harvest_timeout)
    elif spec.family == "sparql":
        rows = _harvest_sparql_templates(spec)
    elif spec.family == "rest":
        rows = _harvest_rest_catalog(spec)
    elif spec.family == "worldbank":
        rows = await _harvest_worldbank(spec.endpoint, harvest_limit, config.harvest_timeout)
        rows = _augment_worldbank_rows(rows, metrics_map=metrics_map)
    elif spec.family == "ukons":
        rows = await _harvest_ukons(spec.endpoint, harvest_limit, config.harvest_timeout)
    elif spec.family == "undata":
        rows = await _harvest_undata(spec, config.harvest_timeout)
    elif spec.family == "sdmx":
        rows = await _harvest_sdmx_dataflows(spec, config.harvest_timeout)
    elif spec.family == "who":
        rows = await _harvest_who_indicators(spec.endpoint, harvest_limit, config.harvest_timeout)
    elif spec.family == "uis":
        rows = await _harvest_uis_indicators(spec.endpoint, harvest_limit, config.harvest_timeout)
    elif spec.family == "wvs":
        rows = await _harvest_wvs(spec.endpoint, harvest_limit, config.harvest_timeout)
    elif spec.family == "unpd":
        rows = await _harvest_unpd_indicators(spec.endpoint, harvest_limit, config.harvest_timeout)
    else:
        logger.warning("Unknown source family '{}' for {}", spec.family, spec.name)
        rows = []
    rows = _prioritize_rows_for_sampling(rows, spec=spec, config=config, metrics_map=metrics_map)
    rows = _apply_limit(rows, config.max_datasets_per_source)

    ts_dir = source_root / _utc_slug()
    payload_path = ts_dir / "payload.jsonl"
    manifest_path = ts_dir / "manifest.json"
    _write_jsonl(payload_path, rows)

    write_raw_manifest(
        manifest_path=manifest_path,
        source=spec.name,
        endpoint=spec.endpoint,
        payload_path=payload_path,
        count=len(rows),
        filters={
            "agency_prefix": spec.agency_prefix,
            "agency_allowlist": list(spec.agency_allowlist),
            "exclude_agencies": list(spec.exclude_agencies),
            "wave": spec.wave,
            "run_lane": spec.run_lane,
            "publish_blocking": spec.publish_blocking,
            "history_policy": spec.history_policy,
            "default_lookback_days": spec.default_lookback_days,
            "max_rows_per_snapshot": spec.max_rows_per_snapshot,
            "max_bytes_per_snapshot": spec.max_bytes_per_snapshot,
            "allow_manual_backfill": spec.allow_manual_backfill,
            "seed_from": spec.seed_from,
            "format_allowlist": list(spec.format_allowlist),
        },
        parser_version="2",
    )
    return rows


def _flatten_text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        out: list[str] = []
        for nested in value.values():
            out.extend(_flatten_text_values(nested))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_text_values(item))
        return out
    text = str(value).strip()
    return [text] if text else []


def _row_text(row: dict[str, Any]) -> str:
    body_parts: list[str] = []
    for key in (
        "name",
        "title",
        "description",
        "Definition",
        "sourceNote",
        "notes",
        "keywords",
        "category",
        "categories",
        "regions",
        "themes",
    ):
        body_parts.extend(_flatten_text_values(row.get(key)))
    tags = " ".join(_flatten_text_values(row.get("tags")))
    body = " ".join(body_parts)
    return f"{body} {tags}".strip().lower()


def _priority_metric_hits(text: str) -> list[str]:
    hits: list[str] = []
    for metric_id in _PRIORITY_PATTERNS:
        patterns = _PRIORITY_PATTERNS.get(metric_id, ())
        if any(pattern in text for pattern in patterns):
            hits.append(metric_id)
    return hits


def _score_row_for_sampling(
    row: dict[str, Any],
    *,
    spec: SourceSpec,
    metrics_map: dict[str, dict] | None,
) -> tuple[int, list[str]]:
    text = _row_text(row)
    matched_metrics = map_to_polisyos_metrics(row, metrics_map)
    heuristic_hits = _priority_metric_hits(text)
    candidates: list[str] = []
    for metric_id in [*matched_metrics, *heuristic_hits]:
        if metric_id not in candidates:
            candidates.append(metric_id)

    priority_hits = [metric for metric in candidates if metric in _SMOKE_PRIORITY_METRICS]
    score = 0
    score += 100 * len(priority_hits)
    score += 25 * len(candidates)
    score += 4 * sum(1 for metric_id in _SMOKE_PRIORITY_METRICS if any(pattern in text for pattern in _PRIORITY_PATTERNS.get(metric_id, ())))

    if spec.family == "sdmx":
        code = str(row.get("id", "") or "").lower()
        if any(token in code for token in ("une", "unemp", "lfs", "cpi", "gdp", "pov", "mig", "edu", "health")):
            score += 10

    if any(token in text for token in _PRIORITY_BLACKLIST):
        score -= 15
    if row.get("description"):
        score += 2
    return score, candidates


def _prioritize_rows_for_sampling(
    rows: list[dict],
    *,
    spec: SourceSpec,
    config: DatasetBatchConfig,
    metrics_map: dict[str, dict] | None,
) -> list[dict]:
    if not rows or not config.is_sampled_run:
        return rows
    if spec.family not in {"sdmx", "who", "uis", "unpd", "worldbank", "wvs", "ckan", "poland_api"}:
        return rows

    scored: list[tuple[int, int, tuple[str, ...], dict]] = []
    for index, row in enumerate(rows):
        score, candidates = _score_row_for_sampling(row, spec=spec, metrics_map=metrics_map)
        if candidates:
            row = dict(row)
            row["harvest_metric_candidates"] = candidates
        scored.append((score, index, tuple(candidates), row))

    ranked = sorted(
        scored,
        key=lambda item: (
            -int(bool(item[2])) if spec.metrics_required else 0,
            -item[0],
            item[1],
        ),
    )
    selected_indexes: list[int] = []
    selected_set: set[int] = set()
    limit = max(int(config.max_datasets_per_source), 0)

    if limit > 0:
        priority_order = _SOURCE_PRIORITY_METRICS.get(spec.name, _SMOKE_PRIORITY_METRICS)
        for metric_id in priority_order:
            for _score, index, candidates, _row in ranked:
                if metric_id not in candidates or index in selected_set:
                    continue
                selected_indexes.append(index)
                selected_set.add(index)
                break
            if len(selected_indexes) >= limit:
                break

        if len(selected_indexes) < limit:
            candidate_ranked = [item for item in ranked if item[2]]
            fallback_ranked = candidate_ranked if spec.metrics_required and candidate_ranked else ranked
            for _score, index, _candidates, _row in fallback_ranked:
                if index in selected_set:
                    continue
                selected_indexes.append(index)
                selected_set.add(index)
                if len(selected_indexes) >= limit:
                    break

    ranked_by_index = {index: row for _score, index, _candidates, row in ranked}
    prioritized = [ranked_by_index[index] for index in selected_indexes if index in ranked_by_index]
    prioritized.extend(
        row
        for _score, index, _candidates, row in ranked
        if index not in selected_set
    )
    logger.info(
        "Prioritized {} sampled rows for {} before applying limit {}",
        len(prioritized),
        spec.name,
        config.max_datasets_per_source,
    )
    return prioritized


def _augment_worldbank_rows(
    rows: list[dict],
    *,
    metrics_map: dict[str, dict] | None,
) -> list[dict]:
    if not metrics_map:
        return rows
    seen = {
        str(row.get("id") or "").strip().upper()
        for row in rows
        if isinstance(row, dict)
    }
    augmented = list(rows)
    for metric_id, spec in metrics_map.items():
        if not isinstance(spec, dict):
            continue
        keywords = [str(value).strip() for value in spec.get("keywords", []) if str(value).strip()]
        for indicator_id in spec.get("worldbank_indicators", []) or []:
            code = str(indicator_id or "").strip()
            if not code:
                continue
            upper_code = code.upper()
            if upper_code in seen:
                continue
            seen.add(upper_code)
            title = keywords[0] if keywords else code
            augmented.append(
                {
                    "id": code,
                    "name": title,
                    "sourceNote": " ".join(keywords),
                    "harvest_metric_candidates": [metric_id],
                }
            )
    return augmented


def _harvest_from_seed_source(
    spec: SourceSpec,
    config: DatasetBatchConfig,
    *,
    harvested: dict[str, list[dict]] | None = None,
) -> list[dict]:
    rows = list((harvested or {}).get(spec.seed_from, []))
    if not rows:
        seed_root = config.raw_dir / spec.seed_from
        latest_dir = _latest_snapshot_dir(seed_root)
        latest_payload = latest_dir / "payload.jsonl" if latest_dir else None
        rows = _read_jsonl(latest_payload) if latest_payload else []

    curated: list[dict] = []
    for row in rows:
        candidate = _curate_seed_row(row, spec)
        if candidate is not None:
            curated.append(row)
            if candidate is not row:
                curated[-1] = candidate

    limit = max(int(config.max_datasets_per_source), 0)
    return curated[:limit] if limit else curated


def _curate_seed_row(row: dict[str, Any], spec: SourceSpec) -> dict[str, Any] | None:
    if spec.family == "ckan":
        return curate_ckan_package(row, spec)
    if not _generic_seed_row_allowed(row, spec):
        return None
    return dict(row)


def _generic_seed_row_allowed(row: dict[str, Any], spec: SourceSpec) -> bool:
    text = _row_text(row)
    allow_match = _matches_any_seed(text, spec.keyword_allowlist) if spec.keyword_allowlist else True
    deny_match = _matches_any_seed(text, spec.keyword_denylist)
    if not allow_match or deny_match:
        return False

    formats = _seed_row_formats(row)
    if spec.family == "poland_api" and row.get("resources_related_url"):
        # Poland catalog rows often advertise only the landing-page HTML format even when
        # the related resources API resolves to machine-readable JSON distributions later.
        if not any(fmt for fmt in formats if fmt != "HTML") and spec.format_allowlist:
            formats = tuple(spec.format_allowlist)
    if spec.format_denylist and any(fmt in spec.format_denylist for fmt in formats):
        return False
    if spec.format_allowlist and not any(fmt in spec.format_allowlist for fmt in formats):
        return False
    if spec.require_curated_resources:
        return bool(
            row.get("resource_url")
            or row.get("resources_related_url")
            or row.get("dataset_url")
            or row.get("url")
        )
    return True


def _seed_row_formats(row: dict[str, Any]) -> tuple[str, ...]:
    formats = [str(item).strip().upper() for item in (row.get("formats") or []) if str(item).strip()]
    explicit = str(row.get("format") or "").strip().upper()
    if explicit and explicit not in formats:
        formats.append(explicit)
    return tuple(formats)


def _matches_any_seed(text: str, needles: tuple[str, ...]) -> bool:
    haystack = text.lower()
    for needle in needles:
        candidate = str(needle or "").strip().lower()
        if candidate and candidate in haystack:
            return True
    return False


async def _harvest_ckan(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    start = 0
    per_page = 100
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            params = {"rows": per_page, "start": start, "include_private": "false"}
            async with session.get(endpoint, params=params) as resp:
                if resp.status != 200:
                    break
                data = await resp.json(content_type=None)
            result = data.get("result", {}) if isinstance(data, dict) else {}
            batch = result.get("results", []) if isinstance(result, dict) else []
            if not batch:
                break
            rows.extend([r for r in batch if isinstance(r, dict)])
            total = int(result.get("count", 0))
            start += per_page
            if start >= min(total, limit):
                break
    return rows[:limit]


async def _harvest_opendatasoft(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    per_page = 100
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    base = endpoint.rstrip("/")
    url = f"{base}/api/explore/v2.1/catalog/datasets"
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            params = {"limit": min(per_page, limit - len(rows)), "offset": offset}
            async with session.get(url, params=params, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    break
                payload = await resp.json(content_type=None)
            batch = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(batch, list) or not batch:
                break
            for item in batch:
                if not isinstance(item, dict):
                    continue
                metas = item.get("metas") if isinstance(item.get("metas"), dict) else {}
                default = metas.get("default") if isinstance(metas.get("default"), dict) else metas
                dataset_id = str(item.get("dataset_id") or item.get("datasetid") or "").strip()
                title = str(default.get("title") or dataset_id).strip()
                rows.append(
                    {
                        "id": dataset_id,
                        "title": title,
                        "description": str(default.get("description") or "").strip(),
                        "keywords": [str(tag).strip() for tag in (default.get("keyword") or []) if str(tag).strip()],
                        "category": str(default.get("theme") or "").strip(),
                        "format": "JSON",
                        "formats": ["JSON"],
                        "schema_fields": [
                            str(field.get("name") or "").strip()
                            for field in (item.get("fields") or [])
                            if isinstance(field, dict) and str(field.get("name") or "").strip()
                        ],
                        "dataset_url": f"{base}/api/explore/v2.1/catalog/datasets/{dataset_id}/records",
                        "metadata_modified": default.get("modified"),
                        "publisher": str(default.get("publisher") or "Opendatasoft").strip(),
                    }
                )
            if len(batch) < per_page:
                break
            offset += per_page
    return rows[:limit]


async def _harvest_socrata(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    page = 1
    per_page = 100
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    base = endpoint.rstrip("/")
    url = f"{base}/api/views"
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            params = {"limit": min(per_page, limit - len(rows)), "page": page}
            async with session.get(url, params=params, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    break
                payload = await resp.json(content_type=None)
            if not isinstance(payload, list) or not payload:
                break
            for item in payload:
                if not isinstance(item, dict):
                    continue
                dataset_id = str(item.get("id") or "").strip()
                rows.append(
                    {
                        "id": dataset_id,
                        "title": str(item.get("name") or dataset_id).strip(),
                        "description": str(item.get("description") or "").strip(),
                        "category": str(item.get("category") or "").strip(),
                        "keywords": [
                            str(item.get("category") or "").strip(),
                            str(item.get("attribution") or "").strip(),
                        ],
                        "format": "JSON",
                        "formats": ["JSON"],
                        "dataset_url": f"{base}/resource/{dataset_id}.json",
                        "metadata_modified": item.get("rowsUpdatedAt"),
                        "publisher": str(item.get("attribution") or "Socrata").strip(),
                    }
                )
            if len(payload) < per_page:
                break
            page += 1
    return rows[:limit]


def _harvest_sparql_templates(spec: SourceSpec) -> list[dict]:
    templates = _SPARQL_SOURCE_TEMPLATES.get(spec.name, ())
    return [
        {
            **template,
            "formats": [template.get("format", "JSON")],
            "dataset_url": spec.endpoint,
            "publisher": spec.name,
        }
        for template in templates
    ]


def _harvest_rest_catalog(spec: SourceSpec) -> list[dict]:
    templates = _REST_SOURCE_TEMPLATES.get(spec.name, ())
    return [
        {
            **template,
            "dataset_url": spec.endpoint,
            "publisher": spec.name,
            "metadata_modified": datetime.now(UTC).date().isoformat(),
        }
        for template in templates
    ]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").replace("&nbsp;", " ").strip()


def _flatten_poland_open_data_row(raw: dict[str, Any]) -> dict[str, Any]:
    attrs = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
    relationships = raw.get("relationships") if isinstance(raw.get("relationships"), dict) else {}
    keywords = [str(item).strip() for item in (attrs.get("keywords") or []) if str(item).strip()]
    category = attrs.get("category") if isinstance(attrs.get("category"), dict) else {}
    category_title = str(category.get("title") or "").strip()
    categories = [
        str(item.get("title") or "").strip()
        for item in (attrs.get("categories") or [])
        if isinstance(item, dict) and str(item.get("title") or "").strip()
    ]
    regions = [
        str(item.get("name") or "").strip()
        for item in (attrs.get("regions") or [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    formats = [str(item).strip().upper() for item in (attrs.get("formats") or []) if str(item).strip()]
    types = [str(item).strip() for item in (attrs.get("types") or []) if str(item).strip()]
    institution = relationships.get("institution") if isinstance(relationships.get("institution"), dict) else {}
    institution_data = institution.get("data") if isinstance(institution.get("data"), dict) else {}
    resources_rel = relationships.get("resources") if isinstance(relationships.get("resources"), dict) else {}
    resources_links = resources_rel.get("links") if isinstance(resources_rel.get("links"), dict) else {}
    resources_related_url = str(resources_links.get("related") or "").strip()
    notes = _strip_html(str(attrs.get("notes") or ""))
    description_parts = [notes, category_title, *categories, *keywords, *regions, *types]
    publisher = str(institution_data.get("id") or "").strip() or "data_gov_pl"
    tag_names = list(dict.fromkeys([*keywords, *categories, category_title]))
    return {
        "id": str(raw.get("id") or ""),
        "name": str(attrs.get("slug") or ""),
        "title": str(attrs.get("title") or attrs.get("slug") or raw.get("id") or ""),
        "notes": notes,
        "description": " ".join(part for part in description_parts if part).strip(),
        "keywords": keywords,
        "category": category_title,
        "categories": categories,
        "regions": regions,
        "types": types,
        "formats": formats,
        "organization": {"name": publisher},
        "tags": [{"name": item} for item in tag_names if item],
        "metadata_modified": attrs.get("resource_modified") or attrs.get("modified"),
        "modified": attrs.get("modified"),
        "resource_modified": attrs.get("resource_modified"),
        "license_name": str(attrs.get("license_condition_original") or ""),
        "resources_related_url": resources_related_url,
        "dataset_url": str(((raw.get("links") or {}).get("self")) or "").strip(),
        "spatial": "POL" if any(region.lower() in {"polska", "poland"} for region in regions) else "",
    }


async def _harvest_poland_open_data(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    page = 1
    per_page = 100
    next_url: str | None = None
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            request_url = next_url or endpoint
            params = None if next_url else {"page": page, "per_page": per_page, "sort": "id"}
            async with session.get(
                request_url,
                params=params,
                headers={"Accept": "application/vnd.api+json"},
            ) as resp:
                if resp.status != 200:
                    break
                payload = await resp.json(content_type=None)
            batch = payload.get("data", []) if isinstance(payload, dict) else []
            if not isinstance(batch, list) or not batch:
                break
            rows.extend(
                _flatten_poland_open_data_row(item)
                for item in batch
                if isinstance(item, dict)
            )
            links = payload.get("links", {}) if isinstance(payload, dict) else {}
            next_url = str(links.get("next") or "").strip() or None
            page += 1
            if not next_url:
                break
    return rows[:limit]


async def _harvest_worldbank(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    page = 1
    per_page = 1000
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            params = {"format": "json", "per_page": per_page, "page": page}
            async with session.get(endpoint, params=params) as resp:
                if resp.status != 200:
                    break
                data = await resp.json(content_type=None)
            if not isinstance(data, list) or len(data) < 2:
                break
            batch = data[1] if isinstance(data[1], list) else []
            if not batch:
                break
            rows.extend([r for r in batch if isinstance(r, dict)])
            total = int(data[0].get("total", 0)) if isinstance(data[0], dict) else 0
            page += 1
            if len(rows) >= min(limit, total or limit):
                break
    return rows[:limit]


async def _harvest_ukons(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    per_page = 50
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            params = {"offset": offset, "limit": per_page}
            async with session.get(endpoint, params=params) as resp:
                if resp.status != 200:
                    break
                data = await resp.json(content_type=None)
            items = data.get("items", []) if isinstance(data, dict) else []
            if not items:
                break
            rows.extend([r for r in items if isinstance(r, dict)])
            offset += per_page
    return rows[:limit]


async def _harvest_undata(spec: SourceSpec, timeout_s: int) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(spec.endpoint, headers={"Accept": "text/json"}) as resp:
            if resp.status != 200:
                return []
            payload = await resp.json(content_type=None)

    refs = payload.get("references", {}) if isinstance(payload, dict) else {}
    rows: list[dict] = []
    if isinstance(refs, dict):
        for value in refs.values():
            if isinstance(value, dict):
                rows.append(value)
            elif isinstance(value, list):
                rows.extend([v for v in value if isinstance(v, dict)])

    allow = set(spec.agency_allowlist)
    exclude = set(spec.exclude_agencies)
    filtered: list[dict] = []
    for row in rows:
        agency = str(row.get("agencyID", ""))
        if allow and agency not in allow:
            continue
        if agency in exclude:
            continue
        filtered.append(row)
    return filtered


async def _harvest_sdmx_dataflows(spec: SourceSpec, timeout_s: int) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(spec.endpoint, headers={"Accept": "application/xml"}) as resp:
            if resp.status != 200:
                return []
            content = await resp.read()

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    rows: list[dict] = []
    for elem in root.iter():
        tag = elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag
        if tag != "Dataflow":
            continue
        row = {
            "id": elem.attrib.get("id", ""),
            "agencyID": elem.attrib.get("agencyID", ""),
            "version": elem.attrib.get("version", ""),
            "name": "",
            "description": "",
        }
        for child in elem:
            ctag = child.tag.split("}", 1)[1] if "}" in child.tag else child.tag
            if ctag == "Name" and not row["name"]:
                row["name"] = (child.text or "").strip()
            elif ctag == "Description" and not row["description"]:
                row["description"] = (child.text or "").strip()

        agency = str(row.get("agencyID", ""))
        if spec.agency_prefix and not agency.startswith(spec.agency_prefix):
            continue
        rows.append(row)
    return rows


async def _harvest_who_indicators(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    next_url: str | None = endpoint
    timeout = aiohttp.ClientTimeout(total=timeout_s)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        while next_url and len(rows) < limit:
            async with session.get(next_url, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    break
                payload = await resp.json(content_type=None)
            batch = payload.get("value", []) if isinstance(payload, dict) else []
            if not isinstance(batch, list) or not batch:
                break
            rows.extend([row for row in batch if isinstance(row, dict)])
            next_url = payload.get("@odata.nextLink") if isinstance(payload, dict) else None
    return rows[:limit]


async def _harvest_uis_indicators(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(endpoint, headers={"Accept": "application/json"}) as resp:
            if resp.status != 200:
                return []
            payload = await resp.json(content_type=None)

    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            rows = [row for row in payload["data"] if isinstance(row, dict)]
        elif isinstance(payload.get("items"), list):
            rows = [row for row in payload["items"] if isinstance(row, dict)]
        else:
            rows = [payload]
    else:
        rows = []
    return rows[:limit]


async def _harvest_wvs(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(endpoint, headers={"Accept": "application/json"}) as resp:
                if resp.status == 200:
                    payload = await resp.json(content_type=None)
                    if isinstance(payload, list):
                        rows = [row for row in payload if isinstance(row, dict)]
                    elif isinstance(payload, dict):
                        if isinstance(payload.get("data"), list):
                            rows = [row for row in payload["data"] if isinstance(row, dict)]
                        elif isinstance(payload.get("items"), list):
                            rows = [row for row in payload["items"] if isinstance(row, dict)]
                        elif isinstance(payload.get("results"), list):
                            rows = [row for row in payload["results"] if isinstance(row, dict)]
                        else:
                            rows = [payload]
    except Exception:
        logger.debug("Falling back to static WVS indicator catalog", exc_info=True)

    if not rows:
        rows = [dict(item) for item in _WVS_STATIC_INDICATORS]
    return rows[:limit]


async def _harvest_unpd_indicators(endpoint: str, limit: int, timeout_s: int) -> list[dict]:
    rows: list[dict] = []
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    next_url: str | None = endpoint
    page = 1

    async with aiohttp.ClientSession(timeout=timeout) as session:
        while len(rows) < limit:
            if next_url:
                request_url = next_url
                params: dict[str, Any] | None = None
            else:
                request_url = endpoint
                params = {"page": page}
            async with session.get(request_url, params=params, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    break
                payload = await resp.json(content_type=None)

            if not isinstance(payload, dict):
                break
            batch = payload.get("data", [])
            if not isinstance(batch, list) or not batch:
                break
            rows.extend([row for row in batch if isinstance(row, dict)])

            next_url = (
                payload.get("next")
                or payload.get("nextPage")
                or payload.get("next_page")
                or payload.get("nextPageUrl")
            )
            if not next_url:
                page += 1
            if len(batch) == 0:
                break

    return rows[:limit]
