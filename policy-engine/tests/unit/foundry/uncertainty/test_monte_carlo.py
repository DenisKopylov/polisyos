from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import numpy as np
import numpy.testing as npt
import pytest

from polisyos.foundry.uncertainty.config import AdaptiveStoppingConfig, PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

if TYPE_CHECKING:
    from polisyos.foundry.uncertainty.protocol import PropagationResult


def _normal_env(point: float, std: float, level: float = 0.95) -> UncertaintyEnvelope:
    from statistics import NormalDist

    z = NormalDist().inv_cdf((1.0 + level) / 2.0)
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - z * std, point + z * std),
        confidence_level=level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
    )


def _linear_sim(**params: float) -> dict[str, float]:
    return {"y": 2.0 * params.get("x", 0.0) + 3.0 * params.get("z", 0.0)}


def _joint_normal_inputs(
    means: dict[str, float], covariance: np.ndarray, columns: list[str]
) -> dict[str, UncertaintyEnvelope]:
    names = list(means)
    inputs = {}
    for row, name in enumerate(names):
        std = float(np.sqrt(covariance[row, row]))
        inputs[name] = _normal_env(means[name], std).model_copy(
            update={
                "distribution_payload": ParametricFitCarrier(
                    family=DistributionFamily.NORMAL,
                    parameters={"mean": means[name], "std": std},
                ),
                "metadata": {
                    "covariance_row": [float(covariance[row, names.index(col)]) for col in columns],
                    "covariance_params": columns,
                },
            }
        )
    return inputs


def _output_samples(result: PropagationResult) -> np.ndarray:
    # This helper consumes the public envelope payload, not the sampler internals.
    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert payload.sample_axis == "draw"
    return np.asarray(payload.samples, dtype=np.float64)


def _envelope_sha256(envelope: UncertaintyEnvelope) -> str:
    wire = json.dumps(
        envelope.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(wire).hexdigest()


@pytest.mark.parametrize("sampling_method", ["random", "sobol", "halton"])
def test_mc_gaussian_draws_follow_declared_covariance_and_axes(sampling_method: str) -> None:
    means = {"a": 1.0, "b": -3.0, "c": 5.0}
    covariance = np.asarray([[1.0, 1.0, -0.5], [1.0, 4.0, 0.75], [-0.5, 0.75, 9.0]])
    inputs = _joint_normal_inputs(means, covariance, ["c", "a", "b"])
    reordered = _joint_normal_inputs(means, covariance, ["a", "b", "c"])
    reordered = dict(reversed(list(reordered.items())))
    config = PropagationConfig(
        mc_n_samples=512,
        mc_batch_size=128,
        mc_seed=101,
        mc_sampling_method=sampling_method,
        compute_sensitivity=False,
    )

    def simulation(a: float, b: float, c: float) -> dict[str, float]:
        return {"a_out": a, "b_out": b, "c_out": c, "mix": a - 2.0 * b + 0.5 * c}

    metrics = ["a_out", "b_out", "c_out", "mix"]
    results = MonteCarloPropagator(config).propagate(simulation, means, inputs, metrics)
    replay = MonteCarloPropagator(config).propagate(simulation, means, reordered, metrics)
    draws = np.column_stack([_output_samples(result) for result in results])
    replay_draws = np.column_stack([_output_samples(result) for result in replay])

    # Equivalent column declarations and mapping insertion orders identify the same draws.
    npt.assert_array_equal(draws, replay_draws)
    assert draws.shape == (512, 4)
    npt.assert_allclose(draws[:, 3], draws[:, 0] - 2.0 * draws[:, 1] + 0.5 * draws[:, 2], atol=1e-5)
    normalized = (draws[:, :3] - np.asarray([1.0, -3.0, 5.0])) / np.asarray([1.0, 2.0, 3.0])
    npt.assert_allclose(normalized.mean(axis=0), np.zeros(3), atol=0.2, rtol=0.0)
    expected_covariance = np.asarray(
        [[1.0, 0.5, -1.0 / 6.0], [0.5, 1.0, 0.125], [-1.0 / 6.0, 0.125, 1.0]]
    )
    npt.assert_allclose(
        np.cov(normalized, rowvar=False, bias=True), expected_covariance, atol=0.24, rtol=0.0
    )

    for result in results:
        assert result.diagnostics["n_failed"] == 0
        assert result.envelope.gate_eligible is False
        assert result.envelope.metadata["joint_gaussian_basis"] == "declared_non_authoritative"
        recipe = result.diagnostics["draw_outcome_provenance"]["sampling_recipe"]
        assert recipe["input_param_names"] == ["a", "b", "c"]
        assert recipe["sample_axis"] == "draw"
        assert recipe["input_envelope_sha256"] == {
            name: _envelope_sha256(envelope) for name, envelope in inputs.items()
        }
        reopened = UncertaintyEnvelope.model_validate_json(result.envelope.model_dump_json())
        assert isinstance(reopened.distribution_payload, PosteriorSamplesCarrier)
        npt.assert_array_equal(reopened.distribution_payload.samples, _output_samples(result))


@pytest.mark.parametrize("sampling_method", ["random", "sobol", "halton"])
def test_mc_gaussian_singular_support_survives_requested_jitter(sampling_method: str) -> None:
    means = {"a": 1.0, "b": -3.0, "c": 5.0}
    direction = np.asarray([1.0, -2.0, 3.0])
    inputs = _joint_normal_inputs(means, np.outer(direction, direction), ["c", "a", "b"])
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=256,
            mc_batch_size=64,
            mc_seed=21,
            mc_sampling_method=sampling_method,
            delta_covariance_jitter=0.25,
            compute_sensitivity=False,
        )
    ).propagate(lambda a, b, c: {"a": a, "b": b, "c": c}, means, inputs, ["a", "b", "c"])
    draws = np.column_stack([_output_samples(item) for item in result])

    npt.assert_allclose(draws[:, 1] + 2.0 * draws[:, 0], -1.0, atol=2e-5, rtol=0.0)
    npt.assert_allclose(draws[:, 2] - 3.0 * draws[:, 0], 2.0, atol=2e-5, rtol=0.0)
    assert 0.55 < np.var(draws[:, 0]) < 1.5  # A sampler that returns only the mean is not valid.
    assert all(item.envelope.gate_eligible is False for item in result)


