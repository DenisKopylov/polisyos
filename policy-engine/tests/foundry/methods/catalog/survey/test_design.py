from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestComplexSurveyDesign:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.design.complex_survey@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "y": rng.normal(100, 15, size=60),
            "weights": rng.uniform(0.5, 2.0, size=60),
            "strata": np.repeat([0, 1, 2], 20),
            "clusters": np.tile(np.arange(10), 6),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.design.complex_survey@1.0.0")
        state = {
            "y": np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0]),
            "weights": np.array([1.0, 1.0, 2.0, 2.0, 1.5, 1.5]),
            "strata": np.array([0, 0, 1, 1, 2, 2]),
            "clusters": np.array([0, 1, 2, 3, 4, 5]),
        }
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))
