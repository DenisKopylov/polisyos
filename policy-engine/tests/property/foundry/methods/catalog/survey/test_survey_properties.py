"""Property-based tests for survey estimation methods."""

from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, given, settings

from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import survey_strategy


def _run(registry, dispatcher, fqn, state, params=None):
    return invoke_property_method(
        dispatcher=dispatcher,
        method_class=registry.get(fqn),
        state=state,
        bound_inputs=state,
        params=params or {},
        seed=17,
    ).output


def _ht_mean_rounding_bound(values: np.ndarray, weights: np.ndarray) -> float:
    """Bound binary64 error for the positive-weight HT mean calculation."""
    unit_roundoff = np.finfo(np.float64).eps / 2.0
    n_terms = values.size
    gamma_n = (n_terms * unit_roundoff) / (1.0 - n_terms * unit_roundoff)
    gamma_n_plus_one = ((n_terms + 1) * unit_roundoff) / (
        1.0 - (n_terms + 1) * unit_roundoff
    )
    upper_ratio = (1.0 + gamma_n_plus_one) * (1.0 + unit_roundoff) / (1.0 - gamma_n)
    lower_ratio = (1.0 - gamma_n_plus_one) * (1.0 - unit_roundoff) / (1.0 + gamma_n)
    relative_roundoff = max(upper_ratio - 1.0, 1.0 - lower_ratio)
    value_scale = float(np.max(np.abs(values)))
    if value_scale == 0.0:
        return 0.0

    # Round each half-ULP budget upward to representable minimum-subnormal quanta:
    # n products plus n-1 numerator additions fit within n quanta; division gets one.
    smallest_subnormal = float(np.nextafter(np.float64(0.0), np.float64(1.0)))
    numerator_underflow = n_terms * smallest_subnormal
    denominator = max(float(np.sum(weights)), 1e-12)
    absolute_underflow = (
        (1.0 + unit_roundoff) * numerator_underflow / denominator + smallest_subnormal
    )
    return value_scale * relative_roundoff + absolute_underflow


def _raking_inputs(data):
    weights = np.asarray(data["weights"], dtype=float)
    strata = np.asarray(data["strata_id"], dtype=int)
    strata_matrix = np.eye(int(data["n_strata"]), dtype=float)[strata]
    parity_matrix = np.eye(2, dtype=float)[np.arange(weights.size) % 2]
    categories = np.column_stack((strata_matrix, parity_matrix))
    strata_targets = strata_matrix.T @ weights
    parity_targets = parity_matrix.T @ weights
    transfer = 0.1 * float(np.min(parity_targets))
    targets = np.concatenate(
        (strata_targets, parity_targets + np.array([transfer, -transfer], dtype=float))
    )
    return {
        "sample_weights": weights,
        "category_matrix": categories,
        "target_totals": targets,
    }, targets


