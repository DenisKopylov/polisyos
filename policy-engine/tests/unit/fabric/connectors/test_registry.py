"""Comprehensive tests for Phase 2.2: Registry Architecture & Lazy Loading."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest

from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
    SourceConnectorInstance,
    SourceConnectorValue,
)
from polisyos.fabric.connectors.discovery import ConnectorDiscovery
from polisyos.fabric.connectors.pool import (
    ConnectionPool,
    PoolClosedError,
    PoolConfig,
    PoolExhaustedError,
)
from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.connectors.registry import (
    AmbiguousConnectorError,
    ConnectorAlreadyRegisteredError,
    ConnectorConfigError,
    ConnectorEntry,
    ConnectorNotFoundError,
    ConnectorPreferences,
    ConnectorRegistry,
)
from polisyos.fabric.connectors.types import (
    DataChunk,
    DatasetDescriptor,
    FreshnessResult,
    FreshnessStatus,
    ValidationResult,
)
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    build_live_execution_authorization,
)
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)

# =============================================================================
# Test Fixtures: Mock Connectors
# =============================================================================


class MockConnectorA(BaseConnector[list[dict]]):
    """Mock connector with FULL_FETCH and STREAMING capabilities."""

    connector_id: ClassVar[str] = "mock_a"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH | ConnectorCapability.STREAMING
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="mock_a",
        version="1.0.0",
        namespace="test.mock",
        source_name="Mock Source A",
        source_organization="Test Org",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.STREAMING,
        ),
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True, message="OK")

    async def fetch(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> FetchResult[list[dict]]:
        return FetchResult(
            data=[{"mock": "data"}],
            row_count=1,
            schema_id="test.schema",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=datetime.now(UTC).isoformat(),
                timestamp=datetime.now(UTC),
            ),
            fetched_at=datetime.now(UTC),
            completeness=1.0,
        )

    async def fetch_stream(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> AsyncIterator[DataChunk[list[dict]]]:
        del handle, request
        yield DataChunk(data=[{"mock": "stream"}], chunk_index=0, row_count=1)

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        return ValidationResult.success()


class _Net01LifecycleConnector(MockConnectorA):
    """Connector with deterministic disconnect gates for NET-01 ownership probes."""

    def __init__(
        self,
        *,
        disconnect_failures: int = 0,
        block_disconnect: bool = False,
        block_health_check: bool = False,
    ) -> None:
        self.disconnect_failures = disconnect_failures
        self.disconnect_calls: list[str] = []
        self.disconnect_started = asyncio.Event()
        self.allow_disconnect = asyncio.Event()
        if not block_disconnect:
            self.allow_disconnect.set()
        self.health_check_started = asyncio.Event()
        self.allow_health_check = asyncio.Event()
        if not block_health_check:
            self.allow_health_check.set()

    async def disconnect(self, handle: ConnectionHandle) -> None:
        self.disconnect_calls.append(handle.session_id)
        self.disconnect_started.set()
        if self.disconnect_failures:
            self.disconnect_failures -= 1
            raise RuntimeError("controlled disconnect failure")
        await self.allow_disconnect.wait()

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        self.health_check_started.set()
        await self.allow_health_check.wait()
        return await super().health_check(handle)


class _Net01ConnectGateConnector(MockConnectorA):
    """Connector that pauses after a pool permit is reserved."""

    def __init__(self) -> None:
        self.connect_started = asyncio.Event()
        self.allow_connect = asyncio.Event()

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        self.connect_started.set()
        await self.allow_connect.wait()
        return self._create_handle(config)


class MockConnectorA_v10(BaseConnector[list[dict]]):
    """Mock connector with higher semver version."""

    connector_id: ClassVar[str] = "mock_a"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="mock_a",
        version="10.0.0",
        namespace="test.mock",
        source_name="Mock Source A v10",
        source_organization="Test Org",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True, message="OK")

    async def fetch(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> FetchResult[list[dict]]:
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="test.schema",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=datetime.now(UTC).isoformat(),
                timestamp=datetime.now(UTC),
            ),
            fetched_at=datetime.now(UTC),
            completeness=1.0,
        )

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        return ValidationResult.success()


class MockConnectorB(BaseConnector[list[dict]]):
    """Mock connector with CATALOG_BROWSE capability."""

    connector_id: ClassVar[str] = "mock_b"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH | ConnectorCapability.CATALOG_BROWSE
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="mock_b",
        version="1.0.0",
        namespace="test.mock",
        source_name="Mock Source B",
        source_organization="Test Org",
        trust_level=TrustLevel.HIGH,
        quality_tier=QualityTier.GOLD,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CATALOG_BROWSE,
        ),
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True, message="OK")

    async def fetch(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> FetchResult[list[dict]]:
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="test",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=datetime.now(UTC).isoformat(),
                timestamp=datetime.now(UTC),
            ),
            fetched_at=datetime.now(UTC),
            completeness=1.0,
        )

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        yield DatasetDescriptor(
            dataset_id="test.dataset",
            name="Test Dataset",
            description="A test dataset",
        )

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        return ValidationResult.success()


class MockConnectorC(BaseConnector[list[dict]]):
    """Mock connector with HIGH trust in different namespace."""

    connector_id: ClassVar[str] = "mock_c"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.STREAMING
        | ConnectorCapability.FRESHNESS_CHECK
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="mock_c",
        version="2.0.0",
        namespace="production.data",
        source_name="Mock Source C",
        source_organization="Prod Org",
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.PLATINUM,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.STREAMING,
            ConnectorCapability.FRESHNESS_CHECK,
        ),
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True, message="OK")

    async def fetch(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> FetchResult[list[dict]]:
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="test",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=datetime.now(UTC).isoformat(),
                timestamp=datetime.now(UTC),
            ),
            fetched_at=datetime.now(UTC),
            completeness=1.0,
        )

    async def check_freshness(
        self, handle: ConnectionHandle, dataset_id: str, cached_version: DataVersion
    ) -> FreshnessResult:
        del handle, dataset_id, cached_version
        return FreshnessResult(status=FreshnessStatus.FRESH)

    async def fetch_stream(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> AsyncIterator[DataChunk[list[dict]]]:
        del handle, request
        yield DataChunk(data=[], chunk_index=0, row_count=0)

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        return ValidationResult.success()


@pytest.fixture
def sample_config() -> ConnectionConfig:
    """Sample connection configuration."""
    return ConnectionConfig(
        url="https://api.example.com/v1",
        headers={"User-Agent": "PolicyOS/Test"},
        timeout_seconds=30,
    )


@pytest.fixture
def alt_config() -> ConnectionConfig:
    return ConnectionConfig(
        url="https://api.alt.example.com/v2",
        headers={"User-Agent": "PolicyOS/Test"},
        timeout_seconds=30,
    )


@pytest.fixture
def registry() -> ConnectorRegistry:
    """Fresh registry instance for testing (not singleton)."""
    ConnectorRegistry.reset_instance()
    # Create instance without bootstrap to avoid loading real connectors
    return ConnectorRegistry.get_instance(bootstrap=False)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before and after each test."""
    ConnectorRegistry.reset_instance()
    ConnectorDiscovery.reset()
    yield
    ConnectorRegistry.reset_instance()
    ConnectorDiscovery.reset()


# =============================================================================
# ConnectorRegistry: Singleton Tests
# =============================================================================


