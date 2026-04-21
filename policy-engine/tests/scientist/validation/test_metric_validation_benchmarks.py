from __future__ import annotations

import pytest

from polisyos.scientist.validation import run_metric_validation_type_i_bench


def test_metric_validation_type_i_bench_emits_expected_summary_shapes() -> None:
    result = run_metric_validation_type_i_bench(
        alpha=0.05,
        n_trials=8,
        n_samples_binary=64,
        n_samples_regression=48,
        n_resamples=49,
        random_seed=17,
    )

    assert result.alpha == 0.05
    assert result.n_trials == 8
    assert {summary.scenario_id for summary in result.single_test_summaries} == {
        "binary_null",
        "regression_null",
    }
    assert {summary.metric_id for summary in result.single_test_summaries} == {
        "roc_auc",
        "accuracy",
        "log_loss",
        "brier",
        "f1",
        "mse",
        "rmse",
        "mae",
    }
    assert {summary.correction for summary in result.family_error_summaries} == {
        "bonferroni",
        "holm",
        "bh",
        "by",
    }
    assert all(0.0 <= summary.empirical_type_i <= 1.0 for summary in result.single_test_summaries)
    assert all(
        summary.acceptance_ceiling == pytest.approx(0.06)
        for summary in result.single_test_summaries
    )
    assert all(0.0 <= summary.empirical_error_rate <= 1.0 for summary in result.family_error_summaries)
    assert all(
        summary.acceptance_ceiling == pytest.approx(0.055)
        for summary in result.family_error_summaries
    )
    assert len(result.notes) == 2
