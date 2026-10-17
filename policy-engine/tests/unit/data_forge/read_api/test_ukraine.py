from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest

from polisyos.data_forge.domains.ukraine import demography as demography_module
from polisyos.data_forge.read_api.ukraine import (
    load_demography_artifacts,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.read_api.ukraine import UkraineDemographyArtifacts


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


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


def _layout_payloads(label: str) -> dict[str, dict]:
    """Return visibly distinct, shape-compatible values for one layout fixture."""
    base = 100.0 if label == "new" else 900.0
    return {
        "targets": {
            "state_ids": [f"{label}:a", f"{label}:b"],
            "target_state_totals": [base, base + 1.0],
            "entrant_state_totals": [base / 10, base / 20],
            "metadata": {"layout_fixture": label},
        },
        "priors": {
            "transition_prior_matrix": (
                [[0.91, 0.09], [0.23, 0.77]] if label == "new" else [[0.61, 0.39], [0.34, 0.66]]
            ),
            "allowed_transition_mask": [[True, True], [False, True]],
        },
        "donor": {
            "donor_weights": [0.13, 0.87] if label == "new" else [0.75, 0.25],
            "donor_state_index": [0, 1],
            "donor_record_index": [int(base) + 1, int(base) + 2],
        },
    }


def _write_layout_member(
    root: Path,
    layout: str,
    role: str,
    payload: dict | None = None,
) -> None:
    _write_json(
        root / _LAYOUT_PATHS[layout][role],
        payload if payload is not None else _layout_payloads(layout)[role],
    )


def _write_complete_layout(root: Path, layout: str, *, donor: bool = True) -> None:
    for role in ("targets", "priors", *(("donor",) if donor else ())):
        _write_layout_member(root, layout, role)


def _assert_layout_values(artifacts: UkraineDemographyArtifacts, layout: str) -> None:
    expected = _layout_payloads(layout)
    assert artifacts.source_evidence.source_layout == layout
    assert artifacts.state_ids == expected["targets"]["state_ids"]
    assert np.array_equal(
        artifacts.target_state_totals,
        np.asarray(expected["targets"]["target_state_totals"]),
    )
    assert np.array_equal(
        artifacts.entrant_state_totals,
        np.asarray(expected["targets"]["entrant_state_totals"]),
    )
    assert np.array_equal(
        artifacts.transition_prior_matrix,
        np.asarray(expected["priors"]["transition_prior_matrix"]),
    )
    assert np.array_equal(artifacts.donor_weights, np.asarray(expected["donor"]["donor_weights"]))
    assert np.array_equal(
        artifacts.donor_record_index,
        np.asarray(expected["donor"]["donor_record_index"]),
    )


def test_public_demography_readers_preserve_each_complete_layout(tmp_path: Path) -> None:
    """The artifact and scalar APIs read all roles from the selected complete layout."""
    for layout in ("new", "legacy"):
        root = tmp_path / layout
        _write_complete_layout(root, layout)
        expected = _layout_payloads(layout)

        artifacts = load_demography_artifacts(root)
        _assert_layout_values(artifacts, layout)

        targets = load_reconciled_targets(root)
        priors = load_transition_priors(root)
        donor = load_donor_pool(root)
        assert targets.evidence.source_layout == layout
        assert targets["state_ids"] == expected["targets"]["state_ids"]
        assert targets["target_state_totals"] == expected["targets"]["target_state_totals"]
        assert priors.evidence.source_layout == layout
        assert priors["transition_prior_matrix"] == expected["priors"]["transition_prior_matrix"]
        assert donor.evidence.source_layout == layout
        assert donor["donor_record_index"] == expected["donor"]["donor_record_index"]


@pytest.mark.parametrize(
    ("targets_layout", "priors_layout"),
    [("new", "legacy"), ("legacy", "new")],
)
def test_public_demography_readers_refuse_cross_layout_required_members(
    tmp_path: Path,
    targets_layout: str,
    priors_layout: str,
) -> None:
    """Required members from different layouts never form an implicit snapshot."""
    root = tmp_path / f"{targets_layout}_targets_{priors_layout}_priors"
    _write_layout_member(root, targets_layout, "targets")
    _write_layout_member(root, priors_layout, "priors")

    with pytest.raises(ValueError, match="layout"):
        load_demography_artifacts(root)
    for reader in (load_reconciled_targets, load_transition_priors, load_donor_pool):
        with pytest.raises(ValueError, match="layout"):
            reader(root)


def test_layout_selector_is_the_cross_role_semantic_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing whole-layout selection makes the public scalar readers splice values."""
    root = tmp_path / "cross_role_counterfactual"
    _write_layout_member(root, "new", "targets")
    _write_layout_member(root, "legacy", "priors")

    def select_each_role_independently(
        source_root: Path,
        requested_layout: str | None,
        *,
        standalone_member: str | None = None,
    ) -> tuple[str | None, dict[str, Path]]:
        if requested_layout is not None:
            selected = requested_layout
        else:
            candidates = ("new", "legacy") if standalone_member == "targets" else ("legacy", "new")
            selected = next(
                layout
                for layout in candidates
                if standalone_member is not None
                and (source_root / _LAYOUT_PATHS[layout][standalone_member]).is_file()
            )
        paths = demography_module._layout_member_paths(source_root, selected)
        return selected, paths

    with monkeypatch.context() as patch:
        patch.setattr(
            demography_module, "_select_demography_layout", select_each_role_independently
        )
        targets = load_reconciled_targets(root)
        priors = load_transition_priors(root)
        assert targets.evidence.source_layout == "new"
        assert (
            targets["target_state_totals"]
            == _layout_payloads("new")["targets"]["target_state_totals"]
        )
        assert priors.evidence.source_layout == "legacy"
        assert (
            priors["transition_prior_matrix"]
            == _layout_payloads("legacy")["priors"]["transition_prior_matrix"]
        )

    with pytest.raises(ValueError, match="layout"):
        load_reconciled_targets(root)


def test_multiple_complete_layouts_require_an_explicit_selection(tmp_path: Path) -> None:
    """Conflicting complete snapshots refuse implicit choice but remain readable by request."""
    root = tmp_path / "two_complete_layouts"
    _write_complete_layout(root, "new")
    _write_complete_layout(root, "legacy")

    with pytest.raises(ValueError, match="multiple complete"):
        load_demography_artifacts(root)
    for reader in (load_reconciled_targets, load_transition_priors, load_donor_pool):
        with pytest.raises(ValueError, match="multiple complete"):
            reader(root)

    for layout in ("new", "legacy"):
        artifacts = load_demography_artifacts(root, layout=layout)
        _assert_layout_values(artifacts, layout)
        assert (
            load_reconciled_targets(root, layout=layout)["state_ids"]
            == _layout_payloads(layout)["targets"]["state_ids"]
        )


@pytest.mark.parametrize(
    ("members", "complete_layout"),
    [
        ((("new", "targets"), ("new", "priors"), ("legacy", "donor")), "new"),
        ((("legacy", "targets"), ("legacy", "priors"), ("new", "donor")), "legacy"),
        ((("new", "targets"), ("legacy", "donor")), None),
    ],
)
def test_foreign_or_incomplete_optional_donor_does_not_cross_layouts(
    tmp_path: Path,
    members: tuple[tuple[str, str], ...],
    complete_layout: str | None,
) -> None:
    """Optionality permits absence, not borrowing a donor from a different layout."""
    root = tmp_path / "foreign_donor"
    for layout, role in members:
        _write_layout_member(root, layout, role)

    with pytest.raises(ValueError, match="layout"):
        load_demography_artifacts(root)
    if complete_layout is not None:
        with pytest.raises(ValueError, match="layout"):
            load_demography_artifacts(root, layout=complete_layout)
    for reader in (load_reconciled_targets, load_transition_priors, load_donor_pool):
        with pytest.raises(ValueError, match="layout"):
            reader(root)


def test_absent_donor_remains_optional_inside_one_complete_layout(tmp_path: Path) -> None:
    """A genuinely absent optional donor does not invalidate a single complete layout."""
    root = tmp_path / "optional_donor_absent"
    _write_complete_layout(root, "new", donor=False)

    artifacts = load_demography_artifacts(root)
    _assert_layout_values_without_donor(artifacts, "new")
    donor = load_donor_pool(root)
    assert dict(donor) == {}
    assert donor.evidence.donor_disposition == "not_established"


def _assert_layout_values_without_donor(
    artifacts: UkraineDemographyArtifacts,
    layout: str,
) -> None:
    expected = _layout_payloads(layout)
    assert artifacts.source_evidence.source_layout == layout
    assert artifacts.state_ids == expected["targets"]["state_ids"]
    assert np.array_equal(
        artifacts.target_state_totals,
        np.asarray(expected["targets"]["target_state_totals"]),
    )
    assert np.array_equal(
        artifacts.transition_prior_matrix,
        np.asarray(expected["priors"]["transition_prior_matrix"]),
    )
    assert artifacts.donor_weights is None
