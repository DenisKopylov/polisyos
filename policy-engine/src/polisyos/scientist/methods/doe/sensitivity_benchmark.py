"""Coverage benchmarks and calibration profiles for sensitivity-index uncertainty."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from .uncertainty import (
    SensitivityInterval,
    SensitivityUncertaintyBundle,
    SensitivityUncertaintyConfig,
    SobolRowBlockData,
    _sobol_estimates,
    analyze_morris_trajectory_bootstrap,
    analyze_sobol_paired_bootstrap,
)


class SensitivityTruth(BaseModel):
    """Analytic or reference truth for a sensitivity benchmark case."""

    model_config = ConfigDict(extra="forbid")

    benchmark_id: str
    parameter_names: list[str]
    indices: dict[str, dict[str, float]] = Field(default_factory=dict)
    rank_metric: str = "ST"
    truth_source: str = "analytic"


class CoverageBenchmarkConfig(BaseModel):
    """Execution settings for development and release coverage benchmarks."""

    model_config = ConfigDict(extra="forbid")

    mode: str = Field(default="development", pattern=r"^(development|release)$")
    development_repetitions: int = Field(default=500, ge=1)
    release_repetitions: int = Field(default=2000, ge=1)
    sobol_sample_sizes: list[int] = Field(default_factory=lambda: [128, 256, 512, 1024, 2048, 4096])
    morris_trajectory_counts: list[int] = Field(default_factory=lambda: [10, 20, 50, 100])
    nominal_levels: list[float] = Field(default_factory=lambda: [0.90, 0.95, 0.99])
    random_seed: int = 20260426
    n_resamples: int = Field(default=399, ge=10)

    @property
    def repetitions(self) -> int:
        return self.release_repetitions if self.mode == "release" else self.development_repetitions


class CoverageObservation(BaseModel):
    """Coverage diagnostics for one outer benchmark repetition."""

    model_config = ConfigDict(extra="forbid")

    covered: dict[str, bool] = Field(default_factory=dict)
    simultaneous_covered: bool | None = None
    widths: dict[str, float] = Field(default_factory=dict)
    interval_scores: dict[str, float] = Field(default_factory=dict)
    miss_direction: dict[str, str] = Field(default_factory=dict)
    boundary_failures: dict[str, bool] = Field(default_factory=dict)
    rank_covered: bool | None = None
    top_k_covered: bool | None = None
    pairwise_bins: dict[str, tuple[int, int]] = Field(default_factory=dict)


class CoverageScenarioResult(BaseModel):
    """Aggregated coverage metrics for a benchmark scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    method: str
    index_types: list[str]
    sampler: str
    dimension: int
    sample_size: int
    n_repetitions: int
    nominal_level: float
    marginal_coverage: float
    simultaneous_coverage: float | None = None
    mean_interval_width: float
    median_interval_width: float
    interval_score: float
    miss_below_rate: float
    miss_above_rate: float
    boundary_failure_rate: float
    rank_coverage: float | None = None
    top_k_coverage: float | None = None
    pairwise_calibration: dict[str, float] = Field(default_factory=dict)
    ci_disagreement: float | None = None
    approved: bool = False
    approval_notes: list[str] = Field(default_factory=list)


class CoverageAcceptanceCriteria(BaseModel):
    """Catalog approval thresholds for sensitivity CI methods."""

    model_config = ConfigDict(extra="forbid")

    marginal_ordinary_low: float = 0.93
    marginal_ordinary_high: float = 0.97
    marginal_stress_floor: float = 0.92
    simultaneous_floor: float = 0.93
    boundary_failure_max: float = 0.01
    pairwise_dominance_floor: float = 0.90
    max_mean_width: float | None = None


class CoverageSummary(BaseModel):
    """Coverage profile summary across benchmark scenarios."""

    model_config = ConfigDict(extra="forbid")

    min_95_coverage: float
    median_95_coverage: float
    max_95_coverage: float


class SensitivityCoverageProfile(BaseModel):
    """Versioned calibration profile attached to catalog uncertainty outputs."""

    model_config = ConfigDict(extra="forbid")

    coverage_profile_id: str
    method: str
    index_types: list[str]
    samplers: list[str]
    benchmark_commit: str
    nominal_levels_tested: list[float]
    coverage_summary: CoverageSummary
    approved: bool
    calibrated_multiplier: float | None = None
    acceptance_notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class SobolBenchmarkCase:
    """Executable Sobol benchmark case with known analytic or reference truth."""

    benchmark_id: str
    parameter_names: tuple[str, ...]
    evaluator: Callable[[np.ndarray], np.ndarray]
    truth: SensitivityTruth
    sampler: str = "iid_mc"
    stress_case: bool = False


@dataclass(frozen=True)
class MorrisBenchmarkCase:
    """Executable Morris benchmark case based on elementary-effect sampling."""

    benchmark_id: str
    parameter_names: tuple[str, ...]
    effect_sampler: Callable[[np.random.Generator, int], np.ndarray]
    truth: SensitivityTruth
    optimized_trajectories: bool = False
    stress_case: bool = False


def sobol_linear_function(x: np.ndarray, coefficients: Mapping[str, float]) -> np.ndarray:
    """Evaluate ``f(x)=sum a_i x_i`` on unit-cube samples."""

    coeff_vector = np.asarray([float(value) for value in coefficients.values()], dtype=float)
    samples = np.asarray(x, dtype=float)
    return samples @ coeff_vector


