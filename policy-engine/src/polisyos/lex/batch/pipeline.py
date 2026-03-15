"""Orchestrate all stages of the Lex batch pipeline in a memory-friendly way."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from polisyos.common.logger import get_logger
from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.doc_family import classify_doc_family, infer_doc_type_category
from polisyos.lex.batch.progress import ProgressTracker
from polisyos.lex.batch.provisions_io import read_provisions, write_provisions

if TYPE_CHECKING:
    from polisyos.lex.batch.llm_gate import GateRuntime
    from polisyos.lex.batch.spo_extractor import GonkaClient
    from polisyos.lex.batch.structurer import ProvisionSpan
    from polisyos.lex.batch.xml_parser import NPADocument

logger = get_logger(__name__)
T = TypeVar("T")


@dataclass
class PipelineStats:
    total_docs: int = 0
    total_provisions: int = 0
    total_spo: int = 0
    entities: int = 0
    facts: int = 0
    provisions_embedded: int = 0
    elapsed_seconds: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    quality_passed: bool | None = None
    quality_report: dict[str, float] = field(default_factory=dict)
    quality_failed_checks: list[str] = field(default_factory=list)
    quality_skipped_checks: list[str] = field(default_factory=list)
    llm_gate_metrics: dict[str, float | int] = field(default_factory=dict)
    grounded_statements: int = 0
    normative_statements: int = 0
    candidate_facts: int = 0
    grounded_facts: int = 0
    normative_facts: int = 0
    reference_edges: int = 0
    exported_claims: int = 0
    exported_claim_sets: int = 0
    benchmark_passed: bool | None = None
    benchmark_metrics: dict[str, float | int] = field(default_factory=dict)
    benchmark_failed_checks: list[str] = field(default_factory=list)
    published_bundle: bool = False


@dataclass
class LLMGateStats:
    """Runtime counters for LLM gating decisions."""

    provisions_seen: int = 0
    skipped_total: int = 0
    auto_by_code_total: int = 0
    llm_candidate_total: int = 0
    llm_sent_total: int = 0
    deferred_total: int = 0
    audit_sample_total: int = 0
    audit_miss_total: int = 0
    circuit_breaker_hits: int = 0
    dedup_reused_total: int = 0

    @property
    def llm_saved_pct(self) -> float:
        if self.llm_candidate_total <= 0:
            return 100.0
        saved = max(0, self.llm_candidate_total - self.llm_sent_total)
        return (saved * 100.0) / self.llm_candidate_total

    @property
    def audit_miss_rate_pct(self) -> float:
        if self.audit_sample_total <= 0:
            return 0.0
        return (self.audit_miss_total * 100.0) / self.audit_sample_total


@dataclass
class StructureQualityStats:
    provision_docs_total: int = 0
    full_only_docs: int = 0
    duplicate_anchor_docs: int = 0


@dataclass(frozen=True)
class SPOLLMSettings:
    task_batch_size: int
    request_batch_size: int
    request_batch_chars: int | None
    group_timeout_seconds: float | None


@dataclass
class SPODocRoutingPlan:
    reasoning_spans: list[ProvisionSpan]
    llm_allowed: bool
    llm_settings: SPOLLMSettings
    flags: tuple[str, ...] = ()


_STRATIFIED_AUDIT_FAMILIES = frozenset({"appendix_heavy", "law", "treaty_protocol", "decree_resolution"})


@dataclass
class StratifiedAuditSampler:
    base_rate: float
    max_forced_samples: int = 32
    sampled_counts: dict[str, int] = field(default_factory=dict)
    forced_samples_used: int = 0

    @staticmethod
    def _key(*, family: str, subtype: str, route_class: str) -> str:
        return f"{family or 'other'}|{subtype or 'unknown'}|{route_class or 'unknown'}"

    def should_force_sample(
        self,
        *,
        family: str,
        subtype: str,
        route_class: str,
        llm_available: bool,
    ) -> bool:
        if not llm_available or self.base_rate <= 0.0:
            return False
        if family not in _STRATIFIED_AUDIT_FAMILIES:
            return False
        if self.forced_samples_used >= self.max_forced_samples:
            return False
        key = self._key(family=family, subtype=subtype, route_class=route_class)
        return self.sampled_counts.get(key, 0) < 1

    def register_sample(
        self,
        *,
        family: str,
        subtype: str,
        route_class: str,
        forced: bool,
    ) -> None:
        key = self._key(family=family, subtype=subtype, route_class=route_class)
        self.sampled_counts[key] = self.sampled_counts.get(key, 0) + 1
        if forced:
            self.forced_samples_used += 1


_MEGA_CATALOG_TITLE_RE = re.compile(
    r"\b("
    r"спис(?:ок|ки|ків|ку)|"
    r"перелік(?:и|ів|у)?|"
    r"реєстр(?:и|ів|у)?|"
    r"мереж[а-яіїєґ]*|"
    r"каталог(?:и|ів|у)?|"
    r"номенклатур[а-яіїєґ]*|"
    r"тариф[а-яіїєґ]*|"
    r"ставк[аиі]\s+мита|"
    r"штатн[а-яіїєґ]*\s+норматив[а-яіїєґ]*|"
    r"перелік\s+об['’]єкт[а-яіїєґ]*"
    r")\b",
    re.IGNORECASE,
)
_PURE_CATALOG_TITLE_RE = re.compile(
    r"\b("
    r"спис(?:ок|ки|ків|ку)|"
    r"перелік(?:и|ів|у)?|"
    r"реєстр(?:и|ів|у)?|"
    r"мереж[а-яіїєґ]*|"
    r"каталог(?:и|ів|у)?|"
    r"номенклатур[а-яіїєґ]*|"
    r"тариф[а-яіїєґ]*|"
    r"ставк[аиі]\s+мита|"
    r"штатн[а-яіїєґ]*\s+норматив[а-яіїєґ]*"
    r")\b",
    re.IGNORECASE,
)
_NORMATIVE_SPAN_SIGNAL_RE = re.compile(
    r"("
    r"зобов['’]?яз|"
    r"повин(?:ен|на|ні|но)|"
    r"має\s+право|"
    r"забороняє(?:ться)?|"
    r"не\s+допускає(?:ться)?|"
    r"затвердити|затверджується|"
    r"встановити|встановлюється|"
    r"визначити|визначається|"
    r"внести\s+зміни|"
    r"набирає\s+чинності|"
    r"поширюється|"
    r"доручити|"
    r"ратифікувати|"
    r"схвалити|"
    r"підлягає|"
    r"забезпечити|"
    r"визна(?:ти|ється)\s+таким"
    r")",
    re.IGNORECASE,
)
_REFERENCE_SPAN_SIGNAL_RE = re.compile(
    r"("
    r"статт[іяею]|"
    r"пункт[ауеиі]?|"
    r"розділ|"
    r"глава|"
    r"закон(?:у|ом)?\s+україни|"
    r"постанова|"
    r"наказ|"
    r"№\s*\d"
    r")",
    re.IGNORECASE,
)
_THRESHOLD_SPAN_SIGNAL_RE = re.compile(
    r"("
    r"\d+\s*(?:%|грн|коп|рок(?:ів|и)?|дн(?:ів|і)?|місяц(?:ів|і)|квартал(?:ів|и)?)|"
    r"не\s+менше|"
    r"не\s+більше|"
    r"не\s+нижче|"
    r"не\s+вище"
    r")",
    re.IGNORECASE,
)


def _span_reasoning_score(
    span: ProvisionSpan,
    *,
    doc_title: str,
    quality_family: str,
) -> int:
    struct_kind = (span.struct_kind or span.kind or "").strip().lower()
    section_role = (span.section_role or "").strip().lower()
    text = span.text.strip()
    score = 0

    if struct_kind in {"article", "part", "point", "subpoint"}:
        score += 5
    elif struct_kind in {"paragraph", "enumeration_item"}:
        score += 3
    elif struct_kind == "table_row":
        score += 1

    if section_role in {"table_clause", "catalog_entry", "form_clause"}:
        score += 1
    if section_role in {"table_header", "appendix_section", "form_header", "attachment_inventory"}:
        score -= 6

    if len(text) < 40:
        score -= 4
    elif len(text) <= 1200:
        score += 2
    elif len(text) <= 2400:
        score += 1
    elif len(text) > 4500:
        score -= 3

    if text.endswith(":"):
        score -= 3
    if _NORMATIVE_SPAN_SIGNAL_RE.search(text):
        score += 5
    if _REFERENCE_SPAN_SIGNAL_RE.search(text):
        score += 3
    if _THRESHOLD_SPAN_SIGNAL_RE.search(text):
        score += 3

    if quality_family == "appendix_heavy" and section_role == "catalog_entry":
        if not _NORMATIVE_SPAN_SIGNAL_RE.search(text) and not _THRESHOLD_SPAN_SIGNAL_RE.search(text):
            score -= 3
    if _PURE_CATALOG_TITLE_RE.search(doc_title) and section_role == "catalog_entry":
        if not _NORMATIVE_SPAN_SIGNAL_RE.search(text) and not _THRESHOLD_SPAN_SIGNAL_RE.search(text):
            score -= 4
    return score


def _prioritize_reasoning_spans(
    spans: list[ProvisionSpan],
    *,
    doc_title: str,
    quality_family: str,
    limit: int,
) -> list[ProvisionSpan]:
    if limit <= 0 or not spans:
        return []
    scored: list[tuple[int, int, ProvisionSpan]] = []
    for idx, span in enumerate(spans):
        scored.append(((_span_reasoning_score(span, doc_title=doc_title, quality_family=quality_family)), idx, span))
    scored.sort(
        key=lambda item: (
            item[0],
            -min(len(item[2].text), 4096),
            -item[1],
        ),
        reverse=True,
    )
    selected = scored[:limit]
    if not selected:
        return []
    selected_indexes = {idx for _, idx, _ in selected}
    return [span for idx, span in enumerate(spans) if idx in selected_indexes]


def _build_spo_doc_routing_plan(
    *,
    doc: NPADocument,
    prov_rows: list[dict[str, Any]],
    reasoning_spans: list[ProvisionSpan],
    quality_family: str,
    config: BatchConfig,
) -> SPODocRoutingPlan:
    reasoning_total = len(reasoning_spans)
    base_limit = reasoning_total
    if config.spo_max_provisions_per_doc is not None:
        configured_limit = int(config.spo_max_provisions_per_doc)
        if quality_family == "law":
            configured_limit = max(configured_limit, 24)
        elif quality_family == "treaty_protocol":
            configured_limit = max(configured_limit, 16)
        base_limit = min(base_limit, configured_limit)
    base_settings = SPOLLMSettings(
        task_batch_size=max(1, int(config.spo_task_batch_size)),
        request_batch_size=max(1, int(config.spo_request_batch_size)),
        request_batch_chars=(
            int(config.spo_request_batch_chars)
            if config.spo_request_batch_chars is not None
            else None
        ),
        group_timeout_seconds=config.spo_group_timeout_seconds,
    )
    if not reasoning_spans:
        return SPODocRoutingPlan(
            reasoning_spans=[],
            llm_allowed=True,
            llm_settings=base_settings,
        )

    total_provisions = len(prov_rows)
    search_only_total = max(0, total_provisions - reasoning_total)
    search_only_ratio = search_only_total / max(1, total_provisions)
    title = str(doc.card.name or "")
    lower_title = title.lower()
    mega_title = bool(_MEGA_CATALOG_TITLE_RE.search(lower_title))
    pure_catalog_title = bool(_PURE_CATALOG_TITLE_RE.search(lower_title))

    extreme_outlier = total_provisions >= 3000 or (
        mega_title and total_provisions >= 1200 and search_only_ratio >= 0.94
    )
    mega_outlier = extreme_outlier or (
        (mega_title or quality_family == "appendix_heavy")
        and total_provisions >= 800
        and search_only_ratio >= 0.85
    )
    large_batch = reasoning_total >= 96 or total_provisions >= 1200

    flags: list[str] = []
    selected_spans = reasoning_spans
    llm_allowed = True
    llm_settings = base_settings

    if extreme_outlier:
        flags.extend(["mega_outlier", "extreme_outlier"])
        span_limit = min(base_limit, 6)
        selected_spans = _prioritize_reasoning_spans(
            reasoning_spans,
            doc_title=title,
            quality_family=quality_family,
            limit=span_limit,
        )
        llm_allowed = not pure_catalog_title
        llm_settings = SPOLLMSettings(
            task_batch_size=min(base_settings.task_batch_size, 8),
            request_batch_size=1,
            request_batch_chars=min(base_settings.request_batch_chars or 2200, 2200),
            group_timeout_seconds=(
                min(base_settings.group_timeout_seconds, 45.0)
                if base_settings.group_timeout_seconds is not None
                else 45.0
            ),
        )
    elif mega_outlier:
        flags.append("mega_outlier")
        span_limit = min(base_limit, 8 if pure_catalog_title else 10)
        selected_spans = _prioritize_reasoning_spans(
            reasoning_spans,
            doc_title=title,
            quality_family=quality_family,
            limit=span_limit,
        )
        llm_allowed = not (pure_catalog_title and search_only_ratio >= 0.97 and total_provisions >= 1200)
        llm_settings = SPOLLMSettings(
            task_batch_size=min(base_settings.task_batch_size, 16),
            request_batch_size=min(base_settings.request_batch_size, 2),
            request_batch_chars=min(base_settings.request_batch_chars or 2400, 2400),
            group_timeout_seconds=(
                min(base_settings.group_timeout_seconds, 60.0)
                if base_settings.group_timeout_seconds is not None
                else 60.0
            ),
        )
    elif large_batch:
        flags.append("adaptive_batching")
        span_limit = base_limit if config.spo_max_provisions_per_doc is not None else min(reasoning_total, 16)
        if span_limit < reasoning_total:
            selected_spans = _prioritize_reasoning_spans(
                reasoning_spans,
                doc_title=title,
                quality_family=quality_family,
                limit=span_limit,
            )
        else:
            selected_spans = reasoning_spans[:span_limit]
        llm_settings = SPOLLMSettings(
            task_batch_size=min(base_settings.task_batch_size, 24),
            request_batch_size=min(base_settings.request_batch_size, 2),
            request_batch_chars=min(base_settings.request_batch_chars or 3200, 3200),
            group_timeout_seconds=(
                min(base_settings.group_timeout_seconds, 70.0)
                if base_settings.group_timeout_seconds is not None
                else 70.0
            ),
        )
    elif base_limit < reasoning_total:
        selected_spans = reasoning_spans[:base_limit]

    if not selected_spans and reasoning_spans:
        selected_spans = reasoning_spans[: min(len(reasoning_spans), max(1, base_limit))]

    if not llm_allowed:
        flags.append("deterministic_only_outlier")

    return SPODocRoutingPlan(
        reasoning_spans=selected_spans,
        llm_allowed=llm_allowed,
        llm_settings=llm_settings,
        flags=tuple(flags),
    )


def _group_docs_by_spo_settings(
    docs_by_id: dict[str, NPADocument],
    settings_by_doc: dict[str, SPOLLMSettings],
) -> list[tuple[SPOLLMSettings, list[NPADocument]]]:
    grouped: dict[SPOLLMSettings, list[NPADocument]] = {}
    for doc_id, doc in docs_by_id.items():
        settings = settings_by_doc.get(doc_id)
        if settings is None:
            continue
        grouped.setdefault(settings, []).append(doc)
    ordered = sorted(
        grouped.items(),
        key=lambda item: (
            item[0].request_batch_size,
            item[0].task_batch_size,
            item[0].request_batch_chars or 999999,
            len(item[1]),
        ),
    )
    return ordered


def _accumulate_structure_quality(stats: StructureQualityStats, prov_rows: list[dict]) -> None:
    stats.provision_docs_total += 1
    has_non_full = False
    seen_anchor: set[str] = set()
    has_dup_anchor = False

    for row in prov_rows:
        kind = str(row.get("kind") or "")
        if kind not in {"full_text", "full_chunk"}:
            has_non_full = True
        anchor = str(row.get("anchor_path") or "")
        if anchor:
            if anchor in seen_anchor:
                has_dup_anchor = True
            seen_anchor.add(anchor)

    if not has_non_full:
        stats.full_only_docs += 1
    if has_dup_anchor:
        stats.duplicate_anchor_docs += 1


def _structure_gate_report(stats: StructureQualityStats) -> dict[str, float]:
    docs_total = max(0, stats.provision_docs_total)
    if docs_total <= 0:
        return {
            "provision_docs_total": 0.0,
            "full_only_docs": 0.0,
            "full_only_docs_pct": 0.0,
            "duplicate_anchor_docs": 0.0,
            "duplicate_anchor_rate_pct": 0.0,
        }
    return {
        "provision_docs_total": float(stats.provision_docs_total),
        "full_only_docs": float(stats.full_only_docs),
        "full_only_docs_pct": (stats.full_only_docs * 100.0) / docs_total,
        "duplicate_anchor_docs": float(stats.duplicate_anchor_docs),
        "duplicate_anchor_rate_pct": (stats.duplicate_anchor_docs * 100.0) / docs_total,
    }


def _check_structure_quality_gate(*, config: BatchConfig, stats: StructureQualityStats) -> None:
    if not config.quality_gates_enabled or not config.quality_structure_gate_enabled:
        return
    if stats.provision_docs_total < config.quality_min_provision_docs_for_doc_rate:
        return

    from polisyos.lex.batch.quality_report import QualityGateThresholds, evaluate_quality_gates

    report = _structure_gate_report(stats)
    gate = evaluate_quality_gates(
        report=report,
        thresholds=QualityGateThresholds(
            max_full_only_docs_pct=config.quality_max_full_only_docs_pct,
            max_empty_statement_rows_pct=config.quality_max_empty_statement_rows_pct,
            max_oov_action_rate_pct=config.quality_max_oov_action_rate_pct,
            max_missing_quote_rate_pct=config.quality_max_missing_quote_rate_pct,
            max_duplicate_anchor_rate_pct=config.quality_max_duplicate_anchor_rate_pct,
            max_audit_miss_rate_pct=config.quality_max_audit_miss_rate_pct,
            min_llm_saved_pct=config.quality_min_llm_saved_pct,
            min_provision_docs_for_doc_rate=config.quality_min_provision_docs_for_doc_rate,
            min_spo_rows_for_row_rate=config.quality_min_spo_rows_for_row_rate,
            min_statements_for_statement_rate=config.quality_min_statements_for_statement_rate,
        ),
    )
    structure_failures = [
        check
        for check in gate.failed_checks
        if check in {"full_only_docs_pct", "duplicate_anchor_rate_pct"}
    ]
    if not structure_failures:
        return

    message = (
        "Structure quality gate failed: "
        + ", ".join(structure_failures)
        + f" (full_only={report['full_only_docs_pct']:.2f}%, "
        + f"dup_anchor={report['duplicate_anchor_rate_pct']:.2f}%, "
        + f"docs={int(report['provision_docs_total'])})"
    )
    if config.quality_structure_fail_fast:
        raise RuntimeError(message)
    logger.warning(message)


def _should_extract_spo_from_span(span: ProvisionSpan) -> bool:
    if not span.text.strip():
        return False
    if span.is_fallback_chunk:
        return False
    if (span.route_class or "").strip().lower() == "search_only":
        return False
    if not span.fallback_allowed_for_reasoning:
        return False
    if span.section_role in {"fallback_recall", "table_header", "appendix_section"}:
        return False
    return True


def _extract_provisions_worker(payload: dict) -> list[dict]:
    """Worker function for provision extraction (runs in subprocess)."""
    from polisyos.lex.batch.structurer import extract_provisions

    text = str(payload.get("text", ""))
    spans = extract_provisions(
        text,
        doc_type=str(payload.get("doc_type") or ""),
        doc_name=str(payload.get("doc_name") or ""),
        publisher=str(payload.get("publisher") or ""),
        enable_paragraphs=bool(payload.get("enable_paragraphs", True)),
        fallback_chunk_chars=int(payload.get("fallback_chunk_chars") or 1800),
        fallback_chunk_overlap=int(payload.get("fallback_chunk_overlap") or 200),
    )
    return [
        {
            "kind": s.kind,
            "number": s.number,
            "anchor_path": s.anchor_path,
            "citation_label": s.citation_label,
            "offset_start": s.offset_start,
            "offset_end": s.offset_end,
            "text": s.text,
            "parent_anchor": s.parent_anchor,
            "depth": s.depth,
            "token_est": s.token_est,
            "text_hash": s.text_hash,
            "is_fallback_chunk": s.is_fallback_chunk,
            "struct_kind": s.struct_kind,
            "section_role": s.section_role,
            "lineage_path": s.lineage_path,
            "appendix_id": s.appendix_id,
            "table_id": s.table_id,
            "fallback_allowed_for_reasoning": s.fallback_allowed_for_reasoning,
            "legal_unit_subtype": s.legal_unit_subtype,
            "route_class": s.route_class,
            "empty_spo_retry_eligible": s.empty_spo_retry_eligible,
            "audit_miss_prone": s.audit_miss_prone,
            "reference_bearing": s.reference_bearing,
            "threshold_bearing": s.threshold_bearing,
        }
        for s in spans
    ]


def _chunked(items: list[T], size: int) -> list[list[T]]:
    chunk_size = max(1, size)
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _as_doc_meta(doc: NPADocument) -> dict:
    return {
        "reestr_code": doc.card.reestr_code,
        "name": doc.card.name,
        "doc_type": doc.card.doc_type,
        "doc_type_category": infer_doc_type_category(
            doc_type=doc.card.doc_type,
            doc_name=doc.card.name,
        ),
        "date_acc": doc.card.date_acc,
        "reestr_date": doc.card.reestr_date,
        "status": doc.card.status,
        "publisher": list(doc.card.publisher),
        "number": doc.card.number,
        "reg_date": doc.card.reg_date,
        "reg_number": doc.card.reg_number,
    }


def _statement_category_set(statements: list[Any]) -> list[str]:
    categories: set[str] = set()
    for statement in statements:
        payload = statement
        if hasattr(statement, "model_dump"):
            payload = statement.model_dump(mode="python")
        if not isinstance(payload, dict):
            continue
        action = str(
            payload.get("action_canon")
            or payload.get("predicate")
            or ""
        ).strip().lower()
        norm_type = str(
            payload.get("norm_type_canon")
            or payload.get("norm_type")
            or ""
        ).strip().lower()
        thresholds = payload.get("thresholds")
        if action in {"requires", "delegates"} or norm_type == "obligation":
            categories.add("obligation")
        if action in {"prohibits", "repeals"} or norm_type == "prohibition":
            categories.add("prohibition")
        if action == "sets_threshold" or bool(thresholds):
            categories.add("threshold")
        if (
            action in {"enters_into_force"}
            or str(payload.get("temporal_text_uk") or "").strip()
            or norm_type == "entry_into_force"
        ):
            categories.add("temporal")
        if action in {"amends", "repeals", "approves"}:
            categories.add("reference_amendment")
        if action in {"grants"} or norm_type == "permission":
            categories.add("permission")
    return sorted(categories)


def _write_doc_metadata_manifest(*, output_dir: Path, doc_metadata: dict[str, dict[str, Any]]) -> Path:
    manifests_dir = output_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifests_dir / "doc_metadata.json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "kind": "lex_doc_metadata",
                "documents_total": len(doc_metadata),
                "documents": doc_metadata,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )
    return manifest_path


def _to_provision_spans(prov_dicts: list[dict]) -> list[ProvisionSpan]:
    from polisyos.lex.batch.structurer import ProvisionSpan

    spans: list[ProvisionSpan] = []
    for p in prov_dicts:
        spans.append(
            ProvisionSpan(
                kind=str(p["kind"]),
                number=p.get("number"),
                anchor_path=str(p["anchor_path"]),
                citation_label=str(p["citation_label"]),
                offset_start=int(p["offset_start"]),
                offset_end=int(p["offset_end"]),
                text=str(p["text"]),
                parent_anchor=(
                    str(p.get("parent_anchor"))
                    if p.get("parent_anchor") is not None
                    else None
                ),
                depth=int(p.get("depth") or 0),
                token_est=int(p.get("token_est") or 0),
                text_hash=str(p.get("text_hash") or ""),
                is_fallback_chunk=bool(p.get("is_fallback_chunk", False)),
                struct_kind=str(p.get("struct_kind") or ""),
                section_role=str(p.get("section_role") or ""),
                lineage_path=str(p.get("lineage_path") or p["anchor_path"]),
                appendix_id=(
                    str(p.get("appendix_id"))
                    if p.get("appendix_id") is not None
                    else None
                ),
                table_id=(
                    str(p.get("table_id"))
                    if p.get("table_id") is not None
                    else None
                ),
                legal_unit_subtype=str(p.get("legal_unit_subtype") or ""),
                route_class=str(p.get("route_class") or ""),
                empty_spo_retry_eligible=bool(p.get("empty_spo_retry_eligible", False)),
                audit_miss_prone=bool(p.get("audit_miss_prone", False)),
                reference_bearing=bool(p.get("reference_bearing", False)),
                threshold_bearing=bool(p.get("threshold_bearing", False)),
                fallback_allowed_for_reasoning=bool(
                    p.get(
                        "fallback_allowed_for_reasoning",
                        not bool(p.get("is_fallback_chunk", False)),
                    ),
                ),
            )
        )
    return spans


def _span_signal_payload(span: ProvisionSpan) -> dict[str, Any]:
    return {
        "legal_unit_subtype": span.legal_unit_subtype or "",
        "route_class": span.route_class or "",
        "empty_spo_retry_eligible": bool(span.empty_spo_retry_eligible),
        "audit_miss_prone": bool(span.audit_miss_prone),
        "reference_bearing": bool(span.reference_bearing),
        "threshold_bearing": bool(span.threshold_bearing),
    }


def _build_llm_fallback_row(
    *,
    doc_id: str,
    span: ProvisionSpan,
    deterministic_candidates: list[Any],
    gate_score: float,
    gate_reason_codes: list[str],
    source_tag: str,
) -> dict[str, Any]:
    from polisyos.lex.knowledge.types import SPOExtractionResult

    result = SPOExtractionResult(
        doc_id=doc_id,
        provision_anchor=span.anchor_path,
        provision_citation=span.citation_label,
        statements=deterministic_candidates,
        prompt_version="deterministic_spo_v1",
        extract_passes=0,
        low_confidence=True,
        low_confidence_reasons=["llm_fallback_pending"],
        extraction_source=source_tag,
        gate_score=gate_score,
        gate_reason_codes=gate_reason_codes,
        **_span_signal_payload(span),
    )
    return result.model_dump(mode="json")


def _write_jsonl_rows(path: str, rows: list[dict], *, append: bool) -> None:
    from pathlib import Path

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(out_path, mode, encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _doc_content_hash(text: str) -> str:
    """Compute a short content hash for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _has_jsonl_rows(path: str) -> bool:
    from pathlib import Path

    root = Path(path)
    return root.exists() and any(root.glob("**/*.jsonl"))


