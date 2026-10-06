"""Native SALib experiment-to-CAS-to-search controls with analytic oracles."""

from __future__ import annotations

import copy

import numpy as np
import pytest

pytest.importorskip("SALib")

from polisyos.scientist.methods.autotune.sensitivity_bridge import SensitivityBridge
from polisyos.scientist.methods.doe._receipt import _load_analysis, _persist_analysis
from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
from polisyos.scientist.methods.doe.designs import ParameterSpec, SensitivityPlan
from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples
from polisyos.scientist.methods.search.sensitivity_adapter import SensitivityAwareCandidateGenerator
from tests._helpers.artifacts import put_json_artifact


def _bounds():
    return [
        {"name": "x", "lower": 0.0, "upper": 10.0, "unit": "metres"},
        {"name": "z", "lower": 0.0, "upper": 1.0, "unit": "seconds"},
    ]


def _plan(**overrides):
    arguments = {
        "method": "sobol",
        "parameter_specs": [
            ParameterSpec(name="x", lower_bound=0.0, upper_bound=1.0),
            ParameterSpec(name="z", lower_bound=0.0, upper_bound=1.0),
        ],
        "input_law": "independent",
        "seed": 127,
        "n_trajectories": 256,
        "max_estimated_runs": 2048,
    }
    arguments.update(overrides)
    return SensitivityPlan(**arguments)


class _BaseGenerator:
    def generate(self, history, current_best, context):
        return {"x": 0.5}

    def generate_batch(self, history, current_best, context, batch_size):
        return [{"x": 0.5} for _ in range(batch_size)]


def test_morris_native_scale_and_persisted_search_consumer(store):
    answer = SensitivityBridge().analyze_search_space(
        _bounds(),
        lambda p: 2 * p["x"] + 3 * p["z"],
        n_trajectories=16,
        seed=43,
        store=store,
    )
    result = answer["result"]
    # Analytic physical derivatives 2 and 3 become full-range effects 20 and 3.
    assert result.mu_star == pytest.approx({"x": 20.0, "z": 3.0})
    assert result.metadata["parameter_units"] == {"x": "metres", "z": "seconds"}
    assert result.total_runs == result.successful_runs == 48
    assert result.failed_runs == 0
    reader = SensitivityAwareCandidateGenerator.from_artifact(
        _BaseGenerator(),
        store,
        answer["analysis_ref"],
    )
    candidate = reader.generate([], None, {})
    metadata = candidate["_sensitivity"]
    assert metadata["analysis_id"] == result.metadata["analysis_id"]
    assert metadata["design_id"] == result.metadata["design_id"]
    assert metadata["analysis_ref"]["artifact_id"] == str(answer["analysis_ref"].artifact_id)
    assert metadata["population_law_status"] == "not_established"
    assert reader.generate_batch([], None, {}, 2)[0]["_sensitivity"] == metadata


def test_sobol_native_linear_oracle_and_replay():
    plan = _plan()
    samples = generate_sensitivity_samples(plan)
    result = analyze_sensitivity(plan, samples, 2 * samples[:, 0] + 3 * samples[:, 1])
    # Var(X)=1/12; independent additive contributions are 4/13 and 9/13.
    assert result.s1 == pytest.approx({"x": 4 / 13, "z": 9 / 13}, abs=0.015)
    assert result.st == pytest.approx({"x": 4 / 13, "z": 9 / 13}, abs=0.015)
    assert result.s2["x"]["z"] == pytest.approx(0.0, abs=0.02)
    np.testing.assert_array_equal(samples, generate_sensitivity_samples(plan))
    assert result.metadata["design_order_basis"] == "recomputed"


