from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.econometrics import (
    ThresholdRegressionData,
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


def _make_threshold_data() -> ThresholdRegressionData:
    rng = np.random.default_rng(21)
    n_obs = 320
    x = rng.normal(size=n_obs)
    s = rng.normal(size=n_obs)
    threshold_shift = 0.15
    state_weight = 0.4
    q = threshold_shift + state_weight * s + rng.normal(scale=0.55, size=n_obs)
    normalized_score = q - (threshold_shift + state_weight * s)
    y = 1.0 + 0.6 * x + 1.35 * (normalized_score >= 0.0).astype(float)
    y += rng.normal(scale=0.2, size=n_obs)

    return ThresholdRegressionData(
        dependent=y,
        exog=x[:, None],
        running_variable=q,
        state_variables=s[:, None],
        feature_names=["x"],
        state_names=["state_score"],
    )


def _make_threshold_iv_data(*, endogenous_threshold: bool) -> ThresholdRegressionData:
    rng = np.random.default_rng(22 if endogenous_threshold else 24)
    n_obs = 480
    x_exog = rng.normal(size=n_obs)
    s = rng.normal(size=n_obs)
    z_q = rng.normal(size=n_obs)
    z_x = rng.normal(size=n_obs)
    latent = rng.normal(scale=0.6, size=n_obs)

    threshold_shift = 0.1
    state_weight = 0.35
    q = threshold_shift + state_weight * s + rng.normal(scale=0.25, size=n_obs)
    if endogenous_threshold:
        q += 0.8 * z_q + 0.55 * latent

    normalized_score = q - (threshold_shift + state_weight * s)
    x_endog = 1.15 * z_x + 0.35 * x_exog + 0.75 * latent + rng.normal(scale=0.2, size=n_obs)
    y = 1.0 + 1.8 * x_endog + 0.45 * x_exog + 1.2 * (normalized_score >= 0.0).astype(float)
    y += 0.55 * latent + rng.normal(scale=0.25, size=n_obs)

    instruments = np.column_stack([z_q, z_x]) if endogenous_threshold else z_x[:, None]
    instrument_names = ["z_q", "z_x"] if endogenous_threshold else ["z_x"]

    return ThresholdRegressionData(
        dependent=y,
        exog=np.column_stack([x_endog, x_exog]),
        running_variable=q,
        state_variables=s[:, None],
        instruments=instruments,
        feature_names=["x_endog", "x_exog"],
        state_names=["state_score"],
        instrument_names=instrument_names,
        cluster_ids=np.repeat(np.arange(60), n_obs // 60),
    )


def _make_kink_data() -> ThresholdRegressionData:
    rng = np.random.default_rng(23)
    n_obs = 360
    x = rng.normal(size=n_obs)
    s = rng.normal(size=n_obs)
    q = 0.2 + 0.35 * s + rng.normal(scale=0.55, size=n_obs)
    normalized_score = q - (0.2 + 0.35 * s)
    y = 0.8 + 0.5 * x + 1.25 * np.maximum(normalized_score, 0.0)
    y += rng.normal(scale=0.18, size=n_obs)

    return ThresholdRegressionData(
        dependent=y,
        exog=x[:, None],
        running_variable=q,
        state_variables=s[:, None],
        feature_names=["x"],
        state_names=["state_score"],
    )


def _make_frd_data(*, weak_first_stage: bool = False) -> ThresholdRegressionData:
    rng = np.random.default_rng(31 if not weak_first_stage else 32)
    n_obs = 420
    x = rng.normal(size=n_obs)
    s = rng.normal(size=n_obs)
    threshold_shift = 0.05
    state_weight = 0.25
    score = rng.normal(scale=0.45, size=n_obs)
    q = threshold_shift + state_weight * s + score

    jump = 0.02 if weak_first_stage else 0.75
    treatment = 0.25 + jump * (score >= 0.0).astype(float) + 0.2 * score + 0.05 * x
    treatment += rng.normal(scale=0.04, size=n_obs)
    y = 1.0 + 1.4 * treatment + 0.25 * score + 0.1 * x + rng.normal(scale=0.08, size=n_obs)

    return ThresholdRegressionData(
        dependent=y,
        exog=x[:, None],
        running_variable=q,
        state_variables=s[:, None],
        treatment=treatment,
        feature_names=["x"],
        state_names=["state_score"],
    )


def _make_frkd_data() -> ThresholdRegressionData:
    rng = np.random.default_rng(33)
    n_obs = 460
    x = rng.normal(size=n_obs)
    s = rng.normal(size=n_obs)
    threshold_shift = -0.03
    state_weight = 0.2
    score = rng.normal(scale=0.55, size=n_obs)
    q = threshold_shift + state_weight * s + score

    policy = 0.35 * score + 1.5 * np.maximum(score, 0.0) + 0.03 * x
    policy += rng.normal(scale=0.025, size=n_obs)
    y = 0.8 + 1.3 * policy + 0.05 * score**2 + 0.03 * x + rng.normal(scale=0.04, size=n_obs)

    return ThresholdRegressionData(
        dependent=y,
        exog=x[:, None],
        running_variable=q,
        state_variables=s[:, None],
        policy_variable=policy,
        feature_names=["x"],
        state_names=["state_score"],
    )


def test_state_dependent_threshold_runs_with_known_surface() -> None:
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("econometrics.thresholds.state_dependent_threshold@1.0.0")

    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_threshold_data(),
        params={
            "state_policy_weights": [0.4],
            "grid_size": 35,
            "trim_fraction": 0.1,
            "covariance": "robust",
            "regime_interactions": False,
        },
        seed=41,
    )

    result = dispatched.output["result"]
    assert result.method_name == "state_dependent_threshold"
    assert result.threshold_state_field is not None
    assert result.threshold_state_field.threshold_surface_mode.value == "affine_state_fixed"
    assert abs(result.threshold_state_field.threshold_shift - 0.15) < 0.25
    assert result.params["regime_intercept"] > 0.8
    assert dispatched.output["specification_curve_bundle"] is not None
    assert dispatched.output["bounds_report"] is None
    assert dispatched.output["uncertainty_envelope"] is not None


def test_state_dependent_threshold_iv_backend_instruments_endogenous_regressor() -> None:
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("econometrics.thresholds.state_dependent_threshold@1.0.0")

    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_threshold_iv_data(endogenous_threshold=False),
        params={
            "state_policy_weights": [0.35],
            "estimation_backend": "2sls",
            "n_endogenous": 1,
            "grid_size": 31,
            "regime_interactions": False,
        },
        seed=43,
    )

    result = dispatched.output["result"]
    assert result.threshold_state_field is not None
    assert result.threshold_state_field.identification_mode.value == "global_iv_gmm"
    assert abs(result.params["x_endog"] - 1.8) < 0.8
    assert result.params["regime_intercept"] > 0.5
    assert dispatched.output["bounds_report"] is None


