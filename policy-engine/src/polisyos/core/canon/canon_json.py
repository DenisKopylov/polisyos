"""Core strict canonical JSON facade with the extended typed-tag profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.common.canonical import (
    ArrayDigestRepresentation,
    BytesHexRepresentation,
    CanonicalResourceLimits,
    FloatHexRepresentation,
    _admit_canon_spec,
)
from polisyos.common.canonical import (
    CanonSpec as _SharedCanonSpec,
)
from polisyos.common.canonical import (
    from_canonical_bytes as _from_canonical_bytes,
)
from polisyos.common.canonical import (
    from_canonical_obj as _from_canonical_obj,
)
from polisyos.common.canonical import (
    to_bounded_canonical_bytes as _to_bounded_canonical_bytes,
)
from polisyos.common.canonical import (
    to_canonical_bytes as _to_canonical_bytes,
)
from polisyos.common.canonical_profile import (
    CanonicalProfileRefusalError,
    _decode_and_reencode_profiled_bytes,
)

CORE_TAG_POLICY_ID = "core-tag-policy@1"
CORE_V3_TAG_POLICY_ID = "core-tag-policy@2"

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


class _CoreCanonicalProfileError(CanonViolation, CanonicalProfileRefusalError):
    """Preserve Core and profile-refusal catches for nonconformant encoded output."""

    def __init__(self, code: str) -> None:
        """Expose the stable profile refusal code through both exception contracts."""
        self.code = code
        ValueError.__init__(self, code)


@dataclass(frozen=True)
class CanonSpec(_SharedCanonSpec):
    """Controls the Core canonical JSON profile."""


def _encode_core_canonical_bytes_raw(obj: Any, spec: CanonSpec) -> bytes:
    """Encode with the shared primitive, without public admission or re-entry."""
    return _to_canonical_bytes(
        obj,
        spec,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
    )


def to_canonical_bytes(obj: Any, spec: CanonSpec | None = None) -> bytes:
    """Emit only bytes that round-trip under Core's selected canonical profile."""
    selected_spec = _admit_canon_spec(spec, CanonSpec, violation_type=CanonViolation)
    data = _encode_core_canonical_bytes_raw(obj, selected_spec)
    try:
        _validate_core_json_payload_conformance(data, selected_spec)
    except CanonicalProfileRefusalError as exc:
        raise _CoreCanonicalProfileError(exc.code) from exc
    return data


def to_bounded_canonical_bytes(obj: Any, spec: CanonSpec, limits: CanonicalResourceLimits) -> bytes:
    """Encode a callback-free Core value under an owner-supplied physical vector."""
    selected_spec = _admit_canon_spec(spec, CanonSpec, violation_type=CanonViolation)
    data = _to_bounded_canonical_bytes(
        obj,
        selected_spec,
        limits,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
    )
    try:
        _validate_core_json_payload_conformance(data, selected_spec)
    except CanonicalProfileRefusalError as exc:
        raise _CoreCanonicalProfileError(exc.code) from exc
    return data


def from_canonical_obj(
    obj: Any, *, max_depth: int = 128, _depth: int = 0, version: str = "0.2.0"
) -> Any:
    """Create a Core value from a canonical object."""
    return _from_canonical_obj(
        obj,
        max_depth=max_depth,
        _depth=_depth,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
        version=version,
    )


def from_canonical_bytes(data: bytes, *, max_depth: int = 128, version: str = "0.2.0") -> Any:
    """Create a Core value from canonical bytes."""
    return _from_canonical_bytes(
        data,
        max_depth=max_depth,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
        version=version,
    )


def _validate_core_json_payload_conformance(data: bytes, spec: CanonSpec) -> None:
    """Require Core JSON bytes to round-trip under their declared profile."""
    _decode_and_reencode_profiled_bytes(
        data,
        max_depth=spec.max_depth,
        spec=spec,
        decode=lambda payload, max_depth: from_canonical_bytes(
            payload,
            max_depth=max_depth,
            version=spec.version if spec.name == "polisyos.canon.json" else "0.2.0",
        ),
        encode=lambda value, _selected_spec: _encode_core_canonical_bytes_raw(value, spec),
    )


__all__ = [
    "CORE_TAG_POLICY_ID",
    "CORE_V3_TAG_POLICY_ID",
    "ArrayDigestRepresentation",
    "BytesHexRepresentation",
    "CanonSpec",
    "CanonViolation",
    "CanonicalResourceLimits",
    "FloatHexRepresentation",
    "from_canonical_bytes",
    "from_canonical_obj",
    "to_bounded_canonical_bytes",
    "to_canonical_bytes",
]
