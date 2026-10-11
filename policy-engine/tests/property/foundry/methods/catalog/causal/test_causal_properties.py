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
    from hypothesis import HealthCheck, assume, given, settings

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")

sys.path.insert(0, "src")

from polisyos.foundry.methods.catalog.causal.protocols import (
    HTEObservationalData,
    RDDObservationalData,
)
from polisyos.ir.analytics.causal import EstimationStatus
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import (
    cross_section_strategy,
    panel_data_strategy,
    rdd_data_strategy,
)

# ---------------------------------------------------------------------------
# RDD properties
# ---------------------------------------------------------------------------


class TestRDDProperties:
    @given(data=rdd_data_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_output_is_finite(self, data, isolated_registry, property_method_dispatcher):
        assume(int(data["n_obs"]) >= 30)
        fqn = "causal.inference.regression_discontinuity@1.0.0"
        method_class = isolated_registry.get(fqn)

        cutoff = float(data["cutoff"])
        running_variable = np.linspace(
            cutoff - 0.9, cutoff + 0.9, num=int(data["n_obs"]), dtype=float
        )
        original_treatment = (data["running_variable"] >= cutoff).astype(float)
        noise = data["outcome"] - data["running_variable"] * 0.5 - original_treatment * float(
            data["effect_true"]
        )
        outcome = (
            running_variable * 0.5
            + (running_variable >= cutoff).astype(float) * float(data["effect_true"])
            + noise
        )
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method_class,
            state=RDDObservationalData(
                outcome=np.zeros_like(outcome),
                running_variable=np.zeros_like(running_variable),
                cutoff=cutoff,
            ),
            bound_inputs={"outcome": outcome, "running_variable": running_variable},
            params={"bandwidth": 1.0, "manipulation_test": False},
            seed=42,
        )
        output = invocation.output
        report = output["report"]

        assert report.status is EstimationStatus.SUCCESS
        assert report.sample_size == data["n_obs"]
        assert np.isfinite(report.point_estimate)
        assert report.standard_error is not None and np.isfinite(report.standard_error)
        assert np.isfinite(np.asarray(report.confidence_interval, dtype=float)).all()

    @given(data=rdd_data_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_result_is_dict(self, data, isolated_registry, property_method_dispatcher):
        assume(int(data["n_obs"]) >= 30)
        fqn = "causal.inference.regression_discontinuity@1.0.0"
        method_class = isolated_registry.get(fqn)
        cutoff = float(data["cutoff"])
        running_variable = np.linspace(
            cutoff - 0.9, cutoff + 0.9, num=int(data["n_obs"]), dtype=float
        )
        original_treatment = (data["running_variable"] >= cutoff).astype(float)
        noise = data["outcome"] - data["running_variable"] * 0.5 - original_treatment * float(
            data["effect_true"]
        )
        outcome = (
            running_variable * 0.5
            + (running_variable >= cutoff).astype(float) * float(data["effect_true"])
            + noise
        )
        output = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method_class,
            state=RDDObservationalData(
                outcome=np.zeros_like(outcome),
                running_variable=np.zeros_like(running_variable),
                cutoff=cutoff,
            ),
            bound_inputs={"outcome": outcome, "running_variable": running_variable},
            params={"bandwidth": 1.0, "manipulation_test": False},
            seed=42,
        ).output

        assert isinstance(output, dict)
        assert output["report"].status is EstimationStatus.SUCCESS
        assert output["report"].estimand == "LATE"
        assert output["report"].sample_size == data["n_obs"]


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
    def test_output_dict_not_empty(self, data, isolated_registry, property_method_dispatcher):
        fqn = "causal.hte.double_ml@1.0.0"
        method_class = isolated_registry.get(fqn)
        n_obs = max(40, int(data["n_obs"]))
        rows = np.arange(n_obs) % int(data["n_obs"])
        treatment = np.resize(np.array([0, 1], dtype=int), n_obs)
        np.random.default_rng(42).shuffle(treatment)
        hte_data = HTEObservationalData(
            outcome=np.asarray(data["outcome"], dtype=float)[rows],
            treatment=treatment,
            covariates=np.asarray(data["covariates"], dtype=float)[rows],
        )
        output = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method_class,
            state=hte_data,
            bound_inputs={"hte_data": hte_data},
            params={},
            seed=42,
        ).output

        report = output["report"]
        if report.status is EstimationStatus.SUCCESS:
            hte_result = output["hte_result"]
            assert hte_result.n_samples == n_obs
            assert np.isfinite(hte_result.ate)
            assert np.isfinite(report.point_estimate)
        else:
            assert report.status is EstimationStatus.NUMERICAL_FAILURE
            assert (report.status_reason or "").startswith("Double ML backend unavailable:")


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
    def test_att_output_exists(self, data, isolated_registry, property_method_dispatcher):
        fqn = "causal.inference.did.callaway_santanna@1.0.0"
        method_class = isolated_registry.get(fqn)
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
        output = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method_class,
            state=state,
            bound_inputs=state,
            params={},
            seed=42,
        ).output

        assert isinstance(output, dict)
        aggregate = output["result"]
        assert aggregate["n_units"] == n_units
        assert aggregate["n_periods"] == n_periods
        assert np.isfinite(aggregate["aggregate_att"])
        assert aggregate["group_time_atts"]
        assert all(np.isfinite(row["att"]) for row in aggregate["group_time_atts"])
