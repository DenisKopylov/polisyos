from __future__ import annotations

import math
from fractions import Fraction
from typing import TYPE_CHECKING

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.connectors.contracts import (
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
    validate_dataframe_against_schema,
)
from polisyos.fabric.data_plane.modes import _sanitize_stream_rows
from polisyos.fabric.data_plane.quarantine import list_quarantine_records, load_quarantine_payload
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


if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("allowed_values", "value", "expected"),
    [
        (frozenset({"allowed"}), "allowed", None),
        (frozenset({"allowed"}), "outside", "schema_allowed_values_violation"),
        (frozenset(), "allowed", "schema_allowed_values_violation"),
        (None, "outside", None),
        (frozenset({"7"}), 7, "schema_type_mismatch"),
    ],
)
def test_category_allowed_values_are_checked_after_type_membership(
    allowed_values: frozenset[str] | None,
    value: object,
    expected: str | None,
) -> None:
    field = FieldSpec(name="category", data_type=SchemaType.CATEGORY, allowed_values=allowed_values)
    assert field_value_violation(value, field) == expected


@pytest.mark.parametrize("batch_size", [1, 3, 8])
@pytest.mark.parametrize("allowed_values", [frozenset({"allowed"}), frozenset(), None])
def test_category_batch_membership_and_quarantine_survive_fresh_cas_read(
    tmp_path: Path,
    batch_size: int,
    allowed_values: frozenset[str] | None,
) -> None:
    import pandas as pd

    rows: list[dict[str, object]] = [
        {"id": "allowed-1", "category": "allowed"},
        {"id": "outside-1", "category": "outside"},
        {"id": "missing"},
        {"id": "null", "category": None},
        {"id": "wrong-type", "category": 7},
        {"id": "allowed-2", "category": "allowed"},
        {"id": "outside-2", "category": "other"},
        {"id": "allowed-3", "category": "allowed"},
    ]
    schema = DataSchema(
        schema_id="test.stream.category_membership",
        version=SchemaVersion(1, 0, 0),
        fields=(
            FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False),
            FieldSpec(
                name="category",
                data_type=SchemaType.CATEGORY,
                presence="optional",
                nullable=True,
                allowed_values=allowed_values,
            ),
        ),
        primary_key=("id",),
        required_completeness=0.0,
    )
    store = FileSystemCAS(tmp_path / "cas")
    retained = []
    quarantined = 0
    for start in range(0, len(rows), batch_size):
        clean, _warnings, count = _sanitize_stream_rows(
            rows[start : start + batch_size],
            connector_id="finite-category-fixture",
            dataset_id="rows",
            store=store,
            chunk_index=start // batch_size,
            schema=schema,
        )
        retained.extend(clean)
        quarantined += count

    expected = [
        row
        for row in rows
        if row.get("category") is None
        or (
            isinstance(row["category"], str)
            and (allowed_values is None or row["category"] in allowed_values)
        )
    ]
    assert retained == expected
    assert quarantined == len(rows) - len(expected)
    fresh = FileSystemCAS(tmp_path / "cas")
    records = list_quarantine_records(fresh)
    assert len(records) == quarantined
    by_id = {
        load_quarantine_payload(fresh, record.raw_payload_ref)["id"]: record
        for _ref, record in records
    }
    for row in rows:
        if row in expected:
            continue
        reason = (
            "schema_type_mismatch"
            if row["id"] == "wrong-type"
            else "schema_allowed_values_violation"
        )
        record = by_id[row["id"]]
        assert record.context["field_violations"] == {"category": reason}
        assert load_quarantine_payload(fresh, record.raw_payload_ref) == row

    # Compare only CATEGORY string membership with the existing DataFrame sibling.
    for value in ("allowed", "outside"):
        errors = validate_dataframe_against_schema(
            pd.DataFrame([{"id": "sibling", "category": value}]), schema
        )
        allowed = allowed_values is None or value in allowed_values
        assert (not errors) == allowed
