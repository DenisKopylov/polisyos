"""Binary probabilistic calibration diagnostics."""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import Any, Mapping, Sequence

import numpy as np

from polisyos.ir.analytics.calibration_diagnostics import (
    CalibrationCurveBin,
    CalibrationDiagnosticIssue,
    CalibrationDiagnosticsReport,
    CalibrationMetricInterval,
    CalibrationMetrics,
    CalibrationTestResult,
)
from polisyos.ir.analytics.query_validation_report import ValidationSeverity

try:  # pragma: no cover - exercised when scipy is available
    from scipy.stats import chi2 as _chi2
except Exception:  # pragma: no cover - fallback path
    _chi2 = None

_EPSILON = 1e-12


@dataclass(frozen=True)
class _CurveSpec:
    binning: str
    n_bins: int

    @property
    def curve_id(self) -> str:
        return f"{self.binning}_{self.n_bins}"


def evaluate_binary(
    *,
    y_true: Sequence[float],
    y_prob: Sequence[float],
    predicted_uncertainties: Sequence[float] | None = None,
    metrics: Sequence[str] | None = None,
    curves: Mapping[str, Any] | None = None,
    tests: Sequence[str] | None = None,
    uncertainty: Mapping[str, Any] | None = None,
    groups: Mapping[str, Sequence[str]] | None = None,
    strict: bool = True,
    repair_strategy: str | None = None,
) -> CalibrationDiagnosticsReport:
    """Evaluate binary probabilistic calibration with governance-friendly outputs."""

    metric_ids = tuple(
        metrics or ("brier", "log_loss", "ece", "mce", "rmsce", "ence", "brier_decomposition")
    )
    curve_specs = _normalize_curve_specs(curves)
    test_ids = tuple(tests or ())
    bootstrap_reps = _bootstrap_repetitions(uncertainty)
    confidence_level = _confidence_level(uncertainty)
    rng_seed = _bootstrap_seed(uncertainty)

    y_arr, p_arr, issues, warning_messages, repair_log = _prepare_binary_inputs(
        y_true=y_true,
        y_prob=y_prob,
        strict=strict,
        repair_strategy=repair_strategy,
    )
    n_obs = int(y_arr.size)
    event_count = int(np.sum(y_arr))
    prevalence = float(np.mean(y_arr)) if n_obs else None
    mean_predicted = float(np.mean(p_arr)) if n_obs else None
    mean_observed = float(np.mean(y_arr)) if n_obs else None

    if n_obs == 0:
        warnings = warning_messages + ("No observations supplied for calibration diagnostics.",)
        return CalibrationDiagnosticsReport(
            task="binary",
            target_type="probability",
            metrics=CalibrationMetrics(n_obs=0, event_count=0),
            issues=tuple(issues),
            warnings=warnings,
            metadata={"repair_log": repair_log},
        )

    curves_map = {
        spec.curve_id: _build_curve(p_arr, y_arr, spec)
        for spec in curve_specs
    }
    primary_spec = _select_primary_curve(curve_specs)
    primary_bins = curves_map[primary_spec.curve_id]
    primary_metric_values = _curve_error_metrics(primary_bins, n_obs)

    brier = float(np.mean((p_arr - y_arr) ** 2))
    log_loss = float(np.mean(-y_arr * np.log(np.clip(p_arr, _EPSILON, 1.0 - _EPSILON)) - (1.0 - y_arr) * np.log(np.clip(1.0 - p_arr, _EPSILON, 1.0 - _EPSILON))))
    uncertainties = _prepare_uncertainties(predicted_uncertainties, p_arr)
    ence = _compute_ence(p_arr, y_arr, uncertainties)
    rel, res, unc = _brier_decomposition(primary_bins, prevalence)

    metric_intervals: dict[str, CalibrationMetricInterval] = {}
    if bootstrap_reps > 0:
        curves_map, metric_intervals = _attach_bootstrap_intervals(
            y_true=y_arr,
            y_prob=p_arr,
            curve_specs=curve_specs,
            primary_curve=primary_spec,
            bootstrap_reps=bootstrap_reps,
            confidence_level=confidence_level,
            rng_seed=rng_seed,
            original_curves=curves_map,
        )

    metrics_payload = CalibrationMetrics(
        n_obs=n_obs,
        event_count=event_count,
        prevalence=prevalence,
        mean_predicted_score=mean_predicted,
        mean_observed_rate=mean_observed,
        brier=brier if "brier" in metric_ids else None,
        log_loss=log_loss if "log_loss" in metric_ids else None,
        ece=primary_metric_values["ece"] if "ece" in metric_ids else None,
        mce=primary_metric_values["mce"] if "mce" in metric_ids else None,
        rmsce=primary_metric_values["rmsce"] if "rmsce" in metric_ids else None,
        ence=ence if "ence" in metric_ids or metrics is None else None,
        rel=rel if "brier_decomposition" in metric_ids else None,
        res=res if "brier_decomposition" in metric_ids else None,
        unc=unc if "brier_decomposition" in metric_ids else None,
        intervals=metric_intervals,
    )

    test_results = _run_tests(
        y_true=y_arr,
        y_prob=p_arr,
        test_ids=test_ids,
    )
    issues.extend(_sample_size_issues(n_obs=n_obs, event_count=event_count, curve_specs=curve_specs))
    issues.extend(_degeneracy_issues(p_arr))
    recommended_action = _recommended_action(
        ece=metrics_payload.ece,
        n_obs=n_obs,
        tests=test_results,
    )
    per_group = _group_metrics(
        y_true=y_arr,
        y_prob=p_arr,
        groups=groups,
        primary_curve=primary_spec,
    )

    return CalibrationDiagnosticsReport(
        task="binary",
        target_type="probability",
        metrics=metrics_payload,
        curves={key: tuple(value) for key, value in curves_map.items()},
        tests=tuple(test_results),
        issues=tuple(issues),
        warnings=warning_messages,
        primary_curve=primary_spec.curve_id,
        per_group=per_group,
        recommended_action=recommended_action,
        metadata={
            "curve_specs": [spec.curve_id for spec in curve_specs],
            "bootstrap_repetitions": bootstrap_reps,
            "confidence_level": confidence_level,
            "repair_log": repair_log,
        },
    )


