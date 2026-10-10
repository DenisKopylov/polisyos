"""Property-based tests for SIR simulation and Monte Carlo summary methods."""

from __future__ import annotations

import sys

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import simulation_strategy


def _assert_sir_population_conservation(trajectory: np.ndarray, population: float) -> None:
    assert trajectory.ndim == 2 and trajectory.shape[1] == 3
    np.testing.assert_allclose(
        trajectory.sum(axis=1), population, rtol=1e-6, err_msg="SIR population not conserved"
    )


class TestSIRProperties:
    @given(data=simulation_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sir_output_finite(self, data, isolated_registry, property_method_dispatcher):
        method = isolated_registry.get("simulation.compartmental.sir@1.0.0")
        state = {"susceptible": data["S0"], "infected": data["I0"], "recovered": data["R0"]}
        params = {"beta": data["beta"], "gamma": data["gamma"], "n_steps": data["n_steps"]}
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params=params,
            seed=42,
        )
        output = result.output["result"]
        trajectory = np.asarray(output["trajectory"], dtype=float)
        final_state = np.asarray(list(output["final_state"].values()), dtype=float)
        assert trajectory.shape == (data["n_steps"], 3)
        assert np.isfinite(trajectory).all()
        assert np.isfinite(final_state).all()
        assert np.isfinite(output["peak_infected"])

    @given(data=simulation_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sir_population_conservation(self, data, isolated_registry, property_method_dispatcher):
        """S + I + R should equal N at every emitted time step."""
        method = isolated_registry.get("simulation.compartmental.sir@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"susceptible": data["S0"], "infected": data["I0"], "recovered": data["R0"]},
            params={"beta": data["beta"], "gamma": data["gamma"], "n_steps": data["n_steps"]},
            seed=42,
        )
        trajectory = np.asarray(result.output["result"]["trajectory"], dtype=float)
        _assert_sir_population_conservation(trajectory, data["N"])

    @given(data=simulation_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sir_compartments_non_negative(self, data, isolated_registry, property_method_dispatcher):
        """Emitted S, I, R population counts must be non-negative."""
        method = isolated_registry.get("simulation.compartmental.sir@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"susceptible": data["S0"], "infected": data["I0"], "recovered": data["R0"]},
            params={"beta": data["beta"], "gamma": data["gamma"], "n_steps": data["n_steps"]},
            seed=42,
        )
        trajectory = np.asarray(result.output["result"]["trajectory"], dtype=float)
        assert trajectory.shape == (data["n_steps"], 3)
        assert np.all(trajectory >= -1e-6)

    def test_population_property_detects_corrupted_interior_step(self):
        trajectory = np.asarray([[90.0, 8.0, 2.0], [89.0, 8.0, 3.0], [88.0, 8.0, 4.0]])
        corrupted = trajectory.copy()
        corrupted[1, 0] += 1.0

        with pytest.raises(AssertionError, match="SIR population not conserved"):
            _assert_sir_population_conservation(corrupted, 100.0)


class TestMonteCarloProperties:
    @given(data=simulation_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_monte_carlo_summarizes_seeded_sir_run_outcomes(
        self, data, isolated_registry, property_method_dispatcher
    ):
        """Summarize fixed-horizon outcomes across a declared toy prior.

        The seeded prior varies initial infected counts; it is not a physical
        population claim or a calibration posterior.
        """
        replicate_count = 8
        output_count = 3
        population = int(data["N"])
        prior_seed = 20261010
        prior_rng = np.random.default_rng(prior_seed)
        initial_infections = prior_rng.integers(
            1, population // 10 + 1, size=replicate_count
        )
        sir = isolated_registry.get("simulation.compartmental.sir@1.0.0")
        terminal_states = []
        first_trajectory = None
        for run_index, infected0 in enumerate(initial_infections):
            simulation = invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=sir,
                state={
                    "susceptible": float(population - infected0),
                    "infected": float(infected0),
                    "recovered": 0.0,
                },
                params={
                    "beta": data["beta"],
                    "gamma": data["gamma"],
                    "n_steps": data["n_steps"],
                },
                seed=prior_seed + run_index,
            )
            trajectory = np.asarray(
                simulation.output["result"]["trajectory"], dtype=float
            )
            assert trajectory.shape == (data["n_steps"], output_count)
            if first_trajectory is None:
                first_trajectory = trajectory
            terminal_states.append(trajectory[-1])

        samples = np.stack(terminal_states, axis=0)
        assert samples.shape == (replicate_count, output_count)
        with pytest.raises(AssertionError, match="one final SIR outcome per prior draw"):
            assert first_trajectory.shape == (replicate_count, output_count), (
                "expected one final SIR outcome per prior draw"
            )

        method = isolated_registry.get("simulation.inference.monte_carlo@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"samples": samples},
            params={"confidence_level": 0.95},
            seed=prior_seed,
        )
        summary = result.output["result"]
        assert summary["n_simulations"] == replicate_count
        assert len(summary["means"]) == output_count
        lower = np.asarray(summary["ci_lower"], dtype=float)
        upper = np.asarray(summary["ci_upper"], dtype=float)
        assert lower.shape == upper.shape == (output_count,)
        assert np.isfinite(lower).all() and np.isfinite(upper).all()
        assert np.all(lower <= upper)
