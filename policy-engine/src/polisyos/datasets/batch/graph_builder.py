"""Stage 4/5: Load merged dataset records into DuckDB and build indexes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import duckdb

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.common.logger import get_logger
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.batch.normalizer import METRIC_INFERENCE_CONFIDENCE
from polisyos.datasets.knowledge.types import DatasetRecord, DistributionRecord

logger = get_logger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS ds_datasets (
    id                                 VARCHAR PRIMARY KEY,
    source                             VARCHAR,
    agency                             VARCHAR,
    dataset_id                         VARCHAR,
    source_dataset_id                  VARCHAR,
    dedup_key                          VARCHAR,
    title                              VARCHAR NOT NULL,
    description                        VARCHAR,
    publisher                          VARCHAR,
    spatial                            VARCHAR,
    temporal_start                     VARCHAR,
    temporal_end                       VARCHAR,
    license                            VARCHAR,
    source_portal                      VARCHAR,
    execution_tier                     VARCHAR DEFAULT 'catalog',
    update_frequency                   VARCHAR,
    last_updated                       VARCHAR,
    polisyos_metrics                   VARCHAR[],
    keywords                           VARCHAR[],
    themes                             VARCHAR[],
    variables                          VARCHAR[],
    formats                            VARCHAR[],
    coverage_countries                 VARCHAR[],
    coverage_regions                   VARCHAR[],
    coverage_time_start                VARCHAR,
    coverage_time_end                  VARCHAR,
    coverage_granularity               VARCHAR,
    access_api_endpoint                VARCHAR,
    access_bulk_download_url           VARCHAR,
    access_license                     VARCHAR,
    access_auth_required               BOOLEAN DEFAULT FALSE,
    quality_description_score          FLOAT DEFAULT 0.0,
    quality_machine_readable_score     FLOAT DEFAULT 0.0,
    quality_parser_support_score       FLOAT DEFAULT 0.0,
    quality_freshness_score            FLOAT DEFAULT 0.0,
    quality_execution_readiness_score  FLOAT DEFAULT 0.0,
    preferred_distribution_id          VARCHAR,
    updated_at                         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ds_distributions (
    id                   VARCHAR PRIMARY KEY,
    dataset_id           VARCHAR NOT NULL,
    url                  VARCHAR,
    format               VARCHAR,
    name                 VARCHAR,
    connector_type       VARCHAR,
    connector_params     JSON,
    source_locator       VARCHAR,
    profile_id           VARCHAR,
    media_type           VARCHAR,
    machine_readable     BOOLEAN DEFAULT FALSE,
    parser_supported     BOOLEAN DEFAULT FALSE,
    size_estimate_bytes  BIGINT,
    checksum             VARCHAR,
    default_filters      JSON,
    quality_score        FLOAT DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ds_metric_bindings (
    metric_id                  VARCHAR NOT NULL,
    dataset_id                 VARCHAR NOT NULL,
    distribution_id            VARCHAR NOT NULL,
    connector_id               VARCHAR NOT NULL,
    profile_id                 VARCHAR,
    request_dataset_id         VARCHAR NOT NULL,
    confidence                 FLOAT DEFAULT 0.0,
    metric_inference_confidence FLOAT DEFAULT 0.0,
    default_filters            JSON,
    execution_tier             VARCHAR DEFAULT 'catalog',
    source                     VARCHAR,
    PRIMARY KEY (metric_id, dataset_id, distribution_id)
);

CREATE TABLE IF NOT EXISTS ds_schema_profiles (
    distribution_id          VARCHAR PRIMARY KEY,
    dataset_id               VARCHAR NOT NULL,
    columns_json             JSON NOT NULL,
    inferred_time_column     VARCHAR,
    inferred_geography_column VARCHAR,
    inferred_value_columns   VARCHAR[],
    sample_row_count         INTEGER DEFAULT 0,
    preview_sample_hash      VARCHAR,
    inference_mode           VARCHAR DEFAULT 'metadata_only',
    parser_mode              VARCHAR DEFAULT 'metadata_only',
    format_notes_json        JSON DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS ds_registry_datasets (
    dataset_id    VARCHAR PRIMARY KEY,
    provider      VARCHAR NOT NULL,
    title         VARCHAR NOT NULL,
    coverage_json VARCHAR NOT NULL,
    access_json   VARCHAR NOT NULL,
    update_freq   VARCHAR NOT NULL,
    last_updated  VARCHAR NOT NULL
);

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

CREATE TABLE IF NOT EXISTS ds_alignment_audit (
    audit_id               VARCHAR PRIMARY KEY,
    dataset_id             VARCHAR NOT NULL,
    raw_variable           VARCHAR NOT NULL,
    canonical_variable     VARCHAR,
    method                 VARCHAR NOT NULL,
    raw_confidence         FLOAT,
    calibrated_confidence  FLOAT,
    alternatives_json      JSON DEFAULT '[]',
    resolved_at            VARCHAR,
    reviewed               BOOLEAN DEFAULT FALSE,
    reviewer_override      VARCHAR DEFAULT NULL
);

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

CREATE TABLE IF NOT EXISTS ds_entity_mappings (
    mapping_id      VARCHAR PRIMARY KEY,
    dataset_id      VARCHAR NOT NULL,
    source          VARCHAR NOT NULL,
    entity_id       VARCHAR NOT NULL,
    entity_label    VARCHAR,
    entity_type     VARCHAR,
    external_id     VARCHAR,
    alias_json      JSON DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS ds_alignment_hints (
    hint_id         VARCHAR PRIMARY KEY,
    dataset_id      VARCHAR NOT NULL,
    canonical_var   VARCHAR NOT NULL,
    hint_type       VARCHAR NOT NULL,
    confidence      FLOAT DEFAULT 0.0,
    evidence_json   JSON DEFAULT '{}'
);
"""

