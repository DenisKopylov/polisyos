from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic import ConfigDict, Field

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactManifest,
    CoreJSONArtifactStore,
    VerificationReport,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodRegistry,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.scientist.compute.job_spec import JobSpec
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
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import (
    SearchGPFitBasis,
    SearchGPProposalUncertainty,
    load_json_artifact,
    load_model_artifact,
)
from polisyos.scientist.methods.autotune.registry import _methodjob_source_admission_failure
from polisyos.scientist.methods.autotune.runtime import (
    MethodJobBenchmarkEvaluator,
    PydanticMutationCodec,
    SequenceCandidateGenerator,
    _build_search_method_run_profile,
    _default_core_json_store,
    _method_request_matches_search_run_profile,
    _persist_search_benchmark_evaluation,
    _search_source_fingerprint,
    _verify_search_source_profile_receipt,
)
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.objective import (
    OptimizationDirection,
    _configured_search_metric_rule_spec,
)
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)


class _V5Mutation(MutationArtifact):
    model_config = ConfigDict(extra="forbid")

    loop_id: str = "v5_search"
    value: float = Field(default=0.0)


class _V5ParameterMutation(_V5Mutation):
    method_offset: float = Field(default=0.0)


class _V5ScoreMethod:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="v5_score",
        namespace="tests.scientist",
        version="1.0.0",
        input_slots=frozenset({SlotSpec("value", SlotType.SCALAR, Unit("dimensionless", "1"))}),
        output_slots=frozenset({SlotSpec("score", SlotType.SCALAR, Unit("dimensionless", "1"))}),
        parameters=(ParameterSpec(name="offset", default=0.0),),
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
        return {"score": float(state["value"]) + float(params.get("offset", 0.0))}


class _V5NativeGPScoreMethod(_V5ScoreMethod):
    """Controlled MethodJob producer with an explicit Search metric unit."""

    signature: ClassVar[MethodSignature] = replace(
        _V5ScoreMethod.signature,
        name="v5_native_gp_score",
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "score": float(state["value"]) + float(params.get("offset", 0.0)),
            "metric_units": {"score": "dimensionless"},
        }


class _V5DeclaredUnitScoreMethod(_V5ScoreMethod):
    """Controlled method whose reported unit can be checked against run config."""

    signature: ClassVar[MethodSignature] = replace(
        _V5ScoreMethod.signature,
        name="v5_declared_unit_score",
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "score": float(state["value"]) + float(params.get("offset", 0.0)),
            "metric_units": {"score": "USD per resident"},
        }


class _V5MechanicalAdmissionScoreMethod(_V5ScoreMethod):
    """Controlled test producer for the candidate-to-registry wiring only."""

    signature: ClassVar[MethodSignature] = replace(
        _V5ScoreMethod.signature,
        name="v5_mechanical_admission_score",
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "score": float(state["value"]) + float(params.get("offset", 0.0)),
            "sample_counts": {"selection": 1},
        }


class _V5NoInputScoreMethod(_V5ScoreMethod):
    signature: ClassVar[MethodSignature] = replace(
        _V5ScoreMethod.signature,
        name="v5_no_input_score",
        input_slots=frozenset(),
    )

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, float]:
        del state, params
        return {"score": 0.5}


class _V5ScoreMethodV2(_V5ScoreMethod):
    signature: ClassVar[MethodSignature] = replace(_V5ScoreMethod.signature, version="2.0.0")


class _V5ScoreMethodChangedAbi(_V5ScoreMethod):
    signature: ClassVar[MethodSignature] = replace(
        _V5ScoreMethod.signature,
        parameters=(ParameterSpec(name="offset", default=0.0, bounds=(0.0, 1.0)),),
    )


class _V5StaticScoreMethod(_V5ScoreMethod):
    signature: ClassVar[MethodSignature] = replace(
        _V5ScoreMethod.signature,
        parameters=(ParameterSpec(name="offset", default=0.0, is_static=True),),
    )


class _V5DefaultlessScoreMethod(_V5ScoreMethod):
    signature: ClassVar[MethodSignature] = replace(
        _V5ScoreMethod.signature,
        parameters=(ParameterSpec(name="offset", default=None, bounds=(-0.5, 0.5)),),
    )


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


def _policy(*, metric: str = "score", unit: str | None = None) -> PromotionPolicy:
    return PromotionPolicy(
        loop_id="v5_search",
        primary_metric=metric,
        unit=unit,
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


def test_method_only_job_computes_candidate_but_holds_unverified_promotion(tmp_path) -> None:
    """Persisted dispatch facts remain candidate evidence without executor custody."""
    MethodRegistry.get_instance().register(_V5MechanicalAdmissionScoreMethod, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="v5_method_only_suite",
            suite_version="1.0",
            kind="method_job",
        ),
    )
    assert suite_ref.manifest_profile_sha256 is not None
    suite_manifest = store.get_manifest(suite_ref)
    assert suite_manifest.inputs == []

    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=BayesianCandidateGenerator(
            SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
            n_initial=2,
            seed=20261015,
        ),
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5MechanicalAdmissionScoreMethod.signature.fqn,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(),
    )
    result = SearchLoopRunner(store=store, registry=registry).run(
        spec,
        suite_ref=suite_ref,
        initial_candidate={"loop_id": "v5_search", "value": 0.4},
        max_iterations=1,
    )
    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    evaluation_ref = _selected_evaluation_ref(stage_b)
    reader = FileSystemCAS(tmp_path / "cas")
    evaluation = load_model_artifact(reader, evaluation_ref, BenchmarkEvaluation)
    assert isinstance(evaluation, BenchmarkEvaluation)
    assert evaluation.status == "measured_candidate", evaluation.notes
    assert evaluation.selection_metrics["score"] == 0.4
    assert "methodjob_execution_provenance_not_established" in evaluation.notes
    assert evaluation.method_result_ref is not None
    assert evaluation.method_evidence_ref is not None
    method_evidence = load_json_artifact(reader, evaluation.method_evidence_ref)
    assert isinstance(method_evidence, dict)
    dispatch_binding = method_evidence["method_dispatch_binding"]
    assert dispatch_binding["schema_version"] == "1.2"
    assert dispatch_binding["input_state_fingerprints"]["value"]["shape"] == []
    candidate_manifest = reader.get_manifest(evaluation.candidate_ref)
    assert candidate_manifest.producer is not None
    assert candidate_manifest.producer.component == (
        "polisyos.scientist.methods.autotune.mutation_artifact"
    )
    request_basis = evaluation.metadata["method_request_basis"]
    assert request_basis["data_snapshot_bindings"] == {}
    assert (
        request_basis["job_spec"]["method_version"]
        == _V5MechanicalAdmissionScoreMethod.signature.version
    )
    assert (
        registry._promotion_binding_failure(
            loop_id="v5_search",
            candidate_ref=evaluation.candidate_ref,
            evaluation=evaluation,
            evaluation_ref=evaluation_ref,
            policy=_policy(),
            suite_ref=suite_ref,
        )
        == "methodjob_execution_provenance_not_established"
    )
    decision = stage_b["feedback"]["promotion_decision"]
    assert decision["promoted"] is False
    assert decision["reason"] == "methodjob_execution_provenance_not_established"
    assert registry.get("v5_search") is None

    incomplete_basis = dict(request_basis)
    incomplete_basis["candidate_input_bindings"] = {}
    incomplete = evaluation.model_copy(
        update={
            "metadata": {
                **evaluation.metadata,
                "method_request_basis": incomplete_basis,
            }
        }
    )
    incomplete_ref = persist_benchmark_evaluation(
        reader,
        incomplete,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    assert (
        registry._promotion_binding_failure(
            loop_id="v5_search",
            candidate_ref=evaluation.candidate_ref,
            evaluation=incomplete,
            evaluation_ref=incomplete_ref,
            policy=_policy(),
            suite_ref=suite_ref,
        )
        == "methodjob_input_slot_binding_mismatch"
    )


@pytest.mark.parametrize("foreign_property", ["producer", "suite_edge"])
def test_same_bytes_foreign_candidate_source_is_held_by_actual_methodjob_admission(
    tmp_path, foreign_property: str
) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="v5_foreign_candidate_suite",
            suite_version="1.0",
            kind="method_job",
        ),
    )
    candidate = _V5Mutation(value=0.4)
    suite_edge = input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")
    canonical_ref = persist_mutation_artifact(
        store,
        candidate,
        inputs=[suite_edge],
        return_selected_profile=True,
    )
    foreign_ref = store.put_json(
        candidate,
        ArtifactWriteOptions(
            kind=f"scientist.autotune.{candidate.loop_id}.candidate",
            media_type="application/json",
            schema=SchemaInfo(
                name=f"polisyos.scientist.methods.autotune.{candidate.__class__.__name__}",
                version=candidate.artifact_version,
            ),
            producer=(
                ProducerInfo(component="tests.foreign_mutation_writer", version="1.0")
                if foreign_property == "producer"
                else ProducerInfo(
                    component="polisyos.scientist.methods.autotune.mutation_artifact",
                    version="1.0",
                )
            ),
            inputs=([suite_edge] if foreign_property == "producer" else []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert foreign_ref.artifact_id == canonical_ref.artifact_id
    assert foreign_ref.manifest_profile_sha256 is not None
    assert canonical_ref.manifest_profile_sha256 is not None
    assert foreign_ref.manifest_profile_sha256 != canonical_ref.manifest_profile_sha256

    evaluation = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        candidate_input_bindings={"value": "value"},
        split=BenchmarkSplit.SELECTION,
    ).evaluate(
        foreign_ref,
        suite_ref,
        {"store": store, "policy": _policy(), "loop_id": "v5_search"},
    )
    assert evaluation.method_result_ref is not None
    assert evaluation.method_evidence_ref is not None
    evaluation_ref = persist_benchmark_evaluation(
        store,
        evaluation,
        inputs=[suite_edge],
        return_selected_profile=True,
    )
    assert (
        _methodjob_source_admission_failure(
            store=store,
            candidate_ref=foreign_ref,
            evaluation_ref=evaluation_ref,
            evaluation=evaluation,
            suite_ref=suite_ref,
            policy=_policy(),
        )
        == "methodjob_candidate_source_manifest_mismatch"
    )

    reason = ChampionRegistry(store=store)._promotion_binding_failure(
        loop_id="v5_search",
        candidate_ref=foreign_ref,
        evaluation=evaluation,
        evaluation_ref=evaluation_ref,
        policy=_policy(),
        suite_ref=suite_ref,
    )

    expected_consumer_reason = (
        "suite_basis_mismatch"
        if foreign_property == "suite_edge"
        else "methodjob_candidate_source_manifest_mismatch"
    )
    assert reason == expected_consumer_reason


def test_method_with_zero_registered_input_slots_binds_empty_dispatch_basis(tmp_path) -> None:
    MethodRegistry.get_instance().register(_V5NoInputScoreMethod, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="v5_zero_input_suite",
            suite_version="1.0",
            kind="method_job",
        ),
    )
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    candidate = _V5Mutation(value=0.4)
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=SequenceCandidateGenerator([candidate]),
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5NoInputScoreMethod.signature.fqn,
            candidate_input_bindings={},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(),
    )

    result = SearchLoopRunner(store=store, registry=registry).run(
        spec,
        suite_ref=suite_ref,
        initial_candidate=candidate.model_dump(mode="json"),
        max_iterations=1,
    )

    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    evaluation_ref = _selected_evaluation_ref(stage_b)
    reader = FileSystemCAS(tmp_path / "cas")
    evaluation = load_model_artifact(reader, evaluation_ref, BenchmarkEvaluation)
    assert isinstance(evaluation, BenchmarkEvaluation)
    assert evaluation.status == "measured_candidate", evaluation.notes
    assert evaluation.promotable is False
    assert evaluation.method_evidence_ref is not None
    evidence = load_json_artifact(reader, evaluation.method_evidence_ref)
    assert isinstance(evidence, dict)
    dispatch_binding = evidence["method_dispatch_binding"]
    assert dispatch_binding["schema_version"] == "1.2"
    assert dispatch_binding["input_state_fingerprints"] == {}
    assert (
        registry._promotion_binding_failure(
            loop_id="v5_search",
            candidate_ref=evaluation.candidate_ref,
            evaluation=evaluation,
            evaluation_ref=evaluation_ref,
            policy=_policy(),
            suite_ref=suite_ref,
        )
        == "methodjob_execution_provenance_not_established"
    )


