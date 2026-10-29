"""Public IR canon module API with its strict historical tag profile."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.common.canonical import (
    CanonSpec as _SharedCanonSpec,
)
from polisyos.common.canonical import (
    _admit_canon_spec,
)
from polisyos.common.canonical import (
    from_canonical_bytes as _from_canonical_bytes,
)
from polisyos.common.canonical import (
    from_canonical_obj as _from_canonical_obj,
)
from polisyos.common.canonical import (
    to_canonical_bytes as _to_canonical_bytes,
)
from polisyos.common.canonical_profile import (
    CanonicalProfileRefusalError,
    _decode_and_reencode_profiled_bytes,
)
from polisyos.common.hashing import (
    DeprecatedHashAlgorithm,
    HashAlgorithm,
)
from polisyos.common.hashing import (
    content_hash as _content_hash,
)

IR_TAG_POLICY_ID = "ir-tag-policy@1"
IR_V3_TAG_POLICY_ID = "ir-tag-policy@2"

_CANONICAL_TYPES = frozenset({"datetime", "date", "decimal", "bytes", "float"})


class CanonViolation(ValueError):  # noqa: N818 - ADR-0104 preserves public API name.
    """Canon violation public type."""


class _IRCanonicalProfileError(CanonViolation, CanonicalProfileRefusalError):
    """Preserve IR and profile-refusal catches for nonconformant encoded output."""

    def __init__(self, code: str) -> None:
        """Expose the stable profile refusal code through both exception contracts."""
        self.code = code
        ValueError.__init__(self, code)


@dataclass(frozen=True)
class CanonSpec(_SharedCanonSpec):
    """Canon spec data model for the IR profile."""


def _encode_ir_canonical_bytes_raw(obj: object, spec: CanonSpec) -> bytes:
    """Encode with IR's selected typed-tag set without public admission or re-entry."""
    return _to_canonical_bytes(
        obj,
        spec,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
    )


def to_canonical_bytes(obj: object, spec: CanonSpec | None = None) -> bytes:
    """Emit bytes that round-trip under IR's selected canonical profile."""
    selected_spec = _admit_canon_spec(spec, CanonSpec, violation_type=CanonViolation)
    data = _encode_ir_canonical_bytes_raw(obj, selected_spec)
    try:
        _validate_ir_json_payload_conformance(data, selected_spec)
    except CanonicalProfileRefusalError as exc:
        raise _IRCanonicalProfileError(exc.code) from exc
    return data


def from_canonical_obj(
    obj: object, *, max_depth: int = 128, _depth: int = 0, version: str = "0.2.0"
) -> object:
    """Create an IR value from a canonical object."""
    return _from_canonical_obj(
        obj,
        max_depth=max_depth,
        _depth=_depth,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
        version=version,
    )


def from_canonical_bytes(data: bytes, *, max_depth: int = 128, version: str = "0.2.0") -> object:
    """Create an IR value from canonical bytes."""
    return _from_canonical_bytes(
        data,
        max_depth=max_depth,
        violation_type=CanonViolation,
        canonical_types=_CANONICAL_TYPES,
        version=version,
    )


def _validate_ir_json_payload_conformance(data: bytes, spec: CanonSpec) -> None:
    """Require IR bytes to round-trip under the exact selected profile and tag set."""
    _decode_and_reencode_profiled_bytes(
        data,
        max_depth=spec.max_depth,
        spec=spec,
        decode=lambda payload, max_depth: from_canonical_bytes(
            payload,
            max_depth=max_depth,
            version=spec.version if spec.name == "polisyos.canon.json" else "0.2.0",
        ),
        encode=lambda value, _selected_spec: _encode_ir_canonical_bytes_raw(value, spec),
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
    "IR_TAG_POLICY_ID",
    "IR_V3_TAG_POLICY_ID",
    "CanonSpec",
    "CanonViolation",
    "DeprecatedHashAlgorithm",
    "HashAlgorithm",
    "content_hash",
    "from_canonical_bytes",
    "from_canonical_obj",
    "to_canonical_bytes",
]
