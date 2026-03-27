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
    z = 1.96  # approx for 0.95
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


def _uniform_env(lo: float, hi: float) -> UncertaintyEnvelope:
    point = (lo + hi) / 2.0
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(lo, hi),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=True,
    )


def _linear_sim(**params: float) -> dict[str, float]:
    return {"y": 2.0 * params.get("x", 0.0) + 3.0 * params.get("z", 0.0)}


class TestAnalyticalRouting:
    def test_analytical_preferred_routes_correctly(self) -> None:
        config = PropagationConfig(preferred_method="analytical")
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _normal_env(1.0, 0.1), "z": _normal_env(2.0, 0.2)}
        weights = {"x": 2.0, "z": 3.0}

        results = dispatcher.propagate(
            _linear_sim,
            {"x": 1.0, "z": 2.0},
            envelopes,
            ["y"],
            weights=weights,
        )

        assert len(results) == 1
        assert results[0].method_used == PropagationMethod.ANALYTICAL
        assert results[0].envelope.propagation_method == PropagationMethod.ANALYTICAL

    def test_analytical_fallback_to_delta_on_nonlinear(self) -> None:
        """When preferred=analytical but inputs are non-normal, should fallback to delta or MC."""
        config = PropagationConfig(preferred_method="analytical")
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _uniform_env(0.5, 1.5)}
        weights = {"x": 2.0}

        results = dispatcher.propagate(
            lambda x=0.0: {"y": 2.0 * x},
            {"x": 1.0},
            envelopes,
            ["y"],
            weights=weights,
        )

        assert len(results) == 1
        # Non-normal inputs → analytical not applicable → falls through to delta/MC
        assert results[0].method_used in {
            PropagationMethod.DELTA_METHOD,
            PropagationMethod.MONTE_CARLO,
        }
        assert results[0].method_used != PropagationMethod.ANALYTICAL

    def test_analytical_output_matches_delta_for_linear(self) -> None:
        """Analytical and delta results should be close for a linear function."""
        envelopes = {"x": _normal_env(1.0, 0.1), "z": _normal_env(2.0, 0.2)}
        weights = {"x": 2.0, "z": 3.0}
        nominal = {"x": 1.0, "z": 2.0}

        analytical_config = PropagationConfig(preferred_method="analytical")
        analytical_disp = PropagationDispatcher(analytical_config)
        analytical_results = analytical_disp.propagate(
            _linear_sim, nominal, envelopes, ["y"], weights=weights,
        )

        delta_config = PropagationConfig(preferred_method="delta")
        delta_disp = PropagationDispatcher(delta_config)
        delta_results = delta_disp.propagate(
            _linear_sim, nominal, envelopes, ["y"],
        )

        a_env = analytical_results[0].envelope
        d_env = delta_results[0].envelope

        assert a_env.point_estimate == pytest.approx(d_env.point_estimate, abs=0.05)
        assert a_env.confidence_interval[0] == pytest.approx(
            d_env.confidence_interval[0], abs=0.1,
        )
        assert a_env.confidence_interval[1] == pytest.approx(
            d_env.confidence_interval[1], abs=0.1,
        )

    def test_auto_select_analytical_when_weights_provided(self) -> None:
        """Auto mode should prefer analytical when weights + all normal."""
        config = PropagationConfig(preferred_method="auto")
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _normal_env(1.0, 0.1), "z": _normal_env(2.0, 0.2)}
        weights = {"x": 2.0, "z": 3.0}

        results = dispatcher.propagate(
            _linear_sim, {"x": 1.0, "z": 2.0}, envelopes, ["y"], weights=weights,
        )

        assert results[0].method_used == PropagationMethod.ANALYTICAL

    def test_auto_select_without_weights_uses_delta_or_mc(self) -> None:
        """Auto mode without weights should not use analytical."""
        config = PropagationConfig(preferred_method="auto")
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _normal_env(1.0, 0.1), "z": _normal_env(2.0, 0.2)}

        results = dispatcher.propagate(
            _linear_sim, {"x": 1.0, "z": 2.0}, envelopes, ["y"],
        )

        assert results[0].method_used in {
            PropagationMethod.DELTA_METHOD,
            PropagationMethod.MONTE_CARLO,
        }
