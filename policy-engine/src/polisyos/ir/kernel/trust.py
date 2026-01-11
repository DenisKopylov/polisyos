from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel


class TrustPolicySpec(KernelModel):
    policy_id: str = Field(..., pattern=ID_PATTERN)
    description: str | None = Field(None, max_length=200)
    min_confidence: float | None = None
    conflict_policy: Literal["optimistic", "pessimistic"] | None = None
    two_pass_compare: bool = False
    thresholds: dict[str, float] | None = None


class TrustRegistry(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    policies: dict[str, TrustPolicySpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_policies(self) -> "TrustRegistry":
        for key, spec in self.policies.items():
            if not key or not isinstance(key, str):
                raise ValueError("trust policy id must be a non-empty string")
            if key != spec.policy_id:
                raise ValueError(f"trust policy id mismatch: '{key}' != '{spec.policy_id}'")
        return self


DEFAULT_TRUST_REGISTRY = TrustRegistry(policies={}, notes=["empty"])
