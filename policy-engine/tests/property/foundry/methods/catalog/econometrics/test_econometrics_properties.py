"""
Property-based tests for econometrics methods:
- GARCH (volatility model)
- Count data (Poisson, NegBin)
- Discrete choice (Logit, Probit)
- Quantile regression
- Panel models (Fixed effects, Random effects)
"""

from __future__ import annotations

import importlib.metadata
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

from polisyos.foundry.methods.catalog.econometrics.protocols import EconometricResult
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope
from tests.unit.foundry.methods.testing.property_invocation import invoke_property_method
from tests.unit.foundry.methods.testing.strategies import (
    count_data_strategy,
    discrete_choice_strategy,
)


def _dict_result(method_result, method_fqn: str) -> dict:
    """Return the nested mapping result after checking the backend result boundary."""
    assert isinstance(method_result.output, dict), f"{method_fqn} did not return an output mapping"
    result = method_result.output.get("result")
    assert isinstance(result, dict), f"{method_fqn} did not return its declared result mapping"
    return result


def _econometric_result(
    method_result,
    *,
    method_fqn: str,
    method_name: str,
    n_obs: int,
) -> EconometricResult:
    """Check the typed econometric result and its observed numerical summaries."""
    assert isinstance(method_result.output, dict), f"{method_fqn} did not return an output mapping"
    result = method_result.output.get("result")
    assert isinstance(result, EconometricResult), f"{method_fqn} did not return EconometricResult"
    assert result.method_name == method_name
    assert result.n_obs == n_obs
    assert result.params
    for field_name, values in (
        ("params", result.params),
        ("std_errors", result.std_errors),
        ("t_stats", result.t_stats),
        ("p_values", result.p_values),
    ):
        if values:
            assert np.isfinite(np.asarray(list(values.values()), dtype=float)).all(), field_name
    return result


def _binary_choice_inputs(data: dict) -> dict:
    """Project the existing multi-alternative fixture to Logit's binary ABI."""
    attributes = np.asarray(data["attributes"], dtype=float)
    choices = np.asarray(data["choice"], dtype=int)
    assert attributes.ndim == 3 and attributes.shape[1] >= 2
    assert choices.shape == (attributes.shape[0],)
    reference = attributes[:, 0, :]
    alternatives = attributes[:, 1:, :].mean(axis=1)
    return {
        "X": reference - alternatives,
        "y": (choices == 0).astype(np.float64),
    }


def _skip_if_missing_optional_distribution(distribution_name: str) -> None:
    """Skip only when optional backend metadata is absent; let broken imports fail."""
    try:
        importlib.metadata.distribution(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        pytest.skip(f"optional dependency {distribution_name!r} is not installed")


class TestCountDataProperties:
    @given(data=count_data_strategy())
    @settings(
        max_examples=30,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_poisson_output_finite(self, data, isolated_registry, property_method_dispatcher):
        fqn = "econometrics.count.poisson@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"X": data["covariates"], "y": data["outcome"]}
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={},
            seed=0,
        )
        result = _dict_result(invocation, fqn)
        coefficients = np.asarray(result["coefficients"], dtype=float)
        assert coefficients.shape == (state["X"].shape[1] + 1,)
        assert np.isfinite(coefficients).all()
        assert np.isfinite(result["log_likelihood"])
        assert np.isfinite(result["deviance"])
        assert result["deviance"] >= -1e-8
        assert result["n_obs"] == data["n_obs"]

    @given(data=count_data_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_negbin_output_dict(self, data, isolated_registry, property_method_dispatcher):
        fqn = "econometrics.count.negative_binomial@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"X": data["covariates"], "y": data["outcome"]}
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={},
            seed=0,
        )
        result = _dict_result(invocation, fqn)
        coefficients = np.asarray(result["coefficients"], dtype=float)
        assert coefficients.shape == (state["X"].shape[1] + 1,)
        assert np.isfinite(coefficients).all()
        assert np.isfinite(result["alpha"])
        assert result["alpha"] >= 0.0
        assert np.isfinite(result["mean_predicted"])
        assert result["mean_predicted"] > 0.0
        assert result["n_obs"] == data["n_obs"]

    @given(data=count_data_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_output_keys_stable(self, data, isolated_registry, property_method_dispatcher):
        """Poisson returns its documented nested estimate fields on repeated calls."""
        fqn = "econometrics.count.poisson@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"X": data["covariates"], "y": data["outcome"]}
        first = _dict_result(
            invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=method,
                state=state,
                params={},
                seed=0,
            ), fqn
        )
        second = _dict_result(
            invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=method,
                state=state,
                params={},
                seed=0,
            ), fqn
        )
        expected = {"coefficients", "log_likelihood", "deviance", "dispersion", "n_obs"}
        assert set(first) == set(second) == expected
        assert first["n_obs"] == second["n_obs"] == data["n_obs"]


