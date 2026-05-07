"""Human-review packet and decision contracts for Scientist release control."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef

__all__ = [
    "FundamentalRightsChecklist",
    "HumanReviewAuditEvent",
    "HumanReviewDecision",
    "HumanReviewPacket",
    "HumanReviewQueueRecord",
    "HumanReviewStatus",
    "RecommendedReviewerAction",
    "ReviewAction",
    "ReviewAssignment",
    "ReviewAssignmentStatus",
    "ReviewControl",
    "ReviewRiskTier",
    "ReviewerRole",
    "ReviewerSignature",
]


class ReviewRiskTier(StrEnum):
    """Risk tier for review-routing and release gates."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PUBLIC_SECTOR_HIGH = "public_sector_high"


class ReviewAction(StrEnum):
    """Reviewer release decision semantics."""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_RERUN = "request_rerun"
    OVERRIDE = "override"
    EXPLANATION_INSUFFICIENT = "explanation_insufficient"
    INTERRUPT_RELEASE = "interrupt_release"


class HumanReviewStatus(StrEnum):
    """Aggregated operational status for a review packet."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RERUN_REQUESTED = "rerun_requested"
    OVERRIDDEN = "overridden"
    EXPLANATION_INSUFFICIENT = "explanation_insufficient"
    INTERRUPTED = "interrupted"
    LEGACY_MISSING = "legacy_missing"


class ReviewerRole(StrEnum):
    """Reviewer role for assignment and two-person verification."""

    PRIMARY = "primary"
    SECOND_PERSON = "second_person"
    DOMAIN_EXPERT = "domain_expert"
    RELEASE_OWNER = "release_owner"


class ReviewAssignmentStatus(StrEnum):
    """Assignment lifecycle status."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReviewControl(StrEnum):
    """Controls available to a human reviewer."""

    STOP_RELEASE = "stop_release"
    OVERRIDE_RELEASE = "override_release"
    REISSUE_WITH_CHANGES = "reissue_with_changes"
    REQUEST_RERUN = "request_rerun"
    REQUEST_EXPLANATION = "request_explanation"


class RecommendedReviewerAction(StrEnum):
    """Recommended reviewer actions rendered in release packets."""

    VERIFY_CLAIMS = "verify_claims"
    CHECK_COUNTEREVIDENCE = "check_counterevidence"
    REVIEW_RIGHTS_IMPACT = "review_rights_impact"
    REVIEW_LEGAL_BASIS = "review_legal_basis"
    REVIEW_FAIRNESS = "review_fairness"
    REVIEW_PRIVACY = "review_privacy"
    APPROVE_OR_REJECT_RELEASE = "approve_or_reject_release"


class FundamentalRightsChecklist(BaseModel):
    """Public-sector/fundamental-rights checklist for high-risk review."""

    model_config = ConfigDict(extra="forbid")

    public_sector_use: bool = False
    affects_fundamental_rights: bool = False
    automated_decision_support: bool = False
    vulnerable_groups_affected: bool = False
    legal_basis_documented: bool = False
    privacy_impact_considered: bool = False
    fairness_impact_considered: bool = False
    human_override_available: bool = False
    explanation_available: bool = False
    issues: list[str] = Field(default_factory=list)

    @property
    def unresolved_items(self) -> list[str]:
        """Return checklist items that remain unresolved."""

        unresolved: list[str] = []
        if self.public_sector_use and not self.legal_basis_documented:
            unresolved.append("legal_basis_documented")
        if self.affects_fundamental_rights and not self.explanation_available:
            unresolved.append("explanation_available")
        if self.automated_decision_support and not self.human_override_available:
            unresolved.append("human_override_available")
        if self.vulnerable_groups_affected and not self.fairness_impact_considered:
            unresolved.append("fairness_impact_considered")
        if self.public_sector_use and not self.privacy_impact_considered:
            unresolved.append("privacy_impact_considered")
        return sorted(set(unresolved).union(self.issues))


