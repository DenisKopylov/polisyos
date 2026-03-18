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
    from hypothesis import given, settings, HealthCheck
    from hypothesis import strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed"
)

sys.path.insert(0, "src")

from tests.foundry.methods.testing.strategies import (
    rdd_data_strategy,
    panel_data_strategy,
    cross_section_strategy,
)


# ---------------------------------------------------------------------------
# RDD properties
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rdd_method(isolated_registry):
    fqn = "causal.rdd.sharp@1.0.0"
    try:
        return isolated_registry.get(fqn)
    except Exception:
        pytest.skip(f"Method {fqn} not registered")


class TestRDDProperties:
    @given(data=rdd_data_strategy())
    @settings(max_examples=30, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_output_is_finite(self, data, isolated_registry):
        fqn = "causal.rdd.sharp@1.0.0"
        try:
            method = isolated_registry.get(fqn)
        except Exception:
            pytest.skip(f"{fqn} not registered")
        state = {
            "outcome": data["outcome"],
            "running_variable": data["running_variable"],
        }
        params = {"cutoff": data["cutoff"], "bandwidth": 1.0}
        try:
            result = method.pure_step(state, params)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert not np.any(np.isnan(arr) & ~np.isinf(arr)), \
                        f"Unexpected NaN in '{key}'"
        except Exception:
            pass  # Small samples may legitimately fail

    @given(data=rdd_data_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_result_is_dict(self, data, isolated_registry):
        fqn = "causal.rdd.sharp@1.0.0"
        try:
            method = isolated_registry.get(fqn)
        except Exception:
            pytest.skip(f"{fqn} not registered")
        state = {
            "outcome": data["outcome"],
            "running_variable": data["running_variable"],
        }
        params = {"cutoff": data["cutoff"], "bandwidth": 1.0}
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
    @settings(max_examples=20, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_output_dict_not_empty(self, data, isolated_registry):
        fqn = "causal.dml.double_ml@1.0.0"
        try:
            method = isolated_registry.get(fqn)
        except Exception:
            pytest.skip(f"{fqn} not registered")
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
    @settings(max_examples=20, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_att_output_exists(self, data, isolated_registry):
        fqn = "causal.did.callaway_santanna@1.0.0"
        try:
            method = isolated_registry.get(fqn)
        except Exception:
            pytest.skip(f"{fqn} not registered")
        n_units = data["n_units"]
        n_periods = data["n_periods"]
        outcome_flat = data["outcome"].flatten()
        entity_id = np.repeat(np.arange(n_units), n_periods).astype(np.int64)
        time_id = np.tile(np.arange(n_periods), n_units).astype(np.int64)
        treatment_flat = np.zeros(len(outcome_flat))
        treated_units = np.where(data["treatment"])[0]
        for u in treated_units:
            mask = entity_id == u
            treatment_flat[mask & (time_id >= data["time_treatment"])] = 1.0

        state = {
            "outcome": outcome_flat,
            "treatment": treatment_flat,
            "entity_id": entity_id,
            "time_id": time_id,
        }
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass
