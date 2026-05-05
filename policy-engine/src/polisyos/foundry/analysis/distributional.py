"""Public analysis distributional module API."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from polisyos.foundry.runtime.numeric import economic_percent_delta
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    DimensionBreakdown,
    DistributionalReport,
    ImpactDirection,
    MetricUnit,
    WinnersLosersEntry,
    WinnersLosersTable,
)


def compute_gini(values: np.ndarray) -> float | None:
    """
    Compute the classical Gini coefficient for non-negative values.

    Returns None when negative values are present because classical Gini
    interpretation is unstable for negative-income distributions.
    """
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return 0.0
    if np.any(~np.isfinite(arr)):
        return None
    if np.any(arr < 0):
        return None
    total = float(np.sum(arr))
    if total <= 0:
        return 0.0
    sorted_values = np.sort(arr)
    n = sorted_values.size
    index = np.arange(1, n + 1, dtype=np.float64)
    gini = (2.0 * np.sum(index * sorted_values) / (n * total)) - (n + 1.0) / n
    return float(max(0.0, min(1.0, gini)))


def compute_palma_ratio(values: np.ndarray, *, eps: float = 1e-9) -> float | None:
    """
    Compute Palma ratio: income share of top 10% / bottom 40%.
    """
    arr = np.asarray(values, dtype=np.float64)
    if arr.size < 10:
        return None
    if np.any(~np.isfinite(arr)):
        return None
    if np.any(arr < 0):
        return None
    sorted_values = np.sort(arr)
    n = sorted_values.size
    bottom_40 = float(np.sum(sorted_values[: int(n * 0.4)]))
    top_10 = float(np.sum(sorted_values[int(n * 0.9) :]))
    if bottom_40 <= eps:
        return None
    return float(top_10 / bottom_40)


def build_income_quintile_breakdown(
    incomes_before: np.ndarray,
    incomes_after: np.ndarray,
    *,
    primary_metric: str = "disposable_income_change_pct",
    vulnerable_quintiles: frozenset[int] = frozenset({0}),
) -> DimensionBreakdown:
    """Build income quintile breakdown."""
    incomes_before = np.asarray(incomes_before, dtype=np.float64)
    incomes_after = np.asarray(incomes_after, dtype=np.float64)
    if incomes_before.shape != incomes_after.shape:
        raise ValueError("incomes_before and incomes_after must have equal shape")
    if incomes_before.ndim != 1:
        raise ValueError("income arrays must be 1D")
    n = incomes_before.size
    if n < 10:
        raise ValueError("income breakdown requires at least 10 agents")

    labels = [
        "Q1 (0-20%)",
        "Q2 (20-40%)",
        "Q3 (40-60%)",
        "Q4 (60-80%)",
        "Q5 (80-100%)",
    ]
    order = np.argsort(incomes_before, kind="stable")
    quintile_indices = np.array_split(order, 5)

    cohorts: list[CohortImpact] = []
    for idx in range(5):
        cohort_idx = quintile_indices[idx]
        count = int(cohort_idx.size)
        before_mean = float(np.mean(incomes_before[cohort_idx]))
        after_mean = float(np.mean(incomes_after[cohort_idx]))
        delta_pct = economic_percent_delta(before_mean, after_mean)
        direction = (
            ImpactDirection.POSITIVE
            if delta_pct > 0.5
            else ImpactDirection.NEGATIVE
            if delta_pct < -0.5
            else ImpactDirection.NEUTRAL
        )
        cohorts.append(
            CohortImpact(
                cohort_id=f"Q{idx + 1}",
                cohort_label=labels[idx],
                population_share=count / n,
                metric_values={
                    "mean_income_before": before_mean,
                    "mean_income_after": after_mean,
                },
                metric_deltas={primary_metric: delta_pct},
                impact_direction=direction,
                is_vulnerable=idx in vulnerable_quintiles,
            )
        )

    return DimensionBreakdown(
        dimension=CohortDimension.INCOME_QUINTILE,
        dimension_label="Income Quintiles",
        cohorts=cohorts,
        primary_metric=primary_metric,
        primary_metric_unit=MetricUnit.PERCENT,
        gini_before=compute_gini(incomes_before),
        gini_after=compute_gini(incomes_after),
    )


def build_geography_breakdown(
    region_ids: np.ndarray,
    region_labels: dict[int, str],
    metric_before: np.ndarray,
    metric_after: np.ndarray,
    *,
    primary_metric: str = "regional_income_change_pct",
    vulnerable_regions: frozenset[int] = frozenset(),
) -> DimensionBreakdown:
    """Build geography breakdown."""
    region_ids = np.asarray(region_ids)
    metric_before = np.asarray(metric_before, dtype=np.float64)
    metric_after = np.asarray(metric_after, dtype=np.float64)
    if region_ids.ndim != 1:
        raise ValueError("region_ids must be 1D")
    if metric_before.shape != metric_after.shape or metric_before.shape[0] != region_ids.shape[0]:
        raise ValueError("region arrays and metric arrays must align")
    n = region_ids.size
    unique = np.unique(region_ids)
    if unique.size < 2:
        raise ValueError("geography breakdown requires at least 2 regions")

    cohorts: list[CohortImpact] = []
    for region in unique:
        mask = region_ids == region
        count = int(np.sum(mask))
        if count == 0:
            continue
        before_mean = float(np.mean(metric_before[mask]))
        after_mean = float(np.mean(metric_after[mask]))
        delta_pct = economic_percent_delta(before_mean, after_mean)
        direction = (
            ImpactDirection.POSITIVE
            if delta_pct > 0.5
            else ImpactDirection.NEGATIVE
            if delta_pct < -0.5
            else ImpactDirection.NEUTRAL
        )
        region_int = int(region)
        cohorts.append(
            CohortImpact(
                cohort_id=f"region_{region_int}",
                cohort_label=region_labels.get(region_int, f"Region {region_int}"),
                population_share=count / n,
                metric_values={"mean_before": before_mean, "mean_after": after_mean},
                metric_deltas={primary_metric: delta_pct},
                impact_direction=direction,
                is_vulnerable=region_int in vulnerable_regions,
            )
        )

    return DimensionBreakdown(
        dimension=CohortDimension.GEOGRAPHY,
        dimension_label="Geographic Regions",
        cohorts=cohorts,
        primary_metric=primary_metric,
        primary_metric_unit=MetricUnit.PERCENT,
    )


def build_winners_losers_table(
    breakdowns: Sequence[DimensionBreakdown],
    *,
    neutral_threshold: float = 0.5,
    canonical_dimension: CohortDimension | None = CohortDimension.INCOME_QUINTILE,
) -> WinnersLosersTable:
    """Build winners losers table."""
    winners: list[WinnersLosersEntry] = []
    losers: list[WinnersLosersEntry] = []
    neutral: list[WinnersLosersEntry] = []

    for breakdown in breakdowns:
        if canonical_dimension is not None and breakdown.dimension != canonical_dimension:
            continue
        for cohort in breakdown.cohorts:
            delta = cohort.metric_deltas.get(breakdown.primary_metric, 0.0)
            entry = WinnersLosersEntry(
                cohort_id=cohort.cohort_id,
                cohort_label=cohort.cohort_label,
                dimension=breakdown.dimension,
                net_impact=delta,
                impact_direction=cohort.impact_direction,
                population_share=cohort.population_share,
                is_vulnerable=cohort.is_vulnerable,
                key_metric=breakdown.primary_metric,
                key_metric_delta=delta,
            )
            if delta > neutral_threshold:
                winners.append(entry)
            elif delta < -neutral_threshold:
                losers.append(entry)
            else:
                neutral.append(entry)

    winners.sort(key=lambda item: item.net_impact, reverse=True)
    losers.sort(key=lambda item: item.net_impact)

    return WinnersLosersTable(
        winners=winners,
        losers=losers,
        neutral=neutral,
        canonical_dimension=canonical_dimension,
    )


def build_distributional_report(
    breakdowns: Sequence[DimensionBreakdown],
    *,
    incomes_before: np.ndarray | None = None,
    incomes_after: np.ndarray | None = None,
    ordinal_poverty_summary: dict[str, Any] | None = None,
    source_simulation_ref: str | None = None,
    methodology: str = "agent_aggregation",
    metadata: dict[str, Any] | None = None,
) -> DistributionalReport:
    """Build distributional report."""
    report_metadata = dict(metadata or {})
    overall_gini_before = None
    overall_gini_after = None
    palma_before = None
    palma_after = None

    if incomes_before is not None and incomes_after is not None:
        arr_before = np.asarray(incomes_before, dtype=np.float64)
        arr_after = np.asarray(incomes_after, dtype=np.float64)
        report_metadata["negative_values_present"] = bool(
            np.any(arr_before < 0) or np.any(arr_after < 0)
        )
        overall_gini_before = compute_gini(arr_before)
        overall_gini_after = compute_gini(arr_after)
        palma_before = compute_palma_ratio(arr_before)
        palma_after = compute_palma_ratio(arr_after)

    winners_losers = build_winners_losers_table(breakdowns)
    return DistributionalReport(
        breakdowns=list(breakdowns),
        winners_losers=winners_losers,
        overall_gini_before=overall_gini_before,
        overall_gini_after=overall_gini_after,
        palma_ratio_before=palma_before,
        palma_ratio_after=palma_after,
        ordinal_poverty_summary=dict(ordinal_poverty_summary or {}),
        source_simulation_ref=source_simulation_ref,
        methodology=methodology,
        metadata=report_metadata,
    )


__all__ = [
    "build_distributional_report",
    "build_geography_breakdown",
    "build_income_quintile_breakdown",
    "build_winners_losers_table",
    "compute_gini",
    "compute_palma_ratio",
]
