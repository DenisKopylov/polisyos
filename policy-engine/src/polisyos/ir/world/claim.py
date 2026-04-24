"""Public world claim module API."""

from __future__ import annotations

import re
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BeforeValidator, Field, field_validator, model_validator

from polisyos.ir.kernel.base import (
    ARTIFACT_ID_PATTERN,
    ID_PATTERN,
    KernelModel,
    reject_float,
    reject_floats_deep,
)

if TYPE_CHECKING:
    from datetime import datetime

    from polisyos.ir.citations import CitationRef
else:
    from datetime import datetime

    from polisyos.ir.citations import CitationRef

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"

_ARTIFACT_RE = re.compile(ARTIFACT_ID_PATTERN)

DecimalZeroToOne = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0, le=1)]
DecimalValue = Annotated[Decimal, BeforeValidator(reject_float)]


class ClaimSourceKind(str, Enum):
    """Claim source kind public type."""

    DOC = "doc"
    DATASET = "dataset"
    SIMULATION = "simulation"
    EXPERT = "expert"
    DERIVED = "derived"


class Claim(KernelModel):
    """Claim public type."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    claim_id: str = Field(..., pattern=ID_PATTERN)
    predicate_id: str = Field(..., pattern=ID_PATTERN)
    subject_id: str | None = Field(None, pattern=ID_PATTERN)
    subject_text: str | None = None
    value_text: str
    value_decimal: DecimalValue | None = None
    unit_id: str | None = Field(None, pattern=ID_PATTERN)
    confidence: DecimalZeroToOne
    source_kind: ClaimSourceKind
    citations: list[CitationRef] = Field(default_factory=list)
    source_artifacts: list[str] = Field(default_factory=list)
    jurisdiction: str | None = None
    domain: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    qualifiers: Annotated[dict[str, str | int | bool], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )
    props: Annotated[dict[str, Any], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )

    @model_validator(mode="before")
    @classmethod
    def reject_floats(cls, value: Any) -> Any:
        reject_floats_deep(value)
        return value

    @field_validator("source_artifacts")
    @classmethod
    def validate_source_artifacts(cls, values: list[str]) -> list[str]:
        for value in values:
            if _ARTIFACT_RE.fullmatch(value) is None:
                raise ValueError(f"artifact_id '{value}' does not match {ARTIFACT_ID_PATTERN}")
        return values

    @model_validator(mode="after")
    def validate_claim(self) -> Claim:
        if self.subject_id is None and self.subject_text is None:
            raise ValueError("claim requires subject_id or subject_text")
        if self.source_kind == ClaimSourceKind.DOC:
            if len(self.citations) == 0:
                raise ValueError("doc claims require citations")
        else:
            if len(self.source_artifacts) == 0:
                raise ValueError("non-doc claims require source_artifacts")
        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_to < self.valid_from:
                raise ValueError("valid_to must be >= valid_from")
        return self


__all__ = [
    "Claim",
    "ClaimSourceKind",
]