def test_search_profile_readers_require_selected_data_snapshot_owner_schema(tmp_path) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    data_ref = store.put_json(
        {"X": [[0.1], [0.2]]},
        ArtifactWriteOptions(
            kind="scientist.method_dataset",
            media_type="application/json",
            schema=SchemaInfo(name="tests.SearchMethodDataset", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )

    def persist_snapshot(schema_version: str) -> ArtifactRef:
        return store.put_json(
            DataSnapshot(data_ref=data_ref),
            ArtifactWriteOptions(
                kind=DataSnapshot.ARTIFACT_KIND,
                media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                    version=schema_version,
                ),
                inputs=[input_ref_from_artifact_ref(data_ref, role="data_ref")],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    valid_snapshot_ref = persist_snapshot(DataSnapshot.ARTIFACT_SCHEMA_VERSION)
    foreign_schema_snapshot_ref = persist_snapshot("9.0")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="v5_snapshot_schema_suite",
            suite_version="2.0",
            kind="method_job",
            data_snapshot_ref=valid_snapshot_ref,
        ),
    )
    candidate_ref = persist_mutation_artifact(
        store,
        _V5Mutation(value=0.25),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
    )
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        method_version=_V5ScoreMethod.signature.version,
        candidate_input_bindings={},
        data_snapshot_bindings={"value": "X"},
        split=BenchmarkSplit.SELECTION,
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=2,
        seed=101,
    )
    valid_context = {
        "policy_context": {"case": "selected_data_snapshot"},
        "data_snapshot_ref": valid_snapshot_ref,
    }
    generator.set_search_run_context(valid_context)
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=evaluator,
        promotion_policy=_policy(),
    )
    profile = _build_search_method_run_profile(
        store=store,
        generator=generator,
        spec=spec,
        suite_ref=suite_ref,
        context=valid_context,
    )
    assert profile is not None
    assert profile.data_snapshot_ref == valid_snapshot_ref
    assert profile.data_ref == data_ref

    job_spec = JobSpec(
        job_kind="method",
        method_fqn=profile.method_fqn,
        method_version=profile.method_version,
        seed=profile.method_seed,
        input_refs={
            "candidate": candidate_ref,
            "benchmark_suite": suite_ref,
            "data_snapshot": valid_snapshot_ref,
            "data": data_ref,
        },
    )

    def request_receipt(snapshot_ref: ArtifactRef) -> dict[str, object]:
        updated_job_spec = job_spec.model_copy(
            update={
                "input_refs": {
                    **job_spec.input_refs,
                    "data_snapshot": snapshot_ref,
                }
            }
        )
        return {
            "candidate_ref": candidate_ref.model_dump(mode="json"),
            "suite_ref": suite_ref.model_dump(mode="json"),
            "method_request_basis": {
                "schema_version": "1",
                "job_spec": updated_job_spec.model_dump(mode="json", exclude_none=True),
                "candidate_ref": candidate_ref.model_dump(mode="json"),
                "suite_ref": suite_ref.model_dump(mode="json"),
                "candidate_input_bindings": {},
                "data_snapshot_bindings": {"value": "X"},
                "primary_metric": "score",
                "direction": "maximize",
                "split": "selection",
                "unit": None,
            },
        }

    evaluation = BenchmarkEvaluation(
        loop_id=profile.loop_id,
        suite_id="v5_snapshot_schema_suite",
        candidate_ref=candidate_ref,
    )
    valid_receipt = request_receipt(valid_snapshot_ref)
    assert _method_request_matches_search_run_profile(
        reader=FileSystemCAS(tmp_path / "cas"),
        evaluation=evaluation,
        receipt=valid_receipt,
        run_profile=profile,
    )

    foreign_profile = profile.model_copy(update={"data_snapshot_ref": foreign_schema_snapshot_ref})
    foreign_receipt = request_receipt(foreign_schema_snapshot_ref)
    assert not _method_request_matches_search_run_profile(
        reader=FileSystemCAS(tmp_path / "cas"),
        evaluation=evaluation,
        receipt=foreign_receipt,
        run_profile=foreign_profile,
    )


def _selected_evaluation_ref(stage_b: dict[str, Any]) -> ArtifactRef:
    """Read the runtime's full selected evaluation ref, never its legacy bare-ID projection."""
    ref = ArtifactRef.model_validate(stage_b["metadata"]["evaluation_artifact_ref"])
    assert ref.manifest_profile_sha256 is not None
    return ref


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


def test_search_parameter_binding_reaches_real_methodjob_and_fresh_receipt(
    tmp_path, monkeypatch
) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_parameter_binding_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(
            bounds=[
                {"name": "value", "lower": 0.0, "upper": 1.0},
                {"name": "method_offset", "lower": -0.5, "upper": 0.5},
            ]
        ),
        n_initial=2,
        seed=53,
    )
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        method_version=_V5ScoreMethod.signature.version,
        candidate_input_bindings={"value": "value"},
        search_parameter_bindings={"method_offset": "offset"},
        split=BenchmarkSplit.SELECTION,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5ParameterMutation),
        candidate_generator=generator,
        benchmark_evaluator=evaluator,
        promotion_policy=_policy(),
    )
    result = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        context={"policy_context": {"case": "typed_parameter_binding"}},
        max_iterations=1,
    )
    assert result.history
    candidate = result.history[0].candidate
    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    fresh_reader = FileSystemCAS(tmp_path / "cas")
    evaluation_ref = _selected_evaluation_ref(stage_b)

    class _NonFilesystemStoreBase:
        """Delegate CAS operations without exposing a filesystem root."""

        def __init__(self, delegate: FileSystemCAS, *, deny_raw: bool = False) -> None:
            self._delegate = delegate
            self._deny_raw = deny_raw
            self.root_accesses = 0
            self.raw_reads = 0

        @property
        def root(self) -> Path:
            self.root_accesses += 1
            raise AssertionError("Core JSON consumer accessed a filesystem root")

        def has(self, artifact_id: ArtifactID | ArtifactRef) -> bool:
            return self._delegate.has(artifact_id)

        def get_bytes(self, artifact_id: ArtifactID | ArtifactRef) -> bytes:
            return self._delegate.get_bytes(artifact_id)

        def get_manifest(self, artifact_id: ArtifactID | ArtifactRef) -> ArtifactManifest:
            return self._delegate.get_manifest(artifact_id)

        def put_bytes(
            self,
            data: bytes,
            opts: ArtifactWriteOptions,
            *,
            return_selected_profile: bool = False,
        ) -> ArtifactRef:
            return self._delegate.put_bytes(
                data, opts, return_selected_profile=return_selected_profile
            )

        def put_json(
            self,
            obj: object,
            opts: ArtifactWriteOptions,
            canon_spec: CanonSpec | None = None,
            *,
            return_selected_profile: bool = False,
        ) -> ArtifactRef:
            return self._delegate.put_json(
                obj,
                opts,
                canon_spec=canon_spec,
                return_selected_profile=return_selected_profile,
            )

        def verify(self, artifact_id: ArtifactID | ArtifactRef) -> VerificationReport:
            return self._delegate.verify(artifact_id)

        def iter_artifact_ids(self) -> list[ArtifactID]:
            return self._delegate.iter_artifact_ids()

        def get_manifest_by_profile(
            self, artifact_id: ArtifactID | str, manifest_profile_sha256: str
        ) -> ArtifactManifest:
            return self._delegate.get_manifest_by_profile(artifact_id, manifest_profile_sha256)

    class _NonFilesystemCoreJSONStore(_NonFilesystemStoreBase):
        def get_raw_manifest_bytes(
            self,
            artifact_id: ArtifactID | ArtifactRef | str,
            *,
            manifest_profile_sha256: str | None = None,
        ) -> bytes:
            self.raw_reads += 1
            if self._deny_raw:
                raise PermissionError("controlled raw-manifest read denial")
            return self._delegate.get_raw_manifest_bytes(
                artifact_id, manifest_profile_sha256=manifest_profile_sha256
            )

    profile_reader: CoreJSONArtifactStore = _NonFilesystemCoreJSONStore(fresh_reader)
    evaluation = load_model_artifact(profile_reader, evaluation_ref, BenchmarkEvaluation)
    assert isinstance(evaluation, BenchmarkEvaluation)
    assert evaluation.method_result_ref is not None
    request_basis = evaluation.metadata["method_request_basis"]
    assert request_basis["schema_version"] == "2"
    assert request_basis["search_parameter_values"] == {"method_offset": candidate["method_offset"]}
    assert request_basis["search_method_run_profile"]["search_parameter_bindings"] == {
        "method_offset": "offset"
    }
    assert request_basis["job_spec"]["method_params"]["offset"] == candidate["method_offset"]
    method_result = load_json_artifact(profile_reader, evaluation.method_result_ref)
    assert method_result == {"score": candidate["value"] + candidate["method_offset"]}
    verified = _verify_search_source_profile_receipt(
        store=profile_reader,
        evaluation_ref=evaluation_ref,
    )
    assert verified is not None
    assert profile_reader.root_accesses == 0
    assert profile_reader.raw_reads > 0

    wrong_profile_ref = evaluation_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    assert (
        _verify_search_source_profile_receipt(
            store=profile_reader, evaluation_ref=wrong_profile_ref
        )
        is None
    )

    actual_manifest = fresh_reader.get_manifest(evaluation_ref)
    assert actual_manifest.artifact_schema is not None
    alternate_profile_ref = fresh_reader.put_bytes(
        fresh_reader.get_bytes(evaluation_ref),
        ArtifactWriteOptions(
            kind=actual_manifest.kind,
            media_type=actual_manifest.media_type,
            schema=SchemaInfo(
                name="tests.foreign.BenchmarkEvaluation",
                version=actual_manifest.artifact_schema.version,
            ),
            producer=actual_manifest.producer,
            env=actual_manifest.env,
            inputs=actual_manifest.inputs,
            canon=actual_manifest.canon,
            governance=actual_manifest.governance,
            tenant_context=actual_manifest.tenant_context,
            same_input_closure=actual_manifest.same_input_closure,
            authority=actual_manifest.authority,
            warnings=actual_manifest.warnings,
        ),
        return_selected_profile=True,
    )
    assert alternate_profile_ref.artifact_id == evaluation_ref.artifact_id
    assert alternate_profile_ref.manifest_profile_sha256 is not None
    assert alternate_profile_ref.manifest_profile_sha256 != evaluation_ref.manifest_profile_sha256
    assert (
        _verify_search_source_profile_receipt(
            store=_NonFilesystemCoreJSONStore(fresh_reader),
            evaluation_ref=alternate_profile_ref,
        )
        is None
    )
    assert (
        _verify_search_source_profile_receipt(
            store=_NonFilesystemCoreJSONStore(fresh_reader),
            evaluation_ref=evaluation_ref,
        )
        is not None
    )

    missing_raw_reader = _NonFilesystemStoreBase(fresh_reader)
    monkeypatch.setattr(
        "polisyos.scientist.methods.autotune.runtime.default_store",
        lambda: missing_raw_reader,
    )
    with pytest.raises(TypeError, match="core_json_artifact_store_unavailable"):
        _default_core_json_store()
    assert (
        _verify_search_source_profile_receipt(
            store=missing_raw_reader, evaluation_ref=evaluation_ref
        )
        is None
    )
    assert missing_raw_reader.root_accesses == 0

    denied_raw_reader = _NonFilesystemCoreJSONStore(fresh_reader, deny_raw=True)
    monkeypatch.setattr(
        "polisyos.scientist.methods.autotune.runtime.default_store",
        lambda: denied_raw_reader,
    )
    assert _default_core_json_store() is denied_raw_reader
    assert (
        _verify_search_source_profile_receipt(
            store=denied_raw_reader, evaluation_ref=evaluation_ref
        )
        is None
    )
    assert denied_raw_reader.raw_reads > 0
    assert denied_raw_reader.root_accesses == 0
    assert generator._search_method_run_profile is not None
    assert generator._search_method_run_profile.schema_version == "2"
    assert generator._search_method_run_profile.method_signature_abi_digest


