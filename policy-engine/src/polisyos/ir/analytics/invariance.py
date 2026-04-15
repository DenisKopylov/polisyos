"""Multi-environment and invariance-learning contracts."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._validation import ensure_finite_numeric, ensure_unique_ids


class EnvironmentShiftType(str, Enum):
    """Distribution shift classes observed across environments."""

    COVARIATE = "covariate"
    INTERVENTIONAL = "interventional"
    SELECTION = "selection"
    TEMPORAL = "temporal"


class InvarianceMethod(str, Enum):
    """Frontier multi-environment causal methods."""

    ICP = "icp"
    IRM = "irm"
    ANCHOR_REGRESSION = "anchor_regression"
    ENVIRONMENT_AWARE_DISCOVERY = "environment_aware_discovery"


class InvarianceVerdict(str, Enum):
    """Outcome of an invariance evaluation run."""

    ACCEPTED = "accepted"
    PARTIAL = "partial"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class EnvironmentSpec(BaseModel):
    """One observed environment or deployment regime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    environment_id: str = Field(min_length=1)
    shift_type: EnvironmentShiftType
    context_features: tuple[str, ...] = ()
    role: str = Field(default="source", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_environment(self) -> "EnvironmentSpec":
        ensure_unique_ids(
            self.context_features,
            key_fn=lambda item: item,
            label="environment context_feature",
        )
        return self


class InvariantMechanismHypothesis(BaseModel):
    """One hypothesis about an invariant mechanism across environments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str = Field(min_length=1)
    target_variable: str = Field(min_length=1)
    invariant_parents: tuple[str, ...] = ()
    violating_environments: tuple[str, ...] = ()
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_hypothesis(self) -> "InvariantMechanismHypothesis":
        ensure_unique_ids(
            self.invariant_parents,
            key_fn=lambda item: item,
            label="invariant parent",
        )
        ensure_unique_ids(
            self.violating_environments,
            key_fn=lambda item: item,
            label="violating environment",
        )
        if self.score is not None:
            ensure_finite_numeric(self.score, field_name=f"{self.hypothesis_id}.score")
        return self


class MultiEnvironmentCausalContract(BaseModel):
    """Contract surface for multi-environment causal identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    contract_id: str = Field(min_length=1)
    method: InvarianceMethod
    target_variable: str = Field(min_length=1)
    intervention_field: str | None = None
    environments: list[EnvironmentSpec] = Field(..., min_length=1)
    assumptions: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_contract(self) -> "MultiEnvironmentCausalContract":
        ensure_unique_ids(
            self.environments,
            key_fn=lambda item: item.environment_id,
            label="environment_id",
        )
        return self


class InvarianceResult(BaseModel):
    """Frozen result contract for multi-environment invariance analysis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    contract_id: str = Field(min_length=1)
    method: InvarianceMethod
    verdict: InvarianceVerdict
    hypotheses: list[InvariantMechanismHypothesis] = Field(default_factory=list)
    accepted_hypothesis_ids: tuple[str, ...] = ()
    rejected_hypothesis_ids: tuple[str, ...] = ()
    environment_risks: dict[str, float] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> "InvarianceResult":
        ensure_unique_ids(
            self.hypotheses,
            key_fn=lambda item: item.hypothesis_id,
            label="hypothesis_id",
        )
        hypothesis_ids = {item.hypothesis_id for item in self.hypotheses}
        missing_accepted = set(self.accepted_hypothesis_ids) - hypothesis_ids
        missing_rejected = set(self.rejected_hypothesis_ids) - hypothesis_ids
        if missing_accepted:
            raise ValueError(
                f"accepted_hypothesis_ids reference unknown hypotheses {sorted(missing_accepted)}"
            )
        if missing_rejected:
            raise ValueError(
                f"rejected_hypothesis_ids reference unknown hypotheses {sorted(missing_rejected)}"
            )
        shared = set(self.accepted_hypothesis_ids) & set(self.rejected_hypothesis_ids)
        if shared:
            raise ValueError(
                f"accepted_hypothesis_ids and rejected_hypothesis_ids overlap {sorted(shared)}"
            )
        for environment_id, risk in self.environment_risks.items():
            if not environment_id.strip():
                raise ValueError("environment_risks keys must be non-empty")
            ensure_finite_numeric(risk, field_name=f"environment_risks.{environment_id}")
        return self


__all__ = [
    "EnvironmentShiftType",
    "EnvironmentSpec",
    "InvarianceMethod",
    "InvarianceResult",
    "InvarianceVerdict",
    "InvariantMechanismHypothesis",
    "MultiEnvironmentCausalContract",
]
