from __future__ import annotations

from enum import Enum
from typing import Literal

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
    reset_rule: Literal["carry", "zero"] | None = None
    resample_rule: str | None = None
    conservation_group_id: str | None = None
    dtype: str | None = None
    shape: list[str] | None = None
    axes: list[str] | None = None


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
            reset_rule="zero",
        ),
        "agents.reported_income": SlotSpec(
            slot_id="agents.reported_income",
            scope=SlotScope.PER_AGENT,
            value_type=SlotValueType.DECIMAL,
            unit=UnitRef(unit_id="usd"),
            kind=SlotKind.FLOW,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="agents.reported_income",
            description="Income reported by agent for taxation",
            reset_rule="zero",
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
            reset_rule="carry",
        ),
        "global.tax_rate": SlotSpec(
            slot_id="global.tax_rate",
            scope=SlotScope.GLOBAL,
            value_type=SlotValueType.DECIMAL,
            unit=UnitRef(unit_id="ratio"),
            kind=SlotKind.PARAMETER,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="tax_rate",
            description="Global income tax rate parameter",
            reset_rule="carry",
        ),
        "agents.employer_id": SlotSpec(
            slot_id="agents.employer_id",
            scope=SlotScope.PER_AGENT,
            value_type=SlotValueType.INT,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="agents.employer_id",
            description="Agent employer identifier",
            reset_rule="carry",
        ),
        "agents.is_employed": SlotSpec(
            slot_id="agents.is_employed",
            scope=SlotScope.PER_AGENT,
            value_type=SlotValueType.BOOL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="agents.is_employed",
            description="Agent employment flag",
            reset_rule="carry",
        ),
        "agents.skill_level": SlotSpec(
            slot_id="agents.skill_level",
            scope=SlotScope.PER_AGENT,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="agents.skill_level",
            description="Agent skill level",
            reset_rule="carry",
        ),
        "agents.risk_aversion": SlotSpec(
            slot_id="agents.risk_aversion",
            scope=SlotScope.PER_AGENT,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="agents.risk_aversion",
            description="Agent risk aversion trait",
            reset_rule="carry",
        ),
        "firms.labor_count": SlotSpec(
            slot_id="firms.labor_count",
            scope=SlotScope.PER_FIRM,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="firms.labor_count",
            description="Firm labor count",
            reset_rule="carry",
        ),
        "firms.wage_offer": SlotSpec(
            slot_id="firms.wage_offer",
            scope=SlotScope.PER_FIRM,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="firms.wage_offer",
            description="Firm wage offer",
            reset_rule="carry",
        ),
    }
)
