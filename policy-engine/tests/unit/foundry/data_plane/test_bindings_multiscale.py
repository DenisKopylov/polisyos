from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts.manifest import (
    InputRef,
    SchemaInfo,
    WarningRecord,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts import DataTrust, ValueOuterSet
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    FoundryInputBindingRule,
    FoundryInputBindings,
    StateSnapshot,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.data_forge.read_api import ukraine as ukraine_read_api
from polisyos.foundry.data_plane.bindings import (
    _auto_rules_from_payload,
    _infer_entity_sizes,
    _load_data_snapshot,
    build_input_bindings,
    load_input_bindings,
    load_ukraine_foundry_intake,
)
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY
from tests._helpers.ukraine_foundry_intake import _ukraine_intake_manifests

_HOUSEHOLD_VALUE_OUTER_SET = ValueOuterSet.interval_box(
    coordinates=(
        "household_cells.disposable_income[0]",
        "household_cells.disposable_income[1]",
    ),
    lower=(480.0, 410.0),
    upper=(560.0, 410.0),
    identification_mode="proxy_identified",
    assumptions=("d3_bias_corrected_household_bounds",),
    assumption_status="externally_supported",
    calibration_scope={
        "population": "synthetic_household_cells",
        "regime": "test_regime",
        "measurement": "household_distribution",
    },
    data_trust=DataTrust(
        tier="derived_proxy",
        trust_cap=0.6,
        trust_multiplier=0.6,
        min_coverage=0.35,
        max_coverage=0.85,
        promotion_floor=0.5,
        authority_ref="repo://l5/measurement_registry.json#/trust_tiers/derived_proxy",
    ),
    world_model_record_ref="world_model_record_test",
    epoch="test_regime",
    representation_status="certified",
)

SYNTHETIC_MULTISCALE_PAYLOAD = {
    "agents": {
        "age": [31, 44],
        "skill_level": [1.1, 1.4],
        "income": [1200.0, 1800.0],
        "reported_income": [1000.0, 1600.0],
        "risk_aversion": [0.4, 0.6],
        "is_employed": [True, False],
        "employer_id": [0, -1],
    },
    "firms": {
        "labor_count": [12.0],
        "wage_offer": [35.0],
    },
    "cells": {
        "active": [True, True, False],
        "region_code": [1, 1, 2],
        "sector_id": [10, 11, 12],
        "population": [1000.0, 850.0, 400.0],
        "employment": [600.0, 430.0, 90.0],
        "output": [1500.0, 1800.0, 700.0],
        "distress_score": [0.1, 0.2, 0.5],
        "public_service_index": [0.9, 0.85, 0.7],
    },
    "household_cells": {
        "active": [True, True],
        "cell_id": [0, 1],
        "household_count": [420.0, 310.0],
        "disposable_income": [520.0, 410.0],
        "poverty_rate": [0.14, 0.22],
        "transfer_intensity": [0.28, 0.35],
        "value_outer_set": _HOUSEHOLD_VALUE_OUTER_SET.model_dump(mode="json"),
    },
}


def _put_json(store: FileSystemCAS, payload, *, kind: str, schema: SchemaInfo | None = None):
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json", schema=schema),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def test_load_ukraine_foundry_intake_content_binds_and_validates_all_method_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_verified_stage_artifacts = ukraine_read_api.load_verified_stage_artifacts

    def _admit_then_mutate_sources(*args, **kwargs):
        receipt = load_verified_stage_artifacts(*args, **kwargs)
        for output in receipt.outputs.values():
            Path(output.source_path).write_text('{"mutated": true}', encoding="utf-8")
        return receipt

    monkeypatch.setattr(
        ukraine_read_api,
        "load_verified_stage_artifacts",
        _admit_then_mutate_sources,
    )

    intake_store = FileSystemCAS(tmp_path / "cas")
    intake = load_ukraine_foundry_intake(
        intake_store,
        stage_manifests=_ukraine_intake_manifests(tmp_path),
        allowed_root=tmp_path,
    )

    assert intake.data_snapshot_ref.artifact_id.hex == "1" * 64
    assert set(intake.method_contracts) == {
        "d1_multiplex_network",
        "d1_trade_network",
        "d1_trade_network_causal",
        "d1_distress_network",
        "d1_distress_network_causal",
        "d1_public_service_network",
        "d1_public_service_network_causal",
        "d2_panel_observational",
        "d2_dynamic_treatment",
        "d2_microsim_survey",
        "d2_survival",
        "d2_panel_econometric",
        "d3_microsim_survey",
    }
    receipt = intake.receipt_ref
    assert receipt.kind == "foundry.ukraine_intake_receipt"

    assert set(intake.method_contract_refs) == set(intake.method_contracts)
    assert set(intake.stage_receipt_refs) == {"d0_p0", "d1", "d2", "d3"}
    bundle = from_canonical_bytes(
        intake_store.get_bytes(intake.method_input_bundle_ref.artifact_id)
    )
    assert bundle["authority_purpose"] == "method_input_transport"
    assert bundle["may_not_use_for"] == [
        "governance_admissibility",
        "method_validity",
    ]
    assert set(bundle["contracts"]) == set(intake.method_contracts)
    assert {entry["consumption_state"] for entry in bundle["contracts"].values()} == {
        "exercised_workflow_consumer",
        "selectable_unselected",
    }
    assert (
        sum(
            entry["consumption_state"] == "exercised_workflow_consumer"
            for entry in bundle["contracts"].values()
        )
        == 1
    )
    assert (
        sum(entry["residual_state"] == "consumer_missing" for entry in bundle["contracts"].values())
        == 12
    )
    assert (
        bundle["contracts"]["d2_panel_observational"]["workflow_consumer"]
        == "scientist_causal_full.run_causal_evaluation"
    )

    for contract_key, contract_ref in intake.method_contract_refs.items():
        store_payload = from_canonical_bytes(intake_store.get_bytes(contract_ref.artifact_id))
        assert store_payload
        entry = bundle["contracts"][contract_key]
        assert entry["artifact_ref"]["artifact_id"] == str(contract_ref.artifact_id)
        contract_manifest = intake_store.get_manifest(contract_ref.artifact_id)
        assert {item.role for item in contract_manifest.inputs} == {
            "verified_stage_output",
            "verified_stage_receipt",
        }

    for stage_id, stage_receipt_ref in intake.stage_receipt_refs.items():
        stage_manifest = intake_store.get_manifest(stage_receipt_ref.artifact_id)
        roles = {item.role for item in stage_manifest.inputs}
        assert "verified_stage_manifest" in roles
        assert any(role.startswith("verified_stage_output:") for role in roles), stage_id


def test_load_ukraine_foundry_intake_preserves_the_selected_snapshot_profile(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "profiled-cas")
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    raw_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=payload_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected_snapshot_ref = DataSnapshotRef.model_validate(
        raw_snapshot_ref.model_dump(mode="python")
    )
    stage_root = tmp_path / "stages"
    intake = load_ukraine_foundry_intake(
        store,
        stage_manifests=_ukraine_intake_manifests(
            stage_root,
            data_snapshot_ref=selected_snapshot_ref,
        ),
        allowed_root=stage_root,
    )

    assert selected_snapshot_ref.manifest_profile_sha256 is not None
    assert intake.data_snapshot_ref == selected_snapshot_ref
    receipt = from_canonical_bytes(store.get_bytes(intake.receipt_ref))
    assert receipt["data_snapshot_ref"] == selected_snapshot_ref.model_dump(mode="json")
    receipt_manifest = store.get_manifest(intake.receipt_ref)
    snapshot_edges = [edge for edge in receipt_manifest.inputs if edge.role == "data_snapshot"]
    assert len(snapshot_edges) == 1
    assert snapshot_edges[0].artifact_id == selected_snapshot_ref.artifact_id
    assert (
        snapshot_edges[0].manifest_profile_sha256 == selected_snapshot_ref.manifest_profile_sha256
    )


def test_load_ukraine_foundry_intake_rejects_same_bytes_with_false_snapshot_schema(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "schema-alias-cas")
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    valid_ref = store.put_json(
        DataSnapshot(data_ref=payload_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    valid_manifest = store.get_manifest(valid_ref)
    alias_schema = SchemaInfo(
        name=f"alias.{DataSnapshot.ARTIFACT_SCHEMA_NAME}",
        version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
    )
    alias_ref = store.put_bytes(
        store.get_bytes(valid_ref),
        PutOptions(
            kind=valid_manifest.kind,
            media_type=valid_manifest.media_type,
            schema=alias_schema,
            inputs=valid_manifest.inputs,
            canon=valid_manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert alias_ref.artifact_id == valid_ref.artifact_id
    assert alias_ref.manifest_profile_sha256 != valid_ref.manifest_profile_sha256
    assert store.verify(alias_ref).ok
    alias_manifest = store.get_manifest(alias_ref)
    assert alias_manifest.kind == valid_manifest.kind
    assert alias_manifest.media_type == valid_manifest.media_type
    assert alias_manifest.artifact_schema == alias_schema
    assert alias_manifest.inputs == valid_manifest.inputs
    assert store.get_bytes(alias_ref) == store.get_bytes(valid_ref)

    stage_root = tmp_path / "stages"
    runtime_bundle_payload = {
        "data_snapshot_artifact_id": str(alias_ref.artifact_id),
        "data_snapshot_ref": alias_ref.model_dump(mode="json"),
    }
    with pytest.raises(ValueError, match="schema"):
        load_ukraine_foundry_intake(
            store,
            stage_manifests=_ukraine_intake_manifests(
                stage_root,
                runtime_bundle_payload=runtime_bundle_payload,
            ),
            allowed_root=stage_root,
        )


def test_load_ukraine_foundry_intake_keeps_profileless_legacy_snapshot_unqualified(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "legacy-cas")
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    raw_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=payload_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    legacy_snapshot_ref = DataSnapshotRef.model_validate(raw_snapshot_ref.model_dump(mode="python"))
    assert legacy_snapshot_ref.manifest_profile_sha256 is None
    stage_root = tmp_path / "stages"
    intake = load_ukraine_foundry_intake(
        store,
        stage_manifests=_ukraine_intake_manifests(
            stage_root,
            data_snapshot_ref=legacy_snapshot_ref,
        ),
        allowed_root=stage_root,
    )

    assert intake.data_snapshot_ref == legacy_snapshot_ref
    assert intake.data_snapshot_ref.manifest_profile_sha256 is None

    binding = build_input_bindings(
        store,
        data_snapshot_ref=intake.data_snapshot_ref,
        registry_bundle_ref=build_default_registry_bundle(store).bundle_ref,
    )
    persisted = load_input_bindings(store, binding.input_bindings_ref)
    assert persisted.data_snapshot_ref.manifest_profile_sha256 is None
    binding_edges = store.get_manifest(binding.input_bindings_ref).inputs
    snapshot_edge = next(edge for edge in binding_edges if edge.role == "input.data_snapshot_ref")
    assert snapshot_edge.manifest_profile_sha256 is None


def test_load_ukraine_foundry_intake_rejects_a_foreign_typed_snapshot_ref(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "foreign-cas")
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    first_raw_ref = store.put_json(
        DataSnapshot(data_ref=payload_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    foreign_payload_ref = _put_json(
        store,
        {"agents": {"age": [22]}},
        kind="fabric.synthetic_multiscale_payload",
    )
    foreign_raw_ref = store.put_json(
        DataSnapshot(data_ref=foreign_payload_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    first_ref = DataSnapshotRef.model_validate(first_raw_ref.model_dump(mode="python"))
    foreign_ref = DataSnapshotRef.model_validate(foreign_raw_ref.model_dump(mode="python"))
    runtime_bundle_payload = {
        "data_snapshot_artifact_id": str(first_ref.artifact_id),
        "data_snapshot_ref": foreign_ref.model_dump(mode="json"),
    }
    stage_root = tmp_path / "stages"
    with pytest.raises(ValueError, match="does not match its artifact ID"):
        load_ukraine_foundry_intake(
            store,
            stage_manifests=_ukraine_intake_manifests(
                stage_root,
                runtime_bundle_payload=runtime_bundle_payload,
            ),
            allowed_root=stage_root,
        )


def test_load_ukraine_foundry_intake_preserves_but_binding_rejects_a_foreign_profile(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "foreign-profile-cas")
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    selected_raw_ref = store.put_json(
        DataSnapshot(data_ref=payload_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    foreign_payload_ref = _put_json(
        store,
        {"agents": {"age": [22]}},
        kind="fabric.synthetic_multiscale_payload",
    )
    foreign_raw_ref = store.put_json(
        DataSnapshot(data_ref=foreign_payload_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected_ref = DataSnapshotRef.model_validate(selected_raw_ref.model_dump(mode="python"))
    foreign_ref = DataSnapshotRef.model_validate(foreign_raw_ref.model_dump(mode="python"))
    foreign_profile_ref = DataSnapshotRef.model_validate(
        selected_ref.model_dump(mode="python")
        | {"manifest_profile_sha256": foreign_ref.manifest_profile_sha256}
    )
    assert foreign_profile_ref.artifact_id == selected_ref.artifact_id
    assert foreign_profile_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
    runtime_bundle_payload = {
        "data_snapshot_artifact_id": str(selected_ref.artifact_id),
        "data_snapshot_ref": foreign_profile_ref.model_dump(mode="json"),
    }
    stage_root = tmp_path / "stages"
    with pytest.raises((FileNotFoundError, ValueError), match="profile|manifest"):
        load_ukraine_foundry_intake(
            store,
            stage_manifests=_ukraine_intake_manifests(
                stage_root,
                runtime_bundle_payload=runtime_bundle_payload,
            ),
            allowed_root=stage_root,
        )


def test_load_ukraine_foundry_intake_fails_closed_on_one_corrupted_method_artifact(
    tmp_path: Path,
) -> None:
    manifests = _ukraine_intake_manifests(tmp_path)
    corrupted = tmp_path / "stages" / "d2" / "survival_contract.json"
    corrupted.write_text('{"features": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="content hash mismatch"):
        load_ukraine_foundry_intake(
            FileSystemCAS(tmp_path / "cas"),
            stage_manifests=manifests,
            allowed_root=tmp_path,
        )


def test_infer_entity_sizes_detects_cells_and_household_cells() -> None:
    rules = _auto_rules_from_payload(
        slot_registry=DEFAULT_SLOT_REGISTRY,
        payload=SYNTHETIC_MULTISCALE_PAYLOAD,
    )

    sizes = _infer_entity_sizes(
        payload=SYNTHETIC_MULTISCALE_PAYLOAD,
        rules=rules,
        slot_registry=DEFAULT_SLOT_REGISTRY,
    )

    assert sizes == (2, 1, 3, 2)


def test_auto_rules_discover_cell_level_slots() -> None:
    rules = _auto_rules_from_payload(
        slot_registry=DEFAULT_SLOT_REGISTRY,
        payload=SYNTHETIC_MULTISCALE_PAYLOAD,
    )
    target_slot_ids = {rule.target_slot_id for rule in rules}

    assert "cells.population" in target_slot_ids
    assert "cells.output" in target_slot_ids
    assert "household_cells.disposable_income" in target_slot_ids
    assert "household_cells.value_outer_set" in target_slot_ids
    assert "household_cells.disposable_income_lower" not in target_slot_ids
    assert "household_cells.disposable_income_upper" not in target_slot_ids
    assert "household_cells.identification_mode_code" not in target_slot_ids
    assert "household_cells.poverty_rate" in target_slot_ids


def test_build_input_bindings_materializes_multiscale_state(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=payload_ref),
        kind="fabric.data_snapshot",
    )
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref

    result = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=None,
    )
    state = load_state_snapshot(store, snapshot_ref=result.bound_state_snapshot_ref)

    assert state.cells is not None
    assert state.household_cells is not None
    assert state.agents.size == 2
    assert state.firms.size == 1
    assert state.cells.size == 3
    assert state.household_cells.size == 2

    assert np.allclose(np.asarray(state.cells.population), np.asarray([1000.0, 850.0, 400.0]))
    assert np.allclose(np.asarray(state.cells.output), np.asarray([1500.0, 1800.0, 700.0]))
    assert np.allclose(
        np.asarray(state.household_cells.disposable_income),
        np.asarray([520.0, 410.0]),
    )
    assert state.household_cells.value_outer_set == _HOUSEHOLD_VALUE_OUTER_SET
    assert state.household_cells.value_outer_set.width == (80.0, 0.0)
    assert np.allclose(
        np.asarray(state.household_cells.poverty_rate),
        np.asarray([0.14, 0.22]),
    )
    assert {
        "auto.cells_population",
        "auto.cells_output",
        "auto.household_cells_disposable_income",
        "auto.household_cells_value_outer_set",
        "auto.household_cells_poverty_rate",
    }.issubset(set(result.applied_binding_ids))


def test_build_input_bindings_preserves_selected_inner_state_blob_view(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A v2.2 selected state-blob view is valid inside a default snapshot wrapper."""
    import polisyos.foundry.data_plane.bindings as bindings_module

    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=payload_ref),
        kind="fabric.data_snapshot",
    )
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref
    original_put_state_snapshot = bindings_module.put_state_snapshot
    selected_blob_refs = []

    def _put_snapshot_with_selected_inner_blob(*args, **kwargs):
        default_wrapper_ref = original_put_state_snapshot(*args, **kwargs)
        wrapper_bytes = store.get_bytes(default_wrapper_ref)
        snapshot = StateSnapshot.model_validate_json(wrapper_bytes)
        default_blob_ref = snapshot.state_ref
        blob_bytes = store.get_bytes(default_blob_ref)
        selected_blob_ref = store.put_bytes(
            blob_bytes,
            PutOptions(
                kind=default_blob_ref.kind,
                media_type=default_blob_ref.media_type,
                inputs=[
                    InputRef(
                        artifact_id=data_snapshot_ref.artifact_id,
                        role="fixture.selected_state_blob_view",
                    )
                ],
            ),
        )
        assert selected_blob_ref.manifest_profile_sha256 is not None
        selected_blob_refs.append(selected_blob_ref)
        lineage_inputs = list(snapshot.lineage_inputs or [])
        lineage_inputs[-1] = input_ref_from_artifact_ref(
            selected_blob_ref,
            role="state_blob",
        )
        selected_snapshot = snapshot.model_copy(
            update={
                "state_ref": selected_blob_ref,
                "lineage_inputs": lineage_inputs,
            }
        )
        return store.put_json(
            selected_snapshot,
            PutOptions(
                kind=default_wrapper_ref.kind,
                media_type=default_wrapper_ref.media_type,
                schema=SchemaInfo(
                    name="polisyos.core.StateSnapshot",
                    version="2.2.0",
                ),
                inputs=lineage_inputs,
            ),
        )

    monkeypatch.setattr(
        bindings_module,
        "put_state_snapshot",
        _put_snapshot_with_selected_inner_blob,
    )

    result = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=None,
    )
    persisted_snapshot = StateSnapshot.model_validate_json(
        store.get_bytes(result.bound_state_snapshot_ref.artifact_id)
    )
    state = load_state_snapshot(store, snapshot_ref=result.bound_state_snapshot_ref)

    assert selected_blob_refs
    assert persisted_snapshot.state_ref.manifest_profile_sha256 is not None
    assert result.bound_state_snapshot_ref.manifest_profile_sha256 is None
    assert state.cells is not None
    assert np.allclose(np.asarray(state.cells.population), np.asarray([1000.0, 850.0, 400.0]))


def test_build_input_bindings_preserves_selected_snapshot_wrapper_view(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidate bindings retain a selected wrapper for the WMR owner to admit."""
    import polisyos.foundry.data_plane.bindings as bindings_module
    from polisyos.foundry.data_plane.bindings import load_input_bindings

    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=payload_ref),
        kind="fabric.data_snapshot",
    )
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref
    original_put_state_snapshot = bindings_module.put_state_snapshot
    selected_wrapper_refs = []

    def _put_snapshot_with_selected_wrapper(*args, **kwargs):
        default_wrapper_ref = original_put_state_snapshot(*args, **kwargs)
        wrapper_bytes = store.get_bytes(default_wrapper_ref)
        manifest = store.get_manifest(default_wrapper_ref)
        selected_wrapper_ref = store.put_bytes(
            wrapper_bytes,
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                inputs=manifest.inputs,
                warnings=[
                    WarningRecord(
                        code="fixture.selected_manifest_view",
                        msg="The wrapper has an alternate typed manifest view.",
                    )
                ],
            ),
        )
        assert selected_wrapper_ref.manifest_profile_sha256 is not None
        selected_wrapper_refs.append(selected_wrapper_ref)
        return selected_wrapper_ref

    monkeypatch.setattr(
        bindings_module,
        "put_state_snapshot",
        _put_snapshot_with_selected_wrapper,
    )

    result = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=None,
    )
    bindings = load_input_bindings(store, result.input_bindings_ref)
    state = load_state_snapshot(store, snapshot_ref=result.bound_state_snapshot_ref)

    assert selected_wrapper_refs
    assert result.bound_state_snapshot_ref.manifest_profile_sha256 == (
        selected_wrapper_refs[0].manifest_profile_sha256
    )
    assert bindings.bound_state_snapshot_ref.manifest_profile_sha256 == (
        selected_wrapper_refs[0].manifest_profile_sha256
    )
    assert store.get_manifest(result.input_bindings_ref).inputs[-1].manifest_profile_sha256 == (
        selected_wrapper_refs[0].manifest_profile_sha256
    )
    assert state.cells is not None
    assert np.allclose(np.asarray(state.cells.population), np.asarray([1000.0, 850.0, 400.0]))


def _put_arrow_payload(store: FileSystemCAS):
    """Persist a real Arrow IPC stream with nested Foundry source paths."""
    pa = pytest.importorskip("pyarrow")
    agents = pa.array(
        [{"income": 1200.0}, {"income": 1800.0}],
        type=pa.struct([("income", pa.float64())]),
    )
    cells = pa.array(
        [{"population": 1000.0}, {"population": 850.0}],
        type=pa.struct([("population", pa.float64())]),
    )
    table = pa.Table.from_arrays([agents, cells], names=["agents", "cells"])
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return store.put_bytes(
        sink.getvalue().to_pybytes(),
        PutOptions(
            kind="fabric.data_payload",
            media_type="application/vnd.apache.arrow.stream",
        ),
    )


def _arrow_binding_rules() -> list[FoundryInputBindingRule]:
    return [
        FoundryInputBindingRule(
            binding_id="arrow.agents_income",
            source_path="agents.income",
            target_slot_id="agents.income",
        ),
        FoundryInputBindingRule(
            binding_id="arrow.cells_population",
            source_path="cells.population",
            target_slot_id="cells.population",
        ),
    ]


def _assert_no_binding_outputs_written(
    store: FileSystemCAS,
    monkeypatch: pytest.MonkeyPatch,
    invoke,
) -> None:
    """Reject any state/binding/report CAS write while input admission fails."""
    import polisyos.foundry.data_plane.bindings as bindings_module

    class UnexpectedBindingOutputWriteError(RuntimeError):
        """Identify a forbidden output write in a negative input test."""

    def _fail_state_write(*args, **kwargs):
        del args, kwargs
        raise UnexpectedBindingOutputWriteError("state snapshot written before input rejection")

    monkeypatch.setattr(bindings_module, "put_state_snapshot", _fail_state_write)
    original_put_json = store.put_json
    original_put_bytes = store.put_bytes

    def _fail_report_write(obj, opts, *args, **kwargs):
        if opts.kind in {
            "foundry.input_bindings",
            "foundry.input_binding_report",
        }:
            raise UnexpectedBindingOutputWriteError(
                f"binding output '{opts.kind}' written before input rejection"
            )
        return original_put_json(obj, opts, *args, **kwargs)

    def _fail_direct_output_write(data, opts, *args, **kwargs):
        if opts.kind in {
            "foundry.state_blob",
            "foundry.state_snapshot",
            "foundry.input_bindings",
            "foundry.input_binding_report",
        }:
            raise UnexpectedBindingOutputWriteError(
                f"direct output '{opts.kind}' written before input rejection"
            )
        return original_put_bytes(data, opts, *args, **kwargs)

    monkeypatch.setattr(store, "put_json", _fail_report_write)
    monkeypatch.setattr(store, "put_bytes", _fail_direct_output_write)
    invoke()


def test_build_input_bindings_consumes_arrow_snapshot_and_materializes_state(tmp_path) -> None:
    """Arrow IPC input must bind real values through the existing Foundry rule path."""
    store = FileSystemCAS(tmp_path / "cas")
    arrow_ref = _put_arrow_payload(store)
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=arrow_ref),
        kind="fabric.data_snapshot",
    )
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref

    result = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=_arrow_binding_rules(),
    )
    state = load_state_snapshot(store, snapshot_ref=result.bound_state_snapshot_ref)

    assert np.allclose(np.asarray(state.agents.income), np.asarray([1200.0, 1800.0]))
    assert np.allclose(np.asarray(state.cells.population), np.asarray([1000.0, 850.0]))
    assert result.applied_binding_ids == (
        "arrow.agents_income",
        "arrow.cells_population",
    )


def test_build_input_bindings_rejects_corrupt_arrow_before_output_cas_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corrupt Arrow bytes are rejected before state or binding reports are persisted."""
    pytest.importorskip("pyarrow")
    store = FileSystemCAS(tmp_path / "cas")
    corrupt_ref = store.put_bytes(
        b"not-an-arrow-ipc-stream",
        PutOptions(
            kind="fabric.data_payload",
            media_type="application/vnd.apache.arrow.stream",
        ),
    )
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=corrupt_ref),
        kind="fabric.data_snapshot",
    )
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref

    with pytest.raises(ValueError, match="Arrow IPC"):
        _assert_no_binding_outputs_written(
            store,
            monkeypatch,
            lambda: build_input_bindings(
                store,
                data_snapshot_ref=data_snapshot_ref,
                registry_bundle_ref=registry_bundle_ref,
                rules=_arrow_binding_rules(),
            ),
        )


def test_build_input_bindings_rejects_snapshot_media_mismatch_before_output_cas_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A snapshot ref must agree with its CAS manifest before binding can write outputs."""
    store = FileSystemCAS(tmp_path / "cas")
    arrow_ref = _put_arrow_payload(store)
    mismatched_ref = arrow_ref.model_copy(update={"media_type": "application/json"})
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=mismatched_ref),
        kind="fabric.data_snapshot",
    )
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref

    with pytest.raises(ValueError, match="media type"):
        _assert_no_binding_outputs_written(
            store,
            monkeypatch,
            lambda: build_input_bindings(
                store,
                data_snapshot_ref=data_snapshot_ref,
                registry_bundle_ref=registry_bundle_ref,
                rules=_arrow_binding_rules(),
            ),
        )


def test_build_input_bindings_rejects_json_manifest_when_snapshot_ref_claims_arrow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A JSON CAS manifest cannot be consumed through an Arrow-typed snapshot ref."""
    store = FileSystemCAS(tmp_path / "cas")
    json_payload_ref = _put_json(
        store,
        {"agents": {"income": [1200.0, 1800.0]}},
        kind="fabric.data_payload",
    )
    mismatched_ref = json_payload_ref.model_copy(
        update={"media_type": "application/vnd.apache.arrow.stream"}
    )
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=mismatched_ref),
        kind="fabric.data_snapshot",
    )
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref

    with pytest.raises(ValueError, match="media type"):
        _assert_no_binding_outputs_written(
            store,
            monkeypatch,
            lambda: build_input_bindings(
                store,
                data_snapshot_ref=data_snapshot_ref,
                registry_bundle_ref=registry_bundle_ref,
                rules=_arrow_binding_rules(),
            ),
        )


def test_build_input_bindings_preserves_selected_data_and_registry_views(
    tmp_path: Path,
) -> None:
    """Data and registry selectors survive binding payload, report, and lineage."""
    from polisyos.foundry.data_plane.bindings import load_input_bindings

    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=payload_ref),
        kind="fabric.data_snapshot",
        schema=SchemaInfo(
            name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
            version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
        ),
    )
    registry_bundle_ref = build_default_registry_bundle(store).bundle_ref

    def _selected_view(ref, *, warning_code: str):
        manifest = store.get_manifest(ref)
        return store.put_bytes(
            store.get_bytes(ref),
            PutOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema,
                inputs=manifest.inputs,
                warnings=[
                    WarningRecord(
                        code=warning_code,
                        msg="The fixture selects an alternate manifest profile.",
                    )
                ],
            ),
        )

    selected_data_snapshot_ref = _selected_view(
        data_snapshot_ref,
        warning_code="fixture.selected_data_snapshot_view",
    )
    selected_registry_bundle_ref = _selected_view(
        registry_bundle_ref,
        warning_code="fixture.selected_registry_bundle_view",
    )
    assert selected_data_snapshot_ref.manifest_profile_sha256 is not None
    assert selected_registry_bundle_ref.manifest_profile_sha256 is not None

    built = build_input_bindings(
        store,
        data_snapshot_ref=selected_data_snapshot_ref,
        registry_bundle_ref=selected_registry_bundle_ref,
    )
    persisted = load_input_bindings(store, built.input_bindings_ref)
    report = json.loads(store.get_bytes(built.input_binding_report_ref))

    assert persisted.data_snapshot_ref.manifest_profile_sha256 == (
        selected_data_snapshot_ref.manifest_profile_sha256
    )
    assert persisted.registry_bundle_ref.manifest_profile_sha256 == (
        selected_registry_bundle_ref.manifest_profile_sha256
    )
    binding_manifest_inputs = store.get_manifest(built.input_bindings_ref).inputs
    assert any(
        ref.role == "input.data_snapshot_ref"
        and ref.manifest_profile_sha256 == selected_data_snapshot_ref.manifest_profile_sha256
        for ref in binding_manifest_inputs
    )
    assert any(
        ref.role == "input.registry_bundle_ref"
        and ref.manifest_profile_sha256 == selected_registry_bundle_ref.manifest_profile_sha256
        for ref in binding_manifest_inputs
    )
    assert report["schema_version"] == "1.1"
    assert report["data_snapshot_ref"]["manifest_profile_sha256"] == (
        selected_data_snapshot_ref.manifest_profile_sha256
    )
    assert report["registry_bundle_ref"]["manifest_profile_sha256"] == (
        selected_registry_bundle_ref.manifest_profile_sha256
    )


def test_load_input_bindings_rejects_payload_version_drift(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    dependency_ref = _put_json(store, {}, kind="test.dependency")
    bindings = FoundryInputBindings(
        data_snapshot_ref=dependency_ref,
        registry_bundle_ref=dependency_ref,
        bound_state_snapshot_ref=StateSnapshotRef(
            artifact_id=dependency_ref.artifact_id,
        ),
    )
    payload = bindings.model_dump(mode="json")
    payload["schema_version"] = "1.1"
    ref = store.put_json(
        payload,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                version=FoundryInputBindings.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_typed_artifact_schema_version_mismatch",
    ):
        load_input_bindings(store, ref)


def test_load_data_snapshot_checks_owner_schema_for_profileless_refs(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = _put_json(store, SYNTHETIC_MULTISCALE_PAYLOAD, kind="test.payload")
    current_ref = _put_json(
        store,
        DataSnapshot(data_ref=payload_ref),
        kind=DataSnapshot.ARTIFACT_KIND,
        schema=SchemaInfo(
            name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
            version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
        ),
    )
    unsupported_ref = _put_json(
        store,
        DataSnapshot(data_ref=payload_ref, notes=["unsupported-schema-profileless-case"]),
        kind=DataSnapshot.ARTIFACT_KIND,
        schema=SchemaInfo(name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version="9.0"),
    )
    assert current_ref.manifest_profile_sha256 is None
    assert isinstance(_load_data_snapshot(store, current_ref), DataSnapshot)

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_typed_artifact_schema_version_unsupported",
    ):
        _load_data_snapshot(store, unsupported_ref)
