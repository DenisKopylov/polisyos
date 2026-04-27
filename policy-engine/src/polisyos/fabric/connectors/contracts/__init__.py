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
    make_field_id,
    make_schema_id,
    normalize_schema_id_part,
)
from polisyos.fabric.connectors.contracts.source_contract import (
    SOURCE_CONTRACT_SCHEMA_VERSION,
    SourceContract,
    SourceContractDocs,
    SourceContractLineage,
    SourceContractQuality,
    SourceContractReplay,
    SourceContractRetention,
    SourceContractSLA,
    SourceContractSchema,
    SourceContractSecurity,
    SourceContractSemantics,
    SourceContractSource,
    SourceContractTerms,
    SourceContractTrust,
    SourceDeprecationPolicy,
    SourceMetricDefinition,
    load_source_contracts,
    source_contracts_compatibility_evidence,
    source_contracts_snapshot_payload,
)
from polisyos.fabric.connectors.contracts.validation_middleware import (
    ContractValidatingProxy,
    SchemaValidationMode,
)

__all__ = [
    "Additivity",
    # Evolution
    "ChangeType",
    "CoercionResult",
    "ConnectorSchemaContract",
    "ContractGovernanceError",
    "ContractGovernanceEvaluation",
    "ContractNotFoundError",
    "ContractRegistry",
    "ContractValidatingProxy",
    "ContractVersionError",
    "ContractViolationError",
    # Schema core
    "DataSchema",
    "EvolutionReport",
    # Connector-level contracts
    "FieldMapping",
    "FieldSpec",
    # Registry
    "FileBackedSchemaRegistry",
    "GeoGranularity",
    # Inference
    "InferenceConfig",
    "InferenceResult",
    # Errors
    "JaxTypeError",
    "MigrationOperation",
    "MigrationPlan",
    "MigrationStatus",
    "SchemaApprovalMetadata",
    "SchemaChange",
    "SchemaCompatibilityError",
    "SchemaError",
    "SchemaEvolution",
    "SchemaHints",
    "SchemaInference",
    "SchemaNotFoundError",
    "SchemaRegistration",
    "SchemaRegistry",
    "SchemaRiskLevel",
    "SchemaType",
    "SchemaValidationMode",
    "SchemaVersion",
    "SchemaVersionConflictError",
    "SemanticType",
    "SOURCE_CONTRACT_SCHEMA_VERSION",
    "SourceContract",
    "SourceContractDocs",
    "SourceContractLineage",
    "SourceContractQuality",
    "SourceContractReplay",
    "SourceContractRetention",
    "SourceContractSLA",
    "SourceContractSchema",
    "SourceContractSecurity",
    "SourceContractSemantics",
    "SourceContractSource",
    "SourceContractTerms",
    "SourceContractTrust",
    "SourceDeprecationPolicy",
    "SourceMetricDefinition",
    "TimeGranularity",
    "TypeCoercionError",
    "actual_version_bump",
    "build_contract_registry",
    "coerce_dataframe_to_schema",
    "evaluate_contract_governance",
    "format_impacted_surfaces",
    "impacted_downstream_surfaces",
    "infer_schema",
    "load_source_contracts",
    "make_field_id",
    "make_schema_id",
    "normalize_schema_id_part",
    "source_contracts_compatibility_evidence",
    "source_contracts_snapshot_payload",
    "validate_dataframe_against_schema",
]
