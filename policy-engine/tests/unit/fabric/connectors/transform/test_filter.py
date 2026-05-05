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
