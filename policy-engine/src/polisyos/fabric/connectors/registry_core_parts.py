"""ConnectorRegistry facade composed from decomposed registry sub-modules."""

from __future__ import annotations

import asyncio
import json
import threading
import weakref
from collections import OrderedDict
from collections.abc import Iterator
from concurrent.futures import Future
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from packaging.version import Version
from packaging.version import parse as parse_version

from polisyos.common.logger import get_logger
from polisyos.core.canon import content_hash
from polisyos.core.registry.generic import GenericRegistry
from polisyos.fabric.connectors._registry_errors import (
    AmbiguousConnectorError,
    ConnectorAlreadyRegisteredError,
    ConnectorConfigError,
    ConnectorNotFoundError,
    RegistryError,
)
from polisyos.fabric.connectors._registry_lifecycle import (
    RegistryLifecycleMixin,
)
from polisyos.fabric.connectors._registry_lifecycle import (
    _StreamOwnerLease as StreamOwnerLeaseState,
)
from polisyos.fabric.connectors._registry_lifecycle import (
    _StreamOwnerStartup as StreamOwnerStartupState,
)
from polisyos.fabric.connectors._registry_lifecycle import (
    _StreamStartupTask as StreamStartupTaskState,
)
from polisyos.fabric.connectors._registry_models import (
    ConnectorEntry,
    ConnectorPreferences,
    RegistryMetrics,
    RegistryStats,
    _ConnectorRegistrationBinding,
)
from polisyos.ir.connectors import ConnectorCapability, ConnectorMetadataSpec, TrustLevel

__all__ = [
    "AmbiguousConnectorError",
    "ConnectorAlreadyRegisteredError",
    "ConnectorConfigError",
    "ConnectorEntry",
    "ConnectorNotFoundError",
    "ConnectorPreferences",
    "ConnectorRegistry",
    "RegistryError",
    "RegistryMetrics",
    "RegistryStats",
]

if TYPE_CHECKING:
    from collections.abc import Iterator

    from polisyos.fabric.connectors.base import (
        ConnectionConfig,
        ConnectionHandle,
        HealthStatus,
        SourceConnectorInstance,
        SourceConnectorValue,
    )
    from polisyos.fabric.connectors.cache.store import ConnectorCacheStore
    from polisyos.fabric.connectors.contracts import ContractRegistry
    from polisyos.fabric.connectors.pool import ConnectionPool

logger = get_logger(__name__)
MAX_CONNECTION_POOLS = 512
_POOL_KEY_STATE_KEY = "__polisyos_connector_pool_key"


def _registration_binding_for_entry(
    registry: ConnectorRegistry,
    entry: ConnectorEntry,
) -> _ConnectorRegistrationBinding:
    """Resolve and verify the private registration record for one live entry."""
    with registry._instance_lock:
        binding = registry._registered_owner_bindings.get(id(entry))
        if (
            binding is None
            or binding.entry is not entry
            or registry._connectors.get(entry.fqid) is not entry
        ):
            raise ConnectorConfigError(
                connector_id=entry.fqid,
                reason="Connector entry has no live registry-owned registration binding",
            )

        if entry.runtime_connector_id != binding.runtime_connector_id:
            detail = "runtime owner"
        elif entry.connector_class is not binding.connector_class:
            detail = "connector class"
        elif entry.factory is not binding.factory:
            detail = "factory"
        elif entry.instance is not binding.instance:
            detail = "admitted instance"
        elif entry.loaded is not (binding.instance is not None):
            detail = "loaded state"
        else:
            return binding

    raise ConnectorConfigError(
        connector_id=entry.fqid,
        reason=(
            f"Connector entry {detail} differs from its registry-owned registration binding; "
            "re-register to replace the selected connector"
        ),
    )


def _same_registration_binding(
    current: _ConnectorRegistrationBinding,
    expected: _ConnectorRegistrationBinding,
) -> bool:
    """Compare stable identity while permitting same-entry lazy materialization."""
    return (
        current.entry is expected.entry
        and current.runtime_connector_id == expected.runtime_connector_id
        and current.connector_class is expected.connector_class
        and current.factory is expected.factory
        and current.registration_generation == expected.registration_generation
    )