_ALTERS = """
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS source_dataset_id VARCHAR;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS execution_tier VARCHAR DEFAULT 'catalog';
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS update_frequency VARCHAR;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS last_updated VARCHAR;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS coverage_countries VARCHAR[];
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS coverage_regions VARCHAR[];
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS coverage_time_start VARCHAR;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS coverage_time_end VARCHAR;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS coverage_granularity VARCHAR;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS access_api_endpoint VARCHAR;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS access_bulk_download_url VARCHAR;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS access_license VARCHAR;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS access_auth_required BOOLEAN DEFAULT FALSE;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS quality_description_score FLOAT DEFAULT 0.0;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS quality_machine_readable_score FLOAT DEFAULT 0.0;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS quality_parser_support_score FLOAT DEFAULT 0.0;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS quality_freshness_score FLOAT DEFAULT 0.0;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS quality_execution_readiness_score FLOAT DEFAULT 0.0;
ALTER TABLE ds_datasets ADD COLUMN IF NOT EXISTS preferred_distribution_id VARCHAR;
ALTER TABLE ds_distributions ADD COLUMN IF NOT EXISTS source_locator VARCHAR;
ALTER TABLE ds_distributions ADD COLUMN IF NOT EXISTS profile_id VARCHAR;
ALTER TABLE ds_distributions ADD COLUMN IF NOT EXISTS media_type VARCHAR;
ALTER TABLE ds_distributions ADD COLUMN IF NOT EXISTS machine_readable BOOLEAN DEFAULT FALSE;
ALTER TABLE ds_distributions ADD COLUMN IF NOT EXISTS parser_supported BOOLEAN DEFAULT FALSE;
ALTER TABLE ds_distributions ADD COLUMN IF NOT EXISTS size_estimate_bytes BIGINT;
ALTER TABLE ds_distributions ADD COLUMN IF NOT EXISTS checksum VARCHAR;
ALTER TABLE ds_distributions ADD COLUMN IF NOT EXISTS default_filters JSON;
ALTER TABLE ds_schema_profiles ADD COLUMN IF NOT EXISTS parser_mode VARCHAR DEFAULT 'metadata_only';
ALTER TABLE ds_schema_profiles ADD COLUMN IF NOT EXISTS format_notes_json JSON DEFAULT '{}';
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_ds_source ON ds_datasets(source);
CREATE INDEX IF NOT EXISTS idx_ds_agency ON ds_datasets(agency);
CREATE INDEX IF NOT EXISTS idx_ds_dedup_key ON ds_datasets(dedup_key);
CREATE INDEX IF NOT EXISTS idx_ds_publisher ON ds_datasets(publisher);
CREATE INDEX IF NOT EXISTS idx_ds_portal ON ds_datasets(source_portal);
CREATE INDEX IF NOT EXISTS idx_ds_exec_tier ON ds_datasets(execution_tier);
CREATE INDEX IF NOT EXISTS idx_ds_preferred_dist ON ds_datasets(preferred_distribution_id);
CREATE INDEX IF NOT EXISTS idx_dist_dataset ON ds_distributions(dataset_id);
CREATE INDEX IF NOT EXISTS idx_dist_connector ON ds_distributions(connector_type);
CREATE INDEX IF NOT EXISTS idx_dist_parser ON ds_distributions(parser_supported);
CREATE INDEX IF NOT EXISTS idx_binding_metric ON ds_metric_bindings(metric_id);
CREATE INDEX IF NOT EXISTS idx_binding_dataset ON ds_metric_bindings(dataset_id);
CREATE INDEX IF NOT EXISTS idx_schema_dataset ON ds_schema_profiles(dataset_id);
CREATE INDEX IF NOT EXISTS idx_registry_provider ON ds_registry_datasets(provider);
CREATE INDEX IF NOT EXISTS idx_va_canonical ON ds_variable_alignments(canonical_var);
CREATE INDEX IF NOT EXISTS idx_va_dataset ON ds_variable_alignments(dataset_id);
CREATE INDEX IF NOT EXISTS idx_alignment_audit_dataset ON ds_alignment_audit(dataset_id);
CREATE INDEX IF NOT EXISTS idx_obs_country_year ON ds_observations(country_code, year);
CREATE INDEX IF NOT EXISTS idx_obs_dataset_raw ON ds_observations(dataset_id, raw_variable);
CREATE INDEX IF NOT EXISTS idx_entity_mapping_dataset ON ds_entity_mappings(dataset_id);
CREATE INDEX IF NOT EXISTS idx_alignment_hint_dataset ON ds_alignment_hints(dataset_id);
"""

