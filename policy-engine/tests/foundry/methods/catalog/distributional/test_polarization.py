from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestEstebanRay:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.polarization.esteban_ray@1.0.0")
        rng = np.random.default_rng(42)
        state = {"values": rng.normal(100, 20, size=200)}
        result = method.pure_step(state, {"alpha": 1.5, "n_groups": 5})
        assert isinstance(result, dict)


class TestDuclosEstebanRay:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.polarization.duclos_esteban_ray@1.0.0")
        rng = np.random.default_rng(42)
        state = {"values": rng.normal(100, 20, size=200)}
        result = method.pure_step(state, {"alpha": 0.5})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "distributional.polarization.duclos_esteban_ray@1.0.0")
        state = {"values": np.array([10.0, 20.0, 30.0, 100.0, 200.0, 300.0])}
        result = method.pure_step(state, {"alpha": 0.5})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))
