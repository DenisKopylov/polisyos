"""Stage 4/5: Load merged dataset records into DuckDB and build indexes."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import duckdb

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.knowledge.types import DatasetRecord

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS ds_datasets (
    id               VARCHAR PRIMARY KEY,
    source           VARCHAR,
    agency           VARCHAR,
    dataset_id       VARCHAR,
    dedup_key        VARCHAR,
    title            VARCHAR NOT NULL,
    description      VARCHAR,
    publisher        VARCHAR,
    spatial          VARCHAR,
    temporal_start   VARCHAR,
    temporal_end     VARCHAR,
    license          VARCHAR,
    source_portal    VARCHAR,
    polisyos_metrics VARCHAR[],
    keywords         VARCHAR[],
    themes           VARCHAR[],
    variables        VARCHAR[],
    formats          VARCHAR[],
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ds_distributions (
    id               VARCHAR PRIMARY KEY,
    dataset_id       VARCHAR NOT NULL,
    url              VARCHAR,
    format           VARCHAR,
    name             VARCHAR,
    connector_type   VARCHAR,
    connector_params JSON,
    quality_score    FLOAT DEFAULT 0.0
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

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_ds_source ON ds_datasets(source);
CREATE INDEX IF NOT EXISTS idx_ds_agency ON ds_datasets(agency);
CREATE INDEX IF NOT EXISTS idx_ds_dedup_key ON ds_datasets(dedup_key);
CREATE INDEX IF NOT EXISTS idx_ds_publisher ON ds_datasets(publisher);
CREATE INDEX IF NOT EXISTS idx_ds_portal ON ds_datasets(source_portal);
CREATE INDEX IF NOT EXISTS idx_dist_dataset ON ds_distributions(dataset_id);
CREATE INDEX IF NOT EXISTS idx_dist_connector ON ds_distributions(connector_type);
CREATE INDEX IF NOT EXISTS idx_registry_provider ON ds_registry_datasets(provider);
CREATE INDEX IF NOT EXISTS idx_va_canonical ON ds_variable_alignments(canonical_var);
CREATE INDEX IF NOT EXISTS idx_va_dataset ON ds_variable_alignments(dataset_id);
CREATE INDEX IF NOT EXISTS idx_obs_country_year ON ds_observations(country_code, year);
CREATE INDEX IF NOT EXISTS idx_obs_dataset_raw ON ds_observations(dataset_id, raw_variable);
"""


@dataclass
class GraphStats:
    datasets: int = 0
    distributions: int = 0


def _init_schema(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in _DDL.strip().split(";"):
        sql = stmt.strip()
        if sql:
            con.execute(sql)


def _truncate(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DELETE FROM ds_distributions")
    con.execute("DELETE FROM ds_datasets")


def _flush_datasets(con: duckdb.DuckDBPyConnection, batch: list[tuple], stats: GraphStats) -> None:
    if not batch:
        return
    con.executemany(
        """INSERT OR REPLACE INTO ds_datasets (
            id, source, agency, dataset_id, dedup_key,
            title, description, publisher, spatial,
            temporal_start, temporal_end, license, source_portal,
            polisyos_metrics, keywords, themes, variables, formats
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            connector_type, connector_params, quality_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        batch,
    )
    stats.distributions += len(batch)
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
        for rec in records:
            ds_batch.append(
                (
                    rec.id,
                    rec.source,
                    rec.agency,
                    rec.dataset_id,
                    rec.dedup_key,
                    rec.title,
                    rec.description,
                    rec.publisher,
                    rec.spatial,
                    rec.temporal_start,
                    rec.temporal_end,
                    rec.license,
                    rec.source_portal,
                    rec.polisyos_metrics,
                    rec.keywords,
                    rec.themes,
                    rec.variables,
                    rec.formats,
                )
            )
            for dist in rec.distributions:
                dist_batch.append(
                    (
                        dist.id,
                        rec.id,
                        dist.url,
                        dist.format,
                        dist.name,
                        dist.connector_type,
                        json.dumps(dist.connector_params, ensure_ascii=False),
                        dist.quality_score,
                    )
                )

            if len(ds_batch) >= insert_batch_size:
                _flush_datasets(con, ds_batch, stats)
                _flush_distributions(con, dist_batch, stats)

        _flush_datasets(con, ds_batch, stats)
        _flush_distributions(con, dist_batch, stats)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return stats


def build_indexes(db_path: Path) -> None:
    """Create secondary indexes and checkpoint DB."""
    con = duckdb.connect(str(db_path))
    try:
        for stmt in _INDEXES.strip().split(";"):
            sql = stmt.strip()
            if sql:
                con.execute(sql)
        con.execute("CHECKPOINT")
    finally:
        con.close()


def run_graph_load(config: DatasetBatchConfig) -> GraphStats:
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
        metrics={"datasets": stats.datasets, "distributions": stats.distributions},
        artifacts=[config.db_path],
        started_at=started_at,
    )
    logger.info("Graph load complete: %d datasets, %d distributions", stats.datasets, stats.distributions)
    return stats


def run_graph_index(config: DatasetBatchConfig) -> None:
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
    logger.info("Graph indexes created for %s", config.db_path)


# Backward-compatible helper used by tests

def build_graph(*, records: Iterable[DatasetRecord], db_path: Path, insert_batch_size: int = 10_000) -> GraphStats:
    stats = load_graph(records=records, db_path=db_path, insert_batch_size=insert_batch_size)
    build_indexes(db_path)
    return stats
