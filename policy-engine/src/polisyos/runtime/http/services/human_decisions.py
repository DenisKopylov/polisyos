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
from datetime import UTC, datetime
from hashlib import sha256
from importlib import import_module
from math import isfinite
from typing import TYPE_CHECKING, Protocol, TypeVar, cast

from pydantic import BaseModel

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
    REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
    REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
    HumanDecisionCreateCommand,
    HumanDecisionExposureAuditEvent,
    HumanDecisionExposureSession,
    HumanDecisionGateInput,
    HumanDecisionGateReason,
    HumanDecisionGateResult,
    HumanDecisionGateStatus,
    HumanDecisionGatewayAdapterInput,
    HumanDecisionPA2GateInput,
    HumanDecisionPA2GatewayAdapterInput,
    HumanDecisionPresentationContract,
    HumanDecisionPrincipalBinding,
    HumanDecisionProductionGateInput,
    HumanDecisionResolverPolicy,
    HumanDecisionWriteContext,
    ReviewerSeparationCredential,
    select_human_decision_gate_status,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    HUMAN_DECISION_RECORD_V2,
    DelegatedActionEnvelope,
    DelegationContract,
    FiveRightsCheck,
    HumanDecisionCanonicalActor,
    HumanDecisionPredicateReceipt,
    HumanDecisionRecord,
    HumanDecisionRecordPredicate,
    HumanDecisionRecordPredicateProvenance,
    HumanDecisionRequest,
    ResponsibilityIntegrityCheck,
)

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from pathlib import Path

    from polisyos.runtime.http.authorization import BoundActionPermissionVerification
    from polisyos.runtime.http.security import RuntimeHumanDecisionCustody

