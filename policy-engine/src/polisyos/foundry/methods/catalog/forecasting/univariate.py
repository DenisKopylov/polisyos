"""Public forecasting univariate module API."""
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
    build_member_spread_bundle,
    build_reconciliation_placeholder_bundle,
    build_residual_conformal_bundle,
    forecasting_output_slots,
    resolve_artifact_store,
)

def _series(state: Any, *, key: str = "series") -> np.ndarray:
    values = state.get(key) if isinstance(state, Mapping) else state
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if arr.size < 3:
        raise ValueError(f"{key} must contain at least 3 observations")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _holt_linear(series: np.ndarray, *, alpha: float, beta: float) -> tuple[float, float]:
    level = float(series[0])
    trend = float(series[1] - series[0])
    for value in series[1:]:
        prev_level = level
        level = alpha * float(value) + (1.0 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1.0 - beta) * trend
    return level, trend


def _exponential_smoothing_result(
    series: np.ndarray,
    *,
    horizon: int,
    alpha: float,
    beta: float,
) -> dict[str, Any]:
    level, trend = _holt_linear(series, alpha=alpha, beta=beta)
    forecast = [float(level + (step + 1) * trend) for step in range(horizon)]
    return {
        "forecast": forecast,
        "level": level,
        "trend": trend,
        "horizon": horizon,
    }


def _theta_result(series: np.ndarray, *, horizon: int, alpha: float) -> dict[str, Any]:
    x = np.arange(series.shape[0], dtype=float)
    slope, intercept = np.polyfit(x, series, 1)
    linear_forecast = intercept + slope * np.arange(series.shape[0], series.shape[0] + horizon, dtype=float)
    level = float(series[0])
    for value in series[1:]:
        level = alpha * float(value) + (1.0 - alpha) * level
    ses_forecast = np.full(horizon, level, dtype=float)
    forecast = 0.5 * linear_forecast + 0.5 * ses_forecast
    return {
        "forecast": forecast.tolist(),
        "linear_component": linear_forecast.tolist(),
        "ses_component": ses_forecast.tolist(),
    }


def _reconcile_sample_paths(
    bottom_sample_paths: np.ndarray,
    aggregation_matrix: np.ndarray,
) -> np.ndarray:
    paths = np.asarray(bottom_sample_paths, dtype=float)
    if paths.ndim != 3:
        raise ValueError("bottom_sample_paths must have shape (n_paths, n_bottom, horizon)")
    if paths.shape[1] != aggregation_matrix.shape[1]:
        raise ValueError("bottom_sample_paths bottom dimension must match aggregation_matrix")
    return np.einsum("ij,pjk->pik", aggregation_matrix, paths, optimize=True)


