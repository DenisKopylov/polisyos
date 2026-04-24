"""Moment-constrained distributionally robust optimization methods."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np

from polisyos.foundry.methods.backends.protocol import SolverStatus
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

from .protocols import (
    AmbiguityCertificate,
    ConstraintCertificate,
    DiagnosticResult,
    MomentBound,
    MomentDROConstraint,
    MomentDROProblem,
    OptimizationResult,
    parse_moment_dro_problem,
)


def _serialize_result(result: OptimizationResult) -> dict[str, Any]:
    payload = result.to_payload()
    payload["contract_id"] = OptimizationResult.contract_id
    return payload


def _pick_solver(cp: Any, requested: str, *fallbacks: str) -> Any:
    installed = {str(name).upper() for name in cp.installed_solvers()}
    for candidate in (requested, *fallbacks):
        token = str(candidate).upper()
        if token in installed and hasattr(cp, token):
            return getattr(cp, token)
    return None


def _solver_status(status: str) -> SolverStatus:
    normalized = str(status).lower()
    if "optimal" in normalized:
        return SolverStatus.OPTIMAL
    if "infeasible" in normalized:
        return SolverStatus.INFEASIBLE
    if "unbounded" in normalized:
        return SolverStatus.UNBOUNDED
    if "limit" in normalized or "timeout" in normalized:
        return SolverStatus.TIMEOUT
    if "error" in normalized:
        return SolverStatus.ERROR
    return SolverStatus.UNKNOWN


def _default_bounds(n_vars: int) -> tuple[np.ndarray, np.ndarray]:
    return np.zeros(n_vars, dtype=float), np.full(n_vars, np.inf, dtype=float)


def _cantelli_multiplier(epsilon: float) -> float:
    safe_epsilon = min(max(float(epsilon), 1e-6), 1.0 - 1e-6)
    return math.sqrt((1.0 - safe_epsilon) / safe_epsilon)


def _psd_factor(covariance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    eigvals, eigvecs = np.linalg.eigh(covariance)
    clipped = np.maximum(eigvals, 0.0)
    factor = np.diag(np.sqrt(clipped)) @ eigvecs.T
    return factor, eigvals


def _sample_covariance(data: np.ndarray, center: np.ndarray | None = None) -> np.ndarray:
    if data.shape[0] <= 1:
        return np.zeros((data.shape[1], data.shape[1]), dtype=float)
    if center is None:
        center = np.mean(data, axis=0)
    residuals = data - center
    return (residuals.T @ residuals) / float(max(data.shape[0] - 1, 1))


def _median_of_means(data: np.ndarray) -> np.ndarray:
    if data.shape[0] < 4:
        return np.median(data, axis=0)
    block_count = max(2, min(int(math.sqrt(data.shape[0])), data.shape[0]))
    blocks = np.array_split(data, block_count)
    block_means = np.asarray([np.mean(block, axis=0) for block in blocks if block.size])
    return np.median(block_means, axis=0)


def _catoni_mean(data: np.ndarray) -> np.ndarray:
    if data.shape[0] <= 2:
        return np.mean(data, axis=0)
    center = np.median(data, axis=0)
    mad = np.median(np.abs(data - center), axis=0)
    scale = np.maximum(1.4826 * mad, np.std(data, axis=0, ddof=1) * 0.25)
    scale = np.where(scale <= 1e-12, 1.0, scale)
    theta = center.astype(float)
    step = scale / math.sqrt(float(data.shape[0]))
    for _ in range(40):
        score = np.tanh((data - theta) / scale)
        theta = theta + step * np.mean(score, axis=0)
    return theta


def _estimate_mean(data: np.ndarray, method: str) -> np.ndarray:
    normalized = method.lower()
    if normalized in {"median_of_means", "mom", "multivariate_mom"}:
        return _median_of_means(data)
    if "catoni" in normalized:
        return _catoni_mean(data)
    if "median" in normalized:
        return np.median(data, axis=0)
    return np.mean(data, axis=0)


def _winsorized(data: np.ndarray) -> np.ndarray:
    if data.shape[0] < 5:
        return data
    center = np.median(data, axis=0)
    mad = np.median(np.abs(data - center), axis=0)
    scale = np.where(1.4826 * mad <= 1e-12, np.std(data, axis=0, ddof=1), 1.4826 * mad)
    scale = np.where(scale <= 1e-12, 1.0, scale)
    lower = center - 4.0 * scale
    upper = center + 4.0 * scale
    return np.clip(data, lower, upper)


def _shrink_covariance(
    covariance: np.ndarray, *, sample_size: int, shrinkage: float | None = None
) -> np.ndarray:
    dim = covariance.shape[0]
    if dim == 0:
        return covariance
    if shrinkage is None:
        shrinkage = min(0.5, max(0.05, dim / max(float(sample_size), 1.0)))
    target_scale = float(np.trace(covariance) / max(dim, 1))
    target = np.eye(dim) * target_scale
    return (1.0 - shrinkage) * covariance + shrinkage * target


def _estimate_covariance(
    data: np.ndarray, center: np.ndarray, method: str
) -> tuple[np.ndarray, dict[str, Any]]:
    normalized = method.lower()
    used_data = _winsorized(data) if "robust" in normalized or "winsor" in normalized else data
    covariance = _sample_covariance(used_data, center=None if used_data is not data else center)
    metadata: dict[str, Any] = {"raw_estimator": method}
    if "shrink" in normalized or data.shape[0] <= 5 * max(data.shape[1], 1):
        shrinkage = min(0.5, max(0.05, data.shape[1] / max(float(data.shape[0]), 1.0)))
        covariance = _shrink_covariance(covariance, sample_size=data.shape[0], shrinkage=shrinkage)
        metadata["shrinkage_intensity"] = shrinkage
    if used_data is not data:
        metadata["winsorized"] = True
    return covariance, metadata


def _central_moment(data: np.ndarray, center: np.ndarray, order: int) -> np.ndarray:
    residuals = data - center
    return np.mean(residuals**order, axis=0)


def _chi_square_sf(value: float, *, df: int) -> float:
    value = max(float(value), 0.0)
    if df == 1:
        return float(math.erfc(math.sqrt(value / 2.0)))
    if df == 2:
        return float(math.exp(-value / 2.0))
    return float(math.exp(-value / 2.0))


def _log_bernoulli_likelihood(successes: int, trials: int, probability: float) -> float:
    if trials <= 0:
        return 0.0
    probability = min(max(float(probability), 1e-12), 1.0 - 1e-12)
    return float(
        successes * math.log(probability) + (trials - successes) * math.log(1.0 - probability)
    )


def _kupiec_diagnostic(name: str, hits: tuple[int, ...], epsilon: float) -> DiagnosticResult:
    n = len(hits)
    if n == 0:
        return DiagnosticResult(
            test_name=f"kupiec_{name}",
            status="warn",
            message="No backtest hits were supplied for unconditional coverage.",
        )
    exceedances = int(sum(hits))
    phat = exceedances / float(n)
    restricted = _log_bernoulli_likelihood(exceedances, n, epsilon)
    unrestricted = _log_bernoulli_likelihood(exceedances, n, phat)
    statistic = max(0.0, -2.0 * (restricted - unrestricted))
    p_value = _chi_square_sf(statistic, df=1)
    status = "fail" if p_value < 0.05 and phat > epsilon else ("warn" if p_value < 0.05 else "pass")
    return DiagnosticResult(
        test_name=f"kupiec_{name}",
        statistic=statistic,
        p_value=p_value,
        status=status,  # type: ignore[arg-type]
        message=(
            f"Observed violation frequency {phat:.3f} "
            f"against certified epsilon {float(epsilon):.3f}."
        ),
        metadata={"exceedances": exceedances, "sample_size": n, "epsilon": float(epsilon)},
    )


def _christoffersen_diagnostic(name: str, hits: tuple[int, ...]) -> DiagnosticResult:
    if len(hits) < 3:
        return DiagnosticResult(
            test_name=f"christoffersen_{name}",
            status="warn",
            message="Not enough backtest hits were supplied for independence diagnostics.",
            metadata={"sample_size": len(hits)},
        )
    n00 = n01 = n10 = n11 = 0
    for previous, current in zip(hits[:-1], hits[1:]):
        if previous == 0 and current == 0:
            n00 += 1
        elif previous == 0 and current == 1:
            n01 += 1
        elif previous == 1 and current == 0:
            n10 += 1
        else:
            n11 += 1
    total = n00 + n01 + n10 + n11
    pi = (n01 + n11) / float(max(total, 1))
    pi0 = n01 / float(max(n00 + n01, 1))
    pi1 = n11 / float(max(n10 + n11, 1))
    restricted = _log_bernoulli_likelihood(n01 + n11, total, pi)
    unrestricted = _log_bernoulli_likelihood(n01, n00 + n01, pi0) + _log_bernoulli_likelihood(
        n11, n10 + n11, pi1
    )
    statistic = max(0.0, -2.0 * (restricted - unrestricted))
    p_value = _chi_square_sf(statistic, df=1)
    status = "warn" if p_value < 0.05 else "pass"
    return DiagnosticResult(
        test_name=f"christoffersen_{name}",
        statistic=statistic,
        p_value=p_value,
        status=status,  # type: ignore[arg-type]
        message="Backtest hit independence check completed.",
        metadata={"n00": n00, "n01": n01, "n10": n10, "n11": n11},
    )


def _shape_tail_diagnostics(
    data: np.ndarray,
    *,
    mean: np.ndarray,
    covariance: np.ndarray,
    tail_fraction: float,
    higher_moment_orders: tuple[int, ...],
) -> tuple[DiagnosticResult, ...]:
    diagnostics: list[DiagnosticResult] = []
    scale = np.sqrt(np.maximum(np.diag(covariance), 1e-12))
    standardized = ((data - mean) / scale).reshape(-1)
    if standardized.size >= 8:
        centered = standardized - float(np.mean(standardized))
        std = float(np.std(centered, ddof=1))
        if std > 1e-12:
            z = centered / std
            skewness = float(np.mean(z**3))
            kurtosis = float(np.mean(z**4))
            statistic = (z.size / 6.0) * (skewness**2 + ((kurtosis - 3.0) ** 2) / 4.0)
            p_value = _chi_square_sf(statistic, df=2)
            diagnostics.append(
                DiagnosticResult(
                    test_name="jarque_bera",
                    statistic=statistic,
                    p_value=p_value,
                    status=("warn" if p_value < 0.05 else "pass"),
                    message="Jarque-Bera shape diagnostic on standardized fiscal shock residuals.",
                    metadata={"skewness": skewness, "kurtosis": kurtosis},
                )
            )
            sorted_z = np.sort(z)
            n = sorted_z.size
            cdf = np.array(
                [0.5 * (1.0 + math.erf(value / math.sqrt(2.0))) for value in sorted_z],
                dtype=float,
            )
            cdf = np.clip(cdf, 1e-12, 1.0 - 1e-12)
            indices = np.arange(1, n + 1)
            ad_statistic = float(
                -n - np.mean((2 * indices - 1) * (np.log(cdf) + np.log(1.0 - cdf[::-1])))
            )
            diagnostics.append(
                DiagnosticResult(
                    test_name="anderson_darling",
                    statistic=ad_statistic,
                    status=("warn" if ad_statistic > 2.5 else "pass"),
                    message="Anderson-Darling normal-tail diagnostic on standardized residuals.",
                    metadata={"critical_value_approx_5pct": 2.5},
                )
            )

    norms = np.linalg.norm((data - mean) / scale, axis=1)
    positive_norms = np.sort(norms[norms > 1e-12])[::-1]
    if positive_norms.size >= 5:
        k = max(
            2, min(positive_norms.size - 1, int(math.ceil(positive_norms.size * tail_fraction)))
        )
        threshold = positive_norms[k]
        logs = np.log(positive_norms[:k] / max(threshold, 1e-12))
        hill_alpha = float(1.0 / max(np.mean(logs), 1e-12))
        if hill_alpha <= 2.0:
            status = "fail"
            message = "Hill tail index suggests second moments may be unstable."
        elif 4 in higher_moment_orders and hill_alpha <= 4.0:
            status = "warn"
            message = "Hill tail index suggests fourth moments may be unstable."
        elif hill_alpha <= 4.0:
            status = "warn"
            message = (
                "Hill tail index indicates heavy tails; avoid certifying higher moments by default."
            )
        else:
            status = "pass"
            message = "Hill tail index is compatible with second-moment DRO diagnostics."
        diagnostics.append(
            DiagnosticResult(
                test_name="hill_tail_index",
                statistic=hill_alpha,
                status=status,  # type: ignore[arg-type]
                message=message,
                metadata={"tail_fraction": float(tail_fraction), "tail_observations": k},
            )
        )
    return tuple(diagnostics)


@dataclass(frozen=True, slots=True)
class _MomentInputs:
    mean: np.ndarray
    covariance: np.ndarray
    factor: np.ndarray
    eigenvalues: np.ndarray
    moment_bounds: tuple[MomentBound, ...]
    diagnostics: tuple[DiagnosticResult, ...]
    sample_size: int | None
    effective_sample_size: float | None
    source: str
    regime_model: str | None
    metadata: Mapping[str, Any]


def _resolve_regime_weights(
    *,
    regime_ids: tuple[str, ...],
    regime_counts: Mapping[str, int],
    probabilities: Mapping[str, float],
    total_count: int,
) -> dict[str, float]:
    if probabilities:
        raw = {regime: float(probabilities.get(regime, 0.0)) for regime in regime_ids}
        mass = sum(raw.values())
        if mass > 0.0:
            return {regime: weight / mass for regime, weight in raw.items()}
    return {
        regime: float(regime_counts[regime]) / float(max(total_count, 1)) for regime in regime_ids
    }


def _moment_bounds_for_estimate(
    *,
    mean: np.ndarray,
    covariance: np.ndarray,
    problem: MomentDROProblem,
    sample_size: int,
    effective_sample_size: float | None,
    regime: str | None,
    covariance_metadata: Mapping[str, Any],
    source: str,
) -> tuple[MomentBound, MomentBound]:
    return (
        MomentBound(
            name="shock_mean",
            order=1,
            estimator=problem.moment_estimator,
            point_estimate=mean.tolist(),
            confidence=problem.confidence_level,
            regime=regime,
            sample_size=sample_size,
            effective_sample_size=effective_sample_size,
            metadata={"gamma_mean": problem.gamma_mean, "source": source},
        ),
        MomentBound(
            name="shock_covariance",
            order=2,
            estimator=problem.covariance_estimator,
            point_estimate=covariance.tolist(),
            confidence=problem.confidence_level,
            regime=regime,
            sample_size=sample_size,
            effective_sample_size=effective_sample_size,
            metadata={
                "gamma_covariance": problem.gamma_covariance,
                "source": source,
                **dict(covariance_metadata),
            },
        ),
    )


def _resolve_moment_inputs(problem: MomentDROProblem) -> _MomentInputs:
    if (
        problem.historical_shocks
        and str(problem.metadata.get("moment_source", "historical_shocks")) != "declared"
    ):
        data = np.asarray(problem.historical_shocks, dtype=float)
        sample_size = int(problem.sample_size or data.shape[0])
        effective_sample_size = float(problem.effective_sample_size or data.shape[0])
        bounds: list[MomentBound] = []
        diagnostics: list[DiagnosticResult] = []
        regime_model = problem.regime_model
        if problem.regime_ids:
            unique_regimes = tuple(dict.fromkeys(problem.regime_ids))
            grouped = {
                regime: data[[idx for idx, item in enumerate(problem.regime_ids) if item == regime]]
                for regime in unique_regimes
            }
            weights = _resolve_regime_weights(
                regime_ids=unique_regimes,
                regime_counts={regime: grouped[regime].shape[0] for regime in unique_regimes},
                probabilities=problem.regime_probabilities,
                total_count=data.shape[0],
            )
            regime_estimates: dict[str, tuple[np.ndarray, np.ndarray, dict[str, Any]]] = {}
            for regime, regime_data in grouped.items():
                regime_mean = _estimate_mean(regime_data, problem.moment_estimator)
                regime_covariance, cov_metadata = _estimate_covariance(
                    regime_data,
                    regime_mean,
                    problem.covariance_estimator,
                )
                regime_estimates[regime] = (regime_mean, regime_covariance, cov_metadata)
                bounds.extend(
                    _moment_bounds_for_estimate(
                        mean=regime_mean,
                        covariance=regime_covariance,
                        problem=problem,
                        sample_size=regime_data.shape[0],
                        effective_sample_size=float(regime_data.shape[0]),
                        regime=regime,
                        covariance_metadata=cov_metadata,
                        source="historical_shocks_regime",
                    )
                )
            mean = sum(weights[regime] * regime_estimates[regime][0] for regime in unique_regimes)
            covariance = np.zeros((data.shape[1], data.shape[1]), dtype=float)
            for regime in unique_regimes:
                regime_mean, regime_covariance, _ = regime_estimates[regime]
                delta = regime_mean - mean
                covariance += weights[regime] * (regime_covariance + np.outer(delta, delta))
            regime_model = regime_model or "declared_regime_ids"
            covariance_metadata = {
                "regime_weights": weights,
                "regime_count": len(unique_regimes),
            }
        else:
            mean = _estimate_mean(data, problem.moment_estimator)
            covariance, covariance_metadata = _estimate_covariance(
                data,
                mean,
                problem.covariance_estimator,
            )
        bounds[:0] = list(
            _moment_bounds_for_estimate(
                mean=mean,
                covariance=covariance,
                problem=problem,
                sample_size=sample_size,
                effective_sample_size=effective_sample_size,
                regime=None,
                covariance_metadata=covariance_metadata,
                source="historical_shocks",
            )
        )
        for order in problem.higher_moment_orders:
            moment = _central_moment(data, mean, order)
            bounds.append(
                MomentBound(
                    name=f"shock_central_moment_{order}",
                    order=order,
                    estimator="sample_central_moment",
                    point_estimate=moment.tolist(),
                    upper=float(np.max(np.abs(moment))),
                    confidence=problem.confidence_level,
                    sample_size=sample_size,
                    effective_sample_size=effective_sample_size,
                    metadata={"source": "historical_shocks", "certified_for_counterpart": False},
                )
            )
        diagnostics.extend(
            _shape_tail_diagnostics(
                data,
                mean=mean,
                covariance=covariance,
                tail_fraction=problem.tail_fraction,
                higher_moment_orders=problem.higher_moment_orders,
            )
        )
        factor, eigenvalues = _psd_factor(covariance)
        return _MomentInputs(
            mean=mean,
            covariance=covariance,
            factor=factor,
            eigenvalues=eigenvalues,
            moment_bounds=tuple(bounds),
            diagnostics=tuple(diagnostics),
            sample_size=sample_size,
            effective_sample_size=effective_sample_size,
            source="historical_shocks",
            regime_model=regime_model,
            metadata={"historical_shock_count": data.shape[0]},
        )

    covariance = np.asarray(problem.shock_covariance, dtype=float)
    mean = np.asarray(problem.shock_mean, dtype=float)
    factor, eigenvalues = _psd_factor(covariance)
    sample_size = problem.sample_size
    effective_sample_size = problem.effective_sample_size
    bounds = _moment_bounds_for_estimate(
        mean=mean,
        covariance=covariance,
        problem=problem,
        sample_size=int(sample_size or 0),
        effective_sample_size=effective_sample_size,
        regime=problem.regime_model,
        covariance_metadata={},
        source="declared_moments",
    )
    return _MomentInputs(
        mean=mean,
        covariance=covariance,
        factor=factor,
        eigenvalues=eigenvalues,
        moment_bounds=bounds,
        diagnostics=(),
        sample_size=sample_size,
        effective_sample_size=effective_sample_size,
        source="declared_moments",
        regime_model=problem.regime_model,
        metadata={},
    )


@dataclass(frozen=True, slots=True)
class _PreparedConstraint:
    constraint: MomentDROConstraint
    effective_epsilon: float
    formulation: str
    exactness: str
    theorem_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _SolveArtifacts:
    status: SolverStatus
    solution: np.ndarray
    objective_value: float | None
    solver_iterations: int
    solver_time_seconds: float
    constraints_satisfied: dict[str, bool]
    solver_name: str


def _prepare_constraints(
    problem: MomentDROProblem,
    *,
    capacity_joint_mode: str,
) -> tuple[_PreparedConstraint, ...]:
    capacity_constraints = [
        constraint
        for constraint in problem.constraints
        if constraint.constraint_class == "capacity"
    ]
    capacity_count = len(capacity_constraints)
    prepared: list[_PreparedConstraint] = []
    for constraint in problem.constraints:
        if constraint.constraint_class == "capacity" and capacity_count > 1:
            if capacity_joint_mode == "bonferroni":
                effective_epsilon = min(max(constraint.epsilon / capacity_count, 1e-6), 1.0 - 1e-6)
                prepared.append(
                    _PreparedConstraint(
                        constraint=constraint,
                        effective_epsilon=effective_epsilon,
                        formulation="joint_chance_bonferroni",
                        exactness="approximation",
                        theorem_refs=(
                            "cantelli_one_sided_moment_bound",
                            "delage_ye_mean_cov_radius_bound",
                            "bonferroni_joint_capacity_relaxation",
                        ),
                    )
                )
            else:
                prepared.append(
                    _PreparedConstraint(
                        constraint=constraint,
                        effective_epsilon=constraint.epsilon,
                        formulation="individual_chance_scalar_moment",
                        exactness="approximation",
                        theorem_refs=(
                            "cantelli_one_sided_moment_bound",
                            "delage_ye_mean_cov_radius_bound",
                        ),
                    )
                )
            continue
        prepared.append(
            _PreparedConstraint(
                constraint=constraint,
                effective_epsilon=constraint.epsilon,
                formulation="dr_chance_scalar_moment",
                exactness="conservative_exact_for_scalarized_moments",
                theorem_refs=(
                    "cantelli_one_sided_moment_bound",
                    "delage_ye_mean_cov_radius_bound",
                ),
            )
        )
    return tuple(prepared)


def _build_constraint_expression(
    cp: Any,
    *,
    x: Any,
    prepared: _PreparedConstraint,
    shock_mean: np.ndarray,
    shock_factor: np.ndarray,
    gamma_mean: float,
    gamma_covariance: float,
) -> Any:
    nominal = np.asarray(prepared.constraint.nominal_coefficients, dtype=float)
    shock_matrix = np.asarray(prepared.constraint.shock_matrix, dtype=float)
    exposure = shock_matrix @ x
    sigma_term = cp.norm(shock_factor @ exposure, 2)
    multiplier = math.sqrt(max(gamma_mean, 0.0)) + (
        math.sqrt(max(gamma_covariance, 0.0)) * _cantelli_multiplier(prepared.effective_epsilon)
    )
    lhs = (
        float(prepared.constraint.intercept)
        + nominal @ x
        + shock_mean @ exposure
        + multiplier * sigma_term
    )
    return lhs <= float(prepared.constraint.threshold)


def _evaluate_constraint(
    *,
    solution: np.ndarray,
    prepared: _PreparedConstraint,
    shock_mean: np.ndarray,
    shock_factor: np.ndarray,
    gamma_mean: float,
    gamma_covariance: float,
) -> dict[str, float]:
    nominal = np.asarray(prepared.constraint.nominal_coefficients, dtype=float)
    shock_matrix = np.asarray(prepared.constraint.shock_matrix, dtype=float)
    exposure = shock_matrix @ solution
    sigma_base = float(np.linalg.norm(shock_factor @ exposure))
    mean_upper = (
        float(prepared.constraint.intercept)
        + float(nominal @ solution)
        + float(shock_mean @ exposure)
        + math.sqrt(max(gamma_mean, 0.0)) * sigma_base
    )
    std_upper = math.sqrt(max(gamma_covariance, 0.0)) * sigma_base
    worst_case_bound = mean_upper + (_cantelli_multiplier(prepared.effective_epsilon) * std_upper)
    slack = float(prepared.constraint.threshold) - worst_case_bound

    if std_upper <= 1e-12:
        violation_probability_bound = (
            1.0 if mean_upper > float(prepared.constraint.threshold) else 0.0
        )
    else:
        gap = max(float(prepared.constraint.threshold) - mean_upper, 0.0)
        if gap <= 0.0:
            violation_probability_bound = 1.0
        else:
            variance = std_upper**2
            violation_probability_bound = variance / (variance + gap**2)

    return {
        "mean_upper": mean_upper,
        "std_upper": std_upper,
        "worst_case_bound": float(worst_case_bound),
        "slack": float(slack),
        "violation_probability_bound": float(min(max(violation_probability_bound, 0.0), 1.0)),
    }


def _solve_once(
    problem: MomentDROProblem,
    *,
    moment_inputs: _MomentInputs,
    prepared_constraints: tuple[_PreparedConstraint, ...],
    gamma_mean: float,
    gamma_covariance: float,
    solver_name: str,
) -> _SolveArtifacts:
    import cvxpy as cp

    objective_vector = np.asarray(problem.objective_vector, dtype=float)
    shock_mean = moment_inputs.mean
    shock_factor = moment_inputs.factor

    x = cp.Variable(objective_vector.shape[0])
    if problem.objective == "maximize":
        objective = cp.Maximize(objective_vector @ x)
    else:
        objective = cp.Minimize(objective_vector @ x)

    if problem.bounds:
        bounds = np.asarray(problem.bounds, dtype=float)
        lb = bounds[:, 0]
        ub = bounds[:, 1]
    else:
        lb, ub = _default_bounds(objective_vector.shape[0])

    constraints = [x >= lb]
    finite_ub = np.isfinite(ub)
    if finite_ub.any():
        constraints.append(x[finite_ub] <= ub[finite_ub])

    deterministic_constraint_matrix = np.asarray(
        problem.deterministic_constraint_matrix, dtype=float
    )
    deterministic_constraint_rhs = np.asarray(problem.deterministic_constraint_rhs, dtype=float)
    if deterministic_constraint_matrix.size:
        constraints.append(deterministic_constraint_matrix @ x <= deterministic_constraint_rhs)

    for prepared in prepared_constraints:
        constraints.append(
            _build_constraint_expression(
                cp,
                x=x,
                prepared=prepared,
                shock_mean=shock_mean,
                shock_factor=shock_factor,
                gamma_mean=gamma_mean,
                gamma_covariance=gamma_covariance,
            )
        )

    program = cp.Problem(objective, constraints)
    started = time.perf_counter()
    solver = _pick_solver(cp, solver_name, "CLARABEL", "ECOS", "SCS")
    program.solve(solver=solver, verbose=False)
    elapsed = time.perf_counter() - started

    status = _solver_status(program.status)
    solution = (
        np.zeros(objective_vector.shape[0], dtype=float)
        if x.value is None
        else np.asarray(x.value, dtype=float)
    )

    constraints_satisfied: dict[str, bool] = {
        f"lower_bound_{idx}": bool(solution[idx] >= lb[idx] - 1e-6)
        for idx in range(solution.shape[0])
    }
    for idx in np.flatnonzero(finite_ub):
        constraints_satisfied[f"upper_bound_{int(idx)}"] = bool(solution[idx] <= ub[idx] + 1e-6)
    if deterministic_constraint_matrix.size:
        deterministic_lhs = deterministic_constraint_matrix @ solution
        for idx in range(deterministic_constraint_matrix.shape[0]):
            constraints_satisfied[f"deterministic_{idx}"] = bool(
                deterministic_lhs[idx] <= deterministic_constraint_rhs[idx] + 1e-6
            )
    for prepared in prepared_constraints:
        evaluation = _evaluate_constraint(
            solution=solution,
            prepared=prepared,
            shock_mean=shock_mean,
            shock_factor=shock_factor,
            gamma_mean=gamma_mean,
            gamma_covariance=gamma_covariance,
        )
        constraints_satisfied[prepared.constraint.name] = bool(evaluation["slack"] >= -1e-6)

    return _SolveArtifacts(
        status=status,
        solution=solution,
        objective_value=(None if program.value is None else float(program.value)),
        solver_iterations=int(getattr(program.solver_stats, "num_iters", 0) or 0),
        solver_time_seconds=float(getattr(program.solver_stats, "solve_time", elapsed) or elapsed),
        constraints_satisfied=constraints_satisfied,
        solver_name=str(solver_name).upper(),
    )


def _build_diagnostics(
    *,
    problem: MomentDROProblem,
    moment_inputs: _MomentInputs,
    solver_status: SolverStatus,
    capacity_joint_mode: str,
    capacity_count: int,
) -> tuple[DiagnosticResult, ...]:
    diagnostics: list[DiagnosticResult] = list(moment_inputs.diagnostics)
    covariance_eigenvalues = moment_inputs.eigenvalues
    min_eigenvalue = float(np.min(covariance_eigenvalues))
    if min_eigenvalue < -1e-6:
        diagnostics.append(
            DiagnosticResult(
                test_name="covariance_psd",
                statistic=min_eigenvalue,
                status="fail",
                message="Shock covariance is not positive semidefinite beyond numerical tolerance.",
            )
        )
    elif min_eigenvalue < 0.0:
        diagnostics.append(
            DiagnosticResult(
                test_name="covariance_psd",
                statistic=min_eigenvalue,
                status="warn",
                message="Shock covariance had a small negative eigenvalue and was clipped to the PSD cone.",
            )
        )
    else:
        diagnostics.append(
            DiagnosticResult(
                test_name="covariance_psd",
                statistic=min_eigenvalue,
                status="pass",
                message="Shock covariance is PSD.",
            )
        )

    positive_eigenvalues = covariance_eigenvalues[covariance_eigenvalues > 1e-9]
    if positive_eigenvalues.size >= 2:
        condition_number = float(np.max(positive_eigenvalues) / np.min(positive_eigenvalues))
        if condition_number > 1e6:
            diagnostics.append(
                DiagnosticResult(
                    test_name="covariance_condition_number",
                    statistic=condition_number,
                    status="warn",
                    message="Shock covariance is ill-conditioned; shrinkage or factor regularization may be safer.",
                    metadata={"threshold": 1e6},
                )
            )
        else:
            diagnostics.append(
                DiagnosticResult(
                    test_name="covariance_condition_number",
                    statistic=condition_number,
                    status="pass",
                    message="Shock covariance condition number is within heuristic tolerance.",
                    metadata={"threshold": 1e6},
                )
            )

    if moment_inputs.sample_size is not None:
        heuristic_floor = max(20, 5 * len(moment_inputs.mean))
        if int(moment_inputs.sample_size) < heuristic_floor:
            diagnostics.append(
                DiagnosticResult(
                    test_name="sample_size_heuristic",
                    statistic=float(moment_inputs.sample_size),
                    status="warn",
                    message="Sample size is small relative to shock dimension; ambiguity bounds may be conservative or unstable.",
                    metadata={"heuristic_floor": heuristic_floor},
                )
            )
        else:
            diagnostics.append(
                DiagnosticResult(
                    test_name="sample_size_heuristic",
                    statistic=float(moment_inputs.sample_size),
                    status="pass",
                    message="Sample size clears the heuristic minimum for first-pass moment calibration.",
                    metadata={"heuristic_floor": heuristic_floor},
                )
            )

    constraint_epsilons = {
        constraint.name: constraint.epsilon for constraint in problem.constraints
    }
    for name, hits in problem.backtest_hits.items():
        diagnostics.append(_kupiec_diagnostic(name, hits, constraint_epsilons.get(name, 0.05)))
        diagnostics.append(_christoffersen_diagnostic(name, hits))

    if capacity_count > 1 and capacity_joint_mode == "bonferroni":
        diagnostics.append(
            DiagnosticResult(
                test_name="capacity_joint_approximation",
                status="warn",
                message="Capacity joint chance control uses a Bonferroni approximation in this Phase-3 implementation slice.",
                metadata={"capacity_count": capacity_count},
            )
        )

    diagnostics.append(
        DiagnosticResult(
            test_name="solver_status",
            status=(
                "pass" if solver_status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE} else "fail"
            ),
            message=f"Solver terminated with status '{solver_status.value}'.",
        )
    )
    return tuple(diagnostics)


def _overall_status(diagnostics: tuple[DiagnosticResult, ...]) -> str:
    statuses = {item.status for item in diagnostics}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def _price_of_ambiguity(
    *,
    problem: MomentDROProblem,
    robust_objective_value: float | None,
    nominal_objective_value: float | None,
) -> float | None:
    if robust_objective_value is None or nominal_objective_value is None:
        return None
    if problem.objective == "maximize":
        return float(nominal_objective_value - robust_objective_value)
    return float(robust_objective_value - nominal_objective_value)


@foundry_method(
    namespace="optimization.dro",
    version="1.0.0",
    tags={"optimization", "dro", "moment", "distributionally-robust", "chance-constrained"},
)
class MomentConstrainedDROEstimator:
    """Solve moment-constrained DRO problems with typed ambiguity certificates."""

    runtime_stack: ClassVar[tuple[str, ...]] = ("cvxpy", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="moment_constrained",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="moment_dro_problem",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("problem", "json"),
                    contract_id=MomentDROProblem.contract_id,
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("result", "json"),
                    contract_id=OptimizationResult.contract_id,
                ),
                SlotSpec("solver_info", SlotType.SCALAR, Unit("solver", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="solver", default="CLARABEL"),
            ParameterSpec(name="capacity_joint_mode", default="bonferroni"),
            ParameterSpec(name="compute_nominal_comparison", default=True),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Moment-constrained distributionally robust optimization with typed ambiguity certificates.",
        tags=frozenset({"optimization", "dro", "moment", "distributionally-robust"}),
        when_to_use="Budget/equity risk under heavy-tailed or regime-uncertain fiscal shocks; first-pass policy DRO with explicit ambiguity reporting",
        citations=(
            "Delage, E. & Ye, Y. (2010). Distributionally robust optimization under moment uncertainty.",
            "Wiesemann, W., Kuhn, D. & Sim, M. (2014). Distributionally robust convex optimization.",
        ),
        when_not_to_use="No moment information is available; second moments are not defensible; nonlinear recourse requires a richer model family",
        output_interpretation="Optimal solution plus a typed ambiguity certificate describing moment bounds, per-constraint worst-case guarantees, and validation diagnostics.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> Any:
        payload = dict(fallback_state) if isinstance(fallback_state, Mapping) else {}
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        problem = parse_moment_dro_problem(state)
        solver_name = str(params.get("solver", "CLARABEL")).upper()
        capacity_joint_mode = str(params.get("capacity_joint_mode", "bonferroni")).lower()
        compute_nominal_comparison = bool(params.get("compute_nominal_comparison", True))

        try:
            prepared_constraints = _prepare_constraints(
                problem,
                capacity_joint_mode=capacity_joint_mode,
            )
            moment_inputs = _resolve_moment_inputs(problem)
            robust = _solve_once(
                problem,
                moment_inputs=moment_inputs,
                prepared_constraints=prepared_constraints,
                gamma_mean=problem.gamma_mean,
                gamma_covariance=problem.gamma_covariance,
                solver_name=solver_name,
            )
        except Exception as exc:  # pragma: no cover - defensive error path
            certificate = AmbiguityCertificate(
                ambiguity_set_type=problem.ambiguity_set_type,
                confidence_level=problem.confidence_level,
                overall_status="fail",
                support_description=problem.support_description,
                regime_model=problem.regime_model,
                diagnostics=(
                    DiagnosticResult(
                        test_name="solver_error",
                        status="fail",
                        message=f"Moment DRO solve failed: {exc}",
                    ),
                ),
                solver_backend=solver_name,
                metadata={"problem_id": problem.problem_id},
            )
            result = OptimizationResult(
                status=SolverStatus.ERROR,
                objective_value=None,
                variables={},
                constraints_satisfied={},
                solver_iterations=0,
                solver_gap=None,
                solver_time_seconds=0.0,
                ambiguity_certificate=certificate,
                metadata={"solver": solver_name, "error": str(exc)},
            )
            return _serialize_result(result), {
                "status": result.status.value,
                "objective_value": None,
                "iterations": 0,
                "solver": solver_name,
                "error": str(exc),
            }

        nominal_objective_value: float | None = None
        if compute_nominal_comparison and robust.status in {
            SolverStatus.OPTIMAL,
            SolverStatus.FEASIBLE,
        }:
            try:
                nominal = _solve_once(
                    problem,
                    moment_inputs=moment_inputs,
                    prepared_constraints=prepared_constraints,
                    gamma_mean=0.0,
                    gamma_covariance=0.0,
                    solver_name=solver_name,
                )
                nominal_objective_value = nominal.objective_value
            except Exception:
                nominal_objective_value = None

        shock_factor = moment_inputs.factor
        shock_mean = moment_inputs.mean
        capacity_count = sum(
            1 for constraint in problem.constraints if constraint.constraint_class == "capacity"
        )
        diagnostics = _build_diagnostics(
            problem=problem,
            moment_inputs=moment_inputs,
            solver_status=robust.status,
            capacity_joint_mode=capacity_joint_mode,
            capacity_count=capacity_count,
        )

        moment_bounds = moment_inputs.moment_bounds

        per_constraint: list[ConstraintCertificate] = []
        if robust.status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
            for prepared in prepared_constraints:
                evaluation = _evaluate_constraint(
                    solution=robust.solution,
                    prepared=prepared,
                    shock_mean=shock_mean,
                    shock_factor=shock_factor,
                    gamma_mean=problem.gamma_mean,
                    gamma_covariance=problem.gamma_covariance,
                )
                per_constraint.append(
                    ConstraintCertificate(
                        name=prepared.constraint.name,
                        constraint_class=prepared.constraint.constraint_class,
                        formulation=prepared.formulation,
                        exactness=prepared.exactness,
                        worst_case_bound=evaluation["worst_case_bound"],
                        threshold=float(prepared.constraint.threshold),
                        slack=evaluation["slack"],
                        solver_family="SOCP",
                        epsilon=prepared.effective_epsilon,
                        violation_probability_bound=evaluation["violation_probability_bound"],
                        theorem_refs=prepared.theorem_refs,
                        metadata={
                            "mean_upper": evaluation["mean_upper"],
                            "std_upper": evaluation["std_upper"],
                            "original_epsilon": float(prepared.constraint.epsilon),
                        },
                    )
                )

        certificate = AmbiguityCertificate(
            ambiguity_set_type=problem.ambiguity_set_type,
            confidence_level=problem.confidence_level,
            overall_status=_overall_status(diagnostics),  # type: ignore[arg-type]
            support_description=problem.support_description,
            regime_model=moment_inputs.regime_model,
            moment_bounds=moment_bounds,
            per_constraint=tuple(per_constraint),
            diagnostics=diagnostics,
            price_of_ambiguity=_price_of_ambiguity(
                problem=problem,
                robust_objective_value=robust.objective_value,
                nominal_objective_value=nominal_objective_value,
            ),
            price_of_robustness=_price_of_ambiguity(
                problem=problem,
                robust_objective_value=robust.objective_value,
                nominal_objective_value=nominal_objective_value,
            ),
            solver_runtime_ms=robust.solver_time_seconds * 1000.0,
            solver_backend=solver_name,
            reproducibility={
                "capacity_joint_mode": capacity_joint_mode,
                "compute_nominal_comparison": compute_nominal_comparison,
                "moment_source": moment_inputs.source,
            },
            metadata={
                "problem_id": problem.problem_id,
                "capacity_count": capacity_count,
                "moment_source": moment_inputs.source,
                "sample_size": moment_inputs.sample_size,
                **dict(moment_inputs.metadata),
            },
        )

        result = OptimizationResult(
            status=robust.status,
            objective_value=robust.objective_value,
            variables={f"x_{idx}": float(value) for idx, value in enumerate(robust.solution)},
            constraints_satisfied=robust.constraints_satisfied,
            solver_iterations=robust.solver_iterations,
            solver_gap=None,
            solver_time_seconds=robust.solver_time_seconds,
            ambiguity_certificate=certificate,
            metadata={
                "solver": solver_name,
                "capacity_joint_mode": capacity_joint_mode,
                "ambiguity_set_type": problem.ambiguity_set_type,
                "moment_source": moment_inputs.source,
            },
        )
        return _serialize_result(result), {
            "status": robust.status.value,
            "gap": None,
            "iterations": robust.solver_iterations,
            "objective_value": robust.objective_value,
            "solver": solver_name,
            "price_of_ambiguity": certificate.price_of_ambiguity,
        }


__all__ = ["MomentConstrainedDROEstimator"]
