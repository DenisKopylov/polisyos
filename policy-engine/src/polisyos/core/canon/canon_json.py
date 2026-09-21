"""Core strict canonical JSON facade with the extended typed-tag profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.common.canonical import (
    CanonSpec as _SharedCanonSpec,
    from_canonical_bytes as _from_canonical_bytes,
    from_canonical_obj as _from_canonical_obj,
    to_canonical_bytes as _to_canonical_bytes,
)

_CANONICAL_TYPES = frozenset(
    {
        "array_digest",
        "bytes",
        "bytes_hex",
        "date",
        "datetime",
        "decimal",
        "float",
        "float_hex",
    }
)


class CanonViolation(ValueError):  # noqa: N818 - ADR-0104 preserves public API name.
    """Canon violation public type."""


@dataclass(frozen=True)
class CanonSpec(_SharedCanonSpec):
    """Controls the Core canonical JSON profile."""


def to_canonical_bytes(obj: Any, spec: CanonSpec | None = None) -> bytes:
    """Convert to canonical bytes using Core's extended typed-tag profile."""
    return _to_canonical_bytes(
        obj,
        spec,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
    )


def from_canonical_obj(obj: Any, *, max_depth: int = 128, _depth: int = 0) -> Any:
    """Create a Core value from a canonical object."""
    return _from_canonical_obj(
        obj,
        max_depth=max_depth,
        _depth=_depth,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
    )


def from_canonical_bytes(data: bytes, *, max_depth: int = 128) -> Any:
    """Create a Core value from canonical bytes."""
    return _from_canonical_bytes(
        data,
        max_depth=max_depth,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
    )


__all__ = [
    "CanonSpec",
    "CanonViolation",
    "from_canonical_bytes",
    "from_canonical_obj",
    "to_canonical_bytes",
]
