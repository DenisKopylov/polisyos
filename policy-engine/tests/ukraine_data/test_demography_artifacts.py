from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from polisyos.data_forge.read_api.ukraine import (
    build_static_aging_state,
    load_demography_artifacts,
)
from polisyos.ukraine_data.demography import load_reconciled_targets


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def test_load_demography_artifacts_and_build_static_aging_state(tmp_path: Path) -> None:
    root = tmp_path / "demography_bundle"
    _write_json(
        root / "demography" / "targets.json",
        {
            "state_ids": ["0-17:F:01", "18-64:F:01"],
            "target_state_totals": [100.0, 250.0],
            "entrant_state_totals": [10.0, 0.0],
            "metadata": {"year": 2027},
        },
    )
    _write_json(
        root / "demography" / "transition_priors.json",
        {
            "transition_prior_matrix": [
                [0.8, 0.2],
                [0.1, 0.9],
            ],
            "allowed_transition_mask": [
                [True, True],
                [False, True],
            ],
        },
    )
    _write_json(
        root / "demography" / "donor_pool.json",
        {
            "donor_weights": [0.25, 0.75],
            "donor_state_index": [0, 0],
            "donor_record_index": [1001, 1002],
        },
    )

    artifacts = load_demography_artifacts(root)
    state = build_static_aging_state(
        base_weights=np.array([2.0, 3.0], dtype=float),
        origin_state_index=np.array([0, 1], dtype=int),
        artifacts=artifacts,
        exit_weights=np.array([0.5, 0.0], dtype=float),
        microsim_calibration_report={
            "decision": "pass",
            "can_run_microsim": True,
            "compatibility_status": "compatible",
        },
    )

    assert artifacts.metadata["year"] == 2027
    assert np.allclose(state["target_state_totals"], np.array([100.0, 250.0]))
    assert np.array_equal(state["donor_record_index"], np.array([1001, 1002]))
    assert np.array_equal(state["allowed_transition_mask"], np.array([[True, True], [False, True]]))
    assert np.allclose(state["exit_weights"], np.array([0.5, 0.0]))
    assert state["microsim_calibration_report"]["can_run_microsim"] is True


def test_ukraine_data_shim_reads_reconciled_targets(tmp_path: Path) -> None:
    root = tmp_path / "legacy_shim"
    _write_json(
        root / "demography_targets.json",
        {
            "state_ids": ["male:0-17", "female:0-17"],
            "target_state_totals": [50.0, 45.0],
            "entrant_state_totals": [5.0, 4.0],
        },
    )

    payload = load_reconciled_targets(root)
    assert payload["state_ids"] == ["male:0-17", "female:0-17"]
    assert payload["target_state_totals"] == [50.0, 45.0]
