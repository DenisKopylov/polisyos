"""Owner-held canonical transition execution provenance and independent readback.

The private completion handle crosses the trusted producer/owner boundary.  The
durable owner index, not a caller's CAS statement or a signer's identity, admits
an origin.  This records execution, and grants no separate minting authority.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from polisyos.core import artifacts, canon, contracts, security
from polisyos.runtime.quality import epoch_validity_cascade as cascade
from polisyos.runtime.quality.semantic_epoch import (
    SemanticEpochManifest,
    SemanticEpochProductionReceipt,
)

ArtifactRef = artifacts.ArtifactRef
Digest = contracts.chronology.Digest
_ORIGIN_KIND = "polisyos.epoch.transition_execution_origin"
_DEPENDENCIES_KIND = "polisyos.epoch.transition_dependency_receipt"
_ADJUDICATIONS_KIND = "polisyos.epoch.transition_adjudication_receipt"
_PRODUCER = (
    "polisyos.runtime.quality.epoch_validity_cascade."
    "EpochValidityTransitionProducer.produce_and_persist"
)
_EXECUTION_SEAL = object()


class AdmittedEpochTransitionSigningProfile(cascade._StrictModel):
    """Exact profile and independently resolved admission, for one purpose/query."""

    signing_profile_ref: ArtifactRef
    signing_profile_content_hash: Digest
    admission_ref: ArtifactRef
    admission_content_hash: Digest
    authority_purpose: str = Field(min_length=1)
    requested_query_context_ref: Digest
    predicate_class: Literal["independently_reconciled"] = "independently_reconciled"


class EpochTransitionSigningProfileAdmissionReader(Protocol):
    """Deployment-owned admission and cryptographic verification, never signer echo."""

    def resolve_admitted_signing_profile(
        self,
        *,
        signing_profile_ref: ArtifactRef,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> AdmittedEpochTransitionSigningProfile: ...

    def verify_transition_signature(
        self,
        *,
        evidence: contracts.chronology.SignedArtifactEvidence,
        signing_profile_ref: ArtifactRef,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> bool: ...


class EpochTransitionOriginStatement(cascade._StrictModel):
    """Immutable evidence of one completed canonical producer execution."""

    schema_version: Literal["polisyos.epoch.transition-execution-origin.v1"] = (
        "polisyos.epoch.transition-execution-origin.v1"
    )
    canonical_producer_ref: Literal[
        "polisyos.runtime.quality.epoch_validity_cascade.EpochValidityTransitionProducer.produce_and_persist"
    ] = _PRODUCER
    previous_epoch_manifest_ref: ArtifactRef
    current_epoch_production_receipt_ref: ArtifactRef
    transition_artifact_ref: ArtifactRef
    transition_content_hash: Digest
    transition_raw_content_hash: Digest
    signed_artifact_evidence_ref: ArtifactRef
    signing_profile_ref: ArtifactRef
    signer_provenance_ref: ArtifactRef
    admitted_signing_profile: AdmittedEpochTransitionSigningProfile
    dependency_receipt_ref: ArtifactRef
    dependency_receipt_content_hash: Digest
    adjudication_receipt_ref: ArtifactRef
    adjudication_receipt_content_hash: Digest
    dependency_denominator_ref: Digest
    adjudication_denominator_ref: Digest
    authority_purpose: str = Field(min_length=1)
    requested_query_context_ref: Digest


@dataclass(frozen=True, slots=True)
class _CompletedEpochTransitionExecution:
    seal: object
    previous_epoch_manifest_ref: ArtifactRef
    current_epoch_production_receipt_ref: ArtifactRef
    transition: cascade.EpochValidityTransitionArtifact
    dependencies: cascade.EpochDependencyDenominatorReceipt
    adjudications: cascade.EpochPerturbationAdjudicationReceipt
    signed: contracts.chronology.PersistedSignedArtifactEvidence

    def __post_init__(self) -> None:
        if self.seal is not _EXECUTION_SEAL:
            raise TypeError("canonical_epoch_transition_execution_required")


def _seal_completed_epoch_transition_execution(
    *,
    previous_epoch_manifest_ref: ArtifactRef,
    current_epoch_production_receipt_ref: ArtifactRef,
    transition: cascade.EpochValidityTransitionArtifact,
    dependencies: cascade.EpochDependencyDenominatorReceipt,
    adjudications: cascade.EpochPerturbationAdjudicationReceipt,
    signed: contracts.chronology.PersistedSignedArtifactEvidence,
) -> _CompletedEpochTransitionExecution:
    """Seal only the canonical producer's completed local execution."""

    return _CompletedEpochTransitionExecution(
        _EXECUTION_SEAL,
        previous_epoch_manifest_ref,
        current_epoch_production_receipt_ref,
        transition,
        dependencies,
        adjudications,
        signed,
    )


