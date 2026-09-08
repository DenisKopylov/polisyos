"""Behavioral witnesses for Claim supersession owner-event production."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, SchemaInfo
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.scientist.evidence.claims.export import ClaimExportAudience, ClaimLedgerExport
from polisyos.scientist.evidence.claims.head_index import (
    ArtifactStoreDecisionPacketRootRepository,
    ClaimLedgerHeadResolutionNonReceipt,
    FilesystemArtifactStoreClaimRootWalk,
    _RepositoryClaimLedgerOwner,
)
from polisyos.scientist.evidence.claims.lifecycle import ClaimLifecycleAction
from polisyos.scientist.evidence.claims.owner_events import (
    OWNER_EVENT_KIND,
    ClaimSupersessionAppointment,
    ClaimSupersessionAuthority,
    persist_claim_supersession_appointment,
    persist_claim_supersession_successor,
    produce_claim_supersession_owner_event,
    read_claim_supersession_candidate,
)
from polisyos.scientist.governance.continuous.lifecycle_bridge import (
    build_epoch_claim_lifecycle_bridge,
    load_lifecycle_bridge_result,
)
from polisyos.scientist.governance.continuous.monitors import (
    GovernanceMonitorEvent,
    LegalChangePerturbation,
    SupersessionCandidateRequest,
    persist_governance_monitor_event,
)
from tests.unit.scientist.evidence.claims.test_head_index import (
    _fixture_policy,
    _FixtureIssuanceVerifier,
    _FixturePolicyResolver,
    _FixtureRootIssuer,
    _initialize_owner_ledger,
)


@pytest.fixture
def owner_event_case(tmp_path: Path):
    """Use explicit synthetic root authority; production defaults remain unappointed."""

    store = FileSystemCAS(tmp_path / "cas")
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
        root_issuer=_FixtureRootIssuer(store),
        issuance_verifier=_FixtureIssuanceVerifier(store),
        head_index_root=tmp_path / "heads",
        decision_packets=ArtifactStoreDecisionPacketRootRepository(
            store=store,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store, artifact_root=store.root
        ),
    )
    prepared, packet_ref, initial = _initialize_owner_ledger(
        owner=owner,
        store=store,
        run_id="owner-event-probe",
        claim_id="predecessor",
    )
    evidence_ref = store.put_bytes(
        b"A legal change has been observed, but replacement authority is unappointed.",
        ArtifactWriteOptions(kind="fixture.legal_change", media_type="text/plain"),
    )
    monitor = GovernanceMonitorEvent(
        event_id="supersession-owner-event-probe",
        decision_packet_ref=packet_ref,
        event_type="policy_context_drift",
        severity="block",
        affected_claim_ids=["predecessor"],
        reason="A caller claims that a replacement has been verified.",
        occurred_at=datetime.now(UTC),
        observed_epoch_ref="sha256:" + "e" * 64,
        perturbation=LegalChangePerturbation(legal_change_evidence_ref=evidence_ref),
        metadata={"superseded_by_claim_id": "absent-successor"},
    )
    persisted_monitor = persist_governance_monitor_event(store, monitor)
    from polisyos.scientist.evidence.claims.audit import _load_append_only_claim_ledger

    ledger = _load_append_only_claim_ledger(store, prepared.initial_ledger_ref)
    successor = ledger.current_claims[0].model_copy(
        update={"claim_id": "actual-successor", "text": "The resolved replacement claim."}
    )
    successor_ref = persist_claim_supersession_successor(store=store, claim=successor)
    return store, owner, prepared, initial, persisted_monitor, successor_ref


def _bridge(case, owner=None):
    store, default_owner, _, _, monitor, _ = case
    return build_epoch_claim_lifecycle_bridge(
        completed_batches=None,
        claim_owner=owner or default_owner,
        artifacts=store,
    ).bridge_monitor_event(
        monitor_event_ref=monitor.event_ref,
        actor_id="runtime.control.decision_validity.monitor_event",
    )


def _event(case, *, signer=None):
    store, _, prepared, _, monitor, successor_ref = case
    return produce_claim_supersession_owner_event(
        store=store,
        owner_key=prepared.owner_key,
        monitor_event_ref=monitor.event_ref,
        prior_ledger_ref=prepared.initial_ledger_ref,
        predecessor_claim_id="predecessor",
        successor_claim_ref=successor_ref,
        effective_at=datetime.now(UTC),
        signer=signer,
        signer_identity="fixture-supersession-owner" if signer else None,
    )


def _signed_authority(case, *, wrong_scope=False):
    store, owner, prepared, _, _, _ = case
    grant_key = Ed25519PrivateKey.generate()
    event_key = Ed25519PrivateKey.generate()
    grant_signer, event_signer = Ed25519Signer(grant_key), Ed25519Signer(event_key)
    grant_verifier, event_verifier = Ed25519Verifier(), Ed25519Verifier()
    grant_verifier.add_trusted_key(
        grant_key.public_key(), identity="fixture-appointing-institution"
    )
    event_verifier.add_trusted_key(event_key.public_key(), identity="fixture-supersession-owner")
    scope = prepared.owner_key
    if wrong_scope:
        scope = scope.model_copy(update={"claim_owner_ref": "a-different-owner"})
    now = datetime.now(UTC)
    grant = ClaimSupersessionAppointment(
        owner_key=scope,
        signer_key_id=event_signer.key_id,
        signer_identity="fixture-supersession-owner",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )
    grant_ref = persist_claim_supersession_appointment(
        store=store,
        appointment=grant,
        signer=grant_signer,
        signer_identity="fixture-appointing-institution",
    )
    authority = ClaimSupersessionAuthority(
        appointment_ref=grant_ref,
        appointment_verifier=grant_verifier,
        event_verifier=event_verifier,
    )
    return replace(owner, owner_event_authority=authority), event_signer


def _requested_case(case):
    store, owner, prepared, initial, monitor, successor_ref = case
    requested = monitor.event.model_copy(
        update={
            "supersession_candidate": SupersessionCandidateRequest(
                predecessor_claim_id="predecessor",
                successor_claim_ref=successor_ref,
                effective_at=datetime.now(UTC),
            )
        }
    )
    persisted = persist_governance_monitor_event(store, requested)
    return store, owner, prepared, initial, persisted, successor_ref


def test_monitor_metadata_cannot_advance_current_claim_head(owner_event_case, monkeypatch) -> None:
    """Real monitor/CAS bridge preserves the head despite a claimed replacement."""

    store, owner, prepared, initial, _, _ = owner_event_case
    predecessor_bytes = store.get_bytes(prepared.initial_ledger_ref.artifact_id)
    calls = []
    real_append = _RepositoryClaimLedgerOwner.append_verified_owner_event

    def counted_append(self, **kwargs):
        calls.append(kwargs)
        return real_append(self, **kwargs)

    monkeypatch.setattr(_RepositoryClaimLedgerOwner, "append_verified_owner_event", counted_append)
    result = _bridge(owner_event_case)
    assert load_lifecycle_bridge_result(store, result.result_ref) == result.result
    assert result.result.updated_ledger.events[-1].action == ClaimLifecycleAction.REVIEW_REQUIRED
    assert store.get_bytes(prepared.initial_ledger_ref.artifact_id) == predecessor_bytes
    assert owner.resolve_current(owner_key=prepared.owner_key) == initial.new_head
    assert calls == []


def test_unsigned_candidate_reaches_consumer_with_empty_appointment(owner_event_case) -> None:
    owner_event_case = _requested_case(owner_event_case)
    store, owner, prepared, initial, _, _ = owner_event_case
    result = _bridge(owner_event_case)
    event_ref = ArtifactRef.model_validate(result.result.metadata["owner_event_ref"])
    candidate = read_claim_supersession_candidate(store=store, owner_event_ref=event_ref)
    assert candidate.candidate_status == "candidate"
    assert candidate.successor_claim_id == "actual-successor"
    assert result.result.metadata["owner_event_ref"] == event_ref.model_dump(mode="json")
    assert result.result.owner_event_outcome.code == "claim_owner_event_authority_unappointed"
    assert owner.owner_event_authority is None
    assert owner.resolve_current(owner_key=prepared.owner_key) == initial.new_head


def _assert_signed_owner_event_round_trip(owner_event_case) -> None:
    """Exercise the source producer, independent signatures, CAS append, and current export."""
    owner_event_case = _requested_case(owner_event_case)
    store, _, prepared, initial, _, _ = owner_event_case
    owner, signer = _signed_authority(owner_event_case)
    old_bytes = store.get_bytes(prepared.initial_ledger_ref.artifact_id)
    candidate_bridge = _bridge(owner_event_case, owner)
    event_ref = ArtifactRef.model_validate(candidate_bridge.result.metadata["owner_event_ref"])
    assert candidate_bridge.result.owner_event_outcome.code == "claim_owner_event_rejected"
    store.sign_artifact(event_ref.artifact_id, signer, signer_identity="fixture-supersession-owner")
    bridged = _bridge(owner_event_case, owner)
    assert bridged.result.owner_event_outcome.result_kind == "advanced"
    assert bridged.result.monitor_projection_authority == "advisory"
    assert bridged.result.updated_ledger.events[-1].action is ClaimLifecycleAction.REVIEW_REQUIRED
    assert load_lifecycle_bridge_result(store, bridged.result_ref) == bridged.result
    export = owner.export_current(owner_key=prepared.owner_key, audience=ClaimExportAudience.EXPERT)
    assert isinstance(export, ClaimLedgerExport)
    assert export.superseded_claim_ids == ["predecessor"]
    assert "actual-successor" not in {claim.claim_id for claim in export.claims}
    public = owner.export_current(owner_key=prepared.owner_key, audience=ClaimExportAudience.PUBLIC)
    assert isinstance(public, ClaimLedgerExport)
    assert "actual-successor" not in {claim.claim_id for claim in public.claims}
    current = owner.resolve_current(owner_key=prepared.owner_key)
    assert current.statement.generation == initial.new_head.statement.generation + 1
    assert store.get_bytes(prepared.initial_ledger_ref.artifact_id) == old_bytes
    again = owner.append_verified_owner_event(
        owner_key=prepared.owner_key, owner_event_ref=event_ref
    )
    assert again.new_head == current


def test_signed_owner_event_reaches_current_export_without_editing_predecessor(
    owner_event_case,
) -> None:
    _assert_signed_owner_event_round_trip(owner_event_case)


def test_current_head_replay_cannot_substitute_a_new_matching_appointment(owner_event_case) -> None:
    store, _, prepared, _, _, _ = owner_event_case
    owner, signer = _signed_authority(owner_event_case)
    event_ref = _event(owner_event_case, signer=signer)
    admitted = owner.append_verified_owner_event(
        owner_key=prepared.owner_key, owner_event_ref=event_ref
    )
    assert admitted.result_kind == "advanced"
    original = ClaimSupersessionAppointment.model_validate_json(
        store.get_bytes(owner.owner_event_authority.appointment_ref.artifact_id)
    )
    replacement = original.model_copy(
        update={"valid_until": original.valid_until + timedelta(hours=1)}
    )
    grant_key = Ed25519PrivateKey.generate()
    grant_verifier = Ed25519Verifier()
    grant_verifier.add_trusted_key(grant_key.public_key(), identity="fixture-new-institution")
    replacement_ref = persist_claim_supersession_appointment(
        store=store,
        appointment=replacement,
        signer=Ed25519Signer(grant_key),
        signer_identity="fixture-new-institution",
    )
    rebound = replace(
        owner,
        owner_event_authority=replace(
            owner.owner_event_authority,
            appointment_ref=replacement_ref,
            appointment_verifier=grant_verifier,
        ),
    )
    current = rebound.resolve_current(owner_key=prepared.owner_key)
    assert isinstance(current, ClaimLedgerHeadResolutionNonReceipt)
    assert current.code == "claim_head_content_mismatch"


@pytest.mark.parametrize(
    "failure", ["unsigned", "wrong_scope", "revoked", "fake_successor", "wrong_vocabulary"]
)
def test_owner_event_verification_rejects_present_but_unproven_evidence(
    owner_event_case, failure
) -> None:
    store, _, prepared, initial, _, _ = owner_event_case
    owner, signer = _signed_authority(owner_event_case, wrong_scope=failure == "wrong_scope")
    event_ref = _event(owner_event_case, signer=None if failure == "unsigned" else signer)
    if failure == "revoked":
        owner.owner_event_authority.event_verifier.add_revoked_key_id(signer.key_id)
    if failure == "fake_successor":
        event = read_claim_supersession_candidate(store=store, owner_event_ref=event_ref)
        fake = event.model_copy(update={"successor_claim_id": "invented-successor"})
        event_ref = store.put_bytes(
            to_canonical_bytes(fake.model_dump(mode="json"), CanonSpec(forbid_floats=False)),
            ArtifactWriteOptions(
                kind=OWNER_EVENT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.claim-ledger.supersession-owner-event.v1",
                    version="1",
                ),
            ),
        )
        store.sign_artifact(
            event_ref.artifact_id, signer, signer_identity="fixture-supersession-owner"
        )
    if failure == "wrong_vocabulary":
        event = read_claim_supersession_candidate(store=store, owner_event_ref=event_ref)
        sibling = event.model_dump(mode="json")
        sibling["effective_at"] = datetime.now(UTC).isoformat()
        event_ref = store.put_bytes(
            to_canonical_bytes(sibling, CanonSpec(forbid_floats=False)),
            ArtifactWriteOptions(
                kind="scientist.claims.a_sibling_vocabulary",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.claim-ledger.supersession-owner-event.v1", version="1"
                ),
            ),
        )
        store.sign_artifact(
            event_ref.artifact_id, signer, signer_identity="fixture-supersession-owner"
        )
    outcome = owner.append_verified_owner_event(
        owner_key=prepared.owner_key, owner_event_ref=event_ref
    )
    assert isinstance(outcome, ClaimLedgerHeadResolutionNonReceipt)
    assert outcome.code == "claim_owner_event_rejected"
    assert owner.resolve_current(owner_key=prepared.owner_key) == initial.new_head
