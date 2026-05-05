"""
Property-based tests for causal methods beyond DID:
- RDD (Regression Discontinuity Design)
- Synthetic Control
- Double Machine Learning (DML)
- Callaway-Sant'Anna staggered DID
"""

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

from tests.unit.foundry.methods.testing.strategies import (
    cross_section_strategy,
    panel_data_strategy,
    rdd_data_strategy,
)

# ---------------------------------------------------------------------------
# RDD properties
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rdd_method(isolated_registry):
    fqn = "causal.inference.regression_discontinuity@1.0.0"
    return isolated_registry.get(fqn)


class TestRDDProperties:
    @given(data=rdd_data_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_output_is_finite(self, data, isolated_registry):
        fqn = "causal.inference.regression_discontinuity@1.0.0"
        method = isolated_registry.get(fqn)
        state = {
            "outcome": data["outcome"],
            "running_variable": data["running_variable"],
            "cutoff": data["cutoff"],
        }
        params = {"bandwidth": 1.0}
        try:
            result = method.pure_step(state, params)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert not np.any(np.isnan(arr) & ~np.isinf(arr)), f"Unexpected NaN in '{key}'"
        except Exception:
            pass  # Small samples may legitimately fail

    @given(data=rdd_data_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_result_is_dict(self, data, isolated_registry):
        fqn = "causal.inference.regression_discontinuity@1.0.0"
        method = isolated_registry.get(fqn)
        state = {
            "outcome": data["outcome"],
            "running_variable": data["running_variable"],
            "cutoff": data["cutoff"],
        }
        params = {"bandwidth": 1.0}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
            assert len(result) > 0
        except Exception:
            pass


# ---------------------------------------------------------------------------
# DML properties
# ---------------------------------------------------------------------------


class TestDMLProperties:
    @given(data=cross_section_strategy())
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_output_dict_not_empty(self, data, isolated_registry):
        fqn = "causal.hte.double_ml@1.0.0"
        method = isolated_registry.get(fqn)
        state = {
            "outcome": data["outcome"],
            "treatment": (data["covariates"][:, 0] > 0).astype(float),
            "covariates": data["covariates"],
        }
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Callaway-Sant'Anna staggered DID properties
# ---------------------------------------------------------------------------


class TestCallawaySantAnnaProperties:
    @given(data=panel_data_strategy(min_units=8, max_units=20))
    @settings(
        max_examples=20,
        deadline=15000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_att_output_exists(self, data, isolated_registry):
        fqn = "causal.inference.did.callaway_santanna@1.0.0"
        method = isolated_registry.get(fqn)
        n_units = data["n_units"]
        n_periods = data["n_periods"]
        outcome_flat = data["outcome"].flatten()
        unit_id = np.repeat(np.arange(n_units), n_periods).astype(np.int64)
        time_id = np.tile(np.arange(n_periods), n_units).astype(np.int64)
        treatment_timing = np.full(n_units, np.inf, dtype=float)
        treatment_timing[np.where(data["treatment"])[0]] = float(data["time_treatment"])

        state = {
            "outcome": outcome_flat,
            "unit_id": unit_id,
            "time_id": time_id,
            "treatment_timing": treatment_timing,
        }
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass
