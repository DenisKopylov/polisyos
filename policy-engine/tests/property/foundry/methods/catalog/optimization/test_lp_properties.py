"""
Property-based tests for Linear Programming optimization methods.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from polisyos.foundry.methods.catalog.optimization.protocols import (
    AllocationItem,
    OptimizationProblem,
    ResourceConstraint,
)
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import lp_data_strategy


def _resource_problem(data: dict) -> OptimizationProblem:
    c = np.asarray(data["c"], dtype=float)
    a_ub = np.asarray(data["A_ub"], dtype=float)
    b_ub = np.asarray(data["b_ub"], dtype=float)
    item_ids = [f"x{i}" for i in range(c.shape[0])]
    return OptimizationProblem(
        problem_id="property_lp",
        items=tuple(
            AllocationItem(
                item_id=item_id,
                cost=0.0,
                benefit=float(c[idx]),
                min_units=0,
                max_units=1000,
                is_integer=False,
            )
            for idx, item_id in enumerate(item_ids)
        ),
        constraints=tuple(
            ResourceConstraint(
                constraint_id=f"c{row_idx}",
                coefficients={
                    item_id: float(a_ub[row_idx, col_idx])
                    for col_idx, item_id in enumerate(item_ids)
                },
                bound=float(b_ub[row_idx]),
                sense="<=",
            )
            for row_idx in range(a_ub.shape[0])
        ),
        objective="maximize",
    )


def _solve_resource_lp(
    data: dict,
    *,
    isolated_registry,
    property_method_dispatcher,
    seed: int = 42,
) -> dict:
    fqn = "optimization.linear.resource_lp@1.0.0"
    problem = _resource_problem(data)
    return invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=isolated_registry.get(fqn),
        state=problem,
        bound_inputs={"optimization_problem": problem},
        params={"prefer_ortools": False},
        seed=seed,
    ).output


@pytest.mark.hypothesis
@given(data=lp_data_strategy())
@settings(
    max_examples=30,
    deadline=20_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_lp_feasible_problem_returns_finite_objective(
    data: dict, isolated_registry, property_method_dispatcher
) -> None:
    """A generated bounded LP returns a finite objective and optimal status."""
    result = _solve_resource_lp(
        data,
        isolated_registry=isolated_registry,
        property_method_dispatcher=property_method_dispatcher,
    )

    assert result["status"] == "optimal"
    assert result["objective_value"] is not None
    assert np.isfinite(float(result["objective_value"]))


@pytest.mark.hypothesis
@given(data=lp_data_strategy())
@settings(
    max_examples=20,
    deadline=20_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_lp_optimal_x_satisfies_constraints(
    data: dict, isolated_registry, property_method_dispatcher
) -> None:
    """The dispatched LP variables satisfy their declared bounds and constraints."""
    result = _solve_resource_lp(
        data,
        isolated_registry=isolated_registry,
        property_method_dispatcher=property_method_dispatcher,
    )

    assert result["status"] == "optimal"
    variables = result["variables"]
    assert variables
    x = np.asarray([variables[f"x{i}"] for i in range(data["c"].shape[0])], dtype=float)
    assert np.all(np.isfinite(x))
    assert np.all(x >= -1e-6)
    lhs = data["A_ub"] @ x
    assert np.all(lhs <= data["b_ub"] + 1e-6)


@pytest.mark.hypothesis
@given(
    n_vars=st.integers(min_value=2, max_value=6),
    seed=st.integers(min_value=0, max_value=99),
)
@settings(
    max_examples=20,
    deadline=15_000,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_lp_deterministic_given_same_seed(
    n_vars: int,
    seed: int,
    isolated_registry,
    property_method_dispatcher,
) -> None:
    """LP objective and variables are stable for the same typed request and seed."""
    rng = np.random.default_rng(seed)
    n_constraints = n_vars + 1
    data = {
        "c": rng.uniform(0, 5, n_vars),
        "A_ub": rng.uniform(0, 3, (n_constraints, n_vars)),
        "b_ub": rng.uniform(5, 20, n_constraints),
    }

    result1 = _solve_resource_lp(
        data,
        isolated_registry=isolated_registry,
        property_method_dispatcher=property_method_dispatcher,
        seed=seed,
    )
    result2 = _solve_resource_lp(
        data,
        isolated_registry=isolated_registry,
        property_method_dispatcher=property_method_dispatcher,
        seed=seed,
    )

    assert result1["status"] == result2["status"] == "optimal"
    assert np.isclose(result1["objective_value"], result2["objective_value"], rtol=1e-8, atol=1e-8)
    assert set(result1["variables"]) == set(result2["variables"])
    np.testing.assert_allclose(
        list(result1["variables"].values()),
        list(result2["variables"].values()),
        rtol=1e-8,
        atol=1e-8,
    )
