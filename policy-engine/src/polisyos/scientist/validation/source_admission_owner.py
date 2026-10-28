"""Typed intake/read bridge for the existing validity owner's committed source state.

The neutral factory/producer ports are trusted composition seams, not candidate
validators. The default has no producer authority. C106 supplies the actual
appointed Runtime factory and live registered Fabric materialization capture.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    read_core_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.protocol import ArtifactStore
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
    VerifiedRegisteredMaterialization,
    _require_registered_materialization,
    _require_source_admission_authority,
    _require_source_admission_scope,
)
from polisyos.scientist.validation.source_admission_state import (
    _digest,
    _SourceAdmissionStateStore,
)


class _RegisteredSourceAdmissionOwner:
    """One composed quantity with the existing DecisionValidityService fence."""

    def __init__(
        self,
        store: ArtifactStore,
        base: Path,
        transaction: Callable[[], AbstractContextManager[object]],
    ) -> None:
        self._store = store
        self._cas_root = base.parent.resolve()
        self._state = _SourceAdmissionStateStore(base, transaction)

    @staticmethod
    def _authority_payload(authority: SourceAdmissionAuthority) -> dict[str, str]:
        state = _require_source_admission_authority(authority)
        return {
            "issuer_key": state.issuer_key,
            "tenant_id": state.tenant_id,
            "cell_id": state.cell_id,
            "provider_id": state.provider_id,
        }

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
            _require_source_admission_authority(authority)

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

    def admit(
        self,
        proof: VerifiedRegisteredMaterialization,
        *,
        event_id: str,
        expected_predecessor: str,
    ) -> SourceAdmissionReceipt:
        _, materialization = _require_registered_materialization(proof)
        if not event_id or len(event_id) > 256 or not isinstance(expected_predecessor, str):
            raise ValueError("source_admission_event_identity_invalid")
        verified = self._verify_refs(
            self._materialization_refs(materialization),
            tenant_id=materialization.registration.tenant_id,
            cell_id=materialization.registration.cell_id,
        )
        # Reconcile the actual captured producer/config after all immutable reads.
        _, rechecked = _require_registered_materialization(proof)
        if rechecked != materialization:
            raise ValueError("source_admission_producer_relation_changed")

        def validate_origin() -> None:
            _require_registered_materialization(proof)

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
        fact = self._state.fact_for_carrier(checked)
        registration = SourceRegistrationReceipt.model_validate_json(
            json.dumps(fact["materialization"]["registration"]), strict=True
        )
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
            _require_source_admission_authority(authority)

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
            _require_source_admission_authority(authority),
            operation="read_event",
            registration_key=registration.registration_key,
            effective_view_contract_ref=registration.effective_view_contract_ref,
            use_contract_ref=registration.use_contract_ref,
        )
        return receipt

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
