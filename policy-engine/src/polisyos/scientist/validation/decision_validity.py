"""Public scientist decision validity module API."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Concatenate, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.timestamps import to_iso_utc, utc_now
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import content_hash, from_canonical_bytes
from polisyos.core.contracts.decision_validity import (
    DecisionDependencyEvent,
    DecisionDependencyKind,
    DecisionLifecycleJob,
    DecisionTriggerRecord,
    DecisionTriggerType,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
    DecisionValidityTransition,
    EpochTransitionVerificationReceipt,
    EpochTransitionVerifier,
    EpochValidityBatchCompletionStatement,
    EpochValidityBatchReceipt,
    EpochValidityBatchTarget,
    EpochValidityPendingBatch,
    PersistedEpochValidityBatchEvidence,
)
from polisyos.core.contracts.feedback import DecisionMonitoringContract
from polisyos.scientist.orchestration.engine.operational_monitoring import get_operational_monitor

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore

_StateModel = TypeVar("_StateModel", bound=BaseModel)

_DECISION_VALIDITY_JSON_LOAD_ERRORS = (OSError, ValueError, json.JSONDecodeError)
_DECISION_VALIDITY_MODEL_ERRORS = (TypeError, ValueError, ValidationError)
_DECISION_VALIDITY_ARTIFACT_LOAD_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)


def _serialize_datetime(value: datetime | None) -> str | None:
    return to_iso_utc(value) if value is not None else None


class _DecisionPacketState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packet_ref: str
    decision_lineage_key: str
    current_status: DecisionValidityStatus = DecisionValidityStatus.WARNING
    last_checked_at: datetime | None = None
    evaluation_ref: str | None = None
    reasons: list[str] = Field(default_factory=list)
    active_triggers: list[DecisionTriggerRecord] = Field(default_factory=list)
    sticky_triggers: list[DecisionTriggerRecord] = Field(default_factory=list)
    dependency_keys: list[str] = Field(default_factory=list)
    review_required: bool = False
    supersedes_decision_ref: str | None = None
    superseded_by_ref: str | None = None
    monitoring_contract_ref: str | None = None
    latest_monitoring_report_ref: str | None = None
    latest_compare_report_ref: str | None = None
    latest_reissue_plan_ref: str | None = None
    lifecycle_events: list[DecisionDependencyEvent] = Field(default_factory=list)
    transition_history: list[DecisionValidityTransition] = Field(default_factory=list)
    lifecycle_jobs: list[DecisionLifecycleJob] = Field(default_factory=list)
    last_transition_at: datetime | None = None


class _DecisionLineageState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_lineage_key: str
    head_packet_ref: str
    evaluation_ref: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class _DecisionDependencyIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dependency_key: str
    dependency_kind: DecisionDependencyKind
    artifact_id: str | None = None
    packet_refs: list[str] = Field(default_factory=list)
    lineage_keys: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class _PersistedEpochBatchReceiptState(BaseModel):
    """Local index binding a batch id to exact CAS receipt bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt: EpochValidityBatchReceipt
    receipt_artifact_ref: ArtifactRef
    receipt_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class _DecisionValidityStateStore:
    """Persist decision validity packets, lineage heads, dependencies, and dedupe state."""

    def __init__(self, cas: ArtifactStore | Path) -> None:
        root_value = getattr(cas, "root", cas)
        if isinstance(root_value, str):
            root_path = Path(root_value)
        elif isinstance(root_value, Path):
            root_path = root_value
        else:
            raise TypeError("DecisionValidityStateStore requires a local store root or Path")
        self._base = root_path / "decision_validity"
        self._packets = self._base / "packets"
        self._lineages = self._base / "lineages"
        self._dependencies = self._base / "dependencies"
        self._dedupes = self._base / "dedupes"
        self._epoch_pending = self._base / "epoch_pending"
        self._epoch_receipts = self._base / "epoch_receipts"
        self._epoch_lock_path = self._base / "epoch_batch.lock"
        self._owner_process_lock = threading.RLock()
        self._owner_transaction_state = threading.local()
        self._packets.mkdir(parents=True, exist_ok=True)
        self._lineages.mkdir(parents=True, exist_ok=True)
        self._dependencies.mkdir(parents=True, exist_ok=True)
        self._dedupes.mkdir(parents=True, exist_ok=True)
        self._epoch_pending.mkdir(parents=True, exist_ok=True)
        self._epoch_receipts.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def make_key(value: str) -> str:
        normalized = value.strip()
        return content_hash(normalized) if normalized else "global"

    def _packet_path(self, packet_ref: str) -> Path:
        return self._packets / f"{self.make_key(packet_ref)}.json"

    def _lineage_path(self, lineage_key: str) -> Path:
        return self._lineages / f"{self.make_key(lineage_key)}.json"

    def _dependency_path(self, dependency_key: str) -> Path:
        return self._dependencies / f"{self.make_key(dependency_key)}.json"

    def _dedupe_path(self, dedupe_key: str) -> Path:
        return self._dedupes / f"{self.make_key(dedupe_key)}.json"

    def load_packet(self, packet_ref: str) -> _DecisionPacketState | None:
        return self._load_model_strict(self._packet_path(packet_ref), _DecisionPacketState)

    def save_packet(self, state: _DecisionPacketState) -> None:
        self._save_model(self._packet_path(state.packet_ref), state)

    def load_lineage(self, lineage_key: str) -> _DecisionLineageState | None:
        return self._load_model_strict(self._lineage_path(lineage_key), _DecisionLineageState)

    def save_lineage(self, state: _DecisionLineageState) -> None:
        self._save_model(self._lineage_path(state.decision_lineage_key), state)

    def load_dependency(self, dependency_key: str) -> _DecisionDependencyIndex | None:
        return self._load_model_strict(
            self._dependency_path(dependency_key), _DecisionDependencyIndex
        )

    def save_dependency(self, state: _DecisionDependencyIndex) -> None:
        self._save_model(self._dependency_path(state.dependency_key), state)

    def load_dedupe_event_id(self, dedupe_key: str) -> str | None:
        path = self._dedupe_path(dedupe_key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("decision_validity_owner_state_corrupt") from exc
        value = payload.get("event_id")
        if not isinstance(value, str) or not value:
            raise RuntimeError("decision_validity_owner_state_corrupt")
        return value

    def save_dedupe_event_id(self, dedupe_key: str, event_id: str) -> None:
        path = self._dedupe_path(dedupe_key)
        self._write_bytes_atomic(
            path,
            json.dumps(
                {"event_id": event_id}, sort_keys=True, separators=(",", ":")
            ).encode("utf-8"),
        )

    def load_epoch_pending(self, batch_id: str) -> EpochValidityPendingBatch | None:
        """Load one durable phase-one freeze."""

        return self._load_model_strict(
            self._epoch_pending / f"{self.make_key(batch_id)}.json",
            EpochValidityPendingBatch,
        )

    def save_epoch_pending(self, batch: EpochValidityPendingBatch) -> None:
        """Atomically publish the complete target denominator before mutation."""

        self._save_model(
            self._epoch_pending / f"{self.make_key(batch.batch_id)}.json",
            batch,
        )

    def list_epoch_pending(self) -> tuple[EpochValidityPendingBatch, ...]:
        """Enumerate every durable freeze for restart-safe owner reads."""

        batches: list[EpochValidityPendingBatch] = []
        for item in sorted(self._epoch_pending.glob("*.json")):
            batch = self._load_model_strict(item, EpochValidityPendingBatch)
            if batch is None:  # pragma: no cover - glob established existence
                raise RuntimeError("decision_validity_epoch_pending_disappeared")
            batches.append(batch)
        return tuple(batches)

    def clear_epoch_pending(self, batch_id: str) -> None:
        """Clear phase one only after a completed receipt is durable."""

        target = self._epoch_pending / f"{self.make_key(batch_id)}.json"
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        else:
            self._fsync_directory(target.parent)

    def load_epoch_receipt(self, batch_id: str) -> EpochValidityBatchReceipt | None:
        evidence = self.load_epoch_receipt_evidence(batch_id)
        return evidence.receipt if evidence is not None else None

    def load_epoch_receipt_evidence(self, batch_id: str) -> _PersistedEpochBatchReceiptState | None:
        return self._load_model_strict(
            self._epoch_receipts / f"{self.make_key(batch_id)}.json",
            _PersistedEpochBatchReceiptState,
        )

    def save_epoch_receipt(
        self,
        receipt: EpochValidityBatchReceipt,
        *,
        receipt_artifact_ref: ArtifactRef,
        receipt_content_hash: str,
    ) -> None:
        self._save_model(
            self._epoch_receipts / f"{self.make_key(receipt.batch_id)}.json",
            _PersistedEpochBatchReceiptState(
                receipt=receipt,
                receipt_artifact_ref=receipt_artifact_ref,
                receipt_content_hash=receipt_content_hash,
            ),
        )

    @contextmanager
    def owner_transaction(self):
        """Serialize every mutation that can change an owner denominator.

        The process-local lock makes the critical section thread-safe.  The
        outermost entry also takes the shared file lock, so independent
        service instances and processes use the same owner boundary.  Nested
        service calls reuse the outer transaction instead of re-locking it.
        """

        with self._owner_process_lock:
            depth = int(getattr(self._owner_transaction_state, "depth", 0))
            descriptor: int | None = None
            if depth == 0:
                descriptor = os.open(self._epoch_lock_path, os.O_CREAT | os.O_RDWR, 0o600)
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                self._owner_transaction_state.descriptor = descriptor
            self._owner_transaction_state.depth = depth + 1
            try:
                yield
            finally:
                next_depth = int(self._owner_transaction_state.depth) - 1
                self._owner_transaction_state.depth = next_depth
                if next_depth == 0:
                    outer_descriptor = int(self._owner_transaction_state.descriptor)
                    fcntl.flock(outer_descriptor, fcntl.LOCK_UN)
                    os.close(outer_descriptor)
                    del self._owner_transaction_state.descriptor

    epoch_batch_transaction = owner_transaction

    def current_projection_generation_ref(self) -> str:
        """Content-bind every file that can change the owner validity projection."""

        digest = hashlib.sha256()
        roots = (self._packets, self._epoch_pending, self._epoch_receipts)
        for root in roots:
            for item in sorted(root.glob("*.json")):
                relative = item.relative_to(self._base).as_posix().encode("utf-8")
                payload = item.read_bytes()
                digest.update(len(relative).to_bytes(8, "big"))
                digest.update(relative)
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
        return "sha256:" + digest.hexdigest()

    @staticmethod
    def _load_model(path: Path, model_type: type[_StateModel]) -> _StateModel | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except _DECISION_VALIDITY_JSON_LOAD_ERRORS:
            return None
        try:
            return cast("_StateModel", model_type.model_validate(payload))
        except _DECISION_VALIDITY_MODEL_ERRORS:
            return None

    @staticmethod
    def _load_model_strict(path: Path, model_type: type[_StateModel]) -> _StateModel | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return cast("_StateModel", model_type.model_validate(payload))
        except _DECISION_VALIDITY_JSON_LOAD_ERRORS + _DECISION_VALIDITY_MODEL_ERRORS as exc:
            raise RuntimeError("decision_validity_owner_state_corrupt") from exc

    @staticmethod
    def _save_model(path: Path, model: BaseModel) -> None:
        payload = json.dumps(
            model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        _DecisionValidityStateStore._write_bytes_atomic(path, payload)

    @staticmethod
    def _write_bytes_atomic(path: Path, payload: bytes) -> None:
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        descriptor = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            temp.replace(path)
            _DecisionValidityStateStore._fsync_directory(path.parent)
        except BaseException:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass
            raise
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class NoEpochTransitionVerifier:
    """Production default: no transition verifier has been configured."""

    verifier_provenance_ref = None

    def verify(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        requested_query_context_ref: str,
        expected_authority_purpose: str,
    ) -> EpochTransitionVerificationReceipt:
        del transition_artifact_ref, requested_query_context_ref, expected_authority_purpose
        raise ValueError("verifier_not_configured")


def _owner_transactional[**P, R](
    method: Callable[Concatenate[Any, P], R],
) -> Callable[Concatenate[Any, P], R]:
    """Run one public owner mutation under the shared re-entrant transaction."""

    @wraps(method)
    def wrapped(self: Any, *args: P.args, **kwargs: P.kwargs) -> R:
        with self._state.owner_transaction():
            return method(self, *args, **kwargs)

    return wrapped


class DecisionValidityService:
    """Coordinate decision packet registration, dependency tracking, and re-evaluation."""

    def __init__(
        self,
        store: ArtifactStore,
        *,
        reevaluate_ttl_seconds: int = 300,
        epoch_transition_verifier: EpochTransitionVerifier | None = None,
    ) -> None:
        self._store = store
        self._state = _DecisionValidityStateStore(store)
        self._ttl = max(0, int(reevaluate_ttl_seconds))
        self._epoch_transition_verifier = epoch_transition_verifier or NoEpochTransitionVerifier()

    def state_generation(self) -> int:
        """Return the number of persisted owner-projection records (test diagnostic)."""

        return sum(
            1
            for root in (
                self._state._packets,
                self._state._epoch_pending,
                self._state._epoch_receipts,
            )
            for _ in root.glob("*.json")
        )

    def current_projection_generation_ref(self) -> str:
        """Return the content-bound cache identity for all current validity facts."""

        return self._state.current_projection_generation_ref()

    @_owner_transactional
    def admit_epoch_validity_batch(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        requested_query_context_ref: str,
    ) -> EpochValidityBatchReceipt:
        """Verify and apply one complete owner-indexed epoch transition batch."""

        verifier = self._epoch_transition_verifier
        receipt = verifier.verify(
            transition_artifact_ref=transition_artifact_ref,
            requested_query_context_ref=requested_query_context_ref,
            expected_authority_purpose="decision_validity_epoch_transition",
        )
        self._validate_epoch_transition_receipt(
            receipt=receipt,
            transition_artifact_ref=transition_artifact_ref,
            requested_query_context_ref=requested_query_context_ref,
        )
        batch_id = _epoch_batch_id(
            transition_artifact_ref=transition_artifact_ref,
            requested_query_context_ref=requested_query_context_ref,
        )
        with self._state.epoch_batch_transaction():
            completed = self._load_completed_epoch_receipt(batch_id)
            pending = self._state.load_epoch_pending(batch_id)
            if completed is not None:
                self._require_completed_matches_verification(
                    completed=completed,
                    receipt=receipt,
                )
                if pending is not None:
                    self._require_pending_matches_verification(
                        pending=pending,
                        receipt=receipt,
                    )
                    self._state.clear_epoch_pending(batch_id)
                return completed

            if pending is None:
                active = self._state.list_epoch_pending()
                if active:
                    raise ValueError("batch_pending")
                expected_targets, expected_denominator = self._resolve_epoch_target_denominator(
                    dependency_keys=receipt.dependency_keys
                )
                observed_targets = {
                    (row.packet_ref, row.dependency_key, row.decision_lineage_key)
                    for row in receipt.targets
                }
                if observed_targets != expected_targets:
                    raise ValueError("target_denominator_mismatch")
                if receipt.dependency_denominator_ref != expected_denominator:
                    raise ValueError("dependency_denominator_unresolved")
                pending = EpochValidityPendingBatch(
                    batch_id=batch_id,
                    transition_artifact_ref=receipt.transition_artifact_ref,
                    transition_content_hash=receipt.transition_content_hash,
                    requested_query_context_ref=receipt.requested_query_context_ref,
                    verifier_provenance_ref=receipt.verifier_provenance_ref,
                    dependency_denominator_ref=receipt.dependency_denominator_ref,
                    adjudication_denominator_ref=receipt.adjudication_denominator_ref,
                    targets=receipt.targets,
                )
                # Phase one is the authoritative freeze and precedes every packet write.
                self._state.save_epoch_pending(pending)
            else:
                # Resume the exact frozen denominator; later owner-index changes do
                # not rewrite a batch that was already admitted.
                self._require_pending_matches_verification(
                    pending=pending,
                    receipt=receipt,
                )

            applied = list(pending.applied_packet_refs)
            targets_by_packet: dict[str, list[EpochValidityBatchTarget]] = {}
            for target in pending.targets:
                targets_by_packet.setdefault(target.packet_ref, []).append(target)
            for packet_ref, packet_targets in targets_by_packet.items():
                if packet_ref in applied:
                    continue
                statuses = [row.status for row in packet_targets]
                status = statuses[0]
                for candidate_status in statuses[1:]:
                    status = _max_status(status, candidate_status)
                reasons = _dedupe_strings([row.reason for row in packet_targets])
                reason = (
                    reasons[0] if len(reasons) == 1 else "epoch_batch_targets:" + "|".join(reasons)
                )
                event = DecisionDependencyEvent(
                    event_id=(f"{batch_id}:{_DecisionValidityStateStore.make_key(packet_ref)}"),
                    dedupe_key=(f"{batch_id}:{_DecisionValidityStateStore.make_key(packet_ref)}"),
                    trigger_type=DecisionTriggerType.HISTORICAL_SEMANTIC_REVISION,
                    status=status,
                    reason=reason,
                    dependency_keys=[row.dependency_key for row in packet_targets],
                    source_ref=str(receipt.transition_artifact_ref.artifact_id),
                    payload={
                        "epoch_batch_id": batch_id,
                        "requested_query_context_ref": requested_query_context_ref,
                        "dependency_denominator_ref": receipt.dependency_denominator_ref,
                        "adjudication_denominator_ref": receipt.adjudication_denominator_ref,
                        "target_dispositions": [
                            row.model_dump(mode="json") for row in packet_targets
                        ],
                    },
                )
                self._apply_event_to_packet(packet_ref=packet_ref, event=event)
                applied.append(packet_ref)
                pending = pending.model_copy(update={"applied_packet_refs": tuple(applied)})
                self._state.save_epoch_pending(pending)

            affected_packet_refs = tuple(dict.fromkeys(row.packet_ref for row in pending.targets))
            completion = EpochValidityBatchCompletionStatement(
                batch_id=batch_id,
                transition_artifact_ref=receipt.transition_artifact_ref,
                transition_content_hash=receipt.transition_content_hash,
                requested_query_context_ref=receipt.requested_query_context_ref,
                dependency_denominator_ref=receipt.dependency_denominator_ref,
                adjudication_denominator_ref=receipt.adjudication_denominator_ref,
                verifier_provenance_ref=receipt.verifier_provenance_ref,
                affected_packet_refs=affected_packet_refs,
                targets=pending.targets,
                predicate_class="independently_reconciled",
            )
            completion_ref = self._store.put_json(
                completion.model_dump(mode="json"),
                ArtifactWriteOptions(
                    kind="scientist.decision_validity_epoch_batch_completion",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name=("polisyos.decision-validity.epoch-batch-completion.v1"),
                        version="1.0",
                    ),
                    inputs=[
                        InputRef(
                            artifact_id=transition_artifact_ref.artifact_id,
                            role="epoch_transition",
                        )
                    ],
                ),
            )
            result = EpochValidityBatchReceipt(
                batch_id=batch_id,
                transition_artifact_ref=receipt.transition_artifact_ref,
                transition_content_hash=receipt.transition_content_hash,
                requested_query_context_ref=receipt.requested_query_context_ref,
                dependency_denominator_ref=receipt.dependency_denominator_ref,
                adjudication_denominator_ref=receipt.adjudication_denominator_ref,
                verifier_provenance_ref=receipt.verifier_provenance_ref,
                completion_receipt_ref=completion_ref,
                affected_packet_refs=affected_packet_refs,
                targets=pending.targets,
            )
            result_ref = self._store.put_json(
                result.model_dump(mode="json"),
                ArtifactWriteOptions(
                    kind="scientist.decision_validity_epoch_batch_receipt",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.decision-validity.epoch-batch-receipt.v1",
                        version="1.0",
                    ),
                    inputs=[
                        InputRef(
                            artifact_id=transition_artifact_ref.artifact_id,
                            role="epoch_transition",
                        ),
                        InputRef(
                            artifact_id=completion_ref.artifact_id,
                            role="completion_statement",
                        ),
                    ],
                ),
            )
            result_raw = self._store.get_bytes(result_ref.artifact_id)
            result_hash = "sha256:" + hashlib.sha256(result_raw).hexdigest()
            self._state.save_epoch_receipt(
                result,
                receipt_artifact_ref=result_ref,
                receipt_content_hash=result_hash,
            )
            self._state.clear_epoch_pending(batch_id)
            return result

    @staticmethod
    def _require_pending_matches_verification(
        *,
        pending: EpochValidityPendingBatch,
        receipt: EpochTransitionVerificationReceipt,
    ) -> None:
        expected = (
            receipt.transition_artifact_ref,
            receipt.transition_content_hash,
            receipt.requested_query_context_ref,
            receipt.verifier_provenance_ref,
            receipt.dependency_denominator_ref,
            receipt.adjudication_denominator_ref,
            receipt.targets,
        )
        observed = (
            pending.transition_artifact_ref,
            pending.transition_content_hash,
            pending.requested_query_context_ref,
            pending.verifier_provenance_ref,
            pending.dependency_denominator_ref,
            pending.adjudication_denominator_ref,
            pending.targets,
        )
        if observed != expected:
            raise ValueError("epoch_pending_verification_binding_mismatch")

    @staticmethod
    def _require_completed_matches_verification(
        *,
        completed: EpochValidityBatchReceipt,
        receipt: EpochTransitionVerificationReceipt,
    ) -> None:
        expected_packets = tuple(dict.fromkeys(row.packet_ref for row in receipt.targets))
        if (
            completed.transition_artifact_ref != receipt.transition_artifact_ref
            or completed.transition_content_hash != receipt.transition_content_hash
            or completed.requested_query_context_ref != receipt.requested_query_context_ref
            or completed.dependency_denominator_ref != receipt.dependency_denominator_ref
            or completed.adjudication_denominator_ref != receipt.adjudication_denominator_ref
            or completed.verifier_provenance_ref != receipt.verifier_provenance_ref
            or completed.affected_packet_refs != expected_packets
            or completed.targets != receipt.targets
        ):
            raise ValueError("epoch_completed_verification_binding_mismatch")

    def _load_completed_epoch_receipt(self, batch_id: str) -> EpochValidityBatchReceipt | None:
        evidence = self._state.load_epoch_receipt_evidence(batch_id)
        if evidence is None:
            return None
        try:
            report = self._store.verify(evidence.receipt_artifact_ref.artifact_id)
            raw = self._store.get_bytes(evidence.receipt_artifact_ref.artifact_id)
            parsed = EpochValidityBatchReceipt.model_validate(from_canonical_bytes(raw))
            completion_report = self._store.verify(parsed.completion_receipt_ref.artifact_id)
            completion_raw = self._store.get_bytes(parsed.completion_receipt_ref.artifact_id)
            completion = EpochValidityBatchCompletionStatement.model_validate(
                from_canonical_bytes(completion_raw)
            )
            transition_report = self._store.verify(parsed.transition_artifact_ref.artifact_id)
            transition_raw = self._store.get_bytes(parsed.transition_artifact_ref.artifact_id)
        except _DECISION_VALIDITY_ARTIFACT_LOAD_ERRORS as exc:
            raise RuntimeError("decision_validity_epoch_receipt_unresolved") from exc
        observed_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        observed_transition_hash = "sha256:" + hashlib.sha256(transition_raw).hexdigest()
        if (
            not report.ok
            or not completion_report.ok
            or not transition_report.ok
            or observed_hash != evidence.receipt_content_hash
            or observed_transition_hash != parsed.transition_content_hash
            or parsed != evidence.receipt
            or completion.batch_id != parsed.batch_id
            or completion.transition_artifact_ref != parsed.transition_artifact_ref
            or completion.transition_content_hash != parsed.transition_content_hash
            or completion.requested_query_context_ref != parsed.requested_query_context_ref
            or completion.dependency_denominator_ref != parsed.dependency_denominator_ref
            or completion.adjudication_denominator_ref != parsed.adjudication_denominator_ref
            or completion.verifier_provenance_ref != parsed.verifier_provenance_ref
            or completion.affected_packet_refs != parsed.affected_packet_refs
            or completion.targets != parsed.targets
        ):
            raise RuntimeError("decision_validity_epoch_receipt_unresolved")
        return parsed

    def resolve_completed_epoch_batch_evidence(
        self,
        *,
        batch_receipt_ref: ArtifactRef,
    ) -> PersistedEpochValidityBatchEvidence:
        """Resolve exact completed bytes by ref for the Claim owner bridge."""

        for item in sorted(self._state._epoch_receipts.glob("*.json")):
            state = self._state._load_model_strict(
                item,
                _PersistedEpochBatchReceiptState,
            )
            if state is None or state.receipt_artifact_ref != batch_receipt_ref:
                continue
            parsed = self._load_completed_epoch_receipt(state.receipt.batch_id)
            if parsed is None:
                break
            raw = self._store.get_bytes(batch_receipt_ref.artifact_id)
            return PersistedEpochValidityBatchEvidence(
                batch_receipt_ref=batch_receipt_ref,
                batch_receipt_content_hash=state.receipt_content_hash,
                receipt_bytes=raw,
                receipt=parsed,
            )
        raise ValueError("decision_validity_epoch_receipt_unresolved")

    def resolve_completed_epoch_batch_evidence_by_id(
        self,
        *,
        batch_id: str,
    ) -> PersistedEpochValidityBatchEvidence:
        """Resolve the exact artifact handle produced for one admitted batch."""

        state = self._state.load_epoch_receipt_evidence(batch_id)
        if state is None:
            raise ValueError("decision_validity_epoch_receipt_unresolved")
        return self.resolve_completed_epoch_batch_evidence(
            batch_receipt_ref=state.receipt_artifact_ref
        )

    @_owner_transactional
    def enumerate_completed_epoch_batch_evidence(
        self,
    ) -> tuple[PersistedEpochValidityBatchEvidence, ...]:
        """Walk the complete owner receipt index under its transaction lock."""

        evidence: list[PersistedEpochValidityBatchEvidence] = []
        for item in sorted(self._state._epoch_receipts.glob("*.json")):
            state = self._state._load_model_strict(
                item,
                _PersistedEpochBatchReceiptState,
            )
            if state is None:
                raise ValueError("decision_validity_epoch_receipt_index_unresolved")
            parsed = self._load_completed_epoch_receipt(state.receipt.batch_id)
            if parsed is None or parsed != state.receipt:
                raise ValueError("decision_validity_epoch_receipt_index_unresolved")
            raw = self._store.get_bytes(state.receipt_artifact_ref.artifact_id)
            evidence.append(
                PersistedEpochValidityBatchEvidence(
                    batch_receipt_ref=state.receipt_artifact_ref,
                    batch_receipt_content_hash=state.receipt_content_hash,
                    receipt_bytes=raw,
                    receipt=parsed,
                )
            )
        return tuple(evidence)

    def _validate_epoch_transition_receipt(
        self,
        *,
        receipt: EpochTransitionVerificationReceipt,
        transition_artifact_ref: ArtifactRef,
        requested_query_context_ref: str,
    ) -> None:
        if receipt.predicate_class != "independently_reconciled":
            raise ValueError("verifier_provenance_untrusted")
        expected_provenance = getattr(
            self._epoch_transition_verifier,
            "verifier_provenance_ref",
            None,
        )
        if expected_provenance is None or receipt.verifier_provenance_ref != expected_provenance:
            raise ValueError("verifier_provenance_untrusted")
        try:
            self._store.get_bytes(expected_provenance.artifact_id)
            provenance_report = self._store.verify(expected_provenance.artifact_id)
            provenance_manifest = self._store.get_manifest(expected_provenance.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("verifier_provenance_untrusted") from exc
        if (
            not provenance_report.ok
            or expected_provenance.kind != "chronology.epoch_transition_verifier"
            or provenance_manifest.kind != "chronology.epoch_transition_verifier"
        ):
            raise ValueError("verifier_provenance_untrusted")
        if receipt.transition_artifact_ref != transition_artifact_ref:
            raise ValueError("ref_unresolved")
        if receipt.requested_query_context_ref != requested_query_context_ref:
            raise ValueError("query_context_mismatch")
        if receipt.authority_purpose != "decision_validity_epoch_transition":
            raise ValueError("authority_purpose_mismatch")
        try:
            raw = self._store.get_bytes(transition_artifact_ref.artifact_id)
            report = self._store.verify(transition_artifact_ref.artifact_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("ref_unresolved") from exc
        observed_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        if not report.ok or receipt.transition_content_hash != observed_hash:
            raise ValueError("content_hash_mismatch")

    def _resolve_epoch_target_denominator(
        self,
        *,
        dependency_keys: tuple[str, ...],
    ) -> tuple[set[tuple[str, str, str]], str]:
        rows: list[dict[str, object]] = []
        targets: set[tuple[str, str, str]] = set()
        for key in sorted(dependency_keys):
            owner = self._state.load_dependency(key)
            if owner is None or owner.dependency_kind != DecisionDependencyKind.SEMANTIC_EPOCH:
                raise ValueError("dependency_denominator_unresolved")
            rows.append(
                {
                    "dependency_key": owner.dependency_key,
                    "dependency_kind": owner.dependency_kind.value,
                    "artifact_id": owner.artifact_id,
                    "packet_refs": sorted(owner.packet_refs),
                    "lineage_keys": sorted(owner.lineage_keys),
                }
            )
            for packet_ref in owner.packet_refs:
                packet = self._state.load_packet(packet_ref)
                if packet is None:
                    raise ValueError("dependency_denominator_unresolved")
                targets.add((packet_ref, key, packet.decision_lineage_key))
        raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return targets, "sha256:" + hashlib.sha256(raw).hexdigest()

    @_owner_transactional
    def register_decision_packet(
        self,
        *,
        packet_ref: str,
        envelope: DecisionValidityEnvelope,
        baseline: DecisionValidityEvaluation,
        monitoring_contract_ref: str | None = None,
    ) -> DecisionValidityEvaluation:
        dependency_keys = envelope.dependency_keys()
        head = self._state.load_lineage(envelope.decision_lineage_key)
        supersedes_ref = head.head_packet_ref if head is not None else None

        evaluation = baseline.model_copy(
            update={
                "decision_packet_ref": packet_ref,
                "decision_lineage_key": envelope.decision_lineage_key,
                "dependency_keys": dependency_keys,
                "evaluated_at": utc_now(),
                "supersedes_decision_ref": supersedes_ref,
                "superseded_by_ref": None,
            }
        )
        persisted = self._persist_evaluation(
            packet_ref=packet_ref,
            evaluation=evaluation,
            sticky_triggers=[],
            monitoring_contract_ref=monitoring_contract_ref,
        )
        self._register_dependencies(
            packet_ref=packet_ref,
            decision_lineage_key=envelope.decision_lineage_key,
            dependencies=tuple(
                dependency
                for section in (
                    envelope.normative_basis,
                    envelope.data_basis,
                    envelope.knowledge_basis,
                    envelope.transportability_basis,
                )
                for dependency in section.dependencies
            ),
        )
        packet_state = self._state.load_packet(packet_ref)
        self._state.save_lineage(
            _DecisionLineageState(
                decision_lineage_key=envelope.decision_lineage_key,
                head_packet_ref=packet_ref,
                evaluation_ref=packet_state.evaluation_ref if packet_state is not None else None,
                updated_at=utc_now(),
            )
        )
        if supersedes_ref and supersedes_ref != packet_ref:
            self._mark_superseded(
                packet_ref=supersedes_ref,
                superseded_by_ref=packet_ref,
                lineage_key=envelope.decision_lineage_key,
            )
        if monitoring_contract_ref:
            self._schedule_monitoring_job(
                packet_ref=packet_ref,
                decision_lineage_key=envelope.decision_lineage_key,
                monitoring_contract_ref=monitoring_contract_ref,
            )
        return persisted

    @_owner_transactional
    def ensure_evaluation(
        self,
        packet_ref: str,
        *,
        packet_payload: dict[str, Any] | None = None,
        force: bool = False,
    ) -> DecisionValidityEvaluation:
        current_state = self._state.load_packet(packet_ref)
        if (
            not force
            and current_state is not None
            and current_state.evaluation_ref
            and current_state.last_checked_at is not None
        ):
            age = utc_now() - current_state.last_checked_at
            if age <= timedelta(seconds=self._ttl):
                loaded = self._load_evaluation(current_state.evaluation_ref)
                if loaded is not None:
                    return self._overlay_epoch_pending(loaded)

        payload = (
            packet_payload if packet_payload is not None else self._load_packet_payload(packet_ref)
        )
        evaluation = self._compute_evaluation(
            packet_ref=packet_ref,
            packet_payload=payload,
            current_state=current_state,
        )
        persisted = self._persist_evaluation(
            packet_ref=packet_ref,
            evaluation=evaluation,
            sticky_triggers=list(current_state.sticky_triggers) if current_state else [],
        )
        return self._overlay_epoch_pending(persisted)

    def read_current_projection(self, packet_ref: str) -> DecisionValidityEvaluation:
        """Read current owner state plus a restart-safe pending-batch overlay."""

        state = self._state.load_packet(packet_ref)
        if state is not None and state.evaluation_ref is not None:
            loaded = self._load_evaluation(state.evaluation_ref)
            if loaded is not None:
                return self._overlay_epoch_pending(loaded)
        return self.ensure_evaluation(packet_ref)

    def _overlay_epoch_pending(
        self,
        evaluation: DecisionValidityEvaluation,
    ) -> DecisionValidityEvaluation:
        pending = tuple(
            batch
            for batch in self._state.list_epoch_pending()
            if any(target.packet_ref == evaluation.decision_packet_ref for target in batch.targets)
        )
        if not pending:
            return evaluation
        status = _max_status(evaluation.status, DecisionValidityStatus.STALE)
        reasons = _dedupe_strings(
            [
                *evaluation.reasons,
                *(f"epoch_validity_batch_pending:{batch.batch_id}" for batch in pending),
            ]
        )
        return evaluation.model_copy(
            update={
                "status": status,
                "reasons": reasons,
                "review_required": _is_review_required_status(status),
                "recommended_action": _recommended_action(status),
            }
        )

    def get_evaluation(
        self,
        packet_ref: str,
        *,
        packet_payload: dict[str, Any] | None = None,
        force: bool = False,
    ) -> tuple[DecisionValidityEvaluation, str | None]:
        evaluation = self.ensure_evaluation(
            packet_ref,
            packet_payload=packet_payload,
            force=force,
        )
        state = self._state.load_packet(packet_ref)
        return evaluation, (state.evaluation_ref if state is not None else None)

    def get_summary(
        self,
        packet_ref: str,
        *,
        packet_payload: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        evaluation, evaluation_ref = self.get_evaluation(
            packet_ref,
            packet_payload=packet_payload,
            force=force,
        )
        return {
            "status": evaluation.status.value,
            "lifecycle_status": evaluation.status.value,
            "checked_at": evaluation.evaluated_at.isoformat(),
            "reasons": list(evaluation.reasons),
            "triggers": [item.model_dump(mode="json") for item in evaluation.triggers],
            "review_required": bool(evaluation.review_required),
            "supersedes_decision_ref": (
                {"artifact_id": evaluation.supersedes_decision_ref}
                if evaluation.supersedes_decision_ref
                else None
            ),
            "superseded_by_ref": (
                {"artifact_id": evaluation.superseded_by_ref}
                if evaluation.superseded_by_ref
                else None
            ),
            "evaluation_ref": {"artifact_id": evaluation_ref} if evaluation_ref else None,
            "decision_lineage_key": evaluation.decision_lineage_key,
            "recommended_action": evaluation.recommended_action,
            "lifecycle": self._lifecycle_summary(packet_ref),
        }

    def mark_dependency_trigger(
        self,
        *,
        dependency_key: str,
        trigger: DecisionTriggerRecord,
    ) -> list[DecisionValidityEvaluation]:
        event = DecisionDependencyEvent(
            event_id=uuid.uuid4().hex,
            dedupe_key=_build_event_dedupe_key(
                trigger=trigger,
                dependency_keys=[dependency_key],
            ),
            trigger_type=trigger.trigger_type,
            status=trigger.status,
            reason=trigger.reason,
            dependency_keys=[dependency_key],
            source_ref=trigger.source_ref,
            payload=dict(trigger.details),
        )
        return self.record_dependency_event(event=event)

    @_owner_transactional
    def record_dependency_event(
        self,
        *,
        event: DecisionDependencyEvent,
    ) -> list[DecisionValidityEvaluation]:
        owner_rows = tuple(self._state.load_dependency(key) for key in event.dependency_keys)
        if any(
            row is not None and row.dependency_kind == DecisionDependencyKind.SEMANTIC_EPOCH
            for row in owner_rows
        ):
            raise ValueError("semantic_epoch_dependency_requires_owner_batch")
        if self._state.load_dedupe_event_id(event.dedupe_key):
            cached_evaluations: list[DecisionValidityEvaluation] = []
            for dependency_key in event.dependency_keys:
                dependency = self._state.load_dependency(dependency_key)
                if dependency is None:
                    continue
                for packet_ref in dependency.packet_refs:
                    cached_evaluations.append(self.ensure_evaluation(packet_ref))
            return cached_evaluations

        self._state.save_dedupe_event_id(event.dedupe_key, event.event_id)
        if event.trigger_type == DecisionTriggerType.CONTEXT_PROFILE_DRIFT:
            get_operational_monitor().record_alert(
                alert_type="drift",
                severity="warn",
                details={
                    "dependency_keys": list(event.dependency_keys),
                    "event_id": event.event_id,
                },
            )
        packet_refs: list[str] = []
        for dependency_key in event.dependency_keys:
            dependency = self._state.load_dependency(dependency_key)
            if dependency is None:
                continue
            for packet_ref in dependency.packet_refs:
                if packet_ref not in packet_refs:
                    packet_refs.append(packet_ref)
        evaluations: list[DecisionValidityEvaluation] = []
        for packet_ref in packet_refs:
            evaluations.append(self._apply_event_to_packet(packet_ref=packet_ref, event=event))
        return evaluations

    @_owner_transactional
    def mark_packet_trigger(
        self,
        *,
        packet_ref: str,
        trigger: DecisionTriggerRecord,
    ) -> DecisionValidityEvaluation:
        state = self._state.load_packet(packet_ref)
        dependency_keys = (
            [trigger.dependency_key]
            if trigger.dependency_key
            else list(state.dependency_keys)
            if state is not None
            else []
        )
        event = DecisionDependencyEvent(
            event_id=uuid.uuid4().hex,
            dedupe_key=_build_event_dedupe_key(
                trigger=trigger,
                dependency_keys=dependency_keys,
                packet_ref=packet_ref,
            ),
            trigger_type=trigger.trigger_type,
            status=trigger.status,
            reason=trigger.reason,
            dependency_keys=dependency_keys,
            source_ref=trigger.source_ref,
            payload=dict(trigger.details),
        )
        if self._state.load_dedupe_event_id(event.dedupe_key):
            return self.ensure_evaluation(packet_ref)
        self._state.save_dedupe_event_id(event.dedupe_key, event.event_id)
        return self._apply_event_to_packet(packet_ref=packet_ref, event=event)

    @_owner_transactional
    def backfill_packet(self, packet_ref: str) -> DecisionValidityEvaluation:
        payload = self._load_packet_payload(packet_ref)
        evaluation = self.ensure_evaluation(packet_ref, packet_payload=payload, force=True)
        if _load_envelope(payload) is None:
            trigger = DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.LEGACY_PACKET,
                status=DecisionValidityStatus.WARNING,
                reason="legacy_packet_missing_validity_envelope",
            )
            evaluation = self.mark_packet_trigger(packet_ref=packet_ref, trigger=trigger)
        return evaluation

    def _apply_event_to_packet(
        self,
        *,
        packet_ref: str,
        event: DecisionDependencyEvent,
    ) -> DecisionValidityEvaluation:
        state = self._state.load_packet(packet_ref)
        if state is None:
            self.ensure_evaluation(packet_ref)
            state = self._state.load_packet(packet_ref)
        if state is None:
            payload = self._load_packet_payload(packet_ref)
            envelope = _load_envelope(payload)
            lineage_key = envelope.decision_lineage_key if envelope is not None else packet_ref
            dependency_keys = envelope.dependency_keys() if envelope is not None else []
            state = _DecisionPacketState(
                packet_ref=packet_ref,
                decision_lineage_key=lineage_key,
                dependency_keys=dependency_keys,
            )
        previous_status = state.current_status
        previous_evaluation_ref = state.evaluation_ref
        sticky = list(state.sticky_triggers if state is not None else [])
        triggers = _trigger_records_from_event(event)
        sticky = _dedupe_trigger_records([*sticky, *triggers])
        lifecycle_events = _dedupe_events([*state.lifecycle_events, event])
        lifecycle_jobs = list(state.lifecycle_jobs)
        job_key = hashlib.sha256(
            f"{packet_ref}\0{event.event_id}\0evaluation".encode()
        ).hexdigest()[:24]
        lifecycle_jobs.append(
            DecisionLifecycleJob(
                job_id=f"decision_eval_{job_key}",
                job_kind="evaluation",
                packet_ref=packet_ref,
                decision_lineage_key=state.decision_lineage_key,
                state="completed",
                reason=event.reason,
                scheduled_for=event.occurred_at,
                trigger_event_id=event.event_id,
                completed_at=utc_now(),
                payload={"dependency_keys": list(event.dependency_keys)},
            )
        )
        state = state.model_copy(
            update={
                "sticky_triggers": sticky,
                "lifecycle_events": lifecycle_events,
                "lifecycle_jobs": _dedupe_jobs(lifecycle_jobs),
            }
        )
        self._state.save_packet(state)
        evaluation = self.ensure_evaluation(packet_ref, force=True)
        refreshed_state = self._state.load_packet(packet_ref)
        self._record_transition(
            packet_ref=packet_ref,
            decision_lineage_key=evaluation.decision_lineage_key,
            previous_status=previous_status,
            current_status=evaluation.status,
            reason=event.reason,
            event_id=event.event_id,
            review_required=evaluation.review_required,
            evaluation_ref=(
                refreshed_state.evaluation_ref
                if refreshed_state is not None
                else previous_evaluation_ref
            ),
        )
        return evaluation

    def _mark_superseded(
        self,
        *,
        packet_ref: str,
        superseded_by_ref: str,
        lineage_key: str,
    ) -> DecisionValidityEvaluation:
        current = self.ensure_evaluation(packet_ref)
        trigger = DecisionTriggerRecord(
            trigger_type=DecisionTriggerType.SUPERSEDED,
            status=DecisionValidityStatus.SUPERSEDED,
            reason=f"superseded_by:{superseded_by_ref}",
            source_ref=superseded_by_ref,
            details={"superseded_by_ref": superseded_by_ref},
        )
        updated = current.model_copy(
            update={
                "status": DecisionValidityStatus.SUPERSEDED,
                "evaluated_at": utc_now(),
                "reasons": _dedupe_strings([*current.reasons, trigger.reason]),
                "triggers": _dedupe_trigger_records([*current.triggers, trigger]),
                "review_required": False,
                "recommended_action": _recommended_action(DecisionValidityStatus.SUPERSEDED),
                "superseded_by_ref": superseded_by_ref,
                "decision_lineage_key": lineage_key,
            }
        )
        state = self._state.load_packet(packet_ref)
        sticky = list(state.sticky_triggers) if state is not None else []
        return self._persist_evaluation(
            packet_ref=packet_ref,
            evaluation=updated,
            sticky_triggers=sticky,
        )

    def _persist_evaluation(
        self,
        *,
        packet_ref: str,
        evaluation: DecisionValidityEvaluation,
        sticky_triggers: list[DecisionTriggerRecord],
        monitoring_contract_ref: str | None = None,
    ) -> DecisionValidityEvaluation:
        packet_artifact_id = ArtifactID.model_validate(packet_ref)
        evaluation_ref = self._store.put_json(
            evaluation.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="scientist.decision_validity_evaluation",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.DecisionValidityEvaluation",
                    version="1.0",
                ),
                inputs=[InputRef(artifact_id=packet_artifact_id, role="decision_packet")],
            ),
        )
        state = self._state.load_packet(packet_ref)
        dependency_keys = list(evaluation.dependency_keys)
        if state is not None and not dependency_keys:
            dependency_keys = list(state.dependency_keys)
        packet_state = _DecisionPacketState(
            packet_ref=packet_ref,
            decision_lineage_key=evaluation.decision_lineage_key,
            current_status=evaluation.status,
            last_checked_at=evaluation.evaluated_at,
            evaluation_ref=str(evaluation_ref.artifact_id),
            reasons=list(evaluation.reasons),
            active_triggers=list(evaluation.triggers),
            sticky_triggers=sticky_triggers,
            dependency_keys=dependency_keys,
            review_required=evaluation.review_required,
            supersedes_decision_ref=evaluation.supersedes_decision_ref,
            superseded_by_ref=evaluation.superseded_by_ref,
            monitoring_contract_ref=(
                monitoring_contract_ref
                if monitoring_contract_ref is not None
                else (state.monitoring_contract_ref if state is not None else None)
            ),
            latest_monitoring_report_ref=(
                state.latest_monitoring_report_ref if state is not None else None
            ),
            latest_compare_report_ref=(
                state.latest_compare_report_ref if state is not None else None
            ),
            latest_reissue_plan_ref=(state.latest_reissue_plan_ref if state is not None else None),
            lifecycle_events=list(state.lifecycle_events) if state is not None else [],
            transition_history=list(state.transition_history) if state is not None else [],
            lifecycle_jobs=list(state.lifecycle_jobs) if state is not None else [],
            last_transition_at=state.last_transition_at if state is not None else None,
        )
        self._state.save_packet(packet_state)
        return evaluation

    @_owner_transactional
    def update_feedback_refs(
        self,
        packet_ref: str,
        *,
        monitoring_contract_ref: str | None = None,
        monitoring_report_ref: str | None = None,
        compare_report_ref: str | None = None,
        reissue_plan_ref: str | None = None,
    ) -> None:
        state = self._state.load_packet(packet_ref)
        if state is None:
            self.ensure_evaluation(packet_ref)
            state = self._state.load_packet(packet_ref)
        if state is None:
            return
        self._state.save_packet(
            state.model_copy(
                update={
                    "monitoring_contract_ref": (
                        monitoring_contract_ref
                        if monitoring_contract_ref is not None
                        else state.monitoring_contract_ref
                    ),
                    "latest_monitoring_report_ref": (
                        monitoring_report_ref
                        if monitoring_report_ref is not None
                        else state.latest_monitoring_report_ref
                    ),
                    "latest_compare_report_ref": (
                        compare_report_ref
                        if compare_report_ref is not None
                        else state.latest_compare_report_ref
                    ),
                    "latest_reissue_plan_ref": (
                        reissue_plan_ref
                        if reissue_plan_ref is not None
                        else state.latest_reissue_plan_ref
                    ),
                    "lifecycle_jobs": _complete_monitoring_jobs(
                        state.lifecycle_jobs,
                        monitoring_contract_ref=monitoring_contract_ref,
                        monitoring_report_ref=monitoring_report_ref,
                    ),
                }
            )
        )

    def get_feedback_refs(self, packet_ref: str) -> dict[str, str | None]:
        state = self._state.load_packet(packet_ref)
        if state is None:
            self.ensure_evaluation(packet_ref)
            state = self._state.load_packet(packet_ref)
        if state is None:
            return {
                "monitoring_contract_ref": None,
                "latest_monitoring_report_ref": None,
                "latest_compare_report_ref": None,
                "latest_reissue_plan_ref": None,
            }
        return {
            "monitoring_contract_ref": state.monitoring_contract_ref,
            "latest_monitoring_report_ref": state.latest_monitoring_report_ref,
            "latest_compare_report_ref": state.latest_compare_report_ref,
            "latest_reissue_plan_ref": state.latest_reissue_plan_ref,
        }

    def _lifecycle_summary(self, packet_ref: str) -> dict[str, Any]:
        state = self._state.load_packet(packet_ref)
        if state is None:
            return {
                "events": [],
                "transitions": [],
                "pending_reviews": [],
                "scheduled_jobs": [],
                "reissue_candidates": [],
                "latest_transition_at": None,
            }
        pending_reviews = [
            {
                "event_id": event.event_id,
                "trigger_type": event.trigger_type.value,
                "reason": event.reason,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in state.lifecycle_events
            if _is_review_required_status(event.status)
        ]
        reissue_candidates = []
        if state.latest_reissue_plan_ref:
            reissue_candidates.append({"artifact_id": state.latest_reissue_plan_ref})
        return {
            "events": [item.model_dump(mode="json") for item in state.lifecycle_events[-20:]],
            "transitions": [
                item.model_dump(mode="json") for item in state.transition_history[-20:]
            ],
            "pending_reviews": pending_reviews,
            "scheduled_jobs": [item.model_dump(mode="json") for item in state.lifecycle_jobs[-20:]],
            "reissue_candidates": reissue_candidates,
            "latest_transition_at": _serialize_datetime(state.last_transition_at),
        }

    def _record_transition(
        self,
        *,
        packet_ref: str,
        decision_lineage_key: str,
        previous_status: DecisionValidityStatus | None,
        current_status: DecisionValidityStatus,
        reason: str,
        event_id: str | None,
        review_required: bool,
        evaluation_ref: str | None,
    ) -> None:
        state = self._state.load_packet(packet_ref)
        if state is None:
            return
        latest = state.transition_history[-1] if state.transition_history else None
        if (
            latest is not None
            and latest.current_status == current_status
            and latest.reason == reason
            and latest.triggered_by_event_id == event_id
        ):
            return
        occurred_at = utc_now()
        transition = DecisionValidityTransition(
            transition_id=f"decision_transition_{uuid.uuid4().hex[:12]}",
            packet_ref=packet_ref,
            decision_lineage_key=decision_lineage_key,
            previous_status=previous_status,
            current_status=current_status,
            reason=reason,
            occurred_at=occurred_at,
            triggered_by_event_id=event_id,
            evaluation_ref=evaluation_ref,
            review_required=review_required,
        )
        self._state.save_packet(
            state.model_copy(
                update={
                    "transition_history": [*state.transition_history, transition],
                    "last_transition_at": occurred_at,
                }
            )
        )

    def _schedule_monitoring_job(
        self,
        *,
        packet_ref: str,
        decision_lineage_key: str,
        monitoring_contract_ref: str,
    ) -> None:
        state = self._state.load_packet(packet_ref)
        if state is None:
            return
        contract = self._load_monitoring_contract(monitoring_contract_ref)
        if contract is None:
            return
        scheduled_for = _monitoring_due_at(contract)
        job = DecisionLifecycleJob(
            job_id=f"decision_monitor_{uuid.uuid4().hex[:12]}",
            job_kind="scheduled_monitoring",
            packet_ref=packet_ref,
            decision_lineage_key=decision_lineage_key,
            state="pending",
            reason="monitoring_contract_registered",
            scheduled_for=scheduled_for,
            monitoring_contract_ref=monitoring_contract_ref,
            payload={"metric_ids": [item.metric_id for item in contract.metrics]},
        )
        self._state.save_packet(
            state.model_copy(
                update={
                    "lifecycle_jobs": _dedupe_jobs([*state.lifecycle_jobs, job]),
                }
            )
        )

    def _compute_evaluation(
        self,
        *,
        packet_ref: str,
        packet_payload: dict[str, Any],
        current_state: _DecisionPacketState | None,
    ) -> DecisionValidityEvaluation:
        envelope = _load_envelope(packet_payload)
        baseline = _load_baseline(packet_payload)
        sticky_triggers = list(current_state.sticky_triggers) if current_state is not None else []
        superseded_by_ref = current_state.superseded_by_ref if current_state is not None else None

        if envelope is None:
            triggers = _dedupe_trigger_records(
                [
                    DecisionTriggerRecord(
                        trigger_type=DecisionTriggerType.LEGACY_PACKET,
                        status=DecisionValidityStatus.WARNING,
                        reason="legacy_packet_missing_validity_envelope",
                    ),
                    *sticky_triggers,
                ]
            )
            reasons = _dedupe_strings(
                [
                    "legacy_packet_missing_validity_envelope",
                    *(trigger.reason for trigger in sticky_triggers),
                ]
            )
            status = DecisionValidityStatus.WARNING
            for trigger in triggers:
                status = _max_status(status, trigger.status)
            if superseded_by_ref:
                status = DecisionValidityStatus.SUPERSEDED
                superseded_reason = f"superseded_by:{superseded_by_ref}"
                reasons = _dedupe_strings([*reasons, superseded_reason])
                triggers = _dedupe_trigger_records(
                    [
                        *triggers,
                        DecisionTriggerRecord(
                            trigger_type=DecisionTriggerType.SUPERSEDED,
                            status=DecisionValidityStatus.SUPERSEDED,
                            reason=superseded_reason,
                            source_ref=superseded_by_ref,
                            details={"superseded_by_ref": superseded_by_ref},
                        ),
                    ]
                )
            return DecisionValidityEvaluation(
                decision_packet_ref=packet_ref,
                decision_lineage_key=packet_ref,
                status=status,
                reasons=reasons,
                triggers=triggers,
                dependency_keys=[],
                recommended_action=_recommended_action(status),
                review_required=_is_review_required_status(status),
                superseded_by_ref=superseded_by_ref,
            )

        if baseline is None:
            baseline = DecisionValidityEvaluation(
                decision_packet_ref=packet_ref,
                decision_lineage_key=envelope.decision_lineage_key,
                status=DecisionValidityStatus.ACTIVE,
                dependency_keys=envelope.dependency_keys(),
                recommended_action=_recommended_action(DecisionValidityStatus.ACTIVE),
            )

        triggers = _dedupe_trigger_records([*baseline.triggers, *sticky_triggers])
        reasons = _dedupe_strings(
            [
                *baseline.reasons,
                *(trigger.reason for trigger in sticky_triggers),
            ]
        )
        status = baseline.status
        for trigger in triggers:
            status = _max_status(status, trigger.status)

        if superseded_by_ref:
            status = DecisionValidityStatus.SUPERSEDED
            superseded_reason = f"superseded_by:{superseded_by_ref}"
            reasons = _dedupe_strings([*reasons, superseded_reason])
            triggers = _dedupe_trigger_records(
                [
                    *triggers,
                    DecisionTriggerRecord(
                        trigger_type=DecisionTriggerType.SUPERSEDED,
                        status=DecisionValidityStatus.SUPERSEDED,
                        reason=superseded_reason,
                        source_ref=superseded_by_ref,
                        details={"superseded_by_ref": superseded_by_ref},
                    ),
                ]
            )

        return baseline.model_copy(
            update={
                "decision_packet_ref": packet_ref,
                "decision_lineage_key": envelope.decision_lineage_key,
                "evaluated_at": utc_now(),
                "status": status,
                "reasons": reasons,
                "triggers": triggers,
                "dependency_keys": (
                    baseline.dependency_keys
                    if baseline.dependency_keys
                    else envelope.dependency_keys()
                ),
                "review_required": _is_review_required_status(status),
                "recommended_action": _recommended_action(status),
                "supersedes_decision_ref": (
                    current_state.supersedes_decision_ref if current_state is not None else None
                ),
                "superseded_by_ref": superseded_by_ref,
            }
        )

    def _register_dependencies(
        self,
        *,
        packet_ref: str,
        decision_lineage_key: str,
        dependencies: tuple[object, ...],
    ) -> None:
        for dependency in dependencies:
            dependency_key = str(dependency.key)
            dependency_kind = DecisionDependencyKind(dependency.kind)
            artifact_id = getattr(dependency, "artifact_id", None)
            dependency_state = self._state.load_dependency(dependency_key)
            if dependency_state is None:
                dependency_state = _DecisionDependencyIndex(
                    dependency_key=dependency_key,
                    dependency_kind=dependency_kind,
                    artifact_id=artifact_id,
                )
            elif (
                dependency_state.dependency_kind != dependency_kind
                or dependency_state.artifact_id != artifact_id
            ):
                raise ValueError("decision_dependency_owner_identity_mismatch")
            packet_refs = list(dependency_state.packet_refs)
            lineage_keys = list(dependency_state.lineage_keys)
            if packet_ref not in packet_refs:
                packet_refs.append(packet_ref)
            if decision_lineage_key not in lineage_keys:
                lineage_keys.append(decision_lineage_key)
            self._state.save_dependency(
                dependency_state.model_copy(
                    update={
                        "packet_refs": sorted(packet_refs),
                        "lineage_keys": sorted(lineage_keys),
                        "updated_at": utc_now(),
                    }
                )
            )

    def _load_packet_payload(self, packet_ref: str) -> dict[str, Any]:
        artifact_id = ArtifactID.model_validate(packet_ref)
        payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
        return payload if isinstance(payload, dict) else {}

    def _load_evaluation(self, evaluation_ref: str) -> DecisionValidityEvaluation | None:
        try:
            artifact_id = ArtifactID.model_validate(evaluation_ref)
            payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
        except _DECISION_VALIDITY_ARTIFACT_LOAD_ERRORS:
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return DecisionValidityEvaluation.model_validate(payload)
        except _DECISION_VALIDITY_MODEL_ERRORS:
            return None

    def _load_monitoring_contract(
        self,
        monitoring_contract_ref: str,
    ) -> DecisionMonitoringContract | None:
        try:
            artifact_id = ArtifactID.model_validate(monitoring_contract_ref)
            payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
        except _DECISION_VALIDITY_ARTIFACT_LOAD_ERRORS:
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return DecisionMonitoringContract.model_validate(payload)
        except _DECISION_VALIDITY_MODEL_ERRORS:
            return None


def _load_envelope(packet_payload: dict[str, Any]) -> DecisionValidityEnvelope | None:
    value = packet_payload.get("decision_validity_envelope")
    if not isinstance(value, dict):
        return None
    try:
        return DecisionValidityEnvelope.model_validate(value)
    except _DECISION_VALIDITY_MODEL_ERRORS:
        return None


def _load_baseline(packet_payload: dict[str, Any]) -> DecisionValidityEvaluation | None:
    value = packet_payload.get("decision_validity_baseline")
    if not isinstance(value, dict):
        return None
    try:
        return DecisionValidityEvaluation.model_validate(value)
    except _DECISION_VALIDITY_MODEL_ERRORS:
        return None


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _dedupe_trigger_records(
    values: list[DecisionTriggerRecord],
) -> list[DecisionTriggerRecord]:
    deduped: list[DecisionTriggerRecord] = []
    seen: set[tuple[str, str, str | None, str | None]] = set()
    for item in values:
        key = (
            item.trigger_type.value,
            item.reason,
            item.dependency_key,
            item.source_ref,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _dedupe_events(
    values: list[DecisionDependencyEvent],
) -> list[DecisionDependencyEvent]:
    deduped: list[DecisionDependencyEvent] = []
    seen: set[str] = set()
    for item in values:
        if item.event_id in seen:
            continue
        seen.add(item.event_id)
        deduped.append(item)
    return deduped


def _dedupe_jobs(
    values: list[DecisionLifecycleJob],
) -> list[DecisionLifecycleJob]:
    deduped: list[DecisionLifecycleJob] = []
    seen: set[tuple[str, str | None, str]] = set()
    for item in values:
        key = (item.packet_ref, item.trigger_event_id, item.job_kind)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _build_event_dedupe_key(
    *,
    trigger: DecisionTriggerRecord,
    dependency_keys: list[str],
    packet_ref: str | None = None,
) -> str:
    return str(
        content_hash(
            json.dumps(
                {
                    "trigger_type": trigger.trigger_type.value,
                    "status": trigger.status.value,
                    "reason": trigger.reason,
                    "dependency_keys": sorted(item for item in dependency_keys if item),
                    "source_ref": trigger.source_ref,
                    "packet_ref": packet_ref,
                    "details": trigger.details,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    )


def _epoch_batch_id(
    *,
    transition_artifact_ref: ArtifactRef,
    requested_query_context_ref: str,
) -> str:
    payload = json.dumps(
        {
            "transition_artifact_id": str(transition_artifact_ref.artifact_id),
            "transition_kind": transition_artifact_ref.kind,
            "requested_query_context_ref": requested_query_context_ref,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "epoch_batch_" + hashlib.sha256(payload).hexdigest()


def _trigger_records_from_event(
    event: DecisionDependencyEvent,
) -> list[DecisionTriggerRecord]:
    if event.dependency_keys:
        return [
            DecisionTriggerRecord(
                trigger_type=event.trigger_type,
                status=event.status,
                reason=event.reason,
                dependency_key=dependency_key,
                source_ref=event.source_ref,
                details=dict(event.payload),
            )
            for dependency_key in event.dependency_keys
        ]
    return [
        DecisionTriggerRecord(
            trigger_type=event.trigger_type,
            status=event.status,
            reason=event.reason,
            source_ref=event.source_ref,
            details=dict(event.payload),
        )
    ]


def _monitoring_due_at(contract: DecisionMonitoringContract) -> datetime:
    max_offset_days = 0
    for metric in contract.metrics:
        max_offset_days = max(
            max_offset_days,
            int(metric.window.end_offset_days) + int(metric.window.grace_days),
        )
    return cast("datetime", contract.anchor_at + timedelta(days=max_offset_days))


def _complete_monitoring_jobs(
    jobs: list[DecisionLifecycleJob],
    *,
    monitoring_contract_ref: str | None,
    monitoring_report_ref: str | None,
) -> list[DecisionLifecycleJob]:
    if monitoring_report_ref is None:
        return jobs
    completed_at = utc_now()
    updated: list[DecisionLifecycleJob] = []
    for job in jobs:
        if job.job_kind != "scheduled_monitoring":
            updated.append(job)
            continue
        if monitoring_contract_ref and job.monitoring_contract_ref != monitoring_contract_ref:
            updated.append(job)
            continue
        updated.append(
            job.model_copy(
                update={
                    "state": "completed",
                    "completed_at": completed_at,
                    "payload": {
                        **job.payload,
                        "monitoring_report_ref": monitoring_report_ref,
                    },
                }
            )
        )
    return updated


def _recommended_action(status: DecisionValidityStatus) -> str:
    if status == DecisionValidityStatus.ACTIVE:
        return "none"
    if status == DecisionValidityStatus.WARNING:
        return "monitor"
    if status == DecisionValidityStatus.STALE:
        return "refresh_decision"
    if status in {
        DecisionValidityStatus.REVIEW_REQUIRED,
        DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
    }:
        return "human_review"
    if status == DecisionValidityStatus.SUPERSEDED:
        return "review_superseded"
    if status == DecisionValidityStatus.REISSUED:
        return "record_reissue"
    if status == DecisionValidityStatus.WITHDRAWN:
        return "record_withdrawal"
    if status == DecisionValidityStatus.REVOKED:
        return "record_revocation"
    return "human_review"


def _max_status(
    left: DecisionValidityStatus,
    right: DecisionValidityStatus,
) -> DecisionValidityStatus:
    order = {
        DecisionValidityStatus.ACTIVE: 0,
        DecisionValidityStatus.WARNING: 1,
        DecisionValidityStatus.STALE: 2,
        DecisionValidityStatus.REVIEW_REQUIRED: 3,
        DecisionValidityStatus.REQUIRES_HUMAN_REVIEW: 3,
        DecisionValidityStatus.SUPERSEDED: 4,
        DecisionValidityStatus.REISSUED: 5,
        DecisionValidityStatus.REVOKED: 6,
        DecisionValidityStatus.WITHDRAWN: 7,
    }
    return right if order[right] > order[left] else left


def _is_review_required_status(status: DecisionValidityStatus) -> bool:
    return status in {
        DecisionValidityStatus.REVIEW_REQUIRED,
        DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
        DecisionValidityStatus.WITHDRAWN,
    }


__all__ = [
    "DecisionValidityService",
]
