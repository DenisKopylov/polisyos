from __future__ import annotations

import pytest
from polisyos.foundry.methods.backends.protocol import SolverStatus
from polisyos.foundry.methods.catalog.optimization.moment_dro import MomentConstrainedDROEstimator
from polisyos.foundry.methods.catalog.optimization.protocols import (
    AmbiguityCertificate,
    ConstraintCertificate,
    DiagnosticResult,
    MomentBound,
    MomentDROConstraint,
    MomentDROProblem,
    OptimizationResult,
)


def test_optimization_result_serializes_moment_ambiguity_certificate() -> None:
    certificate = AmbiguityCertificate(
        ambiguity_set_type="moment_mean_cov_support",
        confidence_level=0.95,
        overall_status="warn",
        moment_bounds=(
            MomentBound(
                name="shock_mean",
                order=1,
                estimator="catoni",
                point_estimate=[0.1, -0.2],
                confidence=0.95,
                sample_size=84,
            ),
        ),
        per_constraint=(
            ConstraintCertificate(
                name="budget",
                constraint_class="budget",
                formulation="dr_chance_scalar_moment",
                exactness="conservative_exact_for_scalarized_moments",
                worst_case_bound=95.0,
                threshold=100.0,
                slack=5.0,
                solver_family="SOCP",
                epsilon=0.05,
                violation_probability_bound=0.031,
            ),
        ),
        diagnostics=(
            DiagnosticResult(
                test_name="sample_size_heuristic",
                status="warn",
                message="Sample size is small relative to the shock dimension.",
            ),
        ),
        price_of_ambiguity=6.7,
    )
    result = OptimizationResult(
        status=SolverStatus.OPTIMAL,
        objective_value=12.5,
        variables={"x_0": 0.4},
        constraints_satisfied={"budget": True},
        solver_iterations=11,
        solver_gap=None,
        solver_time_seconds=0.12,
        ambiguity_certificate=certificate,
    )

    payload = result.to_payload()

    assert payload["ambiguity_certificate"] is not None
    assert payload["ambiguity_certificate"]["ambiguity_set_type"] == "moment_mean_cov_support"
    assert payload["ambiguity_certificate"]["per_constraint"][0]["name"] == "budget"
    assert payload["ambiguity_certificate"]["moment_bounds"][0]["estimator"] == "catoni"


def test_moment_constrained_dro_estimator_returns_ambiguity_certificate() -> None:
    pytest.importorskip("cvxpy")

    problem = MomentDROProblem(
        problem_id="fiscal_shock_policy",
        objective_vector=(1.0, 1.1),
        objective="maximize",
        bounds=((0.0, 1.0), (0.0, 1.0)),
        shock_mean=(0.0, 0.0),
        shock_covariance=((0.04, 0.0), (0.0, 0.04)),
        constraints=(
            MomentDROConstraint(
                name="budget",
                constraint_class="budget",
                nominal_coefficients=(0.6, 0.4),
                shock_matrix=((0.10, 0.05), (0.05, 0.10)),
                threshold=1.5,
                epsilon=0.05,
            ),
            MomentDROConstraint(
                name="equity_low_vs_high",
                constraint_class="equity",
                nominal_coefficients=(0.10, 0.10),
                shock_matrix=((0.02, 0.01), (0.01, 0.02)),
                threshold=0.40,
                epsilon=0.10,
            ),
            MomentDROConstraint(
                name="capacity_a",
                constraint_class="capacity",
                nominal_coefficients=(0.20, 0.40),
                shock_matrix=((0.04, 0.02), (0.02, 0.04)),
                threshold=0.85,
                epsilon=0.10,
            ),
            MomentDROConstraint(
                name="capacity_b",
                constraint_class="capacity",
                nominal_coefficients=(0.40, 0.20),
                shock_matrix=((0.04, 0.02), (0.02, 0.04)),
                threshold=0.85,
                epsilon=0.10,
            ),
        ),
        gamma_mean=0.10,
        gamma_covariance=1.0,
        confidence_level=0.95,
        sample_size=120,
    )

    result, solver_info = MomentConstrainedDROEstimator.pure_step(
        {"moment_dro_problem": problem},
        {"solver": "CLARABEL", "capacity_joint_mode": "bonferroni"},
    )

    assert result["status"] in {"optimal", "feasible"}
    assert result["ambiguity_certificate"] is not None
    assert result["ambiguity_certificate"]["overall_status"] in {"pass", "warn"}
    assert result["ambiguity_certificate"]["per_constraint"]
    assert any(
        item["constraint_class"] == "budget"
        for item in result["ambiguity_certificate"]["per_constraint"]
    )
    assert any(
        item["formulation"] == "joint_chance_bonferroni"
        for item in result["ambiguity_certificate"]["per_constraint"]
        if item["constraint_class"] == "capacity"
    )
    assert solver_info["solver"] == "CLARABEL"


