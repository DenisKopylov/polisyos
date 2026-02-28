"""Deterministic SPO extractor used before LLM routing."""

from __future__ import annotations

import re
from dataclasses import dataclass

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


def extract_deterministic_spo(
    *,
    text: str,
    citation_label: str,
    doc_title: str,
) -> DeterministicExtraction:
    """Extract high-confidence SPO candidates without LLM."""
    cleaned = text.strip()
    if not cleaned:
        return DeterministicExtraction(candidates=[], confidence=0.0, reason_codes=["empty"])

    reason_codes: list[str] = []
    candidates: list[SPOCandidate] = []
    subject = "орган, що прийняв акт"
    quote = _clip_text(cleaned, size=400)

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
    if thresholds:
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

    if not candidates:
        return DeterministicExtraction(candidates=[], confidence=0.0, reason_codes=["no_match"])

    has_high_precision = any(
        code in reason_codes
        for code in ("entry_into_force_pattern", "repeal_pattern", "amendment_pattern", "approval_pattern", "amend_citation_pattern")
    )
    has_threshold = "threshold_pattern" in reason_codes or bool(_PERCENT_OR_NUMBER_RE.search(cleaned))
    fallback_like = "повний текст" in citation_label.lower()
    confidence = 0.45
    if has_high_precision:
        confidence += 0.25
    if has_threshold:
        confidence += 0.15
    if len(candidates) >= 2:
        confidence += 0.08
    if not fallback_like:
        confidence += 0.07
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

