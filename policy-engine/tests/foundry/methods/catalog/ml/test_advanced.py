from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.ml import TabularData, ensure_ml_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _make_tabular() -> TabularData:
    rng = np.random.default_rng(121)
    x = rng.normal(size=(64, 3))
    y = 0.4 + 1.6 * x[:, 0] - 0.5 * x[:, 1] + 0.2 * x[:, 2] + rng.normal(scale=0.2, size=64)
    return TabularData(features=x, target=y, feature_names=["x0", "x1", "x2"])


def test_gaussian_process_and_quantile_forest_run() -> None:
    pytest.importorskip("sklearn")

    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    tabular = _make_tabular()

    gp_cls = registry.get("ml.regression.gaussian_process@1.0.0")
    gp_result = dispatcher.dispatch(
        method_class=gp_cls,
        signature=gp_cls.signature,
        state=tabular,
        params={"length_scale": 1.2},
        seed=123,
    )
    assert gp_result.output["result"].method_name == "gaussian_process"
    assert gp_result.output["uncertainty_envelope"] is not None

    qf_cls = registry.get("ml.regression.quantile_forest@1.0.0")
    qf_result = dispatcher.dispatch(
        method_class=qf_cls,
        signature=qf_cls.signature,
        state=tabular,
        params={"alpha": 0.1, "n_estimators": 80},
        seed=127,
    )
    coverage = qf_result.output["prediction_interval"].coverage
    assert qf_result.output["result"].method_name == "quantile_forest"
    assert coverage is not None and 0.0 <= coverage <= 1.0


def test_neural_ode_runs_on_time_index_mapping() -> None:
    pytest.importorskip("sklearn")
    pytest.importorskip("scipy")

    ensure_ml_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    series = np.cumsum(np.random.default_rng(129).normal(size=24))
    ode_cls = registry.get("ml.dynamics.neural_ode@1.0.0")
    ode_result = dispatcher.dispatch(
        method_class=ode_cls,
        signature=ode_cls.signature,
        state={"endog": series, "time_index": np.arange(series.shape[0], dtype=float)},
        params={},
        seed=131,
    )
    assert ode_result.output["result"].method_name == "neural_ode"
    assert ode_result.output["uncertainty_envelope"] is not None
