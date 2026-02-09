from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.kernel.numbers import DecimalValue
from polisyos.ir.types import SelectorOperator

SelectorScalar = str | int | bool | DecimalValue
SelectorValue = SelectorScalar | list[SelectorScalar]


class SelectorPredicate(KernelModel):
    kind: Literal["predicate"] = "predicate"
    field: str = Field(..., max_length=64)
    operator: SelectorOperator
    value: SelectorValue

    @model_validator(mode="after")
    def validate_value(self) -> "SelectorPredicate":
        if self.operator in {SelectorOperator.IN, SelectorOperator.NOT_IN}:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("operator 'in' requires a non-empty list")
        if self.operator == SelectorOperator.BETWEEN:
            if not isinstance(self.value, list) or len(self.value) != 2:
                raise ValueError("operator 'between' requires a list of two values")
        if self.operator == SelectorOperator.CONTAINS:
            if not isinstance(self.value, (str, list)):
                raise ValueError("operator 'contains' requires string or list value")
        return self


class SelectorAll(KernelModel):
    kind: Literal["all_of"] = "all_of"
    clauses: list["SelectorExpr"]


class SelectorAny(KernelModel):
    kind: Literal["any_of"] = "any_of"
    clauses: list["SelectorExpr"]


class SelectorNot(KernelModel):
    kind: Literal["not"] = "not"
    clause: "SelectorExpr"


SelectorExpr = Annotated[
    SelectorPredicate | SelectorAll | SelectorAny | SelectorNot,
    Field(discriminator="kind"),
]


__all__ = [
    "SelectorExpr",
    "SelectorPredicate",
    "SelectorAll",
    "SelectorAny",
    "SelectorNot",
    "SelectorScalar",
    "SelectorValue",
]
