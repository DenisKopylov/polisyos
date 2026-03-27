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


class TestMICE:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.imputation.mice@1.0.0")
        rng = np.random.default_rng(42)
        X = rng.normal(0, 1, size=(30, 4))
        missing_mask = np.zeros_like(X, dtype=bool)
        missing_mask[rng.integers(0, 30, size=10), rng.integers(0, 4, size=10)] = True
        state = {"X": X, "missing_mask": missing_mask}
        result = method.pure_step(state, {"n_imputations": 3, "n_cycles": 5, "seed": 42})
        assert isinstance(result, dict)


class TestNonresponseAdjustment:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "survey.imputation.nonresponse_adjustment@1.0.0")
        rng = np.random.default_rng(42)
        n = 40
        state = {
            "X": rng.normal(0, 1, size=(n, 3)),
            "response_indicator": rng.choice([0.0, 1.0], size=n, p=[0.3, 0.7]),
            "base_weights": rng.uniform(0.5, 2.0, size=n),
        }
        result = method.pure_step(state, {"max_iter": 20})
        assert isinstance(result, dict)