def sobol_linear_truth(coefficients: Mapping[str, float], *, benchmark_id: str = "sobol_linear") -> SensitivityTruth:
    """Analytic Sobol truth for ``f(x)=sum a_i x_i`` with iid U(0,1) inputs."""

    names = list(coefficients)
    variances = {name: float(coefficients[name]) ** 2 / 12.0 for name in names}
    total = sum(variances.values())
    indices = {
        "S1": {name: (variances[name] / total if total > 0.0 else 0.0) for name in names},
        "ST": {name: (variances[name] / total if total > 0.0 else 0.0) for name in names},
        "S2": {},
    }
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            indices["S2"][f"{left}:{right}"] = 0.0
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=names,
        indices=indices,
        rank_metric="ST",
    )


def ishigami_function_unit(x: np.ndarray, *, a: float = 7.0, b: float = 0.1) -> np.ndarray:
    """Evaluate the Ishigami function after mapping unit-cube inputs to ``[-pi, pi]``."""

    samples = -math.pi + 2.0 * math.pi * np.asarray(x, dtype=float)
    x1 = samples[:, 0]
    x2 = samples[:, 1]
    x3 = samples[:, 2]
    return np.sin(x1) + a * np.sin(x2) ** 2 + b * x3**4 * np.sin(x1)


def ishigami_truth(
    *,
    a: float = 7.0,
    b: float = 0.1,
    benchmark_id: str = "sobol_ishigami",
) -> SensitivityTruth:
    """Analytic Sobol truth for the standard Ishigami function on ``[-pi, pi]^3``."""

    pi = math.pi
    variance = (a**2 / 8.0) + (b * pi**4 / 5.0) + (b**2 * pi**8 / 18.0) + 0.5
    s1 = 0.5 * (1.0 + b * pi**4 / 5.0) ** 2 / variance
    s2 = (a**2 / 8.0) / variance
    s13 = (8.0 * b**2 * pi**8 / 225.0) / variance
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=["x1", "x2", "x3"],
        indices={
            "S1": {"x1": float(s1), "x2": float(s2), "x3": 0.0},
            "ST": {"x1": float(s1 + s13), "x2": float(s2), "x3": float(s13)},
            "S2": {"x1:x2": 0.0, "x1:x3": float(s13), "x2:x3": 0.0},
        },
        rank_metric="ST",
    )


def sobol_g_function(x: np.ndarray, a_values: Mapping[str, float]) -> np.ndarray:
    """Evaluate the Sobol G-function on unit-cube samples."""

    samples = np.asarray(x, dtype=float)
    a_vector = np.asarray([float(value) for value in a_values.values()], dtype=float)
    return np.prod((np.abs(4.0 * samples - 2.0) + a_vector[None, :]) / (1.0 + a_vector[None, :]), axis=1)


def sobol_g_function_truth(
    a_values: Mapping[str, float],
    *,
    benchmark_id: str = "sobol_g_function",
) -> SensitivityTruth:
    """Analytic Sobol truth for the Sobol G-function with iid U(0,1) inputs."""

    names = list(a_values)
    component_var = {name: 1.0 / (3.0 * (1.0 + float(a_values[name])) ** 2) for name in names}
    total_variance = float(np.prod([1.0 + component_var[name] for name in names]) - 1.0)
    s1 = {name: component_var[name] / total_variance for name in names}
    st = {
        name: (
            component_var[name]
            * float(np.prod([1.0 + component_var[other] for other in names if other != name]))
            / total_variance
        )
        for name in names
    }
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=names,
        indices={"S1": s1, "ST": st, "S2": {}},
        rank_metric="ST",
    )


def sobol_sparse_interaction_function(
    x: np.ndarray,
    coefficients: Mapping[str, float],
    interactions: Mapping[str, float],
) -> np.ndarray:
    """Evaluate a centered sparse additive model with pairwise interactions."""

    names = list(coefficients)
    samples = np.asarray(x, dtype=float) - 0.5
    values = samples @ np.asarray([float(coefficients[name]) for name in names], dtype=float)
    name_to_idx = {name: idx for idx, name in enumerate(names)}
    for pair, coeff in interactions.items():
        left, right = pair.split(":", 1)
        values = values + float(coeff) * samples[:, name_to_idx[left]] * samples[:, name_to_idx[right]]
    return values


def sobol_sparse_interaction_truth(
    coefficients: Mapping[str, float],
    interactions: Mapping[str, float],
    *,
    benchmark_id: str = "sobol_sparse_interaction",
) -> SensitivityTruth:
    """Analytic truth for centered sparse additive plus pairwise interaction models."""

    names = list(coefficients)
    base_var = 1.0 / 12.0
    additive = {name: float(coefficients.get(name, 0.0)) ** 2 * base_var for name in names}
    pair_vars: dict[str, float] = {}
    for pair, coeff in interactions.items():
        left, right = pair.split(":", 1)
        if left not in names or right not in names or left == right:
            raise ValueError(f"invalid interaction pair: {pair}")
        normalized_pair = _pair_key(left, right, names)
        pair_vars[normalized_pair] = float(coeff) ** 2 * base_var**2
    total = sum(additive.values()) + sum(pair_vars.values())
    s1 = {name: (additive[name] / total if total > 0.0 else 0.0) for name in names}
    st = {}
    for name in names:
        interaction_share = sum(value for pair, value in pair_vars.items() if name in pair.split(":"))
        st[name] = (additive[name] + interaction_share) / total if total > 0.0 else 0.0
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=names,
        indices={
            "S1": s1,
            "ST": st,
            "S2": {pair: (value / total if total > 0.0 else 0.0) for pair, value in pair_vars.items()},
        },
        rank_metric="ST",
    )


def sobol_discontinuous_threshold_function(
    x: np.ndarray,
    weights: Mapping[str, float],
    *,
    threshold: float,
) -> np.ndarray:
    """Evaluate a discontinuous weighted-threshold benchmark on unit-cube samples."""

    samples = np.asarray(x, dtype=float)
    weight_vector = np.asarray([float(value) for value in weights.values()], dtype=float)
    return (samples @ weight_vector > threshold).astype(float)


