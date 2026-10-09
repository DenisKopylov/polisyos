from __future__ import annotations

import copy
import os
from typing import Any, Literal

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.foundry.methods import MethodRegistry
from polisyos.foundry.methods.catalog.causal import advanced_designs
from polisyos.foundry.methods.catalog.causal.ci_backends import BootstrapExecutionWork
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
from polisyos.scientist.methods.autotune.execution_work import (
    fingerprint_method_input_value,
)
from polisyos.scientist.methods.autotune.runtime import (
    MethodJobBenchmarkEvaluator,
    PydanticMutationCodec,
    SearchLoopRunner,
    SequenceCandidateGenerator,
    read_method_job_execution_work_packet,
)


class _DiagnosticCausalCandidate(MutationArtifact):
    candidate_status: Literal["diagnostic_only"] = "diagnostic_only"


class _NonDiagnosticCausalCandidate(MutationArtifact):
    candidate_status: Literal["candidate"] = "candidate"


@pytest.fixture(autouse=True)
def _reset_method_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _persist_source_inputs(store: FileSystemCAS) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef]:
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
    )
    snapshot_ref = store.put_json(
        DataSnapshot(data_ref=data_ref),
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[InputRef(artifact_id=data_ref.artifact_id, role="data_ref")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="b157_source_bound", kind="method_job"),
    )
    candidate_ref = persist_mutation_artifact(
        store,
        _DiagnosticCausalCandidate(loop_id="b157_diagnostic"),
        inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
    )
    return candidate_ref, suite_ref, snapshot_ref


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

    fresh_reader = FileSystemCAS(tmp_path / "cas")
    persisted_evaluation_refs = [
        persist_benchmark_evaluation(fresh_reader, evaluation)
        for evaluation in (direct_l4, chained_l3, chained_l4)
    ]
    for evaluation_ref in persisted_evaluation_refs:
        persisted_evaluation = load_model_artifact(
            fresh_reader,
            evaluation_ref,
            BenchmarkEvaluation,
        )
        assert isinstance(persisted_evaluation, BenchmarkEvaluation)
        assert persisted_evaluation.execution_work_packet_status == "available"
        assert persisted_evaluation.execution_work_packet_ref is not None
        evaluation_manifest = fresh_reader.get_manifest(evaluation_ref)
        assert any(
            item.role == "execution_work_packet"
            and item.artifact_id == persisted_evaluation.execution_work_packet_ref.artifact_id
            for item in evaluation_manifest.inputs
        )

    direct_packet = read_method_job_execution_work_packet(
        fresh_reader, direct_l4.execution_work_packet_ref
    )
    l3_packet = read_method_job_execution_work_packet(
        fresh_reader, chained_l3.execution_work_packet_ref
    )
    chained_l4_packet = read_method_job_execution_work_packet(
        fresh_reader, chained_l4.execution_work_packet_ref
    )
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
        data_snapshot_bindings={"X": "X", "treatment": "treatment", "outcome": "outcome"},
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

    def _swap_dispatched_x(spec, *, cas_root, method_state):
        swapped_state = dict(method_state)
        swapped_state["X"] = source_data["X_alternative"]
        return run_job(spec, cas_root=cas_root, method_state=swapped_state)

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