def test_sobol_whole_paired_block_replay_keeps_estimands_and_rebinds_content(store):
    from polisyos.core.artifacts import FileSystemCAS

    plan = _plan(n_trajectories=1024, max_estimated_runs=6144)
    samples = generate_sensitivity_samples(plan)
    outputs = samples[:, 0] + samples[:, 1] + 2 * samples[:, 0] * samples[:, 1]
    original = analyze_sensitivity(plan, samples, outputs)
    original_ref = _persist_analysis(store, plan, samples, outputs, original)
    block_size = 2 * plan.num_parameters + 2
    # Preserve every A/AB/BA/B role inside its block and move paired outcomes with X.
    order = np.random.default_rng(7903).permutation(plan.n_trajectories)
    replay_samples = samples.reshape(-1, block_size, 2)[order].reshape(-1, 2)
    replay_outputs = outputs.reshape(-1, block_size)[order].reshape(-1)
    replay = analyze_sensitivity(plan, replay_samples, replay_outputs)
    assert replay.s1 == pytest.approx({"x": 12 / 25, "z": 12 / 25}, abs=0.01)
    assert replay.st == pytest.approx({"x": 13 / 25, "z": 13 / 25}, abs=0.01)
    assert replay.s2["x"]["z"] == pytest.approx(1 / 25, abs=0.01)
    assert replay.s1 == pytest.approx(original.s1, abs=1e-12)
    assert replay.st == pytest.approx(original.st, abs=1e-12)
    assert replay.s2["x"]["z"] == pytest.approx(original.s2["x"]["z"], abs=1e-12)
    for key in (
        "ordered_samples_sha256",
        "ordered_outputs_sha256",
        "design_id",
        "analysis_id",
    ):
        assert replay.metadata[key] != original.metadata[key]
    with pytest.raises(ValueError, match="does not bind"):
        _persist_analysis(store, plan, replay_samples, replay_outputs, original)
    replay_ref = _persist_analysis(store, plan, replay_samples, replay_outputs, replay)
    assert replay_ref != original_ref
    fresh_store = FileSystemCAS(store.root)
    assert _load_analysis(fresh_store, original_ref) == original
    assert _load_analysis(fresh_store, replay_ref) == replay
    reader = SensitivityAwareCandidateGenerator.from_artifact(
        _BaseGenerator(), fresh_store, replay_ref
    )
    assert (
        reader.generate([], None, {})["_sensitivity"]["analysis_id"]
        == replay.metadata["analysis_id"]
    )
    # Integrity-valid new bytes paired with an old receipt still fail at the real reader.
    import json

    stale = json.loads(store.get_bytes(original_ref))
    stale["samples"] = replay_samples.tolist()
    stale["outputs"] = replay_outputs.tolist()
    stale_ref = put_json_artifact(store, stale, kind="doe_sensitivity_analysis")
    assert fresh_store.verify(stale_ref).ok
    with pytest.raises(ValueError, match="does not reproduce"):
        SensitivityAwareCandidateGenerator.from_artifact(_BaseGenerator(), fresh_store, stale_ref)


@pytest.mark.parametrize("mutation", ["rows", "duplicate_block", "missing_block"])
def test_sobol_refuses_broken_block_membership_or_interior_roles(mutation):
    plan = _plan()
    samples = generate_sensitivity_samples(plan)
    outputs = samples[:, 0] + samples[:, 1]
    block_size = 2 * plan.num_parameters + 2
    if mutation == "rows":
        # Paired outputs follow rows, but AB/BA roles are now wrong inside one block.
        samples[[0, 1]] = samples[[1, 0]]
        outputs[[0, 1]] = outputs[[1, 0]]
    elif mutation == "duplicate_block":
        samples[block_size : 2 * block_size] = samples[:block_size]
        outputs[block_size : 2 * block_size] = outputs[:block_size]
    else:
        samples, outputs = samples[:-block_size], outputs[:-block_size]
    with pytest.raises(ValueError, match="canonical seeded ordered design"):
        analyze_sensitivity(plan, samples, outputs)


@pytest.mark.parametrize("law", ["unknown", "dependent"])
def test_sobol_requires_declared_independent_law_before_evaluator(law):
    calls = []
    with pytest.raises(ValueError, match="independent input law"):
        SensitivityBridge().analyze_search_space(
            _bounds(),
            lambda p: calls.append(p) or 0.0,
            method="sobol",
            seed=31,
            input_law=law,
        )
    assert calls == []


def test_sobol_missing_seed_refuses_before_evaluator():
    calls = []
    with pytest.raises(ValueError, match="seed"):
        SensitivityBridge().analyze_search_space(
            _bounds(),
            lambda p: calls.append(p) or 0.0,
            method="sobol",
            input_law="independent",
        )
    assert calls == []


