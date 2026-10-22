from __future__ import annotations

import asyncio
import math
import threading
from collections.abc import AsyncIterator
from typing import TypeGuard

import pytest

from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    _ConnectionStateKey,
    _MissingConnectionState,
)
from polisyos.fabric.connectors.http_limits import read_bounded_response_body
from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector
from polisyos.fabric.connectors.sources.graphql_api import GraphQLConnector
from polisyos.fabric.connectors.sources.sdmx_source import SDMXSourceConnector
from polisyos.fabric.connectors.types import FetchError


def _is_optional_string(value: object) -> TypeGuard[str | None]:
    return value is None or isinstance(value, str)


def _is_string_object(value: object) -> TypeGuard[object]:
    return isinstance(value, str)


def _is_string_mapping(value: object) -> TypeGuard[dict[str, str]]:
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )


def _handle() -> ConnectionHandle:
    return ConnectionHandle("test.connector", ConnectionConfig(url="https://example.test"))


def _run(coro):
    return asyncio.run(coro)


def test_typed_state_distinguishes_missing_none_and_malformed_values() -> None:
    handle = _handle()
    nullable_key: _ConnectionStateKey[str | None] = _ConnectionStateKey(
        "nullable", _is_optional_string
    )
    assert isinstance(handle._read_typed_state(nullable_key), _MissingConnectionState)
    assert handle._read_typed_state_or_default(nullable_key, "fallback") == "fallback"

    handle.set_state("nullable", None)
    assert handle._read_typed_state(nullable_key) is None

    handle.set_state("nullable", False)
    with pytest.raises(TypeError, match="connection state key 'nullable'"):
        handle._read_typed_state(nullable_key)

    handle.set_state("legacy", False)
    assert handle.get_state("legacy") is False
    assert handle.setdefault_state("legacy", "unused") is False


def test_typed_setdefault_validates_existing_winner_and_proposed_default() -> None:
    handle = _handle()
    key: _ConnectionStateKey[dict[str, str]] = _ConnectionStateKey("mapping", _is_string_mapping)
    handle.set_state("mapping", False)
    with pytest.raises(TypeError, match="connection state key 'mapping'"):
        handle._setdefault_typed_state(key, {})

    broad_key: _ConnectionStateKey[object] = _ConnectionStateKey("winner", _is_string_object)
    handle.set_state("winner", "existing")
    with pytest.raises(TypeError, match="connection state key 'winner'"):
        handle._setdefault_typed_state(broad_key, False)
    assert handle._read_typed_state(broad_key) == "existing"


def test_typed_setdefault_publishes_one_atomic_winner() -> None:
    handle = _handle()
    key: _ConnectionStateKey[dict[str, str]] = _ConnectionStateKey("winner", _is_string_mapping)
    barrier = threading.Barrier(12)
    results: list[dict[str, str]] = []

    def publish(index: int) -> None:
        barrier.wait()
        results.append(handle._setdefault_typed_state(key, {"producer": str(index)}))

    workers = [threading.Thread(target=publish, args=(index,)) for index in range(12)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=2)

    assert all(not worker.is_alive() for worker in workers)
    assert len(results) == 12
    assert all(value is results[0] for value in results)


@pytest.mark.parametrize(
    "bad_state",
    [
        pytest.param(False, id="falsey-wrong-type"),
        pytest.param({}, id="empty-present-map"),
        pytest.param(
            {"rate_limit_remaining": None, "retry_after": math.nan},
            id="nonfinite-present-duration",
        ),
    ],
)
def test_rest_json_fetch_rejects_malformed_present_rate_state_before_request(
    bad_state: object,
) -> None:
    connector = GenericRESTConnector()
    handle = _run(connector.connect(ConnectionConfig(url="https://example.test/api")))
    handle.set_state("rest_json", bad_state)

    with pytest.raises(TypeError, match="connection state key 'rest_json'"):
        _run(connector.fetch(handle, FetchRequest(dataset_id="example.dataset")))


def test_rest_json_session_lock_and_session_consumers_reject_wrong_cached_values() -> None:
    connector = GenericRESTConnector()
    handle = _run(connector.connect(ConnectionConfig(url="https://example.test/api")))

    handle.set_state("_session_lock", False)
    with pytest.raises(TypeError, match="connection state key '_session_lock'"):
        connector._session_lock(handle)

    handle = _run(connector.connect(ConnectionConfig(url="https://example.test/api")))
    handle.set_state("session", False)
    with pytest.raises(TypeError, match="connection state key 'session'"):
        _run(connector.disconnect(handle))


def test_graphql_schema_reader_refuses_malformed_present_cache() -> None:
    connector = GraphQLConnector()
    handle = _run(
        connector.connect(
            ConnectionConfig(
                url="https://example.test/graphql",
                headers={"X-GraphQL-Query": "query { ok }"},
            )
        )
    )
    handle.set_state("graphql_api", False)

    with pytest.raises(TypeError, match="connection state key 'graphql_api'"):
        _run(connector.get_dataset_schema(handle, "example.dataset"))


