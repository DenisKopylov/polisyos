"""Tests for polisyos.scientist.orchestration.engine.state_merge — parallel outcome merging."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.state_merge import (
    _MISSING,
    MergeConflictPolicy,
    StateReplayIncompatible,
    _get_path,
    _state_paths_may_overlap,
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


def test_model_path_lookup_never_evaluates_undeclared_properties():
    """Declared state reads cannot invoke a model's computed property."""
    calls = []

    class ModelWithProperty(BaseModel):
        value: int = 3

        @property
        def computed(self) -> int:
            calls.append("called")
            return 4

    root = ModelWithProperty()
    assert _get_path(root, ("value",)) == 3
    assert _get_path(root, ("computed",)) is _MISSING
    assert calls == []


def test_branch_isolation_does_not_read_undeclared_state_property():
    calls = []

    class StateWithProperty(ExperimentState):
        @property
        def computed(self) -> int:
            calls.append("called")
            return 4

    branch_state(StateWithProperty(run_id="property"), write_paths=("computed",))
    assert calls == []


def test_state_path_comparison_detects_cross_parent_shared_descendant(base_state):
    shared = {"value": "initial"}
    params = {"left": {"child": shared}, "right": {"child": shared}}
    root = base_state.model_copy(update={"params": params})
    assert _state_paths_may_overlap(
        root, ("params", "left", "child", "value"), ("params", "right", "child", "value")
    )
    assert not _state_paths_may_overlap(
        root, ("params", "left", "other"), ("params", "right", "new")
    )


def test_state_path_comparison_conservatively_limits_large_or_unknown_graphs(base_state):
    root = base_state.model_copy(update={"params": {"large": list(range(10_001)), "other": []}})
    assert _state_paths_may_overlap(root, ("params", "large"), ("params", "other"))
    assert _state_paths_may_overlap(root, ("params", "missing", "child"), ("params", "other"))


def test_declared_list_slots_commit_independently_from_real_journals(base_state):
    """Single-index journal operations stay within their declared slots."""
    source = base_state.model_copy(update={"params": {"items": ["first", "second"]}})
    a = branch_state(source, write_paths=("params.items.0",), enforce_write_scope=True)
    b = branch_state(source, write_paths=("params.items.1",), enforce_write_scope=True)
    a.state.params["items"][0] = "from-a"
    b.state.params["items"][1] = "from-b"

    result = merge_parallel_outcomes(
        source,
        {"a": _ok_outcome(a.state), "b": _ok_outcome(b.state)},
        {"a": ["params.items.0"], "b": ["params.items.1"]},
    )
    assert result.applied is True
    assert result.state.params["items"] == ["from-a", "from-b"]
    assert source.params["items"] == ["first", "second"]


def test_unrestricted_journal_replays_a_declared_list_slot(base_state):
    """Isolate journal selection from the stricter producer admission check."""
    source = base_state.model_copy(update={"params": {"items": ["first", "second"]}})
    branch = branch_state(source, write_paths=("params.items.0",))
    branch.state.params["items"][0] = "from-a"
    result = merge_parallel_outcomes(
        source,
        {"a": _ok_outcome(branch.state)},
        {"a": ["params.items.0"]},
    )
    assert result.applied is True
    assert result.state.params["items"] == ["from-a", "second"]
    assert source.params["items"] == ["first", "second"]


def test_unrestricted_journals_detect_alias_conflict(base_state):
    source = base_state.model_copy(update={"params": {"items": ["original"]}})
    a = branch_state(source, write_paths=("params.items.0",))
    b = branch_state(source, write_paths=("params.items.00",))
    a.state.params["items"][0] = "from-a"
    b.state.params["items"][0] = "from-b"
    result = merge_parallel_outcomes(
        source,
        {"a": _ok_outcome(a.state), "b": _ok_outcome(b.state)},
        {"a": ["params.items.0"], "b": ["params.items.00"]},
    )
    assert result.applied is False
    assert result.state.params["items"] == ["original"]
    assert len(result.conflicts) == 1


@pytest.mark.parametrize("alias", ["00", "+0", "-1"])
def test_equivalent_declared_list_slots_conflict_atomically(base_state, alias):
    source = base_state.model_copy(update={"params": {"items": ["original"]}})
    a = branch_state(source, write_paths=("params.items.0",), enforce_write_scope=True)
    b = branch_state(source, write_paths=(f"params.items.{alias}",), enforce_write_scope=True)
    a.state.params["items"][0] = "from-a"
    b.state.params["items"][0] = "from-b"

    result = merge_parallel_outcomes(
        source,
        {"a": _ok_outcome(a.state), "b": _ok_outcome(b.state)},
        {"a": ["params.items.0"], "b": [f"params.items.{alias}"]},
    )
    assert result.applied is False
    assert result.state.params["items"] == ["original"]
    assert len(result.conflicts) == 1


