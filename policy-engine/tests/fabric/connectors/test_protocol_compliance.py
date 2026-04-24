"""Protocol Compliance Tests for Data Fabric Connectors."""

from __future__ import annotations

import asyncio
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
from polisyos.fabric.connectors.capabilities import (
    REQUIRED_ATTRIBUTES,
    REQUIRED_METHODS,
    describe_capabilities,
    requires_capability,
    validate_protocol_compliance,
)
from polisyos.fabric.connectors.types import (
    CapabilityError,
    ConfigurationError,
    ConnectorError,
    DataChunk,
    DatasetDescriptor,
    FetchError,
    FreshnessResult,
    FreshnessStatus,
    RateLimitError,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
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


@pytest.fixture
def sample_config() -> ConnectionConfig:
    return ConnectionConfig(
        url="https://api.example.com/v1",
        headers={"User-Agent": "PolicyOS/1.0"},
        auth_method="api_key",
        auth_credentials={"api_key": "test_secret_key_12345"},
        timeout_seconds=30,
    )


@pytest.fixture
def sample_metadata() -> ConnectorMetadataSpec:
    return ConnectorMetadataSpec(
        connector_id="test_connector",
        version="1.0.0",
        namespace="test.example",
        source_name="Test Data Source",
        source_organization="Test Organization",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CATALOG_BROWSE,
        ),
    )


@pytest.fixture
def sample_version() -> DataVersion:
    return DataVersion(
        strategy=VersionStrategy.CONTENT_HASH,
        value="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        content_hash="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )


class CompliantConnector(BaseConnector[list[dict]]):
    connector_id: ClassVar[str] = "test.compliant"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.STREAMING
        | ConnectorCapability.FRESHNESS_CHECK
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="compliant",
        version="1.0.0",
        namespace="test",
        source_name="Test Source",
        source_organization="Test Org",
        trust_level=TrustLevel.HIGH,
        quality_tier=QualityTier.GOLD,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CATALOG_BROWSE,
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
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[list[dict]]:
        return FetchResult(
            data=[{"test": "data"}],
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

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        yield DatasetDescriptor(
            dataset_id="test.dataset",
            name="Test Dataset",
            description="A test dataset",
        )

    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator[DataChunk[list[dict]]]:
        yield DataChunk(
            data=[{"chunk": 1}],
            chunk_index=0,
            row_count=1,
            is_first=True,
            is_last=True,
        )

    async def check_freshness(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version: DataVersion,
    ) -> FreshnessResult:
        return FreshnessResult(
            status=FreshnessStatus.FRESH,
            message="Data is current",
        )


class MissingAttributesConnector:
    pass


class MissingMethodsConnector:
    connector_id: ClassVar[str] = "test.missing_methods"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="missing_methods",
        version="1.0.0",
        namespace="test",
        source_name="Test",
        source_organization="Test",
        capabilities=ConnectorCapability.FULL_FETCH.value,
    )


class StreamingCapabilityNoMethodConnector:
    connector_id: ClassVar[str] = "test.streaming_no_method"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH | ConnectorCapability.STREAMING
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="streaming_no_method",
        version="1.0.0",
        namespace="test",
        source_name="Test",
        source_organization="Test",
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.STREAMING,
        ),
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True)

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[list[dict]]:
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="test",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value="now",
                timestamp=datetime.now(UTC),
            ),
            fetched_at=datetime.now(UTC),
            completeness=1.0,
        )


class BaseConnectorNoOverride(BaseConnector[list[dict]]):
    connector_id: ClassVar[str] = "test.base_default"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.STREAMING
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="base_default",
        version="1.0.0",
        namespace="test",
        source_name="Test",
        source_organization="Test",
        capabilities=ConnectorCapability.STREAMING.value,
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return self._create_handle(config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True)

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[list[dict]]:
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="test",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value="now",
                timestamp=datetime.now(UTC),
            ),
            fetched_at=datetime.now(UTC),
            completeness=1.0,
        )


