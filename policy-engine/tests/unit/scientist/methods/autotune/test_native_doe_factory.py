"""Ordinary configured factory, strict typed mutation, actual DOE and durable native caller."""

from dataclasses import replace

import pytest

pytest.importorskip("SALib", reason="UNRUN: actual DOE backend required", exc_type=ImportError)
pytest.importorskip("torch", reason="UNRUN: native Sobol backend required", exc_type=ImportError)
pytest.importorskip("botorch", reason="UNRUN: native receiver required", exc_type=ImportError)
pytest.importorskip("gpytorch", reason="UNRUN: native receiver required", exc_type=ImportError)

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
    assert value.botorch_available, "native backend unavailable after required optional imports"
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
    native_id = f"{fresh.controller._run_state.search_id}:{actual.candidate_id}"
    assert actual.payload["_strategy_metadata"]["candidate_id"] == native_id
    assert saved["configuration"]["candidate_identity_profile"] == "native_service_run_candidate.v1"
    resumed_evaluation = fresh.controller._evaluate_for_tell(
        actual.payload, iteration=1, context={}
    )
    fresh.tell(actual.candidate_id, resumed_evaluation)
    consumed = fresh.controller._generator._base._history_to_evaluations(fresh.controller._history)
    assert len(consumed) == 2 and consumed[-1].candidate_id == native_id
    reopened_store = FileSystemCAS(tmp_path / "cas")
    reopened = SearchLoopRunner(
        store=reopened_store,
        registry=ChampionRegistry(tmp_path / "registry", store=reopened_store),
    ).create_service(_spec(answer), suite_ref=suite, max_iterations=3)
    reopened.restore(fresh.checkpoint_ref)
    assert reopened.controller._history == fresh.controller._history
    reopened_consumed = reopened.controller._generator._base._history_to_evaluations(
        reopened.controller._history
    )
    assert [item.candidate_id for item in reopened_consumed] == [
        item.candidate_id for item in consumed
    ]
    assert fresh.controller._generator._base._optimizer._model is None
    print(
        "actual_doe_checkpoint",
        fresh.checkpoint_ref.model_dump(mode="json"),
        configured,
        [item.candidate_id for item in reopened_consumed],
    )


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


@pytest.mark.parametrize("carrier", ["pending", "history", "best", "frontier"])
def test_changed_native_subject_in_actual_checkpoint_refuses_before_live_effect(tmp_path, carrier):
    from polisyos.core.artifacts import SchemaInfo
    from polisyos.core.artifacts.manifest_profile import artifact_manifest_profile_sha256
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec

    store = FileSystemCAS(tmp_path / "cas")
    answer, suite = _analysis(store), _suite(store)
    runner = SearchLoopRunner(
        store=store, registry=ChampionRegistry(tmp_path / "registry", store=store)
    )
    source = runner.create_service(_spec(answer), suite_ref=suite, max_iterations=3)
    first = source.ask(None, None, {})[0]
    source.tell(
        first.candidate_id,
        source.controller._evaluate_for_tell(first.payload, iteration=0, context={}),
    )
    source.ask(None, None, {})
    original = store.get_verified_snapshot(source.checkpoint_ref)
    payload = from_canonical_bytes(original.data)
    if carrier == "pending":
        candidate = payload["pending_candidates"]["candidate_1_0"]
    elif carrier == "history":
        candidate = payload["run_state"]["history"][0]["candidate"]
    elif carrier == "best":
        candidate = payload["run_state"]["best_candidate"]
    else:
        candidate = payload["run_state"]["pareto_points"][0]["candidate"]
    candidate["_strategy_metadata"]["candidate_id"] = "other_run:candidate_1_0"
    bad = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=original.manifest.kind,
            media_type=original.manifest.media_type,
            schema=SchemaInfo(name=original.manifest.artifact_schema.name, version="2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    bad = bad.model_copy(
        update={
            "manifest_profile_sha256": artifact_manifest_profile_sha256(
                store.get_verified_snapshot(bad).manifest
            )
        }
    )
    fresh_store = FileSystemCAS(tmp_path / "cas")
    target = SearchLoopRunner(
        store=fresh_store, registry=ChampionRegistry(tmp_path / "registry", store=fresh_store)
    ).create_service(_spec(answer), suite_ref=suite, max_iterations=3)
    before = target.controller._generator.get_state()
    print("actual_changed_native_subject", carrier, bad.model_dump(mode="json"), payload)
    with pytest.raises(ValueError, match="search_resume_native_candidate_identity"):
        target.restore(bad)
    assert target.controller._run_state.search_id == ""
    assert target.controller._history == []
    assert target._pending_candidates == {}
    assert target.checkpoint_ref is None
    assert target.controller._generator.get_state() == before


@pytest.mark.parametrize("changed_ref", ["missing", "different"])
def test_actual_resolved_analysis_return_ref_cannot_change_before_factory_publication(
    tmp_path, monkeypatch, changed_ref
):
    from hashlib import sha256

    from polisyos.scientist.methods.search.sensitivity_adapter import (
        SensitivityAwareCandidateGenerator,
    )

    store = FileSystemCAS(tmp_path / "cas")
    answer, suite = _analysis(store), _suite(store)
    spec = _spec(answer)
    resolved = []
    actual_resolver = SensitivityAwareCandidateGenerator.from_artifact.__func__

    def changed_resolver(cls, base, actual_store, ref, **kwargs):
        configured = actual_resolver(cls, base, actual_store, ref, **kwargs)
        assert configured.analysis_ref == answer["analysis_ref"]
        assert configured.order_profile == "exploratory_coordinate_order.v1"
        resolved.append((configured, configured.get_state()))
        configured._analysis_ref = None if changed_ref == "missing" else suite
        return configured

    def cas_bytes():
        return {
            str(path.relative_to(tmp_path / "cas")): sha256(path.read_bytes()).hexdigest()
            for path in (tmp_path / "cas").rglob("*")
            if path.is_file()
        }

    before = cas_bytes()
    monkeypatch.setattr(
        SensitivityAwareCandidateGenerator, "from_artifact", classmethod(changed_resolver)
    )
    with pytest.raises(ValueError, match="search_analysis_artifact_ref_configuration_mismatch"):
        SearchLoopRunner(store=store).create_service(spec, suite_ref=suite)
    assert len(resolved) == 1
    configured, configured_state = resolved[0]
    assert configured.get_state() == configured_state
    assert configured_state["activity_started"] is False
    assert configured_state["history_rows"] == []
    assert configured._base._optimizer._model is None
    assert cas_bytes() == before
    print(
        "actual_analysis_return_ref_refusal",
        changed_ref,
        answer["analysis_ref"].model_dump(mode="json"),
        configured.analysis_ref.model_dump(mode="json") if configured.analysis_ref else None,
        sorted(before),
    )
