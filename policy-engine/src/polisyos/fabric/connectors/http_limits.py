"""HTTP response byte-limit helpers shared by Fabric connector families."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Protocol

from polisyos.core import scan_secret_and_pii
from polisyos.fabric.connectors.base import (
    _invoke_runtime_callable,
    _is_runtime_async_iterable,
    _is_runtime_callable,
)
from polisyos.fabric.connectors.types import FetchError


class _HTTPHeaders(Protocol):
    def get(self, key: str, /) -> str | None: ...


class _BeforeClassification(Protocol):
    def __call__(self, payload: bytes, /) -> None: ...


class _OnProgress(Protocol):
    def __call__(self, byte_count: int, /) -> None: ...


class _HTTPResponse(Protocol):
    @property
    def headers(self) -> _HTTPHeaders: ...

    @property
    def content(self) -> object: ...

    async def read(self) -> bytes: ...


class _ChunkedContentReader:
    """Invoke one chunked reader and validate its async stream at consumption."""

    __slots__ = ("_iter_chunked",)

    def __init__(self, iter_chunked: Callable[..., object]) -> None:
        self._iter_chunked = iter_chunked

    async def iter_chunked(self, chunk_size: int, /) -> AsyncIterator[bytes]:
        stream = _invoke_runtime_callable(self._iter_chunked, chunk_size)
        if not _is_runtime_async_iterable(stream):
            raise TypeError("HTTP iter_chunked callback did not return an async iterable")
        async for chunk in stream:
            if not isinstance(chunk, bytes):
                raise TypeError("HTTP iter_chunked stream yielded a non-bytes chunk")
            yield chunk


def _chunked_content_reader(value: object) -> _ChunkedContentReader | None:
    callback = getattr(value, "iter_chunked", None)
    if not _is_runtime_callable(callback):
        return None
    return _ChunkedContentReader(callback)


DEFAULT_READ_CHUNK_SIZE = 64 * 1024


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def read_bounded_response_body(
    response: _HTTPResponse,
    *,
    connector_id: str,
    url: str,
    max_response_bytes: int | None,
    max_decompressed_bytes: int | None,
    chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
    before_classification: _BeforeClassification | None = None,
    on_progress: _OnProgress | None = None,
) -> bytes:
    """Read an aiohttp-style response body with explicit byte ceilings."""

    content_length = _safe_int(response.headers.get("Content-Length"))
    if (
        max_response_bytes is not None
        and content_length is not None
        and content_length > max_response_bytes
    ):
        raise FetchError(
            message=(
                "HTTP response body exceeds safe limit "
                f"({content_length} > {max_response_bytes} bytes)"
            ),
            connector_id=connector_id,
            request_params={"url": url},
        )

    raw = bytearray()
    content = getattr(response, "content", None)
    chunked_reader = _chunked_content_reader(content)
    if chunked_reader is not None:
        async for chunk in chunked_reader.iter_chunked(chunk_size):
            raw.extend(chunk)
            _raise_if_body_limit_exceeded(
                len(raw),
                connector_id=connector_id,
                url=url,
                max_response_bytes=max_response_bytes,
                max_decompressed_bytes=max_decompressed_bytes,
            )
            if on_progress is not None:
                on_progress(len(raw))
        payload = bytes(raw)
        if before_classification is not None:
            before_classification(payload)
        _raise_if_secret_pii_found(payload, connector_id=connector_id, url=url)
        return payload

    fallback = await response.read()
    _raise_if_body_limit_exceeded(
        len(fallback),
        connector_id=connector_id,
        url=url,
        max_response_bytes=max_response_bytes,
        max_decompressed_bytes=max_decompressed_bytes,
    )
    if on_progress is not None:
        on_progress(len(fallback))
    if before_classification is not None:
        before_classification(fallback)
    _raise_if_secret_pii_found(fallback, connector_id=connector_id, url=url)
    return fallback


def _raise_if_body_limit_exceeded(
    size: int,
    *,
    connector_id: str,
    url: str,
    max_response_bytes: int | None,
    max_decompressed_bytes: int | None,
) -> None:
    if max_response_bytes is not None and size > max_response_bytes:
        raise FetchError(
            message=(
                f"HTTP response body exceeds safe limit ({size} > {max_response_bytes} bytes)"
            ),
            connector_id=connector_id,
            request_params={"url": url},
        )
    if max_decompressed_bytes is not None and size > max_decompressed_bytes:
        raise FetchError(
            message=(
                f"Decoded HTTP body exceeds safe limit ({size} > {max_decompressed_bytes} bytes)"
            ),
            connector_id=connector_id,
            request_params={"url": url},
        )


def _raise_if_secret_pii_found(payload: bytes, *, connector_id: str, url: str) -> None:
    try:
        result = scan_secret_and_pii(
            payload,
            scope="connector request/response payloads",
            artifact_ref_or_route=f"connector://{connector_id}/response",
            redact=False,
            block_on_findings=True,
        )
    except Exception as exc:
        raise FetchError(
            message="Connector response secret/PII scan failed closed",
            connector_id=connector_id,
            request_params={"url": url, "scan_error": type(exc).__name__},
        ) from exc
    if result.has_findings:
        raise FetchError(
            message=(
                "Connector response blocked by secret/PII scan: " + ",".join(result.finding_kinds)
            ),
            connector_id=connector_id,
            request_params={"url": url, "secret_pii_scope": "connector_response"},
        )


__all__ = ["DEFAULT_READ_CHUNK_SIZE", "read_bounded_response_body"]
