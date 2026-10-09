"""Bootstrap confidence intervals for backtest metrics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np

from polisyos.core.errors import ErrorCategory, PolicyOSError


class BootstrapValidationError(PolicyOSError):
    """Raised when bootstrap inputs are invalid for statistical evaluation."""

    default_stage = "scientist.backtesting.bootstrap"
    default_category = ErrorCategory.VALIDATION


StatisticFn = Callable[[np.ndarray], float]


@dataclass(frozen=True)
class BootstrapCI:
    """Bootstrap confidence interval with the performed statistic's identity.

    ``statistic`` is the resolved builtin selector or a caller-declared identity
    for a custom callable. Arbitrary callable identity remains unestablished
    when no declaration is supplied; declarations do not verify its semantics.
    """

    metric: str
    point_estimate: float
    lower: float
    upper: float
    confidence_level: float
    n_bootstrap: int
    statistic: str | None = None
    statistic_identity_basis: Literal["recomputed", "consumer_asserted", "not_established"] = (
        "not_established"
    )


def bootstrap_metric(
    values: list[float] | np.ndarray,
    *,
    metric: str = "mean",
    statistic: str | StatisticFn = "mean",
    statistic_id: str | None = None,
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
        One of "mean", "median", "std", or a custom callable.
    statistic_id:
        Optional identity declaration for a custom callable's scientific
        definition. It is retained as ``consumer_asserted``, never inferred
        from a callable's name or treated as verified functional identity.
        Builtin selectors already have a resolved identity and reject this
        argument. Omitting it preserves anonymous callable support.
    confidence_level:
        CI level (default 0.95).
    n_bootstrap:
        Number of resamples.
    seed:
        Random seed for reproducibility.
    """
    arr = _prepare_observations(values, entrypoint="bootstrap_metric")
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

    stat_fn = _resolve_statistic(statistic)
    if statistic_id is not None and (not isinstance(statistic_id, str) or not statistic_id.strip()):
        raise BootstrapValidationError(
            "statistic_id must be a non-empty string when supplied",
            code="invalid_statistic_id",
        )
    if not callable(statistic) and statistic_id is not None:
        raise BootstrapValidationError(
            "statistic_id is only supported for custom callable statistics",
            code="builtin_statistic_id_override",
        )
    point = _evaluate_statistic(stat_fn, arr)

    rng = np.random.default_rng(seed)
    boot_stats = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample = rng.choice(arr, size=arr.size, replace=True)
        boot_stats[i] = _evaluate_statistic(stat_fn, sample)

    alpha = 1.0 - confidence_level
    lower = float(np.percentile(boot_stats, 100 * alpha / 2))
    upper = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))
    if not np.isfinite([lower, upper]).all():
        raise BootstrapValidationError(
            "bootstrap confidence interval must be finite",
            code="non_finite_interval",
        )

    return BootstrapCI(
        metric=metric,
        point_estimate=point,
        lower=lower,
        upper=upper,
        confidence_level=confidence_level,
        n_bootstrap=n_bootstrap,
        statistic=statistic_id if callable(statistic) else statistic,
        statistic_identity_basis=(
            "consumer_asserted"
            if callable(statistic) and statistic_id is not None
            else "not_established"
            if callable(statistic)
            else "recomputed"
        ),
    )


def bootstrap_scenario_metrics(
    errors: list[float],
    *,
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
    seed: int | None = None,
) -> dict[str, BootstrapCI]:
    """Compute bootstrap CIs for RMSE, MAE, and MAPE-like statistics."""
    arr = _prepare_observations(errors, entrypoint="bootstrap_scenario_metrics")
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
        statistic_id="root_mean_square",
        confidence_level=confidence_level,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )

    return results


def _prepare_observations(
    values: list[float] | np.ndarray,
    *,
    entrypoint: str,
) -> np.ndarray:
    """Validate a bootstrap observation vector before callbacks or RNG use.

    Bootstrap resampling treats each input element as one exchangeable
    observation. Accepting a matrix and letting NumPy's scalar reducers flatten
    or aggregate it would silently change that sampling unit.
    """
    try:
        arr = np.asarray(values, dtype=float)
    except (OverflowError, TypeError, ValueError) as exc:
        raise BootstrapValidationError(
            f"{entrypoint} requires numeric observed values",
            code="invalid_values",
        ) from exc

    if arr.ndim != 1:
        raise BootstrapValidationError(
            f"{entrypoint} requires one-dimensional observations",
            code="invalid_dimensions",
            details={"ndim": arr.ndim},
        )
    if arr.size == 0:
        raise BootstrapValidationError(
            f"{entrypoint} requires at least one observed value",
            code="empty_values",
        )
    if not np.isfinite(arr).all():
        raise BootstrapValidationError(
            f"{entrypoint} requires finite observed values",
            code="non_finite_values",
        )
    return arr


def _resolve_statistic(statistic: str | StatisticFn) -> StatisticFn:
    if callable(statistic):
        return statistic
    if isinstance(statistic, str) and statistic in _STAT_FNS:
        return _STAT_FNS[statistic]
    raise BootstrapValidationError(
        f"Unknown bootstrap statistic: {statistic!r}",
        code="unknown_statistic",
        details={"statistic": repr(statistic)},
    )


def _evaluate_statistic(stat_fn: StatisticFn, values: np.ndarray) -> float:
    """Evaluate a statistic and reject non-scalar or non-finite results."""
    raw_result = stat_fn(values)
    try:
        result = float(raw_result)
    except (OverflowError, TypeError, ValueError) as exc:
        raise BootstrapValidationError(
            "bootstrap statistic must return a finite scalar",
            code="invalid_statistic_result",
        ) from exc
    if not np.isfinite(result):
        raise BootstrapValidationError(
            "bootstrap statistic must return a finite result",
            code="non_finite_statistic",
        )
    return result


def _rmse_statistic(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(values**2)))


_STAT_FNS = {
    "mean": np.mean,
    "median": np.median,
    "std": lambda x: np.std(x, ddof=1) if len(x) > 1 else 0.0,
}