class SyncMethodsConnector:
    connector_id: ClassVar[str] = "test.sync_methods"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="sync_methods",
        version="1.0.0",
        namespace="test",
        source_name="Test",
        source_organization="Test",
        capabilities=ConnectorCapability.FULL_FETCH.value,
    )

    def connect(self, config: ConnectionConfig) -> ConnectionHandle:  # Not async!
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    def disconnect(self, handle: ConnectionHandle) -> None:  # Not async!
        return None

    def health_check(self, handle: ConnectionHandle) -> HealthStatus:  # Not async!
        return HealthStatus(healthy=True)

    def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[list[dict]]:  # Not async!
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="test",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value="now",
                timestamp=datetime.now(UTC),
            ),
            fetched_at=datetime.now(UTC),
            completeness=1.0,
        )


class TestProtocolCompliance:
    def test_compliant_connector_passes(self) -> None:
        violations = validate_protocol_compliance(CompliantConnector)
        assert violations == [], f"Unexpected violations: {violations}"

    def test_missing_attributes_fails(self) -> None:
        violations = validate_protocol_compliance(MissingAttributesConnector)
        for attr in REQUIRED_ATTRIBUTES:
            assert any(attr in v for v in violations), f"Should report missing attribute: {attr}"

    def test_missing_methods_fails(self) -> None:
        violations = validate_protocol_compliance(MissingMethodsConnector)
        for method in REQUIRED_METHODS:
            assert any(method in v for v in violations), f"Should report missing method: {method}"

    def test_streaming_capability_without_method_fails(self) -> None:
        violations = validate_protocol_compliance(StreamingCapabilityNoMethodConnector)
        assert any("STREAMING" in v and "fetch_stream" in v for v in violations), (
            f"Should report missing fetch_stream for STREAMING: {violations}"
        )

    def test_baseconnector_default_method_fails(self) -> None:
        violations = validate_protocol_compliance(BaseConnectorNoOverride)
        assert any("BaseConnector default" in v for v in violations)

    def test_protocol_stub_method_fails(self) -> None:
        class ProtocolStubConnector(CompliantConnector):
            async def fetch_stream(  # type: ignore[override]
                self,
                handle: ConnectionHandle,
                request: FetchRequest,
            ) -> AsyncIterator[DataChunk[list[dict]]]: ...

        violations = validate_protocol_compliance(ProtocolStubConnector)
        assert any(
            "fetch_stream" in violation and "not implemented" in violation
            for violation in violations
        )

    def test_sync_methods_fail_strict_mode(self) -> None:
        violations = validate_protocol_compliance(SyncMethodsConnector, strict=True)
        assert any("must be async" in v for v in violations), (
            f"Should report sync methods: {violations}"
        )

    def test_sync_methods_pass_non_strict_mode(self) -> None:
        violations = validate_protocol_compliance(SyncMethodsConnector, strict=False)
        assert not any("must be async" in v for v in violations)


class TestCapabilityValidation:
    def test_requires_capability_passes_when_present(self) -> None:
        class TestConnector:
            connector_id = "test"
            capabilities = ConnectorCapability.STREAMING

            @requires_capability(ConnectorCapability.STREAMING)
            async def fetch_stream(self) -> str:
                return "success"

        connector = TestConnector()
        result = asyncio.run(connector.fetch_stream())
        assert result == "success"

    def test_requires_capability_raises_when_missing(self) -> None:
        class TestConnector:
            connector_id = "test.missing_cap"
            capabilities = ConnectorCapability.FULL_FETCH

            @requires_capability(ConnectorCapability.STREAMING)
            async def fetch_stream(self) -> str:
                return "should not reach"

        connector = TestConnector()
        with pytest.raises(CapabilityError) as exc_info:
            asyncio.run(connector.fetch_stream())

        assert exc_info.value.connector_id == "test.missing_cap"
        assert exc_info.value.required == ConnectorCapability.STREAMING

    def test_requires_capability_propagates_custom_error_message(self) -> None:
        class TestConnector:
            connector_id = "test.custom_message"
            capabilities = ConnectorCapability.FULL_FETCH

            @requires_capability(
                ConnectorCapability.STREAMING,
                error_message="streaming access is disabled for this connector",
            )
            async def fetch_stream(self) -> str:
                return "should not reach"

        with pytest.raises(CapabilityError, match="streaming access is disabled"):
            asyncio.run(TestConnector().fetch_stream())

    def test_capability_error_contains_details(self) -> None:
        error = CapabilityError(
            connector_id="test.connector",
            required=ConnectorCapability.STREAMING,
            available=ConnectorCapability.FULL_FETCH,
        )

        error_dict = error.to_dict()
        assert error_dict["error_type"] == "CapabilityError"
        assert error_dict["connector_id"] == "test.connector"
        assert "STREAMING" in error_dict["details"]["required_capability"]

    def test_describe_capabilities(self) -> None:
        caps = (
            ConnectorCapability.FULL_FETCH
            | ConnectorCapability.STREAMING
            | ConnectorCapability.DATE_RANGE_FILTER
            | ConnectorCapability.RATE_LIMIT_AWARE
        )
        described = describe_capabilities(caps)

        assert "data_access" in described
        assert "FULL_FETCH" in described["data_access"]
        assert "STREAMING" in described["data_access"]
        assert "filtering" in described
        assert "DATE_RANGE_FILTER" in described["filtering"]
        assert "operational" in described
        assert "RATE_LIMIT_AWARE" in described["operational"]


