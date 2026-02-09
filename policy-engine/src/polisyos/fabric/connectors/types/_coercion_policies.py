"""Coercion policy enums, type metadata, and the CoercionRule model.

Contains:
- CoercionPolicy enum (STRICT / WARN / LENIENT)
- DataTypeCategory enum (INTEGER, FLOAT, ...)
- TypeInfo frozen dataclass + TYPE_INFO registry
- CoercionResult dataclass
- CoercionRule Pydantic model for schema integration
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CoercionPolicy",
    "DataTypeCategory",
    "TypeInfo",
    "TYPE_INFO",
    "CoercionResult",
    "CoercionRule",
]


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