class TestRegistrySingleton:
    """Test singleton pattern implementation."""

    def test_get_instance_returns_same_object(self) -> None:
        """Verify singleton returns same instance."""
        registry1 = ConnectorRegistry.get_instance(bootstrap=False)
        registry2 = ConnectorRegistry.get_instance(bootstrap=False)

        assert registry1 is registry2

    def test_reset_instance_creates_new_object(self) -> None:
        """Verify reset creates new instance."""
        registry1 = ConnectorRegistry.get_instance(bootstrap=False)
        registry1.register(MockConnectorA)

        ConnectorRegistry.reset_instance()

        registry2 = ConnectorRegistry.get_instance(bootstrap=False)
        assert registry2 is not registry1
        assert len(registry2) == 0

    def test_thread_safe_initialization(self) -> None:
        """Verify thread-safe singleton initialization."""
        instances: list[ConnectorRegistry] = []
        errors: list[Exception] = []

        def get_registry() -> None:
            try:
                instance = ConnectorRegistry.get_instance(bootstrap=False)
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_registry) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(instances) == 10
        assert all(inst is instances[0] for inst in instances)

    def test_public_get_registry_uses_default_helper(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from polisyos.fabric import connectors as connectors_module

        sentinel = object()
        monkeypatch.setattr(
            connectors_module,
            "_default_connector_registry",
            lambda: sentinel,
        )

        assert connectors_module.get_registry() is sentinel


# =============================================================================
# ConnectorRegistry: Registration Tests
# =============================================================================


class TestRegistryRegistration:
    """Test connector registration functionality."""

    def test_register_valid_connector(self, registry: ConnectorRegistry) -> None:
        """Register a valid connector class."""
        fqid = registry.register(MockConnectorA)

        assert fqid == "test.mock.mock_a@1.0.0"
        assert registry.has("mock_a")
        assert len(registry) == 1

    def test_register_multiple_connectors(self, registry: ConnectorRegistry) -> None:
        """Register multiple connectors."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)
        registry.register(MockConnectorC)

        assert len(registry) == 3
        assert registry.has("mock_a")
        assert registry.has("mock_b")
        assert registry.has("mock_c")

    def test_register_duplicate_raises_error(self, registry: ConnectorRegistry) -> None:
        """Duplicate registration without override raises error."""
        registry.register(MockConnectorA)

        with pytest.raises(ConnectorAlreadyRegisteredError) as exc_info:
            registry.register(MockConnectorA)

        assert "already registered" in str(exc_info.value)

    def test_register_with_override(self, registry: ConnectorRegistry) -> None:
        """Override allows re-registration."""
        registry.register(MockConnectorA)
        fqid = registry.register(MockConnectorA, override=True)

        assert fqid == "test.mock.mock_a@1.0.0"
        assert len(registry) == 1

    def test_register_with_default_config(
        self, registry: ConnectorRegistry, sample_config: ConnectionConfig
    ) -> None:
        """Register with default configuration."""
        registry.register(MockConnectorA, config=sample_config)

        entry = registry.get_entry("mock_a")
        assert entry.default_config == sample_config

    def test_register_with_factory(self, registry: ConnectorRegistry) -> None:
        """Register with a custom factory for DI."""
        calls = {"count": 0}

        def factory() -> MockConnectorA:
            calls["count"] += 1
            return MockConnectorA()

        registry.register(MockConnectorA, factory=factory)

        registry.get("mock_a")
        registry.get("mock_a")

        assert calls["count"] == 1

    def test_unregister_connector(self, registry: ConnectorRegistry) -> None:
        """Unregister removes connector from registry."""
        registry.register(MockConnectorA)
        assert registry.has("mock_a")

        result = registry.unregister("mock_a")

        assert result is True
        assert not registry.has("mock_a")
        assert len(registry) == 0

    def test_unregister_nonexistent_returns_false(self, registry: ConnectorRegistry) -> None:
        """Unregister unknown connector returns False."""
        result = registry.unregister("nonexistent")
        assert result is False


# =============================================================================
# ConnectorRegistry: O(1) Lookup Tests
# =============================================================================


class TestRegistryLookup:
    """Test O(1) connector retrieval."""

    def test_get_by_fqid(self, registry: ConnectorRegistry) -> None:
        """Get connector by fully qualified ID."""
        registry.register(MockConnectorA)

        connector = registry.get("test.mock.mock_a@1.0.0")

        assert isinstance(connector, MockConnectorA)
        assert isinstance(connector, SourceConnectorInstance)

    def test_get_by_short_id(self, registry: ConnectorRegistry) -> None:
        """Get connector by short ID (fuzzy match)."""
        registry.register(MockConnectorA)

        connector = registry.get("mock_a")

        assert isinstance(connector, MockConnectorA)

    def test_get_by_namespace_id(self, registry: ConnectorRegistry) -> None:
        """Get connector by namespace.id format."""
        registry.register(MockConnectorA)

        connector = registry.get("test.mock.mock_a")

        assert isinstance(connector, MockConnectorA)

    def test_get_latest_version_by_short_id(self, registry: ConnectorRegistry) -> None:
        """Short ID returns latest semver version."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorA_v10)

        metadata = registry.get_metadata("test.mock.mock_a")

        assert metadata.version == "10.0.0"

    def test_get_ambiguous_raises_error(self, registry: ConnectorRegistry) -> None:
        """Ambiguous short ID raises error when multiple matches exist."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)

        with pytest.raises(AmbiguousConnectorError):
            registry.get("mock")

    def test_get_nonexistent_raises_error(self, registry: ConnectorRegistry) -> None:
        """Get unknown connector raises error."""
        registry.register(MockConnectorA)

        with pytest.raises(ConnectorNotFoundError) as exc_info:
            registry.get("nonexistent")

        assert "not found" in str(exc_info.value)

    def test_lazy_loading_cache(self, registry: ConnectorRegistry) -> None:
        """Connector is cached after first instantiation."""
        registry.register(MockConnectorA)
        entry = registry.get_entry("mock_a")

        assert entry.loaded is False
        assert entry.instance is None

        connector1 = registry.get("mock_a")
        connector2 = registry.get("mock_a")

        assert entry.loaded is True
        assert connector1 is connector2

    def test_get_metadata_without_instantiation(self, registry: ConnectorRegistry) -> None:
        """get_metadata() doesn't trigger instantiation."""
        registry.register(MockConnectorA)

        metadata = registry.get_metadata("mock_a")
        entry = registry.get_entry("mock_a")

        assert metadata.connector_id == "mock_a"
        assert entry.loaded is False


# =============================================================================
# ConnectorRegistry: Query Tests (Secondary Indices)
# =============================================================================


class TestRegistryQueries:
    """Test capability-based queries using secondary indices."""

    def test_query_by_capability_streaming(self, registry: ConnectorRegistry) -> None:
        """Query connectors with STREAMING capability."""
        registry.register(MockConnectorA)  # Has STREAMING
        registry.register(MockConnectorB)  # No STREAMING
        registry.register(MockConnectorC)  # Has STREAMING

        results = list(registry.query(capabilities=ConnectorCapability.STREAMING))

        assert len(results) == 2
        ids = {r.connector_id for r in results}
        assert ids == {"mock_a", "mock_c"}

    def test_query_by_capability_catalog_browse(self, registry: ConnectorRegistry) -> None:
        """Query connectors with CATALOG_BROWSE capability."""
        registry.register(MockConnectorA)  # No CATALOG_BROWSE
        registry.register(MockConnectorB)  # Has CATALOG_BROWSE
        registry.register(MockConnectorC)  # No CATALOG_BROWSE

        results = list(registry.query(capabilities=ConnectorCapability.CATALOG_BROWSE))

        assert len(results) == 1
        assert results[0].connector_id == "mock_b"

    def test_query_by_multiple_capabilities(self, registry: ConnectorRegistry) -> None:
        """Query requiring multiple capabilities (AND logic)."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)
        registry.register(MockConnectorC)

        # Only MockConnectorC has both STREAMING and FRESHNESS_CHECK
        caps = ConnectorCapability.STREAMING | ConnectorCapability.FRESHNESS_CHECK
        results = list(registry.query(capabilities=caps))

        assert len(results) == 1
        assert results[0].connector_id == "mock_c"

    def test_query_by_namespace(self, registry: ConnectorRegistry) -> None:
        """Query connectors in specific namespace."""
        registry.register(MockConnectorA)  # test.mock
        registry.register(MockConnectorB)  # test.mock
        registry.register(MockConnectorC)  # production.data

        results = list(registry.query(namespace="test.mock"))

        assert len(results) == 2
        ids = {r.connector_id for r in results}
        assert ids == {"mock_a", "mock_b"}

    def test_query_by_trust_level_min(self, registry: ConnectorRegistry) -> None:
        """Query connectors with minimum trust level."""
        registry.register(MockConnectorA)  # MEDIUM
        registry.register(MockConnectorB)  # HIGH
        registry.register(MockConnectorC)  # AUTHORITATIVE

        results = list(registry.query(trust_level_min=TrustLevel.HIGH))

        assert len(results) == 2
        ids = {r.connector_id for r in results}
        assert ids == {"mock_b", "mock_c"}

    def test_query_combined_filters(self, registry: ConnectorRegistry) -> None:
        """Query with multiple filter criteria (AND)."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)
        registry.register(MockConnectorC)

        # STREAMING capability + HIGH trust minimum
        results = list(
            registry.query(
                capabilities=ConnectorCapability.STREAMING,
                trust_level_min=TrustLevel.HIGH,
            )
        )

        # Only MockConnectorC has STREAMING and AUTHORITATIVE trust
        assert len(results) == 1
        assert results[0].connector_id == "mock_c"

    def test_query_returns_deterministic_order(self, registry: ConnectorRegistry) -> None:
        """Query results are in deterministic order."""
        # Register in random order
        registry.register(MockConnectorC)
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)

        results1 = [r.fully_qualified_id for r in registry.query()]
        results2 = [r.fully_qualified_id for r in registry.query()]

        assert results1 == results2
        assert results1 == sorted(results1)

    def test_list_namespaces(self, registry: ConnectorRegistry) -> None:
        """List all registered namespaces."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)
        registry.register(MockConnectorC)

        namespaces = registry.list_namespaces()

        assert set(namespaces) == {"test.mock", "production.data"}

    def test_list_by_namespace(self, registry: ConnectorRegistry) -> None:
        """List connectors in specific namespace."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)
        registry.register(MockConnectorC)

        connectors = registry.list_by_namespace("test.mock")

        assert len(connectors) == 2


# =============================================================================
# ConnectorRegistry: Dataset Resolution Tests
# =============================================================================


class TestDatasetResolution:
    """Test connector scoring for dataset resolution."""

    def test_find_connectors_basic(self, registry: ConnectorRegistry) -> None:
        """Find connectors for a dataset pattern."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)

        entry_a = registry.get_entry("mock_a")
        entry_b = registry.get_entry("mock_b")
        entry_a.known_datasets = frozenset({"any_dataset"})
        entry_b.known_datasets = frozenset({"any_dataset"})

        results = registry.find_connectors_for_dataset("any_dataset")

        assert len(results) == 2
        assert all(isinstance(r[1], float) for r in results)

    def test_find_connectors_requires_catalog(self, registry: ConnectorRegistry) -> None:
        """Without known datasets, requires CATALOG_BROWSE capability."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)

        results = registry.find_connectors_for_dataset("unknown_dataset")

        # Only MockConnectorB has CATALOG_BROWSE
        assert len(results) == 1
        assert results[0][0].connector_id == "mock_b"

    def test_find_connectors_respects_trust_minimum(self, registry: ConnectorRegistry) -> None:
        """Dataset resolution respects minimum trust level."""
        registry.register(MockConnectorA)  # MEDIUM
        registry.register(MockConnectorB)  # HIGH

        entry_a = registry.get_entry("mock_a")
        entry_b = registry.get_entry("mock_b")
        entry_a.known_datasets = frozenset({"dataset"})
        entry_b.known_datasets = frozenset({"dataset"})

        prefs = ConnectorPreferences(min_trust_level=TrustLevel.HIGH)
        results = registry.find_connectors_for_dataset("dataset", preferences=prefs)

        assert len(results) == 1
        assert results[0][0].connector_id == "mock_b"

    def test_find_connectors_excludes_specified(self, registry: ConnectorRegistry) -> None:
        """Dataset resolution excludes specified connectors."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)

        entry_a = registry.get_entry("mock_a")
        entry_b = registry.get_entry("mock_b")
        entry_a.known_datasets = frozenset({"dataset"})
        entry_b.known_datasets = frozenset({"dataset"})

        prefs = ConnectorPreferences(excluded_connectors={"test.mock.mock_a@1.0.0"})
        results = registry.find_connectors_for_dataset("dataset", preferences=prefs)

        assert len(results) == 1
        assert results[0][0].connector_id == "mock_b"

    def test_find_connectors_sorted_by_score(self, registry: ConnectorRegistry) -> None:
        """Results are sorted by relevance score (descending)."""
        registry.register(MockConnectorA)  # MEDIUM trust
        registry.register(MockConnectorC)  # AUTHORITATIVE trust

        entry_a = registry.get_entry("mock_a")
        entry_c = registry.get_entry("mock_c")
        entry_a.known_datasets = frozenset({"dataset"})
        entry_c.known_datasets = frozenset({"dataset"})

        results = registry.find_connectors_for_dataset("dataset")

        # Higher trust = higher score, so C should be first
        assert results[0][0].connector_id == "mock_c"
        assert results[0][1] >= results[1][1]


# =============================================================================
# ConnectorRegistry: Statistics Tests
# =============================================================================


class TestRegistryStats:
    """Test registry statistics and observability."""

    def test_stats_after_registration(self, registry: ConnectorRegistry) -> None:
        """Stats reflect registration count."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)

        stats = registry.stats

        assert stats.registered_connectors == 2
        assert stats.registrations_total == 2
        assert stats.loaded_connectors == 0

    def test_stats_after_get(self, registry: ConnectorRegistry) -> None:
        """Stats reflect get calls and loaded connectors."""
        registry.register(MockConnectorA)
        registry.get("mock_a")

        stats = registry.stats

        assert stats.loaded_connectors == 1
        assert stats.get_calls_total == 1

    def test_stats_after_query(self, registry: ConnectorRegistry) -> None:
        """Stats reflect query calls."""
        registry.register(MockConnectorA)
        list(registry.query())
        list(registry.query(capabilities=ConnectorCapability.STREAMING))

        stats = registry.stats

        assert stats.queries_total == 2

    def test_capabilities_distribution(self, registry: ConnectorRegistry) -> None:
        """Stats include capabilities distribution."""
        registry.register(MockConnectorA)  # FULL_FETCH, STREAMING
        registry.register(MockConnectorB)  # FULL_FETCH, CATALOG_BROWSE

        stats = registry.stats

        assert "FULL_FETCH" in stats.capabilities_distribution
        assert stats.capabilities_distribution["FULL_FETCH"] == 2
        assert stats.capabilities_distribution["STREAMING"] == 1


