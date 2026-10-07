"""Public raw Profile2 admission and non-mixture join boundaries on real CAS."""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction

import pytest

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.foundry.uncertainty import summarize_bayesian_calibration_posterior
from polisyos.ir.analytics import load_posterior_summary_envelope, read_posterior_summary_profile
from polisyos.ir.analytics.uncertainty import (
    UncertaintyCompatibilityError,
    UncertaintyEnvelope,
    combine_envelopes,
    compress_envelope,
    join_envelopes,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
    pull_back_envelope,
    push_forward_envelope,
)
from polisyos.ir.registry.refs import UncertaintyEnvelopeRef


def _source(samples=(0.0, 1.0), *, weights=None):
    return summarize_bayesian_calibration_posterior(
        {"x": samples},
        weights=weights,
        draw_ids=[f"actual-row:{i}" for i in range(len(samples))],
        sample_axis="actual-chain:draw",
    ).parameter_envelopes["x"]


def _raw_ref(tmp_path, raw):
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
    assert store.verify(record).ok
    ref = UncertaintyEnvelopeRef.model_validate(
        record.model_dump(include={"artifact_id", "kind", "media_type"})
    )
    return ref


def _load_raw(tmp_path, raw, inlet):
    if inlet == "model":
        return UncertaintyEnvelope.model_validate(raw)
    ref = _raw_ref(tmp_path, raw)
    return load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)


def _compose(envelope, operation, calls):
    def mapper(value):
        calls.append(value)
        return value + 1.0

    if operation == "push":
        return push_forward_envelope(mapper, envelope)
    if operation == "compress":
        return compress_envelope(envelope, target="particles")
    return pull_back_envelope(mapper, envelope, upstream_particles=(0.0, 1.0))


def _load_compose_publish(tmp_path, raw, inlet, operation, calls, outputs):
    envelope = _load_raw(tmp_path / "input", raw, inlet)
    derived = _compose(envelope, operation, calls)
    outputs.append(
        persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path / "output"), derived)
    )


@pytest.mark.parametrize("raw_value", [True, "1.0"])
@pytest.mark.parametrize("inlet", ["legacy_cas", "model"])
@pytest.mark.parametrize("operation", ["push", "compress", "pull"])
def test_raw_profile2_type_refuses_before_public_callback_or_publication(
    tmp_path, raw_value, inlet, operation
):
    raw = _source().model_dump(mode="json")
    raw["distribution_payload"]["samples"][1] = raw_value
    calls = []
    outputs = []
    with pytest.raises(ValueError, match="finite real non-bool"):
        _load_compose_publish(tmp_path, raw, inlet, operation, calls, outputs)
    assert calls == []
    assert outputs == []
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("inlet", ["legacy_cas", "model"])
@pytest.mark.parametrize(
    "mutation",
    ["missing", "non_mapping", "unsupported", "bad_version", "context", "carrier", "joint"],
)
@pytest.mark.parametrize("operation", ["push", "compress", "pull"])
def test_declared_profile2_malformed_context_or_digest_cannot_downgrade(
    tmp_path, inlet, mutation, operation
):
    raw = _source().model_dump(mode="json")
    profile = raw["metadata"]["posterior_summary_profile"]
    if mutation == "missing":
        del raw["metadata"]["posterior_summary_profile"]
    elif mutation == "non_mapping":
        raw["metadata"]["posterior_summary_profile"] = True
    elif mutation == "unsupported":
        profile["profile_id"] = "urn:policyos:ir:bayesian-posterior-summary-profile:3"
    elif mutation == "bad_version":
        profile["profile_version"] = "2.1"
    elif mutation == "context":
        profile["context"]["purpose"] = "unbound-purpose"
    elif mutation == "carrier":
        profile["carrier_content_hash"] = "sha256:" + "0" * 64
    else:
        profile["joint_law_sha256"] = "0" * 64
        raw["metadata"]["joint_law_sha256"] = raw["metadata"]["joint_sample_id"] = "0" * 64
    calls = []
    outputs = []
    with pytest.raises(ValueError):
        _load_compose_publish(tmp_path, raw, inlet, operation, calls, outputs)
    assert calls == []
    assert outputs == []
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize(
    "declaration",
    [
        "posterior_summary_profile_required",
        "posterior_summary_profile_id",
        "posterior_summary_profile_version",
    ],
)
@pytest.mark.parametrize("inlet", ["legacy_cas", "model"])
def test_partial_profile_declaration_refuses_at_raw_inlet(tmp_path, declaration, inlet):
    raw = _source().model_dump(mode="json")
    raw["metadata"] = {declaration: raw["metadata"][declaration]}
    with pytest.raises(ValueError, match="profile is missing"):
        _load_raw(tmp_path, raw, inlet)


