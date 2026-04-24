from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import SolverStatus
from polisyos.foundry.methods.catalog.optimization.advanced_stochastic import (
    BilevelOptimizationEstimator,
)
from polisyos.foundry.methods.catalog.optimization.convex import (
    _box_support_penalty_value,
    _ellipsoid_support_penalty_value,
    _legacy_penalized_nominal_certificate,
    _set_based_ambiguity_certificate,
)
from polisyos.foundry.methods.optimization import ensure_optimization_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.uncertainty import (
    RobustSetCalibrationMethod,
    RobustSetFamily,
    RobustSetSpec,
)


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def test_quadratic_program_and_robust_optimization_run() -> None:
    pytest.importorskip("cvxpy")

    ensure_optimization_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    state = {
        "objective_vector": np.array([1.0, 0.8, 0.2]),
        "quadratic_matrix": np.eye(3),
        "constraint_matrix": np.array([[1.0, 1.0, 1.0], [0.5, 0.2, 0.1]]),
        "constraint_rhs": np.array([1.5, 0.7]),
        "bounds": np.array([[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]]),
    }

    qp_cls = registry.get("optimization.convex.quadratic_program@1.0.0")
    qp_result = dispatcher.dispatch(
        method_class=qp_cls,
        signature=qp_cls.signature,
        state=state,
        params={},
        seed=89,
    )
    assert qp_result.output["status"] in {"optimal", "feasible"}

    robust_cls = registry.get("optimization.convex.robust_optimization@1.0.0")
    robust_result = dispatcher.dispatch(
        method_class=robust_cls,
        signature=robust_cls.signature,
        state={k: v for k, v in state.items() if k != "quadratic_matrix"},
        params={"uncertainty_radius": 0.1},
        seed=97,
    )
    assert robust_result.output["status"] in {"optimal", "feasible"}
    assert robust_result.output["metadata"]["model_semantics"] == "penalized_nominal"

    set_based_cls = registry.get("optimization.convex.set_based_robust_linear@1.0.0")
    set_based_result = dispatcher.dispatch(
        method_class=set_based_cls,
        signature=set_based_cls.signature,
        state={
            **{k: v for k, v in state.items() if k != "quadratic_matrix"},
            "robust_set_spec": {
                "family": RobustSetFamily.BOX.value,
                "size_parameter": 0.1,
                "center": state["objective_vector"].tolist(),
                "scale_diag": [1.0, 0.5, 1.5],
                "coverage_target": 0.9,
                "calibration_method": RobustSetCalibrationMethod.CONFORMAL.value,
            },
        },
        params={},
        seed=101,
    )
    assert set_based_result.output["status"] in {"optimal", "feasible"}
    assert set_based_result.output["metadata"]["model_semantics"] == "set_based_robust_counterpart"
    assert set_based_result.output["metadata"]["robust_set_family"] == RobustSetFamily.BOX.value
    assert set_based_result.output["ambiguity_certificate"]["ambiguity_set_type"] == "robust_box"
    assert set_based_result.output["ambiguity_certificate"]["price_of_robustness"] >= 0.0


def test_multiobjective_nsga2_runs() -> None:
    pytest.importorskip("pymoo")

    ensure_optimization_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    state = {
        "objective_matrix": np.array([[2.0, 1.0], [1.5, 2.5], [1.0, 1.8], [2.2, 0.5]]),
        "cost_vector": np.array([1.0, 1.2, 0.8, 1.1]),
        "budget": 2.3,
    }

    method_cls = registry.get("optimization.multiobjective.multiobjective_nsga2@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params={"n_generations": 20, "pop_size": 30},
        seed=101,
    )

    assert result.output["status"] in {"optimal", "feasible"}
    assert "pareto_front" in result.output["metadata"]


def test_box_support_penalty_exactness() -> None:
    vector = np.asarray([1.0, -2.0, 0.5], dtype=float)
    scale_diag = np.asarray([2.0, 0.5, 4.0], dtype=float)

    penalty = _box_support_penalty_value(vector, rho=0.3, scale_diag=scale_diag)

    assert penalty == pytest.approx(1.5)