# =============================================================================
# ConnectionPool Tests
# =============================================================================


class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.fixture
    def pool_config(self) -> PoolConfig:
        return PoolConfig(max_size=3, acquire_timeout_seconds=1.0)

    @pytest.fixture
    def mock_connector_factory(self):
        def factory() -> MockConnectorA:
            return MockConnectorA()

        return factory

    def test_acquire_creates_connection(
        self,
        mock_connector_factory,
        sample_config: ConnectionConfig,
        pool_config: PoolConfig,
    ) -> None:
        """Acquire creates new connection when pool is empty."""

        async def _run() -> None:
            pool = ConnectionPool(
                connector_factory=mock_connector_factory,
                config=sample_config,
                pool_config=pool_config,
            )

            handle = await pool.acquire()

            assert handle is not None
            assert handle.connector_id == "mock_a"

            await pool.close_all()

        asyncio.run(_run())

    def test_release_returns_to_pool(
        self,
        mock_connector_factory,
        sample_config: ConnectionConfig,
        pool_config: PoolConfig,
    ) -> None:
        """Release returns connection to pool for reuse."""

        async def _run() -> None:
            pool = ConnectionPool(
                connector_factory=mock_connector_factory,
                config=sample_config,
                pool_config=pool_config,
            )

            handle1 = await pool.acquire()
            session_id1 = handle1.session_id
            await pool.release(handle1)

            handle2 = await pool.acquire()

            # Should reuse the same connection
            assert handle2.session_id == session_id1

            await pool.close_all()

        asyncio.run(_run())

    def test_pool_respects_max_size(
        self, mock_connector_factory, sample_config: ConnectionConfig
    ) -> None:
        """Pool respects maximum size configuration."""

        async def _run() -> None:
            pool = ConnectionPool(
                connector_factory=mock_connector_factory,
                config=sample_config,
                pool_config=PoolConfig(max_size=2, acquire_timeout_seconds=0.1),
            )

            handle1 = await pool.acquire()
            handle2 = await pool.acquire()

            # Third acquire should timeout
            with pytest.raises(PoolExhaustedError):
                await pool.acquire()

            await pool.release(handle1)
            await pool.release(handle2)
            await pool.close_all()

        asyncio.run(_run())

    def test_close_all_prevents_further_use(
        self,
        mock_connector_factory,
        sample_config: ConnectionConfig,
        pool_config: PoolConfig,
    ) -> None:
        """Closed pool raises error on acquire."""

        async def _run() -> None:
            pool = ConnectionPool(
                connector_factory=mock_connector_factory,
                config=sample_config,
                pool_config=pool_config,
            )

            await pool.close_all()

            with pytest.raises(PoolClosedError):
                await pool.acquire()

        asyncio.run(_run())

    def test_pool_stats(
        self,
        mock_connector_factory,
        sample_config: ConnectionConfig,
        pool_config: PoolConfig,
    ) -> None:
        """Pool tracks statistics."""

        async def _run() -> None:
            pool = ConnectionPool(
                connector_factory=mock_connector_factory,
                config=sample_config,
                pool_config=pool_config,
            )

            handle = await pool.acquire()
            await pool.release(handle)

            stats = pool.get_stats()

            assert stats.total_acquires == 1
            assert stats.total_releases == 1
            assert stats.total_creates == 1
            assert stats.idle_connections == 1
            assert stats.in_use_connections == 0

            await pool.close_all()

        asyncio.run(_run())

    def test_context_manager(
        self,
        mock_connector_factory,
        sample_config: ConnectionConfig,
        pool_config: PoolConfig,
    ) -> None:
        """Connection context manager releases on exit."""

        async def _run() -> None:
            pool = ConnectionPool(
                connector_factory=mock_connector_factory,
                config=sample_config,
                pool_config=pool_config,
            )

            async with await pool.connection() as handle:
                assert handle is not None
                stats = pool.get_stats()
                assert stats.in_use_connections == 1

            stats = pool.get_stats()
            assert stats.in_use_connections == 0
            assert stats.idle_connections == 1

            await pool.close_all()

        asyncio.run(_run())

    def test_release_is_idempotent_per_handle(
        self,
        mock_connector_factory,
        sample_config: ConnectionConfig,
    ) -> None:
        """Double release cannot over-release the pool semaphore."""

        async def _run() -> None:
            pool = ConnectionPool(
                connector_factory=mock_connector_factory,
                config=sample_config,
                pool_config=PoolConfig(max_size=1, acquire_timeout_seconds=0.1),
            )

            handle = await pool.acquire()
            await pool.release(handle)
            await pool.release(handle)

            next_handle = await pool.acquire()
            with pytest.raises(PoolExhaustedError):
                await pool.acquire()

            await pool.release(next_handle)
            await pool.close_all()

        asyncio.run(_run())

    def test_net01_failed_disconnect_retains_owner_until_retry(
        self,
        sample_config: ConnectionConfig,
    ) -> None:
        """A failed retirement keeps the physical owner and permit together."""

        async def _run() -> None:
            connector = _Net01LifecycleConnector(disconnect_failures=1)
            pool = ConnectionPool(
                connector_factory=lambda: connector,
                config=sample_config,
                pool_config=PoolConfig(
                    max_size=1,
                    max_connection_uses=1,
                    validate_on_acquire=False,
                    acquire_timeout_seconds=0.02,
                ),
            )
            handle = await pool.acquire()
            with suppress(RuntimeError):
                await pool.release(handle)

            assert connector.disconnect_calls == [handle.session_id]
            with pytest.raises(PoolExhaustedError):
                await pool.acquire()

            await pool.release(handle)
            assert connector.disconnect_calls == [handle.session_id, handle.session_id]

            replacement = await pool.acquire()
            assert replacement.session_id != handle.session_id
            await pool.release(replacement)
            await pool.close_all()

        asyncio.run(_run())

    def test_net01_cancelled_disconnect_keeps_same_owner_until_cleanup(
        self,
        sample_config: ConnectionConfig,
    ) -> None:
        """Cancellation during disconnect cannot free a slot for a replacement."""

        async def _run() -> None:
            connector = _Net01LifecycleConnector(block_disconnect=True)
            pool = ConnectionPool(
                connector_factory=lambda: connector,
                config=sample_config,
                pool_config=PoolConfig(
                    max_size=1,
                    max_connection_uses=1,
                    validate_on_acquire=False,
                    acquire_timeout_seconds=0.02,
                ),
            )
            handle = await pool.acquire()
            release_task = asyncio.create_task(pool.release(handle))
            await connector.disconnect_started.wait()
            release_task.cancel()
            await asyncio.sleep(0)
            with pytest.raises(PoolExhaustedError):
                await pool.acquire()

            connector.allow_disconnect.set()
            with pytest.raises(asyncio.CancelledError):
                await release_task

            with suppress(RuntimeError):
                await pool.release(handle)
            replacement = await pool.acquire()
            assert replacement.session_id != handle.session_id
            assert set(connector.disconnect_calls) == {handle.session_id}
            await pool.release(replacement)
            await pool.close_all()

        asyncio.run(_run())

    def test_net01_concurrent_release_returns_one_permit_and_disconnect(
        self,
        sample_config: ConnectionConfig,
    ) -> None:
        """Concurrent release callers share one validated owner transition and permit."""

        async def _run() -> None:
            connector = _Net01LifecycleConnector(block_health_check=True)
            pool = ConnectionPool(
                connector_factory=lambda: connector,
                config=sample_config,
                pool_config=PoolConfig(
                    max_size=1,
                    max_connection_uses=10,
                    validate_on_acquire=False,
                    validate_on_release=True,
                    acquire_timeout_seconds=0.02,
                ),
            )
            handle = await pool.acquire()
            first = asyncio.create_task(pool.release(handle))
            await connector.health_check_started.wait()
            second = asyncio.create_task(pool.release(handle))
            await asyncio.sleep(0)
            assert handle.session_id in pool._pending_cleanup
            connector.allow_health_check.set()
            results = await asyncio.gather(first, second, return_exceptions=True)
            assert all(not isinstance(result, BaseException) for result in results)
            assert pool.get_stats().idle_connections == 1

            replacement = await pool.acquire()
            await pool.release(replacement)
            await pool.close_all()

        asyncio.run(_run())

    def test_net01_closed_pool_acquire_rejects_while_cleanup_pending(
        self,
        sample_config: ConnectionConfig,
    ) -> None:
        """A closed pool rejects new acquire before waiting on a pending permit."""

        async def _run() -> None:
            connector = _Net01LifecycleConnector(block_disconnect=True)
            pool = ConnectionPool(
                connector_factory=lambda: connector,
                config=sample_config,
                pool_config=PoolConfig(
                    max_size=1,
                    max_connection_uses=1,
                    validate_on_acquire=False,
                    acquire_timeout_seconds=0.02,
                ),
            )
            handle = await pool.acquire()
            release_task = asyncio.create_task(pool.release(handle))
            await connector.disconnect_started.wait()
            close_task = asyncio.create_task(pool.close_all())
            await asyncio.sleep(0)
            with pytest.raises(PoolClosedError):
                await pool.acquire()

            connector.allow_disconnect.set()
            await asyncio.gather(release_task, close_task)

        asyncio.run(_run())

    def test_net01_cancelled_connect_releases_reserved_permit(
        self,
        sample_config: ConnectionConfig,
    ) -> None:
        """Cancellation during connector I/O cannot strand the reserved slot."""

        async def _run() -> None:
            connector = _Net01ConnectGateConnector()
            pool = ConnectionPool(
                connector_factory=lambda: connector,
                config=sample_config,
                pool_config=PoolConfig(max_size=1, acquire_timeout_seconds=0.02),
            )
            acquire_task = asyncio.create_task(pool.acquire())
            await connector.connect_started.wait()
            acquire_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await acquire_task

            connector.allow_connect.set()
            replacement = await pool.acquire()
            await pool.release(replacement)
            await pool.close_all()

        asyncio.run(_run())

    def test_net01_close_all_waits_for_pending_release_owner(
        self,
        sample_config: ConnectionConfig,
    ) -> None:
        """close_all cannot report completion while a release cleanup is pending."""

        async def _run() -> None:
            connector = _Net01LifecycleConnector(block_disconnect=True)
            pool = ConnectionPool(
                connector_factory=lambda: connector,
                config=sample_config,
                pool_config=PoolConfig(
                    max_size=1,
                    max_connection_uses=1,
                    validate_on_acquire=False,
                    acquire_timeout_seconds=0.02,
                ),
            )
            handle = await pool.acquire()
            release_task = asyncio.create_task(pool.release(handle))
            await connector.disconnect_started.wait()
            close_task = asyncio.create_task(pool.close_all())
            await asyncio.sleep(0)
            assert not close_task.done()

            connector.allow_disconnect.set()
            await asyncio.gather(release_task, close_task)
            assert connector.disconnect_calls == [handle.session_id]
            with pytest.raises(PoolClosedError):
                await pool.acquire()

        asyncio.run(_run())


