from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    BacktestScenario,
    BiasDirection,
    NativeBacktestVerificationRequiredError,
    OutcomeComparison,
    load_backtest_report,
    load_backtest_report_candidate,
    persist_backtest_report,
)
from polisyos.ir.analytics.causal import CausalMethod
from polisyos.ir.analytics.hte import (
    FeatureImportance,
    HTEResult,
    PolicyRecommendation,
    SubgroupEffect,
    TargetingRule,
    load_hte_result,
    load_policy_recommendation,
    persist_hte_result,
    persist_policy_recommendation,
)
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.trust_scorer import TrustScorer


def test_hte_result_persist_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    result = HTEResult(
        method=CausalMethod.CAUSAL_FOREST,
        ate=0.25,
        ate_ci_lower=0.1,
        ate_ci_upper=0.4,
        cate_values=[0.1, 0.2, 0.3],
        cate_std_values=[0.01, 0.01, 0.02],
        subgroup_effects=[
            SubgroupEffect(
                subgroup_id="q1",
                subgroup_label="Q1",
                subgroup_query="cate < 0.2",
                n_units=2,
                cate_mean=0.15,
                cate_std=0.05,
                cate_ci_lower=0.1,
                cate_ci_upper=0.2,
            )
        ],
        feature_importances=[
            FeatureImportance(feature_name="income", importance_score=0.8, importance_rank=1)
        ],
        n_samples=3,
        n_treated=1,
        n_control=2,
        n_features=1,
        feature_names=["income"],
    )
    ref = persist_hte_result(_ensure_ir_artifact_store(store), result)
    loaded = load_hte_result(_ensure_ir_artifact_store(store), ref)
    assert loaded.method == CausalMethod.CAUSAL_FOREST
    assert loaded.n_samples == 3
    assert loaded.feature_importances[0].feature_name == "income"


def test_policy_recommendation_persist_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    recommendation = PolicyRecommendation(
        budget_constraint=100.0,
        targeting_rules=[
            TargetingRule(
                rule_id="r1",
                predicate="income < 50k",
                priority=1,
                expected_cate=0.4,
                expected_cost_per_unit=10.0,
                n_eligible_units=5,
                cumulative_budget_share=0.5,
            )
        ],
        total_expected_effect=2.0,
        total_cost=50.0,
        n_targeted_units=5,
        n_total_units=10,
    )
    ref = persist_policy_recommendation(_ensure_ir_artifact_store(store), recommendation)
    loaded = load_policy_recommendation(_ensure_ir_artifact_store(store), ref)
    assert loaded.n_targeted_units == 5
    assert loaded.targeting_rules[0].rule_id == "r1"


def test_hte_result_normalizes_n_samples_consistently() -> None:
    payload = {
        "method": CausalMethod.DOUBLE_ML,
        "ate": 0.2,
        "ate_ci_lower": 0.1,
        "ate_ci_upper": 0.3,
        "cate_values": [0.1, 0.2, 0.4],
    }
    normalized = HTEResult.normalize_payload(payload)
    result = HTEResult.from_estimates(**payload)

    assert "n_samples" not in payload
    assert normalized["n_samples"] == 3
    assert result.n_samples == 3
    assert result.model_copy(deep=True).n_samples == 3
    assert HTEResult.model_validate(result.model_dump(mode="json")).n_samples == 3


def test_hte_result_is_frozen_report_contract() -> None:
    result = HTEResult.from_estimates(
        method=CausalMethod.DOUBLE_ML,
        ate=0.2,
        ate_ci_lower=0.1,
        ate_ci_upper=0.3,
        cate_values=[0.1, 0.2, 0.4],
    )

    with pytest.raises(ValidationError, match="frozen"):
        result.n_samples = 99


def test_policy_recommendation_normalizes_targeting_efficiency_consistently() -> None:
    payload = {
        "total_expected_effect": 6.0,
        "total_cost": 3.0,
        "n_targeted_units": 3,
        "n_total_units": 5,
        "targeting_rules": [
            TargetingRule(
                rule_id="r1",
                predicate="cate > 0",
                priority=1,
                expected_cate=2.0,
                expected_cost_per_unit=1.0,
                n_eligible_units=3,
                cumulative_budget_share=1.0,
            )
        ],
    }
    normalized = PolicyRecommendation.normalize_payload(payload)
    recommendation = PolicyRecommendation.from_totals(**payload)

    assert "targeting_efficiency" not in payload
    assert normalized["targeting_efficiency"] == pytest.approx(2.0)
    assert recommendation.targeting_efficiency == pytest.approx(2.0)
    assert recommendation.model_copy(deep=True).targeting_efficiency == pytest.approx(2.0)
    assert PolicyRecommendation.model_validate(
        recommendation.model_dump(mode="json")
    ).targeting_efficiency == pytest.approx(2.0)


