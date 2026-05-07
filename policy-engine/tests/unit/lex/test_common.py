from __future__ import annotations

from datetime import date

from polisyos.lex.common import collapse_ws, parse_iso_date


def test_common_collapses_whitespace_without_touching_words() -> None:
    assert collapse_ws("  legal\n\ttext   with   gaps ") == "legal text with gaps"


def test_common_parses_iso_date_and_datetime_strings() -> None:
    assert parse_iso_date("2026-05-06") == date(2026, 5, 6)
    assert parse_iso_date("2026-05-06T14:30:00Z") == date(2026, 5, 6)
    assert parse_iso_date("not-a-date") is None
