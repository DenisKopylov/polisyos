"""Numerical oracles and removal controls at the canonical sampling intake."""

from __future__ import annotations

import math

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.uncertainty.aggregator import aggregate_envelopes
from polisyos.foundry.uncertainty.config import AdaptiveStoppingConfig, PropagationConfig
from polisyos.foundry.uncertainty.delta import DeltaMethodPropagator
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.foundry.uncertainty.sampling_admission import (
    BoundedIIDMeanPlan,
    BoundedIndicatorResponse,
    admit_float32_range,
    frozen_bernstein_budget,
    joint_carrier_digest,
    verify_mean_certificate,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)


def uniform(low=0.0, high=1.0):
    return UncertaintyEnvelope(
        point_estimate=(low + high) / 2,
        confidence_interval=(low, high),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=True,
    )


def gaussian(std, *, row=None, names=None):
    return UncertaintyEnvelope(
        point_estimate=0,
        confidence_interval=(-1.96 * std, 1.96 * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata={
            "std": std,
            **({"covariance_row": row, "covariance_params": names} if row is not None else {}),
        },
    )


@pytest.mark.parametrize("method", ["random", "sobol", "halton"])
@pytest.mark.parametrize("entry", ["mc", "dispatcher", "delta"])
def test_range_escape_is_rejected_before_any_callback(method, entry):
    calls = []
    env = gaussian(1e20, row=[1e40], names=["x"])
    config = PropagationConfig(mc_sampling_method=method, compute_sensitivity=False)
    producer = {
        "mc": MonteCarloPropagator,
        "dispatcher": PropagationDispatcher,
        "delta": DeltaMethodPropagator,
    }[entry](config)
    result = producer.propagate(
        lambda **p: calls.append(p) or {"y": p["x"]}, {"x": 0}, {"x": env}, ["y"]
    )[0]
    assert calls == []
    assert result.envelope.distribution_family is DistributionFamily.UNKNOWN
    assert not result.envelope.gate_eligible


@pytest.mark.parametrize("variance", [1e-50, 1e-40, 1e-38])
@pytest.mark.parametrize("method", ["random", "sobol", "halton"])
@pytest.mark.parametrize("entry", ["mc", "dispatcher", "delta"])
def test_underflow_law_is_rejected_before_any_callback(variance, method, entry):
    calls = []
    env = gaussian(math.sqrt(variance), row=[variance], names=["x"])
    config = PropagationConfig(mc_sampling_method=method, compute_sensitivity=False)
    producer = {
        "mc": MonteCarloPropagator,
        "dispatcher": PropagationDispatcher,
        "delta": DeltaMethodPropagator,
    }[entry](config)
    result = producer.propagate(
        lambda **p: calls.append(p) or {"y": p["x"]}, {"x": 0}, {"x": env}, ["y"]
    )[0]
    assert calls == []
    assert result.envelope.distribution_family is DistributionFamily.UNKNOWN
    assert not result.envelope.gate_eligible


def test_float32_normal_minimum_survives_actual_jax_quadratic_form():
    import jax.numpy as jnp

    value = float(np.finfo(np.float32).tiny)
    admitted = admit_float32_range([[value]])
    covariance = jnp.asarray(admitted, dtype=jnp.float32)
    gradient = jnp.ones(1, dtype=jnp.float32)
    assert float(gradient @ covariance @ gradient) == value
    assert np.array_equal(admit_float32_range([[0]]), [[0]])


@pytest.mark.parametrize("method", ["random", "sobol", "halton"])
def test_scalar_gaussian_null_law_has_no_artificial_std_floor(method):
    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=256, mc_sampling_method=method, compute_sensitivity=False)
    ).propagate(lambda **p: {"y": p["x"]}, {"x": 0}, {"x": gaussian(0)}, ["y"])[0]
    assert set(result.envelope.distribution_payload.samples) == {0}
    assert result.envelope.metadata["mc_std"] == 0