_TModel = TypeVar("_TModel", bound=BaseModel)
_RECORD_SCHEMA_NAME = "polisyos.runtime.HumanDecisionRecord"
_SOURCE_SCHEMA_NAME = "polisyos.runtime.AgentActionAuthorityDecision"
_SOURCE_ARTIFACT_KIND = "runtime_quality.agent_action_authority_decision"
_SOURCE_SCHEMA_VERSION = "policyos.runtime.agent_action_authority.v1"
_CONTRACT_ARTIFACT_KIND = "runtime_quality.agent_action_delegation_contract"
_CONTRACT_SCHEMA_NAME = "polisyos.runtime.DelegationContract"
_CONTRACT_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s7_delegation.v2"
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
    request: HumanDecisionRequest | None = None
    contract: DelegationContract | None = None
    principal: HumanDecisionPrincipalBinding | None = None
    separation: ReviewerSeparationCredential | None = None
    presentation: HumanDecisionPresentationContract | None = None
    exposure_session: HumanDecisionExposureSession | None = None
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
        (check.predicate, check.satisfied, check.provenance)
        for check in source.predicate_checks
    )
    provenance_required = {
        source.operation_content_hash,
        source.invocation_content_hash,
        source.intent_content_hash,
        *(
            (source.contract_ref,)
            if source.contract_ref is not None
            else ()
        ),
        *(
            (source.bound_resource_digest,)
            if source.bound_resource_digest is not None
            else ()
        ),
        *(
            (source.effect_binding_digest,)
            if source.effect_binding_digest is not None
            else ()
        ),
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
        or request.s6_mandate_firewall_disposition
        != contract.s6_mandate_firewall_disposition
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
        or request.required_role not in principal.decision_roles
        or required_reviewer_permission not in principal.permissions
        or principal.verifier_epoch != verifier_epoch
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
    source: AgentActionAuthorityDecision,
    request: HumanDecisionRequest,
    principal: HumanDecisionPrincipalBinding,
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
    if (
        presentation.decision_request_ref != request.request_ref
        or presentation.decision_request_digest != request_digest
        or presentation.tenant_id != principal.tenant_id
        or presentation.run_id != principal.run_id
        or presentation.verifier_epoch != principal.verifier_epoch
        or presentation.valid_from > now
        or now >= presentation.valid_until
    ):
        issues.add("presentation")
    if source.contract_ref is None or source.contract_ref not in presentation_required:
        issues.add("mandate")
    if any(ref not in presentation_required for ref in request.disconfirming_evidence_refs):
        issues.add("evidence")
    if (
        session.actor_ref != principal.actor_ref
        or session.tenant_id != principal.tenant_id
        or session.run_id != principal.run_id
        or session.verifier_epoch != principal.verifier_epoch
        or session.decision_request_ref != request.request_ref
        or session.decision_request_digest != request_digest
        or session.basis_digest != source.contract_ref
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
        or session.valid_from > now
        or now >= session.valid_until
    ):
        issues.add("session")

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
            and isfinite(event.timestamp)
        )
        if event_valid:
            try:
                event_time = datetime.fromtimestamp(event.timestamp, tz=UTC)
            except (OverflowError, OSError, ValueError):
                event_valid = False
            else:
                event_valid = (
                    session.valid_from <= event_time < session.valid_until
                    and event_time <= now
                )
        if event_valid:
            valid_event_artifacts.append(event.artifact_id)
        else:
            issues.add("session")
    covered = Counter(valid_event_artifacts)
    expected = Counter(session_required)
    if covered != expected:
        issues.add("session")
    mandate_ref = source.contract_ref
    if mandate_ref is None or covered[mandate_ref] < Counter(presentation_required)[mandate_ref]:
        issues.add("mandate")
    if any(
        covered[ref] < Counter(presentation_required)[ref]
        for ref in request.disconfirming_evidence_refs
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

    def __init__(
        self,
        *,
        authority_sink: HumanDecisionAuthoritySinkProtocol,
        custody: RuntimeHumanDecisionCustody,
        resolver_policy: HumanDecisionResolverPolicy,
        access_audit_path: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        control_lifecycle = import_module(
            "polisyos.runtime.http.services.control.run_lifecycle"
        )
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
        bound_permission: BoundActionPermissionVerification | None,
    ) -> HumanDecisionGateResult:
        """Resolve every signed input and return a non-authoritative projection."""

        return self._resolve_gate(gate_input, bound_permission=bound_permission).projection

    def create_record(
        self,
        command: HumanDecisionCreateCommand,
        *,
        bound_permission: BoundActionPermissionVerification,
        write_context: HumanDecisionWriteContext,
    ) -> HumanDecisionRecordReceipt:
        """Persist, sign, reconcile, and commit one exact V2 decision record."""

        resolved = self._resolve_gate(command.gate_input, bound_permission=bound_permission)
        if resolved.projection.status != "available":
            raise HumanDecisionUnavailableError(resolved.projection)
        if not self._custody.available:
            raise HumanDecisionUnavailableError(resolved.projection)
        source = resolved.source
        request = resolved.request
        contract = resolved.contract
        principal = resolved.principal
        separation = resolved.separation
        presentation = resolved.presentation
        session = resolved.exposure_session
        if any(
            value is None
            for value in (source, request, contract, principal, separation, presentation, session)
        ):
            raise HumanDecisionPersistenceError("available gate lost resolved inputs")
        source = cast("AgentActionAuthorityDecision", source)
        request = cast("HumanDecisionRequest", request)
        contract = cast("DelegationContract", contract)
        principal = cast("HumanDecisionPrincipalBinding", principal)
        separation = cast("ReviewerSeparationCredential", separation)
        presentation = cast("HumanDecisionPresentationContract", presentation)
        session = cast("HumanDecisionExposureSession", session)
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
            envelope = next(
                (
                    row
                    for row in contract.action_envelopes
                    if row.envelope_id == source.envelope_id
                ),
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
            governed_action_key = resolved.projection.governed_action_key or ""
        if governed_action_key != resolved.projection.governed_action_key:
            raise HumanDecisionPersistenceError(
                "human-decision governed action key changed after gate resolution"
            )
        binding_sha256 = _sha256_ref(
            {
                "tenant_id": command.gate_input.tenant_id,
                "run_id": command.gate_input.run_id,
                "source_ref": command.gate_input.source_ref,
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
            raise HumanDecisionPersistenceError(
                "human-decision v2 record has no validity boundary"
            )
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
                        raise ValueError(
                            "human-decision custody signature did not bind the record"
                        )
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
                        durable_event_id=(
                            durable_event_id if has_reconciled_orphan else None
                        ),
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
            raise HumanDecisionPersistenceError(
                "human-decision record custody did not complete"
            )
        return receipt

    def read_record(
        self,
        record_ref: str,
        *,
        tenant_id: str,
        run_id: str,
    ) -> HumanDecisionRecord:
        """Read historical or current content only after exact custody verification."""

        resolved = self._read_signed_model(
            record_ref,
            expected_kind=HUMAN_DECISION_RECORD_ARTIFACT_KIND,
            expected_schema_name=_RECORD_SCHEMA_NAME,
            expected_schema_version=HUMAN_DECISION_RECORD_MANIFEST_VERSION,
            model_type=HumanDecisionRecord,
            expected_tenant_id=tenant_id,
            expected_run_id=run_id,
        )
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
        bound_permission: BoundActionPermissionVerification | None,
    ) -> _ResolvedGate:
        if isinstance(gate_input, HumanDecisionProductionGateInput):
            return self._resolve_production_gate(gate_input)
        return self._resolve_pa2_gate(gate_input, bound_permission=bound_permission)

    def _resolve_production_gate(
        self,
        gate_input: HumanDecisionProductionGateInput,
    ) -> _ResolvedGate:
        reasons: list[HumanDecisionGateReason] = []
        if gate_input.production_packet_ref is None and gate_input.source_ref is None:
            reasons.append(
                _reason(
                    "DS9-DECISION-PRODUCER-MISSING",
                    "No verified production approval packet producer is installed.",
                    "producer_missing",
                )
            )
        else:
            supplied_ref = gate_input.production_packet_ref or gate_input.source_ref
            if supplied_ref is not None and not self._sink.has_artifact(supplied_ref):
                reasons.append(
                    _reason(
                        "DS9-DECISION-ARTIFACT-MISSING",
                        "The supplied production approval artifact does not resolve.",
                        "artifact_missing",
                    )
                )
            else:
                reasons.append(
                    _reason(
                        "DS9-DECISION-PRODUCER-MISSING",
                        "Production approval intake is not installed until C03.",
                        "producer_missing",
                    )
                )
        return _ResolvedGate(
            projection=self._projection(
                gate_input,
                reasons=reasons,
                decision_request_ref=gate_input.decision_request_ref,
                decision_request_digest=None,
                governed_action_key=None,
            )
        )

    def _resolve_pa2_gate(
        self,
        gate_input: HumanDecisionPA2GateInput,
        *,
        bound_permission: BoundActionPermissionVerification | None,
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
            source = cast(
                "AgentActionAuthorityDecision", cast("object", resolved_source.model)
            )
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
                contract = cast("DelegationContract", resolved_contract.model)
                if (
                    resolved_contract.signer_identity != contract.mandate_owner_ref
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
                now=now,
                reasons=reasons,
            )
        elif bound_permission is None:
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
                or separation.valid_from > now
                or now >= separation.valid_until
            ):
                reasons.append(
                    _reason(
                        "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING",
                        "Reviewer independence or change authority is not established.",
                        "blocked",
                    )
                )
        if all(
            value is not None
            for value in (source, request, contract, principal, separation)
        ):
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
            if packet_issues & {"separation", "separation_current"}:
                reasons.append(
                    _reason(
                        "DS9-REVIEWER-INDEPENDENCE-CHANGE-AUTHORITY-MISSING",
                        "Reviewer separation does not name the exact reviewed actor.",
                        "blocked",
                    )
                )
        if (
            session is not None
            and gate_input.exposure_session_ref is not None
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
                    source=cast("AgentActionAuthorityDecision", source),
                    request=request,
                    principal=principal,
                    presentation=cast("HumanDecisionPresentationContract", presentation),
                    presentation_ref=cast("str", gate_input.presentation_contract_ref),
                    session=session,
                    session_ref=gate_input.exposure_session_ref,
                    events=events,
                    now=now,
                )
                if source is not None
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

        request_digest = (
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
            decision_request_digest=request_digest,
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
            request=request,
            contract=contract,
            principal=principal,
            separation=separation,
            presentation=presentation,
            exposure_session=session,
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
        if producer is None:
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-PRODUCER-MISSING",
                    "No exact deployment producer trust row exists for this artifact.",
                    "producer_missing",
                )
            )
        verification = self._sink.verify_artifact_signature(
            ref,
            verifier,
            strict_identity=True,
        )
        signer_identity = verification.signer_identity
        key_id = verification.key_id
        if (
            not verification.ok
            or signer_identity is None
            or signer_identity != producer.signer_identity
            or key_id is None
        ):
            raise _ResolutionIssueError(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "Artifact signature/key/identity is not trusted by deployment policy.",
                    "invalid_source",
                )
            )
        report = self._sink.reconcile_authority_artifact(
            ref,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=None,
            expected_run_id=expected_run_id,
            expected_job_id=None,
        )
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

    def _evaluate_principal(
        self,
        gate_input: HumanDecisionPA2GateInput,
        *,
        request: HumanDecisionRequest,
        principal: HumanDecisionPrincipalBinding,
        bound_permission: BoundActionPermissionVerification | None,
        now: datetime,
        reasons: list[HumanDecisionGateReason],
    ) -> None:
        if (
            principal.tenant_id != gate_input.tenant_id
            or principal.run_id != gate_input.run_id
            or principal.principal_audience != self._resolver_policy.principal_audience
            or principal.verifier_epoch != self._verifier_epoch()
            or principal.valid_from > now
            or now >= principal.valid_until
        ):
            reasons.append(
                _reason(
                    "DS9-DECISION-SOURCE-INVALID",
                    "The signed principal binding is stale or context-mismatched.",
                    "invalid_source",
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
        if bound_permission is None:
            reasons.append(
                _reason(
                    "DS9-DECISION-PERMISSION-UNVERIFIED",
                    "No bound action-permission proof reached the gate.",
                    "invalid_source",
                )
            )
            return
        verification = bound_permission.verification
        bound_resource = bound_permission.bound_resource
        granted = tuple(item.value for item in verification.granted_permissions)
        required = verification.requirement.permission.value
        if (
            verification.subject != principal.principal_subject
            or verification.tenant_id != gate_input.tenant_id
            or required != permission
            or permission not in granted
            or getattr(bound_resource, "tenant_id", None) != gate_input.tenant_id
            or not str(getattr(bound_resource, "resource_kind", "")).startswith(
                "runtime.run.human_decision"
            )
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
            ],
            ...,
        ] = (
            ("identity_permission", "recomputed", (gate_input.principal_binding_ref,)),
            ("role_mandate_or_basis", "independently_reconciled", (source.contract_ref,)),
            ("operation_accountability", "recomputed", (gate_input.source_ref,)),
            ("currentness", "recomputed", (gate_input.exposure_session_ref,)),
            ("right_decision_time", "recomputed", (request.request_ref,)),
            (
                "reviewer_independence_change",
                "independently_reconciled",
                (gate_input.reviewer_separation_ref, separation.credential_ref),
            ),
            ("evidence_exposure", "independently_reconciled", evidence),
            (
                "presentation_format_channel",
                "independently_reconciled",
                (gate_input.presentation_contract_ref, presentation.contract_ref),
            ),
            ("source_producer_trust", "independently_reconciled", (gate_input.source_ref,)),
        )
        return tuple(
            HumanDecisionPredicateReceipt(
                predicate=predicate,
                satisfied=True,
                provenance=provenance,
                evidence_refs=tuple(ref for ref in refs if ref is not None),
                reason=f"{predicate} passed against exact signed inputs.",
            )
            for predicate, provenance, refs in rows
        )

    def _build_record(
        self,
        *,
        command: HumanDecisionCreateCommand,
        resolved: _ResolvedGate,
        source: AgentActionAuthorityDecision,
        request: HumanDecisionRequest,
        contract: DelegationContract,
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
            mandate_source_refs=[contract.contract_ref, source.contract_ref or ""],
            five_rights_check=FiveRightsCheck(
                right_decision=True,
                right_person=True,
                right_information=True,
                right_format_channel=True,
                right_time=True,
            ),
            responsibility_integrity=ResponsibilityIntegrityCheck(
                status="pass",
                pattern_ids=["P26", "P05", "P37"],
                reason="All nine gate predicates were recomputed or independently reconciled.",
                missing_requirements=[],
                rule_version_ref=request.rule_version_ref,
            ),
            authority_boundary=_human_act_boundary(request.rule_version_ref),
            provenance_refs=[
                cast("str", command.gate_input.source_ref),
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
            source_ref=command.gate_input.source_ref,
            source_digest=command.gate_input.source_ref,
            decision_request_digest=request_digest,
            basis_ref=source.contract_ref,
            basis_digest=source.contract_ref,
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
            source=source,
            request=request,
            principal=principal,
            presentation=presentation,
            presentation_ref=record.presentation_contract_ref,
            session=session,
            session_ref=record.exposure_session_ref,
            events=events,
            now=now,
        )
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
            raise HumanDecisionOperationalResolutionError(
                "DS9-DECISION-SOURCE-INVALID"
            ) from None
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
            or envelope_digest
            != _sha256_ref(resolution.envelope.model_dump(mode="json"))
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


def _reason(
    code: str,
    message: str,
    status: HumanDecisionGateStatus,
) -> HumanDecisionGateReason:
    return HumanDecisionGateReason(code=code, message=message, status=status)


def _sha256_ref(value: object) -> str:
    return "sha256:" + sha256(
        canon.to_canonical_bytes(value, canon.CanonSpec())
    ).hexdigest()


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
