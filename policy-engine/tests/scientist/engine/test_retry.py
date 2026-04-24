"""Tests for polisyos.scientist.engine.retry — RetryPolicy + wrappers."""

from __future__ import annotations

import multiprocessing as mp
import time as _time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polisyos.scientist.engine.errors import NodeTimeoutError, RetryExhaustedError
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.engine.retry import (
    RetryPolicy,
    _backoff_delay,
    _node_execute_worker,
    _should_retry,
    execute_with_retry_async,
    execute_with_retry_sync,
)
from polisyos.scientist.engine.state import ExperimentState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def state():
    return ExperimentState(run_id="test-run")


@pytest.fixture
def ctx():
    c = MagicMock()
    c.run = MagicMock()
    c.run.emit = MagicMock()
    return c


def _ok_outcome(state):
    return NodeOutcome(status="ok", state=state, events=[], artifacts=[])


def _fail_outcome(state, code="node.exception"):
    return NodeOutcome(
        status="fail",
        state=state,
        events=[],
        artifacts=[],
        error=NodeError(code=code, message="fail"),
    )


# ---------------------------------------------------------------------------
# RetryPolicy model
# ---------------------------------------------------------------------------


class TestRetryPolicy:
    def test_defaults(self):
        p = RetryPolicy()
        assert p.max_retries == 0
        assert p.backoff_base_s == 1.0
        assert p.backoff_factor == 2.0
        assert p.retry_on == ["node.exception"]

    def test_max_retries_bounds(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RetryPolicy(max_retries=-1)
        with pytest.raises(ValidationError):
            RetryPolicy(max_retries=6)

    def test_backoff_base_bounds(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RetryPolicy(backoff_base_s=0.01)
        with pytest.raises(ValidationError):
            RetryPolicy(backoff_base_s=61.0)

    def test_extra_field_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RetryPolicy(unknown=True)

    def test_custom_retry_on(self):
        p = RetryPolicy(retry_on=["node.exception", "node.invalid_outcome"])
        assert "node.invalid_outcome" in p.retry_on


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestShouldRetry:
    def test_matching_code(self):
        err = NodeError(code="node.exception", message="boom")
        policy = RetryPolicy(retry_on=["node.exception"])
        assert _should_retry(err, policy) is True

    def test_non_matching_code(self):
        err = NodeError(code="node.invalid_outcome", message="bad")
        policy = RetryPolicy(retry_on=["node.exception"])
        assert _should_retry(err, policy) is False

    def test_none_error(self):
        policy = RetryPolicy()
        assert _should_retry(None, policy) is False


class TestBackoffDelay:
    def test_first_attempt(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="none")
        assert _backoff_delay(0, p) == 1.0

    def test_second_attempt(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="none")
        assert _backoff_delay(1, p) == 2.0

    def test_third_attempt(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="none")
        assert _backoff_delay(2, p) == 4.0

    def test_custom_base(self):
        p = RetryPolicy(backoff_base_s=0.5, backoff_factor=3.0, jitter="none")
        assert _backoff_delay(1, p) == 1.5

    def test_jitter_full(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="full")
        delays = [_backoff_delay(0, p) for _ in range(100)]
        assert all(0 <= d <= 1.0 for d in delays)

    def test_jitter_equal(self):
        p = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, jitter="equal")
        delays = [_backoff_delay(0, p) for _ in range(100)]
        assert all(0.5 <= d <= 1.0 for d in delays)

    def test_jitter_default_is_full(self):
        p = RetryPolicy()
        assert p.jitter == "full"


# ---------------------------------------------------------------------------
# execute_with_retry_sync
# ---------------------------------------------------------------------------


class TestExecuteWithRetrySync:
    def test_fast_path_no_retry_no_timeout(self, ctx, state):
        """With default policy, delegates directly to node.execute()."""
        node = MagicMock()
        node.execute.return_value = _ok_outcome(state)
        result = execute_with_retry_sync(
            node,
            ctx,
            state,
            retry_policy=RetryPolicy(),
            timeout_s=None,
            alias="a",
        )
        assert result.status == "ok"
        node.execute.assert_called_once()

    def test_succeeds_after_retries(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(max_retries=3, backoff_base_s=0.1, backoff_factor=1.0)
        with patch("polisyos.scientist.engine.retry.time.sleep"):
            result = execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )
        assert result.status == "ok"
        assert node.execute.call_count == 3

    def test_exhausts_retries_on_fail_outcome(self, ctx, state):
        node = MagicMock()
        node.execute.return_value = _fail_outcome(state, code="node.exception")
        policy = RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0)
        with patch("polisyos.scientist.engine.retry.time.sleep"):
            result = execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )
        # Returns last fail outcome (not raises) because the loop exits with the outcome
        assert result.status == "fail"
        assert node.execute.call_count == 3  # 1 + 2 retries

    def test_exception_retry_then_exhausted(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = RuntimeError("boom")
        policy = RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0)
        with (
            patch("polisyos.scientist.engine.retry.time.sleep"),
            pytest.raises(RetryExhaustedError),
        ):
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )
        assert node.execute.call_count == 3

    def test_retry_on_filter(self, ctx, state):
        """Node fails with code not in retry_on → no retry."""
        node = MagicMock()
        node.execute.return_value = _fail_outcome(state, code="node.invalid_outcome")
        policy = RetryPolicy(max_retries=2, retry_on=["node.exception"])
        result = execute_with_retry_sync(
            node,
            ctx,
            state,
            retry_policy=policy,
            timeout_s=None,
            alias="a",
        )
        assert result.status == "fail"
        assert node.execute.call_count == 1  # No retry

    def test_backoff_timing(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(
            max_retries=3,
            backoff_base_s=1.0,
            backoff_factor=2.0,
            jitter="none",
        )
        with patch("polisyos.scientist.engine.retry.time.sleep") as mock_sleep:
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )
        assert mock_sleep.call_count == 2
        # First backoff: 1.0 * 2^0 = 1.0
        assert mock_sleep.call_args_list[0][0][0] == pytest.approx(1.0)
        # Second backoff: 1.0 * 2^1 = 2.0
        assert mock_sleep.call_args_list[1][0][0] == pytest.approx(2.0)

    def test_timeout_raises(self, ctx, state):
        import time as _time

        node = MagicMock()
        node.execute.side_effect = lambda *a, **kw: (_time.sleep(5), _ok_outcome(state))[1]
        with pytest.raises(NodeTimeoutError):
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.1,
                alias="a",
            )

    def test_timeout_path_uses_shared_executor(self, ctx, state, monkeypatch):
        class _FakeFuture:
            def __init__(self, outcome):
                self._outcome = outcome
                self.cancelled = False

            def result(self, timeout=None):
                _ = timeout
                return self._outcome

            def cancel(self) -> None:
                self.cancelled = True

        class _FakeExecutor:
            def __init__(self) -> None:
                self.submissions: list[tuple[object, tuple[object, ...]]] = []

            def submit(self, fn, *args):
                self.submissions.append((fn, args))
                return _FakeFuture(fn(*args))

        node = MagicMock()
        node.execute.return_value = _ok_outcome(state)
        fake_executor = _FakeExecutor()

        monkeypatch.setattr(
            "polisyos.scientist.engine.retry._can_use_forked_timeout_worker",
            lambda: False,
        )
        monkeypatch.setattr(
            "polisyos.scientist.engine.retry.get_shared_executor",
            lambda: fake_executor,
        )

        result = execute_with_retry_sync(
            node,
            ctx,
            state,
            retry_policy=RetryPolicy(),
            timeout_s=0.5,
            alias="a",
        )

        assert result.status == "ok"
        assert len(fake_executor.submissions) == 1
        submitted_fn, submitted_args = fake_executor.submissions[0]
        assert submitted_fn == node.execute
        assert submitted_args == (ctx, state)

    def test_default_policy_zero_retries_no_retry(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=None,
                alias="a",
            )
        assert node.execute.call_count == 1

    def test_node_retry_events_emitted(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0)
        with patch("polisyos.scientist.engine.retry.time.sleep"):
            execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="step_a",
            )
        # Check NODE_RETRY event was emitted
        retry_calls = [c for c in ctx.run.emit.call_args_list if c[0][1] == "NODE_RETRY"]
        assert len(retry_calls) == 1
        assert retry_calls[0][1]["metrics"]["attempt"] == 1


