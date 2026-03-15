"""Safe type coercion system for preventing silent data loss.

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

from ._coercion_engine import (
    TypeCoercion,
    can_safely_cast,
    get_coercion_path,
    safe_cast,
)
from ._coercion_errors import CoercionError, PrecisionLossWarning
from ._coercion_policies import CoercionPolicy, CoercionResult, CoercionRule

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
