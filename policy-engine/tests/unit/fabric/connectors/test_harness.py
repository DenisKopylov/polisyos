"""
Tests for the Phase 2.10 Testing Infrastructure itself.

This file validates that the harness, simulator, fault injector, and
contract verifier all work correctly. It is a meta-test that proves the
machinery is sound before connector developers start using it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd
import pytest
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)
from polisyos.fabric.connectors.testing import (
    APISimulator,
    ConnectorTestHarness,
    ContractViolation,
    FaultInjector,
    FaultProfile,
    FaultSequence,
    SimulatorFixture,
    SimulatorMode,
    assert_schema_compliance,
)
from polisyos.fabric.connectors.testing.contracts import generate_dataframe_for_schema
from polisyos.fabric.connectors.testing.fixtures import SimulatedHTTPError
from polisyos.fabric.connectors.testing.simulator import (
    _canonicalize_url,
    _request_hash,
)
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
)

# =============================================================================
# Stub connector -- passes all compliance checks
# =============================================================================

_FIXED_VERSION = DataVersion(
    strategy=VersionStrategy.TIMESTAMP,
    value="2024-06-15T12:00:00+00:00",
    timestamp=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
)

_FIXED_DATA = [
    {"id": 1, "country_code": "US", "value": 100.0},
    {"id": 2, "country_code": "DE", "value": 200.0},
]


class StubConnector:
    """
    Minimal connector that satisfies the full SourceConnector protocol.

    Used as the target for harness compliance tests. All behaviour
    is deterministic -- no randomness, no timestamps that change.
    """

    connector_id: ClassVar[str] = "test.stub"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="stub",
        version="1.0.0",
        namespace="test",
        source_name="Stub Source",
        source_organization="Test Org",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=ConnectorCapability.FULL_FETCH.value,
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    async def disconnect(self, handle: ConnectionHandle) -> None:
        return None

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        return HealthStatus(healthy=True, message="OK", latency_ms=1.2)

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult:
        return FetchResult(
            data=_FIXED_DATA,
            row_count=len(_FIXED_DATA),
            schema_id="test.stub.dataset",
            schema_version="1.0.0",
            version=_FIXED_VERSION,
            fetched_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC),
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
        )

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> Any:
        class _Result:
            valid = True
            issues: list[str] = []

        return _Result()


# =============================================================================
# Harness compliance tests (using the StubConnector)
# =============================================================================


_STUB_SCHEMA = DataSchema(
    schema_id="test.stub.dataset",
    version=SchemaVersion(1, 0, 0),
    fields=(
        FieldSpec(name="id", data_type=SchemaType.INT64, nullable=False),
        FieldSpec(name="country_code", data_type=SchemaType.STRING, nullable=False),
        FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=True, bounds=(0.0, None)),
    ),
    primary_key=("id",),
)


class TestStubConnectorCompliance(ConnectorTestHarness):
    """Point the harness at StubConnector. All inherited tests should pass."""

    connector_class = StubConnector  # type: ignore[assignment]
    sample_config = ConnectionConfig(url="http://localhost:9999/stub")
    sample_schema = _STUB_SCHEMA
    sample_request = FetchRequest(dataset_id="test.stub.dataset")


# =============================================================================
# Harness violation detection
# =============================================================================


class SyncMethodsConnector:
    """A connector where methods are NOT async -- harness must catch this."""

    connector_id: ClassVar[str] = "test.sync_broken"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="sync_broken",
        version="1.0.0",
        namespace="test",
        source_name="Broken",
        source_organization="Test",
        trust_level=TrustLevel.LOW,
        quality_tier=QualityTier.BRONZE,
        capabilities=ConnectorCapability.FULL_FETCH.value,
    )

    def connect(self, config: ConnectionConfig) -> ConnectionHandle:  # type: ignore[override]
        return ConnectionHandle(connector_id=self.connector_id, config=config)

    def disconnect(self, handle: ConnectionHandle) -> None:  # type: ignore[override]
        pass

    def health_check(self, handle: ConnectionHandle) -> HealthStatus:  # type: ignore[override]
        return HealthStatus(healthy=True)

    def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult:  # type: ignore[override]
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="x",
            schema_version="1.0",
            version=_FIXED_VERSION,
            fetched_at=datetime.now(UTC),
            completeness=1.0,
        )


class TestHarnessDetectsViolations:
    """Verify that the harness correctly flags non-compliant connectors."""

    def test_detects_sync_methods(self) -> None:
        """Sync methods must be caught by test_core_methods_are_async."""
        harness = ConnectorTestHarness()
        harness.connector_class = SyncMethodsConnector  # type: ignore[assignment]

        with pytest.raises(AssertionError, match="must be async"):
            harness.test_core_methods_are_async()

    def test_detects_missing_attribute(self) -> None:
        """A connector missing 'metadata' must be caught."""

        class NoMetadata:
            connector_id = "test.no_meta"
            capabilities = ConnectorCapability.FULL_FETCH

            async def connect(self, config): ...
            async def disconnect(self, handle): ...
            async def health_check(self, handle): ...
            async def fetch(self, handle, request): ...

        harness = ConnectorTestHarness()
        harness.connector_class = NoMetadata  # type: ignore[assignment]

        with pytest.raises(AssertionError, match="missing required class attribute 'metadata'"):
            harness.test_required_class_attributes()


# =============================================================================
# APISimulator tests
# =============================================================================


class TestAPISimulatorReplay:
    """Test REPLAY mode with pre-written fixtures."""

    @pytest.fixture
    def fixture_dir(self, tmp_path: Path) -> tuple[Path, str, str]:
        """Create a temporary fixture directory with one sample fixture."""
        connector_id = "test_connector"
        dataset_id = "test_dataset"
        connector_dir = tmp_path / connector_id / dataset_id
        connector_dir.mkdir(parents=True)

        fixture = SimulatorFixture(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=__import__("base64").b64encode(b'[{"id": 1}]').decode(),
            captured_at="2024-01-01T00:00:00+00:00",
            request_url="http://localhost/api",
            request_method="GET",
            request_hash="placeholder",  # will be overwritten
            connector_id=connector_id,
            dataset_id=dataset_id,
        )
        canonical_url = _canonicalize_url("http://localhost/api", None)
        real_hash = _request_hash("GET", canonical_url, "none", b"")
        fixture = SimulatorFixture(**{**fixture.to_dict(), "request_hash": real_hash})
        fixture.write(connector_dir / f"{real_hash}.json")

        return tmp_path, connector_id, dataset_id

    @pytest.mark.asyncio
    async def test_replay_serves_fixture(self, fixture_dir: tuple[Path, str, str]) -> None:
        """REPLAY mode returns the captured response."""
        root, connector_id, dataset_id = fixture_dir
        sim = APISimulator(
            mode=SimulatorMode.REPLAY,
            fixture_root=root,
            connector_id=connector_id,
            dataset_id=dataset_id,
        )
        async with sim:
            response = await sim._handle_request("GET", "http://localhost/api")
            body = await response.json()
            assert body == [{"id": 1}]
            assert response.status == 200

    @pytest.mark.asyncio
    async def test_replay_fails_on_missing_fixture(self, tmp_path: Path) -> None:
        """REPLAY mode must fail hard when no fixture exists."""
        from polisyos.fabric.connectors.testing.simulator import MissingFixtureError

        sim = APISimulator(
            mode=SimulatorMode.REPLAY,
            fixture_root=tmp_path,
            connector_id="empty_connector",
            dataset_id="missing_dataset",
        )
        async with sim:
            with pytest.raises(MissingFixtureError, match="No fixture found"):
                await sim._handle_request("GET", "http://localhost/missing")

    def test_request_hash_includes_params(self) -> None:
        """Distinct params should yield distinct request hashes."""
        url = "http://localhost/api"
        h1 = _request_hash("GET", _canonicalize_url(url, {"q": "a"}), "none", b"")
        h2 = _request_hash("GET", _canonicalize_url(url, {"q": "b"}), "none", b"")
        assert h1 != h2

        h3 = _request_hash("GET", _canonicalize_url(url, {"b": 2, "a": 1}), "none", b"")
        h4 = _request_hash("GET", _canonicalize_url(url, {"a": 1, "b": 2}), "none", b"")
        assert h3 == h4


class TestAPISimulatorSynthetic:
    """Test SYNTHETIC mode generates schema-conformant data."""

    @pytest.mark.asyncio
    async def test_synthetic_generates_valid_json(self, sample_schema: DataSchema) -> None:
        """SYNTHETIC response body must be valid JSON array."""
        sim = APISimulator(
            mode=SimulatorMode.SYNTHETIC,
            schema=sample_schema,
        )
        async with sim:
            response = await sim._handle_request("GET", "http://localhost/data")
            body = await response.json()
            assert isinstance(body, list)
            assert len(body) == 100  # default num_rows

    @pytest.mark.asyncio
    async def test_synthetic_requires_schema(self) -> None:
        """SYNTHETIC mode without a schema must raise ValueError."""
        sim = APISimulator(mode=SimulatorMode.SYNTHETIC, schema=None)
        async with sim:
            with pytest.raises(ValueError, match="SYNTHETIC mode requires"):
                await sim._handle_request("GET", "http://localhost/data")


class TestAPISimulatorCallLog:
    """Test the call-log assertion helpers."""

    @pytest.mark.asyncio
    async def test_call_count_tracks_requests(self, tmp_path: Path) -> None:
        """call_count must increment for each intercepted request."""
        connector_id = "log_test"
        dataset_id = "log_dataset"

        for url in ("http://localhost/a", "http://localhost/b"):
            h = _request_hash("GET", _canonicalize_url(url, None), "none", b"")
            fixture = SimulatorFixture(
                status_code=200,
                headers={},
                body=__import__("base64").b64encode(b"{}").decode(),
                captured_at="2024-01-01T00:00:00Z",
                request_url=url,
                request_method="GET",
                request_hash=h,
                connector_id=connector_id,
                dataset_id=dataset_id,
            )
            fixture.write(tmp_path / connector_id / dataset_id / f"{h}.json")

        sim = APISimulator(
            mode=SimulatorMode.REPLAY,
            fixture_root=tmp_path,
            connector_id=connector_id,
            dataset_id=dataset_id,
        )
        async with sim:
            await sim._handle_request("GET", "http://localhost/a")
            await sim._handle_request("GET", "http://localhost/b")
            assert sim.call_count == 2

    @pytest.mark.asyncio
    async def test_assert_called_with_passes(self, tmp_path: Path) -> None:
        """assert_called_with must pass when the URL was hit."""
        connector_id = "assert_test"
        dataset_id = "assert_dataset"
        url = "http://localhost/target"
        h = _request_hash("GET", _canonicalize_url(url, None), "none", b"")
        fixture = SimulatorFixture(
            status_code=200,
            headers={},
            body=__import__("base64").b64encode(b"{}").decode(),
            captured_at="2024-01-01T00:00:00Z",
            request_url=url,
            request_method="GET",
            request_hash=h,
            connector_id=connector_id,
            dataset_id=dataset_id,
        )
        fixture.write(tmp_path / connector_id / dataset_id / f"{h}.json")

        sim = APISimulator(
            mode=SimulatorMode.REPLAY,
            fixture_root=tmp_path,
            connector_id=connector_id,
            dataset_id=dataset_id,
        )
        async with sim:
            await sim._handle_request("GET", url)
            sim.assert_called_with(_canonicalize_url(url, None), "GET")


# =============================================================================
# FaultSequence unit tests
# =============================================================================


class TestFaultSequence:
    """Unit tests for the FaultSequence cursor logic."""

    def test_single_profile_consumed(self) -> None:
        """A profile with count=2 yields exactly 2 faults."""
        seq = FaultSequence([FaultProfile(kind="error", status_code=500, count=2)])

        assert seq.next_fault() is not None
        assert seq.next_fault() is not None
        assert seq.next_fault() is None  # exhausted

    def test_multi_profile_ordering(self) -> None:
        """Profiles are consumed in declaration order."""
        seq = FaultSequence(
            [
                FaultProfile(kind="error", status_code=503, count=1),
                FaultProfile(kind="latency", latency_ms=100, count=1),
                FaultProfile(kind="disconnect", count=1),
            ]
        )

        f1 = seq.next_fault()
        assert f1 is not None and f1.kind == "error" and f1.status_code == 503

        f2 = seq.next_fault()
        assert f2 is not None and f2.kind == "latency"

        f3 = seq.next_fault()
        assert f3 is not None and f3.kind == "disconnect"

        assert seq.next_fault() is None

    def test_count_zero_repeats_forever(self) -> None:
        """count=0 means infinite repetition."""
        seq = FaultSequence([FaultProfile(kind="error", status_code=429, count=0)])

        for _ in range(50):
            fault = seq.next_fault()
            assert fault is not None
            assert fault.status_code == 429

    def test_reset_rewinds(self) -> None:
        """reset() returns the sequence to the start."""
        seq = FaultSequence([FaultProfile(kind="error", status_code=500, count=1)])

        seq.next_fault()
        assert seq.is_exhausted

        seq.reset()
        assert not seq.is_exhausted
        assert seq.next_fault() is not None

    def test_invalid_kind_raises(self) -> None:
        """FaultProfile rejects unknown kind values."""
        with pytest.raises(ValueError, match="Invalid fault kind"):
            FaultProfile(kind="magic")

    def test_latency_requires_positive_ms(self) -> None:
        """latency_ms must be > 0 for kind=latency."""
        with pytest.raises(ValueError, match="latency_ms must be > 0"):
            FaultProfile(kind="latency", latency_ms=0)

    def test_error_requires_valid_status(self) -> None:
        """status_code must be >= 400 for kind=error."""
        with pytest.raises(ValueError, match="status_code must be >= 400"):
            FaultProfile(kind="error", status_code=200)


# =============================================================================
# FaultInjector integration tests
# =============================================================================


class TestFaultInjector:
    """Integration tests: injector + stub connector + resilience interaction."""

    @pytest.fixture
    def stub(self) -> StubConnector:
        return StubConnector()

    @pytest.fixture
    def handle(self) -> ConnectionHandle:
        return ConnectionHandle(
            connector_id="test.stub",
            config=ConnectionConfig(url="http://localhost"),
        )

    @pytest.fixture
    def fetch_request(self) -> FetchRequest:
        return FetchRequest(dataset_id="test.stub.dataset")

    @pytest.mark.asyncio
    async def test_error_injection(
        self, stub: StubConnector, handle: ConnectionHandle, fetch_request: FetchRequest
    ) -> None:
        """SimulatedHTTPError is raised for error faults."""
        injector = FaultInjector.with_error(stub, status_code=503, count=2)

        with pytest.raises(SimulatedHTTPError) as exc_info:
            await injector.fetch(handle, fetch_request)
        assert exc_info.value.status == 503

        # Second call also fails
        with pytest.raises(SimulatedHTTPError):
            await injector.fetch(handle, fetch_request)

        # Third call succeeds (sequence exhausted)
        result = await injector.fetch(handle, fetch_request)
        assert isinstance(result, FetchResult)
        assert injector.faulted_calls == 2

    @pytest.mark.asyncio
    async def test_disconnect_injection(
        self, stub: StubConnector, handle: ConnectionHandle, fetch_request: FetchRequest
    ) -> None:
        """ConnectionError is raised for disconnect faults."""
        injector = FaultInjector.with_disconnect(stub, count=1)

        with pytest.raises(ConnectionError, match="Simulated TCP disconnect"):
            await injector.fetch(handle, fetch_request)

        # Next call passes through
        result = await injector.fetch(handle, fetch_request)
        assert isinstance(result, FetchResult)

    @pytest.mark.asyncio
    async def test_latency_injection(
        self, stub: StubConnector, handle: ConnectionHandle, fetch_request: FetchRequest
    ) -> None:
        """Latency faults delay but still return a result."""
        import time

        injector = FaultInjector.with_latency(stub, latency_ms=50, count=1)

        start = time.monotonic()
        result = await injector.fetch(handle, fetch_request)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert isinstance(result, FetchResult)
        assert elapsed_ms >= 40  # Allow small timing tolerance

    @pytest.mark.asyncio
    async def test_mixed_sequence(
        self, stub: StubConnector, handle: ConnectionHandle, fetch_request: FetchRequest
    ) -> None:
        """A multi-profile sequence fires in order."""
        injector = FaultInjector(
            connector=stub,
            sequence=FaultSequence(
                [
                    FaultProfile(kind="error", status_code=429, count=1),
                    FaultProfile(kind="disconnect", count=1),
                ]
            ),
        )

        with pytest.raises(SimulatedHTTPError) as exc:
            await injector.fetch(handle, fetch_request)
        assert exc.value.status == 429

        with pytest.raises(ConnectionError):
            await injector.fetch(handle, fetch_request)

        result = await injector.fetch(handle, fetch_request)
        assert isinstance(result, FetchResult)

    @pytest.mark.asyncio
    async def test_observability_counters(
        self, stub: StubConnector, handle: ConnectionHandle, fetch_request: FetchRequest
    ) -> None:
        """total_calls and faulted_calls track correctly."""
        injector = FaultInjector.with_error(stub, status_code=500, count=2)

        for _ in range(2):
            with pytest.raises(SimulatedHTTPError):
                await injector.fetch(handle, fetch_request)

        await injector.fetch(handle, fetch_request)  # clean call

        assert injector.total_calls == 3
        assert injector.faulted_calls == 2
        assert injector.sequence_exhausted


# =============================================================================
# Contract verification tests
# =============================================================================


class TestContractVerification:
    """Validate assert_schema_compliance against good and bad data."""

    @pytest.fixture
    def schema(self) -> DataSchema:
        return DataSchema(
            schema_id="test.contract",
            version=SchemaVersion(1, 0, 0),
            fields=(
                FieldSpec(name="id", data_type=SchemaType.INT64, nullable=False),
                FieldSpec(
                    name="value", data_type=SchemaType.FLOAT64, nullable=True, bounds=(0.0, 100.0)
                ),
                FieldSpec(
                    name="label",
                    data_type=SchemaType.CATEGORY,
                    nullable=False,
                    allowed_values=frozenset({"A", "B", "C"}),
                ),
            ),
            required_completeness=0.90,
            allowed_null_fields=frozenset({"value"}),
        )

    def test_valid_data_passes(self, schema: DataSchema) -> None:
        """Conforming data must not raise."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "value": [10.0, 50.0, 99.9],
                "label": ["A", "B", "C"],
            }
        )
        assert_schema_compliance(df, schema)

    def test_missing_column_raises(self, schema: DataSchema) -> None:
        """A missing required column must trigger ContractViolation."""
        df = pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0]})

        with pytest.raises(ContractViolation, match="Missing"):
            assert_schema_compliance(df, schema)

    def test_null_in_non_nullable_raises(self, schema: DataSchema) -> None:
        """Nulls in a non-nullable column must be caught."""
        df = pd.DataFrame(
            {
                "id": [1, None, 3],
                "value": [1.0, 2.0, 3.0],
                "label": ["A", "B", "C"],
            }
        )

        with pytest.raises(ContractViolation, match="null"):
            assert_schema_compliance(df, schema)

    def test_out_of_bounds_raises(self, schema: DataSchema) -> None:
        """Values outside declared bounds must be caught."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "value": [10.0, 200.0, 50.0],
                "label": ["A", "B", "C"],
            }
        )

        with pytest.raises(ContractViolation, match="bound"):
            assert_schema_compliance(df, schema)

    def test_invalid_category_raises(self, schema: DataSchema) -> None:
        """Values outside allowed_values must be caught."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "value": [10.0, 20.0, 30.0],
                "label": ["A", "B", "INVALID"],
            }
        )

        with pytest.raises(ContractViolation, match="invalid values"):
            assert_schema_compliance(df, schema)

    def test_context_attached_to_violation(self, schema: DataSchema) -> None:
        """Context dict must appear in the exception."""
        df = pd.DataFrame({"id": [1], "value": [1.0]})

        with pytest.raises(ContractViolation) as exc_info:
            assert_schema_compliance(
                df,
                schema,
                context={"connector_id": "test.ctx", "dataset": "my_data"},
            )
        violation_str = str(exc_info.value)
        assert "connector_id=test.ctx" in violation_str
        assert "dataset=my_data" in violation_str


