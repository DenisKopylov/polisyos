"""Strict contracts for accountable runtime human decisions.

These models distinguish signed institutional inputs from the PolicyOS custody
signature applied to a persisted decision record.  Serializable gate results
are projections only: operational consumers must re-resolve the referenced
artifacts through :class:`HumanDecisionService` immediately before use.
"""

from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003 - public runtime validator annotation
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from polisyos.core import canon
from polisyos.pdc import AuthorityBoundary, Layer2ReadinessModel
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    HUMAN_DECISION_RECORD_V2,
    DecisionAction,
    DecisionRole,
    FiveRightsRequirement,
    HumanDecisionFiveRightsBinding,
    HumanDecisionRecord,
    HumanDecisionRequest,
)

HUMAN_DECISION_RECORD_MANIFEST_VERSION = "2.0"
HUMAN_DECISION_RECORD_ARTIFACT_KIND = "runtime_quality.agent_action_human_decision"

HUMAN_DECISION_PRINCIPAL_BINDING_V1: Literal[
    "policyos.runtime.human_decision_principal_binding.v1"
] = "policyos.runtime.human_decision_principal_binding.v1"
HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION = "1.0"
HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND = "runtime_quality.human_decision_principal_binding"

REVIEWER_SEPARATION_CREDENTIAL_V1: Literal["policyos.runtime.reviewer_separation_credential.v1"] = (
    "policyos.runtime.reviewer_separation_credential.v1"
)
REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION = "1.0"
REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND = "runtime_quality.reviewer_separation_credential"

HUMAN_DECISION_PRESENTATION_CONTRACT_V1: Literal[
    "policyos.runtime.human_decision_presentation_contract.v1"
] = "policyos.runtime.human_decision_presentation_contract.v1"
HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION = "1.0"
HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND = (
    "runtime_quality.human_decision_presentation_contract"
)

PRODUCTION_HUMAN_DECISION_BASIS_V1: Literal[
    "policyos.runtime.production_human_decision_basis.v1"
] = "policyos.runtime.production_human_decision_basis.v1"
PRODUCTION_HUMAN_DECISION_BASIS_MANIFEST_VERSION = "1.0"
PRODUCTION_HUMAN_DECISION_BASIS_ARTIFACT_KIND = "runtime_quality.production_human_decision_basis"

HUMAN_DECISION_EXPOSURE_SESSION_V1: Literal[
    "policyos.runtime.human_decision_exposure_session.v1"
] = "policyos.runtime.human_decision_exposure_session.v1"
HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION = "1.0"
HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND = "runtime_quality.human_decision_exposure_session"

HUMAN_DECISION_EXPOSURE_EVENT_V1: Literal["policyos.runtime.human_decision_exposure_event.v1"] = (
    "policyos.runtime.human_decision_exposure_event.v1"
)
HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION = "1.0"
HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND = "runtime_quality.human_decision_exposure_event"

_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_ACTION_KIND_PATTERN = r"^[a-z][a-z0-9_.:-]*$"

HumanDecisionSourceKind = Literal[
    "agent_action_authority",
    "production_approval",
]
HumanDecisionGateStatus = Literal[
    "invalid_source",
    "artifact_missing",
    "producer_missing",
    "revalidation_required",
    "blocked",
    "available",
]
HumanDecisionMode = Literal["ordinary", "override", "blocking"]
HumanDecisionPredicate = Literal[
    "identity_permission",
    "role_mandate_or_basis",
    "operation_accountability",
    "currentness",
    "right_decision_time",
    "reviewer_independence_change",
    "evidence_exposure",
    "presentation_format_channel",
    "source_producer_trust",
]
HumanDecisionPredicateProvenance = Literal[
    "recomputed",
    "independently_reconciled",
]

_GATE_PRECEDENCE: tuple[HumanDecisionGateStatus, ...] = (
    "invalid_source",
    "artifact_missing",
    "producer_missing",
    "revalidation_required",
    "blocked",
    "available",
)


class HumanDecisionTrustedProducer(Layer2ReadinessModel):
    """One exact manifest and signer identity admitted by deployment trust."""

    artifact_kind: str = Field(min_length=1, max_length=200)
    schema_name: str = Field(min_length=1, max_length=240)
    schema_version: str = Field(min_length=1, max_length=80)
    signer_identity: str = Field(min_length=1, max_length=300)

    @property
    def manifest_key(self) -> tuple[str, str, str]:
        """Return the exact manifest tuple governed by this row."""

        return self.artifact_kind, self.schema_name, self.schema_version


