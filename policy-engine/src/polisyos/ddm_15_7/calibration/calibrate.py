"""Calibration harness for DDM-15.7 false-positive certification."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Period(BaseModel):
    """Closed-open time period used by stationarity metadata."""

    model_config = ConfigDict(extra="forbid")

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Period:
        if self.end < self.start:
            raise ValueError("period end must not be before start")
        return self


class StationarityRegime(BaseModel):
    """Declared stationarity regime for a calibrated monitor."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    reference_period: Period
    calibration_period: Period
    holdout_stationary_period: Period
    seasonality_strata: list[str] = Field(default_factory=list)
    allowed_dependency_model: Literal["moving_block_bootstrap"] = "moving_block_bootstrap"
    block_length: int = Field(default=1, ge=1)
    label_delay_model: str = "empirical_delay_distribution_v1"
    invalidation_triggers: list[str] = Field(default_factory=list)


class FpTarget(BaseModel):
    """False-positive target for one detector or system alert family."""

    model_config = ConfigDict(extra="forbid")

    horizon: str = Field(min_length=1)
    alpha: float = Field(gt=0.0, lt=1.0)
    ert: float | None = Field(default=None, gt=0.0)


class EmpiricalStationaryHoldout(BaseModel):
    """Observed false-positive behavior on stationary holdout streams."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    alerts: int = Field(ge=0)
    windows: int = Field(ge=0)
    empirical_fp_rate: float = Field(ge=0.0, le=1.0)
    confidence_interval_95: tuple[float, float]
    pass_: bool = Field(alias="pass")


class SyntheticDelayResult(BaseModel):
    """Synthetic power/delay diagnostic."""

    model_config = ConfigDict(extra="forbid")

    min_detectable_shift: float = Field(ge=0.0)
    median_delay_windows: int = Field(ge=0)


class DetectionDelayTests(BaseModel):
    """Synthetic drift-injection delay diagnostics."""

    model_config = ConfigDict(extra="forbid")

    synthetic_covariate_shift: SyntheticDelayResult
    synthetic_concept_shift: SyntheticDelayResult


class CalibrationExpiration(BaseModel):
    """Calibration validity metadata."""

    model_config = ConfigDict(extra="forbid")

    valid_until: datetime
    invalidation_triggers: list[str] = Field(default_factory=list)


class CalibrationReport(BaseModel):
    """Versioned DDM-15.7 calibration report."""

    model_config = ConfigDict(extra="forbid")

    detector_id: str = Field(min_length=1)
    stationarity_regime_id: str = Field(min_length=1)
    fp_target: FpTarget
    threshold: float
    time_varying_thresholds: list[float] = Field(default_factory=list)
    observed_average_run_length: float | None = Field(default=None, ge=0.0)
    empirical_stationary_holdout: EmpiricalStationaryHoldout
    detection_delay_tests: DetectionDelayTests
    expiration: CalibrationExpiration
    calibration_method: str = "moving_block_bootstrap_quantile"
    random_seed: int = 0
    block_length: int = Field(default=1, ge=1)


def calibrate_detector(
    *,
    detector_id: str,
    stationarity_regime: StationarityRegime,
    fp_target: FpTarget,
    calibration_streams: list[list[float]],
    holdout_streams: list[list[float]],
    seed: int = 0,
) -> CalibrationReport:
    """Calibrate a detector threshold and certify stationary holdout behavior."""

    _require_streams(calibration_streams, "calibration_streams")
    _require_streams(holdout_streams, "holdout_streams")
    threshold = max_statistic_quantile(calibration_streams, 1.0 - fp_target.alpha)
    time_thresholds = time_varying_thresholds(calibration_streams, 1.0 - fp_target.alpha)
    holdout_alerts = sum(
        1 for stream in holdout_streams if first_alarm_index(stream, threshold) is not None
    )
    holdout_windows = len(holdout_streams)
    empirical_fp_rate = holdout_alerts / holdout_windows
    confidence_interval = binomial_wilson_interval(holdout_alerts, holdout_windows)
    observed_arl = average_run_length(holdout_streams, threshold)
    pass_holdout = confidence_interval[1] <= fp_target.alpha
    valid_until = stationarity_regime.holdout_stationary_period.end + timedelta(days=30)

    return CalibrationReport(
        detector_id=detector_id,
        stationarity_regime_id=stationarity_regime.id,
        fp_target=fp_target,
        threshold=threshold,
        time_varying_thresholds=time_thresholds,
        observed_average_run_length=observed_arl,
        empirical_stationary_holdout=EmpiricalStationaryHoldout(
            alerts=holdout_alerts,
            windows=holdout_windows,
            empirical_fp_rate=empirical_fp_rate,
            confidence_interval_95=confidence_interval,
            pass_=pass_holdout,
        ),
        detection_delay_tests=DetectionDelayTests(
            synthetic_covariate_shift=synthetic_delay_test(
                calibration_streams[0],
                threshold=threshold,
                shift=0.25,
            ),
            synthetic_concept_shift=synthetic_delay_test(
                calibration_streams[0],
                threshold=threshold,
                shift=0.50,
            ),
        ),
        expiration=CalibrationExpiration(
            valid_until=valid_until,
            invalidation_triggers=list(stationarity_regime.invalidation_triggers),
        ),
        random_seed=seed,
        block_length=stationarity_regime.block_length,
    )


def moving_block_bootstrap(
    values: list[float],
    *,
    block_length: int,
    sample_size: int,
    seed: int = 0,
) -> list[float]:
    """Sample a stream with replacement while preserving local autocorrelation."""

    if not values:
        raise ValueError("values must not be empty")
    if block_length <= 0:
        raise ValueError("block_length must be positive")
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")

    rng = _DeterministicRng(seed)
    sampled: list[float] = []
    max_start = max(1, len(values) - block_length + 1)
    while len(sampled) < sample_size:
        start = rng.randrange(max_start)
        sampled.extend(values[start : start + block_length])
    return sampled[:sample_size]


def bootstrap_stationary_streams(
    values: list[float],
    *,
    block_length: int,
    stream_length: int,
    n_streams: int,
    seed: int = 0,
) -> list[list[float]]:
    """Create no-drift replay streams from one stationary statistic series."""

    if n_streams <= 0:
        raise ValueError("n_streams must be positive")
    return [
        moving_block_bootstrap(
            values,
            block_length=block_length,
            sample_size=stream_length,
            seed=seed + index,
        )
        for index in range(n_streams)
    ]


def stratified_bootstrap_stationary_streams(
    strata_values: dict[str, list[float]],
    *,
    block_length: int,
    stream_length: int,
    n_streams: int,
    seed: int = 0,
) -> list[list[float]]:
    """Create no-drift streams by bootstrapping within declared strata."""

    if not strata_values:
        raise ValueError("strata_values must not be empty")
    if any(not values for values in strata_values.values()):
        raise ValueError("strata_values must not contain empty strata")
    if n_streams <= 0:
        raise ValueError("n_streams must be positive")

    strata = sorted(strata_values)
    streams: list[list[float]] = []
    for stream_index in range(n_streams):
        stream: list[float] = []
        for offset in range(stream_length):
            stratum = strata[offset % len(strata)]
            sample = moving_block_bootstrap(
                strata_values[stratum],
                block_length=block_length,
                sample_size=1,
                seed=seed + stream_index * stream_length + offset,
            )
            stream.extend(sample)
        streams.append(stream)
    return streams


def max_statistic_quantile(streams: list[list[float]], quantile: float) -> float:
    """Return a quantile of per-stream maximum statistics."""

    _require_streams(streams, "streams")
    if quantile <= 0.0 or quantile >= 1.0:
        raise ValueError("quantile must be inside (0, 1)")
    maxima = sorted(max(stream) for stream in streams)
    index = min(len(maxima) - 1, max(0, math.ceil(quantile * len(maxima)) - 1))
    return maxima[index]


def time_varying_thresholds(streams: list[list[float]], quantile: float) -> list[float]:
    """Compute per-time thresholds for sequential online monitoring."""

    _require_streams(streams, "streams")
    horizon = max(len(stream) for stream in streams)
    thresholds: list[float] = []
    for index in range(horizon):
        values_at_index = [
            stream[index]
            for stream in streams
            if index < len(stream)
        ]
        values_at_index.sort()
        threshold_index = min(
            len(values_at_index) - 1,
            max(0, math.ceil(quantile * len(values_at_index)) - 1),
        )
        thresholds.append(values_at_index[threshold_index])
    return thresholds


def first_alarm_index(stream: list[float], threshold: float) -> int | None:
    """Return the first threshold-crossing index or None."""

    for index, value in enumerate(stream):
        if value > threshold:
            return index
    return None


def first_alarm_index_with_thresholds(
    stream: list[float],
    thresholds: list[float],
) -> int | None:
    """Return the first index crossing its matching time-varying threshold."""

    if not thresholds:
        raise ValueError("thresholds must not be empty")
    for index, value in enumerate(stream):
        threshold = thresholds[min(index, len(thresholds) - 1)]
        if value > threshold:
            return index
    return None


def average_run_length(streams: list[list[float]], threshold: float) -> float:
    """Estimate average run length before false alarm on replay streams."""

    _require_streams(streams, "streams")
    run_lengths: list[int] = []
    for stream in streams:
        alarm_index = first_alarm_index(stream, threshold)
        run_lengths.append(len(stream) if alarm_index is None else alarm_index + 1)
    return sum(run_lengths) / len(run_lengths)


def binomial_wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for an empirical alert probability."""

    if n <= 0:
        raise ValueError("n must be positive")
    if successes < 0 or successes > n:
        raise ValueError("successes must be in [0, n]")
    phat = successes / n
    denominator = 1.0 + z**2 / n
    centre = phat + z**2 / (2.0 * n)
    radius = z * math.sqrt((phat * (1.0 - phat) + z**2 / (4.0 * n)) / n)
    low = (centre - radius) / denominator
    high = (centre + radius) / denominator
    return max(0.0, low), min(1.0, high)


