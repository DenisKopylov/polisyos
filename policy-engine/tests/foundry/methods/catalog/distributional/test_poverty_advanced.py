from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestMultidimensionalPoverty:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.multidimensional@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "deprivation_matrix": rng.integers(0, 2, size=(50, 4)).astype(float),
            "weights": np.array([0.25, 0.25, 0.25, 0.25]),
        }
        result = method.pure_step(state, {"k_threshold": 0.33})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.multidimensional@1.0.0")
        state = {
            "deprivation_matrix": np.array([[1, 0, 1], [0, 0, 0], [1, 1, 1]], dtype=float),
            "weights": np.array([0.4, 0.3, 0.3]),
        }
        result = method.pure_step(state, {"k_threshold": 0.5})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))

    def test_no_deprivation(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.poverty.multidimensional@1.0.0")
        state = {
            "deprivation_matrix": np.zeros((20, 3)),
            "weights": np.array([0.33, 0.34, 0.33]),
        }
        result = method.pure_step(state, {"k_threshold": 0.33})
        assert isinstance(result, dict)