def test_state_dependent_threshold_gmm_control_function_bootstrap_reports_audit_trail() -> None:
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("econometrics.thresholds.state_dependent_threshold@1.0.0")

    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_threshold_iv_data(endogenous_threshold=True),
        params={
            "state_policy_weights": [0.35],
            "estimation_backend": "gmm",
            "n_endogenous": 1,
            "use_control_function": True,
            "control_function_order": 2,
            "grid_size": 29,
            "regime_interactions": False,
            "n_bootstrap": 12,
            "bootstrap_seed": 9,
            "bootstrap_by_cluster": True,
        },
        seed=45,
    )

    result = dispatched.output["result"]
    assert result.threshold_state_field is not None
    assert result.threshold_state_field.identification_mode.value == "global_control_function"
    assert result.threshold_state_field.first_stage_r_squared is not None
    assert result.threshold_state_field.first_stage_r_squared > 0.2
    assert result.params["regime_intercept"] > 0.4
    assert result.diagnostics["estimation_backend"] == "gmm"
    assert "bootstrap" in result.diagnostics
    assert dispatched.output["specification_curve_bundle"] is not None


def test_state_dependent_kink_runs_and_returns_kink_plus() -> None:
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("econometrics.thresholds.state_dependent_kink@1.0.0")

    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_kink_data(),
        params={
            "state_policy_weights": [0.35],
            "grid_size": 41,
            "trim_fraction": 0.1,
        },
        seed=47,
    )

    result = dispatched.output["result"]
    assert result.method_name == "state_dependent_kink"
    assert result.threshold_state_field is not None
    assert result.threshold_state_field.continuity_imposed is True
    assert abs(result.threshold_state_field.threshold_shift - 0.2) < 0.3
    assert result.params["kink_plus"] > 0.8
    assert dispatched.output["specification_curve_bundle"] is not None
    assert dispatched.output["bounds_report"] is None


def test_state_dependent_frd_recovers_local_effect() -> None:
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("econometrics.thresholds.state_dependent_frd@1.0.0")

    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_frd_data(),
        params={
            "state_policy_weights": [0.25],
            "threshold_shift": 0.05,
            "bandwidth": 0.35,
            "covariate_adjustment": False,
        },
        seed=51,
    )

    result = dispatched.output["result"]
    assert result.threshold_state_field is not None
    assert result.threshold_state_field.identification_mode.value == "local_fuzzy_rd"
    assert abs(result.params["local_effect"] - 1.4) < 0.45
    assert dispatched.output["specification_curve_bundle"] is not None
    assert dispatched.output["bounds_report"] is None


def test_state_dependent_frkd_recovers_local_effect() -> None:
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("econometrics.thresholds.state_dependent_frkd@1.0.0")

    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_frkd_data(),
        params={
            "state_policy_weights": [0.2],
            "threshold_shift": -0.03,
            "bandwidth": 0.35,
            "covariate_adjustment": False,
            "weak_first_stage_threshold": 1.0,
        },
        seed=53,
    )

    result = dispatched.output["result"]
    assert result.threshold_state_field is not None
    assert result.threshold_state_field.identification_mode.value == "local_fuzzy_rkd"
    assert abs(result.params["local_effect"] - 1.3) < 0.5
    assert dispatched.output["specification_curve_bundle"] is not None
    assert dispatched.output["bounds_report"] is None


def test_state_dependent_frd_triggers_bounds_when_first_stage_is_weak() -> None:
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get("econometrics.thresholds.state_dependent_frd@1.0.0")

    dispatched = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_frd_data(weak_first_stage=True),
        params={
            "state_policy_weights": [0.25],
            "threshold_shift": 0.05,
            "bandwidth": 0.35,
            "covariate_adjustment": False,
            "weak_first_stage_threshold": 10.0,
        },
        seed=55,
    )

    result = dispatched.output["result"]
    assert result.threshold_state_field is not None
    assert dispatched.output["bounds_report"] is not None
    assert result.diagnostics["identify_or_bound"]["triggered"] is True
