"""Unit registry definitions shared by metrics, predicates, slots, and constraints."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel


class UnitKind(str, Enum):
    """Unit kind public type."""

    MONEY = "money"
    RATE = "rate"
    COUNT = "count"
    DURATION = "duration"
    DIMENSIONLESS = "dimensionless"
    GENERIC = "generic"


class UnitRef(KernelModel):
    """Reference a unit-registry entry from another kernel or IR contract."""

    unit_id: str = Field(..., pattern=ID_PATTERN)


class UnitSpec(KernelModel):
    """Unit spec data model."""

    kind: UnitKind


class MoneyUnit(UnitSpec):
    """Money unit public type."""

    kind: Literal["money"] = "money"
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    nominal_year: int | None = Field(None, ge=1900, le=2100)
    price_base: str | None = Field(None, max_length=64)


class RateUnit(UnitSpec):
    """Rate unit public type."""

    kind: Literal["rate"] = "rate"
    base: Literal["ratio", "percent"] = "ratio"


class CountUnit(UnitSpec):
    """Count unit public type."""

    kind: Literal["count"] = "count"
    label: str | None = Field(None, max_length=64)


class DurationUnit(UnitSpec):
    """Duration unit public type."""

    kind: Literal["duration"] = "duration"
    unit: Literal["step", "day", "month", "quarter", "year"] = "step"


class DimensionlessUnit(UnitSpec):
    """Dimensionless unit public type."""

    kind: Literal["dimensionless"] = "dimensionless"
    label: str | None = Field(None, max_length=64)


class GenericUnit(UnitSpec):
    """Generic unit public type."""

    kind: Literal["generic"] = "generic"
    label: str = Field(..., max_length=64)
    description: str | None = Field(None, max_length=200)


UnitSpecType = Annotated[
    MoneyUnit | RateUnit | CountUnit | DurationUnit | DimensionlessUnit | GenericUnit,
    Field(discriminator="kind"),
]


class UnitsRegistry(KernelModel):
    """Registry of unit definitions that becomes stable once a registry bundle is composed."""

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    units: dict[str, UnitSpecType] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_units(self) -> UnitsRegistry:
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
        "index": GenericUnit(
            label="index",
            description="generic measured index level",
        ),
        "per_step": GenericUnit(label="per_step", description="per simulation step"),
    }
)
