"""Export and summary helpers for Claim Ledger v1/v2 artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.scientist.evidence.claims.audit import (
    _append_only_audit_summary,
    _retention_window_for_export,
)
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    lifecycle_status_for_ledger,
)
from polisyos.scientist.evidence.claims.models import ClaimLedger, ClaimPublishability, ClaimRecord

if TYPE_CHECKING:
    from polisyos.scientist.evidence.claims.head_index import ClaimBridgePendingProjection


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
    claim_family: str | None = None
    claim_use: str | None = None
    support_status: str
    publishability: str
    readiness_level: str
    visible: bool
    omission_reason: str | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    facet_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    concept_spine_refs: list[str] = Field(default_factory=list)
    authority_profile_refs: list[str] = Field(default_factory=list)
    baseline_refs: list[str] = Field(default_factory=list)
    alternative_refs: list[str] = Field(default_factory=list)
    comparison_refs: list[str] = Field(default_factory=list)
    method_need_preconditions: list[dict[str, Any]] = Field(default_factory=list)
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
    comparison_records: list[dict[str, Any]] = Field(default_factory=list)
    omitted_claim_ids: list[str] = Field(default_factory=list)
    blocked_claim_ids: list[str] = Field(default_factory=list)
    superseded_claim_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _owner_projection_is_internally_consistent(self) -> ClaimLedgerExport:
        """Reject shaped exports that disagree with their own owner projection."""

        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_export_claim_ids_not_unique")
        hidden = {claim.claim_id for claim in self.claims if not claim.visible}
        if set(self.omitted_claim_ids) != hidden or len(self.omitted_claim_ids) != len(hidden):
            raise ValueError("claim_export_omission_denominator_mismatch")
        if any(
            not claim.visible
            and (
                claim.text
                or claim.blocked_reasons
                or claim.facet_refs
                or claim.obligation_refs
                or claim.concept_spine_refs
                or claim.authority_profile_refs
                or claim.baseline_refs
                or claim.alternative_refs
                or claim.comparison_refs
                or claim.method_need_preconditions
                or claim.source_attribution
            )
            for claim in self.claims
        ):
            raise ValueError("claim_export_hidden_claim_leaks_content")

        lifecycle = self.metadata.get("lifecycle_limitation_by_claim", {})
        if not isinstance(lifecycle, Mapping) or any(
            not isinstance(claim_id, str) or not isinstance(action, str)
            for claim_id, action in lifecycle.items()
        ):
            raise ValueError("claim_export_lifecycle_projection_invalid")
        expected_blocked = {
            claim.claim_id
            for claim in self.claims
            if claim.publishability == ClaimPublishability.BLOCKED.value
        } | {
            str(claim_id)
            for claim_id, action in lifecycle.items()
            if action == ClaimLifecycleAction.BLOCKED.value
        }
        if set(self.blocked_claim_ids) != expected_blocked or len(self.blocked_claim_ids) != len(
            expected_blocked
        ):
            raise ValueError("claim_export_blocked_denominator_mismatch")
        if lifecycle:
            expected_superseded = {
                str(claim_id)
                for claim_id, action in lifecycle.items()
                if action == ClaimLifecycleAction.SUPERSEDED.value
            }
            if set(self.superseded_claim_ids) != expected_superseded or len(
                self.superseded_claim_ids
            ) != len(expected_superseded):
                raise ValueError("claim_export_superseded_denominator_mismatch")

        if self.audience is ClaimExportAudience.PUBLIC:
            limited = set(lifecycle)
            if any(
                claim.visible
                and (
                    claim.publishability != ClaimPublishability.PUBLISHABLE.value
                    or claim.claim_id in limited
                )
                for claim in self.claims
            ):
                raise ValueError("claim_export_public_visibility_bypass")
        return self


def _claim_ledger_summary(
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
        "family_assignment_count": len(_family_assignments(ledger)),
        "baseline_record_count": len(_baseline_records(ledger)),
        "alternative_record_count": len(_alternative_records(ledger)),
        "comparison_record_count": len(_comparison_records(ledger)),
        "lifecycle_status": lifecycle_status_for_ledger(ledger),
        "event_count": len(ledger.events) if isinstance(ledger, AppendOnlyClaimLedger) else 0,
        "publishability_counts": publishability_counts,
        "blocked_claim_ids": blocked,
        "review_required_claim_ids": review_required,
        "publication_ready": not blocked and not review_required,
    }
    if isinstance(ledger, AppendOnlyClaimLedger):
        summary["audit"] = _append_only_audit_summary(ledger)
    return summary


def _blocked_claim_summary(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
) -> dict[str, Any]:
    """Return visible blocked/superseded claim details for packet and reviewer views."""

    blocked_claims = [
        claim for claim in _claims(ledger) if claim.publishability is ClaimPublishability.BLOCKED
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


def _format_resolved_claim_ledger(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
    *,
    audience: ClaimExportAudience | str,
    pending_projection: ClaimBridgePendingProjection,
) -> ClaimLedgerExport:
    """Format owner-resolved bytes while composing any durable pending freeze."""

    resolved_audience = ClaimExportAudience(audience)
    latest_lifecycle = _latest_lifecycle_actions(ledger)
    lifecycle_limited = {
        claim_id: action
        for claim_id, action in latest_lifecycle.items()
        if action
        in {
            ClaimLifecycleAction.BLOCKED,
            ClaimLifecycleAction.INVALIDATED,
            ClaimLifecycleAction.MERGED,
            ClaimLifecycleAction.MARKED_STALE,
            ClaimLifecycleAction.REVIEW_REQUIRED,
            ClaimLifecycleAction.SPLIT,
            ClaimLifecycleAction.SUPERSEDED,
            ClaimLifecycleAction.WITHDRAWN,
        }
    }
    exported_claims: list[ClaimLedgerExportClaim] = []
    omitted: list[str] = []
    for claim in _claims(ledger):
        visible, reason = _claim_visibility(claim, audience=resolved_audience)
        if resolved_audience is ClaimExportAudience.PUBLIC and claim.claim_id in lifecycle_limited:
            visible = False
            reason = f"claim_lifecycle_{lifecycle_limited[claim.claim_id].value}"
        if resolved_audience is ClaimExportAudience.PUBLIC and (
            pending_projection.unresolved_mapping
            or claim.claim_id in pending_projection.ordered_affected_claim_ids
        ):
            visible = False
            reason = (
                "claim_target_denominator_unresolved"
                if pending_projection.unresolved_mapping
                else "claim_bridge_pending"
            )
        if not visible:
            omitted.append(claim.claim_id)
        exported_claims.append(_export_claim(claim, visible=visible, omission_reason=reason))

    blocked_ids = sorted(
        {
            *(
                claim.claim_id
                for claim in _claims(ledger)
                if claim.publishability is ClaimPublishability.BLOCKED
            ),
            *(
                claim_id
                for claim_id, action in lifecycle_limited.items()
                if action is ClaimLifecycleAction.BLOCKED
            ),
        }
    )
    superseded_ids = sorted(_event_claim_ids(ledger, ClaimLifecycleAction.SUPERSEDED))
    active_pending_refs = [
        str(row.pending_ref.artifact_id) for row in pending_projection.active_pendings
    ]
    pending_batch_refs = sorted(
        {
            *(
                str(row.statement.batch_receipt_ref.artifact_id)
                for row in pending_projection.active_pendings
            ),
            *(str(ref.artifact_id) for ref in pending_projection.unmaterialized_batch_receipt_refs),
        }
    )
    pending = bool(active_pending_refs or pending_batch_refs)
    denominator_established = pending_projection.completed_batch_denominator_established
    metadata = {
        "blocked_claims_visible": resolved_audience
        in {ClaimExportAudience.REVIEWER, ClaimExportAudience.EXPERT, ClaimExportAudience.MACHINE},
        "superseded_claims_visible": resolved_audience
        in {ClaimExportAudience.REVIEWER, ClaimExportAudience.EXPERT, ClaimExportAudience.MACHINE},
        "family_assignment_count": len(_family_assignments(ledger)),
        "baseline_record_count": len(_baseline_records(ledger)),
        "alternative_record_count": len(_alternative_records(ledger)),
        "comparison_record_count": len(_comparison_records(ledger)),
        "claim_bridge_pending": pending,
        "claim_currentness": (
            "current" if not pending and denominator_established else "not_established"
        ),
        "completed_batch_denominator_established": denominator_established,
        "pending_receipt_refs": active_pending_refs,
        "pending_batch_receipt_refs": pending_batch_refs,
        "pending_affected_claim_ids": list(pending_projection.ordered_affected_claim_ids),
        "pending_mapping_unresolved": pending_projection.unresolved_mapping,
        "lifecycle_limited_claim_ids": sorted(lifecycle_limited),
        "lifecycle_limitation_by_claim": {
            claim_id: lifecycle_limited[claim_id].value for claim_id in sorted(lifecycle_limited)
        },
        "lifecycle_events": (
            [event.model_dump(mode="json") for event in ledger.events]
            if isinstance(ledger, AppendOnlyClaimLedger)
            and resolved_audience is not ClaimExportAudience.PUBLIC
            else []
        ),
    }
    if isinstance(ledger, AppendOnlyClaimLedger):
        metadata["retention_window"] = _retention_window_for_export(ledger)
    comparison_records = (
        [record.model_dump(mode="json") for record in _comparison_records(ledger)]
        if resolved_audience
        in {ClaimExportAudience.REVIEWER, ClaimExportAudience.EXPERT, ClaimExportAudience.MACHINE}
        else []
    )
    return ClaimLedgerExport(
        run_id=ledger.run_id,
        audience=resolved_audience,
        lifecycle_status=lifecycle_status_for_ledger(ledger),
        claims=exported_claims,
        comparison_records=comparison_records,
        omitted_claim_ids=omitted,
        blocked_claim_ids=blocked_ids,
        superseded_claim_ids=superseded_ids,
        metadata=metadata,
    )


def _legacy_claim_ledger_export_status(
    ledger: ClaimLedger | AppendOnlyClaimLedger | None,
) -> str:
    """Return v1/v2 export compatibility status for old ClaimLedger artifacts."""

    return lifecycle_status_for_ledger(ledger)


def _claims(ledger: ClaimLedger | AppendOnlyClaimLedger) -> list[ClaimRecord]:
    if isinstance(ledger, AppendOnlyClaimLedger):
        return list(ledger.current_claims)
    return list(ledger.claims)


def _event_claim_ids(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
    action: ClaimLifecycleAction,
) -> set[str]:
    if not isinstance(ledger, AppendOnlyClaimLedger):
        return set()
    return {event.claim_id for event in ledger.events if event.action is action}


def _latest_lifecycle_actions(
    ledger: ClaimLedger | AppendOnlyClaimLedger,
) -> dict[str, ClaimLifecycleAction]:
    if not isinstance(ledger, AppendOnlyClaimLedger):
        return {}
    latest: dict[str, ClaimLifecycleAction] = {}
    for event in ledger.events:
        latest[event.claim_id] = event.action
    return latest


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
        claim_family=claim.claim_family.value if claim.claim_family is not None else None,
        claim_use=claim.claim_use.value if claim.claim_use is not None else None,
        support_status=claim.support_status.value,
        publishability=claim.publishability.value,
        readiness_level=claim.readiness_level.value,
        visible=visible,
        omission_reason=omission_reason,
        blocked_reasons=list(claim.blocked_reasons) if visible else [],
        facet_refs=list(claim.facet_refs) if visible else [],
        obligation_refs=list(claim.obligation_refs) if visible else [],
        concept_spine_refs=list(claim.concept_spine_refs) if visible else [],
        authority_profile_refs=list(claim.authority_profile_refs) if visible else [],
        baseline_refs=list(claim.baseline_refs) if visible else [],
        alternative_refs=list(claim.alternative_refs) if visible else [],
        comparison_refs=list(claim.comparison_refs) if visible else [],
        method_need_preconditions=[
            precondition.model_dump(mode="json") for precondition in claim.method_need_preconditions
        ]
        if visible
        else [],
        evidence_ref_count=len(claim.evidence_refs),
        counterevidence_ref_count=len(claim.counterevidence_refs),
        reviewer_ref_count=len(claim.reviewer_refs),
        source_attribution=list(claim.source_attribution) if visible else [],
    )


def _family_assignments(ledger: ClaimLedger | AppendOnlyClaimLedger) -> list[Any]:
    return list(getattr(ledger, "family_assignments", []))


def _baseline_records(ledger: ClaimLedger | AppendOnlyClaimLedger) -> list[Any]:
    return list(getattr(ledger, "baseline_records", []))


def _alternative_records(ledger: ClaimLedger | AppendOnlyClaimLedger) -> list[Any]:
    return list(getattr(ledger, "alternative_records", []))


def _comparison_records(ledger: ClaimLedger | AppendOnlyClaimLedger) -> list[Any]:
    return list(getattr(ledger, "comparison_records", []))


__all__ = [
    "ClaimExportAudience",
    "ClaimLedgerExport",
    "ClaimLedgerExportClaim",
]
