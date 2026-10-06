"""Actual DOE/CAS ranking changes the existing native proposal and default search consumer."""

from copy import deepcopy

import pytest

pytest.importorskip("SALib", reason="UNRUN: actual DOE backend required", exc_type=ImportError)
pytest.importorskip("torch", reason="UNRUN: native Sobol backend required", exc_type=ImportError)
pytest.importorskip("botorch", reason="UNRUN: native receiver required", exc_type=ImportError)
pytest.importorskip("gpytorch", reason="UNRUN: native receiver required", exc_type=ImportError)

from polisyos.core import artifacts, canon
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    persist_benchmark_suite,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.runtime import SearchLoopRunner
from polisyos.scientist.methods.autotune.sensitivity_bridge import SensitivityBridge
from polisyos.scientist.methods.search.sensitivity_adapter import SensitivityAwareCandidateGenerator

pytestmark = pytest.mark.integration


def bounds():
    return [
        {"name": "x", "lower": -2.0, "upper": 2.0, "unit": "metres", "distribution": "uniform"},
        {"name": "z", "lower": 10.0, "upper": 20.0, "unit": "seconds", "distribution": "uniform"},
    ]


def cold(space_bounds=None):
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds() if space_bounds is None else space_bounds),
        primary_metric="score",
        compare_split=BenchmarkSplit.SELECTION,
        direction=MetricDirection.MINIMIZE,
        seed=31,
    )
    assert generator.botorch_available
    return generator


def analysis(store, *, dominant="x", overrides=None):
    calls = []

    def evaluator(params):
        calls.append(dict(params))
        return 100 * params[dominant] + params["z" if dominant == "x" else "x"]

    kwargs = {"method": "morris", "n_trajectories": 8, "seed": 31, "store": store}
    kwargs.update(overrides or {})
    answer = SensitivityBridge().analyze_search_space(bounds(), evaluator, **kwargs)
    expected_runs = kwargs["n_trajectories"] * (6 if kwargs["method"] == "sobol" else 3)
    assert len(calls) == answer["result"].total_runs == expected_runs
    assert answer["result"].ranking[0] == dominant
    return answer


def normalized(candidate):
    return ((candidate["x"] + 2) / 4, (candidate["z"] - 10) / 10)


def test_real_recomputed_ranking_changes_physical_sobol_assignment(tmp_path):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    first = analysis(store, dominant="x")
    second = analysis(store, dominant="z")
    a = SensitivityAwareCandidateGenerator.from_artifact(cold(), store, first["analysis_ref"])
    b = SensitivityAwareCandidateGenerator.from_artifact(cold(), store, second["analysis_ref"])
    baseline = cold().generate([], None, {})
    left, right = a.generate([], None, {}), b.generate([], None, {})
    assert (
        left["_strategy_metadata"]["source"]
        == right["_strategy_metadata"]["source"]
        == "sobol_init"
    )
    assert normalized(left) == pytest.approx(normalized(baseline))
    assert normalized(right) == pytest.approx(normalized(left)[::-1])
    assert normalized(left)[0] != normalized(left)[1]
    assert left["x"] != right["x"] and left["z"] != right["z"]
    assert left["_sensitivity"]["ranking_consumer"] == "native_coordinate_order"
    for adapter, answer in [(a, first), (b, second)]:
        state = adapter.get_state()
        policy = state["config"]["sensitivity_order"]
        assert policy["parameter_order"] == answer["ranking"]
        assert policy["analysis_ref"] == answer["analysis_ref"].model_dump(mode="json")
        assert (
            policy["analysis_identity"]["analysis_id"] == answer["result"].metadata["analysis_id"]
        )
        assert policy["population_law_status"] == "not_established"
        assert adapter._base._optimizer._model is None


