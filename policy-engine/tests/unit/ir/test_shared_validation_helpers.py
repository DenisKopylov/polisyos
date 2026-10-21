from __future__ import annotations

import math
from array import array
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal

import pytest

from polisyos.ir._internal.validation import (
    coerce_float,
    ensure_confidence_interval,
    ensure_finite_numeric,
    ensure_interval_monotonicity,
    ensure_unique_ids,
)


@pytest.mark.parametrize(
    "value",
    [1, 1.5, Decimal("1.5"), "1.5", b"1.5", bytearray(b"1.5"), memoryview(b"1.5")],
)
def test_finite_numeric_helper_preserves_float_convertible_values(
    value: object,
) -> None:
    assert ensure_finite_numeric(value, field_name="value") is value


@pytest.mark.parametrize("value", [object(), float("nan"), float("inf")])
def test_finite_numeric_helper_rejects_non_finite_or_unconvertible_values(
    value: object,
) -> None:
    with pytest.raises(ValueError, match="value must be finite"):
        ensure_finite_numeric(value, field_name="value")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, 1.0),
        (Decimal("1.25"), 1.25),
        ("2.5", 2.5),
        (b"3.5", 3.5),
        (bytearray(b"4.5"), 4.5),
        (memoryview(b"5.5"), 5.5),
    ],
)
def test_float_coercion_preserves_python_float_protocol_values(
    value: object, expected: float
) -> None:
    assert coerce_float(value) == expected


class _FloatLike:
    def __float__(self) -> float:
        return 6.25


class _IndexLike:
    def __index__(self) -> int:
        return 7


class _FloatMethodMissing:
    __float__ = None


class _FloatRefusal:
    def __float__(self) -> float:
        raise ValueError("custom float refusal")


def _float_outcome(
    converter: Callable[[object], float], value: object
) -> tuple[float | None, tuple[type[Exception], str] | None]:
    try:
        return converter(value), None
    except Exception as error:
        return None, (type(error), str(error))


@pytest.mark.parametrize(
    "value",
    [
        "1.25",
        b"2.5",
        bytearray(b"3.75"),
        memoryview(b"4.5"),
        memoryview(b"bad"),
        bytearray(b"bad"),
        array("b", b"5.5"),
        array("b", b"bad"),
        Decimal("6.25"),
        _FloatLike(),
        _IndexLike(),
        True,
        False,
        None,
        object(),
        [],
        timedelta(seconds=1),
        _FloatMethodMissing(),
        _FloatRefusal(),
        float("nan"),
        float("inf"),
    ],
)
def test_float_coercion_matches_builtin_acceptance_and_exact_refusals(
    value: object,
) -> None:
    expected, expected_error = _float_outcome(float, value)
    actual, actual_error = _float_outcome(coerce_float, value)
    assert actual_error == expected_error
    if expected_error is None:
        assert expected is not None
        assert actual is not None
        if math.isnan(expected):
            assert math.isnan(actual)
        else:
            assert actual == expected


def test_float_coercion_matches_optional_numpy_scalar_conversion() -> None:
    numpy = pytest.importorskip("numpy")
    for value in (numpy.float64(1.25), numpy.int64(7), numpy.bool_(True)):
        assert coerce_float(value) == float(value)


def test_finite_numeric_wrapper_keeps_its_field_error_for_float_refusals() -> None:
    for value in (None, timedelta(seconds=1), _FloatMethodMissing(), _FloatRefusal()):
        with pytest.raises(ValueError, match="value must be finite"):
            ensure_finite_numeric(value, field_name="value")


def test_finite_numeric_wrapper_keeps_non_finite_domain_rejection() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="value must be finite"):
            ensure_finite_numeric(value, field_name="value")


def test_float_coercion_does_not_decide_finiteness() -> None:
    assert coerce_float(float("nan")) != coerce_float(float("nan"))
    with pytest.raises(ValueError, match="value must be finite"):
        ensure_finite_numeric(float("nan"), field_name="value")


@pytest.mark.parametrize("value", [None, object(), []])
def test_float_coercion_rejects_values_outside_python_float_protocol(
    value: object,
) -> None:
    with pytest.raises(TypeError):
        coerce_float(value)


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
