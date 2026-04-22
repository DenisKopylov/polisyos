from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.analysis.distributional import (
    build_distributional_report,
    build_geography_breakdown,
    build_income_quintile_breakdown,
    compute_gini,
    compute_palma_ratio,
)
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    DimensionBreakdown,
    ImpactDirection,
    MetricUnit,
    load_distributional_report,
    persist_distributional_report,
)


def test_compute_gini_returns_none_for_negative_values() -> None:
    values = np.array([10.0, -1.0, 5.0])
    assert compute_gini(values) is None


def test_compute_palma_ratio_returns_none_for_tiny_bottom_share() -> None:
    values = np.array([1e-12] * 40 + [100.0] * 60)
    assert compute_palma_ratio(values) is None


def test_compute_palma_ratio_returns_none_for_negative_values() -> None:
    values = np.array([-5.0] * 10 + [10.0] * 10)
    assert compute_palma_ratio(values) is None


def test_dimension_breakdown_validates_primary_metric_presence() -> None:
    with pytest.raises(ValueError, match="missing primary metric"):
        DimensionBreakdown(
            dimension=CohortDimension.CUSTOM,
            dimension_label="Custom",
            primary_metric="income_delta",
            primary_metric_unit=MetricUnit.PERCENT,
            cohorts=[
                CohortImpact(
                    cohort_id="c1",
                    cohort_label="C1",
                    population_share=0.5,
                    metric_deltas={"other_metric": 1.0},
                    impact_direction=ImpactDirection.POSITIVE,
                ),
                CohortImpact(
                    cohort_id="c2",
                    cohort_label="C2",
                    population_share=0.5,
                    metric_deltas={"income_delta": -1.0},
                    impact_direction=ImpactDirection.NEGATIVE,
                ),
            ],
        )


def test_distributional_report_roundtrip_and_negative_flag(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)

    incomes_before = np.array([100.0, 120.0, 150.0, 200.0, 400.0] * 4)
    incomes_after = incomes_before * np.array([0.9, 0.95, 1.0, 1.05, 1.1] * 4)
    breakdown = build_income_quintile_breakdown(incomes_before, incomes_after)

    report = build_distributional_report(
        [breakdown],
        incomes_before=np.array([10.0, -1.0, 5.0]),
        incomes_after=np.array([9.5, -0.5, 5.5]),
    )

    assert report.metadata.get("negative_values_present") is True
    assert report.overall_gini_before is None

    ref = persist_distributional_report(store, report)
    loaded = load_distributional_report(store, ref)

    assert loaded.breakdowns[0].dimension == CohortDimension.INCOME_QUINTILE
    assert loaded.winners_losers.total_winners_share >= 0.0


def test_distributional_report_carries_ordinal_poverty_summary() -> None:
    incomes_before = np.array([100.0, 120.0, 150.0, 200.0, 400.0] * 4)
    incomes_after = incomes_before * np.array([0.9, 0.95, 1.0, 1.05, 1.1] * 4)
    breakdown = build_income_quintile_breakdown(incomes_before, incomes_after)

    report = build_distributional_report(
        [breakdown],
        incomes_before=incomes_before,
        incomes_after=incomes_after,
        ordinal_poverty_summary={
            "status": "included",
            "baseline": {"ordinal_adjusted_headcount_q": 0.2},
            "counterfactual": {"ordinal_adjusted_headcount_q": 0.1},
        },
    )

    assert report.ordinal_poverty_summary["status"] == "included"
    assert report.ordinal_poverty_summary["baseline"]["ordinal_adjusted_headcount_q"] == pytest.approx(0.2)


def test_income_quintile_breakdown_handles_tied_incomes() -> None:
    incomes_before = np.ones(10)
    incomes_after = np.ones(10) * 2.0

    breakdown = build_income_quintile_breakdown(incomes_before, incomes_after)

    assert len(breakdown.cohorts) == 5
    assert [cohort.cohort_id for cohort in breakdown.cohorts] == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert sum(cohort.population_share for cohort in breakdown.cohorts) == pytest.approx(1.0)
    assert all(
        cohort.metric_deltas[breakdown.primary_metric] == pytest.approx(100.0)
        for cohort in breakdown.cohorts
    )


def test_geography_breakdown_uses_symmetric_percent_delta_for_negative_baselines() -> None:
    breakdown = build_geography_breakdown(
        region_ids=np.array([1, 1, 2, 2]),
        region_labels={1: "North", 2: "South"},
        metric_before=np.array([-100.0, -100.0, 50.0, 50.0]),
        metric_after=np.array([-50.0, -50.0, 75.0, 75.0]),
    )

    deltas = {cohort.cohort_id: cohort.metric_deltas[breakdown.primary_metric] for cohort in breakdown.cohorts}
    assert deltas["region_1"] == pytest.approx(66.6666666667)
    assert deltas["region_2"] == pytest.approx(50.0)