class HumanDecisionTrustPolicy(Layer2ReadinessModel):
    """Frozen deployment trust rows used for source-artifact admission."""

    verifier_epoch: str = Field(min_length=1, max_length=200)
    trusted_producers: tuple[HumanDecisionTrustedProducer, ...] = ()

    @model_validator(mode="after")
    def _unique_manifest_rows(self) -> Self:
        keys = tuple(row.manifest_key for row in self.trusted_producers)
        if len(keys) != len(set(keys)):
            raise ValueError("human-decision trust policy has duplicate manifest rows")
        return self

    def producer_for(
        self,
        *,
        artifact_kind: str,
        schema_name: str,
        schema_version: str,
    ) -> HumanDecisionTrustedProducer | None:
        """Return the exact trusted row or ``None`` without fuzzy matching."""

        key = artifact_kind, schema_name, schema_version
        return next(
            (row for row in self.trusted_producers if row.manifest_key == key),
            None,
        )


class HumanDecisionResolverPolicy(Layer2ReadinessModel):
    """Deployment-owned consumer and permission bindings for one resolver."""

    expected_consumer: str = Field(min_length=1, max_length=240)
    expected_audience: str = Field(min_length=1, max_length=240)
    principal_audience: str = Field(min_length=1, max_length=240)
    expected_agent_operation: str | None = Field(default=None, min_length=1, max_length=240)
    required_permission: str = Field(min_length=1, max_length=160)