_TIME_HINTS = ("time", "year", "date", "period")
_GEO_HINTS = ("country", "geo", "region", "territory", "geography", "area")


@dataclass
class GraphStats:
    """Graph stats public type."""
    datasets: int = 0
    distributions: int = 0
    metric_bindings: int = 0
    schema_profiles: int = 0
    entity_mappings: int = 0
    alignment_hints: int = 0


def _run_statements(con: duckdb.DuckDBPyConnection, sql_blob: str) -> None:
    for stmt in sql_blob.strip().split(";"):
        sql = stmt.strip()
        if sql:
            con.execute(sql)


def _init_schema(con: duckdb.DuckDBPyConnection) -> None:
    _run_statements(con, _DDL)
    _run_statements(con, _ALTERS)


def _truncate(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DELETE FROM ds_metric_bindings")
    con.execute("DELETE FROM ds_schema_profiles")
    con.execute("DELETE FROM ds_alignment_audit")
    con.execute("DELETE FROM ds_alignment_hints")
    con.execute("DELETE FROM ds_entity_mappings")
    con.execute("DELETE FROM ds_distributions")
    con.execute("DELETE FROM ds_datasets")


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _preferred_distribution(record: DatasetRecord) -> DistributionRecord | None:
    if not record.distributions:
        return None
    return sorted(
        record.distributions,
        key=lambda item: (
            0 if item.id == record.preferred_distribution_id else 1,
            -int(item.parser_supported),
            -int(item.machine_readable),
            -item.quality_score,
            item.id,
        ),
    )[0]


def _infer_time_column(record: DatasetRecord) -> str:
    for value in record.variables:
        lowered = value.lower()
        if any(token in lowered for token in _TIME_HINTS):
            return value
    return "time" if (record.temporal_start or record.temporal_end) else ""


def _infer_geography_column(record: DatasetRecord) -> str:
    for value in record.variables:
        lowered = value.lower()
        if any(token in lowered for token in _GEO_HINTS):
            return value
    return "country" if (record.coverage.countries or record.spatial) else ""


def _infer_value_columns(record: DatasetRecord, *, time_col: str, geo_col: str) -> list[str]:
    excluded = {time_col, geo_col, ""}
    values = [value for value in record.variables if value not in excluded]
    if values:
        return values[:8]
    return ["value"]


def _schema_profile_row(record: DatasetRecord, distribution: DistributionRecord) -> tuple:
    preview_columns = [
        str(value).strip()
        for value in (distribution.connector_params.get("schema_fields") or [])
        if str(value).strip()
    ]
    time_col = _infer_time_column(record)
    geo_col = _infer_geography_column(record)
    value_cols = _infer_value_columns(record, time_col=time_col, geo_col=geo_col)
    if preview_columns:
        value_cols = [value for value in preview_columns if value not in {time_col, geo_col, ""}] or value_cols
    columns_json = [
        {"name": name, "inference_source": "preview" if preview_columns else "metadata"}
        for name in (preview_columns or record.variables or value_cols)
    ]
    sample_row_count = int(distribution.connector_params.get("row_count_estimate") or 0)
    parser_mode = _schema_parser_mode(distribution)
    format_notes = {
        "format": distribution.format,
        "media_type": distribution.media_type,
        "profile_id": distribution.profile_id,
        "machine_readable": bool(distribution.machine_readable),
        "parser_supported": bool(distribution.parser_supported),
    }
    preview_hash = hashlib.sha256(
        _json_text(
            {
                "dataset_id": record.id,
                "distribution_id": distribution.id,
                "columns": columns_json,
                "parser_mode": parser_mode,
                "format_notes": format_notes,
            }
        ).encode("utf-8")
    ).hexdigest()[:16]
    return (
        distribution.id,
        record.id,
        _json_text(columns_json),
        time_col or None,
        geo_col or None,
        value_cols,
        sample_row_count,
        preview_hash,
        "preview_metadata" if preview_columns or sample_row_count else "metadata_only",
        parser_mode,
        _json_text(format_notes),
    )


def _schema_parser_mode(distribution: DistributionRecord) -> str:
    connector = (distribution.connector_type or "").strip()
    if connector == "ckan.resource":
        return "file_parser"
    if connector in {
        "worldbank.wdi",
        "ukons.datasets",
        "eurostat.data",
        "sdmx.source",
        "who.indicators",
        "unpd.data",
        "unesco_uis.data",
        "wvs.wave7",
        "rest.json",
    }:
        return "api_tabular"
    if connector in {"opendatasoft.ods", "socrata.soda"}:
        return "api_catalog"
    if connector == "sparql.endpoint":
        return "linked_data"
    return "metadata_only"


def _metric_binding_rows(record: DatasetRecord, distribution: DistributionRecord | None) -> list[tuple]:
    if distribution is None:
        return []
    if (distribution.connector_type or "").strip() == "sparql.endpoint":
        return []
    request_dataset_id = distribution.source_locator or record.source_dataset_id or record.dataset_id
    if not request_dataset_id or not distribution.connector_type:
        return []
    confidence = max(
        0.05,
        min(
            1.0,
            float(record.quality.execution_readiness_score or 0.0) or float(distribution.quality_score or 0.0) or 0.5,
        ),
    )
    methods = record.polisyos_metrics_methods or {}
    return [
        (
            metric_id,
            record.id,
            distribution.id,
            distribution.connector_type,
            distribution.profile_id,
            request_dataset_id,
            confidence,
            METRIC_INFERENCE_CONFIDENCE.get(methods.get(metric_id, ""), 0.0),
            _json_text(distribution.default_filters or {}),
            record.execution_tier or "catalog",
            record.source,
        )
        for metric_id in record.polisyos_metrics
    ]


def _entity_mapping_rows(record: DatasetRecord, distribution: DistributionRecord | None) -> list[tuple]:
    if distribution is None or (distribution.connector_type or "").strip() != "sparql.endpoint":
        return []
    alias_values = [
        item
        for item in [record.title, *record.keywords[:8], *record.themes[:4]]
        if item
    ]
    return [
        (
            _stable_mapping_id(record.id, "entity"),
            record.id,
            record.source,
            record.source_dataset_id or record.dataset_id or record.id,
            record.title,
            "linked_dataset",
            distribution.source_locator or record.source_dataset_id or record.dataset_id or record.id,
            _json_text(alias_values),
        )
    ]


def _alignment_hint_rows(record: DatasetRecord, distribution: DistributionRecord | None) -> list[tuple]:
    if distribution is None or (distribution.connector_type or "").strip() != "sparql.endpoint":
        return []
    return [
        (
            _stable_mapping_id(record.id, f"hint:{metric_id}"),
            record.id,
            metric_id,
            "linked_data_alignment",
            0.55,
            _json_text(
                {
                    "source": record.source,
                    "title": record.title,
                    "keywords": record.keywords[:10],
                    "themes": record.themes[:6],
                }
            ),
        )
        for metric_id in record.polisyos_metrics
    ]


def _stable_mapping_id(*parts: str, size: int = 20) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:size]


