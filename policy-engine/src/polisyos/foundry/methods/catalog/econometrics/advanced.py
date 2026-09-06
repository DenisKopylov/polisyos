"""Estimate non-linear, event-study, volatility, and structural-break econometric models."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from statistics import NormalDist
from typing import Any, ClassVar

import numpy as np

from polisyos.calibration.continuous import evaluate_continuous
from polisyos.core.observability import DeterminismTier
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
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastingUncertaintyBundle,
    ForecastIntervalSemantics,
    HorizonDiagnosticState,
    HorizonInterval,
    HorizonPolicyRule,
    HorizonPolicySpec,
    HorizonQuantileSet,
)

from .protocols import (
    EconometricResult,
    NonstationaryVolatilitySummary,
    PanelData,
    TimeSeriesData,
    VolatilityBreak,
    VolatilityBreakDetectionMethod,
    VolatilityCoverageSummary,
    VolatilityLossFamily,
    VolatilityRegimeSegment,
)


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except Exception:
        return None
    if not np.isfinite(result):
        return None
    return result


def _panel_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=PanelData,
        nested_keys=("panel_data",),
    )


def _time_series_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=TimeSeriesData,
        nested_keys=("time_series_data",),
    )


def _panel_observational_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=PanelObservationalData,
        nested_keys=("panel_data", "panel_observational_data"),
    )


def _result_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec.for_output_contract(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("result", "json"),
                output_contract=EconometricResult,
            ),
            SlotSpec(
                name="uncertainty_envelope",
                slot_type=SlotType.SCALAR,
                unit=Unit("uncertainty", "json"),
            ),
        }
    )


def _volatility_output_slots() -> frozenset[SlotSpec]:
    return _result_output_slots().union(
        {
            SlotSpec.for_output_contract(
                name="forecasting_uncertainty_bundle",
                slot_type=SlotType.SCALAR,
                unit=Unit("uncertainty", "json"),
                output_contract=ForecastingUncertaintyBundle,
            ),
        }
    )


def _build_regression_result(
    *,
    method_name: str,
    params: Mapping[str, Any],
    std_errors: Mapping[str, Any] | None = None,
    p_values: Mapping[str, Any] | None = None,
    confidence_intervals: Mapping[str, tuple[float, float]] | None = None,
    diagnostics: dict[str, Any] | None = None,
    model_info: dict[str, Any] | None = None,
    n_obs: int = 0,
    n_periods: int | None = None,
) -> EconometricResult:
    return EconometricResult(
        method_name=method_name,
        params={str(k): float(v) for k, v in params.items() if _safe_float(v) is not None},
        std_errors={
            str(k): float(v) for k, v in (std_errors or {}).items() if _safe_float(v) is not None
        },
        p_values={
            str(k): float(v) for k, v in (p_values or {}).items() if _safe_float(v) is not None
        },
        confidence_intervals=dict(confidence_intervals or {}),
        diagnostics=diagnostics or {},
        model_info=model_info or {},
        n_obs=int(n_obs),
        n_periods=n_periods,
    )


def _python_scalar(value: Any) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, (str, int, float)):
        return value
    try:
        return float(value)
    except Exception:
        return str(value)


def _sanitize_group_label(value: Any) -> str:
    text = "".join(ch if str(ch).isalnum() else "_" for ch in str(value).strip())
    normalized = text.strip("_").lower()
    return normalized or "group"


def _resolve_interval_levels(value: Any) -> tuple[float, ...]:
    if value is None:
        return (0.5, 0.8, 0.9, 0.95)
    if isinstance(value, (list, tuple)):
        levels = tuple(float(item) for item in value)
    else:
        levels = tuple(float(item.strip()) for item in str(value).split(",") if item.strip())
    if not levels:
        raise ValueError("diagnostic_levels must contain at least one coverage level")
    for level in levels:
        if not 0.0 < level < 1.0:
            raise ValueError("diagnostic_levels must stay inside (0, 1)")
    return tuple(sorted(set(levels)))


def _balanced_panel_arrays(
    data: PanelData,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    entities = np.unique(np.asarray(data.entity_ids))
    times = np.unique(np.asarray(data.time_ids))
    y_matrix = np.full((entities.size, times.size), np.nan, dtype=float)
    x_tensor = np.full((entities.size, times.size, data.n_features), np.nan, dtype=float)
    entity_lookup = {entity: idx for idx, entity in enumerate(entities.tolist())}
    time_lookup = {time: idx for idx, time in enumerate(times.tolist())}

    dependent = np.asarray(data.dependent, dtype=float)
    exog = np.asarray(data.exog, dtype=float)
    entity_ids = np.asarray(data.entity_ids)
    time_ids = np.asarray(data.time_ids)

    for row_idx in range(data.n_obs):
        entity = (
            entity_ids[row_idx].item()
            if isinstance(entity_ids[row_idx], np.generic)
            else entity_ids[row_idx]
        )
        time = (
            time_ids[row_idx].item()
            if isinstance(time_ids[row_idx], np.generic)
            else time_ids[row_idx]
        )
        e_idx = entity_lookup[entity]
        t_idx = time_lookup[time]
        if np.isfinite(y_matrix[e_idx, t_idx]):
            raise ValueError(
                "nonstationary_garch requires a balanced panel without duplicate entity/time rows"
            )
        y_matrix[e_idx, t_idx] = dependent[row_idx]
        x_tensor[e_idx, t_idx, :] = exog[row_idx]

    if np.isnan(y_matrix).any() or np.isnan(x_tensor).any():
        raise ValueError(
            "nonstationary_garch currently requires a balanced panel without missing cells"
        )
    return y_matrix, x_tensor, entities, times


def _resolve_entity_group_map(
    data: PanelData,
    entities: np.ndarray,
) -> tuple[dict[Any, str], str]:
    metadata = data.metadata if isinstance(data.metadata, dict) else {}
    raw = (
        metadata.get("group_labels") or metadata.get("group_assignments") or metadata.get("groups")
    )
    if raw is None:
        return (dict.fromkeys(entities.tolist(), "pooled"), "metadata_default:pooled")

    if isinstance(raw, Mapping):
        group_map: dict[Any, str] = {}
        for entity in entities.tolist():
            group = raw.get(entity)
            if group is None:
                group = raw.get(str(entity))
            if group is None:
                raise ValueError("group_labels mapping must provide a label for every entity")
            group_map[entity] = str(group)
        return group_map, "metadata_mapping"

    labels = np.asarray(raw, dtype=object).reshape(-1)
    if labels.size == entities.size:
        return (
            {entity: str(labels[idx]) for idx, entity in enumerate(entities.tolist())},
            "metadata_entity_vector",
        )
    if labels.size == data.n_obs:
        row_entity_ids = np.asarray(data.entity_ids)
        group_map = {}
        for entity in entities.tolist():
            entity_mask = row_entity_ids == entity
            entity_labels = {str(item) for item in labels[entity_mask].tolist()}
            if len(entity_labels) != 1:
                raise ValueError("row-aligned group labels must be constant within each entity")
            group_map[entity] = next(iter(entity_labels))
        return group_map, "metadata_row_vector"
    raise ValueError("group_labels must be a mapping, entity-aligned vector, or row-aligned vector")


def _break_detection_score(proxy: np.ndarray, breakpoint_index: int, window: int) -> float | None:
    if breakpoint_index <= 0 or breakpoint_index >= proxy.shape[0]:
        return None
    left = np.log(np.maximum(proxy[max(0, breakpoint_index - window) : breakpoint_index], 1e-8))
    right = np.log(
        np.maximum(proxy[breakpoint_index : min(proxy.shape[0], breakpoint_index + window)], 1e-8)
    )
    if left.size == 0 or right.size == 0:
        return None
    return float(abs(np.mean(right) - np.mean(left)))


def _detect_group_breaks(
    proxy: np.ndarray,
    *,
    method: VolatilityBreakDetectionMethod,
    max_breaks: int,
    min_segment_length: int,
    penalty: float,
) -> list[int]:
    if method is VolatilityBreakDetectionMethod.NONE or max_breaks <= 0:
        return []
    if proxy.shape[0] < 2 * max(min_segment_length, 1):
        return []

    try:
        import ruptures as rpt
    except ModuleNotFoundError:
        candidate_scores: list[tuple[float, int]] = []
        for breakpoint in range(min_segment_length, proxy.shape[0] - min_segment_length + 1):
            score = _break_detection_score(proxy, breakpoint, min_segment_length)
            if score is not None:
                candidate_scores.append((float(score), int(breakpoint)))
        chosen: list[int] = []
        for _, breakpoint in sorted(candidate_scores, reverse=True):
            if any(abs(breakpoint - existing) < min_segment_length for existing in chosen):
                continue
            chosen.append(int(breakpoint))
            if len(chosen) >= max_breaks:
                break
        return sorted(chosen)

    signal = np.log(np.maximum(np.asarray(proxy, dtype=float), 1e-8)).reshape(-1, 1)
    if method is VolatilityBreakDetectionMethod.BINSEG_LOG_VARIANCE:
        algo = rpt.Binseg(model="l2", min_size=max(min_segment_length, 2)).fit(signal)
        candidates = algo.predict(n_bkps=max_breaks)
    else:
        algo = rpt.Pelt(model="l2", min_size=max(min_segment_length, 2)).fit(signal)
        candidates = algo.predict(pen=float(penalty))

    return [
        int(breakpoint)
        for breakpoint in candidates[:-1]
        if min_segment_length <= int(breakpoint) <= signal.shape[0] - min_segment_length
    ][:max_breaks]


def _segment_boundaries(total_periods: int, breakpoints: list[int] | tuple[int, ...]) -> list[int]:
    cleaned = sorted(
        {int(breakpoint) for breakpoint in breakpoints if 0 < int(breakpoint) < int(total_periods)}
    )
    return [0, *cleaned, int(total_periods)]


def _winsorize_huber_proxy(
    series: np.ndarray, *, kappa: float
) -> tuple[np.ndarray, dict[str, float]]:
    arr = np.asarray(series, dtype=float)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    scale = 1.4826 * mad if mad > 1e-8 else float(np.std(arr, ddof=1) if arr.size > 1 else 0.0)
    if scale <= 1e-8:
        return arr.copy(), {"winsorized_share": 0.0, "clip_scale": 0.0}
    lower = median - kappa * scale
    upper = median + kappa * scale
    clipped = np.clip(arr, lower, upper)
    winsorized_share = float(np.mean(np.abs(clipped - arr) > 1e-12))
    return clipped, {"winsorized_share": winsorized_share, "clip_scale": float(scale)}


def _persistence_from_params(params: Mapping[str, float]) -> float | None:
    total = 0.0
    found = False
    for name, value in params.items():
        if name.startswith("alpha[") or name.startswith("beta["):
            total += float(value)
            found = True
    return total if found else None


def _chi_square_tail_df1(statistic: float) -> float:
    return math.erfc(math.sqrt(max(statistic, 0.0) / 2.0))


def _christoffersen_pvalues(covered: np.ndarray, alpha: float) -> tuple[float | None, float | None]:
    hits = np.asarray(covered, dtype=bool).astype(int).reshape(-1)
    if hits.size < 2:
        return None, None

    misses = 1 - hits
    n_obs = int(misses.size)
    n_miss = int(np.sum(misses))
    alpha = min(max(float(alpha), 1e-12), 1.0 - 1e-12)
    p_hat = n_miss / max(n_obs, 1)
    loglik_null = n_miss * math.log(alpha) + (n_obs - n_miss) * math.log(1.0 - alpha)
    loglik_alt = n_miss * math.log(max(p_hat, 1e-12)) + (n_obs - n_miss) * math.log(
        max(1.0 - p_hat, 1e-12)
    )
    lr_uc = -2.0 * (loglik_null - loglik_alt)
    conditional = _chi_square_tail_df1(lr_uc)

    n00 = n01 = n10 = n11 = 0
    for left, right in zip(misses[:-1], misses[1:], strict=True):
        if left == 0 and right == 0:
            n00 += 1
        elif left == 0 and right == 1:
            n01 += 1
        elif left == 1 and right == 0:
            n10 += 1
        else:
            n11 += 1
    total = n00 + n01 + n10 + n11
    if total == 0:
        return conditional, None

    pi = (n01 + n11) / max(total, 1)
    pi01 = n01 / max(n00 + n01, 1)
    pi11 = n11 / max(n10 + n11, 1)
    null_loglik = (n00 + n10) * math.log(max(1.0 - pi, 1e-12)) + (n01 + n11) * math.log(
        max(pi, 1e-12)
    )
    alt_loglik = (
        n00 * math.log(max(1.0 - pi01, 1e-12))
        + n01 * math.log(max(pi01, 1e-12))
        + n10 * math.log(max(1.0 - pi11, 1e-12))
        + n11 * math.log(max(pi11, 1e-12))
    )
    independence = _chi_square_tail_df1(-2.0 * (null_loglik - alt_loglik))
    return conditional, independence


def _weighted_interval_score(
    y_true: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    *,
    alpha: float,
) -> float:
    width = np.maximum(np.asarray(upper, dtype=float) - np.asarray(lower, dtype=float), 0.0)
    penalties = (2.0 / max(alpha, 1e-12)) * np.maximum(lower - y_true, 0.0)
    penalties += (2.0 / max(alpha, 1e-12)) * np.maximum(y_true - upper, 0.0)
    return float(np.mean(width + penalties))


def _resolve_holdout_length(
    segment_length: int,
    requested_holdout: int,
    *,
    min_train_length: int,
) -> int:
    if requested_holdout <= 0:
        return 0
    max_holdout = max(int(segment_length) - int(min_train_length), 0)
    if max_holdout <= 0:
        return 0
    return min(int(requested_holdout), max_holdout)


def _extract_forecast_sigmas(forecast_variance: Any, horizon: int) -> np.ndarray:
    arr = np.asarray(forecast_variance, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1, 1)
    elif arr.ndim == 1:
        arr = arr.reshape(1, -1)
    sigmas = np.sqrt(np.maximum(arr[-1, :horizon], 1e-12))
    return sigmas.reshape(-1)


def _fit_garch_segment_payload(
    series: np.ndarray,
    *,
    p: int,
    q: int,
    mean_model: str,
    distribution: str,
    loss_family: VolatilityLossFamily,
    huber_kappa: float,
    all_levels: tuple[float, ...],
    nominal_coverage: float,
    holdout_periods: int,
    min_train_length: int,
) -> dict[str, Any] | None:
    from arch import arch_model

    series = np.asarray(series, dtype=float).reshape(-1)
    fit_series = series
    loss_diag: dict[str, float] = {"winsorized_share": 0.0}
    if loss_family is VolatilityLossFamily.HUBER_PROXY:
        fit_series, loss_diag = _winsorize_huber_proxy(series, kappa=huber_kappa)

    fit = arch_model(
        fit_series,
        mean=mean_model,
        vol="GARCH",
        p=p,
        q=q,
        dist=distribution,
        rescale=False,
    ).fit(disp="off")

    param_dict = {str(key): float(value) for key, value in fit.params.items()}
    std_error_dict = {str(key): float(value) for key, value in fit.std_err.items()}
    conditional_vol = np.asarray(fit.conditional_volatility, dtype=float).reshape(-1)
    mu = float(param_dict.get("mu", 0.0))

    try:
        forecast = fit.forecast(horizon=1, reindex=False)
        next_sigma = float(_extract_forecast_sigmas(forecast.variance, 1)[0])
    except Exception:
        next_sigma = float(conditional_vol[-1])

    evaluation_mode = "in_sample_proxy"
    eval_series = series
    eval_mu = mu
    eval_sigmas = conditional_vol

    holdout_length = _resolve_holdout_length(
        segment_length=series.size,
        requested_holdout=holdout_periods,
        min_train_length=min_train_length,
    )
    if holdout_length > 0:
        try:
            train_series = fit_series[:-holdout_length]
            train_fit = arch_model(
                train_series,
                mean=mean_model,
                vol="GARCH",
                p=p,
                q=q,
                dist=distribution,
                rescale=False,
            ).fit(disp="off")
            forecast = train_fit.forecast(horizon=holdout_length, reindex=False)
            forecast_sigmas = _extract_forecast_sigmas(forecast.variance, holdout_length)
            if forecast_sigmas.size == holdout_length:
                eval_series = series[-holdout_length:]
                eval_mu = float(train_fit.params.get("mu", mu))
                eval_sigmas = forecast_sigmas
                evaluation_mode = "blocked_holdout"
        except Exception:
            evaluation_mode = "in_sample_proxy"

    intervals = {}
    for level in all_levels:
        z = NormalDist().inv_cdf((1.0 + level) / 2.0)
        lower = eval_mu - z * eval_sigmas
        upper = eval_mu + z * eval_sigmas
        intervals[level] = [(float(lo), float(hi)) for lo, hi in zip(lower, upper, strict=True)]

    return {
        "params": param_dict,
        "std_errors": std_error_dict,
        "conditional_vol": conditional_vol,
        "next_sigma": next_sigma,
        "next_mean": mu,
        "loss_diag": loss_diag,
        "eval_series": np.asarray(eval_series, dtype=float),
        "intervals": intervals,
        "evaluation_mode": evaluation_mode,
    }


def _summarize_interval_diagnostics(
    *,
    y_values: list[float],
    intervals_by_level: Mapping[float, list[tuple[float, float]]],
    all_levels: tuple[float, ...],
    nominal_coverage: float,
) -> dict[str, Any]:
    y_true = np.asarray(y_values, dtype=float)
    primary_intervals = intervals_by_level[nominal_coverage]
    lower = np.asarray([item[0] for item in primary_intervals], dtype=float)
    upper = np.asarray([item[1] for item in primary_intervals], dtype=float)
    covered = (y_true >= lower) & (y_true <= upper)
    conditional_pvalue, independence_pvalue = _christoffersen_pvalues(
        covered,
        alpha=1.0 - nominal_coverage,
    )
    report = evaluate_continuous(
        y_true=y_true.tolist(),
        intervals={level: intervals_by_level[level] for level in all_levels},
        levels=list(all_levels),
        strict=True,
    )
    wis = _weighted_interval_score(
        y_true,
        lower,
        upper,
        alpha=1.0 - nominal_coverage,
    )
    return {
        "y_true": y_true,
        "lower": lower,
        "upper": upper,
        "covered": covered,
        "empirical_coverage": float(np.mean(covered)) if covered.size else None,
        "conditional_pvalue": conditional_pvalue,
        "independence_pvalue": independence_pvalue,
        "report": report,
        "mean_interval_width": float(np.mean(upper - lower)),
        "wis": wis,
    }


def _select_group_breaks_by_bic(
    group_returns: np.ndarray,
    screened_breaks: list[int],
    *,
    p: int,
    q: int,
    mean_model: str,
    distribution: str,
    loss_family: VolatilityLossFamily,
    huber_kappa: float,
    min_segment_length: int,
) -> tuple[list[int], dict[str, Any]]:
    from arch import arch_model

    candidates = [tuple()] + [
        tuple(screened_breaks[:idx]) for idx in range(1, len(screened_breaks) + 1)
    ]
    candidate_rows: list[dict[str, Any]] = []
    best_breaks: tuple[int, ...] = tuple()
    best_bic = float("inf")

    for candidate in candidates:
        total_loglikelihood = 0.0
        total_params = 0
        successful_fits = 0
        boundaries = _segment_boundaries(group_returns.shape[1], candidate)
        for start_idx, end_idx in zip(boundaries[:-1], boundaries[1:], strict=True):
            if end_idx - start_idx < min_segment_length:
                total_loglikelihood = float("-inf")
                break
            for entity_series in group_returns[:, start_idx:end_idx]:
                fit_series = np.asarray(entity_series, dtype=float)
                if loss_family is VolatilityLossFamily.HUBER_PROXY:
                    fit_series, _ = _winsorize_huber_proxy(fit_series, kappa=huber_kappa)
                try:
                    fit = arch_model(
                        fit_series,
                        mean=mean_model,
                        vol="GARCH",
                        p=p,
                        q=q,
                        dist=distribution,
                        rescale=False,
                    ).fit(disp="off")
                except Exception:
                    continue
                total_loglikelihood += float(fit.loglikelihood)
                total_params += len(fit.params)
                successful_fits += 1

        n_obs = int(group_returns.size)
        bic = float("inf")
        if successful_fits > 0 and np.isfinite(total_loglikelihood):
            bic = float(-2.0 * total_loglikelihood + total_params * math.log(max(n_obs, 2)))
        candidate_rows.append(
            {
                "breakpoints": list(candidate),
                "n_breaks": len(candidate),
                "bic": bic,
                "successful_fits": successful_fits,
            }
        )
        if bic < best_bic:
            best_bic = bic
            best_breaks = candidate

    return list(best_breaks), {
        "screened_breaks": list(screened_breaks),
        "bic_candidates": candidate_rows,
        "selected_break_count": len(best_breaks),
        "selected_bic": best_bic,
    }


def _evaluate_panel_volatility_scenario(
    *,
    scenario_name: str,
    y_matrix: np.ndarray,
    entities: np.ndarray,
    group_map: Mapping[Any, str],
    p: int,
    q: int,
    max_breaks: int,
    min_segment_length: int,
    break_method: VolatilityBreakDetectionMethod,
    break_penalty: float,
    mean_model: str,
    distribution: str,
    loss_family: VolatilityLossFamily,
    huber_kappa: float,
    nominal_coverage: float,
    all_levels: tuple[float, ...],
    holdout_periods: int,
) -> dict[str, Any]:
    entity_list = entities.tolist()
    ordered_groups = sorted({str(group_map[entity]) for entity in entity_list})
    intervals_by_level = {level: [] for level in all_levels}
    y_values: list[float] = []
    evaluation_modes: set[str] = set()
    total_breaks = 0
    total_regimes = 0

    for group_label in ordered_groups:
        group_entity_indices = [
            idx for idx, entity in enumerate(entity_list) if str(group_map[entity]) == group_label
        ]
        group_returns = y_matrix[group_entity_indices, :]
        screened_breaks = _detect_group_breaks(
            np.mean(np.square(group_returns), axis=0),
            method=break_method,
            max_breaks=max_breaks,
            min_segment_length=min_segment_length,
            penalty=break_penalty,
        )
        selected_breaks, _ = _select_group_breaks_by_bic(
            group_returns,
            screened_breaks,
            p=p,
            q=q,
            mean_model=mean_model,
            distribution=distribution,
            loss_family=loss_family,
            huber_kappa=huber_kappa,
            min_segment_length=min_segment_length,
        )
        total_breaks += len(selected_breaks)
        boundaries = _segment_boundaries(y_matrix.shape[1], selected_breaks)
        total_regimes += len(boundaries) - 1
        for start_idx, end_idx in zip(boundaries[:-1], boundaries[1:], strict=True):
            for entity_idx in group_entity_indices:
                try:
                    payload = _fit_garch_segment_payload(
                        y_matrix[entity_idx, start_idx:end_idx],
                        p=p,
                        q=q,
                        mean_model=mean_model,
                        distribution=distribution,
                        loss_family=loss_family,
                        huber_kappa=huber_kappa,
                        all_levels=all_levels,
                        nominal_coverage=nominal_coverage,
                        holdout_periods=holdout_periods,
                        min_train_length=max(min_segment_length // 2, max(p, q) + 5),
                    )
                except Exception:
                    continue
                if payload is None:
                    continue
                y_values.extend(payload["eval_series"].tolist())
                for level in all_levels:
                    intervals_by_level[level].extend(payload["intervals"][level])
                evaluation_modes.add(str(payload["evaluation_mode"]))

    if not y_values:
        return {
            "scenario": scenario_name,
            "status": "failed",
            "n_groups": len(ordered_groups),
            "n_regimes": total_regimes,
            "break_count": total_breaks,
        }

    diagnostics = _summarize_interval_diagnostics(
        y_values=y_values,
        intervals_by_level=intervals_by_level,
        all_levels=all_levels,
        nominal_coverage=nominal_coverage,
    )
    empirical = diagnostics["empirical_coverage"]
    return {
        "scenario": scenario_name,
        "status": "ok",
        "n_groups": len(ordered_groups),
        "n_regimes": total_regimes,
        "break_count": total_breaks,
        "sample_count": int(diagnostics["y_true"].size),
        "coverage_semantics": (
            "blocked_holdout"
            if "blocked_holdout" in evaluation_modes
            else "in_sample_one_step_proxy"
        ),
        "empirical_coverage": empirical,
        "coverage_gap": None if empirical is None else float(empirical - nominal_coverage),
        "ece": diagnostics["report"].metrics.ece,
        "max_calibration_error": diagnostics["report"].metrics.mce,
        "conditional_coverage_pvalue": diagnostics["conditional_pvalue"],
        "independence_pvalue": diagnostics["independence_pvalue"],
        "mean_interval_width": diagnostics["mean_interval_width"],
        "wis": diagnostics["wis"],
    }


def _volatility_diagnostic_state(
    empirical_coverage: float | None,
    nominal_coverage: float,
    sample_count: int,
    conditional_pvalue: float | None,
    independence_pvalue: float | None,
) -> HorizonDiagnosticState:
    if empirical_coverage is None or sample_count < 10:
        return HorizonDiagnosticState.RED
    if empirical_coverage < nominal_coverage - 0.10:
        return HorizonDiagnosticState.RED
    if conditional_pvalue is not None and conditional_pvalue < 0.05:
        return HorizonDiagnosticState.RED
    if independence_pvalue is not None and independence_pvalue < 0.05:
        return HorizonDiagnosticState.RED
    if abs(empirical_coverage - nominal_coverage) > 0.05:
        return HorizonDiagnosticState.AMBER
    return HorizonDiagnosticState.GREEN


def _build_nonstationary_uncertainty_bundle(
    *,
    method_fqn: str,
    target_id: str,
    nominal_coverage: float,
    empirical_coverage: float | None,
    conditional_pvalue: float | None,
    independence_pvalue: float | None,
    mean_interval_width: float | None,
    wis: float | None,
    sample_count: int,
    point_forecast: float,
    sigma_forecast: float,
    regime_flags: tuple[str, ...],
    sample_size_assumption: str,
) -> ForecastingUncertaintyBundle:
    generated_at = datetime.now(UTC)
    quantile_levels = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
    lower_quantile = (1.0 - nominal_coverage) / 2.0
    upper_quantile = 1.0 - lower_quantile
    lower = point_forecast + sigma_forecast * NormalDist().inv_cdf(lower_quantile)
    upper = point_forecast + sigma_forecast * NormalDist().inv_cdf(upper_quantile)
    diagnostic_state = _volatility_diagnostic_state(
        empirical_coverage=empirical_coverage,
        nominal_coverage=nominal_coverage,
        sample_count=sample_count,
        conditional_pvalue=conditional_pvalue,
        independence_pvalue=independence_pvalue,
    )
    fallback = (
        ForecastCalibrationMethod.CONFORMAL
        if diagnostic_state is not HorizonDiagnosticState.GREEN
        else None
    )
    quantiles = {
        str(level): point_forecast + sigma_forecast * NormalDist().inv_cdf(level)
        for level in quantile_levels
    }
    gap = None if empirical_coverage is None else float(empirical_coverage - nominal_coverage)
    return ForecastingUncertaintyBundle(
        method_fqn=method_fqn,
        target_id=target_id,
        generated_at=generated_at,
        prediction_interval=(
            HorizonInterval(
                horizon=1,
                point=point_forecast,
                lower=lower,
                upper=upper,
                coverage_target=nominal_coverage,
                constructor=ForecastCalibrationMethod.PARAMETRIC,
                sample_count=sample_count if sample_count > 0 else None,
            ),
        ),
        fan_chart=FanChartSpec(
            quantile_levels=quantile_levels,
            horizons=(HorizonQuantileSet(horizon=1, quantiles=quantiles),),
        ),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=nominal_coverage,
            empirical_coverage_by_horizon={}
            if empirical_coverage is None
            else {1: empirical_coverage},
            coverage_gap_by_horizon={} if gap is None else {1: gap},
            mean_interval_width_by_horizon={}
            if mean_interval_width is None
            else {1: mean_interval_width},
            conditional_coverage_pvalue_by_horizon={}
            if conditional_pvalue is None
            else {1: conditional_pvalue},
            independence_pvalue_by_horizon={}
            if independence_pvalue is None
            else {1: independence_pvalue},
            wis_by_horizon={} if wis is None else {1: wis},
            sample_count_by_horizon={1: sample_count},
            regime_flags=regime_flags,
            recommended_fallback=fallback,
            calibration_window=sample_count,
            last_recalibrated_at=generated_at,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.PARAMETRIC,
            rules=(
                HorizonPolicyRule(
                    horizon_start=1,
                    horizon_end=1,
                    diagnostic_state=diagnostic_state,
                    allowed_methods=(
                        (ForecastCalibrationMethod.PARAMETRIC, ForecastCalibrationMethod.CONFORMAL)
                        if diagnostic_state is not HorizonDiagnosticState.RED
                        else (ForecastCalibrationMethod.CONFORMAL,)
                    ),
                    gate_eligible=diagnostic_state is not HorizonDiagnosticState.RED,
                    fallback=fallback,
                    regime="structural_break_garch",
                ),
            ),
            gate_eligible=diagnostic_state is not HorizonDiagnosticState.RED,
            summary="Group-aware structural-break volatility coverage at horizon 1",
        ),
        interval_semantics=ForecastIntervalSemantics.PREDICTION_INTERVAL,
        calibration_method=ForecastCalibrationMethod.PARAMETRIC,
        nominal_coverage=nominal_coverage,
        sample_size_assumption=sample_size_assumption,
        regime_assumption="group-specific finite structural breaks",
        metadata={"bundle_scope": "policy_risk_nonstationary_garch"},
    )


@foundry_method(
    namespace="econometrics.regression",
    version="1.0.0",
    tags={"econometrics", "quantile-regression"},
)
class QuantileRegressionEstimator:
    """Estimate conditional quantiles under asymmetric loss; avoid tiny samples or sparse tails."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="quantile_regression",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("dependent", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "exog", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")
                ),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="quantile", default=0.5),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Quantile regression for heterogeneous effects across the conditional distribution.",
        tags=frozenset({"econometrics", "quantile-regression"}),
        citations=("Koenker, R. (2005). Quantile Regression.",),
        when_to_use="Distributional effects of treatment/policy; heterogeneous impacts at different outcome quantiles",
        typical_min_obs=100,
        output_interpretation="Conditional quantile function. β(τ): effect at quantile τ. Plot β(τ) vs τ to see distributional heterogeneity.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        payload = _panel_payload(fallback_state)
        payload.update(bound_inputs)
        return PanelData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: PanelData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        import statsmodels.api as sm

        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        q = float(params.get("quantile", 0.5))
        confidence_level = float(params.get("confidence_level", 0.95))
        x = sm.add_constant(np.asarray(data.exog), has_constant="add")
        fit = sm.QuantReg(np.asarray(data.dependent), x).fit(q=q)
        names = ["const"] + list(data.feature_names or [f"x{i}" for i in range(data.exog.shape[1])])
        ci = fit.conf_int(alpha=1.0 - confidence_level)
        intervals = {
            names[idx]: (float(ci[idx, 0]), float(ci[idx, 1]))
            for idx in range(min(len(names), ci.shape[0]))
        }
        result = _build_regression_result(
            method_name="quantile_regression",
            params={names[idx]: fit.params[idx] for idx in range(len(names))},
            std_errors={names[idx]: fit.bse[idx] for idx in range(len(names))},
            p_values={names[idx]: fit.pvalues[idx] for idx in range(len(names))},
            confidence_intervals=intervals,
            diagnostics={
                "quantile": q,
                "pseudo_r_squared": _safe_float(getattr(fit, "prsquared", None)),
            },
            model_info={"library": "statsmodels", "estimator": "QuantReg"},
            n_obs=data.n_obs,
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "event-study"},
)
class EventStudyEstimator:
    """Estimate dynamic event-time effects under a valid control trend; avoid contaminated controls or weak pre-period support."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="event_study",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "outcome",
                    SlotType.MATRIX,
                    Unit("outcome", "value"),
                    shape=("n_units", "n_periods"),
                ),
                SlotSpec("treatment", SlotType.VECTOR, Unit("binary", "flag"), shape=("n_units",)),
                SlotSpec("time_treatment", SlotType.SCALAR, Unit("time", "index")),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="pre_window", default=4),
            ParameterSpec(name="post_window", default=4),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Simple event-study estimator over relative treatment time.",
        tags=frozenset({"econometrics", "event-study"}),
        citations=(
            "Sun, L. & Abraham, S. (2021). Estimating dynamic treatment effects in event studies.",
        ),
        when_to_use="Panel data with staggered or common treatment timing; plot dynamic treatment effects around event",
        typical_min_obs=50,
        output_interpretation="Coefficients at each relative period (pre/post event). Pre-period estimates should be near zero (parallel trends check).",
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> PanelObservationalData:
        payload = _panel_observational_payload(fallback_state)
        payload.update(bound_inputs)
        return PanelObservationalData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: PanelObservationalData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        timing = (
            np.asarray(data.treatment_timing)
            if data.treatment_timing is not None
            else np.where(np.asarray(data.treatment) == 1, int(data.time_treatment), -1)
        )
        pre_window = max(1, int(params.get("pre_window", 4)))
        post_window = max(1, int(params.get("post_window", 4)))
        confidence_level = float(params.get("confidence_level", 0.95))
        z = 1.959963984540054 if confidence_level >= 0.95 else 1.6448536269514722

        estimates: dict[str, float] = {}
        ses: dict[str, float] = {}
        pvalues: dict[str, float] = {}
        intervals: dict[str, tuple[float, float]] = {}
        n_cells = 0
        for rel_time in range(-pre_window, post_window + 1):
            if rel_time == -1:
                continue
            cell_effects: list[float] = []
            for unit_idx, start in enumerate(timing):
                if start < 0:
                    continue
                event_t = int(start + rel_time)
                baseline_t = int(start - 1)
                if event_t < 0 or event_t >= data.n_periods or baseline_t < 0:
                    continue
                control_mask = timing == -1
                if not control_mask.any():
                    control_mask = np.asarray(data.treatment) == 0
                if not control_mask.any():
                    continue
                treated_delta = float(
                    data.outcome[unit_idx, event_t] - data.outcome[unit_idx, baseline_t]
                )
                control_delta = float(
                    np.mean(
                        data.outcome[control_mask, event_t] - data.outcome[control_mask, baseline_t]
                    )
                )
                cell_effects.append(treated_delta - control_delta)
            if not cell_effects:
                continue
            arr = np.asarray(cell_effects, dtype=float)
            estimate = float(np.mean(arr))
            se = float(np.std(arr, ddof=1) / np.sqrt(arr.shape[0])) if arr.shape[0] > 1 else 0.0
            label = f"event_t{rel_time:+d}"
            estimates[label] = estimate
            ses[label] = se
            z_score = 0.0 if se <= 0 else estimate / se
            p = float(math.erfc(abs(z_score) / np.sqrt(2.0)))
            pvalues[label] = p
            intervals[label] = (estimate - z * se, estimate + z * se)
            n_cells += int(arr.shape[0])

        result = _build_regression_result(
            method_name="event_study",
            params=estimates,
            std_errors=ses,
            p_values=pvalues,
            confidence_intervals=intervals,
            diagnostics={"n_cells": n_cells, "pre_window": pre_window, "post_window": post_window},
            model_info={"library": "numpy", "estimator": "event_study"},
            n_obs=int(data.n_units * data.n_periods),
            n_periods=data.n_periods,
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


@foundry_method(
    namespace="econometrics.timeseries",
    version="1.0.0",
    tags={"econometrics", "local-projections"},
)
class LocalProjectionsEstimator:
    """Estimate impulse responses horizon-by-horizon; avoid short samples with too many horizons or weak shock identification."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="local_projections",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",)),
                SlotSpec(
                    "exog", SlotType.MATRIX, Unit("shock", "value"), shape=("n_obs", "n_features")
                ),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="max_horizon", default=6),
            ParameterSpec(name="n_lags", default=2),
            ParameterSpec(name="shock_column", default=0),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Jorda local projections for impulse responses.",
        tags=frozenset({"econometrics", "local-projections"}),
        citations=(
            "Jorda, O. (2005). Estimation and Inference of Impulse Responses by Local Projections.",
        ),
        when_to_use="Flexible impulse response estimation without VAR model restrictions; non-linear or state-dependent dynamics",
        typical_min_obs=80,
        output_interpretation="IRF at each horizon h. Plot irf_h0 through irf_hH with CIs. More robust to misspecification than VAR-based IRFs.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: TimeSeriesData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        import statsmodels.api as sm

        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        y = np.asarray(data.endog, dtype=float)
        if y.ndim != 1:
            raise ValueError("local projections currently require 1D endog")
        if data.exog is None:
            raise ValueError("local projections require exog with a shock column")
        shocks = np.asarray(data.exog, dtype=float)
        shock_col = int(params.get("shock_column", 0))
        max_horizon = max(1, int(params.get("max_horizon", 6)))
        n_lags = max(1, int(params.get("n_lags", 2)))
        confidence_level = float(params.get("confidence_level", 0.95))
        z = 1.959963984540054 if confidence_level >= 0.95 else 1.6448536269514722

        estimates: dict[str, float] = {}
        ses: dict[str, float] = {}
        pvalues: dict[str, float] = {}
        intervals: dict[str, tuple[float, float]] = {}
        for horizon in range(max_horizon + 1):
            rows = []
            targets = []
            for t in range(n_lags, y.shape[0] - horizon):
                lagged = [y[t - lag] for lag in range(1, n_lags + 1)]
                rows.append([shocks[t, shock_col], *lagged])
                targets.append(y[t + horizon])
            x = sm.add_constant(np.asarray(rows, dtype=float), has_constant="add")
            fit = sm.OLS(np.asarray(targets, dtype=float), x).fit(cov_type="HC1")
            key = f"irf_h{horizon}"
            estimate = float(fit.params[1])
            se = float(fit.bse[1])
            p = float(fit.pvalues[1])
            estimates[key] = estimate
            ses[key] = se
            pvalues[key] = p
            intervals[key] = (estimate - z * se, estimate + z * se)

        result = _build_regression_result(
            method_name="local_projections",
            params=estimates,
            std_errors=ses,
            p_values=pvalues,
            confidence_intervals=intervals,
            diagnostics={"max_horizon": max_horizon, "n_lags": n_lags},
            model_info={"library": "statsmodels", "estimator": "OLS"},
            n_obs=y.shape[0],
            n_periods=y.shape[0],
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


@foundry_method(
    namespace="econometrics.timeseries",
    version="1.0.0",
    tags={"econometrics", "garch"},
)
class GARCHEstimator:
    """Estimate conditional volatility dynamics under GARCH-style persistence; avoid nearly homoskedastic series or too few observations."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("arch", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="garch",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="p", default=1),
            ParameterSpec(name="q", default=1),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="GARCH volatility model for conditional heteroskedasticity.",
        tags=frozenset({"econometrics", "garch"}),
        citations=(
            "Bollerslev, T. (1986). Generalized autoregressive conditional heteroskedasticity.",
        ),
        when_to_use="Volatility clustering in financial/macro time series; conditional heteroskedasticity",
        typical_min_obs=200,
        output_interpretation="Conditional variance forecast. alpha+beta close to 1 = high persistence. ARCH LM test for fit.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: TimeSeriesData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        from arch import arch_model

        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        y = np.asarray(data.endog, dtype=float)
        if y.ndim != 1:
            raise ValueError("garch requires 1D endog")
        fit = arch_model(
            y,
            vol="GARCH",
            p=int(params.get("p", 1)),
            q=int(params.get("q", 1)),
            rescale=False,
        ).fit(disp="off")
        param_names = list(fit.params.index)
        result = _build_regression_result(
            method_name="garch",
            params={param_names[idx]: fit.params.iloc[idx] for idx in range(len(param_names))},
            std_errors={param_names[idx]: fit.std_err.iloc[idx] for idx in range(len(param_names))},
            p_values={param_names[idx]: fit.pvalues.iloc[idx] for idx in range(len(param_names))},
            diagnostics={
                "loglikelihood": _safe_float(getattr(fit, "loglikelihood", None)),
                "aic": _safe_float(getattr(fit, "aic", None)),
                "bic": _safe_float(getattr(fit, "bic", None)),
                "last_conditional_volatility": float(np.asarray(fit.conditional_volatility)[-1]),
            },
            model_info={"library": "arch", "estimator": "GARCH"},
            n_obs=y.shape[0],
            n_periods=y.shape[0],
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


@foundry_method(
    namespace="econometrics.panel",
    version="1.0.0",
    tags={"econometrics", "garch", "panel", "structural-break", "policy-risk"},
)
class NonstationaryGARCHEstimator:
    """Estimate observed-group GARCH regimes with finite structural breaks and coverage-aware diagnostics."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("arch", "ruptures", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="nonstationary_garch",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "dependent", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",)
                ),
                SlotSpec(
                    "exog", SlotType.MATRIX, Unit("feature", "value"), shape=("n_obs", "n_features")
                ),
                SlotSpec("entity_ids", SlotType.VECTOR, Unit("entity", "id"), shape=("n_obs",)),
                SlotSpec("time_ids", SlotType.VECTOR, Unit("time", "index"), shape=("n_obs",)),
            }
        ),
        output_slots=_volatility_output_slots(),
        parameters=(
            ParameterSpec(name="p", default=1),
            ParameterSpec(name="q", default=1),
            ParameterSpec(name="max_breaks", default=1),
            ParameterSpec(name="min_segment_length", default=24),
            ParameterSpec(name="break_detection_method", default="binseg_log_variance"),
            ParameterSpec(name="break_penalty", default=4.0),
            ParameterSpec(name="loss_family", default="gaussian_qml"),
            ParameterSpec(name="huber_kappa", default=1.5),
            ParameterSpec(name="distribution", default="normal"),
            ParameterSpec(name="mean_model", default="Zero"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="nominal_coverage", default=0.9),
            ParameterSpec(name="diagnostic_levels", default=(0.5, 0.8, 0.9, 0.95)),
            ParameterSpec(name="holdout_periods", default=8),
            ParameterSpec(name="run_policy_benchmark", default=True),
            ParameterSpec(name="variance_feature_names", default=None),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Observed-group structural-break GARCH with policy-risk coverage diagnostics.",
        tags=frozenset({"econometrics", "garch", "panel", "structural-break", "policy-risk"}),
        citations=(
            "Bollerslev, T. (1986). Generalized autoregressive conditional heteroskedasticity.",
            "Lamoureux, C. & Lastrapes, W. (1990). Persistence in variance, structural change, and the GARCH model.",
            "Bai, J. & Perron, P. (2003). Computation and analysis of multiple structural change models.",
        ),
        when_to_use="Policy-risk panels with observed group labels, volatility clustering, and suspected regime shifts.",
        typical_min_obs=120,
        output_interpretation="Group- and regime-specific persistence plus coverage diagnostics. High persistence should be interpreted alongside detected breaks.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        payload = _panel_payload(fallback_state)
        payload.update(bound_inputs)
        return PanelData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: PanelData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        y_matrix, x_tensor, entities, times = _balanced_panel_arrays(data)
        group_map, grouping_strategy = _resolve_entity_group_map(data, entities)

        p = max(1, int(params.get("p", 1)))
        q = max(1, int(params.get("q", 1)))
        max_breaks = max(0, int(params.get("max_breaks", 1)))
        min_segment_length = max(int(params.get("min_segment_length", 24)), max(p, q) + 5)
        confidence_level = float(params.get("confidence_level", 0.95))
        nominal_coverage = float(params.get("nominal_coverage", 0.9))
        holdout_periods = max(0, int(params.get("holdout_periods", 8)))
        run_policy_benchmark = bool(params.get("run_policy_benchmark", True))
        if not 0.0 < nominal_coverage < 1.0:
            raise ValueError("nominal_coverage must stay inside (0, 1)")
        diagnostic_levels = _resolve_interval_levels(params.get("diagnostic_levels"))
        all_levels = tuple(sorted(set(diagnostic_levels + (nominal_coverage,))))
        z_value = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
        mean_model = str(params.get("mean_model", "Zero"))
        distribution = str(params.get("distribution", "normal"))

        break_method_aliases = {
            "none": VolatilityBreakDetectionMethod.NONE.value,
            "binseg": VolatilityBreakDetectionMethod.BINSEG_LOG_VARIANCE.value,
            "pelt": VolatilityBreakDetectionMethod.PELT_LOG_VARIANCE.value,
        }
        break_method_value = (
            str(
                params.get(
                    "break_detection_method",
                    VolatilityBreakDetectionMethod.BINSEG_LOG_VARIANCE.value,
                )
            )
            .strip()
            .lower()
        )
        break_method = VolatilityBreakDetectionMethod(
            break_method_aliases.get(break_method_value, break_method_value)
        )
        loss_aliases = {
            "gaussian": VolatilityLossFamily.GAUSSIAN_QML.value,
            "gaussian_qml": VolatilityLossFamily.GAUSSIAN_QML.value,
            "huber": VolatilityLossFamily.HUBER_PROXY.value,
            "huber_proxy": VolatilityLossFamily.HUBER_PROXY.value,
        }
        loss_value = (
            str(params.get("loss_family", VolatilityLossFamily.GAUSSIAN_QML.value)).strip().lower()
        )
        loss_family = VolatilityLossFamily(loss_aliases.get(loss_value, loss_value))
        huber_kappa = float(params.get("huber_kappa", 1.5))
        break_penalty = float(params.get("break_penalty", 4.0))

        feature_names = list(data.feature_names or [f"x{i}" for i in range(data.n_features)])
        variance_feature_spec = params.get("variance_feature_names", None)
        if variance_feature_spec is None:
            variance_feature_indices = tuple(range(data.n_features))
        elif isinstance(variance_feature_spec, str):
            requested = [item.strip() for item in variance_feature_spec.split(",") if item.strip()]
            variance_feature_indices = tuple(feature_names.index(item) for item in requested)
        else:
            requested_list = list(variance_feature_spec)
            if not requested_list:
                variance_feature_indices = ()
            elif all(isinstance(item, str) for item in requested_list):
                variance_feature_indices = tuple(
                    feature_names.index(str(item)) for item in requested_list
                )
            else:
                variance_feature_indices = tuple(int(item) for item in requested_list)
        variance_feature_names = tuple(feature_names[idx] for idx in variance_feature_indices)

        entity_list = entities.tolist()
        ordered_groups = sorted({group_map[entity] for entity in entity_list})
        flat_params: dict[str, float] = {}
        flat_std_errors: dict[str, float] = {}
        flat_t_stats: dict[str, float] = {}
        flat_p_values: dict[str, float] = {}
        flat_intervals: dict[str, tuple[float, float]] = {}
        segment_records: list[VolatilityRegimeSegment] = []
        break_records: list[VolatilityBreak] = []
        warnings: list[str] = []
        global_y: list[float] = []
        global_intervals: dict[float, list[tuple[float, float]]] = {
            level: [] for level in all_levels
        }
        next_sigmas: list[float] = []
        next_means: list[float] = []
        global_evaluation_modes: set[str] = set()

        for group_label in ordered_groups:
            group_entity_indices = [
                idx for idx, entity in enumerate(entity_list) if group_map[entity] == group_label
            ]
            group_returns = y_matrix[group_entity_indices, :]
            proxy = np.mean(np.square(group_returns), axis=0)
            screened_breaks = _detect_group_breaks(
                proxy,
                method=break_method,
                max_breaks=max_breaks,
                min_segment_length=min_segment_length,
                penalty=break_penalty,
            )
            breakpoints, selection_metadata = _select_group_breaks_by_bic(
                group_returns,
                screened_breaks,
                p=p,
                q=q,
                mean_model=mean_model,
                distribution=distribution,
                loss_family=loss_family,
                huber_kappa=huber_kappa,
                min_segment_length=min_segment_length,
            )
            for breakpoint_index in breakpoints:
                break_records.append(
                    VolatilityBreak(
                        group_label=str(group_label),
                        breakpoint_index=breakpoint_index,
                        breakpoint_time_id=_python_scalar(times[breakpoint_index]),
                        detection_score=_break_detection_score(
                            proxy, breakpoint_index, min_segment_length
                        ),
                        metadata={
                            "screening_proxy": "mean_squared_return",
                            "screened_breaks": list(screened_breaks),
                            "selected_break_count": selection_metadata["selected_break_count"],
                        },
                    )
                )

            boundaries = _segment_boundaries(times.shape[0], breakpoints)
            for segment_index, (start_idx, end_idx) in enumerate(
                zip(boundaries[:-1], boundaries[1:], strict=True)
            ):
                entity_param_rows: list[dict[str, float]] = []
                entity_std_error_rows: list[dict[str, float]] = []
                segment_conditional_vols: list[np.ndarray] = []
                segment_eval_y: list[float] = []
                segment_intervals: dict[float, list[tuple[float, float]]] = {
                    level: [] for level in all_levels
                }
                segment_next_sigmas: list[float] = []
                segment_next_means: list[float] = []
                loss_diagnostics: list[dict[str, float]] = []
                evaluation_modes: set[str] = set()

                for entity_idx in group_entity_indices:
                    series = np.asarray(y_matrix[entity_idx, start_idx:end_idx], dtype=float)
                    try:
                        payload = _fit_garch_segment_payload(
                            series,
                            p=p,
                            q=q,
                            mean_model=mean_model,
                            distribution=distribution,
                            loss_family=loss_family,
                            huber_kappa=huber_kappa,
                            all_levels=all_levels,
                            nominal_coverage=nominal_coverage,
                            holdout_periods=holdout_periods,
                            min_train_length=max(min_segment_length // 2, max(p, q) + 5),
                        )
                    except Exception as exc:
                        warnings.append(
                            f"{group_label}:segment_{segment_index}:entity_{entity_list[entity_idx]} fit failed ({exc})"
                        )
                        continue
                    if payload is None:
                        continue

                    entity_param_rows.append(payload["params"])
                    entity_std_error_rows.append(payload["std_errors"])
                    segment_conditional_vols.append(payload["conditional_vol"])
                    segment_next_sigmas.append(float(payload["next_sigma"]))
                    segment_next_means.append(float(payload["next_mean"]))
                    loss_diagnostics.append(payload["loss_diag"])
                    segment_eval_y.extend(payload["eval_series"].tolist())
                    for level in all_levels:
                        segment_intervals[level].extend(payload["intervals"][level])
                    evaluation_modes.add(str(payload["evaluation_mode"]))

                if not entity_param_rows:
                    warnings.append(
                        f"{group_label}:segment_{segment_index} had no successful GARCH fits"
                    )
                    continue

                union_params = sorted({name for row in entity_param_rows for name in row})
                aggregated_params = {
                    name: float(np.mean([row[name] for row in entity_param_rows if name in row]))
                    for name in union_params
                }
                aggregated_std_errors: dict[str, float] = {}
                for name in union_params:
                    values = [row[name] for row in entity_param_rows if name in row]
                    if len(values) > 1:
                        aggregated_std_errors[name] = float(
                            np.std(values, ddof=1) / np.sqrt(len(values))
                        )
                    else:
                        source = entity_std_error_rows[0].get(name, 0.0)
                        aggregated_std_errors[name] = float(max(source, 0.0))

                variance_covariate_proxy_effects: dict[str, float] = {}
                if variance_feature_indices:
                    x_block = x_tensor[group_entity_indices, start_idx:end_idx, :][
                        :, :, variance_feature_indices
                    ]
                    design = x_block.reshape(-1, len(variance_feature_indices))
                    response = np.log(
                        np.maximum(group_returns[:, start_idx:end_idx].reshape(-1) ** 2, 1e-8)
                    )
                    if design.shape[0] > design.shape[1]:
                        design_matrix = np.column_stack([np.ones(design.shape[0]), design])
                        coef, *_ = np.linalg.lstsq(design_matrix, response, rcond=None)
                        variance_covariate_proxy_effects = {
                            variance_feature_names[idx]: float(coef[idx + 1])
                            for idx in range(len(variance_feature_names))
                        }

                segment_summary = _summarize_interval_diagnostics(
                    y_values=segment_eval_y,
                    intervals_by_level=segment_intervals,
                    all_levels=all_levels,
                    nominal_coverage=nominal_coverage,
                )
                segment_y = segment_summary["y_true"]
                primary_lower = segment_summary["lower"]
                primary_upper = segment_summary["upper"]
                covered = segment_summary["covered"]
                conditional_pvalue = segment_summary["conditional_pvalue"]
                independence_pvalue = segment_summary["independence_pvalue"]
                segment_report = segment_summary["report"]
                mean_interval_width = segment_summary["mean_interval_width"]
                wis = segment_summary["wis"]
                persistence = _persistence_from_params(aggregated_params)

                for name, estimate in aggregated_params.items():
                    key = f"{_sanitize_group_label(group_label)}.seg{segment_index}.{name}"
                    std_error = float(max(aggregated_std_errors.get(name, 0.0), 0.0))
                    t_stat = 0.0 if std_error <= 1e-12 else float(estimate / std_error)
                    p_value = float(math.erfc(abs(t_stat) / math.sqrt(2.0)))
                    flat_params[key] = float(estimate)
                    flat_std_errors[key] = std_error
                    flat_t_stats[key] = t_stat
                    flat_p_values[key] = p_value
                    flat_intervals[key] = (
                        float(estimate - z_value * std_error),
                        float(estimate + z_value * std_error),
                    )

                segment_records.append(
                    VolatilityRegimeSegment(
                        group_label=str(group_label),
                        segment_index=segment_index,
                        start_index=start_idx,
                        end_index=end_idx - 1,
                        start_time_id=_python_scalar(times[start_idx]),
                        end_time_id=_python_scalar(times[end_idx - 1]),
                        n_entities=len(entity_param_rows),
                        n_obs=int(segment_y.size),
                        params=aggregated_params,
                        persistence=persistence,
                        mean_conditional_volatility=float(
                            np.mean([np.mean(path) for path in segment_conditional_vols])
                        ),
                        variance_covariate_proxy_effects=variance_covariate_proxy_effects,
                        diagnostics={
                            "empirical_coverage_primary": segment_summary["empirical_coverage"],
                            "ece": segment_report.metrics.ece,
                            "max_calibration_error": segment_report.metrics.mce,
                            "conditional_coverage_pvalue": conditional_pvalue,
                            "independence_pvalue": independence_pvalue,
                            "wis": wis,
                            "coverage_semantics": (
                                "blocked_holdout"
                                if "blocked_holdout" in evaluation_modes
                                else "in_sample_one_step_proxy"
                            ),
                            "winsorized_share_mean": float(
                                np.mean(
                                    [item.get("winsorized_share", 0.0) for item in loss_diagnostics]
                                )
                            ),
                            "break_selection": selection_metadata,
                        },
                    )
                )

                global_y.extend(segment_y.tolist())
                for level in all_levels:
                    global_intervals[level].extend(segment_intervals[level])
                next_sigmas.extend(segment_next_sigmas)
                next_means.extend(segment_next_means)
                global_evaluation_modes.update(evaluation_modes)

        if not segment_records or not flat_params:
            raise ValueError("nonstationary_garch could not fit any group-segment GARCH models")

        overall_summary = _summarize_interval_diagnostics(
            y_values=global_y,
            intervals_by_level=global_intervals,
            all_levels=all_levels,
            nominal_coverage=nominal_coverage,
        )
        overall_y = overall_summary["y_true"]
        overall_primary_lower = overall_summary["lower"]
        overall_primary_upper = overall_summary["upper"]
        overall_covered = overall_summary["covered"]
        overall_conditional_pvalue = overall_summary["conditional_pvalue"]
        overall_independence_pvalue = overall_summary["independence_pvalue"]
        overall_report = overall_summary["report"]
        overall_empirical_coverage = overall_summary["empirical_coverage"]
        overall_wis = overall_summary["wis"]
        mean_interval_width = overall_summary["mean_interval_width"]
        coverage_semantics = (
            "blocked_holdout"
            if "blocked_holdout" in global_evaluation_modes
            else "in_sample_one_step_proxy"
        )
        regime_flags = [
            coverage_semantics,
            "structural_breaks_detected" if break_records else "no_breaks_detected",
        ]
        if loss_family is VolatilityLossFamily.HUBER_PROXY:
            regime_flags.append("huber_proxy")

        benchmark_scenarios: dict[str, Any] = {
            "proposed_profile_break_garch": {
                "scenario": "proposed_profile_break_garch",
                "status": "ok",
                "n_groups": len(ordered_groups),
                "n_regimes": len(segment_records),
                "break_count": len(break_records),
                "sample_count": int(overall_y.size),
                "coverage_semantics": coverage_semantics,
                "empirical_coverage": overall_empirical_coverage,
                "coverage_gap": (
                    None
                    if overall_empirical_coverage is None
                    else float(overall_empirical_coverage - nominal_coverage)
                ),
                "ece": overall_report.metrics.ece,
                "max_calibration_error": overall_report.metrics.mce,
                "conditional_coverage_pvalue": overall_conditional_pvalue,
                "independence_pvalue": overall_independence_pvalue,
                "mean_interval_width": mean_interval_width,
                "wis": overall_wis,
            }
        }
        if run_policy_benchmark:
            pooled_map = dict.fromkeys(entity_list, "pooled")
            benchmark_scenarios["pooled_stationary_garch"] = _evaluate_panel_volatility_scenario(
                scenario_name="pooled_stationary_garch",
                y_matrix=y_matrix,
                entities=entities,
                group_map=pooled_map,
                p=p,
                q=q,
                max_breaks=0,
                min_segment_length=min_segment_length,
                break_method=VolatilityBreakDetectionMethod.NONE,
                break_penalty=break_penalty,
                mean_model=mean_model,
                distribution=distribution,
                loss_family=loss_family,
                huber_kappa=huber_kappa,
                nominal_coverage=nominal_coverage,
                all_levels=all_levels,
                holdout_periods=holdout_periods,
            )
            benchmark_scenarios["group_specific_stationary_garch"] = (
                _evaluate_panel_volatility_scenario(
                    scenario_name="group_specific_stationary_garch",
                    y_matrix=y_matrix,
                    entities=entities,
                    group_map=group_map,
                    p=p,
                    q=q,
                    max_breaks=0,
                    min_segment_length=min_segment_length,
                    break_method=VolatilityBreakDetectionMethod.NONE,
                    break_penalty=break_penalty,
                    mean_model=mean_model,
                    distribution=distribution,
                    loss_family=loss_family,
                    huber_kappa=huber_kappa,
                    nominal_coverage=nominal_coverage,
                    all_levels=all_levels,
                    holdout_periods=holdout_periods,
                )
            )
            benchmark_scenarios["pooled_break_garch"] = _evaluate_panel_volatility_scenario(
                scenario_name="pooled_break_garch",
                y_matrix=y_matrix,
                entities=entities,
                group_map=pooled_map,
                p=p,
                q=q,
                max_breaks=max_breaks,
                min_segment_length=min_segment_length,
                break_method=break_method,
                break_penalty=break_penalty,
                mean_model=mean_model,
                distribution=distribution,
                loss_family=loss_family,
                huber_kappa=huber_kappa,
                nominal_coverage=nominal_coverage,
                all_levels=all_levels,
                holdout_periods=holdout_periods,
            )

        coverage_summary = VolatilityCoverageSummary(
            primary_nominal_coverage=nominal_coverage,
            empirical_coverage=overall_empirical_coverage,
            ece=overall_report.metrics.ece,
            max_calibration_error=overall_report.metrics.mce,
            conditional_coverage_pvalue=overall_conditional_pvalue,
            independence_pvalue=overall_independence_pvalue,
            sample_count=int(overall_y.size),
            recommended_action=overall_report.recommended_action,
            diagnostic_levels=all_levels,
            metadata={
                "mean_interval_width": mean_interval_width,
                "wis": overall_wis,
                "coverage_scope": "group_segment_pooled",
                "coverage_semantics": coverage_semantics,
                "scenario_benchmarks": benchmark_scenarios,
            },
        )
        nonstationary_summary = NonstationaryVolatilitySummary(
            grouping_strategy=grouping_strategy,
            break_detection_method=break_method,
            loss_family=loss_family,
            distribution=distribution,
            n_groups=len(ordered_groups),
            n_regimes=len(segment_records),
            breaks=tuple(break_records),
            segments=tuple(segment_records),
            coverage=coverage_summary,
            warnings=tuple(warnings),
            metadata={
                "target_id": str(data.metadata.get("target_id", "policy_risk_panel")),
                "mean_model": mean_model,
                "variance_feature_names": variance_feature_names,
                "coverage_semantics": coverage_semantics,
                "screening_then_profile_selection": True,
                "benchmark_scenarios": benchmark_scenarios,
            },
        )
        point_forecast = float(np.mean(next_means)) if next_means else 0.0
        sigma_forecast = (
            float(np.median(next_sigmas)) if next_sigmas else float(np.std(overall_y, ddof=1))
        )
        sigma_forecast = max(sigma_forecast, 1e-8)
        uncertainty_bundle = _build_nonstationary_uncertainty_bundle(
            method_fqn="econometrics.panel.nonstationary_garch@1.0.0",
            target_id=str(data.metadata.get("target_id", "policy_risk_panel")),
            nominal_coverage=nominal_coverage,
            empirical_coverage=overall_empirical_coverage,
            conditional_pvalue=overall_conditional_pvalue,
            independence_pvalue=overall_independence_pvalue,
            mean_interval_width=mean_interval_width,
            wis=overall_wis,
            sample_count=int(overall_y.size),
            point_forecast=point_forecast,
            sigma_forecast=sigma_forecast,
            regime_flags=tuple(regime_flags),
            sample_size_assumption=(
                "blocked holdout over the tail of each regime when feasible"
                if coverage_semantics == "blocked_holdout"
                else "in-sample one-step conditional volatility proxy"
            ),
        )

        result = EconometricResult(
            method_name="nonstationary_garch",
            params=flat_params,
            std_errors=flat_std_errors,
            t_stats=flat_t_stats,
            p_values=flat_p_values,
            confidence_intervals=flat_intervals,
            confidence_level=confidence_level,
            n_obs=data.n_obs,
            n_entities=data.n_entities,
            n_periods=data.n_periods,
            diagnostics={
                "group_breakpoints": {
                    group: [
                        item.breakpoint_index for item in break_records if item.group_label == group
                    ]
                    for group in ordered_groups
                },
                "regime_count": len(segment_records),
                "mean_interval_width_primary": mean_interval_width,
                "wis_primary": overall_wis,
                "coverage_recommended_action": overall_report.recommended_action,
                "coverage_semantics": coverage_semantics,
                "policy_risk_benchmark": benchmark_scenarios,
            },
            model_info={
                "library": "arch+ruptures",
                "estimator": "ObservedGroupStructuralBreakGARCH",
                "distribution": distribution,
                "loss_family": loss_family.value,
            },
            metadata={"warnings": warnings},
            nonstationary_volatility=nonstationary_summary,
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
            "forecasting_uncertainty_bundle": uncertainty_bundle,
        }


@foundry_method(
    namespace="econometrics.timeseries",
    version="1.0.0",
    tags={"econometrics", "change-point"},
)
class ChangePointEstimator:
    """Detect structural breaks in a time series; avoid using it as a causal effect estimator without an intervention design."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("ruptures", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="change_point",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("endog", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_output_slots(),
        parameters=(
            ParameterSpec(name="model", default="l2"),
            ParameterSpec(name="penalty", default=3.0),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="envelope_param", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Structural break detection via rupture-based change point search.",
        tags=frozenset({"econometrics", "change-point"}),
        citations=(
            "Truong, C. et al. (2020). Selective review of offline change point detection methods.",
        ),
        when_to_use="Time series with suspected regime shifts or structural breaks; detect when mean/variance changes",
        typical_min_obs=50,
        output_interpretation="Breakpoint indices and segment means. Penalty controls number of breaks detected. Visual inspection recommended.",
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> TimeSeriesData:
        payload = _time_series_payload(fallback_state)
        payload.update(bound_inputs)
        return TimeSeriesData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: TimeSeriesData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        import ruptures as rpt

        data = state if isinstance(state, TimeSeriesData) else TimeSeriesData.model_validate(state)
        y = np.asarray(data.endog, dtype=float)
        if y.ndim != 1:
            raise ValueError("change_point requires 1D endog")
        algo = rpt.Pelt(model=str(params.get("model", "l2"))).fit(y)
        breakpoints = [int(bp) for bp in algo.predict(pen=float(params.get("penalty", 3.0)))[:-1]]
        means = []
        start = 0
        for bp in breakpoints + [y.shape[0]]:
            means.append(float(np.mean(y[start:bp])))
            start = bp
        result = _build_regression_result(
            method_name="change_point",
            params={f"break_{idx}": bp for idx, bp in enumerate(breakpoints)},
            diagnostics={"breakpoints": breakpoints, "segment_means": means},
            model_info={"library": "ruptures", "estimator": "Pelt"},
            n_obs=y.shape[0],
            n_periods=y.shape[0],
        )
        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=params.get("envelope_param")
            ),
        }


__all__ = [
    "ChangePointEstimator",
    "EventStudyEstimator",
    "GARCHEstimator",
    "LocalProjectionsEstimator",
    "NonstationaryGARCHEstimator",
    "QuantileRegressionEstimator",
]
