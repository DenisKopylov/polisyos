from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from .base import KernelModel
from .numbers import DecimalValue


class MoneyValue(KernelModel):
    amount: DecimalValue
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    nominal_year: int | None = Field(None, ge=1900, le=2100)


class RateValue(KernelModel):
    value: DecimalValue
    base: Literal["ratio", "percent"] = "ratio"

    @model_validator(mode="after")
    def validate_range(self) -> "RateValue":
        lower = Decimal("0")
        upper = Decimal("1") if self.base == "ratio" else Decimal("100")
        if self.value < lower or self.value > upper:
            raise ValueError(f"rate out of range for base '{self.base}'")
        return self

    def as_ratio(self) -> Decimal:
        if self.base == "ratio":
            return self.value
        return self.value / Decimal("100")


class CountValue(KernelModel):
    value: int = Field(..., ge=0)
    label: str | None = Field(None, max_length=64)


class DurationValue(KernelModel):
    value: int = Field(..., ge=0)
    unit: Literal["step", "day", "month", "quarter", "year"] = "step"