def _prepare_binary_inputs(
    *,
    y_true: Sequence[float],
    y_prob: Sequence[float],
    strict: bool,
    repair_strategy: str | None,
) -> tuple[np.ndarray, np.ndarray, list[CalibrationDiagnosticIssue], tuple[str, ...], dict[str, Any]]:
    if len(y_true) != len(y_prob):
        raise ValueError("y_true and y_prob must have identical length")

    y_arr = np.asarray(y_true, dtype=float)
    p_arr = np.asarray(y_prob, dtype=float)
    issues: list[CalibrationDiagnosticIssue] = []
    warnings: list[str] = []
    repair_log: dict[str, Any] = {}

    if y_arr.ndim != 1 or p_arr.ndim != 1:
        raise ValueError("binary calibration expects one-dimensional y_true and y_prob")
    if not np.all(np.isfinite(y_arr)):
        raise ValueError("y_true contains non-finite values")
    if not np.all(np.isfinite(p_arr)):
        raise ValueError("y_prob contains non-finite values")
    if not np.all((y_arr == 0.0) | (y_arr == 1.0)):
        raise ValueError("y_true must contain only binary labels 0/1")

    invalid_mask = (p_arr < 0.0) | (p_arr > 1.0)
    if np.any(invalid_mask):
        if strict or repair_strategy not in {"clip", "epsilon_shrink"}:
            raise ValueError("y_prob must stay inside [0, 1] when strict=True")
        clipped = np.clip(p_arr, 0.0, 1.0)
        if repair_strategy == "epsilon_shrink":
            clipped = np.clip(clipped, 1e-6, 1.0 - 1e-6)
        repair_log["probability_repairs"] = int(np.sum(invalid_mask))
        repair_log["repair_strategy"] = repair_strategy
        p_arr = clipped
        issues.append(
            CalibrationDiagnosticIssue(
                code="CALIB_REPAIRED_PROBABILITIES",
                message="Input probabilities were repaired before evaluation.",
                severity=ValidationSeverity.INFO,
                path="calibration.inputs.y_prob",
                expected="all probabilities inside [0, 1]",
                actual={"repaired_count": int(np.sum(invalid_mask)), "strategy": repair_strategy},
            )
        )
        warnings.append("Probabilities were repaired before diagnostics.")

    return y_arr, p_arr, issues, tuple(warnings), repair_log


