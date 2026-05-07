"""Engine metrics protocol — abstraction for node/workflow telemetry.

Defines :class:`EngineMetricsCollector` (a ``runtime_checkable`` protocol) and
a no-op implementation for cases where metrics collection is disabled.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EngineMetricsCollector(Protocol):
    """Interface for recording Scientist engine execution metrics."""

    def record_node_started(
        self,
        *,
        alias: str,
        node_id: str,
        workflow_id: str,
    ) -> None: ...  # pragma: no cover

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
    ) -> None: ...  # pragma: no cover

    def record_tier_completed(
        self,
        *,
        tier_index: int,
        tier_size: int,
        duration_ms: int,
        workflow_id: str,
    ) -> None: ...  # pragma: no cover

    def record_workflow_completed(
        self,
        *,
        workflow_id: str,
        status: str,
        duration_ms: int,
        node_count: int,
    ) -> None: ...  # pragma: no cover

    def record_backpressure(
        self,
        *,
        tier_index: int,
        queued_tasks: int,
        active_tasks: int,
        workflow_id: str,
    ) -> None: ...  # pragma: no cover

    def record_semaphore_wait(
        self,
        *,
        tier_index: int,
        wait_seconds: float,
        workflow_id: str,
    ) -> None: ...  # pragma: no cover

    def record_workflow_state(
        self,
        *,
        run_id: str,
        workflow_id: str,
        state: str,
    ) -> None: ...  # pragma: no cover

    def record_trace_correlation(
        self,
        *,
        runner_backend: str,
        workflow_id: str,
        run_id: str,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None: ...  # pragma: no cover

    def record_operational_alert(
        self,
        *,
        alert_type: str,
        severity: str,
        workflow_id: str | None = None,
        run_id: str | None = None,
    ) -> None: ...  # pragma: no cover


class NoopEngineMetrics:
    """No-op implementation for cases when metrics are disabled."""

    def record_node_started(self, **kw: object) -> None:
        pass

    def record_node_completed(self, **kw: object) -> None:
        pass

    def record_tier_completed(self, **kw: object) -> None:
        pass

    def record_workflow_completed(self, **kw: object) -> None:
        pass

    def record_backpressure(self, **kw: object) -> None:
        pass

    def record_semaphore_wait(self, **kw: object) -> None:
        pass

    def record_workflow_state(self, **kw: object) -> None:
        pass

    def record_trace_correlation(self, **kw: object) -> None:
        pass

    def record_operational_alert(self, **kw: object) -> None:
        pass
