from __future__ import annotations

import pickle

from polisyos.scientist.methods.search.contracts import (
    SearchIteration,
    SearchResult,
    SearchStatus,
)
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    ObjectiveScoreStatus,
)
from polisyos.scientist.policy_design.search import (
    HierarchicalSearchResult,
    HierarchicalSearchState,
)


def test_hierarchical_search_models_resolve_nested_projection_contracts() -> None:
    fixture_unit = "fixture-budget-unit"
    objective = BudgetDeficitObjective(expected_unit=fixture_unit).evaluate(
        {
            "budget_deficit": 0.25,
            "metric_units": {"budget_deficit": fixture_unit},
        }
    )
    assessment = objective.score_assessment
    assert assessment is not None
    assert assessment.status is ObjectiveScoreStatus.AVAILABLE
    assert assessment.value is not None

    iteration = SearchIteration(
        iteration=1,
        candidate={"candidate_id": "candidate-search-annotations"},
        objective_value=assessment.value,
        objective_details=[objective],
        is_promising=True,
        stage_a_passed=True,
        stage_b_result={},
        duration_seconds=0.01,
        score_status=assessment.status,
        score_assessment=assessment,
    )
    search_result = SearchResult(
        search_id="search-with-typed-history",
        status=SearchStatus.STOPPED,
        best_candidate={"candidate_id": "candidate-search-annotations"},
        best_objective=assessment.value,
        iterations_completed=1,
        history=[iteration],
        stopping_reason="test",
        total_duration_seconds=0.01,
        stage_a_evaluations=1,
        stage_b_evaluations=1,
    )

    state = HierarchicalSearchState(parameter_search_results={"candidate": search_result})
    result = HierarchicalSearchResult(state=state)

    assert result.state.parameter_search_results["candidate"] is search_result
    assert result.pareto_projection is None
    HierarchicalSearchResult.model_json_schema()

    wire = result.model_dump(mode="json")
    restored = HierarchicalSearchResult.model_validate(wire)
    restored_search_result = restored.state.parameter_search_results["candidate"]
    restored_iteration = restored_search_result.history[0]
    assert isinstance(restored_iteration, SearchIteration)
    assert restored_iteration.objective_details == [objective]
    assert restored_iteration.score_assessment == assessment
    assert pickle.loads(pickle.dumps(iteration)) == iteration  # noqa: S301
    assert pickle.loads(pickle.dumps(search_result)) == search_result  # noqa: S301