class HumanDecisionWriteContext(Layer2ReadinessModel):
    """Server-derived writer identity; it is never accepted from caller DTOs."""

    tenant_id: str = Field(min_length=1, max_length=200)
    cell_id: str | None = Field(default=None, min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    job_id: str = Field(min_length=1, max_length=200)
    trace_id: str = Field(min_length=1, max_length=200)
    span_id: str = Field(min_length=1, max_length=200)
    parent_span_id: str | None = Field(default=None, min_length=1, max_length=200)
    owner: str = Field(min_length=1, max_length=200)
    requested_execution_profile: str = Field(min_length=1, max_length=80)
    effective_execution_profile: str = Field(min_length=1, max_length=80)
    effective_mode_ref: str = Field(min_length=1, max_length=300)
    degradation_ledger_ref: str | None = Field(default=None, min_length=1, max_length=300)


class HumanDecisionPrincipalBinding(Layer2ReadinessModel):
    """Signed principal identity, role, permission, and validity binding."""

    schema_version: Literal["policyos.runtime.human_decision_principal_binding.v1"] = (
        HUMAN_DECISION_PRINCIPAL_BINDING_V1
    )
    binding_id: str = Field(min_length=1, max_length=180)
    binding_ref: str = Field(min_length=1, max_length=300)
    tenant_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    principal_issuer: str = Field(min_length=1, max_length=300)
    principal_audience: str = Field(min_length=1, max_length=300)
    principal_subject: str = Field(min_length=1, max_length=300)
    actor_ref: str = Field(min_length=1, max_length=300)
    actor_key_id: str = Field(min_length=1, max_length=200)
    decision_roles: tuple[DecisionRole, ...] = Field(min_length=1, max_length=20)
    permissions: tuple[str, ...] = Field(min_length=1, max_length=40)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    verifier_epoch: str = Field(min_length=1, max_length=200)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(min_length=1, max_length=300)
    issued_at: AwareDatetime

    @model_validator(mode="after")
    def _valid_interval(self) -> Self:
        if self.valid_until <= self.valid_from:
            raise ValueError("principal binding validity interval is empty")
        if len(self.decision_roles) != len(set(self.decision_roles)):
            raise ValueError("principal binding decision roles must be unique")
        if len(self.permissions) != len(set(self.permissions)):
            raise ValueError("principal binding permissions must be unique")
        return self


class ReviewerSeparationCredential(Layer2ReadinessModel):
    """Signed reviewer-independence and exact change-authority credential."""

    schema_version: Literal["policyos.runtime.reviewer_separation_credential.v1"] = (
        REVIEWER_SEPARATION_CREDENTIAL_V1
    )
    credential_id: str = Field(min_length=1, max_length=180)
    credential_ref: str = Field(min_length=1, max_length=300)
    tenant_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    case_id: str = Field(min_length=1, max_length=200)
    decision_request_ref: str = Field(min_length=1, max_length=300)
    decision_request_digest: str = Field(pattern=_SHA256_PATTERN)
    reviewer_actor_ref: str = Field(min_length=1, max_length=300)
    reviewed_actor_refs: tuple[str, ...] = Field(min_length=1, max_length=40)
    independence_established: bool
    change_authority_actions: tuple[DecisionAction, ...] = Field(
        min_length=1,
        max_length=5,
    )
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    verifier_epoch: str = Field(min_length=1, max_length=200)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(min_length=1, max_length=300)
    issued_at: AwareDatetime

    @model_validator(mode="after")
    def _valid_interval(self) -> Self:
        if self.valid_until <= self.valid_from:
            raise ValueError("reviewer separation validity interval is empty")
        return self


class HumanDecisionPresentationContract(Layer2ReadinessModel):
    """Signed format/channel contract for the pre-action presentation."""

    schema_version: Literal["policyos.runtime.human_decision_presentation_contract.v1"] = (
        HUMAN_DECISION_PRESENTATION_CONTRACT_V1
    )
    contract_id: str = Field(min_length=1, max_length=180)
    contract_ref: str = Field(min_length=1, max_length=300)
    tenant_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    decision_request_ref: str = Field(min_length=1, max_length=300)
    decision_request_digest: str = Field(pattern=_SHA256_PATTERN)
    required_artifact_digests: tuple[str, ...] = Field(min_length=1, max_length=80)
    renderer_id: str = Field(min_length=1, max_length=240)
    renderer_version: str = Field(min_length=1, max_length=80)
    channel: str = Field(min_length=1, max_length=160)
    representation: Literal["full", "redacted", "truncated"]
    redaction_policy_ref: str | None = Field(default=None, max_length=300)
    truncation_policy_ref: str | None = Field(default=None, max_length=300)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    verifier_epoch: str = Field(min_length=1, max_length=200)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(min_length=1, max_length=300)
    issued_at: AwareDatetime

    @model_validator(mode="after")
    def _representation_policy(self) -> Self:
        if self.valid_until <= self.valid_from:
            raise ValueError("presentation contract validity interval is empty")
        if self.representation == "redacted" and not self.redaction_policy_ref:
            raise ValueError("redacted presentation requires a redaction policy")
        if self.representation == "truncated" and not self.truncation_policy_ref:
            raise ValueError("truncated presentation requires a truncation policy")
        if self.representation == "full" and (
            self.redaction_policy_ref is not None or self.truncation_policy_ref is not None
        ):
            raise ValueError("full presentation cannot carry reduction policy refs")
        return self


class ProductionHumanDecisionBasis(Layer2ReadinessModel):
    """Signed production basis; its producer remains foreign to DS9."""

    schema_version: Literal["policyos.runtime.production_human_decision_basis.v1"] = (
        PRODUCTION_HUMAN_DECISION_BASIS_V1
    )
    basis_id: str = Field(min_length=1, max_length=180)
    basis_ref: str = Field(min_length=1, max_length=300)
    tenant_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    case_id: str = Field(min_length=1, max_length=200)
    governed_action_key: str = Field(pattern=_SHA256_PATTERN)
    decision_request: HumanDecisionRequest
    requester_actor_ref: str = Field(min_length=1, max_length=300)
    decision_request_ref: str = Field(min_length=1, max_length=300)
    decision_request_digest: str = Field(pattern=_SHA256_PATTERN)
    mandate_record_ref: str = Field(min_length=1, max_length=300)
    mandate_owner_ref: str = Field(min_length=1, max_length=300)
    operation_id: str = Field(min_length=1, max_length=200)
    action_kind: str = Field(pattern=_ACTION_KIND_PATTERN, max_length=120)
    decision_rights_matrix_ref: str = Field(min_length=1, max_length=300)
    required_role: str = Field(min_length=1, max_length=120)
    offered_actions: tuple[DecisionAction, ...] = Field(min_length=1, max_length=5)
    scorecard_ref: str = Field(min_length=1, max_length=300)
    scorecard_digest: str = Field(pattern=_SHA256_PATTERN)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    verifier_epoch: str = Field(min_length=1, max_length=200)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(min_length=1, max_length=300)
    issued_at: AwareDatetime

    @model_validator(mode="after")
    def _valid_interval(self) -> Self:
        if self.valid_until <= self.valid_from:
            raise ValueError("production human-decision basis interval is empty")
        request = self.decision_request
        request_digest = "sha256:" + canon.content_hash(
            canon.to_canonical_bytes(
                request.model_dump(mode="json"),
                canon.CanonSpec(forbid_floats=False),
            )
        )
        if (
            self.decision_request_ref != request.request_ref
            or self.decision_request_digest != request_digest
            or self.case_id != request.case_id
            or self.mandate_record_ref != request.s6_mandate_record_ref
            or self.decision_rights_matrix_ref != request.decision_rights_matrix_ref
            or self.required_role != request.required_role
            or self.offered_actions != tuple(request.available_actions)
            or self.rule_version_ref != request.rule_version_ref
            or self.authority_boundary != request.authority_boundary
        ):
            raise ValueError("production basis differs from its complete signed request")
        decision_ends = tuple(
            value
            for value in (request.decision_due_at, request.decidable_until)
            if value is not None
        )
        if self.valid_from < request.requested_at or any(
            self.valid_until > boundary for boundary in decision_ends
        ):
            raise ValueError("production basis validity exceeds the request decision window")
        return self


class HumanDecisionExposureSession(Layer2ReadinessModel):
    """Custody-signed, one-request evidence delivery session."""

    schema_version: Literal["policyos.runtime.human_decision_exposure_session.v1"] = (
        HUMAN_DECISION_EXPOSURE_SESSION_V1
    )
    session_id: str = Field(min_length=1, max_length=180)
    session_ref: str = Field(min_length=1, max_length=300)
    tenant_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    principal_binding_ref: str = Field(pattern=_SHA256_PATTERN)
    principal_binding_digest: str = Field(pattern=_SHA256_PATTERN)
    principal_subject: str = Field(min_length=1, max_length=300)
    actor_ref: str = Field(min_length=1, max_length=300)
    decision_request_ref: str = Field(min_length=1, max_length=300)
    decision_request_digest: str = Field(pattern=_SHA256_PATTERN)
    basis_digest: str = Field(pattern=_SHA256_PATTERN)
    required_artifact_digests: tuple[str, ...] = Field(min_length=1, max_length=80)
    presentation_contract_ref: str = Field(pattern=_SHA256_PATTERN)
    presentation_contract_digest: str = Field(pattern=_SHA256_PATTERN)
    renderer_id: str = Field(min_length=1, max_length=240)
    renderer_version: str = Field(min_length=1, max_length=80)
    channel: str = Field(min_length=1, max_length=160)
    representation: Literal["full", "redacted", "truncated"]
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    verifier_epoch: str = Field(min_length=1, max_length=200)
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(min_length=1, max_length=300)
    issued_at: AwareDatetime

    @model_validator(mode="after")
    def _valid_interval(self) -> Self:
        if self.valid_until <= self.valid_from:
            raise ValueError("exposure session validity interval is empty")
        if self.principal_binding_ref != self.principal_binding_digest:
            raise ValueError("exposure session principal binding digest changed")
        return self


class HumanDecisionExposureAuditEvent(Layer2ReadinessModel):
    """Top-level completed-byte receipt stored in the existing access trail."""

    schema_version: Literal["policyos.runtime.human_decision_exposure_event.v1"] = (
        HUMAN_DECISION_EXPOSURE_EVENT_V1
    )
    event_type: Literal["runtime.human_decision.exposure"] = "runtime.human_decision.exposure"
    timestamp: float
    event_id: str = Field(min_length=1, max_length=220)
    event_ref: str = Field(min_length=1, max_length=300)
    event_receipt_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    tenant_id: str = Field(min_length=1, max_length=200)
    actor_ref: str = Field(min_length=1, max_length=300)
    run_id: str = Field(min_length=1, max_length=200)
    request_ref: str = Field(min_length=1, max_length=300)
    request_digest: str = Field(pattern=_SHA256_PATTERN)
    basis_digest: str = Field(pattern=_SHA256_PATTERN)
    session_ref: str = Field(pattern=_SHA256_PATTERN)
    artifact_id: str = Field(pattern=_SHA256_PATTERN)
    content_digest: str = Field(pattern=_SHA256_PATTERN)
    delivered_bytes: int = Field(gt=0)
    allowed_multiplicity: int = Field(gt=0, le=80)
    verifier_epoch: str = Field(min_length=1, max_length=200)


class HumanDecisionGateReason(Layer2ReadinessModel):
    """One surfaced, typed reason contributing to a gate status."""

    code: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=500)
    status: HumanDecisionGateStatus


