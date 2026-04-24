"""Formal statistical validation for paired metric comparisons."""

from __future__ import annotations

from datetime import UTC, datetime
from math import sqrt
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import stats
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    log_loss,
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
)

from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    MetricObservationBundle,
    MetricObservationBundleRef,
    ModelOutputs,
)
from polisyos.ir.analytics.metric_validation_report import (
    FamilyAdjustment,
    MetricComparisonResult,
    MetricValidationReport,
    SignificanceRecord,
    ValidationIssue,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact

MetricId = Literal[
    "roc_auc",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "log_loss",
    "brier",
    "mse",
    "rmse",
    "mae",
    "average_precision",
]

CorrectionMethod = Literal[
    "none",
    "bonferroni",
    "holm",
    "bh",
    "by",
    "westfall_young_maxT",
    "westfall_young_minP",
]

TestId = Literal[
    "delong_auc",
    "mcnemar_exact",
    "mcnemar_chi2",
    "paired_t",
    "wilcoxon_signed_rank",
    "paired_permutation",
    "paired_bootstrap_bca",
]

FamilyScope = Literal["per_candidate", "per_metric", "all_pairs_all_metrics"]

_EPS = 1e-15
_PAIRWISE_SCOPE = "pairwise"
_HIGHER_IS_BETTER = {
    "roc_auc",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "average_precision",
}
_TEST_LABELS: dict[str, str] = {
    "delong_auc": "DeLong AUC",
    "mcnemar_exact": "McNemar exact",
    "mcnemar_chi2": "McNemar chi-square",
    "paired_t": "Paired t-test",
    "wilcoxon_signed_rank": "Wilcoxon signed-rank",
    "paired_permutation": "Paired permutation",
    "paired_bootstrap_bca": "Paired bootstrap",
}


class TestConfig(BaseModel):
    """Runtime configuration for paired metric validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    __test__ = False

    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    alternative: Literal["two-sided", "greater", "less"] = "two-sided"
    n_resamples: int = Field(default=20_000, ge=100)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    correction: CorrectionMethod = "holm"
    random_seed: int | None = None
    exact_if_feasible: bool = True


def persist_metric_observation_bundle(
    store: ArtifactStore,
    bundle: MetricObservationBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "polisyos.foundry.metric_observation_bundle",
    schema_version: str = "1.0",
) -> MetricObservationBundleRef:
    """Persist a metric observation bundle and return its typed reference."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="foundry.metric_observation_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return MetricObservationBundleRef.model_validate(ref)


def load_metric_observation_bundle(
    store: ArtifactStore,
    ref: MetricObservationBundleRef,
) -> MetricObservationBundle:
    """Load a persisted metric observation bundle from CAS."""

    payload = get_json_artifact(store, ref.artifact_id)
    return MetricObservationBundle.model_validate(payload)


def describe_test_id(test_id: str) -> str:
    """Return a dashboard-friendly label for a statistical test identifier."""

    return _TEST_LABELS.get(test_id, test_id.replace("_", " ").title())


def recommend_test(
    *,
    metric_id: MetricId,
    task: str,
    has_scores: bool,
    is_paired: bool,
    n_samples: int,
    class_prevalence: float | None = None,
) -> TestId:
    """Recommend the default paired test for the given metric family."""

    del n_samples, class_prevalence
    if not is_paired:
        return "paired_permutation"
    if metric_id == "roc_auc" and task == "binary" and has_scores:
        return "delong_auc"
    if metric_id == "accuracy":
        return "mcnemar_exact"
    if metric_id in {"log_loss", "brier", "mse", "rmse", "mae"}:
        return "paired_t"
    return "paired_permutation"


def compare_metric_pairwise(
    *,
    bundle: MetricObservationBundle,
    baseline_model_id: str,
    candidate_model_id: str,
    metric_id: MetricId,
    config: TestConfig,
    family_scope: str = _PAIRWISE_SCOPE,
) -> MetricComparisonResult:
    """Compare one candidate against a baseline on a single metric."""

    baseline = _require_model(bundle, baseline_model_id)
    candidate = _require_model(bundle, candidate_model_id)
    baseline_value = _metric_value(metric_id, bundle, baseline)
    candidate_value = _metric_value(metric_id, bundle, candidate)
    delta_value = float(candidate_value - baseline_value)
    recommended_test = recommend_test(
        metric_id=metric_id,
        task=bundle.task,
        has_scores=candidate.y_score is not None and baseline.y_score is not None,
        is_paired=True,
        n_samples=len(bundle.y_true),
    )
    significance, resampling_method = _run_significance_test(
        metric_id=metric_id,
        bundle=bundle,
        baseline=baseline,
        candidate=candidate,
        config=config,
        test_id=recommended_test,
        delta_value=delta_value,
    )
    return MetricComparisonResult(
        metric_id=metric_id,
        metric_direction=_metric_direction(metric_id),
        baseline_model_id=baseline_model_id,
        candidate_model_id=candidate_model_id,
        baseline_value=float(baseline_value),
        candidate_value=float(candidate_value),
        delta_value=delta_value,
        significance=significance,
        resampling_method=resampling_method,
        sample_size_effective=len(bundle.y_true),
        family_id=_family_id(
            bundle=bundle,
            baseline_model_id=baseline_model_id,
            candidate_model_id=candidate_model_id,
            metric_id=metric_id,
            family_scope=family_scope,
        ),
        family_scope=family_scope,
    )


def compare_metric_family(
    *,
    bundle: MetricObservationBundle,
    baseline_model_id: str,
    candidate_model_ids: list[str],
    metric_ids: list[MetricId],
    config: TestConfig,
    family_scope: FamilyScope = "all_pairs_all_metrics",
) -> MetricValidationReport:
    """Compare a family of candidate/metric pairs and apply multiplicity correction."""

    comparisons: list[MetricComparisonResult] = []
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    for candidate_model_id in candidate_model_ids:
        for metric_id in metric_ids:
            try:
                comparisons.append(
                    compare_metric_pairwise(
                        bundle=bundle,
                        baseline_model_id=baseline_model_id,
                        candidate_model_id=candidate_model_id,
                        metric_id=metric_id,
                        config=config,
                        family_scope=family_scope,
                    )
                )
            except Exception as exc:
                errors.append(
                    ValidationIssue(
                        code="metric_validation.compare_failed",
                        severity="error",
                        message=str(exc),
                        field_path=f"{candidate_model_id}.{metric_id}",
                        hint="Inspect observation bundle alignment and metric requirements.",
                    )
                )

    adjusted = list(comparisons)
    grouped_indices: dict[str, list[int]] = {}
    family_adjustment = _family_adjustment_metadata(
        method=config.correction,
        alpha=config.alpha,
        hypotheses_total=max(len(comparisons), 1),
    )
    if comparisons:
        grouped_indices = _group_comparison_indices(comparisons, family_scope)
        hypotheses_total = 0
        for indices in grouped_indices.values():
            hypotheses_total = max(hypotheses_total, len(indices))
            raw = np.asarray(
                [comparisons[index].significance.p_value_raw or 1.0 for index in indices],
                dtype=float,
            )
            adjusted_pvalues, rejects, group_adjustment = _apply_correction(
                raw_pvalues=raw,
                method=config.correction,
                alpha=config.alpha,
            )
            family_adjustment = group_adjustment.model_copy(
                update={
                    "hypotheses_total": max(group_adjustment.hypotheses_total, hypotheses_total)
                }
            )
            for local_index, comparison_index in enumerate(indices):
                comparison = comparisons[comparison_index]
                significance = comparison.significance.model_copy(
                    update={
                        "p_value_adj": float(adjusted_pvalues[local_index]),
                        "reject_null_adj": bool(rejects[local_index]),
                    }
                )
                adjusted[comparison_index] = comparison.model_copy(
                    update={"significance": significance}
                )

    if any(
        comparison.metric_id == "rmse"
        and "rmse_tested_on_squared_losses" in comparison.significance.assumption_flags
        for comparison in adjusted
    ):
        warnings.append(
            ValidationIssue(
                code="metric_validation.rmse_proxy_test",
                severity="warning",
                message="RMSE significance was tested on paired squared losses; RMSE remains a secondary scale.",
                field_path="comparisons",
                hint="Prefer reviewing both delta_rmse and delta_mse when thresholds are tight.",
            )
        )

    notes = [f"family_scope={family_scope}", f"correction={config.correction}"]
    if grouped_indices and len(grouped_indices) > 1:
        notes.append(f"group_count={len(grouped_indices)}")

    run_id = (
        str(bundle.metadata.get("run_id")) if bundle.metadata.get("run_id") is not None else None
    )
    checked_at = datetime.now(UTC).isoformat()
    report_id = f"mvr_{checked_at.replace(':', '').replace('-', '')}"
    return MetricValidationReport(
        report_id=report_id,
        run_id=run_id,
        dataset_id=bundle.dataset_id,
        task=bundle.task,
        is_valid=not errors,
        checked_at=checked_at,
        errors=tuple(errors),
        warnings=tuple(warnings),
        family_adjustment=family_adjustment,
        comparisons=tuple(adjusted),
        notes=tuple(notes),
    )


def adjust_family(
    *,
    raw_pvalues: np.ndarray,
    method: CorrectionMethod,
    alpha: float,
    permutation_null: np.ndarray | None = None,
) -> FamilyAdjustment:
    """Return only the family-level multiplicity metadata for a correction method."""

    del permutation_null
    _, _, adjustment = _apply_correction(
        raw_pvalues=np.asarray(raw_pvalues, dtype=float),
        method=method,
        alpha=alpha,
    )
    return adjustment


def _require_model(bundle: MetricObservationBundle, model_id: str) -> ModelOutputs:
    outputs = bundle.models.get(model_id)
    if outputs is None:
        raise ValueError(f"Model {model_id!r} is missing from the observation bundle")
    return outputs


def _metric_direction(metric_id: str) -> Literal["higher_is_better", "lower_is_better"]:
    return "higher_is_better" if metric_id in _HIGHER_IS_BETTER else "lower_is_better"


def _family_id(
    *,
    bundle: MetricObservationBundle,
    baseline_model_id: str,
    candidate_model_id: str,
    metric_id: str,
    family_scope: str,
) -> str:
    if family_scope == "per_candidate":
        return f"{bundle.dataset_id}:{baseline_model_id}_vs_{candidate_model_id}"
    if family_scope == "per_metric":
        return f"{bundle.dataset_id}:{metric_id}"
    if family_scope == "all_pairs_all_metrics":
        return f"{bundle.dataset_id}:{baseline_model_id}:all_pairs_all_metrics"
    return f"{bundle.dataset_id}:{baseline_model_id}_vs_{candidate_model_id}:{metric_id}"


def _group_comparison_indices(
    comparisons: list[MetricComparisonResult],
    family_scope: FamilyScope,
) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for index, comparison in enumerate(comparisons):
        if family_scope == "per_candidate":
            key = comparison.family_id
        elif family_scope == "per_metric":
            key = comparison.metric_id
        else:
            key = "all_pairs_all_metrics"
        groups.setdefault(key, []).append(index)
    return groups


def _family_adjustment_metadata(
    *,
    method: CorrectionMethod,
    alpha: float,
    hypotheses_total: int,
) -> FamilyAdjustment:
    error_rate_target = "FDR" if method in {"bh", "by"} else "FWER"
    dependency_assumption = {
        "none": None,
        "bonferroni": "arbitrary",
        "holm": "arbitrary",
        "bh": "independent_or_prds",
        "by": "arbitrary",
        "westfall_young_maxT": "resampled_dependence",
        "westfall_young_minP": "resampled_dependence",
    }[method]
    return FamilyAdjustment(
        method=method,
        alpha=float(alpha),
        hypotheses_total=int(max(hypotheses_total, 1)),
        error_rate_target=error_rate_target,
        dependency_assumption=dependency_assumption,
    )


def _apply_correction(
    *,
    raw_pvalues: np.ndarray,
    method: CorrectionMethod,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray, FamilyAdjustment]:
    raw = np.asarray(raw_pvalues, dtype=float)
    if raw.size == 0:
        return (
            raw,
            np.asarray([], dtype=bool),
            _family_adjustment_metadata(
                method=method,
                alpha=alpha,
                hypotheses_total=1,
            ),
        )
    if method in {"westfall_young_maxT", "westfall_young_minP"}:
        raise NotImplementedError(f"{method} is reserved for a later phase")
    if method == "none":
        adjusted = np.clip(raw, 0.0, 1.0)
        reject = adjusted <= alpha
    else:
        adjusted = {
            "bonferroni": _bonferroni_adjust,
            "holm": _holm_adjust,
            "bh": _bh_adjust,
            "by": _by_adjust,
        }[method](raw)
        reject = adjusted <= alpha
    return (
        np.asarray(adjusted, dtype=float),
        np.asarray(reject, dtype=bool),
        _family_adjustment_metadata(method=method, alpha=alpha, hypotheses_total=raw.size),
    )


def _bonferroni_adjust(raw_pvalues: np.ndarray) -> np.ndarray:
    raw = np.asarray(raw_pvalues, dtype=float)
    return np.clip(raw * raw.size, 0.0, 1.0)


def _holm_adjust(raw_pvalues: np.ndarray) -> np.ndarray:
    raw = np.asarray(raw_pvalues, dtype=float)
    order = np.argsort(raw, kind="mergesort")
    sorted_raw = raw[order]
    multipliers = np.arange(raw.size, 0, -1, dtype=float)
    # Holm adjusted p-values are a step-down monotone transform.
    sorted_adjusted = np.maximum.accumulate(sorted_raw * multipliers)
    sorted_adjusted = np.clip(sorted_adjusted, 0.0, 1.0)
    adjusted = np.empty_like(sorted_adjusted)
    adjusted[order] = sorted_adjusted
    return adjusted


def _bh_adjust(raw_pvalues: np.ndarray) -> np.ndarray:
    return _step_up_fdr_adjust(raw_pvalues, harmonic_factor=1.0)


def _by_adjust(raw_pvalues: np.ndarray) -> np.ndarray:
    size = np.asarray(raw_pvalues, dtype=float).size
    harmonic = float(np.sum(1.0 / np.arange(1, size + 1, dtype=float))) if size else 1.0
    return _step_up_fdr_adjust(raw_pvalues, harmonic_factor=harmonic)


def _step_up_fdr_adjust(raw_pvalues: np.ndarray, *, harmonic_factor: float) -> np.ndarray:
    raw = np.asarray(raw_pvalues, dtype=float)
    order = np.argsort(raw, kind="mergesort")
    sorted_raw = raw[order]
    ranks = np.arange(1, raw.size + 1, dtype=float)
    scaled = (sorted_raw * raw.size * harmonic_factor) / ranks
    sorted_adjusted = np.minimum.accumulate(scaled[::-1])[::-1]
    sorted_adjusted = np.clip(sorted_adjusted, 0.0, 1.0)
    adjusted = np.empty_like(sorted_adjusted)
    adjusted[order] = sorted_adjusted
    return adjusted


def _run_significance_test(
    *,
    metric_id: MetricId,
    bundle: MetricObservationBundle,
    baseline: ModelOutputs,
    candidate: ModelOutputs,
    config: TestConfig,
    test_id: TestId,
    delta_value: float,
) -> tuple[SignificanceRecord, str | None]:
    if test_id == "delong_auc":
        return _run_delong_auc(bundle, baseline, candidate, config, delta_value), None
    if test_id.startswith("mcnemar"):
        return _run_mcnemar(bundle, baseline, candidate, config, delta_value), None
    if test_id == "paired_t":
        return _run_paired_t(metric_id, bundle, baseline, candidate, config, delta_value), None
    return _run_paired_permutation(metric_id, bundle, baseline, candidate, config, delta_value)


def _run_delong_auc(
    bundle: MetricObservationBundle,
    baseline: ModelOutputs,
    candidate: ModelOutputs,
    config: TestConfig,
    delta_value: float,
) -> SignificanceRecord:
    y_true = _binary_indicator(bundle.y_true)
    baseline_scores = _binary_score_vector(_require_score_array(baseline))
    candidate_scores = _binary_score_vector(_require_score_array(candidate))
    order = np.argsort(-y_true, kind="mergesort")
    y_sorted = y_true[order]
    label_1_count = int(np.sum(y_sorted))
    if label_1_count == 0 or label_1_count == y_sorted.size:
        raise ValueError("DeLong AUC requires both positive and negative observations")
    preds = np.vstack([baseline_scores[order], candidate_scores[order]])
    aucs, covariance = _fast_delong(preds, label_1_count)
    variance = float(
        covariance[0, 0] + covariance[1, 1] - 2.0 * covariance[0, 1]
        if covariance.ndim == 2
        else covariance
    )
    variance = max(variance, 0.0)
    standard_error = sqrt(variance) if variance > 0 else 0.0
    statistic = float((aucs[1] - aucs[0]) / standard_error) if standard_error > 0 else 0.0
    p_value = _normal_pvalue(statistic, config.alternative)
    ci_low = ci_high = None
    if standard_error > 0:
        z_crit = float(stats.norm.ppf(0.5 + config.confidence_level / 2.0))
        ci_low = float((aucs[1] - aucs[0]) - z_crit * standard_error)
        ci_high = float((aucs[1] - aucs[0]) + z_crit * standard_error)
    return SignificanceRecord(
        test_id="delong_auc",
        null_hypothesis="AUC(candidate) - AUC(baseline) = 0",
        alternative=config.alternative,
        statistic=statistic,
        effect_size=delta_value,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_level=config.confidence_level if ci_low is not None and ci_high is not None else None,
        p_value_raw=p_value,
        alpha=config.alpha,
        reject_null_raw=bool(p_value <= config.alpha),
    )


def _run_mcnemar(
    bundle: MetricObservationBundle,
    baseline: ModelOutputs,
    candidate: ModelOutputs,
    config: TestConfig,
    delta_value: float,
) -> SignificanceRecord:
    baseline_pred = _require_pred_array(baseline)
    candidate_pred = _require_pred_array(candidate)
    y_true = np.asarray(bundle.y_true)
    if baseline_pred.shape != y_true.shape or candidate_pred.shape != y_true.shape:
        raise ValueError("McNemar requires one prediction per observation for both models")
    baseline_correct = baseline_pred == y_true
    candidate_correct = candidate_pred == y_true
    b = int(np.sum(baseline_correct & ~candidate_correct))
    c = int(np.sum(~baseline_correct & candidate_correct))
    discordant = b + c
    if discordant == 0:
        p_value = 1.0
        statistic = 0.0
        test_name = "mcnemar_exact"
    elif config.exact_if_feasible or config.alternative != "two-sided" or discordant < 25:
        result = stats.binomtest(
            c,
            n=discordant,
            p=0.5,
            alternative=_binom_alternative(config.alternative),
        )
        p_value = float(result.pvalue)
        statistic = float(c / discordant)
        test_name = "mcnemar_exact"
    else:
        statistic = float(((abs(b - c) - 1.0) ** 2) / discordant)
        p_value = float(stats.chi2.sf(statistic, df=1))
        test_name = "mcnemar_chi2"
    return SignificanceRecord(
        test_id=test_name,
        null_hypothesis="Accuracy(candidate) - Accuracy(baseline) = 0",
        alternative=config.alternative,
        statistic=statistic,
        effect_size=delta_value,
        p_value_raw=p_value,
        alpha=config.alpha,
        reject_null_raw=bool(p_value <= config.alpha),
        assumption_flags=(("low_discordance",) if discordant < 10 else ()),
    )


def _run_paired_t(
    metric_id: MetricId,
    bundle: MetricObservationBundle,
    baseline: ModelOutputs,
    candidate: ModelOutputs,
    config: TestConfig,
    delta_value: float,
) -> SignificanceRecord:
    baseline_loss, assumption_flags = _per_example_loss(metric_id, bundle, baseline)
    candidate_loss, candidate_flags = _per_example_loss(metric_id, bundle, candidate)
    deltas = candidate_loss - baseline_loss
    finite = np.isfinite(deltas)
    deltas = deltas[finite]
    if deltas.size == 0:
        raise ValueError(f"{metric_id} paired t-test requires at least one finite loss difference")
    result = stats.ttest_1samp(deltas, popmean=0.0, alternative=config.alternative)
    p_value = float(result.pvalue)
    statistic = float(result.statistic) if np.isfinite(result.statistic) else 0.0
    ci_low, ci_high = _mean_difference_ci(
        deltas,
        confidence_level=config.confidence_level,
    )
    assumption = tuple(dict.fromkeys(assumption_flags + candidate_flags))
    return SignificanceRecord(
        test_id="paired_t",
        null_hypothesis=f"{metric_id}(candidate) - {metric_id}(baseline) = 0",
        alternative=config.alternative,
        statistic=statistic,
        effect_size=delta_value,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_level=config.confidence_level if ci_low is not None and ci_high is not None else None,
        p_value_raw=p_value,
        alpha=config.alpha,
        reject_null_raw=bool(p_value <= config.alpha),
        assumption_flags=assumption,
    )


def _run_paired_permutation(
    metric_id: MetricId,
    bundle: MetricObservationBundle,
    baseline: ModelOutputs,
    candidate: ModelOutputs,
    config: TestConfig,
    delta_value: float,
) -> tuple[SignificanceRecord, str]:
    rng = np.random.default_rng(config.random_seed)
    y_true = np.asarray(bundle.y_true)
    sample_weight = (
        np.asarray(bundle.sample_weight, dtype=float) if bundle.sample_weight is not None else None
    )
    if metric_id in {"roc_auc", "average_precision", "log_loss", "brier"}:
        baseline_values = _require_score_array(baseline)
        candidate_values = _require_score_array(candidate)

        def statistic(left: np.ndarray, right: np.ndarray, axis: int = 0) -> float:
            del axis
            return float(
                _metric_value_from_parts(
                    metric_id,
                    task=bundle.task,
                    y_true=y_true,
                    y_score=right,
                    sample_weight=sample_weight,
                )
                - _metric_value_from_parts(
                    metric_id,
                    task=bundle.task,
                    y_true=y_true,
                    y_score=left,
                    sample_weight=sample_weight,
                )
            )

        bootstrap = lambda idx: float(
            _metric_value_from_parts(
                metric_id,
                task=bundle.task,
                y_true=y_true[idx],
                y_score=candidate_values[idx],
                sample_weight=sample_weight[idx] if sample_weight is not None else None,
            )
            - _metric_value_from_parts(
                metric_id,
                task=bundle.task,
                y_true=y_true[idx],
                y_score=baseline_values[idx],
                sample_weight=sample_weight[idx] if sample_weight is not None else None,
            )
        )
    else:
        baseline_values = _require_pred_array(baseline)
        candidate_values = _require_pred_array(candidate)

        def statistic(left: np.ndarray, right: np.ndarray, axis: int = 0) -> float:
            del axis
            return float(
                _metric_value_from_parts(
                    metric_id,
                    task=bundle.task,
                    y_true=y_true,
                    y_pred=right,
                    sample_weight=sample_weight,
                )
                - _metric_value_from_parts(
                    metric_id,
                    task=bundle.task,
                    y_true=y_true,
                    y_pred=left,
                    sample_weight=sample_weight,
                )
            )

        bootstrap = lambda idx: float(
            _metric_value_from_parts(
                metric_id,
                task=bundle.task,
                y_true=y_true[idx],
                y_pred=candidate_values[idx],
                sample_weight=sample_weight[idx] if sample_weight is not None else None,
            )
            - _metric_value_from_parts(
                metric_id,
                task=bundle.task,
                y_true=y_true[idx],
                y_pred=baseline_values[idx],
                sample_weight=sample_weight[idx] if sample_weight is not None else None,
            )
        )

    result = stats.permutation_test(
        (baseline_values, candidate_values),
        statistic,
        permutation_type="samples",
        vectorized=False,
        n_resamples=config.n_resamples,
        alternative=config.alternative,
        rng=rng,
    )
    ci_low, ci_high = _bootstrap_ci(
        n_samples=len(y_true),
        confidence_level=config.confidence_level,
        n_resamples=min(config.n_resamples, 2_000),
        rng=rng,
        statistic=bootstrap,
    )
    significance = SignificanceRecord(
        test_id="paired_permutation",
        null_hypothesis=f"{metric_id}(candidate) - {metric_id}(baseline) = 0",
        alternative=config.alternative,
        statistic=float(result.statistic),
        effect_size=delta_value,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_level=config.confidence_level if ci_low is not None and ci_high is not None else None,
        p_value_raw=float(result.pvalue),
        alpha=config.alpha,
        reject_null_raw=bool(float(result.pvalue) <= config.alpha),
        assumption_flags=(
            ("non_additive_metric",) if metric_id in {"f1", "precision", "recall"} else ()
        ),
    )
    return significance, "paired_permutation"


def _metric_value(
    metric_id: MetricId, bundle: MetricObservationBundle, outputs: ModelOutputs
) -> float:
    sample_weight = (
        np.asarray(bundle.sample_weight, dtype=float) if bundle.sample_weight is not None else None
    )
    y_true = np.asarray(bundle.y_true)
    y_pred = np.asarray(outputs.y_pred) if outputs.y_pred is not None else None
    y_score = np.asarray(outputs.y_score, dtype=float) if outputs.y_score is not None else None
    return _metric_value_from_parts(
        metric_id,
        task=bundle.task,
        y_true=y_true,
        y_pred=y_pred,
        y_score=y_score,
        sample_weight=sample_weight,
    )


def _metric_value_from_parts(
    metric_id: MetricId,
    *,
    task: str,
    y_true: np.ndarray,
    y_pred: np.ndarray | None = None,
    y_score: np.ndarray | None = None,
    sample_weight: np.ndarray | None = None,
) -> float:
    if metric_id == "accuracy":
        if y_pred is None:
            raise ValueError("accuracy requires y_pred")
        return float(accuracy_score(y_true, y_pred, sample_weight=sample_weight))
    if metric_id == "precision":
        if y_pred is None:
            raise ValueError("precision requires y_pred")
        kwargs = _classification_average_kwargs(task, y_true)
        return float(
            precision_score(y_true, y_pred, sample_weight=sample_weight, zero_division=0, **kwargs)
        )
    if metric_id == "recall":
        if y_pred is None:
            raise ValueError("recall requires y_pred")
        kwargs = _classification_average_kwargs(task, y_true)
        return float(
            recall_score(y_true, y_pred, sample_weight=sample_weight, zero_division=0, **kwargs)
        )
    if metric_id == "f1":
        if y_pred is None:
            raise ValueError("f1 requires y_pred")
        kwargs = _classification_average_kwargs(task, y_true)
        return float(
            f1_score(y_true, y_pred, sample_weight=sample_weight, zero_division=0, **kwargs)
        )
    if metric_id == "roc_auc":
        if y_score is None:
            raise ValueError("roc_auc requires y_score")
        if task == "binary":
            return float(
                roc_auc_score(
                    _binary_indicator(y_true),
                    _binary_score_vector(np.asarray(y_score, dtype=float)),
                    sample_weight=sample_weight,
                )
            )
        if y_score.ndim != 2:
            raise ValueError("multiclass roc_auc requires a score matrix")
        return float(
            roc_auc_score(
                y_true,
                y_score,
                sample_weight=sample_weight,
                multi_class="ovr",
                average="macro",
            )
        )
    if metric_id == "average_precision":
        if y_score is None:
            raise ValueError("average_precision requires y_score")
        if task == "binary":
            return float(
                average_precision_score(
                    _binary_indicator(y_true),
                    _binary_score_vector(np.asarray(y_score, dtype=float)),
                    sample_weight=sample_weight,
                )
            )
        return float(
            average_precision_score(
                y_true,
                y_score,
                sample_weight=sample_weight,
                average="macro",
            )
        )
    if metric_id == "log_loss":
        if y_score is None:
            raise ValueError("log_loss requires y_score")
        labels = sorted({value for value in y_true.tolist()})
        return float(log_loss(y_true, y_score, sample_weight=sample_weight, labels=labels))
    if metric_id == "brier":
        if y_score is None:
            raise ValueError("brier requires y_score")
        target = _binary_indicator(y_true).astype(float)
        return _weighted_mean(
            np.square(_binary_score_vector(np.asarray(y_score, dtype=float)) - target),
            sample_weight,
        )
    if metric_id == "mse":
        if y_pred is None:
            raise ValueError("mse requires y_pred")
        squared = np.square(np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float))
        return _weighted_mean(squared, sample_weight)
    if metric_id == "rmse":
        return float(
            sqrt(
                _metric_value_from_parts(
                    "mse",
                    task=task,
                    y_true=y_true,
                    y_pred=y_pred,
                    y_score=y_score,
                    sample_weight=sample_weight,
                )
            )
        )
    if metric_id == "mae":
        if y_pred is None:
            raise ValueError("mae requires y_pred")
        return float(
            mean_absolute_error(
                y_true.astype(float), y_pred.astype(float), sample_weight=sample_weight
            )
        )
    raise ValueError(f"Unsupported metric_id: {metric_id}")


