"""Rotating, sentinel and adversarial challenge-pack metadata."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef

__all__ = [
    "ChallengePack",
    "ChallengePackKind",
    "challenge_pack_is_expired",
    "next_rotation_due_at",
]


class ChallengePackKind(StrEnum):
    """Challenge pack kinds tracked by benchmark authority."""

    ROTATING = "rotating_challenge"
    SENTINEL = "sentinel"
    ADVERSARIAL = "adversarial"


class ChallengePack(BaseModel):
    """Metadata for an offline challenge pack."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(min_length=1)
    kind: ChallengePackKind
    artifact_ref: ArtifactRef
    rotation_group: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rotation_days: int = Field(default=30, ge=1)
    lineage_key: str | None = None
    source_challenge_ids: list[str] = Field(default_factory=list)
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


def next_rotation_due_at(pack: ChallengePack) -> datetime:
    """Return when a rotating challenge pack must be refreshed."""

    return pack.created_at.astimezone(UTC) + timedelta(days=pack.rotation_days)


def challenge_pack_is_expired(
    pack: ChallengePack,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when the challenge pack is past its rotation window."""

    active_now = (now or datetime.now(UTC)).astimezone(UTC)
    return next_rotation_due_at(pack) < active_now
