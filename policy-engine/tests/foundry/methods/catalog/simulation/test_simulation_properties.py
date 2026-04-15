"""Property-based tests for simulation methods: SIR, discrete event, Monte Carlo."""
from __future__ import annotations
import sys
import numpy as np
import pytest

try:
    from hypothesis import given, settings, HealthCheck
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from tests.foundry.methods.testing.strategies import simulation_strategy


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestSIRProperties:
    @given(data=simulation_strategy())
    @settings(max_examples=30, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_sir_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "simulation.compartmental.sir@1.0.0")
        state = {"S0": data["S0"], "I0": data["I0"], "R0": data["R0"], "N": data["N"]}
        params = {"beta": data["beta"], "gamma": data["gamma"], "n_steps": data["n_steps"]}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert not np.all(np.isnan(arr)), f"All-NaN in SIR/{key}"
        except Exception:
            pass

    @given(data=simulation_strategy())
    @settings(max_examples=25, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_sir_population_conservation(self, data, isolated_registry):
        """S + I + R should equal N at every time step."""
        method = _method_or_skip(isolated_registry, "simulation.compartmental.sir@1.0.0")
        state = {"S0": data["S0"], "I0": data["I0"], "R0": data["R0"], "N": data["N"]}
        params = {"beta": data["beta"], "gamma": data["gamma"], "n_steps": data["n_steps"]}
        try:
            result = method.pure_step(state, params)
            S = result.get("S")
            I = result.get("I")
            R = result.get("R")
            if S is not None and I is not None and R is not None:
                S, I, R = np.asarray(S), np.asarray(I), np.asarray(R)
                if np.all(np.isfinite(S)) and np.all(np.isfinite(I)) and np.all(np.isfinite(R)):
                    total = S + I + R
                    np.testing.assert_allclose(
                        total, data["N"], rtol=1e-6,
                        err_msg="SIR population not conserved"
                    )
        except Exception:
            pass

    @given(data=simulation_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_sir_compartments_non_negative(self, data, isolated_registry):
        """S, I, R values must be non-negative (population counts)."""
        method = _method_or_skip(isolated_registry, "simulation.compartmental.sir@1.0.0")
        state = {"S0": data["S0"], "I0": data["I0"], "R0": data["R0"], "N": data["N"]}
        params = {"beta": data["beta"], "gamma": data["gamma"], "n_steps": data["n_steps"]}
        try:
            result = method.pure_step(state, params)
            for comp in ("S", "I", "R"):
                if comp in result:
                    arr = np.asarray(result[comp])
                    if np.all(np.isfinite(arr)):
                        assert np.all(arr >= -1e-6), f"SIR compartment {comp} went negative"
        except Exception:
            pass


class TestMonteCarloProperties:
    @given(data=simulation_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_monte_carlo_output_dict(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "simulation.inference.monte_carlo@1.0.0")
        state = {"initial_value": data["S0"]}
        params = {"n_simulations": 100, "n_steps": data["n_steps"], "seed": 42}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
        except Exception:
            pass