def sobol_heavy_tailed_additive_function(
    x: np.ndarray,
    coefficients: Mapping[str, float],
    *,
    tail_power: float = 0.45,
) -> np.ndarray:
    """Evaluate a finite-variance heavy-tailed additive benchmark."""

    if not 0.0 < tail_power < 0.5:
        raise ValueError("tail_power must be in (0, 0.5) to keep finite variance")
    samples = np.asarray(x, dtype=float)
    transformed = np.power(np.clip(1.0 - samples, 1e-12, 1.0), -tail_power)
    transformed = transformed - (1.0 / (1.0 - tail_power))
    coeff_vector = np.asarray([float(value) for value in coefficients.values()], dtype=float)
    return transformed @ coeff_vector


def sobol_heavy_tailed_additive_truth(
    coefficients: Mapping[str, float],
    *,
    tail_power: float = 0.45,
    benchmark_id: str = "sobol_heavy_tailed_additive",
) -> SensitivityTruth:
    """Analytic Sobol truth for the finite-variance heavy-tailed additive benchmark."""

    if not 0.0 < tail_power < 0.5:
        raise ValueError("tail_power must be in (0, 0.5) to keep finite variance")
    names = list(coefficients)
    component_variance = 1.0 / (1.0 - 2.0 * tail_power) - (1.0 / (1.0 - tail_power)) ** 2
    variances = {name: float(coefficients[name]) ** 2 * component_variance for name in names}
    total = sum(variances.values())
    indices = {
        "S1": {name: (variances[name] / total if total > 0.0 else 0.0) for name in names},
        "ST": {name: (variances[name] / total if total > 0.0 else 0.0) for name in names},
        "S2": {},
    }
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            indices["S2"][f"{left}:{right}"] = 0.0
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=names,
        indices=indices,
        rank_metric="ST",
    )


def reference_sobol_truth(
    evaluator: Callable[[np.ndarray], np.ndarray],
    parameter_names: Sequence[str],
    *,
    benchmark_id: str,
    sample_size: int = 20_000,
    seed: int = 20260426,
) -> SensitivityTruth:
    """Estimate Sobol truth by a large iid pick-freeze reference run."""

    names = tuple(parameter_names)
    rng = np.random.default_rng(seed)
    blocks = _sample_sobol_pick_freeze_blocks(evaluator, names, sample_size, rng)
    labels, values = _sobol_estimates(blocks)
    indices: dict[str, dict[str, float]] = {"S1": {}, "ST": {}, "S2": {}}
    for (index, parameter), value in zip(labels, values, strict=True):
        indices.setdefault(index, {})[parameter] = float(value)
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=list(names),
        indices=indices,
        rank_metric="ST",
        truth_source=f"reference_mc_n{sample_size}",
    )


def morris_linear_truth(coefficients: Mapping[str, float], *, benchmark_id: str = "morris_linear") -> SensitivityTruth:
    """Analytic Morris truth for a linear additive function."""

    names = list(coefficients)
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=names,
        indices={
            "mu": {name: float(coefficients[name]) for name in names},
            "mu_star": {name: abs(float(coefficients[name])) for name in names},
            "sigma": dict.fromkeys(names, 0.0),
        },
        rank_metric="mu_star",
    )


def morris_quadratic_truth(
    coefficients: Mapping[str, float],
    *,
    benchmark_id: str = "morris_quadratic_derivative_reference",
) -> SensitivityTruth:
    """Derivative-reference Morris truth for ``f(x)=sum a_i x_i^2``."""

    names = list(coefficients)
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=names,
        indices={
            "mu": {name: float(coefficients[name]) for name in names},
            "mu_star": {name: abs(float(coefficients[name])) for name in names},
            "sigma": {name: abs(float(coefficients[name])) / math.sqrt(3.0) for name in names},
        },
        rank_metric="mu_star",
        truth_source="analytic_derivative_reference",
    )


def morris_interaction_truth(
    coefficients: Mapping[str, float],
    *,
    interaction_pair: tuple[str, str],
    interaction_coefficient: float = 1.0,
    benchmark_id: str = "morris_pairwise_interaction",
) -> SensitivityTruth:
    """Derivative-reference Morris truth for ``c*x_i*x_j + sum a_i*x_i``."""

    names = list(coefficients)
    left, right = interaction_pair
    if left not in names or right not in names or left == right:
        raise ValueError("interaction_pair must contain two distinct known parameter names")
    c = float(interaction_coefficient)
    mu: dict[str, float] = {}
    mu_star: dict[str, float] = {}
    sigma: dict[str, float] = {}
    for name in names:
        base = float(coefficients[name])
        if name in {left, right}:
            mu[name] = base + c / 2.0
            mu_star[name] = _uniform_abs_mean(base, c)
            sigma[name] = abs(c) / math.sqrt(12.0)
        else:
            mu[name] = base
            mu_star[name] = abs(base)
            sigma[name] = 0.0
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=names,
        indices={"mu": mu, "mu_star": mu_star, "sigma": sigma},
        rank_metric="mu_star",
        truth_source="analytic_derivative_reference",
    )


def morris_nonmonotonic_truth(
    coefficients: Mapping[str, float],
    *,
    benchmark_id: str = "morris_nonmonotonic_cancellation",
) -> SensitivityTruth:
    """Derivative-reference Morris truth for ``sum a_i sin(2*pi*x_i)``."""

    names = list(coefficients)
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=names,
        indices={
            "mu": dict.fromkeys(names, 0.0),
            "mu_star": {name: 4.0 * abs(float(coefficients[name])) for name in names},
            "sigma": {name: math.sqrt(2.0) * math.pi * abs(float(coefficients[name])) for name in names},
        },
        rank_metric="mu_star",
        truth_source="analytic_derivative_reference",
    )


