from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.foundry.methods.registry import MethodRegistry


def test_parallel_trends_check_runs() -> None:
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    rng = np.random.default_rng(41)
    outcome = np.vstack([np.linspace(1.0, 3.5, 8) + rng.normal(scale=0.08, size=8) for _ in range(8)])
    outcome[4:, 4:] += 0.5
    state = PanelObservationalData(
        outcome=outcome,
        treatment=np.array([0, 0, 0, 0, 1, 1, 1, 1]),
        time_treatment=4,
        treatment_timing=np.array([-1, -1, -1, -1, 4, 4, 4, 4]),
    )

    method_cls = registry.get("causal.diagnostics.parallel_trends_check@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params={"alpha": 0.05},
        seed=43,
    )

    assert result.output["result"]["test_name"] == "parallel_trends_check"
    assert "p_value" in result.output["result"]
