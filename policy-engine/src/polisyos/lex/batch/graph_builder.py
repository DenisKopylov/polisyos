"""Stage 4: Stream SPO results into DuckDB knowledge graph."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import duckdb

from polisyos.lex.batch.provisions_io import provision_text_by_anchor, read_provisions
from polisyos.lex.knowledge.types import SPOExtractionResult

logger = logging.getLogger(__name__)

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
    original_context    VARCHAR,
    doc_id              VARCHAR NOT NULL,
    doc_reestr_code     VARCHAR,
    doc_name            VARCHAR,
    doc_type            VARCHAR,
    doc_date_acc        VARCHAR,
    doc_status          VARCHAR,
    provision_anchor    VARCHAR,
    provision_citation  VARCHAR,
    effective_from      DATE,
    effective_to        DATE,
    metadata            JSON,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
CREATE INDEX IF NOT EXISTS idx_entities_name ON lex_entities(name_en);
CREATE INDEX IF NOT EXISTS idx_provisions_doc ON lex_provisions(doc_id);
CREATE INDEX IF NOT EXISTS idx_thresholds_fact ON lex_rule_thresholds(fact_id);
CREATE INDEX IF NOT EXISTS idx_clauses_fact ON lex_rule_clauses(fact_id);
CREATE INDEX IF NOT EXISTS idx_links_fact ON lex_rule_links(fact_id);
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
    provisions: int = 0
    thresholds: int = 0
    clauses: int = 0
    links: int = 0
    docs_processed: int = 0
    spo_files_read: int = 0


def build_graph(
    *,
    spo_results_dir: Path,
    provisions_dir: Path,
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
        _stream_facts_to_duckdb(
            con=con,
            stats=stats,
            dedup=dedup,
            spo_results_dir=spo_results_dir,
            provisions_dir=provisions_dir,
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
        stats.entities = _insert_entities(
            con=con,
            dedup=dedup,
            insert_batch_size=insert_batch_size,
        )
        _ensure_indexes(con)
        con.execute("CHECKPOINT")
    finally:
        con.close()

    logger.info(
        "Graph built: %d entities, %d facts, %d provisions, %d thresholds, %d clauses, %d links in %s",
        stats.entities,
        stats.facts,
        stats.provisions,
        stats.thresholds,
        stats.clauses,
        stats.links,
        db_path,
    )
    return stats


def _init_schema(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in _DDL.strip().split(";"):
        sql = stmt.strip()
        if sql:
            con.execute(sql)


def _truncate_existing_rows(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DELETE FROM lex_rule_links")
    con.execute("DELETE FROM lex_rule_clauses")
    con.execute("DELETE FROM lex_rule_thresholds")
    con.execute("DELETE FROM lex_facts")
    con.execute("DELETE FROM lex_entities")
    con.execute("DELETE FROM lex_provisions")


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
                thresholds_json, original_context,
                doc_id, doc_reestr_code, doc_name, doc_type, doc_date_acc, doc_status,
                provision_anchor, provision_citation, effective_from, effective_to, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    doc_metadata: dict[str, dict],
    insert_batch_size: int,
) -> None:
    fact_rows: list[tuple] = []
    threshold_rows: list[tuple] = []
    clause_rows: list[tuple] = []
    link_rows: list[tuple] = []

    for jsonl_file in sorted(spo_results_dir.glob("**/*.jsonl")):
        stats.spo_files_read += 1
        doc_id = jsonl_file.stem
        meta = doc_metadata.get(doc_id, {})
        ctx_by_anchor = provision_text_by_anchor(provisions_dir=provisions_dir, doc_id=doc_id)

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
                    },
                    ensure_ascii=False,
                )

                for stmt in result.statements:
                    subj_id = dedup.get_or_create(stmt.subject_en, stmt.subject_uk)
                    obj_id = dedup.get_or_create(stmt.object_en, stmt.object_uk)

                    fid = _fact_id(
                        doc_id,
                        result.provision_anchor,
                        stmt.statement_id,
                        stmt.source_quote_start,
                        stmt.source_quote_end,
                    )

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
                            original_context,
                            doc_id,
                            meta.get("reestr_code", ""),
                            meta.get("name", ""),
                            meta.get("doc_type", ""),
                            meta.get("date_acc", ""),
                            meta.get("status", ""),
                            result.provision_anchor,
                            result.provision_citation,
                            None,
                            None,
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
                "Graph builder: %d docs, %d entities, %d facts inserted",
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
        offset_start, offset_end, token_count_est, text_hash, is_fallback_chunk, metadata
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                None,
            )
            batch.append(row)
            if len(batch) >= insert_batch_size:
                con.executemany(sql, batch)
                stats.provisions += len(batch)
                batch.clear()

    if batch:
        con.executemany(sql, batch)
        stats.provisions += len(batch)


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