def _classification_average_kwargs(task: str, y_true: np.ndarray) -> dict[str, Any]:
    if task == "binary":
        return {"average": "binary", "pos_label": _binary_positive_label(y_true)}
    return {"average": "macro"}


def _per_example_loss(
    metric_id: MetricId,
    bundle: MetricObservationBundle,
    outputs: ModelOutputs,
) -> tuple[np.ndarray, tuple[str, ...]]:
    if outputs.per_example_loss is not None and metric_id in outputs.per_example_loss:
        return np.asarray(outputs.per_example_loss[metric_id], dtype=float), ()

    weight = (
        np.asarray(bundle.sample_weight, dtype=float) if bundle.sample_weight is not None else None
    )
    normalized_weight = weight / max(float(np.mean(weight)), _EPS) if weight is not None else None
    y_true = np.asarray(bundle.y_true)
    y_pred = np.asarray(outputs.y_pred) if outputs.y_pred is not None else None
    y_score = np.asarray(outputs.y_score, dtype=float) if outputs.y_score is not None else None
    flags: list[str] = []
    if normalized_weight is not None:
        flags.append("sample_weight_embedded_in_losses")
    if metric_id == "log_loss":
        if y_score is None:
            raise ValueError("log_loss requires y_score")
        losses = _per_example_log_loss(y_true, y_score)
    elif metric_id == "brier":
        if y_score is None:
            raise ValueError("brier requires y_score")
        target = _binary_indicator(y_true).astype(float)
        losses = np.square(_binary_score_vector(np.asarray(y_score, dtype=float)) - target)
    elif metric_id == "mse":
        if y_pred is None:
            raise ValueError("mse requires y_pred")
        losses = np.square(np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float))
    elif metric_id == "rmse":
        if y_pred is None:
            raise ValueError("rmse requires y_pred")
        losses = np.square(np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float))
        flags.append("rmse_tested_on_squared_losses")
    elif metric_id == "mae":
        if y_pred is None:
            raise ValueError("mae requires y_pred")
        losses = np.abs(np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float))
    else:
        raise ValueError(f"paired_t is not configured for metric {metric_id}")
    if normalized_weight is not None:
        losses = losses * normalized_weight
    return np.asarray(losses, dtype=float), tuple(flags)


