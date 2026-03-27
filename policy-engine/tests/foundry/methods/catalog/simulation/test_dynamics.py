from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    ensure_all_methods_registered(registry)
    try:
        return registry.get(fqn)
    except Exception:
        pytest.skip(f"{fqn} not registered")


class TestStockFlow:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.system_dynamics.stock_flow@1.0.0")
        state = {
            "initial_stocks": np.array([100.0, 50.0, 200.0]),
            "flow_matrix": np.array([
                [0.0, 0.1, 0.0],
                [0.05, 0.0, 0.2],
                [0.0, 0.0, 0.0],
            ]),
        }
        result = method.pure_step(state, {"n_steps": 10, "dt": 1.0})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.system_dynamics.stock_flow@1.0.0")
        state = {
            "initial_stocks": np.array([50.0, 50.0]),
            "flow_matrix": np.array([[0.0, 0.1], [0.1, 0.0]]),
            "exogenous_inflows": np.array([5.0, 0.0]),
        }
        result = method.pure_step(state, {"n_steps": 5, "dt": 0.5})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


class TestSIRCompartmental:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.compartmental.sir@1.0.0")
        state = {
            "susceptible": 990.0,
            "infected": 10.0,
            "recovered": 0.0,
        }
        result = method.pure_step(state, {"beta": 0.35, "gamma": 0.1, "n_steps": 30, "dt": 1.0})
        assert isinstance(result, dict)
