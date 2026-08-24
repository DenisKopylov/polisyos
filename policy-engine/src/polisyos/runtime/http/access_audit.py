"""Append-only audit logging for runtime reads and authorization decisions."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from functools import partial
from hashlib import sha256
from importlib import import_module
from typing import TYPE_CHECKING, Any, Literal, TextIO, cast

from anyio import to_thread
from pydantic import BaseModel, ConfigDict

from polisyos.common.serialization import fast_json_dumps
from polisyos.core import artifacts, canon
from polisyos.runtime.http.services.human_decision_contracts import (
    HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
    HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
    HumanDecisionExposureAuditEvent,
)
from polisyos.runtime.quality.authority import GovernanceMetadata

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from contextlib import AbstractContextManager
    from pathlib import Path
    from typing import Protocol

    from fastapi import Request

    class _CasRef(Protocol):
        @property
        def artifact_id(self) -> object: ...

    class _AuthorityWriteResult(Protocol):
        @property
        def cas_ref(self) -> _CasRef: ...

        @property
        def payload_sha256(self) -> str: ...

    class _ExposureSignatureVerification(Protocol):
        status: artifacts.SignatureVerificationStatus
        signer_identity: str | None
        key_id: str | None

    class _ExposureArtifactStore(Protocol):
        def has(self, artifact_ref: str) -> bool: ...

        def get_signature(
            self,
            artifact_ref: artifacts.ArtifactID,
        ) -> object | None: ...

        def sign_artifact(
            self,
            artifact_ref: artifacts.ArtifactID,
            signer: artifacts.Ed25519Signer,
            *,
            signer_identity: str,
        ) -> object: ...

        def verify_signature(
            self,
            artifact_ref: artifacts.ArtifactID,
            verifier: artifacts.Ed25519Verifier,
            *,
            strict_identity: bool,
        ) -> artifacts.SignatureVerificationResult: ...

    class _ExposureAuthoritySink(Protocol):
        def has_artifact(self, artifact_ref: str) -> bool: ...

        def write_authority_artifact(
            self,
            payload: object,
            options: artifacts.ArtifactWriteOptions,
            *,
            authority_fields: Mapping[str, object],
        ) -> _AuthorityWriteResult: ...

        def get_artifact_signature(self, artifact_ref: str) -> object | None: ...

        def sign_artifact(
            self,
            artifact_ref: str,
            signer: artifacts.Ed25519Signer,
            *,
            signer_identity: str,
        ) -> object: ...

        def verify_artifact_signature(
            self,
            artifact_ref: str,
            verifier: object,
            *,
            strict_identity: bool,
        ) -> _ExposureSignatureVerification: ...


logger = logging.getLogger("polisyos.runtime.authorization_audit")

try:  # pragma: no cover - platform import; production and CI are POSIX
    import fcntl
except ModuleNotFoundError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


_AUDIT_LOCKS_GUARD = threading.Lock()
_AUDIT_LOCKS: dict[str, threading.RLock] = {}
_EXPOSURE_EVENT_TYPE = "runtime.human_decision.exposure"
_EXPOSURE_RESERVATION_EVENT_TYPE = "runtime.human_decision.exposure_delivery_reserved"


class RuntimeAuthorizationAuditError(RuntimeError):
    """Signal that a mutation decision could not reach the authority audit."""


class HumanDecisionExposureReplayError(RuntimeAuthorizationAuditError):
    """Signal that a delivery slot is already reserved or completed."""


class RuntimeAuthorizationOutcome(StrEnum):
    """Closed terminal authorization outcomes."""

    ALLOW = "allow"
    DENY = "deny"


class RuntimeAuthorizationAuditEvent(BaseModel):
    """Strict terminal event appended to the existing runtime access audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.authorization_audit.v1"] = (
        "polisyos.runtime.authorization_audit.v1"
    )
    event_type: Literal["runtime.authorization.decision"] = "runtime.authorization.decision"
    timestamp: float
    request_id: str
    outcome: RuntimeAuthorizationOutcome
    denial_reason: str
    method: str
    route_path: str
    permission: str
    resource_id: str
    resource_digest: str
    resource_kind: str
    binding_authority: str
    step_up_class: str
    step_up_outcome: Literal["not_required", "verified", "denied", "unresolved"]
    subject: str
    tenant_id: str
    principal_type: str
    opa_policy: str
    opa_reasons: list[str]


