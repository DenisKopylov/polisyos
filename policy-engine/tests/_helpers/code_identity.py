"""Stable content witness for Python code objects observed by test instruments.

The witness is not semantic equivalence or an executable's provenance. Callers
must separately bind actual code objects, source bytes, interpreter and process.
"""

from __future__ import annotations

import hashlib
import json
import struct
from types import CodeType
from typing import Any

CODE_FINGERPRINT_SCHEME = "policyos-test-code-fields-v1"


def _canonical(value: Any) -> object:
    """Encode supported immutable code fields without marshal reference state."""
    value_type = type(value)
    if value is None:
        return ["none"]
    if value is Ellipsis:
        return ["ellipsis"]
    if value is NotImplemented:
        return ["notimplemented"]
    if value_type is bool:
        return ["bool", value]
    if value_type is int:
        magnitude = abs(value)
        return [
            "int",
            value < 0,
            magnitude.to_bytes((magnitude.bit_length() + 7) // 8, "big").hex(),
        ]
    if value_type is float:
        return ["float64", struct.pack(">d", value).hex()]
    if value_type is complex:
        return ["complex128", struct.pack(">dd", value.real, value.imag).hex()]
    if value_type is str:
        return ["str", value]
    if value_type is bytes:
        return ["bytes", value.hex()]
    if value_type is tuple:
        return ["tuple", [_canonical(item) for item in value]]
    if value_type is frozenset:
        members = [_canonical(item) for item in value]
        members.sort(key=lambda item: json.dumps(item, ensure_ascii=True, separators=(",", ":")))
        return ["frozenset", members]
    if value_type is slice:
        return ["slice", _canonical(value.start), _canonical(value.stop), _canonical(value.step)]
    if value_type is CodeType:
        fields = {}
        for name in sorted(dir(value)):
            if not name.startswith("co_") or name == "co_lnotab":
                continue
            field_value = getattr(value, name)
            if callable(field_value):
                continue
            fields[name] = _canonical(field_value)
        return ["code", fields]
    raise TypeError(
        f"unsupported code field value: {value_type.__module__}.{value_type.__qualname__}"
    )


def code_fingerprint(code: CodeType) -> str:
    """Fingerprint observable non-callable code fields in one interpreter profile.

    Args:
        code: The actual Python code object whose fields are to be recorded.

    Returns:
        A SHA-256 digest of the canonical, type-tagged field representation.

    Raises:
        TypeError: If the argument or a field has an unsupported value type.

    The deprecated ``co_lnotab`` is excluded: ``co_linetable`` is included and
    is its modern input. Runtime specialization, callable accessors, native code,
    external state and module globals are not represented.
    """
    if type(code) is not CodeType:
        raise TypeError("code_fingerprint requires a Python CodeType")
    raw = json.dumps(
        [CODE_FINGERPRINT_SCHEME, _canonical(code)], ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()