class TestHorvitzThompsonProperties:
    @given(data=survey_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_ht_output_finite(self, data, isolated_registry, property_method_dispatcher):
        values = np.asarray(data["outcome"], dtype=float)
        inclusion = 1.0 / (1.0 + np.asarray(data["weights"], dtype=float))
        state = {"values": values, "inclusion_probabilities": inclusion}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "survey.weighting.horvitz_thompson@1.0.0",
            state,
        )["result"]
        weights = np.asarray(result["weights"], dtype=float)
        assert weights.shape == values.shape
        assert np.all(np.isfinite(weights))
        assert np.isfinite(float(result["total_estimate"]))
        assert np.isfinite(float(result["mean_estimate"]))

    @given(data=survey_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_ht_estimate_not_nan(self, data, isolated_registry, property_method_dispatcher):
        values = np.asarray(data["outcome"], dtype=float)
        state = {
            "values": values,
            "inclusion_probabilities": 1.0 / (1.0 + np.asarray(data["weights"], dtype=float)),
        }
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "survey.weighting.horvitz_thompson@1.0.0",
            state,
        )["result"]
        estimate = float(result["mean_estimate"])
        weights = np.asarray(result["weights"], dtype=np.float64)
        assert np.isfinite(estimate)
        assert weights.shape == values.shape
        assert np.all(np.isfinite(weights))
        assert np.all(weights > 0.0)

        rounding_bound = _ht_mean_rounding_bound(values, weights)
        lower = float(np.min(values)) - rounding_bound
        upper = float(np.max(values)) + rounding_bound
        assert lower <= estimate <= upper

    def test_ht_smallest_subnormal_rounding_is_within_bound(
        self, isolated_registry, property_method_dispatcher
    ):
        smallest_subnormal = float(np.nextafter(np.float64(0.0), np.float64(1.0)))
        values = np.zeros(20, dtype=np.float64)
        values[0] = smallest_subnormal
        inclusion = np.full(values.shape, 2.0 / 3.0, dtype=np.float64)
        state = {"values": values, "inclusion_probabilities": inclusion}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "survey.weighting.horvitz_thompson@1.0.0",
            state,
        )["result"]
        weights = np.asarray(result["weights"], dtype=np.float64)
        estimate = float(result["mean_estimate"])

        assert np.all(np.isfinite(weights))
        assert np.all(weights > 0.0)
        assert np.isfinite(estimate)
        rounding_bound = _ht_mean_rounding_bound(values, weights)
        lower = float(np.min(values)) - rounding_bound
        upper = float(np.max(values)) + rounding_bound
        assert lower <= estimate <= upper
        # This sparse case's exact mean is below half a subnormal ULP; zero is valid.
        assert estimate == 0.0
        assert lower <= 0.0 <= upper

    def test_ht_subnormal_signal_rejects_zero_estimate(
        self, isolated_registry, property_method_dispatcher
    ):
        outcome = 1e-310
        values = np.full(20, outcome, dtype=np.float64)
        inclusion = np.full(values.shape, 2.0 / 3.0, dtype=np.float64)
        state = {"values": values, "inclusion_probabilities": inclusion}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "survey.weighting.horvitz_thompson@1.0.0",
            state,
        )["result"]
        weights = np.asarray(result["weights"], dtype=np.float64)
        estimate = float(result["mean_estimate"])

        assert np.all(np.isfinite(weights))
        assert np.all(weights > 0.0)
        assert np.isfinite(estimate)
        rounding_bound = _ht_mean_rounding_bound(values, weights)
        lower = outcome - rounding_bound
        upper = outcome + rounding_bound
        assert lower <= estimate <= upper
        assert estimate > 0.0
        assert not lower <= 0.0 <= upper

    @given(data=survey_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_ht_deterministic(self, data, isolated_registry, property_method_dispatcher):
        values = np.asarray(data["outcome"], dtype=float)
        state = {
            "values": values,
            "inclusion_probabilities": 1.0 / (1.0 + np.asarray(data["weights"], dtype=float)),
        }
        fqn = "survey.weighting.horvitz_thompson@1.0.0"
        first = _run(isolated_registry, property_method_dispatcher, fqn, state)["result"]
        second = _run(isolated_registry, property_method_dispatcher, fqn, state)["result"]
        assert first["total_estimate"] == second["total_estimate"]
        assert first["mean_estimate"] == second["mean_estimate"]
        np.testing.assert_array_equal(first["weights"], second["weights"])


class TestRakingProperties:
    @given(data=survey_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_raking_output_dict(self, data, isolated_registry, property_method_dispatcher):
        state, target = _raking_inputs(data)
        result = _run(
            isolated_registry, property_method_dispatcher, "survey.weighting.raking@1.0.0", state
        )["result"]
        calibrated = np.asarray(result["calibrated_weights"], dtype=float)
        assert result["converged"] is True
        assert np.all(np.isfinite(calibrated))
        assert np.all(calibrated > 0.0)
        assert not np.allclose(calibrated, state["sample_weights"])
        n_strata = int(data["n_strata"])
        parity_matrix = np.eye(2, dtype=float)[np.arange(calibrated.size) % 2]
        base_parity_totals = parity_matrix.T @ state["sample_weights"]
        assert not np.allclose(target[n_strata:], base_parity_totals)
        achieved = np.asarray(result["achieved_totals"], dtype=float)
        np.testing.assert_allclose(achieved[:n_strata], target[:n_strata], atol=1e-6)
        np.testing.assert_allclose(achieved[n_strata:], target[n_strata:], atol=1e-6)
