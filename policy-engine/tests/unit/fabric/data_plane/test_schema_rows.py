from __future__ import annotations

import math
from fractions import Fraction

import numpy as np

from polisyos.fabric.connectors.contracts import FieldSpec, SchemaType
from polisyos.fabric.data_plane.schema_rows import _type_member, field_value_violation


def test_integer_membership_normalizes_integral_values_without_admitting_out_of_range() -> None:
    assert _type_member(127, SchemaType.INT8)
    assert _type_member(-128, SchemaType.INT8)
    assert not _type_member(128, SchemaType.INT8)
    assert _type_member(255, SchemaType.UINT8)
    assert not _type_member(-1, SchemaType.UINT8)
    assert _type_member(np.int64(127), SchemaType.INT8)
    assert _type_member(np.uint64(255), SchemaType.UINT8)
    assert not _type_member(True, SchemaType.INT8)
    assert not _type_member(127.0, SchemaType.INT8)
    assert not _type_member(float("nan"), SchemaType.INT8)


def test_numeric_bounds_preserve_native_fraction_to_float_comparison() -> None:
    field = FieldSpec(
        name="ratio",
        data_type=SchemaType.FLOAT64,
        bounds=(0.2, None),
    )

    assert field_value_violation(Fraction(1, 5), field) == "schema_bounds_violation"
    assert field_value_violation(0.2, field) is None
    assert _type_member(float("nan"), SchemaType.FLOAT64)
    assert field_value_violation(math.nan, field) == "schema_non_finite"
