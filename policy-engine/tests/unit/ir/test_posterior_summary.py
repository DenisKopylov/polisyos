"""Native profile and CAS controls for the original B201/B202 properties."""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.foundry.uncertainty import summarize_bayesian_calibration_posterior
from polisyos.ir.analytics import (
    DistributionFamily,
    PosteriorParameterBinding,
    PosteriorSamplesCarrier,
    PosteriorSummaryContext,
    UncertaintyEnvelope,
    UncertaintySource,
    load_posterior_summary_envelope,
    posterior_nominal_mean,
    posterior_summary_functionals,
    read_posterior_summary_profile,
    validate_raw_posterior_summary_envelope,
)
from polisyos.ir.analytics.uncertainty import (
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)


def test_asymmetric_native_adapter_fresh_read_keeps_independent_functionals(tmp_path):
    binding = PosteriorParameterBinding(estimand_id="finite:x", unit="score", scale="linear")
    context = PosteriorSummaryContext(parameters={"x": binding})
    summary = summarize_bayesian_calibration_posterior({"x": [0.0] * 99 + [100.0]}, context=context)
    ref = persist_uncertainty_envelope(
        core_artifacts.FileSystemCAS(tmp_path), summary.parameter_envelopes["x"]
    )
    readback = load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert summary.posterior_means == {"x": 1.0}
    assert readback.point_estimate == 0.0
    assert readback.confidence_interval == (0.0, 0.0)
    assert posterior_nominal_mean(readback, parameter_name="x", binding=binding) == 1.0
    assert not readback.gate_eligible
    profile = read_posterior_summary_profile(readback)
    assert profile.point_functional == "median"
    assert profile.interval_functional == "equal_tail_inverse_cdf"
    assert profile.context.lineage_refs == {}
    assert profile.context.purpose is None
    assert readback.distribution_payload.samples == (0.0,) * 99 + (100.0,)
    with pytest.raises(ValueError, match="binding"):
        posterior_nominal_mean(
            readback,
            binding=PosteriorParameterBinding(estimand_id="finite:x", unit="money", scale="linear"),
        )


def test_weighted_atoms_inverse_cdf_and_zero_mass_are_explicit():
    summary = summarize_bayesian_calibration_posterior(
        {"x": [0, 1, 4, 100]}, weights=[1, 1, 2, 0], credible_mass=0.5
    )
    env = summary.parameter_envelopes["x"]
    assert summary.posterior_means["x"] == 2.25
    assert env.point_estimate == 1
    assert env.confidence_interval == (0, 4)
    assert posterior_nominal_mean(env) == 2.25
    zero = summarize_bayesian_calibration_posterior({"x": [0, 999, 2]}, weights=[1, 0, 3])
    assert zero.posterior_means["x"] == 1.5
    assert zero.parameter_envelopes["x"].point_estimate == 2
    assert zero.parameter_envelopes["x"].confidence_interval == (0, 2)


@pytest.mark.parametrize(
    ("draws", "kwargs"),
    [
        ({"x": [True, False]}, {}),
        ({"x": [1, True]}, {}),
        ({"x": [np.bool_(True)]}, {}),
        ({"x": [np.nan]}, {}),
        ({"x": [np.inf]}, {}),
        ({"x": ["1"]}, {}),
        ({"x": []}, {}),
        ({"x": [[1, 2]]}, {}),
        ({"x": [1, 2], "y": [3]}, {}),
        ({"x": [0, 1]}, {"weights": [0, 0]}),
        ({"x": [0, 1]}, {"weights": [1, -1]}),
        ({"x": [0, 1]}, {"weights": [True, True]}),
        ({"x": [0, 1]}, {"weights": [1, np.inf]}),
        ({"x": [0, 1]}, {"draw_ids": ["same", "same"]}),
    ],
)
def test_invalid_corpus_is_refused_by_real_producer(draws, kwargs):
    with pytest.raises((ValueError, TypeError)):
        summarize_bayesian_calibration_posterior(draws, **kwargs)


