"""Baseline estimators: OLS and naive difference-in-means (numpy only)."""

from __future__ import annotations

from typing import Any

import numpy as np

from benchmarks.honest_comparison.adapters.base import EstimatorResult


class OLSBaseline:
    name = "OLS_Baseline"
    library = "numpy"

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
        n, p = X.shape
        # Regress Y on [X, T] via OLS
        design = np.column_stack([np.ones(n), X, T.reshape(-1, 1)])
        beta, _, _, _ = np.linalg.lstsq(design, Y, rcond=None)
        ate = float(beta[-1])

        # Bootstrap SE
        rng = np.random.default_rng(seed)
        n_boot = config.get("bootstrap_draws", 200)
        boot_ates = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n, n)
            b_beta, _, _, _ = np.linalg.lstsq(design[idx], Y[idx], rcond=None)
            boot_ates[b] = b_beta[-1]
        se = float(np.std(boot_ates, ddof=1))

        return EstimatorResult(
            ate=ate,
            ate_se=se,
            ci_lower=ate - 1.96 * se,
            ci_upper=ate + 1.96 * se,
        )


class NaiveDiffMeans:
    name = "Naive_DiffMeans"
    library = "numpy"

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
        treated = T.astype(bool)
        ate = float(np.mean(Y[treated]) - np.mean(Y[~treated]))

        rng = np.random.default_rng(seed)
        n = len(Y)
        n_boot = config.get("bootstrap_draws", 200)
        boot_ates = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n, n)
            t_b, y_b = T[idx].astype(bool), Y[idx]
            if t_b.sum() == 0 or (~t_b).sum() == 0:
                boot_ates[b] = np.nan
            else:
                boot_ates[b] = np.mean(y_b[t_b]) - np.mean(y_b[~t_b])
        se = float(np.nanstd(boot_ates, ddof=1))

        return EstimatorResult(
            ate=ate,
            ate_se=se,
            ci_lower=ate - 1.96 * se,
            ci_upper=ate + 1.96 * se,
        )
