"""Stable namespace identities for backend-local CAS cache paths."""

from __future__ import annotations

import hashlib
import json


def cache_namespace(
    *,
    backend: str,
    bucket: str,
    prefix: str,
    region: str | None = None,
) -> str:
    """Return a domain-separated key for one durable object-store namespace."""
    payload = json.dumps(
        [backend, bucket, prefix.rstrip("/"), region],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(b"polisyos.cas.local-cache-namespace.v1\0" + payload).hexdigest()


__all__ = ["cache_namespace"]