def test_policy_recommendation_is_frozen_report_contract() -> None:
    recommendation = PolicyRecommendation.from_totals(
        total_expected_effect=6.0,
        total_cost=3.0,
        n_targeted_units=3,
        n_total_units=5,
        targeting_rules=[
            TargetingRule(
                rule_id="r1",
                predicate="cate > 0",
                priority=1,
                expected_cate=2.0,
                expected_cost_per_unit=1.0,
                n_eligible_units=3,
                cumulative_budget_share=1.0,
            )
        ],
    )

    with pytest.raises(ValidationError, match="frozen"):
        recommendation.total_cost = 4.0


def test_backtest_report_persist_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    scenario = BacktestScenario(
        scenario_id="s1",
        scenario_label="scenario 1",
        outcome_comparisons=[
            OutcomeComparison(
                metric_name="gdp",
                y_pred=value,
                y_true=value,
                absolute_error=0.0,
                relative_error=0.0,
            )
            for value in (1.0, 2.0, 3.0)
        ],
        rmse=0.0,
        mae=0.0,
        mape=0.0,
        requested_count=3,
        compared_count=3,
        absolute_error_sum=0.0,
        squared_error_sum=0.0,
        percentage_error_sum=0.0,
        percentage_error_count=3,
    )
    orchestrator = BacktestOrchestrator.__new__(BacktestOrchestrator)
    orchestrator._trust_scorer = TrustScorer()
    report = orchestrator._aggregate(
        report_id="BT_test",
        scenarios=[scenario],
        metadata={},
        prediction_mode_requested=None,
        prediction_mode_effective=None,
        degraded_reasons=[],
    )
    report = orchestrator._validate_trust_projection_before_persist(report)
    assert report.metric_diagnostics_are_source_bound()
    assert report.has_source_bound_exact_zero_metrics()
    assert report.trust_eligible
    assert report.trust_score is not None
    assert report.trust_grade is not None

    ref = persist_backtest_report(_ensure_ir_artifact_store(store), report)
    loaded = load_backtest_report(_ensure_ir_artifact_store(store), ref)
    assert loaded.report_id == "BT_test"
    assert loaded.n_scenarios == 1
    assert loaded.metric_diagnostics_are_source_bound()
    assert loaded.has_source_bound_exact_zero_metrics()
    assert loaded.trust_eligible
    assert loaded.trust_score == report.trust_score
    assert loaded.trust_grade == report.trust_grade


def test_unbound_legacy_backtest_grade_is_refused_and_persists_as_limited(tmp_path) -> None:
    store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    report = BacktestReport(
        report_id="BT_legacy_unbound",
        scenarios=[
            BacktestScenario(
                scenario_id="s1",
                scenario_label="scenario 1",
                outcome_comparisons=[
                    OutcomeComparison(
                        metric_name="gdp",
                        y_pred=1.0,
                        y_true=1.2,
                        absolute_error=0.2,
                        relative_error=1.0 / 6.0,
                    )
                ],
                rmse=0.2,
                mae=0.2,
                mape=(1.0 / 6.0) * 100.0,
            )
        ],
        overall_rmse=0.2,
        overall_mae=0.2,
        overall_mape=(1.0 / 6.0) * 100.0,
        n_scenarios=1,
        n_metrics_evaluated=1,
        overall_bias_direction=BiasDirection.NEUTRAL,
        trust_score=0.62,
        trust_grade="C",
    )
    assert report.metric_diagnostics_are_source_bound() is False
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert report.trust_grade is None
    assert "metric_diagnostics_not_source_bound" in report.degraded_reasons

    ref = persist_backtest_report(store, report)
    loaded = load_backtest_report(store, ref)
    assert loaded.metric_diagnostics_are_source_bound() is False
    assert loaded.trust_eligible is False
    assert loaded.trust_score is None
    assert loaded.trust_grade is None
    assert "metric_diagnostics_not_source_bound" in loaded.degraded_reasons


def test_report_loader_requires_native_verification_but_keeps_legacy_metadata(tmp_path) -> None:
    store = _ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    scenario = BacktestScenario(
        scenario_id="s1", scenario_label="legacy", metadata={"native_note": "ordinary label"}
    )
    legacy = BacktestReport(report_id="legacy", scenarios=[scenario])
    legacy_ref = persist_backtest_report(store, legacy)
    assert load_backtest_report(store, legacy_ref).scenarios[0].metadata == scenario.metadata

    candidate = legacy.model_copy(
        update={
            "scenarios": [
                scenario.model_copy(update={"metadata": {"native_forecast_ref": {"id": "x"}}})
            ]
        }
    )
    candidate_ref = persist_backtest_report(store, candidate)
    with pytest.raises(NativeBacktestVerificationRequiredError):
        load_backtest_report(store, candidate_ref)
    assert load_backtest_report_candidate(store, candidate_ref).report_id == "legacy"
