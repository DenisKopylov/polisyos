from __future__ import annotations

import numpy as np


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestStockFlow:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.system_dynamics.stock_flow@1.0.0")
        state = {
            "initial_stocks": np.array([100.0, 50.0, 200.0]),
            "flow_matrix": np.array(
                [
                    [0.0, 0.1, 0.0],
                    [0.05, 0.0, 0.2],
                    [0.0, 0.0, 0.0],
                ]
            ),
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


class TestCanonicalDynamicalSystems:
    def test_registered(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "simulation.dynamical_systems.canonical@1.0.0",
        )

        assert method is not None

    def test_hopf_emits_limit_cycle_validation_trajectory(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "simulation.dynamical_systems.canonical@1.0.0",
        )

        result = method.pure_step(
            {"initial_state": np.asarray([0.5, 0.0])},
            {"system": "hopf_normal_form", "mu": 0.2, "n_steps": 20, "dt": 0.05},
        )["result"]

        assert result["suggested_attractor_kind"] == "limit_cycle"
        assert result["variable_ids"] == ["x", "y"]
        assert len(result["trajectory"]) == 21

    def test_logistic_map_emits_chaos_validation_trajectory(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "simulation.dynamical_systems.canonical@1.0.0",
        )

        result = method.pure_step(
            {"initial_state": np.asarray([0.12345])},
            {"system": "logistic_map", "r": 4.0, "n_steps": 8},
        )["result"]

        assert result["model_family"] == "discrete_map"
        assert result["suggested_attractor_kind"] == "chaotic"
        assert len(result["trajectory"]) == 9
