from __future__ import annotations

from typing import cast

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
