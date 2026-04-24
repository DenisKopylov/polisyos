"""Research-backed Phase 0 benchmark and recommendation surface for forecasting uncertainty."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from polisyos.foundry.methods.catalog.forecasting.advanced import (
    ProphetEstimator,
    STLDecompositionEstimator,
    VECForecastEstimator,
)
from polisyos.foundry.methods.catalog.forecasting.univariate import (
    BottomUpReconciliationEstimator,
    ExponentialSmoothingEstimator,
    ForecastEnsembleEstimator,
    ThetaMethodEstimator,
)


class ForecastBenchmarkRegime(str, Enum):
    """Synthetic data regimes used by the Phase 0 benchmark harness."""

    STABLE_SMALL = "stable_small"
    STABLE_MEDIUM = "stable_medium"
    POLICY_BREAKS = "policy_breaks"


class ForecastResearchStrategy(str, Enum):
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
)


_ALL_METHOD_FQNS = (
    "forecasting.univariate.exponential_smoothing@1.0.0",
    "forecasting.univariate.theta@1.0.0",
    "forecasting.ensemble.simple_average@1.0.0",
    "forecasting.reconciliation.bottom_up@1.0.0",
    "forecasting.decomposition.stl@1.0.0",
    "forecasting.multivariate.vec_forecast@1.0.0",
    "forecasting.advanced.prophet@1.0.0",
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


__all__ = [
    "ForecastBenchmarkRegime",
    "ForecastBenchmarkResult",
    "ForecastRecommendationCell",
    "ForecastResearchStrategy",
    "lookup_phase0_forecasting_recommendation",
    "phase0_forecasting_recommendation_matrix",
    "run_phase0_forecasting_benchmark",
]
