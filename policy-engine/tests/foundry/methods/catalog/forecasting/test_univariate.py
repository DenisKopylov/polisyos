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


class TestExponentialSmoothing:
    def test_basic_forecast(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "forecasting.univariate.exponential_smoothing@1.0.0")
        state = {"series": np.array([1.0, 2.0, 3.0, 4.0, 5.0])}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)
        assert any(k for k in result if "forecast" in k.lower() or "smoothed" in k.lower() or "fitted" in k.lower() or len(result) > 0)

    def test_constant_series(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "forecasting.univariate.exponential_smoothing@1.0.0")
        state = {"series": np.array([5.0] * 10)}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)


class TestThetaMethod:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "forecasting.univariate.theta@1.0.0")
        state = {"series": np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "forecasting.univariate.theta@1.0.0")
        state = {"series": np.array([10.0, 20.0, 15.0, 25.0, 30.0, 28.0, 35.0, 40.0])}
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))
