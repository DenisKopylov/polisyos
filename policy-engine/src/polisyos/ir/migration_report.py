"""Public ir migration report module API."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from polisyos.ir.kernel.base import KernelModel

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class MigrationWarning(KernelModel):
    """Migration warning public type."""
    code: str
    message: str
    path: str | None = None


class MigrationAction(KernelModel):
    """Migration action public type."""
    kind: Literal["copy", "default", "drop", "transform", "split", "merge"]
    from_path: str | None = None
    to_path: str | None = None
    note: str | None = None
    lossy: bool = False


class MigrationReport(KernelModel):
    """Migration report data model."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    migration_id: str
    source_format: str
    source_schema_version: str
    target_format: str
    target_schema_version: str
    source_ref: str
    warnings: list[MigrationWarning] = Field(default_factory=list)
    actions: list[MigrationAction] = Field(default_factory=list)


__all__ = [
    "MigrationReport",
    "MigrationAction",
    "MigrationWarning",
]
