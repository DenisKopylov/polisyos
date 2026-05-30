"""Append-only claim lifecycle contracts for Scientist Claim Ledger v2."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef  # noqa: TC001
from polisyos.scientist.evidence.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
)

CLAIM_LEDGER_V2_FLAG = "scientist.best_in_class.wave2.phase2_1.claim_ledger_v2"
REQUIRE_LIFECYCLE_EVENTS_FLAG = (
    "scientist.best_in_class.wave2.phase2_1.require_lifecycle_events"
)


class ClaimLifecycleAction(str, Enum):
    """Lifecycle actions recorded for a claim without mutating old artifacts."""

    CREATED = "created"
    UPDATED_SUPPORT = "updated_support"
    UPDATED_READINESS = "updated_readiness"
    MERGED = "merged"
    SPLIT = "split"
    SUPERSEDED = "superseded"
    BLOCKED = "blocked"
    UNBLOCKED = "unblocked"
    MARKED_STALE = "marked_stale"
    REVIEW_REQUIRED = "review_required"
    REISSUED = "reissued"
    WITHDRAWN = "withdrawn"
    REVIEWED = "reviewed"
    INVALIDATED = "invalidated"


class ClaimLifecycleEvent(BaseModel):
    """One append-only lifecycle event for a claim."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    action: ClaimLifecycleAction
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    previous_claim_ref: ArtifactRef | None = None
    next_claim_ref: ArtifactRef | None = None
    evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "claim_id", "run_id", "actor_id", "reason")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim lifecycle text fields cannot be blank")
        return value

    @model_validator(mode="after")
    def _validate_action_metadata(self) -> ClaimLifecycleEvent:
        if self.action is ClaimLifecycleAction.MERGED:
            _require_metadata_list(self.metadata, "source_claim_ids", self.action)
            _require_metadata_list(self.metadata, "target_claim_ids", self.action)
        if self.action is ClaimLifecycleAction.SPLIT:
            source_ids = _require_metadata_list(
                self.metadata,
                "source_claim_ids",
                self.action,
            )
            _require_metadata_list(self.metadata, "target_claim_ids", self.action)
            if self.claim_id not in source_ids:
                raise ValueError("split events must preserve the source claim_id")
        if self.action is ClaimLifecycleAction.SUPERSEDED and (
            not self.metadata.get("superseded_by_claim_id")
            and self.next_claim_ref is None
        ):
            raise ValueError("superseded events require a superseding claim id or ref")
        return self