def morris_sparse_screening_truth(
    dimension: int,
    active_coefficients: Mapping[str, float],
    *,
    benchmark_id: str = "morris_sparse_screening",
) -> SensitivityTruth:
    """High-dimensional sparse Morris screening truth with inactive dummy factors."""

    coefficients = {f"x{i}": 0.0 for i in range(1, dimension + 1)}
    coefficients.update({name: float(value) for name, value in active_coefficients.items()})
    return morris_linear_truth(coefficients, benchmark_id=benchmark_id).model_copy(
        update={"truth_source": "analytic_sparse_linear"}
    )


def morris_grouped_truth(
    groups: Mapping[str, Sequence[str]],
    coefficients: Mapping[str, float],
    *,
    benchmark_id: str = "morris_grouped_factors",
) -> SensitivityTruth:
    """Group-level Morris truth when a group is moved as one linear factor block."""

    group_mu = {group: sum(float(coefficients.get(name, 0.0)) for name in members) for group, members in groups.items()}
    return SensitivityTruth(
        benchmark_id=benchmark_id,
        parameter_names=list(groups),
        indices={
            "mu": group_mu,
            "mu_star": {group: abs(value) for group, value in group_mu.items()},
            "sigma": dict.fromkeys(groups, 0.0),
        },
        rank_metric="mu_star",
        truth_source="analytic_grouped_linear",
    )


def default_sensitivity_truth_suite() -> list[SensitivityTruth]:
    """Return the built-in analytic truth suite used by CI benchmark smoke and release runs."""

    return [
        sobol_linear_truth({"x1": 2.0, "x2": 1.0, "x3": 0.25}),
        ishigami_truth(),
        sobol_g_function_truth({"x1": 0.0, "x2": 1.0, "x3": 9.0, "x4": 99.0}),
        sobol_sparse_interaction_truth(
            {f"x{i}": (2.0 if i == 1 else 0.2 if i <= 4 else 0.0) for i in range(1, 21)},
            {"x1:x2": 1.5, "x3:x4": 0.5},
            benchmark_id="sobol_sparse_high_d_interactions",
        ),
        morris_linear_truth({"x1": 2.0, "x2": -1.0, "x3": 0.0}),
        morris_quadratic_truth({"x1": 2.0, "x2": -1.0, "x3": 0.25}),
        morris_interaction_truth(
            {"x1": 0.2, "x2": 0.0, "x3": 1.0},
            interaction_pair=("x1", "x2"),
        ),
        morris_nonmonotonic_truth({"x1": 1.0, "x2": 0.25, "x3": 0.0}),
        morris_sparse_screening_truth(50, {"x1": 2.0, "x4": 1.0, "x9": 0.5}),
        morris_grouped_truth(
            {"g1": ("x1", "x2"), "g2": ("x3",), "g3": ("x4", "x5")},
            {"x1": 1.0, "x2": 0.5, "x3": -0.25, "x4": 0.1, "x5": 0.1},
        ),
        sobol_heavy_tailed_additive_truth({"x1": 2.0, "x2": 1.0, "x3": 0.0}),
    ]


def default_sobol_benchmark_cases(
    *,
    reference_sample_size: int = 20_000,
    seed: int = 20260426,
) -> list[SobolBenchmarkCase]:
    """Return executable Sobol cases covering smooth, sparse, discontinuous, and heavy-tail models."""

    linear_coefficients = {"x1": 2.0, "x2": 1.0, "x3": 0.25}
    g_values = {"x1": 0.0, "x2": 1.0, "x3": 9.0, "x4": 99.0}
    sparse_coefficients = {f"x{i}": (2.0 if i == 1 else 0.2 if i <= 4 else 0.0) for i in range(1, 21)}
    sparse_interactions = {"x1:x2": 1.5, "x3:x4": 0.5}
    threshold_weights = {"x1": 1.0, "x2": 0.7, "x3": 0.2, "x4": 0.1}
    heavy_coefficients = {"x1": 2.0, "x2": 1.0, "x3": 0.0}
    threshold_evaluator = lambda x: sobol_discontinuous_threshold_function(
        x,
        threshold_weights,
        threshold=1.15,
    )
    threshold_truth = reference_sobol_truth(
        threshold_evaluator,
        tuple(threshold_weights),
        benchmark_id="sobol_discontinuous_threshold",
        sample_size=reference_sample_size,
        seed=seed,
    )
    return [
        SobolBenchmarkCase(
            benchmark_id="sobol_linear",
            parameter_names=tuple(linear_coefficients),
            evaluator=lambda x: sobol_linear_function(x, linear_coefficients),
            truth=sobol_linear_truth(linear_coefficients),
        ),
        SobolBenchmarkCase(
            benchmark_id="sobol_ishigami",
            parameter_names=("x1", "x2", "x3"),
            evaluator=ishigami_function_unit,
            truth=ishigami_truth(),
        ),
        SobolBenchmarkCase(
            benchmark_id="sobol_g_function",
            parameter_names=tuple(g_values),
            evaluator=lambda x: sobol_g_function(x, g_values),
            truth=sobol_g_function_truth(g_values),
        ),
        SobolBenchmarkCase(
            benchmark_id="sobol_sparse_high_d_interactions",
            parameter_names=tuple(sparse_coefficients),
            evaluator=lambda x: sobol_sparse_interaction_function(x, sparse_coefficients, sparse_interactions),
            truth=sobol_sparse_interaction_truth(
                sparse_coefficients,
                sparse_interactions,
                benchmark_id="sobol_sparse_high_d_interactions",
            ),
        ),
        SobolBenchmarkCase(
            benchmark_id="sobol_discontinuous_threshold",
            parameter_names=tuple(threshold_weights),
            evaluator=threshold_evaluator,
            truth=threshold_truth,
            stress_case=True,
        ),
        SobolBenchmarkCase(
            benchmark_id="sobol_heavy_tailed_additive",
            parameter_names=tuple(heavy_coefficients),
            evaluator=lambda x: sobol_heavy_tailed_additive_function(x, heavy_coefficients),
            truth=sobol_heavy_tailed_additive_truth(heavy_coefficients),
            stress_case=True,
        ),
    ]