@pytest.mark.parametrize("method", ["random", "sobol", "halton"])
def test_singular_joint_gaussian_preserves_tied_law(method):
    names = ["a", "b"]
    tied = {name: gaussian(0.05, row=[0.0025, 0.0025], names=names) for name in names}
    independent = {
        "a": gaussian(0.05, row=[0.0025, 0], names=names),
        "b": gaussian(0.05, row=[0, 0.0025], names=names),
    }
    producer = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=4096, mc_sampling_method=method, compute_sensitivity=False)
    )
    zero = producer.propagate(lambda **p: {"y": p["a"] - p["b"]}, {"a": 0, "b": 0}, tied, ["y"])[0]
    separated = producer.propagate(
        lambda **p: {"y": p["a"] - p["b"]}, {"a": 0, "b": 0}, independent, ["y"]
    )[0]
    assert np.var(zero.envelope.distribution_payload.samples) < 1e-20
    assert np.var(separated.envelope.distribution_payload.samples) == pytest.approx(0.005, rel=0.08)
    assert not zero.envelope.gate_eligible


def test_missing_joint_law_and_fake_independence_do_not_invoke_evaluator():
    for declaration in ({}, {"dependency": "independent", "independence": True}):
        calls = []
        env = gaussian(0.05).model_copy(update={"metadata": declaration})
        result = MonteCarloPropagator().propagate(
            lambda calls=calls, **p: calls.append(p) or {"y": p["a"] - p["b"]},
            {"a": 0, "b": 0},
            {"a": env, "b": env},
            ["y"],
        )[0]
        assert calls == []
        assert result.envelope.metadata["failure"] == "unknown_dependency"


def test_paired_carrier_bytes_order_and_row_identity_are_content_bound():
    names, ids = ["a", "b"], ["row-0", "row-1"]
    base = uniform(-1, 1).model_copy(
        update={
            "distribution_family": DistributionFamily.BOOTSTRAP,
            "distribution_payload": PosteriorSamplesCarrier(samples=(-1, 1)),
            "metadata": {
                "joint_sample_id": "paired",
                "joint_draw_ids": ids,
                "joint_parameter_order": names,
            },
        }
    )
    envelopes = dict.fromkeys(names, base)
    digest = joint_carrier_digest(names, envelopes, ids)
    envelopes = {
        name: env.model_copy(update={"metadata": {**env.metadata, "joint_law_sha256": digest}})
        for name, env in envelopes.items()
    }
    producer = MonteCarloPropagator(PropagationConfig(compute_sensitivity=False))
    result = producer.propagate(
        lambda **p: {"y": p["a"] - p["b"]}, {"a": 0, "b": 0}, envelopes, ["y"]
    )[0]
    assert set(result.envelope.distribution_payload.samples) == {0}
    envelopes["b"] = envelopes["b"].model_copy(
        update={"distribution_payload": PosteriorSamplesCarrier(samples=(1, -1))}
    )
    rejected = producer.propagate(
        lambda **p: pytest.fail("invalid law evaluated"), {"a": 0, "b": 0}, envelopes, ["y"]
    )[0]
    assert rejected.envelope.metadata["failure"] == "incompatible_content_bound_joint_law"


def test_uniform_failed_support_keeps_all_outcomes_and_conditional_mean(tmp_path):
    def response(**params):
        if params["x"] < 0:
            raise ValueError("undefined support")
        return {"y": params["x"]}

    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=4096, compute_sensitivity=False)
    ).propagate(response, {"x": 0}, {"x": uniform(-1, 1)}, ["y"])[0]
    receipt = result.diagnostics["draw_outcome_provenance"]
    assert len(receipt["draw_records"]) == 4096
    assert {row["draw_index"] for row in receipt["draw_records"]} == set(range(4096))
    failed = sum(bool(row["failed_outputs"]) for row in receipt["draw_records"])
    assert failed == len(receipt["failure_records"])
    assert result.envelope.point_estimate == pytest.approx(0.5, abs=0.02)
    assert result.envelope.metadata["distribution_sample_semantics"] == (
        "successful_draws_only_conditional_on_execution"
    )
    store = FileSystemCAS(tmp_path)
    ref = persist_uncertainty_envelope(store, result.envelope)
    readback = load_uncertainty_envelope(FileSystemCAS(tmp_path), ref)
    assert not readback.gate_eligible
    assert readback.confidence_level is None
    assert readback.metadata["draw_failure_count"] == failed


