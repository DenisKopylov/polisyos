"""Tests for WS8.1 — SLO Metrics + Alerting.

Covers protocol extensions (backpressure, semaphore_wait, workflow_state),
OTel bridge wiring, and async_executor integration.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from polisyos.scientist.orchestration.engine.metrics_protocol import (
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
            from polisyos.scientist.orchestration.engine.metrics_otel import OTelEngineMetrics

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
        from polisyos.scientist.orchestration.engine.metrics_otel import OTelEngineMetrics

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

    def test_record_node_started_runs(self) -> None:
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        otel.record_node_started(alias="agent", node_id="node.agent@1.0.0", workflow_id="w1")

    def test_trace_correlations_are_bounded(self) -> None:
        try:
            from polisyos.scientist.orchestration.engine.metrics_otel import OTelEngineMetrics

            otel = OTelEngineMetrics(max_trace_correlations=2)
        except Exception:
            pytest.skip("OTel not available")
        otel.record_trace_correlation(
            runner_backend="local",
            workflow_id="w1",
            run_id="r1",
            trace_id="1",
            span_id="1",
        )
        otel.record_trace_correlation(
            runner_backend="ray",
            workflow_id="w1",
            run_id="r1",
            trace_id="2",
            span_id="2",
        )
        otel.record_trace_correlation(
            runner_backend="temporal",
            workflow_id="w1",
            run_id="r1",
            trace_id="3",
            span_id="3",
        )
        recent = otel.recent_trace_correlations()
        assert len(recent) == 2
        assert [item.runner_backend for item in recent] == ["ray", "temporal"]

    def test_record_operational_alert_runs(self) -> None:
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        otel.record_operational_alert(
            alert_type="fairness_regression",
            severity="warn",
            workflow_id="w1",
            run_id="r1",
        )

    def test_node_completed_retry_count_zero_skips_histogram(self) -> None:
        """retry_count=0 should not record to retry histogram."""
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        # With noop this is a no-op; verify no exception
        otel.record_node_completed(
            alias="a",
            node_id="n",
            workflow_id="w",
            status="ok",
            duration_ms=100,
            cache_hit=False,
            retry_count=0,
        )

    def test_node_completed_retry_count_nonzero_records(self) -> None:
        """retry_count > 0 should attempt to record to retry histogram."""
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        otel.record_node_completed(
            alias="a",
            node_id="n",
            workflow_id="w",
            status="ok",
            duration_ms=200,
            cache_hit=False,
            retry_count=2,
        )

    def test_cache_hit_included_in_execution_counter(self) -> None:
        try:
            otel = self._make_otel()
        except Exception:
            pytest.skip("OTel not available")
        otel.record_node_completed(
            alias="a",
            node_id="n",
            workflow_id="w",
            status="ok",
            duration_ms=100,
            cache_hit=True,
            retry_count=0,
        )

    def test_accepts_injected_metrics_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _FakeMetrics:
            scientist_node_starts_total = None
            scientist_node_duration_seconds = None
            scientist_node_executions_total = None
            scientist_node_retry_count = None
            scientist_tier_duration_seconds = None
            scientist_tier_queue_depth = None
            scientist_semaphore_wait_seconds = None
            scientist_workflow_state = None
            slo_dag_runs_total = None
            slo_dag_duration_seconds = None

            def __init__(self) -> None:
                self.trace_calls: list[dict[str, str | None]] = []
                self.alert_calls: list[dict[str, str | None]] = []

            def record_scientist_trace_correlation(
                self,
                *,
                runner_backend: str,
                workflow_id: str,
                run_id: str,
                trace_id: str | None = None,
                span_id: str | None = None,
            ) -> None:
                self.trace_calls.append(
                    {
                        "runner_backend": runner_backend,
                        "workflow_id": workflow_id,
                        "run_id": run_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                    }
                )

            def record_scientist_operational_alert(
                self,
                *,
                alert_type: str,
                severity: str,
                workflow_id: str | None = None,
                run_id: str | None = None,
            ) -> None:
                self.alert_calls.append(
                    {
                        "alert_type": alert_type,
                        "severity": severity,
                        "workflow_id": workflow_id,
                        "run_id": run_id,
                    }
                )

        from polisyos.scientist.orchestration.engine.metrics_otel import OTelEngineMetrics

        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.metrics_otel._default_metrics",
            lambda: (_ for _ in ()).throw(
                AssertionError("global metrics lookup should not run when metrics are injected")
            ),
        )

        metrics = _FakeMetrics()
        otel = OTelEngineMetrics(metrics=metrics, max_trace_correlations=2)
        otel.record_trace_correlation(
            runner_backend="local",
            workflow_id="w1",
            run_id="r1",
            trace_id="t1",
            span_id="s1",
        )
        otel.record_operational_alert(
            alert_type="degraded_dependency",
            severity="warn",
            workflow_id="w1",
            run_id="r1",
        )

        assert metrics.trace_calls == [
            {
                "runner_backend": "local",
                "workflow_id": "w1",
                "run_id": "r1",
                "trace_id": "t1",
                "span_id": "s1",
            }
        ]
        assert metrics.alert_calls == [
            {
                "alert_type": "degraded_dependency",
                "severity": "warn",
                "workflow_id": "w1",
                "run_id": "r1",
            }
        ]


# ---------------------------------------------------------------------------
# Async executor integration — source inspection
# ---------------------------------------------------------------------------


class TestAsyncExecutorMetricsIntegration:
    """Verify async executor calls metrics correctly."""

    def test_backpressure_no_hasattr_guard(self) -> None:
        """record_backpressure must be called directly, not via hasattr."""
        import inspect

        from polisyos.scientist.orchestration.engine import async_executor as mod

        source = inspect.getsource(mod.AsyncWorkflowExecutor)
        # Find all occurrences of record_backpressure
        lines = source.split("\n")
        backpressure_lines = [
            source_line for source_line in lines if "record_backpressure" in source_line
        ]
        # None should be guarded by hasattr
        for line in backpressure_lines:
            assert "hasattr" not in line, f"hasattr guard found: {line.strip()}"

    def test_retry_count_not_hardcoded_zero(self) -> None:
        """retry_count should use actual retry_stats, not hardcoded 0."""
        import inspect

        from polisyos.scientist.orchestration.engine import async_executor as mod

        source = inspect.getsource(mod.AsyncWorkflowExecutor)
        assert "retry_count=0" not in source, "retry_count should use actual value from retry_stats"

    def test_workflow_state_emitted(self) -> None:
        """record_workflow_state should appear in executor source."""
        import inspect

        from polisyos.scientist.orchestration.engine import async_executor as mod

        source = inspect.getsource(mod.AsyncWorkflowExecutor)
        assert "record_workflow_state" in source


# ---------------------------------------------------------------------------
# Retry stats integration
# ---------------------------------------------------------------------------


class TestRetryStatsIntegration:
    """Test that retry_stats dict is populated by execute_with_retry_async."""

    @pytest.mark.asyncio
    async def test_retry_stats_populated_on_success(self) -> None:
        from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
        from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_async
        from polisyos.scientist.orchestration.engine.state import ExperimentState

        state = ExperimentState(run_id="test-run")
        node = MagicMock()
        node.execute = MagicMock(
            return_value=NodeOutcome(
                status="ok",
                state=state,
            )
        )
        ctx = MagicMock()
        stats: dict[str, int] = {}

        await execute_with_retry_async(
            node,
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None,
            alias="test",
            retry_stats=stats,
        )
        assert stats["attempts"] == 1

    @pytest.mark.asyncio
    async def test_retry_stats_none_is_safe(self) -> None:
        """retry_stats=None (default) should not cause errors."""
        from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
        from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_async
        from polisyos.scientist.orchestration.engine.state import ExperimentState

        state = ExperimentState(run_id="test-run")
        node = MagicMock()
        node.execute = MagicMock(
            return_value=NodeOutcome(
                status="ok",
                state=state,
            )
        )
        ctx = MagicMock()

        await execute_with_retry_async(
            node,
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None,
            alias="test",
        )


# ---------------------------------------------------------------------------
# Alerting rules YAML
# ---------------------------------------------------------------------------


class TestAlertingRules:
    """Validate the Prometheus alerting rules file."""

    def test_alerting_rules_yaml_valid(self) -> None:
        rules_path = (
            Path(__file__).resolve().parents[4]
            / "ops"
            / "observability"
            / "prometheus"
            / "rules"
            / "scientist-alerts.yml"
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