def default_morris_benchmark_cases() -> list[MorrisBenchmarkCase]:
    """Return executable Morris cases covering linear, nonlinear, interaction, sparse, and grouped effects."""

    linear_coefficients = {"x1": 2.0, "x2": -1.0, "x3": 0.0}
    quadratic_coefficients = {"x1": 2.0, "x2": -1.0, "x3": 0.25}
    interaction_coefficients = {"x1": 0.2, "x2": 0.0, "x3": 1.0}
    nonmonotonic_coefficients = {"x1": 1.0, "x2": 0.25, "x3": 0.0}
    sparse_truth = morris_sparse_screening_truth(50, {"x1": 2.0, "x4": 1.0, "x9": 0.5})
    groups = {"g1": ("x1", "x2"), "g2": ("x3",), "g3": ("x4", "x5")}
    grouped_truth = morris_grouped_truth(
        groups,
        {"x1": 1.0, "x2": 0.5, "x3": -0.25, "x4": 0.1, "x5": 0.1},
    )
    return [
        MorrisBenchmarkCase(
            benchmark_id="morris_linear",
            parameter_names=tuple(linear_coefficients),
            effect_sampler=lambda rng, r: _sample_linear_effects(linear_coefficients, r),
            truth=morris_linear_truth(linear_coefficients),
        ),
        MorrisBenchmarkCase(
            benchmark_id="morris_quadratic_derivative_reference",
            parameter_names=tuple(quadratic_coefficients),
            effect_sampler=lambda rng, r: _sample_quadratic_derivative_effects(
                rng,
                quadratic_coefficients,
                r,
            ),
            truth=morris_quadratic_truth(quadratic_coefficients),
        ),
        MorrisBenchmarkCase(
            benchmark_id="morris_pairwise_interaction",
            parameter_names=tuple(interaction_coefficients),
            effect_sampler=lambda rng, r: _sample_interaction_derivative_effects(
                rng,
                interaction_coefficients,
                interaction_pair=("x1", "x2"),
                interaction_coefficient=1.0,
                trajectories=r,
            ),
            truth=morris_interaction_truth(interaction_coefficients, interaction_pair=("x1", "x2")),
        ),
        MorrisBenchmarkCase(
            benchmark_id="morris_nonmonotonic_cancellation",
            parameter_names=tuple(nonmonotonic_coefficients),
            effect_sampler=lambda rng, r: _sample_nonmonotonic_derivative_effects(
                rng,
                nonmonotonic_coefficients,
                r,
            ),
            truth=morris_nonmonotonic_truth(nonmonotonic_coefficients),
            stress_case=True,
        ),
        MorrisBenchmarkCase(
            benchmark_id=sparse_truth.benchmark_id,
            parameter_names=tuple(sparse_truth.parameter_names),
            effect_sampler=lambda rng, r: _sample_linear_effects(
                sparse_truth.indices["mu"],
                r,
            ),
            truth=sparse_truth,
            stress_case=True,
        ),
        MorrisBenchmarkCase(
            benchmark_id=grouped_truth.benchmark_id,
            parameter_names=tuple(grouped_truth.parameter_names),
            effect_sampler=lambda rng, r: _sample_linear_effects(
                grouped_truth.indices["mu"],
                r,
            ),
            truth=grouped_truth,
            optimized_trajectories=True,
        ),
    ]


def evaluate_coverage_observation(
    bundle: SensitivityUncertaintyBundle,
    truth: SensitivityTruth,
    *,
    level: float = 0.95,
    top_k: int = 3,
) -> CoverageObservation:
    """Compare one uncertainty bundle to known truth."""

    del level
    covered: dict[str, bool] = {}
    widths: dict[str, float] = {}
    scores: dict[str, float] = {}
    miss_direction: dict[str, str] = {}
    boundary_failures: dict[str, bool] = {}
    simultaneous_flags: list[bool] = []
    alpha = 0.05

    for item in bundle.sensitivity_results:
        true_value = truth.indices.get(item.index, {}).get(item.parameter)
        if true_value is None or item.ci is None:
            continue
        key = f"{item.index}:{item.parameter}"
        covered[key] = item.ci.low <= true_value <= item.ci.high
        widths[key] = item.ci.high - item.ci.low
        scores[key] = _interval_score(item.ci, true_value, alpha)
        if true_value < item.ci.low:
            miss_direction[key] = "below"
        elif true_value > item.ci.high:
            miss_direction[key] = "above"
        boundary_failures[key] = bool(
            item.diagnostics.degenerate or item.diagnostics.bootstrap_out_of_bounds_rate > 0.05
        )
        if item.simultaneous_ci is not None:
            simultaneous_flags.append(item.simultaneous_ci.low <= true_value <= item.simultaneous_ci.high)

    rank_covered = _rank_covered(bundle, truth)
    top_k_covered = _top_k_covered(bundle, truth, top_k=top_k)
    pairwise_bins = _pairwise_bin_counts(bundle, truth)

    return CoverageObservation(
        covered=covered,
        simultaneous_covered=(all(simultaneous_flags) if simultaneous_flags else None),
        widths=widths,
        interval_scores=scores,
        miss_direction=miss_direction,
        boundary_failures=boundary_failures,
        rank_covered=rank_covered,
        top_k_covered=top_k_covered,
        pairwise_bins=pairwise_bins,
    )


