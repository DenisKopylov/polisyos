"""Main type coercion engine and module-level convenience functions.

Contains:
- TypeCoercion class: the primary coercion engine with configurable policy
- safe_cast(): convenience function that raises on failure
- can_safely_cast(): convenience predicate for checking castability
- get_coercion_path(): determines the intermediate type path between two types
"""
from __future__ import annotations

import warnings
from typing import Any, Callable, ClassVar

from ._coercion_errors import CoercionError, PrecisionLossWarning
from ._coercion_policies import (
    CoercionPolicy,
    CoercionResult,
    DataTypeCategory,
    TYPE_INFO,
)
from ._coercion_rules import (
    coerce_to_int,
    coerce_to_float,
    coerce_to_decimal,
    coerce_to_boolean,
    coerce_to_string,
    coerce_to_date,
    coerce_to_datetime,
)

__all__ = [
    "TypeCoercion",
    "safe_cast",
    "can_safely_cast",
    "get_coercion_path",
]


# =============================================================================
# Coercion Path Resolution
# =============================================================================


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
            result = coerce_to_int(value, bits, signed=True, policy=self.policy)
        elif target_lower in ("uint8", "uint16", "uint32", "uint64"):
            bits = int(target_lower[4:])
            result = coerce_to_int(value, bits, signed=False, policy=self.policy)
        elif target_lower in ("float16", "float32", "float64"):
            bits = int(target_lower[5:])
            result = coerce_to_float(value, bits, policy=self.policy)
        elif target_lower == "decimal":
            result = coerce_to_decimal(value, policy=self.policy)
        elif target_lower == "boolean":
            result = coerce_to_boolean(value, policy=self.policy)
        elif target_lower in ("string", "category"):
            result = coerce_to_string(value, policy=self.policy)
        elif target_lower == "date":
            result = coerce_to_date(value, policy=self.policy)
        elif target_lower in ("datetime", "timestamp_tz"):
            result = coerce_to_datetime(value, policy=self.policy)
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
