"""Public IR canon module API with its strict historical tag profile."""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from polisyos.common.canonical import (
    CanonSpec as _SharedCanonSpec,
    from_canonical_bytes as _from_canonical_bytes,
    from_canonical_obj as _from_canonical_obj,
    to_canonical_bytes as _to_canonical_bytes,
)

_CANONICAL_TYPES = frozenset({"datetime", "date", "decimal", "bytes", "float"})


class _Hasher(Protocol):
    def update(self, data: bytes, /) -> None: ...

    def hexdigest(self) -> str: ...


class CanonViolation(ValueError):  # noqa: N818 - ADR-0104 preserves public API name.
    """Canon violation public type."""


@dataclass(frozen=True)
class CanonSpec(_SharedCanonSpec):
    """Canon spec data model for the IR profile."""


def to_canonical_bytes(obj: Any, spec: CanonSpec | None = None) -> bytes:
    """Convert to canonical bytes using IR's strict historical tag profile."""
    return _to_canonical_bytes(
        obj,
        spec,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
    )


def from_canonical_obj(obj: Any, *, max_depth: int = 128, _depth: int = 0) -> Any:
    """Create an IR value from a canonical object."""
    return _from_canonical_obj(
        obj,
        max_depth=max_depth,
        _depth=_depth,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
    )


def from_canonical_bytes(data: bytes, *, max_depth: int = 128) -> Any:
    """Create an IR value from canonical bytes."""
    return _from_canonical_bytes(
        data,
        max_depth=max_depth,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
    )


HashAlgorithm = Literal["sha256", "blake2b"]
DeprecatedHashAlgorithm = Literal["sha1"]


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
    """Hash a byte stream using the canonical CAS hash policy.

    ``str`` payloads are encoded as UTF-8 before hashing. Use
    ``to_canonical_bytes`` for structured payloads when strings and raw bytes
    must remain semantically distinct.
    """
    hasher = _new_hasher(algorithm, digest_size=digest_size)
    hasher.update(_to_bytes(payload))
    digest = hasher.hexdigest()
    if prefix:
        return f"{algorithm}:{digest}"
    return digest


__all__ = [
    "CanonSpec",
    "CanonViolation",
    "DeprecatedHashAlgorithm",
    "HashAlgorithm",
    "content_hash",
    "from_canonical_bytes",
    "from_canonical_obj",
    "to_canonical_bytes",
]
