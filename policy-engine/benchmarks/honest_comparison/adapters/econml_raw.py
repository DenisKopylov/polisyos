"""Raw EconML adapters — direct library calls, no PolicyOS wrappers."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

from benchmarks.honest_comparison.adapters.base import EstimatorResult


def _make_sklearn_models(config: dict[str, Any], seed: int):
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

    prop = config.get("propensity_model", "logistic_regression")
    out = config.get("outcome_model", "linear_regression")

    if prop == "logistic_regression":
        model_t = LogisticRegression(max_iter=1000, random_state=seed)
    else:
        model_t = HistGradientBoostingClassifier(
            max_iter=config.get("propensity_max_iter", 200),
            max_depth=config.get("propensity_max_depth", 6),
            random_state=seed,
        )

    if out == "linear_regression":
        model_y = LinearRegression()
    else:
        model_y = HistGradientBoostingRegressor(
            max_iter=config.get("outcome_max_iter", 200),
            max_depth=config.get("outcome_max_depth", 6),
            random_state=seed,
        )

    return model_y, model_t


def _ate_from_cate(model, X, alpha: float = 0.05):
    """Extract ATE + CI from a fitted EconML model."""
    cate = model.effect(X).flatten()
    ate = float(np.mean(cate))

    try:
        inf = model.effect_inference(X)
        ci = inf.conf_int(alpha=alpha)
        ate_inf = inf.population_summary()
        se = float(ate_inf.stderr_mean) if hasattr(ate_inf, "stderr_mean") else None
        ci_lower = float(np.mean(ci[0]))
        ci_upper = float(np.mean(ci[1]))
    except Exception:
        se = float(np.std(cate) / np.sqrt(len(cate)))
        z = stats.norm.ppf(1 - alpha / 2)
        ci_lower = ate - z * se
        ci_upper = ate + z * se

    return EstimatorResult(
        ate=ate, ate_se=se, ci_lower=ci_lower, ci_upper=ci_upper, cate=cate,
    )


class RawEconMLLinearDML:
    name = "Raw_EconML_LinearDML"
    library = "econml"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from econml.dml import LinearDML
        model_y, model_t = _make_sklearn_models(config, seed)
        m = LinearDML(
            model_y=model_y, model_t=model_t,
            discrete_treatment=True,
            cv=config.get("cv_folds", 5), random_state=seed,
        )
        m.fit(Y, T, X=X)
        return _ate_from_cate(m, X)


class RawEconMLCausalForestDML:
    name = "Raw_EconML_CausalForestDML"
    library = "econml"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from econml.dml import CausalForestDML
        model_y, model_t = _make_sklearn_models(config, seed)
        m = CausalForestDML(
            model_y=model_y, model_t=model_t,
            discrete_treatment=True,
            n_estimators=200, min_samples_leaf=5, max_samples=0.5,
            cv=config.get("cv_folds", 5), random_state=seed,
        )
        m.fit(Y, T, X=X)
        return _ate_from_cate(m, X)


class RawEconMLXLearner:
    name = "Raw_EconML_XLearner"
    library = "econml"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from econml.metalearners import XLearner
        model_y, model_t = _make_sklearn_models(config, seed)
        m = XLearner(models=model_y, propensity_model=model_t)
        m.fit(Y, T, X=X)
        cate = m.effect(X).flatten()
        ate = float(np.mean(cate))
        se = float(np.std(cate) / np.sqrt(len(cate)))
        return EstimatorResult(
            ate=ate, ate_se=se,
            ci_lower=ate - 1.96 * se, ci_upper=ate + 1.96 * se,
            cate=cate,
        )


class RawEconMLTLearner:
    name = "Raw_EconML_TLearner"
    library = "econml"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from econml.metalearners import TLearner
        model_y, _ = _make_sklearn_models(config, seed)
        m = TLearner(models=model_y)
        m.fit(Y, T, X=X)
        cate = m.effect(X).flatten()
        ate = float(np.mean(cate))
        se = float(np.std(cate) / np.sqrt(len(cate)))
        return EstimatorResult(
            ate=ate, ate_se=se,
            ci_lower=ate - 1.96 * se, ci_upper=ate + 1.96 * se,
            cate=cate,
        )


class RawEconMLForestDR:
    name = "Raw_EconML_ForestDR"
    library = "econml"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from econml.dr import ForestDRLearner
        model_y, model_t = _make_sklearn_models(config, seed)
        min_prop = config.get("overlap_trimming_lower", 0.01)
        m = ForestDRLearner(
            model_regression=model_y, model_propensity=model_t,
            min_propensity=min_prop,
            n_estimators=200, min_samples_leaf=5,
            cv=config.get("cv_folds", 5), random_state=seed,
        )
        m.fit(Y, T, X=X)
        return _ate_from_cate(m, X)


class RawEconMLDRLearner:
    name = "Raw_EconML_DRLearner"
    library = "econml"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from econml.dr import DRLearner
        model_y, model_t = _make_sklearn_models(config, seed)
        min_prop = config.get("overlap_trimming_lower", 0.01)
        m = DRLearner(
            model_regression=model_y, model_propensity=model_t,
            min_propensity=min_prop,
            cv=config.get("cv_folds", 5), random_state=seed,
        )
        m.fit(Y, T, X=X)
        return _ate_from_cate(m, X)
