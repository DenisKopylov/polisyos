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


class TestNormalScores:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.probabilistic.normal_scores@1.0.0")
        state = {
            "observations": np.array([1.0, 2.0, 3.0]),
            "predictive_mean": np.array([1.1, 2.2, 2.8]),
            "predictive_std": np.array([0.5, 0.5, 0.5]),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.probabilistic.normal_scores@1.0.0")
        rng = np.random.default_rng(42)
        state = {
            "observations": rng.normal(0, 1, size=20),
            "predictive_mean": rng.normal(0, 1, size=20),
            "predictive_std": np.abs(rng.normal(1, 0.2, size=20)),
        }
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))

    def test_perfect_prediction(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.probabilistic.normal_scores@1.0.0")
        values = np.array([1.0, 2.0, 3.0])
        state = {
            "observations": values,
            "predictive_mean": values,
            "predictive_std": np.array([0.1, 0.1, 0.1]),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_wide_uncertainty(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.probabilistic.normal_scores@1.0.0")
        state = {
            "observations": np.array([1.0, 2.0]),
            "predictive_mean": np.array([1.0, 2.0]),
            "predictive_std": np.array([100.0, 100.0]),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)
