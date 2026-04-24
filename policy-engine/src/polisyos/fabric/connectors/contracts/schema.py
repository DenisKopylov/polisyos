"""
Data schema definitions for connector data contracts.

This module provides the canonical type system that bridges:
- Pandas DataFrames (data engineering)
- DuckDB storage (analytical queries)
- JAX arrays (scientific computing)

Public API is assembled from private sub-modules:
- _schema_errors:  exception hierarchy
- _schema_types:   SchemaType, SemanticType, Additivity, TimeGranularity, GeoGranularity
- _schema_field:   SchemaVersion, FieldSpec, FIELD_NAME_PATTERN
- _schema_core:    DataSchema
"""

from polisyos.fabric.connectors.contracts._schema_core import DataSchema
from polisyos.fabric.connectors.contracts._schema_errors import (
    JaxTypeError,
    SchemaCompatibilityError,
    SchemaError,
    TypeCoercionError,
)
from polisyos.fabric.connectors.contracts._schema_field import (
    FIELD_NAME_PATTERN,
    FieldSpec,
    SchemaVersion,
    normalize_unit_id,
)
from polisyos.fabric.connectors.contracts._schema_types import (
    Additivity,
    GeoGranularity,
    SchemaType,
    SemanticType,
    TimeGranularity,
)

__all__ = [
    # Versioning & field spec
    "FIELD_NAME_PATTERN",
    # Types / enums
    "Additivity",
    # Core schema
    "DataSchema",
    "FieldSpec",
    "GeoGranularity",
    # Errors
    "JaxTypeError",
    "SchemaCompatibilityError",
    "SchemaError",
    "SchemaType",
    "SchemaVersion",
    "SemanticType",
    "TimeGranularity",
    "TypeCoercionError",
    "normalize_unit_id",
]
