"""Content-bound supersession candidates and independently signed owner acts.

Production supplies no appointment. Persisting a candidate never grants authority;
the Claim owner independently verifies a separately signed, scoped appointment and
the event signature before admitting the append-only lifecycle effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.scientist.evidence.claims.audit import _load_append_only_claim_ledger
from polisyos.scientist.evidence.claims.head_index import ClaimLedgerOwnerKey, _read_exact_artifact
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    ClaimLifecycleEvent,
    append_lifecycle_event,
)
from polisyos.scientist.evidence.claims.models import ClaimRecord

ArtifactRef = core_artifacts.ArtifactRef
ArtifactWriteOptions = core_artifacts.ArtifactWriteOptions
Ed25519Signer = core_artifacts.Ed25519Signer
Ed25519Verifier = core_artifacts.Ed25519Verifier
FileSystemCAS = core_artifacts.FileSystemCAS
SchemaInfo = core_artifacts.SchemaInfo
SignatureVerificationStatus = core_artifacts.SignatureVerificationStatus
CanonSpec = core_canon.CanonSpec
from_canonical_bytes = core_canon.from_canonical_bytes
to_canonical_bytes = core_canon.to_canonical_bytes

OWNER_EVENT_KIND = "scientist.claims.supersession_owner_event"
OWNER_EVENT_BRIDGE_KIND = "scientist.claims.owner_event_bridge"
_EVENT_SCHEMA = SchemaInfo(name="polisyos.claim-ledger.supersession-owner-event.v1", version="1")
_SUCCESSOR_KIND = "scientist.claims.supersession_successor_candidate"
_SUCCESSOR_SCHEMA = SchemaInfo(name="polisyos.claim-ledger.supersession-successor.v1", version="1")
_APPOINTMENT_KIND = "scientist.claims.supersession_appointment"
_APPOINTMENT_SCHEMA = SchemaInfo(
    name="polisyos.claim-ledger.supersession-appointment.v1", version="1"
)
_CANON = CanonSpec(forbid_floats=False)


class _EventModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClaimSupersessionAppointment(_EventModel):
    """Externally signed grant for one owner scope and one exact authority purpose."""

    schema_version: Literal["polisyos.claim-ledger.supersession-appointment.v1"] = (
        "polisyos.claim-ledger.supersession-appointment.v1"
    )
    authority_purpose: Literal["claim_supersession"] = "claim_supersession"
    owner_key: ClaimLedgerOwnerKey
    signer_key_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    signer_identity: str = Field(min_length=1)
    valid_from: datetime
    valid_until: datetime

    @model_validator(mode="after")
    def _valid_time_window(self) -> ClaimSupersessionAppointment:
        if (
            self.valid_from.tzinfo is None
            or self.valid_until.tzinfo is None
            or self.valid_until <= self.valid_from
        ):
            raise ValueError("claim_supersession_appointment_time_invalid")
        return self


@dataclass(frozen=True, slots=True)
class ClaimSupersessionAuthority:
    """Explicit trust dependencies; an absent slot never acquires default trust.

    The appointment verifier authenticates the institutional grant. The event
    verifier authenticates its grantee. They must resolve different signing keys.
    Merely constructing this dependency does not make either signature valid.
    """

    appointment_ref: ArtifactRef
    appointment_verifier: Ed25519Verifier
    event_verifier: Ed25519Verifier


class ClaimSupersessionOwnerEvent(_EventModel):
    """Candidate legal/policy replacement, authoritative only after independent verification."""

    schema_version: Literal["polisyos.claim-ledger.supersession-owner-event.v1"] = (
        "polisyos.claim-ledger.supersession-owner-event.v1"
    )
    authority_purpose: Literal["claim_supersession"] = "claim_supersession"
    rule_version: Literal["claim-supersession.v1"] = "claim-supersession.v1"
    candidate_status: Literal["candidate"] = "candidate"
    owner_key: ClaimLedgerOwnerKey
    decision_packet_ref: ArtifactRef
    monitor_event_ref: ArtifactRef
    monitor_event_content_hash: str
    prior_ledger_ref: ArtifactRef
    prior_ledger_content_hash: str
    predecessor_claim_id: str = Field(min_length=1)
    successor_claim_ref: ArtifactRef
    successor_claim_content_hash: str
    successor_claim_id: str = Field(min_length=1)
    legal_evidence_ref: ArtifactRef
    legal_evidence_content_hash: str
    effective_at: datetime

    @model_validator(mode="after")
    def _aware_effective_time(self) -> ClaimSupersessionOwnerEvent:
        if self.effective_at.tzinfo is None:
            raise ValueError("claim_supersession_effective_time_invalid")
        return self


class ClaimSupersessionBridgeStatement(_EventModel):
    """Exact replay witness for one independently verified owner-event append."""

    schema_version: Literal["polisyos.claim-ledger.owner-event-bridge.v1"] = (
        "polisyos.claim-ledger.owner-event-bridge.v1"
    )
    owner_key: ClaimLedgerOwnerKey
    owner_event_ref: ArtifactRef
    owner_event_content_hash: str
    appointment_ref: ArtifactRef
    appointment_content_hash: str
    decision_packet_ref: ArtifactRef
    prior_ledger_ref: ArtifactRef
    prior_ledger_content_hash: str
    next_ledger_ref: ArtifactRef
    next_ledger_content_hash: str


def _persist(
    store: FileSystemCAS, value: BaseModel, *, kind: str, schema: SchemaInfo
) -> ArtifactRef:
    return store.put_bytes(
        to_canonical_bytes(value.model_dump(mode="json"), _CANON),
        ArtifactWriteOptions(kind=kind, media_type="application/json", schema=schema),
    )


def _read(store: FileSystemCAS, ref: ArtifactRef, *, kind: str, schema: SchemaInfo) -> bytes:
    return _read_exact_artifact(
        store=store,
        ref=ref,
        expected_kind=kind,
        expected_media_type="application/json",
        expected_schema=schema,
    )


def persist_claim_supersession_successor(
    *, store: FileSystemCAS, claim: ClaimRecord
) -> ArtifactRef:
    """Persist actual typed replacement content as a candidate, without signing it."""

    checked = ClaimRecord.model_validate(claim.model_dump(mode="json"))
    return _persist(store, checked, kind=_SUCCESSOR_KIND, schema=_SUCCESSOR_SCHEMA)


def persist_claim_supersession_appointment(
    *,
    store: FileSystemCAS,
    appointment: ClaimSupersessionAppointment,
    signer: Ed25519Signer,
    signer_identity: str,
) -> ArtifactRef:
    """Persist an explicitly supplied institution's signed grant; never create a default grant."""

    checked = ClaimSupersessionAppointment.model_validate(appointment.model_dump(mode="json"))
    ref = _persist(store, checked, kind=_APPOINTMENT_KIND, schema=_APPOINTMENT_SCHEMA)
    store.sign_artifact(ref.artifact_id, signer, signer_identity=signer_identity)
    return ref


