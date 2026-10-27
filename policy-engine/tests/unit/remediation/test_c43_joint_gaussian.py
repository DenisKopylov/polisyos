"""Behavioral oracles for effective inputs and declared Gaussian joint laws."""

from __future__ import annotations

from functools import wraps

import numpy as np
import pytest

from polisyos.foundry.uncertainty.analytical import AnalyticalPropagator
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.delta import DeltaMethodPropagator
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

pytestmark = pytest.mark.unit


def _normal(name: str, row: list[float], columns: list[str], *, std: float = 1.0):
    return UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.959963984540054 * std, 1.959963984540054 * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata={"covariance_row": row, "covariance_params": columns, "coordinate": name},
    )


def _pair(rho: float) -> dict[str, UncertaintyEnvelope]:
    # Rows are owned by the enclosing envelope; columns are intentionally reversed.
    return {"a": _normal("a", [rho, 1.0], ["b", "a"]), "b": _normal("b", [1.0, rho], ["b", "a"])}


def _difference(a: float, b: float) -> dict[str, float]:
    return {"y": a - b}


@pytest.mark.parametrize("rho", [-1.0, -0.8, 0.0, 0.8, 1.0])
@pytest.mark.parametrize("method", ["random", "sobol"])
def test_same_declared_joint_gaussian_has_same_linear_variance_in_four_backends(
    rho: float, method: str
):
    envs = _pair(rho)
    expected = 2.0 - 2.0 * rho  # independent w.T @ [[1,rho],[rho,1]] @ w
    nominal = {"a": 0.0, "b": 0.0}
    delta = DeltaMethodPropagator(PropagationConfig(delta_covariance_jitter=0.0)).propagate(
        _difference, nominal, envs, ["y"]
    )[0]
    analytical = AnalyticalPropagator.propagate_linear_combination(
        weights={"a": 1.0, "b": -1.0}, input_envelopes=envs, output_metric_id="y"
    )
    assert delta.diagnostics["output_variance"] == pytest.approx(expected, abs=2e-5)
    assert analytical.diagnostics["output_variance"] == pytest.approx(expected, abs=2e-5)
    assert delta.envelope.gate_eligible is False
    assert analytical.envelope.gate_eligible is False
    mc = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=2048,
            mc_batch_size=256,
            mc_sampling_method=method,
            mc_seed=108,
            mc_qmc_scramble=True,
            compute_sensitivity=False,
        )
    ).propagate(_difference, nominal, envs, ["y"])[0]
    carrier = mc.envelope.distribution_payload
    assert isinstance(carrier, PosteriorSamplesCarrier)
    assert np.var(np.asarray(carrier.samples)) == pytest.approx(
        expected, abs=max(0.05, 0.15 * expected)
    )
    # A producer-declared covariance is not source-law verification.
    assert mc.envelope.gate_eligible is False


@pytest.mark.parametrize("method", ["random", "sobol"])
@pytest.mark.parametrize("kind", ["asymmetric", "unlabeled", "mixed_family"])
def test_unbindable_joint_law_never_runs_an_independent_gate_eligible_sampler(
    method: str, kind: str
):
    envs = _pair(0.8)
    if kind == "asymmetric":
        envs["b"] = _normal("b", [1.0, -0.8], ["b", "a"])
    elif kind == "unlabeled":
        envs = {
            name: env.model_copy(
                update={"metadata": {"covariance_row": env.metadata["covariance_row"]}}
            )
            for name, env in envs.items()
        }
    else:
        envs["b"] = envs["b"].model_copy(update={"distribution_family": DistributionFamily.UNIFORM})
    calls = []

    def response(**kwargs):
        calls.append(kwargs)
        return {"y": kwargs["a"] - kwargs["b"]}

    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, mc_sampling_method=method)
    ).propagate(response, {"a": 0.0, "b": 0.0}, envs, ["y"])[0]
    assert result.envelope.distribution_family is DistributionFamily.UNKNOWN
    assert result.envelope.gate_eligible is False
    assert calls == []


