from __future__ import annotations

import logging
from dataclasses import replace
from types import SimpleNamespace

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
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
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.governance.stress_scenarios import (
    StressScenarioRunner,
    load_stress_test_report,
)
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.methods.doe.stress_report import StressOutcomeBasis, StressTestReport
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.funnel.level5_refutation_governance import (
    Level5RefutationGovernanceStage,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_reporting import (
    _extract_level5_gate,
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


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def test_phase_d4_runtime_helper_persists_rotating_and_stress_artifacts(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_d4_runtime")
    candidate_ref = ctx.store.put_json(
        {"candidate_id": "cand-1"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
    )
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
        params={"policy_loop_id": "loop-a"},
        artifacts_index={
            ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF: strategic_bundle_ref,
        },
    )
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
    assert bundle.adversarial_artifact_refs == stress_refs

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

    merged_ref = _ensure_stress_test_report(
        ctx,
        state,
        evaluation_vector=PolicyEvaluationVector(candidate_id="cand-1"),
        supplemental_reports=stress_reports,
        phase_d4_suite_ids=[report.metadata["challenge_suite_id"] for report in stress_reports],
        expected_candidate_ref=candidate_ref,
    )
    assert merged_ref is not None
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
    other_candidate_ref = ctx.store.put_json(
        {"candidate_id": "cand-1-other"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
    )
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
    candidate_ref = ctx.store.put_json(
        {"candidate_id": "candidate-continuous"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
    )
    produced = StressScenarioRunner(ctx.store).run(baseline_metrics={"policy_value": 100.0})
    source_report = load_stress_test_report(ctx.store, produced.stress_test_report_ref)
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
    )
    assert composed_ref is not None
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
    candidate_ref = ctx.store.put_json(
        {"candidate_id": "candidate-statuses"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
    )
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
    candidate_ref = ctx.store.put_json(
        {"candidate_id": "cand-2"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
    )
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
