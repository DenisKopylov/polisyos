"""Tests for the circuit breaker module."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from polisyos.scientist.engine.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from polisyos.scientist.engine.errors import CircuitBreakerOpenError
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.engine.retry import (
    RetryPolicy,
    execute_with_retry_async,
    execute_with_retry_sync,
)
from polisyos.scientist.engine.state import ExperimentState


@pytest.fixture
def state():
    return ExperimentState(run_id="cb-test")


# ── Config validation ────────────────────────────────────────────────

class TestCircuitBreakerConfig:
    def test_defaults(self) -> None:
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.recovery_timeout_s == 30.0
        assert cfg.half_open_max_calls == 1

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            CircuitBreakerConfig(unknown_field=1)  # type: ignore[call-arg]

    def test_bounds(self) -> None:
        with pytest.raises(ValidationError):
            CircuitBreakerConfig(failure_threshold=0)
        with pytest.raises(ValidationError):
            CircuitBreakerConfig(recovery_timeout_s=0.5)


# ── State machine ────────────────────────────────────────────────────

class TestCircuitBreakerStateMachine:
    def test_initial_state_closed(self) -> None:
        cb = CircuitBreaker()
        assert cb.state == "closed"

    def test_allow_request_when_closed(self) -> None:
        cb = CircuitBreaker()
        assert cb.allow_request() is True

    def test_closed_to_open_after_threshold(self) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker(cfg)

        for _ in range(2):
            cb.record_failure()
            assert cb.state == "closed"

        cb.record_failure()
        assert cb.state == "open"

    def test_open_rejects_requests(self) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker(cfg)
        cb.record_failure()

        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_open_to_half_open_after_recovery(self) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_s=1.0)
        cb = CircuitBreaker(cfg)
        cb.record_failure()
        assert cb.state == "open"

        # Simulate time passing beyond recovery_timeout
        cb._last_failure_time = time.monotonic() - 2.0
        assert cb.state == "half_open"

    def test_half_open_allows_limited_calls(self) -> None:
        cfg = CircuitBreakerConfig(
            failure_threshold=1, recovery_timeout_s=1.0, half_open_max_calls=2,
        )
        cb = CircuitBreaker(cfg)
        cb.record_failure()

        # Simulate recovery timeout
        cb._last_failure_time = time.monotonic() - 2.0

        assert cb.allow_request() is True
        assert cb.allow_request() is True
        assert cb.allow_request() is False

    def test_half_open_success_closes(self) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_s=1.0)
        cb = CircuitBreaker(cfg)
        cb.record_failure()

        cb._last_failure_time = time.monotonic() - 2.0
        assert cb.state == "half_open"

        cb.record_success()
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_half_open_failure_reopens(self) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_s=1.0)
        cb = CircuitBreaker(cfg)
        cb.record_failure()

        cb._last_failure_time = time.monotonic() - 2.0
        assert cb.state == "half_open"

        cb.record_failure()
        assert cb.state == "open"

    def test_success_resets_failure_count(self) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker(cfg)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"

    def test_reset(self) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker(cfg)
        cb.record_failure()
        assert cb.state == "open"

        cb.reset()
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_name(self) -> None:
        cb = CircuitBreaker(name="test_node")
        assert cb.name == "test_node"


# ── Thread safety ────────────────────────────────────────────────────

class TestCircuitBreakerThreadSafety:
    def test_concurrent_failures(self) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=50)
        cb = CircuitBreaker(cfg)
        barrier = threading.Barrier(10)

        def fail_many() -> None:
            barrier.wait()
            for _ in range(10):
                cb.record_failure()

        threads = [threading.Thread(target=fail_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert cb.failure_count == 100
        assert cb.state == "open"


# ── Integration with retry ───────────────────────────────────────────

def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.run.emit = MagicMock()
    ctx.store.put_json = MagicMock(return_value=MagicMock())
    return ctx


class TestCircuitBreakerRetryIntegration:
    def test_sync_cb_open_raises(self, state) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker(cfg)
        cb.record_failure()

        node = MagicMock()
        ctx = _make_ctx()

        with pytest.raises(CircuitBreakerOpenError):
            execute_with_retry_sync(
                node, ctx, state,
                retry_policy=RetryPolicy(max_retries=0),
                timeout_s=None, alias="test",
                circuit_breaker=cb,
            )

    def test_sync_cb_records_success(self, state) -> None:
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
        cb.record_failure()

        node = MagicMock()
        node.execute.return_value = NodeOutcome(status="ok", state=state)
        ctx = _make_ctx()

        execute_with_retry_sync(
            node, ctx, state,
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None, alias="test",
            circuit_breaker=cb,
        )
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_async_cb_open_raises(self, state) -> None:
        cfg = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker(cfg)
        cb.record_failure()

        node = MagicMock()
        ctx = _make_ctx()

        with pytest.raises(CircuitBreakerOpenError):
            await execute_with_retry_async(
                node, ctx, state,
                retry_policy=RetryPolicy(max_retries=0),
                timeout_s=None, alias="test",
                circuit_breaker=cb,
            )

    @pytest.mark.asyncio
    async def test_async_cancelled_error_propagates(self, state) -> None:
        node = MagicMock()
        node.execute.side_effect = asyncio.CancelledError()
        ctx = _make_ctx()

        with pytest.raises(asyncio.CancelledError):
            await execute_with_retry_async(
                node, ctx, state,
                retry_policy=RetryPolicy(max_retries=3),
                timeout_s=None, alias="test",
            )

        # Should not have retried
        assert node.execute.call_count == 1

    def test_sync_dead_letter_on_exhaustion(self, state) -> None:
        node = MagicMock()
        node.execute.side_effect = RuntimeError("boom")
        node.spec.metadata.component_id = "test.node@1.0.0"
        ctx = _make_ctx()

        policy = RetryPolicy(max_retries=1, backoff_base_s=0.1, backoff_factor=1.0)
        with patch("polisyos.scientist.engine.retry.time.sleep"):
            with pytest.raises(Exception):  # noqa: B017
                execute_with_retry_sync(
                    node, ctx, state,
                    retry_policy=policy,
                    timeout_s=None, alias="dlq_test",
                )

        # Dead-letter artifact should have been persisted
        ctx.store.put_json.assert_called()
        call_args = ctx.store.put_json.call_args
        payload = call_args[0][0]
        assert payload["kind"] == "scientist.dead_letter"
        assert payload["alias"] == "dlq_test"
        assert payload["error_type"] == "RuntimeError"

    def test_dead_letter_store_failure_swallowed(self, state) -> None:
        node = MagicMock()
        node.execute.side_effect = RuntimeError("boom")
        node.spec.metadata.component_id = "test.node@1.0.0"
        ctx = _make_ctx()
        ctx.store.put_json.side_effect = OSError("disk full")

        policy = RetryPolicy(max_retries=1, backoff_base_s=0.1, backoff_factor=1.0)
        with patch("polisyos.scientist.engine.retry.time.sleep"):
            with pytest.raises(Exception):  # noqa: B017
                execute_with_retry_sync(
                    node, ctx, state,
                    retry_policy=policy,
                    timeout_s=None, alias="test",
                )
        # Should not crash — DLQ is best-effort