@pytest.mark.parametrize("correlation", [0.8, -0.8, None])
def test_mc_gaussian_marginals_do_not_authorize_joint_assumption(correlation: float | None) -> None:
    means = {"a": 0.0, "b": 0.0}
    if correlation is None:
        inputs = {name: _normal_env(0.0, 1.0) for name in means}
        expected_variance = 2.0
    else:
        inputs = _joint_normal_inputs(
            means, np.asarray([[1.0, correlation], [correlation, 1.0]]), ["b", "a"]
        )
        expected_variance = 2.0 - 2.0 * correlation
    assert all(envelope.gate_eligible for envelope in inputs.values())
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=512, mc_seed=7, compute_sensitivity=False)
    ).propagate(lambda a, b: {"difference": a - b}, means, inputs, ["difference"])[0]

    assert np.var(_output_samples(result)) == pytest.approx(expected_variance, rel=0.25)
    assert result.envelope.gate_eligible is False
    if correlation is None:
        assert (
            result.envelope.metadata["joint_dependency"]
            == "independence_assumption_not_established"
        )
    else:
        assert result.envelope.metadata["joint_gaussian_basis"] == "declared_non_authoritative"
        assert result.envelope.metadata["parameter_unit_binding"] == "not_established"


@pytest.mark.parametrize("sampling_method", ["random", "sobol", "halton"])
@pytest.mark.parametrize(
    "invalid", ["indefinite", "asymmetric", "nonfinite", "duplicate_axes", "missing_row"]
)
def test_mc_invalid_gaussian_covariance_refuses_before_callback(
    sampling_method: str, invalid: str
) -> None:
    means = {"a": 0.0, "b": 0.0}
    covariance = {
        "indefinite": [[1.0, 2.0], [2.0, 1.0]],
        "asymmetric": [[1.0, 0.8], [0.2, 1.0]],
        "nonfinite": [[1.0, float("nan")], [float("nan"), 1.0]],
    }.get(invalid, [[1.0, 0.5], [0.5, 1.0]])
    inputs = _joint_normal_inputs(means, np.asarray(covariance), ["a", "b"])
    if invalid == "duplicate_axes":
        for name in means:
            inputs[name].metadata["covariance_params"] = ["a", "a"]
    if invalid == "missing_row":
        del inputs["b"].metadata["covariance_row"]
    calls: list[dict[str, float]] = []

    def simulation(**params: float) -> dict[str, float]:
        calls.append(params)
        return {"difference": params["a"] - params["b"]}

    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=100,
            mc_sampling_method=sampling_method,
            delta_covariance_jitter=0.5,
            compute_sensitivity=False,
        )
    ).propagate(simulation, means, inputs, ["difference"])[0]

    assert calls == []
    assert result.envelope.metadata["failure"] == "incompatible_dependency"
    assert result.envelope.gate_eligible is False