def test_ellipsoid_support_penalty_exactness() -> None:
    vector = np.asarray([1.0, 2.0], dtype=float)
    covariance = np.asarray([[4.0, 0.0], [0.0, 9.0]], dtype=float)

    penalty = _ellipsoid_support_penalty_value(vector, rho=0.5, covariance=covariance)

    assert penalty == pytest.approx(0.5 * np.sqrt(40.0))


def test_set_based_robust_ambiguity_certificate_is_machine_readable() -> None:
    spec = {
        "family": RobustSetFamily.ELLIPSOID.value,
        "size_parameter": 2.0,
        "center": [1.0, 0.5],
        "covariance": [[0.25, 0.0], [0.0, 0.04]],
        "coverage_target": 0.9,
        "calibration_method": RobustSetCalibrationMethod.CONFORMAL.value,
    }

    certificate = _set_based_ambiguity_certificate(
        spec=RobustSetSpec.model_validate(spec),
        status=SolverStatus.OPTIMAL,
        support_penalty=0.42,
        solver_name="TEST",
        elapsed_seconds=0.01,
    )
    payload = certificate.to_payload()

    assert payload["ambiguity_set_type"] == "robust_ellipsoid"
    assert payload["overall_status"] == "pass"
    assert payload["price_of_robustness"] == pytest.approx(0.42)
    assert payload["diagnostics"][0]["test_name"] == "robust_set_geometry"


def test_legacy_robust_estimator_certificate_warns_about_semantics() -> None:
    certificate = _legacy_penalized_nominal_certificate(
        rho=0.2,
        solution=np.asarray([1.0, -2.0], dtype=float),
        solver_name="TEST",
        elapsed_seconds=0.01,
    )
    payload = certificate.to_payload()

    assert payload["overall_status"] == "warn"
    assert payload["metadata"]["coverage_certified"] is False
    assert payload["price_of_robustness"] == pytest.approx(0.6)


def test_bilevel_counterexample_switches_to_bounds() -> None:
    result = BilevelOptimizationEstimator.pure_step(
        {
            "c_upper": np.array([1.0], dtype=float),
            "c_lower": np.array([0.5], dtype=float),
            "A_upper": np.array([[1.0]], dtype=float),
            "b_upper": np.array([1.0], dtype=float),
            "A_lower": np.array([[1.0]], dtype=float),
            "b_lower": np.array([1.0], dtype=float),
            "follower_model": {
                "kind": "quartic_counterexample",
                "lambda": 10.0,
            },
        },
        {"ambiguity_mode": "auto"},
    )

    ambiguity_certificate = result["result"]["ambiguity_certificate"]

    assert ambiguity_certificate["mode"] == "leader_objective_bounds"
    assert result["result"]["objective_value"] is None
    assert result["result"]["point_solution_suppressed"] is True


def test_bilevel_counterexample_interval_matches_theory() -> None:
    result = BilevelOptimizationEstimator.pure_step(
        {
            "c_upper": np.array([1.0], dtype=float),
            "c_lower": np.array([0.5], dtype=float),
            "A_upper": np.array([[1.0]], dtype=float),
            "b_upper": np.array([1.0], dtype=float),
            "A_lower": np.array([[1.0]], dtype=float),
            "b_lower": np.array([1.0], dtype=float),
            "follower_model": {
                "kind": "quartic_double_well",
                "leader_weight": 10.0,
            },
        },
        {"ambiguity_mode": "auto"},
    )

    ambiguity_certificate = result["result"]["ambiguity_certificate"]

    assert ambiguity_certificate["incumbent_lower"] == pytest.approx(-10.0)
    assert ambiguity_certificate["incumbent_upper"] == pytest.approx(10.0)
    assert ambiguity_certificate["optimistic_value"] == pytest.approx(-10.0)
    assert ambiguity_certificate["pessimistic_value"] == pytest.approx(0.0)