def summarize_coverage_observations(
    observations: Sequence[CoverageObservation],
    *,
    scenario_id: str,
    method: str,
    index_types: Sequence[str],
    sampler: str,
    dimension: int,
    sample_size: int,
    nominal_level: float,
    criteria: CoverageAcceptanceCriteria | None = None,
) -> CoverageScenarioResult:
    """Aggregate per-repetition observations into benchmark metrics."""

    if not observations:
        raise ValueError("observations must not be empty")
    criteria = criteria or CoverageAcceptanceCriteria()
    all_covered = [flag for obs in observations for flag in obs.covered.values()]
    all_widths = [width for obs in observations for width in obs.widths.values()]
    all_scores = [score for obs in observations for score in obs.interval_scores.values()]
    below = sum(1 for obs in observations for value in obs.miss_direction.values() if value == "below")
    above = sum(1 for obs in observations for value in obs.miss_direction.values() if value == "above")
    misses = below + above
    boundary = [flag for obs in observations for flag in obs.boundary_failures.values()]
    simultaneous = [obs.simultaneous_covered for obs in observations if obs.simultaneous_covered is not None]
    rank = [obs.rank_covered for obs in observations if obs.rank_covered is not None]
    top_k = [obs.top_k_covered for obs in observations if obs.top_k_covered is not None]

    pairwise_calibration = _aggregate_pairwise_bins(observations)
    marginal = float(np.mean(all_covered)) if all_covered else 0.0
    result = CoverageScenarioResult(
        scenario_id=scenario_id,
        method=method,
        index_types=list(index_types),
        sampler=sampler,
        dimension=dimension,
        sample_size=sample_size,
        n_repetitions=len(observations),
        nominal_level=nominal_level,
        marginal_coverage=marginal,
        simultaneous_coverage=float(np.mean(simultaneous)) if simultaneous else None,
        mean_interval_width=float(np.mean(all_widths)) if all_widths else math.inf,
        median_interval_width=float(np.median(all_widths)) if all_widths else math.inf,
        interval_score=float(np.mean(all_scores)) if all_scores else math.inf,
        miss_below_rate=(below / misses if misses else 0.0),
        miss_above_rate=(above / misses if misses else 0.0),
        boundary_failure_rate=float(np.mean(boundary)) if boundary else 0.0,
        rank_coverage=float(np.mean(rank)) if rank else None,
        top_k_coverage=float(np.mean(top_k)) if top_k else None,
        pairwise_calibration=pairwise_calibration,
    )
    approved, notes = evaluate_acceptance(result, criteria)
    return result.model_copy(update={"approved": approved, "approval_notes": notes})


def evaluate_acceptance(
    result: CoverageScenarioResult,
    criteria: CoverageAcceptanceCriteria | None = None,
    *,
    stress_case: bool = False,
) -> tuple[bool, list[str]]:
    """Apply catalog approval criteria to a scenario result."""

    criteria = criteria or CoverageAcceptanceCriteria()
    notes: list[str] = []
    if stress_case:
        if result.marginal_coverage < criteria.marginal_stress_floor:
            notes.append("marginal_coverage_below_stress_floor")
    elif not (
        criteria.marginal_ordinary_low <= result.marginal_coverage <= criteria.marginal_ordinary_high
    ):
        notes.append("marginal_coverage_outside_ordinary_band")
    if (
        result.simultaneous_coverage is not None
        and result.simultaneous_coverage < criteria.simultaneous_floor
    ):
        notes.append("simultaneous_coverage_below_floor")
    if result.boundary_failure_rate > criteria.boundary_failure_max:
        notes.append("boundary_failure_rate_too_high")
    for bin_label, calibration in result.pairwise_calibration.items():
        if bin_label == "0.9-1.0" and calibration < criteria.pairwise_dominance_floor:
            notes.append("pairwise_dominance_under_calibrated")
    if criteria.max_mean_width is not None and result.mean_interval_width > criteria.max_mean_width:
        notes.append("mean_interval_width_too_large")
    return not notes, notes


def build_coverage_profile(
    *,
    coverage_profile_id: str,
    method: str,
    index_types: Sequence[str],
    samplers: Sequence[str],
    benchmark_commit: str,
    scenario_results: Sequence[CoverageScenarioResult],
    nominal_levels_tested: Sequence[float] = (0.90, 0.95, 0.99),
    calibrated_multiplier: float | None = None,
) -> SensitivityCoverageProfile:
    """Build a versioned catalog calibration profile from benchmark scenarios."""

    if not scenario_results:
        raise ValueError("scenario_results must not be empty")
    coverages = [
        result.marginal_coverage
        for result in scenario_results
        if abs(result.nominal_level - 0.95) < 1e-9
    ] or [result.marginal_coverage for result in scenario_results]
    approved = all(result.approved for result in scenario_results)
    notes = sorted({note for result in scenario_results for note in result.approval_notes})
    return SensitivityCoverageProfile(
        coverage_profile_id=coverage_profile_id,
        method=method,
        index_types=list(index_types),
        samplers=list(samplers),
        benchmark_commit=benchmark_commit,
        nominal_levels_tested=list(nominal_levels_tested),
        coverage_summary=CoverageSummary(
            min_95_coverage=float(np.min(coverages)),
            median_95_coverage=float(np.median(coverages)),
            max_95_coverage=float(np.max(coverages)),
        ),
        approved=approved,
        calibrated_multiplier=calibrated_multiplier,
        acceptance_notes=notes,
    )


def run_sobol_linear_coverage_benchmark(
    coefficients: Mapping[str, float],
    *,
    sample_size: int,
    repetitions: int,
    uncertainty_config: SensitivityUncertaintyConfig | None = None,
    seed: int = 20260426,
) -> CoverageScenarioResult:
    """Run a self-contained iid Monte Carlo coverage benchmark for an additive linear model."""

    truth = sobol_linear_truth(coefficients)
    return run_sobol_iid_coverage_benchmark(
        lambda x: sobol_linear_function(x, coefficients),
        truth,
        sample_size=sample_size,
        repetitions=repetitions,
        uncertainty_config=uncertainty_config,
        seed=seed,
    )


