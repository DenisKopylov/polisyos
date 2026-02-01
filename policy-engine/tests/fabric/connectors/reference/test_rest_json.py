"""
Test suite for GenericRESTConnector - Phase 2.11.

Includes harness compliance and connector-specific unit/integration tests.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest, FetchResult
from polisyos.fabric.connectors.contracts.schema import DataSchema, FieldSpec, SchemaType, SchemaVersion
from polisyos.fabric.connectors.reference.rest_json import (
    GenericRESTConnector,
    PaginationStrategy,
    _extract_nested,
)
from polisyos.fabric.connectors.testing import ConnectorTestHarness
from polisyos.fabric.connectors.types import RateLimitError
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

    @pytest.fixture()
    def connector_instance(self) -> GenericRESTConnector:
        connector = GenericRESTConnector()

        async def mock_fetch(handle, request):
            version = DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value="sha256:" + "1" * 64,
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                content_hash="sha256:" + "1" * 64,
            )
            return FetchResult(
                data=[{"id": 1, "country": "US", "value": 100.0}],
                row_count=1,
                schema_id="reference.rest_json.test_api",
                schema_version="1.0.0",
                version=version,
                fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                completeness=1.0,
                quality_tier=QualityTier.SILVER,
            )

        connector.fetch = mock_fetch
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
            headers={"X-REST-DataPath": "data", "X-REST-Pagination": "page_number"},
            rate_limit_rps=10.0,
        )
    )

    result = await connector.fetch(handle, FetchRequest(dataset_id="integration"))
    assert result.row_count == 3
    assert len(result.data) == 3
    assert handle.state["rest_json"].get("retry_after") is not None

    await connector.disconnect(handle)
    await runner.cleanup()