class TestDiscreteChoiceProperties:
    @given(data=discrete_choice_strategy())
    @settings(
        max_examples=25,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_logit_output_finite(self, data, isolated_registry, property_method_dispatcher):
        fqn = "econometrics.discrete_choice.logit@1.0.0"
        method = isolated_registry.get(fqn)
        state = _binary_choice_inputs(data)
        result = _dict_result(
            invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=method,
                state=state,
                params={},
                seed=0,
            ), fqn
        )
        coefficients = np.asarray(result["coefficients"], dtype=float)
        assert coefficients.shape == (state["X"].shape[1] + 1,)
        assert np.isfinite(coefficients).all()
        assert np.isfinite(result["log_likelihood"])
        assert np.isfinite(result["accuracy"])
        assert 0.0 <= result["accuracy"] <= 1.0
        assert result["n_obs"] == state["X"].shape[0]

    @given(data=discrete_choice_strategy())
    @settings(
        max_examples=20,
        deadline=10000,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_logit_result_is_dict(self, data, isolated_registry, property_method_dispatcher):
        fqn = "econometrics.discrete_choice.logit@1.0.0"
        method = isolated_registry.get(fqn)
        state = _binary_choice_inputs(data)
        result = _dict_result(
            invoke_property_method(
                dispatcher=property_method_dispatcher,
                method_class=method,
                state=state,
                params={},
                seed=0,
            ), fqn
        )
        assert set(result) == {"coefficients", "log_likelihood", "accuracy", "n_obs", "n_features"}
        assert result["n_features"] == state["X"].shape[1]
        assert result["n_obs"] == state["X"].shape[0]


def _seeded_garch_candidate(*, seed: int, n_obs: int = 512) -> dict[str, np.ndarray | int]:
    """Build a test-local stationary GARCH candidate, not a calibrated data claim."""
    burn_in = 256
    omega = 0.1
    alpha = 0.12
    beta = 0.83
    innovations = np.random.default_rng(seed).standard_normal(n_obs + burn_in)
    conditional_variance = np.empty(n_obs + burn_in, dtype=float)
    endog = np.empty(n_obs + burn_in, dtype=float)
    conditional_variance[0] = omega / (1.0 - alpha - beta)
    endog[0] = np.sqrt(conditional_variance[0]) * innovations[0]
    for index in range(1, len(endog)):
        conditional_variance[index] = (
            omega + alpha * endog[index - 1] ** 2 + beta * conditional_variance[index - 1]
        )
        endog[index] = np.sqrt(conditional_variance[index]) * innovations[index]
    return {"endog": endog[burn_in:].copy(), "n_obs": n_obs}


class TestGARCHProperties:
    def test_garch_output_finite(self, isolated_registry, property_method_dispatcher):
        _skip_if_missing_optional_distribution("arch")
        fqn = "econometrics.timeseries.garch@1.0.0"
        method = isolated_registry.get(fqn)
        data = _seeded_garch_candidate(seed=20261010)
        state = {"endog": data["endog"]}
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={"p": 1, "q": 1},
            seed=0,
        )
        result = _econometric_result(
            invocation, method_fqn=fqn, method_name="garch", n_obs=data["n_obs"]
        )
        expected_diagnostics = {
            "loglikelihood",
            "aic",
            "bic",
            "last_conditional_volatility",
        }
        assert set(result.std_errors) == set(result.params)
        assert set(result.p_values) == set(result.params)
        assert set(result.diagnostics) == expected_diagnostics
        assert all(
            value is not None and np.isfinite(value) for value in result.diagnostics.values()
        )

    def test_garch_uncertainty_projection_matches_estimate(
        self, isolated_registry, property_method_dispatcher
    ):
        _skip_if_missing_optional_distribution("arch")
        fqn = "econometrics.timeseries.garch@1.0.0"
        method = isolated_registry.get(fqn)
        data = _seeded_garch_candidate(seed=20261010)
        state = {"endog": data["endog"]}
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={"p": 1, "q": 1},
            seed=0,
        )
        result = _econometric_result(
            invocation, method_fqn=fqn, method_name="garch", n_obs=data["n_obs"]
        )
        assert set(invocation.output) == {"result", "uncertainty_envelope"}
        envelope = invocation.output["uncertainty_envelope"]
        assert isinstance(envelope, UncertaintyEnvelope)
        parameter = envelope.metadata["param_name"]
        assert parameter in result.params
        assert envelope.point_estimate == pytest.approx(result.params[parameter])
        lower, upper = envelope.confidence_interval
        assert lower <= envelope.point_estimate <= upper
        assert envelope.sample_size == result.n_obs
        assert result.diagnostics["last_conditional_volatility"] >= 0.0

    def test_garch_rejects_multivariate_endog(self, isolated_registry):
        _skip_if_missing_optional_distribution("arch")
        fqn = "econometrics.timeseries.garch@1.0.0"
        method = isolated_registry.get(fqn)
        state = {"endog": np.zeros((512, 1), dtype=float)}
        with pytest.raises(ValueError, match=r"^garch requires 1D endog$"):
            method.pure_step(state, {"p": 1, "q": 1})


