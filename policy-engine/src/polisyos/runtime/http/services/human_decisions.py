"""Resolve and persist accountable, custodied human decisions.

The public gate result is a projection only.  This service retains the concrete
CAS, signature, event, and reservation re-resolution path and invokes it again
before every write or operational consumption.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from importlib import import_module
from math import isfinite
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common import logger as common_logger
from polisyos.core import artifacts, canon
from polisyos.pdc import AuthorityBoundary
from polisyos.runtime.http.services.human_decision_contracts import (
    HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
    HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
    HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
    HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
    HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
    HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
    HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
    HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
    HUMAN_DECISION_RECORD_ARTIFACT_KIND,
    HUMAN_DECISION_RECORD_MANIFEST_VERSION,
    PRODUCTION_HUMAN_DECISION_BASIS_ARTIFACT_KIND,
    PRODUCTION_HUMAN_DECISION_BASIS_MANIFEST_VERSION,
    REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
    REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
    HumanDecisionAllowedDecision,
    HumanDecisionCreateCommand,
    HumanDecisionExposureAuditEvent,
    HumanDecisionExposureSession,
    HumanDecisionExposureSurface,
    HumanDecisionGateInput,
    HumanDecisionGateReason,
    HumanDecisionGateResponse,
    HumanDecisionGateResult,
    HumanDecisionGateStatus,
    HumanDecisionGatewayAdapterInput,
    HumanDecisionMandateSurface,
    HumanDecisionPA2GateInput,
    HumanDecisionPA2GatewayAdapterInput,
    HumanDecisionPA2ReplaySelector,
    HumanDecisionPresentationContract,
    HumanDecisionPrincipalBinding,
    HumanDecisionProductionGateInput,
    HumanDecisionProductionReplaySelector,
    HumanDecisionRequestSurface,
    HumanDecisionResolverPolicy,
    HumanDecisionSubmissionSurface,
    HumanDecisionWriteContext,
    ProductionHumanDecisionBasis,
    ReviewerSeparationCredential,
    select_human_decision_gate_status,
)
from polisyos.runtime.quality.approval import ProductionApprovalPacket
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import (
    AuthorityReconciliationError,
)
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    HUMAN_DECISION_RECORD_V2,
    DelegatedActionEnvelope,
    DelegationContract,
    HumanDecisionCanonicalActor,
    HumanDecisionPredicateReceipt,
    HumanDecisionRecord,
    HumanDecisionRecordPredicate,
    HumanDecisionRecordPredicateProvenance,
    HumanDecisionRequest,
    ResponsibilityIntegrityCheck,
    derive_five_rights_check,
)

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from pathlib import Path

    from polisyos.runtime.http.access_audit import (
        ReservedHumanDecisionExposureEvent,
    )
    from polisyos.runtime.http.authorization import (
        ActionPermissionVerification,
        BoundActionPermissionVerification,
    )
    from polisyos.runtime.http.security import RuntimeHumanDecisionCustody

_TModel = TypeVar("_TModel", bound=BaseModel)
_RECORD_SCHEMA_NAME = "polisyos.runtime.HumanDecisionRecord"
_SOURCE_SCHEMA_NAME = "polisyos.runtime.AgentActionAuthorityDecision"
_SOURCE_ARTIFACT_KIND = "runtime_quality.agent_action_authority_decision"
_SOURCE_SCHEMA_VERSION = "policyos.runtime.agent_action_authority.v1"
_CONTRACT_ARTIFACT_KIND = "runtime_quality.agent_action_delegation_contract"
_CONTRACT_SCHEMA_NAME = "polisyos.runtime.DelegationContract"
_CONTRACT_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s7_delegation.v2"
_PRODUCTION_BASIS_SCHEMA_NAME = "polisyos.runtime.ProductionHumanDecisionBasis"
_PRODUCTION_APPROVAL_PACKET_KIND = "runtime.production_approval_" + "packet"
_PRODUCTION_APPROVAL_PACKET_SCHEMA_NAME = "polisyos.runtime.ProductionApprovalPacket"
_PRODUCTION_APPROVAL_PACKET_SCHEMA_VERSION = "2.0"
_PRODUCTION_APPROVAL_PACKET_SCHEMA_ID = "policyos.production_approval_" + "packet.v2"
_RAW_APPROVAL_READY = "approval_" + "ready"
_RAW_APPROVAL_STATE_FIELD = "approval_" + "state"
_QUALITY_SCORECARD_KIND = "runtime.quality_scorecard"
_QUALITY_SCORECARD_SCHEMA_NAME = "polisyos.runtime.QualityScorecard"
_QUALITY_SCORECARD_SCHEMA_VERSION = "1.0"
_RESERVATION_LEASE_SECONDS = 60

logger = common_logger.get_logger(__name__)


class AgentActionAuthorityDecision(Protocol):
    """Structural view of the dynamically loaded authority decision model."""

    outcome: str
    refusal_reasons: tuple[str, ...]
    action_kind: str
    case_id: str
    bound_resource_digest: str | None
    contract_ref: str | None
    contract_content_hash: str | None
    envelope_id: str | None
    envelope_ref: str | None
    envelope_predicate_provenance: str
    operation_content_hash: str
    invocation_id: str
    invocation_content_hash: str
    intent_content_hash: str
    operation_id: str
    operation_version: str
    admission_bundle_ref: str | None
    effect_binding_id: str | None
    effect_binding_digest: str | None
    effect_implementation_ref: str | None
    permission_snapshot: AgentActionPermissionSnapshot | None
    predicate_checks: tuple[AgentActionPredicateCheck, ...]
    rule_version_ref: str
    decided_at: datetime
    human_decision_request: HumanDecisionRequest | None


class AgentActionPermissionSnapshot(Protocol):
    """Structural view of the signed agent permission snapshot."""

    subject: str
    tenant_id: str
    roles: tuple[str, ...]
    required_permission: str
    granted_permissions: tuple[str, ...]
    resource_digest: str


class AgentActionPredicateCheck(Protocol):
    """Structural view of one signed source predicate receipt."""

    predicate: str
    satisfied: bool
    provenance: str


class _LiveOperation(Protocol):
    operation_id: str
    operation_version: str


class _LiveInvocation(Protocol):
    invocation_id: str


class _LiveIntent(Protocol):
    action_kind: str


class _LiveResolvedContract(Protocol):
    resolved_for_resource_digest: str
    contract_cas_ref: str
    contract_payload_hash: str


class _LiveEffectBinding(Protocol):
    binding_id: str
    binding_digest: str
    implementation_ref: str


class HumanDecisionUnavailableError(ValueError):
    """Expose one typed fail-closed gate result to a route or consumer."""

    def __init__(self, gate: HumanDecisionGateResult) -> None:
        self.gate = gate
        super().__init__(gate.status)


class HumanDecisionPersistenceError(RuntimeError):
    """Signal that record custody did not complete end to end."""


class HumanDecisionOperationalResolutionError(ValueError):
    """Reject a projection or stale record at the concrete consumer boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _SignedQualityScorecard(BaseModel):
    """Minimum strict authority-bearing scorecard envelope.

    Quality evidence remains extensible, but the identity fields that join the
    production decision chain are exact and independently verified by the
    signed-manifest reader.
    """

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        populate_by_name=True,
        strict=True,
    )

    schema_version: Literal["policyos.quality_scorecard.v1"]
    run_id: str = Field(min_length=1)
    quality_status: str = Field(min_length=1)
    approval_posture: str = Field(
        min_length=1,
        alias=_RAW_APPROVAL_STATE_FIELD,
    )


@dataclass(frozen=True, slots=True)
class HumanDecisionRecordReceipt:
    """Exact record, signature, event, and reservation readback receipt."""

    record: HumanDecisionRecord
    record_ref: str
    record_digest: str
    durable_event_id: str
    reservation_id: str
    reservation_version: int
    custody_signer_identity: str
    custody_key_id: str


@dataclass(frozen=True, slots=True)
class HumanDecisionExposureSessionReceipt:
    """Custody-signed session and durable authority-write readback."""

    session: HumanDecisionExposureSession
    session_ref: str
    session_digest: str
    durable_event_id: str
    custody_signer_identity: str
    custody_key_id: str


@dataclass(frozen=True, slots=True)
class HumanDecisionExposureDelivery:
    """Verified exact bytes and signed bindings admitted for one delivery."""

    session: HumanDecisionExposureSession
    session_ref: str
    artifact_ref: str
    content: bytes
    media_type: str
    allowed_multiplicity: int
    valid_until: datetime


@dataclass(frozen=True, slots=True)
class ResolvedProductionApprovalInputs:
    """Independently reconciled inputs retained behind the concrete resolver."""

    scorecard: Mapping[str, object]
    scorecard_ref: str
    scorecard_digest: str
    scorecard_signer_identity: str
    basis: ProductionHumanDecisionBasis
    basis_ref: str
    basis_signer_identity: str
    record: HumanDecisionRecord
    record_ref: str
    valid_from: datetime
    valid_until: datetime
    verifier_epoch: str


@dataclass(frozen=True, slots=True)
class ResolvedProductionApprovalPacket:
    """Signed packet plus freshly reconciled inputs, never an authority DTO."""

    packet: ProductionApprovalPacket
    packet_ref: str
    inputs: ResolvedProductionApprovalInputs


@dataclass(frozen=True, slots=True)
class ProductionApprovalPacketReceipt:
    """Custody signature, durable event, and exact readback for one V2 packet."""

    packet: ProductionApprovalPacket
    packet_ref: str
    durable_event_id: str
    custody_signer_identity: str
    custody_key_id: str


@dataclass(frozen=True, slots=True)
class _ResolvedSignedArtifact:
    model: BaseModel
    ref: str
    signer_identity: str
    key_id: str
    durable_event_id: str


@dataclass(frozen=True, slots=True)
class _ResolvedGate:
    projection: HumanDecisionGateResult
    source: AgentActionAuthorityDecision | None = None
    source_artifact_ref: str | None = None
    request: HumanDecisionRequest | None = None
    contract: DelegationContract | None = None
    contract_artifact_ref: str | None = None
    production_basis: ProductionHumanDecisionBasis | None = None
    production_basis_ref: str | None = None
    principal: HumanDecisionPrincipalBinding | None = None
    principal_artifact_ref: str | None = None
    separation: ReviewerSeparationCredential | None = None
    separation_artifact_ref: str | None = None
    presentation: HumanDecisionPresentationContract | None = None
    presentation_artifact_ref: str | None = None
    exposure_session: HumanDecisionExposureSession | None = None
    exposure_session_artifact_ref: str | None = None
    exposure_events: tuple[HumanDecisionExposureAuditEvent, ...] = ()
    predicate_receipts: tuple[HumanDecisionPredicateReceipt, ...] = ()
    valid_from: datetime | None = None
    valid_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class _ResolvedPA2OperationalAuthority:
    """Private output of signed-packet plus live-input reconciliation."""

    record: HumanDecisionRecord
    source: AgentActionAuthorityDecision
    request: HumanDecisionRequest
    contract: DelegationContract
    envelope: DelegatedActionEnvelope
    request_digest: str


class _ReservationRecord(Protocol):
    reservation_id: str
    reservation_version: int
    state: str
    binding_sha256: str
    record_valid_until: datetime
    record_ref: str | None
    record_sha256: str | None
    durable_event_id: str | None


class _ReservationResult(Protocol):
    acquired: bool
    issue_code: str | None
    reservation: _ReservationRecord


class _CasRef(Protocol):
    artifact_id: object


class _AuthorityWriteResult(Protocol):
    cas_ref: _CasRef
    payload_sha256: str


class _AuthorityReconciliation(Protocol):
    durable_event_id: str | None


class _SignatureVerification(Protocol):
    ok: bool
    signer_identity: str | None
    key_id: str | None


class _HumanDecisionWriteFence(Protocol):
    def commit(
        self,
        *,
        record_ref: str,
        record_sha256: str,
        durable_event_id: str,
        committed_at: datetime,
    ) -> _ReservationRecord: ...

    def recover(
        self,
        *,
        record_ref: str | None,
        record_sha256: str | None,
        durable_event_id: str | None,
    ) -> _ReservationRecord: ...


def _pa2_packet_join_issues(
    *,
    source: AgentActionAuthorityDecision,
    request: HumanDecisionRequest,
    contract: DelegationContract,
    principal: HumanDecisionPrincipalBinding,
    separation: ReviewerSeparationCredential,
    basis_ref: str | None,
    tenant_id: str,
    run_id: str,
    principal_audience: str,
    required_reviewer_permission: str,
    verifier_epoch: str,
    custody_key_id: str,
    now: datetime,
) -> tuple[DelegatedActionEnvelope | None, frozenset[str]]:
    """Recompute the signed PA2 packet join; no DTO echo can establish it."""

    issues: set[str] = set()
    request_digest = _sha256_ref(request.model_dump(mode="json"))
    rights_rows = tuple(
        row
        for row in contract.decision_rights_matrix_rows
        if row.decision_class_id == request.decision_class_id
    )
    if len(rights_rows) != 1:
        rights_row = None
        issues.add("source")
    else:
        rights_row = rights_rows[0]
    envelope = next(
        (row for row in contract.action_envelopes if row.envelope_id == source.envelope_id),
        None,
    )
    snapshot = source.permission_snapshot
    expected_source_checks = (
        ("verified_identity", True, "recomputed"),
        ("explicit_permission", True, "recomputed"),
        ("mandate_bounded_delegation", True, "independently_reconciled"),
        ("operation_in_envelope", False, "recomputed"),
        ("live_accountability", True, "recomputed"),
    )
    source_checks = tuple(
        (check.predicate, check.satisfied, check.provenance) for check in source.predicate_checks
    )
    provenance_required = {
        source.operation_content_hash,
        source.invocation_content_hash,
        source.intent_content_hash,
        *((source.contract_ref,) if source.contract_ref is not None else ()),
        *((source.bound_resource_digest,) if source.bound_resource_digest is not None else ()),
        *((source.effect_binding_digest,) if source.effect_binding_digest is not None else ()),
    }
    if (
        source.outcome != "refused"
        or source.refusal_reasons != ("operation_out_of_envelope",)
        or source_checks != expected_source_checks
        or request.decision_class_id != "mandate_boundary"
        or request.interaction_mode != "request_driven"
        or request.disposition != "request_human_decision"
        or set(request.need_reasons) != {"out_of_envelope"}
        or not provenance_required.issubset(request.provenance_refs)
        or not (request.requested_at <= source.decided_at <= now)
        or basis_ref is None
        or source.contract_ref != basis_ref
        or source.contract_content_hash != basis_ref
        or request.delegation_contract_ref != contract.contract_ref
        or source.case_id != request.case_id
        or request.case_id != contract.case_id
        or request.decision_rights_matrix_ref != contract.decision_rights_matrix_ref
        or request.s6_mandate_record_ref != contract.s6_mandate_record_ref
        or request.s6_mandate_firewall_disposition != contract.s6_mandate_firewall_disposition
        or request.rule_version_ref != contract.rule_version_ref
        or contract.s6_mandate_firewall_disposition != "pass"
        or envelope is None
        or snapshot is None
        or source.envelope_predicate_provenance != "recomputed"
    ):
        issues.add("source")
    if rights_row is not None and (
        request.required_role != rights_row.required_role
        or tuple(request.available_actions) != tuple(rights_row.available_actions)
    ):
        issues.add("source")
    if envelope is not None:
        snapshot_roles = set(snapshot.roles) if snapshot is not None else set()
        envelope_roles = {
            role.value if hasattr(role, "value") else str(role)
            for role in envelope.authorized_runtime_roles
        }
        envelope_permission = (
            envelope.required_permission.value
            if hasattr(envelope.required_permission, "value")
            else str(envelope.required_permission)
        )
        if (
            source.envelope_ref != envelope.envelope_ref
            or envelope.case_id != contract.case_id
            or envelope.mandate_owner_ref != contract.mandate_owner_ref
            or envelope.action_kind != source.action_kind
            or envelope.rule_version_ref != contract.rule_version_ref
            or envelope.required_tenant_id != tenant_id
            or snapshot is None
            or snapshot.subject != envelope.authorized_subject
            or snapshot.tenant_id != tenant_id
            or snapshot.required_permission != envelope_permission
            or envelope_permission not in snapshot.granted_permissions
            or envelope_roles.isdisjoint(snapshot_roles)
            or source.bound_resource_digest != envelope.required_resource_digest
            or snapshot.resource_digest != envelope.required_resource_digest
        ):
            issues.add("source")
        if (
            envelope.status != "active"
            or source.decided_at < envelope.valid_from
            or source.decided_at >= envelope.valid_until
            or now < envelope.valid_from
            or now >= envelope.valid_until
        ):
            issues.add("ttl")
    if (
        principal.actor_ref != contract.mandate_owner_ref
        or principal.actor_key_id == custody_key_id
    ):
        issues.add("principal")
    if (
        principal.tenant_id != tenant_id
        or principal.run_id != run_id
        or principal.principal_audience != principal_audience
    ):
        issues.add("principal")
    if (
        request.required_role not in principal.decision_roles
        or required_reviewer_permission not in principal.permissions
    ):
        issues.add("principal_authority")
    if (
        principal.verifier_epoch != verifier_epoch
        or principal.valid_from > now
        or now >= principal.valid_until
    ):
        issues.add("principal_current")
    reviewed_subject = snapshot.subject if snapshot is not None else None
    if (
        separation.tenant_id != tenant_id
        or separation.run_id != run_id
        or separation.case_id != request.case_id
        or separation.decision_request_ref != request.request_ref
        or separation.decision_request_digest != request_digest
        or separation.reviewer_actor_ref != principal.actor_ref
        or reviewed_subject is None
        or reviewed_subject not in separation.reviewed_actor_refs
        or principal.actor_ref == reviewed_subject
        or principal.actor_ref in separation.reviewed_actor_refs
        or not separation.independence_established
        or not set(request.available_actions).issubset(separation.change_authority_actions)
    ):
        issues.add("separation")
    if (
        separation.verifier_epoch != verifier_epoch
        or separation.valid_from > now
        or now >= separation.valid_until
    ):
        issues.add("separation_current")
    return envelope, frozenset(issues)


def _pa2_governed_action_key(
    *,
    source: AgentActionAuthorityDecision,
    contract: DelegationContract,
    envelope: DelegatedActionEnvelope,
    tenant_id: str,
    run_id: str,
) -> str:
    """Hash only the replay-stable owner action join serialized by the CAS."""

    return _sha256_ref(
        {
            "tenant_id": tenant_id,
            "run_id": run_id,
            "action_kind": source.action_kind,
            "operation_id": source.operation_id,
            "operation_version": source.operation_version,
            "operation_content_hash": source.operation_content_hash,
            "invocation_content_hash": source.invocation_content_hash,
            "intent_content_hash": source.intent_content_hash,
            "contract_ref": source.contract_ref,
            "contract_content_hash": source.contract_content_hash,
            "contract_logical_ref": contract.contract_ref,
            "bound_resource_digest": source.bound_resource_digest,
            "envelope_id": source.envelope_id,
            "envelope_ref": envelope.envelope_ref,
            "envelope_digest": _sha256_ref(envelope.model_dump(mode="json")),
            "effect_binding_digest": source.effect_binding_digest,
        }
    )


