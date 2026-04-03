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
from polisyos.datasets.batch.checkpoints import fingerprint_paths, load_json, write_json
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
    # ── Macroeconomics ──
    ("gdp_per_capita", ("gdp per capita", "gross domestic product per capita", "ввп на душу")),
    ("gdp_growth", ("gdp growth", "economic growth", "зростання ввп", "wzrost pkb")),
    ("gdp", ("gross domestic product", " gdp ", "ввп")),
    ("unemployment_rate", ("unemployment", "jobless", "безробіт", "somaj", "șomaj", "bezroboc", "rynek pracy")),
    ("youth_unemployment", ("youth unemployment", "young unemploy", "молодіжне безробіт", "bezroboc młodz")),
    ("inflation", ("inflation", "consumer price", "cpi", "інфляц", "inflatie", "inflație", "inflacja")),
    ("interest_rate", ("interest rate", "central bank rate", "відсоткова ставка", "stopa procentowa")),
    ("public_debt", ("public debt", "government debt", "державний борг", "dług publiczny")),
    ("gov_balance", ("fiscal balance", "budget deficit", "budget surplus", "дефіцит бюджет")),
    ("trade_balance", ("trade balance", "export import", "торговий баланс", "bilans handlowy")),
    ("trade_openness", ("trade openness", "trade to gdp", "відкритість торгівлі")),
    ("fdi_inflows", ("foreign direct investment", " fdi ", "прямі іноземні інвестиц", "bezpośrednie inwestycje")),
    ("savings_rate", ("savings rate", "gross savings", "заощаджен")),
    ("investment_rate", ("gross capital formation", "investment rate", "інвестиц")),
    # ── Poverty & Inequality ──
    ("poverty_rate", ("poverty", "deprivation", "бідн", "saracie", "sărăcie", "ubóstw")),
    ("gini_coefficient", ("gini", "income inequality", "gini coefficient", "współczynnik gini")),
    ("inequality", ("inequality", "income distribution", "нерівн", "nierówn")),
    # ── Labour ──
    ("labor_force_participation", ("labor force participation", "labour force participation", "робочій силі")),
    ("female_labor_participation", ("female labor", "female labour", "women employment", "жіноча зайнят")),
    ("employment_rate", ("employment rate", "рівень зайнятост", "stopa zatrudnien")),
    ("informality_rate", ("informal economy", "informal employment", "тіньова економік")),
    ("wage_growth", ("wage growth", "wage increase", "зростання зарплат", "wzrost płac")),
    ("gender_wage_gap", ("gender pay gap", "gender wage gap", "гендерний розрив в оплат")),
    ("labor_productivity", ("labor productivity", "labour productivity", "продуктивність праці")),
    ("minimum_wage", ("minimum wage", "мінімальна заробітна", "płaca minimalna")),
    ("long_term_unemployment", ("long-term unemployment", "довгострокове безробіт")),
    ("working_poverty", ("working poverty", "in-work poverty", "працююча бідн")),
    # ── Migration ──
    ("migration", ("migration", "migrant", "refugee", "міграц", "migratie", "migrație", "migrac")),
    ("refugee_population", ("refugee", "asylum seeker", "біженц", "uchodźc")),
    ("remittance_inflows", ("remittance", "грошові перекази", "przekazy pieniężne")),
    ("displacement", ("internally displaced", "displacement", "переміщен")),
    # ── Demographics ──
    ("population_growth", ("population growth", "приріст населення", "przyrost naturalny")),
    ("fertility_rate", ("fertility rate", "birth rate", "народжуван", "dzietnoś")),
    ("urbanization_rate", ("urbanization", "urban population", "урбанізац", "urbanizacj")),
    ("dependency_ratio", ("dependency ratio", "age dependency", "коефіцієнт залежност")),
    # ── Health ──
    ("health_outcomes", ("life expectancy", "healthy life expectancy", "mortality", "тривалість життя", "здоров", "sanat", "sănătate", "spital", "zdrow", "szpital")),
    ("infant_mortality", ("infant mortality", "child mortality", "neonatal mortality", "дитяча смертн", "śmiertelność niemowl")),
    ("maternal_mortality", ("maternal mortality", "материнська смертн", "śmiertelność matek")),
    ("vaccination_coverage", ("vaccination", "immunization", "immunisation", "вакцинац", "щепленн", "szczepien")),
    ("obesity_prevalence", ("obesity", "overweight", "ожирінн", "otyłoś")),
    ("child_stunting", ("stunting", "malnutrition", "wasting", "затримка росту")),
    ("physician_density", ("physician density", "doctors per capita", "лікарі на душу")),
    ("hospital_beds", ("hospital beds", "лікарняні ліжк", "łóżka szpitaln")),
    ("clean_water_access", ("clean water", "safe water", "drinking water", "чиста вода", "czysta woda")),
    ("sanitation_coverage", ("sanitation", "sewerage", "каналізац", "kanalizacj")),
    ("universal_health_coverage", ("universal health coverage", " uhc ", "загальне медичне")),
    ("hiv_prevalence", ("hiv", "aids", "віл", "снід")),
    ("tuberculosis_incidence", ("tuberculosis", " tb ", "туберкульоз", "gruźlic")),
    ("noncommunicable_disease_mortality", ("noncommunicable disease", " ncd ", "неінфекційні захворюванн")),
    ("health_spending", ("health spending", "health expenditure", "витрати на здоров", "wydatki na zdrow")),
    ("out_of_pocket_spending", ("out-of-pocket", "out of pocket health", "витрати з власної кишен")),
    ("suicide_rate", ("suicide", "самогубств", "samobójstw")),
    # ── Education ──
    ("education_outcomes", ("education", "enrollment", "enrolment", "school", "literacy", "освіт", "зарахув", "educat", "școal", "scoala", "edukac", "szkol")),
    ("education_spending", ("education spending", "education expenditure", "витрати на освіт", "wydatki na edukacj")),
    ("tertiary_enrollment", ("tertiary enrollment", "university enrollment", "вища освіт", "szkolnictwo wyższ")),
    ("years_of_schooling", ("years of schooling", "expected years", "роки навчанн")),
    ("school_quality", ("learning outcomes", "learning poverty", "якість освіт", "jakość edukacj")),
    ("research_output", ("scientific publications", "research output", "наукові публікаці")),
    # ── Governance ──
    ("social_trust", ("social trust", "trust survey", "довір")),
    ("institutional_quality", ("rule of law", "government effectiveness", "regulatory quality", "institutional quality", "guvern", "administratie", "administrație", "administrac", "rząd")),
    ("corruption_level", ("corruption", "корупц", "korupcj", "anti-corruption")),
    ("democracy_quality", ("democracy", "democratic", "демократ", "demokracj")),
    ("public_trust", ("public trust", "trust in government", "trust in institution", "довіра до уряд")),
    ("political_stability", ("political stability", "political violence", "політична стабільн")),
    ("judicial_quality", ("judicial quality", "court system", "судова систем", "wymiar sprawiedliwoś")),
    ("property_rights", ("property rights", "права власност", "prawa własnośc")),
    # ── Environment & Climate ──
    ("co2_emissions", ("co2", "carbon emission", "greenhouse gas", "викид", "emisje co2")),
    ("renewable_energy_share", ("renewable energy", "clean energy", "відновлювана енерг", "energia odnawialn")),
    ("forest_cover", ("forest cover", "forest area", "deforestation", "ліс", "площа лісів")),
    ("air_quality_index", ("air quality", "pm2.5", "air pollution", "якість повітря", "jakość powietrz")),
    ("water_stress", ("water stress", "water scarcity", "водний стрес", "stres wodny")),
    ("energy_intensity", ("energy intensity", "energy efficiency", "енергоінтенсивн")),
    ("electricity_access", ("electricity access", "electrification", "доступ до електрик")),
    ("waste_management", ("waste management", "recycling", "відход", "gospodarka odpadami")),
    # ── Finance ──
    ("financial_inclusion", ("financial inclusion", "bank account", "фінансова інклюз", "inkluzja finansow")),
    ("credit_access", ("domestic credit", "credit access", "доступ до кредит")),
    # ── Infrastructure & Digital ──
    ("internet_penetration", ("internet users", "internet access", "інтернет", "dostęp do internet")),
    ("broadband_penetration", ("broadband", "fixed broadband", "широкосмуговий")),
    ("mobile_coverage", ("mobile phone", "cellular subscription", "мобільний зв'язок")),
    ("logistics_performance", ("logistics performance", " lpi ", "логістик")),
    # ── Security & Conflict ──
    ("homicide_rate", ("homicide", "murder rate", "вбивств", "zabójstw")),
    ("military_spending", ("military spending", "defense spending", "військові витрат", "wydatki wojskow")),
    ("conflict_intensity", ("armed conflict", "conflict intensity", "збройний конфлікт")),
    # ── Social ──
    ("social_capital", ("social capital", "civic participation", "соціальний капітал", "kapitał społeczn")),
    ("cultural_cluster", ("cultural values", "cultural cluster", "культурні ціннос")),
    ("gender_equality", ("gender equality", "women rights", "гендерна рівн", "równość płci")),
    ("social_protection_coverage", ("social protection", "social safety net", "соціальний захист")),
    ("child_labor", ("child labor", "child labour", "дитяча прац", "praca dziec")),
    ("human_capital", ("human capital index", " hci ", "людський капітал")),
    ("tax_revenue", ("tax revenue", "податкові надходженн", "wpływy podatkow")),
    ("government_spending", ("government spending", "public expenditure", "державні витрат")),
    ("r_and_d_spending", ("research and development", "r&d spending", "нддкр", "wydatki na b+r")),
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
    """Extract variables helper."""
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
    return [metric_id for metric_id, _method in _map_metrics_with_method(raw, metrics_map)]