@pytest.mark.parametrize("mutation", ["mean", "profile", "carrier", "rows", "required", "context"])
def test_integrity_valid_forged_profile_refuses_fresh_named_computation(tmp_path, mutation):
    from polisyos.ir.registry.refs import UncertaintyEnvelopeRef

    env = summarize_bayesian_calibration_posterior({"x": [0, 0, 100]}).parameter_envelopes["x"]
    payload = deepcopy(env.model_dump(mode="python"))
    if mutation == "mean":
        payload["metadata"]["posterior_summary_profile"]["posterior_mean"] = 123.0
    elif mutation == "profile":
        payload["metadata"]["posterior_summary_profile"]["profile_version"] = "999.0"
    elif mutation == "carrier":
        payload["distribution_payload"] = None
    elif mutation == "rows":
        payload["distribution_payload"]["samples"] = (100, 0, 0)
    elif mutation == "context":
        payload["metadata"]["posterior_summary_profile"]["context"]["purpose"] = "forged"
    else:
        del payload["metadata"]["posterior_summary_profile"]
    # Persist the deliberately invalid raw input without first coercing or
    # constructing its DTO. Admission may reject at the fresh raw inlet.
    store = core_artifacts.FileSystemCAS(tmp_path)
    record = store.put_json(
        payload,
        core_artifacts.PutOptions(
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(name="ir.uncertainty_envelope", version="1.1"),
        ),
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    ref = UncertaintyEnvelopeRef.model_validate(
        record.model_dump(include={"artifact_id", "kind", "media_type"})
    )
    assert store.verify(record).ok
    with pytest.raises(ValueError):
        posterior_nominal_mean(
            load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
        )


def test_v11_unprofiled_inline_carrier_replay_is_unchanged(tmp_path):
    legacy = UncertaintyEnvelope(
        point_estimate=0,
        confidence_interval=(-1, 1),
        distribution_family=DistributionFamily.BAYESIAN,
        source=UncertaintySource.CALIBRATION,
        distribution_payload=PosteriorSamplesCarrier(samples=(-1, 1)),
        metadata={
            "joint_sample_id": "legacy-joint",
            "joint_draw_ids": ["row:0", "row:1"],
            "joint_parameter_order": ["x"],
        },
    )
    store = core_artifacts.FileSystemCAS(tmp_path)
    ref = persist_uncertainty_envelope(store, legacy)
    raw = store.get_bytes(ref.artifact_id)
    fresh = load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert fresh == legacy
    assert posterior_nominal_mean(fresh) == 0
    assert read_posterior_summary_profile(fresh) is None
    assert store.get_bytes(persist_uncertainty_envelope(store, fresh).artifact_id) == raw


@pytest.mark.parametrize("required", [False, "true", None])
def test_named_functional_markers_cannot_fall_back_when_profile_removed(required):
    env = summarize_bayesian_calibration_posterior({"x": [0, 0, 100]}).parameter_envelopes["x"]
    raw = env.model_dump(mode="json")
    del raw["metadata"]["posterior_summary_profile"]
    if required is None:
        del raw["metadata"]["posterior_summary_profile_required"]
    else:
        raw["metadata"]["posterior_summary_profile_required"] = required
    with pytest.raises(ValueError, match="profile is missing"):
        validate_raw_posterior_summary_envelope(raw)
    with pytest.raises(ValueError, match="profile is missing"):
        posterior_nominal_mean(UncertaintyEnvelope.model_validate(raw))


def test_v11_generic_functional_labels_are_legacy_without_new_profile_discriminator(tmp_path):
    legacy = UncertaintyEnvelope(
        point_estimate=0,
        confidence_interval=(0, 0),
        confidence_level=0.9,
        distribution_family=DistributionFamily.BAYESIAN,
        source=UncertaintySource.CALIBRATION,
        distribution_payload=PosteriorSamplesCarrier(samples=(0.0,) * 99 + (100.0,)),
        gate_eligible=False,
        metadata={
            "point_functional": "median",
            "interval_functional": "equal_tail_inverse_cdf",
            "posterior_mean": 1.0,
            "joint_sample_id": "legacy-joint",
        },
    )
    store = core_artifacts.FileSystemCAS(tmp_path)
    ref = persist_uncertainty_envelope(store, legacy)
    fresh = load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert fresh == legacy
    assert posterior_nominal_mean(fresh) == 0
    assert read_posterior_summary_profile(fresh) is None
    assert store.get_bytes(persist_uncertainty_envelope(store, fresh).artifact_id) == (
        store.get_bytes(ref.artifact_id)
    )


@pytest.mark.parametrize("weights", [None, [-0.0, 1.0]])
def test_new_profile_signed_zero_uses_existing_canonical_cas_representation(tmp_path, weights):
    env = summarize_bayesian_calibration_posterior(
        {"x": [-0.0, 1.0]}, weights=weights
    ).parameter_envelopes["x"]
    assert not np.signbit(env.distribution_payload.samples[0])
    assert all(not np.signbit(p) for p in env.distribution_payload.weights)
    ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), env)
    fresh = load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert posterior_nominal_mean(fresh) == (0.5 if weights is None else 1.0)
    assert read_posterior_summary_profile(fresh) is not None


