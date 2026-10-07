"""Independent exact-ratio and paired-premise regressions for Profile2."""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.foundry.calibration.uncertainty_adapter import (
    summarize_bayesian_calibration_posterior,
)
from polisyos.foundry.uncertainty import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.foundry.uncertainty.sampling_admission import admit_empirical_weights, empirical_cdf
from polisyos.ir.analytics import (
    PosteriorSummaryProfile,
    PosteriorSummaryProfileV2,
    UncertaintyEnvelope,
    admit_posterior_summary_profiles,
    load_posterior_summary_envelope,
    posterior_nominal_mean,
    posterior_summary_functionals_v2,
    read_posterior_summary_profile,
)
from polisyos.ir.analytics.uncertainty import persist_uncertainty_envelope


def _oracle_cuts(weights):
    exact = [Fraction(float(w)) for w in weights]
    total = sum(exact)
    result, cumulative = [], Fraction()
    for weight in exact:
        cumulative += weight / total
        result.append(cumulative)
    return result


@pytest.mark.parametrize(
    "weights",
    [
        [1, 2],
        [1, 0, 3],
        [5e-11, 0.5, 0.5 - 5e-11],
        [0.5, 5e-11, 0.5 - 5e-11],
        [0.5, 0.5 - 5e-11, 5e-11],
        [1e-20, 0.5, 0.5],
        [0.5, 1e-20, 0.5],
    ],
)
def test_every_boundary_neighbor_uses_exact_finite_input_mass(weights):
    canonical = admit_empirical_weights(weights, len(weights))
    assert np.array_equal(admit_empirical_weights(canonical, len(weights)), canonical)
    cuts = empirical_cdf(canonical)
    expected_cuts = _oracle_cuts(weights)
    probes = {0.0, np.nextafter(1.0, 0.0)}
    for rational in expected_cuts:
        rounded = float(rational)
        probes.update([rounded, np.nextafter(rounded, 0.0), np.nextafter(rounded, 1.0)])
    for u in sorted(x for x in probes if 0 <= x < 1):
        expected = next(i for i, cut in enumerate(expected_cuts) if Fraction(float(u)) < cut)
        assert np.searchsorted(cuts, u, side="right") == expected


@pytest.mark.parametrize("last", [100.0, 1e15])
def test_hundred_atom_mean_and_finite_bucket_law_share_exact_ratios(tmp_path, last):
    summary = summarize_bayesian_calibration_posterior({"x": [0.0] * 99 + [last]})
    env = summary.parameter_envelopes["x"]
    assert summary.posterior_means["x"] == last / 100
    assert env.point_estimate == 0 and env.confidence_interval == (0, 0)
    profile = read_posterior_summary_profile(env)
    assert isinstance(profile, PosteriorSummaryProfileV2)
    assert sum(profile.probabilities) == 50  # Explicit ratio weights, not floating p.
    ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), env)
    fresh = load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
    assert posterior_nominal_mean(fresh) == last / 100
    assert empirical_cdf(profile.probabilities)[98] >= float(Fraction(99, 100))
    assert not fresh.gate_eligible


def test_quantile_one_third_neighbors_are_exact_rational_not_nearest_cut():
    weights = tuple(admit_empirical_weights([1, 2], 2))
    lower = float(Fraction(1, 3))
    upper = np.nextafter(lower, 1.0)
    # Lower tail q=(1-mass)/2 is exactly the supplied finite value.
    for q, expected in [(lower, 0.0), (upper, 1.0)]:
        mass = 1 - 2 * q
        actual_q = (1 - mass) / 2
        expected = 0.0 if Fraction(float(actual_q)) <= Fraction(1, 3) else 1.0
        assert posterior_summary_functionals_v2((0.0, 1.0), weights, mass)[2][0] == expected


@pytest.mark.parametrize("weights", [[1, 1e-20], [np.finfo(float).max, np.nextafter(0, 1)]])
def test_unreachable_or_scale_collapsed_positive_atom_refuses(weights):
    with pytest.raises(ValueError):
        admit_empirical_weights(weights, 2)


