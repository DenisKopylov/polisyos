"""Rotating challenge-pack lifecycle, freshness and lineage helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evals.challenge_factory import GeneratedChallenge
from polisyos.scientist.evals.challenge_packs import ChallengePack, ChallengePackKind
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistryEntry

__all__ = [
    "ChallengePackLineage",
    "RotatingChallengePackStatus",
    "build_challenge_pack_lineage",
    "challenge_lineage_from_registry_entry",
    "dedupe_challenge_lineage",
    "lineage_is_fresh",
    "validate_fresh_rotating_challenge_evidence",
]


class RotatingChallengePackStatus(StrEnum):
    """Rotation lifecycle status for challenge-pack evidence."""

    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    EXPIRED = "expired"
    RETIRED = "retired"


class ChallengePackLineage(BaseModel):
    """Lineage summary tracked by benchmark authority metadata."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    pack_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    pack_ref: ArtifactRef | None = None
    source_challenge_ids: list[str] = Field(default_factory=list)
    source_failure_ref_ids: list[str] = Field(default_factory=list)
    challenge_classes: list[str] = Field(default_factory=list)
    reviewer_ref_ids: list[str] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=list)
    parent_pack_refs: list[ArtifactRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    revision: str | None = None
    status: RotatingChallengePackStatus = RotatingChallengePackStatus.PENDING_REVIEW
    lineage_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_lineage_key(self) -> ChallengePackLineage:
        if self.lineage_key is None:
            self.lineage_key = _stable_lineage_key(
                self.kind,
                self.pack_id,
                self.source_challenge_ids,
                self.source_failure_ref_ids,
                self.parent_pack_refs,
            )
        return self


def build_challenge_pack_lineage(
    pack: ChallengePack,
    challenges: Iterable[GeneratedChallenge],
    *,
    parent_pack_refs: Iterable[ArtifactRef] = (),
    revision: str | None = None,
    status: RotatingChallengePackStatus = RotatingChallengePackStatus.ACTIVE,
) -> ChallengePackLineage:
    """Build lineage metadata from a reviewed challenge pack."""

    challenge_list = list(challenges)
    source_failure_ref_ids = sorted(
        {
            str(ref.artifact_id)
            for challenge in challenge_list
            for ref in challenge.source_failure_refs
        }
    )
    return ChallengePackLineage(
        pack_id=pack.pack_id,
        kind=pack.kind.value,
        pack_ref=pack.artifact_ref,
        source_challenge_ids=sorted({challenge.challenge_id for challenge in challenge_list}),
        source_failure_ref_ids=source_failure_ref_ids,
        parent_pack_refs=list(parent_pack_refs),
        created_at=pack.created_at,
        expires_at=pack.created_at.astimezone(UTC) + timedelta(days=pack.rotation_days),
        revision=revision,
        status=status,
    )


def challenge_lineage_from_registry_entry(
    entry: BenchmarkRegistryEntry,
) -> ChallengePackLineage | None:
    """Reconstruct challenge-pack lineage from registry metadata."""

    raw = (entry.metadata or {}).get("challenge_pack_lineage")
    if not isinstance(raw, dict):
        return None
    payload = dict(raw)
    payload.setdefault("pack_id", entry.suite_id or str(entry.artifact_ref.artifact_id))
    payload.setdefault("kind", entry.split_type)
    payload.setdefault("pack_ref", entry.artifact_ref)
    payload.setdefault("created_at", entry.created_at)
    payload.setdefault("revision", entry.benchmark_revision)
    expires_at = (entry.metadata or {}).get("expires_at")
    if expires_at is not None:
        payload.setdefault("expires_at", expires_at)
    return ChallengePackLineage.model_validate(payload)


def dedupe_challenge_lineage(
    lineages: Iterable[ChallengePackLineage],
) -> list[ChallengePackLineage]:
    """Deduplicate lineage records by lineage key, keeping the newest record."""

    by_key: dict[str, ChallengePackLineage] = {}
    for lineage in lineages:
        key = lineage.lineage_key or lineage.pack_id
        existing = by_key.get(key)
        if existing is None or lineage.created_at > existing.created_at:
            by_key[key] = lineage
    return sorted(by_key.values(), key=lambda item: item.created_at, reverse=True)


def lineage_is_fresh(
    lineage: ChallengePackLineage,
    *,
    now: datetime | None = None,
    freshness_days: int = 30,
) -> bool:
    """Return True when a rotating lineage is active and within freshness window."""

    if lineage.kind != ChallengePackKind.ROTATING.value:
        return False
    if lineage.status in {
        RotatingChallengePackStatus.EXPIRED,
        RotatingChallengePackStatus.RETIRED,
        RotatingChallengePackStatus.PENDING_REVIEW,
    }:
        return False
    active_now = (now or datetime.now(UTC)).astimezone(UTC)
    if lineage.expires_at is not None and lineage.expires_at.astimezone(UTC) < active_now:
        return False
    return lineage.created_at.astimezone(UTC) + timedelta(days=freshness_days) >= active_now


def validate_fresh_rotating_challenge_evidence(
    lineages: Iterable[ChallengePackLineage],
    *,
    near_frontier: bool,
    now: datetime | None = None,
    freshness_days: int = 30,
) -> list[str]:
    """Return blockers for near-frontier promotion lacking fresh rotating challenges."""

    if not near_frontier:
        return []
    deduped = dedupe_challenge_lineage(lineages)
    rotating = [item for item in deduped if item.kind == ChallengePackKind.ROTATING.value]
    if not rotating:
        return ["fresh_rotating_challenge_evidence_missing"]
    fresh = [
        item
        for item in rotating
        if lineage_is_fresh(item, now=now, freshness_days=freshness_days)
    ]
    if fresh:
        return []
    return [f"rotating_challenge_expired:{item.pack_id}" for item in rotating]


def _stable_lineage_key(
    kind: str,
    pack_id: str,
    source_challenge_ids: list[str],
    source_failure_ref_ids: list[str],
    parent_pack_refs: list[ArtifactRef],
) -> str:
    material = "|".join(
        [
            kind,
            pack_id,
            ",".join(sorted(source_challenge_ids)),
            ",".join(sorted(source_failure_ref_ids)),
            ",".join(sorted(str(ref.artifact_id) for ref in parent_pack_refs)),
        ]
    )
    return "lineage_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
