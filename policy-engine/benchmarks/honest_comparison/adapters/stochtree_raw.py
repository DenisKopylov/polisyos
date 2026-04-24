"""Raw stochtree BCF adapter (optional)."""

from __future__ import annotations

import numpy as np

from benchmarks.honest_comparison.adapters.base import EstimatorResult


class RawBCF:
    name = "Raw_StochTree_BCF"
    library = "stochtree"

    def supports_cate(self) -> bool:
        return True

    def fit_predict(self, X, T, Y, config, seed) -> EstimatorResult:
        from stochtree import BCFModel

        bcf = BCFModel()
        bcf.sample(
            X_train=X,
            Z_train=T.astype(int),
            y_train=Y,
            X_test=X,
            Z_test=T.astype(int),
            num_gfr=10,
            num_burnin=100,
            num_mcmc=200,
        )

        tau_hat = bcf.tau_hat_test  # posterior mean of CATE
        if tau_hat.ndim == 2:
            cate = tau_hat.mean(axis=1)
        else:
            cate = tau_hat.flatten()

        ate = float(np.mean(cate))
        # Posterior uncertainty
        if tau_hat.ndim == 2:
            ate_draws = tau_hat.mean(axis=0)
            se = float(np.std(ate_draws, ddof=1))
        else:
            se = float(np.std(cate) / np.sqrt(len(cate)))

        return EstimatorResult(
            ate=ate,
            ate_se=se,
            ci_lower=ate - 1.96 * se,
            ci_upper=ate + 1.96 * se,
            cate=cate,
        )