def test_declared_list_slot_does_not_authorize_structural_mutation(base_state):
    source = base_state.model_copy(update={"params": {"items": ["first", "second"]}})
    branch = branch_state(source, write_paths=("params.items.0",), enforce_write_scope=True)
    with pytest.raises(ValueError, match="undeclared state_writes"):
        del branch.state.params["items"][0]
    assert source.params["items"] == ["first", "second"]


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

    @pytest.mark.parametrize("root", ["inputs", "artifacts_index", "reports_index"])
    @pytest.mark.parametrize("replacement", ["empty", "different"])
    def test_whole_protected_root_replacement_refuses_lost_current_keys_atomically(
        self, base_state, root, replacement
    ):
        """Recorded root sets cannot erase the current base or publish a sibling write."""
        original_ref = _artifact_ref("a")
        current_ref = _artifact_ref("b")
        source = base_state.model_copy(update={root: {"evidence": original_ref}})
        branch = branch_state(source, write_paths=(root, "params"), enforce_write_scope=True)
        branch.state.params["staged"] = "must-not-publish"
        setattr(
            branch.state,
            root,
            {} if replacement == "empty" else {"new": original_ref},
        )
        current = base_state.model_copy(
            update={root: {"evidence": original_ref, "current-only": current_ref}}
        )
        before = current.model_dump(mode="python")

        with pytest.raises(StateReplayIncompatible) as exc:
            merge_parallel_outcomes(
                current,
                {"node_a": _ok_outcome(branch.state)},
                {"node_a": [root, "params"]},
            )

        assert exc.value.path.startswith(f"{root}.")
        assert current.model_dump(mode="python") == before
        assert "staged" not in current.params

    @pytest.mark.parametrize("root", ["inputs", "artifacts_index", "reports_index"])
    def test_whole_protected_root_set_allows_existing_ref_update_and_addition(
        self, base_state, root
    ):
        """Protection is key membership, not a blanket ban on useful root writes."""
        source = base_state.model_copy(update={root: {"evidence": _artifact_ref("a")}})
        branch = branch_state(source, write_paths=(root,), enforce_write_scope=True)
        replacement = {"evidence": _artifact_ref("b"), "new": _artifact_ref("c")}
        setattr(branch.state, root, replacement)

        result = merge_parallel_outcomes(
            source,
            {"node_a": _ok_outcome(branch.state)},
            {"node_a": [root]},
        )

        assert result.applied is True
        assert getattr(result.state, root) == replacement
        assert getattr(source, root)["evidence"] == _artifact_ref("a")
        assert "new" not in getattr(source, root)

    @pytest.mark.parametrize("root", ["inputs", "artifacts_index", "reports_index"])
    def test_unjournaled_non_mapping_protected_root_refuses_without_mutating_base(
        self, base_state, root
    ):
        """Compatibility outcomes cannot substitute a missing protected container."""
        source = base_state.model_copy(update={root: {"evidence": _artifact_ref("a")}})
        invalid = source.model_copy(update={root: None})
        before = source.model_dump(mode="python")

        with pytest.raises(StateReplayIncompatible, match=root):
            merge_parallel_outcomes(source, {"node_a": _ok_outcome(invalid)}, {"node_a": [root]})

        assert source.model_dump(mode="python") == before

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

        with pytest.raises(StateReplayIncompatible):
            merge_parallel_outcomes(
                current,
                {"node_a": _ok_outcome(branch)},
                {"node_a": ["params.items"]},
            )

    # Production mutation caught: a recorded list replacement must validate
    # the current target kind and presence before writing a replacement value.
    @pytest.mark.parametrize("current_params", [{"items": {}}, {}])
    def test_replay_replace_requires_current_list_target(
        self,
        base_state,
        current_params,
    ):
        source = base_state.model_copy(update={"params": {"items": ["b", "a"]}})
        branch = branch_state(source, write_paths=("params.items",)).state
        branch.params["items"].sort()
        current = base_state.model_copy(update={"params": current_params})

        with pytest.raises(StateReplayIncompatible):
            merge_parallel_outcomes(
                current,
                {"node_a": _ok_outcome(branch)},
                {"node_a": ["params.items"]},
            )
