"""Typed Policy Design Case projection contracts for runtime/API consumers."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic resolves runtime annotations.
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION = "policyos.runtime.policy_design_case.projection.v1"
RECOURSE_POINTER_SCHEMA_VERSION = "policyos.runtime.policy_design_case.recourse_pointer.v1"


class PolicyDesignCaseAudience(StrEnum):
    """Audience tier for a Policy Design Case projection."""

    PUBLIC = "public"
    REVIEWER = "reviewer"
    EXPERT = "expert"
    MACHINE = "machine"


class PolicyDesignCaseProjectionLabel(BaseModel):
    """One display label attached to a projection state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: str = Field(min_length=1)
    label: str = Field(min_length=1)
    authority_role: Literal["projection_only"] = "projection_only"
    source_authority: str = Field(default="policy_design_case", min_length=1)


class PolicyDesignCaseProjectionBlocker(BaseModel):
    """Closeout or publication blocker surfaced through a projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    severity: str = Field(default="fail", min_length=1)
    message: str = Field(min_length=1)
    module_id: str | None = None
    owner: str | None = None
    evidence_ref: str | None = None
    next_action: str | None = None


class PolicyDesignCaseCloseoutTruth(BaseModel):
    """Closeout truth that every audience must preserve."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(min_length=1)
    verdict: str = Field(min_length=1)
    can_closeout: bool
    blocker_codes: tuple[str, ...] = Field(default=())
    limitation_codes: tuple[str, ...] = Field(default=())
    omission_codes: tuple[str, ...] = Field(default=())
    contested_state: str = Field(default="not_contested", min_length=1)
    blockers: tuple[PolicyDesignCaseProjectionBlocker, ...] = Field(default=())


class PolicyDesignCaseProjectionGap(BaseModel):
    """Projection-visible blocker, limitation, redaction, or omission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gap_id: str = Field(min_length=1)
    gap_code: str = Field(min_length=1)
    gap_family: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    message: str = Field(min_length=1)
    audience_visibility: tuple[PolicyDesignCaseAudience, ...] = Field(default=())
    claim_ids: tuple[str, ...] = Field(default=())
    source: str | None = None
    owner: str | None = None
    evidence_ref: str | None = None
    next_action: str | None = None
    publication_effect: str = Field(default="unaffected", min_length=1)
    closeout_effect: str = Field(default="limited_closeout", min_length=1)


class PolicyDesignCaseProjectionOmission(BaseModel):
    """Audience-visible omission manifest row for redacted or omitted PDC content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    omission_id: str = Field(min_length=1)
    omission_code: str = Field(min_length=1)
    omission_family: str = Field(default="projection", min_length=1)
    reason: str = Field(min_length=1)
    audience_visibility: tuple[PolicyDesignCaseAudience, ...] = Field(default=())
    claim_ids: tuple[str, ...] = Field(default=())
    source: str | None = None
    owner: str | None = None
    evidence_ref: str | None = None
    manifest_ref: str | None = None
    publication_effect: str = Field(default="omission_manifest_required", min_length=1)
    closeout_effect: str = Field(default="limited_closeout", min_length=1)


class PolicyDesignCaseRecoursePointer(BaseModel):
    """Projection pointer to a deployment-owned recourse process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[RECOURSE_POINTER_SCHEMA_VERSION] = RECOURSE_POINTER_SCHEMA_VERSION
    uri: str = Field(min_length=1)
    verification_status: Literal["verified_reachable"] = "verified_reachable"
    verified_at: str = Field(min_length=1)
    verification_ref: str = Field(min_length=1)
    owner: str | None = None
    authority_boundary: Literal["deployment_owned_recourse_process"] = (
        "deployment_owned_recourse_process"
    )


class PolicyDesignCaseContestedRecord(BaseModel):
    """Projection-visible contested record owned by PolicyOS."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contested_record_id: str = Field(min_length=1)
    case_ref: str = Field(min_length=1)
    claim_refs: tuple[str, ...] = Field(default=())
    audience_visibility: tuple[PolicyDesignCaseAudience, ...] = Field(default=())
    contestability_status: str = Field(min_length=1)
    grounds: tuple[str, ...] = Field(default=())
    standing_or_actor_ref: str | None = None
    counterevidence_refs: tuple[str, ...] = Field(default=())
    source_truth_conflict_refs: tuple[str, ...] = Field(default=())
    authority_profile: str = Field(min_length=1)
    publication_effect: str = Field(min_length=1)
    reopening_trigger_refs: tuple[str, ...] = Field(default=())
    lifecycle_event_refs: tuple[str, ...] = Field(default=())
    recourse_pointer: PolicyDesignCaseRecoursePointer | None = None
    recourse_outcome_refs: tuple[str, ...] = Field(default=())
    ingestion_event_refs: tuple[str, ...] = Field(default=())
    public_projection_effect: str = Field(min_length=1)


