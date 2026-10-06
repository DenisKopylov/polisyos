"""Ordinary configured factory, strict typed mutation, actual DOE and durable native caller."""

from dataclasses import replace

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
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
    load_model_artifact,
    persist_benchmark_suite,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.runtime import PydanticMutationCodec, SearchLoopRunner
from polisyos.scientist.methods.autotune.sensitivity_bridge import SensitivityBridge


class _Mutation(MutationArtifact):
    x: float
    z: float


class _Evaluator:
    def checkpoint_configuration(self):
        return {"formula": "100*z+x", "unit": "synthetic_score", "version": 1}

    def evaluate(self, candidate_ref, suite_ref, context):
        candidate = load_model_artifact(context["store"], candidate_ref, _Mutation)
        return BenchmarkEvaluation(
            loop_id="native-doe",
            suite_id="native-coordinate-experiment",
            candidate_ref=candidate_ref,
            selection_metrics={"score": 100 * candidate.z + candidate.x},
            sample_counts={"selection": 1},
            guardrails={"finite": True},
            runtime_split_type=BenchmarkSplit.SELECTION,
            promotable=True,
        )


def _bounds():
    return [
        {"name": "x", "lower": -2.0, "upper": 2.0, "unit": "metres"},
        {"name": "z", "lower": 10.0, "upper": 20.0, "unit": "seconds"},
    ]


def _generator():
    value = BayesianCandidateGenerator(
        SearchSpace(_bounds()),
        primary_metric="score",
        direction=MetricDirection.MINIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
        seed=31,
    )
    assert value.botorch_available, "UNRUN: actual native backend unavailable"
    return value


def _analysis(store):
    actual = []

    def evaluate(params):
        actual.append(dict(params))
        return 100 * params["z"] + params["x"]

    answer = SensitivityBridge().analyze_search_space(
        _bounds(), evaluate, n_trajectories=8, seed=31, store=store
    )
    assert len(actual) == answer["result"].total_runs == 24
    assert answer["ranking"] == ["z", "x"]
    assert answer["analysis_ref"].manifest_profile_sha256
    return answer


def _spec(answer, *, metadata=True):
    return SearchLoopSpec(
        loop_id="native-doe",
        mutation_codec=PydanticMutationCodec(_Mutation),
        candidate_generator=_generator(),
        benchmark_evaluator=_Evaluator(),
        promotion_policy=PromotionPolicy(
            loop_id="native-doe",
            primary_metric="score",
            unit="synthetic_score",
            direction=MetricDirection.MINIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            required_guardrails=["finite"],
        ),
        metadata={
            "analysis_ref": answer["analysis_ref"].model_dump(mode="json"),
            "analysis_order_profile": "exploratory_coordinate_order.v1",
            "analysis_purpose": "exploratory",
        }
        if metadata
        else {},
    )


def _suite(store):
    return persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="native-coordinate-experiment", kind="analytic", data_basis="candidate_only"
        ),
    )


def _coordinates(payload):
    return ((payload["x"] + 2) / 4, (payload["z"] - 10) / 10)


