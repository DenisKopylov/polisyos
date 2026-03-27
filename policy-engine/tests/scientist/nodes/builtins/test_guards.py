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


def _make_state(**artifacts: ArtifactRef) -> ExperimentState:
    return ExperimentState(
        run_id="test_run",
        artifacts_index=dict(artifacts),
        params={},
    )


class TestPreCheck:
    def test_pass_when_reads_present(self):
        spec = _make_spec(reads=["causal_graph"])
        state = _make_state(causal_graph=_ref("cg"))
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
        before = _make_state(key1=_ref("a"))
        after = _make_state(key1=_ref("a"))
        guard = StateMutationGuard(spec)
        guard.post_check(before, after)

    def test_declared_write_ok(self):
        spec = _make_spec(writes=["new_key"])
        before = _make_state(key1=_ref("a"))
        after = _make_state(key1=_ref("a"), new_key=_ref("b"))
        guard = StateMutationGuard(spec)
        guard.post_check(before, after)

    def test_undeclared_write_raises(self):
        spec = _make_spec(writes=[])
        before = _make_state(key1=_ref("a"))
        after = _make_state(key1=_ref("a"), surprise=_ref("x"))
        guard = StateMutationGuard(spec)
        with pytest.raises(StateMutationViolation, match="undeclared"):
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