def _normalize_curve_specs(curves: Mapping[str, Any] | None) -> tuple[_CurveSpec, ...]:
    if curves is None:
        return (_CurveSpec("uniform", 10),)

    raw_binning = curves.get("binning", ["uniform"])
    raw_bins = curves.get("n_bins", [10])
    binning_values = [raw_binning] if isinstance(raw_binning, str) else list(raw_binning)
    n_bins_values = [raw_bins] if isinstance(raw_bins, int) else list(raw_bins)
    specs: list[_CurveSpec] = []
    for binning, n_bins in product(binning_values, n_bins_values):
        normalized = str(binning).strip().lower().replace("equal_mass", "quantile")
        if normalized not in {"uniform", "quantile"}:
            raise ValueError(f"Unsupported calibration binning strategy: {binning}")
        candidate_bins = int(n_bins)
        if candidate_bins <= 0:
            raise ValueError("n_bins must be positive")
        specs.append(_CurveSpec(normalized, candidate_bins))
    if not specs:
        specs.append(_CurveSpec("uniform", 10))
    return tuple(specs)


def _select_primary_curve(curve_specs: Sequence[_CurveSpec]) -> _CurveSpec:
    for spec in curve_specs:
        if spec.binning == "quantile":
            return spec
    return curve_specs[0]


def _build_curve(
    y_prob: np.ndarray,
    y_true: np.ndarray,
    spec: _CurveSpec,
) -> list[CalibrationCurveBin]:
    if spec.binning == "uniform":
        return _build_uniform_curve(y_prob, y_true, spec.n_bins)
    return _build_quantile_curve(y_prob, y_true, spec.n_bins)


def _build_uniform_curve(
    y_prob: np.ndarray,
    y_true: np.ndarray,
    n_bins: int,
) -> list[CalibrationCurveBin]:
    bins: list[CalibrationCurveBin] = []
    for index in range(n_bins):
        lower = index / n_bins
        upper = (index + 1) / n_bins
        if index == n_bins - 1:
            mask = (y_prob >= lower) & (y_prob <= upper)
        else:
            mask = (y_prob >= lower) & (y_prob < upper)
        bins.append(_summarize_bin(lower, upper, y_prob[mask], y_true[mask]))
    return bins


def _build_quantile_curve(
    y_prob: np.ndarray,
    y_true: np.ndarray,
    n_bins: int,
) -> list[CalibrationCurveBin]:
    order = np.argsort(y_prob, kind="mergesort")
    ordered_prob = y_prob[order]
    ordered_true = y_true[order]
    bins: list[CalibrationCurveBin] = []
    for prob_chunk, true_chunk in zip(np.array_split(ordered_prob, n_bins), np.array_split(ordered_true, n_bins)):
        if prob_chunk.size == 0:
            bins.append(CalibrationCurveBin(lower=0.0, upper=0.0, count=0))
            continue
        bins.append(
            _summarize_bin(
                float(np.min(prob_chunk)),
                float(np.max(prob_chunk)),
                prob_chunk,
                true_chunk,
            )
        )
    return bins


