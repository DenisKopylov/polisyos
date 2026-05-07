from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from polisyos.fabric._internal.numeric_parsing import normalize_decimal_text, parse_decimal_text


@st.composite
def _decimal_texts(draw: st.DrawFn) -> tuple[str, Decimal]:
    sign = draw(st.sampled_from(["", "+", "-"]))
    integer = draw(st.integers(min_value=0, max_value=10**9))
    fraction_len = draw(st.sampled_from([1, 2, 4, 5, 6]))
    fraction = draw(st.integers(min_value=0, max_value=(10**fraction_len) - 1))
    separator = draw(st.sampled_from([".", ","]))
    rendered_fraction = f"{fraction:0{fraction_len}d}"
    text = f"{sign}{integer}{separator}{rendered_fraction}"
    expected = Decimal(f"{sign}{integer}.{rendered_fraction}")
    return text, expected


@given(example=_decimal_texts())
@settings(max_examples=120)
def test_decimal_text_parser_preserves_decimal_value(example: tuple[str, Decimal]) -> None:
    text, expected = example

    assert parse_decimal_text(text) == expected
    assert Decimal(normalize_decimal_text(text) or "NaN") == expected


@given(value=st.integers(min_value=1000, max_value=10**12))
@settings(max_examples=80)
def test_grouped_integer_text_parses_as_whole_number(value: int) -> None:
    grouped = f"{value:,}"

    assert parse_decimal_text(grouped) == Decimal(value)
    assert parse_decimal_text(grouped.replace(",", "_")) == Decimal(value)
