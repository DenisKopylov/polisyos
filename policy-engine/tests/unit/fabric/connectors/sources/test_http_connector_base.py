from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, ClassVar

import pytest

pytest.importorskip("aiohttp")

from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase, HTTPResilienceProfile
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
        now = datetime.now(UTC)
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
    def __init__(
        self,
        status: int,
        headers: dict[str, str],
        body: bytes,
        *,
        stream_chunks: list[bytes] | None = None,
    ) -> None:
        self.status = status
        self.headers = headers
        self._body = body
        self.content = _FakeContent(stream_chunks or [body]) if stream_chunks is not None else None

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        return None

    async def read(self) -> bytes:
        return self._body


class _FakeContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def iter_chunked(self, _size: int):
        for chunk in self._chunks:
            yield chunk


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def get(
        self, url: str, *, params: dict[str, str], headers: dict[str, str] | None = None
    ) -> _FakeResponse:
        del url, params, headers
        return self._response


class _ObserverLimits:
    max_response_bytes = 1024
    max_decompressed_bytes = 2048


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


def test_request_json_blocks_secret_pii_response_payload() -> None:
    connector = _DummyConnector()
    response = _FakeResponse(
        status=200,
        headers={},
        body=b'{"email":"policy.fixture@example.org"}',
    )

    with pytest.raises(FetchError, match="blocked by secret/PII scan"):
        _run(
            connector._request_json(
                _FakeSession(response),
                "https://example.test/secret",
                params={},
                connector_id=connector.connector_id,
            )
        )


def test_connection_config_redaction_uses_shared_secret_pii_scanner() -> None:
    config = ConnectionConfig(
        url="https://example.test",
        auth_method="bearer",
        auth_credentials={"token": "sk-testsecret1234567890"},
    )

    payload = config.to_dict(redact=True)

    assert "sk-testsecret1234567890" not in str(payload)
    assert "[POLISYOS_SECRET_" in str(payload)


def test_request_json_rejects_oversized_content_length() -> None:
    class _LimitedConnector(_DummyConnector):
        resilience_profile = HTTPResilienceProfile(max_response_bytes=8, max_json_bytes=8)

    connector = _LimitedConnector()
    response = _FakeResponse(
        status=200,
        headers={"Content-Length": "32"},
        body=b'{"ok":1}',
    )

    with pytest.raises(FetchError, match="exceeds safe limit"):
        _run(
            connector._request_json(
                _FakeSession(response),
                "https://example.test/too-large",
                params={},
                connector_id=connector.connector_id,
            )
        )


def test_request_json_rejects_streamed_decompressed_body_limit() -> None:
    class _LimitedConnector(_DummyConnector):
        resilience_profile = HTTPResilienceProfile(
            max_response_bytes=64,
            max_json_bytes=64,
            max_decompressed_bytes=16,
        )

    connector = _LimitedConnector()
    response = _FakeResponse(
        status=200,
        headers={},
        body=b'{"ok": true, "value": 1}',
        stream_chunks=[b'{"ok": ', b'true, "value": 1}'],
    )

    with pytest.raises(FetchError, match="Decoded HTTP body exceeds safe limit"):
        _run(
            connector._request_json(
                _FakeSession(response),
                "https://example.test/stream-too-large",
                params={},
                connector_id=connector.connector_id,
            )
        )


def test_request_json_rejects_top_level_row_limit() -> None:
    class _LimitedConnector(_DummyConnector):
        resilience_profile = HTTPResilienceProfile(max_json_bytes=128, max_rows=2)

    connector = _LimitedConnector()
    response = _FakeResponse(
        status=200,
        headers={},
        body=b'[{"id":1},{"id":2},{"id":3}]',
    )

    with pytest.raises(FetchError, match="row count exceeds safe limit"):
        _run(
            connector._request_json(
                _FakeSession(response),
                "https://example.test/too-many-rows",
                params={},
                connector_id=connector.connector_id,
            )
        )


def test_session_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[_FakeClientSession] = []

    class _FakeClientSession:
        def __init__(self, *, timeout) -> None:
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


