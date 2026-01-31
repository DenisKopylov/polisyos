"""
Safe type coercion system for preventing silent data loss.

This module implements type conversion rules that:
- Allow widening conversions (int32 -> int64)
- Prevent narrowing conversions (float64 -> int32) unless safe
- Validate string-to-type conversions (strict parsing)
- Warn on potential precision loss

The system integrates with fabric/connectors/contracts/schema.py SchemaType
to provide conversion logic for the connector data pipeline.

Design principles:
- Explicit over implicit: no silent type conversions
- Safety first: prevent precision loss by default
- Configurable strictness: allow overrides when user accepts risk
- Clear error messages: explain what went wrong and why

Example:
    >>> from polisyos.fabric.connectors.types.coercion import (
    ...     TypeCoercion, CoercionPolicy, safe_cast
    ... )
    >>>
    >>> # Safe widening conversion
    >>> result = safe_cast(42, target_type="int64")
    >>> assert result == 42
    >>>
    >>> # Blocked narrowing conversion
    >>> safe_cast(3.14159, target_type="int32")  # Raises error
    >>>
    >>> # Strict string parsing
    >>> safe_cast("2024-01-15", target_type="date")
"""
from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum, auto
from typing import Any, Callable, ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "TypeCoercion",
    "CoercionPolicy",
    "CoercionResult",
    "CoercionError",
    "PrecisionLossWarning",
    "safe_cast",
    "can_safely_cast",
    "get_coercion_path",
    "CoercionRule",
]


# =============================================================================
# Type Variable
# =============================================================================

T = TypeVar("T")


# =============================================================================
# Exceptions and Warnings
# =============================================================================


class CoercionError(ValueError):
    """Raised when type coercion fails or would cause data loss."""

    def __init__(
        self,
        value: Any,
        source_type: str,
        target_type: str,
        reason: str,
    ):
        self.value = value
        self.source_type = source_type
        self.target_type = target_type
        self.reason = reason

        # Truncate long values for error message
        value_repr = repr(value)
        if len(value_repr) > 50:
            value_repr = value_repr[:50] + "..."

        super().__init__(
            f"Cannot coerce {value_repr} ({source_type}) to {target_type}: {reason}"
        )


class PrecisionLossWarning(UserWarning):
    """Warning issued when coercion may lose precision."""

    def __init__(
        self,
        value: Any,
        source_type: str,
        target_type: str,
        description: str,
    ):
        self.value = value
        self.source_type = source_type
        self.target_type = target_type
        self.description = description
        super().__init__(
            f"Potential precision loss converting {source_type} to {target_type}: "
            f"{description}"
        )


# =============================================================================
# Coercion Policy
# =============================================================================


class CoercionPolicy(str, Enum):
    """
    Policy for handling potentially lossy type conversions.

    Attributes:
        STRICT: Reject any conversion that could lose precision
        WARN: Allow with warning on potential precision loss
        LENIENT: Allow all valid conversions without warning
    """

    STRICT = "strict"
    WARN = "warn"
    LENIENT = "lenient"


# =============================================================================
# Schema Types (local definition to avoid circular imports)
# =============================================================================


class DataTypeCategory(Enum):
    """Categories of data types for coercion rules."""

    INTEGER = auto()
    FLOAT = auto()
    DECIMAL = auto()
    BOOLEAN = auto()
    STRING = auto()
    DATETIME = auto()
    DATE = auto()
    TIME = auto()
    DURATION = auto()
    BINARY = auto()
    ARRAY = auto()
    JSON = auto()
    CATEGORY = auto()


# Type info for coercion decisions
@dataclass(frozen=True)
class TypeInfo:
    """Information about a data type for coercion."""

    category: DataTypeCategory
    bits: int | None = None  # Bit width for numeric types
    signed: bool = True  # For integers
    precision: int | None = None  # For decimals

    @property
    def is_numeric(self) -> bool:
        """Check if this is a numeric type."""
        return self.category in (
            DataTypeCategory.INTEGER,
            DataTypeCategory.FLOAT,
            DataTypeCategory.DECIMAL,
        )


