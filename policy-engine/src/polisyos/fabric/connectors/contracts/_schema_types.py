"""
Canonical type enums for the data schema system.

Provides:
- SchemaType: canonical data types with multi-backend mapping
- SemanticType: domain-specific field meaning
- Additivity: aggregation semantics
- TimeGranularity: temporal resolution
- GeoGranularity: geographic resolution
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from ._schema_errors import JaxTypeError

if TYPE_CHECKING:
    import jax.numpy as jnp

__all__ = [
    "Additivity",
    "GeoGranularity",
    "SchemaType",
    "SemanticType",
    "TimeGranularity",
]


# ---- SchemaType -------------------------------------------------------------


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

    def to_jax_dtype(self, *, strict: bool = False) -> jnp.dtype | None:
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

    def is_compatible_with(self, other: SchemaType) -> bool:
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


# ---- SemanticType ------------------------------------------------------------


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


# ---- Additivity --------------------------------------------------------------


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


# ---- TimeGranularity ---------------------------------------------------------


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

    def is_finer_than(self, other: TimeGranularity) -> bool:
        """Check if this granularity is finer (higher frequency) than another."""
        self_days = self.approximate_days
        other_days = other.approximate_days
        if self_days is None or other_days is None:
            return False
        return self_days < other_days

    def is_coarser_than(self, other: TimeGranularity) -> bool:
        """Check if this granularity is coarser (lower frequency) than another."""
        self_days = self.approximate_days
        other_days = other.approximate_days
        if self_days is None or other_days is None:
            return False
        return self_days > other_days


# ---- GeoGranularity ----------------------------------------------------------


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