def test_get_session_is_race_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[_FakeClientSession] = []

    class _FakeClientSession:
        def __init__(self, *, timeout) -> None:
            del timeout
            self.closed = False
            created.append(self)

        async def close(self) -> None:
            self.closed = True

    import polisyos.fabric.connectors.sources.http_base as http_base_module

    monkeypatch.setattr(http_base_module.aiohttp, "ClientSession", _FakeClientSession)

    async def _exercise() -> None:
        connector = _DummyConnector()
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        sessions = await asyncio.gather(*(connector._get_session(handle) for _ in range(10)))
        assert len(created) == 1
        assert len({id(session) for session in sessions}) == 1
        await connector.disconnect(handle)

    _run(_exercise())


def test_connection_handle_state_snapshot_is_immutable() -> None:
    connector = _DummyConnector()
    handle = _run(connector.connect(ConnectionConfig(url="https://example.test")))

    snapshot = handle.state

    with pytest.raises(TypeError):
        snapshot["base_url"] = "https://mutated.test"  # type: ignore[index]

    assert handle.get_state("base_url") == "https://example.test"

    _run(connector.disconnect(handle))


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


def test_raw_http_observer_runs_before_json_parse_with_exact_bounded_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.fabric.connectors.sources.http_base as http_base_module

    connector = _DummyConnector()
    raw = b'{"rows":[{"value":1}]}'
    response_headers = {"Content-Type": "application/json", "ETag": '"v1"'}
    params = {"country": "UA"}
    events: list[str] = []
    witnessed: list[tuple[object, ...]] = []

    class _Observer(_ObserverLimits):
        def before_request(
            self,
            connector_id: str,
            url: str,
            request_params: dict[str, str],
        ) -> None:
            events.append("before_request")
            witnessed.append((connector_id, url, request_params))

        def on_raw_response(
            self,
            connector_id: str,
            url: str,
            request_params: dict[str, str],
            status_code: int,
            headers: dict[str, str],
            body: bytes,
        ) -> None:
            events.append("raw_response")
            witnessed.append(
                (connector_id, url, request_params, status_code, headers, body)
            )

    original_loads = http_base_module.json.loads

    def _tracked_loads(payload: bytes) -> object:
        events.append("json_parse")
        return original_loads(payload)

    monkeypatch.setattr(http_base_module.json, "loads", _tracked_loads)

    body, headers, returned_raw = _run(
        connector._request_json(
            _FakeSession(_FakeResponse(200, response_headers, raw)),
            "https://example.test/data",
            params=params,
            connector_id=connector.connector_id,
            raw_http_response_observer=_Observer(),
        )
    )

    assert body == {"rows": [{"value": 1}]}
    assert headers == response_headers
    assert returned_raw is raw
    assert events == ["before_request", "raw_response", "json_parse"]
    assert witnessed == [
        (connector.connector_id, "https://example.test/data", params),
        (
            connector.connector_id,
            "https://example.test/data",
            params,
            200,
            response_headers,
            raw,
        ),
    ]


def test_raw_http_observer_can_abort_before_network_request() -> None:
    connector = _DummyConnector()
    request_attempted = False

    class _NoBudgetObserver(_ObserverLimits):
        def before_request(
            self,
            connector_id: str,
            url: str,
            params: dict[str, str],
        ) -> None:
            del connector_id, url, params
            raise RuntimeError("HTTP call budget exhausted")

        def on_raw_response(self, *args: object) -> None:
            del args
            pytest.fail("a response cannot exist when the request budget rejects the call")

    class _NoRequestSession:
        def get(self, *args: object, **kwargs: object) -> _FakeResponse:
            nonlocal request_attempted
            del args, kwargs
            request_attempted = True
            pytest.fail("session.get ran after the observer rejected the request")

    with pytest.raises(RuntimeError, match="HTTP call budget exhausted"):
        _run(
            connector._request_json(
                _NoRequestSession(),  # type: ignore[arg-type]
                "https://example.test/data",
                params={"country": "UA"},
                connector_id=connector.connector_id,
                raw_http_response_observer=_NoBudgetObserver(),
            )
        )

    assert request_attempted is False


