"""Focused semantic controls for producing reconciliation and frozen replay."""

from pathlib import Path

import pytest

from polisyos.core import artifacts, canon


def _reader_fixture(tmp_path: Path):
    from polisyos.runtime.quality.epoch_transition_verification import (
        ProducingEpochDenominatorReconciliationReader,
    )
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _runtime_reconciliation_fixture,
    )

    fixture = _runtime_reconciliation_fixture(tmp_path)
    reader = ProducingEpochDenominatorReconciliationReader(
        store=fixture.store, verifier_provenance_ref=fixture.provenance
    )
    kwargs = {
        "transition_artifact_ref": fixture.transition_ref,
        "transition_content_hash": fixture.transition_raw_hash,
        "requested_query_context_ref": fixture.query_ref,
        "authority_purpose": "decision_validity_epoch_transition",
        "scientist_snapshot_handle": fixture.snapshot.handle,
    }
    return fixture, reader, kwargs


def _corrupt_sidecar(store):
    store.put_bytes(
        b"{}",
        artifacts.ArtifactWriteOptions(
            kind="polisyos.epoch.transition_denominator_reconciliation_receipt",
            media_type="application/vnd.polisyos.chronology+json",
        ),
    )


def test_producing_reader_persists_sidecar_and_replays_exact_frozen_handle(tmp_path: Path) -> None:
    """New malformed candidates after freezing cannot replace or invalidate the handle."""

    fixture, reader, kwargs = _reader_fixture(tmp_path)
    with pytest.raises(ValueError, match=r"^epoch_denominator_reconciliation_unavailable$"):
        fixture.reader.resolve_for_first_admission(**kwargs)
    produced = reader.resolve_for_first_admission(**kwargs)
    assert fixture.store.get_bytes(produced.handle.reconciliation_receipt_ref.artifact_id)
    assert reader.resolve_exact(handle=produced.handle) == produced
    _corrupt_sidecar(fixture.store)
    assert reader.resolve_exact(handle=produced.handle) == produced
    with pytest.raises(ValueError, match=r"^epoch_denominator_reconciliation_unresolved$"):
        reader.resolve_for_first_admission(**kwargs)


def test_producing_reader_retains_corrupt_existing_candidate_refusal(tmp_path: Path) -> None:
    """A newly produced good sidecar does not excuse a malformed member of the live census."""

    fixture, reader, kwargs = _reader_fixture(tmp_path)
    _corrupt_sidecar(fixture.store)
    with pytest.raises(ValueError, match=r"^epoch_denominator_reconciliation_unresolved$"):
        reader.resolve_for_first_admission(**kwargs)


def test_complete_target_census_refuses_missing_unselected_owner_member(tmp_path: Path) -> None:
    """Valid selected rows do not excuse a broken member of the complete owner inventory."""

    from polisyos.scientist.validation.decision_validity import DecisionValidityService
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _put_json,
        _register_reconciliation_packet,
    )

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    service = DecisionValidityService(store)
    selected = _put_json(store, {"target": "selected"}, kind="runtime.epoch_target")
    outside = _put_json(store, {"target": "outside"}, kind="runtime.epoch_target")
    for target, key in ((selected, "epoch::selected"), (outside, "epoch::outside")):
        _register_reconciliation_packet(
            service,
            store,
            dependency_key=key,
            dependency_artifact_id=str(target.artifact_id),
            lineage_key=f"lineage-{key}",
        )
    service._state._dependency_path("epoch::outside").unlink()
    with pytest.raises(RuntimeError, match=r"^decision_validity_owner_state_corrupt$"):
        service.persist_epoch_impact_snapshot_for_targets(
            target_refs=(selected,), requested_query_context_ref="sha256:" + "c" * 64
        )


def test_complete_target_census_rejects_false_profile_with_real_impact(tmp_path: Path) -> None:
    """A profile lie must refuse even when its unchanged ID resolves a nonempty owner impact."""

    from polisyos.scientist.validation.decision_validity import DecisionValidityService
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _put_json,
        _register_reconciliation_packet,
    )

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    service = DecisionValidityService(store)
    target = _put_json(store, {"target": "selected"}, kind="runtime.epoch_target")
    _register_reconciliation_packet(
        service,
        store,
        dependency_key="epoch::selected",
        dependency_artifact_id=str(target.artifact_id),
        lineage_key="lineage-selected",
    )
    exact = service.persist_epoch_impact_snapshot_for_targets(
        target_refs=(target,), requested_query_context_ref="sha256:" + "c" * 64
    )
    assert exact.snapshot.targets
    with pytest.raises(ValueError, match=r"^dependency_denominator_unresolved$"):
        service.persist_epoch_impact_snapshot_for_targets(
            target_refs=(target.model_copy(update={"kind": "wrong.target"}),),
            requested_query_context_ref="sha256:" + "c" * 64,
        )


