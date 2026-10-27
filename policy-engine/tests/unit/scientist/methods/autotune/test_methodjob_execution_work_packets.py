from __future__ import annotations

import copy
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.foundry.methods import BootstrapExecutionWork, MethodRegistry
from polisyos.foundry.methods.catalog.causal import advanced_designs
from polisyos.foundry.methods.catalog.causal.nuisance_layer import TauFitResult
from polisyos.scientist.compute import runner as compute_runner
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    ChampionRegistry,
    MethodDispatchBinding,
    MethodJobExecutionWorkPacket,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    load_json_artifact,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_method_job_execution_work_packet,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.execution_work import (
    _fingerprint_method_request_material,
    fingerprint_method_input_value,
)
from polisyos.scientist.methods.autotune.runtime import (
    MethodJobBenchmarkEvaluator,
    PydanticMutationCodec,
    SearchLoopRunner,
    SequenceCandidateGenerator,
    read_method_job_execution_work_packet,
)
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreStatus,
    OptimizationDirection,
    _configured_search_metric_profile_fingerprint,
    _configured_search_metric_rule_spec,
)


class _DiagnosticCausalCandidate(MutationArtifact):
    candidate_status: Literal["diagnostic_only"] = "diagnostic_only"


class _NonDiagnosticCausalCandidate(MutationArtifact):
    candidate_status: Literal["candidate"] = "candidate"


class _NativeSearchDiagnosticCandidate(_DiagnosticCausalCandidate):
    loop_id: Literal["b157_diagnostic"] = "b157_diagnostic"
    search_coordinate: float = 0.5


def test_method_request_fingerprint_accepts_only_finite_floats_and_preserves_int_bytes() -> None:
    integer_request = {"count": 3, "seed": 17}
    assert _fingerprint_method_request_material(integer_request) == fingerprint(integer_request)
    assert _fingerprint_method_request_material({"clip": 0.4}) != (
        _fingerprint_method_request_material({"clip": 0.41})
    )
    assert _fingerprint_method_request_material({"clip": 0.4, "count": 3}) == (
        _fingerprint_method_request_material({"count": 3, "clip": 0.4})
    )
    for non_finite in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="NaN/Inf forbidden"):
            _fingerprint_method_request_material({"clip": non_finite})


def test_dispatch_input_fingerprint_preserves_scalar_shape_and_value() -> None:
    scalar = fingerprint_method_input_value(0.4)
    vector = fingerprint_method_input_value(np.asarray([0.4]))

    assert scalar.shape == []
    assert vector.shape == [1]
    assert scalar.dtype == vector.dtype
    assert scalar.sha256 == vector.sha256
    big_endian_scalar = fingerprint_method_input_value(np.asarray(0.4, dtype=">f8"))
    big_endian_vector = fingerprint_method_input_value(np.asarray([0.4], dtype=">f8"))
    assert big_endian_scalar == scalar
    assert big_endian_vector == vector
    with pytest.raises(ValueError, match="non-object array"):
        fingerprint_method_input_value(np.asarray([object()], dtype=object))

    scalar_binding = {
        "schema_version": "1.2",
        "method_fqn": "tests.method",
        "method_version": "1.0.0",
        "method_seed": 17,
        "method_params_fingerprint": "a" * 64,
        "input_refs": {},
        "input_schemas": {},
        "input_state_fingerprints": {"value": scalar.model_dump(mode="json")},
    }
    assert MethodDispatchBinding.model_validate(scalar_binding).schema_version == "1.2"
    vector_binding = {
        **scalar_binding,
        "input_state_fingerprints": {"value": vector.model_dump(mode="json")},
    }
    with pytest.raises(ValueError, match="schema 1.2"):
        MethodDispatchBinding.model_validate(vector_binding)
    with pytest.raises(ValueError, match="schema 1.1"):
        MethodDispatchBinding.model_validate({**scalar_binding, "schema_version": "1.1"})
    with pytest.raises(ValueError, match="non-negative"):
        type(scalar).model_validate({**scalar.model_dump(), "shape": [-1]})


