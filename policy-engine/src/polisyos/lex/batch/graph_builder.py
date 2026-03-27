"""Stage 4: Stream SPO results into DuckDB knowledge graph."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from polisyos.common.logger import get_logger
from polisyos.lex.batch.amendment_detector import detect_amendments
from polisyos.lex.batch.doc_identity import (
    DocIndexEntry,
    DocResolutionIndex,
    build_doc_resolution_index,
    doc_family_id,
    doc_type_category,
    normalize_publishers,
    normalize_ref_number,
    normalize_text_key,
    version_sort_key,
)
from polisyos.lex.batch.entity_resolver import EntityRecord, EntityResolver, normalize_entity_name
from polisyos.lex.batch.provisions_io import _shard_prefix, read_provisions
from polisyos.lex.knowledge.types import SPOExtractionResult

logger = get_logger(__name__)

_AMENDMENT_TITLE_TARGET_RE = re.compile(
    r"(?:внесення\s+змін|внести\s+(?:такі\s+)?зміни|"
    r"доповнення|про\s+зміну|про\s+зміни|"
    r"зміни\s+(?:та\s+доповнення\s+)?до|"
    r"про\s+внесення\s+змін|"
    r"визнання\s+(?:таким|такими).+?чинність.+?до)\s+до\s+(?P<target>.+)$",
    re.IGNORECASE,
)
_AMENDMENT_TITLE_TARGET_ALT_RE = re.compile(
    r"(?:внесення\s+змін|зміни|доповнення)\s+(?:до\s+)?(?:деяких\s+)?(?:законодавчих\s+актів|законів)\b",
    re.IGNORECASE,
)
_AMENDMENT_TITLE_STOP_RE = re.compile(r"[:(]|,?\s+(?:щодо|та\s+деяких|у\s+зв'язку)\b", re.IGNORECASE)

def _normalize_entity_name(name: str) -> str:
    return normalize_entity_name(name)


def _stable_hash(*parts: str, size: int = 20) -> str:
    canon = "|".join(parts)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:size]

class EntityDeduplicator(EntityResolver):
    """Backward-compatible alias for the richer entity resolver."""

    def get_or_create(
        self,
        name_en: str,
        name_uk: str,
        entity_type: str = "concept",
        entity_subtype: str = "",
    ) -> str:
        return self.resolve(
            name_en=name_en,
            name_uk=name_uk,
            entity_type=entity_type,
            entity_subtype=entity_subtype,
        )


_DDL = """
CREATE TABLE IF NOT EXISTS lex_entities (
    entity_id      VARCHAR PRIMARY KEY,
    name_en        VARCHAR NOT NULL,
    name_uk        VARCHAR,
    entity_type    VARCHAR NOT NULL,
    entity_subtype VARCHAR,
    mention_count  INTEGER DEFAULT 1,
    aliases_en     VARCHAR,
    aliases_uk     VARCHAR,
    wikidata_id    VARCHAR,
    metadata       JSON,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_facts (
    fact_id             VARCHAR PRIMARY KEY,
    statement_id        VARCHAR,
    subject_id          VARCHAR NOT NULL,
    predicate           VARCHAR NOT NULL,
    object_id           VARCHAR NOT NULL,
    fact_text           VARCHAR NOT NULL,
    confidence          REAL NOT NULL,
    norm_type           VARCHAR,
    action_canon        VARCHAR,
    norm_type_canon     VARCHAR,
    subject_en          VARCHAR,
    subject_uk          VARCHAR,
    object_en           VARCHAR,
    object_uk           VARCHAR,
    condition_text_uk   VARCHAR,
    exception_text_uk   VARCHAR,
    procedure_text_uk   VARCHAR,
    temporal_text_uk    VARCHAR,
    sanction_text_uk    VARCHAR,
    source_quote_uk     VARCHAR,
    source_quote_start  INTEGER,
    source_quote_end    INTEGER,
    thresholds_json     VARCHAR,
    trust_tier          VARCHAR,
    grounding_status    VARCHAR,
    canonical_status    VARCHAR,
    reference_resolution_status VARCHAR,
    structure_quality   VARCHAR,
    constraint_type_canon VARCHAR,
    legal_unit_subtype  VARCHAR,
    route_class         VARCHAR,
    empty_spo_retry_eligible BOOLEAN,
    audit_miss_prone    BOOLEAN,
    reference_bearing   BOOLEAN,
    threshold_bearing   BOOLEAN,
    fused_confidence    REAL,
    confidence_breakdown_json VARCHAR,
    consistency_score   REAL,
    hallucination_flags_json VARCHAR,
    quality_band        VARCHAR,
    doc_id              VARCHAR NOT NULL,
    doc_reestr_code     VARCHAR,
    doc_name            VARCHAR,
    doc_type            VARCHAR,
    doc_date_acc        VARCHAR,
    doc_status          VARCHAR,
    jurisdiction        VARCHAR,
    top_domain          VARCHAR,
    doc_family_id       VARCHAR,
    version_id          VARCHAR,
    provision_anchor    VARCHAR,
    provision_citation  VARCHAR,
    effective_from      VARCHAR,
    effective_to        VARCHAR,
    extraction_source   VARCHAR,
    gate_score          REAL,
    gate_reason_codes   VARCHAR,
    metadata            JSON,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE VIEW lex_fact_candidates AS
    SELECT * FROM lex_facts WHERE trust_tier = 'search_candidate';

CREATE OR REPLACE VIEW lex_fact_grounded AS
    SELECT * FROM lex_facts WHERE trust_tier IN ('grounded_fact', 'normative_fact');

CREATE OR REPLACE VIEW lex_normative_facts AS
    SELECT * FROM lex_facts WHERE trust_tier = 'normative_fact';

CREATE OR REPLACE VIEW lex_normative_ready_facts AS
    SELECT * FROM lex_facts
    WHERE trust_tier = 'normative_fact'
      AND COALESCE(fused_confidence, confidence, 0.0) >= 0.65;

CREATE OR REPLACE VIEW lex_high_confidence_norms AS
    SELECT * FROM lex_facts
    WHERE trust_tier = 'normative_fact'
      AND COALESCE(fused_confidence, confidence, 0.0) >= 0.85;

CREATE TABLE IF NOT EXISTS lex_rule_thresholds (
    threshold_id    VARCHAR PRIMARY KEY,
    fact_id         VARCHAR NOT NULL,
    metric          VARCHAR,
    operator        VARCHAR,
    value_decimal   VARCHAR,
    value_text      VARCHAR,
    unit            VARCHAR,
    applies_to      VARCHAR,
    metadata        JSON,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_rule_clauses (
    clause_id       VARCHAR PRIMARY KEY,
    fact_id         VARCHAR NOT NULL,
    clause_type     VARCHAR NOT NULL,
    text_uk         VARCHAR NOT NULL,
    expr_json       VARCHAR,
    metadata        JSON,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_rule_links (
    link_id         VARCHAR PRIMARY KEY,
    fact_id         VARCHAR NOT NULL,
    relation_type   VARCHAR NOT NULL,
    target_doc_id   VARCHAR,
    target_anchor   VARCHAR,
    ref_text_uk     VARCHAR,
    metadata        JSON,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_provisions (
    provision_id        VARCHAR PRIMARY KEY,
    doc_id              VARCHAR NOT NULL,
    doc_reestr_code     VARCHAR,
    doc_name            VARCHAR,
    doc_type            VARCHAR,
    doc_status          VARCHAR,
    anchor_path         VARCHAR NOT NULL,
    parent_anchor       VARCHAR,
    depth               INTEGER,
    citation_label      VARCHAR NOT NULL,
    kind                VARCHAR NOT NULL,
    provision_text      VARCHAR NOT NULL,
    offset_start        INTEGER,
    offset_end          INTEGER,
    token_count_est     INTEGER,
    text_hash           VARCHAR,
    is_fallback_chunk   BOOLEAN,
    struct_kind         VARCHAR,
    section_role        VARCHAR,
    lineage_path        VARCHAR,
    appendix_id         VARCHAR,
    table_id            VARCHAR,
    fallback_allowed_for_reasoning BOOLEAN,
    legal_unit_subtype  VARCHAR,
    route_class         VARCHAR,
    empty_spo_retry_eligible BOOLEAN,
    audit_miss_prone    BOOLEAN,
    reference_bearing   BOOLEAN,
    threshold_bearing   BOOLEAN,
    metadata            JSON,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_references (
    reference_id        VARCHAR PRIMARY KEY,
    doc_id              VARCHAR NOT NULL,
    provision_anchor    VARCHAR,
    source_span_start   INTEGER,
    source_span_end     INTEGER,
    target_raw          VARCHAR,
    ref_type            VARCHAR,
    confidence          REAL,
    metadata            JSON,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_doc_domains (
    domain_id           VARCHAR PRIMARY KEY,
    doc_id              VARCHAR NOT NULL,
    domain              VARCHAR NOT NULL,
    score               REAL NOT NULL,
    rank                INTEGER NOT NULL,
    is_top              BOOLEAN,
    hits                INTEGER,
    metadata            JSON,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_reference_edges (
    reference_edge_id   VARCHAR PRIMARY KEY,
    source_doc_id       VARCHAR NOT NULL,
    source_doc_family_id VARCHAR,
    source_anchor       VARCHAR,
    target_doc_id       VARCHAR,
    target_doc_family_id VARCHAR,
    target_doc_reestr_code VARCHAR,
    target_doc_number   VARCHAR,
    target_doc_type     VARCHAR,
    target_doc_date_acc VARCHAR,
    target_doc_status   VARCHAR,
    target_anchor       VARCHAR,
    relation_type       VARCHAR NOT NULL,
    matched_by          VARCHAR,
    resolution_confidence REAL,
    resolution_status   VARCHAR,
    ref_text_uk         VARCHAR,
    version_id          VARCHAR,
    metadata            JSON,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_doc_versions (
    version_row_id      VARCHAR PRIMARY KEY,
    doc_id              VARCHAR NOT NULL,
    doc_family_id       VARCHAR NOT NULL,
    version_id          VARCHAR NOT NULL,
    doc_reestr_code     VARCHAR,
    doc_number          VARCHAR,
    reg_number          VARCHAR,
    publisher           VARCHAR,
    doc_name            VARCHAR,
    doc_type            VARCHAR,
    doc_date_acc        VARCHAR,
    doc_status          VARCHAR,
    version_rank        INTEGER,
    previous_version_id VARCHAR,
    next_version_id     VARCHAR,
    is_latest           BOOLEAN,
    metadata            JSON,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_reference_resolution_audit (
    ref_id               VARCHAR PRIMARY KEY,
    source_doc_id        VARCHAR NOT NULL,
    source_anchor        VARCHAR,
    ref_text_uk          VARCHAR,
    target_raw           VARCHAR,
    resolution_method    VARCHAR,
    resolution_status    VARCHAR,
    resolution_confidence REAL,
    candidate_count      INTEGER,
    selected_target_doc_id VARCHAR,
    alternatives_json    VARCHAR,
    metadata             JSON,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_pattern_feedback_queue (
    feedback_id          VARCHAR PRIMARY KEY,
    doc_id               VARCHAR NOT NULL,
    provision_anchor     VARCHAR,
    quality_family       VARCHAR,
    legal_unit_subtype   VARCHAR,
    route_class          VARCHAR,
    deterministic_reason_codes VARCHAR,
    llm_delta            INTEGER,
    miss_categories_json VARCHAR,
    cluster_key          VARCHAR,
    suggestion_family    VARCHAR,
    metadata             JSON,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_amendments (
    amendment_id         VARCHAR PRIMARY KEY,
    amending_doc_id      VARCHAR NOT NULL,
    amended_doc_id       VARCHAR,
    amendment_type       VARCHAR NOT NULL,
    target_anchor        VARCHAR,
    old_text_uk          VARCHAR,
    new_text_uk          VARCHAR,
    effective_from       VARCHAR,
    detected_by          VARCHAR DEFAULT 'pattern',
    confidence           REAL DEFAULT 0.8,
    metadata             JSON,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lex_consistency_issues (
    issue_id             VARCHAR PRIMARY KEY,
    type                 VARCHAR NOT NULL,
    fact_id_1            VARCHAR NOT NULL,
    fact_id_2            VARCHAR NOT NULL,
    doc_id_1             VARCHAR NOT NULL,
    doc_id_2             VARCHAR,
    subject_en           VARCHAR,
    object_en            VARCHAR,
    norm_type_1          VARCHAR,
    norm_type_2          VARCHAR,
    severity             VARCHAR,
    resolution_principle VARCHAR,
    prevailing_doc_id    VARCHAR,
    resolution_confidence REAL,
    requires_manual_review BOOLEAN DEFAULT TRUE,
    anchor_1             VARCHAR,
    anchor_2             VARCHAR,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_facts_subject ON lex_facts(subject_id);
CREATE INDEX IF NOT EXISTS idx_facts_object ON lex_facts(object_id);
CREATE INDEX IF NOT EXISTS idx_facts_predicate ON lex_facts(predicate);
CREATE INDEX IF NOT EXISTS idx_facts_action_canon ON lex_facts(action_canon);
CREATE INDEX IF NOT EXISTS idx_facts_norm_type_canon ON lex_facts(norm_type_canon);
CREATE INDEX IF NOT EXISTS idx_facts_doc ON lex_facts(doc_id);
CREATE INDEX IF NOT EXISTS idx_facts_trust_tier ON lex_facts(trust_tier);
CREATE INDEX IF NOT EXISTS idx_facts_fused_confidence ON lex_facts(fused_confidence);
CREATE INDEX IF NOT EXISTS idx_facts_quality_band ON lex_facts(quality_band);
CREATE INDEX IF NOT EXISTS idx_facts_top_domain ON lex_facts(top_domain);
CREATE INDEX IF NOT EXISTS idx_facts_jurisdiction ON lex_facts(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_facts_legal_unit_subtype ON lex_facts(legal_unit_subtype);
CREATE INDEX IF NOT EXISTS idx_facts_route_class ON lex_facts(route_class);
CREATE INDEX IF NOT EXISTS idx_entities_name ON lex_entities(name_en);
CREATE INDEX IF NOT EXISTS idx_provisions_doc ON lex_provisions(doc_id);
CREATE INDEX IF NOT EXISTS idx_provisions_legal_unit_subtype ON lex_provisions(legal_unit_subtype);
CREATE INDEX IF NOT EXISTS idx_provisions_route_class ON lex_provisions(route_class);
CREATE INDEX IF NOT EXISTS idx_thresholds_fact ON lex_rule_thresholds(fact_id);
CREATE INDEX IF NOT EXISTS idx_clauses_fact ON lex_rule_clauses(fact_id);
CREATE INDEX IF NOT EXISTS idx_links_fact ON lex_rule_links(fact_id);
CREATE INDEX IF NOT EXISTS idx_facts_extraction_source ON lex_facts(extraction_source);
CREATE INDEX IF NOT EXISTS idx_references_doc ON lex_references(doc_id);
CREATE INDEX IF NOT EXISTS idx_domains_doc ON lex_doc_domains(doc_id);
CREATE INDEX IF NOT EXISTS idx_domains_domain ON lex_doc_domains(domain);
CREATE INDEX IF NOT EXISTS idx_reference_edges_source_doc ON lex_reference_edges(source_doc_id);
CREATE INDEX IF NOT EXISTS idx_reference_edges_target_doc ON lex_reference_edges(target_doc_id);
CREATE INDEX IF NOT EXISTS idx_doc_versions_family ON lex_doc_versions(doc_family_id);
CREATE INDEX IF NOT EXISTS idx_reference_audit_source_doc ON lex_reference_resolution_audit(source_doc_id);
CREATE INDEX IF NOT EXISTS idx_pattern_feedback_cluster ON lex_pattern_feedback_queue(cluster_key);
CREATE INDEX IF NOT EXISTS idx_amendments_doc ON lex_amendments(amending_doc_id);
CREATE INDEX IF NOT EXISTS idx_consistency_doc ON lex_consistency_issues(doc_id_1);
"""


def _fact_id(
    doc_id: str,
    anchor: str,
    statement_id: str,
    quote_start: int | None,
    quote_end: int | None,
) -> str:
    return _stable_hash(
        doc_id,
        anchor,
        statement_id,
        str(quote_start if quote_start is not None else ""),
        str(quote_end if quote_end is not None else ""),
        size=20,
    )


def _fact_signature(
    *,
    provision_anchor: str,
    extraction_source: str,
    stmt,
) -> str:
    payload = {
        "provision_anchor": provision_anchor,
        "extraction_source": extraction_source,
        "statement": stmt.model_dump(mode="json"),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _allocate_fact_id(
    *,
    base_fact_id: str,
    signature: str,
    fact_signatures_by_id: dict[str, str],
    fact_ids_by_signature: dict[str, str],
) -> tuple[str, bool, bool]:
    existing_fact_id = fact_ids_by_signature.get(signature)
    if existing_fact_id is not None:
        return existing_fact_id, True, existing_fact_id != base_fact_id

    if base_fact_id not in fact_signatures_by_id:
        fact_signatures_by_id[base_fact_id] = signature
        fact_ids_by_signature[signature] = base_fact_id
        return base_fact_id, False, False

    attempt = _stable_hash(base_fact_id, signature, size=20)
    salt = 1
    while attempt in fact_signatures_by_id and fact_signatures_by_id[attempt] != signature:
        salt += 1
        attempt = _stable_hash(base_fact_id, signature, str(salt), size=20)

    fact_signatures_by_id[attempt] = signature
    fact_ids_by_signature[signature] = attempt
    return attempt, False, True


def _provision_id(
    doc_id: str,
    anchor_path: str,
    offset_start: int,
    offset_end: int,
    text_hash: str,
) -> str:
    return _stable_hash(
        doc_id,
        anchor_path,
        str(offset_start),
        str(offset_end),
        text_hash,
        size=20,
    )


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class GraphStats:
    entities: int = 0
    facts: int = 0
    candidate_facts: int = 0
    grounded_facts: int = 0
    normative_facts: int = 0
    high_confidence_norms: int = 0
    provisions: int = 0
    thresholds: int = 0
    clauses: int = 0
    links: int = 0
    references: int = 0
    reference_edges: int = 0
    doc_domains: int = 0
    doc_versions: int = 0
    amendments: int = 0
    amendments_with_target: int = 0
    amendment_docs_total: int = 0
    amendment_docs_with_target: int = 0
    reference_resolution_audit: int = 0
    reference_resolution_resolved: int = 0
    reference_resolution_partial: int = 0
    pattern_feedback_queue: int = 0
    docs_processed: int = 0
    spo_files_read: int = 0


def build_graph(
    *,
    spo_results_dir: Path,
    provisions_dir: Path,
    references_dir: Path | None,
    domains_dir: Path | None,
    doc_metadata: dict[str, dict],
    db_path: Path,
    feedback_queue_path: Path | None = None,
    insert_batch_size: int = 10_000,
) -> GraphStats:
    """Read SPO/provision files and stream rows to DuckDB."""
    stats = GraphStats()
    dedup = EntityDeduplicator()
    con = duckdb.connect(str(db_path))
    try:
        con.execute("PRAGMA force_compression='zstd'")
        _init_schema(con)
        _truncate_existing_rows(con)

        # --- Transaction 1: core data ingestion (facts, provisions, references, domains) ---
        con.execute("BEGIN TRANSACTION")
        _stream_facts_to_duckdb(
            con=con,
            stats=stats,
            dedup=dedup,
            spo_results_dir=spo_results_dir,
            provisions_dir=provisions_dir,
            references_dir=references_dir,
            doc_metadata=doc_metadata,
            insert_batch_size=insert_batch_size,
        )
        _stream_provisions_to_duckdb(
            con=con,
            stats=stats,
            provisions_dir=provisions_dir,
            doc_metadata=doc_metadata,
            insert_batch_size=insert_batch_size,
        )
        _stream_references_to_duckdb(
            con=con,
            stats=stats,
            references_dir=references_dir,
            insert_batch_size=insert_batch_size,
        )
        _stream_domains_to_duckdb(
            con=con,
            stats=stats,
            domains_dir=domains_dir,
            insert_batch_size=insert_batch_size,
        )
        con.execute("COMMIT")

        # --- Transaction 2: edges, versions, audit, feedback ---
        con.execute("BEGIN TRANSACTION")
        _stream_reference_edges_to_duckdb(
            con=con,
            stats=stats,
            references_dir=references_dir,
            insert_batch_size=insert_batch_size,
        )
        _stream_doc_versions_to_duckdb(
            con=con,
            stats=stats,
            doc_metadata=doc_metadata,
            insert_batch_size=insert_batch_size,
        )
        _stream_reference_resolution_audit_to_duckdb(
            con=con,
            stats=stats,
            references_dir=references_dir,
            insert_batch_size=insert_batch_size,
        )
        _stream_pattern_feedback_to_duckdb(
            con=con,
            stats=stats,
            feedback_queue_path=feedback_queue_path,
            insert_batch_size=insert_batch_size,
        )
        con.execute("COMMIT")

        # --- Transaction 3: amendments, enrichment, entities ---
        con.execute("BEGIN TRANSACTION")
        _stream_amendments_to_duckdb(
            con=con,
            stats=stats,
            provisions_dir=provisions_dir,
            references_dir=references_dir,
            doc_metadata=doc_metadata,
            insert_batch_size=insert_batch_size,
        )
        _enrich_fact_domains(con)
        _populate_fact_partitions(con=con, stats=stats)
        stats.entities = _insert_entities(
            con=con,
            dedup=dedup,
            insert_batch_size=insert_batch_size,
        )
        con.execute("COMMIT")

        _ensure_indexes(con)
        con.execute("CHECKPOINT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception as exc:
            logger.debug("Ignored exception: {}", exc)
        raise
    finally:
        con.close()

    logger.info(
        "Graph built: {} entities, {} facts ({} candidate / {} grounded / {} normative / {} high-confidence), "
        "{} provisions, {} thresholds, {} clauses, {} links, {} references, {} resolved edges, {} domain rows in {}",
        stats.entities,
        stats.facts,
        stats.candidate_facts,
        stats.grounded_facts,
        stats.normative_facts,
        stats.high_confidence_norms,
        stats.provisions,
        stats.thresholds,
        stats.clauses,
        stats.links,
        stats.references,
        stats.reference_edges,
        stats.doc_domains,
        db_path,
    )
    return stats


def _init_schema(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in _DDL.strip().split(";"):
        sql = stmt.strip()
        if sql:
            con.execute(sql)
    _ensure_optional_columns(con)


_OPTIONAL_COLUMNS: dict[str, dict[str, str]] = {
    "lex_facts": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
        "fused_confidence": "REAL",
        "confidence_breakdown_json": "VARCHAR",
        "consistency_score": "REAL",
        "hallucination_flags_json": "VARCHAR",
        "quality_band": "VARCHAR",
    },
    "lex_fact_candidates": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
        "fused_confidence": "REAL",
        "confidence_breakdown_json": "VARCHAR",
        "consistency_score": "REAL",
        "hallucination_flags_json": "VARCHAR",
        "quality_band": "VARCHAR",
    },
    "lex_fact_grounded": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
        "fused_confidence": "REAL",
        "confidence_breakdown_json": "VARCHAR",
        "consistency_score": "REAL",
        "hallucination_flags_json": "VARCHAR",
        "quality_band": "VARCHAR",
    },
    "lex_normative_facts": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
        "fused_confidence": "REAL",
        "confidence_breakdown_json": "VARCHAR",
        "consistency_score": "REAL",
        "hallucination_flags_json": "VARCHAR",
        "quality_band": "VARCHAR",
    },
    "lex_high_confidence_norms": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
        "fused_confidence": "REAL",
        "confidence_breakdown_json": "VARCHAR",
        "consistency_score": "REAL",
        "hallucination_flags_json": "VARCHAR",
        "quality_band": "VARCHAR",
    },
    "lex_provisions": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
    },
    "lex_entities": {
        "entity_subtype": "VARCHAR",
        "wikidata_id": "VARCHAR",
    },
}


def _column_exists(con: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> bool:
    row = con.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = ? AND column_name = ?
        LIMIT 1
        """,
        [table_name, column_name],
    ).fetchone()
    return row is not None


def _ensure_optional_columns(con: duckdb.DuckDBPyConnection) -> None:
    for table_name, columns in _OPTIONAL_COLUMNS.items():
        for column_name, sql_type in columns.items():
            if _column_exists(con, table_name, column_name):
                continue
            con.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}")


def _truncate_existing_rows(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DELETE FROM lex_consistency_issues")
    con.execute("DELETE FROM lex_amendments")
    con.execute("DELETE FROM lex_pattern_feedback_queue")
    con.execute("DELETE FROM lex_reference_resolution_audit")
    con.execute("DELETE FROM lex_doc_versions")
    con.execute("DELETE FROM lex_reference_edges")
    con.execute("DELETE FROM lex_doc_domains")
    con.execute("DELETE FROM lex_references")
    con.execute("DELETE FROM lex_rule_links")
    con.execute("DELETE FROM lex_rule_clauses")
    con.execute("DELETE FROM lex_rule_thresholds")
    con.execute("DELETE FROM lex_facts")
    con.execute("DELETE FROM lex_entities")
    con.execute("DELETE FROM lex_provisions")


def _reference_status_rank(value: str) -> int:
    return {"not_applicable": 0, "unresolved": 1, "partial": 2, "resolved": 3}.get(value, 0)


def _merge_reference_status(current: str, resolved_status: str) -> str:
    return current if _reference_status_rank(current) >= _reference_status_rank(resolved_status) else resolved_status


def _resolved_reference_statuses(*, references_dir: Path | None, doc_id: str) -> dict[str, str]:
    if references_dir is None:
        return {}
    ref_path = references_dir / doc_id[:2].lower() / f"{doc_id}.jsonl"
    if not ref_path.exists():
        return {}
    by_anchor: dict[str, str] = {}
    with open(ref_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            anchor = str(row.get("anchor_path") or "")
            if not anchor:
                continue
            status = str(row.get("resolution_status") or "unresolved")
            current = by_anchor.get(anchor, "not_applicable")
            by_anchor[anchor] = _merge_reference_status(current, status)
    return by_anchor


def _populate_fact_partitions(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
) -> None:
    # Partition tables are now views — just collect stats.
    stats.candidate_facts = int(con.execute("SELECT COUNT(*) FROM lex_fact_candidates").fetchone()[0])
    stats.grounded_facts = int(con.execute("SELECT COUNT(*) FROM lex_fact_grounded").fetchone()[0])
    stats.normative_facts = int(con.execute("SELECT COUNT(*) FROM lex_normative_facts").fetchone()[0])
    stats.high_confidence_norms = int(con.execute("SELECT COUNT(*) FROM lex_high_confidence_norms").fetchone()[0])


def _enrich_fact_domains(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        UPDATE lex_facts AS f
        SET top_domain = d.domain
        FROM (
            SELECT doc_id, domain
            FROM lex_doc_domains
            WHERE is_top = TRUE
        ) AS d
        WHERE f.doc_id = d.doc_id
        """
    )


def _flush_fact_related_batches(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    fact_rows: list[tuple],
    threshold_rows: list[tuple],
    clause_rows: list[tuple],
    link_rows: list[tuple],
) -> None:
    if fact_rows:
        con.executemany(
            """
            INSERT INTO lex_facts (
                fact_id, statement_id, subject_id, predicate, object_id,
                fact_text, confidence, norm_type, action_canon, norm_type_canon,
                subject_en, subject_uk, object_en, object_uk,
                condition_text_uk, exception_text_uk, procedure_text_uk,
                temporal_text_uk, sanction_text_uk,
                source_quote_uk, source_quote_start, source_quote_end,
                thresholds_json, trust_tier, grounding_status, canonical_status,
                reference_resolution_status, structure_quality, constraint_type_canon,
                legal_unit_subtype, route_class, empty_spo_retry_eligible, audit_miss_prone,
                reference_bearing, threshold_bearing, fused_confidence, confidence_breakdown_json,
                consistency_score, hallucination_flags_json, quality_band,
                doc_id, doc_reestr_code, doc_name, doc_type, doc_date_acc, doc_status,
                jurisdiction, top_domain, doc_family_id, version_id,
                provision_anchor, provision_citation, effective_from, effective_to,
                extraction_source, gate_score, gate_reason_codes, metadata
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            fact_rows,
        )
        stats.facts += len(fact_rows)
        fact_rows.clear()

    if threshold_rows:
        con.executemany(
            """
            INSERT INTO lex_rule_thresholds (
                threshold_id, fact_id, metric, operator, value_decimal,
                value_text, unit, applies_to, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            threshold_rows,
        )
        stats.thresholds += len(threshold_rows)
        threshold_rows.clear()

    if clause_rows:
        con.executemany(
            """
            INSERT INTO lex_rule_clauses (
                clause_id, fact_id, clause_type, text_uk, expr_json, metadata
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            clause_rows,
        )
        stats.clauses += len(clause_rows)
        clause_rows.clear()

    if link_rows:
        con.executemany(
            """
            INSERT INTO lex_rule_links (
                link_id, fact_id, relation_type, target_doc_id,
                target_anchor, ref_text_uk, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            link_rows,
        )
        stats.links += len(link_rows)
        link_rows.clear()


def _stream_facts_to_duckdb(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    dedup: EntityDeduplicator,
    spo_results_dir: Path,
    provisions_dir: Path,
    references_dir: Path | None,
    doc_metadata: dict[str, dict],
    insert_batch_size: int,
) -> None:
    fact_rows: list[tuple] = []
    threshold_rows: list[tuple] = []
    clause_rows: list[tuple] = []
    link_rows: list[tuple] = []
    fact_signatures_by_id: dict[str, str] = {}
    fact_ids_by_signature: dict[str, str] = {}
    skipped_duplicate_facts = 0
    fact_id_collisions = 0

    for jsonl_file in sorted(spo_results_dir.glob("**/*.jsonl")):
        stats.spo_files_read += 1
        doc_id = jsonl_file.stem
        meta = doc_metadata.get(doc_id, {})
        provisions = read_provisions(provisions_dir=provisions_dir, doc_id=doc_id)
        ctx_by_anchor = {str(row.get("anchor_path") or ""): str(row.get("text") or "") for row in provisions}
        prov_by_anchor = {
            str(row.get("anchor_path") or ""): row
            for row in provisions
            if str(row.get("anchor_path") or "")
        }
        resolved_reference_statuses = _resolved_reference_statuses(
            references_dir=references_dir,
            doc_id=doc_id,
        )
        current_doc_family_id = doc_family_id(meta)
        version_id = doc_id

        with open(jsonl_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                result = SPOExtractionResult.model_validate_json(line)
                fact_metadata_json = json.dumps(
                    {
                        "low_confidence": result.low_confidence,
                        "low_confidence_reasons": result.low_confidence_reasons,
                        "legal_unit_subtype": result.legal_unit_subtype,
                        "route_class": result.route_class,
                        "empty_spo_retry_eligible": result.empty_spo_retry_eligible,
                        "audit_miss_prone": result.audit_miss_prone,
                        "reference_bearing": result.reference_bearing,
                        "threshold_bearing": result.threshold_bearing,
                    },
                    ensure_ascii=False,
                )
                extraction_source = result.extraction_source or "llm"
                gate_score = float(result.gate_score or 0.0)
                gate_reason_codes = (
                    json.dumps(result.gate_reason_codes, ensure_ascii=False)
                    if result.gate_reason_codes
                    else "[]"
                )

                for stmt in result.statements:
                    provision_meta = prov_by_anchor.get(result.provision_anchor, {})
                    subj_id = dedup.get_or_create(stmt.subject_en, stmt.subject_uk)
                    obj_id = dedup.get_or_create(stmt.object_en, stmt.object_uk)

                    base_fid = _fact_id(
                        doc_id,
                        result.provision_anchor,
                        stmt.statement_id,
                        stmt.source_quote_start,
                        stmt.source_quote_end,
                    )
                    fid, is_exact_duplicate, used_collision_id = _allocate_fact_id(
                        base_fact_id=base_fid,
                        signature=_fact_signature(
                            provision_anchor=result.provision_anchor,
                            extraction_source=extraction_source,
                            stmt=stmt,
                        ),
                        fact_signatures_by_id=fact_signatures_by_id,
                        fact_ids_by_signature=fact_ids_by_signature,
                    )
                    if is_exact_duplicate:
                        skipped_duplicate_facts += 1
                        continue
                    if used_collision_id:
                        fact_id_collisions += 1

                    thresholds_json = json.dumps(
                        [th.model_dump(mode="json") for th in stmt.thresholds],
                        ensure_ascii=False,
                    )
                    fact_rows.append(
                        (
                            fid,
                            stmt.statement_id,
                            subj_id,
                            stmt.predicate,
                            obj_id,
                            stmt.fact_text_en or stmt.fact_text,
                            stmt.confidence_final if stmt.confidence_final is not None else stmt.confidence,
                            stmt.norm_type,
                            stmt.action_canon,
                            stmt.norm_type_canon,
                            stmt.subject_en,
                            stmt.subject_uk,
                            stmt.object_en,
                            stmt.object_uk,
                            stmt.condition_text_uk,
                            stmt.exception_text_uk,
                            stmt.procedure_text_uk,
                            stmt.temporal_text_uk,
                            stmt.sanction_text_uk,
                            stmt.source_quote_uk,
                            stmt.source_quote_start,
                            stmt.source_quote_end,
                            thresholds_json,
                            stmt.trust_tier,
                            stmt.grounding_status,
                            stmt.canonical_status,
                            _merge_reference_status(
                                stmt.reference_resolution_status,
                                resolved_reference_statuses.get(result.provision_anchor, "not_applicable"),
                            ),
                            stmt.structure_quality
                            or (
                                "fallback_search_only"
                                if bool(provision_meta.get("is_fallback_chunk", False))
                                else "structured_legal_unit"
                            ),
                            stmt.constraint_type_canon,
                            result.legal_unit_subtype,
                            result.route_class,
                            bool(result.empty_spo_retry_eligible),
                            bool(result.audit_miss_prone),
                            bool(result.reference_bearing),
                            bool(result.threshold_bearing),
                            stmt.fused_confidence,
                            stmt.confidence_breakdown_json or "",
                            stmt.consistency_score,
                            stmt.hallucination_flags_json or "",
                            stmt.quality_band or "",
                            doc_id,
                            meta.get("reestr_code", ""),
                            meta.get("name", ""),
                            meta.get("doc_type", ""),
                            meta.get("date_acc", ""),
                            meta.get("status", ""),
                            "UA",
                            "",
                            current_doc_family_id,
                            version_id,
                            result.provision_anchor,
                            result.provision_citation,
                            meta.get("date_acc", ""),
                            "",
                            extraction_source,
                            gate_score,
                            gate_reason_codes,
                            fact_metadata_json,
                        )
                    )

                    for idx, threshold in enumerate(stmt.thresholds, start=1):
                        tid = _stable_hash(fid, str(idx), threshold.metric, threshold.operator, size=24)
                        threshold_rows.append(
                            (
                                tid,
                                fid,
                                threshold.metric,
                                threshold.operator,
                                threshold.value_decimal,
                                threshold.value_text,
                                threshold.unit,
                                threshold.applies_to,
                                None,
                            )
                        )

                    clause_items = (
                        ("condition", stmt.condition_text_uk),
                        ("exception", stmt.exception_text_uk),
                        ("procedure", stmt.procedure_text_uk),
                        ("temporal", stmt.temporal_text_uk),
                        ("sanction", stmt.sanction_text_uk),
                    )
                    for clause_type, clause_text in clause_items:
                        if not clause_text.strip():
                            continue
                        cid = _stable_hash(fid, clause_type, clause_text[:200], size=24)
                        clause_rows.append((cid, fid, clause_type, clause_text, None, None))

                    for idx, link in enumerate(stmt.links, start=1):
                        lid = _stable_hash(
                            fid,
                            str(idx),
                            link.relation_type,
                            link.target_doc_id,
                            link.target_anchor,
                            size=24,
                        )
                        link_rows.append(
                            (
                                lid,
                                fid,
                                link.relation_type,
                                link.target_doc_id,
                                link.target_anchor,
                                link.ref_text_uk,
                                None,
                            )
                        )

                    if len(fact_rows) >= insert_batch_size:
                        _flush_fact_related_batches(
                            con=con,
                            stats=stats,
                            fact_rows=fact_rows,
                            threshold_rows=threshold_rows,
                            clause_rows=clause_rows,
                            link_rows=link_rows,
                        )

        stats.docs_processed += 1
        if stats.docs_processed % 5000 == 0:
            logger.info(
                "Graph builder: {} docs, {} entities, {} facts inserted",
                stats.docs_processed,
                dedup.count,
                stats.facts,
            )

    _flush_fact_related_batches(
        con=con,
        stats=stats,
        fact_rows=fact_rows,
        threshold_rows=threshold_rows,
        clause_rows=clause_rows,
        link_rows=link_rows,
    )
    if skipped_duplicate_facts or fact_id_collisions:
        logger.warning(
            "Graph builder deduplicated {} exact fact duplicates and rewrote {} fact_id collisions",
            skipped_duplicate_facts,
            fact_id_collisions,
        )


def _stream_provisions_to_duckdb(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    provisions_dir: Path,
    doc_metadata: dict[str, dict],
    insert_batch_size: int,
) -> None:
    batch: list[tuple] = []

    sql = """
    INSERT INTO lex_provisions (
        provision_id, doc_id, doc_reestr_code, doc_name, doc_type, doc_status,
        anchor_path, parent_anchor, depth, citation_label, kind, provision_text,
        offset_start, offset_end, token_count_est, text_hash, is_fallback_chunk,
        struct_kind, section_role, lineage_path, appendix_id, table_id,
        fallback_allowed_for_reasoning, legal_unit_subtype, route_class,
        empty_spo_retry_eligible, audit_miss_prone, reference_bearing, threshold_bearing, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for prov_file in sorted(provisions_dir.glob("**/*.jsonl")):
        doc_id = prov_file.stem
        meta = doc_metadata.get(doc_id, {})
        provisions = read_provisions(provisions_dir=provisions_dir, doc_id=doc_id)
        for prov in provisions:
            text = str(prov.get("text", ""))
            offset_start = int(prov.get("offset_start") or 0)
            offset_end = int(prov.get("offset_end") or max(offset_start + 1, len(text)))
            text_hash = str(prov.get("text_hash") or _stable_hash(text, size=16))
            pid = _provision_id(
                doc_id,
                str(prov.get("anchor_path", "")),
                offset_start,
                offset_end,
                text_hash,
            )
            row = (
                pid,
                doc_id,
                meta.get("reestr_code", ""),
                meta.get("name", ""),
                meta.get("doc_type", ""),
                meta.get("status", ""),
                str(prov.get("anchor_path", "")),
                str(prov.get("parent_anchor")) if prov.get("parent_anchor") is not None else None,
                int(prov.get("depth") or 0),
                str(prov.get("citation_label", "")),
                str(prov.get("kind", "")),
                text,
                offset_start,
                offset_end,
                int(prov.get("token_est") or _estimate_tokens(text)),
                text_hash,
                bool(prov.get("is_fallback_chunk", False)),
                str(prov.get("struct_kind") or ""),
                str(prov.get("section_role") or ""),
                str(prov.get("lineage_path") or prov.get("anchor_path") or ""),
                str(prov.get("appendix_id")) if prov.get("appendix_id") is not None else None,
                str(prov.get("table_id")) if prov.get("table_id") is not None else None,
                bool(prov.get("fallback_allowed_for_reasoning", False)),
                str(prov.get("legal_unit_subtype") or ""),
                str(prov.get("route_class") or ""),
                bool(prov.get("empty_spo_retry_eligible", False)),
                bool(prov.get("audit_miss_prone", False)),
                bool(prov.get("reference_bearing", False)),
                bool(prov.get("threshold_bearing", False)),
                json.dumps(
                    {
                        "legal_unit_subtype": str(prov.get("legal_unit_subtype") or ""),
                        "route_class": str(prov.get("route_class") or ""),
                        "empty_spo_retry_eligible": bool(prov.get("empty_spo_retry_eligible", False)),
                        "audit_miss_prone": bool(prov.get("audit_miss_prone", False)),
                        "reference_bearing": bool(prov.get("reference_bearing", False)),
                        "threshold_bearing": bool(prov.get("threshold_bearing", False)),
                    },
                    ensure_ascii=False,
                ),
            )
            batch.append(row)
            if len(batch) >= insert_batch_size:
                con.executemany(sql, batch)
                stats.provisions += len(batch)
                batch.clear()

    if batch:
        con.executemany(sql, batch)
        stats.provisions += len(batch)


def _stream_references_to_duckdb(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    references_dir: Path | None,
    insert_batch_size: int,
) -> None:
    if references_dir is None or not references_dir.exists():
        return

    sql = """
    INSERT INTO lex_references (
        reference_id, doc_id, provision_anchor, source_span_start, source_span_end,
        target_raw, ref_type, confidence, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[tuple] = []
    seen_reference_ids: set[str] = set()
    for ref_file in sorted(references_dir.glob("**/*.jsonl")):
        with open(ref_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                doc_id = str(row.get("doc_id", ""))
                anchor = str(row.get("anchor_path", ""))
                source_start = int(row.get("source_span_start") or 0)
                source_end = int(row.get("source_span_end") or source_start)
                target_raw = str(row.get("target_raw", ""))
                ref_type = str(row.get("type", ""))
                confidence = float(row.get("confidence") or 0.0)
                ref_id = _stable_hash(doc_id, anchor, str(source_start), str(source_end), target_raw, size=24)
                if ref_id in seen_reference_ids:
                    continue
                seen_reference_ids.add(ref_id)
                batch.append(
                    (
                        ref_id,
                        doc_id,
                        anchor,
                        source_start,
                        source_end,
                        target_raw,
                        ref_type,
                        confidence,
                        json.dumps(
                            {
                                key: value
                                for key, value in row.items()
                                if key
                                not in {
                                    "doc_id",
                                    "anchor_path",
                                    "source_span_start",
                                    "source_span_end",
                                    "target_raw",
                                    "type",
                                    "confidence",
                                }
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
                if len(batch) >= insert_batch_size:
                    con.executemany(sql, batch)
                    stats.references += len(batch)
                    batch.clear()
    if batch:
        con.executemany(sql, batch)
        stats.references += len(batch)


def _stream_domains_to_duckdb(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    domains_dir: Path | None,
    insert_batch_size: int,
) -> None:
    if domains_dir is None or not domains_dir.exists():
        return

    sql = """
    INSERT INTO lex_doc_domains (
        domain_id, doc_id, domain, score, rank, is_top, hits, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[tuple] = []
    for domain_file in sorted(domains_dir.glob("**/*.json")):
        with open(domain_file, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        doc_id = str(payload.get("doc_id", ""))
        top_domain = str(payload.get("top_domain") or "")
        scores = payload.get("scores", [])
        if not isinstance(scores, list):
            continue
        for idx, score_row in enumerate(scores, start=1):
            if not isinstance(score_row, dict):
                continue
            domain = str(score_row.get("domain") or "")
            score = float(score_row.get("score") or 0.0)
            hits = int(score_row.get("hits") or 0)
            domain_id = _stable_hash(doc_id, domain, str(idx), size=24)
            batch.append(
                (
                    domain_id,
                    doc_id,
                    domain,
                    score,
                    idx,
                    bool(top_domain and domain == top_domain),
                    hits,
                    None,
                )
            )
            if len(batch) >= insert_batch_size:
                con.executemany(sql, batch)
                stats.doc_domains += len(batch)
                batch.clear()

    if batch:
        con.executemany(sql, batch)
        stats.doc_domains += len(batch)


def _stream_reference_edges_to_duckdb(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    references_dir: Path | None,
    insert_batch_size: int,
) -> None:
    if references_dir is None or not references_dir.exists():
        return

    sql = """
    INSERT INTO lex_reference_edges (
        reference_edge_id, source_doc_id, source_doc_family_id, source_anchor,
        target_doc_id, target_doc_family_id, target_doc_reestr_code, target_doc_number,
        target_doc_type, target_doc_date_acc, target_doc_status, target_anchor,
        relation_type, matched_by, resolution_confidence, resolution_status, ref_text_uk, version_id, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[tuple] = []
    seen_edge_ids: set[str] = set()
    for ref_file in sorted(references_dir.glob("**/*.jsonl")):
        with open(ref_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                edge_id = str(
                    row.get("reference_edge_id")
                    or _stable_hash(
                        str(row.get("doc_id") or ""),
                        str(row.get("anchor_path") or ""),
                        str(row.get("target_doc_id") or ""),
                        str(row.get("target_anchor") or ""),
                        size=24,
                    )
                )
                if edge_id in seen_edge_ids:
                    continue
                seen_edge_ids.add(edge_id)
                batch.append(
                    (
                        edge_id,
                        str(row.get("doc_id") or ""),
                        str(row.get("source_doc_family_id") or ""),
                        str(row.get("anchor_path") or ""),
                        str(row.get("target_doc_id") or ""),
                        str(row.get("target_doc_family_id") or ""),
                        str(row.get("target_doc_reestr_code") or ""),
                        str(row.get("target_doc_number") or ""),
                        str(row.get("target_doc_type") or ""),
                        str(row.get("target_doc_date_acc") or ""),
                        str(row.get("target_doc_status") or ""),
                        str(row.get("target_anchor") or ""),
                        str(row.get("relation_type") or row.get("type") or "references"),
                        str(row.get("matched_by") or ""),
                        float(row.get("resolution_confidence") or row.get("confidence") or 0.0),
                        str(row.get("resolution_status") or "unresolved"),
                        str(row.get("target_raw") or ""),
                        str(row.get("target_version_id") or row.get("version_id") or row.get("target_doc_id") or ""),
                        json.dumps(
                            {
                                key: value
                                for key, value in row.items()
                                if key
                                not in {
                                    "reference_edge_id",
                                    "doc_id",
                                    "source_doc_family_id",
                                    "anchor_path",
                                    "target_doc_id",
                                    "target_doc_family_id",
                                    "target_doc_reestr_code",
                                    "target_doc_number",
                                    "target_doc_type",
                                    "target_doc_date_acc",
                                    "target_doc_status",
                                    "target_anchor",
                                    "relation_type",
                                    "matched_by",
                                    "resolution_confidence",
                                    "resolution_status",
                                    "target_raw",
                                    "target_version_id",
                                    "version_id",
                                }
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
                if len(batch) >= insert_batch_size:
                    con.executemany(sql, batch)
                    stats.reference_edges += len(batch)
                    batch.clear()
    if batch:
        con.executemany(sql, batch)
        stats.reference_edges += len(batch)


def _stream_reference_resolution_audit_to_duckdb(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    references_dir: Path | None,
    insert_batch_size: int,
) -> None:
    if references_dir is None or not references_dir.exists():
        return
    sql = """
    INSERT INTO lex_reference_resolution_audit (
        ref_id, source_doc_id, source_anchor, ref_text_uk, target_raw,
        resolution_method, resolution_status, resolution_confidence, candidate_count,
        selected_target_doc_id, alternatives_json, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[tuple[Any, ...]] = []
    seen_ids: set[str] = set()
    for ref_file in sorted(references_dir.glob("**/*.jsonl")):
        with open(ref_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                ref_id = str(row.get("reference_edge_id") or _stable_hash(str(row.get("doc_id") or ""), str(row.get("anchor_path") or ""), str(row.get("target_raw") or ""), "audit", size=24))
                if ref_id in seen_ids:
                    continue
                seen_ids.add(ref_id)
                batch.append(
                    (
                        ref_id,
                        str(row.get("doc_id") or ""),
                        str(row.get("anchor_path") or ""),
                        str(row.get("target_raw") or ""),
                        str(row.get("target_raw") or ""),
                        str(row.get("resolution_method") or row.get("matched_by") or ""),
                        str(row.get("resolution_status") or "unresolved"),
                        float(row.get("resolution_confidence") or 0.0),
                        int(row.get("candidate_count") or 0),
                        str(row.get("selected_target_doc_id") or row.get("target_doc_id") or ""),
                        str(row.get("alternatives_json") or "[]"),
                        json.dumps(
                            {
                                "relation_type": str(row.get("relation_type") or row.get("type") or "references"),
                                "target_anchor": str(row.get("target_anchor") or ""),
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
                status = str(row.get("resolution_status") or "unresolved").strip().lower()
                if status in {"resolved", "partial"}:
                    stats.reference_resolution_resolved += 1
                if status == "partial":
                    stats.reference_resolution_partial += 1
                if len(batch) >= insert_batch_size:
                    con.executemany(sql, batch)
                    stats.reference_resolution_audit += len(batch)
                    batch.clear()
    if batch:
        con.executemany(sql, batch)
        stats.reference_resolution_audit += len(batch)


def _stream_pattern_feedback_to_duckdb(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    feedback_queue_path: Path | None,
    insert_batch_size: int,
) -> None:
    if feedback_queue_path is None or not feedback_queue_path.exists():
        return
    sql = """
    INSERT INTO lex_pattern_feedback_queue (
        feedback_id, doc_id, provision_anchor, quality_family, legal_unit_subtype,
        route_class, deterministic_reason_codes, llm_delta, miss_categories_json,
        cluster_key, suggestion_family, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[tuple[Any, ...]] = []
    with open(feedback_queue_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            batch.append(
                (
                    str(row.get("feedback_id") or ""),
                    str(row.get("doc_id") or ""),
                    str(row.get("provision_anchor") or ""),
                    str(row.get("quality_family") or "other"),
                    str(row.get("legal_unit_subtype") or ""),
                    str(row.get("route_class") or ""),
                    json.dumps(row.get("deterministic_reason_codes") or [], ensure_ascii=False),
                    int(row.get("llm_delta") or 0),
                    json.dumps(row.get("miss_categories") or [], ensure_ascii=False),
                    str(row.get("cluster_key") or ""),
                    str(row.get("suggestion_family") or ""),
                    json.dumps(row.get("metadata") or {}, ensure_ascii=False),
                )
            )
            if len(batch) >= insert_batch_size:
                con.executemany(sql, batch)
                stats.pattern_feedback_queue += len(batch)
                batch.clear()
    if batch:
        con.executemany(sql, batch)
        stats.pattern_feedback_queue += len(batch)


def _stream_amendments_to_duckdb(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    provisions_dir: Path,
    references_dir: Path | None,
    doc_metadata: dict[str, dict],
    insert_batch_size: int,
) -> None:
    provision_files = sorted(provisions_dir.glob("**/*.jsonl"))
    if not provision_files:
        return
    doc_index = build_doc_resolution_index(doc_metadata)
    sql = """
    INSERT INTO lex_amendments (
        amendment_id, amending_doc_id, amended_doc_id, amendment_type, target_anchor,
        old_text_uk, new_text_uk, effective_from, detected_by, confidence, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[tuple[Any, ...]] = []
    for jsonl_file in provision_files:
        doc_id = jsonl_file.stem
        meta = doc_metadata.get(doc_id, {})
        doc_amendment_count = 0
        doc_targeted_amendment_count = 0
        amendment_target_hints = _load_amendment_target_hints_for_doc(
            references_dir=references_dir,
            doc_id=doc_id,
        )
        with open(jsonl_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                text = str(row.get("text") or "")
                if not text:
                    continue
                amendments = detect_amendments(text)
                for idx, amendment in enumerate(amendments, start=1):
                    doc_amendment_count += 1
                    amended_doc_id, target_hint = _select_amendment_target(
                        source_doc_id=doc_id,
                        doc_meta=meta,
                        target_hints=amendment_target_hints,
                        source_text=amendment.source_text,
                        target_anchor=amendment.target_anchor,
                        doc_index=doc_index,
                    )
                    if amended_doc_id:
                        doc_targeted_amendment_count += 1
                    target_source = str(target_hint.get("source") or "").strip().lower()
                    detected_by = "pattern"
                    if target_source:
                        if target_source.startswith("doc_title"):
                            detected_by = "pattern+title"
                        elif target_source.startswith("doc_metadata"):
                            detected_by = "pattern+metadata"
                        elif target_source.startswith("source_text"):
                            detected_by = "pattern+source_text"
                        else:
                            detected_by = "pattern+refs"
                    batch.append(
                        (
                            _stable_hash(doc_id, row.get("anchor_path", ""), amendment.amendment_type, str(idx), size=24),
                            doc_id,
                            amended_doc_id,
                            amendment.amendment_type,
                            amendment.target_anchor,
                            amendment.old_text_uk,
                            amendment.new_text_uk,
                            amendment.effective_from,
                            detected_by,
                            amendment.confidence,
                            json.dumps(
                                {
                                    "source_anchor": str(row.get("anchor_path") or ""),
                                    "source_text": amendment.source_text,
                                    "target_resolution_method": str(target_hint.get("source") or ""),
                                    "target_resolution_score": float(target_hint.get("score") or 0.0),
                                    "target_resolution_candidates_count": int(
                                        target_hint.get("target_resolution_candidates_count") or 0
                                    ),
                                    "target_hint": target_hint,
                                },
                                ensure_ascii=False,
                            ),
                        )
                    )
                    if len(batch) >= insert_batch_size:
                        con.executemany(sql, batch)
                        stats.amendments += len(batch)
                        batch.clear()
        if doc_amendment_count > 0:
            stats.amendment_docs_total += 1
            if doc_targeted_amendment_count > 0:
                stats.amendment_docs_with_target += 1
            stats.amendments_with_target += doc_targeted_amendment_count
    if batch:
        con.executemany(sql, batch)
        stats.amendments += len(batch)


def _load_amendment_target_hints_for_doc(
    *,
    references_dir: Path | None,
    doc_id: str,
) -> list[dict[str, Any]]:
    if references_dir is None:
        return []
    ref_path = references_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"
    if not ref_path.exists():
        return []

    hints: list[dict[str, Any]] = []
    with open(ref_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            target_doc_id = str(row.get("selected_target_doc_id") or row.get("target_doc_id") or "")
            if not target_doc_id or target_doc_id == doc_id:
                continue
            status = str(row.get("resolution_status") or "").strip().lower()
            if status not in {"resolved", "partial"}:
                continue
            hints.append(
                {
                    "target_doc_id": target_doc_id,
                    "relation_type": str(row.get("relation_type") or row.get("relation_hint") or "references"),
                    "resolution_confidence": float(row.get("resolution_confidence") or row.get("confidence") or 0.0),
                    "matched_by": str(row.get("matched_by") or row.get("resolution_method") or ""),
                    "target_anchor": str(row.get("target_anchor") or ""),
                    "target_doc_type": str(row.get("target_doc_type") or ""),
                }
            )
    return hints


def _select_amendment_target(
    *,
    source_doc_id: str,
    doc_meta: dict[str, Any],
    target_hints: list[dict[str, Any]],
    source_text: str,
    target_anchor: str,
    doc_index: DocResolutionIndex,
) -> tuple[str, dict[str, Any]]:
    explicit_target = _explicit_amendment_target_from_meta(doc_meta=doc_meta, doc_index=doc_index)
    if explicit_target:
        return explicit_target.doc_id, {
            "source": explicit_target.source,
            "target_doc_id": explicit_target.doc_id,
            "target_doc_name": explicit_target.doc_name,
            "score": round(explicit_target.score, 4),
            "target_resolution_candidates_count": explicit_target.candidate_count,
        }

    relation_priority = {
        "amends": 5,
        "repeals": 4,
        "replaces": 4,
        "supplements": 3,
        "approves": 2,
        "references": 1,
    }
    ranked = sorted(
        (
            hint
            for hint in target_hints
            if str(hint.get("target_doc_id") or "").strip()
            and str(hint.get("target_doc_id") or "").strip() != source_doc_id
        ),
        key=lambda hint: (
            relation_priority.get(str(hint.get("relation_type") or "").strip().lower(), 0),
            float(hint.get("resolution_confidence") or 0.0),
        ),
        reverse=True,
    )
    if ranked:
        best = ranked[0]
        return str(best.get("target_doc_id") or ""), {
            **best,
            "source": str(best.get("source") or "resolved_references"),
            "target_resolution_candidates_count": len(ranked),
        }

    inferred = _infer_amendment_target_from_title(
        source_doc_id=source_doc_id,
        doc_meta=doc_meta,
        doc_index=doc_index,
    )
    if inferred is not None:
        return inferred.doc_id, {
            "source": inferred.source,
            "target_doc_id": inferred.doc_id,
            "target_doc_name": inferred.doc_name,
            "score": round(inferred.score, 4),
            "target_resolution_candidates_count": inferred.candidate_count,
        }

    inferred_from_source = _infer_amendment_target_from_source_text(
        source_doc_id=source_doc_id,
        source_text=source_text,
        target_anchor=target_anchor,
        doc_index=doc_index,
    )
    if inferred_from_source is not None:
        return inferred_from_source.doc_id, {
            "source": inferred_from_source.source,
            "target_doc_id": inferred_from_source.doc_id,
            "target_doc_name": inferred_from_source.doc_name,
            "score": round(inferred_from_source.score, 4),
            "target_resolution_candidates_count": inferred_from_source.candidate_count,
        }
    return "", {}


@dataclass(frozen=True)
class _AmendmentTargetMatch:
    doc_id: str
    doc_name: str
    source: str
    score: float
    candidate_count: int = 1


def _explicit_amendment_target_from_meta(
    *,
    doc_meta: dict[str, Any],
    doc_index: DocResolutionIndex,
) -> _AmendmentTargetMatch | None:
    def _first_value(keys: tuple[str, ...]) -> str:
        for key in keys:
            value = str(doc_meta.get(key) or "").strip()
            if value:
                return value
        return ""

    explicit_doc_id = _first_value(
        (
            "amends_doc_id",
            "amended_doc_id",
            "target_doc_id",
            "amendment_target_doc_id",
        )
    )
    if explicit_doc_id and explicit_doc_id in doc_index.by_doc_id:
        entry = doc_index.by_doc_id[explicit_doc_id]
        return _AmendmentTargetMatch(
            doc_id=entry.doc_id,
            doc_name=entry.name,
            source="doc_metadata",
            score=1.0,
        )

    reestr_code = normalize_ref_number(
        _first_value(
            (
                "amends_reestr_code",
                "amended_reestr_code",
                "target_reestr_code",
                "amendment_target_reestr_code",
            )
        )
    )
    if reestr_code:
        candidates = doc_index.by_reestr_code.get(reestr_code, [])
        if candidates:
            entry = candidates[-1]
            return _AmendmentTargetMatch(
                doc_id=entry.doc_id,
                doc_name=entry.name,
                source="doc_metadata_reestr_code",
                score=0.99,
            )

    number = normalize_ref_number(
        _first_value(
            (
                "amends_number",
                "amended_number",
                "target_number",
                "amendment_target_number",
            )
        )
    )
    date_acc = _first_value(
        (
            "amends_date_acc",
            "amended_date_acc",
            "target_date_acc",
            "amendment_target_date_acc",
            "target_date",
            "amendment_target_date",
        )
    )
    if number and date_acc:
        candidates = [*doc_index.by_number_date.get((number, date_acc), []), *doc_index.by_reg_number_date.get((number, date_acc), [])]
        if candidates:
            entry = candidates[-1]
            return _AmendmentTargetMatch(
                doc_id=entry.doc_id,
                doc_name=entry.name,
                source="doc_metadata_number_date",
                score=0.98,
            )

    target_name = _first_value(
        (
            "amends_name",
            "amended_name",
            "target_name",
            "amendment_target_name",
            "target_doc_name",
        )
    )
    if target_name:
        return _best_title_target_match(
            source_doc_id="",
            target_raw=target_name,
            doc_index=doc_index,
            source="doc_metadata_name",
        )
    return None


def _infer_amendment_target_from_title(
    *,
    source_doc_id: str,
    doc_meta: dict[str, Any],
    doc_index: DocResolutionIndex,
) -> _AmendmentTargetMatch | None:
    doc_name = str(doc_meta.get("name") or "").strip()
    if not doc_name:
        return None
    match = _AMENDMENT_TITLE_TARGET_RE.search(doc_name)
    if match is None:
        # Fallback: try to extract target from document number/date in the title
        number_hint = normalize_ref_number(doc_name)
        date_hint = ""
        date_match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", doc_name)
        if date_match:
            date_hint = date_match.group(1)
        if number_hint and date_hint:
            candidates = [
                *doc_index.by_number_date.get((number_hint, date_hint), []),
                *doc_index.by_reg_number_date.get((number_hint, date_hint), []),
            ]
            candidates = [e for e in candidates if e.doc_id != source_doc_id]
            if candidates:
                entry = candidates[-1]
                return _AmendmentTargetMatch(
                    doc_id=entry.doc_id,
                    doc_name=entry.name,
                    source="doc_title_number_date",
                    score=0.90,
                )
        return None
    target_raw = str(match.group("target") or "").strip()
    if not target_raw:
        return None
    target_raw = _AMENDMENT_TITLE_STOP_RE.split(target_raw, maxsplit=1)[0].strip(" \"'«»")
    if not target_raw:
        return None
    return _best_title_target_match(
        source_doc_id=source_doc_id,
        target_raw=target_raw,
        doc_index=doc_index,
        source="doc_title_inference",
    )


def _infer_amendment_target_from_source_text(
    *,
    source_doc_id: str,
    source_text: str,
    target_anchor: str,
    doc_index: DocResolutionIndex,
) -> _AmendmentTargetMatch | None:
    cleaned = " ".join(str(source_text or "").split()).strip()
    if not cleaned:
        return None

    fragments: list[str] = []
    for match in re.finditer(r"[«\"'](?P<target>[^»\"']{6,220})[»\"']", cleaned):
        fragment = str(match.group("target") or "").strip()
        if fragment:
            fragments.append(fragment)
    generic_target_match = re.search(
        r"(?:до|у)\s+(?P<target>[^,.:\n]{8,240})",
        cleaned,
        re.IGNORECASE,
    )
    if generic_target_match:
        target_fragment = str(generic_target_match.group("target") or "").strip()
        if target_fragment:
            fragments.append(target_fragment)
    if target_anchor:
        anchor_fragment = re.sub(r"^article:", "стаття ", str(target_anchor)).strip()
        if anchor_fragment:
            fragments.append(f"{cleaned} {anchor_fragment}")

    best_match: _AmendmentTargetMatch | None = None
    for fragment in fragments:
        match = _best_title_target_match(
            source_doc_id=source_doc_id,
            target_raw=fragment,
            doc_index=doc_index,
            source="source_text_inference",
        )
        if match is None:
            continue
        if best_match is None or match.score > best_match.score:
            best_match = match
    return best_match


def _best_title_target_match(
    *,
    source_doc_id: str,
    target_raw: str,
    doc_index: DocResolutionIndex,
    source: str,
) -> _AmendmentTargetMatch | None:
    target_norm = normalize_text_key(target_raw)
    if not target_norm:
        return None
    target_tokens = set(target_norm.split())
    # Filter out very common stop-words that inflate overlap scores
    _STOP = {"до", "та", "і", "в", "у", "на", "з", "із", "про", "що", "від", "за", "або"}
    target_content_tokens = target_tokens - _STOP
    type_hint = doc_type_category(target_raw)
    number_hint = normalize_ref_number(target_raw)
    ranked: list[tuple[float, DocIndexEntry]] = []
    for entry in doc_index.entries:
        if entry.doc_id == source_doc_id:
            continue
        if type_hint and type_hint not in {"regulation"} and entry.doc_type_category != type_hint:
            continue
        score = 0.0
        if number_hint and (entry.doc_number_norm == number_hint or entry.reg_number_norm == number_hint or entry.reestr_code_norm == number_hint):
            score = max(score, 0.98)
        if target_norm in entry.name_norm or entry.name_norm in target_norm:
            score = max(score, 0.92 if target_norm in entry.name_norm else 0.84)
        elif target_content_tokens:
            entry_tokens = set(entry.name_norm.split()) - _STOP
            overlap = len(target_content_tokens & entry_tokens)
            if overlap:
                # Harmonic mean of precision and recall over tokens
                precision = overlap / max(1, len(target_content_tokens))
                recall = overlap / max(1, len(entry_tokens))
                f1 = (2 * precision * recall) / max(0.001, precision + recall)
                score = max(score, f1)
        if score >= 0.40:
            ranked.append((score, entry))
    if not ranked:
        return None
    ranked.sort(
        key=lambda item: (
            item[0],
            item[1].doc_date.isoformat() if item[1].doc_date else str(item[1].meta.get("date_acc") or ""),
            item[1].doc_id,
        ),
        reverse=True,
    )
    best_score, best_entry = ranked[0]
    if len(ranked) > 1 and ranked[1][0] >= best_score - 0.03:
        return None
    return _AmendmentTargetMatch(
        doc_id=best_entry.doc_id,
        doc_name=best_entry.name,
        source=source,
        score=best_score,
        candidate_count=len(ranked),
    )


def _stream_doc_versions_to_duckdb(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    doc_metadata: dict[str, dict],
    insert_batch_size: int,
) -> None:
    if not doc_metadata:
        return

    family_entries: dict[str, list[tuple[str, dict]]] = {}
    for doc_id, meta in doc_metadata.items():
        family_entries.setdefault(doc_family_id(meta), []).append((doc_id, meta))

    version_rows: list[tuple] = []
    for family_id, family_docs in sorted(family_entries.items()):
        ordered = sorted(
            family_docs,
            key=lambda item: version_sort_key(item[1], item[0]),
        )
        for idx, (doc_id, meta) in enumerate(ordered, start=1):
            previous_version_id = ordered[idx - 2][0] if idx > 1 else None
            next_version_id = ordered[idx][0] if idx < len(ordered) else None
            publisher_parts = meta.get("publisher")
            publisher = (
                " ".join(str(item) for item in publisher_parts)
                if isinstance(publisher_parts, (list, tuple))
                else str(publisher_parts or "")
            )
            version_rows.append(
                (
                    _stable_hash(doc_id, family_id, size=24),
                    doc_id,
                    family_id,
                    doc_id,
                    str(meta.get("reestr_code") or ""),
                    str(meta.get("number") or ""),
                    str(meta.get("reg_number") or ""),
                    publisher,
                    str(meta.get("name") or ""),
                    str(meta.get("doc_type") or ""),
                    str(meta.get("date_acc") or ""),
                    str(meta.get("status") or ""),
                    idx,
                    previous_version_id,
                    next_version_id,
                    bool(idx == len(ordered)),
                    json.dumps(
                        {
                            "publisher_raw": meta.get("publisher"),
                            "publisher_norm": normalize_publishers(meta.get("publisher")),
                            "reestr_date": str(meta.get("reestr_date") or ""),
                            "reg_date": str(meta.get("reg_date") or ""),
                        },
                        ensure_ascii=False,
                    ),
                )
            )

    sql = """
    INSERT INTO lex_doc_versions (
        version_row_id, doc_id, doc_family_id, version_id, doc_reestr_code,
        doc_number, reg_number, publisher, doc_name, doc_type, doc_date_acc,
        doc_status, version_rank, previous_version_id, next_version_id, is_latest, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[tuple] = []
    for row in version_rows:
        batch.append(row)
        if len(batch) >= insert_batch_size:
            con.executemany(sql, batch)
            stats.doc_versions += len(batch)
            batch.clear()
    if batch:
        con.executemany(sql, batch)
        stats.doc_versions += len(batch)


def _insert_entities(
    *,
    con: duckdb.DuckDBPyConnection,
    dedup: EntityDeduplicator,
    insert_batch_size: int,
) -> int:
    sql = """
    INSERT INTO lex_entities (
        entity_id, name_en, name_uk, entity_type, entity_subtype,
        mention_count, aliases_en, aliases_uk, wikidata_id, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[tuple] = []
    count = 0
    for rec in dedup.all_records():
        row = (
            rec.entity_id,
            rec.name_en,
            rec.name_uk,
            rec.entity_type,
            rec.entity_subtype or None,
            rec.mention_count,
            "; ".join(sorted(rec.aliases_en)) if rec.aliases_en else None,
            "; ".join(sorted(rec.aliases_uk)) if rec.aliases_uk else None,
            rec.wikidata_id or None,
            json.dumps({"entity_subtype": rec.entity_subtype or ""}, ensure_ascii=False),
        )
        batch.append(row)
        if len(batch) >= insert_batch_size:
            con.executemany(sql, batch)
            count += len(batch)
            batch.clear()

    if batch:
        con.executemany(sql, batch)
        count += len(batch)
    return count


def _ensure_indexes(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in _INDEXES.strip().split(";"):
        sql = stmt.strip()
        if sql:
            con.execute(sql)