def test_complete_target_census_cannot_admit_another_tenants_packet(tmp_path: Path) -> None:
    """A shared Runtime target does not grant custody of another tenant's decision packet."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.scientist.validation.decision_validity import DecisionValidityService
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _put_json,
        _register_reconciliation_packet,
    )

    store = artifacts.FileSystemCAS(
        tmp_path / "cas", ownership_enforced=True, ownership_requires_scope=False
    )
    service = DecisionValidityService(store)
    packets = {}
    for tenant in ("tenant-a", "tenant-b"):
        with tenant_scope(None, tenant_id=tenant, cell_id="cell-a"):
            target = _put_json(store, {"target": "shared"}, kind="runtime.epoch_target")
            packets[tenant] = _register_reconciliation_packet(
                service,
                store,
                dependency_key=f"epoch::{tenant}",
                dependency_artifact_id=str(target.artifact_id),
                lineage_key=f"lineage-{tenant}",
            )
    with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-a"):
        with pytest.raises(PermissionError):
            store.get_bytes(artifacts.ArtifactID.model_validate(packets["tenant-a"]))
        with pytest.raises(RuntimeError, match=r"^decision_validity_owner_state_corrupt$"):
            service.persist_epoch_impact_snapshot_for_targets(
                target_refs=(target,), requested_query_context_ref="sha256:" + "c" * 64
            )


@pytest.mark.parametrize("failure", ["missing-packet-artifact", "backend-key-error"])
def test_complete_target_census_normalizes_unreadable_packet(tmp_path: Path, failure: str) -> None:
    """Every backend's missing packet result retains the same owner-state refusal."""

    from polisyos.scientist.validation.decision_validity import DecisionValidityService
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _put_json,
        _register_reconciliation_packet,
    )

    class BackendMissCAS(artifacts.FileSystemCAS):
        missing_packet: str | None = None

        def get_bytes(self, artifact_id):
            if str(artifact_id) == self.missing_packet:
                raise KeyError(str(artifact_id))
            return super().get_bytes(artifact_id)

    store = BackendMissCAS(tmp_path / "cas")
    service = DecisionValidityService(store)
    target = _put_json(store, {"target": "selected"}, kind="runtime.epoch_target")
    packet = _register_reconciliation_packet(
        service,
        store,
        dependency_key="epoch::selected",
        dependency_artifact_id=str(target.artifact_id),
        lineage_key="lineage-selected",
    )
    if failure == "backend-key-error":
        store.missing_packet = packet
    else:
        blob, _ = store._paths(artifacts.ArtifactID.model_validate(packet))
        blob.rename(blob.with_suffix(".unavailable"))
    with pytest.raises(RuntimeError, match=r"^decision_validity_owner_state_corrupt$"):
        service.persist_epoch_impact_snapshot_for_targets(
            target_refs=(target,), requested_query_context_ref="sha256:" + "c" * 64
        )


def test_reconciliation_inputs_preserve_each_manifest_selector() -> None:
    """Receipt edges retain producer-selected views and preserve default selectors."""
    from polisyos.runtime.quality import epoch_denominator_reconciliation as module

    profile = "sha256:" + "a" * 64
    refs = tuple(
        artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate("sha256:" + chr(ord("b") + index) * 64),
            kind=f"test.input.{index}",
            media_type="application/octet-stream",
            manifest_profile_sha256=profile if index != 1 else None,
        )
        for index in range(3)
    )
    inputs = module._receipt_inputs(
        transition_ref=refs[0],
        snapshot_ref=refs[1],
        provenance_ref=refs[2],
    )
    by_role = {row.role: row for row in inputs}
    assert by_role["epoch_transition"].manifest_profile_sha256 == profile
    assert by_role["decision_validity_epoch_impact_snapshot"].manifest_profile_sha256 is None
    assert by_role["epoch_transition_verifier_provenance"].manifest_profile_sha256 == profile


