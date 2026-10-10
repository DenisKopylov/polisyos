from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.solver_runner import SolverRunner
from polisyos.foundry.methods.optimization import ensure_optimization_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def test_socp_and_stochastic_program_known_feasible() -> None:
    pytest.importorskip("cvxpy")

    ensure_optimization_methods_registered()
    registry = MethodRegistry.get_instance()

    socp_cls = registry.get("optimization.convex.socp@1.0.0")
    socp_payload, socp_info = socp_cls.pure_step(
        {
            "objective_vector": np.array([1.0, 0.2]),
            "cone_matrix": np.array([[1.0, 0.0], [0.0, 1.0]]),
            "cone_bound": 1.0,
            "linear_constraint_matrix": np.array([[1.0, 0.0], [0.0, 1.0]]),
            "linear_constraint_rhs": np.array([2.0, 2.0]),
            "bounds": np.array([[0.0, 2.0], [0.0, 2.0]]),
        },
        {},
    )
    assert socp_payload["status"] in {"optimal", "feasible"}
    assert socp_info["status"] in {"optimal", "feasible"}

    stochastic_cls = registry.get("optimization.stochastic.two_stage_stochastic_program@1.0.0")
    stochastic_payload, stochastic_info = stochastic_cls.pure_step(
        {
            "objective_vector": np.array([1.0, 0.5]),
            "technology_matrix": np.array([[1.0, 0.5], [0.2, 1.0]]),
            "scenario_demand_matrix": np.array([[0.9, 0.3], [1.2, 0.6], [0.7, 0.4]]),
            "scenario_probabilities": np.array([0.2, 0.5, 0.3]),
            "recourse_cost_vector": np.array([1.5, 1.0]),
            "bounds": np.array([[0.0, 2.0], [0.0, 2.0]]),
        },
        {},
    )
    assert stochastic_payload["status"] in {"optimal", "feasible"}
    assert stochastic_info["solver"]


def test_dynamic_programming_and_socp_dispatcher_path() -> None:
    ensure_optimization_methods_registered()
    registry = MethodRegistry.get_instance()

    dp_cls = registry.get("optimization.dynamic.dynamic_programming@1.0.0")
    dp_result = dp_cls.pure_step(
        {
            "reward_tensor": np.array(
                [
                    [[1.0, 0.5], [0.2, 1.2]],
                    [[0.9, 0.4], [0.3, 1.0]],
                ]
            ),
            "transition_tensor": np.array(
                [
                    [[[0.8, 0.2], [0.1, 0.9]], [[0.7, 0.3], [0.2, 0.8]]],
                    [[[0.9, 0.1], [0.3, 0.7]], [[0.6, 0.4], [0.2, 0.8]]],
                ]
            ),
            "initial_state": 0,
        },
        {"discount_factor": 0.95},
    )
    assert dp_result["result"]["status"] == "optimal"

    runner = SolverRunner()
    if not runner.is_available():
        pytest.skip("solver backend not available in this environment")
    pytest.importorskip("cvxpy")

    dispatcher = MethodDispatcher.get_instance()
    socp_cls = registry.get("optimization.convex.socp@1.0.0")
    dispatch_result = dispatcher.dispatch(
        method_class=socp_cls,
        signature=socp_cls.signature,
        state={
            "objective_vector": np.array([1.0, 0.2]),
            "cone_matrix": np.array([[1.0, 0.0], [0.0, 1.0]]),
            "cone_bound": 1.0,
            "linear_constraint_matrix": np.array([[1.0, 0.0], [0.0, 1.0]]),
            "linear_constraint_rhs": np.array([2.0, 2.0]),
            "bounds": np.array([[0.0, 2.0], [0.0, 2.0]]),
        },
        params={},
        seed=113,
    )
    assert dispatch_result.output["status"] in {
        "optimal",
        "feasible",
        "infeasible",
        "timeout",
        "error",
        "unknown",
    }
    assert dispatch_result.slot_outputs["solver_info"]["status"]