def test_ordinary_spec_metadata_changes_actual_proposal_and_typed_persisted_consumer(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    answer = _analysis(store)
    spec = _spec(answer)
    ordinary = _generator().generate([], None, {})
    suite = _suite(store)
    runner = SearchLoopRunner(
        store=store, registry=ChampionRegistry(tmp_path / "registry", store=store)
    )
    result = runner.run(spec, suite_ref=suite, max_iterations=1)
    assert result.iterations_completed == result.stage_b_evaluations == 1
    row = result.history[0]
    assert _coordinates(row.candidate) == pytest.approx(_coordinates(ordinary)[::-1])
    assert _coordinates(row.candidate) != pytest.approx(_coordinates(ordinary))
    assert row.candidate["_sensitivity"]["ranking_consumer"] == "native_coordinate_order"
    refs = row.stage_b_result["simulation_results"]
    from polisyos.core.artifacts import ArtifactRef

    candidate_ref = ArtifactRef.model_validate(refs["candidate_artifact_ref"])
    evaluation_ref = ArtifactRef.model_validate(refs["evaluation_artifact_ref"])
    candidate = load_model_artifact(store, candidate_ref, _Mutation)
    evaluation = load_model_artifact(store, evaluation_ref, BenchmarkEvaluation)
    assert candidate.loop_id == "native-doe"
    assert candidate.x == row.candidate["x"] and candidate.z == row.candidate["z"]
    assert evaluation.selection_metrics == {"score": 100 * candidate.z + candidate.x}
    for ref in (candidate_ref, evaluation_ref):
        inputs = store.get_verified_snapshot(ref).manifest.inputs
        selected = [item for item in inputs if item.role == "sensitivity_analysis"]
        assert len(selected) == 1
        assert selected[0].artifact_id == answer["analysis_ref"].artifact_id
        assert selected[0].manifest_profile_sha256 == answer["analysis_ref"].manifest_profile_sha256
    fresh_store = FileSystemCAS(tmp_path / "cas")
    fresh = SearchLoopRunner(
        store=fresh_store, registry=ChampionRegistry(tmp_path / "registry", store=fresh_store)
    ).resume(
        _spec(answer),
        suite_ref=suite,
        checkpoint_ref=ArtifactRef.model_validate(result.telemetry["checkpoint_ref"]),
        max_iterations=1,
    )
    assert fresh.history == result.history
    assert fresh.best_candidate == result.best_candidate
    assert fresh.pareto_front == result.pareto_front
    assert spec.candidate_generator._optimizer._model is None
    print("actual_doe_typed_consumer", refs, answer["analysis_ref"].model_dump(mode="json"))


def test_fresh_configured_public_factory_preserves_next_proposal_and_exact_analysis(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    answer, suite = _analysis(store), _suite(store)
    runner = SearchLoopRunner(
        store=store, registry=ChampionRegistry(tmp_path / "registry", store=store)
    )
    source = runner.create_service(_spec(answer), suite_ref=suite, max_iterations=3)
    first = source.ask(None, None, {})[0]
    evaluation = source.controller._evaluate_for_tell(first.payload, iteration=0, context={})
    source.tell(first.candidate_id, evaluation)
    acknowledged = source.checkpoint_ref
    expected = source.ask(None, None, {})[0]
    fresh_store = FileSystemCAS(tmp_path / "cas")
    fresh = SearchLoopRunner(
        store=fresh_store, registry=ChampionRegistry(tmp_path / "registry", store=fresh_store)
    ).create_service(_spec(answer), suite_ref=suite, max_iterations=3)
    fresh.restore(acknowledged)
    actual = fresh.ask(None, None, {})[0]
    print("actual_next_action", actual.model_dump(mode="json"))
    print("expected_next_action", expected.model_dump(mode="json"))
    assert actual == expected
    assert fresh.controller._history == source.controller._history
    saved = from_canonical_bytes(fresh_store.get_verified_snapshot(fresh.checkpoint_ref).data)
    configured = saved["configuration"]["basis"]["analysis_configuration"]
    assert configured["analysis_ref"] == answer["analysis_ref"].model_dump(mode="json")
    assert configured["order_profile"] == "exploratory_coordinate_order.v1"
    assert configured["purpose"] == "exploratory"
    assert fresh.controller._generator._base._optimizer._model is None
    print("actual_doe_checkpoint", fresh.checkpoint_ref.model_dump(mode="json"), configured)


@pytest.mark.parametrize(
    "change", ["missing_purpose", "unknown_profile", "unqualified", "non_native"]
)
def test_invalid_factory_analysis_configuration_refuses_before_native_activity(tmp_path, change):
    store = FileSystemCAS(tmp_path / "cas")
    answer, suite = _analysis(store), _suite(store)
    spec = _spec(answer)
    before = spec.candidate_generator.get_state()
    if change == "missing_purpose":
        spec.metadata.pop("analysis_purpose")
    elif change == "unknown_profile":
        spec.metadata["analysis_order_profile"] = "unknown"
    elif change == "unqualified":
        spec.metadata["analysis_ref"]["manifest_profile_sha256"] = None
    else:
        from polisyos.scientist.methods.autotune.runtime import SequenceCandidateGenerator

        spec = replace(spec, candidate_generator=SequenceCandidateGenerator([{"x": 0, "z": 10}]))
        before = spec.candidate_generator.get_state()
    with pytest.raises(ValueError):
        SearchLoopRunner(store=store).create_service(spec, suite_ref=suite)
    assert spec.candidate_generator.get_state() == before


def test_meaningful_or_forged_native_payload_is_not_dropped_by_typed_projection(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    answer, suite = _analysis(store), _suite(store)
    spec = _spec(answer)
    runner = SearchLoopRunner(store=store)
    service = runner.create_service(spec, suite_ref=suite)
    generated = service.ask(None, None, {})[0].payload
    effective = replace(spec, candidate_generator=service.controller._generator)
    meaningful = {**generated, "semantic": {"interventions": [{"type": "actual_policy_change"}]}}
    with pytest.raises(ValueError):
        runner._evaluate_candidate(
            effective, suite_ref=suite, candidate_payload=meaningful, context={}
        )
    forged = {**generated, "_sensitivity": {**generated["_sensitivity"], "ranking": ["x", "z"]}}
    with pytest.raises(ValueError, match="sensitivity_configuration_mismatch"):
        runner._evaluate_candidate(effective, suite_ref=suite, candidate_payload=forged, context={})
    unknown = {**generated, "unexpected_mutation_field": 1}
    with pytest.raises(ValueError):
        runner._evaluate_candidate(
            effective, suite_ref=suite, candidate_payload=unknown, context={}
        )
