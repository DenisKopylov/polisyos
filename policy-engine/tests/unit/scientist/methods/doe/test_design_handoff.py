"""Actual completed design persistence, fresh search consumption and replay refusal."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.methods.doe._receipt import (
    _load_analysis,
    _load_multi_output_analysis,
    _persist_analysis,
    _persist_multi_output_analysis,
)
from polisyos.scientist.methods.doe.adaptive import (
    AdaptiveResult,
    AdaptiveSampler,
    ConvergenceConfig,
)
from polisyos.scientist.methods.doe.designs import ParameterSpec, SensitivityPlan
from polisyos.scientist.methods.doe.multi_output import MultiOutputAnalyzer
from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples
from polisyos.scientist.methods.doe.uncertainty import SensitivityUncertaintyConfig
from polisyos.scientist.methods.search.sensitivity_adapter import SensitivityAwareCandidateGenerator


class _Candidates:
    def generate(self, history, current_best, context):
        return {"x": 0.5}

    def generate_batch(self, history, current_best, context, batch_size):
        return [self.generate(history, current_best, context) for _ in range(batch_size)]


def _plan(**updates):
    values = {
        "method": "morris",
        "parameter_specs": [
            ParameterSpec(name="x", lower_bound=0.0, upper_bound=10.0, unit="metres"),
            ParameterSpec(name="z", lower_bound=0.0, upper_bound=1.0, unit="seconds"),
        ],
        "seed": 17,
        "n_trajectories": 2,
        "allow_large_run": True,
    }
    values.update(updates)
    return SensitivityPlan(**values)


@pytest.mark.parametrize("failure_phase", ["none", "evaluation", "analysis"])
def test_actual_adaptive_last_design_reaches_fresh_search_consumer(
    store, monkeypatch, failure_phase
):
    from polisyos.scientist.methods.doe import analysis

    evaluated = []
    original_prepare = analysis._prepare_analysis_inputs

    def prepare(plan, samples, outputs):
        if failure_phase == "analysis" and plan.n_trajectories == 4:
            raise ValueError("declared second analysis boundary fault")
        return original_prepare(plan, samples, outputs)

    monkeypatch.setattr(analysis, "_prepare_analysis_inputs", prepare)

    def evaluate(samples):
        evaluated.append(samples.copy())
        if failure_phase == "evaluation" and len(evaluated) == 2:
            raise ValueError("declared partial evaluator boundary fault")
        return 2 * samples[:, 0] + 3 * samples[:, 1]

    result = AdaptiveSampler(
        _plan(),
        ConvergenceConfig(max_rounds=2, trajectory_step=2, ranking_stability_threshold=1.01),
    ).run(evaluate)
    assert [len(x) for x in evaluated] == [6, 12]
    expected_round = 2 if failure_phase == "none" else 1
    expected_rows = 12 if expected_round == 2 else 6
    assert result.final_context == {
        "completed_round": expected_round,
        "initial_n_trajectories": 2,
        "trajectory_step": 2,
    }
    np.testing.assert_array_equal(result.final_samples, evaluated[expected_round - 1])
    assert result.final_result.total_runs == expected_rows
    assert result.total_evaluations == (6 if failure_phase == "evaluation" else 18)
    assert all(a.generation_seconds >= 0.0 for a in result.attempts)
    assert all(
        a.evaluation_seconds is not None and a.evaluation_seconds >= 0.0 for a in result.attempts
    )
    assert result.attempts[0].analysis_seconds is not None
    assert result.attempts[0].analysis_seconds >= 0.0
    if failure_phase == "evaluation":
        assert result.attempts[-1].evaluator_completed is None
        assert result.attempts[-1].analysis_seconds is None
    elif failure_phase == "analysis":
        assert result.attempts[-1].evaluator_completed == 12
    # Restore the genuine numerical producer before the independent selected
    # reader replays; the injected boundary fault is not a numerical backend.
    monkeypatch.setattr(analysis, "_prepare_analysis_inputs", original_prepare)
    ref = result.persist_final(store)
    payload = from_canonical_bytes(store.get_bytes(ref))
    assert payload["adaptive_context"] == result.final_context
    assert payload["plan"]["n_trajectories"] == result.final_plan.n_trajectories
    fresh = FileSystemCAS(store.root)
    loaded = _load_analysis(fresh, ref)
    assert loaded.mu_star == pytest.approx({"x": 20.0, "z": 3.0})
    assert loaded.total_runs == expected_rows
    consumer = SensitivityAwareCandidateGenerator.from_artifact(_Candidates(), fresh, ref)
    candidate = consumer.generate([], None, {})
    assert candidate["_sensitivity"]["design_id"] == loaded.metadata["design_id"]
    assert candidate["_sensitivity"]["analysis_ref"]["artifact_id"] == str(ref.artifact_id)


@pytest.mark.parametrize("mutation", ["seed", "axes", "round", "raw_samples"])
def test_adaptive_selected_source_mutations_refuse_at_actual_reader(store, mutation):
    result = AdaptiveSampler(_plan(), ConvergenceConfig(max_rounds=1)).run(
        lambda samples: 2 * samples[:, 0] + 3 * samples[:, 1]
    )
    ref = result.persist_final(store)
    payload = copy.deepcopy(from_canonical_bytes(store.get_bytes(ref)))
    if mutation == "seed":
        payload["plan"]["seed"] += 1
    elif mutation == "axes":
        payload["plan"]["parameter_specs"].reverse()
    elif mutation == "round":
        payload["adaptive_context"]["completed_round"] += 1
    else:
        payload["samples"][0][0] += 0.5
    changed = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="doe_sensitivity_analysis",
            media_type="application/json",
            schema=SchemaInfo(name="doe_sensitivity_analysis", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    assert store.verify(changed).ok
    with pytest.raises(ValueError, match="does not bind|do not reconcile|does not reproduce"):
        _load_analysis(FileSystemCAS(store.root), changed)


def test_legacy_bare_adaptive_result_cannot_invent_a_persisted_source(store):
    original = AdaptiveSampler(_plan(), ConvergenceConfig(max_rounds=1)).run(
        lambda samples: samples[:, 0] + samples[:, 1]
    )
    legacy = AdaptiveResult(final_result=original.final_result)
    with pytest.raises(ValueError, match="source design is not established"):
        legacy.persist_final(store)


@pytest.mark.parametrize("multi_output", [False, True])
def test_imputation_limit_and_original_rows_survive_selected_fresh_reader(store, multi_output):
    from polisyos.scientist.methods.doe.analysis import analyze_sensitivity

    plan = _plan(
        n_trajectories=16,
        run_failure_policy="impute_baseline",
        uncertainty=SensitivityUncertaintyConfig(enabled=True, n_resamples=20, random_seed=7),
    )
    samples = generate_sensitivity_samples(plan)
    scalar = 2 * samples[:, 0] + 3 * samples[:, 1]
    outputs = np.column_stack((scalar, samples[:, 0] ** 2)) if multi_output else scalar
    outputs[1] = np.nan
    if multi_output:
        result = MultiOutputAnalyzer().analyze(plan, samples, outputs)
        ref = _persist_multi_output_analysis(store, plan, samples, outputs, result)
        loaded = _load_multi_output_analysis(FileSystemCAS(store.root), ref)
        components = loaded.per_component
    else:
        result = analyze_sensitivity(plan, samples, outputs)
        ref = _persist_analysis(store, plan, samples, outputs, result)
        loaded = _load_analysis(FileSystemCAS(store.root), ref)
        components = [loaded]
    original = from_canonical_bytes(store.get_bytes(ref))
    np.testing.assert_array_equal(np.asarray(original["samples"], dtype=float), samples)
    np.testing.assert_array_equal(np.asarray(original["outputs"], dtype=float), outputs)
    for component in components:
        assert component.total_runs == 48
        assert component.failed_runs == 1
        assert component.metadata["imputed_row_indices"] == [1]
        assert component.metadata["imputation_model_status"] == "not_established"
        assert component.metadata["uncertainty_status"] == "unavailable"
        assert component.uncertainty is None


def test_multi_output_result_payload_refuses_extra_fields_at_fresh_reader(store):
    plan = _plan()
    samples = generate_sensitivity_samples(plan)
    outputs = np.column_stack((samples[:, 0] + samples[:, 1], samples[:, 0] - samples[:, 1]))
    result = MultiOutputAnalyzer().analyze(plan, samples, outputs)
    ref = _persist_multi_output_analysis(store, plan, samples, outputs, result)
    _load_multi_output_analysis(FileSystemCAS(store.root), ref)
    payload = from_canonical_bytes(store.get_bytes(ref))
    payload["result"]["unrecognized_fit_authority"] = "qualified"
    changed = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="doe_multi_output_analysis",
            media_type="application/json",
            schema=SchemaInfo(name="doe_multi_output_analysis", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    assert store.verify(changed).ok
    # The bounded Core reader reports its strict Python-adapter diagnostic
    # after both Python/JSON admission fail; it need not expose Pydantic's
    # secondary JSON ``extra_forbidden`` wording.
    with pytest.raises(ValueError, match="MultiOutputSensitivityResult"):
        _load_multi_output_analysis(FileSystemCAS(store.root), changed)
