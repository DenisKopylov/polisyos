"""Quality report and quality gates for Lex batch pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QualityGateThresholds:
    max_full_only_docs_pct: float = 30.0
    max_empty_statement_rows_pct: float = 12.0
    max_oov_action_rate_pct: float = 1.0
    max_missing_quote_rate_pct: float = 5.0
    max_duplicate_anchor_rate_pct: float = 0.1
    min_provision_docs_for_doc_rate: int = 25
    min_spo_rows_for_row_rate: int = 50
    min_statements_for_statement_rate: int = 100


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    failed_checks: list[str]
    skipped_checks: list[str]
    report: dict[str, Any]


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return (numerator * 100.0) / denominator


def build_quality_report(
    *,
    provisions_dir: Path,
    spo_results_dir: Path,
) -> dict[str, Any]:
    """Compute quality report from provision and SPO JSONL outputs."""
    provision_files = list(provisions_dir.glob("**/*.jsonl"))
    spo_files = list(spo_results_dir.glob("**/*.jsonl"))

    docs_total = 0
    full_only_docs = 0
    duplicate_anchor_docs = 0

    for prov_file in provision_files:
        docs_total += 1
        has_non_full = False
        seen_anchor: set[str] = set()
        has_dup_anchor = False

        with open(prov_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                kind = str(row.get("kind") or "")
                if kind not in {"full_text", "full_chunk"}:
                    has_non_full = True
                anchor = str(row.get("anchor_path") or "")
                if anchor:
                    if anchor in seen_anchor:
                        has_dup_anchor = True
                    seen_anchor.add(anchor)

        if not has_non_full:
            full_only_docs += 1
        if has_dup_anchor:
            duplicate_anchor_docs += 1

    rows_total = 0
    empty_statement_rows = 0
    statement_total = 0
    missing_quote_statements = 0
    oov_action_total = 0

    for spo_file in spo_files:
        with open(spo_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rows_total += 1
                row = json.loads(line)
                statements = row.get("statements", [])
                if not isinstance(statements, list):
                    statements = []
                if not statements:
                    empty_statement_rows += 1

                norm_report_raw = row.get("normalization_report_json")
                if isinstance(norm_report_raw, str) and norm_report_raw.strip():
                    try:
                        norm_report = json.loads(norm_report_raw)
                    except json.JSONDecodeError:
                        norm_report = {}
                    oov_action_total += int(norm_report.get("oov_action") or 0)

                for stmt in statements:
                    if not isinstance(stmt, dict):
                        continue
                    statement_total += 1
                    quote = str(stmt.get("source_quote_uk") or "")
                    q_start = stmt.get("source_quote_start")
                    q_end = stmt.get("source_quote_end")
                    if (not quote.strip()) or (q_start is None) or (q_end is None):
                        missing_quote_statements += 1

    report = {
        "provision_docs_total": docs_total,
        "full_only_docs": full_only_docs,
        "full_only_docs_pct": _safe_pct(full_only_docs, docs_total),
        "duplicate_anchor_docs": duplicate_anchor_docs,
        "duplicate_anchor_rate_pct": _safe_pct(duplicate_anchor_docs, docs_total),
        "spo_rows_total": rows_total,
        "empty_statement_rows": empty_statement_rows,
        "empty_statement_rows_pct": _safe_pct(empty_statement_rows, rows_total),
        "statement_total": statement_total,
        "missing_quote_statements": missing_quote_statements,
        "missing_quote_rate_pct": _safe_pct(missing_quote_statements, statement_total),
        "oov_action_total": oov_action_total,
        "oov_action_rate_pct": _safe_pct(oov_action_total, statement_total),
    }
    return report


def evaluate_quality_gates(
    *,
    report: dict[str, Any],
    thresholds: QualityGateThresholds,
) -> QualityGateResult:
    """Evaluate report against critical thresholds."""
    failed: list[str] = []
    skipped: list[str] = []

    provision_docs_total = int(report.get("provision_docs_total", 0) or 0)
    if provision_docs_total >= thresholds.min_provision_docs_for_doc_rate:
        if float(report.get("full_only_docs_pct", 0.0)) > thresholds.max_full_only_docs_pct:
            failed.append("full_only_docs_pct")
        if float(report.get("duplicate_anchor_rate_pct", 0.0)) > thresholds.max_duplicate_anchor_rate_pct:
            failed.append("duplicate_anchor_rate_pct")
    else:
        skipped.extend(["full_only_docs_pct", "duplicate_anchor_rate_pct"])

    spo_rows_total = int(report.get("spo_rows_total", 0) or 0)
    if spo_rows_total >= thresholds.min_spo_rows_for_row_rate:
        if float(report.get("empty_statement_rows_pct", 0.0)) > thresholds.max_empty_statement_rows_pct:
            failed.append("empty_statement_rows_pct")
    else:
        skipped.append("empty_statement_rows_pct")

    statement_total = int(report.get("statement_total", 0) or 0)
    if statement_total >= thresholds.min_statements_for_statement_rate:
        if float(report.get("oov_action_rate_pct", 0.0)) > thresholds.max_oov_action_rate_pct:
            failed.append("oov_action_rate_pct")
        if float(report.get("missing_quote_rate_pct", 0.0)) > thresholds.max_missing_quote_rate_pct:
            failed.append("missing_quote_rate_pct")
    else:
        skipped.extend(["oov_action_rate_pct", "missing_quote_rate_pct"])

    return QualityGateResult(
        passed=not failed,
        failed_checks=failed,
        skipped_checks=skipped,
        report=report,
    )
