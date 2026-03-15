from __future__ import annotations

from polisyos.foundry.methods.bayesian import ensure_bayesian_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_bayesian_methods_queryable() -> None:
    MethodRegistry.reset_instance()
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()

    signatures = [sig for sig in registry.query() if sig.namespace.startswith("bayesian.")]
    names = {sig.name for sig in signatures}

    assert names == {
        "linear_regression",
        "autoregression",
    }
