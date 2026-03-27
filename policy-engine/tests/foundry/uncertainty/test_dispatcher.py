from __future__ import annotations

import pytest

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher


def _normal_env(point: float, std: float, level: float = 0.95) -> UncertaintyEnvelope:
    z = 1.96
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
    return {"y": 2.0 * params.get("x", 0.0)}


class TestDispatcherEdgeCases:
    def test_dispatcher_empty_envelopes_returns_empty(self) -> None:
        dispatcher = PropagationDispatcher()
        results = dispatcher.propagate(
            _linear_sim, {"x": 1.0}, {}, ["y"],
        )
        assert results == []

    def test_dispatcher_empty_metric_ids_returns_empty(self) -> None:
        dispatcher = PropagationDispatcher()
        envelopes = {"x": _normal_env(1.0, 0.5)}
        results = dispatcher.propagate(
            _linear_sim, {"x": 1.0}, envelopes, [],
        )
        assert results == []

    def test_dispatcher_explicit_mc_mode(self) -> None:
        config = PropagationConfig(preferred_method="monte_carlo", mc_n_samples=200, mc_seed=42)
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = dispatcher.propagate(
            _linear_sim, {"x": 1.0}, envelopes, ["y"],
        )

        assert len(results) == 1
        assert results[0].method_used == PropagationMethod.MONTE_CARLO

    def test_dispatcher_explicit_delta_mode(self) -> None:
        config = PropagationConfig(preferred_method="delta")
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = dispatcher.propagate(
            _linear_sim, {"x": 1.0}, envelopes, ["y"],
        )

        assert len(results) == 1
        assert results[0].method_used == PropagationMethod.DELTA_METHOD

    def test_dispatcher_non_differentiable_fallback(self) -> None:
        config = PropagationConfig(preferred_method="auto", mc_n_samples=200, mc_seed=42)
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = dispatcher.propagate(
            _linear_sim,
            {"x": 1.0},
            envelopes,
            ["y"],
            is_jax_differentiable=False,
        )

        assert len(results) == 1
        assert results[0].method_used == PropagationMethod.MONTE_CARLO
