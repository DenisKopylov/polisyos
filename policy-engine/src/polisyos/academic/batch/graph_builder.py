"""Stage: load merged academic records into DuckDB and build indexes."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import duckdb

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.knowledge.types import WorkRecord

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS ac_works (
    id              VARCHAR PRIMARY KEY,
    title           VARCHAR NOT NULL,
    doi             VARCHAR,
    abstract        VARCHAR,
    year            INTEGER,
    publication_date VARCHAR,
    language        VARCHAR,
    work_type       VARCHAR,
    is_retracted    BOOLEAN DEFAULT FALSE,
    cited_by_count  INTEGER DEFAULT 0,
    fwci            DOUBLE,
    citation_percentile DOUBLE,
    citation_top_1  BOOLEAN DEFAULT FALSE,
    citation_top_10 BOOLEAN DEFAULT FALSE,
    journal         VARCHAR,
    source_id       VARCHAR,
    is_oa           BOOLEAN DEFAULT FALSE,
    has_fulltext    BOOLEAN DEFAULT FALSE,
    full_text_url   VARCHAR,
    trust_score     FLOAT DEFAULT 0.0,
    study_design    VARCHAR
);

CREATE TABLE IF NOT EXISTS ac_work_concepts (
    work_id         VARCHAR NOT NULL,
    topic_id        VARCHAR,
    concept         VARCHAR NOT NULL,
    level           INTEGER,
    score           FLOAT,
    PRIMARY KEY (work_id, topic_id, concept)
);

CREATE TABLE IF NOT EXISTS ac_parameter_estimates (
    id              VARCHAR PRIMARY KEY,
    work_id         VARCHAR NOT NULL,
    variable_name   VARCHAR,
    estimate        DOUBLE NOT NULL,
    ci_low          DOUBLE,
    ci_high         DOUBLE,
    std_error       DOUBLE,
    unit            VARCHAR,
    domain          VARCHAR,
    study_design    VARCHAR,
    sample_size     INTEGER,
    country         VARCHAR,
    period_start    INTEGER,
    period_end      INTEGER,
    trust_score     FLOAT DEFAULT 0.0,
    raw_context     VARCHAR
);

CREATE TABLE IF NOT EXISTS ac_causal_claims (
    id              VARCHAR PRIMARY KEY,
    work_id         VARCHAR NOT NULL,
    cause           VARCHAR NOT NULL,
    effect          VARCHAR NOT NULL,
    direction       VARCHAR,
    strength        VARCHAR,
    mechanism       VARCHAR,
    domain          VARCHAR,
    trust_score     FLOAT DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ac_runs (
    run_id          VARCHAR PRIMARY KEY,
    pass_name       VARCHAR,
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    config_json     VARCHAR,
    status          VARCHAR
);

CREATE TABLE IF NOT EXISTS ac_topics (
    topic_id          VARCHAR PRIMARY KEY,
    display_name      VARCHAR,
    policy_block      VARCHAR,
    policy_subblock   VARCHAR,
    source_file       VARCHAR,
    works_count       BIGINT,
    cited_by_count    BIGINT,
    score_core        INTEGER,
    score_domain      INTEGER,
    score_context     INTEGER
);

CREATE TABLE IF NOT EXISTS ac_topic_selections (
    run_id            VARCHAR NOT NULL,
    topic_id          VARCHAR NOT NULL,
    work_id           VARCHAR NOT NULL,
    rank              INTEGER,
    selection_score   DOUBLE,
    batch_origin      VARCHAR,
    selected_at       TIMESTAMP,
    PRIMARY KEY (run_id, topic_id, work_id)
);

CREATE TABLE IF NOT EXISTS ac_article_extractions (
    extraction_id      VARCHAR PRIMARY KEY,
    run_id             VARCHAR NOT NULL,
    work_id            VARCHAR NOT NULL,
    extraction_mode    VARCHAR,
    extraction_json    VARCHAR NOT NULL,
    context_json       VARCHAR,
    confidence         FLOAT,
    token_prompt       INTEGER DEFAULT 0,
    token_completion   INTEGER DEFAULT 0,
    cost_usd           DOUBLE DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ac_boundary_conditions (
    boundary_id        VARCHAR PRIMARY KEY,
    work_id            VARCHAR NOT NULL,
    variable           VARCHAR,
    operator           VARCHAR,
    threshold_value    VARCHAR,
    scope_text         VARCHAR,
    confidence         FLOAT DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ac_ingest_errors (
    error_id           VARCHAR PRIMARY KEY,
    run_id             VARCHAR,
    stage              VARCHAR,
    topic_id           VARCHAR,
    work_id            VARCHAR,
    error_code         VARCHAR,
    error_message      VARCHAR,
    payload_ref        VARCHAR,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_ac_works_year ON ac_works(year);
CREATE INDEX IF NOT EXISTS idx_ac_works_trust ON ac_works(trust_score);
CREATE INDEX IF NOT EXISTS idx_ac_concepts_work ON ac_work_concepts(work_id);
CREATE INDEX IF NOT EXISTS idx_ac_concepts_topic_id ON ac_work_concepts(topic_id);
CREATE INDEX IF NOT EXISTS idx_ac_concepts_concept ON ac_work_concepts(concept);
CREATE INDEX IF NOT EXISTS idx_ac_estimates_work ON ac_parameter_estimates(work_id);
CREATE INDEX IF NOT EXISTS idx_ac_estimates_var ON ac_parameter_estimates(variable_name);
CREATE INDEX IF NOT EXISTS idx_ac_estimates_domain ON ac_parameter_estimates(domain);
CREATE INDEX IF NOT EXISTS idx_ac_claims_work ON ac_causal_claims(work_id);
CREATE INDEX IF NOT EXISTS idx_ac_claims_cause ON ac_causal_claims(cause);
CREATE INDEX IF NOT EXISTS idx_ac_claims_effect ON ac_causal_claims(effect);
CREATE INDEX IF NOT EXISTS idx_topic_sel_topic_rank ON ac_topic_selections(topic_id, rank);
CREATE INDEX IF NOT EXISTS idx_topic_sel_work ON ac_topic_selections(work_id);
CREATE INDEX IF NOT EXISTS idx_article_extractions_work_mode ON ac_article_extractions(work_id, extraction_mode);
CREATE INDEX IF NOT EXISTS idx_boundary_work ON ac_boundary_conditions(work_id);
CREATE INDEX IF NOT EXISTS idx_runs_pass_status ON ac_runs(pass_name, status);
"""


