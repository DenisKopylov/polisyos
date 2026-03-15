"""Deterministic SPO extractor used before LLM routing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

from polisyos.lex.batch.canonicalizers import (
    canonicalize_action,
    canonicalize_norm_type,
    extract_thresholds_from_text,
)
from polisyos.lex.knowledge.types import SPOCandidate


@dataclass(frozen=True)
class DeterministicExtraction:
    """Result of deterministic extraction for one provision."""

    candidates: list[SPOCandidate]
    confidence: float
    reason_codes: list[str]


_ENTRY_INTO_FORCE_RE = re.compile(
    r"(?:набирає|набуває)\s+чинності?\s*(.{0,160})",
    re.IGNORECASE,
)
_REPEAL_RE = re.compile(
    r"визнати\s+(?:таки(?:м|ми)\s*,?\s*що\s*втратил(?:и|а|о)\s+чинність|такими\s*що\s*втратили\s+чинність)\s*(.{0,240})",
    re.IGNORECASE,
)
_AMEND_RE = re.compile(
    r"(?:внести\s+(?:такі\s+)?зміни|викласти\s+в\s+(?:такій\s+)?(?:новій\s+)?редакції)",
    re.IGNORECASE,
)
_APPROVE_RE = re.compile(
    r"(?:затвердити|схвалити|ухвалити|прийняти)\s+(.{8,180})",
    re.IGNORECASE,
)
_REQUIRE_RE = re.compile(
    r"(?:повинен|повинна|повинні|зобов[’'`ʼ]яз(?:аний|ана|ати|атися)?|має\s+забезпечити|необхідно)",
    re.IGNORECASE,
)
_PROHIBIT_RE = re.compile(
    r"(?:забороняється|заборонено|не\s+має\s+права|не\s+допускається)",
    re.IGNORECASE,
)
_DELEGATE_RE = re.compile(
    r"(?:доручити|уповноважити|покласти\s+на)",
    re.IGNORECASE,
)
_PERCENT_OR_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|грн|дн(?:ів|і)?|рок(?:ів|и)?)\b", re.IGNORECASE)

# Enhanced extractors: capture actual object for prohibit/require
_PROHIBIT_OBJECT_RE = re.compile(
    r"(?:забороня(?:ється|ти|ється)|заборонено|не\s+допускається|не\s+має\s+права)\s+(.{5,250}?)(?:\.|;|,\s*крім)",
    re.IGNORECASE,
)
_REQUIRE_OBJECT_RE = re.compile(
    r"(?:повинен|повинна|повинні|зобов[''`ʼ]яз(?:аний|ана|ані))\s+(.{5,250}?)(?:\.|;)",
    re.IGNORECASE,
)

# Citation amendment: "статтю N викласти/замінити/доповнити"
_AMEND_CITATION_RE = re.compile(
    r"(?:статтю|пункт|частину|абзац)\s+(\d+(?:\.\d+)?)\s+(?:викласти|замінити|доповнити|виключити)",
    re.IGNORECASE,
)

# Numbered list items: "1) something; 2) something;"
_LIST_ITEM_RE = re.compile(r"^\s*\d+\)\s+(.+?)(?:;\s*$|$)", re.MULTILINE)
_ARTICLE_PREFIX_RE = re.compile(
    r"^\s*(?:стаття|article)\s+[\dIVXLCА-Яа-яіїєґ.\-]+\s*[.)]?\s*",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯІЇЄҐ])")
_CLAUSE_SPLIT_RE = re.compile(r"\s*;\s+|\s*:\s+(?=[A-ZА-ЯІЇЄҐ])")
_INLINE_SUBCLAUSE_SPLIT_RE = re.compile(r"\s+(?=\d+\.\d+\.\s+)")
_RIGHT_RE = re.compile(
    r"(?P<subject>[^.]{2,180}?)\s+ма(?:є|ють)\s+право\s+(?P<object>[^.]{4,260})",
    re.IGNORECASE,
)
_RIGHTS_LIST_RE = re.compile(
    r"(?P<subject>[^.]{2,180}?)\s+ма(?:є|ють)\s+право\s*:\s*(?P<object>.+)",
    re.IGNORECASE | re.DOTALL,
)
_GUARANTEE_RE = re.compile(
    r"(?:(?P<subject>[^.]{2,120}?)\s+)?гаранту(?:ється|ються)\s+(?P<object>[^.]{4,260})",
    re.IGNORECASE,
)
_TREATY_TITLE_RE = re.compile(r"(угода|договір|конвенц|протокол)", re.IGNORECASE)
_RESOLUTION_TITLE_RE = re.compile(r"(указ|постанова|розпорядження|рішення)", re.IGNORECASE)
_TREATY_OBLIGATION_RE = re.compile(
    r"(?P<subject>(?:(?:кожна|будь-яка)\s+(?:договірна\s+)?сторона|договірні\s+сторони)[^.]{0,80}?)\s+"
    r"(?:(?:зобов['’`ʼ]язується|зобов['’`ʼ]язуються|повинна|повинні|має|мають))\s+"
    r"(?P<object>[^.]{6,280})",
    re.IGNORECASE,
)
_TREATY_COOPERATION_RE = re.compile(
    r"(?:співробітництво|взаємодія)\s+(?:здійснюється|провадиться|забезпечується)\s+(?P<object>[^.]{6,220})",
    re.IGNORECASE,
)
_TREATY_FUTURE_COOPERATION_RE = re.compile(
    r"(?P<subject>(?:договірні\s+сторони|кожна\s+договірна\s+сторона|сторони))\s+"
    r"(?:будуть\s+)?(?P<lemma>здійснювати|розвивати|сприяти|забезпечувати)\s+"
    r"(?P<object>[^.]{6,280})",
    re.IGNORECASE,
)
_TREATY_DELEGATION_RE = re.compile(
    r"(?P<subject>(?:договірні\s+сторони|сторони))\s+доручають\s+(?P<object>[^.]{6,280})",
    re.IGNORECASE,
)
_RATIFICATION_RE = re.compile(
    r"(?:ратифікувати|схвалити|затвердити)\s+(?P<object>[^.]{6,220})",
    re.IGNORECASE,
)
_IMPLEMENTATION_MANDATE_RE = re.compile(
    r"(?P<subject>[^.]{2,140}?)\s+(?:забезпечує|здійснює|організовує|подає|повідомляє)\s+(?P<object>[^.]{6,240})",
    re.IGNORECASE,
)
_IMPERATIVE_MANDATE_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>надіслати|підготувати|забезпечити|організувати|подати|повідомити|"
    r"розподілити|перерахувати|видати)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_DEFINED_BY_LAW_RE = re.compile(
    r"(?P<object>[^.]{4,260}?)\s+визнача(?:ється|ються)\s+(?:лише\s+|виключно\s+)?законом",
    re.IGNORECASE,
)
_RECOGNIZED_AS_RE = re.compile(
    r"(?P<subject>[^.]{2,220}?)\s+визна(?:ється|ються)\s+(?P<object>[^.]{4,260})",
    re.IGNORECASE,
)
_EXISTS_RE = re.compile(
    r"(?:(?P<scope>в\s+україні)\s+)?існу(?:є|ють)\s+(?P<object>[^.]{4,220})",
    re.IGNORECASE,
)
_DECLARATIVE_IS_RE = re.compile(
    r"(?P<subject>[^.]{2,160}?)\s+є\s+(?P<object>[^.]{4,260})",
    re.IGNORECASE,
)
_DASH_DEFINITION_RE = re.compile(
    r"^(?P<subject>[^.\n]{2,120}?)\s+[-–—]\s+(?P<object>[^.\n]{4,220})",
    re.IGNORECASE,
)
_DASH_THIS_IS_RE = re.compile(
    r"^(?P<subject>[^.\n]{2,200}?)\s*[-–—]\s*це\s+(?P<object>[^.\n]{8,360})",
    re.IGNORECASE,
)
_LIST_DEFINITION_RE = re.compile(
    r"(?P<subject>[^.\n:]{2,180}?)\s+(?:є|становлять)\s*:\s*(?P<object>.+)",
    re.IGNORECASE | re.DOTALL,
)
_AMEND_WORDING_RE = re.compile(
    r"(?P<object>(?:(?:у|в)\s+(?:статті|частині|пункті|абзаці)\s+[^:;\n]{1,80}\s*:\s*)?"
    r"[^.]{0,260}?\b(?:замінити|доповнити|виключити)\s+слов(?:а|ами)[^.]{0,260})",
    re.IGNORECASE,
)
_PRINCIPLES_LIST_RE = re.compile(
    r"(?P<subject>[^.]{2,200}?)\s+(?:здійснюється|здійснюються|ґрунтується|ґрунтуються)\s+"
    r"(?:на\s+основі|за\s+принципами?)\s+(?:таких\s+)?(?:принципів|засад)\s*:\s*(?P<object>.+)",
    re.IGNORECASE | re.DOTALL,
)
_APPLIES_SCOPE_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+поширюється\s+на\s+"
    r"(?P<object>[^.;]{6,280}?)(?=(?:\s+(?:та|і)\s+встановлює)|[.;]|$)",
    re.IGNORECASE,
)
_ESTABLISHES_ORDER_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+встановлює\s+(?P<object>порядок[^.;]{4,260})",
    re.IGNORECASE,
)
_SUBJECT_REQUIRE_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>повинен|повинна|повинні|зобов['’`ʼ]язан(?:ий|а|і)?|зобов['’`ʼ]язується|"
    r"зобов['’`ʼ]язуються|має\s+забезпечити|мають\s+забезпечити|забезпечує|забезпечують)\s+"
    r"(?P<object>[^.;]{6,280})",
    re.IGNORECASE,
)
_SUBJECT_PROHIBIT_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>не\s+має\s+права|не\s+мають\s+права|не\s+допускається|не\s+допускаються|"
    r"забороняється|забороняються|не\s+може|не\s+можуть)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_SUBJECT_PERMISSION_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>має\s+право|мають\s+право|може|можуть)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_TEMPORAL_APPLICABILITY_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>застосовується|застосовуються|діє|діють|набирає\s+чинності|набирають\s+чинності)\s+"
    r"(?P<object>[^.;]{6,220})",
    re.IGNORECASE,
)
_SANCTION_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>тягне\s+за\s+собою|карається|штрафується)\s+"
    r"(?P<object>[^.;]{6,220})",
    re.IGNORECASE,
)
_EXCEPTION_RE = re.compile(
    r"(?:крім\s+випадків|якщо\s+інше\s+не\s+передбачено)\s+(?P<object>[^.;]{6,220})",
    re.IGNORECASE,
)
_PASSIVE_PROCEDURE_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+"
    r"(?P<lemma>проводиться|проводяться|здійснюється|здійснюються|розраховується|розраховуються)\s+"
    r"(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_SUBJECT_TO_RE = re.compile(
    r"(?P<subject>[^.;:]{2,180}?)\s+підляга(?:є|ють)\s+(?P<object>[^.;]{6,240})",
    re.IGNORECASE,
)
_DEONTIC_MARKER_RE = re.compile(
    r"(повинен|повинна|повинні|зобов|заборон|не допускається|не може бути|має право|гарантується|гарантуються)",
    re.IGNORECASE,
)
_CONSTITUTIONAL_TITLE_RE = re.compile(r"конституц", re.IGNORECASE)
_CODE_TITLE_RE = re.compile(r"кодекс", re.IGNORECASE)
_BASIC_LAW_TITLE_RE = re.compile(r"основи\s+законодавства", re.IGNORECASE)
_APPROVAL_BUNDLE_RE = re.compile(
    r"(?P<lemma>затвердити|затверджено|затверджений|затверджена|схвалити|схвалено|погодити|погоджено|доручити)\s+(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_ANNEX_RE = re.compile(r"(додат(?:ок|ки)\s*(?:N|№)?\s*[\w\-]*)", re.IGNORECASE)
_THRESHOLD_ROW_RE = re.compile(
    r"^(?P<subject>[^\n.;]{2,160}?)\s{2,}(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>%|грн|коп|рок(?:ів|и)?|дн(?:ів|і)?|місяц(?:ів|і)?|кг|тонн(?:и)?)\b",
    re.IGNORECASE,
)
_MULTIVALUE_THRESHOLD_ROW_RE = re.compile(
    r"^(?P<subject>[^\d\n.;]{2,180}?)\s+(?P<values>\d+(?:[.,]\d+)?(?:\s+\d+(?:[.,]\d+)?){1,})(?:\s*(?P<unit>%|грн|коп|тис\.?(?:куб\.?\s*метрів)?|га|кг|тонн(?:и)?)\b)?",
    re.IGNORECASE,
)
_APPLICANT_ACTION_RE = re.compile(
    r"(?:(?P<subject>заявник|заявники|суб['’`ʼ]єкт(?:\s+господарювання)?)\s+)?"
    r"(?P<lemma>подає|подати|подати\s+до|надати|надає|повідомити|повідомляє|дода(?:ти|є)|зобов['’`ʼ]язується)\s+"
    r"(?P<object>[^.;]{5,260})",
    re.IGNORECASE,
)
_APPLICATION_CONDITION_RE = re.compile(
    r"(за\s+умови\s+[^.;]{6,220}|у\s+разі\s+[^.;]{6,220}|за\s+наявності\s+[^.;]{6,220})",
    re.IGNORECASE,
)
_APPLICATION_BULLET_RE = re.compile(
    r"^\s*(?:[-\u2013\u2014\u2022]|\d+[.)])?\s*"
    r"(?P<lemma>виконувати|забезпечувати|сплатити|сплачувати|подати|подавати|надати|надавати|"
    r"повідомити|повідомляти|дотримуватися|зберігати|здійснювати|використовувати|"
    r"одержати|одержувати)\s+"
    r"(?P<object>[^.;]{4,240})",
    re.IGNORECASE,
)
_MANDATORY_EXECUTION_RE = re.compile(
    r"(?P<subject>[^.;:]{2,220}?)\s+є\s+обов['’`ʼ]язков(?:им|ими)\s+для\s+виконання\s+(?P<object>[^.;]{6,260})",
    re.IGNORECASE,
)
_COMPETENCE_LIST_RE = re.compile(
    r"до\s+компетенції\s+(?P<subject>[^:.;]{4,180})\s+належ(?:ить|ать)\s*:\s*(?P<object>.+)",
    re.IGNORECASE | re.DOTALL,
)
_PERMISSION_CONDITION_RE = re.compile(
    r"(?P<object>[^.;]{6,220}?)\s+за\s+умови\s+(?P<condition>[^.;]{6,180})",
    re.IGNORECASE,
)


def _build_candidate(
    *,
    subject_uk: str,
    predicate: str,
    object_uk: str,
    norm_type: str,
    fact_text: str,
    quote: str,
    confidence: float,
    thresholds_text: str | None = None,
) -> SPOCandidate:
    action_canon, _ = canonicalize_action(predicate)
    norm_canon, _ = canonicalize_norm_type(norm_type)
    thresholds = extract_thresholds_from_text(thresholds_text or quote, applies_to=object_uk)
    return SPOCandidate.model_validate(
        {
            "subject_en": subject_uk,
            "subject_uk": subject_uk,
            "predicate": predicate,
            "object_en": object_uk,
            "object_uk": object_uk,
            "fact_text": fact_text,
            "confidence": max(0.0, min(1.0, confidence)),
            "norm_type": norm_type,
            "action_raw": predicate,
            "action_canon": action_canon,
            "norm_type_raw": norm_type,
            "norm_type_canon": norm_canon,
            "source_quote_uk": quote[:500],
            "thresholds": [threshold.model_dump(mode="json") for threshold in thresholds],
        }
    )


def _clip_text(text: str, size: int = 220) -> str:
    chunk = " ".join(text.strip().split())
    if len(chunk) <= size:
        return chunk
    return f"{chunk[:size - 1]}…"


def _strip_article_prefix(text: str) -> str:
    return _ARTICLE_PREFIX_RE.sub("", text.strip(), count=1)


def _iter_sentences(text: str) -> Iterable[str]:
    stripped = _strip_article_prefix(text)
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(stripped) if part.strip()]
    if not parts:
        yield stripped
        return
    for part in parts:
        subparts = [chunk.strip() for chunk in _INLINE_SUBCLAUSE_SPLIT_RE.split(part) if chunk.strip()]
        if not subparts:
            yield part
            continue
        for subpart in subparts:
            yield subpart


def _iter_semantic_clauses(text: str) -> Iterable[str]:
    emitted = False
    for clause in _CLAUSE_SPLIT_RE.split(text):
        stripped = clause.strip()
        if not stripped:
            continue
        emitted = True
        yield stripped
    if not emitted:
        yield text.strip()


def _iter_list_items(text: str) -> Iterable[str]:
    for raw in re.split(r"\s*;\s+|\s*\n+\s*", text):
        item = raw.strip(" -\u2013\u2014\u2022\t\r\n")
        if len(item) >= 4:
            yield item


def _approval_object_hint(text: str) -> str:
    lines = [_compact for _compact in (" ".join(line.split()) for line in text.splitlines()) if _compact]
    skip_markers = ("розпорядженням", "постановою", "наказом", "від ", "n ", "№")
    for line in lines:
        lower = line.lower()
        if any(marker in lower for marker in skip_markers):
            continue
        if lower.startswith(("затверджено", "схвалено", "погоджено", "затвердити", "схвалити", "погодити")):
            continue
        if len(line) >= 5:
            return _clip_text(line, 220)
    return ""


def _iter_retry_chunks(text: str, *, quality_family: str, struct_kind: str) -> Iterable[str]:
    seen: set[str] = set()
    base_chunks: list[str] = []
    if quality_family in {"law", "treaty_protocol"}:
        base_chunks.extend(_iter_sentences(text))
    base_chunks.extend(_iter_semantic_clauses(text))
    if quality_family == "appendix_heavy" or struct_kind in {"paragraph", "enumeration_item", "table_row"}:
        base_chunks.extend(part.strip() for part in text.splitlines() if part.strip())
    for chunk in base_chunks:
        compact = " ".join(chunk.split())
        if len(compact) < 24 or compact in seen:
            continue
        seen.add(compact)
        yield compact


def _is_basic_article_context(*, doc_title: str, citation_label: str) -> bool:
    title = doc_title or ""
    citation = citation_label or ""
    return bool(
        _CONSTITUTIONAL_TITLE_RE.search(title)
        or _CODE_TITLE_RE.search(title)
        or _BASIC_LAW_TITLE_RE.search(title)
        or citation.lower().startswith("стаття")
    )


def _token_count(text: str) -> int:
    return len([part for part in text.split() if part])


def _is_compact_clause(*, subject: str, object_text: str, sentence: str) -> bool:
    object_lower = object_text.lower()
    if any(marker in object_lower for marker in (", який", ", яка", ", яке", ", що", ";")) and _token_count(object_text) > 14:
        return False
    return (
        len(sentence) <= 280
        and _token_count(sentence) <= 40
        and len(subject) <= 160
        and len(object_text) <= 180
        and _token_count(subject) <= 16
        and _token_count(object_text) <= 24
    )


def _extract_structured_article_candidates(
    *,
    text: str,
    citation_label: str,
    doc_title: str,
) -> tuple[list[SPOCandidate], list[str]]:
    if not _is_basic_article_context(doc_title=doc_title, citation_label=citation_label):
        return [], []

    is_constitutional_doc = bool(_CONSTITUTIONAL_TITLE_RE.search(doc_title or ""))
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []

    for sentence in _iter_sentences(text):
        sentence = sentence.strip()
        if len(sentence) < 12:
            continue
        quote = _clip_text(sentence, size=320)

        right_match = _RIGHT_RE.match(sentence)
        if right_match:
            subject_uk = _clip_text(right_match.group("subject").strip(" ,;:"), 120)
            object_uk = _clip_text(f"має право {right_match.group('object').strip(' .;:')}", 220)
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk or "суб'єкт правовідносин",
                    predicate="grants",
                    object_uk=object_uk,
                    norm_type="permission",
                    fact_text=f"{subject_uk or 'субʼєкт'} має право {right_match.group('object').strip(' .;:')}",
                    quote=quote,
                    confidence=0.89 if is_constitutional_doc else 0.84,
                )
            )
            reason_codes.append("article_right_pattern")

        rights_list_match = _RIGHTS_LIST_RE.match(sentence)
        if rights_list_match and sentence.count(";") >= 2:
            subject_uk = _clip_text(rights_list_match.group("subject").strip(" ,;:"), 140)
            for item in _iter_list_items(rights_list_match.group("object")):
                object_uk = _clip_text(f"має право {item.strip(' .;:')}", 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "суб'єкт правовідносин",
                        predicate="grants",
                        object_uk=object_uk,
                        norm_type="permission",
                        fact_text=f"{subject_uk or 'субʼєкт'} має право {item.strip(' .;:')}",
                        quote=quote,
                        confidence=0.83,
                    )
                )
            reason_codes.append("article_rights_list_pattern")

        guarantee_match = _GUARANTEE_RE.match(sentence)
        if guarantee_match:
            prefix = (guarantee_match.group("subject") or "").strip(" ,;:")
            object_uk = _clip_text(guarantee_match.group("object").strip(" .;:"), 220)
            subject_uk = prefix or ("держава" if is_constitutional_doc else "цей акт")
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="grants",
                    object_uk=object_uk,
                    norm_type="permission",
                    fact_text=f"Гарантується {object_uk}",
                    quote=quote,
                    confidence=0.88 if is_constitutional_doc else 0.83,
                )
            )
            reason_codes.append("article_guarantee_pattern")

        defined_by_law_match = _DEFINED_BY_LAW_RE.match(sentence)
        if defined_by_law_match:
            raw_object = defined_by_law_match.group("object").strip(" ,;:")
            object_uk = _clip_text(raw_object, 200)
            if is_constitutional_doc or _is_compact_clause(
                subject=raw_object,
                object_text="законом",
                sentence=sentence,
            ):
                candidates.append(
                    _build_candidate(
                        subject_uk=object_uk,
                        predicate="defines",
                        object_uk="законом",
                        norm_type="definition",
                        fact_text=f"{object_uk} визначаються законом",
                        quote=quote,
                        confidence=0.87 if is_constitutional_doc else 0.79,
                    )
                )
                reason_codes.append("article_defined_by_law_pattern")

        dash_definition_match = _DASH_DEFINITION_RE.match(sentence)
        if dash_definition_match:
            raw_subject = dash_definition_match.group("subject").strip(" ,;:")
            raw_object = dash_definition_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 140)
            object_uk = _clip_text(raw_object, 180)
            if _is_compact_clause(subject=raw_subject, object_text=raw_object, sentence=sentence):
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{subject_uk} - {object_uk}",
                        quote=quote,
                        confidence=0.87 if is_constitutional_doc else 0.85,
                    )
                )
                reason_codes.append("article_dash_definition_pattern")

        dash_this_is_match = _DASH_THIS_IS_RE.match(sentence)
        if dash_this_is_match:
            raw_subject = dash_this_is_match.group("subject").strip(" ,;:")
            raw_object = dash_this_is_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{subject_uk} - це {object_uk}",
                        quote=quote,
                        confidence=0.86 if is_constitutional_doc else 0.81,
                    )
                )
                reason_codes.append("article_dash_this_is_pattern")

        list_definition_match = _LIST_DEFINITION_RE.search(sentence)
        if list_definition_match and (
            sentence.count(";") >= 2 or sentence.count("\n") >= 2
        ):
            raw_subject = list_definition_match.group("subject").strip(" ,;:")
            subject_uk = _clip_text(raw_subject, 160)
            if subject_uk:
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk="перелік визначених елементів",
                        norm_type="definition",
                        fact_text=f"{subject_uk} визначаються переліком у статті",
                        quote=quote,
                        confidence=0.78,
                    )
                )
                reason_codes.append("article_list_definition_pattern")

        principles_list_match = _PRINCIPLES_LIST_RE.search(sentence)
        if principles_list_match and sentence.count(";") >= 2:
            subject_uk = _clip_text(principles_list_match.group("subject").strip(" ,;:"), 160)
            for item in _iter_list_items(principles_list_match.group("object")):
                item_text = _clip_text(item.strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "цей акт",
                        predicate="applies_to",
                        object_uk=item_text,
                        norm_type="procedure",
                        fact_text=f"{subject_uk or 'цей акт'} застосовується за принципом {item_text}",
                        quote=quote,
                        confidence=0.8,
                    )
                )
            reason_codes.append("article_principles_list_pattern")

        amend_wording_match = _AMEND_WORDING_RE.search(sentence)
        if amend_wording_match:
            object_uk = _clip_text(amend_wording_match.group("object").strip(" .;:"), 220)
            candidates.append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="amends",
                    object_uk=object_uk or "словесне формулювання норми",
                    norm_type="amendment",
                    fact_text=f"Внесено словесну зміну: {object_uk or 'словесне формулювання норми'}",
                    quote=quote,
                    confidence=0.84,
                )
            )
            reason_codes.append("article_amend_wording_pattern")

        recognized_match = _RECOGNIZED_AS_RE.match(sentence)
        if recognized_match:
            raw_subject = recognized_match.group("subject").strip(" ,;:")
            raw_object = recognized_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if _is_compact_clause(subject=raw_subject, object_text=raw_object, sentence=sentence):
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{subject_uk} визнаються {object_uk}",
                        quote=quote,
                        confidence=0.86 if is_constitutional_doc else 0.78,
                    )
                )
                reason_codes.append("article_recognition_pattern")

        exists_match = _EXISTS_RE.match(sentence)
        if exists_match and not _DEONTIC_MARKER_RE.search(sentence):
            scope = (exists_match.group("scope") or "в Україні").strip(" ,;:")
            raw_object = exists_match.group("object").strip(" .;:")
            object_uk = _clip_text(raw_object, 220)
            if _is_compact_clause(subject=scope, object_text=raw_object, sentence=sentence):
                candidates.append(
                    _build_candidate(
                        subject_uk=scope,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{scope} існує {object_uk}",
                        quote=quote,
                        confidence=0.86 if is_constitutional_doc else 0.77,
                    )
                )
                reason_codes.append("article_existence_pattern")

        declarative_match = _DECLARATIVE_IS_RE.match(sentence)
        if declarative_match and not _DEONTIC_MARKER_RE.search(sentence):
            raw_subject = declarative_match.group("subject").strip(" ,;:")
            raw_object = declarative_match.group("object").strip(" .;:")
            subject_uk = _clip_text(raw_subject, 160)
            object_uk = _clip_text(raw_object, 220)
            if subject_uk and object_uk and _is_compact_clause(
                subject=raw_subject,
                object_text=raw_object,
                sentence=sentence,
            ):
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk,
                        predicate="defines",
                        object_uk=object_uk,
                        norm_type="definition",
                        fact_text=f"{subject_uk} є {object_uk}",
                        quote=quote,
                        confidence=0.86 if is_constitutional_doc else 0.76,
                    )
                )
                reason_codes.append("article_declarative_pattern")

        for clause in _iter_semantic_clauses(sentence):
            clause_quote = _clip_text(clause, size=320)
            mandatory_execution_match = _MANDATORY_EXECUTION_RE.search(clause)
            if mandatory_execution_match:
                raw_subject = mandatory_execution_match.group("subject").strip(" ,;:")
                raw_object = mandatory_execution_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 180)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="requires",
                            object_uk=object_uk,
                            norm_type="obligation",
                            fact_text=f"{subject_uk} є обов'язковими для виконання {raw_object}",
                            quote=clause_quote,
                            confidence=0.84 if is_constitutional_doc else 0.8,
                        )
                    )
                    reason_codes.append("article_mandatory_execution_pattern")

            require_match = _SUBJECT_REQUIRE_RE.search(clause)
            if require_match:
                raw_subject = require_match.group("subject").strip(" ,;:")
                raw_object = require_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="requires",
                            object_uk=object_uk,
                            norm_type="obligation",
                            fact_text=f"{subject_uk} {require_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.84 if is_constitutional_doc else 0.8,
                        )
                    )
                    reason_codes.append("article_subject_requirement_pattern")

            prohibit_match = _SUBJECT_PROHIBIT_RE.search(clause)
            if prohibit_match:
                raw_subject = prohibit_match.group("subject").strip(" ,;:")
                raw_object = prohibit_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="prohibits",
                            object_uk=object_uk,
                            norm_type="prohibition",
                            fact_text=f"{subject_uk} {prohibit_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.84 if is_constitutional_doc else 0.8,
                        )
                    )
                    reason_codes.append("article_subject_prohibition_pattern")

            permission_match = _SUBJECT_PERMISSION_RE.search(clause)
            if permission_match:
                raw_subject = permission_match.group("subject").strip(" ,;:")
                raw_object = permission_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                lemma = permission_match.group("lemma").lower()
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="grants",
                            object_uk=(f"має право {object_uk}" if "має право" in lemma else object_uk),
                            norm_type="permission",
                            fact_text=f"{subject_uk} {permission_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.84 if is_constitutional_doc else 0.79,
                        )
                    )
                    reason_codes.append("article_subject_permission_pattern")
                    condition_match = _PERMISSION_CONDITION_RE.search(raw_object)
                    if condition_match:
                        condition_uk = _clip_text(condition_match.group("condition").strip(" .;:"), 220)
                        candidates.append(
                            _build_candidate(
                                subject_uk=subject_uk,
                                predicate="applies_to",
                                object_uk=condition_uk,
                                norm_type="condition",
                                fact_text=f"{subject_uk} застосовується за умови {condition_uk}",
                                quote=clause_quote,
                                confidence=0.77,
                            )
                        )
                        reason_codes.append("article_permission_condition_pattern")

            temporal_match = _TEMPORAL_APPLICABILITY_RE.search(clause)
            if temporal_match:
                raw_subject = temporal_match.group("subject").strip(" ,;:")
                raw_object = temporal_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="applies_to",
                            object_uk=object_uk,
                            norm_type="applicability",
                            fact_text=f"{subject_uk} {temporal_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.82 if is_constitutional_doc else 0.78,
                        )
                    )
                    reason_codes.append("article_temporal_applicability_pattern")

            sanction_match = _SANCTION_RE.search(clause)
            if sanction_match:
                raw_subject = sanction_match.group("subject").strip(" ,;:")
                raw_object = sanction_match.group("object").strip(" .;:")
                subject_uk = _clip_text(raw_subject, 160)
                object_uk = _clip_text(raw_object, 220)
                if subject_uk and object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk=subject_uk,
                            predicate="sanctions",
                            object_uk=object_uk,
                            norm_type="sanction",
                            fact_text=f"{subject_uk} {sanction_match.group('lemma').strip()} {raw_object}",
                            quote=clause_quote,
                            confidence=0.83 if is_constitutional_doc else 0.79,
                        )
                    )
                    reason_codes.append("article_sanction_pattern")

            exception_match = _EXCEPTION_RE.search(clause)
            if exception_match:
                object_uk = _clip_text(exception_match.group("object").strip(" .;:"), 220)
                if object_uk:
                    candidates.append(
                        _build_candidate(
                            subject_uk="виняток застосування норми",
                            predicate="applies_to",
                            object_uk=object_uk,
                            norm_type="applicability",
                            fact_text=f"Виняток застосовується щодо: {object_uk}",
                            quote=clause_quote,
                            confidence=0.78,
                        )
                    )
                    reason_codes.append("article_exception_pattern")

        competence_match = _COMPETENCE_LIST_RE.search(sentence)
        if competence_match and (sentence.count(";") >= 2 or sentence.count("\n") >= 2):
            subject_uk = _clip_text(competence_match.group("subject").strip(" ,;:"), 180)
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk or "орган управління",
                    predicate="defines",
                    object_uk="перелік компетенцій, визначений у статті",
                    norm_type="definition",
                    fact_text=f"До компетенції {subject_uk or 'органу управління'} належить перелік визначених повноважень",
                    quote=quote,
                    confidence=0.8,
                )
            )
            reason_codes.append("article_competence_list_pattern")

    return candidates, reason_codes


def _extract_treaty_resolution_candidates(
    *,
    text: str,
    citation_label: str,
    doc_title: str,
) -> tuple[list[SPOCandidate], list[str]]:
    del citation_label
    title = doc_title or ""
    treaty_like = bool(_TREATY_TITLE_RE.search(title))
    resolution_like = bool(_RESOLUTION_TITLE_RE.search(title))
    if not treaty_like and not resolution_like:
        return [], []

    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []
    for sentence in _iter_sentences(text):
        sentence = sentence.strip()
        if len(sentence) < 16:
            continue
        quote = _clip_text(sentence, size=320)

        if treaty_like:
            treaty_match = _TREATY_OBLIGATION_RE.search(sentence)
            if treaty_match:
                subject_uk = _clip_text(treaty_match.group("subject").strip(" ,;:"), 140)
                object_uk = _clip_text(treaty_match.group("object").strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "договірна сторона",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk or 'договірна сторона'} зобов'язується {object_uk}",
                        quote=quote,
                        confidence=0.84,
                    )
                )
                reason_codes.append("treaty_obligation_pattern")

            cooperation_match = _TREATY_COOPERATION_RE.search(sentence)
            if cooperation_match:
                object_uk = _clip_text(cooperation_match.group("object").strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk="договірні сторони",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="procedure",
                        fact_text=f"Співробітництво здійснюється {object_uk}",
                        quote=quote,
                        confidence=0.8,
                    )
                )
                reason_codes.append("treaty_cooperation_pattern")

            future_cooperation_match = _TREATY_FUTURE_COOPERATION_RE.search(sentence)
            if future_cooperation_match:
                subject_uk = _clip_text(future_cooperation_match.group("subject").strip(" ,;:"), 140)
                object_uk = _clip_text(
                    f"{future_cooperation_match.group('lemma').strip()} "
                    f"{future_cooperation_match.group('object').strip(' .;:')}",
                    240,
                )
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "договірні сторони",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk or 'договірні сторони'} {object_uk}",
                        quote=quote,
                        confidence=0.84,
                    )
                )
                reason_codes.append("treaty_future_cooperation_pattern")

            treaty_delegate_match = _TREATY_DELEGATION_RE.search(sentence)
            if treaty_delegate_match:
                subject_uk = _clip_text(treaty_delegate_match.group("subject").strip(" ,;:"), 140)
                object_uk = _clip_text(treaty_delegate_match.group("object").strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "договірні сторони",
                        predicate="delegates",
                        object_uk=object_uk,
                        norm_type="delegation",
                        fact_text=f"{subject_uk or 'договірні сторони'} доручають {object_uk}",
                        quote=quote,
                        confidence=0.82,
                    )
                )
                reason_codes.append("treaty_delegation_pattern")

        ratification_match = _RATIFICATION_RE.search(sentence)
        if ratification_match:
            object_uk = _clip_text(ratification_match.group("object").strip(" .;:"), 220)
            candidates.append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="approves",
                    object_uk=object_uk,
                    norm_type="procedure",
                    fact_text=f"Схвалено/затверджено: {object_uk}",
                    quote=quote,
                    confidence=0.83,
                )
            )
            reason_codes.append("ratification_pattern")

        if resolution_like:
            mandate_match = _IMPLEMENTATION_MANDATE_RE.search(sentence)
            if mandate_match:
                subject_uk = _clip_text(mandate_match.group("subject").strip(" ,;:"), 140)
                object_uk = _clip_text(mandate_match.group("object").strip(" .;:"), 220)
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "адресат акта",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk or 'адресат акта'} забезпечує {object_uk}",
                        quote=quote,
                        confidence=0.8,
                    )
                )
                reason_codes.append("resolution_mandate_pattern")

            imperative_mandate_match = _IMPERATIVE_MANDATE_RE.search(sentence)
            if imperative_mandate_match:
                subject_uk = _clip_text(imperative_mandate_match.group("subject").strip(" ,;:"), 160)
                object_uk = _clip_text(
                    f"{imperative_mandate_match.group('lemma').strip()} "
                    f"{imperative_mandate_match.group('object').strip(' .;:')}",
                    220,
                )
                candidates.append(
                    _build_candidate(
                        subject_uk=subject_uk or "адресат акта",
                        predicate="requires",
                        object_uk=object_uk,
                        norm_type="obligation",
                        fact_text=f"{subject_uk or 'адресат акта'} {object_uk}",
                        quote=quote,
                        confidence=0.81,
                    )
                )
                reason_codes.append("resolution_imperative_mandate_pattern")

    return candidates, reason_codes


def _extract_amendment_bundle_candidates(*, text: str, doc_title: str) -> tuple[list[SPOCandidate], list[str]]:
    cleaned = text.strip()
    if not cleaned:
        return [], []
    quote = _clip_text(cleaned, size=360)
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []

    if _AMEND_RE.search(cleaned) or _AMEND_WORDING_RE.search(cleaned) or _AMEND_CITATION_RE.search(cleaned):
        amend_target = doc_title or "зазначений акт"
        citation_match = _AMEND_CITATION_RE.search(cleaned)
        wording_match = _AMEND_WORDING_RE.search(cleaned)
        if citation_match:
            amend_target = f"стаття/пункт {citation_match.group(1)} {doc_title or 'зазначеного акту'}"
        elif wording_match:
            amend_target = _clip_text(wording_match.group("object").strip(" .;:"), 220)
        candidates.append(
            _build_candidate(
                subject_uk="орган, що прийняв акт",
                predicate="amends",
                object_uk=amend_target,
                norm_type="amendment",
                fact_text=f"Внесено зміни до {amend_target}",
                quote=quote,
                confidence=0.9 if citation_match else 0.86,
            )
        )
        reason_codes.append("subtype_amendment_bundle")
        if "новій редакції" in cleaned.lower() or "такій редакції" in cleaned.lower():
            candidates.append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="supersedes",
                    object_uk=amend_target,
                    norm_type="amendment",
                    fact_text=f"Попередню редакцію норми замінено: {amend_target}",
                    quote=quote,
                    confidence=0.85,
                )
            )
            reason_codes.append("subtype_supersedes_bundle")

    repeal_match = _REPEAL_RE.search(cleaned)
    if repeal_match:
        repeal_target = (repeal_match.group(1) or "").strip(" .;:") or "визначені акти"
        candidates.append(
            _build_candidate(
                subject_uk="орган, що прийняв акт",
                predicate="repeals",
                object_uk=_clip_text(repeal_target, 220),
                norm_type="repeal",
                fact_text=f"Скасовано або визнано таким, що втратив чинність: {_clip_text(repeal_target, 180)}",
                quote=quote,
                confidence=0.9,
            )
        )
        reason_codes.append("subtype_repeal_bundle")

    if _ENTRY_INTO_FORCE_RE.search(cleaned):
        entry = (_ENTRY_INTO_FORCE_RE.search(cleaned).group(1) or "").strip(" .;:") if _ENTRY_INTO_FORCE_RE.search(cleaned) else ""
        candidates.append(
            _build_candidate(
                subject_uk="цей акт",
                predicate="enters_into_force",
                object_uk=entry or "у визначений строк",
                norm_type="entry_into_force",
                fact_text=f"Акт набирає чинності {entry or 'у визначений строк'}",
                quote=quote,
                confidence=0.88,
            )
        )
        reason_codes.append("subtype_entry_into_force")

    return candidates, reason_codes


def _extract_approval_bundle_candidates(*, text: str, doc_title: str) -> tuple[list[SPOCandidate], list[str]]:
    cleaned = text.strip()
    if not cleaned:
        return [], []
    quote = _clip_text(cleaned, size=360)
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []
    for match in _APPROVAL_BUNDLE_RE.finditer(cleaned):
        lemma = match.group("lemma").strip().lower()
        object_uk = _clip_text(match.group("object").strip(" .;:"), 220)
        annex_match = _ANNEX_RE.search(object_uk) or _ANNEX_RE.search(cleaned)
        approval_target = (
            object_uk
            or (annex_match.group(1) if annex_match else "")
            or _approval_object_hint(cleaned)
            or "доданий документ"
        )
        if lemma.startswith(("затверд", "схвал", "погод")):
            candidates.append(
                _build_candidate(
                    subject_uk="орган, що прийняв акт",
                    predicate="approves",
                    object_uk=approval_target,
                    norm_type="procedure",
                    fact_text=f"Схвалено або затверджено: {approval_target}",
                    quote=quote,
                    confidence=0.87 if annex_match else 0.83,
                )
            )
            reason_codes.append("subtype_approval_bundle")
            if annex_match:
                candidates.append(
                    _build_candidate(
                        subject_uk="цей акт",
                        predicate="applies_to",
                        object_uk=_clip_text(annex_match.group(1), 180),
                        norm_type="applicability",
                        fact_text=f"Акт застосовується до {annex_match.group(1)}",
                        quote=quote,
                        confidence=0.78,
                    )
                )
                reason_codes.append("subtype_approval_annex_reference")
        elif lemma.startswith("доруч"):
            candidates.append(
                _build_candidate(
                    subject_uk="адресат акта",
                    predicate="delegates",
                    object_uk=object_uk or doc_title or "виконання дії",
                    norm_type="delegation",
                    fact_text=f"Доручено: {object_uk or 'виконання дії'}",
                    quote=quote,
                    confidence=0.82,
                )
            )
            reason_codes.append("subtype_delegate_bundle")
    return candidates, reason_codes


def _extract_threshold_row_candidates(*, text: str, doc_title: str) -> tuple[list[SPOCandidate], list[str]]:
    cleaned = text.strip()
    if not cleaned:
        return [], []
    quote = _clip_text(cleaned, size=320)
    match = _THRESHOLD_ROW_RE.search(cleaned)
    if not match:
        multi_match = _MULTIVALUE_THRESHOLD_ROW_RE.search(cleaned)
        if multi_match:
            subject_uk = _clip_text(multi_match.group("subject").strip(" .;:"), 160)
            thresholds = extract_thresholds_from_text(cleaned, applies_to=subject_uk or doc_title or "регульований показник")
            value_label = thresholds[0].value_text if thresholds else multi_match.group("values").split()[0]
            return [
                _build_candidate(
                    subject_uk=subject_uk or "регульований показник",
                    predicate="sets_threshold",
                    object_uk=doc_title or subject_uk or "регульований показник",
                    norm_type="obligation",
                    fact_text=f"{subject_uk or 'регульований показник'} має встановлені ліміти {value_label}",
                    quote=quote,
                    confidence=0.88,
                    thresholds_text=cleaned,
                )
            ], ["subtype_threshold_multivalue_row"]
        thresholds = extract_thresholds_from_text(cleaned, applies_to=doc_title or "регульований показник")
        if not thresholds:
            return [], []
        value_label = thresholds[0].value_text or thresholds[0].value_decimal or "числовий поріг"
        return [
            _build_candidate(
                subject_uk="орган, що прийняв акт",
                predicate="sets_threshold",
                object_uk=doc_title or "регульований показник",
                norm_type="obligation",
                fact_text=f"Встановлено поріг: {value_label}",
                quote=quote,
                confidence=0.86,
                thresholds_text=cleaned,
            )
        ], ["subtype_threshold_fallback"]
    subject_uk = _clip_text(match.group("subject").strip(" .;:"), 160)
    value = match.group("value").strip()
    unit = match.group("unit").strip()
    return [
        _build_candidate(
            subject_uk=subject_uk or "регульований показник",
            predicate="sets_threshold",
            object_uk=f"{value} {unit}",
            norm_type="obligation",
            fact_text=f"{subject_uk or 'регульований показник'} має поріг {value} {unit}",
            quote=quote,
            confidence=0.9,
            thresholds_text=cleaned,
        )
    ], ["subtype_threshold_row"]


def _extract_application_requirement_candidates(*, text: str) -> tuple[list[SPOCandidate], list[str]]:
    cleaned = text.strip()
    if not cleaned:
        return [], []
    quote = _clip_text(cleaned, size=320)
    candidates: list[SPOCandidate] = []
    reason_codes: list[str] = []
    for match in _APPLICANT_ACTION_RE.finditer(cleaned):
        lemma = match.group("lemma").strip().lower()
        subject_uk = _clip_text((match.group("subject") or "заявник").strip(" ,;:"), 140)
        object_uk = _clip_text(match.group("object").strip(" .;:"), 220)
        predicate = "requires"
        norm_type = "obligation"
        if lemma.startswith(("повідом",)):
            predicate = "requires"
        elif lemma.startswith(("надати", "надає", "дода", "подати", "подає")):
            predicate = "requires"
        elif "просить" in lemma:
            predicate = "grants"
            norm_type = "permission"
        candidates.append(
            _build_candidate(
                subject_uk=subject_uk or "заявник",
                predicate=predicate,
                object_uk=object_uk or "виконати вимогу форми",
                norm_type=norm_type,
                fact_text=f"{subject_uk or 'заявник'} {lemma} {object_uk or 'виконати вимогу форми'}",
                quote=quote,
                confidence=0.84,
            )
        )
        reason_codes.append("subtype_application_requirement")
    for item in _iter_list_items(cleaned):
        bullet_match = _APPLICATION_BULLET_RE.match(item)
        if not bullet_match:
            continue
        lemma = bullet_match.group("lemma").strip().lower()
        object_uk = _clip_text(bullet_match.group("object").strip(" .;:"), 220)
        candidates.append(
            _build_candidate(
                subject_uk="заявник",
                predicate="requires",
                object_uk=object_uk or "виконати вимогу форми",
                norm_type="obligation",
                fact_text=f"заявник {lemma} {object_uk or 'виконати вимогу форми'}",
                quote=quote,
                confidence=0.83,
            )
        )
        reason_codes.append("subtype_application_bullet_requirement")
    condition_match = _APPLICATION_CONDITION_RE.search(cleaned)
    if condition_match:
        candidates.append(
            _build_candidate(
                subject_uk="заявник",
                predicate="applies_to",
                object_uk=_clip_text(condition_match.group(1).strip(" .;:"), 220),
                norm_type="condition",
                fact_text=f"Застосовується умова: {condition_match.group(1).strip(' .;:')}",
                quote=quote,
                confidence=0.8,
            )
        )
        reason_codes.append("subtype_application_condition")
    return candidates, reason_codes


def extract_deterministic_spo(
    *,
    text: str,
    citation_label: str,
    doc_title: str,
    legal_unit_subtype: str = "",
    quality_family: str = "",
    reference_bearing: bool = False,
    threshold_bearing: bool = False,
) -> DeterministicExtraction:
    """Extract high-confidence SPO candidates without LLM."""
    cleaned = text.strip()
    if not cleaned:
        return DeterministicExtraction(candidates=[], confidence=0.0, reason_codes=["empty"])

    reason_codes: list[str] = []
    candidates: list[SPOCandidate] = []
    subject = "орган, що прийняв акт"
    quote = _clip_text(cleaned, size=400)
    subtype = (legal_unit_subtype or "").strip().lower()

    subtype_extractors: tuple[tuple[str, Callable[[], tuple[list[SPOCandidate], list[str]]]], ...] = (
        ("amendment_bundle", lambda: _extract_amendment_bundle_candidates(text=cleaned, doc_title=doc_title)),
        ("approval_bundle", lambda: _extract_approval_bundle_candidates(text=cleaned, doc_title=doc_title)),
        ("tariff_threshold_row", lambda: _extract_threshold_row_candidates(text=cleaned, doc_title=doc_title)),
        ("application_requirement", lambda: _extract_application_requirement_candidates(text=cleaned)),
    )
    for target_subtype, extractor in subtype_extractors:
        if subtype != target_subtype:
            continue
        subtype_candidates, subtype_reason_codes = extractor()
        if subtype_candidates:
            candidates.extend(subtype_candidates)
            reason_codes.extend(subtype_reason_codes)

    article_candidates, article_reason_codes = _extract_structured_article_candidates(
        text=cleaned,
        citation_label=citation_label,
        doc_title=doc_title,
    )
    if article_candidates:
        candidates.extend(article_candidates)
        reason_codes.extend(article_reason_codes)

    treaty_candidates, treaty_reason_codes = _extract_treaty_resolution_candidates(
        text=cleaned,
        citation_label=citation_label,
        doc_title=doc_title,
    )
    if treaty_candidates:
        candidates.extend(treaty_candidates)
        reason_codes.extend(treaty_reason_codes)

    entry_match = _ENTRY_INTO_FORCE_RE.search(cleaned)
    if entry_match:
        detail = (entry_match.group(1) or "").strip(" .")
        object_uk = detail or "з дня офіційного опублікування"
        candidates.append(
            _build_candidate(
                subject_uk="цей акт",
                predicate="enters_into_force",
                object_uk=object_uk,
                norm_type="entry_into_force",
                fact_text=f"Акт набирає чинності {object_uk}".strip(),
                quote=quote,
                confidence=0.9,
            )
        )
        reason_codes.append("entry_into_force_pattern")

    repeal_match = _REPEAL_RE.search(cleaned)
    if repeal_match:
        object_uk = (repeal_match.group(1) or "").strip(" .") or "визначені акти"
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="repeals",
                object_uk=object_uk,
                norm_type="repeal",
                fact_text=f"Визнано такими, що втратили чинність: {object_uk}",
                quote=quote,
                confidence=0.9,
            )
        )
        reason_codes.append("repeal_pattern")

    if _AMEND_RE.search(cleaned):
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="amends",
                object_uk=doc_title or "зазначений акт",
                norm_type="amendment",
                fact_text="Внесено зміни до акту",
                quote=quote,
                confidence=0.87,
            )
        )
        reason_codes.append("amendment_pattern")

    amend_wording_match = _AMEND_WORDING_RE.search(cleaned)
    if amend_wording_match:
        object_uk = _clip_text(amend_wording_match.group("object").strip(" .;:"), 220)
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="amends",
                object_uk=object_uk or "словесне формулювання норми",
                norm_type="amendment",
                fact_text=f"Внесено словесну зміну: {object_uk or 'словесне формулювання норми'}",
                quote=quote,
                confidence=0.84,
            )
        )
        reason_codes.append("amend_wording_pattern")

    approve_match = _APPROVE_RE.search(cleaned)
    if approve_match:
        object_uk = (approve_match.group(1) or "").strip(" .")
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="approves",
                object_uk=object_uk or "доданий документ",
                norm_type="procedure",
                fact_text=f"Затверджено: {object_uk or 'доданий документ'}",
                quote=quote,
                confidence=0.86,
            )
        )
        reason_codes.append("approval_pattern")

    thresholds = extract_thresholds_from_text(cleaned, applies_to=doc_title or "цей акт")
    if thresholds and (threshold_bearing or subtype in {"tariff_threshold_row", "core_normative_clause", ""}):
        best = thresholds[0]
        threshold_desc = best.value_text or best.value_decimal or "числовий поріг"
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="sets_threshold",
                object_uk=doc_title or "регульований показник",
                norm_type="obligation",
                fact_text=f"Встановлено поріг: {threshold_desc}",
                quote=quote,
                confidence=0.88,
                thresholds_text=cleaned,
            )
        )
        reason_codes.append("threshold_pattern")

    if _DELEGATE_RE.search(cleaned):
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="delegates",
                object_uk="уповноважений орган",
                norm_type="delegation",
                fact_text="Повноваження делеговано уповноваженому органу",
                quote=quote,
                confidence=0.78,
            )
        )
        reason_codes.append("delegate_pattern")

    if _PROHIBIT_RE.search(cleaned):
        # Try to extract the actual prohibited action
        prohibit_obj_match = _PROHIBIT_OBJECT_RE.search(cleaned)
        prohibit_obj = (
            prohibit_obj_match.group(1).strip() if prohibit_obj_match else "зазначена дія"
        )
        candidates.append(
            _build_candidate(
                subject_uk="суб'єкт правовідносин",
                predicate="prohibits",
                object_uk=prohibit_obj,
                norm_type="prohibition",
                fact_text=f"Забороняється: {_clip_text(prohibit_obj, 150)}",
                quote=quote,
                confidence=0.80 if prohibit_obj_match else 0.76,
            )
        )
        reason_codes.append("prohibit_pattern")

    if _REQUIRE_RE.search(cleaned):
        # Try to extract the actual requirement object
        require_obj_match = _REQUIRE_OBJECT_RE.search(cleaned)
        require_obj = (
            require_obj_match.group(1).strip() if require_obj_match else "виконання вимог норми"
        )
        candidates.append(
            _build_candidate(
                subject_uk="суб'єкт правовідносин",
                predicate="requires",
                object_uk=require_obj,
                norm_type="obligation",
                fact_text=f"Вимагається: {_clip_text(require_obj, 150)}",
                quote=quote,
                confidence=0.78 if require_obj_match else 0.74,
            )
        )
        reason_codes.append("require_pattern")

    global_rights_list_match = _RIGHTS_LIST_RE.search(cleaned)
    if global_rights_list_match and cleaned.count(";") >= 2:
        subject_uk = _clip_text(global_rights_list_match.group("subject").strip(" ,;:"), 140)
        for item in _iter_list_items(global_rights_list_match.group("object")):
            object_uk = _clip_text(f"має право {item.strip(' .;:')}", 220)
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk or "суб'єкт правовідносин",
                    predicate="grants",
                    object_uk=object_uk,
                    norm_type="permission",
                    fact_text=f"{subject_uk or 'субʼєкт'} має право {item.strip(' .;:')}",
                    quote=quote,
                    confidence=0.82,
                )
            )
        reason_codes.append("rights_list_pattern")

    passive_procedure_match = _PASSIVE_PROCEDURE_RE.search(cleaned)
    if passive_procedure_match:
        subject_uk = _clip_text(passive_procedure_match.group("subject").strip(" ,;:"), 160)
        object_uk = _clip_text(passive_procedure_match.group("object").strip(" .;:"), 220)
        if (
            subject_uk
            and object_uk
            and not _PRINCIPLES_LIST_RE.search(cleaned)
            and not _RIGHTS_LIST_RE.search(cleaned)
        ):
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="applies_to",
                    object_uk=object_uk,
                    norm_type="procedure",
                    fact_text=f"{subject_uk} {passive_procedure_match.group('lemma').strip()} {object_uk}",
                    quote=quote,
                    confidence=0.8,
                )
            )
            reason_codes.append("passive_procedure_pattern")

    subject_to_match = _SUBJECT_TO_RE.search(cleaned)
    if subject_to_match:
        subject_uk = _clip_text(subject_to_match.group("subject").strip(" ,;:"), 160)
        object_uk = _clip_text(subject_to_match.group("object").strip(" .;:"), 220)
        if subject_uk and object_uk:
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="applies_to",
                    object_uk=object_uk,
                    norm_type="applicability",
                    fact_text=f"{subject_uk} підлягає {object_uk}",
                    quote=quote,
                    confidence=0.79,
                )
            )
            reason_codes.append("subject_to_pattern")

    applies_scope_match = _APPLIES_SCOPE_RE.search(cleaned)
    if applies_scope_match:
        subject_uk = _clip_text(applies_scope_match.group("subject").strip(" ,;:"), 160)
        object_uk = _clip_text(applies_scope_match.group("object").strip(" .;:"), 220)
        if subject_uk and object_uk:
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="applies_to",
                    object_uk=object_uk,
                    norm_type="applicability",
                    fact_text=f"{subject_uk} поширюється на {object_uk}",
                    quote=quote,
                    confidence=0.8,
                )
            )
            reason_codes.append("applies_scope_pattern")

    establishes_order_match = _ESTABLISHES_ORDER_RE.search(cleaned)
    if establishes_order_match:
        subject_uk = _clip_text(establishes_order_match.group("subject").strip(" ,;:"), 160)
        object_uk = _clip_text(establishes_order_match.group("object").strip(" .;:"), 220)
        if subject_uk and object_uk:
            candidates.append(
                _build_candidate(
                    subject_uk=subject_uk,
                    predicate="defines",
                    object_uk=object_uk,
                    norm_type="procedure",
                    fact_text=f"{subject_uk} встановлює {object_uk}",
                    quote=quote,
                    confidence=0.81,
                )
            )
            reason_codes.append("establishes_order_pattern")

    # Citation amendment: "статтю N викласти/замінити"
    amend_citation_match = _AMEND_CITATION_RE.search(cleaned)
    if amend_citation_match and not _AMEND_RE.search(cleaned):
        target_num = amend_citation_match.group(1)
        candidates.append(
            _build_candidate(
                subject_uk=subject,
                predicate="amends",
                object_uk=f"стаття/пункт {target_num} {doc_title or 'зазначеного акту'}",
                norm_type="amendment",
                fact_text=f"Внесено зміни до статті/пункту {target_num}",
                quote=quote,
                confidence=0.85,
            )
        )
        reason_codes.append("amend_citation_pattern")

    # Deduplicate near-identical facts by (predicate, fact_text).
    seen: set[tuple[str, str]] = set()
    deduped: list[SPOCandidate] = []
    for candidate in candidates:
        key = (candidate.predicate, candidate.fact_text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    candidates = deduped

    if subtype == "citation_only" and not candidates:
        return DeterministicExtraction(candidates=[], confidence=0.0, reason_codes=["citation_only"])

    if not candidates:
        return DeterministicExtraction(candidates=[], confidence=0.0, reason_codes=["no_match"])

    max_pattern_confidence = max(candidate.confidence for candidate in candidates)
    has_high_precision = any(
        code in reason_codes
        for code in (
            "entry_into_force_pattern",
            "repeal_pattern",
            "amendment_pattern",
            "approval_pattern",
            "amend_citation_pattern",
            "subtype_supersedes_bundle",
        )
    )
    has_article_semantics = any(
        code in reason_codes
        for code in (
            "article_right_pattern",
            "article_guarantee_pattern",
            "article_defined_by_law_pattern",
            "article_recognition_pattern",
            "article_existence_pattern",
            "article_declarative_pattern",
            "article_dash_definition_pattern",
            "article_dash_this_is_pattern",
            "article_list_definition_pattern",
            "article_principles_list_pattern",
            "article_rights_list_pattern",
            "article_amend_wording_pattern",
            "article_subject_requirement_pattern",
            "article_mandatory_execution_pattern",
            "article_subject_prohibition_pattern",
            "article_subject_permission_pattern",
            "article_permission_condition_pattern",
            "article_temporal_applicability_pattern",
            "article_sanction_pattern",
            "article_exception_pattern",
            "article_competence_list_pattern",
            "treaty_obligation_pattern",
            "treaty_cooperation_pattern",
            "ratification_pattern",
            "resolution_mandate_pattern",
            "resolution_imperative_mandate_pattern",
            "treaty_future_cooperation_pattern",
            "treaty_delegation_pattern",
            "rights_list_pattern",
            "passive_procedure_pattern",
            "subject_to_pattern",
            "applies_scope_pattern",
            "establishes_order_pattern",
        )
    )
    has_threshold = (
        "threshold_pattern" in reason_codes
        or "subtype_threshold_row" in reason_codes
        or "subtype_threshold_multivalue_row" in reason_codes
        or "subtype_threshold_fallback" in reason_codes
        or threshold_bearing
        or bool(_PERCENT_OR_NUMBER_RE.search(cleaned))
    )
    fallback_like = "повний текст" in citation_label.lower()
    constitutional_doc = bool(_CONSTITUTIONAL_TITLE_RE.search(doc_title or ""))
    confidence = 0.45
    if has_high_precision:
        confidence += 0.25
    if has_article_semantics:
        confidence += 0.18 if constitutional_doc else 0.10
    if has_threshold:
        confidence += 0.15
    if len(candidates) >= 2:
        confidence += 0.08
    if not fallback_like:
        confidence += 0.07
    confidence = max(confidence, max_pattern_confidence)
    if constitutional_doc and has_article_semantics:
        confidence = max(confidence, 0.87)
    if subtype in {"amendment_bundle", "approval_bundle", "tariff_threshold_row", "application_requirement"}:
        confidence = max(confidence, 0.84)
    if reference_bearing and subtype in {"amendment_bundle", "approval_bundle"}:
        confidence = max(confidence, 0.87)
    if quality_family == "appendix_heavy" and subtype in {"application_requirement", "tariff_threshold_row"}:
        confidence = max(confidence, 0.85)
    confidence = min(0.95, confidence)

    normalized_candidates = [
        candidate.model_copy(update={"confidence": confidence})
        for candidate in candidates
    ]
    return DeterministicExtraction(
        candidates=normalized_candidates,
        confidence=confidence,
        reason_codes=sorted(set(reason_codes)),
    )


def extract_family_retry_spo(
    *,
    text: str,
    citation_label: str,
    doc_title: str,
    quality_family: str,
    struct_kind: str = "",
    legal_unit_subtype: str = "",
) -> DeterministicExtraction:
    """Second-pass deterministic retry for law and appendix-heavy empty rows."""
    family = (quality_family or "").strip().lower()
    if family not in {"law", "appendix_heavy", "treaty_protocol"}:
        return DeterministicExtraction(candidates=[], confidence=0.0, reason_codes=["retry_not_applicable"])

    merged_candidates: list[SPOCandidate] = []
    merged_reason_codes: list[str] = []
    seen_keys: set[tuple[str, str]] = set()

    for chunk in _iter_retry_chunks(text, quality_family=family, struct_kind=struct_kind):
        extraction = extract_deterministic_spo(
            text=chunk,
            citation_label=citation_label,
            doc_title=doc_title,
            legal_unit_subtype=legal_unit_subtype,
            quality_family=family,
        )
        if not extraction.candidates:
            continue
        for candidate in extraction.candidates:
            key = (candidate.predicate, candidate.fact_text)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged_candidates.append(candidate)
        merged_reason_codes.extend(extraction.reason_codes)

    if not merged_candidates:
        return DeterministicExtraction(candidates=[], confidence=0.0, reason_codes=["retry_no_match"])

    confidence = min(0.9, max(candidate.confidence for candidate in merged_candidates))
    merged_candidates = [
        candidate.model_copy(update={"confidence": confidence})
        for candidate in merged_candidates
    ]
    return DeterministicExtraction(
        candidates=merged_candidates,
        confidence=confidence,
        reason_codes=sorted({"retry_clause_split", *merged_reason_codes}),
    )
