"""Benchmark harness for adaptive / responsive survey design estimators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import numpy as np

from .adaptive import AdaptiveAugmentedEstimator, AdaptiveCalibratedIPWEstimator


class AdaptiveBenchmarkScenarioKind(StrEnum):
    """Simulation families recommended by IV.T5."""

    FAVORABLE_MAR = "favorable_mar"
    WEAK_X = "weak_x"
    MEASUREMENT_TRADEOFF = "measurement_tradeoff"
    INFORMATIVE_CLUSTERED = "informative_clustered"


@dataclass(frozen=True, slots=True)
class AdaptiveBenchmarkConfig:
    """Configuration for the IV.T5 adaptive-design benchmark suite."""

    suite_id: str = "survey_adaptive_design_phase1"
    suite_version: str = "1.0"
    scenario_kinds: tuple[AdaptiveBenchmarkScenarioKind, ...] = (
        AdaptiveBenchmarkScenarioKind.FAVORABLE_MAR,
        AdaptiveBenchmarkScenarioKind.WEAK_X,
        AdaptiveBenchmarkScenarioKind.MEASUREMENT_TRADEOFF,
        AdaptiveBenchmarkScenarioKind.INFORMATIVE_CLUSTERED,
    )
    estimator_names: tuple[Literal["adaptive_calibrated_ipw", "adaptive_augmented"], ...] = (
        "adaptive_calibrated_ipw",
        "adaptive_augmented",
    )
    population_size: int = 5000
    sample_size: int = 700
    n_repetitions: int = 100
    n_bootstrap_replicates: int = 64
    seed: int = 42

    def __post_init__(self) -> None:
        if self.population_size < 500:
            raise ValueError("population_size must be at least 500")
        if self.sample_size < 80:
            raise ValueError("sample_size must be at least 80")
        if self.sample_size >= self.population_size:
            raise ValueError("sample_size must be smaller than population_size")
        if self.n_repetitions < 2:
            raise ValueError("n_repetitions must be at least 2")
        if self.n_bootstrap_replicates < 2:
            raise ValueError("n_bootstrap_replicates must be at least 2")
        if not self.scenario_kinds:
            raise ValueError("At least one scenario_kind is required")
        if not self.estimator_names:
            raise ValueError("At least one estimator_name is required")


@dataclass(frozen=True, slots=True)
class AdaptiveBenchmarkCaseResult:
    """Summary metrics for one estimator-scenario cell."""

    scenario_kind: AdaptiveBenchmarkScenarioKind
    estimator_name: Literal["adaptive_calibrated_ipw", "adaptive_augmented"]
    repetitions: int
    bias: float
    relative_bias: float
    rmse: float
    empirical_variance: float
    mean_estimated_variance: float
    coverage_95: float
    mean_effective_sample_size: float
    mean_design_effect: float
    mean_weight_cv: float
    mean_calibration_residual: float
    mean_action_efficacy: float
    mean_cost_per_complete: float
    mean_loss: float
    mean_response_rate: float


@dataclass(frozen=True, slots=True)
class AdaptiveBenchmarkSuiteResult:
    """Executable output of the IV.T5 benchmark harness."""

    config: AdaptiveBenchmarkConfig
    case_results: tuple[AdaptiveBenchmarkCaseResult, ...]
    aggregate_metrics: dict[str, float]


def default_adaptive_benchmark_config() -> AdaptiveBenchmarkConfig:
    """Return the default Phase 1 adaptive-design benchmark configuration."""

    return AdaptiveBenchmarkConfig()


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -20.0, 20.0)))


def _cluster_effects(rng: np.random.Generator, n_clusters: int, scale: float) -> np.ndarray:
    return rng.normal(loc=0.0, scale=scale, size=n_clusters)


def _make_population(
    kind: AdaptiveBenchmarkScenarioKind,
    *,
    population_size: int,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    cluster_size = 25
    n_clusters = int(np.ceil(population_size / cluster_size))
    clusters = np.repeat(np.arange(n_clusters), cluster_size)[:population_size]
    strata = clusters % 5
    group = rng.binomial(1, 0.38, size=population_size).astype(float)
    x_signal = rng.normal(size=population_size)
    admin_signal = 0.65 * x_signal + 0.55 * group + rng.normal(scale=0.7, size=population_size)
    rare_cluster = np.isin(clusters, np.arange(0, n_clusters, max(n_clusters // 8, 1))).astype(
        float
    )
    cluster_fx = _cluster_effects(
        rng,
        n_clusters,
        scale=0.7 if kind != AdaptiveBenchmarkScenarioKind.INFORMATIVE_CLUSTERED else 1.2,
    )
    base_noise = rng.normal(scale=1.0, size=population_size)

    if kind == AdaptiveBenchmarkScenarioKind.FAVORABLE_MAR:
        y_true = (
            12.0
            + 2.0 * group
            + 1.6 * x_signal
            + 1.1 * admin_signal
            + cluster_fx[clusters]
            + base_noise
        )
    elif kind == AdaptiveBenchmarkScenarioKind.WEAK_X:
        y_true = (
            12.0
            + 0.15 * group
            + 0.10 * x_signal
            + 0.05 * admin_signal
            + cluster_fx[clusters]
            + rng.normal(scale=2.0, size=population_size)
        )
    elif kind == AdaptiveBenchmarkScenarioKind.MEASUREMENT_TRADEOFF:
        y_true = (
            11.0
            + 1.2 * group
            + 1.0 * x_signal
            + 0.8 * admin_signal
            + cluster_fx[clusters]
            + base_noise
        )
    else:
        y_true = (
            10.0
            + 1.4 * group
            + 0.7 * x_signal
            + 0.9 * admin_signal
            + 3.0 * rare_cluster
            + cluster_fx[clusters]
            + base_noise
        )

    return {
        "clusters": clusters.astype(object),
        "strata": strata.astype(object),
        "group": group,
        "x_signal": x_signal,
        "admin_signal": admin_signal,
        "rare_cluster": rare_cluster,
        "y_true": y_true,
    }


def _sample_state(
    population: dict[str, np.ndarray],
    kind: AdaptiveBenchmarkScenarioKind,
    *,
    sample_size: int,
    rng: np.random.Generator,
) -> tuple[dict[str, np.ndarray], float]:
    n_population = population["y_true"].shape[0]
    sample_idx = np.sort(rng.choice(n_population, size=sample_size, replace=False))
    pi0 = np.full(sample_size, sample_size / n_population, dtype=float)

    group = population["group"][sample_idx]
    x_signal = population["x_signal"][sample_idx]
    admin_signal = population["admin_signal"][sample_idx]
    rare_cluster = population["rare_cluster"][sample_idx]
    y_true = population["y_true"][sample_idx]
    strata = population["strata"][sample_idx]
    clusters = population["clusters"][sample_idx]

    contact_burden = np.clip(
        1.6
        + 0.9 * group
        + 0.7 * rare_cluster
        - 0.5 * x_signal
        + rng.normal(scale=0.5, size=sample_size),
        0.2,
        None,
    )
    mode_history = np.clip(
        0.2 + 0.4 * group + 0.25 * rare_cluster + rng.normal(scale=0.2, size=sample_size), 0.0, 1.5
    )

    if kind == AdaptiveBenchmarkScenarioKind.FAVORABLE_MAR:
        phase1_eta = 1.1 - 0.9 * group - 0.8 * contact_burden + 0.9 * admin_signal
    elif kind == AdaptiveBenchmarkScenarioKind.WEAK_X:
        phase1_eta = 0.9 - 0.6 * group - 0.9 * contact_burden + 0.8 * admin_signal
    elif kind == AdaptiveBenchmarkScenarioKind.MEASUREMENT_TRADEOFF:
        phase1_eta = 0.8 - 0.7 * group - 0.9 * contact_burden + 0.6 * admin_signal
    else:
        phase1_eta = (
            0.7 - 0.9 * group - 0.7 * contact_burden + 0.4 * admin_signal - 1.0 * rare_cluster
        )

    rho1 = _sigmoid(phase1_eta)
    response1 = rng.binomial(1, rho1, size=sample_size).astype(float)
    nonrespondent = response1 < 0.5

    targeted_rule = (rho1 < np.quantile(rho1, 0.45)) | (rare_cluster > 0.5)
    q_followup = np.where(nonrespondent & targeted_rule, 0.65, 1.0)
    followup_selected = (rng.uniform(size=sample_size) < q_followup) & nonrespondent
    mode_switch = followup_selected & ((group > 0.5) | (rare_cluster > 0.5))

    if kind == AdaptiveBenchmarkScenarioKind.FAVORABLE_MAR:
        phase2_eta = (
            -0.1
            + 1.4 * followup_selected
            + 0.6 * mode_switch
            + 0.6 * admin_signal
            - 0.3 * contact_burden
        )
    elif kind == AdaptiveBenchmarkScenarioKind.WEAK_X:
        phase2_eta = (
            -0.3
            + 1.0 * followup_selected
            + 0.2 * mode_switch
            + 0.5 * admin_signal
            - 0.3 * contact_burden
        )
    elif kind == AdaptiveBenchmarkScenarioKind.MEASUREMENT_TRADEOFF:
        phase2_eta = (
            -0.1
            + 1.3 * followup_selected
            + 0.9 * mode_switch
            + 0.5 * admin_signal
            - 0.2 * contact_burden
        )
    else:
        phase2_eta = (
            -0.4
            + 1.1 * followup_selected
            + 0.8 * rare_cluster
            + 0.5 * admin_signal
            - 0.2 * contact_burden
        )

    rho2 = _sigmoid(phase2_eta)
    response2 = (rng.binomial(1, rho2, size=sample_size) > 0) & followup_selected
    final_response = (response1 > 0.5) | response2

    y_observed = np.full(sample_size, np.nan, dtype=float)
    y_observed[response1 > 0.5] = y_true[response1 > 0.5]
    y_observed[response2] = y_true[response2]
    if kind == AdaptiveBenchmarkScenarioKind.MEASUREMENT_TRADEOFF:
        y_observed[response2 & mode_switch] += 1.35

    paradata = np.column_stack([contact_burden, mode_history])
    actions = np.column_stack([followup_selected.astype(float), mode_switch.astype(float)])
    cost_vector = (
        1.0
        + 0.2 * contact_burden
        + 0.8 * followup_selected.astype(float)
        + 0.5 * mode_switch.astype(float)
    )
    X_aux = np.column_stack([np.ones(sample_size), group, admin_signal])
    control_totals = np.array(
        [
            float(n_population),
            float(np.sum(population["group"])),
            float(np.sum(population["admin_signal"])),
        ],
        dtype=float,
    )

    state = {
        "y_observed": y_observed,
        "response_indicator": final_response.astype(float),
        "base_inclusion_probabilities": pi0,
        "followup_sampling_probabilities": q_followup.astype(float),
        "X_aux": X_aux,
        "paradata_matrix": paradata,
        "action_matrix": actions,
        "control_totals": control_totals,
        "strata": strata,
        "clusters": clusters,
        "cost_vector": cost_vector,
    }
    truth = float(np.mean(y_true))
    return state, truth


def _action_efficacy(payload: dict[str, object]) -> float:
    diagnostics = payload.get("diagnostics") or {}
    action_effects = (
        diagnostics.get("action_effect_diagnostics") if isinstance(diagnostics, dict) else {}
    )
    if not isinstance(action_effects, dict) or not action_effects:
        return 0.0
    gaps = []
    for values in action_effects.values():
        if isinstance(values, dict):
            gaps.append(float(values.get("response_rate_gap", 0.0)))
    return float(np.mean(gaps)) if gaps else 0.0


def _run_estimator(
    estimator_name: Literal["adaptive_calibrated_ipw", "adaptive_augmented"],
    state: dict[str, np.ndarray],
    *,
    n_bootstrap_replicates: int,
    seed: int,
) -> dict[str, object]:
    params = {
        "calibration_method": "linear",
        "variance_method": "bootstrap",
        "n_replicates": n_bootstrap_replicates,
        "trim_method": "clip",
        "trim_quantile": 0.98,
        "confidence_level": 0.95,
        "decision_rule_id": "benchmark-rule",
        "adaptation_log_id": f"benchmark-log-{seed}",
        "control_totals_version": "synthetic_population_controls",
        "mode_column_indices": (1,),
        "seed": seed,
    }
    if estimator_name == "adaptive_augmented":
        return AdaptiveAugmentedEstimator.pure_step(state, params)["result"]
    return AdaptiveCalibratedIPWEstimator.pure_step(state, params)["result"]


def run_adaptive_benchmark_suite(
    config: AdaptiveBenchmarkConfig | None = None,
) -> AdaptiveBenchmarkSuiteResult:
    """Run the IV.T5 benchmark suite across estimators and scenario families."""

    resolved = config or default_adaptive_benchmark_config()
    master_rng = np.random.default_rng(resolved.seed)
    case_results: list[AdaptiveBenchmarkCaseResult] = []

    for scenario_kind in resolved.scenario_kinds:
        for estimator_name in resolved.estimator_names:
            errors: list[float] = []
            rel_errors: list[float] = []
            estimated_vars: list[float] = []
            covered: list[float] = []
            ess_values: list[float] = []
            design_effects: list[float] = []
            weight_cvs: list[float] = []
            residuals: list[float] = []
            action_efficacy: list[float] = []
            cost_per_complete: list[float] = []
            losses: list[float] = []
            response_rates: list[float] = []
            estimates: list[float] = []

            for rep in range(resolved.n_repetitions):
                rep_seed = int(master_rng.integers(0, 2**31 - 1))
                rng = np.random.default_rng(rep_seed)
                population = _make_population(
                    scenario_kind,
                    population_size=resolved.population_size,
                    rng=rng,
                )
                state, truth = _sample_state(
                    population,
                    scenario_kind,
                    sample_size=resolved.sample_size,
                    rng=rng,
                )
                payload = _run_estimator(
                    estimator_name,
                    state,
                    n_bootstrap_replicates=resolved.n_bootstrap_replicates,
                    seed=rep_seed,
                )
                estimate = float(payload["point_estimate"])
                se = float(payload["standard_error"])
                ci_lower = float(payload["ci_lower"])
                ci_upper = float(payload["ci_upper"])
                respondents = int(payload["adaptive_status"]["n_respondents"])
                weight_summary = payload["final_weights_summary"]
                calibration_status = payload["calibration_status"]
                stop_status = payload["stop_status"]

                estimates.append(estimate)
                errors.append(estimate - truth)
                rel_errors.append((estimate - truth) / truth if abs(truth) > 1e-12 else 0.0)
                estimated_vars.append(float(payload["variance_estimate"]))
                covered.append(float(ci_lower <= truth <= ci_upper))
                ess_values.append(float(weight_summary["effective_sample_size"]))
                design_effects.append(float(weight_summary["design_effect"]))
                weight_cvs.append(float(weight_summary["cv"]))
                residuals.append(float(calibration_status["max_abs_residual"]))
                action_efficacy.append(_action_efficacy(payload))
                cost_per_complete.append(
                    float(stop_status["cost_summary"]["total_cost"]) / max(respondents, 1)
                )
                losses.append(float(stop_status["loss_value"]))
                response_rates.append(float(payload["response_rate"]))

            case_results.append(
                AdaptiveBenchmarkCaseResult(
                    scenario_kind=scenario_kind,
                    estimator_name=estimator_name,
                    repetitions=resolved.n_repetitions,
                    bias=float(np.mean(errors)),
                    relative_bias=float(np.mean(rel_errors)),
                    rmse=float(np.sqrt(np.mean(np.square(errors)))),
                    empirical_variance=float(np.var(estimates, ddof=1)),
                    mean_estimated_variance=float(np.mean(estimated_vars)),
                    coverage_95=float(np.mean(covered)),
                    mean_effective_sample_size=float(np.mean(ess_values)),
                    mean_design_effect=float(np.mean(design_effects)),
                    mean_weight_cv=float(np.mean(weight_cvs)),
                    mean_calibration_residual=float(np.mean(residuals)),
                    mean_action_efficacy=float(np.mean(action_efficacy)),
                    mean_cost_per_complete=float(np.mean(cost_per_complete)),
                    mean_loss=float(np.mean(losses)),
                    mean_response_rate=float(np.mean(response_rates)),
                )
            )

    aggregate_metrics = {
        "n_case_results": float(len(case_results)),
        "mean_abs_bias": float(np.mean([abs(result.bias) for result in case_results]))
        if case_results
        else 0.0,
        "mean_rmse": float(np.mean([result.rmse for result in case_results]))
        if case_results
        else 0.0,
        "mean_coverage_95": float(np.mean([result.coverage_95 for result in case_results]))
        if case_results
        else 0.0,
        "mean_effective_sample_size": float(
            np.mean([result.mean_effective_sample_size for result in case_results])
        )
        if case_results
        else 0.0,
        "mean_cost_per_complete": float(
            np.mean([result.mean_cost_per_complete for result in case_results])
        )
        if case_results
        else 0.0,
    }
    return AdaptiveBenchmarkSuiteResult(
        config=resolved,
        case_results=tuple(case_results),
        aggregate_metrics=aggregate_metrics,
    )


__all__ = [
    "AdaptiveBenchmarkCaseResult",
    "AdaptiveBenchmarkConfig",
    "AdaptiveBenchmarkScenarioKind",
    "AdaptiveBenchmarkSuiteResult",
    "default_adaptive_benchmark_config",
    "run_adaptive_benchmark_suite",
]
