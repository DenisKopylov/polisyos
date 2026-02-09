"""Tests for the MetricsRegistry singleton."""
from __future__ import annotations

import time

from polisyos.core.observability import get_metrics


class TestMetricsRegistry:
    """Tests for the MetricsRegistry singleton."""

    def test_singleton_pattern(self):
        """Metrics registry should be a singleton."""
        metrics1 = get_metrics()
        metrics2 = get_metrics()
        assert metrics1 is metrics2

    def test_histogram_timer(self, test_tracer_provider):
        """Histogram timer should record durations."""
        metrics = get_metrics()

        with metrics.time_simulation({"node": "test"}):
            time.sleep(0.01)

        # Metric was recorded (we can't easily verify the value without a reader)
        # This test mainly verifies no exceptions are raised

    def test_counter_recording(self, test_tracer_provider):
        """Counters should increment without error."""
        metrics = get_metrics()

        metrics.record_workflow_run("success", "EXECUTE", "drafter")
        metrics.record_llm_call("gpt-4", "success", 100, 50)
        metrics.record_validation_issue("blocker", "schema_pass", "type_error")

        # No exceptions = success