class TestFetchRequestHashing:
    def test_same_params_same_hash(self) -> None:
        request1 = FetchRequest(
            dataset_id="test.dataset",
            date_start=datetime(2024, 1, 1, tzinfo=UTC),
            date_end=datetime(2024, 12, 31, tzinfo=UTC),
            filters=(("country", ("USA", "DEU")),),
        )
        request2 = FetchRequest(
            dataset_id="test.dataset",
            date_start=datetime(2024, 1, 1, tzinfo=UTC),
            date_end=datetime(2024, 12, 31, tzinfo=UTC),
            filters=(("country", ("USA", "DEU")),),
        )

        assert request1.cache_key == request2.cache_key
        assert hash(request1) == hash(request2)

    def test_filter_order_does_not_affect_hash(self) -> None:
        request1 = FetchRequest(
            dataset_id="test",
            filters=(("country", ("USA", "DEU")),),
        )
        request2 = FetchRequest(
            dataset_id="test",
            filters=(("country", ("DEU", "USA")),),
        )

        assert request1.cache_key == request2.cache_key
        assert request1.query_key == request2.query_key

    def test_different_params_different_hash(self) -> None:
        request1 = FetchRequest(
            dataset_id="test.dataset",
            date_start=datetime(2024, 1, 1, tzinfo=UTC),
        )
        request2 = FetchRequest(
            dataset_id="test.dataset",
            date_start=datetime(2025, 1, 1, tzinfo=UTC),
        )

        assert request1.cache_key != request2.cache_key

    def test_pagination_changes_request_key_only(self) -> None:
        base_request = FetchRequest(dataset_id="test.dataset")
        paged = base_request.with_pagination(page_size=100, page_token="next")

        assert base_request.query_key == paged.query_key
        assert base_request.request_key != paged.request_key

    def test_output_preferences_change_request_key_only(self) -> None:
        base_request = FetchRequest(dataset_id="test.dataset", include_metadata=True)
        altered = FetchRequest(dataset_id="test.dataset", include_metadata=False)

        assert base_request.query_key == altered.query_key
        assert base_request.request_key != altered.request_key

    def test_cache_key_format(self) -> None:
        request = FetchRequest(dataset_id="test")
        assert request.cache_key.startswith("sha256:")
        hex_part = request.cache_key.replace("sha256:", "")
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_request_immutability(self) -> None:
        request = FetchRequest(dataset_id="test")
        with pytest.raises(AttributeError):
            request.dataset_id = "modified"  # type: ignore[misc]

    def test_with_pagination_creates_new_request(self) -> None:
        original = FetchRequest(dataset_id="test", page_size=10)
        paginated = original.with_pagination(page_size=20, page_token="next")

        assert original.page_size == 10
        assert original.page_token is None
        assert paginated.page_size == 20
        assert paginated.page_token == "next"
        assert paginated.dataset_id == original.dataset_id

    def test_with_filter_creates_new_request(self) -> None:
        original = FetchRequest(dataset_id="test")
        filtered = original.with_filter("country", "USA", "DEU")

        assert original.filters == ()
        assert filtered.filters == (("country", ("DEU", "USA")),)

    def test_query_and_request_keys_are_precomputed_stably(self) -> None:
        request = FetchRequest(
            dataset_id="test.dataset",
            page_size=50,
            filters=(("country", ("USA", "DEU")),),
        )

        assert request.query_key == request._query_key
        assert request.request_key == request._request_key
        assert request.query_key.startswith("sha256:")
        assert request.request_key.startswith("sha256:")


