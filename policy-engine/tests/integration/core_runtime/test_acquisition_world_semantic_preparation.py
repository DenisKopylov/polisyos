"""Real-owner witnesses for write-free world preparation and immutable source replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.foundry.data_plane import prepare_json_input_binding_values
from polisyos.runtime.quality import data_state_substrate as owner
from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
from polisyos.runtime.quality.world_model_record import world_model_artifact_views
from tests._helpers import world_model_record as world_fixture
from tests.integration.core_runtime.test_acquisition_data_preparation import _observe_store_writes
from tests.integration.core_runtime.test_acquisition_observation_semantics import _case


def test_historical_source_preparation_replays_without_current_overlay_or_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path)
    expected = case.prepared
    writes = _observe_store_writes(monkeypatch)

    def no_current_owner(**_kwargs: object) -> None:
        raise AssertionError("historical replay requested a current native permit")

    monkeypatch.setattr(
        case.scenario.overlay, "read_activated_semantic_epoch_observations", no_current_owner
    )
    observed = owner.replay_acquired_observation_snapshot_preparation(
        FileSystemCAS(case.scenario.store.root),
        base_data_snapshot_ref=expected.base_data_snapshot_ref,
        receipt_ref=expected.receipt_ref,
        passport_ref=expected.observation_projection.passport_ref,
        boundary_candidate_ref=case.scenario.candidate.candidate_ref,
        source_ref=case.scenario.candidate.statement.source_record_ref,
        observation_id=expected.selected_observation_id,
        slot_binding=expected.selected_profile,
        transaction_time=case.args["transaction_time"],
    )
    assert observed == expected
    assert writes == []
    assert not case.workspace.exists()


def test_historical_source_replay_requires_exact_boundary_source_join(tmp_path: Path) -> None:
    case = _case(tmp_path)
    prepared = case.prepared
    wrong = case.scenario.candidate.statement.source_record_ref.model_copy(
        update={"kind": "foreign.opaque"}
    )
    with pytest.raises(owner.DataStateSubstrateError, match="source_binding_mismatch"):
        owner.replay_acquired_observation_snapshot_preparation(
            case.scenario.store,
            base_data_snapshot_ref=prepared.base_data_snapshot_ref,
            receipt_ref=prepared.receipt_ref,
            passport_ref=prepared.observation_projection.passport_ref,
            boundary_candidate_ref=case.scenario.candidate.candidate_ref,
            source_ref=wrong,
            observation_id=prepared.selected_observation_id,
            slot_binding=prepared.selected_profile,
            transaction_time=case.args["transaction_time"],
        )


def _world_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    case = _case(tmp_path / "source")
    monkeypatch.setattr(world_fixture, "FileSystemCAS", lambda _path: case.scenario.store)
    store, base, _model, _registry = world_fixture._build_record(tmp_path / "base")
    substrate = world_fixture._substrate_registry()
    views = world_model_artifact_views(base.record)
    plan = owner._prepare_acquired_observation_world(
        store,
        base_world_model_record=base.record,
        acquired_rule=case.prepared.foundry_binding_rule,
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=substrate,
    )
    numerical = prepare_json_input_binding_values(
        store,
        payload_json=case.prepared.payload_json,
        registry_bundle_ref=views.registry_bundle_ref,
        rules=list(plan.rules),
    )
    return case, base, substrate, views, numerical


def test_prospective_world_values_write_nothing_and_match_the_actual_produced_world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, base, substrate, views, numerical = _world_case(tmp_path, monkeypatch)
    writes = _observe_store_writes(monkeypatch)
    before = owner.prepare_acquired_observation_world_semantic_values(
        store=case.scenario.store,
        base_world_model_record=base.record,
        data_preparation=case.prepared,
        prepared_state_values=numerical,
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=substrate,
    )
    assert before["status"] == "established", before
    assert before["predicate_provenance"] == "recomputed"
    assert writes == []
    materialized = owner.materialize_acquired_observation_snapshot(
        case.scenario.store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    substrate_ref = persist_substrate_registry(case.scenario.store, substrate)
    actual = owner.build_acquired_observation_candidate_world(
        case.scenario.store,
        base_world_model=base.record,
        substrate_registry=substrate,
        substrate_registry_artifact_ref=substrate_ref,
        materialization=materialized,
        workspace_dir=tmp_path / "world",
        transaction_time=case.args["transaction_time"],
    )
    after = owner.read_acquired_observation_world_semantic_values(
        store=FileSystemCAS(case.scenario.store.root),
        world_model_record=actual.world_model.record,
        registry_bundle_ref=views.registry_bundle_ref,
    )
    assert after["status"] == "established", after
    assert before["effective_values"] == after["effective_values"]
    # Keep every CAS ref and producer marker, but falsify the actual quality output.
    binding_path = Path(actual.world_model.record.data_forge_binding_ref.binding_path)
    original = binding_path.read_bytes()
    altered = json.loads(original)
    altered["bindings"][0]["quality_gates"][0]["status"] = "fail"
    try:
        binding_path.write_text(json.dumps(altered), encoding="utf-8")
        refused = owner.read_acquired_observation_world_semantic_values(
            store=case.scenario.store,
            world_model_record=actual.world_model.record,
            registry_bundle_ref=views.registry_bundle_ref,
        )
        assert refused["status"] == "not_established"
    finally:
        binding_path.write_bytes(original)


def test_supplied_state_plan_cannot_self_attest_completeness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, base, substrate, views, _numerical = _world_case(tmp_path, monkeypatch)
    result = owner.prepare_acquired_observation_world_semantic_values(
        store=case.scenario.store,
        base_world_model_record=base.record,
        data_preparation=case.prepared,
        prepared_state_values={"complete": True},
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=substrate,
    )
    assert result["status"] == "not_established"
    assert result["reason_codes"]