def _active_spo_results_dir(config: BatchConfig) -> str:
    if _has_jsonl_rows(str(config.grounded_spo_dir)):
        return str(config.grounded_spo_dir)
    return str(config.spo_results_dir)


def _active_references_dir(config: BatchConfig) -> str:
    if _has_jsonl_rows(str(config.resolved_references_dir)):
        return str(config.resolved_references_dir)
    return str(config.references_dir)


def _write_doc_domain(*, domains_dir: str, doc_id: str, payload: dict) -> None:
    from pathlib import Path

    out_path = Path(domains_dir) / doc_id[:2].lower() / f"{doc_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


async def _process_structure_chunk(
    *,
    config: BatchConfig,
    progress: ProgressTracker,
    docs_chunk: list[NPADocument],
) -> tuple[dict[str, list[dict]], int, StructureQualityStats]:
    """Extract provisions for one document chunk and persist to disk."""
    docs_to_process: list[NPADocument] = []
    doc_meta_by_id: dict[str, dict[str, Any]] = {}
    for d in docs_chunk:
        doc_hash = _doc_content_hash(d.text)
        if config.resume and progress.is_done_with_hash(d.card.doc_id, "structured", doc_hash):
            continue
        # Even without --resume, skip if provisions file exists and hash matches.
        from polisyos.lex.batch.provisions_io import provision_file_path

        if provision_file_path(config.provisions_dir, d.card.doc_id).exists():
            if progress.is_done_with_hash(d.card.doc_id, "structured", doc_hash):
                continue
        docs_to_process.append(d)
        doc_meta_by_id[d.card.doc_id] = _as_doc_meta(d)

    if not docs_to_process:
        return {}, 0, StructureQualityStats()

    workers = min(config.structure_workers, len(docs_to_process))
    provisions_by_doc: dict[str, list[dict]] = {}
    total_provisions = 0
    structure_stats = StructureQualityStats()
    doc_text_by_id = {d.card.doc_id: d.text for d in docs_to_process}
    executor_cls: type[ProcessPoolExecutor] | type[ThreadPoolExecutor] = ProcessPoolExecutor
    main_file = str(getattr(sys.modules.get("__main__"), "__file__", "") or "")
    if not main_file or "<stdin>" in main_file:
        executor_cls = ThreadPoolExecutor
        logger.info(
            "Using thread pool for structure extraction because __main__.__file__ is %r",
            main_file or None,
        )
        pool = executor_cls(max_workers=max(1, workers))
    else:
        try:
            pool = executor_cls(max_workers=max(1, workers))
        except (PermissionError, OSError, NotImplementedError, ValueError) as exc:
            logger.warning(
                "Process pool unavailable for structure extraction ({}); falling back to thread pool",
                exc,
            )
            executor_cls = ThreadPoolExecutor
            pool = executor_cls(max_workers=max(1, workers))

    with pool:
        futures = {
            pool.submit(
                _extract_provisions_worker,
                {
                    "text": doc.text,
                    "doc_type": doc.card.doc_type,
                    "doc_name": doc.card.name,
                    "publisher": doc.card.publisher,
                    "enable_paragraphs": config.structure_enable_paragraphs,
                    "fallback_chunk_chars": config.structure_fallback_chunk_chars,
                    "fallback_chunk_overlap": config.structure_fallback_chunk_overlap,
                },
            ): doc.card.doc_id
            for doc in docs_to_process
        }
        for future in as_completed(futures):
            doc_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # pragma: no cover - worker crash is environment-specific
                logger.warning("Structure extraction failed for {}: {}", doc_id, exc)
                continue
            doc_type_category = str(doc_meta_by_id.get(doc_id, {}).get("doc_type_category") or "other")
            for row in result:
                if not isinstance(row, dict):
                    continue
                row.setdefault("doc_type_category", doc_type_category)
            provisions_by_doc[doc_id] = result
            total_provisions += len(result)
            _accumulate_structure_quality(structure_stats, result)
            write_provisions(
                provisions_dir=config.provisions_dir,
                doc_id=doc_id,
                provisions=result,
            )
            doc_hash = _doc_content_hash(doc_text_by_id[doc_id])
            progress.mark_done(
                doc_id, "structured",
                stats={"provisions": len(result)},
                content_hash=doc_hash,
            )
    return provisions_by_doc, total_provisions, structure_stats


