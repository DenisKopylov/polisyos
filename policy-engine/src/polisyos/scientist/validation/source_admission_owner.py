"""Typed intake/read bridge for the existing validity owner's committed source state.

The neutral factory/producer ports are trusted composition seams, not candidate
validators. The default has no producer authority. C106 supplies the actual
appointed Runtime factory and live registered Fabric materialization capture.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import threading
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    read_core_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.decision_validity import (
    RegisteredMaterialization,
    SourceAdmissionCarrier,
    SourceAdmissionReceipt,
    SourceCurrentUseProjection,
    SourceRegistrationReceipt,
    source_admission_basis_digest,
)
from polisyos.core.contracts.fabric import (
    DataSnapshotOwnerBound,
    FabricBridgeDataSnapshotLineage,
    data_snapshot_manifest_inputs_match,
    data_snapshot_owner_input_requirements,
)
from polisyos.scientist.validation.source_admission_port import (
    SourceAdmissionAuthority,
    SourceIssuerCall,
    VerifiedRegisteredMaterialization,
    _read_registered_materialization_candidate,
    _require_registered_materialization,
    _require_source_admission_authority,
    _require_source_admission_call,
    _require_source_admission_scope,
)
from polisyos.scientist.validation.source_admission_state import (
    _digest,
    _SourceAdmissionStateStore,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from concurrent.futures import Future
    from contextlib import AbstractContextManager
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scientist.validation.decision_validity import DecisionValidityService


_ResultT = TypeVar("_ResultT")


class _SourceAcquisitionFence:
    """Retain a stripe while timed-out owner work may still be running."""

    def __init__(self, descriptor: int) -> None:
        self._descriptor = descriptor
        self._lock = threading.Lock()
        self._pending = 0
        self._finished = False
        self._closed = False

    def retain_until_complete(self, future: Future[Any]) -> None:
        with self._lock:
            if self._finished:
                raise ValueError("source_admission_acquisition_fence_finished")
            self._pending += 1
        future.add_done_callback(self._completed)

    def _completed(self, _future: Future[Any]) -> None:
        with self._lock:
            self._pending -= 1
            if self._finished and self._pending == 0:
                self._close_locked()

    def finish(self) -> None:
        with self._lock:
            self._finished = True
            if self._pending == 0:
                self._close_locked()

    def _close_locked(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                fcntl.flock(self._descriptor, fcntl.LOCK_UN)
            finally:
                os.close(self._descriptor)


_ACTIVE_SOURCE_ACQUISITION: ContextVar[_SourceAcquisitionFence | None] = ContextVar(
    "source_admission_acquisition_fence", default=None
)


def _retain_source_acquisition_until_complete(future: Future[Any]) -> None:
    """Defer stripe release when a timed-out owner operation is still live."""
    fence = _ACTIVE_SOURCE_ACQUISITION.get()
    if fence is not None:
        fence.retain_until_complete(future)


class _RegisteredSourceAdmissionOwner:
    """One composed quantity with the existing DecisionValidityService fence."""

    def __init__(
        self,
        store: ArtifactStore,
        base: Path,
        transaction: Callable[[], AbstractContextManager[object]],
        *,
        runtime_decision_owner: object | None = None,
        runtime_guarded_store: object | None = None,
    ) -> None:
        if (runtime_decision_owner is None) != (runtime_guarded_store is None):
            raise ValueError("registered_sql_runtime_owner_binding_invalid")
        self._runtime_decision_owner = runtime_decision_owner
        self._runtime_guarded_store = runtime_guarded_store
        self._runtime_issuer_verifier = None
        self._store = store
        self._cas_root = base.parent.resolve()
        self._acquisition_lock_dir = base / "source_acquisition_locks"
        self._state = _SourceAdmissionStateStore(base, transaction)

    def install_issuer_verifier(self, *, owner: object, verifier: object) -> None:
        """Install the Runtime factory's verifier once on this guarded owner."""
        if (
            owner is not self._runtime_decision_owner
            or self._runtime_guarded_store is None
            or verifier is None
            or self._runtime_issuer_verifier is not None
        ):
            raise ValueError("source_admission_issuer_installation_invalid")
        self._runtime_issuer_verifier = verifier

    def require_issuer_verifier(self, *, owner: object, verifier: object) -> None:
        """Reject a missing, foreign or replaced Runtime issuer pin."""
        if (
            owner is not self._runtime_decision_owner
            or self._runtime_guarded_store is None
            or verifier is None
            or self._runtime_issuer_verifier is not verifier
            or getattr(owner, "_registered_sql_issuer_verifier", None) is not verifier
        ):
            raise ValueError("source_admission_issuer_not_pinned")

    def _require_issuer_call(
        self, authority: SourceAdmissionAuthority, call: SourceIssuerCall
    ) -> Any:
        if self._runtime_decision_owner is None:
            # Preserve the bare C105 trusted-composition test seam.
            return _require_source_admission_authority(authority)
        return _require_source_admission_call(
            authority, owner=self._runtime_decision_owner, call=call
        )

    @staticmethod
    def _authority_payload(authority: SourceAdmissionAuthority) -> dict[str, str]:
        state = _require_source_admission_authority(authority)
        return {
            "issuer_key": state.issuer_key,
            "tenant_id": state.tenant_id,
            "cell_id": state.cell_id,
            "provider_id": state.provider_id,
        }

    def run_serialized_acquisition(
        self,
        authority: SourceAdmissionAuthority,
        *,
        event_id: str,
        action: Callable[[], _ResultT],
    ) -> _ResultT:
        """Serialize one event's retry window without creating source authority.

        This fixed set of lock stripes is coordination only, never a ledger.
        The action must still pass the normal owner admission and grant checks.
        Busy retries fail promptly and may recover the original event later.
        Lock order is acquisition stripe then the existing owner transaction;
        no source transition takes a stripe while holding that transaction.
        """
        authority_state = _require_source_admission_authority(authority)
        issuer_call = SourceIssuerCall(
            operation="acquire",
            event_id=event_id,
            expected_predecessor=(
                authority_state.initial_call.expected_predecessor
                if authority_state.initial_call is not None
                else None
            ),
        )
        self._require_issuer_call(authority, issuer_call)
        if (
            not isinstance(event_id, str)
            or not event_id
            or len(event_id) > 256
            or "admit" not in authority_state.permitted_operations
            or not callable(action)
        ):
            raise ValueError("source_admission_acquisition_lock_invalid")
        self._scoped_store(authority_state.tenant_id, authority_state.cell_id)
        directory = self._acquisition_lock_dir
        directory.mkdir(parents=True, exist_ok=True)
        if (
            directory.is_symlink()
            or directory.resolve().parent != self._state.root_path.parent.resolve()
        ):
            raise ValueError("source_admission_acquisition_lock_root_invalid")
        stripe = hashlib.sha256(event_id.encode("utf-8")).digest()[0] % 64
        path = directory / f"stripe-{stripe:02d}.lock"
        if not hasattr(os, "O_NOFOLLOW"):
            raise ValueError("source_admission_acquisition_lock_nofollow_unavailable")
        if _ACTIVE_SOURCE_ACQUISITION.get() is not None:
            raise ValueError("source_admission_acquisition_reentry_unsupported")
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("source_admission_acquisition_lock_not_regular")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("source_admission_acquisition_busy") from exc
        except BaseException:
            os.close(descriptor)
            raise
        fence = _SourceAcquisitionFence(descriptor)
        token = _ACTIVE_SOURCE_ACQUISITION.set(fence)
        try:
            if self._require_issuer_call(authority, issuer_call) != authority_state:
                raise ValueError("source_admission_authority_changed")
            return action()
        finally:
            _ACTIVE_SOURCE_ACQUISITION.reset(token)
            fence.finish()

    def _require_runtime_backend(self, backend: FileSystemCAS) -> None:
        """Check the exact local backend without handing it to the caller."""
        if (
            type(backend) is not FileSystemCAS
            or self._store is not backend
            or backend.root.resolve() != self._cas_root
        ):
            raise ValueError("source_admission_storage_profile_not_established")

    def _require_runtime_binding(
        self, backend: FileSystemCAS, *, decision_owner: object, guarded_store: object
    ) -> None:
        self._require_runtime_backend(backend)
        if (
            self._runtime_decision_owner is not decision_owner
            or self._runtime_guarded_store is not guarded_store
        ):
            raise ValueError("registered_sql_runtime_owner_binding_invalid")

    def _scoped_store(self, tenant_id: str | None, cell_id: str | None) -> FileSystemCAS:
        if (
            not isinstance(self._store, FileSystemCAS)
            or self._store.root.resolve() != self._cas_root
        ):
            raise ValueError("source_admission_storage_profile_not_established")
        # Reuse the actual Core selected-view ownership reader. Scope comes from
        # the verified issuer or immutable committed registration, never a new
        # consumer-supplied list/manifest ownership declaration.
        return (
            FileSystemCAS.for_tenant(self._store, tenant_id, cell_id) if tenant_id else self._store
        )

    def _verify_ref(
        self,
        ref: ArtifactRef,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
    ) -> dict[str, object]:
        # Never silently bind a mutable default selector on an authority read.
        checked = ArtifactRef.model_validate_json(ref.model_dump_json(), strict=True)
        if checked.manifest_profile_sha256 is None:
            raise ValueError("source_admission_selected_profile_required")
        reader = self._scoped_store(tenant_id, cell_id)
        manifest = reader.get_manifest(checked)
        if (manifest.artifact_id, manifest.kind, manifest.media_type) != (
            checked.artifact_id,
            checked.kind,
            checked.media_type,
        ) or artifact_manifest_profile_sha256(manifest) != checked.manifest_profile_sha256:
            raise ValueError("source_admission_reference_identity_mismatch")
        raw = reader.get_bytes(checked)
        if (
            type(raw) is not bytes
            or hashlib.sha256(raw).hexdigest() != checked.artifact_id.hex
            or len(raw) != manifest.byte_size
            or not reader.verify(checked).ok
        ):
            raise ValueError("source_admission_reference_content_mismatch")
        return {
            "ref": checked.model_dump(mode="json"),
            "raw_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "manifest_profile_sha256": artifact_manifest_profile_sha256(manifest),
        }

    def _verify_refs(
        self,
        refs: tuple[ArtifactRef, ...],
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
    ) -> list[dict[str, object]]:
        unique = {artifact_ref_identity_key(ref): ref for ref in refs}
        return [
            self._verify_ref(unique[key], tenant_id=tenant_id, cell_id=cell_id)
            for key in sorted(unique, key=lambda key: (*key[:3], key[3] or ""))
        ]

    def register(
        self,
        authority: SourceAdmissionAuthority,
        *,
        event_id: str,
        registration_key: str,
        effective_view_contract_ref: ArtifactRef,
        use_contract_ref: ArtifactRef,
    ) -> SourceRegistrationReceipt:
        authority_payload = self._authority_payload(authority)
        issuer_call = SourceIssuerCall(operation="genesis", event_id=event_id)
        self._require_issuer_call(authority, issuer_call)
        _require_source_admission_scope(
            _require_source_admission_authority(authority),
            operation="genesis",
            registration_key=registration_key,
            effective_view_contract_ref=effective_view_contract_ref,
            use_contract_ref=use_contract_ref,
        )
        if (
            not event_id
            or len(event_id) > 256
            or not registration_key
            or len(registration_key) > 256
        ):
            raise ValueError("source_admission_event_identity_invalid")
        reader = self._scoped_store(authority_payload["tenant_id"], authority_payload["cell_id"])
        verified = self._verify_refs(
            (effective_view_contract_ref, use_contract_ref),
            tenant_id=authority_payload["tenant_id"],
            cell_id=authority_payload["cell_id"],
        )
        for ref in (effective_view_contract_ref, use_contract_ref):
            schema = reader.get_manifest(ref).artifact_schema
            if schema is None or not schema.name.strip() or not schema.version.strip():
                raise ValueError("source_admission_versioned_contract_required")
        # Actual authority identity/config is rechecked after potentially slow CAS I/O.
        if self._authority_payload(authority) != authority_payload:
            raise ValueError("source_admission_authority_changed")

        def validate_origin() -> None:
            self._require_issuer_call(authority, issuer_call)

        return self._state.register(
            authority=authority_payload,
            event_id=event_id,
            registration_key=registration_key,
            view_ref=effective_view_contract_ref.model_dump(mode="json"),
            use_ref=use_contract_ref.model_dump(mode="json"),
            verified_refs=verified,
            validate_origin=validate_origin,
        )

    def _materialization_refs(
        self, materialization: RegisteredMaterialization
    ) -> tuple[ArtifactRef, ...]:
        snapshot_ref = materialization.snapshot_ref
        if (
            snapshot_ref.kind != DataSnapshotOwnerBound.ARTIFACT_KIND
            or snapshot_ref.media_type != DataSnapshotOwnerBound.ARTIFACT_MEDIA_TYPE
        ):
            raise ValueError("source_admission_snapshot_schema_unsupported")
        registration = materialization.registration
        reader = self._scoped_store(registration.tenant_id, registration.cell_id)
        self._verify_ref(
            snapshot_ref, tenant_id=registration.tenant_id, cell_id=registration.cell_id
        )
        manifest = reader.get_manifest(snapshot_ref)
        schema = manifest.artifact_schema
        if (
            schema is None
            or schema.name != DataSnapshotOwnerBound.ARTIFACT_SCHEMA_NAME
            or schema.version != DataSnapshotOwnerBound.ARTIFACT_SCHEMA_VERSION
        ):
            raise ValueError("source_admission_snapshot_schema_unsupported")
        value = read_core_json_artifact(reader, snapshot_ref).value
        snapshot = DataSnapshotOwnerBound.model_validate_json(
            json.dumps(value, sort_keys=True, separators=(",", ":")), strict=True
        )
        if not isinstance(snapshot.source_lineage, FabricBridgeDataSnapshotLineage):
            raise ValueError("source_admission_snapshot_owner_unsupported")
        actual = (
            snapshot.source_lineage.data_view_request_ref,
            snapshot.data_ref,
            snapshot.data_schema_ref,
            snapshot.quality_report_ref,
        )
        declared = (
            materialization.request_ref,
            materialization.payload_ref,
            materialization.schema_ref,
            materialization.quality_ref,
        )
        if any(
            left is None or artifact_ref_identity_key(left) != artifact_ref_identity_key(right)
            for left, right in zip(actual, declared, strict=True)
        ):
            raise ValueError("source_admission_snapshot_binding_mismatch")
        if not data_snapshot_manifest_inputs_match(
            snapshot, manifest.inputs, schema_version=schema.version
        ):
            raise ValueError("source_admission_snapshot_input_denominator_mismatch")
        # Derive all present schema-bound fields, including evidence and warnings,
        # from the actual owner contract, never from an authorial dependency list.
        requirements = data_snapshot_owner_input_requirements(snapshot)
        return (
            snapshot_ref,
            materialization.producer_capture_ref,
            materialization.registration.effective_view_contract_ref,
            materialization.registration.use_contract_ref,
            *(ref for ref, _ in requirements),
        )

    def _require_live_materialization(
        self, proof: VerifiedRegisteredMaterialization
    ) -> tuple[object, RegisteredMaterialization]:
        if self._runtime_decision_owner is None:
            return _require_registered_materialization(proof)
        from polisyos.scientist.adapters.registered_sql_admission import (
            _require_registered_sql_producer_capture,
        )

        return _require_registered_sql_producer_capture(
            proof,
            owner=cast("DecisionValidityService", self._runtime_decision_owner),
            store=cast("ArtifactStore", self._runtime_guarded_store),
        )

    def admit(
        self,
        proof: VerifiedRegisteredMaterialization,
        *,
        event_id: str,
        expected_predecessor: str,
    ) -> SourceAdmissionReceipt:
        _, materialization = self._require_live_materialization(proof)
        authority, candidate, _ = _read_registered_materialization_candidate(proof)
        if candidate != materialization:
            raise ValueError("source_admission_producer_relation_changed")
        issuer_call = SourceIssuerCall(
            operation="admit",
            event_id=event_id,
            expected_predecessor=expected_predecessor,
            registration=materialization.registration,
            materialization=materialization,
        )
        self._require_issuer_call(authority, issuer_call)
        if not event_id or len(event_id) > 256 or not isinstance(expected_predecessor, str):
            raise ValueError("source_admission_event_identity_invalid")
        verified = self._verify_refs(
            self._materialization_refs(materialization),
            tenant_id=materialization.registration.tenant_id,
            cell_id=materialization.registration.cell_id,
        )
        # Reconcile the actual captured producer/config after all immutable reads.
        _, rechecked = self._require_live_materialization(proof)
        if rechecked != materialization:
            raise ValueError("source_admission_producer_relation_changed")

        def validate_origin() -> None:
            self._require_issuer_call(authority, issuer_call)
            self._require_live_materialization(proof)

        return self._state.admit(
            materialization=materialization,
            event_id=event_id,
            expected_predecessor=expected_predecessor,
            verified_refs=verified,
            validate_origin=validate_origin,
        )

    def transition(
        self,
        authority: SourceAdmissionAuthority,
        *,
        event_id: str,
        expected_predecessor: str,
        operation: Literal["withdraw", "readmit", "supersede"],
        target: SourceAdmissionCarrier,
    ) -> SourceAdmissionReceipt:
        authority_payload = self._authority_payload(authority)
        checked = SourceAdmissionCarrier.model_validate_json(target.model_dump_json(), strict=True)
        if not event_id or len(event_id) > 256 or not isinstance(expected_predecessor, str):
            raise ValueError("source_admission_event_identity_invalid")
        if self._runtime_decision_owner is not None and operation != "withdraw":
            raise ValueError("source_admission_operation_scope_not_established")
        self._require_issuer_call(
            authority,
            SourceIssuerCall(
                operation="withdraw",
                event_id=event_id,
                expected_predecessor=expected_predecessor,
                target=checked,
            ),
        )
        fact = self._state.fact_for_carrier(checked)
        registration = SourceRegistrationReceipt.model_validate_json(
            json.dumps(fact["materialization"]["registration"]), strict=True
        )
        issuer_call = SourceIssuerCall(
            operation="withdraw",
            event_id=event_id,
            expected_predecessor=expected_predecessor,
            registration=registration,
            target=checked,
        )
        self._require_issuer_call(authority, issuer_call)
        _require_source_admission_scope(
            _require_source_admission_authority(authority),
            operation=operation,
            registration_key=registration.registration_key,
            effective_view_contract_ref=registration.effective_view_contract_ref,
            use_contract_ref=registration.use_contract_ref,
        )
        if operation == "readmit":
            original = fact["verified_refs"]
            refs = tuple(
                ArtifactRef.model_validate_json(json.dumps(row["ref"]), strict=True)
                for row in original
            )
            if (
                self._verify_refs(
                    refs, tenant_id=registration.tenant_id, cell_id=registration.cell_id
                )
                != original
            ):
                raise ValueError("source_admission_reference_content_mismatch")

        def validate_origin() -> None:
            self._require_issuer_call(authority, issuer_call)

        return self._state.transition(
            authority=authority_payload,
            event_id=event_id,
            expected_predecessor=expected_predecessor,
            operation=operation,
            target=checked,
            validate_origin=validate_origin,
        )

    def event_receipt(
        self,
        authority: SourceAdmissionAuthority,
        *,
        event_id: str,
    ) -> SourceAdmissionReceipt | None:
        """Read protected original committed history, not admit a new or changed command."""
        issuer_call = SourceIssuerCall(operation="read_event", event_id=event_id)
        self._require_issuer_call(authority, issuer_call)
        receipt = self._state.event_receipt(
            authority=self._authority_payload(authority), event_id=event_id
        )
        if receipt is None:
            return None
        registration = receipt.source_registration
        if registration is None:
            if receipt.carrier is None:
                raise ValueError("source_admission_event_scope_not_established")
            fact = self._state.fact_for_carrier(receipt.carrier)
            registration = SourceRegistrationReceipt.model_validate_json(
                json.dumps(fact["materialization"]["registration"]), strict=True
            )
        _require_source_admission_scope(
            self._require_issuer_call(
                authority,
                SourceIssuerCall(
                    operation="read_event", event_id=event_id, registration=registration
                ),
            ),
            operation="read_event",
            registration_key=registration.registration_key,
            effective_view_contract_ref=registration.effective_view_contract_ref,
            use_contract_ref=registration.use_contract_ref,
        )
        return receipt

    def scope_head(
        self, authority: SourceAdmissionAuthority, registration: SourceRegistrationReceipt
    ) -> str:
        """Read a protected current predecessor, never infer current-use status."""
        authority_state = _require_source_admission_authority(authority)
        checked = SourceRegistrationReceipt.model_validate_json(
            registration.model_dump_json(), strict=True
        )
        issuer_call = SourceIssuerCall(
            operation="current_head",
            event_id=(
                authority_state.initial_call.event_id if authority_state.initial_call else "legacy"
            ),
            expected_predecessor=(
                authority_state.initial_call.expected_predecessor
                if authority_state.initial_call
                else None
            ),
            registration=checked,
        )
        self._require_issuer_call(authority, issuer_call)
        _require_source_admission_scope(
            authority_state,
            operation="read_event",
            registration_key=checked.registration_key,
            effective_view_contract_ref=checked.effective_view_contract_ref,
            use_contract_ref=checked.use_contract_ref,
        )
        if (
            checked.tenant_id,
            checked.cell_id,
            checked.provider_id,
            checked.issuer_key,
        ) != (
            authority_state.tenant_id,
            authority_state.cell_id,
            authority_state.provider_id,
            authority_state.issuer_key,
        ):
            raise ValueError("source_admission_wrong_authority_scope")
        head = self._state.scope_head(checked)
        if self._require_issuer_call(authority, issuer_call) != authority_state:
            raise ValueError("source_admission_authority_changed")
        return head

    def materialization_event(
        self, authority: SourceAdmissionAuthority, *, event_id: str
    ) -> tuple[SourceAdmissionReceipt, RegisteredMaterialization, str] | None:
        """Recover an original committed admit command, not current-use authority."""
        self._require_issuer_call(
            authority, SourceIssuerCall(operation="read_event", event_id=event_id)
        )
        result = self._state.materialization_event(
            authority=self._authority_payload(authority), event_id=event_id
        )
        if result is None:
            return None
        receipt, materialization, predecessor = result
        registration = materialization.registration
        _require_source_admission_scope(
            self._require_issuer_call(
                authority,
                SourceIssuerCall(
                    operation="read_event",
                    event_id=event_id,
                    expected_predecessor=predecessor,
                    registration=registration,
                    materialization=materialization,
                ),
            ),
            operation="read_event",
            registration_key=registration.registration_key,
            effective_view_contract_ref=registration.effective_view_contract_ref,
            use_contract_ref=registration.use_contract_ref,
        )
        return receipt, materialization, predecessor

    def carrier_history(
        self, carrier: SourceAdmissionCarrier, *, event_id: str
    ) -> tuple[SourceAdmissionReceipt, RegisteredMaterialization, str]:
        """Recover the exact committed original event for a concrete carrier."""
        checked = SourceAdmissionCarrier.model_validate_json(carrier.model_dump_json(), strict=True)
        fact = self._state.fact_for_carrier(checked)
        materialization = RegisteredMaterialization.model_validate_json(
            json.dumps(fact["materialization"]), strict=True
        )
        registration = materialization.registration
        result = self._state.materialization_event(
            authority={
                "issuer_key": registration.issuer_key,
                "tenant_id": registration.tenant_id,
                "cell_id": registration.cell_id,
                "provider_id": registration.provider_id,
            },
            event_id=event_id,
        )
        if result is None or result[0].carrier != checked or result[1] != materialization:
            raise ValueError("source_admission_original_event_not_established")
        return result

    def read(
        self,
        carriers: tuple[SourceAdmissionCarrier, ...],
        *,
        require_selected: bool = False,
    ) -> SourceCurrentUseProjection:
        generation = 0
        committed_root = None
        basis_digest = None
        try:
            checked = tuple(
                SourceAdmissionCarrier.model_validate_json(carrier.model_dump_json(), strict=True)
                for carrier in carriers
            )
            basis_digest = source_admission_basis_digest(checked, require_selected=require_selected)
            _, facts, reasons = self._state.snapshot_facts(
                checked, require_selected=require_selected
            )
            input_error = None
            if not reasons:
                try:
                    for fact in facts:
                        original = fact["verified_refs"]
                        refs = tuple(
                            ArtifactRef.model_validate_json(json.dumps(row["ref"]), strict=True)
                            for row in original
                        )
                        registration = fact["materialization"]["registration"]
                        if (
                            self._verify_refs(
                                refs,
                                tenant_id=registration["tenant_id"],
                                cell_id=registration["cell_id"],
                            )
                            != original
                        ):
                            raise ValueError("source_admission_reference_content_mismatch")
                except (
                    AttributeError,
                    KeyError,
                    OSError,
                    ValueError,
                    TypeError,
                    RuntimeError,
                ):
                    input_error = "source_admission_reference_not_established"
            # This second short common-fence read is the decisive linearization.
            final, current_facts, current_reasons = self._state.snapshot_facts(
                checked, require_selected=require_selected
            )
            generation = final.generation
            committed_root = _digest(final.payload()) if final.generation else None
            if input_error is not None:
                current_reasons = (*current_reasons, input_error)
            if not current_reasons and [_digest(fact) for fact in facts] != [
                _digest(fact) for fact in current_facts
            ]:
                current_reasons = ("source_admission_basis_changed_during_read",)
            if reasons and not current_reasons:
                # An admission appearing after the CAS phase was never verified.
                current_reasons = ("source_admission_basis_changed_during_read",)
            status = (
                "current"
                if not current_reasons
                else ("withdrawn" if "source_admission_withdrawn" in current_reasons else "unknown")
            )
            return SourceCurrentUseProjection(
                status=status,
                reason_codes=tuple(dict.fromkeys(current_reasons)),
                generation=generation,
                committed_root=committed_root,
                basis_digest=basis_digest,
                selection_checked=require_selected is True,
                predicate_provenance="recomputed" if status == "current" else "not_established",
                checked_at=datetime.now(UTC),
            )
        except (AttributeError, KeyError, OSError, ValueError, TypeError, RuntimeError):
            return SourceCurrentUseProjection(
                status="unknown",
                reason_codes=("source_admission_committed_basis_not_established",),
                generation=generation,
                committed_root=committed_root,
                basis_digest=basis_digest,
                selection_checked=require_selected is True,
                predicate_provenance="not_established",
                checked_at=datetime.now(UTC),
            )