# =============================================================================
# Discovery Tests
# =============================================================================


class TestConnectorDiscovery:
    """Test connector discovery mechanisms."""

    def test_discovery_singleton(self) -> None:
        """Discovery is a singleton."""
        d1 = ConnectorDiscovery()
        d2 = ConnectorDiscovery()

        assert d1 is d2

    def test_discover_tracks_errors(self) -> None:
        """Discovery tracks errors for invalid modules."""
        discovery = ConnectorDiscovery()
        discovery.add_module("nonexistent.module.path")

        list(discovery.discover_all())

        errors = discovery.errors
        assert len(errors) > 0
        assert any("nonexistent" in e.module_path for e in errors)

    def test_add_explicit_module(self) -> None:
        """Can add explicit module for discovery."""
        discovery = ConnectorDiscovery()
        discovery.add_module("polisyos.fabric.connectors.base")

        # Should not raise
        list(discovery.discover_all())

    def test_discovery_reset(self) -> None:
        """Reset clears singleton."""
        d1 = ConnectorDiscovery()
        d1.add_module("test.module")

        ConnectorDiscovery.reset()

        d2 = ConnectorDiscovery()
        assert d2 is not d1
        assert len(d2._additional_modules) == 0

    def test_discovery_singleton_is_thread_safe(self) -> None:
        ConnectorDiscovery.reset()
        instances: list[ConnectorDiscovery] = []
        errors: list[BaseException] = []
        gate = threading.Barrier(8)

        def _build() -> None:
            try:
                gate.wait()
                instances.append(ConnectorDiscovery())
            except BaseException as exc:  # pragma: no cover - test helper
                errors.append(exc)

        threads = [threading.Thread(target=_build) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert len({id(instance) for instance in instances}) == 1

    def test_registry_get_does_not_double_wrap_fetch_under_concurrency(
        self,
        registry: ConnectorRegistry,
    ) -> None:
        registry.register(MockConnectorA)
        connectors: list[SourceConnectorInstance[object]] = []
        errors: list[BaseException] = []
        gate = threading.Barrier(8)

        def _get_connector() -> None:
            try:
                gate.wait()
                connector = registry.get("mock_a")
                assert isinstance(connector, SourceConnectorInstance)
                connectors.append(connector)
            except BaseException as exc:  # pragma: no cover - test helper
                errors.append(exc)

        threads = [threading.Thread(target=_get_connector) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert len({id(connector) for connector in connectors}) == 1

        wrapped_depth = 0
        fetch = connectors[0].fetch
        while hasattr(fetch, "__wrapped__"):
            wrapped_depth += 1
            fetch = fetch.__wrapped__  # type: ignore[attr-defined]
        assert wrapped_depth == 1


# =============================================================================
# Integration Tests
# =============================================================================


class TestRegistryIntegration:
    """Integration tests for registry with pools."""

    def test_ordinary_registry_leases_keep_active_validation_on_create_and_reuse(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """Without a journal permit, both new and reused handles stay actively checked."""

        class _CountingHealthConnector(MockConnectorA):
            def __init__(self) -> None:
                self.health_check_count = 0

            async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
                self.health_check_count += 1
                return HealthStatus(healthy=True, message="counted")

        connector = _CountingHealthConnector()

        async def _run() -> None:
            registry.register(
                _CountingHealthConnector,
                config=sample_config,
                factory=lambda: connector,
            )
            first = await registry.get_connection("mock_a")
            assert connector.health_check_count == 1
            await registry.release_connection("mock_a", first)

            pool = next(iter(registry._connection_pools.values()))
            pool._config.health_check_interval_seconds = 0.0
            second = await registry.get_connection("mock_a")
            assert second.session_id == first.session_id
            assert connector.health_check_count == 2
            assert pool._config.validate_on_acquire is True
            await registry.release_connection("mock_a", second)
            await registry.shutdown_async()

        asyncio.run(_run())

    def test_pending_startup_cleanup_is_retried_by_shutdown_and_keeps_owner(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """A failed startup cleanup stays registry-owned until disconnect succeeds."""

        async def _run() -> None:
            connector = _Net01LifecycleConnector(disconnect_failures=2)
            pool = ConnectionPool[SourceConnectorValue[Any]](
                connector_factory=lambda: connector,
                config=sample_config,
                pool_config=PoolConfig(
                    max_size=1,
                    max_connection_uses=1,
                    validate_on_acquire=False,
                    acquire_timeout_seconds=0.02,
                ),
            )
            handle = await pool.acquire()
            with pytest.raises(RuntimeError):
                await pool.release(handle)

            registry.retain_pending_startup_cleanup("mock_a", pool)
            assert id(pool) in registry._pending_startup_cleanup
            assert pool not in registry._connection_pools.values()

            with pytest.raises(RuntimeError):
                await registry.shutdown_async()
            assert id(pool) in registry._pending_startup_cleanup
            assert connector.disconnect_calls == [handle.session_id, handle.session_id]

            await registry.shutdown_async()
            assert id(pool) not in registry._pending_startup_cleanup
            assert connector.disconnect_calls == [handle.session_id] * 3

        asyncio.run(_run())

    def test_pending_startup_cleanup_survives_unregister_retry(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """Unregister retries a pending owner even after the connector is removed."""

        async def _run() -> None:
            connector = _Net01LifecycleConnector(disconnect_failures=2)
            registry.register(
                _Net01LifecycleConnector,
                config=sample_config,
                factory=lambda: connector,
            )
            pool = ConnectionPool[SourceConnectorValue[Any]](
                connector_factory=lambda: connector,
                config=sample_config,
                pool_config=PoolConfig(
                    max_size=1,
                    max_connection_uses=1,
                    validate_on_acquire=False,
                    acquire_timeout_seconds=0.02,
                ),
            )
            handle = await pool.acquire()
            with pytest.raises(RuntimeError):
                await pool.release(handle)
            registry.retain_pending_startup_cleanup("mock_a", pool)

            with pytest.raises(RuntimeError):
                await registry.unregister_async("mock_a")
            assert id(pool) in registry._pending_startup_cleanup
            assert not registry.has("mock_a")

            await registry.unregister_async("mock_a")
            assert id(pool) not in registry._pending_startup_cleanup
            assert connector.disconnect_calls == [handle.session_id] * 3

        asyncio.run(_run())

    def test_shutdown_retains_normal_pool_owner_when_disconnect_fails(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """Shutdown keeps an evicted normal owner reachable for a later retry."""

        async def _run() -> None:
            connector = _Net01LifecycleConnector(disconnect_failures=1)
            registry.register(
                _Net01LifecycleConnector,
                config=sample_config,
                factory=lambda: connector,
            )
            handle = await registry.get_connection("mock_a")
            await registry.release_connection("mock_a", handle)

            with pytest.raises(RuntimeError, match="cleanup remains pending"):
                await registry.shutdown_async()
            assert len(registry._pending_startup_cleanup) == 1
            assert registry._connection_pools == {}
            assert connector.disconnect_calls == [handle.session_id]

            await registry.shutdown_async()
            assert registry._pending_startup_cleanup == {}
            assert connector.disconnect_calls == [handle.session_id] * 2

        asyncio.run(_run())

    def test_trim_retains_evicted_pool_owner_when_disconnect_fails(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        alt_config: ConnectionConfig,
    ) -> None:
        """LRU trim keeps a failed eviction reachable for the next lifecycle retry."""

        async def _run() -> None:
            connector = _Net01LifecycleConnector(disconnect_failures=1)
            registry.register(
                _Net01LifecycleConnector,
                config=sample_config,
                factory=lambda: connector,
            )
            registry._max_connection_pools = 1
            first = await registry.get_connection("mock_a")
            await registry.release_connection("mock_a", first)

            with pytest.raises(RuntimeError, match="cleanup remains pending"):
                await registry.get_connection("mock_a", config=alt_config)
            assert len(registry._pending_startup_cleanup) == 1
            assert connector.disconnect_calls == [first.session_id]

            await registry.shutdown_async()
            assert registry._pending_startup_cleanup == {}
            assert connector.disconnect_calls == [first.session_id] * 2

        asyncio.run(_run())

    def test_registry_connection_pooling(
        self, registry: ConnectorRegistry, sample_config: ConnectionConfig
    ) -> None:
        """Registry integrates with connection pooling."""

        async def _run() -> None:
            registry.register(MockConnectorA, config=sample_config)

            handle = await registry.get_connection("mock_a")
            assert handle is not None

            await registry.release_connection("mock_a", handle)

            stats = registry.stats
            assert stats.active_pools == 1

        asyncio.run(_run())

    def test_registry_connection_pools_are_event_loop_scoped(
        self,
        registry: ConnectorRegistry,
    ) -> None:
        """Fresh-loop callers do not share asyncio pool primitives."""
        config = ConnectionConfig(
            url="https://api.example.com/v1",
            headers={"User-Agent": "PolicyOS/Test"},
            timeout_seconds=30,
            max_connections=1,
        )
        registry.register(MockConnectorA, config=config)

        barrier = threading.Barrier(2)
        errors: list[BaseException] = []

        def _worker() -> None:
            async def _run() -> None:
                barrier.wait(timeout=5)
                handle = await registry.get_connection("mock_a")
                await asyncio.sleep(0.02)
                await registry.release_connection("mock_a", handle)

            try:
                asyncio.run(_run())
            except BaseException as exc:  # pragma: no cover - asserted below.
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert errors == []
        assert registry.stats.active_pools == 2

    def test_bootstrap_default_configs_uses_default_profile_registry_helper(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Profile bootstrap resolves through helper-isolated singleton boundary."""

        class _Profile:
            profile_id = "test.mock.profile"
            connector_family = "test.mock"

        class _ProfileRegistry:
            def list_all(self) -> list[_Profile]:
                return [_Profile()]

        registry.register(MockConnectorA)
        monkeypatch.setattr(
            "polisyos.fabric.connectors._registry_lifecycle._default_source_profile_registry",
            lambda: _ProfileRegistry(),
        )
        monkeypatch.setattr(
            "polisyos.fabric.connectors.profiles.registry.SourceProfileRegistry.get_instance",
            lambda: (_ for _ in ()).throw(
                AssertionError("default profile registry helper should isolate singleton lookup")
            ),
        )
        monkeypatch.setattr(
            "polisyos.fabric.connectors.profiles.resolver.resolve_connection_config",
            lambda profile: sample_config,
        )

        registry._bootstrap_default_configs()

        entry = registry.get_entry("mock_a")
        assert entry.default_config == sample_config

    def test_slo_wrapper_uses_default_metrics_helper(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SLO wrapper resolves metrics through helper-isolated bootstrap hook."""

        class _Metrics:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def record_slo_connector_request(self, status: str, *, connector_id: str) -> None:
                self.calls.append((status, connector_id))

        metrics = _Metrics()
        monkeypatch.setattr(
            "polisyos.fabric.connectors._registry_lifecycle._default_metrics",
            lambda: metrics,
        )
        monkeypatch.setattr(
            "polisyos.fabric.connectors._registry_lifecycle.get_metrics",
            lambda: (_ for _ in ()).throw(
                AssertionError("default metrics helper should isolate direct observability lookup")
            ),
        )
        registry.register(MockConnectorA, config=sample_config)

        async def _run() -> None:
            connector = registry.get("mock_a", enable_cache=False)
            handle = await connector.connect(sample_config)
            await connector.fetch(handle, FetchRequest(dataset_id="dataset.test"))

        asyncio.run(_run())

        assert metrics.calls == [("ok", "test.mock.mock_a@1.0.0")]

    def test_cached_fetch_receipt_is_counted_once_by_registry_slo_wrapper(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from datetime import timedelta

        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.connectors.cache import ConnectorCacheStore, TTLPolicy

        class _Metrics:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def record_slo_connector_request(self, status: str, *, connector_id: str) -> None:
                self.calls.append((status, connector_id))

        metrics = _Metrics()
        monkeypatch.setattr(
            "polisyos.fabric.connectors._registry_lifecycle._default_metrics",
            lambda: metrics,
        )
        cache = ConnectorCacheStore(
            FileSystemCAS(tmp_path / "cas"),
            TTLPolicy(ttl=timedelta(hours=1)),
        )
        registry.configure_cache(cache)
        registry.register(MockConnectorA, config=sample_config)

        async def _run() -> None:
            from polisyos.fabric.connectors.cache import (
                CacheFetchReceipt,
                CachingConnectorProxy,
            )

            connector = registry.get("mock_a")
            assert isinstance(connector, CachingConnectorProxy)
            handle = await connector.connect(sample_config)
            request = FetchRequest(dataset_id="dataset.receipt-slo")
            await connector.fetch(handle, request)
            receipt = await connector.fetch_with_receipt(
                handle,
                request,
                require_selected_profile=True,
            )
            assert isinstance(receipt, CacheFetchReceipt)
            assert receipt.lookup_outcome == "hit"
            assert receipt.cache_result is not None
            assert receipt.cache_result.metadata.cache_key.startswith(
                "fabric.connector_cache.selected-source.v1:"
            )
            await connector.disconnect(handle)

        asyncio.run(_run())
        cache.close()

        assert metrics.calls == [
            ("ok", "test.mock.mock_a@1.0.0"),
            ("ok", "test.mock.mock_a@1.0.0"),
        ]

    def test_cached_wrapper_tracks_replacement_registration_for_fetch(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        tmp_path: Path,
    ) -> None:
        """A cached proxy follows same-owner replacement and fetches through it."""
        from datetime import timedelta

        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.connectors.cache import (
            CachingConnectorProxy,
            ConnectorCacheStore,
            TTLPolicy,
        )

        calls: list[str] = []

        class Original(MockConnectorA):
            producer_label: ClassVar[str] = "original"

            async def fetch(
                self,
                handle: ConnectionHandle,
                request: FetchRequest,
            ) -> FetchResult[list[dict]]:
                calls.append(self.producer_label)
                result = await super().fetch(handle, request)
                result.data[:] = [{"producer": self.producer_label}]
                return result

        class Replacement(Original):
            producer_label: ClassVar[str] = "replacement"

        cache = ConnectorCacheStore(
            FileSystemCAS(tmp_path / "cas"),
            TTLPolicy(ttl=timedelta(hours=1)),
        )
        registry.configure_cache(cache)
        registry.register(Original, config=sample_config)
        first = registry.get("mock_a")
        assert isinstance(first, CachingConnectorProxy)

        registry.register(Replacement, config=sample_config, override=True)
        current = registry.get("mock_a")
        assert isinstance(current, CachingConnectorProxy)
        assert current is not first

        async def _fetch() -> list[dict]:
            handle = await current.connect(sample_config)
            result = await current.fetch(
                handle,
                FetchRequest(dataset_id="registry.override.never-fetched"),
            )
            await current.disconnect(handle)
            return result.data

        try:
            assert asyncio.run(_fetch()) == [{"producer": "replacement"}]
        finally:
            cache.close()

        assert calls == ["replacement"]

    def test_contract_wrapper_tracks_replacement_registration_for_fetch(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """A contract proxy follows same-owner replacement and validates its fetch."""
        from polisyos.fabric.connectors.contracts import (
            ConnectorSchemaContract,
            ContractRegistry,
            ContractValidatingProxy,
            DataSchema,
            FieldSpec,
            SchemaType,
            SchemaVersion,
        )

        schema = DataSchema(
            schema_id="test.registry.registration_origin",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="producer", data_type=SchemaType.STRING, nullable=False),),
            primary_key=("producer",),
            required_completeness=0.0,
        )
        contracts = ContractRegistry()
        contracts.register(
            ConnectorSchemaContract(
                contract_id="test.registry.registration_origin",
                connector_id="mock_a",
                dataset_id="registry.override.contract",
                schema=schema,
                min_completeness=0.0,
                created_by="tests",
            )
        )
        registry.configure_contracts(contracts)
        calls: list[str] = []

        class Original(MockConnectorA):
            producer_label: ClassVar[str] = "original"

            async def fetch(
                self,
                handle: ConnectionHandle,
                request: FetchRequest,
            ) -> FetchResult[list[dict]]:
                calls.append(self.producer_label)
                result = await super().fetch(handle, request)
                return result.model_copy(
                    update={
                        "data": [{"producer": self.producer_label}],
                        "schema_id": schema.schema_id,
                        "schema_version": str(schema.version),
                    }
                )

        class Replacement(Original):
            producer_label: ClassVar[str] = "replacement"

        registry.register(Original, config=sample_config)
        first = registry.get("mock_a", enable_cache=False)
        assert isinstance(first, ContractValidatingProxy)

        registry.register(Replacement, config=sample_config, override=True)
        current = registry.get("mock_a", enable_cache=False)
        assert isinstance(current, ContractValidatingProxy)
        assert current is not first

        async def _fetch() -> list[dict]:
            handle = await current.connect(sample_config)
            result = await current.fetch(
                handle,
                FetchRequest(dataset_id="registry.override.contract"),
            )
            await current.disconnect(handle)
            return result.data

        assert asyncio.run(_fetch()) == [{"producer": "replacement"}]
        assert calls == ["replacement"]

    @pytest.mark.parametrize(
        ("surface_path", "enable_cache"),
        [
            ("cache_import_failure", True),
            ("cache_wrapper_failure", True),
            ("normal_cache", True),
            ("no_cache", False),
            ("contract_wrapper", False),
        ],
    )
    def test_get_finalizes_every_surface_after_registration_override(
        self,
        surface_path: str,
        enable_cache: bool,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Every optional surface path rejects an in-flight superseded get."""
        import builtins
        from datetime import timedelta

        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.connectors.cache import ConnectorCacheStore, TTLPolicy
        from polisyos.fabric.connectors.contracts import (
            ConnectorSchemaContract,
            ContractRegistry,
            DataSchema,
            FieldSpec,
            SchemaType,
            SchemaVersion,
        )

        dataset_id = "registry.override.finalization"
        contract_schema = DataSchema(
            schema_id="test.registry.finalized_surface",
            version=SchemaVersion(1, 0, 0),
            fields=(FieldSpec(name="producer", data_type=SchemaType.STRING, nullable=False),),
            primary_key=("producer",),
            required_completeness=0.0,
        )
        if surface_path == "contract_wrapper":
            contracts = ContractRegistry()
            contracts.register(
                ConnectorSchemaContract(
                    contract_id="test.registry.finalized_surface",
                    connector_id="mock_a",
                    dataset_id=dataset_id,
                    schema=contract_schema,
                    min_completeness=0.0,
                    created_by="tests",
                )
            )
            registry.configure_contracts(contracts)

        if surface_path != "contract_wrapper":
            cache = ConnectorCacheStore(
                FileSystemCAS(tmp_path / "cas"),
                TTLPolicy(ttl=timedelta(hours=1)),
            )
            registry.configure_cache(cache)
        else:
            cache = None

        calls: list[str] = []

        class Original(MockConnectorA):
            producer_label: ClassVar[str] = "original"

            async def fetch(
                self,
                handle: ConnectionHandle,
                request: FetchRequest,
            ) -> FetchResult[list[dict]]:
                calls.append(self.producer_label)
                result = await super().fetch(handle, request)
                data = [{"producer": self.producer_label}]
                if surface_path == "contract_wrapper":
                    return result.model_copy(
                        update={
                            "data": data,
                            "schema_id": contract_schema.schema_id,
                            "schema_version": str(contract_schema.version),
                        }
                    )
                result.data[:] = data
                return result

        class Replacement(Original):
            producer_label: ClassVar[str] = "replacement"

        registry.register(Original, config=sample_config)
        if surface_path == "cache_import_failure":
            original_import = builtins.__import__

            def fail_optional_cache_proxy(
                name: str,
                globals: dict[str, object] | None = None,
                locals: dict[str, object] | None = None,
                fromlist: tuple[str, ...] = (),
                level: int = 0,
            ):
                if name == "polisyos.fabric.connectors.cache.proxy":
                    raise ModuleNotFoundError("simulated optional cache proxy failure")
                return original_import(name, globals, locals, fromlist, level)

            monkeypatch.setattr(builtins, "__import__", fail_optional_cache_proxy)
        elif surface_path == "cache_wrapper_failure":
            monkeypatch.setattr(
                registry,
                "_build_schema_hash_provider",
                lambda **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("simulated cache wrapper failure")
                ),
            )

        started = threading.Event()
        resume = threading.Event()
        results: list[SourceConnectorValue[Any]] = []
        errors: list[BaseException] = []

        def pause_before_surface_return(
            connector: SourceConnectorValue[Any],
            *,
            connector_id: str,
        ) -> SourceConnectorValue[Any]:
            started.set()
            assert resume.wait(timeout=5)
            return connector

        monkeypatch.setattr(registry, "_apply_slo_metrics_wrapper", pause_before_surface_return)

        def get_stale_registration() -> None:
            try:
                results.append(registry.get("mock_a", enable_cache=enable_cache))
            except BaseException as exc:  # Captured for an assertion in the test thread.
                errors.append(exc)

        worker = threading.Thread(target=get_stale_registration)
        worker.start()
        try:
            assert started.wait(timeout=5)
            registry.register(Replacement, config=sample_config, override=True)
            resume.set()
            worker.join(timeout=5)
            assert not worker.is_alive()
            if results:
                assert errors == []
            else:
                assert len(errors) == 1 and isinstance(errors[0], ConnectorConfigError)
        finally:
            resume.set()
            worker.join(timeout=5)
            if surface_path == "cache_import_failure":
                monkeypatch.setattr(builtins, "__import__", original_import)
            if surface_path == "cache_wrapper_failure":
                monkeypatch.setattr(
                    registry,
                    "_build_schema_hash_provider",
                    ConnectorRegistry._build_schema_hash_provider.__get__(registry),
                )
            monkeypatch.setattr(
                registry,
                "_apply_slo_metrics_wrapper",
                ConnectorRegistry._apply_slo_metrics_wrapper.__get__(registry),
            )

        try:
            current = registry.get("mock_a", enable_cache=enable_cache)

            async def fetch_surface(
                connector: SourceConnectorValue[Any],
                request_id: str,
            ) -> list[dict]:
                handle = await connector.connect(sample_config)
                result = await connector.fetch(
                    handle,
                    FetchRequest(dataset_id=request_id),
                )
                await connector.disconnect(handle)
                return result.data

            stale_data = (
                asyncio.run(fetch_surface(results[0], f"{dataset_id}.stale")) if results else None
            )
            current_data = asyncio.run(fetch_surface(current, dataset_id))
            assert stale_data is None or stale_data == [{"producer": "replacement"}], {
                "surface_path": surface_path,
                "stale_fetch_data": stale_data,
            }
            assert current_data == [{"producer": "replacement"}]
            assert results == []
            assert calls == ["replacement"]
        finally:
            if cache is not None:
                cache.close()

    def test_stale_inflight_get_cannot_backfill_replaced_registration_wrapper(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A delayed get cannot repopulate the derived-wrapper cache after override."""
        from datetime import timedelta

        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.fabric.connectors.cache import ConnectorCacheStore, TTLPolicy

        class Original(MockConnectorA):
            pass

        class Replacement(MockConnectorA):
            pass

        cache = ConnectorCacheStore(
            FileSystemCAS(tmp_path / "cas"),
            TTLPolicy(ttl=timedelta(hours=1)),
        )
        registry.configure_cache(cache)
        registry.register(Original, config=sample_config)
        registry.get("mock_a")

        started = threading.Event()
        resume = threading.Event()
        results: list[SourceConnectorValue[Any]] = []
        errors: list[BaseException] = []
        original_apply = registry._apply_slo_metrics_wrapper

        def _pause_before_wrapper_emission(
            connector: SourceConnectorValue[Any],
            *,
            connector_id: str,
        ) -> SourceConnectorValue[Any]:
            started.set()
            assert resume.wait(timeout=5)
            return original_apply(connector, connector_id=connector_id)

        monkeypatch.setattr(
            registry,
            "_apply_slo_metrics_wrapper",
            _pause_before_wrapper_emission,
        )

        def _get_stale_registration() -> None:
            try:
                results.append(registry.get("mock_a"))
            except BaseException as exc:  # Captured for an assertion in the test thread.
                errors.append(exc)

        worker = threading.Thread(target=_get_stale_registration)
        worker.start()
        assert started.wait(timeout=5)
        registry.register(Replacement, config=sample_config, override=True)
        resume.set()
        worker.join(timeout=5)

        try:
            assert not worker.is_alive()
            assert results == []
            assert len(errors) == 1 and isinstance(errors[0], ConnectorConfigError)
            entry = registry.get_entry("mock_a")
            assert not registry._cache_wrappers
            monkeypatch.setattr(
                registry,
                "_apply_slo_metrics_wrapper",
                original_apply,
            )
            current = registry.get("mock_a")
            assert current is not None
            binding = registry._registered_owner_bindings[id(entry)]
            assert set(registry._cache_wrappers) == {(entry.fqid, binding.registration_generation)}
        finally:
            resume.set()
            cache.close()

    def test_unregister_async_drains_owned_pool(
        self, registry: ConnectorRegistry, sample_config: ConnectionConfig
    ) -> None:
        """Async unregister closes associated pools without fire-and-forget tasks."""

        class TrackingConnector(MockConnectorA):
            disconnect_count = 0

            async def disconnect(self, handle: ConnectionHandle) -> None:
                type(self).disconnect_count += 1

        async def _run() -> None:
            registry.register(TrackingConnector, config=sample_config)
            handle = await registry.get_connection("mock_a")
            await registry.release_connection("mock_a", handle)

            assert registry.stats.active_pools == 1
            assert await registry.unregister_async("mock_a") is True
            assert registry.stats.active_pools == 0
            assert TrackingConnector.disconnect_count == 1

        asyncio.run(_run())

    def test_sync_unregister_refuses_running_loop_with_active_pool(
        self, registry: ConnectorRegistry, sample_config: ConnectionConfig
    ) -> None:
        """Sync unregister does not create fire-and-forget cleanup tasks in a live loop."""

        async def _run() -> None:
            registry.register(MockConnectorA, config=sample_config)
            handle = await registry.get_connection("mock_a")
            await registry.release_connection("mock_a", handle)

            with pytest.raises(RuntimeError, match="unregister_async"):
                registry.unregister("mock_a")

            assert await registry.unregister_async("mock_a") is True

        asyncio.run(_run())

    def test_registry_pool_keyed_by_config(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        alt_config: ConnectionConfig,
    ) -> None:
        """Pools are isolated by config fingerprint."""

        async def _run() -> None:
            registry.register(MockConnectorA, config=sample_config)

            handle1 = await registry.get_connection("mock_a")
            handle2 = await registry.get_connection("mock_a", config=alt_config)

            assert handle1.config.url != handle2.config.url

            await registry.release_connection("mock_a", handle1)
            await registry.release_connection("mock_a", handle2)

            stats = registry.stats
            assert stats.active_pools == 2

        asyncio.run(_run())

    def test_get_connection_without_config_raises(self, registry: ConnectorRegistry) -> None:
        """get_connection without config raises error."""

        async def _run() -> None:
            registry.register(MockConnectorA)  # No default config

            with pytest.raises(ConnectorConfigError):
                await registry.get_connection("mock_a")

        asyncio.run(_run())

    def test_health_tracking(self, registry: ConnectorRegistry) -> None:
        """Registry tracks connector health."""
        registry.register(MockConnectorA)

        health = HealthStatus(healthy=True, message="OK")
        registry.update_health("mock_a", health)

        entry = registry.get_entry("mock_a")
        assert entry.health_status is not None
        assert entry.health_status.healthy is True
        assert entry.consecutive_failures == 0

    def test_health_tracking_failures(self, registry: ConnectorRegistry) -> None:
        """Registry tracks consecutive failures."""
        registry.register(MockConnectorA)

        for i in range(3):
            health = HealthStatus(healthy=False, message=f"Error {i}")
            registry.update_health("mock_a", health)

        entry = registry.get_entry("mock_a")
        assert entry.consecutive_failures == 3

    def test_registry_iteration(self, registry: ConnectorRegistry) -> None:
        """Registry supports iteration over FQIDs."""
        registry.register(MockConnectorA)
        registry.register(MockConnectorB)

        fqids = list(registry)

        assert len(fqids) == 2
        assert "test.mock.mock_a@1.0.0" in fqids
        assert "test.mock.mock_b@1.0.0" in fqids

    def test_registry_contains(self, registry: ConnectorRegistry) -> None:
        """Registry supports 'in' operator."""
        registry.register(MockConnectorA)

        assert "mock_a" in registry
        assert "test.mock.mock_a@1.0.0" in registry
        assert "nonexistent" not in registry

    def test_registration_owner_binding_tracks_replacement_and_unregistration(
        self, registry: ConnectorRegistry
    ) -> None:
        """Private owner state follows exact entries through registry lifecycle."""

        class ReplacementRuntimeOwner(MockConnectorA):
            connector_id: ClassVar[str] = "mock_a.replacement"

        registry.register(MockConnectorA)
        first_entry = registry.get_entry("mock_a")
        first_instance = registry.get("mock_a", enable_cache=False)
        first_binding = registry._registered_owner_bindings[id(first_entry)]
        assert first_binding.entry is first_entry
        assert first_binding.runtime_connector_id == "mock_a"
        assert first_binding.connector_class is MockConnectorA
        assert first_binding.factory is first_entry.factory
        assert first_binding.instance is first_instance
        first_generation = first_binding.registration_generation

        registry.register(ReplacementRuntimeOwner, override=True)
        replacement = registry.get_entry("mock_a")
        assert replacement is not first_entry
        assert id(first_entry) not in registry._registered_owner_bindings
        replacement_binding = registry._registered_owner_bindings[id(replacement)]
        assert replacement_binding.entry is replacement
        assert replacement_binding.runtime_connector_id == "mock_a.replacement"
        assert replacement_binding.connector_class is ReplacementRuntimeOwner
        assert replacement_binding.factory is replacement.factory
        assert replacement_binding.instance is None
        assert replacement_binding.registration_generation > first_generation
        assert registry.get("mock_a").connector_id == "mock_a.replacement"

        stale_binding = registry._registered_owner_bindings[id(replacement)]
        assert registry.unregister("mock_a")
        assert dict(registry._registered_owner_bindings) == {}
        registry.register(MockConnectorA)
        reregistered = registry.get_entry("mock_a")
        assert reregistered is not replacement
        assert id(replacement) not in registry._registered_owner_bindings
        assert registry._registered_owner_bindings[id(reregistered)] is not stale_binding
        assert (
            registry._registered_owner_bindings[id(reregistered)].runtime_connector_id == "mock_a"
        )
        assert (
            registry._registered_owner_bindings[id(reregistered)].registration_generation
            > replacement_binding.registration_generation
        )

    def test_override_changes_pool_owner_for_normal_and_live_permit_routes(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        tmp_path: Path,
    ) -> None:
        """A new registration gets a new pool while old handles keep their owner."""

        class OriginalRuntimeOwner(MockConnectorA):
            connector_id: ClassVar[str] = "mock_a"
            disconnect_calls: ClassVar[int] = 0

            async def disconnect(self, handle: ConnectionHandle) -> None:
                type(self).disconnect_calls += 1

        class ReplacementRuntimeOwner(OriginalRuntimeOwner):
            connector_id: ClassVar[str] = "mock_a.replacement"
            disconnect_calls: ClassVar[int] = 0

        attempt_id = "registration-override"
        dataset_id = "override-dataset"
        request = {
            "connector_id": "mock_a",
            "profile_id": "mock_a_profile",
            "request_dataset_id": dataset_id,
            "variable_id": dataset_id,
            "schema_contract": {"columns": ["id", "value"]},
        }
        schema_contract = request["schema_contract"]
        source_profile = SourceProfile(
            profile_id="mock_a_profile",
            display_name="Mock A",
            connector_family="mock_a",
            base_url="https://api.example.com/v1",
            timeout_seconds=30,
            rate_limit_rps=2.0,
            requests_per_hour=120,
        )
        family_receipt = {
            "connector_id": "mock_a",
            "protocol_conformant": True,
            "harness_checks_passed": ("core_methods_are_async", "protocol_compliance"),
            "harness_check_failures": (),
            "safe_dry_run_passed": True,
            "simulator_intercepted": True,
            "network_escape_attempt_count": 0,
            "dry_run_attempts": (
                {
                    "attempt_id": attempt_id,
                    "profile_id": "mock_a_profile",
                    "request_dataset_id": dataset_id,
                    "outcome": "replay_fixture_missing_after_interception",
                    "transport_intercepted": True,
                },
            ),
        }
        baseline_sha256 = "sha256:" + "f" * 64
        authorization = build_live_execution_authorization(
            attempt_id=attempt_id,
            connector_id="mock_a",
            request_dataset_id=dataset_id,
            request=request,
            schema_contract=schema_contract,
            source_profile=source_profile,
            baseline_sha256=baseline_sha256,
            family_receipt=family_receipt,
            max_response_bytes=65_536,
            max_decompressed_bytes=65_536,
        )
        journal = AppendOnlyEvidenceJournal(tmp_path / "registration-override.jsonl")
        request_ref = journal.append_request(attempt_id=attempt_id, request=request)

        async def exercise() -> None:
            registry.register(OriginalRuntimeOwner, config=sample_config)
            original_pool, original_key = await registry._resolve_connection_pool(
                "mock_a", sample_config
            )
            original_handle = await registry.get_connection("mock_a", sample_config)
            assert original_handle.connector_id == "mock_a"
            assert original_handle.get_state("__polisyos_connector_pool_key") == original_key
            assert original_pool._in_use[original_handle.session_id].connector.__class__ is (
                OriginalRuntimeOwner
            )

            registry.register(ReplacementRuntimeOwner, config=sample_config, override=True)
            replacement_pool, replacement_key = await registry._resolve_connection_pool(
                "mock_a", sample_config
            )
            assert replacement_pool is not original_pool
            assert replacement_key != original_key

            replacement_handle = await registry.get_connection("mock_a", sample_config)
            with journal.live_acquire_permit_scope(
                authorization=authorization,
                request_ref=request_ref,
                connector_id="mock_a",
                request_dataset_id=dataset_id,
                request=request,
                schema_contract=schema_contract,
                source_profile=source_profile,
                baseline_sha256=baseline_sha256,
                family_receipt=family_receipt,
                timeout_cap_seconds=15.0,
                heartbeat_cap_seconds=5.0,
                max_response_bytes=65_536,
                max_decompressed_bytes=65_536,
            ) as permit:
                live_permit_handle = await registry._get_connection_with_live_permit(
                    "mock_a",
                    sample_config,
                    dataset_id=dataset_id,
                    permit=permit,
                )
            assert replacement_handle.connector_id == "mock_a.replacement"
            assert live_permit_handle.connector_id == "mock_a.replacement"
            assert original_pool.get_stats().in_use_connections == 1
            assert replacement_pool.get_stats().in_use_connections == 2
            assert original_pool._semaphore._value == original_pool._config.max_size - 1
            assert replacement_pool._semaphore._value == replacement_pool._config.max_size - 2

            await registry.release_connection("mock_a", original_handle)
            assert original_pool.get_stats().in_use_connections == 0
            assert original_pool.get_stats().idle_connections == 1
            assert replacement_pool.get_stats().in_use_connections == 2
            assert original_pool._semaphore._value == original_pool._config.max_size
            assert replacement_pool._semaphore._value == replacement_pool._config.max_size - 2

            await registry.release_connection("mock_a", replacement_handle)
            await registry.release_connection("mock_a", live_permit_handle)
            assert replacement_pool.get_stats().in_use_connections == 0
            assert replacement_pool._semaphore._value == replacement_pool._config.max_size

            await registry.shutdown_async()
            assert OriginalRuntimeOwner.disconnect_calls == 1
            assert ReplacementRuntimeOwner.disconnect_calls == 2

        asyncio.run(exercise())

    def test_registered_factory_owner_is_bound_before_lazy_instance_or_pool_use(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """An injected factory cannot replace the selected registered owner."""

        class ForeignFactoryConnector(MockConnectorA):
            connector_id: ClassVar[str] = "foreign.owner"

            def __init__(self) -> None:
                self.connect_calls = 0

            async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
                self.connect_calls += 1
                return await super().connect(config)

        connector = ForeignFactoryConnector()
        factory_calls = 0

        def factory() -> ForeignFactoryConnector:
            nonlocal factory_calls
            factory_calls += 1
            return connector

        registry.register(MockConnectorA, config=sample_config, factory=factory)
        entry = registry.get_entry("mock_a")
        assert factory_calls == 0

        try:
            with pytest.raises(ConnectorConfigError, match="factory owner"):
                registry.get("mock_a")

            assert entry.instance is None
            assert entry.loaded is False
            assert factory_calls == 1
            assert connector.connect_calls == 0

            async def check_pool_route() -> None:
                with pytest.raises(ConnectorConfigError, match="factory owner"):
                    await registry.get_connection("mock_a", sample_config)

                assert connector.connect_calls == 0
                assert factory_calls == 2
                assert all(
                    pool.get_stats().total_connections == 0
                    and pool.get_stats().in_use_connections == 0
                    and pool._semaphore._value == pool._config.max_size
                    for pool in registry._connection_pools.values()
                )

            asyncio.run(check_pool_route())
        finally:
            asyncio.run(registry.shutdown_async())

    def test_registered_di_factory_remains_the_admitted_factory(
        self, registry: ConnectorRegistry
    ) -> None:
        """The registration-time DI callable remains valid and is cached privately."""
        connector = MockConnectorA()
        factory_calls = 0

        def factory() -> MockConnectorA:
            nonlocal factory_calls
            factory_calls += 1
            return connector

        registry.register(MockConnectorA, factory=factory)
        entry = registry.get_entry("mock_a")

        first = registry.get("mock_a", enable_cache=False)
        second = registry.get("mock_a", enable_cache=False)

        assert first is connector
        assert second is connector
        assert factory_calls == 1
        binding = registry._registered_owner_bindings[id(entry)]
        assert binding.instance is connector
        assert entry.instance is connector
        assert entry.loaded is True

    def test_connector_entry_preserves_legacy_positional_constructor(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """Registry-owned identity state leaves the entry positional API unchanged."""
        registry.register(MockConnectorA, config=sample_config)
        entry = registry.get_entry("mock_a")

        legacy = ConnectorEntry(
            entry.metadata,
            entry.capabilities,
            entry.connector_class,
            entry.factory,
            sample_config,
        )

        assert legacy.default_config is sample_config
        assert legacy.runtime_connector_id is None

    def test_public_entry_factory_and_class_mutation_cannot_redefine_registration(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """Mutable public entry fields cannot substitute a same-owner producer."""

        class SameOwnerReplacement(MockConnectorA):
            connect_calls = 0

            async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
                type(self).connect_calls += 1
                return await super().connect(config)

        replacement = SameOwnerReplacement()
        replacement_factory_calls = 0

        def replacement_factory() -> SameOwnerReplacement:
            nonlocal replacement_factory_calls
            replacement_factory_calls += 1
            return replacement

        registry.register(MockConnectorA, config=sample_config)
        entry = registry.get_entry("mock_a")
        original_factory = entry.factory
        entry.factory = replacement_factory
        try:
            with pytest.raises(ConnectorConfigError, match="factory differs"):
                registry.get("mock_a")

            async def check_pool_routes() -> None:
                with pytest.raises(ConnectorConfigError, match="factory differs"):
                    await registry.get_connection("mock_a", sample_config)

                with pytest.raises(ConnectorConfigError, match="factory differs"):
                    await registry._get_connection_with_live_permit(
                        "mock_a",
                        sample_config,
                        dataset_id="factory-mutation",
                        permit=object(),
                    )

            asyncio.run(check_pool_routes())
            assert replacement_factory_calls == 0
            assert SameOwnerReplacement.connect_calls == 0
            assert entry.instance is None
            assert entry.loaded is False
        finally:
            entry.factory = original_factory
            asyncio.run(registry.shutdown_async())

    def test_public_entry_class_instance_and_loaded_mutations_fail_closed(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """A mutable entry cannot self-admit its factory, class, or instance."""

        class SameOwnerReplacement(MockConnectorA):
            connect_calls = 0

            async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
                type(self).connect_calls += 1
                return await super().connect(config)

        registry.register(MockConnectorA, config=sample_config)
        entry = registry.get_entry("mock_a")
        assert registry.get_entry("mock_a") is entry
        original_class = entry.connector_class

        entry.runtime_connector_id = "mock_b"
        with pytest.raises(ConnectorConfigError, match="runtime owner differs"):
            registry.get("mock_a")
        entry.runtime_connector_id = "mock_a"
        entry.connector_class = SameOwnerReplacement
        with pytest.raises(ConnectorConfigError, match="connector class differs"):
            registry.get("mock_a")
        entry.connector_class = original_class

        injected = SameOwnerReplacement()
        entry.instance = injected
        entry.loaded = True
        with pytest.raises(ConnectorConfigError, match="admitted instance differs"):
            registry.get("mock_a")
        assert injected.connect_calls == 0
        assert SameOwnerReplacement.connect_calls == 0

        entry.instance = None
        entry.loaded = True
        with pytest.raises(ConnectorConfigError, match="loaded state differs"):
            registry.get("mock_a")
        assert SameOwnerReplacement.connect_calls == 0

        entry.loaded = False
        admitted = registry.get("mock_a", enable_cache=False)
        assert isinstance(admitted, MockConnectorA)
        entry.instance = injected
        with pytest.raises(ConnectorConfigError, match="admitted instance differs"):
            registry.get("mock_a", enable_cache=False)
        assert injected.connect_calls == 0
        assert SameOwnerReplacement.connect_calls == 0

    def test_registry_reset_discards_registration_bindings(self) -> None:
        """Reset clears private registration provenance along with registry entries."""
        registry = ConnectorRegistry.get_instance(bootstrap=False)
        registry.register(MockConnectorA)
        entry = registry.get_entry("mock_a")
        assert registry._registered_owner_bindings[id(entry)].entry is entry

        ConnectorRegistry.reset_instance()

        assert registry._registered_owner_bindings == {}
        assert registry._connectors.get(entry.fqid) is None

    def test_selected_runtime_owner_is_snapshotted_before_class_mutation(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """Changing a connector class after registration cannot change its owner."""

        class MutableOwnerConnector(MockConnectorA):
            connector_id: ClassVar[str] = "mock_a"

        factory_calls = 0
        connect_calls = 0

        class CountingMutableOwnerConnector(MutableOwnerConnector):
            connector_id: ClassVar[str] = "mock_a"

            async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
                nonlocal connect_calls
                connect_calls += 1
                return await super().connect(config)

        def factory() -> CountingMutableOwnerConnector:
            nonlocal factory_calls
            factory_calls += 1
            return CountingMutableOwnerConnector()

        registry.register(
            CountingMutableOwnerConnector,
            config=sample_config,
            factory=factory,
        )
        entry = registry.get_entry("mock_a")
        assert factory_calls == 0

        original_id = CountingMutableOwnerConnector.connector_id
        CountingMutableOwnerConnector.connector_id = "foreign.owner"
        try:
            with pytest.raises(ConnectorConfigError, match="factory owner"):
                registry.get("mock_a")

            assert entry.runtime_connector_id == "mock_a"
            assert entry.instance is None
            assert entry.loaded is False
            assert factory_calls == 1
            assert connect_calls == 0

            async def check_pool_route() -> None:
                with pytest.raises(ConnectorConfigError, match="factory owner"):
                    await registry.get_connection("mock_a", sample_config)

                assert factory_calls == 2
                assert connect_calls == 0
                assert all(
                    pool.get_stats().total_connections == 0
                    and pool.get_stats().in_use_connections == 0
                    and pool._semaphore._value == pool._config.max_size
                    for pool in registry._connection_pools.values()
                )

            asyncio.run(check_pool_route())
        finally:
            CountingMutableOwnerConnector.connector_id = original_id
            asyncio.run(registry.shutdown_async())

    def test_registry_release_uses_exact_handle_owner_after_identity_and_route_mutation(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        alt_config: ConnectionConfig,
    ) -> None:
        """A corrupted handle is retired by its actual pool, regardless of caller labels."""

        async def _run() -> None:
            registry.register(MockConnectorA, config=sample_config)
            handle = await registry.get_connection("mock_a")
            pool = next(iter(registry._connection_pools.values()))

            object.__setattr__(handle, "connector_id", "foreign.connector")
            object.__setattr__(handle, "session_id", "foreign-session")
            object.__setattr__(handle, "config", alt_config)
            handle.set_state("__polisyos_connector_pool_key", ("wrong", "route", 999))
            admitted_state = handle._state
            object.__setattr__(handle, "_state", object())

            await registry.release_connection("unregistered.caller", handle)

            assert handle.connector_id == "mock_a"
            assert handle.session_id != "foreign-session"
            assert handle.config == sample_config
            assert handle._state is admitted_state
            stats = pool.get_stats()
            assert stats.in_use_connections == 0
            assert stats.total_closes == 1
            assert pool._pending_cleanup == {}
            assert pool._semaphore._value == pool._config.max_size

        asyncio.run(_run())

    def test_registry_release_does_not_accept_a_same_session_clone(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
    ) -> None:
        """Session ID equality cannot release a different handle object."""

        async def _run() -> None:
            registry.register(MockConnectorA, config=sample_config)
            handle = await registry.get_connection("mock_a")
            pool = next(iter(registry._connection_pools.values()))
            clone = ConnectionHandle(
                connector_id=handle.connector_id,
                config=handle.config,
                created_at=handle.created_at,
                session_id=handle.session_id,
            )

            await registry.release_connection("mock_a", clone)
            assert pool.get_stats().in_use_connections == 1
            assert pool._semaphore._value == pool._config.max_size - 1

            await registry.release_connection("mock_a", handle)
            assert pool.get_stats().in_use_connections == 0
            assert pool._semaphore._value == pool._config.max_size

        asyncio.run(_run())

    def test_registry_release_tries_all_pool_owners_after_route_mutation(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        alt_config: ConnectionConfig,
    ) -> None:
        """A wrong but well-shaped pool route only changes lookup order."""

        async def _run() -> None:
            registry.register(MockConnectorA, config=sample_config)
            first = await registry.get_connection("mock_a", config=sample_config)
            first_key = first.get_state("__polisyos_connector_pool_key")
            second = await registry.get_connection("mock_a", config=alt_config)
            second_key = second.get_state("__polisyos_connector_pool_key")
            pools = dict(registry._connection_pools.items())
            first_pool = pools[first_key]
            second_pool = pools[second_key]
            first.set_state("__polisyos_connector_pool_key", second_key)

            await registry.release_connection("mock_a", first)
            assert first_pool.get_stats().in_use_connections == 0
            assert second_pool.get_stats().in_use_connections == 1

            await registry.release_connection("mock_a", second)
            assert second_pool.get_stats().in_use_connections == 0

        asyncio.run(_run())

    @pytest.mark.parametrize("mutate_route", [False, True])
    def test_registry_release_routes_to_owner_loop_with_or_without_pool_tag(
        self,
        registry: ConnectorRegistry,
        sample_config: ConnectionConfig,
        mutate_route: bool,
    ) -> None:
        """Exact lease ownership remains releasable from another live event loop."""
        registry.register(MockConnectorA, config=sample_config)
        acquired = threading.Event()
        allow_owner_loop_exit = threading.Event()
        handles: list[ConnectionHandle] = []
        errors: list[BaseException] = []

        def _owner_worker() -> None:
            async def _run_owner_loop() -> None:
                handle = await registry.get_connection("mock_a")
                handles.append(handle)
                acquired.set()
                await asyncio.to_thread(allow_owner_loop_exit.wait)

            try:
                asyncio.run(_run_owner_loop())
            except BaseException as exc:  # pragma: no cover - asserted below.
                errors.append(exc)

        owner = threading.Thread(target=_owner_worker)
        owner.start()
        released = threading.Event()
        releaser: threading.Thread | None = None
        try:
            assert acquired.wait(timeout=5)
            handle = handles[0]
            pool = next(iter(registry._connection_pools.values()))
            if mutate_route:
                handle.pop_state("__polisyos_connector_pool_key")

            def _release_worker() -> None:
                async def _run_release_loop() -> None:
                    await registry.release_connection("mock_a", handle)

                try:
                    asyncio.run(_run_release_loop())
                except BaseException as exc:  # pragma: no cover - asserted below.
                    errors.append(exc)
                finally:
                    released.set()

            releaser = threading.Thread(target=_release_worker)
            releaser.start()
            assert released.wait(timeout=5)
            assert pool.get_stats().in_use_connections == 0
            assert pool.get_stats().total_releases == 1
        finally:
            allow_owner_loop_exit.set()
            if releaser is not None:
                releaser.join(timeout=5)
            owner.join(timeout=5)

        assert not owner.is_alive()
        assert releaser is None or not releaser.is_alive()
        assert errors == []


def test_captured_registration_refuses_override_before_get_and_keeps_unbound_lookup(
    registry: ConnectorRegistry,
    sample_config: ConnectionConfig,
) -> None:
    """A stale token refuses before the replacement factory; ordinary lookup stays live."""
    original_calls: list[str] = []
    replacement_calls: list[str] = []

    def original_factory() -> MockConnectorA:
        original_calls.append("original")
        return MockConnectorA()

    def replacement_factory() -> MockConnectorA:
        replacement_calls.append("replacement")
        return MockConnectorA()

    registry.register(MockConnectorA, config=sample_config, factory=original_factory)
    selected = registry._capture_registration_binding("mock_a")
    registry.register(
        MockConnectorA,
        config=sample_config,
        override=True,
        factory=replacement_factory,
    )

    with pytest.raises(ConnectorConfigError, match="registration changed after capture"):
        registry.get(
            "mock_a",
            enable_cache=False,
            _registration_binding=selected,
        )
    assert original_calls == []
    assert replacement_calls == []

    current = registry.get("mock_a", enable_cache=False)
    assert current.connector_id == "mock_a"
    assert original_calls == []
    assert replacement_calls == ["replacement"]


def test_captured_registration_allows_same_entry_lazy_load_and_refuses_replaced_connection(
    registry: ConnectorRegistry,
    sample_config: ConnectionConfig,
) -> None:
    """The same registration may materialize lazily, but a replacement cannot take its pool."""
    original_calls: list[str] = []
    replacement_calls: list[str] = []

    def original_factory() -> MockConnectorA:
        original_calls.append("original")
        return MockConnectorA()

    def replacement_factory() -> MockConnectorA:
        replacement_calls.append("replacement")
        return MockConnectorA()

    registry.register(MockConnectorA, config=sample_config, factory=original_factory)
    selected = registry._capture_registration_binding("mock_a")
    assert (
        registry.get(
            "mock_a",
            enable_cache=False,
            _registration_binding=selected,
        ).connector_id
        == "mock_a"
    )
    assert original_calls == ["original"]

    registry.register(
        MockConnectorA,
        config=sample_config,
        override=True,
        factory=replacement_factory,
    )

    async def _exercise() -> None:
        with pytest.raises(ConnectorConfigError, match="registration changed after capture"):
            await registry.get_connection(
                "mock_a",
                sample_config,
                _registration_binding=selected,
            )
        assert replacement_calls == []

        handle = await registry.get_connection("mock_a", sample_config)
        assert replacement_calls == ["replacement"]
        await registry.release_connection("mock_a", handle)
        await registry.shutdown_async()

    asyncio.run(_exercise())


@pytest.mark.parametrize(
    "resolution_error",
    [
        ConnectorNotFoundError("removed"),
        AmbiguousConnectorError("removed", ["one.removed", "two.removed"]),
    ],
)
def test_pending_cleanup_retains_only_expected_resolution_failures(
    registry: ConnectorRegistry,
    sample_config: ConnectionConfig,
    monkeypatch: pytest.MonkeyPatch,
    resolution_error: Exception,
) -> None:
    """Unregistered/ambiguous IDs still retain their exact pending pool owner."""
    pool = ConnectionPool(
        connector_factory=MockConnectorA,
        config=sample_config,
        pool_config=PoolConfig(),
    )

    def resolve(_connector_id: str) -> str:
        raise resolution_error

    monkeypatch.setattr(registry, "_resolve_id", resolve)
    registry.retain_pending_startup_cleanup("removed", pool)
    assert registry._pending_startup_cleanup[id(pool)] == ("removed", pool)


def test_pending_cleanup_does_not_hide_unexpected_resolution_failure(
    registry: ConnectorRegistry,
    sample_config: ConnectionConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken resolver cannot be laundered into an ordinary removed owner."""
    pool = ConnectionPool(
        connector_factory=MockConnectorA,
        config=sample_config,
        pool_config=PoolConfig(),
    )

    def resolve(_connector_id: str) -> str:
        raise RuntimeError("resolver invariant broke")

    monkeypatch.setattr(registry, "_resolve_id", resolve)
    with pytest.raises(RuntimeError, match="resolver invariant broke"):
        registry.retain_pending_startup_cleanup("removed", pool)
    assert registry._pending_startup_cleanup == {}


@pytest.mark.parametrize("import_error", [ModuleNotFoundError, RuntimeError])
def test_optional_cache_import_does_not_hide_unexpected_execution_failure(
    registry: ConnectorRegistry,
    sample_config: ConnectionConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    import_error: type[Exception],
) -> None:
    """Only an unavailable optional import falls back; imported code bugs escape."""
    import builtins
    from datetime import timedelta

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.connectors.cache import (
        CachingConnectorProxy,
        ConnectorCacheStore,
        TTLPolicy,
    )

    registry.register(MockConnectorA, config=sample_config)
    registry.configure_cache(
        ConnectorCacheStore(FileSystemCAS(tmp_path / "cas"), TTLPolicy(ttl=timedelta(hours=1)))
    )
    original_import = builtins.__import__
    attempts: list[str] = []

    def load_proxy(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "polisyos.fabric.connectors.cache.proxy":
            attempts.append(name)
            raise import_error("controlled cache module failure")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", load_proxy)
    if issubclass(import_error, ImportError):
        connector = registry.get("mock_a")
        assert not isinstance(connector, CachingConnectorProxy)
        assert connector.connector_id == "mock_a"
    else:
        with pytest.raises(RuntimeError, match="controlled cache module failure"):
            registry.get("mock_a")
    assert attempts == ["polisyos.fabric.connectors.cache.proxy"]