class HumanReviewAuditEvent(BaseModel):
    """Append-only audit event for packet/decision lifecycle."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    packet_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    actor_id: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewerSignature(BaseModel):
    """Typed reviewer signature attached to a decision or packet."""

    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(min_length=1)
    role: ReviewerRole = ReviewerRole.PRIMARY
    signed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    attestation: str = Field(min_length=1)
    signature_ref: ArtifactRef | None = None


class ReviewAssignment(BaseModel):
    """Assignment of a review packet to a human reviewer."""

    model_config = ConfigDict(extra="forbid")

    assignment_id: str = Field(min_length=1)
    packet_id: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    role: ReviewerRole = ReviewerRole.PRIMARY
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    due_at: datetime | None = None
    status: ReviewAssignmentStatus = ReviewAssignmentStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)


class HumanReviewPacket(BaseModel):
    """CAS-persisted operational packet for accountable human oversight."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    packet_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    workflow_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    risk_tier: ReviewRiskTier = ReviewRiskTier.MEDIUM
    decision_summary: dict[str, Any] = Field(default_factory=dict)
    claim_ledger_summary: dict[str, Any] = Field(default_factory=dict)
    top_evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    top_counterevidence_refs: list[ArtifactRef] = Field(default_factory=list)
    uncertainty_summary: dict[str, Any] = Field(default_factory=dict)
    calibration_summary: dict[str, Any] = Field(default_factory=dict)
    source_freshness_summary: dict[str, Any] = Field(default_factory=dict)
    legal_fairness_privacy_escalation_issues: list[dict[str, Any]] = Field(
        default_factory=list
    )
    blocked_claim_ids: list[str] = Field(default_factory=list)
    unresolved_assumptions: list[str] = Field(default_factory=list)
    recommended_reviewer_actions: list[RecommendedReviewerAction] = Field(
        default_factory=list
    )
    controls: list[ReviewControl] = Field(default_factory=list)
    fundamental_rights_checklist: FundamentalRightsChecklist = Field(
        default_factory=FundamentalRightsChecklist
    )
    required_reviewer_count: int = Field(default=1, ge=1, le=4)
    assignments: list[ReviewAssignment] = Field(default_factory=list)
    audit_trail: list[HumanReviewAuditEvent] = Field(default_factory=list)
    reviewer_signatures: list[ReviewerSignature] = Field(default_factory=list)
    decision_packet_ref: ArtifactRef | None = None
    claims_ref: ArtifactRef | None = None
    governance_report_ref: ArtifactRef | None = None
    research_dag_ref: ArtifactRef | None = None
    evidence_bundle_ref: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _high_risk_has_controls(self) -> HumanReviewPacket:
        if self.risk_tier in {ReviewRiskTier.HIGH, ReviewRiskTier.PUBLIC_SECTOR_HIGH}:
            if ReviewControl.STOP_RELEASE not in self.controls:
                raise ValueError("high-risk review packets must include stop_release control")
            if ReviewControl.OVERRIDE_RELEASE not in self.controls:
                raise ValueError("high-risk review packets must include override_release control")
        if self.required_reviewer_count > 1:
            reviewer_ids = [assignment.reviewer_id for assignment in self.assignments]
            if reviewer_ids and len(set(reviewer_ids)) < min(self.required_reviewer_count, len(reviewer_ids)):
                raise ValueError("two-person verification assignments must use distinct reviewers")
        return self


class HumanReviewDecision(BaseModel):
    """CAS-persisted decision made by a human reviewer."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    decision_id: str = Field(min_length=1)
    packet_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    action: ReviewAction
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rationale: str = Field(min_length=1)
    override_reason: str | None = None
    explanation_gap: str | None = None
    requested_changes: list[str] = Field(default_factory=list)
    signature: ReviewerSignature
    packet_ref: ArtifactRef | None = None
    supersedes_decision_ref: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _action_specific_fields(self) -> HumanReviewDecision:
        if self.action is ReviewAction.OVERRIDE and not self.override_reason:
            raise ValueError("override decisions require override_reason")
        if self.action is ReviewAction.EXPLANATION_INSUFFICIENT and not self.explanation_gap:
            raise ValueError("explanation_insufficient decisions require explanation_gap")
        if self.action is ReviewAction.REQUEST_RERUN and not self.requested_changes:
            raise ValueError("request_rerun decisions require requested_changes")
        if self.signature.reviewer_id != self.reviewer_id:
            raise ValueError("signature reviewer_id must match decision reviewer_id")
        return self


class HumanReviewQueueRecord(BaseModel):
    """Queue state for one review packet."""

    model_config = ConfigDict(extra="forbid")

    packet_id: str = Field(min_length=1)
    packet_ref: ArtifactRef
    status: HumanReviewStatus = HumanReviewStatus.PENDING
    risk_tier: ReviewRiskTier = ReviewRiskTier.MEDIUM
    required_reviewer_count: int = Field(default=1, ge=1, le=4)
    assignments: list[ReviewAssignment] = Field(default_factory=list)
    decision_refs: list[ArtifactRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