def run_sobol_iid_coverage_benchmark(
    evaluator: Callable[[np.ndarray], np.ndarray],
    truth: SensitivityTruth,
    *,
    sample_size: int,
    repetitions: int,
    uncertainty_config: SensitivityUncertaintyConfig | None = None,
    seed: int = 20260426,
    criteria: CoverageAcceptanceCriteria | None = None,
) -> CoverageScenarioResult:
    """Run an iid pick-freeze Sobol coverage benchmark for a supplied model and truth."""

    cfg = uncertainty_config or SensitivityUncertaintyConfig(
        enabled=True,
        method="percentile",
        n_resamples=199,
        random_seed=seed,
    )
    rng = np.random.default_rng(seed)
    observations: list[CoverageObservation] = []
    for rep in range(repetitions):
        blocks = _sample_sobol_pick_freeze_blocks(evaluator, truth.parameter_names, sample_size, rng)
        rep_cfg = cfg.model_copy(update={"random_seed": seed + rep})
        bundle = analyze_sobol_paired_bootstrap(blocks, rep_cfg)
        observations.append(evaluate_coverage_observation(bundle, truth, level=cfg.level))
    return summarize_coverage_observations(
        observations,
        scenario_id=truth.benchmark_id,
        method="paired_bootstrap",
        index_types=tuple(truth.indices.keys()),
        sampler="iid_mc",
        dimension=len(truth.parameter_names),
        sample_size=sample_size,
        nominal_level=cfg.level,
        criteria=criteria,
    )


def run_morris_effect_coverage_benchmark(
    effect_sampler: Callable[[np.random.Generator, int], np.ndarray],
    truth: SensitivityTruth,
    *,
    trajectories: int,
    repetitions: int,
    uncertainty_config: SensitivityUncertaintyConfig | None = None,
    seed: int = 20260426,
    optimized_trajectories: bool = False,
    criteria: CoverageAcceptanceCriteria | None = None,
) -> CoverageScenarioResult:
    """Run a Morris coverage benchmark from sampled elementary-effect matrices."""

    cfg = uncertainty_config or SensitivityUncertaintyConfig(
        enabled=True,
        method="percentile",
        n_resamples=199,
        random_seed=seed,
    )
    rng = np.random.default_rng(seed)
    observations: list[CoverageObservation] = []
    for rep in range(repetitions):
        effects = effect_sampler(rng, trajectories)
        rep_cfg = cfg.model_copy(update={"random_seed": seed + rep})
        bundle = analyze_morris_trajectory_bootstrap(effects, truth.parameter_names, rep_cfg)
        observations.append(evaluate_coverage_observation(bundle, truth, level=cfg.level))
    return summarize_coverage_observations(
        observations,
        scenario_id=truth.benchmark_id,
        method="trajectory_bootstrap",
        index_types=tuple(truth.indices.keys()),
        sampler="optimized_morris" if optimized_trajectories else "random_morris",
        dimension=len(truth.parameter_names),
        sample_size=trajectories,
        nominal_level=cfg.level,
        criteria=criteria,
    )


def learn_calibrated_multiplier(required_ratios: Sequence[float], *, nominal_level: float = 0.95) -> float:
    """Learn a conservative interval-width multiplier from holdout required-width ratios."""

    ratios = np.asarray(required_ratios, dtype=float)
    ratios = ratios[np.isfinite(ratios)]
    if ratios.size == 0:
        return 1.0
    return max(1.0, float(np.quantile(ratios, nominal_level)))


def _sample_sobol_pick_freeze_blocks(
    evaluator: Callable[[np.ndarray], np.ndarray],
    parameter_names: Sequence[str],
    sample_size: int,
    rng: np.random.Generator,
) -> SobolRowBlockData:
    dimension = len(parameter_names)
    a = rng.random((sample_size, dimension))
    b = rng.random((sample_size, dimension))
    y_a = evaluator(a)
    y_b = evaluator(b)
    y_ab = np.empty((sample_size, dimension), dtype=float)
    for col in range(dimension):
        mixed = a.copy()
        mixed[:, col] = b[:, col]
        y_ab[:, col] = evaluator(mixed)
    return SobolRowBlockData(
        y_a=y_a,
        y_b=y_b,
        y_ab=y_ab,
        parameter_names=tuple(parameter_names),
    )


def _sample_linear_effects(coefficients: Mapping[str, float], trajectories: int) -> np.ndarray:
    values = np.asarray([float(value) for value in coefficients.values()], dtype=float)
    return np.tile(values[None, :], (trajectories, 1))


def _sample_quadratic_derivative_effects(
    rng: np.random.Generator,
    coefficients: Mapping[str, float],
    trajectories: int,
) -> np.ndarray:
    values = np.asarray([float(value) for value in coefficients.values()], dtype=float)
    return 2.0 * rng.random((trajectories, values.size)) * values[None, :]


def _sample_interaction_derivative_effects(
    rng: np.random.Generator,
    coefficients: Mapping[str, float],
    *,
    interaction_pair: tuple[str, str],
    interaction_coefficient: float,
    trajectories: int,
) -> np.ndarray:
    names = list(coefficients)
    effects = _sample_linear_effects(coefficients, trajectories)
    left, right = interaction_pair
    left_idx = names.index(left)
    right_idx = names.index(right)
    samples = rng.random((trajectories, len(names)))
    effects[:, left_idx] += interaction_coefficient * samples[:, right_idx]
    effects[:, right_idx] += interaction_coefficient * samples[:, left_idx]
    return effects