def select_human_decision_gate_status(
    reasons: Sequence[HumanDecisionGateReason],
) -> HumanDecisionGateStatus:
    """Reduce all reasons by the fixed fail-closed precedence lattice."""

    if not reasons:
        return "available"
    statuses = {reason.status for reason in reasons}
    return next(status for status in _GATE_PRECEDENCE if status in statuses)


class _HumanDecisionGateInputBase(Layer2ReadinessModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    decision_request_ref: str | None = Field(default=None, min_length=1, max_length=300)
    decision_request_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    basis_ref: str | None = Field(default=None, min_length=1, max_length=300)
    principal_binding_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    reviewer_separation_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    presentation_contract_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    exposure_session_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    basis_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)


class HumanDecisionPA2GateInput(_HumanDecisionGateInputBase):
    """Pre-action S7 source selector; it carries no caller-authored authority."""

    source_kind: Literal["agent_action_authority"]
    source_ref: str = Field(pattern=_SHA256_PATTERN)
    action_kind: str = Field(pattern=_ACTION_KIND_PATTERN, max_length=120)


class HumanDecisionProductionGateInput(_HumanDecisionGateInputBase):
    """Production selector whose positive producer is intentionally foreign."""

    source_kind: Literal["production_approval"]
    source_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    production_packet_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)


