"""Calibrate robust uncertainty sets against empirical coverage and conservatism."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from statistics import NormalDist
from typing import Any

import numpy as np

from polisyos.ir.analytics.uncertainty import (
    RobustSetAdequacyStatus,
    RobustSetCalibrationMethod,
    RobustSetCalibrationReport,
    RobustSetCalibrationStatus,
    RobustSetFamily,
    RobustSetFrontierPoint,
    RobustSetSpec,
)

_EPS = 1e-8
_DEFAULT_RHO_FACTORS = (0.7, 0.85, 1.0, 1.15, 1.3, 1.6, 2.0)


def _coerce_family(value: RobustSetFamily | str) -> RobustSetFamily:
    return value if isinstance(value, RobustSetFamily) else RobustSetFamily(value)


def _coerce_calibration_method(
    value: RobustSetCalibrationMethod | str,
) -> RobustSetCalibrationMethod:
    return (
        value
        if isinstance(value, RobustSetCalibrationMethod)
        else RobustSetCalibrationMethod(value)
    )


def _as_sample_matrix(theta_samples: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    samples = np.asarray(theta_samples, dtype=float)
    if samples.ndim == 1:
        samples = samples.reshape(-1, 1)
    if samples.ndim != 2 or samples.shape[0] == 0 or samples.shape[1] == 0:
        raise ValueError("theta_samples must be a non-empty 2D matrix or 1D vector")
    if not np.all(np.isfinite(samples)):
        raise ValueError("theta_samples must be finite")
    return samples


def _split_samples(
    samples: np.ndarray,
    *,
    ratios: tuple[float, float, float],
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if len(ratios) != 3 or any(r <= 0.0 for r in ratios):
        raise ValueError("ratios must contain three positive values")
    total = float(sum(ratios))
    normalized = np.asarray([r / total for r in ratios], dtype=float)
    n_samples = samples.shape[0]
    if n_samples < 6:
        raise ValueError("theta_samples must contain at least six rows")

    counts = np.floor(normalized * n_samples).astype(int)
    counts = np.maximum(counts, 1)
    while counts.sum() > n_samples:
        counts[np.argmax(counts)] -= 1
    while counts.sum() < n_samples:
        counts[np.argmin(counts)] += 1

    rng = np.random.default_rng(seed)
    order = rng.permutation(n_samples)
    a, b = counts[0], counts[0] + counts[1]
    return samples[order[:a]], samples[order[a:b]], samples[order[b:]]


def _estimate_center(samples: np.ndarray) -> np.ndarray:
    return np.mean(samples, axis=0, dtype=float)


def _estimate_scale_diag(samples: np.ndarray) -> np.ndarray:
    ddof = 1 if samples.shape[0] > 1 else 0
    scale = np.std(samples, axis=0, ddof=ddof, dtype=float)
    scale = np.where(np.isfinite(scale), scale, 0.0)
    return np.maximum(scale, _EPS)


def _repair_covariance(covariance: np.ndarray) -> np.ndarray:
    symmetric = 0.5 * (covariance + covariance.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    clipped = np.clip(eigenvalues, a_min=_EPS, a_max=None)
    return (eigenvectors * clipped) @ eigenvectors.T


def _estimate_shrinkage_covariance(samples: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    dimension = samples.shape[1]
    if samples.shape[0] <= 1:
        eye = np.eye(dimension, dtype=float)
        return eye, {
            "shrinkage_applied": True,
            "shrinkage_intensity": 1.0,
            "sample_covariance_rank": 0,
        }

    covariance = np.cov(samples, rowvar=False, ddof=1)
    if dimension == 1:
        covariance = np.asarray([[float(covariance)]], dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    diagonal = np.diag(np.clip(np.diag(covariance), a_min=_EPS, a_max=None))
    rank = int(np.linalg.matrix_rank(covariance))
    needs_shrinkage = (
        samples.shape[0] <= dimension or rank < dimension or not np.all(np.isfinite(covariance))
    )
    shrinkage = 0.0
    if needs_shrinkage:
        ratio = dimension / max(samples.shape[0] - 1, 1)
        shrinkage = min(0.9, ratio / (1.0 + ratio))
        covariance = (1.0 - shrinkage) * covariance + shrinkage * diagonal
    covariance = _repair_covariance(covariance)
    return covariance, {
        "shrinkage_applied": needs_shrinkage,
        "shrinkage_intensity": shrinkage,
        "sample_covariance_rank": rank,
    }


def _box_scores(samples: np.ndarray, center: np.ndarray, scale_diag: np.ndarray) -> np.ndarray:
    normalized = np.abs((samples - center) / scale_diag)
    return np.max(normalized, axis=1)


def _ellipsoid_scores(
    samples: np.ndarray, center: np.ndarray, covariance: np.ndarray
) -> np.ndarray:
    inverse = np.linalg.pinv(covariance, hermitian=True)
    centered = samples - center
    squared = np.einsum("ni,ij,nj->n", centered, inverse, centered)
    return np.sqrt(np.maximum(squared, 0.0))


def _conformal_quantile(scores: np.ndarray, target_coverage: float) -> float:
    sorted_scores = np.sort(np.asarray(scores, dtype=float))
    if sorted_scores.size == 0:
        raise ValueError("scores must be non-empty")
    index = int(math.ceil(target_coverage * (sorted_scores.size + 1))) - 1
    index = min(max(index, 0), sorted_scores.size - 1)
    return float(sorted_scores[index])


def gaussian_parametric_radius(
    *,
    family: RobustSetFamily | str,
    dimension: int,
    coverage_target: float,
) -> float:
    """Return the Gaussian radius implied by a target coverage level.

    For box sets this uses the exact independent-standard-normal formula.
    For ellipsoids it uses scipy's chi-square quantile when available, with a
    Wilson-Hilferty approximation fallback to avoid a hard scipy dependency.
    """

    resolved_family = _coerce_family(family)
    if dimension <= 0:
        raise ValueError("dimension must be positive")
    if not 0.0 < float(coverage_target) < 1.0:
        raise ValueError("coverage_target must be in (0, 1)")

    if resolved_family is RobustSetFamily.BOX:
        marginal = (1.0 + float(coverage_target) ** (1.0 / dimension)) / 2.0
        return float(NormalDist().inv_cdf(marginal))
    if resolved_family is RobustSetFamily.ELLIPSOID:
        try:  # pragma: no cover - exercised only when scipy is installed
            from scipy.stats import chi2

            return float(math.sqrt(float(chi2.ppf(float(coverage_target), dimension))))
        except Exception:
            z = NormalDist().inv_cdf(float(coverage_target))
            term = 1.0 - 2.0 / (9.0 * dimension) + z * math.sqrt(2.0 / (9.0 * dimension))
            return float(math.sqrt(max(dimension * term**3, 0.0)))
    raise ValueError("gaussian_parametric_radius supports only box and ellipsoid families")


def _local_rho_grid(base_rho: float, scores: np.ndarray, factors: Sequence[float]) -> np.ndarray:
    positive_factors = sorted({float(factor) for factor in factors if float(factor) > 0.0})
    reference = max(float(base_rho), float(np.quantile(scores, 0.75)), 1.0)
    if base_rho <= _EPS:
        grid = np.asarray(
            [0.0, *(0.25 * reference * factor for factor in positive_factors)], dtype=float
        )
    else:
        grid = np.asarray([base_rho * factor for factor in positive_factors], dtype=float)
    return np.unique(np.clip(grid, a_min=0.0, a_max=None))


def _wilson_lcb(coverage: float, n_samples: int, *, level: float) -> float:
    if n_samples <= 0:
        return 0.0
    p_hat = min(max(float(coverage), 0.0), 1.0)
    z = NormalDist().inv_cdf(level)
    denom = 1.0 + z**2 / n_samples
    center = p_hat + z**2 / (2.0 * n_samples)
    radius = z * math.sqrt((p_hat * (1.0 - p_hat) + z**2 / (4.0 * n_samples)) / n_samples)
    return max(0.0, (center - radius) / denom)


def _bootstrap_mean_ucb(
    samples: np.ndarray,
    *,
    level: float,
    bootstrap_reps: int,
    seed: int,
) -> float:
    values = np.asarray(samples, dtype=float).reshape(-1)
    if values.size == 0:
        raise ValueError("bootstrap samples must be non-empty")
    if values.size == 1:
        return float(values[0])
    rng = np.random.default_rng(seed)
    draws = np.empty(bootstrap_reps, dtype=float)
    for idx in range(bootstrap_reps):
        picked = rng.integers(0, values.size, size=values.size)
        draws[idx] = float(np.mean(values[picked]))
    return float(np.quantile(draws, level))


def _empirical_cvar(losses: np.ndarray, *, alpha: float = 0.05) -> float:
    normalized = np.sort(np.asarray(losses, dtype=float))
    tail_count = max(1, int(math.ceil(alpha * normalized.size)))
    return float(np.mean(normalized[-tail_count:]))


def _estimate_frontier_knee(frontier: list[RobustSetFrontierPoint]) -> float | None:
    if len(frontier) < 3:
        return None

    coverages = np.asarray([point.coverage_emp for point in frontier], dtype=float)
    inflations = np.asarray([point.inflation_mean for point in frontier], dtype=float)
    cover_span = np.ptp(coverages)
    infl_span = np.ptp(inflations)
    if cover_span <= _EPS or infl_span <= _EPS:
        return None

    x = (coverages - np.min(coverages)) / cover_span
    y = 1.0 - (inflations - np.min(inflations)) / infl_span
    start = np.array([x[0], y[0]], dtype=float)
    end = np.array([x[-1], y[-1]], dtype=float)
    direction = end - start
    length = np.linalg.norm(direction)
    if length <= _EPS:
        return None

    distances: list[float] = []
    for x_i, y_i in zip(x, y, strict=False):
        point = np.array([x_i, y_i], dtype=float)
        offset = point - start
        cross = abs(direction[0] * offset[1] - direction[1] * offset[0])
        distances.append(float(cross / length))
    return frontier[int(np.argmax(distances))].rho


def _build_set_spec(
    *,
    family: RobustSetFamily,
    size_parameter: float,
    center: np.ndarray,
    scale_diag: np.ndarray | None,
    covariance: np.ndarray | None,
    coverage_target: float,
    calibration_method: RobustSetCalibrationMethod,
    metadata: dict[str, Any] | None = None,
) -> RobustSetSpec:
    payload: dict[str, Any] = {
        "family": family,
        "size_parameter": float(size_parameter),
        "center": tuple(float(value) for value in center),
        "coverage_target": float(coverage_target),
        "calibration_method": calibration_method,
        "metadata": dict(metadata or {}),
    }
    if scale_diag is not None:
        payload["scale_diag"] = tuple(float(value) for value in scale_diag)
    if covariance is not None:
        payload["covariance"] = tuple(
            tuple(float(value) for value in row) for row in np.asarray(covariance, dtype=float)
        )
    return RobustSetSpec.model_validate(payload)


def build_robust_set_spec_from_samples(
    theta_samples: Sequence[Sequence[float]] | np.ndarray,
    *,
    family: RobustSetFamily | str,
    size_parameter: float,
    coverage_target: float | None = None,
    calibration_method: RobustSetCalibrationMethod | str = RobustSetCalibrationMethod.CONFORMAL,
) -> RobustSetSpec:
    """Estimate geometry from samples and return a typed robust-set specification."""

    samples = _as_sample_matrix(theta_samples)
    resolved_family = _coerce_family(family)
    resolved_method = _coerce_calibration_method(calibration_method)
    center = _estimate_center(samples)
    scale_diag = _estimate_scale_diag(samples) if resolved_family is RobustSetFamily.BOX else None
    covariance = None
    metadata: dict[str, Any] = {"estimated_from_samples": int(samples.shape[0])}
    if resolved_family is RobustSetFamily.ELLIPSOID:
        covariance, covariance_meta = _estimate_shrinkage_covariance(samples)
        metadata.update(covariance_meta)
    return _build_set_spec(
        family=resolved_family,
        size_parameter=float(size_parameter),
        center=center,
        scale_diag=scale_diag,
        covariance=covariance,
        coverage_target=float(coverage_target) if coverage_target is not None else 0.0,
        calibration_method=resolved_method,
        metadata=metadata,
    )


def select_robust_set_size(
    theta_samples: Sequence[Sequence[float]] | np.ndarray,
    *,
    coverage_target: float,
    inflation_budget: float | None,
    family: RobustSetFamily | str,
    solve_nominal: Callable[[np.ndarray], Any],
    solve_robust: Callable[[RobustSetSpec], Any],
    loss_fn: Callable[[Any, np.ndarray], float],
    calibration_method: RobustSetCalibrationMethod | str = RobustSetCalibrationMethod.CONFORMAL,
    seed: int = 7,
    ratios: tuple[float, float, float] = (0.5, 0.25, 0.25),
    rho_factors: Sequence[float] = _DEFAULT_RHO_FACTORS,
    frontier_confidence_level: float = 0.95,
    bootstrap_reps: int = 400,
) -> RobustSetCalibrationReport:
    """Choose the smallest robust-set radius that satisfies coverage and inflation targets."""

    resolved_family = _coerce_family(family)
    resolved_method = _coerce_calibration_method(calibration_method)
    if not 0.0 < float(coverage_target) < 1.0:
        raise ValueError("coverage_target must be in (0, 1)")
    try:
        samples = _as_sample_matrix(theta_samples)
        train, calib, valid = _split_samples(samples, ratios=ratios, seed=seed)
    except ValueError as exc:
        return RobustSetCalibrationReport(
            family=resolved_family,
            selected_size=None,
            target_coverage=float(coverage_target),
            target_inflation=inflation_budget,
            empirical_frontier=(),
            status=RobustSetCalibrationStatus.INSUFFICIENT_DATA,
            adequacy_status=RobustSetAdequacyStatus.INSUFFICIENT_DATA,
            assumptions=("exchangeable_samples",),
            metadata={"reason": str(exc)},
        )

    center = _estimate_center(train)
    scale_diag = _estimate_scale_diag(train) if resolved_family is RobustSetFamily.BOX else None
    covariance = None
    covariance_meta: dict[str, Any] = {}
    if resolved_family is RobustSetFamily.ELLIPSOID:
        covariance, covariance_meta = _estimate_shrinkage_covariance(train)

    if resolved_family is RobustSetFamily.BOX:
        calib_scores = _box_scores(
            calib, center, scale_diag if scale_diag is not None else np.ones_like(center)
        )
    else:
        calib_scores = _ellipsoid_scores(
            calib, center, covariance if covariance is not None else np.eye(center.size)
        )

    if resolved_method is RobustSetCalibrationMethod.GAUSSIAN_PARAMETRIC:
        rho0 = gaussian_parametric_radius(
            family=resolved_family,
            dimension=center.size,
            coverage_target=float(coverage_target),
        )
        assumptions_seed = "gaussian_parametric_radius"
    else:
        rho0 = _conformal_quantile(calib_scores, float(coverage_target))
        assumptions_seed = "score_calibrated_radius"
    rho_grid = _local_rho_grid(rho0, calib_scores, rho_factors)
    nominal_solution = solve_nominal(center)
    frontier: list[RobustSetFrontierPoint] = []
    feasible_rhos: list[float] = []
    frontier_seed = int(seed)

    for index, rho in enumerate(rho_grid):
        spec = _build_set_spec(
            family=resolved_family,
            size_parameter=float(rho),
            center=center,
            scale_diag=scale_diag,
            covariance=covariance,
            coverage_target=float(coverage_target),
            calibration_method=resolved_method,
            metadata={"source": "set_size_selector", **covariance_meta},
        )
        robust_solution = solve_robust(spec)
        nominal_losses = np.asarray(
            [float(loss_fn(nominal_solution, theta)) for theta in valid],
            dtype=float,
        )
        robust_losses = np.asarray(
            [float(loss_fn(robust_solution, theta)) for theta in valid],
            dtype=float,
        )
        inflation_samples = robust_losses - nominal_losses
        if resolved_family is RobustSetFamily.BOX:
            coverage_mask = (
                _box_scores(
                    valid, center, scale_diag if scale_diag is not None else np.ones_like(center)
                )
                <= rho
            )
        else:
            coverage_mask = (
                _ellipsoid_scores(
                    valid, center, covariance if covariance is not None else np.eye(center.size)
                )
                <= rho
            )

        coverage_emp = float(np.mean(coverage_mask))
        coverage_lcb = _wilson_lcb(
            coverage_emp,
            len(valid),
            level=frontier_confidence_level,
        )
        inflation_mean = float(np.mean(inflation_samples))
        inflation_ucb = _bootstrap_mean_ucb(
            inflation_samples,
            level=frontier_confidence_level,
            bootstrap_reps=bootstrap_reps,
            seed=frontier_seed + index,
        )
        point = RobustSetFrontierPoint(
            rho=float(rho),
            coverage_emp=coverage_emp,
            coverage_lcb=coverage_lcb,
            inflation_mean=inflation_mean,
            inflation_ucb=inflation_ucb,
            worst_case_premium=float(np.max(robust_losses) - np.mean(nominal_losses)),
            cvar05=_empirical_cvar(robust_losses),
        )
        frontier.append(point)

        meets_coverage = coverage_lcb >= float(coverage_target)
        meets_inflation = inflation_budget is None or inflation_ucb <= float(inflation_budget)
        if meets_coverage and meets_inflation:
            feasible_rhos.append(float(rho))

    frontier.sort(key=lambda point: point.rho)
    frontier_knee_rho = _estimate_frontier_knee(frontier)
    metadata: dict[str, Any] = {
        "train_size": int(train.shape[0]),
        "calibration_size": int(calib.shape[0]),
        "validation_size": int(valid.shape[0]),
        "frontier_knee_rho": frontier_knee_rho,
        "center": [float(value) for value in center],
        "rho_seed": float(rho0),
        **covariance_meta,
    }
    if scale_diag is not None:
        metadata["scale_diag"] = [float(value) for value in scale_diag]
    if covariance is not None:
        metadata["covariance"] = [
            [float(value) for value in row] for row in np.asarray(covariance, dtype=float)
        ]

    if not feasible_rhos:
        coverage_possible = any(point.coverage_lcb >= float(coverage_target) for point in frontier)
        inflation_possible = inflation_budget is None or any(
            point.inflation_ucb <= float(inflation_budget) for point in frontier
        )
        if not coverage_possible:
            adequacy_status = RobustSetAdequacyStatus.UNDERCOVERAGE
            blockers = ("coverage_target_not_met",)
        elif not inflation_possible:
            adequacy_status = RobustSetAdequacyStatus.OVERCONSERVATIVE
            blockers = ("inflation_budget_not_met",)
        else:
            adequacy_status = RobustSetAdequacyStatus.INFEASIBLE_TARGET_PAIR
            blockers = ("coverage_inflation_targets_not_jointly_met",)
        metadata["blockers"] = list(blockers)
        return RobustSetCalibrationReport(
            family=resolved_family,
            selected_size=None,
            target_coverage=float(coverage_target),
            target_inflation=inflation_budget,
            empirical_frontier=tuple(frontier),
            status=RobustSetCalibrationStatus.INFEASIBLE_TARGET_PAIR,
            adequacy_status=adequacy_status,
            assumptions=("exchangeable_samples", assumptions_seed),
            metadata=metadata,
        )

    selected_size = min(feasible_rhos)
    selected_spec = _build_set_spec(
        family=resolved_family,
        size_parameter=selected_size,
        center=center,
        scale_diag=scale_diag,
        covariance=covariance,
        coverage_target=float(coverage_target),
        calibration_method=resolved_method,
        metadata={"source": "selected_spec", **covariance_meta},
    )
    metadata["selected_spec"] = selected_spec.model_dump(mode="python", exclude_none=True)
    return RobustSetCalibrationReport(
        family=resolved_family,
        selected_size=selected_size,
        target_coverage=float(coverage_target),
        target_inflation=inflation_budget,
        empirical_frontier=tuple(frontier),
        status=RobustSetCalibrationStatus.OK,
        adequacy_status=RobustSetAdequacyStatus.CALIBRATED,
        assumptions=("exchangeable_samples", assumptions_seed),
        metadata=metadata,
    )


class RobustSetCalibrator:
    """Convenience facade for sample-driven robust-set geometry estimation."""

    @staticmethod
    def build_spec(
        theta_samples: Sequence[Sequence[float]] | np.ndarray,
        *,
        family: RobustSetFamily | str,
        size_parameter: float,
        coverage_target: float | None = None,
        calibration_method: RobustSetCalibrationMethod | str = RobustSetCalibrationMethod.CONFORMAL,
    ) -> RobustSetSpec:
        return build_robust_set_spec_from_samples(
            theta_samples,
            family=family,
            size_parameter=size_parameter,
            coverage_target=coverage_target,
            calibration_method=calibration_method,
        )


class SetSizeSelector:
    """Convenience facade for coverage-vs-inflation set-size selection."""

    @staticmethod
    def select(
        theta_samples: Sequence[Sequence[float]] | np.ndarray,
        *,
        coverage_target: float,
        inflation_budget: float | None,
        family: RobustSetFamily | str,
        solve_nominal: Callable[[np.ndarray], Any],
        solve_robust: Callable[[RobustSetSpec], Any],
        loss_fn: Callable[[Any, np.ndarray], float],
        calibration_method: RobustSetCalibrationMethod | str = RobustSetCalibrationMethod.CONFORMAL,
        seed: int = 7,
    ) -> RobustSetCalibrationReport:
        return select_robust_set_size(
            theta_samples,
            coverage_target=coverage_target,
            inflation_budget=inflation_budget,
            family=family,
            solve_nominal=solve_nominal,
            solve_robust=solve_robust,
            loss_fn=loss_fn,
            calibration_method=calibration_method,
            seed=seed,
        )


__all__ = [
    "RobustSetCalibrator",
    "SetSizeSelector",
    "build_robust_set_spec_from_samples",
    "gaussian_parametric_radius",
    "select_robust_set_size",
]
