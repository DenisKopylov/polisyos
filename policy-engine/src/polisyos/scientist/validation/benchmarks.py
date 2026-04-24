"""Regression bench for formal metric-validation error calibration."""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.foundry import MetricObservationBundle, ModelOutputs

from .metrics import (
    CorrectionMethod,
    MetricId,
    TestConfig,
    compare_metric_family,
    compare_metric_pairwise,
)


class TypeITestSummary(BaseModel):
    """Empirical Type I summary for one metric/test family under the null."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    metric_id: MetricId
    alpha: float
    n_trials: int = Field(ge=1)
    empirical_type_i: float = Field(ge=0.0, le=1.0)
    acceptance_ceiling: float = Field(ge=0.0, le=1.0)
    passes_acceptance: bool


class FamilyErrorSummary(BaseModel):
    """Empirical family-level error summary for a multiplicity correction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str
    correction: CorrectionMethod
    error_rate_target: Literal["FWER", "FDR"]
    alpha: float
    n_trials: int = Field(ge=1)
    empirical_error_rate: float = Field(ge=0.0, le=1.0)
    acceptance_ceiling: float = Field(ge=0.0, le=1.0)
    passes_acceptance: bool


class MetricValidationTypeIBenchResult(BaseModel):
    """Deterministic calibration bench output for CI regression coverage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alpha: float
    n_trials: int = Field(ge=1)
    single_test_summaries: tuple[TypeITestSummary, ...]
    family_error_summaries: tuple[FamilyErrorSummary, ...]
    notes: tuple[str, ...] = ()


def run_metric_validation_type_i_bench(
    *,
    alpha: float = 0.05,
    n_trials: int = 64,
    n_samples_binary: int = 256,
    n_samples_regression: int = 192,
    n_resamples: int = 199,
    random_seed: int = 0,
    family_corrections: tuple[CorrectionMethod, ...] = ("bonferroni", "holm", "bh", "by"),
) -> MetricValidationTypeIBenchResult:
    """Estimate empirical Type I / family error under exchangeable null scenarios."""

    rng = np.random.default_rng(random_seed)
    effective_n_resamples = max(int(n_resamples), 100)
    binary_metrics: tuple[MetricId, ...] = ("roc_auc", "accuracy", "log_loss", "brier", "f1")
    regression_metrics: tuple[MetricId, ...] = ("mse", "rmse", "mae")

    single_test_rejections: dict[tuple[str, MetricId], int] = {
        ("binary_null", metric_id): 0 for metric_id in binary_metrics
    }
    single_test_rejections.update(
        {("regression_null", metric_id): 0 for metric_id in regression_metrics}
    )
    family_rejections: dict[CorrectionMethod, int] = dict.fromkeys(family_corrections, 0)

    for trial in range(n_trials):
        binary_bundle = _binary_null_bundle(
            rng=rng,
            dataset_id=f"binary_null_{trial}",
            n_samples=n_samples_binary,
        )
        for metric_id in binary_metrics:
            result = compare_metric_pairwise(
                bundle=binary_bundle,
                baseline_model_id="baseline",
                candidate_model_id="candidate",
                metric_id=metric_id,
                config=TestConfig(
                    alpha=alpha,
                    correction="none",
                    n_resamples=effective_n_resamples,
                    random_seed=int(rng.integers(0, 2**31 - 1)),
                ),
            )
            if bool(result.significance.reject_null_raw):
                single_test_rejections[("binary_null", metric_id)] += 1

        for correction in family_corrections:
            family_report = compare_metric_family(
                bundle=binary_bundle,
                baseline_model_id="baseline",
                candidate_model_ids=["candidate"],
                metric_ids=list(binary_metrics),
                config=TestConfig(
                    alpha=alpha,
                    correction=correction,
                    n_resamples=effective_n_resamples,
                    random_seed=int(rng.integers(0, 2**31 - 1)),
                ),
                family_scope="all_pairs_all_metrics",
            )
            if any(
                bool(
                    comparison.significance.reject_null_adj
                    if comparison.significance.reject_null_adj is not None
                    else comparison.significance.reject_null_raw
                )
                for comparison in family_report.comparisons
            ):
                family_rejections[correction] += 1

        regression_bundle = _regression_null_bundle(
            rng=rng,
            dataset_id=f"regression_null_{trial}",
            n_samples=n_samples_regression,
        )
        for metric_id in regression_metrics:
            result = compare_metric_pairwise(
                bundle=regression_bundle,
                baseline_model_id="baseline",
                candidate_model_id="candidate",
                metric_id=metric_id,
                config=TestConfig(
                    alpha=alpha,
                    correction="none",
                    n_resamples=effective_n_resamples,
                    random_seed=int(rng.integers(0, 2**31 - 1)),
                ),
            )
            if bool(result.significance.reject_null_raw):
                single_test_rejections[("regression_null", metric_id)] += 1

    single_test_summaries = tuple(
        TypeITestSummary(
            scenario_id=scenario_id,
            metric_id=metric_id,
            alpha=alpha,
            n_trials=n_trials,
            empirical_type_i=count / n_trials,
            acceptance_ceiling=min(1.0, 1.2 * alpha),
            passes_acceptance=(count / n_trials) <= min(1.0, 1.2 * alpha),
        )
        for (scenario_id, metric_id), count in sorted(single_test_rejections.items())
    )

    family_error_summaries = tuple(
        FamilyErrorSummary(
            scenario_id="binary_null_family",
            correction=correction,
            error_rate_target=("FDR" if correction in {"bh", "by"} else "FWER"),
            alpha=alpha,
            n_trials=n_trials,
            empirical_error_rate=count / n_trials,
            acceptance_ceiling=min(1.0, 1.1 * alpha),
            passes_acceptance=(count / n_trials) <= min(1.0, 1.1 * alpha),
        )
        for correction, count in family_rejections.items()
    )

    return MetricValidationTypeIBenchResult(
        alpha=alpha,
        n_trials=n_trials,
        single_test_summaries=single_test_summaries,
        family_error_summaries=family_error_summaries,
        notes=(
            "Bench uses exchangeable binary and regression null scenarios for CI regression guarding.",
            "BH/BY family summaries are evaluated under the global null, where FDR reduces to a familywise error event rate.",
        ),
    )


def _binary_null_bundle(
    *,
    rng: np.random.Generator,
    dataset_id: str,
    n_samples: int,
) -> MetricObservationBundle:
    y_true = rng.binomial(1, 0.4, size=n_samples).astype(int)
    common_signal = (2.2 * y_true - 1.1) + rng.normal(0.0, 0.9, size=n_samples)
    baseline_logits = common_signal + rng.normal(0.0, 0.65, size=n_samples)
    candidate_logits = common_signal + rng.normal(0.0, 0.65, size=n_samples)
    baseline_scores = _expit(baseline_logits)
    candidate_scores = _expit(candidate_logits)
    return MetricObservationBundle(
        dataset_id=dataset_id,
        task="binary",
        sample_ids=[f"row_{index}" for index in range(n_samples)],
        y_true=y_true.tolist(),
        models={
            "baseline": ModelOutputs(
                model_id="baseline",
                y_pred=(baseline_scores >= 0.5).astype(int).tolist(),
                y_score=baseline_scores.tolist(),
            ),
            "candidate": ModelOutputs(
                model_id="candidate",
                y_pred=(candidate_scores >= 0.5).astype(int).tolist(),
                y_score=candidate_scores.tolist(),
            ),
        },
        metadata={"bench_scenario": "binary_null"},
    )


def _regression_null_bundle(
    *,
    rng: np.random.Generator,
    dataset_id: str,
    n_samples: int,
) -> MetricObservationBundle:
    x = rng.normal(0.0, 1.0, size=n_samples)
    y_true = 1.5 + 0.8 * x + rng.normal(0.0, 0.7, size=n_samples)
    shared_prediction = 1.5 + 0.8 * x
    baseline_pred = shared_prediction + rng.normal(0.0, 0.5, size=n_samples)
    candidate_pred = shared_prediction + rng.normal(0.0, 0.5, size=n_samples)
    return MetricObservationBundle(
        dataset_id=dataset_id,
        task="regression",
        sample_ids=[f"row_{index}" for index in range(n_samples)],
        y_true=y_true.tolist(),
        models={
            "baseline": ModelOutputs(
                model_id="baseline",
                y_pred=baseline_pred.tolist(),
            ),
            "candidate": ModelOutputs(
                model_id="candidate",
                y_pred=candidate_pred.tolist(),
            ),
        },
        metadata={"bench_scenario": "regression_null"},
    )


def _expit(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    return 1.0 / (1.0 + np.exp(-arr))