class TestMonteCarloPropagator:
    def test_mc_linear_fn_approximates_delta(self) -> None:
        config = PropagationConfig(mc_n_samples=2000, mc_seed=42)
        mc = MonteCarloPropagator(config)
        envelopes = {"x": _normal_env(1.0, 0.5), "z": _normal_env(2.0, 1.0)}

        results = mc.propagate(
            _linear_sim,
            {"x": 1.0, "z": 2.0},
            envelopes,
            ["y"],
        )

        assert len(results) == 1
        import math

        expected_std = math.sqrt(4 * 0.5**2 + 9 * 1.0**2)
        ci_width = results[0].envelope.ci_width
        actual_half_width = ci_width / 2.0
        npt.assert_allclose(actual_half_width, 1.96 * expected_std, rtol=0.25)

    def test_mc_preserves_fixed_nominal_parameters_across_samples(self) -> None:
        """Every sampled call retains nominal parameters outside the envelope."""
        calls: list[dict[str, float]] = []

        def scaled_sim(**params: float) -> dict[str, float]:
            calls.append(params)
            return {"y": params["x"] * params["scale"]}

        result = MonteCarloPropagator(
            PropagationConfig(mc_n_samples=100, mc_batch_size=100, mc_seed=42)
        ).propagate(
            scaled_sim,
            {"x": 10.0, "scale": 2.0},
            {"x": _normal_env(10.0, 1.0)},
            ["y"],
        )[0]

        assert result.diagnostics["n_failed"] == 0
        assert result.envelope.distribution_family == DistributionFamily.BOOTSTRAP
        assert result.envelope.point_estimate == pytest.approx(20.0, abs=1.0)
        assert {call.get("scale") for call in calls} == {2.0}

    def test_mc_seed_determinism(self) -> None:
        config = PropagationConfig(mc_n_samples=500, mc_seed=123)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        mc1 = MonteCarloPropagator(config)
        r1 = mc1.propagate(lambda x=0.0: {"y": x * 2}, {"x": 1.0}, envelopes, ["y"])

        mc2 = MonteCarloPropagator(config)
        r2 = mc2.propagate(lambda x=0.0: {"y": x * 2}, {"x": 1.0}, envelopes, ["y"])

        assert r1[0].envelope.point_estimate == pytest.approx(
            r2[0].envelope.point_estimate,
            abs=1e-6,
        )

    def test_mc_adaptive_stopping_early(self) -> None:
        adaptive = AdaptiveStoppingConfig(
            enabled=True,
            min_samples=50,
            max_samples=5000,
            ci_half_width_target=10.0,
            check_interval=50,
        )
        config = PropagationConfig(mc_n_samples=5000, mc_seed=42, adaptive_stopping=adaptive)
        mc = MonteCarloPropagator(config)
        envelopes = {"x": _normal_env(1.0, 0.01)}

        results = mc.propagate(
            lambda x=0.0: {"y": x},
            {"x": 1.0},
            envelopes,
            ["y"],
        )

        assert len(results) == 1
        assert (
            results[0].diagnostics.get("stopped_early", False) is True
            or results[0].diagnostics.get("n_samples", 5000) < 5000
        )

    def test_mc_qmc_vs_random_consistency(self) -> None:
        config_random = PropagationConfig(
            mc_n_samples=1000, mc_seed=42, mc_sampling_method="random"
        )
        config_sobol = PropagationConfig(mc_n_samples=1000, mc_seed=42, mc_sampling_method="sobol")

        envelopes = {"x": _normal_env(1.0, 0.5)}
        sim = lambda x=0.0: {"y": x * 2}

        r_random = MonteCarloPropagator(config_random).propagate(sim, {"x": 1.0}, envelopes, ["y"])
        r_sobol = MonteCarloPropagator(config_sobol).propagate(sim, {"x": 1.0}, envelopes, ["y"])

        npt.assert_allclose(
            r_random[0].envelope.point_estimate,
            r_sobol[0].envelope.point_estimate,
            rtol=0.3,
        )

    def test_mc_heuristic_fallback_on_sim_failures(self) -> None:
        def always_fail(**params: float) -> dict[str, float]:
            raise RuntimeError("sim exploded")

        config = PropagationConfig(mc_n_samples=100, mc_seed=42)
        mc = MonteCarloPropagator(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = mc.propagate(always_fail, {"x": 1.0}, envelopes, ["y"])

        assert len(results) == 1
        assert results[0].envelope.is_heuristic_ci is True

    def test_mc_qmc_failure_path_counts_failures_and_avoids_input_metric_fallback(self) -> None:
        def always_fail(**params: float) -> dict[str, float]:
            raise RuntimeError("sim exploded")

        config = PropagationConfig(
            mc_n_samples=128,
            mc_seed=7,
            mc_sampling_method="sobol",
        )
        envelopes = {"x": _normal_env(1.0, 0.5)}

        result = MonteCarloPropagator(config).propagate(
            always_fail,
            {"x": 1.0},
            envelopes,
            ["y"],
        )[0]

        assert result.diagnostics["n_failed"] == 128
        assert result.diagnostics["executor_failed_batches"] == 128
        assert result.envelope.metadata["failure"] == "insufficient_valid_samples"
        assert result.envelope.metadata["fallback_point_estimate_source"] != "nominal_params"
        assert result.envelope.point_estimate == pytest.approx(0.0)

    def test_mc_empty_metrics_returns_empty(self) -> None:
        config = PropagationConfig(mc_n_samples=100)
        mc = MonteCarloPropagator(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = mc.propagate(
            lambda x=0.0: {"y": x},
            {"x": 1.0},
            envelopes,
            [],
        )

        assert results == []

    def test_mc_sobol_chunking_preserves_requested_sample_count(self) -> None:
        config = PropagationConfig(
            mc_n_samples=130,
            mc_batch_size=70,
            mc_seed=11,
            mc_sampling_method="sobol",
        )
        result = MonteCarloPropagator(config).propagate(
            lambda x=0.0: {"y": x},
            {"x": 0.0},
            {"x": _normal_env(0.0, 1.0)},
            ["y"],
        )[0]

        assert result.diagnostics["n_samples"] == 130
        assert result.diagnostics["n_failed"] == 0

    def test_qmc_sampler_state_reuses_buffered_chunk(self) -> None:
        propagator = MonteCarloPropagator(
            PropagationConfig(
                mc_n_samples=140,
                mc_batch_size=70,
                mc_seed=5,
                mc_sampling_method="sobol",
            )
        )

        state = propagator._create_qmc_sampler_state(2)
        first, state = propagator._next_qmc_uniform_chunk(state, 70)
        second, state = propagator._next_qmc_uniform_chunk(state, 70)

        assert first.shape == (70, 2)
        assert second.shape == (70, 2)
        assert np.all((first >= 0.0) & (first <= 1.0))
        assert np.all((second >= 0.0) & (second <= 1.0))
        assert int(state["generated"]) == 140
        assert state["buffer"].shape[0] < 128
