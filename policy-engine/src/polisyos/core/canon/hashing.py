"""Core hashing facade with structured fingerprint compatibility helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from polisyos.common.hashing import (
    DeprecatedHashAlgorithm,
    HashAlgorithm,
    content_hash as _content_hash,
    streaming_hash as _streaming_hash,
    truncated_hash as _truncated_hash,
)

from .canon_json import CanonSpec, to_canonical_bytes


def content_hash(
    payload: bytes | bytearray | memoryview | str,
    *,
    algorithm: HashAlgorithm | DeprecatedHashAlgorithm = "sha256",
    prefix: bool = False,
    digest_size: int | None = None,
) -> str:
    """Hash byte/string payload with the Core-compatible CAS policy."""
    return _content_hash(
        payload,
        algorithm=algorithm,
        prefix=prefix,
        digest_size=digest_size,
    )


def fingerprint(
    value: Any,
    *,
    algorithm: HashAlgorithm | DeprecatedHashAlgorithm = "sha256",
    prefix: bool = False,
    canon_spec: CanonSpec | None = None,
    digest_size: int | None = None,
) -> str:
    """Hash a structured value after Core canonical JSON encoding."""
    canonical = to_canonical_bytes(value, canon_spec)
    return content_hash(
        canonical,
        algorithm=algorithm,
        prefix=prefix,
        digest_size=digest_size,
    )


def truncated_hash(
    payload: bytes | bytearray | memoryview | str,
    *,
    length: int = 16,
    algorithm: HashAlgorithm | DeprecatedHashAlgorithm = "sha256",
    prefix: bool = False,
    digest_size: int | None = None,
) -> str:
    """Return a truncated Core-compatible digest."""
    return _truncated_hash(
        payload,
        length=length,
        algorithm=algorithm,
        prefix=prefix,
        digest_size=digest_size,
    )


def streaming_hash(
    chunks: Iterable[bytes | bytearray | memoryview],
    *,
    algorithm: HashAlgorithm | DeprecatedHashAlgorithm = "sha256",
    prefix: bool = False,
    digest_size: int | None = None,
) -> str:
    """Hash an iterable of binary chunks with the Core-compatible policy."""
    return _streaming_hash(
        chunks,
        algorithm=algorithm,
        prefix=prefix,
        digest_size=digest_size,
    )


__all__ = [
    "DeprecatedHashAlgorithm",
    "content_hash",
    "fingerprint",
    "streaming_hash",
    "truncated_hash",
]
