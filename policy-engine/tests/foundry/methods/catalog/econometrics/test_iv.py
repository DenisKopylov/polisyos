from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.econometrics import (
    PanelData,
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


def _make_iv_panel() -> PanelData:
    rng = np.random.default_rng(11)
    n_entities = 40
    n_periods = 5
    n_obs = n_entities * n_periods

    entity_ids = np.repeat(np.arange(n_entities), n_periods)
    time_ids = np.tile(np.arange(n_periods), n_entities)

    z = rng.normal(size=n_obs)
    x_exog = rng.normal(size=n_obs)
    u = rng.normal(scale=0.6, size=n_obs)
    x_endog = 0.9 * z + 0.4 * u + rng.normal(scale=0.2, size=n_obs)
    epsilon = u + rng.normal(scale=0.2, size=n_obs)
    y = 2.0 * x_endog + 0.6 * x_exog + epsilon

    return PanelData(
        dependent=y,
        exog=np.column_stack([x_endog, x_exog]),
        entity_ids=entity_ids,
        time_ids=time_ids,
        instrument_ids=np.column_stack([z]),
        feature_names=["x_endog", "x_exog"],
        instrument_names=["z1"],
    )


def test_iv_2sls_runs_and_estimates_endogenous_effect() -> None:
    pytest.importorskip("linearmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.iv.instrumental_variables@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_iv_panel(),
        params={"method": "2sls", "n_endogenous": 1, "cov_type": "robust"},
        seed=5,
    )

    result = dispatched.output["result"]
    assert result.method_name == "iv_2sls"
    assert any("x_endog" in name for name in result.params)

    beta = next(value for key, value in result.params.items() if "x_endog" in key)
    assert abs(beta - 2.0) < 0.5
    assert dispatched.output["envelope"] is not None


def test_iv_gmm_runs() -> None:
    pytest.importorskip("linearmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.iv.instrumental_variables@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_iv_panel(),
        params={
            "method": "gmm",
            "n_endogenous": 1,
            "cov_type": "robust",
            "weight_type": "robust",
        },
        seed=6,
    )

    result = dispatched.output["result"]
    assert result.method_name == "iv_gmm"
    assert result.n_obs > 0