def test_pilot_budget_native_mean_and_fresh_cas_readback(tmp_path):
    plan = BoundedIIDMeanPlan(metric_id="y")
    variance, budget = frozen_bernstein_budget(np.zeros(256), plan)
    expected_a = math.sqrt(math.log(160) / 512)
    assert variance == pytest.approx(expected_a, abs=1e-15)
    assert budget == math.ceil((2 * expected_a + 0.1 / 3) * math.log(80) / 0.05**2) == 408
    response = BoundedIndicatorResponse("x", "y", 0.001)
    outputs = []
    for batch_size in (10, 200, 4096):
        producer = PropagationDispatcher(
            PropagationConfig(
                mc_batch_size=batch_size, bounded_iid_mean=plan, compute_sensitivity=False
            )
        )
        result = producer.propagate(response, {"x": 0.5}, {"x": uniform()}, ["y"])[0]
        certificate = verify_mean_certificate(result.envelope)
        assert certificate.pilot_mean == 0
        assert certificate.main_samples == 408
        assert certificate.pilot_stream != certificate.main_stream
        assert result.envelope.sample_size == 408
        outputs.append(result.envelope.distribution_payload.samples)
    assert outputs[0] == outputs[1] == outputs[2]
    store = FileSystemCAS(tmp_path)
    ref = persist_uncertainty_envelope(store, result.envelope)
    loaded = load_uncertainty_envelope(FileSystemCAS(tmp_path), ref)
    assert verify_mean_certificate(loaded) == certificate
    raw = {**loaded.metadata["mean_estimator_certificate"], "main_stream": certificate.pilot_stream}
    fake = loaded.model_copy(
        update={"metadata": {**loaded.metadata, "mean_estimator_certificate": raw}}
    )
    with pytest.raises(ValueError, match="reconciliation"):
        verify_mean_certificate(fake)


