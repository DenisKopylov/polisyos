"""Claim-level diff helpers for Scientist ledgers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    claim_by_id,
)
from polisyos.scientist.evidence.claims.models import ClaimLedger, ClaimPublishability, ClaimRecord


class ClaimFieldChange(BaseModel):
    """One changed claim field."""

    model_config = ConfigDict(extra="forbid")

    field: str
    before: Any
    after: Any


class ClaimLedgerDiff(BaseModel):
    """Claim-level diff between two ledger snapshots."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    before_run_id: str
    after_run_id: str
    added_claim_ids: list[str] = Field(default_factory=list)
    removed_claim_ids: list[str] = Field(default_factory=list)
    changed_claim_ids: list[str] = Field(default_factory=list)
    changed_support_claim_ids: list[str] = Field(default_factory=list)
    changed_readiness_claim_ids: list[str] = Field(default_factory=list)
    blocked_claim_ids: list[str] = Field(default_factory=list)
    superseded_claim_ids: list[str] = Field(default_factory=list)
    counterevidence_changed_claim_ids: list[str] = Field(default_factory=list)
    reviewer_attribution_changed_claim_ids: list[str] = Field(default_factory=list)
    silent_publication_regression_claim_ids: list[str] = Field(default_factory=list)
    field_changes: dict[str, list[ClaimFieldChange]] = Field(default_factory=dict)


def diff_claim_ledgers(
    before: ClaimLedger | AppendOnlyClaimLedger,
    after: ClaimLedger | AppendOnlyClaimLedger,
) -> ClaimLedgerDiff:
    """Diff claims by semantic claim ids rather than artifact filenames."""

    before_claims = claim_by_id(before)
    after_claims = claim_by_id(after)
    before_ids = set(before_claims)
    after_ids = set(after_claims)

    field_changes: dict[str, list[ClaimFieldChange]] = {}
    changed_support: list[str] = []
    changed_readiness: list[str] = []
    counterevidence_changed: list[str] = []
    reviewer_changed: list[str] = []
    silent_regressions: list[str] = []

    for claim_id in sorted(before_ids & after_ids):
        changes = _claim_field_changes(before_claims[claim_id], after_claims[claim_id])
        if changes:
            field_changes[claim_id] = changes
        fields = {change.field for change in changes}
        if "support_status" in fields:
            changed_support.append(claim_id)
        if "readiness_level" in fields:
            changed_readiness.append(claim_id)
        if "counterevidence_refs" in fields:
            counterevidence_changed.append(claim_id)
        if "reviewer_refs" in fields:
            reviewer_changed.append(claim_id)
        if _is_silent_publication_regression(
            before_claims[claim_id],
            after_claims[claim_id],
            after,
        ):
            silent_regressions.append(claim_id)

    removed = sorted(before_ids - after_ids)
    for claim_id in removed:
        if before_claims[claim_id].publishability is ClaimPublishability.PUBLISHABLE:
            if not _has_lifecycle_action(after, claim_id, ClaimLifecycleAction.SUPERSEDED):
                silent_regressions.append(claim_id)

    blocked_ids = sorted(
        {
            claim.claim_id
            for claim in after_claims.values()
            if claim.publishability is ClaimPublishability.BLOCKED
        }
        | _event_claim_ids(after, ClaimLifecycleAction.BLOCKED)
    )
    superseded_ids = sorted(_event_claim_ids(after, ClaimLifecycleAction.SUPERSEDED))

    return ClaimLedgerDiff(
        before_run_id=before.run_id,
        after_run_id=after.run_id,
        added_claim_ids=sorted(after_ids - before_ids),
        removed_claim_ids=removed,
        changed_claim_ids=sorted(field_changes),
        changed_support_claim_ids=changed_support,
        changed_readiness_claim_ids=changed_readiness,
        blocked_claim_ids=blocked_ids,
        superseded_claim_ids=superseded_ids,
        counterevidence_changed_claim_ids=counterevidence_changed,
        reviewer_attribution_changed_claim_ids=reviewer_changed,
        silent_publication_regression_claim_ids=sorted(set(silent_regressions)),
        field_changes=field_changes,
    )


def _claim_field_changes(before: ClaimRecord, after: ClaimRecord) -> list[ClaimFieldChange]:
    fields = (
        "text",
        "normalized_subject",
        "support_status",
        "publishability",
        "readiness_level",
        "evidence_refs",
        "counterevidence_refs",
        "uncertainty_profile_ref",
        "provenance_ref",
        "source_attribution",
        "reviewer_refs",
        "blocked_reasons",
    )
    changes: list[ClaimFieldChange] = []
    for field in fields:
        before_value = _json_value(getattr(before, field))
        after_value = _json_value(getattr(after, field))
        if before_value != after_value:
            changes.append(
                ClaimFieldChange(
                    field=field,
                    before=before_value,
                    after=after_value,
                )
            )
    return changes


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value


def _event_claim_ids(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
    action: ClaimLifecycleAction,
) -> set[str]:
    if not isinstance(ledger, AppendOnlyClaimLedger):
        return set()
    return {event.claim_id for event in ledger.events if event.action is action}


def _has_lifecycle_action(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
    claim_id: str,
    action: ClaimLifecycleAction,
) -> bool:
    if not isinstance(ledger, AppendOnlyClaimLedger):
        return False
    return any(event.claim_id == claim_id and event.action is action for event in ledger.events)


def _is_silent_publication_regression(
    before: ClaimRecord,
    after: ClaimRecord,
    after_ledger: ClaimLedger | AppendOnlyClaimLedger,
) -> bool:
    if before.publishability is not ClaimPublishability.PUBLISHABLE:
        return False
    if after.publishability is ClaimPublishability.PUBLISHABLE:
        return False
    return not any(
        _has_lifecycle_action(after_ledger, before.claim_id, action)
        for action in (
            ClaimLifecycleAction.BLOCKED,
            ClaimLifecycleAction.SUPERSEDED,
            ClaimLifecycleAction.INVALIDATED,
            ClaimLifecycleAction.REVIEWED,
        )
    )


__all__ = [
    "ClaimFieldChange",
    "ClaimLedgerDiff",
    "diff_claim_ledgers",
]
