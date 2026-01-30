"""Data Fabric Connectors - Protocol Foundation & Capability System."""

# IR-level contracts
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
    flags_from_capabilities,
)

# Protocol and core types
from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
    SourceConnector,
)

# Error types and supporting structures
from polisyos.fabric.connectors.types import (
    CapabilityError,
    ConfigurationError,
    ConnectionError,
    ConnectorError,
    DataChunk,
    DatasetDescriptor,
    FetchError,
    FreshnessResult,
    FreshnessStatus,
    RateLimitError,
    RateLimitStatus,
    SchemaError,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)

# Capability utilities
from polisyos.fabric.connectors.capabilities import (
    CAPABILITY_METHOD_REQUIREMENTS,
    REQUIRED_ATTRIBUTES,
    REQUIRED_METHODS,
    capabilities_summary,
    check_capability_at_runtime,
    describe_capabilities,
    get_missing_capabilities,
    requires_any_capability,
    requires_capability,
    validate_protocol_compliance,
)

__all__ = [
    # === IR Contracts ===
    "ConnectorCapability",
    "ConnectorMetadataSpec",
    "DataVersion",
    "QualityTier",
    "TrustLevel",
    "VersionStrategy",
    "capabilities_from_flags",
    "flags_from_capabilities",
    # === Protocol & Core Types ===
    "SourceConnector",
    "BaseConnector",
    "ConnectionConfig",
    "ConnectionHandle",
    "FetchRequest",
    "FetchResult",
    "HealthStatus",
    # === Error Types ===
    "ConnectorError",
    "CapabilityError",
    "ConfigurationError",
    "ConnectionError",
    "FetchError",
    "RateLimitError",
    "SchemaError",
    # === Supporting Types ===
    "DataChunk",
    "DatasetDescriptor",
    "FreshnessResult",
    "FreshnessStatus",
    "RateLimitStatus",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    # === Capability Utilities ===
    "requires_capability",
    "requires_any_capability",
    "validate_protocol_compliance",
    "check_capability_at_runtime",
    "get_missing_capabilities",
    "describe_capabilities",
    "capabilities_summary",
    "CAPABILITY_METHOD_REQUIREMENTS",
    "REQUIRED_METHODS",
    "REQUIRED_ATTRIBUTES",
]

__version__ = "2.1.0"
__phase__ = "Phase 2.1: Protocol Foundation & Capability System"
