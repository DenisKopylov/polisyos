"""Tests for polisyos.scientist.orchestration.engine.state_merge — parallel outcome merging."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
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


def _artifact_ref(tag: str = "a") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{tag * 64}",
        kind="test.ref",
        media_type="application/json",
    )


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

    # Production mutation caught: replay must consume the branch's recorded
    # writes instead of diffing a cached post-state against the current base.
    def test_replay_preserves_unrelated_changes_and_reapplies_same_value_write(self, base_state):
        original = base_state.model_copy(
            update={"params": {"unrelated": "old", "y": 4}},
        )
        branch = branch_state(original, write_paths=("params",)).state
        branch.params["y"] = 4
        branch.params["written"] = True

        current = base_state.model_copy(
            update={"params": {"unrelated": "new", "y": 9}},
        )
        result = merge_parallel_outcomes(
            current,
            {"node_a": _ok_outcome(branch)},
            {"node_a": ["params"]},
        )

        assert result.state.params == {
            "unrelated": "new",
            "y": 4,
            "written": True,
        }
        assert result.applied_paths == ["params.written", "params.y"]

    # Production mutation caught: merge must carry an explicit delete operation
    # and must not confuse deletion with a null write or with no write.
    def test_replay_distinguishes_delete_null_and_no_write(self, base_state):
        original = base_state.model_copy(update={"params": {"stale": 1, "keep": 2}})

        delete_branch = branch_state(original, write_paths=("params",)).state
        del delete_branch.params["stale"]
        null_branch = branch_state(original, write_paths=("params",)).state
        null_branch.params["stale"] = None
        no_write_branch = branch_state(original, write_paths=("params",)).state

        deleted = merge_parallel_outcomes(
            original,
            {"delete": _ok_outcome(delete_branch)},
            {"delete": ["params"]},
        )
        set_null = merge_parallel_outcomes(
            original,
            {"null": _ok_outcome(null_branch)},
            {"null": ["params"]},
        )
        untouched = merge_parallel_outcomes(
            original,
            {"none": _ok_outcome(no_write_branch)},
            {"none": ["params"]},
        )

        assert "stale" not in deleted.state.params
        assert deleted.state.params["keep"] == 2
        assert set_null.state.params["stale"] is None
        assert untouched.state.params == {"stale": 1, "keep": 2}

    # Production mutation caught: evidence/index roots must reject physical
    # deletion instead of silently treating it as an omitted output key.
    def test_replay_rejects_deletion_from_protected_index(self, base_state):
        original = base_state.model_copy(update={"artifacts_index": {"evidence": "ref"}})
        branch = branch_state(original, write_paths=("artifacts_index",)).state
        del branch.artifacts_index["evidence"]

        with pytest.raises(ValueError, match="deletion forbidden"):
            merge_parallel_outcomes(
                original,
                {"node_a": _ok_outcome(branch)},
                {"node_a": ["artifacts_index"]},
            )

    # Production mutation caught: scalar/ref paths must replay through both
    # parallel merge and an explicit same-value declared write.
    def test_replay_replays_top_level_ref_and_same_value_write(self, base_state):
        previous_ref = _artifact_ref("a")
        next_ref = _artifact_ref("b")
        source = base_state.model_copy(update={"preflight_report_ref": previous_ref})

        changed_branch = branch_state(source, write_paths=("preflight_report_ref",))
        changed_branch.state.preflight_report_ref = next_ref
        changed_result = merge_parallel_outcomes(
            base_state.model_copy(update={"preflight_report_ref": None}),
            {"node_a": _ok_outcome(changed_branch.state)},
            {"node_a": ["preflight_report_ref"]},
        )

        same_value_branch = branch_state(source, write_paths=("preflight_report_ref",))
        same_value_branch.state.preflight_report_ref = previous_ref
        same_value_result = merge_parallel_outcomes(
            base_state.model_copy(update={"preflight_report_ref": None}),
            {"node_a": _ok_outcome(same_value_branch.state)},
            {"node_a": ["preflight_report_ref"]},
        )

        assert changed_result.state.preflight_report_ref == next_ref
        assert same_value_result.state.preflight_report_ref == previous_ref

    # Production mutation caught: merge must retain journal order when a child
    # write is followed by deleting its parent.
    def test_replay_preserves_child_set_then_parent_delete_order(self, base_state):
        source = base_state.model_copy(update={"params": {"cfg": {"x": 1}}})
        branch = branch_state(source, write_paths=("params",)).state
        branch.params["cfg"]["x"] = 2
        del branch.params["cfg"]

        result = merge_parallel_outcomes(
            source,
            {"node_a": _ok_outcome(branch)},
            {"node_a": ["params"]},
        )

        assert "cfg" not in result.state.params

    # Production mutation caught: merge must retain journal order when a parent
    # replacement is followed by deleting one of its children.
    def test_replay_preserves_parent_set_then_child_delete_order(self, base_state):
        source = base_state.model_copy(update={"params": {"cfg": {"x": 1}}})
        branch = branch_state(source, write_paths=("params",)).state
        branch.params["cfg"] = {"x": 2, "y": 3}
        del branch.params["cfg"]["x"]

        result = merge_parallel_outcomes(
            source,
            {"node_a": _ok_outcome(branch)},
            {"node_a": ["params"]},
        )

        assert result.state.params["cfg"] == {"y": 3}

    # Production mutation caught: overlapping parent/child declarations must
    # select one journal operation rather than applying the append twice.
    def test_replay_deduplicates_overlapping_write_specs(self, base_state):
        source = base_state.model_copy(update={"params": {"items": []}})
        branch = branch_state(source, write_paths=("params",)).state
        branch.params["items"].append("x")

        result = merge_parallel_outcomes(
            source,
            {"node_a": _ok_outcome(branch)},
            {"node_a": ["params", "params.items"]},
        )

        assert result.state.params["items"] == ["x"]

    # Production mutation caught: invalid replay targets must become a typed
    # cache-incompatible result, never a silent no-op or a raw IndexError.
    @pytest.mark.parametrize(
        "current_params",
        [{}, {"items": {}}, {"items": []}, {"items": ["only"]}],
    )
    def test_replay_invalid_container_or_index_fails_closed(
        self,
        base_state,
        current_params,
    ):
        source = base_state.model_copy(update={"params": {"items": ["cached", "removed"]}})
        branch = branch_state(source, write_paths=("params.items",)).state
        branch.params["items"].pop(1)
        current = base_state.model_copy(update={"params": current_params})

        try:
            result = merge_parallel_outcomes(
                current,
                {"node_a": _ok_outcome(branch)},
                {"node_a": ["params.items"]},
            )
        except Exception as exc:  # noqa: BLE001 - assert the typed boundary contract.
            assert exc.__class__.__name__ == "StateReplayIncompatible"
        else:
            assert result.applied is False
            assert result.state is current
            assert any("replay_incompatible" in item for item in result.conflicts)