@foundry_method(
    namespace="forecasting.univariate",
    version="1.0.0",
    tags={"forecasting", "time-series", "exponential-smoothing"},
)
class ExponentialSmoothingEstimator:
    """Generate univariate baseline forecasts with exponential smoothing."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="exponential_smoothing",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {SlotSpec("series", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",))}
        ),
        output_slots=forecasting_output_slots(),
        parameters=(
            ParameterSpec(name="horizon", default=6),
            ParameterSpec(name="alpha", default=0.3),
            ParameterSpec(name="beta", default=0.1),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Holt linear exponential smoothing for univariate forecasting.",
        tags=frozenset({"forecasting", "time-series", "exponential-smoothing"}),
        declared_truthfulness_tier="approximate_calibrated",
        truthfulness_scope="marginal_coverage",
        when_to_use="Univariate forecasting with trend/seasonality components; operational forecasting",
        typical_min_obs=24,
        output_interpretation=(
            "Point forecasts plus forecasting_uncertainty_bundle. "
            "Phase 0 emits horizon-wise residual/conformal-style intervals; "
            "full state-space ETS parametric PI are not implemented in this lightweight backend."
        ),
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        series = _series(state)
        horizon = max(1, int(params.get("horizon", 6)))
        alpha = float(np.clip(float(params.get("alpha", 0.3)), 1e-6, 1.0))
        beta = float(np.clip(float(params.get("beta", 0.1)), 1e-6, 1.0))
        artifact_store = resolve_artifact_store(state if isinstance(state, Mapping) else None, params)
        result = _exponential_smoothing_result(series, horizon=horizon, alpha=alpha, beta=beta)
        return {
            "result": result,
            "forecasting_uncertainty_bundle": build_residual_conformal_bundle(
                method_fqn="forecasting.univariate.exponential_smoothing@1.0.0",
                target_id="series",
                history=series,
                point_forecast=np.asarray(result["forecast"], dtype=float),
                forecast_fn=lambda train, h: np.asarray(
                    _exponential_smoothing_result(np.asarray(train, dtype=float), horizon=h, alpha=alpha, beta=beta)["forecast"],
                    dtype=float,
                ),
                min_train_size=3,
                method_note=(
                    "Phase 0 keeps exponential smoothing on residual conformal intervals; "
                    "state-space ETS parametric intervals remain a future upgrade."
                ),
                artifact_store=artifact_store,
            ),
        }


@foundry_method(
    namespace="forecasting.univariate",
    version="1.0.0",
    tags={"forecasting", "time-series", "theta"},
)
class ThetaMethodEstimator:
    """Generate univariate forecasts with the Theta method."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="theta",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {SlotSpec("series", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",))}
        ),
        output_slots=forecasting_output_slots(),
        parameters=(
            ParameterSpec(name="horizon", default=6),
            ParameterSpec(name="alpha", default=0.2),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Theta method blending linear trend extrapolation with exponential smoothing.",
        tags=frozenset({"forecasting", "time-series", "theta"}),
        declared_truthfulness_tier="approximate_calibrated",
        truthfulness_scope="marginal_coverage",
        when_to_use="M3/M4 competition winner; robust univariate forecasting",
        typical_min_obs=12,
        output_interpretation=(
            "Forecast = 0.5 * linear trend + 0.5 * SES, plus forecasting_uncertainty_bundle. "
            "Phase 0 uses horizon-wise residual/conformal-style intervals instead of claiming full Theta state-space PI."
        ),
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        series = _series(state)
        horizon = max(1, int(params.get("horizon", 6)))
        alpha = float(np.clip(float(params.get("alpha", 0.2)), 1e-6, 1.0))
        artifact_store = resolve_artifact_store(state if isinstance(state, Mapping) else None, params)
        result = _theta_result(series, horizon=horizon, alpha=alpha)
        return {
            "result": result,
            "forecasting_uncertainty_bundle": build_residual_conformal_bundle(
                method_fqn="forecasting.univariate.theta@1.0.0",
                target_id="series",
                history=series,
                point_forecast=np.asarray(result["forecast"], dtype=float),
                forecast_fn=lambda train, h: np.asarray(
                    _theta_result(np.asarray(train, dtype=float), horizon=h, alpha=alpha)["forecast"],
                    dtype=float,
                ),
                min_train_size=3,
                method_note=(
                    "Theta intervals are emitted through residual conformal calibration in Phase 0; "
                    "short-horizon SES-with-drift parametrics are not advertised by this lightweight implementation."
                ),
                artifact_store=artifact_store,
            ),
        }


@foundry_method(
    namespace="forecasting.ensemble",
    version="1.0.0",
    tags={"forecasting", "ensemble", "time-series"},
)
class ForecastEnsembleEstimator:
    """Combine several forecast baselines into one ensemble projection."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="simple_average",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("forecast_matrix", SlotType.MATRIX, Unit("forecast", "value"), shape=("n_models", "horizon")),
            }
        ),
        output_slots=forecasting_output_slots(),
        parameters=(ParameterSpec(name="weights", default=None),),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Weighted ensemble averaging over multiple forecast trajectories.",
        tags=frozenset({"forecasting", "ensemble", "time-series"}),
        truthfulness_scope="predictive_calibration",
        when_to_use="Combine multiple model forecasts to reduce variance; model uncertainty aggregation",
        output_interpretation=(
            "Weighted average forecast plus forecasting_uncertainty_bundle. "
            "Current bundle is explicitly heuristic member-spread only until predictive densities or sample paths are available."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        forecast_matrix = np.asarray(state["forecast_matrix"], dtype=float)
        if forecast_matrix.ndim != 2:
            raise ValueError("forecast_matrix must be 2D")
        artifact_store = resolve_artifact_store(state, params)
        weights_raw = params.get("weights")
        if weights_raw is None:
            weights = np.full(forecast_matrix.shape[0], 1.0 / forecast_matrix.shape[0], dtype=float)
        else:
            weights = np.asarray(weights_raw, dtype=float)
            if weights.shape != (forecast_matrix.shape[0],):
                raise ValueError("weights must match the number of forecast rows")
            weights = weights / max(float(np.sum(weights)), 1e-12)
        ensemble = weights @ forecast_matrix
        return {
            "result": {"forecast": ensemble.tolist(), "weights": weights.tolist()},
            "forecasting_uncertainty_bundle": build_member_spread_bundle(
                method_fqn="forecasting.ensemble.simple_average@1.0.0",
                target_id="ensemble_forecast",
                member_forecasts=forecast_matrix,
                ensemble_forecast=ensemble,
                artifact_store=artifact_store,
            ),
        }


@foundry_method(
    namespace="forecasting.reconciliation",
    version="1.0.0",
    tags={"forecasting", "hierarchical", "reconciliation", "time-series"},
)
class BottomUpReconciliationEstimator:
    """Reconcile hierarchical forecasts bottom-up when planners need aggregate-consistent projections."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bottom_up",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("bottom_forecasts", SlotType.MATRIX, Unit("forecast", "value"), shape=("n_bottom", "horizon")),
                SlotSpec("aggregation_matrix", SlotType.MATRIX, Unit("aggregation", "weight"), shape=("n_total", "n_bottom")),
            }
        ),
        output_slots=forecasting_output_slots(),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Bottom-up hierarchical reconciliation using an aggregation matrix.",
        tags=frozenset({"forecasting", "hierarchical", "reconciliation", "time-series"}),
        truthfulness_scope="predictive_calibration",
        when_to_use="Reconcile forecasts across hierarchy levels; ensure aggregate consistency (national = sum of regions)",
        output_interpretation=(
            "Reconciled point forecasts at all hierarchy levels plus forecasting_uncertainty_bundle. "
            "Phase 0 marks the bundle non-gate-eligible until coherent predictive paths are available."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        bottom = np.asarray(state["bottom_forecasts"], dtype=float)
        aggregation = np.asarray(state["aggregation_matrix"], dtype=float)
        if bottom.ndim != 2 or aggregation.ndim != 2:
            raise ValueError("bottom_forecasts and aggregation_matrix must be 2D")
        if aggregation.shape[1] != bottom.shape[0]:
            raise ValueError("aggregation_matrix columns must equal number of bottom series")
        artifact_store = resolve_artifact_store(state, params)
        bottom_sample_paths = state.get("bottom_sample_paths")
        coherent_paths = None
        if bottom_sample_paths is not None:
            coherent_paths = _reconcile_sample_paths(np.asarray(bottom_sample_paths, dtype=float), aggregation)
        reconciled = aggregation @ bottom
        return {
            "result": {
                "reconciled_forecasts": reconciled.tolist(),
                "bottom_forecasts": bottom.tolist(),
            },
            "forecasting_uncertainty_bundle": build_reconciliation_placeholder_bundle(
                method_fqn="forecasting.reconciliation.bottom_up@1.0.0",
                target_id="reconciled_hierarchy",
                reconciled_forecasts=reconciled,
                coherent_sample_paths=coherent_paths,
                artifact_store=artifact_store,
            ),
        }


__all__ = [
    "BottomUpReconciliationEstimator",
    "ExponentialSmoothingEstimator",
    "ForecastEnsembleEstimator",
    "ThetaMethodEstimator",
]
