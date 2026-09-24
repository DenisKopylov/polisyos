"""Synthetic appointments exercise the real owner, CAS and signature boundary."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import ValidationError

from polisyos.core.artifacts.signing import Ed25519Signer
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.continuous.governed_public_record import (
    GovernedPublicRecordDimensions,
    GovernedPublicRecordError,
    GovernedPublicRecordOwner,
    GovernedPublicRecordVerificationResponse,
    PublicationMandateStatement,
    PublicationSigningSlot,
    PublicationTrustedKey,
    _PrivateDraft,
    publication_trust_epoch,
)
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tests.unit.scientist.evidence.claims.test_head_index import _build_packet_bound_owner_case

NOW = datetime(2026, 9, 12, 12, tzinfo=UTC)


def synthetic_signer(issuer: str, purpose: str) -> tuple[Ed25519Signer, PublicationTrustedKey]:
    """Generate explicitly synthetic test keys, never production appointments."""
    private = Ed25519PrivateKey.generate()
    signer = Ed25519Signer(private)
    key = PublicationTrustedKey(
        public_key_pem=private.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ),
        issuer_id=issuer,
        purposes=frozenset({purpose}),
    )
    return signer, key


def build_governed_owner_case(
    *,
    store: FileSystemCAS,
    index_root: Path,
    completed_batches: DecisionValidityService,
    claim_metadata: dict[str, object] | None = None,
) -> tuple[GovernedPublicRecordOwner, object, object, Ed25519Signer, PublicationSigningSlot]:
    """Share real source ownership with API tests; institutions are synthetic."""
    claim_owner, prepared, packet_ref, _ = _build_packet_bound_owner_case(
        store=store,
        head_index_root=index_root / "claim-heads",
        completed_batches=completed_batches,
        claim_metadata=claim_metadata,
    )
    publisher, publisher_key = synthetic_signer("synthetic-publisher", "governed_public_record")
    institution, institution_key = synthetic_signer(
        "synthetic-institution", "governed_public_record_mandate"
    )
    slot = PublicationSigningSlot(
        signer=publisher,
        issuer_id="synthetic-publisher",
        publisher_trusted_keys=(publisher_key,),
        mandate_trusted_keys=(institution_key,),
        verifier_epoch=publication_trust_epoch(
            "synthetic-publisher", (publisher_key,), (institution_key,)
        ),
    )
    owner = GovernedPublicRecordOwner(
        store=store, claim_owner=claim_owner, index_root=index_root / "publication", slot=slot
    )
    return owner, prepared, packet_ref, institution, slot


def appoint_synthetic_publication(owner, packet_ref, institution, slot, *, digest=None):
    """Approve only the independently prepared exact content and owner scope."""
    draft = owner.prepare(
        decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
    )
    snapshot = owner.claim_owner.resolve_current_for_packet(decision_packet_ref=packet_ref)
    mandate = PublicationMandateStatement(
        authority_issuer_id="synthetic-institution",
        authority_key_id=institution.key_id,
        issuer_id=slot.issuer_id,
        signing_key_id=slot.signer.key_id,
        public_document_digest=digest or draft.public_document_digest,
        decision_packet_ref=packet_ref,
        owner_scope_ref=snapshot.head.statement.owner_key.scope_ref,
        ledger_artifact_ref=snapshot.head.statement.ledger_artifact_ref,
        authority_basis="Explicitly synthetic institutional appointment for mechanism tests.",
        issued_at=NOW,
        valid_from=NOW,
        valid_until=NOW + timedelta(days=1),
        staleness_after_seconds=3600,
        verifier_epoch=slot.verifier_epoch,
    )
    mandate_ref = owner._put(mandate, "polisyos.publication_mandate")
    owner.store.sign_artifact(
        mandate_ref.artifact_id, institution, signer_identity="synthetic-institution"
    )
    configured = GovernedPublicRecordOwner(
        store=owner.store,
        claim_owner=owner.claim_owner,
        index_root=owner.index_root,
        slot=replace(slot, mandate_ref=mandate_ref),
    )
    return configured, draft


@pytest.fixture
def case(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    return build_governed_owner_case(
        store=store, index_root=tmp_path, completed_batches=DecisionValidityService(store)
    )


def test_empty_slot_prepares_private_candidate_without_public_index(case):
    owner, _, packet_ref, _, _ = case
    empty = GovernedPublicRecordOwner(
        store=owner.store,
        claim_owner=owner.claim_owner,
        index_root=owner.index_root,
        slot=PublicationSigningSlot.empty(),
    )
    with pytest.raises(GovernedPublicRecordError, match="publication_signer_not_configured"):
        empty.issue(decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW)
    assert empty.issued_record_ids() == ()
    assert len(list((empty.index_root / "drafts").iterdir())) == 1
    assert not (empty.index_root / "issued").exists()


def test_real_owner_signed_mandate_issuance_readback_and_custody(case):
    owner, _, packet_ref, institution, slot = case
    configured, draft = appoint_synthetic_publication(owner, packet_ref, institution, slot)
    later = NOW + timedelta(minutes=1)
    assert (
        configured.prepare(
            decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=later
        )
        == draft
    )
    record_id = configured.issue(
        decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=later
    )
    response = configured.verify(record_id)
    assert response.report_authentication == "verified"
    assert response.public_document == draft.public_document
    assert response.dimensions.current_authority == "not_established"
    assert response.dimensions.issuer_issuance == "established"
    binding = configured.resolve_custody_binding(record_id)
    assert binding.affected_claim_ids == ("snapshot-claim",)
    assert binding.decision_packet_ref == packet_ref
    assert binding.published_at == later
    assert configured.issued_record_ids() == (record_id,)
    assert str(packet_ref.artifact_id) not in response.model_dump_json()
    assert "packet-snapshot" not in response.model_dump_json()
    restarted = GovernedPublicRecordOwner(
        store=owner.store,
        claim_owner=owner.claim_owner,
        index_root=owner.index_root,
        slot=configured.slot,
    )
    assert restarted.verify(record_id) == response
    assert restarted.resolve_custody_binding(record_id) == binding


def test_whole_raw_tree_is_preserved_modulo_injective_reference_relocation(case):
    owner, _, packet_ref, _, _ = case
    draft = owner.prepare(
        decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
    )
    private = owner._read(draft.candidate_ref, _PrivateDraft, "scientist.publication.private_draft")
    source_ref = private.snapshot.head.statement.ledger_artifact_ref
    original = json.loads(owner.store.get_bytes(source_ref.artifact_id))
    inverse = {value: key for key, value in private.relocation.items()}

    def restore(value):
        if isinstance(value, dict):
            return {key: restore(child) for key, child in value.items()}
        if isinstance(value, list):
            return [restore(child) for child in value]
        return inverse.get(value, value) if isinstance(value, str) else value

    assert restore(draft.public_document["ledger"]) == original
    assert all(value.startswith("gph_") for value in private.relocation.values())
    assert len(set(private.relocation.values())) == len(private.relocation)
    assert (
        draft.public_document["ledger"]["events"][0]["metadata"]
        == original["events"][0]["metadata"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "missing_claim",
        "changed_status",
        "changed_event_time",
        "changed_basis",
        "changed_container_order",
    ],
)
def test_full_transform_detects_material_changes(case, change):
    owner, _, packet_ref, _, _ = case
    candidate = owner.prepare(
        decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
    )
    draft = owner._read(
        candidate.candidate_ref, _PrivateDraft, "scientist.publication.private_draft"
    )
    document = json.loads(json.dumps(draft.public_document))
    ledger = document["ledger"]
    if change == "missing_claim":
        ledger["current_claims"] = []
    elif change == "changed_status":
        ledger["current_claims"][0]["publishability"] = "blocked"
    elif change == "changed_event_time":
        ledger["events"][0]["occurred_at"] = "2099-01-01"
    elif change == "changed_basis":
        ledger["current_claims"][0]["evidence_refs"] = []
    else:
        document["denied_uses"] = list(reversed(document["denied_uses"]))
    corrupt = draft.model_copy(update={"public_document": document})
    with pytest.raises(GovernedPublicRecordError, match="projection_complete_transform_mismatch"):
        owner._validate_draft(corrupt)


def test_wrong_exact_content_mandate_cannot_issue(case):
    owner, _, packet_ref, institution, slot = case
    configured, _ = appoint_synthetic_publication(
        owner, packet_ref, institution, slot, digest="sha256:" + "a" * 64
    )
    with pytest.raises(GovernedPublicRecordError, match="publication_mandate_binding_invalid"):
        configured.issue(
            decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
        )
    assert configured.issued_record_ids() == ()


def test_historical_revocation_does_not_erase_issuance_or_custody(case):
    owner, _, packet_ref, institution, slot = case
    configured, _ = appoint_synthetic_publication(owner, packet_ref, institution, slot)
    record_id = configured.issue(
        decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
    )
    revoked_slot = replace(
        configured.slot,
        publisher_trusted_keys=(replace(slot.publisher_trusted_keys[0], revoked=True),),
    )
    revoked = GovernedPublicRecordOwner(
        store=owner.store,
        claim_owner=owner.claim_owner,
        index_root=owner.index_root,
        slot=revoked_slot,
    )
    response = revoked.verify(record_id)
    assert response.report_authentication == "verified"
    assert response.cryptographic_signature == "valid"
    assert response.report_key_status == "revoked"
    assert revoked.resolve_custody_binding(record_id) == configured.resolve_custody_binding(
        record_id
    )


def test_exact_unsigned_sidecar_fields_cannot_change_after_issuance(case):
    owner, _, packet_ref, institution, slot = case
    configured, _ = appoint_synthetic_publication(owner, packet_ref, institution, slot)
    record_id = configured.issue(
        decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
    )
    binding = configured.resolve_custody_binding(record_id)
    blob_path, _ = configured.store.get_paths(binding.signature_ref.artifact_id)
    signature_path = blob_path.with_suffix(".sig")
    sidecar = json.loads(signature_path.read_bytes())
    sidecar["signer_identity"] = "an unsigned substitution"
    signature_path.write_text(json.dumps(sidecar))
    response = configured.verify(record_id)
    assert response.report_authentication == "invalid"
    assert response.public_document is None
    assert response.reason_codes == ("record_exact_signature_evidence_changed",)


def test_arbitrary_metadata_is_refused_without_lossy_projection(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    owner, _, packet_ref, _, _ = build_governed_owner_case(
        store=store,
        index_root=tmp_path,
        completed_batches=DecisionValidityService(store),
        claim_metadata={"protected": "secret"},
    )
    with pytest.raises(GovernedPublicRecordError, match="source_metadata_profile_unsupported"):
        owner.prepare(decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW)
    assert owner.issued_record_ids() == ()


def test_absence_reads_are_private_and_unresolved_scope_is_declared(case):
    owner, _, _, _, _ = case
    record_id = "gpr_" + "x" * 32
    with pytest.raises(GovernedPublicRecordError) as error:
        owner.resolve_custody_binding(record_id)
    assert error.value.reads[0].operation == "issued_index.read_bytes"
    assert error.value.reads[0].outcome == "absent"
    assert error.value.reads[0].unresolved_by_construction
    response = owner.verify(record_id)
    assert response.public_document is None
    assert str(owner.index_root) not in response.model_dump_json()


def test_fabricated_positive_envelope_and_projection_flags_are_not_authority():
    with pytest.raises(ValidationError):
        GovernedPublicRecordVerificationResponse(
            record_id="gpr_" + "x" * 32,
            report_authentication="verified",
            cryptographic_signature="valid",
            report_key_status="trusted",
            dimensions=GovernedPublicRecordDimensions(
                issuer_issuance="established", projection_faithfulness="established"
            ),
        )


def test_candidate_ledger_cannot_borrow_an_issued_root_for_historical_admission(case):
    from polisyos.scientist.evidence.claims.audit import _persist_append_only_claim_ledger
    from polisyos.scientist.evidence.claims.head_index import (
        PacketBoundClaimLedgerSnapshot,
        PersistedClaimLedgerHead,
        _persist_profiled_statement,
        project_claim_ledger_current_head,
    )
    from polisyos.scientist.governance.continuous.governed_public_record import (
        _bytes,
        _digest,
        _project,
    )

    owner, _, packet_ref, _, _ = case
    candidate = owner.prepare(
        decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
    )
    draft = owner._read(
        candidate.candidate_ref, _PrivateDraft, "scientist.publication.private_draft"
    )
    candidate_ledger = draft.snapshot.ledger.model_copy(
        update={
            "current_claims": [
                draft.snapshot.ledger.current_claims[0].model_copy(
                    update={"text": "A candidate never admitted by the Claim root issuer."}
                )
            ],
        }
    )
    ledger_ref = _persist_append_only_claim_ledger(owner.store, candidate_ledger)
    head_statement = draft.snapshot.head.statement.model_copy(
        update={
            "ledger_artifact_ref": ledger_ref,
            "ledger_raw_cas_hash": str(ledger_ref.artifact_id),
        }
    )
    head_ref, head_hash = _persist_profiled_statement(
        store=owner.store, record="claim_ledger_head", value=head_statement
    )
    head = PersistedClaimLedgerHead(
        head_ref=head_ref, head_content_hash=head_hash, statement=head_statement
    )
    projected, relocation = _project(candidate_ledger, mapping=draft.relocation)
    # Every shape, hash, PUBLIC marker and projection binding remains valid.
    # Only the independent immutable-root issuance replay distinguishes this
    # candidate from an admitted source; removing it makes this test fail.
    forged_snapshot = PacketBoundClaimLedgerSnapshot.model_validate_json(
        draft.snapshot.model_copy(
            update={
                "ledger": candidate_ledger,
                "head": head,
                "current_head_projection": project_claim_ledger_current_head(
                    head=head,
                    claim_export=draft.snapshot.public_export,
                ),
            }
        ).model_dump_json()
    )
    forged = draft.model_copy(
        update={
            "snapshot": forged_snapshot,
            "public_document": projected,
            "public_document_digest": _digest(_bytes(projected)),
            "relocation": relocation,
        }
    )
    with pytest.raises(
        GovernedPublicRecordError, match="historical_source_admission_not_established"
    ):
        owner._validate_draft(forged)


def test_private_reference_in_material_is_a_bounded_refusal(case):
    from polisyos.scientist.governance.continuous.governed_public_record import _project

    owner, _, packet_ref, _, _ = case
    source = owner.claim_owner.resolve_current_for_packet(decision_packet_ref=packet_ref).ledger
    changed = source.model_copy(
        update={
            "current_claims": [
                source.current_claims[0].model_copy(
                    update={
                        "text": "Read the protected evidence at "
                        + str(source.current_claims[0].evidence_refs[0].artifact_id),
                    }
                )
            ]
        }
    )
    with pytest.raises(GovernedPublicRecordError, match="source_reference_embedded_in_material"):
        _project(changed)


@pytest.mark.parametrize("kind", ["malformed_name", "malformed_content", "symlink"])
def test_controlled_inventory_never_silently_discards_malformed_members(case, kind):
    owner, _, _, _, _ = case
    directory = owner.index_root / "issued"
    directory.mkdir(parents=True)
    if kind == "malformed_name":
        (directory / "unissued.json").write_text("{}")
    elif kind == "malformed_content":
        (directory / ("gpr_" + "x" * 32 + ".json")).write_text("{")
    else:
        (directory / ("gpr_" + "x" * 32 + ".json")).symlink_to(directory / "missing")
    with pytest.raises(GovernedPublicRecordError, match="issuance_index_invalid") as error:
        owner.issued_record_ids()
    assert error.value.reads[-1].outcome == "invalid"


def test_index_emission_is_atomic_and_never_overwrites(tmp_path, monkeypatch):
    import os

    path = tmp_path / "issued" / "index.json"
    original_link = os.link
    observations = []

    def observe_complete_before_link(source, destination):
        observations.append((path.exists(), Path(source).read_bytes()))
        original_link(source, destination)

    monkeypatch.setattr(os, "link", observe_complete_before_link)
    GovernedPublicRecordOwner._atomic_new(path, b'{"complete":true}')
    assert observations == [(False, b'{"complete":true}')]
    with pytest.raises(FileExistsError):
        GovernedPublicRecordOwner._atomic_new(path, b"overwrite")
    assert path.read_bytes() == b'{"complete":true}'


def _epoch_snapshots(owner, packet_ref):
    """Build a real active-epoch reduction and the measured writable-graph forgery."""
    from polisyos.scientist.evidence.claims.audit import _persist_append_only_claim_ledger
    from polisyos.scientist.evidence.claims.head_index import (
        ClaimLifecycleBridgeAdvanced,
        PacketBoundClaimLedgerSnapshot,
        PersistedClaimLedgerHead,
        _persist_profiled_statement,
        project_claim_ledger_current_head,
    )
    from polisyos.scientist.governance.continuous.lifecycle_bridge import (
        load_lifecycle_bridge_result,
        persist_lifecycle_bridge_result,
    )
    from tests.unit.scientist.evidence.claims.test_head_index import _verified_batch_for_packet

    source_owner = owner.claim_owner
    genesis = source_owner.resolve_current_for_packet(decision_packet_ref=packet_ref)
    dependency = str(genesis.ledger.current_claims[0].evidence_refs[0].artifact_id)
    batch = _verified_batch_for_packet(
        store=owner.store,
        ledger_ref=genesis.head.statement.ledger_artifact_ref,
        packet_ref=packet_ref,
        batch_seed="a",
        targets=((dependency, "active", "Synthetic verified no-change epoch"),),
    )
    advanced = source_owner.advance_verified_batch(
        verified_batch=batch, decision_packet_ref=packet_ref
    )
    assert isinstance(advanced, ClaimLifecycleBridgeAdvanced)
    genuine = source_owner.resolve_current_for_packet(decision_packet_ref=packet_ref)
    assert isinstance(genuine, PacketBoundClaimLedgerSnapshot)
    altered = genesis.ledger.model_copy(
        update={
            "current_claims": [
                genesis.ledger.current_claims[0].model_copy(
                    update={"text": "Injected claim never produced by the epoch reducer."}
                ),
            ]
        }
    )
    altered_ref = _persist_append_only_claim_ledger(owner.store, altered)
    bridge = advanced.bridge_result.statement
    lifecycle = load_lifecycle_bridge_result(owner.store, bridge.lifecycle_result_ref)
    lifecycle_ref = persist_lifecycle_bridge_result(
        owner.store, lifecycle.model_copy(update={"updated_ledger": altered})
    )
    forged_bridge = bridge.model_copy(
        update={
            "next_ledger_ref": altered_ref,
            "next_ledger_content_hash": str(altered_ref.artifact_id),
            "lifecycle_result_ref": lifecycle_ref,
            "lifecycle_result_content_hash": str(lifecycle_ref.artifact_id),
        }
    )
    bridge_ref, _ = _persist_profiled_statement(
        store=owner.store, record="claim_bridge_result", value=forged_bridge
    )
    statement = genuine.head.statement.model_copy(
        update={
            "bridge_result_refs": (bridge_ref,),
            "ledger_artifact_ref": altered_ref,
            "ledger_raw_cas_hash": str(altered_ref.artifact_id),
        }
    )
    head_ref, head_hash = _persist_profiled_statement(
        store=owner.store, record="claim_ledger_head", value=statement
    )
    head = PersistedClaimLedgerHead(
        head_ref=head_ref, head_content_hash=head_hash, statement=statement
    )
    forged = PacketBoundClaimLedgerSnapshot.model_validate_json(
        genuine.model_copy(
            update={
                "head": head,
                "ledger": altered,
                "current_head_projection": project_claim_ledger_current_head(
                    head=head, claim_export=genuine.public_export
                ),
            }
        ).model_dump_json()
    )
    # The old epoch closure still accepts this exact graph; no consumer was
    # weakened or silently repaired. This is the measured unsupported profile.
    assert source_owner._verify_closed_head(forged.head) is None
    return genuine, forged


@pytest.mark.parametrize("source_kind", ["genuine_epoch", "forged_epoch"])
def test_historical_source_profile_refuses_all_transition_heads(case, source_kind):
    from polisyos.scientist.evidence.claims.head_index import ClaimLedgerHeadResolutionNonReceipt

    owner, _, packet_ref, _, _ = case
    candidate = owner.prepare(
        decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
    )
    draft = owner._read(
        candidate.candidate_ref, _PrivateDraft, "scientist.publication.private_draft"
    )
    genuine, forged = _epoch_snapshots(owner, packet_ref)
    source = genuine if source_kind == "genuine_epoch" else forged
    refused = owner.claim_owner.verify_historical_packet_snapshot(snapshot=source)
    assert isinstance(refused, ClaimLedgerHeadResolutionNonReceipt)
    assert refused.code == "claim_historical_transition_profile_unsupported"
    with pytest.raises(
        GovernedPublicRecordError, match="claim_historical_transition_profile_unsupported"
    ):
        owner._validate_draft(draft.model_copy(update={"snapshot": source}))
    with pytest.raises(
        GovernedPublicRecordError, match="claim_historical_transition_profile_unsupported"
    ):
        owner.prepare(decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW)
    assert owner.issued_record_ids() == ()


def test_initial_publication_remains_verifiable_after_actual_epoch_advance(case):
    owner, _, packet_ref, institution, slot = case
    configured, _ = appoint_synthetic_publication(owner, packet_ref, institution, slot)
    record_id = configured.issue(
        decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
    )
    original = configured.verify(record_id)
    original_binding = configured.resolve_custody_binding(record_id)
    _epoch_snapshots(configured, packet_ref)
    assert configured.verify(record_id) == original
    assert configured.resolve_custody_binding(record_id) == original_binding
    with pytest.raises(
        GovernedPublicRecordError, match="claim_historical_transition_profile_unsupported"
    ):
        configured.issue(
            decision_id="packet-snapshot", decision_packet_ref=packet_ref, issued_at=NOW
        )
