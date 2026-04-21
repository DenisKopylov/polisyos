from __future__ import annotations

import math
from statistics import NormalDist

import pytest

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.delta import DeltaMethodPropagator
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _normal_env(
    *,
    mean: float,
    std: float,
    confidence_level: float = 0.95,
    covariance_row: list[float] | None = None,
    covariance_params: list[str] | None = None,
) -> UncertaintyEnvelope:
    z = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    lo = mean - z * std
    hi = mean + z * std
    metadata: dict[str, object] = {}
    if covariance_row is not None:
        metadata["covariance_row"] = covariance_row
    if covariance_params is not None:
        metadata["covariance_params"] = covariance_params
    return UncertaintyEnvelope(
        point_estimate=mean,
        confidence_interval=(lo, hi),
        confidence_level=confidence_level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata=metadata,
    )


def test_delta_uses_full_covariance_when_available() -> None:
    envelopes = {
        "x": _normal_env(
            mean=1.0,
            std=1.0,
            covariance_row=[1.0, 0.5],
            covariance_params=["x", "y"],
        ),
        "y": _normal_env(
            mean=2.0,
            std=2.0,
            covariance_row=[0.5, 4.0],
            covariance_params=["x", "y"],
        ),
    }

    def sim_fn(**params):
        return {"z": 2.0 * params["x"] + params["y"]}

    propagator = DeltaMethodPropagator(PropagationConfig(delta_use_full_covariance=True))
    result = propagator.propagate(
        simulation_fn=sim_fn,
        nominal_params={"x": 1.0, "y": 2.0},
        input_envelopes=envelopes,
        output_metric_ids=["z"],
    )

    env = result[0].envelope
    z = NormalDist().inv_cdf((1.0 + env.confidence_level) / 2.0)
    std_out = (env.confidence_interval[1] - env.confidence_interval[0]) / (2.0 * z)

    expected_std = math.sqrt(10.0)
    assert std_out == pytest.approx(expected_std, rel=1e-3)
    assert env.composition_provenance is not None
    assert env.composition_provenance.composed_flavour == ComposedFlavour.DELTA
    assert env.composition_provenance.certificate_kind == CertificateKind.TAYLOR_REMAINDER


def test_dispatcher_falls_back_to_monte_carlo_for_non_differentiable_function() -> None:
    envelopes = {"x": _normal_env(mean=1.0, std=0.1)}

    def non_diff(**params):
        return {"z": float(params["x"]) ** 2}

    dispatcher = PropagationDispatcher(
        PropagationConfig(mc_n_samples=200, mc_batch_size=40, mc_min_valid_samples=20)
    )
    results = dispatcher.propagate(
        simulation_fn=non_diff,
        nominal_params={"x": 1.0},
        input_envelopes=envelopes,
        output_metric_ids=["z"],
        is_jax_differentiable=True,
    )

    assert results
    assert results[0].method_used == PropagationMethod.MONTE_CARLO


def test_monte_carlo_uses_heuristic_envelope_when_samples_fail() -> None:
    envelopes = {"x": _normal_env(mean=1.0, std=0.1)}

    def always_fail(**params):  # noqa: ARG001
        raise RuntimeError("boom")

    mc = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, mc_batch_size=25, mc_min_valid_samples=20)
    )
    results = mc.propagate(
        simulation_fn=always_fail,
        nominal_params={"x": 1.0},
        input_envelopes=envelopes,
        output_metric_ids=["z"],
    )

    env = results[0].envelope
    assert env.is_heuristic_ci is True
    assert env.gate_eligible is False
    assert env.interval_semantics == IntervalSemantics.HEURISTIC_RANGE
    assert env.confidence_interval == (env.point_estimate, env.point_estimate)
    assert env.composition_provenance is not None
    assert env.composition_provenance.composed_flavour == ComposedFlavour.MONTE_CARLO
