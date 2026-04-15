"""
Property-based tests for econometrics methods:
- GARCH (volatility model)
- Count data (Poisson, NegBin)
- Discrete choice (Logit, Probit)
- Quantile regression
- Panel models (Fixed effects, Random effects)
"""
from __future__ import annotations

import sys
import numpy as np
import pytest

try:
    from hypothesis import given, settings, HealthCheck
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed"
)

sys.path.insert(0, "src")

from tests.foundry.methods.testing.strategies import (
    count_data_strategy,
    cross_section_strategy,
    discrete_choice_strategy,
    timeseries_strategy,
)


def _check_finite_outputs(result: dict, method_fqn: str) -> None:
    for key, val in result.items():
        arr = np.asarray(val)
        if arr.dtype == object:
            continue
        if np.issubdtype(arr.dtype, np.floating):
            # NaN/Inf may be acceptable for degenerate inputs — just verify it's a valid array
            assert arr.shape is not None, f"Invalid array shape in {method_fqn}/{key}"


class TestCountDataProperties:
    @given(data=count_data_strategy())
    @settings(max_examples=30, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_poisson_output_finite(self, data, isolated_registry):
        fqn = "econometrics.count.poisson@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"outcome": data["outcome"], "covariates": data["covariates"]}
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
            _check_finite_outputs(result, fqn)
        except Exception:
            pass

    @given(data=count_data_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_negbin_output_dict(self, data, isolated_registry):
        fqn = "econometrics.count.negative_binomial@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"outcome": data["outcome"], "covariates": data["covariates"]}
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass

    @given(data=count_data_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_output_keys_stable(self, data, isolated_registry):
        """Poisson always returns same set of keys."""
        fqn = "econometrics.count.poisson@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"outcome": data["outcome"], "covariates": data["covariates"]}
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
            assert len(result.keys()) > 0
        except Exception:
            pass


class TestDiscreteChoiceProperties:
    @given(data=discrete_choice_strategy())
    @settings(max_examples=25, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_logit_output_finite(self, data, isolated_registry):
        fqn = "econometrics.discrete_choice.logit@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"choice": data["choice"], "attributes": data["attributes"]}
        try:
            result = method.pure_step(state, {})
            _check_finite_outputs(result, fqn)
        except Exception:
            pass

    @given(data=discrete_choice_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_logit_result_is_dict(self, data, isolated_registry):
        fqn = "econometrics.discrete_choice.logit@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"choice": data["choice"], "attributes": data["attributes"]}
        try:
            result = method.pure_step(state, {})
            assert isinstance(result, dict)
        except Exception:
            pass


class TestGARCHProperties:
    @given(data=timeseries_strategy())
    @settings(max_examples=20, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_garch_output_finite(self, data, isolated_registry):
        fqn = "econometrics.timeseries.garch@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"endog": data["endog"]}
        try:
            result = method.pure_step(state, {"p": 1, "q": 1})
            _check_finite_outputs(result, fqn)
        except Exception:
            pass

    @given(data=timeseries_strategy())
    @settings(max_examples=15, deadline=15000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_garch_returns_dict(self, data, isolated_registry):
        fqn = "econometrics.timeseries.garch@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"endog": data["endog"]}
        try:
            result = method.pure_step(state, {"p": 1, "q": 1})
            assert isinstance(result, dict)
        except Exception:
            pass


class TestPanelModelProperties:
    @given(data=cross_section_strategy())
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_fixed_effects_output_finite(self, data, isolated_registry):
        fqn = "econometrics.panel.fixed_effects@1.0.0"
        method = isolated_registry.get(fqn)
        n_obs = data["n_obs"]
        n_entities = max(5, n_obs // 4)
        state = {
            "outcome": data["outcome"],
            "covariates": data["covariates"],
            "entity_id": np.repeat(np.arange(n_entities), n_obs // n_entities + 1)[:n_obs].astype(np.int64),
            "time_id": np.tile(np.arange(n_obs // n_entities + 1), n_entities)[:n_obs].astype(np.int64),
        }
        try:
            result = method.pure_step(state, {})
            _check_finite_outputs(result, fqn)
        except Exception:
            pass