class HumanDecisionExposureDeliveryReservation(BaseModel):
    """Durable, signed-quota-bound claim on one exact evidence delivery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.human_decision_exposure_delivery_reservation.v1"] = (
        "polisyos.runtime.human_decision_exposure_delivery_reservation.v1"
    )
    event_type: Literal["runtime.human_decision.exposure_delivery_reserved"] = (
        "runtime.human_decision.exposure_delivery_reserved"
    )
    timestamp: float
    reservation_id: str
    event_id: str
    event_receipt_ref: str
    tenant_id: str
    actor_ref: str
    run_id: str
    request_ref: str
    request_digest: str
    basis_digest: str
    session_ref: str
    artifact_id: str
    expected_content_digest: str
    expected_bytes: int
    allowed_multiplicity: int
    verifier_epoch: str


class RuntimeDataAccessAuditTrail:
    """Persist data-access audit events for compliance review."""

    def __init__(self, *, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        key = str(self._path.resolve())
        with _AUDIT_LOCKS_GUARD:
            self._lock = _AUDIT_LOCKS.setdefault(key, threading.RLock())

    def append(self, entry: dict[str, Any]) -> None:
        if entry.get("event_type") in {
            _EXPOSURE_EVENT_TYPE,
            _EXPOSURE_RESERVATION_EVENT_TYPE,
        }:
            raise RuntimeAuthorizationAuditError(
                "Exposure delivery state requires the dedicated reserved writer"
            )
        self._append_line(entry)

    def append_completed_exposure(
        self,
        event: HumanDecisionExposureAuditEvent,
        *,
        allowed_multiplicity: int = 1,
    ) -> None:
        """Reject raw completion; verified reserved completion is module-private."""
        del event, allowed_multiplicity
        raise RuntimeAuthorizationAuditError(
            "Completed exposure events require a verified delivery reservation"
        )

    def _reserve_exposure_delivery(
        self,
        prepared: PreparedHumanDecisionExposureEvent,
    ) -> ReservedHumanDecisionExposureEvent:
        """Reserve one durable delivery slot before any response bytes leave."""
        _validate_prepared_exposure(prepared)
        event = prepared.completed_event
        reservation_id = event.event_id
        with self._locked_handle() as handle:
            handle.seek(0)
            completed = 0
            reserved = 0
            for raw_line in handle:
                parsed = _parse_authority_scan_line(raw_line)
                event_type = parsed.get("event_type")
                if event_type == _EXPOSURE_RESERVATION_EVENT_TYPE:
                    try:
                        prior_reservation = HumanDecisionExposureDeliveryReservation.model_validate(
                            parsed
                        )
                    except ValueError as exc:
                        raise RuntimeAuthorizationAuditError(
                            "Existing human-decision delivery reservation is malformed"
                        ) from exc
                    if (
                        prior_reservation.reservation_id == reservation_id
                        or prior_reservation.event_id == event.event_id
                        or prior_reservation.event_receipt_ref == prepared.receipt_ref
                    ):
                        raise HumanDecisionExposureReplayError(
                            "Human-decision exposure event is already reserved"
                        )
                    if (
                        prior_reservation.session_ref == event.session_ref
                        and prior_reservation.artifact_id == event.artifact_id
                    ):
                        reserved += 1
                    continue
                if (
                    parsed.get("session_ref") != event.session_ref
                    or parsed.get("artifact_id") != event.artifact_id
                ):
                    continue
                if event_type == _EXPOSURE_EVENT_TYPE:
                    completed += 1
            # A non-completed reservation remains consumed: after a transport
            # exception the server cannot prove that zero bytes reached the
            # client. Retrying therefore requires a newly signed session.
            if max(completed, reserved) >= event.allowed_multiplicity:
                raise HumanDecisionExposureReplayError(
                    "Human-decision exposure replay exceeds the signed multiplicity"
                )
            reservation = HumanDecisionExposureDeliveryReservation(
                timestamp=time.time(),
                reservation_id=reservation_id,
                event_id=event.event_id,
                event_receipt_ref=prepared.receipt_ref,
                tenant_id=event.tenant_id,
                actor_ref=event.actor_ref,
                run_id=event.run_id,
                request_ref=event.request_ref,
                request_digest=event.request_digest,
                basis_digest=event.basis_digest,
                session_ref=event.session_ref,
                artifact_id=event.artifact_id,
                expected_content_digest=event.content_digest,
                expected_bytes=event.delivered_bytes,
                allowed_multiplicity=event.allowed_multiplicity,
                verifier_epoch=event.verifier_epoch,
            )
            self._write_locked(handle, reservation.model_dump(mode="json"))
        return ReservedHumanDecisionExposureEvent(
            prepared=prepared,
            reservation_id=reservation_id,
        )

    def _append_reserved_exposure(
        self,
        reserved: ReservedHumanDecisionExposureEvent,
    ) -> None:
        """Append one signature-verified completion against its durable slot."""
        if type(reserved) is not ReservedHumanDecisionExposureEvent:
            raise TypeError("reserved must be a ReservedHumanDecisionExposureEvent")
        _validate_prepared_exposure(reserved.prepared)
        event = reserved.prepared.completed_event
        if reserved.reservation_id != event.event_id:
            raise RuntimeAuthorizationAuditError(
                "Human-decision exposure reservation identity is not content-bound"
            )
        with self._locked_handle() as handle:
            handle.seek(0)
            reservation: HumanDecisionExposureDeliveryReservation | None = None
            completed = 0
            for raw_line in handle:
                parsed = _parse_authority_scan_line(raw_line)
                event_type = parsed.get("event_type")
                if event_type == _EXPOSURE_RESERVATION_EVENT_TYPE:
                    try:
                        candidate = HumanDecisionExposureDeliveryReservation.model_validate(parsed)
                    except ValueError as exc:
                        raise RuntimeAuthorizationAuditError(
                            "Existing human-decision delivery reservation is malformed"
                        ) from exc
                    if candidate.reservation_id == reserved.reservation_id:
                        if reservation is not None:
                            raise RuntimeAuthorizationAuditError(
                                "Human-decision exposure reservation is duplicated"
                            )
                        reservation = candidate
                    continue
                if event_type != _EXPOSURE_EVENT_TYPE:
                    continue
                if (
                    parsed.get("event_id") == event.event_id
                    or parsed.get("event_receipt_ref") == reserved.prepared.receipt_ref
                ):
                    raise HumanDecisionExposureReplayError(
                        "Human-decision exposure reservation is already completed"
                    )
                if (
                    parsed.get("session_ref") == event.session_ref
                    and parsed.get("artifact_id") == event.artifact_id
                ):
                    completed += 1
            if reservation is None:
                raise RuntimeAuthorizationAuditError(
                    "Human-decision exposure completion lacks its durable reservation"
                )
            if not _reservation_matches_prepared(reservation, reserved.prepared):
                raise RuntimeAuthorizationAuditError(
                    "Human-decision exposure reservation differs from its signed receipt"
                )
            if completed >= reservation.allowed_multiplicity:
                raise HumanDecisionExposureReplayError(
                    "Human-decision exposure replay exceeds the signed multiplicity"
                )
            self._write_locked(handle, event.model_dump(mode="json"))

    def _append_line(self, entry: dict[str, Any]) -> None:
        with self._locked_handle() as handle:
            self._write_locked(handle, entry)

    def _locked_handle(self) -> AbstractContextManager[TextIO]:
        """Return a process- and host-serialized append/read handle context."""
        from contextlib import contextmanager

        @contextmanager
        def _context() -> Iterator[TextIO]:
            with self._lock, self._path.open("a+", encoding="utf-8") as handle:
                if fcntl is None:
                    raise RuntimeAuthorizationAuditError(
                        "Host-level access-audit locking is unavailable"
                    )
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield handle
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        return _context()

    @staticmethod
    def _write_locked(handle: TextIO, entry: dict[str, Any]) -> None:
        line = fast_json_dumps(entry, sort_keys=False) + "\n"
        handle.seek(0, os.SEEK_END)
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _parse_authority_scan_line(raw_line: str) -> dict[str, Any]:
    """Fail closed when corrupt trail bytes make replay state unknowable."""

    try:
        parsed = json.loads(raw_line)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeAuthorizationAuditError(
            "Runtime access audit corruption makes exposure reservation state unknowable"
        ) from exc
    if not isinstance(parsed, dict):
        raise RuntimeAuthorizationAuditError(
            "Runtime access audit entry must be an object for exposure reservation scans"
        )
    return cast("dict[str, Any]", parsed)


@dataclass(frozen=True, slots=True)
class PreparedHumanDecisionExposureEvent:
    """Unsigned authority receipt prepared before any response bytes are sent."""

    unsigned_event: HumanDecisionExposureAuditEvent
    completed_event: HumanDecisionExposureAuditEvent
    receipt_ref: str


@dataclass(frozen=True, slots=True)
class ReservedHumanDecisionExposureEvent:
    """Prepared receipt plus its durable pre-send delivery reservation."""

    prepared: PreparedHumanDecisionExposureEvent
    reservation_id: str


def _validate_prepared_exposure(
    prepared: PreparedHumanDecisionExposureEvent,
) -> None:
    """Content-bind a prepared value instead of trusting its dataclass shape."""
    if type(prepared) is not PreparedHumanDecisionExposureEvent:
        raise TypeError("prepared must be a PreparedHumanDecisionExposureEvent")
    unsigned = prepared.unsigned_event
    completed = prepared.completed_event
    if (
        type(unsigned) is not HumanDecisionExposureAuditEvent
        or type(completed) is not HumanDecisionExposureAuditEvent
        or unsigned.event_receipt_ref is not None
        or completed != unsigned.model_copy(update={"event_receipt_ref": prepared.receipt_ref})
    ):
        raise RuntimeAuthorizationAuditError(
            "Human-decision exposure prepared receipt is not content-bound"
        )
    expected_ref = (
        "sha256:"
        + sha256(
            canon.to_canonical_bytes(
                unsigned.model_dump(mode="json"),
                canon.CanonSpec(forbid_floats=False),
            )
        ).hexdigest()
    )
    if prepared.receipt_ref != expected_ref:
        raise RuntimeAuthorizationAuditError(
            "Human-decision exposure receipt ref differs from its exact payload"
        )


def _reservation_matches_prepared(
    reservation: HumanDecisionExposureDeliveryReservation,
    prepared: PreparedHumanDecisionExposureEvent,
) -> bool:
    """Compare every authority-bearing reservation field to the signed event."""
    event = prepared.completed_event
    return (
        reservation.reservation_id == event.event_id
        and reservation.event_id == event.event_id
        and reservation.event_receipt_ref == prepared.receipt_ref
        and reservation.tenant_id == event.tenant_id
        and reservation.actor_ref == event.actor_ref
        and reservation.run_id == event.run_id
        and reservation.request_ref == event.request_ref
        and reservation.request_digest == event.request_digest
        and reservation.basis_digest == event.basis_digest
        and reservation.session_ref == event.session_ref
        and reservation.artifact_id == event.artifact_id
        and reservation.expected_content_digest == event.content_digest
        and reservation.expected_bytes == event.delivered_bytes
        and reservation.allowed_multiplicity == event.allowed_multiplicity
        and reservation.verifier_epoch == event.verifier_epoch
    )


def _exposure_authority_write_inputs(
    event: HumanDecisionExposureAuditEvent,
    *,
    has_artifact: Callable[[str], bool],
) -> tuple[dict[str, Any], str, artifacts.ArtifactWriteOptions, dict[str, Any]]:
    """Build the one canonical receipt write used by direct and service seams."""
    canon_spec = canon.CanonSpec(forbid_floats=False)
    payload = event.model_dump(mode="json")
    payload_ref = "sha256:" + sha256(canon.to_canonical_bytes(payload, canon_spec)).hexdigest()
    input_refs = tuple(
        ref
        for ref in (
            event.artifact_id,
            event.session_ref,
            event.request_ref,
            event.basis_digest,
        )
        if _is_canonical_artifact_ref(ref) and has_artifact(ref)
    )
    generated_at = datetime.fromtimestamp(event.timestamp, tz=UTC).isoformat()
    closure_digest = (
        "sha256:"
        + sha256(
            canon.to_canonical_bytes(
                {
                    "event_id": event.event_id,
                    "tenant_id": event.tenant_id,
                    "run_id": event.run_id,
                    "session_ref": event.session_ref,
                    "artifact_id": event.artifact_id,
                }
            )
        ).hexdigest()
    )
    job_id = f"human-decision-exposure-{event.event_id}"
    options = artifacts.ArtifactWriteOptions(
        kind=HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name="polisyos.runtime.HumanDecisionExposureAuditEvent",
            version=HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
        ),
        producer=artifacts.ProducerInfo(
            component="polisyos.runtime.http.access_audit",
            version="1.0",
        ),
        governance=artifacts.ArtifactGovernanceInfo(classification="restricted"),
        inputs=[
            artifacts.InputRef(
                artifact_id=artifacts.ArtifactID.model_validate(ref),
                role="exposure_input",
            )
            for ref in input_refs
        ],
    )
    authority_fields: dict[str, Any] = {
        "evidence_id": event.event_id,
        "evidence_class": "authority_bearing",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "owner": "polisyos.runtime.http.human_decision_custody",
        "reader_contract": "runtime.http.human_decision_exposure_event.reader",
        "reader_contract_version": "1.0",
        "tenant_id": event.tenant_id,
        "cell_id": None,
        "run_id": event.run_id,
        "job_id": job_id,
        "trace_id": f"trace-{event.event_id}",
        "span_id": f"span-{event.event_id}",
        "parent_span_id": None,
        "requested_execution_profile": "governed",
        "effective_execution_profile": "governed",
        "phase": "human_decision_evidence_delivery",
        "generated_at": generated_at,
        "as_of_time": generated_at,
        "same_input_closure": {
            "closure_id": f"human-decision-exposure.{closure_digest[7:31]}",
            "status": "closed",
            "run_id": event.run_id,
            "job_id": job_id,
            "tenant_id": event.tenant_id,
            "cell_id": None,
            "effective_mode_ref": "runtime://human-decision/evidence-delivery",
            "degradation_ledger_ref": None,
            "evidence_input_refs": input_refs,
            "closure_sha256": closure_digest,
        },
        "input_refs": input_refs,
        "effective_mode_ref": "runtime://human-decision/evidence-delivery",
        "degradation_ledger_ref": None,
        "semantic_binding_ref": event.session_ref,
        "validation_status": "pass",
        "blocking_status": "non_blocking",
        "governance": GovernanceMetadata(
            classification="restricted",
            authority_boundary="runtime.human_decision_exposure_transport",
            pii="identity_bound",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="none",
            approval_policy="completed_exact_byte_delivery_only",
        ),
        "event_id": f"evt_human_decision_exposure_{closure_digest[7:31]}",
        "event_source": "polisyos.runtime.http.access_audit",
        "event_type": "polisyos.runtime.diagnostic.cas_write.v1",
        "event_subject": (f"run/{event.run_id}/human-decision-exposure/{event.event_id}"),
        "state_after": "prepared",
        "canon_spec": canon_spec,
    }
    return payload, payload_ref, options, authority_fields


def _is_canonical_artifact_ref(value: str) -> bool:
    """Return whether a string is an exact lowercase SHA-256 CAS reference."""

    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _prepared_exposure_from_result(
    event: HumanDecisionExposureAuditEvent,
    *,
    payload_ref: str,
    result: _AuthorityWriteResult,
) -> PreparedHumanDecisionExposureEvent:
    receipt_ref = str(result.cas_ref.artifact_id)
    if receipt_ref != payload_ref or result.payload_sha256 != payload_ref[7:]:
        raise RuntimeAuthorizationAuditError(
            "Human-decision exposure receipt digest changed during persistence"
        )
    return PreparedHumanDecisionExposureEvent(
        unsigned_event=event,
        completed_event=event.model_copy(update={"event_receipt_ref": receipt_ref}),
        receipt_ref=receipt_ref,
    )


def prepare_human_decision_exposure_event(
    *,
    event: HumanDecisionExposureAuditEvent,
    artifact_store: _ExposureArtifactStore,
    event_log: object,
) -> PreparedHumanDecisionExposureEvent:
    """Persist an unsigned receipt; completion remains impossible until delivery."""
    if type(event) is not HumanDecisionExposureAuditEvent:
        raise TypeError("event must be a HumanDecisionExposureAuditEvent")
    if event.event_receipt_ref is not None:
        raise ValueError("an exposure event must be prepared without a receipt ref")
    authority_artifacts = cast(
        "Any", import_module("polisyos.runtime.http.services.control.artifacts")
    )
    writer = authority_artifacts.write_runtime_authority_artifact

    payload, payload_ref, options, authority_fields = _exposure_authority_write_inputs(
        event, has_artifact=artifact_store.has
    )
    result = writer(
        artifact_store,
        event_log,
        payload,
        options,
        **authority_fields,
    )
    return _prepared_exposure_from_result(
        event,
        payload_ref=payload_ref,
        result=result,
    )


def prepare_human_decision_exposure_event_through_sink(
    *,
    event: HumanDecisionExposureAuditEvent,
    authority_sink: _ExposureAuthoritySink,
) -> PreparedHumanDecisionExposureEvent:
    """Prepare through the deployed narrow CAS/event sink without exposing internals."""
    if type(event) is not HumanDecisionExposureAuditEvent:
        raise TypeError("event must be a HumanDecisionExposureAuditEvent")
    if event.event_receipt_ref is not None:
        raise ValueError("an exposure event must be prepared without a receipt ref")
    payload, payload_ref, options, authority_fields = _exposure_authority_write_inputs(
        event,
        has_artifact=authority_sink.has_artifact,
    )
    result = authority_sink.write_authority_artifact(
        payload,
        options,
        authority_fields=authority_fields,
    )
    return _prepared_exposure_from_result(
        event,
        payload_ref=payload_ref,
        result=result,
    )


def reserve_human_decision_exposure_event(
    *,
    trail: RuntimeDataAccessAuditTrail,
    prepared: PreparedHumanDecisionExposureEvent,
    artifact_store: _ExposureArtifactStore,
    signer: artifacts.Ed25519Signer,
    signer_identity: str,
    verifier: artifacts.Ed25519Verifier,
) -> ReservedHumanDecisionExposureEvent:
    """Verify custody, then claim one signed-quota slot before response bytes."""
    _verify_prepared_exposure_signature(
        prepared=prepared,
        get_signature=lambda ref: artifact_store.get_signature(
            artifacts.ArtifactID.model_validate(ref)
        ),
        sign=lambda ref: artifact_store.sign_artifact(
            artifacts.ArtifactID.model_validate(ref),
            signer,
            signer_identity=signer_identity,
        ),
        verify=lambda ref: artifact_store.verify_signature(
            artifacts.ArtifactID.model_validate(ref),
            verifier,
            strict_identity=True,
        ),
        signer=signer,
        signer_identity=signer_identity,
    )
    return trail._reserve_exposure_delivery(prepared)


def reserve_human_decision_exposure_event_through_sink(
    *,
    trail: RuntimeDataAccessAuditTrail,
    prepared: PreparedHumanDecisionExposureEvent,
    authority_sink: _ExposureAuthoritySink,
    signer: artifacts.Ed25519Signer,
    signer_identity: str,
    verifier: artifacts.Ed25519Verifier,
) -> ReservedHumanDecisionExposureEvent:
    """Verify deployed custody, then claim a slot before response bytes."""
    _verify_prepared_exposure_signature(
        prepared=prepared,
        get_signature=authority_sink.get_artifact_signature,
        sign=lambda ref: authority_sink.sign_artifact(
            ref,
            signer,
            signer_identity=signer_identity,
        ),
        verify=lambda ref: authority_sink.verify_artifact_signature(
            ref,
            verifier,
            strict_identity=True,
        ),
        signer=signer,
        signer_identity=signer_identity,
    )
    return trail._reserve_exposure_delivery(prepared)


def _verify_prepared_exposure_signature(
    *,
    prepared: PreparedHumanDecisionExposureEvent,
    get_signature: Callable[[str], object | None],
    sign: Callable[[str], object],
    verify: Callable[[str], _ExposureSignatureVerification],
    signer: artifacts.Ed25519Signer,
    signer_identity: str,
) -> None:
    """Prove the prepared receipt's exact custody signature before reservation."""
    _validate_prepared_exposure(prepared)
    if get_signature(prepared.receipt_ref) is None:
        sign(prepared.receipt_ref)
    verification = verify(prepared.receipt_ref)
    if (
        verification.status is not artifacts.SignatureVerificationStatus.VALID
        or verification.signer_identity != signer_identity
        or verification.key_id != signer.key_id
    ):
        raise RuntimeAuthorizationAuditError(
            "Human-decision exposure receipt signature did not verify"
        )