def test_actual_cas_checkpoint_reopen_preserves_next_native_action(tmp_path):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    answer = analysis(store, dominant="z")
    original = SensitivityAwareCandidateGenerator.from_artifact(
        cold(), store, answer["analysis_ref"]
    )
    original.generate([], None, {})
    state_ref = store.put_json(
        original.get_state(),
        artifacts.PutOptions(kind="search.generator_state", media_type="application/json"),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    fresh_store = artifacts.FileSystemCAS(store.root)
    resumed = SensitivityAwareCandidateGenerator.from_artifact(
        cold(), fresh_store, answer["analysis_ref"]
    )
    resumed.set_state(canon.from_canonical_bytes(fresh_store.get_verified_snapshot(state_ref).data))
    expected, actual = original.generate([], None, {}), resumed.generate([], None, {})
    assert normalized(actual) == normalized(expected)
    assert actual["_sensitivity"]["analysis_ref"] == answer["analysis_ref"].model_dump(mode="json")
    assert (
        resumed.get_state()["strategy_state"]["rng_state"]["sobol"]
        == original.get_state()["strategy_state"]["rng_state"]["sobol"]
    )


@pytest.mark.parametrize("mutation", ["lower", "unit", "distribution", "missing", "unknown_unit"])
def test_actual_native_basis_mismatch_refuses_before_proposal(tmp_path, mutation):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    answer = analysis(store)
    changed = bounds()
    if mutation == "lower":
        changed[0]["lower"] = -3.0
    elif mutation == "unit":
        changed[0]["unit"] = "feet"
    elif mutation == "distribution":
        changed[0]["distribution"] = "normal"
    elif mutation == "missing":
        changed = changed[:1]
    else:
        changed[0]["unit"] = "unspecified"
    generator = cold(changed)
    before = generator.get_state()
    with pytest.raises(ValueError):
        SensitivityAwareCandidateGenerator.from_artifact(generator, store, answer["analysis_ref"])
    assert generator.get_state() == before
    assert generator._optimizer._model is None


def test_same_ref_changed_source_refuses_before_proposal_and_restore(tmp_path):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    answer = analysis(store, dominant="z")
    generator = cold()
    adapter = SensitivityAwareCandidateGenerator.from_artifact(
        generator, store, answer["analysis_ref"]
    )
    adapter.generate([], None, {})
    state = adapter.get_state()
    before = deepcopy(generator._optimizer.get_state().to_artifact())
    blob, _ = store._paths(answer["analysis_ref"].artifact_id)
    blob.write_bytes(b"changed original DOE rows under the same selected full reference")
    with pytest.raises(artifacts.ArtifactIntegrityError):
        adapter.generate([], None, {})
    with pytest.raises(artifacts.ArtifactIntegrityError):
        adapter.set_state(state)
    assert generator._optimizer.get_state().to_artifact() == before
    assert generator._optimizer._model is None


@pytest.mark.parametrize("mutation", ["seed", "law", "forged_index", "wrong_schema"])
def test_integrity_valid_forged_receipt_refuses_before_native_change(tmp_path, mutation):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    answer = analysis(
        store, overrides={"method": "sobol", "n_trajectories": 32, "input_law": "independent"}
    )
    raw = canon.from_canonical_bytes(store.get_verified_snapshot(answer["analysis_ref"]).data)
    if mutation == "seed":
        raw["plan"]["seed"] = None
    elif mutation == "law":
        raw["plan"]["input_law"] = "unknown"
    elif mutation == "forged_index":
        raw["result"]["st"]["x"] = 0.99
    options = artifacts.PutOptions(
        kind="doe_sensitivity_analysis",
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name="doe_sensitivity_analysis", version="3.0" if mutation == "wrong_schema" else "1.0"
        ),
    )
    invalid_ref = store.put_json(raw, options, canon_spec=canon.CanonSpec(forbid_floats=False))
    from polisyos.core.artifacts.manifest_profile import artifact_manifest_profile_sha256

    snapshot = store.get_verified_snapshot(invalid_ref)
    invalid_ref = invalid_ref.model_copy(
        update={"manifest_profile_sha256": artifact_manifest_profile_sha256(snapshot.manifest)}
    )
    generator = cold()
    before = generator.get_state()
    with pytest.raises(ValueError):
        SensitivityAwareCandidateGenerator.from_artifact(generator, store, invalid_ref)
    assert generator.get_state() == before