def _flush_datasets(con: duckdb.DuckDBPyConnection, batch: list[tuple], stats: GraphStats) -> None:
    if not batch:
        return
    con.executemany(
        """INSERT OR REPLACE INTO ds_datasets (
            id, source, agency, dataset_id, source_dataset_id, dedup_key,
            title, description, publisher, spatial,
            temporal_start, temporal_end, license, source_portal,
            execution_tier, update_frequency, last_updated,
            polisyos_metrics, keywords, themes, variables, formats,
            coverage_countries, coverage_regions, coverage_time_start, coverage_time_end, coverage_granularity,
            access_api_endpoint, access_bulk_download_url, access_license, access_auth_required,
            quality_description_score, quality_machine_readable_score, quality_parser_support_score,
            quality_freshness_score, quality_execution_readiness_score,
            preferred_distribution_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        batch,
    )
    stats.datasets += len(batch)
    batch.clear()


def _flush_distributions(con: duckdb.DuckDBPyConnection, batch: list[tuple], stats: GraphStats) -> None:
    if not batch:
        return
    con.executemany(
        """INSERT OR REPLACE INTO ds_distributions (
            id, dataset_id, url, format, name,
            connector_type, connector_params, source_locator, profile_id, media_type,
            machine_readable, parser_supported, size_estimate_bytes, checksum, default_filters,
            quality_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        batch,
    )
    stats.distributions += len(batch)
    batch.clear()


def _flush_metric_bindings(con: duckdb.DuckDBPyConnection, batch: list[tuple], stats: GraphStats) -> None:
    if not batch:
        return
    con.executemany(
        """INSERT OR REPLACE INTO ds_metric_bindings (
            metric_id, dataset_id, distribution_id, connector_id, profile_id,
            request_dataset_id, confidence, metric_inference_confidence,
            default_filters, execution_tier, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        batch,
    )
    stats.metric_bindings += len(batch)
    batch.clear()


def _flush_schema_profiles(con: duckdb.DuckDBPyConnection, batch: list[tuple], stats: GraphStats) -> None:
    if not batch:
        return
    con.executemany(
        """INSERT OR REPLACE INTO ds_schema_profiles (
            distribution_id, dataset_id, columns_json, inferred_time_column, inferred_geography_column,
            inferred_value_columns, sample_row_count, preview_sample_hash, inference_mode,
            parser_mode, format_notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        batch,
    )
    stats.schema_profiles += len(batch)
    batch.clear()


def _flush_entity_mappings(con: duckdb.DuckDBPyConnection, batch: list[tuple], stats: GraphStats) -> None:
    if not batch:
        return
    con.executemany(
        """INSERT OR REPLACE INTO ds_entity_mappings (
            mapping_id, dataset_id, source, entity_id, entity_label, entity_type, external_id, alias_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        batch,
    )
    stats.entity_mappings += len(batch)
    batch.clear()


def _flush_alignment_hints(con: duckdb.DuckDBPyConnection, batch: list[tuple], stats: GraphStats) -> None:
    if not batch:
        return
    con.executemany(
        """INSERT OR REPLACE INTO ds_alignment_hints (
            hint_id, dataset_id, canonical_var, hint_type, confidence, evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?)""",
        batch,
    )
    stats.alignment_hints += len(batch)
    batch.clear()


def load_graph(
    *,
    records: Iterable[DatasetRecord],
    db_path: Path,
    insert_batch_size: int = 10_000,
) -> GraphStats:
    """Load records into DuckDB tables (without index creation)."""
    stats = GraphStats()
    con = duckdb.connect(str(db_path))
    try:
        _init_schema(con)
        _truncate(con)

        ds_batch: list[tuple] = []
        dist_batch: list[tuple] = []
        metric_binding_batch: list[tuple] = []
        schema_profile_batch: list[tuple] = []
        entity_mapping_batch: list[tuple] = []
        alignment_hint_batch: list[tuple] = []
        for rec in records:
            ds_batch.append(
                (
                    rec.id,
                    rec.source,
                    rec.agency,
                    rec.dataset_id,
                    rec.source_dataset_id,
                    rec.dedup_key,
                    rec.title,
                    rec.description,
                    rec.publisher,
                    rec.spatial,
                    rec.temporal_start,
                    rec.temporal_end,
                    rec.license,
                    rec.source_portal,
                    rec.execution_tier,
                    rec.update_frequency,
                    rec.last_updated,
                    rec.polisyos_metrics,
                    rec.keywords,
                    rec.themes,
                    rec.variables,
                    rec.formats,
                    rec.coverage.countries,
                    rec.coverage.regions,
                    rec.coverage.time_start,
                    rec.coverage.time_end,
                    rec.coverage.granularity,
                    rec.access.api_endpoint,
                    rec.access.bulk_download_url,
                    rec.access.license,
                    rec.access.auth_required,
                    rec.quality.description_score,
                    rec.quality.machine_readable_score,
                    rec.quality.parser_support_score,
                    rec.quality.freshness_score,
                    rec.quality.execution_readiness_score,
                    rec.preferred_distribution_id,
                )
            )

            preferred_distribution = _preferred_distribution(rec)
            metric_binding_batch.extend(_metric_binding_rows(rec, preferred_distribution))
            entity_mapping_batch.extend(_entity_mapping_rows(rec, preferred_distribution))
            alignment_hint_batch.extend(_alignment_hint_rows(rec, preferred_distribution))

            for dist in rec.distributions:
                dist_batch.append(
                    (
                        dist.id,
                        rec.id,
                        dist.url,
                        dist.format,
                        dist.name,
                        dist.connector_type,
                        _json_text(dist.connector_params),
                        dist.source_locator,
                        dist.profile_id,
                        dist.media_type,
                        dist.machine_readable,
                        dist.parser_supported,
                        dist.size_estimate_bytes,
                        dist.checksum,
                        _json_text(dist.default_filters),
                        dist.quality_score,
                    )
                )
                if rec.execution_tier != "catalog" and (dist.parser_supported or dist.machine_readable):
                    schema_profile_batch.append(_schema_profile_row(rec, dist))

            if len(ds_batch) >= insert_batch_size:
                _flush_datasets(con, ds_batch, stats)
                _flush_distributions(con, dist_batch, stats)
                _flush_metric_bindings(con, metric_binding_batch, stats)
                _flush_schema_profiles(con, schema_profile_batch, stats)
                _flush_entity_mappings(con, entity_mapping_batch, stats)
                _flush_alignment_hints(con, alignment_hint_batch, stats)

        _flush_datasets(con, ds_batch, stats)
        _flush_distributions(con, dist_batch, stats)
        _flush_metric_bindings(con, metric_binding_batch, stats)
        _flush_schema_profiles(con, schema_profile_batch, stats)
        _flush_entity_mappings(con, entity_mapping_batch, stats)
        _flush_alignment_hints(con, alignment_hint_batch, stats)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return stats


def build_indexes(db_path: Path) -> None:
    """Create secondary indexes and checkpoint DB."""
    con = duckdb.connect(str(db_path))
    try:
        _run_statements(con, _INDEXES)
        con.execute("CHECKPOINT")
    finally:
        con.close()


def run_graph_load(config: DatasetBatchConfig) -> GraphStats:
    """Run graph load."""
    started_at = datetime.now(UTC).isoformat()

    def _iter_records() -> Iterable[DatasetRecord]:
        with open(config.merged_records_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield DatasetRecord.model_validate_json(line)

    stats = load_graph(records=_iter_records(), db_path=config.db_path)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "graph_load.json",
        stage="graph_load",
        status="ok",
        metrics={
            "datasets": stats.datasets,
            "distributions": stats.distributions,
            "metric_bindings": stats.metric_bindings,
            "schema_profiles": stats.schema_profiles,
            "entity_mappings": stats.entity_mappings,
            "alignment_hints": stats.alignment_hints,
        },
        artifacts=[config.db_path],
        started_at=started_at,
    )
    logger.info(
        "Graph load complete: {} datasets, {} distributions, {} metric bindings, {} schema profiles, {} entity mappings, {} alignment hints",
        stats.datasets,
        stats.distributions,
        stats.metric_bindings,
        stats.schema_profiles,
        stats.entity_mappings,
        stats.alignment_hints,
    )
    return stats


def run_graph_index(config: DatasetBatchConfig) -> None:
    """Run graph index."""
    started_at = datetime.now(UTC).isoformat()
    build_indexes(config.db_path)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "graph_index.json",
        stage="graph_index",
        status="ok",
        metrics={},
        artifacts=[config.db_path],
        started_at=started_at,
    )
    logger.info("Graph indexes created for {}", config.db_path)


def build_graph(*, records: Iterable[DatasetRecord], db_path: Path, insert_batch_size: int = 10_000) -> GraphStats:
    """Backward-compatible helper used by tests."""
    stats = load_graph(records=records, db_path=db_path, insert_batch_size=insert_batch_size)
    build_indexes(db_path)
    return stats