def synthetic_delay_test(
    stationary_stream: list[float],
    *,
    threshold: float,
    shift: float,
) -> SyntheticDelayResult:
    """Inject a simple mean shift and report threshold-crossing delay."""

    if not stationary_stream:
        raise ValueError("stationary_stream must not be empty")
    change_point = len(stationary_stream) // 2
    shifted = [
        value if index < change_point else value + shift
        for index, value in enumerate(stationary_stream)
    ]
    alarm_index = first_alarm_index(shifted[change_point:], threshold)
    delay = len(stationary_stream) if alarm_index is None else alarm_index + 1
    return SyntheticDelayResult(min_detectable_shift=shift, median_delay_windows=delay)


def load_statistic_streams(
    path: Path,
    *,
    statistic_column: str,
    stream_column: str,
) -> list[list[float]]:
    """Load statistic streams from a CSV file."""

    grouped: dict[str, list[float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            stream_id = row.get(stream_column)
            statistic = row.get(statistic_column)
            if stream_id is None or statistic is None:
                raise ValueError("CSV is missing required statistic or stream column")
            grouped.setdefault(stream_id, []).append(float(statistic))
    return list(grouped.values())


def main(argv: list[str] | None = None) -> int:
    """Run detector calibration from the command line."""

    parser = argparse.ArgumentParser(description="Calibrate a DDM-15.7 detector")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-version", default="unknown")
    parser.add_argument("--detector-id", required=True)
    parser.add_argument("--stationarity-regime", required=True)
    parser.add_argument("--reference-period", required=True)
    parser.add_argument("--calibration-period", required=True)
    parser.add_argument("--holdout-period", required=True)
    parser.add_argument("--target-fp-budget", required=True, type=float)
    parser.add_argument("--seasonality-strata", default="")
    parser.add_argument("--block-length", required=True, type=int)
    parser.add_argument("--statistic-csv", required=True)
    parser.add_argument("--statistic-column", default="statistic")
    parser.add_argument("--stream-column", default="stream_id")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    regime = StationarityRegime(
        id=args.stationarity_regime,
        model_id=args.model_id,
        model_version=args.model_version,
        reference_period=_parse_period(args.reference_period),
        calibration_period=_parse_period(args.calibration_period),
        holdout_stationary_period=_parse_period(args.holdout_period),
        seasonality_strata=_split_csv(args.seasonality_strata),
        block_length=args.block_length,
        invalidation_triggers=[
            "model_version_change",
            "feature_transform_change",
            "upstream_schema_change",
            "label_delay_distribution_shift",
            "business_policy_change",
        ],
    )
    streams = load_statistic_streams(
        Path(args.statistic_csv),
        statistic_column=args.statistic_column,
        stream_column=args.stream_column,
    )
    split = max(1, len(streams) // 2)
    report = calibrate_detector(
        detector_id=args.detector_id,
        stationarity_regime=regime,
        fp_target=FpTarget(horizon="30d", alpha=args.target_fp_budget),
        calibration_streams=streams[:split],
        holdout_streams=streams[split:] or streams[:split],
    )
    Path(args.output).write_text(
        json.dumps(report.model_dump(mode="json", by_alias=True), indent=2),
        encoding="utf-8",
    )
    return 0


class _DeterministicRng:
    """Tiny deterministic generator for reproducible bootstrap sampling."""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0x7FFFFFFF

    def randrange(self, stop: int) -> int:
        if stop <= 0:
            raise ValueError("stop must be positive")
        self._state = (1103515245 * self._state + 12345) & 0x7FFFFFFF
        return self._state % stop


def _parse_period(raw: str) -> Period:
    parts = [part.strip() for part in raw.split(",", maxsplit=1)]
    if len(parts) != 2:
        raise ValueError("period must be formatted as start,end")
    return Period(start=datetime.fromisoformat(parts[0]), end=datetime.fromisoformat(parts[1]))


def _split_csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _require_streams(streams: list[list[float]], name: str) -> None:
    if not streams:
        raise ValueError(f"{name} must not be empty")
    if any(not stream for stream in streams):
        raise ValueError(f"{name} must not contain empty streams")


if __name__ == "__main__":
    sys.exit(main())
