from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.econometrics import (
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


def _make_high_dimensional_iv_panel() -> PanelData:
    rng = np.random.default_rng(29)
    n_entities = 80
    n_periods = 4
    n_obs = n_entities * n_periods

    entity_ids = np.repeat(np.arange(n_entities), n_periods)
    time_ids = np.tile(np.arange(n_periods), n_entities)

    controls = rng.normal(size=(n_obs, 8))
    instruments = rng.normal(size=(n_obs, 6))
    latent = rng.normal(scale=0.4, size=n_obs)

    x0 = controls[:, 0]
    x3 = controls[:, 3]
    z0 = instruments[:, 0]
    z1 = instruments[:, 1]

    x_endog = (
        1.3 * z0 + 0.4 * z1 + 0.8 * x0 - 0.5 * x3 + latent + rng.normal(scale=0.15, size=n_obs)
    )
    y = 1.8 * x_endog + 0.7 * x0 - 0.4 * x3 + latent + rng.normal(scale=0.2, size=n_obs)

    feature_names = ["x_endog"] + [f"x{i}" for i in range(controls.shape[1])]
    instrument_names = [f"z{i}" for i in range(instruments.shape[1])]

    return PanelData(
        dependent=y,
        exog=np.column_stack([x_endog, controls]),
        entity_ids=entity_ids,
        time_ids=time_ids,
        instrument_ids=instruments,
        feature_names=feature_names,
        instrument_names=instrument_names,
    )


def _make_multi_endogenous_high_dimensional_iv_panel() -> PanelData:
    rng = np.random.default_rng(31)
    n_entities = 100
    n_periods = 4
    n_obs = n_entities * n_periods

    entity_ids = np.repeat(np.arange(n_entities), n_periods)
    time_ids = np.tile(np.arange(n_periods), n_entities)

    controls = rng.normal(size=(n_obs, 8))
    instruments = rng.normal(size=(n_obs, 6))
    latent = rng.normal(scale=0.25, size=n_obs)

    x0 = controls[:, 0]
    x2 = controls[:, 2]
    z0 = instruments[:, 0]
    z1 = instruments[:, 1]
    z2 = instruments[:, 2]
    z3 = instruments[:, 3]

    d1 = 1.2 * z0 + 0.5 * z1 + 0.7 * x0 - 0.2 * x2 + latent + rng.normal(scale=0.12, size=n_obs)
    d2 = 1.1 * z2 - 0.4 * z3 + 0.3 * x0 + 0.5 * x2 + latent + rng.normal(scale=0.12, size=n_obs)
    y = 1.6 * d1 - 0.9 * d2 + 0.8 * x0 - 0.4 * x2 + latent + rng.normal(scale=0.18, size=n_obs)

    feature_names = ["x_endog_1", "x_endog_2"] + [f"x{i}" for i in range(controls.shape[1])]
    instrument_names = [f"z{i}" for i in range(instruments.shape[1])]

    return PanelData(
        dependent=y,
        exog=np.column_stack([d1, d2, controls]),
        entity_ids=entity_ids,
        time_ids=time_ids,
        instrument_ids=instruments,
        feature_names=feature_names,
        instrument_names=instrument_names,
    )


def test_iv_2sls_runs_and_estimates_endogenous_effect() -> None:
    pytest.importorskip("linearmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.iv.two_stage_least_squares@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_iv_panel(),
        params={"n_endogenous": 1, "cov_type": "robust"},
        seed=5,
    )

    result = dispatched.output["result"]
    assert result.method_name == "iv_2sls"
    assert any("x_endog" in name for name in result.params)

    beta = next(value for key, value in result.params.items() if "x_endog" in key)
    assert abs(beta - 2.0) < 0.5
    assert dispatched.output["uncertainty_envelope"] is not None


def test_iv_gmm_runs() -> None:
    pytest.importorskip("linearmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.iv.gmm@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_iv_panel(),
        params={
            "n_endogenous": 1,
            "cov_type": "robust",
            "weight_type": "robust",
        },
        seed=6,
    )

    result = dispatched.output["result"]
    assert result.method_name == "iv_gmm"
    assert result.n_obs > 0
    assert dispatched.output["uncertainty_envelope"] is not None


def test_high_dimensional_post_selection_iv_assigns_orthogonal_tier() -> None:
    pytest.importorskip("linearmodels")
    pytest.importorskip("statsmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.iv.high_dimensional_post_selection@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_high_dimensional_iv_panel(),
        params={
            "n_endogenous": 1,
            "n_folds": 3,
            "seed": 7,
            "weak_iv_threshold": 5.0,
        },
        seed=7,
    )

    result = dispatched.output["result"]
    assert result.method_name == "iv_high_dimensional_post_selection"
    assert result.coverage_guarantee_tier == "ORTHOGONAL_CROSSFIT"
    assert "x_endog" in result.post_selection_ci
    assert result.coverage_diagnostic is not None
    assert result.coverage_diagnostic.overall_gate_passed is True
    assert dispatched.output["uncertainty_envelope"] is not None


def test_high_dimensional_post_selection_iv_falls_back_to_weak_iv_robust_set() -> None:
    pytest.importorskip("linearmodels")
    pytest.importorskip("statsmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.iv.high_dimensional_post_selection@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_high_dimensional_iv_panel(),
        params={
            "n_endogenous": 1,
            "n_folds": 3,
            "seed": 11,
            "weak_iv_threshold": 1_000_000.0,
            "ar_grid_points": 81,
        },
        seed=11,
    )

    result = dispatched.output["result"]
    assert result.coverage_guarantee_tier == "WEAK_IV_ROBUST_SET"
    assert "x_endog" in result.post_selection_ci
    assert "x_endog" in result.weak_iv_robust_ci
    assert result.coverage_diagnostic is not None
    assert result.coverage_diagnostic.identification is not None
    assert result.coverage_diagnostic.identification.passed is False
    assert result.coverage_diagnostic.interval_disagreement is not None
    assert result.coverage_diagnostic.interval_disagreement.set_inversion_used is True


def test_high_dimensional_post_selection_iv_explicit_heuristic_route() -> None:
    pytest.importorskip("linearmodels")
    pytest.importorskip("statsmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.iv.high_dimensional_post_selection@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_high_dimensional_iv_panel(),
        params={
            "n_endogenous": 1,
            "inference_route": "heuristic",
            "n_folds": 3,
            "seed": 13,
        },
        seed=13,
    )

    result = dispatched.output["result"]
    assert result.coverage_guarantee_tier == "HEURISTIC_POST_SELECTION"
    assert "x_endog" in result.post_selection_ci
    assert result.coverage_diagnostic is not None
    assert result.coverage_diagnostic.orthogonality is not None
    assert result.coverage_diagnostic.orthogonality.score_type == "post_selection_wald"


def test_high_dimensional_post_selection_iv_supports_multiple_endogenous_regressors() -> None:
    pytest.importorskip("linearmodels")
    pytest.importorskip("statsmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("econometrics.iv.high_dimensional_post_selection@1.0.0")

    dispatcher = MethodDispatcher.get_instance()
    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_multi_endogenous_high_dimensional_iv_panel(),
        params={
            "n_endogenous": 2,
            "n_folds": 3,
            "seed": 17,
            "weak_iv_threshold": 5.0,
        },
        seed=17,
    )

    result = dispatched.output["result"]
    assert result.method_name == "iv_high_dimensional_post_selection"
    assert result.coverage_diagnostic is not None
    assert result.coverage_diagnostic.identification is not None
    assert result.coverage_diagnostic.identification.multiple_endogenous_flag is True
    assert "x_endog_1" in result.params
    assert "x_endog_2" in result.params
