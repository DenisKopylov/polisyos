"""Bootstrap confidence intervals for backtest metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class BootstrapCI:
    """Bootstrap confidence interval result."""

    metric: str
    point_estimate: float
    lower: float
    upper: float
    confidence_level: float
    n_bootstrap: int


def bootstrap_metric(
    values: list[float] | np.ndarray,
    *,
    metric: str = "mean",
    statistic: str = "mean",
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
    seed: int | None = None,
) -> BootstrapCI:
    """Compute bootstrap confidence interval for a statistic.

    Parameters
    ----------
    values:
        Observed values.
    metric:
        Name label for the metric.
    statistic:
        One of "mean", "median", "std".
    confidence_level:
        CI level (default 0.95).
    n_bootstrap:
        Number of resamples.
    seed:
        Random seed for reproducibility.
    """
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return BootstrapCI(
            metric=metric,
            point_estimate=0.0,
            lower=0.0,
            upper=0.0,
            confidence_level=confidence_level,
            n_bootstrap=n_bootstrap,
        )

    rng = np.random.default_rng(seed)
    stat_fn = _STAT_FNS.get(statistic, np.mean)
    point = float(stat_fn(arr))

    boot_stats = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample = rng.choice(arr, size=arr.size, replace=True)
        boot_stats[i] = stat_fn(sample)

    alpha = 1.0 - confidence_level
    lower = float(np.percentile(boot_stats, 100 * alpha / 2))
    upper = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))

    return BootstrapCI(
        metric=metric,
        point_estimate=point,
        lower=lower,
        upper=upper,
        confidence_level=confidence_level,
        n_bootstrap=n_bootstrap,
    )


def bootstrap_scenario_metrics(
    errors: list[float],
    *,
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
    seed: int | None = None,
) -> dict[str, BootstrapCI]:
    """Compute bootstrap CIs for RMSE, MAE, and MAPE-like statistics."""
    arr = np.asarray(errors, dtype=float)
    results: dict[str, BootstrapCI] = {}

    results["mae"] = bootstrap_metric(
        np.abs(arr), metric="mae", statistic="mean",
        confidence_level=confidence_level, n_bootstrap=n_bootstrap, seed=seed,
    )
    results["rmse"] = bootstrap_metric(
        arr ** 2, metric="rmse", statistic="mean",
        confidence_level=confidence_level, n_bootstrap=n_bootstrap, seed=seed,
    )
    # Transform RMSE point/bounds to actual RMSE scale
    rmse = results["rmse"]
    results["rmse"] = BootstrapCI(
        metric="rmse",
        point_estimate=float(np.sqrt(max(0, rmse.point_estimate))),
        lower=float(np.sqrt(max(0, rmse.lower))),
        upper=float(np.sqrt(max(0, rmse.upper))),
        confidence_level=rmse.confidence_level,
        n_bootstrap=rmse.n_bootstrap,
    )

    return results


_STAT_FNS = {
    "mean": np.mean,
    "median": np.median,
    "std": lambda x: np.std(x, ddof=1) if len(x) > 1 else 0.0,
}