# Type info registry
TYPE_INFO: dict[str, TypeInfo] = {
    # Integers
    "int8": TypeInfo(DataTypeCategory.INTEGER, bits=8, signed=True),
    "int16": TypeInfo(DataTypeCategory.INTEGER, bits=16, signed=True),
    "int32": TypeInfo(DataTypeCategory.INTEGER, bits=32, signed=True),
    "int64": TypeInfo(DataTypeCategory.INTEGER, bits=64, signed=True),
    "uint8": TypeInfo(DataTypeCategory.INTEGER, bits=8, signed=False),
    "uint16": TypeInfo(DataTypeCategory.INTEGER, bits=16, signed=False),
    "uint32": TypeInfo(DataTypeCategory.INTEGER, bits=32, signed=False),
    "uint64": TypeInfo(DataTypeCategory.INTEGER, bits=64, signed=False),

    # Floats
    "float16": TypeInfo(DataTypeCategory.FLOAT, bits=16),
    "float32": TypeInfo(DataTypeCategory.FLOAT, bits=32),
    "float64": TypeInfo(DataTypeCategory.FLOAT, bits=64),

    # Decimal
    "decimal": TypeInfo(DataTypeCategory.DECIMAL),

    # Boolean
    "boolean": TypeInfo(DataTypeCategory.BOOLEAN),

    # String
    "string": TypeInfo(DataTypeCategory.STRING),
    "category": TypeInfo(DataTypeCategory.CATEGORY),

    # Temporal
    "date": TypeInfo(DataTypeCategory.DATE),
    "datetime": TypeInfo(DataTypeCategory.DATETIME),
    "timestamp_tz": TypeInfo(DataTypeCategory.DATETIME),
    "time": TypeInfo(DataTypeCategory.TIME),
    "duration": TypeInfo(DataTypeCategory.DURATION),

    # Complex
    "binary": TypeInfo(DataTypeCategory.BINARY),
    "array": TypeInfo(DataTypeCategory.ARRAY),
    "json": TypeInfo(DataTypeCategory.JSON),
}


# =============================================================================
# Coercion Result
# =============================================================================


@dataclass
class CoercionResult:
    """
    Result of a type coercion operation.

    Attributes:
        success: Whether the coercion succeeded
        value: The coerced value (if successful)
        source_type: Original type name
        target_type: Target type name
        precision_loss: Whether precision was potentially lost
        warnings: List of warning messages
        error: Error message if failed
    """

    success: bool
    value: Any = None
    source_type: str = ""
    target_type: str = ""
    precision_loss: bool = False
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def ok(
        cls,
        value: Any,
        source_type: str,
        target_type: str,
        *,
        precision_loss: bool = False,
        warnings: list[str] | None = None,
    ) -> "CoercionResult":
        """Create a successful result."""
        return cls(
            success=True,
            value=value,
            source_type=source_type,
            target_type=target_type,
            precision_loss=precision_loss,
            warnings=warnings or [],
        )

    @classmethod
    def fail(
        cls,
        source_type: str,
        target_type: str,
        error: str,
    ) -> "CoercionResult":
        """Create a failed result."""
        return cls(
            success=False,
            source_type=source_type,
            target_type=target_type,
            error=error,
        )


# =============================================================================
# Coercion Functions
# =============================================================================


