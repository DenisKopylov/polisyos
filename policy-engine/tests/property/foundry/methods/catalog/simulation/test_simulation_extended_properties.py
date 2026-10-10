"""Property-based tests for stock-flow and bootstrap simulation methods."""

from __future__ import annotations

import sys

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method


class TestStockFlowProperties:
    @given(
        initial_stock=st.floats(min_value=10.0, max_value=10000.0, allow_nan=False),
        inflow_rate=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        outflow_rate=st.floats(min_value=0.0, max_value=0.5, allow_nan=False),
        n_steps=st.integers(min_value=5, max_value=50),
    )
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_stock_flow_output_finite(
        self, initial_stock, inflow_rate, outflow_rate, n_steps, isolated_registry,
        property_method_dispatcher,
    ):
        method = isolated_registry.get("simulation.system_dynamics.stock_flow@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={
                "initial_stocks": np.asarray([initial_stock, initial_stock / 2.0], dtype=float),
                "flow_matrix": np.asarray([[0.0, outflow_rate], [inflow_rate, 0.0]], dtype=float),
            },
            params={"n_steps": n_steps, "dt": 1.0},
            seed=42,
        )
        payload = result.output["result"]
        trajectory = np.asarray(payload["trajectory"], dtype=float)
        assert trajectory.shape == (n_steps + 1, 2)
        assert np.isfinite(trajectory).all()
        assert np.isfinite(np.asarray(payload["final_stocks"], dtype=float)).all()


class TestBootstrapProperties:
    @given(
        data=st.lists(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=100,
        ).map(np.array),
        n_boot=st.integers(min_value=50, max_value=200),
    )
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_bootstrap_ci_bounds_ordered(
        self, data, n_boot, isolated_registry, property_method_dispatcher
    ):
        method = isolated_registry.get("simulation.inference.bootstrap@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"data": data},
            params={
                "n_bootstrap": n_boot,
                "confidence_level": 0.99,
                "seed": 42,
            },
            seed=42,
        )
        interval = result.output["result"]
        assert interval["n_bootstrap"] == n_boot
        lo = float(interval["ci_lower"])
        hi = float(interval["ci_upper"])
        assert np.isfinite([lo, hi]).all()
        assert lo <= hi

    @given(
        data=st.lists(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=100,
        ).map(np.array),
    )
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_bootstrap_standard_error_non_negative(
        self, data, isolated_registry, property_method_dispatcher
    ):
        method = isolated_registry.get("simulation.inference.bootstrap@1.0.0")
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state={"data": data},
            params={"n_bootstrap": 100, "seed": 42},
            seed=42,
        )
        standard_error = float(result.output["result"]["bootstrap_se"])
        assert result.output["result"]["n_bootstrap"] == 100
        assert np.isfinite(standard_error)
        assert standard_error >= 0.0

    @given(
        data=st.lists(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=20,
            max_size=100,
        ).map(np.array),
    )
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_bootstrap_deterministic_with_seed(
        self, data, isolated_registry, property_method_dispatcher
    ):
        method = isolated_registry.get("simulation.inference.bootstrap@1.0.0")
        arguments = {
            "dispatcher": property_method_dispatcher,
            "method_class": method,
            "state": {"data": data},
            "params": {"n_bootstrap": 100, "seed": 42},
            "seed": 42,
        }
        first = invoke_property_method(**arguments).output["result"]
        second = invoke_property_method(**arguments).output["result"]
        assert first == second
        assert first["n_bootstrap"] == second["n_bootstrap"] == 100
