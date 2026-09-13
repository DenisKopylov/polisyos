"""Canonical execution origin is separate from exact transition signature evidence."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polisyos.core import artifacts, security
from polisyos.core.artifacts.signed_evidence import FileSystemSignedArtifactEvidenceRepository


def _module():
    name = "polisyos.runtime.quality.epoch_transition_origin"
    assert importlib.util.find_spec(name) is not None, "canonical execution origin owner missing"
    return importlib.import_module(name)


def _producer_fixture(
    tmp_path: Path,
    *,
    with_owner: bool = True,
    authority_purpose: str = "decision_validity",
    disposition: str | None = None,
    store: artifacts.FileSystemCAS | None = None,
    trusted_signer: bool = True,
):
    module = _module()
    from polisyos.runtime.quality import epoch_validity_cascade as cascade
    from tests.unit.runtime.quality.test_epoch_validity_cascade import (
        _ref,
        _transition_history_adapter,
        _transition_history_fixture,
    )

    fixture = _transition_history_fixture(
        tmp_path, authority_purpose=authority_purpose, store=store
    )
    target = fixture.store.put_bytes(
        b"isolated-test-target",
        artifacts.ArtifactWriteOptions(
            kind="test.epoch_target", media_type="application/octet-stream"
        ),
    )
    edges = (
        cascade.EpochDependencyEdge(
            source_ref=fixture.previous_ref,
            target_ref=target,
            relation="invalidates",
            authority_purpose=authority_purpose,
        ),
    )
    graph = cascade.EpochDependencyGraph(
        edges=edges,
        denominator_ref=cascade._semantic_hash(
            "polisyos.epoch.dependency-graph.v1", {"edges": edges}
        ),
    )
    dependencies = cascade.EpochDependencyDenominatorReceipt(
        denominator_ref=cascade.epoch_dependency_outer_denominator_ref(
            certificate_bindings=(), dependency_graph=graph
        ),
        certificate_bindings=(),
        dependency_graph=graph,
        target_refs=(target,),
        predicate_class="independently_reconciled",
    )
    events = ()
    owners = ()
    if disposition is not None:
        event_ref = fixture.store.put_bytes(
            b"isolated-advisory-event",
            artifacts.ArtifactWriteOptions(
                kind="test.monitor_event", media_type="application/octet-stream"
            ),
        )
        owner_ref = fixture.store.put_bytes(
            b"isolated-owner-result",
            artifacts.ArtifactWriteOptions(
                kind="test.owner_disposition", media_type="application/octet-stream"
            ),
        )
        events = (
            cascade.AdvisoryPerturbationEvent(
                event_ref=event_ref,
                target_ref=target,
                source_class="incident",
                scope="dependency_descendants",
                event_kind="invalidate",
                authority_purpose=authority_purpose,
                observed_epoch_ref=fixture.previous.epoch_ref,
            ),
        )
        owners = (
            cascade.OwnerAdjudicatedTargetDisposition(
                target_ref=target,
                event_ref=event_ref,
                disposition=disposition,
                owner_evidence_ref=owner_ref,
                owner_evidence_content_hash=str(owner_ref.artifact_id),
                authority_purpose=authority_purpose,
                predicate_class="independently_reconciled",
            ),
        )
    adjudications = cascade.EpochPerturbationAdjudicationReceipt(
        denominator_ref=cascade._semantic_hash(
            "polisyos.epoch.perturbation-adjudication-denominator.v1",
            {"advisory_events": events, "owner_dispositions": owners},
        ),
        advisory_events=events,
        owner_dispositions=owners,
        predicate_class="independently_reconciled",
    )

    class IsolatedInputs:
        """Test-controlled denominator; not a production completeness witness."""

        def resolve_complete_epoch_dependencies(self, **kwargs):
            return dependencies

        def resolve_complete_owner_adjudications(self, **kwargs):
            return adjudications

    key = Ed25519PrivateKey.generate()
    signer = artifacts.Ed25519Signer(key)
    verifier = artifacts.Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(
        key.public_key() if trusted_signer else Ed25519PrivateKey.generate().public_key(),
        identity="isolated-signature-owner",
    )
    repository = FileSystemSignedArtifactEvidenceRepository(fixture.store)
    profile = fixture.store.put_bytes(
        b"isolated admitted profile",
        artifacts.ArtifactWriteOptions(kind="test.profile", media_type="application/octet-stream"),
    )
    admission = fixture.store.put_bytes(
        b"isolated owner admission",
        artifacts.ArtifactWriteOptions(
            kind="test.admission", media_type="application/octet-stream"
        ),
    )
    query = fixture.current.requested_query_context_ref

    class Profiles:
        available = True
        signature_valid = True

        def resolve_admitted_signing_profile(
            self, *, signing_profile_ref, authority_purpose, requested_query_context_ref
        ):
            if (
                not self.available
                or signing_profile_ref != profile
                or authority_purpose != fixture.current.authority_purpose
                or requested_query_context_ref != query
            ):
                raise ValueError("profile not admitted")
            return module.AdmittedEpochTransitionSigningProfile(
                signing_profile_ref=profile,
                signing_profile_content_hash=str(profile.artifact_id),
                admission_ref=admission,
                admission_content_hash=str(admission.artifact_id),
                authority_purpose=authority_purpose,
                requested_query_context_ref=requested_query_context_ref,
            )

        def verify_transition_signature(self, *, evidence, **kwargs):
            return self.signature_valid and security.verify_signed_evidence(
                evidence, verifier=verifier
            )

    class Signing:
        retained = None

        def sign_transition(self, *, transition_bytes, **kwargs):
            if self.retained is not None:
                exact = repository.read_exact(evidence_record_ref=self.retained.evidence_record_ref)
                if exact.blob_bytes == transition_bytes:
                    return self.retained
            self.retained = repository.persist_signed(
                blob_bytes=transition_bytes,
                write_options=artifacts.ArtifactWriteOptions(
                    kind="polisyos.epoch.validity_transition",
                    media_type="application/vnd.polisyos.chronology+json",
                ),
                signer=signer,
                signing_profile_ref=profile,
                signer_provenance_ref=_ref("signer-origin"),
            )
            return self.retained

    profiles = Profiles()
    owner = module.FileEpochTransitionOriginOwner(
        root=tmp_path / "origins",
        artifacts=fixture.store,
        signed_artifacts=repository,
        signing_profiles=profiles,
    )
    producer = cascade.EpochValidityTransitionProducer(
        dependency_inventory=IsolatedInputs(),
        adjudications=IsolatedInputs(),
        epoch_history=_transition_history_adapter(fixture),
        signed_artifacts=repository,
        signing_authority=Signing(),
        origins=owner if with_owner else None,
    )
    kwargs = {
        "previous_epoch_ref": fixture.previous_ref,
        "current_epoch_receipt_ref": fixture.current_receipt.receipt_ref,
        "requested_query_context_ref": query,
        "authority_purpose": authority_purpose,
    }
    return producer, owner, profiles, fixture, repository, kwargs


def _read(owner, result):
    return owner.resolve_admitted_origin(
        origin_ref=result.producer_identity_ref,
        transition_artifact_ref=result.transition_artifact_ref,
        signed_artifact_evidence_ref=result.signed_artifact_evidence_ref,
        signing_profile_ref=result.signing_profile_ref,
        authority_purpose=result.authority_purpose,
        requested_query_context_ref=result.requested_query_context_ref,
    )


def test_canonical_producer_persists_independently_readable_execution_origin(
    tmp_path: Path,
) -> None:
    producer, owner, profiles, fixture, repository, kwargs = _producer_fixture(tmp_path)
    from polisyos.runtime.quality import epoch_validity_cascade as cascade

    result = producer.produce_and_persist(**kwargs)
    assert isinstance(result, cascade.PersistedEpochValidityTransition)
    assert result.producer_identity_ref != result.signer_provenance_ref
    origin = _read(owner, result)
    assert origin.previous_epoch_manifest_ref == fixture.previous_ref
    assert origin.current_epoch_production_receipt_ref == fixture.current_receipt.receipt_ref
    assert origin.transition_artifact_ref == result.transition_artifact_ref
    restarted = _module().FileEpochTransitionOriginOwner(
        root=tmp_path / "origins",
        artifacts=fixture.store,
        signed_artifacts=repository,
        signing_profiles=profiles,
    )
    assert _read(restarted, result) == origin


def test_cas_origin_copy_cannot_substitute_for_owner_execution_membership(tmp_path: Path) -> None:
    producer, owner, profiles, fixture, repository, kwargs = _producer_fixture(tmp_path)
    from polisyos.runtime.quality import epoch_validity_cascade as cascade

    result = producer.produce_and_persist(**kwargs)
    assert isinstance(result, cascade.PersistedEpochValidityTransition)
    # Exact same artifact/signature/profile/origin bytes, different empty owner index.
    foreign_owner = _module().FileEpochTransitionOriginOwner(
        root=tmp_path / "foreign-origins",
        artifacts=fixture.store,
        signed_artifacts=repository,
        signing_profiles=profiles,
    )
    with pytest.raises(ValueError, match="origin_not_admitted"):
        _read(foreign_owner, result)
    assert _read(owner, result)


@pytest.mark.parametrize("missing", ["owner", "profile", "signature"])
def test_exact_signed_bytes_do_not_replace_origin_or_profile_admission(
    tmp_path: Path, missing: str
) -> None:
    producer, _, profiles, _, _, kwargs = _producer_fixture(
        tmp_path, with_owner=missing != "owner", trusted_signer=missing != "signature"
    )
    from polisyos.runtime.quality import epoch_validity_cascade as cascade

    profiles.available = missing != "profile"
    result = producer.produce_and_persist(**kwargs)
    assert isinstance(result, cascade.EpochTransitionSigningNonReceipt)
    assert result.code == "epoch_transition_exact_evidence_unavailable"


def test_origin_readback_rechecks_admission_and_query(tmp_path: Path) -> None:
    producer, owner, profiles, _, _, kwargs = _producer_fixture(tmp_path)
    from polisyos.runtime.quality import epoch_validity_cascade as cascade
    from tests.unit.runtime.quality.test_epoch_validity_cascade import _digest

    result = producer.produce_and_persist(**kwargs)
    assert isinstance(result, cascade.PersistedEpochValidityTransition)
    with pytest.raises(ValueError):
        _read(
            owner, result.model_copy(update={"requested_query_context_ref": _digest("wrong-query")})
        )
    profiles.available = False
    with pytest.raises(ValueError):
        _read(owner, result)


def test_origin_index_is_scoped_at_operation_time_and_survives_restart(tmp_path: Path) -> None:
    """A valid origin in another tenant/cell is not a member of this owner scope."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality import epoch_validity_cascade as cascade

    store = artifacts.FileSystemCAS(
        tmp_path / "cas", ownership_enforced=True, ownership_requires_scope=False
    )
    root = tmp_path / "shared-origins"
    retained = []
    for tenant, cell in (("tenant-a", "cell-a"), ("tenant-b", "cell-a"), ("tenant-a", "cell-b")):
        with tenant_scope(None, tenant_id=tenant, cell_id=cell):
            producer, _, profiles, _fixture, repository, kwargs = _producer_fixture(
                tmp_path / f"{tenant}-{cell}", store=store,
                authority_purpose=f"origin-scope:{tenant}:{cell}",
            )
            owner = _module().FileEpochTransitionOriginOwner(
                root=root, artifacts=store, signed_artifacts=repository, signing_profiles=profiles
            )
            producer._origins = owner
            result = producer.produce_and_persist(**kwargs)
            assert isinstance(result, cascade.PersistedEpochValidityTransition), (tenant, cell)
            assert _read(owner, result)
            retained.append((tenant, cell, profiles, repository, result))

    # The same object follows the active scope after restart, not its construction context.
    for tenant, cell, profiles, repository, result in retained:
        owner = _module().FileEpochTransitionOriginOwner(
            root=root, artifacts=store, signed_artifacts=repository, signing_profiles=profiles
        )
        with tenant_scope(None, tenant_id=tenant, cell_id=cell):
            assert _read(owner, result)
            for other_tenant, other_cell, _, _, other in retained:
                if (other_tenant, other_cell) != (tenant, cell):
                    with pytest.raises(ValueError, match=r"^epoch_transition_origin_not_admitted$"):
                        _read(owner, other)
    # CLI's unscoped index is separate and cannot discover tenant origins.
    with pytest.raises(ValueError, match=r"^epoch_transition_origin_not_admitted$"):
        _read(owner, retained[0][-1])
