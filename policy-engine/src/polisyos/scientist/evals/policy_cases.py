"""Policy-domain eval case pack fixtures for Scientist benchmark authority."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef

__all__ = [
    "PolicyCaseDimension",
    "PolicyDomainEvalCase",
    "PolicyDomainEvalPack",
    "default_policy_domain_eval_pack",
]


class PolicyCaseDimension(StrEnum):
    """Policy-design dimensions evaluated by Phase 1.5 case packs."""

    PARETO = "pareto"
    CONSTRAINTS = "constraints"
    WELFARE = "welfare"
    EQUITY = "equity"
    LEGAL_FEASIBILITY = "legal_feasibility"


class PolicyDomainEvalCase(BaseModel):
    """One domain-local policy eval case fixture."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    family: str = Field(default="policy_design", min_length=1)
    dimensions: list[PolicyCaseDimension] = Field(default_factory=list)
    prompt_ref: ArtifactRef | None = None
    expected_outcome_ref: ArtifactRef | None = None
    risk_tier: str = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyDomainEvalPack(BaseModel):
    """Small fixture contract for policy-domain benchmark packs."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(min_length=1)
    revision: str = Field(default="1.0", min_length=1)
    cases: list[PolicyDomainEvalCase] = Field(default_factory=list)
    hidden_holdout_ref: ArtifactRef | None = None

    @property
    def covered_dimensions(self) -> set[PolicyCaseDimension]:
        """Return all policy dimensions represented by this pack."""

        return {dimension for case in self.cases for dimension in case.dimensions}


def default_policy_domain_eval_pack() -> PolicyDomainEvalPack:
    """Return a no-data fixture pack that documents required policy dimensions."""

    return PolicyDomainEvalPack(
        pack_id="policy_domain_eval_pack_v1",
        cases=[
            PolicyDomainEvalCase(
                case_id="policy_design_core_fixture",
                dimensions=list(PolicyCaseDimension),
                risk_tier="high",
            )
        ],
    )
