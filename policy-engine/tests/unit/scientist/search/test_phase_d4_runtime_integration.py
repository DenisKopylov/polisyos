from __future__ import annotations

import logging

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
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, BenchmarkSplit
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _run_and_register_phase_d4_challenge_suites,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry


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
        ctx.store,
        StrategicClosureSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            equilibrium_concept=StrategicEquilibriumConcept.STACKELBERG,
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
            profile_count=4,
            equilibrium_count=2,
        ),
    )
    equilibrium_set_ref = persist_equilibrium_set_summary(
        ctx.store,
        EquilibriumSetSummary(
            equilibrium_profiles=(),
            equilibrium_count=0,
        ),
    )
    selected_equilibrium_ref = persist_equilibrium_selection_summary(
        ctx.store,
        EquilibriumSelectionSummary(
            selected_equilibrium={"leader": "A", "follower": "X"},
            equilibrium_selection_dependence="follower_best_response_tie_breaking",
        ),
    )
    post_adaptation_policy_value_ref = persist_post_adaptation_policy_value_summary(
        ctx.store,
        PostAdaptationPolicyValueSummary(
            fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
            baseline_policy_value=1.0,
            point_value=1.2,
        ),
    )
    strategic_bundle_ref = persist_strategic_response_bundle(
        ctx.store,
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
    assert len(stress_refs) == 1

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
