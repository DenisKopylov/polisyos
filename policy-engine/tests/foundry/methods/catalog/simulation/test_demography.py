from __future__ import annotations

import numpy as np


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _passing_microsim_gate() -> dict[str, object]:
    return {
        "decision": "pass",
        "can_run_microsim": True,
        "compatibility_status": "compatible",
        "blocking_reasons": [],
    }


class TestStaticAgingSimulation:
    def test_deterministic_static_aging_matches_targets(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "simulation.demography.static_aging@1.0.0",
        )
        state = {
            "base_weights": np.array([3.0, 2.0], dtype=float),
            "origin_state_index": np.array([0, 1], dtype=int),
            "target_state_totals": np.array([2.0, 2.0, 1.0], dtype=float),
            "transition_prior_matrix": np.array(
                [
                    [0.8, 0.2, 0.0],
                    [0.0, 0.6, 0.4],
                ],
                dtype=float,
            ),
            "microsim_calibration_report": _passing_microsim_gate(),
        }

        result = method.pure_step(state, {"mode": "deterministic", "tolerance": 1e-10})["result"]

        assert np.allclose(result.aged_state_totals, np.array([2.0, 2.0, 1.0]))
        assert np.allclose(result.transition_matrix.sum(axis=1), np.array([3.0, 2.0]))
        assert result.diagnostics["mode"] == "deterministic"
        assert result.stochastic_draws == []

    def test_static_aging_scales_donor_pool_for_entrants(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "simulation.demography.static_aging@1.0.0",
        )
        state = {
            "base_weights": np.array([2.0, 2.0], dtype=float),
            "exit_weights": np.array([1.0, 0.0], dtype=float),
            "origin_state_index": np.array([0, 1], dtype=int),
            "target_state_totals": np.array([1.0, 3.0], dtype=float),
            "entrant_state_totals": np.array([0.0, 1.0], dtype=float),
            "transition_prior_matrix": np.array(
                [
                    [1.0, 0.0],
                    [0.0, 1.0],
                ],
                dtype=float,
            ),
            "donor_weights": np.array([0.25, 0.75], dtype=float),
            "donor_state_index": np.array([1, 1], dtype=int),
            "donor_record_index": np.array([10, 11], dtype=int),
            "microsim_calibration_report": _passing_microsim_gate(),
        }

        result = method.pure_step(state, {"mode": "deterministic", "tolerance": 1e-10})["result"]

        assert np.allclose(result.entrant_weights.sum(), 1.0)
        assert np.array_equal(result.entrant_record_index, np.array([10, 11]))
        assert np.allclose(result.aged_state_totals, np.array([1.0, 3.0]))

    def test_integerized_mode_emits_discrete_draw(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "simulation.demography.static_aging@1.0.0",
        )
        state = {
            "base_weights": np.array([2.4, 1.6], dtype=float),
            "origin_state_index": np.array([0, 1], dtype=int),
            "target_state_totals": np.array([2.0, 2.0], dtype=float),
            "transition_prior_matrix": np.array(
                [
                    [0.7, 0.3],
                    [0.2, 0.8],
                ],
                dtype=float,
            ),
            "microsim_calibration_report": _passing_microsim_gate(),
        }

        result = method.pure_step(
            state,
            {
                "mode": "integerized",
                "seed": 7,
                "unit_weight": 1.0,
                "tolerance": 1e-10,
            },
        )["result"]

        assert len(result.stochastic_draws) == 1
        draw = result.stochastic_draws[0]
        assert all(float(weight).is_integer() for weight in draw["survivor_weights"])
        assert np.isclose(sum(draw["state_totals"]), round(sum(state["base_weights"])))

    def test_static_aging_refuses_uncertified_weights(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "simulation.demography.static_aging@1.0.0",
        )
        state = {
            "base_weights": np.array([3.0, 2.0], dtype=float),
            "origin_state_index": np.array([0, 1], dtype=int),
            "target_state_totals": np.array([2.0, 2.0, 1.0], dtype=float),
            "transition_prior_matrix": np.array(
                [
                    [0.8, 0.2, 0.0],
                    [0.0, 0.6, 0.4],
                ],
                dtype=float,
            ),
        }

        try:
            method.pure_step(state, {"mode": "deterministic", "tolerance": 1e-10})
        except ValueError as exc:
            assert "requires microsim_calibration_report" in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("static_aging should refuse uncertified weights")
