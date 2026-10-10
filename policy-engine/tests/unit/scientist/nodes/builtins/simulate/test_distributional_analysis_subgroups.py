"""Behavior tests for aligned distributional subgroup projections."""

from __future__ import annotations

from dataclasses import replace

import jax.numpy as jnp
import numpy as np

from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.analytics.distributional import CohortDimension
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_subgroups import (
    _aligned_geography_subgroups,
    _build_aligned_geography_breakdown,
)


def _state_with_employer_ids(employer_ids: list[int]) -> GlobalState:
    state = GlobalState.empty(len(employer_ids), 3)
    return replace(
        state,
        agents=replace(
            state.agents,
            employer_id=jnp.asarray(employer_ids, dtype=jnp.int32),
        ),
    )


def test_geography_groups_and_breakdown_are_order_invariant() -> None:
    employer_ids = [0] * 10 + [1] * 10
    baseline_state = _state_with_employer_ids(employer_ids)
    simulated_state = _state_with_employer_ids(employer_ids)
    groups, warnings = _aligned_geography_subgroups(
        baseline_state=baseline_state,
        simulated_state=simulated_state,
    )

    assert warnings == []
    assert [(group.subgroup_id, int(group.mask.sum())) for group in groups] == [
        ("region_0", 10),
        ("region_1", 10),
    ]
    assert all(group.dimension is CohortDimension.GEOGRAPHY for group in groups)

    incomes_before = np.arange(10.0, 30.0)
    incomes_after = incomes_before + np.asarray([1.0] * 10 + [3.0] * 10)
    breakdown = _build_aligned_geography_breakdown(
        baseline_state=baseline_state,
        incomes_before=incomes_before,
        incomes_after=incomes_after,
        geography_groups=groups,
    )
    assert breakdown is not None
    assert breakdown.dimension is CohortDimension.GEOGRAPHY
    assert [cohort.cohort_id for cohort in breakdown.cohorts] == ["region_0", "region_1"]

    permutation = np.arange(len(employer_ids))[::-1]
    permuted_state = _state_with_employer_ids(np.asarray(employer_ids)[permutation].tolist())
    permuted_groups, permuted_warnings = _aligned_geography_subgroups(
        baseline_state=permuted_state,
        simulated_state=permuted_state,
    )
    assert permuted_warnings == []
    assert [group.subgroup_id for group in permuted_groups] == [
        group.subgroup_id for group in groups
    ]
    for original, permuted in zip(groups, permuted_groups, strict=True):
        np.testing.assert_array_equal(permuted.mask, original.mask[permutation])


def test_misaligned_geography_is_skipped_instead_of_joined_by_position() -> None:
    baseline_state = _state_with_employer_ids([0] * 10 + [1] * 10)
    misaligned_ids = [1, *([0] * 9), *([1] * 10)]
    simulated_state = _state_with_employer_ids(misaligned_ids)

    groups, warnings = _aligned_geography_subgroups(
        baseline_state=baseline_state,
        simulated_state=simulated_state,
    )

    assert groups == []
    assert warnings == [
        "Geography subgroup comparisons skipped: employer_id not aligned between snapshots"
    ]
    assert (
        _build_aligned_geography_breakdown(
            baseline_state=baseline_state,
            incomes_before=np.arange(10.0, 30.0),
            incomes_after=np.arange(11.0, 31.0),
            geography_groups=groups,
        )
        is None
    )
