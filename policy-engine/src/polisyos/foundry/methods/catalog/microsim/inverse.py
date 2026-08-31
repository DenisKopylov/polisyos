"""Inverse behavioral calibration baseline for Track 11 microsimulation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.calibration.identifiability import (
    IdentifiabilityReport,
    IdentifiabilityStatus,
    ParamIdentifiability,
)
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
from polisyos.foundry.methods.catalog._payloads import extract_model_payload
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.ir.analytics.microsim_calibration import (
    build_microsim_calibration_report,
    persist_microsim_calibration_report,
)

from .protocols import (
    InverseBehavioralCalibrationResult,
    InverseBehavioralIdentifiedSet,
    SurveyMicroData,
)

_EPS = 1e-12


@dataclass(frozen=True)
class _PreparedCalibrationData:
    observed: np.ndarray
    policy_shifter: np.ndarray
    weights: np.ndarray
    upper_bound: np.ndarray | None
    diagnostics: dict[str, Any]


def _survey_payload(state: object) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=SurveyMicroData,
        nested_keys=("survey_micro_data",),
    )


def _as_payload(state: object) -> dict[str, Any]:
    if isinstance(state, SurveyMicroData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        return dict(state)
    raise TypeError("inverse_behavioral_calibration expects mapping or SurveyMicroData input")


def _resolve_value(state: Mapping[str, Any], key: str) -> object | None:
    if key in state and state.get(key) is not None:
        return state.get(key)
    metadata = state.get("metadata")
    if isinstance(metadata, Mapping):
        return metadata.get(key)
    return None


def _mapping_config(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _nested_config(
    payload: Mapping[str, Any],
    params: Mapping[str, Any],
    key: str,
) -> dict[str, Any]:
    """Resolve proposed Track 11 config blocks from params, payload, or metadata."""

    resolved: dict[str, Any] = {}
    metadata = payload.get("metadata")
    if isinstance(metadata, Mapping):
        resolved.update(_mapping_config(metadata.get(key)))
    resolved.update(_mapping_config(payload.get(key)))
    resolved.update(_mapping_config(params.get(key)))
    return resolved


def _config_value(
    params: Mapping[str, Any],
    config: Mapping[str, Any],
    key: str,
    default: object | None = None,
) -> object | None:
    if key in params and params.get(key) is not None:
        return params.get(key)
    if key in config and config.get(key) is not None:
        return config.get(key)
    return default


def _bool_value(value: object | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _float_tuple(value: object | None, *, default: tuple[float, ...]) -> tuple[float, ...]:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return (float(value),)
    try:
        resolved = tuple(float(item) for item in value)
    except TypeError:
        return default
    return resolved or default


def _encode_numeric(values: object) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim == 2:
        if np.issubdtype(array.dtype, np.number):
            return array.astype(float)
        columns = [_encode_numeric(array[:, idx]).reshape(-1, 1) for idx in range(array.shape[1])]
        return np.column_stack(columns)
    if np.issubdtype(array.dtype, np.number):
        return array.astype(float)
    _, inverse = np.unique(array.astype(str), return_inverse=True)
    return inverse.astype(float)


def _resolve_numeric_vector(
    state: Mapping[str, Any],
    *,
    key: str,
    n_obs: int | None = None,
    allow_scalar: bool = False,
) -> np.ndarray:
    value = _resolve_value(state, key)
    if value is None:
        raise ValueError(f"missing required field '{key}'")
    array = np.asarray(_encode_numeric(value), dtype=float)
    if array.ndim == 0:
        if not allow_scalar or n_obs is None:
            raise ValueError(f"{key} must be a 1D array")
        return np.full(n_obs, float(array.item()), dtype=float)
    if array.ndim != 1:
        raise ValueError(f"{key} must be a 1D array")
    if n_obs is not None and array.shape[0] != n_obs:
        raise ValueError(f"{key} length must match observation count")
    return array


def _resolve_numeric_matrix_or_vector(
    state: Mapping[str, Any],
    *,
    key: str,
    n_obs: int,
) -> np.ndarray:
    value = _resolve_value(state, key)
    if value is None:
        raise ValueError(f"missing required field '{key}'")
    array = np.asarray(_encode_numeric(value), dtype=float)
    if array.ndim == 0:
        return np.full(n_obs, float(array.item()), dtype=float)
    if array.ndim == 1:
        if array.shape[0] != n_obs:
            raise ValueError(f"{key} length must match observation count")
        return array
    if array.ndim == 2 and array.shape[0] == n_obs:
        return array
    raise ValueError(f"{key} must be scalar, 1D, or 2D with row count matching observation count")


def _resolve_optional_numeric_vector(
    state: Mapping[str, Any],
    *,
    key: str,
    n_obs: int,
) -> np.ndarray | None:
    value = _resolve_value(state, key)
    if value is None:
        return None
    array = np.asarray(_encode_numeric(value), dtype=float)
    if array.ndim == 0:
        return np.full(n_obs, float(array.item()), dtype=float)
    if array.ndim != 1 or array.shape[0] != n_obs:
        raise ValueError(f"{key} must be scalar or a 1D array matching observation count")
    return array


def _policy_shifter_score(raw: np.ndarray, *, column: int | None = None) -> tuple[np.ndarray, str]:
    array = np.asarray(raw, dtype=float)
    if array.ndim == 1:
        return array, "vector"
    if array.ndim != 2:
        raise ValueError("policy shifter must be one- or two-dimensional")
    if column is not None:
        if column < 0 or column >= array.shape[1]:
            raise ValueError("policy_shifter_column is out of bounds")
        return np.asarray(array[:, column], dtype=float), f"column_{column}"
    centered = array - np.nanmean(array, axis=0, keepdims=True)
    centered = np.nan_to_num(centered, nan=0.0)
    if not np.any(np.abs(centered) > 0.0):
        return np.asarray(np.mean(array, axis=1), dtype=float), "column_mean"
    try:
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        return np.asarray(centered @ vt[0], dtype=float), "svd_pc1"
    except np.linalg.LinAlgError:
        return np.asarray(np.mean(centered, axis=1), dtype=float), "column_mean_fallback"


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(values * weights) / max(np.sum(weights), _EPS))


def _weighted_var(values: np.ndarray, weights: np.ndarray) -> float:
    mean = _weighted_mean(values, weights)
    return float(np.sum(weights * np.square(values - mean)) / max(np.sum(weights), _EPS))


def _weighted_corr(x: np.ndarray, y: np.ndarray, weights: np.ndarray) -> float | None:
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(weights) & (weights > 0.0)
    if int(np.sum(mask)) < 2:
        return None
    x_masked = x[mask]
    y_masked = y[mask]
    w_masked = weights[mask]
    x_centered = x_masked - _weighted_mean(x_masked, w_masked)
    y_centered = y_masked - _weighted_mean(y_masked, w_masked)
    denominator = math.sqrt(
        max(float(np.sum(w_masked * np.square(x_centered))), _EPS)
        * max(float(np.sum(w_masked * np.square(y_centered))), _EPS)
    )
    if denominator <= 0.0:
        return None
    return float(np.sum(w_masked * x_centered * y_centered) / denominator)


def _effective_sample_size(weights: np.ndarray) -> float:
    numerator = float(np.sum(weights) ** 2)
    denominator = float(np.sum(np.square(weights)))
    return numerator / max(denominator, _EPS)


def _detect_regime(payload: Mapping[str, Any], n_obs: int) -> str:
    household_ids = _resolve_optional_numeric_vector(payload, key="household_ids", n_obs=n_obs)
    period_id = _resolve_optional_numeric_vector(payload, key="period_id", n_obs=n_obs)
    if period_id is None:
        return "cross_section"
    if household_ids is None:
        return "repeated_cross_section"
    _, counts = np.unique(household_ids.astype(str), return_counts=True)
    return "panel" if np.any(counts > 1) else "repeated_cross_section"


def _group_key_column(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values)
    if np.issubdtype(array.dtype, np.number):
        return np.asarray([f"{float(item):.12g}" for item in array], dtype=object)
    return array.astype(str)


def _weighted_cell_aggregate(
    *,
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    upper_bound: np.ndarray | None,
    grouping_columns: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, dict[str, Any]]:
    key_strings = np.asarray(
        [
            "|".join(row)
            for row in zip(*[_group_key_column(col) for col in grouping_columns], strict=False)
        ],
        dtype=object,
    )
    unique_keys, inverse, counts = np.unique(key_strings, return_inverse=True, return_counts=True)
    if unique_keys.shape[0] == observed.shape[0] or int(np.max(counts)) <= 1:
        return (
            observed,
            policy_shifter,
            weights,
            upper_bound,
            {
                "aggregation_strategy": "raw",
                "n_cells": int(observed.shape[0]),
                "min_cell_size": 1,
                "max_cell_size": 1,
            },
        )

    n_cells = unique_keys.shape[0]
    obs_cells = np.zeros(n_cells, dtype=float)
    shifter_cells = np.zeros(n_cells, dtype=float)
    weight_cells = np.zeros(n_cells, dtype=float)
    upper_cells = None if upper_bound is None else np.zeros(n_cells, dtype=float)
    for cell_idx in range(n_cells):
        mask = inverse == cell_idx
        cell_weights = weights[mask]
        weight_sum = max(float(np.sum(cell_weights)), _EPS)
        weight_cells[cell_idx] = weight_sum
        obs_cells[cell_idx] = float(np.sum(observed[mask] * cell_weights) / weight_sum)
        shifter_cells[cell_idx] = float(np.sum(policy_shifter[mask] * cell_weights) / weight_sum)
        if upper_cells is not None and upper_bound is not None:
            upper_cells[cell_idx] = float(np.sum(upper_bound[mask] * cell_weights) / weight_sum)

    return (
        obs_cells,
        shifter_cells,
        weight_cells,
        upper_cells,
        {
            "aggregation_strategy": "weighted_cells",
            "n_cells": int(n_cells),
            "min_cell_size": int(np.min(counts)),
            "max_cell_size": int(np.max(counts)),
        },
    )


def _aggregate_or_smooth(
    payload: Mapping[str, Any],
    *,
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    upper_bound: np.ndarray | None,
    regime: str,
    estimator_config: Mapping[str, Any],
    params: Mapping[str, Any],
) -> _PreparedCalibrationData:
    diagnostics: dict[str, Any] = {
        "denoising_used": False,
        "repeat_measure_key": None,
        "aggregation_fields": [],
        "aggregation_strategy": "raw",
        "n_cells": int(observed.shape[0]),
        "min_cell_size": 1,
        "max_cell_size": 1,
    }

    fit_observed = np.asarray(observed, dtype=float)
    repeat_key = str(
        _config_value(params, estimator_config, "repeat_measure_key", "income_repeat_measure")
    )
    repeat_measure = _resolve_optional_numeric_vector(
        payload, key=repeat_key, n_obs=observed.shape[0]
    )
    if repeat_measure is not None and np.all(np.isfinite(repeat_measure)):
        repeat_blend = float(_config_value(params, estimator_config, "repeat_blend", 0.5))
        repeat_blend = float(np.clip(repeat_blend, 0.0, 1.0))
        fit_observed = (1.0 - repeat_blend) * fit_observed + repeat_blend * repeat_measure
        diagnostics.update(
            {
                "denoising_used": True,
                "repeat_measure_key": repeat_key,
                "repeat_blend": repeat_blend,
            }
        )

    aggregation_mode = (
        str(_config_value(params, estimator_config, "aggregation", "auto")).strip().lower()
    )
    grouping_columns: list[np.ndarray] = []
    grouping_fields: list[str] = []
    if aggregation_mode not in {"none", "raw", "off"} and regime in {
        "repeated_cross_section",
        "panel",
    }:
        for key in ("policy_id", "reform_id", "period_id", "cohort_id", "region_id"):
            column = _resolve_optional_numeric_vector(payload, key=key, n_obs=observed.shape[0])
            if column is not None:
                grouping_columns.append(column)
                grouping_fields.append(key)
        if grouping_columns:
            grouping_columns.append(np.round(policy_shifter, 10))
            grouping_fields.append("policy_shifter")
            if upper_bound is not None:
                grouping_columns.append(np.round(upper_bound, 10))
                grouping_fields.append("upper_bound")

    if grouping_columns:
        fit_observed, fit_shifter, fit_weights, fit_upper, agg_diag = _weighted_cell_aggregate(
            observed=fit_observed,
            policy_shifter=policy_shifter,
            weights=weights,
            upper_bound=upper_bound,
            grouping_columns=grouping_columns,
        )
        diagnostics.update(agg_diag)
        diagnostics["aggregation_fields"] = grouping_fields
        return _PreparedCalibrationData(
            observed=fit_observed,
            policy_shifter=fit_shifter,
            weights=fit_weights,
            upper_bound=fit_upper,
            diagnostics=diagnostics,
        )

    return _PreparedCalibrationData(
        observed=fit_observed,
        policy_shifter=policy_shifter,
        weights=weights,
        upper_bound=upper_bound,
        diagnostics=diagnostics,
    )


def _predict_choice(
    policy_shifter: np.ndarray,
    curvature: float,
    *,
    lower_bound: float,
    upper_bound: np.ndarray | None,
) -> np.ndarray:
    candidate = policy_shifter / max(float(curvature), _EPS)
    predicted = np.maximum(candidate, float(lower_bound))
    if upper_bound is not None:
        predicted = np.minimum(predicted, upper_bound)
    return np.asarray(predicted, dtype=float)


def _weighted_mse(observed: np.ndarray, predicted: np.ndarray, weights: np.ndarray) -> float:
    residual = observed - predicted
    return float(np.sum(weights * np.square(residual)) / max(np.sum(weights), _EPS))


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0.0)
    if int(np.sum(mask)) == 0:
        return float("nan")
    values_masked = values[mask]
    weights_masked = weights[mask]
    order = np.argsort(values_masked)
    values_sorted = values_masked[order]
    weights_sorted = weights_masked[order]
    cumulative = np.cumsum(weights_sorted)
    cutoff = float(quantile) * float(cumulative[-1])
    return float(
        values_sorted[
            min(int(np.searchsorted(cumulative, cutoff, side="left")), values_sorted.size - 1)
        ]
    )


def _kkt_violation(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    curvature: float,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    tolerance: float,
) -> float:
    gradient = float(curvature) * observed - policy_shifter
    lower_mask, interior_mask, upper_mask = _active_masks(
        observed,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        tolerance=tolerance,
    )
    violation = np.zeros_like(observed, dtype=float)
    violation[interior_mask] = np.square(gradient[interior_mask])
    violation[lower_mask] = np.square(np.minimum(gradient[lower_mask], 0.0))
    violation[upper_mask] = np.square(np.maximum(gradient[upper_mask], 0.0))
    feasible = _feasibility_violation(
        observed,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )
    return _weighted_mean(violation + np.square(feasible), weights)


def _smoothed_kkt_loss(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    curvature: float,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    tolerance: float,
    smoothing: float,
    kkt_weight: float,
) -> float:
    if not np.isfinite(curvature) or curvature <= _EPS:
        return float("inf")
    predicted = _predict_choice(
        policy_shifter,
        curvature,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )
    mse = _weighted_mse(observed, predicted, weights)
    kkt = _kkt_violation(
        observed,
        policy_shifter,
        weights,
        curvature=curvature,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        tolerance=max(tolerance, smoothing),
    )
    return float(mse + float(kkt_weight) * kkt)


def _active_masks(
    observed: np.ndarray,
    *,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    tolerance: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lower_mask = observed <= float(lower_bound) + float(tolerance)
    upper_mask = np.zeros(observed.shape[0], dtype=bool)
    if upper_bound is not None:
        upper_mask = observed >= upper_bound - float(tolerance)
    interior_mask = ~(lower_mask | upper_mask)
    return lower_mask, interior_mask, upper_mask


def _feasibility_violation(
    observed: np.ndarray,
    *,
    lower_bound: float,
    upper_bound: np.ndarray | None,
) -> np.ndarray:
    below = np.maximum(float(lower_bound) - observed, 0.0)
    above = np.zeros_like(observed, dtype=float)
    if upper_bound is not None:
        above = np.maximum(observed - upper_bound, 0.0)
    return below + above


def _analytic_curvature_estimate(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    tolerance: float,
) -> tuple[float, np.ndarray] | None:
    _, interior_mask, _ = _active_masks(
        observed,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        tolerance=tolerance,
    )
    interior_mask &= (
        np.isfinite(observed) & np.isfinite(policy_shifter) & np.isfinite(weights) & (weights > 0.0)
    )
    interior_mask &= observed > float(lower_bound) + float(tolerance)
    if int(np.sum(interior_mask)) < 3:
        return None
    numerator = float(
        np.sum(weights[interior_mask] * policy_shifter[interior_mask] * observed[interior_mask])
    )
    denominator = float(np.sum(weights[interior_mask] * np.square(observed[interior_mask])))
    if denominator <= _EPS:
        return None
    curvature = numerator / denominator
    if not np.isfinite(curvature) or curvature <= _EPS:
        return None
    return float(curvature), interior_mask


def _initial_curvature_guesses(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    tolerance: float,
    multi_start: int,
) -> list[float]:
    guesses: list[float] = []
    point = _analytic_curvature_estimate(
        observed,
        policy_shifter,
        weights,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        tolerance=tolerance,
    )
    if point is not None:
        guesses.append(float(point[0]))

    ratio_mask = (
        np.isfinite(observed) & np.isfinite(policy_shifter) & (observed > lower_bound + tolerance)
    )
    ratios = policy_shifter[ratio_mask] / np.maximum(observed[ratio_mask], tolerance)
    ratios = ratios[np.isfinite(ratios) & (ratios > tolerance)]
    if ratios.size:
        for quantile in np.linspace(0.1, 0.9, min(max(multi_start, 5), 11)):
            guesses.append(float(np.quantile(ratios, quantile)))
    if not guesses:
        scale = max(float(np.std(policy_shifter)), tolerance) / max(
            float(np.std(observed)), tolerance
        )
        guesses.append(float(max(scale, tolerance)))

    base_values = [
        max(float(item), tolerance) for item in guesses if np.isfinite(item) and item > 0.0
    ]
    expanded: list[float] = []
    for base in base_values:
        for multiplier in (0.25, 0.5, 1.0, 2.0, 4.0):
            expanded.append(float(max(base * multiplier, tolerance)))
    unique = sorted({round(item, 12) for item in expanded if np.isfinite(item) and item > 0.0})
    return [float(item) for item in unique[: max(multi_start, 1)]]


def _solve_smoothed_kkt_gmm(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    tolerance: float,
    multi_start: int,
    smoothing_path: tuple[float, ...],
    kkt_weight: float,
) -> tuple[float, float] | None:
    starts = _initial_curvature_guesses(
        observed,
        policy_shifter,
        weights,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        tolerance=tolerance,
        multi_start=multi_start,
    )
    if not starts:
        return None
    best: tuple[float, float] | None = None
    for start in starts:
        current = float(max(start, tolerance))
        for smoothing in smoothing_path:
            span = np.linspace(-1.25, 1.25, max(17, min(61, 2 * max(multi_start, 8) + 1)))
            grid = np.unique(np.maximum(current * np.exp(span), tolerance))
            losses = [
                _smoothed_kkt_loss(
                    observed,
                    policy_shifter,
                    weights,
                    curvature=float(candidate),
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    tolerance=tolerance,
                    smoothing=float(smoothing),
                    kkt_weight=kkt_weight,
                )
                for candidate in grid
            ]
            current = float(grid[int(np.argmin(losses))])
        loss = _smoothed_kkt_loss(
            observed,
            policy_shifter,
            weights,
            curvature=current,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            tolerance=tolerance,
            smoothing=float(smoothing_path[-1]),
            kkt_weight=kkt_weight,
        )
        if best is None or loss < best[1]:
            best = (float(current), float(loss))
    return best


def _bounds_only_curvature_interval(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    *,
    upper_bound: np.ndarray,
    lower_bound: float,
    tolerance: float,
) -> tuple[float, float] | None:
    _, _, upper_mask = _active_masks(
        observed,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        tolerance=tolerance,
    )
    candidate_mask = (
        upper_mask
        & np.isfinite(policy_shifter)
        & np.isfinite(upper_bound)
        & (upper_bound > tolerance)
    )
    if int(np.sum(candidate_mask)) == 0:
        return None
    upper_candidates = policy_shifter[candidate_mask] / np.maximum(
        upper_bound[candidate_mask], tolerance
    )
    upper_candidates = upper_candidates[
        np.isfinite(upper_candidates) & (upper_candidates > tolerance)
    ]
    if upper_candidates.size == 0:
        return None
    return float(tolerance), float(np.min(upper_candidates))


def _bootstrap_draws(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    bootstrap_reps: int,
    tolerance: float,
    rng: np.random.Generator,
) -> tuple[list[dict[str, float]], float | None]:
    if bootstrap_reps <= 0 or observed.shape[0] < 4:
        return [], None
    draws: list[dict[str, float]] = []
    active_shares: list[np.ndarray] = []
    for _ in range(bootstrap_reps):
        sample_idx = rng.integers(0, observed.shape[0], size=observed.shape[0])
        obs_b = observed[sample_idx]
        shifter_b = policy_shifter[sample_idx]
        weights_b = weights[sample_idx]
        upper_b = None if upper_bound is None else upper_bound[sample_idx]
        point = _analytic_curvature_estimate(
            obs_b,
            shifter_b,
            weights_b,
            lower_bound=lower_bound,
            upper_bound=upper_b,
            tolerance=tolerance,
        )
        if point is not None:
            curvature_b, _ = point
            draw = {"curvature": float(curvature_b)}
        elif upper_b is not None:
            bounds = _bounds_only_curvature_interval(
                obs_b,
                shifter_b,
                upper_bound=upper_b,
                lower_bound=lower_bound,
                tolerance=tolerance,
            )
            if bounds is None:
                continue
            draw = {"curvature_upper_bound": float(bounds[1])}
        else:
            continue
        lower_mask_b, interior_mask_b, upper_mask_b = _active_masks(
            obs_b,
            lower_bound=lower_bound,
            upper_bound=upper_b,
            tolerance=tolerance,
        )
        active_shares.append(
            np.array(
                [
                    float(np.mean(lower_mask_b)),
                    float(np.mean(interior_mask_b)),
                    float(np.mean(upper_mask_b)),
                ],
                dtype=float,
            )
        )
        draws.append(draw)
    if not active_shares:
        return draws, None
    stability = float(
        np.clip(1.0 - float(np.mean(np.std(np.vstack(active_shares), axis=0))), 0.0, 1.0)
    )
    return draws, stability


def _bootstrap_intervals(draws: list[dict[str, float]]) -> dict[str, tuple[float, float]]:
    if not draws:
        return {}
    keys = sorted({key for draw in draws for key in draw})
    intervals: dict[str, tuple[float, float]] = {}
    for key in keys:
        values = np.asarray([draw[key] for draw in draws if key in draw], dtype=float)
        if values.size == 0:
            continue
        intervals[key] = (
            float(np.quantile(values, 0.05)),
            float(np.quantile(values, 0.95)),
        )
    return intervals


def _numeric_jacobian(
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    curvature: float,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    estimated_upper_bound: float | None,
    step_scale: float = 1e-5,
) -> tuple[int, float, np.ndarray]:
    base_prediction = _predict_choice(
        policy_shifter,
        curvature,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )
    columns: list[np.ndarray] = []

    curvature_step = max(abs(curvature) * step_scale, 1e-6)
    pred_plus = _predict_choice(
        policy_shifter,
        curvature + curvature_step,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )
    pred_minus = _predict_choice(
        policy_shifter,
        max(curvature - curvature_step, curvature_step),
        lower_bound=lower_bound,
        upper_bound=upper_bound,
    )
    columns.append((pred_plus - pred_minus) / (2.0 * curvature_step))

    if estimated_upper_bound is not None:
        upper_step = max(abs(estimated_upper_bound) * step_scale, 1e-6)
        upper_plus = np.full(
            policy_shifter.shape[0], estimated_upper_bound + upper_step, dtype=float
        )
        upper_minus = np.full(
            policy_shifter.shape[0],
            max(estimated_upper_bound - upper_step, lower_bound + upper_step),
            dtype=float,
        )
        pred_upper_plus = _predict_choice(
            policy_shifter,
            curvature,
            lower_bound=lower_bound,
            upper_bound=upper_plus,
        )
        pred_upper_minus = _predict_choice(
            policy_shifter,
            curvature,
            lower_bound=lower_bound,
            upper_bound=upper_minus,
        )
        columns.append((pred_upper_plus - pred_upper_minus) / (2.0 * upper_step))

    if not columns:
        return 0, float("inf"), base_prediction

    jacobian = np.column_stack(columns)
    weighted_jacobian = jacobian * np.sqrt(np.clip(weights, 0.0, None))[:, None]
    if not np.any(np.abs(weighted_jacobian) > 0.0):
        return 0, float("inf"), base_prediction
    rank = int(np.linalg.matrix_rank(weighted_jacobian, tol=1e-8))
    gram = weighted_jacobian.T @ weighted_jacobian
    try:
        condition_number = float(np.linalg.cond(gram))
    except np.linalg.LinAlgError:
        condition_number = float("inf")
    return rank, condition_number, base_prediction


def _build_identifiability_report(
    *,
    param_names: tuple[str, ...],
    jacobian_rank: int,
    condition_number: float,
    bootstrap_draws: list[dict[str, float]],
    identified_object: str,
) -> IdentifiabilityReport:
    draws_by_name: dict[str, np.ndarray] = {}
    for name in param_names:
        values = [draw[name] for draw in bootstrap_draws if name in draw]
        draws_by_name[name] = (
            np.asarray(values, dtype=float) if values else np.asarray([], dtype=float)
        )

    params: list[ParamIdentifiability] = []
    n_identified = 0
    n_sloppy = 0
    n_non_identified = 0
    for index, name in enumerate(param_names):
        draws = draws_by_name[name]
        std = float(np.std(draws, ddof=1)) if draws.size >= 2 else float("inf")
        if identified_object in {"not_identified", "manual_override_required"}:
            status = IdentifiabilityStatus.NON_IDENTIFIED
        elif identified_object == "bounds_only":
            status = IdentifiabilityStatus.SLOPPY
        elif jacobian_rank <= index:
            status = IdentifiabilityStatus.NON_IDENTIFIED
        elif (
            not math.isfinite(condition_number)
            or condition_number > 1e6
            or (math.isfinite(std) and std > 0.5)
        ):
            status = IdentifiabilityStatus.SLOPPY
        else:
            status = IdentifiabilityStatus.IDENTIFIED
        if status == IdentifiabilityStatus.IDENTIFIED:
            n_identified += 1
        elif status == IdentifiabilityStatus.SLOPPY:
            n_sloppy += 1
        else:
            n_non_identified += 1
        params.append(
            ParamIdentifiability(
                name=name,
                status=status,
                eigenvalue=float(max(jacobian_rank - index, 0)),
                std=std,
            )
        )
    return IdentifiabilityReport(
        params=params,
        n_identified=n_identified,
        n_sloppy=n_sloppy,
        n_non_identified=n_non_identified,
        effective_dimension=int(jacobian_rank),
    )


def _fit_known_upper_bound(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    tolerance: float,
) -> tuple[str, float | None, np.ndarray | None, InverseBehavioralIdentifiedSet | None]:
    point = _analytic_curvature_estimate(
        observed,
        policy_shifter,
        weights,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        tolerance=tolerance,
    )
    if point is not None:
        curvature, _ = point
        return "point", float(curvature), upper_bound, None
    if upper_bound is not None:
        bounds = _bounds_only_curvature_interval(
            observed,
            policy_shifter,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            tolerance=tolerance,
        )
        if bounds is not None:
            lower, upper = bounds
            identified_set = InverseBehavioralIdentifiedSet(
                parameter_bounds={"curvature": (float(lower), float(upper))},
                representative_point={"curvature": float(upper)},
                warnings=("upper-bound support only; returning set-valued calibration",),
            )
            return "bounds", float(upper), upper_bound, identified_set
    return "blocked", None, upper_bound, None


def _fit_with_estimated_upper_bound(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    lower_bound: float,
    tolerance: float,
    grid_size: int,
) -> tuple[float, float] | None:
    finite_observed = observed[np.isfinite(observed)]
    if finite_observed.size < 4:
        return None
    candidate_grid = np.unique(
        np.quantile(
            finite_observed,
            np.linspace(0.65, 0.995, max(grid_size, 8)),
        )
    )
    candidate_grid = candidate_grid[candidate_grid > lower_bound + tolerance]
    best: tuple[float, float, float] | None = None
    for candidate_upper in candidate_grid:
        upper_bound = np.full(observed.shape[0], float(candidate_upper), dtype=float)
        point = _analytic_curvature_estimate(
            observed,
            policy_shifter,
            weights,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            tolerance=tolerance,
        )
        if point is None:
            continue
        curvature, _ = point
        predicted = _predict_choice(
            policy_shifter,
            curvature,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )
        loss = _weighted_mse(observed, predicted, weights)
        if best is None or loss < best[0]:
            best = (loss, float(curvature), float(candidate_upper))
    if best is None:
        return None
    return float(best[1]), float(best[2])


def _build_profile_identified_set(
    observed: np.ndarray,
    policy_shifter: np.ndarray,
    weights: np.ndarray,
    *,
    curvature: float | None,
    lower_bound: float,
    upper_bound: np.ndarray | None,
    estimated_upper_bound: float | None,
    tolerance: float,
    grid_size: int,
    profile_rel_tol: float,
    profile_abs_tol: float,
    warnings: tuple[str, ...] = (),
) -> InverseBehavioralIdentifiedSet | None:
    if curvature is None or not np.isfinite(curvature) or curvature <= 0.0:
        return None
    grid_n = max(9, int(grid_size))
    q_lower = max(float(curvature) * 0.35, tolerance)
    q_upper = max(float(curvature) * 2.75, q_lower * 1.01)
    q_grid = np.geomspace(q_lower, q_upper, grid_n)

    if estimated_upper_bound is not None:
        observed_max = float(np.max(observed))
        u_lower = max(observed_max, lower_bound + tolerance)
        u_upper = max(float(estimated_upper_bound) * 1.75, observed_max * 2.0, u_lower + tolerance)
        u_grid: np.ndarray | None = np.linspace(u_lower, u_upper, grid_n)
    else:
        u_grid = None

    best_loss = float("inf")
    scored: list[tuple[float, float | None, float]] = []
    for q_candidate in q_grid:
        if u_grid is None:
            candidate_upper = upper_bound
            loss = _weighted_mse(
                observed,
                _predict_choice(
                    policy_shifter,
                    float(q_candidate),
                    lower_bound=lower_bound,
                    upper_bound=candidate_upper,
                ),
                weights,
            )
            scored.append((float(q_candidate), None, float(loss)))
            best_loss = min(best_loss, float(loss))
            continue
        for u_candidate in u_grid:
            candidate_upper = np.full(observed.shape[0], float(u_candidate), dtype=float)
            loss = _weighted_mse(
                observed,
                _predict_choice(
                    policy_shifter,
                    float(q_candidate),
                    lower_bound=lower_bound,
                    upper_bound=candidate_upper,
                ),
                weights,
            )
            scored.append((float(q_candidate), float(u_candidate), float(loss)))
            best_loss = min(best_loss, float(loss))

    threshold = best_loss + max(
        float(profile_abs_tol), float(profile_rel_tol) * max(best_loss, _EPS)
    )
    feasible = [(q, u, loss) for q, u, loss in scored if loss <= threshold]
    if not feasible:
        return None
    q_values = np.asarray([item[0] for item in feasible], dtype=float)
    parameter_bounds: dict[str, tuple[float, float]] = {
        "curvature": (float(np.min(q_values)), float(np.max(q_values))),
    }
    representative_point = {"curvature": float(curvature)}
    if u_grid is not None:
        u_values = np.asarray([item[1] for item in feasible if item[1] is not None], dtype=float)
        if u_values.size:
            parameter_bounds["upper_bound"] = (float(np.min(u_values)), float(np.max(u_values)))
            representative_point["upper_bound"] = float(
                estimated_upper_bound if estimated_upper_bound is not None else np.median(u_values)
            )
    return InverseBehavioralIdentifiedSet(
        parameter_bounds=parameter_bounds,
        representative_point=representative_point,
        feasible_share=float(len(feasible) / max(len(scored), 1)),
        grid_size=len(scored),
        warnings=warnings,
    )


@foundry_method(
    namespace="microsim.calibration",
    version="1.0.0",
    tags={"microsim", "inverse-optimization", "behavioral-calibration", "survey"},
)
class InverseBehavioralCalibrationEstimator:
    """Calibrate a latent convex behavioral objective with explicit fallback semantics."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="inverse_behavioral_calibration",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("choice", "observed"), shape=("n_obs",)
                ),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "survey"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("inverse_calibration", "json"),
                    contract_id=InverseBehavioralCalibrationResult.contract_id,
                ),
                SlotSpec("diagnostics", SlotType.SCALAR, Unit("diagnostics", "json")),
                SlotSpec("microsim_calibration_report", SlotType.SCALAR, Unit("microsim", "json")),
                SlotSpec(
                    "microsim_calibration_report_ref", SlotType.SCALAR, Unit("artifact", "json")
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="observed_choice_key", default="market_income"),
            ParameterSpec(name="policy_shifter_key", default="instrument_z"),
            ParameterSpec(name="policy_shifter_column", default=None),
            ParameterSpec(name="known_upper_bound", default=None),
            ParameterSpec(name="upper_bound_key", default=None),
            ParameterSpec(name="estimate_upper_bound", default=False),
            ParameterSpec(name="upper_bound_grid_size", default=16),
            ParameterSpec(name="lower_bound", default=0.0),
            ParameterSpec(name="interior_tolerance", default=1e-6),
            ParameterSpec(name="mode", default="point_or_set"),
            ParameterSpec(name="solver", default="smoothed_kkt_gmm"),
            ParameterSpec(name="multi_start", default=20),
            ParameterSpec(name="smoothing_path", default=(1e-1, 1e-2, 1e-3)),
            ParameterSpec(name="kkt_weight", default=0.05),
            ParameterSpec(name="bootstrap_reps", default=64),
            ParameterSpec(name="manual_curvature", default=None),
            ParameterSpec(name="fit_loss_warn_threshold", default=0.25),
            ParameterSpec(name="fit_loss_block_threshold", default=1.0),
            ParameterSpec(name="condition_number_warn_threshold", default=1e6),
            ParameterSpec(name="condition_number_block_threshold", default=1e10),
            ParameterSpec(name="min_interior_observations", default=3),
            ParameterSpec(name="min_constraint_hit_rate", default=0.05),
            ParameterSpec(name="profile_grid_size", default=21),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Baseline inverse-optimization estimator for one-dimensional convex behavioral "
            "calibration with point-identification diagnostics and set-valued fallback."
        ),
        tags=frozenset({"microsim", "inverse-optimization", "behavioral-calibration", "survey"}),
        when_to_use=(
            "Need a gate-compatible inverse-calibration artifact before running behavioral "
            "microsimulation, especially when support may be too weak for a silent point estimate."
        ),
        citations=(
            "Keshavarz, A., Wang, Y. & Boyd, S. (2011). Imputing a convex objective function.",
            "Aswani, A., Shen, Z.-J. M. & Siddiq, A. (2018). Inverse optimization with noisy data.",
        ),
        when_not_to_use=(
            "Need a full multi-constraint KKT-GMM solver, general equilibrium inversion, or a "
            "nonconvex/dynamic behavioral model beyond the current one-dimensional baseline."
        ),
        output_interpretation=(
            "Read identified_object and identifiability_status first. bounds_only returns an "
            "identified set, while manual_override_required and not_identified must not be read as "
            "data-driven point identification."
        ),
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: object,
    ) -> dict[str, Any]:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(
        state: Mapping[str, Any] | SurveyMicroData, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        payload = _as_payload(state)
        declared_feasibility = _nested_config(payload, params, "declared_feasibility")
        objective_basis = _nested_config(payload, params, "objective_basis")
        estimator_config = _nested_config(payload, params, "estimator_config")

        observed_choice_key = str(
            _config_value(
                params,
                estimator_config,
                "observed_choice_key",
                objective_basis.get("observed_choice_key", "market_income"),
            )
        )
        policy_shifter_key = str(
            _config_value(
                params,
                estimator_config,
                "policy_shifter_key",
                objective_basis.get("policy_shifter_key", "instrument_z"),
            )
        )
        policy_shifter_column_raw = _config_value(params, estimator_config, "policy_shifter_column")
        policy_shifter_column = (
            None if policy_shifter_column_raw is None else int(policy_shifter_column_raw)
        )
        lower_bound = float(_config_value(params, declared_feasibility, "lower_bound", 0.0))
        tolerance = max(
            1e-8, float(_config_value(params, estimator_config, "interior_tolerance", 1e-6))
        )
        bootstrap_reps = max(0, int(_config_value(params, estimator_config, "bootstrap_reps", 64)))
        estimate_upper_bound = _bool_value(
            _config_value(params, declared_feasibility, "estimate_upper_bound", False)
        )
        upper_bound_grid_size = max(
            8,
            int(_config_value(params, estimator_config, "upper_bound_grid_size", 16)),
        )
        manual_curvature_raw = _config_value(params, estimator_config, "manual_curvature")
        mode = str(_config_value(params, estimator_config, "mode", "point_or_set")).strip().lower()
        if mode not in {"point_or_set", "set_only", "diagnostics_only"}:
            raise ValueError("mode must be one of point_or_set, set_only, diagnostics_only")
        solver = (
            str(_config_value(params, estimator_config, "solver", "smoothed_kkt_gmm"))
            .strip()
            .lower()
        )
        multi_start = max(1, int(_config_value(params, estimator_config, "multi_start", 20)))
        smoothing_path = _float_tuple(
            _config_value(params, estimator_config, "smoothing_path", (1e-1, 1e-2, 1e-3)),
            default=(1e-1, 1e-2, 1e-3),
        )
        kkt_weight = max(0.0, float(_config_value(params, estimator_config, "kkt_weight", 0.05)))
        min_interior_observations = max(
            1,
            int(_config_value(params, estimator_config, "min_interior_observations", 3)),
        )
        min_constraint_hit_rate = float(
            _config_value(params, estimator_config, "min_constraint_hit_rate", 0.05)
        )
        fit_loss_warn_threshold = float(
            _config_value(params, estimator_config, "fit_loss_warn_threshold", 0.25)
        )
        fit_loss_block_threshold = float(
            _config_value(params, estimator_config, "fit_loss_block_threshold", 1.0)
        )
        condition_number_warn_threshold = float(
            _config_value(params, estimator_config, "condition_number_warn_threshold", 1e6)
        )
        condition_number_block_threshold = float(
            _config_value(params, estimator_config, "condition_number_block_threshold", 1e10)
        )
        profile_grid_size = max(
            9, int(_config_value(params, estimator_config, "profile_grid_size", 21))
        )
        profile_rel_tol = float(_config_value(params, estimator_config, "profile_rel_tol", 0.10))
        profile_abs_tol = float(_config_value(params, estimator_config, "profile_abs_tol", 1e-8))
        objective_family = str(objective_basis.get("basis_name", "single_index_quadratic_cap"))
        constraint_family = str(declared_feasibility.get("family", "box_interval"))

        observed = _resolve_numeric_vector(payload, key=observed_choice_key)
        weights = _resolve_numeric_vector(payload, key="weights", n_obs=observed.shape[0])
        if np.any(~np.isfinite(observed)):
            raise ValueError(f"{observed_choice_key} must contain only finite values")
        if np.any(~np.isfinite(weights)) or np.any(weights <= 0.0):
            raise ValueError("weights must be finite and strictly positive")

        policy_shifter_raw = _resolve_numeric_matrix_or_vector(
            payload,
            key=policy_shifter_key,
            n_obs=observed.shape[0],
        )
        policy_shifter, policy_shifter_projection = _policy_shifter_score(
            policy_shifter_raw,
            column=policy_shifter_column,
        )
        if not np.any(np.abs(policy_shifter - np.mean(policy_shifter)) > tolerance):
            raise ValueError("policy shifter has insufficient variation for inverse calibration")

        upper_bound: np.ndarray | None = None
        upper_bound_source: str | None = None
        known_upper_bound_raw = _config_value(
            params,
            declared_feasibility,
            "known_upper_bound",
            declared_feasibility.get("upper_bound"),
        )
        upper_bound_key_raw = _config_value(params, declared_feasibility, "upper_bound_key")
        if known_upper_bound_raw is not None:
            upper_bound = np.asarray(
                _resolve_numeric_vector(
                    {"known_upper_bound": known_upper_bound_raw},
                    key="known_upper_bound",
                    n_obs=observed.shape[0],
                    allow_scalar=True,
                ),
                dtype=float,
            )
            upper_bound_source = "known_upper_bound"
        elif upper_bound_key_raw is not None:
            upper_bound_key = str(upper_bound_key_raw)
            upper_bound = _resolve_numeric_vector(
                payload,
                key=upper_bound_key,
                n_obs=observed.shape[0],
                allow_scalar=True,
            )
            upper_bound_source = upper_bound_key
        if upper_bound is not None:
            upper_bound = np.maximum(np.asarray(upper_bound, dtype=float), lower_bound + tolerance)

        raw_repeat_measure = _resolve_optional_numeric_vector(
            payload,
            key=str(
                _config_value(
                    params, estimator_config, "repeat_measure_key", "income_repeat_measure"
                )
            ),
            n_obs=observed.shape[0],
        )
        raw_measurement_reliability = (
            _weighted_corr(observed, raw_repeat_measure, weights)
            if raw_repeat_measure is not None
            else None
        )
        regime = _detect_regime(payload, observed.shape[0])
        effective_sample_size = _effective_sample_size(weights)
        prepared = _aggregate_or_smooth(
            payload,
            observed=observed,
            policy_shifter=policy_shifter,
            weights=weights,
            upper_bound=upper_bound,
            regime=regime,
            estimator_config=estimator_config,
            params=params,
        )
        observed = prepared.observed
        policy_shifter = prepared.policy_shifter
        weights = prepared.weights
        upper_bound = prepared.upper_bound

        feasibility_violation = _feasibility_violation(
            observed,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )
        distance_to_feasibility = _weighted_mean(feasibility_violation, weights)
        normalized_distance = distance_to_feasibility / max(
            _weighted_mean(np.abs(observed), weights), 1.0
        )
        lower_mask, interior_mask, upper_mask = _active_masks(
            observed,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            tolerance=tolerance,
        )

        diagnostics: dict[str, Any] = {
            "observed_choice_key": observed_choice_key,
            "policy_shifter_key": policy_shifter_key,
            "policy_shifter_projection": policy_shifter_projection,
            "policy_shifter_mean": float(np.mean(policy_shifter)),
            "policy_shifter_sd": float(np.std(policy_shifter)),
            "regime": regime,
            "effective_sample_size": float(effective_sample_size),
            "measurement_reliability": raw_measurement_reliability,
            "distance_to_feasibility": float(distance_to_feasibility),
            "normalized_distance": float(normalized_distance),
            "lower_active_share": float(np.mean(lower_mask)),
            "interior_share": float(np.mean(interior_mask)),
            "upper_active_share": float(np.mean(upper_mask)),
            "interior_observations": int(np.sum(interior_mask)),
            "warnings": [],
            "block_reasons": [],
            "assumptions": [
                "single_index_quadratic_objective",
                "box_feasibility_set",
                "positive_curvature_normalization",
            ],
            "declared_feasibility": declared_feasibility,
            "objective_basis": objective_basis,
            "estimator_config": estimator_config,
            "mode": mode,
            "solver": solver,
            "multi_start": int(multi_start),
            "smoothing_path": [float(item) for item in smoothing_path],
        }
        diagnostics.update(prepared.diagnostics)

        if distance_to_feasibility > 1e-6 and not estimate_upper_bound:
            diagnostics["block_reasons"].append("observed_choices_violate_declared_feasibility")

        identified_object = "not_identified"
        curvature: float | None = None
        estimated_upper_bound: float | None = None
        identified_set: InverseBehavioralIdentifiedSet | None = None

        if manual_curvature_raw is not None:
            curvature = max(float(manual_curvature_raw), tolerance)
            identified_object = "manual_override_required"
            diagnostics["warnings"].append("manual_curvature_override_not_estimated_from_data")
        elif estimate_upper_bound and upper_bound is None:
            point_without_cap = _analytic_curvature_estimate(
                observed,
                policy_shifter,
                weights,
                lower_bound=lower_bound,
                upper_bound=None,
                tolerance=tolerance,
            )
            if (
                point_without_cap is not None
                and int(np.sum(point_without_cap[1])) >= min_interior_observations
            ):
                curvature = float(point_without_cap[0])
                refined = (
                    _solve_smoothed_kkt_gmm(
                        observed,
                        policy_shifter,
                        weights,
                        lower_bound=lower_bound,
                        upper_bound=None,
                        tolerance=tolerance,
                        multi_start=multi_start,
                        smoothing_path=smoothing_path,
                        kkt_weight=kkt_weight,
                    )
                    if solver in {"auto", "smoothed_kkt_gmm"}
                    else None
                )
                if refined is not None:
                    curvature = float(refined[0])
                observed_max = float(np.max(observed))
                predicted_no_cap = _predict_choice(
                    policy_shifter,
                    curvature,
                    lower_bound=lower_bound,
                    upper_bound=None,
                )
                upper_lower = max(observed_max, lower_bound + tolerance)
                upper_upper = max(
                    upper_lower + tolerance,
                    float(np.max(predicted_no_cap)) * 2.0,
                    observed_max * 2.0,
                )
                identified_set = InverseBehavioralIdentifiedSet(
                    parameter_bounds={"upper_bound": (float(upper_lower), float(upper_upper))},
                    representative_point={
                        "curvature": float(curvature),
                        "upper_bound": float(upper_lower),
                    },
                    feasible_share=1.0,
                    grid_size=1,
                    warnings=(
                        "latent upper-bound constraint never binds; "
                        "constraint parameter is not point identified",
                    ),
                )
                identified_object = "objective_params"
                diagnostics["warnings"].append("latent_constraint_not_point_identified")
                upper_bound_source = "latent_upper_bound_not_point_identified"
            else:
                estimated = _fit_with_estimated_upper_bound(
                    observed,
                    policy_shifter,
                    weights,
                    lower_bound=lower_bound,
                    tolerance=tolerance,
                    grid_size=upper_bound_grid_size,
                )
                if estimated is not None:
                    curvature, estimated_upper_bound = estimated
                    upper_bound = np.full(observed.shape[0], estimated_upper_bound, dtype=float)
                    upper_bound_source = "estimated_global_upper_bound"
                    _, estimated_interior_mask, estimated_upper_mask = _active_masks(
                        observed,
                        lower_bound=lower_bound,
                        upper_bound=upper_bound,
                        tolerance=tolerance,
                    )
                    if float(np.mean(estimated_upper_mask)) >= min_constraint_hit_rate:
                        identified_object = "objective_and_constraint_params"
                    elif int(np.sum(estimated_interior_mask)) >= min_interior_observations:
                        identified_object = "objective_params"
                        diagnostics["warnings"].append("latent_constraint_not_point_identified")
                        identified_set = _build_profile_identified_set(
                            observed,
                            policy_shifter,
                            weights,
                            curvature=curvature,
                            lower_bound=lower_bound,
                            upper_bound=upper_bound,
                            estimated_upper_bound=estimated_upper_bound,
                            tolerance=tolerance,
                            grid_size=profile_grid_size,
                            profile_rel_tol=profile_rel_tol,
                            profile_abs_tol=profile_abs_tol,
                            warnings=(
                                "latent upper-bound support is too sparse for point identification",
                            ),
                        )
                    else:
                        diagnostics["block_reasons"].append(
                            "unable_to_estimate_upper_bound_from_support"
                        )
                        curvature = None
                        estimated_upper_bound = None
                        upper_bound = None
                else:
                    diagnostics["block_reasons"].append(
                        "unable_to_estimate_upper_bound_from_support"
                    )
        else:
            fit_kind, curvature, upper_bound, identified_set = _fit_known_upper_bound(
                observed,
                policy_shifter,
                weights,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                tolerance=tolerance,
            )
            if fit_kind == "point":
                identified_object = "objective_params"
            elif fit_kind == "bounds":
                identified_object = "bounds_only"
                diagnostics["warnings"].append(
                    "point_identification_failed_returning_identified_set"
                )
            else:
                diagnostics["block_reasons"].append("insufficient_interior_or_boundary_support")

        if "observed_choices_violate_declared_feasibility" in diagnostics["block_reasons"]:
            identified_object = "not_identified"
            curvature = None
            identified_set = None

        if (
            curvature is not None
            and identified_object in {"objective_params", "objective_and_constraint_params"}
            and solver in {"auto", "smoothed_kkt_gmm"}
        ):
            refined = _solve_smoothed_kkt_gmm(
                observed,
                policy_shifter,
                weights,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                tolerance=tolerance,
                multi_start=multi_start,
                smoothing_path=smoothing_path,
                kkt_weight=kkt_weight,
            )
            if refined is not None:
                curvature = float(refined[0])

        if curvature is None or not np.isfinite(curvature) or curvature <= 0.0:
            predicted = np.asarray(observed, dtype=float).copy()
            fit_loss = 0.0
            jacobian_rank = 0
            condition_number = float("inf")
            bootstrap_draws: list[dict[str, float]] = []
        else:
            predicted = _predict_choice(
                policy_shifter,
                curvature,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
            )
            fit_loss = _weighted_mse(observed, predicted, weights)
            bootstrap_draws, active_set_stability = _bootstrap_draws(
                observed,
                policy_shifter,
                weights,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                bootstrap_reps=bootstrap_reps,
                tolerance=tolerance,
                rng=np.random.default_rng(int(params.get("__seed__", 0))),
            )
            diagnostics["active_set_stability"] = active_set_stability
            jacobian_rank, condition_number, _ = _numeric_jacobian(
                policy_shifter,
                weights,
                curvature=curvature,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                estimated_upper_bound=estimated_upper_bound,
            )
            if active_set_stability is not None and active_set_stability < 0.75:
                diagnostics["warnings"].append("bootstrap_active_sets_unstable")

        normalized_fit_loss = fit_loss / max(_weighted_var(observed, weights), 1e-12)
        diagnostics["normalized_fit_loss"] = float(normalized_fit_loss)
        if (
            normalized_fit_loss > fit_loss_warn_threshold
            and identified_object != "manual_override_required"
        ):
            diagnostics["warnings"].append("large_inverse_fit_loss")
        if normalized_fit_loss > fit_loss_block_threshold and identified_object not in {
            "manual_override_required",
            "bounds_only",
        }:
            diagnostics["block_reasons"].append("wrong_model_class_or_large_optimality_gap")
            identified_object = "not_identified"
            curvature = None
            estimated_upper_bound = None
            identified_set = None
        if (
            condition_number is not None
            and math.isfinite(condition_number)
            and condition_number > condition_number_warn_threshold
        ):
            diagnostics["warnings"].append("ill_conditioned_kkt_jacobian")
        if (
            condition_number is None
            or not math.isfinite(condition_number)
            or condition_number > condition_number_block_threshold
        ) and identified_object == "objective_and_constraint_params":
            diagnostics["warnings"].append("constraint_parameter_weakly_identified")
            identified_object = "objective_params"
            diagnostics["warnings"].append("latent_constraint_not_point_identified")

        if (
            identified_set is None
            and curvature is not None
            and identified_object in {"objective_params", "objective_and_constraint_params"}
            and mode in {"point_or_set", "set_only"}
        ):
            identified_set = _build_profile_identified_set(
                observed,
                policy_shifter,
                weights,
                curvature=curvature,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                estimated_upper_bound=estimated_upper_bound,
                tolerance=tolerance,
                grid_size=profile_grid_size,
                profile_rel_tol=profile_rel_tol,
                profile_abs_tol=profile_abs_tol,
                warnings=(),
            )
        if mode == "set_only" and identified_set is not None:
            identified_object = "bounds_only"
            diagnostics["warnings"].append("set_only_mode_returning_identified_set")
        if mode == "diagnostics_only":
            identified_object = "not_identified"
            curvature = None
            estimated_upper_bound = None
            diagnostics["block_reasons"].append("diagnostics_only_no_operational_estimate")

        includes_latent_upper = bool(
            estimate_upper_bound
            or estimated_upper_bound is not None
            or (identified_set is not None and "upper_bound" in identified_set.parameter_bounds)
        )
        param_names = ("curvature", "upper_bound") if includes_latent_upper else ("curvature",)
        if estimated_upper_bound is not None and bootstrap_draws:
            for draw in bootstrap_draws:
                if "curvature" in draw and "upper_bound" not in draw:
                    draw["upper_bound"] = float(estimated_upper_bound)
        bootstrap_intervals = _bootstrap_intervals(bootstrap_draws)

        identifiability_report = _build_identifiability_report(
            param_names=param_names,
            jacobian_rank=jacobian_rank if curvature is not None else 0,
            condition_number=condition_number if curvature is not None else float("inf"),
            bootstrap_draws=bootstrap_draws,
            identified_object=identified_object,
        )

        if identified_object in {"not_identified", "manual_override_required"}:
            identifiability_status = IdentifiabilityStatus.NON_IDENTIFIED.value
        elif (
            identified_object == "bounds_only"
            or "latent_constraint_not_point_identified" in diagnostics["warnings"]
        ):
            identifiability_status = IdentifiabilityStatus.SLOPPY.value
        elif jacobian_rank < len(param_names):
            identifiability_status = IdentifiabilityStatus.NON_IDENTIFIED.value
        elif (
            diagnostics["warnings"]
            or not math.isfinite(condition_number)
            or condition_number > condition_number_warn_threshold
            or fit_loss > max(_weighted_var(observed, weights), 1.0)
        ):
            identifiability_status = IdentifiabilityStatus.SLOPPY.value
        else:
            identifiability_status = IdentifiabilityStatus.IDENTIFIED.value

        if (
            identified_object == "bounds_only"
            and identified_set is not None
            and "curvature_upper_bound" in bootstrap_intervals
        ):
            lower_bound_set = identified_set.parameter_bounds["curvature"][0]
            identified_set = identified_set.model_copy(
                update={
                    "parameter_bounds": {
                        "curvature": (
                            float(lower_bound_set),
                            float(bootstrap_intervals["curvature_upper_bound"][1]),
                        )
                    }
                }
            )

        objective_params: dict[str, float] = {}
        constraint_params: dict[str, float] = {}
        if identified_object == "objective_params" and curvature is not None:
            objective_params["curvature"] = float(curvature)
        elif (
            identified_object == "objective_and_constraint_params"
            and curvature is not None
            and estimated_upper_bound is not None
        ):
            objective_params["curvature"] = float(curvature)
            constraint_params["upper_bound"] = float(estimated_upper_bound)
        elif identified_object == "bounds_only" and identified_set is not None:
            objective_params = dict(identified_set.representative_point)
            constraint_params = {
                key: value for key, value in objective_params.items() if key in {"upper_bound"}
            }
            objective_params = {
                key: value
                for key, value in objective_params.items()
                if key not in constraint_params
            }
        elif identified_object == "manual_override_required" and curvature is not None:
            objective_params["curvature"] = float(curvature)

        if identified_object == "bounds_only" and identified_set is None:
            diagnostics["block_reasons"].append("bounds_only_requires_identified_set")
            identified_object = "not_identified"
            objective_params = {}

        optimality_gap_stats = {
            "rmse": float(math.sqrt(max(fit_loss, 0.0))),
            "mean_abs_gap": float(_weighted_mean(np.abs(observed - predicted), weights)),
            "max_abs_gap": float(np.max(np.abs(observed - predicted))),
            "mean_feasibility_violation": float(distance_to_feasibility),
        }

        if identifiability_status == IdentifiabilityStatus.IDENTIFIED.value:
            compatibility_status = "compatible"
            reason_code = "POINT_IDENTIFIED"
        elif identified_object in {"bounds_only", "manual_override_required"} or (
            identified_object == "objective_params"
            and identifiability_status == IdentifiabilityStatus.SLOPPY.value
        ):
            compatibility_status = "approximately_compatible"
            reason_code = "PARTIAL_IDENTIFICATION_FALLBACK"
        else:
            compatibility_status = "incompatible"
            reason_code = "NOT_IDENTIFIED"
        if diagnostics["block_reasons"] and identified_object == "not_identified":
            compatibility_status = "incompatible"
            reason_code = "NOT_IDENTIFIED"

        report_warnings = list(diagnostics["warnings"])
        if identified_object == "bounds_only":
            report_warnings.append("inverse_calibration_bounds_only")
        if identified_object == "manual_override_required":
            report_warnings.append("inverse_calibration_manual_override")
        report_blocking = list(diagnostics["block_reasons"])
        calibration_report = build_microsim_calibration_report(
            compatibility_status=compatibility_status,
            reason_code=reason_code,
            exact_feasible=bool(distance_to_feasibility <= 1e-9),
            distance_to_feasibility=float(distance_to_feasibility),
            normalized_distance=float(normalized_distance),
            jacobian_rank=int(jacobian_rank),
            condition_number=None
            if not math.isfinite(condition_number)
            else float(condition_number),
            max_abs_gap=float(optimality_gap_stats["max_abs_gap"]),
            warnings=report_warnings,
            blocking_reasons=report_blocking,
            metadata={
                "objective_family": objective_family,
                "constraint_family": constraint_family,
                "identified_object": identified_object,
                "regime": regime,
                "policy_shifter_key": policy_shifter_key,
                "policy_shifter_projection": policy_shifter_projection,
                "upper_bound_source": upper_bound_source,
                "fit_loss": float(fit_loss),
                "normalized_fit_loss": float(normalized_fit_loss),
                "bootstrap_reps": int(bootstrap_reps),
                "mode": mode,
                "solver": solver,
            },
        )

        artifact_store = resolve_artifact_store(payload, params)
        calibration_report_ref = (
            persist_microsim_calibration_report(artifact_store, calibration_report)
            if artifact_store is not None
            else None
        )

        result = InverseBehavioralCalibrationResult(
            objective_family=objective_family,
            constraint_family=constraint_family,
            objective_params=objective_params,
            constraint_params=constraint_params,
            normalization={
                "sign_anchor": "curvature>0",
                "scale_rule": "single_parameter_sign_anchor",
            },
            fit_loss=float(fit_loss),
            optimality_gap_stats=optimality_gap_stats,
            identified_object=identified_object,
            regime=regime,
            effective_sample_size=float(effective_sample_size),
            measurement_reliability=raw_measurement_reliability,
            identifiability_status=identifiability_status,
            identifiability=identifiability_report,
            jacobian_rank=int(jacobian_rank),
            condition_number=None
            if not math.isfinite(condition_number)
            else float(condition_number),
            bootstrap_intervals=bootstrap_intervals,
            identified_set=identified_set,
            identified_set_summary=(
                None if identified_set is None else identified_set.model_dump(mode="json")
            ),
            fallback_used=(
                identified_object in {"bounds_only", "manual_override_required", "not_identified"}
                or "latent_constraint_not_point_identified" in diagnostics["warnings"]
            ),
            diagnostics={
                **diagnostics,
                "predicted_mean": float(_weighted_mean(predicted, weights)),
                "bootstrap_success_reps": len(bootstrap_draws),
                "jacobian_rank": int(jacobian_rank),
                "condition_number": None
                if not math.isfinite(condition_number)
                else float(condition_number),
            },
            microsim_calibration_report=calibration_report.model_dump(mode="json"),
            microsim_calibration_report_ref=(
                None
                if calibration_report_ref is None
                else calibration_report_ref.model_dump(mode="json")
            ),
            metadata={
                "observed_choice_key": observed_choice_key,
                "policy_shifter_key": policy_shifter_key,
                "policy_shifter_projection": policy_shifter_projection,
                "upper_bound_source": upper_bound_source,
                "estimator_version": "1.0.0",
                "declared_feasibility": declared_feasibility,
                "objective_basis": objective_basis,
                "estimator_config": estimator_config,
                "mode": mode,
            },
        )
        return {
            "result": result,
            "diagnostics": result.diagnostics,
            "microsim_calibration_report": calibration_report.model_dump(mode="json"),
            "microsim_calibration_report_ref": (
                None
                if calibration_report_ref is None
                else calibration_report_ref.model_dump(mode="json")
            ),
        }


__all__ = ["InverseBehavioralCalibrationEstimator"]