def test_scoped_facade_resolves_actual_profile_and_reader():
    import polisyos.ir as root
    from polisyos.ir.analytics import PosteriorSummaryProfile
    from polisyos.ir.analytics.posterior_summary import PosteriorSummaryProfile as Defined

    assert PosteriorSummaryProfile is Defined
    assert root.PosteriorSummaryProfile is Defined
    assert PosteriorSummaryProfile.model_json_schema()["$id"].endswith("summary-profile:1")
    entry = root.get_ir_type("PosteriorSummaryProfile")
    assert entry.abi_key == "posterior_summary_profile"
    assert entry.abi_schema_file == "posterior_summary_profile.schema.json"


def test_identical_summaries_do_not_merge_different_persisted_atom_laws(tmp_path):
    # Independent counts: both population second moments=.6 and equal-tail[-1,1].
    laws = [
        [-1.0] * 30 + [0.0] * 40 + [1.0] * 30,
        [-4.0] + [-1.0] * 14 + [0.0] * 70 + [1.0] * 14 + [4.0],
    ]
    refs, readbacks = [], []
    for values in laws:
        env = summarize_bayesian_calibration_posterior({"x": values}).parameter_envelopes["x"]
        ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), env)
        refs.append(ref)
        readbacks.append(load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), ref))
    assert refs[0].artifact_id != refs[1].artifact_id
    for env in readbacks:
        assert env.point_estimate == 0
        assert env.confidence_interval == (-1, 1)
        assert posterior_nominal_mean(env) == 0
    assert [
        sum(
            p
            for x, p in zip(
                env.distribution_payload.samples, env.distribution_payload.weights, strict=True
            )
            if x == 0
        )
        / sum(env.distribution_payload.weights)
        for env in readbacks
    ] == pytest.approx([0.4, 0.7])


def test_whole_row_reordering_preserves_functionals_changes_exact_identity(tmp_path):
    before = summarize_bayesian_calibration_posterior(
        {"a": [0, 1, 4], "b": [0, 2, 5]}, weights=[1, 1, 2], draw_ids=["r0", "r1", "r2"]
    )
    after = summarize_bayesian_calibration_posterior(
        {"b": [5, 0, 2], "a": [4, 0, 1]}, weights=[2, 1, 1], draw_ids=["r2", "r0", "r1"]
    )
    assert before.posterior_means == after.posterior_means == {"a": 2.25, "b": 3.0}
    assert before.credible_intervals == after.credible_intervals
    for name in before.parameter_envelopes:
        old = before.parameter_envelopes[name]
        new = after.parameter_envelopes[name]
        old_ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), old)
        new_ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), new)
        assert old_ref.artifact_id != new_ref.artifact_id
        assert old.metadata["joint_law_sha256"] != new.metadata["joint_law_sha256"]
        assert (
            posterior_nominal_mean(
                load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), new_ref)
            )
            == before.posterior_means[name]
        )


