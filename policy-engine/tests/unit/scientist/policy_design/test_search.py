from __future__ import annotations

from polisyos.scientist.methods.search.contracts import SearchResult, SearchStatus
from polisyos.scientist.policy_design.search import (
    HierarchicalSearchResult,
    HierarchicalSearchState,
)


def test_hierarchical_search_models_resolve_nested_projection_contracts() -> None:
    search_result = SearchResult(
        search_id="search-without-projection",
        status=SearchStatus.STOPPED,
        best_candidate=None,
        best_objective=0.0,
        iterations_completed=0,
        history=[],
        stopping_reason="test",
        total_duration_seconds=0.0,
        stage_a_evaluations=0,
        stage_b_evaluations=0,
    )

    state = HierarchicalSearchState(parameter_search_results={"candidate": search_result})
    result = HierarchicalSearchResult(state=state)

    assert result.state.parameter_search_results["candidate"] is search_result
    assert result.pareto_projection is None
