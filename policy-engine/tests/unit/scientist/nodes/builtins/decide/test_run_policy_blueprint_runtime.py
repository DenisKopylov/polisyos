from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import pytest

from polisyos.core.artifacts import ArtifactStore
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    RunPolicyBlueprintRuntimeNode,
    _PolicyRuntimeWorkflowEngine,
    _resolve_replay_bundle_ref,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def test_canonical_node_keeps_non_policy_skip_behavior() -> None:
    state = ExperimentState(run_id="runtime-decomposition-skip", params={"policy_mode": False})

    outcome = RunPolicyBlueprintRuntimeNode().execute(cast("ExecutionContext", None), state)

    assert RunPolicyBlueprintRuntimeNode.__module__ == (
        "polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime"
    )
    assert _PolicyRuntimeWorkflowEngine.__module__ == RunPolicyBlueprintRuntimeNode.__module__
    assert _resolve_replay_bundle_ref.__module__ == RunPolicyBlueprintRuntimeNode.__module__
    assert outcome.status == "skip"
    assert outcome.state is state


class _StringRootStore:
    """Transparent store proxy with an invalid backing-root value."""

    def __init__(self, target: Any) -> None:
        self._target = target

    @property
    def root(self) -> str:
        return "not-a-path"

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


def test_policy_runtime_node_rejects_string_root_before_resolving_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "run_invalid_registry_root"
    store = FileSystemCAS(tmp_path / run_id)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=cast("ArtifactStore", _StringRootStore(store)),
        run=run,
        logger=logging.getLogger(f"test.{run_id}"),
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "resolve_policy_runtime_request",
        lambda *_args: pytest.fail("invalid root must refuse before input resolution"),
    )

    with pytest.raises(ValueError, match="policy_runtime_registry_root_unavailable"):
        RunPolicyBlueprintRuntimeNode().execute(
            ctx,
            ExperimentState(run_id=run_id, params={"policy_mode": True}),
        )
