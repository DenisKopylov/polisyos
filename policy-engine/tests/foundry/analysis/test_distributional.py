from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.analysis.distributional import (
    build_distributional_report,
    build_income_quintile_breakdown,
    compute_gini,
    compute_palma_ratio,
)
from polisyos.ir.distributional import (
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