def _per_example_log_loss(y_true: np.ndarray, y_score: np.ndarray) -> np.ndarray:
    scores = np.clip(np.asarray(y_score, dtype=float), _EPS, 1.0 - _EPS)
    if scores.ndim == 1:
        target = _binary_indicator(y_true).astype(float)
        return -(target * np.log(scores) + (1.0 - target) * np.log(1.0 - scores))
    labels = sorted({value for value in y_true.tolist()})
    label_to_index = {label: index for index, label in enumerate(labels)}
    encoded = np.asarray([label_to_index[value] for value in y_true.tolist()], dtype=int)
    return -np.log(np.clip(scores[np.arange(encoded.size), encoded], _EPS, 1.0))


def _weighted_mean(values: np.ndarray, sample_weight: np.ndarray | None) -> float:
    arr = np.asarray(values, dtype=float)
    if sample_weight is None:
        return float(np.mean(arr))
    weights = np.asarray(sample_weight, dtype=float)
    if arr.shape[0] != weights.shape[0]:
        raise ValueError("sample_weight length must match observation count")
    total = float(np.sum(weights))
    if total <= 0:
        raise ValueError("sample_weight must sum to a positive value")
    return float(np.sum(arr * weights) / total)


def _binary_positive_label(y_true: np.ndarray) -> bool | int | float | str:
    unique = sorted({value for value in y_true.tolist()})
    if len(unique) != 2:
        raise ValueError("Binary metrics require exactly two label values")
    return unique[-1]


