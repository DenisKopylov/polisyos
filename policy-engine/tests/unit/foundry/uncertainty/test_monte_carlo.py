from __future__ import annotations

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
    names: list[str], covariance: np.ndarray, columns: list[str]
) -> dict[str, UncertaintyEnvelope]:
    """Build declared Gaussian coordinates with independently known covariance."""
    inputs = {}
    for row, name in enumerate(names):
        std = float(np.sqrt(covariance[row, row]))
        inputs[name] = _normal_env(0.0, std).model_copy(
            update={
                "distribution_payload": ParametricFitCarrier(
                    family=DistributionFamily.NORMAL, parameters={"mean": 0.0, "std": std}
                ),
                "gate_eligible": False,
                "metadata": {
                    "covariance_row": [float(covariance[row, names.index(col)]) for col in columns],
                    "covariance_params": columns,
                },
            }
        )
    return inputs


@pytest.mark.parametrize("sampling_method", ["random", "sobol", "halton"])
def test_mc_gaussian_joint_draws_preserve_singular_law_and_covariance_axes(
    sampling_method: str,
) -> None:
    """Every draw stays on a declared rank-one Gaussian support after axis reorder."""
    names = ["a", "b", "c"]
    scales = np.asarray([1.0, 2.0, 3.0])
    inputs = _joint_normal_inputs(names, np.outer(scales, scales), ["c", "a", "b"])
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=256,
            mc_batch_size=60,
            mc_sampling_method=sampling_method,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda a, b, c: {"y": 2.0 * a - b, "z": 3.0 * a - c},
        dict.fromkeys(names, 0.0),
        inputs,
        ["y", "z"],
    )

    for output in result:
        payload = output.envelope.distribution_payload
        assert isinstance(payload, PosteriorSamplesCarrier)
        npt.assert_allclose(payload.samples, 0.0, atol=2e-6, rtol=0.0)
        assert output.diagnostics["n_failed"] == 0
        assert output.envelope.gate_eligible is False
        assert output.envelope.metadata["gaussian_joint_identity_status"] == (
            "declared_non_authoritative"
        )
        reopened = UncertaintyEnvelope.model_validate_json(output.envelope.model_dump_json())
        assert isinstance(reopened.distribution_payload, PosteriorSamplesCarrier)
        npt.assert_allclose(reopened.distribution_payload.samples, 0.0, atol=2e-6, rtol=0.0)


def test_mc_declared_gaussian_joint_model_cannot_grant_authority_from_marginals() -> None:
    """Admitted marginal envelopes do not verify the extra joint-Gaussian assumption."""
    inputs = {
        name: envelope.model_copy(update={"gate_eligible": True})
        for name, envelope in _joint_normal_inputs(["a", "b"], np.ones((2, 2)), ["a", "b"]).items()
    }
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
    ).propagate(lambda a, b: {"y": a - b}, {"a": 0.0, "b": 0.0}, inputs, ["y"])[0]

    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["gaussian_joint_identity_status"] == (
        "declared_non_authoritative"
    )


@pytest.mark.parametrize("sampling_method", ["random", "sobol", "halton"])
def test_mc_gaussian_independent_control_retains_nonzero_difference_variance(
    sampling_method: str,
) -> None:
    """Independent Gaussian coordinates must retain their variance of the difference."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=1024,
            mc_batch_size=128,
            mc_sampling_method=sampling_method,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda a, b: {"y": a - b},
        {"a": 0.0, "b": 0.0},
        _joint_normal_inputs(["a", "b"], np.eye(2), ["b", "a"]),
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert np.var(payload.samples) == pytest.approx(2.0, abs=0.3)


@pytest.mark.parametrize("sampling_method", ["random", "sobol", "halton"])
def test_mc_invalid_gaussian_covariance_is_refused_before_model_calls(
    sampling_method: str,
) -> None:
    """A materially indefinite declaration cannot become independent fallback samples."""
    calls = []

    def simulation(**params: float) -> dict[str, float]:
        calls.append(params)
        return {"y": params["a"] - params["b"]}

    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, mc_sampling_method=sampling_method)
    ).propagate(
        simulation,
        {"a": 0.0, "b": 0.0},
        _joint_normal_inputs(["a", "b"], np.asarray([[1.0, 2.0], [2.0, 1.0]]), ["a", "b"]),
        ["y"],
    )[0]

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
