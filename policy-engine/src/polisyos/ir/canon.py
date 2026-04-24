"""Public ir canon module API."""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import math
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import BaseModel

_CANONICAL_TYPES = frozenset({"datetime", "date", "decimal", "bytes", "float"})


class _Hasher(Protocol):
    def update(self, data: bytes, /) -> None: ...

    def hexdigest(self) -> str: ...


class CanonViolation(ValueError):  # noqa: N818 - ADR-0104 preserves public API name.
    """Canon violation public type."""

    pass


@dataclass(frozen=True)
class CanonSpec:
    """Canon spec data model."""

    name: str = "polisyos.canon.json"
    version: str = "0.2.0"

    forbid_floats: bool = True
    forbid_nan_inf: bool = True
    exclude_none: bool = True
    max_depth: int = 128

    sort_keys: bool = True
    separators: tuple[str, str] = (",", ":")
    ensure_ascii: bool = False


def _iso_utc(dt: datetime) -> str:
    """Normalize datetimes to the canonical UTC ``Z`` representation.

    Naive datetimes are interpreted as UTC for legacy canon compatibility; IR
    contracts that need stronger guarantees, such as ``Fact.tx_time``, validate
    awareness before reaching this generic serializer.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _check_depth(depth: int, max_depth: int) -> None:
    if depth > max_depth:
        raise CanonViolation(f"Canonical JSON recursion depth exceeds max_depth={max_depth}")


def _canonical_float_repr(value: float) -> str:
    if value == 0.0:
        return "0"
    return format(value, ".17g")


def _canonicalize_mapping(obj: Mapping[Any, Any], spec: CanonSpec, depth: int) -> dict[str, Any]:
    if "_type" in obj:
        kind = obj.get("_type")
        if kind not in _CANONICAL_TYPES:
            raise CanonViolation(f"Unknown canonical _type: {kind!r}")

    out: dict[str, Any] = {}
    for k, v in obj.items():
        if not isinstance(k, str):
            raise CanonViolation(f"JSON keys must be str, got: {type(k)}")
        out[k] = _canonicalize_obj(v, spec, depth + 1)
    return out


def _canonicalize_dataclass(obj: Any, spec: CanonSpec, depth: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in dataclasses.fields(obj):
        value = getattr(obj, field.name)
        if spec.exclude_none and value is None:
            continue
        out[field.name] = _canonicalize_obj(value, spec, depth + 1)
    return out


def _canonicalize_obj(obj: Any, spec: CanonSpec, depth: int = 0) -> Any:
    _check_depth(depth, spec.max_depth)

    if isinstance(obj, BaseModel):
        return _canonicalize_obj(
            obj.model_dump(mode="python", by_alias=True, exclude_none=spec.exclude_none),
            spec,
            depth + 1,
        )

    if dataclasses.is_dataclass(obj):
        return _canonicalize_dataclass(obj, spec, depth + 1)

    if isinstance(obj, datetime):
        return {"_type": "datetime", "iso_utc": _iso_utc(obj)}
    if isinstance(obj, date):
        return {"_type": "date", "iso": obj.isoformat()}

    if isinstance(obj, Decimal):
        return {"_type": "decimal", "value": str(obj)}

    if isinstance(obj, (bytes, bytearray, memoryview)):
        b = bytes(obj)
        return {
            "_type": "bytes",
            "encoding": "base64",
            "data": base64.b64encode(b).decode("ascii"),
        }

    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if spec.forbid_nan_inf and (math.isnan(obj) or math.isinf(obj)):
            raise CanonViolation("NaN/Inf forbidden in canonical JSON")
        if spec.forbid_floats:
            raise CanonViolation("float forbidden in canonical JSON")
        return {"_type": "float", "repr": _canonical_float_repr(obj)}

    if isinstance(obj, str):
        return obj

    if isinstance(obj, Mapping):
        return _canonicalize_mapping(obj, spec, depth + 1)

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray, memoryview)):
        return [_canonicalize_obj(x, spec, depth + 1) for x in obj]

    raise CanonViolation(f"Unsupported type for canonical JSON: {type(obj)}")


def to_canonical_bytes(obj: Any, spec: CanonSpec | None = None) -> bytes:
    """Convert to canonical bytes."""
    spec = spec or CanonSpec()
    canon_obj = _canonicalize_obj(obj, spec)
    try:
        payload = json.dumps(
            canon_obj,
            sort_keys=spec.sort_keys,
            separators=spec.separators,
            ensure_ascii=spec.ensure_ascii,
            allow_nan=False,
        )
    except ValueError as exc:
        raise CanonViolation(str(exc)) from exc
    return payload.encode("utf-8")


def _parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def from_canonical_obj(obj: Any, *, max_depth: int = 128, _depth: int = 0) -> Any:
    """Create from canonical obj."""
    _check_depth(_depth, max_depth)
    if isinstance(obj, Mapping):
        if "_type" in obj:
            kind = obj.get("_type")
            if kind == "datetime":
                return _parse_datetime(obj["iso_utc"])
            if kind == "date":
                return date.fromisoformat(obj["iso"])
            if kind == "decimal":
                return Decimal(obj["value"])
            if kind == "bytes":
                data = obj["data"]
                return base64.b64decode(data.encode("ascii"))
            if kind == "float":
                return float(obj["repr"])
            raise CanonViolation(f"Unknown canonical _type: {kind!r}")
        return {
            k: from_canonical_obj(v, max_depth=max_depth, _depth=_depth + 1) for k, v in obj.items()
        }

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray, memoryview)):
        return [from_canonical_obj(item, max_depth=max_depth, _depth=_depth + 1) for item in obj]

    return obj


def from_canonical_bytes(data: bytes, *, max_depth: int = 128) -> Any:
    """Create from canonical bytes."""
    payload = json.loads(data)
    return from_canonical_obj(payload, max_depth=max_depth)


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