# =============================================================================
# Synthetic data generation tests
# =============================================================================


class TestSyntheticGeneration:
    """Validate that generated DataFrames conform to their source schema."""

    @pytest.fixture
    def rich_schema(self) -> DataSchema:
        """Schema with every constraint type exercised."""
        return DataSchema(
            schema_id="test.synthetic.rich",
            version=SchemaVersion(1, 0, 0),
            fields=(
                FieldSpec(name="id", data_type=SchemaType.INT64, nullable=False),
                FieldSpec(
                    name="score", data_type=SchemaType.FLOAT64, nullable=True, bounds=(0.0, 100.0)
                ),
                FieldSpec(
                    name="tag",
                    data_type=SchemaType.CATEGORY,
                    nullable=False,
                    allowed_values=frozenset({"alpha", "beta", "gamma"}),
                ),
                FieldSpec(name="active", data_type=SchemaType.BOOLEAN, nullable=False),
                FieldSpec(name="name", data_type=SchemaType.STRING, nullable=True, max_length=20),
            ),
            allowed_null_fields=frozenset({"score", "name"}),
            required_completeness=0.80,
        )

    def test_generated_shape(self, rich_schema: DataSchema) -> None:
        """Output must have the right number of rows and columns."""
        df = generate_dataframe_for_schema(rich_schema, num_rows=42, seed=7)
        assert len(df) == 42
        assert set(df.columns) == {"id", "score", "tag", "active", "name"}

    def test_generated_categories_in_allowed_set(self, rich_schema: DataSchema) -> None:
        """All category values must be within allowed_values."""
        df = generate_dataframe_for_schema(rich_schema, num_rows=200, seed=42)
        non_null_tags = df["tag"].dropna()
        assert set(non_null_tags.unique()).issubset({"alpha", "beta", "gamma"})

    def test_generated_booleans_are_bool(self, rich_schema: DataSchema) -> None:
        """Boolean column must contain only True/False/None."""
        df = generate_dataframe_for_schema(rich_schema, num_rows=100, seed=1)
        non_null = df["active"].dropna()
        assert all(isinstance(v, (bool, np.bool_)) for v in non_null)

    def test_reproducibility_with_seed(self, rich_schema: DataSchema) -> None:
        """Same seed must produce identical DataFrames."""
        df1 = generate_dataframe_for_schema(rich_schema, num_rows=10, seed=99)
        df2 = generate_dataframe_for_schema(rich_schema, num_rows=10, seed=99)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_differ(self, rich_schema: DataSchema) -> None:
        """Different seeds must (almost certainly) produce different data."""
        df1 = generate_dataframe_for_schema(rich_schema, num_rows=50, seed=1)
        df2 = generate_dataframe_for_schema(rich_schema, num_rows=50, seed=2)
        assert not df1.equals(df2)

    def test_nullable_columns_have_nulls(self, rich_schema: DataSchema) -> None:
        """With enough rows, nullable columns should contain at least one null."""
        df = generate_dataframe_for_schema(rich_schema, num_rows=500, seed=42)
        assert df["score"].isna().any(), "Nullable 'score' should have nulls in 500 rows"
        assert df["name"].isna().any(), "Nullable 'name' should have nulls in 500 rows"

    def test_non_nullable_columns_have_no_nulls(self, rich_schema: DataSchema) -> None:
        """Non-nullable columns must never contain nulls."""
        df = generate_dataframe_for_schema(rich_schema, num_rows=200, seed=42)
        assert not df["id"].isna().any()
        assert not df["tag"].isna().any()
        assert not df["active"].isna().any()