class AppendOnlyClaimLedger(BaseModel):
    """Claim Ledger v2 sidecar with current claims and immutable lifecycle events."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.0"] = "2.0"
    run_id: str = Field(min_length=1)
    base_ledger_ref: ArtifactRef | None = None
    current_claims: list[ClaimRecord] = Field(default_factory=list)
    events: list[ClaimLifecycleEvent] = Field(default_factory=list)
    retention_policy: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_append_only_contract(self) -> AppendOnlyClaimLedger:
        claim_ids = [claim.claim_id for claim in self.current_claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("AppendOnlyClaimLedger current_claims must have unique ids")
        if any(claim.run_id != self.run_id for claim in self.current_claims):
            raise ValueError("AppendOnlyClaimLedger claims must share the ledger run_id")

        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("AppendOnlyClaimLedger events must have unique event_ids")
        if any(event.run_id != self.run_id for event in self.events):
            raise ValueError("AppendOnlyClaimLedger events must share the ledger run_id")
        if self.events != sorted(self.events, key=lambda event: event.occurred_at):
            raise ValueError("AppendOnlyClaimLedger events must be append-only ordered")

        current_ids = set(claim_ids)
        for event in self.events:
            if event.claim_id not in current_ids:
                raise ValueError("lifecycle event claim_id must remain visible in current_claims")

        max_events = self.retention_policy.get("max_events")
        if max_events is not None and (not isinstance(max_events, int) or max_events < 1):
            raise ValueError("retention_policy.max_events must be a positive integer")
        return self


def lifecycle_status_for_ledger(
    ledger: ClaimLedger | AppendOnlyClaimLedger | None,
) -> Literal["available", "legacy_no_events", "legacy_missing"]:
    """Return public lifecycle rendering status for v1/v2 ledgers."""

    if ledger is None:
        return "legacy_missing"
    if isinstance(ledger, AppendOnlyClaimLedger):
        if ledger.retention_policy.get("legacy_status") == "legacy_no_events":
            return "legacy_no_events"
        return "available"
    return "legacy_no_events"


def lifecycle_event_id(
    *,
    run_id: str,
    claim_id: str,
    action: ClaimLifecycleAction,
    actor_id: str,
    reason: str,
    sequence: int,
) -> str:
    """Create a deterministic event id for repeatable fixtures and packet projection."""

    digest = hashlib.sha256(
        json.dumps(
            {
                "run_id": run_id,
                "claim_id": claim_id,
                "action": action.value,
                "actor_id": actor_id,
                "reason": reason,
                "sequence": sequence,
            },
            sort_keys=True,
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"claim_event_{digest}"


def build_initial_append_only_ledger(
    ledger: ClaimLedger,
    *,
    actor_id: str,
    reason: str,
    occurred_at: datetime | None = None,
    base_ledger_ref: ArtifactRef | None = None,
    retention_policy: dict[str, Any] | None = None,
) -> AppendOnlyClaimLedger:
    """Wrap a Phase 1.1 ledger in a v2 append-only lifecycle sidecar."""

    timestamp = occurred_at or datetime.now(UTC)
    events = [
        ClaimLifecycleEvent(
            event_id=lifecycle_event_id(
                run_id=ledger.run_id,
                claim_id=claim.claim_id,
                action=ClaimLifecycleAction.CREATED,
                actor_id=actor_id,
                reason=reason,
                sequence=index,
            ),
            claim_id=claim.claim_id,
            run_id=ledger.run_id,
            action=ClaimLifecycleAction.CREATED,
            occurred_at=timestamp,
            actor_id=actor_id,
            reason=reason,
            evidence_refs=list(claim.evidence_refs),
            reviewer_refs=list(claim.reviewer_refs),
            metadata={
                "claim_type": claim.claim_type.value,
                "support_status": claim.support_status.value,
                "publishability": claim.publishability.value,
                "readiness_level": claim.readiness_level.value,
            },
        )
        for index, claim in enumerate(ledger.claims)
    ]
    return AppendOnlyClaimLedger(
        run_id=ledger.run_id,
        base_ledger_ref=base_ledger_ref,
        current_claims=list(ledger.claims),
        events=events,
        retention_policy=retention_policy or {},
        metadata={
            "base_schema_version": ledger.schema_version,
            "created_by_node_id": ledger.created_by_node_id,
        },
    )


def append_lifecycle_event(
    ledger: AppendOnlyClaimLedger,
    event: ClaimLifecycleEvent,
) -> AppendOnlyClaimLedger:
    """Return a new ledger with `event` appended after validation."""

    if event.run_id != ledger.run_id:
        raise ValueError("lifecycle event run_id must match ledger run_id")
    if any(existing.event_id == event.event_id for existing in ledger.events):
        raise ValueError("lifecycle event already exists")
    if ledger.events and event.occurred_at < ledger.events[-1].occurred_at:
        raise ValueError("lifecycle events cannot be reordered")
    return AppendOnlyClaimLedger.model_validate(
        ledger.model_copy(update={"events": [*ledger.events, event]}).model_dump(mode="python")
    )


def validate_claim_transition(
    previous: ClaimRecord,
    next_claim: ClaimRecord | None,
    *,
    action: ClaimLifecycleAction,
    reason: str,
) -> None:
    """Validate a single claim transition before a new lifecycle event is appended."""

    if not reason.strip():
        raise ValueError("claim lifecycle transitions require reason")
    if next_claim is None:
        if previous.publishability is ClaimPublishability.PUBLISHABLE:
            raise ValueError("publishable claims cannot be silently deleted")
        return
    if previous.claim_id != next_claim.claim_id and action not in {
        ClaimLifecycleAction.MERGED,
        ClaimLifecycleAction.SPLIT,
        ClaimLifecycleAction.SUPERSEDED,
    }:
        raise ValueError("claim_id changes require merge, split, or supersede action")
    if (
        previous.publishability is ClaimPublishability.PUBLISHABLE
        and next_claim.publishability is not ClaimPublishability.PUBLISHABLE
        and action
        not in {
            ClaimLifecycleAction.BLOCKED,
            ClaimLifecycleAction.SUPERSEDED,
            ClaimLifecycleAction.INVALIDATED,
            ClaimLifecycleAction.MARKED_STALE,
            ClaimLifecycleAction.REVIEW_REQUIRED,
            ClaimLifecycleAction.REISSUED,
            ClaimLifecycleAction.WITHDRAWN,
            ClaimLifecycleAction.REVIEWED,
        }
    ):
        raise ValueError("publishable claims cannot be silently downgraded")
    if previous.publishability != next_claim.publishability:
        if next_claim.publishability is ClaimPublishability.BLOCKED and (
            action is not ClaimLifecycleAction.BLOCKED
        ):
            raise ValueError("blocking a claim requires blocked action")
        if previous.publishability is ClaimPublishability.BLOCKED and (
            next_claim.publishability is not ClaimPublishability.BLOCKED
            and action not in {ClaimLifecycleAction.UNBLOCKED, ClaimLifecycleAction.REVIEWED}
        ):
            raise ValueError("unblocking a claim requires unblocked or reviewed action")
        if action not in {
            ClaimLifecycleAction.BLOCKED,
            ClaimLifecycleAction.UNBLOCKED,
            ClaimLifecycleAction.REVIEWED,
            ClaimLifecycleAction.INVALIDATED,
            ClaimLifecycleAction.MARKED_STALE,
            ClaimLifecycleAction.SUPERSEDED,
            ClaimLifecycleAction.REVIEW_REQUIRED,
            ClaimLifecycleAction.REISSUED,
            ClaimLifecycleAction.WITHDRAWN,
        }:
            raise ValueError("publishability changes require a release lifecycle action")
    if previous.readiness_level != next_claim.readiness_level and action not in {
        ClaimLifecycleAction.UPDATED_READINESS,
        ClaimLifecycleAction.BLOCKED,
        ClaimLifecycleAction.UNBLOCKED,
        ClaimLifecycleAction.REVIEWED,
        ClaimLifecycleAction.INVALIDATED,
        ClaimLifecycleAction.MARKED_STALE,
        ClaimLifecycleAction.MERGED,
        ClaimLifecycleAction.SPLIT,
        ClaimLifecycleAction.SUPERSEDED,
        ClaimLifecycleAction.REVIEW_REQUIRED,
        ClaimLifecycleAction.REISSUED,
        ClaimLifecycleAction.WITHDRAWN,
    }:
        raise ValueError("readiness changes require updated_readiness action")
    if previous.support_status != next_claim.support_status and action not in {
        ClaimLifecycleAction.UPDATED_SUPPORT,
        ClaimLifecycleAction.BLOCKED,
        ClaimLifecycleAction.UNBLOCKED,
        ClaimLifecycleAction.REVIEWED,
        ClaimLifecycleAction.INVALIDATED,
        ClaimLifecycleAction.MARKED_STALE,
        ClaimLifecycleAction.MERGED,
        ClaimLifecycleAction.SPLIT,
        ClaimLifecycleAction.SUPERSEDED,
        ClaimLifecycleAction.REVIEW_REQUIRED,
        ClaimLifecycleAction.REISSUED,
        ClaimLifecycleAction.WITHDRAWN,
    }:
        raise ValueError("support changes require updated_support action")


def claim_by_id(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
) -> dict[str, ClaimRecord]:
    """Return current claims keyed by id for v1 or v2 ledgers."""

    claims = ledger.current_claims if isinstance(ledger, AppendOnlyClaimLedger) else ledger.claims
    return {claim.claim_id: claim for claim in claims}


def _require_metadata_list(
    metadata: dict[str, Any],
    key: str,
    action: ClaimLifecycleAction,
) -> list[str]:
    raw = metadata.get(key)
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"{action.value} events require metadata.{key}")
    return raw


__all__ = [
    "CLAIM_LEDGER_V2_FLAG",
    "REQUIRE_LIFECYCLE_EVENTS_FLAG",
    "AppendOnlyClaimLedger",
    "ClaimLifecycleAction",
    "ClaimLifecycleEvent",
    "append_lifecycle_event",
    "build_initial_append_only_ledger",
    "claim_by_id",
    "lifecycle_event_id",
    "lifecycle_status_for_ledger",
    "validate_claim_transition",
]
