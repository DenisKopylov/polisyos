"""UQP-02 witnesses for covariance axes, joint laws, and empirical carriers."""

from __future__ import annotations

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
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

pytestmark = pytest.mark.unit


def _normal_env(
    point: float,
    std: float,
    *,
    metadata: dict[str, object] | None = None,
) -> UncertaintyEnvelope:
    """Build a normal input with an independently specified standard deviation."""
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - 1.96 * std, point + 1.96 * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata=metadata or {},
    )


def _empirical_env(
    samples: tuple[float, ...],
    *,
    sample_axis: str = "row",
    weights: tuple[float, ...] | None = None,
    joint_id: str | None = "uqp-test-shared-rows",
    metadata: dict[str, object] | None = None,
) -> UncertaintyEnvelope:
    """Build a small empirical carrier whose row axis is part of the contract."""
    envelope_metadata = dict(metadata or {})
    if joint_id is not None:
        envelope_metadata.setdefault("joint_sample_id", joint_id)
    return UncertaintyEnvelope(
        point_estimate=float(np.mean(samples)),
        confidence_interval=(float(min(samples)), float(max(samples))),
        confidence_level=0.95,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        distribution_payload=PosteriorSamplesCarrier(
            samples=samples,
            sample_axis=sample_axis,
            weights=weights,
        ),
        sample_size=len(samples),
        gate_eligible=True,
        metadata=envelope_metadata,
    )


def _parametric_normal_env(
    *,
    envelope_point: float = 0.0,
    envelope_std: float = 1.0,
    fit_mean: float = 42.0,
    fit_std: float = 0.25,
) -> UncertaintyEnvelope:
    """Build a normal envelope whose typed fit intentionally differs from its interval."""
    return UncertaintyEnvelope(
        point_estimate=envelope_point,
        confidence_interval=(
            envelope_point - 1.96 * envelope_std,
            envelope_point + 1.96 * envelope_std,
        ),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"mean": fit_mean, "std": fit_std},
        ),
        gate_eligible=True,
        metadata={},
    )


def test_covariance_reorders_columns_without_reordering_owner_rows() -> None:
    """A [b, a] column declaration must retain a's row and b's row ownership."""
    envelopes = {
        "a": _normal_env(
            0.0,
            1.0,
            metadata={"covariance_row": [0.0, 1.0], "covariance_params": ["b", "a"]},
        ),
        "b": _normal_env(
            0.0,
            3.0,
            metadata={"covariance_row": [9.0, 0.0], "covariance_params": ["b", "a"]},
        ),
    }

    covariance = build_covariance_matrix(
        ["a", "b"],
        envelopes,
        use_full_covariance=True,
        jitter=0.0,
    )

    npt.assert_allclose(np.asarray(covariance), np.diag([1.0, 9.0]), atol=1e-5)


def test_covariance_rejects_mixed_column_declarations() -> None:
    """A partial column-order declaration cannot be applied to every row."""
    envelopes = {
        "a": _normal_env(
            0.0,
            1.0,
            metadata={"covariance_row": [1.0, 0.0], "covariance_params": ["a", "b"]},
        ),
        "b": _normal_env(0.0, 1.0, metadata={"covariance_row": [0.0, 1.0]}),
    }

    with pytest.raises(ValueError, match="declared for every covariance row"):
        build_covariance_matrix(
            ["a", "b"],
            envelopes,
            use_full_covariance=True,
            jitter=0.0,
        )


def test_covariance_rejects_marginally_incompatible_matrix() -> None:
    """Spectral repair must not conceal a matrix with the wrong marginal scale."""
    envelopes = {
        "a": _normal_env(
            0.0,
            1.0,
            metadata={"covariance_row": [4.0, 0.0], "covariance_params": ["a", "b"]},
        ),
        "b": _normal_env(
            0.0,
            1.0,
            metadata={"covariance_row": [0.0, 1.0], "covariance_params": ["a", "b"]},
        ),
    }

    with pytest.raises(ValueError, match="diagonal"):
        build_covariance_matrix(
            ["a", "b"],
            envelopes,
            use_full_covariance=True,
            jitter=0.0,
        )


