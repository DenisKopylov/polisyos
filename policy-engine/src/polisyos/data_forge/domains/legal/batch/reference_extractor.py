"""Deterministic extractor for cross-references inside legal provisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.legal.batch.doc_identity import doc_type_category
from polisyos.data_forge.domains.legal.batch.patterns import (
    ARTICLEISH_REFERENCE_RE,
    REFERENCE_AMENDS_RE,
    REFERENCE_APPLIES_TO_RE,
    REFERENCE_APPROVES_RE,
    REFERENCE_ENTRY_INTO_FORCE_RE,
    REFERENCE_PATTERNS_UA,
    REFERENCE_REPEALS_RE,
)

if TYPE_CHECKING:
    import re

    from polisyos.data_forge.domains.legal.batch.jurisdictions.protocol import JurisdictionPlugin

_ARTICLEish_RE = ARTICLEISH_REFERENCE_RE
_AMENDS_RE = REFERENCE_AMENDS_RE
_REPEALS_RE = REFERENCE_REPEALS_RE
_APPROVES_RE = REFERENCE_APPROVES_RE
_ENTRY_INTO_FORCE_RE = REFERENCE_ENTRY_INTO_FORCE_RE
_APPLIES_TO_RE = REFERENCE_APPLIES_TO_RE


@dataclass(frozen=True)
class ReferenceHit:
    """One extracted legal reference."""

    doc_id: str
    anchor_path: str
    source_span_start: int
    source_span_end: int
    target_raw: str
    ref_type: str
    confidence: float
    target_number: str = ""
    target_date: str = ""
    target_doc_type: str = ""
    relation_hint: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "anchor_path": self.anchor_path,
            "source_span_start": self.source_span_start,
            "source_span_end": self.source_span_end,
            "target_raw": self.target_raw,
            "type": self.ref_type,
            "confidence": self.confidence,
            "target_number": self.target_number,
            "target_date": self.target_date,
            "target_doc_type": self.target_doc_type,
            "relation_hint": self.relation_hint,
        }


_REFERENCE_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = REFERENCE_PATTERNS_UA


def _relation_hint(text: str, start: int, end: int) -> str:
    left_boundary = max(
        text.rfind(".", 0, start), text.rfind("\n", 0, start), text.rfind(";", 0, start)
    )
    right_candidates = [
        pos for pos in (text.find(".", end), text.find("\n", end), text.find(";", end)) if pos >= 0
    ]
    right_boundary = min(right_candidates) if right_candidates else len(text)
    context = text[left_boundary + 1 : right_boundary]
    if _REPEALS_RE.search(context):
        return "repeals"
    if _AMENDS_RE.search(context):
        return "amends"
    if _APPROVES_RE.search(context):
        return "approves"
    if _ENTRY_INTO_FORCE_RE.search(context):
        return "enters_into_force"
    if _APPLIES_TO_RE.search(context):
        return "applies_to"
    return "references"


def _resolved_doc_type(match: re.Match[str]) -> str:
    groups = match.groupdict()
    if groups.get("title"):
        title = str(groups.get("title") or "")
        category = doc_type_category(title)
        if category:
            return category
    if groups.get("doc_type"):
        category = doc_type_category(str(groups.get("doc_type") or ""))
        if category:
            return category
    full = match.group(0)
    if "цього закону" in full.lower():
        return "self_reference"
    return ""


def extract_references(
    *,
    text: str,
    doc_id: str,
    anchor_path: str,
    jurisdiction_plugin: JurisdictionPlugin | None = None,
) -> list[ReferenceHit]:
    """Extract legal references from provision text."""
    hits: list[ReferenceHit] = []
    seen: set[tuple[int, int, str, str, str, str]] = set()
    patterns = (
        jurisdiction_plugin.reference_patterns()
        if jurisdiction_plugin is not None
        else _REFERENCE_PATTERNS
    )
    for ref_type, pattern, confidence in patterns:
        for match in pattern.finditer(text):
            target_raw = match.group(0).strip()
            if not target_raw:
                continue
            key = (
                match.start(),
                match.end(),
                target_raw,
                str(match.groupdict().get("number") or ""),
                str(match.groupdict().get("date") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            hit = ReferenceHit(
                doc_id=doc_id,
                anchor_path=anchor_path,
                source_span_start=match.start(),
                source_span_end=match.end(),
                target_raw=target_raw,
                ref_type=ref_type,
                confidence=confidence,
                target_number=str(match.groupdict().get("number") or ""),
                target_date=str(match.groupdict().get("date") or ""),
                target_doc_type=_resolved_doc_type(match),
                relation_hint=_relation_hint(text, match.start(), match.end()),
            )
            hits.append(hit)
    hits.sort(
        key=lambda item: (
            item.source_span_start,
            item.source_span_end,
            item.ref_type,
            item.target_raw,
        )
    )
    return hits
