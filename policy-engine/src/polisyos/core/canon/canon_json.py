"""Canonical JSON normalization for hashing, persistence, and cross-runtime comparisons."""
from __future__ import annotations

import base64
import dataclasses
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from pydantic import BaseModel


class CanonViolation(ValueError):
    """Canon violation public type."""
    pass


@dataclass(frozen=True)
class CanonSpec:
    """Controls how arbitrary Python objects are normalized into canonical JSON bytes."""
    name: str = "polisyos.canon.json"
    version: str = "0.1.0"

    forbid_floats: bool = True
    forbid_nan_inf: bool = True

    sort_keys: bool = True
    separators: tuple[str, str] = (",", ":")
    ensure_ascii: bool = False


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonicalize_obj(obj: Any, spec: CanonSpec) -> Any:
    if isinstance(obj, BaseModel):
        return _canonicalize_obj(
            obj.model_dump(mode="python", by_alias=True, exclude_none=True),
            spec,
        )

    if dataclasses.is_dataclass(obj):
        return _canonicalize_obj(dataclasses.asdict(obj), spec)

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
        return {"_type": "float", "repr": format(obj, ".17g")}

    if isinstance(obj, str):
        return obj

    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise CanonViolation(f"JSON keys must be str, got: {type(k)}")
            out[k] = _canonicalize_obj(v, spec)
        return out

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray, memoryview)):
        return [_canonicalize_obj(x, spec) for x in obj]

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


def from_canonical_obj(obj: Any) -> Any:
    """Create from canonical obj."""
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
        return {k: from_canonical_obj(v) for k, v in obj.items()}

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray, memoryview)):
        return [from_canonical_obj(item) for item in obj]

    return obj


def from_canonical_bytes(data: bytes) -> Any:
    """Create from canonical bytes."""
    payload = json.loads(data)
    return from_canonical_obj(payload)
