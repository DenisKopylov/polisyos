"""
Core DataSchema Pydantic model and hashing helpers.

Provides:
- DataSchema: immutable dataset schema with CAS-compatible content hashing,
  multi-backend type mapping (pandas, JAX, DuckDB), and schema evolution helpers
- Helper functions for deterministic content hashing of field payloads
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.quality.finite import ensure_probability
from polisyos.fabric.quality.safety import validate_sql_identifier
from polisyos.ir.kernel.units import UnitRef

from ._schema_field import SCHEMA_ID_PATTERN, FieldSpec, SchemaVersion, make_schema_id
from ._schema_types import GeoGranularity, TimeGranularity

__all__ = [
    "DataSchema",
]


# =============================================================================
# Hashing helpers
# =============================================================================


def _float_token(value: float | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {"_type": "float", "repr": format(value, ".17g")}


def _number_token(value: int | float | None) -> int | dict[str, str] | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    return _float_token(float(value))


def _sorted_list(values: Sequence[str] | set[str] | frozenset[str]) -> list[str]:
    return sorted(values)


def _unit_id(unit: UnitRef | None) -> str | None:
    return unit.unit_id if unit else None


def _field_hash_payload(field: FieldSpec) -> dict[str, Any]:
    payload = {
        "name": field.name,
        "data_type": field.data_type.value,
        "element_type": field.element_type.value if field.element_type else None,
        "unit": _unit_id(field.unit),
        "display_unit": field.display_unit,
        "semantic_type": field.semantic_type.value if field.semantic_type else None,
        "additivity": field.additivity.value if field.additivity else None,
        "nullable": field.nullable,
        "bounds": [_number_token(field.bounds[0]), _number_token(field.bounds[1])],
        "allowed_values": (
            _sorted_list(field.allowed_values) if field.allowed_values is not None else None
        ),
        "pattern": field.pattern,
        "max_length": field.max_length,
        "precision": field.precision,
        "scale": field.scale,
        "expected_completeness": _float_token(field.expected_completeness),
        "tags": _sorted_list(field.tags),
    }
    if field.field_id is not None:
        payload["field_id"] = field.field_id
    return payload


# =============================================================================
# Data Schema
# =============================================================================


class DataSchema(BaseModel):
    """
    Immutable schema definition for a dataset.

    Design principles:
    - Self-describing (no external schema registry required)
    - Versionable (supports schema evolution)
    - Composable (can merge schemas from multiple sources)
    - JAX-compatible (maps to array dtypes at Foundry boundary)
    - CAS-addressable (deterministic hash for caching)

    Relationship to DataContract:
    - DataContract: metric-level metadata (single column)
    - DataSchema: dataset-level structure (all columns)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Identity
    schema_id: str = Field(
        ...,
        pattern=SCHEMA_ID_PATTERN,
        description="Unique schema identifier (e.g., 'worldbank.wdi.gdp')",
    )
    version: SchemaVersion = Field(..., description="Semantic version")

    # Structure
    fields: tuple[FieldSpec, ...] = Field(..., min_length=1)
    primary_key: tuple[str, ...] = Field(
        default=(),
        description="Fields comprising the primary key",
    )
    grain_dims: tuple[str, ...] = Field(
        default=(),
        description="Dimensions that define record grain (entity keys)",
    )

    # Temporal semantics
    time_dimension: str | None = Field(
        default=None,
        description="Field representing time dimension",
    )
    time_granularity: TimeGranularity | None = Field(
        default=None,
        description="Temporal granularity of data",
    )

    # Spatial semantics
    geo_dimension: str | None = Field(
        default=None,
        description="Field representing geographic dimension",
    )
    geo_granularity: GeoGranularity | None = Field(
        default=None,
        description="Geographic granularity of data",
    )

    # Quality expectations
    required_completeness: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable data completeness",
    )
    allowed_null_fields: frozenset[str] = Field(
        default_factory=frozenset,
        description="Fields explicitly allowed to have nulls",
    )

    # Metadata
    description: str = Field(default="", max_length=2048)
    source: str = Field(default="", max_length=256)
    tags: frozenset[str] = Field(default_factory=frozenset)
    created_at: datetime | None = Field(default=None)

    @field_validator("version", mode="before")
    @classmethod
    def _parse_version(cls, value: SchemaVersion | str | dict[str, Any]) -> SchemaVersion:
        if isinstance(value, SchemaVersion):
            return value
        if isinstance(value, str):
            return SchemaVersion.parse(value)
        if isinstance(value, Mapping):
            return SchemaVersion(**value)
        raise TypeError("version must be SchemaVersion or version string")

    @field_validator("required_completeness", mode="after")
    @classmethod
    def _validate_required_completeness(cls, value: float) -> float:
        return ensure_probability(value, what="required_completeness")

    @model_validator(mode="after")
    def validate_field_references(self) -> DataSchema:
        """Validate that referenced fields exist."""
        field_names = {f.name for f in self.fields}

        for pk_field in self.primary_key:
            if pk_field not in field_names:
                raise ValueError(f"Primary key field '{pk_field}' not found in schema")

        for grain_field in self.grain_dims:
            if grain_field not in field_names:
                raise ValueError(f"Grain dimension '{grain_field}' not found in schema")

        if self.time_dimension and self.time_dimension not in field_names:
            raise ValueError(f"Time dimension '{self.time_dimension}' not found in schema")

        if self.geo_dimension and self.geo_dimension not in field_names:
            raise ValueError(f"Geo dimension '{self.geo_dimension}' not found in schema")

        for null_field in self.allowed_null_fields:
            if null_field not in field_names:
                raise ValueError(f"Allowed null field '{null_field}' not found in schema")

        return self

    @model_validator(mode="after")
    def validate_unique_field_names(self) -> DataSchema:
        """Ensure field names are unique."""
        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate field names: {set(duplicates)}")
        return self

    @model_validator(mode="after")
    def validate_unique_field_ids(self) -> DataSchema:
        """Ensure stable field identities are unique within the schema."""
        ids = [field.stable_id for field in self.fields]
        if len(ids) != len(set(ids)):
            duplicates = sorted({field_id for field_id in ids if ids.count(field_id) > 1})
            raise ValueError(f"Duplicate field ids: {duplicates}")
        return self

    def get_field(self, name: str) -> FieldSpec | None:
        """Get field by name."""
        return next((f for f in self.fields if f.name == name), None)

    def get_field_by_id(self, field_id: str) -> FieldSpec | None:
        """Get field by stable id."""
        return next((f for f in self.fields if f.stable_id == field_id), None)

    def field_names(self) -> list[str]:
        """Get ordered list of field names."""
        return [f.name for f in self.fields]

    def field_ids(self) -> list[str]:
        """Get ordered list of stable field identities."""
        return [f.stable_id for f in self.fields]

    def effective_grain_dims(self) -> tuple[str, ...]:
        """Return grain dimensions, falling back to primary_key if unspecified."""
        if self.grain_dims:
            return self.grain_dims
        return self.primary_key

    def numeric_fields(self) -> list[FieldSpec]:
        """Get fields that can be used in numeric computations."""
        return [f for f in self.fields if f.data_type.is_numeric()]

    def to_pandas_dtypes(self) -> dict[str, str]:
        """Convert to pandas dtype specification."""
        return {f.name: f.data_type.to_pandas_dtype() for f in self.fields}

    def to_jax_dtypes(self, *, strict: bool = False) -> dict[str, Any]:
        """
        Convert to JAX dtype specification for Foundry boundary.

        Only includes fields that can cross into JAX (numeric types).
        Non-numeric fields are excluded.
        """
        result: dict[str, Any] = {}
        for f in self.fields:
            jax_dtype = f.data_type.to_jax_dtype(strict=strict)
            if jax_dtype is not None:
                result[f.name] = jax_dtype
        return result

    def jax_excluded_fields(self) -> list[str]:
        """Get fields that cannot cross into JAX."""
        return [f.name for f in self.fields if not f.data_type.is_numeric()]

    def to_duckdb_schema(self) -> str:
        """
        Generate DuckDB CREATE TABLE column specification.

        Returns just the columns part: (col1 TYPE, col2 TYPE, ...)
        """
        columns = [f.to_duckdb_column_def() for f in self.fields]
        pk_clause = ""
        if self.primary_key:
            primary_key_columns = ", ".join(
                validate_sql_identifier(pk_field, what="schema primary key")
                for pk_field in self.primary_key
            )
            pk_clause = f", PRIMARY KEY ({primary_key_columns})"
        return f"({', '.join(columns)}{pk_clause})"

    def to_duckdb_create_table(self, table_name: str) -> str:
        """Generate full DuckDB CREATE TABLE statement."""
        table_sql = validate_sql_identifier(table_name, what="schema table", allow_dotted=True)
        return f"CREATE TABLE {table_sql} {self.to_duckdb_schema()}"

    @property
    def content_hash(self) -> str:
        """
        CAS-compatible content hash for caching.

        Hash is based on schema content only (excludes schema_id/version).
        """
        from polisyos.core.canon import to_canonical_bytes

        canonical_dict = {
            "fields": [_field_hash_payload(f) for f in self.fields],
            "primary_key": list(self.primary_key),
            "grain_dims": list(self.grain_dims),
            "time_dimension": self.time_dimension,
            "time_granularity": self.time_granularity.value if self.time_granularity else None,
            "geo_dimension": self.geo_dimension,
            "geo_granularity": self.geo_granularity.value if self.geo_granularity else None,
            "required_completeness": _float_token(self.required_completeness),
            "allowed_null_fields": _sorted_list(self.allowed_null_fields),
            "tags": _sorted_list(self.tags),
        }

        canonical = to_canonical_bytes(canonical_dict)
        return compute_content_hash(canonical, prefix=True)

    @property
    def identity_key(self) -> tuple[str, str, str]:
        """Stable identity tuple combining ID, version, and content hash."""
        return (self.schema_id, str(self.version), self.content_hash)

    def select_fields(self, names: Sequence[str]) -> DataSchema:
        """Create a new schema with only the specified fields."""
        selected = tuple(f for f in self.fields if f.name in names)
        if not selected:
            raise ValueError("No matching fields found")

        selected_names = {f.name for f in selected}
        new_pk = tuple(pk for pk in self.primary_key if pk in selected_names)
        new_time = self.time_dimension if self.time_dimension in selected_names else None
        new_geo = self.geo_dimension if self.geo_dimension in selected_names else None

        return DataSchema(
            schema_id=make_schema_id(self.schema_id, "selected"),
            version=self.version,
            fields=selected,
            primary_key=new_pk,
            grain_dims=tuple(g for g in self.grain_dims if g in selected_names),
            time_dimension=new_time,
            time_granularity=self.time_granularity if new_time else None,
            geo_dimension=new_geo,
            geo_granularity=self.geo_granularity if new_geo else None,
            required_completeness=self.required_completeness,
            allowed_null_fields=self.allowed_null_fields & selected_names,
            description=self.description,
            source=self.source,
            tags=self.tags,
        )

    def add_field(self, field: FieldSpec) -> DataSchema:
        """Create a new schema with an additional field."""
        if any(f.name == field.name for f in self.fields):
            raise ValueError(f"Field '{field.name}' already exists")

        return DataSchema(
            schema_id=self.schema_id,
            version=self.version.bump_minor(),
            fields=(*self.fields, field),
            primary_key=self.primary_key,
            grain_dims=self.grain_dims,
            time_dimension=self.time_dimension,
            time_granularity=self.time_granularity,
            geo_dimension=self.geo_dimension,
            geo_granularity=self.geo_granularity,
            required_completeness=self.required_completeness,
            allowed_null_fields=self.allowed_null_fields,
            description=self.description,
            source=self.source,
            tags=self.tags,
        )
