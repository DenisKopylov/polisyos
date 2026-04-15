from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestTransitionMatrix:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.mobility.transition_matrix@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "origin_classes": rng.integers(0, 5, size=100),
            "destination_classes": rng.integers(0, 5, size=100),
        }
        result = method.pure_step(state, {"n_classes": 5})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.mobility.transition_matrix@1.0.0")
        state = {
            "origin_classes": np.array([0, 0, 1, 1, 2]),
            "destination_classes": np.array([0, 1, 1, 2, 2]),
        }
        result = method.pure_step(state, {"n_classes": 3})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


class TestIntergenerationalElasticity:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.mobility.intergenerational_elasticity@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "parent_values": np.abs(rng.normal(50, 10, size=50)) + 1.0,
            "child_values": np.abs(rng.normal(55, 12, size=50)) + 1.0,
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)