def test_sdmx_cached_resilience_key_refuses_nonfinite_present_tuple() -> None:
    connector = SDMXSourceConnector()
    handle = _run(connector.connect(ConnectionConfig(url="https://example.test/sdmx")))
    handle.set_state(
        "_sdmx_head_executor_config",
        (1, 0.1, None, 2.0, 0.5, math.nan, False, None),
    )

    with pytest.raises(
        TypeError,
        match="connection state key '_sdmx_head_executor_config'",
    ):
        connector._head_executor(handle)


class _ChunkedContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def iter_chunked(self, _chunk_size: int) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


class _ReadOnlyResponse:
    def __init__(self, body: bytes, content: object) -> None:
        self._headers = {"Content-Length": str(len(body))}
        self._body = body
        self._content = content

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    @property
    def content(self) -> object:
        return self._content

    async def read(self) -> bytes:
        return self._body


async def _aiohttp_response(
    body: bytes,
    content: object,
) -> object:
    from aiohttp import ClientResponse
    from aiohttp.client_reqrep import RequestInfo
    from aiohttp.helpers import TimerNoop
    from multidict import CIMultiDict, CIMultiDictProxy
    from yarl import URL

    url = URL("https://example.test/data")
    headers = CIMultiDictProxy(CIMultiDict({"Content-Length": str(len(body))}))
    request_info = RequestInfo(url, "GET", headers, url)
    response = ClientResponse(
        "GET",
        url,
        writer=None,
        continue100=None,
        timer=TimerNoop(),
        request_info=request_info,
        traces=[],
        loop=asyncio.get_running_loop(),
        session=None,
    )
    response._headers = headers
    response.content = content
    response._body = body if content is None else None
    return response


def test_aiohttp_client_response_uses_readonly_header_surface() -> None:
    body = b'{"ok":true}'
    response = _run(_aiohttp_response(body, _ChunkedContent([body])))
    payload = _run(
        read_bounded_response_body(
            response,
            connector_id="test.http",
            url="https://example.test/data",
            max_response_bytes=32,
            max_decompressed_bytes=32,
        )
    )
    assert payload == body
    assert response.headers["Content-Length"] == str(len(body))


def test_readonly_http_response_contract_keeps_chunked_body_callbacks_and_limits() -> None:
    body = b'{"ok":true}'
    response = _ReadOnlyResponse(body, _ChunkedContent([b'{"ok":', b"true}"]))
    classified: list[bytes] = []
    progress: list[int] = []

    payload = _run(
        read_bounded_response_body(
            response,
            connector_id="test.http",
            url="https://example.test/data",
            max_response_bytes=32,
            max_decompressed_bytes=32,
            chunk_size=8,
            before_classification=classified.append,
            on_progress=progress.append,
        )
    )

    assert payload == body
    assert classified == [body]
    assert progress == [6, len(body)]


def test_readonly_http_response_contract_keeps_read_fallback_and_size_refusal() -> None:
    body = b'{"ok":true}'
    fallback = _ReadOnlyResponse(body, None)
    progress: list[int] = []
    payload = _run(
        read_bounded_response_body(
            fallback,
            connector_id="test.http",
            url="https://example.test/data",
            max_response_bytes=32,
            max_decompressed_bytes=32,
            on_progress=progress.append,
        )
    )
    assert payload == body
    assert progress == [len(body)]

    oversized = _ReadOnlyResponse(body, None)
    with pytest.raises(FetchError, match="exceeds safe limit"):
        _run(
            read_bounded_response_body(
                oversized,
                connector_id="test.http",
                url="https://example.test/data",
                max_response_bytes=2,
                max_decompressed_bytes=32,
            )
        )


def test_sdmx_head_executor_state_rejects_raw_callable() -> None:
    connector = SDMXSourceConnector()
    handle = _handle()

    async def arbitrary_callable(**_kwargs: object) -> dict[str, str]:
        raise AssertionError("a raw cached callable must not be invoked")

    handle.set_state("_sdmx_head_executor", arbitrary_callable)
    with pytest.raises(TypeError, match="connection state key '_sdmx_head_executor'"):
        connector._head_executor(handle)


def test_chunked_content_rejects_bytearray_extendable_non_bytes_chunks() -> None:
    class _IntegerStream:
        async def iter_chunked(self, _chunk_size: int) -> AsyncIterator[object]:
            yield [65, 66]

    with pytest.raises(TypeError, match="non-bytes chunk"):
        _run(
            read_bounded_response_body(
                _ReadOnlyResponse(b"AB", _IntegerStream()),
                connector_id="test.http",
                url="https://example.test/data",
                max_response_bytes=32,
                max_decompressed_bytes=32,
            )
        )
