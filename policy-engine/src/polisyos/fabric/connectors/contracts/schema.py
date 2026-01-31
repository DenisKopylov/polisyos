"""
Data schema definitions for connector data contracts.

This module provides the canonical type system that bridges:
- Pandas DataFrames (data engineering)
- DuckDB storage (analytical queries)
- JAX arrays (scientific computing)

Design principles:
- Platform-agnostic canonical types
- Explicit type coercion rules
- CAS-compatible content hashing
- Immutable schema definitions
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.kernel.units import UnitRef

if TYPE_CHECKING:
    import jax.numpy as jnp


# =============================================================================
# Type Mappings
# =============================================================================


class SchemaType(str, Enum):
    """
    Canonical data types with multi-backend mapping.

    This enum is the single source of truth for data types, providing
    explicit conversions to platform-specific representations.

    Note: This is distinct from fabric/catalog/contract.DataType which
    is metric-focused. This version is schema-focused with full backend
    mapping support.
    """

    # Integer types
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"

    # Floating point types
    FLOAT16 = "float16"
    FLOAT32 = "float32"
    FLOAT64 = "float64"

    # Boolean
    BOOLEAN = "boolean"

    # String types
    STRING = "string"
    CATEGORY = "category"

    # Temporal types
    DATE = "date"
    DATETIME = "datetime"
    TIMESTAMP_TZ = "timestamp_tz"
    TIME = "time"
    DURATION = "duration"

    # Complex types
    ARRAY = "array"
    JSON = "json"
    BINARY = "binary"

    # Decimal (for exact financial calculations)
    DECIMAL = "decimal"

    def to_pandas_dtype(self) -> str:
        """
        Convert to pandas dtype specification.

        Uses nullable dtypes (Int64 vs int64) for proper NA handling.
        """
        mapping = {
            # Integers (nullable)
            SchemaType.INT8: "Int8",
            SchemaType.INT16: "Int16",
            SchemaType.INT32: "Int32",
            SchemaType.INT64: "Int64",
            SchemaType.UINT8: "UInt8",
            SchemaType.UINT16: "UInt16",
            SchemaType.UINT32: "UInt32",
            SchemaType.UINT64: "UInt64",
            # Floats
            SchemaType.FLOAT16: "Float32",  # Pandas doesn't have Float16
            SchemaType.FLOAT32: "Float32",
            SchemaType.FLOAT64: "Float64",
            # Boolean
            SchemaType.BOOLEAN: "boolean",  # nullable boolean
            # Strings
            SchemaType.STRING: "string",
            SchemaType.CATEGORY: "category",
            # Temporal
            SchemaType.DATE: "datetime64[ns]",
            SchemaType.DATETIME: "datetime64[ns]",
            SchemaType.TIMESTAMP_TZ: "datetime64[ns, UTC]",
            SchemaType.TIME: "object",  # No native time type
            SchemaType.DURATION: "timedelta64[ns]",
            # Complex
            SchemaType.ARRAY: "object",
            SchemaType.JSON: "object",
            SchemaType.BINARY: "object",
            SchemaType.DECIMAL: "object",  # Use decimal.Decimal
        }
        return mapping.get(self, "object")

    def to_jax_dtype(self, *, strict: bool = False) -> "jnp.dtype | None":
        """
        Convert to JAX dtype for the Foundry boundary.

        Returns None for types that cannot cross into JAX (strings,
        complex objects). The simulation layer must handle these
        separately or exclude them from array operations.

        Raises:
            JaxTypeError: If called on non-numeric type in strict mode.
        """
        try:
            import jax.numpy as jnp
        except Exception as exc:  # pragma: no cover - optional dependency
            if strict:
                raise JaxTypeError(self) from exc
            return None

        mapping = {
            # Integers
            SchemaType.INT8: jnp.int8,
            SchemaType.INT16: jnp.int16,
            SchemaType.INT32: jnp.int32,
            SchemaType.INT64: jnp.int64,
            SchemaType.UINT8: jnp.uint8,
            SchemaType.UINT16: jnp.uint16,
            SchemaType.UINT32: jnp.uint32,
            SchemaType.UINT64: jnp.uint64,
            # Floats
            SchemaType.FLOAT16: jnp.float16,
            SchemaType.FLOAT32: jnp.float32,
            SchemaType.FLOAT64: jnp.float64,
            # Boolean
            SchemaType.BOOLEAN: jnp.bool_,
        }
        dtype = mapping.get(self)
        if dtype is None and strict:
            raise JaxTypeError(self)
        return dtype

    def to_duckdb_type(self) -> str:
        """
        Convert to DuckDB type string for storage layer.

        DuckDB has rich type support including nested types.
        """
        mapping = {
            # Integers
            SchemaType.INT8: "TINYINT",
            SchemaType.INT16: "SMALLINT",
            SchemaType.INT32: "INTEGER",
            SchemaType.INT64: "BIGINT",
            SchemaType.UINT8: "UTINYINT",
            SchemaType.UINT16: "USMALLINT",
            SchemaType.UINT32: "UINTEGER",
            SchemaType.UINT64: "UBIGINT",
            # Floats
            SchemaType.FLOAT16: "REAL",  # DuckDB doesn't have FLOAT16
            SchemaType.FLOAT32: "REAL",
            SchemaType.FLOAT64: "DOUBLE",
            # Boolean
            SchemaType.BOOLEAN: "BOOLEAN",
            # Strings
            SchemaType.STRING: "VARCHAR",
            SchemaType.CATEGORY: "VARCHAR",  # Use VARCHAR with enum in practice
            # Temporal
            SchemaType.DATE: "DATE",
            SchemaType.DATETIME: "TIMESTAMP",
            SchemaType.TIMESTAMP_TZ: "TIMESTAMPTZ",
            SchemaType.TIME: "TIME",
            SchemaType.DURATION: "INTERVAL",
            # Complex
            SchemaType.ARRAY: "LIST",
            SchemaType.JSON: "JSON",
            SchemaType.BINARY: "BLOB",
            SchemaType.DECIMAL: "DECIMAL(18,4)",
        }
        return mapping.get(self, "VARCHAR")

    def is_numeric(self) -> bool:
        """Check if this type is numeric (can be used in JAX)."""
        return self in {
            SchemaType.INT8,
            SchemaType.INT16,
            SchemaType.INT32,
            SchemaType.INT64,
            SchemaType.UINT8,
            SchemaType.UINT16,
            SchemaType.UINT32,
            SchemaType.UINT64,
            SchemaType.FLOAT16,
            SchemaType.FLOAT32,
            SchemaType.FLOAT64,
            SchemaType.BOOLEAN,
        }

    def is_temporal(self) -> bool:
        """Check if this type represents time."""
        return self in (
            SchemaType.DATE,
            SchemaType.DATETIME,
            SchemaType.TIMESTAMP_TZ,
            SchemaType.TIME,
            SchemaType.DURATION,
        )

    def is_compatible_with(self, other: "SchemaType") -> bool:
        """
        Check if this type can be safely coerced to another.

        Coercion rules (non-lossy):
        - INT8 -> INT16 -> INT32 -> INT64
        - FLOAT32 -> FLOAT64
        - INT* -> FLOAT64 (precision loss possible but value preserved)
        - DATE -> DATETIME
        """
        if self == other:
            return True

        # Define widening paths
        widening_paths: dict[SchemaType, set[SchemaType]] = {
            SchemaType.INT8: {
                SchemaType.INT16,
                SchemaType.INT32,
                SchemaType.INT64,
                SchemaType.FLOAT32,
                SchemaType.FLOAT64,
            },
            SchemaType.INT16: {
                SchemaType.INT32,
                SchemaType.INT64,
                SchemaType.FLOAT32,
                SchemaType.FLOAT64,
            },
            SchemaType.INT32: {SchemaType.INT64, SchemaType.FLOAT64},
            SchemaType.INT64: {SchemaType.FLOAT64},
            SchemaType.FLOAT16: {SchemaType.FLOAT32, SchemaType.FLOAT64},
            SchemaType.FLOAT32: {SchemaType.FLOAT64},
            SchemaType.DATE: {SchemaType.DATETIME, SchemaType.TIMESTAMP_TZ},
            SchemaType.DATETIME: {SchemaType.TIMESTAMP_TZ},
            SchemaType.UINT8: {
                SchemaType.UINT16,
                SchemaType.UINT32,
                SchemaType.UINT64,
                SchemaType.INT16,
                SchemaType.INT32,
                SchemaType.INT64,
            },
            SchemaType.UINT16: {
                SchemaType.UINT32,
                SchemaType.UINT64,
                SchemaType.INT32,
                SchemaType.INT64,
            },
            SchemaType.UINT32: {SchemaType.UINT64, SchemaType.INT64},
        }

        return other in widening_paths.get(self, set())


class SemanticType(str, Enum):
    """
    Semantic meaning of a field for validation and unit inference.

    Semantic types provide domain-specific meaning that guides:
    - Unit inference (CURRENCY -> money units)
    - Validation rules (PERCENTAGE -> 0-100 range)
    - Display formatting (IDENTIFIER -> no aggregation)
    """

    # Identity
    IDENTIFIER = "identifier"
    CODE = "code"

    # Numeric semantics
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    RATIO = "ratio"
    COUNT = "count"
    RATE = "rate"
    INDEX = "index"

    # Domain-specific
    POPULATION = "population"
    AREA = "area"
    DISTANCE = "distance"
    WEIGHT = "weight"

    # Temporal
    TEMPORAL = "temporal"
    DURATION_SEMANTIC = "duration_semantic"

    # Geospatial
    GEOSPATIAL = "geospatial"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"

    # Text
    NAME = "name"
    DESCRIPTION = "description"

    def get_default_unit(self) -> str | None:
        """Get default unit for this semantic type."""
        defaults = {
            SemanticType.PERCENTAGE: "percent",
            SemanticType.RATIO: "ratio",
            SemanticType.COUNT: "count",
            SemanticType.POPULATION: "persons",
            SemanticType.AREA: "km2",
            SemanticType.DISTANCE: "km",
            SemanticType.LATITUDE: "degrees",
            SemanticType.LONGITUDE: "degrees",
        }
        return defaults.get(self)

    def get_validation_bounds(self) -> tuple[float | None, float | None]:
        """Get typical validation bounds for this semantic type."""
        bounds = {
            SemanticType.PERCENTAGE: (0.0, 100.0),
            SemanticType.RATIO: (0.0, 1.0),
            SemanticType.COUNT: (0.0, None),
            SemanticType.POPULATION: (0.0, None),
            SemanticType.LATITUDE: (-90.0, 90.0),
            SemanticType.LONGITUDE: (-180.0, 180.0),
        }
        return bounds.get(self, (None, None))


class Additivity(str, Enum):
    """
    Additivity semantics for aggregation across dimensions.

    - additive: can sum across time and entities
    - semi_additive: can sum across entities, not time
    - non_additive: should not be summed
    """

    ADDITIVE = "additive"
    SEMI_ADDITIVE = "semi_additive"
    NON_ADDITIVE = "non_additive"

    @property
    def additive_over_time(self) -> bool:
        return self == Additivity.ADDITIVE

    @property
    def additive_over_entities(self) -> bool:
        return self in (Additivity.ADDITIVE, Additivity.SEMI_ADDITIVE)


class TimeGranularity(str, Enum):
    """Temporal granularity of time-series data."""

    SECOND = "second"
    MINUTE = "minute"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    FISCAL_YEAR = "fiscal_year"

    def to_pandas_freq(self) -> str:
        """Convert to pandas frequency string."""
        mapping = {
            TimeGranularity.SECOND: "s",
            TimeGranularity.MINUTE: "min",
            TimeGranularity.HOURLY: "h",
            TimeGranularity.DAILY: "D",
            TimeGranularity.WEEKLY: "W",
            TimeGranularity.MONTHLY: "MS",
            TimeGranularity.QUARTERLY: "QS",
            TimeGranularity.ANNUAL: "YS",
            TimeGranularity.FISCAL_YEAR: "YS",  # Customize with fiscal_year_start
        }
        return mapping[self]

    @property
    def approximate_days(self) -> float | None:
        """Approximate day length for comparison."""
        day_mapping = {
            TimeGranularity.SECOND: 1 / 86400,
            TimeGranularity.MINUTE: 1 / 1440,
            TimeGranularity.HOURLY: 1 / 24,
            TimeGranularity.DAILY: 1,
            TimeGranularity.WEEKLY: 7,
            TimeGranularity.MONTHLY: 30.44,
            TimeGranularity.QUARTERLY: 91.31,
            TimeGranularity.ANNUAL: 365.25,
            TimeGranularity.FISCAL_YEAR: 365.25,
        }
        return day_mapping.get(self)

    def is_finer_than(self, other: "TimeGranularity") -> bool:
        """Check if this granularity is finer (higher frequency) than another."""
        self_days = self.approximate_days
        other_days = other.approximate_days
        if self_days is None or other_days is None:
            return False
        return self_days < other_days

    def is_coarser_than(self, other: "TimeGranularity") -> bool:
        """Check if this granularity is coarser (lower frequency) than another."""
        self_days = self.approximate_days
        other_days = other.approximate_days
        if self_days is None or other_days is None:
            return False
        return self_days > other_days


class GeoGranularity(str, Enum):
    """Geographic granularity (Ukraine-specific + generic)."""

    # Generic
    GLOBAL = "global"
    COUNTRY = "country"
    REGION = "region"
    CITY = "city"
    POSTAL = "postal"

    # Ukraine-specific (KOATUU hierarchy)
    OBLAST = "oblast"
    RAION = "raion"
    HROMADA = "hromada"
    SETTLEMENT = "settlement"

    def hierarchy_level(self) -> int:
        """Get hierarchy level (lower = coarser)."""
        levels = {
            GeoGranularity.GLOBAL: 0,
            GeoGranularity.COUNTRY: 1,
            GeoGranularity.REGION: 2,
            GeoGranularity.OBLAST: 2,
            GeoGranularity.RAION: 3,
            GeoGranularity.CITY: 3,
            GeoGranularity.HROMADA: 4,
            GeoGranularity.POSTAL: 4,
            GeoGranularity.SETTLEMENT: 5,
        }
        return levels.get(self, 99)


# =============================================================================
# Version Management
# =============================================================================


@dataclass(frozen=True, slots=True, order=True)
class SchemaVersion:
    """
    Semantic versioning for schemas.

    Version rules:
    - MAJOR: Breaking changes (field removal, type narrowing)
    - MINOR: Backward-compatible additions (new fields, type widening)
    - PATCH: Documentation, metadata changes
    """

    major: int
    minor: int
    patch: int = 0

    def __post_init__(self) -> None:
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Version components must be non-negative")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def parse(cls, version_str: str) -> "SchemaVersion":
        """Parse version string like '1.2.3' or '1.2'."""
        match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?$", version_str)
        if not match:
            raise ValueError(f"Invalid version format: {version_str}")
        patch = int(match.group(3)) if match.group(3) is not None else 0
        return cls(int(match.group(1)), int(match.group(2)), patch)

    def is_compatible_with(self, other: "SchemaVersion") -> bool:
        """
        Check backward compatibility (same major version).

        A schema at version 1.2.3 is compatible with 1.0.0 but not 2.0.0.
        """
        return self.major == other.major

    def bump_major(self) -> "SchemaVersion":
        """Create new version with major bump."""
        return SchemaVersion(self.major + 1, 0, 0)

    def bump_minor(self) -> "SchemaVersion":
        """Create new version with minor bump."""
        return SchemaVersion(self.major, self.minor + 1, 0)

    def bump_patch(self) -> "SchemaVersion":
        """Create new version with patch bump."""
        return SchemaVersion(self.major, self.minor, self.patch + 1)


# =============================================================================
# Field Specification
# =============================================================================


# Pattern for valid field names (snake_case)
FIELD_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"


def _normalize_unit_id(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("/", "_per_")
    value = value.replace(" ", "_")
    value = re.sub(r"[^a-z0-9_.-]", "_", value)
    value = re.sub(r"_+", "_", value)
    return value


class FieldSpec(BaseModel):
    """
    Specification for a single data field (column).

    Captures both technical type information and semantic meaning,
    enabling:
    - Cross-platform type mapping
    - Validation rule generation
    - Unit-aware calculations
    - Documentation generation
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Identity
    name: str = Field(
        ...,
        pattern=FIELD_NAME_PATTERN,
        description="Field name in snake_case format",
    )

    # Type information
    data_type: SchemaType = Field(..., description="Canonical data type")
    element_type: SchemaType | None = Field(
        default=None,
        description="Element type for ARRAY fields",
    )

    # Units & semantics (integrates with ir/kernel/units.py)
    unit: UnitRef | None = Field(
        default=None,
        description="Unit reference (uses UnitRef identifiers)",
    )
    display_unit: str | None = Field(
        default=None,
        max_length=64,
        description="Optional display unit label (UI only)",
    )
    semantic_type: SemanticType | None = Field(
        default=None,
        description="Semantic meaning for validation and inference",
    )
    additivity: Additivity | None = Field(
        default=None,
        description="Additivity semantics for aggregation (additive/semi/non)",
    )

    # Constraints
    nullable: bool = Field(default=True, description="Whether NULL values are allowed")
    bounds: tuple[float | None, float | None] = Field(
        default=(None, None),
        description="Min/max bounds for numeric fields",
    )
    allowed_values: frozenset[str] | None = Field(
        default=None,
        description="Allowed values for CATEGORY fields",
    )
    pattern: str | None = Field(
        default=None,
        max_length=256,
        description="Regex pattern for STRING validation",
    )
    max_length: int | None = Field(
        default=None,
        ge=1,
        description="Maximum length for STRING/BINARY fields",
    )

    # Decimal precision (for DECIMAL type)
    precision: int | None = Field(default=None, ge=1, le=38)
    scale: int | None = Field(default=None, ge=0, le=38)

    # Documentation
    description: str = Field(default="", max_length=1024)
    source_name: str = Field(
        default="",
        max_length=256,
        description="Original name in source before normalization",
    )

    # Quality expectations
    expected_completeness: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Expected proportion of non-null values",
    )

    # Metadata
    tags: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("unit", mode="before")
    @classmethod
    def _coerce_unit(cls, v: UnitRef | str | None) -> UnitRef | None:
        if v is None or isinstance(v, UnitRef):
            return v
        if isinstance(v, Mapping):
            return UnitRef.model_validate(v)
        if isinstance(v, str):
            unit_id = _normalize_unit_id(v)
            if not unit_id:
                return None
            return UnitRef(unit_id=unit_id)
        raise TypeError("unit must be UnitRef or str")

    @model_validator(mode="after")
    def validate_element_type(self) -> "FieldSpec":
        """Validate element_type is set for ARRAY fields."""
        if self.data_type == SchemaType.ARRAY and self.element_type is None:
            raise ValueError("element_type is required for ARRAY fields")
        if self.data_type != SchemaType.ARRAY and self.element_type is not None:
            raise ValueError("element_type should only be set for ARRAY fields")
        return self

    @model_validator(mode="after")
    def validate_decimal_precision(self) -> "FieldSpec":
        """Validate decimal precision/scale."""
        if self.data_type != SchemaType.DECIMAL:
            return self

        precision = self.precision
        scale = self.scale

        if precision is None:
            precision = 18
            scale = 4 if scale is None else scale
        elif scale is None:
            scale = 0

        if scale is not None and precision is not None and scale > precision:
            raise ValueError("scale cannot exceed precision")

        if precision != self.precision or scale != self.scale:
            return self.model_copy(update={"precision": precision, "scale": scale})

        return self

    @field_validator("bounds", mode="after")
    @classmethod
    def validate_bounds(
        cls, v: tuple[float | None, float | None]
    ) -> tuple[float | None, float | None]:
        """Ensure min <= max."""
        min_val, max_val = v
        if min_val is not None and max_val is not None and min_val > max_val:
            raise ValueError(f"bounds min ({min_val}) must be <= max ({max_val})")
        return v

    def is_compatible_with(self, other: "FieldSpec") -> bool:
        """
        Check if this field can be merged/compared with another.

        Compatibility rules:
        1. Semantic types must match (if both specified)
        2. Data types must be coercible
        3. Units must match if both specified
        """
        if self.semantic_type and other.semantic_type:
            if self.semantic_type != other.semantic_type:
                return False

        if self.additivity and other.additivity:
            if self.additivity != other.additivity:
                return False

        if self.unit and other.unit:
            if self.unit.unit_id != other.unit.unit_id:
                return False

        if not self.data_type.is_compatible_with(other.data_type):
            if not other.data_type.is_compatible_with(self.data_type):
                return False

        return True

    def widen_to(self, other: "FieldSpec") -> "FieldSpec":
        """
        Create a widened field spec that accommodates both fields.

        Used in schema evolution to create compatible merged schemas.
        """
        if self.unit and other.unit and self.unit.unit_id != other.unit.unit_id:
            raise ValueError(
                f"Cannot widen fields with conflicting units: {self.unit} vs {other.unit}"
            )

        if self.semantic_type and other.semantic_type:
            if self.semantic_type != other.semantic_type:
                raise ValueError(
                    "Cannot widen fields with conflicting semantic types: "
                    f"{self.semantic_type} vs {other.semantic_type}"
                )

        if self.additivity and other.additivity:
            if self.additivity != other.additivity:
                raise ValueError(
                    "Cannot widen fields with conflicting additivity: "
                    f"{self.additivity} vs {other.additivity}"
                )

        if self.data_type.is_compatible_with(other.data_type):
            widened_type = other.data_type
        elif other.data_type.is_compatible_with(self.data_type):
            widened_type = self.data_type
        else:
            raise ValueError(f"Cannot widen {self.data_type} and {other.data_type}")

        min_bound = None
        max_bound = None
        if self.bounds[0] is not None or other.bounds[0] is not None:
            vals = [v for v in [self.bounds[0], other.bounds[0]] if v is not None]
            min_bound = min(vals) if vals else None
        if self.bounds[1] is not None or other.bounds[1] is not None:
            vals = [v for v in [self.bounds[1], other.bounds[1]] if v is not None]
            max_bound = max(vals) if vals else None

        merged_allowed = None
        if self.allowed_values or other.allowed_values:
            a = self.allowed_values or frozenset()
            b = other.allowed_values or frozenset()
            merged_allowed = a | b if (a and b) else None

        return FieldSpec(
            name=self.name,
            data_type=widened_type,
            element_type=self.element_type or other.element_type,
            unit=self.unit or other.unit,
            display_unit=self.display_unit or other.display_unit,
            semantic_type=self.semantic_type or other.semantic_type,
            additivity=self.additivity or other.additivity,
            nullable=self.nullable or other.nullable,
            bounds=(min_bound, max_bound),
            allowed_values=merged_allowed,
            pattern=self.pattern if self.pattern == other.pattern else None,
            max_length=self.max_length if self.max_length == other.max_length else None,
            precision=self.precision if self.precision == other.precision else None,
            scale=self.scale if self.scale == other.scale else None,
            description=self.description or other.description,
            source_name=self.source_name or other.source_name,
            expected_completeness=min(self.expected_completeness, other.expected_completeness),
            tags=self.tags | other.tags,
        )

    def to_duckdb_column_def(self) -> str:
        """Generate DuckDB column definition."""
        type_str = self.data_type.to_duckdb_type()

        if self.data_type == SchemaType.DECIMAL and self.precision:
            type_str = f"DECIMAL({self.precision},{self.scale or 0})"

        if self.data_type == SchemaType.ARRAY and self.element_type:
            type_str = f"{self.element_type.to_duckdb_type()}[]"

        null_str = "" if self.nullable else " NOT NULL"
        return f"{self.name} {type_str}{null_str}"


