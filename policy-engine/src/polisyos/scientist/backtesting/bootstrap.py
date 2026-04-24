"""Bootstrap confidence intervals for backtest metrics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from polisyos.core.errors import ErrorCategory, PolicyOSError


class BootstrapValidationError(PolicyOSError):
    """Raised when bootstrap inputs are invalid for statistical evaluation."""

    default_stage = "scientist.backtesting.bootstrap"
    default_category = ErrorCategory.VALIDATION


StatisticFn = Callable[[np.ndarray], float]


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
    statistic: str | StatisticFn = "mean",
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
        raise BootstrapValidationError(
            "bootstrap_metric requires at least one observed value",
            code="empty_values",
        )
    if n_bootstrap <= 0:
        raise BootstrapValidationError(
            "n_bootstrap must be greater than zero",
            code="invalid_n_bootstrap",
            details={"n_bootstrap": n_bootstrap},
        )
    if not 0.0 < confidence_level < 1.0:
        raise BootstrapValidationError(
            "confidence_level must be between 0 and 1",
            code="invalid_confidence_level",
            details={"confidence_level": confidence_level},
        )

    rng = np.random.default_rng(seed)
    stat_fn = _resolve_statistic(statistic)
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
        np.abs(arr),
        metric="mae",
        statistic="mean",
        confidence_level=confidence_level,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    results["rmse"] = bootstrap_metric(
        arr,
        metric="rmse",
        statistic=_rmse_statistic,
        confidence_level=confidence_level,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )

    return results


def _resolve_statistic(statistic: str | StatisticFn) -> StatisticFn:
    if callable(statistic):
        return statistic
    return _STAT_FNS.get(statistic, np.mean)


def _rmse_statistic(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(values**2)))


_STAT_FNS = {
    "mean": np.mean,
    "median": np.median,
    "std": lambda x: np.std(x, ddof=1) if len(x) > 1 else 0.0,
}
