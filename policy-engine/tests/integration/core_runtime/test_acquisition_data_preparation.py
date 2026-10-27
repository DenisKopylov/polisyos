"""Real-owner checks for the write-free acquisition preparation seam."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, data_snapshot_owner_input_requirements
from polisyos.data_forge.domains.catalog.knowledge.overlay import OverlayAdmissionError
from polisyos.runtime.quality.data_snapshot_lineage import (
    ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
    DataSnapshotLineageError,
    DataSnapshotSourceRowNotEstablishedError,
    validate_data_snapshot_owner_lineage,
)
from polisyos.runtime.quality.data_state_substrate import (
    AcquiredObservationDataPreparation,
    ControlledAcquisitionSlotBinding,
    DataStateSubstrateError,
    _acquisition_preparation_sha256,
    materialize_acquired_observation_snapshot,
    prepare_acquired_observation_snapshot,
)
from tests._helpers import world_model_record as world_fixture
from tests._helpers.semantic_epoch_native import _real_epoch_scenario
from tests.unit.runtime.quality.test_acquisition_executor import _activate_real_epoch_scenario


@pytest.fixture
def owner_case(tmp_path: Path):
    """Activate the actual native overlay without the unrelated N7 route."""

    scenario = _real_epoch_scenario(tmp_path)
    _, activated = _activate_real_epoch_scenario(scenario)
    projection = scenario.overlay.read_activated_semantic_epoch_observations(
        receipt_ref=activated.receipt_ref,
        artifact_store=scenario.store,
        passport=scenario.passport,
        authority=scenario.authority,
    )
    selected = projection.observations[0]
    args = {
        "base_data_snapshot_ref": world_fixture._data_snapshot_ref(scenario.store),
        "overlay": scenario.overlay,
        "receipt_ref": activated.receipt_ref,
        "passport": scenario.passport,
        "authority": scenario.authority,
        "observation_id": selected.observation.observation_id,
        "slot_binding": ControlledAcquisitionSlotBinding(
            profile_selection_ref="sha256:" + "7" * 64,
            canonical_variable_id=selected.observation.canonical_var,
            target_slot_id="government.balance",
        ),
        "transaction_time": datetime(2026, 10, 2, 12, 0, tzinfo=UTC),
    }
    return SimpleNamespace(
        scenario=scenario,
        args=args,
        selected=selected,
        projection=projection,
        workspace=tmp_path / "candidate-data-forge",
    )


def _observe_store_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    """Observe real CAS write entrypoints without replacing their behavior."""

    writes: list[str] = []
    for name in ("put_json", "put_bytes", "put_signature", "import_exact_view", "import_subgraph"):
        original = getattr(FileSystemCAS, name)

        def observed(*args: Any, _name: str = name, _original=original, **kwargs: Any) -> Any:
            writes.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(FileSystemCAS, name, observed)
    return writes


def _resign(prepared: AcquiredObservationDataPreparation, **updates: Any):
    """Model an adversary who can recompute every public candidate digest."""

    changed = replace(prepared, **updates)
    return replace(
        changed,
        preparation_sha256=_acquisition_preparation_sha256(changed, include_digest=False),
    )


def test_preparation_has_no_cas_write_and_materialization_rechecks_actual_owner(
    owner_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = owner_case.scenario.store
    writes = _observe_store_writes(monkeypatch)
    read_owner = owner_case.scenario.overlay.read_activated_semantic_epoch_observations
    reads: list[object] = []

    def observed_owner(**kwargs: Any):
        result = read_owner(**kwargs)
        reads.append(result)
        return result

    monkeypatch.setattr(
        owner_case.scenario.overlay, "read_activated_semantic_epoch_observations", observed_owner
    )
    prepared = prepare_acquired_observation_snapshot(store, **owner_case.args)
    assert writes == []
    assert not owner_case.workspace.exists()
    assert len(reads) == 1
    first = prepared.payload()
    first["acquisition"]["selected"]["value"] = "mutated"
    assert prepared.payload()["acquisition"]["selected"]["value"] == (
        owner_case.selected.observation.value
    )
    materialized = materialize_acquired_observation_snapshot(
        store, **owner_case.args, workspace_dir=owner_case.workspace, prepared=prepared
    )
    assert len(reads) == 2
    assert writes
    fresh_store = FileSystemCAS(store.root)
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(fresh_store.get_bytes(materialized.data_snapshot_ref))
    )
    payload = from_canonical_bytes(fresh_store.get_bytes(snapshot.data_ref))
    lineage_result = validate_data_snapshot_owner_lineage(
        fresh_store, materialized.data_snapshot_ref, snapshot, candidate_only=True
    )
    assert lineage_result.acquisition_source_row_status == "not_established"
    assert lineage_result.required_admissibility_blockers == (
        ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
    )
    assert payload == prepared.payload()
    assert payload["_policyos_acquisition"]["base_data_snapshot_id"] == str(
        owner_case.args["base_data_snapshot_ref"].artifact_id
    )
    assert materialized.data_snapshot_ref.manifest_profile_sha256 is not None
    assert prepared.base_snapshot_id != str(owner_case.args["base_data_snapshot_ref"].artifact_id)
    assert (
        snapshot.source_lineage.base_data_snapshot_ref == owner_case.args["base_data_snapshot_ref"]
    )
    assert materialized.observation_projection == owner_case.projection


@pytest.mark.parametrize("field", ["payload", "foundry_rule", "lineage", "base_profile"])
def test_resigned_preparation_cannot_replace_fresh_owner_result(
    owner_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    store = owner_case.scenario.store
    prepared = prepare_acquired_observation_snapshot(store, **owner_case.args)
    if field == "payload":
        payload = prepared.payload()
        payload["acquisition"]["selected"]["value"] = "999"
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        forged = _resign(
            prepared,
            payload_json=encoded,
            payload_sha256=hashlib.sha256(encoded).hexdigest(),
        )
    elif field == "foundry_rule":
        forged = _resign(
            prepared,
            foundry_binding_rule=prepared.foundry_binding_rule.model_copy(
                update={"target_slot_id": "agents.income"}
            ),
        )
    elif field == "lineage":
        forged = _resign(prepared, lineage_inputs=())
    else:
        forged = _resign(
            prepared,
            base_data_snapshot_ref=prepared.base_data_snapshot_ref.model_copy(
                update={"manifest_profile_sha256": "sha256:" + "0" * 64}
            ),
        )
        assert (
            forged.base_data_snapshot_ref.artifact_id == prepared.base_data_snapshot_ref.artifact_id
        )
    # The content digest is internally consistent: it cannot establish owner issuance.
    forged.validate_content_binding()
    writes = _observe_store_writes(monkeypatch)
    with pytest.raises(
        DataStateSubstrateError, match="acquisition_preparation_owner_state_changed"
    ):
        materialize_acquired_observation_snapshot(
            store, **owner_case.args, workspace_dir=owner_case.workspace, prepared=forged
        )
    assert writes == []
    assert not owner_case.workspace.exists()


@pytest.mark.parametrize("drift", ["activation", "row"])
def test_prepared_candidate_does_not_bypass_current_overlay_owner(
    owner_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    store = owner_case.scenario.store
    prepared = prepare_acquired_observation_snapshot(store, **owner_case.args)
    con = duckdb.connect(str(owner_case.scenario.overlay.overlay_path))
    try:
        if drift == "activation":
            con.execute(
                "UPDATE acquisition_epochs SET epoch_activation_state = 'legacy_not_established' "
                "WHERE epoch_id = ? AND passport_id = ?",
                [owner_case.scenario.passport.epoch_id, owner_case.scenario.passport.passport_id],
            )
            code = "epoch_activation_state_not_active"
        else:
            con.execute(
                "UPDATE ds_observations SET value = ? WHERE observation_id = ?",
                [
                    float(owner_case.selected.observation.value) + 1.0,
                    prepared.selected_observation_id,
                ],
            )
            code = "active_epoch_observation_content_mismatch"
    finally:
        con.close()
    writes = _observe_store_writes(monkeypatch)
    with pytest.raises(OverlayAdmissionError, match=code):
        materialize_acquired_observation_snapshot(
            store, **owner_case.args, workspace_dir=owner_case.workspace, prepared=prepared
        )
    assert writes == []
    assert not owner_case.workspace.exists()


@pytest.mark.parametrize("wrong", ["overlay", "passport", "authority"])
def test_prepared_candidate_preserves_materialization_owner_inputs(
    owner_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, wrong: str
) -> None:
    store = owner_case.scenario.store
    prepared = prepare_acquired_observation_snapshot(store, **owner_case.args)
    changed = dict(owner_case.args)
    if wrong == "overlay":
        changed[wrong] = object()
        code = "acquisition_overlay_owner_untyped"
        expected = DataStateSubstrateError
    elif wrong == "passport":
        changed[wrong] = changed[wrong].model_copy(update={"passport_id": "wrong-passport"})
        code = "active_epoch_passport_binding_mismatch"
        expected = OverlayAdmissionError
    else:
        changed[wrong] = object()
        code = "acquisition_authority_unresolved"
        expected = OverlayAdmissionError
    writes = _observe_store_writes(monkeypatch)
    with pytest.raises(expected, match=code):
        materialize_acquired_observation_snapshot(
            store, **changed, workspace_dir=owner_case.workspace, prepared=prepared
        )
    assert writes == []
    assert not owner_case.workspace.exists()


def test_duck_preparation_cannot_supply_materialized_payload(
    owner_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = owner_case.scenario.store
    prepared = prepare_acquired_observation_snapshot(store, **owner_case.args)
    calls: list[str] = []

    def forged_payload():
        calls.append("forged_payload")
        return {"candidate": "wrong"}

    forged = SimpleNamespace(**vars(prepared), payload=forged_payload)
    writes = _observe_store_writes(monkeypatch)
    with pytest.raises(DataStateSubstrateError, match="acquisition_preparation_untyped"):
        materialize_acquired_observation_snapshot(
            store, **owner_case.args, workspace_dir=owner_case.workspace, prepared=forged
        )
    assert calls == []
    assert writes == []
    assert not owner_case.workspace.exists()


def test_explicit_preparation_preserves_aware_transaction_time_check(
    owner_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = owner_case.scenario.store
    prepared = prepare_acquired_observation_snapshot(store, **owner_case.args)
    changed = {**owner_case.args, "transaction_time": datetime(2026, 10, 2, 12, 0)}
    writes = _observe_store_writes(monkeypatch)
    with pytest.raises(DataStateSubstrateError, match="acquisition_transaction_time_must_be_aware"):
        materialize_acquired_observation_snapshot(
            store, **changed, workspace_dir=owner_case.workspace, prepared=prepared
        )
    assert writes == []
    assert not owner_case.workspace.exists()


def test_unresigned_payload_drift_fails_content_check(owner_case: SimpleNamespace) -> None:
    prepared = prepare_acquired_observation_snapshot(owner_case.scenario.store, **owner_case.args)
    with pytest.raises(DataStateSubstrateError, match="acquisition_preparation_content_changed"):
        replace(prepared, payload_json=prepared.payload_json + b" ").payload()


def test_supplied_preparation_is_bound_to_the_actual_declared_target_slot(
    owner_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = owner_case.scenario.store
    prepared = prepare_acquired_observation_snapshot(store, **owner_case.args)
    changed = {
        **owner_case.args,
        "slot_binding": owner_case.args["slot_binding"].model_copy(
            update={"target_slot_id": "agents.income"}
        ),
    }
    writes = _observe_store_writes(monkeypatch)
    with pytest.raises(
        DataStateSubstrateError, match="acquisition_preparation_owner_state_changed"
    ):
        materialize_acquired_observation_snapshot(
            store, **changed, workspace_dir=owner_case.workspace, prepared=prepared
        )
    assert writes == []
    assert not owner_case.workspace.exists()


@pytest.mark.parametrize(
    "invalid", ["child_profile", "missing_parent_edge", "owner_schema_without_lineage"]
)
def test_generic_legacy_base_still_requires_selected_typed_closure(
    owner_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    store = owner_case.scenario.store
    original_ref = owner_case.args["base_data_snapshot_ref"]
    snapshot = DataSnapshot.model_validate(from_canonical_bytes(store.get_bytes(original_ref)))
    assert snapshot.source_lineage is None
    original_manifest = store.get_manifest_by_profile(
        original_ref.artifact_id, original_ref.manifest_profile_sha256
    )
    schema_version = "0.2.0"
    if invalid == "child_profile":
        snapshot.data_ref = snapshot.data_ref.model_copy(update={"manifest_profile_sha256": None})
        code = "acquisition_base_snapshot_child_profile_unselected"
    elif invalid == "missing_parent_edge":
        snapshot.quality_report_ref = store.put_json(
            {"quality": "candidate_fixture"},
            PutOptions(kind="fabric.quality_report", media_type="application/json"),
            return_selected_profile=True,
        )
        code = "acquisition_base_snapshot_owner_lineage_invalid"
    else:
        schema_version = "0.3.0"
        code = "acquisition_base_snapshot_owner_lineage_invalid"
    alternate = store.put_json(
        snapshot.model_dump(mode="json"),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version=schema_version),
            inputs=list(original_manifest.inputs),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    writes = _observe_store_writes(monkeypatch)
    with pytest.raises(DataStateSubstrateError, match=code):
        prepare_acquired_observation_snapshot(
            store, **{**owner_case.args, "base_data_snapshot_ref": alternate}
        )
    assert writes == []
    assert not owner_case.workspace.exists()


def _same_write_options(manifest: Any, **updates: Any) -> PutOptions:
    """Retain exact selected metadata, respecting the manifest's schema alias."""
    values = {
        field.name: getattr(manifest, "artifact_schema" if field.name == "schema" else field.name)
        for field in fields(PutOptions)
    }
    return PutOptions(**{**values, **updates})


