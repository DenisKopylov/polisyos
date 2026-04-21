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
from polisyos.foundry.methods.catalog.forecasting.uncertainty import (
    build_attached_output_bundle,
    build_residual_conformal_bundle,
    forecasting_output_slots,
    resolve_artifact_store,
)

def _stl_result(series: np.ndarray, *, period: int) -> dict[str, Any]:
    n = len(series)

    if period > n:
        trend = np.full(n, np.mean(series))
    else:
        kernel = np.ones(period) / period
        padded = np.pad(series, (period // 2, period // 2), mode="edge")
        trend = np.convolve(padded, kernel, mode="valid")[:n]

    detrended = series - trend
    seasonal = np.zeros(n)
    for pos in range(period):
        indices = np.arange(pos, n, period)
        seasonal[indices] = float(np.mean(detrended[indices]))

    remainder = series - trend - seasonal
    return {
        "trend": trend.tolist(),
        "seasonal": seasonal.tolist(),
        "remainder": remainder.tolist(),
        "period": period,
        "trend_strength": float(1.0 - np.var(remainder) / max(np.var(series - seasonal), 1e-12)),
        "seasonal_strength": float(1.0 - np.var(remainder) / max(np.var(series - trend), 1e-12)),
    }


def _vec_result(data: np.ndarray, *, horizon: int, n_lags: int) -> dict[str, Any]:
    n_obs, n_series = data.shape
    diff = np.diff(data, axis=0)
    if diff.shape[0] <= n_lags:
        forecasts = np.tile(data[-1], (horizon, 1))
        return {"forecasts": forecasts.tolist(), "n_obs": n_obs, "n_series": n_series, "horizon": horizon, "method": "naive"}

    Y = diff[n_lags:]
    X_parts = [diff[n_lags - lag - 1 : diff.shape[0] - lag - 1] for lag in range(n_lags)]
    X = np.hstack(X_parts + [np.ones((Y.shape[0], 1))])

    try:
        B = np.linalg.lstsq(X, Y, rcond=None)[0]
    except np.linalg.LinAlgError:
        forecasts = np.tile(data[-1], (horizon, 1))
        return {"forecasts": forecasts.tolist(), "n_obs": n_obs, "n_series": n_series, "horizon": horizon, "method": "fallback"}

    last_diffs = [diff[-(lag + 1)] for lag in range(n_lags)]
    forecasts = np.zeros((horizon, n_series))
    current_level = data[-1].copy()

    for step in range(horizon):
        x_h = np.concatenate(last_diffs + [np.array([1.0])])
        delta = x_h @ B
        current_level = current_level + delta
        forecasts[step] = current_level
        last_diffs = [delta] + last_diffs[:-1]

    return {
        "forecasts": forecasts.tolist(),
        "n_obs": n_obs,
        "n_series": n_series,
        "horizon": horizon,
        "method": "var_diff",
    }


def _prophet_result(series: np.ndarray, *, horizon: int, period: int) -> dict[str, Any]:
    n = len(series)
    t = np.arange(n, dtype=float)

    t_mean = np.mean(t)
    y_mean = np.mean(series)
    slope = float(np.sum((t - t_mean) * (series - y_mean)) / max(np.sum((t - t_mean) ** 2), 1e-12))
    intercept = y_mean - slope * t_mean
    trend = intercept + slope * t

    detrended = series - trend
    seasonal_pattern = np.zeros(period)
    for pos in range(period):
        indices = np.arange(pos, n, period)
        if len(indices) > 0:
            seasonal_pattern[pos] = float(np.mean(detrended[indices]))

    future_t = np.arange(n, n + horizon, dtype=float)
    future_trend = intercept + slope * future_t
    future_seasonal = np.array([seasonal_pattern[int(ft) % period] for ft in future_t])
    forecast = future_trend + future_seasonal

    residuals = series - trend - np.array([seasonal_pattern[int(tt) % period] for tt in t])
    residual_std = float(np.std(residuals, ddof=1)) if n > 2 else 0.0
    return {
        "forecast": forecast.tolist(),
        "trend_slope": slope,
        "trend_intercept": float(intercept),
        "seasonal_pattern": seasonal_pattern.tolist(),
        "residual_std": residual_std,
        "horizon": horizon,
    }


def _vec_predictive_paths(
    data: np.ndarray,
    *,
    horizon: int,
    n_lags: int,
    n_draws: int,
    random_seed: int,
) -> np.ndarray:
    point = np.asarray(_vec_result(data, horizon=horizon, n_lags=n_lags)["forecasts"], dtype=float)
    if n_draws <= 0:
        return np.empty((0,) + point.shape, dtype=float)

    diff = np.diff(data, axis=0)
    if diff.shape[0] <= n_lags:
        return np.repeat(point[None, :, :], n_draws, axis=0)

    y = diff[n_lags:]
    x_parts = [diff[n_lags - lag - 1 : diff.shape[0] - lag - 1] for lag in range(n_lags)]
    x = np.hstack(x_parts + [np.ones((y.shape[0], 1))])
    try:
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        residuals = y - x @ beta
    except np.linalg.LinAlgError:
        return np.repeat(point[None, :, :], n_draws, axis=0)

    if residuals.size == 0:
        return np.repeat(point[None, :, :], n_draws, axis=0)

    rng = np.random.default_rng(random_seed)
    paths = np.zeros((n_draws, horizon, data.shape[1]), dtype=float)
    for draw in range(n_draws):
        current_level = np.asarray(data[-1], dtype=float).copy()
        last_diffs = [diff[-(lag + 1)].copy() for lag in range(n_lags)]
        for step in range(horizon):
            x_h = np.concatenate(last_diffs + [np.array([1.0])])
            innovation = residuals[rng.integers(0, residuals.shape[0])]
            delta = x_h @ beta + innovation
            current_level = current_level + delta
            paths[draw, step] = current_level
            last_diffs = [delta] + last_diffs[:-1]
    return paths


def _prophet_predictive_paths(
    series: np.ndarray,
    *,
    horizon: int,
    period: int,
    n_draws: int,
    random_seed: int,
) -> np.ndarray:
    result = _prophet_result(series, horizon=horizon, period=period)
    point = np.asarray(result["forecast"], dtype=float)
    if n_draws <= 0:
        return np.empty((0, horizon), dtype=float)
    residual_std = float(result["residual_std"])
    if residual_std <= 0.0:
        return np.repeat(point[None, :], n_draws, axis=0)
    rng = np.random.default_rng(random_seed)
    scales = residual_std * np.sqrt(np.arange(1, horizon + 1, dtype=float))
    noise = rng.normal(loc=0.0, scale=scales, size=(n_draws, horizon))
    return point[None, :] + noise


@foundry_method(
    namespace="forecasting.decomposition",
    version="1.0.0",
    tags={"forecasting", "decomposition", "stl", "time-series"},
)
class STLDecompositionEstimator:
    """Decompose a series into seasonal, trend, and remainder parts before downstream forecasting."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="stl",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("series", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=forecasting_output_slots(),
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
        output_interpretation=(
            "Trend + seasonal + remainder, plus a non-gate-eligible forecasting_uncertainty_bundle "
            "that explicitly marks STL as attached-output-only until a downstream forecaster is chosen."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        series = np.asarray(state["series"], dtype=float)
        if series.ndim != 1 or series.size < 4:
            raise ValueError("series must be 1D with at least 4 observations")

        period = int(params.get("period", 12))
        return {
            "result": _stl_result(series, period=period),
            "forecasting_uncertainty_bundle": build_attached_output_bundle(
                method_fqn="forecasting.decomposition.stl@1.0.0",
                target_id="decomposition_artifacts",
                note=(
                    "STL decomposition is not a standalone interval-producing forecaster; "
                    "uncertainty must be attached after downstream forecasting and recomposition."
                ),
            ),
        }


@foundry_method(
    namespace="forecasting.multivariate",
    version="1.0.0",
    tags={"forecasting", "multivariate", "vec", "time-series"},
)
class VECForecastEstimator:
    """Forecast cointegrated multivariate series with a vector error-correction model."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="vec_forecast",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("series_matrix", SlotType.MATRIX, Unit("value", "amount"),
                         shape=("n_obs", "n_series")),
            }
        ),
        output_slots=forecasting_output_slots(),
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
        output_interpretation=(
            "Level forecasts for all series h steps ahead plus forecasting_uncertainty_bundle. "
            "Phase 0 exposes multivariate marginal residual/conformal-style intervals; joint predictive regions remain future work."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = np.asarray(state["series_matrix"], dtype=float)
        if data.ndim != 2:
            raise ValueError("series_matrix must be 2D")
        horizon = int(params.get("horizon", 5))
        n_lags = int(params.get("n_lags", 1))
        artifact_store = resolve_artifact_store(state, params)
        predictive_draws = int(params.get("predictive_draws", 64 if artifact_store is not None else 0))
        random_seed = int(params.get("random_seed", 0))
        result = _vec_result(data, horizon=horizon, n_lags=n_lags)
        return {
            "result": result,
            "forecasting_uncertainty_bundle": build_residual_conformal_bundle(
                method_fqn="forecasting.multivariate.vec_forecast@1.0.0",
                target_id="series_matrix",
                history=data,
                point_forecast=np.asarray(result["forecasts"], dtype=float),
                forecast_fn=lambda train, h: np.asarray(
                    _vec_result(np.asarray(train, dtype=float), horizon=h, n_lags=n_lags)["forecasts"],
                    dtype=float,
                ),
                min_train_size=max(3, n_lags + 2),
                method_note=(
                    "Phase 0 emits multivariate marginal residual conformal intervals; "
                    "joint CVAR-style posterior predictive regions remain a future upgrade."
                ),
                extra_regime_flags=("joint_region_not_emitted",),
                artifact_store=artifact_store,
                posterior_predictive_samples=(
                    _vec_predictive_paths(
                        data,
                        horizon=horizon,
                        n_lags=n_lags,
                        n_draws=predictive_draws,
                        random_seed=random_seed,
                    )
                    if predictive_draws > 0
                    else None
                ),
            ),
        }


@foundry_method(
    namespace="forecasting.advanced",
    version="1.0.0",
    tags={"forecasting", "advanced", "prophet", "time-series"},
)
class ProphetEstimator:
    """Generate calendar-aware forecasts with Prophet-style trend and seasonality components."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="prophet",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("series", SlotType.VECTOR, Unit("value", "amount"), shape=("n_obs",)),
            }
        ),
        output_slots=forecasting_output_slots(),
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
        output_interpretation=(
            "Decomposed forecast plus forecasting_uncertainty_bundle. "
            "Phase 0 does not advertise raw Prophet-style MC bands as calibrated; the bundle uses residual/conformal-style recalibration."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        series = np.asarray(state["series"], dtype=float)
        if series.ndim != 1 or series.size < 3:
            raise ValueError("series must be 1D with at least 3 observations")

        horizon = int(params.get("horizon", 10))
        period = int(params.get("period", 12))
        artifact_store = resolve_artifact_store(state, params)
        predictive_draws = int(params.get("predictive_draws", 64 if artifact_store is not None else 0))
        random_seed = int(params.get("random_seed", 0))
        result = _prophet_result(series, horizon=horizon, period=period)
        return {
            "result": result,
            "forecasting_uncertainty_bundle": build_residual_conformal_bundle(
                method_fqn="forecasting.advanced.prophet@1.0.0",
                target_id="series",
                history=series,
                point_forecast=np.asarray(result["forecast"], dtype=float),
                forecast_fn=lambda train, h: np.asarray(
                    _prophet_result(np.asarray(train, dtype=float), horizon=h, period=period)["forecast"],
                    dtype=float,
                ),
                min_train_size=3,
                method_note=(
                    "Raw Prophet-style bands are not treated as calibrated in Phase 0; "
                    "the lightweight backend publishes residual conformal recalibration instead."
                ),
                extra_regime_flags=("raw_prophet_bands_not_exported",),
                artifact_store=artifact_store,
                posterior_predictive_samples=(
                    _prophet_predictive_paths(
                        series,
                        horizon=horizon,
                        period=period,
                        n_draws=predictive_draws,
                        random_seed=random_seed,
                    )
                    if predictive_draws > 0
                    else None
                ),
            ),
        }


__all__ = [
    "ProphetEstimator",
    "STLDecompositionEstimator",
    "VECForecastEstimator",
]
