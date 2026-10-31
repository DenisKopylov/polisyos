from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

import polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime as runtime_owner
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir import UncertaintyType
from polisyos.ir.analytics.strategic import (
    EquilibriumSelectionSummary,
    EquilibriumSetSummary,
    FiniteStrategicPayoffTable,
    PostAdaptationPolicyValueSummary,
    StrategicClosureSummary,
    StrategicDecompositionStatus,
    StrategicEquilibriumConcept,
    StrategicFallbackMode,
    StrategicResponseBundle,
    StrategicSCM,
    encode_action_profile,
    persist_equilibrium_selection_summary,
    persist_equilibrium_set_summary,
    persist_post_adaptation_policy_value_summary,
    persist_strategic_closure_summary,
    persist_strategic_response_bundle,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.kernel.base import ComputeBudget
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.registry.refs import ArtifactRefModel, StrategicPayoffTableRef
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
from polisyos.scientist.methods.backtesting.phase_d4_source import (
    PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
    build_phase_d4_replay_source,
    build_phase_d4_suite_roster,
    load_selected_phase_d4_replay_source,
    persist_phase_d4_replay_source,
)
from polisyos.scientist.methods.doe.stress_report import (
    StressOutcomeBasis,
    StressTestReport,
    resolve_stress_report_artifact,
    resolve_stress_score_components,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.promotion_evidence import (
    PromotionEvidenceBundle,
    _PhaseD4ChallengeSourceBasis,
    _PolicyRuntimeSelectionSourceBasis,
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
        runtime_request=runtime_request,
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
    rotating_refs = session.rotating_refs
    phase_d4_refs = session.phase_d4_rotating_refs
    stress_refs = session.phase_d4_stress_refs
    selected_roster = build_phase_d4_suite_roster(
        ctx.store,
        rotating_evaluation_refs=rotating_refs,
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_run_id=state.run_id,
        expected_loop_id=selection_evaluation.loop_id,
    )
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
    assert len(phase_d4_refs) == 2
    assert len(stress_refs) == 2
    reversed_selected_roster = build_phase_d4_suite_roster(
        ctx.store,
        rotating_evaluation_refs=list(reversed(rotating_refs)),
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_run_id=state.run_id,
        expected_loop_id=selection_evaluation.loop_id,
    )
    assert reversed_selected_roster.suite_evaluation_refs == selected_roster.suite_evaluation_refs

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
    assert all(report.schema_version == "1.2" for report in stress_reports)
    assert all(report.case_truth_status == "recomputed" for report in stress_reports)
    bases = [
        StressOutcomeBasis.model_validate(
            load_core_json_artifact(ctx.store, report.score_components[0].outcome_basis_ref)
        )
        for report in stress_reports
    ]
    assert all(basis.complete and len(basis.outcomes) == basis.expected_count for basis in bases)
    assert all(basis.schema_version == "2.0" for basis in bases)
    assert all(basis.phase_d4_replay_source_ref is not None for basis in bases)
    for report, basis in zip(stress_reports, bases, strict=True):
        assert basis.benchmark_evaluation_ref is not None
        source_ref = basis.phase_d4_replay_source_ref
        assert source_ref is not None
        basis_ref = report.score_components[0].outcome_basis_ref
        basis_manifest = ctx.store.get_manifest(basis_ref)
        evaluation_manifest = ctx.store.get_manifest(basis.benchmark_evaluation_ref)
        assert any(
            item.role == "phase_d4_replay_source"
            and item.manifest_profile_sha256 == source_ref.manifest_profile_sha256
            for item in basis_manifest.inputs
        )
        assert any(
            item.role == "phase_d4_replay_source"
            and item.manifest_profile_sha256 == source_ref.manifest_profile_sha256
            for item in evaluation_manifest.inputs
        )

    source_report = stress_reports[0]
    source_basis = bases[0]
    source_evaluation_ref = source_basis.benchmark_evaluation_ref
    assert source_evaluation_ref is not None
    source_basis_ref = source_report.score_components[0].outcome_basis_ref
    source_basis_manifest = ctx.store.get_manifest(source_basis_ref)
    assert source_basis_manifest.artifact_schema is not None
    legacy_basis = source_basis.model_copy(
        update={"schema_version": "1.0", "phase_d4_replay_source_ref": None}
    )
    legacy_basis_ref = ctx.store.put_json(
        legacy_basis,
        PutOptions(
            kind=source_basis_manifest.kind,
            media_type=source_basis_manifest.media_type,
            schema=SchemaInfo(name="polisyos.scientist.StressOutcomeBasis", version="1.0"),
            inputs=source_basis_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    legacy_resolution = resolve_stress_score_components(
        ctx.store,
        [
            source_report.score_components[0].model_copy(
                update={"outcome_basis_ref": legacy_basis_ref}
            ),
            *(item.score_components[0] for item in stress_reports[1:]),
        ],
        expected_candidate_ref=candidate_ref,
        expected_run_id=state.run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    assert legacy_resolution.status == "unbound"
    assert legacy_resolution.case_truth_reason == "phase_d4_aggregate_only_source_schema"
    assert legacy_resolution.observed_sample_assessment is None
    selected_replay_source_ref = source_basis.phase_d4_replay_source_ref
    assert selected_replay_source_ref is not None
    selected_replay_source, _ = load_selected_phase_d4_replay_source(
        ctx.store, selected_replay_source_ref
    )
    sibling_replay_source_ref = persist_phase_d4_replay_source(
        ctx.store,
        selected_replay_source.model_copy(
            update={"captured_at": selected_replay_source.captured_at + timedelta(microseconds=1)}
        ),
    )
    sibling_source_basis = source_basis.model_copy(
        update={"phase_d4_replay_source_ref": sibling_replay_source_ref}
    )
    sibling_basis_inputs = [
        item for item in source_basis_manifest.inputs if item.role != "phase_d4_replay_source"
    ]
    sibling_basis_inputs.append(
        InputRef(
            artifact_id=sibling_replay_source_ref.artifact_id,
            role="phase_d4_replay_source",
            manifest_profile_sha256=sibling_replay_source_ref.manifest_profile_sha256,
        )
    )
    sibling_basis_ref = ctx.store.put_json(
        sibling_source_basis,
        PutOptions(
            kind=source_basis_manifest.kind,
            media_type=source_basis_manifest.media_type,
            schema=source_basis_manifest.artifact_schema,
            producer=source_basis_manifest.producer,
            inputs=sibling_basis_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    sibling_source_resolution = resolve_stress_score_components(
        ctx.store,
        [
            source_report.score_components[0].model_copy(
                update={"outcome_basis_ref": sibling_basis_ref}
            )
        ],
        expected_candidate_ref=candidate_ref,
        expected_run_id=state.run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    assert sibling_source_resolution.status == "invalid"
    assert sibling_source_resolution.reason_code == "phase_d4_selected_replay_source_mismatch"

    renamed_source_id = "old-display-id-without-suite-prefix"
    renamed_basis_ref = ctx.store.put_json(
        source_basis.model_copy(update={"source_id": renamed_source_id}),
        PutOptions(
            kind=source_basis_manifest.kind,
            media_type=source_basis_manifest.media_type,
            schema=source_basis_manifest.artifact_schema,
            producer=source_basis_manifest.producer,
            inputs=source_basis_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert renamed_basis_ref.manifest_profile_sha256 is not None
    renamed_component = source_report.score_components[0].model_copy(
        update={"component_id": renamed_source_id, "outcome_basis_ref": renamed_basis_ref}
    )
    base_source_manifest = ctx.store.get_manifest(stress_refs[0])
    assert base_source_manifest.artifact_schema is not None
    renamed_base_report = source_report.model_copy(
        update={"report_id": "renamed-old-d4-source", "score_components": [renamed_component]}
    )
    renamed_base_report_ref = ctx.store.put_json(
        renamed_base_report,
        PutOptions(
            kind=base_source_manifest.kind,
            media_type=base_source_manifest.media_type,
            schema=base_source_manifest.artifact_schema,
            producer=base_source_manifest.producer,
            inputs=[
                InputRef(
                    artifact_id=candidate_ref.artifact_id,
                    role="candidate",
                    manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=source_basis.benchmark_evaluation_ref.artifact_id,
                    role="benchmark_evaluation",
                    manifest_profile_sha256=(
                        source_basis.benchmark_evaluation_ref.manifest_profile_sha256
                    ),
                ),
                InputRef(
                    artifact_id=renamed_basis_ref.artifact_id,
                    role="stress_outcome_basis",
                    manifest_profile_sha256=renamed_basis_ref.manifest_profile_sha256,
                ),
                InputRef(
                    artifact_id=source_basis.benchmark_evaluation_ref.artifact_id,
                    role=PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
                    manifest_profile_sha256=(
                        source_basis.benchmark_evaluation_ref.manifest_profile_sha256
                    ),
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert renamed_base_report_ref.manifest_profile_sha256 is not None
    assert renamed_base_report.score_components[0].component_id == renamed_source_id
    assert source_basis.suite_id is not None
    same_suite_replacement_ref = _ensure_stress_test_report(
        ctx,
        ExperimentState(
            run_id=state.run_id,
            artifacts_index={ARTIFACT_STRESS_TEST_REPORT_REF: renamed_base_report_ref},
        ),
        evaluation_vector=selection_vector,
        supplemental_reports=stress_reports,
        supplemental_report_refs=stress_refs,
        phase_d4_suite_ids=[item.suite_id for item in selected_roster.suites],
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    assert same_suite_replacement_ref is not None
    same_suite_replacement = StressTestReport.model_validate(
        load_core_json_artifact(ctx.store, same_suite_replacement_ref)
    )
    replacement_manifest = ctx.store.get_manifest(same_suite_replacement_ref)
    assert replacement_manifest.artifact_schema is not None
    assert replacement_manifest.artifact_schema.version == same_suite_replacement.schema_version
    assert [item.component_id for item in same_suite_replacement.score_components] == [
        item.component_id for report in stress_reports for item in report.score_components
    ]
    assert renamed_source_id not in {
        item.component_id for item in same_suite_replacement.score_components
    }
    _, same_suite_resolution = resolve_stress_report_artifact(
        ctx.store,
        same_suite_replacement_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=state.run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
        require_phase_d4_roster=True,
    )
    expected_selected_total = sum(len(item.outcomes) for item in bases)
    assert same_suite_resolution.status == "available"
    assert same_suite_resolution.case_truth_status == "recomputed"
    assert same_suite_resolution.total_scenarios_evaluated == expected_selected_total
    assert same_suite_replacement.total_scenarios_evaluated == expected_selected_total
    same_suite_l5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "cand-1"},
        {
            "store": ctx.store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": same_suite_replacement_ref,
            "selection_evaluation_ref": selection_ref,
            "selection_evaluation": selection_evaluation,
            "run_id": state.run_id,
            "phase_d4_selected_evaluation_refs": selected_roster.rotating_evaluation_refs,
        },
    )
    assert same_suite_l5.feedback["stress_score_status"] == "available"
    assert same_suite_l5.feedback["stress_score_value"] == pytest.approx(
        same_suite_resolution.robustness_score
    )
    observed = same_suite_l5.feedback["stress_observed_sample_assessment"]
    assert observed["status"] == "complete"
    assert observed["score_scope"] == "observed_finite_scenarios"
    assert observed["observed_fraction"] == pytest.approx(
        same_suite_resolution.passed_count / expected_selected_total
    )
    assert observed["attempted"] == observed["finite_evaluated"] == expected_selected_total
    assert observed["violated_scenarios"] == (
        expected_selected_total - same_suite_resolution.passed_count
    )
    assert observed["unknown_or_nonfinite"] == 0
    assert observed["completeness"] is True
    assert observed["population_probability"] == "not_established"
    assert observed["model_uncertainty"] == "not_established"
    assert same_suite_l5.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1.0

    # Reopen the produced artifacts through the real aggregate consumer; the
    # finite fraction must not become a current or historical model estimate.
    funnel = FunnelOrchestrator([Level5RefutationGovernanceStage(require_hidden_holdout=False)])
    ticket = funnel.submit(
        candidate.model_dump(mode="json"),
        {
            "store": FileSystemCAS(ctx.store.root),
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": same_suite_replacement_ref,
            "selection_evaluation_ref": selection_ref,
            "selection_evaluation": selection_evaluation,
            "run_id": state.run_id,
            "phase_d4_selected_evaluation_refs": selected_roster.rotating_evaluation_refs,
        },
    )
    outcome = funnel.advance(ticket, policy="full")
    assert outcome.final_result is not None
    assert outcome.final_result.feedback["stress_observed_sample_assessment"] == observed
    assert outcome.uncertainty_envelope.uncertainties[UncertaintyType.MODEL].level == 1.0
    historical = outcome.final_result.feedback["uncertainty_historical_max"]
    assert historical["uncertainties"]["model"]["level"] == 1.0

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
            schema=SchemaInfo(
                name="polisyos.scientist.StressOutcomeBasis", version=wrong_basis.schema_version
            ),
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
            schema=SchemaInfo(
                name="polisyos.scientist.StressTestReport", version=wrong_report.schema_version
            ),
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
                InputRef(
                    artifact_id=source_evaluation_ref.artifact_id,
                    role=PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
                    manifest_profile_sha256=source_evaluation_ref.manifest_profile_sha256,
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    single_selected_roster = build_phase_d4_suite_roster(
        ctx.store,
        rotating_evaluation_refs=[source_evaluation_ref],
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_run_id=state.run_id,
        expected_loop_id=selection_evaluation.loop_id,
    )
    _, wrong_evaluation_resolution = resolve_stress_report_artifact(
        ctx.store,
        wrong_report_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=state.run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=single_selected_roster,
        require_phase_d4_roster=True,
    )
    assert wrong_evaluation_resolution.status == "invalid"
    assert wrong_evaluation_resolution.reason_code == "score_claim_without_resolved_basis"
    wrong_component_resolution = resolve_stress_score_components(
        ctx.store,
        [wrong_component],
        expected_candidate_ref=candidate_ref,
        expected_run_id=state.run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=single_selected_roster,
    )
    assert wrong_component_resolution.reason_code == "phase_d4_selected_suite_evaluation_mismatch"
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
            PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
        ]
        assert [item.manifest_profile_sha256 for item in source_manifest.inputs] == [
            candidate_ref.manifest_profile_sha256,
            basis.benchmark_evaluation_ref.manifest_profile_sha256,
            report.score_components[0].outcome_basis_ref.manifest_profile_sha256,
            basis.benchmark_evaluation_ref.manifest_profile_sha256,
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
        *[
            InputRef(
                artifact_id=ref.artifact_id,
                role=PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for ref in selected_roster.suite_evaluation_refs
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

    mismatched_run_ref = _ensure_stress_test_report(
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
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    assert mismatched_run_ref is not None
    mismatched_run_report = StressTestReport.model_validate(
        load_core_json_artifact(ctx.store, mismatched_run_ref)
    )
    assert mismatched_run_report.score_status == "unbound"
    assert mismatched_run_report.score_reason == (
        "phase_d4_selected_roster_context_missing_or_mismatched"
    )
    assert mismatched_run_report.robustness_score is None

    single_source_ref = _ensure_stress_test_report(
        ctx,
        ExperimentState(
            run_id=state.run_id,
            artifacts_index={ARTIFACT_STRESS_TEST_REPORT_REF: duplicate_base_ref},
        ),
        evaluation_vector=PolicyEvaluationVector(candidate_id="cand-1"),
        supplemental_reports=[duplicate_source_report],
        supplemental_report_refs=[stress_refs[0]],
        phase_d4_suite_ids=[duplicate_suite_id],
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    assert single_source_ref is not None
    single_source_report = StressTestReport.model_validate(
        load_core_json_artifact(ctx.store, single_source_ref)
    )
    _, single_source_resolution = resolve_stress_report_artifact(
        ctx.store,
        single_source_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=state.run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
        require_phase_d4_roster=True,
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
        *[
            InputRef(
                artifact_id=ref.artifact_id,
                role=PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for ref in selected_roster.suite_evaluation_refs
        ],
    ]
    assert ctx.store.get_manifest(single_source_ref).inputs == expected_single_inputs

    duplicate_ref = _ensure_stress_test_report(
        ctx,
        ExperimentState(
            run_id=state.run_id,
            artifacts_index={ARTIFACT_STRESS_TEST_REPORT_REF: duplicate_base_ref},
        ),
        evaluation_vector=PolicyEvaluationVector(candidate_id="cand-1"),
        supplemental_reports=[duplicate_source_report, duplicate_source_report],
        supplemental_report_refs=[stress_refs[0], stress_refs[0]],
        phase_d4_suite_ids=[duplicate_suite_id] * 2,
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
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
        *[
            InputRef(
                artifact_id=ref.artifact_id,
                role=PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for ref in selected_roster.suite_evaluation_refs
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
        ctx.store,
        duplicate_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=state.run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
        require_phase_d4_roster=True,
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
            "selection_evaluation_ref": selection_ref,
            "selection_evaluation": selection_evaluation,
            "run_id": state.run_id,
            "phase_d4_selected_evaluation_refs": selected_roster.rotating_evaluation_refs,
        },
    )
    assert duplicate_l5.feedback["stress_score_status"] == "invalid"
    assert duplicate_l5.feedback["stress_score_value"] is None
    assert duplicate_l5.feedback["stress_observed_sample_assessment"]["status"] == "unassessed"
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
    unscoped_ref = _ensure_stress_test_report(
        ctx,
        state,
        evaluation_vector=PolicyEvaluationVector(),
        phase_d4_suite_ids=["phase_d4_source_trace"],
        expected_candidate_ref=candidate_ref,
    )
    assert unscoped_ref is not None
    unscoped_report = StressTestReport.model_validate(
        load_core_json_artifact(ctx.store, unscoped_ref)
    )
    assert unscoped_report.score_profile == "continuous_severity_v1"
    assert unscoped_report.score_status == "profile_mismatch"
    assert unscoped_report.robustness_score is None
    unscoped_level5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {},
        {
            "store": ctx.store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": unscoped_ref,
        },
    )
    assert unscoped_level5.feedback["stress_score_status"] == "profile_mismatch"
    assert unscoped_level5.feedback["stress_observed_sample_assessment"]["status"] == "unassessed"

    selection_evaluation = BenchmarkEvaluation(
        loop_id="loop-continuous",
        suite_id="policy_selection",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.9},
        holdout_metrics={"score": 0.9},
        sample_counts={BenchmarkSplit.SELECTION.value: 10},
        promotable=True,
        runtime_split_type=BenchmarkSplit.SELECTION,
    )
    selection_ref = persist_benchmark_evaluation(
        ctx.store, selection_evaluation, return_selected_profile=True
    )
    scoped_state = ExperimentState(
        run_id=state.run_id,
        params=_phase_d4_raw_source_params(candidate_ref),
        artifacts_index=state.artifacts_index,
    )
    benchmark_refs, stress_refs, warnings = _run_and_register_phase_d4_challenge_suites(
        ctx,
        scoped_state,
        benchmark_registry=BenchmarkRegistry(
            tmp_path / "search_registry" / "continuous-benchmarks"
        ),
        candidate_ref=candidate_ref,
        selection_evaluation=selection_evaluation,
        selection_evaluation_ref=selection_ref,
        benchmark_scope={
            "artifact_family": "continuous_mixed_sources",
            "claim_mode": "estimation",
            "query_type": "policy",
            "estimator_name": "runtime",
            "readiness_target": "deployment_ready",
        },
        artifacts_index={},
    )
    assert warnings == ()
    assert stress_refs
    reports = [
        StressTestReport.model_validate(load_core_json_artifact(ctx.store, ref))
        for ref in stress_refs
    ]
    roster = build_phase_d4_suite_roster(
        ctx.store,
        rotating_evaluation_refs=benchmark_refs,
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_run_id=state.run_id,
        expected_loop_id=selection_evaluation.loop_id,
    )
    composed_ref = _ensure_stress_test_report(
        ctx,
        scoped_state,
        evaluation_vector=PolicyEvaluationVector(),
        supplemental_reports=reports,
        supplemental_report_refs=stress_refs,
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=roster,
    )
    assert composed_ref is not None
    assert composed_ref.manifest_profile_sha256 is not None
    composed_manifest = ctx.store.get_manifest(composed_ref)
    assert [item.role for item in composed_manifest.inputs] == [
        "candidate",
        "base_stress_report",
        *("supplemental_stress_report" for _ in stress_refs),
        *("stress_outcome_basis" for report in reports for _ in report.score_components),
        *(PHASE_D4_SELECTED_EVALUATION_INPUT_ROLE for _ in roster.suite_evaluation_refs),
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
            "selection_evaluation": selection_evaluation,
            "selection_evaluation_ref": selection_ref,
            "run_id": state.run_id,
            "phase_d4_selected_evaluation_refs": benchmark_refs,
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


def _phase_d4_raw_source_params(candidate_ref: ArtifactRef) -> dict[str, object]:
    agents = ("leader", "follower")
    action_spaces = {"leader": ("L1", "L2"), "follower": ("F1", "F2")}
    leader_payoffs = {
        encode_action_profile({"leader": "L1", "follower": "F1"}, agent_order=agents): 3.0,
        encode_action_profile({"leader": "L1", "follower": "F2"}, agent_order=agents): 1.0,
        encode_action_profile({"leader": "L2", "follower": "F1"}, agent_order=agents): 2.0,
        encode_action_profile({"leader": "L2", "follower": "F2"}, agent_order=agents): 0.0,
    }
    follower_payoffs = {
        encode_action_profile({"leader": "L1", "follower": "F1"}, agent_order=agents): 2.0,
        encode_action_profile({"leader": "L1", "follower": "F2"}, agent_order=agents): 0.0,
        encode_action_profile({"leader": "L2", "follower": "F1"}, agent_order=agents): 1.0,
        encode_action_profile({"leader": "L2", "follower": "F2"}, agent_order=agents): 3.0,
    }
    tables = {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=agents,
            action_spaces=action_spaces,
            payoffs=leader_payoffs,
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=agents,
            action_spaces=action_spaces,
            payoffs=follower_payoffs,
        ),
    }

    def ref(seed: str, *, kind: str) -> ArtifactRefModel:
        return ArtifactRefModel(
            artifact_id=ArtifactID.model_validate(
                f"sha256:{hashlib.sha256(seed.encode()).hexdigest()}"
            ),
            kind=kind,
            media_type="application/json",
        )

    contract = StrategicSCM(
        base_graph_ref=ref("d4-graph", kind="ir.causal_graph_model").model_dump(mode="json"),
        strategic_agents=agents,
        utility_refs={
            "leader": StrategicPayoffTableRef.model_validate(
                ref("d4-leader", kind="ir.strategic_payoff_table").model_dump(mode="json")
            ),
            "follower": StrategicPayoffTableRef.model_validate(
                ref("d4-follower", kind="ir.strategic_payoff_table").model_dump(mode="json")
            ),
        },
        policy_rule_ref=ArtifactRefModel.model_validate(candidate_ref.model_dump(mode="json")),
        equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
        compute_budget=ComputeBudget(max_sim_runs=16.0),
    )
    return {
        "strategic_scm": contract.model_dump(mode="json"),
        "strategic_payoff_tables": {
            agent: table.model_dump(mode="json") for agent, table in tables.items()
        },
        "baseline_policy_value": 0.5,
    }


def test_phase_d4_case_replay_rejects_same_rate_case_swap(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_d4_case_truth")
    candidate_ref = _persist_policy_candidate(ctx.store, "candidate-d4-case-truth")
    run_id = "R_d4_case_truth"
    loop_id = "loop-case-truth"
    selection_evaluation = BenchmarkEvaluation(
        loop_id=loop_id,
        suite_id="policy_selection",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 0.9},
        holdout_metrics={"score": 0.9},
        sample_counts={BenchmarkSplit.SELECTION.value: 10},
        promotable=True,
        runtime_split_type=BenchmarkSplit.SELECTION,
    )
    selection_ref = persist_benchmark_evaluation(
        ctx.store, selection_evaluation, return_selected_profile=True
    )
    params = _phase_d4_raw_source_params(candidate_ref)
    # Raw solver and budget controls pass; this actual observed-summary audit fails.
    # Its row identity must survive replay even when a forged report keeps the same rate.
    params["strategic_response_summary"] = {"fallback_mode": "static_ate"}
    state = ExperimentState(run_id=run_id, params=params)
    assert type(state.params["baseline_policy_value"]) is Decimal
    assert state.params["baseline_policy_value"] == Decimal("0.5")
    source_context = build_phase_d4_replay_source(
        run_id=run_id,
        loop_id=loop_id,
        candidate_ref=candidate_ref,
        selection_evaluation_ref=selection_ref,
        selection_evaluation=selection_evaluation,
        params=state.params,
        artifacts_index={},
        store=ctx.store,
    )
    assert source_context.selection_evaluation_ref == selection_ref
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")
    benchmark_refs, stress_refs, warnings = _run_and_register_phase_d4_challenge_suites(
        ctx,
        state,
        benchmark_registry=registry,
        candidate_ref=candidate_ref,
        selection_evaluation=selection_evaluation,
        selection_evaluation_ref=selection_ref,
        benchmark_scope={
            "artifact_family": "phase_d4_case_truth",
            "claim_mode": "estimation",
            "query_type": "policy",
            "estimator_name": "runtime",
            "readiness_target": "deployment_ready",
        },
        artifacts_index={},
    )
    assert len(benchmark_refs) == len(stress_refs) == 2
    selected_roster = build_phase_d4_suite_roster(
        ctx.store,
        rotating_evaluation_refs=benchmark_refs,
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_run_id=run_id,
        expected_loop_id=loop_id,
    )
    assert {item.suite_id for item in selected_roster.suites} == {
        "strategic_gaming_v1",
        "multiplicity_disclosure_v1",
    }
    source_reports = [
        StressTestReport.model_validate(load_core_json_artifact(ctx.store, ref))
        for ref in stress_refs
    ]
    stress_report_ref = _ensure_stress_test_report(
        ctx,
        state,
        evaluation_vector=PolicyEvaluationVector(),
        supplemental_reports=source_reports,
        supplemental_report_refs=stress_refs,
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    assert stress_report_ref is not None
    report = StressTestReport.model_validate(load_core_json_artifact(ctx.store, stress_report_ref))
    component = next(
        item
        for item in report.score_components
        if StressOutcomeBasis.model_validate(
            load_core_json_artifact(ctx.store, item.outcome_basis_ref)
        ).suite_id
        == "strategic_gaming_v1"
    )
    basis_ref = component.outcome_basis_ref
    basis = StressOutcomeBasis.model_validate(load_core_json_artifact(ctx.store, basis_ref))
    evaluation_ref = basis.benchmark_evaluation_ref
    source_ref = basis.phase_d4_replay_source_ref
    if evaluation_ref is None or source_ref is None:
        raise AssertionError("phase_d4_selected_source_edges_missing")
    persisted_source, _ = load_selected_phase_d4_replay_source(ctx.store, source_ref)
    assert type(persisted_source.params["baseline_policy_value"]) is Decimal
    assert persisted_source.params["baseline_policy_value"] == Decimal("0.5")
    evaluation = BenchmarkEvaluation.model_validate(
        load_core_json_artifact(ctx.store, evaluation_ref)
    )
    _, no_roster_resolution = resolve_stress_report_artifact(
        ctx.store,
        stress_report_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_selection_evaluation_ref=selection_ref,
    )
    assert no_roster_resolution.status == "invalid"
    assert no_roster_resolution.reason_code == "score_claim_without_resolved_basis"
    assert no_roster_resolution.robustness_score is None
    no_roster_components = resolve_stress_score_components(
        ctx.store,
        report.score_components,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_selection_evaluation_ref=selection_ref,
    )
    assert no_roster_components.status == "unbound"
    assert no_roster_components.reason_code == "phase_d4_selected_roster_missing"
    legacy_basis = basis.model_copy(
        update={"schema_version": "1.0", "phase_d4_replay_source_ref": None}
    )
    legacy_report = report.model_copy(update={"schema_version": "1.1", "case_truth_reason": None})
    legacy_basis_wire_shape = "phase_d4_replay_source_ref" not in legacy_basis.model_dump(
        mode="json"
    )
    legacy_report_wire_shape = "case_truth_status" not in legacy_report.model_dump(mode="json")
    positive_report, positive_resolution = resolve_stress_report_artifact(
        ctx.store,
        stress_report_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    _unanchored_report, missing_context_resolution = resolve_stress_report_artifact(
        ctx.store,
        stress_report_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_phase_d4_roster=selected_roster,
    )

    report_manifest = ctx.store.get_manifest(stress_report_ref)

    def persist_control_report(control_component, *, schema_version: str) -> ArtifactRef:
        report_body = report.model_copy(
            update={
                "schema_version": schema_version,
                "score_components": [
                    control_component if item == component else item
                    for item in report.score_components
                ],
                "case_truth_status": "not_established",
                "case_truth_reason": None,
            }
        )
        control_basis = StressOutcomeBasis.model_validate(
            load_core_json_artifact(ctx.store, control_component.outcome_basis_ref)
        )
        evaluation_ref = control_basis.benchmark_evaluation_ref
        report_inputs = [
            item for item in report_manifest.inputs if item.role != "stress_outcome_basis"
        ]
        report_inputs.extend(
            InputRef(
                artifact_id=item.outcome_basis_ref.artifact_id,
                role="stress_outcome_basis",
                manifest_profile_sha256=item.outcome_basis_ref.manifest_profile_sha256,
            )
            for item in report_body.score_components
        )
        if evaluation_ref is None:
            raise AssertionError("phase_d4_control_evaluation_ref_missing")
        return ctx.store.put_json(
            report_body,
            PutOptions(
                kind="scientist.stress_test_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.StressTestReport",
                    version=schema_version,
                ),
                inputs=report_inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    def evaluate_report_in_level5(report_ref: ArtifactRef):
        return Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
            {"candidate_id": "candidate-d4-case-truth"},
            {
                "store": ctx.store,
                "policy_candidate_ref": candidate_ref,
                "stress_test_report_ref": report_ref,
                "selection_evaluation_ref": selection_ref,
                "selection_evaluation": selection_evaluation,
                "run_id": run_id,
                "phase_d4_selected_evaluation_refs": benchmark_refs,
            },
        )

    # A source-kind-driven resolver must keep a legacy D4 basis limited even if both display
    # identifiers are renamed so they no longer carry the old phase_d4 prefix.
    renamed_legacy_id = "unrelated-display-id"
    renamed_legacy_basis = legacy_basis.model_copy(update={"source_id": renamed_legacy_id})
    legacy_basis_inputs = [
        InputRef(
            artifact_id=candidate_ref.artifact_id,
            role="candidate",
            manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=evaluation_ref.artifact_id,
            role="benchmark_evaluation",
            manifest_profile_sha256=evaluation_ref.manifest_profile_sha256,
        ),
    ]
    renamed_legacy_basis_ref = ctx.store.put_json(
        renamed_legacy_basis,
        PutOptions(
            kind="scientist.stress_outcome_basis",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.StressOutcomeBasis", version=legacy_basis.schema_version
            ),
            inputs=legacy_basis_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    renamed_legacy_component = component.model_copy(
        update={
            "component_id": renamed_legacy_id,
            "outcome_basis_ref": renamed_legacy_basis_ref,
        }
    )
    renamed_legacy_report_ref = persist_control_report(
        renamed_legacy_component, schema_version="1.1"
    )
    renamed_legacy_report, renamed_legacy_resolution = resolve_stress_report_artifact(
        ctx.store,
        renamed_legacy_report_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    renamed_legacy_level5 = evaluate_report_in_level5(renamed_legacy_report_ref)

    wrong_id_component = component.model_copy(
        update={"component_id": "renamed-component-with-unmodified-basis-id"}
    )
    wrong_id_report_ref = persist_control_report(wrong_id_component, schema_version="1.2")
    _wrong_id_report, wrong_id_resolution = resolve_stress_report_artifact(
        ctx.store,
        wrong_id_report_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    wrong_id_level5 = evaluate_report_in_level5(wrong_id_report_ref)

    wrong_kind_id = "phase_d4:mislabelled-kind"
    wrong_kind_basis = legacy_basis.model_copy(
        update={"source_kind": "adversarial_plan", "source_id": wrong_kind_id}
    )
    wrong_kind_basis_ref = ctx.store.put_json(
        wrong_kind_basis,
        PutOptions(
            kind="scientist.stress_outcome_basis",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.StressOutcomeBasis", version=legacy_basis.schema_version
            ),
            inputs=legacy_basis_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    wrong_kind_component = component.model_copy(
        update={"component_id": wrong_kind_id, "outcome_basis_ref": wrong_kind_basis_ref}
    )
    wrong_kind_report_ref = persist_control_report(wrong_kind_component, schema_version="1.1")
    _wrong_kind_report, wrong_kind_resolution = resolve_stress_report_artifact(
        ctx.store,
        wrong_kind_report_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    wrong_kind_level5 = evaluate_report_in_level5(wrong_kind_report_ref)

    # The source basis cannot nominate its own selected context. Produce a second real suite
    # with a different selected evaluation while the protected consumer keeps the original ref.
    alternate_selection = selection_evaluation.model_copy(
        update={"selection_metrics": {"score": 0.1}}
    )
    alternate_selection_ref = persist_benchmark_evaluation(
        ctx.store,
        alternate_selection,
        return_selected_profile=True,
    )
    alternate_state = ExperimentState(run_id=run_id, params=params)
    alternate_registry = BenchmarkRegistry(tmp_path / "search_registry" / "alternate-benchmarks")
    alternate_benchmark_refs, alternate_stress_refs, alternate_warnings = (
        _run_and_register_phase_d4_challenge_suites(
            ctx,
            alternate_state,
            benchmark_registry=alternate_registry,
            candidate_ref=candidate_ref,
            selection_evaluation=alternate_selection,
            selection_evaluation_ref=alternate_selection_ref,
            benchmark_scope={
                "artifact_family": "phase_d4_case_truth_alternate",
                "claim_mode": "estimation",
                "query_type": "policy",
                "estimator_name": "runtime",
                "readiness_target": "deployment_ready",
            },
            artifacts_index={},
        )
    )
    assert alternate_warnings == ()
    assert len(alternate_benchmark_refs) == len(alternate_stress_refs) == 2
    alternate_roster = build_phase_d4_suite_roster(
        ctx.store,
        rotating_evaluation_refs=alternate_benchmark_refs,
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=alternate_selection_ref,
        expected_run_id=run_id,
        expected_loop_id=loop_id,
    )
    alternate_report_ref = _ensure_stress_test_report(
        ctx,
        alternate_state,
        evaluation_vector=PolicyEvaluationVector(),
        supplemental_reports=[
            StressTestReport.model_validate(load_core_json_artifact(ctx.store, ref))
            for ref in alternate_stress_refs
        ],
        supplemental_report_refs=alternate_stress_refs,
        expected_candidate_ref=candidate_ref,
        expected_selection_evaluation_ref=alternate_selection_ref,
        expected_phase_d4_roster=alternate_roster,
    )
    assert alternate_report_ref is not None
    alternate_report = StressTestReport.model_validate(
        load_core_json_artifact(ctx.store, alternate_report_ref)
    )
    alternate_basis = next(
        value
        for item in alternate_report.score_components
        if (
            value := StressOutcomeBasis.model_validate(
                load_core_json_artifact(ctx.store, item.outcome_basis_ref)
            )
        ).suite_id
        == "strategic_gaming_v1"
    )
    alternate_source_ref = alternate_basis.phase_d4_replay_source_ref
    assert alternate_source_ref is not None
    alternate_source, _alternate_source_manifest = load_selected_phase_d4_replay_source(
        ctx.store, alternate_source_ref
    )
    assert alternate_source.selection_evaluation_ref == alternate_selection_ref
    assert alternate_basis.outcomes == basis.outcomes
    assert alternate_basis.expected_scenario_ids == basis.expected_scenario_ids
    assert sum(item.status == "failed" for item in alternate_basis.outcomes) == sum(
        item.status == "failed" for item in basis.outcomes
    )
    _alternate_report, alternate_context_resolution = resolve_stress_report_artifact(
        ctx.store,
        alternate_report_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    alternate_context_level5 = Level5RefutationGovernanceStage(
        require_hidden_holdout=False
    ).evaluate(
        {"candidate_id": "candidate-d4-case-truth"},
        {
            "store": ctx.store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": alternate_report_ref,
            "selection_evaluation_ref": selection_ref,
            "selection_evaluation": selection_evaluation,
            "run_id": run_id,
            "phase_d4_selected_evaluation_refs": benchmark_refs,
        },
    )

    failed_index = next(
        index for index, item in enumerate(basis.outcomes) if item.status == "failed"
    )
    passed_index = next(
        index for index, item in enumerate(basis.outcomes) if item.status == "passed"
    )
    original_failed = basis.outcomes[failed_index]
    original_passed = basis.outcomes[passed_index]
    swapped = list(basis.outcomes)
    swapped[failed_index] = original_failed.model_copy(
        update={"status": "passed", "vulnerabilities": []}
    )
    swapped[passed_index] = original_passed.model_copy(
        update={"status": "failed", "vulnerabilities": original_failed.vulnerabilities}
    )
    tampered_basis = basis.model_copy(update={"outcomes": swapped})
    original_rate = evaluation.selection_metrics["challenge_pass_rate"]
    tampered_basis_manifest = ctx.store.get_manifest(basis_ref)
    tampered_basis_ref = ctx.store.put_json(
        tampered_basis,
        PutOptions(
            kind="scientist.stress_outcome_basis",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressOutcomeBasis", version="2.0"),
            inputs=list(tampered_basis_manifest.inputs),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    tampered_component = component.model_copy(update={"outcome_basis_ref": tampered_basis_ref})
    tampered_report = positive_report.model_copy(
        update={
            "score_components": [
                tampered_component if item == component else item
                for item in positive_report.score_components
            ],
            "vulnerabilities": [
                vulnerability
                for item in positive_report.score_components
                for row in (
                    swapped
                    if item == component
                    else StressOutcomeBasis.model_validate(
                        load_core_json_artifact(ctx.store, item.outcome_basis_ref)
                    ).outcomes
                )
                for vulnerability in row.vulnerabilities
            ],
        }
    )
    tampered_report_ref = ctx.store.put_json(
        tampered_report,
        PutOptions(
            kind="scientist.stress_test_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.StressTestReport", version="1.2"),
            inputs=[
                *(item for item in report_manifest.inputs if item.role != "stress_outcome_basis"),
                *(
                    InputRef(
                        artifact_id=item.outcome_basis_ref.artifact_id,
                        role="stress_outcome_basis",
                        manifest_profile_sha256=item.outcome_basis_ref.manifest_profile_sha256,
                    )
                    for item in tampered_report.score_components
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _tampered_report, negative_resolution = resolve_stress_report_artifact(
        ctx.store,
        tampered_report_ref,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    negative_component_resolution = resolve_stress_score_components(
        ctx.store,
        tampered_report.score_components,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_selection_evaluation_ref=selection_ref,
        expected_phase_d4_roster=selected_roster,
    )
    assert negative_component_resolution.reason_code == "phase_d4_case_rows_or_projection_mismatch"
    level5 = Level5RefutationGovernanceStage(require_hidden_holdout=False).evaluate(
        {"candidate_id": "candidate-d4-case-truth"},
        {
            "store": ctx.store,
            "policy_candidate_ref": candidate_ref,
            "stress_test_report_ref": tampered_report_ref,
            "selection_evaluation_ref": selection_ref,
            "selection_evaluation": selection_evaluation,
            "run_id": run_id,
            "phase_d4_selected_evaluation_refs": benchmark_refs,
        },
    )

    def promotion_source_error(report_ref: ArtifactRef) -> str | None:
        bundle = PromotionEvidenceBundle(
            run_id=run_id,
            produced_by_run_id=run_id,
            candidate_ref=candidate_ref,
            selection_evaluation_ref=selection_ref,
            rotating_challenge_evaluation_refs=benchmark_refs,
            stress_test_report_ref=report_ref,
        )
        source_basis = _PhaseD4ChallengeSourceBasis(stress_report_ref=report_ref)
        try:
            bundle.assert_runtime_compatible(
                run_id=run_id,
                store=ctx.store,
                expected_loop_id=loop_id,
                source_basis_by_role={
                    "selection_evaluation_ref": _PolicyRuntimeSelectionSourceBasis(
                        expected_evaluation=selection_evaluation
                    ),
                    "rotating_challenge_evaluation_refs": source_basis,
                },
            )
        except ValueError as exc:
            return str(exc)
        return None

    positive_promotion_error = promotion_source_error(stress_report_ref)
    negative_promotion_error = promotion_source_error(tampered_report_ref)
    alternate_context_promotion_error = promotion_source_error(alternate_report_ref)
    print(  # noqa: T201
        "phase_d4_case_replay_probe "
        f"warnings={warnings!r} benchmark_refs={len(benchmark_refs)} "
        f"positive={positive_resolution.status}/{positive_resolution.case_truth_status} "
        f"renamed_legacy={renamed_legacy_resolution.status}/"
        f"{renamed_legacy_resolution.reason_code}/required="
        f"{renamed_legacy_resolution.case_truth_required} "
        f"wrong_id={wrong_id_resolution.status}/{wrong_id_resolution.reason_code} "
        f"wrong_kind={wrong_kind_resolution.status}/{wrong_kind_resolution.reason_code} "
        f"wrong_id_l5={wrong_id_level5.feedback.get('stress_score_status')} "
        f"wrong_kind_l5={wrong_kind_level5.feedback.get('stress_score_status')} "
        f"missing_context={missing_context_resolution.status}/"
        f"{missing_context_resolution.reason_code} "
        f"alternate_context={alternate_context_resolution.status}/"
        f"{alternate_context_resolution.reason_code} "
        f"alternate_l5={alternate_context_level5.feedback.get('stress_score_status')} "
        f"negative={negative_resolution.status}/{negative_resolution.reason_code} "
        f"level5={level5.feedback.get('stress_score_status')}/"
        f"{level5.feedback.get('stress_score_value')} "
        f"promotion_positive={positive_promotion_error!r} "
        f"promotion_alternate_context={alternate_context_promotion_error!r} "
        f"promotion_negative={negative_promotion_error!r} "
        f"rate={original_rate} swapped_failures="
        f"{sum(item.status == 'failed' for item in swapped)}"
    )
    assert warnings == ()
    assert len(benchmark_refs) == 2
    assert report.schema_version == "1.2"
    assert legacy_basis_wire_shape
    assert legacy_report_wire_shape
    assert positive_resolution.status == "available"
    assert positive_resolution.case_truth_required is True
    assert positive_resolution.case_truth_status == "recomputed"
    assert positive_report._case_truth_required is True
    assert missing_context_resolution.status == "invalid"
    assert missing_context_resolution.reason_code == "score_claim_without_resolved_basis"
    assert missing_context_resolution.robustness_score is None
    missing_context_components = resolve_stress_score_components(
        ctx.store,
        report.score_components,
        expected_candidate_ref=candidate_ref,
        expected_run_id=run_id,
        expected_phase_d4_roster=selected_roster,
    )
    assert missing_context_components.status == "unbound"
    assert missing_context_components.reason_code == (
        "phase_d4_selected_roster_context_missing_or_mismatched"
    )
    assert renamed_legacy_resolution.status != "available"
    assert renamed_legacy_resolution.robustness_score is None
    assert renamed_legacy_resolution.observed_sample_assessment is None
    assert renamed_legacy_resolution.case_truth_required is True
    assert renamed_legacy_report.is_robust is False
    assert renamed_legacy_level5.feedback["stress_score_status"] != "available"
    assert renamed_legacy_level5.feedback["stress_score_value"] is None
    assert (
        renamed_legacy_level5.feedback["stress_observed_sample_assessment"]["status"]
        == "unassessed"
    )
    assert wrong_id_resolution.status != "available"
    assert wrong_id_resolution.robustness_score is None
    assert wrong_id_level5.feedback["stress_score_status"] != "available"
    assert wrong_id_level5.feedback["stress_score_value"] is None
    assert wrong_kind_resolution.status != "available"
    assert wrong_kind_resolution.robustness_score is None
    assert wrong_kind_level5.feedback["stress_score_status"] != "available"
    assert wrong_kind_level5.feedback["stress_score_value"] is None
    assert alternate_context_resolution.status == "invalid"
    assert alternate_context_resolution.reason_code == (
        "stress_report_selected_phase_d4_roster_lineage_mismatch"
    )
    assert alternate_context_level5.feedback["stress_score_status"] == "invalid"
    assert alternate_context_level5.feedback["stress_score_value"] is None
    assert positive_report.case_truth_status == "recomputed"
    assert sum(item.status == "failed" for item in swapped) == sum(
        item.status == "failed" for item in basis.outcomes
    )
    assert tampered_basis.expected_scenario_ids == basis.expected_scenario_ids
    assert original_rate == evaluation.selection_metrics["challenge_pass_rate"]
    assert negative_resolution.status == "invalid"
    assert negative_resolution.robustness_score is None
    assert level5.feedback["stress_score_status"] == "invalid"
    assert level5.feedback["stress_score_case_truth_status"] == "not_established"
    assert level5.feedback["stress_score_value"] is None
    assert positive_promotion_error is None
    assert negative_promotion_error == (
        "PromotionEvidenceBundle rotating challenge cases were not source-replayed."
    )
    assert alternate_context_promotion_error == (
        "PromotionEvidenceBundle rotating challenge cases were not source-replayed."
    )
