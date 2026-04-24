"""Result types produced by the Trinity linker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, ID_PATTERN, KernelModel

if TYPE_CHECKING:
    from polisyos.ir.trinity import TrinityBundle
else:
    from polisyos.ir.trinity import TrinityBundle

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class LinkedIntervention(KernelModel):
    """Linked intervention public type."""

    intervention_id: str = Field(..., pattern=ID_PATTERN)
    mechanism_id: str = Field(..., pattern=ID_PATTERN)
    reads_slots: list[str] = Field(default_factory=list)
    writes_slots: list[str] = Field(default_factory=list)
    schedule_start: int
    schedule_end: int


class TrinityBindings(KernelModel):
    """Trinity bindings public type."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    interventions: list[LinkedIntervention] = Field(default_factory=list)
    used_mechanisms: list[str] = Field(default_factory=list)
    used_slots_read: list[str] = Field(default_factory=list)
    used_slots_write: list[str] = Field(default_factory=list)
    used_units: list[str] = Field(default_factory=list)
    used_metrics: list[str] = Field(default_factory=list)
    used_constraints: list[str] = Field(default_factory=list)
    used_selector_fields: list[str] = Field(default_factory=list)


class LinkedTrinityBundle(KernelModel):
    """Bundle a Trinity payload with resolved registry bindings and stable digests after linking."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    bundle: TrinityBundle
    registry_digest: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    bundle_digest: str | None = Field(None, pattern=ARTIFACT_ID_PATTERN)
    bindings: TrinityBindings = Field(default_factory=TrinityBindings)


__all__ = [
    "SCHEMA_VERSION_PATTERN",
    "LinkedIntervention",
    "LinkedTrinityBundle",
    "TrinityBindings",
]
