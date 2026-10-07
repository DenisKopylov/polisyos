"""Actual Profile2 composition and configured fresh-CAS law admission controls."""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import pytest

from polisyos.core import artifacts as core_artifacts
from polisyos.foundry.calibration.uncertainty_adapter import (
    summarize_bayesian_calibration_posterior,
)
from polisyos.ir.analytics import (
    PosteriorParameterBinding,
    PosteriorSamplesCarrier,
    PosteriorSummaryContext,
    read_posterior_summary_profile,
)
from polisyos.ir.analytics.posterior_summary import posterior_joint_carrier_digest
from polisyos.ir.analytics.uncertainty import (
    ExactnessKind,
    ParametricFitCarrier,
    UncertaintyCompatibilityError,
    compress_envelope,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
    pull_back_envelope,
    push_forward_envelope,
)


def _source(samples, *, weights=None, mass=0.9, context=None):
    return summarize_bayesian_calibration_posterior(
        {"x": samples},
        weights=weights,
        credible_mass=mass,
        draw_ids=[f"source-row:{i}" for i in range(len(samples))],
        sample_axis="actual-chain-draw",
        context=context,
    ).parameter_envelopes["x"]


def _fresh(tmp_path, envelope):
    ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), envelope)
    fresh = load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert fresh == envelope
    assert not fresh.gate_eligible
    return fresh


@pytest.mark.parametrize("samples", [(1.6e308,) * 4, (0.0, 1.0)])
def test_identity_push_uses_finite_ratio_mean_and_inverse_cdf_atom(tmp_path, samples):
    weights = (1.0, 2.0) if len(samples) == 2 else (0.5,) * 4
    mass = 0.32 if len(samples) == 2 else 0.9
    source = _source(samples, weights=weights, mass=mass)
    result = _fresh(tmp_path, push_forward_envelope(lambda x: x, source))
    profile = read_posterior_summary_profile(result)
    expected_mean = float(
        sum((Fraction(x) * Fraction(w) for x, w in zip(samples, weights, strict=True)), Fraction())
        / sum(map(Fraction, weights), Fraction())
    )
    expected_atom = 1.0 if len(samples) == 2 else 1.6e308
    assert profile.posterior_mean == expected_mean
    assert result.point_estimate == expected_atom
    assert result.confidence_interval == (expected_atom, expected_atom)
    assert profile.draw_ids == tuple(f"source-row:{i}" for i in range(len(samples)))
    assert profile.sample_axis == "actual-chain-draw"


def test_push_reissues_content_and_clears_arbitrary_map_binding(tmp_path):
    binding = PosteriorParameterBinding(estimand_id="source:x", unit="score", scale="linear")
    context = PosteriorSummaryContext(
        parameters={"x": binding}, purpose="predictive", time_roles={"fit_time": "2026-10-01"}
    )
    source = _source([0.0, 1.0, 4.0], weights=[1.0, 1.0, 2.0], mass=0.5, context=context)
    source = source.model_copy(update={"metadata": {**source.metadata, "fit_authority": True}})
    old = read_posterior_summary_profile(source)
    result = _fresh(tmp_path, push_forward_envelope(lambda x: x * 2.0, source))
    new = read_posterior_summary_profile(result)
    assert new.posterior_mean == 4.5
    assert result.point_estimate == 2.0
    assert result.confidence_interval == (0.0, 8.0)
    assert new.carrier_content_hash != old.carrier_content_hash
    assert new.joint_law_sha256 != old.joint_law_sha256
    assert new.draw_ids == old.draw_ids
    assert new.sample_axis == old.sample_axis
    assert new.binding is None
    assert new.context.parameters == {}
    assert new.context.time_roles == context.time_roles
    assert new.context.purpose == context.purpose
    assert result.metadata["inherited_parent_lineage_authoritative"] is False
    assert result.metadata["parent_posterior_profile_hash"].startswith("sha256:")
    assert "fit_authority" not in result.metadata
    forged = result.model_copy(update={"metadata": source.metadata})
    with pytest.raises(ValueError, match="binding"):
        read_posterior_summary_profile(_fresh(tmp_path / "forged", forged))


def test_asymmetric_push_keeps_mean_outside_equal_tail_interval(tmp_path):
    source = _source([0.0] * 99 + [100.0])
    result = _fresh(tmp_path, push_forward_envelope(lambda x: x * 2.0, source))
    assert read_posterior_summary_profile(result).posterior_mean == 2.0
    assert result.point_estimate == 0.0
    assert result.confidence_interval == (0.0, 0.0)