def _stable_hash(*parts: str, size: int = 24) -> str:
    canon = "|".join(parts)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:size]


@dataclass
class GraphStats:
    works: int = 0
    concepts: int = 0
    estimates: int = 0
    claims: int = 0
    runs: int = 0
    topics: int = 0
    topic_selections: int = 0
    article_extractions: int = 0
    boundary_conditions: int = 0
    ingest_errors: int = 0


def _init_schema(con: duckdb.DuckDBPyConnection) -> None:
    # Recreate tables on each load to keep schema deterministic across versions.
    con.execute("DROP TABLE IF EXISTS ac_ingest_errors")
    con.execute("DROP TABLE IF EXISTS ac_boundary_conditions")
    con.execute("DROP TABLE IF EXISTS ac_article_extractions")
    con.execute("DROP TABLE IF EXISTS ac_topic_selections")
    con.execute("DROP TABLE IF EXISTS ac_topics")
    con.execute("DROP TABLE IF EXISTS ac_runs")
    con.execute("DROP TABLE IF EXISTS ac_causal_claims")
    con.execute("DROP TABLE IF EXISTS ac_parameter_estimates")
    con.execute("DROP TABLE IF EXISTS ac_work_concepts")
    con.execute("DROP TABLE IF EXISTS ac_works")
    for stmt in _DDL.strip().split(";"):
        sql = stmt.strip()
        if sql:
            con.execute(sql)


