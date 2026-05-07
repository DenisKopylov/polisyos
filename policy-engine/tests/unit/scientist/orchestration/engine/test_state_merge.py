"""Tests for polisyos.scientist.orchestration.engine.state_merge — parallel outcome merging."""

from __future__ import annotations

import pytest
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_merge import (
    MergeConflictPolicy,
    merge_parallel_outcomes,
)


@pytest.fixture
def base_state():
    return ExperimentState(run_id="test-merge")


def _ok_outcome(state: ExperimentState, **updates) -> NodeOutcome:
    updated_state = state.model_copy(update=updates) if updates else state
    return NodeOutcome(status="ok", state=updated_state, events=[], artifacts=[])


# ---------------------------------------------------------------------------
# merge_parallel_outcomes
# ---------------------------------------------------------------------------


class TestMergeParallelOutcomes:
    def test_empty_outcomes(self, base_state):
        result = merge_parallel_outcomes(base_state, {}, {})
        assert result.state is base_state
        assert result.conflicts == []

    def test_single_outcome_disjoint_dict_write(self, base_state):
        outcome = _ok_outcome(base_state, params={"key1": "val1"})
        result = merge_parallel_outcomes(
            base_state,
            {"node_a": outcome},
            {"node_a": ["params"]},
        )
        assert result.state.params.get("key1") == "val1"
        assert result.conflicts == []

    def test_two_outcomes_disjoint_writes(self, base_state):
        outcome_a = _ok_outcome(base_state, params={"key_a": "a"})
        outcome_b = _ok_outcome(base_state, artifacts_index={"art_b": "ref_b"})
        result = merge_parallel_outcomes(
            base_state,
            {"node_a": outcome_a, "node_b": outcome_b},
            {"node_a": ["params"], "node_b": ["artifacts_index"]},
        )
        assert result.state.params.get("key_a") == "a"
        assert result.state.artifacts_index.get("art_b") == "ref_b"
        assert result.conflicts == []

    def test_overlapping_dict_keys_conflict(self, base_state):
        outcome_a = _ok_outcome(base_state, params={"shared": "from_a"})
        outcome_b = _ok_outcome(base_state, params={"shared": "from_b"})
        result = merge_parallel_outcomes(
            base_state,
            {"node_a": outcome_a, "node_b": outcome_b},
            {"node_a": ["params"], "node_b": ["params"]},
        )
        assert result.applied is False
        assert result.state is base_state
        assert len(result.conflicts) == 1
        assert "params.shared" in result.conflicts[0]
        assert result.conflict_details[0].path == "params.shared"

    def test_disjoint_dict_keys_same_field(self, base_state):
        outcome_a = _ok_outcome(base_state, params={"key_a": "a"})
        outcome_b = _ok_outcome(base_state, params={"key_b": "b"})
        result = merge_parallel_outcomes(
            base_state,
            {"node_a": outcome_a, "node_b": outcome_b},
            {"node_a": ["params"], "node_b": ["params"]},
        )
        assert result.state.params.get("key_a") == "a"
        assert result.state.params.get("key_b") == "b"
        assert result.conflicts == []

    def test_base_state_unchanged_on_empty(self, base_state):
        result = merge_parallel_outcomes(base_state, {}, {})
        assert result.state is base_state

    def test_scalar_field_write(self, base_state):
        # run_id is a scalar string field
        outcome = _ok_outcome(base_state, run_id="new-run-id")
        result = merge_parallel_outcomes(
            base_state,
            {"node_a": outcome},
            {"node_a": ["run_id"]},
        )
        assert result.state.run_id == "new-run-id"
        assert result.conflicts == []

    def test_preserves_base_keys_on_merge(self, base_state):
        # Put some initial data in base state
        base = base_state.model_copy(update={"params": {"existing": "value"}})
        outcome = _ok_outcome(base, params={"existing": "value", "new_key": "new_val"})
        result = merge_parallel_outcomes(
            base,
            {"node_a": outcome},
            {"node_a": ["params"]},
        )
        assert result.state.params.get("existing") == "value"
        assert result.state.params.get("new_key") == "new_val"
        assert result.conflicts == []

    def test_dot_path_writes_merge_atomically(self, base_state):
        outcome_a = _ok_outcome(base_state, params={"alpha": 1})
        outcome_b = _ok_outcome(base_state, params={"beta": 2})
        result = merge_parallel_outcomes(
            base_state,
            {"node_a": outcome_a, "node_b": outcome_b},
            {"node_a": ["params.alpha"], "node_b": ["params.beta"]},
        )
        assert result.applied is True
        assert result.state.params == {"alpha": 1, "beta": 2}

    def test_dot_path_conflict_keeps_base_state(self, base_state):
        base = base_state.model_copy(update={"params": {"shared": "base", "safe": "keep"}})
        outcome_a = _ok_outcome(base, params={"shared": "from_a", "safe": "keep"})
        outcome_b = _ok_outcome(base, params={"shared": "from_b", "safe": "keep"})
        result = merge_parallel_outcomes(
            base,
            {"node_a": outcome_a, "node_b": outcome_b},
            {"node_a": ["params.shared"], "node_b": ["params.shared"]},
        )
        assert result.applied is False
        assert result.state.params == {"shared": "base", "safe": "keep"}
        assert result.conflict_details[0].aliases == ("node_a", "node_b")

    def test_last_write_wins_is_explicit(self, base_state):
        outcome_a = _ok_outcome(base_state, params={"shared": "from_a"})
        outcome_b = _ok_outcome(base_state, params={"shared": "from_b"})
        result = merge_parallel_outcomes(
            base_state,
            {"node_a": outcome_a, "node_b": outcome_b},
            {"node_a": ["params.shared"], "node_b": ["params.shared"]},
            conflict_policy=MergeConflictPolicy.LAST_WRITE_WINS,
        )
        assert result.applied is True
        assert result.state.params["shared"] == "from_b"
        assert result.conflicts == []
        assert len(result.resolved_conflicts) == 1

    def test_nested_overlap_is_reported_as_conflict(self, base_state):
        outcome_a = _ok_outcome(base_state, params={"bucket": {"a": 1}})
        outcome_b = _ok_outcome(base_state, params={"bucket": {"a": 2}})
        result = merge_parallel_outcomes(
            base_state,
            {"node_a": outcome_a, "node_b": outcome_b},
            {"node_a": ["params.bucket"], "node_b": ["params.bucket.a"]},
        )
        assert result.applied is False
        assert result.conflict_details[0].path == "params.bucket"
