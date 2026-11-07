from __future__ import annotations

from collections.abc import Mapping
from itertools import cycle

import numpy as np
import pytest

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


def test_adaptive_stopping_reaches_non_divisible_check_boundary() -> None:
    """A 50-row batch must be split to evaluate the 60-row boundary."""

    result = MonteCarloPropagator(_adaptive_config(target=0.01)).propagate(
        lambda **_: {"y": 10.0},
        {"x": 1.0},
        {"x": _normal_env(1.0, 0.01)},
        ["y"],
    )[0]

    assert result.diagnostics["stopped_early"] is True
    assert result.diagnostics["n_samples"] == 60


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


def test_stopping_profile_names_full_width_and_keeps_legacy_serialization() -> None:
    """Both names keep the historical full-width heuristic, not an MCSE claim."""
    current = AdaptiveStoppingConfig.model_validate(
        {"enabled": True, "relative_full_width_target": 0.015}
    )
    historical = AdaptiveStoppingConfig.model_validate(
        {"enabled": True, "ci_half_width_target": 0.015}
    )
    assert current == historical
    assert current.relative_full_width_target == 0.015
    serialized = current.model_dump(mode="json")
    assert serialized["ci_half_width_target"] == 0.015
    assert "relative_full_width_target" not in serialized
    assert AdaptiveStoppingConfig.model_validate(serialized) == current
    with pytest.raises(ValueError, match="only one"):
        AdaptiveStoppingConfig.model_validate(
            {"relative_full_width_target": 0.015, "ci_half_width_target": 0.02}
        )

    propagator = MonteCarloPropagator()
    for n in (200, 10_000):
        values = {"y": np.resize(np.array([99.0, 101.0]), n)}
        assert not propagator._check_adaptive_stop(n, current, values, ["y"], 0.05)
        constant = {"y": np.full(n, 100.0)}
        assert propagator._check_adaptive_stop(n, current, constant, ["y"], 0.05)


def test_native_stop_result_declares_width_heuristic_and_unattempted_draws() -> None:
    """A real early stop remains candidate-only and declares the actual stopping rule."""
    result = MonteCarloPropagator(_adaptive_config(target=0.01)).propagate(
        lambda **_: {"y": 100.0},
        {"x": 1.0},
        {"x": _normal_env(1.0, 0.01)},
        ["y"],
    )[0]

    expected_profile = {
        "profile": "relative_full_output_width_heuristic_v1",
        "relative_full_width_target": 0.01,
        "stop_reason": "reached_width_target",
        "is_monte_carlo_standard_error": False,
    }
    assert result.envelope.metadata["adaptive_stopping_profile"] == expected_profile
    assert result.diagnostics["adaptive_stopping_profile"] == expected_profile
    assert result.diagnostics["draw_outcome_provenance"]["unattempted_draw_count"] == 180
    assert result.envelope.gate_eligible is False
