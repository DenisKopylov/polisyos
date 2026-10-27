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

_RAW_MAPPING_TYPE = "mapping"
_RAW_MAPPING_FIELDS = frozenset({"_type", "entries"})
_V3_NATIVE_FIELDS = {
    "datetime": frozenset({"_type", "iso_utc"}),
    "date": frozenset({"_type", "iso"}),
    "decimal": frozenset({"_type", "value"}),
    "bytes": frozenset({"_type", "encoding", "data"}),
    "float": frozenset({"_type", "repr"}),
}


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


def _admit_canon_spec[CanonSpecT: CanonSpec](
    spec: object | None,
    spec_type: type[CanonSpecT],
    *,
    violation_type: type[ValueError],
    artifact_writer: bool = False,
) -> CanonSpecT:
    """Freeze primitive codec fields before any projection or store callbacks.

    A spec's base dataclass storage is read via its native descriptor, bypassing
    subclass ``__getattribute__`` and descriptors.  Arbitrary duck objects and
    non-primitive field carriers are refused; they are not a codec contract.
    Raw byte import remains separate and can retain an unknown declaration.
    """
    if spec is None:
        selected = spec_type()
    else:
        actual_mro = type.__getattribute__(type(spec), "__mro__")
        if not any(base is CanonSpec for base in actual_mro):
            _raise_violation(violation_type, "canonical_spec_invalid")
        try:
            descriptor = CanonSpec.__dict__["__dict__"]
            storage = descriptor.__get__(spec, type(spec))
        except (AttributeError, TypeError) as exc:
            raise violation_type("canonical_spec_invalid") from exc
        if type(storage) is not dict:
            _raise_violation(violation_type, "canonical_spec_invalid")
        try:
            values = {field.name: storage[field.name] for field in dataclasses.fields(CanonSpec)}
        except KeyError as exc:
            raise violation_type("canonical_spec_invalid") from exc
        if (
            type(values["name"]) is not str
            or type(values["version"]) is not str
            or any(
                type(values[name]) is not bool
                for name in (
                    "forbid_floats",
                    "forbid_nan_inf",
                    "exclude_none",
                    "sort_keys",
                    "ensure_ascii",
                )
            )
            or type(values["max_depth"]) is not int
            or values["max_depth"] < 0
            or type(values["separators"]) is not tuple
            or len(values["separators"]) != 2
            or any(type(value) is not str for value in values["separators"])
        ):
            _raise_violation(violation_type, "canonical_spec_invalid")
        selected = spec_type(**values)
    if selected.name == "polisyos.canon.json":
        if artifact_writer and selected.version != "0.2.0":
            _raise_violation(violation_type, "canonical_writer_profile_unavailable")
        if selected.version not in ("0.2.0", "0.3.0"):
            _raise_violation(violation_type, "unsupported_canonical_codec_version")
    return selected


def _uses_v3_grammar(spec: CanonSpec) -> bool:
    """Select the grammar only for its exact declared codec name and version."""
    return spec.name == "polisyos.canon.json" and spec.version == "0.3.0"


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


def _escape_projected_mapping(
    value: dict[str, _CanonicalValue], spec: CanonSpec
) -> dict[str, _CanonicalValue]:
    """Escape ordinary projected mappings after their members are canonicalized.

    Native typed envelopes are emitted separately and never pass this policy.
    """
    if _uses_v3_grammar(spec) and "_type" in value:
        return {
            "_type": _RAW_MAPPING_TYPE,
            "entries": [[key, value[key]] for key in sorted(value)],
        }
    return value


