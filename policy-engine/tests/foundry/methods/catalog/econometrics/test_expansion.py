from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import PanelObservationalData
from polisyos.foundry.methods.econometrics import TimeSeriesData, ensure_econometric_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _time_series() -> TimeSeriesData:
    rng = np.random.default_rng(11)
    endog = np.cumsum(rng.normal(size=(48, 2)), axis=0) + np.array([0.2, -0.15]) * np.arange(48)[:, None]
    return TimeSeriesData(endog=endog)


def _panel() -> PanelObservationalData:
    return PanelObservationalData(
        outcome=np.array(
            [
                [1.0, 1.1, 1.2, 1.25, 1.3],
                [0.9, 1.0, 1.05, 1.1, 1.15],
                [1.2, 1.25, 1.35, 1.55, 1.65],
                [1.0, 1.05, 1.1, 1.18, 1.22],
            ]
        ),
        treatment=np.array([0, 0, 1, 1]),
        time_treatment=3,
        covariates=np.array([[1.0, 0.2], [0.8, 0.1], [1.2, 0.4], [0.9, 0.15]]),
        unit_ids=np.arange(4),
        time_index=np.arange(5),
    )


def test_vecm_and_bayesian_var_run() -> None:
    pytest.importorskip("statsmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    state = _time_series()

    vecm_cls = registry.get("econometrics.timeseries.vecm@1.0.0")
    vecm_result = dispatcher.dispatch(
        method_class=vecm_cls,
        signature=vecm_cls.signature,
        state=state,
        params={"coint_rank": 1, "k_ar_diff": 1},
        seed=101,
    )
    assert vecm_result.output["result"].method_name == "vecm"
    assert "alpha_0_0" in vecm_result.output["result"].params

    bvar_cls = registry.get("econometrics.timeseries.bayesian_var@1.0.0")
    bvar_result = dispatcher.dispatch(
        method_class=bvar_cls,
        signature=bvar_cls.signature,
        state=state,
        params={"n_lags": 2, "prior_scale": 0.35},
        seed=103,
    )
    assert bvar_result.output["result"].method_name == "bayesian_var"
    assert "prior_scale" in bvar_result.output["result"].diagnostics


def test_synthetic_did_and_spatial_autoregressive_run() -> None:
    pytest.importorskip("statsmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    sdid_cls = registry.get("econometrics.panel.synthetic_did@1.0.0")
    sdid_result = dispatcher.dispatch(
        method_class=sdid_cls,
        signature=sdid_cls.signature,
        state=_panel(),
        params={"ridge": 1e-3},
        seed=107,
    )
    assert sdid_result.output["result"].method_name == "synthetic_did"
    assert "donor_weights" in sdid_result.output["result"].diagnostics

    rng = np.random.default_rng(13)
    features = np.column_stack([np.ones(8), rng.normal(size=8), rng.normal(size=8)])
    endog = 0.5 + features @ np.array([0.2, 1.0, -0.4]) + rng.normal(scale=0.05, size=8)
    weights = np.array(
        [
            [0, 1, 1, 0, 0, 0, 1, 0],
            [1, 0, 0, 1, 0, 0, 0, 1],
            [1, 0, 0, 1, 1, 0, 0, 0],
            [0, 1, 1, 0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0, 1, 1, 0],
            [0, 0, 0, 1, 1, 0, 0, 1],
            [1, 0, 0, 0, 1, 0, 0, 1],
            [0, 1, 0, 0, 0, 1, 1, 0],
        ],
        dtype=float,
    )
    sar_cls = registry.get("econometrics.spatial.spatial_autoregressive@1.0.0")
    sar_result = dispatcher.dispatch(
        method_class=sar_cls,
        signature=sar_cls.signature,
        state={"endog": endog, "exog": features, "weights_matrix": weights},
        params={},
        seed=109,
    )
    assert sar_result.output["result"].method_name == "spatial_autoregressive"
    assert "rho" in sar_result.output["result"].params
