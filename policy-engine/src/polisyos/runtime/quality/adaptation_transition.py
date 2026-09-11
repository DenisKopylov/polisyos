"""Durable candidate response custody over the existing control outbox and CAS.

ControlPlaneStore owns persistence, uniqueness and checkpoints; FileSystemCAS owns
artifact bytes; the PDC AuthorityBoundary owns authority vocabulary. This module
adds the GY-CR1 response bridge, not another database, scheduler or executor.
WP-08 leaves every signer slot empty. No protected action can be authorized here.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
    infer_artifact_store_config,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import to_canonical_bytes
from polisyos.fabric.io import atomic
from polisyos.pdc import AuthorityBoundary

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.core.artifacts import ArtifactStore
    from polisyos.runtime.http.services.control_plane_store import (
        ControlOutboxRecord,
        ControlPlaneStore,
    )

SCHEMA_VERSION = "polisyos.runtime.adaptation_transition.v1"
REQUEST_TOPIC = "polisyos.runtime.adaptation.request.v1"
DECISION_TOPIC = "polisyos.runtime.adaptation.decision.v1"
RESTART_TOPIC = "polisyos.runtime.adaptation.restart.v1"
type _Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _boundary() -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["candidate_response_custody"],
        may_not_use_for=[
            "protected_action_authorization", "external_policy_execution",
            "restart_authorization", "signer_appointment",
        ],
        source_authority="deterministic_producer",
        posture="shadow",
        rule_version_refs=[SCHEMA_VERSION, "WP-08", "FM-OPS-16"],
        known_limits=["No institutional signer or after-hours substitute is appointed."],
    )


class _CandidateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")
    artifact_kind: ClassVar[str]
    schema_version: Literal["polisyos.runtime.adaptation_transition.v1"] = SCHEMA_VERSION
    authority_boundary: AuthorityBoundary = Field(default_factory=_boundary)
    appointed_signer: None = None
    after_hours_substitute: None = None
    execution_authorized: Literal[False] = False

    @model_validator(mode="after")
    def _candidate_boundary(self) -> Self:
        if self.authority_boundary.model_dump() != _boundary().model_dump():
            raise ValueError("candidate_authority_boundary_required")
        return self


class CandidateOperationCharter(_CandidateRecord):
    """Candidate operation description; it appoints and preauthorizes nobody."""

    action_description: _Text
    required_signer_role: _Text
    escalation_after_seconds: int = Field(gt=0)
    conservative_posture: Literal["no_authority_expansion"] = "no_authority_expansion"
    loss_description: _Text = "unknown; no action authority established"
    reversibility_description: _Text = "unknown"
    blast_radius_description: _Text = "unknown"
    provenance_refs: tuple[_Text, ...] = Field(min_length=1)


class AdaptationTransitionRequest(_CandidateRecord):
    """Persistable candidate request carrying unratified operation context."""

    artifact_kind = "runtime.adaptation_transition_request"
    request_id: _Text
    tenant_id: _Text
    cell_id: _Text
    contract_ref: _Text
    signal_refs: tuple[_Text, ...]
    diagnosis_refs: tuple[_Text, ...]
    observed_at: AwareDatetime
    current_context: dict[_Text, _Text]
    requested_context: dict[_Text, _Text]
    charter: CandidateOperationCharter
    intended_claim_consequence: _Text
    provenance_refs: tuple[_Text, ...] = Field(min_length=1)


class AdaptationDecisionRecord(_CandidateRecord):
    """A deterministic custody refusal, never a signed adaptation approval."""

    artifact_kind = "runtime.adaptation_decision_record"
    request_ref: _Text
    status: Literal["failed_safe"] = "failed_safe"
    missing_role: _Text
    reason: Literal["institutional_signer_not_established"] = "institutional_signer_not_established"
    predicate_provenance: Literal["not_established"] = "not_established"
    conservative_posture: Literal["no_authority_expansion"] = "no_authority_expansion"
    effective_at: AwareDatetime
    escalate_at: AwareDatetime
    public_meaning: Literal["protected_response_withheld"] = "protected_response_withheld"


class RestartEvidenceRecord(_CandidateRecord):
    """Bound candidate restart evidence; its presence cannot reopen a response."""

    artifact_kind = "runtime.restart_evidence_record"
    prior_decision_ref: _Text
    repair_ref: _Text
    test_refs: tuple[_Text, ...]
    measurement_health_ref: _Text
    residual_harm_refs: tuple[_Text, ...]
    historical_claim_status: _Text
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    provenance_refs: tuple[_Text, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered_interval(self) -> Self:
        if self.expires_at <= self.observed_at:
            raise ValueError("restart_evidence_interval_invalid")
        return self


class KPIControlStateSnapshot(_CandidateRecord):
    """Persisted audit projection of custody state with no Atlas status extension."""

    artifact_kind = "runtime.kpi_control_state_snapshot"
    request_ref: _Text
    decision_ref: _Text | None
    restart_ref: _Text | None
    restart_disposition: Literal["not_supplied", "current_candidate", "expired_candidate"]
    status: Literal["pending", "failed_safe"]
    missing_role: _Text
    conservative_posture: Literal["no_authority_expansion"] = "no_authority_expansion"
    current_context: dict[_Text, _Text]
    requested_context: dict[_Text, _Text]
    contract_ref: _Text
    open_diagnosis_refs: tuple[_Text, ...]
    observed_at: AwareDatetime
    received_at: AwareDatetime
    decision_recorded_at: AwareDatetime | None
    as_of: AwareDatetime
    escalate_at: AwareDatetime
    escalation_due: bool


class AdaptationTransitionRuntime:
    """Submit, recover and inspect durable candidate response requests.

    Args:
        store: Existing Runtime control persistence owner.
        artifact_store: Existing tenant-scoped CAS owner.
        tenant_id: Exact tenant scope of this composition.
        cell_id: Exact cell scope of this composition.
    """

    def __init__(
        self, *, store: ControlPlaneStore, artifact_store: ArtifactStore,
        tenant_id: str, cell_id: str,
    ) -> None:
        self._store = store
        self._cas = artifact_store
        cas_config = infer_artifact_store_config(artifact_store)
        if cas_config is None or cas_config.backend != "filesystem" or not cas_config.root:
            raise ValueError("candidate_custody_filesystem_root_unavailable")
        self._cas_root = Path(cas_config.root)
        self._tenant_id = tenant_id
        self._cell_id = cell_id
        if atomic.fcntl is None:
            raise RuntimeError("candidate_custody_process_lock_unavailable")

    @classmethod
    def open(cls, *, root: Path, tenant_id: str, cell_id: str) -> Self:
        """Open the real local owners in their supported composition-root order."""
        # The existing service facade initializes split control modules before
        # the store; direct cold store import encounters their historical cycle.
        importlib.import_module("polisyos.runtime.http.services.control")
        from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

        return cls(
            store=ControlPlaneStore(backend="sqlite", sqlite_path=root / "control.sqlite"),
            artifact_store=build_artifact_store(
                ArtifactStoreConfig(
                    backend="filesystem",
                    root=str(root / "cas"),
                ),
                tenant_id=tenant_id,
                cell_id=cell_id,
            ),
            tenant_id=tenant_id, cell_id=cell_id,
        )

    def submit(self, request: AdaptationTransitionRequest) -> str:
        """Durably admit one candidate, refusing same-identity changed bytes."""
        request = AdaptationTransitionRequest.model_validate(request.model_dump(mode="json"))
        self._check_scope(request)
        reference = self._persist(request)
        record = self._enqueue_exact(
            topic=REQUEST_TOPIC, key=self._request_key(request),
            payload={"artifact_ref": reference}, conflict="request_identity_conflict",
        )
        return record.event_id

    def process(self, ticket: str) -> AdaptationDecisionRecord:
        """Recover or publish the single failed-safe custody decision, then checkpoint."""
        row, request = self._read_request(ticket)
        decision = self._expected_decision(row, request)
        reference = self._persist(decision)
        self._enqueue_exact(
            topic=DECISION_TOPIC, key=str(row.event_key),
            payload={"artifact_ref": reference, "request_ref": decision.request_ref},
            conflict="custody_publication_conflict",
        )
        self._read_decision(row, request)
        self._checkpoint(ticket)
        return decision

    def record_restart(self, ticket: str, evidence: RestartEvidenceRecord) -> str:
        """Persist exact prior-decision-bound candidate evidence without reopening."""
        evidence = RestartEvidenceRecord.model_validate(evidence.model_dump(mode="json"))
        row, request = self._read_request(ticket)
        decision_row, _ = self._read_decision(row, request)
        if (
            decision_row is None
            or evidence.prior_decision_ref != decision_row.payload["artifact_ref"]
        ):
            raise ValueError("restart_decision_mismatch")
        reference = self._persist(evidence)
        self._enqueue_exact(
            topic=RESTART_TOPIC, key=reference,
            payload={"artifact_ref": reference, "request_ref": row.payload["artifact_ref"]},
            conflict="restart_publication_conflict",
        )
        return reference

    def snapshot(
        self, ticket: str, *, as_of: datetime, restart_ref: str | None = None,
    ) -> KPIControlStateSnapshot:
        """Independently read and persist the exact custody state and clock projection."""
        if as_of.tzinfo is None:
            raise ValueError("snapshot_time_requires_timezone")
        row, request = self._read_request(ticket)
        if as_of < row.created_at:
            raise ValueError("snapshot_before_receipt")
        if request.observed_at > as_of:
            raise ValueError("request_observation_after_snapshot")
        decision_row, decision = self._read_decision(row, request)
        if decision_row is not None and decision_row.created_at > as_of:
            raise ValueError("decision_not_available_as_of")
        decision_ref = decision_row.payload["artifact_ref"] if decision_row is not None else None
        restart_disposition = "not_supplied"
        if restart_ref is not None:
            restart_row = self._by_key(RESTART_TOPIC, restart_ref)
            if restart_row is None or restart_row.payload != {
                "artifact_ref": restart_ref, "request_ref": row.payload["artifact_ref"],
            }:
                raise ValueError("restart_receipt_missing")
            evidence = self._load(restart_ref, RestartEvidenceRecord)
            if evidence.prior_decision_ref != decision_ref:
                raise ValueError("restart_decision_mismatch")
            if restart_row.created_at > as_of or evidence.observed_at > as_of:
                raise ValueError("restart_evidence_not_available_as_of")
            restart_disposition = (
                "expired_candidate" if as_of >= evidence.expires_at else "current_candidate"
            )
        escalate_at = row.created_at + timedelta(seconds=request.charter.escalation_after_seconds)
        snapshot = KPIControlStateSnapshot(
            request_ref=row.payload["artifact_ref"], decision_ref=decision_ref,
            restart_ref=restart_ref, restart_disposition=restart_disposition,
            status="failed_safe" if decision is not None else "pending",
            missing_role=request.charter.required_signer_role,
            current_context=request.current_context, requested_context=request.requested_context,
            contract_ref=request.contract_ref, open_diagnosis_refs=request.diagnosis_refs,
            observed_at=request.observed_at, received_at=row.created_at,
            decision_recorded_at=decision_row.created_at if decision_row is not None else None,
            as_of=as_of, escalate_at=escalate_at, escalation_due=as_of >= escalate_at,
        )
        self._persist(snapshot)
        return snapshot

    def _by_key(self, topic: str, key: str) -> ControlOutboxRecord | None:
        # Architect-approved internal Runtime seam. Preserve governed owner bytes;
        # never reproduce its SQL or enumerate its capped list API to find a key.
        return self._store._get_outbox_event_by_key(topic=topic, event_key=key)

    def _enqueue_exact(
        self, *, topic: str, key: str, payload: dict[str, str], conflict: str,
    ) -> ControlOutboxRecord:
        try:
            row = self._store.enqueue_outbox_event(topic=topic, event_key=key, payload=payload)
        except Exception:
            # A competing insert can win the existing SQL unique constraint.
            # Reconcile only an actual persisted exact row; other failures propagate.
            row = self._by_key(topic, key)
            if row is None:
                raise
        if row.topic != topic or row.event_key != key or row.payload != payload:
            raise ValueError(conflict)
        return row

    def _checkpoint(self, ticket: str) -> None:
        row = self._store.get_outbox_event(ticket)
        if row is None:
            raise ValueError("request_receipt_missing")
        if row.state != "published":
            self._store.mark_outbox_published(event_id=ticket)

    def _read_request(self, ticket: str) -> tuple[ControlOutboxRecord, AdaptationTransitionRequest]:
        row = self._store.get_outbox_event(ticket)
        if row is None or row.topic != REQUEST_TOPIC or set(row.payload) != {"artifact_ref"}:
            raise ValueError("request_receipt_missing")
        request = self._load(row.payload["artifact_ref"], AdaptationTransitionRequest)
        self._check_scope(request)
        if row.event_key != self._request_key(request):
            raise ValueError("request_identity_conflict")
        return row, request

    def _read_decision(
        self, row: ControlOutboxRecord, request: AdaptationTransitionRequest,
    ) -> tuple[ControlOutboxRecord | None, AdaptationDecisionRecord | None]:
        publication = self._by_key(DECISION_TOPIC, str(row.event_key))
        if publication is None:
            return None, None
        if set(publication.payload) != {"artifact_ref", "request_ref"}:
            raise ValueError("custody_publication_conflict")
        decision = self._load(publication.payload["artifact_ref"], AdaptationDecisionRecord)
        if (
            publication.payload["request_ref"] != row.payload["artifact_ref"]
            or decision != self._expected_decision(row, request)
        ):
            raise ValueError("custody_publication_conflict")
        return publication, decision

    @staticmethod
    def _expected_decision(
        row: ControlOutboxRecord, request: AdaptationTransitionRequest,
    ) -> AdaptationDecisionRecord:
        return AdaptationDecisionRecord(
            request_ref=row.payload["artifact_ref"],
            missing_role=request.charter.required_signer_role,
            effective_at=row.created_at,
            escalate_at=(
                row.created_at + timedelta(seconds=request.charter.escalation_after_seconds)
            ),
        )

    def _check_scope(self, request: AdaptationTransitionRequest) -> None:
        if request.tenant_id != self._tenant_id or request.cell_id != self._cell_id:
            raise ValueError("request_scope_mismatch")

    @staticmethod
    def _request_key(request: AdaptationTransitionRequest) -> str:
        payload = {"tenant_id": request.tenant_id, "cell_id": request.cell_id,
                   "request_id": request.request_id}
        return hashlib.sha256(to_canonical_bytes(payload)).hexdigest()

    def _persist(self, record: _CandidateRecord) -> str:
        record = type(record).model_validate(record.model_dump(mode="json"))
        # The CAS ownership index has a per-instance lock. Serialize only its
        # put/readback across cooperating CR1 writers sharing this local CAS root.
        lock_path = self._cas_root / "artifacts/ownership/adaptation-transition.lock"
        with atomic.file_lock(lock_path):
            reference = str(self._cas.put_json(
                record.model_dump(mode="json"),
                ArtifactWriteOptions(
                    kind=record.artifact_kind, media_type="application/json",
                    schema=SchemaInfo(
                        name=f"polisyos.runtime.{type(record).__name__}", version="1.0",
                    ),
                ),
            ).artifact_id)
            if self._load(reference, type(record)) != record:
                raise ValueError("candidate_artifact_readback_mismatch")
        return reference

    def _load[T: _CandidateRecord](self, reference: str, record_type: type[T]) -> T:
        record = record_type.model_validate_json(self._cas.get_bytes(reference))
        manifest = self._cas.get_manifest(reference)
        if (
            manifest.kind != record_type.artifact_kind
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name != f"polisyos.runtime.{record_type.__name__}"
            or manifest.artifact_schema.version != "1.0"
        ):
            raise ValueError("candidate_artifact_manifest_mismatch")
        return record


def main(argv: Sequence[str] | None = None) -> int:
    """Run the local candidate request worker or persist an audit snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--cell", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit")
    submit.add_argument("request_file", type=Path)
    process = commands.add_parser("process")
    process.add_argument("ticket")
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("ticket")
    args = parser.parse_args(argv)
    runtime = AdaptationTransitionRuntime.open(
        root=args.root, tenant_id=args.tenant, cell_id=args.cell,
    )
    if args.command == "submit":
        request = AdaptationTransitionRequest.model_validate_json(args.request_file.read_bytes())
        sys.stdout.write(runtime.submit(request) + "\n")
    else:
        result = (
            runtime.process(args.ticket) if args.command == "process"
            else runtime.snapshot(args.ticket, as_of=datetime.now(UTC))
        )
        sys.stdout.write(result.model_dump_json(indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
