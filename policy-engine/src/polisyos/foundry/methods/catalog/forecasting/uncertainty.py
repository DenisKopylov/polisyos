"""Helpers for attaching honest multi-horizon uncertainty bundles to forecasting methods."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np

from polisyos.foundry.methods.base import SlotSpec, SlotType, Unit
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastingUncertaintyBundle,
    ForecastingUncertaintyBundleV2,
    ForecastIntervalSemantics,
    HorizonDiagnosticState,
    HorizonInterval,
    HorizonPolicyRule,
    HorizonPolicySpec,
    HorizonQuantileSet,
    ReconciliationCertificate,
    ReconciliationMethod,
    ReconciliationStatus,
)
from polisyos.ir.artifacts import ArtifactStore, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel

_FAN_LEVELS = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
_EPS = 1e-12


def forecasting_output_slots(
    *,
    output_contract: type[ForecastingUncertaintyBundle] = ForecastingUncertaintyBundle,
) -> frozenset[SlotSpec]:
    """Return the standard forecasting output surface for Phase 0."""

    return frozenset(
        {
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec.for_output_contract(
                "forecasting_uncertainty_bundle",
                SlotType.SCALAR,
                Unit("uncertainty", "json"),
                output_contract=output_contract,
            ),
        }
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def resolve_artifact_store(
    state: Mapping[str, Any] | None,
    params: Mapping[str, Any] | None,
) -> ArtifactStore | None:
    """Best-effort lookup for an optional artifact store passed through runtime inputs."""

    for container in (params, state):
        if not isinstance(container, Mapping):
            continue
        candidate = container.get("artifact_store")
        if candidate is not None:
            return candidate
    return None


def _serialize_numeric(value: Any) -> Any:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        return float(arr.item())
    payload = arr.tolist()
    if isinstance(payload, list):
        return tuple(_serialize_numeric(item) for item in payload)
    return payload


def _fallback_scale(history: np.ndarray) -> np.ndarray:
    arr = np.asarray(history, dtype=float)
    if arr.shape[0] < 2:
        return np.zeros(arr.shape[1:], dtype=float)
    diffs = np.diff(arr, axis=0)
    if diffs.shape[0] < 2:
        return np.abs(diffs[0])
    return np.std(diffs, axis=0, ddof=1)


def _mean_interval_width(lower: np.ndarray, upper: np.ndarray) -> float:
    width = np.asarray(upper, dtype=float) - np.asarray(lower, dtype=float)
    return float(np.mean(np.maximum(width, 0.0)))


def _infer_aggregation_groups(
    aggregation_matrix: np.ndarray | None,
    *,
    tolerance: float = 1e-9,
) -> tuple[tuple[int, tuple[int, ...]], ...]:
    """Infer parent -> immediate child row relationships from a summing matrix."""

    if aggregation_matrix is None:
        return ()
    matrix = np.asarray(aggregation_matrix, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("aggregation_matrix must be a matrix")
    groups: list[tuple[int, tuple[int, ...]]] = []
    for parent_idx, parent_row in enumerate(matrix):
        candidates: list[int] = []
        for child_idx, child_row in enumerate(matrix):
            if child_idx == parent_idx:
                continue
            if np.any(child_row < -tolerance):
                continue
            is_subset = np.all(parent_row - child_row >= -tolerance)
            is_strict = np.any(parent_row - child_row > tolerance)
            if is_subset and is_strict:
                candidates.append(child_idx)

        immediate_children: list[int] = []
        for child_idx in candidates:
            child_row = matrix[child_idx]
            dominated = False
            for other_idx in candidates:
                if other_idx == child_idx:
                    continue
                other_row = matrix[other_idx]
                child_within_other = np.all(other_row - child_row >= -tolerance)
                other_is_strict = np.any(other_row - child_row > tolerance)
                other_within_parent = np.all(parent_row - other_row >= -tolerance)
                if child_within_other and other_is_strict and other_within_parent:
                    dominated = True
                    break
            if not dominated:
                immediate_children.append(child_idx)

        if len(immediate_children) < 2:
            continue
        child_sum = np.sum(matrix[immediate_children], axis=0)
        if np.allclose(child_sum, parent_row, atol=tolerance, rtol=0.0):
            groups.append((parent_idx, tuple(immediate_children)))
    return tuple(groups)


def _max_point_aggregation_error_by_horizon(
    reconciled_forecasts: np.ndarray,
    *,
    aggregation_matrix: np.ndarray | None = None,
    bottom_forecasts: np.ndarray | None = None,
    aggregation_groups: tuple[tuple[int, tuple[int, ...]], ...] = (),
) -> dict[int, float]:
    reconciled = np.asarray(reconciled_forecasts, dtype=float)
    if reconciled.ndim != 2:
        raise ValueError("reconciled_forecasts must be a matrix")
    horizon_count = int(reconciled.shape[1])

    if aggregation_matrix is not None and bottom_forecasts is not None:
        expected = np.asarray(aggregation_matrix, dtype=float) @ np.asarray(
            bottom_forecasts, dtype=float
        )
        if expected.shape != reconciled.shape:
            raise ValueError("aggregation_matrix @ bottom_forecasts must match reconciled_forecasts")
        errors = np.max(np.abs(reconciled - expected), axis=0)
        return {h: float(errors[h - 1]) for h in range(1, horizon_count + 1)}

    groups = aggregation_groups
    if not groups:
        return dict.fromkeys(range(1, horizon_count + 1), 0.0)
    values: dict[int, float] = {}
    for h in range(1, horizon_count + 1):
        max_error = 0.0
        for parent, children in groups:
            implied_parent = np.sum(reconciled[list(children), h - 1])
            max_error = max(max_error, abs(float(reconciled[parent, h - 1] - implied_parent)))
        values[h] = max_error
    return values


def _max_constraint_error_by_horizon(
    forecasts: np.ndarray,
    constraint_matrix: np.ndarray | None,
) -> dict[int, float]:
    values = np.asarray(forecasts, dtype=float)
    if values.ndim != 2:
        raise ValueError("forecasts must be a matrix")
    horizon_count = int(values.shape[1])
    if constraint_matrix is None:
        return dict.fromkeys(range(1, horizon_count + 1), 0.0)
    constraints = np.asarray(constraint_matrix, dtype=float)
    if constraints.ndim != 2:
        raise ValueError("constraint_matrix must be a matrix")
    if constraints.shape[1] != values.shape[0]:
        raise ValueError("constraint_matrix columns must match forecast node count")
    residual = constraints @ values
    errors = np.max(np.abs(residual), axis=0) if residual.size else np.zeros(horizon_count)
    return {h: float(errors[h - 1]) for h in range(1, horizon_count + 1)}


def _max_calibration_constraint_error(
    actuals: np.ndarray,
    constraint_matrix: np.ndarray | None,
) -> float:
    values = np.asarray(actuals, dtype=float)
    if constraint_matrix is None or values.size == 0:
        return 0.0
    constraints = np.asarray(constraint_matrix, dtype=float)
    if values.ndim != 3:
        raise ValueError("calibration actuals must have shape (n_calibration, n_nodes, horizon)")
    if constraints.ndim != 2 or constraints.shape[1] != values.shape[1]:
        raise ValueError("constraint_matrix columns must match calibration node count")
    residual = np.einsum("ij,pjk->pik", constraints, values, optimize=True)
    return float(np.max(np.abs(residual))) if residual.size else 0.0


def _aggregation_gap_by_horizon(
    lower: np.ndarray | None,
    upper: np.ndarray | None,
    aggregation_groups: tuple[tuple[int, tuple[int, ...]], ...],
) -> dict[int, float]:
    if lower is None or upper is None or not aggregation_groups:
        return {}
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    if lo.shape != hi.shape or lo.ndim != 2:
        raise ValueError("lower and upper interval matrices must share shape (n_nodes, horizon)")
    values: dict[int, float] = {}
    for h in range(1, lo.shape[1] + 1):
        max_gap = 0.0
        for parent, children in aggregation_groups:
            child_lower = float(np.sum(lo[list(children), h - 1]))
            child_upper = float(np.sum(hi[list(children), h - 1]))
            parent_lower = float(lo[parent, h - 1])
            parent_upper = float(hi[parent, h - 1])
            gap = max(0.0, child_lower - parent_upper, parent_lower - child_upper)
            max_gap = max(max_gap, gap)
        values[h] = max_gap
    return values


def _coerce_interval_matrix(
    value: np.ndarray | None,
    expected_shape: tuple[int, int],
    *,
    label: str,
) -> np.ndarray | None:
    if value is None:
        return None
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != expected_shape:
        raise ValueError(f"{label} must have shape {expected_shape}")
    return matrix


def _width_by_horizon(lower: np.ndarray, upper: np.ndarray) -> dict[int, float | None]:
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    if lo.shape != hi.shape or lo.ndim != 2:
        raise ValueError("interval matrices must share shape (n_nodes, horizon)")
    return {h: _mean_interval_width(lo[:, h - 1], hi[:, h - 1]) for h in range(1, lo.shape[1] + 1)}


def _width_reduction_by_horizon(
    final_width: Mapping[int, float | None],
    *,
    base_lower: np.ndarray | None = None,
    base_upper: np.ndarray | None = None,
    base_width: Mapping[int, float | None] | None = None,
) -> tuple[dict[int, float | None], dict[int, float | None]]:
    if base_width is None:
        if base_lower is None or base_upper is None:
            return (
                dict.fromkeys(final_width, None),
                dict.fromkeys(final_width, None),
            )
        base_width = _width_by_horizon(base_lower, base_upper)
    reduction: dict[int, float | None] = {}
    normalized: dict[int, float | None] = {}
    for horizon, final_value in final_width.items():
        base_value = base_width.get(horizon)
        if base_value is None or final_value is None:
            reduction[horizon] = None
            normalized[horizon] = None
            continue
        delta = float(base_value) - float(final_value)
        reduction[horizon] = delta
        normalized[horizon] = None if base_value <= _EPS else delta / float(base_value)
    return reduction, dict(base_width)


def _diagnostic_state_by_horizon(
    rules: tuple[HorizonPolicyRule, ...],
) -> dict[int, str]:
    states: dict[int, str] = {}
    for rule in rules:
        for horizon in range(rule.horizon_start, rule.horizon_end + 1):
            states[horizon] = rule.diagnostic_state.value
    return states


def _persist_json_ref(
    store: ArtifactStore,
    payload: dict[str, Any],
    *,
    kind: str,
    schema_name: str,
    schema_version: str = "1.0",
) -> ArtifactRefModel:
    ref = put_json_artifact(
        store,
        payload,
        kind=kind,
        schema_name=schema_name,
        schema_version=schema_version,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref)


def _conformal_radius(abs_errors: np.ndarray, coverage: float) -> np.ndarray:
    arr = np.asarray(abs_errors, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    n_samples = arr.shape[0]
    if n_samples == 0:
        raise ValueError("conformal radius requires at least one calibration error")
    rank = int(math.ceil((n_samples + 1) * float(np.clip(coverage, 0.0, 1.0)))) - 1
    rank = max(0, min(rank, n_samples - 1))
    sorted_errors = np.sort(arr, axis=0)
    radius = sorted_errors[rank]
    if radius.shape == (1,):
        return radius.reshape(())
    return radius


def _miss_sequence(covered: np.ndarray) -> np.ndarray:
    arr = np.asarray(covered, dtype=bool)
    if arr.ndim == 1:
        return (~arr).astype(int)
    return (~np.all(arr, axis=tuple(range(1, arr.ndim)))).astype(int)


def _log_prob_bernoulli(count_ones: int, count_total: int, p: float) -> float:
    if count_total <= 0:
        return 0.0
    p = min(max(float(p), _EPS), 1.0 - _EPS)
    return count_ones * math.log(p) + (count_total - count_ones) * math.log(1.0 - p)


def _chi_square_tail_df1(statistic: float) -> float:
    return math.erfc(math.sqrt(max(statistic, 0.0) / 2.0))


def _chi_square_tail_df2(statistic: float) -> float:
    return math.exp(-max(statistic, 0.0) / 2.0)


def _christoffersen_pvalues(
    miss_sequence: np.ndarray, alpha: float
) -> tuple[float | None, float | None]:
    misses = np.asarray(miss_sequence, dtype=int).reshape(-1)
    if misses.size < 2:
        return None, None

    n1 = int(np.sum(misses))
    n = int(misses.size)
    p_hat = n1 / max(n, 1)
    lr_uc = -2.0 * (_log_prob_bernoulli(n1, n, alpha) - _log_prob_bernoulli(n1, n, p_hat))
    conditional_pvalue = _chi_square_tail_df1(lr_uc)

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
        return conditional_pvalue, None

    pi = (n01 + n11) / max(total, 1)
    pi01 = n01 / max(n00 + n01, 1)
    pi11 = n11 / max(n10 + n11, 1)
    null_loglik = (n00 + n10) * math.log(max(1.0 - pi, _EPS)) + (n01 + n11) * math.log(
        max(pi, _EPS)
    )
    alt_loglik = (
        n00 * math.log(max(1.0 - pi01, _EPS))
        + n01 * math.log(max(pi01, _EPS))
        + n10 * math.log(max(1.0 - pi11, _EPS))
        + n11 * math.log(max(pi11, _EPS))
    )
    lr_ind = -2.0 * (null_loglik - alt_loglik)
    independence_pvalue = _chi_square_tail_df1(lr_ind)
    return conditional_pvalue, independence_pvalue


def _weighted_interval_score(errors: np.ndarray, radius: np.ndarray, alpha: float) -> float:
    err = np.asarray(errors, dtype=float)
    rad = np.asarray(radius, dtype=float)
    lower = -rad
    upper = rad
    width = upper - lower
    score = np.asarray(width, dtype=float)
    score = score + (2.0 / max(alpha, _EPS)) * np.maximum(lower - err, 0.0)
    score = score + (2.0 / max(alpha, _EPS)) * np.maximum(err - upper, 0.0)
    return float(np.mean(score))


def _diagnostic_state(
    empirical_coverage: float | None,
    nominal_coverage: float,
    sample_count: int,
    conditional_pvalue: float | None,
    independence_pvalue: float | None,
) -> HorizonDiagnosticState:
    if sample_count < 5 or empirical_coverage is None:
        return HorizonDiagnosticState.RED
    gap = abs(empirical_coverage - nominal_coverage)
    if empirical_coverage < nominal_coverage - 0.10:
        return HorizonDiagnosticState.RED
    if conditional_pvalue is not None and conditional_pvalue < 0.05:
        return HorizonDiagnosticState.RED
    if independence_pvalue is not None and independence_pvalue < 0.05:
        return HorizonDiagnosticState.RED
    if gap > 0.08 or empirical_coverage < nominal_coverage - 0.05:
        return HorizonDiagnosticState.AMBER
    return HorizonDiagnosticState.GREEN


def _fan_chart_quantiles(
    point: np.ndarray, abs_errors: np.ndarray | None, nominal_radius: np.ndarray
) -> dict[str, Any]:
    quantiles: dict[str, Any] = {}
    for level in _FAN_LEVELS:
        if math.isclose(level, 0.50):
            quantiles[str(level)] = _serialize_numeric(point)
            continue
        central_coverage = max(0.0, min(1.0, abs(2.0 * level - 1.0)))
        if abs_errors is not None and abs_errors.size > 0:
            radius = _conformal_radius(abs_errors, central_coverage)
        else:
            coverage_scale = 0.0 if central_coverage <= 0.0 else central_coverage
            radius = np.asarray(nominal_radius, dtype=float) * coverage_scale
        payload = point - radius if level < 0.50 else point + radius
        quantiles[str(level)] = _serialize_numeric(payload)
    return quantiles


def build_residual_conformal_bundle(
    *,
    method_fqn: str,
    source_method: str | None = None,
    target_id: str,
    history: np.ndarray,
    point_forecast: np.ndarray,
    forecast_fn: Callable[[np.ndarray, int], np.ndarray],
    nominal_coverage: float = 0.90,
    min_train_size: int = 4,
    method_note: str | None = None,
    extra_regime_flags: tuple[str, ...] = (),
    extra_metadata: Mapping[str, Any] | None = None,
    artifact_store: ArtifactStore | None = None,
    posterior_predictive_samples: np.ndarray | None = None,
) -> ForecastingUncertaintyBundle:
    """Build a horizon-wise residual bundle from rolling-origin calibration errors."""

    observed = np.asarray(history, dtype=float)
    forecast = np.asarray(point_forecast, dtype=float)
    if forecast.ndim == 0:
        forecast = forecast.reshape(1)
    horizon_count = int(forecast.shape[0])
    alpha = 1.0 - nominal_coverage
    fallback_scale = _fallback_scale(observed)
    last_radius: np.ndarray | None = None

    intervals: list[HorizonInterval] = []
    fan_entries: list[HorizonQuantileSet] = []
    empirical_coverage: dict[int, float] = {}
    coverage_gap: dict[int, float] = {}
    mean_interval_width: dict[int, float | None] = {}
    conditional_pvalues: dict[int, float | None] = {}
    independence_pvalues: dict[int, float | None] = {}
    wis_by_horizon: dict[int, float | None] = {}
    sample_count_by_horizon: dict[int, int] = {}
    interval_hit_sequences: dict[int, list[int]] = {}
    states: list[HorizonDiagnosticState] = []
    generated_at = _utc_now()

    insufficient_windows = False
    for horizon in range(1, horizon_count + 1):
        errors: list[np.ndarray] = []
        for train_end in range(max(int(min_train_size), 2), observed.shape[0] - horizon + 1):
            train = observed[:train_end]
            predicted_path = np.asarray(forecast_fn(train, horizon), dtype=float)
            predicted = np.asarray(predicted_path[horizon - 1], dtype=float)
            actual = np.asarray(observed[train_end + horizon - 1], dtype=float)
            errors.append(actual - predicted)

        if errors:
            error_array = np.asarray(errors, dtype=float)
            abs_errors = np.abs(error_array)
            radius = np.asarray(_conformal_radius(abs_errors, nominal_coverage), dtype=float)
            last_radius = radius
            covered = abs_errors <= radius
            empirical = float(np.mean(covered))
            miss_sequence = _miss_sequence(covered)
            conditional_pvalue, independence_pvalue = _christoffersen_pvalues(miss_sequence, alpha)
            wis = _weighted_interval_score(error_array, radius, alpha)
            sample_count = int(error_array.shape[0])
        else:
            error_array = np.empty((0,) + tuple(forecast.shape[1:]), dtype=float)
            abs_errors = None
            insufficient_windows = True
            sample_count = 0
            scale_multiplier = math.sqrt(float(horizon))
            base_radius = (
                last_radius if last_radius is not None else np.asarray(fallback_scale, dtype=float)
            )
            radius = np.asarray(base_radius, dtype=float) * scale_multiplier
            empirical = None
            conditional_pvalue = None
            independence_pvalue = None
            wis = None

        point = np.asarray(forecast[horizon - 1], dtype=float)
        lower = point - radius
        upper = point + radius
        state = _diagnostic_state(
            empirical,
            nominal_coverage,
            sample_count,
            conditional_pvalue,
            independence_pvalue,
        )
        states.append(state)

        interval_constructor = (
            ForecastCalibrationMethod.CONFORMAL
            if sample_count > 0
            else ForecastCalibrationMethod.NONE
        )
        intervals.append(
            HorizonInterval(
                horizon=horizon,
                point=_serialize_numeric(point),
                lower=_serialize_numeric(lower),
                upper=_serialize_numeric(upper),
                coverage_target=nominal_coverage,
                constructor=interval_constructor,
                sample_count=sample_count if sample_count > 0 else None,
                diagnostics={
                    "diagnostic_state": state.value,
                    "rolling_windows": sample_count,
                },
            )
        )
        fan_entries.append(
            HorizonQuantileSet(
                horizon=horizon,
                quantiles=_fan_chart_quantiles(point, abs_errors, radius),
            )
        )
        if empirical is not None:
            empirical_coverage[horizon] = empirical
            coverage_gap[horizon] = empirical - nominal_coverage
            interval_hit_sequences[horizon] = np.asarray(covered, dtype=int).reshape(-1).tolist()
        conditional_pvalues[horizon] = conditional_pvalue
        independence_pvalues[horizon] = independence_pvalue
        mean_interval_width[horizon] = _mean_interval_width(lower, upper)
        wis_by_horizon[horizon] = wis
        sample_count_by_horizon[horizon] = sample_count

    interval_semantics = (
        ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL
        if sample_count_by_horizon and min(sample_count_by_horizon.values()) >= 5
        else ForecastIntervalSemantics.HEURISTIC_RANGE
    )
    regime_flags = [
        "marginal_coverage_only",
        "conditional_coverage_unavailable_in_full_generalitiy",
        *extra_regime_flags,
    ]
    if observed.ndim > 1:
        regime_flags.append("multivariate_marginal_intervals")
    if insufficient_windows:
        regime_flags.append("insufficient_horizon_calibration")

    pit_summary_ref: ArtifactRefModel | None = None
    if artifact_store is not None and interval_hit_sequences:
        pit_summary_ref = _persist_json_ref(
            artifact_store,
            {
                "method_fqn": method_fqn,
                "target_id": target_id,
                "generated_at": generated_at.isoformat(),
                "summary_type": "interval_hit_sequence",
                "nominal_coverage": nominal_coverage,
                "empirical_coverage_by_horizon": {
                    str(h): value for h, value in empirical_coverage.items()
                },
                "coverage_gap_by_horizon": {str(h): value for h, value in coverage_gap.items()},
                "conditional_coverage_pvalue_by_horizon": {
                    str(h): value for h, value in conditional_pvalues.items()
                },
                "independence_pvalue_by_horizon": {
                    str(h): value for h, value in independence_pvalues.items()
                },
                "hit_sequences_by_horizon": {
                    str(h): value for h, value in interval_hit_sequences.items()
                },
                "sample_count_by_horizon": {
                    str(h): value for h, value in sample_count_by_horizon.items()
                },
                "pit_available": False,
            },
            kind="ir.forecasting_pit_summary",
            schema_name="ir.forecasting_pit_summary",
        )

    posterior_predictive_ref: ArtifactRefModel | None = None
    if artifact_store is not None and posterior_predictive_samples is not None:
        samples = np.asarray(posterior_predictive_samples, dtype=float)
        posterior_predictive_ref = _persist_json_ref(
            artifact_store,
            {
                "method_fqn": method_fqn,
                "target_id": target_id,
                "generated_at": generated_at.isoformat(),
                "payload_kind": "predictive_sample_paths",
                "sample_paths": _serialize_numeric(samples),
                "sample_count": int(samples.shape[0]) if samples.ndim >= 1 else 1,
            },
            kind="ir.forecasting_posterior_predictive",
            schema_name="ir.forecasting_posterior_predictive",
        )
        regime_flags.append("source_predictive_paths_attached")

    rules: list[HorizonPolicyRule] = []
    for horizon, state in enumerate(states, start=1):
        long_horizon_note = "recalibration_required_for_long_horizon" if horizon >= 5 else None
        note = (
            method_note
            if horizon < 5 or not long_horizon_note
            else f"{method_note}; {long_horizon_note}"
        )
        if method_note is None:
            note = long_horizon_note
        gate_ok = interval_semantics == ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL
        if state is HorizonDiagnosticState.RED:
            gate_ok = False
        rules.append(
            HorizonPolicyRule(
                horizon_start=horizon,
                horizon_end=horizon,
                diagnostic_state=state,
                allowed_methods=(ForecastCalibrationMethod.CONFORMAL,) if gate_ok else (),
                gate_eligible=gate_ok,
                fallback=ForecastCalibrationMethod.BOOTSTRAP if not gate_ok else None,
                note=note,
            )
        )

    bundle_gate_eligible = (
        interval_semantics == ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL
    )
    if any(rule.diagnostic_state is HorizonDiagnosticState.RED for rule in rules):
        bundle_gate_eligible = False

    return ForecastingUncertaintyBundle(
        method_fqn=method_fqn,
        source_method=source_method or method_fqn,
        target_id=target_id,
        generated_at=generated_at,
        prediction_interval=tuple(intervals),
        fan_chart=FanChartSpec(
            quantile_levels=_FAN_LEVELS,
            horizons=tuple(fan_entries),
        ),
        posterior_predictive_ref=posterior_predictive_ref,
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=nominal_coverage,
            empirical_coverage_by_horizon=empirical_coverage,
            coverage_gap_by_horizon=coverage_gap,
            mean_interval_width_by_horizon=mean_interval_width,
            conditional_coverage_pvalue_by_horizon=conditional_pvalues,
            independence_pvalue_by_horizon=independence_pvalues,
            wis_by_horizon=wis_by_horizon,
            sample_count_by_horizon=sample_count_by_horizon,
            pit_summary_ref=pit_summary_ref,
            regime_flags=tuple(dict.fromkeys(regime_flags)),
            recommended_fallback=(
                ForecastCalibrationMethod.BOOTSTRAP if not bundle_gate_eligible else None
            ),
            calibration_window=int(observed.shape[0]),
            last_recalibrated_at=_utc_now(),
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.CONFORMAL,
            rules=tuple(rules),
            gate_eligible=bundle_gate_eligible,
            summary=(
                "Phase 0 default uses rolling-origin residual conformal calibration; "
                "only marginal coverage is targeted."
            ),
        ),
        interval_semantics=interval_semantics,
        calibration_method=ForecastCalibrationMethod.CONFORMAL,
        nominal_coverage=nominal_coverage,
        sample_size_assumption="rolling-origin calibration residuals by horizon",
        regime_assumption=(
            "Exact conditional coverage is not claimed; diagnostics are horizon-wise and marginal."
        ),
        metadata={
            "phase": "phase0",
            "method_note": method_note,
            "history_observations": int(observed.shape[0]),
            **dict(extra_metadata or {}),
        },
    )


def build_member_spread_bundle(
    *,
    method_fqn: str,
    target_id: str,
    member_forecasts: np.ndarray,
    ensemble_forecast: np.ndarray,
    nominal_coverage: float = 0.90,
    artifact_store: ArtifactStore | None = None,
) -> ForecastingUncertaintyBundle:
    """Build a heuristic bundle from ensemble-member forecast spread."""

    members = np.asarray(member_forecasts, dtype=float)
    point = np.asarray(ensemble_forecast, dtype=float)
    if members.ndim != 2:
        raise ValueError("member_forecasts must be a 2D matrix")
    lower = np.min(members, axis=0)
    upper = np.max(members, axis=0)
    fan_entries = []
    mean_interval_width = {}
    for horizon in range(1, point.shape[0] + 1):
        column = np.asarray(members[:, horizon - 1], dtype=float)
        quantiles = {str(level): float(np.quantile(column, level)) for level in _FAN_LEVELS}
        fan_entries.append(HorizonQuantileSet(horizon=horizon, quantiles=quantiles))
        mean_interval_width[horizon] = float(np.max(column) - np.min(column))

    generated_at = _utc_now()
    posterior_predictive_ref: ArtifactRefModel | None = None
    regime_flags = ["member_spread_heuristic"]
    if artifact_store is not None:
        posterior_predictive_ref = _persist_json_ref(
            artifact_store,
            {
                "method_fqn": method_fqn,
                "target_id": target_id,
                "generated_at": generated_at.isoformat(),
                "payload_kind": "ensemble_member_paths",
                "member_paths": _serialize_numeric(members),
            },
            kind="ir.forecasting_posterior_predictive",
            schema_name="ir.forecasting_posterior_predictive",
        )
        regime_flags.append("member_path_proxy")
        regime_flags.append("linear_pool_calibration_missing")
    else:
        regime_flags.append("predictive_density_missing")

    rules = tuple(
        HorizonPolicyRule(
            horizon_start=h,
            horizon_end=h,
            diagnostic_state=HorizonDiagnosticState.RED,
            allowed_methods=(),
            gate_eligible=False,
            fallback=ForecastCalibrationMethod.CONFORMAL,
            note="member spread is a heuristic until predictive densities or sample paths are available",
        )
        for h in range(1, point.shape[0] + 1)
    )

    return ForecastingUncertaintyBundle(
        method_fqn=method_fqn,
        source_method=method_fqn,
        target_id=target_id,
        generated_at=generated_at,
        prediction_interval=tuple(
            HorizonInterval(
                horizon=h,
                point=float(point[h - 1]),
                lower=float(lower[h - 1]),
                upper=float(upper[h - 1]),
                coverage_target=nominal_coverage,
                constructor=ForecastCalibrationMethod.NONE,
                diagnostics={"diagnostic_state": HorizonDiagnosticState.RED.value},
            )
            for h in range(1, point.shape[0] + 1)
        ),
        fan_chart=FanChartSpec(quantile_levels=_FAN_LEVELS, horizons=tuple(fan_entries)),
        posterior_predictive_ref=posterior_predictive_ref,
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=nominal_coverage,
            mean_interval_width_by_horizon=mean_interval_width,
            sample_count_by_horizon={
                h: int(members.shape[0]) for h in range(1, point.shape[0] + 1)
            },
            regime_flags=tuple(dict.fromkeys(regime_flags)),
            recommended_fallback=ForecastCalibrationMethod.CONFORMAL,
            calibration_window=int(members.shape[0]),
            last_recalibrated_at=generated_at,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.NONE,
            rules=rules,
            gate_eligible=False,
            summary="Ensemble member spread is exposed as a heuristic range only.",
        ),
        interval_semantics=ForecastIntervalSemantics.HEURISTIC_RANGE,
        calibration_method=ForecastCalibrationMethod.NONE,
        nominal_coverage=nominal_coverage,
        sample_size_assumption="ensemble member spread only; no empirical coverage guarantee",
        regime_assumption="Requires predictive densities or member backtests for statistical intervals.",
        metadata={"phase": "phase0", "n_members": int(members.shape[0])},
    )


def build_reconciled_conformal_bundle(
    *,
    method_fqn: str,
    target_id: str,
    reconciled_forecasts: np.ndarray,
    calibration_reconciled_forecasts: np.ndarray,
    calibration_actuals: np.ndarray,
    nominal_coverage: float = 0.90,
    coherent_sample_paths: np.ndarray | None = None,
    aggregation_matrix: np.ndarray | None = None,
    bottom_forecasts: np.ndarray | None = None,
    constraint_matrix: np.ndarray | None = None,
    unreconciled_interval_lower: np.ndarray | None = None,
    unreconciled_interval_upper: np.ndarray | None = None,
    calibration_unreconciled_forecasts: np.ndarray | None = None,
    constraints_kind: Literal["hierarchical", "grouped", "general_linear"] = "hierarchical",
    reconciliation_method: ReconciliationMethod = ReconciliationMethod.BOTTOM_UP,
    min_calibration_count: int = 5,
    artifact_store: ArtifactStore | None = None,
    beta_mixing_penalty: float | None = None,
) -> ForecastingUncertaintyBundleV2:
    """Calibrate intervals on residuals from an already-reconciled predictor."""

    reconciled = np.asarray(reconciled_forecasts, dtype=float)
    calibration_forecasts = np.asarray(calibration_reconciled_forecasts, dtype=float)
    actuals = np.asarray(calibration_actuals, dtype=float)
    if reconciled.ndim != 2:
        raise ValueError("reconciled_forecasts must be a matrix")
    if calibration_forecasts.ndim != 3 or actuals.ndim != 3:
        raise ValueError(
            "calibration_reconciled_forecasts and calibration_actuals must have "
            "shape (n_calibration, n_nodes, horizon)"
        )
    if calibration_forecasts.shape != actuals.shape:
        raise ValueError("calibration forecasts and actuals must share the same shape")
    if calibration_forecasts.shape[1:] != reconciled.shape:
        raise ValueError("calibration forecast node/horizon shape must match final forecast")

    generated_at = _utc_now()
    alpha = 1.0 - nominal_coverage
    n_calibration = int(calibration_forecasts.shape[0])
    horizon_count = int(reconciled.shape[1])
    interval_shape = (int(reconciled.shape[0]), horizon_count)
    base_lower = _coerce_interval_matrix(
        unreconciled_interval_lower,
        interval_shape,
        label="unreconciled_interval_lower",
    )
    base_upper = _coerce_interval_matrix(
        unreconciled_interval_upper,
        interval_shape,
        label="unreconciled_interval_upper",
    )
    if (base_lower is None) != (base_upper is None):
        raise ValueError("unreconciled interval lower and upper must be supplied together")
    calibration_unreconciled = None
    if calibration_unreconciled_forecasts is not None:
        calibration_unreconciled = np.asarray(calibration_unreconciled_forecasts, dtype=float)
        if calibration_unreconciled.shape != actuals.shape:
            raise ValueError("calibration_unreconciled_forecasts must match calibration_actuals")
    paths_for_fan: np.ndarray | None = None
    if coherent_sample_paths is not None:
        paths_for_fan = np.asarray(coherent_sample_paths, dtype=float)
        if paths_for_fan.ndim != 3:
            raise ValueError("coherent_sample_paths must have shape (n_paths, n_nodes, horizon)")
        if paths_for_fan.shape[1:] != reconciled.shape:
            raise ValueError("coherent_sample_paths must align with reconciled_forecasts")
    aggregation_groups = _infer_aggregation_groups(aggregation_matrix)
    point_aggregation_error = _max_point_aggregation_error_by_horizon(
        reconciled,
        aggregation_matrix=aggregation_matrix,
        bottom_forecasts=bottom_forecasts,
        aggregation_groups=aggregation_groups,
    )
    point_constraint_error = _max_constraint_error_by_horizon(reconciled, constraint_matrix)
    max_point_error = max(
        max(point_aggregation_error.values(), default=0.0),
        max(point_constraint_error.values(), default=0.0),
    )

    target_aggregation_error = 0.0
    if aggregation_groups:
        for parent, children in aggregation_groups:
            implied_parent = np.sum(actuals[:, list(children), :], axis=1)
            target_aggregation_error = max(
                target_aggregation_error,
                float(np.max(np.abs(actuals[:, parent, :] - implied_parent))),
            )
    target_constraint_error = _max_calibration_constraint_error(actuals, constraint_matrix)

    residuals = actuals - calibration_forecasts
    abs_errors = np.abs(residuals)
    unreconciled_width_by_horizon: dict[int, float | None] | None = None
    if calibration_unreconciled is not None:
        unreconciled_width_by_horizon = {}
        base_abs_errors = np.abs(actuals - calibration_unreconciled)
        for horizon in range(1, horizon_count + 1):
            base_radius = np.asarray(
                _conformal_radius(base_abs_errors[:, :, horizon - 1], nominal_coverage),
                dtype=float,
            )
            unreconciled_width_by_horizon[horizon] = float(np.mean(2.0 * base_radius))
    lower_matrix = np.empty_like(reconciled, dtype=float)
    upper_matrix = np.empty_like(reconciled, dtype=float)
    intervals: list[HorizonInterval] = []
    fan_entries: list[HorizonQuantileSet] = []
    empirical_coverage: dict[int, float] = {}
    coverage_gap: dict[int, float] = {}
    mean_interval_width: dict[int, float | None] = {}
    wis_by_horizon: dict[int, float | None] = {}
    sample_count_by_horizon: dict[int, int] = {}
    conditional_pvalues: dict[int, float | None] = {}
    independence_pvalues: dict[int, float | None] = {}
    node_diagnostics: dict[str, Any] = {}
    states: list[HorizonDiagnosticState] = []

    for horizon in range(1, horizon_count + 1):
        horizon_abs_errors = abs_errors[:, :, horizon - 1]
        radius = np.asarray(_conformal_radius(horizon_abs_errors, nominal_coverage), dtype=float)
        point = np.asarray(reconciled[:, horizon - 1], dtype=float)
        lower = point - radius
        upper = point + radius
        lower_matrix[:, horizon - 1] = lower
        upper_matrix[:, horizon - 1] = upper

        covered = horizon_abs_errors <= radius[None, :]
        empirical = float(np.mean(covered))
        wis = _weighted_interval_score(residuals[:, :, horizon - 1], radius, alpha)
        state = _diagnostic_state(
            empirical,
            nominal_coverage,
            n_calibration,
            None,
            None,
        )
        states.append(state)

        node_diagnostics[str(horizon)] = {
            "empirical_coverage_by_node": np.mean(covered, axis=0).tolist(),
            "conformal_radius_by_node": radius.tolist(),
            "sample_count": n_calibration,
            "diagnostic_state": state.value,
        }
        intervals.append(
            HorizonInterval(
                horizon=horizon,
                point=_serialize_numeric(point),
                lower=_serialize_numeric(lower),
                upper=_serialize_numeric(upper),
                coverage_target=nominal_coverage,
                constructor=ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION,
                sample_count=n_calibration,
                diagnostics={
                    "diagnostic_state": state.value,
                    "rolling_windows": n_calibration,
                    "calibrated_after_reconciliation": True,
                },
            )
        )
        fan_quantiles = (
            {
                str(level): _serialize_numeric(
                    np.quantile(paths_for_fan[:, :, horizon - 1], level, axis=0)
                )
                for level in _FAN_LEVELS
            }
            if paths_for_fan is not None
            else _fan_chart_quantiles(point, horizon_abs_errors, radius)
        )
        fan_entries.append(
            HorizonQuantileSet(
                horizon=horizon,
                quantiles=fan_quantiles,
            )
        )
        empirical_coverage[horizon] = empirical
        coverage_gap[horizon] = empirical - nominal_coverage
        mean_interval_width[horizon] = _mean_interval_width(lower, upper)
        wis_by_horizon[horizon] = wis
        sample_count_by_horizon[horizon] = n_calibration
        conditional_pvalues[horizon] = None
        independence_pvalues[horizon] = None

    aggregation_gap = _aggregation_gap_by_horizon(
        lower_matrix,
        upper_matrix,
        aggregation_groups,
    )
    preconditions = {
        "rolling_origin_residual_bank": True,
        "minimum_calibration_count": n_calibration >= min_calibration_count,
        "calibration_window_count": n_calibration,
        "min_calibration_count": int(min_calibration_count),
        "coherent_targets": max(target_aggregation_error, target_constraint_error) <= 1e-8,
        "max_target_aggregation_error": target_aggregation_error,
        "max_target_constraint_error": target_constraint_error,
        "coherent_points": max_point_error <= 1e-8,
        "max_point_aggregation_error": max(point_aggregation_error.values(), default=0.0),
        "max_point_constraint_error": max(point_constraint_error.values(), default=0.0),
        "reconciliation_map_fixed_before_test_time": True,
        "calibrated_after_reconciliation": True,
        "beta_mixing_penalty": beta_mixing_penalty,
    }
    preconditions_passed = all(
        bool(preconditions[key])
        for key in (
            "rolling_origin_residual_bank",
            "minimum_calibration_count",
            "coherent_targets",
            "coherent_points",
            "reconciliation_map_fixed_before_test_time",
            "calibrated_after_reconciliation",
        )
    )

    posterior_predictive_ref: ArtifactRefModel | None = None
    if paths_for_fan is not None:
        if artifact_store is not None:
            posterior_predictive_ref = _persist_json_ref(
                artifact_store,
                {
                    "method_fqn": method_fqn,
                    "target_id": target_id,
                    "generated_at": generated_at.isoformat(),
                    "payload_kind": "coherent_sample_paths",
                    "sample_paths": _serialize_numeric(paths_for_fan),
                    "sample_count": int(paths_for_fan.shape[0]),
                },
                kind="ir.forecasting_posterior_predictive",
                schema_name="ir.forecasting_posterior_predictive",
            )

    node_level_diagnostics_ref: ArtifactRefModel | None = None
    if artifact_store is not None:
        node_level_diagnostics_ref = _persist_json_ref(
            artifact_store,
            {
                "method_fqn": method_fqn,
                "target_id": target_id,
                "generated_at": generated_at.isoformat(),
                "diagnostic_kind": "reconciled_conformal_node_horizon",
                "node_diagnostics_by_horizon": node_diagnostics,
            },
            kind="ir.forecasting_reconciliation_diagnostics",
            schema_name="ir.forecasting_reconciliation_diagnostics",
        )

    rules: list[HorizonPolicyRule] = []
    for horizon, state in enumerate(states, start=1):
        gate_ok = preconditions_passed and state is not HorizonDiagnosticState.RED
        rules.append(
            HorizonPolicyRule(
                horizon_start=horizon,
                horizon_end=horizon,
                diagnostic_state=state,
                allowed_methods=(
                    (ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION,)
                    if gate_ok
                    else ()
                ),
                gate_eligible=gate_ok,
                fallback=ForecastCalibrationMethod.COHERENT_BOOTSTRAP if not gate_ok else None,
                note="intervals are conformal-calibrated on reconciled residuals",
            )
        )
    bundle_gate_eligible = preconditions_passed and all(
        rule.diagnostic_state is not HorizonDiagnosticState.RED for rule in rules
    )

    regime_flags = [
        "marginal_coverage_only",
        "reconciled_predictor_conformal_calibration",
    ]
    if beta_mixing_penalty is not None:
        regime_flags.append("beta_mixing_penalty_declared")
    if aggregation_gap:
        regime_flags.append("aggregation_gap_reported")
    if not preconditions_passed:
        regime_flags.append("coverage_certificate_preconditions_failed")

    diagnostic_state_by_horizon = _diagnostic_state_by_horizon(tuple(rules))
    width_reduction, unreconciled_width = _width_reduction_by_horizon(
        mean_interval_width,
        base_lower=base_lower,
        base_upper=base_upper,
        base_width=unreconciled_width_by_horizon,
    )
    diagnostics = {
        "max_point_aggregation_error_by_horizon": point_aggregation_error,
        "max_point_constraint_error_by_horizon": point_constraint_error,
        "aggregation_gap_by_horizon": aggregation_gap,
        "empirical_coverage_by_horizon": empirical_coverage,
        "mean_interval_width_by_horizon": mean_interval_width,
        "unreconciled_mean_interval_width_by_horizon": unreconciled_width,
        "width_reduction_vs_unreconciled_by_horizon": width_reduction,
        "width_reduction_ratio_vs_unreconciled_by_horizon": {
            horizon: (
                None
                if unreconciled_width[horizon] is None
                or width_reduction[horizon] is None
                or float(unreconciled_width[horizon] or 0.0) <= _EPS
                else float(width_reduction[horizon]) / float(unreconciled_width[horizon])
            )
            for horizon in mean_interval_width
        },
        "sample_count_by_horizon": sample_count_by_horizon,
        "diagnostic_state_by_horizon": diagnostic_state_by_horizon,
        "aggregation_group_count": len(aggregation_groups),
        "node_count": int(reconciled.shape[0]),
        "fan_chart_source": "coherent_sample_paths" if paths_for_fan is not None else "conformal_residuals",
    }
    status = (
        ReconciliationStatus.CERTIFIED
        if preconditions_passed
        else ReconciliationStatus.FALLBACK
    )
    certificate = ReconciliationCertificate(
        status=status,
        method=reconciliation_method,
        constraints_kind=constraints_kind,
        coherent_points=max_point_error <= 1e-8,
        coherent_paths=paths_for_fan is not None,
        coverage_scope=(
            "per_series_marginal_with_beta_mixing_penalty"
            if preconditions_passed and beta_mixing_penalty is not None
            else "per_series_marginal"
            if preconditions_passed
            else "uncertified"
        ),
        preconditions_passed=preconditions_passed,
        preconditions=preconditions,
        diagnostics=diagnostics,
        coherent_sample_paths_ref=posterior_predictive_ref,
        node_level_diagnostics_ref=node_level_diagnostics_ref,
        fallback_reason=None if preconditions_passed else "reconciled calibration preconditions failed",
    )

    return ForecastingUncertaintyBundleV2(
        method_fqn=method_fqn,
        source_method=method_fqn,
        target_id=target_id,
        generated_at=generated_at,
        prediction_interval=tuple(intervals),
        fan_chart=FanChartSpec(
            quantile_levels=_FAN_LEVELS,
            horizons=tuple(fan_entries),
        ),
        posterior_predictive_ref=posterior_predictive_ref,
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=nominal_coverage,
            empirical_coverage_by_horizon=empirical_coverage,
            coverage_gap_by_horizon=coverage_gap,
            mean_interval_width_by_horizon=mean_interval_width,
            conditional_coverage_pvalue_by_horizon=conditional_pvalues,
            independence_pvalue_by_horizon=independence_pvalues,
            wis_by_horizon=wis_by_horizon,
            sample_count_by_horizon=sample_count_by_horizon,
            regime_flags=tuple(dict.fromkeys(regime_flags)),
            recommended_fallback=(
                ForecastCalibrationMethod.COHERENT_BOOTSTRAP
                if not bundle_gate_eligible
                else None
            ),
            calibration_window=n_calibration,
            last_recalibrated_at=generated_at,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=(
                ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION
                if preconditions_passed
                else ForecastCalibrationMethod.NONE
            ),
            rules=tuple(rules),
            gate_eligible=bundle_gate_eligible,
            summary=(
                "Intervals are calibrated after bottom-up reconciliation; coverage is "
                "per-series and per-horizon marginal."
                if preconditions_passed
                else "Reconciliation was attempted, but certified coverage preconditions failed."
            ),
        ),
        interval_semantics=(
            ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL
            if preconditions_passed
            else ForecastIntervalSemantics.HEURISTIC_RANGE
        ),
        calibration_method=(
            ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION
            if preconditions_passed
            else ForecastCalibrationMethod.NONE
        ),
        nominal_coverage=nominal_coverage,
        sample_size_assumption="rolling-origin residuals from reconciled forecasts",
        regime_assumption=(
            "Per-series, per-horizon marginal coverage is claimed under split-conformal "
            "exchangeability or the declared time-series dependence penalty."
            if preconditions_passed
            else "Certified reconciliation coverage is unavailable for this residual bank."
        ),
        metadata={
            "phase": "phase4",
            "n_nodes": int(reconciled.shape[0]),
            "calibration_windows": n_calibration,
            "reconciliation": "reconcile_then_calibrate",
        },
        reconciliation_certificate=certificate,
    )


def build_reconciliation_placeholder_bundle(
    *,
    method_fqn: str,
    target_id: str,
    reconciled_forecasts: np.ndarray,
    nominal_coverage: float = 0.90,
    coherent_sample_paths: np.ndarray | None = None,
    aggregation_matrix: np.ndarray | None = None,
    bottom_forecasts: np.ndarray | None = None,
    constraint_matrix: np.ndarray | None = None,
    unreconciled_interval_lower: np.ndarray | None = None,
    unreconciled_interval_upper: np.ndarray | None = None,
    constraints_kind: Literal["hierarchical", "grouped", "general_linear"] = "hierarchical",
    reconciliation_method: ReconciliationMethod = ReconciliationMethod.BOTTOM_UP,
    artifact_store: ArtifactStore | None = None,
) -> ForecastingUncertaintyBundleV2:
    """Expose reconciliation outputs without overstating probabilistic validity."""

    reconciled = np.asarray(reconciled_forecasts, dtype=float)
    if reconciled.ndim != 2:
        raise ValueError("reconciled_forecasts must be a matrix")
    horizon_count = int(reconciled.shape[1])
    horizon_vectors = [reconciled[:, horizon - 1] for horizon in range(1, horizon_count + 1)]
    generated_at = _utc_now()
    predictive_ref: ArtifactRefModel | None = None
    interval_shape = (int(reconciled.shape[0]), horizon_count)
    base_lower = _coerce_interval_matrix(
        unreconciled_interval_lower,
        interval_shape,
        label="unreconciled_interval_lower",
    )
    base_upper = _coerce_interval_matrix(
        unreconciled_interval_upper,
        interval_shape,
        label="unreconciled_interval_upper",
    )
    if (base_lower is None) != (base_upper is None):
        raise ValueError("unreconciled interval lower and upper must be supplied together")
    aggregation_groups = _infer_aggregation_groups(aggregation_matrix)
    point_aggregation_error = _max_point_aggregation_error_by_horizon(
        reconciled,
        aggregation_matrix=aggregation_matrix,
        bottom_forecasts=bottom_forecasts,
        aggregation_groups=aggregation_groups,
    )
    point_constraint_error = _max_constraint_error_by_horizon(reconciled, constraint_matrix)
    max_point_error = max(
        max(point_aggregation_error.values(), default=0.0),
        max(point_constraint_error.values(), default=0.0),
    )

    if coherent_sample_paths is not None:
        paths = np.asarray(coherent_sample_paths, dtype=float)
        if paths.ndim != 3:
            raise ValueError("coherent_sample_paths must have shape (n_paths, n_nodes, horizon)")
        if paths.shape[1] != reconciled.shape[0] or paths.shape[2] != horizon_count:
            raise ValueError("coherent_sample_paths must align with reconciled_forecasts")
        if artifact_store is not None:
            predictive_ref = _persist_json_ref(
                artifact_store,
                {
                    "method_fqn": method_fqn,
                    "target_id": target_id,
                    "generated_at": generated_at.isoformat(),
                    "payload_kind": "coherent_sample_paths",
                    "sample_paths": _serialize_numeric(paths),
                    "sample_count": int(paths.shape[0]),
                },
                kind="ir.forecasting_posterior_predictive",
                schema_name="ir.forecasting_posterior_predictive",
            )
        intervals = []
        fan_entries = []
        mean_interval_width = {}
        sample_count_by_horizon = {}
        lower_matrix = np.empty_like(reconciled, dtype=float)
        upper_matrix = np.empty_like(reconciled, dtype=float)
        for h in range(1, horizon_count + 1):
            path_slice = np.asarray(paths[:, :, h - 1], dtype=float)
            lower = np.quantile(path_slice, (1.0 - nominal_coverage) / 2.0, axis=0)
            upper = np.quantile(path_slice, 1.0 - (1.0 - nominal_coverage) / 2.0, axis=0)
            point = np.asarray(reconciled[:, h - 1], dtype=float)
            lower = np.minimum(lower, point)
            upper = np.maximum(upper, point)
            lower_matrix[:, h - 1] = lower
            upper_matrix[:, h - 1] = upper
            intervals.append(
                HorizonInterval(
                    horizon=h,
                    point=_serialize_numeric(point),
                    lower=_serialize_numeric(lower),
                    upper=_serialize_numeric(upper),
                    coverage_target=nominal_coverage,
                    constructor=ForecastCalibrationMethod.COHERENT_BOOTSTRAP,
                    sample_count=int(paths.shape[0]),
                    diagnostics={"diagnostic_state": HorizonDiagnosticState.AMBER.value},
                )
            )
            fan_entries.append(
                HorizonQuantileSet(
                    horizon=h,
                    quantiles={
                        str(level): _serialize_numeric(np.quantile(path_slice, level, axis=0))
                        for level in _FAN_LEVELS
                    },
                )
            )
            mean_interval_width[h] = _mean_interval_width(lower, upper)
            sample_count_by_horizon[h] = int(paths.shape[0])
        rules = tuple(
            HorizonPolicyRule(
                horizon_start=h,
                horizon_end=h,
                diagnostic_state=HorizonDiagnosticState.AMBER,
                allowed_methods=(ForecastCalibrationMethod.COHERENT_BOOTSTRAP,),
                gate_eligible=False,
                fallback=ForecastCalibrationMethod.CONFORMAL,
                note="coherent sample paths are attached, but coverage backtesting remains pending",
            )
            for h in range(1, horizon_count + 1)
        )
        aggregation_gap = _aggregation_gap_by_horizon(
            base_lower if base_lower is not None else lower_matrix,
            base_upper if base_upper is not None else upper_matrix,
            aggregation_groups,
        )
        width_reduction, unreconciled_width = _width_reduction_by_horizon(
            mean_interval_width,
            base_lower=base_lower,
            base_upper=base_upper,
        )
        diagnostics = {
            "max_point_aggregation_error_by_horizon": point_aggregation_error,
            "max_point_constraint_error_by_horizon": point_constraint_error,
            "aggregation_gap_by_horizon": aggregation_gap,
            "empirical_coverage_by_horizon": {},
            "mean_interval_width_by_horizon": mean_interval_width,
            "unreconciled_mean_interval_width_by_horizon": unreconciled_width,
            "width_reduction_vs_unreconciled_by_horizon": width_reduction,
            "sample_count_by_horizon": sample_count_by_horizon,
            "diagnostic_state_by_horizon": _diagnostic_state_by_horizon(rules),
            "aggregation_group_count": len(aggregation_groups),
            "node_count": int(reconciled.shape[0]),
            "fallback_interval_source": (
                "coherent_sample_paths_with_unreconciled_gap"
                if base_lower is not None
                else "coherent_sample_paths"
            ),
        }
        certificate = ReconciliationCertificate(
            status=ReconciliationStatus.FALLBACK,
            method=reconciliation_method,
            constraints_kind=constraints_kind,
            coherent_points=max_point_error <= 1e-8,
            coherent_paths=True,
            coverage_scope="uncertified",
            preconditions_passed=False,
            preconditions={
                "rolling_origin_residual_bank": False,
                "coherent_sample_paths": True,
                "coverage_backtest_available": False,
                "coherent_points": max_point_error <= 1e-8,
                "max_point_aggregation_error": max(point_aggregation_error.values(), default=0.0),
                "max_point_constraint_error": max(point_constraint_error.values(), default=0.0),
            },
            diagnostics=diagnostics,
            coherent_sample_paths_ref=predictive_ref,
            fallback_reason="coherent paths emitted, but coverage backtest is pending",
        )
        return ForecastingUncertaintyBundleV2(
            method_fqn=method_fqn,
            source_method=method_fqn,
            target_id=target_id,
            generated_at=generated_at,
            prediction_interval=tuple(intervals),
            fan_chart=FanChartSpec(
                quantile_levels=_FAN_LEVELS,
                horizons=tuple(fan_entries),
            ),
            posterior_predictive_ref=predictive_ref,
            coverage_diagnostic=ForecastCoverageDiagnostic(
                nominal_coverage=nominal_coverage,
                mean_interval_width_by_horizon=mean_interval_width,
                sample_count_by_horizon=sample_count_by_horizon,
                regime_flags=(
                    "coherent_paths_emitted",
                    "coverage_backtest_pending",
                    "coverage_certificate_missing",
                    "aggregation_gap_reported",
                ),
                calibration_window=int(paths.shape[0]),
                last_recalibrated_at=generated_at,
            ),
            horizon_policy=HorizonPolicySpec(
                default_method=ForecastCalibrationMethod.COHERENT_BOOTSTRAP,
                rules=rules,
                gate_eligible=False,
                summary=(
                    "Coherent sample paths are available for bottom-up reconciliation, "
                    "but Phase 0 still requires external coverage validation before gating."
                ),
            ),
            interval_semantics=ForecastIntervalSemantics.PREDICTION_INTERVAL,
            calibration_method=ForecastCalibrationMethod.COHERENT_BOOTSTRAP,
            nominal_coverage=nominal_coverage,
            sample_size_assumption="coherent reconciled sample paths",
            regime_assumption="Hierarchy coherence is preserved path-wise; coverage validation remains external.",
            metadata={
                "phase": "phase0",
                "n_nodes": int(reconciled.shape[0]),
                "sample_paths": int(paths.shape[0]),
            },
            reconciliation_certificate=certificate,
        )

    rules = tuple(
        HorizonPolicyRule(
            horizon_start=h,
            horizon_end=h,
            diagnostic_state=HorizonDiagnosticState.RED,
            allowed_methods=(),
            gate_eligible=False,
            fallback=ForecastCalibrationMethod.COHERENT_BOOTSTRAP,
            note="coherent sample paths are required for probabilistically valid hierarchical intervals",
        )
        for h in range(1, horizon_count + 1)
    )
    point_matrix = np.asarray(reconciled, dtype=float)
    if base_lower is not None and base_upper is not None:
        interval_lower = np.minimum(base_lower, point_matrix)
        interval_upper = np.maximum(base_upper, point_matrix)
        base_adjustment = {
            h: float(
                np.mean(
                    np.maximum(base_lower[:, h - 1] - point_matrix[:, h - 1], 0.0)
                    + np.maximum(point_matrix[:, h - 1] - base_upper[:, h - 1], 0.0)
                )
            )
            for h in range(1, horizon_count + 1)
        }
        fallback_interval_source = "unreconciled_per_series_intervals"
    else:
        interval_lower = point_matrix
        interval_upper = point_matrix
        base_adjustment = dict.fromkeys(range(1, horizon_count + 1), 0.0)
        fallback_interval_source = "reconciled_points_only"
    aggregation_gap = _aggregation_gap_by_horizon(
        base_lower if base_lower is not None else interval_lower,
        base_upper if base_upper is not None else interval_upper,
        aggregation_groups,
    )
    mean_interval_width = _width_by_horizon(interval_lower, interval_upper)
    sample_count_by_horizon = dict.fromkeys(range(1, horizon_count + 1), 0)
    width_reduction, unreconciled_width = _width_reduction_by_horizon(
        mean_interval_width,
        base_lower=base_lower,
        base_upper=base_upper,
    )
    diagnostics = {
        "max_point_aggregation_error_by_horizon": point_aggregation_error,
        "max_point_constraint_error_by_horizon": point_constraint_error,
        "aggregation_gap_by_horizon": aggregation_gap,
        "empirical_coverage_by_horizon": {},
        "mean_interval_width_by_horizon": mean_interval_width,
        "unreconciled_mean_interval_width_by_horizon": unreconciled_width,
        "width_reduction_vs_unreconciled_by_horizon": width_reduction,
        "base_interval_point_containment_adjustment_by_horizon": base_adjustment,
        "sample_count_by_horizon": sample_count_by_horizon,
        "diagnostic_state_by_horizon": _diagnostic_state_by_horizon(rules),
        "aggregation_group_count": len(aggregation_groups),
        "node_count": int(reconciled.shape[0]),
        "fallback_interval_source": fallback_interval_source,
    }
    certificate = ReconciliationCertificate(
        status=ReconciliationStatus.FALLBACK,
        method=reconciliation_method,
        constraints_kind=constraints_kind,
        coherent_points=max_point_error <= 1e-8,
        coherent_paths=False,
        coverage_scope="uncertified",
        preconditions_passed=False,
        preconditions={
            "rolling_origin_residual_bank": False,
            "coherent_sample_paths": False,
            "coherent_points": max_point_error <= 1e-8,
            "max_point_aggregation_error": max(point_aggregation_error.values(), default=0.0),
            "max_point_constraint_error": max(point_constraint_error.values(), default=0.0),
        },
        diagnostics=diagnostics,
        fallback_reason="reconciled calibration residual bank is missing",
    )
    return ForecastingUncertaintyBundleV2(
        method_fqn=method_fqn,
        source_method=method_fqn,
        target_id=target_id,
        generated_at=generated_at,
        prediction_interval=tuple(
            HorizonInterval(
                horizon=h,
                point=_serialize_numeric(point),
                lower=_serialize_numeric(interval_lower[:, h - 1]),
                upper=_serialize_numeric(interval_upper[:, h - 1]),
                coverage_target=nominal_coverage,
                constructor=ForecastCalibrationMethod.NONE,
                diagnostics={"diagnostic_state": HorizonDiagnosticState.RED.value},
            )
            for h, point in enumerate(horizon_vectors, start=1)
        ),
        fan_chart=FanChartSpec(
            quantile_levels=(0.50,),
            horizons=tuple(
                HorizonQuantileSet(
                    horizon=h,
                    quantiles={"0.5": _serialize_numeric(point)},
                )
                for h, point in enumerate(horizon_vectors, start=1)
            ),
        ),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=nominal_coverage,
            mean_interval_width_by_horizon=mean_interval_width,
            sample_count_by_horizon=sample_count_by_horizon,
            regime_flags=(
                "coherent_paths_required",
                "distribution_missing",
                "intervals_not_reconciled",
                "aggregation_gap_reported",
                "coverage_certificate_missing",
            ),
            recommended_fallback=ForecastCalibrationMethod.COHERENT_BOOTSTRAP,
            calibration_window=int(reconciled.shape[0]),
            last_recalibrated_at=generated_at,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.NONE,
            rules=rules,
            gate_eligible=False,
            summary="Bottom-up reconciliation is emitted without probabilistic claims until coherent paths exist.",
        ),
        interval_semantics=ForecastIntervalSemantics.HEURISTIC_RANGE,
        calibration_method=ForecastCalibrationMethod.NONE,
        nominal_coverage=nominal_coverage,
        sample_size_assumption="reconciled point forecasts only",
        regime_assumption="Requires coherent bootstrap or Gaussian reconciliation on predictive paths.",
        metadata={"phase": "phase0", "n_nodes": int(reconciled.shape[0])},
        reconciliation_certificate=certificate,
    )


def build_attached_output_bundle(
    *,
    method_fqn: str,
    target_id: str,
    note: str,
    nominal_coverage: float = 0.90,
) -> ForecastingUncertaintyBundle:
    """Emit a bundle for decomposition-only methods without statistical claims."""

    return ForecastingUncertaintyBundle(
        method_fqn=method_fqn,
        source_method=method_fqn,
        target_id=target_id,
        generated_at=_utc_now(),
        prediction_interval=(),
        fan_chart=FanChartSpec(),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=nominal_coverage,
            regime_flags=("attached_output_only",),
            recommended_fallback=ForecastCalibrationMethod.CONFORMAL,
            calibration_window=0,
            last_recalibrated_at=_utc_now(),
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.NONE,
            rules=(),
            gate_eligible=False,
            summary=note,
        ),
        interval_semantics=ForecastIntervalSemantics.HEURISTIC_RANGE,
        calibration_method=ForecastCalibrationMethod.NONE,
        nominal_coverage=nominal_coverage,
        sample_size_assumption="no standalone forecast object was produced",
        regime_assumption=note,
        metadata={"phase": "phase0", "method_role": "attached_output_only"},
    )


__all__ = [
    "build_attached_output_bundle",
    "build_member_spread_bundle",
    "build_reconciled_conformal_bundle",
    "build_reconciliation_placeholder_bundle",
    "build_residual_conformal_bundle",
    "forecasting_output_slots",
    "resolve_artifact_store",
]
