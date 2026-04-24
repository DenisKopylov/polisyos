"""Raw zepid adapters — direct library calls for ATE estimation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from benchmarks.honest_comparison.adapters.base import EstimatorResult


def _to_df(X: np.ndarray, T: np.ndarray, Y: np.ndarray) -> pd.DataFrame:
    """Convert arrays to DataFrame expected by zepid."""
    cols = {f"X{i}": X[:, i] for i in range(X.shape[1])}
    cols["T"] = T
    cols["Y"] = Y
    return pd.DataFrame(cols)


def _covariate_formula(p: int) -> str:
    return " + ".join(f"X{i}" for i in range(p))


class RawZepidTMLE:
    name = "Raw_Zepid_TMLE"
    library = "zepid"

    def supports_cate(self) -> bool:
        return False

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from zepid.causal.doublyrobust import TMLE

        df = _to_df(X, T, Y)
        p = X.shape[1]
        cov_formula = _covariate_formula(p)

        tmle = TMLE(df, exposure="T", outcome="Y")
        tmle.exposure_model(cov_formula, print_results=False)
        tmle.outcome_model(f"T + {cov_formula}", print_results=False)
        tmle.fit()

        return EstimatorResult(
            ate=float(tmle.average_treatment_effect),
            ci_lower=float(tmle.average_treatment_effect_ci[0]),
            ci_upper=float(tmle.average_treatment_effect_ci[1]),
        )


class RawZepidIPTW:
    name = "Raw_Zepid_IPTW"
    library = "zepid"

    def supports_cate(self) -> bool:
        return False

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from zepid.causal.ipw import IPTW

        df = _to_df(X, T, Y)
        p = X.shape[1]
        cov_formula = _covariate_formula(p)

        ipt = IPTW(df, treatment="T", outcome="Y")
        ipt.treatment_model(cov_formula, print_results=False)
        # zepid prepends "outcome ~" internally — only pass the RHS
        ipt.marginal_structural_model("T")
        ipt.fit()

        # Result stored in ipt.average_treatment_effect DataFrame (index = label names)
        ate_df = ipt.average_treatment_effect
        ate = float(ate_df.loc["T", "ATE"])
        se = float(ate_df.loc["T", "SE(ATE)"])

        return EstimatorResult(
            ate=ate,
            ate_se=se,
            ci_lower=ate - 1.96 * se,
            ci_upper=ate + 1.96 * se,
        )


class RawZepidAIPTW:
    name = "Raw_Zepid_AIPTW"
    library = "zepid"

    def supports_cate(self) -> bool:
        return False

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from zepid.causal.doublyrobust import AIPTW

        df = _to_df(X, T, Y)
        p = X.shape[1]
        cov_formula = _covariate_formula(p)

        aiptw = AIPTW(df, exposure="T", outcome="Y")
        aiptw.exposure_model(cov_formula, print_results=False)
        aiptw.outcome_model(f"T + {cov_formula}", print_results=False)
        aiptw.fit()

        return EstimatorResult(
            ate=float(aiptw.average_treatment_effect),
            ci_lower=float(aiptw.average_treatment_effect_ci[0]),
            ci_upper=float(aiptw.average_treatment_effect_ci[1]),
        )
