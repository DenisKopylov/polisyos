"""Public foundry layout module API."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.kernel.slots import SlotRegistry, SlotScope

_KNOWN_SLOT_FAMILIES = ("agents", "firms", "cells", "household_cells", "global")
_ENTITY_SIZE_KEYS: dict[str, str | None] = {
    "agents": "n_agents",
    "firms": "n_firms",
    "cells": "n_cells",
    "household_cells": "n_household_cells",
    "global": None,
}
_FAMILY_SCOPES: dict[str, SlotScope] = {
    "agents": SlotScope.PER_AGENT,
    "firms": SlotScope.PER_FIRM,
    "cells": SlotScope.PER_CELL,
    "household_cells": SlotScope.PER_CELL,
    "global": SlotScope.GLOBAL,
}


class SlotLayout(BaseModel):
    """Resolved mapping from slot identifiers to state paths in `GlobalState`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    layout: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class SlotFamily(BaseModel):
    """Grouping of slots that share a state scope and cardinality key."""

    model_config = ConfigDict(extra="forbid")

    scope: SlotScope
    state_prefix: str | None = None
    entity_size_key: str | None = None
    slots: list[str] = Field(default_factory=list)


class SlotFamilyManifest(BaseModel):
    """Inventory of slot families derived from the active slot registry."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    families: dict[str, SlotFamily] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


def build_slot_layout(slot_registry: SlotRegistry) -> SlotLayout:
    """Materialize the slot-to-state-path layout used by execution and docs."""

    layout = {}
    for slot_id, spec in slot_registry.slots.items():
        if spec.state_path:
            layout[slot_id] = spec.state_path
    return SlotLayout(layout=layout)


def build_slot_family_manifest(slot_registry: SlotRegistry) -> SlotFamilyManifest:
    """Group slots into agent, firm, cell, and global state families."""

    families: dict[str, SlotFamily] = {}
    for slot_id, spec in sorted(slot_registry.slots.items()):
        family_name = _family_name_for_slot(slot_id=slot_id, state_path=spec.state_path)
        family = families.setdefault(
            family_name,
            SlotFamily(
                scope=_FAMILY_SCOPES[family_name],
                state_prefix=None if family_name == "global" else family_name,
                entity_size_key=_ENTITY_SIZE_KEYS[family_name],
                slots=[],
            ),
        )
        family.slots.append(slot_id)

    return SlotFamilyManifest(
        families=families,
        notes=["Families are derived from state_path prefixes when present, else slot_id prefixes."],
    )


def _family_name_for_slot(*, slot_id: str, state_path: str | None) -> str:
    source = state_path or slot_id
    prefix = source.split(".", 1)[0]
    if prefix in _KNOWN_SLOT_FAMILIES[:-1]:
        return prefix
    return "global"
