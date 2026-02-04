from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from polisyos.ir.kernel.base import ID_PATTERN

_ID_RE = re.compile(ID_PATTERN)
_NUMERIC_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")

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


def canonicalize_id(raw: str) -> str | None:
    value = raw.strip().lower()
    value = value.replace("/", "_")
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^a-z0-9_.-]", "_", value)
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
    value = raw_unit.strip().lower()
    if not value:
        return None
    alias = _UNIT_ALIASES.get(value)
    if alias is not None:
        return alias
    return canonicalize_id(value)


def parse_decimal_value_text(value_text: str) -> Decimal | None:
    value = value_text.strip()
    if "," in value and "." not in value:
        value = value.replace(",", ".")
    if _NUMERIC_RE.fullmatch(value) is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):  # pragma: no cover - defensive
        return None


def canonical_decimal_text(value: Decimal) -> str:
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
    "parse_decimal_value_text",
]