def test_bilevel_generic_near_optimal_witnesses_switch_to_bounds() -> None:
    result = BilevelOptimizationEstimator.pure_step(
        {
            "c_upper": np.array([0.0], dtype=float),
            "c_lower": np.array([0.0], dtype=float),
            "A_upper": np.array([[1.0]], dtype=float),
            "b_upper": np.array([1.0], dtype=float),
            "A_lower": np.array([[1.0]], dtype=float),
            "b_lower": np.array([1.0], dtype=float),
            "lower_level_structure": {"nonconvex": True},
            "follower_value_upper": 0.05,
            "lower_level_response_witnesses": [
                {
                    "leader_objective": -3.0,
                    "follower_objective": 0.02,
                    "lower_feasible": True,
                },
                {
                    "leader_objective": 4.0,
                    "follower_objective": 0.04,
                    "lower_feasible": True,
                },
                {
                    "leader_objective": 100.0,
                    "follower_objective": 1.0,
                    "lower_feasible": True,
                },
            ],
        },
        {"ambiguity_mode": "auto", "delta_near_opt": 0.01},
    )

    ambiguity_certificate = result["result"]["ambiguity_certificate"]

    assert ambiguity_certificate["mode"] == "leader_objective_bounds"
    assert ambiguity_certificate["incumbent_lower"] == pytest.approx(-3.0)
    assert ambiguity_certificate["incumbent_upper"] == pytest.approx(4.0)
    assert ambiguity_certificate["witness_count"] == 2
    assert result["result"]["leader_objective_bounds_available"] is True


def test_nonconvex_epsilon_only_solver_forces_abstention_without_witnesses() -> None:
    result = BilevelOptimizationEstimator.pure_step(
        {
            "c_upper": np.array([1.0], dtype=float),
            "c_lower": np.array([0.0], dtype=float),
            "A_upper": np.array([[1.0]], dtype=float),
            "b_upper": np.array([1.0], dtype=float),
            "A_lower": np.array([[1.0]], dtype=float),
            "b_lower": np.array([1.0], dtype=float),
            "epsilon_feasible_only": True,
            "follower_global_gap": 1.0e-3,
        },
        {"ambiguity_mode": "auto", "follower_gap_tol": 1.0e-8},
    )

    ambiguity_certificate = result["result"]["ambiguity_certificate"]

    assert ambiguity_certificate["mode"] == "leader_objective_bounds"
    assert ambiguity_certificate["trigger"] == "epsilon_feasible_lower_level_only"
    assert ambiguity_certificate["incumbent_lower"] is None
    assert ambiguity_certificate["incumbent_upper"] is None
    assert result["result"]["objective_value"] is None
    assert result["result"]["leader_objective_bounds_available"] is False
    assert result["result"]["abstained_from_point_certificate"] is True


def test_nonconvex_epsilon_only_solver_uses_explicit_leader_bounds() -> None:
    result = BilevelOptimizationEstimator.pure_step(
        {
            "c_upper": np.array([1.0], dtype=float),
            "c_lower": np.array([0.0], dtype=float),
            "A_upper": np.array([[1.0]], dtype=float),
            "b_upper": np.array([1.0], dtype=float),
            "A_lower": np.array([[1.0]], dtype=float),
            "b_lower": np.array([1.0], dtype=float),
            "epsilon_feasible_only": True,
            "leader_objective_bounds": [-2.5, 8.0],
        },
        {"ambiguity_mode": "auto"},
    )

    ambiguity_certificate = result["result"]["ambiguity_certificate"]

    assert ambiguity_certificate["mode"] == "leader_objective_bounds"
    assert ambiguity_certificate["trigger"] == "explicit_leader_objective_bounds"
    assert ambiguity_certificate["incumbent_lower"] == pytest.approx(-2.5)
    assert ambiguity_certificate["incumbent_upper"] == pytest.approx(8.0)
    assert result["result"]["leader_objective_bounds_available"] is True
    assert result["result"]["abstained_from_point_certificate"] is False


def test_convex_unique_follower_keeps_point_mode() -> None:
    result = BilevelOptimizationEstimator.pure_step(
        {
            "c_upper": np.array([0.0, 0.0], dtype=float),
            "c_lower": np.array([0.0, 0.0], dtype=float),
            "A_upper": np.eye(2, dtype=float),
            "b_upper": np.ones(2, dtype=float),
            "A_lower": np.eye(2, dtype=float),
            "b_lower": np.ones(2, dtype=float),
        },
        {"ambiguity_mode": "auto"},
    )

    ambiguity_certificate = result["result"]["ambiguity_certificate"]

    assert ambiguity_certificate["mode"] == "none"
    assert result["result"]["objective_value"] == pytest.approx(0.0)
    assert result["result"]["point_solution_suppressed"] is False