def read_claim_supersession_candidate(
    *, store: FileSystemCAS, owner_event_ref: ArtifactRef
) -> ClaimSupersessionOwnerEvent:
    """Read exact candidate vocabulary without conferring owner authority."""

    raw = _read(store, owner_event_ref, kind=OWNER_EVENT_KIND, schema=_EVENT_SCHEMA)
    event = ClaimSupersessionOwnerEvent.model_validate(from_canonical_bytes(raw))
    if to_canonical_bytes(event.model_dump(mode="json"), _CANON) != raw:
        raise ValueError("claim_supersession_event_noncanonical")
    return event


def produce_claim_supersession_owner_event(
    *,
    store: FileSystemCAS,
    owner_key: ClaimLedgerOwnerKey,
    monitor_event_ref: ArtifactRef,
    prior_ledger_ref: ArtifactRef,
    predecessor_claim_id: str,
    successor_claim_ref: ArtifactRef,
    effective_at: datetime,
    signer: Ed25519Signer | None = None,
    signer_identity: str | None = None,
) -> ArtifactRef:
    """Emit a persisted replacement candidate from resolved content, optionally externally signed.

    Signing capability must be explicitly supplied. An unsigned result remains a
    usable candidate but cannot advance a Claim head.
    """

    from polisyos.scientist.governance.continuous.monitors import (
        LegalChangePerturbation,
        resolve_governance_monitor_event,
    )

    monitor = resolve_governance_monitor_event(store, monitor_event_ref).event
    if not isinstance(monitor.perturbation, LegalChangePerturbation):
        raise ValueError("claim_supersession_legal_basis_missing")
    successor = ClaimRecord.model_validate(
        from_canonical_bytes(
            _read(store, successor_claim_ref, kind=_SUCCESSOR_KIND, schema=_SUCCESSOR_SCHEMA)
        )
    )
    legal_ref = monitor.perturbation.legal_change_evidence_ref
    if not store.verify(legal_ref.artifact_id).ok:
        raise ValueError("claim_supersession_legal_basis_unresolved")
    event = ClaimSupersessionOwnerEvent(
        owner_key=owner_key,
        decision_packet_ref=monitor.decision_packet_ref,
        monitor_event_ref=monitor_event_ref,
        monitor_event_content_hash=str(monitor_event_ref.artifact_id),
        prior_ledger_ref=prior_ledger_ref,
        prior_ledger_content_hash=str(prior_ledger_ref.artifact_id),
        predecessor_claim_id=predecessor_claim_id,
        successor_claim_ref=successor_claim_ref,
        successor_claim_content_hash=str(successor_claim_ref.artifact_id),
        successor_claim_id=successor.claim_id,
        legal_evidence_ref=legal_ref,
        legal_evidence_content_hash=str(legal_ref.artifact_id),
        effective_at=effective_at,
    )
    _validate_candidate_content(store=store, event=event)
    ref = _persist(store, event, kind=OWNER_EVENT_KIND, schema=_EVENT_SCHEMA)
    if signer is not None:
        if not signer_identity:
            raise ValueError("claim_supersession_signer_identity_missing")
        store.sign_artifact(ref.artifact_id, signer, signer_identity=signer_identity)
    if read_claim_supersession_candidate(store=store, owner_event_ref=ref) != event:
        raise ValueError("claim_supersession_event_readback_mismatch")
    return ref


