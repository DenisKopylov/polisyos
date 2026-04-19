"""OpenTelemetry-backed engine metrics collector.

Bridges :class:`EngineMetricsCollector` to the existing global
:class:`MetricsRegistry` singleton from ``polisyos.core.observability``.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from polisyos.core.observability import MetricsRegistry, get_metrics


@dataclass(frozen=True, slots=True)
class TraceCorrelationRecord:
    """Bounded trace-correlation breadcrumb retained for runtime inspection."""

    runner_backend: str
    workflow_id: str
    run_id: str
    trace_id: str | None = None
    span_id: str | None = None


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


class OTelEngineMetrics:
    """Records engine metrics via the PolicyOS MetricsRegistry singleton."""

    def __init__(
        self,
        *,
        metrics: MetricsRegistry | None = None,
        max_trace_correlations: int = 256,
    ) -> None:
        self._m = metrics if metrics is not None else _default_metrics()
        self._recent_trace_correlations: deque[TraceCorrelationRecord] = deque(
            maxlen=max(1, int(max_trace_correlations)),
        )

    def record_node_started(
        self, *, alias: str, node_id: str, workflow_id: str,
    ) -> None:
        if self._m.scientist_node_starts_total is not None:
            self._m.scientist_node_starts_total.add(
                1,
                {
                    "alias": alias,
                    "node_id": node_id,
                    "workflow_id": workflow_id,
                },
            )

    def record_node_completed(
        self,
        *,
        alias: str,
        node_id: str,
        workflow_id: str,
        status: str,
        duration_ms: int,
        cache_hit: bool,
        retry_count: int,
    ) -> None:
        attrs = {
            "node_id": node_id,
            "status": status,
            "workflow_id": workflow_id,
        }
        if self._m.scientist_node_duration_seconds is not None:
            self._m.scientist_node_duration_seconds.record(
                duration_ms / 1000.0, attrs,
            )
        if self._m.scientist_node_executions_total is not None:
            self._m.scientist_node_executions_total.add(
                1,
                {
                    "node_id": node_id,
                    "status": status,
                    "cache_hit": str(cache_hit).lower(),
                },
            )
        if retry_count > 0 and self._m.scientist_node_retry_count is not None:
            self._m.scientist_node_retry_count.record(
                retry_count, {"node_id": node_id},
            )

    def record_tier_completed(
        self, *, tier_index: int, tier_size: int, duration_ms: int, workflow_id: str,
    ) -> None:
        if self._m.scientist_tier_duration_seconds is not None:
            self._m.scientist_tier_duration_seconds.record(
                duration_ms / 1000.0,
                {
                    "tier_index": str(tier_index),
                    "tier_size": str(tier_size),
                    "workflow_id": workflow_id,
                },
            )

    def record_workflow_completed(
        self, *, workflow_id: str, status: str, duration_ms: int, node_count: int,
    ) -> None:
        # Leverage existing slo_dag_runs_total + slo_dag_duration_seconds
        if self._m.slo_dag_runs_total is not None:
            self._m.slo_dag_runs_total.add(1, {"workflow_id": workflow_id, "status": status})
        if self._m.slo_dag_duration_seconds is not None:
            self._m.slo_dag_duration_seconds.record(
                duration_ms / 1000.0,
                {"workflow_id": workflow_id, "status": status},
            )

    def record_backpressure(
        self, *, tier_index: int, queued_tasks: int, active_tasks: int, workflow_id: str,
    ) -> None:
        if self._m.scientist_tier_queue_depth is not None:
            self._m.scientist_tier_queue_depth.set(
                queued_tasks,
                {"tier_index": str(tier_index), "workflow_id": workflow_id},
            )

    def record_semaphore_wait(
        self, *, tier_index: int, wait_seconds: float, workflow_id: str,
    ) -> None:
        if self._m.scientist_semaphore_wait_seconds is not None:
            self._m.scientist_semaphore_wait_seconds.record(
                wait_seconds,
                {"tier_index": str(tier_index), "workflow_id": workflow_id},
            )

    def record_workflow_state(
        self, *, run_id: str, workflow_id: str, state: str,
    ) -> None:
        if self._m.scientist_workflow_state is not None:
            self._m.scientist_workflow_state.add(
                1, {"run_id": run_id, "workflow_id": workflow_id, "state": state},
            )

    def record_trace_correlation(
        self,
        *,
        runner_backend: str,
        workflow_id: str,
        run_id: str,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        self._recent_trace_correlations.append(
            TraceCorrelationRecord(
                runner_backend=runner_backend,
                workflow_id=workflow_id,
                run_id=run_id,
                trace_id=trace_id,
                span_id=span_id,
            )
        )
        self._m.record_scientist_trace_correlation(
            runner_backend=runner_backend,
            workflow_id=workflow_id,
            run_id=run_id,
            trace_id=trace_id,
            span_id=span_id,
        )

    def record_operational_alert(
        self,
        *,
        alert_type: str,
        severity: str,
        workflow_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self._m.record_scientist_operational_alert(
            alert_type=alert_type,
            severity=severity,
            workflow_id=workflow_id,
            run_id=run_id,
        )

    def recent_trace_correlations(self) -> list[TraceCorrelationRecord]:
        """Return a bounded snapshot of recent runner trace correlations."""
        return list(self._recent_trace_correlations)