def test_tiny_sorted_atom_is_kept_when_finite_uniform_boundary_exists():
    from polisyos.foundry.uncertainty import sampling_admission

    weights = sampling_admission.admit_empirical_weights([1e-20, 0.5, 0.5], 3)
    cumulative = sampling_admission.empirical_cdf(weights)
    assert cumulative.tolist() == [1e-20, np.nextafter(0.5, 1.0), 1]
    summary = summarize_bayesian_calibration_posterior({"x": [0, -1, 1]}, weights=weights)
    assert summary.posterior_means["x"] == 0
    assert summary.parameter_envelopes["x"].point_estimate == 0


@pytest.mark.parametrize("bad", [True, np.bool_(True), "1.0"])
@pytest.mark.parametrize("axis", ["samples", "probabilities"])
def test_public_functionals_refuse_non_real_or_bool_axes(bad, axis):
    samples, probabilities = (0.0, 1.0), (0.5, 0.5)
    if axis == "samples":
        samples = (0.0, bad)
    else:
        probabilities = (0.5, bad)
    with pytest.raises(ValueError, match="real non-bool"):
        posterior_summary_functionals(samples, probabilities, 0.9)
    assert posterior_summary_functionals((0.0, 1.0), (0.5, 0.5), 0.9) == (0.5, 0.0, (0.0, 1.0))


def test_single_profile_consistently_forged_joint_digest_is_recomputed():
    env = summarize_bayesian_calibration_posterior({"x": [0, 1]}).parameter_envelopes["x"]
    raw = env.model_dump(mode="python")
    raw["metadata"]["posterior_summary_profile"]["joint_law_sha256"] = "0" * 64
    raw["metadata"]["joint_law_sha256"] = raw["metadata"]["joint_sample_id"] = "0" * 64
    forged = UncertaintyEnvelope.model_validate(raw)
    with pytest.raises(ValueError, match="joint content digest"):
        posterior_nominal_mean(forged)


def test_large_finite_corpus_preserves_law_without_intermediate_spread_overflow(tmp_path):
    summary = summarize_bayesian_calibration_posterior({"x": [0.0, 1e200]})
    env = summary.parameter_envelopes["x"]
    assert summary.posterior_means["x"] == 5e199
    assert env.point_estimate == 0
    assert env.confidence_interval == (0, 1e200)
    assert summary.uncertainty_decomposition["x"]["diagnostics"]["total_std"] == 5e199
    assert not summary.uncertainty_decomposition["x"]["total"]["gate_eligible"]
    ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), env)
    fresh = load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert fresh.distribution_payload.samples == (0.0, 1e200)
    assert posterior_nominal_mean(fresh) == 5e199
    with pytest.raises(ValueError):
        summarize_bayesian_calibration_posterior({"x": [0.0, float("inf")]})
    # Finite inputs whose requested Gaussian diagnostic bounds are nonfinite
    # retain the existing finite-bound refusal, never a valid covariance flag.
    with pytest.raises(ValueError):
        summarize_bayesian_calibration_posterior({"x": [-1.79e308, 1.79e308]})


@pytest.mark.parametrize("raw_value", [True, "1.0"])
def test_profile_raw_cas_types_refuse_before_legacy_coercion(tmp_path, raw_value):
    from polisyos.ir.registry.refs import UncertaintyEnvelopeRef

    env = summarize_bayesian_calibration_posterior({"x": [0, 1]}).parameter_envelopes["x"]
    raw = env.model_dump(mode="json")
    raw["distribution_payload"]["samples"][1] = raw_value
    store = core_artifacts.FileSystemCAS(tmp_path)
    record = store.put_json(
        raw,
        core_artifacts.PutOptions(
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            schema=core_artifacts.SchemaInfo(name="ir.uncertainty_envelope", version="1.1"),
        ),
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    ref = UncertaintyEnvelopeRef.model_validate(
        record.model_dump(include={"artifact_id", "kind", "media_type"})
    )
    assert store.verify(record).ok
    # The common DTO inlet now guards raw Profile2 before either public loader
    # can erase its raw type; literal Profile1/unprofiled replay is separate.
    with pytest.raises(ValueError, match="real non-bool"):
        load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    with pytest.raises(ValueError, match="real non-bool"):
        load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
