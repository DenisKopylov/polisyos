from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.metric_validation_report import (
    FamilyAdjustment,
    MetricComparisonResult,
    MetricValidationReport,
    SignificanceRecord,
    load_metric_validation_report,
    persist_metric_validation_report,
)


def test_metric_validation_report_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report = MetricValidationReport(
        report_id="mvr_roundtrip",
        run_id="run-1",
        dataset_id="holdout_v1",
        task="binary",
        checked_at="2026-04-21T10:00:00Z",
        family_adjustment=FamilyAdjustment(
            method="holm",
            alpha=0.05,
            hypotheses_total=2,
            error_rate_target="FWER",
            dependency_assumption="arbitrary",
        ),
        comparisons=(
            MetricComparisonResult(
                metric_id="accuracy",
                metric_direction="higher_is_better",
                baseline_model_id="baseline",
                candidate_model_id="candidate",
                baseline_value=0.71,
                candidate_value=0.76,
                delta_value=0.05,
                significance=SignificanceRecord(
                    test_id="mcnemar_exact",
                    null_hypothesis="Accuracy(candidate) - Accuracy(baseline) = 0",
                    alternative="greater",
                    p_value_raw=0.031,
                    p_value_adj=0.031,
                    alpha=0.05,
                    reject_null_raw=True,
                    reject_null_adj=True,
                ),
                family_id="holdout_v1:baseline_vs_candidate",
                family_scope="per_candidate",
            ),
        ),
        notes=("seed=7",),
    )

    ref = persist_metric_validation_report(store, report)
    loaded = load_metric_validation_report(store, ref)

    assert ref.kind == "scientist.metric_validation_report"
    assert loaded == report
