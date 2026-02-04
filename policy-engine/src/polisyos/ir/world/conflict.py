from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Literal

from pydantic import BeforeValidator, Field, field_validator, model_validator
from typing_extensions import Annotated

from polisyos.ir.kernel.base import (
    ARTIFACT_ID_PATTERN,
    ID_PATTERN,
    KernelModel,
    reject_float,
    reject_floats_deep,
)
from polisyos.ir.world.ids import conflict_set_id_from_key

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"
DECIMAL_STRING_PATTERN = r"^-?\d+(?:\.\d+)?$"

WorldID = Annotated[str, Field(pattern=ID_PATTERN)]
DecimalZeroToOne = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0, le=1)]


class ConflictKind(str, Enum):
    VALUE_MISMATCH = "value_mismatch"
    UNIT_MISMATCH = "unit_mismatch"
    DEFINITION_MISMATCH = "definition_mismatch"
    TEMPORAL_MISMATCH = "temporal_mismatch"
    DUPLICATE = "duplicate"


def _ensure_sorted_unique(values: list[str], *, field: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique ids")
    if values != sorted(values):
        raise ValueError(f"{field} must be sorted")
    return values


def _validate_decimal_string(value: str) -> str:
    try:
        Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid decimal string: {value}") from exc
    return value


class ConflictSetResolution(KernelModel):
    winner_claim_id: WorldID
    policy_id: WorldID
    confidence: DecimalZeroToOne
    rationale: str
    resolution_artifact_id: str = Field(..., pattern=ARTIFACT_ID_PATTERN)


class ConflictSet(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    conflict_set_id: WorldID
    conflict_key: str = Field(..., pattern=SHA256_HEX_PATTERN)
    conflict_kind: ConflictKind
    member_claim_ids: list[WorldID] = Field(..., min_length=2)
    resolution: ConflictSetResolution | None = None
    props: Annotated[dict[str, Any], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )

    @model_validator(mode="before")
    @classmethod
    def reject_floats(cls, value: Any) -> Any:
        reject_floats_deep(value)
        return value

    @field_validator("member_claim_ids")
    @classmethod
    def validate_member_claim_ids(cls, values: list[str]) -> list[str]:
        return _ensure_sorted_unique(values, field="member_claim_ids")

    @model_validator(mode="after")
    def validate_conflict_set_id(self) -> "ConflictSet":
        expected = conflict_set_id_from_key(conflict_key=self.conflict_key)
        if self.conflict_set_id != expected:
            raise ValueError(
                f"conflict_set_id mismatch: {self.conflict_set_id} != {expected}"
            )
        return self


class ConflictResolutionCandidate(KernelModel):
    claim_id: WorldID
    score_total: str = Field(..., pattern=DECIMAL_STRING_PATTERN)
    score_breakdown: Annotated[
        dict[str, str],
        BeforeValidator(reject_floats_deep),
    ] = Field(default_factory=dict)

    @field_validator("score_total")
    @classmethod
    def validate_score_total(cls, value: str) -> str:
        return _validate_decimal_string(value)

    @field_validator("score_breakdown")
    @classmethod
    def validate_score_breakdown(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key in sorted(value):
            normalized[key] = _validate_decimal_string(str(value[key]))
        return normalized


class ConflictResolutionInputs(KernelModel):
    claim_ids: list[WorldID] = Field(default_factory=list)
    doc_version_ids: list[WorldID] = Field(default_factory=list)
    trust_assessment_ids: list[WorldID] = Field(default_factory=list)

    @field_validator("claim_ids", "doc_version_ids", "trust_assessment_ids")
    @classmethod
    def validate_sorted_unique(cls, values: list[str], info) -> list[str]:
        return _ensure_sorted_unique(values, field=str(info.field_name))


class ConflictResolution(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    conflict_set_id: WorldID
    policy_id: WorldID
    algorithm_version: str
    candidates: list[ConflictResolutionCandidate] = Field(..., min_length=1)
    winner_claim_id: WorldID
    tie_break_rule: Literal["lexicographic_claim_id"] = "lexicographic_claim_id"
    inputs: ConflictResolutionInputs
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_floats(cls, value: Any) -> Any:
        reject_floats_deep(value)
        return value

    @model_validator(mode="after")
    def validate_ranking(self) -> "ConflictResolution":
        ranked = sorted(
            self.candidates,
            key=lambda c: (-Decimal(c.score_total), c.claim_id),
        )
        if [candidate.claim_id for candidate in ranked] != [
            candidate.claim_id for candidate in self.candidates
        ]:
            raise ValueError("candidates must be sorted by score_total desc, claim_id asc")
        if self.winner_claim_id != self.candidates[0].claim_id:
            raise ValueError("winner_claim_id must match first candidate in ranking")
        return self


__all__ = [
    "ConflictKind",
    "ConflictResolution",
    "ConflictResolutionCandidate",
    "ConflictResolutionInputs",
    "ConflictSet",
    "ConflictSetResolution",
]