def test_joint_arrays_without_supplied_alignment_refuse_and_reader_refuses_forgery(tmp_path):
    with pytest.raises(ValueError, match="explicit producer-supplied"):
        summarize_bayesian_calibration_posterior({"a": [-1, 1], "b": [-1, 1]})
    healthy = summarize_bayesian_calibration_posterior(
        {"a": [-1, 1], "b": [-1, 1]}, draw_ids=["joint:0", "joint:1"]
    ).parameter_envelopes
    forged = {}
    for name, env in healthy.items():
        raw = deepcopy(env.model_dump(mode="python"))
        raw["metadata"]["posterior_summary_profile"]["row_identity_basis"] = "producer_input_order"
        malformed = UncertaintyEnvelope.model_validate(raw)
        store = core_artifacts.FileSystemCAS(tmp_path)
        ref = persist_uncertainty_envelope(store, malformed)
        assert store.verify(ref.artifact_id).ok
        with pytest.raises(ValueError):
            load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
        forged[name] = malformed
    calls = []

    def callback(**row):
        calls.append(row)
        return {"y": row["a"] - row["b"]}

    result = MonteCarloPropagator(PropagationConfig(mc_n_samples=256)).propagate(
        callback, {"a": 0, "b": 0}, forged, ["y"]
    )
    assert calls == []
    assert not result[0].envelope.gate_eligible
    with pytest.raises(ValueError):
        admit_posterior_summary_profiles(forged)


@pytest.mark.parametrize("backend", ["random", "sobol", "halton"])
def test_all_backends_consume_ratio_weights_through_shared_transform(tmp_path, backend):
    summary = summarize_bayesian_calibration_posterior(
        {"a": [0, 1, 4], "b": [0, 2, 5]}, weights=[1, 1, 2], draw_ids=["r0", "r1", "r2"]
    )
    store = core_artifacts.FileSystemCAS(tmp_path)
    refs = {
        n: persist_uncertainty_envelope(store, env)
        for n, env in summary.parameter_envelopes.items()
    }
    fresh = {
        n: load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
        for n, ref in refs.items()
    }
    calls = []

    def callback(**row):
        calls.append((row["a"], row["b"]))
        return {"y": row["a"] + row["b"]}

    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=256, mc_sampling_method=backend, mc_qmc_scramble=False)
    ).propagate(callback, {"a": 2.25, "b": 3.0}, fresh, ["y"])
    assert len(calls) == 257
    assert set(calls[1:]) <= {(0, 0), (1, 2), (4, 5)}
    if backend == "sobol":
        assert Counter(calls[1:]) == {(0, 0): 64, (1, 2): 64, (4, 5): 128}
        values = [a + b for a, b in calls[1:]]
        assert sum(values) / 256 == 21 / 4
        assert sum((y - 21 / 4) ** 2 for y in values) / 256 == 243 / 16
    assert not result[0].envelope.gate_eligible


def test_literal_profile_one_decode_display_replay_is_unchanged(tmp_path):
    directory = Path(__file__).parents[2] / "fixtures/ir/posterior-summary-profile-v1"
    index = json.loads((directory / "index.json").read_text())
    for row in index["records"]:
        raw = (directory / row["path"]).read_bytes()
        env = UncertaintyEnvelope.model_validate(core_canon.from_canonical_bytes(raw))
        profile = read_posterior_summary_profile(env)
        assert type(profile) is PosteriorSummaryProfile
        ref = persist_uncertainty_envelope(core_artifacts.FileSystemCAS(tmp_path), env)
        fresh = load_posterior_summary_envelope(core_artifacts.FileSystemCAS(tmp_path), ref)
        assert fresh == env
        assert core_artifacts.FileSystemCAS(tmp_path).get_bytes(ref.artifact_id) == raw
        assert posterior_nominal_mean(fresh) == profile.posterior_mean