def _exposure_binding_issues(
    *,
    basis_ref: str,
    request: HumanDecisionRequest,
    principal: HumanDecisionPrincipalBinding,
    principal_ref: str,
    presentation: HumanDecisionPresentationContract,
    presentation_ref: str,
    session: HumanDecisionExposureSession,
    session_ref: str,
    events: Sequence[HumanDecisionExposureAuditEvent],
    now: datetime,
) -> frozenset[str]:
    """Recompute the exact signed presentation/session/event relationship."""

    issues: set[str] = set()
    request_digest = _sha256_ref(request.model_dump(mode="json"))
    presentation_required = tuple(presentation.required_artifact_digests)
    session_required = tuple(session.required_artifact_digests)
    rights_binding = request.five_rights_binding
    if (
        presentation.decision_request_ref != request.request_ref
        or presentation.decision_request_digest != request_digest
        or presentation.tenant_id != principal.tenant_id
        or presentation.run_id != principal.run_id
        or presentation.verifier_epoch != principal.verifier_epoch
    ):
        issues.add("presentation")
    if presentation.valid_from > now or now >= presentation.valid_until:
        issues.add("presentation_current")
    if Counter(presentation_required)[basis_ref] != 1:
        issues.add("mandate")
    expected_presentation = Counter(
        (
            basis_ref,
            *rights_binding.required_information_refs,
        )
    )
    if (
        not rights_binding.required_information_refs
        or Counter(presentation_required) != expected_presentation
    ):
        issues.add("evidence")
    if (
        presentation.channel != rights_binding.required_channel
        or presentation.representation != rights_binding.required_representation
    ):
        issues.add("presentation")
    if (
        session.actor_ref != principal.actor_ref
        or session.principal_subject != principal.principal_subject
        or session.principal_binding_ref != principal_ref
        or session.principal_binding_digest != principal_ref
        or session.tenant_id != principal.tenant_id
        or session.run_id != principal.run_id
        or session.verifier_epoch != principal.verifier_epoch
        or session.decision_request_ref != request.request_ref
        or session.decision_request_digest != request_digest
        or session.basis_digest != basis_ref
        or session.presentation_contract_ref != presentation_ref
        or session.presentation_contract_digest != presentation_ref
        or presentation_required != session_required
        or (
            session.renderer_id,
            session.renderer_version,
            session.channel,
            session.representation,
        )
        != (
            presentation.renderer_id,
            presentation.renderer_version,
            presentation.channel,
            presentation.representation,
        )
    ):
        issues.add("session")
    if session.valid_from > now or now >= session.valid_until:
        issues.add("session_current")

    valid_event_artifacts: list[str] = []
    for event in events:
        event_valid = (
            event.tenant_id == session.tenant_id
            and event.actor_ref == principal.actor_ref
            and event.run_id == session.run_id
            and event.request_ref == request.request_ref
            and event.request_digest == request_digest
            and event.basis_digest == session.basis_digest
            and event.session_ref == session_ref
            and event.verifier_epoch == session.verifier_epoch
            and event.content_digest == event.artifact_id
            and event.allowed_multiplicity == Counter(session_required)[event.artifact_id]
            and isfinite(event.timestamp)
        )
        if event_valid:
            try:
                event_time = datetime.fromtimestamp(event.timestamp, tz=UTC)
            except (OverflowError, OSError, ValueError):
                event_valid = False
            else:
                event_valid = (
                    session.valid_from <= event_time < session.valid_until and event_time <= now
                )
        if event_valid:
            valid_event_artifacts.append(event.artifact_id)
        else:
            issues.add("session")
    covered = Counter(valid_event_artifacts)
    expected = Counter(session_required)
    if any(count > expected[artifact_ref] for artifact_ref, count in covered.items()):
        issues.add("session")
    if covered[basis_ref] < expected[basis_ref]:
        issues.add("mandate")
    if any(
        artifact_ref != basis_ref and covered[artifact_ref] < required_count
        for artifact_ref, required_count in expected.items()
    ):
        issues.add("evidence")
    return frozenset(issues)


class HumanDecisionAuthoritySinkProtocol(Protocol):
    """Narrow structural type for the exact runtime-owned authority sink."""

    def reserve_action(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        binding_sha256: str,
        now: datetime,
        lease_seconds: int,
        record_valid_until: datetime,
    ) -> _ReservationResult: ...

    def get_reservation(
        self, *, tenant_id: str, governed_action_key: str
    ) -> _ReservationRecord | None: ...

    def get_reservation_generation(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_version: int,
    ) -> _ReservationRecord | None: ...

    def hold_write_fence(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        binding_sha256: str,
        acquired_at: datetime,
        expected_record_valid_until: datetime,
    ) -> AbstractContextManager[_HumanDecisionWriteFence]: ...

    def mark_recovery_required(
        self,
        *,
        tenant_id: str,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        record_ref: str | None = None,
        record_sha256: str | None = None,
        durable_event_id: str | None = None,
    ) -> _ReservationRecord: ...

    def reconcile_orphan_reservation(self, **kwargs: object) -> _ReservationRecord: ...

    def write_authority_artifact(
        self,
        payload: object,
        options: artifacts.ArtifactWriteOptions,
        *,
        authority_fields: Mapping[str, object],
    ) -> _AuthorityWriteResult: ...

    def reconcile_authority_artifact(
        self,
        artifact_ref: str,
        *,
        expected_tenant_id: str | None,
        expected_cell_id: str | None,
        expected_run_id: str | None,
        expected_job_id: str | None,
    ) -> _AuthorityReconciliation: ...

    def has_artifact(self, artifact_ref: str) -> bool: ...

    def get_artifact_bytes(self, artifact_ref: str) -> bytes: ...

    def get_artifact_manifest(self, artifact_ref: str) -> artifacts.ArtifactManifest: ...

    def get_artifact_signature(self, artifact_ref: str) -> object | None: ...

    def sign_artifact(
        self,
        artifact_ref: str,
        signer: object,
        *,
        signer_identity: str,
    ) -> object: ...

    def verify_artifact_signature(
        self,
        artifact_ref: str,
        verifier: object,
        *,
        strict_identity: bool = True,
    ) -> _SignatureVerification: ...


class _ResolutionIssueError(ValueError):
    def __init__(self, reason: HumanDecisionGateReason) -> None:
        self.reason = reason
        super().__init__(reason.code)


