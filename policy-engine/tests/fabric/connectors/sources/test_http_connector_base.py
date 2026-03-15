from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, ClassVar

import pytest

pytest.importorskip("aiohttp")

from polisyos.fabric.connectors.base import ConnectionConfig, ConnectionHandle, FetchRequest, FetchResult, HealthStatus
from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase
from polisyos.fabric.connectors.types import FetchError, RateLimitError
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)


class _DummyConnector(HTTPConnectorBase[list[dict[str, Any]]]):
    connector_id: ClassVar[str] = "test.http_dummy"
    _BASE_URL: ClassVar[str] = "https://example.test"
    capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id="http_dummy",
        version="1.0.0",
        namespace="test",
        source_name="Dummy",
        source_organization="PolicyOS Tests",
        source_url="https://example.test",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
    )

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        del handle
        return HealthStatus(healthy=True, message="ok")

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[list[dict[str, Any]]]:
        del handle, request
        now = datetime.now(timezone.utc)
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="test.schema",
            schema_version="1.0.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                timestamp=now,
                content_hash="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            ),
            fetched_at=now,
            completeness=1.0,
        )


class _FakeResponse:
    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self._body = body

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        return None

    async def read(self) -> bytes:
        return self._body


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def get(self, url: str, *, params: dict[str, str], headers: dict[str, str] | None = None) -> _FakeResponse:
        del url, params, headers
        return self._response


def _run(coro):
    return asyncio.run(coro)


def test_request_json_handles_rate_limit() -> None:
    connector = _DummyConnector()
    response = _FakeResponse(
        status=429,
        headers={"Retry-After": "5", "X-RateLimit-Remaining": "0"},
        body=b"{}",
    )
    with pytest.raises(RateLimitError) as exc:
        _run(
            connector._request_json(
                _FakeSession(response),
                "https://example.test/rate-limit",
                params={},
                connector_id=connector.connector_id,
            )
        )

    assert exc.value.retry_after == 5
    assert exc.value.limit_remaining == 0


def test_request_json_handles_http_error() -> None:
    connector = _DummyConnector()
    response = _FakeResponse(
        status=503,
        headers={},
        body=b'{"error":"temporary"}',
    )

    with pytest.raises(FetchError) as exc:
        _run(
            connector._request_json(
                _FakeSession(response),
                "https://example.test/fail",
                params={"q": "x"},
                connector_id=connector.connector_id,
            )
        )

    assert getattr(exc.value, "status_code", None) == 503


def test_request_json_handles_invalid_json() -> None:
    connector = _DummyConnector()
    response = _FakeResponse(
        status=200,
        headers={},
        body=b"not-json",
    )

    with pytest.raises(FetchError):
        _run(
            connector._request_json(
                _FakeSession(response),
                "https://example.test/bad-json",
                params={},
                connector_id=connector.connector_id,
            )
        )


def test_session_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list["_FakeClientSession"] = []

    class _FakeClientSession:
        def __init__(self, *, timeout) -> None:  # noqa: ANN001
            del timeout
            self.closed = False
            created.append(self)

        async def close(self) -> None:
            self.closed = True

    import polisyos.fabric.connectors.sources.http_base as http_base_module

    monkeypatch.setattr(http_base_module.aiohttp, "ClientSession", _FakeClientSession)

    connector = _DummyConnector()
    handle = _run(connector.connect(ConnectionConfig(url="https://example.test")))
    assert handle.state["base_url"] == "https://example.test"

    session = _run(connector._get_session(handle))
    assert session is created[0]
    assert session.closed is False

    _run(connector.disconnect(handle))
    assert session.closed is True


def test_build_auth_headers_supports_bearer() -> None:
    connector = _DummyConnector()
    handle = _run(
        connector.connect(
            ConnectionConfig(
                url="https://example.test",
                auth_method="bearer",
                auth_credentials={"token": "secret-token"},
            )
        )
    )

    headers = connector._build_auth_headers(handle, {"Accept": "application/json"})
    assert headers["Accept"] == "application/json"
    assert headers["Authorization"] == "Bearer secret-token"
