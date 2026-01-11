from __future__ import annotations

from pydantic import Field, model_validator
from typing import Literal

from .base import ID_PATTERN, KernelModel, SLOT_ID_PATTERN


class ConstraintSpec(KernelModel):
    constraint_id: str = Field(..., pattern=ID_PATTERN)
    unit_id: str | None = Field(None, pattern=ID_PATTERN)
    slot_id: str | None = Field(None, pattern=SLOT_ID_PATTERN)
    operator: Literal["<", "<=", ">", ">=", "==", "!="] | None = None
    description: str | None = Field(None, max_length=200)


class ConstraintRegistry(KernelModel):
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
