"""Behavioral regression tests for the BKT-03 honest bias/statistics contract."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
from polisyos.ir.analytics.backtest import BacktestReport, BiasDirection
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import (
    HistoricalValidationPlan,
    PredictionSource,
)


def _run_provided_report(
    tmp_path: Path,
    *,
    predictions: list[float],
    truths: list[float],
) -> BacktestReport:
    """Run one complete provided-prediction backtest for a regression fixture."""
    history_path = tmp_path / "history.json"
    history_path.write_text('{"metric": [0.0, 0.0, 0.0]}', encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="bkt-03-regression",
        historical_data_path=str(history_path),
        ground_truth_outcomes={"metric": truths},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": predictions},
    )
    return BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos")).run([plan])


def test_constant_nonzero_residual_keeps_descriptive_bias_without_significance(
    tmp_path: Path,
) -> None:
    """A constant residual must remain visible when variance blocks a test."""
    report = _run_provided_report(
        tmp_path,
        predictions=[10.0, 10.0, 10.0],
        truths=[0.0, 0.0, 0.0],
    )

    assert report.overall_mae == pytest.approx(10.0)
    assert report.detected_biases
    bias = report.detected_biases[0]
    assert bias.affected_metrics == ["metric"]
    assert bias.magnitude == pytest.approx(10.0)
    assert bias.p_value is None
    assert bias.statistical_test != "one-sample t-test H0(mean_error=0)"
    assert bias.metadata["test_status"] == "not_computable"
    assert bias.metadata["test_reason"] == "zero_variance"
    assert report.overall_bias_direction is not BiasDirection.NEUTRAL
    assert report.degraded is True
    assert report.degraded_reasons
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert report.trust_grade is None


def test_small_nonzero_residual_keeps_descriptive_bias_and_degrades_trust(
    tmp_path: Path,
) -> None:
    """A nonzero small sample is descriptive, not evidence of no bias."""
    report = _run_provided_report(
        tmp_path,
        predictions=[0.5, 1.5],
        truths=[0.0, 0.0],
    )

    assert report.overall_mae == pytest.approx(1.0)
    assert report.detected_biases
    bias = report.detected_biases[0]
    assert bias.affected_metrics == ["metric"]
    assert bias.magnitude == pytest.approx(1.0)
    assert bias.p_value is None
    assert bias.metadata["test_status"] == "not_computable"
    assert bias.metadata["test_reason"] == "insufficient_observations"
    assert any("insufficient_observations" in reason for reason in report.degraded_reasons)
    assert report.degraded is True
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert report.trust_grade is None


def test_zero_residual_is_a_separate_no_bias_control(tmp_path: Path) -> None:
    """A truly zero residual remains distinct from an untestable bias."""
    report = _run_provided_report(
        tmp_path,
        predictions=[0.0, 0.0, 0.0],
        truths=[0.0, 0.0, 0.0],
    )

    assert report.overall_mae == pytest.approx(0.0)
    assert report.detected_biases == []
    assert report.overall_bias_direction is BiasDirection.NEUTRAL


def test_small_sample_ttest_matches_scipy_reference() -> None:
    """The small-n reference is Student's t, not a normal approximation."""
    scipy_stats = pytest.importorskip("scipy.stats")
    errors = np.asarray([0.5, 1.5, 2.5], dtype=float)

    expected = float(scipy_stats.ttest_1samp(errors, popmean=0.0).pvalue)
    observed = BacktestOrchestrator._two_sided_ttest_pvalue(errors)

    assert observed == pytest.approx(expected, rel=1e-10, abs=1e-10)
    assert observed == pytest.approx(0.121690, abs=1e-6)


def test_scipy_unavailability_preserves_metrics_and_withholds_trust(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """An unavailable test backend is explicit and cannot produce positive trust."""

    def _unavailable(_module_name: str) -> object:
        raise ModuleNotFoundError("simulated scipy.stats unavailability")

    monkeypatch.setattr(orchestrator_module, "import_module", _unavailable)
    report = _run_provided_report(
        tmp_path,
        predictions=[0.5, 1.5, 2.5],
        truths=[0.0, 0.0, 0.0],
    )

    scenario = report.scenarios[0]
    assert scenario.compared_count == 3
    assert scenario.mae == pytest.approx(1.5)
    assert report.overall_mae == pytest.approx(1.5)
    assert report.degraded is True
    assert report.degraded_reasons
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert report.trust_grade is None
    assert report.detected_biases
    bias = report.detected_biases[0]
    assert bias.magnitude == pytest.approx(1.5)
    assert bias.p_value is None
    assert "t-test" not in bias.statistical_test.lower()
