"""Stage 2: Lightweight provision extraction reusing UA regex from corpus/structure.py.

No CAS, no world events — just text → list of ProvisionSpan.
Designed for batch processing of 140K documents.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from polisyos.lex.corpus.structure import (
    _POINT_RE_LIST,
    _SUBPOINT_RE,
    _LineSpan,
    _ProvisionCandidate,
    _build_candidates,
    _citation_label,
    _iter_lines_with_offsets,
    _ruleset_for,
)
from polisyos.lex.types import LexStructureOptions

logger = logging.getLogger(__name__)


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


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _anchor_depth(anchor_path: str) -> int:
    return anchor_path.count("/") + 1 if anchor_path else 0


def _chunk_full_text(
    *,
    text: str,
    chunk_chars: int,
    overlap_chars: int,
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
            )
        )
        if end >= n:
            break
        start = max(end - safe_overlap, start + 1)
        idx += 1

    return spans


def extract_provisions(
    text: str,
    *,
    jurisdiction: str = "UA",
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

    lines = _iter_lines_with_offsets(text)

    try:
        ruleset = _ruleset_for(jurisdiction)
    except Exception:
        # Unsupported jurisdiction — chunk whole text instead of monolithic full_text.
        return _chunk_full_text(
            text=text,
            chunk_chars=fallback_chunk_chars,
            overlap_chars=fallback_chunk_overlap,
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
        # No articles found — chunk text to avoid giant prompts.
        return _chunk_full_text(
            text=text,
            chunk_chars=fallback_chunk_chars,
            overlap_chars=fallback_chunk_overlap,
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
            )
        )

    return spans
