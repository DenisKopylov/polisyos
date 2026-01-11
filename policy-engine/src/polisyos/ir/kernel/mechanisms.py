from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel


class ParamType(str, Enum):
    DECIMAL = "decimal"
    INT = "int"
    BOOL = "bool"
    STRING = "string"
    MONEY = "money"
    RATE = "rate"
    COUNT = "count"
    DURATION = "duration"
    ENUM = "enum"
    OBJECT = "object"
    ARRAY = "array"


class ParamSpec(KernelModel):
    param_id: str = Field(..., max_length=128)
    required: bool = False
    value_type: ParamType = ParamType.DECIMAL
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    unit_id: str | None = Field(None, pattern=ID_PATTERN)
    description: str | None = Field(None, max_length=200)
    enum_values: list[str] | None = None


class MechanismTypeSpec(KernelModel):
    mechanism_id: str = Field(..., pattern=ID_PATTERN)
    params: dict[str, ParamSpec] = Field(default_factory=dict)
    reads_slots: list[str] = Field(default_factory=list)
    writes_slots: list[str] = Field(default_factory=list)
    default_merge: dict[str, str] = Field(default_factory=dict)
    description: str | None = Field(None, max_length=200)


class MechanismTypeRegistry(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mechanisms: dict[str, MechanismTypeSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_registry(self) -> "MechanismTypeRegistry":
        for key, spec in self.mechanisms.items():
            if not key or not isinstance(key, str):
                raise ValueError("mechanism id must be a non-empty string")
            if key != spec.mechanism_id:
                raise ValueError(f"mechanism id mismatch: '{key}' != '{spec.mechanism_id}'")
            for param_key, param in spec.params.items():
                if param_key != param.param_id:
                    raise ValueError(
                        f"param id mismatch for mechanism '{key}': '{param_key}' != '{param.param_id}'"
                    )
        return self


DEFAULT_MECHANISM_REGISTRY = MechanismTypeRegistry(
    mechanisms={
        "tax_subsidy": MechanismTypeSpec(
            mechanism_id="tax_subsidy",
            params={
                "rate": ParamSpec(
                    param_id="rate",
                    required=True,
                    value_type=ParamType.RATE,
                    min_value=Decimal("0"),
                    max_value=Decimal("1"),
                    unit_id="ratio",
                )
            },
            reads_slots=["agents.income"],
            writes_slots=["agents.income", "government.balance"],
            default_merge={"agents.income": "sum", "government.balance": "sum"},
            description="Subsidy applied to agent income",
        ),
        "income_tax": MechanismTypeSpec(
            mechanism_id="income_tax",
            params={
                "rate": ParamSpec(
                    param_id="rate",
                    required=True,
                    value_type=ParamType.RATE,
                    min_value=Decimal("0"),
                    max_value=Decimal("1"),
                    unit_id="ratio",
                )
            },
            reads_slots=["agents.income"],
            writes_slots=["agents.income", "government.balance"],
            default_merge={"agents.income": "sum", "government.balance": "sum"},
            description="Income tax applied to agent income",
        ),
        "queue": MechanismTypeSpec(
            mechanism_id="queue",
            params={
                "service_rate": ParamSpec(
                    param_id="service_rate",
                    required=True,
                    value_type=ParamType.DECIMAL,
                    min_value=Decimal("0"),
                    max_value=Decimal("1e9"),
                    unit_id="per_step",
                ),
                "arrival_rate": ParamSpec(
                    param_id="arrival_rate",
                    required=True,
                    value_type=ParamType.DECIMAL,
                    min_value=Decimal("0"),
                    max_value=Decimal("1e9"),
                    unit_id="per_step",
                ),
            },
            description="Queue mechanism (standalone)",
        ),
    }
)