def _summarize_bin(
    lower: float,
    upper: float,
    probs: np.ndarray,
    outcomes: np.ndarray,
) -> CalibrationCurveBin:
    if probs.size == 0:
        return CalibrationCurveBin(lower=lower, upper=upper, count=0)
    mean_predicted = float(np.mean(probs))
    mean_observed = float(np.mean(outcomes))
    return CalibrationCurveBin(
        lower=lower,
        upper=upper,
        count=int(probs.size),
        mean_predicted=mean_predicted,
        mean_observed=mean_observed,
        absolute_gap=abs(mean_predicted - mean_observed),
    )


def _curve_error_metrics(
    bins: Sequence[CalibrationCurveBin],
    n_obs: int,
) -> dict[str, float]:
    if n_obs <= 0:
        return {"ece": 0.0, "mce": 0.0, "rmsce": 0.0}
    gaps = np.asarray([item.absolute_gap or 0.0 for item in bins], dtype=float)
    weights = np.asarray([item.count / n_obs for item in bins], dtype=float)
    ece = float(np.sum(weights * gaps))
    mce = float(np.max(gaps, initial=0.0))
    rmsce = float(math.sqrt(np.sum(weights * (gaps ** 2))))
    return {"ece": ece, "mce": mce, "rmsce": rmsce}


def _brier_decomposition(
    bins: Sequence[CalibrationCurveBin],
    prevalence: float | None,
) -> tuple[float | None, float | None, float | None]:
    if prevalence is None:
        return None, None, None
    n_obs = sum(item.count for item in bins)
    if n_obs <= 0:
        return None, None, None
    rel = 0.0
    res = 0.0
    for item in bins:
        if item.count <= 0 or item.mean_predicted is None or item.mean_observed is None:
            continue
        weight = item.count / n_obs
        rel += weight * (item.mean_predicted - item.mean_observed) ** 2
        res += weight * (item.mean_observed - prevalence) ** 2
    unc = prevalence * (1.0 - prevalence)
    return float(rel), float(res), float(unc)


def _prepare_uncertainties(
    predicted_uncertainties: Sequence[float] | None,
    probabilities: np.ndarray,
) -> np.ndarray:
    if predicted_uncertainties is None:
        return np.sqrt(np.clip(probabilities * (1.0 - probabilities), 0.0, None))
    uncertainty_arr = np.asarray(predicted_uncertainties, dtype=float).reshape(-1)
    if uncertainty_arr.size != probabilities.size:
        raise ValueError("predicted_uncertainties must match y_prob length")
    if not np.all(np.isfinite(uncertainty_arr)):
        raise ValueError("predicted_uncertainties contains non-finite values")
    return np.clip(uncertainty_arr, 0.0, None)


def _compute_ence(
    probabilities: np.ndarray,
    outcomes: np.ndarray,
    uncertainties: np.ndarray,
    *,
    n_bins: int = 10,
) -> float:
    ranked = sorted(
        zip(uncertainties.tolist(), probabilities.tolist(), outcomes.tolist(), strict=True),
        key=lambda item: item[0],
    )
    if not ranked:
        return 0.0
    chunk_size = max(1, math.ceil(len(ranked) / n_bins))
    errors: list[float] = []
    for start in range(0, len(ranked), chunk_size):
        chunk = ranked[start : start + chunk_size]
        mean_uncertainty = sum(item[0] for item in chunk) / len(chunk)
        rmse = math.sqrt(sum((item[1] - item[2]) ** 2 for item in chunk) / len(chunk))
        if mean_uncertainty <= _EPSILON:
            continue
        errors.append(abs(mean_uncertainty - rmse) / mean_uncertainty)
    return 0.0 if not errors else float(sum(errors) / len(errors))