def _binary_indicator(y_true: np.ndarray | list[bool | int | float | str]) -> np.ndarray:
    arr = np.asarray(y_true, dtype=object)
    positive_label = _binary_positive_label(arr)
    return (arr == positive_label).astype(int)


def _require_pred_array(outputs: ModelOutputs) -> np.ndarray:
    if outputs.y_pred is None:
        raise ValueError(f"Model {outputs.model_id!r} is missing y_pred")
    return np.asarray(outputs.y_pred)


def _require_score_array(outputs: ModelOutputs) -> np.ndarray:
    if outputs.y_score is None:
        raise ValueError(f"Model {outputs.model_id!r} is missing y_score")
    return np.asarray(outputs.y_score, dtype=float)


def _binary_score_vector(values: np.ndarray) -> np.ndarray:
    scores = np.asarray(values, dtype=float)
    if scores.ndim == 1:
        return scores
    if scores.ndim == 2 and scores.shape[1] >= 2:
        return scores[:, -1]
    raise ValueError("Binary score arrays must be one-dimensional or Nx2 probability matrices")


def _mean_difference_ci(
    deltas: np.ndarray,
    *,
    confidence_level: float,
) -> tuple[float | None, float | None]:
    values = np.asarray(deltas, dtype=float)
    if values.size < 2:
        return None, None
    standard_error = float(stats.sem(values, nan_policy="omit"))
    if not np.isfinite(standard_error):
        return None, None
    critical = float(stats.t.ppf(0.5 + confidence_level / 2.0, df=values.size - 1))
    mean = float(np.mean(values))
    radius = critical * standard_error
    return mean - radius, mean + radius