def _rebind_candidate_owner_ref(
    store: FileSystemCAS,
    snapshot_ref: Any,
    selected_ref: Any,
    *,
    member: str,
    update_payload: bool,
    omit_parent_edge: bool = False,
):
    """Persist an untrusted but type-shaped alternative for the actual reader."""
    snapshot = DataSnapshot.model_validate(from_canonical_bytes(store.get_bytes(snapshot_ref)))
    parent = store.get_manifest_by_profile(
        snapshot_ref.artifact_id, snapshot_ref.manifest_profile_sha256
    )
    lineage = snapshot.source_lineage.model_copy(update={member: selected_ref})
    selected_role = (
        "evidence.overlay_admission_receipt"
        if member == "overlay_admission_receipt_ref"
        else "evidence.acquisition_passport"
    )
    if update_payload:
        payload = from_canonical_bytes(store.get_bytes(snapshot.data_ref))
        payload_key = "receipt_ref" if member == "overlay_admission_receipt_ref" else "passport_ref"
        payload["_policyos_acquisition"][payload_key] = selected_ref.model_dump(mode="json")
        payload_manifest = store.get_manifest_by_profile(
            snapshot.data_ref.artifact_id, snapshot.data_ref.manifest_profile_sha256
        )
        payload_inputs = [
            input_ref_from_artifact_ref(ref, role=role)
            for ref, role in data_snapshot_owner_input_requirements(
                snapshot.model_copy(update={"source_lineage": lineage})
            )
            if role != "payload.acquired_observation_candidate"
        ]
        payload_ref = store.put_json(
            payload,
            _same_write_options(payload_manifest, inputs=payload_inputs),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        snapshot = snapshot.model_copy(update={"data_ref": payload_ref})
    snapshot = snapshot.model_copy(update={"source_lineage": lineage})
    inputs = [
        input_ref_from_artifact_ref(ref, role=role)
        for ref, role in data_snapshot_owner_input_requirements(snapshot)
        if not (omit_parent_edge and role == selected_role)
    ]
    return store.put_json(
        snapshot.model_dump(mode="json"),
        _same_write_options(parent, inputs=inputs),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


@pytest.mark.parametrize("member", ["overlay_admission_receipt_ref", "passport_ref"])
@pytest.mark.parametrize("invalid", ["kind", "media", "profile", "missing_edge"])
def test_fresh_lineage_consumer_rejects_wrong_epoch_codec_and_unbound_profile(
    owner_case: SimpleNamespace, invalid: str, member: str
) -> None:
    store = owner_case.scenario.store
    prepared = prepare_acquired_observation_snapshot(store, **owner_case.args)
    materialized = materialize_acquired_observation_snapshot(
        store, **owner_case.args, workspace_dir=owner_case.workspace, prepared=prepared
    )
    original_snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(materialized.data_snapshot_ref))
    )
    validate_data_snapshot_owner_lineage(
        store, materialized.data_snapshot_ref, original_snapshot, candidate_only=True
    )
    original = getattr(original_snapshot.source_lineage, member)
    manifest = store.get_manifest_by_profile(original.artifact_id, original.manifest_profile_sha256)
    if invalid == "kind":
        opts = _same_write_options(manifest, kind="fixture.untrusted_epoch_receipt")
    elif invalid == "media":
        opts = _same_write_options(manifest, media_type="application/octet-stream", canon=None)
    elif invalid == "profile":
        opts = _same_write_options(
            manifest, producer=ProducerInfo(component="fixture.alternate_view", version="1.0")
        )
    else:
        opts = None
    if opts is not None:
        selected = store.put_bytes(store.get_bytes(original), opts, return_selected_profile=True)
        assert selected.artifact_id == original.artifact_id
        assert selected.manifest_profile_sha256 != original.manifest_profile_sha256
        assert store.verify(selected).ok
    else:
        selected = original
    candidate = _rebind_candidate_owner_ref(
        store,
        materialized.data_snapshot_ref,
        selected,
        member=member,
        update_payload=invalid in {"kind", "media"},
        omit_parent_edge=invalid == "missing_edge",
    )
    fresh_store = FileSystemCAS(store.root)
    snapshot = DataSnapshot.model_validate(from_canonical_bytes(fresh_store.get_bytes(candidate)))
    expected = {
        "kind": "acquired_observation_owner_child_mismatch",
        "media": "acquired_observation_owner_child_mismatch",
        "profile": "data_snapshot_owner_source_edges_mismatch",
        "missing_edge": "data_snapshot_owner_parent_inputs_mismatch",
    }[invalid]
    with pytest.raises(DataSnapshotLineageError, match=expected) as failure:
        validate_data_snapshot_owner_lineage(fresh_store, candidate, snapshot, candidate_only=True)
    if invalid in {"kind", "media"}:
        assert isinstance(failure.value.__cause__, ValueError)
        assert "epoch statement reference profile differs" in str(failure.value.__cause__)


