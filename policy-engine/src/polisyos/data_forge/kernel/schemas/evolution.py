"""Schema evolution rule contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel


class SchemaChangeKind(str, Enum):
    """Known schema change families."""

    ADD_OPTIONAL_FIELD = "add_optional_field"
    ADD_REQUIRED_FIELD = "add_required_field"
    REMOVE_FIELD = "remove_field"
    TYPE_CHANGE = "type_change"
    METADATA_ONLY = "metadata_only"


class SchemaEvolutionRule(DataForgeModel):
    """Document why a schema change is allowed."""

    schema_id: str = Field(min_length=1)
    from_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    to_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    change_kind: SchemaChangeKind
    rationale: str = Field(min_length=1)


__all__ = ["SchemaChangeKind", "SchemaEvolutionRule"]
