from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.optimization import ensure_optimization_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


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
