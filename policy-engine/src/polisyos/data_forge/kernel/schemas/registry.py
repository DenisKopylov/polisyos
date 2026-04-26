"""Versioned schema registry skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pydantic import Field

from polisyos.data_forge.errors import DataForgeValidationError
from polisyos.data_forge.kernel._base import DataForgeModel

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+\.\d+$"


class CompatibilityMode(str, Enum):
    """Compatibility mode declared for a schema version."""

    BACKWARD = "BACKWARD"
    FORWARD = "FORWARD"
    FULL = "FULL"


class SchemaVersion(DataForgeModel):
    """One versioned JSON-schema-like contract."""

    schema_id: str = Field(min_length=1)
    version: str = Field(pattern=SCHEMA_VERSION_PATTERN)
    compat_mode: CompatibilityMode
    json_schema: dict[str, object] = Field(default_factory=dict)


@dataclass(slots=True)
class SchemaRegistry:
    """In-memory registry for Phase 0A schema contracts."""

    _schemas: dict[tuple[str, str], SchemaVersion] = field(default_factory=dict)

    def register(self, schema: SchemaVersion) -> SchemaVersion:
        """Register one schema version, rejecting duplicate ids."""
        key = (schema.schema_id, schema.version)
        if key in self._schemas:
            raise DataForgeValidationError(
                f"schema already registered: {schema.schema_id}@{schema.version}"
            )
        self._schemas[key] = schema
        return schema

    def get(self, schema_id: str, version: str) -> SchemaVersion:
        """Return one schema version."""
        try:
            return self._schemas[(schema_id, version)]
        except KeyError as exc:
            raise DataForgeValidationError(f"schema not registered: {schema_id}@{version}") from exc

    def latest(self, schema_id: str) -> SchemaVersion:
        """Return the lexicographically latest semantic version for a schema id."""
        candidates = [schema for key, schema in self._schemas.items() if key[0] == schema_id]
        if not candidates:
            raise DataForgeValidationError(f"schema not registered: {schema_id}")
        return max(candidates, key=lambda schema: tuple(map(int, schema.version.split("."))))

    def list_versions(self, schema_id: str) -> tuple[SchemaVersion, ...]:
        """Return all versions registered for a schema id in ascending version order."""
        candidates = [schema for key, schema in self._schemas.items() if key[0] == schema_id]
        return tuple(
            sorted(candidates, key=lambda schema: tuple(map(int, schema.version.split("."))))
        )


__all__ = ["CompatibilityMode", "SchemaRegistry", "SchemaVersion"]
