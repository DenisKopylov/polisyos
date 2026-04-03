"""Public backends explicit lines v 1 module API."""
from __future__ import annotations

import re
from decimal import Decimal

from polisyos.ir.world.doc import DocMeta

from ..canonicalize import canonical_unit, canonicalize_id
from ..types import ChunkContext, ClaimCandidate, ClaimExtractOptions

_LEFT_SIDE_RE = re.compile(r"^(?P<predicate>.+?)\s*\((?P<subject>[^()]*)\)\s*$")
_RIGHT_SIDE_RE = re.compile(r"^(?P<value>.*?)(?:\s*\[(?P<unit>[^\[\]]+)\])?$")


def _parse_claim_line(line: str) -> tuple[str, str | None, str, str | None] | None:
    cleaned = line.split("#", 1)[0].strip()
    if not cleaned.startswith("claim:"):
        return None
    payload = cleaned[len("claim:") :].strip()
    if "=" not in payload:
        return None
    left, right = payload.split("=", 1)

    left = left.strip()
    subject_text: str | None = None
    match_left = _LEFT_SIDE_RE.fullmatch(left)
    if match_left is not None:
        predicate_raw = match_left.group("predicate").strip()
        subject_text = match_left.group("subject").strip() or None
    else:
        predicate_raw = left

    right = right.strip()
    match_right = _RIGHT_SIDE_RE.fullmatch(right)
    if match_right is None:
        return None

    value_text = match_right.group("value").strip()
    if not value_text:
        return None
    unit_raw = match_right.group("unit")
    unit_raw = unit_raw.strip() if unit_raw else None
    return predicate_raw, subject_text, value_text, unit_raw


def extract(
    *,
    ctx: ChunkContext,
    meta: DocMeta,
    normalized_text: str,
    options: ClaimExtractOptions,
) -> list[ClaimCandidate]:
    """Extract helper."""
    del options  # deterministic backend has no tunables yet
    chunk_text = normalized_text[ctx.offset_start : ctx.offset_end]
    out: list[ClaimCandidate] = []
    for line in chunk_text.splitlines():
        parsed = _parse_claim_line(line)
        if parsed is None:
            continue
        predicate_raw, subject_text, value_text, unit_raw = parsed
        predicate_id = canonicalize_id(predicate_raw)
        if predicate_id is None:
            continue
        unit_id = canonical_unit(unit_raw) if unit_raw is not None else None
        out.append(
            ClaimCandidate(
                predicate_id=predicate_id,
                subject_id=meta.doc_source_id,
                subject_text=subject_text,
                value_text=value_text,
                value_decimal=None,
                unit_id=unit_id,
                confidence=Decimal("1"),
                qualifiers={},
                props={},
                citation_fragment_id=ctx.fragment_id,
            )
        )
    return out


__all__ = ["extract"]
