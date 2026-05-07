"""Public governance selector expr module API."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, model_validator

from polisyos.ir._internal.validation import (
    validate_selector_aggregation_shape,
    validate_selector_predicate_shape,
    validate_selector_quantifier_shape,
    validate_selector_temporal_shape,
)
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.kernel.numbers import DecimalValue

if TYPE_CHECKING:
    from polisyos.ir.types import SelectorOperator
else:
    from polisyos.ir.types import SelectorOperator

SelectorScalar = str | int | bool | DecimalValue
SelectorValue = SelectorScalar | list[SelectorScalar]


class SelectorQuantifierKind(str, Enum):
    """Quantified collection selectors."""

    EXISTS = "exists"
    FOR_ALL = "for_all"
    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    EXACTLY = "exactly"


class SelectorAggregationFunction(str, Enum):
    """Aggregate functions supported inside selector predicates."""

    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"


class SelectorTemporalOperator(str, Enum):
    """Temporal wrappers for selector predicates."""

    EVER = "ever"
    ALWAYS_WITHIN = "always_within"
    EVENTUALLY_WITHIN = "eventually_within"
    HISTORICALLY_WITHIN = "historically_within"


class SelectorPredicate(KernelModel):
    """Selector predicate public type."""

    kind: Literal["predicate"] = "predicate"
    field: str = Field(..., max_length=64)
    operator: SelectorOperator
    value: SelectorValue

    @model_validator(mode="after")
    def validate_value(self) -> SelectorPredicate:
        validate_selector_predicate_shape(
            field=self.field,
            operator=self.operator,
            value=self.value,
        )
        return self


class SelectorAll(KernelModel):
    """Selector all public type."""

    kind: Literal["all_of"] = "all_of"
    clauses: list[SelectorExpr] = Field(..., min_length=1, max_length=32)


class SelectorAny(KernelModel):
    """Selector any public type."""

    kind: Literal["any_of"] = "any_of"
    clauses: list[SelectorExpr] = Field(..., min_length=1, max_length=32)


class SelectorNot(KernelModel):
    """Selector not public type."""

    kind: Literal["not"] = "not"
    clause: SelectorExpr


class SelectorQuantifier(KernelModel):
    """Quantified selector over a repeated/collection field."""

    kind: Literal["quantifier"] = "quantifier"
    quantifier: SelectorQuantifierKind
    collection_field: str = Field(..., max_length=128)
    clause: SelectorExpr
    threshold: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def validate_quantifier(self) -> SelectorQuantifier:
        validate_selector_quantifier_shape(
            collection_field=self.collection_field,
            quantifier=self.quantifier,
            threshold=self.threshold,
        )
        return self


class SelectorAggregate(KernelModel):
    """Aggregate selector predicate over a collection."""

    kind: Literal["aggregate"] = "aggregate"
    aggregation: SelectorAggregationFunction
    collection_field: str = Field(..., max_length=128)
    value_field: str | None = Field(None, max_length=128)
    where: SelectorExpr | None = None
    operator: SelectorOperator
    value: SelectorScalar

    @model_validator(mode="after")
    def validate_aggregate(self) -> SelectorAggregate:
        validate_selector_aggregation_shape(
            collection_field=self.collection_field,
            aggregation=self.aggregation,
            value_field=self.value_field,
            operator=self.operator,
            value=self.value,
        )
        return self


class SelectorTemporalPredicate(KernelModel):
    """Temporal wrapper around a selector clause."""

    kind: Literal["temporal"] = "temporal"
    temporal_operator: SelectorTemporalOperator
    clause: SelectorExpr
    lower_bound: Annotated[int, Field(ge=0)] = 0
    upper_bound: Annotated[int, Field(ge=0)] | None = None
    clock_field: str | None = Field(None, max_length=128)

    @model_validator(mode="after")
    def validate_temporal(self) -> SelectorTemporalPredicate:
        validate_selector_temporal_shape(
            clock_field=self.clock_field,
            lower_bound=self.lower_bound,
            upper_bound=self.upper_bound,
        )
        if self.temporal_operator is SelectorTemporalOperator.EVER:
            if self.lower_bound != 0 or self.upper_bound is not None:
                raise ValueError("temporal operator 'ever' does not allow bounds")
        elif self.upper_bound is None:
            raise ValueError(
                f"temporal operator '{self.temporal_operator.value}' requires upper_bound"
            )
        return self


SelectorExpr = Annotated[
    SelectorPredicate
    | SelectorAll
    | SelectorAny
    | SelectorNot
    | SelectorQuantifier
    | SelectorAggregate
    | SelectorTemporalPredicate,
    Field(discriminator="kind"),
]


__all__ = [
    "SelectorAggregate",
    "SelectorAggregationFunction",
    "SelectorAll",
    "SelectorAny",
    "SelectorExpr",
    "SelectorNot",
    "SelectorPredicate",
    "SelectorQuantifier",
    "SelectorQuantifierKind",
    "SelectorScalar",
    "SelectorTemporalOperator",
    "SelectorTemporalPredicate",
    "SelectorValue",
]
