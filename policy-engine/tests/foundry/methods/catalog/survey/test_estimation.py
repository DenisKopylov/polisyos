from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestFayHerriot:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.estimation.fay_herriot@1.0.0")
        rng = np.random.default_rng(42)
        n_areas = 20
        state = {
            "y_direct": rng.normal(50, 5, size=n_areas),
            "X": rng.normal(0, 1, size=(n_areas, 3)),
            "sampling_var": np.abs(rng.normal(1, 0.3, size=n_areas)) + 0.1,
        }
        result = method.pure_step(state, {"max_iter": 50})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.estimation.fay_herriot@1.0.0")
        state = {
            "y_direct": np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
            "X": np.ones((5, 1)),
            "sampling_var": np.array([1.0, 1.0, 1.0, 1.0, 1.0]),
        }
        result = method.pure_step(state, {"max_iter": 20})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))
