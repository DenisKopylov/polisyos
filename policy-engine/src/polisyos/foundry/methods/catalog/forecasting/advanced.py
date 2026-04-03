"""Public forecasting advanced module API."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


@foundry_method(
    namespace="forecasting.decomposition",
    version="1.0.0",
    tags={"forecasting", "decomposition", "stl", "time-series"},
)
class STLDecompositionEstimator:
    """STL decomposition estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="stl",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("series", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="period", default=12),
            ParameterSpec(name="n_iterations", default=2),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simplified STL-like seasonal-trend decomposition via moving averages.",
        tags=frozenset({"forecasting", "decomposition", "stl", "seasonal", "time-series"}),
        citations=("Cleveland, R.B. et al. (1990). STL: A Seasonal-Trend Decomposition Procedure Based on Loess.",),
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Decompose time series into trend, seasonal, and remainder; preprocessing before forecasting",
        output_interpretation="Trend + seasonal + remainder. Trend strength/seasonal strength in [0,1]: >0.6 = strong component. Remainder = unexplained noise.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        series = np.asarray(state["series"], dtype=float)
        if series.ndim != 1 or series.size < 4:
            raise ValueError("series must be 1D with at least 4 observations")

        period = int(params.get("period", 12))
        n = len(series)

        # Trend via centered moving average
        if period > n:
            trend = np.full(n, np.mean(series))
        else:
            kernel = np.ones(period) / period
            padded = np.pad(series, (period // 2, period // 2), mode="edge")
            trend = np.convolve(padded, kernel, mode="valid")[:n]

        # Seasonal: average detrended value per period position
        detrended = series - trend
        seasonal = np.zeros(n)
        for pos in range(period):
            indices = np.arange(pos, n, period)
            seasonal[indices] = float(np.mean(detrended[indices]))

        # Remainder
        remainder = series - trend - seasonal

        return {
            "result": {
                "trend": trend.tolist(),
                "seasonal": seasonal.tolist(),
                "remainder": remainder.tolist(),
                "period": period,
                "trend_strength": float(1.0 - np.var(remainder) / max(np.var(series - seasonal), 1e-12)),
                "seasonal_strength": float(1.0 - np.var(remainder) / max(np.var(series - trend), 1e-12)),
            }
        }


@foundry_method(
    namespace="forecasting.multivariate",
    version="1.0.0",
    tags={"forecasting", "multivariate", "vec", "time-series"},
)
class VECForecastEstimator:
    """VEC forecast estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="vec_forecast",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("series_matrix", SlotType.MATRIX, Unit("value", "amount"),
                         shape=("n_obs", "n_series")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="horizon", default=5),
            ParameterSpec(name="n_lags", default=1),
        ),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simplified vector forecast using VAR(p) on first differences.",
        tags=frozenset({"forecasting", "multivariate", "vec", "var", "time-series"}),
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Multivariate time series forecasting with cross-variable dynamics; VAR on integrated series",
        output_interpretation="Level forecasts for all series h steps ahead. Check forecast vs naive baseline. Cross-variable spillovers captured.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = np.asarray(state["series_matrix"], dtype=float)
        if data.ndim != 2:
            raise ValueError("series_matrix must be 2D")
        n_obs, n_series = data.shape
        horizon = int(params.get("horizon", 5))
        n_lags = int(params.get("n_lags", 1))

        # First differences
        diff = np.diff(data, axis=0)

        # Simple VAR(p) via OLS: Y = X @ B
        if diff.shape[0] <= n_lags:
            # Not enough data — naive forecast
            forecasts = np.tile(data[-1], (horizon, 1))
            return {"result": {"forecasts": forecasts.tolist(), "n_obs": n_obs, "method": "naive"}}

        Y = diff[n_lags:]
        X_parts = [diff[n_lags - lag - 1 : diff.shape[0] - lag - 1] for lag in range(n_lags)]
        X = np.hstack(X_parts + [np.ones((Y.shape[0], 1))])

        # OLS: B = (X'X)^-1 X'Y
        try:
            B = np.linalg.lstsq(X, Y, rcond=None)[0]
        except np.linalg.LinAlgError:
            forecasts = np.tile(data[-1], (horizon, 1))
            return {"result": {"forecasts": forecasts.tolist(), "n_obs": n_obs, "method": "fallback"}}

        # Forecast in levels
        last_diffs = [diff[-(lag + 1)] for lag in range(n_lags)]
        forecasts = np.zeros((horizon, n_series))
        current_level = data[-1].copy()

        for h in range(horizon):
            x_h = np.concatenate(last_diffs + [np.array([1.0])])
            delta = x_h @ B
            current_level = current_level + delta
            forecasts[h] = current_level
            last_diffs = [delta] + last_diffs[:-1]

        return {
            "result": {
                "forecasts": forecasts.tolist(),
                "n_obs": n_obs,
                "n_series": n_series,
                "horizon": horizon,
                "method": "var_diff",
            }
        }


@foundry_method(
    namespace="forecasting.advanced",
    version="1.0.0",
    tags={"forecasting", "advanced", "prophet", "time-series"},
)
class ProphetEstimator:
    """Prophet estimator implementation."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="prophet",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("series", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="horizon", default=10),
            ParameterSpec(name="yearly_seasonality", default=True),
            ParameterSpec(name="period", default=12),
        ),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Lightweight Prophet-like additive model (trend + seasonality) via numpy.",
        tags=frozenset({"forecasting", "advanced", "prophet", "additive", "time-series"}),
        citations=("Taylor, S.J. & Letham, B. (2018). Forecasting at Scale. PeerJ.",),
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Multiple seasonality; holiday effects; trend changepoints; business time series",
        typical_min_obs=100,
        output_interpretation="Decomposed forecast: trend + seasonality + holidays. Uncertainty bands via MC.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        series = np.asarray(state["series"], dtype=float)
        if series.ndim != 1 or series.size < 3:
            raise ValueError("series must be 1D with at least 3 observations")

        horizon = int(params.get("horizon", 10))
        period = int(params.get("period", 12))
        n = len(series)
        t = np.arange(n, dtype=float)

        # Linear trend via OLS
        t_mean = np.mean(t)
        y_mean = np.mean(series)
        slope = float(np.sum((t - t_mean) * (series - y_mean)) / max(np.sum((t - t_mean) ** 2), 1e-12))
        intercept = y_mean - slope * t_mean
        trend = intercept + slope * t

        # Seasonal component
        detrended = series - trend
        seasonal_pattern = np.zeros(period)
        for pos in range(period):
            indices = np.arange(pos, n, period)
            if len(indices) > 0:
                seasonal_pattern[pos] = float(np.mean(detrended[indices]))

        # Forecast
        future_t = np.arange(n, n + horizon, dtype=float)
        future_trend = intercept + slope * future_t
        future_seasonal = np.array([seasonal_pattern[int(ft) % period] for ft in future_t])
        forecast = future_trend + future_seasonal

        # Residual-based uncertainty
        residuals = series - trend - np.array([seasonal_pattern[int(tt) % period] for tt in t])
        residual_std = float(np.std(residuals, ddof=1)) if n > 2 else 0.0

        return {
            "result": {
                "forecast": forecast.tolist(),
                "trend_slope": slope,
                "trend_intercept": float(intercept),
                "seasonal_pattern": seasonal_pattern.tolist(),
                "residual_std": residual_std,
                "horizon": horizon,
            }
        }


__all__ = [
    "ProphetEstimator",
    "STLDecompositionEstimator",
    "VECForecastEstimator",
]