def _require_expected_registration_binding(
    registry: ConnectorRegistry,
    entry: ConnectorEntry,
    expected: _ConnectorRegistrationBinding | None,
) -> _ConnectorRegistrationBinding:
    """Require a captured registration to remain the exact live registry owner."""
    current = _registration_binding_for_entry(registry, entry)
    if expected is not None and not _same_registration_binding(current, expected):
        raise ConnectorConfigError(
            connector_id=entry.fqid,
            reason="Connector registration changed after capture",
        )
    return current


def _validated_registration_owner_id(
    entry: ConnectorEntry,
    binding: _ConnectorRegistrationBinding,
) -> str:
    """Validate the runtime owner from one already-captured registration."""
    from polisyos.fabric.connectors.base import validate_connector_owner_id

    try:
        return validate_connector_owner_id(binding.runtime_connector_id)
    except ValueError as exc:
        raise ConnectorConfigError(
            connector_id=entry.fqid,
            reason="Connector entry has no valid registry-owned runtime owner",
        ) from exc


def selected_connector_owner_id(
    registry: ConnectorRegistry,
    entry: ConnectorEntry,
) -> str:
    """Resolve the immutable runtime identity captured for this registration."""
    binding = _registration_binding_for_entry(registry, entry)
    return _validated_registration_owner_id(entry, binding)


def require_selected_connector_owner(
    entry: ConnectorEntry,
    connector: SourceConnectorValue[Any],
    selected_owner_id: str,
    *,
    source: str,
) -> SourceConnectorValue[Any]:
    """Require a factory or cached instance to retain the selected class owner."""
    from polisyos.fabric.connectors.base import require_connector_owner

    try:
        require_connector_owner(connector, selected_owner_id)
    except ValueError as exc:
        raise ConnectorConfigError(
            connector_id=entry.fqid,
            reason=f"{source} owner does not match selected connector class: {exc}",
        ) from exc
    return connector


def create_selected_connector(
    registry: ConnectorRegistry,
    entry: ConnectorEntry,
    selected_owner_id: str,
) -> SourceConnectorValue[Any]:
    """Invoke only the factory captured for this exact registration."""
    binding = _registration_binding_for_entry(registry, entry)
    if binding.runtime_connector_id != selected_owner_id:
        raise ConnectorConfigError(
            connector_id=entry.fqid,
            reason="Selected connector owner no longer matches its registration binding",
        )
    return require_selected_connector_owner(
        entry,
        binding.factory(),
        binding.runtime_connector_id,
        source="factory",
    )


@dataclass(eq=False)
class _StreamOwnerStartup:
    """One in-flight startup, settled independently of its asyncio loop."""

    task: StreamStartupTaskState
    loop: asyncio.AbstractEventLoop
    completed: Future[None] = field(default_factory=Future)
    cleanup_started: bool = False


@dataclass(eq=False)
class _StreamOwnerLease:
    """Registry-local ownership of one logical stream and its private pool."""

    fqid: str
    dataset_id: str
    partition_key: str
    pool: ConnectionPool[SourceConnectorValue[Any]] | None = None
    startup: StreamOwnerStartupState | None = None
    invalidated: bool = False

    @property
    def key(self) -> tuple[str, str, str]:
        return self.fqid, self.dataset_id, self.partition_key