def test_scalar_joint_source_refuses_before_any_map_callback():
    source = summarize_bayesian_calibration_posterior(
        {"a": [0.0, 1.0], "b": [0.0, 1.0]}, draw_ids=["paired:0", "paired:1"]
    ).parameter_envelopes["a"]
    calls = []
    with pytest.raises(UncertaintyCompatibilityError, match="single-coordinate"):
        push_forward_envelope(lambda x: calls.append(x) or x, source)
    assert calls == []


def test_corrupt_declared_carrier_refuses_before_any_map_callback():
    source = _source([0.0, 1.0])
    forged = source.model_copy(
        update={"distribution_payload": PosteriorSamplesCarrier(samples=(1.0, 2.0))}
    )
    calls = []
    with pytest.raises(ValueError, match="binding"):
        push_forward_envelope(lambda x: calls.append(x) or x, forged)
    assert calls == []


@pytest.mark.parametrize(
    "declaration", ["missing", "unknown", "required_only", "id_only", "version_only"]
)
@pytest.mark.parametrize("operation", ["push", "compress", "pull"])
def test_incomplete_profile_declaration_refuses_at_shared_inlet(declaration, operation):
    source = _source([0.0, 1.0])
    metadata = source.metadata.copy()
    if declaration in {"missing", "unknown"}:
        metadata.pop("posterior_summary_profile_id")
        metadata.pop("posterior_summary_profile_version")
        if declaration == "missing":
            metadata.pop("posterior_summary_profile")
        else:
            metadata["posterior_summary_profile"] = {"profile_id": "unsupported"}
    else:
        keys = {
            "required_only": "posterior_summary_profile_required",
            "id_only": "posterior_summary_profile_id",
            "version_only": "posterior_summary_profile_version",
        }
        metadata = {keys[declaration]: metadata[keys[declaration]]}
    forged = source.model_copy(update={"metadata": metadata})
    calls = []
    func = lambda x: calls.append(x) or x
    with pytest.raises(ValueError):
        if operation == "push":
            push_forward_envelope(func, forged)
        elif operation == "compress":
            compress_envelope(forged, target="interval")
        else:
            pull_back_envelope(func, forged, upstream_particles=(0.0, 1.0))
    assert calls == []


def test_unprofiled_invalid_map_keeps_legacy_callback_coercion_order():
    source = _source([0.0, 1.0]).model_copy(update={"metadata": {}})
    calls = []

    def bad_first(x):
        calls.append(x)
        return "invalid" if x == 0.0 else x

    with pytest.raises(ValueError):
        push_forward_envelope(bad_first, source)
    assert calls == [0.0]


@pytest.mark.parametrize("invalid", [True, np.bool_(True), "1", 1j, np.nan, np.inf, -np.inf])
def test_invalid_transformed_draw_refuses_whole_profile_publication(invalid):
    source = _source([0.0, 1.0])
    with pytest.raises(UncertaintyCompatibilityError, match="finite real non-bool"):
        push_forward_envelope(lambda x: invalid if x == 0 else x, source)


@pytest.mark.parametrize("target", ["interval", "moments"])
def test_law_losing_compression_clears_complete_profile_declaration(tmp_path, target):
    source = _source([0.0] * 99 + [100.0])
    result = _fresh(tmp_path, compress_envelope(source, target=target))
    assert read_posterior_summary_profile(result) is None
    assert all(
        key not in result.metadata
        for key in (
            "posterior_summary_profile",
            "posterior_summary_profile_required",
            "posterior_summary_profile_id",
            "posterior_summary_profile_version",
            "point_functional",
            "interval_functional",
            "joint_parameter_order",
            "joint_draw_ids",
            "joint_law_sha256",
            "joint_sample_id",
        )
    )
    assert result.metadata["posterior_composition_limitation"]
    if target == "moments":
        assert result.point_estimate == 1.0
        assert result.distribution_payload.parameters == {"mean": 1.0, "std": math.sqrt(99.0)}
        assert result.confidence_interval != source.confidence_interval
        assert result.ci_lower < 1.0 < result.ci_upper
        assert result.composition_provenance.exactness is ExactnessKind.APPROXIMATION
    forged = result.model_copy(update={"metadata": source.metadata})
    with pytest.raises(ValueError, match="exact carrier"):
        read_posterior_summary_profile(_fresh(tmp_path / "stale", forged))


def test_particles_compression_preserves_exact_axis_and_profile(tmp_path):
    source = _source([0.0, 1.0, 4.0], weights=[1.0, 0.0, 2.0])
    result = _fresh(tmp_path, compress_envelope(source, target="particles"))
    assert result.distribution_payload == source.distribution_payload
    assert read_posterior_summary_profile(result) == read_posterior_summary_profile(source)