@pytest.mark.parametrize("status_code", [429, 503])
def test_raw_http_observer_journals_non_success_body_before_status_error(
    status_code: int,
) -> None:
    connector = _DummyConnector()
    raw = b'{"error":"temporary"}'
    witnessed: list[tuple[int, bytes]] = []

    class _Observer(_ObserverLimits):
        def before_request(self, *args: object) -> None:
            del args

        def on_raw_response(
            self,
            connector_id: str,
            url: str,
            params: dict[str, str],
            status_code: int,
            headers: dict[str, str],
            body: bytes,
        ) -> None:
            del connector_id, url, params, headers
            witnessed.append((status_code, body))

    error_type = RateLimitError if status_code == 429 else FetchError
    with pytest.raises(error_type) as exc:
        _run(
            connector._request_json(
                _FakeSession(_FakeResponse(status_code, {"Retry-After": "2"}, raw)),
                "https://example.test/fail",
                params={"q": "x"},
                connector_id=connector.connector_id,
                raw_http_response_observer=_Observer(),
            )
        )

    if status_code == 503:
        assert getattr(exc.value, "status_code", None) == 503
    else:
        assert isinstance(exc.value, RateLimitError)
    assert witnessed == [(status_code, raw)]


def test_raw_http_observer_journals_exact_body_before_pii_classification() -> None:
    connector = _DummyConnector()
    raw = b'{"email":"alice@example.com"}'
    witnessed: list[bytes] = []

    class _Observer(_ObserverLimits):
        def before_request(self, *args: object) -> None:
            del args

        def on_raw_response(self, *args: object) -> None:
            witnessed.append(args[-1])  # type: ignore[arg-type]

    with pytest.raises(FetchError, match="secret/PII"):
        _run(
            connector._request_json(
                _FakeSession(_FakeResponse(200, {}, raw)),
                "https://example.test/pii",
                params={},
                connector_id=connector.connector_id,
                raw_http_response_observer=_Observer(),
            )
        )

    assert witnessed == [raw]


def test_raw_http_observer_reports_headers_and_progress_before_raw_body() -> None:
    connector = _DummyConnector()
    raw = b'{"ok":true}'
    events: list[tuple[str, object]] = []

    class _Observer(_ObserverLimits):
        def before_request(self, *args: object) -> None:
            del args

        def on_response_headers(self, *args: object) -> None:
            events.append(("headers", args[-1]))

        def on_body_progress(self, *args: object) -> None:
            events.append(("progress", args[-1]))

        def on_raw_response(self, *args: object) -> None:
            events.append(("raw", args[-1]))

    _run(
        connector._request_json(
            _FakeSession(_FakeResponse(200, {"ETag": "v1"}, raw)),
            "https://example.test/progress",
            params={},
            connector_id=connector.connector_id,
            raw_http_response_observer=_Observer(),
        )
    )

    assert events == [
        ("headers", {"ETag": "v1"}),
        ("progress", len(raw)),
        ("raw", raw),
    ]


def test_raw_http_observer_emits_periodic_waiting_until_response_headers() -> None:
    connector = _DummyConnector()

    async def _exercise() -> None:
        release_headers = asyncio.Event()
        two_waiting_heartbeats = asyncio.Event()
        events: list[str] = []

        class _DelayedResponse(_FakeResponse):
            async def __aenter__(self) -> _FakeResponse:
                await release_headers.wait()
                return self

        class _Observer(_ObserverLimits):
            heartbeat_interval_seconds = 0.001

            def before_request(self, *args: object) -> None:
                del args
                events.append("before_request")

            def on_waiting(self, *args: object) -> None:
                assert isinstance(args[-1], float)
                events.append("waiting")
                if events.count("waiting") == 2:
                    two_waiting_heartbeats.set()

            def on_response_headers(self, *args: object) -> None:
                del args
                events.append("response_headers")

            def on_body_progress(self, *args: object) -> None:
                del args
                events.append("body_progress")

            def on_raw_response(self, *args: object) -> None:
                del args
                events.append("raw_response")

        task = asyncio.create_task(
            connector._request_json(
                _FakeSession(_DelayedResponse(200, {}, b"{}")),
                "https://example.test/waiting",
                params={"country": "UA"},
                connector_id=connector.connector_id,
                raw_http_response_observer=_Observer(),
            )
        )
        await asyncio.wait_for(two_waiting_heartbeats.wait(), timeout=1.0)
        release_headers.set()
        await task
        waiting_count = events.count("waiting")
        await asyncio.sleep(0.005)

        assert events[:3] == ["before_request", "waiting", "waiting"]
        assert events[waiting_count + 1 :] == [
            "response_headers",
            "body_progress",
            "raw_response",
        ]
        assert events.count("waiting") == waiting_count
        assert not [
            pending
            for pending in asyncio.all_tasks()
            if pending is not asyncio.current_task() and not pending.done()
        ]

    _run(_exercise())


