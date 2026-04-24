"""Raw CausalML adapters (optional — gracefully skip if not installed)."""

from __future__ import annotations

from typing import Any

import numpy as np

from benchmarks.honest_comparison.adapters.base import EstimatorResult


def _make_base_learner(config: dict[str, Any], seed: int):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import LinearRegression

    out = config.get("outcome_model", "linear_regression")
    if out == "linear_regression":
        return LinearRegression()
    return HistGradientBoostingRegressor(
        max_iter=config.get("outcome_max_iter", 200),
        max_depth=config.get("outcome_max_depth", 6),
        random_state=seed,
    )


class RawCausalMLXLearner:
    name = "Raw_CausalML_XLearner"
    library = "causalml"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from causalml.inference.meta import BaseXRegressor

        learner = _make_base_learner(config, seed)
        m = BaseXRegressor(learner=learner, control_name="control")

        # CausalML expects string treatment
        treatment_str = np.where(T == 1, "treatment", "control")
        cate = m.fit_predict(X=X, treatment=treatment_str, y=Y)
        if cate.ndim == 2:
            cate = cate[:, 0]
        cate = cate.flatten()
        ate = float(np.mean(cate))
        se = float(np.std(cate) / np.sqrt(len(cate)))

        return EstimatorResult(
            ate=ate,
            ate_se=se,
            ci_lower=ate - 1.96 * se,
            ci_upper=ate + 1.96 * se,
            cate=cate,
        )


class RawCausalMLTLearner:
    name = "Raw_CausalML_TLearner"
    library = "causalml"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from causalml.inference.meta import BaseTRegressor

        learner = _make_base_learner(config, seed)
        m = BaseTRegressor(learner=learner, control_name="control")

        treatment_str = np.where(T == 1, "treatment", "control")
        cate = m.fit_predict(X=X, treatment=treatment_str, y=Y)
        if cate.ndim == 2:
            cate = cate[:, 0]
        cate = cate.flatten()
        ate = float(np.mean(cate))
        se = float(np.std(cate) / np.sqrt(len(cate)))

        return EstimatorResult(
            ate=ate,
            ate_se=se,
            ci_lower=ate - 1.96 * se,
            ci_upper=ate + 1.96 * se,
            cate=cate,
        )