def _coherently_forged_materialization(owner_case: SimpleNamespace, *, forge: bool):
    """Change selected value/history and self-hashes while preserving real owner refs."""
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        ActivatedAcquisitionObservationProjection,
    )
    from polisyos.runtime.quality import data_state_substrate as owner

    store = owner_case.scenario.store
    prepared = prepare_acquired_observation_snapshot(store, **owner_case.args)
    issued = materialize_acquired_observation_snapshot(
        store, **owner_case.args, workspace_dir=owner_case.workspace, prepared=prepared
    )
    if not forge:
        return issued
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(issued.data_snapshot_ref))
    )
    payload = from_canonical_bytes(store.get_bytes(snapshot.data_ref))
    projection = prepared.observation_projection
    changed_observation = owner_case.selected.observation.model_copy(
        update={"value": float(owner_case.selected.observation.value) + 1.0}
    )
    forged_projection = ActivatedAcquisitionObservationProjection.issue(
        receipt_ref=projection.receipt_ref,
        receipt_content_sha256=projection.receipt_content_sha256,
        passport_ref=projection.passport_ref,
        passport_content_sha256=projection.passport_content_sha256,
        variable_id=projection.variable_id,
        epoch_id=projection.epoch_id,
        passport_id=projection.passport_id,
        admission_content_sha256=projection.admission_content_sha256,
        observations=[
            changed_observation
            if row.observation.observation_id == changed_observation.observation_id
            else row.observation
            for row in projection.observations
        ],
    )
    selected_row = next(
        row
        for row in forged_projection.observations
        if row.observation.observation_id == changed_observation.observation_id
    )
    payload["acquisition"]["selected"]["value"] = changed_observation.value
    payload["acquisition"]["selected"]["row_content_sha256"] = selected_row.row_content_sha256
    payload["_policyos_acquisition"]["selected_row_content_sha256"] = (
        selected_row.row_content_sha256
    )
    payload["_policyos_acquisition"]["projection_content_sha256"] = (
        forged_projection.projection_content_sha256
    )
    for row in payload["_policyos_acquisition_history"]:
        if row["observation_id"] == changed_observation.observation_id:
            row["observation"] = changed_observation.model_dump(mode="json")
            row["row_content_sha256"] = selected_row.row_content_sha256
            row["projection_content_sha256"] = forged_projection.projection_content_sha256
    payload_manifest = store.get_manifest_by_profile(
        snapshot.data_ref.artifact_id, snapshot.data_ref.manifest_profile_sha256
    )
    payload_ref = store.put_json(
        payload,
        _same_write_options(payload_manifest),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    snapshot_id = (
        "gy-s1-acquisition-overlay-" + str(payload_ref.artifact_id).removeprefix("sha256:")[:20]
    )
    snapshot = snapshot.model_copy(
        update={
            "data_ref": payload_ref,
            "stats": {
                **snapshot.stats,
                "snapshot_id": snapshot_id,
                "selected_row_content_sha256": selected_row.row_content_sha256,
                "projection_content_sha256": forged_projection.projection_content_sha256,
            },
        }
    )
    parent = store.get_manifest_by_profile(
        issued.data_snapshot_ref.artifact_id, issued.data_snapshot_ref.manifest_profile_sha256
    )
    inputs = [
        input_ref_from_artifact_ref(ref, role=role)
        for ref, role in data_snapshot_owner_input_requirements(snapshot)
    ]
    snapshot_ref = store.put_json(
        snapshot.model_dump(mode="json"),
        _same_write_options(parent, inputs=inputs),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    binding = owner._write_data_forge_snapshot_binding(
        workspace_dir=owner_case.workspace.parent / "forged-candidate-data",
        snapshot_id=snapshot_id,
        payload=payload,
        payload_content_hash=str(payload_ref.artifact_id),
        published_at=owner_case.args["transaction_time"].isoformat(),
        corpus_id="candidate-acquisition-observation-overlay",
        builder_revision="polisyos.runtime.quality.data_state_substrate.materialize_acquired_observation_snapshot",
        lineage_refs=tuple(
            owner._cas_data_forge_ref(ref)
            for ref in (
                snapshot.source_lineage.base_data_snapshot_ref,
                snapshot.source_lineage.overlay_admission_receipt_ref,
                snapshot.source_lineage.passport_ref,
                payload_ref,
            )
        ),
        claim_requirement_bindings=(
            {
                "claim_id": "candidate-acquired-world-state",
                "requirement_id": f"candidate-observation:{prepared.selected_profile.canonical_variable_id}",
                "requirement_kind": "candidate_acquisition_observation",
                "authority_level": "candidate",
                "time_role": "transaction_time",
            },
        ),
    )
    actual = owner_case.scenario.overlay.read_activated_semantic_epoch_observations(
        receipt_ref=owner_case.args["receipt_ref"],
        artifact_store=store,
        passport=owner_case.scenario.passport,
        authority=owner_case.scenario.authority,
    )
    real_row = next(
        row
        for row in actual.observations
        if row.observation.observation_id == changed_observation.observation_id
    )
    assert real_row.observation.value != payload["acquisition"]["selected"]["value"]
    assert snapshot.source_lineage.overlay_admission_receipt_ref == projection.receipt_ref
    assert snapshot.source_lineage.passport_ref == projection.passport_ref
    return replace(
        issued,
        data_snapshot_ref=snapshot_ref,
        data_forge_snapshot_binding_path=binding,
        snapshot_id=snapshot_id,
        payload_content_hash=str(payload_ref.artifact_id),
        observation_projection=forged_projection,
    )


@pytest.mark.parametrize("forge", [False, True])
def test_store_only_acquisition_rows_never_enter_the_authority_band(
    owner_case: SimpleNamespace, forge: bool
) -> None:
    result = _coherently_forged_materialization(owner_case, forge=forge)
    store = FileSystemCAS(owner_case.scenario.store.root)
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(result.data_snapshot_ref))
    )
    # The candidate structural path must reach and verify all real CAS/epoch edges.
    verdict = validate_data_snapshot_owner_lineage(
        store, result.data_snapshot_ref, snapshot, candidate_only=True
    )
    assert verdict.acquisition_source_row_status == "not_established"
    assert verdict.required_admissibility_blockers == (ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,)
    with pytest.raises(DataSnapshotSourceRowNotEstablishedError) as refusal:
        validate_data_snapshot_owner_lineage(store, result.data_snapshot_ref, snapshot)
    assert refusal.value.code == ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION


