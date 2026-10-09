from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, ClassVar

import pytest
from pydantic import ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodRegistry,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    ChampionRegistry,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopRunner,
    SearchLoopSpec,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import load_json_artifact, load_model_artifact
from polisyos.scientist.methods.autotune.runtime import (
    MethodJobBenchmarkEvaluator,
    PydanticMutationCodec,
)
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)


class _V5Mutation(MutationArtifact):
    model_config = ConfigDict(extra="forbid")

    loop_id: str = "v5_search"
    value: float = Field(default=0.0)


class _V5ScoreMethod:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="v5_score",
        namespace="tests.scientist",
        version="1.0.0",
        input_slots=frozenset({SlotSpec("value", SlotType.SCALAR, Unit("dimensionless", "1"))}),
        output_slots=frozenset({SlotSpec("score", SlotType.SCALAR, Unit("dimensionless", "1"))}),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="V5 test scoring method")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, float]:
        del params
        return {"score": float(state["value"])}


class _V5VectorIndex:
    dim = 1

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}

    def add(self, *, key: str, embedding: list[float], metadata: dict[str, Any]) -> None:
        del embedding
        self._records[key] = dict(metadata)

    def query(
        self,
        embedding: list[float],
        top_k: int,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        del embedding
        return [(key, 0.0, dict(meta)) for key, meta in list(self._records.items())[:top_k]]


@pytest.fixture(autouse=True)
def _reset_method_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _policy(*, metric: str = "score") -> PromotionPolicy:
    return PromotionPolicy(
        loop_id="v5_search",
        primary_metric=metric,
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
        min_sample_count=1,
    )


def _register_method() -> None:
    MethodRegistry.get_instance().register(_V5ScoreMethod, override=True)


def _persist_inputs(store: FileSystemCAS) -> tuple[ArtifactRef, ArtifactRef]:
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_suite", kind="method_job"),
    )
    candidate_ref = persist_mutation_artifact(
        store,
        _V5Mutation(value=0.25),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )
    return candidate_ref, suite_ref


def test_method_job_evaluator_uses_real_runner_and_returns_cas_provenance(tmp_path) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref, suite_ref = _persist_inputs(store)
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        candidate_input_bindings={"value": "value"},
        split=BenchmarkSplit.SELECTION,
    )

    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {
            "store": store,
            "policy": _policy(),
            "loop_id": "v5_search",
        },
    )

    assert evaluation.selection_metrics == {"score": 0.25}
    assert evaluation.promotable is False
    assert evaluation.method_result_ref is not None
    assert evaluation.method_evidence_ref is not None
    reader = FileSystemCAS(tmp_path / "cas")
    assert load_json_artifact(reader, evaluation.method_result_ref) == {"score": 0.25}
    evidence = from_canonical_bytes(reader.get_bytes(evaluation.method_evidence_ref.artifact_id))
    assert evidence["authority_purpose"] == "method_execution"
    assert evidence["may_not_use_for"] == ["governance_admissibility", "method_validity"]


