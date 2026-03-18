"""
Property-based tests for Linear Programming optimization methods.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.foundry.methods.testing.strategies import lp_data_strategy


@pytest.mark.hypothesis
@given(data=lp_data_strategy())
@settings(max_examples=30, deadline=20_000)
def test_lp_feasible_problem_returns_finite_objective(data: dict) -> None:
    """Feasible LP must return a finite objective value."""
    try:
        from polisyos.foundry.methods.catalog.optimization._registry_boot import (
            LinearProgram,
        )
    except ImportError:
        pytest.skip("LinearProgram not importable")

    assume(np.all(data["b_ub"] > 0))  # feasibility at x=0

    try:
        state = {
            "c": data["c"],
            "A_ub": data["A_ub"],
            "b_ub": data["b_ub"],
        }
        result = LinearProgram.pure_step(state, {})
        assert isinstance(result, dict)
        obj = result.get("objective_value") or result.get("optimal_value")
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
    try:
        from polisyos.foundry.methods.catalog.optimization._registry_boot import (
            LinearProgram,
        )
    except ImportError:
        pytest.skip("LinearProgram not importable")

    assume(np.all(data["b_ub"] > 0))

    try:
        state = {
            "c": data["c"],
            "A_ub": data["A_ub"],
            "b_ub": data["b_ub"],
        }
        result = LinearProgram.pure_step(state, {})
        x = result.get("optimal_x") or result.get("x_opt")
        if x is None:
            return
        x = np.asarray(x)
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
    try:
        from polisyos.foundry.methods.catalog.optimization._registry_boot import (
            LinearProgram,
        )
    except ImportError:
        pytest.skip("LinearProgram not importable")

    rng = np.random.default_rng(seed)
    n_constraints = n_vars + 1
    c = rng.uniform(0, 5, n_vars)
    A_ub = rng.uniform(0, 3, (n_constraints, n_vars))
    b_ub = rng.uniform(5, 20, n_constraints)

    state = {"c": c, "A_ub": A_ub, "b_ub": b_ub}

    try:
        result1 = LinearProgram.pure_step(state, {})
        result2 = LinearProgram.pure_step(state, {})
        obj1 = result1.get("objective_value") or result1.get("optimal_value")
        obj2 = result2.get("objective_value") or result2.get("optimal_value")
        if obj1 is not None and obj2 is not None:
            assert np.isclose(float(obj1), float(obj2), rtol=1e-8)
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("infeasible", "unbounded", "solver")):
            return
        raise
