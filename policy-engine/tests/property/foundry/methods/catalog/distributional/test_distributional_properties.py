"""Property-based tests for distributional / inequality methods."""

from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, given, settings

from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import distribution_strategy


def _run(registry, dispatcher, fqn, state, params=None):
    return invoke_property_method(
        dispatcher=dispatcher,
        method_class=registry.get(fqn),
        state=state,
        bound_inputs=state,
        params=params or {},
        seed=17,
    ).output


class TestGiniProperties:
    @given(data=distribution_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gini_output_finite(self, data, isolated_registry, property_method_dispatcher):
        state = {"values": np.asarray(data["income"], dtype=float)}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "distributional.inequality.lorenz_curve@1.0.0",
            state,
        )["result"]
        population = np.asarray(result["population_share"], dtype=float)
        value_share = np.asarray(result["value_share"], dtype=float)
        assert population.shape == value_share.shape == (len(data["income"]) + 1,)
        assert np.all(np.isfinite(population))
        assert np.all(np.isfinite(value_share))
        assert np.isfinite(float(result["gini"]))

    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gini_in_range(self, data, isolated_registry, property_method_dispatcher):
        """Gini coefficient should be in [0, 1]."""
        state = {"values": np.asarray(data["income"], dtype=float)}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "distributional.inequality.lorenz_curve@1.0.0",
            state,
        )["result"]
        gini = float(result["gini"])
        assert np.isfinite(gini)
        assert 0.0 <= gini <= 1.0

    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gini_deterministic(self, data, isolated_registry, property_method_dispatcher):
        state = {"values": np.asarray(data["income"], dtype=float)}
        fqn = "distributional.inequality.lorenz_curve@1.0.0"
        first = _run(isolated_registry, property_method_dispatcher, fqn, state)["result"]
        second = _run(isolated_registry, property_method_dispatcher, fqn, state)["result"]
        np.testing.assert_array_equal(first["population_share"], second["population_share"])
        np.testing.assert_array_equal(first["value_share"], second["value_share"])
        assert first["gini"] == second["gini"]


class TestFGTPovertyProperties:
    @given(data=distribution_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_fgt_output_finite(self, data, isolated_registry, property_method_dispatcher):
        state = {
            "values": np.asarray(data["income"], dtype=float),
            "poverty_line": float(data["poverty_line"]),
        }
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "distributional.poverty.fgt@1.0.0",
            state,
            {"alpha": 0},
        )["result"]
        assert all(
            np.isfinite(float(result[key]))
            for key in ("fgt", "headcount_ratio", "poverty_gap_index", "poverty_line")
        )

    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_headcount_ratio_in_range(self, data, isolated_registry, property_method_dispatcher):
        """FGT(0) equals the observed share below the declared poverty line."""
        values = np.asarray(data["income"], dtype=float)
        line = float(data["poverty_line"])
        state = {"values": values, "poverty_line": line}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "distributional.poverty.fgt@1.0.0",
            state,
            {"alpha": 0},
        )["result"]
        headcount = float(result["headcount_ratio"])
        assert np.isfinite(headcount)
        assert 0.0 <= headcount <= 1.0
        expected_headcount = float(np.mean(values < line))
        assert headcount == expected_headcount
        assert float(result["fgt"]) == expected_headcount

    def test_fgt_zero_uses_strict_below_line_mask(
        self, isolated_registry, property_method_dispatcher
    ):
        """FGT(0) counts values strictly below the line, not values at the line."""
        values = np.array([4.0, 9.0, 10.0, 11.0, 12.0], dtype=float)
        line = 10.0
        state = {"values": values, "poverty_line": line}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "distributional.poverty.fgt@1.0.0",
            state,
            {"alpha": 0},
        )["result"]

        expected = float(np.mean(values < line))
        adjacent_inclusive = float(np.mean(values <= line))
        assert expected == 0.4
        assert adjacent_inclusive == 0.6
        assert float(result["headcount_ratio"]) == expected
        assert float(result["fgt"]) == expected
        assert float(result["fgt"]) != adjacent_inclusive

    def test_fgt_zero_is_zero_when_all_values_are_non_poor(
        self, isolated_registry, property_method_dispatcher
    ):
        """An all-non-poor population has FGT(0)=0, including the line-equal unit."""
        values = np.array([10.0, 11.0, 12.0], dtype=float)
        state = {"values": values, "poverty_line": 10.0}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "distributional.poverty.fgt@1.0.0",
            state,
            {"alpha": 0},
        )["result"]

        assert float(result["headcount_ratio"]) == 0.0
        assert float(result["fgt"]) == 0.0
