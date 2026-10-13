from __future__ import annotations

import logging
from dataclasses import replace
from types import SimpleNamespace

import pytest

import polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime as runtime_owner
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.strategic import (
    EquilibriumSelectionSummary,
    EquilibriumSetSummary,
    PostAdaptationPolicyValueSummary,
    StrategicClosureSummary,
    StrategicDecompositionStatus,
    StrategicEquilibriumConcept,
    StrategicFallbackMode,
    StrategicResponseBundle,
    persist_equilibrium_selection_summary,
    persist_equilibrium_set_summary,
    persist_post_adaptation_policy_value_summary,
    persist_strategic_closure_summary,
    persist_strategic_response_bundle,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.governance.stress_scenarios import (
    StressScenarioRunner,
    load_stress_test_report,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.doe.stress_report import (
    StressOutcomeBasis,
    StressTestReport,
    resolve_stress_report_artifact,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.promotion_evidence import (
    load_promotion_evidence_bundle,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_benchmarks import (
    prepare_runtime_benchmark_evidence,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _RuntimeSession,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
    _extract_level5_gate,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_request import (
    resolve_policy_runtime_request,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _ensure_stress_test_report,
    _run_and_register_phase_d4_challenge_suites,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _build_policy_candidate(candidate_id: str) -> PolicyCandidateSchema:
    token = candidate_id.replace("-", "_")
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(problem_id=f"problem_{token}", domain=ProblemDomain.FISCAL),
            policy_spec=PolicySpec(policy_id=f"policy_{token}"),
            model_spec=ModelSpec(model_id=f"model_{token}", data_snapshot_ref="sha256:" + "3" * 64),
        ),
        candidate_id=candidate_id,
    )


def _persist_policy_candidate(store, candidate_id: str) -> ArtifactRef:
    candidate = _build_policy_candidate(candidate_id)
    return persist_policy_candidate_schema(store, candidate, return_selected_profile=True)


def test_phase_d4_runtime_helper_persists_rotating_and_stress_artifacts(
    tmp_path, monkeypatch
) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_d4_runtime")
    candidate = _build_policy_candidate("cand-1")
    seed_candidate_ref = persist_policy_candidate_schema(
        ctx.store, candidate, return_selected_profile=True
    )
    candidate_ref = seed_candidate_ref
    strategic_closure_ref = persist_strategic_closure_summary(
        _ensure_ir_artifact_store(ctx.store),
        StrategicClosureSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
            profile_count=4,
            equilibrium_count=2,
        ),
    )
    equilibrium_set_ref = persist_equilibrium_set_summary(
        _ensure_ir_artifact_store(ctx.store),
        EquilibriumSetSummary(
            equilibrium_profiles=(),
            equilibrium_count=0,
        ),
    )
    selected_equilibrium_ref = persist_equilibrium_selection_summary(
        _ensure_ir_artifact_store(ctx.store),
        EquilibriumSelectionSummary(
            selected_equilibrium={"leader": "A", "follower": "X"},
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
        ),
    )
    post_adaptation_policy_value_ref = persist_post_adaptation_policy_value_summary(
        _ensure_ir_artifact_store(ctx.store),
        PostAdaptationPolicyValueSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            baseline_policy_value=1.0,
            point_value=1.2,
        ),
    )
    strategic_bundle_ref = persist_strategic_response_bundle(
        _ensure_ir_artifact_store(ctx.store),
        StrategicResponseBundle(
            causal_component_ref=ArtifactRefModel.model_validate(
                candidate_ref.model_dump(mode="json")
            ),
            strategic_closure_ref=strategic_closure_ref,
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
            equilibrium_set_ref=equilibrium_set_ref,
            selected_equilibrium_ref=selected_equilibrium_ref,
            post_adaptation_policy_value_ref=post_adaptation_policy_value_ref,
            decomposition_status=StrategicDecompositionStatus.EXACT,
            decomposition_certificate_ref=ArtifactRefModel(
                artifact_id=candidate_ref.artifact_id,
                kind="ir.strategic_decomposition_certificate",
                media_type="application/json",
            ),
            anchor_equilibrium_ref=selected_equilibrium_ref,
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
        ),
    )
    state = ExperimentState(
        run_id="R_d4_runtime",
        params={
            "policy_loop_id": "loop-a",
            "policy_candidate_schema": candidate.model_dump(mode="json"),
        },
        artifacts_index={
            ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF: strategic_bundle_ref,
        },
    )
    runtime_request = resolve_policy_runtime_request(ctx, state)
    assert runtime_request is not None
    assert runtime_request.candidate == candidate
    candidate_ref = runtime_request.candidate_ref
    assert candidate_ref == seed_candidate_ref
    assert candidate_ref.kind == PolicyCandidateSchema.ARTIFACT_KIND
    assert candidate_ref.media_type == PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE
    assert candidate_ref.manifest_profile_sha256 is not None
    candidate_manifest = ctx.store.get_manifest(candidate_ref)
    assert candidate_manifest.kind == PolicyCandidateSchema.ARTIFACT_KIND
    assert candidate_manifest.media_type == PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE
    assert candidate_manifest.artifact_schema is not None
    assert candidate_manifest.artifact_schema.name == PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME
    assert (
        candidate_manifest.artifact_schema.version == PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION
    )
    persisted_candidate = PolicyCandidateSchema.model_validate(
        load_core_json_artifact(
            ctx.store,
            candidate_ref,
            manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
        )
    )
    assert persisted_candidate == candidate
    selection_evaluation = BenchmarkEvaluation(
        loop_id="loop-a",
        suite_id="policy_selection",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.9},
        holdout_metrics={"score": 0.9},
        sample_counts={BenchmarkSplit.SELECTION.value: 10},
        promotable=True,
        runtime_split_type=BenchmarkSplit.SELECTION,
    )
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")
    benchmark_scope = {
        "artifact_family": "frontier_family",
        "claim_mode": "estimation",
        "query_type": "policy",
        "estimator_name": "runtime",
        "readiness_target": "deployment_ready",
    }
    selection_ref = persist_benchmark_evaluation(
        ctx.store, selection_evaluation, return_selected_profile=True
    )
    registry.record_evaluation(
        selection_evaluation,
        selection_ref,
        run_id=state.run_id,
        family=benchmark_scope["artifact_family"],
        query_type=benchmark_scope["query_type"],
        estimator_name=benchmark_scope["estimator_name"],
        readiness_target=benchmark_scope["readiness_target"],
        produced_by_run_id=state.run_id,
    )
    selection_vector = PolicyEvaluationVector(candidate_id="cand-1")
    selection_vector_ref = runtime_owner.persist_policy_evaluation_vector(
        ctx, candidate_ref=candidate_ref, evaluation_vector=selection_vector
    )
    monkeypatch.setattr(runtime_owner, "_ensure_calibration_report", lambda *_args: None)
    monkeypatch.setattr(
        runtime_owner, "_ensure_platform_meta_report", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(runtime_owner, "load_funnel_calibration_report", lambda *_args: None)
    monkeypatch.setattr(
        runtime_owner, "_resolve_degradation_mode", lambda *_args, **_kwargs: "normal"
    )
    session = _RuntimeSession(
        ctx=ctx,
        state=state,
        owner=runtime_owner,
        candidate=runtime_request.candidate,
        candidate_ref=candidate_ref,
        uncertainty_envelope=None,
        governance_report=None,
        causal_report=None,
        distributional_report=None,
        cross_graph_profile=None,
        evidence_sources=None,
        runtime_source_statuses={},
        simulation_metrics={},
        ambiguity_certificate=None,
        ambiguity_certificate_ref=None,
        runtime_backend=None,
        input_signature="r952-runtime-caller-test",
        runtime_artifacts_index=state.artifacts_index,
        selection_vector=selection_vector,
        selection_vector_ref=selection_vector_ref,
        selection_evaluation=selection_evaluation,
        selection_ref=selection_ref,
        benchmark_scope=benchmark_scope,
        benchmark_registry=registry,
    )
    prepare_runtime_benchmark_evidence(session)
    rotating_refs = session.phase_d4_rotating_refs
    stress_refs = session.phase_d4_stress_refs
    warnings = session.phase_d4_warnings
    merged_ref = session.stress_report_ref
    assert merged_ref is not None
    assert session.evidence_bundle is not None
    assert session.evidence_bundle.stress_test_report_ref == merged_ref
    assert session.evidence_ref is not None
    persisted_evidence = load_promotion_evidence_bundle(ctx.store, session.evidence_ref)
    assert persisted_evidence.stress_test_report_ref == merged_ref

    assert warnings == ("phase_d4_strategic_suite_audit_only",)
    assert len(rotating_refs) == 2
    assert len(stress_refs) == 2

    rotating_evaluations = [
        BenchmarkEvaluation.model_validate(
            from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
        )
        for ref in rotating_refs
    ]
    assert all(
        evaluation.resolved_runtime_split_type() is BenchmarkSplit.ROTATING_CHALLENGE
        for evaluation in rotating_evaluations
    )

    bundle = registry.resolve_family_bundle(
        family="frontier_family",
        claim_mode="estimation",
        run_id="R_d4_runtime",
        loop_id="loop-a",
        query_type="policy",
        estimator_name="runtime",
        readiness_target="deployment_ready",
    )
    assert len(bundle.rotating_challenge_evaluation_refs) == 2

    def suite_refs(refs):
        result = {}
        for ref in refs:
            report = StressTestReport.model_validate(load_core_json_artifact(ctx.store, ref))
            suite_id = report.metadata.get("challenge_suite_id")
            if suite_id is not None:
                result[suite_id] = (str(ref.artifact_id), ref.manifest_profile_sha256)
        return result

    assert suite_refs(bundle.adversarial_artifact_refs) == suite_refs(stress_refs)
    assert all(ref.manifest_profile_sha256 is not None for ref in stress_refs)

    stress_reports = [
        StressTestReport.model_validate(load_core_json_artifact(ctx.store, ref))
        for ref in stress_refs
    ]
    assert all(report.score_status == "available" for report in stress_reports)
    assert all(report.score_predicate_status == "recomputed" for report in stress_reports)
    bases = [
        StressOutcomeBasis.model_validate(
            load_core_json_artifact(ctx.store, report.score_components[0].outcome_basis_ref)
        )
        for report in stress_reports
    ]
    assert all(basis.complete and len(basis.outcomes) == basis.expected_count for basis in bases)

    source_report = stress_reports[0]
    source_basis = bases[0]
    source_evaluation_ref = source_basis.benchmark_evaluation_ref
    assert source_evaluation_ref is not None
    source_evaluation = BenchmarkEvaluation.model_validate(
        load_core_json_artifact(ctx.store, source_evaluation_ref)
    )
    wrong_evaluation_ref = ctx.store.put_json(
        source_evaluation,
        PutOptions(
            kind=f"scientist.autotune.{source_evaluation.loop_id}.evaluation",
            media_type="application/json",
            schema=SchemaInfo(
                name="wrong.BenchmarkEvaluation", version=source_evaluation.suite_version
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert wrong_evaluation_ref.artifact_id == source_evaluation_ref.artifact_id
    assert (
        wrong_evaluation_ref.manifest_profile_sha256
        != source_evaluation_ref.manifest_profile_sha256
    )
    wrong_basis = source_basis.model_copy(update={"benchmark_evaluation_ref": wrong_evaluation_ref})
    wrong_basis_ref = ctx.store.put_json(
        wrong_basis,
        PutOptions(
            kind="scientist.stress_outcome_basis",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressOutcomeBasis", version="1.0"),
            inputs=[
                InputRef(
                    artifact_id=wrong_evaluation_ref.artifact_id,
                    role="benchmark_evaluation",
                    manifest_profile_sha256=wrong_evaluation_ref.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=candidate_ref.artifact_id,
                    role="candidate",
                    manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    wrong_component = source_report.score_components[0].model_copy(
        update={"outcome_basis_ref": wrong_basis_ref}
    )
    wrong_report = source_report.model_copy(update={"score_components": [wrong_component]})
    wrong_report_ref = ctx.store.put_json(
        wrong_report,
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.1"),
            inputs=[
                InputRef(
                    artifact_id=candidate_ref.artifact_id,
                    role="candidate",
                    manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=wrong_evaluation_ref.artifact_id,
                    role="benchmark_evaluation",
                    manifest_profile_sha256=wrong_evaluation_ref.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=wrong_basis_ref.artifact_id,
                    role="stress_outcome_basis",
                    manifest_profile_sha256=wrong_basis_ref.manifest_profile_sha256,
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _, wrong_evaluation_resolution = resolve_stress_report_artifact(
        ctx.store, wrong_report_ref, expected_candidate_ref=candidate_ref
    )
    assert wrong_evaluation_resolution.status == "invalid"
    assert wrong_evaluation_resolution.robustness_score is None
    assert all(
        report.score_components[0].outcome_basis_ref.manifest_profile_sha256 is not None
        for report in stress_reports
    )
    assert all(
        basis.benchmark_evaluation_ref is not None
        and basis.benchmark_evaluation_ref.manifest_profile_sha256 is not None
        for basis in bases
    )
    for report_ref, report, basis in zip(stress_refs, stress_reports, bases, strict=True):
        source_manifest = ctx.store.get_manifest(report_ref)
        assert [item.role for item in source_manifest.inputs] == [
            "candidate",
            "benchmark_evaluation",
            "stress_outcome_basis",
        ]
        assert [item.manifest_profile_sha256 for item in source_manifest.inputs] == [
            candidate_ref.manifest_profile_sha256,
            basis.benchmark_evaluation_ref.manifest_profile_sha256,
            report.score_components[0].outcome_basis_ref.manifest_profile_sha256,
        ]

    tampered_report = stress_reports[0].model_copy(
        update={"critical_count": stress_reports[0].critical_count + 1}
    )
    with pytest.raises(ValueError, match="stress_report_source_body_mismatch"):
        _ensure_stress_test_report(
            ctx,
            state,
            evaluation_vector=PolicyEvaluationVector(candidate_id="cand-1"),
            supplemental_reports=[tampered_report],
            supplemental_report_refs=[stress_refs[0]],
            expected_candidate_ref=candidate_ref,
        )
    with pytest.raises(ValueError, match="stress_report_source_pair_count_mismatch"):
        _ensure_stress_test_report(
            ctx,
            state,
            evaluation_vector=PolicyEvaluationVector(candidate_id="cand-1"),
            supplemental_reports=[stress_reports[0]],
            expected_candidate_ref=candidate_ref,
        )
    wrong_scope_candidate_ref = candidate_ref.model_copy(
        update={"kind": "scientist.stress_test_report"}
    )
    with pytest.raises(ValueError, match="stress_report_expected_candidate_identity_mismatch"):
        _ensure_stress_test_report(
            ctx,
            state,
            evaluation_vector=PolicyEvaluationVector(candidate_id="cand-1"),
            expected_candidate_ref=wrong_scope_candidate_ref,
        )
    wrong_schema_ref = ctx.store.put_json(
        stress_reports[0],
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="wrong.StressTestReport", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert wrong_schema_ref.artifact_id == stress_refs[0].artifact_id
    assert wrong_schema_ref.manifest_profile_sha256 != stress_refs[0].manifest_profile_sha256
    with pytest.raises(ValueError, match="selected_source_schema_name_mismatch"):
        _ensure_stress_test_report(
            ctx,
            state,
            evaluation_vector=PolicyEvaluationVector(candidate_id="cand-1"),
            supplemental_reports=[stress_reports[0]],
            supplemental_report_refs=[wrong_schema_ref],
            expected_candidate_ref=candidate_ref,
        )
    wrong_schema_l5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "cand-1"},
        {
            "store": ctx.store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": wrong_schema_ref,
        },
    )
    assert wrong_schema_l5.feedback["stress_score_status"] == "invalid"

    assert merged_ref is not None
    assert merged_ref.manifest_profile_sha256 is not None
    merged_inputs = ctx.store.get_manifest(merged_ref).inputs
    expected_merged_inputs = [
        InputRef(
            artifact_id=candidate_ref.artifact_id,
            role="candidate",
            manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
        ),
        *[
            InputRef(
                artifact_id=ref.artifact_id,
                role="supplemental_stress_report",
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for ref in stress_refs
        ],
        *[
            InputRef(
                artifact_id=component.outcome_basis_ref.artifact_id,
                role="stress_outcome_basis",
                manifest_profile_sha256=component.outcome_basis_ref.manifest_profile_sha256,
            )
            for report in stress_reports
            for component in report.score_components
        ],
    ]
    assert merged_inputs == expected_merged_inputs

    duplicate_base_ref = stress_refs[1]
    duplicate_base_report = stress_reports[1]
    duplicate_source_report = stress_reports[0]
    duplicate_suite_id = str(duplicate_source_report.metadata["challenge_suite_id"])
    assert duplicate_suite_id != duplicate_base_report.metadata["challenge_suite_id"]

    def selected_source_rows(report: StressTestReport):
        rows = []
        for component in report.score_components:
            basis = StressOutcomeBasis.model_validate(
                load_core_json_artifact(ctx.store, component.outcome_basis_ref)
            )
            assert basis.complete
            assert basis.expected_count == len(basis.outcomes)
            assert basis.expected_scenario_ids == [row.scenario_id for row in basis.outcomes]
            assert [row.occurrence_index for row in basis.outcomes] == list(
                range(basis.expected_count)
            )
            rows.extend(basis.outcomes)
        return rows

    unique_source_rows = [
        *selected_source_rows(duplicate_base_report),
        *selected_source_rows(duplicate_source_report),
    ]
    assert unique_source_rows
    assert all(row.status in {"passed", "failed"} for row in unique_source_rows)
    expected_unique_total = len(unique_source_rows)
    expected_unique_passed = sum(row.status == "passed" for row in unique_source_rows)

    single_source_ref = _ensure_stress_test_report(
        ctx,
        ExperimentState(
            run_id="R_d4_single_source_control",
            artifacts_index={ARTIFACT_STRESS_TEST_REPORT_REF: duplicate_base_ref},
        ),
        evaluation_vector=PolicyEvaluationVector(candidate_id="cand-1"),
        supplemental_reports=[duplicate_source_report],
        supplemental_report_refs=[stress_refs[0]],
        phase_d4_suite_ids=[duplicate_suite_id],
        expected_candidate_ref=candidate_ref,
    )
    assert single_source_ref is not None
    single_source_report = StressTestReport.model_validate(
        load_core_json_artifact(ctx.store, single_source_ref)
    )
    _, single_source_resolution = resolve_stress_report_artifact(
        ctx.store, single_source_ref, expected_candidate_ref=candidate_ref
    )
    assert single_source_report.score_profile == "finite_binary_scenario_v1"
    assert single_source_report.score_status == "available"
    assert single_source_report.score_reason == "source_bound_occurrences_recomputed"
    assert single_source_report.score_predicate_status == "recomputed"
    assert single_source_report.total_scenarios_evaluated == expected_unique_total
    assert single_source_report.robustness_score == pytest.approx(
        expected_unique_passed / expected_unique_total
    )
    assert single_source_resolution.status == "available"
    assert single_source_resolution.reason_code == "source_bound_occurrences_recomputed"
    assert single_source_resolution.total_scenarios_evaluated == expected_unique_total
    assert single_source_resolution.passed_count == expected_unique_passed
    assert single_source_resolution.robustness_score == pytest.approx(
        expected_unique_passed / expected_unique_total
    )

    expected_single_components = [
        *duplicate_base_report.score_components,
        *duplicate_source_report.score_components,
    ]
    expected_single_inputs = [
        InputRef(
            artifact_id=candidate_ref.artifact_id,
            role="candidate",
            manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=duplicate_base_ref.artifact_id,
            role="base_stress_report",
            manifest_profile_sha256=duplicate_base_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=stress_refs[0].artifact_id,
            role="supplemental_stress_report",
            manifest_profile_sha256=stress_refs[0].manifest_profile_sha256,
        ),
        *[
            InputRef(
                artifact_id=component.outcome_basis_ref.artifact_id,
                role="stress_outcome_basis",
                manifest_profile_sha256=component.outcome_basis_ref.manifest_profile_sha256,
            )
            for component in expected_single_components
        ],
    ]
    assert ctx.store.get_manifest(single_source_ref).inputs == expected_single_inputs

    duplicate_ref = _ensure_stress_test_report(
        ctx,
        ExperimentState(
            run_id="R_d4_duplicate",
            artifacts_index={ARTIFACT_STRESS_TEST_REPORT_REF: duplicate_base_ref},
        ),
        evaluation_vector=PolicyEvaluationVector(candidate_id="cand-1"),
        supplemental_reports=[duplicate_source_report, duplicate_source_report],
        supplemental_report_refs=[stress_refs[0], stress_refs[0]],
        phase_d4_suite_ids=[duplicate_suite_id] * 2,
        expected_candidate_ref=candidate_ref,
    )
    assert duplicate_ref is not None
    duplicate_manifest = ctx.store.get_manifest(duplicate_ref)
    duplicate_inputs = [
        item for item in duplicate_manifest.inputs if item.role == "supplemental_stress_report"
    ]
    assert len(duplicate_inputs) == 2
    assert duplicate_inputs == [
        InputRef(
            artifact_id=stress_refs[0].artifact_id,
            role="supplemental_stress_report",
            manifest_profile_sha256=stress_refs[0].manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=stress_refs[0].artifact_id,
            role="supplemental_stress_report",
            manifest_profile_sha256=stress_refs[0].manifest_profile_sha256,
        ),
    ]
    expected_duplicate_components = [
        *duplicate_base_report.score_components,
        *duplicate_source_report.score_components,
        *duplicate_source_report.score_components,
    ]
    expected_duplicate_inputs = [
        InputRef(
            artifact_id=candidate_ref.artifact_id,
            role="candidate",
            manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=duplicate_base_ref.artifact_id,
            role="base_stress_report",
            manifest_profile_sha256=duplicate_base_ref.manifest_profile_sha256,
        ),
        *[
            InputRef(
                artifact_id=stress_refs[0].artifact_id,
                role="supplemental_stress_report",
                manifest_profile_sha256=stress_refs[0].manifest_profile_sha256,
            )
            for _ in range(2)
        ],
        *[
            InputRef(
                artifact_id=component.outcome_basis_ref.artifact_id,
                role="stress_outcome_basis",
                manifest_profile_sha256=component.outcome_basis_ref.manifest_profile_sha256,
            )
            for component in expected_duplicate_components
        ],
    ]
    assert duplicate_manifest.inputs == expected_duplicate_inputs
    duplicate_report = StressTestReport.model_validate(
        load_core_json_artifact(ctx.store, duplicate_ref)
    )
    assert duplicate_report.score_profile == "finite_binary_scenario_v1"
    assert duplicate_report.score_status == "invalid"
    assert duplicate_report.score_reason == "duplicate_component_id"
    assert duplicate_report.robustness_score is None
    assert duplicate_report.total_scenarios_evaluated == expected_unique_total

    def component_identity(component):
        ref = component.outcome_basis_ref
        return (
            component.component_id,
            component.score_profile,
            str(ref.artifact_id),
            ref.kind,
            ref.media_type,
            ref.manifest_profile_sha256,
        )

    assert [component_identity(item) for item in duplicate_report.score_components] == [
        component_identity(item) for item in expected_duplicate_components
    ]
    assert len(duplicate_report.score_components) == len(expected_duplicate_components)
    for source_component in duplicate_source_report.score_components:
        repeated = [
            item
            for item in duplicate_report.score_components
            if item.component_id == source_component.component_id
        ]
        assert [component_identity(item) for item in repeated] == [
            component_identity(source_component),
            component_identity(source_component),
        ]

    fresh_duplicate_report, duplicate_resolution = resolve_stress_report_artifact(
        ctx.store, duplicate_ref, expected_candidate_ref=candidate_ref
    )
    assert fresh_duplicate_report == duplicate_report
    assert duplicate_resolution.status == "invalid"
    assert duplicate_resolution.reason_code == "duplicate_component_id"
    assert duplicate_resolution.robustness_score is None

    duplicate_l5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "cand-1"},
        {
            "store": ctx.store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": duplicate_ref,
        },
    )
    assert duplicate_l5.feedback["stress_score_status"] == "invalid"
    assert duplicate_l5.feedback["stress_score_value"] is None
    assert any(
        card.failure_type == "stress_score_invalid" and card.is_blocker
        for card in duplicate_l5.failure_cards
    )
    in_memory_forgery = StressTestReport(
        report_id="forged-memory-summary",
        schema_version="1.1",
        score_profile="finite_binary_scenario_v1",
        score_status="available",
        score_predicate_status="recomputed",
        robustness_score=0.0,
        total_scenarios_evaluated=999,
    )
    fresh_l5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "cand-1"},
        {
            "store": ctx.store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": merged_ref,
            "stress_test_report": in_memory_forgery,
        },
    )
    assert not any(card.failure_type == "stress_test_failed" for card in fresh_l5.failure_cards)
    other_candidate_ref = _persist_policy_candidate(ctx.store, "cand-1-other")
    stale_l5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "cand-1"},
        {
            "store": ctx.store,
            "policy_candidate_ref": other_candidate_ref,
            "stress_test_report_ref": merged_ref,
        },
    )
    assert stale_l5.feedback["stress_score_status"] == "invalid"
    assert any(
        card.failure_type == "stress_score_invalid" and card.is_blocker
        for card in stale_l5.failure_cards
    )
    assert not any(card.failure_type == "stress_test_failed" for card in stale_l5.failure_cards)


def test_continuous_stress_stays_limited_through_fresh_level5_gate(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_b106_continuous")
    candidate_ref = _persist_policy_candidate(ctx.store, "candidate-continuous")
    produced = StressScenarioRunner(ctx.store).run(
        baseline_metrics={"policy_value": 100.0},
        inputs=[
            InputRef(
                artifact_id=candidate_ref.artifact_id,
                role="candidate",
                manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
            )
        ],
    )
    assert produced.stress_test_report_ref is not None
    source_report = load_stress_test_report(ctx.store, produced.stress_test_report_ref)
    assert produced.stress_test_report_ref.manifest_profile_sha256 is not None
    source_manifest = ctx.store.get_manifest(produced.stress_test_report_ref)
    assert [item.role for item in source_manifest.inputs] == ["candidate"]
    assert (
        source_manifest.inputs[0].manifest_profile_sha256 == candidate_ref.manifest_profile_sha256
    )
    assert source_report.score_profile == "continuous_severity_v1"
    assert source_report.score_status == "available"
    assert source_report.robustness_score is not None

    state = ExperimentState(
        run_id="R_b106_continuous",
        artifacts_index={ARTIFACT_STRESS_TEST_REPORT_REF: produced.stress_test_report_ref},
    )
    composed_ref = _ensure_stress_test_report(
        ctx,
        state,
        evaluation_vector=PolicyEvaluationVector(),
        phase_d4_suite_ids=["phase_d4_source_trace"],
        expected_candidate_ref=candidate_ref,
    )
    assert composed_ref is not None
    assert composed_ref.manifest_profile_sha256 is not None
    composed_manifest = ctx.store.get_manifest(composed_ref)
    assert [item.role for item in composed_manifest.inputs] == [
        "candidate",
        "base_stress_report",
    ]
    assert (
        composed_manifest.inputs[0].manifest_profile_sha256 == candidate_ref.manifest_profile_sha256
    )
    assert (
        composed_manifest.inputs[1].manifest_profile_sha256
        == produced.stress_test_report_ref.manifest_profile_sha256
    )
    composed_report = StressTestReport.model_validate(
        load_core_json_artifact(ctx.store, composed_ref)
    )
    assert composed_report.score_profile == "mixed_unscored"
    assert composed_report.score_status == "profile_mismatch"
    assert composed_report.robustness_score is None
    source_rows = composed_report.metadata["score_source_reports"]
    assert any(
        row["report_id"] == source_report.report_id
        and row["score_status"] == "available"
        and row["score_profile"] == "continuous_severity_v1"
        for row in source_rows
    )

    level5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "candidate-continuous"},
        {
            "store": ctx.store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": composed_ref,
        },
    )
    assert level5.feedback["stress_score_status"] == "profile_mismatch"
    assert level5.feedback["stress_score_profile"] == "mixed_unscored"
    assert level5.feedback["stress_score_value"] is None
    assert level5.feedback["stress_score_source_reports"] == source_rows
    assert level5.terminal_action == "defer_to_human"
    assert any(
        card.failure_type == "stress_score_unavailable" and card.severity.value == "warning"
        for card in level5.failure_cards
    )
    assert not any(
        card.failure_type in {"stress_test_failed", "stress_score_invalid"}
        for card in level5.failure_cards
    )

    outcome = SimpleNamespace(stage_results={5: level5})
    assert _extract_level5_gate(outcome)["passed"] is False
    warning_without_defer = replace(level5, terminal_action=None)
    assert (
        _extract_level5_gate(SimpleNamespace(stage_results={5: warning_without_defer}))["passed"]
        is False
    )


def test_l5_distinguishes_missing_legacy_and_malformed_stress_scores(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_b106_statuses")
    candidate_ref = _persist_policy_candidate(ctx.store, "candidate-statuses")
    stage = Level5RefutationGovernanceStage(require_hidden_holdout=False)
    missing = stage.evaluate(
        {"candidate_id": "candidate-statuses"},
        {"store": ctx.store, "policy_candidate_ref": candidate_ref},
    )
    assert missing.feedback["stress_score_status"] == "not_evaluated"
    assert missing.feedback["stress_score_value"] is None
    assert missing.terminal_action == "defer_to_human"
    assert not any(card.failure_type == "stress_test_failed" for card in missing.failure_cards)

    legacy_ref = ctx.store.put_json(
        {
            "schema_version": "1.0",
            "report_id": "legacy-stress-report",
            "total_scenarios_evaluated": 1,
            "high_count": 1,
            "robustness_score": 0.0,
        },
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    legacy = stage.evaluate(
        {"candidate_id": "candidate-statuses"},
        {
            "store": ctx.store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": legacy_ref,
        },
    )
    assert legacy.feedback["stress_score_status"] == "legacy_unknown"
    assert legacy.feedback["stress_score_value"] is None
    assert legacy.terminal_action == "defer_to_human"
    assert not any(card.failure_type == "stress_test_failed" for card in legacy.failure_cards)

    malformed = stage.evaluate(
        {"candidate_id": "candidate-statuses"},
        {"stress_test_report_ref": {"not_an_artifact_ref": True}},
    )
    assert malformed.feedback["stress_score_status"] == "invalid"
    assert any(
        card.failure_type == "stress_score_invalid" and card.is_blocker
        for card in malformed.failure_cards
    )
    assert not any(card.failure_type == "stress_test_failed" for card in malformed.failure_cards)


def test_phase_d4_runtime_helper_skips_cleanly_without_evidence(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_d4_skip")
    candidate_ref = _persist_policy_candidate(ctx.store, "cand-2")
    state = ExperimentState(run_id="R_d4_skip", params={"policy_loop_id": "loop-a"})
    selection_evaluation = BenchmarkEvaluation(
        loop_id="loop-a",
        suite_id="policy_selection",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.9},
        holdout_metrics={"score": 0.9},
        sample_counts={BenchmarkSplit.SELECTION.value: 10},
        promotable=True,
        runtime_split_type=BenchmarkSplit.SELECTION,
    )
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")

    rotating_refs, stress_refs, warnings = _run_and_register_phase_d4_challenge_suites(
        ctx,
        state,
        benchmark_registry=registry,
        candidate_ref=candidate_ref,
        selection_evaluation=selection_evaluation,
        benchmark_scope={
            "artifact_family": "frontier_family",
            "claim_mode": "estimation",
            "query_type": "policy",
            "estimator_name": "runtime",
            "readiness_target": "deployment_ready",
        },
        artifacts_index=state.artifacts_index,
    )

    assert rotating_refs == []
    assert stress_refs == []
    assert warnings == ("phase_d4_skipped_no_strategic_or_abstraction_evidence",)
