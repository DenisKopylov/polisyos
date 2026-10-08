"""Exercise interval admission through evaluation, backtest persistence and fresh readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.ir_adapter import build_ir_artifact_store
from polisyos.ir.analytics.backtest import BacktestReport, BacktestScenario, load_backtest_report
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.scientist.methods.backtesting.evaluator import PredictionEvaluator
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource


def _evaluate(interval: Any) -> BacktestScenario:
    return PredictionEvaluator().evaluate(
        scenario_id="interval-admission",
        scenario_label="synthetic paired interval",
        y_pred={"metric": [0.0, 0.0, 0.0]},
        y_true={"metric": [0.0, 0.0, 0.0]},
        intervals={"metric": [interval, interval, interval]},
    )


@pytest.mark.parametrize(
    ("interval", "reason"),
    [
        ((2.0, -2.0), "reversed_interval"),
        ((-2.0, 2.0, 999.0), "invalid_interval_shape"),
        ((-2.0,), "invalid_interval_shape"),
        (3.0, "invalid_interval_shape"),
        ("12", "invalid_interval_shape"),
        ({0: -2.0, 1: 2.0}, "invalid_interval_shape"),
        ((False, 2.0), "non_numeric_interval"),
        (("-2", "2"), "non_numeric_interval"),
        ((float("nan"), 2.0), "non_finite_interval"),
        ((-2.0, float("inf")), "non_finite_interval"),
    ],
)
def test_invalid_interval_preserves_point_comparisons_and_requested_denominator(
    interval: Any, reason: str
) -> None:
    scenario = _evaluate(interval)
    assert scenario.requested_count == scenario.compared_count == 3
    assert scenario.missing_count == scenario.invalid_count == 0
    assert scenario.rmse == scenario.mae == 0.0
    assert scenario.interval_requested_count == 3
    assert scenario.interval_available_count == scenario.interval_evaluated_count == 0
    assert scenario.coverage_probability is None
    assert scenario.interval_availability == 0.0
    assert all(item.within_ci is None for item in scenario.outcome_comparisons)
    assert all(item.ci_lower is item.ci_upper is None for item in scenario.outcome_comparisons)
    admission = scenario.metadata["interval_admission"]
    assert admission["status"] == "limited"
    assert admission["basis"] == "recomputed"
    assert [item["time_index"] for item in admission["limitations"]] == [0, 1, 2]
    assert {item["reason"] for item in admission["limitations"]} == {reason}


@pytest.mark.parametrize("interval", [(-2.0, 2.0), [0.0, 0.0]])
def test_ordered_finite_interval_and_equal_endpoint_are_supported(interval: Any) -> None:
    scenario = _evaluate(interval)
    assert scenario.interval_requested_count == scenario.interval_evaluated_count == 3
    assert scenario.interval_hit_count == 3
    assert scenario.coverage_probability == 1.0
    assert scenario.metadata["interval_admission"]["status"] == "evaluated"
    assert scenario.metadata["interval_admission"]["limitations"] == []


def _run_report(
    tmp_path: Path,
    *,
    interval: tuple[float, float],
    truths: list[float] | None = None,
) -> tuple[BacktestReport, BacktestReport]:
    truths = [0.0, 0.0, 0.0] if truths is None else truths
    history_path = tmp_path / "history.json"
    history_path.write_text('{"metric": [0, 0, 0]}', encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="paired-interval",
        plan_label="synthetic paired interval",
        historical_data_path=str(history_path),
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": [0.0, 0.0, 0.0]},
        prediction_intervals={"metric": [interval, interval, interval]},
        ground_truth_outcomes={"metric": truths},
    )
    cas_root = tmp_path / "cas"
    report = BacktestOrchestrator(cas_root=str(cas_root)).run([plan])
    assert report.cas_artifact_id is not None
    ref = BacktestReportRef(
        artifact_id=report.cas_artifact_id,
        kind="ir.backtest_report",
        media_type="application/json",
    )
    fresh = load_backtest_report(build_ir_artifact_store(cas_root), ref)
    return report, fresh


@pytest.mark.parametrize("interval", [(2.0, -2.0), (float("nan"), 2.0), (-2.0, float("inf"))])
def test_actual_backtest_keeps_unavailable_intervals_non_gating_after_cas_readback(
    tmp_path: Path, interval: tuple[float, float]
) -> None:
    report, fresh = _run_report(tmp_path, interval=interval)
    for result in (report, fresh):
        assert result.n_metrics_evaluated == 3
        assert result.overall_rmse == 0.0
        assert result.overall_coverage_probability is None
        assert result.scenarios[0].interval_requested_count == 3
        assert result.scenarios[0].interval_evaluated_count == 0
        assert result.scenarios[0].metadata["interval_admission"]["status"] == "limited"
        assert result.degraded is True
        assert any("interval_admission_limited" in reason for reason in result.degraded_reasons)
        assert result.trust_eligible is False
        assert result.trust_score is result.trust_grade is None


def test_same_intervals_changed_observations_change_actual_persisted_coverage(
    tmp_path: Path,
) -> None:
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()
    _, good = _run_report(inside, interval=(-2.0, 2.0), truths=[-2.0, 0.0, 2.0])
    _, bad = _run_report(outside, interval=(-2.0, 2.0), truths=[-3.0, 0.0, 3.0])
    assert (
        good.scenarios[0].interval_requested_count == bad.scenarios[0].interval_requested_count == 3
    )
    assert (
        good.scenarios[0].interval_evaluated_count == bad.scenarios[0].interval_evaluated_count == 3
    )
    assert good.scenarios[0].interval_hit_count == 3
    assert bad.scenarios[0].interval_hit_count == 1
    assert good.overall_coverage_probability == 1.0
    assert bad.overall_coverage_probability == pytest.approx(1 / 3)
    assert good.scenarios[0].nominal_confidence_level == bad.scenarios[0].nominal_confidence_level


def test_partial_interval_roster_retains_attempted_cells_and_marks_conditional_coverage() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="partial",
        scenario_label="partial",
        y_pred={"metric": [0.0, 0.0, 0.0]},
        y_true={"metric": [0.0, 0.0, 0.0]},
        intervals={"metric": [(-2.0, 2.0)]},
    )
    assert scenario.compared_count == scenario.requested_count == 3
    assert scenario.interval_requested_count == 3
    assert scenario.interval_evaluated_count == 1
    assert scenario.interval_availability == pytest.approx(1 / 3)
    assert scenario.coverage_probability == 1.0
    admission = scenario.metadata["interval_admission"]
    assert admission["coverage_scope"] == "evaluated_pairs_only"
    assert admission["status"] == "limited"
    assert [item["time_index"] for item in admission["limitations"]] == [1, 2]


def test_unknown_interval_axes_cannot_claim_complete_admission() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="foreign-axes",
        scenario_label="foreign-axes",
        y_pred={"metric": [0.0]},
        y_true={"metric": [0.0]},
        intervals={"metric": [(-2.0, 2.0), (-2.0, 2.0)], "foreign": [(-2.0, 2.0)]},
    )
    assert scenario.requested_count == scenario.compared_count == 1
    assert scenario.interval_requested_count == scenario.interval_evaluated_count == 1
    assert scenario.coverage_probability == 1.0
    admission = scenario.metadata["interval_admission"]
    assert admission["status"] == "limited"
    assert {item["reason"] for item in admission["limitations"]} == {
        "unknown_metric",
        "unexpected_interval_time_index",
    }


def test_point_failures_preserve_interval_attempted_roster() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="missing-points",
        scenario_label="missing-points",
        y_pred={"metric": [0.0, float("nan")]},
        y_true={"metric": [0.0, 0.0, 0.0]},
        intervals={"metric": [(-2.0, 2.0)] * 3},
    )
    assert scenario.requested_count == 3
    assert scenario.compared_count == scenario.missing_count == scenario.invalid_count == 1
    assert scenario.interval_requested_count == 3
    assert scenario.interval_evaluated_count == 1
    admission = scenario.metadata["interval_admission"]
    assert admission["requested_count"] == 3
    assert admission["evaluated_count"] == 1
    assert admission["status"] == "limited"
    assert [item["time_index"] for item in admission["limitations"]] == [1, 2]


def test_caller_interval_admission_metadata_cannot_override_computed_limitation() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="metadata-fake",
        scenario_label="metadata-fake",
        y_pred={"metric": [0.0]},
        y_true={"metric": [0.0]},
        intervals={"metric": [(2.0, -2.0)]},
        metadata={"interval_admission": {"status": "evaluated", "basis": "recomputed"}},
    )
    assert scenario.coverage_probability is None
    assert scenario.metadata["interval_admission"]["status"] == "limited"
    assert (
        scenario.metadata["interval_admission"]["limitations"][0]["reason"] == "reversed_interval"
    )


def test_point_only_evaluation_does_not_invent_an_interval_limitation() -> None:
    scenario = PredictionEvaluator().evaluate(
        scenario_id="point-only",
        scenario_label="point-only",
        y_pred={"metric": [0.0, 0.0, 0.0]},
        y_true={"metric": [0.0, 0.0, 0.0]},
    )
    assert scenario.compared_count == 3
    assert scenario.interval_requested_count == 0
    assert "interval_admission" not in scenario.metadata
