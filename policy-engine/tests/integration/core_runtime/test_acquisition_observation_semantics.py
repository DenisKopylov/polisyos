"""Real preparation/materialization/replay checks for candidate observation semantics."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.data_forge import read_api
from polisyos.runtime.quality import data_state_substrate as owner
from tests._helpers import semantic_epoch_native as native_fixture
from tests._helpers import world_model_record as world_fixture
from tests.unit.runtime.quality.test_acquisition_executor import _activate_real_epoch_scenario


def _case(root: Path, *, epoch_id: int = 1) -> SimpleNamespace:
    scenario = native_fixture._real_epoch_scenario(root, epoch_id=epoch_id)
    _, activated = _activate_real_epoch_scenario(scenario)
    projection = scenario.overlay.read_activated_semantic_epoch_observations(
        receipt_ref=activated.receipt_ref,
        artifact_store=scenario.store,
        passport=scenario.passport,
        authority=scenario.authority,
    )
    selected = projection.observations[0].observation
    args = {
        "base_data_snapshot_ref": world_fixture._data_snapshot_ref(scenario.store),
        "overlay": scenario.overlay,
        "receipt_ref": activated.receipt_ref,
        "passport": scenario.passport,
        "authority": scenario.authority,
        "observation_id": selected.observation_id,
        "slot_binding": owner.ControlledAcquisitionSlotBinding(
            profile_selection_ref="sha256:" + "7" * 64,
            canonical_variable_id=selected.canonical_var,
            target_slot_id="government.balance",
        ),
        "transaction_time": datetime(2026, 10, 2, 12, tzinfo=UTC),
    }
    prepared = owner.prepare_acquired_observation_snapshot(scenario.store, **args)
    return SimpleNamespace(
        scenario=scenario, args=args, prepared=prepared, workspace=root / "materialized"
    )


def test_real_preparation_and_fresh_selected_snapshot_replay_use_one_semantic_projection(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    prepared_values = owner.prepare_acquired_observation_semantic_values(case.prepared)
    issued = owner.materialize_acquired_observation_snapshot(
        case.scenario.store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    fresh_store = FileSystemCAS(case.scenario.store.root)
    replayed = owner.read_acquired_observation_semantic_values(
        fresh_store, issued.data_snapshot_ref
    )
    assert replayed == prepared_values
    expected_rule = owner.read_acquired_observation_binding_rule(
        fresh_store, issued.data_snapshot_ref
    )
    assert expected_rule == issued.foundry_binding_rule
    assert owner.acquired_observation_binding_rule_values(
        case.prepared
    ) == expected_rule.model_dump(mode="json", exclude={"notes"})
    row = case.prepared.observation_projection.observations[0].observation
    semantic_row = replayed["observation"]
    assert isinstance(semantic_row, dict)
    wire_row = row.model_dump(mode="json")
    assert semantic_row == {
        name: wire_row.get(name) for name in type(row).model_fields if name != "observation_id"
    }
    assert replayed["selected_row_count"] == 1
    assert "source_watermark" in semantic_row
    assert "dataset_version" in semantic_row
    assert "condition_json" in semantic_row


def test_real_new_epoch_with_only_occurrence_id_change_has_equal_semantic_values(
    tmp_path: Path,
) -> None:
    previous = _case(tmp_path / "previous", epoch_id=1)
    current = _case(tmp_path / "current", epoch_id=2)
    assert previous.prepared.selected_observation_id != current.prepared.selected_observation_id
    assert previous.prepared.foundry_binding_rule != current.prepared.foundry_binding_rule
    assert owner.prepare_acquired_observation_semantic_values(previous.prepared) == (
        owner.prepare_acquired_observation_semantic_values(current.prepared)
    )
    # The full occurrence reports remain untouched even when effective rules agree.
    assert (
        previous.prepared.payload()["_policyos_acquisition_history"]
        != (current.prepared.payload()["_policyos_acquisition_history"])
    )


@pytest.mark.parametrize(
    "change",
    [
        {"country_code": "PL"},
        {"year": 2023},
        {"survey_year": 2023},
        {"wave": 2},
        {"condition_json": {"population": "other"}},
    ],
)
def test_real_same_value_changed_source_coordinates_change_semantic_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, object]
) -> None:
    original = native_fixture._fixture
    rows = [{"country_code": "UA", "year": 2024, "distress_score": 0.42}]
    with monkeypatch.context() as scoped:
        scoped.setattr(native_fixture, "_fixture", partial(original, rows=rows, source_rows=rows))
        previous = _case(tmp_path / "previous")
    changed_rows = [{**rows[0], **change}]
    with monkeypatch.context() as scoped:
        scoped.setattr(
            native_fixture,
            "_fixture",
            partial(original, rows=changed_rows, source_rows=changed_rows),
        )
        current = _case(tmp_path / "current")
    before = owner.prepare_acquired_observation_semantic_values(previous.prepared)
    after = owner.prepare_acquired_observation_semantic_values(current.prepared)
    before_row, after_row = before["observation"], after["observation"]
    assert isinstance(before_row, dict) and isinstance(after_row, dict)
    assert before_row["value"] == after_row["value"]
    assert before != after


def test_duplicate_selected_source_multiplicity_is_refused_by_real_canonical_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = native_fixture._fixture
    repeated = [{"country_code": "UA", "year": 2024, "distress_score": 0.42}] * 2
    with monkeypatch.context() as scoped:
        scoped.setattr(
            native_fixture, "_fixture", partial(original, rows=repeated, source_rows=repeated)
        )
        with pytest.raises(ValueError, match="identity_aggregation_not_unique"):
            _case(tmp_path)


def test_rule_projection_refuses_extra_notes_before_excluding_generated_report_field(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    rule = case.prepared.foundry_binding_rule.model_copy(
        update={
            "notes": [*case.prepared.foundry_binding_rule.notes, "pretend_semantic_override"],
        }
    )
    changed = replace(case.prepared, foundry_binding_rule=rule)
    changed = replace(
        changed,
        preparation_sha256=owner._acquisition_preparation_sha256(changed, include_digest=False),
    )
    with pytest.raises(owner.DataStateSubstrateError, match="full_binding_rule_mismatch"):
        owner.acquired_observation_binding_rule_values(changed)


def test_reader_refuses_wrong_or_opaque_selected_snapshot_source(tmp_path: Path) -> None:
    case = _case(tmp_path)
    opaque = case.scenario.store.put_bytes(
        b"opaque source",
        PutOptions(kind="foreign.opaque", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    with pytest.raises((owner.DataStateSubstrateError, ValueError)):
        owner.read_acquired_observation_semantic_values(case.scenario.store, opaque)
    without_profile = case.args["base_data_snapshot_ref"].model_copy(
        update={"manifest_profile_sha256": None}
    )
    with pytest.raises(owner.DataStateSubstrateError, match="profile_unselected"):
        owner.read_acquired_observation_semantic_values(case.scenario.store, without_profile)


def test_public_parser_is_the_actual_data_forge_owner_function() -> None:
    from polisyos.data_forge.domains.catalog.knowledge.overlay import derive_canonical_observations

    assert read_api.catalog.derive_canonical_observations is derive_canonical_observations


def test_unknown_valid_time_survives_actual_acquired_snapshot_writer(tmp_path: Path) -> None:
    from polisyos.fabric.world.store.snapshots import resolve_world_snapshot

    root = owner._write_acquired_candidate_fabric_snapshot(
        workspace_dir=tmp_path,
        snapshot_id="unknown-valid-time",
        payload_hash="sha256:" + "a" * 64,
        transaction_time="2026-10-29T12:00:00+00:00",
        as_of_valid_time=None,
    )
    snapshot = resolve_world_snapshot(root, snapshot_id="unknown-valid-time")
    assert snapshot.as_of_valid_time is None
    assert snapshot.as_of_tx_time == "2026-10-29T12:00:00+00:00"


def test_candidate_world_keeps_unknown_base_valid_time_through_actual_builder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.fabric.world.store.snapshots import resolve_world_snapshot
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry

    case = _case(tmp_path / "source")
    # Reuse this real CAS, not an owner-result substitute, for the base fixture.
    monkeypatch.setattr(world_fixture, "FileSystemCAS", lambda _path: case.scenario.store)
    original_ref = world_fixture._fabric_ref
    monkeypatch.setattr(world_fixture, "_fabric_ref", partial(original_ref, as_of_valid_time=None))
    store, base, _model, _registry = world_fixture._build_record(tmp_path / "base")
    assert base.record.fabric_world_ref.as_of_valid_time is None
    issued = owner.materialize_acquired_observation_snapshot(
        store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    substrate = world_fixture._substrate_registry()
    substrate_ref = persist_substrate_registry(store, substrate)
    built = owner.build_acquired_observation_candidate_world(
        store,
        base_world_model=base.record,
        substrate_registry=substrate,
        substrate_registry_artifact_ref=substrate_ref,
        materialization=issued,
        workspace_dir=tmp_path / "world",
        transaction_time=case.args["transaction_time"],
    )
    assert built.world_model.record.fabric_world_ref.as_of_valid_time is None
    snapshot = resolve_world_snapshot(
        Path(built.world_model.record.fabric_world_ref.snapshot_root),
        snapshot_id=built.world_model.record.fabric_world_ref.snapshot_id,
    )
    assert snapshot.as_of_valid_time is None
    assert snapshot.as_of_tx_time is not None


def test_actual_materializer_consumes_the_shared_semantic_reconciler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path)

    def refuse(_prepared: owner.AcquiredObservationDataPreparation) -> dict[str, object]:
        raise owner.DataStateSubstrateError("test_semantic_reconciler_removed_control")

    monkeypatch.setattr(owner, "prepare_acquired_observation_semantic_values", refuse)
    with pytest.raises(
        owner.DataStateSubstrateError, match="test_semantic_reconciler_removed_control"
    ):
        owner.materialize_acquired_observation_snapshot(
            case.scenario.store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
        )
    assert not case.workspace.exists()


def test_historical_reader_refuses_opaque_bytes_in_the_actual_selected_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.artifacts import ArtifactRef

    case = _case(tmp_path)
    issued = owner.materialize_acquired_observation_snapshot(
        case.scenario.store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    source_id = case.scenario.candidate.statement.source_record_ref.artifact_id
    original = FileSystemCAS.get_bytes

    def corrupted_read(store: FileSystemCAS, selected: object) -> bytes:
        identity = selected.artifact_id if isinstance(selected, ArtifactRef) else selected
        if str(identity) == str(source_id):
            return b"opaque bytes instead of the selected canonical source"
        return original(store, selected)

    # Keep every real persisted blob and receipt; remove only the source read relation.
    assert case.scenario.store.has(source_id)
    monkeypatch.setattr(FileSystemCAS, "get_bytes", corrupted_read)
    with pytest.raises(owner.DataStateSubstrateError):
        owner.read_acquired_observation_semantic_values(
            FileSystemCAS(case.scenario.store.root), issued.data_snapshot_ref
        )


@pytest.mark.parametrize(
    ("field", "changed_value"),
    [
        ("dataset_id", "other-dataset"),
        ("dataset_version", "other-version"),
        ("raw_variable", "other-field"),
        ("country_code", "PL"),
        ("year", 2023),
        ("survey_year", 2023),
        ("wave", 2),
        ("condition_json", '{"population":"other"}'),
        ("acquisition_method", "other-method"),
        ("observation_class", "proxy"),
    ],
)
def test_each_coordinate_is_decisive_even_when_scalar_and_watermark_are_held_fixed(
    tmp_path: Path, field: str, changed_value: object
) -> None:
    """Exercise the shared pure projector, without issuing a counterfactual admission."""
    case = _case(tmp_path)
    selected = case.prepared.observation_projection.observations[0].observation
    changed = type(selected).model_validate(
        {**selected.model_dump(mode="json"), field: changed_value}
    )
    arguments = {
        "slot_binding": case.prepared.selected_profile,
        "projection_row_count": len(case.prepared.observation_projection.observations),
    }
    before = owner._acquired_observation_semantic_values(observation=selected, **arguments)
    after = owner._acquired_observation_semantic_values(observation=changed, **arguments)
    before_row, after_row = before["observation"], after["observation"]
    assert isinstance(before_row, dict) and isinstance(after_row, dict)
    assert before_row["value"] == after_row["value"]
    assert before_row["source_watermark"] == after_row["source_watermark"]
    assert before_row[field] != after_row[field]
    assert before != after
