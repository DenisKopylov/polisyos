from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator
from typing_extensions import Annotated

from .base import ID_PATTERN, KernelModel


class UnitKind(str, Enum):
    MONEY = "money"
    RATE = "rate"
    COUNT = "count"
    DURATION = "duration"
    DIMENSIONLESS = "dimensionless"
    GENERIC = "generic"


class UnitRef(KernelModel):
    unit_id: str = Field(..., pattern=ID_PATTERN)


class UnitSpec(KernelModel):
    kind: UnitKind


class MoneyUnit(UnitSpec):
    kind: Literal["money"] = "money"
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    nominal_year: int | None = Field(None, ge=1900, le=2100)
    price_base: str | None = Field(None, max_length=64)


class RateUnit(UnitSpec):
    kind: Literal["rate"] = "rate"
    base: Literal["ratio", "percent"] = "ratio"


class CountUnit(UnitSpec):
    kind: Literal["count"] = "count"
    label: str | None = Field(None, max_length=64)


class DurationUnit(UnitSpec):
    kind: Literal["duration"] = "duration"
    unit: Literal["step", "day", "month", "quarter", "year"] = "step"


class DimensionlessUnit(UnitSpec):
    kind: Literal["dimensionless"] = "dimensionless"
    label: str | None = Field(None, max_length=64)


class GenericUnit(UnitSpec):
    kind: Literal["generic"] = "generic"
    label: str = Field(..., max_length=64)
    description: str | None = Field(None, max_length=200)


UnitSpecType = Annotated[
    MoneyUnit | RateUnit | CountUnit | DurationUnit | DimensionlessUnit | GenericUnit,
    Field(discriminator="kind"),
]


class UnitsRegistry(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    units: dict[str, UnitSpecType] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_units(self) -> "UnitsRegistry":
        for key in self.units:
            if not key or not isinstance(key, str):
                raise ValueError("unit_id must be a non-empty string")
            if not _valid_id(key):
                raise ValueError(f"unit_id '{key}' does not match {ID_PATTERN}")
        return self


def _valid_id(value: str) -> bool:
    import re

    return bool(re.match(ID_PATTERN, value))


DEFAULT_UNITS_REGISTRY = UnitsRegistry(
    units={
        "ratio": RateUnit(base="ratio"),
        "percent": RateUnit(base="percent"),
        "usd": MoneyUnit(currency="USD"),
        "uah": MoneyUnit(currency="UAH"),
        "year": DurationUnit(unit="year"),
        "month": DurationUnit(unit="month"),
        "per_step": GenericUnit(label="per_step", description="per simulation step"),
    }
)