def test_complete_joint_particles_compression_preserves_fresh_group(tmp_path):
    from polisyos.ir.analytics.posterior_summary import admit_posterior_summary_profiles

    source = summarize_bayesian_calibration_posterior(
        {"a": [0.0, 1.0], "b": [0.0, -1.0]},
        draw_ids=["paired:0", "paired:1"],
        sample_axis="chain:draw",
    ).parameter_envelopes
    fresh = {
        name: _fresh(tmp_path / name, compress_envelope(env, target="particles"))
        for name, env in source.items()
    }
    admit_posterior_summary_profiles(fresh)
    assert all(
        fresh[name].distribution_payload == env.distribution_payload for name, env in source.items()
    )


def test_zero_spread_moment_projection_is_finite_non_gating(tmp_path):
    result = _fresh(tmp_path, compress_envelope(_source([1.6e308] * 4), target="moments"))
    assert result.point_estimate == 1.6e308
    assert result.confidence_interval == (1.6e308, 1.6e308)
    assert result.distribution_payload.parameters["std"] == 0.0
    assert read_posterior_summary_profile(result) is None


def test_pullback_retained_ratio_mean_is_finite_constraint_only(tmp_path):
    source = _source([1.6e308] * 4)
    supplied = PosteriorSamplesCarrier(
        samples=(1.6e308,) * 4, weights=(0.5,) * 4, sample_axis="upstream-row"
    )
    result = _fresh(tmp_path, pull_back_envelope(lambda x: x, source, upstream_particles=supplied))
    assert result.point_estimate == 1.6e308
    assert result.distribution_payload.sample_axis == "upstream-row"
    assert result.composition_provenance.exactness is ExactnessKind.CONSTRAINT_ONLY
    assert read_posterior_summary_profile(result) is None
    assert result.metadata["posterior_composition_limitation"].startswith("retained upstream")


def test_pullback_selected_zero_mass_refuses_instead_of_inventing_uniform_law():
    source = _source([0.0, 0.0])
    supplied = PosteriorSamplesCarrier(samples=(0.0, 1.0), weights=(0.0, 1.0))
    with pytest.raises(ValueError, match="positive finite"):
        pull_back_envelope(lambda x: x, source, upstream_particles=supplied)


@pytest.mark.parametrize(
    "payload", [None, ParametricFitCarrier(family="normal", parameters={"mean": 0.0, "std": 1.0})]
)
def test_joint_digest_admits_real_carrier_before_payload_access(payload):
    source = _source([0.0, 1.0]).model_copy(update={"distribution_payload": payload})
    with pytest.raises(ValueError, match="exact posterior carriers"):
        posterior_joint_carrier_digest(["x"], {"x": source}, ["source-row:0", "source-row:1"])


def test_joint_digest_missing_coordinate_is_typed_refusal():
    with pytest.raises(ValueError, match="every declared coordinate"):
        posterior_joint_carrier_digest(["x"], {}, ["row:0"])


def test_profile1_composition_keeps_legacy_functionals_and_metadata():
    source = _source([0.0, 1.0])
    raw = source.metadata["posterior_summary_profile"].copy()
    raw.update(
        profile_id="urn:policyos:ir:bayesian-posterior-summary-profile:1", profile_version="1.0"
    )
    del raw["probability_convention"]
    del raw["sampling_approximation"]
    metadata = {
        **source.metadata,
        "posterior_summary_profile": raw,
        "posterior_summary_profile_id": raw["profile_id"],
        "posterior_summary_profile_version": "1.0",
    }
    legacy = source.model_copy(update={"metadata": metadata})
    assert read_posterior_summary_profile(legacy).profile_version == "1.0"
    result = push_forward_envelope(lambda x: x, legacy)
    assert result.point_estimate == 0.5
    assert result.confidence_interval == (0.0, pytest.approx(0.9))
    assert result.metadata["posterior_summary_profile"] == raw


def test_nonfinite_moment_projection_refuses_without_clipping():
    source = push_forward_envelope(lambda x: x * 1.6e308, _source([-1.0, 1.0]))
    with pytest.raises(ValueError, match="finite"):
        compress_envelope(source, target="moments")


def test_unprofiled_particle_push_retains_legacy_mean_and_interpolation():
    source = _source([0.0, 1.0, 4.0]).model_copy(update={"metadata": {}, "gate_eligible": True})
    result = push_forward_envelope(lambda x: x, source)
    assert result.point_estimate == pytest.approx(5.0 / 3.0)
    assert result.confidence_interval == (0.0, pytest.approx(3.55))
    assert result.gate_eligible
    assert read_posterior_summary_profile(result) is None