def test_search_parameter_binding_rejects_same_fqn_version_with_changed_abi(tmp_path) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_same_version_abi_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "method_offset", "lower": -0.5, "upper": 0.5}]),
        n_initial=2,
        seed=67,
    )
    context = {"policy_context": {"case": "same_version_abi_drift"}}
    generator.set_search_run_context(context)
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        method_version=_V5ScoreMethod.signature.version,
        candidate_input_bindings={"value": "value"},
        search_parameter_bindings={"method_offset": "offset"},
        split=BenchmarkSplit.SELECTION,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5ParameterMutation),
        candidate_generator=generator,
        benchmark_evaluator=evaluator,
        promotion_policy=_policy(),
    )
    profile = _build_search_method_run_profile(
        store=store,
        generator=generator,
        spec=spec,
        suite_ref=suite_ref,
        context=context,
    )
    assert profile is not None
    assert profile.method_fqn == _V5ScoreMethodChangedAbi.signature.fqn
    assert profile.method_version == _V5ScoreMethodChangedAbi.signature.version
    assert profile.method_signature_abi_digest != _V5ScoreMethodChangedAbi.signature.abi_digest()

    MethodRegistry.get_instance().register(_V5ScoreMethodChangedAbi, override=True)
    current_signature = MethodRegistry.get_instance().get_signature(profile.method_fqn)
    assert current_signature is not None
    assert current_signature.fqn == profile.method_fqn
    assert current_signature.version == profile.method_version
    assert current_signature.abi_digest() != profile.method_signature_abi_digest
    candidate_ref = persist_mutation_artifact(
        store,
        _V5ParameterMutation(value=0.25, method_offset=0.3),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )
    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {
            "store": store,
            "policy": _policy(),
            "loop_id": "v5_search",
            "_search_method_run_profile": profile.model_dump(mode="json", exclude_none=True),
        },
    )
    assert evaluation.status == "search_parameter_binding_rejected"
    assert evaluation.method_result_ref is None
    assert evaluation.method_evidence_ref is None


@pytest.mark.parametrize(
    "method_type",
    [_V5StaticScoreMethod, _V5DefaultlessScoreMethod],
    ids=["static", "defaultless"],
)
def test_search_parameter_binding_refuses_static_or_defaultless_method_parameters(
    tmp_path, method_type: type[_V5ScoreMethod]
) -> None:
    MethodRegistry.get_instance().register(method_type, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id=f"v5_{method_type.__name__}_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "method_offset", "lower": -0.5, "upper": 0.5}]),
        n_initial=2,
        seed=71,
    )
    context = {"policy_context": {"case": method_type.__name__}}
    generator.set_search_run_context(context)
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=method_type.signature.fqn,
        method_version=method_type.signature.version,
        candidate_input_bindings={"value": "value"},
        search_parameter_bindings={"method_offset": "offset"},
        split=BenchmarkSplit.SELECTION,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5ParameterMutation),
        candidate_generator=generator,
        benchmark_evaluator=evaluator,
        promotion_policy=_policy(),
    )
    assert (
        _build_search_method_run_profile(
            store=store,
            generator=generator,
            spec=spec,
            suite_ref=suite_ref,
            context=context,
        )
        is None
    )
    candidate_ref = persist_mutation_artifact(
        store,
        _V5ParameterMutation(value=0.25, method_offset=0.3),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )
    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {
            "store": store,
            "policy": _policy(),
            "loop_id": "v5_search",
            "_search_method_run_profile": None,
        },
    )
    assert evaluation.status == "search_parameter_basis_unavailable"
    assert evaluation.method_result_ref is None
    assert evaluation.method_evidence_ref is None


def test_search_parameter_binding_rejects_duplicate_method_targets() -> None:
    with pytest.raises(
        ValueError, match="each dynamic MethodJob parameter can have one SearchSpace binding"
    ):
        MethodJobBenchmarkEvaluator(
            method_fqn=_V5ScoreMethod.signature.fqn,
            method_version=_V5ScoreMethod.signature.version,
            candidate_input_bindings={"value": "value"},
            search_parameter_bindings={
                "first_coordinate": "offset",
                "second_coordinate": "offset",
            },
            split=BenchmarkSplit.SELECTION,
        )


@pytest.mark.parametrize(
    "candidate_payload",
    [
        {"loop_id": "v5_search", "value": 0.25},
        {"loop_id": "v5_search", "value": 0.25, "method_offset": True},
        {"loop_id": "v5_search", "value": 0.25, "method_offset": "0.3"},
        {"loop_id": "v5_search", "value": 0.25, "method_offset": 1.5},
    ],
    ids=["missing", "boolean", "coerced-string", "outside-bounds"],
)
def test_search_parameter_binding_rejects_missing_malformed_or_out_of_bounds_candidate(
    tmp_path, candidate_payload: dict[str, Any]
) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_parameter_rejection_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "method_offset", "lower": -0.5, "upper": 0.5}]),
        n_initial=2,
        seed=59,
    )
    context = {"policy_context": {"case": "typed_parameter_rejection"}}
    generator.set_search_run_context(context)
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        method_version=_V5ScoreMethod.signature.version,
        candidate_input_bindings={"value": "value"},
        search_parameter_bindings={"method_offset": "offset"},
        split=BenchmarkSplit.SELECTION,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5ParameterMutation),
        candidate_generator=generator,
        benchmark_evaluator=evaluator,
        promotion_policy=_policy(),
    )
    profile = _build_search_method_run_profile(
        store=store,
        generator=generator,
        spec=spec,
        suite_ref=suite_ref,
        context=context,
    )
    assert profile is not None
    candidate_ref = store.put_json(
        candidate_payload,
        ArtifactWriteOptions(
            kind="scientist.autotune.v5_search.candidate",
            media_type="application/json",
            schema=SchemaInfo(name="tests.V5ParameterMutation", version="1.0"),
            inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {
            "store": store,
            "policy": _policy(),
            "loop_id": "v5_search",
            "_search_method_run_profile": profile.model_dump(mode="json", exclude_none=True),
        },
    )
    assert evaluation.status == "search_parameter_binding_rejected"
    assert evaluation.method_result_ref is None


def test_search_parameter_binding_rejects_foreign_profiles_and_undeclared_maps(
    tmp_path,
) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_parameter_profile_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "method_offset", "lower": -0.5, "upper": 0.5}]),
        n_initial=2,
        seed=61,
    )
    context = {"policy_context": {"case": "parameter_profile_identity"}}
    generator.set_search_run_context(context)
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        method_version=_V5ScoreMethod.signature.version,
        candidate_input_bindings={"value": "value"},
        search_parameter_bindings={"method_offset": "offset"},
        split=BenchmarkSplit.SELECTION,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5ParameterMutation),
        candidate_generator=generator,
        benchmark_evaluator=evaluator,
        promotion_policy=_policy(),
    )
    profile = _build_search_method_run_profile(
        store=store,
        generator=generator,
        spec=spec,
        suite_ref=suite_ref,
        context=context,
    )
    assert profile is not None
    candidate_ref = persist_mutation_artifact(
        store,
        _V5ParameterMutation(value=0.25, method_offset=0.3),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )
    direct_context = {
        "store": store,
        "policy": _policy(),
        "loop_id": "v5_search",
        "_search_method_run_profile": profile.model_dump(mode="json", exclude_none=True),
    }
    foreign_profile = profile.model_copy(update={"method_fqn": "foreign.method@1.0.0"})
    foreign_result = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {
            **direct_context,
            "_search_method_run_profile": foreign_profile.model_dump(
                mode="json", exclude_none=True
            ),
        },
    )
    assert foreign_result.status == "search_parameter_basis_unavailable"
    assert foreign_result.method_result_ref is None

    for bindings in (
        {"missing_search_dimension": "offset"},
        {"method_offset": "unknown_method_parameter"},
        {"method_offset": "offset", "extra_dimension": "unknown_method_parameter"},
    ):
        invalid_evaluator = MethodJobBenchmarkEvaluator(
            method_fqn=_V5ScoreMethod.signature.fqn,
            method_version=_V5ScoreMethod.signature.version,
            candidate_input_bindings={"value": "value"},
            search_parameter_bindings=bindings,
            split=BenchmarkSplit.SELECTION,
        )
        invalid_spec = replace(spec, benchmark_evaluator=invalid_evaluator)
        assert (
            _build_search_method_run_profile(
                store=store,
                generator=generator,
                spec=invalid_spec,
                suite_ref=suite_ref,
                context=context,
            )
            is None
        )
        rejected = invalid_evaluator.evaluate(
            candidate_ref,
            suite_ref,
            {**direct_context, "_search_method_run_profile": None},
        )
        assert rejected.status == "search_parameter_basis_unavailable"
        assert rejected.method_result_ref is None

    with pytest.raises(ValueError, match="must not also appear in method_params"):
        MethodJobBenchmarkEvaluator(
            method_fqn=_V5ScoreMethod.signature.fqn,
            method_version=_V5ScoreMethod.signature.version,
            candidate_input_bindings={"value": "value"},
            method_params={"offset": 0.0},
            search_parameter_bindings={"method_offset": "offset"},
        )


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
    assert "search_gp_fit_basis_ref" not in evaluation.metadata
    assert "fit_basis_ref" not in evaluation.metadata["search_source_profile_receipt"]
    assert evaluation.metadata["search_source_profile_receipt"]["grade"] == "candidate_only"
    untyped_ref = fresh_reader.put_json(
        evaluation,
        ArtifactWriteOptions(
            kind=f"scientist.autotune.{evaluation.loop_id}.evaluation",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert untyped_ref.manifest_profile_sha256 is not None
    assert fresh_reader.get_manifest(untyped_ref).artifact_schema is None
    assert (
        _verify_search_source_profile_receipt(
            store=fresh_reader,
            evaluation_ref=untyped_ref,
        )
        is None
    )
    assert evaluation.metadata["method_request_basis"]["schema_version"] == "1"
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
    assert source_evaluation.metadata["warm_start_compatibility"] == (
        evaluation.search_source_profile.model_dump(mode="json", exclude_none=True)
    )
    assert source_evaluation.metadata["search_source_profile_receipt"]["grade"] == "candidate_only"

    marker_only = replace(
        source_evaluation,
        metadata={
            key: value
            for key, value in source_evaluation.metadata.items()
            if key != "search_source_profile_receipt"
        },
    )
    marker_only_generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=2,
        seed=43,
    )
    marker_only_generator.set_search_run_context(original_context)
    marker_only_spec = replace(spec, candidate_generator=marker_only_generator)
    target_method_run_profile = _build_search_method_run_profile(
        store=fresh_reader,
        generator=marker_only_generator,
        spec=marker_only_spec,
        suite_ref=suite_ref,
        context=original_context,
    )
    assert target_method_run_profile is not None
    marker_only_generator.set_search_method_run_profile(target_method_run_profile)
    marker_only_generator._configure_source_store(store)
    marker_only_generator.warm_start_for_context([marker_only], context=original_context)
    assert marker_only_generator._warm_start_rejections[-1]["reason"] == (
        "source profile receipt missing"
    )
    assert not marker_only_generator._optimizer._warm_evals

    # A completed stage-B row without its persisted source receipt cannot inherit
    # the visible candidate profile during fresh history reconstruction.
    stripped = evaluation.model_copy(
        update={
            "search_source_profile": None,
            "metadata": {
                key: value
                for key, value in evaluation.metadata.items()
                if key != "search_source_profile_receipt"
            },
        }
    )
    stripped_ref = persist_benchmark_evaluation(
        store,
        stripped,
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )
    original_entry = result.history[0]
    stripped_stage_b = {
        **original_entry.stage_b_result,
        "metadata": {
            **original_entry.stage_b_result["metadata"],
            "evaluation_artifact_ref": stripped_ref.model_dump(mode="json"),
            "evaluation_id": str(stripped_ref.artifact_id),
        },
    }
    stripped_entry = {
        "candidate": original_entry.candidate,
        "stage_b_result": stripped_stage_b,
        "objective_value": original_entry.objective_value,
        "stage_a_passed": original_entry.stage_a_passed,
        "duration_seconds": original_entry.duration_seconds,
    }
    unverified_history = generator._history_to_evaluations([stripped_entry])
    assert len(unverified_history) == 1
    assert "warm_start_compatibility" not in unverified_history[0].metadata
    assert "search_source_profile_receipt" not in unverified_history[0].metadata
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
        tenant_id=None,
        objective_directions={"score": OptimizationDirection.MINIMIZE.value},
        objective_rule_specs={
            "score": _configured_search_metric_rule_spec("score", "maximize") or ""
        },
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


def test_initial_candidate_profile_marker_does_not_create_a_source_receipt(tmp_path) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_forged_marker_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=2,
        seed=41,
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
    forged_profile = {
        "profile_kind": "configured_native_gp",
        "proposal_source": "bayesian_acquisition",
        "warm_start_eligible": True,
    }

    result = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        initial_candidate={
            "loop_id": "v5_search",
            "value": 0.5,
            "_strategy_metadata": {
                "candidate_id": "caller-selected",
                "warm_start_compatibility": forged_profile,
            },
        },
        max_iterations=1,
    )

    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    evaluation = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"),
        _selected_evaluation_ref(stage_b),
        BenchmarkEvaluation,
    )
    assert evaluation.search_source_profile is None
    assert "search_source_profile_receipt" not in evaluation.metadata
    rehydrated = generator._history_to_evaluations(result.history)
    assert len(rehydrated) == 1
    assert "warm_start_compatibility" not in rehydrated[0].metadata