def test_raw_http_waiting_heartbeat_cancels_with_delayed_request() -> None:
    connector = _DummyConnector()

    async def _exercise() -> None:
        waiting_seen = asyncio.Event()
        entry_cancelled = asyncio.Event()
        waiting_count = 0

        class _DelayedResponse(_FakeResponse):
            async def __aenter__(self) -> _FakeResponse:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    entry_cancelled.set()
                    raise
                raise AssertionError("unreachable")

        class _Observer(_ObserverLimits):
            heartbeat_interval_seconds = 0.001

            def before_request(self, *args: object) -> None:
                del args

            def on_waiting(self, *args: object) -> None:
                nonlocal waiting_count
                del args
                waiting_count += 1
                waiting_seen.set()

            def on_raw_response(self, *args: object) -> None:
                del args
                pytest.fail("a cancelled request cannot produce raw evidence")

        task = asyncio.create_task(
            connector._request_json(
                _FakeSession(_DelayedResponse(200, {}, b"{}")),
                "https://example.test/cancel",
                params={},
                connector_id=connector.connector_id,
                raw_http_response_observer=_Observer(),
            )
        )
        await asyncio.wait_for(waiting_seen.wait(), timeout=1.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(entry_cancelled.wait(), timeout=1.0)
        count_after_cancel = waiting_count
        await asyncio.sleep(0.005)

        assert waiting_count == count_after_cancel
        assert not [
            pending
            for pending in asyncio.all_tasks()
            if pending is not asyncio.current_task() and not pending.done()
        ]

    _run(_exercise())


def test_raw_http_waiting_heartbeat_stops_when_response_entry_fails() -> None:
    connector = _DummyConnector()

    async def _exercise() -> None:
        waiting_seen = asyncio.Event()
        fail_entry = asyncio.Event()
        waiting_count = 0

        class _FailingResponse(_FakeResponse):
            async def __aenter__(self) -> _FakeResponse:
                await fail_entry.wait()
                raise RuntimeError("response headers unavailable")

        class _Observer(_ObserverLimits):
            heartbeat_interval_seconds = 0.001

            def before_request(self, *args: object) -> None:
                del args

            def on_waiting(self, *args: object) -> None:
                nonlocal waiting_count
                del args
                waiting_count += 1
                waiting_seen.set()

            def on_raw_response(self, *args: object) -> None:
                del args
                pytest.fail("a failed request cannot produce raw evidence")

        task = asyncio.create_task(
            connector._request_json(
                _FakeSession(_FailingResponse(200, {}, b"{}")),
                "https://example.test/fail-before-headers",
                params={},
                connector_id=connector.connector_id,
                raw_http_response_observer=_Observer(),
            )
        )
        await asyncio.wait_for(waiting_seen.wait(), timeout=1.0)
        fail_entry.set()
        with pytest.raises(RuntimeError, match="response headers unavailable"):
            await task
        count_after_error = waiting_count
        await asyncio.sleep(0.005)

        assert waiting_count == count_after_error
        assert not [
            pending
            for pending in asyncio.all_tasks()
            if pending is not asyncio.current_task() and not pending.done()
        ]

    _run(_exercise())


def test_error_response_body_remains_unread_when_no_observer_is_installed() -> None:
    connector = _DummyConnector()

    class _UnreadableErrorResponse(_FakeResponse):
        async def read(self) -> bytes:
            pytest.fail("legacy error-status handling must not read the response body")

    with pytest.raises(FetchError) as exc:
        _run(
            connector._request_json(
                _FakeSession(_UnreadableErrorResponse(503, {}, b"must-not-read")),
                "https://example.test/fail",
                params={},
                connector_id=connector.connector_id,
            )
        )

    assert getattr(exc.value, "status_code", None) == 503


def test_raw_http_observer_failure_prevents_json_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.fabric.connectors.sources.http_base as http_base_module

    connector = _DummyConnector()

    class _FailingObserver(_ObserverLimits):
        def before_request(self, *args: object) -> None:
            del args

        def on_raw_response(self, *args: object) -> None:
            del args
            raise RuntimeError("journal unavailable")

    def _must_not_parse(*args: object, **kwargs: object) -> object:
        del args, kwargs
        pytest.fail("JSON parsing ran after the raw HTTP observer failed")

    monkeypatch.setattr(http_base_module.json, "loads", _must_not_parse)

    with pytest.raises(RuntimeError, match="journal unavailable"):
        _run(
            connector._request_json(
                _FakeSession(_FakeResponse(200, {}, b'{"ok":true}')),
                "https://example.test/data",
                params={},
                connector_id=connector.connector_id,
                raw_http_response_observer=_FailingObserver(),
            )
        )


def test_sources_facade_exports_raw_http_response_observer() -> None:
    from polisyos.fabric import connectors
    from polisyos.fabric.connectors import sources
    from polisyos.fabric.connectors.sources import http_base

    assert sources.RawHTTPResponseObserver is http_base.RawHTTPResponseObserver
    assert connectors.RawHTTPResponseObserver is http_base.RawHTTPResponseObserver


def test_raw_http_observer_tighter_limits_bound_response_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = _DummyConnector()
    observed_limits: list[tuple[int | None, int | None]] = []

    class _TightObserver(_ObserverLimits):
        max_response_bytes = 3
        max_decompressed_bytes = 4

        def before_request(self, *args: object) -> None:
            del args

        def on_raw_response(self, *args: object) -> None:
            del args

    async def _read_response_body(
        response: object,
        *,
        connector_id: str,
        url: str,
        max_response_bytes: int | None = None,
        max_decompressed_bytes: int | None = None,
        before_classification: Callable[[bytes], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
    ) -> bytes:
        del response, connector_id, url, on_progress
        observed_limits.append((max_response_bytes, max_decompressed_bytes))
        if before_classification is not None:
            before_classification(b"{}")
        return b"{}"

    monkeypatch.setattr(connector, "_read_response_body", _read_response_body)

    _run(
        connector._request_json(
            _FakeSession(_FakeResponse(200, {}, b"{}")),
            "https://example.test/data",
            params={},
            connector_id=connector.connector_id,
            raw_http_response_observer=_TightObserver(),
        )
    )

    assert observed_limits == [(3, 4)]


def test_sync_fetch_handle_observer_flows_through_resilient_http_request() -> None:
    from polisyos.fabric.ingestion.ingestion import _sync_fetch

    raw = b'{"rows":[]}'
    events: list[str] = []
    config = ConnectionConfig(url="https://example.test")

    class _Observer(_ObserverLimits):
        def before_request(self, *args: object) -> None:
            del args
            events.append("before_request")

        def on_raw_response(self, *args: object) -> None:
            assert args[-1] is raw
            events.append("raw_response")

    observer = _Observer()

    class _RequestingConnector(_DummyConnector):
        async def _get_session(self, handle: ConnectionHandle) -> _FakeSession:
            del handle
            return _FakeSession(_FakeResponse(200, {}, raw))

        async def fetch(
            self,
            handle: ConnectionHandle,
            request: FetchRequest,
        ) -> FetchResult[list[dict[str, Any]]]:
            body, _headers, returned_raw = await self._resilient_request_json(
                handle,
                "https://example.test/data",
                params={"dataset": request.dataset_id},
            )
            assert body == {"rows": []}
            assert returned_raw is raw
            events.append("fetch_result")
            return await super().fetch(handle, request)

    connector = _RequestingConnector()
    handle = _run(connector.connect(config))

    class _Registry:
        async def get_connection(
            self,
            connector_id: str,
            connection_config: ConnectionConfig,
        ) -> ConnectionHandle:
            assert connector_id == connector.connector_id
            assert connection_config is config
            return handle

        async def release_connection(
            self,
            connector_id: str,
            released_handle: ConnectionHandle,
        ) -> None:
            assert connector_id == connector.connector_id
            assert released_handle is handle
            assert observer not in released_handle.state.values()

    result = _sync_fetch(
        _Registry(),  # type: ignore[arg-type]
        connector.connector_id,
        connector,
        FetchRequest(dataset_id="raw.dataset"),
        connection_config=config,
        raw_http_response_observer=observer,
    )

    assert result.row_count == 0
    assert events == ["before_request", "raw_response", "fetch_result"]
