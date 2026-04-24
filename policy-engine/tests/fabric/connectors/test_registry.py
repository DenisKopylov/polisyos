"""Comprehensive tests for Phase 2.2: Registry Architecture & Lazy Loading."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import ClassVar

import pytest

from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.discovery import ConnectorDiscovery
from polisyos.fabric.connectors.pool import (
    ConnectionPool,
    PoolClosedError,
    PoolConfig,
    PoolExhaustedError,
)
from polisyos.fabric.connectors.registry import (
    AmbiguousConnectorError,
    ConnectorAlreadyRegisteredError,
    ConnectorConfigError,
    ConnectorNotFoundError,
    ConnectorPreferences,
    ConnectorRegistry,
)
from polisyos.fabric.connectors.types import (
    DatasetDescriptor,
    FreshnessResult,
    FreshnessStatus,
    ValidationResult,
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
    ) -> AsyncIterator[list[dict]]:
        yield [{"mock": "stream"}]

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        return ValidationResult.success()


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
        return FreshnessResult(status=FreshnessStatus.FRESH, current_version=cached_version)

    async def fetch_stream(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> AsyncIterator[list[dict]]:
        yield []

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
        connectors: list[object] = []
        errors: list[BaseException] = []
        gate = threading.Barrier(8)

        def _get_connector() -> None:
            try:
                gate.wait()
                connectors.append(registry.get("mock_a"))
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
