"""Exact reconciliation between Runtime and Scientist epoch denominators.

The two denominators answer different completeness questions. This module
therefore verifies and persists their relation without rewriting either owner
digest or accepting caller-supplied membership.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polisyos.core import artifacts, canon
from polisyos.core.contracts import (
    DecisionValidityEpochImpactSnapshot,
    DecisionValidityEpochImpactSnapshotHandle,
    EpochTransitionDenominatorMappingRow,
    EpochTransitionDenominatorReconciliationHandle,
    EpochTransitionDenominatorReconciliationReceipt,
    PersistedDecisionValidityEpochImpactSnapshot,
    PersistedEpochTransitionDenominatorReconciliation,
)
from polisyos.runtime.quality.epoch_validity_cascade import (
    EpochValidityTransitionArtifact,
    _epoch_dependency_target_refs,
    epoch_dependency_outer_denominator_ref,
)
from polisyos.runtime.quality.epoch_validity_cascade import (
    _canonical_bytes as _transition_canonical_bytes,
)

ArtifactRef = artifacts.ArtifactRef
ArtifactStore = artifacts.ArtifactStore

_CHRONOLOGY_MEDIA_TYPE = "application/vnd.polisyos.chronology+json"
_TRANSITION_KIND = "polisyos.epoch.validity_transition"
_PROVENANCE_KIND = "chronology.epoch_transition_verifier"
_SNAPSHOT_KIND = "scientist.decision_validity_epoch_impact_snapshot"
_SNAPSHOT_MEDIA_TYPE = "application/json"
_SNAPSHOT_SCHEMA = "polisyos.decision-validity.epoch-impact-snapshot.v1"
_RECONCILIATION_KIND = "polisyos.epoch.transition_denominator_reconciliation_receipt"
_RECONCILIATION_SCHEMA = "polisyos.epoch-transition-denominator-reconciliation.v1"
_CANON_SPEC = canon.CanonSpec()
_CANON_INFO = artifacts.CanonInfo.from_spec(_CANON_SPEC)


class EpochDenominatorReconciliationNonReceipt(BaseModel):
    """Typed refusal proving the two owner member populations do not reconcile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["rejected"] = "rejected"
    code: Literal["epoch_denominator_membership_mismatch"]
    predicate_class: Literal["recomputed"] = "recomputed"
    reconciliation_handle: None = None


def _raw_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _manifest_ref(manifest: artifacts.ArtifactManifest) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
    )


def _receipt_inputs(
    *,
    transition_ref: ArtifactRef,
    snapshot_ref: ArtifactRef,
    provenance_ref: ArtifactRef,
) -> list[artifacts.InputRef]:
    rows = [
        artifacts.InputRef(
            artifact_id=transition_ref.artifact_id,
            role="epoch_transition",
        ),
        artifacts.InputRef(
            artifact_id=snapshot_ref.artifact_id,
            role="decision_validity_epoch_impact_snapshot",
        ),
        artifacts.InputRef(
            artifact_id=provenance_ref.artifact_id,
            role="epoch_transition_verifier_provenance",
        ),
    ]
    return sorted(rows, key=lambda row: (row.role, str(row.artifact_id)))


def _read_transition_exact(
    *,
    store: ArtifactStore,
    ref: ArtifactRef,
) -> tuple[EpochValidityTransitionArtifact, bytes]:
    try:
        manifest = store.get_manifest(ref.artifact_id)
        raw = store.get_bytes(ref.artifact_id)
        report = store.verify(ref.artifact_id)
        if (
            ref.kind != _TRANSITION_KIND
            or ref.media_type != _CHRONOLOGY_MEDIA_TYPE
            or _manifest_ref(manifest) != ref
            or manifest.artifact_schema is not None
            or manifest.canon is not None
            or not report.ok
            or _raw_digest(raw) != str(ref.artifact_id)
        ):
            raise ValueError("transition profile mismatch")
        transition = EpochValidityTransitionArtifact.model_validate_json(raw)
        if _transition_canonical_bytes(transition) != raw:
            raise ValueError("transition bytes noncanonical")
        expected_outer = epoch_dependency_outer_denominator_ref(
            certificate_bindings=transition.certificate_bindings,
            dependency_graph=transition.dependency_graph,
        )
        if transition.dependency_denominator_ref != expected_outer:
            raise ValueError("transition outer denominator mismatch")
        return transition, raw
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("epoch_denominator_reconciliation_unresolved") from exc