@pytest.mark.skipif(
    os.environ.get("POLISYOS_RUN_NATIVE_GP_HEAVY") != "1",
    reason="reserved single native GP fit slot",
)
def test_fitted_native_gp_profile_round_trips_into_same_context_search(tmp_path) -> None:
    _register_method()
    MethodRegistry.get_instance().register(_V5ScoreMethodV2, override=True)
    MethodRegistry.get_instance().register(_V5NativeGPScoreMethod, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_native_gp_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        primary_metric="score",
        direction=MetricDirection.MAXIMIZE,
        unit="dimensionless",
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=3,
        seed=31,
    )
    generator._optimizer._config.num_restarts = 1
    generator._optimizer._config.raw_samples = 16
    generator._optimizer._config.refit_interval = 1
    policy = _policy(unit="dimensionless")
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5NativeGPScoreMethod.signature.fqn,
            method_version=_V5NativeGPScoreMethod.signature.version,
            method_params={"offset": 0.0},
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=policy,
    )
    source_context = {"policy_context": {"year": 2032, "unit": "dimensionless"}}
    original_context = {"policy_context": dict(source_context["policy_context"])}
    from polisyos.runtime.http.resilience import guard_runtime_cas

    guarded_store = guard_runtime_cas(store)
    runner = SearchLoopRunner(store=guarded_store, registry=registry)
    source_result = runner.run(
        spec,
        suite_ref=suite_ref,
        context=source_context,
        max_iterations=4,
    )

    assert source_context == original_context
    assert generator._source_store is runner._store
    assert generator._optimizer._model is not None
    assert source_result.history[-1].candidate["_strategy_metadata"]["source"] == (
        "bayesian_acquisition"
    )
    source_stage_b = source_result.history[-1].stage_b_result
    assert source_stage_b is not None
    source_evaluation_ref = _selected_evaluation_ref(source_stage_b)
    source_reader = FileSystemCAS(tmp_path / "cas")
    source_evaluation = load_model_artifact(
        source_reader,
        source_evaluation_ref,
        BenchmarkEvaluation,
    )
    assert source_evaluation.metadata["metric_unit"] == "dimensionless"
    assert source_evaluation.method_result_ref is not None
    method_result = load_json_artifact(source_reader, source_evaluation.method_result_ref)
    assert method_result["metric_units"] == {"score": "dimensionless"}
    assert source_stage_b["simulation_results"]["metric_units"] == {"score": "dimensionless"}
    admitted_history = generator._history_to_evaluations([source_result.history[-1]])
    assert len(admitted_history) == 1
    assert admitted_history[0].score_status.value == "available"
    assert admitted_history[0].scalar_score is not None
    assert admitted_history[0].metadata["search_source_profile_receipt"]["unit"] == (
        "dimensionless"
    )

    missing_unit_history = deepcopy(source_result.history[-1])
    missing_unit_history.stage_b_result["simulation_results"].pop("metric_units")
    missing_unit_admission = generator._history_to_evaluations([missing_unit_history])[0]
    assert missing_unit_admission.scalar_score is None
    assert missing_unit_admission.score_status.value == "unavailable"
    assert "search_source_profile_receipt" not in missing_unit_admission.metadata

    mismatched_unit_history = deepcopy(source_result.history[-1])
    mismatched_unit_history.stage_b_result["simulation_results"]["metric_units"] = {"score": "USD"}
    mismatched_unit_admission = generator._history_to_evaluations([mismatched_unit_history])[0]
    assert mismatched_unit_admission.scalar_score is None
    assert mismatched_unit_admission.score_status.value == "invalid"
    assert "search_source_profile_receipt" not in mismatched_unit_admission.metadata

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
    fit_basis_ref = ArtifactRef.model_validate(
        source_evaluation.metadata["search_gp_fit_basis_ref"]
    )
    assert fit_basis_ref.manifest_profile_sha256 is not None
    fit_basis_manifest = source_reader.get_manifest(fit_basis_ref)
    assert fit_basis_manifest.kind == "scientist.autotune.search_gp_fit_basis"
    assert fit_basis_manifest.artifact_schema is not None
    assert fit_basis_manifest.artifact_schema.name.endswith("SearchGPFitBasis")
    assert all(
        item.manifest_profile_sha256 is not None
        for item in fit_basis_manifest.inputs
        if item.role == "training_evaluation"
    )
    source_manifest = source_reader.get_manifest(source_evaluation_ref)
    assert {item.role for item in source_manifest.inputs} >= {
        "candidate",
        "benchmark_suite",
        "method_result",
        "method_evidence",
        "search_gp_fit_basis",
    }
    assert (
        next(
            item for item in source_manifest.inputs if item.role == "search_gp_fit_basis"
        ).manifest_profile_sha256
        == fit_basis_ref.manifest_profile_sha256
    )

    source_evaluation_artifact_ref = source_evaluation_ref
    fit_basis = load_model_artifact(source_reader, fit_basis_ref, SearchGPFitBasis)
    assert isinstance(fit_basis, SearchGPFitBasis)
    source_receipt = source_evaluation.metadata["search_source_profile_receipt"]
    proposal_uncertainty = SearchGPProposalUncertainty.model_validate(
        source_receipt["proposal_uncertainty"]
    )
    emitted_metadata = source_result.history[-1].candidate["_strategy_metadata"]
    assert proposal_uncertainty.authority_purpose == ("candidate_search_gp_proposal_uncertainty")
    assert proposal_uncertainty.grade == "candidate_only"
    assert proposal_uncertainty.proposal_source == "bayesian_acquisition"
    assert proposal_uncertainty.fit_basis_ref == fit_basis_ref
    assert proposal_uncertainty.candidate_ref == source_evaluation.candidate_ref
    assert proposal_uncertainty.method_result_ref == source_evaluation.method_result_ref
    assert proposal_uncertainty.method_evidence_ref == source_evaluation.method_evidence_ref
    assert proposal_uncertainty.method_job_key == source_evaluation.method_job_key
    assert proposal_uncertainty.acquisition_type == emitted_metadata["acquisition_type"]
    assert proposal_uncertainty.predicted_mean == emitted_metadata["predicted_mean"]
    assert proposal_uncertainty.predicted_std == emitted_metadata["predicted_std"]
    assert proposal_uncertainty.acquisition_value == emitted_metadata["acquisition_value"]
    assert len(fit_basis.acquisition_evaluation_refs) == (fit_basis.acquisition_observation_count)
    assert len(fit_basis.fitted_model_state_fingerprint) == 64

    def assert_uncertainty_receipt_is_refused(receipt_variant: dict[str, Any]) -> None:
        receipt_variant = dict(receipt_variant)
        receipt_variant.pop("receipt_sha256", None)
        receipt_variant["receipt_sha256"] = _search_source_fingerprint(receipt_variant)
        variant_evaluation = source_evaluation.model_copy(
            update={
                "metadata": {
                    **source_evaluation.metadata,
                    "search_source_profile_receipt": receipt_variant,
                }
            }
        )
        variant_ref = _persist_search_benchmark_evaluation(
            store,
            variant_evaluation,
            suite_ref=suite_ref,
        )
        assert (
            _verify_search_source_profile_receipt(
                store=store,
                evaluation_ref=variant_ref,
                expected_receipt=receipt_variant,
                expected_profile=source_profile.model_dump(mode="json", exclude_none=True),
                expected_method_run_profile=fit_basis.run_profile,
                require_warm_start_eligible=True,
            )
            is None
        )

    missing_uncertainty_receipt = dict(source_receipt)
    missing_uncertainty_receipt.pop("proposal_uncertainty")
    assert_uncertainty_receipt_is_refused(missing_uncertainty_receipt)
    changed_uncertainty_receipt = dict(source_receipt)
    changed_uncertainty_receipt["proposal_uncertainty"] = dict(
        source_receipt["proposal_uncertainty"]
    )
    changed_uncertainty_receipt["proposal_uncertainty"]["predicted_std"] += 0.5
    assert_uncertainty_receipt_is_refused(changed_uncertainty_receipt)
    fitted_optimizer = generator._optimizer
    fitted_model = fitted_optimizer._model
    torch = fitted_optimizer._torch
    assert fitted_model is not None
    assert torch is not None
    from gpytorch.constraints import Interval

    recorded_state_fingerprint = fit_basis.fitted_model_state_fingerprint
    assert fitted_optimizer._fitted_model_state_fingerprint() == recorded_state_fingerprint
    registered_bound = next(
        (
            (module, bound_name, bound)
            for module in fitted_model.modules()
            if isinstance(module, Interval)
            for bound_name, bound in module.named_buffers(recurse=False)
            if (bound_name == "upper_bound" and bool(torch.isposinf(bound).all().item()))
            or (bound_name == "lower_bound" and bool(torch.isneginf(bound).all().item()))
        ),
        None,
    )
    assert registered_bound is not None
    constraint, bound_name, bound = registered_bound
    assert bound_name not in dict(constraint.named_parameters(recurse=False))
    original_bound = bound.detach().clone()
    parameter_names = {name for name, _ in fitted_model.named_parameters()}
    state_name = f"{next(name for name, module in fitted_model.named_modules() if module is constraint)}.{bound_name}"
    if state_name.startswith("."):
        state_name = state_name[1:]
    assert state_name not in parameter_names
    assert torch.equal(fitted_model.state_dict()[state_name].detach().cpu(), original_bound.cpu())
    if bound_name == "upper_bound":
        finite_bound = constraint.lower_bound.detach().to(
            device=bound.device, dtype=bound.dtype
        ) + torch.ones_like(bound)
        wrong_sign_infinity = float("-inf")
    else:
        finite_bound = constraint.upper_bound.detach().to(
            device=bound.device, dtype=bound.dtype
        ) - torch.ones_like(bound)
        wrong_sign_infinity = float("inf")
    try:
        with torch.no_grad():
            bound.copy_(finite_bound)
        changed_bound_fingerprint = fitted_optimizer._fitted_model_state_fingerprint()
        assert changed_bound_fingerprint is not None
        assert changed_bound_fingerprint != recorded_state_fingerprint
        with torch.no_grad():
            bound.fill_(wrong_sign_infinity)
        assert fitted_optimizer._fitted_model_state_fingerprint() is None
        with torch.no_grad():
            bound.fill_(float("nan"))
        assert fitted_optimizer._fitted_model_state_fingerprint() is None
    finally:
        with torch.no_grad():
            bound.copy_(original_bound)
    assert fitted_optimizer._fitted_model_state_fingerprint() == recorded_state_fingerprint

    fitted_parameter = next(fitted_model.parameters())
    original_parameter = fitted_parameter.detach().clone()
    try:
        for invalid_value in (float("inf"), float("nan")):
            with torch.no_grad():
                fitted_parameter.fill_(invalid_value)
            assert fitted_optimizer._fitted_model_state_fingerprint() is None
            with torch.no_grad():
                fitted_parameter.copy_(original_parameter)
    finally:
        with torch.no_grad():
            fitted_parameter.copy_(original_parameter)
    assert fitted_optimizer._fitted_model_state_fingerprint() == recorded_state_fingerprint

    forged_model = torch.nn.Module()
    forged_model.register_buffer(
        "upper_bound",
        torch.tensor(float("inf"), dtype=fitted_parameter.dtype),
    )
    original_model = fitted_optimizer._model
    try:
        fitted_optimizer._model = forged_model
        assert fitted_optimizer._fitted_model_state_fingerprint() is None
    finally:
        fitted_optimizer._model = original_model
    assert fitted_optimizer._fitted_model_state_fingerprint() == recorded_state_fingerprint
    corrupted_training_refs = list(fit_basis.training_evaluation_refs)
    corrupted_training_refs[-1] = source_evaluation_artifact_ref
    forged_basis = fit_basis.model_copy(
        update={"training_evaluation_refs": corrupted_training_refs}
    )
    forged_fit_basis_ref = store.put_json(
        forged_basis,
        ArtifactWriteOptions(
            kind="scientist.autotune.search_gp_fit_basis",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.SearchGPFitBasis",
                version="2.0",
            ),
            inputs=[
                input_ref_from_artifact_ref(ref, role="training_evaluation")
                for ref in corrupted_training_refs
            ]
            + [
                input_ref_from_artifact_ref(ref, role="acquisition_evaluation")
                for ref in fit_basis.acquisition_evaluation_refs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    forged_receipt = dict(source_evaluation.metadata["search_source_profile_receipt"])
    forged_receipt["fit_basis_ref"] = forged_fit_basis_ref.model_dump(mode="json")
    forged_receipt.pop("receipt_sha256", None)
    forged_receipt["receipt_sha256"] = _search_source_fingerprint(forged_receipt)
    forged_evaluation = source_evaluation.model_copy(
        update={
            "metadata": {
                **source_evaluation.metadata,
                "search_source_profile_receipt": forged_receipt,
                "search_gp_fit_basis_ref": forged_fit_basis_ref.model_dump(mode="json"),
            }
        }
    )
    forged_evaluation_ref = _persist_search_benchmark_evaluation(
        store,
        forged_evaluation,
        suite_ref=suite_ref,
    )
    assert forged_fit_basis_ref.manifest_profile_sha256 is not None
    assert forged_evaluation_ref.manifest_profile_sha256 is not None
    assert (
        _verify_search_source_profile_receipt(
            store=store,
            evaluation_ref=forged_evaluation_ref,
            expected_receipt=forged_receipt,
            expected_profile=source_profile.model_dump(mode="json", exclude_none=True),
            expected_method_run_profile=fit_basis.run_profile,
            require_warm_start_eligible=True,
        )
        is None
    )

    altered_state_basis = fit_basis.model_copy(update={"fitted_model_state_fingerprint": "0" * 64})
    altered_state_basis_ref = store.put_json(
        altered_state_basis,
        ArtifactWriteOptions(
            kind="scientist.autotune.search_gp_fit_basis",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.SearchGPFitBasis",
                version="2.0",
            ),
            inputs=[
                input_ref_from_artifact_ref(ref, role="training_evaluation")
                for ref in fit_basis.training_evaluation_refs
            ]
            + [
                input_ref_from_artifact_ref(ref, role="acquisition_evaluation")
                for ref in fit_basis.acquisition_evaluation_refs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False),
        return_selected_profile=True,
    )
    altered_state_receipt = dict(source_evaluation.metadata["search_source_profile_receipt"])
    altered_state_receipt["fit_basis_ref"] = altered_state_basis_ref.model_dump(mode="json")
    altered_state_receipt.pop("receipt_sha256", None)
    altered_state_receipt["receipt_sha256"] = _search_source_fingerprint(altered_state_receipt)
    altered_state_evaluation = source_evaluation.model_copy(
        update={
            "metadata": {
                **source_evaluation.metadata,
                "search_source_profile_receipt": altered_state_receipt,
                "search_gp_fit_basis_ref": altered_state_basis_ref.model_dump(mode="json"),
            }
        }
    )
    altered_state_evaluation_ref = _persist_search_benchmark_evaluation(
        store, altered_state_evaluation, suite_ref=suite_ref
    )
    assert (
        _verify_search_source_profile_receipt(
            store=store,
            evaluation_ref=altered_state_evaluation_ref,
            expected_receipt=altered_state_receipt,
            expected_profile=source_profile.model_dump(mode="json", exclude_none=True),
            expected_method_run_profile=fit_basis.run_profile,
            require_warm_start_eligible=True,
        )
        is None
    )

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
        tenant_id=None,
        objective_directions={policy.primary_metric: OptimizationDirection.MINIMIZE.value},
        objective_rule_specs={
            policy.primary_metric: _configured_search_metric_rule_spec(
                policy.primary_metric, generator._direction.value
            )
            or ""
        },
        embedding=[1.0],
        num_evaluations=len(source_evaluations),
    )
    assert transfer.register_run(source_fingerprint, source_evaluations) is not None
    bridge = WarmStartBridge(transfer)

    def assert_target_method_mismatch_is_refused(
        *,
        run_id: str,
        evaluator: MethodJobBenchmarkEvaluator,
        expected_method_fqn: str,
        expected_method_version: str,
        expected_method_params: dict[str, Any],
        expected_profile_update: dict[str, Any],
        expected_score_offset: float,
    ) -> None:
        mismatch_generator = BayesianCandidateGenerator(
            SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
            n_initial=3,
            seed=47,
        )
        mismatch_fingerprint = source_fingerprint.model_copy(update={"run_id": run_id})
        mismatch_result = SearchLoopRunner(store=store, registry=registry).run(
            replace(
                spec,
                candidate_generator=mismatch_generator,
                benchmark_evaluator=evaluator,
            ),
            suite_ref=suite_ref,
            context=original_context,
            max_iterations=1,
            warm_start_bridge=bridge,
            warm_start_fingerprint=mismatch_fingerprint,
        )

        assert mismatch_result.history
        target_profile = mismatch_generator._search_method_run_profile
        assert target_profile == fit_basis.run_profile.model_copy(update=expected_profile_update)
        assert mismatch_generator._warm_start_accepted_count == 0
        assert (
            sum(
                rejection.get("reason") == "source profile receipt or CAS chain invalid"
                for rejection in mismatch_generator._warm_start_rejections
            )
            == 1
        )
        assert not mismatch_generator._optimizer._warm_evals

        stage_b = mismatch_result.history[-1].stage_b_result
        assert stage_b is not None
        target_reader = FileSystemCAS(tmp_path / "cas")
        target_evaluation = load_model_artifact(
            target_reader,
            _selected_evaluation_ref(stage_b),
            BenchmarkEvaluation,
        )
        assert target_evaluation.status == "measured_candidate"
        assert target_evaluation.method_result_ref is not None
        assert target_evaluation.method_evidence_ref is not None
        actual_job_spec = target_evaluation.metadata["method_request_basis"]["job_spec"]
        assert actual_job_spec["method_fqn"] == expected_method_fqn
        assert actual_job_spec["method_version"] == expected_method_version
        assert actual_job_spec["method_params"] == expected_method_params
        target_output = load_json_artifact(target_reader, target_evaluation.method_result_ref)
        assert target_output["score"] == pytest.approx(
            float(mismatch_result.history[-1].candidate["value"]) + expected_score_offset
        )

    # Foundry's canonical FQN contains the semver suffix, so selecting the actual
    # v2 MethodJob changes both version-bound profile fields; the helper asserts
    # every other source-basis field remains identical.
    assert_target_method_mismatch_is_refused(
        run_id="v5-native-method-version-mismatch",
        evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5ScoreMethodV2.signature.fqn,
            method_version=_V5ScoreMethodV2.signature.version,
            method_params={"offset": 0.0},
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        expected_method_fqn=_V5ScoreMethodV2.signature.fqn,
        expected_method_version=_V5ScoreMethodV2.signature.version,
        expected_method_params={"offset": 0.0},
        expected_profile_update={
            "method_fqn": _V5ScoreMethodV2.signature.fqn,
            "method_version": _V5ScoreMethodV2.signature.version,
        },
        expected_score_offset=0.0,
    )
    assert_target_method_mismatch_is_refused(
        run_id="v5-native-method-params-mismatch",
        evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5ScoreMethod.signature.fqn,
            method_version=_V5ScoreMethod.signature.version,
            method_params={"offset": 0.5},
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        expected_method_fqn=_V5ScoreMethod.signature.fqn,
        expected_method_version=_V5ScoreMethod.signature.version,
        expected_method_params={"offset": 0.5},
        expected_profile_update={
            "method_params_fingerprint": _search_source_fingerprint({"offset": 0.5})
        },
        expected_score_offset=0.5,
    )

    target_generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=3,
        seed=37,
    )
    target_generator._optimizer._config.num_restarts = 1
    target_generator._optimizer._config.raw_samples = 16
    target_fingerprint = source_fingerprint.model_copy(update={"run_id": "v5-native-target-run"})
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
        _selected_evaluation_ref(target_stage_b),
        BenchmarkEvaluation,
    )
    assert target_evaluation.search_source_profile is not None
    assert target_evaluation.search_source_profile.training_observation_count == 3
    assert target_evaluation.search_source_profile.warm_start_eligible is True
    assert target_evaluation.search_source_profile.context_fingerprint == (
        source_profile.context_fingerprint
    )

    # Reuse the same eligible source evaluation and CAS receipt, changing only one
    # load-bearing context value on a fresh target generator.
    native_source_evaluations = [
        evaluation
        for evaluation in transferred_profiles
        if evaluation.candidate_id in fitted_source_ids
    ]
    assert len(native_source_evaluations) == 1
    native_source_evaluation = native_source_evaluations[0]
    assert native_source_evaluation.metadata["search_source_evaluation_ref"] == (
        source_evaluation_ref.model_dump(mode="json")
    )
    assert native_source_evaluation.metadata["search_source_profile_receipt"] == source_receipt
    assert native_source_evaluation.metadata["warm_start_compatibility"] == (
        source_profile.model_dump(mode="json", exclude_none=True)
    )
    assert (
        ArtifactRef.model_validate(
            native_source_evaluation.metadata["search_source_profile_receipt"]["fit_basis_ref"]
        )
        == fit_basis_ref
    )

    changed_context = {"policy_context": {**original_context["policy_context"], "year": 2033}}
    assert changed_context["policy_context"]["unit"] == original_context["policy_context"]["unit"]
    assert changed_context["policy_context"]["year"] != original_context["policy_context"]["year"]
    changed_context_generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=3,
        seed=37,
    )
    changed_context_generator._optimizer._config.num_restarts = 1
    changed_context_generator._optimizer._config.raw_samples = 16
    changed_context_generator.set_search_run_context(changed_context)
    changed_context_generator._configure_source_store(runner._store)
    assert changed_context_generator._source_store is runner._store
    changed_context_spec = replace(spec, candidate_generator=changed_context_generator)
    changed_context_profile = _build_search_method_run_profile(
        store=runner._store,
        generator=changed_context_generator,
        spec=changed_context_spec,
        suite_ref=suite_ref,
        context=changed_context,
    )
    assert changed_context_profile is not None
    assert changed_context_profile.context_fingerprint != fit_basis.run_profile.context_fingerprint
    assert (
        changed_context_profile.model_copy(
            update={"context_fingerprint": fit_basis.run_profile.context_fingerprint}
        )
        == fit_basis.run_profile
    )
    changed_context_generator.set_search_method_run_profile(changed_context_profile)

    changed_context_generator.warm_start_for_context(
        native_source_evaluations,
        context=changed_context,
    )
    assert changed_context_generator._warm_start_accepted_count == 0
    assert not changed_context_generator._optimizer._warm_evals
    assert changed_context_generator._optimizer._model is None
    assert changed_context_generator._warm_start_rejections == [
        {"reason": "source profile receipt or CAS chain invalid"}
    ]


