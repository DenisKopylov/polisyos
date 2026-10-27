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
    "bytes_hex": frozenset({"_type", "value"}),
    "float_hex": frozenset({"_type", "value"}),
    "array_digest": frozenset({"_type", "dtype", "shape", "digest"}),
}


@dataclass(frozen=True)
class BytesHexRepresentation:
    """Core-owned immutable hexadecimal bytes representation."""

    value: str

    def __post_init__(self) -> None:
        if (
            type(self.value) is not str
            or len(self.value) % 2
            or any(character not in "0123456789abcdef" for character in self.value)
        ):
            raise CanonicalError("bytes_hex_representation_invalid")


@dataclass(frozen=True)
class FloatHexRepresentation:
    """Core-owned immutable finite IEEE floating representation."""

    value: str

    def __post_init__(self) -> None:
        # A finite Python float's canonical hex form is shorter than this
        # format-derived ceiling; reject long input before float parsing.
        if type(self.value) is not str or len(self.value) > 32:
            raise CanonicalError("float_hex_representation_invalid")
        try:
            decoded = float.fromhex(self.value)
        except (OverflowError, ValueError) as exc:
            raise CanonicalError("float_hex_representation_invalid") from exc
        if not math.isfinite(decoded) or decoded.hex() != self.value:
            raise CanonicalError("float_hex_representation_not_normalized")


@dataclass(frozen=True)
class ArrayDigestRepresentation:
    """Core-owned opaque array descriptor; it does not attest array contents."""

    dtype: str
    shape: tuple[int, ...]
    digest: str

    def __post_init__(self) -> None:
        if (
            type(self.dtype) is not str
            or not self.dtype
            or type(self.shape) is not tuple
            or any(type(item) is not int or item < 0 for item in self.shape)
            or type(self.digest) is not str
            or len(self.digest) != 71
            or not self.digest.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in self.digest[7:])
        ):
            raise CanonicalError("array_digest_representation_invalid")
        try:
            bytes.fromhex(self.digest[7:])
        except ValueError as exc:
            raise CanonicalError("array_digest_representation_invalid") from exc


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


@dataclass(frozen=True)
class CanonicalResourceLimits:
    """Owner-supplied physical limits for one bounded codec call."""

    policy_id: str
    max_wire_bytes: int
    max_wire_depth: int
    max_elements: int

    def __post_init__(self) -> None:
        if (
            type(self.policy_id) is not str
            or not self.policy_id
            or type(self.max_wire_bytes) is not int
            or self.max_wire_bytes <= 0
            or type(self.max_wire_depth) is not int
            or self.max_wire_depth < 0
            or type(self.max_elements) is not int
            or self.max_elements <= 0
        ):
            raise CanonicalError("canonical_resource_limits_invalid")


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


def _require_carrier_profile(
    kind: str,
    spec: CanonSpec,
    canonical_types: Collection[str],
    violation_type: type[ValueError],
) -> None:
    """Admit a new representation only under its selected .3 tag law."""
    if not _uses_v3_grammar(spec) or kind not in canonical_types:
        _raise_violation(violation_type, "canonical_carrier_profile_unsupported")


def _canonicalize_obj(
    obj: object,
    spec: CanonSpec,
    depth: int = 0,
    *,
    violation_type: type[ValueError],
    canonical_types: Collection[str],
) -> _CanonicalValue:
    _check_depth(depth, spec.max_depth, violation_type)

    if type(obj) is BytesHexRepresentation:
        _require_carrier_profile("bytes_hex", spec, canonical_types, violation_type)
        return {"_type": "bytes_hex", "value": obj.value}
    if type(obj) is FloatHexRepresentation:
        _require_carrier_profile("float_hex", spec, canonical_types, violation_type)
        if spec.forbid_floats:
            _raise_violation(violation_type, "float forbidden in canonical JSON")
        return {"_type": "float_hex", "value": obj.value}
    if type(obj) is ArrayDigestRepresentation:
        _require_carrier_profile("array_digest", spec, canonical_types, violation_type)
        return {
            "_type": "array_digest",
            "dtype": obj.dtype,
            "shape": list(obj.shape),
            "digest": obj.digest,
        }

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


