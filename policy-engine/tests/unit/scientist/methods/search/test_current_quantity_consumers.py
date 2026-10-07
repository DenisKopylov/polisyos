"""Actual ordinary registry intake preserves unknowns and rejects invalid numbers."""

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.scientist.methods.search.pareto_registry import (
    ParetoBasisScope,
    ParetoRegistry,
    ParetoView,
)
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)


def _vector(candidate_id, values):
    return PolicyEvaluationVector(
        candidate_id=candidate_id,
        primary={
            name: ObjectiveChannelValue(
                name=name,
                kind=ObjectiveKind.PRIMARY,
                value=value,
                direction=ObjectiveDirection.MAXIMIZE,
            )
            for name, value in values.items()
        },
    )


def _ref(store, candidate_id):
    return store.put_json(
        {"candidate_id": candidate_id, "profile": "declared-numeric-fixture.v1"},
        ArtifactWriteOptions(kind="declared.numeric-candidate", media_type="application/json"),
    )


def _update(registry, store, candidate_id, values):
    ref = _ref(store, candidate_id)
    registry.update(
        "quantity-intake",
        candidate_hash=str(ref.artifact_id),
        candidate_ref=ref,
        evaluation=_vector(candidate_id, values),
        objective_basis_by_view={
            "global_feasible": ParetoBasisScope(
                scope="declared",
                coordinate_ids=["policy_value", "employment"],
                basis_ref="declared-numeric-fixture.v1",
            )
        },
    )
    return str(ref.artifact_id)


def test_public_registry_missing_axis_remains_unassessed_at_fresh_projection(tmp_path):
    root = tmp_path / "registry"
    registry = ParetoRegistry(root=root)
    store = FileSystemCAS(tmp_path / "cas")
    valid = _update(registry, store, "valid", {"policy_value": 2.0, "employment": 1.0})
    unknown = _update(registry, store, "unknown", {"policy_value": 100.0})
    fresh = ParetoRegistry(root=root).get_snapshot("quantity-intake")
    projection = fresh.project_view(ParetoView.GLOBAL_FEASIBLE)
    assert projection.assessment.status == "partial"
    assert projection.assessment.input_count == 2
    assert projection.assessment.assessed_count == 1
    assert projection.assessment.unassessed_candidate_hashes == [unknown]
    assert projection.assessment.missing_coordinate_ids_by_candidate_hash[unknown]
    assert projection.ranked_frontier_hashes == ()
    assert projection.candidate_frontier_hashes == (valid,)
    assert unknown not in projection.candidate_frontier_hashes
    assert unknown in projection.unassessed_candidate_hashes
    assert fresh.hypervolume_by_view["global_feasible"] == 0.0
    assert fresh.hypervolume_assessments["global_feasible"].status == "available"
    assert projection.assessment.coverage_status == "partial"


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_public_registry_nonfinite_refusal_preserves_canonical_previous_bytes(tmp_path, invalid):
    root = tmp_path / "registry"
    registry = ParetoRegistry(root=root)
    store = FileSystemCAS(tmp_path / "cas")
    valid = _update(registry, store, "valid", {"policy_value": 2.0, "employment": 1.0})
    canonical = root / "loops" / "quantity-intake" / "pareto_registry.json"
    previous = canonical.read_bytes()
    with pytest.raises(ValueError, match="finite"):
        _update(registry, store, "invalid", {"policy_value": invalid, "employment": 1.0})
    assert canonical.read_bytes() == previous
    fresh = ParetoRegistry(root=root).get_snapshot("quantity-intake")
    assert set(fresh.entries) == {valid}
    assert fresh.project_view(ParetoView.GLOBAL_FEASIBLE).assessment.status == "complete"
    assert fresh.hypervolume_by_view["global_feasible"] == 0.0
    assert fresh.hypervolume_assessments["global_feasible"].status == "available"


def test_public_registry_wholly_unassessed_basis_is_unavailable_on_fresh_read(tmp_path):
    root = tmp_path / "registry"
    registry = ParetoRegistry(root=root)
    store = FileSystemCAS(tmp_path / "cas")
    unknown = _update(registry, store, "unknown", {})
    fresh = ParetoRegistry(root=root).get_snapshot("quantity-intake")
    projection = fresh.project_view(ParetoView.GLOBAL_FEASIBLE)
    assert projection.assessment.status == "no_usable_inputs"
    assert projection.assessment.input_count == 1
    assert projection.assessment.assessed_count == 0
    assert projection.unassessed_candidate_hashes == (unknown,)
    assert projection.ranked_frontier_hashes == projection.candidate_frontier_hashes == ()
    assert fresh.hypervolume_by_view["global_feasible"] is None
    assert fresh.hypervolume_assessments["global_feasible"].status == "unavailable"
    assert fresh.hypervolume_assessments["global_feasible"].reason == "no_usable_inputs"