def test_reported_method_unit_must_match_selected_run_unit(tmp_path) -> None:
    MethodRegistry.get_instance().register(_V5DeclaredUnitScoreMethod, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_unit_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        n_initial=2,
        seed=20261020,
        primary_metric="score",
        direction=MetricDirection.MAXIMIZE,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5DeclaredUnitScoreMethod.signature.fqn,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(metric="score", unit="EUR per resident"),
    )

    result = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        initial_candidate={"loop_id": "v5_search", "value": 0.4},
        max_iterations=1,
    )

    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    evaluation = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"),
        _selected_evaluation_ref(stage_b),
        BenchmarkEvaluation,
    )
    assert evaluation.status == "metric_unavailable"
    assert evaluation.selection_metrics == {}
    assert evaluation.promotable is False
    assert evaluation.metadata["metric_unit"] == "USD per resident"
    request_basis = evaluation.metadata["method_request_basis"]
    run_profile = request_basis["search_method_run_profile"]
    assert run_profile["unit"] == "EUR per resident"
    assert run_profile["objective_fingerprint"] == generator._objective_profile_fingerprint(
        unit="EUR per resident"
    )


def test_methodjob_metric_without_selected_unit_is_not_carried_to_search_history(
    tmp_path,
) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_missing_unit_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        primary_metric="score",
        direction=MetricDirection.MAXIMIZE,
        unit="dimensionless",
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=2,
        seed=20261027,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5ScoreMethod.signature.fqn,
            method_version=_V5ScoreMethod.signature.version,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(unit="dimensionless"),
    )

    result = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        initial_candidate={"loop_id": "v5_search", "value": 0.4},
        max_iterations=1,
    )

    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    assert "metric_units" not in stage_b["simulation_results"]
    evaluation = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"),
        _selected_evaluation_ref(stage_b),
        BenchmarkEvaluation,
    )
    assert evaluation.metadata.get("metric_unit") is None
    assert evaluation.status == "metric_unavailable"
    history = generator._history_to_evaluations([result.history[0]])
    assert history[0].scalar_score is None
    assert history[0].score_status.value != "available"
    assert "search_source_profile_receipt" not in history[0].metadata


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
        _selected_evaluation_ref(stage_b),
        BenchmarkEvaluation,
    )
    assert evaluation.selection_metrics == {}
    assert evaluation.promotable is False
    assert evaluation.status == "metric_unavailable"