def test_dispatcher_rejects_unresolved_input_before_even_the_applicability_probe():
    calls = []

    def requires_fixed(x: float, scale: float) -> dict[str, float]:
        return {"y": x * scale}

    @wraps(requires_fixed)
    def observable_wrapper(*args, **kwargs):
        calls.append(dict(kwargs))
        return requires_fixed(*args, **kwargs)

    env = _normal("x", [1.0], ["x"])
    with pytest.raises(ValueError, match="scale"):
        PropagationDispatcher(PropagationConfig()).propagate(
            observable_wrapper, {"x": 1.0}, {"x": env}, ["y"]
        )
    assert calls == []


@pytest.mark.parametrize("method", ["auto", "delta", "random", "sobol"])
def test_all_actual_evaluator_calls_keep_the_fixed_value_without_a_fake_envelope(method: str):
    calls = []

    def response(x: float, scale: float = 1.0) -> dict[str, float]:
        calls.append(scale)
        return {"y": x * scale}

    env = _normal("x", [0.0001], ["x"], std=0.01).model_copy(
        update={
            "point_estimate": 1.0,
            "confidence_interval": (0.9804003601545995, 1.0195996398454005),
        }
    )
    config = PropagationConfig(
        mc_n_samples=128,
        mc_batch_size=128,
        mc_sampling_method=("sobol" if method == "sobol" else "random"),
        compute_sensitivity=False,
    )
    if method in {"random", "sobol"}:
        result = MonteCarloPropagator(config).propagate(
            response, {"x": 1.0, "scale": 3.0}, {"x": env}, ["y"]
        )[0]
    elif method == "delta":
        result = DeltaMethodPropagator(config).propagate(
            response, {"x": 1.0, "scale": 3.0}, {"x": env}, ["y"]
        )[0]
    else:
        result = PropagationDispatcher(config).propagate(
            response, {"x": 1.0, "scale": 3.0}, {"x": env}, ["y"]
        )[0]
    assert calls and all(value == 3.0 for value in calls)
    assert result.envelope.point_estimate == pytest.approx(3.0, abs=0.03)


def test_three_distinct_coordinate_rows_and_columns_retain_their_own_units():
    from polisyos.foundry.uncertainty.covariance import build_covariance_matrix

    columns = ["c", "a", "b"]
    envs = {
        "a": _normal("a", [0.0, 1.0, 0.4], columns, std=1.0),
        "b": _normal("b", [0.6, 0.4, 4.0], columns, std=2.0),
        "c": _normal("c", [9.0, 0.0, 0.6], columns, std=3.0),
    }
    units = {"a": "worker", "b": "currency", "c": "time"}
    envs = {
        name: env.model_copy(update={"metadata": {**env.metadata, "unit_id": units[name]}})
        for name, env in envs.items()
    }
    matrix = build_covariance_matrix(
        list(envs), envs, use_full_covariance=True, jitter=0.0, preserve_singular=True
    )
    np.testing.assert_allclose(
        np.asarray(matrix), [[1.0, 0.4, 0.0], [0.4, 4.0, 0.6], [0.0, 0.6, 9.0]], atol=1e-5
    )
    # Arithmetic does not verify the declared source/unit identities.
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
    ).propagate(lambda **p: {"y": p["a"] + p["b"] + p["c"]}, dict.fromkeys(envs, 0.0), envs, ["y"])[
        0
    ]
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["parameter_unit_binding"] == "not_established"


def test_mixed_marginals_without_a_joint_law_are_at_most_a_limited_candidate():
    normal = _normal("a", [1.0], ["a"]).model_copy(update={"metadata": {}})
    uniform = normal.model_copy(update={"distribution_family": DistributionFamily.UNIFORM})
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
    ).propagate(
        lambda **p: {"y": p["a"] - p["b"]}, {"a": 0.0, "b": 0.0}, {"a": normal, "b": uniform}, ["y"]
    )[0]
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["joint_dependency"] == "independence_assumption_not_established"


def test_declared_covariance_is_not_replaced_by_diagonal_config():
    envs = _pair(0.8)
    config = PropagationConfig(delta_use_full_covariance=False, preferred_method="analytical")
    result = PropagationDispatcher(config).propagate(
        _difference, {"a": 0.0, "b": 0.0}, envs, ["y"], weights={"a": 1.0, "b": -1.0}
    )[0]
    assert result.envelope.distribution_family is DistributionFamily.UNKNOWN
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["failure"] == "incompatible_dependency"


