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
    SCHEMA_ID_PATTERN,
    FieldSpec,
    SchemaVersion,
    make_field_id,
    make_schema_id,
    normalize_schema_id_part,
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
    "FIELD_NAME_PATTERN",
    "SCHEMA_ID_PATTERN",
    "Additivity",
    "DataSchema",
    "FieldSpec",
    "GeoGranularity",
    "JaxTypeError",
    "SchemaCompatibilityError",
    "SchemaError",
    "SchemaType",
    "SchemaVersion",
    "SemanticType",
    "TimeGranularity",
    "TypeCoercionError",
    "make_field_id",
    "make_schema_id",
    "normalize_schema_id_part",
    "normalize_unit_id",
]
