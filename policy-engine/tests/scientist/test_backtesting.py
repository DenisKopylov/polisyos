from __future__ import annotations

import json

from polisyos.ir.analytics.backtest import BacktestScenario
from polisyos.scientist.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.backtesting.trust_scorer import TrustScorer


def test_backtesting_orchestrator_naive_mode(tmp_path) -> None:
    history = {
        "tax_revenue": [10.0, 11.0, 12.0, 12.5, 13.0],
    }
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    plan = HistoricalValidationPlan(
        plan_id="bt_1",
        plan_label="naive backtest",
        historical_data_path=str(history_path),
        intervention_step=3,
        target_metrics=["tax_revenue"],
        ground_truth_outcomes={"tax_revenue": [13.2, 13.4]},
        prediction_source=PredictionSource.NAIVE,
    )

    orchestrator = BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos"))
    report = orchestrator.run([plan])
    assert report.n_scenarios == 1
    assert report.cas_artifact_id is not None
    assert report.scenarios[0].scenario_id == "bt_1"


def test_trust_scorer_coverage_gate_caps_grade() -> None:
    scorer = TrustScorer()
    scenarios = [
        BacktestScenario(
            scenario_id="s1",
            scenario_label="scenario",
            rmse=0.1,
            mae=0.1,
            mape=2.0,
            coverage_probability=0.4,
        )
    ]
    score, grade = scorer.compute(scenarios=scenarios, biases=[])
    assert score is not None
    assert grade in {"C", "D", "F"}
