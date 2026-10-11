
"""Property-based tests for sensitivity analysis methods — Sobol, Morris, specification curve."""

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


def _invoke(
    isolated_registry,
    property_method_dispatcher,
    fqn: str,
    state: dict,
    params: dict,
    *,
    seed: int = 42,
):
    return invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=isolated_registry.get(fqn),
        state=state,
        bound_inputs=state,
        params=params,
        seed=seed,
    ).output


class TestMorrisProperties:
    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_morris_output_finite(self, data, isolated_registry, property_method_dispatcher):
        state = _morris_inputs(data["n_params"])
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            "sensitivity.global.morris@1.0.0",
            state,
            {},
        )
        result = output["result"]
        mu_star = np.asarray(result["mu_star"], dtype=float)
        sigma = np.asarray(result["sigma"], dtype=float)

        assert mu_star.shape == sigma.shape == (data["n_params"],)
        assert np.isfinite(mu_star).all()
        assert np.isfinite(sigma).all()
        np.testing.assert_allclose(mu_star, np.ones(data["n_params"]), atol=1e-12)

    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_morris_mu_star_non_negative(self, data, isolated_registry, property_method_dispatcher):
        """mu* is the mean absolute elementary effect for the supplied OAT path."""
        state = _morris_inputs(data["n_params"])
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            "sensitivity.global.morris@1.0.0",
            state,
            {},
        )
        mu_star = np.asarray(output["result"]["mu_star"], dtype=float)

        assert mu_star.shape == (data["n_params"],)
        assert np.isfinite(mu_star).all()
        assert np.all(mu_star >= 0.0)
        np.testing.assert_allclose(mu_star, np.ones(data["n_params"]), atol=1e-12)


class TestSpecificationCurveProperties:
    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_specification_curve_output_dict(self, data, isolated_registry, property_method_dispatcher):
        estimates = np.asarray(data["Y"], dtype=float)
        state = {
            "estimates": estimates,
            "standard_errors": np.full(estimates.shape, 0.5, dtype=float),
        }
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            "sensitivity.specification.specification_curve@1.0.0",
            state,
            {"significance_level": 0.05},
        )
        result = output["result"]

        assert isinstance(output, dict)
        assert result["n_specifications"] == estimates.size
        np.testing.assert_array_equal(result["sorted_estimates"], np.sort(estimates))
        assert 0.0 <= result["share_significant"] <= 1.0

    @given(data=sensitivity_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_specification_curve_deterministic(self, data, isolated_registry, property_method_dispatcher):
        estimates = np.asarray(data["Y"], dtype=float)
        state = {
            "estimates": estimates,
            "standard_errors": np.full(estimates.shape, 0.5, dtype=float),
        }
        fqn = "sensitivity.specification.specification_curve@1.0.0"
        first = _invoke(
            isolated_registry, property_method_dispatcher, fqn, state, {"significance_level": 0.05}
        )
        second = _invoke(
            isolated_registry, property_method_dispatcher, fqn, state, {"significance_level": 0.05}
        )

        assert first["result"] == second["result"]
