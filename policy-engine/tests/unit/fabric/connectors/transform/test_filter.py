from __future__ import annotations

import pandas as pd
import pytest

from polisyos.fabric.connectors.transform.filter import FilterTransform
from polisyos.fabric.connectors.transform.pipeline import TransformContext, TransformError


def test_filter_transform_supports_boolean_ast_expressions() -> None:
    data = pd.DataFrame(
        {
            "country": ["UA", "DE", "UA"],
            "value": [10, 5, 0],
        }
    )

    transform = FilterTransform(condition="country == 'UA' and value > 0")
    result, _lineage, warnings = transform.apply(data, TransformContext())

    assert warnings == []
    assert result["country"].tolist() == ["UA"]
    assert result["value"].tolist() == [10]


def test_filter_transform_supports_in_membership() -> None:
    data = pd.DataFrame({"country": ["UA", "DE", "FR"], "value": [1, 2, 3]})

    transform = FilterTransform(condition="country in ['UA', 'FR']")
    result, _lineage, _warnings = transform.apply(data, TransformContext())

    assert result["country"].tolist() == ["UA", "FR"]


def test_filter_transform_rejects_code_execution_attempts() -> None:
    data = pd.DataFrame({"country": ["UA"], "value": [1]})
    transform = FilterTransform(condition="__import__('os').system('id')")

    with pytest.raises(TransformError, match="Unsafe filter condition"):
        transform.apply(data, TransformContext())


def test_filter_transform_rejects_attribute_access() -> None:
    data = pd.DataFrame({"country": ["UA"], "value": [1]})
    transform = FilterTransform(condition="country.str.startswith('U')")

    with pytest.raises(TransformError, match="Unsafe filter condition"):
        transform.apply(data, TransformContext())


def test_filter_transform_supports_numeric_unary_and_arithmetic_operations() -> None:
    data = pd.DataFrame({"value": [1, 3, 5]})

    transform = FilterTransform(
        condition="0 < value and +(value - 2) * 2 / 2 > 0 and -value < 0 and (value + 1) % 2 == 0"
    )
    result, _lineage, warnings = transform.apply(data, TransformContext())

    assert warnings == []
    assert result["value"].tolist() == [3, 5]


@pytest.mark.parametrize(
    ("condition", "expected_index"),
    [
        ("1 == 1", [20, 21, 22]),
        ("1 != 1", []),
        ("2 > 1", [20, 21, 22]),
        ("2 >= 3", []),
        ("1 < 2", [20, 21, 22]),
        ("1 <= 0", []),
        ("left == 3", [21]),
        ("left != 3", [20, 22]),
        ("left > 3", [22]),
        ("left >= 3", [21, 22]),
        ("left < 3", [20]),
        ("left <= 3", [20, 21]),
        ("3 == right", [21]),
        ("3 != right", [20, 22]),
        ("3 > right", [20]),
        ("3 >= right", [20, 21]),
        ("3 < right", [22]),
        ("3 <= right", [21, 22]),
        ("left == right", [21]),
        ("left != right", [20, 22]),
        ("left > right", [22]),
        ("left >= right", [21, 22]),
        ("left < right", [20]),
        ("left <= right", [20, 21]),
    ],
)
def test_filter_transform_preserves_comparison_dispatch_across_operand_shapes(
    condition: str,
    expected_index: list[int],
) -> None:
    data = pd.DataFrame(
        {"left": [1, 3, 5], "right": [2, 3, 4]},
        index=[20, 21, 22],
    )

    result, _lineage, warnings = FilterTransform(condition=condition).apply(
        data,
        TransformContext(),
    )

    assert warnings == []
    assert result.index.tolist() == expected_index


@pytest.mark.parametrize(
    ("condition", "expected_index"),
    [
        ("'a' in 'cat'", [10, 20]),
        ("'z' in 'cat'", []),
        ("'z' not in 'cat'", [10, 20]),
        ("'a' not in 'cat'", []),
        ("1 in [1, 2]", [10, 20]),
        ("1 not in [2, 3]", [10, 20]),
        ("10 in value", [10, 20]),
        ("100 in value", []),
        ("10 not in value", []),
        ("100 not in value", [10, 20]),
    ],
)
def test_filter_transform_preserves_scalar_left_python_membership(
    condition: str,
    expected_index: list[int],
) -> None:
    data = pd.DataFrame({"value": [100, 200]}, index=[10, 20])

    result, _lineage, warnings = FilterTransform(condition=condition).apply(
        data,
        TransformContext(),
    )

    assert warnings == []
    assert result.index.tolist() == expected_index


@pytest.mark.parametrize("operator", ["in", "not in"])
@pytest.mark.parametrize("right_hand_side", ["1", "other"])
def test_filter_transform_rejects_nonliteral_membership_for_series_left(
    operator: str,
    right_hand_side: str,
) -> None:
    data = pd.DataFrame({"value": [1, 2], "other": [1, 2]})

    with pytest.raises(TransformError, match="Unsafe filter condition"):
        FilterTransform(condition=f"value {operator} {right_hand_side}").apply(
            data,
            TransformContext(),
        )


def test_filter_transform_preserves_series_not_in_literal_membership() -> None:
    data = pd.DataFrame({"country": ["UA", "DE", "FR"]})

    result, _lineage, warnings = FilterTransform(
        condition="country not in ['UA', 'FR']",
    ).apply(data, TransformContext())

    assert warnings == []
    assert result["country"].tolist() == ["DE"]
