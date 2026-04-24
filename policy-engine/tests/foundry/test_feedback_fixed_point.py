from __future__ import annotations

import numpy as np

from polisyos.core.contracts.foundry import (
    FeedbackConfig,
    FeedbackSolverConfig,
    FeedbackStateSnapshot,
    FeedbackVariableSpec,
)
from polisyos.foundry.feedback import MapEvaluation, prepare_feedback_config, solve_fixed_point


def test_hybrid_feedback_solver_converges_on_reflection_map() -> None:
    config = FeedbackConfig(
        variables=[
            FeedbackVariableSpec(
                variable_id="x",
                source_kind="state_path",
                source_ref="market.avg_wage",
                target_kind="state_path",
                target_ref="tax_rate",
                initial_value=1.0,
                lower_bound=0.0,
                upper_bound=1.0,
                scale=1.0,
            )
        ],
        solver=FeedbackSolverConfig(
            homotopy_grid=[0.0, 0.5, 1.0],
            damping_init=0.5,
            max_iter=20,
        ),
    )
    prepared = prepare_feedback_config(
        config,
        initial_state=FeedbackStateSnapshot(
            variable_ids=["x"],
            values=[1.0],
            scales=[1.0],
            lower_bounds=[0.0],
            upper_bounds=[1.0],
            weights=[1.0],
        ),
    )

    def evaluate(values: np.ndarray) -> MapEvaluation:
        x = float(values[0])
        return MapEvaluation(
            map_value=np.asarray([1.0 - x], dtype=float),
            diagnostics={"toy_map": "reflection"},
        )

    outcome = solve_fixed_point(prepared=prepared, evaluate_map=evaluate)

    assert outcome.converged is True
    assert np.allclose(outcome.solution, np.array([0.5], dtype=float))
    assert outcome.trace
    assert outcome.jacobian is not None
    assert outcome.jacobian.spectral_radius is not None
    assert outcome.jacobian.spectral_radius >= 0.99


def test_feedback_solver_reports_alternative_fixed_points_from_multi_start() -> None:
    config = FeedbackConfig(
        variables=[
            FeedbackVariableSpec(
                variable_id="x",
                source_kind="state_path",
                source_ref="market.avg_wage",
                target_kind="state_path",
                target_ref="tax_rate",
                initial_value=0.0,
                lower_bound=0.0,
                upper_bound=1.0,
                scale=1.0,
            )
        ],
        solver=FeedbackSolverConfig(
            homotopy_grid=[0.0, 1.0],
            max_iter=5,
            multi_start_values=[[1.0]],
            fixed_point_merge_tol=1.0e-6,
        ),
    )
    prepared = prepare_feedback_config(
        config,
        initial_state=FeedbackStateSnapshot(
            variable_ids=["x"],
            values=[0.0],
            scales=[1.0],
            lower_bounds=[0.0],
            upper_bounds=[1.0],
            weights=[1.0],
        ),
    )

    def evaluate(values: np.ndarray) -> MapEvaluation:
        return MapEvaluation(
            map_value=np.asarray(values, dtype=float),
            diagnostics={"toy_map": "identity"},
        )

    outcome = solve_fixed_point(prepared=prepared, evaluate_map=evaluate)

    assert outcome.converged is True
    assert outcome.final_diagnostics["multiple_fixed_points"] == 1
    assert len(outcome.alternative_solutions) == 1
    assert np.allclose(outcome.solution, np.asarray([0.0], dtype=float))
    assert np.allclose(outcome.alternative_solutions[0].solution, np.asarray([1.0], dtype=float))


def test_feedback_solver_respects_budget_aware_stopping_rule() -> None:
    config = FeedbackConfig(
        variables=[
            FeedbackVariableSpec(
                variable_id="x",
                source_kind="state_path",
                source_ref="market.avg_wage",
                target_kind="state_path",
                target_ref="tax_rate",
                initial_value=0.5,
                lower_bound=0.0,
                upper_bound=1.0,
                scale=1.0,
            )
        ],
        solver=FeedbackSolverConfig(
            homotopy_grid=[0.0, 1.0],
            max_iter=5,
            max_restarts=1,
            stagnation_patience=2,
            budget_diagnostic_id="budget_gap",
            budget_tolerance=0.1,
            compute_jacobian_diagnostics=False,
        ),
    )
    prepared = prepare_feedback_config(
        config,
        initial_state=FeedbackStateSnapshot(
            variable_ids=["x"],
            values=[0.5],
            scales=[1.0],
            lower_bounds=[0.0],
            upper_bounds=[1.0],
            weights=[1.0],
        ),
    )

    def evaluate(values: np.ndarray) -> MapEvaluation:
        return MapEvaluation(
            map_value=np.asarray(values, dtype=float),
            diagnostics={"budget_gap": 1.0},
            budget_gap=1.0,
        )

    outcome = solve_fixed_point(prepared=prepared, evaluate_map=evaluate)

    assert outcome.converged is False
    assert outcome.final_budget_gap == 1.0
    assert outcome.status in {"stagnated", "restarts_exhausted", "max_iter_exceeded"}
    assert outcome.failure_reason is not None