class FileEpochTransitionOriginOwner:
    """Persist execution admissions separately from candidate CAS artifacts.

    The configured directory is trusted owner state, as for native epoch history.
    Hostile code mutating that directory or Python private state is outside this
    internal capability boundary.  Readback never requires a retained epoch to
    remain the live head; the producer established currentness before admission.
    """

    def __init__(
        self,
        *,
        root: Path,
        artifacts: artifacts.ArtifactStore,
        signed_artifacts: contracts.chronology.SignedArtifactEvidenceRepository,
        signing_profiles: EpochTransitionSigningProfileAdmissionReader | None = None,
    ) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._artifacts = artifacts
        self._signed_artifacts = signed_artifacts
        self._signing_profiles = signing_profiles

    def _scope_root(self) -> Path:
        """Select the complete owner namespace from trusted operation-time context."""

        scope = security.get_current_access_scope_or_none()
        tenant = scope.tenant_id if scope is not None else security.get_current_tenant_id_or_none()
        cell = scope.cell_id if scope is not None else security.get_current_cell_id()
        root = self._root
        if tenant is not None:
            coordinate = canon.to_canonical_bytes(
                {"tenant_id": tenant, "cell_id": cell}, canon.CanonSpec()
            )
            root = root / "tenant-scopes" / hashlib.sha256(coordinate).hexdigest()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _profile(
        self,
        *,
        evidence: contracts.chronology.SignedArtifactEvidence,
        signing_profile_ref: ArtifactRef,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> AdmittedEpochTransitionSigningProfile:
        reader = self._signing_profiles
        if reader is None:
            raise ValueError("epoch_transition_signing_profile_not_admitted")
        profile = AdmittedEpochTransitionSigningProfile.model_validate(
            reader.resolve_admitted_signing_profile(
                signing_profile_ref=signing_profile_ref,
                authority_purpose=authority_purpose,
                requested_query_context_ref=requested_query_context_ref,
            ).model_dump(mode="json")
        )
        if (
            profile.signing_profile_ref != signing_profile_ref
            or profile.authority_purpose != authority_purpose
            or profile.requested_query_context_ref != requested_query_context_ref
            or profile.signing_profile_content_hash != str(signing_profile_ref.artifact_id)
            or profile.admission_content_hash != str(profile.admission_ref.artifact_id)
            or not reader.verify_transition_signature(
                evidence=evidence,
                signing_profile_ref=signing_profile_ref,
                authority_purpose=authority_purpose,
                requested_query_context_ref=requested_query_context_ref,
            )
        ):
            raise ValueError("epoch_transition_signing_profile_or_signature_mismatch")
        return profile

    def _read_epoch_model[Model: SemanticEpochManifest | SemanticEpochProductionReceipt](
        self,
        ref: ArtifactRef,
        model: type[Model],
        *,
        kind: str,
        media_type: str,
    ) -> Model:
        raw = self._artifacts.get_bytes(ref.artifact_id)
        manifest = self._artifacts.get_manifest(ref.artifact_id)
        frames = contracts.chronology._split_framed_records(raw)
        if (
            not self._artifacts.verify(ref.artifact_id).ok
            or str(ref.artifact_id) != security.raw_content_hash(raw)
            or ref.kind != kind
            or manifest.kind != kind
            or ref.media_type != media_type
            or manifest.media_type != media_type
            or manifest.artifact_id != ref.artifact_id
            or manifest.artifact_schema is not None
            or manifest.canon is not None
            or len(frames) != 1
        ):
            raise ValueError("epoch_origin_retained_source_mismatch")
        value = model.model_validate(canon.from_canonical_bytes(frames[0]))
        if raw != contracts.chronology._frame_record(contracts.epoch.canonical_epoch_bytes(value)):
            raise ValueError("epoch_origin_retained_source_noncanonical")
        if isinstance(value, SemanticEpochProductionReceipt):
            expected_inputs = tuple(
                artifacts.InputRef(artifact_id=source.artifact_id, role="epoch_production_input")
                for source in (
                    value.prepared_epoch_ref,
                    value.admitted_boundary_evidence_ref,
                    value.semantic_manifest_ref,
                    value.history_append_receipt_ref,
                    value.chronology_bundle_ref,
                    value.chronology_verification_ref,
                )
                if source is not None
            )
            ordered = cascade.FileSemanticEpochTransitionHistoryAdapter._sorted_inputs
            if ordered(manifest.inputs) != ordered(expected_inputs):
                raise ValueError("epoch_origin_retained_receipt_inputs_mismatch")
        return value

    def _verify_origin(self, origin: EpochTransitionOriginStatement) -> None:
        exact = self._signed_artifacts.read_exact(
            evidence_record_ref=origin.signed_artifact_evidence_ref
        )
        record = security.parse_canonical_statement(
            exact.persisted.record_bytes, contracts.chronology.SignedArtifactEvidenceRecord
        )
        profile = self._profile(
            evidence=exact,
            signing_profile_ref=origin.signing_profile_ref,
            authority_purpose=origin.authority_purpose,
            requested_query_context_ref=origin.requested_query_context_ref,
        )
        transition = cascade._read_model(
            store=self._artifacts,
            ref=origin.transition_artifact_ref,
            model=cascade.EpochValidityTransitionArtifact,
            kind="polisyos.epoch.validity_transition",
        )
        dependencies = cascade._read_model(
            store=self._artifacts,
            ref=origin.dependency_receipt_ref,
            model=cascade.EpochDependencyDenominatorReceipt,
            kind=_DEPENDENCIES_KIND,
        )
        adjudications = cascade._read_model(
            store=self._artifacts,
            ref=origin.adjudication_receipt_ref,
            model=cascade.EpochPerturbationAdjudicationReceipt,
            kind=_ADJUDICATIONS_KIND,
        )
        if (
            not isinstance(transition, cascade.EpochValidityTransitionArtifact)
            or not isinstance(dependencies, cascade.EpochDependencyDenominatorReceipt)
            or not isinstance(adjudications, cascade.EpochPerturbationAdjudicationReceipt)
        ):
            raise ValueError("epoch_origin_input_type_mismatch")
        previous = self._read_epoch_model(
            origin.previous_epoch_manifest_ref,
            SemanticEpochManifest,
            kind="epoch.semantic_manifest",
            media_type="application/vnd.polisyos.epoch+json",
        )
        receipt = self._read_epoch_model(
            origin.current_epoch_production_receipt_ref,
            SemanticEpochProductionReceipt,
            kind="epoch.production_receipt",
            media_type="application/vnd.polisyos.epoch-production-receipt+json",
        )
        if receipt.status not in {"appended", "no_change"} or receipt.semantic_manifest_ref is None:
            raise ValueError("epoch_origin_current_receipt_not_positive")
        current = self._read_epoch_model(
            receipt.semantic_manifest_ref,
            SemanticEpochManifest,
            kind="epoch.semantic_manifest",
            media_type="application/vnd.polisyos.epoch+json",
        )
        vector = cascade.resolve_owner_target_dispositions(
            advisory_events=adjudications.advisory_events,
            owner_dispositions=adjudications.owner_dispositions,
            dependency_graph=dependencies.dependency_graph,
        )
        recomputed = cascade.build_epoch_validity_transition(
            previous_epoch=previous,
            current_epoch=current,
            certificates=dependencies.certificate_bindings,
            dependency_graph=dependencies.dependency_graph,
            target_vector=vector,
            dependency_denominator_ref=dependencies.denominator_ref,
            adjudication_denominator_ref=adjudications.denominator_ref,
            authority_purpose=origin.authority_purpose,
            requested_query_context_ref=origin.requested_query_context_ref,
        )
        if (
            profile != origin.admitted_signing_profile
            or record.artifact_ref != origin.transition_artifact_ref
            or record.signing_profile_ref != origin.signing_profile_ref
            or record.signer_provenance_ref != origin.signer_provenance_ref
            or exact.blob_bytes != cascade._canonical_bytes(transition)
            or record.raw_blob_bytes_hash != origin.transition_raw_content_hash
            or origin.transition_raw_content_hash != str(origin.transition_artifact_ref.artifact_id)
            or origin.transition_content_hash != transition.transition_content_hash
            or origin.dependency_receipt_content_hash
            != str(origin.dependency_receipt_ref.artifact_id)
            or origin.adjudication_receipt_content_hash
            != str(origin.adjudication_receipt_ref.artifact_id)
            or origin.dependency_denominator_ref != dependencies.denominator_ref
            or origin.adjudication_denominator_ref != adjudications.denominator_ref
            or previous.scope_identity != current.scope_identity
            or current.predecessor_refs != (previous.epoch_ref,)
            or previous.authority_purpose != origin.authority_purpose
            or current.authority_purpose != origin.authority_purpose
            or receipt.epoch_ref != current.epoch_ref
            or receipt.requested_query_context_ref != origin.requested_query_context_ref
            or current.requested_query_context_ref != origin.requested_query_context_ref
            or recomputed != transition
        ):
            raise ValueError("epoch_transition_origin_binding_mismatch")

    def _admit_completed_execution(
        self, execution: _CompletedEpochTransitionExecution
    ) -> ArtifactRef:
        if (
            type(execution) is not _CompletedEpochTransitionExecution
            or execution.seal is not _EXECUTION_SEAL
        ):
            raise TypeError("canonical_epoch_transition_execution_required")
        exact = self._signed_artifacts.read_exact(
            evidence_record_ref=execution.signed.evidence_record_ref
        )
        record = security.parse_canonical_statement(
            exact.persisted.record_bytes, contracts.chronology.SignedArtifactEvidenceRecord
        )
        if exact.persisted != execution.signed or exact.blob_bytes != cascade._canonical_bytes(
            execution.transition
        ):
            raise ValueError("epoch_transition_execution_signed_bytes_mismatch")
        profile = self._profile(
            evidence=exact,
            signing_profile_ref=record.signing_profile_ref,
            authority_purpose=execution.transition.authority_purpose,
            requested_query_context_ref=execution.transition.requested_query_context_ref,
        )
        dependencies, _, _ = cascade._persist_model(
            store=self._artifacts, value=execution.dependencies, kind=_DEPENDENCIES_KIND
        )
        adjudications, _, _ = cascade._persist_model(
            store=self._artifacts, value=execution.adjudications, kind=_ADJUDICATIONS_KIND
        )
        origin = EpochTransitionOriginStatement(
            previous_epoch_manifest_ref=execution.previous_epoch_manifest_ref,
            current_epoch_production_receipt_ref=execution.current_epoch_production_receipt_ref,
            transition_artifact_ref=record.artifact_ref,
            transition_content_hash=execution.transition.transition_content_hash,
            transition_raw_content_hash=record.raw_blob_bytes_hash,
            signed_artifact_evidence_ref=execution.signed.evidence_record_ref,
            signing_profile_ref=record.signing_profile_ref,
            signer_provenance_ref=record.signer_provenance_ref,
            admitted_signing_profile=profile,
            dependency_receipt_ref=dependencies,
            dependency_receipt_content_hash=str(dependencies.artifact_id),
            adjudication_receipt_ref=adjudications,
            adjudication_receipt_content_hash=str(adjudications.artifact_id),
            dependency_denominator_ref=execution.dependencies.denominator_ref,
            adjudication_denominator_ref=execution.adjudications.denominator_ref,
            authority_purpose=execution.transition.authority_purpose,
            requested_query_context_ref=execution.transition.requested_query_context_ref,
        )
        self._verify_origin(origin)
        ref, _, _ = cascade._persist_model(store=self._artifacts, value=origin, kind=_ORIGIN_KIND)
        index_raw = cascade._canonical_bytes(ref)
        scope_root = self._scope_root()
        index_path = scope_root / f"{ref.artifact_id.hex}.json"
        with (scope_root / "origins.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if index_path.exists():
                if index_path.read_bytes() != index_raw:
                    raise ValueError("epoch_origin_owner_index_conflict")
            else:
                with tempfile.NamedTemporaryFile(
                    dir=scope_root, prefix=".origin-", delete=False
                ) as handle:
                    scratch = Path(handle.name)
                    handle.write(index_raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(scratch, index_path)
                    directory = os.open(scope_root, os.O_RDONLY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                finally:
                    scratch.unlink(missing_ok=True)
        self.resolve_admitted_origin(
            origin_ref=ref,
            transition_artifact_ref=record.artifact_ref,
            signed_artifact_evidence_ref=execution.signed.evidence_record_ref,
            signing_profile_ref=record.signing_profile_ref,
            authority_purpose=origin.authority_purpose,
            requested_query_context_ref=origin.requested_query_context_ref,
        )
        self.resolve_admitted_origin_for_transition(
            transition_artifact_ref=record.artifact_ref,
            authority_purpose=origin.authority_purpose,
            requested_query_context_ref=origin.requested_query_context_ref,
        )
        return ref

    def _indexed_origins(self) -> tuple[tuple[ArtifactRef, EpochTransitionOriginStatement], ...]:
        rows = []
        scope_root = self._scope_root()
        with (scope_root / "origins.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
            for path in sorted(scope_root.glob("*.json")):
                raw = path.read_bytes()
                ref = ArtifactRef.model_validate(canon.from_canonical_bytes(raw))
                if (
                    path.name != f"{ref.artifact_id.hex}.json"
                    or cascade._canonical_bytes(ref) != raw
                ):
                    raise ValueError("epoch_origin_owner_index_corrupt")
                origin = cascade._read_model(
                    store=self._artifacts,
                    ref=ref,
                    model=EpochTransitionOriginStatement,
                    kind=_ORIGIN_KIND,
                )
                if not isinstance(origin, EpochTransitionOriginStatement):
                    raise ValueError("epoch_origin_owner_index_corrupt")
                rows.append((ref, origin))
        return tuple(rows)

    def resolve_admitted_origin(
        self,
        *,
        origin_ref: ArtifactRef,
        transition_artifact_ref: ArtifactRef,
        signed_artifact_evidence_ref: ArtifactRef,
        signing_profile_ref: ArtifactRef,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> EpochTransitionOriginStatement:
        """Resolve owner membership and independently recheck every origin binding."""

        origins = [origin for ref, origin in self._indexed_origins() if ref == origin_ref]
        if len(origins) != 1:
            raise ValueError("epoch_transition_origin_not_admitted")
        origin = origins[0]
        if (
            origin.transition_artifact_ref != transition_artifact_ref
            or origin.signed_artifact_evidence_ref != signed_artifact_evidence_ref
            or origin.signing_profile_ref != signing_profile_ref
            or origin.authority_purpose != authority_purpose
            or origin.requested_query_context_ref != requested_query_context_ref
        ):
            raise ValueError("epoch_transition_origin_binding_mismatch")
        self._verify_origin(origin)
        return origin

    def resolve_admitted_origin_for_transition(
        self,
        *,
        transition_artifact_ref: ArtifactRef,
        authority_purpose: str,
        requested_query_context_ref: Digest,
    ) -> EpochTransitionOriginStatement:
        """Find the unique admitted origin without accepting a caller's origin ref."""

        rows = [
            (ref, origin)
            for ref, origin in self._indexed_origins()
            if origin.transition_artifact_ref == transition_artifact_ref
            and origin.authority_purpose == authority_purpose
            and origin.requested_query_context_ref == requested_query_context_ref
        ]
        if len(rows) != 1:
            raise ValueError("epoch_transition_origin_absent_or_ambiguous")
        ref, origin = rows[0]
        return self.resolve_admitted_origin(
            origin_ref=ref,
            transition_artifact_ref=transition_artifact_ref,
            signed_artifact_evidence_ref=origin.signed_artifact_evidence_ref,
            signing_profile_ref=origin.signing_profile_ref,
            authority_purpose=authority_purpose,
            requested_query_context_ref=requested_query_context_ref,
        )