def complete_human_decision_exposure_event(
    *,
    trail: RuntimeDataAccessAuditTrail,
    reserved: ReservedHumanDecisionExposureEvent,
    artifact_store: _ExposureArtifactStore,
    signer: artifacts.Ed25519Signer,
    signer_identity: str,
    verifier: artifacts.Ed25519Verifier,
) -> HumanDecisionExposureAuditEvent:
    """Reverify preflight custody after exact bytes, then append completion."""
    if type(reserved) is not ReservedHumanDecisionExposureEvent:
        raise TypeError("reserved must be a ReservedHumanDecisionExposureEvent")
    prepared = reserved.prepared
    _validate_prepared_exposure(prepared)
    receipt_id = artifacts.ArtifactID.model_validate(prepared.receipt_ref)
    if artifact_store.get_signature(receipt_id) is None:
        raise RuntimeAuthorizationAuditError(
            "Reserved human-decision exposure receipt lost its custody signature"
        )
    verification = artifact_store.verify_signature(
        receipt_id,
        verifier,
        strict_identity=True,
    )
    if (
        verification.status is not artifacts.SignatureVerificationStatus.VALID
        or verification.signer_identity != signer_identity
        or verification.key_id != signer.key_id
    ):
        raise RuntimeAuthorizationAuditError(
            "Human-decision exposure receipt signature did not verify"
        )
    trail._append_reserved_exposure(reserved)
    return prepared.completed_event