def test_single_effective_analytical_coordinate_does_not_require_joint_dependence():
    envs = _pair(0.8)
    result = AnalyticalPropagator.propagate_linear_combination(
        weights={"a": 1.0}, input_envelopes=envs, output_metric_id="y"
    )
    assert result.diagnostics["output_variance"] == pytest.approx(1.0, abs=1e-5)
    assert result.input_envelopes_used == ["a"]
    assert result.envelope.gate_eligible is True


def test_opaque_signature_refuses_before_any_evaluator_attempt():
    calls = []

    class OpaqueEvaluator:
        @property
        def __signature__(self):
            raise ValueError("opaque")

        def __call__(self, **kwargs):
            calls.append(kwargs)
            raise TypeError("missing scale")

    env = _normal("x", [1.0], ["x"])
    with pytest.raises(ValueError, match="inspectable"):
        PropagationDispatcher(PropagationConfig()).propagate(
            OpaqueEvaluator(), {"x": 1.0}, {"x": env}, ["y"]
        )
    assert calls == []


def test_analytical_supplied_covariance_must_match_the_named_input_law():
    envs = _pair(0.8)
    expected = np.asarray([[1.0, 0.8], [0.8, 1.0]])
    valid = AnalyticalPropagator.propagate_linear_combination(
        weights={"a": 1.0}, input_envelopes=envs, output_metric_id="y", covariance=expected
    )
    assert valid.diagnostics["output_variance"] == pytest.approx(1.0, abs=1e-5)
    assert valid.envelope.gate_eligible is True
    for foreign in (np.zeros((2, 2)), np.asarray([[1.0, -0.8], [-0.8, 1.0]]), np.eye(1)):
        with pytest.raises(ValueError, match="covariance"):
            AnalyticalPropagator.propagate_linear_combination(
                weights={"a": 1.0}, input_envelopes=envs, output_metric_id="y", covariance=foreign
            )


def test_analytical_dispatch_uses_the_same_configured_singular_covariance_policy():
    envs = {
        "a": _normal("a", [0.0, 0.0], ["a", "b"], std=0.0),
        "b": _normal("b", [0.0, 1.0], ["a", "b"], std=1.0),
    }
    config = PropagationConfig(preferred_method="analytical", delta_covariance_jitter=1e-9)
    result = PropagationDispatcher(config).propagate(
        lambda a, b: {"y": a}, {"a": 0.0, "b": 0.0}, envs, ["y"], weights={"a": 1.0}
    )[0]
    assert result.method_used is PropagationMethod.ANALYTICAL
    assert result.diagnostics["output_variance"] == pytest.approx(0.0, abs=1e-11)
    assert result.envelope.metadata["covariance_jitter_applied_to_input_law"] is False


@pytest.mark.parametrize("method", ["random", "sobol"])
def test_large_requested_jitter_does_not_change_the_declared_singular_law(method: str):
    envs = _pair(1.0)
    nominal = {"a": 0.0, "b": 0.0}
    config = PropagationConfig(
        delta_covariance_jitter=0.5,
        preferred_method="analytical",
        mc_sampling_method=method,
        mc_n_samples=128,
        compute_sensitivity=False,
    )
    delta = DeltaMethodPropagator(config).propagate(_difference, nominal, envs, ["y"])[0]
    analytical = PropagationDispatcher(config).propagate(
        _difference, nominal, envs, ["y"], weights={"a": 1.0, "b": -1.0}
    )[0]
    sampled = MonteCarloPropagator(config).propagate(_difference, nominal, envs, ["y"])[0]
    assert analytical.method_used is PropagationMethod.ANALYTICAL
    assert delta.diagnostics["output_variance"] == pytest.approx(0.0, abs=1e-6)
    assert analytical.diagnostics["output_variance"] == pytest.approx(0.0, abs=1e-6)
    carrier = sampled.envelope.distribution_payload
    assert isinstance(carrier, PosteriorSamplesCarrier)
    assert np.var(np.asarray(carrier.samples)) == pytest.approx(0.0, abs=1e-6)
    for result in (delta, analytical, sampled):
        assert result.envelope.metadata["covariance_jitter_requested"] == pytest.approx(0.5)
        assert result.envelope.metadata["covariance_jitter_applied_to_input_law"] is False
