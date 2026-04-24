from __future__ import annotations

import pytest

from polisyos.foundry.methods.backends.protocol import SolverStatus
from polisyos.foundry.methods.catalog.optimization.protocols import (
    AllocationItem,
    AmbiguityCertificate,
    AuctionFormatRecommendation,
    AuctionReserveProblem,
    ConstraintCertificate,
    DiagnosticResult,
    MomentBound,
    OptimizationAmbiguityCertificate,
    OptimizationProblem,
    OptimizationResult,
    ResourceConstraint,
)


def test_optimization_problem_rejects_unknown_item_in_constraint() -> None:
    with pytest.raises(ValueError, match="references unknown item"):
        OptimizationProblem(
            problem_id="p1",
            items=(AllocationItem(item_id="a", cost=1.0, benefit=1.0),),
            constraints=(
                ResourceConstraint(
                    constraint_id="c1",
                    coefficients={"missing": 1.0},
                    bound=1.0,
                ),
            ),
        )


def test_problem_from_mapping_parses_payload() -> None:
    payload = {
        "problem_id": "p2",
        "items": [
            {"item_id": "a", "cost": 2.0, "benefit": 5.0},
            {"item_id": "b", "cost": 1.0, "benefit": 2.0, "is_integer": False},
        ],
        "constraints": [
            {
                "constraint_id": "resource",
                "coefficients": {"a": 1.0, "b": 2.0},
                "bound": 3.0,
                "sense": "<=",
            }
        ],
        "objective": "maximize",
        "budget": 4.0,
    }
    problem = OptimizationProblem.from_mapping(payload)
    assert problem.problem_id == "p2"
    assert len(problem.items) == 2
    assert problem.budget == 4.0


def test_auction_reserve_problem_rejects_mismatched_row_width() -> None:
    with pytest.raises(ValueError, match="reserve_grid length"):
        AuctionReserveProblem(
            reserve_grid=(0.2, 0.5),
            scenario_revenues=((0.1,),),
        )


def test_optimization_result_serializes_ambiguity_certificate() -> None:
    result = OptimizationResult(
        status=SolverStatus.FEASIBLE,
        objective_value=None,
        variables={"x_0": 1.0},
        constraints_satisfied={"upper": True, "lower": True},
        solver_iterations=4,
        solver_gap=None,
        solver_time_seconds=0.02,
        ambiguity_certificate=OptimizationAmbiguityCertificate(
            mode="leader_objective_bounds",
            incumbent_lower=-10.0,
            incumbent_upper=0.0,
            optimistic_value=-10.0,
            pessimistic_value=0.0,
            trigger="nonconvex_follower_with_ambiguous_response",
            witness_count=2,
            note="Point bilevel certificate suppressed.",
        ),
    )

    payload = result.to_payload()

    assert payload["ambiguity_certificate"] is not None
    assert payload["ambiguity_certificate"]["mode"] == "leader_objective_bounds"
    assert payload["ambiguity_certificate"]["incumbent_lower"] == -10.0
    assert payload["ambiguity_certificate"]["incumbent_upper"] == 0.0


def test_optimization_result_serializes_rich_ambiguity_certificate() -> None:
    result = OptimizationResult(
        status=SolverStatus.OPTIMAL,
        objective_value=0.2,
        variables={"reserve": 0.2},
        constraints_satisfied={"revenue_floor": True},
        solver_iterations=3,
        solver_gap=None,
        solver_time_seconds=0.01,
        ambiguity_certificate=AmbiguityCertificate(
            ambiguity_set_type="hybrid",
            confidence_level=1.0,
            overall_status="warn",
            moment_bounds=(
                MomentBound(
                    name="scenario_expected_revenue",
                    order=1,
                    estimator="scenario_average",
                    point_estimate=(0.2, 0.4),
                    confidence=1.0,
                    sample_size=2,
                ),
            ),
            per_constraint=(
                ConstraintCertificate(
                    name="worst_case_revenue",
                    constraint_class="revenue",
                    formulation="scenario_maximin_lp",
                    exactness="exact",
                    worst_case_bound=0.2,
                    threshold=0.1,
                    slack=0.1,
                    solver_family="LP",
                ),
            ),
            diagnostics=(
                DiagnosticResult(
                    test_name="revenue_equivalence",
                    status="warn",
                    message="Secret reserve prevents format-level revenue equivalence.",
                ),
            ),
        ),
    )

    payload = result.to_payload()
    assert payload["ambiguity_certificate"] is not None
    assert payload["ambiguity_certificate"]["per_constraint"][0]["constraint_class"] == "revenue"
    assert payload["ambiguity_certificate"]["diagnostics"][0]["status"] == "warn"


def test_optimization_result_serializes_format_recommendation() -> None:
    result = OptimizationResult(
        status=SolverStatus.OPTIMAL,
        objective_value=0.4,
        variables={"reserve": 0.2},
        constraints_satisfied={"revenue_equivalence_conditions": True},
        solver_iterations=2,
        solver_gap=None,
        solver_time_seconds=0.01,
        format_recommendation=AuctionFormatRecommendation(
            uncertainty_regime="moderate",
            recommended_format="second_price",
            reserve_policy="public_downward_robustified",
            reserve_visibility="public",
            revenue_equivalence_holds=True,
            rationale="Public reserve keeps the standard benchmark while correcting reserve risk.",
            compared_formats=("second_price", "english"),
        ),
    )

    payload = result.to_payload()

    assert payload["format_recommendation"] is not None
    assert payload["format_recommendation"]["recommended_format"] == "second_price"
    assert payload["format_recommendation"]["reserve_policy"] == "public_downward_robustified"
