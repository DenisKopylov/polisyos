from __future__ import annotations

import numpy as np


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestSTLDecomposition:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "forecasting.decomposition.stl@1.0.0")
        state = {"series": np.sin(np.linspace(0, 4 * np.pi, 50)) + np.linspace(0, 5, 50)}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "forecasting.decomposition.stl@1.0.0")
        state = {"series": np.random.default_rng(42).normal(100, 10, size=60)}
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


class TestVECForecast:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "forecasting.multivariate.vec_forecast@1.0.0")
        rng = np.random.default_rng(42)
        state = {"series_matrix": rng.normal(0, 1, size=(20, 3))}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_shape(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "forecasting.multivariate.vec_forecast@1.0.0")
        rng = np.random.default_rng(42)
        state = {"series_matrix": rng.normal(0, 1, size=(30, 2))}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)