HumanDecisionGateInput = Annotated[
    HumanDecisionPA2GateInput | HumanDecisionProductionGateInput,
    Field(discriminator="source_kind"),
]


class HumanDecisionGateResult(Layer2ReadinessModel):
    """Non-authoritative projection of a freshly resolved pre-action gate."""

    status: HumanDecisionGateStatus
    reasons: tuple[HumanDecisionGateReason, ...]
    source_kind: HumanDecisionSourceKind
    tenant_id: str
    run_id: str
    decision_request_ref: str | None
    decision_request_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    governed_action_key: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    required_artifact_digests: tuple[str, ...] = ()
    exposure_event_refs: tuple[str, ...] = ()
    resolved_at: AwareDatetime
    verifier_epoch: str
    operational_authority: Literal[False] = False

    @model_validator(mode="after")
    def _status_matches_reasons(self) -> Self:
        if self.status != select_human_decision_gate_status(self.reasons):
            raise ValueError("human-decision gate status does not match its reasons")
        return self


class HumanDecisionRequestSurface(Layer2ReadinessModel):
    """Signed request fields required to understand the offered action."""

    case_id: str = Field(min_length=1, max_length=200)
    delegation_contract_ref: str = Field(min_length=1, max_length=300)
    decision_rights_matrix_ref: str = Field(min_length=1, max_length=300)
    required_role: DecisionRole
    available_actions: tuple[DecisionAction, ...]
    requested_at: AwareDatetime
    decision_due_at: AwareDatetime | None = None
    decidable_until: AwareDatetime | None = None
    five_rights_requirements: FiveRightsRequirement
    five_rights_binding: HumanDecisionFiveRightsBinding


class HumanDecisionMandateSurface(Layer2ReadinessModel):
    """Mandate-owner envelope shown before any decision action."""

    mandate_record_ref: str = Field(min_length=1, max_length=300)
    mandate_owner_ref: str = Field(min_length=1, max_length=300)
    operation_id: str = Field(min_length=1, max_length=200)
    action_kind: str = Field(min_length=1, max_length=120)
    valid_from: AwareDatetime
    valid_until: AwareDatetime


class HumanDecisionExposureSurface(Layer2ReadinessModel):
    """Exact evidence-session and completed-delivery projection."""

    exposure_session_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    required_artifact_digests: tuple[str, ...]
    completed_artifact_digests: tuple[str, ...]
    renderer_id: str | None = Field(default=None, min_length=1, max_length=240)
    renderer_version: str | None = Field(default=None, min_length=1, max_length=80)
    channel: str | None = Field(default=None, min_length=1, max_length=160)
    representation: Literal["full", "redacted", "truncated"] | None = None


class HumanDecisionContestabilitySurface(Layer2ReadinessModel):
    """Case/source-bound internal appeal navigation; never an appeal outcome."""

    case_id: str = Field(min_length=1, max_length=200)
    source_ref: str = Field(pattern=_SHA256_PATTERN)
    href: str = Field(min_length=1, max_length=1_000)


