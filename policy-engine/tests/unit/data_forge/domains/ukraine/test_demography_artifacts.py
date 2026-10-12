from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest

from polisyos.data_forge.domains.ukraine.demography import load_reconciled_targets
from polisyos.data_forge.read_api.ukraine import (
    HistoricalLayoutRequest,
    build_static_aging_state,
    load_demography_artifacts,
)

if TYPE_CHECKING:
    from pathlib import Path


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


def test_historical_omitted_entrant_totals_keep_bounded_legacy_projection(
    tmp_path: Path,
) -> None:
    """The historical adapter preserves shape without promoting the zero to evidence."""
    root = tmp_path / "historical_without_entrants"
    _write_json(
        root / "demography" / "targets.json",
        {
            "state_ids": ["state:a", "state:b"],
            "target_state_totals": [100.0, 250.0],
            "metadata": {"year": 2027},
        },
    )
    _write_json(
        root / "demography" / "transition_priors.json",
        {"transition_prior_matrix": [[0.8, 0.2], [0.1, 0.9]]},
    )

    source = HistoricalLayoutRequest(kind="historical_layout", root=root, layout="new")
    artifacts = load_demography_artifacts(source=source)

    assert np.array_equal(artifacts.entrant_state_totals, np.zeros(2))
    assert artifacts.source_evidence.source_status == "legacy_limited"
    assert artifacts.source_evidence.source_currentness_provenance == "not_established"
    assert artifacts.metadata["entrant_state_totals_compatibility"] == (
        "historical_zero_projection_for_omitted_field"
    )
    assert artifacts.metadata["entrant_state_totals_measurement_status"] == "not_established"
    assert any(
        "not a measured zero" in note
        for note in artifacts.source_evidence.compatibility_notes
    )


def test_historical_present_malformed_entrant_totals_do_not_use_legacy_projection(
    tmp_path: Path,
) -> None:
    """Only an absent legacy field uses the compatibility adapter; malformed supplied data fails."""
    root = tmp_path / "historical_malformed_entrants"
    _write_json(
        root / "demography" / "targets.json",
        {
            "state_ids": ["state:a", "state:b"],
            "target_state_totals": [100.0, 250.0],
            "entrant_state_totals": None,
        },
    )
    _write_json(
        root / "demography" / "transition_priors.json",
        {"transition_prior_matrix": [[0.8, 0.2], [0.1, 0.9]]},
    )

    with pytest.raises(ValueError):
        load_demography_artifacts(
            source=HistoricalLayoutRequest(kind="historical_layout", root=root, layout="new")
        )
