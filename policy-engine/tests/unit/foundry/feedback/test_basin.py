from __future__ import annotations

import numpy as np

from polisyos.core.contracts.foundry import (
    FeedbackConfig,
    FeedbackSolverConfig,
    FeedbackStateSnapshot,
    FeedbackVariableSpec,
)
from polisyos.foundry.feedback.basin import (
    BasinCluster,
    estimate_basin_shares,
    wilson_interval,
)
from polisyos.foundry.feedback.config import prepare_feedback_config


def _prepared():
    config = FeedbackConfig(
        variables=[
            FeedbackVariableSpec(
                variable_id="x",
                source_kind="state_path",
                source_ref="market.x",
                target_kind="state_path",
                target_ref="policy.x",
                initial_value=0.0,
                lower_bound=-2.0,
                upper_bound=2.0,
                scale=1.0,
            )
        ],
        solver=FeedbackSolverConfig(fixed_point_merge_tol=1.0e-3),
    )
    return prepare_feedback_config(
        config,
        initial_state=FeedbackStateSnapshot(
            variable_ids=["x"],
            values=[0.0],
            scales=[1.0],
            lower_bounds=[-2.0],
            upper_bounds=[2.0],
            weights=[1.0],
        ),
    )


def test_failed_and_unassigned_starts_remain_in_basin_draw_denominator() -> None:
    prepared = _prepared()
    starts = [np.asarray([value], dtype=float) for value in (0.0, 1.0, 2.0, 3.0)]
    cluster = BasinCluster(equilibrium_id="eq-zero", solution=np.asarray([0.0], dtype=float))

    def solve_start(
        start: np.ndarray,
    ) -> tuple[bool, str, np.ndarray, float | None]:
        marker = float(start[0])
        if marker == 1.0:
            return False, "max_iter_exceeded", np.asarray([1.0]), None
        if marker == 2.0:
            return True, "converged", np.asarray([0.25]), 0.0
        return True, "converged", np.asarray([0.0]), 0.0

    estimates, hits, assignments = estimate_basin_shares(
        prepared=prepared,
        clusters=[cluster],
        starts=starts,
        solve_start=solve_start,
    )

    assert [assignment.status for assignment in assignments] == [
        "assigned",
        "max_iter_exceeded",
        "unassigned",
        "assigned",
    ]
    assert [assignment.equilibrium_id for assignment in assignments] == [
        "eq-zero",
        None,
        None,
        "eq-zero",
    ]
    assert hits == {"eq-zero": 2}
    assert len(assignments) == 4
    assert len(estimates) == 1
    estimate = estimates[0]
    assert estimate.draws == 4
    assert estimate.hits == 2
    assert estimate.share_hat == 0.5
    assert estimate.ci_95 is not None
    assert estimate.ci_95.lower < estimate.share_hat < estimate.ci_95.upper


def test_empty_basin_draws_have_uninformative_wilson_bounds_without_solver_calls() -> None:
    prepared = _prepared()
    cluster = BasinCluster(equilibrium_id="eq-zero", solution=np.asarray([0.0], dtype=float))

    def unexpected_solve(_start: np.ndarray) -> tuple[bool, str, np.ndarray, float | None]:
        raise AssertionError("an empty draw set must not call the solver")

    estimates, hits, assignments = estimate_basin_shares(
        prepared=prepared,
        clusters=[cluster],
        starts=[],
        solve_start=unexpected_solve,
    )
    interval = wilson_interval(0, 0)

    assert hits == {"eq-zero": 0}
    assert assignments == []
    assert estimates[0].draws == 0
    assert estimates[0].hits == 0
    assert estimates[0].share_hat is None
    assert estimates[0].ci_95 is None
    assert interval.lower == 0.0
    assert interval.upper == 1.0
