"""Semantic action dates, trace-only dates and independent evaluation custody."""

from copy import deepcopy

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.runtime import SequenceCandidateGenerator
from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
)
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry, ParetoView
from polisyos.scientist.methods.search.run_state import SearchRunState
from polisyos.scientist.methods.search.service import (
    NativeSearchService,
    _decode_checkpoint,
)
from polisyos.scientist.methods.search.stopping import MaxIterations


def _date_stage_b(candidate, context):
    from polisyos.scientist.policy_design.objectives import (
        ObjectiveChannelValue,
        ObjectiveDirection,
        ObjectiveKind,
        PolicyEvaluationVector,
    )

    replica = candidate["_replica"]
    return {
        "simulation_results": {"budget_deficit": 2},
        "feedback": {"verdict": "APPROVE"},
        "policy_evaluation": PolicyEvaluationVector(
            candidate_id=f"full-fixture-evaluation-{replica}",
            primary={
                "policy_value": ObjectiveChannelValue(
                    name="policy_value",
                    kind=ObjectiveKind.PRIMARY,
                    value=2,
                    direction=ObjectiveDirection.MAXIMIZE,
                ),
                "employment": ObjectiveChannelValue(
                    name="employment",
                    kind=ObjectiveKind.PRIMARY,
                    value=0.5,
                    direction=ObjectiveDirection.MAXIMIZE,
                ),
            },
            metadata={"replicate_id": f"independent-replica-{replica}"},
        ),
    }


def _date_service(root, registry):
    first = {
        "cost": 2,
        "semantic": {"metadata": {"starts_at": "2026-01-01", "effective_date": "2026-01-15"}},
        "created_at": "2026-04-01",
        "metadata": {"loaded_at": "2026-04-01"},
        "_replica": 1,
    }
    equivalent = {
        "_replica": 2,
        "metadata": {"loaded_at": "2026-05-01"},
        "created_at": "2026-05-01",
        "semantic": {"metadata": {"effective_date": "2026-01-15", "starts_at": "2026-01-01"}},
        "cost": 2,
    }
    later = deepcopy(first)
    later["semantic"]["metadata"]["starts_at"] = "2026-02-01"
    later["_replica"] = 3
    return NativeSearchService(
        SearchController(
            SearchConfig(
                stopping=MaxIterations(3),
                objective=CompositeObjective([BudgetDeficitObjective()]),
                enable_stage_a=False,
                pareto_registry=registry,
            ),
            SequenceCandidateGenerator([first, equivalent, later]),
            lambda candidate, context: (0.0, True),
            _date_stage_b,
        ),
        store=FileSystemCAS(root),
    )


@pytest.mark.parametrize("registry_profile", [False, True])
def test_actual_native_frontier_registry_and_cas_preserve_semantic_dates_and_all_replicas(
    tmp_path, registry_profile
):
    registry_root = tmp_path / "registry"
    registry = ParetoRegistry(registry_root) if registry_profile else None
    source = _date_service(tmp_path / "cas", registry)
    result = source.run_search(initial_context={})
    ref = source.checkpoint_ref
    original = source._store.get_bytes(ref)
    fresh_store = FileSystemCAS(tmp_path / "cas")
    raw = _decode_checkpoint(fresh_store.get_verified_snapshot(ref).data)
    fresh_state = SearchRunState.from_checkpoint(raw["run_state"])
    assert fresh_state.history == result.history
    assert len(fresh_state.history) == fresh_state.evaluation_iterations == 3
    assert len(raw["completed_candidate_ids"]) == 3
    assert len(set(raw["completed_candidate_ids"])) == 3
    assert [row.policy_evaluation.candidate_id for row in fresh_state.history] == [
        "full-fixture-evaluation-1",
        "full-fixture-evaluation-2",
        "full-fixture-evaluation-3",
    ]
    assert [row.policy_evaluation.metadata["replicate_id"] for row in fresh_state.history] == [
        "independent-replica-1",
        "independent-replica-2",
        "independent-replica-3",
    ]
    assert [row.candidate["semantic"]["metadata"]["starts_at"] for row in fresh_state.history] == [
        "2026-01-01",
        "2026-01-01",
        "2026-02-01",
    ]
    # The two same-action evaluations remain in history; the candidate frontier
    # independently contains two logical subjects, regardless of trace/JSON order.
    if registry_profile:
        persisted = ParetoRegistry(registry_root).get_snapshot(result.search_id)
        assert len(persisted.entries) == 2
        assert {
            row.seed_payload["semantic"]["metadata"]["starts_at"]
            for row in persisted.entries.values()
        } == {"2026-01-01", "2026-02-01"}
        assert all(
            row.seed_payload["semantic"]["metadata"]["effective_date"] == "2026-01-15"
            for row in persisted.entries.values()
        )
        assert {row.evaluation.metadata["replicate_id"] for row in persisted.entries.values()} == {
            "independent-replica-2",
            "independent-replica-3",
        }
        # This is observed candidate identity, not a claim of global ranking or
        # a public resume profile for configured external registries.
        projection = persisted.project_view(ParetoView.GLOBAL_FEASIBLE)
        assert projection.ranked_frontier_hashes == ()
        assert projection.assessment.status != "complete"
    else:
        assert len(fresh_state.pareto_points) == 2
        assert {
            point.candidate["semantic"]["metadata"]["starts_at"]
            for point in fresh_state.pareto_points
        } == {"2026-01-01", "2026-02-01"}
        fresh = _date_service(tmp_path / "cas", None)
        fresh.restore(ref, context={})
        resumed = fresh.resume_search(context={})
        assert resumed.history == result.history and resumed.pareto_front == result.pareto_front
    assert fresh_store.get_bytes(ref) == original
