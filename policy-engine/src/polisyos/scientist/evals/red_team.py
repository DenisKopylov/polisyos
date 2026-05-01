"""Red-team scenario registry for generated challenge packs."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evals.challenge_factory import (
    REQUIRED_CHALLENGE_CLASSES,
    ChallengeClass,
    ChallengeStatus,
)

__all__ = [
    "RedTeamRiskTag",
    "RedTeamScenario",
    "default_red_team_scenario_registry",
    "red_team_registry_missing_classes",
]


class RedTeamRiskTag(StrEnum):
    """Risk tags used to route red-team cases to review and benchmark authority."""

    CITATION_FAITHFULNESS = "citation_faithfulness"
    TEMPORAL_STALENESS = "temporal_staleness"
    CAUSAL_ASSUMPTION = "causal_assumption"
    FAIRNESS = "fairness"
    LEGAL = "legal"
    STRATEGIC_RESPONSE = "strategic_response"
    BUDGET = "budget"
    HUMAN_OVERSIGHT = "human_oversight"


class RedTeamScenario(BaseModel):
    """Reviewed red-team scenario metadata."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    challenge_class: str = Field(min_length=1)
    risk_tags: list[RedTeamRiskTag] = Field(default_factory=list)
    prompt_or_case_ref: ArtifactRef | None = None
    expected_failure_mode: str = Field(min_length=1)
    status: ChallengeStatus = ChallengeStatus.REVIEW_REQUIRED
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_tags(self) -> RedTeamScenario:
        if not self.risk_tags:
            raise ValueError("RedTeamScenario requires risk_tags")
        return self


def default_red_team_scenario_registry() -> list[RedTeamScenario]:
    """Return the v1 red-team registry covering all required challenge classes."""

    tag_map: dict[ChallengeClass, list[RedTeamRiskTag]] = {
        ChallengeClass.SOURCE_CONTRADICTION: [RedTeamRiskTag.CITATION_FAITHFULNESS],
        ChallengeClass.STALE_SOURCE: [RedTeamRiskTag.TEMPORAL_STALENESS],
        ChallengeClass.FORGED_CITATION: [RedTeamRiskTag.CITATION_FAITHFULNESS],
        ChallengeClass.MISSING_TRANSPORTABILITY_ASSUMPTION: [RedTeamRiskTag.CAUSAL_ASSUMPTION],
        ChallengeClass.HIDDEN_CONFOUNDING_PROXY_ASSUMPTION_TRAP: [RedTeamRiskTag.CAUSAL_ASSUMPTION],
        ChallengeClass.FAIRNESS_THRESHOLD_REVERSAL: [RedTeamRiskTag.FAIRNESS],
        ChallengeClass.LEGAL_EXCEPTION: [RedTeamRiskTag.LEGAL],
        ChallengeClass.POLICY_GAMING_STRATEGIC_RESPONSE: [RedTeamRiskTag.STRATEGIC_RESPONSE],
        ChallengeClass.BUDGET_INFEASIBILITY: [RedTeamRiskTag.BUDGET],
        ChallengeClass.AMBIGUOUS_HUMAN_REVIEW_INSTRUCTION: [RedTeamRiskTag.HUMAN_OVERSIGHT],
    }
    return [
        RedTeamScenario(
            scenario_id=f"red_team_{challenge_class.value}",
            challenge_class=challenge_class.value,
            risk_tags=tags,
            expected_failure_mode=f"Probe {challenge_class.value} before promotion.",
        )
        for challenge_class, tags in tag_map.items()
    ]


def red_team_registry_missing_classes(
    scenarios: list[RedTeamScenario],
) -> list[str]:
    """Return required challenge classes not covered by a red-team registry."""

    covered = {scenario.challenge_class for scenario in scenarios}
    return sorted(set(REQUIRED_CHALLENGE_CLASSES) - covered)
