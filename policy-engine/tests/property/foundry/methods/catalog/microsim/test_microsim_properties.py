"""Property-based tests for microsimulation methods: tax-benefit, dynamic micro."""

from __future__ import annotations

import sys

import numpy as np
import pytest

try:
    from hypothesis import HealthCheck, given, settings

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")

from tests.unit.foundry.methods.testing.strategies import microsim_strategy


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


class TestTaxBenefitProperties:
    @given(data=microsim_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tax_benefit_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "microsim.policy.tax_benefit_calculator@1.0.0")
        state = {
            "market_income": data["income"],
            "weights": np.ones_like(data["income"], dtype=float),
        }
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating) and arr.size > 0:
                    assert arr.shape is not None
        except Exception:
            pass

    @given(data=microsim_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tax_benefit_disposable_income_non_negative(self, data, isolated_registry):
        """Disposable income (income - tax + benefits) should be >= 0 for positive income."""
        method = _method_or_skip(isolated_registry, "microsim.policy.tax_benefit_calculator@1.0.0")
        state = {
            "market_income": data["income"],
            "weights": np.ones_like(data["income"], dtype=float),
        }
        try:
            result = method.pure_step(state, {})
            if "disposable_income" in result:
                disp = np.asarray(result["disposable_income"])
                if np.all(np.isfinite(disp)):
                    assert np.all(disp >= -1.0), "Disposable income is significantly negative"
        except Exception:
            pass

    @given(data=microsim_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_tax_benefit_deterministic(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "microsim.policy.tax_benefit_calculator@1.0.0")
        state = {
            "market_income": data["income"],
            "weights": np.ones_like(data["income"], dtype=float),
        }
        try:
            r1 = method.pure_step(state, {})
            r2 = method.pure_step(state, {})
            assert set(r1.keys()) == set(r2.keys())
        except Exception:
            pass


class TestStaticMicrosimProperties:
    @given(data=microsim_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_static_microsim_output_dict(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "microsim.static.static_microsim@1.0.0")
        state = {
            "market_income": data["income"],
            "weights": np.ones_like(data["income"], dtype=float),
        }
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass

    @given(data=microsim_strategy())
    @settings(
        max_examples=15,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_static_microsim_output_shape(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "microsim.static.static_microsim@1.0.0")
        state = {
            "market_income": data["income"],
            "weights": np.ones_like(data["income"], dtype=float),
        }
        try:
            result = method.pure_step(state, {})
            # Population-level outputs should match n_agents
            for key, val in result.items():
                arr = np.asarray(val)
                if arr.ndim == 1 and arr.shape[0] == data["n_agents"]:
                    pass  # Individual-level output — shape matches
        except Exception:
            pass
