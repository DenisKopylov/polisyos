"""PolicyOS CATE estimators: CausalForest, X-Learner, DML (EconML wrappers)."""

from __future__ import annotations

import sys
from typing import Any

import numpy as np

from benchmarks.honest_comparison.adapters.base import EstimatorResult

if "src" not in sys.path:
    sys.path.insert(0, "src")


def _build_state(X: np.ndarray, T: np.ndarray, Y: np.ndarray):
    """Build HTEObservationalData from arrays."""
    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

    return HTEObservationalData(
        outcome=Y,
        treatment=T.astype(int),
        covariates=X,
        confounders=None,
        feature_names=[f"X{i}" for i in range(X.shape[1])],
    )


def _extract_result(result: dict) -> EstimatorResult:
    """Extract EstimatorResult from PolicyOS pure_step output."""
    # hte_result may be top-level or in extras
    hte = result.get("hte_result") or (result.get("extras") or {}).get("hte_result")

    if hte is not None:
        cate = np.array(hte.cate_values) if hte.cate_values else None
        return EstimatorResult(
            ate=hte.ate,
            ci_lower=hte.ate_ci_lower,
            ci_upper=hte.ate_ci_upper,
            cate=cate,
        )
    # Fallback: check envelope
    envelope = result.get("envelope")
    if envelope is not None:
        return EstimatorResult(
            ate=envelope.point_estimate,
            ci_lower=envelope.confidence_interval[0] if envelope.confidence_interval else None,
            ci_upper=envelope.confidence_interval[1] if envelope.confidence_interval else None,
        )
    return EstimatorResult(failed=True, failure_reason="No result found in pure_step output")


class PolicyOSCausalForest:
    name = "PolicyOS_CausalForest"
    library = "policyos"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(
        self,
        X: np.ndarray,
        T: np.ndarray,
        Y: np.ndarray,
        config: dict[str, Any],
        seed: int,
    ) -> EstimatorResult:
        from polisyos.foundry.methods.catalog.causal.cate import CausalForestEstimator

        state = _build_state(X, T, Y)
        params = {
            "n_estimators": 200,
            "min_samples_leaf": 5,
            "honest": True,
            "cv_folds": config.get("cv_folds", 5),
            "confidence_level": 0.95,
            "random_state": seed,
            "model_y_backend": config.get("outcome_model", "linear_regression"),
            "model_t_backend": config.get("propensity_model", "logistic_regression"),
        }
        result = CausalForestEstimator.pure_step(state, params)
        return _extract_result(result)


class PolicyOSXLearner:
    name = "PolicyOS_XLearner"
    library = "policyos"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(
        self,
        X: np.ndarray,
        T: np.ndarray,
        Y: np.ndarray,
        config: dict[str, Any],
        seed: int,
    ) -> EstimatorResult:
        from polisyos.foundry.methods.catalog.causal.meta_learners import MetaLearnerEstimator

        base_model_name = (
            "linear" if config.get("outcome_model") == "linear_regression" else "gradient_boosting"
        )
        state = _build_state(X, T, Y)
        params = {
            "learner_type": "x",
            "base_model": base_model_name,
            "confidence_level": 0.95,
            "random_state": seed,
        }
        result = MetaLearnerEstimator.pure_step(state, params)
        return _extract_result(result)


class PolicyOSDML:
    name = "PolicyOS_DML"
    library = "policyos"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(
        self,
        X: np.ndarray,
        T: np.ndarray,
        Y: np.ndarray,
        config: dict[str, Any],
        seed: int,
    ) -> EstimatorResult:
        from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning

        state = _build_state(X, T, Y)
        # EconML's internal model selector only accepts: linear, poly, forest, gbf, nnet, automl
        # Map our nuisance config strings to EconML's vocabulary
        _model_map = {
            "linear_regression": "linear",
            "logistic_regression": "linear",
            "hist_gradient_boosting_regressor": "forest",
            "hist_gradient_boosting_classifier": "forest",
        }
        raw_out = config.get("outcome_model", "linear_regression")
        raw_prop = config.get("propensity_model", "logistic_regression")
        params = {
            "model_type": "linear",
            "cv_folds": config.get("cv_folds", 5),
            "confidence_level": 0.95,
            "random_state": seed,
            "model_y": _model_map.get(raw_out, "linear"),
            "model_t": _model_map.get(raw_prop, "linear"),
        }
        result = DoubleMachineLearning.pure_step(state, params)
        return _extract_result(result)
