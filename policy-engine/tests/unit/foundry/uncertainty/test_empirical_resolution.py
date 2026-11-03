"""Empirical inverse-CDF semantics at representable probability boundaries."""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import numpy.testing as npt
import pytest

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.covariance import build_covariance_matrix
from polisyos.foundry.uncertainty.empirical import (
    EmpiricalNumericResolutionError,
    empirical_weighted_moments,
    prepare_empirical_cdf,
)
from polisyos.foundry.uncertainty.monte_carlo import (
    MonteCarloPropagator,
    _empirical_indices_from_uniform,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NumericPolicySpec,
    NumericToleranceMode,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _carrier(weights: tuple[float, ...]) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        numeric_policy=NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT),
        point_estimate=0.0,
        confidence_interval=(-1.0, 1.0),
        confidence_level=0.95,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        distribution_payload=PosteriorSamplesCarrier(samples=(-1.0, 1.0), weights=weights),
        sample_size=2,
        gate_eligible=False,
    )


def test_inverse_cdf_preserves_small_representable_tail_and_zero_weight_boundaries() -> None:
    """Right-continuous intervals retain a small finite endpoint, without Gaussian clipping."""
    points = np.array([0.0, 5e-13, 1e-12, np.nextafter(1.0, 0.0)])
    npt.assert_array_equal(
        _empirical_indices_from_uniform(points, np.array([1e-12, 1.0 - 1e-12])),
        [0, 0, 1, 1],
    )
    npt.assert_array_equal(
        _empirical_indices_from_uniform(
            np.array([0.0, 0.2, np.nextafter(1.0, 0.0)]),
            np.array([0.0, 0.2, 0.8, 0.0]),
        ),
        [1, 2, 2],
    )


@pytest.mark.parametrize("point", [-1e-12, 1.0, 1.1, float("nan"), float("inf")])
def test_inverse_cdf_rejects_uniform_values_outside_its_domain(point: float) -> None:
    """Invalid inputs must not be clamped into a seemingly valid sampled law."""
    with pytest.raises(ValueError, match="uniform"):
        _empirical_indices_from_uniform(np.array([point]), np.array([0.2, 0.8]))


def test_inverse_cdf_rejects_positive_weight_lost_in_cumulative_rounding() -> None:
    """A positive atom whose float64 interval collapses is not silently removed."""
    with pytest.raises(ValueError, match="numeric resolution"):
        _empirical_indices_from_uniform(np.array([0.0]), np.array([1.0, 1e-20]))


def test_inverse_cdf_rejects_tail_interval_wholly_above_its_uniform_domain() -> None:
    """A rising CDF is insufficient when its last interval is beyond 1."""
    weights = np.array([0.01] * 100 + [math.ulp(1.0)])
    probabilities = weights / np.sum(weights)
    cumulative = np.cumsum(probabilities)
    assert cumulative[-2] >= 1.0
    assert cumulative[-1] > cumulative[-2]
    with pytest.raises(ValueError, match="numeric resolution"):
        _empirical_indices_from_uniform(np.array([0.0]), weights)


def test_weighted_joint_moments_follow_the_actual_rows() -> None:
    means, covariance = empirical_weighted_moments([(0.0, 0.0), (10.0, 20.0)], [0.99, 0.01])
    expected_mean = [Fraction(1, 10), Fraction(1, 5)]
    expected_cov = [[Fraction(99, 100), Fraction(99, 50)], [Fraction(99, 50), Fraction(99, 25)]]
    npt.assert_allclose(means, [float(value) for value in expected_mean], rtol=1e-15, atol=0)
    npt.assert_allclose(
        covariance,
        [[float(value) for value in row] for row in expected_cov],
        rtol=1e-15,
        atol=0,
    )


def test_moment_admission_is_distinct_from_finite_sampling_cdf() -> None:
    with pytest.raises(EmpiricalNumericResolutionError, match="numeric resolution"):
        prepare_empirical_cdf([1.0, 1e-20])
    means, covariance = empirical_weighted_moments([(0.0,), (1.0,)], [1.0, 1e-20])
    assert means[0] == pytest.approx(1e-20, rel=1e-15, abs=0)
    assert covariance[0, 0] == pytest.approx(1e-20, rel=1e-15, abs=0)


@pytest.mark.parametrize("value", [1e-200, 1e200])
def test_unrepresentable_empirical_variance_does_not_become_zero_or_infinity(value: float) -> None:
    with pytest.raises(EmpiricalNumericResolutionError, match="representable"):
        empirical_weighted_moments([(0.0,), (value,)], [0.5, 0.5])


def test_empirical_moment_input_cannot_erase_integer_support() -> None:
    with pytest.raises(ValueError, match="cannot change"):
        empirical_weighted_moments([(0,), (2**60 + 1,)], [1.0, 1.0])


def test_equal_empirical_rows_remain_an_exact_point_mass() -> None:
    means, covariance = empirical_weighted_moments([(1.0,)] * 49, [1.0] * 49)
    npt.assert_array_equal(means, [1.0])
    npt.assert_array_equal(covariance, [[0.0]])


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_tiny_paired_rows_keep_representable_cross_covariance(sign: float) -> None:
    point = 1e-161
    rows = [(point, sign * point), (-point, -sign * point)] * 50
    means, covariance = empirical_weighted_moments(rows, [1.0] * 100)
    expected = float(Fraction.from_float(point) ** 2)
    assert expected > 0.0
    npt.assert_array_equal(means, [0.0, 0.0])
    npt.assert_array_equal(covariance, [[expected, sign * expected], [sign * expected, expected]])


