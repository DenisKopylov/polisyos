from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.econometrics import (
    TimeSeriesData,
    ensure_econometric_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _make_arima_series() -> np.ndarray:
    rng = np.random.default_rng(99)
    n = 120
    values = np.zeros(n, dtype=float)
    epsilon = rng.normal(scale=0.5, size=n)
    for t in range(1, n):
        values[t] = 0.7 * values[t - 1] + epsilon[t]
    return values


def _make_var_series() -> np.ndarray:
    rng = np.random.default_rng(101)
    n = 150
    y = np.zeros((n, 2), dtype=float)
    noise = rng.normal(scale=0.2, size=(n, 2))
    for t in range(1, n):
        y[t, 0] = 0.5 * y[t - 1, 0] + 0.2 * y[t - 1, 1] + noise[t, 0]
        y[t, 1] = -0.1 * y[t - 1, 0] + 0.4 * y[t - 1, 1] + noise[t, 1]
    return y


def test_arima_runs() -> None:
    pytest.importorskip("statsmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.timeseries.time_series@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=TimeSeriesData(endog=_make_arima_series()),
        params={"model": "arima", "p": 1, "d": 0, "q": 0},
        seed=10,
    )

    result = dispatched.output["result"]
    assert result.method_name == "arima"
    assert result.n_obs > 0
    assert result.params
    assert dispatched.output["uncertainty_envelope"] is not None


def test_var_runs() -> None:
    pytest.importorskip("statsmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.timeseries.time_series@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=TimeSeriesData(endog=_make_var_series()),
        params={"model": "var", "max_lags": 4, "information_criterion": "aic"},
        seed=12,
    )

    result = dispatched.output["result"]
    assert result.method_name == "var"
    assert result.params
    assert result.n_obs > 0
    assert dispatched.output["uncertainty_envelope"] is not None
