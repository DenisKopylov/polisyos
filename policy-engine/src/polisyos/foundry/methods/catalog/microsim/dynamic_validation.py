"""Validation helpers for dynamic microsimulation panel-moment diagnostics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any

import numpy as np

try:
    from scipy.stats import chi2
except Exception:  # pragma: no cover - reduced runtimes may omit scipy extras.
    chi2 = None

from .protocols import (
    DynamicMicrosimResult,
    DynamicMicrosimResultV2,
    DynamicMicrosimValidationDiagnostic,
    DynamicValidationSpec,
    HorizonBiasEnvelope,
    SensitivityRunResult,
    SurveyMicroData,
    ValidationCellResult,
    ValidationMomentSpec,
    ValidationOmnibusTest,
    upgrade_dynamic_microsim_result,
)

_EPS = 1.0e-12
_AGGREGATE_COHORT: dict[str, str | int] = {"all": "all"}
_MEAN_MOMENTS = {"mean_income", "mean_market_income", "weighted_mean_final_income"}


@dataclass(frozen=True)
class _MomentRow:
    cohort_key: dict[str, str | int]
    horizon_years: int
    moment_id: str
    value: float
    support_type: str | None = None
    se: float | None = None
    n: int | None = None
    ess: float | None = None


def _normal_two_sided_p(test_stat: float) -> float:
    return float(math.erfc(abs(float(test_stat)) / math.sqrt(2.0)))


def _chi2_sf(statistic: float, df: int) -> float | None:
    if df <= 0:
        return None
    if chi2 is not None:
        return float(chi2.sf(float(statistic), int(df)))
    if df == 1:
        return float(math.erfc(math.sqrt(max(float(statistic), 0.0) / 2.0)))
    z_value = (
        (max(float(statistic), _EPS) / float(df)) ** (1.0 / 3.0)
        - (1.0 - 2.0 / (9.0 * float(df)))
    ) / math.sqrt(2.0 / (9.0 * float(df)))
    return float(0.5 * math.erfc(z_value / math.sqrt(2.0)))


def _confidence_z(confidence_level: float) -> float:
    return float(NormalDist().inv_cdf(0.5 + float(confidence_level) / 2.0))


def _as_array(value: Any, *, name: str, ndim: int | None = None) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if ndim is not None and array.ndim != ndim:
        raise ValueError(f"{name} must be a {ndim}D numeric array")
    return array


def _optional_mapping_value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _normalize_cohort_key(raw: Any) -> dict[str, str | int]:
    if raw is None:
        return dict(_AGGREGATE_COHORT)
    if isinstance(raw, Mapping):
        if not raw:
            return dict(_AGGREGATE_COHORT)
        normalized: dict[str, str | int] = {}
        for key, value in raw.items():
            if isinstance(value, str):
                normalized[str(key)] = value
            elif isinstance(value, bool):
                normalized[str(key)] = int(value)
            elif isinstance(value, int):
                normalized[str(key)] = value
            else:
                normalized[str(key)] = str(value)
        return normalized
    return {"cohort": str(raw)}


def _cohort_tuple(cohort_key: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    cohort = _normalize_cohort_key(cohort_key)
    return tuple(sorted((str(key), str(value)) for key, value in cohort.items()))


def _row_lookup_key(
    row: _MomentRow | ValidationCellResult,
) -> tuple[tuple[tuple[str, str], ...], int, str]:
    cohort = _normalize_cohort_key(row.cohort_key)
    return (_cohort_tuple(cohort), int(row.horizon_years), str(row.moment_id))


def _support_for_horizon(spec: DynamicValidationSpec, horizon: int) -> str:
    explicit = spec.support_type_by_horizon.get(int(horizon))
    if explicit is not None:
        return explicit
    if spec.direct_support_max_horizon is None:
        return "direct"
    return "direct" if int(horizon) <= int(spec.direct_support_max_horizon) else "extrapolated"


def _effective_sample_size(weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    squared = float(np.sum(np.square(weights)))
    if total <= 0.0 or squared <= 0.0:
        return 0.0
    return float(total * total / squared)


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= 0.0:
        return float(np.mean(values)) if values.size else 0.0
    return float(np.sum(values * weights) / total)


def _weighted_var(values: np.ndarray, weights: np.ndarray) -> float:
    mean = _weighted_mean(values, weights)
    total = float(np.sum(weights))
    if total <= 0.0:
        return float(np.var(values)) if values.size else 0.0
    return float(np.sum(weights * np.square(values - mean)) / total)


def _weighted_cov(x_values: np.ndarray, y_values: np.ndarray, weights: np.ndarray) -> float:
    x_mean = _weighted_mean(x_values, weights)
    y_mean = _weighted_mean(y_values, weights)
    total = float(np.sum(weights))
    if total <= 0.0:
        return float(np.mean((x_values - x_mean) * (y_values - y_mean)))
    return float(np.sum(weights * (x_values - x_mean) * (y_values - y_mean)) / total)


def _weighted_corr(x_values: np.ndarray, y_values: np.ndarray, weights: np.ndarray) -> float:
    cov = _weighted_cov(x_values, y_values, weights)
    x_var = _weighted_var(x_values, weights)
    y_var = _weighted_var(y_values, weights)
    denom = math.sqrt(max(x_var * y_var, 0.0))
    if denom <= _EPS:
        return 0.0
    return float(np.clip(cov / denom, -1.0, 1.0))


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    if values.size == 0:
        return 0.0
    order = np.argsort(values, kind="mergesort")
    x = values[order]
    w = weights[order]
    total = float(np.sum(w))
    if total <= _EPS:
        return float(np.quantile(x, quantile))
    cdf = (np.cumsum(w) - 0.5 * w) / total
    return float(np.interp(float(quantile), cdf, x, left=x[0], right=x[-1]))


def _weighted_ranks(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    ranks = np.full(values.shape, 0.5, dtype=float)
    mask = np.isfinite(values) & np.isfinite(weights) & (weights >= 0.0)
    clean_values = values[mask].astype(float)
    clean_weights = weights[mask].astype(float)
    if clean_values.size == 0:
        return ranks
    order = np.argsort(clean_values, kind="mergesort")
    sorted_weights = clean_weights[order]
    total = float(np.sum(sorted_weights))
    clean_indices = np.flatnonzero(mask)
    if total <= _EPS:
        ranks[clean_indices[order]] = (
            np.arange(clean_values.size, dtype=float) + 0.5
        ) / clean_values.size
        return ranks
    cdf = (np.cumsum(sorted_weights) - 0.5 * sorted_weights) / total
    ranked = np.empty(clean_values.size, dtype=float)
    ranked[order] = cdf
    ranks[clean_indices] = ranked
    return ranks


def _weighted_quintiles(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    ranks = _weighted_ranks(values, weights)
    return np.clip(np.floor(ranks * 5.0).astype(int), 0, 4)


def _clean_values(values: np.ndarray, weights: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    if weights is None:
        weights = np.ones(values.shape[0], dtype=float)
    mask = np.isfinite(values) & np.isfinite(weights) & (weights >= 0.0)
    cleaned_values = values[mask].astype(float)
    cleaned_weights = weights[mask].astype(float)
    if cleaned_values.size == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    if float(np.sum(cleaned_weights)) <= _EPS:
        cleaned_weights = np.ones_like(cleaned_values, dtype=float)
    return cleaned_values, cleaned_weights


def _mapping_from_source(source: Any, key: str) -> Mapping[str, Any] | None:
    value = _optional_mapping_value(source, key)
    if isinstance(value, Mapping):
        return value
    return None


def _cohort_data_from_source(
    source: Any,
    dimensions: tuple[str, ...],
    *,
    n_obs: int,
    explicit_mapping_key: str = "cohort_data",
) -> dict[str, np.ndarray]:
    if not dimensions or dimensions == ("all",):
        return {}
    mappings: list[Mapping[str, Any]] = []
    explicit = _mapping_from_source(source, explicit_mapping_key)
    if explicit is not None:
        mappings.append(explicit)
    metadata = _mapping_from_source(source, "metadata")
    if metadata is not None:
        cohort_meta = metadata.get(explicit_mapping_key)
        if isinstance(cohort_meta, Mapping):
            mappings.append(cohort_meta)

    cohort_data: dict[str, np.ndarray] = {}
    for dimension in dimensions:
        if dimension == "all":
            continue
        value = _optional_mapping_value(source, dimension)
        if value is None:
            for mapping in mappings:
                if dimension in mapping:
                    value = mapping[dimension]
                    break
        if value is None:
            continue
        array = np.asarray(value)
        if array.ndim != 1:
            raise ValueError(f"cohort dimension {dimension!r} must be a 1D array")
        if array.shape[0] != n_obs:
            raise ValueError(f"cohort dimension {dimension!r} length must match observations")
        cohort_data[dimension] = array
    return cohort_data


def _cohort_groups(
    cohort_data: Mapping[str, np.ndarray],
    *,
    n_obs: int,
) -> list[tuple[dict[str, str | int], np.ndarray]]:
    if not cohort_data:
        return [(dict(_AGGREGATE_COHORT), np.ones(n_obs, dtype=bool))]
    labels: list[str] = []
    keys: list[dict[str, str | int]] = []
    for index in range(n_obs):
        key: dict[str, str | int] = {}
        parts: list[str] = []
        for dimension, values in cohort_data.items():
            raw = values[index]
            value: str | int
            if isinstance(raw, str):
                value = raw
            elif isinstance(raw, (np.integer, int, bool)):
                value = int(raw)
            else:
                value = str(raw)
            key[str(dimension)] = value
            parts.append(f"{dimension}={value}")
        labels.append("|".join(parts))
        keys.append(key)

    groups: list[tuple[dict[str, str | int], np.ndarray]] = []
    for label in sorted(set(labels)):
        mask = np.asarray([item == label for item in labels], dtype=bool)
        first_idx = int(np.flatnonzero(mask)[0])
        groups.append((keys[first_idx], mask))
    return groups


def _long_panel_to_path(
    panel_data: SurveyMicroData | Mapping[str, Any],
    spec: DynamicValidationSpec,
    warnings: list[str],
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]] | None:
    person_payload = _optional_mapping_value(panel_data, "person_id")
    if person_payload is None:
        person_payload = _optional_mapping_value(panel_data, "household_ids")
    period_payload = _optional_mapping_value(panel_data, "year")
    if period_payload is None:
        period_payload = _optional_mapping_value(panel_data, "period_id")
    income_payload = _optional_mapping_value(panel_data, "income")
    if income_payload is None:
        income_payload = _optional_mapping_value(panel_data, "market_income")
    if person_payload is None or period_payload is None or income_payload is None:
        return None

    person_ids = np.asarray(person_payload).astype(str)
    periods_raw = np.asarray(period_payload)
    incomes = np.asarray(income_payload, dtype=float)
    if not (person_ids.ndim == periods_raw.ndim == incomes.ndim == 1):
        raise ValueError("long panel person_id, period/year, and income must be 1D arrays")
    if not (person_ids.shape[0] == periods_raw.shape[0] == incomes.shape[0]):
        raise ValueError("long panel person_id, period/year, and income lengths must match")

    try:
        periods_for_sort = periods_raw.astype(float)
    except (TypeError, ValueError):
        periods_for_sort = periods_raw.astype(str)
    unique_periods = np.asarray(sorted(set(periods_for_sort.tolist())))
    unique_people = np.asarray(sorted(set(person_ids.tolist())))
    period_index = {str(value): index for index, value in enumerate(unique_periods.astype(str))}
    person_index = {str(value): index for index, value in enumerate(unique_people.astype(str))}

    weights_payload = _optional_mapping_value(panel_data, "weights")
    row_weights = (
        np.asarray(weights_payload, dtype=float)
        if weights_payload is not None
        else np.ones_like(incomes, dtype=float)
    )
    if row_weights.ndim != 1 or row_weights.shape[0] != incomes.shape[0]:
        raise ValueError("long panel weights must be a 1D array matching income")

    income_weighted_sum = np.zeros((unique_periods.size, unique_people.size), dtype=float)
    weight_sum = np.zeros_like(income_weighted_sum)
    person_weight_sum = np.zeros(unique_people.size, dtype=float)
    person_weight_count = np.zeros(unique_people.size, dtype=float)
    for obs_idx, income in enumerate(incomes):
        p_idx = person_index[str(person_ids[obs_idx])]
        t_idx = period_index[str(periods_for_sort[obs_idx])]
        weight = float(row_weights[obs_idx])
        if not math.isfinite(income) or not math.isfinite(weight) or weight < 0.0:
            continue
        income_weighted_sum[t_idx, p_idx] += income * weight
        weight_sum[t_idx, p_idx] += weight
        person_weight_sum[p_idx] += weight
        person_weight_count[p_idx] += 1.0

    path = np.full_like(income_weighted_sum, np.nan)
    mask = weight_sum > _EPS
    path[mask] = income_weighted_sum[mask] / weight_sum[mask]
    person_weights = person_weight_sum / np.maximum(person_weight_count, 1.0)
    person_weights = np.where(person_weights > _EPS, person_weights, 1.0)

    row_cohort_data = _cohort_data_from_source(
        panel_data,
        spec.cohort_dimensions,
        n_obs=incomes.shape[0],
    )
    cohort_data: dict[str, np.ndarray] = {}
    for dimension, values in row_cohort_data.items():
        person_values = np.empty(unique_people.size, dtype=object)
        person_values[:] = "unknown"
        seen: set[int] = set()
        for obs_idx, raw in enumerate(values):
            p_idx = person_index[str(person_ids[obs_idx])]
            if p_idx in seen:
                continue
            person_values[p_idx] = raw
            seen.add(p_idx)
        cohort_data[dimension] = person_values

    return path, person_weights, cohort_data


def _moment_from_values(
    values: np.ndarray,
    weights: np.ndarray | None,
    moment: ValidationMomentSpec,
    *,
    low_income_threshold: float = 1.0,
) -> tuple[float, float | None, int, float]:
    clean_values, clean_weights = _clean_values(values, weights)
    n_obs = int(clean_values.size)
    ess = _effective_sample_size(clean_weights) if n_obs else 0.0
    if n_obs == 0:
        return 0.0, None, 0, 0.0

    moment_id = moment.moment_id
    transformed: np.ndarray
    value: float
    se: float | None = None
    if moment_id in _MEAN_MOMENTS or moment_id == "lifetime_discounted_income":
        transformed = clean_values
        value = _weighted_mean(transformed, clean_weights)
        se = math.sqrt(max(_weighted_var(transformed, clean_weights), 0.0) / max(ess, 1.0))
    elif moment_id == "mean_log_income":
        transformed = np.log(np.maximum(clean_values, 1.0))
        value = _weighted_mean(transformed, clean_weights)
        se = math.sqrt(max(_weighted_var(transformed, clean_weights), 0.0) / max(ess, 1.0))
    elif moment_id in {"median_income", "median"}:
        value = _weighted_quantile(clean_values, clean_weights, 0.5)
    elif moment_id in {"p10_income", "p10"}:
        value = _weighted_quantile(clean_values, clean_weights, 0.10)
    elif moment_id in {"p90_income", "p90"}:
        value = _weighted_quantile(clean_values, clean_weights, 0.90)
    elif moment_id == "var_log_income":
        transformed = np.log(np.maximum(clean_values, 1.0))
        value = _weighted_var(transformed, clean_weights)
    elif moment_id in {"low_income_share", "zero_low_income_share"}:
        indicator = (clean_values <= float(low_income_threshold)).astype(float)
        value = _weighted_mean(indicator, clean_weights)
        se = math.sqrt(max(value * (1.0 - value), 0.0) / max(ess, 1.0))
    elif moment_id == "zero_income_share":
        indicator = (clean_values <= 0.0).astype(float)
        value = _weighted_mean(indicator, clean_weights)
        se = math.sqrt(max(value * (1.0 - value), 0.0) / max(ess, 1.0))
    else:
        raise ValueError(f"Unsupported dynamic validation moment_id: {moment_id}")
    return float(value), (float(se) if se is not None else None), n_obs, float(ess)


def _lag_from_moment_id(moment_id: str, default: int = 1) -> int:
    for token in moment_id.split("_"):
        if token.endswith("y") and token[:-1].isdigit():
            return max(1, int(token[:-1]))
    return default


def _path_moment(
    path: np.ndarray,
    weights: np.ndarray | None,
    moment: ValidationMomentSpec,
    horizon: int,
    spec: DynamicValidationSpec,
) -> tuple[float, float | None, int, float] | None:
    if horizon <= 0 or horizon > path.shape[0]:
        return None
    clean_weights = weights if weights is not None else np.ones(path.shape[1], dtype=float)
    period_values = path[horizon - 1]
    moment_id = moment.moment_id

    if moment_id == "lifetime_discounted_income":
        discount_factor = float(spec.metadata.get("lifetime_discount_factor", 1.0))
        discounts = np.power(discount_factor, np.arange(horizon, dtype=float))
        cumulative = np.sum(path[:horizon] * discounts[:, None], axis=0)
        return _moment_from_values(
            cumulative,
            clean_weights,
            moment,
            low_income_threshold=spec.low_income_threshold,
        )

    if moment_id.startswith("autocovariance_"):
        lag = _lag_from_moment_id(moment_id)
        if horizon <= lag:
            return None
        lagged = path[horizon - lag - 1]
        current = period_values
        if "log_income" in moment_id:
            lagged = np.log(np.maximum(lagged, 1.0))
            current = np.log(np.maximum(current, 1.0))
        mask = np.isfinite(lagged) & np.isfinite(current) & np.isfinite(clean_weights)
        mask &= clean_weights >= 0.0
        if not np.any(mask):
            return None
        x_values = lagged[mask].astype(float)
        y_values = current[mask].astype(float)
        w_values = clean_weights[mask].astype(float)
        value = _weighted_cov(x_values, y_values, w_values)
        centered_product = (x_values - _weighted_mean(x_values, w_values)) * (
            y_values - _weighted_mean(y_values, w_values)
        )
        ess = _effective_sample_size(w_values)
        se = math.sqrt(max(_weighted_var(centered_product, w_values), 0.0) / max(ess, 1.0))
        return float(value), float(se), int(x_values.size), float(ess)

    if moment_id == "rank_rank_persistence":
        if horizon <= 1:
            return None
        baseline = path[0]
        current = period_values
        mask = np.isfinite(baseline) & np.isfinite(current) & np.isfinite(clean_weights)
        mask &= clean_weights >= 0.0
        if not np.any(mask):
            return None
        w_values = clean_weights[mask].astype(float)
        baseline_ranks = _weighted_ranks(baseline[mask].astype(float), w_values)
        current_ranks = _weighted_ranks(current[mask].astype(float), w_values)
        value = _weighted_corr(baseline_ranks, current_ranks, w_values)
        ess = _effective_sample_size(w_values)
        se = math.sqrt(max((1.0 - value * value) / max(ess - 2.0, 1.0), 0.0))
        return float(value), float(se), int(np.sum(mask)), float(ess)

    if moment_id == "quintile_stay_share":
        if horizon <= 1:
            return None
        baseline = path[0]
        current = period_values
        mask = np.isfinite(baseline) & np.isfinite(current) & np.isfinite(clean_weights)
        mask &= clean_weights >= 0.0
        if not np.any(mask):
            return None
        w_values = clean_weights[mask].astype(float)
        baseline_quintile = _weighted_quintiles(baseline[mask].astype(float), w_values)
        current_quintile = _weighted_quintiles(current[mask].astype(float), w_values)
        indicator = (baseline_quintile == current_quintile).astype(float)
        value = _weighted_mean(indicator, w_values)
        ess = _effective_sample_size(w_values)
        se = math.sqrt(max(value * (1.0 - value), 0.0) / max(ess, 1.0))
        return float(value), float(se), int(np.sum(mask)), float(ess)

    return _moment_from_values(
        period_values,
        clean_weights,
        moment,
        low_income_threshold=spec.low_income_threshold,
    )


def _moment_rows_from_payload(
    rows: Any,
    *,
    value_key: str,
    default_support_type: str | None = None,
) -> list[_MomentRow]:
    parsed: list[_MomentRow] = []
    if rows is None:
        return parsed
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("moment rows must be mappings")
        raw_value = row.get(value_key, row.get("value"))
        if raw_value is None:
            raise ValueError(f"moment row missing {value_key!r} or 'value'")
        parsed.append(
            _MomentRow(
                cohort_key=_normalize_cohort_key(row.get("cohort_key")),
                horizon_years=int(row.get("horizon_years", row.get("horizon", 0))),
                moment_id=str(row["moment_id"]),
                value=float(raw_value),
                support_type=str(row.get("support_type", default_support_type))
                if row.get("support_type", default_support_type) is not None
                else None,
                se=float(row["se"]) if row.get("se") is not None else None,
                n=int(row["n"]) if row.get("n") is not None else None,
                ess=float(row["ess"]) if row.get("ess") is not None else None,
            )
        )
    return parsed


def _horizons_for_validation(
    result: DynamicMicrosimResultV2,
    spec: DynamicValidationSpec,
) -> tuple[int, ...]:
    if spec.horizons:
        return tuple(int(horizon) for horizon in spec.horizons)
    if result.mean_income_path:
        return tuple(range(1, len(result.mean_income_path) + 1))
    return (0,)


def _rows_from_income_path(
    path: np.ndarray,
    weights: np.ndarray | None,
    spec: DynamicValidationSpec,
    *,
    cohort_key: dict[str, str | int] | None = None,
    cohort_data: Mapping[str, np.ndarray] | None = None,
    warnings: list[str] | None = None,
) -> list[_MomentRow]:
    rows: list[_MomentRow] = []
    groups = (
        [(_normalize_cohort_key(cohort_key), np.ones(path.shape[1], dtype=bool))]
        if cohort_key is not None
        else _cohort_groups(cohort_data or {}, n_obs=path.shape[1])
    )
    horizons = tuple(h for h in _horizons_from_spec_or_path(spec, path) if h > 0)
    for cohort, mask in groups:
        cohort_path = path[:, mask]
        cohort_weights = weights[mask] if weights is not None else None
        for horizon in horizons:
            if horizon > path.shape[0]:
                continue
            for moment in spec.moment_specs:
                payload = _path_moment(cohort_path, cohort_weights, moment, int(horizon), spec)
                if payload is None:
                    continue
                value, se, n_obs, ess = payload
                if spec.minimum_cell_ess is not None and ess < float(spec.minimum_cell_ess):
                    if warnings is not None:
                        warnings.append(
                            f"low_effective_sample_size:{moment.moment_id}:h{horizon}"
                        )
                    continue
                rows.append(
                    _MomentRow(
                        cohort_key=cohort,
                        horizon_years=int(horizon),
                        moment_id=moment.moment_id,
                        value=value,
                        support_type=_support_for_horizon(spec, int(horizon)),
                        se=se,
                        n=n_obs,
                        ess=ess,
                    )
                )
    return rows


def _horizons_from_spec_or_path(spec: DynamicValidationSpec, path: np.ndarray) -> tuple[int, ...]:
    if spec.horizons:
        return tuple(int(horizon) for horizon in spec.horizons)
    return tuple(range(1, int(path.shape[0]) + 1))


def _simulated_rows_from_result(
    result: DynamicMicrosimResultV2,
    spec: DynamicValidationSpec,
    warnings: list[str],
) -> list[_MomentRow]:
    rows: list[_MomentRow] = []
    final_income = _as_array(result.final_market_income, name="final_market_income", ndim=1)
    weights = (
        _as_array(result.weights, name="dynamic result weights", ndim=1)
        if result.weights is not None
        else np.ones_like(final_income, dtype=float)
    )
    if result.weights is None:
        warnings.append("simulation_weights_unavailable_using_equal_weights_for_distribution_moments")

    path = (
        _as_array(result.market_income_path, name="market_income_path", ndim=2)
        if result.market_income_path is not None
        else None
    )
    if path is not None:
        cohort_data = _cohort_data_from_source(
            result,
            spec.cohort_dimensions,
            n_obs=path.shape[1],
        )
        if spec.cohort_dimensions != ("all",) and not cohort_data:
            warnings.append("simulation_cohort_data_unavailable_using_aggregate_cells")
        rows.extend(_rows_from_income_path(path, weights, spec, cohort_data=cohort_data, warnings=warnings))

    horizons = _horizons_for_validation(result, spec)
    row_keys = {_row_lookup_key(row) for row in rows}
    final_horizon = len(result.mean_income_path)
    for horizon in horizons:
        for moment in spec.moment_specs:
            key = (tuple(sorted((str(k), str(v)) for k, v in _AGGREGATE_COHORT.items())), int(horizon), moment.moment_id)
            if key in row_keys:
                continue
            if moment.moment_id in _MEAN_MOMENTS and 1 <= int(horizon) <= len(result.mean_income_path):
                rows.append(
                    _MomentRow(
                        cohort_key=dict(_AGGREGATE_COHORT),
                        horizon_years=int(horizon),
                        moment_id=moment.moment_id,
                        value=float(result.mean_income_path[int(horizon) - 1]),
                        support_type=_support_for_horizon(spec, int(horizon)),
                        se=None,
                        n=int(final_income.size),
                        ess=_effective_sample_size(weights),
                    )
                )
                continue
            if int(horizon) in {0, final_horizon} or (
                path is None and int(horizon) == max(horizons)
            ):
                try:
                    value, se, n_obs, ess = _moment_from_values(final_income, weights, moment)
                except ValueError:
                    continue
                rows.append(
                    _MomentRow(
                        cohort_key=dict(_AGGREGATE_COHORT),
                        horizon_years=int(horizon),
                        moment_id=moment.moment_id,
                        value=value,
                        support_type=_support_for_horizon(spec, int(horizon)),
                        se=se,
                        n=n_obs,
                        ess=ess,
                    )
                )
    return rows


def _observed_rows_from_panel_data(
    panel_data: SurveyMicroData | Mapping[str, Any],
    spec: DynamicValidationSpec,
    warnings: list[str],
) -> list[_MomentRow]:
    observed_payload = _optional_mapping_value(panel_data, "observed_moments")
    if observed_payload is not None:
        return _moment_rows_from_payload(observed_payload, value_key="observed_value")

    path_payload = _optional_mapping_value(panel_data, "observed_income_path")
    if path_payload is None:
        path_payload = _optional_mapping_value(panel_data, "income_path")
    weights_payload = _optional_mapping_value(panel_data, "weights")
    if path_payload is not None:
        path = _as_array(path_payload, name="observed_income_path", ndim=2)
        weights = (
            _as_array(weights_payload, name="observed weights", ndim=1)
            if weights_payload is not None
            else np.ones(path.shape[1], dtype=float)
        )
        cohort_data = _cohort_data_from_source(
            panel_data,
            spec.cohort_dimensions,
            n_obs=path.shape[1],
        )
        if spec.cohort_dimensions != ("all",) and not cohort_data:
            warnings.append("panel_cohort_data_unavailable_using_aggregate_cells")
        return _rows_from_income_path(
            path,
            weights,
            spec,
            cohort_data=cohort_data,
            warnings=warnings,
        )

    long_panel = _long_panel_to_path(panel_data, spec, warnings)
    if long_panel is not None:
        path, weights, cohort_data = long_panel
        if spec.cohort_dimensions != ("all",) and not cohort_data:
            warnings.append("panel_cohort_data_unavailable_using_aggregate_cells")
        return _rows_from_income_path(
            path,
            weights,
            spec,
            cohort_data=cohort_data,
            warnings=warnings,
        )

    income_payload = _optional_mapping_value(panel_data, "market_income")
    if income_payload is None:
        raise ValueError(
            "panel_data must provide observed_moments, observed_income_path, income_path, "
            "or market_income"
        )
    income = _as_array(income_payload, name="panel market_income", ndim=1)
    weights = (
        _as_array(weights_payload, name="panel weights", ndim=1)
        if weights_payload is not None
        else np.ones_like(income, dtype=float)
    )
    warnings.append("panel_cross_section_reused_for_requested_horizons")
    cohort_data = _cohort_data_from_source(panel_data, spec.cohort_dimensions, n_obs=income.shape[0])
    groups = _cohort_groups(cohort_data, n_obs=income.shape[0])
    rows: list[_MomentRow] = []
    for horizon in _horizons_for_validation(
        DynamicMicrosimResultV2(
            final_market_income=income,
            disposable_income=income,
            mean_income_path=[],
            policy_revenue_path=[],
            weighted_mean_final_income=_weighted_mean(income, weights),
            weights=weights,
        ),
        spec,
    ):
        for cohort, mask in groups:
            for moment in spec.moment_specs:
                try:
                    value, se, n_obs, ess = _moment_from_values(
                        income[mask],
                        weights[mask],
                        moment,
                        low_income_threshold=spec.low_income_threshold,
                    )
                except ValueError:
                    continue
                rows.append(
                    _MomentRow(
                        cohort_key=cohort,
                        horizon_years=int(horizon),
                        moment_id=moment.moment_id,
                        value=value,
                        support_type=_support_for_horizon(spec, int(horizon)),
                        se=se,
                        n=n_obs,
                        ess=ess,
                    )
                )
    return rows


def _simulated_rows_from_payload(
    panel_data: SurveyMicroData | Mapping[str, Any],
    spec: DynamicValidationSpec,
) -> list[_MomentRow]:
    simulated_payload = _optional_mapping_value(panel_data, "simulated_moments")
    if simulated_payload is None:
        return []
    return _moment_rows_from_payload(simulated_payload, value_key="simulated_value")


def _combine_standard_errors(sim_row: _MomentRow, obs_row: _MomentRow) -> float | None:
    pieces = [
        float(value)
        for value in (sim_row.se, obs_row.se)
        if value is not None and math.isfinite(float(value)) and float(value) >= 0.0
    ]
    if not pieces:
        return None
    return float(math.sqrt(sum(value * value for value in pieces)))


def _apply_multiple_testing_correction(
    cell_results: list[ValidationCellResult],
    spec: DynamicValidationSpec,
) -> list[ValidationCellResult]:
    indexed = [
        (index, float(cell.p_value))
        for index, cell in enumerate(cell_results)
        if cell.p_value is not None
    ]
    if not indexed or spec.multiple_testing_correction == "none":
        return cell_results

    adjusted_values: dict[int, float] = {}
    if spec.multiple_testing_correction == "bonferroni":
        n_tests = len(indexed)
        adjusted_values = {index: min(1.0, p_value * n_tests) for index, p_value in indexed}
    else:
        ordered = sorted(indexed, key=lambda item: item[1])
        n_tests = len(ordered)
        running = 0.0
        for rank, (index, p_value) in enumerate(ordered):
            adjusted = min(1.0, (n_tests - rank) * p_value)
            running = max(running, adjusted)
            adjusted_values[index] = running

    return [
        cell.model_copy(update={"p_value_adjusted": adjusted_values[index]})
        if index in adjusted_values
        else cell
        for index, cell in enumerate(cell_results)
    ]


def _build_cell_results(
    simulated_rows: list[_MomentRow],
    observed_rows: list[_MomentRow],
    spec: DynamicValidationSpec,
    warnings: list[str],
) -> list[ValidationCellResult]:
    sim_by_key = {_row_lookup_key(row): row for row in simulated_rows}
    aggregate_prefix = tuple(sorted((str(key), str(value)) for key, value in _AGGREGATE_COHORT.items()))
    z_value = _confidence_z(spec.confidence_level)
    cell_results: list[ValidationCellResult] = []
    missing_simulated = 0
    aggregate_reused = 0

    for obs_row in observed_rows:
        lookup_key = _row_lookup_key(obs_row)
        sim_row = sim_by_key.get(lookup_key)
        if sim_row is None:
            aggregate_key = (aggregate_prefix, int(obs_row.horizon_years), obs_row.moment_id)
            sim_row = sim_by_key.get(aggregate_key)
            if sim_row is not None:
                aggregate_reused += 1
        if sim_row is None:
            missing_simulated += 1
            continue

        bias = float(sim_row.value - obs_row.value)
        relative_bias = (
            float(bias / obs_row.value) if abs(float(obs_row.value)) > _EPS else None
        )
        se = _combine_standard_errors(sim_row, obs_row)
        test_stat: float | None = None
        p_value: float | None = None
        ci_lower: float | None = None
        ci_upper: float | None = None
        if se is not None and se > _EPS:
            test_stat = float(bias / se)
            p_value = _normal_two_sided_p(test_stat)
            ci_lower = float(bias - z_value * se)
            ci_upper = float(bias + z_value * se)

        support = obs_row.support_type or sim_row.support_type or _support_for_horizon(
            spec, obs_row.horizon_years
        )
        cell_results.append(
            ValidationCellResult(
                cohort_key=_normalize_cohort_key(obs_row.cohort_key),
                horizon_years=int(obs_row.horizon_years),
                moment_id=obs_row.moment_id,
                support_type=support,  # type: ignore[arg-type]
                simulated_value=float(sim_row.value),
                observed_value=float(obs_row.value),
                bias=bias,
                relative_bias=relative_bias,
                se=se,
                test_stat=test_stat,
                p_value=p_value,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                n_sim=sim_row.n,
                n_obs=obs_row.n,
                ess_obs=obs_row.ess,
                ess_sim=sim_row.ess,
            )
        )

    if missing_simulated:
        warnings.append(f"missing_simulated_moments:{missing_simulated}")
    if aggregate_reused:
        warnings.append(f"aggregate_simulated_moments_reused_for_cohort_cells:{aggregate_reused}")

    return _apply_multiple_testing_correction(cell_results, spec)


def _build_omnibus_tests(
    cell_results: list[ValidationCellResult],
    spec: DynamicValidationSpec,
) -> list[ValidationOmnibusTest]:
    tests: list[ValidationOmnibusTest] = []

    def build_test(
        rows: list[ValidationCellResult],
        *,
        scope: str,
        method: str,
        null_hypothesis: str,
    ) -> ValidationOmnibusTest | None:
        standardized = [
            float(cell.bias) / float(cell.se)
            for cell in rows
            if cell.se is not None and float(cell.se) > _EPS and math.isfinite(float(cell.bias))
        ]
        if not standardized:
            return None
        statistic = float(np.sum(np.square(np.asarray(standardized, dtype=float))))
        df = int(len(standardized))
        return ValidationOmnibusTest(
            scope=scope,  # type: ignore[arg-type]
            method=method,  # type: ignore[arg-type]
            null_hypothesis=null_hypothesis,
            statistic=statistic,
            df=df,
            p_value=_chi2_sf(statistic, df),
            covariance_estimator="diagonal_pointwise_standard_errors",
            bootstrap_reps=int(spec.bootstrap_reps),
        )

    by_cohort_moment: dict[tuple[tuple[tuple[str, str], ...], str], list[ValidationCellResult]] = {}
    by_cohort: dict[tuple[tuple[str, str], ...], list[ValidationCellResult]] = {}
    for cell in cell_results:
        cohort = _cohort_tuple(cell.cohort_key)
        by_cohort.setdefault(cohort, []).append(cell)
        by_cohort_moment.setdefault((cohort, cell.moment_id), []).append(cell)

    for (cohort, moment_id), rows in sorted(by_cohort_moment.items()):
        if len({cell.horizon_years for cell in rows}) < 2:
            continue
        cohort_label = ",".join(f"{key}={value}" for key, value in cohort)
        test = build_test(
            rows,
            scope="cohort_moment_horizons",
            method="wald",
            null_hypothesis=f"{moment_id} bias is zero for all horizons in {cohort_label}",
        )
        if test is not None:
            tests.append(test)

    for cohort, rows in sorted(by_cohort.items()):
        if len(rows) < 2:
            continue
        cohort_label = ",".join(f"{key}={value}" for key, value in cohort)
        test = build_test(
            rows,
            scope="cohort_all_moments",
            method="wald",
            null_hypothesis=f"all reported moment biases are zero in {cohort_label}",
        )
        if test is not None:
            tests.append(test)

    global_test = build_test(
        cell_results,
        scope="global_all",
        method="hansen_j_type",
        null_hypothesis="the full dynamic microsim validation moment system is compatible",
    )
    if global_test is not None:
        tests.append(global_test)

    by_moment_origin: dict[str, list[tuple[int, float]]] = {}
    for cell in cell_results:
        origin_raw = cell.cohort_key.get("origin_year") or cell.cohort_key.get("origin")
        if origin_raw is None:
            continue
        try:
            origin = int(origin_raw)
        except (TypeError, ValueError):
            continue
        by_moment_origin.setdefault(cell.moment_id, []).append((origin, float(cell.bias)))

    for moment_id, values in sorted(by_moment_origin.items()):
        origins = sorted({origin for origin, _ in values})
        if len(origins) < 3:
            continue
        sup_stat = 0.0
        for split in origins[1:-1]:
            left = np.asarray([bias for origin, bias in values if origin <= split], dtype=float)
            right = np.asarray([bias for origin, bias in values if origin > split], dtype=float)
            if left.size < 2 or right.size < 2:
                continue
            variance = float(np.var(left, ddof=1) / left.size + np.var(right, ddof=1) / right.size)
            if variance <= _EPS:
                continue
            candidate = float((np.mean(left) - np.mean(right)) ** 2 / variance)
            sup_stat = max(sup_stat, candidate)
        if sup_stat > 0.0:
            tests.append(
                ValidationOmnibusTest(
                    scope="cohort_moment_horizons",
                    method="sup_wald",
                    null_hypothesis=f"{moment_id} bias process is stable across origin years",
                    statistic=sup_stat,
                    df=1,
                    p_value=_chi2_sf(sup_stat, 1),
                    covariance_estimator="origin_year_split_variance",
                    bootstrap_reps=int(spec.bootstrap_reps),
                )
            )
    return tests


def _primary_moment_ids(moment_specs: tuple[ValidationMomentSpec, ...]) -> set[str]:
    return {moment.moment_id for moment in moment_specs if moment.primary}


def _build_bias_envelopes(
    cell_results: list[ValidationCellResult],
    spec: DynamicValidationSpec,
) -> list[HorizonBiasEnvelope]:
    rng = np.random.default_rng(int(spec.bootstrap_seed))
    primary_ids = _primary_moment_ids(spec.moment_specs)
    envelopes: list[HorizonBiasEnvelope] = []

    for moment_id in sorted(primary_ids):
        rows = [cell for cell in cell_results if cell.moment_id == moment_id]
        if not rows:
            continue
        horizons = sorted({int(cell.horizon_years) for cell in rows})
        cohorts = sorted({_cohort_tuple(cell.cohort_key) for cell in rows})
        horizon_index = {horizon: index for index, horizon in enumerate(horizons)}
        cohort_index = {cohort: index for index, cohort in enumerate(cohorts)}
        bias_matrix = np.full((len(cohorts), len(horizons)), np.nan, dtype=float)
        se_matrix = np.full((len(cohorts), len(horizons)), np.nan, dtype=float)
        for cell in rows:
            c_idx = cohort_index[_cohort_tuple(cell.cohort_key)]
            h_idx = horizon_index[int(cell.horizon_years)]
            bias_matrix[c_idx, h_idx] = float(cell.bias)
            if cell.se is not None:
                se_matrix[c_idx, h_idx] = float(cell.se)
        point_path: list[float] = []
        se_path: list[float] = []
        for horizon in horizons:
            h_idx = horizon_index[horizon]
            biases = bias_matrix[:, h_idx]
            finite = np.isfinite(biases)
            point = float(np.mean(biases[finite])) if np.any(finite) else 0.0
            if int(np.sum(finite)) > 1:
                se = float(np.std(biases[finite], ddof=1) / math.sqrt(float(np.sum(finite))))
            elif np.any(np.isfinite(se_matrix[:, h_idx])):
                se = float(np.nanmean(se_matrix[:, h_idx]))
            else:
                se = 0.0
            point_path.append(point)
            se_path.append(se)

        critical = _confidence_z(spec.confidence_level)
        if spec.bootstrap_reps > 0 and len(cohorts) > 1:
            sup_stats: list[float] = []
            for _ in range(int(spec.bootstrap_reps)):
                sampled_rows = rng.integers(0, len(cohorts), size=len(cohorts))
                sampled = bias_matrix[sampled_rows, :]
                replicate_stats = []
                for index in range(len(horizons)):
                    values = sampled[:, index]
                    finite = np.isfinite(values)
                    if not np.any(finite) or se_path[index] <= _EPS:
                        replicate_stats.append(0.0)
                        continue
                    replicate_mean = float(np.mean(values[finite]))
                    replicate_stats.append(abs(replicate_mean - point_path[index]) / se_path[index])
                sup_stats.append(max(replicate_stats) if replicate_stats else 0.0)
            if sup_stats:
                critical = float(
                    np.quantile(np.asarray(sup_stats, dtype=float), spec.confidence_level)
                )

        lower_path = [
            float(point - critical * se) for point, se in zip(point_path, se_path, strict=True)
        ]
        upper_path = [
            float(point + critical * se) for point, se in zip(point_path, se_path, strict=True)
        ]
        envelopes.append(
            HorizonBiasEnvelope(
                target_moment_id=moment_id,
                horizons=[int(horizon) for horizon in horizons],
                point_path=point_path,
                lower_path=lower_path,
                upper_path=upper_path,
                confidence_level=float(spec.confidence_level),
                simultaneous=len(horizons) > 1,
                method="sup_t_block_bootstrap",
                scale="bias",
                block_scheme=f"paired_origin_cell_bootstrap:{spec.block_scheme}",
                block_length=int(spec.block_length),
                extrapolated_from_horizon=spec.direct_support_max_horizon
                if spec.direct_support_max_horizon is not None
                and any(horizon > spec.direct_support_max_horizon for horizon in horizons)
                else None,
            )
        )
    return envelopes


def _classify_status(
    cell_results: list[ValidationCellResult],
    spec: DynamicValidationSpec,
    warnings: list[str],
) -> tuple[str, int, int, float | None]:
    if not cell_results:
        return "inconclusive", 0, 0, None

    specs_by_id = {moment.moment_id: moment for moment in spec.moment_specs}
    primary_ids = _primary_moment_ids(spec.moment_specs)
    failed = 0
    warned = 0
    relative_biases: list[float] = []

    for cell in cell_results:
        if cell.moment_id not in primary_ids:
            continue
        moment = specs_by_id.get(cell.moment_id)
        abs_bias = abs(float(cell.bias))
        rel_bias = abs(float(cell.relative_bias)) if cell.relative_bias is not None else None
        if rel_bias is not None:
            relative_biases.append(rel_bias)
        cell_failed = False
        cell_warned = False
        if moment is not None and moment.tolerance_abs is not None:
            cell_failed = cell_failed or abs_bias > float(moment.tolerance_abs)
        if moment is not None and moment.tolerance_rel is not None and rel_bias is not None:
            cell_failed = cell_failed or rel_bias > float(moment.tolerance_rel)
        if (
            spec.max_abs_relative_bias_fail is not None
            and rel_bias is not None
            and rel_bias > float(spec.max_abs_relative_bias_fail)
        ):
            cell_failed = True
        if (
            spec.max_abs_relative_bias_warn is not None
            and rel_bias is not None
            and rel_bias > float(spec.max_abs_relative_bias_warn)
        ):
            cell_warned = True
        if (
            spec.global_pass_rule == "p_value_or_tolerance"
            and cell.p_value_adjusted is not None
            and float(cell.p_value_adjusted) < float(spec.alpha)
        ):
            cell_warned = True
        if cell_failed:
            failed += 1
        elif cell_warned:
            warned += 1

    max_relative = max(relative_biases) if relative_biases else None
    if failed:
        return "fail", failed, warned, max_relative
    if warned or warnings:
        return "warn", failed, warned, max_relative
    return "pass", failed, warned, max_relative


def _status_score(status: str) -> float:
    return {"pass": 0.0, "warn": 1.0, "fail": 2.0, "inconclusive": 3.0}.get(status, 3.0)


def _updated_spec_for_scenario(
    spec: DynamicValidationSpec,
    changed_inputs: Mapping[str, Any],
) -> DynamicValidationSpec:
    payload = spec.model_dump(mode="python")
    payload["sensitivity_scenarios"] = ()
    raw_updates = changed_inputs.get("spec_updates", changed_inputs)
    updates = raw_updates if isinstance(raw_updates, Mapping) else changed_inputs
    for key, value in updates.items():
        if key == "metadata" and isinstance(value, Mapping):
            metadata = dict(payload.get("metadata") or {})
            metadata.update(value)
            payload["metadata"] = metadata
        elif key in payload:
            payload[key] = value
    return DynamicValidationSpec.model_validate(payload)


def _updated_panel_for_scenario(
    panel_data: SurveyMicroData | Mapping[str, Any],
    changed_inputs: Mapping[str, Any],
) -> SurveyMicroData | Mapping[str, Any]:
    updates = changed_inputs.get("panel_data_updates")
    if not isinstance(updates, Mapping) or not isinstance(panel_data, Mapping):
        return panel_data
    merged = dict(panel_data)
    merged.update(updates)
    return merged


def _panel_input_mode(panel_data: SurveyMicroData | Mapping[str, Any]) -> str:
    if _optional_mapping_value(panel_data, "observed_moments") is not None:
        return "precomputed_moments"
    if (
        _optional_mapping_value(panel_data, "observed_income_path") is not None
        or _optional_mapping_value(panel_data, "income_path") is not None
    ):
        return "income_path"
    if (
        (_optional_mapping_value(panel_data, "person_id") is not None
        or _optional_mapping_value(panel_data, "household_ids") is not None)
        and (
            _optional_mapping_value(panel_data, "year") is not None
            or _optional_mapping_value(panel_data, "period_id") is not None
        )
    ):
        return "long_panel"
    return "cross_section_fallback"


def _build_sensitivity_runs(
    result: DynamicMicrosimResult | DynamicMicrosimResultV2,
    panel_data: SurveyMicroData | Mapping[str, Any],
    spec: DynamicValidationSpec,
    base_diagnostic: DynamicMicrosimValidationDiagnostic,
) -> list[SensitivityRunResult]:
    runs: list[SensitivityRunResult] = []
    base_max_bias = base_diagnostic.diagnostics.get("max_abs_relative_bias_primary")
    base_failed = float(base_diagnostic.diagnostics.get("failed_cells_count", 0))
    for scenario in spec.sensitivity_scenarios:
        scenario_spec = _updated_spec_for_scenario(spec, scenario.changed_inputs)
        scenario_panel = _updated_panel_for_scenario(panel_data, scenario.changed_inputs)
        diagnostic = _run_dynamic_validation_core(
            result,
            scenario_panel,
            scenario_spec,
            include_sensitivity=False,
        )
        scenario_max_bias = diagnostic.diagnostics.get("max_abs_relative_bias_primary")
        key_shifts = {
            "status_score_delta": _status_score(diagnostic.status) - _status_score(base_diagnostic.status),
            "failed_cells_delta": float(diagnostic.diagnostics.get("failed_cells_count", 0))
            - base_failed,
        }
        if isinstance(base_max_bias, (int, float)) and isinstance(scenario_max_bias, (int, float)):
            key_shifts["max_abs_relative_bias_primary_delta"] = float(scenario_max_bias) - float(
                base_max_bias
            )
        runs.append(
            SensitivityRunResult(
                scenario_id=scenario.scenario_id,
                changed_inputs=dict(scenario.changed_inputs),
                status=diagnostic.status
                if diagnostic.status in {"pass", "warn", "fail", "inconclusive"}
                else "inconclusive",
                key_shifts=key_shifts,
            )
        )
    return runs


def _run_dynamic_validation_core(
    result: DynamicMicrosimResult | DynamicMicrosimResultV2,
    panel_data: SurveyMicroData | Mapping[str, Any],
    validation_spec: DynamicValidationSpec,
    *,
    include_sensitivity: bool,
) -> DynamicMicrosimValidationDiagnostic:
    """Compare dynamic microsimulation moments with longitudinal panel moments."""

    result_v2 = upgrade_dynamic_microsim_result(result)
    warnings: list[str] = []

    simulated_rows = _simulated_rows_from_payload(panel_data, validation_spec)
    if not simulated_rows:
        simulated_rows = _simulated_rows_from_result(result_v2, validation_spec, warnings)
    observed_rows = _observed_rows_from_panel_data(panel_data, validation_spec, warnings)
    cell_results = _build_cell_results(simulated_rows, observed_rows, validation_spec, warnings)
    omnibus_tests = _build_omnibus_tests(cell_results, validation_spec)
    bias_envelopes = _build_bias_envelopes(cell_results, validation_spec)

    support_audit = {
        str(horizon): _support_for_horizon(validation_spec, int(horizon))
        for horizon in sorted({cell.horizon_years for cell in cell_results})
    }
    if any(support == "extrapolated" for support in support_audit.values()):
        warnings.append("some_horizons_are_extrapolated_beyond_direct_panel_support")
    if any(cell.se is None for cell in cell_results):
        warnings.append("some_cell_tests_lack_standard_errors")

    status, failed_cells, warned_cells, max_relative = _classify_status(
        cell_results, validation_spec, warnings
    )
    diagnostics: dict[str, Any] = {
        "monte_carlo_reps": int(result_v2.metadata.get("monte_carlo_reps", 1)),
        "between_seed_variance_share": result_v2.metadata.get("between_seed_variance_share"),
        "attrition_adjustment": validation_spec.metadata.get("attrition_adjustment"),
        "bootstrap_reps": int(validation_spec.bootstrap_reps),
        "block_length": int(validation_spec.block_length),
        "block_scheme": validation_spec.block_scheme,
        "multiple_testing_correction": validation_spec.multiple_testing_correction,
        "support_audit": support_audit,
        "support_audit_counts": {
            label: int(sum(1 for value in support_audit.values() if value == label))
            for label in ("direct", "stitched", "extrapolated")
        },
        "panel_overlap_degree": validation_spec.metadata.get("panel_overlap_degree"),
        "moment_catalog_primary": sorted(_primary_moment_ids(validation_spec.moment_specs)),
        "failed_cells_count": int(failed_cells),
        "warned_cells_count": int(warned_cells),
        "max_abs_relative_bias_primary": max_relative,
        "global_pass_rule": validation_spec.global_pass_rule,
        "income_concept": validation_spec.income_concept,
        "panel_input_mode": _panel_input_mode(panel_data),
        "recommended_visualizations": [
            "bias_path_with_simultaneous_envelope",
            "standardized_bias_heatmap",
            "observed_vs_simulated_cohort_trajectories",
            "uncertainty_decomposition_waterfall",
        ],
    }

    diagnostic = DynamicMicrosimValidationDiagnostic(
        status=status,  # type: ignore[arg-type]
        comparison_dataset=validation_spec.comparison_dataset,
        comparison_dataset_version=validation_spec.comparison_dataset_version,
        panel_span_years=validation_spec.panel_span_years,
        direct_support_max_horizon=validation_spec.direct_support_max_horizon,
        cohort_dimensions=validation_spec.cohort_dimensions,
        horizons_reported=sorted({int(cell.horizon_years) for cell in cell_results}),
        moment_specs=list(validation_spec.moment_specs),
        cell_results=cell_results,
        omnibus_tests=omnibus_tests,
        bias_envelopes=bias_envelopes,
        diagnostics=diagnostics,
        warnings=sorted(set(warnings)),
        metadata=dict(validation_spec.metadata),
    )
    if include_sensitivity and validation_spec.sensitivity_scenarios:
        sensitivity_runs = _build_sensitivity_runs(
            result_v2,
            panel_data,
            validation_spec,
            diagnostic,
        )
        diagnostic = diagnostic.model_copy(update={"sensitivity_runs": sensitivity_runs})
    return diagnostic


def run_dynamic_validation(
    result: DynamicMicrosimResult | DynamicMicrosimResultV2,
    panel_data: SurveyMicroData | Mapping[str, Any],
    spec: DynamicValidationSpec | Mapping[str, Any],
) -> DynamicMicrosimValidationDiagnostic:
    """Compare dynamic microsimulation moments with longitudinal panel moments."""

    validation_spec = (
        spec if isinstance(spec, DynamicValidationSpec) else DynamicValidationSpec.model_validate(spec)
    )
    return _run_dynamic_validation_core(
        result,
        panel_data,
        validation_spec,
        include_sensitivity=True,
    )


def attach_dynamic_validation(
    result: DynamicMicrosimResult | DynamicMicrosimResultV2,
    panel_data: SurveyMicroData | Mapping[str, Any],
    spec: DynamicValidationSpec | Mapping[str, Any],
) -> DynamicMicrosimResultV2:
    """Return a v2 dynamic result with ``validation_diagnostic`` populated."""

    diagnostic = run_dynamic_validation(result, panel_data, spec)
    return upgrade_dynamic_microsim_result(result, validation_diagnostic=diagnostic)


__all__ = ["attach_dynamic_validation", "run_dynamic_validation"]
