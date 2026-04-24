"""PolicyOS custom ATE estimators: TMLE, AIPW, IPW."""

from __future__ import annotations

import sys
from typing import Any

import numpy as np

from benchmarks.honest_comparison.adapters.base import EstimatorResult

# Ensure PolicyOS is importable
if "src" not in sys.path:
    sys.path.insert(0, "src")


def _tier_to_policyos_params(config: dict[str, Any], seed: int) -> dict[str, Any]:
    """Convert benchmark tier config to PolicyOS ATENuisanceContract params."""
    prop_model = config.get("propensity_model", "logistic_regression")
    out_model = config.get("outcome_model", "linear_regression")

    # Map tier model names to PolicyOS backend names
    prop_map = {
        "logistic_regression": "logistic_regression",
        "hist_gradient_boosting_classifier": "histgradientboosting",
    }
    out_map = {
        "linear_regression": "elastic_net",  # PolicyOS "linear" is elastic_net with alpha~0
        "hist_gradient_boosting_regressor": "histgradientboosting",
    }

    params = {
        "propensity_backend": prop_map.get(prop_model, prop_model),
        "outcome_backend": out_map.get(out_model, out_model),
        "crossfit_folds": config.get("cv_folds", 5),
        "n_repeats": 1,
        "random_seed": seed,
        "bootstrap_draws": config.get("bootstrap_draws", 200),
        "inference_backend": "bootstrap_eif",
        "confidence_level": 0.95,
    }

    # Tier A: disable all extras
    if config.get("calibration") is None:
        params["calibration_mode"] = "none"
    if config.get("overlap_trimming") is None:
        params["propensity_trimming"] = 0.0
        params["propensity_clipping"] = 0.001
    elif config.get("overlap_trimming_lower") is not None:
        params["propensity_clipping"] = config["overlap_trimming_lower"]

    if config.get("model_selection") is None:
        params["nuisance_model_family"] = "fixed"

    return params


class PolicyOSTMLE:
    name = "PolicyOS_TMLE"
    library = "policyos"

    def supports_cate(self) -> bool:
        return False

    def fit_predict(
        self,
        X: np.ndarray,
        T: np.ndarray,
        Y: np.ndarray,
        config: dict[str, Any],
        seed: int,
    ) -> EstimatorResult:
        from polisyos.foundry.methods.catalog.causal.tmle_core import fit_tmle_ate

        params = _tier_to_policyos_params(config, seed)
        fit_result, nuisance = fit_tmle_ate(X, T, Y, params)

        return EstimatorResult(
            ate=fit_result.ate,
            ate_se=fit_result.standard_error,
            ci_lower=fit_result.ci_lower,
            ci_upper=fit_result.ci_upper,
        )


class PolicyOSAIPW:
    name = "PolicyOS_AIPW"
    library = "policyos"

    def supports_cate(self) -> bool:
        return False

    def fit_predict(
        self,
        X: np.ndarray,
        T: np.ndarray,
        Y: np.ndarray,
        config: dict[str, Any],
        seed: int,
    ) -> EstimatorResult:
        from polisyos.foundry.methods.catalog.causal.tmle_core import fit_aipw_ate

        params = _tier_to_policyos_params(config, seed)
        fit_result, nuisance = fit_aipw_ate(X, T, Y, params)

        return EstimatorResult(
            ate=fit_result.ate,
            ate_se=fit_result.standard_error,
            ci_lower=fit_result.ci_lower,
            ci_upper=fit_result.ci_upper,
        )


class PolicyOSIPW:
    name = "PolicyOS_IPW"
    library = "policyos"

    def supports_cate(self) -> bool:
        return False

    def fit_predict(
        self,
        X: np.ndarray,
        T: np.ndarray,
        Y: np.ndarray,
        config: dict[str, Any],
        seed: int,
    ) -> EstimatorResult:
        from polisyos.foundry.methods.catalog.causal.treatment_effects import IPWEstimator

        state = {"X": X, "treatment": T, "outcome": Y}
        params = _tier_to_policyos_params(config, seed)
        params["trimming"] = params.pop("propensity_clipping", 0.01)
        result = IPWEstimator.pure_step(state, params)
        r = result.get("result", result)

        return EstimatorResult(
            ate=r.get("ate") or r.get("ate_hajek"),
            ate_se=r.get("ate_se"),
            ci_lower=r.get("ci_lower"),
            ci_upper=r.get("ci_upper"),
        )