def _canonicalize_mapping(
    obj: Mapping[object, object],
    spec: CanonSpec,
    depth: int,
    *,
    violation_type: type[ValueError],
    canonical_types: Collection[str],
) -> dict[str, _CanonicalValue]:
    escape_raw_mapping = _uses_v3_grammar(spec) and "_type" in obj
    if "_type" in obj and not escape_raw_mapping:
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
    return _escape_projected_mapping(out, spec)


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
    return _escape_projected_mapping(out, spec)


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
            depth if _uses_v3_grammar(spec) else depth + 1,
            violation_type=violation_type,
            canonical_types=canonical_types,
        )

    if dataclasses.is_dataclass(obj):
        return _canonicalize_dataclass(
            obj,
            spec,
            depth if _uses_v3_grammar(spec) else depth + 1,
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
            depth if _uses_v3_grammar(spec) else depth + 1,
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
    spec = _admit_canon_spec(spec, CanonSpec, violation_type=violation_type)
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
    version: str = "0.2.0",
) -> object:
    """Decode canonical objects under an explicit typed-tag profile."""
    if version not in ("0.2.0", "0.3.0"):
        _raise_violation(violation_type, "unsupported_canonical_codec_version")
    _check_depth(_depth, max_depth, violation_type)
    if isinstance(obj, Mapping):
        if "_type" in obj:
            kind = obj.get("_type")
            if version == "0.3.0" and kind == _RAW_MAPPING_TYPE:
                if set(obj) != _RAW_MAPPING_FIELDS or not isinstance(obj.get("entries"), list):
                    _raise_violation(violation_type, "Malformed canonical mapping wrapper")
                reconstructed: dict[str, object] = {}
                previous: str | None = None
                for pair in obj["entries"]:
                    if not isinstance(pair, list) or len(pair) != 2 or type(pair[0]) is not str:
                        _raise_violation(violation_type, "Malformed canonical mapping entry")
                    key = pair[0]
                    if previous is not None and key <= previous:
                        _raise_violation(
                            violation_type,
                            "Canonical mapping entries not strictly sorted",
                        )
                    previous = key
                    reconstructed[key] = from_canonical_obj(
                        pair[1],
                        max_depth=max_depth,
                        _depth=_depth + 1,
                        violation_type=violation_type,
                        canonical_types=canonical_types,
                        version=version,
                    )
                if "_type" not in reconstructed:
                    _raise_violation(violation_type, "Canonical mapping wrapper lacks _type")
                # This is ordinary user data.  Deliberately do not redispatch its root tag.
                return reconstructed
            if not isinstance(kind, str) or kind not in canonical_types:
                _raise_violation(violation_type, f"Unknown canonical _type: {kind!r}")
            if version == "0.3.0":
                # Hex and array descriptor carriers need their own owner types and
                # are not part of this bounded codec slice.  Do not turn those
                # envelopes into ordinary primitives or an unverified array dict.
                expected_fields = _V3_NATIVE_FIELDS.get(kind)
                if expected_fields is None:
                    _raise_violation(violation_type, "canonical_v3_descriptor_unsupported")
                if set(obj) != expected_fields or any(
                    type(obj[field]) is not str for field in expected_fields
                ):
                    _raise_violation(violation_type, "malformed_canonical_native_envelope")
                if kind == "bytes" and obj["encoding"] != "base64":
                    _raise_violation(violation_type, "malformed_canonical_native_envelope")
                try:
                    if kind == "datetime":
                        return _parse_datetime(obj["iso_utc"])
                    if kind == "date":
                        return date.fromisoformat(obj["iso"])
                    if kind == "decimal":
                        return Decimal(obj["value"])
                    if kind == "bytes":
                        return base64.b64decode(obj["data"].encode("ascii"), validate=True)
                    if kind == "float":
                        return float(obj["repr"])
                except (ArithmeticError, TypeError, ValueError) as exc:
                    raise violation_type("malformed_canonical_native_envelope") from exc
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
                version=version,
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
                version=version,
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
    version: str = "0.2.0",
) -> object:
    """Decode canonical bytes under an explicit typed-tag profile."""
    if version not in ("0.2.0", "0.3.0"):
        _raise_violation(violation_type, "unsupported_canonical_codec_version")
    if version == "0.3.0":
        try:
            payload = json.loads(
                data,
                object_pairs_hook=_reject_duplicate_names,
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, ValueError, TypeError) as exc:
            raise violation_type(str(exc)) from exc
    else:
        # Keep the exact legacy parser behaviour for unqualified .2 callers.
        payload = json.loads(data)
    return from_canonical_obj(
        payload,
        max_depth=max_depth,
        violation_type=violation_type,
        canonical_types=canonical_types,
        version=version,
    )


def _reject_duplicate_names(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object while refusing ambiguous duplicate member names."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    """Reject non-JSON numeric constants before constructing a .3 value."""
    raise ValueError(f"invalid JSON numeric constant: {value}")


__all__ = [
    "CanonSpec",
    "CanonicalError",
    "from_canonical_bytes",
    "from_canonical_obj",
    "to_canonical_bytes",
]
