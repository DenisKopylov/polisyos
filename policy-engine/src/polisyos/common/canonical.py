"""Shared strict canonical JSON mechanics for the Core and IR profiles.

The public facades intentionally provide their own ``CanonViolation`` classes
and typed-tag sets.  This module owns only the mechanics that are common to
both profiles; callers supply the profile-specific error type and supported
tag set so a relocation cannot widen the historical IR decoder or merge the
two public exception identities.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import NoReturn

from pydantic import BaseModel

# Inputs remain intentionally polymorphic (dataclasses, Pydantic models, and
# custom values are runtime-dispatched); the recursive alias describes the
# JSON-safe value produced by the encoder without changing that boundary.
type _CanonicalValue = (
    None | bool | int | float | str | dict[str, "_CanonicalValue"] | list["_CanonicalValue"]
)

_ALL_CANONICAL_TYPES = frozenset(
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


class CanonicalError(ValueError):
    """Fallback error for direct use of the shared primitive."""


@dataclass(frozen=True)
class CanonSpec:
    """Controls how arbitrary Python objects are normalized into JSON bytes."""

    name: str = "polisyos.canon.json"
    version: str = "0.2.0"

    forbid_floats: bool = True
    forbid_nan_inf: bool = True
    exclude_none: bool = True
    max_depth: int = 128

    sort_keys: bool = True
    separators: tuple[str, str] = (",", ":")
    ensure_ascii: bool = False


def _raise_violation(violation_type: type[ValueError], message: str) -> NoReturn:
    raise violation_type(message)


def _iso_utc(dt: datetime) -> str:
    """Normalize datetimes to the canonical UTC ``Z`` representation."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _check_depth(depth: int, max_depth: int, violation_type: type[ValueError]) -> None:
    if depth > max_depth:
        _raise_violation(
            violation_type,
            f"Canonical JSON recursion depth exceeds max_depth={max_depth}",
        )


def _canonical_float_repr(value: float) -> str:
    if value == 0.0:
        return "0"
    return format(value, ".17g")


def _canonicalize_mapping(
    obj: Mapping[object, object],
    spec: CanonSpec,
    depth: int,
    *,
    violation_type: type[ValueError],
    canonical_types: Collection[str],
) -> dict[str, _CanonicalValue]:
    if "_type" in obj:
        kind = obj.get("_type")
        if not isinstance(kind, str) or kind not in canonical_types:
            _raise_violation(violation_type, f"Unknown canonical _type: {kind!r}")

    out: dict[str, _CanonicalValue] = {}
    for key, value in obj.items():
        if not isinstance(key, str):
            _raise_violation(violation_type, f"JSON keys must be str, got: {type(key)}")
        out[key] = _canonicalize_obj(
            value,
            spec,
            depth + 1,
            violation_type=violation_type,
            canonical_types=canonical_types,
        )
    return out


def _canonicalize_dataclass(
    obj: object,
    spec: CanonSpec,
    depth: int,
    *,
    violation_type: type[ValueError],
    canonical_types: Collection[str],
) -> dict[str, _CanonicalValue]:
    out: dict[str, _CanonicalValue] = {}
    for field in dataclasses.fields(obj):
        value = getattr(obj, field.name)
        if spec.exclude_none and value is None:
            continue
        out[field.name] = _canonicalize_obj(
            value,
            spec,
            depth + 1,
            violation_type=violation_type,
            canonical_types=canonical_types,
        )
    return out


