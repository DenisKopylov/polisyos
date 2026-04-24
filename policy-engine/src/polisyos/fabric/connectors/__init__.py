"""Data Fabric Connectors - Protocol Foundation & Registry Architecture."""

# IR-level contracts
# Protocol and core types
from polisyos.fabric.connectors.base import (
    AsyncFetchLease,
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    DatasetCapabilitySnapshot,
    FetchRequest,
    FetchResult,
    HealthStatus,
    SourceConnector,
)

# Caching layer (Phase 2.7)
from polisyos.fabric.connectors.cache import (
    CachedFetchResult,
    CacheMetadata,
    CachePolicy,
    CacheStats,
    CachingConnectorProxy,
    ConnectorCacheStore,
    InvalidationEvent,
    InvalidationOrchestrator,
    InvalidationStrategy,
    InvalidationTrigger,
    LRUPolicy,
    PolicyRegistry,
    PrefetchJob,
    PrefetchScheduler,
    SchemaChangeInvalidationTrigger,
    SizeBoundedPolicy,
    SmartExpiryPolicy,
    StaticDataPolicy,
    TTLPolicy,
    VolatileDataPolicy,
    make_schema_hash_provider,
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

# Discovery System (Phase 2.2)
from polisyos.fabric.connectors.discovery import (
    ConnectorDiscovery,
    DiscoveryError,
    DiscoveryResult,
    discover_connectors,
    discover_connectors_from_modules,
    get_discovery_errors,
)
from polisyos.fabric.connectors.family_contracts import (
    API_PROTOCOL_CONNECTOR_CONTRACT,
    CONNECTOR_FAMILY_CONTRACTS,
    DATABASE_CONNECTOR_CONTRACT,
    FILE_CONNECTOR_CONTRACT,
    OBJECT_STORAGE_CONNECTOR_CONTRACT,
    SPATIAL_CONNECTOR_CONTRACT,
    STREAM_CONNECTOR_CONTRACT,
    ConnectorFamilyContract,
    contract_for_family,
)

# Connection Pooling (Phase 2.2)
from polisyos.fabric.connectors.pool import (
    ConnectionPool,
    PoolClosedError,
    PoolConfig,
    PooledConnection,
    PoolExhaustedError,
    PoolStats,
)

# Registry Architecture (Phase 2.2)
from polisyos.fabric.connectors.registry import (
    AmbiguousConnectorError,
    ConnectorAlreadyRegisteredError,
    ConnectorConfigError,
    ConnectorEntry,
    ConnectorNotFoundError,
    ConnectorPreferences,
    ConnectorRegistry,
    RegistryError,
    RegistryMetrics,
    RegistryStats,
)

# Resilience layer (Phase 2.9)
from polisyos.fabric.connectors.resilience import (
    AdaptiveRateLimiter,
    CacheFallback,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
    CircuitState,
    FallbackChain,
    FallbackStrategy,
    MockFallback,
    RaiseFallback,
    RateLimiter,
    RateLimiterConfig,
    ResilienceConfig,
    RetryExhaustedError,
    RetryPolicy,
    apply_resilience,
    is_retryable_error,
    resolve_resilience_config,
    with_circuit_breaker,
    with_fallback,
    with_rate_limit,
    with_retry,
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

# Validation helpers (schema coercion)
from polisyos.fabric.connectors.validation import (
    coerce_fetch_result_against_schema,
    validate_fetch_result_against_schema,
)
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

__all__ = [
    "API_PROTOCOL_CONNECTOR_CONTRACT",
    "CAPABILITY_METHOD_REQUIREMENTS",
    "CONNECTOR_FAMILY_CONTRACTS",
    "DATABASE_CONNECTOR_CONTRACT",
    "FILE_CONNECTOR_CONTRACT",
    "OBJECT_STORAGE_CONNECTOR_CONTRACT",
    "REQUIRED_ATTRIBUTES",
    "REQUIRED_METHODS",
    "SPATIAL_CONNECTOR_CONTRACT",
    "STREAM_CONNECTOR_CONTRACT",
    "AdaptiveRateLimiter",
    "AmbiguousConnectorError",
    "AsyncFetchLease",
    "BaseConnector",
    "CacheFallback",
    "CacheMetadata",
    "CachePolicy",
    "CacheStats",
    "CachedFetchResult",
    "CachingConnectorProxy",
    "CapabilityError",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitOpenError",
    "CircuitState",
    "ConfigurationError",
    "ConnectionConfig",
    "ConnectionError",
    "ConnectionHandle",
    # === Connection Pooling (Phase 2.2) ===
    "ConnectionPool",
    "ConnectorAlreadyRegisteredError",
    # === Caching Layer (Phase 2.7) ===
    "ConnectorCacheStore",
    # === IR Contracts ===
    "ConnectorCapability",
    "ConnectorConfigError",
    # === Discovery System (Phase 2.2) ===
    "ConnectorDiscovery",
    "ConnectorEntry",
    # === Error Types ===
    "ConnectorError",
    # === Family contracts (WS-5B) ===
    "ConnectorFamilyContract",
    "ConnectorMetadataSpec",
    "ConnectorNotFoundError",
    "ConnectorPreferences",
    # === Registry Architecture (Phase 2.2) ===
    "ConnectorRegistry",
    # === Supporting Types ===
    "DataChunk",
    "DataVersion",
    "DatasetCapabilitySnapshot",
    "DatasetDescriptor",
    "DiscoveryError",
    "DiscoveryResult",
    "FallbackChain",
    "FallbackStrategy",
    "FetchError",
    "FetchRequest",
    "FetchResult",
    "FreshnessResult",
    "FreshnessStatus",
    "HealthStatus",
    "InvalidationEvent",
    "InvalidationOrchestrator",
    "InvalidationStrategy",
    "InvalidationTrigger",
    "LRUPolicy",
    "MockFallback",
    "PolicyRegistry",
    "PoolClosedError",
    "PoolConfig",
    "PoolExhaustedError",
    "PoolStats",
    "PooledConnection",
    "PrefetchJob",
    "PrefetchScheduler",
    "QualityTier",
    "RaiseFallback",
    "RateLimitError",
    "RateLimitStatus",
    "RateLimiter",
    "RateLimiterConfig",
    "RegistryError",
    "RegistryMetrics",
    "RegistryStats",
    "ResilienceConfig",
    "RetryExhaustedError",
    # === Resilience Layer (Phase 2.9) ===
    "RetryPolicy",
    "SchemaChangeInvalidationTrigger",
    "SchemaError",
    "SizeBoundedPolicy",
    "SmartExpiryPolicy",
    # === Protocol & Core Types ===
    "SourceConnector",
    "StaticDataPolicy",
    "TTLPolicy",
    "TrustLevel",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    "VersionStrategy",
    "VolatileDataPolicy",
    "apply_resilience",
    "capabilities_from_flags",
    "capabilities_summary",
    "check_capability_at_runtime",
    "coerce_fetch_result_against_schema",
    "contract_for_family",
    "describe_capabilities",
    "discover_connectors",
    "discover_connectors_from_modules",
    "flags_from_capabilities",
    "get_discovery_errors",
    "get_missing_capabilities",
    "get_registry",
    "is_retryable_error",
    "make_schema_hash_provider",
    "requires_any_capability",
    # === Capability Utilities ===
    "requires_capability",
    "resolve_resilience_config",
    # === Validation Helpers ===
    "validate_fetch_result_against_schema",
    "validate_protocol_compliance",
    "with_circuit_breaker",
    "with_fallback",
    "with_rate_limit",
    "with_retry",
]

__version__ = "2.2.0"
__phase__ = "Phase 2.2: Registry Architecture & Lazy Loading"


def _default_connector_registry() -> ConnectorRegistry:
    return ConnectorRegistry.get_instance()


def get_registry() -> ConnectorRegistry:
    """
    Convenience function to get the ConnectorRegistry singleton.

    Usage:
        from polisyos.fabric.connectors import get_registry

        registry = get_registry()
        connector = registry.get("world_bank")
    """
    return _default_connector_registry()