def test_search_runner_preserves_bayesian_payload_and_fresh_reads_job_chain(tmp_path) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=2,
        seed=17,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5ScoreMethod.signature.fqn,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(),
    )
    context = {"policy_context": {"year": 2030, "unit": "dimensionless"}}
    original_context = {"policy_context": dict(context["policy_context"])}

    result = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        context=context,
        max_iterations=1,
    )

    assert generator.botorch_available is True
    assert context == original_context
    assert result.history
    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    simulation = stage_b["simulation_results"]
    fresh_reader = FileSystemCAS(tmp_path / "cas")
    evaluation = load_model_artifact(
        fresh_reader,
        simulation["evaluation_ref"],
        BenchmarkEvaluation,
    )
    assert evaluation.selection_metrics["score"] == result.history[0].candidate["value"]
    assert evaluation.method_result_ref is not None
    assert evaluation.method_evidence_ref is not None
    assert evaluation.search_source_profile is not None
    assert evaluation.search_source_profile.profile_kind == "configured_native_gp"
    assert evaluation.search_source_profile.gp_model_fqn is None
    assert evaluation.search_source_profile.warm_start_eligible is False
    assert evaluation.search_source_profile.search_space_fingerprint
    assert evaluation.search_source_profile.context_fingerprint
    assert evaluation.search_source_profile.training_corpus_fingerprint is None
    assert evaluation.search_source_profile.training_observation_count is None
    assert load_json_artifact(fresh_reader, evaluation.method_result_ref) == {
        "score": result.history[0].candidate["value"]
    }
    assert result.history[0].candidate["_strategy_metadata"]["source"] == "sobol_init"
    manifest = fresh_reader.get_manifest(simulation["evaluation_ref"])
    assert {item.role for item in manifest.inputs} >= {
        "candidate",
        "benchmark_suite",
        "method_result",
        "method_evidence",
    }
    assert registry.get("v5_search") is None

    # The actual persisted method result can be admitted to transfer discovery. Its
    # source profile captures the source context and a cold-start (unfit) GP state.
    source_evaluations = generator._history_to_evaluations(result.history)
    assert len(source_evaluations) == 1
    source_evaluation = source_evaluations[0]
    assert source_evaluation.is_valid
    assert source_evaluation.provenance_ref == str(evaluation.method_result_ref.artifact_id)
    transfer = TransferLearningManager(store, _V5VectorIndex())
    source_fingerprint = RunFingerprint(
        run_id="v5-source-run",
        space_hash=generator._search_space._native.sobol_space_fingerprint(),
        objective_names=["score"],
        bounds={"value": {"lower": 0.0, "upper": 1.0}},
        split=BenchmarkSplit.SELECTION.value,
        units={},
        origin="v5-methodjob-test",
        objective_directions={"score": "minimize"},
        embedding=[1.0],
        num_evaluations=1,
    )
    assert transfer.register_run(source_fingerprint, source_evaluations) is not None
    target_generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=2,
        seed=23,
    )
    target_spec = replace(spec, candidate_generator=target_generator)
    target_fingerprint = source_fingerprint.model_copy(update={"run_id": "v5-target-run"})
    bridge = WarmStartBridge(transfer)
    transferred = bridge.load_warm_start(target_fingerprint)
    assert len(transferred) == 1
    assert transferred[0].is_valid, transferred[0].metadata
    # The source did not yet fit a GP, so its measured compatibility fields are absent
    # and the receiver declines it before context or model admission.
    target_result = SearchLoopRunner(store=store, registry=registry).run(
        target_spec,
        suite_ref=suite_ref,
        context={"policy_context": {"year": 2031, "unit": "dimensionless"}},
        max_iterations=1,
        warm_start_bridge=bridge,
        warm_start_fingerprint=target_fingerprint,
    )
    assert target_result.history
    assert target_generator._warm_start_rejections[-1]["reason"] == (
        "missing or incompatible warm-start fingerprint"
    )
    assert not target_generator._optimizer._warm_evals

    same_context_generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=2,
        seed=29,
    )
    same_context_result = SearchLoopRunner(store=store, registry=registry).run(
        replace(spec, candidate_generator=same_context_generator),
        suite_ref=suite_ref,
        context=original_context,
        max_iterations=1,
        warm_start_bridge=bridge,
        warm_start_fingerprint=target_fingerprint,
    )
    assert same_context_result.history
    assert same_context_generator._warm_start_rejections[-1]["reason"] == (
        "missing or incompatible warm-start fingerprint"
    )
    assert not same_context_generator._optimizer._warm_evals


