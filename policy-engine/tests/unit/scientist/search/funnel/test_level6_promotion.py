"""Actual policy-node positive control for the promotion callback boundary.

The shared harness substitutes external evidence and publication boundaries.
It retains the node, workflow adapter, funnel, Level 6 and inner owner recheck;
its effect recorder establishes ordering, never production publication.
"""

from polisyos.scientist.nodes.builtins.decide import run_policy_blueprint_runtime as runtime
from tests.unit.remediation.test_fun_03 import _install_actual_runtime_node_dependencies


def test_actual_policy_node_normal_path_calls_owner_and_effect_once(tmp_path, monkeypatch):
    harness = _install_actual_runtime_node_dependencies(monkeypatch, tmp_path, mode="normal")
    outcome = runtime.RunPolicyBlueprintRuntimeNode().execute(harness["ctx"], harness["state"])

    assert outcome.status == "ok"
    assert harness["backend_calls"] == ["full"]
    assert harness["runner_calls"] == ["runner"]
    assert harness["owner_checks"] == [True, True]
    assert len(harness["promotion_writes"]) == 1
    assert outcome.state.params["policy_promotion_result"]["decision"] == "complete"
    assert outcome.state.params["_funnel_outcome"]["final_action"] == "complete"
