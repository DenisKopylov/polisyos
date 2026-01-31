"""ConnectorRegistry: central catalog for data source connectors.

Design goals:
- O(1) lookup by connector_id via primary index
- Capability-based queries via secondary indices
- Lazy loading with instance caching
- Namespace isolation
- Connection pooling keyed by (connector_fqid, config_fingerprint)
- Thread-safe for concurrent access
- Extensible via entry points and plugins
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Iterator

from packaging.version import parse as parse_version

from polisyos.common.logger import get_logger
from polisyos.ir.connectors import ConnectorCapability, ConnectorMetadataSpec, TrustLevel

if TYPE_CHECKING:
    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        ConnectionHandle,
        HealthStatus,
        SourceConnector,
    )
    from polisyos.fabric.connectors.pool import ConnectionPool, PoolConfig
    from polisyos.fabric.connectors.types import DatasetDescriptor

logger = get_logger(__name__)


# =============================================================================
# Exception Hierarchy
# =============================================================================


class RegistryError(Exception):
    """Base exception for registry-related errors."""


class ConnectorAlreadyRegisteredError(RegistryError):
    """Raised when attempting to register a connector with existing ID."""

    def __init__(self, connector_id: str) -> None:
        self.connector_id = connector_id
        super().__init__(
            f"Connector '{connector_id}' already registered. Use override=True to replace."
        )


class ConnectorNotFoundError(RegistryError):
    """Raised when requested connector is not in registry."""

    def __init__(self, connector_id: str, available: list[str] | None = None) -> None:
        self.connector_id = connector_id
        self.available = available or []
        msg = f"Connector '{connector_id}' not found"
        if self.available:
            preview = self.available[:5]
            msg += f". Available: {preview}{'...' if len(self.available) > 5 else ''}"
        super().__init__(msg)


class ConnectorConfigError(RegistryError):
    """Raised when connector configuration is invalid."""

    def __init__(self, connector_id: str, reason: str) -> None:
        self.connector_id = connector_id
        self.reason = reason
        super().__init__(f"Configuration error for '{connector_id}': {reason}")


class AmbiguousConnectorError(RegistryError):
    """Raised when connector ID matches multiple connectors."""

    def __init__(self, connector_id: str, matches: list[str]) -> None:
        self.connector_id = connector_id
        self.matches = matches
        super().__init__(
            f"Ambiguous connector ID '{connector_id}'. Matches: {matches}"
        )


# =============================================================================
# Registry Data Structures
# =============================================================================


@dataclass
class ConnectorEntry:
    """
    Registry entry for a connector.

    Separates metadata (immutable) from runtime state (mutable).
    Factory function enables lazy instantiation with instance caching.
    """

    metadata: ConnectorMetadataSpec
    capabilities: ConnectorCapability
    connector_class: type["SourceConnector"]
    factory: Callable[[], "SourceConnector"]
    default_config: "ConnectionConfig | None" = None

    # Runtime state (updated by registry operations)
    instance: "SourceConnector | None" = None
    loaded: bool = False
    known_datasets: frozenset[str] = field(default_factory=frozenset)
    dataset_descriptors: tuple["DatasetDescriptor", ...] = field(default_factory=tuple)
    last_health_check: datetime | None = None
    health_status: "HealthStatus | None" = None
    consecutive_failures: int = 0
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    _instance_lock: threading.Lock = field(
        default_factory=threading.Lock,
        repr=False,
        compare=False,
    )

    @property
    def fqid(self) -> str:
        """Fully qualified connector ID."""
        return self.metadata.fully_qualified_id

    @property
    def short_id(self) -> str:
        """Short connector ID without version."""
        return f"{self.metadata.namespace}.{self.metadata.connector_id}"


@dataclass
class ConnectorPreferences:
    """
    User preferences for connector selection during dataset resolution.

    Used by find_connectors_for_dataset() to rank candidates.
    """

    trust_weight: float = 0.3
    freshness_weight: float = 0.2
    capability_weight: float = 0.2
    reliability_weight: float = 0.3

    preferred_namespaces: list[str] = field(default_factory=list)
    excluded_connectors: set[str] = field(default_factory=set)
    min_trust_level: TrustLevel = TrustLevel.LOW

    def __post_init__(self) -> None:
        total = (
            self.trust_weight
            + self.freshness_weight
            + self.capability_weight
            + self.reliability_weight
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Preference weights must sum to 1.0, got {total}")


@dataclass
class RegistryStats:
    """Snapshot statistics for observability and monitoring."""

    registered_connectors: int
    loaded_connectors: int
    registrations_total: int
    queries_total: int
    get_calls_total: int
    active_pools: int
    namespaces: list[str]
    capabilities_distribution: dict[str, int]


@dataclass
class RegistryMetrics:
    """Monotonic counters suitable for metrics backends (snapshot)."""

    registrations_total: int
    queries_total: int
    get_calls_total: int
    pools_total: int
    pool_acquires_total: int
    pool_releases_total: int
    pool_creates_total: int
    pool_closes_total: int
    pool_health_checks_total: int
    pool_failed_health_checks_total: int
    pool_acquire_wait_time_total_ms: float


# =============================================================================
# ConnectorRegistry Singleton
# =============================================================================


class ConnectorRegistry:
    """
    Singleton registry for all data source connectors.

    Thread-safe singleton pattern with double-checked locking.

    Features:
    - O(1) lookup by fully qualified ID (primary index)
    - O(k) queries by capability/namespace/trust (secondary indices)
    - Lazy loading with instance caching
    - Connection pooling via integrated ConnectionPool instances
    - Health check tracking and automatic failover hints
    """

    _instance: ClassVar["ConnectorRegistry | None"] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        """
        Initialize registry data structures.

        Note: Use get_instance() instead of direct instantiation.
        """
        # Primary index: fully_qualified_id -> ConnectorEntry
        self._connectors: dict[str, ConnectorEntry] = {}

        # Secondary indices for O(k) queries (k = result size)
        self._by_namespace: dict[str, set[str]] = defaultdict(set)
        self._by_capability: dict[ConnectorCapability, set[str]] = defaultdict(set)
        self._by_tag: dict[str, set[str]] = defaultdict(set)
        self._by_trust_level: dict[TrustLevel, set[str]] = defaultdict(set)
        self._by_short_id: dict[str, set[str]] = defaultdict(set)

        # Connection pool management (keyed by (fqid, config_fingerprint))
        self._connection_pools: dict[tuple[str, str], "ConnectionPool"] = {}

        # Instance lock for thread-safe mutations
        self._instance_lock = threading.RLock()

        # Statistics for observability
        self._registration_count = 0
        self._query_count = 0
        self._get_count = 0

        # Bootstrapped flag
        self._bootstrapped = False

        # Optional caching integration
        self._cache_store = None
        self._enable_caching = True
        self._cache_wrappers: dict[str, Any] = {}

    @classmethod
    def get_instance(cls, *, bootstrap: bool = True) -> "ConnectorRegistry":
        """
        Get the singleton registry instance.

        Thread-safe with double-checked locking pattern.

        Args:
            bootstrap: If True, discover and register builtin connectors

        Returns:
            The singleton ConnectorRegistry instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = cls()
                    if bootstrap:
                        instance._bootstrap()
                    cls._instance = instance
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset singleton for testing.

        WARNING: NOT for production use. Closes all connection pools.
        """
        with cls._lock:
            instance = cls._instance
            cls._instance = None

        if instance is None:
            return

        pools_to_close = list(instance._connection_pools.values())
        instance._connectors.clear()
        instance._connection_pools.clear()

        if pools_to_close:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    for pool in pools_to_close:
                        asyncio.create_task(pool.close_all())
                else:
                    loop.run_until_complete(
                        asyncio.gather(*(pool.close_all() for pool in pools_to_close))
                    )
            except Exception:
                pass  # Best effort cleanup

        logger.info("ConnectorRegistry singleton reset")

    def configure_cache(
        self,
        cache_store: Any | None,
        *,
        enable_caching: bool = True,
        reset_wrappers: bool = True,
    ) -> None:
        """Configure optional connector caching behavior."""
        with self._instance_lock:
            self._cache_store = cache_store
            self._enable_caching = enable_caching
            if reset_wrappers:
                self._cache_wrappers.clear()

    def _bootstrap(self) -> None:
        """
        Initialize registry with discovered connectors.

        Uses entry points for plugin discovery.
        """
        if self._bootstrapped:
            return

        from polisyos.fabric.connectors.discovery import discover_connectors

        discovered_count = 0
        error_count = 0

        for connector_class in discover_connectors():
            try:
                self.register(connector_class)
                discovered_count += 1
            except ConnectorAlreadyRegisteredError:
                # Skip duplicates during bootstrap
                pass
            except Exception as e:
                error_count += 1
                logger.warning(
                    "Failed to register connector during bootstrap",
                    connector=getattr(connector_class, "connector_id", "unknown"),
                    error=str(e),
                    error_type=type(e).__name__,
                )

        self._bootstrapped = True
        logger.info(
            "ConnectorRegistry bootstrapped",
            discovered=discovered_count,
            errors=error_count,
            total_registered=len(self._connectors),
        )

    # =========================================================================
    # Registration
    # =========================================================================

    def register(
        self,
        connector_class: type["SourceConnector"],
        config: "ConnectionConfig | None" = None,
        *,
        override: bool = False,
        factory: Callable[[], "SourceConnector"] | None = None,
    ) -> str:
        """
        Register a connector class with optional default config.

        Args:
            connector_class: Class implementing SourceConnector protocol
            config: Optional default connection configuration
            override: Allow overwriting existing registration
            factory: Optional factory for instantiating connectors (DI-friendly)

        Returns:
            Fully qualified ID of registered connector

        Raises:
            ConnectorAlreadyRegisteredError: If connector exists and override=False
            ConnectorConfigError: If provided config is invalid
        """
        from polisyos.fabric.connectors.capabilities import validate_protocol_compliance

        # Validate protocol compliance
        violations = validate_protocol_compliance(connector_class)
        if violations:
            raise ConnectorConfigError(
                connector_id=getattr(connector_class, "connector_id", "unknown"),
                reason=f"Protocol violations: {violations}",
            )

        meta: ConnectorMetadataSpec = connector_class.metadata
        fqid = meta.fully_qualified_id
        caps = connector_class.capabilities

        connector_factory = factory or (lambda cls=connector_class: cls())

        with self._instance_lock:
            if fqid in self._connectors and not override:
                raise ConnectorAlreadyRegisteredError(fqid)

            # Validate config if provided
            if config is not None:
                validation = connector_class.validate_config(config)
                if hasattr(validation, "valid") and not validation.valid:
                    errors = getattr(validation, "issues", [])
                    raise ConnectorConfigError(
                        connector_id=fqid,
                        reason=f"Invalid configuration: {errors}",
                    )

            entry = ConnectorEntry(
                metadata=meta,
                capabilities=caps,
                connector_class=connector_class,
                factory=connector_factory,
                default_config=config,
                loaded=False,
            )

            # Remove old entry from indices if overriding
            if fqid in self._connectors:
                self._remove_from_indices(self._connectors[fqid])

            self._connectors[fqid] = entry
            self._update_indices(entry)
            self._registration_count += 1

            logger.info(
                "Registered connector",
                connector_id=fqid,
                namespace=meta.namespace,
                capabilities=caps.value if hasattr(caps, "value") else str(caps),
                trust_level=meta.trust_level.name,
                override=override,
            )

            return fqid

    def unregister(self, connector_id: str) -> bool:
        """
        Unregister a connector.

        Args:
            connector_id: Short ID or fully qualified ID

        Returns:
            True if connector was found and removed, False otherwise
        """
        try:
            fqid = self._resolve_id(connector_id)
        except ConnectorNotFoundError:
            return False

        pools_to_close: list[ConnectionPool] = []

        with self._instance_lock:
            entry = self._connectors.pop(fqid, None)
            if entry is None:
                return False

            self._remove_from_indices(entry)

            # Close any associated connection pools
            keys_to_remove = [key for key in self._connection_pools if key[0] == fqid]
            for key in keys_to_remove:
                pools_to_close.append(self._connection_pools.pop(key))

            logger.info("Unregistered connector", connector_id=fqid)

        if pools_to_close:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    for pool in pools_to_close:
                        asyncio.create_task(pool.close_all())
                else:
                    loop.run_until_complete(
                        asyncio.gather(*(pool.close_all() for pool in pools_to_close))
                    )
            except Exception:
                pass

        return True

    def _update_indices(self, entry: ConnectorEntry) -> None:
        """Update secondary indices after registration."""
        fqid = entry.fqid

        # Namespace index
        self._by_namespace[entry.metadata.namespace].add(fqid)

        # Short ID index (for fuzzy matching)
        self._by_short_id[entry.short_id].add(fqid)

        # Capability index (add to each matching capability's set)
        for cap in ConnectorCapability:
            if cap & entry.capabilities:
                self._by_capability[cap].add(fqid)

        # Trust level index
        self._by_trust_level[entry.metadata.trust_level].add(fqid)

        # Tag index (if tags present in metadata)
        if hasattr(entry.metadata, "tags"):
            for tag in entry.metadata.tags:
                self._by_tag[tag].add(fqid)

    def _remove_from_indices(self, entry: ConnectorEntry) -> None:
        """Remove connector from all secondary indices."""
        fqid = entry.fqid

        self._by_namespace[entry.metadata.namespace].discard(fqid)
        self._by_short_id[entry.short_id].discard(fqid)

        for cap in ConnectorCapability:
            if cap & entry.capabilities:
                self._by_capability[cap].discard(fqid)

        self._by_trust_level[entry.metadata.trust_level].discard(fqid)

        if hasattr(entry.metadata, "tags"):
            for tag in entry.metadata.tags:
                self._by_tag[tag].discard(fqid)

    def _apply_resilience_if_configured(
        self,
        connector: "SourceConnector",
        entry: ConnectorEntry,
    ) -> "SourceConnector":
        """
        Apply resilience wrappers to connector fetch if configured.

        Resilience is opt-in via metadata.resilience_config or connector.resilience_config.
        """
        if getattr(connector, "_resilience_wrapped", False):
            return connector

        config = getattr(connector, "resilience_config", None)
        if config is None:
            config = entry.metadata.resilience_config

        if config is None:
            return connector

        try:
            from polisyos.fabric.connectors.resilience import apply_resilience

            connector.fetch = apply_resilience(  # type: ignore[method-assign]
                connector.fetch,
                config=config,
                cache_store=self._cache_store,
            )
            setattr(connector, "_resilience_wrapped", True)
        except Exception as exc:
            logger.warning(
                "Failed to apply resilience wrappers",
                connector_id=entry.fqid,
                error=str(exc),
                error_type=type(exc).__name__,
            )

        return connector

    # =========================================================================
    # Retrieval (O(1) Lookup)
    # =========================================================================

    def get(
        self,
        connector_id: str,
        version: str | None = None,
        *,
        enable_cache: bool = True,
    ) -> "SourceConnector":
        """
        Get connector instance by ID.

        Lazy instantiation with instance caching.

        Args:
            connector_id: Short ID (e.g., "world_bank") or fully qualified ID
            version: Optional version constraint (e.g., "1.0.0")
            enable_cache: If True and caching is configured, wrap connector in cache proxy

        Returns:
            Instantiated connector implementing SourceConnector protocol

        Raises:
            ConnectorNotFoundError: If connector not registered
            AmbiguousConnectorError: If ID matches multiple connectors
        """
        fqid = self._resolve_id(connector_id, version)

        with self._instance_lock:
            entry = self._connectors.get(fqid)

        if entry is None:
            raise ConnectorNotFoundError(
                connector_id,
                available=list(self._connectors.keys()),
            )

        if entry.instance is None:
            with entry._instance_lock:
                if entry.instance is None:
                    entry.instance = entry.factory()
                    entry.loaded = True

        with self._instance_lock:
            self._get_count += 1

        connector = entry.instance
        connector = self._apply_resilience_if_configured(connector, entry)

        if self._enable_caching and enable_cache and self._cache_store is not None:
            try:
                from polisyos.fabric.connectors.cache.proxy import CachingConnectorProxy

                if isinstance(connector, CachingConnectorProxy):
                    return connector

                with self._instance_lock:
                    cached = self._cache_wrappers.get(fqid)
                    if cached is None:
                        cached = CachingConnectorProxy(connector, self._cache_store)
                        self._cache_wrappers[fqid] = cached
                return cached
            except Exception:
                return connector

        return connector

    def get_metadata(self, connector_id: str) -> ConnectorMetadataSpec:
        """
        Get connector metadata without instantiating.

        Args:
            connector_id: Short ID or fully qualified ID

        Returns:
            Connector metadata specification
        """
        fqid = self._resolve_id(connector_id)
        with self._instance_lock:
            return self._connectors[fqid].metadata

    def get_entry(self, connector_id: str) -> ConnectorEntry:
        """
        Get full registry entry for a connector.

        Provides access to runtime state like health status and failure counts.
        """
        fqid = self._resolve_id(connector_id)
        with self._instance_lock:
            return self._connectors[fqid]

    def has(self, connector_id: str) -> bool:
        """Check if a connector is registered."""
        try:
            self._resolve_id(connector_id)
            return True
        except (ConnectorNotFoundError, AmbiguousConnectorError):
            return False

    def _resolve_id(
        self,
        connector_id: str,
        version: str | None = None,
    ) -> str:
        """
        Resolve short ID to fully qualified ID.

        Supports:
        - Fully qualified IDs: "international.world_bank@1.0.0"
        - Namespace.ID format: "international.world_bank"
        - Short ID (may be ambiguous): "world_bank"
        """
        # Already fully qualified (has version)
        if "@" in connector_id:
            if connector_id in self._connectors:
                return connector_id
            raise ConnectorNotFoundError(
                connector_id,
                available=list(self._connectors.keys()),
            )

        # Check short_id index for namespace.id format
        if connector_id in self._by_short_id:
            candidates = list(self._by_short_id[connector_id])
            if version:
                candidates = [c for c in candidates if c.endswith(f"@{version}")]

            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1:
                # Return most recent version if no version specified
                if not version:
                    return self._select_latest_version(candidates)
                raise AmbiguousConnectorError(connector_id, candidates)

        # Fuzzy match on any part of the ID
        candidates = [fqid for fqid in self._connectors.keys() if connector_id in fqid]

        if not candidates:
            raise ConnectorNotFoundError(
                connector_id,
                available=list(self._connectors.keys()),
            )

        if version:
            candidates = [c for c in candidates if c.endswith(f"@{version}")]

        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise AmbiguousConnectorError(connector_id, candidates)

        raise ConnectorNotFoundError(
            connector_id,
            available=list(self._connectors.keys()),
        )

    def _select_latest_version(self, candidates: list[str]) -> str:
        """Select the latest semver version from candidate FQIDs."""
        def version_key(fqid: str):
            if "@" not in fqid:
                return parse_version("0")
            version = fqid.split("@", 1)[1]
            try:
                return parse_version(version)
            except Exception:
                return parse_version("0")

        return max(candidates, key=version_key)

    # =========================================================================
    # Queries (O(k) via Secondary Indices)
    # =========================================================================

    def query(
        self,
        *,
        namespace: str | None = None,
        capabilities: ConnectorCapability | None = None,
        tags: set[str] | None = None,
        trust_level_min: TrustLevel | None = None,
    ) -> Iterator[ConnectorMetadataSpec]:
        """
        Query connectors by multiple criteria.

        Uses secondary indices for efficient O(k) filtering where k is the result set size.
        All criteria are AND-combined.

        Args:
            namespace: Filter by namespace (exact match)
            capabilities: Filter by capabilities (must have ALL)
            tags: Filter by tags (must have ALL)
            trust_level_min: Minimum trust level (inclusive)

        Yields:
            Metadata for matching connectors (deterministic order)
        """
        self._query_count += 1

        candidate_sets: list[set[str]] = []

        if namespace:
            candidate_sets.append(self._by_namespace.get(namespace, set()))

        if capabilities:
            for cap in ConnectorCapability:
                if cap & capabilities:
                    candidate_sets.append(self._by_capability.get(cap, set()))

        if tags:
            for tag in tags:
                candidate_sets.append(self._by_tag.get(tag, set()))

        if trust_level_min:
            eligible: set[str] = set()
            for level in TrustLevel:
                if level >= trust_level_min:
                    eligible |= self._by_trust_level.get(level, set())
            candidate_sets.append(eligible)

        if candidate_sets:
            # If any filter yields no candidates, return immediately.
            if any(len(candidates) == 0 for candidates in candidate_sets):
                return
            # Start from the smallest set to minimize intersection cost.
            candidates = set(min(candidate_sets, key=len))
            for candidate_set in candidate_sets:
                candidates &= candidate_set
                if not candidates:
                    return
        else:
            candidates = set(self._connectors.keys())

        # Yield in deterministic order
        for fqid in sorted(candidates):
            yield self._connectors[fqid].metadata

    def query_entries(
        self,
        *,
        namespace: str | None = None,
        capabilities: ConnectorCapability | None = None,
        trust_level_min: TrustLevel | None = None,
    ) -> Iterator[ConnectorEntry]:
        """
        Query for full ConnectorEntry objects.

        Similar to query() but returns entries with runtime state.
        """
        for meta in self.query(
            namespace=namespace,
            capabilities=capabilities,
            trust_level_min=trust_level_min,
        ):
            yield self._connectors[meta.fully_qualified_id]

    def list_namespaces(self) -> list[str]:
        """List all registered namespaces."""
        return sorted(self._by_namespace.keys())

    def list_by_namespace(self, namespace: str) -> list[str]:
        """List all connector FQIDs in a namespace."""
        return sorted(self._by_namespace.get(namespace, set()))

    # =========================================================================
    # Dataset Resolution
    # =========================================================================

    def find_connectors_for_dataset(
        self,
        dataset_pattern: str,
        preferences: ConnectorPreferences | None = None,
    ) -> list[tuple[ConnectorMetadataSpec, float]]:
        """
        Find connectors that can provide a specific dataset.

        Returns scored list for automatic source selection in federation layer.

        Args:
            dataset_pattern: Dataset identifier or pattern to match
            preferences: User preferences for scoring

        Returns:
            List of (connector_metadata, relevance_score) sorted by score
        """
        results: list[tuple[ConnectorMetadataSpec, float]] = []
        prefs = preferences or ConnectorPreferences()

        for fqid, entry in self._connectors.items():
            # Skip excluded connectors
            if fqid in prefs.excluded_connectors:
                continue

            # Check trust level minimum
            if entry.metadata.trust_level < prefs.min_trust_level:
                continue

            match_score = self._dataset_match_score(entry, dataset_pattern)
            if match_score is None:
                continue

            score = self._compute_relevance_score(entry, prefs)
            score += match_score
            results.append((entry.metadata, score))

        return sorted(results, key=lambda x: x[1], reverse=True)

    def _dataset_match_score(self, entry: ConnectorEntry, pattern: str) -> float | None:
        """Evaluate dataset match confidence and return a small score bonus."""
        # Explicit dataset list
        if entry.known_datasets:
            if pattern in entry.known_datasets:
                return 0.3
            if any(pattern in ds for ds in entry.known_datasets):
                return 0.15
            return None

        # Dataset descriptors
        if entry.dataset_descriptors:
            for desc in entry.dataset_descriptors:
                if pattern == desc.dataset_id:
                    return 0.3
            for desc in entry.dataset_descriptors:
                if pattern in desc.dataset_id or pattern in desc.name:
                    return 0.15
            return None

        # If no catalog info is available, require CATALOG_BROWSE capability
        if entry.capabilities & ConnectorCapability.CATALOG_BROWSE:
            return 0.05

        return None

    def _compute_relevance_score(
        self,
        entry: ConnectorEntry,
        prefs: ConnectorPreferences,
    ) -> float:
        """
        Score connector suitability based on preferences.

        Factors:
        - Trust level (higher = better)
        - Capability count (more = better)
        - Reliability (fewer failures = better)
        - Freshness (recent health checks preferred)
        - Namespace preference bonus
        """
        score = 0.0

        # Trust weight (normalized to 0-1)
        trust_max = TrustLevel.AUTHORITATIVE.value
        trust_normalized = entry.metadata.trust_level.value / trust_max
        score += trust_normalized * prefs.trust_weight

        # Capability count (bonus for more features)
        cap_count = (
            bin(entry.capabilities.value).count("1") if hasattr(entry.capabilities, "value") else 1
        )
        cap_max = len(list(ConnectorCapability))
        cap_normalized = cap_count / cap_max
        score += cap_normalized * prefs.capability_weight

        # Reliability (inverse of failure rate)
        if entry.last_health_check is not None:
            reliability = 1.0 / (1.0 + entry.consecutive_failures)
            score += reliability * prefs.reliability_weight
        else:
            score += 0.5 * prefs.reliability_weight  # Unknown reliability

        # Freshness (time since last health check)
        if entry.last_health_check is not None:
            age_hours = (
                datetime.now(timezone.utc) - entry.last_health_check
            ).total_seconds() / 3600
            freshness = max(0.0, 1.0 - (age_hours / 24.0))  # Decay over 24h
            score += freshness * prefs.freshness_weight
        else:
            score += 0.5 * prefs.freshness_weight

        # Namespace preference bonus
        if entry.metadata.namespace in prefs.preferred_namespaces:
            score += 0.1

        return score

    # =========================================================================
    # Connection Pooling
    # =========================================================================

    async def get_connection(
        self,
        connector_id: str,
        config: "ConnectionConfig | None" = None,
    ) -> "ConnectionHandle":
        """
        Get a connection from the pool (or create new pool).

        Connections are pooled per (connector_fqid, config_fingerprint).

        Args:
            connector_id: Short ID or fully qualified ID
            config: Connection configuration (uses default if not provided)

        Returns:
            ConnectionHandle from pool

        Raises:
            ConnectorNotFoundError: If connector not registered
            ConnectorConfigError: If no config available
        """
        from polisyos.fabric.connectors.pool import ConnectionPool, PoolConfig

        fqid = self._resolve_id(connector_id)

        with self._instance_lock:
            entry = self._connectors.get(fqid)

        if entry is None:
            raise ConnectorNotFoundError(connector_id)

        effective_config = config or entry.default_config
        if effective_config is None:
            raise ConnectorConfigError(
                connector_id=fqid,
                reason="No config provided and no default config registered",
            )

        fingerprint = self._config_fingerprint(effective_config)
        pool_key = (fqid, fingerprint)

        with self._instance_lock:
            pool = self._connection_pools.get(pool_key)

        if pool is None:
            pool_config = PoolConfig(max_size=effective_config.max_connections)
            breaker = None
            try:
                if entry.metadata.resilience_config is not None:
                    from polisyos.fabric.connectors.resilience import (
                        CircuitBreaker,
                        resolve_resilience_config,
                    )

                    resolved = resolve_resilience_config(
                        entry.metadata.resilience_config,
                        cache_store=self._cache_store,
                    )
                    if resolved is not None:
                        circuit = resolved.circuit_breaker
                        if isinstance(circuit, CircuitBreaker):
                            breaker = circuit
                        elif circuit is not None:
                            breaker = CircuitBreaker(
                                circuit_id=f"pool:{fqid}:{fingerprint[:8]}",
                                config=circuit,
                            )
            except Exception as exc:
                logger.warning(
                    "Failed to configure pool circuit breaker",
                    connector_id=fqid,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

            new_pool = ConnectionPool(
                connector_factory=entry.factory,
                config=effective_config,
                pool_config=pool_config,
                pool_id=f"pool-{fqid}-{fingerprint[:8]}",
                circuit_breaker=breaker,
            )
            with self._instance_lock:
                pool = self._connection_pools.get(pool_key)
                if pool is None:
                    self._connection_pools[pool_key] = new_pool
                    pool = new_pool

        return await pool.acquire()

    async def release_connection(
        self,
        connector_id: str,
        handle: "ConnectionHandle",
    ) -> None:
        """Release a connection back to the pool."""
        fqid = self._resolve_id(connector_id)
        fingerprint = self._config_fingerprint(handle.config)
        pool_key = (fqid, fingerprint)

        with self._instance_lock:
            pool = self._connection_pools.get(pool_key)

        if pool is not None:
            await pool.release(handle)
        else:
            logger.warning(
                "Connection pool not found for release",
                connector_id=fqid,
                session_id=handle.session_id,
            )

    def _config_fingerprint(self, config: "ConnectionConfig") -> str:
        """Compute stable fingerprint for connection config."""
        payload = config.to_dict(redact=False)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    # =========================================================================
    # Health Tracking
    # =========================================================================

    def update_health(
        self,
        connector_id: str,
        health: "HealthStatus",
    ) -> None:
        """
        Update health status for a connector.

        Called by monitoring systems after health checks.
        """
        fqid = self._resolve_id(connector_id)

        with self._instance_lock:
            entry = self._connectors.get(fqid)
            if entry is None:
                return

            entry.last_health_check = datetime.now(timezone.utc)
            entry.health_status = health

            if health.healthy:
                entry.consecutive_failures = 0
            else:
                entry.consecutive_failures += 1

            logger.debug(
                "Updated connector health",
                connector_id=fqid,
                healthy=health.healthy,
                consecutive_failures=entry.consecutive_failures,
            )

    # =========================================================================
    # Statistics & Observability
    # =========================================================================

    @property
    def stats(self) -> RegistryStats:
        """Get registry statistics for observability."""
        # Count capabilities distribution
        cap_dist: dict[str, int] = {}
        for cap in ConnectorCapability:
            count = len(self._by_capability.get(cap, set()))
            if count > 0:
                cap_dist[cap.name] = count

        loaded_count = sum(1 for e in self._connectors.values() if e.loaded)

        return RegistryStats(
            registered_connectors=len(self._connectors),
            loaded_connectors=loaded_count,
            registrations_total=self._registration_count,
            queries_total=self._query_count,
            get_calls_total=self._get_count,
            active_pools=len(self._connection_pools),
            namespaces=self.list_namespaces(),
            capabilities_distribution=cap_dist,
        )

    @property
    def metrics(self) -> RegistryMetrics:
        """Get aggregated registry metrics counters (snapshot)."""
        with self._instance_lock:
            pools = list(self._connection_pools.values())
            registrations_total = self._registration_count
            queries_total = self._query_count
            get_calls_total = self._get_count

        pool_acquires_total = 0
        pool_releases_total = 0
        pool_creates_total = 0
        pool_closes_total = 0
        pool_health_checks_total = 0
        pool_failed_health_checks_total = 0
        pool_acquire_wait_time_total_ms = 0.0

        for pool in pools:
            stats = pool.get_stats()
            pool_acquires_total += stats.total_acquires
            pool_releases_total += stats.total_releases
            pool_creates_total += stats.total_creates
            pool_closes_total += stats.total_closes
            pool_health_checks_total += stats.total_health_checks
            pool_failed_health_checks_total += stats.failed_health_checks
            pool_acquire_wait_time_total_ms += stats.acquire_wait_time_total_ms

        return RegistryMetrics(
            registrations_total=registrations_total,
            queries_total=queries_total,
            get_calls_total=get_calls_total,
            pools_total=len(pools),
            pool_acquires_total=pool_acquires_total,
            pool_releases_total=pool_releases_total,
            pool_creates_total=pool_creates_total,
            pool_closes_total=pool_closes_total,
            pool_health_checks_total=pool_health_checks_total,
            pool_failed_health_checks_total=pool_failed_health_checks_total,
            pool_acquire_wait_time_total_ms=pool_acquire_wait_time_total_ms,
        )

    def __len__(self) -> int:
        """Number of registered connectors."""
        return len(self._connectors)

    def __iter__(self) -> Iterator[str]:
        """Iterate over registered connector FQIDs."""
        return iter(sorted(self._connectors.keys()))

    def __contains__(self, connector_id: str) -> bool:
        """Check if connector is registered."""
        return self.has(connector_id)
