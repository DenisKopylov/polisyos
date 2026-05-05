from __future__ import annotations

from polisyos.foundry.methods.optimization import ensure_optimization_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_optimization_methods_queryable() -> None:
    MethodRegistry.reset_instance()
    ensure_optimization_methods_registered()
    registry = MethodRegistry.get_instance()

    signatures = [sig for sig in registry.query() if sig.namespace.startswith("optimization")]
    names = {sig.name for sig in signatures}

    assert names == {
        "budget_milp",
        "resource_lp",
        "leontief_io",
        "quadratic_program",
        "robust_optimization",
        "set_based_robust_linear",
        "multiobjective_nsga2",
        "socp",
        "two_stage_stochastic_program",
        "dynamic_programming",
        # Phase 6d additions
        "knapsack",
        "vehicle_routing",
        "nash_equilibrium",
        "bilevel",
        "chance_constrained",
        "moment_constrained",
        "public_reserve_auction",
    }

    fqns = {sig.fqn for sig in signatures}
    assert "optimization.linear.resource_lp@1.0.0" in fqns
    assert "optimization.integer.budget_milp@1.0.0" in fqns
    assert "optimization.io.leontief_io@1.0.0" in fqns
    assert "optimization.dro.moment_constrained@1.0.0" in fqns
    assert "optimization.auction.public_reserve_auction@1.0.0" in fqns


def test_bilevel_registry_backward_compatibility() -> None:
    MethodRegistry.reset_instance()
    ensure_optimization_methods_registered()
    registry = MethodRegistry.get_instance()

    legacy = registry.get("optimization.bilevel.bilevel@1.0.0")
    current = registry.get("optimization.bilevel.bilevel@1.1.0")

    assert legacy.signature.name == "bilevel"
    assert legacy.signature.version == "1.0.0"
    assert current.signature.name == "bilevel"
    assert current.signature.version == "1.1.0"