def _attach_bootstrap_intervals(
    *,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    curve_specs: Sequence[_CurveSpec],
    primary_curve: _CurveSpec,
    bootstrap_reps: int,
    confidence_level: float,
    rng_seed: int | None,
    original_curves: Mapping[str, list[CalibrationCurveBin]],
) -> tuple[dict[str, list[CalibrationCurveBin]], dict[str, CalibrationMetricInterval]]:
    rng = np.random.default_rng(rng_seed)
    alpha = (1.0 - confidence_level) / 2.0
    metric_samples: dict[str, list[float]] = {
        "brier": [],
        "log_loss": [],
        "ece": [],
        "mce": [],
        "rmsce": [],
    }
    curve_observed_samples = {
        spec.curve_id: [[] for _ in range(spec.n_bins)]
        for spec in curve_specs
    }

    n_obs = y_true.size
    for _ in range(bootstrap_reps):
        sample_idx = rng.integers(0, n_obs, size=n_obs)
        sampled_true = y_true[sample_idx]
        sampled_prob = y_prob[sample_idx]
        metric_samples["brier"].append(float(np.mean((sampled_prob - sampled_true) ** 2)))
        metric_samples["log_loss"].append(
            float(
                np.mean(
                    -sampled_true * np.log(np.clip(sampled_prob, _EPSILON, 1.0 - _EPSILON))
                    - (1.0 - sampled_true)
                    * np.log(np.clip(1.0 - sampled_prob, _EPSILON, 1.0 - _EPSILON))
                )
            )
        )
        for spec in curve_specs:
            bins = _build_curve(sampled_prob, sampled_true, spec)
            if spec.curve_id == primary_curve.curve_id:
                curve_metrics = _curve_error_metrics(bins, n_obs)
                for metric_name in ("ece", "mce", "rmsce"):
                    metric_samples[metric_name].append(curve_metrics[metric_name])
            for index, item in enumerate(bins):
                curve_observed_samples[spec.curve_id][index].append(
                    math.nan if item.mean_observed is None else item.mean_observed
                )

    updated_curves: dict[str, list[CalibrationCurveBin]] = {}
    for curve_id, bins in original_curves.items():
        updated_bins: list[CalibrationCurveBin] = []
        for index, item in enumerate(bins):
            samples = np.asarray(curve_observed_samples[curve_id][index], dtype=float)
            valid = samples[np.isfinite(samples)]
            if valid.size == 0:
                updated_bins.append(item)
                continue
            ci_low = float(np.quantile(valid, alpha))
            ci_high = float(np.quantile(valid, 1.0 - alpha))
            updated_bins.append(item.model_copy(update={"ci_low": ci_low, "ci_high": ci_high}))
        updated_curves[curve_id] = updated_bins

    metric_intervals: dict[str, CalibrationMetricInterval] = {}
    for metric_name, samples in metric_samples.items():
        sample_arr = np.asarray(samples, dtype=float)
        if sample_arr.size == 0:
            continue
        metric_intervals[metric_name] = CalibrationMetricInterval(
            low=float(np.quantile(sample_arr, alpha)),
            high=float(np.quantile(sample_arr, 1.0 - alpha)),
        )
    return updated_curves, metric_intervals


def _run_tests(
    *,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    test_ids: Sequence[str],
) -> list[CalibrationTestResult]:
    results: list[CalibrationTestResult] = []
    for test_id in test_ids:
        normalized = str(test_id).strip().lower()
        if normalized == "spiegelhalter":
            results.append(_spiegelhalter_test(y_true, y_prob))
        elif normalized in {"hosmer_lemeshow", "hosmer-lemeshow"}:
            results.append(_hosmer_lemeshow_test(y_true, y_prob))
        else:
            raise ValueError(f"Unsupported calibration test: {test_id}")
    return results


