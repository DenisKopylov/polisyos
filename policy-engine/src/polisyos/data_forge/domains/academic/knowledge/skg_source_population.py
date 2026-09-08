"""Read a complete retained numeric-reference population for an exact request.

This is a lexical source discovery surface, not a scientific eligibility filter.
An absent literal label does not establish semantic absence, and a matching label
does not establish a causal estimand, proposal relation, uncertainty or transport.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Literal

import duckdb
from pydantic import Field

from .skg_identity_bridge import (
    SourceSnapshot,
    _json_bytes,
    _require_snapshot,
    _retained_columns,
    _StrictModel,
)

if TYPE_CHECKING:
    from pathlib import Path

_TABLE = "ac_skg_simulation_parameters"
_COLUMNS = (
    "numeric_id",
    "openalex_id",
    "canonical_name",
    "linked_claim_ids_json",
    "linked_edges_json",
)


class SourceNumericReference(_StrictModel):
    """Stored reference text, including nulls and malformed candidate links."""

    numeric_id: str | None
    openalex_id: str | None
    canonical_name: str | None
    linked_claim_ids_json: str | None
    linked_edges_json: str | None


class SourceReferencePopulation(_StrictModel):
    """Complete projected table denominator and a deliberately lexical match set."""

    purpose: Literal["retained_numeric_reference_discovery"] = (
        "retained_numeric_reference_discovery"
    )
    source_reference: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_variable: str | None
    status: Literal["reference_population_recomputed", "refused"]
    table: Literal["ac_skg_simulation_parameters"] = "ac_skg_simulation_parameters"
    columns: tuple[str, ...] = _COLUMNS
    rows: tuple[SourceNumericReference, ...]
    row_count: int | None = Field(ge=0)
    distinct_numeric_id_count: int | None = Field(ge=0)
    distinct_variable_name_count: int | None = Field(ge=0)
    projection_sha256: str | None = Field(pattern=r"^[0-9a-f]{64}$")
    literal_target_row_indices: tuple[int, ...]
    refusal_reasons: tuple[str, ...]
    semantic_target_coverage: Literal["not_established"] = "not_established"
    scientific_eligibility: Literal["not_established"] = "not_established"
    source_snapshot_authenticity: Literal["not_established"] = "not_established"


def read_source_reference_population(
    *, source: SourceSnapshot, target_variable: str | None, scratch: Path
) -> SourceReferencePopulation:
    """Recompute all retained numeric references without a LIMIT or fuzzy mapping.

    The selected source is independently supplied. Only materialized native text
    columns in its base table are accepted; external reads and unbound WALs are
    refused. Counts describe this projection, never the calibration population.
    """
    _require_snapshot(source)
    if target_variable is not None and (type(target_variable) is not str or not target_variable):
        raise ValueError("source_target_variable_invalid")
    scratch.mkdir(parents=True, exist_ok=True)
    rows: tuple[SourceNumericReference, ...] = ()
    reasons: tuple[str, ...] = ()
    with duckdb.connect(
        str(source.path), read_only=True, config={"temp_directory": str(scratch.resolve())}
    ) as con:
        con.execute("SET enable_external_access = false")
        try:
            types = {column[0]: str(column[1]) for column in _retained_columns(con, _TABLE)}
            if any(types.get(name) not in {"VARCHAR", "JSON"} for name in _COLUMNS):
                raise ValueError("source_reference_columns_missing_or_nontext")
            # The fixed projection preserves native text; sorting uses its complete bytes.
            values = con.execute(
                "SELECT numeric_id, openalex_id, canonical_name, "
                "linked_claim_ids_json, linked_edges_json "
                "FROM main.ac_skg_simulation_parameters"
            ).fetchall()
            projected = [dict(zip(_COLUMNS, value, strict=True)) for value in values]
            projected.sort(key=_json_bytes)
            rows = tuple(SourceNumericReference.model_validate(value) for value in projected)
        except (ValueError, duckdb.Error) as exc:
            reasons = (f"{type(exc).__name__}:{exc}",)
    _require_snapshot(source)
    return SourceReferencePopulation(
        source_reference=source.reference,
        source_sha256=source.sha256,
        target_variable=target_variable,
        status="refused" if reasons else "reference_population_recomputed",
        rows=rows,
        row_count=None if reasons else len(rows),
        distinct_numeric_id_count=(
            None if reasons else len({row.numeric_id for row in rows if row.numeric_id is not None})
        ),
        distinct_variable_name_count=(
            None
            if reasons
            else len({row.canonical_name for row in rows if row.canonical_name is not None})
        ),
        projection_sha256=(
            None
            if reasons
            else hashlib.sha256(
                _json_bytes([row.model_dump(mode="json") for row in rows])
            ).hexdigest()
        ),
        literal_target_row_indices=tuple(
            index
            for index, row in enumerate(rows)
            if target_variable is not None and row.canonical_name == target_variable
        ),
        refusal_reasons=reasons,
    )
