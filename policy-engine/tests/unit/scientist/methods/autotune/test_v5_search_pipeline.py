from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, ClassVar

import pytest
from pydantic import ConfigDict, Field

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
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
from polisyos.scientist.methods.autotune.runtime import (
    MethodJobBenchmarkEvaluator,
    PydanticMutationCodec,
    _build_search_method_run_profile,
    _method_request_matches_search_run_profile,
    _persist_search_benchmark_evaluation,
    _search_source_fingerprint,
    _verify_search_source_profile_receipt,
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


def test_search_profile_readers_require_selected_data_snapshot_owner_schema(tmp_path) -> None:
    _register_method()
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="v5_snapshot_schema_suite", kind="method_job"),
    )
    candidate_ref = persist_mutation_artifact(
        store,
        _V5Mutation(value=0.25),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )
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


def test_search_parameter_binding_reaches_real_methodjob_and_fresh_receipt(tmp_path) -> None:
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
    evaluation = load_model_artifact(fresh_reader, evaluation_ref, BenchmarkEvaluation)
    assert isinstance(evaluation, BenchmarkEvaluation)
    assert evaluation.method_result_ref is not None
    request_basis = evaluation.metadata["method_request_basis"]
    assert request_basis["schema_version"] == "2"
    assert request_basis["search_parameter_values"] == {"method_offset": candidate["method_offset"]}
    assert request_basis["search_method_run_profile"]["search_parameter_bindings"] == {
        "method_offset": "offset"
    }
    assert request_basis["job_spec"]["method_params"]["offset"] == candidate["method_offset"]
    method_result = load_json_artifact(fresh_reader, evaluation.method_result_ref)
    assert method_result == {"score": candidate["value"] + candidate["method_offset"]}
    verified = _verify_search_source_profile_receipt(
        store=fresh_reader,
        evaluation_ref=evaluation_ref,
    )
    assert verified is not None
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
            method_version=_V5ScoreMethod.signature.version,
            method_params={"offset": 0.0},
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
    source_evaluation_ref = _selected_evaluation_ref(source_stage_b)
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
        objective_directions={policy.primary_metric: policy.direction.value},
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