def test_analytical_uses_joint_covariance_for_shared_difference_and_independent_control() -> None:
    """The analytical variance is w.T @ Sigma @ w, not a sum of marginal variances."""
    shared_metadata = {
        "covariance_row": [1.0, 1.0],
        "covariance_params": ["a", "b"],
    }
    shared = {
        "a": _normal_env(0.0, 1.0, metadata=shared_metadata),
        "b": _normal_env(0.0, 1.0, metadata=shared_metadata),
    }
    config = PropagationConfig(
        preferred_method="analytical",
        delta_covariance_jitter=0.0,
    )

    shared_result = PropagationDispatcher(config).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        shared,
        ["y"],
        weights={"a": 1.0, "b": -1.0},
    )[0]
    independent_result = PropagationDispatcher(config).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        {"a": _normal_env(0.0, 1.0), "b": _normal_env(0.0, 1.0)},
        ["y"],
        weights={"a": 1.0, "b": -1.0},
    )[0]

    assert shared_result.method_used is PropagationMethod.ANALYTICAL
    assert shared_result.diagnostics["output_variance"] == pytest.approx(0.0, abs=1e-8)
    assert independent_result.diagnostics["output_variance"] == pytest.approx(2.0, abs=1e-5)


def test_delta_uses_joint_covariance_for_shared_difference() -> None:
    """Delta propagation must retain the same joint Gaussian law as analytical mode."""
    metadata = {"covariance_row": [1.0, 1.0], "covariance_params": ["a", "b"]}
    result = DeltaMethodPropagator(
        PropagationConfig(delta_use_full_covariance=True, delta_covariance_jitter=0.0)
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        {
            "a": _normal_env(0.0, 1.0, metadata=metadata),
            "b": _normal_env(0.0, 1.0, metadata=metadata),
        },
        ["y"],
    )[0]

    assert result.diagnostics["output_variance"] == pytest.approx(0.0, abs=1e-8)


def test_random_mc_preserves_shared_empirical_rows_and_axis() -> None:
    """Aligned empirical rows must be sampled jointly, preserving a=b exactly."""
    weights = (1.0, 2.0, 2.0, 1.0)
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 0.0, 1.0), weights=weights),
        "b": _empirical_env((-1.0, 0.0, 0.0, 1.0), weights=weights),
    }
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="random",
        )
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert payload.sample_axis == "row"
    assert set(payload.samples) == {0.0}
    assert result.diagnostics["n_failed"] == 0


def test_qmc_preserves_shared_empirical_rows_and_axis() -> None:
    """QMC inverse-CDF transforms must use one uniform row coordinate for a shared carrier."""
    samples = (-1.0, 0.0, 0.0, 1.0)
    envelopes = {
        "a": _empirical_env(samples),
        "b": _empirical_env(samples),
    }
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="sobol",
            mc_qmc_scramble=False,
            mc_qmc_replicates=1,
        )
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert payload.sample_axis == "row"
    assert set(payload.samples) == {0.0}
    assert result.envelope.gate_eligible is False