def complete_human_decision_exposure_event_through_sink(
    *,
    trail: RuntimeDataAccessAuditTrail,
    reserved: ReservedHumanDecisionExposureEvent,
    authority_sink: _ExposureAuthoritySink,
    signer: artifacts.Ed25519Signer,
    signer_identity: str,
    verifier: artifacts.Ed25519Verifier,
) -> HumanDecisionExposureAuditEvent:
    """Reverify deployed custody after exact bytes, then append completion."""
    if type(reserved) is not ReservedHumanDecisionExposureEvent:
        raise TypeError("reserved must be a ReservedHumanDecisionExposureEvent")
    prepared = reserved.prepared
    _validate_prepared_exposure(prepared)
    if authority_sink.get_artifact_signature(prepared.receipt_ref) is None:
        raise RuntimeAuthorizationAuditError(
            "Reserved human-decision exposure receipt lost its custody signature"
        )
    verification = authority_sink.verify_artifact_signature(
        prepared.receipt_ref,
        verifier,
        strict_identity=True,
    )
    if (
        verification.status is not artifacts.SignatureVerificationStatus.VALID
        or verification.signer_identity != signer_identity
        or verification.key_id != signer.key_id
    ):
        raise RuntimeAuthorizationAuditError(
            "Human-decision exposure receipt signature did not verify"
        )
    trail._append_reserved_exposure(reserved)
    return prepared.completed_event


