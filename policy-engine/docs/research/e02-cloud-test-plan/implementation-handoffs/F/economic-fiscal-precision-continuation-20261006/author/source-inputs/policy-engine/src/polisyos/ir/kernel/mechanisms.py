"""Mechanism registry definitions that describe runtime inputs, outputs, and parameter contracts."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel


class ParamType(str, Enum):
    """Param type public type."""

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
    """Define one mechanism parameter, including type, bounds, units, and trainability metadata."""

    param_id: str = Field(..., max_length=128)
    required: bool = False
    value_type: ParamType = ParamType.DECIMAL
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    # Флаг для дифференцируемого калибратора: параметр оптимизируется, если True
    trainable: bool = False
    # Опциональные прайоры (MVP: только хранение метаданных, без обязательного использования)
    prior_mean: Decimal | None = None
    prior_std: Decimal | None = None
    unit_id: str | None = Field(None, pattern=ID_PATTERN)
    description: str | None = Field(None, max_length=200)
    enum_values: list[str] | None = None


class MechanismTypeSpec(KernelModel):
    """Describe one mechanism contract, including params plus slot read/write side effects."""

    mechanism_id: str = Field(..., pattern=ID_PATTERN)
    params: dict[str, ParamSpec] = Field(default_factory=dict)
    reads_slots: list[str] = Field(default_factory=list)
    writes_slots: list[str] = Field(default_factory=list)
    default_merge: dict[str, str] = Field(default_factory=dict)
    description: str | None = Field(None, max_length=200)


class MechanismTypeRegistry(KernelModel):
    """Registry of mechanism contracts that ``link_trinity`` resolves before execution."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mechanisms: dict[str, MechanismTypeSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_registry(self) -> MechanismTypeRegistry:
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
                    trainable=True,
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
                    trainable=True,
                    unit_id="ratio",
                )
            },
            reads_slots=["agents.reported_income"],
            writes_slots=["agents.income", "government.balance"],
            default_merge={"agents.income": "sum", "government.balance": "sum"},
            description="Income tax applied to agent income",
        ),
        "labor_market": MechanismTypeSpec(
            mechanism_id="labor_market",
            params={
                "employment_threshold": ParamSpec(
                    param_id="employment_threshold",
                    required=False,
                    value_type=ParamType.RATE,
                    min_value=Decimal("0"),
                    max_value=Decimal("1"),
                )
            },
            reads_slots=[
                "agents.skill_level",
                "firms.wage_offer",
                "agents.is_employed",
                "agents.employer_id",
                "agents.income",
            ],
            writes_slots=[
                "agents.employer_id",
                "agents.is_employed",
                "agents.income",
                "firms.labor_count",
            ],
            default_merge={
                "agents.employer_id": "override",
                "agents.is_employed": "override",
                "agents.income": "sum",
                "firms.labor_count": "override",
            },
            description="Labor market assignment and wage updates",
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
        "adaptive_agent": MechanismTypeSpec(
            mechanism_id="adaptive_agent",
            params={
                "observation_space": ParamSpec(
                    param_id="observation_space", required=True, value_type=ParamType.ARRAY
                ),
                "action_space": ParamSpec(
                    param_id="action_space", required=True, value_type=ParamType.OBJECT
                ),
                "utility": ParamSpec(
                    param_id="utility", required=True, value_type=ParamType.STRING
                ),
                "policy_model": ParamSpec(
                    param_id="policy_model", required=False, value_type=ParamType.OBJECT
                ),
                "weights_artifact": ParamSpec(
                    param_id="weights_artifact", required=False, value_type=ParamType.STRING
                ),
                "learning_rate": ParamSpec(
                    param_id="learning_rate",
                    required=False,
                    value_type=ParamType.DECIMAL,
                    min_value=Decimal("0"),
                ),
                "seed": ParamSpec(
                    param_id="seed",
                    required=False,
                    value_type=ParamType.INT,
                    min_value=Decimal("0"),
                ),
                "stochastic": ParamSpec(
                    param_id="stochastic", required=False, value_type=ParamType.BOOL
                ),
            },
            reads_slots=[],
            writes_slots=[],
            description="Adaptive neural policy mechanism for agent decision-making",
        ),
    }
)


def resolve_mechanism_slots(
    mech: MechanismTypeSpec | None, params: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Resolve mechanism slots."""
    if mech is None:
        return [], []
    if mech.mechanism_id != "adaptive_agent":
        return list(mech.reads_slots), list(mech.writes_slots)

    reads: list[str] = []
    observation_space = params.get("observation_space")
    if isinstance(observation_space, list):
        reads = [item for item in observation_space if isinstance(item, str)]

    writes: list[str] = []
    action_space = params.get("action_space")
    if isinstance(action_space, dict):
        affects = action_space.get("affects")
        if isinstance(affects, list):
            writes = [item for item in affects if isinstance(item, str)]
        elif isinstance(affects, str):
            writes = [affects]
    return reads, writes
