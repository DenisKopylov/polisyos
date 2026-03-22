"""Tests for polisyos.scientist.engine.metrics_protocol — protocol & noop."""
from __future__ import annotations

import pytest

from polisyos.scientist.engine.metrics_protocol import (
    EngineMetricsCollector,
    NoopEngineMetrics,
)


# ---------------------------------------------------------------------------
# NoopEngineMetrics
# ---------------------------------------------------------------------------

class TestNoopEngineMetrics:
    def test_implements_protocol(self):
        noop = NoopEngineMetrics()
        assert isinstance(noop, EngineMetricsCollector)

    def test_record_node_started(self):
        noop = NoopEngineMetrics()
        noop.record_node_started(alias="a", node_id="n", workflow_id="w")

    def test_record_node_completed(self):
        noop = NoopEngineMetrics()
        noop.record_node_completed(
            alias="a", node_id="n", workflow_id="w",
            status="ok", duration_ms=10, cache_hit=False, retry_count=0,
        )

    def test_record_tier_completed(self):
        noop = NoopEngineMetrics()
        noop.record_tier_completed(
            tier_index=0, tier_size=2, duration_ms=50, workflow_id="w",
        )

    def test_record_workflow_completed(self):
        noop = NoopEngineMetrics()
        noop.record_workflow_completed(
            workflow_id="w", status="ok", duration_ms=100, node_count=3,
        )


# ---------------------------------------------------------------------------
# EngineMetricsCollector protocol (runtime checkable)
# ---------------------------------------------------------------------------

class _CustomCollector:
    """A custom implementation to verify protocol structural check."""

    def __init__(self):
        self.calls: list[str] = []

    def record_node_started(self, *, alias, node_id, workflow_id):
        self.calls.append("node_started")

    def record_node_completed(
        self, *, alias, node_id, workflow_id, status, duration_ms, cache_hit, retry_count,
    ):
        self.calls.append("node_completed")

    def record_tier_completed(self, *, tier_index, tier_size, duration_ms, workflow_id):
        self.calls.append("tier_completed")

    def record_workflow_completed(self, *, workflow_id, status, duration_ms, node_count):
        self.calls.append("workflow_completed")


class TestProtocolStructuralCheck:
    def test_custom_collector_is_protocol_instance(self):
        c = _CustomCollector()
        assert isinstance(c, EngineMetricsCollector)

    def test_custom_collector_calls(self):
        c = _CustomCollector()
        c.record_node_started(alias="a", node_id="n", workflow_id="w")
        c.record_node_completed(
            alias="a", node_id="n", workflow_id="w",
            status="ok", duration_ms=10, cache_hit=False, retry_count=0,
        )
        c.record_tier_completed(
            tier_index=0, tier_size=1, duration_ms=5, workflow_id="w",
        )
        c.record_workflow_completed(
            workflow_id="w", status="ok", duration_ms=50, node_count=2,
        )
        assert c.calls == [
            "node_started", "node_completed", "tier_completed", "workflow_completed",
        ]


class _IncompleteCollector:
    """Missing record_workflow_completed — should NOT satisfy protocol."""

    def record_node_started(self, *, alias, node_id, workflow_id):
        pass

    def record_node_completed(
        self, *, alias, node_id, workflow_id, status, duration_ms, cache_hit, retry_count,
    ):
        pass

    def record_tier_completed(self, *, tier_index, tier_size, duration_ms, workflow_id):
        pass


class TestIncompleteCollector:
    def test_missing_method_fails_protocol(self):
        ic = _IncompleteCollector()
        assert not isinstance(ic, EngineMetricsCollector)
