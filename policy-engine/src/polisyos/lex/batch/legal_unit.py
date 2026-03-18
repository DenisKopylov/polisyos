"""Legal unit subtype + routing helpers for Lex batch pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass

from polisyos.lex.batch.doc_family import classify_doc_family, infer_doc_type_category

_AMENDMENT_RE = re.compile(
    r"(внести\s+зміни|внесення\s+змін|викласти\s+у\s+(?:такій|новій)\s+редакції|"
    r"доповнити|доповнення|доповнено|замінити\s+слов(?:о|а|ами)|"
    r"слова?\s+\"?[^\"]+\"?\s+замінити|виключити|виключено|"
    r"визнати\s+(?:таким|такими).+?чинність|скасувати)",
    re.IGNORECASE,
)
_APPROVAL_RE = re.compile(
    r"(затвердити|затверджується|затверджено|схвалити|схвалено|погодити|погоджується|доручити)",
    re.IGNORECASE,
)
_APPROVAL_PASSIVE_RE = re.compile(
    r"(затверджено|затверджений|затверджена|схвалено|погоджено|затверджується)",
    re.IGNORECASE,
)
_TEMPORAL_RE = re.compile(
    r"(набирає\s+чинності|набирають\s+чинності|вводиться\s+в\s+дію|вводяться\s+в\s+дію|"
    r"не\s+пізніше|протягом\s+\d+|до\s+\d{1,2}[./]\d{1,2}[./]\d{2,4})",
    re.IGNORECASE,
)
_SANCTION_RE = re.compile(
    r"(тягне\s+за\s+собою|карається|караються|штраф(?:ується|уються)?|"
    r"адміністративн(?:а|ої)\s+відповідальн)",
    re.IGNORECASE,
)
_EXCEPTION_RE = re.compile(
    r"(крім\s+випадків|крім\s+цього|якщо\s+інше\s+не\s+передбачено|за\s+винятком)",
    re.IGNORECASE,
)
_REFERENCE_RE = re.compile(
    r"(статт[іяею]|частин[аиі]|пункт[ауі]|розділ|глава|додат(?:ок|ки)|"
    r"закон(?:у)?\s+україни|постанова|наказ|розпорядження|рішення|[№N]\s*\d)",
    re.IGNORECASE,
)
_THRESHOLD_RE = re.compile(
    r"(\d+(?:[.,]\d+)?\s*(?:%|грн|коп|рок(?:ів|и)?|дн(?:ів|і)?|місяц(?:ів|і)|"
    r"квартал(?:ів|и)?|тонн(?:и)?|кг|см|мм)|не\s+менше|не\s+більше|мінімальн(?:ий|а|і)|"
    r"максимальн(?:ий|а|і)|ставка|тариф|оклад)",
    re.IGNORECASE,
)
_APPLICATION_RE = re.compile(
    r"(заявник|заяв[ауи]\b|сертифікац|просить\s+провести|подати|надати|повідомити|"
    r"дода(?:ти|ються)|подає|надає)",
    re.IGNORECASE,
)
_APPLICATION_BULLET_RE = re.compile(
    r"^\s*(?:[-\u2013\u2014\u2022]|\d+[.)])?\s*"
    r"(?:виконувати|забезпечувати|сплатити|сплачувати|подати|подавати|надати|надавати|"
    r"повідомити|повідомляти|дотримуватися|зберігати|здійснювати|використовувати|"
    r"одержати|одержувати)\b",
    re.IGNORECASE,
)
_FORM_PLACEHOLDER_RE = re.compile(
    r"(вноситься\s+потрібне|вписується\s+потрібне|потрібне\s+підкреслити|"
    r"непотрібне\s+закреслити|\(\s*дата\s*\)|\bм\.\s*п\.\b)",
    re.IGNORECASE,
)
_FORM_FIELD_LABEL_RE = re.compile(
    r"^(?:дата|примітки|реєстраційний\s+номер|контрольна\s+сума\s+звіту|"
    r"контактна\s+особа(?:\s+з\s+питань\s+складеного\s+звіту)?|"
    r"посада(?:,?\s*підрозділ)?|прізвище,?\s*ім['’`ʼ]я,?\s*по\s+батькові|"
    r"міжміський\s+код,?\s*телефон,?\s*факс|e-mail|статутний\s+капітал|"
    r"номінальна\s+вартість|частка\s+привілейованих\s+акцій|"
    r"сумарна\s+вартість\s+непогашених\s+облігацій|дата\s+прийняття\s+звіту|"
    r"попередній\s+звіт\s+зареєстровано\s+за\s+номером)\b",
    re.IGNORECASE,
)
_REGISTRY_TITLE_RE = re.compile(
    r"^(?:перелік|список|реєстр|номенклатура|класифікатор|збірник|схема)\b",
    re.IGNORECASE,
)
_SETTLEMENT_ITEM_RE = re.compile(
    r"(?:(?:^|\s)\d+\s*)?(?:с\.|смт|м\.|місто)\s*[А-ЯІЇЄҐ][^0-9,;]{1,40}",
    re.IGNORECASE,
)
_AREA_HEADER_RE = re.compile(
    r"^(?:[А-ЯІЇЄҐ][а-яіїєґ'’`ʼ-]+(?:\s+[А-ЯІЇЄҐ][а-яіїєґ'’`ʼ-]+){0,3}\s+"
    r"(?:область|район)|ЗОНА\s+[А-ЯІЇЄҐA-Z'’`ʼ -]+)$",
    re.IGNORECASE,
)
_SALARY_TABLE_RE = re.compile(
    r"(посадов(?:ий|ого)\s+оклад|окладів|ставка|тариф|гривень|грн\b)",
    re.IGNORECASE,
)
_THRESHOLD_MULTI_RE = re.compile(
    r"^[^\d\n]{2,180}?\s+\d+(?:[.,]\d+)?(?:\s+\d+(?:[.,]\d+)?){1,}",
    re.IGNORECASE,
)
_THRESHOLD_STRONG_RE = re.compile(
    r"(ставка|тариф|оклад|ліміт|ліміти|квота|квоти|мінімальн(?:ий|а|і)|"
    r"максимальн(?:ий|а|і)|не\s+менше|не\s+більше|\b\d+(?:[.,]\d+)?\s*(?:%|грн|коп)\b)",
    re.IGNORECASE,
)
_NORMATIVE_RE = re.compile(
    r"(має|мають|повинен|повинні|зобов|заборон|не\s+допускається|не\s+має\s+права|"
    r"підляга|доручити|затвердити|встановити|визначити|поширюється)",
    re.IGNORECASE,
)
_CITATION_ONLY_RE = re.compile(
    r"^(?:відповідно\s+до|згідно\s+з|на\s+підставі)\s+"
    r"(?:(?:статт[іяею]|частин[аиі]|пункт[ауі]|розділ)\s+.+|.+(?:закону|кодексу|порядку))$",
    re.IGNORECASE,
)

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
    "tariff_threshold_row",
}


@dataclass(frozen=True)
class LegalUnitSignals:
    legal_unit_subtype: str
    route_class: str
    empty_spo_retry_eligible: bool
    audit_miss_prone: bool
    reference_bearing: bool
    threshold_bearing: bool


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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
) -> str:
    compact = _compact(text)
    lower = compact.lower()
    title = (doc_title or "").strip()
    title_lower = title.lower()
    threshold_like = False
    if struct_kind == "table_row":
        threshold_like = bool(_THRESHOLD_RE.search(compact) or _THRESHOLD_MULTI_RE.match(compact) or _THRESHOLD_STRONG_RE.search(compact))
    elif struct_kind in {"paragraph", "enumeration_item"}:
        threshold_like = bool(_THRESHOLD_MULTI_RE.match(compact) or _THRESHOLD_STRONG_RE.search(compact))

    if not compact:
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
        and not _NORMATIVE_RE.search(compact)
        and not _AMENDMENT_RE.search(compact)
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
    if _AMENDMENT_RE.search(compact):
        return "amendment_bundle"
    if (_APPROVAL_RE.search(compact) or _APPROVAL_PASSIVE_RE.search(compact)) and (
        "додат" in lower or "положення" in lower or "порядок" in lower or title
    ):
        return "approval_bundle"
    if threshold_like:
        return "tariff_threshold_row"
    if doc_family == "appendix_heavy" and (_APPLICATION_RE.search(compact) or _APPLICATION_BULLET_RE.match(compact)):
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
    if _TEMPORAL_RE.search(compact):
        return "temporal_clause"
    if _EXCEPTION_RE.search(compact):
        return "exception_clause"
    if _CITATION_ONLY_RE.match(compact) and not _NORMATIVE_RE.search(compact):
        return "citation_only"
    if section_role in {"catalog_item"} and not _NORMATIVE_RE.search(compact) and not _THRESHOLD_RE.search(compact):
        return "registry_catalog_row"
    if section_role in {"composition_member"}:
        return "composition_list"
    if doc_family in {"law", "treaty_protocol"} and struct_kind in {"article", "part", "point", "subpoint"}:
        return "core_normative_clause"
    if _NORMATIVE_RE.search(compact) or _REFERENCE_RE.search(compact):
        return "core_normative_clause"
    return "core_normative_clause"


def build_legal_unit_signals(
    *,
    text: str,
    struct_kind: str,
    section_role: str,
    fallback_allowed_for_reasoning: bool,
    doc_family: str,
    doc_title: str = "",
    citation_label: str = "",
) -> LegalUnitSignals:
    compact = _compact(text)
    subtype = detect_legal_unit_subtype(
        text=compact,
        struct_kind=struct_kind,
        section_role=section_role,
        fallback_allowed_for_reasoning=fallback_allowed_for_reasoning,
        doc_family=doc_family,
        doc_title=doc_title,
        citation_label=citation_label,
    )
    reference_bearing = bool(_REFERENCE_RE.search(compact))
    threshold_bearing = bool(_THRESHOLD_RE.search(compact) or _THRESHOLD_MULTI_RE.match(compact))

    if subtype in _HIGH_PRIORITY_NORMATIVE_SUBTYPES:
        route_class = "deterministic_only"
    elif not fallback_allowed_for_reasoning or subtype in _SEARCH_ONLY_SUBTYPES:
        route_class = "search_only"
    elif doc_family in {"law", "treaty_protocol"} and subtype in {
        "core_normative_clause",
        "exception_clause",
        "temporal_clause",
        "sanction_clause",
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
        route_class=route_class,
        empty_spo_retry_eligible=empty_retry,
        audit_miss_prone=audit_miss_prone,
        reference_bearing=reference_bearing,
        threshold_bearing=threshold_bearing,
    )


__all__ = [
    "LegalUnitSignals",
    "build_legal_unit_signals",
    "detect_legal_unit_subtype",
    "infer_doc_family_for_unit",
]
