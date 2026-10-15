"""Canonical DuckDB schema for persisted core-source alignment audit rows.

New tables use the `graph_builder_v1_json` layout. The exact
`registry_v1_varchar` layout remains readable and writable for databases
created by the earlier registry DDL. No data migration is implied here; a
future schema migration must be explicit and carry its own identity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import duckdb

AlignmentAuditSchemaProfile = Literal["registry_v1_varchar", "graph_builder_v1_json"]
AlignmentAuditColumnSignature = tuple[int, str, str, bool, object | None, int]
AlignmentAuditTableSignature = tuple[AlignmentAuditColumnSignature, ...]
AlignmentReviewBasisSchemaProfile = Literal["v1"]
AlignmentReviewBasisTableSignature = tuple[AlignmentAuditColumnSignature, ...]


@dataclass(frozen=True, slots=True)
class AlignmentAuditColumn:
    """Describe one column in the alignment audit table's canonical schema."""

    name: str
    sql_type: str
    nullable: bool = True
    default_expression: str | None = None
    primary_key: bool = False


_BASE_ALIGNMENT_AUDIT_COLUMNS = (
    AlignmentAuditColumn("audit_id", "VARCHAR", nullable=False, primary_key=True),
    AlignmentAuditColumn("dataset_id", "VARCHAR", nullable=False),
    AlignmentAuditColumn("raw_variable", "VARCHAR", nullable=False),
    AlignmentAuditColumn("canonical_variable", "VARCHAR"),
    AlignmentAuditColumn("method", "VARCHAR", nullable=False),
    AlignmentAuditColumn("raw_confidence", "FLOAT"),
    AlignmentAuditColumn("calibrated_confidence", "FLOAT"),
    AlignmentAuditColumn("alternatives_json", "JSON", default_expression="'[]'"),
    AlignmentAuditColumn("resolved_at", "VARCHAR"),
    AlignmentAuditColumn("reviewed", "BOOLEAN", default_expression="FALSE"),
    AlignmentAuditColumn("reviewer_override", "VARCHAR", default_expression="NULL"),
)
_PROFILE_ALTERNATIVES_JSON_TYPES: dict[AlignmentAuditSchemaProfile, str] = {
    "registry_v1_varchar": "VARCHAR",
    "graph_builder_v1_json": "JSON",
}
_ALIGNMENT_REVIEW_BASIS_COLUMNS = (
    AlignmentAuditColumn("dataset_id", "VARCHAR", nullable=False, primary_key=True),
    AlignmentAuditColumn("raw_variable", "VARCHAR", nullable=False, primary_key=True),
    AlignmentAuditColumn("basis_version", "VARCHAR", nullable=False),
    AlignmentAuditColumn("basis_json", "JSON", nullable=False),
    AlignmentAuditColumn("basis_sha256", "VARCHAR", nullable=False),
)


def alignment_audit_columns(
    profile: AlignmentAuditSchemaProfile = "graph_builder_v1_json",
) -> tuple[AlignmentAuditColumn, ...]:
    """Return the ordered column definitions for one accepted physical profile."""
    try:
        alternatives_json_type = _PROFILE_ALTERNATIVES_JSON_TYPES[profile]
    except KeyError as exc:
        raise ValueError(f"unsupported alignment audit schema profile: {profile!r}") from exc
    return tuple(
        replace(column, sql_type=alternatives_json_type)
        if column.name == "alternatives_json"
        else column
        for column in _BASE_ALIGNMENT_AUDIT_COLUMNS
    )


def _create_alignment_audit_table_sql(
    profile: AlignmentAuditSchemaProfile,
) -> str:
    definitions = []
    for column in alignment_audit_columns(profile):
        pieces = [column.name, column.sql_type]
        if column.primary_key:
            pieces.append("PRIMARY KEY")
        elif not column.nullable:
            pieces.append("NOT NULL")
        if column.default_expression is not None:
            pieces.extend(("DEFAULT", column.default_expression))
        definitions.append("    " + " ".join(pieces))
    return "CREATE TABLE IF NOT EXISTS ds_alignment_audit (\n" + ",\n".join(definitions) + "\n)"


def create_alignment_audit_table(
    con: duckdb.DuckDBPyConnection,
    *,
    profile: AlignmentAuditSchemaProfile = "graph_builder_v1_json",
) -> None:
    """Create the alignment audit table from the shared schema definition."""
    con.execute(_create_alignment_audit_table_sql(profile))


