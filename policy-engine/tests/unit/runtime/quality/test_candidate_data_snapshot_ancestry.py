"""Mixed real-owner ancestry stays candidate-only without changing observed epochs."""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import (
    AcquiredObservationDataSnapshotLineage,
    CandidateAcquisitionSourceDataSnapshotLineage,
    DataSnapshot,
    data_snapshot_owner_input_requirements,
)
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.data_snapshot_lineage import (
    ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
    CANDIDATE_SOURCE_LIMITATIONS,
    DataSnapshotLineageError,
    DataSnapshotSourceRowNotEstablishedError,
    validate_data_snapshot_owner_lineage,
)
from polisyos.runtime.quality.data_state_substrate import (
    CandidateAcquisitionSourceSlotBinding,
    ControlledAcquisitionSlotBinding,
    materialize_acquired_observation_snapshot,
    materialize_candidate_acquisition_snapshot,
)
from tests._helpers.lane01_candidate_source import build_lane01_candidate_source
from tests._helpers.semantic_epoch_native import _real_epoch_scenario
from tests._helpers.world_model_record import _data_snapshot_ref
from tests.unit.runtime.quality.test_acquisition_executor import _activate_real_epoch_scenario


@pytest.fixture
def owner_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Compose real native epoch and compiler/source owners in the same CAS."""
    # The older native fixture has no tenant claim. Keep its owner setup intact;
    # candidate source writes and all candidate reads use the explicit lane scope.
    scenario = _real_epoch_scenario(tmp_path / "native")
    _, activated = _activate_real_epoch_scenario(scenario)
    projection = scenario.overlay.read_activated_semantic_epoch_observations(
        receipt_ref=activated.receipt_ref,
        artifact_store=scenario.store,
        passport=scenario.passport,
        authority=scenario.authority,
    )
    with tenant_scope(
        None,
        tenant_id="00000000-0000-4000-8000-000000000101",
        cell_id="00000000-0000-4000-8000-000000000102",
    ):
        case = build_lane01_candidate_source(
            tmp_path / "source",
            monkeypatch,
            store=scenario.store,
            tenant_id="00000000-0000-4000-8000-000000000101",
            cell_id="00000000-0000-4000-8000-000000000102",
        )
        yield SimpleNamespace(
            scenario=scenario,
            activated=activated,
            projection=projection,
            source=case,
            base_ref=_data_snapshot_ref(scenario.store),
            workspace=tmp_path / "materialized",
        )


def _materialize_candidate(case: SimpleNamespace, base_ref: ArtifactRef):
    source = case.source
    binding = CandidateAcquisitionSourceSlotBinding(
        profile_selection_ref="sha256:" + "9" * 64,
        candidate_digest=source.candidate_digest,
        canonical_variable_id=source.entry.target_variable,
        target_slot_id=source.source.target_slot_id,
    )
    assert binding.profile_selection_ref != binding.candidate_digest
    return materialize_candidate_acquisition_snapshot(
        source.store,
        workspace_dir=case.workspace / "candidate",
        base_data_snapshot_ref=base_ref,
        candidate_source_ref=source.source_ref,
        slot_binding=binding,
        transaction_time=datetime(2026, 11, 3, 12, tzinfo=UTC),
        authority=source.authority,
    )


def _materialize_observed(case: SimpleNamespace, base_ref: ArtifactRef):
    selected = case.projection.observations[0].observation
    return materialize_acquired_observation_snapshot(
        case.scenario.store,
        workspace_dir=case.workspace / "observed",
        base_data_snapshot_ref=base_ref,
        overlay=case.scenario.overlay,
        receipt_ref=case.activated.receipt_ref,
        passport=case.scenario.passport,
        authority=case.scenario.authority,
        observation_id=selected.observation_id,
        slot_binding=ControlledAcquisitionSlotBinding(
            profile_selection_ref="sha256:" + "7" * 64,
            canonical_variable_id=selected.canonical_var,
            target_slot_id="government.balance",
        ),
        transaction_time=datetime(2026, 11, 3, 13, tzinfo=UTC),
    )


def _mixed_ancestry(case: SimpleNamespace, order: str):
    if order == "observed_then_candidate":
        base = _materialize_observed(case, case.base_ref)
        descendant = _materialize_candidate(case, base.data_snapshot_ref)
    else:
        base = _materialize_candidate(case, case.base_ref)
        descendant = _materialize_observed(case, base.data_snapshot_ref)
    return base, descendant


def _read_snapshot(store: FileSystemCAS, ref: ArtifactRef) -> DataSnapshot:
    return DataSnapshot.model_validate(load_core_json_artifact(store, ref))


@pytest.mark.parametrize("order", ["observed_then_candidate", "candidate_then_observed"])
def test_actual_mixed_ancestry_preserves_candidate_limits_and_observed_owner(
    owner_case: SimpleNamespace, order: str
) -> None:
    """History may cross owner families; it cannot grant observed authority."""
    base, descendant = _mixed_ancestry(owner_case, order)
    store = FileSystemCAS(owner_case.scenario.store.root)
    base_snapshot = _read_snapshot(store, base.data_snapshot_ref)
    snapshot = _read_snapshot(store, descendant.data_snapshot_ref)
    payload = load_core_json_artifact(store, snapshot.data_ref)
    base_payload = load_core_json_artifact(store, base_snapshot.data_ref)
    source = owner_case.source.source
    assert source.status == "candidate_only"
    assert source.observation_class == "model_output"
    assert snapshot.source_lineage.base_data_snapshot_ref == base.data_snapshot_ref
    assert "_policyos_candidate_acquisition" in payload
    assert "_policyos_acquisition" in payload
    assert payload["_policyos_candidate_acquisition"]["source_provenance_class"] == "model_output"
    assert payload["_policyos_candidate_acquisition"]["limitation_codes"] == list(
        source.limitations
    )
    if order == "observed_then_candidate":
        assert isinstance(snapshot.source_lineage, CandidateAcquisitionSourceDataSnapshotLineage)
        assert payload["_policyos_acquisition"] == base_payload["_policyos_acquisition"]
        assert (
            payload["_policyos_acquisition_history"]
            == base_payload["_policyos_acquisition_history"]
        )
        assert payload["acquisition"]["selected"]["provenance_class"] == "model_output"
        assert payload["acquisition"]["selected"]["value"] == source.observation
        # A genuine historical observed-owner view still replays its full
        # producer body. Version alone must not make every legacy view fail.
        legacy_ref, legacy_snapshot = _legacy_view(store, base.data_snapshot_ref, base_snapshot)
        legacy_verdict = validate_data_snapshot_owner_lineage(
            store, legacy_ref, legacy_snapshot, candidate_only=True
        )
        assert legacy_verdict.required_admissibility_blockers == (
            ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
        )
        with pytest.raises(DataSnapshotSourceRowNotEstablishedError):
            validate_data_snapshot_owner_lineage(store, legacy_ref, legacy_snapshot)
    else:
        assert isinstance(snapshot.source_lineage, AcquiredObservationDataSnapshotLineage)
        assert (
            payload["_policyos_candidate_acquisition"]
            == base_payload["_policyos_candidate_acquisition"]
        )
        assert payload["acquisition"]["selected"]["value"] == (
            owner_case.projection.observations[0].observation.value
        )
        # This declared limitation belongs only to the retained candidate input,
        # not to the current observed owner. Ancestry union is conservative; it
        # does not claim minimal dependencies or perpetual scalar dependence.
        base_only = "current_run_job_route_ownership_not_established"
        assert base_only in source.limitations
        assert base_only not in payload["_policyos_acquisition"]["limitation_codes"]

    verdict = validate_data_snapshot_owner_lineage(
        store, descendant.data_snapshot_ref, snapshot, candidate_only=True
    )
    assert verdict.acquisition_source_row_status == "not_established"
    expected = {
        ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
        *CANDIDATE_SOURCE_LIMITATIONS,
        *source.limitations,
    }
    assert set(verdict.required_admissibility_blockers) == expected
    assert len(verdict.required_admissibility_blockers) == len(expected)
    with pytest.raises(DataSnapshotSourceRowNotEstablishedError) as refusal:
        validate_data_snapshot_owner_lineage(store, descendant.data_snapshot_ref, snapshot)
    assert refusal.value.code == ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION
    if order == "candidate_then_observed":
        # Normalize the genuine observed descendant into its historical wire
        # view while preserving its candidate ancestry and selected owner edges.
        legacy_ref, legacy_snapshot = _legacy_view(store, descendant.data_snapshot_ref, snapshot)
        legacy_verdict = validate_data_snapshot_owner_lineage(
            store, legacy_ref, legacy_snapshot, candidate_only=True
        )
        assert legacy_verdict.required_admissibility_blockers == (
            verdict.required_admissibility_blockers
        )
        with pytest.raises(DataSnapshotSourceRowNotEstablishedError):
            validate_data_snapshot_owner_lineage(store, legacy_ref, legacy_snapshot)

    # Candidate materialization must not insert modeled source rows into the
    # native observed projection, even when its numeric payload is copied later.
    current = owner_case.scenario.overlay.read_activated_semantic_epoch_observations(
        receipt_ref=owner_case.activated.receipt_ref,
        artifact_store=store,
        passport=owner_case.scenario.passport,
        authority=owner_case.scenario.authority,
    )
    assert current == owner_case.projection
    assert all(row.observation.observation_class != "model_output" for row in current.observations)


def _retained_options(manifest: Any, **updates: Any) -> PutOptions:
    values = {
        field.name: getattr(manifest, "artifact_schema" if field.name == "schema" else field.name)
        for field in fields(PutOptions)
    }
    return PutOptions(**{**values, **updates})


def _legacy_view(
    store: FileSystemCAS, snapshot_ref: ArtifactRef, snapshot: DataSnapshot
) -> tuple[ArtifactRef, DataSnapshot]:
    """Retain actual owner bytes/edges under the legacy parent wire shape."""
    legacy = snapshot.model_copy(update={"source_lineage": None})
    legacy_ref = store.put_json(
        legacy,
        _retained_options(
            store.get_manifest(snapshot_ref),
            schema=SchemaInfo(name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version="0.2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return legacy_ref, legacy


@pytest.mark.parametrize(
    ("order", "parent_schema_version"),
    [
        ("observed_then_candidate", "0.3.0"),
        ("candidate_then_observed", "0.3.0"),
        ("observed_then_candidate", "0.2.0"),
    ],
)
def test_mixed_markers_cannot_counterfeit_current_owner_family(
    owner_case: SimpleNamespace, order: str, parent_schema_version: str
) -> None:
    """Substituting schema, typed owner and exact edges cannot launder mixed bytes."""
    base, descendant = _mixed_ancestry(owner_case, order)
    store = FileSystemCAS(owner_case.scenario.store.root)
    ancestor = _read_snapshot(store, base.data_snapshot_ref)
    snapshot = _read_snapshot(store, descendant.data_snapshot_ref)
    payload = load_core_json_artifact(store, snapshot.data_ref)
    assert "_policyos_acquisition" in payload and "_policyos_candidate_acquisition" in payload
    if order == "observed_then_candidate":
        marker = payload["_policyos_acquisition"]
        counterfeit_lineage = AcquiredObservationDataSnapshotLineage(
            base_data_snapshot_ref=ArtifactRef.model_validate(marker["base_data_snapshot_ref"]),
            overlay_admission_receipt_ref=ArtifactRef.model_validate(marker["receipt_ref"]),
            passport_ref=ArtifactRef.model_validate(marker["passport_ref"]),
        )
        counterfeit_schema = SchemaInfo(
            name="polisyos.runtime.quality.AcquisitionDataStatePayload",
            version="policyos.runtime.acquisition_data_state.v2",
        )
        payload_inputs = [
            input_ref_from_artifact_ref(
                counterfeit_lineage.base_data_snapshot_ref, role="input.base_data_snapshot"
            ),
            input_ref_from_artifact_ref(
                counterfeit_lineage.overlay_admission_receipt_ref,
                role="evidence.overlay_admission_receipt",
            ),
            input_ref_from_artifact_ref(
                counterfeit_lineage.passport_ref, role="evidence.acquisition_passport"
            ),
        ]
        snapshot_prefix = "gy-s1-acquisition-overlay-"
        expected_refusal = "acquired_observation_owner_replay_failed"
        # The counterfeit owner points behind the candidate source. If accepted,
        # it would drop source-only blockers while retaining its modeled value.
        assert payload["acquisition"]["selected"]["provenance_class"] == "model_output"
        assert (
            counterfeit_lineage.base_data_snapshot_ref
            == ancestor.source_lineage.base_data_snapshot_ref
            != base.data_snapshot_ref
        )
    else:
        marker = payload["_policyos_candidate_acquisition"]
        counterfeit_lineage = CandidateAcquisitionSourceDataSnapshotLineage(
            base_data_snapshot_ref=ArtifactRef.model_validate(marker["base_data_snapshot_ref"]),
            candidate_source_ref=ArtifactRef.model_validate(marker["candidate_source_ref"]),
        )
        counterfeit_schema = SchemaInfo(
            name="polisyos.runtime.quality.CandidateAcquisitionDataStatePayload",
            version="policyos.runtime.candidate_acquisition_data_state.v1",
        )
        payload_inputs = [
            input_ref_from_artifact_ref(
                counterfeit_lineage.base_data_snapshot_ref, role="input.base_data_snapshot"
            ),
            input_ref_from_artifact_ref(
                counterfeit_lineage.candidate_source_ref,
                role="evidence.candidate_acquisition_source",
            ),
        ]
        snapshot_prefix = "gy-s1-candidate-source-"
        expected_refusal = "candidate_acquisition_source_owner_replay_failed"
    assert counterfeit_lineage == ancestor.source_lineage

    # Reuse the real opposite owner's metadata as well as its typed lineage:
    # stale stats/notes or missing selected edges must not mask the payload test.
    payload_manifest = store.get_manifest_by_profile(
        ancestor.data_ref.artifact_id, ancestor.data_ref.manifest_profile_sha256
    )
    changed_payload = store.put_bytes(
        store.get_bytes(snapshot.data_ref),
        _retained_options(payload_manifest, schema=counterfeit_schema, inputs=payload_inputs),
        return_selected_profile=True,
    )
    assert changed_payload.artifact_id == snapshot.data_ref.artifact_id
    assert store.get_bytes(changed_payload) == store.get_bytes(snapshot.data_ref)
    assert changed_payload.manifest_profile_sha256 != snapshot.data_ref.manifest_profile_sha256
    changed_snapshot = ancestor.model_copy(
        update={
            "data_ref": changed_payload,
            "source_lineage": counterfeit_lineage,
            "stats": {
                **ancestor.stats,
                "snapshot_id": snapshot_prefix
                + str(changed_payload.artifact_id).removeprefix("sha256:")[:20],
            },
        }
    )
    parent = store.get_manifest_by_profile(
        base.data_snapshot_ref.artifact_id, base.data_snapshot_ref.manifest_profile_sha256
    )
    parent_inputs = [
        input_ref_from_artifact_ref(child, role=role)
        for child, role in data_snapshot_owner_input_requirements(changed_snapshot)
    ]
    if parent_schema_version == "0.2.0":
        # The historical parent contract carries no typed lineage field. Its
        # genuine selected receipt/passport/base edges and payload still cannot
        # disguise a newer candidate-source value as acquired-observation data.
        changed_snapshot = changed_snapshot.model_copy(update={"source_lineage": None})
    changed_ref = store.put_json(
        changed_snapshot,
        _retained_options(
            parent,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version=parent_schema_version
            ),
            inputs=parent_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert store.verify(changed_ref).ok and store.verify(changed_payload).ok
    with pytest.raises(DataSnapshotLineageError, match=expected_refusal):
        validate_data_snapshot_owner_lineage(
            store, changed_ref, changed_snapshot, candidate_only=True
        )
    # The original selected profiles remain usable after the adversarial write.
    assert (
        validate_data_snapshot_owner_lineage(
            store, descendant.data_snapshot_ref, snapshot, candidate_only=True
        ).acquisition_source_row_status
        == "not_established"
    )