def test_random_mc_uses_weighted_empirical_atoms_instead_of_ci_normal() -> None:
    """Random sampling must consume source particle masses and preserve atoms."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=256,
            mc_batch_size=256,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="random",
        )
    ).propagate(
        lambda **params: {"y": params["a"]},
        {"a": 0.0},
        {"a": _empirical_env((-1.0, 1.0), weights=(9.0, 1.0))},
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert set(payload.samples) <= {-1.0, 1.0}
    assert payload.samples.count(-1.0) > 0.75 * len(payload.samples)


def test_qmc_uses_weighted_empirical_atoms_instead_of_ci_normal() -> None:
    """QMC must apply the weighted inverse CDF to empirical source atoms."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="sobol",
            mc_qmc_scramble=False,
            mc_qmc_replicates=1,
        )
    ).propagate(
        lambda **params: {"y": params["a"]},
        {"a": 0.0},
        {"a": _empirical_env((-1.0, 1.0), weights=(9.0, 1.0))},
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert set(payload.samples) <= {-1.0, 1.0}
    assert payload.samples.count(-1.0) > 0.75 * len(payload.samples)


def test_incompatible_empirical_axes_are_not_sampled_as_independent() -> None:
    """Mismatched empirical axes must become a typed limitation, not a fake joint law."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 0.0, 1.0), sample_axis="row-a"),
        "b": _empirical_env((-1.0, 0.0, 0.0, 1.0), sample_axis="row-b"),
    }
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
    )[0].envelope

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "incompatible_joint_law"


def test_same_empirical_axis_with_different_weights_is_not_a_joint_law() -> None:
    """Equal labels do not establish a shared law when source masses differ."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 0.0, 1.0), weights=(1.0, 1.0, 1.0, 1.0)),
        "b": _empirical_env((-1.0, 0.0, 0.0, 1.0), weights=(1.0, 2.0, 1.0, 1.0)),
    }
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
    )[0].envelope

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "incompatible_joint_law"


def test_same_empirical_axis_with_different_lengths_is_not_a_joint_law() -> None:
    """Equal labels do not establish row alignment when lengths differ."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 0.0, 1.0)),
        "b": _empirical_env((-1.0, 0.0)),
    }
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
    )[0].envelope

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "incompatible_joint_law"


def test_mixed_empirical_and_parametric_inputs_are_not_assumed_independent() -> None:
    """A carrier plus a non-carrier needs an explicit joint-law producer."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 1.0)),
        "b": _normal_env(0.0, 1.0),
    }
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
    )[0].envelope

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "incompatible_joint_law"


def test_default_empirical_draws_without_shared_identity_are_not_coupled() -> None:
    """Matching free-form axes cannot establish a shared row identity by themselves."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 1.0), joint_id=None),
        "b": _empirical_env((-1.0, 0.0, 1.0), joint_id=None),
    }
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
    )[0].envelope

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "unestablished_joint_law"


def test_unknown_dependency_does_not_fall_back_to_independent_normal() -> None:
    """An explicit unknown dependency must fail closed in every backend."""
    envelopes = {
        "a": _normal_env(0.0, 1.0, metadata={"dependency": "unknown"}),
        "b": _normal_env(0.0, 1.0, metadata={"dependency": "unknown"}),
    }
    calls: list[dict[str, float]] = []

    def simulation(**params: float) -> dict[str, float]:
        calls.append(params)
        return {"y": params["a"] - params["b"]}

    result = PropagationDispatcher(
        PropagationConfig(preferred_method="analytical")
    ).propagate(
        simulation,
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
        weights={"a": 1.0, "b": -1.0},
    )[0].envelope

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "unknown_dependency"
    assert calls == []


def test_random_mc_uses_normal_parametric_fit_payload() -> None:
    """Random sampling must consume a typed normal fit, not reconstruct CI moments."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="random",
        )
    ).propagate(
        lambda **params: {"y": params["a"]},
        {"a": 0.0},
        {"a": _parametric_normal_env()},
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert result.envelope.point_estimate == pytest.approx(42.0, abs=0.2)
    assert all(40.0 < sample < 44.0 for sample in payload.samples)
    assert result.envelope.metadata["parametric_fit_payload_used"] is True


def test_qmc_uses_normal_parametric_fit_payload() -> None:
    """QMC inverse CDF must consume typed fit parameters instead of the envelope CI."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="sobol",
            mc_qmc_scramble=False,
            mc_qmc_replicates=1,
        )
    ).propagate(
        lambda **params: {"y": params["a"]},
        {"a": 0.0},
        {"a": _parametric_normal_env()},
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert result.envelope.point_estimate == pytest.approx(42.0, abs=0.2)
    assert all(40.0 < sample < 44.0 for sample in payload.samples)
    assert result.envelope.metadata["parametric_fit_payload_used"] is True
