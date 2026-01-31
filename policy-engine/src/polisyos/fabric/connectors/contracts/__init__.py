"""
Data schema and contract system for connector data validation.

This module provides the type system that bridges:
- Pandas DataFrames (data engineering)
- DuckDB storage (analytical queries)
- JAX arrays (scientific computing)

Key Components:
- DataSchema: Immutable dataset schema with CAS-compatible hashing
- FieldSpec: Column-level specifications with semantic types
- SchemaInference: Automatic schema inference from data samples
- SchemaEvolution: Change detection and compatibility checking
- SchemaRegistry: Schema storage and version management
"""
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    GeoGranularity,
    JaxTypeError,
    SchemaCompatibilityError,
    SchemaError,
    SchemaType,
    SchemaVersion,
    SemanticType,
    TimeGranularity,
    TypeCoercionError,
)
from polisyos.fabric.connectors.contracts.inference import (
    CoercionResult,
    InferenceConfig,
    InferenceResult,
    SchemaHints,
    SchemaInference,
    coerce_dataframe_to_schema,
    infer_schema,
    validate_dataframe_against_schema,
)
from polisyos.fabric.connectors.contracts.evolution import (
    ChangeType,
    EvolutionReport,
    SchemaChange,
    SchemaEvolution,
)
from polisyos.fabric.connectors.contracts.registry import (
    FileBackedSchemaRegistry,
    SchemaNotFoundError,
    SchemaRegistration,
    SchemaRegistry,
    SchemaVersionConflictError,
)

__all__ = [
    # Schema core
    "DataSchema",
    "SchemaType",
    "FieldSpec",
    "SchemaVersion",
    "SemanticType",
    "TimeGranularity",
    "GeoGranularity",
    # Inference
    "InferenceConfig",
    "InferenceResult",
    "SchemaHints",
    "SchemaInference",
    "infer_schema",
    "validate_dataframe_against_schema",
    "coerce_dataframe_to_schema",
    "CoercionResult",
    # Evolution
    "ChangeType",
    "EvolutionReport",
    "SchemaChange",
    "SchemaEvolution",
    # Registry
    "FileBackedSchemaRegistry",
    "SchemaNotFoundError",
    "SchemaRegistration",
    "SchemaRegistry",
    "SchemaVersionConflictError",
    # Errors
    "JaxTypeError",
    "SchemaCompatibilityError",
    "SchemaError",
    "TypeCoercionError",
]
