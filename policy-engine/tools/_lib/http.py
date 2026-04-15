"""Bounded HTTP helpers for tooling scripts."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Mapping
from typing import Any


def read_bounded_response(response: Any, *, max_bytes: int) -> bytes:
    """Read an HTTP response with a hard cap to avoid unbounded memory growth."""

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, max_bytes + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"response exceeds configured cap of {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def fetch_json(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout_seconds: float = 20.0,
    max_bytes: int = 1024 * 1024,
) -> Any:
    """Fetch and decode JSON with explicit timeout and response-size bounds."""

    request = urllib.request.Request(url, headers=dict(headers or {}))
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = read_bounded_response(response, max_bytes=max_bytes)
    return json.loads(raw.decode("utf-8"))
