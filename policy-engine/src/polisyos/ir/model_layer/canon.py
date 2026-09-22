"""Public IR canon module API with its strict historical tag profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.common.canonical import (
    CanonSpec as _SharedCanonSpec,
    from_canonical_bytes as _from_canonical_bytes,
    from_canonical_obj as _from_canonical_obj,
    to_canonical_bytes as _to_canonical_bytes,
)
from polisyos.common.hashing import (
    DeprecatedHashAlgorithm,
    HashAlgorithm,
    content_hash as _content_hash,
)

_CANONICAL_TYPES = frozenset({"datetime", "date", "decimal", "bytes", "float"})


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
    return _content_hash(
        payload,
        algorithm=algorithm,
        prefix=prefix,
        digest_size=digest_size,
    )


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
