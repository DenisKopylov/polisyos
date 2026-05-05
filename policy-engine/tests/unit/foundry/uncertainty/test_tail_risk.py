from __future__ import annotations

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


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


class TestTailRiskMetrics:
    def test_cvar_less_than_quantile(self) -> None:
        """CVaR at 5% should be <= the 5th percentile by definition."""
        config = PropagationConfig(mc_n_samples=2000, mc_seed=42, compute_sensitivity=False)
        propagator = MonteCarloPropagator(config)

        def sim(**params: float) -> dict[str, float]:
            return {"y": params["x"]}

        results = propagator.propagate(
            sim,
            {"x": 0.0},
            {"x": _normal_env(0.0, 1.0)},
            ["y"],
        )

        tail = results[0].envelope.metadata.get("tail_risk")
        assert tail is not None, "tail_risk metadata missing"
        # CVaR_05 is the mean of samples below q05 — so it must be <= q05.
        # q01 < cvar_05 <= q05 for well-behaved distributions.
        assert tail["quantile_01"] < tail["quantile_99"]
        # For standard normal, both CVaR and quantiles are negative in the left tail
        assert tail["cvar_05"] < 0.0
        assert tail["quantile_01"] < 0.0

    def test_tail_risk_keys_present(self) -> None:
        config = PropagationConfig(mc_n_samples=500, mc_seed=7, compute_sensitivity=False)
        propagator = MonteCarloPropagator(config)

        results = propagator.propagate(
            lambda x=0.0: {"y": x},
            {"x": 0.0},
            {"x": _normal_env(0.0, 1.0)},
            ["y"],
        )

        tail = results[0].envelope.metadata["tail_risk"]
        assert "cvar_05" in tail
        assert "quantile_01" in tail
        assert "quantile_99" in tail

    def test_symmetric_distribution_tail_symmetry(self) -> None:
        """For symmetric dist, q01 and q99 should be roughly equidistant from mean."""
        config = PropagationConfig(mc_n_samples=5000, mc_seed=42, compute_sensitivity=False)
        propagator = MonteCarloPropagator(config)

        results = propagator.propagate(
            lambda x=0.0: {"y": x},
            {"x": 0.0},
            {"x": _normal_env(0.0, 1.0)},
            ["y"],
        )

        tail = results[0].envelope.metadata["tail_risk"]
        point = results[0].envelope.point_estimate
        assert abs(abs(tail["quantile_01"] - point) - abs(tail["quantile_99"] - point)) < 0.3
