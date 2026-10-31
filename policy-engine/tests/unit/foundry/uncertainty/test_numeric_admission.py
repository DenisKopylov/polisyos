"""Real input laws must survive numerical admission before evaluator effects."""

from __future__ import annotations

import warnings
from fractions import Fraction

import jax.numpy as jnp
import numpy as np
import numpy.testing as npt
import pytest

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.covariance import build_covariance_matrix
from polisyos.foundry.uncertainty.delta import DeltaMethodPropagator
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _normal(std: float, *, declared_covariance: bool = True) -> UncertaintyEnvelope:
    metadata: dict[str, object] = {"std": std}
    if declared_covariance:
        metadata.update(covariance_row=[std * std], covariance_params=["x"])
    return UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.959963984540054 * std, 1.959963984540054 * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata=metadata,
    )


def _propagator(route: str, sampling_method: str, *, full_covariance: bool = True):
    config = PropagationConfig(
        mc_n_samples=128,
        mc_batch_size=128,
        mc_sampling_method=sampling_method,
        preferred_method="monte_carlo",
        delta_use_full_covariance=full_covariance,
        delta_covariance_jitter=0.0,
        compute_sensitivity=False,
    )
    if route == "delta":
        return DeltaMethodPropagator(config)
    if route == "dispatcher":
        return PropagationDispatcher(config)
    return MonteCarloPropagator(config)


@pytest.mark.parametrize("route", ["mc", "dispatcher", "delta"])
@pytest.mark.parametrize("sampling_method", ["random", "sobol", "halton"])
@pytest.mark.parametrize("std", [1e20, 1e-25, 1e-20])
def test_covariance_backend_range_refuses_before_evaluator(
    route: str, sampling_method: str, std: float
) -> None:
    calls: list[float] = []

    def evaluator(x: float) -> dict[str, float]:
        calls.append(x)
        return {"y": x}

    error = None
    results = []
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        try:
            results = _propagator(route, sampling_method).propagate(
                evaluator, {"x": 0.0}, {"x": _normal(std)}, ["y"]
            )
        except (ValueError, FloatingPointError) as caught:
            error = caught

    assert calls == [], "a range-invalid covariance reached the evaluator"
    assert error is None, "unsupported covariance should keep the existing limited result"
    assert len(results) == 1
    assert results[0].envelope.gate_eligible is False
    assert results[0].envelope.metadata["failure"] == "incompatible_dependency"
    assert not any("overflow" in str(item.message) for item in observed)


@pytest.mark.parametrize("full_covariance", [False, True])
@pytest.mark.parametrize("std", [1e20, 1e-25, 1e-20])
def test_covariance_builder_refuses_nonfinite_or_subnormal_float32_law(
    full_covariance: bool, std: float
) -> None:
    with pytest.raises(ValueError, match="float32"):
        build_covariance_matrix(
            ["x"],
            {"x": _normal(std, declared_covariance=full_covariance)},
            use_full_covariance=full_covariance,
            jitter=0.0,
            preserve_singular=True,
        )


@pytest.mark.parametrize("full_covariance", [False, True])
def test_float32_minimum_normal_covariance_remains_nonzero_in_actual_jax_arithmetic(
    full_covariance: bool,
) -> None:
    minimum = np.finfo(np.float32).tiny
    covariance = build_covariance_matrix(
        ["x"],
        {"x": _normal(float(np.sqrt(minimum)), declared_covariance=full_covariance)},
        use_full_covariance=full_covariance,
        jitter=0.0,
        preserve_singular=True,
    )
    direction = jnp.ones((1,), dtype=jnp.float32)
    quadratic = float(direction @ covariance @ direction)
    assert quadratic == float(minimum)
    assert quadratic > 0.0


