from __future__ import annotations

import numpy as np

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.data_plane.bindings import (
    _auto_rules_from_payload,
    _infer_entity_sizes,
    build_input_bindings,
)
from polisyos.foundry.executor import load_state_snapshot
from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY


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
    },
}


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
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
    assert np.allclose(
        np.asarray(state.household_cells.poverty_rate),
        np.asarray([0.14, 0.22]),
    )
    assert {
        "auto.cells_population",
        "auto.cells_output",
        "auto.household_cells_disposable_income",
        "auto.household_cells_poverty_rate",
    }.issubset(set(result.applied_binding_ids))
