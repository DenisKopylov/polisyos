"""Property-based tests for spatial autocorrelation and regression methods."""

from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, assume, given, settings

from polisyos.foundry.methods.catalog.spatial.protocols import SpatialData
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import spatial_data_strategy


def _coordinates(data):
    return np.column_stack(
        (np.asarray(data["lon"], dtype=float), np.asarray(data["lat"], dtype=float))
    )


def _spatial_result(dispatcher, method, state, bound_inputs, params, seed=17):
    return invoke_property_method(
        dispatcher=dispatcher,
        method_class=method,
        state=state,
        bound_inputs=bound_inputs,
        params=params,
        seed=seed,
    ).output["result"]


class TestMoranIProperties:
    @given(data=spatial_data_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_moran_i_output_finite(self, data, isolated_registry, property_method_dispatcher):
        coordinates = _coordinates(data)
        values = np.asarray(data["outcome"], dtype=float)
        weights = np.ones((values.size, values.size), dtype=float) - np.eye(values.size)
        state = SpatialData(coordinates=coordinates, values=values, weights_matrix=weights)
        bound = {"coordinates": coordinates, "values": values, "weights_matrix": weights}
        result = _spatial_result(
            property_method_dispatcher,
            isolated_registry.get("spatial.autocorrelation.moran_i@1.0.0"),
            state,
            bound,
            {"n_permutations": 15},
            seed=41,
        )
        assert np.isfinite(result.statistics["moran_i"])
        assert np.isfinite(result.statistics["p_value"])

    @given(data=spatial_data_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_moran_i_range(self, data, isolated_registry, property_method_dispatcher):
        """Moran's I remains bounded for a symmetric complete spatial graph."""
        coordinates = _coordinates(data)
        values = np.asarray(data["outcome"], dtype=float)
        weights = np.ones((values.size, values.size), dtype=float) - np.eye(values.size)
        state = SpatialData(coordinates=coordinates, values=values, weights_matrix=weights)
        bound = {"coordinates": coordinates, "values": values, "weights_matrix": weights}
        result = _spatial_result(
            property_method_dispatcher,
            isolated_registry.get("spatial.autocorrelation.moran_i@1.0.0"),
            state,
            bound,
            {"n_permutations": 10},
            seed=41,
        )
        statistic = float(result.statistics["moran_i"])
        assert np.isfinite(statistic)
        assert -1.0 <= statistic <= 1.0

    @given(data=spatial_data_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_moran_i_deterministic(self, data, isolated_registry, property_method_dispatcher):
        coordinates = _coordinates(data)
        values = np.asarray(data["outcome"], dtype=float)
        weights = np.ones((values.size, values.size), dtype=float) - np.eye(values.size)
        state = SpatialData(coordinates=coordinates, values=values, weights_matrix=weights)
        bound = {"coordinates": coordinates, "values": values, "weights_matrix": weights}
        method = isolated_registry.get("spatial.autocorrelation.moran_i@1.0.0")
        params = {"n_permutations": 15}
        first = _spatial_result(property_method_dispatcher, method, state, bound, params, seed=41)
        second = _spatial_result(property_method_dispatcher, method, state, bound, params, seed=41)
        assert first.statistics == second.statistics


class TestGWRProperties:
    @given(data=spatial_data_strategy())
    @settings(
        max_examples=15,
        deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gwr_output_dict(self, data, isolated_registry, property_method_dispatcher):
        assume(int(data["n_obs"]) >= 50)
        coordinates = _coordinates(data)
        values = np.asarray(data["outcome"], dtype=float)
        features = np.asarray(data["covariates"], dtype=float)
        state = SpatialData(coordinates=coordinates, values=values, features=features)
        bound = {"coordinates": coordinates, "values": values, "features": features}
        bandwidth = max(float(np.ptp(coordinates, axis=0).max()), 1.0)
        result = _spatial_result(
            property_method_dispatcher,
            isolated_registry.get("spatial.regression.gwr@1.0.0"),
            state,
            bound,
            {"bandwidth": bandwidth},
        )
        assert np.isfinite(result.statistics["rmse"])
        assert np.asarray(result.fitted_values).shape == (int(data["n_obs"]),)

    @given(data=spatial_data_strategy())
    @settings(
        max_examples=10,
        deadline=20000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_gwr_local_coefficients_shape(
        self, data, isolated_registry, property_method_dispatcher
    ):
        assume(int(data["n_obs"]) >= 50)
        coordinates = _coordinates(data)
        values = np.asarray(data["outcome"], dtype=float)
        features = np.asarray(data["covariates"], dtype=float)
        state = SpatialData(coordinates=coordinates, values=values, features=features)
        bound = {"coordinates": coordinates, "values": values, "features": features}
        bandwidth = max(float(np.ptp(coordinates, axis=0).max()), 1.0)
        result = _spatial_result(
            property_method_dispatcher,
            isolated_registry.get("spatial.regression.gwr@1.0.0"),
            state,
            bound,
            {"bandwidth": bandwidth},
        )
        coefficients = np.asarray(result.local_coefficients, dtype=float)
        assert coefficients.shape == (int(data["n_obs"]), features.shape[1] + 1)
        assert np.all(np.isfinite(coefficients))
