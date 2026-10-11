"""Property-based tests for distributional mobility and polarization methods."""

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


def _class_inputs(income):
    ranks = np.argsort(np.argsort(np.asarray(income), kind="stable"), kind="stable")
    classes = np.minimum(ranks * 5 // len(ranks), 4)
    return {"origin_classes": classes, "destination_classes": (classes + 1) % 5}


class TestTransitionMatrixProperties:
    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_transition_rows_sum_to_one(self, data, isolated_registry, property_method_dispatcher):
        """Each represented origin class has a normalized transition row."""
        state = _class_inputs(data["income"])
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "distributional.mobility.transition_matrix@1.0.0",
            state,
            {"n_classes": 5},
        )["result"]
        matrix = np.asarray(result.point_estimate.transition_matrix, dtype=float)
        assert matrix.shape == (5, 5)
        assert np.all(np.isfinite(matrix))
        np.testing.assert_allclose(matrix.sum(axis=1), 1.0, atol=1e-12)
        assert np.all(np.diag(matrix) == 0.0)
        expected_destinations = (np.arange(5) + 1) % 5
        np.testing.assert_allclose(
            matrix[np.arange(5), expected_destinations], 1.0, atol=1e-12
        )

    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_transition_matrix_non_negative(
        self, data, isolated_registry, property_method_dispatcher
    ):
        """Transition probabilities are non-negative and finite."""
        state = _class_inputs(data["income"])
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "distributional.mobility.transition_matrix@1.0.0",
            state,
            {"n_classes": 5},
        )["result"]
        matrix = np.asarray(result.point_estimate.transition_matrix, dtype=float)
        assert np.all(np.isfinite(matrix))
        assert np.all(matrix >= 0.0)


class TestPolarizationProperties:
    @given(data=distribution_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_esteban_ray_non_negative(self, data, isolated_registry, property_method_dispatcher):
        """Esteban-Ray polarization is non-negative for a finite income vector."""
        state = {"values": np.asarray(data["income"], dtype=float)}
        result = _run(
            isolated_registry,
            property_method_dispatcher,
            "distributional.polarization.esteban_ray@1.0.0",
            state,
            {"alpha": 1.0},
        )["result"]
        polarization = float(result["polarization"])
        assert np.isfinite(polarization)
        assert polarization >= 0.0

    @given(data=distribution_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_esteban_ray_deterministic(self, data, isolated_registry, property_method_dispatcher):
        """Same income vector and parameters yield the same polarization result."""
        state = {"values": np.asarray(data["income"], dtype=float)}
        fqn = "distributional.polarization.esteban_ray@1.0.0"
        first = _run(isolated_registry, property_method_dispatcher, fqn, state, {"alpha": 1.0})[
            "result"
        ]
        second = _run(isolated_registry, property_method_dispatcher, fqn, state, {"alpha": 1.0})[
            "result"
        ]
        assert first["polarization"] == second["polarization"]
        np.testing.assert_array_equal(first["group_means"], second["group_means"])
        np.testing.assert_array_equal(first["group_shares"], second["group_shares"])
