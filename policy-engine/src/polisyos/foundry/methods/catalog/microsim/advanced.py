"""Public microsim advanced module API."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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

from .protocols import (
    BehavioralResponseResult,
    DynamicMicrosimResult,
    HeterogeneousBehavioralResponseResult,
    ImputationResult,
    SurveyMicroData,
    TaxBenefitResult,
)


def _survey_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=SurveyMicroData,
        nested_keys=("survey_micro_data",),
    )


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(values * weights) / max(np.sum(weights), 1e-12))


def _weighted_var(values: np.ndarray, weights: np.ndarray) -> float:
    mean = _weighted_mean(values, weights)
    return float(np.sum(weights * np.square(values - mean)) / max(np.sum(weights), 1e-12))


def _effective_sample_size(weights: np.ndarray) -> float:
    numerator = float(np.sum(weights) ** 2)
    denominator = float(np.sum(np.square(weights)))
    return numerator / max(denominator, 1e-12)


def _encode_numeric(values: Any) -> np.ndarray:
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


def _optional_vector(state: Mapping[str, Any], key: str, n_obs: int) -> np.ndarray | None:
    value = state.get(key)
    if value is None:
        metadata = state.get("metadata")
        if isinstance(metadata, Mapping):
            value = metadata.get(key)
    if value is None:
        return None
    array = np.asarray(value)
    if array.ndim == 0:
        return np.repeat(array.item(), n_obs)
    if array.ndim != 1:
        raise ValueError(f"{key} must be scalar or a 1D array")
    if array.shape[0] != n_obs:
        raise ValueError(f"{key} length must match market_income length")
    return array


def _optional_matrix(state: Mapping[str, Any], key: str, n_obs: int) -> np.ndarray | None:
    value = state.get(key)
    if value is None:
        metadata = state.get("metadata")
        if isinstance(metadata, Mapping):
            value = metadata.get(key)
    if value is None:
        return None
    array = np.asarray(value)
    if array.ndim != 2 or array.shape[0] != n_obs:
        raise ValueError(f"{key} must be a 2D array with row count matching market_income")
    return array


def _optional_design(state: Mapping[str, Any], key: str, n_obs: int) -> np.ndarray | None:
    value = state.get(key)
    if value is None:
        metadata = state.get("metadata")
        if isinstance(metadata, Mapping):
            value = metadata.get(key)
    if value is None:
        return None
    array = np.asarray(value)
    if array.ndim == 0:
        return np.repeat(array.item(), n_obs).reshape(n_obs, 1)
    if array.ndim == 1:
        if array.shape[0] != n_obs:
            raise ValueError(f"{key} length must match market_income length")
        return array.reshape(n_obs, 1)
    if array.ndim == 2 and array.shape[0] == n_obs:
        return array
    raise ValueError(f"{key} must be scalar, 1D, or 2D with row count matching market_income")


def _as_numeric_design(values: Any, *, n_obs: int | None = None) -> np.ndarray:
    array = np.asarray(_encode_numeric(values), dtype=float)
    if array.ndim == 1:
        if n_obs is not None and array.shape[0] != n_obs:
            raise ValueError("design length must match expected observation count")
        return array.reshape(-1, 1)
    if array.ndim == 2:
        if n_obs is not None and array.shape[0] != n_obs:
            raise ValueError("design row count must match expected observation count")
        return array
    raise ValueError("design inputs must be one- or two-dimensional")


def _instrument_score(instrument: np.ndarray) -> np.ndarray:
    design = _as_numeric_design(instrument)
    if design.shape[1] == 1:
        return design[:, 0]
    centered = design - np.nanmean(design, axis=0, keepdims=True)
    centered = np.nan_to_num(centered, nan=0.0)
    if not np.any(np.abs(centered) > 0.0):
        return np.mean(design, axis=1)
    try:
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        return np.asarray(centered @ vt[0], dtype=float)
    except np.linalg.LinAlgError:
        return np.asarray(np.mean(centered, axis=1), dtype=float)


def _behavioral_metadata(state: Mapping[str, Any]) -> dict[str, Any]:
    metadata = state.get("metadata")
    return dict(metadata) if isinstance(metadata, Mapping) else {}


def _metadata_value(state: Mapping[str, Any], key: str, default: Any = None) -> Any:
    if key in state and state.get(key) is not None:
        return state.get(key)
    return _behavioral_metadata(state).get(key, default)


def _extract_feature_names(state: Mapping[str, Any], n_features: int) -> tuple[str, ...]:
    raw = _metadata_value(state, "feature_names")
    if isinstance(raw, (list, tuple)) and len(raw) >= n_features:
        return tuple(str(item) for item in raw[:n_features])
    return tuple(f"feature_{idx}" for idx in range(n_features))


def _coerce_point_array(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    array = np.asarray(value, dtype=float)
    if array.ndim == 0:
        array = array.reshape(1)
    return array.reshape(-1)


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values, kind="mergesort")
    x = values[order]
    w = weights[order]
    total = float(np.sum(w))
    if x.size == 0 or total <= 1e-12:
        return float("nan")
    cdf = (np.cumsum(w) - 0.5 * w) / total
    return float(np.interp(quantile, cdf, x, left=x[0], right=x[-1]))


def _constant_vector(value: float, size: int) -> np.ndarray:
    return np.full(size, float(value), dtype=float)


def _extract_tax_rate(state: Mapping[str, Any], n_obs: int) -> tuple[np.ndarray, str]:
    rate = state.get("effective_tax_rate")
    source = "effective_tax_rate"
    if rate is None:
        rate = state.get("marginal_tax_rate")
        source = "marginal_tax_rate"
    if rate is None:
        metadata = _behavioral_metadata(state)
        if "effective_tax_rate" in metadata:
            rate = metadata["effective_tax_rate"]
            source = "effective_tax_rate"
        elif "marginal_tax_rate" in metadata:
            rate = metadata["marginal_tax_rate"]
            source = "marginal_tax_rate"
    if rate is None:
        raise ValueError(
            "behavioral_response requires effective_tax_rate or marginal_tax_rate input"
        )
    array = np.asarray(rate, dtype=float)
    if array.ndim != 1 or array.shape[0] != n_obs:
        raise ValueError(f"{source} must be a 1D array matching market_income length")
    return array, source


def _prepare_controls(
    features: np.ndarray | None,
    weights: np.ndarray,
    *,
    feature_names: tuple[str, ...] | None = None,
    max_features: int,
) -> tuple[np.ndarray, tuple[str, ...]]:
    if features is None or features.ndim != 2 or features.shape[1] == 0 or max_features <= 0:
        return np.zeros((weights.shape[0], 0), dtype=float), ()

    usable = np.asarray(features[:, :max_features], dtype=float).copy()
    names: list[str] = []
    raw_names = feature_names or ()
    for idx in range(usable.shape[1]):
        column = usable[:, idx]
        finite_mask = np.isfinite(column)
        fill = (
            _weighted_mean(column[finite_mask], weights[finite_mask]) if finite_mask.any() else 0.0
        )
        column[~finite_mask] = fill
        std = math.sqrt(max(_weighted_var(column, weights), 0.0))
        if std > 1e-9:
            column[:] = (column - _weighted_mean(column, weights)) / std
        else:
            column[:] = column - _weighted_mean(column, weights)
        usable[:, idx] = column
        names.append(str(raw_names[idx]) if idx < len(raw_names) else f"feature_{idx}")
    return usable, tuple(names)


def _solve_weighted_least_squares(
    y: np.ndarray,
    x: np.ndarray,
    weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    sqrt_w = np.sqrt(np.clip(weights, 0.0, None))
    xw = x * sqrt_w[:, None]
    yw = y * sqrt_w
    beta, *_ = np.linalg.lstsq(xw, yw, rcond=None)
    fitted = x @ beta
    resid = y - fitted
    ssr = float(np.sum(weights * np.square(resid)))
    return beta, fitted, ssr


def _weighted_r2(y: np.ndarray, fitted: np.ndarray, weights: np.ndarray) -> float | None:
    denominator = float(np.sum(weights * np.square(y - _weighted_mean(y, weights))))
    if denominator <= 1e-12:
        return None
    ssr = float(np.sum(weights * np.square(y - fitted)))
    return max(0.0, 1.0 - ssr / denominator)


def _weighted_rank(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0.0)
    ranks = np.full(values.shape, 0.5, dtype=float)
    if not np.any(mask):
        return ranks
    values_masked = values[mask]
    weights_masked = weights[mask]
    order = np.argsort(values_masked, kind="mergesort")
    cdf = (np.cumsum(weights_masked[order]) - 0.5 * weights_masked[order]) / max(
        np.sum(weights_masked), 1e-12
    )
    masked_ranks = np.empty(values_masked.shape[0], dtype=float)
    masked_ranks[order] = cdf
    ranks[mask] = masked_ranks
    return ranks


def _interacted_elasticity_projection(
    log_income: np.ndarray,
    log_price: np.ndarray,
    controls: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, np.ndarray, dict[str, Any]]:
    if controls.shape[1] == 0:
        elasticity = _cross_section_slope(log_income, log_price, controls, weights)
        return (
            float(elasticity),
            _constant_vector(float(elasticity), log_income.shape[0]),
            {
                "projection": "constant_slope",
            },
        )

    interactions = controls * log_price[:, None]
    design = np.column_stack(
        [np.ones(log_income.shape[0], dtype=float), controls, log_price, interactions]
    )
    beta, _, _ = _solve_weighted_least_squares(log_income, design, weights)
    n_controls = controls.shape[1]
    base = float(beta[1 + n_controls])
    interaction = np.asarray(beta[2 + n_controls :], dtype=float)
    elasticity_by_obs = base + controls @ interaction
    return (
        _weighted_mean(elasticity_by_obs, weights),
        elasticity_by_obs,
        {
            "projection": "linear_interactions",
            "base_elasticity": base,
            "interaction_coefficients": interaction.tolist(),
        },
    )


def _iv_interacted_elasticity_projection(
    log_income: np.ndarray,
    log_price: np.ndarray,
    instrument: np.ndarray,
    controls: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, np.ndarray, dict[str, Any]]:
    z_design = _as_numeric_design(instrument, n_obs=log_income.shape[0])
    stage1_design = (
        np.column_stack([np.ones(log_income.shape[0], dtype=float), controls, z_design])
        if controls.shape[1] > 0
        else np.column_stack([np.ones(log_income.shape[0], dtype=float), z_design])
    )
    _, fitted_price, _ = _solve_weighted_least_squares(log_price, stage1_design, weights)
    control_rank = _weighted_rank(log_price - fitted_price, weights)
    stage1_r2 = _weighted_r2(log_price, fitted_price, weights)

    if controls.shape[1] == 0:
        stage2_design = np.column_stack(
            [np.ones(log_income.shape[0], dtype=float), fitted_price, control_rank]
        )
        beta, _, _ = _solve_weighted_least_squares(log_income, stage2_design, weights)
        elasticity = float(beta[1])
        return (
            float(elasticity),
            _constant_vector(float(elasticity), log_income.shape[0]),
            {
                "projection": "control_function_constant",
                "base_elasticity": elasticity,
                "control_function_coefficient": float(beta[2]),
                "stage1_r2": stage1_r2,
            },
        )

    fitted_interactions = controls * fitted_price[:, None]
    control_interactions = controls * control_rank[:, None]
    stage2_design = np.column_stack(
        [
            np.ones(log_income.shape[0], dtype=float),
            controls,
            fitted_price,
            control_rank,
            fitted_interactions,
            control_interactions,
        ]
    )
    beta, _, _ = _solve_weighted_least_squares(log_income, stage2_design, weights)
    n_controls = controls.shape[1]
    base = float(beta[1 + n_controls])
    interaction = np.asarray(beta[3 + n_controls : 3 + 2 * n_controls], dtype=float)
    elasticity_by_obs = base + controls @ interaction
    return (
        _weighted_mean(elasticity_by_obs, weights),
        elasticity_by_obs,
        {
            "projection": "control_function_linear_interactions",
            "base_elasticity": base,
            "interaction_coefficients": interaction.tolist(),
            "control_function_coefficient": float(beta[2 + n_controls]),
            "stage1_r2": stage1_r2,
            "control_function_support": [
                float(_weighted_quantile(control_rank, weights, 0.1)),
                float(_weighted_quantile(control_rank, weights, 0.9)),
            ],
        },
    )


def _cohort_specific_elasticity_projection(
    log_income: np.ndarray,
    log_price: np.ndarray,
    cohort_id: np.ndarray,
    period_id: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, np.ndarray, dict[str, Any]]:
    cohort_labels = cohort_id.astype(str)
    period_labels = period_id.astype(str)
    slopes: dict[str, float] = {}
    cohort_weight: dict[str, float] = {}
    cohort_summary: dict[str, float] = {}

    for cohort in np.unique(cohort_labels):
        mask = cohort_labels == cohort
        periods = period_labels[mask]
        unique_periods = np.unique(periods)
        if unique_periods.size < 2:
            continue
        period_means_y: list[float] = []
        period_means_x: list[float] = []
        period_weights: list[float] = []
        for period in unique_periods:
            cell_mask = mask & (period_labels == period)
            cell_weight = float(np.sum(weights[cell_mask]))
            if cell_weight <= 0.0:
                continue
            period_means_y.append(_weighted_mean(log_income[cell_mask], weights[cell_mask]))
            period_means_x.append(_weighted_mean(log_price[cell_mask], weights[cell_mask]))
            period_weights.append(cell_weight)
        if len(period_means_x) < 2:
            continue
        x = np.asarray(period_means_x, dtype=float)
        y = np.asarray(period_means_y, dtype=float)
        w = np.asarray(period_weights, dtype=float)
        x_centered = x - _weighted_mean(x, w)
        denominator = float(np.sum(w * np.square(x_centered)))
        if denominator <= 1e-12:
            continue
        slope = float(np.sum(w * x_centered * (y - _weighted_mean(y, w))) / denominator)
        slopes[cohort] = slope
        cohort_weight[cohort] = float(np.sum(weights[mask]))
        cohort_summary[cohort] = slope

    if not slopes:
        raise ValueError(
            "cohort-level elasticity projection requires at least two informative cohorts"
        )

    elasticity_by_obs = np.asarray(
        [slopes.get(label, np.nan) for label in cohort_labels], dtype=float
    )
    valid_mask = np.isfinite(elasticity_by_obs)
    if not np.all(valid_mask):
        fallback = _weighted_mean(elasticity_by_obs[valid_mask], weights[valid_mask])
        elasticity_by_obs[~valid_mask] = fallback
    return (
        _weighted_mean(elasticity_by_obs, weights),
        elasticity_by_obs,
        {
            "projection": "cohort_specific_slopes",
            "cohort_slopes": cohort_summary,
        },
    )


def _cell_means(
    values: np.ndarray, inverse: np.ndarray, cell_weight: np.ndarray, weights: np.ndarray
) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim == 1:
        return np.bincount(inverse, weights=weights * array) / np.maximum(cell_weight, 1e-12)
    columns = [
        np.bincount(inverse, weights=weights * array[:, idx]) / np.maximum(cell_weight, 1e-12)
        for idx in range(array.shape[1])
    ]
    return np.column_stack(columns)


def _two_way_demean(
    values: np.ndarray,
    cohort_inverse: np.ndarray,
    period_inverse: np.ndarray,
    weights: np.ndarray,
) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    one_dim = array.ndim == 1
    if one_dim:
        array = array.reshape(-1, 1)

    cohort_weight = np.bincount(cohort_inverse, weights=weights)
    period_weight = np.bincount(period_inverse, weights=weights)
    overall = np.sum(array * weights[:, None], axis=0) / max(np.sum(weights), 1e-12)
    demeaned = np.empty_like(array)

    for idx in range(array.shape[1]):
        column = array[:, idx]
        cohort_mean = np.bincount(cohort_inverse, weights=weights * column) / np.maximum(
            cohort_weight, 1e-12
        )
        period_mean = np.bincount(period_inverse, weights=weights * column) / np.maximum(
            period_weight, 1e-12
        )
        demeaned[:, idx] = (
            column - cohort_mean[cohort_inverse] - period_mean[period_inverse] + overall[idx]
        )

    return demeaned[:, 0] if one_dim else demeaned


def _cohort_slope_grid(cohort_slopes: Mapping[str, float]) -> dict[str, Any] | None:
    if not cohort_slopes:
        return None
    values = np.asarray(list(cohort_slopes.values()), dtype=float)
    summary: dict[str, Any] = {
        "mean": float(np.mean(values)),
        "p10": float(np.quantile(values, 0.1)),
        "p50": float(np.quantile(values, 0.5)),
        "p90": float(np.quantile(values, 0.9)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "cohort_count": int(values.size),
        "cohort_slopes": {str(key): float(value) for key, value in cohort_slopes.items()},
    }
    return summary


def _pseudo_panel_grouping_iv_projection(
    log_income: np.ndarray,
    log_price: np.ndarray,
    cohort_id: np.ndarray,
    period_id: np.ndarray,
    instrument: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, dict[str, float], dict[str, Any], int]:
    z_design = _as_numeric_design(instrument, n_obs=log_income.shape[0])
    cell_labels = np.char.add(cohort_id.astype(str), np.char.add("::", period_id.astype(str)))
    _, inverse = np.unique(cell_labels, return_inverse=True)
    cell_weight = np.bincount(inverse, weights=weights)
    cell_count = np.bincount(inverse).astype(int)
    cell_income = _cell_means(log_income, inverse, cell_weight, weights)
    cell_price = _cell_means(log_price, inverse, cell_weight, weights)
    cell_instrument = _cell_means(z_design, inverse, cell_weight, weights)

    cohort_cell = np.empty(cell_weight.shape[0], dtype=object)
    period_cell = np.empty(cell_weight.shape[0], dtype=object)
    seen: set[int] = set()
    for obs_idx, cell_idx in enumerate(inverse):
        if int(cell_idx) in seen:
            continue
        cohort_cell[cell_idx] = cohort_id[obs_idx]
        period_cell[cell_idx] = period_id[obs_idx]
        seen.add(int(cell_idx))

    _, cohort_inverse = np.unique(cohort_cell.astype(str), return_inverse=True)
    _, period_inverse = np.unique(period_cell.astype(str), return_inverse=True)
    y_tilde = _two_way_demean(cell_income, cohort_inverse, period_inverse, cell_weight)
    x_tilde = _two_way_demean(cell_price, cohort_inverse, period_inverse, cell_weight)
    z_tilde = _two_way_demean(cell_instrument, cohort_inverse, period_inverse, cell_weight)

    sqrt_w = np.sqrt(np.clip(cell_weight, 0.0, None))
    zw = z_tilde * sqrt_w[:, None]
    xw = x_tilde * sqrt_w
    gamma, *_ = np.linalg.lstsq(zw, xw, rcond=None)
    x_hat = z_tilde @ gamma
    denominator = float(np.sum(cell_weight * x_hat * x_tilde))
    if abs(denominator) <= 1e-12:
        raise ValueError(
            "pseudo-panel IV first stage is too weak after cohort and period demeaning"
        )
    beta = float(np.sum(cell_weight * x_hat * y_tilde) / denominator)

    cohort_slopes: dict[str, float] = {}
    cohort_labels = np.unique(cohort_cell.astype(str))
    for cohort in cohort_labels:
        mask = cohort_cell.astype(str) == cohort
        if int(np.sum(mask)) < max(3, z_tilde.shape[1] + 1):
            continue
        zw_cohort = z_tilde[mask] * sqrt_w[mask, None]
        xw_cohort = x_tilde[mask] * sqrt_w[mask]
        gamma_cohort, *_ = np.linalg.lstsq(zw_cohort, xw_cohort, rcond=None)
        x_hat_cohort = z_tilde[mask] @ gamma_cohort
        denom_cohort = float(np.sum(cell_weight[mask] * x_hat_cohort * x_tilde[mask]))
        if abs(denom_cohort) <= 1e-12:
            continue
        cohort_slopes[cohort] = float(
            np.sum(cell_weight[mask] * x_hat_cohort * y_tilde[mask]) / denom_cohort
        )

    return (
        beta,
        cohort_slopes,
        {
            "projection": "pseudo_panel_grouping_iv",
            "cell_stage1_r2": _weighted_r2(x_tilde, x_hat, cell_weight),
            "cohort_slopes": cohort_slopes,
            "n_cells": int(cell_weight.shape[0]),
        },
        int(np.min(cell_count)),
    )


def _weighted_corr(x: np.ndarray, y: np.ndarray, weights: np.ndarray) -> float | None:
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(weights) & (weights > 0.0)
    if np.sum(mask) < 2:
        return None
    x_masked = x[mask]
    y_masked = y[mask]
    w_masked = weights[mask]
    x_centered = x_masked - _weighted_mean(x_masked, w_masked)
    y_centered = y_masked - _weighted_mean(y_masked, w_masked)
    numerator = float(np.sum(w_masked * x_centered * y_centered))
    denominator = math.sqrt(
        max(float(np.sum(w_masked * np.square(x_centered))), 1e-12)
        * max(float(np.sum(w_masked * np.square(y_centered))), 1e-12)
    )
    return numerator / denominator if denominator > 0.0 else None


def _feature_local_variation_share(
    log_price: np.ndarray,
    features: np.ndarray,
    weights: np.ndarray,
    *,
    variation_floor: float,
    n_bins: int = 4,
) -> float:
    if features.shape[1] == 0:
        return (
            1.0 if math.sqrt(max(_weighted_var(log_price, weights), 0.0)) > variation_floor else 0.0
        )

    anchor = features[:, 0]
    finite = np.isfinite(anchor)
    if np.sum(finite) < n_bins:
        return (
            1.0 if math.sqrt(max(_weighted_var(log_price, weights), 0.0)) > variation_floor else 0.0
        )

    quantiles = np.quantile(anchor[finite], np.linspace(0.0, 1.0, n_bins + 1))
    edges = np.unique(quantiles)
    if edges.size <= 2:
        return (
            1.0 if math.sqrt(max(_weighted_var(log_price, weights), 0.0)) > variation_floor else 0.0
        )

    good_bins = 0
    total_bins = 0
    for idx in range(edges.size - 1):
        lo = edges[idx]
        hi = edges[idx + 1]
        if idx == edges.size - 2:
            mask = (anchor >= lo) & (anchor <= hi)
        else:
            mask = (anchor >= lo) & (anchor < hi)
        if np.sum(mask) < 2:
            continue
        total_bins += 1
        if math.sqrt(max(_weighted_var(log_price[mask], weights[mask]), 0.0)) > variation_floor:
            good_bins += 1
    if total_bins == 0:
        return 0.0
    return float(good_bins / total_bins)


def _overlap_score(net_rate: np.ndarray, instrument: np.ndarray) -> float | None:
    encoded = _instrument_score(instrument)
    finite_mask = np.isfinite(net_rate) & np.isfinite(encoded)
    if np.sum(finite_mask) < 4:
        return None
    encoded = encoded[finite_mask]
    net_rate = net_rate[finite_mask]
    if np.unique(encoded).size < 2:
        return None
    cutoff = float(np.median(encoded))
    low = net_rate[encoded <= cutoff]
    high = net_rate[encoded > cutoff]
    if low.size < 2 or high.size < 2:
        return None
    low_interval = np.quantile(low, [0.1, 0.9])
    high_interval = np.quantile(high, [0.1, 0.9])
    overlap = max(
        0.0,
        min(float(low_interval[1]), float(high_interval[1]))
        - max(float(low_interval[0]), float(high_interval[0])),
    )
    span = max(
        float(max(low_interval[1], high_interval[1]) - min(low_interval[0], high_interval[0])),
        1e-12,
    )
    return overlap / span


def _first_stage_strength(
    log_price: np.ndarray,
    instrument: np.ndarray,
    controls: np.ndarray,
    weights: np.ndarray,
) -> float | None:
    z_design = _as_numeric_design(instrument, n_obs=log_price.shape[0])
    mask = np.isfinite(log_price) & np.isfinite(weights) & (weights > 0.0)
    if controls.shape[1] > 0:
        mask &= np.isfinite(controls).all(axis=1)
    mask &= np.isfinite(z_design).all(axis=1)
    if np.sum(mask) <= controls.shape[1] + z_design.shape[1] + 2:
        return None
    if np.linalg.matrix_rank(z_design[mask]) == 0:
        return None

    x_controls = (
        np.column_stack([np.ones(np.sum(mask), dtype=float), controls[mask]])
        if controls.shape[1] > 0
        else np.ones((np.sum(mask), 1), dtype=float)
    )
    x_full = np.column_stack([x_controls, z_design[mask]])
    _, _, ssr_restricted = _solve_weighted_least_squares(log_price[mask], x_controls, weights[mask])
    _, _, ssr_full = _solve_weighted_least_squares(log_price[mask], x_full, weights[mask])
    df_num = x_full.shape[1] - x_controls.shape[1]
    df_den = max(np.sum(mask) - x_full.shape[1], 1)
    if ssr_full <= 1e-12:
        return float("inf")
    f_stat = ((ssr_restricted - ssr_full) / max(df_num, 1)) / (ssr_full / df_den)
    return max(float(f_stat), 0.0)


def _condition_number(log_price: np.ndarray, controls: np.ndarray, weights: np.ndarray) -> float:
    design = (
        np.column_stack([np.ones(log_price.shape[0], dtype=float), log_price, controls])
        if controls.shape[1] > 0
        else np.column_stack([np.ones(log_price.shape[0], dtype=float), log_price])
    )
    sqrt_w = np.sqrt(np.clip(weights, 0.0, None))
    weighted_design = design * sqrt_w[:, None]
    gram = weighted_design.T @ weighted_design
    try:
        return float(np.linalg.cond(gram))
    except np.linalg.LinAlgError:
        return float("inf")


def _detect_regime(
    household_ids: np.ndarray | None, period_id: np.ndarray | None
) -> tuple[str, int, float]:
    if period_id is None:
        return "cross_section", 1, 1.0

    unique_periods = int(np.unique(period_id).size)
    if household_ids is None:
        return "repeated_cross_section", unique_periods, 1.0

    _, counts = np.unique(household_ids, return_counts=True)
    repeated = counts > 1
    median_periods = float(np.median(counts[repeated])) if np.any(repeated) else 1.0
    if np.any(repeated):
        return "panel", unique_periods, median_periods
    return "repeated_cross_section", unique_periods, median_periods


def _panel_within_slope(
    log_income: np.ndarray,
    log_price: np.ndarray,
    household_ids: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, float]:
    labels, inverse = np.unique(household_ids.astype(str), return_inverse=True)
    _ = labels
    group_weight = np.bincount(inverse, weights=weights)
    mean_income = np.bincount(inverse, weights=weights * log_income) / np.maximum(
        group_weight, 1e-12
    )
    mean_price = np.bincount(inverse, weights=weights * log_price) / np.maximum(group_weight, 1e-12)
    y_tilde = log_income - mean_income[inverse]
    x_tilde = log_price - mean_price[inverse]
    denominator = float(np.sum(weights * np.square(x_tilde)))
    if denominator <= 1e-12:
        raise ValueError("panel within variation is too small to estimate elasticity")
    beta = float(np.sum(weights * x_tilde * y_tilde) / denominator)
    within_sd = math.sqrt(max(_weighted_var(x_tilde, weights), 0.0))
    return beta, within_sd


def _pseudo_panel_slope(
    log_income: np.ndarray,
    log_price: np.ndarray,
    cohort_id: np.ndarray,
    period_id: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, int]:
    cell_labels = np.char.add(cohort_id.astype(str), np.char.add("::", period_id.astype(str)))
    _, inverse = np.unique(cell_labels, return_inverse=True)
    cell_weight = np.bincount(inverse, weights=weights)
    cell_income = np.bincount(inverse, weights=weights * log_income) / np.maximum(
        cell_weight, 1e-12
    )
    cell_price = np.bincount(inverse, weights=weights * log_price) / np.maximum(cell_weight, 1e-12)
    cell_count = np.bincount(inverse).astype(int)

    cohort_cell = np.empty(cell_weight.shape[0], dtype=object)
    period_cell = np.empty(cell_weight.shape[0], dtype=object)
    seen: set[int] = set()
    for obs_idx, cell_idx in enumerate(inverse):
        if int(cell_idx) in seen:
            continue
        cohort_cell[cell_idx] = cohort_id[obs_idx]
        period_cell[cell_idx] = period_id[obs_idx]
        seen.add(int(cell_idx))

    _, cohort_inverse = np.unique(cohort_cell.astype(str), return_inverse=True)
    _, period_inverse = np.unique(period_cell.astype(str), return_inverse=True)

    cohort_weight = np.bincount(cohort_inverse, weights=cell_weight)
    period_weight = np.bincount(period_inverse, weights=cell_weight)
    cohort_income = np.bincount(cohort_inverse, weights=cell_weight * cell_income) / np.maximum(
        cohort_weight, 1e-12
    )
    cohort_price = np.bincount(cohort_inverse, weights=cell_weight * cell_price) / np.maximum(
        cohort_weight, 1e-12
    )
    period_income = np.bincount(period_inverse, weights=cell_weight * cell_income) / np.maximum(
        period_weight, 1e-12
    )
    period_price = np.bincount(period_inverse, weights=cell_weight * cell_price) / np.maximum(
        period_weight, 1e-12
    )

    grand_income = _weighted_mean(cell_income, cell_weight)
    grand_price = _weighted_mean(cell_price, cell_weight)
    y_tilde = (
        cell_income - cohort_income[cohort_inverse] - period_income[period_inverse] + grand_income
    )
    x_tilde = cell_price - cohort_price[cohort_inverse] - period_price[period_inverse] + grand_price
    denominator = float(np.sum(cell_weight * np.square(x_tilde)))
    if denominator <= 1e-12:
        raise ValueError("pseudo-panel variation is too small to estimate elasticity")
    beta = float(np.sum(cell_weight * x_tilde * y_tilde) / denominator)
    return beta, int(np.min(cell_count))


def _cross_section_slope(
    log_income: np.ndarray,
    log_price: np.ndarray,
    controls: np.ndarray,
    weights: np.ndarray,
) -> float:
    design = (
        np.column_stack([np.ones(log_income.shape[0], dtype=float), controls, log_price])
        if controls.shape[1] > 0
        else np.column_stack([np.ones(log_income.shape[0], dtype=float), log_price])
    )
    beta, _, _ = _solve_weighted_least_squares(log_income, design, weights)
    return float(beta[-1])


def _iv_proxy_slope(
    log_income: np.ndarray,
    log_price: np.ndarray,
    instrument: np.ndarray,
    controls: np.ndarray,
    weights: np.ndarray,
) -> float:
    encoded = _encode_numeric(instrument)
    x_stage1 = (
        np.column_stack([np.ones(log_income.shape[0], dtype=float), controls, encoded])
        if controls.shape[1] > 0
        else np.column_stack([np.ones(log_income.shape[0], dtype=float), encoded])
    )
    _, fitted_price, _ = _solve_weighted_least_squares(log_price, x_stage1, weights)
    x_stage2 = (
        np.column_stack([np.ones(log_income.shape[0], dtype=float), controls, fitted_price])
        if controls.shape[1] > 0
        else np.column_stack([np.ones(log_income.shape[0], dtype=float), fitted_price])
    )
    beta, _, _ = _solve_weighted_least_squares(log_income, x_stage2, weights)
    return float(beta[-1])


def _apply_behavioral_adjustment(
    income: np.ndarray,
    net_rate: np.ndarray,
    weights: np.ndarray,
    elasticity: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    baseline = _weighted_mean(net_rate, weights)
    adjusted_income = income * np.power(net_rate / max(baseline, 1e-3), elasticity)
    change = adjusted_income - income
    return adjusted_income, change, baseline


def _apply_behavioral_bounds(
    income: np.ndarray,
    net_rate: np.ndarray,
    weights: np.ndarray,
    elasticity_lower: float,
    elasticity_upper: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    lower_income, _, baseline = _apply_behavioral_adjustment(
        income,
        net_rate,
        weights,
        float(elasticity_lower),
    )
    upper_income, _, _ = _apply_behavioral_adjustment(
        income,
        net_rate,
        weights,
        float(elasticity_upper),
    )
    midpoint_income = 0.5 * (lower_income + upper_income)
    midpoint_change = midpoint_income - income
    return midpoint_income, midpoint_change, lower_income, upper_income, baseline


def _elasticity_grid_summary(
    elasticity_by_obs: np.ndarray | None,
    weights: np.ndarray,
    *,
    feature_names: tuple[str, ...] = (),
    controls: np.ndarray | None = None,
    weighted_mean_income_lower: float | None = None,
    weighted_mean_income_upper: float | None = None,
) -> dict[str, Any] | None:
    if elasticity_by_obs is None:
        summary: dict[str, Any] = {}
    else:
        summary = {
            "mean": _weighted_mean(elasticity_by_obs, weights),
            "p10": _weighted_quantile(elasticity_by_obs, weights, 0.1),
            "p50": _weighted_quantile(elasticity_by_obs, weights, 0.5),
            "p90": _weighted_quantile(elasticity_by_obs, weights, 0.9),
            "min": float(np.min(elasticity_by_obs)),
            "max": float(np.max(elasticity_by_obs)),
        }
        if controls is not None and controls.shape[1] > 0:
            for idx, name in enumerate(feature_names[: min(len(feature_names), 2)]):
                anchor = controls[:, idx]
                cutoff = _weighted_quantile(anchor, weights, 0.5)
                low_mask = anchor <= cutoff
                high_mask = anchor > cutoff
                if np.any(low_mask):
                    summary[f"{name}:low_mean"] = _weighted_mean(
                        elasticity_by_obs[low_mask], weights[low_mask]
                    )
                if np.any(high_mask):
                    summary[f"{name}:high_mean"] = _weighted_mean(
                        elasticity_by_obs[high_mask], weights[high_mask]
                    )
    if weighted_mean_income_lower is not None and weighted_mean_income_upper is not None:
        ordered = sorted((float(weighted_mean_income_lower), float(weighted_mean_income_upper)))
        summary["weighted_mean_income_lower"] = ordered[0]
        summary["weighted_mean_income_upper"] = ordered[1]
    else:
        if weighted_mean_income_lower is not None:
            summary["weighted_mean_income_lower"] = float(weighted_mean_income_lower)
        if weighted_mean_income_upper is not None:
            summary["weighted_mean_income_upper"] = float(weighted_mean_income_upper)
    return summary or None


def _groupwise_slope_bounds(
    log_income: np.ndarray,
    log_price: np.ndarray,
    controls: np.ndarray,
    weights: np.ndarray,
    group_values: np.ndarray,
    *,
    variation_floor: float,
    min_obs: int | None = None,
) -> tuple[float, float, list[dict[str, Any]]] | None:
    if min_obs is None:
        min_obs = max(6, controls.shape[1] + 3)
    encoded = _instrument_score(group_values)
    if np.unique(encoded).size < 2:
        return None

    slopes: list[dict[str, Any]] = []
    quantile_edges = np.unique(np.quantile(encoded, [0.0, 0.33, 0.67, 1.0]))
    if quantile_edges.size < 3:
        cutoff = float(np.median(encoded))
        bins = [
            ("low", encoded <= cutoff),
            ("high", encoded > cutoff),
        ]
    else:
        bins = []
        for idx in range(quantile_edges.size - 1):
            lo = quantile_edges[idx]
            hi = quantile_edges[idx + 1]
            if idx == quantile_edges.size - 2:
                mask = (encoded >= lo) & (encoded <= hi)
            else:
                mask = (encoded >= lo) & (encoded < hi)
            bins.append((f"bin_{idx}", mask))

    for group, mask in bins:
        if int(np.sum(mask)) < min_obs:
            continue
        if math.sqrt(max(_weighted_var(log_price[mask], weights[mask]), 0.0)) <= variation_floor:
            continue
        slope = _cross_section_slope(
            log_income[mask], log_price[mask], controls[mask], weights[mask]
        )
        slopes.append(
            {
                "group": str(group),
                "elasticity": float(slope),
                "weight_share": float(np.sum(weights[mask]) / max(np.sum(weights), 1e-12)),
            }
        )
    if len(slopes) < 2:
        return None
    slope_values = np.asarray([item["elasticity"] for item in slopes], dtype=float)
    return float(np.min(slope_values)), float(np.max(slope_values)), slopes


def _local_kink_elasticity(
    income: np.ndarray,
    net_rate: np.ndarray,
    weights: np.ndarray,
    kink_points: np.ndarray,
    *,
    bandwidth: float,
    min_side_obs: int,
) -> tuple[float, float, float, list[dict[str, Any]]] | None:
    log_income = np.log(np.clip(income, 1e-3, None))
    log_price = np.log(np.clip(net_rate, 1e-6, None))
    point_estimates: list[float] = []
    local_payloads: list[dict[str, Any]] = []

    for point in kink_points:
        left_mask = (income >= point - bandwidth) & (income < point)
        right_mask = (income > point) & (income <= point + bandwidth)
        if int(np.sum(left_mask)) < min_side_obs or int(np.sum(right_mask)) < min_side_obs:
            continue
        left_price = _weighted_mean(log_price[left_mask], weights[left_mask])
        right_price = _weighted_mean(log_price[right_mask], weights[right_mask])
        denominator = right_price - left_price
        if abs(denominator) <= 1e-9:
            continue
        left_income = _weighted_mean(log_income[left_mask], weights[left_mask])
        right_income = _weighted_mean(log_income[right_mask], weights[right_mask])
        estimate = float((right_income - left_income) / denominator)
        point_estimates.append(estimate)
        local_payloads.append(
            {
                "point": float(point),
                "bandwidth": float(bandwidth),
                "estimate": estimate,
                "left_n": int(np.sum(left_mask)),
                "right_n": int(np.sum(right_mask)),
            }
        )

    if not point_estimates:
        return None
    estimates = np.asarray(point_estimates, dtype=float)
    center = float(np.mean(estimates))
    return center, float(np.min(estimates)), float(np.max(estimates)), local_payloads


def _metric_status(
    value: float | None, *, identified_threshold: float, sloppy_threshold: float
) -> IdentifiabilityStatus:
    if value is None or not math.isfinite(value):
        return IdentifiabilityStatus.NON_IDENTIFIED
    if value >= identified_threshold:
        return IdentifiabilityStatus.IDENTIFIED
    if value >= sloppy_threshold:
        return IdentifiabilityStatus.SLOPPY
    return IdentifiabilityStatus.NON_IDENTIFIED


def _build_identifiability_report(
    *,
    effective_sample_size: float,
    minimum_effective_sample_size: float,
    variation_sd: float,
    variation_floor: float,
    first_stage_strength: float | None,
    minimum_first_stage_strength: float,
    overlap_score: float | None,
    minimum_overlap_score: float,
    measurement_reliability: float | None,
    condition_number: float,
) -> tuple[IdentifiabilityReport, str]:
    metrics = [
        (
            "effective_sample_size",
            effective_sample_size / max(minimum_effective_sample_size, 1e-12),
            max(effective_sample_size, 1.0),
        ),
        (
            "price_variation",
            variation_sd / max(variation_floor, 1e-12),
            max(variation_sd, 1e-12),
        ),
        (
            "first_stage_strength",
            None
            if first_stage_strength is None
            else first_stage_strength / max(minimum_first_stage_strength, 1e-12),
            max(first_stage_strength or 1.0, 1.0),
        ),
        (
            "support_overlap",
            None if overlap_score is None else overlap_score / max(minimum_overlap_score, 1e-12),
            max(overlap_score or 1.0, 1e-6),
        ),
        (
            "measurement_reliability",
            measurement_reliability,
            max(measurement_reliability or 1.0, 1e-6),
        ),
        (
            "numerical_stability",
            0.0
            if not math.isfinite(condition_number)
            else 1.0 / max(math.log10(max(condition_number, 10.0)), 1.0),
            max(condition_number, 1.0),
        ),
    ]

    params: list[ParamIdentifiability] = []
    for name, score, raw_value in metrics:
        if score is None:
            continue
        status = _metric_status(score, identified_threshold=1.0, sloppy_threshold=0.5)
        params.append(
            ParamIdentifiability(
                name=name,
                status=status,
                eigenvalue=0.0 if score is None or not math.isfinite(score) else float(score),
                std=float(1.0 / math.sqrt(max(raw_value, 1e-12))),
            )
        )

    n_identified = sum(param.status is IdentifiabilityStatus.IDENTIFIED for param in params)
    n_sloppy = sum(param.status is IdentifiabilityStatus.SLOPPY for param in params)
    n_non_identified = sum(param.status is IdentifiabilityStatus.NON_IDENTIFIED for param in params)
    report = IdentifiabilityReport(
        params=params,
        n_identified=n_identified,
        n_sloppy=n_sloppy,
        n_non_identified=n_non_identified,
        effective_dimension=n_identified + n_sloppy,
    )
    if n_non_identified > 0:
        overall = IdentifiabilityStatus.NON_IDENTIFIED.value
    elif n_sloppy > 0:
        overall = IdentifiabilityStatus.SLOPPY.value
    else:
        overall = IdentifiabilityStatus.IDENTIFIED.value
    return report, overall


def _behavioral_preflight(
    *,
    state: Mapping[str, Any],
    income: np.ndarray,
    weights: np.ndarray,
    net_rate: np.ndarray,
    controls: np.ndarray,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    metadata = _behavioral_metadata(state)
    n_obs = income.shape[0]
    household_ids = _optional_vector(state, "household_ids", n_obs)
    period_id = _optional_vector(state, "period_id", n_obs)
    cohort_id = _optional_vector(state, "cohort_id", n_obs)
    instrument_z = _optional_design(state, "instrument_z", n_obs)
    income_repeat_measure = _optional_vector(state, "income_repeat_measure", n_obs)
    taxrate_repeat_measure = _optional_vector(state, "taxrate_repeat_measure", n_obs)
    kink_points = _coerce_point_array(_metadata_value(state, "kink_points"))
    notch_points = _coerce_point_array(_metadata_value(state, "notch_points"))
    schedule_segments = _metadata_value(state, "schedule_segments")

    regime, unique_periods, median_periods = _detect_regime(household_ids, period_id)
    minimum_effective_sample_size = float(params.get("minimum_effective_sample_size", 5000.0))
    minimum_first_stage_strength = float(params.get("minimum_first_stage_strength", 10.0))
    minimum_overlap_score = float(params.get("minimum_overlap_score", 0.1))
    repeated_cross_section_min_periods = int(params.get("repeated_cross_section_min_periods", 3))
    panel_min_periods = int(params.get("panel_min_periods", 3))
    minimum_cohort_cell_size = int(params.get("minimum_cohort_cell_size", 200))
    variation_floor = float(params.get("variation_floor", 1e-4))
    assume_exogenous_price = bool(params.get("assume_exogenous_price", False))
    manual_elasticity = params.get("manual_elasticity", params.get("elasticity"))

    log_income = np.log(np.clip(income, 1e-3, None))
    log_price = np.log(np.clip(net_rate, 1e-6, None))
    n_eff = _effective_sample_size(weights)
    variation_sd = math.sqrt(max(_weighted_var(log_price, weights), 0.0))
    local_variation_share = _feature_local_variation_share(
        log_price,
        controls,
        weights,
        variation_floor=variation_floor,
    )
    first_stage = (
        None
        if instrument_z is None
        else _first_stage_strength(log_price, instrument_z, controls, weights)
    )
    overlap = None if instrument_z is None else _overlap_score(net_rate, instrument_z)

    measurement_reliability = None
    if taxrate_repeat_measure is not None:
        repeated_net_rate = np.clip(
            1.0 - np.asarray(taxrate_repeat_measure, dtype=float), 1e-3, None
        )
        measurement_reliability = _weighted_corr(
            np.log(net_rate), np.log(repeated_net_rate), weights
        )
    elif income_repeat_measure is not None:
        measurement_reliability = _weighted_corr(
            log_income,
            np.log(np.clip(np.asarray(income_repeat_measure, dtype=float), 1e-3, None)),
            weights,
        )

    condition_number = _condition_number(log_price, controls, weights)
    has_local_budget_points = (kink_points is not None and kink_points.size > 0) or (
        notch_points is not None and notch_points.size > 0
    )
    has_budget_set_metadata = has_local_budget_points or schedule_segments is not None
    block_reasons: list[str] = []
    warnings: list[str] = []
    assumptions: list[str] = [
        "partial_equilibrium",
        "design_weights_interpreted_as_sampling_weights",
        "log_linear_proxy_response_model",
    ]

    estimation_mode = "blocked"
    identified_object = "not_identified"
    if manual_elasticity is not None:
        estimation_mode = "manual_override"
        identified_object = "manual_override_required"
        warnings.append("manual_elasticity_override_not_estimated_from_data")
    elif regime == "panel":
        if period_id is None or household_ids is None:
            block_reasons.append("panel_mode_requires_household_ids_and_period_id")
        if unique_periods < panel_min_periods or median_periods < panel_min_periods:
            block_reasons.append("insufficient_panel_periods")
        if variation_sd <= variation_floor:
            block_reasons.append("insufficient_net_of_tax_variation")
        if n_eff < minimum_effective_sample_size:
            block_reasons.append("effective_sample_size_below_threshold")
        if not block_reasons:
            estimation_mode = "panel_within"
            identified_object = "conditional_mean_eta"
            assumptions.append("within_household_variation_identifies_average_partial_effect")
            if median_periods <= max(panel_min_periods, 3):
                warnings.append("short_panel_irregular_identification")
    elif regime == "repeated_cross_section":
        if period_id is None or cohort_id is None:
            block_reasons.append("repeated_cross_section_requires_period_id_and_cohort_id")
        if unique_periods < repeated_cross_section_min_periods:
            block_reasons.append("insufficient_repeated_cross_section_periods")
        if variation_sd <= variation_floor:
            block_reasons.append("insufficient_net_of_tax_variation")
        if n_eff < minimum_effective_sample_size:
            block_reasons.append("effective_sample_size_below_threshold")
        if instrument_z is not None:
            if first_stage is None or first_stage < minimum_first_stage_strength:
                block_reasons.append("weak_identification_first_stage")
            if overlap is None or overlap < minimum_overlap_score:
                if first_stage is not None and first_stage >= minimum_first_stage_strength:
                    estimation_mode = "bounds_only_iv"
                    identified_object = "bounds_only"
                    warnings.append("point_identification_blocked_returning_overlap_bounds")
                else:
                    block_reasons.append("insufficient_overlap")
        if not block_reasons:
            estimation_mode = "pseudo_panel_iv" if instrument_z is not None else "pseudo_panel"
            identified_object = "conditional_mean_eta"
            assumptions.append(
                "grouping_iv_for_pseudo_panel"
                if instrument_z is not None
                else "cohort_stability_for_pseudo_panel"
            )
            warnings.append(f"minimum_cohort_cell_size_target:{minimum_cohort_cell_size}")
    else:
        if instrument_z is not None:
            if variation_sd <= variation_floor:
                block_reasons.append("insufficient_net_of_tax_variation")
            if n_eff < minimum_effective_sample_size:
                block_reasons.append("effective_sample_size_below_threshold")
            if first_stage is None or first_stage < minimum_first_stage_strength:
                block_reasons.append("weak_identification_first_stage")
            if overlap is None or overlap < minimum_overlap_score:
                if first_stage is not None and first_stage >= minimum_first_stage_strength:
                    estimation_mode = "bounds_only_iv"
                    identified_object = "bounds_only"
                    warnings.append("point_identification_blocked_returning_overlap_bounds")
                else:
                    block_reasons.append("insufficient_overlap")
            if not block_reasons:
                if estimation_mode != "bounds_only_iv":
                    estimation_mode = "iv_proxy"
                    identified_object = "conditional_mean_eta"
                assumptions.append("excluded_instrument_identifies_average_response")
        elif assume_exogenous_price:
            if variation_sd <= variation_floor:
                block_reasons.append("insufficient_net_of_tax_variation")
            if n_eff < minimum_effective_sample_size:
                block_reasons.append("effective_sample_size_below_threshold")
            if measurement_reliability is not None and measurement_reliability < 0.25:
                block_reasons.append("low_measurement_reliability")
            if local_variation_share < 0.5:
                warnings.append("limited_local_variation_within_feature_support")
            if not block_reasons:
                estimation_mode = "exogenous_wls"
                identified_object = "conditional_mean_eta"
                assumptions.append("conditional_exogeneity_of_net_of_tax_rate")
        else:
            if has_local_budget_points:
                estimation_mode = "local_kink"
                identified_object = "local_average_eta"
                assumptions.append("local_bunching_style_identification_near_kink_or_notch")
            else:
                if has_budget_set_metadata:
                    block_reasons.append("budget_set_identification_detected_but_not_implemented")
                block_reasons.append("cross_section_requires_iv_panel_or_exogeneity_assumption")

    report, identifiability_status = _build_identifiability_report(
        effective_sample_size=n_eff,
        minimum_effective_sample_size=minimum_effective_sample_size,
        variation_sd=variation_sd,
        variation_floor=variation_floor,
        first_stage_strength=first_stage,
        minimum_first_stage_strength=minimum_first_stage_strength,
        overlap_score=overlap,
        minimum_overlap_score=minimum_overlap_score,
        measurement_reliability=measurement_reliability,
        condition_number=condition_number,
    )

    if estimation_mode == "manual_override" or estimation_mode == "blocked":
        identifiability_status = IdentifiabilityStatus.NON_IDENTIFIED.value
    elif (
        identifiability_status == IdentifiabilityStatus.NON_IDENTIFIED.value
        or warnings
        or (math.isfinite(condition_number) and condition_number > 1e6)
    ):
        identifiability_status = IdentifiabilityStatus.SLOPPY.value

    return {
        "regime": regime,
        "unique_periods": unique_periods,
        "median_periods": median_periods,
        "household_ids": household_ids,
        "period_id": period_id,
        "cohort_id": cohort_id,
        "instrument_z": instrument_z,
        "kink_points": kink_points,
        "notch_points": notch_points,
        "schedule_segments": schedule_segments,
        "manual_elasticity": None if manual_elasticity is None else float(manual_elasticity),
        "estimation_mode": estimation_mode,
        "identified_object": identified_object,
        "identifiability_report": report,
        "identifiability_status": identifiability_status,
        "block_reasons": block_reasons,
        "warnings": warnings,
        "assumptions": assumptions,
        "has_repeated_measurement": measurement_reliability is not None,
        "first_stage_strength": first_stage,
        "overlap_score": overlap,
        "measurement_reliability": measurement_reliability,
        "effective_sample_size": n_eff,
        "variation_sd": variation_sd,
        "local_variation_share": local_variation_share,
        "condition_number": condition_number,
        "minimum_cohort_cell_size": minimum_cohort_cell_size,
    }


@foundry_method(
    namespace="microsim.policy",
    version="1.0.0",
    tags={"microsim", "tax-benefit", "survey"},
)
class TaxBenefitCalculatorEstimator:
    """Simulate tax-benefit schedules when planners need post-policy household incomes."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="tax_benefit_calculator",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "survey"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("tax_benefit", "json"),
                    contract_id=TaxBenefitResult.contract_id,
                ),
                SlotSpec(
                    "disposable_income",
                    SlotType.VECTOR,
                    Unit("income", "currency"),
                    shape=("n_obs",),
                ),
                SlotSpec(
                    "tax_liability", SlotType.VECTOR, Unit("tax", "currency"), shape=("n_obs",)
                ),
                SlotSpec(
                    "benefit_income", SlotType.VECTOR, Unit("benefit", "currency"), shape=("n_obs",)
                ),
                SlotSpec(
                    "effective_tax_rate", SlotType.VECTOR, Unit("rate", "share"), shape=("n_obs",)
                ),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="allowance", default=10000.0),
            ParameterSpec(name="threshold_1", default=25000.0),
            ParameterSpec(name="threshold_2", default=60000.0),
            ParameterSpec(name="rate_1", default=0.1),
            ParameterSpec(name="rate_2", default=0.2),
            ParameterSpec(name="rate_3", default=0.32),
            ParameterSpec(name="benefit_floor", default=9000.0),
            ParameterSpec(name="benefit_taper", default=0.2),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Tax-benefit calculator producing liabilities, transfers, disposable income, and tax rates.",
        tags=frozenset({"microsim", "tax-benefit", "survey"}),
        when_to_use="First-order (mechanical) distributional impact of policy reform on existing population; tax/benefit calculator",
        citations=(
            "Immervoll, H. et al. (2006). Microsimulation of personal income tax and transfer systems. International Journal of Microsimulation, 1(1), 1-13.",
            "Sutherland, H. & Figari, F. (2013). EUROMOD: the European Union tax-benefit microsimulation model. International Journal of Microsimulation, 6(1), 4-26.",
        ),
        when_not_to_use="Need behavioral responses; dynamic effects matter (use dynamic microsim)",
        output_interpretation="Distribution of winners/losers. Change in Gini, poverty headcount. Budget cost at first round.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SurveyMicroData:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return SurveyMicroData.model_validate(payload)

    @staticmethod
    def pure_step(state: SurveyMicroData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state if isinstance(state, SurveyMicroData) else SurveyMicroData.model_validate(state)
        )
        income = np.asarray(data.market_income, dtype=float)
        weights = np.asarray(data.weights, dtype=float)
        allowance = float(params.get("allowance", 10000.0))
        threshold_1 = float(params.get("threshold_1", 25000.0))
        threshold_2 = float(params.get("threshold_2", 60000.0))
        rate_1 = float(params.get("rate_1", 0.1))
        rate_2 = float(params.get("rate_2", 0.2))
        rate_3 = float(params.get("rate_3", 0.32))
        benefit_floor = float(params.get("benefit_floor", 9000.0))
        benefit_taper = float(params.get("benefit_taper", 0.2))

        taxable = np.maximum(income - allowance, 0.0)
        band1 = np.minimum(taxable, np.maximum(threshold_1 - allowance, 0.0))
        band2 = np.minimum(
            np.maximum(taxable - band1, 0.0), np.maximum(threshold_2 - threshold_1, 0.0)
        )
        band3 = np.maximum(taxable - band1 - band2, 0.0)
        tax_liability = rate_1 * band1 + rate_2 * band2 + rate_3 * band3
        benefit_income = np.maximum(benefit_floor - benefit_taper * income, 0.0)
        disposable_income = income - tax_liability + benefit_income

        marginal_tax_rate = np.where(
            income <= allowance,
            0.0,
            np.where(
                income <= threshold_1, rate_1, np.where(income <= threshold_2, rate_2, rate_3)
            ),
        )
        effective_tax_rate = np.where(
            income > 1e-9,
            (tax_liability - benefit_income) / income,
            0.0,
        )
        result = TaxBenefitResult(
            disposable_income=disposable_income,
            tax_liability=tax_liability,
            benefit_income=benefit_income,
            marginal_tax_rate=marginal_tax_rate,
            effective_tax_rate=effective_tax_rate,
            weighted_mean_disposable_income=_weighted_mean(disposable_income, weights),
            policy_revenue=float(np.sum((tax_liability - benefit_income) * weights)),
            metadata={
                "allowance": allowance,
                "threshold_1": threshold_1,
                "threshold_2": threshold_2,
            },
        )
        return {
            "result": result,
            "disposable_income": disposable_income,
            "tax_liability": tax_liability,
            "benefit_income": benefit_income,
            "effective_tax_rate": effective_tax_rate,
            "uncertainty_envelope": result.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="microsim.behavior",
    version="1.0.0",
    tags={"microsim", "behavioral-response", "survey"},
)
class BehavioralResponseEstimator:
    """Model labor-supply or income responses after a tax-benefit reform."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="behavioral_response",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "survey"), shape=("n_obs",)),
                SlotSpec(
                    "effective_tax_rate", SlotType.VECTOR, Unit("rate", "share"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("behavior", "json"),
                    contract_id=BehavioralResponseResult.contract_id,
                ),
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(ParameterSpec(name="elasticity", default=0.2),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Behavioral income response to tax wedges using a labor-supply elasticity rule.",
        tags=frozenset({"microsim", "behavioral-response", "survey"}),
        when_to_use="Policy with significant labor supply or consumption behavioral responses; structural microsim",
        citations=(
            "Saez, E. (2001). Using elasticities to derive optimal income tax rates. Review of Economic Studies, 68(1), 205-229.",
            "Immervoll, H. et al. (2007). Welfare reform in European countries: A microsimulation analysis. The Economic Journal, 117(516), 1-44.",
        ),
        when_not_to_use="Behavioral responses negligible; elasticity estimates unavailable or highly uncertain",
        output_interpretation="Behavioral + first-round effects. Elasticities determine magnitude of behavioral response.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("behavioral_response expects mapping input")
        income = np.asarray(state["market_income"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        if "effective_tax_rate" not in state:
            raise ValueError("behavioral_response requires effective_tax_rate input")
        effective_tax_rate = np.asarray(state["effective_tax_rate"], dtype=float)
        elasticity = float(params.get("elasticity", 0.2))
        net_rate = np.clip(1.0 - effective_tax_rate, 1e-3, None)
        baseline = float(np.mean(net_rate))
        adjusted_income = income * np.power(net_rate / max(baseline, 1e-3), elasticity)
        change = adjusted_income - income
        result = BehavioralResponseResult(
            adjusted_market_income=adjusted_income,
            labor_supply_change=change,
            weighted_mean_income=_weighted_mean(adjusted_income, weights),
            elasticity=elasticity,
            metadata={"baseline_net_rate": baseline},
        )
        return {
            "result": result,
            "market_income": adjusted_income,
            "uncertainty_envelope": result.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="microsim.behavior",
    version="2.0.0",
    tags={"microsim", "behavioral-response", "survey", "identifiability"},
)
class HeterogeneousBehavioralResponseEstimator:
    """Estimate only those behavioral elasticities that are supportable from the available data."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="behavioral_response",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "survey"), shape=("n_obs",)),
                SlotSpec(
                    "effective_tax_rate", SlotType.VECTOR, Unit("rate", "share"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("behavior", "json"),
                    contract_id=HeterogeneousBehavioralResponseResult.contract_id,
                ),
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="manual_elasticity", default=None),
            ParameterSpec(name="assume_exogenous_price", default=False),
            ParameterSpec(name="minimum_effective_sample_size", default=5000.0),
            ParameterSpec(name="minimum_first_stage_strength", default=10.0),
            ParameterSpec(name="minimum_overlap_score", default=0.1),
            ParameterSpec(name="variation_floor", default=1e-4),
            ParameterSpec(name="repeated_cross_section_min_periods", default=3),
            ParameterSpec(name="panel_min_periods", default=3),
            ParameterSpec(name="minimum_cohort_cell_size", default=200),
            ParameterSpec(name="max_control_features", default=3),
            ParameterSpec(name="local_kink_bandwidth", default=None),
            ParameterSpec(name="local_kink_bandwidth_ratio", default=0.1),
            ParameterSpec(name="local_kink_bandwidth_min", default=1.0),
            ParameterSpec(name="local_kink_min_side_obs", default=5),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Behavioral-response estimator with explicit identification diagnostics and refusal modes.",
        tags=frozenset({"microsim", "behavioral-response", "survey", "identifiability"}),
        when_to_use="Need an estimated or explicitly blocked behavioral elasticity object rather than a silent scalar override",
        citations=(
            "Imbens, G. & Newey, W. (2009). Identification and Estimation of Triangular Simultaneous Equations Models Without Additivity. Econometrica, 77(5), 1481-1512.",
            "Graham, B. & Powell, J. (2012). Identification and Estimation of Average Partial Effects in Irregular Correlated Random Coefficient Panel Data Models. Econometrica, 80(5), 2105-2152.",
        ),
        when_not_to_use="Need a full structural control-function, CRC, or bunching estimator with inference beyond the proxy estimators implemented here",
        output_interpretation="Returns the identified object type, estimated mean elasticity when available, and a diagnostic trail explaining whether point identification was accepted or blocked.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> dict[str, Any]:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return payload

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise TypeError("behavioral_response expects mapping input")

        income = np.asarray(state["market_income"], dtype=float)
        weights = np.asarray(state["weights"], dtype=float)
        if income.ndim != 1 or weights.ndim != 1 or income.shape[0] != weights.shape[0]:
            raise ValueError("market_income and weights must be 1D arrays with matching length")

        rate, rate_source = _extract_tax_rate(state, income.shape[0])
        net_rate = np.clip(1.0 - rate, 1e-3, None)
        features = _optional_matrix(state, "features", income.shape[0])
        feature_names = _extract_feature_names(
            state,
            0
            if features is None
            else min(features.shape[1], max(0, int(params.get("max_control_features", 3)))),
        )
        max_control_features = max(0, int(params.get("max_control_features", 3)))
        controls, control_names = _prepare_controls(
            features,
            weights,
            feature_names=feature_names,
            max_features=max_control_features,
        )
        preflight = _behavioral_preflight(
            state=state,
            income=income,
            weights=weights,
            net_rate=net_rate,
            controls=controls,
            params=params,
        )

        diagnostics: dict[str, Any] = {
            "estimation_mode": preflight["estimation_mode"],
            "rate_source": rate_source,
            "block_reasons": list(preflight["block_reasons"]),
            "warnings": list(preflight["warnings"]),
            "assumptions": list(preflight["assumptions"]),
            "blocked": preflight["estimation_mode"] == "blocked",
            "variation_sd_log_net_rate": float(preflight["variation_sd"]),
            "local_variation_share": float(preflight["local_variation_share"]),
            "condition_number": float(preflight["condition_number"]),
            "unique_periods": int(preflight["unique_periods"]),
            "median_periods_per_household": float(preflight["median_periods"]),
            "feature_count_used": len(control_names),
            "has_repeated_measurement": bool(preflight["has_repeated_measurement"]),
        }

        elasticity_mean: float | None = None
        elasticity_by_obs: np.ndarray | None = None
        elasticity_lower: np.ndarray | None = None
        elasticity_upper: np.ndarray | None = None
        elasticity_grid: dict[str, Any] | None = None
        adjusted_income = np.asarray(income, dtype=float).copy()
        labor_supply_change = np.zeros_like(adjusted_income)
        baseline_net_rate = _weighted_mean(net_rate, weights)
        identified_object = preflight["identified_object"]
        identifiability_status = preflight["identifiability_status"]

        try:
            log_income = np.log(np.clip(income, 1e-3, None))
            log_price = np.log(np.clip(net_rate, 1e-6, None))
            if preflight["estimation_mode"] == "manual_override":
                elasticity_mean = float(preflight["manual_elasticity"])
                elasticity_by_obs = _constant_vector(elasticity_mean, income.shape[0])
            elif preflight["estimation_mode"] == "panel_within":
                if preflight["household_ids"] is None:
                    raise ValueError("panel estimator requires household_ids")
                elasticity_mean, within_sd = _panel_within_slope(
                    log_income,
                    log_price,
                    np.asarray(preflight["household_ids"]),
                    weights,
                )
                diagnostics["within_variation_sd"] = float(within_sd)
            elif preflight["estimation_mode"] == "pseudo_panel":
                if preflight["cohort_id"] is None or preflight["period_id"] is None:
                    raise ValueError("pseudo-panel estimator requires cohort_id and period_id")
                elasticity_mean, min_cell_size = _pseudo_panel_slope(
                    log_income,
                    log_price,
                    np.asarray(preflight["cohort_id"]),
                    np.asarray(preflight["period_id"]),
                    weights,
                )
                elasticity_mean, _, projection_details = _cohort_specific_elasticity_projection(
                    log_income,
                    log_price,
                    np.asarray(preflight["cohort_id"]),
                    np.asarray(preflight["period_id"]),
                    weights,
                )
                diagnostics.update(projection_details)
                diagnostics["observed_min_cohort_cell_size"] = int(min_cell_size)
                diagnostics["estimand_scope"] = "cohort_average_partial_effect"
                diagnostics["elasticity_by_obs_semantics"] = (
                    "not_returned_to_avoid_overclaiming_individual_identification"
                )
                elasticity_grid = _cohort_slope_grid(
                    projection_details.get("cohort_slopes", {})
                    if isinstance(projection_details, Mapping)
                    else {}
                )
                if min_cell_size < int(preflight["minimum_cohort_cell_size"]):
                    diagnostics["warnings"].append("cohort_cells_below_recommended_size")
                    identifiability_status = IdentifiabilityStatus.SLOPPY.value
            elif preflight["estimation_mode"] == "pseudo_panel_iv":
                if (
                    preflight["cohort_id"] is None
                    or preflight["period_id"] is None
                    or preflight["instrument_z"] is None
                ):
                    raise ValueError(
                        "pseudo-panel IV requires cohort_id, period_id, and instrument_z"
                    )
                elasticity_mean, cohort_slopes, projection_details, min_cell_size = (
                    _pseudo_panel_grouping_iv_projection(
                        log_income,
                        log_price,
                        np.asarray(preflight["cohort_id"]),
                        np.asarray(preflight["period_id"]),
                        np.asarray(preflight["instrument_z"]),
                        weights,
                    )
                )
                diagnostics.update(projection_details)
                diagnostics["observed_min_cohort_cell_size"] = int(min_cell_size)
                diagnostics["estimand_scope"] = "cohort_average_partial_effect"
                diagnostics["elasticity_by_obs_semantics"] = (
                    "not_returned_to_avoid_overclaiming_individual_identification"
                )
                elasticity_grid = _cohort_slope_grid(cohort_slopes)
                if min_cell_size < int(preflight["minimum_cohort_cell_size"]):
                    diagnostics["warnings"].append("cohort_cells_below_recommended_size")
                    identifiability_status = IdentifiabilityStatus.SLOPPY.value
            elif preflight["estimation_mode"] == "iv_proxy":
                if preflight["instrument_z"] is None:
                    raise ValueError("IV proxy requires instrument_z")
                elasticity_mean, elasticity_by_obs, projection_details = (
                    _iv_interacted_elasticity_projection(
                        log_income,
                        log_price,
                        np.asarray(preflight["instrument_z"]),
                        controls,
                        weights,
                    )
                )
                diagnostics.update(projection_details)
                diagnostics["estimand_scope"] = "conditional_mean_structural_elasticity"
            elif preflight["estimation_mode"] == "bounds_only_iv":
                if preflight["instrument_z"] is None:
                    raise ValueError("bounds-only IV mode requires instrument_z")
                bounds = _groupwise_slope_bounds(
                    log_income,
                    log_price,
                    controls,
                    weights,
                    np.asarray(preflight["instrument_z"]),
                    variation_floor=float(params.get("variation_floor", 1e-4)),
                )
                if bounds is None:
                    raise ValueError("unable to construct overlap bounds from instrument subgroups")
                lower_bound, upper_bound, subgroup_slopes = bounds
                identified_object = "bounds_only"
                elasticity_mean = 0.5 * (lower_bound + upper_bound)
                elasticity_by_obs = _constant_vector(elasticity_mean, income.shape[0])
                elasticity_lower = _constant_vector(lower_bound, income.shape[0])
                elasticity_upper = _constant_vector(upper_bound, income.shape[0])
                diagnostics["subgroup_bounds"] = subgroup_slopes
                diagnostics["bounds_reason"] = "insufficient_overlap"
                diagnostics["estimand_scope"] = "partial_identification_interval"
                identifiability_status = IdentifiabilityStatus.SLOPPY.value
            elif preflight["estimation_mode"] == "exogenous_wls":
                elasticity_mean, elasticity_by_obs, projection_details = (
                    _interacted_elasticity_projection(
                        log_income,
                        log_price,
                        controls,
                        weights,
                    )
                )
                diagnostics.update(projection_details)
                diagnostics["estimand_scope"] = "conditional_mean_structural_elasticity"
            elif preflight["estimation_mode"] == "local_kink":
                local_points = preflight["kink_points"]
                if local_points is None or local_points.size == 0:
                    local_points = preflight["notch_points"]
                if local_points is None or local_points.size == 0:
                    raise ValueError("local kink mode requires kink_points or notch_points")
                bandwidth = float(
                    params.get(
                        "local_kink_bandwidth",
                        max(
                            float(params.get("local_kink_bandwidth_min", 1.0)),
                            float(np.median(np.abs(local_points)))
                            * float(params.get("local_kink_bandwidth_ratio", 0.1)),
                        ),
                    )
                )
                local_fit = _local_kink_elasticity(
                    income,
                    net_rate,
                    weights,
                    np.asarray(local_points, dtype=float),
                    bandwidth=bandwidth,
                    min_side_obs=int(params.get("local_kink_min_side_obs", 5)),
                )
                if local_fit is None:
                    raise ValueError("insufficient local support around kink/notch points")
                elasticity_mean, lower_bound, upper_bound, local_payloads = local_fit
                identified_object = "local_average_eta"
                elasticity_by_obs = _constant_vector(elasticity_mean, income.shape[0])
                elasticity_lower = _constant_vector(lower_bound, income.shape[0])
                elasticity_upper = _constant_vector(upper_bound, income.shape[0])
                diagnostics["local_kink_estimates"] = local_payloads
                diagnostics["local_kink_bandwidth"] = bandwidth
                diagnostics["estimand_scope"] = "local_average_eta"
                identifiability_status = IdentifiabilityStatus.SLOPPY.value
        except ValueError as exc:
            diagnostics["block_reasons"].append(f"estimation_failed:{exc}")
            identified_object = "not_identified"
            identifiability_status = IdentifiabilityStatus.NON_IDENTIFIED.value
            elasticity_mean = None
            elasticity_by_obs = None
            elasticity_lower = None
            elasticity_upper = None

        if elasticity_mean is not None and np.isfinite(elasticity_mean):
            if elasticity_lower is not None and elasticity_upper is not None:
                (
                    adjusted_income,
                    labor_supply_change,
                    lower_income,
                    upper_income,
                    baseline_net_rate,
                ) = _apply_behavioral_bounds(
                    income,
                    net_rate,
                    weights,
                    float(np.nanmean(elasticity_lower)),
                    float(np.nanmean(elasticity_upper)),
                )
                elasticity_grid = _elasticity_grid_summary(
                    elasticity_by_obs,
                    weights,
                    feature_names=control_names,
                    controls=controls,
                    weighted_mean_income_lower=_weighted_mean(lower_income, weights),
                    weighted_mean_income_upper=_weighted_mean(upper_income, weights),
                )
            else:
                adjusted_income, labor_supply_change, baseline_net_rate = (
                    _apply_behavioral_adjustment(
                        income,
                        net_rate,
                        weights,
                        float(elasticity_mean),
                    )
                )
                elasticity_grid = _elasticity_grid_summary(
                    elasticity_by_obs,
                    weights,
                    feature_names=control_names,
                    controls=controls,
                )
            if elasticity_grid is None and preflight["estimation_mode"] in {
                "pseudo_panel",
                "pseudo_panel_iv",
            }:
                elasticity_grid = _cohort_slope_grid(
                    diagnostics.get("cohort_slopes", {})
                    if isinstance(diagnostics.get("cohort_slopes"), Mapping)
                    else {}
                )
            diagnostics["elasticity_estimate"] = float(elasticity_mean)
            if (
                abs(float(elasticity_mean)) > 2.0
                and identifiability_status == IdentifiabilityStatus.IDENTIFIED.value
            ):
                diagnostics["warnings"].append("large_elasticity_magnitude_review_recommended")
                identifiability_status = IdentifiabilityStatus.SLOPPY.value
        elif preflight["estimation_mode"] != "manual_override":
            diagnostics["elasticity_estimate"] = None

        diagnostics["identified_object"] = identified_object

        result = HeterogeneousBehavioralResponseResult(
            adjusted_market_income=adjusted_income,
            labor_supply_change=labor_supply_change,
            weighted_mean_income=_weighted_mean(adjusted_income, weights),
            identified_object=identified_object,
            regime=preflight["regime"],
            elasticity_mean=None if elasticity_mean is None else float(elasticity_mean),
            elasticity_by_obs=elasticity_by_obs,
            elasticity_lower=elasticity_lower,
            elasticity_upper=elasticity_upper,
            elasticity_grid=elasticity_grid if elasticity_mean is not None else None,
            first_stage_strength=preflight["first_stage_strength"],
            overlap_score=preflight["overlap_score"],
            measurement_reliability=preflight["measurement_reliability"],
            effective_sample_size=preflight["effective_sample_size"],
            identifiability_status=identifiability_status,
            identifiability=preflight["identifiability_report"],
            diagnostics=diagnostics,
            metadata={
                "baseline_net_rate": float(baseline_net_rate),
                "rate_source": rate_source,
                "feature_count_used": len(control_names),
                "feature_names_used": list(control_names),
                "estimator_version": "2.0.0",
                "assumption_card": list(preflight["assumptions"]),
            },
        )
        return {
            "result": result,
            "market_income": adjusted_income,
            "uncertainty_envelope": result.to_uncertainty_envelope(),
        }


