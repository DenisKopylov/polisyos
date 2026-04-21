"""Adaptive / responsive survey estimators."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, ClassVar, Literal, Mapping, Sequence

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

from .semiparametric import compute_binder_linearized_variance


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _adaptive_input_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("y_observed", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            SlotSpec("response_indicator", SlotType.VECTOR, Unit("indicator", "binary"), shape=("n_obs",)),
            SlotSpec(
                "base_inclusion_probabilities",
                SlotType.VECTOR,
                Unit("probability", "mass"),
                shape=("n_obs",),
            ),
            SlotSpec(
                "followup_sampling_probabilities",
                SlotType.VECTOR,
                Unit("probability", "mass"),
                shape=("n_obs",),
            ),
            SlotSpec("X_aux", SlotType.MATRIX, Unit("auxiliary", "value"), shape=("n_obs", "n_aux")),
            SlotSpec(
                "paradata_matrix",
                SlotType.MATRIX,
                Unit("paradata", "value"),
                shape=("n_obs", "n_paradata"),
            ),
            SlotSpec(
                "action_matrix",
                SlotType.MATRIX,
                Unit("action", "assignment"),
                shape=("n_obs", "n_actions"),
            ),
            SlotSpec("control_totals", SlotType.VECTOR, Unit("control", "value"), shape=("n_aux",)),
            SlotSpec("control_vcov", SlotType.MATRIX, Unit("variance", "value"), shape=("n_aux", "n_aux")),
            SlotSpec("strata", SlotType.VECTOR, Unit("stratum", "id"), shape=("n_obs",)),
            SlotSpec("clusters", SlotType.VECTOR, Unit("cluster", "id"), shape=("n_obs",)),
            SlotSpec(
                "replicate_weights",
                SlotType.MATRIX,
                Unit("weight", "mass"),
                shape=("n_replicates", "n_obs"),
            ),
            SlotSpec("cost_vector", SlotType.VECTOR, Unit("cost", "value"), shape=("n_obs",)),
        }
    )


def _vector(
    state: Mapping[str, Any],
    key: str,
    *,
    allow_nonfinite: bool = False,
    default: Any | None = None,
) -> np.ndarray:
    raw = state[key] if key in state else default
    if raw is None:
        raise KeyError(f"Missing required vector slot: {key}")
    arr = np.asarray(raw, dtype=float).reshape(-1)
    if not allow_nonfinite and np.any(~np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _matrix(
    state: Mapping[str, Any],
    key: str,
    *,
    default: Any | None = None,
) -> np.ndarray:
    raw = state[key] if key in state else default
    if raw is None:
        raise KeyError(f"Missing required matrix slot: {key}")
    arr = np.asarray(raw, dtype=float)
    if arr.ndim == 1:
        arr = arr[:, None]
    if arr.ndim != 2:
        raise ValueError(f"{key} must be a 2D matrix")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _optional_matrix(state: Mapping[str, Any], key: str) -> np.ndarray | None:
    if key not in state:
        return None
    value = np.asarray(state[key], dtype=float)
    if value.size == 0:
        return None
    if value.ndim == 1:
        value = value[:, None]
    if value.ndim != 2:
        raise ValueError(f"{key} must be a 2D matrix")
    if np.any(~np.isfinite(value)):
        raise ValueError(f"{key} must contain only finite values")
    return value


def _labels(state: Mapping[str, Any], key: str, *, n_obs: int) -> np.ndarray | None:
    if key not in state:
        return None
    arr = np.asarray(state[key], dtype=object).reshape(-1)
    if arr.shape[0] != n_obs:
        raise ValueError(f"{key} must have length {n_obs}")
    for item in arr.tolist():
        if item is None:
            raise ValueError(f"{key} must not contain null labels")
        if isinstance(item, float) and not np.isfinite(item):
            raise ValueError(f"{key} must not contain non-finite labels")
    return arr


def _replicate_matrix(state: Mapping[str, Any], *, n_obs: int) -> np.ndarray | None:
    value = _optional_matrix(state, "replicate_weights")
    if value is None:
        return None
    if n_obs not in value.shape:
        raise ValueError("replicate_weights must contain one dimension equal to n_obs")
    if value.shape[1] != n_obs:
        value = value.T
    if value.shape[1] != n_obs:
        raise ValueError("replicate_weights must have n_obs columns")
    if np.any(value < 0.0):
        raise ValueError("replicate_weights must be non-negative")
    return value


def _validate_row_count(key: str, arr: np.ndarray, n_obs: int) -> None:
    if arr.shape[0] != n_obs:
        raise ValueError(f"{key} must have {n_obs} rows, got {arr.shape[0]}")


def _parse_bounds(raw: Any) -> tuple[float | None, float | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, (tuple, list)) or len(raw) != 2:
        raise ValueError("bounds must be a 2-item tuple/list")
    lower = None if raw[0] is None else float(raw[0])
    upper = None if raw[1] is None else float(raw[1])
    if lower is not None and upper is not None and lower > upper:
        raise ValueError("bounds lower must be <= upper")
    return lower, upper


def _safe_probabilities(
    values: np.ndarray,
    *,
    label: str,
    lower: float,
    upper: float,
) -> np.ndarray:
    if np.any(~np.isfinite(values)):
        raise ValueError(f"{label} must contain only finite values")
    if np.any((values <= 0.0) | (values > 1.0)):
        raise ValueError(f"{label} must lie in (0, 1]")
    return np.clip(values, lower, upper)


def _string_tuple(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = (raw,)
    return tuple(str(item) for item in raw)


def _int_tuple(raw: Any) -> tuple[int, ...]:
    if raw is None:
        return ()
    if isinstance(raw, (int, np.integer)):
        return (int(raw),)
    return tuple(int(item) for item in raw)


def _feature_names(
    count: int,
    *,
    prefix: str,
    provided: Sequence[str] | None,
) -> tuple[str, ...]:
    names = tuple(str(item) for item in (provided or ()))
    if not names:
        return tuple(f"{prefix}_{idx}" for idx in range(count))
    if len(names) != count:
        raise ValueError(f"Expected {count} feature names for {prefix}, got {len(names)}")
    return names


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= 0.0:
        return 0.0
    return float(np.sum(weights * values) / total)


def _weighted_cov(x: np.ndarray, y: np.ndarray, weights: np.ndarray) -> float:
    mean_x = _weighted_mean(x, weights)
    mean_y = _weighted_mean(y, weights)
    total = float(np.sum(weights))
    if total <= 0.0:
        return 0.0
    return float(np.sum(weights * (x - mean_x) * (y - mean_y)) / total)


def _weighted_std(values: np.ndarray, weights: np.ndarray) -> float:
    variance = _weighted_cov(values, values, weights)
    return float(np.sqrt(max(variance, 0.0)))


def _weighted_corr(x: np.ndarray, y: np.ndarray, weights: np.ndarray) -> float:
    sx = _weighted_std(x, weights)
    sy = _weighted_std(y, weights)
    if sx <= 1e-12 or sy <= 1e-12:
        return 0.0
    return float(np.clip(_weighted_cov(x, y, weights) / (sx * sy), -1.0, 1.0))


def _combine_features(
    matrices: Sequence[np.ndarray],
    names: Sequence[Sequence[str]],
) -> tuple[np.ndarray, tuple[str, ...]]:
    parts: list[np.ndarray] = []
    part_names: list[str] = []
    for matrix, matrix_names in zip(matrices, names, strict=False):
        if matrix.shape[1] == 0:
            continue
        parts.append(matrix)
        part_names.extend(matrix_names)
    if not parts:
        return np.zeros((matrices[0].shape[0], 0), dtype=float), ()
    features = np.concatenate(parts, axis=1)
    means = np.mean(features, axis=0)
    sds = np.std(features, axis=0)
    sds = np.where(sds > 1e-12, sds, 1.0)
    standardized = (features - means) / sds
    return standardized, tuple(part_names)


def _fit_weighted_linear(
    X: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    ridge: float,
) -> np.ndarray:
    design = np.column_stack([np.ones(X.shape[0]), X])
    gram = design.T @ (weights[:, None] * design)
    penalty = np.eye(gram.shape[0], dtype=float) * ridge
    penalty[0, 0] = 0.0
    rhs = design.T @ (weights * y)
    try:
        return np.linalg.solve(gram + penalty, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(design * np.sqrt(weights)[:, None], y * np.sqrt(weights), rcond=None)[0]


def _predict_linear(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(X.shape[0]), X])
    return design @ beta


def _fit_weighted_logistic(
    X: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    *,
    ridge: float,
    max_iterations: int,
    tolerance: float,
    clip_min: float,
    clip_max: float,
) -> tuple[np.ndarray, np.ndarray]:
    response_rate = float(np.mean(y))
    n_obs = y.shape[0]
    if response_rate <= 0.0 or response_rate >= 1.0:
        propensity = np.full(n_obs, np.clip(response_rate, clip_min, clip_max), dtype=float)
        return propensity, np.zeros(X.shape[1] + 1, dtype=float)

    design = np.column_stack([np.ones(n_obs), X])
    beta = np.zeros(design.shape[1], dtype=float)
    penalty = np.eye(design.shape[1], dtype=float) * ridge
    penalty[0, 0] = 0.0

    for _ in range(max(1, max_iterations)):
        eta = np.clip(design @ beta, -20.0, 20.0)
        propensity = 1.0 / (1.0 + np.exp(-eta))
        working = np.maximum(weights * propensity * (1.0 - propensity), 1e-9)
        gradient = design.T @ (weights * (y - propensity)) - penalty @ beta
        hessian = design.T @ (design * working[:, None]) + penalty
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        beta += step
        if np.max(np.abs(step)) <= tolerance:
            break

    eta = np.clip(design @ beta, -20.0, 20.0)
    propensity = 1.0 / (1.0 + np.exp(-eta))
    return np.clip(propensity, clip_min, clip_max), beta


def _trim_weights(
    weights: np.ndarray,
    respondent_mask: np.ndarray,
    *,
    trim_method: str,
    trim_quantile: float,
    target_sum: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    trimmed = weights.copy()
    respondent_weights = trimmed[respondent_mask]
    if respondent_weights.size == 0:
        raise ValueError("At least one respondent is required")
    if trim_method in {"", "none"}:
        return trimmed, {"applied": False, "method": "none", "trimmed_share": 0.0}
    if trim_method not in {"clip", "winsorize"}:
        raise ValueError("trim_method must be one of {'none', 'clip', 'winsorize'}")

    quantile = float(np.clip(trim_quantile, 0.5, 1.0))
    lower = float(np.min(respondent_weights))
    upper = float(np.quantile(respondent_weights, quantile))
    before = respondent_weights.copy()
    respondent_weights = np.clip(respondent_weights, lower, upper)
    current_sum = float(np.sum(respondent_weights))
    if current_sum > 0.0:
        respondent_weights *= target_sum / current_sum
    trimmed[respondent_mask] = respondent_weights
    return trimmed, {
        "applied": True,
        "method": trim_method,
        "trim_quantile": quantile,
        "lower_bound": lower,
        "upper_bound": upper,
        "trimmed_share": float(np.mean(np.abs(before - respondent_weights) > 1e-12)),
    }


def _linear_calibration(
    weights: np.ndarray,
    X: np.ndarray,
    target_totals: np.ndarray,
    *,
    ridge: float,
    bounds: tuple[float | None, float | None],
) -> tuple[np.ndarray, dict[str, Any]]:
    if X.shape[1] != target_totals.shape[0]:
        raise ValueError("control_totals length must match X_aux columns")
    system = X.T @ (weights[:, None] * X) + np.eye(X.shape[1], dtype=float) * ridge
    rhs = target_totals - (X.T @ weights)
    try:
        lam = np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError:
        lam = np.linalg.lstsq(system, rhs, rcond=None)[0]
    g = 1.0 + X @ lam
    lower, upper = bounds
    if lower is not None:
        g = np.maximum(g, lower)
    if upper is not None:
        g = np.minimum(g, upper)
    g = np.maximum(g, 1e-9)
    calibrated = weights * g
    achieved = X.T @ calibrated
    residuals = target_totals - achieved
    return calibrated, {
        "method": "linear",
        "lambda": lam.tolist(),
        "achieved_totals": achieved.tolist(),
        "target_totals": target_totals.tolist(),
        "residuals": residuals.tolist(),
        "max_abs_residual": float(np.max(np.abs(residuals))) if residuals.size else 0.0,
        "converged": bool(np.max(np.abs(residuals)) <= 1e-6) if residuals.size else True,
    }


def _raking_calibration(
    weights: np.ndarray,
    X: np.ndarray,
    target_totals: np.ndarray,
    *,
    max_iterations: int,
    tolerance: float,
    bounds: tuple[float | None, float | None],
) -> tuple[np.ndarray, dict[str, Any]]:
    if X.shape[1] != target_totals.shape[0]:
        raise ValueError("control_totals length must match X_aux columns")
    if np.any(X < 0.0):
        raise ValueError("raking calibration requires non-negative X_aux")

    calibrated = weights.copy()
    base = weights.copy()
    lower, upper = bounds
    converged = False
    for _ in range(max(1, max_iterations)):
        achieved = X.T @ calibrated
        residuals = target_totals - achieved
        if residuals.size == 0 or float(np.max(np.abs(residuals))) <= tolerance:
            converged = True
            break
        for j in range(X.shape[1]):
            current = float(np.sum(calibrated * X[:, j]))
            target = float(target_totals[j])
            if current <= 0.0 or target <= 0.0:
                continue
            factor = target / current
            calibrated *= np.power(factor, X[:, j])
            if lower is not None:
                calibrated = np.maximum(calibrated, base * lower)
            if upper is not None:
                calibrated = np.minimum(calibrated, base * upper)

    achieved = X.T @ calibrated
    residuals = target_totals - achieved
    return calibrated, {
        "method": "raking",
        "achieved_totals": achieved.tolist(),
        "target_totals": target_totals.tolist(),
        "residuals": residuals.tolist(),
        "max_abs_residual": float(np.max(np.abs(residuals))) if residuals.size else 0.0,
        "converged": converged or bool(np.max(np.abs(residuals)) <= tolerance) if residuals.size else True,
    }


def _logit_calibration(
    weights: np.ndarray,
    X: np.ndarray,
    target_totals: np.ndarray,
    *,
    max_iterations: int,
    tolerance: float,
    ridge: float,
    bounds: tuple[float | None, float | None],
) -> tuple[np.ndarray, dict[str, Any]]:
    lower = 0.2 if bounds[0] is None else float(bounds[0])
    upper = 5.0 if bounds[1] is None else float(bounds[1])
    if not lower < 1.0 < upper:
        raise ValueError("logit calibration requires bounds lower < 1 < upper")
    baseline_share = (1.0 - lower) / (upper - lower)
    baseline_share = float(np.clip(baseline_share, 1e-6, 1.0 - 1e-6))
    offset = float(np.log(baseline_share / (1.0 - baseline_share)))
    lam = np.zeros(X.shape[1], dtype=float)
    converged = False

    for _ in range(max(1, max_iterations)):
        eta = X @ lam + offset
        sig = 1.0 / (1.0 + np.exp(-np.clip(eta, -20.0, 20.0)))
        g = lower + (upper - lower) * sig
        achieved = X.T @ (weights * g)
        residuals = target_totals - achieved
        if residuals.size == 0 or float(np.max(np.abs(residuals))) <= tolerance:
            converged = True
            break
        derivative = weights * (upper - lower) * sig * (1.0 - sig)
        jacobian = X.T @ (derivative[:, None] * X) + np.eye(X.shape[1], dtype=float) * ridge
        try:
            step = np.linalg.solve(jacobian, residuals)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(jacobian, residuals, rcond=None)[0]
        lam += step
        if np.max(np.abs(step)) <= tolerance:
            converged = True
            break

    eta = X @ lam + offset
    sig = 1.0 / (1.0 + np.exp(-np.clip(eta, -20.0, 20.0)))
    g = lower + (upper - lower) * sig
    calibrated = weights * g
    achieved = X.T @ calibrated
    residuals = target_totals - achieved
    return calibrated, {
        "method": "logit",
        "lambda": lam.tolist(),
        "bounds_used": [lower, upper],
        "achieved_totals": achieved.tolist(),
        "target_totals": target_totals.tolist(),
        "residuals": residuals.tolist(),
        "max_abs_residual": float(np.max(np.abs(residuals))) if residuals.size else 0.0,
        "converged": converged or bool(np.max(np.abs(residuals)) <= tolerance) if residuals.size else True,
    }


def _calibrate_weights(
    weights: np.ndarray,
    X: np.ndarray,
    target_totals: np.ndarray,
    *,
    calibration_method: str,
    max_iterations: int,
    tolerance: float,
    ridge: float,
    bounds: tuple[float | None, float | None],
) -> tuple[np.ndarray, dict[str, Any]]:
    if target_totals.size == 0:
        return weights, {
            "method": "none",
            "achieved_totals": [],
            "target_totals": [],
            "residuals": [],
            "max_abs_residual": 0.0,
            "converged": True,
        }
    if calibration_method == "linear":
        return _linear_calibration(weights, X, target_totals, ridge=ridge, bounds=bounds)
    if calibration_method == "raking":
        return _raking_calibration(
            weights,
            X,
            target_totals,
            max_iterations=max_iterations,
            tolerance=tolerance,
            bounds=bounds,
        )
    if calibration_method == "logit":
        return _logit_calibration(
            weights,
            X,
            target_totals,
            max_iterations=max_iterations,
            tolerance=tolerance,
            ridge=ridge,
            bounds=bounds,
        )
    raise ValueError("calibration_method must be one of {'linear', 'raking', 'logit'}")


def _effective_sample_size(weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    denom = float(np.sum(np.square(weights)))
    if total <= 0.0 or denom <= 0.0:
        return 0.0
    return total * total / denom


def _weight_summary(weights: np.ndarray) -> dict[str, Any]:
    if weights.size == 0:
        return {
            "n_respondents": 0,
            "sum": 0.0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "cv": 0.0,
            "effective_sample_size": 0.0,
            "design_effect": 0.0,
            "percentiles": {"p05": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p95": 0.0},
        }
    ess = _effective_sample_size(weights)
    mean = float(np.mean(weights))
    return {
        "n_respondents": int(weights.size),
        "sum": float(np.sum(weights)),
        "min": float(np.min(weights)),
        "max": float(np.max(weights)),
        "mean": mean,
        "cv": float(np.std(weights) / max(mean, 1e-12)),
        "effective_sample_size": ess,
        "design_effect": float(weights.size / max(ess, 1e-12)),
        "percentiles": {
            "p05": float(np.quantile(weights, 0.05)),
            "p25": float(np.quantile(weights, 0.25)),
            "p50": float(np.quantile(weights, 0.50)),
            "p75": float(np.quantile(weights, 0.75)),
            "p95": float(np.quantile(weights, 0.95)),
        },
    }


def _weighted_estimate(
    values: np.ndarray,
    weights: np.ndarray,
    *,
    estimand: Literal["mean", "total"],
) -> tuple[float, float, float, float]:
    total = float(np.sum(weights * values))
    weight_sum = float(np.sum(weights))
    mean = total / max(weight_sum, 1e-12)
    centered = values - mean
    var_mean = float(np.sum(np.square(weights) * np.square(centered)) / max(weight_sum * weight_sum, 1e-12))
    ess = _effective_sample_size(weights)
    if ess > 1.0:
        var_mean *= ess / max(ess - 1.0, 1.0)
    var_total = var_mean * weight_sum * weight_sum
    if estimand == "total":
        return total, mean, max(var_total, 0.0), float(np.sqrt(max(var_total, 0.0)))
    return mean, total, max(var_mean, 0.0), float(np.sqrt(max(var_mean, 0.0)))


def _representativeness_indicator(propensity: np.ndarray, sample_weight: np.ndarray) -> float:
    total = float(np.sum(sample_weight))
    if total <= 0.0:
        return 0.0
    mean = float(np.sum(sample_weight * propensity) / total)
    variance = float(np.sum(sample_weight * np.square(propensity - mean)) / total)
    return float(np.clip(1.0 - 2.0 * np.sqrt(max(variance, 0.0)), 0.0, 1.0))


def _column_diagnostics(
    matrix: np.ndarray,
    names: Sequence[str],
    *,
    propensity: np.ndarray,
    response: np.ndarray,
    sample_weight: np.ndarray,
) -> dict[str, dict[str, float]]:
    if matrix.shape[1] == 0:
        return {}
    diagnostics: dict[str, dict[str, float]] = {}
    for idx, name in enumerate(names):
        column = matrix[:, idx]
        diagnostics[str(name)] = {
            "partial_r_indicator": abs(_weighted_corr(column, propensity, sample_weight)),
            "response_correlation": abs(_weighted_corr(column, response, sample_weight)),
            "mean": _weighted_mean(column, sample_weight),
        }
    return diagnostics


def _action_effect_diagnostics(
    actions: np.ndarray,
    action_names: Sequence[str],
    *,
    response: np.ndarray,
    propensity: np.ndarray,
    cost_vector: np.ndarray,
) -> dict[str, dict[str, float]]:
    if actions.shape[1] == 0:
        return {}
    diagnostics: dict[str, dict[str, float]] = {}
    for idx, name in enumerate(action_names):
        active = actions[:, idx] > 0.5
        inactive = ~active
        response_active = float(np.mean(response[active])) if np.any(active) else 0.0
        response_inactive = float(np.mean(response[inactive])) if np.any(inactive) else 0.0
        propensity_active = float(np.mean(propensity[active])) if np.any(active) else 0.0
        propensity_inactive = float(np.mean(propensity[inactive])) if np.any(inactive) else 0.0
        diagnostics[str(name)] = {
            "n_targeted": float(np.sum(active)),
            "response_rate_targeted": response_active,
            "response_rate_untargeted": response_inactive,
            "response_rate_gap": response_active - response_inactive,
            "estimated_propensity_gap": propensity_active - propensity_inactive,
            "mean_cost_targeted": float(np.mean(cost_vector[active])) if np.any(active) else 0.0,
        }
    return diagnostics


def _operational_differentials(
    matrix: np.ndarray,
    names: Sequence[str],
    *,
    response: np.ndarray,
    weights: np.ndarray,
    selected_indices: Sequence[int],
) -> dict[str, dict[str, float]]:
    diagnostics: dict[str, dict[str, float]] = {}
    for idx in selected_indices:
        if idx < 0 or idx >= matrix.shape[1]:
            continue
        column = matrix[:, idx]
        diagnostics[str(names[idx])] = {
            "response_gap": _weighted_mean(column[response > 0.5], weights[response > 0.5])
            - _weighted_mean(column[response <= 0.5], weights[response <= 0.5])
            if np.any(response <= 0.5)
            else 0.0,
            "response_correlation": abs(_weighted_corr(column, response, weights)),
        }
    return diagnostics


def _control_total_variance_adjustment(
    X: np.ndarray,
    values: np.ndarray,
    weights: np.ndarray,
    control_vcov: np.ndarray | None,
    *,
    ridge: float,
    denominator: float,
) -> tuple[float, list[float]]:
    if control_vcov is None or control_vcov.size == 0 or X.shape[1] == 0:
        return 0.0, []
    beta = _fit_weighted_linear(X, values, weights, ridge=ridge)[1:]
    adjustment_total = float(beta @ control_vcov @ beta)
    adjustment_mean = adjustment_total / max(denominator * denominator, 1e-12)
    return max(adjustment_mean, 0.0), beta.tolist()


def _next_power_of_two(value: int) -> int:
    power = 1
    while power < value:
        power *= 2
    return power


def _hadamard(order: int) -> np.ndarray:
    if order == 1:
        return np.array([[1.0]])
    half = _hadamard(order // 2)
    return np.block([[half, half], [half, -half]])


def _resolved_design_labels(inputs: "_AdaptiveInputs") -> tuple[np.ndarray, np.ndarray]:
    strata = inputs.strata if inputs.strata is not None else np.zeros(inputs.n_obs, dtype=object)
    clusters = inputs.clusters if inputs.clusters is not None else np.arange(inputs.n_obs, dtype=object)
    return strata, clusters


def _generate_bootstrap_replicates(
    base_weights: np.ndarray,
    *,
    inputs: "_AdaptiveInputs",
    n_replicates: int,
    bootstrap_type: str,
    seed: int,
) -> np.ndarray:
    strata, clusters = _resolved_design_labels(inputs)
    use_psu = bootstrap_type in {"auto", "psu", "stratified_psu"} and inputs.clusters is not None
    group_labels = clusters if use_psu else np.arange(inputs.n_obs, dtype=object)
    rng = np.random.default_rng(seed)
    replicates = np.zeros((n_replicates, inputs.n_obs), dtype=float)

    for rep in range(n_replicates):
        counts = np.zeros(inputs.n_obs, dtype=float)
        for stratum in np.unique(strata):
            in_h = strata == stratum
            labels_h = np.unique(group_labels[in_h])
            draws = rng.choice(labels_h, size=len(labels_h), replace=True)
            label_counts = {label: int(np.sum(draws == label)) for label in labels_h}
            for idx in np.flatnonzero(in_h):
                counts[idx] = float(label_counts[group_labels[idx]])
        replicates[rep] = base_weights * counts
    return replicates


def _generate_jackknife_replicates(
    base_weights: np.ndarray,
    *,
    inputs: "_AdaptiveInputs",
    n_replicates: int,
) -> np.ndarray:
    strata, clusters = _resolved_design_labels(inputs)
    replicates: list[np.ndarray] = []
    for stratum in np.unique(strata):
        in_h = strata == stratum
        clusters_h = np.unique(clusters[in_h])
        m_h = int(clusters_h.size)
        if m_h < 2:
            continue
        inflate = m_h / (m_h - 1.0)
        for cluster in clusters_h:
            replicate = base_weights.copy()
            delete_mask = in_h & (clusters == cluster)
            keep_mask = in_h & ~delete_mask
            replicate[delete_mask] = 0.0
            replicate[keep_mask] *= inflate
            replicates.append(replicate)
            if len(replicates) >= n_replicates:
                break
        if len(replicates) >= n_replicates:
            break
    if not replicates:
        raise ValueError("jackknife requires at least one stratum with two or more PSU/units")
    return np.asarray(replicates, dtype=float)


def _generate_brr_replicates(
    base_weights: np.ndarray,
    *,
    inputs: "_AdaptiveInputs",
    n_replicates: int,
) -> np.ndarray:
    strata, clusters = _resolved_design_labels(inputs)
    strata_levels = np.unique(strata)
    psu_pairs: list[tuple[object, object]] = []
    for stratum in strata_levels:
        clusters_h = np.unique(clusters[strata == stratum])
        if clusters_h.size != 2:
            raise ValueError("BRR requires exactly two PSU per stratum")
        psu_pairs.append((clusters_h[0], clusters_h[1]))

    hadamard_order = _next_power_of_two(max(1, len(strata_levels)))
    had = _hadamard(hadamard_order)
    total_reps = min(n_replicates, had.shape[0])
    replicates = np.zeros((total_reps, inputs.n_obs), dtype=float)
    for rep in range(total_reps):
        current = np.zeros(inputs.n_obs, dtype=float)
        for idx, stratum in enumerate(strata_levels):
            choose_first = had[rep, idx] >= 0.0
            selected = psu_pairs[idx][0 if choose_first else 1]
            mask = (strata == stratum) & (clusters == selected)
            current[mask] = 2.0 * base_weights[mask]
        replicates[rep] = current
    return replicates


def _replicate_variance(
    estimates: np.ndarray,
    *,
    full_estimate: float,
    variance_method: str,
    mse: bool,
) -> float:
    if estimates.size <= 1:
        return 0.0
    center = full_estimate if mse else float(np.mean(estimates))
    deltas = estimates - center
    if variance_method == "jackknife":
        return float((estimates.size - 1.0) / estimates.size * np.sum(deltas**2))
    if variance_method == "brr":
        return float(np.mean(deltas**2))
    return float(np.var(estimates, ddof=1))


def _common_parameters() -> tuple[ParameterSpec, ...]:
    return (
        ParameterSpec(name="estimand", default="mean"),
        ParameterSpec(name="propensity_model", default="logistic"),
        ParameterSpec(name="propensity_feature_mode", default="full"),
        ParameterSpec(name="stabilized", default=True),
        ParameterSpec(name="clip_min", default=0.02, bounds=(1e-6, 0.5)),
        ParameterSpec(name="clip_max", default=0.98, bounds=(0.5, 0.999999)),
        ParameterSpec(name="trim_method", default="none"),
        ParameterSpec(name="trim_quantile", default=0.99, bounds=(0.5, 1.0)),
        ParameterSpec(name="calibration_method", default="linear"),
        ParameterSpec(name="variance_method", default="auto"),
        ParameterSpec(name="n_replicates", default=64, bounds=(1, None)),
        ParameterSpec(name="mse", default=True),
        ParameterSpec(name="bootstrap_type", default="auto"),
        ParameterSpec(name="replicate_weight_stage", default="base_design"),
        ParameterSpec(name="max_iterations", default=50, bounds=(1, None)),
        ParameterSpec(name="tolerance", default=1e-8, bounds=(0.0, None)),
        ParameterSpec(name="ridge", default=1e-6, bounds=(0.0, None)),
        ParameterSpec(name="bounds", default=(None, None)),
        ParameterSpec(name="confidence_level", default=0.95, bounds=(0.5, 0.999)),
        ParameterSpec(name="x_feature_names", default=()),
        ParameterSpec(name="paradata_feature_names", default=()),
        ParameterSpec(name="action_feature_names", default=()),
        ParameterSpec(name="mode_column_indices", default=()),
        ParameterSpec(name="interviewer_column_indices", default=()),
        ParameterSpec(name="store_action_history", default=True),
        ParameterSpec(name="store_stop_reason", default=True),
        ParameterSpec(name="require_prespecified_rules", default=True),
        ParameterSpec(name="decision_rule_id", default=""),
        ParameterSpec(name="adaptation_log_id", default=""),
        ParameterSpec(name="control_totals_version", default=""),
        ParameterSpec(name="stop_reason", default=""),
        ParameterSpec(name="stop_lambda", default=1.0, bounds=(0.0, None)),
        ParameterSpec(name="stop_gamma", default=1.0, bounds=(0.0, None)),
        ParameterSpec(name="seed", default=42),
    )


@dataclass(frozen=True, slots=True)
class _AdaptiveInputs:
    y: np.ndarray
    response: np.ndarray
    pi0: np.ndarray
    followup: np.ndarray
    X_aux: np.ndarray
    paradata: np.ndarray
    actions: np.ndarray
    control_totals: np.ndarray
    control_vcov: np.ndarray | None
    strata: np.ndarray | None
    clusters: np.ndarray | None
    replicate_weights: np.ndarray | None
    cost_vector: np.ndarray

    @property
    def n_obs(self) -> int:
        return int(self.y.shape[0])


@dataclass(frozen=True, slots=True)
class _WeightRun:
    base_weights: np.ndarray
    phase_weights: np.ndarray
    propensity: np.ndarray
    propensity_coefficients: np.ndarray
    feature_names: tuple[str, ...]
    features_used: np.ndarray
    nonresponse_weights: np.ndarray
    trimmed_weights: np.ndarray
    final_weights: np.ndarray
    trim_info: dict[str, Any]
    calibration_status: dict[str, Any]
    respondent_mask: np.ndarray
    phase_mean: float
    nr_mean: float
    final_mean: float


@dataclass(frozen=True, slots=True)
class _EstimateRun:
    point_estimate: float
    mean_estimate: float
    total_estimate: float
    variance_estimate: float
    standard_error: float
    variance_method_used: str
    variance_diagnostics: dict[str, Any]
    replicate_estimates: np.ndarray | None
    control_total_variance_adjustment: float
    control_total_slope: list[float]
    auxiliary: dict[str, Any]


def _coerce_inputs(state: Mapping[str, Any]) -> _AdaptiveInputs:
    y = _vector(state, "y_observed", allow_nonfinite=True)
    n_obs = y.shape[0]
    response = np.where(_vector(state, "response_indicator") > 0.5, 1.0, 0.0)
    if response.shape[0] != n_obs:
        raise ValueError("response_indicator must align with y_observed")
    if not np.any(response > 0.5):
        raise ValueError("At least one respondent is required")
    if np.any(~np.isfinite(y[response > 0.5])):
        raise ValueError("y_observed must be finite for responding units")

    pi0 = _vector(state, "base_inclusion_probabilities")
    followup = _vector(state, "followup_sampling_probabilities", default=np.ones(n_obs, dtype=float))
    if pi0.shape[0] != n_obs or followup.shape[0] != n_obs:
        raise ValueError("Inclusion and follow-up probabilities must align with y_observed")

    X_aux = _matrix(state, "X_aux")
    paradata = _matrix(state, "paradata_matrix")
    actions = _matrix(state, "action_matrix")
    _validate_row_count("X_aux", X_aux, n_obs)
    _validate_row_count("paradata_matrix", paradata, n_obs)
    _validate_row_count("action_matrix", actions, n_obs)

    control_totals = _vector(state, "control_totals", default=np.array([], dtype=float))
    control_vcov = _optional_matrix(state, "control_vcov")
    if control_vcov is not None:
        if control_vcov.shape != (X_aux.shape[1], X_aux.shape[1]):
            raise ValueError("control_vcov must have shape (n_aux, n_aux)")
        if not np.allclose(control_vcov, control_vcov.T, atol=1e-8):
            raise ValueError("control_vcov must be symmetric")

    strata = _labels(state, "strata", n_obs=n_obs)
    clusters = _labels(state, "clusters", n_obs=n_obs)
    replicate_weights = _replicate_matrix(state, n_obs=n_obs)
    cost_vector = _vector(state, "cost_vector", default=np.zeros(n_obs, dtype=float))
    if cost_vector.shape[0] != n_obs:
        raise ValueError("cost_vector must align with y_observed")
    if np.any(cost_vector < 0.0):
        raise ValueError("cost_vector must be non-negative")

    return _AdaptiveInputs(
        y=y,
        response=response,
        pi0=pi0,
        followup=followup,
        X_aux=X_aux,
        paradata=paradata,
        actions=actions,
        control_totals=control_totals,
        control_vcov=control_vcov,
        strata=strata,
        clusters=clusters,
        replicate_weights=replicate_weights,
        cost_vector=cost_vector,
    )


def _resolve_feature_block(
    inputs: _AdaptiveInputs,
    params: Mapping[str, Any],
    *,
    mode: str,
) -> tuple[np.ndarray, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    x_names = _feature_names(inputs.X_aux.shape[1], prefix="x", provided=_string_tuple(params.get("x_feature_names")))
    p_names = _feature_names(
        inputs.paradata.shape[1],
        prefix="paradata",
        provided=_string_tuple(params.get("paradata_feature_names")),
    )
    a_names = _feature_names(
        inputs.actions.shape[1],
        prefix="action",
        provided=_string_tuple(params.get("action_feature_names")),
    )

    if mode == "aux_only":
        features, names = _combine_features([inputs.X_aux], [x_names])
    elif mode == "history_only":
        features, names = _combine_features([inputs.paradata, inputs.actions], [p_names, a_names])
    else:
        features, names = _combine_features(
            [inputs.X_aux, inputs.paradata, inputs.actions],
            [x_names, p_names, a_names],
        )
    return features, names, p_names, a_names


def _run_weight_pipeline(
    inputs: _AdaptiveInputs,
    params: Mapping[str, Any],
    *,
    base_weights_override: np.ndarray | None = None,
    feature_mode_override: str | None = None,
    calibration_method_override: str | None = None,
) -> _WeightRun:
    clip_min = float(params.get("clip_min", 0.02))
    clip_max = float(params.get("clip_max", 0.98))
    if not 0.0 < clip_min < clip_max <= 1.0:
        raise ValueError("clip_min and clip_max must satisfy 0 < clip_min < clip_max <= 1")

    pi0 = _safe_probabilities(
        inputs.pi0,
        label="base_inclusion_probabilities",
        lower=1e-9,
        upper=1.0,
    )
    followup = _safe_probabilities(
        inputs.followup,
        label="followup_sampling_probabilities",
        lower=1e-9,
        upper=1.0,
    )
    base_weights = np.asarray(base_weights_override, dtype=float) if base_weights_override is not None else 1.0 / pi0
    if base_weights.shape != pi0.shape or np.any(~np.isfinite(base_weights)) or np.any(base_weights < 0.0):
        raise ValueError("Replicate/base weights must be finite, non-negative, and align with the sample")

    phase_weights = base_weights / followup
    feature_mode = str(feature_mode_override or params.get("propensity_feature_mode", "full")).lower()
    features, feature_names, _, _ = _resolve_feature_block(inputs, params, mode=feature_mode)
    sample_weight = phase_weights / max(float(np.mean(phase_weights)), 1e-12)

    propensity_model = str(params.get("propensity_model", "logistic")).lower()
    if propensity_model != "logistic":
        raise ValueError("Phase 1 adaptive weighting currently supports propensity_model='logistic' only")
    propensity, coefficients = _fit_weighted_logistic(
        features,
        inputs.response,
        sample_weight,
        ridge=float(params.get("ridge", 1e-6)),
        max_iterations=int(params.get("max_iterations", 50)),
        tolerance=float(params.get("tolerance", 1e-8)),
        clip_min=clip_min,
        clip_max=clip_max,
    )

    response_rate = float(np.mean(inputs.response))
    nr_factor = (response_rate / propensity) if bool(params.get("stabilized", True)) else (1.0 / propensity)
    nonresponse_weights = np.zeros(inputs.n_obs, dtype=float)
    respondent_mask = inputs.response > 0.5
    nonresponse_weights[respondent_mask] = phase_weights[respondent_mask] * nr_factor[respondent_mask]

    target_weight_sum = float(np.sum(phase_weights))
    current_weight_sum = float(np.sum(nonresponse_weights[respondent_mask]))
    if current_weight_sum > 0.0:
        nonresponse_weights[respondent_mask] *= target_weight_sum / current_weight_sum

    trimmed_weights, trim_info = _trim_weights(
        nonresponse_weights,
        respondent_mask,
        trim_method=str(params.get("trim_method", "none")).lower(),
        trim_quantile=float(params.get("trim_quantile", 0.99)),
        target_sum=target_weight_sum,
    )

    final_weights = trimmed_weights.copy()
    calibration_status = {
        "method": "none",
        "achieved_totals": [],
        "target_totals": [],
        "residuals": [],
        "max_abs_residual": 0.0,
        "converged": True,
    }
    if inputs.control_totals.size > 0:
        bounds = _parse_bounds(params.get("bounds", (None, None)))
        calibration_method = str(calibration_method_override or params.get("calibration_method", "linear")).lower()
        calibrated_resp, calibration_status = _calibrate_weights(
            trimmed_weights[respondent_mask],
            inputs.X_aux[respondent_mask],
            inputs.control_totals,
            calibration_method=calibration_method,
            max_iterations=int(params.get("max_iterations", 50)),
            tolerance=float(params.get("tolerance", 1e-8)),
            ridge=float(params.get("ridge", 1e-6)),
            bounds=bounds,
        )
        final_weights[:] = 0.0
        final_weights[respondent_mask] = calibrated_resp

    y_resp = inputs.y[respondent_mask]
    phase_resp = phase_weights[respondent_mask]
    nr_resp = nonresponse_weights[respondent_mask]
    final_resp = final_weights[respondent_mask]
    phase_mean = _weighted_mean(y_resp, phase_resp)
    nr_mean = _weighted_mean(y_resp, nr_resp)
    final_mean = _weighted_mean(y_resp, final_resp)

    return _WeightRun(
        base_weights=base_weights,
        phase_weights=phase_weights,
        propensity=propensity,
        propensity_coefficients=coefficients,
        feature_names=feature_names,
        features_used=features,
        nonresponse_weights=nonresponse_weights,
        trimmed_weights=trimmed_weights,
        final_weights=final_weights,
        trim_info=trim_info,
        calibration_status=calibration_status,
        respondent_mask=respondent_mask,
        phase_mean=phase_mean,
        nr_mean=nr_mean,
        final_mean=final_mean,
    )


def _variance_from_linearization(
    inputs: _AdaptiveInputs,
    run: _WeightRun,
    *,
    estimand: Literal["mean", "total"],
    value_vector: np.ndarray,
    analysis_weights: np.ndarray,
    ridge: float,
) -> tuple[float, float, dict[str, Any], float, list[float]]:
    if inputs.strata is not None or inputs.clusters is not None:
        variance = compute_binder_linearized_variance(
            value_vector,
            strata=inputs.strata,
            psu=inputs.clusters,
            analysis_weights=analysis_weights,
        )
        base_variance = variance.variance
        diagnostics = {
            "linearization_backend": "binder",
            "linearized_design_effect": variance.design_effect,
            "linearized_effective_n": variance.effective_n,
        }
    else:
        _, _, base_variance, _ = _weighted_estimate(value_vector, analysis_weights, estimand="mean")
        diagnostics = {
            "linearization_backend": "weighted_approximation",
            "linearized_design_effect": float(len(value_vector) / max(_effective_sample_size(analysis_weights), 1e-12)),
            "linearized_effective_n": _effective_sample_size(analysis_weights),
        }

    control_adjustment_mean, slope = _control_total_variance_adjustment(
        inputs.X_aux,
        value_vector,
        analysis_weights,
        inputs.control_vcov,
        ridge=ridge,
        denominator=float(np.sum(analysis_weights)),
    )
    variance_mean = base_variance + control_adjustment_mean
    if estimand == "total":
        scale = float(np.sum(analysis_weights)) ** 2
        variance_estimate = variance_mean * scale
        control_adjustment = control_adjustment_mean * scale
    else:
        variance_estimate = variance_mean
        control_adjustment = control_adjustment_mean
    return (
        max(variance_estimate, 0.0),
        float(np.sqrt(max(variance_estimate, 0.0))),
        diagnostics,
        float(control_adjustment),
        slope,
    )


def _generate_replicates(
    inputs: _AdaptiveInputs,
    params: Mapping[str, Any],
    *,
    base_weights: np.ndarray,
    variance_method: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    n_replicates = max(2, int(params.get("n_replicates", 64)))
    if inputs.replicate_weights is not None:
        replicates = inputs.replicate_weights
        if replicates.shape[0] > n_replicates:
            replicates = replicates[:n_replicates]
        return replicates, {
            "replicates_source": "supplied",
            "replicate_weight_stage": str(params.get("replicate_weight_stage", "base_design")).lower(),
        }

    seed = int(params.get("seed", 42))
    if variance_method == "bootstrap":
        replicates = _generate_bootstrap_replicates(
            base_weights,
            inputs=inputs,
            n_replicates=n_replicates,
            bootstrap_type=str(params.get("bootstrap_type", "auto")).lower(),
            seed=seed,
        )
        return replicates, {"replicates_source": "generated_bootstrap", "replicate_weight_stage": "base_design"}
    if variance_method == "jackknife":
        replicates = _generate_jackknife_replicates(base_weights, inputs=inputs, n_replicates=n_replicates)
        return replicates, {"replicates_source": "generated_jackknife", "replicate_weight_stage": "base_design"}
    if variance_method == "brr":
        replicates = _generate_brr_replicates(base_weights, inputs=inputs, n_replicates=n_replicates)
        return replicates, {"replicates_source": "generated_brr", "replicate_weight_stage": "base_design"}
    raise ValueError(f"Unsupported replicate variance method: {variance_method}")


def _estimate_from_replicates(
    inputs: _AdaptiveInputs,
    params: Mapping[str, Any],
    run: _WeightRun,
    *,
    estimand: Literal["mean", "total"],
    estimator: Literal["calibrated", "augmented"],
    auxiliary_builder: Any | None = None,
) -> tuple[float, float, dict[str, Any], np.ndarray, float, list[float]]:
    requested_method = str(params.get("variance_method", "auto")).lower()
    variance_method = requested_method
    if variance_method == "auto":
        if inputs.replicate_weights is not None:
            variance_method = "bootstrap"
        elif inputs.clusters is not None or inputs.strata is not None:
            variance_method = "linearization"
        else:
            variance_method = "bootstrap"

    ridge = float(params.get("ridge", 1e-6))
    if variance_method == "linearization":
        if estimator == "augmented" and auxiliary_builder is not None:
            value_vector = np.asarray(auxiliary_builder["pseudo_outcome"], dtype=float)
            analysis_weights = np.asarray(auxiliary_builder["analysis_weights"], dtype=float)
        else:
            respondent_mask = run.respondent_mask
            value_vector = inputs.y[respondent_mask]
            analysis_weights = run.final_weights[respondent_mask]
            if inputs.strata is not None or inputs.clusters is not None:
                reduced_inputs = _AdaptiveInputs(
                    y=value_vector,
                    response=np.ones(value_vector.shape[0], dtype=float),
                    pi0=np.ones(value_vector.shape[0], dtype=float),
                    followup=np.ones(value_vector.shape[0], dtype=float),
                    X_aux=inputs.X_aux[respondent_mask],
                    paradata=inputs.paradata[respondent_mask],
                    actions=inputs.actions[respondent_mask],
                    control_totals=inputs.control_totals,
                    control_vcov=inputs.control_vcov,
                    strata=inputs.strata[respondent_mask] if inputs.strata is not None else None,
                    clusters=inputs.clusters[respondent_mask] if inputs.clusters is not None else None,
                    replicate_weights=None,
                    cost_vector=inputs.cost_vector[respondent_mask],
                )
                return _variance_from_linearization(
                    reduced_inputs,
                    run,
                    estimand=estimand,
                    value_vector=value_vector,
                    analysis_weights=analysis_weights,
                    ridge=ridge,
                ) + (None,)[:0]

        variance, se, diagnostics, control_adjustment, slope = _variance_from_linearization(
            inputs,
            run,
            estimand=estimand,
            value_vector=value_vector,
            analysis_weights=analysis_weights,
            ridge=ridge,
        )
        return variance, se, diagnostics, np.array([], dtype=float), control_adjustment, slope

    replicate_weights, replicate_info = _generate_replicates(
        inputs,
        params,
        base_weights=run.base_weights,
        variance_method=variance_method,
    )

    estimates = np.zeros(replicate_weights.shape[0], dtype=float)
    replicate_stage = replicate_info.get("replicate_weight_stage", "base_design")
    for rep_idx, rep_weights in enumerate(replicate_weights):
        if replicate_stage == "analysis":
            if estimator == "augmented" and auxiliary_builder is not None:
                target_values = np.asarray(auxiliary_builder["pseudo_outcome"], dtype=float)
                estimates[rep_idx] = _weighted_mean(target_values, rep_weights) if estimand == "mean" else float(np.sum(rep_weights * target_values))
            else:
                respondent_mask = run.respondent_mask
                values = inputs.y[respondent_mask]
                weights = rep_weights[respondent_mask]
                estimates[rep_idx] = _weighted_mean(values, weights) if estimand == "mean" else float(np.sum(weights * values))
            continue

        if estimator == "augmented":
            rep_estimate_run, _, _ = _run_augmented_estimation(
                inputs,
                params,
                base_weights_override=rep_weights,
                compute_variance=False,
            )
            estimates[rep_idx] = rep_estimate_run.point_estimate
        else:
            rep_weight_run = _run_weight_pipeline(inputs, params, base_weights_override=rep_weights)
            estimates[rep_idx] = rep_weight_run.final_mean if estimand == "mean" else float(np.sum(rep_weight_run.final_weights[rep_weight_run.respondent_mask] * inputs.y[rep_weight_run.respondent_mask]))

    full_estimate = auxiliary_builder["point_estimate"] if estimator == "augmented" and auxiliary_builder is not None else (run.final_mean if estimand == "mean" else float(np.sum(run.final_weights[run.respondent_mask] * inputs.y[run.respondent_mask])))
    variance = _replicate_variance(
        estimates,
        full_estimate=float(full_estimate),
        variance_method=variance_method,
        mse=bool(params.get("mse", True)),
    )
    control_adjustment_mean, slope = (0.0, [])
    if estimator == "augmented" and auxiliary_builder is not None:
        control_adjustment_mean, slope = _control_total_variance_adjustment(
            inputs.X_aux,
            np.asarray(auxiliary_builder["pseudo_outcome"], dtype=float),
            np.asarray(auxiliary_builder["analysis_weights"], dtype=float),
            inputs.control_vcov,
            ridge=ridge,
            denominator=float(np.sum(np.asarray(auxiliary_builder["analysis_weights"], dtype=float))),
        )
    else:
        control_adjustment_mean, slope = _control_total_variance_adjustment(
            inputs.X_aux[run.respondent_mask],
            inputs.y[run.respondent_mask],
            run.final_weights[run.respondent_mask],
            inputs.control_vcov,
            ridge=ridge,
            denominator=float(np.sum(run.final_weights[run.respondent_mask])),
        )
    if estimand == "total":
        scale = float(np.sum(auxiliary_builder["analysis_weights"])) ** 2 if estimator == "augmented" and auxiliary_builder is not None else float(np.sum(run.final_weights[run.respondent_mask])) ** 2
        variance += control_adjustment_mean * scale
        control_adjustment = control_adjustment_mean * scale
    else:
        variance += control_adjustment_mean
        control_adjustment = control_adjustment_mean
    diagnostics = {
        "replicate_backend": variance_method,
        "replicates_source": replicate_info["replicates_source"],
        "n_replicates_used": int(estimates.size),
        "replicate_weight_stage": replicate_stage,
        "replicate_mean_estimate": float(np.mean(estimates)),
    }
    return float(max(variance, 0.0)), float(np.sqrt(max(variance, 0.0))), diagnostics, estimates, float(control_adjustment), slope


def _build_sensitivity_payload(
    inputs: _AdaptiveInputs,
    params: Mapping[str, Any],
    run: _WeightRun,
    *,
    estimand: Literal["mean", "total"],
) -> dict[str, Any]:
    payload = {
        "phase_only_mean_estimate": run.phase_mean,
        "nonresponse_adjusted_mean_estimate": run.nr_mean,
        "final_mean_estimate": run.final_mean,
        "phase_only_effective_sample_size": _effective_sample_size(run.phase_weights[run.respondent_mask]),
        "final_effective_sample_size": _effective_sample_size(run.final_weights[run.respondent_mask]),
    }

    no_trim_params = dict(params)
    no_trim_params["trim_method"] = "none"
    no_trim_run = _run_weight_pipeline(inputs, no_trim_params)
    payload["no_trim_point_estimate"] = no_trim_run.final_mean if estimand == "mean" else float(
        np.sum(no_trim_run.final_weights[no_trim_run.respondent_mask] * inputs.y[no_trim_run.respondent_mask])
    )

    if inputs.paradata.shape[1] > 0 or inputs.actions.shape[1] > 0:
        aux_only_run = _run_weight_pipeline(inputs, params, feature_mode_override="aux_only")
        payload["alternate_propensity_aux_only_point_estimate"] = aux_only_run.final_mean if estimand == "mean" else float(
            np.sum(aux_only_run.final_weights[aux_only_run.respondent_mask] * inputs.y[aux_only_run.respondent_mask])
        )

    if inputs.control_totals.size > 0:
        current_method = str(params.get("calibration_method", "linear")).lower()
        alternate = "raking" if current_method == "linear" else "linear"
        try:
            alt_run = _run_weight_pipeline(inputs, params, calibration_method_override=alternate)
        except Exception as exc:  # pragma: no cover - diagnostic fallback
            payload[f"alternate_calibration_{alternate}_error"] = str(exc)
        else:
            payload[f"alternate_calibration_{alternate}_point_estimate"] = alt_run.final_mean if estimand == "mean" else float(
                np.sum(alt_run.final_weights[alt_run.respondent_mask] * inputs.y[alt_run.respondent_mask])
            )
    return payload


def _common_payload(
    inputs: _AdaptiveInputs,
    params: Mapping[str, Any],
    run: _WeightRun,
    estimate_run: _EstimateRun,
    *,
    x_names: Sequence[str],
    paradata_names: Sequence[str],
    action_names: Sequence[str],
) -> dict[str, Any]:
    response_rate = float(np.mean(inputs.response))
    clip_min = float(params.get("clip_min", 0.02))
    clip_max = float(params.get("clip_max", 0.98))
    overlap_share = float(np.mean((run.propensity <= clip_min + 1e-9) | (run.propensity >= clip_max - 1e-9)))
    respondent_mask = run.respondent_mask
    respondent_weights = run.final_weights[respondent_mask]
    sample_weight = run.phase_weights / max(float(np.mean(run.phase_weights)), 1e-12)

    r_indicator = _representativeness_indicator(run.propensity, sample_weight)
    partial_r = {
        "x_aux": _column_diagnostics(inputs.X_aux, x_names, propensity=run.propensity, response=inputs.response, sample_weight=sample_weight),
        "paradata": _column_diagnostics(inputs.paradata, paradata_names, propensity=run.propensity, response=inputs.response, sample_weight=sample_weight),
        "actions": _column_diagnostics(inputs.actions, action_names, propensity=run.propensity, response=inputs.response, sample_weight=sample_weight),
    }

    action_effects = _action_effect_diagnostics(
        inputs.actions,
        action_names,
        response=inputs.response,
        propensity=run.propensity,
        cost_vector=inputs.cost_vector,
    )
    mode_checks = _operational_differentials(
        inputs.paradata,
        paradata_names,
        response=inputs.response,
        weights=sample_weight,
        selected_indices=_int_tuple(params.get("mode_column_indices")),
    )
    interviewer_checks = _operational_differentials(
        inputs.paradata,
        paradata_names,
        response=inputs.response,
        weights=sample_weight,
        selected_indices=_int_tuple(params.get("interviewer_column_indices")),
    )

    weight_cv = float(np.std(respondent_weights) / max(np.mean(respondent_weights), 1e-12)) if respondent_weights.size else 0.0
    quality_metrics = {
        "response_rate": response_rate,
        "r_indicator": r_indicator,
        "effective_sample_size": _effective_sample_size(respondent_weights),
        "weight_cv": weight_cv,
        "overlap_share_at_clip_bounds": overlap_share,
        "calibration_max_abs_residual": float(run.calibration_status.get("max_abs_residual", 0.0)),
    }
    loss_value = float(np.sum(inputs.cost_vector)) + float(params.get("stop_lambda", 1.0)) * (1.0 - r_indicator) ** 2 + float(params.get("stop_gamma", 1.0)) * estimate_run.variance_estimate

    return {
        "estimand_type": str(params.get("estimand", "mean")).lower(),
        "point_estimate": estimate_run.point_estimate,
        "mean_estimate": estimate_run.mean_estimate,
        "total_estimate": estimate_run.total_estimate,
        "variance_estimate": estimate_run.variance_estimate,
        "standard_error": estimate_run.standard_error,
        "variance_method_used": estimate_run.variance_method_used,
        "confidence_level": float(params.get("confidence_level", 0.95)),
        "ci_lower": estimate_run.point_estimate - float(NormalDist().inv_cdf((1.0 + float(params.get("confidence_level", 0.95))) / 2.0)) * estimate_run.standard_error,
        "ci_upper": estimate_run.point_estimate + float(NormalDist().inv_cdf((1.0 + float(params.get("confidence_level", 0.95))) / 2.0)) * estimate_run.standard_error,
        "response_rate": response_rate,
        "propensity_scores": run.propensity.tolist(),
        "propensity_model_coefficients": run.propensity_coefficients.tolist(),
        "propensity_feature_names": list(run.feature_names),
        "base_weights": run.base_weights.tolist(),
        "phase_weights": run.phase_weights.tolist(),
        "nonresponse_adjusted_weights": run.nonresponse_weights.tolist(),
        "trimmed_weights": run.trimmed_weights.tolist(),
        "final_weights": run.final_weights.tolist(),
        "final_weights_summary": _weight_summary(respondent_weights),
        "calibration_status": run.calibration_status,
        "adaptive_status": {
            "n_sampled": int(inputs.n_obs),
            "n_phase1": int(inputs.n_obs),
            "n_respondents": int(np.sum(respondent_mask)),
            "n_nonrespondents": int(np.sum(~respondent_mask)),
            "n_followup": int(np.sum(np.abs(inputs.followup - 1.0) > 1e-12)),
            "n_followup_adjusted": int(np.sum(np.abs(inputs.followup - 1.0) > 1e-12)),
            "n_targeted": int(np.sum(np.any(inputs.actions > 0.5, axis=1))) if inputs.actions.shape[1] else 0,
            "assigned_actions_by_group": {
                name: int(np.sum(inputs.actions[:, idx] > 0.5))
                for idx, name in enumerate(action_names)
            },
            "representativeness_indicator": r_indicator,
        },
        "stop_status": {
            "stop_reason": str(params.get("stop_reason", "")) if bool(params.get("store_stop_reason", True)) else "",
            "require_prespecified_rules": bool(params.get("require_prespecified_rules", True)),
            "prespecified_rule_supplied": bool(str(params.get("decision_rule_id", ""))),
            "loss_value": loss_value,
            "quality_metrics_at_stop": quality_metrics,
            "cost_summary": {
                "total_cost": float(np.sum(inputs.cost_vector)),
                "mean_cost_per_case": float(np.mean(inputs.cost_vector)),
                "mean_cost_per_respondent": float(np.mean(inputs.cost_vector[respondent_mask])),
            },
        },
        "diagnostics": {
            "trim": run.trim_info,
            "r_indicator": r_indicator,
            "partial_r_indicators": partial_r,
            "overlap_share_at_clip_bounds": overlap_share,
            "min_propensity": float(np.min(run.propensity)),
            "max_propensity": float(np.max(run.propensity)),
            "clipping_fraction_low": float(np.mean(run.propensity <= clip_min + 1e-9)),
            "clipping_fraction_high": float(np.mean(run.propensity >= clip_max - 1e-9)),
            "action_effect_diagnostics": action_effects,
            "mode_differential_checks": mode_checks,
            "interviewer_differential_checks": interviewer_checks,
            "variance_diagnostics": estimate_run.variance_diagnostics,
            "control_total_variance_adjustment": estimate_run.control_total_variance_adjustment,
            "control_total_slope": estimate_run.control_total_slope,
        },
        "sensitivity": _build_sensitivity_payload(
            inputs,
            params,
            run,
            estimand=str(params.get("estimand", "mean")).lower(),
        ),
        "audit_refs": {
            "decision_rule_id": str(params.get("decision_rule_id", "")),
            "adaptation_log_id": str(params.get("adaptation_log_id", "")),
            "control_totals_version": str(params.get("control_totals_version", "")),
            "action_history_stored": bool(params.get("store_action_history", True)),
        },
    }


def _run_augmented_estimation(
    inputs: _AdaptiveInputs,
    params: Mapping[str, Any],
    *,
    base_weights_override: np.ndarray | None = None,
    compute_variance: bool = True,
) -> tuple[_EstimateRun, dict[str, Any], _WeightRun]:
    run = _run_weight_pipeline(inputs, params, base_weights_override=base_weights_override)
    feature_mode = str(params.get("propensity_feature_mode", "full")).lower()
    features, _, _, _ = _resolve_feature_block(inputs, params, mode=feature_mode)
    respondent_mask = run.respondent_mask
    ridge = float(params.get("outcome_ridge", params.get("ridge", 1e-6)))
    beta = _fit_weighted_linear(
        features[respondent_mask],
        inputs.y[respondent_mask],
        run.final_weights[respondent_mask],
        ridge=ridge,
    )
    m_hat = _predict_linear(features, beta)
    rho = np.clip(run.propensity, float(params.get("clip_min", 0.02)), float(params.get("clip_max", 0.98)))
    pseudo_outcome = m_hat.copy()
    pseudo_outcome[respondent_mask] = m_hat[respondent_mask] + (inputs.y[respondent_mask] - m_hat[respondent_mask]) / rho[respondent_mask]

    analysis_weights = run.phase_weights
    total_estimate = float(np.sum(analysis_weights * pseudo_outcome))
    greg_adjustment = 0.0
    if inputs.control_totals.size > 0 and bool(params.get("use_calibration_on_pseudo_outcome", True)):
        weighted_beta = _fit_weighted_linear(inputs.X_aux, pseudo_outcome, analysis_weights, ridge=ridge)[1:]
        t_ht_x = np.sum(analysis_weights[:, None] * inputs.X_aux, axis=0)
        greg_adjustment = float((inputs.control_totals - t_ht_x) @ weighted_beta)
        total_estimate += greg_adjustment

    mean_estimate = total_estimate / max(float(np.sum(analysis_weights)), 1e-12)
    estimand = str(params.get("estimand", "mean")).lower()
    point_estimate = mean_estimate if estimand == "mean" else total_estimate

    auxiliary = {
        "pseudo_outcome": pseudo_outcome,
        "analysis_weights": analysis_weights,
        "point_estimate": point_estimate,
    }
    if compute_variance:
        variance_estimate, standard_error, variance_diagnostics, replicate_estimates, control_adjustment, slope = _estimate_from_replicates(
            inputs,
            params,
            run,
            estimand=estimand,
            estimator="augmented",
            auxiliary_builder=auxiliary,
        )
    else:
        variance_estimate = 0.0
        standard_error = 0.0
        variance_diagnostics = {"variance_skipped": True}
        replicate_estimates = np.array([], dtype=float)
        control_adjustment = 0.0
        slope = []
    outcome_predictions_resp = m_hat[respondent_mask]
    ss_tot = float(np.sum(run.final_weights[respondent_mask] * (inputs.y[respondent_mask] - _weighted_mean(inputs.y[respondent_mask], run.final_weights[respondent_mask])) ** 2))
    ss_res = float(np.sum(run.final_weights[respondent_mask] * (inputs.y[respondent_mask] - outcome_predictions_resp) ** 2))
    weighted_r2 = 0.0 if ss_tot <= 1e-12 else max(0.0, 1.0 - ss_res / ss_tot)
    estimate_run = _EstimateRun(
        point_estimate=float(point_estimate),
        mean_estimate=float(mean_estimate),
        total_estimate=float(total_estimate),
        variance_estimate=float(variance_estimate),
        standard_error=float(standard_error),
        variance_method_used=str(variance_diagnostics.get("replicate_backend", "linearization" if "linearization_backend" in variance_diagnostics else "replicate")),
        variance_diagnostics=variance_diagnostics,
        replicate_estimates=replicate_estimates if replicate_estimates.size else None,
        control_total_variance_adjustment=float(control_adjustment),
        control_total_slope=slope,
        auxiliary={
            "outcome_model_coefficients": beta.tolist(),
            "weighted_r2": float(weighted_r2),
            "greg_adjustment": float(greg_adjustment),
            "calibrated_ipw_reference_estimate": float(run.final_mean if estimand == "mean" else np.sum(run.final_weights[respondent_mask] * inputs.y[respondent_mask])),
        },
    )
    return estimate_run, auxiliary, run


def _run_calibrated_estimation(
    inputs: _AdaptiveInputs,
    params: Mapping[str, Any],
    *,
    base_weights_override: np.ndarray | None = None,
) -> tuple[_EstimateRun, _WeightRun]:
    run = _run_weight_pipeline(inputs, params, base_weights_override=base_weights_override)
    estimand = str(params.get("estimand", "mean")).lower()
    respondent_mask = run.respondent_mask
    respondent_values = inputs.y[respondent_mask]
    respondent_weights = run.final_weights[respondent_mask]
    point_estimate, alternate_estimate, _, _ = _weighted_estimate(
        respondent_values,
        respondent_weights,
        estimand=estimand,
    )
    variance_estimate, standard_error, variance_diagnostics, replicate_estimates, control_adjustment, slope = _estimate_from_replicates(
        inputs,
        params,
        run,
        estimand=estimand,
        estimator="calibrated",
    )
    estimate_run = _EstimateRun(
        point_estimate=float(point_estimate),
        mean_estimate=float(point_estimate if estimand == "mean" else alternate_estimate),
        total_estimate=float(point_estimate if estimand == "total" else alternate_estimate),
        variance_estimate=float(variance_estimate),
        standard_error=float(standard_error),
        variance_method_used=str(variance_diagnostics.get("replicate_backend", variance_diagnostics.get("linearization_backend", "linearization"))),
        variance_diagnostics=variance_diagnostics,
        replicate_estimates=replicate_estimates if replicate_estimates.size else None,
        control_total_variance_adjustment=float(control_adjustment),
        control_total_slope=slope,
        auxiliary={},
    )
    return estimate_run, run


def _build_calibrated_payload(inputs: _AdaptiveInputs, params: Mapping[str, Any]) -> dict[str, Any]:
    run_estimate, run = _run_calibrated_estimation(inputs, params)
    _, _, paradata_names, action_names = _resolve_feature_block(
        inputs,
        params,
        mode=str(params.get("propensity_feature_mode", "full")).lower(),
    )
    x_names = _feature_names(inputs.X_aux.shape[1], prefix="x", provided=_string_tuple(params.get("x_feature_names")))
    return {
        "result": _common_payload(
            inputs,
            params,
            run,
            run_estimate,
            x_names=x_names,
            paradata_names=paradata_names,
            action_names=action_names,
        )
    }


def _build_augmented_payload(inputs: _AdaptiveInputs, params: Mapping[str, Any]) -> dict[str, Any]:
    estimate_run, auxiliary, run = _run_augmented_estimation(inputs, params)
    _, _, paradata_names, action_names = _resolve_feature_block(
        inputs,
        params,
        mode=str(params.get("propensity_feature_mode", "full")).lower(),
    )
    x_names = _feature_names(inputs.X_aux.shape[1], prefix="x", provided=_string_tuple(params.get("x_feature_names")))
    payload = _common_payload(
        inputs,
        params,
        run,
        estimate_run,
        x_names=x_names,
        paradata_names=paradata_names,
        action_names=action_names,
    )
    payload["augmentation_status"] = {
        "outcome_model": str(params.get("outcome_model", "linear")).lower(),
        "outcome_model_coefficients": estimate_run.auxiliary["outcome_model_coefficients"],
        "weighted_r2": estimate_run.auxiliary["weighted_r2"],
        "greg_adjustment": estimate_run.auxiliary["greg_adjustment"],
        "calibrated_ipw_reference_estimate": estimate_run.auxiliary["calibrated_ipw_reference_estimate"],
    }
    return {"result": payload}


@foundry_method(
    namespace="survey.adaptive",
    version="1.0.0",
    tags={"survey", "adaptive", "responsive", "ipw", "calibration"},
)
class AdaptiveCalibratedIPWEstimator:
    """Adaptive / responsive survey estimator with calibrated IPW weights."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="adaptive_calibrated_ipw",
        namespace="",
        version="0.0.0",
        input_slots=_adaptive_input_slots(),
        output_slots=_result_slot(),
        parameters=_common_parameters(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Adaptive / responsive survey estimator that composes design weights, phase-specific follow-up, response-propensity adjustment, calibration, and replicate-aware variance.",
        tags=frozenset({"survey", "adaptive", "responsive", "ipw", "calibration", "nonresponse"}),
        citations=(
            "Horvitz, D. & Thompson, D. (1952). A generalization of sampling without replacement from a finite universe. Journal of the American Statistical Association, 47(260), 663-685.",
            "Hansen, M. H. & Hurwitz, W. N. (1946). The problem of non-response in sample surveys. Journal of the American Statistical Association, 41(236), 517-529.",
            "Deville, J. & Sarndal, C. (1992). Calibration estimators in survey sampling. Journal of the American Statistical Association, 87(418), 376-382.",
        ),
        equations={
            "final_weight": "w_i = (1 / pi_i^(0)) * (1 / q_i) * (1 / rho_hat_i) * c_i",
            "adaptive_estimator": "T_hat = sum_{i in respondents} w_i y_i",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Adaptive or responsive survey fieldwork where follow-up actions, paradata, and response propensities must be replayed into analysis weights and uncertainty.",
        when_not_to_use="Static probability samples with fully known inclusion probabilities and no adaptive follow-up; use simpler HT or standard calibration estimators instead.",
        typical_min_obs=100,
        output_interpretation="Returns adaptive point estimates, replicate-aware or linearized uncertainty, final weights, calibration residuals, action diagnostics, and auditable stop metadata.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        inputs = _coerce_inputs(state)
        return _build_calibrated_payload(inputs, params)


@foundry_method(
    namespace="survey.adaptive",
    version="1.0.0",
    tags={"survey", "adaptive", "responsive", "aipw", "doubly-robust"},
)
class AdaptiveAugmentedEstimator:
    """Adaptive / responsive survey estimator with outcome augmentation."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="adaptive_augmented",
        namespace="",
        version="0.0.0",
        input_slots=_adaptive_input_slots(),
        output_slots=_result_slot(),
        parameters=_common_parameters()
        + (
            ParameterSpec(name="outcome_model", default="linear"),
            ParameterSpec(name="outcome_ridge", default=1e-6, bounds=(0.0, None)),
            ParameterSpec(name="use_calibration_on_pseudo_outcome", default=True),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Adaptive / responsive survey estimator with AIPW/GREG-style augmentation on top of phase-aware response weighting.",
        tags=frozenset({"survey", "adaptive", "responsive", "aipw", "doubly-robust", "nonresponse"}),
        citations=(
            "Robins, J. M., Rotnitzky, A., & Zhao, L. P. (1994). Estimation of regression coefficients when some regressors are not always observed. Journal of the American Statistical Association, 89(427), 846-866.",
            "Särndal, C. E., Swensson, B., & Wretman, J. (1992). Model Assisted Survey Sampling. Springer.",
        ),
        equations={
            "augmented_estimator": "T_hat = sum_i d_i [m_hat_i + R_i / rho_hat_i * (y_i - m_hat_i)]",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Sensitivity analysis or production settings where adaptive survey weighting should be paired with an outcome model for added robustness.",
        when_not_to_use="When no defensible outcome covariates/history exist or the augmentation model would be purely extrapolative.",
        typical_min_obs=150,
        output_interpretation="Returns an adaptive augmented estimate plus the calibrated IPW reference, outcome-model diagnostics, and the same audit payload as the base adaptive estimator.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        inputs = _coerce_inputs(state)
        if str(params.get("outcome_model", "linear")).lower() != "linear":
            raise ValueError("Phase 1 adaptive augmentation currently supports outcome_model='linear' only")
        return _build_augmented_payload(inputs, params)


AdaptiveResponsiveSurveyEstimator = AdaptiveCalibratedIPWEstimator


__all__ = [
    "AdaptiveAugmentedEstimator",
    "AdaptiveCalibratedIPWEstimator",
    "AdaptiveResponsiveSurveyEstimator",
]