class TestFetchResult:
    def test_valid_result_creation(self, sample_version: DataVersion) -> None:
        result = FetchResult(
            data=[{"a": 1}],
            row_count=1,
            schema_id="test.schema",
            schema_version="1.0",
            version=sample_version,
            fetched_at=datetime.now(UTC),
            completeness=0.95,
        )

        assert result.row_count == 1
        assert result.completeness == 0.95
        assert not result.has_more

    def test_completeness_validation(self, sample_version: DataVersion) -> None:
        with pytest.raises(ValueError):
            FetchResult(
                data=[],
                row_count=0,
                schema_id="test",
                schema_version="1.0",
                version=sample_version,
                fetched_at=datetime.now(UTC),
                completeness=1.5,
            )

    def test_is_complete_property(self, sample_version: DataVersion) -> None:
        result_complete = FetchResult(
            data=[],
            row_count=0,
            schema_id="test",
            schema_version="1.0",
            version=sample_version,
            fetched_at=datetime.now(UTC),
            completeness=1.0,
            has_more=False,
        )

        result_incomplete = FetchResult(
            data=[],
            row_count=0,
            schema_id="test",
            schema_version="1.0",
            version=sample_version,
            fetched_at=datetime.now(UTC),
            completeness=1.0,
            has_more=True,
        )

        assert result_complete.is_complete
        assert not result_incomplete.is_complete

    def test_is_high_quality_property(self, sample_version: DataVersion) -> None:
        high_quality = FetchResult(
            data=[],
            row_count=0,
            schema_id="test",
            schema_version="1.0",
            version=sample_version,
            fetched_at=datetime.now(UTC),
            completeness=0.98,
            quality_tier=QualityTier.GOLD,
            quality_flags=frozenset(),
        )

        low_quality = FetchResult(
            data=[],
            row_count=0,
            schema_id="test",
            schema_version="1.0",
            version=sample_version,
            fetched_at=datetime.now(UTC),
            completeness=0.80,
            quality_tier=QualityTier.BRONZE,
            quality_flags=frozenset({"missing_values"}),
        )

        assert high_quality.is_high_quality
        assert not low_quality.is_high_quality

    def test_structured_boundary_views(self, sample_version: DataVersion) -> None:
        fetched_at = datetime.now(UTC)
        result = FetchResult(
            data=[{"a": 1}],
            row_count=1,
            schema_id="test.schema",
            schema_version="1.0",
            version=sample_version,
            fetched_at=fetched_at,
            source_updated_at=fetched_at,
            completeness=0.98,
            quality_tier=QualityTier.GOLD,
            quality_flags=frozenset({"fresh"}),
            has_more=True,
            next_page_token="next",
            total_count=10,
            fetch_duration_ms=12.0,
            bytes_transferred=1024,
        )

        assert result.schema.schema_id == "test.schema"
        assert result.provenance.version == sample_version
        assert result.quality.quality_flags == frozenset({"fresh"})
        assert result.pagination.next_page_token == "next"
        assert result.transfer.bytes_transferred == 1024
        assert result.schema is result.schema
        assert result.provenance is result.provenance


class TestConnectionConfig:
    def test_redacted_hides_credentials(self, sample_config: ConnectionConfig) -> None:
        redacted = sample_config.redacted()

        assert redacted.auth_credentials == {"api_key": "***"}
        assert sample_config.auth_credentials["api_key"] == "test_secret_key_12345"

    def test_redacted_preserves_non_sensitive(self, sample_config: ConnectionConfig) -> None:
        redacted = sample_config.redacted()

        assert redacted.url == sample_config.url
        assert redacted.timeout_seconds == sample_config.timeout_seconds

    def test_config_immutability(self, sample_config: ConnectionConfig) -> None:
        with pytest.raises(AttributeError):
            sample_config.url = "modified"  # type: ignore[misc]