def _spiegelhalter_test(y_true: np.ndarray, y_prob: np.ndarray) -> CalibrationTestResult:
    residual = (y_true - y_prob) * (1.0 - 2.0 * y_prob)
    numerator = float(np.sum(residual))
    denominator = float(np.sqrt(np.sum(((1.0 - 2.0 * y_prob) ** 2) * y_prob * (1.0 - y_prob))))
    if denominator <= _EPSILON:
        return CalibrationTestResult(
            test_id="spiegelhalter",
            statistic=None,
            p_value=None,
            passed=None,
            assumptions_ok=False,
            notes=("degenerate_probabilities",),
        )
    z_score = numerator / denominator
    p_value = math.erfc(abs(z_score) / math.sqrt(2.0))
    return CalibrationTestResult(
        test_id="spiegelhalter",
        statistic=float(z_score),
        p_value=float(p_value),
        passed=bool(p_value >= 0.05),
        assumptions_ok=True,
    )


def _hosmer_lemeshow_test(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    n_groups: int = 10,
) -> CalibrationTestResult:
    grouped_prob = np.array_split(y_prob[np.argsort(y_prob, kind="mergesort")], n_groups)
    grouped_true = np.array_split(y_true[np.argsort(y_prob, kind="mergesort")], n_groups)
    statistic = 0.0
    notes: list[str] = []
    assumptions_ok = True

    usable_groups = 0
    for probabilities, outcomes in zip(grouped_prob, grouped_true):
        if probabilities.size == 0:
            continue
        observed = float(np.sum(outcomes))
        expected = float(np.sum(probabilities))
        n_group = int(probabilities.size)
        if expected <= 0.0 or expected >= n_group:
            assumptions_ok = False
            notes.append("degenerate_expected_count")
            continue
        non_events_expected = n_group - expected
        if expected < 5.0 or non_events_expected < 5.0:
            assumptions_ok = False
            notes.append("small_expected_count")
            continue
        statistic += ((observed - expected) ** 2) / expected
        statistic += (((n_group - observed) - non_events_expected) ** 2) / non_events_expected
        usable_groups += 1

    df = usable_groups - 2
    if not assumptions_ok or usable_groups < 3 or df <= 0:
        return CalibrationTestResult(
            test_id="hosmer_lemeshow",
            statistic=float(statistic) if usable_groups > 0 else None,
            p_value=None,
            df=max(df, 0),
            passed=None,
            assumptions_ok=False,
            notes=tuple(sorted(set(notes or ["insufficient_group_support"]))),
        )

    if _chi2 is None:  # pragma: no cover - exercised when scipy is unavailable
        return CalibrationTestResult(
            test_id="hosmer_lemeshow",
            statistic=float(statistic),
            p_value=None,
            df=df,
            passed=None,
            assumptions_ok=False,
            notes=("scipy_unavailable_for_chi_square_tail",),
        )

    p_value = float(_chi2.sf(statistic, df))
    return CalibrationTestResult(
        test_id="hosmer_lemeshow",
        statistic=float(statistic),
        p_value=p_value,
        df=df,
        passed=bool(p_value >= 0.05),
        assumptions_ok=True,
    )


def _sample_size_issues(
    *,
    n_obs: int,
    event_count: int,
    curve_specs: Sequence[_CurveSpec],
) -> list[CalibrationDiagnosticIssue]:
    issues: list[CalibrationDiagnosticIssue] = []
    max_bins = max(spec.n_bins for spec in curve_specs)
    if n_obs < max_bins * 20:
        issues.append(
            CalibrationDiagnosticIssue(
                code="CALIB_SPARSE_BINS_RISK",
                message="Sample size is small relative to the requested number of calibration bins.",
                severity=ValidationSeverity.WARNING,
                path="calibration.curves",
                expected={f"n_obs >= {max_bins * 20}": True},
                actual={"n_obs": n_obs, "max_bins": max_bins},
            )
        )
    if event_count < 100:
        issues.append(
            CalibrationDiagnosticIssue(
                code="CALIB_TOO_FEW_EVENTS",
                message="Event count is below the default governance-grade stability target.",
                severity=ValidationSeverity.WARNING,
                path="calibration.data.event_count",
                expected=">=100",
                actual=event_count,
            )
        )
    return issues


