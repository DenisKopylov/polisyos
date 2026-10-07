from __future__ import annotations

from collections.abc import Mapping
from itertools import cycle

from polisyos.foundry.uncertainty.config import (
    AdaptiveStoppingConfig,
    PropagationConfig,
)
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _normal_env(point: float, std: float) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - 1.96 * std, point + 1.96 * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
    )


def _adaptive_config(*, target: float) -> PropagationConfig:
    return PropagationConfig(
        mc_batch_size=50,
        mc_seed=17,
        adaptive_stopping=AdaptiveStoppingConfig(
            enabled=True,
            min_samples=50,
            max_samples=240,
            ci_half_width_target=target,
            check_interval=60,
        ),
        compute_sensitivity=False,
    )


def test_legacy_adaptive_peeking_is_disabled_without_bounded_mean_profile() -> None:
    """Predictive spread cannot authorize repeated fixed-time interval peeking."""

    result = MonteCarloPropagator(_adaptive_config(target=0.01)).propagate(
        lambda **_: {"y": 10.0},
        {"x": 1.0},
        {"x": _normal_env(1.0, 0.01)},
        ["y"],
    )[0]

    assert result.diagnostics["stopped_early"] is False
    assert result.diagnostics["n_samples"] == 240


def test_adaptive_distribution_width_does_not_shrink_for_stable_wide_outputs() -> None:
    """More draws do not make a 99/101 output range satisfy a 1% width target."""

    outputs = cycle((99.0, 101.0))

    def wide_sim(**_: float) -> Mapping[str, float]:
        return {"y": next(outputs)}

    result = MonteCarloPropagator(_adaptive_config(target=0.01)).propagate(
        wide_sim,
        {"x": 1.0},
        {"x": _normal_env(1.0, 0.01)},
        ["y"],
    )[0]

    assert result.diagnostics["stopped_early"] is False
    assert result.diagnostics["n_samples"] == 240
