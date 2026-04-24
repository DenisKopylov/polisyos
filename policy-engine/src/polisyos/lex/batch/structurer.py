"""Stage 2: Lightweight provision extraction reusing UA regex from corpus/structure.py.

No CAS, no world events — just text → list of ProvisionSpan.
Designed for batch processing of 140K documents.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace

from polisyos.common.logger import get_logger
from polisyos.lex.corpus.structure import (
    _POINT_RE_LIST,
    _SUBPOINT_RE,
    _build_candidates,
    _citation_label,
    _iter_lines_with_offsets,
    _LineSpan,
    _ruleset_for,
)
from polisyos.lex.types import LexStructureOptions

logger = get_logger(__name__)


@dataclass(frozen=True)
class ProvisionSpan:
    """A provision extracted from legal text — lightweight, no CAS references."""

    kind: str  # "article", "part", "point", "subpoint", "paragraph", "full_text"
    number: str | None
    anchor_path: str
    citation_label: str
    offset_start: int
    offset_end: int
    text: str
    parent_anchor: str | None = None
    depth: int = 0
    token_est: int = 0
    text_hash: str = ""
    is_fallback_chunk: bool = False
    struct_kind: str = ""
    section_role: str = ""
    lineage_path: str = ""
    appendix_id: str | None = None
    table_id: str | None = None
    fallback_allowed_for_reasoning: bool = False
    legal_unit_subtype: str = ""
    legal_unit_micro_subtype: str = ""
    route_class: str = ""
    empty_spo_retry_eligible: bool = False
    audit_miss_prone: bool = False
    reference_bearing: bool = False
    threshold_bearing: bool = False
    context_prefix: str = ""


_APPENDIX_RE = re.compile(r"^\s*додат(?:ок|ки)\b(?:\s*№?\s*([0-9A-Za-zА-Яа-я\-]+))?", re.IGNORECASE)
_TABLEISH_RE = re.compile(r"(?:\t| {3,}|\|)")
_BULLET_RE = re.compile(r"^\s*[-\u2013\u2014\u2022]\s+\S")
_SUBPOINT_DOT_RE = re.compile(r"^\s*([a-zA-Zа-яА-ЯіїєґІЇЄҐ])\.\s+\S")
_SECTION_KEYWORD_RE = re.compile(
    r"^\s*(?:розділ|глава|section)\s+([IVXLCM\d]+)\b(?:\s*[-–—.:]?\s*(.+))?$",
    re.IGNORECASE,
)
_ROMAN_SECTION_RE = re.compile(r"^\s*([IVXLCM]{1,8})\.\s+(.+)$")
_COLUMN_CLAUSE_RE = re.compile(
    r"^\s*(колонк(?:а|и)|граф(?:а|и)|поле|рядок)\s+([0-9IVXLCM]+)\s*[-–—:]\s*(.+)?$",
    re.IGNORECASE,
)
_ENTRY_INTO_FORCE_RE = re.compile(r"(набирає чинності|вводиться в дію)", re.IGNORECASE)
_DEFINITION_RE = re.compile(r"(визначає|термін|означає|у цьому .* означає)", re.IGNORECASE)
_FORM_HEADER_RE = re.compile(
    r"(заявка\b|схема\b|керівнику\b|органу з сертифікації\b|найменування\b|адреса\b|"
    r"вих\.\s*n|до розпорядження кабінету міністрів україни|система сертифікації укрсепро|"
    r"місячні посадові оклади|найменування\s+посад)",
    re.IGNORECASE,
)
_SIGNATURE_RE = re.compile(
    r"(виконавець:|вик\.:|телефон:|тел\.?:|підпис\)|міністр кабінету міністрів україни|"
    r"начальник управління|начальник гумвс україни|голова робочої групи)",
    re.IGNORECASE,
)
_QUESTIONNAIRE_RE = re.compile(
    r"^\s*(?:[a-zа-яіїєґ]\)|\d+[.)])\s*чи\b.*\?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_ATTACHMENT_RE = re.compile(
    r"^\s*(?:\d+[.)])\s*(копії\b|текст запиту\b|перелік документів\b|додаток\b)",
    re.IGNORECASE,
)
_FORM_REQUEST_ROW_RE = re.compile(
    r"(просить\s+провести\s+сертифікацію|відповідність\s+вимогам|"
    r"вимогам\s+зазначених\s+нормативних\s+документів|"
    r"правилами\s+системи(?:\s+укрсепро)?)",
    re.IGNORECASE,
)
_ROLE_LIST_RE = re.compile(
    r"^\s*[-\u2013\u2014\u2022]\s*(?:заступник|начальник|директор|голов[аи]|секретар|спеціаліст)\b",
    re.IGNORECASE,
)
_FORM_FOOTER_RE = re.compile(
    r"^(?:м\.\s*п\.|печатка\b.*дата\b|дата\b.*печатка\b|підпис\b.*дата\b|дата\b.*підпис\b)",
    re.IGNORECASE,
)
_FORM_INSTRUCTION_RE = re.compile(
    r"\b("
    r"потрібне\s+підкреслити|"
    r"непотрібне\s+закреслити|"
    r"вноситься\s+потрібне|"
    r"вписується\s+потрібне|"
    r"заповнюється\s+(?:заявником|судом|органом)|"
    r"не\s+заповнюється"
    r")\b",
    re.IGNORECASE,
)
_STAMP_RE = re.compile(r"^\s*(?:м\.\s*п\.|мп)\s*$", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(
    r"(?:_{4,}|\"_{2,}|_{2,}\"|_{2,}\)|\(\s*_{2,}|(?:19|20)\d{2}\s*р\.?$|___+)",
    re.IGNORECASE,
)
_CATALOG_HEADER_RE = re.compile(
    r"\b("
    r"номенклатур|"
    r"мережа\b|"
    r"реєстр\b|"
    r"спис(?:ок|ки)\b|"
    r"склад\b|"
    r"перелік\s+(?:судів|підприємств|організацій|установ|посад|статей|видатків|витрат)|"
    r"стат(?:ей|тя)\s+накладних\s+витрат|"
    r"витрати\s+на\s+оплату\s+праці|"
    r"зміст\s+і\s+характеристика\s+витрат"
    r")\b",
    re.IGNORECASE,
)
_HEADING_BLOCK_RE = re.compile(
    r"\b("
    r"схем(?:а|и)\b|"
    r"форма\s+n?\s*\d+|"
    r"журнал\b|"
    r"розрахунков(?:ий|а)\s+тариф|"
    r"категорі(?:ї|я)\s+транспортних\s+засобів"
    r")\b",
    re.IGNORECASE,
)
_STRICT_CATALOG_CONTEXT_RE = re.compile(
    r"\b("
    r"калькулювання\s+собівартості|"
    r"собівартості\s+продукції|"
    r"номенклатур|"
    r"стат(?:ей|тя)\s+накладних\s+витрат|"
    r"витрати\s+на\s+оплату\s+праці"
    r")\b",
    re.IGNORECASE,
)
_FORM_LABEL_RE = re.compile(r"^\(\s*[^)]+\)\s*$")
_FORM_CONTEXT_RE = re.compile(
    r"\b("
    r"ідентифікаційний\s+код\s+заявника|"
    r"телефон\s+телефакс\s+телекс|"
    r"державна\s+комісія\s+з\s+цінних\s+паперів|"
    r"дата\s+реєстрації\s+заяви|"
    r"дата\s+заповнення\s+заяви"
    r")\b",
    re.IGNORECASE,
)
_PAYMENT_FORM_RE = re.compile(
    r"\b("
    r"реєстраційн(?:ого|ий)\s+рахунк|"
    r"банк\s+платника|"
    r"одержувач|"
    r"сума\s+літерами|"
    r"призначення\s+платежу|"
    r"підпис\s+банку|"
    r"місце\s+печатки|"
    r"код\s+банку|"
    r"меморіальн(?:ого|ий)\s+ордер|"
    r"особова\s+картка|"
    r"продовження\s+таблиці|"
    r"контролер|"
    r"касир|"
    r"рах\.\s*n"
    r")\b",
    re.IGNORECASE,
)
_SHORT_SIGNATURE_LABEL_RE = re.compile(
    r"^\s*(?:керівник(?:\s+підприємства)?|головний\s+бухгалтер|місце\s+печатки)(?:\s+підпис)?\s*$",
    re.IGNORECASE,
)
_NOMINAL_LIST_ITEM_RE = re.compile(
    r"^\s*(?:[-\u2013\u2014\u2022]|\d+[.)])\s+"
    r"(?:схем\w+|поряд\w+|акт\w+|копі\w+|перелік\w+|довідк\w+|сертифікат\w+|"
    r"випробувальн\w+|територіальн\w+|складальн\w+|специфікаці\w+|необхідність\b|"
    r"стабільність\b|технічний\b|комісі\w+|орган\w+|документ\w+)",
    re.IGNORECASE,
)
_INFINITIVE_REQUIREMENT_RE = re.compile(
    r"^\s*(?:[-\u2013\u2014\u2022]|\d+[.)])?\s*"
    r"(?:виконувати|забезпечувати|сплатити|сплачувати|подати|подавати|надати|надавати|"
    r"повідомити|повідомляти|дотримуватися|зберігати|погодити|затвердити|"
    r"розподілити|перерахувати|видати|здійснювати|забезпечити|"
    r"підтримувати|використовувати|одержати|одержувати)\b",
    re.IGNORECASE,
)
_MULTIVALUE_THRESHOLD_ROW_RE = re.compile(
    r"^(?P<label>[^\d\n]{2,180}?)\s+\d+(?:[.,]\d+)?(?:\s+\d+(?:[.,]\d+)?){1,}",
    re.IGNORECASE,
)
_REASONING_CUE_RE = re.compile(
    r"\b("
    r"має|мають|повинен|повинні|зобов|заборон|дозвол|підляга|"
    r"затвердж|внести|вносить|скасов|припиня|набирає|вводиться|"
    r"штраф|санкц|відсот|грн|оклад|мінімаль|максималь|строк|термін"
    r")",
    re.IGNORECASE,
)
_STRONG_NORMATIVE_CUE_RE = re.compile(
    r"\b("
    r"має\s+право|"
    r"зобов|"
    r"повинен|повинні|"
    r"заборон|"
    r"підляга|"
    r"затвердж|"
    r"ввести|вводиться|"
    r"набирає\s+чинності|"
    r"не\s+пізніше|"
    r"протягом"
    r")\b",
    re.IGNORECASE,
)
_DECORATIVE_SEPARATOR_RE = re.compile(r"^[\s*._\-–—=|/\\()]+$")
_TABLE_SCAFFOLD_KEEP_CUES_RE = re.compile(
    r"\b(повин|має|зобов|заборон|дозвол|мінімаль|максималь|оклад|грн|відсот|кг|см|мм|дата)\b",
    re.IGNORECASE,
)
_TABLE_FRAGMENT_CELL_RE = re.compile(
    r"(?:"
    r"[А-Яа-яA-Za-z]+-$|"
    r"^[а-яіїєґa-z]{1,5}\b|"
    r"^\d+(?:[.,]\d+)?\s*(?:місяц(?:ів|і|я)|рок(?:ів|и)|км|годин)\b"
    r")",
    re.IGNORECASE,
)


def _compact_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _compose_context_prefix(*parts: str | None) -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        compact = _compact_spaces(str(part or ""))
        if not compact or compact in seen:
            continue
        seen.add(compact)
        ordered.append(compact[:220])
    return " | ".join(ordered[:3])


def _route_doc_profile(*, doc_type: str | None, doc_name: str | None, publisher: str | None) -> str:
    haystack = " ".join(
        part.strip().lower()
        for part in (doc_type or "", doc_name or "", publisher or "")
        if part and part.strip()
    )
    if "закон" in haystack:
        return "law"
    if "кабінет" in haystack or "кму" in haystack or "постанова" in haystack:
        return "cabinet_resolution"
    if "наказ" in haystack:
        return "ministerial_order"
    if "положення" in haystack or "порядок" in haystack or "регламент" in haystack:
        return "procedure_regulation"
    if "додаток" in haystack:
        return "appendix"
    if "таблиц" in haystack or "перелік" in haystack:
        return "table_heavy"
    return "generic"


def _classify_struct_kind(kind: str, text: str) -> str:
    stripped = text.lstrip()
    if _APPENDIX_RE.match(stripped):
        return "appendix"
    if kind == "full_text":
        return "fallback_unit"
    if kind in {"article", "part", "point", "subpoint", "paragraph"}:
        return kind
    if _TABLEISH_RE.search(stripped):
        return "table_row"
    return kind or "provision"


def _classify_section_role(
    *, kind: str, text: str, doc_profile: str, is_fallback_chunk: bool
) -> str:
    if is_fallback_chunk:
        return "fallback_recall"
    if _ENTRY_INTO_FORCE_RE.search(text):
        return "entry_into_force"
    if _DEFINITION_RE.search(text):
        return "definition"
    if kind in {"article", "part"} and "загальн" in text[:160].lower():
        return "general_provisions"
    if doc_profile == "procedure_regulation":
        return "procedure"
    if doc_profile == "appendix":
        return "appendix"
    if doc_profile == "table_heavy":
        return "structured_list"
    return "normative_unit"


def _appendix_id(text: str) -> str | None:
    match = _APPENDIX_RE.match(text.lstrip())
    if match and match.group(1):
        return match.group(1)
    return None


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _anchor_depth(anchor_path: str) -> int:
    return anchor_path.count("/") + 1 if anchor_path else 0


def _is_blank_line(line: _LineSpan) -> bool:
    return not line.line_no_nl.strip()


def _leading_ws(line: _LineSpan) -> int:
    return len(line.line_no_nl) - len(line.line_no_nl.lstrip(" "))


def _is_tableish_line(line: _LineSpan) -> bool:
    stripped = line.line_no_nl.strip()
    if len(stripped) < 3:
        return False
    if _APPENDIX_RE.match(stripped):
        return False
    if stripped.count("*") >= 2 and not _DECORATIVE_SEPARATOR_RE.fullmatch(stripped):
        return True
    if _TABLEISH_RE.search(stripped):
        return True
    return bool(re.search(r"\S(?:.* {2,}\S){2,}", stripped))


def _match_enumeration_marker(line: _LineSpan) -> tuple[str, str | None] | None:
    stripped = line.line_no_nl
    point_number = None
    for regex in _POINT_RE_LIST:
        match = regex.match(stripped)
        if match is not None:
            point_number = match.group(1)
            break
    if point_number is not None:
        return ("point", point_number)
    subpoint_match = _SUBPOINT_RE.match(stripped) or _SUBPOINT_DOT_RE.match(stripped)
    if subpoint_match is not None:
        return ("subpoint", subpoint_match.group(1).lower())
    if _BULLET_RE.match(stripped):
        return ("point", None)
    return None


def _normalize_anchor_token(raw: str | None, *, fallback: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-zА-Яа-яІЇЄҐіїєґ]+", "-", str(raw or "").strip().lower()).strip("-")
    return cleaned or fallback


def _match_section_heading(line: _LineSpan) -> tuple[str, str] | None:
    stripped = line.line_no_nl.strip()
    if not stripped or _APPENDIX_RE.match(stripped):
        return None
    keyword_match = _SECTION_KEYWORD_RE.match(stripped)
    if keyword_match is not None:
        marker = keyword_match.group(1)
        title = (keyword_match.group(2) or "").strip()
        if title:
            return (
                f"Розділ {marker} {title}".strip(),
                _normalize_anchor_token(marker, fallback="section"),
            )
        return (f"Розділ {marker}", _normalize_anchor_token(marker, fallback="section"))
    roman_match = _ROMAN_SECTION_RE.match(stripped)
    if roman_match is None:
        return None
    marker = roman_match.group(1)
    title = roman_match.group(2).strip()
    if not title or title[:1].islower():
        return None
    return (f"{marker}. {title}", _normalize_anchor_token(marker, fallback="section"))


def _match_column_clause(line: _LineSpan) -> tuple[str, str] | None:
    match = _COLUMN_CLAUSE_RE.match(line.line_no_nl.strip())
    if match is None:
        return None
    return (match.group(1).capitalize(), match.group(2))


def _looks_like_table_row_continuation(line: _LineSpan) -> bool:
    stripped = line.line_no_nl.strip()
    if not stripped:
        return False
    if _is_tableish_line(line):
        return False
    if _APPENDIX_RE.match(stripped):
        return False
    if _match_enumeration_marker(line) is not None:
        return False
    if _match_section_heading(line) is not None:
        return False
    if _match_column_clause(line) is not None:
        return False
    if _leading_ws(line) >= 2:
        return True
    return stripped[0].islower() or stripped.startswith(("(", ";", ","))


def _looks_like_table_header_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if "\n" in stripped:
        return False
    if sum(ch.isdigit() for ch in stripped) >= 2:
        return False
    cells = [cell.strip(" |-:") for cell in re.split(r"\t+|\|+| {2,}", stripped) if cell.strip()]
    if len(cells) < 2:
        return False
    header_tokens = (
        "назва",
        "код",
        "показник",
        "значення",
        "приміт",
        "дата",
        "номер",
        "опис",
        "одиниц",
        "посад",
        "оклад",
        "телефон",
        "телефакс",
        "телекс",
        "зміст",
        "характерист",
        "витрат",
        "всього",
        "квартал",
        "граф",
        "розділ",
        "рік",
        "column",
        "value",
    )
    if any(any(token in cell.lower() for token in header_tokens) for cell in cells):
        return True
    short_header_cells = len(cells) <= 3 and all(len(cell.split()) <= 2 for cell in cells)
    if short_header_cells and any(
        token in stripped.lower()
        for token in ("підлягає", "оплачено", "місце", "одержання", "кому", "розписка", "архіву")
    ):
        return True
    if len(cells) < 3:
        return False
    return all(len(cell.split()) <= 2 for cell in cells)


def _looks_like_table_scaffold_text(text: str) -> bool:
    compact = _compact_spaces(text)
    if not compact:
        return True
    if _DECORATIVE_SEPARATOR_RE.fullmatch(compact):
        return True

    stars = compact.count("*")
    if stars < 3:
        return False

    letters = sum(ch.isalpha() for ch in compact)
    digits = sum(ch.isdigit() for ch in compact)
    if letters <= 6 and digits <= 2:
        return True

    if compact.startswith("*") and compact.endswith("*"):
        cells = [
            cell.strip(" *|-:")
            for cell in re.split(r"\*+|\|+| {2,}", compact)
            if cell.strip(" *|-:")
        ]
        if len(cells) <= 1:
            return True
        if len(cells) >= 2 and all(len(cell) <= 3 for cell in cells):
            return True

    if compact.startswith("*") and digits == 0 and not _TABLE_SCAFFOLD_KEEP_CUES_RE.search(compact):
        return True

    cells = [
        cell.strip(" *|-:") for cell in re.split(r"\*+|\|+| {2,}", compact) if cell.strip(" *|-:")
    ]
    if (
        stars >= 5
        and digits <= 3
        and letters <= 24
        and not _TABLE_SCAFFOLD_KEEP_CUES_RE.search(compact)
    ):
        return True
    if re.search(r"\bвсього\b", compact, re.IGNORECASE) and re.search(
        r"\bквартал", compact, re.IGNORECASE
    ):
        return True
    if len(cells) >= 4:
        numericish = sum(
            1 for cell in cells if re.fullmatch(r"(?:\d{1,3}|[Xx]|№|N|п/п)", cell, re.IGNORECASE)
        )
        if numericish / len(cells) >= 0.7:
            return True
        if all(
            len(cell.split()) <= 2 for cell in cells
        ) and not _TABLE_SCAFFOLD_KEEP_CUES_RE.search(compact):
            return True
        fragmented = sum(
            1
            for cell in cells
            if _TABLE_FRAGMENT_CELL_RE.search(cell) or cell.endswith("-") or len(cell.split()) <= 2
        )
        if (
            fragmented / len(cells) >= 0.7
            and not _has_reasoning_cues(compact)
            and not re.search(r"[.;:]\s*$", compact)
        ):
            return True
    return bool(
        stars >= 4
        and len(cells) >= 3
        and not _has_reasoning_cues(compact)
        and not _has_strong_normative_cues(compact)
        and sum(1 for cell in cells if len(cell.split()) <= 2) / max(1, len(cells)) >= 0.7
    )


def _looks_like_placeholder_text(text: str) -> bool:
    compact = _compact_spaces(text)
    if not compact:
        return True
    if _PLACEHOLDER_RE.search(compact):
        return True
    if _FORM_INSTRUCTION_RE.search(compact):
        return True
    if compact.count("_") >= 6:
        return True
    return bool(compact.count('"') >= 2 and compact.count("_") >= 3)


def _looks_like_catalog_header_text(text: str) -> bool:
    compact = _compact_spaces(text)
    if not compact:
        return False
    return bool(_CATALOG_HEADER_RE.search(compact))


def _looks_like_heading_block_text(text: str) -> bool:
    compact = _compact_spaces(text)
    if not compact or _has_strong_normative_cues(compact):
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    uppercase_chars = sum(1 for ch in compact if ch.isalpha() and ch.isupper())
    alpha_chars = sum(1 for ch in compact if ch.isalpha())
    uppercase_ratio = uppercase_chars / max(1, alpha_chars)
    short_multiline = len(lines) <= 4 and all(len(line) <= 80 for line in lines)
    starts_like_title = bool(_HEADING_BLOCK_RE.search(compact))
    return starts_like_title or (short_multiline and uppercase_ratio >= 0.45)


def _has_reasoning_cues(text: str) -> bool:
    compact = _compact_spaces(text)
    if not compact:
        return False
    if _REASONING_CUE_RE.search(compact):
        return True
    if _INFINITIVE_REQUIREMENT_RE.match(compact):
        return True
    if re.search(
        r"\b\d+[.,]?\d*\s*(?:грн|%|відсот|рок(?:ів|и)?|дн(?:ів|і)?|місяц(?:ів|і)?)\b",
        compact,
        re.IGNORECASE,
    ):
        return True
    return bool(re.search(r"\b(?:до|після|протягом|не пізніше)\b", compact, re.IGNORECASE))


def _has_strong_normative_cues(text: str) -> bool:
    compact = _compact_spaces(text)
    if not compact:
        return False
    if _STRONG_NORMATIVE_CUE_RE.search(compact):
        return True
    return bool(re.search(r"\b\d+[.,]?\d*\s*(?:грн|%|відсот)\b", compact, re.IGNORECASE))


def _looks_like_threshold_table_row_text(text: str) -> bool:
    compact = _compact_spaces(text)
    if not compact or _looks_like_placeholder_text(compact):
        return False
    if _looks_like_table_header_text(compact) or _looks_like_table_scaffold_text(compact):
        return False
    if not _MULTIVALUE_THRESHOLD_ROW_RE.match(compact):
        return False
    numeric_hits = re.findall(r"\d+(?:[.,]\d+)?", compact)
    if len(numeric_hits) < 2:
        return False
    label = _MULTIVALUE_THRESHOLD_ROW_RE.match(compact)
    label_text = (label.group("label") if label else "").strip()
    return not (len(label_text) < 2 or label_text.isdigit())


def _looks_like_strict_catalog_context(text: str) -> bool:
    compact = _compact_spaces(text)
    if not compact:
        return False
    return bool(_STRICT_CATALOG_CONTEXT_RE.search(compact))


def _adjust_reasoning_policy(
    *,
    text: str,
    struct_kind: str,
    section_role: str,
    fallback_allowed_for_reasoning: bool,
    catalog_mode: bool = False,
    strict_catalog_mode: bool = False,
) -> tuple[str, bool]:
    compact = _compact_spaces(text)
    lower = compact.lower()
    if not compact:
        return section_role, False
    if struct_kind == "appendix":
        if _SIGNATURE_RE.search(compact) or _STAMP_RE.fullmatch(compact):
            return "signature_block", False
        if _looks_like_catalog_header_text(compact):
            return "catalog_header", False
        if _FORM_INSTRUCTION_RE.search(compact):
            return "form_field", False
        if _FORM_HEADER_RE.search(compact) or _looks_like_placeholder_text(compact):
            return "form_header", False
        return "appendix_header", False
    if _STAMP_RE.fullmatch(compact):
        return "signature_block", False
    if _SIGNATURE_RE.search(compact):
        return "signature_block", False
    if _ROLE_LIST_RE.match(compact):
        return "composition_member", False
    if _QUESTIONNAIRE_RE.match(compact):
        return "questionnaire_item", False
    if _ATTACHMENT_RE.match(compact):
        return "attachment_inventory", False
    if _FORM_LABEL_RE.fullmatch(compact):
        return "form_field", False
    if _SHORT_SIGNATURE_LABEL_RE.fullmatch(compact):
        return "signature_block", False
    if _FORM_CONTEXT_RE.search(compact):
        return "form_field", False
    if _PAYMENT_FORM_RE.search(compact):
        return "form_field", False
    if _FORM_INSTRUCTION_RE.search(compact):
        return "form_field", False
    if _looks_like_placeholder_text(compact):
        return "form_field", False
    if _DECORATIVE_SEPARATOR_RE.fullmatch(compact):
        return "decorative_separator", False
    if _FORM_HEADER_RE.search(compact):
        return "form_header", False
    if struct_kind == "table_row" and _FORM_FOOTER_RE.match(compact):
        return "signature_block", False
    if struct_kind == "table_row" and _looks_like_table_scaffold_text(compact):
        return "table_scaffold", False
    if struct_kind == "table_row" and _looks_like_table_header_text(compact):
        return "table_header", False
    if struct_kind == "table_row" and _FORM_REQUEST_ROW_RE.search(compact):
        return "form_field", False
    if (
        struct_kind == "table_row"
        and "найменування" in lower
        and ("оклад" in lower or "адреса" in lower)
    ):
        return "table_header", False
    if _looks_like_catalog_header_text(compact):
        return "catalog_header", False
    if struct_kind in {"paragraph", "enumeration_item"} and _looks_like_heading_block_text(text):
        return "catalog_header", False
    if struct_kind in {"paragraph", "enumeration_item"} and _INFINITIVE_REQUIREMENT_RE.match(
        compact
    ):
        return "normative_unit", True
    if struct_kind == "table_row" and _looks_like_threshold_table_row_text(compact):
        return "table_row", True
    if (
        struct_kind == "enumeration_item"
        and _NOMINAL_LIST_ITEM_RE.match(compact)
        and not _has_reasoning_cues(compact)
    ):
        return "catalog_item", False
    if (
        strict_catalog_mode
        and struct_kind == "table_row"
        and not _has_strong_normative_cues(compact)
    ):
        return "catalog_item", False
    if (
        strict_catalog_mode
        and struct_kind == "paragraph"
        and not _has_strong_normative_cues(compact)
    ):
        return "catalog_item", False
    if (
        catalog_mode
        and struct_kind in {"paragraph", "enumeration_item", "table_row"}
        and not _has_reasoning_cues(compact)
    ):
        return "catalog_item", False
    return section_role, fallback_allowed_for_reasoning


def _has_structured_fallback_signal(lines: list[_LineSpan], *, doc_profile: str) -> bool:
    appendix_hits = 0
    tableish_hits = 0
    enumeration_hits = 0
    section_hits = 0
    column_clause_hits = 0
    for line in lines:
        if _is_blank_line(line):
            continue
        if _APPENDIX_RE.match(line.line_no_nl):
            appendix_hits += 1
        if _is_tableish_line(line):
            tableish_hits += 1
        if _match_enumeration_marker(line) is not None:
            enumeration_hits += 1
        if _match_section_heading(line) is not None:
            section_hits += 1
        if _match_column_clause(line) is not None:
            column_clause_hits += 1
    if appendix_hits > 0:
        return True
    if tableish_hits >= 2:
        return True
    if enumeration_hits >= 2:
        return True
    if section_hits > 0 and (enumeration_hits > 0 or tableish_hits > 0 or column_clause_hits > 0):
        return True
    if column_clause_hits >= 2:
        return True
    return doc_profile in {"appendix", "table_heavy"} and (
        tableish_hits > 0 or enumeration_hits > 0
    )


def _fallback_citation_label(
    *,
    struct_kind: str,
    number: str | None,
    appendix_id: str | None,
    table_id: str | None,
) -> str:
    if struct_kind == "appendix":
        return f"Додаток {appendix_id or number or ''}".strip()
    if struct_kind == "table_row":
        if appendix_id:
            return f"Додаток {appendix_id}, рядок таблиці {number or '?'}"
        if table_id:
            return f"Таблиця, рядок {number or '?'}"
        return f"Рядок таблиці {number or '?'}"
    if struct_kind == "enumeration_item":
        if appendix_id:
            return f"Додаток {appendix_id}, пункт {number or '?'}"
        return f"Пункт переліку {number or '?'}"
    if appendix_id:
        return f"Додаток {appendix_id}, абзац {number or '?'}"
    return f"Абзац {number or '?'}"


def _build_fallback_span(
    *,
    text: str,
    anchor_path: str,
    kind: str,
    number: str | None,
    offset_start: int,
    offset_end: int,
    parent_anchor: str | None,
    doc_profile: str,
    appendix_id: str | None,
    table_id: str | None,
    fallback_allowed_for_reasoning: bool,
    struct_kind: str | None = None,
    citation_label: str | None = None,
    section_role: str | None = None,
    catalog_mode: bool = False,
    strict_catalog_mode: bool = False,
    context_prefix: str = "",
) -> ProvisionSpan | None:
    provision_text = text[offset_start:offset_end]
    if not provision_text.strip():
        return None
    resolved_struct_kind = struct_kind or _classify_struct_kind(kind, provision_text)
    resolved_role = section_role or _classify_section_role(
        kind=kind,
        text=provision_text,
        doc_profile=doc_profile,
        is_fallback_chunk=False,
    )
    adjusted_role, adjusted_allowed = _adjust_reasoning_policy(
        text=provision_text,
        struct_kind=resolved_struct_kind,
        section_role=resolved_role,
        fallback_allowed_for_reasoning=fallback_allowed_for_reasoning,
        catalog_mode=catalog_mode,
        strict_catalog_mode=strict_catalog_mode,
    )
    return ProvisionSpan(
        kind=kind,
        number=number,
        anchor_path=anchor_path,
        citation_label=citation_label
        or _fallback_citation_label(
            struct_kind=resolved_struct_kind,
            number=number,
            appendix_id=appendix_id,
            table_id=table_id,
        ),
        offset_start=offset_start,
        offset_end=offset_end,
        text=provision_text,
        parent_anchor=parent_anchor,
        depth=_anchor_depth(anchor_path),
        token_est=_estimate_tokens(provision_text),
        text_hash=_text_hash(provision_text),
        is_fallback_chunk=False,
        struct_kind=resolved_struct_kind,
        section_role=adjusted_role,
        lineage_path=anchor_path,
        appendix_id=appendix_id,
        table_id=table_id,
        fallback_allowed_for_reasoning=adjusted_allowed,
        context_prefix=context_prefix,
    )


def _collect_appendix_blocks(
    lines: list[_LineSpan],
) -> list[tuple[str, str | None, list[_LineSpan]]]:
    appendix_headers: list[tuple[int, str | None]] = []
    for idx, line in enumerate(lines):
        match = _APPENDIX_RE.match(line.line_no_nl)
        if match is not None:
            appendix_headers.append((idx, match.group(1)))
    if not appendix_headers:
        return [("body:1", None, lines)]

    blocks: list[tuple[str, str | None, list[_LineSpan]]] = []
    for pos, (start_idx, appendix_id_raw) in enumerate(appendix_headers, start=1):
        end_idx = appendix_headers[pos][0] if pos < len(appendix_headers) else len(lines)
        appendix_id = appendix_id_raw or str(pos)
        blocks.append((f"appendix:{appendix_id}", appendix_id, lines[start_idx:end_idx]))
    return blocks


def _parse_structured_fallback_units(
    *,
    text: str,
    lines: list[_LineSpan],
    doc_profile: str,
    doc_name: str | None = None,
) -> list[ProvisionSpan]:
    if not _has_structured_fallback_signal(lines, doc_profile=doc_profile):
        return []

    spans: list[ProvisionSpan] = []
    strict_catalog_mode = _looks_like_strict_catalog_context(doc_name or "")
    for anchor_root, appendix_id, block_lines in _collect_appendix_blocks(lines):
        if not block_lines:
            continue

        cursor = 0
        section_count = 0
        para_count = 0
        item_count = 0
        table_count = 0
        current_container_anchor = anchor_root
        current_parent_anchor = anchor_root if appendix_id is not None else None
        catalog_mode = strict_catalog_mode
        appendix_heading_text = ""
        current_section_heading_text = ""
        current_table_header_text = ""

        if appendix_id is not None:
            heading_end = 1
            while heading_end < len(block_lines):
                row = block_lines[heading_end]
                if (
                    _is_blank_line(row)
                    or _is_tableish_line(row)
                    or _match_enumeration_marker(row) is not None
                ):
                    break
                if _match_section_heading(row) is not None or _match_column_clause(row) is not None:
                    break
                heading_end += 1
                if heading_end >= 3:
                    break
            appendix_span = _build_fallback_span(
                text=text,
                anchor_path=anchor_root,
                kind="paragraph",
                number=appendix_id,
                offset_start=block_lines[0].start,
                offset_end=block_lines[heading_end - 1].end,
                parent_anchor=None,
                doc_profile="appendix",
                appendix_id=appendix_id,
                table_id=None,
                fallback_allowed_for_reasoning=True,
                struct_kind="appendix",
                catalog_mode=False,
                strict_catalog_mode=strict_catalog_mode,
                context_prefix="",
            )
            if appendix_span is not None:
                spans.append(appendix_span)
                catalog_mode = strict_catalog_mode or appendix_span.section_role in {
                    "catalog_header",
                    "form_header",
                }
                appendix_heading_text = _compact_spaces(appendix_span.text)
            cursor = heading_end

        while cursor < len(block_lines):
            line = block_lines[cursor]
            if _is_blank_line(line):
                cursor += 1
                continue

            section_heading = _match_section_heading(line)
            if section_heading is not None:
                section_count += 1
                para_count = 0
                item_count = 0
                table_count = 0
                title, marker = section_heading
                section_start = cursor
                section_end = cursor + 1
                while section_end < len(block_lines):
                    next_line = block_lines[section_end]
                    if _is_blank_line(next_line):
                        break
                    if _is_tableish_line(next_line):
                        break
                    if _match_enumeration_marker(next_line) is not None:
                        break
                    if _APPENDIX_RE.match(next_line.line_no_nl):
                        break
                    if _match_section_heading(next_line) is not None:
                        break
                    if _match_column_clause(next_line) is not None:
                        break
                    if section_end - section_start >= 1:
                        break
                    section_end += 1
                section_anchor = f"{anchor_root}/sec:{section_count:03d}-{marker}"
                span = _build_fallback_span(
                    text=text,
                    anchor_path=section_anchor,
                    kind="paragraph",
                    number=str(section_count),
                    offset_start=block_lines[section_start].start,
                    offset_end=block_lines[section_end - 1].end,
                    parent_anchor=anchor_root if appendix_id is not None else None,
                    doc_profile=doc_profile,
                    appendix_id=appendix_id,
                    table_id=None,
                    fallback_allowed_for_reasoning=False,
                    citation_label=title,
                    section_role="appendix_section",
                    catalog_mode=False,
                    strict_catalog_mode=strict_catalog_mode,
                    context_prefix=_compose_context_prefix(appendix_heading_text),
                )
                if span is not None:
                    spans.append(span)
                    if strict_catalog_mode or span.section_role == "catalog_header":
                        catalog_mode = True
                    current_section_heading_text = _compact_spaces(span.text)
                    current_table_header_text = ""
                current_container_anchor = section_anchor
                current_parent_anchor = section_anchor
                cursor = section_end
                continue

            column_clause = _match_column_clause(line)
            if column_clause is not None:
                label, column_number = column_clause
                start_idx = cursor
                end_idx = cursor + 1
                while end_idx < len(block_lines):
                    next_line = block_lines[end_idx]
                    if _is_blank_line(next_line):
                        break
                    if _is_tableish_line(next_line):
                        break
                    if _match_enumeration_marker(next_line) is not None:
                        break
                    if _APPENDIX_RE.match(next_line.line_no_nl):
                        break
                    if _match_section_heading(next_line) is not None:
                        break
                    if _match_column_clause(next_line) is not None:
                        break
                    end_idx += 1
                column_token = _normalize_anchor_token(column_number, fallback=str(cursor + 1))
                span = _build_fallback_span(
                    text=text,
                    anchor_path=f"{current_container_anchor}/column:{column_token}",
                    kind="paragraph",
                    number=column_number,
                    offset_start=block_lines[start_idx].start,
                    offset_end=block_lines[end_idx - 1].end,
                    parent_anchor=current_parent_anchor,
                    doc_profile="table_heavy",
                    appendix_id=appendix_id,
                    table_id=f"{current_container_anchor}/columns",
                    fallback_allowed_for_reasoning=True,
                    struct_kind="table_row",
                    citation_label=f"{label} {column_number}",
                    section_role="table_clause",
                    catalog_mode=catalog_mode,
                    strict_catalog_mode=strict_catalog_mode,
                    context_prefix=_compose_context_prefix(
                        appendix_heading_text,
                        current_section_heading_text,
                        current_table_header_text,
                    ),
                )
                if span is not None:
                    spans.append(span)
                cursor = end_idx
                continue

            marker = _match_enumeration_marker(line)
            if marker is not None:
                item_kind, marker_value = marker
                start_idx = cursor
                end_idx = cursor + 1
                while end_idx < len(block_lines):
                    next_line = block_lines[end_idx]
                    if _is_blank_line(next_line) or _is_tableish_line(next_line):
                        break
                    if _match_enumeration_marker(next_line) is not None or _APPENDIX_RE.match(
                        next_line.line_no_nl
                    ):
                        break
                    if (
                        _match_section_heading(next_line) is not None
                        or _match_column_clause(next_line) is not None
                    ):
                        break
                    end_idx += 1
                item_count += 1
                number = marker_value or str(item_count)
                item_anchor = f"{current_container_anchor}/item:{item_count:04d}"
                span = _build_fallback_span(
                    text=text,
                    anchor_path=item_anchor,
                    kind=item_kind,
                    number=number,
                    offset_start=block_lines[start_idx].start,
                    offset_end=block_lines[end_idx - 1].end,
                    parent_anchor=current_parent_anchor,
                    doc_profile=doc_profile,
                    appendix_id=appendix_id,
                    table_id=None,
                    fallback_allowed_for_reasoning=True,
                    struct_kind="enumeration_item",
                    catalog_mode=catalog_mode,
                    strict_catalog_mode=strict_catalog_mode,
                    context_prefix=_compose_context_prefix(
                        appendix_heading_text,
                        current_section_heading_text,
                    ),
                )
                if span is not None:
                    spans.append(span)
                cursor = end_idx
                continue

            if _is_tableish_line(line):
                table_count += 1
                table_id = f"{current_container_anchor}/table:{table_count:03d}"
                row_idx = 1
                header_idx = 1
                seen_data_row = False
                current_table_header_text = ""
                while cursor < len(block_lines) and _is_tableish_line(block_lines[cursor]):
                    row_start = cursor
                    row_end = cursor + 1
                    while row_end < len(block_lines) and _looks_like_table_row_continuation(
                        block_lines[row_end]
                    ):
                        row_end += 1
                    row_text = text[block_lines[row_start].start : block_lines[row_end - 1].end]
                    is_header = (not seen_data_row) and _looks_like_table_header_text(row_text)
                    if is_header:
                        row_anchor = f"{table_id}/header:{header_idx:04d}"
                        row_number = str(header_idx)
                        header_idx += 1
                    else:
                        row_anchor = f"{table_id}/row:{row_idx:04d}"
                        row_number = str(row_idx)
                        row_idx += 1
                        seen_data_row = True
                    row_span = _build_fallback_span(
                        text=text,
                        anchor_path=row_anchor,
                        kind="paragraph",
                        number=row_number,
                        offset_start=block_lines[row_start].start,
                        offset_end=block_lines[row_end - 1].end,
                        parent_anchor=current_parent_anchor,
                        doc_profile="table_heavy",
                        appendix_id=appendix_id,
                        table_id=table_id,
                        fallback_allowed_for_reasoning=not is_header,
                        struct_kind="table_row",
                        section_role="table_header" if is_header else "table_row",
                        citation_label=(
                            f"Додаток {appendix_id}, заголовок таблиці {row_number}"
                            if appendix_id is not None and is_header
                            else f"Заголовок таблиці {row_number}"
                            if is_header
                            else None
                        ),
                        catalog_mode=catalog_mode,
                        strict_catalog_mode=strict_catalog_mode,
                        context_prefix=_compose_context_prefix(
                            appendix_heading_text,
                            current_section_heading_text,
                            current_table_header_text,
                        ),
                    )
                    if row_span is not None:
                        spans.append(row_span)
                        if is_header:
                            current_table_header_text = _compose_context_prefix(
                                current_table_header_text,
                                row_span.text,
                            )
                    cursor = row_end
                    while cursor < len(block_lines) and _is_blank_line(block_lines[cursor]):
                        cursor += 1
                    if cursor >= len(block_lines) or not _is_tableish_line(block_lines[cursor]):
                        break
                current_table_header_text = ""
                continue

            start_idx = cursor
            end_idx = cursor + 1
            while end_idx < len(block_lines):
                next_line = block_lines[end_idx]
                if _is_blank_line(next_line):
                    break
                if _is_tableish_line(next_line):
                    break
                if _match_enumeration_marker(next_line) is not None:
                    break
                if _APPENDIX_RE.match(next_line.line_no_nl):
                    break
                if _match_section_heading(next_line) is not None:
                    break
                if _match_column_clause(next_line) is not None:
                    break
                end_idx += 1
            para_count += 1
            para_anchor = f"{current_container_anchor}/para:{para_count:04d}"
            span = _build_fallback_span(
                text=text,
                anchor_path=para_anchor,
                kind="paragraph",
                number=str(para_count),
                offset_start=block_lines[start_idx].start,
                offset_end=block_lines[end_idx - 1].end,
                parent_anchor=current_parent_anchor,
                doc_profile=doc_profile,
                appendix_id=appendix_id,
                table_id=None,
                fallback_allowed_for_reasoning=True,
                catalog_mode=catalog_mode,
                strict_catalog_mode=strict_catalog_mode,
                context_prefix=_compose_context_prefix(
                    appendix_heading_text,
                    current_section_heading_text,
                ),
            )
            if span is not None:
                spans.append(span)
                if strict_catalog_mode or span.section_role == "catalog_header":
                    catalog_mode = True
            cursor = end_idx

    seen_anchors: set[str] = set()
    deduped_spans: list[ProvisionSpan] = []
    for span in spans:
        if span.anchor_path in seen_anchors:
            continue
        seen_anchors.add(span.anchor_path)
        deduped_spans.append(span)
    return deduped_spans


def _chunk_full_text(
    *,
    text: str,
    chunk_chars: int,
    overlap_chars: int,
    doc_profile: str,
) -> list[ProvisionSpan]:
    """Split fallback full text into deterministic chunks."""
    safe_chunk = max(400, chunk_chars)
    safe_overlap = max(0, min(overlap_chars, safe_chunk // 3))
    n = len(text)
    if n <= safe_chunk:
        chunk_text = text
        return [
            ProvisionSpan(
                kind="full_text",
                number=None,
                anchor_path="full/chunk:0001",
                citation_label="Повний текст, фрагмент 1",
                offset_start=0,
                offset_end=n,
                text=chunk_text,
                parent_anchor="full",
                depth=_anchor_depth("full/chunk:0001"),
                token_est=_estimate_tokens(chunk_text),
                text_hash=_text_hash(chunk_text),
                is_fallback_chunk=True,
                struct_kind="fallback_unit",
                section_role="fallback_recall",
                lineage_path="full/chunk:0001",
                appendix_id=None,
                table_id=None,
                fallback_allowed_for_reasoning=False,
            )
        ]

    spans: list[ProvisionSpan] = []
    start = 0
    idx = 1
    while start < n:
        end = min(n, start + safe_chunk)
        if end < n:
            # Prefer line boundary when possible to preserve legal sentence structure.
            cut = text.rfind("\n", start + safe_chunk // 2, end)
            if cut > start:
                end = cut
        if end <= start:
            end = min(n, start + safe_chunk)
        chunk_text = text[start:end]
        anchor = f"full/chunk:{idx:04d}"
        spans.append(
            ProvisionSpan(
                kind="full_text",
                number=str(idx),
                anchor_path=anchor,
                citation_label=f"Повний текст, фрагмент {idx}",
                offset_start=start,
                offset_end=end,
                text=chunk_text,
                parent_anchor="full",
                depth=_anchor_depth(anchor),
                token_est=_estimate_tokens(chunk_text),
                text_hash=_text_hash(chunk_text),
                is_fallback_chunk=True,
                struct_kind="fallback_unit",
                section_role="fallback_recall" if doc_profile != "appendix" else "appendix",
                lineage_path=anchor,
                appendix_id=None,
                table_id=None,
                fallback_allowed_for_reasoning=False,
            )
        )
        if end >= n:
            break
        start = max(end - safe_overlap, start + 1)
        idx += 1

    return spans


def _apply_legal_unit_signals(
    *,
    spans: list[ProvisionSpan],
    doc_type: str | None,
    doc_name: str | None,
    jurisdiction: str,
) -> list[ProvisionSpan]:
    if not spans:
        return []
    from polisyos.lex.batch.jurisdictions import get_jurisdiction_plugin
    from polisyos.lex.batch.legal_unit import build_legal_unit_signals, infer_doc_family_for_unit

    doc_family = infer_doc_family_for_unit(
        doc_type=str(doc_type or ""),
        doc_name=str(doc_name or ""),
        provision_rows=[
            {
                "struct_kind": span.struct_kind,
                "section_role": span.section_role,
                "appendix_id": span.appendix_id,
                "table_id": span.table_id,
            }
            for span in spans
        ],
    )
    jurisdiction_plugin = get_jurisdiction_plugin(jurisdiction)
    enriched: list[ProvisionSpan] = []
    for span in spans:
        signals = build_legal_unit_signals(
            text=span.text,
            struct_kind=span.struct_kind or span.kind,
            section_role=span.section_role,
            fallback_allowed_for_reasoning=span.fallback_allowed_for_reasoning,
            doc_family=doc_family,
            doc_title=str(doc_name or ""),
            citation_label=span.citation_label,
            context_prefix=span.context_prefix,
            jurisdiction_plugin=jurisdiction_plugin,
        )
        enriched.append(
            replace(
                span,
                legal_unit_subtype=signals.legal_unit_subtype,
                legal_unit_micro_subtype=signals.legal_unit_micro_subtype,
                route_class=signals.route_class,
                empty_spo_retry_eligible=signals.empty_spo_retry_eligible,
                audit_miss_prone=signals.audit_miss_prone,
                reference_bearing=signals.reference_bearing,
                threshold_bearing=signals.threshold_bearing,
            )
        )
    return enriched


def extract_provisions(
    text: str,
    *,
    jurisdiction: str = "UA",
    doc_type: str | None = None,
    doc_name: str | None = None,
    publisher: str | None = None,
    enable_tier_b: bool = True,
    enable_paragraphs: bool = True,
    fallback_chunk_chars: int = 1800,
    fallback_chunk_overlap: int = 200,
) -> list[ProvisionSpan]:
    """Extract provisions from legal text using regex.

    Returns a flat list of ProvisionSpan with the actual text slice.
    If no articles are detected, returns the whole text as a single
    ``full_text`` provision (so that every document yields at least one span).
    """
    if not text or not text.strip():
        return []

    doc_profile = _route_doc_profile(
        doc_type=doc_type,
        doc_name=doc_name,
        publisher=publisher,
    )
    lines = _iter_lines_with_offsets(text)

    try:
        ruleset = _ruleset_for(jurisdiction)
    except Exception:
        # Unsupported jurisdiction — chunk whole text instead of monolithic full_text.
        logger.debug(
            "Unsupported jurisdiction ruleset for %r, falling back to chunked full text",
            jurisdiction,
        )
        return _chunk_full_text(
            text=text,
            chunk_chars=fallback_chunk_chars,
            overlap_chars=fallback_chunk_overlap,
            doc_profile=doc_profile,
        )

    options = LexStructureOptions(
        enable_tier_b=enable_tier_b,
        enable_paragraphs=enable_paragraphs,
        require_articles=False,
    )

    candidates, _quality_issues = _build_candidates(
        text=text,
        lines=lines,
        ruleset=ruleset,
        options=options,
    )

    if not candidates:
        structured_fallback = _parse_structured_fallback_units(
            text=text,
            lines=lines,
            doc_profile=doc_profile,
            doc_name=doc_name,
        )
        if structured_fallback:
            return _apply_legal_unit_signals(
                spans=structured_fallback,
                doc_type=doc_type,
                doc_name=doc_name,
                jurisdiction=jurisdiction,
            )
        # No articles found — chunk text to avoid giant prompts.
        return _apply_legal_unit_signals(
            spans=_chunk_full_text(
                text=text,
                chunk_chars=fallback_chunk_chars,
                overlap_chars=fallback_chunk_overlap,
                doc_profile=doc_profile,
            ),
            doc_type=doc_type,
            doc_name=doc_name,
            jurisdiction=jurisdiction,
        )

    spans: list[ProvisionSpan] = []
    seen_anchors: dict[str, int] = {}
    for c in candidates:
        provision_text = text[c.offset_start : c.offset_end]
        if not provision_text.strip():
            continue
        anchor = c.anchor_path
        seen_anchors[anchor] = seen_anchors.get(anchor, 0) + 1
        if seen_anchors[anchor] > 1:
            anchor = f"{anchor}/dup:{seen_anchors[anchor] - 1}"
        spans.append(
            ProvisionSpan(
                kind=c.kind,
                number=c.number,
                anchor_path=anchor,
                citation_label=_citation_label(c.kind, anchor, jurisdiction),
                offset_start=c.offset_start,
                offset_end=c.offset_end,
                text=provision_text,
                parent_anchor=c.parent_anchor_path,
                depth=_anchor_depth(anchor),
                token_est=_estimate_tokens(provision_text),
                text_hash=_text_hash(provision_text),
                is_fallback_chunk=False,
                struct_kind=_classify_struct_kind(c.kind, provision_text),
                section_role=_classify_section_role(
                    kind=c.kind,
                    text=provision_text,
                    doc_profile=doc_profile,
                    is_fallback_chunk=False,
                ),
                lineage_path=anchor,
                appendix_id=_appendix_id(provision_text),
                table_id=anchor if _TABLEISH_RE.search(provision_text[:200]) else None,
                fallback_allowed_for_reasoning=True,
            )
        )

    return _apply_legal_unit_signals(
        spans=spans,
        doc_type=doc_type,
        doc_name=doc_name,
        jurisdiction=jurisdiction,
    )