def emit_runtime_authorization_audit(
    request: Request,
    *,
    outcome: RuntimeAuthorizationOutcome,
    denial_reason: str = "",
    step_up_outcome: Literal["verified", "denied", "unresolved"] | None = None,
    raise_on_failure: bool,
) -> bool:
    """Append one idempotent terminal authorization admission to ``access.jsonl``.

    The request body and all bearer/step-up assertion material are deliberately
    absent from this contract. An allow-path append failure raises so a handler
    cannot execute without its authorization receipt. The allow outcome records
    admission under the immutable bound context; it is not a handler-success
    assertion.
    """
    if not isinstance(outcome, RuntimeAuthorizationOutcome):
        raise TypeError("outcome must be a RuntimeAuthorizationOutcome")
    state = request.state
    if getattr(state, "runtime_authorization_audit_terminal", False):
        return bool(getattr(state, "runtime_authorization_audit_emitted", False))

    requirement = getattr(state, "authz_route_requirement", None)
    permission_value = getattr(getattr(requirement, "permission", None), "value", "")
    matched_route = getattr(state, "authz_matched_route", None)
    route_path = getattr(matched_route, "path_template", None) or str(request.url.path)
    bound_resource = (
        getattr(state, "authz_bound_resource", None)
        if getattr(state, "authz_resource_frozen", False) is True
        else None
    )
    effective_scope = getattr(state, "authz_effective_scope", None)
    access_scope = effective_scope or getattr(state, "access_scope", None)
    claims = getattr(state, "user_claims", None)
    subject = (
        getattr(access_scope, "user_sub", None)
        or getattr(access_scope, "spiffe_id", None)
        or getattr(claims, "sub", None)
        or "anonymous"
    )
    tenant_id = getattr(access_scope, "tenant_id", None) or getattr(claims, "tenant_id", None) or ""
    principal_type = getattr(access_scope, "principal_type", None) or (
        "user" if claims is not None else "anonymous"
    )
    step_requirement = getattr(state, "authz_step_up_requirement", None)
    step_class = getattr(getattr(step_requirement, "step_up_class", None), "value", "")
    if step_requirement is None:
        resolved_step_outcome = "not_required"
    elif step_up_outcome is not None:
        resolved_step_outcome = step_up_outcome
    elif getattr(state, "step_up_verification", None) is not None:
        resolved_step_outcome = "verified"
    else:
        resolved_step_outcome = "unresolved"
    request_id = getattr(state, "request_id", None)
    if not isinstance(request_id, str) or not request_id:
        request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid.uuid4())
        state.request_id = request_id
    event = RuntimeAuthorizationAuditEvent(
        timestamp=time.time(),
        request_id=request_id,
        outcome=outcome,
        denial_reason=(denial_reason if outcome is RuntimeAuthorizationOutcome.DENY else ""),
        method=request.method.upper(),
        route_path=route_path,
        permission=str(permission_value),
        resource_id=str(getattr(bound_resource, "resource_id", "")),
        resource_digest=str(getattr(bound_resource, "resource_digest", "")),
        resource_kind=str(getattr(bound_resource, "resource_kind", "")),
        binding_authority=str(getattr(getattr(bound_resource, "authority", None), "value", "")),
        step_up_class=str(step_class),
        step_up_outcome=resolved_step_outcome,
        subject=str(subject),
        tenant_id=str(tenant_id),
        principal_type=str(principal_type),
        opa_policy=str(getattr(state, "authz_policy", "") or ""),
        opa_reasons=[str(reason) for reason in getattr(state, "authz_reasons", ())],
    )
    app_state = getattr(getattr(request, "app", object()), "state", object())
    container = getattr(app_state, "runtime_container", None)
    audit_trail = getattr(container, "runtime_access_audit", None)
    if audit_trail is None:
        audit_trail = getattr(app_state, "runtime_access_audit", None)
    append = getattr(audit_trail, "append", None)
    try:
        if not callable(append):
            raise RuntimeAuthorizationAuditError(
                "Runtime authorization access-audit trail is unavailable"
            )
        append(event.model_dump(mode="json"))
    except Exception as exc:
        state.runtime_authorization_audit_terminal = True
        state.runtime_authorization_audit_emitted = False
        if raise_on_failure:
            if isinstance(exc, RuntimeAuthorizationAuditError):
                raise
            raise RuntimeAuthorizationAuditError(
                "Runtime authorization access-audit append failed"
            ) from exc
        logger.exception("Authorization denial audit append failed")
        return False
    state.runtime_authorization_audit_terminal = True
    state.runtime_authorization_audit_emitted = True
    return True


