from __future__ import annotations

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel


class TrustPolicySpec(KernelModel):
    policy_id: str = Field(..., pattern=ID_PATTERN)
    description: str | None = Field(None, max_length=200)


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
