"""Shared amendment quality metrics for QC and benchmark stages."""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

_SINGLE_TARGET_SCOPE_KINDS = {
    "explicit_target",
    "single_target_refs",
    "single_target_title",
    "amendment_title_unresolved",
}
_TITLE_SCOPE_KINDS = {
    "single_target_title",
    "amendment_title_unresolved",
}
_SCOPE_PRIORITY = {
    "explicit_target": 6,
    "single_target_refs": 5,
    "single_target_title": 4,
    "amendment_title_unresolved": 3,
    "multi_target_title": 2,
    "non_amendment_doc": 1,
}


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return bool(
        con.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name],
        ).fetchone()[0]
    )


def _column_exists(con: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = ? AND column_name = ?
            """,
            [table_name, column_name],
        ).fetchone()[0]
    )


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return (numerator * 100.0) / denominator


@dataclass(frozen=True)
class AmendmentQualityMetrics:
    """Roll-up metrics describing amendment extraction quality and coverage."""

    available: bool = False
    amendments_total: int = 0
    amendments_with_target_total: int = 0
    amendment_target_expected_total: int = 0
    amendment_target_row_resolution_pct: float = 0.0
    amendment_docs_extracted: int = 0
    amendment_candidate_docs: int = 0
    amendment_extraction_coverage_pct: float = 0.0
    expected_single_target_amendment_docs_total: int = 0
    resolved_single_target_amendment_docs_total: int = 0
    amendment_target_resolution_pct: float = 0.0
    single_target_amendment_doc_resolution_pct: float = 0.0
    single_target_title_docs_total: int = 0
    resolved_single_target_title_docs_total: int = 0
    single_target_title_resolution_pct: float = 0.0
    amendment_title_unresolved_docs_total: int = 0
    multi_target_title_docs_total: int = 0


def collect_amendment_quality_metrics(
    con: duckdb.DuckDBPyConnection,
) -> AmendmentQualityMetrics:
    """Collect row-level diagnostic and doc-level blocking amendment metrics."""
    if not _table_exists(con, "lex_amendments"):
        return AmendmentQualityMetrics()

    amendments_total = int(con.execute("SELECT COUNT(*) FROM lex_amendments").fetchone()[0])
    amendments_with_target_total = int(
        con.execute(
            """
            SELECT COUNT(*)
            FROM lex_amendments
            WHERE TRIM(COALESCE(amended_doc_id, '')) != ''
            """
        ).fetchone()[0]
    )
    if _column_exists(con, "lex_amendments", "target_resolution_expected"):
        amendment_target_expected_total = int(
            con.execute(
                """
                SELECT COUNT(*)
                FROM lex_amendments
                WHERE COALESCE(target_resolution_expected, TRUE)
                """
            ).fetchone()[0]
        )
    else:
        amendment_target_expected_total = amendments_total
    amendment_target_row_resolution_pct = _safe_pct(
        amendments_with_target_total,
        amendment_target_expected_total or amendments_total,
    )

    amendment_docs_extracted = int(
        con.execute("SELECT COUNT(DISTINCT amending_doc_id) FROM lex_amendments").fetchone()[0]
    )
    amendment_candidate_docs = 0
    if _table_exists(con, "lex_doc_versions"):
        amendment_candidate_docs = int(
            con.execute(
                """
                SELECT COUNT(DISTINCT doc_id)
                FROM lex_doc_versions
                WHERE lower(COALESCE(doc_name, '') || ' ' || COALESCE(doc_type, '')) LIKE '%внесення змін%'
                   OR lower(COALESCE(doc_name, '') || ' ' || COALESCE(doc_type, '')) LIKE '%зміни до%'
                   OR lower(COALESCE(doc_name, '') || ' ' || COALESCE(doc_type, '')) LIKE '%доповнен%'
                   OR lower(COALESCE(doc_name, '') || ' ' || COALESCE(doc_type, '')) LIKE '%змін%'
                """
            ).fetchone()[0]
        )
    amendment_extraction_coverage_pct = _safe_pct(amendment_docs_extracted, amendment_candidate_docs)

    metadata_expr = (
        "COALESCE(json_extract_string(metadata, '$.doc_scope_kind'), '')"
        if _column_exists(con, "lex_amendments", "metadata")
        else "''"
    )
    rows = con.execute(
        f"""
        SELECT
            amending_doc_id,
            TRIM(COALESCE(amended_doc_id, '')) AS amended_doc_id,
            COALESCE(target_resolution_expected, TRUE) AS target_resolution_expected,
            {metadata_expr} AS doc_scope_kind
        FROM lex_amendments
        """
    ).fetchall()

    doc_rollups: dict[str, dict[str, object]] = {}
    for amending_doc_id, amended_doc_id, target_resolution_expected, doc_scope_kind in rows:
        doc_id = str(amending_doc_id or "").strip()
        if not doc_id:
            continue
        scope_kind = str(doc_scope_kind or "").strip()
        rollup = doc_rollups.setdefault(
            doc_id,
            {
                "has_target": False,
                "target_resolution_expected": False,
                "doc_scope_kind": "",
            },
        )
        if str(amended_doc_id or "").strip():
            rollup["has_target"] = True
        if bool(target_resolution_expected):
            rollup["target_resolution_expected"] = True
        current_scope_kind = str(rollup["doc_scope_kind"] or "")
        if _SCOPE_PRIORITY.get(scope_kind, 0) >= _SCOPE_PRIORITY.get(current_scope_kind, 0):
            rollup["doc_scope_kind"] = scope_kind

    expected_single_target_amendment_docs_total = 0
    resolved_single_target_amendment_docs_total = 0
    single_target_title_docs_total = 0
    resolved_single_target_title_docs_total = 0
    amendment_title_unresolved_docs_total = 0
    multi_target_title_docs_total = 0
    for rollup in doc_rollups.values():
        scope_kind = str(rollup["doc_scope_kind"] or "")
        has_target = bool(rollup["has_target"])
        target_resolution_expected = bool(rollup["target_resolution_expected"])
        single_target_expected = scope_kind in _SINGLE_TARGET_SCOPE_KINDS or (
            not scope_kind and target_resolution_expected
        )
        if single_target_expected:
            expected_single_target_amendment_docs_total += 1
            if has_target:
                resolved_single_target_amendment_docs_total += 1
        if scope_kind in _TITLE_SCOPE_KINDS:
            single_target_title_docs_total += 1
            if has_target:
                resolved_single_target_title_docs_total += 1
        if scope_kind == "amendment_title_unresolved":
            amendment_title_unresolved_docs_total += 1
        if scope_kind == "multi_target_title":
            multi_target_title_docs_total += 1

    amendment_target_resolution_pct = _safe_pct(
        resolved_single_target_amendment_docs_total,
        expected_single_target_amendment_docs_total,
    )
    single_target_title_resolution_pct = _safe_pct(
        resolved_single_target_title_docs_total,
        single_target_title_docs_total,
    )

    return AmendmentQualityMetrics(
        available=True,
        amendments_total=amendments_total,
        amendments_with_target_total=amendments_with_target_total,
        amendment_target_expected_total=amendment_target_expected_total or amendments_total,
        amendment_target_row_resolution_pct=amendment_target_row_resolution_pct,
        amendment_docs_extracted=amendment_docs_extracted,
        amendment_candidate_docs=amendment_candidate_docs,
        amendment_extraction_coverage_pct=amendment_extraction_coverage_pct,
        expected_single_target_amendment_docs_total=expected_single_target_amendment_docs_total,
        resolved_single_target_amendment_docs_total=resolved_single_target_amendment_docs_total,
        amendment_target_resolution_pct=amendment_target_resolution_pct,
        single_target_amendment_doc_resolution_pct=amendment_target_resolution_pct,
        single_target_title_docs_total=single_target_title_docs_total,
        resolved_single_target_title_docs_total=resolved_single_target_title_docs_total,
        single_target_title_resolution_pct=single_target_title_resolution_pct,
        amendment_title_unresolved_docs_total=amendment_title_unresolved_docs_total,
        multi_target_title_docs_total=multi_target_title_docs_total,
    )


__all__ = [
    "AmendmentQualityMetrics",
    "collect_amendment_quality_metrics",
]