class ExperimentMutation(MutationArtifact):
    x: float
    z: float


class ExperimentCodec:
    def encode(self, payload):
        return ExperimentMutation.model_validate(payload)

    def decode(self, payload):
        return ExperimentMutation(
            loop_id="doe-order",
            x=payload["x"],
            z=payload["z"],
            metadata={"sensitivity": payload["_sensitivity"]},
        )


class ExperimentEvaluator:
    def __init__(self):
        self.observed = []

    def evaluate(self, candidate_ref, suite_ref, context):
        payload = canon.from_canonical_bytes(
            context["store"].get_verified_snapshot(candidate_ref).data
        )
        self.observed.append((candidate_ref, payload))
        return BenchmarkEvaluation(
            loop_id="doe-order",
            suite_id="coordinate-experiment",
            candidate_ref=candidate_ref,
            selection_metrics={"score": payload["x"] + payload["z"]},
            guardrails={"finite": True},
            promotable=False,
            status="ok",
            runtime_split_type=BenchmarkSplit.SELECTION,
        )


def test_resolved_adapter_reaches_actual_default_loop_persisted_consumer(tmp_path):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    answer = analysis(store, dominant="z")
    generator = SensitivityAwareCandidateGenerator.from_artifact(
        cold(), store, answer["analysis_ref"]
    )
    evaluator = ExperimentEvaluator()
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="coordinate-experiment", kind="analytic", data_basis="candidate_only"
        ),
    )
    policy = PromotionPolicy(
        loop_id="doe-order",
        primary_metric="score",
        unit="synthetic-objective",
        direction=MetricDirection.MINIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
    )
    spec = SearchLoopSpec("doe-order", ExperimentCodec(), generator, evaluator, policy)
    result = SearchLoopRunner(
        store=store, registry=ChampionRegistry(tmp_path / "champions", store=store)
    ).run(spec, suite_ref=suite_ref, max_iterations=1)
    assert result.iterations_completed == 1 and result.stage_b_evaluations == 1
    candidate = result.history[0].candidate
    baseline = cold().generate([], None, {})
    assert normalized(candidate) == pytest.approx(normalized(baseline)[::-1])
    ref, payload = evaluator.observed[0]
    fresh = artifacts.FileSystemCAS(store.root)
    readback = canon.from_canonical_bytes(fresh.get_verified_snapshot(ref).data)
    assert readback == payload
    assert readback["metadata"]["sensitivity"]["analysis_ref"] == answer["analysis_ref"].model_dump(
        mode="json"
    )
    assert candidate["_sensitivity"]["analysis_id"] == answer["result"].metadata["analysis_id"]
    assert generator.get_state()["config"]["sensitivity_order"]["analysis_ref"] == answer[
        "analysis_ref"
    ].model_dump(mode="json")


@pytest.mark.parametrize("selection", [None, "sha256:" + "0" * 64])
def test_unselected_or_forged_manifest_ref_cannot_activate_native_order(tmp_path, selection):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    answer = analysis(store)
    malformed = answer["analysis_ref"].model_copy(update={"manifest_profile_sha256": selection})
    generator = cold()
    before = generator.get_state()
    with pytest.raises((ValueError, artifacts.ArtifactIntegrityError)):
        SensitivityAwareCandidateGenerator.from_artifact(generator, store, malformed)
    assert generator.get_state() == before
    assert generator._optimizer._model is None


def test_same_source_revalidation_preserves_active_stream_and_changed_source_refuses(tmp_path):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    original = analysis(store, dominant="z")
    changed = analysis(store, dominant="x")
    adapter = SensitivityAwareCandidateGenerator.from_artifact(
        cold(), store, original["analysis_ref"]
    )
    adapter.generate([], None, {})
    before = adapter.get_state()
    repeated = SensitivityAwareCandidateGenerator.from_artifact(
        adapter, store, original["analysis_ref"]
    )
    assert repeated.get_state() == before
    with pytest.raises(ValueError, match="precede"):
        SensitivityAwareCandidateGenerator.from_artifact(adapter, store, changed["analysis_ref"])
    assert adapter.get_state() == before