def alignment_audit_table_signature(
    con: duckdb.DuckDBPyConnection,
) -> AlignmentAuditTableSignature:
    """Read a fresh complete physical signature from DuckDB's table catalog."""
    rows = con.execute("PRAGMA table_info('ds_alignment_audit')").fetchall()
    return tuple(
        (int(row[0]), str(row[1]), str(row[2]), bool(row[3]), row[4], int(row[5])) for row in rows
    )


@lru_cache(maxsize=1)
def _known_alignment_audit_signatures() -> tuple[
    tuple[AlignmentAuditSchemaProfile, AlignmentAuditTableSignature], ...
]:
    """Derive accepted signatures by executing this module's creation DDL."""
    import duckdb

    signatures: list[tuple[AlignmentAuditSchemaProfile, AlignmentAuditTableSignature]] = []
    for profile in _PROFILE_ALTERNATIVES_JSON_TYPES:
        scratch = duckdb.connect(":memory:")
        try:
            create_alignment_audit_table(scratch, profile=profile)
            signatures.append((profile, alignment_audit_table_signature(scratch)))
        finally:
            scratch.close()
    return tuple(signatures)


def resolve_alignment_audit_schema_profile(
    con: duckdb.DuckDBPyConnection,
) -> AlignmentAuditSchemaProfile:
    """Match the live table against one exact, source-qualified schema profile.

    The live signature is always re-read. Only the pure signatures generated
    from this module's DDL are cached.
    """
    live_signature = alignment_audit_table_signature(con)
    for profile, expected_signature in _known_alignment_audit_signatures():
        if live_signature == expected_signature:
            return profile
    raise RuntimeError(
        "ds_alignment_audit has an unsupported physical schema; "
        "expected exact registry_v1_varchar or graph_builder_v1_json profile"
    )


def _create_alignment_review_basis_table_sql() -> str:
    """Return the one canonical v1 sidecar table definition."""
    definitions = []
    for column in _ALIGNMENT_REVIEW_BASIS_COLUMNS:
        pieces = [column.name, column.sql_type]
        if not column.primary_key and not column.nullable:
            pieces.append("NOT NULL")
        if column.default_expression is not None:
            pieces.extend(("DEFAULT", column.default_expression))
        definitions.append("    " + " ".join(pieces))
    primary_key_columns = [
        column.name for column in _ALIGNMENT_REVIEW_BASIS_COLUMNS if column.primary_key
    ]
    definitions.append("    PRIMARY KEY (" + ", ".join(primary_key_columns) + ")")
    return (
        "CREATE TABLE IF NOT EXISTS ds_alignment_review_basis (\n" + ",\n".join(definitions) + "\n)"
    )


def create_alignment_review_basis_table(con: duckdb.DuckDBPyConnection) -> None:
    """Create the internal operational review-basis sidecar using its canonical schema."""
    con.execute(_create_alignment_review_basis_table_sql())


def alignment_review_basis_table_signature(
    con: duckdb.DuckDBPyConnection,
) -> AlignmentReviewBasisTableSignature:
    """Read the fresh complete physical signature of the operational basis sidecar."""
    rows = con.execute("PRAGMA table_info('ds_alignment_review_basis')").fetchall()
    return tuple(
        (int(row[0]), str(row[1]), str(row[2]), bool(row[3]), row[4], int(row[5])) for row in rows
    )


@lru_cache(maxsize=1)
def _known_alignment_review_basis_signature() -> AlignmentReviewBasisTableSignature:
    """Derive the supported sidecar signature by executing its canonical DDL."""
    import duckdb

    scratch = duckdb.connect(":memory:")
    try:
        create_alignment_review_basis_table(scratch)
        return alignment_review_basis_table_signature(scratch)
    finally:
        scratch.close()


def resolve_alignment_review_basis_schema(
    con: duckdb.DuckDBPyConnection,
) -> AlignmentReviewBasisSchemaProfile:
    """Fail closed unless the live sidecar matches the complete v1 physical schema."""
    if alignment_review_basis_table_signature(con) != _known_alignment_review_basis_signature():
        raise RuntimeError(
            "ds_alignment_review_basis has an unsupported physical schema; "
            "expected exact v1 profile"
        )
    return "v1"
