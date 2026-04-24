from __future__ import annotations

import numpy.testing as npt

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.delta import DeltaMethodPropagator
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


def _uniform_env(lo: float, hi: float) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=(lo + hi) / 2.0,
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


class TestDeltaMethodPropagator:
    def test_delta_linear_fn_exact(self) -> None:
        """For y=2x+3z, var_y = 4*var_x + 9*var_z exactly."""
        config = PropagationConfig(delta_use_full_covariance=False)
        propagator = DeltaMethodPropagator(config)
        std_x, std_z = 0.5, 1.0
        envelopes = {"x": _normal_env(1.0, std_x), "z": _normal_env(2.0, std_z)}

        results = propagator.propagate(
            _linear_sim,
            {"x": 1.0, "z": 2.0},
            envelopes,
            ["y"],
        )

        assert len(results) == 1
        import math

        expected_std = math.sqrt(4 * std_x**2 + 9 * std_z**2)
        ci_width = results[0].envelope.ci_width
        z_val = 1.96
        actual_std = ci_width / (2 * z_val)
        npt.assert_allclose(actual_std, expected_std, rtol=0.05)

    def test_delta_nonlinear_approximation(self) -> None:
        """For y=x^2, at x=2 Jacobian=4, so output_std ≈ 4*input_std."""
        config = PropagationConfig(delta_use_full_covariance=False)
        propagator = DeltaMethodPropagator(config)
        std_x = 0.1
        envelopes = {"x": _normal_env(2.0, std_x)}

        def quad_sim(**params: float) -> dict[str, float]:
            x = params.get("x", 0.0)
            return {"y": x**2}

        results = propagator.propagate(
            quad_sim,
            {"x": 2.0},
            envelopes,
            ["y"],
        )

        assert len(results) == 1
        ci_width = results[0].envelope.ci_width
        z_val = 1.96
        actual_std = ci_width / (2 * z_val)
        npt.assert_allclose(actual_std, 4.0 * std_x, rtol=0.15)

    def test_delta_multi_output(self) -> None:
        def multi_sim(**params: float) -> dict[str, float]:
            x = params.get("x", 0.0)
            return {"a": 2.0 * x, "b": 3.0 * x}

        config = PropagationConfig()
        propagator = DeltaMethodPropagator(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = propagator.propagate(
            multi_sim,
            {"x": 1.0},
            envelopes,
            ["a", "b"],
        )

        assert len(results) == 2
        assert results[0].metric_id == "a"
        assert results[1].metric_id == "b"

    def test_delta_is_applicable_requires_normal(self) -> None:
        normal_envs = {"x": _normal_env(1.0, 0.5), "z": _normal_env(2.0, 1.0)}
        assert DeltaMethodPropagator.is_applicable(normal_envs) is True

        mixed_envs = {"x": _normal_env(1.0, 0.5), "z": _uniform_env(0.0, 4.0)}
        assert DeltaMethodPropagator.is_applicable(mixed_envs) is False

    def test_delta_propagation_result_metadata(self) -> None:
        config = PropagationConfig()
        propagator = DeltaMethodPropagator(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = propagator.propagate(
            lambda x=0.0: {"y": 2.0 * x},
            {"x": 1.0},
            envelopes,
            ["y"],
        )

        assert results[0].method_used == PropagationMethod.DELTA_METHOD
        assert results[0].envelope.propagation_method == PropagationMethod.DELTA_METHOD
