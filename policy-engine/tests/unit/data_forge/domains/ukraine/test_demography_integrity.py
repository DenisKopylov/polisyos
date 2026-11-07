"""Role ownership and exact discrete identity at the demographic reader boundary."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.ukraine.demography import (
    UkraineDemographyArtifacts,
    load_demography_artifacts,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
)
from polisyos.data_forge.domains.ukraine.demography.source_inventory import (
    HistoricalLayoutRequest,
    SourceResolutionRefusalError,
    read_demography_role,
    resolve_demography_source,
)
from polisyos.data_forge.domains.ukraine.static_aging import build_static_aging_state


def _members() -> dict[str, dict[str, object]]:
    return {
        "targets": {
            "state_ids": ["a", "b"],
            "target_state_totals": [100.0, 250.0],
            "entrant_state_totals": [1.0, 2.0],
        },
        "priors": {"transition_prior_matrix": [[0.8, 0.2], [0.1, 0.9]]},
        "donor": {
            "donor_weights": [0.25, 0.75],
            "donor_state_index": [0, 1],
            "donor_record_index": [1001, 1002],
        },
    }


def _write_snapshot(
    root: Path, members: dict[str, dict[str, object]], *, layout: str = "new"
) -> None:
    names = {
        "targets": "targets.json" if layout == "new" else "demography_targets.json",
        "priors": "transition_priors.json"
        if layout == "new"
        else "demography_transition_priors.json",
        "donor": "donor_pool.json" if layout == "new" else "demography_donor_pool.json",
    }
    directory = root / "demography" if layout == "new" else root
    directory.mkdir(parents=True, exist_ok=True)
    for role, payload in members.items():
        (directory / names[role]).write_text(json.dumps(payload), encoding="utf-8")


def _dto(tmp_path: Path, **changes: object) -> UkraineDemographyArtifacts:
    root = tmp_path / "base"
    _write_snapshot(root, _members())
    valid = load_demography_artifacts(root)
    payload = valid.model_dump(mode="python")
    payload.update(changes)
    return UkraineDemographyArtifacts.model_validate(payload)


@pytest.mark.parametrize(
    ("role", "field", "wrong"),
    [
        ("priors", "target_state_totals", [900.0, 800.0]),
        ("donor", "state_ids", ["b", "a"]),
        ("targets", "transition_prior_matrix", [[1.0, 0.0], [0.0, 1.0]]),
        ("priors", "donor_record_index", [101, 102]),
    ],
)
def test_foreign_computational_role_cannot_overwrite_its_owner(
    tmp_path: Path, role: str, field: str, wrong: object
) -> None:
    members = _members()
    members[role][field] = wrong
    _write_snapshot(tmp_path, members)
    with pytest.raises(SourceResolutionRefusalError) as raised:
        load_demography_artifacts(tmp_path)
    assert raised.value.code == "demography_role_conflict"
    assert role in str(raised.value) and field in str(raised.value)
    # The historical scalar remains useful; it has never selected the foreign role.
    assert load_reconciled_targets(tmp_path)["target_state_totals"] == [100.0, 250.0]


def test_equal_foreign_computational_repetition_preserves_owner_and_order(tmp_path: Path) -> None:
    members = _members()
    members["priors"]["target_state_totals"] = [100, 250]
    members["donor"]["state_ids"] = ["a", "b"]
    _write_snapshot(tmp_path, members)
    aggregate = load_demography_artifacts(tmp_path)
    assert aggregate.state_ids == ["a", "b"]
    assert aggregate.target_state_totals.tolist() == [100.0, 250.0]
    assert load_reconciled_targets(tmp_path)["target_state_totals"] == [100.0, 250.0]


def test_role_metadata_is_lossless_and_cannot_replace_resolved_source_evidence(
    tmp_path: Path,
) -> None:
    members = _members()
    for role in members:
        members[role]["metadata"] = {
            "shared": role,
            f"{role}_note": {"values": [role]},
            "demography_source_status": "verified",
        }
    _write_snapshot(tmp_path, members)
    aggregate = load_demography_artifacts(tmp_path)
    assert aggregate.metadata["demography_source_status"] == "legacy_limited"
    assert aggregate.metadata["demography_source_identity"] == (
        aggregate.source_evidence.source_identity
    )
    for role in members:
        assert aggregate.metadata["demography_role_metadata"][role] == members[role]["metadata"]
        assert aggregate.metadata[f"{role}_note"] == {"values": [role]}


@pytest.mark.parametrize("field", ["donor_state_index", "donor_record_index"])
@pytest.mark.parametrize("bad", [0.9, -0.9, float("nan"), float("inf"), -float("inf"), 2**63])
def test_discrete_ids_refuse_fraction_nonfinite_and_overflow_before_cast(
    tmp_path: Path, field: str, bad: object
) -> None:
    with pytest.raises(ValidationError):
        _dto(tmp_path, **{field: [bad, 1]})


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([2**53 + 1, 1.0], [2**53 + 1, 1]),
        ([2**63 - 1, 1.0], [2**63 - 1, 1]),
        ([-(2**63), -1.0], [-(2**63), -1]),
    ],
)
def test_mixed_record_scalars_preserve_exact_int64_identity(
    tmp_path: Path, values: list[object], expected: list[int]
) -> None:
    result = _dto(tmp_path, donor_record_index=values)
    assert result.donor_record_index.dtype == np.dtype("int64")
    assert result.donor_record_index.tolist() == expected
    # Follow the real export used by the downstream consumer, not an allclose proxy.
    state = build_static_aging_state(
        base_weights=[1.0, 1.0], origin_state_index=[0, 1], artifacts=result
    )
    assert state["donor_record_index"].tolist() == expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([2**53 + 1, 1.0], [2**53 + 1, 1]),
        ([2**63 - 1, 1.0], [2**63 - 1, 1]),
        ([-(2**63), -1.0], [-(2**63), -1]),
    ],
)
def test_historical_raw_json_readers_preserve_mixed_discrete_identities(
    tmp_path: Path, values: list[object], expected: list[int]
) -> None:
    members = _members()
    members["donor"]["donor_record_index"] = values
    _write_snapshot(tmp_path, members)
    # Raw scalar inspection keeps its original JSON values; typed consumption
    # uses the exact same scalar identities before any common NumPy dtype.
    assert load_donor_pool(tmp_path)["donor_record_index"] == values
    aggregate = load_demography_artifacts(tmp_path)
    assert aggregate.donor_record_index.dtype == np.dtype("int64")
    assert aggregate.donor_record_index.tolist() == expected


@pytest.mark.parametrize("values", [[-(2**63) - 1, 1.0], [float(2**63), 1.0]])
def test_record_boundaries_refuse_actual_out_of_range_values(
    tmp_path: Path, values: list[object]
) -> None:
    with pytest.raises(ValidationError):
        _dto(tmp_path, donor_record_index=values)


def test_already_float_record_input_uses_its_actual_rounded_identity(tmp_path: Path) -> None:
    values = np.asarray([2**53 + 1, 1.0])
    result = _dto(tmp_path, donor_record_index=values)
    assert result.donor_record_index.tolist() == [2**53, 1]


def test_standalone_record_index_cannot_bypass_exact_integrality(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        _dto(tmp_path, donor_weights=None, donor_state_index=None, donor_record_index=[1001.9])
    valid = _dto(tmp_path, donor_weights=None, donor_state_index=None, donor_record_index=[-1.0])
    assert valid.donor_record_index.tolist() == [-1]


def test_projection_evidence_exports_do_not_mutate_a_captured_source(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, _members())
    resolved = resolve_demography_source(
        HistoricalLayoutRequest(kind="historical_layout", root=tmp_path, layout="new")
    )
    targets = read_demography_role(resolved, "targets")
    expected = targets.evidence.model_dump(mode="json")
    exported = targets.evidence
    exported.compatibility_notes.append("caller mutation")
    assert read_demography_role(resolved, "priors").evidence.model_dump(mode="json") == expected
    assert targets.evidence.model_dump(mode="json") == expected


def test_aging_state_exports_do_not_mutate_another_consumer(tmp_path: Path) -> None:
    artifacts = _dto(tmp_path)
    one = build_static_aging_state(
        base_weights=[1.0, 1.0], origin_state_index=[0, 1], artifacts=artifacts
    )
    one["target_state_totals"][0] = 999.0
    one["donor_record_index"][0] = -50
    two = build_static_aging_state(
        base_weights=[1.0, 1.0], origin_state_index=[0, 1], artifacts=artifacts
    )
    assert two["target_state_totals"].tolist() == [100.0, 250.0]
    assert two["donor_record_index"].tolist() == [1001, 1002]


def test_whole_historical_layout_selection_keeps_explicit_old_snapshots(tmp_path: Path) -> None:
    old = _members()
    old["targets"]["target_state_totals"] = [7.0, 9.0]
    _write_snapshot(tmp_path, old, layout="legacy")
    assert load_demography_artifacts(tmp_path).target_state_totals.tolist() == [7.0, 9.0]
    _write_snapshot(tmp_path, _members())
    with pytest.raises(ValueError, match="multiple complete"):
        load_demography_artifacts(tmp_path)
    assert load_demography_artifacts(tmp_path, layout="legacy").target_state_totals.tolist() == [
        7.0,
        9.0,
    ]
    assert load_demography_artifacts(tmp_path, layout="new").target_state_totals.tolist() == [
        100.0,
        250.0,
    ]


def test_mixed_layout_is_rejected_before_parsing_individual_members(tmp_path: Path) -> None:
    # Invalid JSON would raise JSONDecodeError if the reader mixed individual files.
    (tmp_path / "demography").mkdir()
    (tmp_path / "demography" / "targets.json").write_text("{not-json", encoding="utf-8")
    (tmp_path / "demography_transition_priors.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="layout is incomplete") as raised:
        load_demography_artifacts(tmp_path)
    assert not isinstance(raised.value, json.JSONDecodeError)


def test_present_invalid_layout_member_is_not_hidden_by_complete_other_layout(
    tmp_path: Path,
) -> None:
    _write_snapshot(tmp_path, _members(), layout="legacy")
    (tmp_path / "demography" / "targets.json").mkdir(parents=True)
    with pytest.raises(ValueError, match="present but is not a readable file"):
        load_demography_artifacts(tmp_path, layout="legacy")


def test_historical_standalone_prior_and_lawful_donor_absence_are_useful(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, {"priors": _members()["priors"]})
    assert load_transition_priors(tmp_path)["transition_prior_matrix"] == [
        [0.8, 0.2],
        [0.1, 0.9],
    ]
    with pytest.raises(ValueError, match="incomplete"):
        load_demography_artifacts(tmp_path)
    _write_snapshot(tmp_path, {k: v for k, v in _members().items() if k != "donor"})
    assert dict(load_donor_pool(tmp_path)) == {}
    assert load_demography_artifacts(tmp_path).donor_record_index is None
