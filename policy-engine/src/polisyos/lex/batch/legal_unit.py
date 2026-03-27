"""Legal unit subtype + routing helpers for Lex batch pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.lex.batch.doc_family import classify_doc_family, infer_doc_type_category
from polisyos.lex.batch.patterns import (
    ACTION_INHERIT_ADD_RE,
    ACTION_INHERIT_APPROVAL_RE,
    ACTION_INHERIT_REMOVE_RE,
    AMENDMENT_CORE_RE,
    APPLICATION_BULLET_RE,
    APPLICATION_CORE_RE,
    APPLICATION_LEAD_RE,
    APPROVAL_PASSIVE_RE,
    APPROVAL_CORE_RE,
    AREA_HEADER_RE,
    CITATION_ONLY_RE,
    COMPLETION_TAIL_RE,
    CONDITION_TAIL_RE,
    EXCEPTION_CORE_RE,
    FORM_FIELD_LABEL_RE,
    FORM_LABEL_NOUN_RE,
    FORM_PLACEHOLDER_RE,
    FORM_SECTION_HEADING_RE,
    FRONT_MATTER_RE,
    MAIN_DEONTIC_RE,
    NORMATIVE_CORE_RE,
    REFERENCE_CORE_RE,
    REGISTRY_TITLE_RE,
    SALARY_TABLE_RE,
    SANCTION_CORE_RE,
    SCOPE_TAIL_RE,
    SETTLEMENT_ITEM_RE,
    TEMPORAL_CORE_RE,
    THRESHOLD_MULTI_RE,
    THRESHOLD_STRONG_RE,
    THRESHOLD_CORE_RE,
    UNITLESS_THRESHOLD_HINT_RE,
)

if TYPE_CHECKING:
    from polisyos.lex.batch.jurisdictions.protocol import JurisdictionPlugin, NormativeSignalPatterns

_AMENDMENT_RE = AMENDMENT_CORE_RE
_APPROVAL_RE = APPROVAL_CORE_RE
_APPROVAL_PASSIVE_RE = APPROVAL_PASSIVE_RE
_TEMPORAL_RE = TEMPORAL_CORE_RE
_SANCTION_RE = SANCTION_CORE_RE
_EXCEPTION_RE = EXCEPTION_CORE_RE
_REFERENCE_RE = REFERENCE_CORE_RE
_THRESHOLD_RE = THRESHOLD_CORE_RE
_APPLICATION_RE = APPLICATION_CORE_RE
_APPLICATION_BULLET_RE = APPLICATION_BULLET_RE
_APPLICATION_LEAD_RE = APPLICATION_LEAD_RE
_FORM_PLACEHOLDER_RE = FORM_PLACEHOLDER_RE
_FORM_SECTION_HEADING_RE = FORM_SECTION_HEADING_RE
_FORM_FIELD_LABEL_RE = FORM_FIELD_LABEL_RE
_FORM_LABEL_NOUN_RE = FORM_LABEL_NOUN_RE
_ACTION_INHERIT_REMOVE_RE = ACTION_INHERIT_REMOVE_RE
_ACTION_INHERIT_ADD_RE = ACTION_INHERIT_ADD_RE
_ACTION_INHERIT_APPROVAL_RE = ACTION_INHERIT_APPROVAL_RE
_FRONT_MATTER_RE = FRONT_MATTER_RE
_REGISTRY_TITLE_RE = REGISTRY_TITLE_RE
_SETTLEMENT_ITEM_RE = SETTLEMENT_ITEM_RE
_AREA_HEADER_RE = AREA_HEADER_RE
_SALARY_TABLE_RE = SALARY_TABLE_RE
_THRESHOLD_MULTI_RE = THRESHOLD_MULTI_RE
_UNITLESS_THRESHOLD_HINT_RE = UNITLESS_THRESHOLD_HINT_RE
_THRESHOLD_STRONG_RE = THRESHOLD_STRONG_RE
_NORMATIVE_RE = NORMATIVE_CORE_RE
_CITATION_ONLY_RE = CITATION_ONLY_RE
_CONDITION_TAIL_RE = CONDITION_TAIL_RE
_SCOPE_TAIL_RE = SCOPE_TAIL_RE
_COMPLETION_TAIL_RE = COMPLETION_TAIL_RE
_MAIN_DEONTIC_RE = MAIN_DEONTIC_RE

_SEARCH_ONLY_SECTION_ROLES = {
    "appendix_header",
    "appendix_section",
    "attachment_inventory",
    "catalog_header",
    "catalog_item",
    "composition_member",
    "decorative_separator",
    "fallback_recall",
    "form_field",
    "form_header",
    "questionnaire_item",
    "signature_block",
    "table_header",
    "table_scaffold",
}
_SEARCH_ONLY_SUBTYPES = {
    "citation_only",
    "composition_list",
    "form_scaffold",
    "inventory_only",
    "registry_catalog_row",
    "table_scaffold",
}
_HIGH_PRIORITY_NORMATIVE_SUBTYPES = {
    "amendment_bundle",
    "approval_bundle",
    "application_requirement",
}


@dataclass(frozen=True)
class LegalUnitSignals:
    legal_unit_subtype: str
    legal_unit_micro_subtype: str
    route_class: str
    empty_spo_retry_eligible: bool
    audit_miss_prone: bool
    reference_bearing: bool
    threshold_bearing: bool


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _signal_patterns(jurisdiction_plugin: JurisdictionPlugin | None) -> NormativeSignalPatterns | None:
    if jurisdiction_plugin is None:
        return None
    cached = getattr(jurisdiction_plugin, "_cached_normative_signal_patterns", None)
    if cached is None:
        cached = jurisdiction_plugin.normative_signal_patterns()
        try:
            setattr(jurisdiction_plugin, "_cached_normative_signal_patterns", cached)
        except Exception:  # pragma: no cover - defensive for exotic plugin objects
            pass
    return cached


def _count_matches(pattern: re.Pattern[str], text: str) -> int:
    return len(pattern.findall(text))


def _any_match(text: str, *patterns: re.Pattern[str] | None) -> bool:
    return any(pattern is not None and bool(pattern.search(text)) for pattern in patterns)


def _is_amendment_like(text: str, jurisdiction_plugin: JurisdictionPlugin | None) -> bool:
    patterns = _signal_patterns(jurisdiction_plugin)
    return _any_match(text, patterns.amendment_re if patterns is not None else _AMENDMENT_RE)


def _is_approval_like(text: str, jurisdiction_plugin: JurisdictionPlugin | None) -> bool:
    patterns = _signal_patterns(jurisdiction_plugin)
    return _any_match(text, patterns.approval_re if patterns is not None else _APPROVAL_RE)


def _is_temporal_like(text: str, jurisdiction_plugin: JurisdictionPlugin | None) -> bool:
    patterns = _signal_patterns(jurisdiction_plugin)
    return _any_match(text, patterns.temporal_re if patterns is not None else _TEMPORAL_RE)


def _is_reference_like(text: str, jurisdiction_plugin: JurisdictionPlugin | None) -> bool:
    patterns = _signal_patterns(jurisdiction_plugin)
    return _any_match(text, patterns.reference_re if patterns is not None else _REFERENCE_RE)


def _is_threshold_like(text: str, jurisdiction_plugin: JurisdictionPlugin | None) -> bool:
    patterns = _signal_patterns(jurisdiction_plugin)
    return _any_match(text, patterns.threshold_re if patterns is not None else _THRESHOLD_RE)


def _is_normative_like(text: str, jurisdiction_plugin: JurisdictionPlugin | None) -> bool:
    patterns = _signal_patterns(jurisdiction_plugin)
    if patterns is None:
        return bool(_NORMATIVE_RE.search(text))
    return _any_match(
        text,
        patterns.obligation_re,
        patterns.prohibition_re,
        patterns.permission_re,
        patterns.approval_re,
    )


def _is_main_deontic(text: str, jurisdiction_plugin: JurisdictionPlugin | None) -> bool:
    patterns = _signal_patterns(jurisdiction_plugin)
    if patterns is None:
        return bool(_MAIN_DEONTIC_RE.search(text))
    return _any_match(
        text,
        patterns.obligation_re,
        patterns.prohibition_re,
        patterns.permission_re,
    )


def infer_doc_family_for_unit(
    *,
    doc_type: str = "",
    doc_name: str = "",
    provision_rows: list[dict] | None = None,
) -> str:
    return classify_doc_family(
        doc_type=doc_type,
        doc_name=doc_name,
        doc_type_category_value=infer_doc_type_category(doc_type=doc_type, doc_name=doc_name),
        provision_rows=provision_rows,
    )


def detect_legal_unit_subtype(
    *,
    text: str,
    struct_kind: str,
    section_role: str,
    fallback_allowed_for_reasoning: bool,
    doc_family: str,
    doc_title: str = "",
    citation_label: str = "",
    context_prefix: str = "",
    jurisdiction_plugin: JurisdictionPlugin | None = None,
) -> str:
    compact = _compact(text)
    lower = compact.lower()
    title = (doc_title or "").strip()
    title_lower = title.lower()
    context = _compact(context_prefix)
    context_lower = context.lower()
    threshold_like = False
    if struct_kind == "table_row":
        threshold_like = bool(
            _is_threshold_like(compact, jurisdiction_plugin)
            or _THRESHOLD_MULTI_RE.match(compact)
            or _THRESHOLD_STRONG_RE.search(compact)
            or (
                _UNITLESS_THRESHOLD_HINT_RE.match(compact)
                and _SALARY_TABLE_RE.search(f"{title} {compact}")
            )
        )
    elif struct_kind in {"paragraph", "enumeration_item"}:
        threshold_like = bool(
            _is_threshold_like(compact, jurisdiction_plugin)
            or _THRESHOLD_MULTI_RE.match(compact)
            or _THRESHOLD_STRONG_RE.search(compact)
        )

    if not compact:
        return "table_scaffold"
    if (
        struct_kind in {"paragraph", "fallback_unit"}
        and not re.match(r"^\s*\d+[.)]", compact)
        and _FRONT_MATTER_RE.search(compact)
        and ("зареєстровано" in lower or "наказую" in lower or "затверджено" in lower)
    ):
        return "table_scaffold"
    if section_role in {"appendix_header", "table_header", "attachment_inventory", "questionnaire_item", "form_field", "decorative_separator"}:
        if section_role == "attachment_inventory":
            return "inventory_only"
        return "table_scaffold"
    if section_role in {"form_header", "signature_block"}:
        if threshold_like and _SALARY_TABLE_RE.search(compact):
            return "tariff_threshold_row"
        return "form_scaffold"
    if section_role == "composition_member":
        return "composition_list"
    if (
        doc_family == "appendix_heavy"
        and not _is_normative_like(compact, jurisdiction_plugin)
        and not _is_amendment_like(compact, jurisdiction_plugin)
        and not _APPLICATION_RE.search(compact)
    ):
        settlement_hits = len(_SETTLEMENT_ITEM_RE.findall(compact))
        if (
            _REGISTRY_TITLE_RE.match(compact)
            or _AREA_HEADER_RE.match(compact)
            or settlement_hits >= 1
        ):
            return "registry_catalog_row"
        if _FORM_FIELD_LABEL_RE.match(compact) or (compact.endswith(":") and len(compact.split()) <= 10):
            return "form_scaffold"
        if section_role == "procedure" and len(compact.split()) <= 14 and not threshold_like:
            return "form_scaffold"
    if _FORM_PLACEHOLDER_RE.search(compact):
        return "form_scaffold"
    if (
        doc_family == "appendix_heavy"
        and (
            _FORM_SECTION_HEADING_RE.match(compact)
            or (
                section_role == "procedure"
                and _FORM_LABEL_NOUN_RE.match(compact)
                and len(compact.split()) <= 18
                and not compact.endswith((".", ";", ":"))
                and not _is_approval_like(compact, jurisdiction_plugin)
                and not _is_amendment_like(compact, jurisdiction_plugin)
                and not _is_normative_like(compact, jurisdiction_plugin)
            )
        )
        and len(compact.split()) <= 20
        and not _is_normative_like(compact, jurisdiction_plugin)
        and not _is_threshold_like(compact, jurisdiction_plugin)
    ):
        return "form_scaffold"
    if (
        doc_family == "appendix_heavy"
        and context
        and struct_kind in {"enumeration_item", "paragraph", "point"}
        and len(compact.split()) <= 18
        and not _is_normative_like(compact, jurisdiction_plugin)
        and not _is_threshold_like(compact, jurisdiction_plugin)
    ):
        if _ACTION_INHERIT_REMOVE_RE.search(context):
            return "amendment_bundle"
        if _ACTION_INHERIT_ADD_RE.search(context):
            return "amendment_bundle"
        if _ACTION_INHERIT_APPROVAL_RE.search(context):
            return "approval_bundle"
    if _is_amendment_like(compact, jurisdiction_plugin):
        return "amendment_bundle"
    if (_is_approval_like(compact, jurisdiction_plugin) or _APPROVAL_PASSIVE_RE.search(compact)) and (
        "додат" in lower or "положення" in lower or "порядок" in lower or title
    ):
        return "approval_bundle"
    if threshold_like:
        return "tariff_threshold_row"
    application_like = bool(_APPLICATION_BULLET_RE.match(compact) or _APPLICATION_LEAD_RE.search(compact))
    if not application_like and section_role == "procedure" and len(compact.split()) <= 40:
        application_like = bool(_APPLICATION_RE.search(compact))
    if doc_family == "appendix_heavy" and application_like:
        return "application_requirement"
    if not fallback_allowed_for_reasoning or section_role in _SEARCH_ONLY_SECTION_ROLES:
        if section_role in {"signature_block", "form_header", "form_field", "questionnaire_item"}:
            return "form_scaffold"
        if section_role in {"attachment_inventory"}:
            return "inventory_only"
        if section_role in {"composition_member"}:
            return "composition_list"
        if section_role in {"catalog_item", "catalog_header"}:
            return "registry_catalog_row"
        return "table_scaffold"
    if _SANCTION_RE.search(compact):
        return "sanction_clause"
    if _is_temporal_like(compact, jurisdiction_plugin):
        return "temporal_clause"
    if _EXCEPTION_RE.search(compact):
        return "exception_clause"
    if _CITATION_ONLY_RE.match(compact) and not _is_normative_like(compact, jurisdiction_plugin):
        return "citation_only"
    if section_role in {"catalog_item"} and not _is_normative_like(compact, jurisdiction_plugin) and not _is_threshold_like(compact, jurisdiction_plugin):
        return "registry_catalog_row"
    if section_role in {"composition_member"}:
        return "composition_list"
    if doc_family in {"law", "treaty_protocol"} and struct_kind in {"article", "part", "point", "subpoint"}:
        return "core_normative_clause"
    if _is_normative_like(compact, jurisdiction_plugin) or _is_reference_like(compact, jurisdiction_plugin):
        return "core_normative_clause"
    return "core_normative_clause"


def detect_legal_unit_micro_subtype(
    *,
    text: str,
    legal_unit_subtype: str,
    reference_bearing: bool,
    threshold_bearing: bool,
    jurisdiction_plugin: JurisdictionPlugin | None = None,
) -> str:
    compact = _compact(text)
    if legal_unit_subtype != "core_normative_clause" or not compact:
        return ""
    if threshold_bearing:
        return "threshold_tail"
    if _CONDITION_TAIL_RE.search(compact):
        return "condition_tail"
    if _SCOPE_TAIL_RE.search(compact):
        return "scope_tail"
    if reference_bearing and (
        _is_amendment_like(compact, jurisdiction_plugin)
        or _is_reference_like(compact, jurisdiction_plugin)
        or re.search(
            r"\b(відповідно\s+до|згідно\s+з|передбачен[оі]\s+статтею|додат(?:ок|ки))\b",
            compact,
            re.IGNORECASE,
        )
    ):
        return "reference_tail"
    if _COMPLETION_TAIL_RE.search(compact):
        return "completion_tail"
    if _is_main_deontic(compact, jurisdiction_plugin):
        return "main_deontic"
    return "main_deontic"


def build_legal_unit_signals(
    *,
    text: str,
    struct_kind: str,
    section_role: str,
    fallback_allowed_for_reasoning: bool,
    doc_family: str,
    doc_title: str = "",
    citation_label: str = "",
    context_prefix: str = "",
    jurisdiction_plugin: JurisdictionPlugin | None = None,
) -> LegalUnitSignals:
    compact = _compact(text)
    lower = compact.lower()
    subtype = detect_legal_unit_subtype(
        text=compact,
        struct_kind=struct_kind,
        section_role=section_role,
        fallback_allowed_for_reasoning=fallback_allowed_for_reasoning,
        doc_family=doc_family,
        doc_title=doc_title,
        citation_label=citation_label,
        context_prefix=context_prefix,
        jurisdiction_plugin=jurisdiction_plugin,
    )
    reference_bearing = _is_reference_like(compact, jurisdiction_plugin)
    threshold_bearing = bool(
        _is_threshold_like(compact, jurisdiction_plugin)
        or (
            struct_kind in {"table_row", "paragraph", "enumeration_item"}
            and _THRESHOLD_MULTI_RE.match(compact)
        )
    )
    if threshold_bearing and re.search(r"\b\d{4}\s+рок", lower):
        strong_threshold_cues = (
            "%" in compact
            or any(
                marker in lower
                for marker in (
                    "ставк",
                    "тариф",
                    "оклад",
                    "поріг",
                    "не менш",
                    "не більш",
                    "не нижче",
                    "не вище",
                    "грн",
                    "коп",
                    "кг",
                    "км",
                    "га",
                    "тонн",
                )
            )
        )
        if not strong_threshold_cues:
            threshold_bearing = False
    micro_subtype = detect_legal_unit_micro_subtype(
        text=compact,
        legal_unit_subtype=subtype,
        reference_bearing=reference_bearing,
        threshold_bearing=threshold_bearing,
        jurisdiction_plugin=jurisdiction_plugin,
    )

    if subtype in _HIGH_PRIORITY_NORMATIVE_SUBTYPES:
        route_class = "deterministic_only"
    elif not fallback_allowed_for_reasoning or subtype in _SEARCH_ONLY_SUBTYPES:
        route_class = "search_only"
    elif doc_family in {"law", "treaty_protocol", "appendix_heavy"} and subtype in {
        "core_normative_clause",
        "exception_clause",
        "temporal_clause",
        "sanction_clause",
        "tariff_threshold_row",
    }:
        route_class = "deterministic_then_llm_retry"
    else:
        route_class = "llm_primary"

    audit_miss_prone = subtype in {
        "amendment_bundle",
        "approval_bundle",
        "application_requirement",
        "core_normative_clause",
        "exception_clause",
        "temporal_clause",
        "sanction_clause",
        "tariff_threshold_row",
    } or reference_bearing or threshold_bearing
    empty_retry = route_class in {"deterministic_then_llm_retry", "llm_primary"} and doc_family in {
        "appendix_heavy",
        "law",
        "treaty_protocol",
    }
    return LegalUnitSignals(
        legal_unit_subtype=subtype,
        legal_unit_micro_subtype=micro_subtype,
        route_class=route_class,
        empty_spo_retry_eligible=empty_retry,
        audit_miss_prone=audit_miss_prone,
        reference_bearing=reference_bearing,
        threshold_bearing=threshold_bearing,
    )


__all__ = [
    "LegalUnitSignals",
    "build_legal_unit_signals",
    "detect_legal_unit_micro_subtype",
    "detect_legal_unit_subtype",
    "infer_doc_family_for_unit",
]
