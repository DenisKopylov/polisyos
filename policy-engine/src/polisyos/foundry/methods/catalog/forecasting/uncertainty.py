"""Helpers for attaching honest multi-horizon uncertainty bundles to forecasting methods."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import numpy as np

from polisyos.foundry.methods.base import SlotSpec, SlotType, Unit
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
from polisyos.ir.artifacts import ArtifactStore, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import ArtifactRefModel

_FAN_LEVELS = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
_EPS = 1e-12


def forecasting_output_slots() -> frozenset[SlotSpec]:
    """Return the standard forecasting output surface for Phase 0."""

    return frozenset(
        {
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec(
                "forecasting_uncertainty_bundle",
                SlotType.SCALAR,
                Unit("uncertainty", "json"),
                contract_id=ForecastingUncertaintyBundle.contract_id,
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
    target_id: str,
    history: np.ndarray,
    point_forecast: np.ndarray,
    forecast_fn: Callable[[np.ndarray, int], np.ndarray],
    nominal_coverage: float = 0.90,
    min_train_size: int = 4,
    method_note: str | None = None,
    extra_regime_flags: tuple[str, ...] = (),
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


def build_reconciliation_placeholder_bundle(
    *,
    method_fqn: str,
    target_id: str,
    reconciled_forecasts: np.ndarray,
    nominal_coverage: float = 0.90,
    coherent_sample_paths: np.ndarray | None = None,
    artifact_store: ArtifactStore | None = None,
) -> ForecastingUncertaintyBundle:
    """Expose reconciliation outputs without overstating probabilistic validity."""

    reconciled = np.asarray(reconciled_forecasts, dtype=float)
    if reconciled.ndim != 2:
        raise ValueError("reconciled_forecasts must be a matrix")
    horizon_count = int(reconciled.shape[1])
    horizon_vectors = [reconciled[:, horizon - 1] for horizon in range(1, horizon_count + 1)]
    generated_at = _utc_now()
    predictive_ref: ArtifactRefModel | None = None

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
        for h in range(1, horizon_count + 1):
            path_slice = np.asarray(paths[:, :, h - 1], dtype=float)
            lower = np.quantile(path_slice, (1.0 - nominal_coverage) / 2.0, axis=0)
            upper = np.quantile(path_slice, 1.0 - (1.0 - nominal_coverage) / 2.0, axis=0)
            point = np.asarray(reconciled[:, h - 1], dtype=float)
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
        return ForecastingUncertaintyBundle(
            method_fqn=method_fqn,
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
                regime_flags=("coherent_paths_emitted", "coverage_backtest_pending"),
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
    return ForecastingUncertaintyBundle(
        method_fqn=method_fqn,
        target_id=target_id,
        generated_at=generated_at,
        prediction_interval=tuple(
            HorizonInterval(
                horizon=h,
                point=_serialize_numeric(point),
                lower=_serialize_numeric(point),
                upper=_serialize_numeric(point),
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
            mean_interval_width_by_horizon=dict.fromkeys(range(1, horizon_count + 1), 0.0),
            sample_count_by_horizon=dict.fromkeys(range(1, horizon_count + 1), 0),
            regime_flags=("coherent_paths_required", "distribution_missing"),
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
    "build_reconciliation_placeholder_bundle",
    "build_residual_conformal_bundle",
    "forecasting_output_slots",
    "resolve_artifact_store",
]
