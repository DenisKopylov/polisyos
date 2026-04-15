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
from polisyos.fabric.connectors.contracts.contract import (
    ConnectorSchemaContract,
    FieldMapping,
)
from polisyos.fabric.connectors.contracts.contract_registry import (
    ContractGovernanceError,
    ContractNotFoundError,
    ContractRegistry,
    ContractVersionError,
    ContractViolationError,
    build_contract_registry,
)
from polisyos.fabric.connectors.contracts.evolution import (
    ChangeType,
    EvolutionReport,
    MigrationOperation,
    MigrationPlan,
    SchemaChange,
    SchemaEvolution,
)
from polisyos.fabric.connectors.contracts.governance import (
    MigrationStatus,
    SchemaApprovalMetadata,
    SchemaRiskLevel,
)
from polisyos.fabric.connectors.contracts.governance_checks import (
    ContractGovernanceEvaluation,
    actual_version_bump,
    evaluate_contract_governance,
    format_impacted_surfaces,
    impacted_downstream_surfaces,
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
from polisyos.fabric.connectors.contracts.registry import (
    FileBackedSchemaRegistry,
    SchemaNotFoundError,
    SchemaRegistration,
    SchemaRegistry,
    SchemaVersionConflictError,
)
from polisyos.fabric.connectors.contracts.schema import (
    Additivity,
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
from polisyos.fabric.connectors.contracts.validation_middleware import (
    ContractValidatingProxy,
    SchemaValidationMode,
)

__all__ = [
    # Schema core
    "DataSchema",
    "SchemaType",
    "FieldSpec",
    "Additivity",
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
    "MigrationOperation",
    "MigrationPlan",
    "SchemaChange",
    "SchemaEvolution",
    "SchemaApprovalMetadata",
    "SchemaRiskLevel",
    "MigrationStatus",
    # Connector-level contracts
    "FieldMapping",
    "ConnectorSchemaContract",
    "ContractRegistry",
    "ContractGovernanceError",
    "ContractNotFoundError",
    "ContractVersionError",
    "ContractViolationError",
    "build_contract_registry",
    "ContractGovernanceEvaluation",
    "actual_version_bump",
    "evaluate_contract_governance",
    "format_impacted_surfaces",
    "impacted_downstream_surfaces",
    "ContractValidatingProxy",
    "SchemaValidationMode",
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