def _truncate(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DELETE FROM ac_ingest_errors")
    con.execute("DELETE FROM ac_boundary_conditions")
    con.execute("DELETE FROM ac_article_extractions")
    con.execute("DELETE FROM ac_topic_selections")
    con.execute("DELETE FROM ac_topics")
    con.execute("DELETE FROM ac_runs")
    con.execute("DELETE FROM ac_causal_claims")
    con.execute("DELETE FROM ac_parameter_estimates")
    con.execute("DELETE FROM ac_work_concepts")
    con.execute("DELETE FROM ac_works")


def _flush_all(
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    work_batch: list[tuple],
    concept_batch: list[tuple],
    estimate_batch: list[tuple],
    claim_batch: list[tuple],
    topic_batch: list[tuple],
    topic_sel_batch: list[tuple],
    extraction_batch: list[tuple],
    boundary_batch: list[tuple],
    ingest_error_batch: list[tuple],
) -> None:
    if work_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_works "
            "("
            "id, title, doi, abstract, year, publication_date, language, work_type, is_retracted, "
            "cited_by_count, fwci, citation_percentile, citation_top_1, citation_top_10, "
            "journal, source_id, is_oa, has_fulltext, full_text_url, trust_score, study_design"
            ") "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            work_batch,
        )
        stats.works += len(work_batch)
        work_batch.clear()

    if concept_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_work_concepts "
            "(work_id, topic_id, concept, level, score) VALUES (?, ?, ?, ?, ?)",
            concept_batch,
        )
        stats.concepts += len(concept_batch)
        concept_batch.clear()

    if estimate_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_parameter_estimates "
            "(id, work_id, variable_name, estimate, ci_low, ci_high, "
            "std_error, unit, domain, study_design, sample_size, "
            "country, period_start, period_end, trust_score, raw_context) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            estimate_batch,
        )
        stats.estimates += len(estimate_batch)
        estimate_batch.clear()

    if claim_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_causal_claims "
            "(id, work_id, cause, effect, direction, strength, mechanism, domain, trust_score) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            claim_batch,
        )
        stats.claims += len(claim_batch)
        claim_batch.clear()

    if topic_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_topics "
            "(topic_id, display_name, policy_block, policy_subblock, source_file, works_count, cited_by_count, score_core, score_domain, score_context) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            topic_batch,
        )
        stats.topics += len(topic_batch)
        topic_batch.clear()

    if topic_sel_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_topic_selections "
            "(run_id, topic_id, work_id, rank, selection_score, batch_origin, selected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            topic_sel_batch,
        )
        stats.topic_selections += len(topic_sel_batch)
        topic_sel_batch.clear()

    if extraction_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_article_extractions "
            "(extraction_id, run_id, work_id, extraction_mode, extraction_json, context_json, confidence, token_prompt, token_completion, cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            extraction_batch,
        )
        stats.article_extractions += len(extraction_batch)
        extraction_batch.clear()

    if boundary_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_boundary_conditions "
            "(boundary_id, work_id, variable, operator, threshold_value, scope_text, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            boundary_batch,
        )
        stats.boundary_conditions += len(boundary_batch)
        boundary_batch.clear()

    if ingest_error_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_ingest_errors "
            "(error_id, run_id, stage, topic_id, work_id, error_code, error_message, payload_ref) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ingest_error_batch,
        )
        stats.ingest_errors += len(ingest_error_batch)
        ingest_error_batch.clear()


