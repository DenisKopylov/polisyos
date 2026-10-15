from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, ProducerInfo
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods import MethodRegistry
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    ChampionRegistry,
    MetricDirection,
    PromotionPolicy,
    SearchLoopSpec,
    load_model_artifact,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.autotune.runtime import (
    PydanticMutationCodec,
    SearchLoopRunner,
    SequenceCandidateGenerator,
)
from polisyos.scientist.methods.backtesting.adversarial import run_phase_d4_challenge_suites
from polisyos.scientist.methods.doe.stress_report import (
    _STRESS_OUTCOME_BASIS_ARTIFACT_KIND,
    _STRESS_OUTCOME_BASIS_SCHEMA_NAME,
    _STRESS_OUTCOME_BASIS_SCHEMA_VERSION,
    _STRESS_TEST_REPORT_ARTIFACT_KIND,
    _STRESS_TEST_REPORT_SCHEMA_NAME,
    StressScoreComponent,
    resolve_stress_score_components,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.promotion_evidence import (
    PromotionEvidenceBundle,
    _MethodJobPromotionSourceBasis,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    _build_promotion_benchmark_source_basis,
    build_selection_benchmark_evaluation,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

_HELPER_PATH = (
    Path(__file__).resolve().parents[4]
    / "unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py"
)
_HELPER_SPEC = importlib.util.spec_from_file_location(
    "e02_methodjob_promotion_test_helpers", _HELPER_PATH
)
assert _HELPER_SPEC is not None and _HELPER_SPEC.loader is not None
_helpers = importlib.util.module_from_spec(_HELPER_SPEC)
sys.modules[_HELPER_SPEC.name] = _helpers
_HELPER_SPEC.loader.exec_module(_helpers)

_D4_HELPER_PATH = (
    Path(__file__).resolve().parents[4]
    / "unit/scientist/search/test_phase_d4_runtime_integration.py"
)
_D4_HELPER_SPEC = importlib.util.spec_from_file_location(
    "e02_methodjob_promotion_d4_helpers", _D4_HELPER_PATH
)
assert _D4_HELPER_SPEC is not None and _D4_HELPER_SPEC.loader is not None
_d4_helpers = importlib.util.module_from_spec(_D4_HELPER_SPEC)
sys.modules[_D4_HELPER_SPEC.name] = _d4_helpers
_D4_HELPER_SPEC.loader.exec_module(_d4_helpers)


def _promotion_basis(run_id: str, candidate_ref: ArtifactRef, suite_ref: ArtifactRef):
    return _MethodJobPromotionSourceBasis(
        expected_run_id=run_id,
        expected_candidate_ref=candidate_ref,
        expected_suite_ref=suite_ref,
        expected_policy=PromotionPolicy(
            loop_id="b157_diagnostic",
            primary_metric="ate",
            direction=MetricDirection.MAXIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            min_sample_count=1,
        ),
    )


def _assert_admitted(
    *,
    store: FileSystemCAS,
    candidate_ref: ArtifactRef,
    evaluation_ref: ArtifactRef,
    run_id: str,
    suite_ref: ArtifactRef,
) -> None:
    bundle = PromotionEvidenceBundle(
        run_id=run_id,
        produced_by_run_id=run_id,
        candidate_ref=candidate_ref,
        selection_evaluation_ref=evaluation_ref,
    )
    bundle.assert_runtime_compatible(
        run_id=run_id,
        store=store,
        expected_loop_id="b157_diagnostic",
        source_basis_by_role={
            "selection_evaluation_ref": _promotion_basis(
                run_id,
                candidate_ref,
                suite_ref,
            )
        },
    )


def _assert_refused(
    *,
    store: FileSystemCAS,
    candidate_ref: ArtifactRef,
    evaluation_ref: ArtifactRef,
    run_id: str,
    suite_ref: ArtifactRef,
) -> None:
    bundle = PromotionEvidenceBundle(
        run_id=run_id,
        produced_by_run_id=run_id,
        candidate_ref=candidate_ref,
        selection_evaluation_ref=evaluation_ref,
    )
    with pytest.raises(ValueError):
        bundle.assert_runtime_compatible(
            run_id=run_id,
            store=store,
            expected_loop_id="b157_diagnostic",
            source_basis_by_role={
                "selection_evaluation_ref": _promotion_basis(
                    run_id,
                    candidate_ref,
                    suite_ref,
                )
            },
        )


def _copy_exact_source_closure(
    source: FileSystemCAS,
    receiver: FileSystemCAS,
    ref: ArtifactRef,
    *,
    skip_default_artifact_ids: set[str] | None = None,
    seen: set[tuple[str, str | None]] | None = None,
) -> None:
    """Import the producer-selected CAS closure without recreating its manifests."""
    skipped = skip_default_artifact_ids or set()
    visited = seen if seen is not None else set()
    identity = (str(ref.artifact_id), ref.manifest_profile_sha256)
    if identity in visited:
        return
    visited.add(identity)

    manifest = source.get_manifest(ref)
    if not (identity[0] in skipped and ref.manifest_profile_sha256 is None):
        receiver.import_exact_view(
            source.get_bytes(ref),
            source.get_raw_manifest_bytes(ref),
            artifact_id=ref,
        )
    for edge in manifest.inputs:
        child_manifest = (
            source.get_manifest_by_profile(edge.artifact_id, edge.manifest_profile_sha256)
            if edge.manifest_profile_sha256 is not None
            else source.get_manifest(edge.artifact_id)
        )
        child_ref = ArtifactRef(
            artifact_id=edge.artifact_id,
            kind=child_manifest.kind,
            media_type=child_manifest.media_type,
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
        _copy_exact_source_closure(
            source,
            receiver,
            child_ref,
            skip_default_artifact_ids=skipped,
            seen=visited,
        )


def _install_foreign_owner_default(
    *,
    source: FileSystemCAS,
    receiver: FileSystemCAS,
    ref: ArtifactRef,
    parent_ref: ArtifactRef,
    role: str,
    producer_component: str | None,
) -> ArtifactRef:
    manifest = source.get_manifest(ref)
    opts = ArtifactWriteOptions(
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema=manifest.artifact_schema,
        producer=(
            ProducerInfo(component=producer_component, version="9.9")
            if producer_component is not None
            else manifest.producer
        ),
        inputs=(
            [input_ref_from_artifact_ref(parent_ref, role=role)]
            if role != "preserve"
            else list(manifest.inputs)
        ),
    )
    foreign_ref = receiver.put_bytes(source.get_bytes(ref), opts)
    foreign_manifest = receiver.get_manifest(foreign_ref)
    assert foreign_ref.artifact_id == ref.artifact_id
    assert source.get_bytes(ref) == receiver.get_bytes(foreign_ref)
    assert foreign_manifest.kind == manifest.kind
    assert foreign_manifest.media_type == manifest.media_type
    assert foreign_manifest.artifact_schema == manifest.artifact_schema
    return foreign_ref


@pytest.mark.integration
def test_real_v1_and_v2_methodjob_sources_are_content_bound_before_promotion(tmp_path, monkeypatch):
    MethodRegistry.reset_instance()

    MethodRegistry.get_instance().register(
        _helpers.advanced_designs.DRLearnerEstimator,
        override=True,
    )
    store = FileSystemCAS(tmp_path / "cas")
    candidate_ref, suite_ref, snapshot_ref = _helpers._persist_source_inputs(store)
    _helpers._patch_lightweight_nuisance_layers(monkeypatch, 40)
    caller_context = {
        "user_request": "controlled source-bound methodjob",
        "estimation_config": {"estimator": "dr_learner", "n_bootstrap": 80},
        "input_bindings": {"source": "controlled-fixture"},
    }
    v1_run_id = "b157-controlled-run"
    v2_run_id = "b157-controlled-search-run"
    policy = PromotionPolicy(
        loop_id="b157_diagnostic",
        primary_metric="ate",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
        min_sample_count=1,
    )

    # Producer v1: the direct MethodJob evaluator and canonical benchmark writer.
    legacy_v1_evaluation = _helpers._evaluate(
        store=store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=snapshot_ref,
        draws=80,
        attempt_id="promotion-v1",
        caller_context=caller_context,
    )
    legacy_v1_ref = persist_benchmark_evaluation(
        store,
        legacy_v1_evaluation,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
    )
    assert legacy_v1_evaluation.execution_work_packet_ref is not None
    assert candidate_ref.manifest_profile_sha256 is None
    assert suite_ref.manifest_profile_sha256 is None
    assert legacy_v1_evaluation.candidate_ref.manifest_profile_sha256 is None
    assert legacy_v1_ref.manifest_profile_sha256 is None
    legacy_v1_packet = _helpers.read_method_job_execution_work_packet(
        store,
        legacy_v1_evaluation.execution_work_packet_ref,
    )
    assert legacy_v1_packet.run_id == v1_run_id
    assert legacy_v1_packet.candidate_ref.manifest_profile_sha256 is None
    assert legacy_v1_packet.benchmark_suite_ref.manifest_profile_sha256 is None

    # A profileless reference is not a portable owner identity. Reopen the actual
    # producer closure in fresh receiver CASes whose default candidate/suite views
    # retain the same payload, kind, media type, and schema while changing only
    # owner producer or input edges. Every variant must be held at admission.
    fresh_receiver_cases = (
        ("profileless_baseline", None, None, "preserve", None),
        ("candidate_foreign_producer", candidate_ref, suite_ref, "preserve", "foreign.candidate"),
        ("candidate_foreign_input", candidate_ref, suite_ref, "foreign_parent", None),
        ("suite_foreign_producer", suite_ref, candidate_ref, "preserve", "foreign.suite"),
        ("suite_foreign_input", suite_ref, candidate_ref, "foreign_parent", None),
    )
    for case_name, owner_ref, parent_ref, role, producer_component in fresh_receiver_cases:
        receiver = FileSystemCAS(tmp_path / "receivers" / case_name)
        skipped_ids: set[str] = set()
        if owner_ref is not None and parent_ref is not None:
            foreign_ref = _install_foreign_owner_default(
                source=store,
                receiver=receiver,
                ref=owner_ref,
                parent_ref=parent_ref,
                role=role,
                producer_component=producer_component,
            )
            assert foreign_ref.artifact_id == owner_ref.artifact_id
            assert foreign_ref.manifest_profile_sha256 is None
            skipped_ids.add(str(owner_ref.artifact_id))
        _copy_exact_source_closure(
            store,
            receiver,
            legacy_v1_ref,
            skip_default_artifact_ids=skipped_ids,
        )
        with pytest.raises(ValueError, match="selected manifest profile"):
            _assert_admitted(
                store=receiver,
                candidate_ref=candidate_ref,
                evaluation_ref=legacy_v1_ref,
                run_id=v1_run_id,
                suite_ref=suite_ref,
            )

    with pytest.raises(ValueError, match="selected manifest profile"):
        _assert_admitted(
            store=store,
            candidate_ref=candidate_ref,
            evaluation_ref=legacy_v1_ref,
            run_id=v1_run_id,
            suite_ref=suite_ref,
        )

    # The source-selected v1 producer returns profile-bearing refs; those exact
    # refs survive a fresh reader and are admitted against the same measured work.
    candidate_ref, suite_ref, snapshot_ref = _helpers._persist_source_inputs(
        store,
        return_selected_profiles=True,
    )
    assert candidate_ref.manifest_profile_sha256 is not None
    assert suite_ref.manifest_profile_sha256 is not None
    v1_evaluation = _helpers._evaluate(
        store=store,
        candidate_ref=candidate_ref,
        suite_ref=suite_ref,
        snapshot_ref=snapshot_ref,
        draws=80,
        attempt_id="promotion-v1-selected",
        caller_context=caller_context,
    )
    v1_ref = persist_benchmark_evaluation(
        store,
        v1_evaluation,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    assert v1_ref.manifest_profile_sha256 is not None
    assert v1_evaluation.execution_work_packet_ref is not None
    v1_packet = _helpers.read_method_job_execution_work_packet(
        store,
        v1_evaluation.execution_work_packet_ref,
    )
    assert v1_packet.run_id == v1_run_id
    assert v1_packet.candidate_ref == candidate_ref
    assert v1_packet.benchmark_suite_ref == suite_ref
    assert v1_packet.candidate_ref.manifest_profile_sha256 is not None
    assert v1_packet.benchmark_suite_ref.manifest_profile_sha256 is not None
    v1_packet_inputs = {
        item.role: item
        for item in store.get_manifest(v1_evaluation.execution_work_packet_ref).inputs
    }
    assert v1_packet_inputs["candidate"] == input_ref_from_artifact_ref(
        candidate_ref,
        role="candidate",
    )
    assert v1_packet_inputs["benchmark_suite"] == input_ref_from_artifact_ref(
        suite_ref,
        role="benchmark_suite",
    )
    v1_evaluation_inputs = {item.role: item for item in store.get_manifest(v1_ref).inputs}
    assert v1_evaluation_inputs["candidate"] == input_ref_from_artifact_ref(
        candidate_ref,
        role="candidate",
    )
    assert v1_evaluation_inputs["benchmark_suite"] == input_ref_from_artifact_ref(
        suite_ref,
        role="benchmark_suite",
    )
    _assert_admitted(
        store=store,
        candidate_ref=candidate_ref,
        evaluation_ref=v1_ref,
        run_id=v1_run_id,
        suite_ref=suite_ref,
    )

    selected_receiver = FileSystemCAS(
        tmp_path / "receivers" / "selected-source-with-foreign-defaults"
    )
    foreign_candidate_default = _install_foreign_owner_default(
        source=store,
        receiver=selected_receiver,
        ref=candidate_ref,
        parent_ref=suite_ref,
        role="foreign_candidate_parent",
        producer_component="foreign.candidate",
    )
    foreign_suite_default = _install_foreign_owner_default(
        source=store,
        receiver=selected_receiver,
        ref=suite_ref,
        parent_ref=candidate_ref,
        role="foreign_suite_parent",
        producer_component="foreign.suite",
    )
    assert foreign_candidate_default.artifact_id == candidate_ref.artifact_id
    assert foreign_suite_default.artifact_id == suite_ref.artifact_id
    assert selected_receiver.get_manifest(foreign_candidate_default).producer is not None
    assert (
        str(selected_receiver.get_manifest(foreign_candidate_default).producer.component)
        == "foreign.candidate"
    )
    assert selected_receiver.get_manifest(foreign_suite_default).producer is not None
    assert (
        str(selected_receiver.get_manifest(foreign_suite_default).producer.component)
        == "foreign.suite"
    )
    assert selected_receiver.get_manifest(foreign_candidate_default).inputs[0].role == (
        "foreign_candidate_parent"
    )
    assert selected_receiver.get_manifest(foreign_suite_default).inputs[0].role == (
        "foreign_suite_parent"
    )
    _copy_exact_source_closure(
        store,
        selected_receiver,
        v1_ref,
        skip_default_artifact_ids={str(candidate_ref.artifact_id), str(suite_ref.artifact_id)},
    )
    assert (
        selected_receiver.get_manifest(candidate_ref).producer
        == store.get_manifest(candidate_ref).producer
    )
    assert (
        selected_receiver.get_manifest(suite_ref).producer == store.get_manifest(suite_ref).producer
    )
    _assert_admitted(
        store=selected_receiver,
        candidate_ref=candidate_ref,
        evaluation_ref=v1_ref,
        run_id=v1_run_id,
        suite_ref=suite_ref,
    )

    # Producer v2: SearchLoopRunner owns the selected profile and persisted report.
    search_evaluator = _helpers.MethodJobBenchmarkEvaluator(
        method_fqn=_helpers.advanced_designs.DRLearnerEstimator.signature.fqn,
        method_version=_helpers.advanced_designs.DRLearnerEstimator.signature.version,
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
    search_result = SearchLoopRunner(
        store=store,
        registry=ChampionRegistry(root=tmp_path / "registry", store=store),
    ).run(
        SearchLoopSpec(
            loop_id="b157_diagnostic",
            mutation_codec=PydanticMutationCodec(_helpers._DiagnosticCausalCandidate),
            candidate_generator=SequenceCandidateGenerator(
                [_helpers._DiagnosticCausalCandidate(loop_id="b157_diagnostic")]
            ),
            benchmark_evaluator=search_evaluator,
            promotion_policy=policy,
        ),
        suite_ref=suite_ref,
        context={"data_snapshot_ref": snapshot_ref, "run_id": v2_run_id},
        max_iterations=1,
    )
    stage_b = search_result.history[0].stage_b_result
    assert stage_b is not None
    v2_ref = _helpers._selected_evaluation_ref(stage_b)
    v2_evaluation = load_model_artifact(store, v2_ref, BenchmarkEvaluation)
    assert isinstance(v2_evaluation, BenchmarkEvaluation)
    assert v2_evaluation.candidate_ref.manifest_profile_sha256 is not None
    assert suite_ref.manifest_profile_sha256 is not None
    assert v2_evaluation.execution_work_packet_ref is not None
    v2_packet = _helpers.read_method_job_execution_work_packet(
        store,
        v2_evaluation.execution_work_packet_ref,
    )
    assert v2_packet.run_id == v2_run_id
    _assert_admitted(
        store=store,
        candidate_ref=v2_evaluation.candidate_ref,
        evaluation_ref=v2_ref,
        run_id=v2_run_id,
        suite_ref=suite_ref,
    )

    # Removing the caller's source intent cannot turn the packet's self-label into authority.
    no_basis_bundle = PromotionEvidenceBundle(
        run_id=v1_run_id,
        produced_by_run_id=v1_run_id,
        candidate_ref=candidate_ref,
        selection_evaluation_ref=v1_ref,
    )
    with pytest.raises(ValueError, match="source basis"):
        no_basis_bundle.assert_runtime_compatible(
            run_id=v1_run_id,
            store=store,
            expected_loop_id="b157_diagnostic",
        )

    # Replaying the same measured work onto a different candidate is refused.
    other_candidate_ref = _helpers.persist_mutation_artifact(
        store,
        _helpers._DiagnosticCausalCandidate(
            loop_id="b157_diagnostic",
            notes=["different source candidate"],
        ),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    replayed_evaluation = v1_evaluation.model_copy(update={"candidate_ref": other_candidate_ref})
    replayed_ref = persist_benchmark_evaluation(
        store,
        replayed_evaluation,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    _assert_refused(
        store=store,
        candidate_ref=other_candidate_ref,
        evaluation_ref=replayed_ref,
        run_id=v1_run_id,
        suite_ref=suite_ref,
    )

    # A claimed score cannot diverge from the real MethodJob output.
    altered_score = v1_evaluation.model_copy(
        update={
            "selection_metrics": {
                "ate": v1_evaluation.selection_metrics["ate"] + 123.0,
            }
        }
    )
    altered_ref = persist_benchmark_evaluation(
        store,
        altered_score,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    _assert_refused(
        store=store,
        candidate_ref=candidate_ref,
        evaluation_ref=altered_ref,
        run_id=v1_run_id,
        suite_ref=suite_ref,
    )

    # The canonical ABI with producer and source edges removed is not enough.
    stripped_ref = store.put_json(
        v1_evaluation.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=f"scientist.autotune.{v1_evaluation.loop_id}.evaluation",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.methods.autotune.BenchmarkEvaluation",
                version=v1_evaluation.suite_version,
            ),
            inputs=[],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _assert_refused(
        store=store,
        candidate_ref=candidate_ref,
        evaluation_ref=stripped_ref,
        run_id=v1_run_id,
        suite_ref=suite_ref,
    )

    # A still-marked evaluation with its required measured packet removed is held.
    no_packet = v1_evaluation.model_copy(
        update={
            "execution_work_packet_ref": None,
            "execution_work_packet_status": "unavailable",
        }
    )
    no_packet_ref = persist_benchmark_evaluation(
        store,
        no_packet,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    _assert_refused(
        store=store,
        candidate_ref=candidate_ref,
        evaluation_ref=no_packet_ref,
        run_id=v1_run_id,
        suite_ref=suite_ref,
    )

    MethodRegistry.reset_instance()


@pytest.mark.integration
def test_real_phase_d4_source_recomputes_rotating_promotion_basis(tmp_path):
    store = FileSystemCAS(tmp_path / "d4-cas")
    candidate_ref = _d4_helpers._persist_policy_candidate(store, "candidate-d4")
    loop_id = "loop-d4"
    summary = {
        "fallback_mode": "exact_equilibrium",
        "equilibrium_selection_dependence": "follower_best_response_tie_breaking",
        "multiplicity_note": "multiple_stackelberg_equilibria",
        "equilibrium_profiles": [
            {"leader": "L1", "follower": "F1"},
            {"leader": "L1", "follower": "F2"},
        ],
        "closure_summary": {"mode": "exact_equilibrium", "equilibrium_count": 2},
    }
    suite_results, warnings = run_phase_d4_challenge_suites(
        store=store,
        run_id="run-d4",
        loop_id=loop_id,
        candidate_ref=candidate_ref,
        params={},
        artifacts_index={},
        selection_metadata={"strategic_response": summary},
    )
    assert warnings == ("phase_d4_strategic_suite_audit_only",)
    assert suite_results
    suite_result = suite_results[0]
    assert suite_result.stress_test_report is not None

    evaluation_ref = persist_benchmark_evaluation(
        store,
        suite_result.benchmark_evaluation,
        return_selected_profile=True,
    )
    basis = suite_result.stress_outcome_basis.model_copy(
        update={"benchmark_evaluation_ref": evaluation_ref}
    )
    basis_ref = store.put_json(
        basis,
        ArtifactWriteOptions(
            kind=_STRESS_OUTCOME_BASIS_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=_STRESS_OUTCOME_BASIS_SCHEMA_NAME,
                version=_STRESS_OUTCOME_BASIS_SCHEMA_VERSION,
            ),
            inputs=[
                input_ref_from_artifact_ref(evaluation_ref, role="benchmark_evaluation"),
                input_ref_from_artifact_ref(candidate_ref, role="candidate"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    component = StressScoreComponent(
        component_id=basis.source_id,
        score_profile="finite_binary_scenario_v1",
        outcome_basis_ref=basis_ref,
    )
    resolution = resolve_stress_score_components(
        store,
        [component],
        expected_candidate_ref=candidate_ref,
    )
    assert resolution.status == "available"
    assert resolution.predicate_status == "recomputed"
    stress_report = suite_result.stress_test_report.model_copy(
        update={
            "score_components": [component],
            "score_profile": resolution.score_profile,
            "score_status": resolution.status,
            "score_reason": resolution.reason_code,
            "score_predicate_status": resolution.predicate_status,
            "robustness_score": resolution.robustness_score,
            "total_scenarios_evaluated": resolution.total_scenarios_evaluated,
            "critical_count": resolution.critical_count,
            "high_count": resolution.high_count,
            "medium_count": resolution.medium_count,
        }
    )
    stress_report_ref = store.put_json(
        stress_report,
        ArtifactWriteOptions(
            kind=_STRESS_TEST_REPORT_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_STRESS_TEST_REPORT_SCHEMA_NAME, version="1.1"),
            inputs=[
                input_ref_from_artifact_ref(candidate_ref, role="candidate"),
                input_ref_from_artifact_ref(evaluation_ref, role="benchmark_evaluation"),
                input_ref_from_artifact_ref(basis_ref, role="stress_outcome_basis"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    state = ExperimentState(run_id="run-d4", params={"policy_loop_id": loop_id})
    selection_vector = PolicyEvaluationVector(candidate_id="candidate-d4")
    selection_evaluation = build_selection_benchmark_evaluation(
        state=state,
        candidate_ref=candidate_ref,
        evaluation_vector=selection_vector,
    )
    selection_ref = persist_benchmark_evaluation(
        store,
        selection_evaluation,
        return_selected_profile=True,
    )

    def _bundle_with_rotation(ref: ArtifactRef) -> PromotionEvidenceBundle:
        return PromotionEvidenceBundle(
            run_id="run-d4",
            produced_by_run_id="run-d4",
            candidate_ref=candidate_ref,
            selection_evaluation_ref=selection_ref,
            rotating_challenge_evaluation_refs=[ref],
            stress_test_report_ref=stress_report_ref,
        )

    source_basis = _build_promotion_benchmark_source_basis(
        state=state,
        candidate_ref=candidate_ref,
        evaluation_vector=selection_vector,
        evidence_bundle=_bundle_with_rotation(evaluation_ref),
        promotion_context={
            "stress_test_report": stress_report,
            "stress_test_report_ref": stress_report_ref,
        },
        expected_loop_id=loop_id,
    )

    _bundle_with_rotation(evaluation_ref).assert_runtime_compatible(
        run_id="run-d4",
        store=store,
        expected_loop_id=loop_id,
        source_basis_by_role=source_basis,
    )

    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")
    counterfeit_profile_ref = persist_benchmark_evaluation(
        store,
        suite_result.benchmark_evaluation,
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="counterfeit_edge")],
        return_selected_profile=True,
    )
    assert counterfeit_profile_ref.artifact_id == evaluation_ref.artifact_id
    assert counterfeit_profile_ref.manifest_profile_sha256 != evaluation_ref.manifest_profile_sha256
    registry.record_evaluation(
        suite_result.benchmark_evaluation,
        counterfeit_profile_ref,
        run_id="run-d4",
        rotation_group="phase_d4_v1",
        produced_by_run_id="run-d4",
    )
    assert registry.get(
        BenchmarkSplit.ROTATING_CHALLENGE.value,
        run_id="run-d4",
        loop_id=loop_id,
    ) == [counterfeit_profile_ref]
    with pytest.raises(ValueError, match="differ from recomputed D4 sources"):
        _bundle_with_rotation(counterfeit_profile_ref).assert_runtime_compatible(
            run_id="run-d4",
            store=store,
            expected_loop_id=loop_id,
            source_basis_by_role=source_basis,
        )

    altered_evaluation = suite_result.benchmark_evaluation.model_copy(
        update={
            "selection_metrics": {
                **suite_result.benchmark_evaluation.selection_metrics,
                "challenge_pass_rate": 0.5,
            }
        }
    )
    altered_ref = persist_benchmark_evaluation(
        store,
        altered_evaluation,
        return_selected_profile=True,
    )
    registry.record_evaluation(
        altered_evaluation,
        altered_ref,
        run_id="run-d4",
        rotation_group="phase_d4_v1",
        produced_by_run_id="run-d4",
    )
    with pytest.raises(ValueError, match="differ from recomputed D4 sources"):
        _bundle_with_rotation(altered_ref).assert_runtime_compatible(
            run_id="run-d4",
            store=store,
            expected_loop_id=loop_id,
            source_basis_by_role=source_basis,
        )