class TestDataVersion:
    def test_timestamp_comparison(self) -> None:
        older = DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value="2024-01-01",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        )
        newer = DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value="2024-06-01",
            timestamp=datetime(2024, 6, 1, tzinfo=UTC),
        )

        assert newer.is_newer_than(older)
        assert not older.is_newer_than(newer)

    def test_revision_comparison(self) -> None:
        v1 = DataVersion(
            strategy=VersionStrategy.REVISION,
            value="1",
            timestamp=datetime.now(UTC),
        )
        v2 = DataVersion(
            strategy=VersionStrategy.REVISION,
            value="2",
            timestamp=datetime.now(UTC),
        )

        assert v2.is_newer_than(v1)
        assert not v1.is_newer_than(v2)

    def test_content_hash_immutability(self) -> None:
        version = DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            timestamp=datetime.now(UTC),
        )

        with pytest.raises(Exception):
            version.value = "modified"  # type: ignore[misc]

    def test_timestamp_coerces_to_utc(self) -> None:
        naive = DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value="2024-01-01",
            timestamp=datetime(2024, 1, 1),
        )
        assert naive.timestamp.tzinfo is not None


class TestConnectorMetadataSpec:
    def test_fully_qualified_id(self, sample_metadata: ConnectorMetadataSpec) -> None:
        fqid = sample_metadata.fully_qualified_id
        assert fqid == "test.example.test_connector@1.0.0"

    def test_has_capability(self, sample_metadata: ConnectorMetadataSpec) -> None:
        assert sample_metadata.has_capability(ConnectorCapability.FULL_FETCH)
        assert sample_metadata.has_capability(ConnectorCapability.CATALOG_BROWSE)
        assert not sample_metadata.has_capability(ConnectorCapability.STREAMING)

    def test_id_pattern_validation(self) -> None:
        ConnectorMetadataSpec(
            connector_id="valid_id",
            version="1.0.0",
            namespace="test",
            source_name="Test",
            source_organization="Test",
        )

        with pytest.raises(ValueError):
            ConnectorMetadataSpec(
                connector_id="1invalid",
                version="1.0.0",
                namespace="test",
                source_name="Test",
                source_organization="Test",
            )

    def test_version_pattern_validation(self) -> None:
        ConnectorMetadataSpec(
            connector_id="test",
            version="1.0.0",
            namespace="test",
            source_name="Test",
            source_organization="Test",
        )

        ConnectorMetadataSpec(
            connector_id="test",
            version="12.34.56",
            namespace="test",
            source_name="Test",
            source_organization="Test",
        )

        with pytest.raises(ValueError):
            ConnectorMetadataSpec(
                connector_id="test",
                version="v1.0",
                namespace="test",
                source_name="Test",
                source_organization="Test",
            )

    def test_structured_boundary_views(self, sample_metadata: ConnectorMetadataSpec) -> None:
        assert sample_metadata.identity.connector_id == sample_metadata.connector_id
        assert sample_metadata.source.source_name == sample_metadata.source_name
        assert sample_metadata.governance.capabilities == sample_metadata.capabilities
        assert sample_metadata.documentation.description == sample_metadata.description
        assert sample_metadata.identity is sample_metadata.identity
        assert sample_metadata.operations is sample_metadata.operations


class TestErrorHierarchy:
    def test_error_inheritance(self) -> None:
        assert issubclass(CapabilityError, ConnectorError)
        assert issubclass(ConfigurationError, ConnectorError)
        assert issubclass(FetchError, ConnectorError)
        assert issubclass(RateLimitError, ConnectorError)

    def test_error_to_dict(self) -> None:
        error = FetchError(
            message="Dataset not found",
            connector_id="test.connector",
            dataset_id="missing.dataset",
        )

        error_dict = error.to_dict()
        assert error_dict["error_type"] == "FetchError"
        assert error_dict["connector_id"] == "test.connector"
        assert error_dict["message"] == "Dataset not found"
        assert error_dict["details"]["dataset_id"] == "missing.dataset"

    def test_rate_limit_error_details(self) -> None:
        error = RateLimitError(
            connector_id="test.connector",
            retry_after=60,
            limit_remaining=0,
            limit_total=100,
        )

        assert error.retry_after == 60
        error_dict = error.to_dict()
        assert error_dict["details"]["retry_after_seconds"] == 60
        assert error_dict["details"]["limit_remaining"] == 0


