from __future__ import annotations

from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from polisyos.lex.common import collapse_ws, parse_iso_date


@given(text=st.text(max_size=240))
@settings(max_examples=120)
def test_collapse_ws_is_idempotent_and_removes_runs(text: str) -> None:
    collapsed = collapse_ws(text)

    assert collapse_ws(collapsed) == collapsed
    assert collapsed == collapsed.strip()
    assert "  " not in collapsed


@given(value=st.dates(min_value=date(1900, 1, 1), max_value=date(2100, 12, 31)))
@settings(max_examples=100)
def test_parse_iso_date_round_trips_iso_dates(value: date) -> None:
    assert parse_iso_date(value.isoformat()) == value
    assert parse_iso_date(f" {value.isoformat()} ") == value