class HumanDecisionService:
    """Concrete resolver and writer over one attested custody/sink composition."""

    _sink: HumanDecisionAuthoritySinkProtocol
    _custody: RuntimeHumanDecisionCustody
    _resolver_policy: HumanDecisionResolverPolicy
    _access_audit_path: Path
    _clock: Callable[[], datetime]

    def __init__(
        self,
        *,
        authority_sink: HumanDecisionAuthoritySinkProtocol,
        custody: RuntimeHumanDecisionCustody,
        resolver_policy: HumanDecisionResolverPolicy,
        access_audit_path: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        control_lifecycle = import_module("polisyos.runtime.http.services.control.run_lifecycle")
        sink_type = control_lifecycle.HumanDecisionAuthoritySink
        if type(authority_sink) is not sink_type:
            raise TypeError("human-decision authority sink must be the exact runtime type")
        deployment_security = import_module("polisyos.runtime.http.deployment_security")
        custody_type = deployment_security.DeploymentHumanDecisionCustody
        if type(custody) is not custody_type:
            raise TypeError("human-decision custody must be the exact deployment type")
        if type(resolver_policy) is not HumanDecisionResolverPolicy:
            raise TypeError("resolver_policy must be a HumanDecisionResolverPolicy")
        self._sink = authority_sink
        self._custody = custody
        self._resolver_policy = resolver_policy
        self._access_audit_path = access_audit_path
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def available(self) -> bool:
        """Return whether the exact deployment custody chain is available."""

        return self._custody.available

    @property
    def unavailability_code(self) -> str | None:
        """Return the typed deployment refusal when custody is unavailable."""

        return self._custody.unavailability_code

    @property
    def custody(self) -> RuntimeHumanDecisionCustody:
        """Return the exact component for composition identity tests."""

        return self._custody

    @property
    def authority_sink(self) -> HumanDecisionAuthoritySinkProtocol:
        """Return the narrow existing-writer/event/reservation boundary."""

        return self._sink

    def resolve_gate(
        self,
        gate_input: HumanDecisionGateInput,
        *,
        bound_permission: (ActionPermissionVerification | BoundActionPermissionVerification | None),
    ) -> HumanDecisionGateResult:
        """Resolve every signed input and return a non-authoritative projection."""

        return self._resolve_gate(
            gate_input,
            bound_permission=bound_permission,
            require_bound_mutation=False,
        ).projection

    def resolve_gate_response(
        self,
        gate_input: HumanDecisionGateInput,
        *,
        bound_permission: (ActionPermissionVerification | BoundActionPermissionVerification | None),
    ) -> HumanDecisionGateResponse:
        """Project one response from the same signed inputs used by the gate."""
        resolved = self._resolve_gate(
            gate_input,
            bound_permission=bound_permission,
            require_bound_mutation=False,
        )
        projection = resolved.projection
        request_surface: HumanDecisionRequestSurface | None = None
        mandate_surface: HumanDecisionMandateSurface | None = None
        if resolved.request is not None:
            request = resolved.request
            request_surface = HumanDecisionRequestSurface(
                case_id=request.case_id,
                delegation_contract_ref=request.delegation_contract_ref,
                decision_rights_matrix_ref=request.decision_rights_matrix_ref,
                required_role=request.required_role,
                available_actions=tuple(request.available_actions),
                requested_at=request.requested_at,
                decision_due_at=request.decision_due_at,
                decidable_until=request.decidable_until,
                five_rights_requirements=request.five_rights_requirements,
                five_rights_binding=request.five_rights_binding,
            )
        if resolved.contract is not None and resolved.source is not None:
            envelope = next(
                (
                    row
                    for row in resolved.contract.action_envelopes
                    if row.envelope_id == resolved.source.envelope_id
                ),
                None,
            )
            if envelope is not None:
                mandate_surface = HumanDecisionMandateSurface(
                    mandate_record_ref=resolved.contract.s6_mandate_record_ref,
                    mandate_owner_ref=envelope.mandate_owner_ref,
                    operation_id=envelope.operation_id,
                    action_kind=envelope.action_kind,
                    valid_from=envelope.valid_from,
                    valid_until=envelope.valid_until,
                )
        elif resolved.production_basis is not None:
            basis = resolved.production_basis
            mandate_surface = HumanDecisionMandateSurface(
                mandate_record_ref=basis.mandate_record_ref,
                mandate_owner_ref=basis.mandate_owner_ref,
                operation_id=basis.operation_id,
                action_kind=basis.action_kind,
                valid_from=basis.valid_from,
                valid_until=basis.valid_until,
            )
        presentation = resolved.presentation
        session = resolved.exposure_session
        exposure = HumanDecisionExposureSurface(
            exposure_session_ref=resolved.exposure_session_artifact_ref,
            required_artifact_digests=projection.required_artifact_digests,
            completed_artifact_digests=tuple(
                event.artifact_id for event in resolved.exposure_events
            ),
            renderer_id=(presentation.renderer_id if presentation is not None else None),
            renderer_version=(presentation.renderer_version if presentation is not None else None),
            channel=(presentation.channel if presentation is not None else None),
            representation=(presentation.representation if presentation is not None else None),
        )
        if session is not None and exposure.exposure_session_ref is None:
            raise HumanDecisionPersistenceError(
                "resolved exposure session lost its exact caller reference"
            )
        continuation = self._response_continuation(resolved)
        submission = (
            HumanDecisionSubmissionSurface(
                selector=continuation,
                allowed_decisions=tuple(
                    HumanDecisionAllowedDecision(
                        action=action,
                        decision_modes=(
                            ("ordinary", "override")
                            if action == "approve"
                            else ("blocking",)
                            if action == "reject"
                            else ("ordinary",)
                        ),
                    )
                    for action in cast("HumanDecisionRequest", resolved.request).available_actions
                ),
            )
            if projection.status == "available" and continuation is not None
            else None
        )
        return HumanDecisionGateResponse(
            status=projection.status,
            reasons=projection.reasons,
            reason_codes=tuple(reason.code for reason in projection.reasons),
            source_kind=projection.source_kind,
            source_ref=(
                resolved.source_artifact_ref
                if projection.source_kind == "agent_action_authority"
                else resolved.production_basis_ref
            ),
            tenant_id=projection.tenant_id,
            run_id=projection.run_id,
            decision_request_ref=projection.decision_request_ref,
            decision_request_digest=projection.decision_request_digest,
            governed_action_key=projection.governed_action_key,
            decision_request=request_surface,
            mandate=mandate_surface,
            exposure=exposure,
            # No admitted live case/source producer exists. A signed request's
            # self-consistent case string is not an institutional case binding.
            contestability=None,
            continuation=continuation,
            submission=submission,
            resolved_at=projection.resolved_at,
            verifier_epoch=projection.verifier_epoch,
        )

    @staticmethod
    def _response_continuation(
        resolved: _ResolvedGate,
    ) -> HumanDecisionPA2ReplaySelector | HumanDecisionProductionReplaySelector | None:
        """Return verified replay selectors only for actionable or evidence-only gates."""

        projection = resolved.projection
        if projection.status not in {"available", "blocked"}:
            return None
        if projection.status == "blocked":
            evidence_only_codes = {
                "DS9-MANDATE-NOT-SHOWN",
                "DS9-EVIDENCE-NOT-OPENED",
                "DS9-RUBBER-STAMP",
            }
            if not {reason.code for reason in projection.reasons}.issubset(evidence_only_codes):
                return None
        common = (
            resolved.request,
            resolved.principal_artifact_ref,
            resolved.separation_artifact_ref,
            resolved.presentation_artifact_ref,
            resolved.exposure_session_artifact_ref,
        )
        if any(value is None for value in common):
            return None
        request = cast("HumanDecisionRequest", resolved.request)
        decision_request_digest = _sha256_ref(request.model_dump(mode="json"))
        principal_binding_ref = cast("str", resolved.principal_artifact_ref)
        reviewer_separation_ref = cast("str", resolved.separation_artifact_ref)
        presentation_contract_ref = cast("str", resolved.presentation_artifact_ref)
        exposure_session_ref = cast("str", resolved.exposure_session_artifact_ref)
        if projection.source_kind == "agent_action_authority":
            source = resolved.source
            if (
                source is None
                or resolved.source_artifact_ref is None
                or resolved.contract_artifact_ref is None
            ):
                return None
            return HumanDecisionPA2ReplaySelector(
                source_kind="agent_action_authority",
                source_ref=resolved.source_artifact_ref,
                basis_ref=resolved.contract_artifact_ref,
                basis_digest=resolved.contract_artifact_ref,
                action_kind=source.action_kind,
                decision_request_ref=request.request_ref,
                decision_request_digest=decision_request_digest,
                principal_binding_ref=principal_binding_ref,
                reviewer_separation_ref=reviewer_separation_ref,
                presentation_contract_ref=presentation_contract_ref,
                exposure_session_ref=exposure_session_ref,
            )
        if resolved.production_basis_ref is None:
            return None
        return HumanDecisionProductionReplaySelector(
            source_kind="production_approval",
            source_ref=resolved.production_basis_ref,
            basis_ref=resolved.production_basis_ref,
            basis_digest=resolved.production_basis_ref,
            decision_request_ref=request.request_ref,
            decision_request_digest=decision_request_digest,
            principal_binding_ref=principal_binding_ref,
            reviewer_separation_ref=reviewer_separation_ref,
            presentation_contract_ref=presentation_contract_ref,
            exposure_session_ref=exposure_session_ref,
        )

    def issue_exposure_session(
        self,
        gate_input: HumanDecisionPA2GateInput | HumanDecisionProductionGateInput,
        *,
        bound_permission: ActionPermissionVerification | BoundActionPermissionVerification,
    ) -> HumanDecisionExposureSessionReceipt:
        """Issue one custody-signed session after exact pre-exposure resolution."""

        if gate_input.exposure_session_ref is not None:
            raise HumanDecisionOperationalResolutionError("DS9-EXPOSURE-SESSION-ALREADY-ISSUED")
        resolved = self._resolve_gate(
            gate_input,
            bound_permission=bound_permission,
            require_bound_mutation=False,
        )
        expected_missing = {"DS9-EXPOSURE-SESSION-PRODUCER-MISSING"}
        reason_codes = {reason.code for reason in resolved.projection.reasons}
        if reason_codes != expected_missing:
            raise HumanDecisionUnavailableError(resolved.projection)
        values = (
            resolved.request,
            resolved.principal,
            resolved.separation,
            resolved.presentation,
            gate_input.principal_binding_ref,
            gate_input.presentation_contract_ref,
        )
        if any(value is None for value in values):
            raise HumanDecisionPersistenceError(
                "exposure-session producer lost a verified pre-action input"
            )
        request = cast("HumanDecisionRequest", resolved.request)
        principal = cast("HumanDecisionPrincipalBinding", resolved.principal)
        separation = cast("ReviewerSeparationCredential", resolved.separation)
        presentation = cast("HumanDecisionPresentationContract", resolved.presentation)
        principal_ref = cast("str", gate_input.principal_binding_ref)
        presentation_ref = cast("str", gate_input.presentation_contract_ref)
        verification = self._require_bound_route_permission(
            bound_permission,
            tenant_id=gate_input.tenant_id,
            run_id=gate_input.run_id,
            route_permission="runs.review",
            resource_kind="runtime.run.human_decision_gate",
            required_selectors={"source_kind": gate_input.source_kind},
            query_selector_parameters=("source_kind",),
            allow_empty_body=True,
        )
        if (
            verification.subject != principal.principal_subject
            or verification.tenant_id != gate_input.tenant_id
            or self._resolver_policy.required_permission
            not in tuple(item.value for item in verification.granted_permissions)
        ):
            raise HumanDecisionOperationalResolutionError("DS9-EXPOSURE-SUBJECT-MISMATCH")
        if isinstance(gate_input, HumanDecisionPA2GateInput):
            source = resolved.source
            contract = resolved.contract
            if source is None or contract is None:
                raise HumanDecisionPersistenceError(
                    "exposure-session producer lost the signed delegation basis"
                )
            envelope = next(
                (row for row in contract.action_envelopes if row.envelope_id == source.envelope_id),
                None,
            )
            if envelope is None or source.contract_ref is None:
                raise HumanDecisionPersistenceError(
                    "exposure-session producer lost the signed delegation basis"
                )
            basis_ref = source.contract_ref
            basis_valid_until = envelope.valid_until
            source_input_refs = (gate_input.source_ref, basis_ref)
        else:
            production_basis = resolved.production_basis
            basis_ref = resolved.production_basis_ref
            if production_basis is None or basis_ref is None:
                raise HumanDecisionPersistenceError(
                    "exposure-session producer lost the signed production basis"
                )
            basis_valid_until = production_basis.valid_until
            source_input_refs = (basis_ref,)
        now = self._now()
        ends = [
            principal.valid_until,
            separation.valid_until,
            presentation.valid_until,
            basis_valid_until,
            now + timedelta(minutes=15),
        ]
        if request.decision_due_at is not None:
            ends.append(request.decision_due_at)
        if request.decidable_until is not None:
            ends.append(request.decidable_until)
        valid_until = min(ends)
        if valid_until <= now:
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-REVALIDATION-REQUIRED")
        session_id = f"human-decision-exposure-{uuid.uuid4().hex}"
        session = HumanDecisionExposureSession(
            session_id=session_id,
            session_ref=f"runtime://human-decision/exposure/{session_id}",
            tenant_id=gate_input.tenant_id,
            run_id=gate_input.run_id,
            principal_binding_ref=principal_ref,
            principal_binding_digest=principal_ref,
            principal_subject=principal.principal_subject,
            actor_ref=principal.actor_ref,
            decision_request_ref=request.request_ref,
            decision_request_digest=_sha256_ref(request.model_dump(mode="json")),
            basis_digest=basis_ref,
            required_artifact_digests=presentation.required_artifact_digests,
            presentation_contract_ref=presentation_ref,
            presentation_contract_digest=presentation_ref,
            renderer_id=presentation.renderer_id,
            renderer_version=presentation.renderer_version,
            channel=presentation.channel,
            representation=presentation.representation,
            valid_from=now,
            valid_until=valid_until,
            verifier_epoch=self._verifier_epoch(),
            authority_boundary=_exposure_session_boundary(presentation.rule_version_ref),
            rule_version_ref=presentation.rule_version_ref,
            issued_at=now,
        )
        input_refs = tuple(
            dict.fromkeys(
                (
                    *source_input_refs,
                    principal_ref,
                    cast("str", gate_input.reviewer_separation_ref),
                    presentation_ref,
                    *presentation.required_artifact_digests,
                )
            )
        )
        return self._persist_exposure_session(session, input_refs=input_refs)

    def resolve_exposure_delivery(
        self,
        *,
        session_ref: str,
        artifact_ref: str,
        tenant_id: str,
        run_id: str,
        bound_permission: ActionPermissionVerification | BoundActionPermissionVerification,
    ) -> HumanDecisionExposureDelivery:
        """Resolve signed session, principal, presentation, and exact CAS bytes once."""

        resolved_session = self._read_signed_model(
            session_ref,
            expected_kind=HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionExposureSession",
            expected_schema_version=HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
            model_type=HumanDecisionExposureSession,
            expected_tenant_id=tenant_id,
            expected_run_id=run_id,
        )
        session = cast("HumanDecisionExposureSession", resolved_session.model)
        verification = self._require_bound_route_permission(
            bound_permission,
            tenant_id=tenant_id,
            run_id=run_id,
            route_permission="runs.review",
            resource_kind="runtime.run.human_decision_evidence",
            required_selectors={"artifact_id": artifact_ref},
            path_selector_parameters=("artifact_id",),
            allow_empty_body=True,
        )
        now = self._now()
        if (
            session.tenant_id != tenant_id
            or session.run_id != run_id
            or session.principal_subject != verification.subject
            or verification.tenant_id != tenant_id
        ):
            raise HumanDecisionOperationalResolutionError("DS9-EXPOSURE-SUBJECT-MISMATCH")
        if (
            session.verifier_epoch != self._verifier_epoch()
            or session.valid_from > now
            or now >= session.valid_until
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-REVALIDATION-REQUIRED")
        resolved_principal = self._read_signed_model(
            session.principal_binding_ref,
            expected_kind=HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionPrincipalBinding",
            expected_schema_version=HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
            model_type=HumanDecisionPrincipalBinding,
            expected_tenant_id=tenant_id,
            expected_run_id=run_id,
        )
        principal = cast("HumanDecisionPrincipalBinding", resolved_principal.model)
        resolved_presentation = self._read_signed_model(
            session.presentation_contract_ref,
            expected_kind=HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionPresentationContract",
            expected_schema_version=HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
            model_type=HumanDecisionPresentationContract,
            expected_tenant_id=tenant_id,
            expected_run_id=run_id,
        )
        presentation = cast("HumanDecisionPresentationContract", resolved_presentation.model)
        if (
            principal.principal_subject != session.principal_subject
            or principal.actor_ref != session.actor_ref
            or session.principal_binding_digest != session.principal_binding_ref
            or presentation.required_artifact_digests != session.required_artifact_digests
            or (
                presentation.renderer_id,
                presentation.renderer_version,
                presentation.channel,
                presentation.representation,
            )
            != (
                session.renderer_id,
                session.renderer_version,
                session.channel,
                session.representation,
            )
        ):
            raise HumanDecisionOperationalResolutionError("DS9-EXPOSURE-SESSION-INVALID")
        allowed_multiplicity = Counter(session.required_artifact_digests)[artifact_ref]
        if allowed_multiplicity <= 0 or not self._sink.has_artifact(artifact_ref):
            raise HumanDecisionOperationalResolutionError("DS9-EXPOSURE-ARTIFACT-NOT-ADMITTED")
        content = self._sink.get_artifact_bytes(artifact_ref)
        if f"sha256:{sha256(content).hexdigest()}" != artifact_ref:
            raise HumanDecisionOperationalResolutionError("DS9-EXPOSURE-CONTENT-DIGEST-MISMATCH")
        manifest = self._sink.get_artifact_manifest(artifact_ref)
        return HumanDecisionExposureDelivery(
            session=session,
            session_ref=session_ref,
            artifact_ref=artifact_ref,
            content=content,
            media_type=manifest.media_type,
            allowed_multiplicity=allowed_multiplicity,
            valid_until=session.valid_until,
        )

    def prepare_exposure_audit_event(
        self,
        delivery: HumanDecisionExposureDelivery,
    ) -> ReservedHumanDecisionExposureEvent:
        """Prepare and durably reserve one receipt before evidence bytes leave."""
        if type(delivery) is not HumanDecisionExposureDelivery:
            raise TypeError("delivery must be a HumanDecisionExposureDelivery")
        from polisyos.runtime.http.access_audit import (
            RuntimeDataAccessAuditTrail,
            prepare_human_decision_exposure_event_through_sink,
        )

        if (
            self._custody.signer is None
            or self._custody.verifier is None
            or self._custody.signer_identity is None
        ):
            raise HumanDecisionPersistenceError("exposure-event custody producer is unavailable")

        event_id = f"human-decision-exposure-{uuid.uuid4().hex}"
        session = delivery.session
        event = HumanDecisionExposureAuditEvent(
            timestamp=self._now().timestamp(),
            event_id=event_id,
            event_ref=f"runtime://human-decision/exposure-events/{event_id}",
            event_receipt_ref=None,
            tenant_id=session.tenant_id,
            actor_ref=session.actor_ref,
            run_id=session.run_id,
            request_ref=session.decision_request_ref,
            request_digest=session.decision_request_digest,
            basis_digest=session.basis_digest,
            session_ref=delivery.session_ref,
            artifact_id=delivery.artifact_ref,
            content_digest=delivery.artifact_ref,
            delivered_bytes=len(delivery.content),
            allowed_multiplicity=delivery.allowed_multiplicity,
            verifier_epoch=session.verifier_epoch,
        )
        prepared = prepare_human_decision_exposure_event_through_sink(
            event=event,
            authority_sink=cast("Any", self._sink),
        )
        from polisyos.runtime.http.access_audit import (
            HumanDecisionExposureReplayError,
            RuntimeAuthorizationAuditError,
            reserve_human_decision_exposure_event_through_sink,
        )

        try:
            return reserve_human_decision_exposure_event_through_sink(
                trail=RuntimeDataAccessAuditTrail(path=self._access_audit_path),
                prepared=prepared,
                authority_sink=cast("Any", self._sink),
                signer=self._custody.signer,
                signer_identity=self._custody.signer_identity,
                verifier=self._custody.verifier,
            )
        except HumanDecisionExposureReplayError as exc:
            raise HumanDecisionOperationalResolutionError(
                "DS9-EXPOSURE-REVALIDATION-REQUIRED"
            ) from exc
        except RuntimeAuthorizationAuditError as exc:
            raise HumanDecisionPersistenceError(
                "exposure-event custody preflight did not complete"
            ) from exc

    def complete_exposure_audit_event(
        self,
        reserved: ReservedHumanDecisionExposureEvent,
    ) -> HumanDecisionExposureAuditEvent:
        """Sign, verify, and append only after exact final-body delivery."""
        from polisyos.runtime.http.access_audit import (
            RuntimeDataAccessAuditTrail,
            complete_human_decision_exposure_event_through_sink,
        )

        signer = self._custody.signer
        verifier = self._custody.verifier
        signer_identity = self._custody.signer_identity
        if signer is None or verifier is None or signer_identity is None:
            raise HumanDecisionPersistenceError("exposure-event custody producer is unavailable")
        return complete_human_decision_exposure_event_through_sink(
            trail=RuntimeDataAccessAuditTrail(path=self._access_audit_path),
            reserved=reserved,
            authority_sink=cast("Any", self._sink),
            signer=signer,
            signer_identity=signer_identity,
            verifier=verifier,
        )

    def _persist_exposure_session(
        self,
        session: HumanDecisionExposureSession,
        *,
        input_refs: tuple[str, ...],
    ) -> HumanDecisionExposureSessionReceipt:
        """Write, sign, reconcile, and read back one issued session."""

        signer = self._custody.signer
        verifier = self._custody.verifier
        signer_identity = self._custody.signer_identity
        if signer is None or verifier is None or signer_identity is None:
            raise HumanDecisionPersistenceError("exposure-session custody producer is unavailable")
        payload = session.model_dump(mode="json")
        expected_ref = _sha256_ref(payload)
        job_id = f"exposure-session-{session.session_id}"
        closure_hash = _sha256_ref(
            {
                "tenant_id": session.tenant_id,
                "run_id": session.run_id,
                "session_id": session.session_id,
                "input_refs": input_refs,
            }
        )
        generated_at = session.issued_at.isoformat()
        result = self._sink.write_authority_artifact(
            payload,
            _exposure_session_write_options(),
            authority_fields={
                "evidence_id": session.session_id,
                "evidence_class": "authority_bearing",
                "authority_role": "producer_authority",
                "provenance_kind": "runtime_emitted",
                "owner": signer_identity,
                "reader_contract": "runtime_quality.human_decision_exposure_session.reader",
                "reader_contract_version": "1.0",
                "tenant_id": session.tenant_id,
                "cell_id": None,
                "run_id": session.run_id,
                "job_id": job_id,
                "trace_id": f"trace-{session.session_id}",
                "span_id": f"span-{session.session_id}",
                "parent_span_id": None,
                "requested_execution_profile": "governed",
                "effective_execution_profile": "governed",
                "phase": "human_decision_exposure_session",
                "generated_at": generated_at,
                "as_of_time": generated_at,
                "same_input_closure": {
                    "closure_id": f"human-decision-exposure.{closure_hash[7:31]}",
                    "status": "closed",
                    "run_id": session.run_id,
                    "job_id": job_id,
                    "tenant_id": session.tenant_id,
                    "cell_id": None,
                    "effective_mode_ref": "runtime://human-decision/exposure-session",
                    "degradation_ledger_ref": None,
                    "evidence_input_refs": input_refs,
                    "closure_sha256": closure_hash,
                },
                "input_refs": input_refs,
                "effective_mode_ref": "runtime://human-decision/exposure-session",
                "degradation_ledger_ref": None,
                "semantic_binding_ref": session.principal_binding_ref,
                "validation_status": "pass",
                "blocking_status": "non_blocking",
                "governance": GovernanceMetadata(
                    classification="restricted",
                    authority_boundary="runtime.human_decision_exposure_session_custody",
                    pii="identity_bound",
                    retention_policy="runtime-quality-90d",
                    review_status="runtime_verified",
                    override_policy="none",
                    approval_policy="signed_principal_and_presentation_required",
                ),
                "event_id": f"evt_exposure_session_{closure_hash[7:31]}",
                "event_source": "polisyos.runtime.http.human_decisions",
                "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
                "event_subject": f"run/{session.run_id}/exposure-session/{session.session_id}",
                "state_after": "persisted",
                "canon_spec": canon.CanonSpec(),
            },
        )
        session_ref = str(result.cas_ref.artifact_id)
        if result.payload_sha256 != expected_ref[7:] or session_ref != expected_ref:
            raise HumanDecisionPersistenceError("exposure-session CAS digest changed")
        if self._sink.get_artifact_signature(session_ref) is None:
            self._sink.sign_artifact(
                session_ref,
                signer,
                signer_identity=signer_identity,
            )
        verification = self._sink.verify_artifact_signature(
            session_ref,
            verifier,
            strict_identity=True,
        )
        if (
            not verification.ok
            or verification.signer_identity != signer_identity
            or verification.key_id != signer.key_id
        ):
            raise HumanDecisionPersistenceError("exposure-session custody signature did not verify")
        loaded = HumanDecisionExposureSession.model_validate(
            canon.from_canonical_bytes(self._sink.get_artifact_bytes(session_ref))
        )
        if loaded != session:
            raise HumanDecisionPersistenceError("exposure-session canonical readback changed")
        report = self._sink.reconcile_authority_artifact(
            session_ref,
            expected_tenant_id=session.tenant_id,
            expected_cell_id=None,
            expected_run_id=session.run_id,
            expected_job_id=job_id,
        )
        if report.durable_event_id is None:
            raise HumanDecisionPersistenceError("exposure-session durable event is missing")
        return HumanDecisionExposureSessionReceipt(
            session=session,
            session_ref=session_ref,
            session_digest=session_ref,
            durable_event_id=report.durable_event_id,
            custody_signer_identity=signer_identity,
            custody_key_id=signer.key_id,
        )

    def create_record(
        self,
        command: HumanDecisionCreateCommand,
        *,
        bound_permission: BoundActionPermissionVerification,
        write_context: HumanDecisionWriteContext,
    ) -> HumanDecisionRecordReceipt:
        """Persist, sign, reconcile, and commit one exact V2 decision record."""

        resolved = self._resolve_gate(
            command.gate_input,
            bound_permission=bound_permission,
            require_bound_mutation=True,
        )
        if resolved.projection.status != "available":
            raise HumanDecisionUnavailableError(resolved.projection)
        if not self._custody.available:
            raise HumanDecisionUnavailableError(resolved.projection)
        source = resolved.source
        request = resolved.request
        contract = resolved.contract
        production_basis = resolved.production_basis
        production_basis_ref = resolved.production_basis_ref
        principal = resolved.principal
        separation = resolved.separation
        presentation = resolved.presentation
        session = resolved.exposure_session
        if any(value is None for value in (request, principal, separation, presentation, session)):
            raise HumanDecisionPersistenceError("available gate lost resolved inputs")
        request = cast("HumanDecisionRequest", request)
        principal = cast("HumanDecisionPrincipalBinding", principal)
        separation = cast("ReviewerSeparationCredential", separation)
        presentation = cast("HumanDecisionPresentationContract", presentation)
        session = cast("HumanDecisionExposureSession", session)
        if isinstance(command.gate_input, HumanDecisionPA2GateInput):
            if source is None or contract is None:
                raise HumanDecisionPersistenceError("available PA2 gate lost resolved inputs")
        elif production_basis is None or production_basis_ref is None:
            raise HumanDecisionPersistenceError("available production gate lost resolved inputs")
        if (
            write_context.tenant_id != command.gate_input.tenant_id
            or write_context.run_id != command.gate_input.run_id
        ):
            raise HumanDecisionPersistenceError("writer context does not bind gate tenant/run")
        if command.decision_action not in request.available_actions:
            raise HumanDecisionUnavailableError(
                self._blocked_projection(
                    command.gate_input,
                    "DS9-DECISION-ACTION-NOT-OFFERED",
                    "The requested action was absent from the signed decision request.",
                )
            )
        if command.decision_action not in separation.change_authority_actions:
            raise HumanDecisionUnavailableError(
                self._blocked_projection(
                    command.gate_input,
                    "DS9-REVIEWER-CHANGE-AUTHORITY-MISSING",
                    "The signed separation credential lacks this change authority.",
                )
            )

        now = self._now()
        if resolved.valid_until is None or now >= resolved.valid_until:
            raise HumanDecisionUnavailableError(
                self._blocked_projection(
                    command.gate_input,
                    "DS9-DECISION-TTL-EXPIRED",
                    "The resolved authoritative interval expired before reservation.",
                )
            )
        attempt_id = f"human-decision-attempt-{uuid.uuid4().hex}"
        if isinstance(command.gate_input, HumanDecisionPA2GateInput):
            source = cast("AgentActionAuthorityDecision", source)
            contract = cast("DelegationContract", contract)
            envelope = next(
                (row for row in contract.action_envelopes if row.envelope_id == source.envelope_id),
                None,
            )
            if envelope is None:
                raise HumanDecisionPersistenceError(
                    "available PA2 gate lost its signed action envelope"
                )
            governed_action_key = _pa2_governed_action_key(
                source=source,
                contract=contract,
                envelope=envelope,
                tenant_id=command.gate_input.tenant_id,
                run_id=command.gate_input.run_id,
            )
        else:
            governed_action_key = cast(
                "ProductionHumanDecisionBasis",
                production_basis,
            ).governed_action_key
        if governed_action_key != resolved.projection.governed_action_key:
            raise HumanDecisionPersistenceError(
                "human-decision governed action key changed after gate resolution"
            )
        binding_sha256 = _sha256_ref(
            {
                "tenant_id": command.gate_input.tenant_id,
                "run_id": command.gate_input.run_id,
                "source_ref": (
                    command.gate_input.source_ref
                    if isinstance(command.gate_input, HumanDecisionPA2GateInput)
                    else production_basis_ref
                ),
                "decision_request_digest": resolved.projection.decision_request_digest,
                "basis_digest": command.gate_input.basis_digest,
                "decision_action": command.decision_action,
                "decision_mode": command.decision_mode,
                "decision_attempt_id": attempt_id,
            }
        )
        reservation_id = f"human-decision-reservation-{uuid.uuid4().hex}"
        reserved = self._sink.reserve_action(
            tenant_id=command.gate_input.tenant_id,
            governed_action_key=governed_action_key,
            reservation_id=reservation_id,
            binding_sha256=binding_sha256,
            now=now,
            lease_seconds=_RESERVATION_LEASE_SECONDS,
            record_valid_until=resolved.valid_until,
        )
        if not reserved.acquired:
            raise HumanDecisionOperationalResolutionError(
                reserved.issue_code or "DS9-OVERLAPPING-REISSUE"
            )

        record_ref: str | None = None
        durable_event_id: str | None = None
        signature_verified = False
        try:
            record = self._build_record(
                command=command,
                resolved=resolved,
                source=source,
                request=request,
                contract=contract,
                production_basis=production_basis,
                production_basis_ref=production_basis_ref,
                principal=principal,
                presentation=presentation,
                session=session,
                attempt_id=attempt_id,
                governed_action_key=governed_action_key,
                binding_sha256=binding_sha256,
                reservation_id=reservation_id,
                reservation_version=reserved.reservation.reservation_version,
                recorded_at=now,
            )
        except Exception as exc:
            self._freeze_failed_reservation(
                command=command,
                governed_action_key=governed_action_key,
                reservation_id=reservation_id,
                reservation_version=reserved.reservation.reservation_version,
                record_ref=record_ref,
                durable_event_id=durable_event_id,
                signature_verified=signature_verified,
                write_context=write_context,
            )
            if isinstance(exc, HumanDecisionPersistenceError):
                raise
            raise HumanDecisionPersistenceError(
                "human-decision record custody did not complete"
            ) from exc

        write_failure: Exception | None = None
        recovery_finalized = False
        receipt: HumanDecisionRecordReceipt | None = None
        expected_record_valid_until = record.valid_until
        if expected_record_valid_until is None:
            self._freeze_failed_reservation(
                command=command,
                governed_action_key=governed_action_key,
                reservation_id=reservation_id,
                reservation_version=reserved.reservation.reservation_version,
                record_ref=record_ref,
                durable_event_id=durable_event_id,
                signature_verified=signature_verified,
                write_context=write_context,
            )
            raise HumanDecisionPersistenceError("human-decision v2 record has no validity boundary")
        try:
            with self._sink.hold_write_fence(
                tenant_id=cast("str", record.tenant_id),
                governed_action_key=governed_action_key,
                reservation_id=reservation_id,
                reservation_version=cast("int", record.reservation_version),
                binding_sha256=binding_sha256,
                acquired_at=self._now(),
                expected_record_valid_until=expected_record_valid_until,
            ) as fence:
                try:
                    payload = record.model_dump(mode="json")
                    expected_ref = _sha256_ref(payload)
                    result = self._sink.write_authority_artifact(
                        payload,
                        _record_write_options(),
                        authority_fields=self._record_authority_fields(
                            record=record,
                            context=write_context,
                            input_refs=self._record_input_refs(record),
                        ),
                    )
                    record_ref = str(result.cas_ref.artifact_id)
                    if result.payload_sha256 != expected_ref[7:] or record_ref != expected_ref:
                        raise ValueError("human-decision record CAS digest changed")
                    existing_signature = self._sink.get_artifact_signature(record_ref)
                    signer = self._custody.signer
                    verifier = self._custody.verifier
                    signer_identity = self._custody.signer_identity
                    if signer is None or verifier is None or signer_identity is None:
                        raise ValueError("human-decision custody producer is unavailable")
                    if existing_signature is None:
                        self._sink.sign_artifact(
                            record_ref,
                            signer,
                            signer_identity=signer_identity,
                        )
                    verification = self._sink.verify_artifact_signature(
                        record_ref,
                        verifier,
                        strict_identity=True,
                    )
                    if (
                        not verification.ok
                        or verification.signer_identity != record.custody_signer_identity
                        or verification.key_id != record.custody_key_id
                    ):
                        raise ValueError("human-decision custody signature did not bind the record")
                    signature_verified = True
                    self._assert_record_manifest(record_ref)
                    loaded = HumanDecisionRecord.model_validate(
                        canon.from_canonical_bytes(self._sink.get_artifact_bytes(record_ref))
                    )
                    if loaded != record:
                        raise ValueError("human-decision record canonical readback changed")
                    report = self._sink.reconcile_authority_artifact(
                        record_ref,
                        expected_tenant_id=write_context.tenant_id,
                        expected_cell_id=write_context.cell_id,
                        expected_run_id=write_context.run_id,
                        expected_job_id=write_context.job_id,
                    )
                    durable_event_id = report.durable_event_id
                    if durable_event_id is None:
                        raise ValueError("human-decision durable event is missing")
                    self._verify_record_signature(record_ref, record)
                    committed = fence.commit(
                        record_ref=record_ref,
                        record_sha256=record_ref,
                        durable_event_id=durable_event_id,
                        committed_at=self._now(),
                    )
                    receipt = HumanDecisionRecordReceipt(
                        record=record,
                        record_ref=record_ref,
                        record_digest=record_ref,
                        durable_event_id=durable_event_id,
                        reservation_id=reservation_id,
                        reservation_version=committed.reservation_version,
                        custody_signer_identity=signer_identity,
                        custody_key_id=signer.key_id,
                    )
                except Exception as exc:
                    write_failure = exc
                    has_reconciled_orphan = (
                        signature_verified
                        and record_ref is not None
                        and durable_event_id is not None
                    )
                    fence.recover(
                        record_ref=record_ref if has_reconciled_orphan else None,
                        record_sha256=record_ref if has_reconciled_orphan else None,
                        durable_event_id=(durable_event_id if has_reconciled_orphan else None),
                    )
                    recovery_finalized = True
        except Exception as exc:
            if not recovery_finalized:
                self._freeze_failed_reservation(
                    command=command,
                    governed_action_key=governed_action_key,
                    reservation_id=reservation_id,
                    reservation_version=reserved.reservation.reservation_version,
                    record_ref=record_ref,
                    durable_event_id=durable_event_id,
                    signature_verified=signature_verified,
                    write_context=write_context,
                )
            raise HumanDecisionPersistenceError(
                "human-decision record custody did not complete"
            ) from (write_failure or exc)
        if write_failure is not None:
            if (
                recovery_finalized
                and signature_verified
                and record_ref is not None
                and durable_event_id is not None
                and self._custody.verifier is not None
                and self._custody.signer_identity is not None
                and self._custody.signer is not None
            ):
                try:
                    self._sink.reconcile_orphan_reservation(
                        tenant_id=command.gate_input.tenant_id,
                        governed_action_key=governed_action_key,
                        reservation_id=reservation_id,
                        reservation_version=reserved.reservation.reservation_version,
                        verifier=self._custody.verifier,
                        expected_signer_identity=self._custody.signer_identity,
                        expected_key_id=self._custody.signer.key_id,
                        expected_cell_id=write_context.cell_id,
                        expected_run_id=write_context.run_id,
                        expected_job_id=write_context.job_id,
                        reconciled_at=self._now(),
                    )
                except Exception as exc:
                    logger.warning(
                        "human_decision_orphan_reconciliation_deferred",
                        reservation_id=reservation_id,
                        error=str(exc),
                    )
            raise HumanDecisionPersistenceError(
                "human-decision record custody did not complete"
            ) from write_failure
        if receipt is None:  # pragma: no cover - finalized fence invariant
            raise HumanDecisionPersistenceError("human-decision record custody did not complete")
        return receipt

    def read_record(
        self,
        record_ref: str,
        *,
        tenant_id: str,
        run_id: str,
    ) -> HumanDecisionRecord:
        """Read historical or current content only after exact custody verification."""

        try:
            resolved = self._read_signed_model(
                record_ref,
                expected_kind=HUMAN_DECISION_RECORD_ARTIFACT_KIND,
                expected_schema_name=_RECORD_SCHEMA_NAME,
                expected_schema_version=HUMAN_DECISION_RECORD_MANIFEST_VERSION,
                model_type=HumanDecisionRecord,
                expected_tenant_id=tenant_id,
                expected_run_id=run_id,
            )
        except _ResolutionIssueError as exc:
            raise HumanDecisionOperationalResolutionError(exc.reason.code) from exc
        record = cast("HumanDecisionRecord", resolved.model)
        if (
            record.schema_version != HUMAN_DECISION_RECORD_V2
            or record.tenant_id != tenant_id
            or record.run_id != run_id
            or record.custody_signer_identity != resolved.signer_identity
            or record.custody_key_id != resolved.key_id
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
        return record

    def resolve_production_approval_inputs(
        self,
        *,
        tenant_id: str,
        run_id: str,
        scorecard_ref: str,
        scorecard_binding_digest: str,
        production_basis_ref: str,
        human_decision_record_ref: str,
        evaluated_at: datetime | None = None,
    ) -> ResolvedProductionApprovalInputs:
        """Re-resolve the three signed production inputs and their live joins.

        This is deliberately not a public currentness verdict.  The final
        deployment-issued resolver wraps this result in a module-private seal
        before any route or operational consumer can use it.
        """

        now = self._now() if evaluated_at is None else evaluated_at
        if now.tzinfo is None or now.utcoffset() is None:
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
        try:
            scorecard_artifact = self._read_signed_model(
                scorecard_ref,
                expected_kind=_QUALITY_SCORECARD_KIND,
                expected_schema_name=_QUALITY_SCORECARD_SCHEMA_NAME,
                expected_schema_version=_QUALITY_SCORECARD_SCHEMA_VERSION,
                model_type=_SignedQualityScorecard,
                expected_tenant_id=tenant_id,
                expected_run_id=run_id,
            )
            basis_artifact = self._read_signed_model(
                production_basis_ref,
                expected_kind=PRODUCTION_HUMAN_DECISION_BASIS_ARTIFACT_KIND,
                expected_schema_name=_PRODUCTION_BASIS_SCHEMA_NAME,
                expected_schema_version=PRODUCTION_HUMAN_DECISION_BASIS_MANIFEST_VERSION,
                model_type=ProductionHumanDecisionBasis,
                expected_tenant_id=tenant_id,
                expected_run_id=run_id,
            )
            record = self.read_record(
                human_decision_record_ref,
                tenant_id=tenant_id,
                run_id=run_id,
            )
        except _ResolutionIssueError as exc:
            raise HumanDecisionOperationalResolutionError(exc.reason.code) from exc

        scorecard = cast("_SignedQualityScorecard", scorecard_artifact.model)
        basis = cast("ProductionHumanDecisionBasis", basis_artifact.model)
        from polisyos.runtime.http.production_approval_binding import (
            production_approval_scorecard_binding_digest,
        )

        recomputed_scorecard_binding = production_approval_scorecard_binding_digest(
            scorecard.model_dump(mode="json", by_alias=True),
            ref=scorecard_ref,
            run_id=run_id,
        )
        valid_from_candidates = (basis.valid_from, cast("datetime", record.valid_from))
        valid_until_candidates = (basis.valid_until, cast("datetime", record.valid_until))
        valid_from = max(valid_from_candidates)
        valid_until = min(valid_until_candidates)
        reservation = self._sink.get_reservation_generation(
            tenant_id=tenant_id,
            governed_action_key=record.governed_action_key or "",
            reservation_version=record.reservation_version or 0,
        )
        if (
            recomputed_scorecard_binding != scorecard_binding_digest
            or basis.tenant_id != tenant_id
            or basis.run_id != run_id
            or basis.scorecard_ref != scorecard_ref
            or basis.scorecard_digest != scorecard_ref
            or record.source_kind != "production_approval"
            or record.source_ref != production_basis_ref
            or record.source_digest != production_basis_ref
            or record.basis_ref != production_basis_ref
            or record.basis_digest != production_basis_ref
            or record.human_decision_request_ref != basis.decision_request_ref
            or record.decision_request_digest != basis.decision_request_digest
            or record.governed_action_key != basis.governed_action_key
            or record.verifier_epoch != basis.verifier_epoch
            or record.decision_action_exercised != "approve"
            or scorecard.quality_status.casefold() not in {"pass", "passed", "ok", "success"}
            or scorecard.approval_posture.casefold()
            not in {_RAW_APPROVAL_READY, "approved", "ready"}
            or reservation is None
            or reservation.state != "committed"
            or reservation.record_ref != human_decision_record_ref
            or reservation.record_sha256 != human_decision_record_ref
            or reservation.reservation_id != record.reservation_id
            or reservation.binding_sha256 != record.binding_sha256
            or now < valid_from
            or now >= valid_until
        ):
            raise HumanDecisionOperationalResolutionError("DS9-RAW-APPROVAL-NOT-AUTHORITY")
        return ResolvedProductionApprovalInputs(
            scorecard=scorecard.model_dump(mode="json", by_alias=True),
            scorecard_ref=scorecard_ref,
            scorecard_digest=scorecard_binding_digest,
            scorecard_signer_identity=scorecard_artifact.signer_identity,
            basis=basis,
            basis_ref=production_basis_ref,
            basis_signer_identity=basis_artifact.signer_identity,
            record=record,
            record_ref=human_decision_record_ref,
            valid_from=valid_from,
            valid_until=valid_until,
            verifier_epoch=basis.verifier_epoch,
        )

    def resolve_production_decision_packet(
        self,
        *,
        packet_ref: str,
        tenant_id: str,
        run_id: str,
        expected_consumer: str,
        expected_audience: str,
        evaluated_at: datetime | None = None,
    ) -> ResolvedProductionApprovalPacket:
        """Verify one custody packet and re-resolve all authority-bearing inputs."""

        now = self._now() if evaluated_at is None else evaluated_at
        try:
            signed = self._read_signed_model(
                packet_ref,
                expected_kind=_PRODUCTION_APPROVAL_PACKET_KIND,
                expected_schema_name=_PRODUCTION_APPROVAL_PACKET_SCHEMA_NAME,
                expected_schema_version=_PRODUCTION_APPROVAL_PACKET_SCHEMA_VERSION,
                model_type=ProductionApprovalPacket,
                expected_tenant_id=tenant_id,
                expected_run_id=run_id,
            )
        except _ResolutionIssueError as exc:
            raise HumanDecisionOperationalResolutionError(exc.reason.code) from exc
        packet = cast("ProductionApprovalPacket", signed.model)
        if (
            packet.schema_version != _PRODUCTION_APPROVAL_PACKET_SCHEMA_ID
            or packet.tenant_id != tenant_id
            or packet.run_id != run_id
            or packet.expected_consumer != expected_consumer
            or packet.expected_audience != expected_audience
            or packet.valid_from is None
            or packet.valid_until is None
            or now < packet.valid_from
            or now >= packet.valid_until
            or packet.decision not in {"approved", "approved_with_override"}
            or packet.scorecard_ref is None
            or packet.production_basis_ref is None
            or packet.human_decision_record_ref is None
            or packet.scorecard_digest is None
        ):
            raise HumanDecisionOperationalResolutionError("DS9-RAW-APPROVAL-NOT-AUTHORITY")
        inputs = self.resolve_production_approval_inputs(
            tenant_id=tenant_id,
            run_id=run_id,
            scorecard_ref=packet.scorecard_ref,
            scorecard_binding_digest=packet.scorecard_digest,
            production_basis_ref=packet.production_basis_ref,
            human_decision_record_ref=packet.human_decision_record_ref,
            evaluated_at=now,
        )
        if (
            packet.production_basis_digest != inputs.basis_ref
            or packet.human_decision_record_digest != inputs.record_ref
            or packet.decision_request_ref != inputs.basis.decision_request_ref
            or packet.decision_request_digest != inputs.basis.decision_request_digest
            or packet.governed_action_key != inputs.basis.governed_action_key
            or packet.valid_from != inputs.valid_from
            or packet.valid_until != inputs.valid_until
            or packet.verifier_epoch != inputs.verifier_epoch
            or packet.scorecard_producer_identity != inputs.scorecard_signer_identity
            or packet.production_basis_producer_identity != inputs.basis_signer_identity
            or packet.rule_version_ref != inputs.basis.rule_version_ref
        ):
            raise HumanDecisionOperationalResolutionError("DS9-RAW-APPROVAL-NOT-AUTHORITY")
        return ResolvedProductionApprovalPacket(
            packet=packet,
            packet_ref=packet_ref,
            inputs=inputs,
        )

    def _persist_production_decision_packet(
        self,
        packet: ProductionApprovalPacket,
        *,
        write_context: HumanDecisionWriteContext,
    ) -> ProductionApprovalPacketReceipt:
        """Persist, custody-sign, reconcile, and read back one exact V2 packet."""

        if (
            type(packet) is not ProductionApprovalPacket
            or packet.schema_version != _PRODUCTION_APPROVAL_PACKET_SCHEMA_ID
            or packet.tenant_id != write_context.tenant_id
            or packet.run_id != write_context.run_id
        ):
            raise HumanDecisionPersistenceError("production approval packet binding changed")
        signer = self._custody.signer
        verifier = self._custody.verifier
        signer_identity = self._custody.signer_identity
        if signer is None or verifier is None or signer_identity is None:
            raise HumanDecisionPersistenceError("production approval custody is unavailable")
        payload = packet.model_dump(mode="json")
        packet_ref = _sha256_ref(payload)
        input_refs = tuple(
            ref
            for ref in (
                packet.scorecard_ref,
                packet.production_basis_ref,
                packet.human_decision_record_ref,
                packet.decision_request_ref,
            )
            if ref is not None
        )
        result = self._sink.write_authority_artifact(
            payload,
            artifacts.ArtifactWriteOptions(
                kind=_PRODUCTION_APPROVAL_PACKET_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=_PRODUCTION_APPROVAL_PACKET_SCHEMA_NAME,
                    version=_PRODUCTION_APPROVAL_PACKET_SCHEMA_VERSION,
                ),
                producer=artifacts.ProducerInfo(
                    component="polisyos.runtime.http.production_approval",
                    version="2.0",
                ),
            ),
            authority_fields=self._production_packet_authority_fields(
                packet=packet,
                context=write_context,
                input_refs=input_refs,
            ),
        )
        written_ref = str(result.cas_ref.artifact_id)
        if written_ref != packet_ref or result.payload_sha256 != packet_ref[7:]:
            raise HumanDecisionPersistenceError("production approval packet CAS digest changed")
        if self._sink.get_artifact_signature(written_ref) is None:
            self._sink.sign_artifact(
                written_ref,
                signer,
                signer_identity=signer_identity,
            )
        verification = self._sink.verify_artifact_signature(
            written_ref,
            verifier,
            strict_identity=True,
        )
        if (
            not verification.ok
            or verification.signer_identity != signer_identity
            or verification.key_id != signer.key_id
        ):
            raise HumanDecisionPersistenceError(
                "production approval custody signature did not verify"
            )
        loaded = ProductionApprovalPacket.model_validate(
            canon.from_canonical_bytes(self._sink.get_artifact_bytes(written_ref))
        )
        if loaded != packet:
            raise HumanDecisionPersistenceError("production approval packet readback changed")
        report = self._sink.reconcile_authority_artifact(
            written_ref,
            expected_tenant_id=write_context.tenant_id,
            expected_cell_id=write_context.cell_id,
            expected_run_id=write_context.run_id,
            expected_job_id=write_context.job_id,
        )
        if report.durable_event_id is None:
            raise HumanDecisionPersistenceError("production approval durable event is missing")
        return ProductionApprovalPacketReceipt(
            packet=packet,
            packet_ref=written_ref,
            durable_event_id=report.durable_event_id,
            custody_signer_identity=signer_identity,
            custody_key_id=signer.key_id,
        )

    def resolve_gateway_adapter(
        self,
        adapter: HumanDecisionGatewayAdapterInput,
        *,
        evaluated_at: datetime | None = None,
        operation: object | None = None,
        invocation: object | None = None,
        intent: object | None = None,
        bound_permission: object | None = None,
        resolved_contract: object | None = None,
        admission: object | None = None,
        admission_ref: str | None = None,
        selected_envelope: object | None = None,
        effect_binding: object | None = None,
    ) -> _ResolvedPA2OperationalAuthority:
        """Re-resolve signed authority against raw, live evaluator-owned inputs."""

        now = self._now()
        if type(adapter) is not HumanDecisionPA2GatewayAdapterInput:
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-PRODUCER-MISSING")
        live_inputs = (
            evaluated_at,
            operation,
            invocation,
            intent,
            bound_permission,
            resolved_contract,
            admission,
            admission_ref,
            selected_envelope,
            effect_binding,
        )
        if any(value is None for value in live_inputs):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-PRODUCER-MISSING")
        if (
            not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None
            or evaluated_at > now
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
        record = self.read_record(
            adapter.record_ref,
            tenant_id=adapter.tenant_id,
            run_id=adapter.run_id,
        )
        if (
            adapter.record_ref != adapter.record_digest
            or record.source_kind != adapter.source_kind
            or record.source_ref != adapter.source_ref
            or record.source_digest != adapter.source_digest
            or record.human_decision_request_ref != adapter.decision_request_ref
            or record.decision_request_digest != adapter.decision_request_digest
            or record.basis_digest != adapter.basis_digest
            or record.rule_version_ref != adapter.rule_version_ref
            or record.verifier_epoch != adapter.verifier_epoch
            or record.valid_from != adapter.valid_from
            or record.valid_until != adapter.valid_until
            or adapter.expected_consumer != self._resolver_policy.expected_consumer
            or adapter.expected_audience != self._resolver_policy.expected_audience
            or (
                self._resolver_policy.expected_agent_operation is not None
                and adapter.expected_operation != self._resolver_policy.expected_agent_operation
            )
            or now < adapter.valid_from
            or now >= adapter.valid_until
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
        reservation = self._sink.get_reservation_generation(
            tenant_id=adapter.tenant_id,
            governed_action_key=record.governed_action_key or "",
            reservation_version=record.reservation_version or 0,
        )
        if (
            reservation is None
            or reservation.state != "committed"
            or reservation.reservation_id != record.reservation_id
            or reservation.record_ref != adapter.record_ref
            or reservation.record_sha256 != adapter.record_digest
            or reservation.binding_sha256 != record.binding_sha256
            or reservation.record_valid_until <= now
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-V1-REVALIDATION")
        resolution = self._revalidate_record_inputs(record, adapter, now=now)
        self._assert_live_pa2_inputs(
            resolution,
            evaluated_at=evaluated_at,
            operation=operation,
            invocation=invocation,
            intent=intent,
            bound_permission=bound_permission,
            resolved_contract=resolved_contract,
            admission=admission,
            admission_ref=cast("str", admission_ref),
            selected_envelope=selected_envelope,
            effect_binding=effect_binding,
        )
        return resolution

    def _resolve_gate(
        self,
        gate_input: HumanDecisionGateInput,
        *,
        bound_permission: (ActionPermissionVerification | BoundActionPermissionVerification | None),
        require_bound_mutation: bool,
    ) -> _ResolvedGate:
        if isinstance(gate_input, HumanDecisionProductionGateInput):
            return self._resolve_production_gate(
                gate_input,
                bound_permission=bound_permission,
                require_bound_mutation=require_bound_mutation,
            )
        return self._resolve_pa2_gate(
            gate_input,
            bound_permission=bound_permission,
            require_bound_mutation=require_bound_mutation,
        )

    def _resolve_production_gate(
        self,
        gate_input: HumanDecisionProductionGateInput,
        *,
        bound_permission: (ActionPermissionVerification | BoundActionPermissionVerification | None),
        require_bound_mutation: bool,
    ) -> _ResolvedGate:
        reasons: list[HumanDecisionGateReason] = []
        now = self._now()
        basis: ProductionHumanDecisionBasis | None = None
        basis_artifact: _ResolvedSignedArtifact | None = None
        principal: HumanDecisionPrincipalBinding | None = None
        separation: ReviewerSeparationCredential | None = None
        presentation: HumanDecisionPresentationContract | None = None
        session: HumanDecisionExposureSession | None = None
        events: tuple[HumanDecisionExposureAuditEvent, ...] = ()

        supplied_refs = (
            gate_input.source_ref,
            gate_input.basis_ref,
            gate_input.basis_digest,
        )
        if all(ref is None for ref in supplied_refs):
            reasons.append(
                _reason(
                    "DS9-DECISION-PRODUCER-MISSING",
                    "No verified production human-decision basis producer is installed.",
                    "producer_missing",
                )
            )
        elif any(ref is None for ref in supplied_refs) or len(set(supplied_refs)) != 1:
            reasons.append(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "Production source, basis ref, and basis digest are not exact-bound.",
                    "invalid_source",
                )
            )
        else:
            supplied_ref = cast("str", gate_input.basis_ref)
            try:
                basis_artifact = self._read_signed_model(
                    supplied_ref,
                    expected_kind=PRODUCTION_HUMAN_DECISION_BASIS_ARTIFACT_KIND,
                    expected_schema_name=_PRODUCTION_BASIS_SCHEMA_NAME,
                    expected_schema_version=PRODUCTION_HUMAN_DECISION_BASIS_MANIFEST_VERSION,
                    model_type=ProductionHumanDecisionBasis,
                    expected_tenant_id=gate_input.tenant_id,
                    expected_run_id=gate_input.run_id,
                )
                basis = cast("ProductionHumanDecisionBasis", basis_artifact.model)
            except _ResolutionIssueError as exc:
                reasons.append(exc.reason)
            except Exception:
                reasons.append(
                    _reason(
                        "DS9-DECISION-SOURCE-INVALID",
                        "The signed production basis could not be verified and reconciled.",
                        "invalid_source",
                    )
                )

        if gate_input.production_packet_ref is not None:
            reasons.append(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "A post-action production packet cannot authorize its pre-action record.",
                    "invalid_source",
                )
            )

        request = basis.decision_request if basis is not None else None
        if basis is not None and request is not None:
            request_digest = _sha256_ref(request.model_dump(mode="json"))
            if (
                basis.tenant_id != gate_input.tenant_id
                or basis.run_id != gate_input.run_id
                or gate_input.decision_request_ref not in {None, request.request_ref}
                or gate_input.decision_request_digest not in {None, request_digest}
                or basis.decision_request_ref != request.request_ref
                or basis.decision_request_digest != request_digest
            ):
                reasons.append(
                    _reason(
                        "DS9-DECISION-SOURCE-INVALID",
                        "The production basis differs from its signed request selectors.",
                        "invalid_source",
                    )
                )
            if (
                basis.verifier_epoch != self._verifier_epoch()
                or basis.valid_from > now
                or now >= basis.valid_until
            ):
                reasons.append(
                    _reason(
                        "DS9-DECISION-REVALIDATION-REQUIRED",
                        "The signed production basis requires online revalidation.",
                        "revalidation_required",
                    )
                )

        resolved_principal = self._optional_signed_model(
            gate_input.principal_binding_ref,
            expected_kind=HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionPrincipalBinding",
            expected_schema_version=HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
            model_type=HumanDecisionPrincipalBinding,
            expected_tenant_id=gate_input.tenant_id,
            expected_run_id=gate_input.run_id,
            missing_code="DS9-PRINCIPAL-BINDING-PRODUCER-MISSING",
            reasons=reasons,
        )
        principal = (
            cast("HumanDecisionPrincipalBinding", resolved_principal.model)
            if resolved_principal is not None
            else None
        )
        if (
            principal is not None
            and resolved_principal is not None
            and principal.principal_issuer != resolved_principal.signer_identity
        ):
            reasons.append(
                _reason(
                    "DS9-PRINCIPAL-SIGNING-KEY-MISMATCH",
                    "The principal issuer differs from the verified binding signer.",
                    "invalid_source",
                )
            )

        resolved_separation = self._optional_signed_model(
            gate_input.reviewer_separation_ref,
            expected_kind=REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.ReviewerSeparationCredential",
            expected_schema_version=REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
            model_type=ReviewerSeparationCredential,
            expected_tenant_id=gate_input.tenant_id,
            expected_run_id=gate_input.run_id,
            missing_code="DS9-REVIEWER-SEPARATION-PRODUCER-MISSING",
            reasons=reasons,
        )
        separation = (
            cast("ReviewerSeparationCredential", resolved_separation.model)
            if resolved_separation is not None
            else None
        )
        if (
            resolved_principal is not None
            and resolved_separation is not None
            and (
                resolved_principal.signer_identity == resolved_separation.signer_identity
                or resolved_principal.key_id == resolved_separation.key_id
            )
        ):
            reasons.append(
                _reason(
                    "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING",
                    "Principal and reviewer-separation attestations are not independent.",
                    "blocked",
                )
            )

        resolved_presentation = self._optional_signed_model(
            gate_input.presentation_contract_ref,
            expected_kind=HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionPresentationContract",
            expected_schema_version=HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
            model_type=HumanDecisionPresentationContract,
            expected_tenant_id=gate_input.tenant_id,
            expected_run_id=gate_input.run_id,
            missing_code="DS9-PRESENTATION-CONTRACT-PRODUCER-MISSING",
            reasons=reasons,
        )
        presentation = (
            cast("HumanDecisionPresentationContract", resolved_presentation.model)
            if resolved_presentation is not None
            else None
        )
        resolved_session = self._optional_signed_model(
            gate_input.exposure_session_ref,
            expected_kind=HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionExposureSession",
            expected_schema_version=HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
            model_type=HumanDecisionExposureSession,
            expected_tenant_id=gate_input.tenant_id,
            expected_run_id=gate_input.run_id,
            missing_code="DS9-EXPOSURE-SESSION-PRODUCER-MISSING",
            reasons=reasons,
        )
        session = (
            cast("HumanDecisionExposureSession", resolved_session.model)
            if resolved_session is not None
            else None
        )

        if request is not None and principal is not None:
            self._evaluate_principal(
                gate_input,
                request=request,
                principal=principal,
                bound_permission=bound_permission,
                require_bound_mutation=require_bound_mutation,
                now=now,
                reasons=reasons,
            )
        elif bound_permission is None and require_bound_mutation:
            reasons.append(
                _reason(
                    "DS9-DECISION-PERMISSION-UNVERIFIED",
                    "No bound action-permission proof reached the gate.",
                    "invalid_source",
                )
            )

        if request is not None and separation is not None and principal is not None and basis:
            request_digest = _sha256_ref(request.model_dump(mode="json"))
            if (
                separation.tenant_id != gate_input.tenant_id
                or separation.run_id != gate_input.run_id
                or separation.case_id != request.case_id
                or separation.decision_request_ref != request.request_ref
                or separation.decision_request_digest != request_digest
                or separation.reviewer_actor_ref != principal.actor_ref
                or basis.requester_actor_ref not in separation.reviewed_actor_refs
                or basis.requester_actor_ref == principal.actor_ref
                or principal.actor_ref in separation.reviewed_actor_refs
                or not separation.independence_established
                or not set(request.available_actions).issubset(separation.change_authority_actions)
            ):
                reasons.append(
                    _reason(
                        "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING",
                        "Reviewer independence or change authority is not established.",
                        "blocked",
                    )
                )
            if (
                separation.verifier_epoch != self._verifier_epoch()
                or separation.valid_from > now
                or now >= separation.valid_until
            ):
                reasons.append(
                    _reason(
                        "DS9-DECISION-REVALIDATION-REQUIRED",
                        "The signed reviewer-separation credential requires online revalidation.",
                        "revalidation_required",
                    )
                )

        if (
            basis is not None
            and basis_artifact is not None
            and resolved_principal is not None
            and basis_artifact.signer_identity == resolved_principal.signer_identity
        ):
            reasons.append(
                _reason(
                    "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING",
                    "The production basis producer and reviewer principal are not independent.",
                    "blocked",
                )
            )

        if (
            session is not None
            and gate_input.exposure_session_ref is not None
            and gate_input.principal_binding_ref is not None
            and principal is not None
            and request is not None
            and basis is not None
            and gate_input.basis_ref is not None
        ):
            events = self._resolve_exposure_events(
                session=session,
                session_artifact_ref=gate_input.exposure_session_ref,
                principal=principal,
                request=request,
                reasons=reasons,
            )
            exposure_issues = (
                _exposure_binding_issues(
                    basis_ref=gate_input.basis_ref,
                    request=request,
                    principal=principal,
                    principal_ref=gate_input.principal_binding_ref,
                    presentation=presentation,
                    presentation_ref=cast("str", gate_input.presentation_contract_ref),
                    session=session,
                    session_ref=gate_input.exposure_session_ref,
                    events=events,
                    now=now,
                )
                if presentation is not None and gate_input.presentation_contract_ref is not None
                else frozenset({"presentation", "session", "mandate", "evidence"})
            )
            self._append_exposure_gate_reasons(reasons, exposure_issues)

        request_digest = (
            _sha256_ref(request.model_dump(mode="json")) if request is not None else None
        )
        projection = self._projection(
            gate_input,
            reasons=reasons,
            decision_request_ref=request.request_ref if request is not None else None,
            decision_request_digest=request_digest,
            governed_action_key=basis.governed_action_key if basis is not None else None,
            required_artifact_digests=(
                session.required_artifact_digests if session is not None else ()
            ),
            exposure_event_refs=tuple(
                event.event_receipt_ref for event in events if event.event_receipt_ref is not None
            ),
        )
        valid_from, valid_until = self._resolved_production_interval(
            basis=basis,
            request=request,
            principal=principal,
            separation=separation,
            presentation=presentation,
            session=session,
        )
        receipts = (
            self._production_predicate_receipts(
                gate_input=gate_input,
                basis=basis,
                request=request,
                principal=principal,
                separation=separation,
                presentation=presentation,
                events=events,
            )
            if projection.status == "available"
            and all(
                value is not None
                for value in (
                    basis,
                    request,
                    principal,
                    separation,
                    presentation,
                    session,
                    gate_input.basis_ref,
                )
            )
            else ()
        )
        return _ResolvedGate(
            projection=projection,
            request=request,
            production_basis=basis,
            production_basis_ref=(basis_artifact.ref if basis_artifact is not None else None),
            principal=principal,
            principal_artifact_ref=(
                resolved_principal.ref if resolved_principal is not None else None
            ),
            separation=separation,
            separation_artifact_ref=(
                resolved_separation.ref if resolved_separation is not None else None
            ),
            presentation=presentation,
            presentation_artifact_ref=(
                resolved_presentation.ref if resolved_presentation is not None else None
            ),
            exposure_session=session,
            exposure_session_artifact_ref=(
                resolved_session.ref if resolved_session is not None else None
            ),
            exposure_events=events,
            predicate_receipts=receipts,
            valid_from=valid_from,
            valid_until=valid_until,
        )

    @staticmethod
    def _append_exposure_gate_reasons(
        reasons: list[HumanDecisionGateReason],
        exposure_issues: frozenset[str],
    ) -> None:
        if "presentation" in exposure_issues:
            reasons.append(
                _reason(
                    "DS9-PRESENTATION-CONTRACT-INVALID",
                    "The signed presentation contract is not current for this request.",
                    "blocked",
                )
            )
        if exposure_issues & {"presentation_current", "session_current"}:
            reasons.append(
                _reason(
                    "DS9-DECISION-REVALIDATION-REQUIRED",
                    "The signed presentation or exposure session requires online revalidation.",
                    "revalidation_required",
                )
            )
        if "session" in exposure_issues:
            reasons.append(
                _reason(
                    "DS9-EXPOSURE-SESSION-INVALID",
                    "The signed exposure session/event relationship is invalid.",
                    "blocked",
                )
            )
        if "mandate" in exposure_issues:
            reasons.append(
                _reason(
                    "DS9-MANDATE-NOT-SHOWN",
                    "No completed exact-byte receipt proves the mandate was shown.",
                    "blocked",
                )
            )
        if "evidence" in exposure_issues:
            reasons.append(
                _reason(
                    "DS9-EVIDENCE-NOT-OPENED",
                    "Required evidence lacks completed exact-byte exposure receipts.",
                    "blocked",
                )
            )
        if exposure_issues & {"mandate", "evidence"}:
            reasons.append(
                _reason(
                    "DS9-RUBBER-STAMP",
                    "Approval cannot proceed without shown mandate and opened evidence.",
                    "blocked",
                )
            )

    def _resolve_pa2_gate(
        self,
        gate_input: HumanDecisionPA2GateInput,
        *,
        bound_permission: (ActionPermissionVerification | BoundActionPermissionVerification | None),
        require_bound_mutation: bool,
    ) -> _ResolvedGate:
        reasons: list[HumanDecisionGateReason] = []
        now = self._now()
        source: AgentActionAuthorityDecision | None = None
        request: HumanDecisionRequest | None = None
        contract: DelegationContract | None = None
        principal: HumanDecisionPrincipalBinding | None = None
        separation: ReviewerSeparationCredential | None = None
        presentation: HumanDecisionPresentationContract | None = None
        session: HumanDecisionExposureSession | None = None
        envelope: DelegatedActionEnvelope | None = None
        events: tuple[HumanDecisionExposureAuditEvent, ...] = ()
        source_ref = gate_input.source_ref
        source_artifact_ref: str | None = None
        contract_artifact_ref: str | None = None

        try:
            resolved_source = self._read_signed_model(
                source_ref,
                expected_kind=_SOURCE_ARTIFACT_KIND,
                expected_schema_name=_SOURCE_SCHEMA_NAME,
                expected_schema_version=_SOURCE_SCHEMA_VERSION,
                model_type=self._agent_action_decision_type(),
                expected_tenant_id=gate_input.tenant_id,
                expected_run_id=gate_input.run_id,
            )
            source_artifact_ref = resolved_source.ref
            source = cast("AgentActionAuthorityDecision", cast("object", resolved_source.model))
            request = source.human_decision_request
            if source.outcome != "refused" or request is None:
                raise _ResolutionIssueError(
                    _reason(
                        "DS9-DECISION-SOURCE-INVALID",
                        "The source is not a refused action with a human-decision request.",
                        "invalid_source",
                    )
                )
            request_digest = _sha256_ref(request.model_dump(mode="json"))
            if (
                gate_input.decision_request_ref is not None
                and gate_input.decision_request_ref != request.request_ref
            ):
                raise _ResolutionIssueError(
                    _reason(
                        "DS9-DECISION-SOURCE-INVALID",
                        "The caller request selector differs from the signed source request.",
                        "invalid_source",
                    )
                )
            if (
                gate_input.decision_request_digest is not None
                and gate_input.decision_request_digest != request_digest
            ):
                raise _ResolutionIssueError(
                    _reason(
                        "DS9-DECISION-SOURCE-INVALID",
                        "The caller request digest differs from the signed source request.",
                        "invalid_source",
                    )
                )
            if gate_input.action_kind != source.action_kind:
                reasons.append(
                    _reason(
                        "DS9-AUTHORITY-CROSS-USE",
                        "Authority for one action kind cannot be reused for another.",
                        "blocked",
                    )
                )
            if (
                self._resolver_policy.expected_agent_operation is not None
                and source.operation_id != self._resolver_policy.expected_agent_operation
            ):
                reasons.append(
                    _reason(
                        "DS9-AUTHORITY-CROSS-USE",
                        "The signed source operation differs from deployment policy.",
                        "blocked",
                    )
                )
            if request.decision_due_at is not None and now > request.decision_due_at:
                reasons.append(
                    _reason(
                        "DS9-DECISION-TTL-EXPIRED",
                        "The signed decision due time has elapsed.",
                        "blocked",
                    )
                )
            if request.decidable_until is not None and now >= request.decidable_until:
                reasons.append(
                    _reason(
                        "DS9-DECISION-TTL-EXPIRED",
                        "The signed decidable interval has elapsed.",
                        "blocked",
                    )
                )
        except _ResolutionIssueError as exc:
            reasons.append(exc.reason)
        except Exception:
            reasons.append(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "The signed action source could not be verified and reconciled.",
                    "invalid_source",
                )
            )

        if source is not None and source.contract_ref is not None:
            try:
                resolved_contract = self._read_signed_model(
                    source.contract_ref,
                    expected_kind=_CONTRACT_ARTIFACT_KIND,
                    expected_schema_name=_CONTRACT_SCHEMA_NAME,
                    expected_schema_version=_CONTRACT_SCHEMA_VERSION,
                    model_type=DelegationContract,
                    expected_tenant_id=gate_input.tenant_id,
                    expected_run_id=None,
                )
                contract_artifact_ref = resolved_contract.ref
                contract = cast("DelegationContract", resolved_contract.model)
                if (
                    resolved_contract.signer_identity != contract.mandate_owner_ref
                    or (
                        gate_input.basis_ref is not None
                        and gate_input.basis_ref != source.contract_ref
                    )
                    or (
                        gate_input.basis_digest is not None
                        and gate_input.basis_digest != source.contract_ref
                    )
                ):
                    reasons.append(
                        _reason(
                            "DS9-DECISION-SOURCE-INVALID",
                            "The selected basis digest differs from the signed contract.",
                            "invalid_source",
                        )
                    )
            except _ResolutionIssueError as exc:
                reasons.append(exc.reason)
            except Exception:
                reasons.append(
                    _reason(
                        "DS9-MANDATE-NOT-SHOWN",
                        "The signed mandate/delegation contract did not resolve.",
                        "blocked",
                    )
                )
        else:
            reasons.append(
                _reason(
                    "DS9-MANDATE-NOT-SHOWN",
                    "The source did not bind a signed mandate/delegation contract.",
                    "blocked",
                )
            )

        resolved_principal = self._optional_signed_model(
            gate_input.principal_binding_ref,
            expected_kind=HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionPrincipalBinding",
            expected_schema_version=HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
            model_type=HumanDecisionPrincipalBinding,
            expected_tenant_id=gate_input.tenant_id,
            expected_run_id=gate_input.run_id,
            missing_code="DS9-PRINCIPAL-BINDING-PRODUCER-MISSING",
            reasons=reasons,
        )
        principal = (
            cast("HumanDecisionPrincipalBinding", resolved_principal.model)
            if resolved_principal is not None
            else None
        )
        if (
            principal is not None
            and resolved_principal is not None
            and principal.principal_issuer != resolved_principal.signer_identity
        ):
            reasons.append(
                _reason(
                    "DS9-PRINCIPAL-SIGNING-KEY-MISMATCH",
                    "The principal issuer differs from the verified binding signer.",
                    "invalid_source",
                )
            )

        resolved_separation = self._optional_signed_model(
            gate_input.reviewer_separation_ref,
            expected_kind=REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.ReviewerSeparationCredential",
            expected_schema_version=REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
            model_type=ReviewerSeparationCredential,
            expected_tenant_id=gate_input.tenant_id,
            expected_run_id=gate_input.run_id,
            missing_code="DS9-REVIEWER-SEPARATION-PRODUCER-MISSING",
            reasons=reasons,
        )
        separation = (
            cast("ReviewerSeparationCredential", resolved_separation.model)
            if resolved_separation is not None
            else None
        )
        if (
            resolved_principal is not None
            and resolved_separation is not None
            and (
                resolved_principal.signer_identity == resolved_separation.signer_identity
                or resolved_principal.key_id == resolved_separation.key_id
            )
        ):
            reasons.append(
                _reason(
                    "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING",
                    "Principal and reviewer-separation attestations are not independent.",
                    "blocked",
                )
            )

        resolved_presentation = self._optional_signed_model(
            gate_input.presentation_contract_ref,
            expected_kind=HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionPresentationContract",
            expected_schema_version=HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
            model_type=HumanDecisionPresentationContract,
            expected_tenant_id=gate_input.tenant_id,
            expected_run_id=gate_input.run_id,
            missing_code="DS9-PRESENTATION-CONTRACT-PRODUCER-MISSING",
            reasons=reasons,
        )
        presentation = (
            cast("HumanDecisionPresentationContract", resolved_presentation.model)
            if resolved_presentation is not None
            else None
        )
        resolved_session = self._optional_signed_model(
            gate_input.exposure_session_ref,
            expected_kind=HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionExposureSession",
            expected_schema_version=HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
            model_type=HumanDecisionExposureSession,
            expected_tenant_id=gate_input.tenant_id,
            expected_run_id=gate_input.run_id,
            missing_code="DS9-EXPOSURE-SESSION-PRODUCER-MISSING",
            reasons=reasons,
        )
        session = (
            cast("HumanDecisionExposureSession", resolved_session.model)
            if resolved_session is not None
            else None
        )

        if request is not None and principal is not None:
            self._evaluate_principal(
                gate_input,
                request=request,
                principal=principal,
                bound_permission=bound_permission,
                require_bound_mutation=require_bound_mutation,
                now=now,
                reasons=reasons,
            )
        elif bound_permission is None and require_bound_mutation:
            reasons.append(
                _reason(
                    "DS9-DECISION-PERMISSION-UNVERIFIED",
                    "No bound action-permission proof reached the gate.",
                    "invalid_source",
                )
            )
        if request is not None and separation is not None and principal is not None:
            request_digest = _sha256_ref(request.model_dump(mode="json"))
            if (
                separation.decision_request_ref != request.request_ref
                or separation.decision_request_digest != request_digest
                or separation.reviewer_actor_ref != principal.actor_ref
                or not separation.independence_established
                or not set(request.available_actions).issubset(separation.change_authority_actions)
            ):
                reasons.append(
                    _reason(
                        "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING",
                        "Reviewer independence or change authority is not established.",
                        "blocked",
                    )
                )
            if (
                separation.verifier_epoch != self._verifier_epoch()
                or separation.valid_from > now
                or now >= separation.valid_until
            ):
                reasons.append(
                    _reason(
                        "DS9-DECISION-REVALIDATION-REQUIRED",
                        "The signed reviewer-separation credential requires online revalidation.",
                        "revalidation_required",
                    )
                )
        if all(value is not None for value in (source, request, contract, principal, separation)):
            signer = self._custody.signer
            envelope, packet_issues = _pa2_packet_join_issues(
                source=cast("AgentActionAuthorityDecision", source),
                request=cast("HumanDecisionRequest", request),
                contract=cast("DelegationContract", contract),
                principal=cast("HumanDecisionPrincipalBinding", principal),
                separation=cast("ReviewerSeparationCredential", separation),
                basis_ref=gate_input.basis_digest,
                tenant_id=gate_input.tenant_id,
                run_id=gate_input.run_id,
                principal_audience=self._resolver_policy.principal_audience,
                required_reviewer_permission=self._resolver_policy.required_permission,
                verifier_epoch=self._verifier_epoch(),
                custody_key_id=signer.key_id if signer is not None else "",
                now=now,
            )
            if packet_issues & {"source", "principal"}:
                reasons.append(
                    _reason(
                        "DS9-DECISION-SOURCE-INVALID",
                        "The signed source/request/contract packet join is invalid.",
                        "invalid_source",
                    )
                )
            if "ttl" in packet_issues:
                reasons.append(
                    _reason(
                        "DS9-DECISION-TTL-EXPIRED",
                        "The exact signed delegation envelope is not live.",
                        "blocked",
                    )
                )
            if "separation" in packet_issues:
                reasons.append(
                    _reason(
                        "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING",
                        "Reviewer separation does not name the exact reviewed actor.",
                        "blocked",
                    )
                )
            if packet_issues & {"principal_current", "separation_current"}:
                reasons.append(
                    _reason(
                        "DS9-DECISION-REVALIDATION-REQUIRED",
                        "The signed delegation packet requires online revalidation.",
                        "revalidation_required",
                    )
                )
        if (
            session is not None
            and gate_input.exposure_session_ref is not None
            and gate_input.principal_binding_ref is not None
            and principal is not None
            and request is not None
        ):
            events = self._resolve_exposure_events(
                session=session,
                session_artifact_ref=gate_input.exposure_session_ref,
                principal=principal,
                request=request,
                reasons=reasons,
            )
            exposure_issues = (
                _exposure_binding_issues(
                    basis_ref=cast("str", source.contract_ref),
                    request=request,
                    principal=principal,
                    principal_ref=gate_input.principal_binding_ref,
                    presentation=presentation,
                    presentation_ref=gate_input.presentation_contract_ref,
                    session=session,
                    session_ref=gate_input.exposure_session_ref,
                    events=events,
                    now=now,
                )
                if source is not None
                and source.contract_ref is not None
                and presentation is not None
                and gate_input.presentation_contract_ref is not None
                else frozenset({"presentation", "session", "mandate", "evidence"})
            )
            if "presentation" in exposure_issues:
                reasons.append(
                    _reason(
                        "DS9-PRESENTATION-CONTRACT-INVALID",
                        "The signed presentation contract is not current for this request.",
                        "blocked",
                    )
                )
            if exposure_issues & {"presentation_current", "session_current"}:
                reasons.append(
                    _reason(
                        "DS9-DECISION-REVALIDATION-REQUIRED",
                        "The signed presentation or exposure session requires online revalidation.",
                        "revalidation_required",
                    )
                )
            if "session" in exposure_issues:
                reasons.append(
                    _reason(
                        "DS9-EXPOSURE-SESSION-INVALID",
                        "The signed exposure session/event relationship is invalid.",
                        "blocked",
                    )
                )
            if "mandate" in exposure_issues:
                reasons.append(
                    _reason(
                        "DS9-MANDATE-NOT-SHOWN",
                        "No completed exact-byte receipt proves the mandate was shown.",
                        "blocked",
                    )
                )
            if "evidence" in exposure_issues:
                reasons.append(
                    _reason(
                        "DS9-EVIDENCE-NOT-OPENED",
                        "Required evidence lacks completed exact-byte exposure receipts.",
                        "blocked",
                    )
                )
            if exposure_issues & {"mandate", "evidence"}:
                reasons.append(
                    _reason(
                        "DS9-RUBBER-STAMP",
                        "Approval cannot proceed without shown mandate and opened evidence.",
                        "blocked",
                    )
                )

        resolved_request_digest = (
            _sha256_ref(request.model_dump(mode="json")) if request is not None else None
        )
        governed_action_key = (
            _pa2_governed_action_key(
                source=source,
                contract=contract,
                envelope=envelope,
                tenant_id=gate_input.tenant_id,
                run_id=gate_input.run_id,
            )
            if source is not None and contract is not None and envelope is not None
            else None
        )
        projection = self._projection(
            gate_input,
            reasons=reasons,
            decision_request_ref=request.request_ref if request is not None else None,
            decision_request_digest=resolved_request_digest,
            governed_action_key=governed_action_key,
            required_artifact_digests=(
                session.required_artifact_digests if session is not None else ()
            ),
            exposure_event_refs=tuple(
                event.event_receipt_ref for event in events if event.event_receipt_ref is not None
            ),
        )
        valid_from, valid_until = self._resolved_interval(
            request=request,
            principal=principal,
            separation=separation,
            presentation=presentation,
            session=session,
            contract=contract,
            source=source,
        )
        receipts = (
            self._predicate_receipts(
                gate_input=gate_input,
                source=source,
                request=request,
                principal=principal,
                separation=separation,
                presentation=presentation,
                events=events,
            )
            if projection.status == "available"
            and all(
                value is not None
                for value in (
                    source,
                    request,
                    contract,
                    principal,
                    separation,
                    presentation,
                    session,
                )
            )
            else ()
        )
        return _ResolvedGate(
            projection=projection,
            source=source,
            source_artifact_ref=source_artifact_ref,
            request=request,
            contract=contract,
            contract_artifact_ref=contract_artifact_ref,
            principal=principal,
            principal_artifact_ref=(
                resolved_principal.ref if resolved_principal is not None else None
            ),
            separation=separation,
            separation_artifact_ref=(
                resolved_separation.ref if resolved_separation is not None else None
            ),
            presentation=presentation,
            presentation_artifact_ref=(
                resolved_presentation.ref if resolved_presentation is not None else None
            ),
            exposure_session=session,
            exposure_session_artifact_ref=(
                resolved_session.ref if resolved_session is not None else None
            ),
            exposure_events=events,
            predicate_receipts=receipts,
            valid_from=valid_from,
            valid_until=valid_until,
        )

    def _optional_signed_model(
        self,
        ref: str | None,
        *,
        expected_kind: str,
        expected_schema_name: str,
        expected_schema_version: str,
        model_type: type[_TModel],
        expected_tenant_id: str,
        expected_run_id: str,
        missing_code: str,
        reasons: list[HumanDecisionGateReason],
    ) -> _ResolvedSignedArtifact | None:
        if ref is None:
            reasons.append(
                _reason(
                    missing_code,
                    "A required verified institutional producer/ref is unavailable.",
                    "producer_missing",
                )
            )
            return None
        try:
            resolved = self._read_signed_model(
                ref,
                expected_kind=expected_kind,
                expected_schema_name=expected_schema_name,
                expected_schema_version=expected_schema_version,
                model_type=model_type,
                expected_tenant_id=expected_tenant_id,
                expected_run_id=expected_run_id,
            )
            return resolved
        except _ResolutionIssueError as exc:
            reasons.append(exc.reason)
            return None
        except Exception:
            reasons.append(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "A supplied institutional artifact failed exact verification.",
                    "invalid_source",
                )
            )
            return None

    def _read_signed_model(
        self,
        ref: str,
        *,
        expected_kind: str,
        expected_schema_name: str,
        expected_schema_version: str,
        model_type: type[_TModel],
        expected_tenant_id: str | None,
        expected_run_id: str | None,
    ) -> _ResolvedSignedArtifact:
        if not self._sink.has_artifact(ref):
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-ARTIFACT-MISSING",
                    "A supplied exact artifact ref is absent.",
                    "artifact_missing",
                )
            )
        if not self._custody.available:
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-PRODUCER-MISSING",
                    "The deployment verifier/trust policy is unavailable.",
                    "producer_missing",
                )
            )
        verifier = self._custody.verifier
        trust_policy = self._custody.trust_policy
        if verifier is None or trust_policy is None:
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-PRODUCER-MISSING",
                    "The deployment verifier/trust policy is incomplete.",
                    "producer_missing",
                )
            )
        manifest = self._sink.get_artifact_manifest(ref)
        schema = manifest.artifact_schema
        if (
            manifest.kind != expected_kind
            or schema is None
            or schema.name != expected_schema_name
            or schema.version != expected_schema_version
        ):
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "Artifact manifest kind/schema/version differs from the resolver contract.",
                    "invalid_source",
                )
            )
        producer = trust_policy.producer_for(
            artifact_kind=expected_kind,
            schema_name=expected_schema_name,
            schema_version=expected_schema_version,
        )
        verification = self._sink.verify_artifact_signature(
            ref,
            verifier,
            strict_identity=True,
        )
        signer_identity = verification.signer_identity
        key_id = verification.key_id
        custody_signer = self._custody.signer
        custody_owned = expected_kind in {
            HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
            HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
            HUMAN_DECISION_RECORD_ARTIFACT_KIND,
            _PRODUCTION_APPROVAL_PACKET_KIND,
        }
        trusted_identity = (
            producer.signer_identity
            if producer is not None
            else self._custody.signer_identity
            if custody_owned
            else None
        )
        trusted_key_id = (
            custody_signer.key_id
            if producer is None and custody_owned and custody_signer is not None
            else None
        )
        if producer is None and trusted_identity is None:
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-PRODUCER-MISSING",
                    "No exact deployment producer trust row exists for this artifact.",
                    "producer_missing",
                )
            )
        if (
            not verification.ok
            or signer_identity is None
            or signer_identity != trusted_identity
            or key_id is None
            or (trusted_key_id is not None and key_id != trusted_key_id)
        ):
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "Artifact signature/key/identity is not trusted by deployment policy.",
                    "invalid_source",
                )
            )
        try:
            report = self._sink.reconcile_authority_artifact(
                ref,
                expected_tenant_id=expected_tenant_id,
                expected_cell_id=None,
                expected_run_id=expected_run_id,
                expected_job_id=None,
            )
        except AuthorityReconciliationError as exc:
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "Artifact authority linkage conflicts with the requested runtime identity.",
                    "invalid_source",
                )
            ) from exc
        if report.durable_event_id is None:
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "Artifact has no reconciled durable event.",
                    "invalid_source",
                )
            )
        try:
            model = model_type.model_validate(
                canon.from_canonical_bytes(self._sink.get_artifact_bytes(ref))
            )
        except (TypeError, ValueError) as exc:
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "Artifact bytes fail the strict typed schema.",
                    "invalid_source",
                )
            ) from exc
        return _ResolvedSignedArtifact(
            model=model,
            ref=ref,
            signer_identity=signer_identity,
            key_id=key_id,
            durable_event_id=report.durable_event_id,
        )

    def _resolve_exposure_events(
        self,
        *,
        session: HumanDecisionExposureSession,
        session_artifact_ref: str,
        principal: HumanDecisionPrincipalBinding,
        request: HumanDecisionRequest,
        reasons: list[HumanDecisionGateReason],
    ) -> tuple[HumanDecisionExposureAuditEvent, ...]:
        if not self._access_audit_path.is_file():
            return ()
        events: list[HumanDecisionExposureAuditEvent] = []
        try:
            lines = self._access_audit_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            reasons.append(
                _reason(
                    "DS9-EXPOSURE-AUDIT-UNAVAILABLE",
                    "The existing access-audit trail could not be read.",
                    "invalid_source",
                )
            )
            return ()
        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, Mapping) or payload.get("event_type") != (
                "runtime.human_decision.exposure"
            ):
                continue
            try:
                event = HumanDecisionExposureAuditEvent.model_validate(payload)
            except (TypeError, ValueError):
                continue
            if (
                event.tenant_id != session.tenant_id
                or event.actor_ref != principal.actor_ref
                or event.run_id != session.run_id
                or event.request_ref != request.request_ref
                or event.request_digest != session.decision_request_digest
                or event.basis_digest != session.basis_digest
                or event.session_ref != session_artifact_ref
                or event.verifier_epoch != session.verifier_epoch
                or event.event_receipt_ref is None
            ):
                continue
            try:
                signed = self._read_signed_model(
                    event.event_receipt_ref,
                    expected_kind=HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
                    expected_schema_name="polisyos.runtime.HumanDecisionExposureAuditEvent",
                    expected_schema_version=HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
                    model_type=HumanDecisionExposureAuditEvent,
                    expected_tenant_id=session.tenant_id,
                    expected_run_id=session.run_id,
                )
                signed_event = cast("HumanDecisionExposureAuditEvent", signed.model)
                if signed_event != event.model_copy(update={"event_receipt_ref": None}):
                    continue
                body = self._sink.get_artifact_bytes(event.artifact_id)
                if event.content_digest != event.artifact_id or len(body) != event.delivered_bytes:
                    continue
            except Exception as exc:
                logger.warning(
                    "human_decision_exposure_event_rejected",
                    event_receipt_ref=event.event_receipt_ref,
                    error=str(exc),
                )
                continue
            events.append(event)
        unique = {
            event.event_receipt_ref: event
            for event in events
            if event.event_receipt_ref is not None
        }
        return tuple(unique[key] for key in sorted(unique))

    def _require_bound_route_permission(
        self,
        permission: ActionPermissionVerification | BoundActionPermissionVerification,
        *,
        tenant_id: str,
        run_id: str,
        route_permission: str,
        resource_kind: str,
        required_selectors: Mapping[str, str] | None = None,
        path_selector_parameters: tuple[str, ...] = (),
        query_selector_parameters: tuple[str, ...] = (),
        allow_empty_body: bool = False,
    ) -> ActionPermissionVerification:
        """Consume only the exact sealed route/resource proof for an authority effect."""
        from polisyos.runtime.http.authorization import (
            BoundActionPermissionVerification as BoundActionPermissionVerificationType,
        )
        from polisyos.runtime.http.authorization import ResourceBindingSource
        from polisyos.runtime.http.resource_binding import (
            BindingAuthority,
            BoundAuthorizationResource,
        )

        if type(permission) is not BoundActionPermissionVerificationType:
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-PERMISSION-UNVERIFIED")
        verification = permission.verification
        bound = permission.bound_resource
        expected_selectors = {
            "run_id": run_id,
            **dict(required_selectors or {}),
        }
        selector_map = dict(getattr(bound, "canonical_selectors", ()))
        binding = verification.requirement.resource_binding
        if (
            type(bound) is not BoundAuthorizationResource
            or verification.requirement is not bound.requirement
            or verification.requirement.permission.value != route_permission
            or binding.resource_kind != resource_kind
            or binding.source is not ResourceBindingSource.OWNED_EXISTING_PATH
            or binding.path_parameter != "run_id"
            or binding.path_selector_parameters != path_selector_parameters
            or binding.query_selector_parameters != query_selector_parameters
            or binding.allow_empty_body is not allow_empty_body
            or bound.tenant_id != tenant_id
            or bound.authority is not BindingAuthority.OWNERSHIP_VERIFIED
            or bound.resource_kind != f"{resource_kind}.ownership_verified"
            or set(selector_map) != set(expected_selectors)
            or any(
                selector_map.get(name)
                != json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                for name, value in expected_selectors.items()
            )
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-PERMISSION-UNVERIFIED")
        granted = {item.value for item in verification.granted_permissions}
        if not {route_permission, self._resolver_policy.required_permission}.issubset(granted):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-PERMISSION-UNVERIFIED")
        return verification

    def _evaluate_principal(
        self,
        gate_input: HumanDecisionPA2GateInput | HumanDecisionProductionGateInput,
        *,
        request: HumanDecisionRequest,
        principal: HumanDecisionPrincipalBinding,
        bound_permission: (ActionPermissionVerification | BoundActionPermissionVerification | None),
        require_bound_mutation: bool,
        now: datetime,
        reasons: list[HumanDecisionGateReason],
    ) -> None:
        if (
            principal.tenant_id != gate_input.tenant_id
            or principal.run_id != gate_input.run_id
            or principal.principal_audience != self._resolver_policy.principal_audience
        ):
            reasons.append(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "The signed principal binding is context-mismatched.",
                    "invalid_source",
                )
            )
        if (
            principal.verifier_epoch != self._verifier_epoch()
            or principal.valid_from > now
            or now >= principal.valid_until
        ):
            reasons.append(
                _reason(
                    "DS9-DECISION-REVALIDATION-REQUIRED",
                    "The signed principal binding requires online revalidation.",
                    "revalidation_required",
                )
            )
        if request.required_role not in principal.decision_roles:
            reasons.append(
                _reason(
                    "DS9-WRONG-ROLE",
                    "The signed principal roles do not include the request's required role.",
                    "blocked",
                )
            )
        permission = self._resolver_policy.required_permission
        if permission not in principal.permissions:
            reasons.append(
                _reason(
                    "DS9-DECISION-PERMISSION-UNVERIFIED",
                    "The signed principal binding lacks the exact decision permission.",
                    "invalid_source",
                )
            )
        if bound_permission is None and not require_bound_mutation:
            return
        if bound_permission is None:
            reasons.append(
                _reason(
                    "DS9-DECISION-PERMISSION-UNVERIFIED",
                    "No bound action-permission proof reached the gate.",
                    "invalid_source",
                )
            )
            return
        from polisyos.runtime.http.authorization import (
            ActionPermissionVerification as ActionPermissionVerificationType,
        )
        from polisyos.runtime.http.authorization import (
            BoundActionPermissionVerification as BoundActionPermissionVerificationType,
        )

        if require_bound_mutation:
            try:
                verification = self._require_bound_route_permission(
                    bound_permission,
                    tenant_id=gate_input.tenant_id,
                    run_id=gate_input.run_id,
                    route_permission=permission,
                    resource_kind="runtime.run.human_decision",
                )
            except HumanDecisionOperationalResolutionError:
                reasons.append(
                    _reason(
                        "DS9-DECISION-PERMISSION-UNVERIFIED",
                        "The route/OPA resource proof does not bind the signed principal.",
                        "invalid_source",
                    )
                )
                return
        elif type(bound_permission) is BoundActionPermissionVerificationType:
            verification = bound_permission.verification
        elif type(bound_permission) is ActionPermissionVerificationType:
            verification = bound_permission
        else:
            reasons.append(
                _reason(
                    "DS9-DECISION-PERMISSION-UNVERIFIED",
                    "The route permission proof has an unsupported type.",
                    "invalid_source",
                )
            )
            return
        granted = tuple(item.value for item in verification.granted_permissions)
        required = verification.requirement.permission.value
        if (
            verification.subject != principal.principal_subject
            or verification.tenant_id != gate_input.tenant_id
            or permission not in granted
            or (require_bound_mutation and required != permission)
        ):
            reasons.append(
                _reason(
                    "DS9-DECISION-PERMISSION-UNVERIFIED",
                    "The route/OPA resource proof does not bind the signed principal.",
                    "invalid_source",
                )
            )

    def _resolved_interval(
        self,
        *,
        request: HumanDecisionRequest | None,
        principal: HumanDecisionPrincipalBinding | None,
        separation: ReviewerSeparationCredential | None,
        presentation: HumanDecisionPresentationContract | None,
        session: HumanDecisionExposureSession | None,
        contract: DelegationContract | None,
        source: AgentActionAuthorityDecision | None,
    ) -> tuple[datetime | None, datetime | None]:
        if any(
            value is None
            for value in (request, principal, separation, presentation, session, contract, source)
        ):
            return None, None
        request = cast("HumanDecisionRequest", request)
        contract = cast("DelegationContract", contract)
        source = cast("AgentActionAuthorityDecision", source)
        envelope = next(
            (row for row in contract.action_envelopes if row.envelope_id == source.envelope_id),
            None,
        )
        if envelope is None:
            return None, None
        starts = (
            cast("HumanDecisionPrincipalBinding", principal).valid_from,
            cast("ReviewerSeparationCredential", separation).valid_from,
            cast("HumanDecisionPresentationContract", presentation).valid_from,
            cast("HumanDecisionExposureSession", session).valid_from,
            envelope.valid_from,
            request.requested_at,
        )
        ends = [
            cast("HumanDecisionPrincipalBinding", principal).valid_until,
            cast("ReviewerSeparationCredential", separation).valid_until,
            cast("HumanDecisionPresentationContract", presentation).valid_until,
            cast("HumanDecisionExposureSession", session).valid_until,
            envelope.valid_until,
        ]
        if request.decision_due_at is not None:
            ends.append(request.decision_due_at)
        if request.decidable_until is not None:
            ends.append(request.decidable_until)
        return max(starts), min(ends)

    def _resolved_production_interval(
        self,
        *,
        basis: ProductionHumanDecisionBasis | None,
        request: HumanDecisionRequest | None,
        principal: HumanDecisionPrincipalBinding | None,
        separation: ReviewerSeparationCredential | None,
        presentation: HumanDecisionPresentationContract | None,
        session: HumanDecisionExposureSession | None,
    ) -> tuple[datetime | None, datetime | None]:
        if any(
            value is None
            for value in (basis, request, principal, separation, presentation, session)
        ):
            return None, None
        typed_basis = cast("ProductionHumanDecisionBasis", basis)
        typed_request = cast("HumanDecisionRequest", request)
        starts = (
            typed_basis.valid_from,
            typed_request.requested_at,
            cast("HumanDecisionPrincipalBinding", principal).valid_from,
            cast("ReviewerSeparationCredential", separation).valid_from,
            cast("HumanDecisionPresentationContract", presentation).valid_from,
            cast("HumanDecisionExposureSession", session).valid_from,
        )
        ends = [
            typed_basis.valid_until,
            cast("HumanDecisionPrincipalBinding", principal).valid_until,
            cast("ReviewerSeparationCredential", separation).valid_until,
            cast("HumanDecisionPresentationContract", presentation).valid_until,
            cast("HumanDecisionExposureSession", session).valid_until,
        ]
        if typed_request.decision_due_at is not None:
            ends.append(typed_request.decision_due_at)
        if typed_request.decidable_until is not None:
            ends.append(typed_request.decidable_until)
        return max(starts), min(ends)

    def _predicate_receipts(
        self,
        *,
        gate_input: HumanDecisionPA2GateInput,
        source: AgentActionAuthorityDecision | None,
        request: HumanDecisionRequest | None,
        principal: HumanDecisionPrincipalBinding | None,
        separation: ReviewerSeparationCredential | None,
        presentation: HumanDecisionPresentationContract | None,
        events: Sequence[HumanDecisionExposureAuditEvent],
    ) -> tuple[HumanDecisionPredicateReceipt, ...]:
        if any(value is None for value in (source, request, principal, separation, presentation)):
            return ()
        source = cast("AgentActionAuthorityDecision", source)
        request = cast("HumanDecisionRequest", request)
        principal = cast("HumanDecisionPrincipalBinding", principal)
        separation = cast("ReviewerSeparationCredential", separation)
        presentation = cast("HumanDecisionPresentationContract", presentation)
        evidence = tuple(
            event.event_receipt_ref for event in events if event.event_receipt_ref is not None
        )
        rows: tuple[
            tuple[
                HumanDecisionRecordPredicate,
                HumanDecisionRecordPredicateProvenance,
                tuple[str | None, ...],
                str,
            ],
            ...,
        ] = (
            (
                "identity_permission",
                "recomputed",
                (gate_input.principal_binding_ref,),
                "DS9-PREDICATE-IDENTITY-PERMISSION",
            ),
            (
                "role_mandate_or_basis",
                "independently_reconciled",
                (source.contract_ref,),
                "DS9-PREDICATE-ROLE-MANDATE",
            ),
            (
                "operation_accountability",
                "recomputed",
                (gate_input.source_ref,),
                "DS9-PREDICATE-OPERATION-ACCOUNTABILITY",
            ),
            (
                "currentness",
                "recomputed",
                (gate_input.exposure_session_ref,),
                "DS9-PREDICATE-CURRENTNESS",
            ),
            (
                "right_decision_time",
                "recomputed",
                (request.request_ref,),
                "DS9-PREDICATE-RIGHT-DECISION-TIME",
            ),
            (
                "reviewer_independence_change",
                "independently_reconciled",
                (gate_input.reviewer_separation_ref, separation.credential_ref),
                "DS9-PREDICATE-REVIEWER-INDEPENDENCE",
            ),
            (
                "evidence_exposure",
                "independently_reconciled",
                evidence,
                "DS9-PREDICATE-EVIDENCE-EXPOSURE",
            ),
            (
                "presentation_format_channel",
                "independently_reconciled",
                (gate_input.presentation_contract_ref, presentation.contract_ref),
                "DS9-PREDICATE-PRESENTATION-FORMAT",
            ),
            (
                "source_producer_trust",
                "independently_reconciled",
                (gate_input.source_ref,),
                "DS9-PREDICATE-SOURCE-TRUST",
            ),
        )
        return tuple(
            HumanDecisionPredicateReceipt(
                predicate=predicate,
                satisfied=True,
                provenance=provenance,
                evidence_refs=tuple(ref for ref in refs if ref is not None),
                reason_code=reason_code,
                reason=f"{predicate} passed against exact signed inputs.",
                rule_version_ref=request.rule_version_ref,
            )
            for predicate, provenance, refs, reason_code in rows
        )

    def _production_predicate_receipts(
        self,
        *,
        gate_input: HumanDecisionProductionGateInput,
        basis: ProductionHumanDecisionBasis | None,
        request: HumanDecisionRequest | None,
        principal: HumanDecisionPrincipalBinding | None,
        separation: ReviewerSeparationCredential | None,
        presentation: HumanDecisionPresentationContract | None,
        events: Sequence[HumanDecisionExposureAuditEvent],
    ) -> tuple[HumanDecisionPredicateReceipt, ...]:
        if any(
            value is None
            for value in (basis, request, principal, separation, presentation, gate_input.basis_ref)
        ):
            return ()
        typed_request = cast("HumanDecisionRequest", request)
        typed_separation = cast("ReviewerSeparationCredential", separation)
        typed_presentation = cast("HumanDecisionPresentationContract", presentation)
        basis_ref = cast("str", gate_input.basis_ref)
        evidence = tuple(
            event.event_receipt_ref for event in events if event.event_receipt_ref is not None
        )
        rows: tuple[
            tuple[
                HumanDecisionRecordPredicate,
                HumanDecisionRecordPredicateProvenance,
                tuple[str | None, ...],
                str,
            ],
            ...,
        ] = (
            (
                "identity_permission",
                "recomputed",
                (gate_input.principal_binding_ref,),
                "DS9-PREDICATE-IDENTITY-PERMISSION",
            ),
            (
                "role_mandate_or_basis",
                "independently_reconciled",
                (basis_ref,),
                "DS9-PREDICATE-ROLE-BASIS",
            ),
            (
                "operation_accountability",
                "recomputed",
                (basis_ref,),
                "DS9-PREDICATE-OPERATION-ACCOUNTABILITY",
            ),
            (
                "currentness",
                "recomputed",
                (gate_input.exposure_session_ref, basis_ref),
                "DS9-PREDICATE-CURRENTNESS",
            ),
            (
                "right_decision_time",
                "recomputed",
                (typed_request.request_ref,),
                "DS9-PREDICATE-RIGHT-DECISION-TIME",
            ),
            (
                "reviewer_independence_change",
                "independently_reconciled",
                (gate_input.reviewer_separation_ref, typed_separation.credential_ref),
                "DS9-PREDICATE-REVIEWER-INDEPENDENCE",
            ),
            (
                "evidence_exposure",
                "independently_reconciled",
                evidence,
                "DS9-PREDICATE-EVIDENCE-EXPOSURE",
            ),
            (
                "presentation_format_channel",
                "independently_reconciled",
                (gate_input.presentation_contract_ref, typed_presentation.contract_ref),
                "DS9-PREDICATE-PRESENTATION-FORMAT",
            ),
            (
                "source_producer_trust",
                "independently_reconciled",
                (basis_ref,),
                "DS9-PREDICATE-SOURCE-TRUST",
            ),
        )
        return tuple(
            HumanDecisionPredicateReceipt(
                predicate=predicate,
                satisfied=True,
                provenance=provenance,
                evidence_refs=tuple(ref for ref in refs if ref is not None),
                reason_code=reason_code,
                reason=f"{predicate} passed against exact signed production inputs.",
                rule_version_ref=typed_request.rule_version_ref,
            )
            for predicate, provenance, refs, reason_code in rows
        )

    def _build_record(
        self,
        *,
        command: HumanDecisionCreateCommand,
        resolved: _ResolvedGate,
        source: AgentActionAuthorityDecision | None,
        request: HumanDecisionRequest,
        contract: DelegationContract | None,
        production_basis: ProductionHumanDecisionBasis | None,
        production_basis_ref: str | None,
        principal: HumanDecisionPrincipalBinding,
        presentation: HumanDecisionPresentationContract,
        session: HumanDecisionExposureSession,
        attempt_id: str,
        governed_action_key: str,
        binding_sha256: str,
        reservation_id: str,
        reservation_version: int,
        recorded_at: datetime,
    ) -> HumanDecisionRecord:
        signer = self._custody.signer
        signer_identity = self._custody.signer_identity
        if signer is None or signer_identity is None:
            raise HumanDecisionPersistenceError("custody signer is unavailable")
        if resolved.valid_from is None or resolved.valid_until is None:
            raise HumanDecisionPersistenceError("resolved validity interval is absent")
        request_digest = _sha256_ref(request.model_dump(mode="json"))
        event_refs = tuple(
            event.event_receipt_ref
            for event in resolved.exposure_events
            if event.event_receipt_ref is not None
        )
        if isinstance(command.gate_input, HumanDecisionPA2GateInput):
            if source is None or contract is None or source.contract_ref is None:
                raise HumanDecisionPersistenceError("record builder lost its PA2 authority inputs")
            resolved_source_ref = command.gate_input.source_ref
            resolved_basis_ref = source.contract_ref
            mandate_source_refs = [contract.contract_ref, source.contract_ref]
        else:
            if production_basis is None or production_basis_ref is None:
                raise HumanDecisionPersistenceError(
                    "record builder lost its production authority inputs"
                )
            resolved_source_ref = production_basis_ref
            resolved_basis_ref = production_basis_ref
            mandate_source_refs = [production_basis_ref]
        return HumanDecisionRecord(
            schema_version=HUMAN_DECISION_RECORD_V2,
            record_id=f"human-decision-{attempt_id[-32:]}",
            record_ref=f"runtime://human-decisions/{attempt_id}",
            case_id=request.case_id,
            human_decision_request_ref=request.request_ref,
            actor_ref=principal.actor_ref,
            actor_role=request.required_role,
            decided_at=recorded_at,
            decision_action_exercised=command.decision_action,
            evidence_summary_ref=presentation.contract_ref,
            disconfirming_evidence_refs=list(request.disconfirming_evidence_refs),
            active_choice=True,
            accountability_statement=command.accountability_statement,
            mandate_record_ref=request.s6_mandate_record_ref,
            mandate_source_refs=mandate_source_refs,
            five_rights_check=derive_five_rights_check(resolved.predicate_receipts),
            responsibility_integrity=ResponsibilityIntegrityCheck(
                status="pass",
                pattern_ids=["P26", "P05", "P37"],
                reason="All nine gate predicates were recomputed or independently reconciled.",
                missing_requirements=[],
                rule_version_ref=request.rule_version_ref,
            ),
            authority_boundary=_human_act_boundary(request.rule_version_ref),
            provenance_refs=[
                resolved_source_ref,
                request.request_ref,
                command.gate_input.principal_binding_ref or "",
                command.gate_input.reviewer_separation_ref or "",
                command.gate_input.presentation_contract_ref or "",
                command.gate_input.exposure_session_ref or "",
                *event_refs,
            ],
            rule_version_ref=request.rule_version_ref,
            created_at=recorded_at,
            tenant_id=command.gate_input.tenant_id,
            run_id=command.gate_input.run_id,
            decision_attempt_id=attempt_id,
            governed_action_key=governed_action_key,
            binding_sha256=binding_sha256,
            source_kind=command.gate_input.source_kind,
            source_ref=resolved_source_ref,
            source_digest=resolved_source_ref,
            decision_request_digest=request_digest,
            basis_ref=resolved_basis_ref,
            basis_digest=resolved_basis_ref,
            principal_binding_ref=command.gate_input.principal_binding_ref,
            principal_binding_digest=command.gate_input.principal_binding_ref,
            reviewer_separation_ref=command.gate_input.reviewer_separation_ref,
            reviewer_separation_digest=command.gate_input.reviewer_separation_ref,
            presentation_contract_ref=command.gate_input.presentation_contract_ref,
            presentation_contract_digest=command.gate_input.presentation_contract_ref,
            exposure_session_ref=command.gate_input.exposure_session_ref,
            exposure_session_digest=command.gate_input.exposure_session_ref,
            canonical_actor=HumanDecisionCanonicalActor(
                issuer=principal.principal_issuer,
                audience=principal.principal_audience,
                subject=principal.principal_subject,
                tenant_id=principal.tenant_id,
                actor_ref=principal.actor_ref,
                signing_key_id=principal.actor_key_id,
                signed_roles=principal.decision_roles,
            ),
            decision_mode=command.decision_mode,
            dissent_statement=command.dissent_statement,
            override_reason=command.override_reason,
            blocking_reason=command.blocking_reason,
            predicate_receipts=resolved.predicate_receipts,
            exposure_event_refs=event_refs,
            exposure_artifact_digests=tuple(session.required_artifact_digests),
            verifier_epoch=self._verifier_epoch(),
            requested_at=request.requested_at,
            observed_at=recorded_at,
            recorded_at=recorded_at,
            valid_from=resolved.valid_from,
            valid_until=resolved.valid_until,
            reservation_id=reservation_id,
            reservation_version=reservation_version,
            custody_signer_identity=signer_identity,
            custody_key_id=signer.key_id,
            custody_boundary=_custody_boundary(request.rule_version_ref),
        )

    def _record_authority_fields(
        self,
        *,
        record: HumanDecisionRecord,
        context: HumanDecisionWriteContext,
        input_refs: tuple[str, ...],
    ) -> Mapping[str, object]:
        closure_hash = _sha256_ref(
            {
                "tenant_id": context.tenant_id,
                "run_id": context.run_id,
                "job_id": context.job_id,
                "input_refs": input_refs,
                "binding_sha256": record.binding_sha256,
            }
        )
        generated_at = cast("datetime", record.recorded_at).isoformat()
        return {
            "evidence_id": record.record_id,
            "evidence_class": "authority_bearing",
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "owner": context.owner,
            "reader_contract": "runtime_quality.human_decision_record.reader",
            "reader_contract_version": "2.0",
            "tenant_id": context.tenant_id,
            "cell_id": context.cell_id,
            "run_id": context.run_id,
            "job_id": context.job_id,
            "trace_id": context.trace_id,
            "span_id": context.span_id,
            "parent_span_id": context.parent_span_id,
            "requested_execution_profile": context.requested_execution_profile,
            "effective_execution_profile": context.effective_execution_profile,
            "phase": "human_decision_custody",
            "generated_at": generated_at,
            "as_of_time": generated_at,
            "same_input_closure": {
                "closure_id": f"human-decision.{closure_hash[7:31]}",
                "status": "closed",
                "run_id": context.run_id,
                "job_id": context.job_id,
                "tenant_id": context.tenant_id,
                "cell_id": context.cell_id,
                "effective_mode_ref": context.effective_mode_ref,
                "degradation_ledger_ref": context.degradation_ledger_ref,
                "evidence_input_refs": input_refs,
                "closure_sha256": closure_hash,
            },
            "input_refs": input_refs,
            "effective_mode_ref": context.effective_mode_ref,
            "degradation_ledger_ref": context.degradation_ledger_ref,
            "semantic_binding_ref": record.binding_sha256,
            "validation_status": "pass",
            "blocking_status": "non_blocking",
            "governance": GovernanceMetadata(
                classification="restricted",
                authority_boundary="runtime.human_decision_record_custody",
                pii="identity_bound",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="signed_reason_and_independent_reviewer_required",
                approval_policy="nine_predicates_and_step_up_required",
            ),
            "event_id": f"evt_human_decision_{cast('str', record.binding_sha256)[7:31]}",
            "event_source": "polisyos.runtime.http.human_decisions",
            "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
            "event_subject": f"run/{context.run_id}/job/{context.job_id}/human-decision",
            "state_after": "persisted",
            "canon_spec": canon.CanonSpec(),
        }

    def _production_packet_authority_fields(
        self,
        *,
        packet: ProductionApprovalPacket,
        context: HumanDecisionWriteContext,
        input_refs: tuple[str, ...],
    ) -> Mapping[str, object]:
        """Build the existing authority-writer envelope for one V2 packet."""

        closure_hash = _sha256_ref(
            {
                "tenant_id": context.tenant_id,
                "run_id": context.run_id,
                "job_id": context.job_id,
                "input_refs": input_refs,
                "governed_action_key": packet.governed_action_key,
            }
        )
        generated_at = packet.generated_at.isoformat()
        return {
            "evidence_id": f"production-approval-{closure_hash[7:31]}",
            "evidence_class": "authority_bearing",
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "owner": context.owner,
            "reader_contract": _PRODUCTION_APPROVAL_PACKET_KIND + ".reader",
            "reader_contract_version": "2.0",
            "tenant_id": context.tenant_id,
            "cell_id": context.cell_id,
            "run_id": context.run_id,
            "job_id": context.job_id,
            "trace_id": context.trace_id,
            "span_id": context.span_id,
            "parent_span_id": context.parent_span_id,
            "requested_execution_profile": context.requested_execution_profile,
            "effective_execution_profile": context.effective_execution_profile,
            "phase": "production_approval_custody",
            "generated_at": generated_at,
            "as_of_time": generated_at,
            "same_input_closure": {
                "closure_id": f"production-approval.{closure_hash[7:31]}",
                "status": "closed",
                "run_id": context.run_id,
                "job_id": context.job_id,
                "tenant_id": context.tenant_id,
                "cell_id": context.cell_id,
                "effective_mode_ref": context.effective_mode_ref,
                "degradation_ledger_ref": context.degradation_ledger_ref,
                "evidence_input_refs": input_refs,
                "closure_sha256": closure_hash,
            },
            "input_refs": input_refs,
            "effective_mode_ref": context.effective_mode_ref,
            "degradation_ledger_ref": context.degradation_ledger_ref,
            "semantic_binding_ref": packet.governed_action_key,
            "validation_status": "pass",
            "blocking_status": "non_blocking",
            "governance": GovernanceMetadata(
                classification="restricted",
                authority_boundary=_PRODUCTION_APPROVAL_PACKET_KIND + "_custody",
                pii="identity_bound",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="signed_reason_and_independent_reviewer_required",
                approval_policy="concrete_resolver_currentness_required",
            ),
            "event_id": f"evt_production_approval_{closure_hash[7:31]}",
            "event_source": "polisyos.runtime.http.production_approval",
            "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
            "event_subject": f"run/{context.run_id}/job/{context.job_id}/production-approval",
            "state_after": "persisted",
            "canon_spec": canon.CanonSpec(forbid_floats=False),
        }

    def _freeze_failed_reservation(
        self,
        *,
        command: HumanDecisionCreateCommand,
        governed_action_key: str,
        reservation_id: str,
        reservation_version: int,
        record_ref: str | None,
        durable_event_id: str | None,
        signature_verified: bool,
        write_context: HumanDecisionWriteContext,
    ) -> None:
        try:
            marked = self._sink.mark_recovery_required(
                tenant_id=command.gate_input.tenant_id,
                governed_action_key=governed_action_key,
                reservation_id=reservation_id,
                reservation_version=reservation_version,
                record_ref=record_ref if durable_event_id is not None else None,
                record_sha256=record_ref if durable_event_id is not None else None,
                durable_event_id=durable_event_id,
            )
            if (
                signature_verified
                and record_ref is not None
                and durable_event_id is not None
                and self._custody.verifier is not None
                and self._custody.signer_identity is not None
                and self._custody.signer is not None
                and marked.state == "recovery_required"
            ):
                self._sink.reconcile_orphan_reservation(
                    tenant_id=command.gate_input.tenant_id,
                    governed_action_key=governed_action_key,
                    reservation_id=reservation_id,
                    reservation_version=reservation_version,
                    verifier=self._custody.verifier,
                    expected_signer_identity=self._custody.signer_identity,
                    expected_key_id=self._custody.signer.key_id,
                    expected_cell_id=write_context.cell_id,
                    expected_run_id=write_context.run_id,
                    expected_job_id=write_context.job_id,
                    reconciled_at=self._now(),
                )
        except Exception:
            return

    def _verify_record_signature(
        self,
        record_ref: str,
        record: HumanDecisionRecord,
    ) -> None:
        verifier = self._custody.verifier
        if verifier is None:
            raise ValueError("human-decision verifier unavailable")
        result = self._sink.verify_artifact_signature(
            record_ref,
            verifier,
            strict_identity=True,
        )
        if (
            not result.ok
            or result.signer_identity != record.custody_signer_identity
            or result.key_id != record.custody_key_id
        ):
            raise ValueError("human-decision custody signature changed")

    def _assert_record_manifest(self, record_ref: str) -> None:
        manifest = self._sink.get_artifact_manifest(record_ref)
        schema = manifest.artifact_schema
        if (
            manifest.kind != HUMAN_DECISION_RECORD_ARTIFACT_KIND
            or schema is None
            or schema.name != _RECORD_SCHEMA_NAME
            or schema.version != HUMAN_DECISION_RECORD_MANIFEST_VERSION
        ):
            raise ValueError("human-decision record manifest changed")

    def _revalidate_record_inputs(
        self,
        record: HumanDecisionRecord,
        adapter: HumanDecisionPA2GatewayAdapterInput,
        *,
        now: datetime,
    ) -> _ResolvedPA2OperationalAuthority:
        if (
            record.principal_binding_ref is None
            or record.reviewer_separation_ref is None
            or record.presentation_contract_ref is None
            or record.exposure_session_ref is None
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
        if (
            adapter.delegation_contract_ref != adapter.delegation_contract_digest
            or adapter.delegation_contract_ref != record.basis_ref
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
        source_resolved = self._read_signed_model(
            cast("str", record.source_ref),
            expected_kind=_SOURCE_ARTIFACT_KIND,
            expected_schema_name=_SOURCE_SCHEMA_NAME,
            expected_schema_version=_SOURCE_SCHEMA_VERSION,
            model_type=self._agent_action_decision_type(),
            expected_tenant_id=adapter.tenant_id,
            expected_run_id=adapter.run_id,
        )
        source = cast("AgentActionAuthorityDecision", cast("object", source_resolved.model))
        request = source.human_decision_request
        if (
            request is None
            or source.contract_ref != adapter.delegation_contract_ref
            or source.operation_id != adapter.expected_operation
            or request.request_ref != adapter.decision_request_ref
            or _sha256_ref(request.model_dump(mode="json")) != adapter.decision_request_digest
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")

        contract_resolved = self._read_signed_model(
            adapter.delegation_contract_ref,
            expected_kind=_CONTRACT_ARTIFACT_KIND,
            expected_schema_name=_CONTRACT_SCHEMA_NAME,
            expected_schema_version=_CONTRACT_SCHEMA_VERSION,
            model_type=DelegationContract,
            expected_tenant_id=adapter.tenant_id,
            expected_run_id=None,
        )
        contract = cast("DelegationContract", contract_resolved.model)
        envelope = next(
            (row for row in contract.action_envelopes if row.envelope_id == source.envelope_id),
            None,
        )
        if (
            envelope is None
            or contract_resolved.signer_identity != contract.mandate_owner_ref
            or source.envelope_ref != adapter.delegation_envelope_ref
            or envelope.envelope_ref != adapter.delegation_envelope_ref
            or _sha256_ref(envelope.model_dump(mode="json")) != adapter.delegation_envelope_digest
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")

        principal_resolved = self._read_signed_model(
            record.principal_binding_ref,
            expected_kind=HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionPrincipalBinding",
            expected_schema_version=HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
            model_type=HumanDecisionPrincipalBinding,
            expected_tenant_id=adapter.tenant_id,
            expected_run_id=adapter.run_id,
        )
        principal = cast("HumanDecisionPrincipalBinding", principal_resolved.model)
        actor = record.canonical_actor
        if (
            actor is None
            or principal.principal_issuer != principal_resolved.signer_identity
            or principal.actor_ref != record.actor_ref
            or principal.actor_ref != actor.actor_ref
            or principal.actor_key_id != actor.signing_key_id
            or principal.decision_roles != actor.signed_roles
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")

        separation_resolved = self._read_signed_model(
            record.reviewer_separation_ref,
            expected_kind=REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.ReviewerSeparationCredential",
            expected_schema_version=REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
            model_type=ReviewerSeparationCredential,
            expected_tenant_id=adapter.tenant_id,
            expected_run_id=adapter.run_id,
        )
        separation = cast("ReviewerSeparationCredential", separation_resolved.model)
        if (
            principal_resolved.signer_identity == separation_resolved.signer_identity
            or principal_resolved.key_id == separation_resolved.key_id
            or not separation.independence_established
            or separation.reviewer_actor_ref != record.actor_ref
            or record.decision_action_exercised not in separation.change_authority_actions
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")

        signer = self._custody.signer
        _, packet_issues = _pa2_packet_join_issues(
            source=source,
            request=request,
            contract=contract,
            principal=principal,
            separation=separation,
            basis_ref=adapter.delegation_contract_ref,
            tenant_id=adapter.tenant_id,
            run_id=adapter.run_id,
            principal_audience=self._resolver_policy.principal_audience,
            required_reviewer_permission=self._resolver_policy.required_permission,
            verifier_epoch=self._verifier_epoch(),
            custody_key_id=signer.key_id if signer is not None else "",
            now=now,
        )
        if packet_issues & {"ttl", "principal_current", "separation_current"}:
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-V1-REVALIDATION")
        if packet_issues:
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")

        presentation_resolved = self._read_signed_model(
            record.presentation_contract_ref,
            expected_kind=HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionPresentationContract",
            expected_schema_version=HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
            model_type=HumanDecisionPresentationContract,
            expected_tenant_id=adapter.tenant_id,
            expected_run_id=adapter.run_id,
        )
        presentation = cast("HumanDecisionPresentationContract", presentation_resolved.model)
        session_resolved = self._read_signed_model(
            record.exposure_session_ref,
            expected_kind=HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
            expected_schema_name="polisyos.runtime.HumanDecisionExposureSession",
            expected_schema_version=HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
            model_type=HumanDecisionExposureSession,
            expected_tenant_id=adapter.tenant_id,
            expected_run_id=adapter.run_id,
        )
        session = cast("HumanDecisionExposureSession", session_resolved.model)
        if (
            presentation.decision_request_digest != adapter.decision_request_digest
            or session.decision_request_digest != adapter.decision_request_digest
            or session.basis_digest != adapter.basis_digest
            or session.presentation_contract_ref != record.presentation_contract_ref
            or tuple(session.required_artifact_digests)
            != tuple(record.exposure_artifact_digests or ())
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")

        events: list[HumanDecisionExposureAuditEvent] = []
        event_refs = tuple(record.exposure_event_refs or ())
        if len(event_refs) != len(set(event_refs)):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
        for event_ref in event_refs:
            event_resolved = self._read_signed_model(
                event_ref,
                expected_kind=HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
                expected_schema_name="polisyos.runtime.HumanDecisionExposureAuditEvent",
                expected_schema_version=HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
                model_type=HumanDecisionExposureAuditEvent,
                expected_tenant_id=adapter.tenant_id,
                expected_run_id=adapter.run_id,
            )
            event = cast("HumanDecisionExposureAuditEvent", event_resolved.model)
            body = self._sink.get_artifact_bytes(event.artifact_id)
            if (
                event.event_receipt_ref is not None
                or event.session_ref != record.exposure_session_ref
                or event.actor_ref != record.actor_ref
                or event.request_digest != adapter.decision_request_digest
                or event.basis_digest != adapter.basis_digest
                or event.content_digest != event.artifact_id
                or len(body) != event.delivered_bytes
            ):
                raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
            events.append(event)
        exposure_issues = _exposure_binding_issues(
            basis_ref=adapter.basis_digest,
            request=request,
            principal=principal,
            principal_ref=record.principal_binding_ref,
            presentation=presentation,
            presentation_ref=record.presentation_contract_ref,
            session=session,
            session_ref=record.exposure_session_ref,
            events=events,
            now=now,
        )
        if exposure_issues & {"presentation_current", "session_current"}:
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-V1-REVALIDATION")
        if exposure_issues:
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
        return _ResolvedPA2OperationalAuthority(
            record=record,
            source=source,
            request=request,
            contract=contract,
            envelope=envelope,
            request_digest=_sha256_ref(request.model_dump(mode="json")),
        )

    def _assert_live_pa2_inputs(
        self,
        resolution: _ResolvedPA2OperationalAuthority,
        *,
        evaluated_at: datetime,
        operation: object,
        invocation: object,
        intent: object,
        bound_permission: object,
        resolved_contract: object,
        admission: object,
        admission_ref: str,
        selected_envelope: object,
        effect_binding: object,
    ) -> None:
        """Bind raw evaluator inputs to the exact signed packet before effect use."""

        authority = import_module("polisyos.runtime.quality.agent_action_authority")
        expected_types = (
            (operation, authority.OperationContract),
            (invocation, authority.OperationInvocationRecord),
            (intent, authority.AgentActionIntent),
            (resolved_contract, authority.ResolvedDelegationContract),
            (admission, authority.AgentActionAdmissionBundle),
            (selected_envelope, DelegatedActionEnvelope),
            (effect_binding, authority.AgentActionEffectBinding),
        )
        if any(type(value) is not expected for value, expected in expected_types):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")
        live_operation = cast("_LiveOperation", operation)
        live_invocation = cast("_LiveInvocation", invocation)
        live_intent = cast("_LiveIntent", intent)
        live_contract = cast("_LiveResolvedContract", resolved_contract)
        live_envelope = cast("DelegatedActionEnvelope", selected_envelope)
        live_binding = cast("_LiveEffectBinding", effect_binding)
        try:
            operation_hash = authority.agent_action_content_hash(operation)
            invocation_hash = authority.agent_action_content_hash(invocation)
            intent_hash = authority.agent_action_content_hash(intent)
            permission_hash = authority.agent_action_permission_hash(bound_permission)
            source_permission_hash = authority.agent_action_content_hash(
                resolution.source.permission_snapshot
            )
            admission_digest = authority.agent_action_content_hash(admission)
            envelope_digest = authority.agent_action_content_hash(selected_envelope)
        except (TypeError, ValueError):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID") from None
        source = resolution.source
        record = resolution.record
        request = resolution.request
        if (
            admission_ref != admission_digest
            or source.action_kind != live_intent.action_kind
            or source.operation_id != live_operation.operation_id
            or source.operation_version != live_operation.operation_version
            or source.operation_content_hash != operation_hash
            or source.invocation_id != live_invocation.invocation_id
            or source.invocation_content_hash != invocation_hash
            or source.intent_content_hash != intent_hash
            or source.bound_resource_digest != live_contract.resolved_for_resource_digest
            or source.contract_ref != live_contract.contract_cas_ref
            or source.contract_content_hash != live_contract.contract_payload_hash
            or source.admission_bundle_ref != admission_ref
            or source.envelope_id != live_envelope.envelope_id
            or source.envelope_ref != live_envelope.envelope_ref
            or envelope_digest != _sha256_ref(resolution.envelope.model_dump(mode="json"))
            or source.effect_binding_id != live_binding.binding_id
            or source.effect_binding_digest != live_binding.binding_digest
            or source.effect_implementation_ref != live_binding.implementation_ref
            or permission_hash != source_permission_hash
            or record.decision_request_digest != resolution.request_digest
            or record.human_decision_request_ref != request.request_ref
            or record.governed_action_key
            != _pa2_governed_action_key(
                source=source,
                contract=resolution.contract,
                envelope=resolution.envelope,
                tenant_id=record.tenant_id or "",
                run_id=record.run_id or "",
            )
            or source.decided_at > evaluated_at
            or record.recorded_at is None
            or record.recorded_at > evaluated_at
            or record.valid_until is None
            or evaluated_at >= record.valid_until
        ):
            raise HumanDecisionOperationalResolutionError("DS9-DECISION-SOURCE-INVALID")

    def _projection(
        self,
        gate_input: HumanDecisionGateInput,
        *,
        reasons: Sequence[HumanDecisionGateReason],
        decision_request_ref: str | None,
        decision_request_digest: str | None,
        governed_action_key: str | None,
        required_artifact_digests: tuple[str, ...] = (),
        exposure_event_refs: tuple[str, ...] = (),
    ) -> HumanDecisionGateResult:
        reason_tuple = tuple(reasons)
        return HumanDecisionGateResult(
            status=select_human_decision_gate_status(reason_tuple),
            reasons=reason_tuple,
            source_kind=gate_input.source_kind,
            tenant_id=gate_input.tenant_id,
            run_id=gate_input.run_id,
            decision_request_ref=decision_request_ref,
            decision_request_digest=decision_request_digest,
            governed_action_key=governed_action_key,
            required_artifact_digests=required_artifact_digests,
            exposure_event_refs=exposure_event_refs,
            resolved_at=self._now(),
            verifier_epoch=self._verifier_epoch(),
        )

    def _blocked_projection(
        self,
        gate_input: HumanDecisionGateInput,
        code: str,
        message: str,
    ) -> HumanDecisionGateResult:
        return self._projection(
            gate_input,
            reasons=(_reason(code, message, "blocked"),),
            decision_request_ref=gate_input.decision_request_ref,
            decision_request_digest=None,
            governed_action_key=None,
        )

    def _record_input_refs(self, record: HumanDecisionRecord) -> tuple[str, ...]:
        return tuple(
            ref
            for ref in (
                record.source_ref,
                record.basis_ref,
                record.principal_binding_ref,
                record.reviewer_separation_ref,
                record.presentation_contract_ref,
                record.exposure_session_ref,
                *(record.exposure_event_refs or ()),
            )
            if ref is not None and self._sink.has_artifact(ref)
        )

    def _verifier_epoch(self) -> str:
        return self._custody.verifier_epoch or "producer-missing"

    def _now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise TypeError("human-decision clock must return an aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def _agent_action_decision_type() -> type[BaseModel]:
        module = import_module("polisyos.runtime.quality.agent_action_authority")
        decision_type = module.AgentActionAuthorityDecision
        if not isinstance(decision_type, type) or not issubclass(decision_type, BaseModel):
            raise TypeError("agent-action authority decision model is unavailable")
        return decision_type


def _record_write_options() -> artifacts.ArtifactWriteOptions:
    return artifacts.ArtifactWriteOptions(
        kind=HUMAN_DECISION_RECORD_ARTIFACT_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=_RECORD_SCHEMA_NAME,
            version=HUMAN_DECISION_RECORD_MANIFEST_VERSION,
        ),
        producer=artifacts.ProducerInfo(
            component="polisyos.runtime.http.human_decisions",
            version="2.0",
        ),
    )


def _exposure_session_write_options() -> artifacts.ArtifactWriteOptions:
    return artifacts.ArtifactWriteOptions(
        kind=HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name="polisyos.runtime.HumanDecisionExposureSession",
            version=HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
        ),
        producer=artifacts.ProducerInfo(
            component="polisyos.runtime.http.human_decisions",
            version="1.0",
        ),
    )


def _permission_verification(
    permission: ActionPermissionVerification | BoundActionPermissionVerification,
) -> ActionPermissionVerification:
    """Return the exact verified principal proof without constructing authority."""

    from polisyos.runtime.http.authorization import (
        ActionPermissionVerification as ActionPermissionVerificationType,
    )
    from polisyos.runtime.http.authorization import (
        BoundActionPermissionVerification as BoundActionPermissionVerificationType,
    )

    if type(permission) is BoundActionPermissionVerificationType:
        return permission.verification
    if type(permission) is ActionPermissionVerificationType:
        return permission
    raise HumanDecisionOperationalResolutionError("DS9-DECISION-PERMISSION-UNVERIFIED")


def _reason(
    code: str,
    message: str,
    status: HumanDecisionGateStatus,
) -> HumanDecisionGateReason:
    return HumanDecisionGateReason(code=code, message=message, status=status)


def _sha256_ref(value: object) -> str:
    return "sha256:" + sha256(canon.to_canonical_bytes(value, canon.CanonSpec())).hexdigest()


def _human_act_boundary(rule_version_ref: str) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["human_decision_act"],
        may_not_use_for=[
            "policyos_custody_signature",
            "publication_authority",
            "claim_evidence",
        ],
        source_authority="human_governance",
        posture="governed",
        rule_version_refs=[rule_version_ref],
    )


def _exposure_session_boundary(rule_version_ref: str) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["human_decision_exposure_session_custody"],
        may_not_use_for=[
            "evidence_comprehension",
            "human_decision_act",
            "publication_authority",
        ],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[rule_version_ref],
    )


def _custody_boundary(rule_version_ref: str) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["human_decision_record_custody"],
        may_not_use_for=[
            "human_signature",
            "publication_authority",
            "claim_evidence",
        ],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[rule_version_ref],
    )


__all__ = [
    "HumanDecisionOperationalResolutionError",
    "HumanDecisionPersistenceError",
    "HumanDecisionRecordReceipt",
    "HumanDecisionService",
    "HumanDecisionUnavailableError",
]
