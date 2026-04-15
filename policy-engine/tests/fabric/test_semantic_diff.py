from __future__ import annotations

from polisyos.fabric.connectors.contracts.schema import DataSchema, FieldSpec, SchemaType, SemanticType
from polisyos.fabric.data_plane.semantic_diff import compare_historical_rows


def test_semantic_diff_uses_primary_key_and_detects_row_revisions() -> None:
    schema = DataSchema(
        schema_id="fixture.metrics",
        version="1.0",
        fields=(
            FieldSpec(name="country_code", data_type=SchemaType.STRING, semantic_type=SemanticType.CODE),
            FieldSpec(name="year", data_type=SchemaType.INT32, semantic_type=SemanticType.TEMPORAL),
            FieldSpec(name="policy_cost", data_type=SchemaType.FLOAT64, semantic_type=SemanticType.CURRENCY),
        ),
        primary_key=("country_code", "year"),
        time_dimension="year",
    )

    report = compare_historical_rows(
        schema,
        [{"country_code": "USA", "year": 2024, "policy_cost": 100.0}],
        schema,
        [
            {"country_code": "USA", "year": 2024, "policy_cost": 125.0},
            {"country_code": "CAN", "year": 2024, "policy_cost": 90.0},
        ],
    )

    assert report.key_fields == ["country_code", "year"]
    assert report.summary.row_revised == 1
    assert report.summary.row_added == 1
    assert report.summary.material_revision is True
    revised = next(item for item in report.changes if item.change_type == "row_revised")
    assert revised.numeric_deltas["policy_cost"] == 25.0


def test_semantic_diff_degrades_when_grain_cannot_be_derived() -> None:
    left_schema = DataSchema(
        schema_id="fixture.no_grain",
        version="1.0",
        fields=(FieldSpec(name="value", data_type=SchemaType.FLOAT64),),
    )
    right_schema = DataSchema(
        schema_id="fixture.no_grain",
        version="1.1",
        fields=(
            FieldSpec(name="value", data_type=SchemaType.FLOAT64),
            FieldSpec(name="extra", data_type=SchemaType.STRING),
        ),
    )

    report = compare_historical_rows(
        left_schema,
        [{"value": 1.0}],
        right_schema,
        [{"value": 1.0, "extra": "x"}],
    )

    assert report.summary.manual_review_required is True
    assert report.summary.schema_only is True
    assert report.notes == ["manual_review_required:grain_not_derivable"]


def test_semantic_diff_reports_duplicate_keys_explicitly() -> None:
    schema = DataSchema(
        schema_id="fixture.duplicates",
        version="1.0",
        fields=(
            FieldSpec(name="country_code", data_type=SchemaType.STRING, semantic_type=SemanticType.CODE),
            FieldSpec(name="year", data_type=SchemaType.INT32, semantic_type=SemanticType.TEMPORAL),
            FieldSpec(name="value", data_type=SchemaType.FLOAT64),
        ),
        primary_key=("country_code", "year"),
        time_dimension="year",
    )

    report = compare_historical_rows(
        schema,
        [
            {"country_code": "USA", "year": 2024, "value": 100.0},
            {"country_code": "USA", "year": 2024, "value": 101.0},
        ],
        schema,
        [{"country_code": "USA", "year": 2024, "value": 100.0}],
    )

    assert report.summary.duplicate_keys_left == 1
    assert report.summary.duplicate_keys_right == 0
    assert report.summary.manual_review_required is True
    assert any(note.startswith("duplicate_keys:left:") for note in report.notes)
