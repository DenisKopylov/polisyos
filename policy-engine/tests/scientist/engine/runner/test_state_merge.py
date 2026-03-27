"""Tests for engine/runner/state_merge.py."""

from __future__ import annotations

import pytest

from polisyos.scientist.engine.runner.serialization import deserialize_state, serialize_state
from polisyos.scientist.engine.runner.state_merge import (
    StateMergeConflictError,
    merge_tier_states,
)
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.state import ExperimentState


def _make_ref(name: str) -> ArtifactRef:
    import hashlib
    sha = "sha256:" + hashlib.sha256(name.encode()).hexdigest()
    return ArtifactRef(artifact_id=sha, kind="test", media_type="application/octet-stream")


def _make_state(**overrides) -> ExperimentState:
    defaults: dict = {
        "run_id": "test-run",
        "schema_version": "1.3",
    }
    defaults.update(overrides)
    return ExperimentState(**defaults)


class TestMergeTierStates:
    def test_empty_results_returns_base(self) -> None:
        base = _make_state()
        base_bytes = serialize_state(base)
        assert merge_tier_states(base_bytes, []) == base_bytes

    def test_single_result_is_identity(self) -> None:
        base = _make_state()
        result = _make_state(params={"key1": "value1"})
        base_bytes = serialize_state(base)
        result_bytes = serialize_state(result)
        merged_bytes = merge_tier_states(base_bytes, [result_bytes])
        assert merged_bytes == result_bytes

    def test_non_conflicting_merge_params(self) -> None:
        base = _make_state()
        r1 = _make_state(params={"a": 1})
        r2 = _make_state(params={"b": 2})

        base_bytes = serialize_state(base)
        merged_bytes = merge_tier_states(
            base_bytes,
            [serialize_state(r1), serialize_state(r2)],
        )
        merged = deserialize_state(merged_bytes)
        assert merged.params["a"] == 1
        assert merged.params["b"] == 2

    def test_conflict_raises_error(self) -> None:
        base = _make_state()
        r1 = _make_state(params={"x": 1})
        r2 = _make_state(params={"x": 2})

        base_bytes = serialize_state(base)
        with pytest.raises(StateMergeConflictError) as exc_info:
            merge_tier_states(
                base_bytes,
                [serialize_state(r1), serialize_state(r2)],
            )
        assert exc_info.value.key == "x"
        assert exc_info.value.field == "params"

    def test_artifacts_index_merge(self) -> None:
        base = _make_state()
        r1 = _make_state()
        r1.artifacts_index["art_a"] = _make_ref("ref_a")
        r2 = _make_state()
        r2.artifacts_index["art_b"] = _make_ref("ref_b")

        base_bytes = serialize_state(base)
        merged_bytes = merge_tier_states(
            base_bytes,
            [serialize_state(r1), serialize_state(r2)],
        )
        merged = deserialize_state(merged_bytes)
        assert "art_a" in merged.artifacts_index
        assert "art_b" in merged.artifacts_index

    def test_same_key_different_results_conflict(self) -> None:
        """If both results modify the same key, conflict is raised."""
        base = _make_state()
        r1 = _make_state(params={"shared": "val1"})
        r2 = _make_state(params={"shared": "val2"})

        base_bytes = serialize_state(base)
        with pytest.raises(StateMergeConflictError):
            merge_tier_states(
                base_bytes,
                [serialize_state(r1), serialize_state(r2)],
            )