# ---------------------------------------------------------------------------
# execute_with_retry_async
# ---------------------------------------------------------------------------


class TestExecuteWithRetryAsync:
    @pytest.mark.asyncio
    async def test_fast_path(self, ctx, state):
        node = MagicMock()
        node.execute.return_value = _ok_outcome(state)
        result = await execute_with_retry_async(
            node,
            ctx,
            state,
            retry_policy=RetryPolicy(),
            timeout_s=None,
            alias="a",
        )
        assert result.status == "ok"

    @pytest.mark.asyncio
    async def test_sync_execution_uses_shared_executor_bridge(self, ctx, state):
        node = MagicMock()
        node.execute.return_value = _ok_outcome(state)

        async def _bridge(func, *args, **kwargs):
            return func(*args, **kwargs)

        with patch(
            "polisyos.scientist.engine.retry.run_blocking_async",
            new=AsyncMock(side_effect=_bridge),
        ) as bridge:
            result = await execute_with_retry_async(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=None,
                alias="a",
            )

        assert result.status == "ok"
        bridge.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_timeout_raises(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = lambda *a, **kw: (_time.sleep(5), _ok_outcome(state))[1]
        with pytest.raises(NodeTimeoutError):
            await execute_with_retry_async(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.1,
                alias="a",
            )

    @pytest.mark.asyncio
    @pytest.mark.skipif("fork" not in mp.get_all_start_methods(), reason="fork worker required")
    async def test_timeout_does_not_leave_child_process(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = lambda *a, **kw: (_time.sleep(5), _ok_outcome(state))[1]

        with pytest.raises(NodeTimeoutError):
            await execute_with_retry_async(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.1,
                alias="a",
            )

        assert [child for child in mp.active_children() if child.name.startswith("Process-")] == []

    @pytest.mark.asyncio
    async def test_retry_succeeds(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(max_retries=2, backoff_base_s=0.1, backoff_factor=1.0)
        result = await execute_with_retry_async(
            node,
            ctx,
            state,
            retry_policy=policy,
            timeout_s=None,
            alias="a",
        )
        assert result.status == "ok"
        assert node.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_exception_retry_exhausted(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = RuntimeError("boom")
        policy = RetryPolicy(max_retries=1, backoff_base_s=0.1, backoff_factor=1.0)
        with pytest.raises(RetryExhaustedError):
            await execute_with_retry_async(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="a",
            )


class TestRetryTimeoutWorker:
    def test_timeout_worker_does_not_swallow_system_exit(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = SystemExit("stop-now")
        result_queue = MagicMock()

        with pytest.raises(SystemExit, match="stop-now"):
            _node_execute_worker(node, ctx, state, result_queue)

        result_queue.put.assert_not_called()