def _guarded_methodjob_evaluator(
    tmp_path: Path,
    *,
    deny_operations: frozenset[str] = frozenset(),
    deny_kinds: frozenset[str] = frozenset(),
) -> tuple[MethodJobBenchmarkEvaluator, ArtifactRef, ArtifactRef, object, object]:
    from polisyos.runtime.http.resilience import guard_runtime_cas

    class _GuardedMethodJobCAS(FileSystemCAS):
        def __init__(
            self, root: Path, *, denied: frozenset[str], denied_kinds: frozenset[str]
        ) -> None:
            self.denied_operations = denied
            self.denied_kinds = denied_kinds
            self.operations: list[dict[str, str | None]] = []
            self.denials: list[dict[str, str | None]] = []
            super().__init__(root, ownership_enforced=True, ownership_requires_scope=False)

        @staticmethod
        def _is_protected_kind(kind: str) -> bool:
            return (
                kind.startswith("scientist.method_result.") or kind == "scientist.method_evidence"
            )

        def _record(
            self,
            operation: str,
            kind: str,
            artifact: object,
            manifest_profile_sha256: str | None = None,
        ) -> dict[str, str | None]:
            entry: dict[str, str | None] = {
                "operation": operation,
                "kind": kind,
                "artifact": str(getattr(artifact, "artifact_id", artifact)),
                "manifest_profile_sha256": manifest_profile_sha256,
            }
            self.operations.append(entry)
            if (
                self._is_protected_kind(kind)
                and operation in self.denied_operations
                and (not self.denied_kinds or kind in self.denied_kinds)
            ):
                self.denials.append(entry)
                raise PermissionError("controlled MethodJob artifact operation denied")
            return entry

        def _bind_successful_write(
            self, entry: dict[str, str | None], operation: str, ref: ArtifactRef
        ) -> None:
            if entry["operation"] != operation:
                raise AssertionError("guarded artifact write trace lost operation ordering")
            entry["artifact"] = str(ref.artifact_id)
            entry["manifest_profile_sha256"] = ref.manifest_profile_sha256

        def get_manifest(self, artifact_id: ArtifactID | ArtifactRef) -> ArtifactManifest:
            manifest = FileSystemCAS.get_manifest(self, artifact_id)
            self._record(
                "get_manifest",
                manifest.kind,
                artifact_id,
                getattr(artifact_id, "manifest_profile_sha256", None),
            )
            return manifest

        def get_manifest_by_profile(
            self, artifact_id: ArtifactID | str, manifest_profile_sha256: str
        ) -> ArtifactManifest:
            manifest = FileSystemCAS.get_manifest_by_profile(
                self, artifact_id, manifest_profile_sha256
            )
            self._record(
                "get_manifest_by_profile", manifest.kind, artifact_id, manifest_profile_sha256
            )
            return manifest

        def get_bytes(self, artifact_id: ArtifactID | ArtifactRef) -> bytes:
            manifest = FileSystemCAS.get_manifest(self, artifact_id)
            self._record(
                "get_bytes",
                manifest.kind,
                artifact_id,
                getattr(artifact_id, "manifest_profile_sha256", None),
            )
            return FileSystemCAS.get_bytes(self, artifact_id)

        def get_raw_manifest_bytes(
            self,
            artifact_id: ArtifactID | ArtifactRef | str,
            *,
            manifest_profile_sha256: str | None = None,
        ) -> bytes:
            if manifest_profile_sha256 is None:
                manifest = FileSystemCAS.get_manifest(self, artifact_id)
                selected_profile = getattr(artifact_id, "manifest_profile_sha256", None)
            else:
                manifest = FileSystemCAS.get_manifest_by_profile(
                    self, artifact_id, manifest_profile_sha256
                )
                selected_profile = manifest_profile_sha256
            self._record("get_raw_manifest_bytes", manifest.kind, artifact_id, selected_profile)
            return FileSystemCAS.get_raw_manifest_bytes(
                self,
                artifact_id,
                manifest_profile_sha256=manifest_profile_sha256,
            )

        def put_json(
            self,
            obj: object,
            opts: ArtifactWriteOptions,
            canon_spec: CanonSpec | None = None,
            *,
            return_selected_profile: bool = False,
        ) -> ArtifactRef:
            entry = self._record("put_json", opts.kind, opts.kind)
            ref = FileSystemCAS.put_json(
                self,
                obj,
                opts,
                canon_spec=canon_spec,
                return_selected_profile=return_selected_profile,
            )
            self._bind_successful_write(entry, "put_json", ref)
            return ref

        def put_bytes(
            self,
            data: bytes,
            opts: ArtifactWriteOptions,
            *,
            return_selected_profile: bool = False,
        ) -> ArtifactRef:
            entry = self._record("put_bytes", opts.kind, opts.kind)
            ref = FileSystemCAS.put_bytes(
                self,
                data,
                opts,
                return_selected_profile=return_selected_profile,
            )
            self._bind_successful_write(entry, "put_bytes", ref)
            return ref

    _register_method()
    root = tmp_path / "cas"
    writer = FileSystemCAS(root)
    suite_ref = persist_benchmark_suite(
        writer,
        BenchmarkSuite(suite_id="v5_suite", kind="method_job"),
    )
    candidate_ref = persist_mutation_artifact(
        writer,
        _V5Mutation(value=0.25),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
        return_selected_profile=True,
    )
    guarded_target = _GuardedMethodJobCAS(root, denied=deny_operations, denied_kinds=deny_kinds)
    guarded_store = guard_runtime_cas(guarded_target)
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        method_version=_V5ScoreMethod.signature.version,
        candidate_input_bindings={"value": "value"},
        split=BenchmarkSplit.SELECTION,
    )
    return evaluator, candidate_ref, suite_ref, guarded_store, guarded_target


def test_methodjob_evaluator_keeps_one_rooted_guarded_store_for_runner_and_fresh_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polisyos.scientist.compute.runner as compute_runner

    evaluator, candidate_ref, suite_ref, store, target = _guarded_methodjob_evaluator(tmp_path)
    assert candidate_ref.manifest_profile_sha256 is not None
    assert suite_ref.manifest_profile_sha256 is not None
    original_run_job = compute_runner.run_job
    factory_returns: list[bool] = []

    def check_factory_then_run(spec: JobSpec, **kwargs: Any) -> Any:
        factory = kwargs.get("store_factory")
        assert callable(factory)
        assert "cas_root" in kwargs
        with pytest.raises(ValueError, match="methodjob_store_root_mismatch"):
            factory(tmp_path / "foreign-root")

        def tracked_factory(requested_root: Path) -> object:
            actual_store = factory(requested_root)
            factory_returns.append(actual_store is store)
            return actual_store

        kwargs["store_factory"] = tracked_factory
        return original_run_job(spec, **kwargs)

    fresh_reader_roots: list[Path] = []

    def reject_fresh_reader(instance: FileSystemCAS, root: Path) -> None:
        del instance
        fresh_reader_roots.append(root)
        raise AssertionError("MethodJob evaluator reconstructed a fresh filesystem reader")

    step_calls: list[bool] = []
    original_step = _V5ScoreMethod.pure_step

    def observed_step(state: Any, params: dict[str, Any]) -> dict[str, float]:
        step_calls.append(True)
        return original_step(state, params)

    monkeypatch.setattr(_V5ScoreMethod, "pure_step", staticmethod(observed_step))
    monkeypatch.setattr(compute_runner, "run_job", check_factory_then_run)
    monkeypatch.setattr(FileSystemCAS, "__init__", reject_fresh_reader)
    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {"store": store, "policy": _policy(), "loop_id": "v5_search"},
    )

    assert len(factory_returns) >= 2
    assert all(factory_returns)
    assert step_calls == [True]
    assert fresh_reader_roots == []
    assert evaluation.selection_metrics == {"score": 0.25}
    assert evaluation.method_result_ref is not None
    assert evaluation.method_evidence_ref is not None
    selected_refs = (
        candidate_ref,
        suite_ref,
        evaluation.method_result_ref,
        evaluation.method_evidence_ref,
    )
    assert all(ref.manifest_profile_sha256 is not None for ref in selected_refs)

    def has_exact_view(event: dict[str, str | None], ref: ArtifactRef) -> bool:
        return (
            event["artifact"] == str(ref.artifact_id)
            and event["manifest_profile_sha256"] == ref.manifest_profile_sha256
        )

    for ref in (candidate_ref, suite_ref):
        assert any(
            event["operation"] == "get_bytes" and has_exact_view(event, ref)
            for event in target.operations
        )
    for ref in (evaluation.method_result_ref, evaluation.method_evidence_ref):
        assert any(
            event["operation"] == "put_json"
            and event["kind"] == ref.kind
            and has_exact_view(event, ref)
            for event in target.operations
        )
        assert any(
            event["operation"] == "get_bytes" and has_exact_view(event, ref)
            for event in target.operations
        )


@pytest.mark.parametrize(
    "denied_kind",
    ["scientist.method_result.tests.scientist", "scientist.method_evidence"],
)
def test_methodjob_evaluator_refuses_same_handle_protected_read_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, denied_kind: str
) -> None:
    evaluator, candidate_ref, suite_ref, store, target = _guarded_methodjob_evaluator(
        tmp_path,
        deny_operations=frozenset(
            {"get_manifest", "get_manifest_by_profile", "get_bytes", "get_raw_manifest_bytes"}
        ),
        deny_kinds=frozenset({denied_kind}),
    )
    fresh_reader_roots: list[Path] = []

    def reject_fresh_reader(instance: FileSystemCAS, root: Path) -> None:
        del instance
        fresh_reader_roots.append(root)
        raise AssertionError("MethodJob evaluator reconstructed a fresh filesystem reader")

    monkeypatch.setattr(FileSystemCAS, "__init__", reject_fresh_reader)
    with pytest.raises(PermissionError, match="controlled MethodJob artifact operation denied"):
        evaluator.evaluate(
            candidate_ref,
            suite_ref,
            {"store": store, "policy": _policy(), "loop_id": "v5_search"},
        )
    assert fresh_reader_roots == []
    assert target.denials
    assert target.denials[0]["operation"].startswith("get_")
    assert target.denials[0]["kind"] == denied_kind


@pytest.mark.parametrize(
    "denied_kind",
    ["scientist.method_result.tests.scientist", "scientist.method_evidence"],
)
def test_methodjob_evaluator_does_not_measure_after_same_handle_protected_write_denial(
    tmp_path: Path, denied_kind: str
) -> None:
    evaluator, candidate_ref, suite_ref, store, target = _guarded_methodjob_evaluator(
        tmp_path,
        deny_operations=frozenset({"put_json"}),
        deny_kinds=frozenset({denied_kind}),
    )
    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {"store": store, "policy": _policy(), "loop_id": "v5_search"},
    )
    assert evaluation.status == "method_job_failed"
    assert not (
        evaluation.method_result_ref is not None and evaluation.method_evidence_ref is not None
    )
    assert target.denials
    assert target.denials[0]["operation"] == "put_json"
    assert target.denials[0]["kind"] == denied_kind


def test_methodjob_evaluator_preserves_ambient_tenant_ownership(tmp_path: Path) -> None:
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.security.tenant_context import tenant_scope

    _register_method()
    root = tmp_path / "tenant-cas"
    owner_store = FileSystemCAS(root).with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-a"):
        suite_ref = persist_benchmark_suite(
            owner_store,
            BenchmarkSuite(suite_id="tenant_owned_suite", kind="method_job"),
        )
        candidate_ref = persist_mutation_artifact(
            owner_store,
            _V5Mutation(value=0.25),
            inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
            return_selected_profile=True,
        )

    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        method_version=_V5ScoreMethod.signature.version,
        candidate_input_bindings={"value": "value"},
        split=BenchmarkSplit.SELECTION,
    )
    context = {
        "store": FileSystemCAS(root),
        "policy": _policy(),
        "loop_id": "v5_search",
    }
    with tenant_scope(None, tenant_id="tenant-a"):
        allowed = evaluator.evaluate(candidate_ref, suite_ref, context)
    assert allowed.selection_metrics == {"score": 0.25}

    with tenant_scope(None, tenant_id="tenant-b"):
        with pytest.raises(ArtifactOwnershipError):
            evaluator.evaluate(candidate_ref, suite_ref, context)


def test_search_loop_runner_normalizes_plain_store_for_tenant_scope(tmp_path: Path) -> None:
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.security.tenant_context import tenant_scope

    root = tmp_path / "runner-tenant-cas"
    ambient_store = FileSystemCAS(root).with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-a"):
        artifact_ref = ambient_store.put_bytes(
            b"search runner tenant artifact",
            PutOptions(kind="test.search_runner_tenant", media_type="text/plain"),
        )

    runner = SearchLoopRunner(store=FileSystemCAS(root))
    with tenant_scope(None, tenant_id="tenant-b"):
        with pytest.raises(ArtifactOwnershipError):
            runner._store.get_bytes(artifact_ref)


