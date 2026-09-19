"""Tests for polisyos.scientist.orchestration.engine.retry — RetryPolicy + wrappers."""

from __future__ import annotations

import asyncio
import concurrent.futures
import multiprocessing as mp
import threading
import time as _time
from contextvars import ContextVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import polisyos.scientist.orchestration.engine.retry as retry_module
from polisyos.core.contracts import BoundedLivenessConfig
from polisyos.scientist.orchestration.engine.errors import NodeTimeoutError, RetryExhaustedError
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.orchestration.engine.retry import (
    RetryPolicy,
    _backoff_delay,
    _node_execute_worker,
    _should_retry,
    execute_with_retry_async,
    execute_with_retry_sync,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

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
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
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
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
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
            patch("polisyos.scientist.orchestration.engine.retry.time.sleep"),
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
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep") as mock_sleep:
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
            "polisyos.scientist.orchestration.engine.retry._can_use_forked_timeout_worker",
            lambda: False,
        )
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry.get_shared_executor",
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
        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
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

    def test_bounded_liveness_config_clamps_retry_ceiling(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = [
            _fail_outcome(state, code="node.exception"),
            _fail_outcome(state, code="node.exception"),
            _ok_outcome(state),
        ]
        policy = RetryPolicy(max_retries=3, backoff_base_s=0.1, backoff_factor=1.0)
        liveness_config = BoundedLivenessConfig(
            config_id="bounded-liveness.test.v1",
            owner="team-runtime-quality",
            version="2026-05-22",
            default_deadline_s=30.0,
            default_retry_ceiling=3,
            producer_retry_ceiling_overrides={"scientist.node.step_a": 1},
            feature_flag="universal_pdc_bounded_liveness",
            rollback_path="restore previous governed config artifact",
            promotion_evidence_ref="artifact://bounded-liveness/evidence",
        )

        with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
            result = execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="step_a",
                liveness_config=liveness_config,
            )

        assert result.status == "fail"
        assert node.execute.call_count == 2

    def test_timeout_thread_fallback_preserves_context_for_each_request(
        self, ctx, state, monkeypatch
    ):
        owner_scope: ContextVar[str | None] = ContextVar("owner_scope", default=None)
        observed: list[str | None] = []

        class _ContextNode:
            def execute(self, _ctx, _state):
                observed.append(owner_scope.get())
                return _ok_outcome(state)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry._can_use_forked_timeout_worker",
            lambda: False,
        )
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry.get_shared_executor",
            lambda: executor,
        )

        try:
            token = owner_scope.set("request-A")
            try:
                direct = execute_with_retry_sync(
                    _ContextNode(),
                    ctx,
                    state,
                    retry_policy=RetryPolicy(),
                    timeout_s=None,
                    alias="a",
                )
            finally:
                owner_scope.reset(token)

            async def _async_entry() -> NodeOutcome:
                token = owner_scope.set("request-B")
                try:
                    return await execute_with_retry_async(
                        _ContextNode(),
                        ctx,
                        state,
                        retry_policy=RetryPolicy(),
                        timeout_s=None,
                        alias="b",
                    )
                finally:
                    owner_scope.reset(token)

            async_result = asyncio.run(_async_entry())

            for request_id in ("request-C", "request-D"):
                token = owner_scope.set(request_id)
                try:
                    threaded = execute_with_retry_sync(
                        _ContextNode(),
                        ctx,
                        state,
                        retry_policy=RetryPolicy(),
                        timeout_s=0.5,
                        alias=request_id,
                    )
                finally:
                    owner_scope.reset(token)
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

        assert direct.status == "ok"
        assert async_result.status == "ok"
        assert threaded.status == "ok"
        assert observed == ["request-A", "request-B", "request-C", "request-D"]
        assert owner_scope.get() is None

    def test_timeout_wait_cancel_does_not_commit_late_state_write(self, ctx, state, monkeypatch):
        started = threading.Event()
        release = threading.Event()
        completed = threading.Event()

        class _LateWriteNode:
            def execute(self, _ctx, passed_state):
                started.set()
                release.wait(timeout=1.0)
                passed_state.params["late_write"] = "unauthorised"
                completed.set()
                return _ok_outcome(passed_state)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry._can_use_forked_timeout_worker",
            lambda: False,
        )
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry.get_shared_executor",
            lambda: executor,
        )

        try:
            with pytest.raises(NodeTimeoutError):
                execute_with_retry_sync(
                    _LateWriteNode(),
                    ctx,
                    state,
                    retry_policy=RetryPolicy(),
                    timeout_s=0.01,
                    alias="late-write",
                )
            assert started.wait(timeout=0.5)
            release.set()
            assert completed.wait(timeout=0.5)
        finally:
            release.set()
            executor.shutdown(wait=True, cancel_futures=True)

        assert "late_write" not in state.params

    def test_one_effective_deadline_passes_remaining_budget_to_each_retry(
        self, ctx, state, monkeypatch
    ):
        config = BoundedLivenessConfig(
            default_deadline_s=0.1,
            default_retry_ceiling=1,
            producer_deadline_overrides_s={"scientist.node.a": 0.1},
        )
        observed: list[float | None] = []

        class _Clock:
            value = 100.0

            def __call__(self) -> float:
                return self.value

        clock = _Clock()

        def _capture(_node, _ctx, _state, *, timeout_s):
            observed.append(timeout_s)
            if len(observed) == 1:
                clock.value += 0.06
                return _fail_outcome(state)
            return _ok_outcome(state)

        monkeypatch.setattr(retry_module, "_execute_with_timeout_sync", _capture)
        monkeypatch.setattr(retry_module.time, "monotonic", clock)
        monkeypatch.setattr(retry_module.time, "sleep", lambda _seconds: None)

        result = execute_with_retry_sync(
            MagicMock(),
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=1, jitter="none"),
            timeout_s=None,
            alias="a",
            liveness_config=config,
        )

        assert result.status == "ok"
        assert observed == [pytest.approx(0.1), pytest.approx(0.04)]


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
            "polisyos.scientist.orchestration.engine.retry.run_blocking_async",
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

    @pytest.mark.asyncio
    async def test_async_entry_uses_one_effective_deadline_when_timeout_is_omitted(
        self, ctx, state, monkeypatch
    ):
        config = BoundedLivenessConfig(default_deadline_s=0.1, default_retry_ceiling=0)
        observed: list[float | None] = []

        async def _bridge(_func, *_args, **kwargs):
            observed.append(kwargs.get("timeout_seconds"))
            return _ok_outcome(state)

        monkeypatch.setattr(retry_module, "run_blocking_async", _bridge)
        result = await execute_with_retry_async(
            MagicMock(),
            ctx,
            state,
            retry_policy=RetryPolicy(),
            timeout_s=None,
            alias="a",
            liveness_config=config,
        )

        assert result.status == "ok"
        assert observed == [pytest.approx(0.1)]