def test_opaque_evaluator_cannot_self_certify_bounded_iid_mean():
    class Fake:
        bounded_iid = True

        def __call__(self, **params):
            pytest.fail("unadmitted callback ran")

    result = MonteCarloPropagator(
        PropagationConfig(bounded_iid_mean=BoundedIIDMeanPlan(metric_id="y"))
    ).propagate(Fake(), {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    assert result.envelope.metadata["failure"] == "bounded_iid_mean_law_not_admitted"


def test_rqmc_complete_nets_and_replica_estimator_error():
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=1000,
            mc_qmc_replicates=4,
            mc_sampling_method="sobol",
            compute_sensitivity=False,
        )
    ).propagate(lambda **p: {"y": p["x"] ** 2}, {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    meta = result.envelope.metadata
    assert meta["qmc_replicate_sizes"] == [256] * 4
    assert result.diagnostics["n_samples"] == 1024
    expected = np.std(meta["qmc_replicate_means"], ddof=1) / 2
    assert meta["mean_estimator_standard_error"] == expected
    assert meta["mc_std"] > 0.1
    assert expected < 0.005


def test_boolean_independence_cannot_promote_aggregation_or_ten_copies():
    env = gaussian(0.05).model_copy(
        update={"metadata": {"independence": True, "envelope_id": "repeat-exact-origin"}}
    )
    repeated = aggregate_envelopes([env] * 10, method="precision_weighted")
    assert repeated.metadata["duplicate_source_count"] == 9
    other = env.model_copy(
        update={"point_estimate": 0.01, "metadata": {"envelope_id": "other-origin"}}
    )
    combined = aggregate_envelopes([env, other], method="precision_weighted")
    assert combined.metadata["effective_information_count"] is None
    assert not combined.gate_eligible


def test_legacy_predictive_spread_never_authorizes_optional_stopping():
    producer = MonteCarloPropagator(
        PropagationConfig(
            adaptive_stopping=AdaptiveStoppingConfig(
                enabled=True, max_samples=500, ci_half_width_target=1
            ),
            compute_sensitivity=False,
        )
    )
    result = producer.propagate(lambda **p: {"y": 0.2}, {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    assert result.diagnostics["n_samples"] == 500
    assert result.diagnostics["stopped_early"] is False


def test_removal_of_range_property_keeps_markers_but_exposes_invalid_inputs(monkeypatch):
    from polisyos.foundry.uncertainty import covariance, monte_carlo

    monkeypatch.setattr(monte_carlo, "admit_sampling_support", lambda envelopes: None)
    monkeypatch.setattr(covariance, "admit_float32_range", lambda value: np.asarray(value))
    calls = []
    with np.errstate(invalid="ignore", over="ignore"):
        MonteCarloPropagator(
            PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
        ).propagate(
            lambda **p: calls.append(p["x"]) or {"y": 0},
            {"x": 0},
            {"x": gaussian(1e20, row=[1e40], names=["x"])},
            ["y"],
        )
    assert any(not math.isfinite(float(value)) for value in calls)


def test_removal_of_draw_outcome_property_is_detected_with_complete_marker_intact():
    from polisyos.foundry.uncertainty.sampling_admission import reconcile_draw_outcomes

    producer = MonteCarloPropagator(PropagationConfig(mc_n_samples=100, compute_sensitivity=False))
    result = producer.propagate(lambda **p: {"y": p["x"]}, {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    receipt = result.diagnostics["draw_outcome_provenance"]
    assert reconcile_draw_outcomes(receipt, ["y"]) == set()
    broken = {**receipt, "draw_records": receipt["draw_records"][:-1]}
    assert broken["outcome_denominator_complete"] is True
    with pytest.raises(ValueError, match="denominator"):
        reconcile_draw_outcomes(broken, ["y"])


@pytest.mark.parametrize("method", ["random", "sobol", "halton"])
def test_failed_support_cannot_certify_any_incomplete_replica(method):
    from polisyos.ir.analytics.uncertainty import CertificateKind

    def response(**params):
        x = params["x"]
        return {"good": x, "partial": None if x < 0 else x}

    results = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=256,
            mc_sampling_method=method,
            mc_qmc_replicates=4,
            compute_sensitivity=False,
        )
    ).propagate(response, {"x": 0}, {"x": uniform(-1, 1)}, ["good", "partial"])
    good, partial = results
    assert good.diagnostics["n_valid"] == 256
    assert partial.diagnostics["n_valid"] < 256
    assert partial.envelope.point_estimate == pytest.approx(0.5, abs=0.1)
    assert not partial.envelope.gate_eligible
    assert partial.envelope.confidence_level is None
    assert "mean_estimator_standard_error" not in partial.envelope.metadata
    assert partial.envelope.metadata["distribution_sample_semantics"] == (
        "successful_draws_only_conditional_on_execution"
    )
    if method != "random":
        assert (
            good.envelope.composition_provenance.certificate_kind is CertificateKind.RQMC_REPLICATES
        )
        assert good.envelope.metadata["qmc_estimator_support"] == "complete"
        assert (
            partial.envelope.composition_provenance.certificate_kind
            is not CertificateKind.RQMC_REPLICATES
        )
        assert partial.envelope.metadata["qmc_estimator_support"] == "incomplete"
        assert partial.envelope.composition_provenance.certificate_radius is None


@pytest.mark.parametrize("method", ["sobol", "halton"])
def test_rqmc_exceptional_support_preserves_conditional_result(method):
    def response(**params):
        if params["x"] < 0:
            raise ValueError("undefined negative support")
        return {"y": params["x"]}

    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=256,
            mc_sampling_method=method,
            mc_qmc_replicates=4,
            compute_sensitivity=False,
        )
    ).propagate(response, {"x": 0}, {"x": uniform(-1, 1)}, ["y"])[0]
    assert result.envelope.point_estimate == pytest.approx(0.5, abs=0.1)
    assert result.envelope.confidence_level is None
    assert not result.envelope.gate_eligible
    assert len(result.diagnostics["draw_outcome_provenance"]["draw_records"]) == 256
    assert "mean_estimator_standard_error" not in result.envelope.metadata


@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize("method", ["delta", "analytical", "monte_carlo"])
def test_covariance_optimization_flag_cannot_replace_declared_tied_law(flag, method):
    names = ["a", "b"]
    law = {name: gaussian(0.05, row=[0.0025, 0.0025], names=names) for name in names}
    result = PropagationDispatcher(
        PropagationConfig(
            preferred_method=method,
            delta_use_full_covariance=flag,
            delta_covariance_jitter=1e-6,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0, "b": 0},
        law,
        ["y"],
        weights={"a": 1, "b": -1},
    )[0]
    assert result.envelope.point_estimate == 0
    assert result.envelope.metadata.get("output_std", result.envelope.metadata.get("mc_std")) < 1e-9
    assert not result.envelope.gate_eligible


def test_direct_analytical_cannot_substitute_diagonal_covariance_for_declared_law():
    from polisyos.foundry.uncertainty.analytical import AnalyticalPropagator

    names = ["a", "b"]
    law = {name: gaussian(0.05, row=[0.0025, 0.0025], names=names) for name in names}
    with pytest.raises(ValueError, match="differs from the declared"):
        AnalyticalPropagator.propagate_linear_combination(
            weights={"a": 1, "b": -1},
            input_envelopes=law,
            output_metric_id="y",
            covariance=np.diag([0.0025, 0.0025]),
            use_full_covariance=False,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("mean_error_interval", "zero_width"),
        ("mc_n_samples", 999),
        ("mc_n_valid", 999),
        ("mc_n_failed", 1),
        ("predictive_interval_semantics", "mean_confidence_interval"),
        ("mc_seed", 999),
        ("mc_std", 0),
        ("mc_sampling_method", "sobol"),
    ],
)
def test_mean_certificate_reconciles_all_advertised_estimator_fields(field, value):
    result = MonteCarloPropagator(
        PropagationConfig(
            bounded_iid_mean=BoundedIIDMeanPlan(metric_id="y"), compute_sensitivity=False
        )
    ).propagate(BoundedIndicatorResponse("x", "y", 0.5), {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    assert verify_mean_certificate(result.envelope) is not None
    if value == "zero_width":
        value = [result.envelope.point_estimate] * 2
    modified = result.envelope.model_copy(
        update={"metadata": {**result.envelope.metadata, field: value}}
    )
    with pytest.raises(ValueError, match="advertised"):
        verify_mean_certificate(modified)


@pytest.mark.parametrize(
    "field,value",
    [
        ("confidence_interval", (0.0, 0.0)),
        ("distribution_family", DistributionFamily.NORMAL),
        ("source", UncertaintySource.MANUAL),
        ("propagation_method", PropagationMethod.NONE),
        ("interval_semantics", IntervalSemantics.HEURISTIC_RANGE),
        ("is_heuristic_ci", True),
        ("sample_size", 999),
    ],
)
def test_mean_certificate_reconciles_its_predictive_compatibility_carrier(field, value):
    result = MonteCarloPropagator(
        PropagationConfig(
            bounded_iid_mean=BoundedIIDMeanPlan(metric_id="y"), compute_sensitivity=False
        )
    ).propagate(BoundedIndicatorResponse("x", "y", 0.5), {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    modified = result.envelope.model_copy(update={field: value})
    with pytest.raises(ValueError, match="advertised"):
        verify_mean_certificate(modified)


def test_bounded_fixed_budget_retains_complete_carrier_below_legacy_minimum(tmp_path):
    result = MonteCarloPropagator(
        PropagationConfig(
            bounded_iid_mean=BoundedIIDMeanPlan(metric_id="y", absolute_error=0.5),
            compute_sensitivity=False,
        )
    ).propagate(BoundedIndicatorResponse("x", "y", 0.5), {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    certificate = verify_mean_certificate(result.envelope)
    assert certificate.main_samples < 50
    assert len(result.envelope.distribution_payload.samples) == certificate.frozen_main_samples
    store = FileSystemCAS(tmp_path)
    ref = persist_uncertainty_envelope(store, result.envelope)
    assert verify_mean_certificate(load_uncertainty_envelope(FileSystemCAS(tmp_path), ref))


def test_bounded_budget_over_declared_maximum_emits_no_certificate():
    result = MonteCarloPropagator(
        PropagationConfig(
            bounded_iid_mean=BoundedIIDMeanPlan(metric_id="y"),
            adaptive_stopping=AdaptiveStoppingConfig(max_samples=100),
            compute_sensitivity=False,
        )
    ).propagate(BoundedIndicatorResponse("x", "y", 0.5), {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    assert result.envelope.metadata["failure"] == "frozen_budget_exceeds_declared_maximum"
    assert verify_mean_certificate(result.envelope) is None


@pytest.mark.parametrize("corruption", ["response", "extra", "missing", "boolean"])
def test_mean_certificate_reconciles_entire_canonical_evaluator_recipe(corruption):
    result = MonteCarloPropagator(
        PropagationConfig(
            bounded_iid_mean=BoundedIIDMeanPlan(metric_id="y"), compute_sensitivity=False
        )
    ).propagate(BoundedIndicatorResponse("x", "y", 0.5), {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    raw = dict(result.envelope.metadata["mean_estimator_certificate"])
    recipe = dict(raw["evaluator_recipe"])
    if corruption == "response":
        recipe["response"] = "fake_other_response"
    elif corruption == "extra":
        recipe["independently_verified"] = True
    elif corruption == "missing":
        del recipe["response"]
    else:
        recipe["threshold"] = False
    raw["evaluator_recipe"] = recipe
    modified = result.envelope.model_copy(
        update={"metadata": {**result.envelope.metadata, "mean_estimator_certificate": raw}}
    )
    with pytest.raises(ValueError, match="recipe"):
        verify_mean_certificate(modified)


@pytest.mark.parametrize("name,threshold", [("x", True), ("x", False), ("", 0.5)])
def test_canonical_producer_and_readback_share_the_same_recipe_admission(name, threshold):
    result = MonteCarloPropagator(
        PropagationConfig(
            bounded_iid_mean=BoundedIIDMeanPlan(metric_id="y"), compute_sensitivity=False
        )
    ).propagate(
        BoundedIndicatorResponse(name, "y", threshold), {name: 0.5}, {name: uniform()}, ["y"]
    )[0]
    assert result.envelope.metadata["failure"] == "bounded_iid_mean_law_not_admitted"
    assert verify_mean_certificate(result.envelope) is None


def test_draw_reconciliation_rejects_orphan_indices_codes_and_duplicate_outputs():
    from copy import deepcopy

    from polisyos.foundry.uncertainty.sampling_admission import reconcile_draw_outcomes

    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
    ).propagate(lambda **p: {"y": p["x"]}, {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    original = result.diagnostics["draw_outcome_provenance"]
    for index, code in [
        (999999, "simulation_exception"),
        (-1, "simulation_exception"),
        (0, "invented_success"),
    ]:
        broken = deepcopy(original)
        broken["failure_records"].append(
            {
                "draw_index": index,
                "sampled_input_sha256": "0" * 64,
                "output_outcomes": [
                    {"output_metric_id": "y", "outcome_code": code, "error_type": None}
                ],
            }
        )
        with pytest.raises(ValueError):
            reconcile_draw_outcomes(broken, ["y"])
    broken = deepcopy(original)
    broken["draw_records"][0]["successful_outputs"] = ["y", "y"]
    with pytest.raises(ValueError, match="denominator"):
        reconcile_draw_outcomes(broken, ["y"])


def test_unattempted_support_marks_every_output_incomplete():
    from polisyos.foundry.uncertainty.sampling_admission import reconcile_draw_outcomes

    result = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=100, compute_sensitivity=False)
    ).propagate(lambda **p: {"y": p["x"]}, {"x": 0.5}, {"x": uniform()}, ["y"])[0]
    receipt = result.diagnostics["draw_outcome_provenance"]
    incomplete = {
        **receipt,
        "requested_draw_count": 101,
        "unattempted_draw_count": 1,
        "outcome_denominator_complete": False,
    }
    assert reconcile_draw_outcomes(incomplete, ["y"]) == {"y"}