def test_methodjob_evaluator_retains_existing_owned_guarded_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polisyos.scientist.compute.runner as compute_runner
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.resilience import guard_runtime_cas

    _register_method()
    root = tmp_path / "owned-guarded-cas"
    owner_store = FileSystemCAS(root).with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-a"):
        suite_ref = persist_benchmark_suite(
            owner_store,
            BenchmarkSuite(suite_id="owned_guarded_suite", kind="method_job"),
        )
        candidate_ref = persist_mutation_artifact(
            owner_store,
            _V5Mutation(value=0.25),
            inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
            return_selected_profile=True,
        )
    guarded_owner_store = guard_runtime_cas(owner_store)
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=_V5ScoreMethod.signature.fqn,
        method_version=_V5ScoreMethod.signature.version,
        candidate_input_bindings={"value": "value"},
        split=BenchmarkSplit.SELECTION,
    )
    original_run_job = compute_runner.run_job
    factory_returns_exact_handle: list[bool] = []

    def tracked_run_job(spec: JobSpec, **kwargs: Any) -> Any:
        factory = kwargs["store_factory"]
        assert callable(factory)

        def observed_factory(requested_root: Path) -> object:
            active = factory(requested_root)
            factory_returns_exact_handle.append(active is guarded_owner_store)
            return active

        kwargs["store_factory"] = observed_factory
        return original_run_job(spec, **kwargs)

    monkeypatch.setattr(compute_runner, "run_job", tracked_run_job)
    context = {
        "store": guarded_owner_store,
        "policy": _policy(),
        "loop_id": "v5_search",
    }
    with tenant_scope(None, tenant_id="tenant-a"):
        allowed = evaluator.evaluate(candidate_ref, suite_ref, context)
    assert allowed.selection_metrics == {"score": 0.25}
    assert factory_returns_exact_handle
    assert all(factory_returns_exact_handle)

    with tenant_scope(None, tenant_id="tenant-b"):
        with pytest.raises(ArtifactOwnershipError):
            evaluator.evaluate(candidate_ref, suite_ref, context)


def test_methodjob_claims_without_method_result_ref_do_not_enter_generic_history(
    tmp_path,
) -> None:
    """A reopened evaluation with remaining MethodJob claims fails closed without its result."""
    MethodRegistry.get_instance().register(_V5NativeGPScoreMethod, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_method_result_removal_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        unit="dimensionless",
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=2,
        seed=20261027,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5NativeGPScoreMethod.signature.fqn,
            method_version=_V5NativeGPScoreMethod.signature.version,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(unit="dimensionless"),
    )
    result = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        context={"policy_context": {"case": "method_result_identity_removal"}},
        max_iterations=1,
    )
    assert result.history
    original_entry = result.history[0]
    assert original_entry.stage_b_result is not None
    source_evaluation_ref = _selected_evaluation_ref(original_entry.stage_b_result)
    source_evaluation = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"),
        source_evaluation_ref,
        BenchmarkEvaluation,
    )
    assert source_evaluation.metadata["metric_unit"] == "dimensionless"
    positive_history = generator._history_to_evaluations([original_entry])
    assert len(positive_history) == 1
    assert positive_history[0].score_status.value == "available"
    assert positive_history[0].scalar_score is not None
    assert positive_history[0].metadata["search_source_profile_receipt"]["unit"] == "dimensionless"
    assert source_evaluation.method_result_ref is not None
    assert source_evaluation.method_evidence_ref is not None
    assert source_evaluation.method_job_key
    assert source_evaluation.search_source_profile is not None
    assert isinstance(source_evaluation.metadata.get("method_request_basis"), dict)
    source_receipt = source_evaluation.metadata.get("search_source_profile_receipt")
    assert isinstance(source_receipt, dict)
    assert source_receipt.get("method_result_ref") is not None
    method_metadata_keys = {
        "method_fqn",
        "method_version",
        "method_seed",
        "method_job_key",
        "method_input_bindings",
        "method_request_basis",
    }
    assert method_metadata_keys.issubset(source_evaluation.metadata)

    removed_result_evaluation = source_evaluation.model_copy(update={"method_result_ref": None})
    removed_result_ref = persist_benchmark_evaluation(
        store,
        removed_result_evaluation,
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
        return_selected_profile=True,
    )
    reopened_removed_result = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"),
        removed_result_ref,
        BenchmarkEvaluation,
    )
    assert reopened_removed_result.method_result_ref is None
    assert reopened_removed_result.method_evidence_ref == source_evaluation.method_evidence_ref
    assert reopened_removed_result.method_job_key == source_evaluation.method_job_key
    assert reopened_removed_result.search_source_profile == source_evaluation.search_source_profile
    assert (
        reopened_removed_result.metadata["method_request_basis"]
        == source_evaluation.metadata["method_request_basis"]
    )
    assert (
        reopened_removed_result.metadata["search_source_profile_receipt"]
        == source_evaluation.metadata["search_source_profile_receipt"]
    )
    for key in method_metadata_keys:
        assert reopened_removed_result.metadata[key] == source_evaluation.metadata[key]
    removed_manifest = FileSystemCAS(tmp_path / "cas").get_manifest(removed_result_ref)
    assert "method_evidence" in {item.role for item in removed_manifest.inputs}
    assert "method_result" not in {item.role for item in removed_manifest.inputs}

    def history_entry_with_ref(
        entry: Any,
        ref: ArtifactRef,
        *,
        keep_method_provenance: bool,
    ) -> dict[str, Any]:
        assert entry.stage_b_result is not None
        stage_b_result = dict(entry.stage_b_result)
        simulation_results = dict(stage_b_result["simulation_results"])
        simulation_results["evaluation_ref"] = str(ref.artifact_id)
        stage_b_result["simulation_results"] = simulation_results
        stage_b_metadata = dict(stage_b_result["metadata"])
        stage_b_metadata["evaluation_artifact_ref"] = ref.model_dump(mode="json")
        stage_b_metadata["evaluation_id"] = str(ref.artifact_id)
        if not keep_method_provenance:
            stage_b_metadata.pop("provenance_ref", None)
        stage_b_result["metadata"] = stage_b_metadata
        return {
            "candidate": entry.candidate,
            "stage_b_result": stage_b_result,
            "objective_value": entry.objective_value,
            "stage_a_passed": entry.stage_a_passed,
            "duration_seconds": entry.duration_seconds,
        }

    methodjob_history = generator._history_to_evaluations(
        [history_entry_with_ref(original_entry, removed_result_ref, keep_method_provenance=True)]
    )
    assert len(methodjob_history) == 1
    assert methodjob_history[0].scalar_score is None
    assert methodjob_history[0].score_status.value != "available"
    assert "search_source_profile_receipt" not in methodjob_history[0].metadata

    # The typed profile by itself remains a generic profile, not MethodJob identity.
    generic_profile_only = source_evaluation.model_copy(
        update={
            "method_result_ref": None,
            "method_evidence_ref": None,
            "method_job_key": None,
            "execution_work_packet_ref": None,
            "execution_work_packet_status": "unavailable",
            "execution_work_packet_note": None,
            "metadata": {
                key: value
                for key, value in source_evaluation.metadata.items()
                if key
                not in method_metadata_keys
                | {
                    "search_source_profile_receipt",
                    "search_source_evaluation_ref",
                    "search_gp_fit_basis_ref",
                }
            },
        }
    )
    assert generic_profile_only.search_source_profile == source_evaluation.search_source_profile
    assert generic_profile_only.method_result_ref is None
    assert generic_profile_only.method_evidence_ref is None
    assert generic_profile_only.method_job_key is None
    generic_profile_ref = persist_benchmark_evaluation(
        store,
        generic_profile_only,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    erased_manifest = store.get_manifest(generic_profile_ref)
    assert {edge.role for edge in erased_manifest.inputs} == {"candidate", "benchmark_suite"}
    assert load_model_artifact(store, suite_ref, BenchmarkSuite).kind == "method_job"
    generic_profile_history = generator._history_to_evaluations(
        [
            history_entry_with_ref(
                original_entry,
                generic_profile_ref,
                keep_method_provenance=False,
            )
        ]
    )
    assert len(generic_profile_history) == 1
    assert generic_profile_history[0].scalar_score is not None
    assert generic_profile_history[0].score_status.value == "available"
    assert "search_source_profile_receipt" not in generic_profile_history[0].metadata


@pytest.mark.parametrize(
    "retained_roles",
    [
        ("method_result",),
        ("method_evidence",),
        ("method_result", "method_evidence"),
        ("execution_work_packet",),
    ],
)
def test_manifest_methodjob_edges_refuse_scalar_after_payload_claims_are_removed(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    retained_roles: tuple[str, ...],
) -> None:
    """Retained CAS MethodJob roles block generic scalar fallback after payload erasure."""
    MethodRegistry.get_instance().register(_V5NativeGPScoreMethod, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_manifest_methodjob_roles_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        unit="dimensionless",
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=2,
        seed=20261027,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5NativeGPScoreMethod.signature.fqn,
            method_version=_V5NativeGPScoreMethod.signature.version,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(unit="dimensionless"),
    )
    result = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        context={"policy_context": {"case": "manifest_methodjob_role_removal"}},
        max_iterations=1,
    )
    assert result.history
    original_entry = result.history[0]
    assert original_entry.stage_b_result is not None
    source_ref = _selected_evaluation_ref(original_entry.stage_b_result)
    source_evaluation = load_model_artifact(store, source_ref, BenchmarkEvaluation)
    assert source_evaluation.metadata["metric_unit"] == "dimensionless"
    positive_history = generator._history_to_evaluations([original_entry])
    assert len(positive_history) == 1
    assert positive_history[0].score_status.value == "available"
    assert positive_history[0].scalar_score is not None
    assert positive_history[0].metadata["search_source_profile_receipt"]["unit"] == "dimensionless"
    assert source_evaluation.method_result_ref is not None
    assert source_evaluation.method_evidence_ref is not None

    stripped_evaluation = source_evaluation.model_copy(
        update={
            "method_result_ref": None,
            "method_evidence_ref": None,
            "method_job_key": None,
            "execution_work_packet_ref": None,
            "execution_work_packet_status": "unavailable",
            "execution_work_packet_note": None,
            "search_source_profile": None,
            "metadata": {"metric_unit": source_evaluation.metadata["metric_unit"]},
        }
    )
    # The work-packet variant deliberately points to a non-packet MethodJob
    # result: a present-but-fake claim must not make generic fallback available.
    role_refs = {
        "method_result": source_evaluation.method_result_ref,
        "method_evidence": source_evaluation.method_evidence_ref,
        "execution_work_packet": source_evaluation.method_result_ref,
    }
    retained_methodjob_ref = persist_benchmark_evaluation(
        store,
        stripped_evaluation,
        inputs=[
            input_ref_from_artifact_ref(suite_ref, role="benchmark_suite"),
            *[input_ref_from_artifact_ref(role_refs[role], role=role) for role in retained_roles],
        ],
        return_selected_profile=True,
    )
    retained_manifest = store.get_manifest(retained_methodjob_ref)
    manifest_roles = {item.role for item in retained_manifest.inputs}
    assert manifest_roles & set(role_refs) == set(retained_roles)
    reopened = load_model_artifact(store, retained_methodjob_ref, BenchmarkEvaluation)
    assert reopened.method_result_ref is None
    assert reopened.method_evidence_ref is None
    assert reopened.method_job_key is None
    assert reopened.metadata == {"metric_unit": "dimensionless"}

    stage_b_result = dict(original_entry.stage_b_result)
    simulation_results = dict(stage_b_result["simulation_results"])
    simulation_results["evaluation_ref"] = str(retained_methodjob_ref.artifact_id)
    stage_b_result["simulation_results"] = simulation_results
    stage_b_metadata = dict(stage_b_result["metadata"])
    stage_b_metadata["evaluation_artifact_ref"] = retained_methodjob_ref.model_dump(mode="json")
    stage_b_metadata["evaluation_id"] = str(retained_methodjob_ref.artifact_id)
    stage_b_result["metadata"] = stage_b_metadata
    selected_history = {
        "candidate": original_entry.candidate,
        "stage_b_result": stage_b_result,
        "objective_value": original_entry.objective_value,
        "stage_a_passed": original_entry.stage_a_passed,
        "duration_seconds": original_entry.duration_seconds,
    }

    history = generator._history_to_evaluations([selected_history])
    assert len(history) == 1
    assert history[0].scalar_score is None
    assert history[0].score_status.value != "available"

    # Removal control retains the selected manifest and reported unit.
    from polisyos.scientist.methods.autotune import source_profile_verification

    with monkeypatch.context() as control:
        control.setattr(
            source_profile_verification,
            "_search_history_source_claimed",
            lambda _evaluation, _manifest: False,
        )
        unguarded = generator._history_to_evaluations([selected_history])
    assert unguarded[0].score_status.value == "available"
    assert unguarded[0].scalar_score == positive_history[0].scalar_score


