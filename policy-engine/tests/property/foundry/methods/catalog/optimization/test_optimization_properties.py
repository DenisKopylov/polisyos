"""
Property-based tests for optimization methods:
- Stochastic programming (two-stage SP)
- Bilevel optimization
- Combinatorial (knapsack)
- Sequential dynamic programming
"""

from __future__ import annotations

import sys
from collections.abc import Mapping

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, assume, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")

sys.path.insert(0, "src")

from polisyos.foundry.methods.catalog.optimization.protocols import (
    AllocationItem,
    OptimizationProblem,
    ResourceConstraint,
)
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import _finite_array, lp_data_strategy


@st.composite
def feasible_milp_strategy(draw):
    """Generate a small feasible MILP with binary variables."""
    n_vars = draw(st.integers(min_value=2, max_value=5))
    n_constraints = draw(st.integers(min_value=1, max_value=4))
    c = draw(_finite_array((n_vars,), min_value=0.0, max_value=10.0))
    a_ub = draw(_finite_array((n_constraints, n_vars), min_value=0.0, max_value=5.0))
    b_ub = draw(_finite_array((n_constraints,), min_value=5.0, max_value=50.0))
    assume(np.all(b_ub > 0))
    return {"c": c, "A_ub": a_ub, "b_ub": b_ub, "n_vars": n_vars}


def _check_finite(value, path: str = "result") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _check_finite(nested, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple, np.ndarray)):
        array = np.asarray(value)
        if np.issubdtype(array.dtype, np.number):
            assert np.isfinite(array).all(), f"Non-finite numeric output at {path}"
        return
    if isinstance(value, (int, float, np.number)) and not isinstance(value, bool):
        assert np.isfinite(value), f"Non-finite numeric output at {path}"


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
                benefit=float(c[index]),
                min_units=0,
                max_units=1000,
                is_integer=False,
            )
            for index, item_id in enumerate(item_ids)
        ),
        constraints=tuple(
            ResourceConstraint(
                constraint_id=f"c{row_index}",
                coefficients={
                    item_id: float(a_ub[row_index, column_index])
                    for column_index, item_id in enumerate(item_ids)
                },
                bound=float(b_ub[row_index]),
                sense="<=",
            )
            for row_index in range(a_ub.shape[0])
        ),
        objective="maximize",
    )


def _two_stage_inputs(data: dict) -> dict[str, np.ndarray]:
    technology = np.maximum(np.asarray(data["A_ub"], dtype=float), 1e-3)
    n_demands, n_vars = technology.shape
    n_scenarios = 5
    return {
        "objective_vector": np.asarray(data["c"], dtype=float),
        "technology_matrix": technology,
        "scenario_demand_matrix": np.tile(
            np.maximum(np.asarray(data["b_ub"], dtype=float) * 0.1, 0.1), (n_scenarios, 1)
        ),
        "scenario_probabilities": np.full(n_scenarios, 1.0 / n_scenarios),
        "recourse_cost_vector": np.ones(n_demands, dtype=float),
        "bounds": np.tile(np.asarray([0.0, 1.0]), (n_vars, 1)),
    }


def _invoke(
    isolated_registry,
    property_method_dispatcher,
    fqn: str,
    state,
    bound_inputs: Mapping[str, object],
    params: dict,
    *,
    seed: int = 42,
):
    return invoke_property_method(
        dispatcher=property_method_dispatcher,
        method_class=isolated_registry.get(fqn),
        state=state,
        bound_inputs=bound_inputs,
        params=params,
        seed=seed,
    ).output


