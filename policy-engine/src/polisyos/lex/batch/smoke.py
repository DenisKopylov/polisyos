"""Fast local smoke and acceptance helpers for Lex batch."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.lex.batch.config import ALL_STAGES, BatchConfig
from polisyos.lex.batch.doc_identity import doc_type_category
from polisyos.lex.batch.pipeline import PipelineStats, run_batch_pipeline
from polisyos.lex.batch.provisions_io import _shard_prefix, provision_file_path
from polisyos.lex.batch.publish import run_publish
from polisyos.lex.batch.quality_report import build_quality_report
from polisyos.lex.batch.xml_parser import iter_documents

_APPENDIX_RE = re.compile(r"(^|\n)\s*додаток\b", re.IGNORECASE)
_TABLE_RE = re.compile(
    r"(^|\n).*(\||\bколонк[а-яіїєґ]*\b|\bграф[а-яіїєґ]*\b|(?:\S+\s{2,}){2,}\S+)",
    re.IGNORECASE,
)
_LIST_RE = re.compile(r"(^|\n)\s*(?:\d+[.)]|[а-яіїєґ]\)|[-*])\s+", re.IGNORECASE)
_ARTICLE_RE = re.compile(r"(^|\n)\s*(?:стаття|розділ|глава)\b", re.IGNORECASE)
_CATEGORY_PRIORITY = (
    "law",
    "code",
    "cabinet_resolution",
    "order",
    "regulation",
    "resolution",
    "decision",
    "decree",
    "directive",
)


@dataclass(frozen=True)
class SmokeProfile:
    name: str
    sample_docs: int
    scan_docs: int
    xml_parse_chunk: int
    structure_workers: int
    spo_batch_docs: int
    spo_task_batch_size: int
    spo_request_batch_size: int
    spo_request_batch_chars: int | None
    spo_group_timeout_seconds: float | None
    spo_max_provisions_per_doc: int
    parallel_llm: int
    gonka_rate_limit_rps: float
    max_retries: int
    llm_gate_mode: str
    llm_gate_threshold: float
    llm_gate_max_share: float
    llm_gate_audit_sample_rate: float
    llm_gap_fill_mode: str
    llm_gap_fill_max_share: float


SMOKE_PROFILES: dict[str, SmokeProfile] = {
    "fast": SmokeProfile(
        name="fast",
        sample_docs=18,
        scan_docs=180,
        xml_parse_chunk=96,
        structure_workers=2,
        spo_batch_docs=48,
        spo_task_batch_size=96,
        spo_request_batch_size=4,
        spo_request_batch_chars=4200,
        spo_group_timeout_seconds=75.0,
        spo_max_provisions_per_doc=10,
        parallel_llm=8,
        gonka_rate_limit_rps=3.0,
        max_retries=5,
        llm_gate_mode="balanced",
        llm_gate_threshold=0.58,
        llm_gate_max_share=0.30,
        llm_gate_audit_sample_rate=0.01,
        llm_gap_fill_mode="off",
        llm_gap_fill_max_share=0.0,
    ),
    "informative": SmokeProfile(
        name="informative",
        sample_docs=36,
        scan_docs=360,
        xml_parse_chunk=160,
        structure_workers=3,
        spo_batch_docs=80,
        spo_task_batch_size=160,
        spo_request_batch_size=4,
        spo_request_batch_chars=4800,
        spo_group_timeout_seconds=90.0,
        spo_max_provisions_per_doc=14,
        parallel_llm=12,
        gonka_rate_limit_rps=4.0,
        max_retries=6,
        llm_gate_mode="balanced",
        llm_gate_threshold=0.55,
        llm_gate_max_share=0.35,
        llm_gate_audit_sample_rate=0.01,
        llm_gap_fill_mode="off",
        llm_gap_fill_max_share=0.0,
    ),
    "acceptance_safe": SmokeProfile(
        name="acceptance_safe",
        sample_docs=96,
        scan_docs=1200,
        xml_parse_chunk=192,
        structure_workers=3,
        spo_batch_docs=24,
        spo_task_batch_size=48,
        spo_request_batch_size=2,
        spo_request_batch_chars=2600,
        spo_group_timeout_seconds=75.0,
        spo_max_provisions_per_doc=10,
        parallel_llm=4,
        gonka_rate_limit_rps=1.2,
        max_retries=8,
        llm_gate_mode="balanced",
        llm_gate_threshold=0.52,
        llm_gate_max_share=0.28,
        llm_gate_audit_sample_rate=0.005,
        llm_gap_fill_mode="off",
        llm_gap_fill_max_share=0.0,
    ),
    "production_gap_fill_wide": SmokeProfile(
        name="production_gap_fill_wide",
        sample_docs=96,
        scan_docs=1200,
        xml_parse_chunk=192,
        structure_workers=3,
        spo_batch_docs=24,
        spo_task_batch_size=48,
        spo_request_batch_size=2,
        spo_request_batch_chars=2600,
        spo_group_timeout_seconds=90.0,
        spo_max_provisions_per_doc=10,
        parallel_llm=10,
        gonka_rate_limit_rps=1.2,
        max_retries=8,
        llm_gate_mode="balanced",
        llm_gate_threshold=0.52,
        llm_gate_max_share=0.35,
        llm_gate_audit_sample_rate=0.005,
        llm_gap_fill_mode="wide",
        llm_gap_fill_max_share=0.80,
    ),
}


@dataclass(frozen=True)
class SmokeCandidate:
    doc_id: str
    name: str
    doc_type: str
    doc_type_category: str
    status: str
    publisher: tuple[str, ...]
    text_length: int
    structure_cues: tuple[str, ...]


def _detect_structure_cues(text: str) -> tuple[str, ...]:
    cues: list[str] = []
    if _APPENDIX_RE.search(text):
        cues.append("appendix")
    if _TABLE_RE.search(text):
        cues.append("table")
    if _LIST_RE.search(text):
        cues.append("list")
    if _ARTICLE_RE.search(text):
        cues.append("article")
    return tuple(cues)


def _category_order(categories: set[str]) -> list[str]:
    ordered = [category for category in _CATEGORY_PRIORITY if category in categories]
    extra = sorted(category for category in categories if category not in ordered)
    return ordered + extra


def _candidate_sort_key(candidate: SmokeCandidate) -> tuple[int, int, str]:
    return (-len(candidate.structure_cues), -candidate.text_length, candidate.doc_id)


def scan_smoke_candidates(
    *,
    cards_path: Path,
    texts_path: Path,
    scan_docs: int,
    status_filter: frozenset[str] | None = None,
    type_filter: frozenset[str] | None = None,
) -> list[SmokeCandidate]:
    candidates: list[SmokeCandidate] = []
    for idx, doc in enumerate(
        iter_documents(
            cards_path,
            texts_path,
            status_filter=status_filter,
            type_filter=type_filter,
        ),
        start=1,
    ):
        category = doc_type_category(doc.card.doc_type or doc.card.name) or "other"
        candidates.append(
            SmokeCandidate(
                doc_id=doc.card.doc_id,
                name=doc.card.name,
                doc_type=doc.card.doc_type,
                doc_type_category=category,
                status=doc.card.status,
                publisher=doc.card.publisher,
                text_length=len(doc.text),
                structure_cues=_detect_structure_cues(doc.text),
            )
        )
        if idx >= scan_docs:
            break
    return candidates


def select_smoke_candidates(
    candidates: list[SmokeCandidate],
    *,
    sample_docs: int,
) -> list[tuple[SmokeCandidate, str]]:
    if not candidates or sample_docs <= 0:
        return []

    selected: list[tuple[SmokeCandidate, str]] = []
    selected_ids: set[str] = set()
    cue_buckets: dict[str, list[SmokeCandidate]] = defaultdict(list)
    category_buckets: dict[str, list[SmokeCandidate]] = defaultdict(list)

    for candidate in candidates:
        category = candidate.doc_type_category or "other"
        category_buckets[category].append(candidate)
        if candidate.structure_cues:
            cue_buckets[category].append(candidate)

    for bucket in category_buckets.values():
        bucket.sort(key=_candidate_sort_key)
    for bucket in cue_buckets.values():
        bucket.sort(key=_candidate_sort_key)

    categories = _category_order(set(category_buckets))
    cue_target = min(max(4, sample_docs // 4), sum(len(bucket) for bucket in cue_buckets.values()))
    cue_indexes = {category: 0 for category in cue_buckets}

    while len(selected) < cue_target:
        added = False
        for category in categories:
            bucket = cue_buckets.get(category, [])
            while cue_indexes.get(category, 0) < len(bucket):
                candidate = bucket[cue_indexes[category]]
                cue_indexes[category] += 1
                if candidate.doc_id in selected_ids:
                    continue
                selected.append((candidate, "cue_rich"))
                selected_ids.add(candidate.doc_id)
                added = True
                break
            if len(selected) >= cue_target:
                break
        if not added:
            break

    category_indexes = {category: 0 for category in category_buckets}
    target_total = min(sample_docs, len(candidates))
    while len(selected) < target_total:
        added = False
        for category in categories:
            bucket = category_buckets.get(category, [])
            while category_indexes.get(category, 0) < len(bucket):
                candidate = bucket[category_indexes[category]]
                category_indexes[category] += 1
                if candidate.doc_id in selected_ids:
                    continue
                selected.append((candidate, "category_round_robin"))
                selected_ids.add(candidate.doc_id)
                added = True
                break
            if len(selected) >= target_total:
                break
        if not added:
            break
    return selected


def write_smoke_plan(
    *,
    output_dir: Path,
    profile: SmokeProfile,
    selected: list[tuple[SmokeCandidate, str]],
    scan_total: int,
) -> Path:
    counts_by_category = Counter(candidate.doc_type_category or "other" for candidate, _ in selected)
    counts_by_cue = Counter(cue for candidate, _ in selected for cue in candidate.structure_cues)
    payload = {
        "kind": "lex_smoke_plan",
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": asdict(profile),
        "scan_total": scan_total,
        "selected_total": len(selected),
        "counts_by_category": dict(counts_by_category),
        "counts_by_structure_cue": dict(counts_by_cue),
        "selected_docs": [
            {
                "doc_id": candidate.doc_id,
                "name": candidate.name,
                "doc_type": candidate.doc_type,
                "doc_type_category": candidate.doc_type_category,
                "status": candidate.status,
                "publisher": list(candidate.publisher),
                "text_length": candidate.text_length,
                "structure_cues": list(candidate.structure_cues),
                "selection_reason": reason,
            }
            for candidate, reason in selected
        ],
    }
    plan_path = output_dir / "smoke" / "smoke_plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return plan_path


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _doc_jsonl_path(base_dir: Path, doc_id: str) -> Path:
    return base_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"


def _summarize_doc(output_dir: Path, plan_entry: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(plan_entry.get("doc_id") or "")
    provision_rows = _jsonl_rows(provision_file_path(output_dir / "provisions", doc_id))
    spo_rows = _jsonl_rows(_doc_jsonl_path(output_dir / "spo_results", doc_id))
    grounded_rows = _jsonl_rows(_doc_jsonl_path(output_dir / "spo_grounded", doc_id))
    reference_rows = _jsonl_rows(_doc_jsonl_path(output_dir / "references", doc_id))
    resolved_rows = _jsonl_rows(_doc_jsonl_path(output_dir / "resolved_references", doc_id))

    non_full_provisions = sum(
        1
        for row in provision_rows
        if str(row.get("kind") or "") not in {"full_text", "full_chunk"}
    )
    fallback_provisions = sum(
        1
        for row in provision_rows
        if bool(row.get("is_fallback_chunk")) or not bool(row.get("fallback_allowed_for_reasoning", True))
    )
    empty_spo_rows = 0
    spo_statement_total = 0
    timeout_fallback_rows = 0
    error_fallback_rows = 0
    grounded_statement_total = 0
    normative_statement_total = 0
    grounded_missing_quote_total = 0
    subtype_counts: Counter[str] = Counter()

    for row in provision_rows:
        subtype = str(row.get("legal_unit_subtype") or "").strip()
        if subtype:
            subtype_counts[subtype] += 1

    for row in spo_rows:
        extraction_source = str(row.get("extraction_source") or "")
        subtype = str(row.get("legal_unit_subtype") or "").strip()
        if subtype:
            subtype_counts[subtype] += 2
        if extraction_source.endswith("timeout_fallback"):
            timeout_fallback_rows += 1
        elif extraction_source.endswith("error_fallback"):
            error_fallback_rows += 1
        statements = row.get("statements", [])
        if not isinstance(statements, list) or not statements:
            empty_spo_rows += 1
        if isinstance(statements, list):
            spo_statement_total += len(statements)

    for row in grounded_rows:
        statements = row.get("statements", [])
        if not isinstance(statements, list):
            continue
        for statement in statements:
            if not isinstance(statement, dict):
                continue
            trust_tier = str(statement.get("trust_tier") or "")
            if trust_tier in {"grounded_fact", "normative_fact"}:
                grounded_statement_total += 1
                if trust_tier == "normative_fact":
                    normative_statement_total += 1
                quote = str(statement.get("source_quote_uk") or "").strip()
                if (not quote) or statement.get("source_quote_start") is None or statement.get("source_quote_end") is None:
                    grounded_missing_quote_total += 1

    flags: list[str] = []
    if provision_rows and non_full_provisions == 0:
        flags.append("full_only_structure")
    if spo_rows and empty_spo_rows == len(spo_rows):
        flags.append("empty_spo_only")
    if timeout_fallback_rows > 0:
        flags.append("llm_timeout_fallback")
    if error_fallback_rows > 0:
        flags.append("llm_error_fallback")
    if grounded_statement_total == 0:
        flags.append("no_grounded_facts")
    if reference_rows and not resolved_rows:
        flags.append("unresolved_references")
    if provision_rows and fallback_provisions == len(provision_rows):
        flags.append("search_only_structure")

    return {
        "doc_id": doc_id,
        "name": plan_entry.get("name", ""),
        "doc_type": plan_entry.get("doc_type", ""),
        "doc_type_category": plan_entry.get("doc_type_category", ""),
        "selection_reason": plan_entry.get("selection_reason", ""),
        "structure_cues": plan_entry.get("structure_cues", []),
        "text_length": int(plan_entry.get("text_length") or 0),
        "dominant_legal_unit_subtype": subtype_counts.most_common(1)[0][0] if subtype_counts else "",
        "legal_unit_subtype_counts": dict(sorted(subtype_counts.items())),
        "provisions_total": len(provision_rows),
        "non_full_provisions": non_full_provisions,
        "fallback_provisions": fallback_provisions,
        "spo_rows_total": len(spo_rows),
        "empty_spo_rows": empty_spo_rows,
        "spo_statement_total": spo_statement_total,
        "timeout_fallback_rows": timeout_fallback_rows,
        "error_fallback_rows": error_fallback_rows,
        "grounded_statement_total": grounded_statement_total,
        "grounded_missing_quote_total": grounded_missing_quote_total,
        "normative_statement_total": normative_statement_total,
        "references_total": len(reference_rows),
        "resolved_references_total": len(resolved_rows),
        "flags": flags,
        "paths": {
            "provisions": str(provision_file_path(output_dir / "provisions", doc_id)),
            "spo_results": str(_doc_jsonl_path(output_dir / "spo_results", doc_id)),
            "spo_grounded": str(_doc_jsonl_path(output_dir / "spo_grounded", doc_id)),
            "references": str(_doc_jsonl_path(output_dir / "references", doc_id)),
            "resolved_references": str(_doc_jsonl_path(output_dir / "resolved_references", doc_id)),
        },
    }


def build_smoke_report(
    *,
    output_dir: Path,
    profile: SmokeProfile,
    plan_path: Path,
    stats: PipelineStats,
) -> tuple[Path, Path]:
    with open(plan_path, "r", encoding="utf-8") as fh:
        plan = json.load(fh)

    quality_report = build_quality_report(
        provisions_dir=output_dir / "provisions",
        spo_results_dir=output_dir / "spo_grounded" if (output_dir / "spo_grounded").exists() else output_dir / "spo_results",
        llm_gate_manifest_path=output_dir / "manifests" / "llm_gate.json",
        llm_gate_audit_path=output_dir / "llm_gate_audit.jsonl",
    )

    consumer_manifest: dict[str, Any] = {}
    consumer_manifest_path = output_dir / "publish" / "consumer_readiness.json"
    if consumer_manifest_path.exists():
        with open(consumer_manifest_path, "r", encoding="utf-8") as fh:
            consumer_manifest = json.load(fh)

    benchmark_manifest: dict[str, Any] = {}
    benchmark_manifest_path = output_dir / "benchmark_report.json"
    if benchmark_manifest_path.exists():
        with open(benchmark_manifest_path, "r", encoding="utf-8") as fh:
            benchmark_manifest = json.load(fh)

    doc_summaries = [
        _summarize_doc(output_dir, entry)
        for entry in plan.get("selected_docs", [])
        if isinstance(entry, dict)
    ]
    top_problem_docs = [
        row for row in sorted(doc_summaries, key=lambda row: (len(row["flags"]), -row["grounded_statement_total"]), reverse=True)
        if row["flags"]
    ][:10]
    problem_doc_groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"docs_total": 0, "flags_total": 0, "grounded_total": 0, "normative_total": 0, "doc_ids": []}
    )
    for row in top_problem_docs:
        key = (str(row.get("doc_type_category") or "other"), str(row.get("dominant_legal_unit_subtype") or "unknown"))
        group = problem_doc_groups[key]
        group["docs_total"] += 1
        group["flags_total"] += len(row["flags"])
        group["grounded_total"] += int(row["grounded_statement_total"])
        group["normative_total"] += int(row["normative_statement_total"])
        group["doc_ids"].append(str(row["doc_id"]))
    top_problem_doc_groups = [
        {
            "doc_family": family,
            "legal_unit_subtype": subtype,
            **payload,
        }
        for (family, subtype), payload in sorted(
            problem_doc_groups.items(),
            key=lambda item: (item[1]["flags_total"], item[1]["docs_total"], -item[1]["grounded_total"]),
            reverse=True,
        )
    ][:8]
    top_good_docs = sorted(
        [row for row in doc_summaries if row["grounded_statement_total"] > 0 or row["resolved_references_total"] > 0],
        key=lambda row: (
            row["normative_statement_total"],
            row["grounded_statement_total"],
            row["resolved_references_total"],
        ),
        reverse=True,
    )[:5]

    report = {
        "kind": "lex_smoke_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": asdict(profile),
        "pipeline": {
            "documents": stats.total_docs,
            "provisions": stats.total_provisions,
            "spo": stats.total_spo,
            "candidate_facts": stats.candidate_facts,
            "grounded_facts": stats.grounded_facts,
            "normative_facts": stats.normative_facts,
            "reference_edges": stats.reference_edges,
            "exported_claims": stats.exported_claims,
            "exported_claim_sets": stats.exported_claim_sets,
            "quality_gate_passed": stats.quality_gate_passed,
            "quality_passed": stats.quality_passed,
            "qc_passed": stats.qc_passed,
            "benchmark_passed": stats.benchmark_passed,
            "release_passed": stats.release_passed,
            "quality_gate_failed_checks": stats.quality_gate_failed_checks,
            "quality_failed_checks": stats.quality_failed_checks,
            "quality_hotspot_failed_checks": stats.quality_hotspot_failed_checks,
            "quality_warning_failed_checks": stats.quality_warning_failed_checks,
            "qc_failed_checks": stats.qc_failed_checks,
            "benchmark_failed_checks": stats.benchmark_failed_checks,
            "release_failed_checks": stats.release_failed_checks,
            "stage_times": stats.stage_times,
            "elapsed_seconds": stats.elapsed_seconds,
            "llm_gate_metrics": stats.llm_gate_metrics,
        },
        "sample_plan": {
            "path": str(plan_path),
            "scan_total": int(plan.get("scan_total") or 0),
            "selected_total": int(plan.get("selected_total") or 0),
            "counts_by_category": plan.get("counts_by_category", {}),
            "counts_by_structure_cue": plan.get("counts_by_structure_cue", {}),
        },
        "quality_report": quality_report,
        "consumer_readiness": consumer_manifest,
        "benchmark_report": benchmark_manifest,
        "document_summary": {
            "selected_docs_total": len(doc_summaries),
            "with_non_full_structure": sum(1 for row in doc_summaries if row["non_full_provisions"] > 0),
            "with_grounded_facts": sum(1 for row in doc_summaries if row["grounded_statement_total"] > 0),
            "with_normative_facts": sum(1 for row in doc_summaries if row["normative_statement_total"] > 0),
            "with_resolved_refs": sum(1 for row in doc_summaries if row["resolved_references_total"] > 0),
            "with_timeout_fallbacks": sum(1 for row in doc_summaries if row["timeout_fallback_rows"] > 0),
            "with_error_fallbacks": sum(1 for row in doc_summaries if row["error_fallback_rows"] > 0),
        },
        "top_problem_docs": top_problem_docs,
        "top_problem_doc_groups": top_problem_doc_groups,
        "top_good_docs": top_good_docs,
        "artifacts": {
            "db_path": str(output_dir / "lex_knowledge_graph.duckdb"),
            "publish_manifest_path": str(output_dir / "publish" / "manifest.json"),
            "consumer_manifest_path": str(consumer_manifest_path),
            "benchmark_report_path": str(benchmark_manifest_path),
            "claim_summary_path": str(output_dir / "claim_exports" / "normative_claim_sets_summary.json"),
        },
    }

    smoke_dir = output_dir / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    report_path = smoke_dir / "smoke_report.json"
    summary_path = smoke_dir / "smoke_summary.md"
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    lines = [
        "# Lex Smoke Summary",
        "",
        f"- Profile: `{profile.name}`",
        f"- Selected docs: `{report['sample_plan']['selected_total']}` from first `{report['sample_plan']['scan_total']}` matched docs",
        f"- Pipeline: docs `{stats.total_docs}`, provisions `{stats.total_provisions}`, SPO rows `{stats.total_spo}`, grounded facts `{stats.grounded_facts}`, normative facts `{stats.normative_facts}`, resolved refs `{stats.reference_edges}`",
        f"- Quality gate passed: `{stats.quality_gate_passed}`",
        f"- QC passed: `{stats.qc_passed}`",
        f"- Benchmark passed: `{stats.benchmark_passed if stats.benchmark_passed is not None else (benchmark_manifest.get('readiness', {}).get('passed') if benchmark_manifest else '-')}`",
        f"- Release passed: `{stats.release_passed}`",
        f"- Quality gate failed checks: `{', '.join(stats.quality_gate_failed_checks) if stats.quality_gate_failed_checks else '-'}`",
        f"- Quality hotspot failed checks: `{', '.join(stats.quality_hotspot_failed_checks) if stats.quality_hotspot_failed_checks else '-'}`",
        f"- QC failed checks: `{', '.join(stats.qc_failed_checks) if stats.qc_failed_checks else '-'}`",
        f"- Release failed checks: `{', '.join(stats.release_failed_checks) if stats.release_failed_checks else '-'}`",
        "",
        "## Sample mix",
        "",
    ]
    for category, count in sorted(report["sample_plan"]["counts_by_category"].items()):
        lines.append(f"- `{category}`: {count}")
    if report["sample_plan"]["counts_by_structure_cue"]:
        lines.extend(["", "## Structure cues", ""])
        for cue, count in sorted(report["sample_plan"]["counts_by_structure_cue"].items()):
            lines.append(f"- `{cue}`: {count}")
    if benchmark_manifest:
        lines.extend(["", "## Benchmark", ""])
        for name, value in sorted((benchmark_manifest.get("metrics") or {}).items()):
            lines.append(f"- `{name}`: {value}")
    if top_problem_docs:
        lines.extend(["", "## Problem docs", ""])
        for row in top_problem_docs[:5]:
            lines.append(
                f"- `{row['doc_id']}` `{row['doc_type_category']}` flags={','.join(row['flags'])} grounded={row['grounded_statement_total']} refs={row['resolved_references_total']} timeout_fb={row['timeout_fallback_rows']}"
            )
    if top_problem_doc_groups:
        lines.extend(["", "## Problem groups", ""])
        for row in top_problem_doc_groups[:5]:
            lines.append(
                f"- `{row['doc_family']}` / `{row['legal_unit_subtype']}` docs={row['docs_total']} flags={row['flags_total']} grounded={row['grounded_total']}"
            )
    if top_good_docs:
        lines.extend(["", "## Good docs", ""])
        for row in top_good_docs[:5]:
            lines.append(
                f"- `{row['doc_id']}` `{row['doc_type_category']}` normative={row['normative_statement_total']} grounded={row['grounded_statement_total']} refs={row['resolved_references_total']}"
            )
    with open(summary_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return report_path, summary_path


def run_smoke(
    *,
    cards_path: Path,
    texts_path: Path,
    output_dir: Path,
    profile_name: str,
    gonka_api_key: str = "",
    gonka_api_keys: list[str] | None = None,
    gonka_base_url: str = "https://api.gonkagate.com/v1",
    gonka_disable_json_mode: bool = False,
    llm_model: str = "qwen/qwen3-235b-a22b-instruct-2507-fp8",
    resume: bool = False,
    status_filter: frozenset[str] | None = None,
    type_filter: frozenset[str] | None = None,
    sample_docs: int | None = None,
    scan_docs: int | None = None,
    parallel_llm: int | None = None,
    gonka_rate_limit_rps: float | None = None,
    max_retries: int | None = None,
    spo_rate_warmup_seconds: float | None = None,
    spo_rate_warmup_start_scale: float | None = None,
    spo_adaptive_rate_enabled: bool | None = None,
    spo_adaptive_rate_recovery_factor: float | None = None,
    spo_adaptive_rate_penalty_multiplier: float | None = None,
    spo_adaptive_rate_max_scale: float | None = None,
    spo_retryable_followup_worker_scale: float | None = None,
    spo_retryable_followup_dispatch_rps_scale: float | None = None,
    spo_retryable_followup_client_rate_scale: float | None = None,
    spo_retryable_followup_client_concurrency_scale: float | None = None,
    spo_request_batch_chars: int | None = None,
    spo_adaptive_batch_downshift_enabled: bool | None = None,
    spo_adaptive_batch_soft_chars_share: float | None = None,
    spo_group_timeout_seconds: float | None = None,
    llm_gap_fill_mode: str | None = None,
    llm_gap_fill_max_share: float | None = None,
    stages: set[str] | None = None,
) -> dict[str, Any]:
    if profile_name not in SMOKE_PROFILES:
        raise ValueError(f"Unknown smoke profile: {profile_name}")

    profile = SMOKE_PROFILES[profile_name]
    overrides = asdict(profile)
    if sample_docs is not None:
        overrides["sample_docs"] = int(sample_docs)
    if scan_docs is not None:
        overrides["scan_docs"] = int(scan_docs)
    if parallel_llm is not None:
        overrides["parallel_llm"] = int(parallel_llm)
    if gonka_rate_limit_rps is not None:
        overrides["gonka_rate_limit_rps"] = float(gonka_rate_limit_rps)
    if max_retries is not None:
        overrides["max_retries"] = int(max_retries)
    if spo_request_batch_chars is not None:
        overrides["spo_request_batch_chars"] = int(spo_request_batch_chars)
    if spo_group_timeout_seconds is not None:
        overrides["spo_group_timeout_seconds"] = float(spo_group_timeout_seconds)
    if llm_gap_fill_mode is not None:
        overrides["llm_gap_fill_mode"] = str(llm_gap_fill_mode)
    if llm_gap_fill_max_share is not None:
        overrides["llm_gap_fill_max_share"] = float(llm_gap_fill_max_share)
    profile = SmokeProfile(**overrides)

    candidates = scan_smoke_candidates(
        cards_path=cards_path,
        texts_path=texts_path,
        scan_docs=profile.scan_docs,
        status_filter=status_filter,
        type_filter=type_filter,
    )
    selected = select_smoke_candidates(candidates, sample_docs=profile.sample_docs)
    if not selected:
        raise RuntimeError("Smoke planner selected zero documents. Check filters or source XML.")

    plan_path = write_smoke_plan(
        output_dir=output_dir,
        profile=profile,
        selected=selected,
        scan_total=len(candidates),
    )
    doc_ids = frozenset(candidate.doc_id for candidate, _ in selected)
    started_at = datetime.now(UTC).isoformat()
    cas_root_env = str(os.environ.get("POLISYOS_CAS_ROOT", "") or "").strip()
    fact_log_root_env = str(os.environ.get("POLISYOS_FACT_LOG_ROOT", "") or "").strip()
    cas_root = Path(cas_root_env).expanduser() if cas_root_env else (output_dir / "cas")
    fact_log_root = Path(fact_log_root_env).expanduser() if fact_log_root_env else (output_dir / "fact_log")
    enable_claim_cas = True

    config = BatchConfig(
        cards_path=cards_path,
        texts_path=texts_path,
        output_dir=output_dir,
        gonka_api_key=gonka_api_key,
        gonka_api_keys=list(gonka_api_keys or []),
        gonka_base_url=gonka_base_url,
        gonka_disable_json_mode=gonka_disable_json_mode,
        llm_model=llm_model,
        max_concurrent_llm=profile.parallel_llm,
        rate_limit_rps=profile.gonka_rate_limit_rps,
        max_retries=profile.max_retries,
        spo_rate_warmup_seconds=45.0 if spo_rate_warmup_seconds is None else float(spo_rate_warmup_seconds),
        spo_rate_warmup_start_scale=3.0 if spo_rate_warmup_start_scale is None else float(spo_rate_warmup_start_scale),
        spo_adaptive_rate_enabled=True if spo_adaptive_rate_enabled is None else bool(spo_adaptive_rate_enabled),
        spo_adaptive_rate_recovery_factor=(
            0.97 if spo_adaptive_rate_recovery_factor is None else float(spo_adaptive_rate_recovery_factor)
        ),
        spo_adaptive_rate_penalty_multiplier=(
            1.35 if spo_adaptive_rate_penalty_multiplier is None else float(spo_adaptive_rate_penalty_multiplier)
        ),
        spo_adaptive_rate_max_scale=(
            8.0 if spo_adaptive_rate_max_scale is None else float(spo_adaptive_rate_max_scale)
        ),
        spo_retryable_followup_worker_scale=(
            0.5 if spo_retryable_followup_worker_scale is None else float(spo_retryable_followup_worker_scale)
        ),
        spo_retryable_followup_dispatch_rps_scale=(
            0.5
            if spo_retryable_followup_dispatch_rps_scale is None
            else float(spo_retryable_followup_dispatch_rps_scale)
        ),
        spo_retryable_followup_client_rate_scale=(
            0.5 if spo_retryable_followup_client_rate_scale is None else float(spo_retryable_followup_client_rate_scale)
        ),
        spo_retryable_followup_client_concurrency_scale=(
            0.5
            if spo_retryable_followup_client_concurrency_scale is None
            else float(spo_retryable_followup_client_concurrency_scale)
        ),
        status_filter=status_filter,
        type_filter=type_filter,
        doc_id_filter=doc_ids,
        stages=stages if stages else ALL_STAGES,
        resume=resume,
        max_docs=len(doc_ids),
        xml_parse_chunk=profile.xml_parse_chunk,
        structure_workers=profile.structure_workers,
        spo_batch_docs=profile.spo_batch_docs,
        spo_task_batch_size=profile.spo_task_batch_size,
        spo_request_batch_size=profile.spo_request_batch_size,
        spo_request_batch_chars=profile.spo_request_batch_chars,
        spo_adaptive_batch_downshift_enabled=(
            True if spo_adaptive_batch_downshift_enabled is None else bool(spo_adaptive_batch_downshift_enabled)
        ),
        spo_adaptive_batch_soft_chars_share=(
            0.80 if spo_adaptive_batch_soft_chars_share is None else float(spo_adaptive_batch_soft_chars_share)
        ),
        spo_group_timeout_seconds=profile.spo_group_timeout_seconds,
        spo_max_provisions_per_doc=profile.spo_max_provisions_per_doc,
        spo_extract_mode="light",
        spo_verify_mode="code",
        llm_gate_enabled=True,
        llm_gate_mode=profile.llm_gate_mode,
        llm_gate_threshold=profile.llm_gate_threshold,
        llm_gate_max_share=profile.llm_gate_max_share,
        llm_gate_audit_sample_rate=profile.llm_gate_audit_sample_rate,
        llm_gap_fill_enabled=profile.llm_gap_fill_mode != "off",
        llm_gap_fill_mode=profile.llm_gap_fill_mode,
        llm_gap_fill_max_share=profile.llm_gap_fill_max_share,
        publish_require_embeddings=False,
        export_claims_to_cas=enable_claim_cas,
        cas_root=cas_root if enable_claim_cas else None,
        fact_log_root=fact_log_root if enable_claim_cas else None,
        quality_fail_on_critical=False,
        quality_structure_fail_fast=False,
        quality_min_audit_samples_for_rate=10,
        quality_min_provision_docs_for_doc_rate=min(10, len(doc_ids)),
        quality_min_spo_rows_for_row_rate=10,
        quality_min_statements_for_statement_rate=20,
    )
    stats = asyncio.run(run_batch_pipeline(config))
    if not (output_dir / "publish" / "manifest.json").exists():
        run_publish(output_dir, require_embeddings=False)

    report_path, summary_path = build_smoke_report(
        output_dir=output_dir,
        profile=profile,
        plan_path=plan_path,
        stats=stats,
    )
    manifest_path = write_stage_manifest(
        manifest_path=output_dir / "manifests" / "smoke.json",
        stage="smoke",
        status="ok",
        metrics={
            "documents": stats.total_docs,
            "provisions": stats.total_provisions,
            "spo": stats.total_spo,
            "grounded_facts": stats.grounded_facts,
            "normative_facts": stats.normative_facts,
            "reference_edges": stats.reference_edges,
            "elapsed_seconds": round(stats.elapsed_seconds, 3),
            "selected_docs": len(doc_ids),
            "scanned_docs": len(candidates),
        },
        artifacts=[
            plan_path,
            report_path,
            summary_path,
            output_dir / "publish" / "manifest.json",
            output_dir / "publish" / "consumer_readiness.json",
            output_dir / "lex_knowledge_graph.duckdb",
        ],
        started_at=started_at,
    )
    return {
        "plan_path": plan_path,
        "report_path": report_path,
        "summary_path": summary_path,
        "manifest_path": manifest_path,
        "stats": stats,
        "profile": profile,
        "selected_docs": len(doc_ids),
        "scanned_docs": len(candidates),
    }


__all__ = [
    "SMOKE_PROFILES",
    "SmokeCandidate",
    "SmokeProfile",
    "build_smoke_report",
    "run_smoke",
    "scan_smoke_candidates",
    "select_smoke_candidates",
    "write_smoke_plan",
]
