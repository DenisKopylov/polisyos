from __future__ import annotations

import numpy as np

from polisyos.core.contracts.foundry import (
    FeedbackConfig,
    FeedbackSolverConfig,
    FeedbackStateSnapshot,
    FeedbackVariableSpec,
)
from polisyos.foundry.feedback import (
    MapEvaluation,
    MultiplicityExplorer,
    discover_equilibria,
    prepare_feedback_config,
    solve_fixed_point,
)
from polisyos.foundry.feedback.continuation import (
    ContinuationPoint,
    build_nearest_neighbor_branches,
    pseudo_arclength_predictor,
)


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


def test_multiplicity_explorer_clusters_fixed_points_and_estimates_basins() -> None:
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
            damping_init=1.0,
            max_iter=12,
            multi_start_values=[[1.0]],
            fixed_point_merge_tol=1.0e-6,
            detect_multiplicity=True,
            multiplicity_max_attempts=2,
            multiplicity_sobol_draws=0,
            basin_draws=6,
            compute_jacobian_diagnostics=True,
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
        fixed_point = 0.0 if float(values[0]) < 0.5 else 1.0
        return MapEvaluation(
            map_value=np.asarray([fixed_point], dtype=float),
            diagnostics={"toy_map": "two_basin"},
        )

    report = discover_equilibria(prepared=prepared, evaluate_map=evaluate)

    assert report.global_diagnostics.num_attempts == 2
    assert report.global_diagnostics.num_equilibria == 2
    assert {candidate.local_stability for candidate in report.equilibria} == {"attractive"}
    assert len(report.basin_estimates) == 2
    assert sum(estimate.hits for estimate in report.basin_estimates) == 6
    assert all(estimate.ci_95 is not None for estimate in report.basin_estimates)

    explorer_report = MultiplicityExplorer(
        prepared=prepared,
        evaluate_map=evaluate,
        model_id="two_basin_unit_test",
    ).run()
    assert explorer_report.model_id == "two_basin_unit_test"
    assert explorer_report.global_diagnostics.num_equilibria == 2


def test_continuation_helpers_predict_and_link_branches() -> None:
    previous = ContinuationPoint(
        lambda_value=0.0,
        equilibrium_id="eq_001",
        solution=np.asarray([1.0], dtype=float),
    )
    current = ContinuationPoint(
        lambda_value=0.5,
        equilibrium_id="eq_002",
        solution=np.asarray([1.5], dtype=float),
    )

    prediction = pseudo_arclength_predictor(previous, current, next_lambda=1.0)
    assert np.allclose(prediction, np.asarray([2.0], dtype=float))

    branches = build_nearest_neighbor_branches(
        [
            (0.0, [("eq_001", np.asarray([1.0], dtype=float))]),
            (0.5, [("eq_002", np.asarray([1.0 + 1.0e-7], dtype=float))]),
        ],
        merge_tol=1.0e-5,
    )
    assert len(branches) == 1
    assert [point.equilibrium_id for point in branches[0].points] == ["eq_001", "eq_002"]


def test_multiplicity_explorer_tracks_parameterized_continuation_branches() -> None:
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
            damping_init=1.0,
            max_iter=10,
            multi_start_values=[[1.0]],
            fixed_point_merge_tol=1.0e-6,
            detect_multiplicity=True,
            multiplicity_mode="continuation",
            multiplicity_max_attempts=4,
            multiplicity_sobol_draws=0,
            continuation_parameter="aggregate_shock_sd",
            continuation_grid=[0.0, 0.5, 1.0],
            compute_jacobian_diagnostics=True,
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

    def map_factory(lambda_value: float):
        def evaluate(values: np.ndarray) -> MapEvaluation:
            x = float(values[0])
            fixed_point = 0.2 + 0.1 * lambda_value if x < 0.5 else 0.8 - 0.1 * lambda_value
            return MapEvaluation(
                map_value=np.asarray([fixed_point], dtype=float),
                diagnostics={"lambda": lambda_value},
            )

        return evaluate

    report = discover_equilibria(
        prepared=prepared,
        evaluate_map=map_factory(0.0),
        continuation_map_factory=map_factory,
    )

    assert report.search_protocol.mode == "continuation"
    assert report.global_diagnostics.num_equilibria == 6
    assert len(report.branches) == 2
    assert sorted(len(branch.points) for branch in report.branches) == [3, 3]
    assert "continuation_engine:pseudo_arclength_predictor" in report.notes