def _validate_candidate_content(
    *, store: FileSystemCAS, event: ClaimSupersessionOwnerEvent
) -> ClaimRecord:
    from polisyos.scientist.governance.continuous.monitors import (
        LegalChangePerturbation,
        resolve_governance_monitor_event,
    )

    monitor = resolve_governance_monitor_event(store, event.monitor_event_ref).event
    ledger = _load_append_only_claim_ledger(store, event.prior_ledger_ref)
    successor = ClaimRecord.model_validate(
        from_canonical_bytes(
            _read(store, event.successor_claim_ref, kind=_SUCCESSOR_KIND, schema=_SUCCESSOR_SCHEMA)
        )
    )
    prior_ids = {claim.claim_id for claim in ledger.current_claims}
    legal_manifest = store.get_manifest(event.legal_evidence_ref.artifact_id)
    if (
        not isinstance(monitor.perturbation, LegalChangePerturbation)
        or monitor.perturbation.legal_change_evidence_ref != event.legal_evidence_ref
        or monitor.decision_packet_ref != event.decision_packet_ref
        or event.predecessor_claim_id not in monitor.affected_claim_ids
        or event.predecessor_claim_id not in prior_ids
        or successor.claim_id in prior_ids
        or successor.claim_id != event.successor_claim_id
        or successor.run_id != ledger.run_id
        or event.effective_at < monitor.occurred_at
        or (ledger.events and event.effective_at < ledger.events[-1].occurred_at)
        or event.monitor_event_content_hash != str(event.monitor_event_ref.artifact_id)
        or event.prior_ledger_content_hash != str(event.prior_ledger_ref.artifact_id)
        or event.successor_claim_content_hash != str(event.successor_claim_ref.artifact_id)
        or event.legal_evidence_content_hash != str(event.legal_evidence_ref.artifact_id)
        or not store.verify(event.legal_evidence_ref.artifact_id).ok
        or legal_manifest.kind != event.legal_evidence_ref.kind
        or legal_manifest.media_type != event.legal_evidence_ref.media_type
    ):
        raise ValueError("claim_supersession_candidate_binding_rejected")
    return successor


