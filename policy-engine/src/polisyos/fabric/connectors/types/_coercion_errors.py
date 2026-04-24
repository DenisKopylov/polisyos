"""Coercion error and warning types.

Defines the exception and warning classes used throughout the coercion
subsystem to signal conversion failures and potential precision loss.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CoercionError",
    "PrecisionLossWarning",
]


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

        super().__init__(f"Cannot coerce {value_repr} ({source_type}) to {target_type}: {reason}")


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
            f"Potential precision loss converting {source_type} to {target_type}: {description}"
        )
