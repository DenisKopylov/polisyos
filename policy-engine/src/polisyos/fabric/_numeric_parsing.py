"""Shared decimal text normalization helpers for Fabric."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

__all__ = [
    "normalize_decimal_text",
    "parse_decimal_text",
]


_SPACE_RE = re.compile(r"[\s\u00a0\u2007\u202f_]+")
_NUMERIC_RE = re.compile(r"^(?P<sign>[+-]?)(?P<mantissa>\d[\d.,]*)(?P<exponent>[eE][+-]?\d+)?$")


def _normalize_mantissa(mantissa: str) -> str | None:
    dot_count = mantissa.count(".")
    comma_count = mantissa.count(",")

    if dot_count and comma_count:
        decimal_sep = "." if mantissa.rfind(".") > mantissa.rfind(",") else ","
        thousands_sep = "," if decimal_sep == "." else "."
        parts = mantissa.split(decimal_sep)
        if len(parts) != 2:
            return None
        integer_part, fractional_part = parts
        if not integer_part or not fractional_part or thousands_sep in fractional_part:
            return None
        integer_digits = integer_part.replace(thousands_sep, "")
        if not integer_digits.isdigit() or not fractional_part.isdigit():
            return None
        return f"{integer_digits}.{fractional_part}"

    if dot_count or comma_count:
        separator = "." if dot_count else ","
        parts = mantissa.split(separator)

        if len(parts) == 2:
            integer_part, fractional_part = parts
            if (
                not integer_part
                or not fractional_part
                or not integer_part.isdigit()
                or not fractional_part.isdigit()
            ):
                return None
            if (
                separator == ","
                and len(fractional_part) == 3
                and len(integer_part) <= 3
                and integer_part != "0"
            ):
                return f"{integer_part}{fractional_part}"
            return f"{integer_part}.{fractional_part}"

        if all(part and part.isdigit() for part in parts) and all(
            len(part) == 3 for part in parts[1:]
        ):
            return "".join(parts)

        return None

    if mantissa.isdigit():
        return mantissa

    return None


def normalize_decimal_text(value_text: str) -> str | None:
    """Normalize locale-formatted decimal text to Decimal-compatible ASCII."""
    normalized = unicodedata.normalize("NFKC", value_text).strip()
    if not normalized:
        return None

    normalized = normalized.replace("\u2212", "-")
    normalized = _SPACE_RE.sub("", normalized)
    match = _NUMERIC_RE.fullmatch(normalized)
    if match is None:
        return None

    mantissa = _normalize_mantissa(match.group("mantissa"))
    if mantissa is None:
        return None

    sign = match.group("sign") or ""
    exponent = match.group("exponent") or ""
    return f"{sign}{mantissa}{exponent}"


def parse_decimal_text(value_text: str) -> Decimal | None:
    """Parse locale-formatted decimal text into ``Decimal`` safely."""
    normalized = normalize_decimal_text(value_text)
    if normalized is None:
        return None
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):  # pragma: no cover - defensive
        return None
