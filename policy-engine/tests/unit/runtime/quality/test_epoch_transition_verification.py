"""Canonical origin, exact signatures and owner impact meet at strict intake."""

from pathlib import Path

import pytest


def test_empty_production_owner_retains_verifier_and_reconciliation_refusals(
    tmp_path: Path,
) -> None:
    from polisyos.core import artifacts
    from polisyos.runtime.quality.epoch_transition_verification import (
        build_epoch_decision_validity_owner,
    )

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    owner = build_epoch_decision_validity_owner(store=store)
    ref = store.put_bytes(
        b"marker", artifacts.ArtifactWriteOptions(kind="test.transition", media_type="text/plain")
    )
    with pytest.raises(ValueError, match=r"^verifier_not_configured$"):
        owner.admit_epoch_validity_batch(
            transition_artifact_ref=ref,
            requested_query_context_ref="sha256:" + "a" * 64,
        )
    with pytest.raises(ValueError, match=r"^epoch_denominator_reconciliation_unavailable$"):
        owner._epoch_denominator_reconciliation_reader.resolve_exact(handle=None)
    assert owner.state_generation() == 0


def test_canonical_transition_reaches_strict_batch_and_replays_frozen_impact(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.quality.epoch_transition_verification import (
        build_epoch_decision_validity_owner,
    )
    from tests.unit.runtime.quality.test_epoch_transition_origin import _producer_fixture
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _register_reconciliation_packet,
    )

    producer, origins, profiles, fixture, _repository, kwargs = _producer_fixture(
        tmp_path, authority_purpose="decision_validity_epoch_transition", disposition="invalidate"
    )
    produced = producer.produce_and_persist(**kwargs)
    target = producer._dependency_inventory.resolve_complete_epoch_dependencies(
        authority_purpose=kwargs["authority_purpose"],
        requested_query_context_ref=kwargs["requested_query_context_ref"],
    ).target_refs[0]
    owner = build_epoch_decision_validity_owner(store=fixture.store, origins=origins)
    packet = _register_reconciliation_packet(
        owner,
        fixture.store,
        dependency_key="epoch::canonical-target",
        dependency_artifact_id=str(target.artifact_id),
        lineage_key="canonical-packet",
    )
    receipt = owner.admit_epoch_validity_batch(
        transition_artifact_ref=produced.transition_artifact_ref,
        requested_query_context_ref=kwargs["requested_query_context_ref"],
    )
    assert receipt.affected_packet_refs == (packet,)
    assert receipt.targets[0].status.value == "stale"
    assert owner.read_current_projection(packet).status.value == "stale"
    _register_reconciliation_packet(
        owner,
        fixture.store,
        dependency_key="epoch::late-target",
        dependency_artifact_id=str(target.artifact_id),
        lineage_key="late-packet",
    )
    assert (
        owner.admit_epoch_validity_batch(
            transition_artifact_ref=produced.transition_artifact_ref,
            requested_query_context_ref=kwargs["requested_query_context_ref"],
        )
        == receipt
    )
    profiles.signature_valid = False
    with pytest.raises(ValueError, match=r"^signature_unverified$"):
        owner.admit_epoch_validity_batch(
            transition_artifact_ref=produced.transition_artifact_ref,
            requested_query_context_ref=kwargs["requested_query_context_ref"],
        )


def test_exact_signed_transition_without_canonical_origin_cannot_mutate_owner(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.quality.epoch_transition_origin import FileEpochTransitionOriginOwner
    from polisyos.runtime.quality.epoch_transition_verification import (
        build_epoch_decision_validity_owner,
    )
    from tests.unit.runtime.quality.test_epoch_transition_origin import _producer_fixture

    producer, _, profiles, fixture, repository, kwargs = _producer_fixture(
        tmp_path, authority_purpose="decision_validity_epoch_transition", disposition="invalidate"
    )
    produced = producer.produce_and_persist(**kwargs)
    foreign = FileEpochTransitionOriginOwner(
        root=tmp_path / "foreign",
        artifacts=fixture.store,
        signed_artifacts=repository,
        signing_profiles=profiles,
    )
    owner = build_epoch_decision_validity_owner(store=fixture.store, origins=foreign)
    with pytest.raises(ValueError, match=r"^signature_unverified$"):
        owner.admit_epoch_validity_batch(
            transition_artifact_ref=produced.transition_artifact_ref,
            requested_query_context_ref=kwargs["requested_query_context_ref"],
        )
    assert owner.state_generation() == 0
