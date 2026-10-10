"""Subgroup alignment and geography-breakdown helpers for distributional reports."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import ValidationError

from polisyos.foundry.analysis.distributional import (
    build_geography_breakdown,
)
from polisyos.ir.analytics import (
    CohortDimension,
)

_DISTRIBUTIONAL_EXECUTION_ERRORS = (RuntimeError, TypeError, ValueError, ValidationError)

_GEOGRAPHY_MIN_GROUP_SIZE = 10


@dataclass(frozen=True)
class _SubgroupSpec:
    dimension: CohortDimension
    subgroup_id: str
    subgroup_label: str
    mask: np.ndarray


def _income_quintile_subgroups(incomes_before: np.ndarray) -> list[_SubgroupSpec]:
    edges = np.percentile(incomes_before, [0, 20, 40, 60, 80, 100])
    groups: list[_SubgroupSpec] = []
    for index in range(5):
        lower = edges[index]
        upper = edges[index + 1]
        if index == 4:
            mask = incomes_before >= lower
        else:
            mask = (incomes_before >= lower) & (incomes_before < upper)
        if int(np.sum(mask)) == 0:
            continue
        groups.append(
            _SubgroupSpec(
                dimension=CohortDimension.INCOME_QUINTILE,
                subgroup_id=f"Q{index + 1}",
                subgroup_label=f"Q{index + 1} ({index * 20}-{(index + 1) * 20}%)",
                mask=mask,
            )
        )
    return groups


def _aligned_geography_subgroups(
    *,
    baseline_state: object,
    simulated_state: object,
) -> tuple[list[_SubgroupSpec], list[str]]:
    baseline_regions = getattr(getattr(baseline_state, "agents", object()), "employer_id", None)
    simulated_regions = getattr(getattr(simulated_state, "agents", object()), "employer_id", None)
    if baseline_regions is None or simulated_regions is None:
        return [], ["Geography subgroup comparisons skipped: employer_id missing"]

    baseline_arr = np.asarray(baseline_regions)
    simulated_arr = np.asarray(simulated_regions)
    if (
        baseline_arr.ndim != 1
        or simulated_arr.ndim != 1
        or baseline_arr.shape != simulated_arr.shape
    ):
        return [], ["Geography subgroup comparisons skipped: employer_id shape mismatch"]
    if not np.array_equal(baseline_arr, simulated_arr):
        return [], [
            "Geography subgroup comparisons skipped: employer_id not aligned between snapshots"
        ]

    groups: list[_SubgroupSpec] = []
    warnings: list[str] = []
    valid_mask = baseline_arr >= 0
    if int(np.sum(valid_mask)) < _GEOGRAPHY_MIN_GROUP_SIZE:
        return [], [
            "Geography subgroup comparisons skipped: insufficient aligned geography observations"
        ]

    for region in np.unique(baseline_arr[valid_mask]):
        mask = baseline_arr == region
        count = int(np.sum(mask))
        if count < _GEOGRAPHY_MIN_GROUP_SIZE:
            warnings.append(
                f"Geography subgroup {int(region)} skipped: only {count} observations (< {_GEOGRAPHY_MIN_GROUP_SIZE})"
            )
            continue
        groups.append(
            _SubgroupSpec(
                dimension=CohortDimension.GEOGRAPHY,
                subgroup_id=f"region_{int(region)}",
                subgroup_label=f"Employer Region {int(region)}",
                mask=mask,
            )
        )
    if len(groups) < 2:
        warnings.append(
            "Geography subgroup comparisons skipped: fewer than two sufficiently sized aligned regions"
        )
        return [], warnings
    return groups, warnings


def _build_aligned_geography_breakdown(
    *,
    baseline_state: object,
    incomes_before: np.ndarray,
    incomes_after: np.ndarray,
    geography_groups: list[_SubgroupSpec],
):
    if not geography_groups:
        return None
    region_ids = getattr(getattr(baseline_state, "agents", object()), "employer_id", None)
    if region_ids is None:
        return None
    region_ids_arr = np.asarray(region_ids)
    if region_ids_arr.ndim != 1 or region_ids_arr.shape[0] != incomes_after.shape[0]:
        return None
    retained_mask = np.zeros(region_ids_arr.shape[0], dtype=bool)
    labels: dict[int, str] = {}
    for group in geography_groups:
        retained_mask |= group.mask
        try:
            region_id = int(str(group.subgroup_id).removeprefix("region_"))
        except ValueError:
            continue
        labels[region_id] = group.subgroup_label
    if int(np.sum(retained_mask)) < (2 * _GEOGRAPHY_MIN_GROUP_SIZE):
        return None
    region_ids_clean = region_ids_arr[retained_mask]
    if np.unique(region_ids_clean).size < 2:
        return None
    try:
        return build_geography_breakdown(
            region_ids_clean,
            labels,
            incomes_before[retained_mask],
            incomes_after[retained_mask],
            primary_metric="regional_income_change_pct",
        )
    except _DISTRIBUTIONAL_EXECUTION_ERRORS:
        return None
