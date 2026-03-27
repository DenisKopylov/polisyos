from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    ensure_all_methods_registered(registry)
    try:
        return registry.get(fqn)
    except Exception:
        pytest.skip(f"{fqn} not registered")


class TestMonteCarloInference:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.inference.monte_carlo@1.0.0")
        rng = np.random.default_rng(42)
        state = {"samples": rng.normal(5, 1, size=(100, 3))}
        result = method.pure_step(state, {"confidence_level": 0.95})
        assert isinstance(result, dict)


class TestBootstrapInference:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.inference.bootstrap@1.0.0")
        rng = np.random.default_rng(42)
        state = {"data": rng.normal(10, 2, size=50)}
        result = method.pure_step(state, {"n_bootstrap": 200, "confidence_level": 0.95, "seed": 42})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.inference.bootstrap@1.0.0")
        state = {"data": np.array([1.0, 2.0, 3.0, 4.0, 5.0])}
        result = method.pure_step(state, {"n_bootstrap": 100, "seed": 0})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


class TestPermutationTest:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "simulation.inference.permutation_test@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "group_a": rng.normal(10, 2, size=20),
            "group_b": rng.normal(12, 2, size=20),
        }
        result = method.pure_step(state, {"n_permutations": 500, "seed": 42})
        assert isinstance(result, dict)