class ConnectorRegistry(RegistryLifecycleMixin):
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

    _instance: ClassVar[ConnectorRegistry | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        """
        Initialize registry data structures.

        Note: Use get_instance() instead of direct instantiation.
        """
        self._registered_owner_bindings: MappingProxyType[int, _ConnectorRegistrationBinding] = (
            MappingProxyType({})
        )
        self._connectors = GenericRegistry[str, ConnectorEntry](
            key_fn=lambda entry: entry.fqid,
            indexers={
                "namespace": lambda entry: entry.metadata.namespace,
                "short_id": lambda entry: entry.short_id,
                "trust_level": lambda entry: entry.metadata.trust_level,
                "tag": lambda entry: getattr(entry.metadata, "tags", ()),
                "capability": lambda entry: [
                    cap for cap in ConnectorCapability if cap & entry.capabilities
                ],
            },
        )

        # Connection pool management is scoped by event loop because pools own
        # asyncio primitives; fresh-loop callers must not share those objects.
        self._connection_pools: OrderedDict[
            tuple[str, str, int], ConnectionPool[SourceConnectorValue[Any]]
        ] = OrderedDict()
        # Pools whose first cleanup attempt cannot confirm physical disconnect
        # are retained here.  This includes startup-created stream pools and
        # normal owners evicted by LRU/shutdown; it stays separate from the
        # LRU so an unresolved physical owner remains registry-reachable.
        self._pending_startup_cleanup: dict[
            int, tuple[str, ConnectionPool[SourceConnectorValue[Any]]]
        ] = {}
        # A private stream pool is deliberately not in the general connection
        # pool cache. This registry-local lease prevents a second private pool
        # from owning the same logical dataset/partition while its first pool is
        # active or awaiting confirmed physical cleanup.
        self._stream_owner_leases: dict[tuple[str, str, str], StreamOwnerLeaseState] = {}
        self._stream_owner_admissions_closed = False
        self._max_connection_pools = MAX_CONNECTION_POOLS
        self._loop_scope_ids: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, int] = (
            weakref.WeakKeyDictionary()
        )
        self._next_loop_scope_id = 1

        # Instance lock for thread-safe mutations
        self._instance_lock = threading.RLock()

        # Statistics for observability
        self._registration_count = 0
        self._query_count = 0
        self._get_count = 0

        # Bootstrapped flag
        self._bootstrapped = False

        # Optional caching integration
        self._cache_store: ConnectorCacheStore | None = None
        self._enable_caching = True
        self._cache_wrappers: dict[tuple[str, int], SourceConnectorInstance[Any]] = {}
        self._contract_registry: ContractRegistry | None = None
        self._contract_validation_mode: Literal["strict", "warn", "disabled"] = "warn"
        self._contract_wrappers: dict[tuple[str, int], SourceConnectorInstance[Any]] = {}
        self._schema_invalidation_callback_registered = False
        self._bootstrap_contract_registry()

    @classmethod
    def get_instance(cls, *, bootstrap: bool = True) -> ConnectorRegistry:
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

        pools_to_close = []
        for pool_key, pool in instance._connection_pools.items():
            instance._pending_startup_cleanup[id(pool)] = (pool_key[0], pool)
            pools_to_close.append(pool)
        for lease in instance._stream_owner_leases.values():
            if lease.pool is not None:
                instance._pending_startup_cleanup[id(lease.pool)] = (lease.fqid, lease.pool)
                pools_to_close.append(lease.pool)
        pools_to_close.extend(pool for _fqid, pool in instance._pending_startup_cleanup.values())
        if pools_to_close and instance._has_running_loop():
            with cls._lock:
                cls._instance = instance
            raise RuntimeError(
                "ConnectorRegistry.reset_instance() cannot close pools while an "
                "event loop is running; call await registry.shutdown_async() first."
            )
        instance._connectors.clear()
        instance._registered_owner_bindings = MappingProxyType({})
        instance._connection_pools.clear()

        try:
            instance._close_pools_sync(pools_to_close)
        except BaseException:
            # Keep the singleton reachable when a physical disconnect is still
            # pending; callers can retry through shutdown_async().
            with cls._lock:
                cls._instance = instance
            raise

        logger.info("ConnectorRegistry singleton reset")

    def get(
        self,
        connector_id: str,
        version: str | None = None,
        *,
        enable_cache: bool = True,
        _registration_binding: _ConnectorRegistrationBinding | None = None,
    ) -> SourceConnectorValue[Any]:
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

        binding = _require_expected_registration_binding(self, entry, _registration_binding)

        if binding.instance is None:
            with entry._instance_lock:
                binding = _require_expected_registration_binding(self, entry, _registration_binding)
                if binding.instance is None:
                    selected_owner_id = binding.runtime_connector_id
                    admitted_instance = create_selected_connector(self, entry, selected_owner_id)
                    with self._instance_lock:
                        current_binding = self._registered_owner_bindings.get(id(entry))
                        if (
                            current_binding is None
                            or current_binding is not binding
                            or current_binding.entry is not entry
                            or self._connectors.get(fqid) is not entry
                        ):
                            raise ConnectorConfigError(
                                connector_id=fqid,
                                reason="Connector registration changed during lazy admission",
                            )
                        _registration_binding_for_entry(self, entry)
                        admitted_binding = _ConnectorRegistrationBinding(
                            entry=entry,
                            runtime_connector_id=binding.runtime_connector_id,
                            connector_class=binding.connector_class,
                            factory=binding.factory,
                            registration_generation=binding.registration_generation,
                            instance=admitted_instance,
                        )
                        owner_bindings = dict(self._registered_owner_bindings)
                        owner_bindings[id(entry)] = admitted_binding
                        self._registered_owner_bindings = MappingProxyType(owner_bindings)
                        entry.instance = admitted_instance
                        entry.loaded = True
                        binding = admitted_binding

        selected_owner_id = binding.runtime_connector_id
        connector = binding.instance
        if connector is None:
            raise ConnectorConfigError(
                connector_id=fqid,
                reason="Registered connector has no registry-admitted instance",
            )
        connector = require_selected_connector_owner(
            entry,
            connector,
            selected_owner_id,
            source="registered instance",
        )

        with self._instance_lock:
            self._get_count += 1

        connector = self._apply_resilience_if_configured(connector, entry)
        connector = self._apply_contract_validation_wrapper(
            connector,
            fqid=fqid,
            entry=entry,
            binding=binding,
        )
        connector = require_selected_connector_owner(
            entry,
            connector,
            selected_owner_id,
            source="wrapped connector",
        )
        self._assert_current_registration(entry, binding)

        surface = connector
        if self._enable_caching and enable_cache and self._cache_store is not None:
            try:
                from polisyos.fabric.connectors.cache.proxy import CachingConnectorProxy
            except ImportError:
                logger.debug(
                    "Failed to load caching proxy for connector %s, using unwrapped",
                    fqid,
                    exc_info=True,
                )
                surface = self._apply_slo_metrics_wrapper(connector, connector_id=fqid)
            else:
                if isinstance(connector, CachingConnectorProxy):
                    surface = connector
                else:
                    try:
                        with self._instance_lock:
                            self._assert_current_registration(entry, binding)
                            wrapper_key = (fqid, binding.registration_generation)
                            cached = self._cache_wrappers.get(wrapper_key)
                            if cached is None:
                                cached = CachingConnectorProxy(
                                    connector,
                                    self._cache_store,
                                    schema_hash_provider=self._build_schema_hash_provider(
                                        connector_short_id=entry.short_id
                                    ),
                                )
                                self._cache_wrappers[wrapper_key] = cached
                        surface = self._apply_slo_metrics_wrapper(
                            cached,
                            connector_id=fqid,
                        )
                    except Exception:
                        logger.debug(
                            "Failed to create caching proxy for connector %s, using unwrapped",
                            fqid,
                            exc_info=True,
                        )
                        surface = self._apply_slo_metrics_wrapper(
                            connector,
                            connector_id=fqid,
                        )
        else:
            surface = self._apply_slo_metrics_wrapper(connector, connector_id=fqid)

        # All successful get() surfaces, including optional-wrapper fallbacks,
        # linearize here against the exact registration selected above.
        self._assert_current_registration(entry, binding)
        if _registration_binding is not None:
            self._require_registration_binding(connector_id, _registration_binding)
        return require_selected_connector_owner(
            entry,
            surface,
            selected_owner_id,
            source="connector surface",
        )

    def _capture_registration_binding(
        self,
        connector_id: str,
    ) -> _ConnectorRegistrationBinding:
        """Capture the current exact registration without instantiating it."""
        fqid = self._resolve_id(connector_id)
        with self._instance_lock:
            entry = self._connectors.get(fqid)
        if entry is None:
            raise ConnectorNotFoundError(connector_id)
        return _registration_binding_for_entry(self, entry)

    def _require_registration_binding(
        self,
        connector_id: str,
        expected: _ConnectorRegistrationBinding,
    ) -> _ConnectorRegistrationBinding:
        """Require a captured exact registration to remain current."""
        fqid = self._resolve_id(connector_id)
        with self._instance_lock:
            entry = self._connectors.get(fqid)
        if entry is None:
            raise ConnectorConfigError(
                connector_id=connector_id,
                reason="Captured connector registration is no longer registered",
            )
        return _require_expected_registration_binding(self, entry, expected)

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
            return self._connectors.require(fqid).metadata

    def get_entry(self, connector_id: str) -> ConnectorEntry:
        """
        Get full registry entry for a connector.

        Provides access to runtime state like health status and failure counts.
        """
        fqid = self._resolve_id(connector_id)
        with self._instance_lock:
            return self._connectors.require(fqid)

    def set_default_config(
        self,
        connector_id: str,
        config: ConnectionConfig,
    ) -> None:
        """Set default ConnectionConfig for a registered connector.

        Args:
            connector_id: Short ID or fully qualified ID
            config: Default connection configuration

        Raises:
            ConnectorNotFoundError: If connector not registered
        """
        fqid = self._resolve_id(connector_id)
        with self._instance_lock:
            entry = self._connectors.get(fqid)
        if entry is None:
            raise ConnectorNotFoundError(
                connector_id,
                available=list(self._connectors.keys()),
            )
        entry.default_config = config
        logger.debug("Set default config", connector_id=fqid)

    def get_default_config(
        self,
        connector_id: str,
    ) -> ConnectionConfig | None:
        """Get default ConnectionConfig for a registered connector.

        Returns None if no default config is set.
        """
        fqid = self._resolve_id(connector_id)
        with self._instance_lock:
            entry = self._connectors.get(fqid)
        if entry is None:
            raise ConnectorNotFoundError(
                connector_id,
                available=list(self._connectors.keys()),
            )
        return entry.default_config

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
            if self._connectors.get(connector_id) is not None:
                return connector_id
            raise ConnectorNotFoundError(
                connector_id,
                available=list(self._connectors.keys()),
            )

        # Check short_id index for namespace.id format
        short_id_matches = [entry.fqid for entry in self._connectors.find("short_id", connector_id)]
        if short_id_matches:
            candidates = short_id_matches
            if version:
                candidates = [
                    candidate for candidate in candidates if candidate.endswith(f"@{version}")
                ]

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

        def version_key(fqid: str) -> Version:
            if "@" not in fqid:
                return parse_version("0")
            version = fqid.split("@", 1)[1]
            try:
                return parse_version(version)
            except Exception:
                logger.debug(
                    "Failed to parse version from FQID %s",
                    fqid,
                    exc_info=True,
                )
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
            namespace_matches = {
                entry.fqid for entry in self._connectors.find("namespace", namespace)
            }
            candidate_sets.append(namespace_matches)

        if capabilities:
            for cap in ConnectorCapability:
                if cap & capabilities:
                    cap_matches = {entry.fqid for entry in self._connectors.find("capability", cap)}
                    candidate_sets.append(cap_matches)

        if tags:
            for tag in tags:
                tag_matches = {entry.fqid for entry in self._connectors.find("tag", tag)}
                candidate_sets.append(tag_matches)

        if trust_level_min:
            eligible: set[str] = set()
            for level in TrustLevel:
                if level >= trust_level_min:
                    eligible |= {
                        entry.fqid for entry in self._connectors.find("trust_level", level)
                    }
            candidate_sets.append(eligible)

        if candidate_sets:
            # If any filter yields no candidates, return immediately.
            if any(len(candidates) == 0 for candidates in candidate_sets):
                return
            # Start from the smallest set to minimize intersection cost.
            smallest_candidates: set[str] = min(
                candidate_sets, key=lambda candidate_set: len(candidate_set)
            )
            candidates = set(smallest_candidates)
            for candidate_set in candidate_sets:
                candidates &= candidate_set
                if not candidates:
                    return
        else:
            candidates = set(self._connectors.keys())

        # Yield in deterministic order
        for fqid in sorted(candidates):
            entry = self._connectors.get(fqid)
            if entry is None:
                continue
            yield entry.metadata

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
            entry = self._connectors.get(meta.fully_qualified_id)
            if entry is not None:
                yield entry

    def list_namespaces(self) -> list[str]:
        """List all registered namespaces."""
        return sorted(str(value) for value in self._connectors.index_values("namespace"))

    def list_by_namespace(self, namespace: str) -> list[str]:
        """List all connector FQIDs in a namespace."""
        return sorted(entry.fqid for entry in self._connectors.find("namespace", namespace))

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
            age_hours = (datetime.now(UTC) - entry.last_health_check).total_seconds() / 3600
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
        config: ConnectionConfig | None = None,
        *,
        _registration_binding: _ConnectorRegistrationBinding | None = None,
    ) -> ConnectionHandle:
        """Get a normally validated connection from the configured pool."""

        pool, pool_key = await self._resolve_connection_pool(
            connector_id,
            config,
            _registration_binding=_registration_binding,
        )
        handle = await pool.acquire()
        handle.set_state(_POOL_KEY_STATE_KEY, pool_key)
        return handle

    async def _get_connection_with_live_permit(
        self,
        connector_id: str,
        config: ConnectionConfig | None,
        *,
        dataset_id: str,
        permit: object,
    ) -> ConnectionHandle:
        """Route one journal-authorized lease through its registered pool owner."""

        pool, pool_key = await self._resolve_connection_pool(connector_id, config)
        _connector, handle = await pool._acquire_with_live_permit(
            permit,
            connector_id=connector_id,
            dataset_id=dataset_id,
        )
        handle.set_state(_POOL_KEY_STATE_KEY, pool_key)
        return handle

    async def _resolve_connection_pool(
        self,
        connector_id: str,
        config: ConnectionConfig | None,
        *,
        _registration_binding: _ConnectorRegistrationBinding | None = None,
    ) -> tuple[ConnectionPool[SourceConnectorValue[Any]], tuple[str, str, int]]:
        """Resolve or create the one pool owned for this connector/config/loop."""

        from polisyos.fabric.connectors.pool import ConnectionPool, PoolConfig

        fqid = self._resolve_id(connector_id)
        with self._instance_lock:
            entry = self._connectors.get(fqid)
            if entry is not None:
                binding = _require_expected_registration_binding(self, entry, _registration_binding)
        if entry is None:
            if _registration_binding is not None:
                raise ConnectorConfigError(
                    connector_id=connector_id,
                    reason="Captured connector registration is no longer registered",
                )
            raise ConnectorNotFoundError(connector_id)

        selected_owner_id = _validated_registration_owner_id(entry, binding)

        effective_config = config or entry.default_config
        if effective_config is None:
            raise ConnectorConfigError(
                connector_id=fqid,
                reason="No config provided and no default config registered",
            )

        fingerprint = self._config_fingerprint(effective_config)
        registration_fingerprint = f"{fingerprint}:registration:{binding.registration_generation}"
        with self._instance_lock:
            pool_scope = self._current_pool_scope_locked()
        pool_key = (fqid, registration_fingerprint, pool_scope)
        with self._instance_lock:
            current_entry = self._connectors.get(fqid)
            if current_entry is not entry:
                raise ConnectorConfigError(
                    connector_id=fqid,
                    reason="Connector registration changed during pool selection",
                )
            current_binding = _require_expected_registration_binding(
                self, entry, _registration_binding
            )
            if not _same_registration_binding(current_binding, binding):
                raise ConnectorConfigError(
                    connector_id=fqid,
                    reason="Connector registration changed during pool selection",
                )
            pool = self._get_connection_pool_locked(pool_key)

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
                                circuit_id=(
                                    f"pool:{fqid}:{fingerprint[:8]}:"
                                    f"registration:{binding.registration_generation}"
                                ),
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
                connector_factory=lambda: create_selected_connector(self, entry, selected_owner_id),
                config=effective_config,
                pool_config=pool_config,
                pool_id=(
                    f"pool-{fqid}-{fingerprint[:8]}-"
                    f"registration{binding.registration_generation}-loop{pool_scope}"
                ),
                circuit_breaker=breaker,
                expected_connector_id=selected_owner_id,
            )
            evicted_pools: list[ConnectionPool[SourceConnectorValue[Any]]] = []
            with self._instance_lock:
                current_entry = self._connectors.get(fqid)
                if current_entry is not entry:
                    raise ConnectorConfigError(
                        connector_id=fqid,
                        reason="Connector registration changed before pool admission",
                    )
                current_binding = _require_expected_registration_binding(
                    self, entry, _registration_binding
                )
                if not _same_registration_binding(current_binding, binding):
                    raise ConnectorConfigError(
                        connector_id=fqid,
                        reason="Connector registration changed before pool admission",
                    )
                pool = self._get_connection_pool_locked(pool_key)
                if pool is None:
                    evicted_pools = self._store_connection_pool_locked(pool_key, new_pool)
                    pool = new_pool
            for evicted_pool in evicted_pools:
                await evicted_pool.close_all()

        return pool, pool_key

    def _release_pool_candidates(
        self, handle: ConnectionHandle
    ) -> list[ConnectionPool[SourceConnectorValue[Any]]]:
        """Return active and retained pools, using the handle route only for ordering."""
        candidates: list[ConnectionPool[SourceConnectorValue[Any]]] = []
        seen: set[int] = set()

        def add(pool: ConnectionPool[SourceConnectorValue[Any]] | None) -> None:
            if pool is None or id(pool) in seen:
                return
            seen.add(id(pool))
            candidates.append(pool)

        # The route tag is only a candidate-order hint. Read it outside the
        # registry lock and let malformed/replaced state fall through to the
        # exact-handle owner scan below.
        try:
            stored_pool_key = handle.get_state(_POOL_KEY_STATE_KEY)
        except Exception:
            stored_pool_key = None

        with self._instance_lock:
            if (
                isinstance(stored_pool_key, tuple)
                and len(stored_pool_key) == 3
                and isinstance(stored_pool_key[0], str)
                and isinstance(stored_pool_key[1], str)
                and type(stored_pool_key[2]) is int
            ):
                add(
                    self._connection_pools.get(
                        (stored_pool_key[0], stored_pool_key[1], stored_pool_key[2])
                    )
                )

            for pool in self._connection_pools.values():
                add(pool)
            for _fqid, pool in self._pending_startup_cleanup.values():
                add(pool)
            for lease in self._stream_owner_leases.values():
                add(lease.pool)

        return candidates

    async def release_connection(
        self,
        connector_id: str,
        handle: ConnectionHandle,
    ) -> None:
        """Release by the exact live pool owner, not caller-mutable handle metadata."""
        for pool in self._release_pool_candidates(handle):
            if not await pool._release_owned_handle(handle):
                continue

            with self._instance_lock:
                evicted_pools = self._trim_connection_pools_locked()
            for evicted_pool in evicted_pools:
                await evicted_pool.close_all()
            return

        logger.warning(
            "Connection pool owner not found for exact handle",
            connector_id=connector_id,
            session_id=handle.session_id,
        )

    def _config_fingerprint(self, config: ConnectionConfig) -> str:
        """Compute stable fingerprint for connection config."""
        payload = config.to_dict(redact=False)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return content_hash(payload_json, prefix=True)

    def claim_stream_owner(
        self,
        connector_id: str,
        dataset_id: str,
        partition_key: str,
        pool: ConnectionPool[SourceConnectorValue[Any]],
    ) -> _StreamOwnerLease | None:
        """Atomically reserve one logical key and bind its private pool."""
        fqid = self._resolve_id(connector_id)
        with self._instance_lock:
            if self._connectors.get(fqid) is None:
                raise ConnectorNotFoundError(
                    connector_id,
                    available=list(self._connectors.keys()),
                )
            if self._stream_owner_admissions_closed:
                return None
            key = (fqid, dataset_id, partition_key)
            if key in self._stream_owner_leases:
                return None
            lease = _StreamOwnerLease(
                fqid=fqid,
                dataset_id=dataset_id,
                partition_key=partition_key,
                pool=pool,
            )
            self._stream_owner_leases[key] = lease
            return lease

    def begin_stream_owner_start(
        self,
        lease: _StreamOwnerLease | None,
    ) -> _StreamOwnerStartup | None:
        """Fence a subscribe transition before it reaches its first await."""
        task = asyncio.current_task()
        if task is None or lease is None:
            return None
        with self._instance_lock:
            if (
                lease.invalidated
                or self._stream_owner_admissions_closed
                or self._stream_owner_leases.get(lease.key) is not lease
                or lease.startup is not None
            ):
                return None
            startup = _StreamOwnerStartup(task=task, loop=task.get_loop())
            lease.startup = startup
            return startup

    def claim_stream_owner_cleanup(
        self,
        lease: _StreamOwnerLease | None,
        startup: _StreamOwnerStartup | None,
    ) -> bool:
        """Choose whether startup or registry lifecycle owns failed-start cleanup."""
        if lease is None or startup is None:
            return True
        with self._instance_lock:
            if (
                lease.invalidated
                or self._stream_owner_leases.get(lease.key) is not lease
                or lease.startup is not startup
            ):
                return False
            startup.cleanup_started = True
            return True

    def stream_owner_is_invalidated(self, lease: _StreamOwnerLease | None) -> bool:
        """Return whether registry teardown owns this exact stream pool."""
        if lease is None:
            return False
        with self._instance_lock:
            return lease.invalidated

    def finish_stream_owner_start(
        self,
        lease: _StreamOwnerLease | None,
        startup: _StreamOwnerStartup | None,
    ) -> None:
        """Settle a start ticket only after its callback stopped touching the pool."""
        if lease is None or startup is None:
            return
        with self._instance_lock:
            if lease.startup is startup:
                lease.startup = None
            if not startup.completed.done():
                startup.completed.set_result(None)

    def commit_stream_owner_ready(
        self,
        lease: _StreamOwnerLease | None,
        startup: _StreamOwnerStartup | None,
    ) -> bool:
        """Commit a ready session only while the same registry lease is active."""
        if lease is None or startup is None:
            return lease is None
        with self._instance_lock:
            return (
                not lease.invalidated
                and not self._stream_owner_admissions_closed
                and self._stream_owner_leases.get(lease.key) is lease
                and lease.startup is startup
            )

    def owns_stream_owner(
        self,
        lease: _StreamOwnerLease | None,
        *,
        connector_id: str,
        dataset_id: str,
        partition_key: str,
        pool: ConnectionPool[SourceConnectorValue[Any]],
    ) -> bool:
        """Verify this registry still owns the exact key, lease, and pool."""
        if lease is None:
            return False
        try:
            fqid = self._resolve_id(connector_id)
        except ConnectorNotFoundError:
            return False
        key = (fqid, dataset_id, partition_key)
        with self._instance_lock:
            return (
                not lease.invalidated
                and not self._stream_owner_admissions_closed
                and lease.key == key
                and lease.pool is pool
                and self._stream_owner_leases.get(key) is lease
            )

    def release_stream_owner(self, lease: _StreamOwnerLease) -> None:
        """Release a logical owner only after its pool close has succeeded."""
        with self._instance_lock:
            if self._stream_owner_leases.get(lease.key) is not lease:
                return
            self._stream_owner_leases.pop(lease.key)
            if lease.pool is not None:
                pending = self._pending_startup_cleanup.get(id(lease.pool))
                if pending is not None and pending[1] is lease.pool:
                    self._pending_startup_cleanup.pop(id(lease.pool), None)

    def _current_pool_scope_locked(self) -> int:
        """Return the current event-loop pool scope.

        ``ConnectionPool`` contains ``asyncio.Lock``/``Semaphore`` instances, so
        sharing one pool across fresh event loops can raise "bound to a different
        event loop" under contention. The registry singleton is process-wide,
        therefore pool keys include a small stable id for the active loop.
        """
        loop = asyncio.get_running_loop()
        scope = self._loop_scope_ids.get(loop)
        if scope is None:
            scope = self._next_loop_scope_id
            self._next_loop_scope_id += 1
            self._loop_scope_ids[loop] = scope
        return scope

    def _get_connection_pool_locked(
        self,
        pool_key: tuple[str, str, int],
    ) -> ConnectionPool[SourceConnectorValue[Any]] | None:
        pool = self._connection_pools.get(pool_key)
        if pool is not None:
            self._connection_pools.move_to_end(pool_key)
        return pool

    def _store_connection_pool_locked(
        self,
        pool_key: tuple[str, str, int],
        pool: ConnectionPool[SourceConnectorValue[Any]],
    ) -> list[ConnectionPool[SourceConnectorValue[Any]]]:
        self._connection_pools[pool_key] = pool
        self._connection_pools.move_to_end(pool_key)
        return self._trim_connection_pools_locked()

    def _trim_connection_pools_locked(
        self,
    ) -> list[ConnectionPool[SourceConnectorValue[Any]]]:
        evicted: list[ConnectionPool[SourceConnectorValue[Any]]] = []
        attempts = len(self._connection_pools)
        while len(self._connection_pools) > self._max_connection_pools and attempts > 0:
            attempts -= 1
            evicted_key, evicted_pool = self._connection_pools.popitem(last=False)
            if evicted_pool.get_stats().in_use_connections > 0:
                self._connection_pools[evicted_key] = evicted_pool
                self._connection_pools.move_to_end(evicted_key)
                continue
            self._pending_startup_cleanup[id(evicted_pool)] = (evicted_key[0], evicted_pool)
            evicted.append(evicted_pool)
        return evicted

    # =========================================================================
    # Health Tracking
    # =========================================================================

    def update_health(
        self,
        connector_id: str,
        health: HealthStatus,
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

            entry.last_health_check = datetime.now(UTC)
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
            count = len({entry.fqid for entry in self._connectors.find("capability", cap)})
            if count > 0 and cap.name is not None:
                cap_dist[cap.name] = count

        loaded_count = sum(1 for e in self._connectors.values() if e.loaded)

        return RegistryStats(
            registered_connectors=self._connectors.count,
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
        return self._connectors.count

    def __iter__(self) -> Iterator[str]:
        """Iterate over registered connector FQIDs."""
        return iter(sorted(self._connectors.keys()))

    def __contains__(self, connector_id: str) -> bool:
        """Check if connector is registered."""
        return self.has(connector_id)
