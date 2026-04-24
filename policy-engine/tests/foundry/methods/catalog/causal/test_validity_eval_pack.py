from __future__ import annotations

import math

import numpy as np

from polisyos.foundry.methods.catalog.causal.frontier import ProximalBridgeEstimator
from polisyos.foundry.methods.catalog.causal.invariance_tests import ICPInvarianceTest
from polisyos.foundry.methods.catalog.causal.sensitivity_metrics import SensitivityMetrics
from polisyos.foundry.methods.causal import GraphCausalData
from polisyos.ir.analytics.causal import EstimationStatus


def test_ws3a_synthetic_sensitivity_eval_pack_reports_robust_effect() -> None:
    rng = np.random.default_rng(4)
    n_obs = 240
    confounder = rng.normal(size=n_obs)
    treatment = (0.9 * confounder + rng.normal(scale=0.6, size=n_obs) > 0).astype(float)
    outcome = 0.8 * treatment + 0.7 * confounder + rng.normal(scale=0.5, size=n_obs)
    data = GraphCausalData(
        data=np.column_stack([treatment, outcome, confounder]),
        column_names=["T", "Y", "Z"],
        treatment="T",
        outcome="Y",
        covariates=["Z"],
    )

    payload = SensitivityMetrics.pure_step(
        data,
        {
            "point_estimate": 0.8,
            "confidence_interval": [0.4, 1.1],
            "standard_error": 0.18,
            "sample_size": n_obs,
            "covariates": ["Z"],
            "benchmark_covariates": ["Z"],
        },
    )
    result = payload["sensitivity_result"]

    assert result.is_robust is True
    assert result.e_value is not None
    assert result.e_value > 2.0
    assert result.e_value_ci_lower is not None
    assert result.e_value_ci_lower > 1.0
    assert result.rosenbaum_gamma is not None
    assert result.rosenbaum_gamma >= 1.25
    assert result.benchmark_results
    assert result.benchmark_results[0].covariate_name == "Z"


def test_ws3a_synthetic_icp_eval_pack_accepts_stable_domains() -> None:
    rng = np.random.default_rng(0)
    n_obs = 160
    domain_labels = np.array([0] * (n_obs // 2) + [1] * (n_obs // 2))
    feature_0 = rng.normal(size=n_obs)
    feature_1 = rng.normal(size=n_obs)
    outcome = 1.5 * feature_0 + rng.normal(size=n_obs)
    data = np.column_stack([feature_0, feature_1, outcome])

    payload = ICPInvarianceTest.pure_step(
        {"data": data, "domain_labels": domain_labels, "target_col": 2},
        {"alpha": 0.05, "correction": "bh"},
    )
    result = payload["result"]

    assert result["passed"] is True
    assert result["n_rejected"] == 0
    assert set(result["invariant_features"]) == {0, 1}


def test_ws3a_semi_synthetic_proximal_eval_pack_yields_finite_interval() -> None:
    rng = np.random.default_rng(1)
    n_obs = 220
    latent = rng.normal(size=n_obs)
    covariates = rng.normal(size=(n_obs, 2))
    treatment = (
        0.8 * latent + 0.9 * covariates[:, 0] + rng.normal(scale=0.5, size=n_obs) > 0
    ).astype(float)
    treatment_proxy = latent + 0.3 * covariates[:, 0] + rng.normal(scale=0.3, size=n_obs)
    outcome_proxy = latent + 0.4 * covariates[:, 1] + rng.normal(scale=0.3, size=n_obs)
    outcome = (
        1.2 * treatment + 0.7 * latent + 0.4 * covariates[:, 0] + rng.normal(scale=0.4, size=n_obs)
    )

    payload = ProximalBridgeEstimator.pure_step(
        {
            "outcome": outcome,
            "treatment": treatment,
            "covariates": covariates,
            "treatment_proxy": treatment_proxy,
            "outcome_proxy": outcome_proxy,
        },
        {"n_bootstrap": 64, "confidence_level": 0.95, "ridge": 1.0e-4, "__seed__": 3},
    )
    report = payload["report"]
    proximal = payload["proximal_result"]
    lower, upper = proximal["confidence_interval"]

    assert report.status is EstimationStatus.SUCCESS
    assert math.isfinite(proximal["point_estimate"])
    assert math.isfinite(lower)
    assert math.isfinite(upper)
    assert lower <= proximal["point_estimate"] <= upper
    assert proximal["proxy_strength"] > 0.5