def _get_int_range(bits: int, signed: bool) -> tuple[int, int]:
    """Get the valid range for an integer type."""
    if signed:
        return (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
    return (0, 2 ** bits - 1)


def _is_exact_integer(value: float) -> bool:
    """Check if a float value represents an exact integer."""
    return math.isfinite(value) and value == math.floor(value)


def _float_to_int_safe(value: float, target_bits: int, target_signed: bool) -> int | None:
    """
    Safely convert a float to an integer if it represents an exact integer.

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
    """
    Check if an integer can be exactly represented in a float.

    float32 has 24 bits of mantissa (23 explicit + 1 implicit)
    float64 has 53 bits of mantissa (52 explicit + 1 implicit)
    """
    mantissa_bits = {16: 11, 32: 24, 64: 53}
    max_exact = 2 ** mantissa_bits.get(float_bits, 53)
    return abs(value) <= max_exact


def _coerce_to_int(
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


def _coerce_to_float(
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


def _coerce_to_decimal(
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


def _coerce_to_boolean(value: Any, policy: CoercionPolicy) -> CoercionResult:
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


def _coerce_to_string(value: Any, policy: CoercionPolicy) -> CoercionResult:
    """Coerce a value to string type."""
    source_type = type(value).__name__

    if value is None:
        return CoercionResult.fail(source_type, "string", "cannot convert None")

    # Most types can be converted to string
    return CoercionResult.ok(str(value), source_type, "string")


def _coerce_to_date(value: Any, policy: CoercionPolicy) -> CoercionResult:
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


def _coerce_to_datetime(value: Any, policy: CoercionPolicy) -> CoercionResult:
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


# =============================================================================
# Main Coercion Class
# =============================================================================


class TypeCoercion:
    """
    Type coercion engine with configurable policy.

    Provides safe type conversions between schema types with:
    - Explicit policy control (STRICT, WARN, LENIENT)
    - Detailed error messages
    - Precision loss tracking

    Example:
        >>> coercer = TypeCoercion(policy=CoercionPolicy.STRICT)
        >>> result = coercer.coerce(3.14, "float64", "int32")
        >>> assert not result.success
        >>> assert "not an exact integer" in result.error
    """

    # Coercion function registry
    _COERCERS: ClassVar[dict[str, Callable[..., CoercionResult]]] = {}

    def __init__(self, policy: CoercionPolicy = CoercionPolicy.STRICT):
        """
        Initialize the type coercer.

        Args:
            policy: How to handle potentially lossy conversions.
        """
        self.policy = policy

    def coerce(
        self,
        value: Any,
        source_type: str,
        target_type: str,
    ) -> CoercionResult:
        """
        Coerce a value from source type to target type.

        Args:
            value: The value to coerce.
            source_type: The source type name (for context).
            target_type: The target type name.

        Returns:
            CoercionResult with success/failure and converted value.
        """
        target_lower = target_type.lower()

        # Integer types
        if target_lower in ("int8", "int16", "int32", "int64"):
            bits = int(target_lower[3:])
            result = _coerce_to_int(value, bits, signed=True, policy=self.policy)
        elif target_lower in ("uint8", "uint16", "uint32", "uint64"):
            bits = int(target_lower[4:])
            result = _coerce_to_int(value, bits, signed=False, policy=self.policy)
        elif target_lower in ("float16", "float32", "float64"):
            bits = int(target_lower[5:])
            result = _coerce_to_float(value, bits, policy=self.policy)
        elif target_lower == "decimal":
            result = _coerce_to_decimal(value, policy=self.policy)
        elif target_lower == "boolean":
            result = _coerce_to_boolean(value, policy=self.policy)
        elif target_lower in ("string", "category"):
            result = _coerce_to_string(value, policy=self.policy)
        elif target_lower == "date":
            result = _coerce_to_date(value, policy=self.policy)
        elif target_lower in ("datetime", "timestamp_tz"):
            result = _coerce_to_datetime(value, policy=self.policy)
        else:
            result = CoercionResult.fail(
                source_type, target_type,
                f"unsupported target type '{target_type}'"
            )

        if (
            self.policy == CoercionPolicy.WARN
            and result.success
            and result.precision_loss
        ):
            description = "; ".join(result.warnings) if result.warnings else "precision loss"
            warnings.warn(
                PrecisionLossWarning(value, source_type, target_type, description),
                stacklevel=2,
            )

        return result

    def can_coerce(self, source_type: str, target_type: str) -> bool:
        """
        Check if coercion is theoretically possible.

        Does not check actual value - just type compatibility.
        """
        path = get_coercion_path(source_type, target_type)
        return path is not None


# =============================================================================
# Module-level convenience functions
# =============================================================================


def safe_cast(
    value: Any,
    target_type: str,
    *,
    policy: CoercionPolicy = CoercionPolicy.STRICT,
    source_type: str | None = None,
) -> Any:
    """
    Safely cast a value to a target type.

    Args:
        value: The value to cast.
        target_type: The target type name (e.g., "int64", "float32").
        policy: How to handle potentially lossy conversions.
        source_type: Optional source type name (inferred if not provided).

    Returns:
        The converted value.

    Raises:
        CoercionError: If conversion fails or would lose precision (in STRICT mode).

    Example:
        >>> safe_cast(42, "float64")  # OK
        42.0
        >>> safe_cast(3.14, "int32")  # Error in STRICT mode
        CoercionError: ...
    """
    if source_type is None:
        source_type = type(value).__name__

    coercer = TypeCoercion(policy=policy)
    result = coercer.coerce(value, source_type, target_type)

    if not result.success:
        raise CoercionError(
            value=value,
            source_type=source_type,
            target_type=target_type,
            reason=result.error or "unknown error",
        )

    return result.value


def can_safely_cast(
    value: Any,
    target_type: str,
    *,
    policy: CoercionPolicy = CoercionPolicy.STRICT,
) -> bool:
    """
    Check if a value can be safely cast to a target type.

    Args:
        value: The value to check.
        target_type: The target type name.
        policy: How to handle potentially lossy conversions.

    Returns:
        True if the value can be safely cast, False otherwise.
    """
    coercer = TypeCoercion(policy=policy)
    result = coercer.coerce(value, type(value).__name__, target_type)
    return result.success


def get_coercion_path(source_type: str, target_type: str) -> list[str] | None:
    """
    Get the coercion path from source to target type.

    Some conversions require intermediate types. This function returns
    the sequence of types to pass through, or None if no path exists.

    Args:
        source_type: Source type name.
        target_type: Target type name.

    Returns:
        List of type names in the coercion path, or None if impossible.
    """
    source_lower = source_type.lower()
    target_lower = target_type.lower()

    # Same type - trivial
    if source_lower == target_lower:
        return [target_type]

    source_info = TYPE_INFO.get(source_lower)
    target_info = TYPE_INFO.get(target_lower)

    if source_info is None or target_info is None:
        # Unknown types - assume direct path possible
        return [source_type, target_type]

    # Integer widening
    if (
        source_info.category == DataTypeCategory.INTEGER
        and target_info.category == DataTypeCategory.INTEGER
    ):
        if source_info.bits and target_info.bits:
            if target_info.bits >= source_info.bits:
                # Check sign compatibility
                if source_info.signed or not target_info.signed:
                    return [source_type, target_type]

    # Integer to float (always possible)
    if (
        source_info.category == DataTypeCategory.INTEGER
        and target_info.category == DataTypeCategory.FLOAT
    ):
        return [source_type, target_type]

    # Float widening
    if (
        source_info.category == DataTypeCategory.FLOAT
        and target_info.category == DataTypeCategory.FLOAT
    ):
        if source_info.bits and target_info.bits:
            if target_info.bits >= source_info.bits:
                return [source_type, target_type]

    # Any numeric to Decimal
    if source_info.is_numeric and target_info.category == DataTypeCategory.DECIMAL:
        return [source_type, target_type]

    # String to most types
    if source_info.category == DataTypeCategory.STRING:
        return [source_type, target_type]

    # Most types to string
    if target_info.category == DataTypeCategory.STRING:
        return [source_type, target_type]

    # Date/datetime conversions
    if source_info.category == DataTypeCategory.DATE:
        if target_info.category == DataTypeCategory.DATETIME:
            return [source_type, target_type]

    if source_info.category == DataTypeCategory.DATETIME:
        if target_info.category == DataTypeCategory.DATE:
            return [source_type, target_type]

    # No known path
    return None


# =============================================================================
# Pydantic Model for Schema Integration
# =============================================================================


class CoercionRule(BaseModel):
    """
    Pydantic model for coercion rules in data schemas.

    This can be attached to FieldSpec to define explicit coercion behavior.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: str = Field(
        ...,
        description="Source type to coerce from",
    )
    target_type: str = Field(
        ...,
        description="Target type to coerce to",
    )
    policy: CoercionPolicy = Field(
        default=CoercionPolicy.STRICT,
        description="Coercion policy for this rule",
    )
    allow_null: bool = Field(
        default=True,
        description="Whether to allow null values through",
    )
    default_value: Any = Field(
        default=None,
        description="Default value if coercion fails (only in LENIENT mode)",
    )
