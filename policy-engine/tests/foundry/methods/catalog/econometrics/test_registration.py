from __future__ import annotations

from polisyos.foundry.methods.econometrics import ensure_econometric_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_econometric_methods_queryable() -> None:
    MethodRegistry.reset_instance()
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()

    signatures = [sig for sig in registry.query() if sig.namespace.startswith("econometrics.")]
    names = {sig.name for sig in signatures}

    assert names == {
        "panel_data",
        "instrumental_variables",
        "time_series",
    }
