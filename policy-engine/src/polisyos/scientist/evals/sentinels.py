"""Sentinel challenge admission contracts for adversarial eval packs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evals.challenge_factory import ChallengeStatus, GeneratedChallenge

__all__ = [
    "SentinelChallengeCase",
    "SentinelChallengeKind",
    "build_sentinel_challenge_case",
    "validate_sentinel_hidden_admission",
]


class SentinelChallengeKind(StrEnum):
    """Sentinel challenge roles used by the factory."""

    CANARY = "canary"
    INVARIANT = "invariant"
    DECOY = "decoy"
    REGRESSION = "regression"


class SentinelChallengeCase(BaseModel):
    """Metadata for a sentinel case before benchmark admission."""

    model_config = ConfigDict(extra="forbid")

    sentinel_id: str = Field(min_length=1)
    kind: SentinelChallengeKind
    challenge_ref: ArtifactRef
    expected_detection: str = Field(min_length=1)
    admission_status: ChallengeStatus = ChallengeStatus.REVIEW_REQUIRED
    leakage_risk: Literal["low", "medium", "high"] = "medium"
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_admission(self) -> SentinelChallengeCase:
        validate_sentinel_hidden_admission(self)
        return self


def build_sentinel_challenge_case(
    challenge: GeneratedChallenge,
    *,
    challenge_ref: ArtifactRef | None = None,
    kind: SentinelChallengeKind = SentinelChallengeKind.REGRESSION,
    expected_detection: str | None = None,
) -> SentinelChallengeCase:
    """Build sentinel metadata from a reviewed generated challenge."""

    return SentinelChallengeCase(
        sentinel_id=f"sentinel_{challenge.challenge_id}",
        kind=kind,
        challenge_ref=challenge_ref or challenge.prompt_or_case_ref,
        expected_detection=expected_detection or challenge.expected_failure_mode,
        admission_status=challenge.status,
        leakage_risk=challenge.leakage_risk,
        reviewer_refs=list(challenge.reviewer_refs),
        metadata={
            "source_challenge_id": challenge.challenge_id,
            "challenge_class": challenge.challenge_class,
        },
    )


def validate_sentinel_hidden_admission(case: SentinelChallengeCase) -> None:
    """Reject hidden sentinel admission without reviewers or with high leakage risk."""

    if case.admission_status is not ChallengeStatus.APPROVED_FOR_HIDDEN:
        return
    if not case.reviewer_refs:
        raise ValueError("hidden sentinel admission requires reviewer_refs")
    if case.leakage_risk == "high":
        raise ValueError("high-leakage sentinel cannot be admitted as hidden")