# =============================================================================
# Data Schema
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
    return sorted(list(values))


def _unit_id(unit: UnitRef | None) -> str | None:
    return unit.unit_id if unit else None


def _field_hash_payload(field: FieldSpec) -> dict[str, Any]:
    return {
        "name": field.name,
        "data_type": field.data_type.value,
        "element_type": field.element_type.value if field.element_type else None,
        "unit": _unit_id(field.unit),
        "display_unit": field.display_unit,
        "semantic_type": field.semantic_type.value if field.semantic_type else None,
        "additivity": field.additivity.value if field.additivity else None,
        "nullable": field.nullable,
        "bounds": [_number_token(field.bounds[0]), _number_token(field.bounds[1])],
        "allowed_values": _sorted_list(field.allowed_values) if field.allowed_values else None,
        "pattern": field.pattern,
        "max_length": field.max_length,
        "precision": field.precision,
        "scale": field.scale,
        "expected_completeness": _float_token(field.expected_completeness),
        "tags": _sorted_list(field.tags),
    }


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
        pattern=r"^[a-z][a-z0-9_.]*$",
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

    @model_validator(mode="after")
    def validate_field_references(self) -> "DataSchema":
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
    def validate_unique_field_names(self) -> "DataSchema":
        """Ensure field names are unique."""
        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate field names: {set(duplicates)}")
        return self

    def get_field(self, name: str) -> FieldSpec | None:
        """Get field by name."""
        return next((f for f in self.fields if f.name == name), None)

    def field_names(self) -> list[str]:
        """Get ordered list of field names."""
        return [f.name for f in self.fields]

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
            pk_clause = f", PRIMARY KEY ({', '.join(self.primary_key)})"
        return f"({', '.join(columns)}{pk_clause})"

    def to_duckdb_create_table(self, table_name: str) -> str:
        """Generate full DuckDB CREATE TABLE statement."""
        return f"CREATE TABLE {table_name} {self.to_duckdb_schema()}"

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
        return f"sha256:{hashlib.sha256(canonical).hexdigest()}"

    @property
    def identity_key(self) -> tuple[str, str, str]:
        """Stable identity tuple combining ID, version, and content hash."""
        return (self.schema_id, str(self.version), self.content_hash)

    def select_fields(self, names: Sequence[str]) -> "DataSchema":
        """Create a new schema with only the specified fields."""
        selected = tuple(f for f in self.fields if f.name in names)
        if not selected:
            raise ValueError("No matching fields found")

        selected_names = {f.name for f in selected}
        new_pk = tuple(pk for pk in self.primary_key if pk in selected_names)
        new_time = self.time_dimension if self.time_dimension in selected_names else None
        new_geo = self.geo_dimension if self.geo_dimension in selected_names else None

        return DataSchema(
            schema_id=f"{self.schema_id}.selected",
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

    def add_field(self, field: FieldSpec) -> "DataSchema":
        """Create a new schema with an additional field."""
        if any(f.name == field.name for f in self.fields):
            raise ValueError(f"Field '{field.name}' already exists")

        return DataSchema(
            schema_id=self.schema_id,
            version=self.version.bump_minor(),
            fields=self.fields + (field,),
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


# =============================================================================
# Type Coercion Errors
# =============================================================================


class SchemaError(Exception):
    """Base exception for schema errors."""


class TypeCoercionError(SchemaError):
    """Raised when type coercion fails."""

    def __init__(
        self,
        source_type: SchemaType,
        target_type: SchemaType,
        field_name: str | None = None,
    ) -> None:
        self.source_type = source_type
        self.target_type = target_type
        self.field_name = field_name

        msg = f"Cannot coerce {source_type.value} to {target_type.value}"
        if field_name:
            msg = f"Field '{field_name}': {msg}"
        super().__init__(msg)


class JaxTypeError(SchemaError):
    """Raised when a type cannot be used in JAX."""

    def __init__(self, data_type: SchemaType, field_name: str | None = None) -> None:
        self.data_type = data_type
        self.field_name = field_name

        msg = f"Type {data_type.value} cannot be used in JAX arrays"
        if field_name:
            msg = f"Field '{field_name}': {msg}"
        super().__init__(msg)


class SchemaCompatibilityError(SchemaError):
    """Raised when schemas are incompatible."""

    def __init__(self, source_schema: str, target_schema: str, reason: str) -> None:
        self.source_schema = source_schema
        self.target_schema = target_schema
        self.reason = reason
        super().__init__(f"Schema '{source_schema}' incompatible with '{target_schema}': {reason}")