@foundry_method(
    namespace="microsim.imputation",
    version="1.0.0",
    tags={"microsim", "imputation", "survey"},
)
class ImputationModelEstimator:
    """Impute missing microsimulation inputs before a downstream household policy run."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="imputation_model",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("imputation", "json"),
                    contract_id=ImputationResult.contract_id,
                ),
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
            }
        ),
        parameters=(ParameterSpec(name="n_estimators", default=100),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Supervised imputation of missing market income using tabular household features.",
        tags=frozenset({"microsim", "imputation", "survey"}),
        when_to_use="Missing income/covariate imputation in survey microdata prior to microsimulation",
        citations=(
            "Rubin, D. (1987). Multiple Imputation for Nonresponse in Surveys. Wiley.",
            "van Buuren, S. (2018). Flexible Imputation of Missing Data. CRC Press.",
        ),
        when_not_to_use="Very high missing rates (>50%); missingness is informative and cannot be modeled",
        output_interpretation="Imputed values replace missing entries. RMSE on observed training data indicates quality. Missing share shows scope of imputation.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SurveyMicroData:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return SurveyMicroData.model_validate(payload)

    @staticmethod
    def pure_step(state: SurveyMicroData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state if isinstance(state, SurveyMicroData) else SurveyMicroData.model_validate(state)
        )
        income = np.asarray(data.market_income, dtype=float)
        missing_mask = ~np.isfinite(income)
        if not missing_mask.any():
            result = ImputationResult(
                imputed_market_income=income,
                missing_share=0.0,
                rmse_train=0.0,
                metadata={"strategy": "identity"},
            )
            return {"result": result, "market_income": income}

        observed_mask = ~missing_mask
        imputed = np.asarray(income, dtype=float).copy()
        rmse_train: float | None = None
        if data.features is not None and np.sum(observed_mask) >= 8:
            from sklearn.ensemble import RandomForestRegressor

            model = RandomForestRegressor(
                n_estimators=max(50, int(params.get("n_estimators", 100))),
                random_state=int(params.get("__seed__", 0)),
            )
            x = np.asarray(data.features, dtype=float)
            model.fit(x[observed_mask], income[observed_mask])
            imputed[missing_mask] = model.predict(x[missing_mask])
            train_pred = model.predict(x[observed_mask])
            rmse_train = float(np.sqrt(np.mean((train_pred - income[observed_mask]) ** 2)))
            strategy = "random_forest"
        else:
            fill_value = float(np.nanmedian(income))
            imputed[missing_mask] = fill_value
            strategy = "median"

        result = ImputationResult(
            imputed_market_income=imputed,
            missing_share=float(np.mean(missing_mask)),
            rmse_train=rmse_train,
            metadata={"strategy": strategy},
        )
        return {
            "result": result,
            "market_income": imputed,
        }


@foundry_method(
    namespace="microsim.dynamic",
    version="1.0.0",
    tags={"microsim", "dynamic", "survey"},
)
class DynamicMicrosimEstimator:
    """Replay households forward through time in a dynamic microsimulation scenario."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dynamic_microsim",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "survey"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("dynamic_microsim", "json"),
                    contract_id=DynamicMicrosimResult.contract_id,
                ),
                SlotSpec(
                    "market_income", SlotType.VECTOR, Unit("income", "currency"), shape=("n_obs",)
                ),
                SlotSpec("uncertainty_envelope", SlotType.SCALAR, Unit("uncertainty", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="horizon", default=5),
            ParameterSpec(name="n_periods", default=None),
            ParameterSpec(name="drift", default=0.02),
            ParameterSpec(name="volatility", default=0.05),
            ParameterSpec(name="tax_rate", default=0.2),
            ParameterSpec(name="benefit_floor", default=8000.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Dynamic microsimulation of income evolution and fiscal outcomes over a finite horizon.",
        tags=frozenset({"microsim", "dynamic", "survey"}),
        when_to_use="Long-run distributional effects; cohort pension reform; lifetime income redistribution",
        citations=(
            "O'Donoghue, C. (2014). Handbook of Microsimulation Modelling. Emerald Group Publishing.",
            "Li, J. & O'Donoghue, C. (2013). A survey of dynamic microsimulation models: uses, model structure and methodology. International Journal of Microsimulation, 6(2), 3-55.",
        ),
        when_not_to_use="Short-run first-order analysis sufficient; no longitudinal data available",
        output_interpretation="Lifetime income/wealth distributions. Generational accounting. Cohort-specific winners/losers.",
        typical_min_obs=1000,
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> SurveyMicroData:
        payload = _survey_payload(fallback_state)
        payload.update(bound_inputs)
        return SurveyMicroData.model_validate(payload)

    @staticmethod
    def pure_step(state: SurveyMicroData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = (
            state if isinstance(state, SurveyMicroData) else SurveyMicroData.model_validate(state)
        )
        income = np.asarray(data.market_income, dtype=float)
        weights = np.asarray(data.weights, dtype=float)
        rng = params.get("__rng__")
        if rng is None or not hasattr(rng, "normal"):
            rng = np.random.default_rng(int(params.get("__seed__", 0)))
        horizon_raw = params.get("n_periods", params.get("horizon", 5))
        if horizon_raw is None:
            horizon_raw = params.get("horizon", 5)
        horizon = max(1, int(horizon_raw))
        drift = float(params.get("drift", 0.02))
        volatility = float(params.get("volatility", 0.05))
        tax_rate = float(params.get("tax_rate", 0.2))
        benefit_floor = float(params.get("benefit_floor", 8000.0))

        current = income.copy()
        mean_income_path: list[float] = []
        policy_revenue_path: list[float] = []
        for _ in range(horizon):
            shocks = rng.normal(loc=0.0, scale=volatility, size=current.shape[0])
            growth = np.maximum(1.0 + drift + shocks, 0.2)
            current = np.maximum(current * growth, 0.0)
            benefits = np.maximum(benefit_floor - 0.15 * current, 0.0)
            taxes = tax_rate * np.maximum(current - benefit_floor, 0.0)
            mean_income_path.append(_weighted_mean(current, weights))
            policy_revenue_path.append(float(np.sum((taxes - benefits) * weights)))

        final_benefits = np.maximum(benefit_floor - 0.15 * current, 0.0)
        final_taxes = tax_rate * np.maximum(current - benefit_floor, 0.0)
        disposable_income = current - final_taxes + final_benefits
        result = DynamicMicrosimResult(
            final_market_income=current,
            disposable_income=disposable_income,
            mean_income_path=mean_income_path,
            policy_revenue_path=policy_revenue_path,
            weighted_mean_final_income=_weighted_mean(current, weights),
            metadata={"horizon": horizon, "drift": drift, "volatility": volatility},
        )
        return {
            "result": result,
            "market_income": current,
            "uncertainty_envelope": result.to_uncertainty_envelope(),
        }


__all__ = [
    "BehavioralResponseEstimator",
    "DynamicMicrosimEstimator",
    "HeterogeneousBehavioralResponseEstimator",
    "ImputationModelEstimator",
    "TaxBenefitCalculatorEstimator",
]
