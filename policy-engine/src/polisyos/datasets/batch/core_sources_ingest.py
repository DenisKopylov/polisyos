"""Stage 0b: ingest transportability sources into registry/alignment/observation tables."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp
import duckdb

from polisyos.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.knowledge.variable_alignment import (
    AlignmentMethod,
    VariableAlignment,
    align_semantic,
    load_seed_alignments,
)
from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
from polisyos.fabric.connectors.sources.sdmx_source import SDMXSourceConnector
from polisyos.fabric.connectors.sources.unesco_uis import UNESCOUISConnector
from polisyos.fabric.connectors.sources.unpd import UNPDConnector
from polisyos.fabric.connectors.sources.who import WHOConnector
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.connectors.sources.wvs import WVSConnector

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
_LEGACY_WVS_INDICATORS: dict[str, str] = {
    "A165": "social_trust",
    "A173": "cultural_cluster",
}
_CANONICAL_ROOTS = tuple(sorted(CANONICAL_VARIABLES.keys()))
_PROXY_METRIC_ALIGNMENTS: dict[str, tuple[tuple[str, float, float], ...]] = {
    "health_spending": (("health_outcomes", 0.72, 0.15),),
    "life_expectancy": (("health_outcomes", 0.92, 0.05),),
    "education_spending": (("education_outcomes", 0.72, 0.15),),
}
_CORE_COUNTRIES: tuple[str, ...] = ("UA", "DE", "PL")
_CORE_YEARS: tuple[int, ...] = (2018, 2019, 2020, 2021, 2022)
_ISO2_TO_ISO3 = {"UA": "UKR", "DE": "DEU", "PL": "POL"}
_ISO3_TO_ISO2 = {value: key for key, value in _ISO2_TO_ISO3.items()}
_NUMERIC_TO_ISO2 = {"804": "UA", "276": "DE", "616": "PL"}
_NAME_TO_ISO2 = {"UKRAINE": "UA", "GERMANY": "DE", "POLAND": "PL"}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class CoreSourcesIngestStats:
    registry_datasets: int = 0
    variable_alignments: int = 0
    observations: int = 0
    observations_attempted: int = 0
    observations_inserted: int = 0
    observations_replaced: int = 0
    failures: int = 0


@dataclass(frozen=True)
class ObservationInsertStats:
    attempted: int = 0
    inserted: int = 0
    replaced: int = 0

    @property
    def written(self) -> int:
        return int(self.inserted + self.replaced)

    def __add__(self, other: object) -> "ObservationInsertStats":
        if not isinstance(other, ObservationInsertStats):
            return NotImplemented
        return ObservationInsertStats(
            attempted=self.attempted + other.attempted,
            inserted=self.inserted + other.inserted,
            replaced=self.replaced + other.replaced,
        )

    def __radd__(self, other: object) -> "ObservationInsertStats":
        if other == 0:
            return self
        return self.__add__(other)


@dataclass(frozen=True)
class CatalogTransportDataset:
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
    dataset_id: str
    source: str
    raw_variable: str
    canonical_var: str
    connector_id: str
    profile_id: str
    request_dataset_id: str
    default_filters: dict[str, list[str]]
    update_frequency: str


@dataclass
class _ConnectorSessionCache:
    worldbank: tuple[WorldBankConnector, Any] | None = None
    wvs: tuple[WVSConnector, Any] | None = None
    eurostat: tuple[EurostatConnector, Any] | None = None
    who: tuple[WHOConnector, Any] | None = None
    unpd: tuple[UNPDConnector, Any] | None = None
    unesco_uis: tuple[UNESCOUISConnector, Any] | None = None
    sdmx_by_profile: dict[str, tuple[SDMXSourceConnector, Any]] | None = None

    def __post_init__(self) -> None:
        if self.sdmx_by_profile is None:
            self.sdmx_by_profile = {}

    async def get_worldbank(self) -> tuple[WorldBankConnector, Any]:
        if self.worldbank is None:
            connector = WorldBankConnector()
            handle = await connector.connect(_resolve_profile_config("worldbank_wdi"))
            self.worldbank = (connector, handle)
        return self.worldbank

    async def get_wvs(self) -> tuple[WVSConnector, Any]:
        if self.wvs is None:
            connector = WVSConnector()
            handle = await connector.connect(_resolve_profile_config("wvs_wave7"))
            self.wvs = (connector, handle)
        return self.wvs

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

    async def close(self) -> None:
        if self.worldbank is not None:
            connector, handle = self.worldbank
            await connector.disconnect(handle)
        if self.wvs is not None:
            connector, handle = self.wvs
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
            catalog_alignments = _build_catalog_alignments(catalog_datasets, _seed_alignments_path())
            stats.registry_datasets = _upsert_catalog_registry_datasets(con, catalog_datasets)
            stats.variable_alignments = _upsert_catalog_alignments(con, catalog_alignments)
        else:
            stats.registry_datasets = _upsert_legacy_registry_datasets(con)
            stats.variable_alignments = _upsert_seed_alignments(con, _seed_alignments_path())

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
    return resolve_connection_config(profile)


def _seed_alignments_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )


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
            condition_json VARCHAR DEFAULT '{}'
        );
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_registry_provider "
        "ON ds_registry_datasets(provider)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_va_canonical "
        "ON ds_variable_alignments(canonical_var)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_va_dataset "
        "ON ds_variable_alignments(dataset_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_country_year "
        "ON ds_observations(country_code, year)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_dataset_raw "
        "ON ds_observations(dataset_id, raw_variable)"
    )


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

    if config.promoted_sources:
        source_filter = sorted(set(config.promoted_sources))
    else:
        source_filter = sorted(_TRANSPORT_SOURCES)

    placeholders = ", ".join("?" for _ in source_filter)
    query = f"""
        SELECT
            d.id,
            d.source,
            d.title,
            COALESCE(d.description, ''),
            COALESCE(NULLIF(d.source_dataset_id, ''), NULLIF(d.dataset_id, ''), d.id),
            COALESCE(d.update_frequency, ''),
            COALESCE(d.last_updated, CURRENT_DATE::VARCHAR),
            json_object(
                'countries', COALESCE(d.coverage_countries, []),
                'regions', COALESCE(d.coverage_regions, []),
                'time_range',
                    CASE
                        WHEN COALESCE(d.coverage_time_start, d.temporal_start, '') != ''
                             OR COALESCE(d.coverage_time_end, d.temporal_end, '') != ''
                        THEN COALESCE(d.coverage_time_start, d.temporal_start, '')
                             || ':'
                             || COALESCE(d.coverage_time_end, d.temporal_end, '')
                        ELSE ''
                    END,
                'granularity', COALESCE(d.coverage_granularity, 'annual')
            ) AS coverage_json,
            json_object(
                'access_type', 'open',
                'api_endpoint', COALESCE(d.access_api_endpoint, ''),
                'bulk_download_url', COALESCE(d.access_bulk_download_url, ''),
                'license', COALESCE(d.access_license, d.license, ''),
                'auth_required', COALESCE(d.access_auth_required, FALSE)
            ) AS access_json,
            COALESCE(d.execution_tier, 'catalog'),
            COALESCE(d.variables, []),
            COALESCE(d.keywords, []),
            COALESCE(d.themes, []),
            COALESCE(d.polisyos_metrics, []),
            COALESCE(dist.connector_type, ''),
            COALESCE(dist.profile_id, ''),
            COALESCE(NULLIF(dist.source_locator, ''), COALESCE(NULLIF(d.source_dataset_id, ''), NULLIF(d.dataset_id, ''), d.id)),
            COALESCE(CAST(dist.default_filters AS VARCHAR), '{{}}')
        FROM ds_datasets AS d
        LEFT JOIN ds_distributions AS dist ON dist.id = d.preferred_distribution_id
        WHERE d.source IN ({placeholders})
    """
    rows = con.execute(query, source_filter).fetchall()
    if not rows:
        return []

    out: list[CatalogTransportDataset] = []
    for row in rows:
        execution_tier = str(row[9] or "catalog")
        source = str(row[1] or "")
        if execution_tier == "catalog" and source not in {"who", "unpd", "unesco_uis"}:
            continue
        out.append(
            CatalogTransportDataset(
                catalog_dataset_id=str(row[0]),
                source=source,
                title=str(row[2] or ""),
                description=str(row[3] or ""),
                source_dataset_id=str(row[4] or ""),
                update_frequency=str(row[5] or ""),
                last_updated=str(row[6] or ""),
                coverage_json=str(row[7] or "{}"),
                access_json=str(row[8] or "{}"),
                execution_tier=execution_tier,
                variables=tuple(str(value) for value in list(row[10] or [])),
                keywords=tuple(str(value) for value in list(row[11] or [])),
                themes=tuple(str(value) for value in list(row[12] or [])),
                polisyos_metrics=tuple(str(value) for value in list(row[13] or [])),
                connector_id=str(row[14] or ""),
                profile_id=str(row[15] or ""),
                request_dataset_id=str(row[16] or ""),
                default_filters=_load_json_dict(row[17]),
            )
        )
    return out


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
        dataset_text_tokens = _tokenize(" ".join((dataset.title, dataset.description, *candidate_vars, *dataset.keywords)))

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
                raw_var = dataset.source_dataset_id or (candidate_vars[0] if candidate_vars else metric)
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
            for canonical_var, confidence, proxy_penalty in _PROXY_METRIC_ALIGNMENTS.get(metric, ()):
                raw_var = dataset.source_dataset_id or (candidate_vars[0] if candidate_vars else metric)
                _remember_alignment(
                    best,
                    VariableAlignment(
                        canonical_var=canonical_var,
                        dataset_var=raw_var,
                        dataset_id=dataset.catalog_dataset_id,
                        method=AlignmentMethod.SEMANTIC,
                        confidence=confidence,
                        evidence=f"metric_binding_proxy:{metric}",
                        is_proxy=True,
                        proxy_penalty=proxy_penalty,
                    ),
                )

        semantic_candidates = [
            canonical_var
            for canonical_var in _CANONICAL_ROOTS
            if _tokenize(canonical_var.replace("_", " ")) & dataset_text_tokens
        ]
        if dataset.source in {"worldbank", "eurostat", "oecd", "ilo", "who", "unpd", "wvs", "unesco_uis"}:
            semantic_candidates.extend(metric for metric in dataset.polisyos_metrics if metric in _CANONICAL_ROOTS)
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


def _build_catalog_observation_plans(
    datasets: list[CatalogTransportDataset],
    alignments: list[VariableAlignment],
    *,
    config: DatasetBatchConfig,
) -> list[ObservationPlan]:
    by_dataset = {item.catalog_dataset_id: item for item in datasets}
    plans: list[ObservationPlan] = []
    seen: set[tuple[str, str, str]] = set()
    for alignment in alignments:
        dataset = by_dataset.get(alignment.dataset_id)
        if dataset is None:
            continue
        if dataset.source not in _TRANSPORT_SOURCES:
            continue
        if alignment.confidence < 0.55:
            continue
        request_dataset_id = dataset.request_dataset_id or dataset.source_dataset_id or alignment.dataset_var
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
            )
        )
    return _limit_observation_plans(plans, datasets, config=config)


def _observation_plan_limit_per_source(config: DatasetBatchConfig) -> int | None:
    if not config.is_sampled_run:
        return None
    base = max(int(config.max_datasets_per_source), 1)
    return max(base, min(base + 2, 6))


def _observation_failure_budget_per_source(config: DatasetBatchConfig) -> int:
    if config.is_sampled_run:
        capped = _observation_plan_limit_per_source(config) or 1
        return max(2, min(capped, 4))
    return 10


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
            dataset_rank.get(item.dataset_id, (9, 9, item.dataset_id)),
            item.canonical_var,
            item.raw_variable,
        ),
    )
    if limit is None:
        return ordered

    grouped: dict[str, list[ObservationPlan]] = {}
    for plan in ordered:
        grouped.setdefault(plan.source, []).append(plan)

    out: list[ObservationPlan] = []
    trimmed = 0
    for source, source_plans in grouped.items():
        selected: list[ObservationPlan] = []
        seen_keys: set[tuple[str, str, str]] = set()
        seen_canonical: set[str] = set()

        for plan in source_plans:
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


async def _ingest_catalog_observations(
    db_path: Path,
    plans: list[ObservationPlan],
    *,
    config: DatasetBatchConfig,
) -> CoreSourcesIngestStats:
    stats = CoreSourcesIngestStats()
    cache = _ConnectorSessionCache()
    failure_budget = _observation_failure_budget_per_source(config)
    failures_by_source: dict[str, int] = {}
    skipped_sources: set[str] = set()
    try:
        with duckdb.connect(str(db_path)) as con:
            for plan in plans:
                if failures_by_source.get(plan.source, 0) >= failure_budget:
                    if plan.source not in skipped_sources:
                        skipped_sources.add(plan.source)
                        logger.warning(
                            "Skipping remaining observation plans for {} after {} failures",
                            plan.source,
                            failures_by_source[plan.source],
                        )
                    continue
                try:
                    rows = await _fetch_observation_rows(plan, cache, config=config)
                except Exception as exc:
                    stats.failures += 1
                    failures_by_source[plan.source] = failures_by_source.get(plan.source, 0) + 1
                    logger.warning(
                        "Observation ingest failed for {}/{}: {}",
                        plan.source,
                        plan.request_dataset_id,
                        exc,
                    )
                    continue
                _merge_observation_stats(stats, _insert_generic_observations(con=con, plan=plan, rows=rows))
            con.execute("CHECKPOINT")
    finally:
        await cache.close()
    return stats


async def _fetch_observation_rows(
    plan: ObservationPlan,
    cache: _ConnectorSessionCache,
    *,
    config: DatasetBatchConfig,
) -> list[dict[str, Any]]:
    if plan.source == "worldbank":
        connector, handle = await cache.get_worldbank()
        rows: list[dict[str, Any]] = []
        for country in _CORE_COUNTRIES:
            result = await connector.fetch(
                handle,
                FetchRequest(
                    dataset_id=plan.request_dataset_id,
                    filters=(("country", (country,)),),
                    date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                    date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                ),
            )
            rows.extend(_records_from_payload(result.data))
        return rows

    if plan.source == "wvs":
        connector, handle = await cache.get_wvs()
        rows: list[dict[str, Any]] = []
        for country in _CORE_COUNTRIES:
            for year in _CORE_YEARS:
                result = await connector.fetch(
                    handle,
                    FetchRequest(
                        dataset_id=plan.request_dataset_id,
                        filters=(
                            ("country", (country,)),
                            ("survey_year", (str(year),)),
                        ),
                    ),
                )
                rows.extend(_records_from_payload(result.data))
        return rows

    if plan.source == "eurostat":
        connector, handle = await cache.get_eurostat()
        requests = [
            FetchRequest(
                dataset_id=plan.request_dataset_id,
                filters=(("geo", (country,)),),
                date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                page_size=200,
            )
            for country in _observation_countries(plan.source, config=config)
        ]
        if config.is_sampled_run:
            requests.append(
                FetchRequest(
                    dataset_id=plan.request_dataset_id,
                    filters=(),
                    date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                    date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                    page_size=200,
                )
            )
        return await _fetch_request_variants(
            connector,
            handle,
            requests,
            stop_after_first_success=config.is_sampled_run,
        )

    if plan.source in {"oecd", "ilo"}:
        profile_id = plan.profile_id or ("oecd_sdmx" if plan.source == "oecd" else "ilo_sdmx")
        connector, handle = await cache.get_sdmx(profile_id)
        requests: list[FetchRequest] = []
        for country in _observation_countries(plan.source, config=config):
            filters = _sdmx_filters_for_country(country, base_filters=plan.default_filters)
            requests.append(
                FetchRequest(
                    dataset_id=plan.request_dataset_id,
                    filters=_filters_to_tuple(filters),
                    date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                    date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                    page_size=200,
                )
            )
        if config.is_sampled_run:
            fallback_filters = _strip_geo_filters(plan.default_filters)
            requests.append(
                FetchRequest(
                    dataset_id=plan.request_dataset_id,
                    filters=_filters_to_tuple(fallback_filters),
                    date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                    date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                    page_size=200,
                )
            )
        return await _fetch_request_variants(
            connector,
            handle,
            requests,
            stop_after_first_success=config.is_sampled_run,
        )

    if plan.source == "who":
        connector, handle = await cache.get_who()
        rows: list[dict[str, Any]] = []
        for country in _CORE_COUNTRIES:
            result = await connector.fetch(
                handle,
                FetchRequest(
                    dataset_id=plan.request_dataset_id,
                    filters=(("country", (country,)),),
                    date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                    date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                )
            )
            rows.extend(_records_from_payload(result.data))
        return rows

    if plan.source == "unpd":
        connector, handle = await cache.get_unpd()
        rows: list[dict[str, Any]] = []
        for country in _CORE_COUNTRIES:
            result = await connector.fetch(
                handle,
                FetchRequest(
                    dataset_id=plan.request_dataset_id,
                    filters=(("country", (country,)),),
                    date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                    date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                )
            )
            rows.extend(_records_from_payload(result.data))
        return rows

    if plan.source == "unesco_uis":
        connector, handle = await cache.get_unesco_uis()
        rows: list[dict[str, Any]] = []
        for country in _CORE_COUNTRIES:
            result = await connector.fetch(
                handle,
                FetchRequest(
                    dataset_id=plan.request_dataset_id,
                    filters=(("country", (country,)),),
                    date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                    date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                )
            )
            rows.extend(_records_from_payload(result.data))
        return rows

    return []


async def _fetch_request_variants(
    connector: Any,
    handle: Any,
    requests: list[FetchRequest],
    *,
    stop_after_first_success: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    last_exc: Exception | None = None
    for request in requests:
        try:
            result = await connector.fetch(handle, request)
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


async def _legacy_ingest_observations(db_path: Path) -> CoreSourcesIngestStats:
    stats = CoreSourcesIngestStats()
    wb = WorldBankConnector()
    wvs = WVSConnector()
    wb_handle = None
    wvs_handle = None
    try:
        wb_handle = await wb.connect(_resolve_profile_config("worldbank_wdi"))
        wvs_handle = await wvs.connect(_resolve_profile_config("wvs_wave7"))

        with duckdb.connect(str(db_path)) as con:
            for country in _CORE_COUNTRIES:
                for indicator, canonical_var in _LEGACY_WGI_INDICATORS.items():
                    try:
                        result = await wb.fetch(
                            wb_handle,
                            FetchRequest(
                                dataset_id=indicator,
                                filters=(("country", (country,)),),
                                date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                                date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                            ),
                        )
                        _merge_observation_stats(stats, _insert_generic_observations(
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
                        ))
                    except Exception as exc:
                        stats.failures += 1
                        logger.warning("Legacy WGI ingest failed for {}/{}: {}", country, indicator, exc)

                for indicator, canonical_var in _LEGACY_WDI_INDICATORS.items():
                    try:
                        result = await wb.fetch(
                            wb_handle,
                            FetchRequest(
                                dataset_id=indicator,
                                filters=(("country", (country,)),),
                                date_start=datetime(min(_CORE_YEARS), 1, 1, tzinfo=UTC),
                                date_end=datetime(max(_CORE_YEARS), 12, 31, tzinfo=UTC),
                            ),
                        )
                        _merge_observation_stats(stats, _insert_generic_observations(
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
                        ))
                    except Exception as exc:
                        stats.failures += 1
                        logger.warning("Legacy WDI ingest failed for {}/{}: {}", country, indicator, exc)

                for indicator, canonical_var in _LEGACY_WVS_INDICATORS.items():
                    for year in _CORE_YEARS:
                        try:
                            result = await wvs.fetch(
                                wvs_handle,
                                FetchRequest(
                                    dataset_id=indicator,
                                    filters=(("country", (country,)), ("survey_year", (str(year),))),
                                ),
                            )
                            _merge_observation_stats(stats, _insert_generic_observations(
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
                                rows=_records_from_payload(result.data),
                            ))
                        except Exception as exc:
                            stats.failures += 1
                            logger.warning("Legacy WVS ingest failed for {}/{}/{}: {}", country, indicator, year, exc)
            con.execute("CHECKPOINT")
    finally:
        if wb_handle is not None:
            await wb.disconnect(wb_handle)
        if wvs_handle is not None:
            await wvs.disconnect(wvs_handle)
    return stats


def _upsert_legacy_registry_datasets(con: duckdb.DuckDBPyConnection) -> int:
    last_updated = datetime.now(UTC).date().isoformat()
    datasets = [
        (
            "WB_WGI",
            "worldbank",
            "World Governance Indicators",
            json.dumps({"countries": [], "time_range": "1996-2023", "granularity": "country-year"}, separators=(",", ":")),
            json.dumps({"access_type": "open", "api_endpoint": "https://api.worldbank.org/v2", "license": "CC-BY-4.0"}, separators=(",", ":")),
            "annual",
            last_updated,
        ),
        (
            "WB_WDI",
            "worldbank",
            "World Development Indicators",
            json.dumps({"countries": [], "time_range": "1960-2023", "granularity": "country-year"}, separators=(",", ":")),
            json.dumps({"access_type": "open", "api_endpoint": "https://api.worldbank.org/v2", "license": "CC-BY-4.0"}, separators=(",", ":")),
            "annual",
            last_updated,
        ),
        (
            "WVS_W7",
            "wvs",
            "World Values Survey Wave 7",
            json.dumps({"countries": [], "time_range": "2017-2022", "granularity": "country-wave"}, separators=(",", ":")),
            json.dumps({"access_type": "open", "api_endpoint": "https://api.worldvaluessurvey.org/v1", "license": "WVS terms"}, separators=(",", ":")),
            "wave",
            last_updated,
        ),
        (
            "IMF_SHADOW",
            "imf",
            "IMF Shadow Economy Estimates",
            json.dumps({"countries": [], "time_range": "1990-2022", "granularity": "country-year"}, separators=(",", ":")),
            json.dumps({"access_type": "open", "api_endpoint": "", "license": "IMF terms"}, separators=(",", ":")),
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
) -> ObservationInsertStats:
    if not rows:
        return ObservationInsertStats()
    attempted = 0
    unique_rows: dict[str, tuple] = {}
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
        )
    if not unique_rows:
        return ObservationInsertStats()
    existing_ids = _existing_observation_ids(con, tuple(unique_rows))
    inserted = len(unique_rows) - len(existing_ids)
    replaced = len(existing_ids)
    con.executemany(
        "INSERT OR REPLACE INTO ds_observations "
        "(observation_id, dataset_id, raw_variable, canonical_var, country_code, "
        "year, survey_year, wave, value, condition_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        list(unique_rows.values()),
    )
    return ObservationInsertStats(
        attempted=attempted,
        inserted=inserted,
        replaced=replaced,
    )


def _merge_observation_stats(
    stats: CoreSourcesIngestStats,
    inserted: ObservationInsertStats,
) -> None:
    stats.observations += inserted.written
    stats.observations_attempted += inserted.attempted
    stats.observations_inserted += inserted.inserted
    stats.observations_replaced += inserted.replaced


def _existing_observation_ids(
    con: duckdb.DuckDBPyConnection,
    observation_ids: tuple[str, ...],
) -> set[str]:
    if not observation_ids:
        return set()
    matches: set[str] = set()
    chunk_size = 512
    for start in range(0, len(observation_ids), chunk_size):
        chunk = observation_ids[start : start + chunk_size]
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

    survey_year = _as_int(
        payload.pop("survey_year", None)
        or payload.pop("SurveyYear", None)
    )
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

    for ignored in ("dataset_id", "observation_index", "unit", "__country_code"):
        payload.pop(ignored, None)
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


def _sdmx_filters_for_country(country_code: str, *, base_filters: dict[str, list[str]]) -> dict[str, list[str]]:
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


def _strip_geo_filters(filters: dict[str, list[str]]) -> dict[str, list[str]]:
    blocked = {"geo", "country", "ref_area", "REF_AREA"}
    return {
        key: list(values)
        for key, values in (filters or {}).items()
        if key not in blocked
    }


def _observation_countries(source: str, *, config: DatasetBatchConfig) -> tuple[str, ...]:
    if config.is_sampled_run and source in {"eurostat", "oecd", "ilo"}:
        return ("UA",)
    return _CORE_COUNTRIES


def _filters_to_tuple(filters: dict[str, list[str]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple((key, tuple(values)) for key, values in sorted(filters.items()))


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
    if value is None:
        return ""
    text = str(value).strip().upper()
    if not text:
        return ""
    if text in _ISO2_TO_ISO3:
        return text
    if text in _ISO3_TO_ISO2:
        return _ISO3_TO_ISO2[text]
    if text in _NUMERIC_TO_ISO2:
        return _NUMERIC_TO_ISO2[text]
    if text in _NAME_TO_ISO2:
        return _NAME_TO_ISO2[text]
    return ""


def _to_iso3(country_code: str) -> str:
    cc = (country_code or "").strip().upper()
    return _ISO2_TO_ISO3.get(cc, cc)


def _country_to_numeric(country_code: str) -> str:
    cc = (country_code or "").strip().upper()
    for numeric, iso2 in _NUMERIC_TO_ISO2.items():
        if iso2 == cc:
            return numeric
    return cc


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
