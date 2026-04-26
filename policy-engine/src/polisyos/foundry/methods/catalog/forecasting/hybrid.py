"""Guarded neural/hybrid forecasting router for trust-region UQ."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

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
    build_residual_conformal_bundle,
    forecasting_output_slots,
    resolve_artifact_store,
)
from polisyos.foundry.methods.catalog.forecasting.univariate import (
    _exponential_smoothing_result,
    _theta_result,
)
from polisyos.ir.analytics.forecasting_uncertainty import (
    ForecastCalibrationMethod,
    ForecastingUncertaintyBundle,
    HorizonDiagnosticState,
)
from polisyos.ir.artifacts import ArtifactStore, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import ArtifactRefModel

_GUARDED_FQN = "forecasting.hybrid.guarded_neural@1.0.0"
_GUARDED_ENSEMBLE_SOURCE = "forecasting.hybrid.guarded_ensemble@1.0.0"
_NBEATS_CHALLENGER_SOURCE = "forecasting.neural.nbeats_like_challenger@1.0.0"
_DEEPAR_CHALLENGER_SOURCE = "forecasting.neural.deepar_challenger@1.0.0"
_TFT_CHALLENGER_SOURCE = "forecasting.neural.tft_challenger@1.0.0"
_PATCHTST_CHALLENGER_SOURCE = "forecasting.neural.patchtst_challenger@1.0.0"
_ETS_SOURCE = "forecasting.univariate.exponential_smoothing@1.0.0"
_THETA_SOURCE = "forecasting.univariate.theta@1.0.0"
_EPS = 1e-12
_RED_MIN_OBS = 60
_GREEN_MIN_OBS = 96
_RED_MIN_SEASONAL_CYCLES = 5.0
_GREEN_MIN_SEASONAL_CYCLES = 8.0
_RED_MAX_NOISE_RATIO = 0.8
_GREEN_MAX_NOISE_RATIO = 0.5
_GLOBAL_POOL_MIN_RELATED_SERIES = 24
_DISAGREEMENT_COMPATIBLE = 1.0
_DISAGREEMENT_ABSTAIN = 1.5


@dataclass(frozen=True)
class _TrustRegion:
    state: str
    n_obs: int
    seasonal_period: int
    seasonal_cycles: float
    seasonal_strength: float
    noise_ratio: float
    reasons: tuple[str, ...]
    shadow_only: bool


@dataclass(frozen=True)
class _ValidationMetrics:
    mase: float | None
    smape: float | None
    origin_count: int
    validation_tail: int


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


def _seasonal_probe(series: np.ndarray, *, period: int) -> tuple[float, float]:
    observed = np.asarray(series, dtype=float)
    total_var = float(np.var(observed))
    if total_var <= _EPS:
        return 0.0, 0.0
    if period <= 1 or observed.size < max(4, period):
        trend = np.full_like(observed, float(np.mean(observed)))
        remainder = observed - trend
        return 0.0, float(np.clip(np.var(remainder) / total_var, 0.0, 1.0))

    kernel = np.ones(period, dtype=float) / float(period)
    padded = np.pad(observed, (period // 2, period // 2), mode="edge")
    trend = np.convolve(padded, kernel, mode="valid")[: observed.size]
    detrended = observed - trend
    seasonal = np.zeros_like(observed)
    for pos in range(period):
        indices = np.arange(pos, observed.size, period)
        if indices.size:
            seasonal[indices] = float(np.mean(detrended[indices]))
    remainder = observed - trend - seasonal
    seasonal_denom = max(float(np.var(observed - trend)), _EPS)
    seasonal_strength = 1.0 - float(np.var(remainder)) / seasonal_denom
    noise_ratio = float(np.var(remainder)) / total_var
    return float(np.clip(seasonal_strength, 0.0, 1.0)), float(np.clip(noise_ratio, 0.0, 1.0))


def _neural_family_key(neural_family: str) -> str:
    family = str(neural_family).strip().lower().replace("-", "_")
    aliases = {
        "n_beats": "nbeats",
        "nbeats_like": "nbeats",
        "deep_ar": "deepar",
        "temporal_fusion_transformer": "tft",
        "patch_tst": "patchtst",
    }
    return aliases.get(family, family)


def _neural_source_method(neural_family: str) -> str:
    family = _neural_family_key(neural_family)
    if family == "nbeats":
        return _NBEATS_CHALLENGER_SOURCE
    if family == "deepar":
        return _DEEPAR_CHALLENGER_SOURCE
    if family == "tft":
        return _TFT_CHALLENGER_SOURCE
    if family == "patchtst":
        return _PATCHTST_CHALLENGER_SOURCE
    normalized = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in family).strip("_")
    return f"forecasting.neural.{normalized or 'unknown'}_challenger@1.0.0"


def _trust_region(
    series: np.ndarray,
    *,
    period: int,
    neural_family: str,
    related_series_count: int,
    has_static_covariates: bool,
    has_known_future_covariates: bool,
    multivariate_context: bool,
    long_context: bool,
) -> _TrustRegion:
    n_obs = int(series.size)
    seasonal_period = max(1, int(period))
    seasonal_cycles = float(n_obs / seasonal_period)
    seasonal_strength, noise_ratio = _seasonal_probe(series, period=seasonal_period)
    family = _neural_family_key(neural_family)
    reasons: list[str] = []

    if n_obs < _RED_MIN_OBS:
        reasons.append("short_series_neural")
    if seasonal_period > 1 and seasonal_cycles < _RED_MIN_SEASONAL_CYCLES:
        reasons.append("insufficient_seasonal_cycles")
    if noise_ratio > _RED_MAX_NOISE_RATIO:
        reasons.append("high_noise_low_signal")

    if reasons:
        state = "red"
    elif (
        n_obs < _GREEN_MIN_OBS
        or (
            seasonal_period > 1
            and seasonal_cycles < _GREEN_MIN_SEASONAL_CYCLES
        )
        or noise_ratio > _GREEN_MAX_NOISE_RATIO
    ):
        state = "amber"
    else:
        state = "green"

    if family == "deepar" and related_series_count < _GLOBAL_POOL_MIN_RELATED_SERIES:
        reasons.append("global_pool_insufficient")
        state = "red" if n_obs <= 120 else "amber"
    elif family == "tft" and not (
        has_static_covariates or has_known_future_covariates
    ):
        reasons.append("covariate_context_missing")
        if state == "green":
            state = "amber"
    elif family == "patchtst" and not (
        multivariate_context or long_context or n_obs >= 180
    ):
        reasons.append("long_context_insufficient")
        if n_obs <= 120 and state == "green":
            state = "amber"

    return _TrustRegion(
        state=state,
        n_obs=n_obs,
        seasonal_period=seasonal_period,
        seasonal_cycles=seasonal_cycles,
        seasonal_strength=seasonal_strength,
        noise_ratio=noise_ratio,
        reasons=tuple(dict.fromkeys(reasons)),
        shadow_only=state != "green",
    )


def _nbeats_like_result(series: np.ndarray, *, horizon: int, period: int) -> dict[str, Any]:
    observed = np.asarray(series, dtype=float)
    n_obs = int(observed.size)
    horizon = max(1, int(horizon))
    t = np.arange(n_obs, dtype=float)
    t_scaled = (t - np.mean(t)) / max(float(np.std(t)), 1.0)
    columns = [np.ones(n_obs), t_scaled, t_scaled**2]
    if period > 1 and n_obs >= period:
        angle = 2.0 * math.pi * t / float(period)
        columns.extend([np.sin(angle), np.cos(angle)])
    design = np.column_stack(columns)
    try:
        coef = np.linalg.lstsq(design, observed, rcond=None)[0]
    except np.linalg.LinAlgError:
        coef = np.zeros(design.shape[1], dtype=float)
        coef[0] = float(observed[-1])

    future_t = np.arange(n_obs, n_obs + horizon, dtype=float)
    future_scaled = (future_t - np.mean(t)) / max(float(np.std(t)), 1.0)
    future_columns = [np.ones(horizon), future_scaled, future_scaled**2]
    if period > 1 and n_obs >= period:
        future_angle = 2.0 * math.pi * future_t / float(period)
        future_columns.extend([np.sin(future_angle), np.cos(future_angle)])
    forecast = np.column_stack(future_columns) @ coef
    return {
        "forecast": forecast.tolist(),
        "basis": "trend_plus_seasonal_backcast_forecast_proxy",
        "horizon": horizon,
    }


def _make_baseline_fn(
    source_method: str,
    *,
    alpha: float,
    beta: float,
) -> Callable[[np.ndarray, int], np.ndarray]:
    if source_method == _ETS_SOURCE:
        return lambda train, h: np.asarray(
            _exponential_smoothing_result(
                np.asarray(train, dtype=float), horizon=h, alpha=alpha, beta=beta
            )["forecast"],
            dtype=float,
        )
    return lambda train, h: np.asarray(
        _theta_result(np.asarray(train, dtype=float), horizon=h, alpha=alpha)["forecast"],
        dtype=float,
    )


def _make_neural_fn(
    *,
    neural_family: str,
    period: int,
) -> Callable[[np.ndarray, int], np.ndarray] | None:
    if _neural_family_key(neural_family) == "nbeats":
        return lambda train, h: np.asarray(
            _nbeats_like_result(np.asarray(train, dtype=float), horizon=h, period=period)[
                "forecast"
            ],
            dtype=float,
        )
    return None


def _mase_scale(series: np.ndarray, *, period: int) -> float:
    observed = np.asarray(series, dtype=float)
    lag = period if period > 1 and observed.size > period else 1
    diffs = np.abs(observed[lag:] - observed[:-lag])
    if diffs.size == 0:
        return 1.0
    return max(float(np.mean(diffs)), _EPS)


def _validation_tail(n_obs: int, *, period: int) -> int:
    return min(max(period, int(math.ceil(0.2 * n_obs)), 12), max(n_obs - 3, 1))


def _rolling_validation_metrics(
    series: np.ndarray,
    forecast_fn: Callable[[np.ndarray, int], np.ndarray],
    *,
    horizon: int,
    period: int,
    n_origins: int,
) -> _ValidationMetrics:
    observed = np.asarray(series, dtype=float)
    tail = _validation_tail(int(observed.size), period=period)
    start = max(3, observed.size - tail)
    stop = max(start + 1, observed.size - 1)
    origins = np.linspace(start, stop, max(1, int(n_origins)), dtype=int)
    origins = np.asarray(sorted(dict.fromkeys(int(origin) for origin in origins)), dtype=int)
    mase_values: list[float] = []
    smape_values: list[float] = []
    scale = _mase_scale(observed[:start], period=period)

    for train_end in origins:
        available = min(int(horizon), int(observed.size - train_end))
        if available <= 0:
            continue
        train = observed[:train_end]
        actual = observed[train_end : train_end + available]
        predicted = np.asarray(forecast_fn(train, available), dtype=float)[:available]
        if predicted.shape[0] != available:
            continue
        error = np.abs(actual - predicted)
        mase_values.append(float(np.mean(error) / scale))
        denom = np.maximum((np.abs(actual) + np.abs(predicted)) / 2.0, _EPS)
        smape_values.append(float(np.mean(error / denom)))

    return _ValidationMetrics(
        mase=float(np.mean(mase_values)) if mase_values else None,
        smape=float(np.mean(smape_values)) if smape_values else None,
        origin_count=len(mase_values),
        validation_tail=int(tail),
    )


def _choose_baseline(
    series: np.ndarray,
    *,
    horizon: int,
    period: int,
    alpha: float,
    beta: float,
    n_origins: int,
) -> tuple[str, Callable[[np.ndarray, int], np.ndarray], _ValidationMetrics]:
    candidates = (_THETA_SOURCE, _ETS_SOURCE)
    scored: list[tuple[float, str, Callable[[np.ndarray, int], np.ndarray], _ValidationMetrics]] = []
    for source_method in candidates:
        fn = _make_baseline_fn(source_method, alpha=alpha, beta=beta)
        metrics = _rolling_validation_metrics(
            series, fn, horizon=horizon, period=period, n_origins=n_origins
        )
        loss = metrics.mase if metrics.mase is not None else math.inf
        scored.append((loss, source_method, fn, metrics))
    scored.sort(key=lambda item: (item[0], item[1] != _THETA_SOURCE))
    _, source_method, fn, metrics = scored[0]
    return source_method, fn, metrics


def _mean_finite(values: Mapping[int, float | None]) -> float | None:
    finite = [float(value) for value in values.values() if value is not None and math.isfinite(value)]
    return float(np.mean(finite)) if finite else None


def _coverage_gap_exceeds(bundle: ForecastingUncertaintyBundle, tolerance: float) -> bool:
    gaps = [
        abs(float(value))
        for value in bundle.coverage_diagnostic.coverage_gap_by_horizon.values()
        if value is not None and math.isfinite(float(value))
    ]
    return bool(gaps and max(gaps) > tolerance)


def _baseline_interval_scales(bundle: ForecastingUncertaintyBundle, *, horizon: int) -> np.ndarray:
    scales = np.ones(horizon, dtype=float)
    for interval in bundle.prediction_interval:
        h = int(interval.horizon)
        if h < 1 or h > horizon:
            continue
        lower = np.asarray(interval.lower, dtype=float)
        upper = np.asarray(interval.upper, dtype=float)
        width = float(np.mean(np.maximum(upper - lower, 0.0)))
        scales[h - 1] = max(width / 2.0, _EPS)
    return scales


def _method_selection_metadata(
    *,
    candidate_methods: tuple[str, ...],
    baseline_method: str,
    neural_method: str | None,
    trust_region: _TrustRegion,
    disagreement_by_horizon: dict[int, float],
    abstained_horizons: tuple[int, ...],
    selection_reason: str,
    validation_metrics: dict[str, Any],
    calibration_window: int,
    shadow_only: bool,
    source_method_by_horizon: dict[int, str],
    weights_by_horizon: dict[int, float],
) -> dict[str, Any]:
    return {
        "method_selection": {
            "candidate_methods": list(candidate_methods),
            "baseline_method": baseline_method,
            "neural_method": neural_method,
            "trust_region_state": trust_region.state,
            "n_obs": trust_region.n_obs,
            "seasonal_period": trust_region.seasonal_period,
            "seasonal_cycles": trust_region.seasonal_cycles,
            "seasonal_strength": trust_region.seasonal_strength,
            "noise_ratio": trust_region.noise_ratio,
            "trust_region_reasons": list(trust_region.reasons),
            "disagreement_by_horizon": {
                str(horizon): value for horizon, value in disagreement_by_horizon.items()
            },
            "abstained_horizons": list(abstained_horizons),
            "selection_reason": selection_reason,
            "validation_metrics": validation_metrics,
            "calibration_window": calibration_window,
            "shadow_only": shadow_only,
            "source_method_by_horizon": {
                str(horizon): source for horizon, source in source_method_by_horizon.items()
            },
            "guarded_weights_by_horizon": {
                str(horizon): weight for horizon, weight in weights_by_horizon.items()
            },
        }
    }


def _decision_thresholds(
    *,
    minimum_point_improvement: float,
    coverage_gap_tolerance: float,
) -> dict[str, Any]:
    return {
        "red_min_obs": _RED_MIN_OBS,
        "green_min_obs": _GREEN_MIN_OBS,
        "red_min_seasonal_cycles": _RED_MIN_SEASONAL_CYCLES,
        "green_min_seasonal_cycles": _GREEN_MIN_SEASONAL_CYCLES,
        "red_max_noise_ratio": _RED_MAX_NOISE_RATIO,
        "green_max_noise_ratio": _GREEN_MAX_NOISE_RATIO,
        "global_pool_min_related_series": _GLOBAL_POOL_MIN_RELATED_SERIES,
        "minimum_point_improvement": minimum_point_improvement,
        "coverage_gap_tolerance": coverage_gap_tolerance,
        "disagreement_compatible": _DISAGREEMENT_COMPATIBLE,
        "disagreement_abstain": _DISAGREEMENT_ABSTAIN,
        "early_horizon_abstention_propagates_through": 3,
    }


def _with_final_uq_metrics(
    metadata: dict[str, Any],
    *,
    baseline_wis: float | None,
    candidate_wis: float | None,
    max_candidate_coverage_gap: float | None,
    coverage_gap_tolerance: float,
) -> dict[str, Any]:
    updated = {"method_selection": dict(metadata["method_selection"])}
    validation_metrics = dict(updated["method_selection"].get("validation_metrics") or {})
    validation_metrics["final_uq"] = {
        "baseline_wis": baseline_wis,
        "candidate_wis": candidate_wis,
        "max_candidate_coverage_gap": max_candidate_coverage_gap,
        "coverage_gap_tolerance": coverage_gap_tolerance,
    }
    updated["method_selection"]["validation_metrics"] = validation_metrics
    return updated


def _persist_selection_artifact(
    metadata: dict[str, Any],
    *,
    artifact_store: ArtifactStore | None,
) -> dict[str, Any]:
    if artifact_store is None:
        return metadata
    selection = dict(metadata["method_selection"])
    ref = put_json_artifact(
        artifact_store,
        {
            "payload_kind": "forecasting_method_selection",
            "method_fqn": _GUARDED_FQN,
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "method_selection": selection,
        },
        kind="ir.forecasting_method_selection",
        schema_name="ir.forecasting_method_selection",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selection["selection_artifact_ref"] = ArtifactRefModel.model_validate(ref).model_dump(
        mode="json"
    )
    return {"method_selection": selection}


def _finalize_selection_metadata(
    metadata: dict[str, Any],
    *,
    artifact_store: ArtifactStore | None,
    neural_backend_status: str,
    decision_thresholds: dict[str, Any],
) -> dict[str, Any]:
    selection = dict(metadata["method_selection"])
    selection["neural_backend_status"] = neural_backend_status
    selection["decision_thresholds"] = decision_thresholds
    selection["serving_policy"] = {
        "red": "baseline_only",
        "amber": "neural_shadow_baseline_serving",
        "green": "guarded_neural_or_guarded_ensemble_after_validation",
    }
    return _persist_selection_artifact(
        {"method_selection": selection},
        artifact_store=artifact_store,
    )


def _annotate_bundle(
    bundle: ForecastingUncertaintyBundle,
    *,
    regime_flags: tuple[str, ...],
    policy_regime: str,
    policy_note: str,
    metadata: dict[str, Any],
) -> ForecastingUncertaintyBundle:
    selection = metadata.get("method_selection") or {}
    source_by_horizon = {
        int(horizon): str(source)
        for horizon, source in (selection.get("source_method_by_horizon") or {}).items()
    }
    baseline_method = selection.get("baseline_method")
    diagnostic = bundle.coverage_diagnostic.model_copy(
        update={
            "regime_flags": tuple(
                dict.fromkeys((*bundle.coverage_diagnostic.regime_flags, *regime_flags))
            ),
            "recommended_fallback": (
                ForecastCalibrationMethod.CONFORMAL
                if "shadow_only_neural" in regime_flags
                or "baseline_disagreement_abstention" in regime_flags
                else bundle.coverage_diagnostic.recommended_fallback
            ),
        }
    )
    rules = []
    for rule in bundle.horizon_policy.rules:
        regime = policy_regime
        note = rule.note
        if note and policy_note:
            note = f"{note}; {policy_note}"
        elif policy_note:
            note = policy_note
        state = rule.diagnostic_state
        if policy_regime == "neural_shadow" and state is HorizonDiagnosticState.GREEN:
            state = HorizonDiagnosticState.AMBER
        horizon_source = source_by_horizon.get(rule.horizon_start)
        if (
            policy_regime == "guarded_neural_ensemble"
            and horizon_source == baseline_method
        ):
            regime = "neural_abstained"
            if state is HorizonDiagnosticState.GREEN:
                state = HorizonDiagnosticState.AMBER
            abstention_note = "neural branch abstained for this horizon; baseline fallback applied"
            note = f"{note}; {abstention_note}" if note else abstention_note
        rules.append(
            rule.model_copy(
                update={
                    "diagnostic_state": state,
                    "regime": regime,
                    "note": note,
                }
            )
        )
    policy = bundle.horizon_policy.model_copy(
        update={
            "rules": tuple(rules),
            "summary": (
                "Guarded neural routing used trust-region, validation, disagreement, "
                "and conformal calibration checks before selecting the serving source."
            ),
        }
    )
    merged_metadata = dict(bundle.metadata)
    merged_metadata.update(metadata)
    return bundle.model_copy(
        update={
            "coverage_diagnostic": diagnostic,
            "horizon_policy": policy,
            "metadata": merged_metadata,
        }
    )


@foundry_method(
    namespace="forecasting.hybrid",
    version="1.0.0",
    tags={"forecasting", "time-series", "neural", "hybrid", "trust-region"},
)
class GuardedNeuralForecastEstimator:
    """Route neural challengers through trust-region, validation, and abstention checks."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="guarded_neural",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {SlotSpec("series", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",))}
        ),
        output_slots=forecasting_output_slots(),
        parameters=(
            ParameterSpec(name="horizon", default=6),
            ParameterSpec(name="period", default=12),
            ParameterSpec(name="neural_family", default="nbeats"),
            ParameterSpec(name="related_series_count", default=1),
            ParameterSpec(name="minimum_point_improvement", default=0.05),
            ParameterSpec(name="coverage_gap_tolerance", default=0.05),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Guarded neural forecasting wrapper that keeps classical baselines as champion, "
            "runs neural candidates as challengers, and abstains outside trust regions."
        ),
        tags=frozenset({"forecasting", "time-series", "neural", "hybrid", "trust-region"}),
        declared_truthfulness_tier="approximate_calibrated",
        truthfulness_scope="marginal_coverage",
        when_to_use=(
            "Operational monthly policy series where neural forecasts must be shadowed, "
            "backed off, or blended only after validation and baseline-disagreement checks."
        ),
        typical_min_obs=96,
        output_interpretation=(
            "Point forecasts plus a conformalized ForecastingUncertaintyBundle. "
            "The bundle's method_fqn is the guarded router; source_method records the serving "
            "baseline or guarded ensemble selected after trust-region checks."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        series = _series(state)
        horizon = max(1, int(params.get("horizon", 6)))
        period = max(1, int(params.get("period", 12)))
        alpha = float(np.clip(float(params.get("alpha", 0.2)), 1e-6, 1.0))
        beta = float(np.clip(float(params.get("beta", 0.1)), 1e-6, 1.0))
        n_origins = max(3, int(params.get("n_origins", 3)))
        neural_family = str(params.get("neural_family", "nbeats"))
        minimum_point_improvement = float(params.get("minimum_point_improvement", 0.05))
        coverage_gap_tolerance = float(params.get("coverage_gap_tolerance", 0.05))
        artifact_store = resolve_artifact_store(state, params)
        decision_thresholds = _decision_thresholds(
            minimum_point_improvement=minimum_point_improvement,
            coverage_gap_tolerance=coverage_gap_tolerance,
        )

        baseline_method, baseline_fn, baseline_metrics = _choose_baseline(
            series,
            horizon=horizon,
            period=period,
            alpha=alpha,
            beta=beta,
            n_origins=n_origins,
        )
        baseline_forecast = np.asarray(baseline_fn(series, horizon), dtype=float)

        trust = _trust_region(
            series,
            period=period,
            neural_family=neural_family,
            related_series_count=int(params.get("related_series_count", 1)),
            has_static_covariates=bool(params.get("has_static_covariates", False)),
            has_known_future_covariates=bool(params.get("has_known_future_covariates", False)),
            multivariate_context=bool(params.get("multivariate_context", False)),
            long_context=bool(params.get("long_context", False)),
        )
        neural_fn = _make_neural_fn(neural_family=neural_family, period=period)
        neural_method = _neural_source_method(neural_family)
        neural_backend_status = (
            "available" if neural_fn is not None else "adapter_not_configured"
        )
        neural_forecast = (
            np.asarray(neural_fn(series, horizon), dtype=float) if neural_fn is not None else None
        )

        candidate_methods = tuple(
            method
            for method in (baseline_method, neural_method, _GUARDED_ENSEMBLE_SOURCE)
            if method is not None
        )
        base_validation_payload = {
            "baseline": {
                "mase": baseline_metrics.mase,
                "smape": baseline_metrics.smape,
                "origin_count": baseline_metrics.origin_count,
                "validation_tail": baseline_metrics.validation_tail,
            }
        }

        baseline_metadata = _method_selection_metadata(
            candidate_methods=candidate_methods,
            baseline_method=baseline_method,
            neural_method=neural_method,
            trust_region=trust,
            disagreement_by_horizon={},
            abstained_horizons=(),
            selection_reason="prefit_trust_region_backoff",
            validation_metrics=base_validation_payload,
            calibration_window=int(series.size),
            shadow_only=True,
            source_method_by_horizon=dict.fromkeys(range(1, horizon + 1), baseline_method),
            weights_by_horizon=dict.fromkeys(range(1, horizon + 1), 0.0),
        )
        regime_flags = [
            "neural_guarded_challenger",
            *trust.reasons,
        ]
        if trust.state == "red":
            regime_flags.append("neural_outside_trust_region")
        if trust.shadow_only:
            regime_flags.append("shadow_only_neural")
        if neural_fn is None:
            regime_flags.append("neural_backend_unavailable")

        baseline_metadata = _finalize_selection_metadata(
            baseline_metadata,
            artifact_store=artifact_store,
            neural_backend_status=neural_backend_status,
            decision_thresholds=decision_thresholds,
        )

        baseline_bundle = build_residual_conformal_bundle(
            method_fqn=_GUARDED_FQN,
            source_method=baseline_method,
            target_id="series",
            history=series,
            point_forecast=baseline_forecast,
            forecast_fn=baseline_fn,
            min_train_size=3,
            method_note="guarded neural router emitted the classical baseline serving trajectory",
            extra_regime_flags=tuple(regime_flags),
            extra_metadata=baseline_metadata,
            artifact_store=artifact_store,
        )

        if trust.state != "green" or neural_fn is None or neural_forecast is None:
            annotated = _annotate_bundle(
                baseline_bundle,
                regime_flags=tuple(regime_flags),
                policy_regime="neural_shadow",
                policy_note="neural challenger is shadow-only outside the green trust region",
                metadata=baseline_metadata,
            )
            return {
                "result": {
                    "forecast": baseline_forecast.tolist(),
                    "source_method": baseline_method,
                    "baseline_method": baseline_method,
                    "neural_method": neural_method,
                    "trust_region_state": trust.state,
                    "selection_reason": "prefit_trust_region_backoff",
                    "shadow_forecast": (
                        neural_forecast.tolist() if neural_forecast is not None else None
                    ),
                },
                "forecasting_uncertainty_bundle": annotated,
            }

        neural_metrics = _rolling_validation_metrics(
            series, neural_fn, horizon=horizon, period=period, n_origins=n_origins
        )
        validation_payload = {
            **base_validation_payload,
            "neural": {
                "mase": neural_metrics.mase,
                "smape": neural_metrics.smape,
                "origin_count": neural_metrics.origin_count,
                "validation_tail": neural_metrics.validation_tail,
            },
        }
        baseline_loss = baseline_metrics.mase
        neural_loss = neural_metrics.mase
        if baseline_loss is None or neural_loss is None or baseline_loss <= _EPS:
            point_improvement = None
        else:
            point_improvement = (baseline_loss - neural_loss) / baseline_loss
        validation_payload["point_loss_improvement"] = point_improvement

        if point_improvement is None or point_improvement < minimum_point_improvement:
            regime_flags.append("neural_validation_not_better")
            metadata = _method_selection_metadata(
                candidate_methods=candidate_methods,
                baseline_method=baseline_method,
                neural_method=neural_method,
                trust_region=trust,
                disagreement_by_horizon={},
                abstained_horizons=(),
                selection_reason="postfit_validation_backoff",
                validation_metrics=validation_payload,
                calibration_window=int(series.size),
                shadow_only=True,
                source_method_by_horizon=dict.fromkeys(range(1, horizon + 1), baseline_method),
                weights_by_horizon=dict.fromkeys(range(1, horizon + 1), 0.0),
            )
            metadata = _finalize_selection_metadata(
                metadata,
                artifact_store=artifact_store,
                neural_backend_status=neural_backend_status,
                decision_thresholds=decision_thresholds,
            )
            annotated = _annotate_bundle(
                baseline_bundle,
                regime_flags=tuple(regime_flags),
                policy_regime="neural_shadow",
                policy_note="neural challenger did not clear the rolling-origin improvement threshold",
                metadata=metadata,
            )
            return {
                "result": {
                    "forecast": baseline_forecast.tolist(),
                    "source_method": baseline_method,
                    "baseline_method": baseline_method,
                    "neural_method": neural_method,
                    "trust_region_state": trust.state,
                    "selection_reason": "postfit_validation_backoff",
                    "shadow_forecast": neural_forecast.tolist(),
                    "point_loss_improvement": point_improvement,
                },
                "forecasting_uncertainty_bundle": annotated,
            }

        scales = _baseline_interval_scales(baseline_bundle, horizon=horizon)
        disagreement = np.abs(neural_forecast - baseline_forecast) / np.maximum(scales, _EPS)
        disagreement_by_horizon = {
            h: float(disagreement[h - 1]) for h in range(1, horizon + 1)
        }
        weights = np.zeros(horizon, dtype=float)
        abstained_horizons: list[int] = []
        block_later = False
        for h in range(1, horizon + 1):
            score = disagreement_by_horizon[h]
            if block_later or score > _DISAGREEMENT_ABSTAIN:
                abstained_horizons.append(h)
                if h <= 3:
                    block_later = True
                continue
            weights[h - 1] = 0.25 if score > _DISAGREEMENT_COMPATIBLE else 0.5

        if abstained_horizons:
            regime_flags.append("baseline_disagreement_abstention")
        source_by_horizon = {
            h: (_GUARDED_ENSEMBLE_SOURCE if weights[h - 1] > 0.0 else baseline_method)
            for h in range(1, horizon + 1)
        }
        weights_by_horizon = {h: float(weights[h - 1]) for h in range(1, horizon + 1)}
        if not np.any(weights > 0.0):
            metadata = _method_selection_metadata(
                candidate_methods=candidate_methods,
                baseline_method=baseline_method,
                neural_method=neural_method,
                trust_region=trust,
                disagreement_by_horizon=disagreement_by_horizon,
                abstained_horizons=tuple(abstained_horizons),
                selection_reason="baseline_disagreement_backoff",
                validation_metrics=validation_payload,
                calibration_window=int(series.size),
                shadow_only=True,
                source_method_by_horizon=source_by_horizon,
                weights_by_horizon=weights_by_horizon,
            )
            metadata = _finalize_selection_metadata(
                metadata,
                artifact_store=artifact_store,
                neural_backend_status=neural_backend_status,
                decision_thresholds=decision_thresholds,
            )
            annotated = _annotate_bundle(
                baseline_bundle,
                regime_flags=tuple(regime_flags),
                policy_regime="neural_abstained",
                policy_note="neural challenger exceeded baseline-disagreement threshold",
                metadata=metadata,
            )
            return {
                "result": {
                    "forecast": baseline_forecast.tolist(),
                    "source_method": baseline_method,
                    "baseline_method": baseline_method,
                    "neural_method": neural_method,
                    "trust_region_state": trust.state,
                    "selection_reason": "baseline_disagreement_backoff",
                    "shadow_forecast": neural_forecast.tolist(),
                    "disagreement_by_horizon": disagreement_by_horizon,
                    "abstained_horizons": abstained_horizons,
                    "point_loss_improvement": point_improvement,
                },
                "forecasting_uncertainty_bundle": annotated,
            }

        final_forecast = (1.0 - weights) * baseline_forecast + weights * neural_forecast

        def guarded_fn(train: np.ndarray, h: int) -> np.ndarray:
            baseline_path = np.asarray(baseline_fn(train, h), dtype=float)
            neural_path = np.asarray(neural_fn(train, h), dtype=float)
            local_weights = weights[:h]
            return (1.0 - local_weights) * baseline_path + local_weights * neural_path

        metadata = _method_selection_metadata(
            candidate_methods=candidate_methods,
            baseline_method=baseline_method,
            neural_method=neural_method,
            trust_region=trust,
            disagreement_by_horizon=disagreement_by_horizon,
            abstained_horizons=tuple(abstained_horizons),
            selection_reason="guarded_ensemble_serving",
            validation_metrics=validation_payload,
            calibration_window=int(series.size),
            shadow_only=False,
            source_method_by_horizon=source_by_horizon,
            weights_by_horizon=weights_by_horizon,
        )
        candidate_bundle = build_residual_conformal_bundle(
            method_fqn=_GUARDED_FQN,
            source_method=_GUARDED_ENSEMBLE_SOURCE,
            target_id="series",
            history=series,
            point_forecast=final_forecast,
            forecast_fn=guarded_fn,
            min_train_size=3,
            method_note=(
                "guarded ensemble blends baseline and neural challenger only where "
                "trust-region and disagreement checks pass"
            ),
            extra_regime_flags=tuple(regime_flags),
            extra_metadata=metadata,
            artifact_store=artifact_store,
        )
        baseline_wis = _mean_finite(baseline_bundle.coverage_diagnostic.wis_by_horizon)
        candidate_wis = _mean_finite(candidate_bundle.coverage_diagnostic.wis_by_horizon)
        candidate_coverage_gaps = [
            abs(float(value))
            for value in candidate_bundle.coverage_diagnostic.coverage_gap_by_horizon.values()
            if value is not None and math.isfinite(float(value))
        ]
        max_candidate_coverage_gap = (
            max(candidate_coverage_gaps) if candidate_coverage_gaps else None
        )
        metadata = _with_final_uq_metrics(
            metadata,
            baseline_wis=baseline_wis,
            candidate_wis=candidate_wis,
            max_candidate_coverage_gap=max_candidate_coverage_gap,
            coverage_gap_tolerance=coverage_gap_tolerance,
        )
        metadata = _finalize_selection_metadata(
            metadata,
            artifact_store=artifact_store,
            neural_backend_status=neural_backend_status,
            decision_thresholds=decision_thresholds,
        )
        wis_degraded = (
            baseline_wis is not None
            and candidate_wis is not None
            and candidate_wis > baseline_wis
        )
        coverage_gap_failed = _coverage_gap_exceeds(candidate_bundle, coverage_gap_tolerance)
        if wis_degraded or coverage_gap_failed:
            fallback_reason = "wis_backoff" if wis_degraded else "coverage_gap_backoff"
            regime_flags.append(fallback_reason)
            metadata = _method_selection_metadata(
                candidate_methods=candidate_methods,
                baseline_method=baseline_method,
                neural_method=neural_method,
                trust_region=trust,
                disagreement_by_horizon=disagreement_by_horizon,
                abstained_horizons=tuple(range(1, horizon + 1)),
                selection_reason=fallback_reason,
                validation_metrics={
                    **validation_payload,
                    "baseline_wis": baseline_wis,
                    "candidate_wis": candidate_wis,
                    "max_candidate_coverage_gap": max_candidate_coverage_gap,
                    "coverage_gap_tolerance": coverage_gap_tolerance,
                },
                calibration_window=int(series.size),
                shadow_only=True,
                source_method_by_horizon=dict.fromkeys(range(1, horizon + 1), baseline_method),
                weights_by_horizon=dict.fromkeys(range(1, horizon + 1), 0.0),
            )
            metadata = _finalize_selection_metadata(
                metadata,
                artifact_store=artifact_store,
                neural_backend_status=neural_backend_status,
                decision_thresholds=decision_thresholds,
            )
            annotated = _annotate_bundle(
                baseline_bundle,
                regime_flags=tuple(regime_flags),
                policy_regime="neural_shadow",
                policy_note="candidate guarded ensemble failed final UQ diagnostics",
                metadata=metadata,
            )
            return {
                "result": {
                    "forecast": baseline_forecast.tolist(),
                    "source_method": baseline_method,
                    "baseline_method": baseline_method,
                    "neural_method": neural_method,
                    "trust_region_state": trust.state,
                    "selection_reason": fallback_reason,
                    "shadow_forecast": neural_forecast.tolist(),
                    "disagreement_by_horizon": disagreement_by_horizon,
                    "point_loss_improvement": point_improvement,
                },
                "forecasting_uncertainty_bundle": annotated,
            }

        annotated = _annotate_bundle(
            candidate_bundle,
            regime_flags=tuple(regime_flags),
            policy_regime="guarded_neural_ensemble",
            policy_note="neural branch admitted only on horizons inside disagreement threshold",
            metadata=metadata,
        )
        return {
            "result": {
                "forecast": final_forecast.tolist(),
                "source_method": _GUARDED_ENSEMBLE_SOURCE,
                "baseline_method": baseline_method,
                "neural_method": neural_method,
                "trust_region_state": trust.state,
                "selection_reason": "guarded_ensemble_serving",
                "baseline_forecast": baseline_forecast.tolist(),
                "neural_forecast": neural_forecast.tolist(),
                "weights_by_horizon": weights_by_horizon,
                "disagreement_by_horizon": disagreement_by_horizon,
                "abstained_horizons": abstained_horizons,
                "point_loss_improvement": point_improvement,
            },
            "forecasting_uncertainty_bundle": annotated,
        }


__all__ = [
    "GuardedNeuralForecastEstimator",
]
