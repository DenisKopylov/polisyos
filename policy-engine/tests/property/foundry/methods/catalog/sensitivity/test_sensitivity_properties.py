"""Property-based tests for global sensitivity analysis methods."""

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
from tests.unit.foundry.methods.testing.strategies import sensitivity_strategy


def _invoke(
    isolated_registry,
    property_method_dispatcher,
    fqn: str,
    state: dict,
    *,
    seed: int = 42,
):
    return invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=isolated_registry.get(fqn),
        state=state,
        bound_inputs=state,
        params={},
        seed=seed,
    ).output


def _sobol_inputs(n_samples: int, n_features: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(2026)
    outputs_a_inputs = rng.uniform(0.0, 1.0, size=(n_samples, n_features))
    outputs_b_inputs = rng.uniform(0.0, 1.0, size=(n_samples, n_features))
    outputs_a = outputs_a_inputs.sum(axis=1)
    outputs_b = outputs_b_inputs.sum(axis=1)
    mixed_outputs = np.empty((n_features, n_samples), dtype=float)
    for feature in range(n_features):
        mixed = outputs_b_inputs.copy()
        mixed[:, feature] = outputs_a_inputs[:, feature]
        mixed_outputs[feature] = mixed.sum(axis=1)
    return {
        "outputs_a": outputs_a,
        "outputs_b": outputs_b,
        "mixed_outputs": mixed_outputs,
    }


def _morris_inputs(n_features: int) -> dict[str, np.ndarray]:
    n_trajectories = 3
    levels = np.empty((n_trajectories, n_features + 1, n_features), dtype=float)
    for trajectory in range(n_trajectories):
        current = np.full(n_features, 0.25, dtype=float)
        levels[trajectory, 0] = current
        for step in range(n_features):
            current = current.copy()
            feature = (step + trajectory) % n_features
            current[feature] = 0.75
            levels[trajectory, step + 1] = current
    return {"parameter_levels": levels, "model_outputs": levels.sum(axis=2)}


class TestSobolIndicesProperties:
    @given(data=sensitivity_strategy())
    @settings(
        max_examples=25,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sobol_output_finite(self, data, isolated_registry, property_method_dispatcher):
        state = _sobol_inputs(max(25, data["n_obs"] // 2), data["n_params"])
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            "sensitivity.global.sobol_first_order@1.0.0",
            state,
        )
        result = output["result"]
        indices = np.asarray(result["first_order_indices"], dtype=float)

        assert np.isfinite(result["variance"]) and result["variance"] > 0.0
        assert indices.shape == (data["n_params"],)
        assert np.isfinite(indices).all()

    @given(data=sensitivity_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sobol_indices_in_range(self, data, isolated_registry, property_method_dispatcher):
        """First-order indices returned for the additive input basis are in [0, 1]."""
        state = _sobol_inputs(max(25, data["n_obs"] // 2), data["n_params"])
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            "sensitivity.global.sobol_first_order@1.0.0",
            state,
        )
        indices = np.asarray(output["result"]["first_order_indices"], dtype=float)

        assert indices.shape == (data["n_params"],)
        assert np.isfinite(indices).all()
        assert np.all(indices >= 0.0)
        assert np.all(indices <= 1.0)

    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_sobol_deterministic(self, data, isolated_registry, property_method_dispatcher):
        state = _sobol_inputs(max(25, data["n_obs"] // 2), data["n_params"])
        fqn = "sensitivity.global.sobol_first_order@1.0.0"
        first = _invoke(isolated_registry, property_method_dispatcher, fqn, state)
        second = _invoke(isolated_registry, property_method_dispatcher, fqn, state)

        assert first["result"] == second["result"]


class TestMorrisScreeningProperties:
    @given(data=sensitivity_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_morris_output_dict(self, data, isolated_registry, property_method_dispatcher):
        state = _morris_inputs(data["n_params"])
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            "sensitivity.global.morris@1.0.0",
            state,
        )
        result = output["result"]

        assert result["n_trajectories"] == 3
        assert result["n_factors"] == data["n_params"]
        assert np.asarray(result["mu_star"], dtype=float).shape == (data["n_params"],)
        np.testing.assert_allclose(result["mu_star"], np.ones(data["n_params"]), atol=1e-12)