@pytest.mark.skipif(
    os.environ.get("POLISYOS_RUN_NATIVE_GP_HEAVY") != "1",
    reason="reserved single native GP fit slot",
)
def test_fitted_native_gp_profile_round_trips_into_same_context_search(tmp_path) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_native_gp_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=3,
        seed=31,
    )
    generator._optimizer._config.num_restarts = 1
    generator._optimizer._config.raw_samples = 16
    generator._optimizer._config.refit_interval = 1
    policy = _policy()
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5ScoreMethod.signature.fqn,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=policy,
    )
    source_context = {"policy_context": {"year": 2032, "unit": "dimensionless"}}
    original_context = {"policy_context": dict(source_context["policy_context"])}
    source_result = SearchLoopRunner(store=store, registry=registry).run(
        spec,
        suite_ref=suite_ref,
        context=source_context,
        max_iterations=4,
    )

    assert source_context == original_context
    assert generator._optimizer._model is not None
    assert source_result.history[-1].candidate["_strategy_metadata"]["source"] == (
        "bayesian_acquisition"
    )
    source_stage_b = source_result.history[-1].stage_b_result
    assert source_stage_b is not None
    source_evaluation_ref = source_stage_b["simulation_results"]["evaluation_ref"]
    source_reader = FileSystemCAS(tmp_path / "cas")
    source_evaluation = load_model_artifact(
        source_reader,
        source_evaluation_ref,
        BenchmarkEvaluation,
    )
    source_profile = source_evaluation.search_source_profile
    assert source_profile is not None
    assert source_profile.profile_kind == "configured_native_gp"
    assert source_profile.gp_model_fqn == "botorch.models.gp_regression.SingleTaskGP"
    assert source_profile.input_transform_fingerprint == "Normalize[0,1]"
    assert source_profile.input_transform_state_fingerprint
    assert source_profile.outcome_transform_fingerprint == "Standardize[m=1]"
    assert source_profile.outcome_transform_state_fingerprint
    assert source_profile.noise_model_fingerprint == "GaussianLikelihood[inferred]"
    assert source_profile.noise_model_state_fingerprint
    assert source_profile.warm_start_eligible is True
    assert source_profile.training_observation_count == 3
    assert source_profile.context_fingerprint == generator._search_run_context_fingerprint
    source_manifest = source_reader.get_manifest(source_evaluation_ref)
    assert {item.role for item in source_manifest.inputs} >= {
        "candidate",
        "benchmark_suite",
        "method_result",
        "method_evidence",
    }

    source_evaluations = generator._history_to_evaluations(source_result.history)
    transfer = TransferLearningManager(store, _V5VectorIndex())
    source_fingerprint = RunFingerprint(
        run_id="v5-native-source-run",
        space_hash=generator._search_space._native.sobol_space_fingerprint(),
        objective_names=[policy.primary_metric],
        bounds={"value": {"lower": 0.0, "upper": 1.0}},
        split=BenchmarkSplit.SELECTION.value,
        units={},
        origin="v5-native-methodjob-test",
        objective_directions={policy.primary_metric: policy.direction.value},
        embedding=[1.0],
        num_evaluations=len(source_evaluations),
    )
    assert transfer.register_run(source_fingerprint, source_evaluations) is not None
    target_generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=3,
        seed=37,
    )
    target_generator._optimizer._config.num_restarts = 1
    target_generator._optimizer._config.raw_samples = 16
    target_fingerprint = source_fingerprint.model_copy(update={"run_id": "v5-native-target-run"})
    bridge = WarmStartBridge(transfer)
    transferred_profiles = bridge.load_warm_start(target_fingerprint)
    fitted_source_ids = {
        evaluation.candidate_id
        for evaluation in transferred_profiles
        if evaluation.metadata.get("warm_start_compatibility", {}).get("warm_start_eligible")
        is True
    }
    assert len(fitted_source_ids) == 1
    training_candidate_ids: list[list[str]] = []
    prepare_training_data = target_generator._optimizer._prepare_training_data

    def observe_training_data(evaluations):
        training_candidate_ids.append([evaluation.candidate_id for evaluation in evaluations])
        return prepare_training_data(evaluations)

    target_generator._optimizer._prepare_training_data = observe_training_data
    target_result = SearchLoopRunner(store=store, registry=registry).run(
        replace(spec, candidate_generator=target_generator),
        suite_ref=suite_ref,
        context=original_context,
        max_iterations=3,
        warm_start_bridge=bridge,
        warm_start_fingerprint=target_fingerprint,
    )

    assert target_result.history
    assert target_generator._warm_start_accepted_count == 1
    assert len(target_generator._optimizer._warm_evals) == 1
    assert len(target_generator._warm_start_rejections) == 3
    assert len(training_candidate_ids) == 1
    assert fitted_source_ids.issubset(set(training_candidate_ids[0]))
    assert len(training_candidate_ids[0]) == 3
    assert target_result.history[-1].candidate["_strategy_metadata"]["source"] == (
        "bayesian_acquisition"
    )
    target_stage_b = target_result.history[-1].stage_b_result
    assert target_stage_b is not None
    target_evaluation = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"),
        target_stage_b["simulation_results"]["evaluation_ref"],
        BenchmarkEvaluation,
    )
    assert target_evaluation.search_source_profile is not None
    assert target_evaluation.search_source_profile.training_observation_count == 3
    assert target_evaluation.search_source_profile.warm_start_eligible is True
    assert target_evaluation.search_source_profile.context_fingerprint == (
        source_profile.context_fingerprint
    )


def test_missing_primary_metric_is_not_promoted_as_zero(tmp_path) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_suite", kind="method_job"),
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=BayesianCandidateGenerator(
            SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
            n_initial=2,
            seed=3,
        ),
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5ScoreMethod.signature.fqn,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(metric="budget_deficit"),
    )

    result = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        max_iterations=1,
    )

    assert result.history
    assert result.history[0].objective_value == float("inf")
    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    assert "budget_deficit" not in stage_b["simulation_results"]
    evaluation = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"),
        stage_b["simulation_results"]["evaluation_ref"],
        BenchmarkEvaluation,
    )
    assert evaluation.selection_metrics == {}
    assert evaluation.promotable is False
    assert evaluation.status == "metric_unavailable"
