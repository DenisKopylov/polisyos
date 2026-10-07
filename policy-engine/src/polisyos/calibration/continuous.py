"""Continuous predictive calibration diagnostics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from polisyos.calibration.curve import compute_calibration_curve
from polisyos.ir.analytics.calibration_diagnostics import (
    CalibrationCurveBin,
    CalibrationDiagnosticIssue,
    CalibrationDiagnosticsReport,
    CalibrationMetricInterval,
    CalibrationMetrics,
)
from polisyos.ir.analytics.query_validation_report import ValidationSeverity

if TYPE_CHECKING:
    from polisyos.core import artifacts as core_artifacts

_EPSILON = 1e-12
_DEFAULT_LEVELS = (0.5, 0.8, 0.9)


def evaluate_continuous(
    *,
    y_true: Sequence[float],
    intervals: Mapping[float, Sequence[tuple[float, float]]]
    | Sequence[Sequence[tuple[float, float]]]
    | None = None,
    predictive_samples: Sequence[Sequence[float]] | None = None,
    levels: Sequence[float] | None = None,
    uncertainty: Mapping[str, Any] | None = None,
    strict: bool = True,
) -> CalibrationDiagnosticsReport:
    """Evaluate interval coverage and PIT-style diagnostics for continuous outcomes."""

    y_arr = np.asarray(y_true, dtype=float)
    if y_arr.ndim != 1 or y_arr.size == 0:
        raise ValueError("y_true must be a nonempty one-dimensional sequence")
    if not np.all(np.isfinite(y_arr)):
        raise ValueError("y_true contains non-finite values")
    bootstrap_seed = _bootstrap_replay_seed(uncertainty, required=False)

    issues: list[CalibrationDiagnosticIssue] = []
    warnings: list[str] = []

    sample_arr = _prepare_predictive_samples(predictive_samples, n_obs=y_arr.size)
    level_values, interval_sets = _prepare_interval_sets(
        y_true=y_arr,
        intervals=intervals,
        predictive_samples=sample_arr,
        levels=levels,
        strict=strict,
    )

    curve_result = compute_calibration_curve(
        y_true=y_arr.tolist(),
        intervals=interval_sets,
        levels=list(level_values),
    )
    if curve_result.evaluation_status != "evaluated":
        issue_code = (
            "CALIB_INTERVAL_INCOMPLETE"
            if curve_result.evaluation_status == "incomplete"
            else "CALIB_INTERVAL_NOT_EVALUATED"
        )
        issues.append(
            CalibrationDiagnosticIssue(
                code=issue_code,
                message="No complete interval-coverage comparison was evaluated.",
                severity=ValidationSeverity.ERROR,
                path="calibration.curves.interval_coverage",
                expected=">=1 measured interval comparison",
                actual=curve_result.n_comparisons,
                context={"evaluation_status": curve_result.evaluation_status},
            )
        )
    deviations = np.asarray(
        [point.empirical_coverage - point.nominal_level for point in curve_result.points],
        dtype=float,
    )
    curve_bins = [
        CalibrationCurveBin(
            lower=float(point.nominal_level),
            upper=float(point.nominal_level),
            count=int(point.n_observations),
            mean_predicted=float(point.nominal_level),
            mean_observed=float(point.empirical_coverage),
            absolute_gap=abs(float(point.empirical_coverage - point.nominal_level)),
        )
        for point in curve_result.points
    ]
    rmsce = float(math.sqrt(np.mean(deviations**2))) if deviations.size else None

    metric_intervals: dict[str, CalibrationMetricInterval] = {}
    if (
        curve_result.evaluation_status == "evaluated"
        and uncertainty
        and int(uncertainty.get("bootstrap", 0) or 0) > 0
    ):
        curve_bins, metric_intervals = _attach_interval_bootstrap(
            y_true=y_arr,
            levels=level_values,
            interval_sets=interval_sets,
            bootstrap_reps=int(uncertainty.get("bootstrap", 0) or 0),
            confidence_level=float(uncertainty.get("confidence_level", 0.95)),
            rng_seed=bootstrap_seed,
            original_bins=curve_bins,
        )

    metadata = {
        "nominal_levels": list(level_values),
        "interval_width_mean": _interval_width_summary(level_values, interval_sets),
    }
    ence = None
    if sample_arr is not None:
        pit = np.mean(sample_arr <= y_arr[:, None], axis=1)
        metadata["pit_histogram"] = _pit_histogram(pit)
        metadata["pit_summary"] = {
            "mean": float(np.mean(pit)),
            "variance": float(np.var(pit)),
            "max_bin_gap": float(
                np.max(np.abs(np.asarray(metadata["pit_histogram"]["density"]) - 0.1))
            ),
        }
        ence = _continuous_ence(y_true=y_arr, predictive_samples=sample_arr)
        if sample_arr.shape[1] < 20:
            warnings.append("Predictive sample count is small for stable PIT diagnostics.")
            issues.append(
                CalibrationDiagnosticIssue(
                    code="CALIB_PIT_LOW_SAMPLE_DRAW_COUNT",
                    message="Predictive sample count is low for stable PIT diagnostics.",
                    severity=ValidationSeverity.WARNING,
                    path="calibration.predictive_samples",
                    expected=">=20 draws",
                    actual=int(sample_arr.shape[1]),
                )
            )
    else:
        warnings.append(
            "PIT diagnostics were skipped because predictive_samples were not provided."
        )

    if y_arr.size < 100:
        issues.append(
            CalibrationDiagnosticIssue(
                code="CALIB_INTERVAL_LOW_N",
                message="Continuous interval calibration is based on a small sample.",
                severity=ValidationSeverity.WARNING,
                path="calibration.metrics.n_obs",
                expected=">=100",
                actual=int(y_arr.size),
            )
        )

    report = CalibrationDiagnosticsReport(
        task="continuous",
        target_type="predictive_distribution" if sample_arr is not None else "interval_set",
        metrics=CalibrationMetrics(
            n_obs=int(y_arr.size),
            ece=None if curve_result.ece is None else float(curve_result.ece),
            mce=None if curve_result.max_ce is None else float(curve_result.max_ce),
            rmsce=rmsce,
            ence=ence,
            intervals=metric_intervals,
        ),
        curves={"interval_coverage": tuple(curve_bins)},
        issues=tuple(issues),
        warnings=tuple(warnings),
        primary_curve="interval_coverage",
        recommended_action=_recommended_action(deviations),
        metadata={
            **metadata,
            "interval_coverage": {
                "status": curve_result.evaluation_status,
                "n_comparisons": curve_result.n_comparisons,
                "requested": int(y_arr.size * len(level_values)),
                "eligible": sum(point.n_observations for point in curve_result.points),
                # Outcomes are observed even when an interval set is missing.
                # Repeated levels are cases, not independent source observations.
                "observed": int(y_arr.size * len(level_values)),
                "observed_outcomes": int(y_arr.size),
                "observed_pairs": sum(len(interval_set) for interval_set in interval_sets),
                "missing_outcomes": 0,
                "missing": int(y_arr.size * len(level_values))
                - sum(point.n_observations for point in curve_result.points),
                "unit": "requested_outcome_level",
                "row_identity_basis": "ordered_position_only",
            },
        },
    )
    report._continuous_inputs = _ContinuousCalibrationInputs(
        y_true=y_arr.tolist(),
        levels=list(level_values),
        intervals=interval_sets,
        predictive_samples=None if sample_arr is None else sample_arr.tolist(),
        uncertainty=None if uncertainty is None else dict(uncertainty),
        strict=strict,
    ).model_dump(mode="json")
    report._continuous_projection_digest = report._projection_digest()
    return report


class _ContinuousCalibrationInputs(BaseModel):
    """Exact ordered inputs to the existing continuous evaluator, not a source attestation."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    protocol: Literal["continuous-calibration-pairs-v1"] = "continuous-calibration-pairs-v1"
    y_true: list[float]
    levels: list[float]
    intervals: list[list[tuple[float, float]]]
    predictive_samples: list[list[float]] | None = None
    uncertainty: dict[str, Any] | None = None
    strict: bool = True


