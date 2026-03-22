"""Quality report and quality gates for Lex batch pipeline."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.lex.batch.doc_family import classify_doc_family
from polisyos.lex.batch.canonicalizers import canonicalize_action

_SEARCH_ONLY_REFERENCE_GATE_EXEMPT_SUBTYPES = {
    "citation_only",
    "composition_list",
    "form_scaffold",
    "inventory_only",
    "registry_catalog_row",
    "table_scaffold",
}

# Subtypes where empty statement rows are structurally expected and should not
# be counted against the empty_statement_rows_pct quality gate.
_STRUCTURALLY_EMPTY_SUBTYPES = {
    "citation_only",
    "composition_list",
    "form_scaffold",
    "inventory_only",
    "registry_catalog_row",
    "table_scaffold",
    "front_matter",
    "header_only",
    "signature_block",
}


@dataclass(frozen=True)
class QualityGateThresholds:
    max_full_only_docs_pct: float = 30.0
    max_empty_statement_rows_pct: float = 12.0
    max_oov_action_rate_pct: float = 1.0
    max_missing_quote_rate_pct: float = 5.0
    max_duplicate_anchor_rate_pct: float = 0.1
    max_audit_miss_rate_pct: float = 3.0
    min_reference_resolution_coverage_pct: float = 80.0
    min_llm_saved_pct: float = 50.0
    min_audit_samples_for_rate: int = 10
    min_provision_docs_for_doc_rate: int = 25
    min_spo_rows_for_row_rate: int = 50
    min_statements_for_statement_rate: int = 100
    min_reference_rows_for_rate: int = 10


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    failed_checks: list[str]
    warning_failed_checks: list[str]
    skipped_checks: list[str]
    report: dict[str, Any]


def _safe_pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return (numerator * 100.0) / denominator


def _empty_family_stats() -> dict[str, Any]:
    return {
        "provision_docs_total": 0,
        "provision_rows_total": 0,
        "full_only_docs": 0,
        "duplicate_anchor_docs": 0,
        "spo_rows_total": 0,
        "empty_statement_rows": 0,
        "statement_total": 0,
        "missing_quote_statements": 0,
        "grounded_statement_total": 0,
        "grounded_missing_quote_statements": 0,
        "normative_statement_total": 0,
        "oov_action_total": 0,
        "timeout_fallback_rows": 0,
        "error_fallback_rows": 0,
        "audit_sample_total": 0,
        "audit_miss_total": 0,
        "primary_clause_miss_total": 0,
        "secondary_clause_miss_total": 0,
        "audit_miss_category_counts": {},
        "route_class_counts": {},
        "reference_rows_total": 0,
        "reference_resolved_rows": 0,
        "reference_partial_rows": 0,
    }


def _finalize_family_breakdown(family_stats: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    breakdown: dict[str, dict[str, Any]] = {}
    for family, raw in sorted(family_stats.items()):
        payload = dict(raw)
        payload["full_only_docs_pct"] = _safe_pct(
            int(payload.get("full_only_docs", 0) or 0),
            int(payload.get("provision_docs_total", 0) or 0),
        )
        payload["duplicate_anchor_rate_pct"] = _safe_pct(
            int(payload.get("duplicate_anchor_docs", 0) or 0),
            int(payload.get("provision_docs_total", 0) or 0),
        )
        payload["empty_statement_rows_pct"] = _safe_pct(
            int(payload.get("empty_statement_rows", 0) or 0),
            int(payload.get("spo_rows_total", 0) or 0),
        )
        payload["missing_quote_rate_pct"] = _safe_pct(
            int(payload.get("missing_quote_statements", 0) or 0),
            int(payload.get("statement_total", 0) or 0),
        )
        payload["grounded_missing_quote_rate_pct"] = _safe_pct(
            int(payload.get("grounded_missing_quote_statements", 0) or 0),
            int(payload.get("grounded_statement_total", 0) or 0),
        )
        payload["oov_action_rate_pct"] = _safe_pct(
            int(payload.get("oov_action_total", 0) or 0),
            int(payload.get("statement_total", 0) or 0),
        )
        payload["timeout_fallback_rate_pct"] = _safe_pct(
            int(payload.get("timeout_fallback_rows", 0) or 0),
            int(payload.get("spo_rows_total", 0) or 0),
        )
        payload["audit_miss_rate_pct"] = _safe_pct(
            int(payload.get("audit_miss_total", 0) or 0),
            int(payload.get("audit_sample_total", 0) or 0),
        )
        payload["primary_clause_miss_rate_pct"] = _safe_pct(
            int(payload.get("primary_clause_miss_total", 0) or 0),
            int(payload.get("audit_sample_total", 0) or 0),
        )
        payload["secondary_clause_miss_rate_pct"] = _safe_pct(
            int(payload.get("secondary_clause_miss_total", 0) or 0),
            int(payload.get("audit_sample_total", 0) or 0),
        )
        payload["reference_resolution_coverage_pct"] = _safe_pct(
            int(payload.get("reference_resolved_rows", 0) or 0),
            int(payload.get("reference_rows_total", 0) or 0),
        )
        payload["audit_miss_category_counts"] = dict(
            sorted((payload.get("audit_miss_category_counts") or {}).items())
        )
        payload["route_class_counts"] = dict(
            sorted((payload.get("route_class_counts") or {}).items())
        )
        breakdown[family] = payload
    return breakdown


def _is_search_only_only(payload: dict[str, Any]) -> bool:
    route_counts = payload.get("route_class_counts") or {}
    active_routes = {
        str(route)
        for route, count in route_counts.items()
        if int(count or 0) > 0
    }
    return bool(active_routes) and active_routes <= {"search_only"}


def build_quality_report(
    *,
    provisions_dir: Path,
    spo_results_dir: Path,
    llm_gate_manifest_path: Path | None = None,
    llm_gate_audit_path: Path | None = None,
    resolved_references_dir: Path | None = None,
) -> dict[str, Any]:
    """Compute quality report from provision and SPO JSONL outputs."""
    provision_files = list(provisions_dir.glob("**/*.jsonl"))
    spo_files = list(spo_results_dir.glob("**/*.jsonl"))
    doc_metadata_path = provisions_dir.parent / "manifests" / "doc_metadata.json"
    doc_metadata: dict[str, dict[str, Any]] = {}
    if doc_metadata_path.exists():
        try:
            with open(doc_metadata_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                source = payload.get("documents") if isinstance(payload.get("documents"), dict) else payload
                doc_metadata = {
                    str(doc_id): dict(meta)
                    for doc_id, meta in source.items()
                    if isinstance(meta, dict)
                }
        except Exception:
            doc_metadata = {}

    docs_total = 0
    full_only_docs = 0
    duplicate_anchor_docs = 0
    doc_family_by_doc: dict[str, str] = {}
    family_stats: dict[str, dict[str, Any]] = defaultdict(_empty_family_stats)
    subtype_stats: dict[str, dict[str, Any]] = defaultdict(_empty_family_stats)
    family_subtype_stats: dict[str, dict[str, Any]] = defaultdict(_empty_family_stats)
    subtype_by_anchor: dict[tuple[str, str], str] = {}
    route_by_anchor: dict[tuple[str, str], str] = {}
    if resolved_references_dir is None:
        resolved_references_dir = provisions_dir.parent / "resolved_references"

    for prov_file in provision_files:
        doc_id = prov_file.stem
        docs_total += 1
        has_non_full = False
        seen_anchor: set[str] = set()
        has_dup_anchor = False
        provision_rows: list[dict[str, Any]] = []
        doc_type_category = ""
        seen_doc_subtypes: set[str] = set()

        with open(prov_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if not doc_type_category:
                    doc_type_category = str(row.get("doc_type_category") or "")
                provision_rows.append(row)
                kind = str(row.get("kind") or "")
                if kind not in {"full_text", "full_chunk"}:
                    has_non_full = True
                anchor = str(row.get("anchor_path") or "")
                subtype = str(row.get("legal_unit_subtype") or "")
                route_class = str(row.get("route_class") or "")
                if anchor:
                    if anchor in seen_anchor:
                        has_dup_anchor = True
                    seen_anchor.add(anchor)
                    if subtype:
                        subtype_by_anchor[(doc_id, anchor)] = subtype
                    if route_class:
                        route_by_anchor[(doc_id, anchor)] = route_class

        if not has_non_full:
            full_only_docs += 1
        if has_dup_anchor:
            duplicate_anchor_docs += 1
        if not doc_type_category:
            meta = doc_metadata.get(doc_id, {})
            doc_type_category = str(meta.get("doc_type_category") or meta.get("doc_type") or meta.get("name") or "")
        family = classify_doc_family(
            doc_type_category_value=doc_type_category,
            provision_rows=provision_rows,
        )
        doc_family_by_doc[doc_id] = family
        family_row = family_stats[family]
        family_row["provision_docs_total"] += 1
        family_row["provision_rows_total"] += len(provision_rows)
        if not has_non_full:
            family_row["full_only_docs"] += 1
        if has_dup_anchor:
            family_row["duplicate_anchor_docs"] += 1
        for row in provision_rows:
            subtype = str(row.get("legal_unit_subtype") or "")
            if not subtype:
                continue
            subtype_row = subtype_stats[subtype]
            family_subtype_key = f"{family}::{subtype}"
            family_subtype_row = family_subtype_stats[family_subtype_key]
            subtype_row["provision_rows_total"] += 1
            family_subtype_row["provision_rows_total"] += 1
            route_class = str(row.get("route_class") or "")
            if route_class:
                counts = subtype_row.setdefault("route_class_counts", {})
                counts[route_class] = int(counts.get(route_class, 0) or 0) + 1
                family_counts = family_subtype_row.setdefault("route_class_counts", {})
                family_counts[route_class] = int(family_counts.get(route_class, 0) or 0) + 1
            if subtype not in seen_doc_subtypes:
                subtype_row["provision_docs_total"] += 1
                family_subtype_row["provision_docs_total"] += 1
                seen_doc_subtypes.add(subtype)
            if str(row.get("kind") or "") in {"full_text", "full_chunk"}:
                subtype_row["full_only_docs"] += 1
                family_subtype_row["full_only_docs"] += 1

    rows_total = 0
    empty_statement_rows = 0
    statement_total = 0
    missing_quote_statements = 0
    grounded_statement_total = 0
    grounded_missing_quote_statements = 0
    normative_statement_total = 0
    oov_action_total = 0

    for spo_file in spo_files:
        family = doc_family_by_doc.get(spo_file.stem, "other")
        family_row = family_stats[family]
        with open(spo_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rows_total += 1
                family_row["spo_rows_total"] += 1
                row = json.loads(line)
                subtype = str(row.get("legal_unit_subtype") or subtype_by_anchor.get((spo_file.stem, str(row.get("provision_anchor") or "")), "") or "")
                route_class = str(row.get("route_class") or route_by_anchor.get((spo_file.stem, str(row.get("provision_anchor") or "")), "") or "")
                subtype_row = subtype_stats[subtype] if subtype else None
                family_subtype_row = family_subtype_stats[f"{family}::{subtype}"] if subtype else None
                if subtype_row is not None:
                    subtype_row["spo_rows_total"] += 1
                    if route_class:
                        counts = subtype_row.setdefault("route_class_counts", {})
                        counts[route_class] = int(counts.get(route_class, 0) or 0) + 1
                if family_subtype_row is not None:
                    family_subtype_row["spo_rows_total"] += 1
                    if route_class:
                        counts = family_subtype_row.setdefault("route_class_counts", {})
                        counts[route_class] = int(counts.get(route_class, 0) or 0) + 1
                extraction_source = str(row.get("extraction_source") or "")
                if extraction_source.endswith("timeout_fallback"):
                    family_row["timeout_fallback_rows"] += 1
                    if subtype_row is not None:
                        subtype_row["timeout_fallback_rows"] += 1
                    if family_subtype_row is not None:
                        family_subtype_row["timeout_fallback_rows"] += 1
                elif extraction_source.endswith("error_fallback"):
                    family_row["error_fallback_rows"] += 1
                    if subtype_row is not None:
                        subtype_row["error_fallback_rows"] += 1
                    if family_subtype_row is not None:
                        family_subtype_row["error_fallback_rows"] += 1
                statements = row.get("statements", [])
                if not isinstance(statements, list):
                    statements = []
                if not statements:
                    # Track all empty rows for per-subtype reporting
                    if subtype_row is not None:
                        subtype_row["empty_statement_rows"] += 1
                    if family_subtype_row is not None:
                        family_subtype_row["empty_statement_rows"] += 1
                    # Only count against aggregate gate if not a structurally empty subtype
                    if subtype not in _STRUCTURALLY_EMPTY_SUBTYPES:
                        empty_statement_rows += 1
                        family_row["empty_statement_rows"] += 1

                for stmt in statements:
                    if not isinstance(stmt, dict):
                        continue
                    statement_total += 1
                    family_row["statement_total"] += 1
                    if subtype_row is not None:
                        subtype_row["statement_total"] += 1
                    if family_subtype_row is not None:
                        family_subtype_row["statement_total"] += 1
                    action_candidates = (
                        stmt.get("action_canon"),
                        stmt.get("predicate"),
                        stmt.get("action_raw"),
                    )
                    for candidate in action_candidates:
                        if not candidate:
                            continue
                        _, action_oov = canonicalize_action(str(candidate))
                        if action_oov:
                            oov_action_total += 1
                            family_row["oov_action_total"] += 1
                            if subtype_row is not None:
                                subtype_row["oov_action_total"] += 1
                            if family_subtype_row is not None:
                                family_subtype_row["oov_action_total"] += 1
                        break
                    trust_tier = str(stmt.get("trust_tier") or "")
                    quote = str(stmt.get("source_quote_uk") or "")
                    q_start = stmt.get("source_quote_start")
                    q_end = stmt.get("source_quote_end")
                    # A quote is only truly missing if there is no quote text at all.
                    # quote_without_offsets (has text, no offsets) is partial, not missing.
                    has_missing_quote = not quote.strip()
                    if has_missing_quote:
                        missing_quote_statements += 1
                        family_row["missing_quote_statements"] += 1
                        if subtype_row is not None:
                            subtype_row["missing_quote_statements"] += 1
                        if family_subtype_row is not None:
                            family_subtype_row["missing_quote_statements"] += 1
                    if trust_tier in {"grounded_fact", "normative_fact"}:
                        grounded_statement_total += 1
                        family_row["grounded_statement_total"] += 1
                        if subtype_row is not None:
                            subtype_row["grounded_statement_total"] += 1
                        if family_subtype_row is not None:
                            family_subtype_row["grounded_statement_total"] += 1
                        if has_missing_quote:
                            grounded_missing_quote_statements += 1
                            family_row["grounded_missing_quote_statements"] += 1
                            if subtype_row is not None:
                                subtype_row["grounded_missing_quote_statements"] += 1
                            if family_subtype_row is not None:
                                family_subtype_row["grounded_missing_quote_statements"] += 1
                    if trust_tier == "normative_fact":
                        normative_statement_total += 1
                        family_row["normative_statement_total"] += 1
                        if subtype_row is not None:
                            subtype_row["normative_statement_total"] += 1
                        if family_subtype_row is not None:
                            family_subtype_row["normative_statement_total"] += 1

    reference_rows_total = 0
    reference_resolved_rows = 0
    if resolved_references_dir is not None and resolved_references_dir.exists():
        for ref_file in sorted(resolved_references_dir.glob("**/*.jsonl")):
            doc_id = ref_file.stem
            family = doc_family_by_doc.get(doc_id, "other")
            family_row = family_stats[family]
            with open(ref_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    reference_rows_total += 1
                    family_row["reference_rows_total"] += 1
                    status = str(row.get("resolution_status") or "unresolved")
                    anchor = str(row.get("anchor_path") or "")
                    subtype = subtype_by_anchor.get((doc_id, anchor), "")
                    subtype_row = subtype_stats[subtype] if subtype else None
                    family_subtype_row = family_subtype_stats[f"{family}::{subtype}"] if subtype else None
                    if subtype_row is not None:
                        subtype_row["reference_rows_total"] += 1
                    if family_subtype_row is not None:
                        family_subtype_row["reference_rows_total"] += 1
                    if status in {"resolved", "partial"}:
                        reference_resolved_rows += 1
                        family_row["reference_resolved_rows"] += 1
                        if subtype_row is not None:
                            subtype_row["reference_resolved_rows"] += 1
                        if family_subtype_row is not None:
                            family_subtype_row["reference_resolved_rows"] += 1
                    if status == "partial":
                        family_row["reference_partial_rows"] += 1
                        if subtype_row is not None:
                            subtype_row["reference_partial_rows"] += 1
                        if family_subtype_row is not None:
                            family_subtype_row["reference_partial_rows"] += 1

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
        "grounded_statement_total": grounded_statement_total,
        "grounded_missing_quote_statements": grounded_missing_quote_statements,
        "grounded_missing_quote_rate_pct": _safe_pct(
            grounded_missing_quote_statements,
            grounded_statement_total,
        ),
        "normative_statement_total": normative_statement_total,
        "oov_action_total": oov_action_total,
        "oov_action_rate_pct": _safe_pct(oov_action_total, statement_total),
        "reference_rows_total": reference_rows_total,
        "reference_resolved_rows": reference_resolved_rows,
        "reference_resolution_coverage_pct": _safe_pct(reference_resolved_rows, reference_rows_total),
    }

    llm_gate_metrics = {}
    if llm_gate_manifest_path is not None and llm_gate_manifest_path.exists():
        with open(llm_gate_manifest_path, "r", encoding="utf-8") as fh:
            gate_payload = json.load(fh)
        if isinstance(gate_payload, dict):
            maybe_metrics = gate_payload.get("metrics")
            if isinstance(maybe_metrics, dict):
                llm_gate_metrics = maybe_metrics

    audit_sample_total = int(llm_gate_metrics.get("audit_sample_total") or 0)
    audit_miss_total = int(llm_gate_metrics.get("audit_miss_total") or 0)
    primary_clause_miss_total = 0
    secondary_clause_miss_total = 0
    if llm_gate_audit_path is not None and llm_gate_audit_path.exists():
        sample_total = 0
        miss_total = 0
        with open(llm_gate_audit_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                sample_total += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                family = str(row.get("quality_family") or doc_family_by_doc.get(str(row.get("doc_id") or ""), "other"))
                family_row = family_stats[family]
                subtype = str(row.get("legal_unit_subtype") or subtype_by_anchor.get((str(row.get("doc_id") or ""), str(row.get("provision_anchor") or "")), "") or "")
                route_class = str(row.get("route_class") or route_by_anchor.get((str(row.get("doc_id") or ""), str(row.get("provision_anchor") or "")), "") or "")
                subtype_row = subtype_stats[subtype] if subtype else None
                family_subtype_row = family_subtype_stats[f"{family}::{subtype}"] if subtype else None
                family_row["audit_sample_total"] += 1
                if route_class:
                    counts = family_row.setdefault("route_class_counts", {})
                    counts[route_class] = int(counts.get(route_class, 0) or 0) + 1
                if subtype_row is not None:
                    subtype_row["audit_sample_total"] += 1
                    if route_class:
                        counts = subtype_row.setdefault("route_class_counts", {})
                        counts[route_class] = int(counts.get(route_class, 0) or 0) + 1
                if family_subtype_row is not None:
                    family_subtype_row["audit_sample_total"] += 1
                    if route_class:
                        counts = family_subtype_row.setdefault("route_class_counts", {})
                        counts[route_class] = int(counts.get(route_class, 0) or 0) + 1
                if bool(row.get("miss")):
                    miss_total += 1
                    family_row["audit_miss_total"] += 1
                    if subtype_row is not None:
                        subtype_row["audit_miss_total"] += 1
                    if family_subtype_row is not None:
                        family_subtype_row["audit_miss_total"] += 1
                    counts = family_row.setdefault("audit_miss_category_counts", {})
                    for item in row.get("miss_categories", []):
                        key = str(item).strip()
                        if not key:
                            continue
                        counts[key] = int(counts.get(key, 0) or 0) + 1
                        if subtype_row is not None:
                            sub_counts = subtype_row.setdefault("audit_miss_category_counts", {})
                            sub_counts[key] = int(sub_counts.get(key, 0) or 0) + 1
                        if family_subtype_row is not None:
                            sub_counts = family_subtype_row.setdefault("audit_miss_category_counts", {})
                            sub_counts[key] = int(sub_counts.get(key, 0) or 0) + 1
                if bool(row.get("primary_clause_miss")):
                    primary_clause_miss_total += 1
                    family_row["primary_clause_miss_total"] += 1
                    if subtype_row is not None:
                        subtype_row["primary_clause_miss_total"] += 1
                    if family_subtype_row is not None:
                        family_subtype_row["primary_clause_miss_total"] += 1
                if bool(row.get("secondary_clause_miss")):
                    secondary_clause_miss_total += 1
                    family_row["secondary_clause_miss_total"] += 1
                    if subtype_row is not None:
                        subtype_row["secondary_clause_miss_total"] += 1
                    if family_subtype_row is not None:
                        family_subtype_row["secondary_clause_miss_total"] += 1
        if sample_total > 0:
            audit_sample_total = sample_total
            audit_miss_total = miss_total

    report["llm_candidate_total"] = int(llm_gate_metrics.get("llm_candidate_total") or 0)
    report["llm_sent_total"] = int(llm_gate_metrics.get("llm_sent_total") or 0)
    report["llm_primary_sent_total"] = int(llm_gate_metrics.get("llm_primary_sent_total") or 0)
    report["llm_saved_pct"] = float(llm_gate_metrics.get("llm_saved_pct") or 0.0)
    report["llm_gap_fill_sent_total"] = int(llm_gate_metrics.get("llm_gap_fill_sent_total") or 0)
    report["llm_gap_fill_added_statements_total"] = int(llm_gate_metrics.get("llm_gap_fill_added_statements_total") or 0)
    report["baseline_vs_gap_fill_added_statements_total"] = int(
        llm_gate_metrics.get("baseline_vs_gap_fill_added_statements_total") or 0
    )
    report["llm_gap_fill_timeout_fallback_total"] = int(
        llm_gate_metrics.get("llm_gap_fill_timeout_fallback_total") or 0
    )
    report["llm_gap_fill_empty_responses_total"] = int(
        llm_gate_metrics.get("llm_gap_fill_empty_responses_total") or 0
    )
    report["llm_gap_fill_gain_rate_pct"] = float(llm_gate_metrics.get("llm_gap_fill_gain_rate_pct") or 0.0)
    report["timeout_retry_groups_total"] = int(llm_gate_metrics.get("timeout_retry_groups_total") or 0)
    report["timeout_retry_success_total"] = int(llm_gate_metrics.get("timeout_retry_success_total") or 0)
    report["timeout_retry_failure_total"] = int(llm_gate_metrics.get("timeout_retry_failure_total") or 0)
    timeout_retry_groups_total = int(report["timeout_retry_groups_total"] or 0)
    report["timeout_retry_success_rate_pct"] = _safe_pct(
        int(report["timeout_retry_success_total"] or 0),
        timeout_retry_groups_total,
    )
    deferred_reason_counts = llm_gate_metrics.get("deferred_reason_counts")
    report["deferred_reason_counts"] = (
        dict(sorted((str(key), int(value or 0)) for key, value in deferred_reason_counts.items()))
        if isinstance(deferred_reason_counts, dict)
        else {}
    )
    report["audit_sample_total"] = audit_sample_total
    report["audit_miss_total"] = audit_miss_total
    report["audit_miss_rate_pct"] = _safe_pct(audit_miss_total, audit_sample_total)
    report["audit_miss_rate_pct_before_gap_fill_baseline"] = float(
        llm_gate_metrics.get("audit_miss_rate_pct_before_gap_fill_baseline") or report["audit_miss_rate_pct"]
    )
    report["audit_miss_rate_pct_after_gap_fill"] = float(
        llm_gate_metrics.get("audit_miss_rate_pct_after_gap_fill") or report["audit_miss_rate_pct"]
    )
    report["primary_clause_miss_total"] = primary_clause_miss_total
    report["secondary_clause_miss_total"] = secondary_clause_miss_total
    report["primary_clause_miss_rate_pct"] = _safe_pct(primary_clause_miss_total, audit_sample_total)
    report["secondary_clause_miss_rate_pct"] = _safe_pct(secondary_clause_miss_total, audit_sample_total)
    report["doc_family_breakdown"] = _finalize_family_breakdown(family_stats)
    report["legal_unit_subtype_breakdown"] = _finalize_family_breakdown(subtype_stats)
    report["family_subtype_breakdown"] = _finalize_family_breakdown(family_subtype_stats)
    aggregate_miss_categories: dict[str, int] = {}
    for payload in report["doc_family_breakdown"].values():
        if not isinstance(payload, dict):
            continue
        for key, value in (payload.get("audit_miss_category_counts") or {}).items():
            aggregate_miss_categories[str(key)] = aggregate_miss_categories.get(str(key), 0) + int(value or 0)
    report["audit_miss_category_counts"] = dict(sorted(aggregate_miss_categories.items()))
    report["top_problem_families"] = [
        {
            "family": family,
            "empty_statement_rows_pct": round(float(payload.get("empty_statement_rows_pct", 0.0) or 0.0), 3),
            "audit_miss_rate_pct": round(float(payload.get("audit_miss_rate_pct", 0.0) or 0.0), 3),
            "primary_clause_miss_rate_pct": round(float(payload.get("primary_clause_miss_rate_pct", 0.0) or 0.0), 3),
            "secondary_clause_miss_rate_pct": round(float(payload.get("secondary_clause_miss_rate_pct", 0.0) or 0.0), 3),
            "timeout_fallback_rate_pct": round(float(payload.get("timeout_fallback_rate_pct", 0.0) or 0.0), 3),
            "spo_rows_total": int(payload.get("spo_rows_total", 0) or 0),
            "audit_sample_total": int(payload.get("audit_sample_total", 0) or 0),
        }
        for family, payload in sorted(
            report["doc_family_breakdown"].items(),
            key=lambda item: (
                float(item[1].get("empty_statement_rows_pct", 0.0) or 0.0),
                float(item[1].get("audit_miss_rate_pct", 0.0) or 0.0),
                float(item[1].get("timeout_fallback_rate_pct", 0.0) or 0.0),
            ),
            reverse=True,
        )
        if family != "other"
    ][:5]
    report["top_problem_subtypes"] = [
        {
            "legal_unit_subtype": subtype,
            "empty_statement_rows_pct": round(float(payload.get("empty_statement_rows_pct", 0.0) or 0.0), 3),
            "audit_miss_rate_pct": round(float(payload.get("audit_miss_rate_pct", 0.0) or 0.0), 3),
            "primary_clause_miss_rate_pct": round(float(payload.get("primary_clause_miss_rate_pct", 0.0) or 0.0), 3),
            "secondary_clause_miss_rate_pct": round(float(payload.get("secondary_clause_miss_rate_pct", 0.0) or 0.0), 3),
            "timeout_fallback_rate_pct": round(float(payload.get("timeout_fallback_rate_pct", 0.0) or 0.0), 3),
            "spo_rows_total": int(payload.get("spo_rows_total", 0) or 0),
            "audit_sample_total": int(payload.get("audit_sample_total", 0) or 0),
            "route_class_counts": dict(payload.get("route_class_counts") or {}),
        }
        for subtype, payload in sorted(
            report["legal_unit_subtype_breakdown"].items(),
            key=lambda item: (
                float(item[1].get("empty_statement_rows_pct", 0.0) or 0.0),
                float(item[1].get("audit_miss_rate_pct", 0.0) or 0.0),
                float(item[1].get("timeout_fallback_rate_pct", 0.0) or 0.0),
            ),
            reverse=True,
        )
        if subtype
    ][:8]
    report["top_unresolved_subtype_families"] = [
        {
            "family": item["family"],
            "legal_unit_subtype": item["legal_unit_subtype"],
            "reference_resolution_coverage_pct": round(float(payload.get("reference_resolution_coverage_pct", 0.0) or 0.0), 3),
            "empty_statement_rows_pct": round(float(payload.get("empty_statement_rows_pct", 0.0) or 0.0), 3),
            "audit_miss_rate_pct": round(float(payload.get("audit_miss_rate_pct", 0.0) or 0.0), 3),
            "reference_rows_total": int(payload.get("reference_rows_total", 0) or 0),
            "spo_rows_total": int(payload.get("spo_rows_total", 0) or 0),
        }
        for key, payload in sorted(
            report["family_subtype_breakdown"].items(),
            key=lambda item: (
                float(item[1].get("reference_resolution_coverage_pct", 0.0) or 0.0),
                -float(item[1].get("empty_statement_rows_pct", 0.0) or 0.0),
                -float(item[1].get("audit_miss_rate_pct", 0.0) or 0.0),
            ),
        )
        if "::" in key
        for item in [{
            "family": key.split("::", 1)[0],
            "legal_unit_subtype": key.split("::", 1)[1],
        }]
        if item["legal_unit_subtype"]
        and int(payload.get("reference_rows_total", 0) or 0) > 0
        and item["legal_unit_subtype"] not in _SEARCH_ONLY_REFERENCE_GATE_EXEMPT_SUBTYPES
        and not _is_search_only_only(payload)
    ][:10]
    report["top_gap_fill_subtypes"] = list(llm_gate_metrics.get("top_gap_fill_subtypes") or [])
    report["top_gap_fill_families"] = list(llm_gate_metrics.get("top_gap_fill_families") or [])
    report["top_timeout_gap_fill_families"] = list(llm_gate_metrics.get("top_timeout_gap_fill_families") or [])
    return report


def evaluate_quality_gates(
    *,
    report: dict[str, Any],
    thresholds: QualityGateThresholds,
) -> QualityGateResult:
    """Evaluate report against critical thresholds."""
    failed: list[str] = []
    warning_failed: list[str] = []
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
        missing_quote_metric = (
            float(report.get("grounded_missing_quote_rate_pct", 0.0))
            if int(report.get("grounded_statement_total", 0) or 0) > 0
            else float(report.get("missing_quote_rate_pct", 0.0))
        )
        if missing_quote_metric > thresholds.max_missing_quote_rate_pct:
            failed.append("missing_quote_rate_pct")
    else:
        skipped.extend(["oov_action_rate_pct", "missing_quote_rate_pct"])

    audit_sample_total = int(report.get("audit_sample_total", 0) or 0)
    if audit_sample_total >= thresholds.min_audit_samples_for_rate:
        if float(report.get("audit_miss_rate_pct", 0.0)) > thresholds.max_audit_miss_rate_pct:
            failed.append("audit_miss_rate_pct")
    else:
        skipped.append("audit_miss_rate_pct")

    reference_rows_total = int(report.get("reference_rows_total", 0) or 0)
    if reference_rows_total >= thresholds.min_reference_rows_for_rate:
        if float(report.get("reference_resolution_coverage_pct", 0.0) or 0.0) < thresholds.min_reference_resolution_coverage_pct:
            failed.append("reference_resolution_coverage_pct")
    else:
        skipped.append("reference_resolution_coverage_pct")

    llm_candidate_total = int(report.get("llm_candidate_total", 0) or 0)
    if llm_candidate_total > 0:
        if float(report.get("llm_saved_pct", 0.0)) < thresholds.min_llm_saved_pct:
            warning_failed.append("llm_saved_pct")
    else:
        skipped.append("llm_saved_pct")

    family_breakdown = report.get("doc_family_breakdown", {})
    if isinstance(family_breakdown, dict):
        family_doc_min = max(3, thresholds.min_provision_docs_for_doc_rate // 4)
        family_row_min = max(10, thresholds.min_spo_rows_for_row_rate // 4)
        family_stmt_min = max(10, thresholds.min_statements_for_statement_rate // 4)
        family_audit_min = max(3, thresholds.min_audit_samples_for_rate // 2)
        for family, payload in family_breakdown.items():
            if not isinstance(payload, dict) or family == "other":
                continue
            if int(payload.get("provision_docs_total", 0) or 0) >= family_doc_min:
                if float(payload.get("full_only_docs_pct", 0.0) or 0.0) > thresholds.max_full_only_docs_pct:
                    failed.append(f"family:{family}:full_only_docs_pct")
                if float(payload.get("duplicate_anchor_rate_pct", 0.0) or 0.0) > thresholds.max_duplicate_anchor_rate_pct:
                    failed.append(f"family:{family}:duplicate_anchor_rate_pct")
            if int(payload.get("spo_rows_total", 0) or 0) >= family_row_min:
                if float(payload.get("empty_statement_rows_pct", 0.0) or 0.0) > thresholds.max_empty_statement_rows_pct:
                    failed.append(f"family:{family}:empty_statement_rows_pct")
            if int(payload.get("statement_total", 0) or 0) >= family_stmt_min:
                if float(payload.get("oov_action_rate_pct", 0.0) or 0.0) > thresholds.max_oov_action_rate_pct:
                    failed.append(f"family:{family}:oov_action_rate_pct")
                family_missing_quote_metric = (
                    float(payload.get("grounded_missing_quote_rate_pct", 0.0) or 0.0)
                    if int(payload.get("grounded_statement_total", 0) or 0) > 0
                    else float(payload.get("missing_quote_rate_pct", 0.0) or 0.0)
                )
                if family_missing_quote_metric > thresholds.max_missing_quote_rate_pct:
                    failed.append(f"family:{family}:missing_quote_rate_pct")
            if int(payload.get("audit_sample_total", 0) or 0) >= family_audit_min:
                if float(payload.get("audit_miss_rate_pct", 0.0) or 0.0) > thresholds.max_audit_miss_rate_pct:
                    failed.append(f"family:{family}:audit_miss_rate_pct")
            if int(payload.get("reference_rows_total", 0) or 0) >= max(3, thresholds.min_reference_rows_for_rate // 2):
                if float(payload.get("reference_resolution_coverage_pct", 0.0) or 0.0) < thresholds.min_reference_resolution_coverage_pct:
                    failed.append(f"family:{family}:reference_resolution_coverage_pct")

    subtype_breakdown = report.get("legal_unit_subtype_breakdown", {})
    if isinstance(subtype_breakdown, dict):
        subtype_doc_min = max(5, thresholds.min_provision_docs_for_doc_rate // 3)
        subtype_row_min = max(15, thresholds.min_spo_rows_for_row_rate // 3)
        subtype_stmt_min = max(15, thresholds.min_statements_for_statement_rate // 3)
        subtype_audit_min = max(4, thresholds.min_audit_samples_for_rate // 2)
        for subtype, payload in subtype_breakdown.items():
            if not isinstance(payload, dict) or not subtype:
                continue
            if int(payload.get("provision_docs_total", 0) or 0) >= subtype_doc_min:
                if float(payload.get("duplicate_anchor_rate_pct", 0.0) or 0.0) > thresholds.max_duplicate_anchor_rate_pct:
                    failed.append(f"subtype:{subtype}:duplicate_anchor_rate_pct")
            if int(payload.get("spo_rows_total", 0) or 0) >= subtype_row_min:
                if float(payload.get("empty_statement_rows_pct", 0.0) or 0.0) > thresholds.max_empty_statement_rows_pct:
                    failed.append(f"subtype:{subtype}:empty_statement_rows_pct")
            if int(payload.get("statement_total", 0) or 0) >= subtype_stmt_min:
                if float(payload.get("oov_action_rate_pct", 0.0) or 0.0) > thresholds.max_oov_action_rate_pct:
                    failed.append(f"subtype:{subtype}:oov_action_rate_pct")
                subtype_missing_quote_metric = (
                    float(payload.get("grounded_missing_quote_rate_pct", 0.0) or 0.0)
                    if int(payload.get("grounded_statement_total", 0) or 0) > 0
                    else float(payload.get("missing_quote_rate_pct", 0.0) or 0.0)
                )
                if subtype_missing_quote_metric > thresholds.max_missing_quote_rate_pct:
                    failed.append(f"subtype:{subtype}:missing_quote_rate_pct")
            if int(payload.get("audit_sample_total", 0) or 0) >= subtype_audit_min:
                if float(payload.get("audit_miss_rate_pct", 0.0) or 0.0) > thresholds.max_audit_miss_rate_pct:
                    failed.append(f"subtype:{subtype}:audit_miss_rate_pct")
            if int(payload.get("reference_rows_total", 0) or 0) >= max(3, thresholds.min_reference_rows_for_rate // 2):
                if (
                    subtype not in _SEARCH_ONLY_REFERENCE_GATE_EXEMPT_SUBTYPES
                    and not _is_search_only_only(payload)
                    and float(payload.get("reference_resolution_coverage_pct", 0.0) or 0.0) < thresholds.min_reference_resolution_coverage_pct
                ):
                    failed.append(f"subtype:{subtype}:reference_resolution_coverage_pct")
                elif subtype in _SEARCH_ONLY_REFERENCE_GATE_EXEMPT_SUBTYPES or _is_search_only_only(payload):
                    skipped.append(f"subtype:{subtype}:reference_resolution_coverage_pct")

    return QualityGateResult(
        passed=not failed,
        failed_checks=failed,
        warning_failed_checks=warning_failed,
        skipped_checks=skipped,
        report=report,
    )