class TestValidationResult:
    def test_success_creation(self) -> None:
        result = ValidationResult.success()

        assert result.valid
        assert len(result.issues) == 0
        assert not result.has_errors
        assert not result.has_warnings

    def test_failure_creation(self) -> None:
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message="Missing required field",
            field="api_key",
        )
        result = ValidationResult.failure(issue)

        assert not result.valid
        assert len(result.issues) == 1
        assert result.has_errors

    def test_with_issue_adds_issue(self) -> None:
        original = ValidationResult.success()
        warning = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            message="Deprecated field",
        )

        updated = original.with_issue(warning)

        assert original.valid
        assert len(original.issues) == 0
        assert updated.valid
        assert len(updated.issues) == 1
        assert updated.has_warnings


class TestCapabilityHelpers:
    def test_capabilities_from_flags(self) -> None:
        bitmask = capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.STREAMING,
        )

        assert bitmask & ConnectorCapability.FULL_FETCH.value
        assert bitmask & ConnectorCapability.STREAMING.value
        assert not (bitmask & ConnectorCapability.CATALOG_BROWSE.value)

    def test_flags_from_capabilities(self) -> None:
        bitmask = ConnectorCapability.FULL_FETCH.value | ConnectorCapability.CATALOG_BROWSE.value
        flags = flags_from_capabilities(bitmask)

        assert ConnectorCapability.FULL_FETCH in flags
        assert ConnectorCapability.CATALOG_BROWSE in flags
        assert ConnectorCapability.STREAMING not in flags

    def test_roundtrip_conversion(self) -> None:
        original_caps = [
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.STREAMING,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ]

        bitmask = capabilities_from_flags(*original_caps)
        restored = flags_from_capabilities(bitmask)

        assert set(restored) == set(original_caps)


class TestConnectorIntegration:
    def test_full_fetch_workflow(self, sample_config: ConnectionConfig) -> None:
        async def _run() -> None:
            connector = CompliantConnector()

            handle = await connector.connect(sample_config)
            assert handle.connector_id == "test.compliant"

            health = await connector.health_check(handle)
            assert health.healthy

            request = FetchRequest(dataset_id="test.dataset")
            result = await connector.fetch(handle, request)

            assert result.row_count == 1
            assert result.completeness == 1.0

            await connector.disconnect(handle)

        asyncio.run(_run())

    def test_catalog_browse_workflow(self, sample_config: ConnectionConfig) -> None:
        async def _run() -> None:
            connector = CompliantConnector()
            handle = await connector.connect(sample_config)

            datasets = []
            async for dataset in connector.list_datasets(handle):
                datasets.append(dataset)

            assert len(datasets) == 1
            assert datasets[0].dataset_id == "test.dataset"

            await connector.disconnect(handle)

        asyncio.run(_run())

    def test_streaming_workflow(self, sample_config: ConnectionConfig) -> None:
        async def _run() -> None:
            connector = CompliantConnector()
            handle = await connector.connect(sample_config)

            request = FetchRequest(dataset_id="test.dataset")
            chunks = []
            async for chunk in connector.fetch_stream(handle, request):
                chunks.append(chunk)

            assert len(chunks) == 1
            assert chunks[0].is_first
            assert chunks[0].is_last

            await connector.disconnect(handle)

        asyncio.run(_run())

    def test_baseconnector_streaming_raises(self, sample_config: ConnectionConfig) -> None:
        async def _run() -> None:
            connector = BaseConnectorNoOverride()
            handle = await connector.connect(sample_config)

            with pytest.raises(NotImplementedError):
                async for _ in connector.fetch_stream(handle, FetchRequest(dataset_id="test")):
                    pass

            await connector.disconnect(handle)

        asyncio.run(_run())
