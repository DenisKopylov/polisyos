"""OpenTelemetry-backed engine metrics collector.

Bridges :class:`EngineMetricsCollector` to the existing global
:class:`MetricsRegistry` singleton from ``polisyos.core.observability``.
"""
from __future__ import annotations


class OTelEngineMetrics:
    """Records engine metrics via the PolicyOS MetricsRegistry singleton."""

    def __init__(self) -> None:
        from polisyos.core.observability import get_metrics

        self._m = get_metrics()

    def record_node_started(
        self, *, alias: str, node_id: str, workflow_id: str,
    ) -> None:
        # Node start is a lightweight event — no counter needed beyond the
        # existing NODE_STARTED run-context emission.  Kept for protocol
        # completeness; could be wired to a counter later.
        pass

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

    def record_tier_completed(
        self, *, tier_index: int, tier_size: int, duration_ms: int, workflow_id: str,
    ) -> None:
        if self._m.scientist_tier_duration_seconds is not None:
            self._m.scientist_tier_duration_seconds.record(
                duration_ms / 1000.0,
                {"tier_index": str(tier_index), "tier_size": str(tier_size), "workflow_id": workflow_id},
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