def _sample_nonmonotonic_derivative_effects(
    rng: np.random.Generator,
    coefficients: Mapping[str, float],
    trajectories: int,
) -> np.ndarray:
    values = np.asarray([float(value) for value in coefficients.values()], dtype=float)
    samples = rng.random((trajectories, values.size))
    return 2.0 * math.pi * values[None, :] * np.cos(2.0 * math.pi * samples)


def _interval_score(interval: SensitivityInterval, truth: float, alpha: float) -> float:
    width = interval.high - interval.low
    below_penalty = (2.0 / alpha) * (interval.low - truth) if truth < interval.low else 0.0
    above_penalty = (2.0 / alpha) * (truth - interval.high) if truth > interval.high else 0.0
    return float(width + below_penalty + above_penalty)


def _rank_covered(bundle: SensitivityUncertaintyBundle, truth: SensitivityTruth) -> bool | None:
    rank_probs = bundle.joint_uncertainty.rank_probabilities
    if not rank_probs:
        return None
    true_order = _truth_order(truth)
    for true_rank_zero, name in enumerate(true_order):
        if rank_probs.get(name, {}).get(str(true_rank_zero + 1), 0.0) <= 0.0:
            return False
    return True


def _top_k_covered(
    bundle: SensitivityUncertaintyBundle,
    truth: SensitivityTruth,
    *,
    top_k: int,
) -> bool | None:
    probs = bundle.joint_uncertainty.top_k_probabilities
    if not probs:
        return None
    truth_top = set(_truth_order(truth)[: min(top_k, len(truth.parameter_names))])
    key = f"top{min(top_k, len(truth.parameter_names))}"
    return all(probs.get(name, {}).get(key, 0.0) > 0.0 for name in truth_top)


def _truth_order(truth: SensitivityTruth) -> list[str]:
    metric = truth.indices.get(truth.rank_metric, {})
    return sorted(truth.parameter_names, key=lambda name: metric.get(name, 0.0), reverse=True)


def _pair_key(left: str, right: str, names: Sequence[str]) -> str:
    ordered = {name: idx for idx, name in enumerate(names)}
    return f"{left}:{right}" if ordered[left] < ordered[right] else f"{right}:{left}"


def _uniform_abs_mean(offset: float, slope: float) -> float:
    if abs(slope) <= 1e-12:
        return abs(offset)
    end = offset + slope
    if offset >= 0.0 and end >= 0.0:
        return offset + slope / 2.0
    if offset <= 0.0 and end <= 0.0:
        return -(offset + slope / 2.0)
    crossing = min(max(-offset / slope, 0.0), 1.0)

    def antiderivative(u: float) -> float:
        return offset * u + slope * u * u / 2.0

    return abs(antiderivative(crossing) - antiderivative(0.0)) + abs(
        antiderivative(1.0) - antiderivative(crossing)
    )


def _pairwise_bin_counts(
    bundle: SensitivityUncertaintyBundle,
    truth: SensitivityTruth,
) -> dict[str, tuple[int, int]]:
    truth_metric = truth.indices.get(truth.rank_metric, {})
    bins: dict[str, tuple[int, int]] = {}
    for pair, probability in bundle.joint_uncertainty.pairwise_dominance.items():
        if ">" not in pair:
            continue
        left, right = pair.split(">", 1)
        if left not in truth_metric or right not in truth_metric:
            continue
        label = _dominance_bin(probability)
        correct = int(truth_metric[left] > truth_metric[right])
        prev_correct, prev_total = bins.get(label, (0, 0))
        bins[label] = (prev_correct + correct, prev_total + 1)
    return bins


def _aggregate_pairwise_bins(observations: Sequence[CoverageObservation]) -> dict[str, float]:
    totals: dict[str, tuple[int, int]] = {}
    for observation in observations:
        for label, (correct, total) in observation.pairwise_bins.items():
            prev_correct, prev_total = totals.get(label, (0, 0))
            totals[label] = (prev_correct + correct, prev_total + total)
    return {
        label: correct / total
        for label, (correct, total) in totals.items()
        if total > 0
    }


def _dominance_bin(probability: float) -> str:
    if probability >= 0.9:
        return "0.9-1.0"
    if probability >= 0.7:
        return "0.7-0.9"
    if probability >= 0.5:
        return "0.5-0.7"
    return "0.0-0.5"


__all__ = [
    "CoverageAcceptanceCriteria",
    "CoverageBenchmarkConfig",
    "CoverageObservation",
    "CoverageScenarioResult",
    "CoverageSummary",
    "MorrisBenchmarkCase",
    "SobolBenchmarkCase",
    "SensitivityCoverageProfile",
    "SensitivityTruth",
    "build_coverage_profile",
    "default_morris_benchmark_cases",
    "default_sobol_benchmark_cases",
    "default_sensitivity_truth_suite",
    "evaluate_acceptance",
    "evaluate_coverage_observation",
    "ishigami_function_unit",
    "ishigami_truth",
    "learn_calibrated_multiplier",
    "morris_grouped_truth",
    "morris_interaction_truth",
    "morris_linear_truth",
    "morris_nonmonotonic_truth",
    "morris_quadratic_truth",
    "morris_sparse_screening_truth",
    "reference_sobol_truth",
    "run_morris_effect_coverage_benchmark",
    "run_sobol_iid_coverage_benchmark",
    "run_sobol_linear_coverage_benchmark",
    "sobol_discontinuous_threshold_function",
    "sobol_g_function",
    "sobol_g_function_truth",
    "sobol_heavy_tailed_additive_function",
    "sobol_heavy_tailed_additive_truth",
    "sobol_linear_function",
    "sobol_linear_truth",
    "sobol_sparse_interaction_function",
    "sobol_sparse_interaction_truth",
    "summarize_coverage_observations",
]
