"""Tests for StateMutationGuard."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.protocol import NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.guards import (
    StateMutationGuard,
    StateMutationViolation,
)

_COUNTER = 0


def _ref(name: str = "test") -> ArtifactRef:
    global _COUNTER
    _COUNTER += 1
    # Valid sha256 hex: 64 lowercase hex chars
    hex_id = f"{_COUNTER:064x}"
    return ArtifactRef(artifact_id=f"sha256:{hex_id}", kind="test", media_type="application/json")


def _make_spec(*, reads: list[str] | None = None, writes: list[str] | None = None) -> NodeSpec:
    return NodeSpec.model_construct(
        metadata=MagicMock(),
        state_reads=reads or [],
        state_writes=writes or [],
        produces=[],
    )


def _make_state(
    *,
    params: dict[str, object] | None = None,
    reports: dict[str, ArtifactRef] | None = None,
    inputs: dict[str, ArtifactRef] | None = None,
    **artifacts: ArtifactRef,
) -> ExperimentState:
    return ExperimentState(
        run_id="test_run",
        inputs=dict(inputs or {}),
        artifacts_index=dict(artifacts),
        reports_index=dict(reports or {}),
        params=dict(params or {}),
    )


class TestPreCheck:
    def test_pass_when_reads_present(self):
        spec = _make_spec(reads=["causal_graph", "params.depth"])
        state = _make_state(causal_graph=_ref("cg"), params={"depth": 2})
        guard = StateMutationGuard(spec)
        warnings = guard.pre_check(state)
        assert warnings == []

    def test_warn_when_read_missing(self):
        spec = _make_spec(reads=["causal_graph", "model_spec"])
        state = _make_state(causal_graph=_ref("cg"))
        guard = StateMutationGuard(spec)
        warnings = guard.pre_check(state)
        assert len(warnings) == 1
        assert "model_spec" in warnings[0]


class TestPostCheck:
    def test_no_mutation_ok(self):
        spec = _make_spec(writes=[])
        ref = _ref("a")
        before = _make_state(key1=ref)
        after = _make_state(key1=ref)
        guard = StateMutationGuard(spec)
        guard.post_check(before, after)

    def test_declared_write_ok(self):
        spec = _make_spec(writes=["new_key"])
        ref = _ref("a")
        before = _make_state(key1=ref)
        after = _make_state(key1=ref, new_key=_ref("b"))
        guard = StateMutationGuard(spec)
        guard.post_check(before, after)

    def test_explicit_nested_write_ok(self):
        spec = _make_spec(writes=["params.depth"])
        before = _make_state(params={"depth": 1, "mode": "fast"})
        after = _make_state(params={"depth": 2, "mode": "fast"})
        guard = StateMutationGuard(spec)
        guard.post_check(before, after)

    def test_container_write_covers_nested_write(self):
        spec = _make_spec(writes=["params"])
        before = _make_state(params={"nested": {"score": 1}})
        after = _make_state(params={"nested": {"score": 2}})
        guard = StateMutationGuard(spec)
        guard.post_check(before, after)

    def test_undeclared_write_raises(self):
        spec = _make_spec(writes=[])
        before = _make_state(key1=_ref("a"))
        after = _make_state(key1=_ref("a"), surprise=_ref("x"))
        guard = StateMutationGuard(spec)
        with pytest.raises(StateMutationViolation, match="undeclared"):
            guard.post_check(before, after)

    def test_undeclared_existing_artifact_replacement_raises(self):
        spec = _make_spec(writes=[])
        before = _make_state(key1=_ref("a"))
        after = _make_state(key1=_ref("b"))
        guard = StateMutationGuard(spec)
        with pytest.raises(StateMutationViolation, match="undeclared"):
            guard.post_check(before, after)

    def test_undeclared_param_mutation_raises(self):
        spec = _make_spec(writes=[])
        before = _make_state(params={"depth": 1})
        after = _make_state(params={"depth": 2})
        guard = StateMutationGuard(spec)
        with pytest.raises(StateMutationViolation, match="params.depth"):
            guard.post_check(before, after)

    def test_removed_key_raises(self):
        spec = _make_spec(writes=[])
        before = _make_state(key1=_ref("a"), key2=_ref("b"))
        after = _make_state(key1=_ref("a"))
        guard = StateMutationGuard(spec)
        with pytest.raises(StateMutationViolation, match="removed"):
            guard.post_check(before, after)

    def test_noop_state_ok(self):
        spec = _make_spec(writes=["x"])
        state = _make_state()
        guard = StateMutationGuard(spec)
        guard.post_check(state, state)
