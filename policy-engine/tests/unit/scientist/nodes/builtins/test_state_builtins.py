"""Regression tests for copy-on-write state builtins."""

from __future__ import annotations

import pytest
from polisyos.scientist.orchestration.engine.builtins.emit_artifact import EmitArtifactNode
from polisyos.scientist.orchestration.engine.builtins.set_state import SetStateNode
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state


def test_set_state_uses_copy_on_write_for_params(
    execution_context,
    minimal_state,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nested = {"items": ["baseline"]}
    state = ExperimentState(run_id=minimal_state.run_id, inputs=minimal_state.inputs)
    state.params = {"nested": nested}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return branch_state(base_state, write_paths=write_paths)

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.builtins.set_state.branch_state",
        _spy_branch,
    )

    outcome = SetStateNode(params={"key": "status", "value": "ready"}).execute(
        execution_context,
        state,
    )

    assert outcome.status == "ok"
    assert observed["write_paths"] == ("params",)
    assert "status" not in state.params
    assert outcome.state.params["status"] == "ready"
    assert outcome.state.params["nested"] == {"items": ["baseline"]}


def test_emit_artifact_uses_copy_on_write_for_artifacts_index(
    execution_context,
    minimal_state,
    artifact_ref_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_ref = artifact_ref_factory(kind="ir.input")
    state = ExperimentState(run_id=minimal_state.run_id, inputs=minimal_state.inputs)
    state.artifacts_index = {"existing": existing_ref}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return branch_state(base_state, write_paths=write_paths)

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.builtins.emit_artifact.branch_state",
        _spy_branch,
    )

    outcome = EmitArtifactNode(params={"key": "emitted", "payload": {"ok": True}}).execute(
        execution_context,
        state,
    )

    assert outcome.status == "ok"
    assert observed["write_paths"] == ("artifacts_index",)
    assert "emitted" not in state.artifacts_index
    assert outcome.state.artifacts_index["existing"] == existing_ref
    assert outcome.state.artifacts_index["emitted"] == outcome.artifacts[0]
