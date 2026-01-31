"""
ConnectorTestHarness -- pytest-compatible compliance base class.

Every concrete connector test suite inherits from this class. The harness
automatically exercises the four pillars of connector compliance:

    1. Protocol shape    -- class attributes + async method signatures
    2. Lifecycle safety  -- connect -> health_check -> disconnect round-trip
    3. Result structure  -- FetchResult fields, schema compliance, DataVersion
    4. Determinism       -- idempotency of fetch (same input => same content hash)

Design decisions
----------------
* Uses pytest fixtures, marks, and parametrize -- no custom runner.
* connector_instance and connection_handle are pytest fixtures so subclasses
  can override them with DI wrappers.
* All I/O methods are async; the harness is decorated with @pytest.mark.asyncio.
* Protocol compliance delegates to validate_protocol_compliance() from Phase 2.1.
* Hash comparison in test_idempotency uses FetchResult.content_hash when present;
  otherwise falls back to a stable SHA-256 over canonical JSON for data.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from datetime import datetime, timezone
from typing import Any, ClassVar, Type

import pytest

from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
    SourceConnector,
)
from polisyos.fabric.connectors.capabilities import validate_protocol_compliance
from polisyos.fabric.connectors.contracts.schema import DataSchema
from polisyos.fabric.connectors.testing.contracts import assert_schema_compliance
from polisyos.ir.connectors import ConnectorCapability, DataVersion, VersionStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_records(data: Any) -> list[dict[str, Any]]:
    """
    Convert data payload into a list-of-dicts.

    Accepts pandas DataFrame or list-of-dicts. Raises TypeError otherwise.
    """
    try:
        import pandas as pd  # noqa: F401

        if hasattr(data, "to_dict"):
            return data.to_dict(orient="records")
    except Exception:
        pass

    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return data

    raise TypeError(
        "FetchResult.data must be a DataFrame or list-of-dicts to validate schema."
    )


def _sorted_records_by_pk(records: list[dict[str, Any]], pk: tuple[str, ...]) -> list[dict[str, Any]]:
    """Return records sorted deterministically by primary key, if possible."""
    if not pk:
        return records

    def _key(rec: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(rec.get(field) for field in pk)

    # Only sort if all PK fields exist in every record
    if all(all(field in rec for field in pk) for rec in records):
        return sorted(records, key=_key)

    return records


def _stable_hash(data: Any, schema: DataSchema | None = None) -> str:
    """
    Produce a deterministic SHA-256 fingerprint for arbitrary data.

    Handles pandas DataFrames, lists-of-dicts, and anything that json.dumps can
    serialise (with sort_keys). For DataFrames we convert to records first so the
    hash is independent of index state. If schema.primary_key is set, records are
    sorted by that key before hashing to avoid order-related nondeterminism.
    """
    payload: Any

    try:
        import pandas as pd  # noqa: F401

        if hasattr(data, "to_dict"):
            records = data.to_dict(orient="records")
            if schema and schema.primary_key:
                records = _sorted_records_by_pk(records, schema.primary_key)
            payload = records
        else:
            payload = data
    except ImportError:  # pragma: no cover
        payload = data

    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        if schema and schema.primary_key:
            payload = _sorted_records_by_pk(payload, schema.primary_key)

    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _minimal_version() -> DataVersion:
    """Return a structurally valid DataVersion for assertion checks."""
    return DataVersion(
        strategy=VersionStrategy.TIMESTAMP,
        value=datetime.now(timezone.utc).isoformat(),
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Required capability -> method mapping (mirrors Phase 2.1 capabilities.py)
# ---------------------------------------------------------------------------

_CAPABILITY_METHODS: dict[ConnectorCapability, str] = {
    ConnectorCapability.CATALOG_BROWSE: "list_datasets",
    ConnectorCapability.STREAMING: "fetch_stream",
    ConnectorCapability.FRESHNESS_CHECK: "check_freshness",
    ConnectorCapability.SCHEMA_INTROSPECTION: "get_dataset_schema",
}


# ---------------------------------------------------------------------------
# ConnectorTestHarness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class ConnectorTestHarness:
    """
    Abstract pytest base class for connector compliance testing.

    Subclasses set class-level attributes and inherit a rich suite of
    test_* methods. Pytest discovers every test automatically.
    """

    # ------------------------------------------------------------------
    # Subclass MUST set these
    # ------------------------------------------------------------------
    connector_class: ClassVar[Type[SourceConnector]]
    sample_config: ClassVar[ConnectionConfig]
    sample_schema: ClassVar[DataSchema]
    sample_request: ClassVar[FetchRequest]

    # ------------------------------------------------------------------
    # Fixtures -- override for DI
    # ------------------------------------------------------------------

    @pytest.fixture()
    def connector_instance(self) -> SourceConnector:
        """
        Instantiate the connector under test.

        Override this fixture to inject mocks, simulators, or
        dependency-injected collaborators.
        """
        return self.connector_class()

    @pytest.fixture()
    async def connection_handle(self, connector_instance: SourceConnector) -> ConnectionHandle:
        """
        Perform connect() and return the live handle.

        The handle is used by lifecycle and fetch tests. Teardown
        (disconnect) happens in the connected fixture.
        """
        return await connector_instance.connect(self.sample_config)

    @pytest.fixture()
    async def connected(
        self,
        connector_instance: SourceConnector,
        connection_handle: ConnectionHandle,
    ):
        """
        Context fixture: yields (connector, handle), disconnects after test.

        All tests that need a live connection should request this fixture
        rather than connection_handle directly.
        """
        yield connector_instance, connection_handle
        # Guaranteed teardown -- even if the test body raises
        try:
            await connector_instance.disconnect(connection_handle)
        except Exception:  # pragma: no cover -- best-effort teardown
            pass

    # ==================================================================
    # 1. PROTOCOL COMPLIANCE
    # ==================================================================

    def test_protocol_compliance(self) -> None:
        """
        Verify all required class attributes and async method signatures.

        Delegates to validate_protocol_compliance() (Phase 2.1) which checks:
            - connector_id, capabilities, metadata class attributes exist
            - connect / disconnect / health_check / fetch are async
            - capability-gated methods exist when the capability flag is set
        """
        violations = validate_protocol_compliance(self.connector_class)
        assert violations == [], (
            f"Protocol violations in {self.connector_class.__name__}:\n"
            + "\n".join(f"  -  {v}" for v in violations)
        )

    def test_required_class_attributes(self) -> None:
        """
        Independently assert the three mandatory class attributes.

        Provides a clearer error message than the generic protocol check
        when a developer forgets metadata.
        """
        for attr in ("connector_id", "capabilities", "metadata"):
            assert hasattr(self.connector_class, attr), (
                f"{self.connector_class.__name__} is missing required "
                f"class attribute '{attr}'."
            )

    def test_core_methods_are_async(self) -> None:
        """
        Each core method must be a coroutine function.

        Sync implementations silently pass duck-typing but break at await time.
        This test catches that early.
        """
        for method_name in ("connect", "disconnect", "health_check", "fetch"):
            method = getattr(self.connector_class, method_name, None)
            assert method is not None, (
                f"Missing method '{method_name}' on {self.connector_class.__name__}"
            )
            assert inspect.iscoroutinefunction(method), (
                f"Method '{method_name}' on {self.connector_class.__name__} "
                f"must be async (a coroutine function)."
            )

    def test_capability_gated_methods_present(self) -> None:
        """
        For each declared capability, verify the required method exists.

        E.g. if STREAMING is in capabilities, fetch_stream must be
        defined and must be async.
        """
        caps = self.connector_class.capabilities
        for cap, method_name in _CAPABILITY_METHODS.items():
            if caps & cap:
                method = getattr(self.connector_class, method_name, None)
                assert method is not None, (
                    f"Capability {cap.name} declared but method "
                    f"'{method_name}' is missing."
                )
                assert inspect.iscoroutinefunction(method), (
                    f"Capability-gated method '{method_name}' must be async."
                )

    # ==================================================================
    # 2. CONNECTION LIFECYCLE
    # ==================================================================

    async def test_connection_lifecycle(self, connector_instance: SourceConnector) -> None:
        """
        Full lifecycle: connect -> health_check -> disconnect.

        Assertions:
            - connect() returns a ConnectionHandle with matching connector_id
            - health_check() returns HealthStatus(healthy=True)
            - disconnect() completes without raising
        """
        handle = await connector_instance.connect(self.sample_config)

        # --- handle contract ---
        assert isinstance(handle, ConnectionHandle), (
            "connect() must return a ConnectionHandle instance."
        )
        assert handle.connector_id == self.connector_class.connector_id, (
            f"Handle connector_id '{handle.connector_id}' does not match "
            f"declared connector_id '{self.connector_class.connector_id}'."
        )
        assert handle.config == self.sample_config, (
            "Handle config must echo the ConnectionConfig that was passed in."
        )
        assert handle.session_id, "Handle must have a non-empty session_id."

        # --- health check ---
        health: HealthStatus = await connector_instance.health_check(handle)
        assert isinstance(health, HealthStatus), (
            "health_check() must return a HealthStatus instance."
        )
        assert health.healthy is True, (
            f"health_check() reported unhealthy: {health.message}"
        )

        # --- teardown ---
        await connector_instance.disconnect(handle)
        # No assertion needed -- absence of exception IS the assertion.

    async def test_connect_returns_unique_sessions(
        self, connector_instance: SourceConnector
    ) -> None:
        """
        Two connect() calls must produce distinct session_ids.

        This guards against connectors that accidentally return a
        singleton handle, which would break concurrent usage.
        """
        h1 = await connector_instance.connect(self.sample_config)
        h2 = await connector_instance.connect(self.sample_config)

        assert h1.session_id != h2.session_id, (
            "connect() must produce unique session_ids on each call."
        )

        await connector_instance.disconnect(h1)
        await connector_instance.disconnect(h2)

    async def test_disconnect_idempotent(self, connector_instance: SourceConnector) -> None:
        """
        disconnect() should be safe to call multiple times.

        This mirrors real-world finally-block usage where cleanup may
        be invoked defensively.
        """
        handle = await connector_instance.connect(self.sample_config)
        await connector_instance.disconnect(handle)
        await connector_instance.disconnect(handle)

    # ==================================================================
    # 3. FETCH STRUCTURE VALIDATION
    # ==================================================================

    async def test_fetch_returns_fetch_result(self, connected: tuple) -> None:
        """fetch() must return a FetchResult with correct generic structure."""
        connector, handle = connected
        result = await connector.fetch(handle, self.sample_request)

        assert isinstance(result, FetchResult), (
            f"fetch() returned {type(result).__name__}, expected FetchResult."
        )

    async def test_fetch_result_has_valid_version(self, connected: tuple) -> None:
        """
        FetchResult.version must be a well-formed DataVersion.

        Checks that strategy is a known VersionStrategy and that value
        is non-empty.
        """
        connector, handle = connected
        result: FetchResult = await connector.fetch(handle, self.sample_request)

        assert result.version is not None, (
            "FetchResult.version must not be None."
        )
        assert isinstance(result.version, DataVersion), (
            "FetchResult.version must be a DataVersion instance."
        )
        assert result.version.value, (
            "DataVersion.value must be a non-empty string."
        )
        # Verify strategy is a recognised enum value
        assert isinstance(result.version.strategy, VersionStrategy), (
            f"DataVersion.strategy '{result.version.strategy}' is not a "
            f"valid VersionStrategy."
        )

    async def test_fetch_result_schema_fields(self, connected: tuple) -> None:
        """
        FetchResult must carry schema_id and schema_version.

        These fields are required for downstream schema validation and
        CAS-based caching (Law D).
        """
        connector, handle = connected
        result: FetchResult = await connector.fetch(handle, self.sample_request)

        assert result.schema_id, (
            "FetchResult.schema_id must be a non-empty string."
        )
        assert result.schema_version, (
            "FetchResult.schema_version must be a non-empty string "
            "(e.g. '1.0' or '1.0.0')."
        )

    async def test_fetch_result_completeness_bounds(self, connected: tuple) -> None:
        """
        completeness must be in [0.0, 1.0].

        Pydantic validation on FetchResult enforces this, but an
        explicit test provides a clear failure message.
        """
        connector, handle = connected
        result: FetchResult = await connector.fetch(handle, self.sample_request)

        assert 0.0 <= result.completeness <= 1.0, (
            f"FetchResult.completeness={result.completeness} is outside "
            f"the valid range [0.0, 1.0]."
        )

    async def test_fetch_result_row_count_non_negative(self, connected: tuple) -> None:
        """row_count must be >= 0."""
        connector, handle = connected
        result: FetchResult = await connector.fetch(handle, self.sample_request)

        assert result.row_count >= 0, (
            f"FetchResult.row_count={result.row_count} must be >= 0."
        )

    async def test_fetch_result_matches_schema(self, connected: tuple) -> None:
        """
        FetchResult.data must conform to the declared schema.

        Converts list-of-dicts or DataFrame to a DataFrame and runs the
        contract validator. This is the core safety check that prevents
        connectors from returning structurally invalid data.
        """
        connector, handle = connected
        result: FetchResult = await connector.fetch(handle, self.sample_request)

        records = _to_records(result.data)
        try:
            import pandas as pd  # noqa: F401

            df = pd.DataFrame(records)
        except Exception as exc:  # pragma: no cover
            raise AssertionError("Failed to coerce FetchResult.data to DataFrame") from exc

        assert_schema_compliance(
            df,
            self.sample_schema,
            context={
                "connector_id": self.connector_class.connector_id,
                "dataset": self.sample_request.dataset_id,
            },
        )

    # ==================================================================
    # 4. IDEMPOTENCY (DETERMINISM)
    # ==================================================================

    async def test_idempotency(self, connected: tuple) -> None:
        """
        Fetching the same request twice must yield identical data.

        This is the harness-level enforcement of Law D (deterministic
        replay). We compare content hashes rather than raw data to stay
        agnostic to DataFrame index ordering.

        Comparison strategy (in priority order):
            1. If FetchResult exposes a content_hash field, compare it.
            2. Otherwise, compute _stable_hash() over the data payload.

        If schema.primary_key is set, ordering is canonicalized by that key
        before hashing to avoid false negatives due to row ordering.
        """
        connector, handle = connected

        result_a: FetchResult = await connector.fetch(handle, self.sample_request)
        result_b: FetchResult = await connector.fetch(handle, self.sample_request)

        # Prefer the connector's own content_hash if available
        hash_a = getattr(result_a, "content_hash", None) or _stable_hash(
            result_a.data, self.sample_schema
        )
        hash_b = getattr(result_b, "content_hash", None) or _stable_hash(
            result_b.data, self.sample_schema
        )

        assert hash_a == hash_b, (
            "Idempotency violation: two fetches with identical parameters "
            "produced different data hashes.\n"
            f"  First  hash : {hash_a}\n"
            f"  Second hash : {hash_b}\n"
            "Check for non-deterministic defaults (e.g. 'now' timestamps, "
            "random IDs) in the connector's fetch() path."
        )

    async def test_idempotency_preserves_version(self, connected: tuple) -> None:
        """
        Two fetches with the same request must return the same DataVersion.

        If the upstream source has not changed between calls, the
        connector must not fabricate a new version on each call.
        """
        connector, handle = connected

        r1: FetchResult = await connector.fetch(handle, self.sample_request)
        r2: FetchResult = await connector.fetch(handle, self.sample_request)

        assert r1.version.value == r2.version.value, (
            "Idempotency violation: DataVersion.value changed between "
            "identical fetches.\n"
            f"  First  : {r1.version.value}\n"
            f"  Second : {r2.version.value}"
        )

    async def test_concurrent_fetches(self, connected: tuple) -> None:
        """
        Two concurrent fetches on the same handle should succeed.

        This catches shared mutable state or singleton handle misuse.
        """
        connector, handle = connected

        results = await asyncio.gather(
            connector.fetch(handle, self.sample_request),
            connector.fetch(handle, self.sample_request),
        )

        assert all(isinstance(r, FetchResult) for r in results), (
            "Concurrent fetches must each return a FetchResult."
        )
