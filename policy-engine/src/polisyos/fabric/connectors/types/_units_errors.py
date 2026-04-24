"""Unit-related exception classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._units_core import Unit

__all__ = [
    "UnitConversionError",
    "UnitParseError",
]


class UnitParseError(ValueError):
    """Raised when a unit string cannot be parsed."""

    def __init__(self, unit_str: str, reason: str = ""):
        self.unit_str = unit_str
        self.reason = reason
        msg = f"Cannot parse unit '{unit_str}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class UnitConversionError(ValueError):
    """Raised when unit conversion is not possible."""

    def __init__(
        self,
        source: Unit,
        target: Unit,
        reason: str = "incompatible dimensions",
    ):
        self.source = source
        self.target = target
        self.reason = reason
        super().__init__(f"Cannot convert from '{source}' to '{target}': {reason}")
