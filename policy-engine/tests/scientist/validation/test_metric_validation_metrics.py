from __future__ import annotations

from polisyos.core.contracts.foundry import MetricObservationBundle, ModelOutputs
from polisyos.scientist.validation.metrics import TestConfig, compare_metric_family, compare_metric_pairwise


def test_compare_metric_family_uses_metric_specific_default_tests() -> None:
    bundle = MetricObservationBundle(
        dataset_id="holdout_binary",
        task="binary",
        sample_ids=[f"row_{idx}" for idx in range(10)],
        y_true=[0, 1, 0, 1, 1, 0, 1, 0, 1, 0],
        models={
            "baseline": ModelOutputs(
                model_id="baseline",
                y_pred=[0, 1, 0, 1, 1, 0, 0, 0, 1, 0],
                y_score=[0.10, 0.72, 0.25, 0.69, 0.77, 0.35, 0.46, 0.44, 0.71, 0.32],
            ),
            "candidate": ModelOutputs(
                model_id="candidate",
                y_pred=[0, 1, 0, 1, 1, 0, 1, 0, 1, 0],
                y_score=[0.06, 0.86, 0.14, 0.82, 0.88, 0.21, 0.74, 0.18, 0.83, 0.12],
            ),
        },
        metadata={"run_id": "run_metric_validation"},
    )

    report = compare_metric_family(
        bundle=bundle,
        baseline_model_id="baseline",
        candidate_model_ids=["candidate"],
        metric_ids=["roc_auc", "accuracy", "log_loss", "f1"],
        config=TestConfig(
            alpha=0.05,
            correction="holm",
            n_resamples=199,
            confidence_level=0.95,
            random_seed=7,
        ),
        family_scope="all_pairs_all_metrics",
    )

    by_metric = {comparison.metric_id: comparison for comparison in report.comparisons}

    assert report.is_valid is True
    assert report.run_id == "run_metric_validation"
    assert by_metric["roc_auc"].significance.test_id == "delong_auc"
    assert by_metric["accuracy"].significance.test_id in {"mcnemar_exact", "mcnemar_chi2"}
    assert by_metric["log_loss"].significance.test_id == "paired_t"
    assert by_metric["f1"].significance.test_id == "paired_permutation"
    assert all(comparison.significance.p_value_adj is not None for comparison in report.comparisons)


def test_compare_metric_pairwise_rmse_flags_squared_loss_proxy() -> None:
    bundle = MetricObservationBundle(
        dataset_id="holdout_regression",
        task="regression",
        sample_ids=[f"row_{idx}" for idx in range(6)],
        y_true=[1.0, 2.0, 1.5, 2.5, 3.0, 2.2],
        models={
            "baseline": ModelOutputs(
                model_id="baseline",
                y_pred=[0.7, 2.4, 1.9, 2.9, 2.3, 2.7],
            ),
            "candidate": ModelOutputs(
                model_id="candidate",
                y_pred=[0.9, 2.1, 1.6, 2.4, 2.8, 2.3],
            ),
        },
    )

    result = compare_metric_pairwise(
        bundle=bundle,
        baseline_model_id="baseline",
        candidate_model_id="candidate",
        metric_id="rmse",
        config=TestConfig(alpha=0.05, n_resamples=199, random_seed=3),
    )

    assert result.significance.test_id == "paired_t"
    assert "rmse_tested_on_squared_losses" in result.significance.assumption_flags
