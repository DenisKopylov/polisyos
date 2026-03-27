from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import kstest

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.foundry.uncertainty.quasi_mc import QuasiMCSampler


def _normal_env(point: float, std: float) -> UncertaintyEnvelope:
    z = 1.96
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - z * std, point + z * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
    )


class TestQuasiMCSampler:
    def test_sobol_samples_uniformity(self) -> None:
        sampler = QuasiMCSampler(method="sobol", seed=42)
        samples = sampler.sample(1024, 3)

        assert samples.shape == (1024, 3)
        for dim in range(3):
            _, p_value = kstest(samples[:, dim], "uniform")
            assert p_value > 0.05, f"Dim {dim} failed KS test: p={p_value}"

    def test_halton_samples_uniformity(self) -> None:
        sampler = QuasiMCSampler(method="halton", seed=42)
        samples = sampler.sample(1000, 3)

        assert samples.shape == (1000, 3)
        for dim in range(3):
            _, p_value = kstest(samples[:, dim], "uniform")
            assert p_value > 0.05, f"Dim {dim} failed KS test: p={p_value}"

    def test_halton_dimensionality(self) -> None:
        sampler = QuasiMCSampler(method="halton", seed=42)
        for n_dims in (1, 5, 20):
            samples = sampler.sample(500, n_dims)
            assert samples.shape == (500, n_dims)
            assert np.all((samples >= 0.0) & (samples <= 1.0))

    def test_power_of_two_rounding(self) -> None:
        sampler = QuasiMCSampler(method="sobol", seed=42)
        samples = sampler.sample(1000, 2)
        assert samples.shape == (1000, 2)

    def test_unknown_method_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown QMC method"):
            QuasiMCSampler(method="latin")

    def test_samples_in_unit_cube(self) -> None:
        sampler = QuasiMCSampler(method="sobol", seed=42)
        samples = sampler.sample(512, 5)
        assert np.all(samples >= 0.0)
        assert np.all(samples <= 1.0)


class TestQMCVarianceReduction:
    def test_sobol_variance_reduction(self) -> None:
        """QMC CI width should be narrower than pseudo-random MC for the same n_samples."""
        envelopes = {"x": _normal_env(1.0, 0.5), "z": _normal_env(2.0, 0.5)}
        nominal = {"x": 1.0, "z": 2.0}

        def sim(**params: float) -> dict[str, float]:
            return {"y": 2.0 * params["x"] + 3.0 * params["z"]}

        qmc_config = PropagationConfig(
            mc_n_samples=500,
            mc_sampling_method="sobol",
            mc_seed=42,
        )
        random_config = PropagationConfig(
            mc_n_samples=500,
            mc_sampling_method="random",
            mc_seed=42,
        )

        qmc_results = MonteCarloPropagator(qmc_config).propagate(
            sim, nominal, envelopes, ["y"],
        )
        random_results = MonteCarloPropagator(random_config).propagate(
            sim, nominal, envelopes, ["y"],
        )

        qmc_width = qmc_results[0].envelope.ci_width
        random_width = random_results[0].envelope.ci_width

        # QMC should produce tighter or comparable CIs
        assert qmc_width <= random_width * 1.1, (
            f"QMC width {qmc_width} unexpectedly wider than random {random_width}"
        )
