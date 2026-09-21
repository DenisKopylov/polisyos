"""Test-first LA-032 witnesses for one-layout demographic snapshots."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from polisyos.data_forge.domains.ukraine.demography import (
    load_demography_artifacts,
)
from polisyos.data_forge.read_api.ukraine import (
    build_static_aging_state,
    load_demography_artifacts as load_demography_from_read_api,
    load_reconciled_targets as load_targets_from_read_api,
)


_LAYOUT_PATHS = {
    "new": {
        "targets": "demography/targets.json",
        "priors": "demography/transition_priors.json",
        "donor": "demography/donor_pool.json",
    },
    "legacy": {
        "targets": "demography_targets.json",
        "priors": "demography_transition_priors.json",
        "donor": "demography_donor_pool.json",
    },
}


def _path(root: Path, layout: str, artifact: str) -> Path:
    """Return one declared artifact path for a supported layout."""
    return root / _LAYOUT_PATHS[layout][artifact]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write a small fixture member without introducing a persisted manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _targets(
    snapshot: str,
    *,
    totals: tuple[float, float] = (100.0, 250.0),
) -> dict[str, object]:
    """Return the target member for a deliberately named snapshot."""
    return {
        "state_ids": ["0-17:F:TEST", "18-64:F:TEST"],
        "target_state_totals": list(totals),
        "entrant_state_totals": [10.0, 2.0],
        "metadata": {"snapshot": snapshot, "year": 2027},
    }


def _priors(*, scale: float = 1.0) -> dict[str, object]:
    """Return a shape-compatible prior member with an inspectable value."""
    return {
        "transition_prior_matrix": [
            [0.8 * scale, 0.2 * scale],
            [0.1 * scale, 0.9 * scale],
        ],
        "allowed_transition_mask": [[True, True], [False, True]],
    }


def _donor() -> dict[str, object]:
    """Return the optional donor member."""
    return {
        "donor_weights": [0.25, 0.75],
        "donor_state_index": [0, 1],
        "donor_record_index": [1001, 1002],
    }


def _write_layout(
    root: Path,
    layout: str,
    *,
    snapshot: str,
    include_donor: bool = True,
    totals: tuple[float, float] = (100.0, 250.0),
    prior_scale: float = 1.0,
) -> None:
    """Write one complete old or new layout, with no cross-layout members."""
    _write_json(_path(root, layout, "targets"), _targets(snapshot, totals=totals))
    _write_json(_path(root, layout, "priors"), _priors(scale=prior_scale))
    if include_donor:
        _write_json(_path(root, layout, "donor"), _donor())


def test_clean_new_layout_is_selected_as_one_snapshot(tmp_path: Path) -> None:
    """A complete hierarchical layout preserves its declared snapshot metadata."""
    root = tmp_path / "new"
    _write_layout(root, "new", snapshot="new-2027")

    artifacts = load_demography_artifacts(root)

    assert artifacts.metadata["snapshot"] == "new-2027"
    assert np.array_equal(artifacts.target_state_totals, np.array([100.0, 250.0]))
    assert np.array_equal(artifacts.donor_record_index, np.array([1001, 1002]))


def test_clean_legacy_layout_remains_readable_as_one_snapshot(tmp_path: Path) -> None:
    """A complete flat layout remains an explicitly supported historical reader."""
    root = tmp_path / "legacy"
    _write_layout(root, "legacy", snapshot="legacy-2027", totals=(80.0, 220.0))

    artifacts = load_demography_artifacts(root)
    targets = load_targets_from_read_api(root)

    assert artifacts.metadata["snapshot"] == "legacy-2027"
    assert np.array_equal(artifacts.target_state_totals, np.array([80.0, 220.0]))
    assert targets["target_state_totals"] == [80.0, 220.0]


def test_two_complete_layouts_require_explicit_snapshot_selection(tmp_path: Path) -> None:
    """Coexisting complete layouts must not be chosen by filename precedence."""
    root = tmp_path / "ambiguous"
    _write_layout(root, "new", snapshot="new-2027")
    _write_layout(root, "legacy", snapshot="legacy-2026", totals=(900.0, 800.0))

    with pytest.raises(ValueError):
        load_demography_artifacts(root)

    selected_new = load_demography_artifacts(root, layout="new")
    selected_legacy = load_demography_artifacts(root, layout="legacy")

    assert selected_new.metadata["snapshot"] == "new-2027"
    assert selected_new.metadata["demography_layout"] == "new"
    assert np.array_equal(selected_new.target_state_totals, np.array([100.0, 250.0]))
    assert selected_legacy.metadata["snapshot"] == "legacy-2026"
    assert selected_legacy.metadata["demography_layout"] == "legacy"
    assert np.array_equal(selected_legacy.target_state_totals, np.array([900.0, 800.0]))


def test_mixed_targets_and_priors_fail_before_component_composition(tmp_path: Path) -> None:
    """Shape-compatible members from different layouts are not one snapshot."""
    root = tmp_path / "mixed"
    _write_json(_path(root, "new", "targets"), _targets("new-2027"))
    _write_json(_path(root, "legacy", "priors"), _priors(scale=2.0))

    with pytest.raises(ValueError):
        load_demography_artifacts(root)


def test_incomplete_new_layout_does_not_fallback_to_legacy_priors(tmp_path: Path) -> None:
    """A missing required new member cannot silently select an old member."""
    root = tmp_path / "incomplete"
    _write_json(_path(root, "new", "targets"), _targets("new-2027"))
    _write_json(_path(root, "legacy", "priors"), _priors(scale=2.0))

    with pytest.raises((FileNotFoundError, ValueError)):
        load_demography_artifacts(root)


def test_corrupt_new_member_does_not_fallback_to_legacy_bytes(tmp_path: Path) -> None:
    """A corrupt selected member fails closed even when an old copy exists."""
    root = tmp_path / "corrupt"
    _write_json(_path(root, "new", "targets"), _targets("new-2027"))
    corrupt = _path(root, "new", "priors")
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_text("{not-json", encoding="utf-8")
    _write_layout(root, "legacy", snapshot="legacy-2026", include_donor=False)

    with pytest.raises(ValueError):
        load_demography_artifacts(root, layout="new")


def test_shape_mismatch_fails_closed_without_layout_fallback(tmp_path: Path) -> None:
    """A selected layout's invalid shapes are not repaired by another filename."""
    root = tmp_path / "shape-mismatch"
    _write_json(_path(root, "new", "targets"), _targets("new-2027"))
    _write_json(
        _path(root, "new", "priors"),
        {
            "transition_prior_matrix": [[1.0]],
            "allowed_transition_mask": [[True]],
        },
    )
    _write_layout(root, "legacy", snapshot="legacy-2026", include_donor=False)

    with pytest.raises(ValueError):
        load_demography_artifacts(root, layout="new")


