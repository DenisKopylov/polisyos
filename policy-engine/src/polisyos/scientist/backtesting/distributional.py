"""Distributional tests for backtest residuals."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np


def _chi2_survival(statistic: float, degrees_of_freedom: int) -> float:
    """Return chi-square survival probability with a robust local fallback."""

    if statistic <= 0.0 or degrees_of_freedom <= 0:
        return 1.0
    try:
        from scipy.stats import chi2

        return float(chi2.sf(statistic, degrees_of_freedom))
    except ImportError:
        pass

    # Wilson-Hilferty normal approximation for Chi-square upper tail.
    df = float(degrees_of_freedom)
    z = ((statistic / df) ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))) / math.sqrt(
        2.0 / (9.0 * df)
    )
    return 0.5 * math.erfc(z / math.sqrt(2.0))


@dataclass(frozen=True)
class DistributionalTestResult:
    """Result of a distributional test on residuals."""

    test_name: str
    statistic: float
    p_value: float | None
    reject_null: bool
    description: str


def test_residual_normality(
    residuals: list[float] | np.ndarray,
    *,
    alpha: float = 0.05,
) -> DistributionalTestResult:
    """Test whether residuals follow a normal distribution.

    Uses Shapiro-Wilk when scipy is available, otherwise
    falls back to kurtosis/skewness heuristic.
    """
    arr = np.asarray(residuals, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size < 3:
        return DistributionalTestResult(
            test_name="normality",
            statistic=0.0,
            p_value=None,
            reject_null=False,
            description="insufficient_data",
        )

    try:
        from scipy.stats import shapiro
        stat, p_value = shapiro(arr[:5000])  # shapiro limit
        return DistributionalTestResult(
            test_name="shapiro_wilk",
            statistic=float(stat),
            p_value=float(p_value),
            reject_null=bool(p_value < alpha),
            description="scipy.shapiro_wilk",
        )
    except ImportError:
        pass

    # Fallback: Jarque-Bera approximation
    n = arr.size
    mean = np.mean(arr)
    std = np.std(arr, ddof=1)
    if std < 1e-12:
        return DistributionalTestResult(
            test_name="jarque_bera_approx",
            statistic=0.0,
            p_value=1.0,
            reject_null=False,
            description="zero_variance",
        )
    z = (arr - mean) / std
    skew = float(np.mean(z ** 3))
    kurt = float(np.mean(z ** 4) - 3.0)
    jb = (n / 6.0) * (skew ** 2 + (kurt ** 2) / 4.0)

    return DistributionalTestResult(
        test_name="jarque_bera_approx",
        statistic=float(jb),
        p_value=None,
        reject_null=bool(jb > 5.99),  # chi2(2) at 0.05
        description="jarque_bera_approximation",
    )


def test_residual_autocorrelation(
    residuals: list[float] | np.ndarray,
    *,
    max_lag: int = 5,
    alpha: float = 0.05,
) -> DistributionalTestResult:
    """Test for residual autocorrelation using the Ljung-Box Q statistic."""
    arr = np.asarray(residuals, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = arr.size

    if max_lag < 1:
        return DistributionalTestResult(
            test_name="ljung_box",
            statistic=0.0,
            p_value=None,
            reject_null=False,
            description="invalid_max_lag",
        )

    if n < max_lag + 2:
        return DistributionalTestResult(
            test_name="ljung_box",
            statistic=0.0,
            p_value=None,
            reject_null=False,
            description="insufficient_data",
        )

    mean = np.mean(arr)
    centered = arr - mean
    c0 = float(np.sum(centered ** 2)) / n

    if c0 < 1e-12:
        return DistributionalTestResult(
            test_name="ljung_box",
            statistic=0.0,
            p_value=1.0,
            reject_null=False,
            description="zero_variance",
        )

    q_stat = 0.0
    for k in range(1, max_lag + 1):
        rk = float(np.sum(centered[:n - k] * centered[k:])) / (n * c0)
        q_stat += (rk ** 2) / (n - k)
    q_stat *= n * (n + 2)
    p_value = _chi2_survival(q_stat, max_lag)
    reject = bool(p_value < alpha)

    return DistributionalTestResult(
        test_name="ljung_box",
        statistic=float(q_stat),
        p_value=float(p_value),
        reject_null=reject,
        description=f"ljung_box_Q_lag{max_lag}",
    )


def test_residual_stationarity(
    residuals: list[float] | np.ndarray,
    *,
    window_fraction: float = 0.5,
) -> DistributionalTestResult:
    """Simple stationarity check by comparing mean/variance of first vs second half."""
    arr = np.asarray(residuals, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size < 6:
        return DistributionalTestResult(
            test_name="stationarity_split",
            statistic=0.0,
            p_value=None,
            reject_null=False,
            description="insufficient_data",
        )

    split = int(len(arr) * window_fraction)
    first, second = arr[:split], arr[split:]

    mean_diff = abs(float(np.mean(first)) - float(np.mean(second)))
    var_first = float(np.var(first, ddof=1)) if len(first) > 1 else 0.0
    var_second = float(np.var(second, ddof=1)) if len(second) > 1 else 0.0
    var_ratio = max(var_first, var_second) / max(min(var_first, var_second), 1e-12)

    # Non-stationarity heuristic: large mean shift or variance ratio
    statistic = mean_diff + var_ratio
    reject = bool(var_ratio > 4.0 or mean_diff > 2 * np.sqrt(max(var_first, var_second)))

    return DistributionalTestResult(
        test_name="stationarity_split",
        statistic=float(statistic),
        p_value=None,
        reject_null=reject,
        description=f"mean_diff={mean_diff:.4f} var_ratio={var_ratio:.4f}",
    )
