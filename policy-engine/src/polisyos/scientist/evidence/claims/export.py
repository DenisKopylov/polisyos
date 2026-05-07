"""Export and summary helpers for Claim Ledger v1/v2 artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.evidence.claims.audit import (
    append_only_audit_summary,
    retention_window_for_export,
)
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    lifecycle_status_for_ledger,
)
from polisyos.scientist.evidence.claims.models import ClaimLedger, ClaimPublishability, ClaimRecord


class ClaimExportAudience(str, Enum):
    """Audience-specific export modes."""

    PUBLIC = "public"
    REVIEWER = "reviewer"
    EXPERT = "expert"
    MACHINE = "machine"


class ClaimLedgerExportClaim(BaseModel):
    """One exported claim plus omission/visibility metadata."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    text: str
    claim_type: str
    support_status: str
    publishability: str
    readiness_level: str
    visible: bool
    omission_reason: str | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    evidence_ref_count: int = 0
    counterevidence_ref_count: int = 0
    reviewer_ref_count: int = 0
    source_attribution: list[str] = Field(default_factory=list)


class ClaimLedgerExport(BaseModel):
    """Audience-specific export of a claim ledger."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    audience: ClaimExportAudience
    lifecycle_status: Literal["available", "legacy_no_events", "legacy_missing"]
    claims: list[ClaimLedgerExportClaim] = Field(default_factory=list)
    omitted_claim_ids: list[str] = Field(default_factory=list)
    blocked_claim_ids: list[str] = Field(default_factory=list)
    superseded_claim_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def claim_ledger_summary(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
) -> dict[str, Any]:
    """Return the packet-level ledger summary used by DecisionPacket v3.x."""

    claims = _claims(ledger)
    blocked = [
        claim.claim_id for claim in claims if claim.publishability is ClaimPublishability.BLOCKED
    ]
    review_required = [
        claim.claim_id
        for claim in claims
        if claim.publishability is ClaimPublishability.REVIEW_REQUIRED
    ]
    publishability_counts = {
        item.value: sum(1 for claim in claims if claim.publishability is item)
        for item in ClaimPublishability
    }
    summary: dict[str, Any] = {
        "schema_version": ledger.schema_version,
        "run_id": ledger.run_id,
        "claim_count": len(claims),
        "lifecycle_status": lifecycle_status_for_ledger(ledger),
        "event_count": len(ledger.events) if isinstance(ledger, AppendOnlyClaimLedger) else 0,
        "publishability_counts": publishability_counts,
        "blocked_claim_ids": blocked,
        "review_required_claim_ids": review_required,
        "publication_ready": not blocked and not review_required,
    }
    if isinstance(ledger, AppendOnlyClaimLedger):
        summary["audit"] = append_only_audit_summary(ledger)
    return summary


def blocked_claim_summary(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
) -> dict[str, Any]:
    """Return visible blocked/superseded claim details for packet and reviewer views."""

    blocked_claims = [
        claim
        for claim in _claims(ledger)
        if claim.publishability is ClaimPublishability.BLOCKED
    ]
    superseded_ids = sorted(_event_claim_ids(ledger, ClaimLifecycleAction.SUPERSEDED))
    return {
        "schema_version": "1.0",
        "run_id": ledger.run_id,
        "lifecycle_status": lifecycle_status_for_ledger(ledger),
        "blocked_count": len(blocked_claims),
        "blocked_claims": [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "blocked_reasons": list(claim.blocked_reasons),
                "counterevidence_ref_count": len(claim.counterevidence_refs),
                "reviewer_ref_count": len(claim.reviewer_refs),
            }
            for claim in blocked_claims
        ],
        "superseded_claim_ids": superseded_ids,
    }


def export_claim_ledger(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
    *,
    audience: ClaimExportAudience | str,
) -> ClaimLedgerExport:
    """Export claims for public, reviewer, expert or machine consumers."""

    resolved_audience = ClaimExportAudience(audience)
    exported_claims: list[ClaimLedgerExportClaim] = []
    omitted: list[str] = []
    for claim in _claims(ledger):
        visible, reason = _claim_visibility(claim, audience=resolved_audience)
        if not visible:
            omitted.append(claim.claim_id)
        exported_claims.append(_export_claim(claim, visible=visible, omission_reason=reason))

    blocked_ids = [
        claim.claim_id
        for claim in _claims(ledger)
        if claim.publishability is ClaimPublishability.BLOCKED
    ]
    superseded_ids = sorted(_event_claim_ids(ledger, ClaimLifecycleAction.SUPERSEDED))
    metadata = {
        "blocked_claims_visible": resolved_audience
        in {ClaimExportAudience.REVIEWER, ClaimExportAudience.EXPERT, ClaimExportAudience.MACHINE},
        "superseded_claims_visible": resolved_audience
        in {ClaimExportAudience.REVIEWER, ClaimExportAudience.EXPERT, ClaimExportAudience.MACHINE},
    }
    if isinstance(ledger, AppendOnlyClaimLedger):
        metadata["retention_window"] = retention_window_for_export(ledger)
    return ClaimLedgerExport(
        run_id=ledger.run_id,
        audience=resolved_audience,
        lifecycle_status=lifecycle_status_for_ledger(ledger),
        claims=exported_claims,
        omitted_claim_ids=omitted,
        blocked_claim_ids=blocked_ids,
        superseded_claim_ids=superseded_ids,
        metadata=metadata,
    )


def legacy_claim_ledger_export_status(ledger: ClaimLedger | AppendOnlyClaimLedger | None) -> str:
    """Return v1/v2 export compatibility status for old ClaimLedger artifacts."""

    return lifecycle_status_for_ledger(ledger)


def _claims(ledger: ClaimLedger | AppendOnlyClaimLedger) -> list[ClaimRecord]:
    return list(ledger.current_claims if isinstance(ledger, AppendOnlyClaimLedger) else ledger.claims)


def _event_claim_ids(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
    action: ClaimLifecycleAction,
) -> set[str]:
    if not isinstance(ledger, AppendOnlyClaimLedger):
        return set()
    return {event.claim_id for event in ledger.events if event.action is action}


def _claim_visibility(
    claim: ClaimRecord,
    *,
    audience: ClaimExportAudience,
) -> tuple[bool, str | None]:
    if audience in {
        ClaimExportAudience.REVIEWER,
        ClaimExportAudience.EXPERT,
        ClaimExportAudience.MACHINE,
    }:
        return True, None
    if claim.publishability is ClaimPublishability.PUBLISHABLE:
        return True, None
    if claim.publishability is ClaimPublishability.BLOCKED:
        return False, "blocked_claim_visible_only_to_reviewer_or_machine"
    return False, f"{claim.publishability.value}_not_public"


def _export_claim(
    claim: ClaimRecord,
    *,
    visible: bool,
    omission_reason: str | None,
) -> ClaimLedgerExportClaim:
    return ClaimLedgerExportClaim(
        claim_id=claim.claim_id,
        text=claim.text if visible else "",
        claim_type=claim.claim_type.value,
        support_status=claim.support_status.value,
        publishability=claim.publishability.value,
        readiness_level=claim.readiness_level.value,
        visible=visible,
        omission_reason=omission_reason,
        blocked_reasons=list(claim.blocked_reasons) if visible else [],
        evidence_ref_count=len(claim.evidence_refs),
        counterevidence_ref_count=len(claim.counterevidence_refs),
        reviewer_ref_count=len(claim.reviewer_refs),
        source_attribution=list(claim.source_attribution) if visible else [],
    )


__all__ = [
    "ClaimExportAudience",
    "ClaimLedgerExport",
    "ClaimLedgerExportClaim",
    "blocked_claim_summary",
    "claim_ledger_summary",
    "export_claim_ledger",
    "legacy_claim_ledger_export_status",
]
