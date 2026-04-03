"""Public backends lex norm regex v 1 module API."""
from __future__ import annotations

import re
from decimal import Decimal

from polisyos.ir.world.doc import DocMeta

from ..canonicalize import canonical_unit, canonicalize_id, parse_decimal_value_text
from ..types import ChunkContext, ClaimCandidate, ClaimExtractOptions

_LINE_RE = re.compile(
    r"^(?:(?:\d+[.)]|[a-zа-я]\))\s*)?(?:norm|claim)\s*:\s*(?P<body>.+)$",
    flags=re.IGNORECASE,
)
_EXPR_RE = re.compile(r"^(?P<left>.+?)\s*(?P<op><=|>=|=|<|>)\s*(?P<right>.+)$")
_LEFT_RE = re.compile(r"^(?P<predicate>[^()]+?)(?:\((?P<subject>[^()]*)\))?$")
_RIGHT_RE = re.compile(r"^(?P<value>.*?)(?:\s*\[(?P<unit>[^\[\]]+)\])?$")


def _parse_line(line: str) -> tuple[str, str | None, str, str | None, str] | None:
    cleaned = line.split("#", 1)[0].strip()
    if not cleaned:
        return None

    line_match = _LINE_RE.fullmatch(cleaned)
    if line_match is None:
        return None

    expr_match = _EXPR_RE.fullmatch(line_match.group("body").strip())
    if expr_match is None:
        return None

    left_match = _LEFT_RE.fullmatch(expr_match.group("left").strip())
    if left_match is None:
        return None

    predicate_raw = left_match.group("predicate").strip()
    subject_text_raw = left_match.group("subject")
    subject_text = subject_text_raw.strip() if subject_text_raw else None
    if subject_text == "":
        subject_text = None

    right_match = _RIGHT_RE.fullmatch(expr_match.group("right").strip())
    if right_match is None:
        return None

    value_text = right_match.group("value").strip()
    if not value_text:
        return None

    unit_raw = right_match.group("unit")
    unit_raw = unit_raw.strip() if unit_raw else None

    op = expr_match.group("op")
    return predicate_raw, subject_text, value_text, unit_raw, op


def extract(
    *,
    ctx: ChunkContext,
    meta: DocMeta,
    normalized_text: str,
    options: ClaimExtractOptions,
) -> list[ClaimCandidate]:
    """Extract helper."""
    del meta

    chunk_text = normalized_text[ctx.offset_start : ctx.offset_end]
    max_per_chunk = options.max_claims_per_chunk

    out: list[ClaimCandidate] = []
    for line in chunk_text.splitlines():
        parsed = _parse_line(line)
        if parsed is None:
            continue

        predicate_raw, subject_text, value_text, unit_raw, op = parsed
        predicate_id = canonicalize_id(predicate_raw)
        if predicate_id is None:
            continue

        unit_id = canonical_unit(unit_raw) if unit_raw is not None else None
        value_decimal = parse_decimal_value_text(value_text)

        out.append(
            ClaimCandidate(
                predicate_id=predicate_id,
                subject_id=None,
                subject_text=subject_text,
                value_text=value_text,
                value_decimal=value_decimal,
                unit_id=unit_id,
                confidence=Decimal("0.6"),
                qualifiers={"op": op},
                props={"lex": {"operator": op}},
                citation_fragment_id=ctx.fragment_id,
            )
        )
        if max_per_chunk is not None and len(out) >= max_per_chunk:
            break

    return out


__all__ = ["extract"]
