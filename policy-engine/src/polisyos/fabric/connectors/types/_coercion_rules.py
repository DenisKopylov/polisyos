"""Individual type coercion functions.

Each function converts an arbitrary value into a specific target type,
respecting the supplied CoercionPolicy.  They return a CoercionResult
rather than raising, so callers can decide how to surface failures.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from ._coercion_policies import CoercionPolicy, CoercionResult

__all__ = [
    "coerce_to_int",
    "coerce_to_float",
    "coerce_to_decimal",
    "coerce_to_boolean",
    "coerce_to_string",
    "coerce_to_date",
    "coerce_to_datetime",
]


# =============================================================================
# Numeric helpers
# =============================================================================


def _get_int_range(bits: int, signed: bool) -> tuple[int, int]:
    """Get the valid range for an integer type."""
    if signed:
        return (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
    return (0, 2 ** bits - 1)


def _is_exact_integer(value: float) -> bool:
    """Check if a float value represents an exact integer."""
    return math.isfinite(value) and value == math.floor(value)


def _float_to_int_safe(
    value: float, target_bits: int, target_signed: bool
) -> int | None:
    """Safely convert a float to an integer if it represents an exact integer.

    Returns None if conversion would lose precision or overflow.
    """
    if not math.isfinite(value):
        return None

    if not _is_exact_integer(value):
        return None

    int_value = int(value)
    min_val, max_val = _get_int_range(target_bits, target_signed)

    if int_value < min_val or int_value > max_val:
        return None

    return int_value


def _int_fits_in_float(value: int, float_bits: int) -> bool:
    """Check if an integer can be exactly represented in a float.

    float32 has 24 bits of mantissa (23 explicit + 1 implicit)
    float64 has 53 bits of mantissa (52 explicit + 1 implicit)
    """
    mantissa_bits = {16: 11, 32: 24, 64: 53}
    max_exact = 2 ** mantissa_bits.get(float_bits, 53)
    return abs(value) <= max_exact


# =============================================================================
# Integer coercion
# =============================================================================


def coerce_to_int(
    value: Any,
    target_bits: int,
    signed: bool,
    policy: CoercionPolicy,
) -> CoercionResult:
    """Coerce a value to an integer type."""
    target_type = f"{'int' if signed else 'uint'}{target_bits}"
    min_val, max_val = _get_int_range(target_bits, signed)
    source_type = type(value).__name__

    # From None
    if value is None:
        return CoercionResult.fail(source_type, target_type, "cannot convert None")

    # From bool
    if isinstance(value, bool):
        int_val = 1 if value else 0
        return CoercionResult.ok(int_val, "bool", target_type)

    # From int
    if isinstance(value, int):
        if min_val <= value <= max_val:
            return CoercionResult.ok(value, "int", target_type)
        return CoercionResult.fail(
            "int", target_type,
            f"value {value} out of range [{min_val}, {max_val}]"
        )

    # From float
    if isinstance(value, float):
        safe_int = _float_to_int_safe(value, target_bits, signed)
        if safe_int is not None:
            return CoercionResult.ok(safe_int, "float", target_type)

        if policy == CoercionPolicy.STRICT:
            return CoercionResult.fail(
                "float", target_type,
                f"value {value} is not an exact integer or out of range"
            )

        # Lenient/Warn: truncate
        if math.isfinite(value):
            truncated = int(value)
            if min_val <= truncated <= max_val:
                return CoercionResult.ok(
                    truncated, "float", target_type,
                    precision_loss=True,
                    warnings=[f"truncated {value} to {truncated}"],
                )

        return CoercionResult.fail(
            "float", target_type, f"value {value} cannot be converted"
        )

    # From Decimal
    if isinstance(value, Decimal):
        try:
            # Check if it's an integer
            if value == value.to_integral_value():
                int_val = int(value)
                if min_val <= int_val <= max_val:
                    return CoercionResult.ok(int_val, "Decimal", target_type)
                return CoercionResult.fail(
                    "Decimal", target_type,
                    f"value {value} out of range"
                )

            if policy == CoercionPolicy.STRICT:
                return CoercionResult.fail(
                    "Decimal", target_type,
                    f"value {value} is not an exact integer"
                )

            # Lenient/Warn: round
            rounded = int(value.to_integral_value(rounding=ROUND_HALF_UP))
            if min_val <= rounded <= max_val:
                return CoercionResult.ok(
                    rounded, "Decimal", target_type,
                    precision_loss=True,
                    warnings=[f"rounded {value} to {rounded}"],
                )

            return CoercionResult.fail(
                "Decimal", target_type, f"value {value} out of range after rounding"
            )
        except (InvalidOperation, OverflowError) as exc:
            return CoercionResult.fail("Decimal", target_type, str(exc))

    # From string
    if isinstance(value, str):
        value = value.strip()

        # Try integer parsing
        try:
            int_val = int(value)
            if min_val <= int_val <= max_val:
                return CoercionResult.ok(int_val, "string", target_type)
            return CoercionResult.fail(
                "string", target_type,
                f"value {int_val} out of range"
            )
        except ValueError:
            pass

        # Try float parsing (for "1.0" -> 1)
        try:
            float_val = float(value)
            if _is_exact_integer(float_val):
                int_val = int(float_val)
                if min_val <= int_val <= max_val:
                    return CoercionResult.ok(int_val, "string", target_type)
        except ValueError:
            pass

        return CoercionResult.fail(
            "string", target_type, f"cannot parse '{value}' as integer"
        )

    return CoercionResult.fail(
        source_type, target_type, f"unsupported source type {source_type}"
    )


# =============================================================================
# Float coercion
# =============================================================================


def coerce_to_float(
    value: Any,
    target_bits: int,
    policy: CoercionPolicy,
) -> CoercionResult:
    """Coerce a value to a float type."""
    target_type = f"float{target_bits}"
    source_type = type(value).__name__

    if value is None:
        return CoercionResult.fail(source_type, target_type, "cannot convert None")

    # From bool
    if isinstance(value, bool):
        float_val = 1.0 if value else 0.0
        return CoercionResult.ok(float_val, "bool", target_type)

    # From int
    if isinstance(value, int):
        # Check for precision loss
        if not _int_fits_in_float(value, target_bits):
            if policy == CoercionPolicy.STRICT:
                return CoercionResult.fail(
                    "int", target_type,
                    f"integer {value} may lose precision in {target_type}"
                )
            return CoercionResult.ok(
                float(value), "int", target_type,
                precision_loss=True,
                warnings=[f"large integer {value} may lose precision"],
            )
        return CoercionResult.ok(float(value), "int", target_type)

    # From float
    if isinstance(value, float):
        # Check for narrowing
        if target_bits < 64 and math.isfinite(value):
            # For float64 -> float32, check if value fits
            if target_bits == 32:
                import struct
                try:
                    # Round-trip through float32
                    f32 = struct.unpack('f', struct.pack('f', value))[0]
                    if f32 != value and policy == CoercionPolicy.STRICT:
                        return CoercionResult.fail(
                            "float64", target_type,
                            f"value {value} loses precision in float32"
                        )
                    if f32 != value:
                        return CoercionResult.ok(
                            f32, "float64", target_type,
                            precision_loss=True,
                            warnings=[f"precision loss: {value} -> {f32}"],
                        )
                except (struct.error, OverflowError):
                    return CoercionResult.fail(
                        "float64", target_type,
                        f"value {value} overflows float32"
                    )
        return CoercionResult.ok(value, "float", target_type)

    # From Decimal
    if isinstance(value, Decimal):
        try:
            float_val = float(value)
            # Check round-trip
            if Decimal(str(float_val)) != value:
                if policy == CoercionPolicy.STRICT:
                    return CoercionResult.fail(
                        "Decimal", target_type,
                        f"Decimal {value} loses precision as float"
                    )
                return CoercionResult.ok(
                    float_val, "Decimal", target_type,
                    precision_loss=True,
                    warnings=["precision loss converting Decimal to float"],
                )
            return CoercionResult.ok(float_val, "Decimal", target_type)
        except (InvalidOperation, OverflowError) as exc:
            return CoercionResult.fail("Decimal", target_type, str(exc))

    # From string
    if isinstance(value, str):
        value = value.strip()
        try:
            float_val = float(value)
            return CoercionResult.ok(float_val, "string", target_type)
        except ValueError:
            return CoercionResult.fail(
                "string", target_type, f"cannot parse '{value}' as float"
            )

    return CoercionResult.fail(
        source_type, target_type, f"unsupported source type {source_type}"
    )


# =============================================================================
# Decimal coercion
# =============================================================================


def coerce_to_decimal(
    value: Any,
    policy: CoercionPolicy,
) -> CoercionResult:
    """Coerce a value to Decimal type."""
    target_type = "decimal"
    source_type = type(value).__name__

    if value is None:
        return CoercionResult.fail(source_type, target_type, "cannot convert None")

    # From bool
    if isinstance(value, bool):
        return CoercionResult.ok(Decimal(1 if value else 0), "bool", target_type)

    # From int
    if isinstance(value, int):
        return CoercionResult.ok(Decimal(value), "int", target_type)

    # From float
    if isinstance(value, float):
        if not math.isfinite(value):
            return CoercionResult.fail(
                "float", target_type, f"cannot convert {value} to Decimal"
            )
        # Use string conversion for better precision
        return CoercionResult.ok(Decimal(str(value)), "float", target_type)

    # From Decimal (identity)
    if isinstance(value, Decimal):
        return CoercionResult.ok(value, "Decimal", target_type)

    # From string
    if isinstance(value, str):
        value = value.strip()
        # Remove currency symbols and thousand separators
        cleaned = re.sub(r'[,$\u20ac\u00a3\u00a5\u20b4\s]', '', value)
        try:
            return CoercionResult.ok(Decimal(cleaned), "string", target_type)
        except InvalidOperation:
            return CoercionResult.fail(
                "string", target_type, f"cannot parse '{value}' as Decimal"
            )

    return CoercionResult.fail(
        source_type, target_type, f"unsupported source type {source_type}"
    )


# =============================================================================
# Boolean coercion
# =============================================================================


def coerce_to_boolean(value: Any, policy: CoercionPolicy) -> CoercionResult:
    """Coerce a value to boolean type."""
    source_type = type(value).__name__

    if value is None:
        return CoercionResult.fail(source_type, "boolean", "cannot convert None")

    # From bool
    if isinstance(value, bool):
        return CoercionResult.ok(value, "bool", "boolean")

    # From int
    if isinstance(value, int):
        if value in (0, 1):
            return CoercionResult.ok(bool(value), "int", "boolean")
        if policy == CoercionPolicy.STRICT:
            return CoercionResult.fail(
                "int", "boolean", f"only 0 and 1 allowed, got {value}"
            )
        return CoercionResult.ok(bool(value), "int", "boolean")

    # From float
    if isinstance(value, float):
        if value in (0.0, 1.0):
            return CoercionResult.ok(bool(value), "float", "boolean")
        if policy == CoercionPolicy.STRICT:
            return CoercionResult.fail(
                "float", "boolean", f"only 0.0 and 1.0 allowed, got {value}"
            )
        return CoercionResult.ok(bool(value), "float", "boolean")

    # From string
    if isinstance(value, str):
        value_lower = value.strip().lower()
        true_values = {"true", "yes", "1", "on", "t", "y"}
        false_values = {"false", "no", "0", "off", "f", "n", ""}

        if value_lower in true_values:
            return CoercionResult.ok(True, "string", "boolean")
        if value_lower in false_values:
            return CoercionResult.ok(False, "string", "boolean")

        return CoercionResult.fail(
            "string", "boolean", f"cannot interpret '{value}' as boolean"
        )

    return CoercionResult.fail(
        source_type, "boolean", f"unsupported source type {source_type}"
    )


# =============================================================================
# String coercion
# =============================================================================


def coerce_to_string(value: Any, policy: CoercionPolicy) -> CoercionResult:
    """Coerce a value to string type."""
    source_type = type(value).__name__

    if value is None:
        return CoercionResult.fail(source_type, "string", "cannot convert None")

    # Most types can be converted to string
    return CoercionResult.ok(str(value), source_type, "string")


# =============================================================================
# Date coercion
# =============================================================================


def coerce_to_date(value: Any, policy: CoercionPolicy) -> CoercionResult:
    """Coerce a value to date type."""
    source_type = type(value).__name__

    if value is None:
        return CoercionResult.fail(source_type, "date", "cannot convert None")

    # From date (identity)
    if isinstance(value, date) and not isinstance(value, datetime):
        return CoercionResult.ok(value, "date", "date")

    # From datetime (truncate time)
    if isinstance(value, datetime):
        result = value.date()
        if value.hour or value.minute or value.second or value.microsecond:
            if policy == CoercionPolicy.STRICT:
                return CoercionResult.fail(
                    "datetime", "date", "datetime has non-zero time component"
                )
            return CoercionResult.ok(
                result, "datetime", "date",
                precision_loss=True,
                warnings=["time component truncated"],
            )
        return CoercionResult.ok(result, "datetime", "date")

    # From string
    if isinstance(value, str):
        value = value.strip()

        # Try ISO format first
        date_patterns = [
            (r"^(\d{4})-(\d{2})-(\d{2})$", "%Y-%m-%d"),
            (r"^(\d{2})/(\d{2})/(\d{4})$", "%m/%d/%Y"),
            (r"^(\d{2})-(\d{2})-(\d{4})$", "%d-%m-%Y"),
            (r"^(\d{4})/(\d{2})/(\d{2})$", "%Y/%m/%d"),
            (r"^(\d{8})$", "%Y%m%d"),
        ]

        for pattern, fmt in date_patterns:
            if re.match(pattern, value):
                try:
                    parsed = datetime.strptime(value, fmt).date()
                    return CoercionResult.ok(parsed, "string", "date")
                except ValueError:
                    continue

        # Try ISO parsing
        try:
            parsed = date.fromisoformat(value)
            return CoercionResult.ok(parsed, "string", "date")
        except ValueError:
            pass

        return CoercionResult.fail(
            "string", "date", f"cannot parse '{value}' as date"
        )

    # From int (Excel serial date)
    if isinstance(value, int):
        # Excel uses days since 1899-12-30
        if value > 0:
            try:
                excel_epoch = date(1899, 12, 30)
                result = excel_epoch + timedelta(days=value)
                return CoercionResult.ok(result, "int", "date")
            except (ValueError, OverflowError):
                pass
        return CoercionResult.fail("int", "date", f"invalid date value {value}")

    return CoercionResult.fail(
        source_type, "date", f"unsupported source type {source_type}"
    )


# =============================================================================
# Datetime coercion
# =============================================================================


def coerce_to_datetime(value: Any, policy: CoercionPolicy) -> CoercionResult:
    """Coerce a value to datetime type."""
    source_type = type(value).__name__

    if value is None:
        return CoercionResult.fail(source_type, "datetime", "cannot convert None")

    # From datetime (identity)
    if isinstance(value, datetime):
        return CoercionResult.ok(value, "datetime", "datetime")

    # From date (add midnight time)
    if isinstance(value, date):
        result = datetime.combine(value, time.min)
        return CoercionResult.ok(result, "date", "datetime")

    # From string
    if isinstance(value, str):
        value = value.strip()

        datetime_patterns = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ]

        for fmt in datetime_patterns:
            try:
                parsed = datetime.strptime(value, fmt)
                return CoercionResult.ok(parsed, "string", "datetime")
            except ValueError:
                continue

        # Try ISO parsing
        try:
            # Handle timezone-aware strings
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return CoercionResult.ok(parsed, "string", "datetime")
        except ValueError:
            pass

        # Try as date only
        try:
            parsed_date = date.fromisoformat(value)
            result = datetime.combine(parsed_date, time.min)
            return CoercionResult.ok(result, "string", "datetime")
        except ValueError:
            pass

        return CoercionResult.fail(
            "string", "datetime", f"cannot parse '{value}' as datetime"
        )

    # From int/float (Unix timestamp)
    if isinstance(value, (int, float)):
        try:
            result = datetime.fromtimestamp(value)
            return CoercionResult.ok(result, source_type, "datetime")
        except (ValueError, OSError, OverflowError):
            return CoercionResult.fail(
                source_type, "datetime", f"invalid timestamp {value}"
            )

    return CoercionResult.fail(
        source_type, "datetime", f"unsupported source type {source_type}"
    )
