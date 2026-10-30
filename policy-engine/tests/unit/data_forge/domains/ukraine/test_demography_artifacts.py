from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Literal

import numpy as np
import pytest

from polisyos.data_forge.read_api.ukraine import (
    HistoricalLayoutRequest,
    build_static_aging_state,
    load_demography_artifacts,
    load_reconciled_targets,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.domains.ukraine.demography.source_inventory import (
        DemographyRoleProjection,
        ResolvedDemographySource,
    )


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


def test_historical_reader_keeps_captured_member_bytes_after_paths_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resolved historical bundle must retain its values and limited provenance."""
    from polisyos.data_forge.domains.ukraine import demography

    root = tmp_path / "historical_mutation"
    targets = root / "demography" / "targets.json"
    priors = root / "demography" / "transition_priors.json"
    _write_json(
        targets,
        {
            "state_ids": ["state:a", "state:b"],
            "target_state_totals": [10.0, 20.0],
            "entrant_state_totals": [0.0, 0.0],
        },
    )
    _write_json(priors, {"transition_prior_matrix": [[0.8, 0.2], [0.1, 0.9]]})
    identity_input = {
        "layout": "new",
        "members": {
            "targets.json": hashlib.sha256(targets.read_bytes()).hexdigest(),
            "priors.json": hashlib.sha256(priors.read_bytes()).hexdigest(),
        },
    }
    identity_bytes = json.dumps(
        identity_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    expected_identity = f"legacy:{hashlib.sha256(identity_bytes).hexdigest()}"
    real_role_reader = demography.read_demography_role
    changed = False

    def mutate_after_resolution(
        resolved: ResolvedDemographySource,
        role: Literal["targets", "priors", "donor"],
    ) -> DemographyRoleProjection:
        nonlocal changed
        if not changed:
            changed = True
            _write_json(
                targets,
                {
                    "state_ids": ["state:a", "state:b"],
                    "target_state_totals": [90.0, 80.0],
                    "entrant_state_totals": [0.0, 0.0],
                },
            )
            _write_json(priors, {"transition_prior_matrix": [[0.3, 0.7], [0.6, 0.4]]})
        return real_role_reader(resolved, role)

    monkeypatch.setattr(demography, "read_demography_role", mutate_after_resolution)
    request = HistoricalLayoutRequest(kind="historical_layout", root=root, layout="new")
    captured = load_demography_artifacts(source=request)
    monkeypatch.setattr(demography, "read_demography_role", real_role_reader)
    fresh = load_demography_artifacts(source=request)

    assert captured.target_state_totals.tolist() == [10.0, 20.0]
    assert captured.transition_prior_matrix.tolist() == [[0.8, 0.2], [0.1, 0.9]]
    assert captured.source_evidence.source_identity == expected_identity
    assert captured.source_evidence.source_status == "legacy_limited"
    assert captured.source_evidence.member_content_binding_provenance == "not_established"
    assert captured.source_evidence.source_currentness_provenance == "not_established"
    assert fresh.target_state_totals.tolist() == [90.0, 80.0]
    assert fresh.transition_prior_matrix.tolist() == [[0.3, 0.7], [0.6, 0.4]]
    assert fresh.source_evidence.source_identity != expected_identity


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
        "not a measured zero" in note for note in artifacts.source_evidence.compatibility_notes
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