@pytest.fixture(autouse=True)
def _reset_method_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _persist_source_inputs(
    store: FileSystemCAS,
    *,
    return_selected_profiles: bool = False,
) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef]:
    n = 40
    x = np.linspace(-1.0, 1.0, n).reshape(-1, 1)
    treatment = np.asarray([0, 1] * (n // 2), dtype=float)
    outcome = 1.0 + x[:, 0] + 0.4 * treatment
    data_ref = store.put_json(
        {
            "X": x.tolist(),
            "X_alternative": (x + 0.25).tolist(),
            "treatment": treatment.tolist(),
            "outcome": outcome.tolist(),
        },
        ArtifactWriteOptions(
            kind="scientist.method_dataset",
            media_type="application/json",
            schema=SchemaInfo(name="tests.MethodDataset", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    snapshot_ref = store.put_json(
        DataSnapshot(data_ref=data_ref),
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[input_ref_from_artifact_ref(data_ref, role="data_ref")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="b157_source_bound",
            suite_version="2.0",
            kind="method_job",
            data_snapshot_ref=snapshot_ref,
        ),
        return_selected_profile=True,
    )
    candidate_ref = persist_mutation_artifact(
        store,
        _DiagnosticCausalCandidate(loop_id="b157_diagnostic"),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=return_selected_profiles,
    )
    return candidate_ref, suite_ref, snapshot_ref


def _persist_parameter_search_source_inputs(
    store: FileSystemCAS,
) -> tuple[ArtifactRef, ArtifactRef]:
    """Persist a fixed-seed nonlinear synthetic source for parameter-effect search."""
    n = 40
    x_axis = np.linspace(-2.25, 2.25, n)
    x = x_axis.reshape(-1, 1)
    rng = np.random.default_rng(20261012)
    treatment_probability = 1.0 / (1.0 + np.exp(-1.8 * x_axis))
    treatment = (rng.random(n) < treatment_probability).astype(float)
    noise = rng.normal(0.0, 0.2, n)
    outcome = (
        0.7 * np.sin(1.6 * x_axis)
        + 0.08 * np.square(x_axis)
        + treatment * (0.2 + 0.45 * np.tanh(x_axis))
        + noise
    )
    data_ref = store.put_json(
        {
            "X": x.tolist(),
            "X_alternative": (x + 0.25).tolist(),
            "treatment": treatment.tolist(),
            "outcome": outcome.tolist(),
        },
        ArtifactWriteOptions(
            kind="scientist.method_dataset",
            media_type="application/json",
            schema=SchemaInfo(name="tests.MethodDataset", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    snapshot_ref = store.put_json(
        DataSnapshot(data_ref=data_ref),
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[input_ref_from_artifact_ref(data_ref, role="data_ref")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="b157_parameter_search_source_bound",
            suite_version="2.0",
            kind="method_job",
            data_snapshot_ref=snapshot_ref,
        ),
    )
    return suite_ref, snapshot_ref


def _selected_evaluation_ref(stage_b: dict[str, Any]) -> ArtifactRef:
    """Read the runtime's full selected evaluation ref, never its legacy bare-ID projection."""
    ref = ArtifactRef.model_validate(stage_b["metadata"]["evaluation_artifact_ref"])
    assert ref.manifest_profile_sha256 is not None
    return ref


def _patch_lightweight_nuisance_layers(monkeypatch: pytest.MonkeyPatch, n: int) -> None:
    x_axis = np.linspace(-1.0, 1.0, n)
    outcome = 1.0 + x_axis
    nuisance = type(
        "ControlledNuisanceOutputs",
        (),
        {
            "propensity": np.full(n, 0.5),
            "mu1": outcome + 0.2,
            "mu0": outcome - 0.2,
            "trim_mask": np.ones(n, dtype=bool),
            "diagnostics": lambda self: {"fixture": "controlled-nuisance-layer"},
            "aipw_scores": lambda self, y, t: np.asarray(y) + np.asarray(t) + 0.1,
        },
    )()
    monkeypatch.setattr(
        advanced_designs,
        "_resolve_nuisance_outputs",
        lambda *args, **kwargs: nuisance,
    )
    monkeypatch.setattr(
        advanced_designs,
        "fit_dr_tau_model",
        lambda x, pseudo, config: TauFitResult(
            cate_predictions=np.linspace(0.5, 1.5, len(x)),
            feature_importances=np.asarray([1.0]),
        ),
    )


def _evaluate(
    *,
    store: FileSystemCAS,
    candidate_ref: ArtifactRef,
    suite_ref: ArtifactRef,
    snapshot_ref: ArtifactRef,
    draws: int,
    attempt_id: str,
    caller_context: dict[str, Any],
) -> Any:
    full_estimation_config = caller_context.get("estimation_config")
    if not isinstance(full_estimation_config, dict):
        raise TypeError("the controlled witness needs the caller's full estimation config")
    full_draws = full_estimation_config.get("n_bootstrap")
    if isinstance(full_draws, bool) or not isinstance(full_draws, int) or draws > full_draws:
        raise ValueError("stage draw request must be bounded by the original full request")
    stage_estimation_config = {**full_estimation_config, "n_bootstrap": draws}
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=advanced_designs.DRLearnerEstimator.signature.fqn,
        method_version=advanced_designs.DRLearnerEstimator.signature.version,
        candidate_input_bindings={},
        data_snapshot_bindings={
            "X": "X",
            "treatment": "treatment",
            "outcome": "outcome",
        },
        method_params={
            "capture_execution_work": True,
            "bootstrap_draws": stage_estimation_config["n_bootstrap"],
            "nuisance_model_family": "lightweight",
            "random_seed": 17,
            "crossfit_folds": 2,
            "n_repeats": 1,
        },
        split=BenchmarkSplit.SELECTION,
        seed=17,
    )
    return evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {
            "store": store,
            "policy": PromotionPolicy(
                loop_id="b157_diagnostic",
                primary_metric="ate",
                direction=MetricDirection.MAXIMIZE,
                compare_split=BenchmarkSplit.SELECTION,
                min_sample_count=1,
            ),
            "loop_id": "b157_diagnostic",
            "run_id": "b157-controlled-run",
            "evaluation_id": "same-original-request",
            "evaluation_attempt_id": attempt_id,
            "data_snapshot_ref": snapshot_ref,
            **caller_context,
        },
    )


def test_methodjob_refuses_data_snapshot_with_foreign_owner_schema(
    tmp_path,
) -> None:
    MethodRegistry.get_instance().register(advanced_designs.DRLearnerEstimator, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref, suite_ref, valid_snapshot_ref = _persist_source_inputs(store)
    snapshot = load_model_artifact(store, valid_snapshot_ref, DataSnapshot)
    assert isinstance(snapshot, DataSnapshot)
    foreign_schema_snapshot_ref = store.put_json(
        snapshot,
        ArtifactWriteOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version="9.0"),
            inputs=[input_ref_from_artifact_ref(snapshot.data_ref, role="data_ref")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(
        ValueError,
        match="canon_profile_typed_artifact_schema_version_unsupported",
    ):
        persist_benchmark_suite(
            store,
            BenchmarkSuite(
                suite_id="invalid_methodjob_source",
                suite_version="2.0",
                kind="method_job",
                data_snapshot_ref=foreign_schema_snapshot_ref,
            ),
        )

    evaluation = _evaluate(
        store=store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=foreign_schema_snapshot_ref,
        draws=8,
        attempt_id="wrong-snapshot-schema",
        caller_context={"estimation_config": {"estimator": "dr_learner", "n_bootstrap": 80}},
    )

    assert evaluation.status == "data_snapshot_unavailable"
    assert any(
        "methodjob_context_snapshot_does_not_match_suite" in note for note in evaluation.notes
    ), evaluation.notes


def _work(packet: MethodJobExecutionWorkPacket) -> BootstrapExecutionWork:
    return BootstrapExecutionWork.model_validate(packet.bootstrap_execution)


def test_source_bound_methodjob_work_packet_supports_same_input_l3_to_l4_witness(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    MethodRegistry.get_instance().register(advanced_designs.DRLearnerEstimator, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref, suite_ref, snapshot_ref = _persist_source_inputs(store)
    _patch_lightweight_nuisance_layers(monkeypatch, 40)
    caller_context = {
        "user_request": "same diagnostic causal request",
        "estimation_config": {"estimator": "dr_learner", "n_bootstrap": 80},
        "input_bindings": {"source": "the-bound-dataset"},
    }
    before = copy.deepcopy(caller_context)

    direct_l4 = _evaluate(
        store=store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=snapshot_ref,
        draws=80,
        attempt_id="direct-l4-attempt",
        caller_context=caller_context,
    )
    chained_l3 = _evaluate(
        store=store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=snapshot_ref,
        draws=40,
        attempt_id="chain-l3-attempt",
        caller_context=caller_context,
    )
    chained_l4 = _evaluate(
        store=store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=snapshot_ref,
        draws=80,
        attempt_id="chain-l4-attempt",
        caller_context=caller_context,
    )

    assert caller_context == before
    assert not direct_l4.promotable and not chained_l3.promotable and not chained_l4.promotable
    assert direct_l4.execution_work_packet_status == "available"
    assert chained_l3.execution_work_packet_status == "available"
    assert chained_l4.execution_work_packet_status == "available"
    assert direct_l4.execution_work_packet_ref is not None
    assert chained_l3.execution_work_packet_ref is not None
    assert chained_l4.execution_work_packet_ref is not None
    for evaluation in (direct_l4, chained_l3, chained_l4):
        assert evaluation.method_result_ref is not None
        assert evaluation.method_result_ref.manifest_profile_sha256 is not None
        assert evaluation.method_evidence_ref is not None
        assert evaluation.method_evidence_ref.manifest_profile_sha256 is not None
        assert evaluation.execution_work_packet_ref.manifest_profile_sha256 is not None

    fresh_reader = FileSystemCAS(tmp_path / "cas")
    persisted_evaluation_refs = [
        persist_benchmark_evaluation(
            fresh_reader,
            evaluation,
            inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        )
        for evaluation in (direct_l4, chained_l3, chained_l4)
    ]
    for evaluation_ref in persisted_evaluation_refs:
        persisted_evaluation = load_model_artifact(
            fresh_reader,
            evaluation_ref,
            BenchmarkEvaluation,
        )
        assert isinstance(persisted_evaluation, BenchmarkEvaluation)
        assert persisted_evaluation.metadata.get("metric_unit") is None
        assert persisted_evaluation.execution_work_packet_status == "available"
        assert persisted_evaluation.execution_work_packet_ref is not None
        evaluation_manifest = fresh_reader.get_manifest(evaluation_ref)
        expected_inputs = {
            ref.role: ref
            for ref in (
                input_ref_from_artifact_ref(persisted_evaluation.candidate_ref, role="candidate"),
                input_ref_from_artifact_ref(suite_ref, role="benchmark_suite"),
                input_ref_from_artifact_ref(
                    persisted_evaluation.method_result_ref, role="method_result"
                ),
                input_ref_from_artifact_ref(
                    persisted_evaluation.method_evidence_ref, role="method_evidence"
                ),
                input_ref_from_artifact_ref(
                    persisted_evaluation.execution_work_packet_ref,
                    role="execution_work_packet",
                ),
            )
        }
        actual_inputs = {ref.role: ref for ref in evaluation_manifest.inputs}
        assert len(evaluation_manifest.inputs) == len(actual_inputs) == len(expected_inputs)
        assert actual_inputs == expected_inputs

    direct_packet = read_method_job_execution_work_packet(
        fresh_reader, direct_l4.execution_work_packet_ref
    )
    l3_packet = read_method_job_execution_work_packet(
        fresh_reader, chained_l3.execution_work_packet_ref
    )
    chained_l4_packet = read_method_job_execution_work_packet(
        fresh_reader, chained_l4.execution_work_packet_ref
    )
    assert direct_packet.schema_version == "1.2"
    assert l3_packet.schema_version == "1.2"
    assert chained_l4_packet.schema_version == "1.2"
    for packet, evaluation in (
        (direct_packet, direct_l4),
        (l3_packet, chained_l3),
        (chained_l4_packet, chained_l4),
    ):
        assert evaluation.execution_work_packet_ref is not None
        assert packet.method_result_ref.manifest_profile_sha256 is not None
        assert packet.method_evidence_ref.manifest_profile_sha256 is not None
        assert evaluation.execution_work_packet_ref.manifest_profile_sha256 is not None
        packet_manifest = fresh_reader.get_manifest(evaluation.execution_work_packet_ref)
        assert packet_manifest.inputs == [
            input_ref_from_artifact_ref(packet.candidate_ref, role="candidate"),
            input_ref_from_artifact_ref(packet.benchmark_suite_ref, role="benchmark_suite"),
            input_ref_from_artifact_ref(packet.data_snapshot_ref, role="data_snapshot"),
            input_ref_from_artifact_ref(packet.data_ref, role="data"),
            input_ref_from_artifact_ref(packet.method_result_ref, role="method_result"),
            input_ref_from_artifact_ref(packet.method_evidence_ref, role="method_evidence"),
        ]
        assert fresh_reader.get_manifest(packet.method_evidence_ref).inputs == [
            input_ref_from_artifact_ref(packet.method_result_ref, role="method_result")
        ]
    direct_evidence = load_json_artifact(fresh_reader, direct_packet.method_evidence_ref)
    assert isinstance(direct_evidence, dict)
    dispatch_binding = MethodDispatchBinding.model_validate(
        direct_evidence["method_dispatch_binding"]
    )
    expected_dispatch_refs = {
        "candidate": direct_packet.candidate_ref,
        "benchmark_suite": direct_packet.benchmark_suite_ref,
        "data_snapshot": direct_packet.data_snapshot_ref,
        "data": direct_packet.data_ref,
    }
    assert dispatch_binding.input_refs == expected_dispatch_refs
    assert dispatch_binding.input_schemas == {
        name: fresh_reader.get_manifest(ref).artifact_schema
        for name, ref in expected_dispatch_refs.items()
    }
    source_data = load_json_artifact(fresh_reader, direct_packet.data_ref)
    assert isinstance(source_data, dict)
    assert dispatch_binding.input_state_fingerprints["X"] == fingerprint_method_input_value(
        np.asarray(source_data["X"])
    )
    direct_result = load_json_artifact(fresh_reader, direct_packet.method_result_ref)
    chained_l4_result = load_json_artifact(fresh_reader, chained_l4_packet.method_result_ref)
    assert direct_result == chained_l4_result
    assert direct_packet.effective_method_config == chained_l4_packet.effective_method_config
    assert (
        direct_packet.data_snapshot_ref
        == l3_packet.data_snapshot_ref
        == chained_l4_packet.data_snapshot_ref
    )
    assert direct_packet.method_seed == l3_packet.method_seed == chained_l4_packet.method_seed == 17
    assert l3_packet.actual_sample_count == direct_packet.actual_sample_count == 40
    assert _work(l3_packet).completed_draw_count == 40
    assert _work(direct_packet).completed_draw_count == 80
    assert _work(chained_l4_packet) == _work(direct_packet)
    assert direct_packet.run_id == l3_packet.run_id == chained_l4_packet.run_id
    assert direct_packet.evaluation_id == l3_packet.evaluation_id == chained_l4_packet.evaluation_id
    assert (
        len(
            {
                direct_packet.evaluation_attempt_id,
                l3_packet.evaluation_attempt_id,
                chained_l4_packet.evaluation_attempt_id,
            }
        )
        == 3
    )
    assert direct_packet.method_profile_fingerprint == chained_l4_packet.method_profile_fingerprint

    forged_counts = BootstrapExecutionWork(
        requested_draw_count=80,
        attempted_draw_count=80,
        completed_draw_count=79,
        failed_draw_count=1,
        unattempted_draw_count=0,
        draw_execution_status="partial",
    )
    forged_packet = direct_packet.model_copy(update={"bootstrap_execution": forged_counts})
    forged_ref = persist_method_job_execution_work_packet(fresh_reader, forged_packet)
    with pytest.raises(ValueError, match="method_work_packet_result_measurement_mismatch"):
        read_method_job_execution_work_packet(fresh_reader, forged_ref)

    false_self_label = direct_packet.model_dump(mode="json")
    false_self_label["candidate_status"] = "publishable"
    with pytest.raises(ValueError):
        MethodJobExecutionWorkPacket.model_validate(false_self_label)

    non_diagnostic_candidate_ref = persist_mutation_artifact(
        fresh_reader,
        _NonDiagnosticCausalCandidate(loop_id="b157_diagnostic"),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )
    packet_repointed_at_non_diagnostic_candidate = direct_packet.model_copy(
        update={"candidate_ref": non_diagnostic_candidate_ref}
    )
    repointed_ref = persist_method_job_execution_work_packet(
        fresh_reader,
        packet_repointed_at_non_diagnostic_candidate,
    )
    with pytest.raises(ValueError, match="method_work_packet_candidate_status_mismatch"):
        read_method_job_execution_work_packet(fresh_reader, repointed_ref)

    for changed_field in ("input_refs", "input_schemas"):
        altered_evidence_payload = copy.deepcopy(direct_evidence)
        altered_binding = altered_evidence_payload["method_dispatch_binding"]
        if changed_field == "input_refs":
            altered_binding["input_refs"]["data"]["manifest_profile_sha256"] = "sha256:" + "0" * 64
        else:
            altered_binding["input_schemas"]["data"]["version"] = "forged"
        altered_evidence_ref = fresh_reader.put_json(
            altered_evidence_payload,
            ArtifactWriteOptions(
                kind="scientist.method_evidence",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.MethodExecutionEvidence",
                    version="0.1.0",
                ),
                inputs=[
                    InputRef(
                        artifact_id=direct_packet.method_result_ref.artifact_id,
                        role="method_result",
                        manifest_profile_sha256=(
                            direct_packet.method_result_ref.manifest_profile_sha256
                        ),
                    )
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        altered_packet_ref = persist_method_job_execution_work_packet(
            fresh_reader,
            direct_packet.model_copy(update={"method_evidence_ref": altered_evidence_ref}),
        )
        with pytest.raises(
            ValueError,
            match="method_work_packet_dispatch_binding_mismatch",
        ):
            read_method_job_execution_work_packet(fresh_reader, altered_packet_ref)

    search_evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=advanced_designs.DRLearnerEstimator.signature.fqn,
        method_version=advanced_designs.DRLearnerEstimator.signature.version,
        candidate_input_bindings={},
        data_snapshot_bindings={
            "X": "X",
            "treatment": "treatment",
            "outcome": "outcome",
        },
        method_params={
            "capture_execution_work": True,
            "bootstrap_draws": 40,
            "random_seed": 17,
            "crossfit_folds": 2,
            "n_repeats": 1,
        },
        split=BenchmarkSplit.SELECTION,
        seed=17,
    )
    search_spec = SearchLoopSpec(
        loop_id="b157_diagnostic",
        mutation_codec=PydanticMutationCodec(_DiagnosticCausalCandidate),
        candidate_generator=SequenceCandidateGenerator(
            [_DiagnosticCausalCandidate(loop_id="b157_diagnostic")]
        ),
        benchmark_evaluator=search_evaluator,
        promotion_policy=PromotionPolicy(
            loop_id="b157_diagnostic",
            primary_metric="ate",
            direction=MetricDirection.MAXIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            min_sample_count=1,
        ),
    )
    search_result = SearchLoopRunner(
        store=fresh_reader,
        registry=ChampionRegistry(root=tmp_path / "registry", store=fresh_reader),
    ).run(
        search_spec,
        suite_ref=suite_ref,
        context={"data_snapshot_ref": snapshot_ref},
        max_iterations=1,
    )
    stage_b = search_result.history[0].stage_b_result
    assert stage_b is not None
    stage_b_results = stage_b["simulation_results"]
    search_evaluation = load_model_artifact(
        fresh_reader,
        stage_b_results["evaluation_ref"],
        BenchmarkEvaluation,
    )
    assert isinstance(search_evaluation, BenchmarkEvaluation)
    assert search_evaluation.execution_work_packet_status == "available"
    assert stage_b_results["ate"] == search_evaluation.selection_metrics["ate"]
    assert stage_b_results["execution_work_packet_ref"] == str(
        search_evaluation.execution_work_packet_ref.artifact_id
    )
    search_packet = read_method_job_execution_work_packet(
        fresh_reader,
        search_evaluation.execution_work_packet_ref,
    )
    assert search_packet.run_id.startswith("search-run:")
    assert search_packet.evaluation_id.startswith("search-evaluation:")
    assert search_packet.evaluation_attempt_id.startswith("search-attempt:")

    source_snapshot = load_model_artifact(fresh_reader, snapshot_ref, DataSnapshot)
    assert isinstance(source_snapshot, DataSnapshot)
    source_data = load_json_artifact(fresh_reader, source_snapshot.data_ref)
    assert isinstance(source_data, dict)
    run_job = compute_runner.run_job

    def _swap_dispatched_x(
        spec,
        *,
        cas_root,
        method_state,
        store_factory: Callable[[Path], ArtifactStore] | None = None,
        capture_dispatch_binding=False,
    ):
        swapped_state = dict(method_state)
        swapped_state["X"] = source_data["X_alternative"]
        return run_job(
            spec,
            cas_root=cas_root,
            method_state=swapped_state,
            store_factory=store_factory,
            capture_dispatch_binding=capture_dispatch_binding,
        )

    monkeypatch.setattr(compute_runner, "run_job", _swap_dispatched_x)
    swapped_input_evaluation = _evaluate(
        store=fresh_reader,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=snapshot_ref,
        draws=80,
        attempt_id="swapped-input-attempt",
        caller_context={
            **caller_context,
            "method_job_seed": 29,
        },
    )
    assert swapped_input_evaluation.execution_work_packet_status == "rejected"
    assert swapped_input_evaluation.execution_work_packet_ref is not None
    swapped_packet = load_model_artifact(
        fresh_reader,
        swapped_input_evaluation.execution_work_packet_ref,
        MethodJobExecutionWorkPacket,
    )
    assert isinstance(swapped_packet, MethodJobExecutionWorkPacket)
    assert swapped_packet.data_slot_bindings == {
        "X": "X",
        "treatment": "treatment",
        "outcome": "outcome",
    }
    assert swapped_packet.actual_sample_count == 40
    assert _work(swapped_packet).completed_draw_count == 80
    with pytest.raises(ValueError, match="method_work_packet_dispatch_binding_mismatch"):
        read_method_job_execution_work_packet(
            fresh_reader,
            swapped_input_evaluation.execution_work_packet_ref,
        )


def test_search_loop_rejects_score_after_source_bound_dispatch_swap(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    MethodRegistry.get_instance().register(advanced_designs.DRLearnerEstimator, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    _, suite_ref, snapshot_ref = _persist_source_inputs(store)
    _patch_lightweight_nuisance_layers(monkeypatch, 40)
    snapshot = load_model_artifact(store, snapshot_ref, DataSnapshot)
    assert isinstance(snapshot, DataSnapshot)
    source_data = load_json_artifact(store, snapshot.data_ref)
    assert isinstance(source_data, dict)
    run_job = compute_runner.run_job

    def _swap_dispatched_x(
        spec,
        *,
        cas_root,
        method_state,
        store_factory: Callable[[Path], ArtifactStore] | None = None,
        capture_dispatch_binding=False,
    ):
        swapped_state = dict(method_state)
        swapped_state["X"] = source_data["X_alternative"]
        return run_job(
            spec,
            cas_root=cas_root,
            method_state=swapped_state,
            store_factory=store_factory,
            capture_dispatch_binding=capture_dispatch_binding,
        )

    monkeypatch.setattr(compute_runner, "run_job", _swap_dispatched_x)
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=advanced_designs.DRLearnerEstimator.signature.fqn,
        method_version=advanced_designs.DRLearnerEstimator.signature.version,
        candidate_input_bindings={},
        data_snapshot_bindings={
            "X": "X",
            "treatment": "treatment",
            "outcome": "outcome",
        },
        method_params={
            "capture_execution_work": True,
            "bootstrap_draws": 40,
            "nuisance_model_family": "lightweight",
            "random_seed": 17,
            "crossfit_folds": 2,
            "n_repeats": 1,
        },
        split=BenchmarkSplit.SELECTION,
        seed=17,
    )
    spec = SearchLoopSpec(
        loop_id="b157_diagnostic",
        mutation_codec=PydanticMutationCodec(_DiagnosticCausalCandidate),
        candidate_generator=SequenceCandidateGenerator(
            [_DiagnosticCausalCandidate(loop_id="b157_diagnostic")]
        ),
        benchmark_evaluator=evaluator,
        promotion_policy=PromotionPolicy(
            loop_id="b157_diagnostic",
            primary_metric="ate",
            direction=MetricDirection.MAXIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            min_sample_count=1,
        ),
    )
    result = SearchLoopRunner(
        store=store,
        registry=ChampionRegistry(root=tmp_path / "registry", store=store),
    ).run(
        spec,
        suite_ref=suite_ref,
        context={"data_snapshot_ref": snapshot_ref},
        max_iterations=1,
    )

    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    evaluation = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"),
        _selected_evaluation_ref(stage_b),
        BenchmarkEvaluation,
    )
    assert isinstance(evaluation, BenchmarkEvaluation)
    assert evaluation.execution_work_packet_status == "rejected"
    assert evaluation.execution_work_packet_ref is not None
    fresh_reader = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(ValueError, match="method_work_packet_dispatch_binding_mismatch"):
        read_method_job_execution_work_packet(
            fresh_reader,
            evaluation.execution_work_packet_ref,
        )

    # The source evaluator records a finite ATE, but rejected source proof must
    # prevent that value from entering the SearchLoop score or promotion path.
    assert "ate" not in stage_b["simulation_results"]
    assert stage_b["feedback"]["promotion_decision"]["promoted"] is False


@pytest.mark.parametrize(
    "failure_mode",
    [
        "missing_packet",
        "unreadable_packet",
        "metric_mismatch",
        "capture_omitted",
        "capture_disabled",
    ],
)
def test_search_loop_uses_execution_evidence_not_diagnostic_packet_as_admission(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    MethodRegistry.get_instance().register(advanced_designs.DRLearnerEstimator, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    _, suite_ref, snapshot_ref = _persist_source_inputs(store)
    _patch_lightweight_nuisance_layers(monkeypatch, 40)
    method_params: dict[str, Any] = {
        "bootstrap_draws": 40,
        "nuisance_model_family": "lightweight",
        "random_seed": 17,
        "crossfit_folds": 2,
        "n_repeats": 1,
    }
    if failure_mode != "capture_omitted":
        method_params["capture_execution_work"] = failure_mode != "capture_disabled"
    evaluator = MethodJobBenchmarkEvaluator(
        method_fqn=advanced_designs.DRLearnerEstimator.signature.fqn,
        method_version=advanced_designs.DRLearnerEstimator.signature.version,
        candidate_input_bindings={},
        data_snapshot_bindings={
            "X": "X",
            "treatment": "treatment",
            "outcome": "outcome",
        },
        method_params=method_params,
        split=BenchmarkSplit.SELECTION,
        seed=17,
    )
    evaluate = evaluator.evaluate

    def _alter_evaluation(candidate_ref, current_suite_ref, context):
        evaluation = evaluate(candidate_ref, current_suite_ref, context)
        if failure_mode in {"capture_omitted", "capture_disabled"}:
            assert np.isfinite(evaluation.selection_metrics["ate"])
            return evaluation
        if failure_mode == "missing_packet":
            return evaluation.model_copy(
                update={
                    "execution_work_packet_ref": None,
                    "execution_work_packet_status": "unavailable",
                    "execution_work_packet_note": "test_removed_packet_ref",
                }
            )
        if failure_mode == "unreadable_packet":
            ref = ArtifactRef(
                artifact_id="sha256:" + "f" * 64,
                kind="scientist.autotune.method_execution_work_packet",
                media_type="application/json",
            )
            return evaluation.model_copy(
                update={
                    "execution_work_packet_ref": ref,
                    "execution_work_packet_status": "available",
                }
            )
        return evaluation.model_copy(
            update={
                "selection_metrics": {
                    **evaluation.selection_metrics,
                    "ate": evaluation.selection_metrics["ate"] + 1.0,
                }
            }
        )

    monkeypatch.setattr(evaluator, "evaluate", _alter_evaluation)
    spec = SearchLoopSpec(
        loop_id="b157_diagnostic",
        mutation_codec=PydanticMutationCodec(_DiagnosticCausalCandidate),
        candidate_generator=SequenceCandidateGenerator(
            [_DiagnosticCausalCandidate(loop_id="b157_diagnostic")]
        ),
        benchmark_evaluator=evaluator,
        promotion_policy=PromotionPolicy(
            loop_id="b157_diagnostic",
            primary_metric="ate",
            direction=MetricDirection.MAXIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            min_sample_count=1,
        ),
    )
    result = SearchLoopRunner(
        store=store,
        registry=ChampionRegistry(root=tmp_path / "registry", store=store),
    ).run(
        spec,
        suite_ref=suite_ref,
        context={"data_snapshot_ref": snapshot_ref},
        max_iterations=1,
    )

    stage_b = result.history[0].stage_b_result
    assert stage_b is not None
    evaluation = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"),
        _selected_evaluation_ref(stage_b),
        BenchmarkEvaluation,
    )
    assert isinstance(evaluation, BenchmarkEvaluation)
    if failure_mode in {"capture_omitted", "capture_disabled"}:
        assert evaluation.status == "measured_candidate"
        assert "ate" in stage_b["simulation_results"]
        assert evaluation.execution_work_packet_status == "unavailable"
        return
    if failure_mode in {"missing_packet", "unreadable_packet"}:
        assert evaluation.status == "measured_candidate"
        assert "ate" in stage_b["simulation_results"]
        assert evaluation.execution_work_packet_status == (
            "unavailable" if failure_mode == "missing_packet" else "available"
        )
        return

    assert evaluation.promotable is False
    assert evaluation.status == "methodjob_source_rejected"
    assert "ate" not in stage_b["simulation_results"]
    assert stage_b["feedback"]["promotion_decision"]["promoted"] is False


@pytest.mark.skipif(
    os.environ.get("POLISYOS_RUN_NATIVE_METHODJOB_WORK") != "1",
    reason="native GP and DR MethodJob use the serialized numerical verification slot",
)
def test_native_methodjob_unitless_ate_explores_without_gp_admission(
    tmp_path,
) -> None:
    MethodRegistry.get_instance().register(advanced_designs.DRLearnerEstimator, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref, snapshot_ref = _persist_parameter_search_source_inputs(store)
    context = {
        "data_snapshot_ref": snapshot_ref.model_dump(mode="json"),
        "policy_context": {"case": "b157_source_bound_diagnostic"},
    }

    def _spec(generator: BayesianCandidateGenerator) -> SearchLoopSpec:
        return SearchLoopSpec(
            loop_id="b157_diagnostic",
            mutation_codec=PydanticMutationCodec(_NativeSearchDiagnosticCandidate),
            candidate_generator=generator,
            benchmark_evaluator=MethodJobBenchmarkEvaluator(
                method_fqn=advanced_designs.DRLearnerEstimator.signature.fqn,
                method_version=advanced_designs.DRLearnerEstimator.signature.version,
                candidate_input_bindings={},
                data_snapshot_bindings={
                    "X": "X",
                    "treatment": "treatment",
                    "outcome": "outcome",
                },
                search_parameter_bindings={"search_coordinate": "propensity_clipping"},
                method_params={
                    "capture_execution_work": True,
                    "bootstrap_draws": 40,
                    "nuisance_model_family": "lightweight",
                    "random_seed": 17,
                    "crossfit_folds": 2,
                    "n_repeats": 1,
                },
                split=BenchmarkSplit.SELECTION,
                seed=17,
            ),
            promotion_policy=PromotionPolicy(
                loop_id="b157_diagnostic",
                primary_metric="ate",
                direction=MetricDirection.MAXIMIZE,
                compare_split=BenchmarkSplit.SELECTION,
                min_sample_count=1,
            ),
        )

    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=[{"name": "search_coordinate", "lower": 0.01, "upper": 0.49}]),
        primary_metric="ate",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=2,
        seed=17,
    )
    assert generator.botorch_available is True
    source_result = SearchLoopRunner(
        store=store,
        registry=ChampionRegistry(root=tmp_path / "source-registry", store=store),
    ).run(
        _spec(generator),
        suite_ref=suite_ref,
        context=context,
        max_iterations=4,
    )
    assert len(source_result.history) == 4

    fresh_reader = FileSystemCAS(tmp_path / "cas")
    observed_ate_values: list[float] = []
    observed_clipping_values: list[float] = []
    observed_method_result_refs: list[ArtifactRef] = []
    observed_evaluation_refs: list[ArtifactRef] = []
    for item in source_result.history:
        stage_b = item.stage_b_result
        assert stage_b is not None
        evaluation_ref = _selected_evaluation_ref(stage_b)
        evaluation = load_model_artifact(
            fresh_reader,
            evaluation_ref,
            BenchmarkEvaluation,
        )
        assert isinstance(evaluation, BenchmarkEvaluation)
        assert evaluation.execution_work_packet_status == "available"
        assert evaluation.execution_work_packet_ref is not None
        assert stage_b["feedback"]["execution_work_packet_status"] == "available"
        assert stage_b["simulation_results"]["ate"] == evaluation.selection_metrics["ate"]
        packet = read_method_job_execution_work_packet(
            fresh_reader, evaluation.execution_work_packet_ref
        )
        candidate = item.candidate
        selected_clipping = candidate["search_coordinate"]
        assert packet.schema_version == "1.3"
        run_profile = packet.search_method_run_profile
        assert run_profile is not None
        assert run_profile.primary_metric == "ate"
        assert run_profile.direction == "maximize"
        assert run_profile.unit is None
        assert run_profile.objective_fingerprint == generator._objective_profile_fingerprint(
            unit=run_profile.unit
        )
        assert generator._optimizer._selected_objective_direction is OptimizationDirection.MINIMIZE
        assert generator._optimizer._selected_objective_rule_spec == (
            _configured_search_metric_rule_spec("ate", "maximize")
        )
        assert run_profile.search_parameter_bindings == {"search_coordinate": "propensity_clipping"}
        assert packet.search_parameter_values == {"search_coordinate": selected_clipping}
        assert packet.configured_method_params["propensity_clipping"] == selected_clipping
        if not observed_clipping_values:
            detached_packet = packet.model_copy(
                update={"search_parameter_values": {"search_coordinate": selected_clipping + 0.1}}
            )
            detached_ref = persist_method_job_execution_work_packet(fresh_reader, detached_packet)
            with pytest.raises(
                ValueError, match="method_work_packet_search_parameter_source_mismatch"
            ):
                read_method_job_execution_work_packet(fresh_reader, detached_ref)
        assert packet.actual_sample_count == 40
        assert _work(packet).completed_draw_count == 40
        method_output = load_json_artifact(fresh_reader, packet.method_result_ref)
        assert isinstance(method_output, dict)
        result_body = method_output.get("result")
        assert isinstance(result_body, dict)
        assert result_body["nuisance_config"]["propensity_clipping"] == selected_clipping
        metric_units = result_body.get("metric_units")
        assert not isinstance(metric_units, dict) or "ate" not in metric_units
        assert evaluation.metadata.get("metric_unit") is None
        diagnostics = result_body.get("nuisance_diagnostics")
        assert isinstance(diagnostics, dict)
        observed_ate_values.append(evaluation.selection_metrics["ate"])
        observed_clipping_values.append(selected_clipping)
        observed_method_result_refs.append(packet.method_result_ref)
        observed_evaluation_refs.append(evaluation_ref)
        assert evaluation.promotable is False
    assert len(observed_evaluation_refs) == 4
    assert (
        len(
            {
                (str(ref.artifact_id), ref.manifest_profile_sha256)
                for ref in observed_evaluation_refs
            }
        )
        == 4
    )
    assert all(np.isfinite(value) for value in observed_ate_values)
    assert len(set(observed_clipping_values)) == 4
    assert len(observed_method_result_refs) == 4
    assert (
        len(
            {
                (str(ref.artifact_id), ref.manifest_profile_sha256)
                for ref in observed_method_result_refs
            }
        )
        == 4
    )
    persisted_run_profile = generator._search_method_run_profile
    assert persisted_run_profile is not None
    invalid_profiles = (
        persisted_run_profile.model_copy(update={"direction": "minimize"}),
        persisted_run_profile.model_copy(update={"unit": "incompatible-unit"}),
        persisted_run_profile.model_copy(update={"objective_fingerprint": "0" * 64}),
    )
    for invalid_profile in invalid_profiles:
        with pytest.raises(ValueError, match="selected Bayesian objective basis"):
            generator.set_search_method_run_profile(invalid_profile)

    run_context = generator._search_run_context_fingerprint
    assert isinstance(run_context, str) and run_context
    wrong_source_rule_fingerprint = _configured_search_metric_profile_fingerprint(
        "ate", "minimize", persisted_run_profile.unit
    )
    assert wrong_source_rule_fingerprint is not None
    with pytest.raises(
        ValueError, match="configured search run differs from selected objective rule and unit"
    ):
        generator._optimizer.set_search_run_profile(
            context_fingerprint=run_context,
            objective_fingerprint=wrong_source_rule_fingerprint,
            objective_unit=persisted_run_profile.unit,
        )
    wrong_unit_fingerprint = generator._objective_profile_fingerprint(unit="incompatible-unit")
    assert wrong_unit_fingerprint is not None
    with pytest.raises(
        RuntimeError, match="selected objective unit cannot change after score admission"
    ):
        generator._optimizer.set_search_run_profile(
            context_fingerprint=run_context,
            objective_fingerprint=wrong_unit_fingerprint,
            objective_unit="incompatible-unit",
        )

    last_history_item = source_result.history[-1]
    assert last_history_item.candidate["_strategy_metadata"]["source"] == "sobol_init"
    last_stage_b = last_history_item.stage_b_result
    assert last_stage_b is not None
    last_evaluation_ref = _selected_evaluation_ref(last_stage_b)
    assert last_evaluation_ref == observed_evaluation_refs[-1]
    source_evaluation = load_model_artifact(
        fresh_reader,
        last_evaluation_ref,
        BenchmarkEvaluation,
    )
    assert isinstance(source_evaluation, BenchmarkEvaluation)
    profile = source_evaluation.search_source_profile
    assert profile is not None
    assert profile.profile_kind == "configured_native_gp"
    assert profile.proposal_source == "sobol_init"
    assert profile.gp_model_fqn is None
    assert profile.warm_start_eligible is False
    assert profile.training_observation_count is None
    assert "search_gp_fit_basis_ref" not in source_evaluation.metadata

    source_evaluations = generator._history_to_evaluations(source_result.history)
    assert len(source_evaluations) == len(source_result.history) == 4
    assert all(evaluation.status.value == "stage_b_error" for evaluation in source_evaluations)
    assert all(
        evaluation.score_status is ObjectiveScoreStatus.UNAVAILABLE
        for evaluation in source_evaluations
    )
    assert all(evaluation.scalar_score is None for evaluation in source_evaluations)
    assert all(
        evaluation.score_assessment is not None
        and evaluation.score_assessment.limitation == "objective_rule_unit_not_established"
        for evaluation in source_evaluations
    )
    assert generator._optimizer._effective_training_corpus(source_evaluations) == []
    assert generator._optimizer._model is None

    skipped_history = [{"candidate": {"unrelated_parameter": index}} for index in range(7)]
    assert generator._history_to_evaluations(skipped_history) == []
    candidate_after_skipped_history = generator.generate(
        skipped_history,
        current_best=None,
        context=context,
    )
    expected_vector = generator._search_space.sample_sobol(n_samples=8, seed=17)[7]
    expected_params = generator._search_space.denormalize(expected_vector)
    assert (
        candidate_after_skipped_history["search_coordinate"] == expected_params["search_coordinate"]
    )
    assert generator._optimizer._sobol_cursor == 8


@pytest.mark.skipif(
    os.environ.get("POLISYOS_RUN_NATIVE_METHODJOB_WORK") != "1",
    reason="native DR L3/L4 fit uses the serialized numerical verification slot",
)
def test_native_source_bound_methodjob_direct_l4_matches_l3_to_l4(tmp_path) -> None:
    MethodRegistry.get_instance().register(advanced_designs.DRLearnerEstimator, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref, suite_ref, snapshot_ref = _persist_source_inputs(store)
    caller_context = {
        "user_request": "same native diagnostic causal request",
        "estimation_config": {"estimator": "dr_learner", "n_bootstrap": 80},
        "input_bindings": {"source": "the-bound-dataset"},
    }
    caller_context_before = copy.deepcopy(caller_context)

    direct_l4 = _evaluate(
        store=store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=snapshot_ref,
        draws=80,
        attempt_id="native-direct-l4-attempt",
        caller_context=caller_context,
    )
    chained_l3 = _evaluate(
        store=store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=snapshot_ref,
        draws=40,
        attempt_id="native-chain-l3-attempt",
        caller_context=caller_context,
    )
    chained_l4 = _evaluate(
        store=store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=snapshot_ref,
        draws=80,
        attempt_id="native-chain-l4-attempt",
        caller_context=caller_context,
    )

    assert caller_context == caller_context_before
    assert not direct_l4.promotable and not chained_l3.promotable and not chained_l4.promotable
    assert all(
        evaluation.execution_work_packet_status == "available"
        and evaluation.execution_work_packet_ref is not None
        for evaluation in (direct_l4, chained_l3, chained_l4)
    )
    fresh_reader = FileSystemCAS(tmp_path / "cas")
    packets = [
        read_method_job_execution_work_packet(fresh_reader, evaluation.execution_work_packet_ref)
        for evaluation in (direct_l4, chained_l3, chained_l4)
    ]
    direct_packet, l3_packet, chained_l4_packet = packets
    direct_result = load_json_artifact(fresh_reader, direct_packet.method_result_ref)
    chained_l4_result = load_json_artifact(fresh_reader, chained_l4_packet.method_result_ref)

    assert direct_packet.candidate_status == "diagnostic_only"
    assert (
        direct_packet.data_snapshot_ref
        == l3_packet.data_snapshot_ref
        == chained_l4_packet.data_snapshot_ref
    )
    assert direct_packet.method_seed == l3_packet.method_seed == chained_l4_packet.method_seed == 17
    assert direct_packet.effective_method_config == chained_l4_packet.effective_method_config
    assert direct_packet.method_profile_fingerprint == chained_l4_packet.method_profile_fingerprint
    assert direct_packet.method_job_key == chained_l4_packet.method_job_key
    assert direct_result == chained_l4_result
    assert l3_packet.actual_sample_count == direct_packet.actual_sample_count == 40
    assert _work(l3_packet).requested_draw_count == _work(l3_packet).completed_draw_count == 40
    assert (
        _work(direct_packet).requested_draw_count == _work(direct_packet).completed_draw_count == 80
    )
    assert _work(chained_l4_packet) == _work(direct_packet)
    assert direct_packet.run_id == l3_packet.run_id == chained_l4_packet.run_id
    assert direct_packet.evaluation_id == l3_packet.evaluation_id == chained_l4_packet.evaluation_id
    assert len({packet.evaluation_attempt_id for packet in packets}) == 3