def _map_metrics_both(
    raw: dict, metrics_map: dict[str, dict] | None
) -> tuple[list[str], dict[str, str]]:
    """Return ``(metric_ids, {metric_id: inference_method})``."""
    pairs = _map_metrics_with_method(raw, metrics_map)
    return [m for m, _ in pairs], {m: method for m, method in pairs}


# Metric inference methods in descending quality order.
METRIC_INFERENCE_CODE_MATCH = "code_match"
METRIC_INFERENCE_KEYWORD_MATCH = "keyword_match"
METRIC_INFERENCE_EMBEDDING_SIMILARITY = "embedding_similarity"
METRIC_INFERENCE_HEURISTIC = "heuristic"

# Confidence score associated with each inference method.
METRIC_INFERENCE_CONFIDENCE: dict[str, float] = {
    METRIC_INFERENCE_CODE_MATCH: 0.95,
    METRIC_INFERENCE_KEYWORD_MATCH: 0.75,
    METRIC_INFERENCE_EMBEDDING_SIMILARITY: 0.65,
    METRIC_INFERENCE_HEURISTIC: 0.55,
}


def _map_metrics_with_method(
    raw: dict, metrics_map: dict[str, dict] | None
) -> list[tuple[str, str]]:
    """Return ``[(metric_id, inference_method), ...]``."""
    if not metrics_map:
        return []
    text = " ".join(
        str(raw.get(key, "") or "")
        for key in ("title", "name", "description", "Definition", "sourceNote", "notes", "IndicatorName")
    ).lower()
    codes = {str(raw.get(k, "")).upper() for k in ("id", "dataset_id", "indicator_id", "dataflow_id") if raw.get(k)}

    matched: list[tuple[str, str]] = []
    seen: set[str] = set()

    hinted = raw.get("harvest_metric_candidates")
    if isinstance(hinted, list):
        for metric_id in hinted:
            metric_text = str(metric_id or "").strip()
            if metric_text and metric_text in metrics_map and metric_text not in seen:
                matched.append((metric_text, METRIC_INFERENCE_CODE_MATCH))
                seen.add(metric_text)

    for metric_id, spec in metrics_map.items():
        if metric_id in seen:
            continue
        for code_key in ("sdmx_concepts", "worldbank_indicators", "eurostat_codes", "who_indicators"):
            code_set = {str(v).upper() for v in spec.get(code_key, [])}
            if codes & code_set:
                matched.append((metric_id, METRIC_INFERENCE_CODE_MATCH))
                seen.add(metric_id)
                break
        if metric_id in seen:
            continue
        keywords = [str(v).lower() for v in spec.get("keywords", [])]
        if keywords:
            hits = sum(1 for k in keywords if k in text)
            if hits > 0:
                ratio = hits / len(keywords)
                # Proportional confidence: 1/5 kw → keyword_weak, 3/5+ → keyword_match
                method = METRIC_INFERENCE_KEYWORD_MATCH if ratio >= 0.3 else METRIC_INFERENCE_HEURISTIC
                matched.append((metric_id, method))
                seen.add(metric_id)

    for metric_id, patterns in _HEURISTIC_METRIC_PATTERNS:
        if metric_id in seen:
            continue
        if any(pattern in text for pattern in patterns):
            matched.append((metric_id, METRIC_INFERENCE_HEURISTIC))
            seen.add(metric_id)

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
        polisyos_metrics=(_mm := _map_metrics_both(raw, metrics_map))[0],
        polisyos_metrics_methods=_mm[1],
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
        polisyos_metrics=(_mm := _map_metrics_both(raw, metrics_map))[0],
        polisyos_metrics_methods=_mm[1],
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
        polisyos_metrics=(_mm := _map_metrics_both(raw, metrics_map))[0],
        polisyos_metrics_methods=_mm[1],
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
        polisyos_metrics=(_mm := _map_metrics_both(raw, metrics_map))[0],
        polisyos_metrics_methods=_mm[1],
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
        polisyos_metrics=(_mm := _map_metrics_both(raw, metrics_map))[0],
        polisyos_metrics_methods=_mm[1],
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
        polisyos_metrics=(_mm := _map_metrics_both(raw, metrics_map))[0],
        polisyos_metrics_methods=_mm[1],
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
        polisyos_metrics=(_mm := _map_metrics_both(raw, metrics_map))[0],
        polisyos_metrics_methods=_mm[1],
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
    checkpoint = load_json(config.normalize_checkpoint_path, default={})
    if not isinstance(checkpoint, dict):
        checkpoint = {}
    for source_dir in source_dirs:
        latest_snapshots = sorted([p for p in source_dir.iterdir() if p.is_dir()])
        if not latest_snapshots:
            continue
        latest = latest_snapshots[-1]
        payload = latest / "payload.jsonl"
        out_path = config.normalized_dir / f"{source_dir.name}.jsonl"
        source_fingerprint = fingerprint_paths([payload])
        existing_entry = checkpoint.get(source_dir.name) if isinstance(checkpoint, dict) else None
        if (
            config.resume
            and isinstance(existing_entry, dict)
            and str(existing_entry.get("status")) == "complete"
            and str(existing_entry.get("input_fingerprint", "")) == source_fingerprint
            and out_path.exists()
        ):
            counts[source_dir.name] = sum(
                1 for _line in open(out_path, "r", encoding="utf-8")
            )
            artifacts.append(out_path)
            continue
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
                        endpoint="data/raw/wvs/WVS_Time_Series_1981-2022_csv_v5_0.csv",
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

        with open(out_path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(rec.model_dump_json() + "\n")
        counts[source] = len(records)
        artifacts.append(out_path)
        checkpoint[source] = {
            "status": "complete",
            "input_fingerprint": source_fingerprint,
            "records": len(records),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        write_json(config.normalize_checkpoint_path, checkpoint)

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
    """Map to polisyos metrics helper."""
    return _map_metrics(raw, metrics_map)


def normalize_ckan(raw: dict, source_portal: str, metrics_map: dict | None = None) -> DatasetRecord:
    """Normalize ckan helper."""
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
    """Normalize worldbank helper."""
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
    """Normalize to dcat helper."""
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
                endpoint="data/raw/wvs/WVS_Time_Series_1981-2022_csv_v5_0.csv",
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
