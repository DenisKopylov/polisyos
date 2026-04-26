"""Schema migration contracts."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel

SchemaMigration = Callable[[dict[str, object]], dict[str, object]]


class SchemaMigrationPlan(DataForgeModel):
    """Registered migration edge between two schema versions."""

    schema_id: str = Field(min_length=1)
    from_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    to_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    migration_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")


__all__ = ["SchemaMigration", "SchemaMigrationPlan"]