def load_graph(
    *,
    records: Iterable[WorkRecord],
    db_path: Path,
    insert_batch_size: int = 10_000,
    run_id: str = "",
    pass_name: str = "",
    config_json: str = "",
    topics_catalog_path: Path | None = None,
    ingest_errors_path: Path | None = None,
) -> GraphStats:
    """Load records into DuckDB tables (without creating indexes)."""
    stats = GraphStats()
    con = duckdb.connect(str(db_path))

    try:
        _init_schema(con)
        _truncate(con)

        # Register run row.
        if run_id:
            con.execute(
                "INSERT OR REPLACE INTO ac_runs (run_id, pass_name, started_at, finished_at, config_json, status) VALUES (?, ?, ?, ?, ?, ?)",
                [run_id, pass_name, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat(), config_json, "ok"],
            )
            stats.runs = 1

        # Preload topics catalog when present.
        topic_batch: list[tuple] = []
        if topics_catalog_path and topics_catalog_path.exists():
            with open(topics_catalog_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    topic_batch.append(
                        (
                            str(row.get("topic_id") or ""),
                            str(row.get("display_name") or ""),
                            str(row.get("policy_block") or ""),
                            str(row.get("policy_subblock") or ""),
                            str(row.get("source_file") or ""),
                            int(row.get("works_count") or 0),
                            int(row.get("cited_by_count") or 0),
                            int(row.get("score_core") or 0),
                            int(row.get("score_domain") or 0),
                            int(row.get("score_context") or 0),
                        )
                    )

        work_batch: list[tuple] = []
        concept_batch: list[tuple] = []
        estimate_batch: list[tuple] = []
        claim_batch: list[tuple] = []
        topic_sel_batch: list[tuple] = []
        extraction_batch: list[tuple] = []
        boundary_batch: list[tuple] = []
        ingest_error_batch: list[tuple] = []
        topic_seen: set[str] = {str(t[0]) for t in topic_batch if t and t[0]}

        for record in records:
            work_batch.append(
                (
                    record.id,
                    record.title,
                    record.doi,
                    record.abstract,
                    record.year,
                    record.publication_date,
                    record.language,
                    record.work_type,
                    record.is_retracted,
                    record.cited_by_count,
                    record.fwci,
                    record.citation_normalized_percentile,
                    record.citation_is_top_1_percent,
                    record.citation_is_top_10_percent,
                    record.journal,
                    record.source_id,
                    record.is_oa,
                    record.has_fulltext,
                    record.full_text_url,
                    record.trust_score,
                    record.study_design,
                )
            )

            for concept_data in record.concepts:
                if isinstance(concept_data, dict):
                    topic_id = str(concept_data.get("id") or "")
                    if topic_id and "/" in topic_id:
                        topic_id = topic_id.rsplit("/", 1)[-1]
                    concept_batch.append(
                        (
                            record.id,
                            topic_id,
                            concept_data.get("display_name", ""),
                            concept_data.get("level"),
                            concept_data.get("score"),
                        )
                    )

            for i, est in enumerate(record.estimates):
                eid = _stable_hash(record.id, str(i), str(est.value), est.variable_hint)
                estimate_batch.append(
                    (
                        eid,
                        record.id,
                        est.variable_hint,
                        est.value,
                        est.ci_low,
                        est.ci_high,
                        est.std_error,
                        est.unit,
                        "",
                        record.study_design,
                        int(record.metadata.get("sample_size")) if record.metadata.get("sample_size") else None,
                        str(record.context_profile.get("context_id") or ""),
                        None,
                        None,
                        record.trust_score,
                        est.context_snippet[:500],
                    )
                )

            for i, claim in enumerate(record.causal_claims):
                if isinstance(claim, dict):
                    cid = _stable_hash(record.id, str(i), str(claim.get("cause", "")), str(claim.get("effect", "")))
                    claim_batch.append(
                        (
                            cid,
                            record.id,
                            claim.get("cause", ""),
                            claim.get("effect", ""),
                            claim.get("direction", ""),
                            claim.get("strength", ""),
                            claim.get("mechanism", ""),
                            claim.get("domain", ""),
                            record.trust_score,
                        )
                    )

            for i, bnd in enumerate(record.boundary_conditions):
                if not isinstance(bnd, dict):
                    continue
                bid = _stable_hash(record.id, "boundary", str(i), str(bnd.get("scope_text", "")))
                boundary_batch.append(
                    (
                        bid,
                        record.id,
                        str(bnd.get("variable") or ""),
                        str(bnd.get("operator") or ""),
                        str(bnd.get("threshold_value") or ""),
                        str(bnd.get("scope_text") or ""),
                        float(bnd.get("confidence") or 0.0),
                    )
                )

            extraction_id = _stable_hash(record.id, record.extraction_mode, run_id)
            extraction_batch.append(
                (
                    extraction_id,
                    run_id,
                    record.id,
                    record.extraction_mode,
                    json.dumps(
                        {
                            "estimates": [e.model_dump(mode="json") for e in record.estimates],
                            "causal_claims": record.causal_claims,
                            "boundary_conditions": record.boundary_conditions,
                            "study_design": record.study_design,
                            "method_signal_score": record.method_signal_score,
                            "metadata": record.metadata,
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(record.context_profile, ensure_ascii=False),
                    float(record.extraction_confidence),
                    int(record.token_count_prompt),
                    int(record.token_count_completion),
                    float(record.extraction_cost_usd + record.screening_cost_usd),
                )
            )

            for t in record.source_topics:
                if t.topic_id and t.topic_id not in topic_seen:
                    topic_seen.add(t.topic_id)
                    topic_batch.append(
                        (
                            t.topic_id,
                            t.topic_display_name,
                            t.policy_block,
                            t.policy_subblock,
                            t.source_file,
                            0,
                            0,
                            0,
                            0,
                            0,
                        )
                    )
                topic_sel_batch.append(
                    (
                        run_id,
                        t.topic_id,
                        record.id,
                        t.rank,
                        t.selection_score,
                        t.batch_origin,
                        t.selected_at or None,
                    )
                )

            if len(work_batch) >= insert_batch_size:
                _flush_all(
                    con,
                    stats,
                    work_batch,
                    concept_batch,
                    estimate_batch,
                    claim_batch,
                    topic_batch,
                    topic_sel_batch,
                    extraction_batch,
                    boundary_batch,
                    ingest_error_batch,
                )

        # ingest errors (optional)
        if ingest_errors_path and ingest_errors_path.exists():
            with open(ingest_errors_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        continue
                    ingest_error_batch.append(
                        (
                            _stable_hash(
                                str(row.get("run_id") or run_id),
                                str(row.get("stage") or ""),
                                str(row.get("topic_id") or ""),
                                str(row.get("work_id") or ""),
                                str(row.get("error_code") or ""),
                            ),
                            str(row.get("run_id") or run_id),
                            str(row.get("stage") or ""),
                            str(row.get("topic_id") or ""),
                            str(row.get("work_id") or ""),
                            str(row.get("error_code") or ""),
                            str(row.get("error_message") or ""),
                            str(row.get("payload_ref") or ""),
                        )
                    )

        _flush_all(
            con,
            stats,
            work_batch,
            concept_batch,
            estimate_batch,
            claim_batch,
            topic_batch,
            topic_sel_batch,
            extraction_batch,
            boundary_batch,
            ingest_error_batch,
        )

        # finalize run row timestamps
        if run_id:
            con.execute(
                "UPDATE ac_runs SET finished_at = ?, status = ? WHERE run_id = ?",
                [datetime.now(UTC).isoformat(), "ok", run_id],
            )

        con.execute("CHECKPOINT")
    finally:
        con.close()
    return stats


def build_indexes(db_path: Path) -> None:
    """Create secondary indexes after load stage."""
    con = duckdb.connect(str(db_path))
    try:
        for stmt in _INDEXES.strip().split(";"):
            sql = stmt.strip()
            if sql:
                con.execute(sql)
        con.execute("CHECKPOINT")
    finally:
        con.close()


def run_graph_load(config: AcademicBatchConfig) -> GraphStats:
    started_at = datetime.now(UTC).isoformat()

    def _iter_records() -> Iterable[WorkRecord]:
        with open(config.merged_records_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield WorkRecord.model_validate_json(line)

    cfg_json = json.dumps(
        {
            "target_per_topic": config.target_per_topic,
            "pass_name": config.pass_name,
            "run_id": config.run_id,
            "llm_gate_enabled": config.llm_gate_enabled,
            "llm_gate_mode": config.llm_gate_mode,
        },
        ensure_ascii=False,
    )

    stats = load_graph(
        records=_iter_records(),
        db_path=config.db_path,
        insert_batch_size=config.graph_insert_batch,
        run_id=config.run_id,
        pass_name=config.pass_name,
        config_json=cfg_json,
        topics_catalog_path=config.topics_catalog_path if config.topics_catalog_path.exists() else None,
        ingest_errors_path=config.ingest_errors_path if config.ingest_errors_path.exists() else None,
    )
    write_stage_manifest(
        manifest_path=config.manifests_dir / "graph_load.json",
        stage="graph_load",
        status="ok",
        metrics={
            "works": stats.works,
            "concepts": stats.concepts,
            "estimates": stats.estimates,
            "claims": stats.claims,
            "runs": stats.runs,
            "topics": stats.topics,
            "topic_selections": stats.topic_selections,
            "article_extractions": stats.article_extractions,
            "boundary_conditions": stats.boundary_conditions,
            "ingest_errors": stats.ingest_errors,
        },
        artifacts=[config.db_path],
        started_at=started_at,
    )
    return stats


def run_graph_index(config: AcademicBatchConfig) -> None:
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


# Backward-compatible helper used by existing tests.
def build_graph(*, records: Iterable[WorkRecord], db_path: Path, insert_batch_size: int = 10_000) -> GraphStats:
    stats = load_graph(records=records, db_path=db_path, insert_batch_size=insert_batch_size)
    build_indexes(db_path)
    return stats
