from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import DataTrust, ValueOuterSet
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.registry import build_default_registry_bundle
from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import StageId
from polisyos.foundry.data_plane.bindings import (
    _auto_rules_from_payload,
    _infer_entity_sizes,
    build_input_bindings,
    load_ukraine_foundry_intake,
)
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY

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


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _write_ukraine_stage(
    root: Path,
    *,
    stage_id: StageId,
    outputs: dict[str, dict[str, object]],
) -> Path:
    stage_dir = root / "stages" / stage_id.value
    stage_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for name, payload in outputs.items():
        path = stage_dir / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        records.append(ArtifactRecord.from_path(path))
    manifest = BuildRunManifest(
        run_id="ukraine-intake-test",
        stage_id=stage_id,
        status="completed",
        started_at="2026-08-26T10:00:00+00:00",
        finished_at="2026-08-26T10:01:00+00:00",
        outputs=records,
    )
    manifest_path = root / "manifests" / f"build_{stage_id.value}.json"
    write_manifest(manifest_path, manifest)
    return manifest_path


def _ukraine_intake_manifests(root: Path) -> dict[str, Path]:
    adjacency = [[0.0, 1.0], [1.0, 0.0]]
    network = {
        "adjacency": adjacency,
        "node_features": [[0.1], [0.2]],
        "node_states": [0.1, 0.2],
        "node_ids": ["a", "b"],
        "metadata": {"producer_stage": "d1"},
    }
    network_causal = {
        "outcome": [1.0, 2.0],
        "treatment": [0, 1],
        "covariates": [[0.1], [0.2]],
        "adjacency_matrix": adjacency,
        "metadata": {"producer_stage": "d1"},
    }
    proxy_bundle = {
        "contract_target": {
            "contract_id": "foundry.causal.proxy_measurement_data.v1",
            "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
        },
        "proxy_channels": [
            {
                "family": "distress_enforcement",
                "proxy_variable": "C_star",
                "latent_variable": "C",
                "treatment_variable": "x",
                "outcome_variable": "y",
                "target_contract": {
                    "contract_id": "foundry.causal.proxy_measurement_data.v1",
                    "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
                },
            }
        ],
        "proxy_map": {"C": "C_star"},
    }
    d1_outputs = {
        "proxy_identification_bundle_v1.json": proxy_bundle,
        "multiplex_network_data.json": {
            "adjacency_layers": [adjacency, adjacency],
            "node_features": [[0.1], [0.2]],
            "node_ids": ["a", "b"],
            "metadata": {"producer_stage": "d1"},
        },
    }
    for layer in ("trade", "distress", "public_service"):
        d1_outputs[f"{layer}_network_data.json"] = network
        d1_outputs[f"{layer}_network_causal_data.json"] = network_causal
    return {
        "d0_p0": _write_ukraine_stage(
            root,
            stage_id=StageId.D0_P0,
            outputs={
                "runtime_bundle_manifest.json": {
                    "data_snapshot_artifact_id": "sha256:" + ("1" * 64),
                }
            },
        ),
        "d1": _write_ukraine_stage(root, stage_id=StageId.D1, outputs=d1_outputs),
        "d2": _write_ukraine_stage(
            root,
            stage_id=StageId.D2,
            outputs={
                "panel_observational_contract.json": {
                    "outcome": [[1.0, 2.0], [2.0, 3.0]],
                    "treatment": [0, 1],
                    "time_treatment": 1,
                    "metadata": {"producer_stage": "d2"},
                },
                "dynamic_treatment_contract.json": {
                    "outcome": list(np.linspace(1.0, 2.0, 10)),
                    "treatment_sequence": [[0, 1]] * 10,
                    "covariate_sequence": [[[0.1], [0.2]]] * 10,
                    "metadata": {"producer_stage": "d2"},
                },
                "microsim_survey_contract_preview.json": {
                    "market_income": [100.0, 200.0],
                    "weights": [1.0, 1.0],
                    "metadata": {"producer_stage": "d2"},
                },
                "survival_contract.json": {
                    "features": [[0.1], [0.2]],
                    "durations": [1.0, 2.0],
                    "events": [0, 1],
                    "metadata": {"producer_stage": "d2"},
                },
                "panel_econometric_contract.json": {
                    "dependent": list(np.linspace(1.0, 8.0, 8)),
                    "exog": [[0.0], [1.0]] * 4,
                    "entity_ids": ["a", "a", "b", "b", "c", "c", "d", "d"],
                    "time_ids": [0, 1] * 4,
                    "metadata": {"producer_stage": "d2"},
                },
            },
        ),
        "d3": _write_ukraine_stage(
            root,
            stage_id=StageId.D3,
            outputs={
                "microsim_survey_contract_v1.json": {
                    "market_income": [100.0, 200.0],
                    "weights": [1.0, 1.0],
                    "metadata": {"producer_stage": "d3"},
                }
            },
        ),
    }


def test_load_ukraine_foundry_intake_content_binds_and_validates_all_method_contracts(
    tmp_path: Path,
) -> None:
    intake = load_ukraine_foundry_intake(
        FileSystemCAS(tmp_path / "cas"),
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
