from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.backtest import (
    BacktestReport,
    BacktestScenario,
    BiasDirection,
    OutcomeComparison,
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.causal import CausalMethod
from polisyos.ir.hte import (
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
    ref = persist_hte_result(store, result)
    loaded = load_hte_result(store, ref)
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
    ref = persist_policy_recommendation(store, recommendation)
    loaded = load_policy_recommendation(store, ref)
    assert loaded.n_targeted_units == 5
    assert loaded.targeting_rules[0].rule_id == "r1"


def test_backtest_report_persist_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report = BacktestReport(
        report_id="BT_test",
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
                        relative_error=0.1667,
                    )
                ],
                rmse=0.2,
                mae=0.2,
                mape=16.67,
                coverage_probability=0.5,
            )
        ],
        overall_rmse=0.2,
        overall_mae=0.2,
        overall_mape=16.67,
        overall_coverage_probability=0.5,
        n_scenarios=1,
        n_metrics_evaluated=1,
        overall_bias_direction=BiasDirection.NEUTRAL,
        trust_score=0.62,
        trust_grade="C",
    )
    ref = persist_backtest_report(store, report)
    loaded = load_backtest_report(store, ref)
    assert loaded.report_id == "BT_test"
    assert loaded.n_scenarios == 1
    assert loaded.trust_grade == "C"