def to_bounded_canonical_bytes(
    obj: object,
    spec: CanonSpec,
    limits: CanonicalResourceLimits,
    *,
    violation_type: type[ValueError] = CanonicalError,
    canonical_types: Collection[str] = _ALL_CANONICAL_TYPES,
) -> bytes:
    """Snapshot and encode exact callback-free values under one wire vector.

    Bytes, lexical JSON elements and container depth are charged incrementally
    before input-sized output projection or materialization. The owned snapshot
    makes the counted value the value subsequently encoded. Mutable containers
    changed during iteration are refused when Python detects that mutation.
    Supported inputs are exact built-in JSON scalars, bytes, lists, tuples,
    dictionaries with exact string keys, and the three representation carriers.
    Other owner projections require a separately admitted bounded contract.
    """
    spec = _admit_canon_spec(spec, CanonSpec, violation_type=violation_type)
    if type(limits) is not CanonicalResourceLimits:
        _raise_violation(violation_type, "canonical_resource_policy_missing")
    policy_id = limits.policy_id
    max_bytes = limits.max_wire_bytes
    max_depth = limits.max_wire_depth
    max_elements = limits.max_elements
    if (
        type(policy_id) is not str
        or not policy_id
        or type(max_bytes) is not int
        or max_bytes <= 0
        or type(max_depth) is not int
        or max_depth < 0
        or type(max_elements) is not int
        or max_elements <= 0
    ):
        _raise_violation(violation_type, "canonical_resource_limits_invalid")
    if (
        type(canonical_types) is not frozenset
        or len(canonical_types) > len(_ALL_CANONICAL_TYPES)
        or any(
            type(kind) is not str or kind not in _ALL_CANONICAL_TYPES for kind in canonical_types
        )
    ):
        _raise_violation(violation_type, "canonical_bounded_type_policy_invalid")

    item_separator, key_separator = spec.separators
    byte_count = 0
    element_count = 0
    active: set[int] = set()

    def take_bytes(amount: int) -> None:
        nonlocal byte_count
        if amount > max_bytes - byte_count:
            _raise_violation(violation_type, "canonical_wire_bytes_exceeded")
        byte_count += amount

    def take_element() -> None:
        nonlocal element_count
        if element_count >= max_elements:
            _raise_violation(violation_type, "canonical_wire_elements_exceeded")
        element_count += 1

    def require_minimum(depth: int, nodes: int, byte_lower_bound: int) -> None:
        if depth > max_depth:
            _raise_violation(violation_type, "canonical_wire_depth_exceeded")
        if nodes > max_elements - element_count:
            _raise_violation(violation_type, "canonical_wire_elements_exceeded")
        if byte_lower_bound > max_bytes - byte_count:
            _raise_violation(violation_type, "canonical_wire_bytes_exceeded")

    def utf8_width(character: str) -> int:
        point = ord(character)
        if point < 0x80:
            return 1
        if point < 0x800:
            return 2
        if 0xD800 <= point <= 0xDFFF:
            _raise_violation(violation_type, "canonical_bounded_unicode_invalid")
        return 3 if point < 0x10000 else 4

    def separator(value: str) -> None:
        # Separators are literal JSON output, not JSON string values. Their
        # character count is a cheap lower bound before the bounded UTF-8 walk.
        if len(value) > max_bytes - byte_count:
            _raise_violation(violation_type, "canonical_wire_bytes_exceeded")
        for character in value:
            take_bytes(utf8_width(character))

    def string(value: str) -> None:
        take_element()
        # Every code point needs at least one byte in JSON. This O(1) guard
        # refuses a huge string before scanning it or constructing escaped text.
        if len(value) + 2 > max_bytes - byte_count:
            _raise_violation(violation_type, "canonical_wire_bytes_exceeded")
        take_bytes(2)
        for character in value:
            point = ord(character)
            if character in '"\\\b\f\n\r\t':
                width = 2
            elif point < 0x20:
                width = 6
            elif spec.ensure_ascii and point >= 0x7F:
                width = 6 if point <= 0xFFFF else 12
            else:
                width = utf8_width(character)
            take_bytes(width)

    def integer(value: int) -> None:
        take_element()
        available = max_bytes - byte_count
        negative = value < 0
        digits = available - int(negative)
        if digits < 1:
            _raise_violation(violation_type, "canonical_wire_bytes_exceeded")
        bits = value.bit_length()
        # An upper bound avoids allocating decimal text until it is known to
        # fit; the rare ambiguous boundary is decided by a budget-sized integer.
        upper_digits = max(1, (bits * 30103) // 100000 + 1)
        if upper_digits > digits:
            if bits > digits * 4:
                _raise_violation(violation_type, "canonical_wire_bytes_exceeded")
            threshold = 10**digits
            if value >= threshold or value <= -threshold:
                _raise_violation(violation_type, "canonical_wire_bytes_exceeded")
        try:
            size = len(str(value))
        except ValueError as exc:
            raise violation_type("canonical_bounded_integer_invalid") from exc
        take_bytes(size)

    def array_start(depth: int, count: int) -> None:
        lower = 2 + count + max(0, count - 1) * len(item_separator)
        require_minimum(depth, 1 + count, lower)
        take_element()
        take_bytes(2)

    def object_start(depth: int, count: int) -> None:
        lower = 2 + count * (3 + len(key_separator))
        lower += max(0, count - 1) * len(item_separator)
        require_minimum(depth, 1 + 2 * count, lower)
        take_element()
        take_bytes(2)

    def object_member(name: str, index: int) -> None:
        if index:
            separator(item_separator)
        string(name)
        separator(key_separator)

    def shape(value: tuple[int, ...], depth: int) -> None:
        array_start(depth, len(value))
        for index, item in enumerate(value):
            if index:
                separator(item_separator)
            if type(item) is not int or item < 0:
                _raise_violation(violation_type, "canonical_bounded_carrier_invalid")
            integer(item)

    def native(
        kind: str,
        fields: tuple[tuple[str, object], ...],
        depth: int,
        *,
        base64_length: int | None = None,
    ) -> None:
        if kind not in canonical_types:
            _raise_violation(violation_type, "canonical_bounded_type_policy_invalid")
        object_start(depth, len(fields) + 1)
        object_member("_type", 0)
        string(kind)
        for index, (name, value) in enumerate(fields, 1):
            object_member(name, index)
            if name == "data" and base64_length is not None:
                take_element()
                take_bytes(base64_length + 2)
            elif type(value) is str:
                string(value)
            elif type(value) is tuple:
                shape(value, depth + 1)
            else:
                _raise_violation(violation_type, "canonical_bounded_carrier_invalid")

    def clone(value: object, logical_depth: int, wire_depth: int) -> object:
        _check_depth(logical_depth, spec.max_depth, violation_type)
        value_type = type(value)
        if value is None:
            take_element()
            take_bytes(4)
            return None
        if value_type is bool:
            take_element()
            take_bytes(4 if value else 5)
            return value
        if value_type is int:
            integer(value)
            return value
        if value_type is str:
            string(value)
            return value
        if value_type is float:
            if spec.forbid_nan_inf and not math.isfinite(value):
                _raise_violation(violation_type, "NaN/Inf forbidden in canonical JSON")
            if spec.forbid_floats:
                _raise_violation(violation_type, "float forbidden in canonical JSON")
            native("float", (("repr", _canonical_float_repr(value)),), wire_depth)
            return value
        if value_type is bytes:
            data_length = 4 * ((len(value) + 2) // 3)
            native(
                "bytes",
                (("encoding", "base64"), ("data", "")),
                wire_depth,
                base64_length=data_length,
            )
            return value
        if value_type in {
            BytesHexRepresentation,
            FloatHexRepresentation,
            ArrayDigestRepresentation,
        } and not _uses_v3_grammar(spec):
            _raise_violation(violation_type, "canonical_carrier_profile_unsupported")
        if value_type is BytesHexRepresentation:
            text = value.value
            if type(text) is not str:
                _raise_violation(violation_type, "canonical_bounded_carrier_invalid")
            native("bytes_hex", (("value", text),), wire_depth)
            try:
                return BytesHexRepresentation(text)
            except ValueError as exc:
                raise violation_type("canonical_bounded_carrier_invalid") from exc
        if value_type is FloatHexRepresentation:
            text = value.value
            if type(text) is not str or spec.forbid_floats:
                _raise_violation(violation_type, "canonical_bounded_carrier_invalid")
            native("float_hex", (("value", text),), wire_depth)
            try:
                return FloatHexRepresentation(text)
            except ValueError as exc:
                raise violation_type("canonical_bounded_carrier_invalid") from exc
        if value_type is ArrayDigestRepresentation:
            dtype, dimensions, digest = value.dtype, value.shape, value.digest
            if type(dtype) is not str or type(dimensions) is not tuple or type(digest) is not str:
                _raise_violation(violation_type, "canonical_bounded_carrier_invalid")
            native(
                "array_digest",
                (("dtype", dtype), ("shape", dimensions), ("digest", digest)),
                wire_depth,
            )
            try:
                return ArrayDigestRepresentation(dtype, dimensions, digest)
            except ValueError as exc:
                raise violation_type("canonical_bounded_carrier_invalid") from exc
        if value_type not in {list, tuple, dict}:
            _raise_violation(violation_type, "canonical_bounded_projection_required")

        identity = id(value)
        if identity in active:
            _raise_violation(violation_type, "canonical_bounded_cycle")
        active.add(identity)
        try:
            count = len(value)
            if value_type in {list, tuple}:
                array_start(wire_depth, count)
                result: list[object] = []
                for index, item in enumerate(value):
                    if index:
                        separator(item_separator)
                    result.append(clone(item, logical_depth + 1, wire_depth + 1))
                return result

            # Establish root depth and a lower bound before key scanning,
            # pair-list construction, sorting, or wrapper projection.
            lower = 2 + count * (3 + len(key_separator))
            lower += max(0, count - 1) * len(item_separator)
            require_minimum(wire_depth, 1 + 2 * count, lower)
            escaped = False
            for key in value:
                if type(key) is not str:
                    _raise_violation(violation_type, "canonical_bounded_key_invalid")
                if key == "_type" and _uses_v3_grammar(spec):
                    escaped = True
            if escaped:
                require_minimum(wire_depth + 2, 5 + 3 * count, lower)
                object_start(wire_depth, 2)
                object_member("_type", 0)
                string("mapping")
                object_member("entries", 1)
                array_start(wire_depth + 1, count)
            else:
                object_start(wire_depth, count)
            result_map: dict[str, object] = {}
            for index, (key, item) in enumerate(value.items()):
                if type(key) is not str:
                    _raise_violation(violation_type, "canonical_bounded_key_invalid")
                if escaped:
                    if index:
                        separator(item_separator)
                    array_start(wire_depth + 2, 2)
                    string(key)
                    separator(item_separator)
                    child_depth = wire_depth + 3
                else:
                    object_member(key, index)
                    child_depth = wire_depth + 1
                logical_step = 1 if _uses_v3_grammar(spec) else 2
                result_map[key] = clone(item, logical_depth + logical_step, child_depth)
            if (_uses_v3_grammar(spec) and "_type" in result_map) != escaped:
                _raise_violation(violation_type, "canonical_bounded_input_changed")
            return result_map
        finally:
            active.remove(identity)

    try:
        snapshot = clone(obj, 0, 1)
        payload = to_canonical_bytes(
            snapshot, spec, violation_type=violation_type, canonical_types=canonical_types
        )
    except RecursionError as exc:
        raise violation_type("canonical_bounded_recursion_capacity") from exc
    except RuntimeError as exc:
        raise violation_type("canonical_bounded_input_changed") from exc
    if len(payload) != byte_count:
        _raise_violation(violation_type, "canonical_wire_accounting_mismatch")
    return payload


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
                expected_fields = _V3_NATIVE_FIELDS.get(kind)
                if expected_fields is None:
                    _raise_violation(violation_type, "canonical_v3_descriptor_unsupported")
                if set(obj) != expected_fields:
                    _raise_violation(violation_type, "malformed_canonical_native_envelope")
                if kind != "array_digest" and any(
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
                    if kind == "bytes_hex":
                        return BytesHexRepresentation(obj["value"])
                    if kind == "float_hex":
                        return FloatHexRepresentation(obj["value"])
                    if kind == "array_digest":
                        shape = obj["shape"]
                        if type(shape) is not list:
                            _raise_violation(violation_type, "malformed_canonical_native_envelope")
                        return ArrayDigestRepresentation(
                            dtype=obj["dtype"], shape=tuple(shape), digest=obj["digest"]
                        )
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
    "ArrayDigestRepresentation",
    "BytesHexRepresentation",
    "CanonSpec",
    "CanonicalError",
    "CanonicalResourceLimits",
    "FloatHexRepresentation",
    "from_canonical_bytes",
    "from_canonical_obj",
    "to_bounded_canonical_bytes",
    "to_canonical_bytes",
]