async def _process_spo_chunk(
    *,
    config: BatchConfig,
    progress: ProgressTracker,
    docs_chunk: list[NPADocument],
    structure_cache: dict[str, list[dict]],
    spo_client: GonkaClient | None,
    gate_runtime: GateRuntime,
    gate_stats: LLMGateStats,
) -> int:
    """Run SPO extraction for one document chunk with deterministic-first gating."""
    from polisyos.lex.batch.deterministic_spo import extract_deterministic_spo, extract_family_retry_spo
    from polisyos.lex.batch.domain_classifier import classify_domains
    from polisyos.lex.batch.llm_gate import build_gate_features, decide_route
    from polisyos.lex.batch.provisions_io import _shard_prefix
    from polisyos.lex.batch.reference_extractor import extract_references
    from polisyos.lex.batch.rule_classifier import classify_provision
    from polisyos.lex.batch.spo_extractor import extract_spo_for_documents
    from polisyos.lex.knowledge.types import SPOCandidate, SPOExtractionResult

    llm_available = spo_client is not None
    docs_for_llm: dict[str, NPADocument] = {}
    docs_for_audit_llm: dict[str, NPADocument] = {}
    spans_by_doc_llm: dict[str, list[ProvisionSpan]] = {}
    spans_by_doc_audit: dict[str, list[ProvisionSpan]] = {}
    llm_settings_by_doc: dict[str, SPOLLMSettings] = {}
    audit_settings_by_doc: dict[str, SPOLLMSettings] = {}
    gate_meta_by_anchor: dict[str, dict[str, dict[str, Any]]] = {}
    gate_meta_by_anchor_audit: dict[str, dict[str, dict[str, Any]]] = {}
    fallback_rows_by_anchor: dict[str, dict[str, dict[str, Any]]] = {}
    fallback_rows_by_anchor_audit: dict[str, dict[str, dict[str, Any]]] = {}
    audit_baseline: dict[str, dict[str, dict[str, Any]]] = {}
    audit_sampler = StratifiedAuditSampler(base_rate=config.llm_gate_audit_sample_rate)
    docs_to_mark_done: set[str] = set()

    # --- Provision deduplication across all docs in this chunk ---
    # Maps text_hash → (doc_id, anchor_path) of the first occurrence.
    # Duplicate provisions get their SPO results cloned from the first.
    dedup_map: dict[str, tuple[str, str]] = {}  # text_hash → (doc_id, anchor)
    dedup_pending: dict[str, list[tuple[str, ProvisionSpan]]] = {}  # text_hash → [(doc_id, span), ...]

    total_spo = 0
    for doc in docs_chunk:
        doc_id = doc.card.doc_id
        doc_hash = _doc_content_hash(doc.text)
        if config.resume and progress.is_done_with_hash(doc_id, "spo_extracted", doc_hash):
            continue

        prov_rows = structure_cache.get(doc_id)
        if prov_rows is None:
            prov_rows = read_provisions(provisions_dir=config.provisions_dir, doc_id=doc_id)
        if not prov_rows:
            progress.mark_done(doc_id, "spo_extracted", content_hash=doc_hash)
            continue

        spans = _to_provision_spans(prov_rows)
        if not spans:
            progress.mark_done(doc_id, "spo_extracted", content_hash=doc_hash)
            continue

        doc_type_category = infer_doc_type_category(
            doc_type=doc.card.doc_type,
            doc_name=doc.card.name,
        )
        quality_family = classify_doc_family(
            doc_type=doc.card.doc_type,
            doc_name=doc.card.name,
            doc_type_category_value=doc_type_category,
            provision_rows=prov_rows,
        )

        reasoning_spans = [span for span in spans if _should_extract_spo_from_span(span)]
        routing_plan = _build_spo_doc_routing_plan(
            doc=doc,
            prov_rows=prov_rows,
            reasoning_spans=reasoning_spans,
            quality_family=quality_family,
            config=config,
        )
        reasoning_spans = routing_plan.reasoning_spans
        doc_llm_available = llm_available and routing_plan.llm_allowed
        llm_settings_by_doc[doc_id] = routing_plan.llm_settings
        audit_settings_by_doc[doc_id] = routing_plan.llm_settings

        # Reset per-doc SPO output when not resuming.
        spo_path = config.spo_results_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"
        if not config.resume and spo_path.exists():
            spo_path.unlink()

        # Deterministic reference graph.
        if config.extract_references_enabled:
            reference_rows: list[dict] = []
            for span in spans:
                for hit in extract_references(
                    text=span.text,
                    doc_id=doc_id,
                    anchor_path=span.anchor_path,
                ):
                    reference_rows.append(hit.as_dict())
            if reference_rows:
                _write_jsonl_rows(
                    str(config.references_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"),
                    reference_rows,
                    append=False,
                )

        # Deterministic domain classification.
        if config.extract_domains_enabled:
            domain_payload = classify_domains(
                text=f"{doc.card.name}\n{doc.text}",
                doc_id=doc_id,
            ).as_dict()
            _write_doc_domain(
                domains_dir=str(config.domains_dir),
                doc_id=doc_id,
                payload=domain_payload,
            )

        if len(reasoning_spans) < len(spans):
            logger.debug(
                "SPO reasoning filter skipped {} search-only provisions for {}",
                len(spans) - len(reasoning_spans),
                doc_id,
            )
        if routing_plan.flags:
            logger.info(
                "SPO routing for {}: flags={} total={} reasoning={} selected={} llm_allowed={} batch={}/{}/{} timeout={}",
                doc_id,
                ",".join(routing_plan.flags),
                len(spans),
                len([span for span in spans if _should_extract_spo_from_span(span)]),
                len(reasoning_spans),
                doc_llm_available,
                routing_plan.llm_settings.task_batch_size,
                routing_plan.llm_settings.request_batch_size,
                routing_plan.llm_settings.request_batch_chars,
                routing_plan.llm_settings.group_timeout_seconds,
            )

        if not reasoning_spans:
            docs_to_mark_done.add(doc_id)
            continue

        # --- Template-based full-document extraction (before per-provision loop) ---
        from polisyos.lex.batch.template_extractor import try_template_extraction

        template_match = try_template_extraction(
            doc_id=doc_id,
            doc_type=doc.card.doc_type,
            publisher=doc.card.publisher,
            doc_title=doc.card.name,
            provisions=[
                {"text": s.text, "anchor_path": s.anchor_path, "citation_label": s.citation_label}
                for s in reasoning_spans
            ],
        )
        if template_match.matched and template_match.results:
            template_rows: list[dict] = []
            span_by_anchor = {span.anchor_path: span for span in reasoning_spans}
            for tmpl_result in template_match.results:
                row = tmpl_result.model_dump(mode="json")
                span = span_by_anchor.get(str(row.get("provision_anchor") or ""))
                if span is not None:
                    row.update(_span_signal_payload(span))
                template_rows.append(row)
                total_spo += len(tmpl_result.statements)
                gate_stats.auto_by_code_total += len(tmpl_result.statements)
                gate_stats.provisions_seen += 1
            _write_jsonl_rows(str(spo_path), template_rows, append=True)
            docs_to_mark_done.add(doc_id)
            continue

        local_rows: list[dict] = []
        docs_to_mark_done.add(doc_id)
        for span in reasoning_spans:
            gate_stats.provisions_seen += 1

            # --- Provision dedup by text_hash ---
            th = span.text_hash
            if th and th in dedup_map:
                # This text was already processed; defer result cloning.
                dedup_pending.setdefault(th, []).append((doc_id, span))
                gate_stats.dedup_reused_total += 1
                continue
            if th:
                dedup_map[th] = (doc_id, span.anchor_path)

            reference_hits = (
                extract_references(
                    text=span.text,
                    doc_id=doc_id,
                    anchor_path=span.anchor_path,
                )
                if config.extract_references_enabled
                else []
            )

            if config.spo_skip_trivial:
                cls = classify_provision(span.text, span.citation_label, doc.card.name)
                if cls.action == "skip":
                    gate_stats.skipped_total += 1
                    continue
                if cls.action == "auto" and cls.auto_statements:
                    candidates: list[SPOCandidate] = []
                    for st in cls.auto_statements:
                        try:
                            candidates.append(
                                SPOCandidate.model_validate(
                                    {
                                        "subject_en": st.get("subject_uk", ""),
                                        "subject_uk": st.get("subject_uk", ""),
                                        "predicate": st.get("predicate", "requires"),
                                        "object_en": st.get("object_uk", ""),
                                        "object_uk": st.get("object_uk", ""),
                                        "fact_text": st.get("fact_text", ""),
                                        "confidence": float(st.get("confidence", "0.9")),
                                        "norm_type": st.get("norm_type", "obligation"),
                                        "action_raw": st.get("predicate", "requires"),
                                        "action_canon": st.get("predicate", "requires"),
                                        "norm_type_raw": st.get("norm_type", "obligation"),
                                        "norm_type_canon": st.get("norm_type", "obligation"),
                                        "source_quote_uk": st.get("source_quote_uk", ""),
                                    }
                                )
                            )
                        except Exception:
                            logger.debug("Failed to validate SPOCandidate from rule classifier for doc {}", doc_id)
                            continue
                    if candidates:
                        result = SPOExtractionResult(
                            doc_id=doc_id,
                            provision_anchor=span.anchor_path,
                            provision_citation=span.citation_label,
                            statements=candidates,
                            prompt_version="rule_classifier_v1",
                            extract_passes=0,
                            extraction_source="rule_auto",
                            gate_score=0.0,
                            gate_reason_codes=["rule_classifier_auto"],
                            **_span_signal_payload(span),
                        )
                        local_rows.append(result.model_dump(mode="json"))
                        total_spo += len(candidates)
                        gate_stats.auto_by_code_total += len(candidates)
                    continue

            deterministic = extract_deterministic_spo(
                text=span.text,
                citation_label=span.citation_label,
                doc_title=doc.card.name,
                legal_unit_subtype=span.legal_unit_subtype,
                quality_family=quality_family,
                reference_bearing=span.reference_bearing,
                threshold_bearing=span.threshold_bearing,
            )
            if not deterministic.candidates and quality_family in {"law", "appendix_heavy", "treaty_protocol"}:
                retry_deterministic = extract_family_retry_spo(
                    text=span.text,
                    citation_label=span.citation_label,
                    doc_title=doc.card.name,
                    quality_family=quality_family,
                    struct_kind=span.struct_kind or span.kind,
                    legal_unit_subtype=span.legal_unit_subtype,
                )
                if retry_deterministic.candidates:
                    deterministic = retry_deterministic

            gate_stats.llm_candidate_total += 1
            llm_share = gate_stats.llm_sent_total / max(1, gate_stats.llm_candidate_total)
            features = build_gate_features(
                text=span.text,
                deterministic_confidence=deterministic.confidence,
                reference_count=len(reference_hits),
                fallback_chunk=span.is_fallback_chunk,
                publisher=" ".join(doc.card.publisher) if doc.card.publisher else "",
                doc_title=doc.card.name,
                citation_label=span.citation_label,
                struct_kind=span.struct_kind or span.kind,
                section_role=span.section_role,
                doc_type_category=doc_type_category,
                legal_unit_subtype=span.legal_unit_subtype,
                route_class=span.route_class,
                empty_spo_retry_eligible=span.empty_spo_retry_eligible,
                audit_miss_prone=span.audit_miss_prone,
                reference_bearing=span.reference_bearing,
                threshold_bearing=span.threshold_bearing,
            )
            decision = decide_route(
                gate_enabled=config.llm_gate_enabled,
                runtime=gate_runtime,
                llm_available=doc_llm_available,
                llm_share=llm_share,
                deterministic_confidence=deterministic.confidence,
                auto_conf_threshold=config.llm_gate_auto_conf_threshold,
                min_score_force_llm=config.llm_gate_min_score_force_llm,
                features=features,
                audit_sample_rate=config.llm_gate_audit_sample_rate,
                audit_seed=f"{doc_id}:{span.anchor_path}",
            )
            reason_codes = sorted(set(decision.reason_codes + deterministic.reason_codes))
            forced_audit_sample = False
            if (
                decision.route not in {"llm", "audit_llm"}
                and audit_sampler.should_force_sample(
                    family=quality_family,
                    subtype=span.legal_unit_subtype,
                    route_class=span.route_class,
                    llm_available=doc_llm_available,
                )
            ):
                decision = type(decision)(
                    route="audit_llm",
                    score=decision.score,
                    reason_codes=sorted(set(reason_codes + ["stratified_audit_quota"])),
                )
                reason_codes = list(decision.reason_codes)
                forced_audit_sample = True

            if decision.route == "auto":
                result = SPOExtractionResult(
                    doc_id=doc_id,
                    provision_anchor=span.anchor_path,
                    provision_citation=span.citation_label,
                    statements=deterministic.candidates,
                    prompt_version="deterministic_spo_v1",
                    extract_passes=0,
                    low_confidence=deterministic.confidence < config.llm_gate_auto_conf_threshold,
                    extraction_source="rule_auto",
                    gate_score=decision.score,
                    gate_reason_codes=reason_codes,
                    **_span_signal_payload(span),
                )
                local_rows.append(result.model_dump(mode="json"))
                total_spo += len(deterministic.candidates)
                gate_stats.auto_by_code_total += len(deterministic.candidates)
                continue

            if decision.route == "llm" and doc_llm_available:
                docs_for_llm[doc_id] = doc
                spans_by_doc_llm.setdefault(doc_id, []).append(span)
                gate_meta_by_anchor.setdefault(doc_id, {})[span.anchor_path] = {
                    "gate_score": float(decision.score),
                    "gate_reason_codes": list(reason_codes),
                    **_span_signal_payload(span),
                }
                fallback_rows_by_anchor.setdefault(doc_id, {})[span.anchor_path] = _build_llm_fallback_row(
                    doc_id=doc_id,
                    span=span,
                    deterministic_candidates=deterministic.candidates,
                    gate_score=decision.score,
                    gate_reason_codes=reason_codes,
                    source_tag="llm_timeout_fallback",
                )
                gate_stats.llm_sent_total += 1
                continue

            if decision.route == "audit_llm" and doc_llm_available:
                audit_sampler.register_sample(
                    family=quality_family,
                    subtype=span.legal_unit_subtype,
                    route_class=span.route_class,
                    forced=forced_audit_sample,
                )
                docs_for_audit_llm[doc_id] = doc
                spans_by_doc_audit.setdefault(doc_id, []).append(span)
                gate_meta_by_anchor_audit.setdefault(doc_id, {})[span.anchor_path] = {
                    "gate_score": float(decision.score),
                    "gate_reason_codes": list(reason_codes),
                    **_span_signal_payload(span),
                }
                fallback_rows_by_anchor_audit.setdefault(doc_id, {})[span.anchor_path] = _build_llm_fallback_row(
                    doc_id=doc_id,
                    span=span,
                    deterministic_candidates=deterministic.candidates,
                    gate_score=decision.score,
                    gate_reason_codes=reason_codes,
                    source_tag="audit_llm_timeout_fallback",
                )
                audit_baseline.setdefault(doc_id, {})[span.anchor_path] = {
                    "baseline_count": len(deterministic.candidates),
                    "baseline_categories": _statement_category_set(deterministic.candidates),
                    "doc_type_category": doc_type_category,
                    "quality_family": quality_family,
                    "gate_reason_codes": reason_codes,
                    "search_only_structure": not span.fallback_allowed_for_reasoning,
                    "empty_spo_only": len(deterministic.candidates) == 0,
                    "section_role": span.section_role,
                    "struct_kind": span.struct_kind or span.kind,
                    **_span_signal_payload(span),
                }
                gate_stats.audit_sample_total += 1
                gate_stats.llm_sent_total += 1
                continue

            # deferred: keep deterministic rows but mark provenance and low confidence.
            result = SPOExtractionResult(
                doc_id=doc_id,
                provision_anchor=span.anchor_path,
                provision_citation=span.citation_label,
                statements=deterministic.candidates,
                prompt_version="deterministic_spo_v1",
                extract_passes=0,
                low_confidence=True,
                low_confidence_reasons=["deferred_no_llm"],
                extraction_source="deferred",
                gate_score=decision.score,
                gate_reason_codes=reason_codes,
                **_span_signal_payload(span),
            )
            local_rows.append(result.model_dump(mode="json"))
            total_spo += len(deterministic.candidates)
            gate_stats.deferred_total += 1

        if local_rows:
            _write_jsonl_rows(str(spo_path), local_rows, append=True)

    failed_doc_ids_total: set[str] = set()
    if llm_available and docs_for_llm:
        for llm_settings, llm_docs in _group_docs_by_spo_settings(docs_for_llm, llm_settings_by_doc):
            for docs_batch in _chunked(llm_docs, config.spo_batch_docs):
                batch_spo, failed_ids = await extract_spo_for_documents(
                    spo_client,
                    docs_batch,
                    spans_by_doc_llm,
                    results_dir=config.spo_results_dir,
                    task_batch_size=llm_settings.task_batch_size,
                    request_batch_size=llm_settings.request_batch_size,
                    request_batch_chars=llm_settings.request_batch_chars,
                    group_timeout_seconds=llm_settings.group_timeout_seconds,
                    verify_mode=config.spo_verify_mode,
                    extract_mode=config.spo_extract_mode,
                    overwrite_existing=False,
                    extraction_source="llm",
                    gate_meta_by_anchor=gate_meta_by_anchor,
                    fallback_rows_by_anchor=fallback_rows_by_anchor,
                )
                total_spo += batch_spo
                failed_doc_ids_total.update(failed_ids)

    if llm_available and docs_for_audit_llm:
        audit_rows: list[dict] = []
        chunk_audit_miss = 0
        chunk_audit_total = 0

        def _audit_sink(row: dict[str, object]) -> None:
            nonlocal chunk_audit_miss, chunk_audit_total
            doc_id = str(row.get("doc_id", ""))
            anchor = str(row.get("provision_anchor", ""))
            statements = row.get("statements")
            llm_count = len(statements) if isinstance(statements, list) else 0
            baseline_meta = audit_baseline.get(doc_id, {}).get(anchor, {})
            baseline_count = int(baseline_meta.get("baseline_count", 0) or 0)
            miss = llm_count > baseline_count
            llm_categories = _statement_category_set(statements if isinstance(statements, list) else [])
            baseline_categories = {
                str(item)
                for item in baseline_meta.get("baseline_categories", [])
                if str(item).strip()
            }
            miss_categories = sorted(set(llm_categories) - baseline_categories)
            if miss and not miss_categories:
                miss_categories = ["additional_statement"]
            chunk_audit_total += 1
            if miss:
                chunk_audit_miss += 1
            audit_rows.append(
                {
                    "doc_id": doc_id,
                    "provision_anchor": anchor,
                    "baseline_count": baseline_count,
                    "llm_count": llm_count,
                    "miss": miss,
                    "miss_categories": miss_categories,
                    "baseline_categories": sorted(baseline_categories),
                    "llm_categories": llm_categories,
                    "empty_spo_only": bool(baseline_meta.get("empty_spo_only", False)),
                    "llm_timeout_fallback": str(row.get("extraction_source") or "").endswith("timeout_fallback"),
                    "doc_type_category": str(baseline_meta.get("doc_type_category") or ""),
                    "quality_family": str(baseline_meta.get("quality_family") or "other"),
                    "gate_reason_codes": list(baseline_meta.get("gate_reason_codes") or []),
                    "search_only_structure": bool(baseline_meta.get("search_only_structure", False)),
                    "struct_kind": str(baseline_meta.get("struct_kind") or ""),
                    "section_role": str(baseline_meta.get("section_role") or ""),
                    "legal_unit_subtype": str(baseline_meta.get("legal_unit_subtype") or ""),
                    "route_class": str(baseline_meta.get("route_class") or ""),
                    "empty_spo_retry_eligible": bool(baseline_meta.get("empty_spo_retry_eligible", False)),
                    "audit_miss_prone": bool(baseline_meta.get("audit_miss_prone", False)),
                    "reference_bearing": bool(baseline_meta.get("reference_bearing", False)),
                    "threshold_bearing": bool(baseline_meta.get("threshold_bearing", False)),
                }
            )

        for audit_settings, audit_docs in _group_docs_by_spo_settings(docs_for_audit_llm, audit_settings_by_doc):
            for docs_batch in _chunked(audit_docs, config.spo_batch_docs):
                batch_spo, failed_ids = await extract_spo_for_documents(
                    spo_client,
                    docs_batch,
                    spans_by_doc_audit,
                    results_dir=config.spo_results_dir,
                    task_batch_size=audit_settings.task_batch_size,
                    request_batch_size=audit_settings.request_batch_size,
                    request_batch_chars=audit_settings.request_batch_chars,
                    group_timeout_seconds=audit_settings.group_timeout_seconds,
                    verify_mode=config.spo_verify_mode,
                    extract_mode=config.spo_extract_mode,
                    overwrite_existing=False,
                    extraction_source="audit_llm",
                    gate_meta_by_anchor=gate_meta_by_anchor_audit,
                    fallback_rows_by_anchor=fallback_rows_by_anchor_audit,
                    result_sink=_audit_sink,
                )
                total_spo += batch_spo
                failed_doc_ids_total.update(failed_ids)

        if audit_rows:
            _write_jsonl_rows(str(config.llm_gate_audit_path), audit_rows, append=True)
        gate_stats.audit_miss_total += chunk_audit_miss
        if chunk_audit_total > 0:
            miss_rate = (chunk_audit_miss * 100.0) / chunk_audit_total
            if gate_runtime.register_audit_miss_rate(miss_rate):
                logger.warning(
                    "LLM gate circuit breaker triggered (audit miss rate %.2f%%). Safe-pass enabled.",
                    miss_rate,
                )
            gate_stats.circuit_breaker_hits = gate_runtime.circuit_breaker_hits

    # --- Resolve dedup pending: clone SPO results for duplicate provisions ---
    if dedup_pending:
        from polisyos.lex.batch.provisions_io import _shard_prefix as _sp

        for text_hash, duplicates in dedup_pending.items():
            orig_doc_id, orig_anchor = dedup_map.get(text_hash, ("", ""))
            if not orig_doc_id:
                continue
            # Read the original SPO result for this provision.
            orig_spo_path = config.spo_results_dir / _sp(orig_doc_id) / f"{orig_doc_id}.jsonl"
            orig_row: dict | None = None
            if orig_spo_path.exists():
                with open(orig_spo_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        row = json.loads(line)
                        if row.get("provision_anchor") == orig_anchor:
                            orig_row = row
                            break
            if orig_row is None:
                continue
            # Clone for each duplicate.
            for dup_doc_id, dup_span in duplicates:
                cloned = dict(orig_row)
                cloned["doc_id"] = dup_doc_id
                cloned["provision_anchor"] = dup_span.anchor_path
                cloned["provision_citation"] = dup_span.citation_label
                cloned["extraction_source"] = "dedup_clone"
                dup_spo_path = config.spo_results_dir / _sp(dup_doc_id) / f"{dup_doc_id}.jsonl"
                _write_jsonl_rows(str(dup_spo_path), [cloned], append=True)
                stmts = cloned.get("statements", [])
                total_spo += len(stmts) if isinstance(stmts, list) else 0

        if gate_stats.dedup_reused_total > 0:
            logger.info(
                "Provision dedup: {} provisions reused from {} unique texts",
                gate_stats.dedup_reused_total,
                len(dedup_map),
            )

    for doc_id in docs_to_mark_done:
        if doc_id not in failed_doc_ids_total:
            doc_hash = _doc_content_hash(next(
                (d.text for d in docs_chunk if d.card.doc_id == doc_id), "",
            ))
            progress.mark_done(doc_id, "spo_extracted", content_hash=doc_hash)

    logger.info(
        "LLM gate chunk: seen={} auto={} llm_sent={} deferred={} skipped={} dedup={} audit_miss_rate={:.2f}%",
        gate_stats.provisions_seen,
        gate_stats.auto_by_code_total,
        gate_stats.llm_sent_total,
        gate_stats.deferred_total,
        gate_stats.skipped_total,
        gate_stats.dedup_reused_total,
        gate_stats.audit_miss_rate_pct,
    )
    return total_spo


async def run_batch_pipeline(config: BatchConfig) -> PipelineStats:
    """Run configured stages sequentially with bounded memory."""
    t0 = time.monotonic()
    stats = PipelineStats()
    progress = ProgressTracker(config.progress_path)

    from polisyos.lex.batch.xml_parser import iter_documents

    doc_metadata: dict[str, dict] = {}
    needs_document_stream = bool({"parse", "structure", "spo", "resolve_refs", "graph"} & set(config.stages))
    if needs_document_stream:
        parse_start = time.monotonic()
        structure_elapsed = 0.0
        spo_elapsed = 0.0
        structure_quality_stats = StructureQualityStats()

        logger.info("=== Streaming documents ===")
        if config.sharded:
            logger.info(
                "Sharding enabled: {} ({}/{})",
                config.shard_slug,
                config.shard_index + 1,
                config.shard_count,
            )
        run_structure = "structure" in config.stages
        run_spo = "spo" in config.stages
        llm_keys = [str(key).strip() for key in config.gonka_api_keys if str(key).strip()]
        llm_available = bool(llm_keys or config.gonka_api_key)
        if run_spo and not llm_available:
            logger.warning("GONKA_API_KEY not set — running deterministic SPO only (no LLM calls).")

        spo_client = None
        if run_spo and llm_available:
            from polisyos.lex.batch.spo_extractor import GonkaClient, GonkaClientPool

            if len(llm_keys) > 1:
                spo_client = GonkaClientPool(
                    api_keys=llm_keys,
                    base_url=config.gonka_base_url,
                    model=config.llm_model,
                    disable_json_mode=config.gonka_disable_json_mode,
                    max_concurrent=config.max_concurrent_llm,
                    rate_limit_rps=config.rate_limit_rps,
                    temperature=config.llm_temperature,
                    max_retries=config.max_retries,
                )
                logger.info(
                    "Using Gonka key pool: {} keys, approx total concurrency={}, approx total rps={:.2f}",
                    len(llm_keys),
                    len(llm_keys) * config.max_concurrent_llm,
                    len(llm_keys) * config.rate_limit_rps,
                )
            else:
                spo_client = GonkaClient(
                    api_key=config.gonka_api_key,
                    base_url=config.gonka_base_url,
                    model=config.llm_model,
                    disable_json_mode=config.gonka_disable_json_mode,
                    max_concurrent=config.max_concurrent_llm,
                    rate_limit_rps=config.rate_limit_rps,
                    temperature=config.llm_temperature,
                    max_retries=config.max_retries,
                )
            if config.spo_cache_enabled:
                from polisyos.lex.batch.spo_cache import SPOCache

                cache_path = config.spo_cache_path or (config.output_dir / "spo_cache.sqlite")
                spo_response_cache = SPOCache(cache_path)
                spo_client.set_cache(spo_response_cache)
                logger.info("SPO response cache enabled: {}", cache_path)
            else:
                spo_response_cache = None

            logger.info(
                "SPO extract_mode={}, verify_mode={}, skip_trivial={}, gate_mode={}",
                config.spo_extract_mode,
                config.spo_verify_mode,
                config.spo_skip_trivial,
                config.llm_gate_mode,
            )
        if run_spo:
            from polisyos.lex.batch.llm_gate import GateRuntime

            gate_runtime = GateRuntime(
                threshold=config.llm_gate_threshold,
                mode=config.llm_gate_mode,
                max_share=config.llm_gate_max_share,
                audit_max_miss_rate_pct=config.llm_gate_audit_max_miss_rate_pct,
                circuit_breaker_enabled=config.llm_gate_circuit_breaker_enabled,
            )
            gate_stats = LLMGateStats()
        else:
            gate_runtime = None
            gate_stats = LLMGateStats()

        # --max-docs: determine which progress stage to count "new" docs against
        _target_stage: str | None = None
        if run_spo:
            _target_stage = "spo_extracted"
        elif run_structure:
            _target_stage = "structured"
        new_docs_count = 0

        chunk: list[NPADocument] = []
        if spo_client is not None:
            await spo_client.__aenter__()
        try:
            for doc in iter_documents(
                config.cards_path,
                config.texts_path,
                status_filter=set(config.status_filter) if config.status_filter else None,
                type_filter=set(config.type_filter) if config.type_filter else None,
                doc_id_filter=set(config.doc_id_filter) if config.doc_id_filter else None,
            ):
                if not config.is_doc_in_shard(doc.card.doc_id):
                    continue

                # --max-docs: count only docs that still need work
                is_new = _target_stage is None or not progress.is_done(
                    doc.card.doc_id, _target_stage,
                )
                if is_new:
                    new_docs_count += 1

                stats.total_docs += 1
                doc_metadata[doc.card.doc_id] = _as_doc_meta(doc)
                chunk.append(doc)

                # Flush chunk when full OR when --max-docs limit reached
                reached_limit = (
                    config.max_docs is not None and new_docs_count >= config.max_docs
                )
                if not reached_limit and len(chunk) < max(1, config.xml_parse_chunk):
                    continue

                if run_structure:
                    st = time.monotonic()
                    structure_cache, added, chunk_structure_stats = await _process_structure_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                    )
                    stats.total_provisions += added
                    structure_quality_stats.provision_docs_total += chunk_structure_stats.provision_docs_total
                    structure_quality_stats.full_only_docs += chunk_structure_stats.full_only_docs
                    structure_quality_stats.duplicate_anchor_docs += chunk_structure_stats.duplicate_anchor_docs
                    structure_elapsed += time.monotonic() - st
                    _check_structure_quality_gate(
                        config=config,
                        stats=structure_quality_stats,
                    )
                else:
                    structure_cache = {}

                if run_spo:
                    st = time.monotonic()
                    stats.total_spo += await _process_spo_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                        structure_cache=structure_cache,
                        spo_client=spo_client,
                        gate_runtime=gate_runtime,
                        gate_stats=gate_stats,
                    )
                    spo_elapsed += time.monotonic() - st
                chunk.clear()

                if reached_limit:
                    logger.info(
                        "Reached --max-docs limit ({} new documents). Stopping.",
                        config.max_docs,
                    )
                    break

            if chunk:
                if run_structure:
                    st = time.monotonic()
                    structure_cache, added, chunk_structure_stats = await _process_structure_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                    )
                    stats.total_provisions += added
                    structure_quality_stats.provision_docs_total += chunk_structure_stats.provision_docs_total
                    structure_quality_stats.full_only_docs += chunk_structure_stats.full_only_docs
                    structure_quality_stats.duplicate_anchor_docs += chunk_structure_stats.duplicate_anchor_docs
                    structure_elapsed += time.monotonic() - st
                    _check_structure_quality_gate(
                        config=config,
                        stats=structure_quality_stats,
                    )
                else:
                    structure_cache = {}

                if run_spo:
                    st = time.monotonic()
                    stats.total_spo += await _process_spo_chunk(
                        config=config,
                        progress=progress,
                        docs_chunk=chunk,
                        structure_cache=structure_cache,
                        spo_client=spo_client,
                        gate_runtime=gate_runtime,
                        gate_stats=gate_stats,
                    )
                    spo_elapsed += time.monotonic() - st
                chunk.clear()
        finally:
            if spo_client is not None:
                await spo_client.__aexit__(None, None, None)

        if "parse" in config.stages:
            stats.stage_times["parse"] = time.monotonic() - parse_start
        if "structure" in config.stages:
            stats.stage_times["structure"] = structure_elapsed
        if "spo" in config.stages:
            stats.stage_times["spo"] = spo_elapsed
            stats.llm_gate_metrics = {
                "provisions_seen": gate_stats.provisions_seen,
                "skipped_total": gate_stats.skipped_total,
                "auto_by_code_total": gate_stats.auto_by_code_total,
                "llm_candidate_total": gate_stats.llm_candidate_total,
                "llm_sent_total": gate_stats.llm_sent_total,
                "deferred_total": gate_stats.deferred_total,
                "dedup_reused_total": gate_stats.dedup_reused_total,
                "llm_saved_pct": round(gate_stats.llm_saved_pct, 3),
                "audit_sample_total": gate_stats.audit_sample_total,
                "audit_miss_total": gate_stats.audit_miss_total,
                "audit_miss_rate_pct": round(gate_stats.audit_miss_rate_pct, 3),
                "circuit_breaker_hits": gate_stats.circuit_breaker_hits,
                "safe_pass_active": int(bool(gate_runtime.safe_pass_active)) if gate_runtime else 0,
            }
            (config.output_dir / "manifests").mkdir(parents=True, exist_ok=True)
            with open(config.llm_gate_manifest_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "kind": "stage",
                        "stage": "llm_gate",
                        "mode": config.llm_gate_mode,
                        "gate_enabled": config.llm_gate_enabled,
                        "threshold": config.llm_gate_threshold,
                        "max_share": config.llm_gate_max_share,
                        "metrics": stats.llm_gate_metrics,
                },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )

        if doc_metadata:
            _write_doc_metadata_manifest(output_dir=config.output_dir, doc_metadata=doc_metadata)

        if stats.total_docs == 0:
            logger.warning("No documents found. Pipeline complete.")
            stats.elapsed_seconds = time.monotonic() - t0
            return stats

    if "ground_quotes" in config.stages:
        st = time.monotonic()
        logger.info("=== Ground quotes ===")
        from polisyos.lex.batch.postprocess import ground_spo_quotes

        grounded_stats = ground_spo_quotes(
            spo_results_dir=config.spo_results_dir,
            provisions_dir=config.provisions_dir,
            output_dir=config.grounded_spo_dir,
        )
        stats.grounded_statements = grounded_stats["statements_grounded"]
        stats.normative_statements = grounded_stats["statements_normative"]
        stats.stage_times["ground_quotes"] = time.monotonic() - st

    if "resolve_refs" in config.stages:
        st = time.monotonic()
        logger.info("=== Resolve references ===")
        from polisyos.lex.batch.postprocess import resolve_references

        resolved_stats = resolve_references(
            references_dir=config.references_dir,
            output_dir=config.resolved_references_dir,
            doc_metadata=doc_metadata,
        )
        stats.reference_edges = max(stats.reference_edges, resolved_stats["rows_resolved"])
        stats.stage_times["resolve_refs"] = time.monotonic() - st

    if "graph" in config.stages:
        st = time.monotonic()
        logger.info("=== Stage 4: Build graph ===")
        from polisyos.lex.batch.graph_builder import build_graph

        graph_stats = build_graph(
            spo_results_dir=Path(_active_spo_results_dir(config)),
            provisions_dir=config.provisions_dir,
            references_dir=(
                Path(_active_references_dir(config))
                if config.extract_references_enabled
                else None
            ),
            domains_dir=config.domains_dir if config.extract_domains_enabled else None,
            doc_metadata=doc_metadata,
            db_path=config.db_path,
            insert_batch_size=config.graph_insert_batch,
        )
        stats.entities = graph_stats.entities
        stats.facts = graph_stats.facts
        stats.candidate_facts = graph_stats.candidate_facts
        stats.grounded_facts = graph_stats.grounded_facts
        stats.normative_facts = graph_stats.normative_facts
        stats.reference_edges = graph_stats.reference_edges
        stats.stage_times["graph"] = time.monotonic() - st

    if config.quality_gates_enabled and "spo" in config.stages:
        st = time.monotonic()
        logger.info("=== Quality gates ===")
        from polisyos.lex.batch.quality_report import (
            QualityGateThresholds,
            build_quality_report,
            evaluate_quality_gates,
        )

        report = build_quality_report(
            provisions_dir=config.provisions_dir,
            spo_results_dir=Path(_active_spo_results_dir(config)),
            llm_gate_manifest_path=config.llm_gate_manifest_path,
            llm_gate_audit_path=config.llm_gate_audit_path,
        )
        thresholds = QualityGateThresholds(
            max_full_only_docs_pct=config.quality_max_full_only_docs_pct,
            max_empty_statement_rows_pct=config.quality_max_empty_statement_rows_pct,
            max_oov_action_rate_pct=config.quality_max_oov_action_rate_pct,
            max_missing_quote_rate_pct=config.quality_max_missing_quote_rate_pct,
            max_duplicate_anchor_rate_pct=config.quality_max_duplicate_anchor_rate_pct,
            max_audit_miss_rate_pct=config.quality_max_audit_miss_rate_pct,
            min_reference_resolution_coverage_pct=config.quality_min_reference_resolution_coverage_pct,
            min_llm_saved_pct=config.quality_min_llm_saved_pct,
            min_audit_samples_for_rate=config.quality_min_audit_samples_for_rate,
            min_provision_docs_for_doc_rate=config.quality_min_provision_docs_for_doc_rate,
            min_spo_rows_for_row_rate=config.quality_min_spo_rows_for_row_rate,
            min_statements_for_statement_rate=config.quality_min_statements_for_statement_rate,
            min_reference_rows_for_rate=config.quality_min_reference_rows_for_rate,
        )
        gate = evaluate_quality_gates(report=report, thresholds=thresholds)
        stats.quality_passed = gate.passed
        stats.quality_failed_checks = list(gate.failed_checks)
        stats.quality_skipped_checks = list(gate.skipped_checks)
        stats.quality_report = {
            key: float(value) if isinstance(value, (int, float)) else 0.0
            for key, value in gate.report.items()
            if isinstance(value, (int, float))
        }
        stats.stage_times["quality"] = time.monotonic() - st

        logger.info(
            "Quality report: full_only={:.2f}% empty_rows={:.2f}% oov_action={:.2f}% missing_quote={:.2f}% dup_anchor={:.3f}%",
            float(report.get("full_only_docs_pct", 0.0)),
            float(report.get("empty_statement_rows_pct", 0.0)),
            float(report.get("oov_action_rate_pct", 0.0)),
            float(report.get("missing_quote_rate_pct", 0.0)),
            float(report.get("duplicate_anchor_rate_pct", 0.0)),
        )
        if gate.skipped_checks:
            logger.info("Quality checks skipped due to low sample size: {}", ", ".join(gate.skipped_checks))
        if gate.warning_failed_checks:
            logger.warning("Quality warning checks failed: {}", ", ".join(gate.warning_failed_checks))
        if (not gate.passed) and (not config.quality_fail_on_critical):
            logger.warning(
                "Quality gates failed (warn-only): {}",
                ", ".join(gate.failed_checks),
            )
        if (not gate.passed) and config.quality_fail_on_critical:
            raise RuntimeError(
                f"Quality gates failed: {', '.join(gate.failed_checks)}. "
                f"Report: {gate.report}"
            )

    if "export_claims" in config.stages:
        st = time.monotonic()
        logger.info("=== Export claims ===")
        from polisyos.lex.batch.postprocess import export_normative_claims

        export_stats = export_normative_claims(
            db_path=config.db_path,
            output_dir=config.claim_exports_dir,
        )
        stats.exported_claims = export_stats["claims_total"]
        if config.export_claims_to_cas:
            from polisyos.lex.batch.claim_bridge import export_normative_claim_sets

            bridge_result = export_normative_claim_sets(
                db_path=config.db_path,
                cas_root=config.cas_root or (config.output_dir / ".polisyos"),
                fact_log_root=config.fact_log_root or (config.output_dir / "fact_log"),
                output_dir=config.claim_exports_dir,
            )
            stats.exported_claim_sets = len(bridge_result.normalized_claim_set_artifact_ids)
        stats.stage_times["export_claims"] = time.monotonic() - st

    if "benchmark" in config.stages:
        st = time.monotonic()
        logger.info("=== Benchmark ===")
        from polisyos.lex.batch.benchmark import run_benchmark

        benchmark_outcome = run_benchmark(config)
        stats.benchmark_passed = benchmark_outcome.passed
        stats.benchmark_metrics = benchmark_outcome.metrics
        stats.benchmark_failed_checks = benchmark_outcome.failed_checks
        stats.stage_times["benchmark"] = time.monotonic() - st

    if "qc" in config.stages:
        st = time.monotonic()
        logger.info("=== QC ===")
        from polisyos.lex.batch.qc import run_qc

        qc_report = run_qc(
            config,
            fail_fast=config.quality_fail_on_critical,
        )
        stats.stage_times["qc"] = time.monotonic() - st
        if stats.quality_passed is None:
            stats.quality_passed = qc_report.passed

    if "publish_bundle" in config.stages:
        st = time.monotonic()
        logger.info("=== Publish bundle ===")
        from polisyos.lex.batch.publish import run_publish

        run_publish(
            config.output_dir,
            require_embeddings=config.publish_require_embeddings,
        )
        stats.published_bundle = True
        stats.stage_times["publish_bundle"] = time.monotonic() - st

    stats.elapsed_seconds = time.monotonic() - t0
    logger.info(
        "Pipeline complete in {:.1f}s: {} docs, {} entities, {} facts",
        stats.elapsed_seconds,
        stats.total_docs,
        stats.entities,
        stats.facts,
    )
    return stats