class PolicyDesignCaseDeficitProjection(BaseModel):
    """Projection row for a deficit that constrains authority or publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deficit_id: str = Field(min_length=1)
    deficit_family: str = Field(min_length=1)
    deficit_code: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = Field(default=())
    authority_level: str = Field(min_length=1)
    audience_scope: str = Field(min_length=1)
    disposition: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    ttl_expires_at: datetime | None = None
    runtime_event_ref: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    support_cap: str | None = None
    readiness_cap: str | None = None
    max_audience: str | None = None
    public_limitation_note: str | None = None
    review_refs: tuple[str, ...] = Field(default=())


class PolicyDesignCaseParticipationRequirementProjection(BaseModel):
    """Privacy-safe participation requirement/evaluation row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    participation_ref: str | None = None
    claim_use_requested: str = Field(min_length=1)
    claim_use_allowed: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    consultation_mode: str | None = None
    provenance_class: str = Field(min_length=1)
    representativeness_class: str = Field(min_length=1)
    public_projection_effect: str = Field(min_length=1)
    downgrade_reason: str | None = None
    blocker_code: str | None = None
    limitations: tuple[str, ...] = Field(default=())
    privacy_constraints: tuple[str, ...] = Field(default=())
    raw_materials_redacted: bool = True
    evidence_ref: str | None = None
    audience_visibility: tuple[PolicyDesignCaseAudience, ...] = Field(default=())


class PolicyDesignCaseInvariantSummary(BaseModel):
    """Projection summary of invariant and formal-substrate reader results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(default="not_provided", min_length=1)
    passing_count: int = Field(default=0, ge=0)
    failing_count: int = Field(default=0, ge=0)
    blocker_codes: tuple[str, ...] = Field(default=())
    evidence_refs: tuple[str, ...] = Field(default=())
    details: dict[str, Any] = Field(default_factory=dict)


class PolicyDesignCaseProjection(BaseModel):
    """Typed, non-authoritative multi-audience Policy Design Case projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION] = (
        POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION
    )
    generated_at: datetime
    surface: str = Field(min_length=1)
    audience: PolicyDesignCaseAudience
    policy_design_case_id: str | None = None
    run_id: str | None = None
    source_ref: str | None = None
    source_ref_fingerprint: str | None = None
    primary_state: str = Field(min_length=1)
    states: tuple[str, ...] = Field(default=())
    labels: tuple[PolicyDesignCaseProjectionLabel, ...] = Field(default=())
    closeout_truth: PolicyDesignCaseCloseoutTruth
    projection_gaps: tuple[PolicyDesignCaseProjectionGap, ...] = Field(default=())
    omission_manifest: tuple[PolicyDesignCaseProjectionOmission, ...] = Field(default=())
    contested_records: tuple[PolicyDesignCaseContestedRecord, ...] = Field(default=())
    recourse_pointer: PolicyDesignCaseRecoursePointer | None = None
    deficit_register: tuple[PolicyDesignCaseDeficitProjection, ...] = Field(default=())
    participation_requirements: tuple[
        PolicyDesignCaseParticipationRequirementProjection, ...
    ] = Field(default=())
    invariant_summary: PolicyDesignCaseInvariantSummary = Field(
        default_factory=PolicyDesignCaseInvariantSummary
    )
    authority_role: Literal["projection_only"] = "projection_only"
    projection_policy: Literal[
        "reads_policy_design_case_only",
        "reads_runtime_policy_design_case_graph",
    ] = "reads_policy_design_case_only"
    authoritative_for: tuple[str, ...] = Field(default=())
    evidence_class: str = Field(min_length=1)
    provenance_kind: Literal["runtime_projection"] = "runtime_projection"
    redacted: bool = False
    redaction_summary: dict[str, Any] = Field(default_factory=dict)
    audit_refs: tuple[str, ...] = Field(default=())
    source_authority_refs: dict[str, str] = Field(default_factory=dict)
    source_state: dict[str, Any] = Field(default_factory=dict)
    may_be_used_for: tuple[str, ...] = Field(default=())
    may_not_be_used_for: tuple[str, ...] = Field(default=())
    capability_reality_state: str = Field(default="implemented", min_length=1)
    contract_verification_status: str = Field(default="not_verified", min_length=1)
    contract_verification_refs: tuple[str, ...] = Field(default=())

    @model_validator(mode="after")
    def _enforce_projection_only_boundary(self) -> PolicyDesignCaseProjection:
        forbidden_uses = set(self.may_not_be_used_for)
        required_forbidden = {
            "claim_authority",
            "runtime_closeout_authority",
            "scorecard_authority",
        }
        if self.authoritative_for:
            raise ValueError("Policy Design Case projections cannot be authoritative_for any slot")
        if not required_forbidden <= forbidden_uses:
            raise ValueError(
                "Policy Design Case projections must forbid claim, scorecard, and closeout use"
            )
        return self


class PolicyDesignCaseProjectionConsumerContract(BaseModel):
    """Verification row for an audience-specific projection consumer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    consumer: PolicyDesignCaseAudience
    status: Literal["pass", "fail"]
    issue_codes: tuple[str, ...] = Field(default=())
    verified_fields: tuple[str, ...] = Field(default=())


__all__ = [
    "POLICY_DESIGN_CASE_PROJECTION_SCHEMA_VERSION",
    "RECOURSE_POINTER_SCHEMA_VERSION",
    "PolicyDesignCaseAudience",
    "PolicyDesignCaseCloseoutTruth",
    "PolicyDesignCaseContestedRecord",
    "PolicyDesignCaseDeficitProjection",
    "PolicyDesignCaseInvariantSummary",
    "PolicyDesignCaseParticipationRequirementProjection",
    "PolicyDesignCaseProjection",
    "PolicyDesignCaseProjectionBlocker",
    "PolicyDesignCaseProjectionConsumerContract",
    "PolicyDesignCaseProjectionGap",
    "PolicyDesignCaseProjectionLabel",
    "PolicyDesignCaseProjectionOmission",
    "PolicyDesignCaseRecoursePointer",
]
