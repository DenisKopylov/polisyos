"""Public world trust module API."""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Annotated

from polisyos.ir.kernel.base import ID_PATTERN, KernelModel, reject_float, reject_floats_deep
from polisyos.ir.world.ids import trust_assessment_id_from_payload

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"

DecimalZeroToOne = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0, le=1)]


class TrustTier(str, Enum):
    """Trust tier public type."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TrustAssessment(KernelModel):
    """Trust assessment public type."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    trust_assessment_id: str = Field(..., pattern=ID_PATTERN)
    policy_id: str = Field(..., pattern=ID_PATTERN)
    algorithm_version: str
    target_world_id: str = Field(..., pattern=ID_PATTERN)
    score: DecimalZeroToOne
    tier: TrustTier
    features: Annotated[dict[str, str | int | bool], BeforeValidator(reject_floats_deep)] = (
        Field(default_factory=dict)
    )
    rationale: Annotated[dict[str, Any] | list[Any], BeforeValidator(reject_floats_deep)] = (
        Field(default_factory=dict)
    )
    props: Annotated[dict[str, Any], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )

    @model_validator(mode="before")
    @classmethod
    def reject_floats(cls, value: Any) -> Any:
        reject_floats_deep(value)
        return value

    @model_validator(mode="after")
    def validate_id(self) -> "TrustAssessment":
        payload = {
            "policy_id": self.policy_id,
            "algorithm_version": self.algorithm_version,
            "target_world_id": self.target_world_id,
            "score": self.score,
            "tier": self.tier.value,
            "features": self.features,
            "rationale": self.rationale,
            "props": self.props,
        }
        expected = trust_assessment_id_from_payload(payload=payload)
        if self.trust_assessment_id != expected:
            raise ValueError(
                "trust_assessment_id mismatch: "
                f"{self.trust_assessment_id} != {expected}"
            )
        return self


__all__ = [
    "TrustAssessment",
    "TrustTier",
]
