from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from .base import SLOT_ID_PATTERN, KernelModel
from .merge_rules import MergeRuleRef
from .units import UnitRef


class SlotKind(str, Enum):
    STOCK = "stock"
    FLOW = "flow"
    PARAMETER = "parameter"


class SlotScope(str, Enum):
    GLOBAL = "global"
    PER_AGENT = "per_agent"
    PER_FIRM = "per_firm"
    PER_ENTITY = "per_entity"


class SlotValueType(str, Enum):
    BOOL = "bool"
    INT = "int"
    DECIMAL = "decimal"
    STRING = "string"


class SlotSpec(KernelModel):
    slot_id: str = Field(..., pattern=SLOT_ID_PATTERN)
    scope: SlotScope
    value_type: SlotValueType
    unit: UnitRef | None = None
    kind: SlotKind
    merge_rule: MergeRuleRef
    state_path: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=200)


class SlotRegistry(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    slots: dict[str, SlotSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_slots(self) -> "SlotRegistry":
        for key, spec in self.slots.items():
            if not key or not isinstance(key, str):
                raise ValueError("slot_id must be a non-empty string")
            if key != spec.slot_id:
                raise ValueError(f"slot_id mismatch: '{key}' != '{spec.slot_id}'")
        return self


DEFAULT_SLOT_REGISTRY = SlotRegistry(
    slots={
        "agents.income": SlotSpec(
            slot_id="agents.income",
            scope=SlotScope.PER_AGENT,
            value_type=SlotValueType.DECIMAL,
            unit=UnitRef(unit_id="usd"),
            kind=SlotKind.FLOW,
            merge_rule=MergeRuleRef(rule_id="sum"),
            state_path="agents.income",
            description="Agent income (per-step flow)",
        ),
        "government.balance": SlotSpec(
            slot_id="government.balance",
            scope=SlotScope.GLOBAL,
            value_type=SlotValueType.DECIMAL,
            unit=UnitRef(unit_id="usd"),
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="sum"),
            state_path="government_balance",
            description="Government balance (stock)",
        ),
    }
)
