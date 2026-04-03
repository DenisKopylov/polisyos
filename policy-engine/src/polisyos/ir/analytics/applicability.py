"""Public analytics applicability module API."""
from __future__ import annotations

import re

from pydantic import Field, field_validator, model_validator

from polisyos.ir.kernel.base import ID_PATTERN, KernelModel

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"

_ID_RE = re.compile(ID_PATTERN)


class TimeWindow(KernelModel):
    """Time window public type."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    valid_from: str | None = None
    valid_to: str | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "TimeWindow":
        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_to < self.valid_from:
                raise ValueError("valid_to must be >= valid_from")
        return self


class IdSelector(KernelModel):
    """ID selector public type."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    any_of: list[str] = Field(default_factory=list)
    all_of: list[str] = Field(default_factory=list)
    none_of: list[str] = Field(default_factory=list)

    @field_validator("any_of", "all_of", "none_of")
    @classmethod
    def validate_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate ids are not allowed")
        for value in values:
            if _ID_RE.match(value) is None:
                raise ValueError(f"id '{value}' does not match {ID_PATTERN}")
        return values


class ApplicabilityEntitySelector(KernelModel):
    """Applicability entity selector public type."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    actors: IdSelector = Field(default_factory=IdSelector)
    concepts: IdSelector = Field(default_factory=IdSelector)


class ConditionExpr(KernelModel):
    """Condition expr public type."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    language: str = Field(..., min_length=1)
    expr: str = Field(..., min_length=1)
    notes: list[str] = Field(default_factory=list)
    refs: dict[str, str] = Field(default_factory=dict)


class NormApplicability(KernelModel):
    """Norm applicability public type."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    jurisdiction: IdSelector = Field(default_factory=IdSelector)
    time: TimeWindow = Field(default_factory=TimeWindow)
    subject: ApplicabilityEntitySelector = Field(default_factory=ApplicabilityEntitySelector)
    object: ApplicabilityEntitySelector = Field(default_factory=ApplicabilityEntitySelector)
    conditions: list[ConditionExpr] = Field(default_factory=list)
    exceptions: list["NormApplicability"] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


__all__ = [
    "ApplicabilityEntitySelector",
    "ConditionExpr",
    "IdSelector",
    "NormApplicability",
    "TimeWindow",
]
