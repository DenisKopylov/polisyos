"""Public data plane semantic diff module API."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import HistoricalSemanticDiffReportRef
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.feedback import (
    HistoricalSemanticDiffReport,
    HistoricalSemanticDiffSummary,
    HistoricalSemanticRowDelta,
)
from polisyos.fabric.connectors.contracts.evolution import SchemaEvolution
from polisyos.fabric.connectors.contracts.schema import DataSchema, SemanticType


_SEMANTIC_GRAIN_TYPES = {
    SemanticType.CODE,
    SemanticType.INDEX,
    SemanticType.IDENTIFIER,
}


def compare_historical_rows(
    left_schema: DataSchema,
    left_rows: Sequence[Mapping[str, Any]],
    right_schema: DataSchema,
    right_rows: Sequence[Mapping[str, Any]],
    *,
    left_data_ref: str | None = None,
    right_data_ref: str | None = None,
) -> HistoricalSemanticDiffReport:
    """Compare historical rows helper."""
    schema_report = SchemaEvolution().compare(left_schema, right_schema)
    key_fields, manual_review_required = _resolve_key_fields(left_schema, right_schema)

    summary = HistoricalSemanticDiffSummary(
        schema_only=False,
        material_revision=False,
        manual_review_required=manual_review_required,
        key_fields=list(key_fields),
        schema_change_types=[
            change.change_type.value
            for change in schema_report.changes
        ],
    )

    if manual_review_required:
        summary.schema_only = bool(schema_report.changes)
        return HistoricalSemanticDiffReport(
            left_schema_id=left_schema.schema_id,
            right_schema_id=right_schema.schema_id,
            left_data_ref=left_data_ref,
            right_data_ref=right_data_ref,
            key_fields=list(key_fields),
            summary=summary,
            notes=["manual_review_required:grain_not_derivable"],
        )

    left_index = _index_rows(left_rows, key_fields)
    right_index = _index_rows(right_rows, key_fields)
    all_keys = sorted(set(left_index) | set(right_index))
    changes: list[HistoricalSemanticRowDelta] = []
    numeric_fields = {
        field.name
        for field in right_schema.numeric_fields()
    } | {field.name for field in left_schema.numeric_fields()}
    semantic_fields = {
        field.name: field.semantic_type.value if field.semantic_type is not None else None
        for field in left_schema.fields
    }
    right_semantic_fields = {
        field.name: field.semantic_type.value if field.semantic_type is not None else None
        for field in right_schema.fields
    }

    matched_rows = 0
    for row_key in all_keys:
        left_row = left_index.get(row_key)
        right_row = right_index.get(row_key)
        if left_row is None and right_row is not None:
            changes.append(
                HistoricalSemanticRowDelta(
                    row_key=row_key,
                    change_type="row_added",
                    new_row=dict(right_row),
                )
            )
            continue
        if left_row is not None and right_row is None:
            changes.append(
                HistoricalSemanticRowDelta(
                    row_key=row_key,
                    change_type="row_removed",
                    old_row=dict(left_row),
                )
            )
            continue
        if left_row is None or right_row is None:
            continue

        matched_rows += 1
        field_deltas: dict[str, dict[str, Any]] = {}
        numeric_deltas: dict[str, float] = {}
        semantics_changed = False
        for field_name in sorted(set(left_row) | set(right_row)):
            left_value = left_row.get(field_name)
            right_value = right_row.get(field_name)
            if left_value == right_value:
                if semantic_fields.get(field_name) != right_semantic_fields.get(field_name):
                    semantics_changed = True
                continue
            field_deltas[field_name] = {
                "old": left_value,
                "new": right_value,
            }
            if field_name in numeric_fields:
                left_num = _as_float(left_value)
                right_num = _as_float(right_value)
                if left_num is not None and right_num is not None:
                    numeric_deltas[field_name] = round(right_num - left_num, 6)
            if semantic_fields.get(field_name) != right_semantic_fields.get(field_name):
                semantics_changed = True

        if field_deltas:
            changes.append(
                HistoricalSemanticRowDelta(
                    row_key=row_key,
                    change_type="field_semantics_changed" if semantics_changed else "row_revised",
                    field_deltas=field_deltas,
                    numeric_deltas=numeric_deltas,
                    old_row=dict(left_row),
                    new_row=dict(right_row),
                )
            )

    summary.row_added = sum(1 for item in changes if item.change_type == "row_added")
    summary.row_removed = sum(1 for item in changes if item.change_type == "row_removed")
    summary.row_revised = sum(1 for item in changes if item.change_type == "row_revised")
    summary.field_semantics_changed = sum(
        1 for item in changes if item.change_type == "field_semantics_changed"
    )
    summary.matched_rows = matched_rows
    summary.compared_rows = len(all_keys)
    summary.coverage_ratio = (
        matched_rows / len(all_keys) if all_keys else 1.0
    )
    summary.schema_only = bool(schema_report.changes) and not changes
    summary.material_revision = bool(
        summary.row_added
        or summary.row_removed
        or summary.row_revised
        or summary.field_semantics_changed
    )

    return HistoricalSemanticDiffReport(
        left_schema_id=left_schema.schema_id,
        right_schema_id=right_schema.schema_id,
        left_data_ref=left_data_ref,
        right_data_ref=right_data_ref,
        key_fields=list(key_fields),
        summary=summary,
        changes=changes,
        notes=[],
    )


def persist_historical_semantic_diff_report(
    store: FileSystemCAS,
    report: HistoricalSemanticDiffReport,
    *,
    inputs: list[InputRef] | None = None,
) -> HistoricalSemanticDiffReportRef:
    """Persist historical semantic diff report helper."""
    ref = store.put_json(
        report,
        PutOptions(
            kind="fabric.historical_semantic_diff_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.fabric.HistoricalSemanticDiffReport",
                version=report.schema_version,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return HistoricalSemanticDiffReportRef.model_validate(ref)


def _resolve_key_fields(left_schema: DataSchema, right_schema: DataSchema) -> tuple[tuple[str, ...], bool]:
    if left_schema.primary_key and left_schema.primary_key == right_schema.primary_key:
        return tuple(left_schema.primary_key), False

    derived: list[str] = []
    for field_name in (left_schema.time_dimension, left_schema.geo_dimension):
        if field_name and field_name in left_schema.field_names() and field_name in right_schema.field_names():
            derived.append(field_name)
    for field in left_schema.fields:
        if (
            field.semantic_type in _SEMANTIC_GRAIN_TYPES
            and field.name in right_schema.field_names()
            and field.name not in derived
        ):
            derived.append(field.name)
    if not derived:
        return tuple(), True
    return tuple(derived), False


def _index_rows(rows: Sequence[Mapping[str, Any]], key_fields: Sequence[str]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        row_key = _row_key(row, key_fields)
        index[row_key] = row
    return index


def _row_key(row: Mapping[str, Any], key_fields: Sequence[str]) -> str:
    return "|".join(f"{field}={row.get(field)!r}" for field in key_fields)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


__all__ = [
    "compare_historical_rows",
    "persist_historical_semantic_diff_report",
]