def _degeneracy_issues(y_prob: np.ndarray) -> list[CalibrationDiagnosticIssue]:
    if y_prob.size <= 1 or not np.allclose(y_prob, y_prob[0]):
        return []
    return [
        CalibrationDiagnosticIssue(
            code="CALIB_DEGENERATE_PREDICTIONS",
            message="All predicted probabilities are identical, so calibration curves are weakly informative.",
            severity=ValidationSeverity.WARNING,
            path="calibration.inputs.y_prob",
            expected="non-constant probability scores",
            actual=float(y_prob[0]),
        )
    ]


def _recommended_action(
    *,
    ece: float | None,
    n_obs: int,
    tests: Sequence[CalibrationTestResult],
) -> str | None:
    rejected = any(result.passed is False for result in tests)
    if ece is None:
        return None
    if ece <= 0.05 and not rejected:
        return None
    if n_obs < 1000:
        return "fit_sigmoid_or_temperature"
    return "fit_isotonic_or_temperature"


def _group_metrics(
    *,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    groups: Mapping[str, Sequence[str]] | None,
    primary_curve: _CurveSpec,
) -> dict[str, CalibrationMetrics]:
    if not groups:
        return {}
    result: dict[str, CalibrationMetrics] = {}
    for axis, labels in groups.items():
        if len(labels) != y_true.size:
            raise ValueError(f"groups[{axis!r}] must match y_true length")
        grouped_indices: dict[str, list[int]] = {}
        for index, label in enumerate(labels):
            grouped_indices.setdefault(str(label), []).append(index)
        for group_value, indices in sorted(grouped_indices.items()):
            group_true = y_true[indices]
            group_prob = y_prob[indices]
            bins = _build_curve(group_prob, group_true, primary_curve)
            metric_values = _curve_error_metrics(bins, len(indices))
            result[f"{axis}={group_value}"] = CalibrationMetrics(
                n_obs=len(indices),
                event_count=int(np.sum(group_true)),
                prevalence=float(np.mean(group_true)) if len(indices) else None,
                mean_predicted_score=float(np.mean(group_prob)) if len(indices) else None,
                mean_observed_rate=float(np.mean(group_true)) if len(indices) else None,
                brier=float(np.mean((group_prob - group_true) ** 2)) if len(indices) else None,
                log_loss=(
                    float(
                        np.mean(
                            -group_true * np.log(np.clip(group_prob, _EPSILON, 1.0 - _EPSILON))
                            - (1.0 - group_true)
                            * np.log(np.clip(1.0 - group_prob, _EPSILON, 1.0 - _EPSILON))
                        )
                    )
                    if len(indices)
                    else None
                ),
                ece=metric_values["ece"],
                mce=metric_values["mce"],
                rmsce=metric_values["rmsce"],
                ence=_compute_ence(
                    group_prob,
                    group_true,
                    _prepare_uncertainties(None, group_prob),
                ),
            )
    return result


def _bootstrap_repetitions(uncertainty: Mapping[str, Any] | None) -> int:
    if uncertainty is None:
        return 0
    bootstrap = uncertainty.get("bootstrap", 0)
    return int(bootstrap or 0)


def _confidence_level(uncertainty: Mapping[str, Any] | None) -> float:
    if uncertainty is None:
        return 0.95
    candidate = float(uncertainty.get("confidence_level", 0.95))
    return min(0.999, max(0.5, candidate))


def _bootstrap_seed(uncertainty: Mapping[str, Any] | None) -> int | None:
    if uncertainty is None or "seed" not in uncertainty:
        return None
    return int(uncertainty["seed"])


__all__ = [
    "evaluate_binary",
]
