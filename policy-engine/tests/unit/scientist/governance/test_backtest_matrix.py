from __future__ import annotations

import json

from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner


def _plan(tmp_path, kind: BacktestKind) -> HistoricalValidationPlan:
    path = tmp_path / f"{kind.value}_historical.json"
    path.write_text(json.dumps({"metric": [1.0, 1.05, 1.1, 1.15]}), encoding="utf-8")
    return HistoricalValidationPlan(
        plan_id=f"{kind.value}_plan",
        plan_label=f"{kind.value} synthetic",
        historical_data_path=str(path),
        intervention_step=2,
        ground_truth_outcomes={"metric": [1.1, 1.15]},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [1.08, 1.13]},
    )


def _bundle(tmp_path, kind: BacktestKind) -> BacktestPlanBundle:
    return BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id=f"{kind.value}_bundle",
            contract_fqn="polisyos.tests.BacktestPlanBundle",
        ),
        required_fields=["metric"],
        holdout_windows=["2024-Q4"],
        plans=[_plan(tmp_path, kind)],
        historical_payloads={kind.value: {"metric": [1.0, 1.05, 1.1, 1.15]}},
    )


def test_backtest_matrix_runner_runs_all_five_backtests(tmp_path, cas_store) -> None:
    runner = BacktestMatrixRunner(cas_store)
    result = runner.run({kind: _bundle(tmp_path, kind) for kind in BacktestKind})

    assert len(result.kind_results) == 5
    assert result.backtest_report_ref is not None
    assert result.composite_score is not None
    assert 0.0 <= result.composite_score <= 1.0
    assert all(item.status == "ok" for item in result.kind_results)
    assert all(item.score is not None and 0.0 <= item.score <= 1.0 for item in result.kind_results)

    report = load_backtest_report(cas_store, result.backtest_report_ref)
    assert report.n_scenarios == 5
    assert report.trust_eligible is True
    assert report.degraded is False
    assert all("backtest_kind" in scenario.metadata for scenario in report.scenarios)
    assert all(":" in scenario.scenario_id for scenario in report.scenarios)


def test_backtest_matrix_runner_marks_missing_bundles_as_explicit_gaps(tmp_path, cas_store) -> None:
    runner = BacktestMatrixRunner(cas_store)
    result = runner.run({BacktestKind.MACRO: _bundle(tmp_path, BacktestKind.MACRO)})

    gaps = {item.kind: item for item in result.kind_results if item.status == "gap"}
    assert BacktestKind.CELL in gaps
    assert gaps[BacktestKind.CELL].gap_flag == "missing_backtest_bundle:cell"
    assert result.backtest_report_ref is not None

    report = load_backtest_report(cas_store, result.backtest_report_ref)
    assert report.n_scenarios == 1
    assert report.trust_eligible is True
