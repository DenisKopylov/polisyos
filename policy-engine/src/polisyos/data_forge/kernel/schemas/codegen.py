"""Schema code-generation placeholders for Phase 0A."""

from __future__ import annotations

from polisyos.data_forge.kernel._base import DataForgeModel


class GeneratedSchemaModule(DataForgeModel):
    """Description of generated schema code without writing files."""

    module_name: str
    schema_id: str
    schema_version: str


__all__ = ["GeneratedSchemaModule"]
