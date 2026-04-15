"""Hashing helpers built on canonical JSON so artifact IDs stay stable across runtimes."""
from __future__ import annotations

import hashlib
import warnings
from collections.abc import Iterable
from typing import Any, Literal, Protocol

from .canon_json import CanonSpec, to_canonical_bytes

HashAlgorithm = Literal["sha256", "blake2b"]
DeprecatedHashAlgorithm = Literal["sha1"]


class _Hasher(Protocol):
    def update(self, data: bytes, /) -> None:
        ...

    def hexdigest(self) -> str:
        ...


def _new_hasher(
    algorithm: HashAlgorithm | DeprecatedHashAlgorithm,
    *,
    digest_size: int | None = None,
) -> _Hasher:
    if algorithm == "sha256":
        return hashlib.sha256()
    if algorithm == "sha1":
        warnings.warn(
            "sha1 content hashing is deprecated and must be requested explicitly; "
            "use sha256 for canonical CAS paths.",
            DeprecationWarning,
            stacklevel=2,
        )
        # ADR-0104 keeps sha1 only for explicit legacy reads with a warning.
        return hashlib.sha1()  # noqa: S324
    if algorithm == "blake2b":
        if digest_size is not None:
            return hashlib.blake2b(digest_size=digest_size)
        return hashlib.blake2b()
    raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def _to_bytes(value: bytes | bytearray | memoryview | str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, str):
        return value.encode("utf-8")
    raise TypeError(f"Unsupported payload type for hashing: {type(value).__name__}")


def content_hash(
    payload: bytes | bytearray | memoryview | str,
    *,
    algorithm: HashAlgorithm | DeprecatedHashAlgorithm = "sha256",
    prefix: bool = False,
    digest_size: int | None = None,
) -> str:
    """
    Hash byte/string payload with a consistent API.

    Args:
        payload: Raw bytes or UTF-8 string.
        algorithm: Hash algorithm. sha1 is accepted only as an explicit
            deprecated legacy branch; canonical CAS paths use sha256.
        prefix: If True, prepend '<algorithm>:'.
        digest_size: Optional digest size for blake2b.
    """

    hasher = _new_hasher(algorithm, digest_size=digest_size)
    hasher.update(_to_bytes(payload))
    digest = hasher.hexdigest()
    if prefix:
        return f"{algorithm}:{digest}"
    return digest


def fingerprint(
    value: Any,
    *,
    algorithm: HashAlgorithm | DeprecatedHashAlgorithm = "sha256",
    prefix: bool = False,
    canon_spec: CanonSpec | None = None,
    digest_size: int | None = None,
) -> str:
    """
    Hash a structured value after normalizing it through canonical JSON encoding.

    This is the default path for stable artifact fingerprints because it removes
    representation differences between dicts, models, and dataclasses.
    """

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
    """
    Return truncated digest (first N hex chars).
    """

    if length <= 0:
        raise ValueError("length must be > 0")
    digest = content_hash(
        payload,
        algorithm=algorithm,
        prefix=False,
        digest_size=digest_size,
    )[:length]
    if prefix:
        return f"{algorithm}:{digest}"
    return digest


def streaming_hash(
    chunks: Iterable[bytes | bytearray | memoryview],
    *,
    algorithm: HashAlgorithm | DeprecatedHashAlgorithm = "sha256",
    prefix: bool = False,
    digest_size: int | None = None,
) -> str:
    """Hash an iterable of binary chunks."""

    hasher = _new_hasher(algorithm, digest_size=digest_size)
    for chunk in chunks:
        hasher.update(_to_bytes(chunk))
    digest = hasher.hexdigest()
    if prefix:
        return f"{algorithm}:{digest}"
    return digest
