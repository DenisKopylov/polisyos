from __future__ import annotations

from decimal import Decimal

from polisyos.fabric._internal.numeric_parsing import normalize_decimal_text, parse_decimal_text


def test_numeric_parsing_normalizes_locale_decimal_text() -> None:
    assert normalize_decimal_text(" 1.234,50 ") == "1234.50"
    assert normalize_decimal_text("-1,234.50") == "-1234.50"
    assert parse_decimal_text("1,23e3") == Decimal("1.23E+3")


def test_numeric_parsing_rejects_ambiguous_or_empty_values() -> None:
    assert normalize_decimal_text("") is None
    assert normalize_decimal_text("1.2.3") is None
    assert parse_decimal_text("not a number") is None
