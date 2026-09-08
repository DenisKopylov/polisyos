"""Behavioral negatives for public record population custody."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.scientist.governance.continuous import published_signature_custody as custody


def _population(store: core_artifacts.FileSystemCAS):
    def put(kind: str):
        return store.put_json(
            {"synthetic_test_only": True, "kind": kind},
            core_artifacts.PutOptions(kind=kind, media_type="application/json"),
        )

    now = datetime(2026, 9, 7, tzinfo=UTC)
    return custody.persist_public_signature_population(
        store,
        population_id="synthetic-negative-control",
        population_provenance="synthetic_test",
        members=(
            custody.PublicSignaturePopulationMember(
                signature_ref=put("synthetic.signature"),
                decision_packet_ref=put("synthetic.decision_packet"),
                affected_claim_ids=("synthetic-claim",),
                published_at=now,
                staleness_after_seconds=60,
            ),
        ),
        captured_at=now,
    )


def _no_lifecycle(ref):
    raise AssertionError(f"A population negative cannot emit lifecycle authority: {ref}")


def test_missing_population_persists_blocked_without_inventing_resolved_refs(tmp_path: Path):
    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
    population = _population(store)
    missing = population.model_copy(
        update={
            "population_ref": population.population_ref.model_copy(
                update={"artifact_id": "sha256:" + "0" * 64}
            )
        }
    )

    result = custody.PublishedSignatureCustodyWatcher(
        store=store,
        population_provider=custody.StaticPublicSignaturePopulationProvider(missing),
        lifecycle_publisher=_no_lifecycle,
    ).scan_once()

    assert result.status == "blocked"
    assert result.predicate_provenance == "not_established"
    assert result.scan_receipt_ref is not None
    persisted = custody.PublishedSignatureCustodyScan.model_validate(
        core_canon.from_canonical_bytes(store.get_bytes(result.scan_receipt_ref.artifact_id))
    )
    assert persisted.population_ref is None
    assert persisted.population_content_hash is None
    assert persisted.member_count == 0
    assert not persisted.monitor_event_refs
    assert not persisted.lifecycle_bridge_result_refs

    # Keep its negative markers while trying to invent a watched population/effect.
    for changes in (
        {"status": "watched"},
        {"member_count": 1},
        {"predicate_provenance": "institutionally_supplied"},
        {"monitor_event_refs": (population.population_ref,)},
        {"lifecycle_bridge_result_refs": (population.population_ref,)},
        {"population_ref": population.population_ref},
    ):
        with pytest.raises(ValueError):
            custody.PublishedSignatureCustodyScan.model_validate(
                {**persisted.model_dump(), **changes}
            )


def _issued_reports(tmp_path: Path, numbers: tuple[int, ...] = (1, 2)):
    from polisyos.runtime.http.services.public_decision_verification import (
        PublicDecisionVerificationService,
        PublicDecisionVerificationTrustedKey,
    )

    pair = core_artifacts.KeyPair.generate()
    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
    index_root = tmp_path / "issued"
    source = PublicDecisionVerificationService(
        store=store,
        index_root=index_root,
        issuer_id="test-public-report-issuer",
        signer=core_artifacts.Ed25519Signer(pair.private_key),
        trusted_keys=(
            PublicDecisionVerificationTrustedKey(
                public_key_pem=pair.public_pem(),
                issuer_id="test-public-report-issuer",
                purposes=frozenset({"public_decision_verification_record"}),
            ),
        ),
    )
    ids = tuple(
        source.issue(
            decision_id=f"candidate-{number}",
            public_document={"candidate": number},
            issued_at=datetime(2026, 9, 7, tzinfo=UTC),
        )
        for number in numbers
    )
    return source, store, index_root, ids


def test_real_empty_issuance_slot_does_not_become_watched_empty(tmp_path: Path):
    source, store, _, _ = _issued_reports(tmp_path, ())
    result = custody.PublishedSignatureCustodyWatcher(
        store=store,
        population_provider=custody.PublicVerificationRecordPopulationProvider(source=source),
        lifecycle_publisher=_no_lifecycle,
    ).scan_once()

    assert result.status == "not_established"
    assert result.reason == "governed_public_record_producer_missing"
    assert result.scan_receipt_ref is not None
    persisted = custody.PublishedSignatureCustodyScan.model_validate(
        core_canon.from_canonical_bytes(store.get_bytes(result.scan_receipt_ref.artifact_id))
    )
    assert persisted.record_inspections == ()
    assert persisted.population_ref is None
    assert persisted.member_count == 0


def test_real_signed_report_inventory_is_inspected_but_not_a_governed_population(tmp_path: Path):
    source, store, _, ids = _issued_reports(tmp_path)
    provider = custody.PublicVerificationRecordPopulationProvider(source=source)
    result = custody.PublishedSignatureCustodyWatcher(
        store=store, population_provider=provider, lifecycle_publisher=_no_lifecycle
    ).scan_once()

    assert result.status == "not_established"
    assert result.reason == "governed_public_record_producer_missing"
    assert result.predicate_provenance == "not_established"
    assert result.scan_receipt_ref is not None
    persisted = custody.PublishedSignatureCustodyScan.model_validate(
        core_canon.from_canonical_bytes(store.get_bytes(result.scan_receipt_ref.artifact_id))
    )
    assert tuple(row.record_id for row in persisted.record_inspections) == tuple(sorted(ids))
    assert {row.report_authentication for row in persisted.record_inspections} == {"verified"}
    assert {row.reason for row in persisted.record_inspections} == {"promoted_record_missing"}
    assert persisted.member_count == 0
    assert persisted.population_ref is None
    assert not persisted.monitor_event_refs
    assert not persisted.lifecycle_bridge_result_refs


def test_corrupt_actual_report_changes_population_nonreceipt_not_its_markers(tmp_path: Path):
    source, store, index_root, ids = _issued_reports(tmp_path)
    provider = custody.PublicVerificationRecordPopulationProvider(source=source)
    before = provider.resolve()
    entry = json.loads((index_root / f"{ids[0]}.json").read_bytes())
    artifact_id = core_artifacts.ArtifactID.model_validate(entry["record_artifact_ref"])
    signature = store.get_signature(artifact_id)
    assert signature is not None
    store.put_signature(artifact_id, signature.model_copy(update={"signature_hex": "00" * 64}))

    after = provider.resolve()

    assert before.reason == "governed_public_record_producer_missing"
    assert after.reason == "public_record_verification_not_established"
    assert before.status == after.status == "not_established"
    assert before.predicate_provenance == after.predicate_provenance == "not_established"
    assert tuple(row.record_id for row in after.record_inspections) == tuple(sorted(ids))
    invalid = next(row for row in after.record_inspections if row.record_id == ids[0])
    assert invalid.report_authentication == "invalid"
    assert invalid.reason == "record_not_authenticated"


def test_corrupt_controlled_inventory_is_recorded_as_unresolved(tmp_path: Path):
    source, store, index_root, ids = _issued_reports(tmp_path)
    (index_root / f"{ids[0]}.json").write_text("{not-json")
    result = custody.PublishedSignatureCustodyWatcher(
        store=store,
        population_provider=custody.PublicVerificationRecordPopulationProvider(source=source),
        lifecycle_publisher=_no_lifecycle,
    ).scan_once()

    assert result.status == "not_established"
    assert result.reason == "public_record_inventory_unresolvable"
    assert result.scan_receipt_ref is not None
    persisted = custody.PublishedSignatureCustodyScan.model_validate(
        core_canon.from_canonical_bytes(store.get_bytes(result.scan_receipt_ref.artifact_id))
    )
    assert persisted.record_inspections == ()
    assert persisted.member_count == 0


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"record_id": "another-issued-record"}, "record_binding_mismatch"),
        ({"report_authentication": "future_positive"}, "record_verification_error"),
        ({"promoted_record": {"caller_says": "promoted"}}, "promoted_record_not_admitted"),
    ],
)
def test_report_markers_cannot_supply_missing_governed_binding(tmp_path: Path, changes, reason):
    source, _, _, ids = _issued_reports(tmp_path)

    class ChangedObservationSource:
        def issued_record_ids(self):
            return source.issued_record_ids()

        def verify(self, record_id):
            # Real cryptographic verification stays; only the downstream declaration changes.
            return source.verify(record_id).model_copy(update=changes)

    result = custody.PublicVerificationRecordPopulationProvider(
        source=ChangedObservationSource()
    ).resolve()

    assert result.status == "not_established"
    assert result.predicate_provenance == "not_established"
    assert result.reason == "public_record_verification_not_established"
    assert tuple(row.record_id for row in result.record_inspections) == tuple(sorted(ids))
    assert {row.reason for row in result.record_inspections} == {reason}