class _ContinuousCalibrationArtifact(BaseModel):
    """Content-bound descriptive report and receipt; source authority is unavailable."""

    model_config = ConfigDict(extra="forbid")
    protocol: Literal["continuous-calibration-diagnostics-v1"] = (
        "continuous-calibration-diagnostics-v1"
    )
    pairs_ref: dict[str, Any]
    report: dict[str, Any]
    receipt: dict[str, Any]
    source_binding: dict[str, Any] | None = None
    source_binding_basis: Literal["consumer_asserted", "not_established"]
    authority_purpose: Literal["descriptive_predictive_calibration"] = (
        "descriptive_predictive_calibration"
    )
    gate_eligible: Literal[False] = False


def _bootstrap_replay_seed(uncertainty: Mapping[str, Any] | None, *, required: bool) -> int | None:
    """Admit one exact deterministic seed before any bootstrap callback."""
    if not uncertainty or int(uncertainty.get("bootstrap", 0) or 0) <= 0:
        return None
    if "seed" not in uncertainty:
        if required:
            raise ValueError("Persisted bootstrap calibration requires an explicit replay seed")
        return None
    seed = uncertainty["seed"]
    if type(seed) is not int or seed < 0:
        raise ValueError("Bootstrap replay seed must be a nonnegative integer, not bool or null")
    return seed


