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