# =============================================================================
# SimulatorFixture serialisation round-trip
# =============================================================================


class TestSimulatorFixtureSerialization:
    """Verify fixture write -> read round-trip integrity."""

    def test_roundtrip(self, tmp_path: Path) -> None:
        """Writing and reading a fixture must produce an identical object."""
        import base64

        original = SimulatorFixture(
            status_code=201,
            headers={"X-Custom": "value", "Content-Type": "text/plain"},
            body=base64.b64encode(b"hello world").decode(),
            captured_at="2024-03-15T10:30:00+00:00",
            request_url="https://api.example.com/data",
            request_method="POST",
            request_hash="abc123" * 10 + "abcd",
            connector_id="example.connector",
            dataset_id="example.dataset",
        )

        path = tmp_path / "test_fixture.json"
        original.write(path)
        loaded = SimulatorFixture.read(path)

        assert loaded == original

    def test_body_decode(self) -> None:
        """body_bytes and body_text must correctly decode base64."""
        import base64

        raw = b"test payload \xc3\xa9"
        fixture = SimulatorFixture(
            status_code=200,
            headers={},
            body=base64.b64encode(raw).decode(),
            captured_at="",
            request_url="",
            request_method="GET",
            request_hash="",
        )
        assert fixture.body_bytes == raw
        assert fixture.body_text == raw.decode("utf-8")