def test_removing_new_required_member_does_not_change_snapshot_to_legacy(
    tmp_path: Path,
) -> None:
    """Removing a new member cannot switch the experiment to a flat snapshot."""
    root = tmp_path / "removed-new-member"
    _write_layout(root, "new", snapshot="new-2027")
    _write_layout(root, "legacy", snapshot="legacy-2026", totals=(900.0, 800.0))
    _path(root, "new", "targets").unlink()

    with pytest.raises((FileNotFoundError, ValueError)):
        load_demography_artifacts(root)
    with pytest.raises(ValueError):
        load_demography_artifacts(root, layout="legacy")


def test_optional_donor_remains_optional_after_layout_selection(tmp_path: Path) -> None:
    """A selected complete layout may intentionally omit its optional donor."""
    root = tmp_path / "without-donor"
    _write_layout(root, "new", snapshot="new-2027", include_donor=False)

    artifacts = load_demography_artifacts(root)

    assert artifacts.donor_weights is None
    assert artifacts.donor_state_index is None
    assert artifacts.donor_record_index is None


def test_read_api_and_static_aging_preserve_snapshot_controls(tmp_path: Path) -> None:
    """The read facade and pure static-aging builder preserve typed payloads."""
    root = tmp_path / "read-api"
    _write_layout(root, "new", snapshot="new-2027")

    artifacts = load_demography_from_read_api(root)
    state = build_static_aging_state(
        base_weights=np.array([1.0, 2.0]),
        origin_state_index=np.array([0, 1]),
        artifacts=artifacts,
        exit_weights=np.array([0.2, 0.0]),
    )

    assert artifacts.contract_id == "data_forge.ukraine.demography.artifacts.v1"
    assert not hasattr(artifacts, "authority_purpose")
    assert np.array_equal(state["target_state_totals"], np.array([100.0, 250.0]))
    assert np.array_equal(state["donor_record_index"], np.array([1001, 1002]))
    assert np.array_equal(state["exit_weights"], np.array([0.2, 0.0]))
