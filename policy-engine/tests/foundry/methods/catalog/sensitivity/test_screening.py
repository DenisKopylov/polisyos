from __future__ import annotations

import numpy as np


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestMorris:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "sensitivity.global.morris@1.0.0")
        rng = np.random.default_rng(42)
        n_trajectories, n_factors = 10, 3
        state = {
            "model_outputs": rng.normal(0, 1, size=(n_trajectories, n_factors + 1)),
            "parameter_levels": rng.uniform(0, 1, size=(n_trajectories, n_factors + 1, n_factors)),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "sensitivity.global.morris@1.0.0")
        rng = np.random.default_rng(0)
        n_trajectories, n_factors = 8, 2
        state = {
            "model_outputs": rng.normal(0, 1, size=(n_trajectories, n_factors + 1)),
            "parameter_levels": rng.uniform(0, 1, size=(n_trajectories, n_factors + 1, n_factors)),
        }
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))
