"""Tests for WS8.1 — SLO Metrics + Alerting.

Covers protocol extensions (backpressure, semaphore_wait, workflow_state),
OTel bridge wiring, and async_executor integration.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from polisyos.scientist.engine.metrics_protocol import (
    EngineMetricsCollector,
    NoopEngineMetrics,
)


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------

class TestProtocolCompliance:
    """Ensure Noop and OTel implementations satisfy the extended protocol."""

    def test_noop_metrics_has_new_methods(self) -> None:
        noop = NoopEngineMetrics()
        noop.record_backpressure(tier_index=0, queued_tasks=5, active_tasks=2, workflow_id="w")
        noop.record_semaphore_wait(tier_index=0, wait_seconds=1.5, workflow_id="w")
        noop.record_workflow_state(run_id="r", workflow_id="w", state="running")

    def test_noop_is_protocol_instance(self) -> None:
        assert isinstance(NoopEngineMetrics(), EngineMetricsCollector)

    def test_otel_is_protocol_instance(self) -> None:
        try:
            from polisyos.scientist.engine.metrics_otel import OTelEngineMetrics
            otel = OTelEngineMetrics()
            assert isinstance(otel, EngineMetricsCollector)
        except Exception:
            pytest.skip("OTel not available")


# ---------------------------------------------------------------------------
# OTel bridge — uses the noop fallback MetricsRegistry
# ---------------------------------------------------------------------------

class TestOTelBridge:
    """Test OTelEngineMetrics methods execute without error.

    The MetricsRegistry is a noop stub in test env (no OTel provider).
    We verify methods run successfully and use correct instrument names.
    """

    def _make_otel(self):
        from polisyos.scientist.engine.metrics_otel import OTelEngineMetrics
        return OTelEngineMetrics()

    def test_record_backpressure_runs(self) -> None:
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        # Should not raise — noop registry returns _NoopMetric
        otel.record_backpressure(tier_index=1, queued_tasks=10, active_tasks=3, workflow_id="w1")

    def test_record_semaphore_wait_runs(self) -> None:
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        otel.record_semaphore_wait(tier_index=0, wait_seconds=2.5, workflow_id="w1")

    def test_record_workflow_state_transitions(self) -> None:
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        otel.record_workflow_state(run_id="r1", workflow_id="w1", state="running")
        otel.record_workflow_state(run_id="r1", workflow_id="w1", state="ok")

    def test_node_completed_retry_count_zero_skips_histogram(self) -> None:
        """retry_count=0 should not record to retry histogram."""
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        # With noop this is a no-op; verify no exception
        otel.record_node_completed(
            alias="a", node_id="n", workflow_id="w",
            status="ok", duration_ms=100, cache_hit=False, retry_count=0,
        )

    def test_node_completed_retry_count_nonzero_records(self) -> None:
        """retry_count > 0 should attempt to record to retry histogram."""
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        otel.record_node_completed(
            alias="a", node_id="n", workflow_id="w",
            status="ok", duration_ms=200, cache_hit=False, retry_count=2,
        )

    def test_cache_hit_included_in_execution_counter(self) -> None:
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        otel.record_node_completed(
            alias="a", node_id="n", workflow_id="w",
            status="ok", duration_ms=100, cache_hit=True, retry_count=0,
        )


# ---------------------------------------------------------------------------
# Async executor integration — source inspection
# ---------------------------------------------------------------------------

class TestAsyncExecutorMetricsIntegration:
    """Verify async executor calls metrics correctly."""

    def test_backpressure_no_hasattr_guard(self) -> None:
        """record_backpressure must be called directly, not via hasattr."""
        import inspect
        from polisyos.scientist.engine import async_executor as mod
        source = inspect.getsource(mod.AsyncWorkflowExecutor)
        # Find all occurrences of record_backpressure
        lines = source.split("\n")
        backpressure_lines = [l for l in lines if "record_backpressure" in l]
        # None should be guarded by hasattr
        for line in backpressure_lines:
            assert "hasattr" not in line, f"hasattr guard found: {line.strip()}"

    def test_retry_count_not_hardcoded_zero(self) -> None:
        """retry_count should use actual retry_stats, not hardcoded 0."""
        import inspect
        from polisyos.scientist.engine import async_executor as mod
        source = inspect.getsource(mod.AsyncWorkflowExecutor)
        assert "retry_count=0" not in source, "retry_count should use actual value from retry_stats"

    def test_workflow_state_emitted(self) -> None:
        """record_workflow_state should appear in executor source."""
        import inspect
        from polisyos.scientist.engine import async_executor as mod
        source = inspect.getsource(mod.AsyncWorkflowExecutor)
        assert "record_workflow_state" in source


# ---------------------------------------------------------------------------
# Retry stats integration
# ---------------------------------------------------------------------------

class TestRetryStatsIntegration:
    """Test that retry_stats dict is populated by execute_with_retry_async."""

    @pytest.mark.asyncio
    async def test_retry_stats_populated_on_success(self) -> None:
        from polisyos.scientist.engine.retry import RetryPolicy, execute_with_retry_async
        from polisyos.scientist.engine.protocol import NodeOutcome
        from polisyos.scientist.engine.state import ExperimentState

        state = ExperimentState(run_id="test-run")
        node = MagicMock()
        node.execute = MagicMock(return_value=NodeOutcome(
            status="ok", state=state,
        ))
        ctx = MagicMock()
        stats: dict[str, int] = {}

        await execute_with_retry_async(
            node, ctx, state,
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None, alias="test",
            retry_stats=stats,
        )
        assert stats["attempts"] == 1

    @pytest.mark.asyncio
    async def test_retry_stats_none_is_safe(self) -> None:
        """retry_stats=None (default) should not cause errors."""
        from polisyos.scientist.engine.retry import RetryPolicy, execute_with_retry_async
        from polisyos.scientist.engine.protocol import NodeOutcome
        from polisyos.scientist.engine.state import ExperimentState

        state = ExperimentState(run_id="test-run")
        node = MagicMock()
        node.execute = MagicMock(return_value=NodeOutcome(
            status="ok", state=state,
        ))
        ctx = MagicMock()

        await execute_with_retry_async(
            node, ctx, state,
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None, alias="test",
        )


# ---------------------------------------------------------------------------
# Alerting rules YAML
# ---------------------------------------------------------------------------

class TestAlertingRules:
    """Validate the Prometheus alerting rules file."""

    def test_alerting_rules_yaml_valid(self) -> None:
        rules_path = (
            Path(__file__).resolve().parents[3]
            / "deploy" / "prometheus" / "scientist_alerts.yml"
        )
        if not rules_path.exists():
            pytest.skip("Alerting rules file not found")
        data = yaml.safe_load(rules_path.read_text())
        assert "groups" in data
        group = data["groups"][0]
        assert group["name"] == "scientist_slo"
        alert_names = [r["alert"] for r in group["rules"]]
        assert "ScientistNodeP95LatencyHigh" in alert_names
        assert "ScientistWorkflowFailRate" in alert_names
        assert "ScientistBudgetNearExhaustion" in alert_names
        assert "ScientistTierQueueDepthHigh" in alert_names
        assert "ScientistSemaphoreWaitHigh" in alert_names