class TestRetryTimeoutWorker:
    def test_timeout_worker_does_not_swallow_system_exit(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = SystemExit("stop-now")
        result_queue = MagicMock()

        with pytest.raises(SystemExit, match="stop-now"):
            _node_execute_worker(node, ctx, state, result_queue)

        result_queue.put.assert_not_called()


class _OutputAwareTransportNode:
    def __init__(self, outcome, worker_pid_path):
        self.outcome = outcome
        self.worker_pid_path = worker_pid_path

    def execute(self, ctx, state):
        import os

        self.worker_pid_path.write_text(str(os.getpid()))
        return self.outcome


@pytest.mark.skipif(
    "fork" not in mp.get_all_start_methods(), reason="actual fork worker unavailable"
)
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_output_aware_fork_retry_preserves_complete_outcome(tmp_path, ctx, mode) -> None:
    import asyncio
    import os

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.scientist.orchestration.engine import OutputAwareNodeOutcome
    from tests.unit.scientist.orchestration.engine.runner.test_serialization import (
        _output_aware_transport_outcome,
    )

    outcome = _output_aware_transport_outcome(FileSystemCAS(tmp_path / "cas"))
    worker_pid_path = tmp_path / "actual-worker-pid"
    node = _OutputAwareTransportNode(outcome, worker_pid_path)
    kwargs = {"retry_policy": RetryPolicy(), "timeout_s": 10.0, "alias": "output-aware-wire"}
    if mode == "sync":
        restored = execute_with_retry_sync(node, ctx, outcome.state, **kwargs)
    else:
        restored = asyncio.run(execute_with_retry_async(node, ctx, outcome.state, **kwargs))
    assert int(worker_pid_path.read_text()) != os.getpid()
    assert type(restored) is OutputAwareNodeOutcome
    assert restored.model_dump(mode="json") == outcome.model_dump(mode="json")
