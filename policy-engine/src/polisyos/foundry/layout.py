from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.kernel.slots import SlotRegistry


class SlotLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    layout: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


def build_slot_layout(slot_registry: SlotRegistry) -> SlotLayout:
    layout = {}
    for slot_id, spec in slot_registry.slots.items():
        if spec.state_path:
            layout[slot_id] = spec.state_path
    return SlotLayout(layout=layout)
