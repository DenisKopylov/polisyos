"""Canonical JSON normalization for hashing, persistence, and cross-runtime comparisons."""
from __future__ import annotations

import base64
import dataclasses
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

_CANONICAL_TYPES = frozenset({"datetime", "date", "decimal", "bytes", "float"})


class CanonViolation(ValueError):  # noqa: N818 - ADR-0104 preserves public API name.
    """Canon violation public type."""
    pass


@dataclass(frozen=True)
class CanonSpec:
    """Controls how arbitrary Python objects are normalized into canonical JSON bytes."""
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
    contracts that need stronger guarantees validate awareness before reaching
    this generic serializer.
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
            k: from_canonical_obj(v, max_depth=max_depth, _depth=_depth + 1)
            for k, v in obj.items()
        }

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray, memoryview)):
        return [from_canonical_obj(item, max_depth=max_depth, _depth=_depth + 1) for item in obj]

    return obj


def from_canonical_bytes(data: bytes, *, max_depth: int = 128) -> Any:
    """Create from canonical bytes."""
    payload = json.loads(data)
    return from_canonical_obj(payload, max_depth=max_depth)
