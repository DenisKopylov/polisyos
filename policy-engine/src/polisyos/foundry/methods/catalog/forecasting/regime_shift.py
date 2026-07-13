"""Regime-aware forecasting for nonstationary policy time series."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

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
from polisyos.foundry.methods.catalog.forecasting.uncertainty import (
    forecasting_output_slots,
    resolve_artifact_store,
)
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastIntervalSemantics,
    HorizonDiagnosticState,
    HorizonInterval,
    HorizonPolicyRule,
    HorizonPolicySpec,
    HorizonQuantileSet,
)
from polisyos.ir.analytics.phase4_dynamics import Phase4DynamicsGate
from polisyos.ir.analytics.regime_shift_forecast import (
    ForecastShiftTypeAssessment,
    RegimeBenchmarkStatus,
    RegimeForecastCalibrationStatus,
    RegimeIdentifiabilityStatus,
    RegimeModelFamily,
    RegimeShiftForecastBundle,
)
from polisyos.ir.artifacts import ArtifactStore, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.registry.refs import ArtifactRefModel

_METHOD_FQN = "forecasting.regime_shift.hybrid@1.0.0"
_EPS = 1e-12
_FAN_LEVELS = (0.05, 0.50, 0.95)


@dataclass(frozen=True)
class _SegmentSummary:
    label: int
    start: int
    end: int
    canonical_label: str
    mean: float
    variance: float
    slope: float
    length: int


@dataclass(frozen=True)
class _SegmentationResult:
    breakpoints: tuple[int, ...]
    break_count_posterior: dict[int, float]
    regime_count_posterior: dict[int, float]
    selected_break_count_probability: float
    selected_bic: float


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _series(state: Any, *, key: str = "series") -> np.ndarray:
    values = state.get(key) if isinstance(state, Mapping) else state
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if arr.size < 12:
        raise ValueError(f"{key} must contain at least 12 observations")
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{key} must contain only finite values")
    return arr


def _segments_from_breaks(n_obs: int, breakpoints: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    boundaries = (0, *breakpoints, n_obs)
    return tuple((int(boundaries[i]), int(boundaries[i + 1])) for i in range(len(boundaries) - 1))


def _segment_sse(series: np.ndarray, start: int, end: int) -> float:
    values = series[start:end]
    if values.size == 0:
        return 0.0
    if values.size >= 3:
        x = np.arange(values.size, dtype=float)
        slope, intercept = np.polyfit(x, values, deg=1)
        fitted = intercept + slope * x
        return float(np.sum((values - fitted) ** 2))
    center = float(np.mean(values))
    return float(np.sum((values - center) ** 2))


def _total_sse(series: np.ndarray, breakpoints: tuple[int, ...]) -> float:
    return sum(_segment_sse(series, start, end) for start, end in _segments_from_breaks(series.size, breakpoints))


def _bic_score(series: np.ndarray, breakpoints: tuple[int, ...], *, penalty_scale: float) -> float:
    n_obs = int(series.size)
    sse = max(_total_sse(series, breakpoints), _EPS)
    n_segments = len(breakpoints) + 1
    n_parameters = 2 * n_segments + len(breakpoints)
    return float(n_obs * math.log(sse / max(n_obs, 1)) + penalty_scale * n_parameters * math.log(max(n_obs, 2)))


def _softmax_scores(scores: Mapping[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    best = min(scores.values())
    weights = {count: math.exp(-0.5 * (score - best)) for count, score in scores.items()}
    total = max(sum(weights.values()), _EPS)
    return {count: float(weight / total) for count, weight in sorted(weights.items())}


def _select_breaks(
    series: np.ndarray,
    *,
    max_breaks: int,
    min_dwell: int,
    penalty_scale: float,
) -> _SegmentationResult:
    n_obs = int(series.size)
    feasible_max = max(0, min(int(max_breaks), n_obs // max(min_dwell, 1) - 1))
    segmentations: dict[int, tuple[int, ...]] = {0: ()}

    previous_breaks: tuple[int, ...] = ()
    for break_count in range(1, feasible_max + 1):
        best_candidate: tuple[int, ...] | None = None
        best_sse = math.inf
        for start, end in _segments_from_breaks(n_obs, previous_breaks):
            if end - start < 2 * min_dwell:
                continue
            for candidate_break in range(start + min_dwell, end - min_dwell + 1):
                candidate = tuple(sorted((*previous_breaks, candidate_break)))
                sse = _total_sse(series, candidate)
                if sse < best_sse:
                    best_sse = sse
                    best_candidate = candidate
        if best_candidate is None:
            break
        segmentations[break_count] = best_candidate
        previous_breaks = best_candidate

    bic_by_break_count = {
        count: _bic_score(series, breaks, penalty_scale=penalty_scale)
        for count, breaks in segmentations.items()
    }
    posterior = _softmax_scores(bic_by_break_count)
    selected_count = min(bic_by_break_count, key=bic_by_break_count.__getitem__)
    selected_breaks = segmentations[selected_count]
    return _SegmentationResult(
        breakpoints=selected_breaks,
        break_count_posterior=posterior,
        regime_count_posterior={count + 1: prob for count, prob in posterior.items()},
        selected_break_count_probability=float(posterior.get(selected_count, 0.0)),
        selected_bic=float(bic_by_break_count[selected_count]),
    )


def _segment_slope(values: np.ndarray) -> float:
    if values.size < 3:
        return float(values[-1] - values[0]) if values.size > 1 else 0.0
    x = np.arange(values.size, dtype=float)
    slope, _intercept = np.polyfit(x, values, deg=1)
    return float(slope)


def _summarize_segments(series: np.ndarray, breakpoints: tuple[int, ...]) -> tuple[_SegmentSummary, ...]:
    raw: list[tuple[int, int, int, float, float, float, int]] = []
    for label, (start, end) in enumerate(_segments_from_breaks(int(series.size), breakpoints)):
        values = series[start:end]
        variance = float(np.var(values, ddof=1)) if values.size > 1 else 0.0
        raw.append(
            (
                label,
                start,
                end,
                float(np.mean(values)),
                variance,
                _segment_slope(values),
                int(values.size),
            )
        )

    canonical_by_label = {
        label: f"regime_{rank}"
        for rank, (label, *_rest) in enumerate(sorted(raw, key=lambda item: (item[3], item[1])))
    }
    return tuple(
        _SegmentSummary(
            label=label,
            start=start,
            end=end,
            canonical_label=canonical_by_label[label],
            mean=mean,
            variance=variance,
            slope=slope,
            length=length,
        )
        for label, start, end, mean, variance, slope, length in raw
    )


def _state_labels(n_obs: int, segments: tuple[_SegmentSummary, ...]) -> list[str]:
    labels = [""] * n_obs
    for segment in segments:
        for time_index in range(segment.start, segment.end):
            labels[time_index] = segment.canonical_label
    return labels


def _conformal_radius(errors: np.ndarray, coverage: float) -> float:
    arr = np.sort(np.abs(np.asarray(errors, dtype=float).reshape(-1)))
    if arr.size == 0:
        return 0.0
    rank = int(math.ceil((arr.size + 1) * float(np.clip(coverage, 0.0, 1.0)))) - 1
    rank = max(0, min(rank, arr.size - 1))
    return float(arr[rank])


def _segment_for_time(segments: tuple[_SegmentSummary, ...], time_index: int) -> _SegmentSummary:
    for segment in segments:
        if segment.start <= time_index < segment.end:
            return segment
    return segments[-1]


def _fitted_values(series: np.ndarray, segments: tuple[_SegmentSummary, ...]) -> np.ndarray:
    fitted = np.zeros_like(series, dtype=float)
    for segment in segments:
        fitted[segment.start : segment.end] = segment.mean
    return fitted


def _coverage_from_radius(actual: np.ndarray, center: np.ndarray, radius: float) -> float:
    if actual.size == 0:
        return 1.0
    hits = np.abs(actual - center) <= radius + _EPS
    return float(np.mean(hits))


def _calibration_slices(
    series: np.ndarray,
    segments: tuple[_SegmentSummary, ...],
    breakpoints: tuple[int, ...],
    *,
    nominal_coverage: float,
    radius: float,
    break_window: int,
) -> dict[str, Any]:
    fitted = _fitted_values(series, segments)
    overall = _coverage_from_radius(series, fitted, radius)
    by_regime = {
        segment.canonical_label: {
            "coverage": _coverage_from_radius(
                series[segment.start : segment.end],
                fitted[segment.start : segment.end],
                radius,
            ),
            "sample_count": segment.length,
        }
        for segment in segments
    }

    distance_rows: list[dict[str, Any]] = []
    for distance in range(-break_window, break_window + 1):
        values: list[float] = []
        centers: list[float] = []
        for breakpoint in breakpoints:
            index = breakpoint + distance
            if 0 <= index < series.size:
                values.append(float(series[index]))
                centers.append(float(fitted[index]))
        if values:
            distance_rows.append(
                {
                    "distance_to_break": distance,
                    "coverage": _coverage_from_radius(
                        np.asarray(values, dtype=float),
                        np.asarray(centers, dtype=float),
                        radius,
                    ),
                    "sample_count": len(values),
                }
            )

    by_regime_gaps = [
        abs(float(payload["coverage"]) - nominal_coverage)
        for payload in by_regime.values()
        if int(payload["sample_count"]) >= 3
    ]
    distance_gaps = [
        max(0.0, nominal_coverage - float(payload["coverage"]))
        for payload in distance_rows
        if int(payload["sample_count"]) >= 3
    ]
    return {
        "nominal_coverage": nominal_coverage,
        "overall_coverage": overall,
        "overall_gap": overall - nominal_coverage,
        "by_regime": by_regime,
        "by_distance_to_break": distance_rows,
        "max_abs_regime_gap": max(by_regime_gaps, default=0.0),
        "max_break_undercoverage_gap": max(distance_gaps, default=0.0),
        "radius": radius,
    }


def _break_recovery_curve(
    series: np.ndarray,
    segments: tuple[_SegmentSummary, ...],
    breakpoints: tuple[int, ...],
    *,
    radius: float,
    nominal_coverage: float,
    tolerance: float,
    break_window: int,
) -> dict[str, Any]:
    fitted = _fitted_values(series, segments)
    rows: list[dict[str, Any]] = []
    recovery_times: list[int | None] = []
    for breakpoint in breakpoints:
        post_rows: list[dict[str, Any]] = []
        recovered_at: int | None = None
        hits: list[float] = []
        for distance in range(0, break_window + 1):
            index = breakpoint + distance
            if index >= series.size:
                continue
            hit = float(abs(float(series[index]) - float(fitted[index])) <= radius + _EPS)
            hits.append(hit)
            cumulative = float(np.mean(hits))
            post_rows.append(
                {
                    "distance_after_break": distance,
                    "coverage": cumulative,
                    "sample_count": len(hits),
                }
            )
            if recovered_at is None and cumulative >= nominal_coverage - tolerance:
                recovered_at = distance
        rows.append({"breakpoint": breakpoint, "post_break_curve": post_rows})
        recovery_times.append(recovered_at)
    finite_recovery = [value for value in recovery_times if value is not None]
    return {
        "nominal_coverage": nominal_coverage,
        "tolerance": tolerance,
        "break_window": break_window,
        "curves": rows,
        "recovery_time_by_break": {
            str(breakpoint): recovery for breakpoint, recovery in zip(breakpoints, recovery_times, strict=True)
        },
        "max_recovery_time": max(finite_recovery) if finite_recovery else None,
    }


def _transition_summary(labels: list[str]) -> dict[str, Any]:
    states = tuple(sorted(dict.fromkeys(labels)))
    counts = {state: dict.fromkeys(states, 0) for state in states}
    for previous, current in zip(labels, labels[1:], strict=False):
        counts[previous][current] += 1
    probabilities: dict[str, dict[str, float]] = {}
    for state, row in counts.items():
        total = sum(row.values())
        probabilities[state] = {
            other: (float(value / total) if total else 0.0) for other, value in row.items()
        }
    return {"states": states, "transition_counts": counts, "transition_probabilities": probabilities}


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _artifact_ref(
    payload: dict[str, Any],
    *,
    kind: str,
    schema_name: str,
    artifact_store: ArtifactStore | None,
) -> ArtifactRefModel:
    json_payload = _json_ready(payload)
    if artifact_store is not None:
        ref = put_json_artifact(
            artifact_store,
            json_payload,
            kind=kind,
            schema_name=schema_name,
            schema_version="1.0",
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return ArtifactRefModel.model_validate(ref)

    canonical = to_canonical_bytes(
        {"kind": kind, "schema_name": schema_name, "payload": json_payload},
        CanonSpec(forbid_floats=False),
    )
    digest = hashlib.sha256(canonical).hexdigest()
    return ArtifactRefModel(
        artifact_id=f"sha256:{digest}",
        kind=kind,
        media_type="application/json",
    )


def _assignment_posterior_payload(labels: list[str], states: tuple[str, ...]) -> dict[str, Any]:
    return {
        "posterior_type": "hard_assignment_proxy",
        "states": states,
        "time_index": [
            {
                "t": time_index,
                "assigned_state": label,
                "probabilities": {state: (1.0 if state == label else 0.0) for state in states},
            }
            for time_index, label in enumerate(labels)
        ],
    }


def _break_posterior_payload(
    n_obs: int,
    breakpoints: tuple[int, ...],
    *,
    break_window: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for time_index in range(n_obs):
        probability = 0.0
        for breakpoint in breakpoints:
            distance = abs(time_index - breakpoint)
            if distance <= break_window:
                probability = max(probability, (break_window + 1 - distance) / (break_window + 1))
        rows.append({"t": time_index, "break_probability": float(probability)})
    return {
        "posterior_type": "localized_break_probability_proxy",
        "breakpoints": breakpoints,
        "time_index": rows,
    }


def _run_length_payload(n_obs: int, breakpoints: tuple[int, ...]) -> dict[str, Any]:
    last_break = max(breakpoints, default=0)
    rows = [{"t": t, "run_length": t - max([b for b in breakpoints if b <= t], default=0)} for t in range(n_obs)]
    return {
        "posterior_type": "hard_run_length_proxy",
        "current_run_length": int(n_obs - last_break),
        "time_index": rows,
    }


def _parameter_summary_payload(segments: tuple[_SegmentSummary, ...]) -> dict[str, Any]:
    return {
        "regimes": [
            {
                "label": segment.canonical_label,
                "segment_label": segment.label,
                "start": segment.start,
                "end": segment.end,
                "mean": segment.mean,
                "variance": segment.variance,
                "slope": segment.slope,
                "sample_count": segment.length,
            }
            for segment in segments
        ]
    }


def _duration_summary_payload(segments: tuple[_SegmentSummary, ...], *, min_dwell: int) -> dict[str, Any]:
    durations = [segment.length for segment in segments]
    return {
        "duration_model": "empirical_segment_dwell_time",
        "min_dwell_required": min_dwell,
        "observed_durations": durations,
        "minimum_observed_duration": min(durations) if durations else 0,
        "duration_by_regime": {
            segment.canonical_label: segment.length for segment in segments
        },
    }


def _predictive_mixture_payload(forecast: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> dict[str, Any]:
    return {
        "mixture_type": "last_regime_with_break_uncertainty_proxy",
        "horizons": [
            {
                "horizon": horizon,
                "point": float(point),
                "lower": float(lo),
                "upper": float(hi),
            }
            for horizon, (point, lo, hi) in enumerate(zip(forecast, lower, upper, strict=True), start=1)
        ],
    }


def _conditional_forecasts_payload(
    segments: tuple[_SegmentSummary, ...],
    horizon: int,
    radius: float,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for segment in segments:
        point = np.asarray([segment.mean + step * segment.slope for step in range(1, horizon + 1)], dtype=float)
        scale = np.sqrt(np.arange(1, horizon + 1, dtype=float))
        rows.append(
            {
                "regime": segment.canonical_label,
                "forecast": point.tolist(),
                "lower": (point - radius * scale).tolist(),
                "upper": (point + radius * scale).tolist(),
            }
        )
    return {"regime_conditional_forecasts": rows}


def _identifiability_payload(
    segments: tuple[_SegmentSummary, ...],
    segmentation: _SegmentationResult,
    *,
    lag_order: int,
    min_dwell: int,
    separation_threshold: float,
    nominal_coverage: float,
    coverage_tolerance: float,
    calibration_slices: Mapping[str, Any],
) -> tuple[dict[str, Any], RegimeIdentifiabilityStatus, RegimeBenchmarkStatus]:
    variances = [max(segment.variance, 0.0) for segment in segments]
    pooled_std = math.sqrt(max(float(np.mean(variances)), _EPS))
    adjacent_separations: list[float] = []
    for left, right in zip(segments, segments[1:], strict=False):
        adjacent_separations.append(abs(right.mean - left.mean) / pooled_std)
    min_separation = min(adjacent_separations, default=math.inf)
    dwell_ok = bool(all(segment.length > lag_order and segment.length >= min_dwell for segment in segments))
    separability_ok = bool(min_separation >= separation_threshold or len(segments) == 1)
    count_penalty_ok = bool(segmentation.selected_break_count_probability >= 0.50)
    overall_coverage = float(calibration_slices["overall_coverage"])
    max_regime_gap = float(calibration_slices["max_abs_regime_gap"])
    max_break_undercoverage = float(calibration_slices["max_break_undercoverage_gap"])
    calibration_ok = (
        overall_coverage >= nominal_coverage - coverage_tolerance
        and max_regime_gap <= max(coverage_tolerance * 2.0, 0.20)
        and max_break_undercoverage <= max(coverage_tolerance * 2.0, 0.20)
    )

    if separability_ok and dwell_ok and count_penalty_ok:
        identifiability_status = RegimeIdentifiabilityStatus.IDENTIFIED
    elif dwell_ok and (separability_ok or count_penalty_ok):
        identifiability_status = RegimeIdentifiabilityStatus.WEAKLY_IDENTIFIED
    else:
        identifiability_status = RegimeIdentifiabilityStatus.NOT_IDENTIFIED

    if identifiability_status is RegimeIdentifiabilityStatus.IDENTIFIED and calibration_ok:
        benchmark_status = RegimeBenchmarkStatus.GREEN
    elif overall_coverage >= nominal_coverage - coverage_tolerance:
        benchmark_status = RegimeBenchmarkStatus.YELLOW
    else:
        benchmark_status = RegimeBenchmarkStatus.RED

    payload = {
        "gates": {
            "separability": {
                "passed": separability_ok,
                "minimum_adjacent_standardized_separation": None if math.isinf(min_separation) else min_separation,
                "threshold": separation_threshold,
            },
            "dwell_time": {
                "passed": dwell_ok,
                "minimum_required_dwell": min_dwell,
                "lag_order": lag_order,
                "minimum_observed_dwell": min((segment.length for segment in segments), default=0),
            },
            "complexity_control": {
                "passed": count_penalty_ok,
                "selected_break_count_probability": segmentation.selected_break_count_probability,
                "selected_bic": segmentation.selected_bic,
            },
            "adaptive_calibration": {
                "passed": calibration_ok,
                "overall_coverage": overall_coverage,
                "nominal_coverage": nominal_coverage,
                "coverage_tolerance": coverage_tolerance,
                "max_abs_regime_gap": max_regime_gap,
                "max_break_undercoverage_gap": max_break_undercoverage,
            },
        },
        "identifiability_status": identifiability_status.value,
        "benchmark_status": benchmark_status.value,
    }
    return payload, identifiability_status, benchmark_status


def _regime_status(
    benchmark_status: RegimeBenchmarkStatus,
    identifiability_status: RegimeIdentifiabilityStatus,
    breakpoints: tuple[int, ...],
    *,
    n_obs: int,
    break_window: int,
) -> RegimeForecastCalibrationStatus:
    if breakpoints and n_obs - max(breakpoints) <= break_window:
        return RegimeForecastCalibrationStatus.DRIFTING
    if (
        benchmark_status is RegimeBenchmarkStatus.GREEN
        and identifiability_status is RegimeIdentifiabilityStatus.IDENTIFIED
    ):
        return RegimeForecastCalibrationStatus.CALIBRATED
    if benchmark_status is RegimeBenchmarkStatus.YELLOW:
        return RegimeForecastCalibrationStatus.WEAKLY_CALIBRATED
    return RegimeForecastCalibrationStatus.UNKNOWN


def _forecast_last_regime(
    series: np.ndarray,
    segments: tuple[_SegmentSummary, ...],
    *,
    horizon: int,
) -> np.ndarray:
    last = segments[-1]
    values = series[last.start : last.end]
    slope = last.slope if values.size >= 4 else float(np.mean(np.diff(values))) if values.size > 1 else 0.0
    anchor = float(values[-1]) if values.size else last.mean
    shrink = min(1.0, values.size / 24.0)
    effective_slope = shrink * slope
    return np.asarray([anchor + effective_slope * step for step in range(1, horizon + 1)], dtype=float)


def _build_intervals(
    forecast: np.ndarray,
    *,
    radius: float,
    nominal_coverage: float,
    sample_count: int,
    diagnostic_state: HorizonDiagnosticState,
) -> tuple[tuple[HorizonInterval, ...], FanChartSpec]:
    intervals: list[HorizonInterval] = []
    fan_entries: list[HorizonQuantileSet] = []
    for horizon, point in enumerate(forecast, start=1):
        scaled_radius = radius * math.sqrt(float(horizon))
        lower = float(point - scaled_radius)
        upper = float(point + scaled_radius)
        point_float = float(point)
        intervals.append(
            HorizonInterval(
                horizon=horizon,
                point=point_float,
                lower=lower,
                upper=upper,
                coverage_target=nominal_coverage,
                constructor=ForecastCalibrationMethod.CONFORMAL,
                sample_count=sample_count,
                diagnostics={
                    "diagnostic_state": diagnostic_state.value,
                    "adaptive_regime_calibration": True,
                },
            )
        )
        fan_entries.append(
            HorizonQuantileSet(
                horizon=horizon,
                quantiles={
                    "0.05": lower,
                    "0.5": point_float,
                    "0.95": upper,
                },
            )
        )
    return tuple(intervals), FanChartSpec(quantile_levels=_FAN_LEVELS, horizons=tuple(fan_entries))


@foundry_method(
    namespace="forecasting.regime_shift",
    version="1.0.0",
    tags={"forecasting", "time-series", "regime-switching", "structural-breaks"},
)
class RegimeShiftForecastEstimator:
    """Hybrid changepoint/regime forecaster with explicit calibration gates."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="hybrid",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {SlotSpec("series", SlotType.VECTOR, Unit("timeseries", "value"), shape=("n_obs",))}
        ),
        output_slots=forecasting_output_slots(output_contract=RegimeShiftForecastBundle),
        parameters=(
            ParameterSpec(name="horizon", default=6),
            ParameterSpec(name="nominal_coverage", default=0.9),
            ParameterSpec(name="max_breaks", default=3),
            ParameterSpec(name="min_dwell", default=8),
            ParameterSpec(name="lag_order", default=2),
            ParameterSpec(name="separation_threshold", default=1.25),
            ParameterSpec(name="coverage_tolerance", default=0.08),
            ParameterSpec(name="break_window", default=4),
            ParameterSpec(name="shift_type_assessment", default="structural"),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Hybrid regime-shift forecaster for nonstationary policy series. "
            "It detects persistent structural breaks, stores assignment/break uncertainty, "
            "and gates intervals on separability, dwell time, complexity control, and calibration."
        ),
        tags=frozenset({"forecasting", "time-series", "regime-switching", "structural-breaks"}),
        declared_truthfulness_tier="approximate_calibrated",
        truthfulness_scope="marginal_coverage",
        when_to_use=(
            "Policy time series with reforms, crises, or institutional shifts where a stable "
            "ARIMA-style stationarity assumption is not credible."
        ),
        typical_min_obs=48,
        output_interpretation=(
            "Returns a RegimeShiftForecastBundle containing forecast intervals plus regime-count, "
            "assignment, break-date, dwell-time, shift-type, and benchmark diagnostics."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        series = _series(state)
        horizon = max(1, int(params.get("horizon", 6)))
        nominal_coverage = float(np.clip(float(params.get("nominal_coverage", 0.90)), 0.50, 0.99))
        lag_order = max(0, int(params.get("lag_order", 2)))
        min_dwell = max(lag_order + 1, int(params.get("min_dwell", 8)))
        max_breaks = max(0, int(params.get("max_breaks", 3)))
        penalty_scale = max(0.25, float(params.get("penalty_scale", 1.0)))
        separation_threshold = max(0.0, float(params.get("separation_threshold", 1.25)))
        coverage_tolerance = max(0.0, float(params.get("coverage_tolerance", 0.08)))
        break_window = max(0, int(params.get("break_window", 4)))
        shift_type = ForecastShiftTypeAssessment(
            str(params.get("shift_type_assessment", ForecastShiftTypeAssessment.STRUCTURAL.value))
        )
        artifact_store = resolve_artifact_store(state, params)

        segmentation = _select_breaks(
            series,
            max_breaks=max_breaks,
            min_dwell=min_dwell,
            penalty_scale=penalty_scale,
        )
        segments = _summarize_segments(series, segmentation.breakpoints)
        labels = _state_labels(int(series.size), segments)
        states = tuple(sorted(dict.fromkeys(labels)))
        fitted = _fitted_values(series, segments)
        residuals = series - fitted
        radius = max(
            _conformal_radius(residuals, nominal_coverage),
            float(np.std(np.diff(series), ddof=1)) if series.size > 2 else 0.0,
            _EPS,
        )

        calibration_slices = _calibration_slices(
            series,
            segments,
            segmentation.breakpoints,
            nominal_coverage=nominal_coverage,
            radius=radius,
            break_window=break_window,
        )
        recovery_curve = _break_recovery_curve(
            series,
            segments,
            segmentation.breakpoints,
            radius=radius,
            nominal_coverage=nominal_coverage,
            tolerance=coverage_tolerance,
            break_window=break_window,
        )
        diagnostics, identifiability_status, benchmark_status = _identifiability_payload(
            segments,
            segmentation,
            lag_order=lag_order,
            min_dwell=min_dwell,
            separation_threshold=separation_threshold,
            nominal_coverage=nominal_coverage,
            coverage_tolerance=coverage_tolerance,
            calibration_slices=calibration_slices,
        )
        regime_status = _regime_status(
            benchmark_status,
            identifiability_status,
            segmentation.breakpoints,
            n_obs=int(series.size),
            break_window=break_window,
        )
        Phase4DynamicsGate().enforce(
            horizon=horizon,
            regime_bundle={"regime_status": regime_status.value},
            metadata={"method_fqn": _METHOD_FQN, "stage": "pre_forecast"},
        )

        forecast = _forecast_last_regime(series, segments, horizon=horizon)
        scale = np.sqrt(np.arange(1, horizon + 1, dtype=float))
        lower = forecast - radius * scale
        upper = forecast + radius * scale
        horizon_state = (
            HorizonDiagnosticState.GREEN
            if benchmark_status is RegimeBenchmarkStatus.GREEN
            else HorizonDiagnosticState.AMBER
            if benchmark_status is RegimeBenchmarkStatus.YELLOW
            else HorizonDiagnosticState.RED
        )
        intervals, fan_chart = _build_intervals(
            forecast,
            radius=radius,
            nominal_coverage=nominal_coverage,
            sample_count=int(series.size),
            diagnostic_state=horizon_state,
        )

        generated_at = _utc_now()
        coverage_by_horizon = {h: float(calibration_slices["overall_coverage"]) for h in range(1, horizon + 1)}
        coverage_gap_by_horizon = {
            h: float(calibration_slices["overall_coverage"]) - nominal_coverage for h in range(1, horizon + 1)
        }
        width_by_horizon = {h: float(2.0 * radius * math.sqrt(float(h))) for h in range(1, horizon + 1)}
        sample_count_by_horizon = dict.fromkeys(range(1, horizon + 1), int(series.size))
        gate_eligible = benchmark_status is not RegimeBenchmarkStatus.RED
        rule = HorizonPolicyRule(
            horizon_start=1,
            horizon_end=horizon,
            diagnostic_state=horizon_state,
            allowed_methods=(ForecastCalibrationMethod.CONFORMAL,) if gate_eligible else (),
            gate_eligible=gate_eligible,
            fallback=ForecastCalibrationMethod.BOOTSTRAP if not gate_eligible else None,
            regime=regime_status.value,
            note="Regime-aware adaptive conformal intervals are gated by separability, dwell time, count penalty, and break-local coverage.",
        )

        refs = {
            "regime_count_posterior_ref": _artifact_ref(
                {"posterior": segmentation.regime_count_posterior},
                kind="ir.regime_count_posterior",
                schema_name="ir.regime_count_posterior",
                artifact_store=artifact_store,
            ),
            "break_count_posterior_ref": _artifact_ref(
                {"posterior": segmentation.break_count_posterior},
                kind="ir.break_count_posterior",
                schema_name="ir.break_count_posterior",
                artifact_store=artifact_store,
            ),
            "assignment_posterior_ref": _artifact_ref(
                _assignment_posterior_payload(labels, states),
                kind="ir.regime_assignment_posterior",
                schema_name="ir.regime_assignment_posterior",
                artifact_store=artifact_store,
            ),
            "break_posterior_ref": _artifact_ref(
                _break_posterior_payload(int(series.size), segmentation.breakpoints, break_window=break_window),
                kind="ir.break_posterior",
                schema_name="ir.break_posterior",
                artifact_store=artifact_store,
            ),
            "run_length_posterior_ref": _artifact_ref(
                _run_length_payload(int(series.size), segmentation.breakpoints),
                kind="ir.run_length_posterior",
                schema_name="ir.run_length_posterior",
                artifact_store=artifact_store,
            ),
            "permutation_invariant_regime_map_ref": _artifact_ref(
                {
                    "canonicalization": "sort_by_regime_mean_then_first_occurrence",
                    "map": {str(segment.label): segment.canonical_label for segment in segments},
                },
                kind="ir.permutation_invariant_regime_map",
                schema_name="ir.permutation_invariant_regime_map",
                artifact_store=artifact_store,
            ),
            "regime_parameter_summary_ref": _artifact_ref(
                _parameter_summary_payload(segments),
                kind="ir.regime_parameter_summary",
                schema_name="ir.regime_parameter_summary",
                artifact_store=artifact_store,
            ),
            "duration_summary_ref": _artifact_ref(
                _duration_summary_payload(segments, min_dwell=min_dwell),
                kind="ir.regime_duration_summary",
                schema_name="ir.regime_duration_summary",
                artifact_store=artifact_store,
            ),
            "transition_summary_ref": _artifact_ref(
                _transition_summary(labels),
                kind="ir.regime_transition_summary",
                schema_name="ir.regime_transition_summary",
                artifact_store=artifact_store,
            ),
            "predictive_mixture_ref": _artifact_ref(
                _predictive_mixture_payload(forecast, lower, upper),
                kind="ir.regime_predictive_mixture",
                schema_name="ir.regime_predictive_mixture",
                artifact_store=artifact_store,
            ),
            "regime_conditional_forecasts_ref": _artifact_ref(
                _conditional_forecasts_payload(segments, horizon, radius),
                kind="ir.regime_conditional_forecasts",
                schema_name="ir.regime_conditional_forecasts",
                artifact_store=artifact_store,
            ),
            "calibration_slice_ref": _artifact_ref(
                dict(calibration_slices),
                kind="ir.regime_calibration_slice",
                schema_name="ir.regime_calibration_slice",
                artifact_store=artifact_store,
            ),
            "break_recovery_curve_ref": _artifact_ref(
                recovery_curve,
                kind="ir.break_recovery_curve",
                schema_name="ir.break_recovery_curve",
                artifact_store=artifact_store,
            ),
            "shift_type_assessment_ref": _artifact_ref(
                {"shift_type_assessment": shift_type.value},
                kind="ir.shift_type_assessment",
                schema_name="ir.shift_type_assessment",
                artifact_store=artifact_store,
            ),
            "identifiability_diagnostics_ref": _artifact_ref(
                diagnostics,
                kind="ir.regime_identifiability_diagnostics",
                schema_name="ir.regime_identifiability_diagnostics",
                artifact_store=artifact_store,
            ),
        }

        bundle = RegimeShiftForecastBundle(
            method_fqn=_METHOD_FQN,
            source_method=_METHOD_FQN,
            target_id="series",
            generated_at=generated_at,
            prediction_interval=intervals,
            fan_chart=fan_chart,
            coverage_diagnostic=ForecastCoverageDiagnostic(
                nominal_coverage=nominal_coverage,
                empirical_coverage_by_horizon=coverage_by_horizon,
                coverage_gap_by_horizon=coverage_gap_by_horizon,
                mean_interval_width_by_horizon=width_by_horizon,
                conditional_coverage_pvalue_by_horizon=dict.fromkeys(range(1, horizon + 1), None),
                independence_pvalue_by_horizon=dict.fromkeys(range(1, horizon + 1), None),
                wis_by_horizon=dict.fromkeys(range(1, horizon + 1), None),
                sample_count_by_horizon=sample_count_by_horizon,
                regime_flags=(
                    "regime_conditional_coverage_tracked",
                    "break_local_coverage_tracked",
                    "assignment_uncertainty_attached",
                ),
                recommended_fallback=ForecastCalibrationMethod.BOOTSTRAP if not gate_eligible else None,
                calibration_window=int(series.size),
                last_recalibrated_at=generated_at,
            ),
            horizon_policy=HorizonPolicySpec(
                default_method=ForecastCalibrationMethod.CONFORMAL,
                rules=(rule,),
                gate_eligible=gate_eligible,
                summary="Regime-shift forecast intervals are released through traffic-light benchmark gates.",
            ),
            interval_semantics=ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
            calibration_method=ForecastCalibrationMethod.CONFORMAL,
            nominal_coverage=nominal_coverage,
            sample_size_assumption="empirical residual conformal radius within detected regimes",
            regime_assumption="hybrid recurrent-regime/changepoint uncertainty with explicit dwell and separability gates",
            regime_model_family=RegimeModelFamily.HYBRID,
            identifiability_status=identifiability_status,
            regime_status=regime_status,
            shift_type_assessment=shift_type,
            benchmark_status=benchmark_status,
            metadata={
                "phase": "phase4",
                "method_note": "Hybrid regime-shift forecaster with adaptive conformal calibration overlay.",
                "history_observations": int(series.size),
                "breakpoints": list(segmentation.breakpoints),
                "regime_count": len(segments),
                "minimum_dwell_observed": min((segment.length for segment in segments), default=0),
                "selected_break_count_probability": segmentation.selected_break_count_probability,
            },
            **refs,
        )

        return {
            "result": {
                "forecast": forecast.tolist(),
                "lower": lower.tolist(),
                "upper": upper.tolist(),
                "breakpoints": list(segmentation.breakpoints),
                "regime_count": len(segments),
                "identifiability_status": identifiability_status.value,
                "regime_status": regime_status.value,
                "benchmark_status": benchmark_status.value,
                "shift_type_assessment": shift_type.value,
            },
            "forecasting_uncertainty_bundle": bundle,
            "regime_shift_forecast_bundle": bundle,
        }


__all__ = ["RegimeShiftForecastEstimator"]