def test_profile_placement_is_distinct_and_old_public_type_is_preserved():
    import polisyos.ir as ir

    assert ir.PosteriorSummaryProfile is PosteriorSummaryProfile
    assert ir.PosteriorSummaryProfileV2 is PosteriorSummaryProfileV2
    assert PosteriorSummaryProfile.model_json_schema()["$id"].endswith("profile:1")
    assert PosteriorSummaryProfileV2.model_json_schema()["$id"].endswith("profile:2")
    assert ir.get_ir_type("PosteriorSummaryProfileV2").abi_key == "posterior_summary_profile_v2"


def test_nearly_equal_paired_weights_do_not_collapse_into_same_admitted_law():
    a = admit_empirical_weights([0.5, 0.5], 2)
    b = admit_empirical_weights([0.5000000000005, 0.4999999999995], 2)
    assert not np.array_equal(a, b)
    assert _oracle_cuts(a) != _oracle_cuts(b)


@pytest.mark.parametrize("backend", ["random", "sobol", "halton"])
def test_unreachable_last_atom_refuses_before_all_backend_callbacks(backend):
    # Unprofiled v1.1 carrier still traverses the same law admission mechanism.
    from polisyos.ir.analytics import DistributionFamily, PosteriorSamplesCarrier, UncertaintySource

    env = UncertaintyEnvelope(
        point_estimate=0,
        confidence_interval=(0, 1),
        distribution_family=DistributionFamily.BAYESIAN,
        source=UncertaintySource.CALIBRATION,
        distribution_payload=PosteriorSamplesCarrier(samples=(0, 1), weights=(1.0, 1e-20)),
        numeric_policy={"mode": "decimal_exact"},
    )
    calls = []

    def callback(**row):
        calls.append(row)
        return {"y": row["x"]}

    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=256, mc_sampling_method=backend)
    ).propagate(callback, {"x": 0}, {"x": env}, ["y"])
    assert calls == []
    assert not result[0].envelope.gate_eligible


def test_removing_common_alignment_admission_keeps_markers_but_breaks_control(monkeypatch):
    from polisyos.foundry.uncertainty import sampling_admission

    healthy = summarize_bayesian_calibration_posterior(
        {"a": [-1, 1], "b": [-1, 1]}, draw_ids=["shared:0", "shared:1"]
    ).parameter_envelopes
    forged = {}
    for name, env in healthy.items():
        raw = env.model_dump(mode="python")
        raw["metadata"]["posterior_summary_profile"]["row_identity_basis"] = "producer_input_order"
        forged[name] = UncertaintyEnvelope.model_validate(raw)
    calls = []

    def callback(**row):
        calls.append(row)
        return {"y": row["a"] - row["b"]}

    def actual_control():
        MonteCarloPropagator(PropagationConfig(mc_n_samples=256)).propagate(
            callback, {"a": 0, "b": 0}, forged, ["y"]
        )
        assert calls == []

    actual_control()
    monkeypatch.setattr(sampling_admission, "admit_posterior_summary_profiles", lambda _: None)
    with pytest.raises(AssertionError):
        actual_control()
    assert len(calls) == 257


def test_population_spread_uses_exact_ratios_without_variance_float_overflow():
    from polisyos.ir.analytics import posterior_population_std_v2

    weights = tuple(admit_empirical_weights([1, 1], 2))
    assert posterior_population_std_v2((0.0, 1e200), weights) == 5e199
    assert posterior_population_std_v2((0.0, 2.0), weights) == 1.0


def test_nearest_float_proxy_fails_boundary_control_with_same_declared_law(monkeypatch):
    from polisyos.foundry.uncertainty import sampling_admission

    weights = admit_empirical_weights([1, 2], 2)
    u = float(Fraction(1, 3))

    def exact_boundary_control():
        assert np.searchsorted(sampling_admission.empirical_cdf(weights), u, side="right") == 0

    exact_boundary_control()
    # Keep finite inputs, weights and public helper name, remove exact cut rounding.
    monkeypatch.setattr(
        sampling_admission, "posterior_sampling_cdf", lambda w: np.cumsum(w / sum(w))
    )
    with pytest.raises(AssertionError):
        exact_boundary_control()
