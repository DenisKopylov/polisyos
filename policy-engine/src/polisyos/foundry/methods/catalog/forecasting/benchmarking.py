"""Research-backed Phase 0 benchmark and recommendation surface for forecasting uncertainty."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.forecasting.advanced import (
    ProphetEstimator,
    STLDecompositionEstimator,
    VECForecastEstimator,
)
from polisyos.foundry.methods.catalog.forecasting.regime_shift import (
    RegimeShiftForecastEstimator,
)
from polisyos.foundry.methods.catalog.forecasting.univariate import (
    BottomUpReconciliationEstimator,
    ExponentialSmoothingEstimator,
    ForecastEnsembleEstimator,
    ThetaMethodEstimator,
)


class ForecastBenchmarkRegime(StrEnum):
    """Synthetic data regimes used by the Phase 0 benchmark harness."""

    STABLE_SMALL = "stable_small"
    STABLE_MEDIUM = "stable_medium"
    POLICY_BREAKS = "policy_breaks"


class ForecastResearchStrategy(StrEnum):
    """Research recommendation vocabulary for interval construction."""

    PARAMETRIC = "parametric_state_space"
    BOOTSTRAP = "bootstrap"
    CONFORMAL = "conformal"
    BAYESIAN = "bayesian_posterior_predictive"
    BAYESIAN_PLUS_CONFORMAL = "bayesian_plus_conformal"
    LINEAR_POOL_PLUS_CONFORMAL = "linear_pool_plus_conformal"
    ADAPTIVE_LINEAR_POOL_PLUS_CONFORMAL = "adaptive_linear_pool_plus_conformal"
    GAUSSIAN_RECONCILIATION = "gaussian_reconciliation"
    COHERENT_BOOTSTRAP = "coherent_bootstrap"
    DECOMPOSE_RECOMPOSE_CONFORMAL = "decompose_forecast_recompose_conformal"
    REGIME_SWITCHING_ADAPTIVE_CONFORMAL = "regime_switching_adaptive_conformal"


@dataclass(frozen=True)
class ForecastRecommendationCell:
    method_fqn: str
    regime: ForecastBenchmarkRegime
    horizon_start: int
    horizon_end: int
    strategies: tuple[ForecastResearchStrategy, ...]
    bundle_policy: str


@dataclass(frozen=True)
class ForecastBenchmarkResult:
    method_fqn: str
    regime: ForecastBenchmarkRegime
    status: str
    nominal_coverage: float
    observed_coverage_by_horizon: dict[int, float | None]
    mean_interval_width_by_horizon: dict[int, float | None]
    mean_interval_score_by_horizon: dict[int, float | None]
    current_interval_semantics: str
    current_calibration_method: str
    current_gate_eligible: bool
    truthfulness_tier: str
    truthfulness_scope: str
    research_recommendation_by_horizon: dict[int, tuple[str, ...]]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegimeShiftCalibrationBenchmarkResult:
    """One factorial acceptance cell for regime-shift forecasting."""

    case_id: str
    method_fqn: str
    status: str
    n_obs: int
    horizon: int
    regime_count: int
    min_dwell: int
    separation: float
    recurring: bool
    shift_type: str
    true_breakpoints: tuple[int, ...]
    detected_breakpoints: tuple[int, ...]
    benchmark_status: str | None
    identifiability_status: str | None
    regime_status: str | None
    observed_coverage_by_horizon: dict[int, float | None]
    mean_interval_score_by_horizon: dict[int, float | None]
    break_localization_error: float | None
    detection_delay: float | None
    accepted: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SyntheticScenario:
    history_univariate: np.ndarray
    future_univariate: np.ndarray
    history_multivariate: np.ndarray
    future_multivariate: np.ndarray
    bottom_history: np.ndarray
    bottom_future: np.ndarray
    aggregation_matrix: np.ndarray


_RECOMMENDATIONS: tuple[ForecastRecommendationCell, ...] = (
    ForecastRecommendationCell(
        "forecasting.univariate.exponential_smoothing@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        1,
        4,
        (ForecastResearchStrategy.PARAMETRIC,),
        "Prefer state-space ETS when available; current lightweight backend should stay conformalized.",
    ),
    ForecastRecommendationCell(
        "forecasting.univariate.exponential_smoothing@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        12,
        24,
        (ForecastResearchStrategy.BOOTSTRAP, ForecastResearchStrategy.CONFORMAL),
        "Long horizons should bootstrap first and conformal-recalibrate before gating.",
    ),
    ForecastRecommendationCell(
        "forecasting.univariate.exponential_smoothing@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        1,
        4,
        (ForecastResearchStrategy.PARAMETRIC, ForecastResearchStrategy.BOOTSTRAP),
        "Short-horizon ETS can stay parametric when fully specified; lightweight code should still validate against bootstrap.",
    ),
    ForecastRecommendationCell(
        "forecasting.univariate.exponential_smoothing@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        12,
        24,
        (ForecastResearchStrategy.BOOTSTRAP, ForecastResearchStrategy.CONFORMAL),
        "Long-horizon drift accumulation requires bootstrap plus conformal recalibration.",
    ),
    ForecastRecommendationCell(
        "forecasting.univariate.exponential_smoothing@1.0.0",
        ForecastBenchmarkRegime.POLICY_BREAKS,
        1,
        24,
        (ForecastResearchStrategy.CONFORMAL,),
        "Break regimes should default to horizon-wise conformal intervals.",
    ),
    ForecastRecommendationCell(
        "forecasting.univariate.theta@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        1,
        4,
        (ForecastResearchStrategy.PARAMETRIC,),
        "SES-with-drift style parametrics are acceptable only at short stable horizons.",
    ),
    ForecastRecommendationCell(
        "forecasting.univariate.theta@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        12,
        24,
        (ForecastResearchStrategy.CONFORMAL,),
        "Long-horizon Theta drift misspecification calls for conformal overlay.",
    ),
    ForecastRecommendationCell(
        "forecasting.univariate.theta@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        1,
        4,
        (ForecastResearchStrategy.PARAMETRIC,),
        "Short-horizon Theta remains competitive in medium stable regimes.",
    ),
    ForecastRecommendationCell(
        "forecasting.univariate.theta@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        12,
        24,
        (ForecastResearchStrategy.BOOTSTRAP, ForecastResearchStrategy.CONFORMAL),
        "Long horizons should bootstrap or conformalize, not rely on raw parametrics.",
    ),
    ForecastRecommendationCell(
        "forecasting.univariate.theta@1.0.0",
        ForecastBenchmarkRegime.POLICY_BREAKS,
        1,
        24,
        (ForecastResearchStrategy.CONFORMAL,),
        "Break regimes should stay on conformal calibration across all horizons.",
    ),
    ForecastRecommendationCell(
        "forecasting.ensemble.simple_average@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        1,
        24,
        (ForecastResearchStrategy.LINEAR_POOL_PLUS_CONFORMAL,),
        "Ensembles should combine predictive densities or path pools, never endpoint averages.",
    ),
    ForecastRecommendationCell(
        "forecasting.ensemble.simple_average@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        1,
        24,
        (ForecastResearchStrategy.LINEAR_POOL_PLUS_CONFORMAL,),
        "Stable medium regimes still want pooled predictive paths plus conformal recalibration.",
    ),
    ForecastRecommendationCell(
        "forecasting.ensemble.simple_average@1.0.0",
        ForecastBenchmarkRegime.POLICY_BREAKS,
        1,
        24,
        (ForecastResearchStrategy.ADAPTIVE_LINEAR_POOL_PLUS_CONFORMAL,),
        "Break regimes require adaptive pooling with recalibration.",
    ),
    ForecastRecommendationCell(
        "forecasting.reconciliation.bottom_up@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        1,
        4,
        (ForecastResearchStrategy.GAUSSIAN_RECONCILIATION,),
        "Short stable horizons can use Gaussian probabilistic reconciliation when its assumptions hold.",
    ),
    ForecastRecommendationCell(
        "forecasting.reconciliation.bottom_up@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        12,
        24,
        (ForecastResearchStrategy.COHERENT_BOOTSTRAP,),
        "Long horizons require coherent reconciled sample paths.",
    ),
    ForecastRecommendationCell(
        "forecasting.reconciliation.bottom_up@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        1,
        4,
        (
            ForecastResearchStrategy.GAUSSIAN_RECONCILIATION,
            ForecastResearchStrategy.COHERENT_BOOTSTRAP,
        ),
        "Medium stable hierarchies can use Gaussian or coherent bootstrap depending diagnostics.",
    ),
    ForecastRecommendationCell(
        "forecasting.reconciliation.bottom_up@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        12,
        24,
        (ForecastResearchStrategy.COHERENT_BOOTSTRAP,),
        "Long horizons still need coherent bootstrap paths.",
    ),
    ForecastRecommendationCell(
        "forecasting.reconciliation.bottom_up@1.0.0",
        ForecastBenchmarkRegime.POLICY_BREAKS,
        1,
        24,
        (ForecastResearchStrategy.COHERENT_BOOTSTRAP,),
        "Break regimes should stay on coherent bootstrap paths at every horizon.",
    ),
    ForecastRecommendationCell(
        "forecasting.decomposition.stl@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        1,
        24,
        (ForecastResearchStrategy.DECOMPOSE_RECOMPOSE_CONFORMAL,),
        "STL should only attach uncertainty after downstream forecasting and recomposition.",
    ),
    ForecastRecommendationCell(
        "forecasting.decomposition.stl@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        1,
        24,
        (ForecastResearchStrategy.DECOMPOSE_RECOMPOSE_CONFORMAL,),
        "STL remains an attached-output-only method in medium regimes.",
    ),
    ForecastRecommendationCell(
        "forecasting.decomposition.stl@1.0.0",
        ForecastBenchmarkRegime.POLICY_BREAKS,
        1,
        24,
        (ForecastResearchStrategy.DECOMPOSE_RECOMPOSE_CONFORMAL,),
        "Break regimes still require downstream forecast plus sliding recalibration after decomposition.",
    ),
    ForecastRecommendationCell(
        "forecasting.multivariate.vec_forecast@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        1,
        4,
        (ForecastResearchStrategy.BOOTSTRAP,),
        "Short stable multivariate horizons can start from residual or block bootstrap.",
    ),
    ForecastRecommendationCell(
        "forecasting.multivariate.vec_forecast@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        12,
        24,
        (ForecastResearchStrategy.BOOTSTRAP, ForecastResearchStrategy.CONFORMAL),
        "Long multivariate horizons need bootstrap plus conformal overlay.",
    ),
    ForecastRecommendationCell(
        "forecasting.multivariate.vec_forecast@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        1,
        4,
        (ForecastResearchStrategy.BAYESIAN,),
        "A fuller CVAR backend should prefer Bayesian predictive densities on stable medium regimes.",
    ),
    ForecastRecommendationCell(
        "forecasting.multivariate.vec_forecast@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        12,
        24,
        (ForecastResearchStrategy.BAYESIAN, ForecastResearchStrategy.CONFORMAL),
        "Long horizons still require post-hoc conformal recalibration.",
    ),
    ForecastRecommendationCell(
        "forecasting.multivariate.vec_forecast@1.0.0",
        ForecastBenchmarkRegime.POLICY_BREAKS,
        1,
        24,
        (ForecastResearchStrategy.BOOTSTRAP, ForecastResearchStrategy.CONFORMAL),
        "Current lightweight VEC should stay on bootstrap plus conformal in break regimes.",
    ),
    ForecastRecommendationCell(
        "forecasting.advanced.prophet@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        1,
        24,
        (ForecastResearchStrategy.CONFORMAL,),
        "Raw Prophet bands are not governance-grade; conformal recalibration is required.",
    ),
    ForecastRecommendationCell(
        "forecasting.advanced.prophet@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        1,
        4,
        (ForecastResearchStrategy.BAYESIAN_PLUS_CONFORMAL,),
        "Medium stable Prophet should use posterior predictive draws and then conformalize.",
    ),
    ForecastRecommendationCell(
        "forecasting.advanced.prophet@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        12,
        24,
        (ForecastResearchStrategy.CONFORMAL,),
        "Long-horizon Prophet remains conformal-first even when posterior draws exist.",
    ),
    ForecastRecommendationCell(
        "forecasting.advanced.prophet@1.0.0",
        ForecastBenchmarkRegime.POLICY_BREAKS,
        1,
        24,
        (ForecastResearchStrategy.CONFORMAL,),
        "Break regimes should never expose raw Prophet bands as calibrated.",
    ),
    ForecastRecommendationCell(
        "forecasting.regime_shift.hybrid@1.0.0",
        ForecastBenchmarkRegime.STABLE_SMALL,
        1,
        24,
        (ForecastResearchStrategy.REGIME_SWITCHING_ADAPTIVE_CONFORMAL,),
        "Stable series should accept a one-regime certificate only when the no-break posterior and coverage gates pass.",
    ),
    ForecastRecommendationCell(
        "forecasting.regime_shift.hybrid@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        1,
        24,
        (ForecastResearchStrategy.REGIME_SWITCHING_ADAPTIVE_CONFORMAL,),
        "Medium stable regimes use the same bundle shape so regime uncertainty remains comparable across benchmarks.",
    ),
    ForecastRecommendationCell(
        "forecasting.regime_shift.hybrid@1.0.0",
        ForecastBenchmarkRegime.POLICY_BREAKS,
        1,
        24,
        (ForecastResearchStrategy.REGIME_SWITCHING_ADAPTIVE_CONFORMAL,),
        "Policy-break regimes require assignment, break-date, recovery-curve, and regime-conditional coverage artifacts.",
    ),
)


_ALL_METHOD_FQNS = (
    "forecasting.univariate.exponential_smoothing@1.0.0",
    "forecasting.univariate.theta@1.0.0",
    "forecasting.ensemble.simple_average@1.0.0",
    "forecasting.reconciliation.bottom_up@1.0.0",
    "forecasting.decomposition.stl@1.0.0",
    "forecasting.multivariate.vec_forecast@1.0.0",
    "forecasting.advanced.prophet@1.0.0",
    "forecasting.regime_shift.hybrid@1.0.0",
)


def phase0_forecasting_recommendation_matrix() -> tuple[ForecastRecommendationCell, ...]:
    """Return the research-backed recommendation matrix for Track 3.1."""

    return _RECOMMENDATIONS


def lookup_phase0_forecasting_recommendation(
    method_fqn: str,
    regime: ForecastBenchmarkRegime,
    horizon: int,
) -> ForecastRecommendationCell:
    """Resolve the research recommendation for a method/regime/horizon cell."""

    for cell in _RECOMMENDATIONS:
        if cell.method_fqn != method_fqn or cell.regime is not regime:
            continue
        if cell.horizon_start <= horizon <= cell.horizon_end:
            return cell
    raise KeyError(f"No Phase 0 recommendation for {method_fqn=} {regime.value=} {horizon=}")


def _regime_observation_count(regime: ForecastBenchmarkRegime) -> int:
    if regime is ForecastBenchmarkRegime.STABLE_SMALL:
        return 36
    return 96


def _generate_base_signal(
    regime: ForecastBenchmarkRegime,
    *,
    n_obs: int,
    horizon: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    total = n_obs + horizon
    t = np.arange(total, dtype=float)
    slope = 0.15 if regime is ForecastBenchmarkRegime.STABLE_SMALL else 0.08
    seasonal_amp = 1.5 if regime is ForecastBenchmarkRegime.STABLE_SMALL else 3.0
    noise_scale = 0.35 if regime is ForecastBenchmarkRegime.STABLE_SMALL else 0.45
    signal = 40.0 + slope * t + seasonal_amp * np.sin((2.0 * math.pi * t) / 12.0)
    signal = signal + rng.normal(0.0, noise_scale, size=total)
    if regime is ForecastBenchmarkRegime.POLICY_BREAKS:
        break_start = max(n_obs - 10, total // 2)
        signal[break_start:] = signal[break_start:] + 5.0
        signal[break_start:] = signal[break_start:] + 0.20 * np.arange(
            total - break_start, dtype=float
        )
        shock_index = min(n_obs + max(horizon // 3, 1), total - 1)
        signal[shock_index:] = signal[shock_index:] - 3.0
    return signal


def _regime_state_pattern(regime_count: int, *, recurring: bool) -> tuple[int, ...]:
    if regime_count <= 1:
        return (0,)
    if recurring and regime_count >= 3:
        return (*range(regime_count - 1), 0)
    return tuple(range(regime_count))


def _build_regime_factorial_signal(
    *,
    n_obs: int,
    horizon: int,
    regime_count: int,
    min_dwell: int,
    separation: float,
    recurring: bool,
    shift_type: str,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, tuple[int, ...]]:
    if regime_count < 1:
        raise ValueError("regime_count must be >= 1")
    if n_obs < regime_count * min_dwell:
        raise ValueError("n_obs must allow every regime to satisfy min_dwell")

    rng = np.random.default_rng(seed)
    state_pattern = _regime_state_pattern(regime_count, recurring=recurring)
    segment_count = len(state_pattern)
    base_length = n_obs // segment_count
    lengths = [base_length] * segment_count
    lengths[-1] += n_obs - sum(lengths)
    breakpoints = tuple(int(sum(lengths[:idx])) for idx in range(1, segment_count))

    history = np.zeros(n_obs, dtype=float)
    cursor = 0
    for segment_index, (state, length) in enumerate(zip(state_pattern, lengths, strict=True)):
        local_t = np.arange(length, dtype=float)
        has_level_shift = shift_type in {"level", "mixed"}
        has_slope_shift = shift_type in {"slope", "mixed"}
        has_variance_shift = shift_type in {"variance", "mixed"}
        mean = 40.0 + (separation * 3.0 * state if has_level_shift else 0.0)
        slope = 0.04 + (0.08 * state if has_slope_shift else 0.0)
        noise_scale = 0.25 * (1.0 + state if has_variance_shift else 1.0)
        history[cursor : cursor + length] = (
            mean
            + slope * local_t
            + 0.3 * np.sin((2.0 * math.pi * (cursor + local_t)) / 12.0)
            + rng.normal(0.0, noise_scale, size=length)
        )
        if segment_index > 0 and not has_level_shift and has_slope_shift:
            history[cursor : cursor + length] += history[cursor - 1] - history[cursor]
        cursor += length

    last_state = state_pattern[-1]
    future_t = np.arange(1, horizon + 1, dtype=float)
    has_level_shift = shift_type in {"level", "mixed"}
    has_slope_shift = shift_type in {"slope", "mixed"}
    has_variance_shift = shift_type in {"variance", "mixed"}
    future_mean = 40.0 + (separation * 3.0 * last_state if has_level_shift else 0.0)
    future_slope = 0.04 + (0.08 * last_state if has_slope_shift else 0.0)
    noise_scale = 0.25 * (1.0 + last_state if has_variance_shift else 1.0)
    anchor = float(history[-1])
    future = (
        anchor
        + future_slope * future_t
        + 0.3 * np.sin((2.0 * math.pi * (n_obs + future_t)) / 12.0)
        + rng.normal(0.0, noise_scale, size=horizon)
    )
    if has_level_shift:
        future += future_mean - float(np.mean(history[-min_dwell:]))
    return history, future, breakpoints


def _build_scenario(
    regime: ForecastBenchmarkRegime,
    *,
    horizons: tuple[int, ...],
    seed: int,
) -> _SyntheticScenario:
    horizon_max = max(horizons)
    n_obs = _regime_observation_count(regime)
    base = _generate_base_signal(regime, n_obs=n_obs, horizon=horizon_max, seed=seed)
    history_univariate = base[:n_obs]
    future_univariate = base[n_obs:]

    rng = np.random.default_rng(seed + 17)
    common = _generate_base_signal(regime, n_obs=n_obs, horizon=horizon_max, seed=seed + 3)
    seasonal_shift = np.sin((2.0 * math.pi * np.arange(n_obs + horizon_max, dtype=float)) / 6.0)
    series_1 = common + 0.4 * seasonal_shift + rng.normal(0.0, 0.25, size=n_obs + horizon_max)
    series_2 = (
        common
        - 2.5
        + 0.6 * np.roll(seasonal_shift, 1)
        + rng.normal(0.0, 0.25, size=n_obs + horizon_max)
    )
    history_multivariate = np.column_stack([series_1[:n_obs], series_2[:n_obs]])
    future_multivariate = np.column_stack([series_1[n_obs:], series_2[n_obs:]])

    bottom_1 = 0.55 * base + 8.0 + rng.normal(0.0, 0.20, size=n_obs + horizon_max)
    bottom_2 = (
        0.45 * base
        + 5.0
        + 0.8 * np.cos((2.0 * math.pi * np.arange(n_obs + horizon_max, dtype=float)) / 12.0)
    )
    bottom_2 = bottom_2 + rng.normal(0.0, 0.20, size=n_obs + horizon_max)
    bottom_history = np.vstack([bottom_1[:n_obs], bottom_2[:n_obs]])
    bottom_future = np.vstack([bottom_1[n_obs:], bottom_2[n_obs:]])
    aggregation_matrix = np.asarray(
        [
            [1.0, 1.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        dtype=float,
    )

    return _SyntheticScenario(
        history_univariate=history_univariate,
        future_univariate=future_univariate,
        history_multivariate=history_multivariate,
        future_multivariate=future_multivariate,
        bottom_history=bottom_history,
        bottom_future=bottom_future,
        aggregation_matrix=aggregation_matrix,
    )


def _interval_score(actual: Any, lower: Any, upper: Any, alpha: float) -> float:
    y = np.asarray(actual, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    width = hi - lo
    score = width + (2.0 / max(alpha, 1e-12)) * np.maximum(lo - y, 0.0)
    score = score + (2.0 / max(alpha, 1e-12)) * np.maximum(y - hi, 0.0)
    return float(np.mean(score))


def _actual_is_covered(actual: Any, lower: Any, upper: Any) -> bool:
    y = np.asarray(actual, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    return bool(np.all((y >= lo) & (y <= hi)))


def _mean_width(lower: Any, upper: Any) -> float:
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    return float(np.mean(np.maximum(hi - lo, 0.0)))


def _interval_lookup(bundle: Any) -> dict[int, Any]:
    return {interval.horizon: interval for interval in bundle.prediction_interval}


def _build_bottom_forecasts(history: np.ndarray, horizon: int) -> np.ndarray:
    forecasts = []
    for row in history:
        result = ExponentialSmoothingEstimator.pure_step(
            {"series": row}, {"horizon": horizon, "alpha": 0.3, "beta": 0.1}
        )
        forecasts.append(np.asarray(result["result"]["forecast"], dtype=float))
    return np.vstack(forecasts)


def _build_bottom_sample_paths(
    history: np.ndarray, point_forecasts: np.ndarray, *, n_paths: int, seed: int
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    scales = []
    for row in history:
        diffs = np.diff(np.asarray(row, dtype=float))
        scale = float(np.std(diffs, ddof=1)) if diffs.size > 1 else 0.25
        scales.append(max(scale, 0.1))
    scales_arr = np.asarray(scales, dtype=float)
    noise = rng.normal(
        loc=0.0,
        scale=scales_arr[None, :, None]
        * np.sqrt(np.arange(1, point_forecasts.shape[1] + 1, dtype=float))[None, None, :],
        size=(n_paths, point_forecasts.shape[0], point_forecasts.shape[1]),
    )
    return point_forecasts[None, :, :] + noise


def _build_ensemble_member_matrix(history: np.ndarray, horizon: int) -> np.ndarray:
    ets = ExponentialSmoothingEstimator.pure_step(
        {"series": history}, {"horizon": horizon, "alpha": 0.3, "beta": 0.1}
    )
    theta = ThetaMethodEstimator.pure_step({"series": history}, {"horizon": horizon, "alpha": 0.2})
    prophet = ProphetEstimator.pure_step({"series": history}, {"horizon": horizon, "period": 12})
    return np.vstack(
        [
            np.asarray(ets["result"]["forecast"], dtype=float),
            np.asarray(theta["result"]["forecast"], dtype=float),
            np.asarray(prophet["result"]["forecast"], dtype=float),
        ]
    )


def _evaluate_method_once(
    method_fqn: str,
    regime: ForecastBenchmarkRegime,
    *,
    scenario: _SyntheticScenario,
    horizons: tuple[int, ...],
    seed: int,
) -> tuple[Any, dict[int, Any], tuple[str, ...]]:
    horizon_max = max(horizons)
    if method_fqn == "forecasting.univariate.exponential_smoothing@1.0.0":
        result = ExponentialSmoothingEstimator.pure_step(
            {"series": scenario.history_univariate},
            {"horizon": horizon_max, "alpha": 0.3, "beta": 0.1},
        )
        actual = {h: float(scenario.future_univariate[h - 1]) for h in horizons}
        return result["forecasting_uncertainty_bundle"], actual, ()
    if method_fqn == "forecasting.univariate.theta@1.0.0":
        result = ThetaMethodEstimator.pure_step(
            {"series": scenario.history_univariate},
            {"horizon": horizon_max, "alpha": 0.2},
        )
        actual = {h: float(scenario.future_univariate[h - 1]) for h in horizons}
        return result["forecasting_uncertainty_bundle"], actual, ()
    if method_fqn == "forecasting.ensemble.simple_average@1.0.0":
        member_matrix = _build_ensemble_member_matrix(scenario.history_univariate, horizon_max)
        result = ForecastEnsembleEstimator.pure_step({"forecast_matrix": member_matrix}, {})
        actual = {h: float(scenario.future_univariate[h - 1]) for h in horizons}
        return result["forecasting_uncertainty_bundle"], actual, ()
    if method_fqn == "forecasting.reconciliation.bottom_up@1.0.0":
        bottom_forecasts = _build_bottom_forecasts(scenario.bottom_history, horizon_max)
        bottom_sample_paths = _build_bottom_sample_paths(
            scenario.bottom_history, bottom_forecasts, n_paths=48, seed=seed + 101
        )
        result = BottomUpReconciliationEstimator.pure_step(
            {
                "bottom_forecasts": bottom_forecasts,
                "aggregation_matrix": scenario.aggregation_matrix,
                "bottom_sample_paths": bottom_sample_paths,
            },
            {},
        )
        future_reconciled = scenario.aggregation_matrix @ scenario.bottom_future
        actual = {h: future_reconciled[:, h - 1] for h in horizons}
        return result["forecasting_uncertainty_bundle"], actual, ("coherent_path_proxy",)
    if method_fqn == "forecasting.decomposition.stl@1.0.0":
        result = STLDecompositionEstimator.pure_step(
            {"series": scenario.history_univariate}, {"period": 12}
        )
        return result["forecasting_uncertainty_bundle"], {}, ("attached_output_only",)
    if method_fqn == "forecasting.multivariate.vec_forecast@1.0.0":
        result = VECForecastEstimator.pure_step(
            {"series_matrix": scenario.history_multivariate},
            {"horizon": horizon_max, "n_lags": 1, "predictive_draws": 32, "random_seed": seed},
        )
        actual = {h: scenario.future_multivariate[h - 1] for h in horizons}
        return result["forecasting_uncertainty_bundle"], actual, ()
    if method_fqn == "forecasting.advanced.prophet@1.0.0":
        result = ProphetEstimator.pure_step(
            {"series": scenario.history_univariate},
            {"horizon": horizon_max, "period": 12, "predictive_draws": 32, "random_seed": seed},
        )
        actual = {h: float(scenario.future_univariate[h - 1]) for h in horizons}
        return result["forecasting_uncertainty_bundle"], actual, ()
    if method_fqn == "forecasting.regime_shift.hybrid@1.0.0":
        result = RegimeShiftForecastEstimator.pure_step(
            {"series": scenario.history_univariate},
            {
                "horizon": horizon_max,
                "max_breaks": 3,
                "min_dwell": 8,
                "break_window": 4,
                "coverage_tolerance": 0.10,
                "shift_type_assessment": "structural",
            },
        )
        actual = {h: float(scenario.future_univariate[h - 1]) for h in horizons}
        notes = (
            f"benchmark_status={result['result']['benchmark_status']}",
            f"regime_status={result['result']['regime_status']}",
        )
        return result["forecasting_uncertainty_bundle"], actual, notes
    raise KeyError(f"Unsupported forecasting method for Phase 0 benchmark: {method_fqn}")


def _stable_method_seed(method_fqn: str, regime: ForecastBenchmarkRegime) -> int:
    return sum(ord(ch) for ch in f"{method_fqn}:{regime.value}")


def run_phase0_forecasting_benchmark(
    *,
    methods: tuple[str, ...] = _ALL_METHOD_FQNS,
    regimes: tuple[ForecastBenchmarkRegime, ...] = tuple(ForecastBenchmarkRegime),
    horizons: tuple[int, ...] = (1, 4, 12, 24),
    n_trials: int = 3,
    base_seed: int = 2026,
) -> list[ForecastBenchmarkResult]:
    """Run a synthetic coverage smoke-benchmark aligned with the Track 3.1 research plan."""

    selected_horizons = tuple(sorted(dict.fromkeys(int(h) for h in horizons)))
    results: list[ForecastBenchmarkResult] = []

    for regime in regimes:
        for method_fqn in methods:
            coverage_lists = {h: [] for h in selected_horizons}
            width_lists = {h: [] for h in selected_horizons}
            wis_lists = {h: [] for h in selected_horizons}
            notes: list[str] = []
            final_bundle = None

            for trial in range(n_trials):
                scenario_seed = (
                    base_seed + 1000 * trial + (_stable_method_seed(method_fqn, regime) % 997)
                )
                scenario = _build_scenario(regime, horizons=selected_horizons, seed=scenario_seed)
                bundle, actual_by_horizon, trial_notes = _evaluate_method_once(
                    method_fqn,
                    regime,
                    scenario=scenario,
                    horizons=selected_horizons,
                    seed=base_seed + trial,
                )
                final_bundle = bundle
                notes.extend(trial_notes)

                if not bundle.prediction_interval:
                    continue
                lookup = _interval_lookup(bundle)
                for horizon in selected_horizons:
                    interval = lookup.get(horizon)
                    actual = actual_by_horizon.get(horizon)
                    if interval is None or actual is None:
                        continue
                    coverage_lists[horizon].append(
                        1.0 if _actual_is_covered(actual, interval.lower, interval.upper) else 0.0
                    )
                    width_lists[horizon].append(_mean_width(interval.lower, interval.upper))
                    wis_lists[horizon].append(
                        _interval_score(
                            actual,
                            interval.lower,
                            interval.upper,
                            1.0 - float(interval.coverage_target or bundle.nominal_coverage),
                        )
                    )

            if final_bundle is None:
                continue

            receipt = final_bundle.to_truthfulness_receipt()
            if not final_bundle.prediction_interval:
                status = "attached_output_only"
            else:
                status = "evaluated"
            research_recommendation = {
                h: tuple(
                    strategy.value
                    for strategy in lookup_phase0_forecasting_recommendation(
                        method_fqn, regime, h
                    ).strategies
                )
                for h in selected_horizons
            }
            results.append(
                ForecastBenchmarkResult(
                    method_fqn=method_fqn,
                    regime=regime,
                    status=status,
                    nominal_coverage=float(final_bundle.nominal_coverage),
                    observed_coverage_by_horizon={
                        h: (float(np.mean(values)) if values else None)
                        for h, values in coverage_lists.items()
                    },
                    mean_interval_width_by_horizon={
                        h: (float(np.mean(values)) if values else None)
                        for h, values in width_lists.items()
                    },
                    mean_interval_score_by_horizon={
                        h: (float(np.mean(values)) if values else None)
                        for h, values in wis_lists.items()
                    },
                    current_interval_semantics=final_bundle.interval_semantics.value,
                    current_calibration_method=final_bundle.calibration_method.value,
                    current_gate_eligible=bool(final_bundle.horizon_policy.gate_eligible),
                    truthfulness_tier=receipt.runtime_truthfulness_tier.value,
                    truthfulness_scope=receipt.truthfulness_scope.value,
                    research_recommendation_by_horizon=research_recommendation,
                    notes=tuple(dict.fromkeys(notes)),
                )
            )
    return results


def _break_localization_metrics(
    true_breakpoints: tuple[int, ...],
    detected_breakpoints: tuple[int, ...],
) -> tuple[float | None, float | None]:
    if not true_breakpoints:
        return None, None
    if not detected_breakpoints:
        return math.inf, math.inf
    errors: list[float] = []
    delays: list[float] = []
    for true_break in true_breakpoints:
        nearest = min(detected_breakpoints, key=lambda candidate: abs(candidate - true_break))
        errors.append(float(abs(nearest - true_break)))
        delays.append(float(max(0, nearest - true_break)))
    return float(np.mean(errors)), float(np.mean(delays))


def run_regime_shift_calibration_benchmark(
    *,
    series_lengths: tuple[int, ...] = (72,),
    regime_counts: tuple[int, ...] = (1, 2, 3),
    min_dwells: tuple[int, ...] = (8,),
    separations: tuple[float, ...] = (1.0, 2.0),
    recurring_modes: tuple[bool, ...] = (False, True),
    shift_types: tuple[str, ...] = ("level", "slope", "variance", "mixed"),
    horizon: int = 6,
    n_trials: int = 1,
    base_seed: int = 2026,
    nominal_coverage: float = 0.90,
    coverage_tolerance: float = 0.10,
) -> list[RegimeShiftCalibrationBenchmarkResult]:
    """Run the Phase 4 factorial acceptance benchmark for regime-shift forecasting."""

    results: list[RegimeShiftCalibrationBenchmarkResult] = []
    case_index = 0
    for n_obs in series_lengths:
        for regime_count in regime_counts:
            for min_dwell in min_dwells:
                for separation in separations:
                    for recurring in recurring_modes:
                        for shift_type in shift_types:
                            if n_obs < max(regime_count, 1) * min_dwell:
                                continue
                            for trial in range(n_trials):
                                seed = base_seed + 1000 * trial + case_index
                                case_id = (
                                    f"n{n_obs}-k{regime_count}-d{min_dwell}-"
                                    f"s{separation:g}-r{int(recurring)}-{shift_type}-t{trial}"
                                )
                                case_index += 1
                                history, future, true_breakpoints = _build_regime_factorial_signal(
                                    n_obs=n_obs,
                                    horizon=horizon,
                                    regime_count=regime_count,
                                    min_dwell=min_dwell,
                                    separation=separation,
                                    recurring=recurring,
                                    shift_type=shift_type,
                                    seed=seed,
                                )
                                try:
                                    result = RegimeShiftForecastEstimator.pure_step(
                                        {"series": history},
                                        {
                                            "horizon": horizon,
                                            "min_dwell": min_dwell,
                                            "max_breaks": max(regime_count + 1, 1),
                                            "nominal_coverage": nominal_coverage,
                                            "coverage_tolerance": coverage_tolerance,
                                            "shift_type_assessment": "structural",
                                        },
                                    )
                                except ValueError as exc:
                                    results.append(
                                        RegimeShiftCalibrationBenchmarkResult(
                                            case_id=case_id,
                                            method_fqn="forecasting.regime_shift.hybrid@1.0.0",
                                            status="rejected",
                                            n_obs=n_obs,
                                            horizon=horizon,
                                            regime_count=regime_count,
                                            min_dwell=min_dwell,
                                            separation=float(separation),
                                            recurring=recurring,
                                            shift_type=shift_type,
                                            true_breakpoints=true_breakpoints,
                                            detected_breakpoints=(),
                                            benchmark_status=None,
                                            identifiability_status=None,
                                            regime_status=None,
                                            observed_coverage_by_horizon=dict.fromkeys(
                                                range(1, horizon + 1)
                                            ),
                                            mean_interval_score_by_horizon=dict.fromkeys(
                                                range(1, horizon + 1)
                                            ),
                                            break_localization_error=None,
                                            detection_delay=None,
                                            accepted=False,
                                            notes=(str(exc),),
                                        )
                                    )
                                    continue

                                bundle = result["regime_shift_forecast_bundle"]
                                detected = tuple(int(value) for value in result["result"]["breakpoints"])
                                lookup = _interval_lookup(bundle)
                                observed_coverage: dict[int, float | None] = {}
                                interval_score: dict[int, float | None] = {}
                                for h in range(1, horizon + 1):
                                    interval = lookup.get(h)
                                    if interval is None:
                                        observed_coverage[h] = None
                                        interval_score[h] = None
                                        continue
                                    actual = float(future[h - 1])
                                    observed_coverage[h] = (
                                        1.0
                                        if _actual_is_covered(actual, interval.lower, interval.upper)
                                        else 0.0
                                    )
                                    interval_score[h] = _interval_score(
                                        actual,
                                        interval.lower,
                                        interval.upper,
                                        1.0 - float(interval.coverage_target or nominal_coverage),
                                    )
                                localization_error, detection_delay = _break_localization_metrics(
                                    true_breakpoints,
                                    detected,
                                )
                                coverage_values = [
                                    value for value in observed_coverage.values() if value is not None
                                ]
                                future_coverage_ok = (
                                    len(coverage_values) < 10
                                    or float(np.mean(coverage_values))
                                    >= nominal_coverage - coverage_tolerance
                                )
                                accepted = (
                                    result["result"]["benchmark_status"] == "green"
                                    and result["result"]["regime_status"] == "calibrated"
                                    and future_coverage_ok
                                )
                                results.append(
                                    RegimeShiftCalibrationBenchmarkResult(
                                        case_id=case_id,
                                        method_fqn="forecasting.regime_shift.hybrid@1.0.0",
                                        status="evaluated",
                                        n_obs=n_obs,
                                        horizon=horizon,
                                        regime_count=regime_count,
                                        min_dwell=min_dwell,
                                        separation=float(separation),
                                        recurring=recurring,
                                        shift_type=shift_type,
                                        true_breakpoints=true_breakpoints,
                                        detected_breakpoints=detected,
                                        benchmark_status=result["result"]["benchmark_status"],
                                        identifiability_status=result["result"][
                                            "identifiability_status"
                                        ],
                                        regime_status=result["result"]["regime_status"],
                                        observed_coverage_by_horizon=observed_coverage,
                                        mean_interval_score_by_horizon=interval_score,
                                        break_localization_error=localization_error,
                                        detection_delay=detection_delay,
                                        accepted=accepted,
                                    )
                                )
    return results


__all__ = [
    "ForecastBenchmarkRegime",
    "ForecastBenchmarkResult",
    "ForecastRecommendationCell",
    "ForecastResearchStrategy",
    "RegimeShiftCalibrationBenchmarkResult",
    "lookup_phase0_forecasting_recommendation",
    "phase0_forecasting_recommendation_matrix",
    "run_phase0_forecasting_benchmark",
    "run_regime_shift_calibration_benchmark",
]
