"""Public claims canonicalize module API."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from decimal import Decimal

from polisyos.fabric._numeric_parsing import parse_decimal_text
from polisyos.ir.kernel.base import ID_PATTERN

_ID_RE = re.compile(ID_PATTERN)

_UNIT_ALIASES: dict[str, str] = {
    "%": "percent",
    "pct": "percent",
    "percent": "percent",
    "unit.m": "m",
    "meter": "m",
    "metre": "m",
    "m": "m",
    "unit.km": "km",
    "km": "km",
    "usd": "usd",
    "$": "usd",
    "uah": "uah",
    "year": "year",
    "month": "month",
}


def _transliterate_fragment(fragment: str) -> str:
    decomposed = unicodedata.normalize("NFKD", fragment)
    stripped = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return stripped.encode("ascii", "ignore").decode("ascii")


def _encode_unicode_char(char: str) -> str:
    return f"u{ord(char):04x}"


def _canonicalize_char(char: str, *, transliterate: bool) -> str:
    if char in "/\\" or char.isspace():
        return "_"
    if char in "_.-":
        return char
    if char.isascii():
        return char if char.isalnum() else "_"
    if transliterate:
        transliterated = _transliterate_fragment(char).casefold()
        cleaned = "".join(
            fragment for fragment in transliterated if fragment.isalnum() or fragment in "_.-"
        )
        if cleaned:
            return cleaned
    if unicodedata.category(char)[:1] in {"L", "N"}:
        return _encode_unicode_char(char)
    return "_"


def canonicalize_id(raw: str, *, transliterate: bool = False) -> str | None:
    """Canonicalize an identifier while preserving non-ASCII information."""
    value = unicodedata.normalize("NFKC", raw).casefold().strip()
    if not value:
        return None
    value = "".join(_canonicalize_char(char, transliterate=transliterate) for char in value)
    value = re.sub(r"_+", "_", value)
    value = re.sub(r"\.+", ".", value)
    value = re.sub(r"-+", "-", value)
    value = value.strip("_.-")
    if not value:
        return None
    if not value[0].isalpha():
        value = f"id_{value}"
    if _ID_RE.fullmatch(value) is None:
        return None
    return value


def canonical_unit(raw_unit: str) -> str | None:
    """Canonical unit helper."""
    value = unicodedata.normalize("NFKC", raw_unit).casefold().strip()
    if not value:
        return None
    alias = _UNIT_ALIASES.get(value)
    if alias is not None:
        return alias
    return canonicalize_id(value)


def parse_decimal_value_text(value_text: str) -> Decimal | None:
    """Parse decimal value text helper."""
    return parse_decimal_text(value_text)


def detect_canonical_id_collisions(
    raw_values: Iterable[str],
    *,
    transliterate: bool = False,
) -> dict[str, tuple[str, ...]]:
    """Find raw values that collapse to the same canonical id."""
    buckets: dict[str, set[str]] = {}
    for raw in raw_values:
        canonical = canonicalize_id(raw, transliterate=transliterate)
        if canonical is None:
            continue
        buckets.setdefault(canonical, set()).add(raw)
    return {
        canonical: tuple(sorted(raws))
        for canonical, raws in sorted(buckets.items())
        if len(raws) > 1
    }


def canonical_decimal_text(value: Decimal) -> str:
    """Canonical decimal text helper."""
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered == "-0":
        return "0"
    return rendered


__all__ = [
    "canonical_decimal_text",
    "canonical_unit",
    "canonicalize_id",
    "detect_canonical_id_collisions",
    "parse_decimal_value_text",
]