def _bootstrap_ci(
    *,
    n_samples: int,
    confidence_level: float,
    n_resamples: int,
    rng: np.random.Generator,
    statistic,
) -> tuple[float | None, float | None]:
    draws: list[float] = []
    for _ in range(n_resamples):
        index = rng.integers(0, n_samples, size=n_samples)
        value = float(statistic(index))
        if np.isfinite(value):
            draws.append(value)
    if not draws:
        return None, None
    alpha = 1.0 - confidence_level
    lower = float(np.quantile(draws, alpha / 2.0))
    upper = float(np.quantile(draws, 1.0 - alpha / 2.0))
    return lower, upper


def _normal_pvalue(statistic: float, alternative: str) -> float:
    if alternative == "greater":
        return float(stats.norm.sf(statistic))
    if alternative == "less":
        return float(stats.norm.cdf(statistic))
    return float(2.0 * stats.norm.sf(abs(statistic)))


def _binom_alternative(alternative: str) -> Literal["two-sided", "greater", "less"]:
    if alternative == "greater":
        return "greater"
    if alternative == "less":
        return "less"
    return "two-sided"


def _compute_midrank(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values)
    sorted_values = values[order]
    result = np.zeros(sorted_values.shape[0], dtype=float)
    start = 0
    while start < sorted_values.shape[0]:
        end = start
        while end < sorted_values.shape[0] and sorted_values[end] == sorted_values[start]:
            end += 1
        result[start:end] = 0.5 * (start + end - 1) + 1
        start = end
    out = np.empty_like(result)
    out[order] = result
    return out


