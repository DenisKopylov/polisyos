"""Public backends regex numeric v 1 module API."""

from __future__ import annotations

import re
from decimal import Decimal

from polisyos.ir.world.doc import DocMeta

from ..canonicalize import canonical_unit, canonicalize_id, parse_decimal_value_text
from ..types import ChunkContext, ClaimCandidate, ClaimExtractOptions

_NUMERIC_RE = re.compile(
    r"(?P<num>[+-]?(?:\d{1,3}(?:[.,\u00a0\u202f\s]\d{3})+|\d+)(?:[.,]\d+)?(?:[eE][+-]?\d+)?)"
    r"\s*(?P<unit>percent|pct|usd|uah|year|month|km|m|%)(?=\b|[^0-9A-Za-z_]|$)",
    flags=re.IGNORECASE,
)


def extract(
    *,
    ctx: ChunkContext,
    meta: DocMeta,
    normalized_text: str,
    options: ClaimExtractOptions,
) -> list[ClaimCandidate]:
    """Extract helper."""
    chunk_text = normalized_text[ctx.offset_start : ctx.offset_end]
    max_per_chunk = options.max_claims_per_chunk

    out: list[ClaimCandidate] = []
    for match in _NUMERIC_RE.finditer(chunk_text):
        value_text = match.group("num").strip()
        value_decimal = parse_decimal_value_text(value_text)
        if value_decimal is None:
            continue
        unit_id = canonical_unit(match.group("unit"))
        if unit_id is None:
            continue
        predicate_id = canonicalize_id(f"extract.numeric.{unit_id}")
        if predicate_id is None:
            continue
        out.append(
            ClaimCandidate(
                predicate_id=predicate_id,
                subject_id=meta.doc_source_id,
                subject_text=None,
                value_text=value_text,
                value_decimal=value_decimal,
                unit_id=unit_id,
                confidence=Decimal("0.3"),
                qualifiers={},
                props={},
                citation_fragment_id=ctx.fragment_id,
            )
        )
        if max_per_chunk is not None and len(out) >= max_per_chunk:
            break
    return out


__all__ = ["extract"]