@pytest.mark.parametrize("mutation", ["reverse", "correlate", "wrong_seed", "wrong_distribution"])
def test_shape_and_law_markers_do_not_admit_a_different_sobol_design(mutation):
    plan = _plan()
    samples = generate_sensitivity_samples(plan)
    if mutation == "reverse":
        samples = samples[::-1]
    elif mutation == "correlate":
        samples[:, 1] = samples[:, 0]
    elif mutation == "wrong_seed":
        plan = _plan(seed=128)
    else:
        replacement = plan.model_dump()
        replacement["parameter_specs"][0].update(
            distribution="triangular",
            distribution_spec={"kind": "triangular", "mode_fraction": 0.75},
        )
        plan = SensitivityPlan.model_validate(replacement)
    with pytest.raises(ValueError, match="canonical seeded ordered design"):
        analyze_sensitivity(plan, samples, samples[:, 0] + samples[:, 1])


def test_bridge_seed_isolation_distribution_and_exact_identity(store):
    bridge = SensitivityBridge()
    bounds = [
        {
            "name": "x",
            "lower": 0.0,
            "upper": 1.0,
            "distribution": "triangular",
            "distribution_spec": {"kind": "triangular", "mode_fraction": 0.75},
        }
    ]
    before = copy.deepcopy(np.random.get_state())
    first = bridge.analyze_search_space(
        bounds,
        lambda p: p["x"],
        seed=17,
        n_trajectories=16,
        store=store,
    )
    bridge.analyze_search_space(bounds, lambda p: p["x"], seed=18, n_trajectories=16)
    repeated = bridge.analyze_search_space(
        bounds,
        lambda p: p["x"],
        seed=17,
        n_trajectories=16,
        store=store,
    )
    after = np.random.get_state()
    assert before[0] == after[0]
    np.testing.assert_array_equal(before[1], after[1])
    assert before[2:] == after[2:]
    assert first["analysis_ref"] == repeated["analysis_ref"]
    assert (
        first["result"].metadata["distribution_mapping_fingerprint"]
        == repeated["result"].metadata["distribution_mapping_fingerprint"]
    )


@pytest.mark.parametrize("mutation", ["result", "order", "seed", "kind", "schema"])
def test_content_valid_fake_receipt_refuses_at_actual_consumer(store, mutation):
    answer = SensitivityBridge().analyze_search_space(
        _bounds(),
        lambda p: 2 * p["x"] + 3 * p["z"],
        seed=43,
        store=store,
    )
    import json

    payload = json.loads(store.get_bytes(answer["analysis_ref"]))
    kind, schema_version = "doe_sensitivity_analysis", "1.0"
    if mutation == "result":
        payload["result"]["mu_star"]["x"] = 999.0
    elif mutation == "order":
        payload["samples"] = payload["samples"][::-1]
    elif mutation == "seed":
        payload["plan"]["seed"] = 44
    elif mutation == "kind":
        kind = "not_doe_sensitivity_analysis"
    else:
        schema_version = "9.0"
    fake = put_json_artifact(store, payload, kind=kind, schema_version=schema_version)
    assert store.verify(fake).ok  # Byte/hash validity is the cheap proxy, not numerical validity.
    with pytest.raises(ValueError):
        SensitivityAwareCandidateGenerator.from_artifact(_BaseGenerator(), store, fake)


@pytest.mark.parametrize("failed_value", [np.nan, np.inf, -np.inf])
def test_denominator_and_failed_support_survive_morris_receipt(store, failed_value):
    from polisyos.scientist.methods.doe._receipt import _persist_analysis

    plan = _plan(
        method="morris",
        n_trajectories=8,
        run_failure_policy="drop_failed",
        min_success_rate=0.5,
    )
    samples = generate_sensitivity_samples(plan)
    outputs = samples[:, 0] + samples[:, 1]
    outputs[1] = failed_value
    result = analyze_sensitivity(plan, samples, outputs)
    ref = _persist_analysis(store, plan, samples, outputs, result)
    reopened = _load_analysis(store, ref)
    assert reopened.total_runs == 24
    assert reopened.successful_runs == 23
    assert reopened.failed_runs == 1
    assert reopened.metadata["effective_run_count"] == 21
    assert reopened.metadata["failed_row_indices"] == [1]
    assert reopened.metadata["dropped_trajectory_ids"] == [0]
    assert reopened.metadata["selection_bias_status"] == "not_established"


def test_unknown_method_and_budget_are_admitted_before_callback():
    calls = []
    for kwargs in ({"method": "misspelled"}, {"n_trajectories": 1000}):
        with pytest.raises(ValueError):
            SensitivityBridge().analyze_search_space(
                _bounds(),
                lambda p: calls.append(p) or 0.0,
                seed=31,
                **kwargs,
            )
    assert calls == []
