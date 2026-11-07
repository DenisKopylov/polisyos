"""
Test suite for GenericRESTConnector - Phase 2.11.

Includes harness compliance and connector-specific unit/integration tests.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import polisyos.fabric.connectors.reference.rest_json as rest_json_module
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
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
from polisyos.fabric.connectors.reference.rest_json import (
    GenericRESTConnector,
    PaginationStrategy,
    _extract_nested,
)
from polisyos.fabric.connectors.testing import ConnectorTestHarness
from polisyos.fabric.connectors.types import RateLimitError
from polisyos.fabric.quality.safety import UnsafeDataPathError
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy

SAMPLE_SCHEMA = DataSchema(
    schema_id="reference.rest_json.test_api",
    version=SchemaVersion(1, 0, 0),
    fields=(
        FieldSpec(name="id", data_type=SchemaType.INT64, nullable=False),
        FieldSpec(name="country", data_type=SchemaType.STRING, nullable=False),
        FieldSpec(name="value", data_type=SchemaType.FLOAT64, nullable=False),
    ),
)


# =============================================================================
# Harness compliance
# =============================================================================


class TestRESTCompliance(ConnectorTestHarness):
    connector_class = GenericRESTConnector
    sample_config = ConnectionConfig(
        url="http://localhost:9999/api/data",
        headers={"X-REST-DataPath": "data"},
    )
    sample_schema = SAMPLE_SCHEMA
    sample_request = FetchRequest(dataset_id="test_api")

    @pytest.fixture
    def connector_instance(self) -> GenericRESTConnector:
        connector = GenericRESTConnector()

        async def mock_fetch(handle, request):
            version = DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value="sha256:" + "1" * 64,
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                content_hash="sha256:" + "1" * 64,
            )
            return FetchResult(
                data=[{"id": 1, "country": "US", "value": 100.0}],
                row_count=1,
                schema_id="reference.rest_json.test_api",
                schema_version="1.0.0",
                version=version,
                fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
                completeness=1.0,
                quality_tier=QualityTier.SILVER,
            )

        async def mock_health_check(handle):
            return HealthStatus(healthy=True, message="mocked")

        connector.fetch = mock_fetch
        connector.health_check = mock_health_check
        return connector


# =============================================================================
# Unit tests
# =============================================================================


class TestNestedExtraction:
    def test_single_level(self) -> None:
        assert _extract_nested({"data": [1, 2]}, "data") == [1, 2]

    def test_two_levels(self) -> None:
        obj = {"response": {"items": [{"a": 1}]}}
        assert _extract_nested(obj, "response.items") == [{"a": 1}]

    def test_list_index(self) -> None:
        obj = {"data": [{"x": 1}, {"x": 2}]}
        assert _extract_nested(obj, "data.1.x") == 2

    def test_missing_key_raises(self) -> None:
        with pytest.raises(KeyError):
            _extract_nested({"data": []}, "missing")

    def test_data_path_depth_is_bounded(self) -> None:
        with pytest.raises(UnsafeDataPathError, match="depth"):
            _extract_nested({"data": []}, "a.b.c.d.e.f.g.h.i")

    def test_rejects_unsafe_path_token(self) -> None:
        with pytest.raises(UnsafeDataPathError, match="Unsafe data_path token"):
            _extract_nested({"data": []}, "data.__secret")


class TestPaginationConfig:
    def test_page_number_default(self) -> None:
        config = ConnectionConfig(url="http://x.com/api")
        cfg = GenericRESTConnector._parse_rest_config(config)
        assert cfg["pagination"] == PaginationStrategy.PAGE_NUMBER

    def test_cursor_explicit(self) -> None:
        config = ConnectionConfig(
            url="http://x.com/api",
            headers={"X-REST-Pagination": "cursor"},
        )
        cfg = GenericRESTConnector._parse_rest_config(config)
        assert cfg["pagination"] == PaginationStrategy.CURSOR


class TestAuthHeaders:
    def test_bearer_token(self) -> None:
        config = ConnectionConfig(
            url="http://x.com",
            auth_method="bearer",
            auth_credentials={"token": "my-secret"},
        )
        headers = GenericRESTConnector()._build_auth_headers(config)
        assert headers["Authorization"] == "Bearer my-secret"

    def test_api_key(self) -> None:
        config = ConnectionConfig(
            url="http://x.com",
            auth_method="api_key",
            auth_credentials={"header": "X-Custom-Key", "key": "k123"},
        )
        headers = GenericRESTConnector()._build_auth_headers(config)
        assert headers["X-Custom-Key"] == "k123"


class TestConfigValidation:
    def test_missing_url(self) -> None:
        result = GenericRESTConnector.validate_config(ConnectionConfig(url=""))
        assert not result.valid

    def test_invalid_pagination(self) -> None:
        config = ConnectionConfig(
            url="http://x.com",
            headers={"X-REST-Pagination": "invalid_strategy"},
        )
        result = GenericRESTConnector.validate_config(config)
        assert not result.valid

    def test_invalid_data_path(self) -> None:
        config = ConnectionConfig(
            url="http://x.com",
            headers={"X-REST-DataPath": "data.__secret"},
        )
        result = GenericRESTConnector.validate_config(config)
        assert not result.valid


@pytest.mark.asyncio
async def test_rate_limit_error_mapping() -> None:
    connector = GenericRESTConnector()
    handle = await connector.connect(ConnectionConfig(url="http://localhost"))

    class FakeResponse:
        def __init__(self):
            self.status = 429
            self.headers = {"Retry-After": "5", "X-RateLimit-Remaining": "0"}

        async def read(self):
            return b""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    with pytest.raises(RateLimitError):
        await connector._request_page_raw(handle, FakeSession(), "http://localhost", {})


@pytest.mark.asyncio
async def test_rest_json_reuses_one_session_per_handle(monkeypatch) -> None:
    created = []

    class FakeClientSession:
        def __init__(self, *args, **kwargs):
            self.closed = False
            created.append(self)

        async def close(self):
            self.closed = True

    monkeypatch.setattr(rest_json_module.aiohttp, "ClientSession", FakeClientSession)

    connector = GenericRESTConnector()
    handle = await connector.connect(ConnectionConfig(url="http://localhost"))
    sessions = await asyncio.gather(*(connector._get_session(handle) for _ in range(10)))

    assert len(created) == 1
    assert len({id(session) for session in sessions}) == 1

    await connector.disconnect(handle)
    assert created[0].closed


@pytest.mark.parametrize(
    ("response_headers", "payloads", "expected_strategy", "expects_marker"),
    [
        (
            [{"Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"}],
            [[{"id": 1}]],
            VersionStrategy.TIMESTAMP,
            True,
        ),
        ([{}], [[{"id": 1}]], VersionStrategy.CONTENT_HASH, False),
        (
            [{"Last-Modified": "not-a-date"}],
            [[{"id": 1}]],
            VersionStrategy.CONTENT_HASH,
            False,
        ),
        (
            [
                {"Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"},
                {"Last-Modified": "Tue, 02 Jan 2024 00:00:00 GMT"},
            ],
            [[{"id": 1}], []],
            VersionStrategy.CONTENT_HASH,
            False,
        ),
    ],
)
@pytest.mark.asyncio
async def test_rest_json_fetch_binds_last_modified_source_marker(
    response_headers,
    payloads,
    expected_strategy,
    expects_marker,
    monkeypatch,
) -> None:
    """Fetch binds only a valid consistent Last-Modified source boundary."""

    class FakeResponse:
        status = 200

        def __init__(self, headers, payload):
            self.headers = headers
            self._payload = payload

        async def read(self):
            return json.dumps({"data": self._payload}).encode("utf-8")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

    class FakeSession:
        closed = False

        def __init__(self):
            self.calls = []
            self._responses = [
                FakeResponse(headers, payload)
                for headers, payload in zip(response_headers, payloads, strict=True)
            ]

        def get(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return self._responses.pop(0)

        async def close(self):
            self.closed = True

    connector = GenericRESTConnector()
    config_headers = {"X-REST-DataPath": "data"}
    if len(payloads) > 1:
        config_headers["X-REST-PageSize"] = "1"
    handle = await connector.connect(
        ConnectionConfig(
            url="https://example.test/data",
            headers=config_headers,
        )
    )
    session = FakeSession()
    monkeypatch.setattr(rest_json_module.aiohttp, "ClientSession", FakeSession)
    handle.set_state("session", session)

    result = await connector.fetch(handle, FetchRequest(dataset_id="dataset"))

    assert result.version.strategy is expected_strategy
    if expects_marker:
        assert result.source_updated_at is not None
        assert result.source_updated_at.tzinfo is not None
        assert result.source_updated_at == result.version.timestamp
        assert result.version.value == result.source_updated_at.isoformat()
    else:
        assert result.source_updated_at is None
        assert result.version.strategy is VersionStrategy.CONTENT_HASH
    assert not session._responses

    await connector.disconnect(handle)


# =============================================================================
# Integration tests (local aiohttp server)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rest_pagination_with_rate_limit(monkeypatch) -> None:
    import aiohttp.web

    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    call_state = {"count": 0}

    async def handler(request):
        call_state["count"] += 1
        if call_state["count"] == 1:
            return aiohttp.web.Response(
                status=429,
                headers={"Retry-After": "1", "X-RateLimit-Remaining": "0"},
            )

        page = int(request.query.get("page", "1"))
        data = [
            {"id": 1, "country": "US", "value": 100.0},
            {"id": 2, "country": "DE", "value": 200.0},
        ]
        if page == 2:
            data = [{"id": 3, "country": "FR", "value": 300.0}]
        return aiohttp.web.json_response(
            {"data": data},
            headers={"X-RateLimit-Remaining": "5", "ETag": 'W/"etag"'},
        )

    app = aiohttp.web.Application()
    app.router.add_get("/api/data", handler)

    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}/api/data"

    connector = GenericRESTConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url=url,
            headers={
                "X-REST-DataPath": "data",
                "X-REST-Pagination": "page_number",
                "X-REST-PageSize": "2",
            },
            rate_limit_rps=10.0,
        )
    )

    result = await connector.fetch(handle, FetchRequest(dataset_id="integration"))
    assert result.row_count == 3
    assert len(result.data) == 3
    assert handle.get_state("rest_json")["retry_after"] is not None

    await connector.disconnect(handle)
    await runner.cleanup()


@pytest.mark.parametrize("header_name", ["Etag", "etag", "eTaG", "ETag"])
@pytest.mark.asyncio
async def test_actual_http_response_header_case_preserves_etag_and_incremental_since(
    header_name: str,
) -> None:
    """Use actual aiohttp bytes: converting response headers to dict loses this."""
    import aiohttp.web

    observed = []

    async def endpoint(request):
        observed.append(dict(request.query))
        return aiohttp.web.json_response({"data": []}, headers={header_name: '"source-9"'})

    app = aiohttp.web.Application()
    app.router.add_get("/records", endpoint)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    connector = GenericRESTConnector()
    handle = await connector.connect(ConnectionConfig(url=f"http://127.0.0.1:{port}/records"))
    previous = DataVersion(
        strategy=VersionStrategy.ETAG,
        value='"source-8"',
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    try:
        result = await connector.fetch(
            handle, FetchRequest(dataset_id="events", incremental_since=previous)
        )
        assert result.version.strategy is VersionStrategy.ETAG
        assert result.version.value == '"source-9"'
        assert observed and all(query.get("since") == '"source-8"' for query in observed)
    finally:
        await connector.disconnect(handle)
        await runner.cleanup()


def _rest_rate_limiter_registry(connector: GenericRESTConnector):
    page_request = connector._page_request
    while page_request is not None:
        registry = getattr(page_request, "_rate_limiters", None)
        if registry is not None:
            return registry
        page_request = getattr(page_request, "__wrapped__", None)
    raise AssertionError("Generic REST page request has no rate limiter registry")


class _RestLimiterClock:
    """Clock seam for limiter state while actual aiohttp loopback I/O still runs."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        if delay > 0:
            self.now = math.nextafter(self.now + delay, math.inf)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("rate", "same_rate", "spacing"),
    [(1, 1.0, 1.0), (0.2, 0.2, 5.0)],
)
@pytest.mark.asyncio
async def test_actual_rest_transport_shares_numeric_rate_key_and_separates_domains(
    monkeypatch: pytest.MonkeyPatch,
    rate: int | float,
    same_rate: float,
    spacing: float,
) -> None:
    """Real aiohttp pagination retains numeric owners and fractional pacing."""
    from socket import AF_INET, IPPROTO_TCP

    import aiohttp.abc
    import aiohttp.web

    import polisyos.fabric.connectors.resilience.rate_limiter as rate_limiter_module
    from polisyos.fabric.connectors.reference.rest_json import _SESSION_STATE_KEY

    class _LoopbackResolver(aiohttp.abc.AbstractResolver):
        async def resolve(self, host, port=0, family=0):
            assert host == "alternate.test"
            return [
                {
                    "hostname": host,
                    "host": "127.0.0.1",
                    "port": port,
                    "family": AF_INET,
                    "proto": IPPROTO_TCP,
                    "flags": 0,
                }
            ]

        async def close(self) -> None:
            return None

    class _LoopbackREST(GenericRESTConnector):
        async def _get_session(self, handle):
            async with self._session_lock(handle):
                session = handle._read_typed_state_or_default(_SESSION_STATE_KEY, None)
                if session is None or session.closed:
                    session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=handle.config.timeout_seconds),
                        connector=aiohttp.TCPConnector(resolver=_LoopbackResolver()),
                    )
                    handle._set_typed_state(_SESSION_STATE_KEY, session)
                return session

    clock = _RestLimiterClock()
    monkeypatch.setattr(rate_limiter_module, "_monotonic", clock.monotonic)
    monkeypatch.setattr(
        rate_limiter_module,
        "asyncio",
        SimpleNamespace(sleep=clock.sleep),
    )

    observed: list[tuple[str, float, int]] = []

    async def endpoint(request):
        page = int(request.query.get("page", "1"))
        observed.append((request.host, clock.now, page))
        rows = [{"id": page}] if page == 1 else []
        return aiohttp.web.json_response({"data": rows})

    app = aiohttp.web.Application()
    app.router.add_get("/records", endpoint)
    runner = aiohttp.web.AppRunner(app)
    connector = _LoopbackREST()
    handles = []
    try:
        await runner.setup()
        site = aiohttp.web.TCPSite(runner, host="127.0.0.1", port=0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        urls = [
            f"http://127.0.0.1:{port}/records",
            f"http://alternate.test:{port}/records",
        ]

        def config(url: str, rate: int | float) -> ConnectionConfig:
            return ConnectionConfig(
                url=url,
                headers={
                    "X-REST-DataPath": "data",
                    "X-REST-Pagination": "page_number",
                    "X-REST-PageSize": "1",
                },
                rate_limit_rps=rate,
            )

        first_handle = await connector.connect(config(urls[0], rate))
        second_handle = await connector.connect(config(urls[0], same_rate))
        independent_domain = await connector.connect(config(urls[1], float(rate)))
        handles.extend((first_handle, second_handle, independent_domain))
        request = FetchRequest(dataset_id="records")

        assert (await connector.fetch(first_handle, request)).row_count == 1
        assert (await connector.fetch(second_handle, request)).row_count == 1
        assert (await connector.fetch(independent_domain, request)).row_count == 1

        first_host = f"127.0.0.1:{port}"
        second_host = f"alternate.test:{port}"
        assert [(host, round(when, 6), page) for host, when, page in observed] == [
            (first_host, 0.0, 1),
            (first_host, spacing, 2),
            (first_host, spacing * 2, 1),
            (first_host, spacing * 3, 2),
            (second_host, spacing * 3, 1),
            (second_host, spacing * 4, 2),
        ]

        registry = _rest_rate_limiter_registry(connector)
        assert len(registry._items) == 2
        assert {entry.value.limiter_id for entry in registry._items.values()} == {
            f"reference.rest_json:{first_host}",
            f"reference.rest_json:{second_host}",
        }
    finally:
        for handle in handles:
            await connector.disconnect(handle)
        await runner.cleanup()


@pytest.mark.integration
@pytest.mark.parametrize("rate", [0.0, -1.0, float("nan"), float("inf")])
@pytest.mark.asyncio
async def test_actual_rest_transport_rejects_invalid_rates_before_http_request(rate: float) -> None:
    """Invalid limiter settings refuse before the selected HTTP transport is entered."""
    import aiohttp.web

    requests: list[str] = []

    async def endpoint(request):
        requests.append(request.path_qs)
        return aiohttp.web.json_response({"data": []})

    app = aiohttp.web.Application()
    app.router.add_get("/records", endpoint)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host="127.0.0.1", port=0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    connector = GenericRESTConnector()
    handle = await connector.connect(
        ConnectionConfig(url=f"http://127.0.0.1:{port}/records", rate_limit_rps=rate)
    )
    try:
        with pytest.raises(ValueError):
            await connector.fetch(handle, FetchRequest(dataset_id="records"))
        assert requests == []
    finally:
        await connector.disconnect(handle)
        await runner.cleanup()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_actual_rest_result_survives_initialized_observability_profile() -> None:
    """Actual aiohttp results survive enabled and disabled telemetry owners."""
    import aiohttp.web

    from polisyos.core.observability import get_metrics, get_tracer

    enabled = os.environ.get("POLISYOS_OTEL_ENABLED", "true").lower() == "true"
    requests = 0

    async def endpoint(_request):
        nonlocal requests
        requests += 1
        return aiohttp.web.json_response({"data": [{"id": 9}]})

    app = aiohttp.web.Application()
    app.router.add_get("/records", endpoint)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host="127.0.0.1", port=0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    metrics = get_metrics()
    metrics._ensure_initialized()
    tracer = get_tracer()
    tracer._ensure_initialized()
    connector = GenericRESTConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url=f"http://127.0.0.1:{port}/records",
            headers={"X-REST-DataPath": "data"},
            rate_limit_rps=1.0,
        )
    )
    try:
        result = await connector.fetch(handle, FetchRequest(dataset_id="records"))
        assert result.data == [{"id": 9}]
        assert result.row_count == 1
        assert requests == 1

        assert metrics._config is not None and metrics._config.enabled is enabled
        assert tracer._config is not None and tracer._config.enabled is enabled

        if enabled:
            assert metrics._provider is not None
            assert metrics._meter is not None
            assert tracer._tracer is not None
            assert metrics.connector_rate_limit_acquire_duration_seconds is not None
        else:
            assert metrics._provider is None
            assert metrics._meter is None
            with tracer.start_as_current_span("fabric.net02.disabled_telemetry") as span:
                assert not span.is_recording()
    finally:
        await connector.disconnect(handle)
        await runner.cleanup()