class TestStochasticProgrammingProperties:
    @given(data=lp_data_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_two_stage_sp_output_dict(self, data, isolated_registry, property_method_dispatcher):
        state = _two_stage_inputs(data)
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            "optimization.stochastic.two_stage_stochastic_program@1.0.0",
            state,
            state,
            {"solver": "CLARABEL"},
        )

        assert isinstance(output, dict)
        assert output["status"] == "optimal"
        assert np.isfinite(output["objective_value"])
        _check_finite(output)

    @given(data=lp_data_strategy())
    @settings(
        max_examples=15,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_two_stage_sp_keys_stable(self, data, isolated_registry, property_method_dispatcher):
        state = _two_stage_inputs(data)
        fqn = "optimization.stochastic.two_stage_stochastic_program@1.0.0"
        first = _invoke(
            isolated_registry,
            property_method_dispatcher,
            fqn,
            state,
            state,
            {"solver": "CLARABEL"},
            seed=42,
        )
        second = _invoke(
            isolated_registry,
            property_method_dispatcher,
            fqn,
            state,
            state,
            {"solver": "CLARABEL"},
            seed=42,
        )

        assert set(first) == set(second)
        assert first["status"] == second["status"] == "optimal"
        assert np.isclose(first["objective_value"], second["objective_value"], rtol=1e-6, atol=1e-6)
        assert set(first["variables"]) == set(second["variables"])
        np.testing.assert_allclose(
            list(first["variables"].values()),
            list(second["variables"].values()),
            rtol=1e-6,
            atol=1e-6,
        )


class TestCombinationalProperties:
    @given(
        n_items=st.integers(min_value=3, max_value=10),
        capacity=st.floats(min_value=5.0, max_value=50.0, allow_nan=False),
    )
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_knapsack_output_finite(
        self, n_items, capacity, isolated_registry, property_method_dispatcher
    ):
        fqn = "optimization.combinatorial.knapsack@1.0.0"
        values = np.arange(1.0, float(n_items) + 1.0, dtype=float)
        weights = np.full(n_items, 0.6 * capacity, dtype=float)
        state = {"values": values, "weights": weights}
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            fqn,
            state,
            state,
            {"capacity": capacity},
        )
        result = output["result"]
        selected = np.asarray(result["selected_items"], dtype=int)

        assert np.isfinite(result["total_value"])
        assert np.isfinite(result["total_weight"])
        assert np.all((selected >= 0) & (selected < n_items))
        assert result["total_weight"] <= capacity + 1e-9
        assert len(selected) == 1
        assert result["total_value"] == float(np.max(values))
        np.testing.assert_allclose(
            result["total_value"], values[selected].sum(), rtol=1e-7, atol=1e-7
        )

    @given(
        n_items=st.integers(min_value=3, max_value=10),
        capacity=st.floats(min_value=5.0, max_value=50.0, allow_nan=False),
    )
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_knapsack_result_is_dict(
        self, n_items, capacity, isolated_registry, property_method_dispatcher
    ):
        fqn = "optimization.combinatorial.knapsack@1.0.0"
        values = np.arange(1.0, float(n_items) + 1.0, dtype=float)
        weights = np.full(n_items, 0.6 * capacity, dtype=float)
        state = {"values": values, "weights": weights}
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            fqn,
            state,
            state,
            {"capacity": capacity},
        )
        result = output["result"]

        assert isinstance(output, dict)
        assert isinstance(result, dict)
        assert result["n_items"] == n_items
        assert isinstance(result["selected_items"], list)
        selected = np.asarray(result["selected_items"], dtype=int)
        assert np.all((selected >= 0) & (selected < n_items))
        assert result["total_weight"] <= capacity + 1e-9
        assert len(selected) == 1
        assert result["total_value"] == float(np.max(values))


class TestLPProperties:
    """Regression: LP standard form — optimal solution satisfies constraints."""

    @given(data=lp_data_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_lp_solution_feasible(self, data, isolated_registry, property_method_dispatcher):
        fqn = "optimization.linear.resource_lp@1.0.0"
        problem = _resource_problem(data)
        output = _invoke(
            isolated_registry,
            property_method_dispatcher,
            fqn,
            problem,
            {"optimization_problem": problem},
            {"prefer_ortools": False},
        )

        assert output["status"] == "optimal"
        variables = output["variables"]
        assert variables
        x = np.asarray([variables[f"x{i}"] for i in range(data["c"].shape[0])], dtype=float)
        assert np.all(np.isfinite(x))
        assert np.all(x >= -1e-6), "LP solution violates non-negativity"
        lhs = data["A_ub"] @ x
        assert np.all(lhs <= data["b_ub"] + 1e-6), "LP solution violates constraints"
