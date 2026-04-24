from __future__ import annotations

from polisyos.foundry.methods.catalog.policy import ensure_policy_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_policy_methods_queryable():
    MethodRegistry.reset_instance()
    ensure_policy_methods_registered()
    registry = MethodRegistry.get_instance()

    welfare_names = {sig.name for sig in registry.query(namespace="policy.welfare")}
    assert welfare_names.issuperset(
        {
            "cost_benefit_analysis",
            "cost_effectiveness",
            "utilitarian_swf",
            "rawlsian_swf",
            "atkinson_swf",
            "sen_capability",
            "sufficient_statistics_welfare",
        }
    )

    evaluation_names = {sig.name for sig in registry.query(namespace="policy.evaluation")}
    assert evaluation_names.issuperset(
        {
            "budget_impact",
            "scorecard",
            "ex_ante_simulation",
            "foundation_model_policy_analysis",
        }
    )

    macro_names = {sig.name for sig in registry.query(namespace="policy.macro")}
    assert macro_names == {"fiscal_multiplier", "krusell_smith_lite"}

    public_finance_names = {sig.name for sig in registry.query(namespace="policy.public_finance")}
    assert public_finance_names == {"optimal_linear_tax"}

    agent_sim_names = {sig.name for sig in registry.query(namespace="policy.agent_sim")}
    assert agent_sim_names == {"mean_field_equilibrium"}

    mcda_names = {sig.name for sig in registry.query(namespace="policy.mcda")}
    assert mcda_names == {
        "topsis",
        "ahp",
        "electre",
        "rank_stability",
        "robust_topsis",
        "robust_ahp",
        "robust_electre",
    }
