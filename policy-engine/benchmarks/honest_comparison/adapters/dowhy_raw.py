"""Raw DoWhy adapters — direct library calls."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from benchmarks.honest_comparison.adapters.base import EstimatorResult


def _to_df(X: np.ndarray, T: np.ndarray, Y: np.ndarray) -> pd.DataFrame:
    cols = {f"X{i}": X[:, i] for i in range(X.shape[1])}
    cols["T"] = T
    cols["Y"] = Y
    return pd.DataFrame(cols)


class RawDoWhyLinear:
    name = "Raw_DoWhy_Linear"
    library = "dowhy"

    def supports_cate(self) -> bool:
        return False

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        import dowhy

        df = _to_df(X, T, Y)
        p = X.shape[1]
        common_causes = [f"X{i}" for i in range(p)]

        model = dowhy.CausalModel(
            data=df,
            treatment="T",
            outcome="Y",
            common_causes=common_causes,
        )
        identified = model.identify_effect(proceed_when_unidentifiable=True)
        estimate = model.estimate_effect(
            identified,
            method_name="backdoor.linear_regression",
            confidence_intervals=True,
            test_significance=True,
        )

        ate = float(estimate.value)
        ci = estimate.get_confidence_intervals()
        # ci is a 2D array [[lower, upper]]
        if ci is not None:
            ci_arr = np.array(ci).flatten()
            ci_lower = float(ci_arr[0])
            ci_upper = float(ci_arr[1])
        else:
            ci_lower = ate - 1.96
            ci_upper = ate + 1.96

        return EstimatorResult(ate=ate, ci_lower=ci_lower, ci_upper=ci_upper)


class RawDoWhyIPW:
    name = "Raw_DoWhy_IPW"
    library = "dowhy"

    def supports_cate(self) -> bool:
        return False

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        import dowhy

        df = _to_df(X, T, Y)
        p = X.shape[1]
        common_causes = [f"X{i}" for i in range(p)]

        model = dowhy.CausalModel(
            data=df,
            treatment="T",
            outcome="Y",
            common_causes=common_causes,
        )
        identified = model.identify_effect(proceed_when_unidentifiable=True)
        estimate = model.estimate_effect(
            identified,
            method_name="backdoor.propensity_score_weighting",
            confidence_intervals=True,
            test_significance=True,
        )

        ate = float(estimate.value)
        ci = estimate.get_confidence_intervals()
        if ci is not None:
            ci_arr = np.array(ci).flatten()
            ci_lower = float(ci_arr[0])
            ci_upper = float(ci_arr[1])
        else:
            ci_lower = ate - 1.96
            ci_upper = ate + 1.96

        return EstimatorResult(ate=ate, ci_lower=ci_lower, ci_upper=ci_upper)
