"""Stage 4: Stream SPO results into DuckDB knowledge graph."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import duckdb

from polisyos.common.logger import get_logger
from polisyos.lex.batch.doc_identity import doc_family_id, normalize_publishers, version_sort_key
from polisyos.lex.batch.provisions_io import read_provisions
from polisyos.lex.knowledge.types import SPOExtractionResult

logger = get_logger(__name__)

_NORMALIZE_RE = re.compile(r"[^a-z0-9_]+")


def _normalize_entity_name(name: str) -> str:
    return _NORMALIZE_RE.sub("_", name.strip().lower()).strip("_")


def _stable_hash(*parts: str, size: int = 20) -> str:
    canon = "|".join(parts)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:size]


def _entity_id(normalized_name: str) -> str:
    return _stable_hash(normalized_name, size=16)


@dataclass
class _EntityRecord:
    entity_id: str
    name_en: str
    name_uk: str
    entity_type: str
    mention_count: int = 1
    aliases_en: set[str] = field(default_factory=set)
    aliases_uk: set[str] = field(default_factory=set)


class EntityDeduplicator:
    """In-memory entity dedup using normalized English name as canonical key."""

    def __init__(self) -> None:
        self._by_norm: dict[str, _EntityRecord] = {}

    def get_or_create(
        self,
        name_en: str,
        name_uk: str,
        entity_type: str = "concept",
    ) -> str:
        norm = _normalize_entity_name(name_en)
        if not norm:
            norm = _normalize_entity_name(name_uk) or "unknown"

        rec = self._by_norm.get(norm)
        if rec is not None:
            rec.mention_count += 1
            if name_en and name_en != rec.name_en:
                rec.aliases_en.add(name_en)
            if name_uk and name_uk != rec.name_uk:
                rec.aliases_uk.add(name_uk)
            return rec.entity_id

        eid = _entity_id(norm)
        self._by_norm[norm] = _EntityRecord(
            entity_id=eid,
            name_en=name_en,
            name_uk=name_uk,
            entity_type=entity_type,
        )
        return eid

    def all_records(self) -> Iterator[_EntityRecord]:
        yield from self._by_norm.values()

    @property
    def count(self) -> int:
        return len(self._by_norm)


_DDL = """
CREATE TABLE IF NOT EXISTS lex_entities (
    entity_id      VARCHAR PRIMARY KEY,
    name_en        VARCHAR NOT NULL,
    name_uk        VARCHAR,
    entity_type    VARCHAR NOT NULL,
    mention_count  INTEGER DEFAULT 1,
    aliases_en     VARCHAR,
    aliases_uk     VARCHAR,
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
    original_context    VARCHAR,
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

CREATE TABLE IF NOT EXISTS lex_fact_candidates AS
    SELECT * FROM lex_facts WHERE 1 = 0;

CREATE TABLE IF NOT EXISTS lex_fact_grounded AS
    SELECT * FROM lex_facts WHERE 1 = 0;

CREATE TABLE IF NOT EXISTS lex_normative_facts AS
    SELECT * FROM lex_facts WHERE 1 = 0;

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
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_facts_subject ON lex_facts(subject_id);
CREATE INDEX IF NOT EXISTS idx_facts_object ON lex_facts(object_id);
CREATE INDEX IF NOT EXISTS idx_facts_predicate ON lex_facts(predicate);
CREATE INDEX IF NOT EXISTS idx_facts_action_canon ON lex_facts(action_canon);
CREATE INDEX IF NOT EXISTS idx_facts_norm_type_canon ON lex_facts(norm_type_canon);
CREATE INDEX IF NOT EXISTS idx_facts_doc ON lex_facts(doc_id);
CREATE INDEX IF NOT EXISTS idx_facts_trust_tier ON lex_facts(trust_tier);
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
    provisions: int = 0
    thresholds: int = 0
    clauses: int = 0
    links: int = 0
    references: int = 0
    reference_edges: int = 0
    doc_domains: int = 0
    doc_versions: int = 0
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
    insert_batch_size: int = 10_000,
) -> GraphStats:
    """Read SPO/provision files and stream rows to DuckDB."""
    stats = GraphStats()
    dedup = EntityDeduplicator()
    con = duckdb.connect(str(db_path))
    try:
        _init_schema(con)
        _truncate_existing_rows(con)

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
        con.execute("COMMIT")

        con.execute("BEGIN TRANSACTION")
        _stream_provisions_to_duckdb(
            con=con,
            stats=stats,
            provisions_dir=provisions_dir,
            doc_metadata=doc_metadata,
            insert_batch_size=insert_batch_size,
        )
        con.execute("COMMIT")

        con.execute("BEGIN TRANSACTION")
        _stream_references_to_duckdb(
            con=con,
            stats=stats,
            references_dir=references_dir,
            insert_batch_size=insert_batch_size,
        )
        con.execute("COMMIT")

        con.execute("BEGIN TRANSACTION")
        _stream_domains_to_duckdb(
            con=con,
            stats=stats,
            domains_dir=domains_dir,
            insert_batch_size=insert_batch_size,
        )
        con.execute("COMMIT")

        con.execute("BEGIN TRANSACTION")
        _stream_reference_edges_to_duckdb(
            con=con,
            stats=stats,
            references_dir=references_dir,
            insert_batch_size=insert_batch_size,
        )
        con.execute("COMMIT")

        con.execute("BEGIN TRANSACTION")
        _stream_doc_versions_to_duckdb(
            con=con,
            stats=stats,
            doc_metadata=doc_metadata,
            insert_batch_size=insert_batch_size,
        )
        con.execute("COMMIT")

        con.execute("BEGIN TRANSACTION")
        _enrich_fact_domains(con)
        _populate_fact_partitions(con=con, stats=stats)
        con.execute("COMMIT")

        con.execute("BEGIN TRANSACTION")
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
        "Graph built: {} entities, {} facts ({} candidate / {} grounded / {} normative), "
        "{} provisions, {} thresholds, {} clauses, {} links, {} references, {} resolved edges, {} domain rows in {}",
        stats.entities,
        stats.facts,
        stats.candidate_facts,
        stats.grounded_facts,
        stats.normative_facts,
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
    },
    "lex_fact_candidates": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
    },
    "lex_fact_grounded": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
    },
    "lex_normative_facts": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
    },
    "lex_provisions": {
        "legal_unit_subtype": "VARCHAR",
        "route_class": "VARCHAR",
        "empty_spo_retry_eligible": "BOOLEAN",
        "audit_miss_prone": "BOOLEAN",
        "reference_bearing": "BOOLEAN",
        "threshold_bearing": "BOOLEAN",
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
    con.execute("DELETE FROM lex_doc_versions")
    con.execute("DELETE FROM lex_reference_edges")
    con.execute("DELETE FROM lex_doc_domains")
    con.execute("DELETE FROM lex_references")
    con.execute("DELETE FROM lex_rule_links")
    con.execute("DELETE FROM lex_rule_clauses")
    con.execute("DELETE FROM lex_rule_thresholds")
    con.execute("DELETE FROM lex_normative_facts")
    con.execute("DELETE FROM lex_fact_grounded")
    con.execute("DELETE FROM lex_fact_candidates")
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
    con.execute("DELETE FROM lex_fact_candidates")
    con.execute("DELETE FROM lex_fact_grounded")
    con.execute("DELETE FROM lex_normative_facts")
    con.execute(
        "INSERT INTO lex_fact_candidates SELECT * FROM lex_facts WHERE trust_tier = 'search_candidate'"
    )
    con.execute(
        "INSERT INTO lex_fact_grounded SELECT * FROM lex_facts WHERE trust_tier IN ('grounded_fact', 'normative_fact')"
    )
    con.execute(
        "INSERT INTO lex_normative_facts SELECT * FROM lex_facts WHERE trust_tier = 'normative_fact'"
    )
    stats.candidate_facts = int(con.execute("SELECT COUNT(*) FROM lex_fact_candidates").fetchone()[0])
    stats.grounded_facts = int(con.execute("SELECT COUNT(*) FROM lex_fact_grounded").fetchone()[0])
    stats.normative_facts = int(con.execute("SELECT COUNT(*) FROM lex_normative_facts").fetchone()[0])


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
                reference_bearing, threshold_bearing, original_context,
                doc_id, doc_reestr_code, doc_name, doc_type, doc_date_acc, doc_status,
                jurisdiction, top_domain, doc_family_id, version_id,
                provision_anchor, provision_citation, effective_from, effective_to,
                extraction_source, gate_score, gate_reason_codes, metadata
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
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
                    original_context = (
                        stmt.source_quote_uk
                        or ctx_by_anchor.get(result.provision_anchor, "")
                    )[:500]

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
                            original_context,
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
        entity_id, name_en, name_uk, entity_type,
        mention_count, aliases_en, aliases_uk, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[tuple] = []
    count = 0
    for rec in dedup.all_records():
        row = (
            rec.entity_id,
            rec.name_en,
            rec.name_uk,
            rec.entity_type,
            rec.mention_count,
            "; ".join(sorted(rec.aliases_en)) if rec.aliases_en else None,
            "; ".join(sorted(rec.aliases_uk)) if rec.aliases_uk else None,
            None,
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
