from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import build_data_readiness_report
from polisyos.scientist.autotune.models import persist_benchmark_evaluation
from polisyos.scientist.autotune.registry import ChampionRegistry
from polisyos.scientist.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema
from polisyos.scientist.replay.verification import load_replay_verification_report
from polisyos.scientist.search.judge_stack import JudgeName, JudgeStack, PolicyPromotionCoordinator
from tests.unit.scientist.search.test_phase_b_policy_runtime import (
    _benchmark,
    _candidate,
    _causal_effect_report,
    _cross_graph_profile,
    _distributional_report,
    _evaluation_vector,
    _persist_replay_support,
    _prior_knowledge_bundle,
    _uncertainty,
)


def _phase2_bundle(
    tmp_path,
    *,
    artifact_family: str,
    estimator_name: str,
    query_type: str,
):
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "search_registry", store=store)
    coordinator = PolicyPromotionCoordinator(champion_registry=registry, store=store)

    candidate = _candidate(evidence_depth="replicated")
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    selection_eval, hidden_holdout = _benchmark(candidate_ref, holdout_score=0.94)
    evaluation_ref = persist_benchmark_evaluation(store, selection_eval)
    replay_ref, replay_verification_ref = _persist_replay_support(
        store,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        run_id=f"{artifact_family}-phase2",
    )
    replay_verification_report = load_replay_verification_report(store, replay_verification_ref)

    return coordinator.build_input_bundle(
        candidate=candidate,
        benchmark_evaluation=selection_eval,
        hidden_holdout_evaluation=hidden_holdout,
        evaluation_vector=_evaluation_vector(candidate),
        distributional_report=_distributional_report(),
        causal_effect_report=_causal_effect_report(),
        data_readiness_report=build_data_readiness_report(
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
        ),
        artifact_family=artifact_family,
        estimator_name=estimator_name,
        query_type=query_type,
        cross_graph_profile=_cross_graph_profile(),
        prior_knowledge_bundle=_prior_knowledge_bundle(status="ok", coverage_complete=True),
        governance_report={"verdict": "approve", "issues": []},
        uncertainty_envelope=_uncertainty(0.1),
        replay_bundle_ref=replay_ref,
        replay_verification_ref=replay_verification_ref,
        replay_verification_report=replay_verification_report,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10.0"))},
            spent={"run": Decimal("1.0")},
        ),
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "checkpoints": [
                {"stage": "data_loaded", "timestamp": "2026-03-25T10:00:00Z"},
                {"stage": "estimation_complete", "timestamp": "2026-03-25T10:01:00Z"},
            ],
            "verified_claims": [{"source_ref": "source:1", "confidence": 0.9}],
            "data_sources": [{"name": "dataset", "last_updated": "2026-03-01T00:00:00+00:00"}],
            "knowledge_metadata": {"last_updated": "2026-03-01T00:00:00+00:00"},
            "pii_scan_results": {"max_severity": "none", "total_entities_found": 0},
            "audit_lineage_complete": True,
        },
        compute_cost_usd=1.0,
        replay_cost_usd=0.5,
        expected_improvement=2.0,
        timeout_risk=0.1,
    )


def test_phase2_econometrics_frontier_six_judge_promote(tmp_path) -> None:
    verdict = JudgeStack().evaluate(
        _phase2_bundle(
            tmp_path,
            artifact_family="econometrics_frontier",
            estimator_name="high_dimensional_post_selection_iv",
            query_type="post_selection_inference",
        )
    )

    assert verdict.composite_decision == "promote"


def test_phase5_preflight_evaluates_all_six_judges(tmp_path) -> None:
    verdict = JudgeStack().evaluate_phase5_preflight(
        _phase2_bundle(
            tmp_path,
            artifact_family="econometrics_frontier",
            estimator_name="high_dimensional_post_selection_iv",
            query_type="post_selection_inference",
        )
    )

    assert set(verdict.per_judge) == {judge.value for judge in JudgeName}
    assert all(
        judge_status.violations != ["judge_inactive"] for judge_status in verdict.per_judge.values()
    )


def test_phase2_distributional_frontier_six_judge_promote(tmp_path) -> None:
    verdict = JudgeStack().evaluate(
        _phase2_bundle(
            tmp_path,
            artifact_family="distributional_frontier",
            estimator_name="distributional_bounds_engine",
            query_type="partial_identification",
        )
    )

    assert verdict.composite_decision == "promote"


def test_phase2_mobility_frontier_six_judge_promote(tmp_path) -> None:
    verdict = JudgeStack().evaluate(
        _phase2_bundle(
            tmp_path,
            artifact_family="mobility_frontier",
            estimator_name="attrition_adjusted_transition_matrix",
            query_type="mobility_under_attrition",
        )
    )

    assert verdict.composite_decision == "promote"


def test_phase2_network_identification_six_judge_promote(tmp_path) -> None:
    verdict = JudgeStack().evaluate(
        _phase2_bundle(
            tmp_path,
            artifact_family="network_identification",
            estimator_name="network_missingness_frontier",
            query_type="partial_observability_bounds",
        )
    )

    assert verdict.composite_decision == "promote"


def test_phase2_spatial_identification_six_judge_promote(tmp_path) -> None:
    verdict = JudgeStack().evaluate(
        _phase2_bundle(
            tmp_path,
            artifact_family="spatial_identification",
            estimator_name="spatial_interference_frontier",
            query_type="maup_and_interference_identification",
        )
    )

    assert verdict.composite_decision == "promote"
