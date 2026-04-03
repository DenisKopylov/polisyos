"""Helper functions for the Lex batch pipeline."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from polisyos.common.logger import get_logger
from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.doc_family import infer_doc_type_category
from polisyos.lex.batch.pipeline_types import SPODocRoutingPlan, SPOLLMSettings, StructureQualityStats
from polisyos.lex.batch.progress import ProgressTracker
from polisyos.lex.batch.provisions_io import read_provisions, write_provisions
from polisyos.lex.batch.temporal_resolver import resolve_document_temporal

if TYPE_CHECKING:
    from polisyos.lex.batch.structurer import ProvisionSpan
    from polisyos.lex.batch.xml_parser import NPADocument

logger = get_logger(__name__)
T = TypeVar("T")


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
_AUDIT_LOW_SIGNAL_FORM_LABEL_RE = re.compile(
    r"^(?:назва|інформація\s+про|прізвище|ім['’`ʼ]я|по\s+батькові|"
    r"місце(?:\s+здійснення)?|участь|наявність|вид\s+діяльності|"
    r"ідентифікаційний\s+код|адреса|телефон|дата|контактна\s+особа)\b",
    re.IGNORECASE,
)
_AUDIT_FRONT_MATTER_RE = re.compile(
    r"(зареєстровано|наказую:|затверджено|"
    r"від\s+\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*(?:р\.?)?\s*(?:n|№)\s*\d+|"
    r"від\s+\d{1,2}\s+[а-яіїєґ]+\s+\d{4}\s*р\.?\s*(?:n|№)\s*\d+)",
    re.IGNORECASE,
)
_GAP_FILL_EXCLUDED_SUBTYPES = frozenset(
    {
        "citation_only",
        "composition_list",
        "form_scaffold",
        "inventory_only",
        "registry_catalog_row",
        "table_scaffold",
    }
)
_PASSIVE_DELEGATION_TAIL_RE = re.compile(
    r"(порядок\s+[^.]{0,120}?встановлюється|визначається\s+стороною|визначається\s+органом|"
    r"може\s+надаватися|не\s+може|має\s+право|у\s+цьому\s+разі|при\s+цьому)",
    re.IGNORECASE,
)


def _should_skip_audit_for_span(span: ProvisionSpan) -> bool:
    text = " ".join((span.text or "").split()).strip()
    if not text:
        return True
    if (span.route_class or "") == "search_only" or (span.legal_unit_subtype or "") == "form_scaffold":
        return True
    if span.legal_unit_subtype in {"application_requirement", "core_normative_clause"}:
        if (
            len(text.split()) <= 18
            and not text.endswith((".", ";", ":"))
            and not _NORMATIVE_SPAN_SIGNAL_RE.search(text)
            and not _REFERENCE_SPAN_SIGNAL_RE.search(text)
            and not _THRESHOLD_SPAN_SIGNAL_RE.search(text)
            and _AUDIT_LOW_SIGNAL_FORM_LABEL_RE.match(text)
        ):
            return True
    if (
        span.legal_unit_subtype in {"core_normative_clause", "tariff_threshold_row"}
        and _AUDIT_FRONT_MATTER_RE.search(text)
        and not _NORMATIVE_SPAN_SIGNAL_RE.search(text)
    ):
        return True
    return False


def _contains_gap_fill_tail_marker(text: str, markers: list[str]) -> bool:
    lowered = " ".join((text or "").lower().split())
    return any(marker.lower() in lowered for marker in markers if marker)


def _gap_fill_priority(*, family: str, subtype: str) -> int:
    if subtype == "application_requirement":
        return 1
    if subtype == "core_normative_clause":
        return 2
    if family == "treaty_protocol":
        return 3
    if subtype == "approval_bundle":
        return 4
    if subtype == "temporal_clause":
        return 5
    if subtype == "amendment_bundle":
        return 6
    if subtype == "tariff_threshold_row":
        return 7
    return 99


def _is_gap_fill_low_signal(span: ProvisionSpan) -> bool:
    text = " ".join((span.text or "").split()).strip()
    if not text:
        return True
    if (span.route_class or "") == "search_only":
        return True
    if (span.legal_unit_subtype or "") in _GAP_FILL_EXCLUDED_SUBTYPES:
        return True
    if _should_skip_audit_for_span(span):
        return True
    if span.is_fallback_chunk:
        if span.legal_unit_subtype not in {"approval_bundle", "amendment_bundle"}:
            return True
        if len(text) > 600:
            return True
    return False


def _should_route_llm_gap_fill(
    *,
    config: BatchConfig,
    span: ProvisionSpan,
    quality_family: str,
    deterministic_candidates: list[Any],
) -> tuple[bool, int, list[str]]:
    if not config.llm_gap_fill_enabled or config.llm_gap_fill_mode == "off":
        return False, 99, []
    if _is_gap_fill_low_signal(span):
        return False, 99, []

    subtype = str(span.legal_unit_subtype or "")
    family_match = quality_family in set(config.llm_gap_fill_target_families)
    subtype_match = subtype in set(config.llm_gap_fill_target_subtypes)
    text = span.text or ""
    det_count = len(deterministic_candidates)
    tail_hit = _contains_gap_fill_tail_marker(text, config.llm_gap_fill_tail_markers)
    delegation_tail_hit = bool(_PASSIVE_DELEGATION_TAIL_RE.search(text))
    reasons: list[str] = []

    if config.llm_gap_fill_force_empty_spo and det_count == 0 and (family_match or subtype_match):
        reasons.append("empty_spo_baseline")
    if (
        config.llm_gap_fill_force_single_fact_tails
        and det_count == 1
        and (tail_hit or delegation_tail_hit)
    ):
        reasons.append("single_fact_tail")
    if quality_family == "treaty_protocol" and (family_match or subtype_match):
        reasons.append("treaty_priority_family")
    if subtype in {"approval_bundle", "amendment_bundle"} and (family_match or subtype_match):
        reasons.append("bundle_priority_subtype")
    strong_appendix_signal = any(
        (
            det_count == 0,
            tail_hit,
            delegation_tail_hit,
            bool(span.reference_bearing),
            bool(span.threshold_bearing),
        )
    )
    if quality_family == "appendix_heavy" and subtype == "core_normative_clause" and strong_appendix_signal:
        reasons.append("appendix_core_strong_signal")
    if subtype == "sanction_clause" and det_count <= 1:
        reasons.append("sanction_low_det")
    if subtype == "tariff_threshold_row" and det_count <= 1:
        reasons.append("tariff_threshold_low_det")
    _GAP_FILL_AUDIT_MISS_SUBTYPES = {"sanction_clause", "tariff_threshold_row"}
    if (
        span.audit_miss_prone
        and det_count <= 1
        and subtype in _GAP_FILL_AUDIT_MISS_SUBTYPES
    ):
        reasons.append("audit_miss_prone_low_det")
    if tail_hit:
        reasons.append("tail_marker")
    if delegation_tail_hit:
        reasons.append("delegation_tail")

    if not reasons:
        return False, 99, []

    if config.llm_gap_fill_mode == "narrow":
        narrow_reasons = {"empty_spo_baseline", "single_fact_tail", "treaty_priority_family"}
        if not any(reason in narrow_reasons for reason in reasons):
            return False, 99, []

    return True, _gap_fill_priority(family=quality_family, subtype=subtype), sorted(set(reasons))


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

    risky_selected_spans = [
        span
        for span in selected_spans
        if (span.legal_unit_subtype or "") in {"sanction_clause", "tariff_threshold_row"}
        or (
            quality_family == "appendix_heavy"
            and (span.legal_unit_subtype or "") == "core_normative_clause"
        )
    ]
    if risky_selected_spans:
        flags.append("risk_subtype_downshift")
        llm_settings = SPOLLMSettings(
            task_batch_size=min(llm_settings.task_batch_size, 12),
            request_batch_size=1,
            request_batch_chars=min(llm_settings.request_batch_chars or 2200, 2200),
            group_timeout_seconds=llm_settings.group_timeout_seconds,
        )

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


_MIN_PROVISION_TEXT_CHARS = 10
"""Minimum number of non-whitespace characters for a provision to be worth
extracting SPO from.  Provisions below this threshold are structural anchors
with no meaningful normative content (e.g. empty table cells, stray numbers,
or unicode-only whitespace that survives ``str.strip``)."""


def _strip_all_whitespace(text: str) -> str:
    """Remove ALL unicode whitespace including NBSP / zero-width chars."""
    import re
    return re.sub(r"\s+", "", text)


def _should_extract_spo_from_span(span: ProvisionSpan) -> bool:
    high_precision_fallback = False
    if not span.text.strip():
        return False
    # Catch provisions that are structurally anchored but contain only trivial
    # text (numbers, punctuation, invisible unicode) — these always produce
    # empty SPO rows and inflate empty_statement_rows_pct.
    if len(_strip_all_whitespace(span.text)) < _MIN_PROVISION_TEXT_CHARS:
        return False
    if span.is_fallback_chunk:
        subtype = (span.legal_unit_subtype or "").strip().lower()
        high_precision_fallback = subtype in {"amendment_bundle", "approval_bundle"} and len(span.text) <= 3600
        if not high_precision_fallback:
            return False
    if (span.route_class or "").strip().lower() == "search_only":
        return False
    if not span.fallback_allowed_for_reasoning and not high_precision_fallback:
        return False
    if span.section_role in {"table_header", "appendix_section"}:
        return False
    if span.section_role == "fallback_recall" and not high_precision_fallback:
        return False
    return True


def _extract_provisions_worker(payload: dict) -> list[dict]:
    from polisyos.lex.batch.structurer import extract_provisions

    text = str(payload.get("text", ""))
    spans = extract_provisions(
        text,
        jurisdiction=str(payload.get("jurisdiction") or "UA"),
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
            "legal_unit_micro_subtype": s.legal_unit_micro_subtype,
            "route_class": s.route_class,
            "empty_spo_retry_eligible": s.empty_spo_retry_eligible,
            "audit_miss_prone": s.audit_miss_prone,
            "reference_bearing": s.reference_bearing,
            "threshold_bearing": s.threshold_bearing,
            "context_prefix": s.context_prefix,
        }
        for s in spans
    ]


def _chunked(items: list[T], size: int) -> list[list[T]]:
    chunk_size = max(1, size)
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _as_doc_meta(doc: NPADocument) -> dict:
    temporal = resolve_document_temporal(
        {
            "date_acc": doc.card.date_acc,
            "reestr_date": doc.card.reestr_date,
            "status": doc.card.status,
            "publication": list(doc.card.publication),
            "reg_date": doc.card.reg_date,
        },
        text=doc.text,
    )
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
        "publication": list(doc.card.publication),
        "reg_date": doc.card.reg_date,
        "reg_number": doc.card.reg_number,
        "published_at": temporal.published_at,
        "temporal": temporal.to_metadata(),
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
        if str(payload.get("condition_text_uk") or "").strip() or str(payload.get("exception_text_uk") or "").strip():
            categories.add("condition")
        if str(payload.get("sanction_text_uk") or "").strip():
            categories.add("sanction")
        if str(payload.get("temporal_text_uk") or "").strip():
            categories.add("temporal")
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
        if action in {"penalizes"} or norm_type == "sanction":
            categories.add("sanction")
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


def _load_doc_metadata_manifest(output_dir: Path) -> dict[str, dict[str, Any]]:
    """Load doc_metadata from previously saved manifest (fast-path for resume)."""
    manifest_path = output_dir / "manifests" / "doc_metadata.json"
    if not manifest_path.exists():
        return {}
    with open(manifest_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if isinstance(payload, dict):
        source = payload.get("documents") if isinstance(payload.get("documents"), dict) else payload
        return {
            str(doc_id): dict(meta)
            for doc_id, meta in source.items()
            if isinstance(meta, dict)
        }
    return {}


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
                legal_unit_micro_subtype=str(p.get("legal_unit_micro_subtype") or ""),
                route_class=str(p.get("route_class") or ""),
                empty_spo_retry_eligible=bool(p.get("empty_spo_retry_eligible", False)),
                audit_miss_prone=bool(p.get("audit_miss_prone", False)),
                reference_bearing=bool(p.get("reference_bearing", False)),
                threshold_bearing=bool(p.get("threshold_bearing", False)),
                context_prefix=str(p.get("context_prefix") or ""),
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
        "legal_unit_micro_subtype": span.legal_unit_micro_subtype or "",
        "route_class": span.route_class or "",
        "empty_spo_retry_eligible": bool(span.empty_spo_retry_eligible),
        "audit_miss_prone": bool(span.audit_miss_prone),
        "reference_bearing": bool(span.reference_bearing),
        "threshold_bearing": bool(span.threshold_bearing),
        "context_prefix": span.context_prefix or "",
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
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(out_path, mode, encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _doc_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _has_jsonl_rows(path: str) -> bool:
    root = Path(path)
    return root.exists() and any(root.glob("**/*.jsonl"))


def _bump_counter(counter: dict[str, int], key: str, amount: int = 1) -> None:
    if not key:
        return
    counter[key] = int(counter.get(key, 0) or 0) + amount


async def _call_extract_spo_for_documents(
    extract_fn: Any,
    client: Any,
    documents: list[Any],
    provisions_by_doc: dict[str, list[Any]],
    **kwargs: Any,
) -> tuple[int, set[str]]:
    try:
        signature = inspect.signature(extract_fn)
    except (TypeError, ValueError):
        return await extract_fn(client, documents, provisions_by_doc, **kwargs)

    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return await extract_fn(client, documents, provisions_by_doc, **kwargs)

    filtered_kwargs = {
        key: value
        for key, value in kwargs.items()
        if key in signature.parameters
    }
    return await extract_fn(client, documents, provisions_by_doc, **filtered_kwargs)


def _active_spo_results_dir(config: BatchConfig) -> str:
    if _has_jsonl_rows(str(config.grounded_spo_dir)):
        return str(config.grounded_spo_dir)
    return str(config.spo_results_dir)


def _active_references_dir(config: BatchConfig) -> str:
    if _has_jsonl_rows(str(config.resolved_references_dir)):
        return str(config.resolved_references_dir)
    return str(config.references_dir)


def _write_doc_domain(*, domains_dir: str, doc_id: str, payload: dict) -> None:
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
    docs_to_process: list[NPADocument] = []
    doc_meta_by_id: dict[str, dict[str, Any]] = {}
    for d in docs_chunk:
        doc_hash = _doc_content_hash(d.text)
        if config.resume and progress.is_done_with_hash(d.card.doc_id, "structured", doc_hash):
            continue
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
    pipeline_module = sys.modules.get("polisyos.lex.batch.pipeline")
    process_pool_cls = getattr(pipeline_module, "ProcessPoolExecutor", ProcessPoolExecutor)
    thread_pool_cls = getattr(pipeline_module, "ThreadPoolExecutor", ThreadPoolExecutor)
    executor_cls: type[ProcessPoolExecutor] | type[ThreadPoolExecutor] = process_pool_cls
    main_file = str(getattr(sys.modules.get("__main__"), "__file__", "") or "")
    if not main_file or "<stdin>" in main_file:
        executor_cls = thread_pool_cls
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
            executor_cls = thread_pool_cls
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
                    "jurisdiction": config.jurisdiction,
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
            except Exception as exc:  # pragma: no cover
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
                doc_id,
                "structured",
                stats={"provisions": len(result)},
                content_hash=doc_hash,
            )
    return provisions_by_doc, total_provisions, structure_stats


__all__ = [
    "_active_references_dir",
    "_active_spo_results_dir",
    "_as_doc_meta",
    "_build_llm_fallback_row",
    "_build_spo_doc_routing_plan",
    "_bump_counter",
    "_call_extract_spo_for_documents",
    "_check_structure_quality_gate",
    "_chunked",
    "_doc_content_hash",
    "_group_docs_by_spo_settings",
    "_process_structure_chunk",
    "_should_extract_spo_from_span",
    "_should_route_llm_gap_fill",
    "_should_skip_audit_for_span",
    "_span_signal_payload",
    "_statement_category_set",
    "_structure_gate_report",
    "_to_provision_spans",
    "_write_doc_domain",
    "_load_doc_metadata_manifest",
    "_write_doc_metadata_manifest",
    "_write_jsonl_rows",
]
