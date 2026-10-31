"""Continuous predictive calibration diagnostics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from polisyos.calibration.curve import compute_calibration_curve
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    ArtifactWriteOptions,
    CoreJSONArtifactBoundedMemberReader,
    CoreJsonReadLimits,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    read_core_json_artifact_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.analytics.calibration_diagnostics import (
    CalibrationCurveBin,
    CalibrationDiagnosticIssue,
    CalibrationDiagnosticsReport,
    CalibrationMetricInterval,
    CalibrationMetrics,
)
from polisyos.ir.analytics.query_validation_report import ValidationSeverity

_EPSILON = 1e-12
_DEFAULT_LEVELS = (0.5, 0.8, 0.9)
_INPUT_ROLE = "continuous_evaluation_inputs"
_CONTINUOUS_READ_LIMITS = CoreJsonReadLimits(
    max_bytes=16 * 1024 * 1024,
    max_depth=64,
    max_elements=2_000_000,
    max_manifest_bytes=1024 * 1024,
)
_CONTINUOUS_CANON = CanonSpec(forbid_floats=False, exclude_none=False)
_CONTINUOUS_BOOTSTRAP_PAIR_BUDGET = 1_000_000


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

    y_arr = np.asarray(y_true, dtype=float).reshape(-1)
    if y_arr.size == 0:
        raise ValueError("y_true must not be empty for continuous diagnostics")
    if not np.all(np.isfinite(y_arr)):
        raise ValueError("y_true contains non-finite values")

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
            rng_seed=None if "seed" not in uncertainty else int(uncertainty["seed"]),
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

    return CalibrationDiagnosticsReport(
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
                "requested_levels": list(level_values),
                "evaluated_levels": [point.nominal_level for point in curve_result.points],
                "skipped_levels": [
                    level
                    for level, interval_set in zip(level_values, interval_sets, strict=True)
                    if not interval_set
                ],
            },
        },
    )


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
    if len(set(level_values)) != len(level_values):
        raise ValueError("continuous interval levels must be unique")
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


class _ContinuousBootstrapPlan(BaseModel):
    """Replayable options for the existing continuous bootstrap calculation."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    bootstrap: StrictInt = Field(default=0, ge=0)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    seed: StrictInt | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_replay_seed(self) -> _ContinuousBootstrapPlan:
        """Refuse an unreplayable bootstrap before it can sample."""
        if self.bootstrap > 0 and self.seed is None:
            raise ValueError("persisted continuous bootstrap requires an explicit replay seed")
        return self


class _ContinuousEvaluationInputs(BaseModel):
    """Exact ordered numeric inputs, without a claim about their external source."""

    ARTIFACT_KIND: ClassVar[str] = "calibration.continuous_inputs"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.calibration.continuous_inputs"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: Literal["1.0"] = "1.0"
    y_true: tuple[float, ...] = Field(min_length=1)
    levels: tuple[float, ...]
    interval_sets: tuple[tuple[tuple[float, float], ...], ...]
    predictive_samples: tuple[tuple[float, ...], ...] | None = None
    uncertainty: _ContinuousBootstrapPlan | None = None
    strict: bool = True

    @model_validator(mode="after")
    def require_bounded_bootstrap_replay(self) -> _ContinuousEvaluationInputs:
        """Bound expanded numerical work as well as retained input bytes."""
        repetitions = 0 if self.uncertainty is None else self.uncertainty.bootstrap
        pair_evaluations = repetitions * len(self.y_true) * max(1, len(self.levels))
        if pair_evaluations > _CONTINUOUS_BOOTSTRAP_PAIR_BUDGET:
            raise ValueError("persisted continuous bootstrap exceeds replay pair budget")
        return self