def _fast_delong(
    predictions_sorted_transposed: np.ndarray,
    label_1_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    m = label_1_count
    n = predictions_sorted_transposed.shape[1] - m
    positives = predictions_sorted_transposed[:, :m]
    negatives = predictions_sorted_transposed[:, m:]
    k = predictions_sorted_transposed.shape[0]

    tx = np.empty((k, m), dtype=float)
    ty = np.empty((k, n), dtype=float)
    tz = np.empty((k, m + n), dtype=float)
    for row in range(k):
        tx[row] = _compute_midrank(positives[row])
        ty[row] = _compute_midrank(negatives[row])
        tz[row] = _compute_midrank(predictions_sorted_transposed[row])

    aucs = tz[:, :m].sum(axis=1) / (m * n) - (m + 1.0) / (2.0 * n)
    v01 = (tz[:, :m] - tx) / n
    v10 = 1.0 - (tz[:, m:] - ty) / m
    sx = np.cov(v01)
    sy = np.cov(v10)
    covariance = sx / m + sy / n
    return aucs, np.asarray(covariance, dtype=float)


__all__ = [
    "CorrectionMethod",
    "FamilyScope",
    "MetricId",
    "TestConfig",
    "TestId",
    "adjust_family",
    "compare_metric_family",
    "compare_metric_pairwise",
    "describe_test_id",
    "load_metric_observation_bundle",
    "persist_metric_observation_bundle",
    "recommend_test",
]
