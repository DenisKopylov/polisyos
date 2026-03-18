from __future__ import annotations

from polisyos.foundry.methods.catalog.policy import ensure_policy_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_policy_methods_queryable():
    MethodRegistry.reset_instance()
    ensure_policy_methods_registered()
    registry = MethodRegistry.get_instance()

    welfare_names = {sig.name for sig in registry.query(namespace="policy.welfare")}
    assert welfare_names == {
        "cost_benefit_analysis",
        "cost_effectiveness",
        "utilitarian_swf",
        "rawlsian_swf",
        "atkinson_swf",
        "sen_capability",
    }

    evaluation_names = {sig.name for sig in registry.query(namespace="policy.evaluation")}
    assert evaluation_names == {
        "budget_impact",
        "scorecard",
        "ex_ante_simulation",
    }

    mcda_names = {sig.name for sig in registry.query(namespace="policy.mcda")}
    assert mcda_names == {
        "topsis",
        "ahp",
        "electre",
    }