def test_strict_profile2_to_push_to_fresh_cas_preserves_actual_law(tmp_path):
    source = _source((1.0, 3.0))
    source_ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), source)
    admitted = load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), source_ref)
    calls = []
    mapped = push_forward_envelope(lambda value: calls.append(value) or value * 2.0, admitted)
    ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), mapped)
    fresh = load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert calls == [1.0, 3.0]
    assert fresh.distribution_payload.samples == (2.0, 6.0)
    assert read_posterior_summary_profile(fresh).posterior_mean == float(
        (Fraction(2) + Fraction(6)) / 2
    )
    assert not fresh.gate_eligible


def _profile1_raw():
    raw = _source().model_dump(mode="json")
    profile = raw["metadata"]["posterior_summary_profile"]
    profile.update(
        profile_id="urn:policyos:ir:bayesian-posterior-summary-profile:1", profile_version="1.0"
    )
    del profile["probability_convention"]
    del profile["sampling_approximation"]
    raw["metadata"]["posterior_summary_profile_id"] = profile["profile_id"]
    raw["metadata"]["posterior_summary_profile_version"] = "1.0"
    return raw


def test_profile1_literal_cas_replay_keeps_original_bytes(tmp_path):
    raw = _profile1_raw()
    ref = _raw_ref(tmp_path, raw)
    before = core_artifacts.FileSystemCAS(tmp_path).get_bytes(ref.artifact_id)
    fresh = load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert fresh.model_dump(mode="json") == raw
    assert read_posterior_summary_profile(fresh).profile_version == "1.0"
    reopened = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), fresh)
    assert core_artifacts.FileSystemCAS(tmp_path).get_bytes(reopened.artifact_id) == before


@pytest.mark.parametrize("raw_value", [True, "1.0"])
@pytest.mark.parametrize("profile", ["profile1", "generic"])
@pytest.mark.parametrize("inlet", ["legacy_cas", "model"])
def test_profile1_and_unprofiled_v11_keep_legacy_raw_coercion(tmp_path, raw_value, profile, inlet):
    raw = _profile1_raw()
    if profile == "generic":
        raw["metadata"] = {}
    raw["distribution_payload"]["samples"][1] = raw_value
    fresh = _load_raw(tmp_path, raw, inlet)
    assert fresh.distribution_payload.samples == (0.0, 1.0)
    if profile == "profile1":
        assert read_posterior_summary_profile(fresh).profile_version == "1.0"
    else:
        assert read_posterior_summary_profile(fresh) is None


def _join_publish(tmp_path, pair):
    result = join_envelopes(pair)
    return persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), result)


@pytest.mark.parametrize("order", ["profile_first", "profile_last"])
@pytest.mark.parametrize("sibling", ["profile2", "generic"])
def test_profile2_multi_join_refuses_before_generic_lowering(tmp_path, order, sibling):
    left = _source((2.0,))
    right = _source((10.0, 14.0))
    assert sum(left.distribution_payload.weights) == 0.5
    assert sum(right.distribution_payload.weights) == 1.0
    if sibling == "generic":
        right = right.model_copy(update={"metadata": {}})
    pair = (left, right) if order == "profile_first" else (right, left)
    with pytest.raises(UncertaintyCompatibilityError, match=r"Profile2.*mixture"):
        _join_publish(tmp_path, pair)
    assert not tmp_path.exists() or not any(tmp_path.iterdir())


def test_profile2_single_join_preserves_identity_and_content():
    source = _source()
    assert join_envelopes([source]) is source


@pytest.mark.parametrize("profile", ["generic", "profile1"])
def test_non_profile2_joins_keep_generic_concatenation(tmp_path, profile):
    raw = _profile1_raw()
    if profile == "generic":
        raw["metadata"] = {}
    left = UncertaintyEnvelope.model_validate(raw)
    right = UncertaintyEnvelope.model_validate(deepcopy(raw))
    joined = join_envelopes([left, right])
    assert joined.distribution_payload.samples == (0.0, 1.0, 0.0, 1.0)
    ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), joined)
    fresh = load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert fresh == joined
    assert read_posterior_summary_profile(fresh) is None


def test_combine_profile2_remains_non_gating_lossy_summary_on_fresh_read(tmp_path):
    combined = combine_envelopes([_source((2.0,)), _source((10.0, 14.0))])
    ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), combined)
    fresh = load_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert fresh.distribution_payload is None
    assert read_posterior_summary_profile(fresh) is None
    assert not fresh.gate_eligible
