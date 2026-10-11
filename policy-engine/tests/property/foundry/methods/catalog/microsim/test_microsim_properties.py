"""Property-based tests for microsimulation methods: tax-benefit and static micro."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings

from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreakerRegistry
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.microsim import SurveyMicroData
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import microsim_strategy


def _fresh_property_dispatcher() -> MethodDispatcher:
    """Isolate one invalid Hypothesis example from prior backend failures."""
    CircuitBreakerRegistry.reset_instance()
    return MethodDispatcher(enable_runtime_selection=False)


def _run_calibrated_static(data, registry, dispatcher):
    income = np.asarray(data["income"], dtype=float) + np.linspace(1.0, 2.0, int(data["n_agents"]))
    weights = np.ones_like(income, dtype=float)
    survey = SurveyMicroData(market_income=income, weights=weights)
    calibration_method = registry.get("microsim.calibration.reweighting_calibration@1.0.0")
    calibration = invoke_property_method(
        dispatcher=dispatcher,
        method_class=calibration_method,
        state=survey,
        bound_inputs={"market_income": income, "weights": weights},
        params={
            "target_total_weight": float(weights.sum()),
            "target_mean_income": float(income.mean()),
        },
        seed=79,
    ).output
    calibrated_weights = np.asarray(calibration["weights"], dtype=float)
    calibrated_state = survey.model_copy(
        update={
            "weights": calibrated_weights,
            "microsim_calibration_report": calibration["microsim_calibration_report"],
            "microsim_calibration_report_ref": calibration["microsim_calibration_report_ref"],
        }
    )
    static_method = registry.get("microsim.static.static_microsim@1.0.0")
    return invoke_property_method(
        dispatcher=dispatcher,
        method_class=static_method,
        state=calibrated_state,
        bound_inputs={"market_income": income, "weights": calibrated_weights},
        params={},
        seed=83,
    ).output


class TestTaxBenefitProperties:
    @given(data=microsim_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tax_benefit_output_finite(self, data, isolated_registry, property_method_dispatcher):
        method = isolated_registry.get("microsim.policy.tax_benefit_calculator@1.0.0")
        income = np.asarray(data["income"], dtype=float)
        weights = np.ones_like(income, dtype=float)
        state = SurveyMicroData(market_income=income, weights=weights)
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            bound_inputs={"market_income": income, "weights": weights},
            params={},
            seed=17,
        ).output
        for key in ("disposable_income", "tax_liability", "benefit_income", "effective_tax_rate"):
            values = np.asarray(result[key], dtype=float)
            assert values.shape == income.shape
            assert np.all(np.isfinite(values))

    @given(data=microsim_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tax_benefit_disposable_income_non_negative(
        self, data, isolated_registry, property_method_dispatcher
    ):
        """Disposable income is non-negative under the declared tax-benefit schedule."""
        method = isolated_registry.get("microsim.policy.tax_benefit_calculator@1.0.0")
        income = np.asarray(data["income"], dtype=float)
        weights = np.ones_like(income, dtype=float)
        state = SurveyMicroData(market_income=income, weights=weights)
        result = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            bound_inputs={"market_income": income, "weights": weights},
            params={},
            seed=17,
        ).output
        disposable = np.asarray(result["disposable_income"], dtype=float)
        assert np.all(np.isfinite(disposable))
        assert np.all(disposable >= 0.0)

    @given(data=microsim_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tax_benefit_deterministic(self, data, isolated_registry, property_method_dispatcher):
        method = isolated_registry.get("microsim.policy.tax_benefit_calculator@1.0.0")
        income = np.asarray(data["income"], dtype=float)
        weights = np.ones_like(income, dtype=float)
        state = SurveyMicroData(market_income=income, weights=weights)
        kwargs = {
            "dispatcher": property_method_dispatcher,
            "method_class": method,
            "state": state,
            "bound_inputs": {"market_income": income, "weights": weights},
            "params": {},
            "seed": 17,
        }
        first = invoke_property_method(**kwargs).output
        second = invoke_property_method(**kwargs).output
        for key in ("disposable_income", "tax_liability", "benefit_income", "effective_tax_rate"):
            np.testing.assert_array_equal(first[key], second[key])


class TestStaticMicrosimProperties:
    @given(data=microsim_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_static_microsim_output_dict(self, data, isolated_registry, property_method_dispatcher):
        result = _run_calibrated_static(data, isolated_registry, property_method_dispatcher)
        assert np.isfinite(float(result["result"].weighted_mean_disposable_income))
        assert result["uncertainty_envelope"] is not None

    @given(data=microsim_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_static_microsim_output_shape(
        self, data, isolated_registry, property_method_dispatcher
    ):
        result = _run_calibrated_static(data, isolated_registry, property_method_dispatcher)
        disposable = np.asarray(result["result"].disposable_income, dtype=float)
        assert disposable.shape == (int(data["n_agents"]),)
        assert np.all(np.isfinite(disposable))

    @given(data=microsim_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_static_microsim_refuses_uncertified_weights(self, data, isolated_registry):
        income = np.asarray(data["income"], dtype=float)
        weights = np.ones_like(income, dtype=float)
        state = SurveyMicroData(market_income=income, weights=weights)
        method = isolated_registry.get("microsim.static.static_microsim@1.0.0")
        with pytest.raises(ValueError, match="requires microsim_calibration_report"):
            invoke_property_method(
                dispatcher=_fresh_property_dispatcher(),
                method_class=method,
                state=state,
                bound_inputs={"market_income": income, "weights": weights},
                params={},
                seed=83,
            )
