from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource


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
        plans=[_plan(tmp_path, kind).model_dump(mode="json")],
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


def test_backtest_matrix_rejects_unknown_payload_before_any_execution(tmp_path, cas_store) -> None:
    unreadable_path = tmp_path / "must_not_be_read.json"
    valid_bundle = BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id="macro_bundle",
            contract_fqn="polisyos.tests.BacktestPlanBundle",
        ),
        required_fields=["metric"],
        plans=[
            {
                "plan_id": "valid_but_unreadable",
                "historical_data_path": str(unreadable_path),
                "ground_truth_outcomes": {"metric": [1.0]},
                "target_metrics": ["metric"],
            }
        ],
    )
    unknown_bundle = BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id="cell_bundle",
            contract_fqn="polisyos.tests.BacktestPlanBundle",
        ),
        required_fields=["metric"],
        plans=[
            {
                "plan_id": "unknown_prediction_source",
                "historical_data_path": str(tmp_path / "unused.json"),
                "ground_truth_outcomes": {"metric": [1.0]},
                "target_metrics": ["metric"],
                "prediction_source": "self_attested_oracle",
            }
        ],
    )

    with pytest.raises(ValidationError, match="prediction_source"):
        BacktestMatrixRunner(cas_store).run(
            {
                BacktestKind.MACRO: valid_bundle,
                BacktestKind.CELL: unknown_bundle,
            }
        )
