"""Consistency checks for normative legal facts."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from polisyos.lex.batch.patterns import DOC_TYPE_HIERARCHY_UA

if TYPE_CHECKING:
    import duckdb

_CONTRADICTIONS_SQL = """
WITH active_norms AS (
    SELECT
        f.fact_id,
        COALESCE(f.subject_en, '') AS subject_en,
        COALESCE(f.object_en, '') AS object_en,
        COALESCE(f.norm_type_canon, f.norm_type, '') AS norm_type,
        COALESCE(f.action_canon, f.predicate, '') AS action_canon,
        COALESCE(f.doc_id, '') AS doc_id,
        COALESCE(f.doc_type, '') AS doc_type,
        COALESCE(f.doc_date_acc, '') AS doc_date_acc,
        COALESCE(f.provision_anchor, '') AS provision_anchor,
        COALESCE(v.is_latest, TRUE) AS is_latest,
        COALESCE(v.doc_status, COALESCE(f.doc_status, '')) AS doc_status
    FROM lex_normative_facts f
    LEFT JOIN lex_doc_versions v ON v.doc_id = f.doc_id
    WHERE COALESCE(f.jurisdiction, 'UA') = ?
),
filtered AS (
    SELECT * FROM active_norms
    WHERE is_latest = TRUE
      AND LOWER(doc_status) NOT IN ('скасовано', 'втратив чинність')
),
pairs AS (
    SELECT
        a.fact_id AS fact_id_1,
        b.fact_id AS fact_id_2,
        a.subject_en,
        a.object_en,
        a.norm_type AS norm_type_1,
        b.norm_type AS norm_type_2,
        a.doc_id AS doc_id_1,
        b.doc_id AS doc_id_2,
        a.doc_type AS doc_type_1,
        b.doc_type AS doc_type_2,
        a.doc_date_acc AS doc_date_acc_1,
        b.doc_date_acc AS doc_date_acc_2,
        a.provision_anchor AS anchor_1,
        b.provision_anchor AS anchor_2,
        a.action_canon AS action_1,
        b.action_canon AS action_2
    FROM filtered a
    JOIN filtered b
      ON a.subject_en = b.subject_en
     AND a.object_en = b.object_en
     AND a.fact_id < b.fact_id
     AND (
        (a.norm_type = 'obligation' AND b.norm_type = 'prohibition')
        OR (a.norm_type = 'prohibition' AND b.norm_type = 'obligation')
        OR (a.norm_type = 'permission' AND b.norm_type = 'prohibition')
        OR (a.norm_type = 'prohibition' AND b.norm_type = 'permission')
     )
)
SELECT *
FROM pairs
WHERE action_1 = action_2 OR action_1 = '' OR action_2 = ''
"""


def detect_consistency_issues(
    con: duckdb.DuckDBPyConnection,
    *,
    jurisdiction: str = "UA",
) -> int:
    """Detect consistency issues helper."""
    if not _table_exists(con, "lex_consistency_issues") or not _table_exists(
        con, "lex_normative_facts"
    ):
        return 0
    con.execute("DELETE FROM lex_consistency_issues")
    rows = con.execute(_CONTRADICTIONS_SQL, [jurisdiction]).fetchall()
    payloads: list[tuple[Any, ...]] = []
    for row in rows:
        principle, prevailing_doc_id = _resolve_principle(
            doc_type_1=str(row[8] or ""),
            doc_type_2=str(row[9] or ""),
            doc_date_1=str(row[10] or ""),
            doc_date_2=str(row[11] or ""),
            doc_id_1=str(row[6] or ""),
            doc_id_2=str(row[7] or ""),
        )
        issue_id = hashlib.sha256(
            "|".join(str(item or "") for item in row[:6]).encode("utf-8")
        ).hexdigest()[:24]
        payloads.append(
            (
                issue_id,
                "cross_document_contradiction"
                if str(row[6] or "") != str(row[7] or "")
                else "intra_document_contradiction",
                str(row[0] or ""),
                str(row[1] or ""),
                str(row[6] or ""),
                str(row[7] or ""),
                str(row[2] or ""),
                str(row[3] or ""),
                str(row[4] or ""),
                str(row[5] or ""),
                "high",
                principle,
                prevailing_doc_id,
                0.85 if prevailing_doc_id else 0.3,
                not bool(prevailing_doc_id),
                str(row[12] or ""),
                str(row[13] or ""),
            )
        )
    if payloads:
        con.executemany(
            """
            INSERT INTO lex_consistency_issues (
                issue_id, type, fact_id_1, fact_id_2, doc_id_1, doc_id_2,
                subject_en, object_en, norm_type_1, norm_type_2, severity,
                resolution_principle, prevailing_doc_id, resolution_confidence,
                requires_manual_review, anchor_1, anchor_2
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payloads,
        )
    return len(payloads)


def _resolve_principle(
    *,
    doc_type_1: str,
    doc_type_2: str,
    doc_date_1: str,
    doc_date_2: str,
    doc_id_1: str,
    doc_id_2: str,
) -> tuple[str, str]:
    rank_1 = DOC_TYPE_HIERARCHY_UA.get(doc_type_1, 999)
    rank_2 = DOC_TYPE_HIERARCHY_UA.get(doc_type_2, 999)
    if rank_1 < rank_2:
        return "lex_superior", doc_id_1
    if rank_2 < rank_1:
        return "lex_superior", doc_id_2
    if doc_date_1 and doc_date_2:
        if doc_date_1 > doc_date_2:
            return "lex_posterior", doc_id_1
        if doc_date_2 > doc_date_1:
            return "lex_posterior", doc_id_2
    return "unresolved", ""


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1",
        [table_name],
    ).fetchone()
    return row is not None
