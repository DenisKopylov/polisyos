"""Behavioral tests for normalization transforms."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from polisyos.fabric.connectors.transform.normalizer import NormalizationTransform
from polisyos.fabric.connectors.transform.pipeline import TransformContext


def test_normalization_converts_units_and_preserves_missing_values() -> None:
    transform = NormalizationTransform(
        unit_conversions={"distance": ("km", "m")},
        cast_to_schema=False,
    )

    result, _lineage, warnings = transform.apply(
        pd.DataFrame({"distance": [1.5, None]}),
        TransformContext(),
    )

    assert warnings == []
    assert result["distance"].iloc[0] == Decimal("1500.0")
    assert pd.isna(result["distance"].iloc[1])


def test_normalization_casts_values_using_the_safe_coercion_path() -> None:
    transform = NormalizationTransform(
        type_casts={"count": "int64"},
        cast_to_schema=False,
    )

    result, _lineage, warnings = transform.apply(
        pd.DataFrame({"count": ["1", "2"]}),
        TransformContext(),
    )

    assert warnings == []
    assert result["count"].tolist() == [1, 2]


def test_pandas_safe_cast_preserves_dynamic_extension_dtype_values() -> None:
    transform = NormalizationTransform(cast_to_schema=False)

    result = transform._pandas_safe_cast(pd.Series(["left", "right"]), "category")

    assert result.tolist() == ["left", "right"]
    assert isinstance(result.dtype, pd.CategoricalDtype)
