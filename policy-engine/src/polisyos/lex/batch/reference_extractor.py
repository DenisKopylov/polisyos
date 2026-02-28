"""Deterministic extractor for cross-references inside legal provisions."""

from __future__ import annotations

import re
from dataclasses import dataclass


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

    def as_dict(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "anchor_path": self.anchor_path,
            "source_span_start": self.source_span_start,
            "source_span_end": self.source_span_end,
            "target_raw": self.target_raw,
            "type": self.ref_type,
            "confidence": self.confidence,
        }


_REFERENCE_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (
        "article_reference",
        re.compile(
            r"відповідно до (?:статті|частини|пункту)\s+[\d\.]+\s+(.+?Закону\s+України[^,\.]+)",
            re.IGNORECASE,
        ),
        0.9,
    ),
    (
        "article_reference",
        re.compile(
            r"згідно з (?:статтею|частиною)\s+[\d\.]+\s+(.+?(?:Закону|Кодексу)[^,\.]+)",
            re.IGNORECASE,
        ),
        0.9,
    ),
    (
        "law_number",
        re.compile(
            r"Закон України від \d{2}\.\d{2}\.\d{4}\s*[№N]\s*([\d\-А-ЯA-Z]+)",
            re.IGNORECASE,
        ),
        0.96,
    ),
    (
        "doc_number_date",
        re.compile(
            r"[№N]\s*([\d]+[-–]?\w*)\s+від\s+(\d{2}\.\d{2}\.\d{4})",
            re.IGNORECASE,
        ),
        0.94,
    ),
    (
        "cabinet_resolution",
        re.compile(
            r"постанов[аи]\s+(?:Кабінету Міністрів|КМУ)[^,\.]+від[^,\.]+",
            re.IGNORECASE,
        ),
        0.9,
    ),
)


def extract_references(*, text: str, doc_id: str, anchor_path: str) -> list[ReferenceHit]:
    """Extract legal references from provision text."""
    hits: list[ReferenceHit] = []
    for ref_type, pattern, confidence in _REFERENCE_PATTERNS:
        for match in pattern.finditer(text):
            target_raw = match.group(0).strip()
            if match.lastindex and match.group(1):
                # Prefer object-like captured part when available.
                target_raw = str(match.group(1)).strip() or target_raw
            if not target_raw:
                continue
            hits.append(
                ReferenceHit(
                    doc_id=doc_id,
                    anchor_path=anchor_path,
                    source_span_start=match.start(),
                    source_span_end=match.end(),
                    target_raw=target_raw,
                    ref_type=ref_type,
                    confidence=confidence,
                )
            )
    return hits

