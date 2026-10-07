"""Native finite-law oracles, category removal and pre-callback controls."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.monte_carlo import (
    MonteCarloPropagator,
    _empirical_indices_from_uniform,
)
from polisyos.foundry.uncertainty.sampling_admission import (
    admit_empirical_weights,
    joint_carrier_digest,
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
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)


def paired(weights_a=(1, 1, 2), weights_b=(1, 1, 2)):
    """Three deliberately unequal atoms of an explicitly paired law."""
    names, ids = ["a", "b"], ["r0", "r1", "r2"]
    envs = {
        name: UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(0, 5),
            confidence_level=None,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
            gate_eligible=False,
            numeric_policy=NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT),
            distribution_payload=PosteriorSamplesCarrier(samples=samples, weights=weights),
        )
        for name, point, samples, weights in [
            ("a", 2.25, (0, 1, 4), weights_a),
            ("b", 3, (0, 2, 5), weights_b),
        ]
    }
    digest = joint_carrier_digest(names, envs, ids)
    return {
        name: env.model_copy(
            update={
                "metadata": {
                    "joint_sample_id": "dyadic-fixture",
                    "joint_draw_ids": ids,
                    "joint_parameter_order": names,
                    "joint_law_sha256": digest,
                }
            }
        )
        for name, env in envs.items()
    }


def config(method="sobol", *, scramble=False):
    return PropagationConfig(
        mc_n_samples=256,
        mc_sampling_method=method,
        mc_qmc_scramble=scramble,
        compute_sensitivity=False,
    )


def test_complete_dyadic_net_reads_same_persisted_joint_law(tmp_path):
    envs = paired()
    store = FileSystemCAS(tmp_path)
    refs = {name: persist_uncertainty_envelope(store, env) for name, env in envs.items()}
    readback = {
        name: load_uncertainty_envelope(FileSystemCAS(tmp_path), ref) for name, ref in refs.items()
    }
    calls = []
    result = MonteCarloPropagator(config()).propagate(
        lambda **p: calls.append((float(p["a"]), float(p["b"]))) or {"y": p["a"] + p["b"]},
        {"a": 2.25, "b": 3},
        readback,
        ["y"],
    )[0]
    # One nominal call is separate from the 256 sampled rows.
    assert len(calls) == 257
    assert Counter(calls[1:]) == {(0, 0): 64, (1, 2): 64, (4, 5): 128}
    draws = result.envelope.distribution_payload.samples
    assert np.mean(draws) == 5.25
    assert np.var(draws) == 15.1875
    assert not result.envelope.gate_eligible


@pytest.mark.parametrize("method", ["random", "sobol", "halton"])
@pytest.mark.parametrize("entry", [MonteCarloPropagator, PropagationDispatcher])
@pytest.mark.parametrize("mutation", ["near_weights", "permuted_rows", "stale_digest", "collapse"])
def test_joint_law_corruption_is_refused_before_any_callback(method, entry, mutation):
    envs = paired()
    if mutation == "near_weights":
        envs = paired((0.25, 0.25, 0.5), (0.2500000000005, 0.2499999999995, 0.5))
    elif mutation == "collapse":
        envs = paired((0.5, 1e-20, 0.5), (0.5, 1e-20, 0.5))
    elif mutation == "permuted_rows":
        payload = envs["b"].distribution_payload.model_copy(update={"samples": (5, 2, 0)})
        envs["b"] = envs["b"].model_copy(update={"distribution_payload": payload})
    else:
        envs["b"] = envs["b"].model_copy(
            update={"metadata": {**envs["b"].metadata, "joint_law_sha256": "0" * 64}}
        )
    result = entry(config(method)).propagate(
        lambda **p: pytest.fail("inadmissible law reached evaluator"),
        {"a": 2.25, "b": 3},
        envs,
        ["y"],
    )[0]
    assert result.envelope.distribution_family is DistributionFamily.UNKNOWN
    assert not result.envelope.gate_eligible


@pytest.mark.parametrize("method", ["random", "sobol", "halton"])
@pytest.mark.parametrize("entry", [MonteCarloPropagator, PropagationDispatcher])
def test_covariance_only_uniform_law_refused_before_sampler_or_evaluator(
    method, entry, monkeypatch
):
    envs = {
        name: env.model_copy(
            update={
                "distribution_family": DistributionFamily.UNIFORM,
                "distribution_payload": None,
                "point_estimate": 0.5,
                "confidence_interval": (0, 1),
                "metadata": {
                    "std": float(np.sqrt(1 / 12)),
                    "covariance_params": ["a", "b"],
                    "covariance_row": [1 / 12, 0] if name == "a" else [0, 1 / 12],
                },
            }
        )
        for name, env in paired().items()
    }
    monkeypatch.setattr(
        MonteCarloPropagator,
        "_random_input_samples",
        lambda *a, **kw: pytest.fail("inadmissible law reached random sampler"),
    )
    monkeypatch.setattr(
        MonteCarloPropagator,
        "_create_qmc_sampler_state_with_seed",
        lambda *a, **kw: pytest.fail("inadmissible law reached QMC sampler"),
    )
    result = entry(config(method)).propagate(
        lambda **p: pytest.fail("inadmissible law reached nominal/evaluator"),
        {"a": 0.5, "b": 0.5},
        envs,
        ["y"],
    )[0]
    assert result.envelope.metadata["failure"] == "unsupported_joint_sampling_law"
    assert result.envelope.distribution_family is DistributionFamily.UNKNOWN
    assert not result.envelope.gate_eligible


@pytest.mark.parametrize(
    ("weights", "uniforms", "expected"),
    [
        ([5e-11, 1 - 5e-11], [0, 2.5e-11], [0, 0]),
        ([0.5, 5e-11, 0.5 - 5e-11], [0.5, 0.5 + 2.5e-11], [1, 1]),
        ([1 - 5e-11, 5e-11], [1 - 2.5e-11, np.nextafter(1.0, 0.0)], [1, 1]),
        ([0, 0.5, 0, 0.5, 0], [0, np.nextafter(0.5, 0), 0.5, np.nextafter(1.0, 0)], [1, 1, 3, 3]),
    ],
)
def test_positive_atoms_and_zero_mass_boundaries(weights, uniforms, expected):
    probabilities = admit_empirical_weights(weights, len(weights))
    assert _empirical_indices_from_uniform(np.array(uniforms), probabilities).tolist() == expected


@pytest.mark.parametrize("u", [1.0, -1e-16, np.inf, -np.inf, np.nan])
def test_invalid_uniform_domain_refused_without_clipping(u):
    with pytest.raises(ValueError, match=r"\[0, 1\)"):
        _empirical_indices_from_uniform(np.array([u]), np.array([0.5, 0.5]))


@pytest.mark.parametrize("weights", [[0.5, 1e-20, 0.5], [1, 1e-20], [1e308, 1e-300]])
def test_unrepresentable_positive_categories_are_explicitly_refused(weights):
    with pytest.raises(ValueError, match="collapses|underflows"):
        admit_empirical_weights(weights, len(weights))


def test_proportional_weights_have_exact_canonical_agreement():
    assert np.array_equal(
        admit_empirical_weights([1, 1, 2], 3), admit_empirical_weights([2, 2, 4], 3)
    )


def test_upstream_numeric_policy_loss_is_explicit_after_persisted_readback(tmp_path):
    """Sampling cannot restore source mass already erased by a lossy IR profile."""
    source_weights = (0.5, 1e-20, 0.5)
    exact = paired(source_weights, source_weights)["a"]
    rounded = UncertaintyEnvelope.model_validate(
        {**exact.model_dump(mode="python"), "numeric_policy": NumericPolicySpec()}
    )
    assert rounded.distribution_payload.weights == (0.5, 0, 0.5)
    assert exact.distribution_payload.weights == source_weights
    store = FileSystemCAS(tmp_path)
    for env, expected in [(exact, source_weights), (rounded, (0.5, 0, 0.5))]:
        ref = persist_uncertainty_envelope(store, env)
        assert (
            load_uncertainty_envelope(FileSystemCAS(tmp_path), ref).distribution_payload.weights
            == expected
        )
