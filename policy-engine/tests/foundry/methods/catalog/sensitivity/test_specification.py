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


class TestSpecificationCurve:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "sensitivity.specification.specification_curve@1.0.0")
        rng = np.random.default_rng(42)
        n_specs = 20
        state = {
            "estimates": rng.normal(2.0, 0.5, size=n_specs),
            "standard_errors": np.abs(rng.normal(0.3, 0.1, size=n_specs)) + 0.01,
        }
        result = method.pure_step(state, {"significance_level": 0.05})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "sensitivity.specification.specification_curve@1.0.0")
        state = {
            "estimates": np.array([1.0, 1.5, 2.0, 2.5, 3.0]),
            "standard_errors": np.array([0.1, 0.2, 0.15, 0.1, 0.3]),
        }
        result = method.pure_step(state, {"significance_level": 0.05})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))