class _ContinuousEvaluationArtifact(BaseModel):
    """Descriptive report bound to the exact inputs which must reproduce it."""

    ARTIFACT_KIND: ClassVar[str] = "calibration.continuous_evaluation"
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.calibration.continuous_evaluation"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    inputs_ref: ArtifactRef
    report: CalibrationDiagnosticsReport
    replay_semantics: Literal["current_evaluator_numeric_recomputation"] = (
        "current_evaluator_numeric_recomputation"
    )
    measurement_source_assurance: Literal["not_established"] = "not_established"
    authority_purpose: Literal["descriptive_predictive_calibration"] = (
        "descriptive_predictive_calibration"
    )
    gate_eligible: Literal[False] = False


def _continuous_input_snapshot(
    *,
    y_true: Sequence[float],
    intervals: Mapping[float, Sequence[tuple[float, float]]]
    | Sequence[Sequence[tuple[float, float]]]
    | None,
    predictive_samples: Sequence[Sequence[float]] | None,
    levels: Sequence[float] | None,
    uncertainty: Mapping[str, Any] | None,
    strict: bool,
) -> _ContinuousEvaluationInputs:
    """Snapshot the effective evaluator inputs before any bootstrap callback."""
    y_arr = np.asarray(y_true, dtype=float)
    if y_arr.ndim != 1 or y_arr.size == 0:
        raise ValueError("persisted y_true must be a nonempty one-dimensional sequence")
    if not np.all(np.isfinite(y_arr)):
        raise ValueError("y_true contains non-finite values")
    samples = _prepare_predictive_samples(predictive_samples, n_obs=y_arr.size)
    level_values, interval_sets = _prepare_interval_sets(
        y_true=y_arr,
        intervals=intervals,
        predictive_samples=samples,
        levels=levels,
        strict=strict,
    )
    bootstrap = (
        None if uncertainty is None else _ContinuousBootstrapPlan.model_validate(dict(uncertainty))
    )
    return _ContinuousEvaluationInputs(
        y_true=tuple(y_arr.tolist()),
        levels=level_values,
        interval_sets=tuple(tuple(pair for pair in interval_set) for interval_set in interval_sets),
        predictive_samples=None
        if samples is None
        else tuple(tuple(row) for row in samples.tolist()),
        uncertainty=bootstrap,
        strict=strict,
    )


def _reproduce_continuous(inputs: _ContinuousEvaluationInputs) -> CalibrationDiagnosticsReport:
    """Run the canonical numerical producer on the retained ordered values."""
    return evaluate_continuous(
        y_true=inputs.y_true,
        intervals=inputs.interval_sets,
        predictive_samples=inputs.predictive_samples,
        levels=inputs.levels,
        uncertainty=(
            None if inputs.uncertainty is None else inputs.uncertainty.model_dump(mode="python")
        ),
        strict=inputs.strict,
    )


def persist_continuous_evaluation(
    store: ArtifactStore,
    *,
    y_true: Sequence[float],
    intervals: Mapping[float, Sequence[tuple[float, float]]]
    | Sequence[Sequence[tuple[float, float]]]
    | None = None,
    predictive_samples: Sequence[Sequence[float]] | None = None,
    levels: Sequence[float] | None = None,
    uncertainty: Mapping[str, Any] | None = None,
    strict: bool = True,
) -> ArtifactRef:
    """Evaluate and persist ordered inputs and their descriptive calibration report.

    The returned selected reference carries one exact selected input edge. A
    fresh reader recomputes the report rather than trusting summary fields.
    Caller-provided arrays establish no production source, estimand, issuer,
    currentness or causal authority. Existing report admission stays unverified.

    Args:
        store: Existing Core CAS writer.
        y_true: Ordered finite scalar observations represented by the evaluator.
        intervals: Ordered interval sets, optionally indexed by nominal level.
        predictive_samples: Optional draws used by the actual PIT/ENCE producer.
        levels: Nominal levels interpreted by the existing evaluator.
        uncertainty: Bootstrap options; a positive count requires an explicit seed.
        strict: Preserve the evaluator's bound-order validation setting.

    Returns:
        Exact selected reference to the persisted report and its input binding.

    Raises:
        ValueError: Inputs or deterministic replay options are invalid.
    """
    inputs = _continuous_input_snapshot(
        y_true=y_true,
        intervals=intervals,
        predictive_samples=predictive_samples,
        levels=levels,
        uncertainty=uncertainty,
        strict=strict,
    )
    report = _reproduce_continuous(inputs)
    inputs_ref = store.put_json(
        inputs.model_dump(mode="python"),
        ArtifactWriteOptions(
            kind=inputs.ARTIFACT_KIND,
            media_type=inputs.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=inputs.ARTIFACT_SCHEMA_NAME, version=inputs.schema_version),
        ),
        canon_spec=_CONTINUOUS_CANON,
        return_selected_profile=True,
    )
    if not inputs_ref.manifest_profile_sha256:
        raise ValueError("continuous evaluation writer did not return a selected input profile")
    artifact = _ContinuousEvaluationArtifact(inputs_ref=inputs_ref, report=report)
    ref = store.put_json(
        artifact.model_dump(mode="python"),
        ArtifactWriteOptions(
            kind=artifact.ARTIFACT_KIND,
            media_type=artifact.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=artifact.ARTIFACT_SCHEMA_NAME, version=artifact.schema_version),
            inputs=[input_ref_from_artifact_ref(inputs_ref, role=_INPUT_ROLE)],
        ),
        canon_spec=_CONTINUOUS_CANON,
        return_selected_profile=True,
    )
    if not ref.manifest_profile_sha256:
        raise ValueError("continuous evaluation writer did not return a selected report profile")
    return ref


