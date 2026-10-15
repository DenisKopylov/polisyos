from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.ir._internal.validation import (
    ensure_confidence_interval,
    ensure_finite_numeric,
    ensure_interval_monotonicity,
    ensure_unique_ids,
)


@pytest.mark.parametrize(
    "value",
    [1, 1.5, Decimal("1.5"), "1.5", b"1.5", bytearray(b"1.5"), memoryview(b"1.5")],
)
def test_finite_numeric_helper_preserves_float_convertible_values(value: object) -> None:
    assert ensure_finite_numeric(value, field_name="value") is value


@pytest.mark.parametrize("value", [object(), float("nan"), float("inf")])
def test_finite_numeric_helper_rejects_non_finite_or_unconvertible_values(
    value: object,
) -> None:
    with pytest.raises(ValueError, match="value must be finite"):
        ensure_finite_numeric(value, field_name="value")


def test_interval_helper_keeps_dynamic_ordering_and_comparison_failure() -> None:
    ensure_interval_monotonicity("2024-01", "2024-02", label="month")

    with pytest.raises(ValueError, match="endpoints must be comparable"):
        ensure_interval_monotonicity(object(), object(), label="interval")


def test_confidence_interval_accepts_decimal_and_rejects_outside_point() -> None:
    ensure_confidence_interval(
        (Decimal("1.0"), Decimal("2.0")),
        point_estimate=Decimal("1.5"),
        label="estimate",
    )

    with pytest.raises(ValueError, match="point_estimate must lie inside estimate"):
        ensure_confidence_interval(
            (Decimal("1.0"), Decimal("2.0")),
            point_estimate=Decimal("2.1"),
            label="estimate",
        )


def test_unique_id_helper_supports_hashable_tuple_keys() -> None:
    with pytest.raises(ValueError, match="duplicate tuple key"):
        ensure_unique_ids(
            ["first", "second"],
            key_fn=lambda _item: ("same", 1),
            label="tuple key",
        )