def _read_snapshot_exact(
    *,
    store: ArtifactStore,
    handle: DecisionValidityEpochImpactSnapshotHandle,
) -> PersistedDecisionValidityEpochImpactSnapshot:
    try:
        ref = handle.snapshot_ref
        manifest = store.get_manifest(ref.artifact_id)
        raw = store.get_bytes(ref.artifact_id)
        report = store.verify(ref.artifact_id)
        if (
            ref.kind != _SNAPSHOT_KIND
            or ref.media_type != _SNAPSHOT_MEDIA_TYPE
            or _manifest_ref(manifest) != ref
            or manifest.artifact_schema
            != artifacts.SchemaInfo(name=_SNAPSHOT_SCHEMA, version="1.0")
            or manifest.canon != _CANON_INFO
            or not report.ok
            or _raw_digest(raw) != str(ref.artifact_id)
        ):
            raise ValueError("snapshot profile mismatch")
        snapshot = DecisionValidityEpochImpactSnapshot.model_validate(
            canon.from_canonical_bytes(raw)
        )
        if (
            canon.to_canonical_bytes(snapshot.model_dump(mode="json"), _CANON_SPEC) != raw
            or handle.snapshot_content_hash != snapshot.snapshot_content_hash
        ):
            raise ValueError("snapshot bytes mismatch")
        return PersistedDecisionValidityEpochImpactSnapshot(
            handle=handle,
            snapshot_bytes=raw,
            snapshot=snapshot,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("epoch_denominator_reconciliation_unresolved") from exc


def _read_target_exact(*, store: ArtifactStore, ref: ArtifactRef) -> None:
    try:
        manifest = store.get_manifest(ref.artifact_id)
        raw = store.get_bytes(ref.artifact_id)
        report = store.verify(ref.artifact_id)
        if (
            _manifest_ref(manifest) != ref
            or not report.ok
            or _raw_digest(raw) != str(ref.artifact_id)
        ):
            raise ValueError("runtime target mismatch")
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("epoch_denominator_reconciliation_unresolved") from exc


def _verify_appointed_provenance(
    *,
    store: ArtifactStore,
    appointed_ref: ArtifactRef,
    receipt_ref: ArtifactRef,
) -> None:
    try:
        if appointed_ref != receipt_ref:
            raise ValueError("provenance appointment mismatch")
        manifest = store.get_manifest(receipt_ref.artifact_id)
        raw = store.get_bytes(receipt_ref.artifact_id)
        report = store.verify(receipt_ref.artifact_id)
        if (
            receipt_ref.kind != _PROVENANCE_KIND
            or _manifest_ref(manifest) != receipt_ref
            or not report.ok
            or _raw_digest(raw) != str(receipt_ref.artifact_id)
        ):
            raise ValueError("provenance mismatch")
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("epoch_denominator_reconciliation_unresolved") from exc


def _derive_receipt(
    *,
    store: ArtifactStore,
    transition_ref: ArtifactRef,
    transition: EpochValidityTransitionArtifact,
    transition_raw: bytes,
    snapshot: PersistedDecisionValidityEpochImpactSnapshot,
    requested_query_context_ref: str,
    authority_purpose: Literal["decision_validity_epoch_transition"],
    verifier_provenance_ref: ArtifactRef,
) -> EpochTransitionDenominatorReconciliationReceipt | EpochDenominatorReconciliationNonReceipt:
    if (
        transition.requested_query_context_ref != requested_query_context_ref
        or transition.authority_purpose != authority_purpose
        or snapshot.snapshot.requested_query_context_ref != requested_query_context_ref
        or snapshot.snapshot.authority_purpose != authority_purpose
    ):
        raise ValueError("epoch_denominator_reconciliation_unresolved")

    runtime_targets = _epoch_dependency_target_refs(transition.dependency_graph)
    for runtime_target in runtime_targets:
        _read_target_exact(store=store, ref=runtime_target)
    targets_by_artifact_id: dict[str, list[ArtifactRef]] = {}
    for runtime_target in runtime_targets:
        targets_by_artifact_id.setdefault(str(runtime_target.artifact_id), []).append(
            runtime_target
        )

    selected_by_dependency: dict[str, ArtifactRef] = {}
    for owner in snapshot.snapshot.owner_rows:
        candidates = targets_by_artifact_id.get(owner.artifact_id, [])
        if len(candidates) != 1:
            return EpochDenominatorReconciliationNonReceipt(
                code="epoch_denominator_membership_mismatch"
            )
        selected_by_dependency[owner.dependency_key] = candidates[0]

    owner_artifacts = {
        owner.dependency_key: owner.artifact_id for owner in snapshot.snapshot.owner_rows
    }
    mapping_rows = tuple(
        EpochTransitionDenominatorMappingRow(
            dependency_key=target.dependency_key,
            dependency_artifact_id=owner_artifacts[target.dependency_key],
            packet_ref=target.packet_ref,
            decision_lineage_key=target.decision_lineage_key,
            runtime_target_ref=selected_by_dependency[target.dependency_key],
        )
        for target in snapshot.snapshot.targets
    )
    return EpochTransitionDenominatorReconciliationReceipt.build(
        requested_query_context_ref=requested_query_context_ref,
        verifier_provenance_ref=verifier_provenance_ref,
        transition_artifact_ref=transition_ref,
        transition_content_hash=_raw_digest(transition_raw),
        epoch_dependency_denominator_ref=transition.dependency_denominator_ref,
        runtime_target_refs=runtime_targets,
        scientist_snapshot_ref=snapshot.handle.snapshot_ref,
        scientist_snapshot_content_hash=snapshot.handle.snapshot_content_hash,
        decision_impact_denominator_ref=snapshot.snapshot.decision_impact_denominator_ref,
        requested_dependency_keys=snapshot.snapshot.requested_dependency_keys,
        scientist_owner_rows=snapshot.snapshot.owner_rows,
        scientist_targets=snapshot.snapshot.targets,
        mapping_rows=mapping_rows,
    )


class EpochTransitionDenominatorReconciliationReader:
    """Resolve fresh candidates completely and replay only exact frozen handles."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        verifier_provenance_ref: ArtifactRef | None,
    ) -> None:
        self._store = store
        self.verifier_provenance_ref = verifier_provenance_ref

    def _require_appointment(self) -> ArtifactRef:
        if self.verifier_provenance_ref is None:
            raise ValueError("epoch_denominator_reconciliation_unavailable")
        return self.verifier_provenance_ref

    def _read_receipt_exact(
        self,
        *,
        handle: EpochTransitionDenominatorReconciliationHandle,
    ) -> PersistedEpochTransitionDenominatorReconciliation:
        try:
            ref = handle.reconciliation_receipt_ref
            manifest = self._store.get_manifest(ref.artifact_id)
            raw = self._store.get_bytes(ref.artifact_id)
            report = self._store.verify(ref.artifact_id)
            if (
                ref.kind != _RECONCILIATION_KIND
                or ref.media_type != _CHRONOLOGY_MEDIA_TYPE
                or _manifest_ref(manifest) != ref
                or manifest.artifact_schema
                != artifacts.SchemaInfo(name=_RECONCILIATION_SCHEMA, version="1.0")
                or manifest.canon != _CANON_INFO
                or not report.ok
                or _raw_digest(raw) != str(ref.artifact_id)
            ):
                raise ValueError("receipt profile mismatch")
            receipt = EpochTransitionDenominatorReconciliationReceipt.model_validate(
                canon.from_canonical_bytes(raw)
            )
            if (
                canon.to_canonical_bytes(receipt.model_dump(mode="json"), _CANON_SPEC) != raw
                or handle.reconciliation_receipt_content_hash != receipt.reconciliation_content_hash
                or manifest.inputs
                != _receipt_inputs(
                    transition_ref=receipt.transition_artifact_ref,
                    snapshot_ref=receipt.scientist_snapshot_ref,
                    provenance_ref=receipt.verifier_provenance_ref,
                )
            ):
                raise ValueError("receipt bytes or inputs mismatch")
            transition, transition_raw = _read_transition_exact(
                store=self._store,
                ref=receipt.transition_artifact_ref,
            )
            snapshot = _read_snapshot_exact(
                store=self._store,
                handle=DecisionValidityEpochImpactSnapshotHandle(
                    snapshot_ref=receipt.scientist_snapshot_ref,
                    snapshot_content_hash=receipt.scientist_snapshot_content_hash,
                ),
            )
            appointed = self._require_appointment()
            _verify_appointed_provenance(
                store=self._store,
                appointed_ref=appointed,
                receipt_ref=receipt.verifier_provenance_ref,
            )
            expected = _derive_receipt(
                store=self._store,
                transition_ref=receipt.transition_artifact_ref,
                transition=transition,
                transition_raw=transition_raw,
                snapshot=snapshot,
                requested_query_context_ref=receipt.requested_query_context_ref,
                authority_purpose=receipt.authority_purpose,
                verifier_provenance_ref=receipt.verifier_provenance_ref,
            )
            if (
                isinstance(expected, EpochDenominatorReconciliationNonReceipt)
                or expected != receipt
            ):
                raise ValueError("receipt cannot be reproduced")
            return PersistedEpochTransitionDenominatorReconciliation(
                handle=handle,
                receipt_bytes=raw,
                receipt=receipt,
            )
        except ValueError as exc:
            if str(exc) == "epoch_denominator_reconciliation_unavailable":
                raise
            raise ValueError("epoch_denominator_reconciliation_unresolved") from exc
        except (KeyError, OSError, RuntimeError, TypeError) as exc:
            raise ValueError("epoch_denominator_reconciliation_unresolved") from exc

    def resolve_exact(
        self,
        *,
        handle: EpochTransitionDenominatorReconciliationHandle,
    ) -> PersistedEpochTransitionDenominatorReconciliation:
        """Resolve and recompute one receipt selected by its exact frozen handle."""

        return self._read_receipt_exact(handle=handle)

    def resolve_for_first_admission(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        transition_content_hash: str,
        requested_query_context_ref: str,
        authority_purpose: Literal["decision_validity_epoch_transition"],
        scientist_snapshot_handle: DecisionValidityEpochImpactSnapshotHandle,
    ) -> PersistedEpochTransitionDenominatorReconciliation:
        """Scan the complete live CAS denominator for one exact candidate."""

        appointed = self._require_appointment()
        transition, transition_raw = _read_transition_exact(
            store=self._store,
            ref=transition_artifact_ref,
        )
        if _raw_digest(transition_raw) != transition_content_hash:
            raise ValueError("epoch_denominator_reconciliation_unresolved")
        snapshot = _read_snapshot_exact(
            store=self._store,
            handle=scientist_snapshot_handle,
        )
        _verify_appointed_provenance(
            store=self._store,
            appointed_ref=appointed,
            receipt_ref=appointed,
        )
        relation = _derive_receipt(
            store=self._store,
            transition_ref=transition_artifact_ref,
            transition=transition,
            transition_raw=transition_raw,
            snapshot=snapshot,
            requested_query_context_ref=requested_query_context_ref,
            authority_purpose=authority_purpose,
            verifier_provenance_ref=appointed,
        )

        matches: list[PersistedEpochTransitionDenominatorReconciliation] = []
        try:
            artifact_ids = sorted(self._store.iter_artifact_ids(), key=str)
            for artifact_id in artifact_ids:
                manifest = self._store.get_manifest(artifact_id)
                if manifest.kind != _RECONCILIATION_KIND:
                    continue
                raw = self._store.get_bytes(artifact_id)
                parsed = EpochTransitionDenominatorReconciliationReceipt.model_validate(
                    canon.from_canonical_bytes(raw)
                )
                candidate = self.resolve_exact(
                    handle=EpochTransitionDenominatorReconciliationHandle(
                        reconciliation_receipt_ref=_manifest_ref(manifest),
                        reconciliation_receipt_content_hash=(parsed.reconciliation_content_hash),
                    )
                )
                receipt = candidate.receipt
                if (
                    receipt.transition_artifact_ref == transition_artifact_ref
                    and receipt.transition_content_hash == transition_content_hash
                    and receipt.requested_query_context_ref == requested_query_context_ref
                    and receipt.authority_purpose == authority_purpose
                    and receipt.scientist_snapshot_ref == scientist_snapshot_handle.snapshot_ref
                    and receipt.scientist_snapshot_content_hash
                    == scientist_snapshot_handle.snapshot_content_hash
                    and receipt.verifier_provenance_ref == appointed
                ):
                    matches.append(candidate)
        except ValueError as exc:
            if str(exc).startswith("epoch_denominator_reconciliation_"):
                raise
            raise ValueError("epoch_denominator_reconciliation_unresolved") from exc
        except (KeyError, OSError, RuntimeError, TypeError) as exc:
            raise ValueError("epoch_denominator_reconciliation_unresolved") from exc

        if len(matches) > 1:
            raise ValueError("epoch_denominator_reconciliation_ambiguous")
        if matches:
            return matches[0]
        if isinstance(relation, EpochDenominatorReconciliationNonReceipt):
            raise ValueError("epoch_denominator_membership_mismatch")
        raise ValueError("epoch_denominator_reconciliation_unavailable")


class EpochTransitionDenominatorReconciliationProducer:
    """Produce only a relation derived from exact Runtime and Scientist sources."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        verifier_provenance_ref: ArtifactRef | None,
    ) -> None:
        self._store = store
        self.verifier_provenance_ref = verifier_provenance_ref

    def produce_and_persist(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        scientist_snapshot_handle: DecisionValidityEpochImpactSnapshotHandle,
        requested_query_context_ref: str,
        authority_purpose: Literal["decision_validity_epoch_transition"],
    ) -> (
        PersistedEpochTransitionDenominatorReconciliation | EpochDenominatorReconciliationNonReceipt
    ):
        """Derive, persist, then exact-read one reconciliation."""

        if self.verifier_provenance_ref is None:
            raise ValueError("epoch_denominator_reconciliation_unavailable")
        transition, transition_raw = _read_transition_exact(
            store=self._store,
            ref=transition_artifact_ref,
        )
        snapshot = _read_snapshot_exact(
            store=self._store,
            handle=scientist_snapshot_handle,
        )
        _verify_appointed_provenance(
            store=self._store,
            appointed_ref=self.verifier_provenance_ref,
            receipt_ref=self.verifier_provenance_ref,
        )
        receipt = _derive_receipt(
            store=self._store,
            transition_ref=transition_artifact_ref,
            transition=transition,
            transition_raw=transition_raw,
            snapshot=snapshot,
            requested_query_context_ref=requested_query_context_ref,
            authority_purpose=authority_purpose,
            verifier_provenance_ref=self.verifier_provenance_ref,
        )
        if isinstance(receipt, EpochDenominatorReconciliationNonReceipt):
            return receipt
        raw = canon.to_canonical_bytes(receipt.model_dump(mode="json"), _CANON_SPEC)
        ref = self._store.put_bytes(
            raw,
            artifacts.ArtifactWriteOptions(
                kind=_RECONCILIATION_KIND,
                media_type=_CHRONOLOGY_MEDIA_TYPE,
                schema=artifacts.SchemaInfo(name=_RECONCILIATION_SCHEMA, version="1.0"),
                canon=_CANON_INFO,
                inputs=_receipt_inputs(
                    transition_ref=transition_artifact_ref,
                    snapshot_ref=scientist_snapshot_handle.snapshot_ref,
                    provenance_ref=self.verifier_provenance_ref,
                ),
            ),
        )
        handle = EpochTransitionDenominatorReconciliationHandle(
            reconciliation_receipt_ref=ref,
            reconciliation_receipt_content_hash=receipt.reconciliation_content_hash,
        )
        return EpochTransitionDenominatorReconciliationReader(
            store=self._store,
            verifier_provenance_ref=self.verifier_provenance_ref,
        ).resolve_exact(handle=handle)


__all__ = [
    "EpochDenominatorReconciliationNonReceipt",
    "EpochTransitionDenominatorReconciliationHandle",
    "EpochTransitionDenominatorReconciliationProducer",
    "EpochTransitionDenominatorReconciliationReader",
    "PersistedEpochTransitionDenominatorReconciliation",
]
