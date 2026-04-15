from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestHorvitzThompson:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.weighting.horvitz_thompson@1.0.0")
        state = {
            "values": np.array([10.0, 20.0, 30.0, 40.0, 50.0]),
            "inclusion_probabilities": np.array([0.2, 0.3, 0.5, 0.4, 0.6]),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.weighting.horvitz_thompson@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "values": rng.normal(100, 10, size=20),
            "inclusion_probabilities": rng.uniform(0.1, 0.9, size=20),
        }
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))
