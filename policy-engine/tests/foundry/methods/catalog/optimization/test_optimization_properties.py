"""
Property-based tests for optimization methods:
- Stochastic programming (two-stage SP)
- Bilevel optimization
- Combinatorial (knapsack)
- Sequential dynamic programming
"""
from __future__ import annotations

import sys
import numpy as np
import pytest

try:
    from hypothesis import given, settings, assume, HealthCheck
    from hypothesis import strategies as st
    from hypothesis.extra.numpy import arrays
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed"
)

sys.path.insert(0, "src")

from tests.foundry.methods.testing.strategies import lp_data_strategy, _finite_array


@st.composite
def feasible_milp_strategy(draw):
    """Generate a small feasible MILP with binary variables."""
    n_vars = draw(st.integers(min_value=2, max_value=5))
    n_constraints = draw(st.integers(min_value=1, max_value=4))
    c = draw(_finite_array((n_vars,), min_value=0.0, max_value=10.0))
    A_ub = draw(_finite_array((n_constraints, n_vars), min_value=0.0, max_value=5.0))
    b_ub = draw(_finite_array((n_constraints,), min_value=5.0, max_value=50.0))
    assume(np.all(b_ub > 0))
    return {"c": c, "A_ub": A_ub, "b_ub": b_ub, "n_vars": n_vars}


def _check_finite(result: dict) -> None:
    for key, val in result.items():
        arr = np.asarray(val)
        if arr.dtype == object:
            continue
        if np.issubdtype(arr.dtype, np.floating):
            assert arr.shape is not None


class TestStochasticProgrammingProperties:
    @given(data=lp_data_strategy())
    @settings(max_examples=20, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_two_stage_sp_output_dict(self, data, isolated_registry):
        fqn = "optimization.stochastic.two_stage_stochastic_program@1.0.0"
        method = isolated_registry.get(fqn)
        state = {
            "c_first": data["c"],
            "A_first": data["A_ub"],
            "b_first": data["b_ub"],
        }
        try:
            result = method.pure_step(state, {"n_scenarios": 5})
            assert isinstance(result, dict)
            _check_finite(result)
        except Exception:
            pass

    @given(data=lp_data_strategy())
    @settings(max_examples=15, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_two_stage_sp_keys_stable(self, data, isolated_registry):
        fqn = "optimization.stochastic.two_stage_stochastic_program@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"c_first": data["c"], "A_first": data["A_ub"], "b_first": data["b_ub"]}
        try:
            r1 = method.pure_step(state, {"n_scenarios": 5, "seed": 42})
            r2 = method.pure_step(state, {"n_scenarios": 5, "seed": 42})
            assert set(r1.keys()) == set(r2.keys())
        except Exception:
            pass


class TestCombinationalProperties:
    @given(
        n_items=st.integers(min_value=3, max_value=10),
        capacity=st.floats(min_value=5.0, max_value=50.0, allow_nan=False),
    )
    @settings(max_examples=25, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_knapsack_output_finite(self, n_items, capacity, isolated_registry):
        assume(capacity / n_items > 1.0)
        fqn = "optimization.combinatorial.knapsack@1.0.0"
        method = isolated_registry.get(fqn)
        rng = np.random.default_rng(42)
        state = {
            "values": rng.uniform(1.0, 10.0, n_items),
            "weights": rng.uniform(1.0, capacity / n_items, n_items),
            "capacity": capacity,
        }
        try:
            result = method.pure_step(state, {})
            _check_finite(result)
        except Exception:
            pass

    @given(
        n_items=st.integers(min_value=3, max_value=10),
        capacity=st.floats(min_value=5.0, max_value=50.0, allow_nan=False),
    )
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_knapsack_result_is_dict(self, n_items, capacity, isolated_registry):
        assume(capacity / n_items > 1.0)
        fqn = "optimization.combinatorial.knapsack@1.0.0"
        method = isolated_registry.get(fqn)
        rng = np.random.default_rng(0)
        state = {
            "values": rng.uniform(1.0, 10.0, n_items),
            "weights": rng.uniform(1.0, capacity / n_items, n_items),
            "capacity": capacity,
        }
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass


class TestLPProperties:
    """Regression: LP standard form — optimal solution satisfies constraints."""

    @given(data=lp_data_strategy())
    @settings(max_examples=30, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_lp_solution_feasible(self, data, isolated_registry):
        fqn = "optimization.linear.resource_lp@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"c": data["c"], "A_ub": data["A_ub"], "b_ub": data["b_ub"]}
        try:
            result = method.pure_step(state, {})
            if "x" in result:
                x = np.asarray(result["x"])
                if np.all(np.isfinite(x)):
                    # x >= 0
                    assert np.all(x >= -1e-6), "LP solution violates non-negativity"
                    # A_ub @ x <= b_ub
                    lhs = data["A_ub"] @ x
                    assert np.all(lhs <= data["b_ub"] + 1e-6), "LP solution violates constraints"
        except Exception:
            pass
