from __future__ import annotations

import numpy as np
import numpy.testing as npt
import pytest

from polisyos.foundry.uncertainty.config import AdaptiveStoppingConfig, PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
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


class TestMonteCarloPropagator:
    def test_mc_linear_fn_approximates_delta(self) -> None:
        config = PropagationConfig(mc_n_samples=2000, mc_seed=42)
        mc = MonteCarloPropagator(config)
        envelopes = _declared_gaussian_product(
            {"x": _normal_env(1.0, 0.5), "z": _normal_env(2.0, 1.0)}
        )

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

    def test_unadmitted_legacy_adaptive_settings_run_fixed_maximum(self) -> None:
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
        assert results[0].diagnostics["stopped_early"] is False
        assert results[0].diagnostics["n_samples"] == 5000

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

    def test_mc_sobol_chunking_preserves_complete_rounded_net(self) -> None:
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

        assert result.diagnostics["n_samples"] == 256
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


def _declared_gaussian_product(envelopes):
    from polisyos.foundry.uncertainty.covariance import extract_std

    names = sorted(envelopes)
    return {
        name: env.model_copy(
            update={
                "metadata": {
                    **env.metadata,
                    "covariance_params": names,
                    "covariance_row": [
                        extract_std(env) ** 2 if column == name else 0.0 for column in names
                    ],
                }
            }
        )
        for name, env in envelopes.items()
    }
