from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
    RunHierarchicalPolicySearchNode,
)


def test_run_hierarchical_policy_search_adapter_assertion_is_not_swallowed(
    execution_context,
    minimal_state,
) -> None:
    candidate = MagicMock()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._resolve_search_candidate",
            return_value=candidate,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search.HierarchicalPolicySearchAdapter.run_search",
            side_effect=AssertionError("search invariant"),
        ),
    ):
        with pytest.raises(AssertionError, match="search invariant"):
            RunHierarchicalPolicySearchNode().execute(execution_context, minimal_state)


def test_run_hierarchical_policy_search_uses_branch_state_for_final_outputs(
    execution_context,
    minimal_state,
    artifact_ref_factory,
) -> None:
    candidate = MagicMock()
    candidate.candidate_id = "champion"
    candidate.candidate_hash.return_value = "hash:champion"
    candidate.trinity_bundle = {"bundle": "payload"}
    search_result = SimpleNamespace(model_dump=lambda mode="json": {"status": "ok"})
    calls: list[tuple[str, ...]] = []

    def _recording_branch_state(base_state, *, write_paths=()):
        calls.append(tuple(write_paths))
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._resolve_search_candidate",
            return_value=candidate,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search.HierarchicalPolicySearchAdapter.run_search",
            return_value=search_result,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._select_champion_candidate",
            return_value=candidate,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._persist_trinity_bundle",
            return_value=artifact_ref_factory(kind="ir.trinity_bundle"),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search._persist_frontier_report",
            return_value=artifact_ref_factory(kind="ir.policy_frontier_report"),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search.branch_state",
            side_effect=_recording_branch_state,
        ),
    ):
        outcome = RunHierarchicalPolicySearchNode().execute(execution_context, minimal_state)

    assert outcome.status == "ok"
    assert any("params.policy_candidate_schema" in write_paths for write_paths in calls)
