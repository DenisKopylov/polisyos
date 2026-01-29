"""Tests for log-trace correlation utilities."""
from __future__ import annotations

import logging

from polisyos.core.observability import get_tracer
from polisyos.core.observability.logs import TraceContextFilter, get_trace_context_dict


class TestLogCorrelation:
    """Tests for log-trace correlation."""

    def test_trace_context_in_logs(self, test_tracer_provider, caplog):
        """Logs should include trace context."""
        # Setup logger with trace filter
        logger = logging.getLogger("test.correlation")
        logger.addFilter(TraceContextFilter())
        logger.setLevel(logging.INFO)

        tracer = get_tracer()

        with tracer.start_as_current_span("log_test"):
            with caplog.at_level(logging.INFO):
                logger.info("Test message")

            # Check that trace_id was added to log record
            records = [r for r in caplog.records if r.message == "Test message"]
            assert len(records) == 1

            record = records[0]
            assert hasattr(record, "trace_id")
            assert record.trace_id is not None
            assert len(record.trace_id) == 32

    def test_get_trace_context_dict(self, test_tracer_provider):
        """get_trace_context_dict should return current context."""
        tracer = get_tracer()

        # No active span
        ctx = get_trace_context_dict()
        assert ctx["trace_id"] is None

        # With active span
        with tracer.start_as_current_span("test"):
            ctx = get_trace_context_dict()
            assert ctx["trace_id"] is not None
            assert ctx["span_id"] is not None
