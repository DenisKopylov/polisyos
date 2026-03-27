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


class TestSobolFirstOrder:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "sensitivity.global.sobol_first_order@1.0.0")
        rng = np.random.default_rng(42)
        n_samples, n_features = 100, 3
        state = {
            "outputs_a": rng.normal(0, 1, size=n_samples),
            "outputs_b": rng.normal(0, 1, size=n_samples),
            "mixed_outputs": rng.normal(0, 1, size=(n_features, n_samples)),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "sensitivity.global.sobol_first_order@1.0.0")
        rng = np.random.default_rng(0)
        n_samples, n_features = 200, 4
        state = {
            "outputs_a": rng.normal(0, 1, size=n_samples),
            "outputs_b": rng.normal(0, 1, size=n_samples),
            "mixed_outputs": rng.normal(0, 1, size=(n_features, n_samples)),
        }
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))