def test_empirical_covariance_retains_mean_offset_below_output_ulp() -> None:
    anchor = 1e16
    rows = [(anchor, anchor), (anchor + 2.0, anchor + 2.0)]
    means, covariance = empirical_weighted_moments(rows, [1.0, 1.0])
    exact_values = [Fraction.from_float(row[0]) for row in rows]
    exact_mean = sum(exact_values, Fraction()) / 2
    expected_variance = sum((value - exact_mean) ** 2 for value in exact_values) / 2
    npt.assert_array_equal(means, [float(exact_mean), float(exact_mean)])
    npt.assert_array_equal(covariance, [[float(expected_variance)] * 2] * 2)


def test_foundry_covariance_uses_aligned_weighted_rows_and_refuses_lost_alignment() -> None:
    def envelope(point: float, high: float, joint_id: str | None) -> UncertaintyEnvelope:
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(0.0, high),
            confidence_level=0.95,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.BOOTSTRAP,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            distribution_payload=PosteriorSamplesCarrier(
                samples=(0.0, high), weights=(0.99, 0.01), sample_axis="row"
            ),
            gate_eligible=False,
            metadata={} if joint_id is None else {"joint_sample_id": joint_id},
        )

    inputs = {"x": envelope(0.1, 10.0, "rows"), "y": envelope(0.2, 20.0, "rows")}
    actual = build_covariance_matrix(["x", "y"], inputs, use_full_covariance=True, jitter=0.0)
    expected = [[float(Fraction(99, 100)), float(Fraction(99, 50))], [1.98, 3.96]]
    npt.assert_allclose(np.asarray(actual), expected, rtol=1e-6, atol=0)
    with pytest.raises(ValueError, match="discard"):
        build_covariance_matrix(["x", "y"], inputs, use_full_covariance=False, jitter=0.0)
    inputs["y"] = envelope(0.2, 20.0, None)
    with pytest.raises(ValueError, match="joint_law"):
        build_covariance_matrix(["x", "y"], inputs, use_full_covariance=True, jitter=0.0)


@pytest.mark.parametrize("sampling_method", ["random", "sobol"])
def test_native_sampler_reports_collapsed_positive_source_mass_before_evaluation(
    sampling_method: str,
) -> None:
    """Both routes withhold success and leave the original positive source weight intact."""
    envelope = _carrier((1.0, 1e-20))
    calls: list[float] = []

    def evaluate(*, x: float) -> dict[str, float]:
        calls.append(float(x))
        return {"y": x}

    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=100,
            mc_batch_size=50,
            mc_min_valid_samples=10,
            mc_sampling_method=sampling_method,
            compute_sensitivity=False,
        )
    ).propagate(evaluate, {"x": 0.0}, {"x": envelope}, ["y"])[0]

    assert result.envelope.distribution_family is DistributionFamily.UNKNOWN
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["failure"] == "empirical_numeric_resolution"
    assert envelope.distribution_payload is not None
    assert isinstance(envelope.distribution_payload, PosteriorSamplesCarrier)
    assert envelope.distribution_payload.weights == (1.0, 1e-20)
    assert calls == []


@pytest.mark.parametrize("sampling_method", ["random", "sobol"])
def test_paired_empirical_columns_refuse_distinct_representable_small_weights(
    sampling_method: str,
) -> None:
    """A shared row label cannot silently reconcile different actual weight laws."""
    left = _carrier((1e-12, 1.0 - 1e-12)).model_copy(
        update={"metadata": {"joint_sample_id": "declared-candidate-rows"}}
    )
    right = _carrier((1.5e-12, 1.0 - 1.5e-12)).model_copy(
        update={"metadata": {"joint_sample_id": "declared-candidate-rows"}}
    )
    calls: list[tuple[float, float]] = []

    def evaluate(*, x: float, y: float) -> dict[str, float]:
        calls.append((float(x), float(y)))
        return {"difference": x - y}

    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=100,
            mc_batch_size=50,
            mc_min_valid_samples=10,
            mc_sampling_method=sampling_method,
            compute_sensitivity=False,
        )
    ).propagate(evaluate, {"x": 0.0, "y": 0.0}, {"x": left, "y": right}, ["difference"])[0]

    assert result.envelope.distribution_family is DistributionFamily.UNKNOWN
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["failure"] == "incompatible_joint_law"
    assert calls == []


@pytest.mark.parametrize("sampling_method", ["random", "sobol"])
def test_native_result_discloses_empirical_sampling_algorithm(sampling_method: str) -> None:
    """The native consumer can inspect the changed producer-asserted numeric profile."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=100,
            mc_batch_size=50,
            mc_min_valid_samples=10,
            mc_sampling_method=sampling_method,
            compute_sensitivity=False,
        )
    ).propagate(lambda *, x: {"y": x}, {"x": 0.0}, {"x": _carrier((0.25, 0.75))}, ["y"])[0]

    profile = result.envelope.metadata["empirical_sampling_profile"]
    assert profile["algorithm"] == "float64_empirical_cdf_inverse_v1"
    assert profile["uniform_backend"] == (
        "jax_default_float" if sampling_method == "random" else "scipy_qmc"
    )
    assert profile["finite_uniform_lattice"] is True
    assert profile["implementation_identity_status"] == "producer_asserted"
    assert result.diagnostics["empirical_sampling_profile"] == profile
    assert isinstance(result.envelope.distribution_payload, PosteriorSamplesCarrier)
    assert set(result.envelope.distribution_payload.samples) <= {-1.0, 1.0}
