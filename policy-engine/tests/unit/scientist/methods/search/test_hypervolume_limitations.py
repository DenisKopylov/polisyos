"""Overflowed volume stays unavailable while the real frontier remains usable."""

from __future__ import annotations

import copy
import json

import pytest

from polisyos.scientist.methods.search.contracts import ParetoBasisScope
from polisyos.scientist.methods.search.pareto_registry import (
    ParetoRegistry,
    ParetoRegistrySnapshot,
    ParetoView,
)
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)


def _evaluation(candidate_id: str, value: float) -> PolicyEvaluationVector:
    return PolicyEvaluationVector(
        candidate_id=candidate_id,
        primary={
            name: ObjectiveChannelValue(
                name=name,
                kind=ObjectiveKind.PRIMARY,
                value=value,
                direction=ObjectiveDirection.MAXIMIZE,
            )
            for name in ("policy_value", "employment")
        },
        feasible=True,
    )


def test_registry_persists_unavailable_volume_without_losing_frontier(tmp_path) -> None:
    root = tmp_path / "registry"
    registry = ParetoRegistry(root=root)
    basis = ParetoBasisScope(
        scope="declared", coordinate_ids=["policy_value", "employment"], basis_ref="fixture:axes/v1"
    )
    worst_hash, best_hash = "a" * 64, "b" * 64
    for candidate_hash, value in ((worst_hash, -1e308), (best_hash, 1e308)):
        registry.update(
            "overflow",
            candidate_hash=candidate_hash,
            evaluation=_evaluation(candidate_hash, value),
            objective_basis_by_view={"global_feasible": basis},
        )
    restored = ParetoRegistry(root=root).get_snapshot("overflow")
    projection = restored.project_view(ParetoView.GLOBAL_FEASIBLE)
    assert projection.ranked_frontier_hashes == (best_hash,)
    assert restored.hypervolume_by_view["global_feasible"] is None
    assessment = restored.hypervolume_assessments_by_view["global_feasible"]
    assert assessment.status == "unavailable"
    assert assessment.predicate_basis == "not_established"
    assert assessment.limitation == "non_finite_derived_hypervolume"
    assert projection.assessment.hypervolume_assessment == assessment
    payload = restored.model_dump(mode="json")
    encoded = json.dumps(payload, allow_nan=False)
    assert ParetoRegistrySnapshot.model_validate_json(encoded) == restored

    # A fake measured zero or loss of the diagnostic cannot admit the same artifact.
    for mutation in ("fake_zero", "missing_diagnostic"):
        broken = copy.deepcopy(payload)
        if mutation == "fake_zero":
            broken["hypervolume_by_view"]["global_feasible"] = 0.0
        else:
            broken["hypervolume_assessments_by_view"].pop("global_feasible")
        with pytest.raises(ValueError):
            ParetoRegistrySnapshot.model_validate(broken)