def test_generic_benchmark_manifest_roles_remain_eligible_for_generic_history(
    tmp_path,
) -> None:
    """The existing generic BenchmarkEvaluation producer keeps its scalar history path."""

    class GenericBenchmarkEvaluator:
        def evaluate(self, candidate_ref, suite_ref, context):
            store = context["store"]
            candidate = load_model_artifact(store, candidate_ref, _V5Mutation)
            suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
            score = float(candidate.value)
            return BenchmarkEvaluation(
                loop_id="v5_search",
                suite_id=suite.suite_id,
                suite_version=suite.suite_version,
                candidate_ref=candidate_ref,
                selection_metrics={"score": score},
                holdout_metrics={"score": score},
                metadata={"metric_unit": "dimensionless"},
                sample_counts={
                    BenchmarkSplit.SELECTION.value: 1,
                    BenchmarkSplit.HOLDOUT.value: 1,
                },
                guardrails={"score_present": True},
                promotable=True,
                runtime_split_type=BenchmarkSplit.SELECTION,
            )

    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_generic_history_suite", kind="generic"),
        return_selected_profile=True,
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        unit="dimensionless",
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=2,
        seed=20261027,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=GenericBenchmarkEvaluator(),
        promotion_policy=_policy(unit="dimensionless"),
    )
    result = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        context={"policy_context": {"case": "generic_history_source_roles"}},
        max_iterations=1,
    )
    assert result.history
    entry = result.history[0]
    assert entry.stage_b_result is not None
    evaluation_ref = _selected_evaluation_ref(entry.stage_b_result)
    manifest = store.get_manifest(evaluation_ref)
    assert {item.role for item in manifest.inputs} == {"candidate", "benchmark_suite"}

    from polisyos.scientist.methods.autotune.source_profile_verification import (
        _resolve_search_history_source,
        _SearchHistorySourceDisposition,
    )

    resolution = _resolve_search_history_source(
        store=store,
        evaluation_ref=evaluation_ref,
    )
    assert resolution.disposition is _SearchHistorySourceDisposition.NOT_APPLICABLE
    assert resolution.evaluation is not None
    assert resolution.verified is None

    history = generator._history_to_evaluations(result.history)
    assert len(history) == 1
    assert history[0].scalar_score is not None
    assert history[0].score_status.value == "available"
    assert history[0].metadata["search_source_assurance"] == (
        "generic_producer_declared_candidate_only"
    )

    # A later stage edit cannot rewrite the selected producer's score.
    altered = deepcopy(entry)
    assert altered.stage_b_result is not None
    altered.stage_b_result["simulation_results"]["score"] += 0.25
    unbound = generator._history_to_evaluations([altered])[0]
    assert unbound.scalar_score is None
    assert unbound.score_status.value != "available"

    # The selected candidate is the source of optimizer coordinates, not a
    # caller-replaced X paired with the original persisted Y.
    altered_candidate = deepcopy(entry)
    altered_candidate.candidate["value"] = 0.0 if entry.candidate["value"] != 0.0 else 1.0
    assert altered_candidate.stage_b_result == entry.stage_b_result
    unbound_candidate = generator._history_to_evaluations([altered_candidate])[0]
    assert unbound_candidate.scalar_score is None
    assert unbound_candidate.score_status.value != "available"

    # A stale/removed status and a failed source with green stage feedback
    # cannot turn the selected evaluation into a successful observation.
    status_removed = deepcopy(entry)
    assert status_removed.stage_b_result is not None
    status_removed.stage_b_result["feedback"].pop("status")
    unbound_status = generator._history_to_evaluations([status_removed])[0]
    assert unbound_status.scalar_score is None
    assert unbound_status.score_status.value != "available"

    selected_evaluation = load_model_artifact(store, evaluation_ref, BenchmarkEvaluation)
    for source_status, stage_status in (("failed", "ok"), ("review_required", "review_required")):
        limited_ref = _persist_search_benchmark_evaluation(
            store,
            selected_evaluation.model_copy(update={"status": source_status}),
            suite_ref=suite_ref,
        )
        limited_entry = deepcopy(entry)
        assert limited_entry.stage_b_result is not None
        limited_entry.stage_b_result["metadata"]["evaluation_artifact_ref"] = (
            limited_ref.model_dump(mode="json")
        )
        limited_entry.stage_b_result["metadata"]["evaluation_id"] = str(limited_ref.artifact_id)
        limited_entry.stage_b_result["simulation_results"]["evaluation_ref"] = str(
            limited_ref.artifact_id
        )
        limited_entry.stage_b_result["feedback"]["status"] = stage_status
        limited_history = generator._history_to_evaluations([limited_entry])[0]
        assert limited_history.scalar_score is None
        assert limited_history.score_status.value != "available"


def test_search_history_refuses_changed_selected_source_edges(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source receipt cannot authorize another view of any required input."""
    from polisyos.scientist.methods.autotune import source_profile_verification
    from polisyos.scientist.methods.autotune.source_profile_verification import (
        _resolve_search_history_source,
        _SearchHistorySourceDisposition,
    )

    MethodRegistry.get_instance().register(_V5NativeGPScoreMethod, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_selected_edge_suite", kind="method_job"),
    )
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "value", "lower": 0.0, "upper": 1.0}]),
        unit="dimensionless",
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=2,
        seed=20261027,
    )
    spec = SearchLoopSpec(
        loop_id="v5_search",
        mutation_codec=PydanticMutationCodec(_V5Mutation),
        candidate_generator=generator,
        benchmark_evaluator=MethodJobBenchmarkEvaluator(
            method_fqn=_V5NativeGPScoreMethod.signature.fqn,
            method_version=_V5NativeGPScoreMethod.signature.version,
            candidate_input_bindings={"value": "value"},
            split=BenchmarkSplit.SELECTION,
        ),
        promotion_policy=_policy(unit="dimensionless"),
    )
    run = SearchLoopRunner(store=store).run(
        spec,
        suite_ref=suite_ref,
        context={"policy_context": {"case": "selected_source_edge"}},
        max_iterations=1,
    )
    original_entry = run.history[0]
    assert original_entry.stage_b_result is not None
    evaluation_ref = _selected_evaluation_ref(original_entry.stage_b_result)
    evaluation = load_model_artifact(store, evaluation_ref, BenchmarkEvaluation)
    assert evaluation.metadata["metric_unit"] == "dimensionless"
    receipt = evaluation.metadata["search_source_profile_receipt"]
    assert _verify_search_source_profile_receipt(store=store, evaluation_ref=evaluation_ref)
    positive = generator._history_to_evaluations([original_entry])[0]
    assert positive.score_status.value == "available"
    assert positive.scalar_score is not None

    def copy_with_manifest(
        ref: ArtifactRef,
        *,
        inputs: list[InputRef] | None = None,
        producer: ProducerInfo | None = None,
        schema: SchemaInfo | None = None,
    ) -> ArtifactRef:
        manifest = store.get_manifest(ref)
        return store.put_bytes(
            store.get_bytes(ref),
            ArtifactWriteOptions(
                kind=manifest.kind,
                media_type=manifest.media_type,
                schema=manifest.artifact_schema if schema is None else schema,
                producer=manifest.producer if producer is None else producer,
                env=manifest.env,
                inputs=list(manifest.inputs) if inputs is None else inputs,
                canon=manifest.canon,
                governance=manifest.governance,
                tenant_context=manifest.tenant_context,
                same_input_closure=manifest.same_input_closure,
                authority=manifest.authority,
                warnings=manifest.warnings,
            ),
            return_selected_profile=True,
        )

    original_manifest = store.get_manifest(evaluation_ref)
    assert original_manifest.artifact_schema is not None
    foreign_writer = copy_with_manifest(
        evaluation_ref,
        producer=ProducerInfo(component="tests.foreign_benchmark_writer", version="1.0"),
    )
    foreign_schema_version = copy_with_manifest(
        evaluation_ref,
        schema=SchemaInfo(name=original_manifest.artifact_schema.name, version="99.0"),
    )
    for invalid_ref in (foreign_writer, foreign_schema_version):
        assert invalid_ref.artifact_id == evaluation_ref.artifact_id
        assert (
            _verify_search_source_profile_receipt(store=store, evaluation_ref=invalid_ref) is None
        )
        assert (
            _resolve_search_history_source(store=store, evaluation_ref=invalid_ref).disposition
            is _SearchHistorySourceDisposition.REFUSED
        )

    for role, key in (
        ("candidate", "candidate_ref"),
        ("benchmark_suite", "suite_ref"),
        ("method_result", "method_result_ref"),
        ("method_evidence", "method_evidence_ref"),
    ):
        source_ref = ArtifactRef.model_validate(receipt[key])
        matching = [item for item in original_manifest.inputs if item.role == role]
        assert matching == [input_ref_from_artifact_ref(source_ref, role=role)]
        alternative = copy_with_manifest(
            source_ref,
            producer=ProducerInfo(component="tests.selected_view_alternative", version="1"),
        )
        assert alternative.artifact_id == source_ref.artifact_id
        assert alternative.kind == source_ref.kind
        assert alternative.media_type == source_ref.media_type
        assert alternative.manifest_profile_sha256 != source_ref.manifest_profile_sha256
        altered_edge = input_ref_from_artifact_ref(alternative, role=role)
        variants = (
            [altered_edge if item.role == role else item for item in original_manifest.inputs],
            list(original_manifest.inputs) + [altered_edge],
            [
                item.model_copy(update={"manifest_profile_sha256": None})
                if item.role == role
                else item
                for item in original_manifest.inputs
            ],
        )
        for inputs in variants:
            altered_ref = copy_with_manifest(evaluation_ref, inputs=inputs)
            assert altered_ref.artifact_id == evaluation_ref.artifact_id
            assert altered_ref.manifest_profile_sha256 != evaluation_ref.manifest_profile_sha256
            assert store.get_manifest(altered_ref).inputs == inputs
            assert (
                _verify_search_source_profile_receipt(store=store, evaluation_ref=altered_ref)
                is None
            )
            resolution = _resolve_search_history_source(store=store, evaluation_ref=altered_ref)
            assert resolution.disposition is _SearchHistorySourceDisposition.REFUSED
            altered_entry = deepcopy(original_entry)
            assert altered_entry.stage_b_result is not None
            altered_entry.stage_b_result["metadata"]["evaluation_artifact_ref"] = (
                altered_ref.model_dump(mode="json")
            )
            refused = generator._history_to_evaluations([altered_entry])[0]
            assert refused.scalar_score is None
            assert refused.score_status.value != "available"
            assert "search_source_profile_receipt" not in refused.metadata

            # Removal control restores the former role/ID-only predicate while
            # leaving all selected refs, manifests, receipts and payloads intact.
            with monkeypatch.context() as control:
                control.setattr(
                    source_profile_verification,
                    "_search_source_manifest_input_matches",
                    lambda manifest, selected_role, ref: any(
                        edge.role == selected_role and edge.artifact_id == ref.artifact_id
                        for edge in manifest.inputs
                    ),
                )
                unguarded = generator._history_to_evaluations([altered_entry])[0]
            assert unguarded.score_status.value == "available"
            assert unguarded.scalar_score == positive.scalar_score

    # The persisted metadata is a projection, not evidence by itself. Keep
    # the selected result and receipt fixed while falsifying only that unit.
    false_unit = evaluation.model_copy(
        update={"metadata": {**evaluation.metadata, "metric_unit": "USD"}}
    )
    false_unit_ref = _persist_search_benchmark_evaluation(store, false_unit, suite_ref=suite_ref)
    assert _verify_search_source_profile_receipt(store=store, evaluation_ref=false_unit_ref) is None
    false_entry = deepcopy(original_entry)
    assert false_entry.stage_b_result is not None
    false_entry.stage_b_result["metadata"]["evaluation_artifact_ref"] = false_unit_ref.model_dump(
        mode="json"
    )
    false_entry.stage_b_result["metadata"]["evaluation_id"] = str(false_unit_ref.artifact_id)
    false_entry.stage_b_result["simulation_results"]["evaluation_ref"] = str(
        false_unit_ref.artifact_id
    )
    false_history = generator._history_to_evaluations([false_entry])[0]
    assert false_history.scalar_score is None
    assert false_history.score_status.value != "available"
