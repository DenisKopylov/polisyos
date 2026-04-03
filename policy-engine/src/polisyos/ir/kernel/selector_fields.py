"""Public kernel selector fields module API."""
from __future__ import annotations

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel
from .slots import SlotScope


class SelectorFieldSpec(KernelModel):
    """Selector field spec data model."""
    field_id: str = Field(..., pattern=ID_PATTERN)
    scope: SlotScope
    state_path: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=200)


class SelectorFieldRegistry(KernelModel):
    """Selector field registry implementation."""
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    fields: dict[str, SelectorFieldSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_fields(self) -> "SelectorFieldRegistry":
        for key, spec in self.fields.items():
            if not key or not isinstance(key, str):
                raise ValueError("selector field id must be a non-empty string")
            if key != spec.field_id:
                raise ValueError(f"selector field id mismatch: '{key}' != '{spec.field_id}'")
        return self


DEFAULT_SELECTOR_FIELD_REGISTRY = SelectorFieldRegistry(
    fields={
        "id": SelectorFieldSpec(
            field_id="id",
            scope=SlotScope.PER_AGENT,
            description="Entity identifier",
        ),
        "agent_id": SelectorFieldSpec(
            field_id="agent_id",
            scope=SlotScope.PER_AGENT,
            description="Agent identifier",
        ),
        "age": SelectorFieldSpec(
            field_id="age",
            scope=SlotScope.PER_AGENT,
            state_path="agents.age",
            description="Agent age",
        ),
        "income": SelectorFieldSpec(
            field_id="income",
            scope=SlotScope.PER_AGENT,
            state_path="agents.income",
            description="Agent income",
        ),
        "savings": SelectorFieldSpec(
            field_id="savings",
            scope=SlotScope.PER_AGENT,
            state_path="agents.savings",
            description="Agent savings",
        ),
        "is_employed": SelectorFieldSpec(
            field_id="is_employed",
            scope=SlotScope.PER_AGENT,
            state_path="agents.is_employed",
            description="Employment flag",
        ),
        "household_cell_id": SelectorFieldSpec(
            field_id="household_cell_id",
            scope=SlotScope.PER_AGENT,
            state_path="agents.household_cell_id",
            description="Household cell identifier",
        ),
        "sector": SelectorFieldSpec(
            field_id="sector",
            scope=SlotScope.PER_FIRM,
            state_path="firms.sector_id",
            description="Economic sector",
        ),
        "firm_cell_id": SelectorFieldSpec(
            field_id="firm_cell_id",
            scope=SlotScope.PER_FIRM,
            state_path="firms.cell_id",
            description="Firm cell identifier",
        ),
        "region_code": SelectorFieldSpec(
            field_id="region_code",
            scope=SlotScope.PER_CELL,
            state_path="cells.region_code",
            description="Cell region code",
        ),
        "sector_id": SelectorFieldSpec(
            field_id="sector_id",
            scope=SlotScope.PER_CELL,
            state_path="cells.sector_id",
            description="Cell sector identifier",
        ),
        "employment_status": SelectorFieldSpec(
            field_id="employment_status",
            scope=SlotScope.PER_AGENT,
            state_path="agents.is_employed",
            description="Employment status label",
        ),
    },
    notes=["default selector fields"],
)