def test_moment_dro_estimates_moments_from_historical_shocks_and_backtests() -> None:
    pytest.importorskip("cvxpy")

    problem = MomentDROProblem(
        problem_id="regime_aware_fiscal_shock_policy",
        objective_vector=(0.8, 1.0),
        objective="maximize",
        bounds=((0.0, 1.0), (0.0, 1.0)),
        historical_shocks=(
            (-0.08, 0.03),
            (-0.04, 0.02),
            (0.02, -0.01),
            (0.04, -0.02),
            (0.01, 0.01),
            (-0.02, 0.04),
            (0.20, 0.14),
            (0.24, 0.12),
            (0.18, 0.16),
            (0.28, 0.10),
            (0.22, 0.18),
            (0.19, 0.11),
        ),
        regime_ids=(
            "normal",
            "normal",
            "normal",
            "normal",
            "normal",
            "normal",
            "stress",
            "stress",
            "stress",
            "stress",
            "stress",
            "stress",
        ),
        regime_probabilities={"normal": 0.65, "stress": 0.35},
        moment_estimator="median_of_means",
        covariance_estimator="robust_cov_shrinkage",
        higher_moment_orders=(4,),
        backtest_hits={
            "budget": (0, 0, 1, 0, 0, 0, 0, 1, 0, 0),
        },
        constraints=(
            MomentDROConstraint(
                name="budget",
                constraint_class="budget",
                nominal_coefficients=(0.25, 0.20),
                shock_matrix=((0.03, 0.02), (0.02, 0.03)),
                threshold=1.2,
                epsilon=0.20,
            ),
            MomentDROConstraint(
                name="equity_gap",
                constraint_class="equity",
                nominal_coefficients=(0.05, 0.06),
                shock_matrix=((0.01, 0.01), (0.01, 0.01)),
                threshold=0.40,
                epsilon=0.20,
            ),
        ),
        gamma_mean=0.05,
        gamma_covariance=1.0,
        confidence_level=0.95,
    )

    result, _ = MomentConstrainedDROEstimator.pure_step(
        {"moment_dro_problem": problem},
        {"solver": "CLARABEL"},
    )

    certificate = result["ambiguity_certificate"]

    assert result["status"] in {"optimal", "feasible"}
    assert certificate["metadata"]["moment_source"] == "historical_shocks"
    assert certificate["regime_model"] == "declared_regime_ids"
    assert any(item["regime"] == "stress" for item in certificate["moment_bounds"])
    assert any(item["name"] == "shock_central_moment_4" for item in certificate["moment_bounds"])

    diagnostic_names = {item["test_name"] for item in certificate["diagnostics"]}
    assert "jarque_bera" in diagnostic_names
    assert "anderson_darling" in diagnostic_names
    assert "hill_tail_index" in diagnostic_names
    assert "kupiec_budget" in diagnostic_names
    assert "christoffersen_budget" in diagnostic_names
