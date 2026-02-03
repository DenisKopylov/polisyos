"""Data Fabric Connectors - Protocol Foundation & Registry Architecture."""

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

# Connection Pooling (Phase 2.2)
from polisyos.fabric.connectors.pool import (
    ConnectionPool,
    PoolClosedError,
    PoolConfig,
    PoolExhaustedError,
    PoolStats,
    PooledConnection,
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

# Caching layer (Phase 2.7)
from polisyos.fabric.connectors.cache import (
    CacheMetadata,
    CachePolicy,
    CacheStats,
    CachedFetchResult,
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
    SizeBoundedPolicy,
    SmartExpiryPolicy,
    StaticDataPolicy,
    TTLPolicy,
    VolatileDataPolicy,
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
    resolve_resilience_config,
    is_retryable_error,
    with_circuit_breaker,
    with_fallback,
    with_rate_limit,
    with_retry,
)

# Validation helpers (schema coercion)
from polisyos.fabric.connectors.validation import (
    coerce_fetch_result_against_schema,
    validate_fetch_result_against_schema,
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
    # === Registry Architecture (Phase 2.2) ===
    "ConnectorRegistry",
    "ConnectorEntry",
    "ConnectorPreferences",
    "RegistryStats",
    "RegistryMetrics",
    "RegistryError",
    "ConnectorAlreadyRegisteredError",
    "ConnectorNotFoundError",
    "ConnectorConfigError",
    "AmbiguousConnectorError",
    # === Connection Pooling (Phase 2.2) ===
    "ConnectionPool",
    "PoolConfig",
    "PooledConnection",
    "PoolStats",
    "PoolExhaustedError",
    "PoolClosedError",
    # === Discovery System (Phase 2.2) ===
    "ConnectorDiscovery",
    "DiscoveryResult",
    "DiscoveryError",
    "discover_connectors",
    "discover_connectors_from_modules",
    "get_discovery_errors",
    # === Caching Layer (Phase 2.7) ===
    "ConnectorCacheStore",
    "CachingConnectorProxy",
    "CachedFetchResult",
    "CacheMetadata",
    "CacheStats",
    "CachePolicy",
    "TTLPolicy",
    "StaticDataPolicy",
    "VolatileDataPolicy",
    "SmartExpiryPolicy",
    "LRUPolicy",
    "SizeBoundedPolicy",
    "PolicyRegistry",
    "InvalidationStrategy",
    "InvalidationEvent",
    "InvalidationTrigger",
    "InvalidationOrchestrator",
    "PrefetchScheduler",
    "PrefetchJob",
    # === Resilience Layer (Phase 2.9) ===
    "RetryPolicy",
    "RetryExhaustedError",
    "is_retryable_error",
    "with_retry",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "CircuitOpenError",
    "with_circuit_breaker",
    "RateLimiter",
    "AdaptiveRateLimiter",
    "RateLimiterConfig",
    "with_rate_limit",
    "FallbackStrategy",
    "FallbackChain",
    "CacheFallback",
    "MockFallback",
    "RaiseFallback",
    "with_fallback",
    "ResilienceConfig",
    "resolve_resilience_config",
    "apply_resilience",
    # === Validation Helpers ===
    "validate_fetch_result_against_schema",
    "coerce_fetch_result_against_schema",
    "get_registry",
]

__version__ = "2.2.0"
__phase__ = "Phase 2.2: Registry Architecture & Lazy Loading"


def get_registry() -> ConnectorRegistry:
    """
    Convenience function to get the ConnectorRegistry singleton.

    Usage:
        from polisyos.fabric.connectors import get_registry

        registry = get_registry()
        connector = registry.get("world_bank")
    """
    return ConnectorRegistry.get_instance()
