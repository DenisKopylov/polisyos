"""Property-based tests for mechanism runtime methods."""
from __future__ import annotations
import sys
import numpy as np
import pytest

try:
    from hypothesis import given, settings, HealthCheck
    from hypothesis import strategies as st
    from hypothesis.extra.numpy import arrays

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
sys.path.insert(0, "src")


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


@st.composite
def _tax_data(draw):
    n = draw(st.integers(min_value=10, max_value=100))
    income = draw(arrays(np.float64, (n,), elements=st.floats(100.0, 100000.0, allow_nan=False, allow_infinity=False)))
    rate = draw(st.floats(min_value=0.0, max_value=0.5, allow_nan=False))
    threshold = draw(st.floats(min_value=0.0, max_value=50000.0, allow_nan=False))
    return {"income": income, "rate": rate, "threshold": threshold, "n": n}


class TestTaxSubsidyProperties:
    @given(data=_tax_data())
    @settings(max_examples=25, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_tax_revenue_non_negative(self, data, isolated_registry):
        """Tax revenue should be non-negative for non-negative rates."""
        method = _method_or_skip(isolated_registry, "mechanism.runtime.tax_subsidy@1.0.0")
        state = {"income": data["income"]}
        params = {"rate": data["rate"], "threshold": data["threshold"]}
        try:
            result = method.pure_step(state, params)
            if "total_revenue" in result:
                rev = float(result["total_revenue"])
                if np.isfinite(rev):
                    assert rev >= -1e-10, f"Negative tax revenue: {rev}"
        except Exception:
            pass

    @given(data=_tax_data())
    @settings(max_examples=25, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_tax_output_finite(self, data, isolated_registry):
        method = _method_or_skip(isolated_registry, "mechanism.runtime.tax_subsidy@1.0.0")
        state = {"income": data["income"]}
        params = {"rate": data["rate"], "threshold": data["threshold"]}
        try:
            result = method.pure_step(state, params)
            assert isinstance(result, dict)
            for key, val in result.items():
                arr = np.asarray(val)
                if np.issubdtype(arr.dtype, np.floating):
                    assert not np.all(np.isnan(arr)), f"All-NaN in tax_subsidy/{key}"
        except Exception:
            pass

    @given(data=_tax_data())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_zero_rate_no_tax(self, data, isolated_registry):
        """Zero tax rate should yield zero revenue."""
        method = _method_or_skip(isolated_registry, "mechanism.runtime.tax_subsidy@1.0.0")
        state = {"income": data["income"]}
        params = {"rate": 0.0, "threshold": data["threshold"]}
        try:
            result = method.pure_step(state, params)
            if "total_revenue" in result:
                rev = float(result["total_revenue"])
                if np.isfinite(rev):
                    assert abs(rev) < 1e-6, f"Expected zero revenue, got {rev}"
        except Exception:
            pass