def _require_reproduced_continuous_report(
    stored: CalibrationDiagnosticsReport, reproduced: CalibrationDiagnosticsReport
) -> None:
    """Reconcile the complete typed result, not merely its hash or nominal level."""
    if to_canonical_bytes(
        stored.model_dump(mode="python"), _CONTINUOUS_CANON
    ) != to_canonical_bytes(reproduced.model_dump(mode="python"), _CONTINUOUS_CANON):
        raise ValueError("persisted continuous calibration report does not reproduce")


def load_continuous_evaluation(
    store: CoreJSONArtifactBoundedMemberReader,
    ref: ArtifactRef,
    *,
    expected_inputs_ref: ArtifactRef | None = None,
    limits: CoreJsonReadLimits = _CONTINUOUS_READ_LIMITS,
) -> CalibrationDiagnosticsReport:
    """Reopen exact selected inputs and recompute a persisted numerical report.

    Args:
        store: Existing bounded Core CAS reader, including its normal scope checks.
        ref: Selected report reference returned by the producer.
        expected_inputs_ref: Optional independently selected input expectation.
        limits: Explicit bounds applied to both manifest and payload reads.

    Returns:
        Freshly recomputed diagnostics, retaining unverified source admission.

    Raises:
        ValueError: Kind/schema, selected input edge, expected source or report differs.
    """
    report_read = read_core_json_artifact_bounded(store, ref, limits=limits)
    artifact = validate_core_model_bounded_read(_ContinuousEvaluationArtifact, report_read)
    if not artifact.inputs_ref.manifest_profile_sha256:
        raise ValueError("continuous evaluation requires a selected input profile")
    expected_edge = input_ref_from_artifact_ref(artifact.inputs_ref, role=_INPUT_ROLE)
    if report_read.manifest.inputs != [expected_edge]:
        raise ValueError("continuous evaluation input manifest edge mismatch")
    if expected_inputs_ref is not None and artifact_ref_identity_key(
        expected_inputs_ref
    ) != artifact_ref_identity_key(artifact.inputs_ref):
        raise ValueError("continuous evaluation expected input profile mismatch")
    inputs_read = read_core_json_artifact_bounded(store, artifact.inputs_ref, limits=limits)
    inputs = validate_core_model_bounded_read(_ContinuousEvaluationInputs, inputs_read)
    reproduced = _reproduce_continuous(inputs)
    _require_reproduced_continuous_report(artifact.report, reproduced)
    return reproduced


__all__ = [
    "evaluate_continuous",
    "load_continuous_evaluation",
    "persist_continuous_evaluation",
]