def test_acquired_world_is_limited_and_default_authority_reentry_refuses_coherent_forgery(
    owner_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.runtime.quality import data_state_substrate as owner
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
    from polisyos.runtime.quality.world_model_record import (
        WorldModelRecordError,
        load_world_model_record,
    )

    store = owner_case.scenario.store
    result = _coherently_forged_materialization(owner_case, forge=True)
    _same_store, base_world, _model_spec, _bundle = world_fixture._build_record(
        store.root.parent,
        data_snapshot_factory=lambda _store: owner_case.args["base_data_snapshot_ref"],
    )
    registry = world_fixture._substrate_registry()
    registry_ref = persist_substrate_registry(store, registry)
    kwargs = {
        "base_world_model": base_world.record,
        "substrate_registry": registry,
        "substrate_registry_artifact_ref": registry_ref,
        "materialization": result,
        "transaction_time": owner_case.args["transaction_time"],
    }
    candidate = owner.build_acquired_observation_candidate_world(
        store, **kwargs, workspace_dir=owner_case.workspace.parent / "candidate-limited-world"
    )
    assert candidate.world_model.record.authority_status == "limited"
    assert (
        ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION
        in candidate.world_model.record.limitations.admissibility_blockers
    )
    assert (
        load_world_model_record(store, candidate.world_model.record_ref).authority_status
        == "limited"
    )
    from polisyos.runtime.quality.world_model_record import (
        WorldModelRecord,
        persist_world_model_record,
        world_model_record_content_hash_from_fields,
    )

    bound = candidate.world_model.record.model_copy(update={"authority_status": "bound"})
    bound_ref = persist_world_model_record(store, bound)
    with pytest.raises(WorldModelRecordError) as false_bound:
        load_world_model_record(store, bound_ref)
    assert isinstance(false_bound.value.__cause__, DataSnapshotSourceRowNotEstablishedError)
    fields = candidate.world_model.record.model_dump(
        mode="python", exclude={"world_model_record_id", "content_hash"}
    )
    fields["limitations"] = candidate.world_model.record.limitations.model_copy(
        update={
            "admissibility_blockers": tuple(
                value
                for value in candidate.world_model.record.limitations.admissibility_blockers
                if value != ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION
            )
        }
    )
    digest = world_model_record_content_hash_from_fields(fields)
    omitted = WorldModelRecord(
        world_model_record_id=f"world_model_record_{digest.removeprefix('sha256:')[:16]}",
        content_hash=digest,
        **fields,
    )
    omitted_ref = persist_world_model_record(store, omitted)
    with pytest.raises(
        WorldModelRecordError, match="world_model_record_source_row_limitation_missing"
    ):
        load_world_model_record(store, omitted_ref)
    actual_builder = owner.build_world_model_record

    def request_authority(*args: Any, **supplied: Any):
        assert supplied["candidate_only"] is True
        return actual_builder(*args, **{**supplied, "candidate_only": False})

    monkeypatch.setattr(owner, "build_world_model_record", request_authority)
    with pytest.raises(
        WorldModelRecordError, match="data_snapshot_owner_lineage_invalid"
    ) as blocked:
        owner.build_acquired_observation_candidate_world(
            store, **kwargs, workspace_dir=owner_case.workspace.parent / "authority-request-world"
        )
    assert isinstance(blocked.value.__cause__, DataSnapshotSourceRowNotEstablishedError)


def test_predictive_observed_intake_refuses_coherent_acquired_rows(
    owner_case: SimpleNamespace,
) -> None:
    from polisyos.runtime.http.services.predictive_calibration import (
        PredictiveCalibrationError,
        _load_verified_observed_data_snapshot,
    )

    result = _coherently_forged_materialization(owner_case, forge=True)
    with pytest.raises(PredictiveCalibrationError) as refusal:
        _load_verified_observed_data_snapshot(owner_case.scenario.store, result.data_snapshot_ref)
    assert refusal.value.code == "predictive_calibration_acquired_source_row_not_established"
    assert isinstance(refusal.value.__cause__, DataSnapshotSourceRowNotEstablishedError)


def test_predictive_observed_intake_keeps_valid_generic_legacy_snapshot(
    owner_case: SimpleNamespace,
) -> None:
    from polisyos.runtime.http.services.predictive_calibration import (
        _load_verified_observed_data_snapshot,
    )

    result = _load_verified_observed_data_snapshot(
        owner_case.scenario.store, owner_case.args["base_data_snapshot_ref"]
    )
    assert result.source_lineage is None
    assert result.data_ref.manifest_profile_sha256 is not None


def test_actual_l4_legacy_producer_result_remains_usable_by_world_and_predictive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use the real S1 writer/finalizer; controlled source projection is not production proof."""
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.runtime.http.services.predictive_calibration import (
        _load_verified_observed_data_snapshot,
    )
    from polisyos.runtime.quality import data_state_substrate as owner
    from polisyos.runtime.quality.world_model_record import (
        build_world_model_record,
        load_world_model_record,
    )

    store = FileSystemCAS(tmp_path / "cas")
    paths = owner._DataStatePaths(
        l1_dcat_path=tmp_path / "l1.parquet",
        agent_registry_full=tmp_path / "agent-registry.parquet",
        firm_fundamentals_annual=tmp_path / "firm-fundamentals.parquet",
        budget_flows_monthly_sparse=tmp_path / "budget-flows.parquet",
        corrected_firm_panels=tmp_path / "corrected-firm-panels.parquet",
        calibrated_household_cells=tmp_path / "calibrated-household-cells.parquet",
    )
    # Only upstream source availability/projection is a compact fixture here.
    # The target writer, CAS, finalizer, typed reader and WMR/PCL consumers are real.
    monkeypatch.setattr(owner, "_default_data_state_paths", lambda *_a, **_k: paths)
    monkeypatch.setattr(owner, "_require_paths", lambda *_a, **_k: None)
    monkeypatch.setattr(
        owner,
        "build_l5_family_binding_profile",
        lambda *_a, **_k: SimpleNamespace(
            schema_regime_status="single_regime",
            model_dump=lambda **_kwargs: {"schema_version": "controlled-source-projection"},
        ),
    )
    monkeypatch.setattr(
        owner,
        "_project_real_l4_payload",
        lambda *_a, **_k: (
            world_fixture.FABRIC_PAYLOAD,
            {
                "bound_agent_count": 2,
                "l4_total_rows": {"agent_registry_full": 2, "budget_flows_monthly_sparse": 0},
            },
        ),
    )
    materialized = owner.materialize_l4_data_state_snapshot(
        store,
        repo_root=tmp_path,
        workspace_dir=tmp_path / "actual-l4-writer",
        agent_limit=2,
        required_l1_variables=(),
        families=("firm_fundamentals",),
        substrate_registry=SimpleNamespace(substrate_version_id="controlled-source-projection"),
        period_start="2026-01",
        period_end="2026-02",
    )
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(materialized.data_snapshot_ref))
    )
    payload_manifest = store.get_manifest_by_profile(
        snapshot.data_ref.artifact_id, snapshot.data_ref.manifest_profile_sha256
    )
    assert payload_manifest.kind == "fabric.production_data_state_payload"
    assert payload_manifest.artifact_schema == SchemaInfo(
        name="polisyos.runtime.quality.DataStatePayload",
        version=owner.DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
    )
    assert snapshot.source_lineage is None
    verdict = validate_data_snapshot_owner_lineage(store, materialized.data_snapshot_ref, snapshot)
    assert verdict.acquisition_source_row_status == "not_applicable"
    assert verdict.required_admissibility_blockers == ()
    observed = _load_verified_observed_data_snapshot(store, materialized.data_snapshot_ref)
    assert observed.model_dump(mode="json") == snapshot.model_dump(mode="json")
    bundle = build_default_registry_bundle(store)
    model_spec = world_fixture._model_spec(materialized.data_snapshot_ref, bundle.bundle_ref)
    world_fixture._write_fabric_world_snapshot(tmp_path, snapshot_id=materialized.snapshot_id)
    built = build_world_model_record(
        store,
        fabric_world_ref=world_fixture._fabric_ref(tmp_path, snapshot_id=materialized.snapshot_id),
        data_forge_snapshot_binding_path=materialized.data_forge_snapshot_binding_path,
        data_snapshot_ref=materialized.data_snapshot_ref,
        model_spec=model_spec,
        skg_causal_prior_ref=world_fixture._skg_ref(tmp_path, snapshot_id=materialized.snapshot_id),
        substrate_registry=world_fixture._substrate_registry(),
        region_or_jurisdiction="UA-30",
        population_scope="controlled-source-projection",
        policy_domain="fiscal_credit",
        valid_time_scope="2026-05-24/2026-12-31",
        tx_time_scope="2026-05-24T12:00:00+00:00",
        resolution="firm_month",
        branch_mode=world_fixture.BranchMode.OBSERVED,
        policy_slot_ids=("agents.income", "government.balance"),
        producer_ref="test.l4_contract_composition",
        required_substrate_families=("firm_fundamentals",),
        data_forge_role=materialized.data_forge_role,
    )
    assert built.record.authority_status == "bound"
    assert (
        ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION
        not in built.record.limitations.admissibility_blockers
    )
    assert load_world_model_record(store, built.record_ref).authority_status == "bound"
