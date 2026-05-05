"""Structured amendment extraction from UA legal provisions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from polisyos.data_forge.domains.legal.batch.patterns import AMENDMENT_CORE_RE
from polisyos.data_forge.domains.legal.batch.temporal_parser import parse_temporal_constraints

# --- Structural amendment patterns (capture groups for target/old/new text) ---

_STRUCTURAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # "У статті N слова «X» замінити словами «Y»"
    (
        "replace_text",
        re.compile(
            r"[Уу]\s+(?:статт[іиюяею]|частин[іиау]|пункт[іиау])\s+(\d+(?:[-.]\d+)*)"
            r"(?:\s+(?:(?!\s+слова?\s+[«\"']).){0,180})?"
            r"\s+слова?\s+[«\"'](.*?)[»\"']\s+замінити\s+словами?\s+[«\"'](.*?)[»\"']",
            re.DOTALL | re.IGNORECASE,
        ),
    ),
    # "Статтю N викласти в такій/новій редакції:"
    (
        "modify_provision",
        re.compile(
            r"(?:статт[юяею]|частин[уау]|пункт)\s+(\d+(?:[-.]\d+)*)"
            r"\s+викласти\s+(?:в|у)\s+(?:такій|новій)\s+редакції\s*:\s*(.*?)(?=\n\s*\d+[\.\)]|\Z)",
            re.DOTALL | re.IGNORECASE,
        ),
    ),
    # "Доповнити статтею N-1 такого змісту:"
    (
        "add_provision",
        re.compile(
            r"[Дд]оповнити\s+(?:статтею|частиною|пунктом|абзацом|підпунктом)\s+([\d\-]+(?:[-.]\d+)*)"
            r"\s+такого\s+змісту\s*:\s*(.*?)(?=\n\s*\d+[\.\)]|\Z)",
            re.DOTALL | re.IGNORECASE,
        ),
    ),
    # "Статтю N виключити" / "Пункт N виключити"
    (
        "remove_provision",
        re.compile(
            r"(?:статт[юяею]|частин[уау]|пункт|підпункт|абзац)\s+(\d+(?:[-.]\d+)*)\s+виключити",
            re.IGNORECASE,
        ),
    ),
    # Passive forms: "доповнено наступним пунктом N"
    (
        "add_provision",
        re.compile(
            r"доповнено\s+(?:наступним\s+)?(?:пунктом|статтею|частиною|абзацом|підпунктом)\s+([\d\-]+(?:[-.]\d+)*)"
            r"(?:\s+такого\s+змісту\s*:\s*(.*?)(?=\n\s*\d+[\.\)]|\Z))?",
            re.DOTALL | re.IGNORECASE,
        ),
    ),
    # Passive: "виключено пункт N"
    (
        "remove_provision",
        re.compile(
            r"виключено\s+(?:пункт|статт[юяею]|частин[уау]|підпункт|абзац)\s+(\d+(?:[-.]\d+)*)",
            re.IGNORECASE,
        ),
    ),
    # "Внести такі зміни до статті N:"
    (
        "modify_provision",
        re.compile(
            r"внести\s+(?:такі\s+)?(?:зміни|доповнення)\s+до\s+(?:статт[іиюяею]|частин[іиау]|пункт[іиау])\s+(\d+(?:[-.]\d+)*)"
            r"(?:\s*:\s*(.*?)(?=\n\s*\d+[\.\)]|\Z))?",
            re.DOTALL | re.IGNORECASE,
        ),
    ),
    # "визнати таким(и), що втратив(ли) чинність" with anchor
    (
        "repeal_provision",
        re.compile(
            r"(?:статт[юяею]|частин[уау]|пункт|підпункт|абзац)\s+(\d+(?:[-.]\d+)*)"
            r"\s+визнати\s+(?:таким|такими)(?:,\s*що|\s+що)\s+втратив(?:ли)?\s+чинність",
            re.IGNORECASE,
        ),
    ),
    # "скасувати пункт/статтю N"
    (
        "repeal_provision",
        re.compile(
            r"скасувати\s+(?:статт[юяею]|частин[уау]|пункт|підпункт|абзац)\s+(\d+(?:[-.]\d+)*)",
            re.IGNORECASE,
        ),
    ),
    # "змінити назву статті N" / "змінити на ..."
    (
        "modify_provision",
        re.compile(
            r"змінити\s+(?:назву\s+)?(?:статт[іиюяею]|частин[іиау]|пункт[іиау])\s+(\d+(?:[-.]\d+)*)"
            r"(?:\s+на\s+(.*?)(?=\n\s*\d+[\.\)]|\Z))?",
            re.DOTALL | re.IGNORECASE,
        ),
    ),
    # Abbreviated anchors: "п. N виключити", "ч. N доповнити"
    (
        "remove_provision",
        re.compile(
            r"(?:п\.|пп\.|ч\.|абз\.)\s*(\d+(?:[-.]\d+)*)\s+виключити",
            re.IGNORECASE,
        ),
    ),
    (
        "modify_provision",
        re.compile(
            r"(?:п\.|пп\.|ч\.|абз\.)\s*(\d+(?:[-.]\d+)*)\s+(?:викласти|доповнити|змінити)"
            r"(?:\s+(?:в|у)\s+(?:такій|новій)\s+редакції)?\s*(?::\s*(.*?)(?=\n\s*\d+[\.\)]|\Z))?",
            re.DOTALL | re.IGNORECASE,
        ),
    ),
]

# --- Broad (non-structural) amendment signal: detects amendment-like provisions
# that don't have a clean structural anchor but still indicate amendment intent ---

_BROAD_AMENDMENT_RE = re.compile(
    r"(?:внести\s+(?:такі\s+)?(?:зміни|доповнення)\s+до|"
    r"внесення\s+змін\s+до|"
    r"доповнити\s+(?:цей|цю|це|зазначений|зазначену)(?:\s+\w+){0,3}?\s+(?:наступним|таким)|"
    r"замінити\s+(?:в\s+)?(?:тексті|документі|законі|постанові)(?:\s+\w+){0,3}?\s+слов|"
    r"увести\s+в\s+дію|ввести\s+в\s+дію|"
    r"вважати\s+(?:таким|такими)(?:,\s*що|\s+що)\s+втратив)",
    re.IGNORECASE,
)

_LOW_SIGNAL_FALLBACKS = {
    "виключено",
    "виключити",
    "доповнити",
    "доповнено",
    "увести",
    "ввести",
    "скасувати",
}
_FALLBACK_CONTEXT_RE = re.compile(
    r"(статт[іиюяею]|частин[іиау]|пункт[іиау]|підпункт|абзац|"
    r"закон(?:у)?\s+україни|кодекс(?:у)?\s+україни|постанова|наказ|указ|розпорядження|"
    r"внести\s+(?:такі\s+)?(?:зміни|доповнення)|внесення\s+змін)",
    re.IGNORECASE,
)
_AMENDMENT_SCAN_PREFILTER_RE = re.compile(
    r"(внести\s+(?:такі\s+)?(?:зміни|доповнення)|внесення\s+змін|"
    r"викласти\s+(?:в|у)\s+(?:такій|новій)\s+редакції|"
    r"доповнити|доповнено|замінити\s+слов(?:о|а|ами)|"
    r"слова?\s+[«\"']?[^»\"']+[»\"']?\s+замінити|"
    r"виключити|виключено|змінити\s+на|змінити\s+назву|"
    r"увести|ввести|визнати\s+(?:таким|такими).+?чинність|скасувати)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AmendmentRecord:
    """Structured amendment extracted from Ukrainian legal text."""

    amendment_type: str
    target_anchor: str
    old_text_uk: str
    new_text_uk: str
    effective_from: str
    confidence: float
    source_text: str


def _extract_target_anchor(groups: tuple[str, ...], amendment_type: str) -> str:
    if not groups:
        return ""
    anchor_num = groups[0]
    # Decide anchor prefix based on context (structural patterns always capture a number)
    return f"article:{anchor_num}"


def _should_keep_fallback_signal(text: str, match: re.Match[str]) -> bool:
    source_text = " ".join(match.group(0).split()).strip().lower()
    if source_text not in _LOW_SIGNAL_FALLBACKS:
        return True
    window = text[max(0, match.start() - 120) : min(len(text), match.end() + 120)]
    return bool(_FALLBACK_CONTEXT_RE.search(window))


def detect_amendments(text: str) -> list[AmendmentRecord]:
    """Extract structural and fallback amendment signals from provision text."""

    if not _AMENDMENT_SCAN_PREFILTER_RE.search(text):
        return []

    amendments: list[AmendmentRecord] = []
    seen_spans: set[tuple[int, int]] = set()
    effective_from: str | None = None

    def get_effective_from() -> str:
        nonlocal effective_from
        if effective_from is None:
            temporal = parse_temporal_constraints(text)
            effective_from = next(
                (item.effective_from_iso or "" for item in temporal if item.effective_from_iso),
                "",
            )
        return effective_from

    # Pass 1: structural patterns with captured anchors
    for amendment_type, pattern in _STRUCTURAL_PATTERNS:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if any(s <= span[0] < e or s < span[1] <= e for s, e in seen_spans):
                continue
            seen_spans.add(span)
            groups = match.groups()
            target_anchor = _extract_target_anchor(groups, amendment_type)
            old_text = groups[1] if amendment_type == "replace_text" and len(groups) > 2 else ""
            new_text = groups[-1] if len(groups) > 1 and groups[-1] else ""
            confidence = 0.88
            if amendment_type == "remove_provision":
                confidence = 0.92
            elif amendment_type == "repeal_provision":
                confidence = 0.90
            amendments.append(
                AmendmentRecord(
                    amendment_type=amendment_type,
                    target_anchor=target_anchor,
                    old_text_uk=old_text,
                    new_text_uk=new_text.strip() if new_text else "",
                    effective_from=get_effective_from(),
                    confidence=confidence,
                    source_text=match.group(0).strip()[:500],
                )
            )

    # Pass 2: broad amendment signals (lower confidence, no structural anchor)
    for match in _BROAD_AMENDMENT_RE.finditer(text):
        span = (match.start(), match.end())
        if any(s <= span[0] < e or s < span[1] <= e for s, e in seen_spans):
            continue
        seen_spans.add(span)
        amendments.append(
            AmendmentRecord(
                amendment_type="general_amendment",
                target_anchor="",
                old_text_uk="",
                new_text_uk="",
                effective_from=get_effective_from(),
                confidence=0.72,
                source_text=match.group(0).strip()[:500],
            )
        )

    # Pass 3: fallback to AMENDMENT_CORE_RE from pattern registry for remaining signals
    for match in AMENDMENT_CORE_RE.finditer(text):
        span = (match.start(), match.end())
        if any(
            abs(span[0] - s) < 15 or (s <= span[0] < e or s < span[1] <= e) for s, e in seen_spans
        ):
            continue
        if not _should_keep_fallback_signal(text, match):
            continue
        seen_spans.add(span)
        amendments.append(
            AmendmentRecord(
                amendment_type="amendment_signal",
                target_anchor="",
                old_text_uk="",
                new_text_uk="",
                effective_from=get_effective_from(),
                confidence=0.65,
                source_text=match.group(0).strip()[:500],
            )
        )

    return amendments
