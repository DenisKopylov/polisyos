"""Canonical epoch production and verification at the strict Decision Validity intake.

The registered control-plane epoch-batch route reaches this composition through
DecisionValidityService. Runtime and Scientist denominators remain separate;
the existing reconciliation reader admits their independently derived relation.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Literal

from polisyos.core import artifacts, canon, contracts
from polisyos.core.contracts import (
    DecisionValidityEpochImpactSnapshotHandle,
    DecisionValidityStatus,
    EpochTransitionDenominatorReconciliationHandle,
    EpochTransitionVerificationReceipt,
    EpochValidityBatchTarget,
    PersistedEpochTransitionDenominatorReconciliation,
)
from polisyos.runtime.quality.epoch_denominator_reconciliation import (
    EpochDenominatorReconciliationNonReceipt,
    EpochTransitionDenominatorReconciliationProducer,
    EpochTransitionDenominatorReconciliationReader,
    _read_transition_exact,
)
from polisyos.runtime.quality.epoch_validity_cascade import EpochTransitionSigningNonReceipt
from polisyos.scientist import DecisionValidityService

if TYPE_CHECKING:
    from polisyos.runtime.quality.epoch_certificate_issuance import DecisionPacketEpochIssuanceOwner
    from polisyos.runtime.quality.epoch_deployment import EpochDeployment
    from polisyos.runtime.quality.epoch_transition_inputs import EpochTransitionProductionBridge
    from polisyos.runtime.quality.epoch_transition_origin import FileEpochTransitionOriginOwner

_PURPOSE = "decision_validity_epoch_transition"


class ProducingEpochDenominatorReconciliationReader:
    """Produce the exact first-admission sidecar, then invoke the strict reader.

    Replay delegates the frozen handle directly and never produces a replacement.
    The existing reader retains its missing, malformed and ambiguous refusals.
    """

    def __init__(
        self, *, store: artifacts.ArtifactStore, verifier_provenance_ref: artifacts.ArtifactRef
    ) -> None:
        self.verifier_provenance_ref = verifier_provenance_ref
        self._producer = EpochTransitionDenominatorReconciliationProducer(
            store=store,
            verifier_provenance_ref=verifier_provenance_ref,
        )
        self._reader = EpochTransitionDenominatorReconciliationReader(
            store=store,
            verifier_provenance_ref=verifier_provenance_ref,
        )

    def resolve_for_first_admission(
        self,
        *,
        transition_artifact_ref: artifacts.ArtifactRef,
        transition_content_hash: str,
        requested_query_context_ref: str,
        authority_purpose: Literal["decision_validity_epoch_transition"],
        scientist_snapshot_handle: DecisionValidityEpochImpactSnapshotHandle,
    ) -> PersistedEpochTransitionDenominatorReconciliation:
        """Derive the missing artifact without relaxing its consuming predicate."""

        produced = self._producer.produce_and_persist(
            transition_artifact_ref=transition_artifact_ref,
            scientist_snapshot_handle=scientist_snapshot_handle,
            requested_query_context_ref=requested_query_context_ref,
            authority_purpose=authority_purpose,
        )
        if isinstance(produced, EpochDenominatorReconciliationNonReceipt):
            raise ValueError(produced.code)
        return self._reader.resolve_for_first_admission(
            transition_artifact_ref=transition_artifact_ref,
            transition_content_hash=transition_content_hash,
            scientist_snapshot_handle=scientist_snapshot_handle,
            requested_query_context_ref=requested_query_context_ref,
            authority_purpose=authority_purpose,
        )

    def resolve_exact(
        self,
        *,
        handle: EpochTransitionDenominatorReconciliationHandle,
    ) -> PersistedEpochTransitionDenominatorReconciliation:
        """Read the original immutable relation after admission."""

        return self._reader.resolve_exact(handle=handle)


class CanonicalEpochTransitionVerifier:
    """Verify actual canonical origin before deriving the owner batch receipt."""

    def __init__(
        self,
        *,
        store: artifacts.ArtifactStore,
        origins: FileEpochTransitionOriginOwner,
        decision_validity_owner: DecisionValidityService,
        production_bridge: EpochTransitionProductionBridge | None = None,
    ) -> None:
        self._store = store
        self._origins = origins
        self._owner = decision_validity_owner
        self._production_bridge = production_bridge
        # This identifies this running verifier implementation, not an institution
        # or a permission grant. Admission below is always recomputed from evidence.
        self.verifier_provenance_ref = self._persist_execution_provenance()

    def _persist_execution_provenance(self) -> artifacts.ArtifactRef:
        # Re-emitting our own canonical bytes uses the ordinary CAS writer in the
        # active tenant/cell scope. It never grants access to someone else's input.
        return self._store.put_bytes(
            canon.to_canonical_bytes(
                {
                    "canonical_verifier": f"{type(self).__module__}.{type(self).__qualname__}",
                    "rule_version": "polisyos.epoch.canonical-transition-verification.v1",
                    "authority_purpose": _PURPOSE,
                },
                canon.CanonSpec(),
            ),
            artifacts.ArtifactWriteOptions(
                kind="chronology.epoch_transition_verifier", media_type="application/json"
            ),
        )

    def verify(
        self,
        *,
        transition_artifact_ref: artifacts.ArtifactRef,
        requested_query_context_ref: str,
        expected_authority_purpose: str,
    ) -> EpochTransitionVerificationReceipt:
        """Read exact origin/signature/basis and freeze a complete Scientist projection."""

        if expected_authority_purpose != _PURPOSE:
            raise ValueError("authority_purpose_mismatch")
        if self._persist_execution_provenance() != self.verifier_provenance_ref:
            raise ValueError("verifier_provenance_untrusted")
        frozen = self._owner.resolve_epoch_admitted_impact_snapshot(
            transition_artifact_ref=transition_artifact_ref,
            requested_query_context_ref=requested_query_context_ref,
        )
        if frozen is None and self._production_bridge is not None:
            produced = self._production_bridge.produce_for_requested_transition(
                transition_artifact_ref=transition_artifact_ref,
                requested_query_context_ref=requested_query_context_ref,
                authority_purpose=expected_authority_purpose,
            )
            if isinstance(produced, EpochTransitionSigningNonReceipt):
                raise ValueError(produced.code)
        try:
            # Rechecks independent profile admission, cryptographic signature,
            # owner origin membership and the frozen executed input receipts.
            self._origins.resolve_admitted_origin_for_transition(
                transition_artifact_ref=transition_artifact_ref,
                authority_purpose=expected_authority_purpose,
                requested_query_context_ref=requested_query_context_ref,
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("signature_unverified") from exc
        transition, raw = _read_transition_exact(store=self._store, ref=transition_artifact_ref)
        if transition.authority_purpose != expected_authority_purpose:
            raise ValueError("authority_purpose_mismatch")
        if transition.requested_query_context_ref != requested_query_context_ref:
            raise ValueError("query_context_mismatch")
        snapshot = frozen or self._owner.persist_epoch_impact_snapshot_for_targets(
            target_refs=tuple(row.target_ref for row in transition.target_vector.rows),
            requested_query_context_ref=requested_query_context_ref,
        )
        targets_by_id = {
            str(row.target_ref.artifact_id): row for row in transition.target_vector.rows
        }
        owners_by_key = {row.dependency_key: row for row in snapshot.snapshot.owner_rows}
        batch_targets = []
        for target in snapshot.snapshot.targets:
            owner = owners_by_key[target.dependency_key]
            disposition = targets_by_id.get(owner.artifact_id)
            if disposition is None:
                raise ValueError("target_denominator_mismatch")
            batch_targets.append(
                EpochValidityBatchTarget(
                    packet_ref=target.packet_ref,
                    dependency_key=target.dependency_key,
                    decision_lineage_key=target.decision_lineage_key,
                    status=_decision_status(disposition.disposition),
                    reason=f"epoch_owner_disposition:{disposition.disposition}",
                )
            )
        if not batch_targets or not snapshot.snapshot.requested_dependency_keys:
            # The strict consumer contract excludes an empty decision batch.
            raise ValueError("target_denominator_mismatch")
        return EpochTransitionVerificationReceipt(
            transition_artifact_ref=transition_artifact_ref,
            transition_content_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
            requested_query_context_ref=requested_query_context_ref,
            authority_purpose=expected_authority_purpose,
            verifier_provenance_ref=self.verifier_provenance_ref,
            dependency_keys=snapshot.snapshot.requested_dependency_keys,
            dependency_denominator_ref=snapshot.snapshot.decision_impact_denominator_ref,
            adjudication_denominator_ref=transition.adjudication_denominator_ref,
            targets=tuple(batch_targets),
            predicate_class="independently_reconciled",
        )


def _decision_status(disposition: str) -> DecisionValidityStatus:
    # CB-D02/D04: an invalidated certificate or requested reissue requires
    # revalidation; a request is never evidence of a completed replacement.
    if disposition in {"invalidate", "reissue"}:
        return DecisionValidityStatus.STALE
    if disposition in {"review_required", "contested"}:
        return DecisionValidityStatus.REVIEW_REQUIRED
    if disposition == "withdraw":
        return DecisionValidityStatus.WITHDRAWN
    if disposition == "supersede":
        return DecisionValidityStatus.SUPERSEDED
    if disposition in {"unchanged", "annotation_only"}:
        # ACTIVE is the existing lattice identity. It does not clear existing
        # sticky triggers; the unchanged owner evaluator composes the result.
        return DecisionValidityStatus.ACTIVE
    raise ValueError("epoch_transition_disposition_unresolved")


def build_epoch_decision_validity_owner(
    *,
    store: artifacts.ArtifactStore,
    origins: FileEpochTransitionOriginOwner | None = None,
    production_bridge: EpochTransitionProductionBridge | None = None,
) -> DecisionValidityService:
    """Compose real intake while leaving unconfigured production slots empty."""

    owner = DecisionValidityService(store)
    if origins is None:
        return owner
    configure_epoch_decision_validity_owner(
        owner=owner,
        origins=origins,
        production_bridge=production_bridge,
    )
    return owner


def configure_epoch_decision_validity_owner(
    *,
    owner: DecisionValidityService,
    origins: FileEpochTransitionOriginOwner,
    production_bridge: EpochTransitionProductionBridge | None = None,
) -> None:
    """Install collaborators on the same container-owned service before startup.

    Promotion and Claim lifecycle already hold this owner identity; composition
    does not replace it with a second owner over a divergent store or index.
    """

    store = owner._store
    if origins._artifacts is not store:
        raise ValueError("epoch_transition_origin_owner_store_mismatch")
    verifier = CanonicalEpochTransitionVerifier(
        store=store,
        origins=origins,
        decision_validity_owner=owner,
        production_bridge=production_bridge,
    )
    owner._epoch_transition_verifier = verifier
    owner._epoch_denominator_reconciliation_reader = ProducingEpochDenominatorReconciliationReader(
        store=store,
        verifier_provenance_ref=verifier.verifier_provenance_ref,
    )


def configure_deployed_epoch_intake(
    *,
    owner: DecisionValidityService,
    deployment: EpochDeployment,
) -> None:
    """Wire the existing control owner to production from configured evidence.

    Public trust, exact signed evidence and native history are deployment inputs.
    An absent native perturbation admission owner remains a typed refusal in the
    complete source reader; a monitor inventory cannot manufacture that premise.
    """

    from pathlib import Path

    from polisyos.core import FileSystemSignedArtifactEvidenceRepository
    from polisyos.runtime.quality import epoch_validity_cascade as cascade
    from polisyos.runtime.quality.epoch_certificate_issuance import DecisionPacketEpochIssuanceOwner
    from polisyos.runtime.quality.epoch_deployment import EpochDeployment
    from polisyos.runtime.quality.epoch_transition_inputs import (
        CanonicalEpochDependencyDenominatorProvider,
        CanonicalEpochPerturbationAdjudicationProvider,
        CanonicalEpochTransitionSourceResolver,
        EpochTransitionProductionBridge,
        NativeEpochSemanticBasisDeltaProvider,
        ResolvedEpochTransitionSource,
    )
    from polisyos.runtime.quality.epoch_transition_origin import FileEpochTransitionOriginOwner
    from polisyos.runtime.quality.semantic_epoch_store import FileSemanticEpochHistoryRepository

    if type(deployment) is not EpochDeployment:
        raise TypeError("epoch intake requires a factory-produced deployment")
    if (
        not deployment.has_transition_evidence_configuration
        or deployment.native_epoch_history_root is None
    ):
        return
    store = owner._store
    root = getattr(store, "root", None)
    if not isinstance(root, Path):
        raise TypeError("epoch intake requires the canonical local artifact owner")
    history = FileSemanticEpochHistoryRepository(
        root=deployment.native_epoch_history_root,
        artifacts=store,
    )
    signed = FileSystemSignedArtifactEvidenceRepository(store)
    origins = FileEpochTransitionOriginOwner(
        root=root / "epoch-transition-origins",
        artifacts=store,
        signed_artifacts=signed,
        signing_profiles=deployment,
    )
    issuances = DecisionPacketEpochIssuanceOwner.for_store(
        store=store,
        history=history,
        input_resolver=deployment.epoch_certificate_issuance_input_resolver,
    )
    source_resolver = CanonicalEpochTransitionSourceResolver(artifacts=store, history=history)

    class ConfiguredSigningAuthority:
        """Read an exact externally signed result for this canonical execution."""

        def sign_transition(
            self,
            *,
            transition_bytes: bytes,
            authority_purpose: str,
            requested_query_context_ref: str,
        ) -> (
            contracts.chronology.PersistedSignedArtifactEvidence
            | cascade.EpochTransitionSigningNonReceipt
        ):
            try:
                return deployment.resolve_exact_signed_transition(
                    transition_bytes=transition_bytes,
                    authority_purpose=authority_purpose,
                    requested_query_context_ref=requested_query_context_ref,
                ).persisted
            except (KeyError, OSError, RuntimeError, TypeError, ValueError):
                return cascade.EpochTransitionSigningNonReceipt(
                    status="not_established",
                    code="epoch_transition_exact_evidence_unavailable",
                    predicate_class="not_established",
                )

    def producer(source: ResolvedEpochTransitionSource) -> cascade.EpochValidityTransitionProducer:
        dependencies = CanonicalEpochDependencyDenominatorProvider(
            issuance_owner=issuances,
            source=source,
        )
        return cascade.EpochValidityTransitionProducer(
            dependency_inventory=dependencies,
            adjudications=CanonicalEpochPerturbationAdjudicationProvider(
                artifacts=store,
                dependency_inventory=dependencies,
                owner_admissions=deployment.epoch_perturbation_adjudication_provider,
                owner_evidence=deployment.epoch_owner_disposition_evidence_reader,
                native_basis=NativeEpochSemanticBasisDeltaProvider(
                    artifacts=store,
                    source_resolver=source_resolver,
                    dependency_inventory=dependencies,
                ),
            ),
            epoch_history=cascade.FileSemanticEpochTransitionHistoryAdapter(
                artifacts=store,
                history=history,
            ),
            signed_artifacts=signed,
            signing_authority=ConfiguredSigningAuthority(),
            origins=origins,
        )

    configure_epoch_decision_validity_owner(
        owner=owner,
        origins=origins,
        production_bridge=EpochTransitionProductionBridge(
            source_resolver=source_resolver,
            producer_factory=producer,
        ),
    )


def build_deployed_epoch_issuance_owner(
    *,
    store: artifacts.ArtifactStore,
    deployment: EpochDeployment,
) -> DecisionPacketEpochIssuanceOwner:
    """Capture the exact deployment input resolver at the real packet producer seam."""

    from polisyos.runtime.quality.epoch_certificate_issuance import DecisionPacketEpochIssuanceOwner
    from polisyos.runtime.quality.semantic_epoch_store import FileSemanticEpochHistoryRepository

    history = (
        FileSemanticEpochHistoryRepository(
            root=deployment.native_epoch_history_root, artifacts=store
        )
        if deployment.native_epoch_history_root is not None
        else None
    )
    return DecisionPacketEpochIssuanceOwner.for_store(
        store=store,
        history=history,
        input_resolver=deployment.epoch_certificate_issuance_input_resolver,
    )
