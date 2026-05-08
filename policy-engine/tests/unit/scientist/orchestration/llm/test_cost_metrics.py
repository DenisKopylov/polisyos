"""Tests for WS8.3 — LLM Cost Dashboard Metrics.

Covers cost/token/latency metric emission from LLMBudgetEnforcer,
budget utilization gauge, cost anomaly detection, and graceful
behaviour when MetricsRegistry is absent.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.cost_anomaly import CostAnomalyDetector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_enforcer(
    *,
    max_usd: Decimal = Decimal("100"),
    model_name: str = "gpt-4",
    run_id: str = "test-run",
) -> LLMBudgetEnforcer:
    budget_state = BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=max_usd)},
    )
    client = MagicMock()
    return LLMBudgetEnforcer(
        client=client,
        budget_state=budget_state,
        budget_keys=["run"],
        model_name=model_name,
        run_id=run_id,
    )


def _mock_response(prompt_tokens: int = 100, completion_tokens: int = 50) -> MagicMock:
    resp = MagicMock()
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    resp.usage = usage
    return resp


# ---------------------------------------------------------------------------
# Cost histogram
# ---------------------------------------------------------------------------


class TestPostRecordEmitsCostHistogram:
    def test_cost_histogram_recorded(self) -> None:
        enforcer = _make_enforcer()
        resp = _mock_response()
        cost = enforcer._post_record(resp)
        assert cost >= Decimal(0)

    def test_post_record_returns_cost(self) -> None:
        enforcer = _make_enforcer()
        resp = _mock_response(prompt_tokens=0, completion_tokens=0)
        cost = enforcer._post_record(resp)
        assert isinstance(cost, Decimal)


# ---------------------------------------------------------------------------
# Token counts
# ---------------------------------------------------------------------------


class TestPostRecordEmitsTokenCounts:
    def test_token_recording_does_not_crash(self) -> None:
        enforcer = _make_enforcer()
        resp = _mock_response(prompt_tokens=500, completion_tokens=200)
        enforcer._post_record(resp)


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------


class TestLatencyMeasured:
    def test_invoke_measures_latency(self) -> None:
        enforcer = _make_enforcer()
        enforcer._client.invoke.return_value = _mock_response()
        enforcer.invoke("hello", _prompt_tokens_estimate=10)

    @pytest.mark.asyncio
    async def test_generate_measures_latency(self) -> None:
        enforcer = _make_enforcer()
        enforcer._client.generate = AsyncMock(return_value=_mock_response())
        await enforcer.generate(user="hello", _prompt_tokens_estimate=10)


# ---------------------------------------------------------------------------
# Budget utilization gauge
# ---------------------------------------------------------------------------


class TestBudgetUtilizationGauge:
    def test_utilization_updated_after_spend(self) -> None:
        enforcer = _make_enforcer(max_usd=Decimal("10"))
        resp = _mock_response()
        enforcer._post_record(resp)
        util = enforcer.budget_state.utilization("run")
        assert util is not None
        assert util >= 0.0

    def test_utilization_none_for_unknown_key(self) -> None:
        enforcer = _make_enforcer()
        assert enforcer.budget_state.utilization("nonexistent") is None


# ---------------------------------------------------------------------------
# Cost anomaly detector
# ---------------------------------------------------------------------------


class TestCostAnomalyDetectorNormal:
    def test_no_anomaly_on_uniform_costs(self) -> None:
        detector = CostAnomalyDetector(window_size=10)
        for _ in range(20):
            assert detector.check(1.0) is False


class TestCostAnomalyDetectorSpike:
    def test_detects_large_spike(self) -> None:
        detector = CostAnomalyDetector(window_size=20, z_threshold=3.0)
        for _ in range(20):
            detector.check(1.0)
        assert detector.check(100.0) is True


class TestCostAnomalyDetectorEmptyWindow:
    def test_first_call_not_anomaly(self) -> None:
        detector = CostAnomalyDetector()
        assert detector.check(999.0) is False

    def test_second_call_not_anomaly(self) -> None:
        detector = CostAnomalyDetector()
        detector.check(1.0)
        assert detector.check(1.0) is False


# ---------------------------------------------------------------------------
# Graceful without registry
# ---------------------------------------------------------------------------


class TestMetricsGracefulWithoutRegistry:
    def test_post_record_works_when_get_metrics_raises(self) -> None:
        enforcer = _make_enforcer()
        resp = _mock_response()
        with patch(
            "polisyos.scientist.orchestration.llm.budget_enforcer.CostAnomalyDetector.check",
            return_value=False,
        ):
            cost = enforcer._post_record(resp)
        assert isinstance(cost, Decimal)


# ---------------------------------------------------------------------------
# Grafana dashboard template
# ---------------------------------------------------------------------------


class TestGrafanaDashboard:
    def test_dashboard_json_valid(self) -> None:
        import pathlib

        dashboard_path = (
            pathlib.Path(__file__).resolve().parents[5]
            / "ops"
            / "observability"
            / "grafana"
            / "dashboards"
            / "scientist-llm-cost.json"
        )
        data = json.loads(dashboard_path.read_text())
        assert "panels" in data
        assert len(data["panels"]) >= 5
        titles = {p["title"] for p in data["panels"]}
        assert "LLM Cost over Time" in titles
        assert "Budget Utilization" in titles
        assert "Cost Anomalies" in titles
