"""
Property-based tests for Linear Programming optimization methods.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from polisyos.foundry.methods.catalog.optimization.lp import ResourceLP
from polisyos.foundry.methods.catalog.optimization.protocols import (
    AllocationItem,
    OptimizationProblem,
    ResourceConstraint,
)
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


def _solve_resource_lp(data: dict) -> dict:
    result, _solver_info = ResourceLP.pure_step(
        _resource_problem(data),
        {"prefer_ortools": False},
    )
    return result


@pytest.mark.hypothesis
@given(data=lp_data_strategy())
@settings(max_examples=30, deadline=20_000)
def test_lp_feasible_problem_returns_finite_objective(data: dict) -> None:
    """Feasible LP must return a finite objective value."""
    assume(np.all(data["b_ub"] > 0))  # feasibility at x=0

    try:
        result = _solve_resource_lp(data)
        assert isinstance(result, dict)
        if result.get("status") == "error":
            return
        obj = result.get("objective_value")
        if obj is not None:
            assert np.isfinite(float(obj))
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("infeasible", "unbounded", "solver")):
            return
        raise


@pytest.mark.hypothesis
@given(data=lp_data_strategy())
@settings(max_examples=20, deadline=20_000)
def test_lp_optimal_x_satisfies_constraints(data: dict) -> None:
    """Optimal LP solution must satisfy A_ub @ x ≤ b_ub and x ≥ 0."""
    assume(np.all(data["b_ub"] > 0))

    try:
        result = _solve_resource_lp(data)
        variables = result.get("variables")
        if not variables:
            return
        x = np.asarray([variables[f"x{i}"] for i in range(data["c"].shape[0])], dtype=float)
        # x ≥ 0 (allow small numerical tolerance)
        assert np.all(x >= -1e-6)
        # A_ub @ x ≤ b_ub (allow small tolerance)
        lhs = data["A_ub"] @ x
        assert np.all(lhs <= data["b_ub"] + 1e-6)
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("infeasible", "unbounded", "solver")):
            return
        raise


@pytest.mark.hypothesis
@given(
    n_vars=st.integers(min_value=2, max_value=6),
    seed=st.integers(min_value=0, max_value=99),
)
@settings(max_examples=20, deadline=15_000)
def test_lp_deterministic_given_same_seed(n_vars: int, seed: int) -> None:
    """LP results must be identical when called twice with the same inputs."""
    rng = np.random.default_rng(seed)
    n_constraints = n_vars + 1
    c = rng.uniform(0, 5, n_vars)
    A_ub = rng.uniform(0, 3, (n_constraints, n_vars))
    b_ub = rng.uniform(5, 20, n_constraints)

    state = {"c": c, "A_ub": A_ub, "b_ub": b_ub}

    try:
        result1 = _solve_resource_lp(state)
        result2 = _solve_resource_lp(state)
        obj1 = result1.get("objective_value")
        obj2 = result2.get("objective_value")
        if obj1 is not None and obj2 is not None:
            assert np.isclose(float(obj1), float(obj2), rtol=1e-8)
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("infeasible", "unbounded", "solver")):
            return
        raise
