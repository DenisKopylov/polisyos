"""Public kernel slots module API."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from .base import SLOT_ID_PATTERN, KernelModel
from .merge_rules import ConflictResolution, MergeRuleRef
from .units import UnitRef


class SlotKind(str, Enum):
    """Slot kind public type."""
    STOCK = "stock"
    FLOW = "flow"
    PARAMETER = "parameter"


class SlotScope(str, Enum):
    """Slot scope public type."""
    GLOBAL = "global"
    PER_AGENT = "per_agent"
    PER_FIRM = "per_firm"
    PER_CELL = "per_cell"
    PER_ENTITY = "per_entity"


class SlotValueType(str, Enum):
    """Slot value type public type."""
    BOOL = "bool"
    INT = "int"
    DECIMAL = "decimal"
    STRING = "string"


class MergeOverride(KernelModel):
    """Slot-specific merge configuration."""

    conflict_resolution: ConflictResolution | None = None
    default_priority: int | None = Field(None, ge=0, le=1000)


class SlotSpec(KernelModel):
    """
    Specification for a state slot with explicit merge semantics.

    The merge_rule field is required to force explicit conflict resolution.
    """

    slot_id: str = Field(..., pattern=SLOT_ID_PATTERN)
    scope: SlotScope
    value_type: SlotValueType
    unit: UnitRef | None = None
    kind: SlotKind
    merge_rule: MergeRuleRef = Field(
        ...,
        description=(
            "Reference to merge rule. Required to prevent implicit order-dependent behavior."
        ),
    )
    merge_override: MergeOverride | None = Field(
        default=None,
        description="Slot-specific merge configuration overriding registry defaults.",
    )
    state_path: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=200)
    reset_rule: Literal["carry", "zero"] | None = None
    resample_rule: str | None = None
    conservation_group_id: str | None = None
    dtype: str | None = None
    shape: list[str] | None = None
    axes: list[str] | None = None


class SlotRegistry(KernelModel):
    """Slot registry implementation."""
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
        "agents.household_cell_id": SlotSpec(
            slot_id="agents.household_cell_id",
            scope=SlotScope.PER_AGENT,
            value_type=SlotValueType.INT,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="agents.household_cell_id",
            description="Household cell identifier for each agent",
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
        "firms.active": SlotSpec(
            slot_id="firms.active",
            scope=SlotScope.PER_FIRM,
            value_type=SlotValueType.BOOL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="firms.active",
            description="Firm active flag",
            reset_rule="carry",
        ),
        "firms.firm_id": SlotSpec(
            slot_id="firms.firm_id",
            scope=SlotScope.PER_FIRM,
            value_type=SlotValueType.INT,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="firms.firm_id",
            description="Firm identifier",
            reset_rule="carry",
        ),
        "firms.cell_id": SlotSpec(
            slot_id="firms.cell_id",
            scope=SlotScope.PER_FIRM,
            value_type=SlotValueType.INT,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="firms.cell_id",
            description="Firm cell identifier",
            reset_rule="carry",
        ),
        "firms.firm_type_id": SlotSpec(
            slot_id="firms.firm_type_id",
            scope=SlotScope.PER_FIRM,
            value_type=SlotValueType.INT,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="firms.firm_type_id",
            description="Firm type identifier",
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
        "cells.active": SlotSpec(
            slot_id="cells.active",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.BOOL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="cells.active",
            description="Cell activity flag",
            reset_rule="carry",
        ),
        "cells.region_code": SlotSpec(
            slot_id="cells.region_code",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.INT,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="cells.region_code",
            description="Region identifier for each cell",
            reset_rule="carry",
        ),
        "cells.sector_id": SlotSpec(
            slot_id="cells.sector_id",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.INT,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="cells.sector_id",
            description="Sector identifier for each cell",
            reset_rule="carry",
        ),
        "cells.population": SlotSpec(
            slot_id="cells.population",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="cells.population",
            description="Cell population",
            reset_rule="carry",
        ),
        "cells.firm_count": SlotSpec(
            slot_id="cells.firm_count",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="cells.firm_count",
            description="Cell firm count",
            reset_rule="carry",
        ),
        "cells.employment": SlotSpec(
            slot_id="cells.employment",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="cells.employment",
            description="Cell employment level",
            reset_rule="carry",
        ),
        "cells.output": SlotSpec(
            slot_id="cells.output",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="cells.output",
            description="Cell output proxy",
            reset_rule="carry",
        ),
        "cells.distress_score": SlotSpec(
            slot_id="cells.distress_score",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="cells.distress_score",
            description="Cell distress score",
            reset_rule="carry",
        ),
        "cells.public_service_index": SlotSpec(
            slot_id="cells.public_service_index",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="cells.public_service_index",
            description="Cell public service index",
            reset_rule="carry",
        ),
        "household_cells.active": SlotSpec(
            slot_id="household_cells.active",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.BOOL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="household_cells.active",
            description="Household-cell activity flag",
            reset_rule="carry",
        ),
        "household_cells.cell_id": SlotSpec(
            slot_id="household_cells.cell_id",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.INT,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="household_cells.cell_id",
            description="Parent cell identifier for household aggregation cells",
            reset_rule="carry",
        ),
        "household_cells.household_count": SlotSpec(
            slot_id="household_cells.household_count",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="household_cells.household_count",
            description="Household count per household cell",
            reset_rule="carry",
        ),
        "household_cells.disposable_income": SlotSpec(
            slot_id="household_cells.disposable_income",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="household_cells.disposable_income",
            description="Disposable income per household cell",
            reset_rule="carry",
        ),
        "household_cells.poverty_rate": SlotSpec(
            slot_id="household_cells.poverty_rate",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="household_cells.poverty_rate",
            description="Poverty rate per household cell",
            reset_rule="carry",
        ),
        "household_cells.transfer_intensity": SlotSpec(
            slot_id="household_cells.transfer_intensity",
            scope=SlotScope.PER_CELL,
            value_type=SlotValueType.DECIMAL,
            kind=SlotKind.STOCK,
            merge_rule=MergeRuleRef(rule_id="override"),
            state_path="household_cells.transfer_intensity",
            description="Transfer intensity per household cell",
            reset_rule="carry",
        ),
    }
)
