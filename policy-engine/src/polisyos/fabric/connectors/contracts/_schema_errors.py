"""
Exception hierarchy for schema validation and type coercion errors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._schema_types import SchemaType

__all__ = [
    "JaxTypeError",
    "SchemaCompatibilityError",
    "SchemaError",
    "TypeCoercionError",
]


class SchemaError(Exception):
    """Base exception for schema errors."""


class TypeCoercionError(SchemaError):
    """Raised when type coercion fails."""

    def __init__(
        self,
        source_type: SchemaType,
        target_type: SchemaType,
        field_name: str | None = None,
    ) -> None:
        self.source_type = source_type
        self.target_type = target_type
        self.field_name = field_name

        msg = f"Cannot coerce {source_type.value} to {target_type.value}"
        if field_name:
            msg = f"Field '{field_name}': {msg}"
        super().__init__(msg)


class JaxTypeError(SchemaError):
    """Raised when a type cannot be used in JAX."""

    def __init__(self, data_type: SchemaType, field_name: str | None = None) -> None:
        self.data_type = data_type
        self.field_name = field_name

        msg = f"Type {data_type.value} cannot be used in JAX arrays"
        if field_name:
            msg = f"Field '{field_name}': {msg}"
        super().__init__(msg)


class SchemaCompatibilityError(SchemaError):
    """Raised when schemas are incompatible."""

    def __init__(self, source_schema: str, target_schema: str, reason: str) -> None:
        self.source_schema = source_schema
        self.target_schema = target_schema
        self.reason = reason
        super().__init__(f"Schema '{source_schema}' incompatible with '{target_schema}': {reason}")