def _canonicalize_obj(
    obj: object,
    spec: CanonSpec,
    depth: int = 0,
    *,
    violation_type: type[ValueError],
    canonical_types: Collection[str],
) -> _CanonicalValue:
    _check_depth(depth, spec.max_depth, violation_type)

    if isinstance(obj, BaseModel):
        return _canonicalize_obj(
            obj.model_dump(mode="python", by_alias=True, exclude_none=spec.exclude_none),
            spec,
            depth + 1,
            violation_type=violation_type,
            canonical_types=canonical_types,
        )

    if dataclasses.is_dataclass(obj):
        return _canonicalize_dataclass(
            obj,
            spec,
            depth + 1,
            violation_type=violation_type,
            canonical_types=canonical_types,
        )

    if isinstance(obj, datetime):
        return {"_type": "datetime", "iso_utc": _iso_utc(obj)}
    if isinstance(obj, date):
        return {"_type": "date", "iso": obj.isoformat()}

    if isinstance(obj, Decimal):
        return {"_type": "decimal", "value": str(obj)}

    if isinstance(obj, (bytes, bytearray, memoryview)):
        raw = bytes(obj)
        return {
            "_type": "bytes",
            "encoding": "base64",
            "data": base64.b64encode(raw).decode("ascii"),
        }

    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if spec.forbid_nan_inf and (math.isnan(obj) or math.isinf(obj)):
            _raise_violation(violation_type, "NaN/Inf forbidden in canonical JSON")
        if spec.forbid_floats:
            _raise_violation(violation_type, "float forbidden in canonical JSON")
        return {"_type": "float", "repr": _canonical_float_repr(obj)}

    if isinstance(obj, str):
        return obj

    if isinstance(obj, Mapping):
        return _canonicalize_mapping(
            obj,
            spec,
            depth + 1,
            violation_type=violation_type,
            canonical_types=canonical_types,
        )

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray, memoryview)):
        return [
            _canonicalize_obj(
                item,
                spec,
                depth + 1,
                violation_type=violation_type,
                canonical_types=canonical_types,
            )
            for item in obj
        ]

    _raise_violation(violation_type, f"Unsupported type for canonical JSON: {type(obj)}")


def to_canonical_bytes(
    obj: object,
    spec: CanonSpec | None = None,
    *,
    violation_type: type[ValueError] = CanonicalError,
    canonical_types: Collection[str] = _ALL_CANONICAL_TYPES,
) -> bytes:
    """Convert a value to canonical bytes under an explicit typed-tag profile."""
    spec = spec or CanonSpec()
    canon_obj = _canonicalize_obj(
        obj,
        spec,
        violation_type=violation_type,
        canonical_types=canonical_types,
    )
    try:
        payload = json.dumps(
            canon_obj,
            sort_keys=spec.sort_keys,
            separators=spec.separators,
            ensure_ascii=spec.ensure_ascii,
            allow_nan=False,
        )
    except ValueError as exc:
        raise violation_type(str(exc)) from exc
    return payload.encode("utf-8")


def _parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def from_canonical_obj(
    obj: object,
    *,
    max_depth: int = 128,
    _depth: int = 0,
    violation_type: type[ValueError] = CanonicalError,
    canonical_types: Collection[str] = _ALL_CANONICAL_TYPES,
) -> object:
    """Decode canonical objects under an explicit typed-tag profile."""
    _check_depth(_depth, max_depth, violation_type)
    if isinstance(obj, Mapping):
        if "_type" in obj:
            kind = obj.get("_type")
            if not isinstance(kind, str) or kind not in canonical_types:
                _raise_violation(violation_type, f"Unknown canonical _type: {kind!r}")
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
            if kind == "float_hex":
                return float.fromhex(obj["value"])
            if kind == "bytes_hex":
                return bytes.fromhex(obj["value"])
            if kind == "array_digest":
                return dict(obj)
            _raise_violation(violation_type, f"Unknown canonical _type: {kind!r}")
        return {
            key: from_canonical_obj(
                value,
                max_depth=max_depth,
                _depth=_depth + 1,
                violation_type=violation_type,
                canonical_types=canonical_types,
            )
            for key, value in obj.items()
        }

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray, memoryview)):
        return [
            from_canonical_obj(
                item,
                max_depth=max_depth,
                _depth=_depth + 1,
                violation_type=violation_type,
                canonical_types=canonical_types,
            )
            for item in obj
        ]

    return obj


def from_canonical_bytes(
    data: bytes,
    *,
    max_depth: int = 128,
    violation_type: type[ValueError] = CanonicalError,
    canonical_types: Collection[str] = _ALL_CANONICAL_TYPES,
) -> object:
    """Decode canonical bytes under an explicit typed-tag profile."""
    payload = json.loads(data)
    return from_canonical_obj(
        payload,
        max_depth=max_depth,
        violation_type=violation_type,
        canonical_types=canonical_types,
    )


__all__ = [
    "CanonSpec",
    "CanonicalError",
    "from_canonical_bytes",
    "from_canonical_obj",
    "to_canonical_bytes",
]