def resolve_claim_supersession_owner_event(
    *,
    store: FileSystemCAS,
    owner_event_ref: ArtifactRef,
    authority: ClaimSupersessionAuthority | None,
    expected_owner_key: ClaimLedgerOwnerKey,
) -> ClaimSupersessionOwnerEvent:
    """Verify actual appointment and event signatures, then recompute all source bindings."""

    if authority is None:
        raise ValueError("claim_owner_event_authority_unappointed")
    event = read_claim_supersession_candidate(store=store, owner_event_ref=owner_event_ref)
    appointment = ClaimSupersessionAppointment.model_validate(
        from_canonical_bytes(
            _read(
                store, authority.appointment_ref, kind=_APPOINTMENT_KIND, schema=_APPOINTMENT_SCHEMA
            )
        )
    )
    grant_signature = store.verify_signature(
        authority.appointment_ref.artifact_id, authority.appointment_verifier, strict_identity=True
    )
    event_signature = store.verify_signature(
        owner_event_ref.artifact_id, authority.event_verifier, strict_identity=True
    )
    now = datetime.now(UTC)
    if (
        grant_signature.status is not SignatureVerificationStatus.VALID
        or event_signature.status is not SignatureVerificationStatus.VALID
        or grant_signature.key_id == event_signature.key_id
        or event_signature.key_id != appointment.signer_key_id
        or event_signature.signer_identity != appointment.signer_identity
        or event.owner_key != expected_owner_key
        or appointment.owner_key != expected_owner_key
        or not appointment.valid_from <= event.effective_at <= now < appointment.valid_until
    ):
        raise ValueError("claim_supersession_signature_or_scope_rejected")
    _validate_candidate_content(store=store, event=event)
    return event


def apply_claim_supersession_owner_event(
    *,
    store: FileSystemCAS,
    ledger: AppendOnlyClaimLedger,
    event: ClaimSupersessionOwnerEvent,
    owner_event_ref: ArtifactRef,
) -> AppendOnlyClaimLedger:
    """Recompute the exact append while retaining the predecessor claim and its bytes."""

    _validate_candidate_content(store=store, event=event)
    if ledger != _load_append_only_claim_ledger(store, event.prior_ledger_ref):
        raise ValueError("claim_supersession_prior_ledger_mismatch")
    # This act admits the relation only. Successor evidence, readiness and
    # publication status require their own Claim issuance authority.
    return append_lifecycle_event(
        ledger,
        ClaimLifecycleEvent(
            event_id="claim_owner_event_" + owner_event_ref.artifact_id.hex,
            claim_id=event.predecessor_claim_id,
            run_id=ledger.run_id,
            action=ClaimLifecycleAction.SUPERSEDED,
            occurred_at=event.effective_at,
            actor_id="claim_supersession_owner",
            reason="Independently verified owner supersession act.",
            previous_claim_ref=event.prior_ledger_ref,
            next_claim_ref=event.successor_claim_ref,
            evidence_refs=[event.monitor_event_ref, event.legal_evidence_ref, owner_event_ref],
            metadata={
                "superseded_by_claim_id": event.successor_claim_id,
                "owner_event_ref": owner_event_ref.model_dump(mode="json"),
                "rule_version": event.rule_version,
                "predicate_class": "independently_reconciled",
            },
        ),
    )


def find_claim_supersession_candidates(
    *, store: FileSystemCAS, monitor_event_ref: ArtifactRef
) -> tuple[tuple[ArtifactRef, ClaimSupersessionOwnerEvent], ...]:
    """Enumerate actual same-store event artifacts for this exact monitor input."""

    rows = []
    for artifact_id in store.iter_artifact_ids():
        manifest = store.get_manifest(artifact_id)
        if manifest.kind != OWNER_EVENT_KIND:
            continue
        ref = ArtifactRef(
            artifact_id=artifact_id, kind=manifest.kind, media_type=manifest.media_type
        )
        event = read_claim_supersession_candidate(store=store, owner_event_ref=ref)
        if event.monitor_event_ref == monitor_event_ref:
            rows.append((ref, event))
    return tuple(sorted(rows, key=lambda row: str(row[0].artifact_id)))
