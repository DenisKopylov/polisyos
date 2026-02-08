from __future__ import annotations

from polisyos.foundry.methods.catalog.optimization import ensure_optimization_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_optimization_methods_queryable() -> None:
    MethodRegistry.reset_instance()
    ensure_optimization_methods_registered()
    registry = MethodRegistry.get_instance()

    signatures = [sig for sig in registry.query() if sig.namespace.startswith("optimization")]
    names = {sig.name for sig in signatures}

    assert names == {"budget_milp", "resource_lp", "leontief_io"}
