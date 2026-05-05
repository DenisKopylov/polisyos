from __future__ import annotations

from polisyos.foundry.uncertainty.config import AdaptiveStoppingConfig, PropagationConfig
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


def _constant_sim(**params: float) -> dict[str, float]:
    """Very low variance — should converge quickly."""
    return {"y": 10.0 + params.get("x", 0.0) * 0.001}


def _high_variance_sim(**params: float) -> dict[str, float]:
    """High sensitivity — unlikely to converge with tight target."""
    return {"y": params.get("x", 0.0) * 100.0}


class TestAdaptiveStopping:
    def test_adaptive_stops_early_on_convergence(self) -> None:
        config = PropagationConfig(
            mc_n_samples=200,
            adaptive_stopping=AdaptiveStoppingConfig(
                enabled=True,
                min_samples=200,
                max_samples=5000,
                ci_half_width_target=0.5,
                check_interval=200,
            ),
            compute_sensitivity=False,
        )
        propagator = MonteCarloPropagator(config)
        results = propagator.propagate(
            _constant_sim,
            {"x": 1.0},
            {"x": _normal_env(1.0, 0.01)},
            ["y"],
        )
        assert len(results) == 1
        diag = results[0].diagnostics
        assert diag["stopped_early"] is True
        assert diag["n_samples"] < 5000

    def test_adaptive_respects_min_samples(self) -> None:
        config = PropagationConfig(
            mc_n_samples=200,
            adaptive_stopping=AdaptiveStoppingConfig(
                enabled=True,
                min_samples=300,
                max_samples=5000,
                ci_half_width_target=10.0,  # Very loose — would stop immediately
                check_interval=100,
            ),
            compute_sensitivity=False,
        )
        propagator = MonteCarloPropagator(config)
        results = propagator.propagate(
            _constant_sim,
            {"x": 1.0},
            {"x": _normal_env(1.0, 0.01)},
            ["y"],
        )
        assert results[0].diagnostics["n_samples"] >= 300

    def test_adaptive_respects_max_samples(self) -> None:
        config = PropagationConfig(
            mc_n_samples=200,
            adaptive_stopping=AdaptiveStoppingConfig(
                enabled=True,
                min_samples=200,
                max_samples=500,
                ci_half_width_target=1e-10,  # Impossibly tight
                check_interval=100,
            ),
            compute_sensitivity=False,
        )
        propagator = MonteCarloPropagator(config)
        results = propagator.propagate(
            _high_variance_sim,
            {"x": 1.0},
            {"x": _normal_env(1.0, 1.0)},
            ["y"],
        )
        assert results[0].diagnostics["n_samples"] <= 500
        assert results[0].diagnostics["stopped_early"] is False

    def test_disabled_adaptive_uses_fixed_samples(self) -> None:
        config = PropagationConfig(
            mc_n_samples=300,
            adaptive_stopping=AdaptiveStoppingConfig(enabled=False),
            compute_sensitivity=False,
        )
        propagator = MonteCarloPropagator(config)
        results = propagator.propagate(
            _constant_sim,
            {"x": 1.0},
            {"x": _normal_env(1.0, 0.01)},
            ["y"],
        )
        assert results[0].diagnostics["n_samples"] == 300
        assert results[0].diagnostics["stopped_early"] is False