def test_reconciliation_receipt_round_trips_cas_selected_profiles_for_all_existing_edges(
    tmp_path: Path,
) -> None:
    import polisyos.scientist.validation.decision_validity as decision_validity
    from polisyos.core.contracts import DecisionValidityEpochImpactSnapshotHandle
    from polisyos.runtime.quality import epoch_denominator_reconciliation as module
    from polisyos.runtime.quality import epoch_validity_cascade as cascade
    from polisyos.runtime.quality.epoch_denominator_reconciliation import (
        EpochTransitionDenominatorReconciliationProducer,
        EpochTransitionDenominatorReconciliationReader,
    )
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _runtime_reconciliation_fixture,
    )

    fixture = _runtime_reconciliation_fixture(tmp_path)
    store = fixture.store

    selected_transition = store.put_bytes(
        store.get_bytes(fixture.transition_ref),
        cascade._epoch_transition_artifact_write_options(),
        return_selected_profile=True,
    )
    assert selected_transition.manifest_profile_sha256 is not None

    snapshot_ref = fixture.snapshot.handle.snapshot_ref
    selected_snapshot = store.put_bytes(
        store.get_bytes(snapshot_ref),
        artifacts.ArtifactWriteOptions(
            kind=decision_validity._EPOCH_IMPACT_SNAPSHOT_KIND,
            media_type=decision_validity._EPOCH_IMPACT_SNAPSHOT_MEDIA_TYPE,
            schema=artifacts.SchemaInfo(
                name=decision_validity._EPOCH_IMPACT_SNAPSHOT_SCHEMA,
                version="1.0",
            ),
            canon=artifacts.CanonInfo.from_spec(decision_validity._EPOCH_IMPACT_SNAPSHOT_CANON),
        ),
        return_selected_profile=True,
    )
    assert selected_snapshot.manifest_profile_sha256 is not None
    selected_snapshot_handle = DecisionValidityEpochImpactSnapshotHandle(
        snapshot_ref=selected_snapshot,
        snapshot_content_hash=fixture.snapshot.snapshot.snapshot_content_hash,
    )

    selected_provenance = store.put_bytes(
        store.get_bytes(fixture.provenance),
        artifacts.ArtifactWriteOptions(
            kind="chronology.epoch_transition_verifier",
            media_type="application/json",
        ),
        return_selected_profile=True,
    )
    assert selected_provenance.manifest_profile_sha256 is not None

    producer = EpochTransitionDenominatorReconciliationProducer(
        store=store,
        verifier_provenance_ref=selected_provenance,
    )
    persisted = producer.produce_and_persist(
        transition_artifact_ref=selected_transition,
        scientist_snapshot_handle=selected_snapshot_handle,
        requested_query_context_ref=fixture.query_ref,
        authority_purpose="decision_validity_epoch_transition",
    )
    assert not isinstance(persisted, module.EpochDenominatorReconciliationNonReceipt)

    receipt_manifest = store.get_manifest(persisted.handle.reconciliation_receipt_ref)
    by_role = {row.role: row for row in receipt_manifest.inputs}
    assert (
        by_role["epoch_transition"].manifest_profile_sha256
        == selected_transition.manifest_profile_sha256
    )
    assert (
        by_role["decision_validity_epoch_impact_snapshot"].manifest_profile_sha256
        == selected_snapshot.manifest_profile_sha256
    )
    assert (
        by_role["epoch_transition_verifier_provenance"].manifest_profile_sha256
        == selected_provenance.manifest_profile_sha256
    )

    reread = EpochTransitionDenominatorReconciliationReader(
        store=store,
        verifier_provenance_ref=selected_provenance,
    ).resolve_exact(handle=persisted.handle)
    assert reread == persisted


def test_manifest_refinement_respects_default_and_selected_selectors(tmp_path: Path) -> None:
    """A default selector may carry CAN; explicit selected selectors bind exact views."""
    from polisyos.runtime.quality import epoch_denominator_reconciliation as module

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    spec = canon.CanonSpec(forbid_floats=False)
    payload = canon.to_canonical_bytes({"transition": "view"}, spec)
    ref = store.put_bytes(
        payload,
        artifacts.ArtifactWriteOptions(
            kind="test.transition_view",
            media_type="application/json",
            canon=artifacts.CanonInfo.from_spec(spec),
        ),
        return_selected_profile=True,
    )
    manifest = store.get_manifest(ref)
    default_ref = artifacts.ArtifactRef(
        artifact_id=ref.artifact_id,
        kind=ref.kind,
        media_type=ref.media_type,
    )
    wrong_ref = ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
    assert module._manifest_matches_ref(manifest, ref)
    assert module._manifest_matches_ref(manifest, default_ref)
    assert not module._manifest_matches_ref(manifest, wrong_ref)
