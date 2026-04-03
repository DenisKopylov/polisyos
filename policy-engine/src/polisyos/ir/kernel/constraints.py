"""Constraint registry definitions used by problem framing and Trinity linking."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import ID_PATTERN, SLOT_ID_PATTERN, KernelModel


class ConstraintSpec(KernelModel):
    """Declare one named bound or legal/accounting rule that downstream linkers can validate."""
    constraint_id: str = Field(..., pattern=ID_PATTERN)
    unit_id: str | None = Field(None, pattern=ID_PATTERN)
    slot_id: str | None = Field(None, pattern=SLOT_ID_PATTERN)
    operator: Literal["<", "<=", ">", ">=", "==", "!="] | None = None
    description: str | None = Field(None, max_length=200)
    constraint_type: Literal["accounting", "non_negative", "budget", "legal"] | None = None
    policy_by_mode: dict[str, str] | None = None
    repair_strategy: str | None = None


class ConstraintRegistry(KernelModel):
    """Registry of reusable constraints that ``link_trinity`` and governance checks resolve by id."""
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    constraints: dict[str, ConstraintSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_constraints(self) -> "ConstraintRegistry":
        for key, spec in self.constraints.items():
            if not key or not isinstance(key, str):
                raise ValueError("constraint id must be a non-empty string")
            if key != spec.constraint_id:
                raise ValueError(f"constraint id mismatch: '{key}' != '{spec.constraint_id}'")
            if spec.operator is not None and spec.slot_id is None:
                raise ValueError(
                    f"constraint '{spec.constraint_id}' defines operator without slot_id"
                )
        return self


DEFAULT_CONSTRAINT_REGISTRY = ConstraintRegistry(
    constraints={
        "min_balance": ConstraintSpec(
            constraint_id="min_balance",
            unit_id="usd",
            slot_id="government.balance",
            operator=">=",
            description="Minimum acceptable government balance",
        )
    },
    notes=["default constraints"],
)