class HumanDecisionGateResponse(Layer2ReadinessModel):
    """REVIEWER/EXPERT/MACHINE projection of one freshly resolved gate."""

    status: HumanDecisionGateStatus
    reasons: tuple[HumanDecisionGateReason, ...]
    reason_codes: tuple[str, ...]
    source_kind: HumanDecisionSourceKind
    source_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    tenant_id: str
    run_id: str
    decision_request_ref: str | None
    decision_request_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    governed_action_key: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    decision_request: HumanDecisionRequestSurface | None = None
    mandate: HumanDecisionMandateSurface | None = None
    exposure: HumanDecisionExposureSurface
    contestability: HumanDecisionContestabilitySurface | None = None
    resolved_at: AwareDatetime
    verifier_epoch: str
    operational_authority: Literal[False] = False

    @model_validator(mode="after")
    def _surface_matches_gate(self) -> Self:
        if self.status != select_human_decision_gate_status(self.reasons):
            raise ValueError("human-decision surface status does not match reasons")
        if self.reason_codes != tuple(reason.code for reason in self.reasons):
            raise ValueError("human-decision surface reason codes changed order")
        if self.contestability is not None and (
            self.source_ref != self.contestability.source_ref
            or self.decision_request is None
            or self.decision_request.case_id != self.contestability.case_id
        ):
            raise ValueError("contestability requires exact case/source binding")
        return self


class HumanDecisionCreateResponse(Layer2ReadinessModel):
    """Durable v2 readback returned only after custody reconciliation."""

    run_id: str = Field(min_length=1, max_length=200)
    record_ref: str = Field(pattern=_SHA256_PATTERN)
    record_digest: str = Field(pattern=_SHA256_PATTERN)
    record: HumanDecisionRecord
    durable_event_id: str = Field(min_length=1, max_length=300)
    reservation_id: str = Field(min_length=1, max_length=200)
    reservation_version: int = Field(ge=1)

    @model_validator(mode="after")
    def _exact_record_ref(self) -> Self:
        if self.record_ref != self.record_digest:
            raise ValueError("human-decision response record ref/digest changed")
        if self.record.record_ref != self.record_ref:
            raise ValueError("human-decision response record readback changed")
        return self


