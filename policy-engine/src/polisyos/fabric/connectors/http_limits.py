"""HTTP response byte-limit helpers shared by Fabric connector families."""

from __future__ import annotations

from typing import Any

from polisyos.fabric.connectors.types import FetchError

DEFAULT_READ_CHUNK_SIZE = 64 * 1024


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def read_bounded_response_body(
    response: Any,
    *,
    connector_id: str,
    url: str,
    max_response_bytes: int | None,
    max_decompressed_bytes: int | None,
    chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
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
    if content is not None and hasattr(content, "iter_chunked"):
        async for chunk in content.iter_chunked(chunk_size):
            raw.extend(chunk)
            _raise_if_body_limit_exceeded(
                len(raw),
                connector_id=connector_id,
                url=url,
                max_response_bytes=max_response_bytes,
                max_decompressed_bytes=max_decompressed_bytes,
            )
        return bytes(raw)

    fallback = await response.read()
    _raise_if_body_limit_exceeded(
        len(fallback),
        connector_id=connector_id,
        url=url,
        max_response_bytes=max_response_bytes,
        max_decompressed_bytes=max_decompressed_bytes,
    )
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
                "HTTP response body exceeds safe limit "
                f"({size} > {max_response_bytes} bytes)"
            ),
            connector_id=connector_id,
            request_params={"url": url},
        )
    if max_decompressed_bytes is not None and size > max_decompressed_bytes:
        raise FetchError(
            message=(
                "Decoded HTTP body exceeds safe limit "
                f"({size} > {max_decompressed_bytes} bytes)"
            ),
            connector_id=connector_id,
            request_params={"url": url},
        )


__all__ = ["DEFAULT_READ_CHUNK_SIZE", "read_bounded_response_body"]