async def emit_runtime_authorization_audit_async(
    request: Request,
    *,
    outcome: RuntimeAuthorizationOutcome,
    denial_reason: str = "",
    step_up_outcome: Literal["verified", "denied", "unresolved"] | None = None,
    raise_on_failure: bool,
) -> bool:
    """Append one decision without running durable audit I/O on the ASGI loop."""
    return await to_thread.run_sync(
        partial(
            emit_runtime_authorization_audit,
            request,
            outcome=outcome,
            denial_reason=denial_reason,
            step_up_outcome=step_up_outcome,
            raise_on_failure=raise_on_failure,
        )
    )


__all__ = [
    "HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND",
    "HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION",
    "HumanDecisionExposureAuditEvent",
    "HumanDecisionExposureReplayError",
    "PreparedHumanDecisionExposureEvent",
    "ReservedHumanDecisionExposureEvent",
    "RuntimeAuthorizationAuditError",
    "RuntimeAuthorizationAuditEvent",
    "RuntimeAuthorizationOutcome",
    "RuntimeDataAccessAuditTrail",
    "complete_human_decision_exposure_event",
    "complete_human_decision_exposure_event_through_sink",
    "emit_runtime_authorization_audit",
    "emit_runtime_authorization_audit_async",
    "prepare_human_decision_exposure_event",
    "prepare_human_decision_exposure_event_through_sink",
    "reserve_human_decision_exposure_event",
    "reserve_human_decision_exposure_event_through_sink",
]
