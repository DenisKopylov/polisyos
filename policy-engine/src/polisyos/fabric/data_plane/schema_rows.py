"""Row-local membership checks against the declared connector schema.

No DataFrame dtype inference or coercion participates in admission, so a
neighbouring row or a different sanitization batch cannot change membership.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from numbers import Integral, Real
from typing import TYPE_CHECKING, Any

from polisyos.fabric.connectors.contracts import SchemaType

if TYPE_CHECKING:
    from polisyos.fabric.connectors.contracts import FieldSpec


def _type_member(value: Any, kind: SchemaType) -> bool:
    name = kind.value
    if name.startswith(("int", "uint")):
        if isinstance(value, bool) or not isinstance(value, Integral):
            return False
        bits = int(name.removeprefix("uint").removeprefix("int"))
        low = 0 if name.startswith("uint") else -(2 ** (bits - 1))
        high = 2**bits - 1 if name.startswith("uint") else 2 ** (bits - 1) - 1
        return low <= value <= high
    if name.startswith("float"):
        return not isinstance(value, bool) and isinstance(value, Real)
    if kind == SchemaType.DECIMAL:
        return isinstance(value, Decimal)
    if kind == SchemaType.BOOLEAN:
        return type(value) is bool
    if kind in (SchemaType.STRING, SchemaType.CATEGORY):
        return isinstance(value, str)
    if kind == SchemaType.ARRAY:
        return isinstance(value, list | tuple)
    if kind == SchemaType.JSON:
        return _json_member(value)
    if kind == SchemaType.BINARY:
        return isinstance(value, bytes)
    try:
        if kind == SchemaType.DATE:
            return (isinstance(value, date) and not isinstance(value, datetime)) or (
                isinstance(value, str) and date.fromisoformat(value) is not None
            )
        if kind in (SchemaType.DATETIME, SchemaType.TIMESTAMP_TZ):
            parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
            return kind == SchemaType.DATETIME or parsed.utcoffset() is not None
        if kind == SchemaType.TIME:
            return isinstance(value, time) or (
                isinstance(value, str) and time.fromisoformat(value) is not None
            )
        if kind == SchemaType.DURATION:
            return isinstance(value, timedelta)
    except (TypeError, ValueError, OverflowError):
        return False
    return False


def _json_member(value: Any) -> bool:
    if value is None or isinstance(value, str | bool | int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_json_member(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _json_member(item) for key, item in value.items())
    return False


def field_value_violation(value: Any, field: FieldSpec) -> str | None:
    """Return the actual field violation, without modifying its source value.

    Missing fields and nullability belong to the schema-level caller. Present
    values are checked against FieldSpec's type and declared value restrictions.
    """
    if not _type_member(value, field.data_type):
        return "schema_type_mismatch"
    if field.data_type.is_numeric() or field.data_type == SchemaType.DECIMAL:
        if isinstance(value, Decimal):
            finite = value.is_finite()
        else:
            try:
                finite = math.isfinite(value)
            except OverflowError:
                finite = False
        if not finite:
            return "schema_non_finite"
        if field.bounds:
            low, high = field.bounds
            if (low is not None and value < low) or (high is not None and value > high):
                return "schema_bounds_violation"
    if field.data_type == SchemaType.ARRAY and field.element_type is not None:
        if any(not _type_member(item, field.element_type) for item in value):
            return "schema_element_type_mismatch"
        if any(isinstance(item, Real) and not math.isfinite(item) for item in value):
            return "schema_non_finite"
    if field.pattern and isinstance(value, str) and re.fullmatch(field.pattern, value) is None:
        return "schema_pattern_violation"
    if field.max_length is not None and isinstance(value, str | bytes | list | tuple):
        if len(value) > field.max_length:
            return "schema_length_violation"
    return None