def _fixed_effects_panel_candidate(*, seed: int = 20261010) -> dict[str, np.ndarray | int]:
    """Build one test-local panel candidate with an observed within-entity regressor."""
    n_entities = 8
    n_periods = 16
    n_obs = n_entities * n_periods
    rng = np.random.default_rng(seed)
    entity_ids = np.repeat(np.arange(n_entities), n_periods)
    time_ids = np.tile(np.arange(n_periods), n_entities)
    within_time = np.tile(np.linspace(-1.0, 1.0, n_periods), n_entities)
    entity_offset = np.repeat(np.linspace(-0.75, 0.75, n_entities), n_periods)
    exog = (
        within_time + entity_offset + rng.normal(0.0, 0.05, n_obs)
    ).reshape(n_obs, 1)
    entity_effect = np.repeat(rng.normal(0.0, 1.0, n_entities), n_periods)
    dependent = 0.8 * exog[:, 0] + entity_effect + rng.normal(0.0, 0.2, n_obs)
    return {
        "dependent": dependent,
        "exog": exog,
        "entity_ids": entity_ids,
        "time_ids": time_ids,
        "n_obs": n_obs,
    }


class TestPanelModelProperties:
    def test_fixed_effects_output_finite(self, isolated_registry, property_method_dispatcher):
        _skip_if_missing_optional_distribution("linearmodels")
        fqn = "econometrics.panel.fixed_effects@1.0.0"
        method = isolated_registry.get(fqn)
        data = _fixed_effects_panel_candidate()
        state = {
            "dependent": data["dependent"],
            "exog": data["exog"],
            "entity_ids": data["entity_ids"],
            "time_ids": data["time_ids"],
        }
        within_entity_exog = state["exog"].copy()
        for entity in np.unique(state["entity_ids"]):
            mask = state["entity_ids"] == entity
            within_values = within_entity_exog[mask]
            assert float(np.ptp(within_values[:, 0])) > 0.0
            within_entity_exog[mask] = within_values - within_values.mean(axis=0)
        assert np.linalg.matrix_rank(within_entity_exog) == state["exog"].shape[1]
        invocation = invoke_property_method(
            dispatcher=property_method_dispatcher,
            method_class=method,
            state=state,
            params={},
            seed=0,
        )
        result = _econometric_result(
            invocation, method_fqn=fqn, method_name="fixed_effects", n_obs=data["n_obs"]
        )
        assert set(result.std_errors) == set(result.params)

    def test_fixed_effects_rejects_time_invariant_exog(self, isolated_registry):
        _skip_if_missing_optional_distribution("linearmodels")
        fqn = "econometrics.panel.fixed_effects@1.0.0"
        method = isolated_registry.get(fqn)
        n_entities = 4
        n_periods = 4
        entity_ids = np.repeat(np.arange(n_entities), n_periods)
        state = {
            "dependent": np.linspace(0.0, 1.0, n_entities * n_periods),
            "exog": entity_ids.astype(float).reshape(-1, 1),
            "entity_ids": entity_ids,
            "time_ids": np.tile(np.arange(n_periods), n_entities),
        }
        with pytest.raises(
            ValueError,
            match=r"^Fixed Effects dropped all regressors as time-invariant within entities$",
        ):
            method.pure_step(state, {})