@pytest.mark.parametrize("route", ["mc", "dispatcher"])
@pytest.mark.parametrize("sampling_method", ["random", "sobol", "halton"])
@pytest.mark.parametrize("field", ["samples", "weights"])
@pytest.mark.parametrize(
    "bad_kind",
    [
        "complex",
        "real_complex",
        "object_complex",
        "string",
        "tiny",
        "integer_loss",
        "object_integer_loss",
        "list_integer_loss",
        "nonfinite",
    ],
)
def test_empirical_real_domain_refuses_before_coercion_or_evaluator(
    route: str, sampling_method: str, field: str, bad_kind: str
) -> None:
    bad_values = {
        "complex": np.array([0.25 + 0.1j, 0.75 - 0.1j]),
        "real_complex": np.array([0.25 + 0j, 0.75 + 0j]),
        "object_complex": np.array([0.25 + 0.1j, 0.75 - 0.1j], dtype=object),
        "string": np.array(["0.25", "0.75"]),
        "tiny": np.array([Fraction(1, 10**400), Fraction(1)], dtype=object),
        "integer_loss": np.array([2**53 + 1, 2**53 + 2], dtype=np.int64),
        "object_integer_loss": np.array([np.int64(2**53 + 1), 0.75], dtype=object),
        "list_integer_loss": [np.int64(2**53 + 1), 0.75],
        "nonfinite": np.array([np.nan, 1.0]),
    }[bad_kind]
    # model_copy deliberately retains the raw caller representation. A validated
    # constructor would already have erased the numerical-domain discriminator.
    carrier = PosteriorSamplesCarrier(samples=(0.25, 0.75), weights=(1.0, 1.0)).model_copy(
        update={field: bad_values}
    )
    envelope = UncertaintyEnvelope(
        point_estimate=0.5,
        confidence_interval=(0.25, 0.75),
        confidence_level=0.95,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
    ).model_copy(update={"distribution_payload": carrier})
    calls: list[float] = []

    def evaluator(x: float) -> dict[str, float]:
        calls.append(x)
        return {"y": x}

    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        result = _propagator(route, sampling_method).propagate(
            evaluator, {"x": 0.5}, {"x": envelope}, ["y"]
        )[0]

    assert calls == [], "an unadmitted empirical domain reached the evaluator"
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["failure"] == "incompatible_joint_law"
    assert not any("Casting complex values" in str(item.message) for item in observed)


@pytest.mark.parametrize("dtype", [np.float32, np.float64, object])
@pytest.mark.parametrize("route", ["mc", "dispatcher"])
def test_representable_real_empirical_support_is_preserved(dtype: object, route: str) -> None:
    carrier = PosteriorSamplesCarrier(samples=(0.25, 0.75), weights=(1.0, 1.0)).model_copy(
        update={
            "samples": np.array([0.25, 0.75], dtype=dtype),
            "weights": np.array([1, 1], dtype=dtype),
        }
    )
    envelope = UncertaintyEnvelope(
        point_estimate=0.5,
        confidence_interval=(0.25, 0.75),
        confidence_level=0.95,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
    ).model_copy(update={"distribution_payload": carrier})
    calls: list[float] = []

    def evaluator(x: float) -> dict[str, float]:
        calls.append(float(x))
        return {"y": x}

    with warnings.catch_warnings(record=True):
        result = _propagator(route, "random").propagate(
            evaluator, {"x": 0.5}, {"x": envelope}, ["y"]
        )[0]
    samples = result.envelope.distribution_payload
    assert isinstance(samples, PosteriorSamplesCarrier)
    assert len(calls) == 129
    assert calls[0] == 0.5
    assert set(calls[1:]) == {0.25, 0.75}
    assert len(samples.samples) == 128
    assert set(samples.samples) == {0.25, 0.75}


@pytest.mark.parametrize("route", ["mc", "dispatcher"])
@pytest.mark.parametrize("sampling_method", ["random", "sobol", "halton"])
def test_zero_standard_deviation_remains_exact_point_mass(route: str, sampling_method: str) -> None:
    result = _propagator(route, sampling_method).propagate(
        lambda x: {"y": x},
        {"x": 0.0},
        {"x": _normal(0.0, declared_covariance=False)},
        ["y"],
    )[0]

    carrier = result.envelope.distribution_payload
    assert isinstance(carrier, PosteriorSamplesCarrier)
    npt.assert_array_equal(carrier.samples, np.zeros(128))
    assert result.envelope.metadata["mc_std"] == 0.0
    assert result.envelope.confidence_interval == (0.0, 0.0)