class HumanDecisionCreateCommand(Layer2ReadinessModel):
    """Caller decision fields; all authority-bearing fields are deliberately absent."""

    gate_input: HumanDecisionGateInput
    decision_action: DecisionAction
    decision_mode: HumanDecisionMode
    accountability_statement: str = Field(min_length=1, max_length=500)
    dissent_statement: str = Field(min_length=1, max_length=1_000)
    override_reason: str | None = Field(default=None, min_length=1, max_length=1_000)
    blocking_reason: str | None = Field(default=None, min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def _decision_shape(self) -> Self:
        if self.decision_mode == "ordinary":
            if self.decision_action not in {
                "approve",
                "request_evidence",
                "revise_scope",
                "escalate",
            }:
                raise ValueError("ordinary decision action is not admitted")
            if self.override_reason is not None or self.blocking_reason is not None:
                raise ValueError("ordinary decisions cannot carry override/blocking reasons")
        elif self.decision_mode == "override":
            if self.decision_action != "approve" or self.override_reason is None:
                raise ValueError("override requires approve plus an override reason")
            if self.blocking_reason is not None:
                raise ValueError("override cannot carry a blocking reason")
        else:
            if self.decision_action != "reject" or self.blocking_reason is None:
                raise ValueError("blocking requires reject plus a blocking reason")
            if self.override_reason is not None:
                raise ValueError("blocking cannot carry an override reason")
        return self


class _HumanDecisionGatewayAdapterBase(Layer2ReadinessModel):
    tenant_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    decision_request_ref: str = Field(min_length=1, max_length=300)
    decision_request_digest: str = Field(pattern=_SHA256_PATTERN)
    record_ref: str = Field(pattern=_SHA256_PATTERN)
    record_digest: str = Field(pattern=_SHA256_PATTERN)
    source_ref: str = Field(pattern=_SHA256_PATTERN)
    source_digest: str = Field(pattern=_SHA256_PATTERN)
    basis_digest: str = Field(pattern=_SHA256_PATTERN)
    record_schema_version: Literal["policyos.runtime.human_decision_record.v2"] = (
        HUMAN_DECISION_RECORD_V2
    )
    rule_version_ref: str = Field(min_length=1, max_length=300)
    verifier_epoch: str = Field(min_length=1, max_length=200)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    expected_consumer: str = Field(min_length=1, max_length=240)
    expected_operation: str = Field(min_length=1, max_length=240)
    expected_audience: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def _valid_interval_and_digests(self) -> Self:
        if self.valid_until <= self.valid_from:
            raise ValueError("gateway adapter validity interval is empty")
        if self.record_ref != self.record_digest:
            raise ValueError("record ref and digest must be exactly content-bound")
        if self.source_ref != self.source_digest:
            raise ValueError("source ref and digest must be exactly content-bound")
        return self


class HumanDecisionPA2GatewayAdapterInput(_HumanDecisionGatewayAdapterBase):
    """S7-only operational adapter; production fields are structurally forbidden."""

    source_kind: Literal["agent_action_authority"]
    delegation_contract_ref: str = Field(pattern=_SHA256_PATTERN)
    delegation_contract_digest: str = Field(pattern=_SHA256_PATTERN)
    delegation_envelope_ref: str = Field(min_length=1, max_length=300)
    delegation_envelope_digest: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _contract_digest_matches(self) -> Self:
        if self.delegation_contract_ref != self.delegation_contract_digest:
            raise ValueError("delegation contract ref and digest must match")
        return self


class HumanDecisionProductionGatewayAdapterInput(_HumanDecisionGatewayAdapterBase):
    """Production-only adapter; S7 fields are structurally forbidden."""

    source_kind: Literal["production_approval"]
    production_packet_ref: str = Field(pattern=_SHA256_PATTERN)
    production_packet_digest: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _packet_digest_matches(self) -> Self:
        if self.production_packet_ref != self.production_packet_digest:
            raise ValueError("production packet ref and digest must match")
        return self


HumanDecisionGatewayAdapterInput = Annotated[
    HumanDecisionPA2GatewayAdapterInput | HumanDecisionProductionGatewayAdapterInput,
    Field(discriminator="source_kind"),
]


__all__ = [
    "HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND",
    "HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION",
    "HUMAN_DECISION_EXPOSURE_EVENT_V1",
    "HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND",
    "HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION",
    "HUMAN_DECISION_EXPOSURE_SESSION_V1",
    "HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND",
    "HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION",
    "HUMAN_DECISION_PRESENTATION_CONTRACT_V1",
    "HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND",
    "HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION",
    "HUMAN_DECISION_PRINCIPAL_BINDING_V1",
    "HUMAN_DECISION_RECORD_ARTIFACT_KIND",
    "HUMAN_DECISION_RECORD_MANIFEST_VERSION",
    "HUMAN_DECISION_RECORD_V2",
    "PRODUCTION_HUMAN_DECISION_BASIS_ARTIFACT_KIND",
    "PRODUCTION_HUMAN_DECISION_BASIS_MANIFEST_VERSION",
    "PRODUCTION_HUMAN_DECISION_BASIS_V1",
    "REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND",
    "REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION",
    "REVIEWER_SEPARATION_CREDENTIAL_V1",
    "HumanDecisionContestabilitySurface",
    "HumanDecisionCreateCommand",
    "HumanDecisionCreateResponse",
    "HumanDecisionExposureAuditEvent",
    "HumanDecisionExposureSession",
    "HumanDecisionExposureSurface",
    "HumanDecisionGateInput",
    "HumanDecisionGateReason",
    "HumanDecisionGateResponse",
    "HumanDecisionGateResult",
    "HumanDecisionGateStatus",
    "HumanDecisionGatewayAdapterInput",
    "HumanDecisionMandateSurface",
    "HumanDecisionMode",
    "HumanDecisionPA2GateInput",
    "HumanDecisionPA2GatewayAdapterInput",
    "HumanDecisionPredicate",
    "HumanDecisionPredicateProvenance",
    "HumanDecisionPresentationContract",
    "HumanDecisionPrincipalBinding",
    "HumanDecisionProductionGateInput",
    "HumanDecisionProductionGatewayAdapterInput",
    "HumanDecisionRequestSurface",
    "HumanDecisionResolverPolicy",
    "HumanDecisionSourceKind",
    "HumanDecisionTrustPolicy",
    "HumanDecisionTrustedProducer",
    "HumanDecisionWriteContext",
    "ProductionHumanDecisionBasis",
    "ReviewerSeparationCredential",
    "select_human_decision_gate_status",
]