def persist_continuous_evaluation(
    store: core_artifacts.ArtifactStore,
    report: CalibrationDiagnosticsReport,
    *,
    source_binding: Mapping[str, Any] | None = None,
) -> core_artifacts.ArtifactRef:
    """Persist exact ordered pairs and a reproducible report on the configured CAS.

    Source/split/horizon/time declarations are retained as caller assertions and
    never authorize a production claim. Bootstrap replay requires an explicit seed.
    """
    from polisyos.core import artifacts as core_artifacts
    from polisyos.core import canon as core_canon

    if report.task != "continuous" or report._continuous_inputs is None:
        raise ValueError("Continuous calibration inputs must be rebound before persistence")
    inputs = _ContinuousCalibrationInputs.model_validate(report._continuous_inputs)
    _bootstrap_replay_seed(inputs.uncertainty, required=True)
    reproduced = _reproduce_continuous(inputs)
    if reproduced.model_dump(mode="json") != report.model_dump(mode="json"):
        raise ValueError("Continuous calibration report does not reproduce from its pairs")
    pairs = store.put_json(
        inputs.model_dump(mode="json"),
        core_artifacts.ArtifactWriteOptions(
            kind="continuous_calibration_pairs",
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(name="continuous_calibration_pairs", version="1.0"),
        ),
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    artifact = _ContinuousCalibrationArtifact(
        pairs_ref=pairs.model_dump(mode="json"),
        report=report.model_dump(mode="json"),
        receipt=reproduced.to_truthfulness_receipt().model_dump(mode="json"),
        source_binding=None if source_binding is None else dict(source_binding),
        source_binding_basis="not_established" if source_binding is None else "consumer_asserted",
    )
    return store.put_json(
        artifact.model_dump(mode="json"),
        core_artifacts.ArtifactWriteOptions(
            kind="continuous_calibration_diagnostics",
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(
                name="continuous_calibration_diagnostics", version="1.0"
            ),
        ),
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )


def load_continuous_evaluation(
    store: core_artifacts.ArtifactStore, ref: core_artifacts.ArtifactRef
) -> CalibrationDiagnosticsReport:
    """Reopen both artifacts and recompute the full report/receipt before consumption."""
    from polisyos.core import artifacts as core_artifacts

    artifact = _ContinuousCalibrationArtifact.model_validate(
        _load_continuous_artifact(store, ref, "continuous_calibration_diagnostics")
    )
    pairs_ref = core_artifacts.ArtifactRef.model_validate(artifact.pairs_ref)
    inputs = _ContinuousCalibrationInputs.model_validate(
        _load_continuous_artifact(store, pairs_ref, "continuous_calibration_pairs")
    )
    _bootstrap_replay_seed(inputs.uncertainty, required=True)
    reproduced = _reproduce_continuous(inputs)
    if reproduced.model_dump(mode="json") != artifact.report:
        raise ValueError("Persisted continuous calibration report does not reproduce")
    if reproduced.to_truthfulness_receipt().model_dump(mode="json") != artifact.receipt:
        raise ValueError("Persisted continuous calibration receipt does not reproduce")
    reproduced._continuous_pairs_ref = str(pairs_ref.artifact_id)
    return reproduced


def _reproduce_continuous(inputs: _ContinuousCalibrationInputs) -> CalibrationDiagnosticsReport:
    return evaluate_continuous(
        y_true=inputs.y_true,
        intervals=inputs.intervals,
        levels=inputs.levels,
        predictive_samples=inputs.predictive_samples,
        uncertainty=inputs.uncertainty,
        strict=inputs.strict,
    )


def _load_continuous_artifact(
    store: core_artifacts.ArtifactStore, ref: core_artifacts.ArtifactRef, kind: str
) -> Any:
    from polisyos.core import canon as core_canon

    manifest = store.get_manifest(ref)
    if (
        manifest.kind != kind
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != kind
        or manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("Continuous calibration artifact kind/schema mismatch")
    if not store.verify(ref).ok:
        raise ValueError("Continuous calibration artifact integrity failed")
    return core_canon.from_canonical_bytes(store.get_bytes(ref))


def _prepare_predictive_samples(
    predictive_samples: Sequence[Sequence[float]] | None,
    *,
    n_obs: int,
) -> np.ndarray | None:
    if predictive_samples is None:
        return None
    sample_arr = np.asarray(predictive_samples, dtype=float)
    if sample_arr.ndim != 2:
        raise ValueError("predictive_samples must be a 2D array with shape (n_obs, n_draws)")
    if sample_arr.shape[0] != n_obs:
        raise ValueError("predictive_samples row count must match y_true length")
    if not np.all(np.isfinite(sample_arr)):
        raise ValueError("predictive_samples contains non-finite values")
    return sample_arr


def _prepare_interval_sets(
    *,
    y_true: np.ndarray,
    intervals: Mapping[float, Sequence[tuple[float, float]]]
    | Sequence[Sequence[tuple[float, float]]]
    | None,
    predictive_samples: np.ndarray | None,
    levels: Sequence[float] | None,
    strict: bool,
) -> tuple[tuple[float, ...], list[list[tuple[float, float]]]]:
    if intervals is None and predictive_samples is None:
        raise ValueError("continuous diagnostics require intervals or predictive_samples")
    if intervals is None:
        level_values = tuple(
            float(level) for level in (_DEFAULT_LEVELS if levels is None else levels)
        )
        interval_sets = None
    elif isinstance(intervals, Mapping):
        ordered = sorted((float(level), interval_set) for level, interval_set in intervals.items())
        level_values = tuple(level for level, _ in ordered)
        interval_sets = [list(interval_set) for _, interval_set in ordered]
        if levels is not None:
            requested_levels = tuple(float(level) for level in levels)
            if len(requested_levels) != len(level_values) or set(requested_levels) != set(
                level_values
            ):
                raise ValueError("levels must match interval mapping keys")
    else:
        if levels is None:
            raise ValueError("levels are required when intervals are passed as a sequence")
        level_values = tuple(float(level) for level in levels)
        interval_sets = [list(interval_set) for interval_set in intervals]

    for level in level_values:
        if not math.isfinite(level) or level <= 0.0 or level >= 1.0:
            raise ValueError("continuous interval levels must be finite and stay inside (0, 1)")
    if interval_sets is None:
        interval_sets = _intervals_from_samples(predictive_samples, level_values)
    if len(level_values) != len(interval_sets):
        raise ValueError("levels and interval sets must have identical length")
    for interval_set in interval_sets:
        if interval_set and len(interval_set) != y_true.size:
            raise ValueError("each interval set must align with y_true length")
        for lower, upper in interval_set:
            if not math.isfinite(float(lower)) or not math.isfinite(float(upper)):
                raise ValueError("interval bounds must be finite")
            if strict and float(lower) > float(upper):
                raise ValueError("interval lower bound must not exceed upper bound")
    return level_values, interval_sets


def _intervals_from_samples(
    predictive_samples: np.ndarray | None,
    levels: Sequence[float],
) -> list[list[tuple[float, float]]]:
    if predictive_samples is None:
        raise ValueError("predictive_samples are required to synthesize intervals")
    interval_sets: list[list[tuple[float, float]]] = []
    for level in levels:
        alpha = (1.0 - float(level)) / 2.0
        lower = np.quantile(predictive_samples, alpha, axis=1)
        upper = np.quantile(predictive_samples, 1.0 - alpha, axis=1)
        interval_sets.append([(float(lo), float(hi)) for lo, hi in zip(lower, upper, strict=True)])
    return interval_sets


def _attach_interval_bootstrap(
    *,
    y_true: np.ndarray,
    levels: Sequence[float],
    interval_sets: Sequence[Sequence[tuple[float, float]]],
    bootstrap_reps: int,
    confidence_level: float,
    rng_seed: int | None,
    original_bins: Sequence[CalibrationCurveBin],
) -> tuple[list[CalibrationCurveBin], dict[str, CalibrationMetricInterval]]:
    rng = np.random.default_rng(rng_seed)
    alpha = (1.0 - confidence_level) / 2.0
    n_obs = y_true.size
    coverage_samples = [[] for _ in range(len(levels))]
    metric_samples = {"ece": [], "mce": [], "rmsce": []}

    for _ in range(bootstrap_reps):
        sample_idx = rng.integers(0, n_obs, size=n_obs)
        sampled_true = y_true[sample_idx]
        sampled_interval_sets = [
            [interval_set[index] for index in sample_idx] for interval_set in interval_sets
        ]
        result = compute_calibration_curve(
            y_true=sampled_true.tolist(),
            intervals=sampled_interval_sets,
            levels=list(levels),
        )
        deviations = np.asarray(
            [point.empirical_coverage - point.nominal_level for point in result.points],
            dtype=float,
        )
        if result.ece is None or result.max_ce is None:
            raise ValueError("bootstrap requires evaluated interval-coverage comparisons")
        metric_samples["ece"].append(float(result.ece))
        metric_samples["mce"].append(float(result.max_ce))
        metric_samples["rmsce"].append(
            float(math.sqrt(np.mean(deviations**2))) if deviations.size else 0.0
        )
        for index, point in enumerate(result.points):
            coverage_samples[index].append(float(point.empirical_coverage))

    updated_bins: list[CalibrationCurveBin] = []
    for index, item in enumerate(original_bins):
        sample_arr = np.asarray(coverage_samples[index], dtype=float)
        if sample_arr.size == 0:
            updated_bins.append(item)
            continue
        updated_bins.append(
            item.model_copy(
                update={
                    "ci_low": float(np.quantile(sample_arr, alpha)),
                    "ci_high": float(np.quantile(sample_arr, 1.0 - alpha)),
                }
            )
        )

    metric_intervals = {
        metric_name: CalibrationMetricInterval(
            low=float(np.quantile(np.asarray(samples, dtype=float), alpha)),
            high=float(np.quantile(np.asarray(samples, dtype=float), 1.0 - alpha)),
        )
        for metric_name, samples in metric_samples.items()
        if samples
    }
    return updated_bins, metric_intervals


def _pit_histogram(pit: np.ndarray, *, n_bins: int = 10) -> dict[str, Any]:
    counts, edges = np.histogram(pit, bins=np.linspace(0.0, 1.0, n_bins + 1))
    density = counts / max(np.sum(counts), 1)
    return {
        "counts": counts.astype(int).tolist(),
        "density": density.astype(float).tolist(),
        "edges": edges.astype(float).tolist(),
    }


def _interval_width_summary(
    levels: Sequence[float],
    interval_sets: Sequence[Sequence[tuple[float, float]]],
) -> dict[str, float]:
    summary: dict[str, float] = {}
    for level, interval_set in zip(levels, interval_sets, strict=True):
        widths = [float(upper - lower) for lower, upper in interval_set]
        summary[str(level)] = float(np.mean(np.asarray(widths, dtype=float))) if widths else 0.0
    return summary


def _continuous_ence(
    *,
    y_true: np.ndarray,
    predictive_samples: np.ndarray,
    n_bins: int = 10,
) -> float:
    predictive_std = np.std(predictive_samples, axis=1, ddof=0)
    predictive_mean = np.mean(predictive_samples, axis=1)
    residual = y_true - predictive_mean
    order = np.argsort(predictive_std, kind="mergesort")
    std_sorted = predictive_std[order]
    residual_sorted = residual[order]
    errors: list[float] = []
    for std_chunk, residual_chunk in zip(
        np.array_split(std_sorted, n_bins),
        np.array_split(residual_sorted, n_bins),
        strict=True,
    ):
        if std_chunk.size == 0:
            continue
        mean_std = float(np.mean(std_chunk))
        rmse = float(math.sqrt(np.mean(residual_chunk**2)))
        if mean_std <= _EPSILON:
            continue
        errors.append(abs(mean_std - rmse) / mean_std)
    return 0.0 if not errors else float(np.mean(np.asarray(errors, dtype=float)))


def _recommended_action(deviations: np.ndarray) -> str | None:
    if deviations.size == 0:
        return None
    mean_gap = float(np.mean(deviations))
    if mean_gap < -0.03:
        return "widen_prediction_intervals"
    if mean_gap > 0.03:
        return "narrow_prediction_intervals"
    return None


__all__ = [
    "evaluate_continuous",
]
