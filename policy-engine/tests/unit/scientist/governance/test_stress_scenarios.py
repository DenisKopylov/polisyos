from __future__ import annotations

from polisyos.scientist.governance.stress_scenarios import (
    StressScenarioKind,
    StressScenarioRunner,
    load_stress_test_report,
)


def test_stress_scenario_runner_executes_all_six_scenarios(cas_store) -> None:
    runner = StressScenarioRunner(cas_store)
    result = runner.run(baseline_metrics={"policy_value": 100.0, "coverage": 0.9})

    assert len(result.comparisons) == 6
    assert result.stress_test_report_ref is not None
    assert result.robustness_score is not None
    assert all(item.scenario in StressScenarioKind for item in result.comparisons)
    assert all(item.baseline_objective == 100.0 for item in result.comparisons)

    report = load_stress_test_report(cas_store, result.stress_test_report_ref)
    assert report.total_scenarios_evaluated == 6
    assert report.worst_case_objective is not None


def test_stress_scenario_runner_escalates_severity_by_threshold(cas_store) -> None:
    runner = StressScenarioRunner(cas_store)
    result = runner.run(
        baseline_metrics={"policy_value": 100.0},
        scenario_objective_overrides={
            StressScenarioKind.BUDGET_CONTRACTION: 70.0,
            StressScenarioKind.PROCUREMENT_SHOCK: 84.0,
            StressScenarioKind.WAGE_SUBSIDY: 94.0,
            StressScenarioKind.FX: 98.0,
            StressScenarioKind.TRADE_DISRUPTION: 100.0,
            StressScenarioKind.REIMBURSEMENT_TARIFF: 100.0,
        },
    )

    severity_by_kind = {item.scenario: item.severity for item in result.comparisons}
    assert severity_by_kind[StressScenarioKind.BUDGET_CONTRACTION] == "critical"
    assert severity_by_kind[StressScenarioKind.PROCUREMENT_SHOCK] == "high"
    assert severity_by_kind[StressScenarioKind.WAGE_SUBSIDY] == "medium"
    assert result.critical_count == 1
    assert result.high_count == 1
    assert result.medium_count == 1
