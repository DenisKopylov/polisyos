"""Tests for polisyos.scientist.orchestration.engine.retry — RetryPolicy + wrappers."""

from __future__ import annotations

import asyncio
import concurrent.futures
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import threading
import time as _time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import BoundedLivenessConfig
from polisyos.core.errors import ErrorCategory
from polisyos.core.run.context import RunContext
from polisyos.core.run.manifest import RunManifest
from polisyos.scientist.orchestration.engine import retry as retry_module
from polisyos.scientist.orchestration.engine.context import ClaimCapableExecutionContext
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


class _TransientTransportValueError(ValueError):
    default_category = ErrorCategory.TRANSIENT
    code = "node.transport"


class _ValidationTransportError(RuntimeError):
    default_category = ErrorCategory.VALIDATION


class _CodedTransportError(RuntimeError):
    code = "node.action"


class _ErrorTransportNode:
    """Record real compute attempts outside the forked object's memory."""

    def __init__(self, attempts_path, error=None, *, return_failure=False, recover=True) -> None:
        self.attempts_path = attempts_path
        self.error = error
        self.return_failure = return_failure
        self.recover = recover

    def execute(self, _ctx, state):
        with self.attempts_path.open("a") as attempts:
            attempts.write("attempt\n")
        if self.return_failure:
            return _fail_outcome(state, code="node.invalid_state")
        if not self.recover or len(self.attempts_path.read_text().splitlines()) == 1:
            raise self.error
        return _ok_outcome(state)


class _AsyncErrorTransportNode(_ErrorTransportNode):
    async def execute_async(self, ctx, state):
        await asyncio.sleep(0)
        return self.execute(ctx, state)


@pytest.mark.parametrize("route", ["direct", "thread", "async-thread", "fork", "async"])
def test_provider_timeout_error_is_retryable_across_execution_routes(
    tmp_path, ctx, state, route, monkeypatch
):
    if route == "fork" and "fork" not in mp.get_all_start_methods():
        pytest.skip("fork unavailable")
    if route in {"thread", "async-thread"}:
        monkeypatch.setattr(retry_module, "_can_use_forked_timeout_worker", lambda: False)
    attempts_path = tmp_path / "attempts"
    node_type = _AsyncErrorTransportNode if route == "async" else _ErrorTransportNode
    node = node_type(attempts_path, TimeoutError("provider request exceeded its own deadline"))
    kwargs = {
        "retry_policy": RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
        "timeout_s": None if route == "direct" else 2.0,
        "alias": "provider-timeout",
    }
    outcome = _execute_retry_mode(
        "async" if route in {"async", "async-thread"} else "sync", node, ctx, state, **kwargs
    )
    assert outcome.status == "ok"
    assert attempts_path.read_text().splitlines() == ["attempt", "attempt"]


@pytest.mark.parametrize("route", ["thread", "async-thread", "async"])
def test_wrapper_expiration_is_terminal_without_another_attempt(
    tmp_path, ctx, state, route, monkeypatch
):
    if route in {"thread", "async-thread"}:
        monkeypatch.setattr(retry_module, "_can_use_forked_timeout_worker", lambda: False)
    attempts_path = tmp_path / "attempts"
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    class _SlowThreadNode:
        def execute(self, _ctx, passed_state):
            with attempts_path.open("a") as attempts:
                attempts.write("attempt\n")
            started.set()
            try:
                assert release.wait(timeout=2.0)
                return _ok_outcome(passed_state)
            finally:
                finished.set()

    class _SlowAsyncNode:
        async def execute_async(self, _ctx, passed_state):
            with attempts_path.open("a") as attempts:
                attempts.write("attempt\n")
            try:
                await asyncio.sleep(2.0)
                return _ok_outcome(passed_state)
            finally:
                finished.set()

    node = _SlowAsyncNode() if route == "async" else _SlowThreadNode()
    kwargs = {
        "retry_policy": RetryPolicy(max_retries=2, backoff_base_s=0.1, jitter="none"),
        "timeout_s": 0.05,
        "alias": "wrapper-expiry",
    }
    try:
        with pytest.raises(NodeTimeoutError):
            _execute_retry_mode(
                "sync" if route == "thread" else "async", node, ctx, state, **kwargs
            )
    finally:
        release.set()
        assert finished.wait(timeout=2.0)
    if route != "async":
        assert started.is_set()
    assert attempts_path.read_text().splitlines() == ["attempt"]


@pytest.mark.skipif("fork" not in mp.get_all_start_methods(), reason="fork unavailable")
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("shape", ["return", "raise"])
def test_fork_permanent_error_shape_keeps_one_real_attempt(tmp_path, ctx, state, mode, shape):
    attempts_path = tmp_path / "attempts"
    node = _ErrorTransportNode(
        attempts_path,
        ValueError("invalid input contract"),
        return_failure=shape == "return",
        recover=False,
    )
    kwargs = {
        "retry_policy": RetryPolicy(max_retries=2, backoff_base_s=0.1, jitter="none"),
        "timeout_s": 2.0,
        "alias": "transport-permanent",
    }
    if shape == "raise":
        with pytest.raises(RetryExhaustedError):
            _execute_retry_mode(mode, node, ctx, state, **kwargs)
    else:
        outcome = _execute_retry_mode(mode, node, ctx, state, **kwargs)
        assert outcome.status == "fail"
    assert attempts_path.read_text().splitlines() == ["attempt"]


@pytest.mark.skipif("fork" not in mp.get_all_start_methods(), reason="fork unavailable")
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    ("error", "retry_on", "expected_attempts"),
    [
        (_ValidationTransportError("temporary sounding message"), ["node.exception"], 1),
        (AttributeError("invalid node contract"), ["node.exception"], 1),
        (LookupError("invalid lookup contract"), ["node.exception"], 1),
        (_TransientTransportValueError("invalid sounding value"), ["node.transport"], 2),
        (_CodedTransportError("custom code"), ["node.action"], 2),
        (_CodedTransportError("custom code"), ["node.exception"], 1),
        (OSError("ValueError: fatal sounding message"), ["node.exception"], 2),
        (ValueError("ConnectionError: transient sounding message"), ["node.exception"], 1),
    ],
)
def test_fork_exception_preserves_category_and_policy_code(
    tmp_path, ctx, state, mode, error, retry_on, expected_attempts
):
    attempts_path = tmp_path / "attempts"
    node = _ErrorTransportNode(attempts_path, error)
    kwargs = {
        "retry_policy": RetryPolicy(
            max_retries=2, backoff_base_s=0.1, jitter="none", retry_on=retry_on
        ),
        "timeout_s": 2.0,
        "alias": "transport-classified",
    }
    if expected_attempts == 1:
        with pytest.raises(RetryExhaustedError):
            _execute_retry_mode(mode, node, ctx, state, **kwargs)
    else:
        outcome = _execute_retry_mode(mode, node, ctx, state, **kwargs)
        assert outcome.status == "ok"
    assert len(attempts_path.read_text().splitlines()) == expected_attempts


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
    def test_attempt_context_preserves_claim_capable_context_type(self):
        target = ClaimCapableExecutionContext(
            store=MagicMock(),
            run=MagicMock(),
            logger=MagicMock(),
            claim_ledger_owner=MagicMock(),
        )
        authority = retry_module._AttemptAuthority()

        attempt = retry_module._build_attempt_context(target, authority)

        assert isinstance(attempt, ClaimCapableExecutionContext)
        assert attempt.claim_ledger_owner is not target.claim_ledger_owner
        authority.revoke()
        attempt.claim_ledger_owner.persist_candidate_ledger(ledger="late")
        target.claim_ledger_owner.persist_candidate_ledger.assert_not_called()

    def test_claim_capable_execute_preserves_type_and_manifest_authority(self, state, monkeypatch):
        class _RecordingStore:
            def __init__(self) -> None:
                self.put_json_calls: list[tuple[object, object]] = []

            def put_json(self, payload: object, options: object) -> object:
                self.put_json_calls.append((payload, options))
                return object()

        class _RecordingAudit:
            def __init__(self) -> None:
                self.append_calls: list[dict[str, object]] = []
                self.emit_calls: list[object] = []

            def append(self, **kwargs: object) -> None:
                self.append_calls.append(kwargs)

            def emit(self, record: object) -> None:
                self.emit_calls.append(record)

            def close(self) -> None:
                return None

        class _RecordingRun:
            def __init__(self, audit_sink: _RecordingAudit) -> None:
                self.emit_calls: list[tuple[object, ...]] = []
                self.run_manifest = type(
                    "_Manifest",
                    (),
                    {
                        "status": "running",
                        "errors": [{"nested": {"events": []}}],
                    },
                )()
                self._audit_sink = audit_sink

            def emit(self, *args: object, **kwargs: object) -> None:
                self.emit_calls.append((*args, kwargs))

        class _RecordingClaimOwner:
            def __init__(self) -> None:
                self.persist_calls: list[dict[str, object]] = []

            def persist_candidate_ledger(self, **kwargs: object) -> object:
                self.persist_calls.append(kwargs)
                return object()

        store = _RecordingStore()
        run_audit = _RecordingAudit()
        run = _RecordingRun(run_audit)
        audit = _RecordingAudit()
        claim_owner = _RecordingClaimOwner()
        ctx = ClaimCapableExecutionContext(
            store=store,
            run=run,
            logger=MagicMock(),
            audit=audit,
            claim_ledger_owner=claim_owner,
        )
        started = threading.Event()
        release = threading.Event()
        completed = threading.Event()

        class _LateClaimNode:
            def execute(self, passed_ctx, passed_state):
                assert isinstance(passed_ctx, ClaimCapableExecutionContext)
                started.set()
                release.wait(timeout=1.0)
                passed_ctx.run.run_manifest.status = "late"
                passed_ctx.run.run_manifest.errors[0]["nested"]["events"].append("late")
                passed_ctx.store.put_json({"late": "write"}, object())
                passed_ctx.run.emit("late", "LATE_WRITE")
                passed_ctx.run._audit_sink.emit({"late": "audit"})
                passed_ctx.audit.append(action="late")
                passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="late")
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
                    _LateClaimNode(),
                    ctx,
                    state,
                    retry_policy=RetryPolicy(),
                    timeout_s=0.01,
                    alias="late-claim",
                )
            assert started.wait(timeout=0.5)
            release.set()
            assert completed.wait(timeout=0.5)
        finally:
            release.set()
            executor.shutdown(wait=True, cancel_futures=True)

        assert run.run_manifest.status == "running"
        assert run.run_manifest.errors == [{"nested": {"events": []}}]
        assert store.put_json_calls == []
        assert run.emit_calls == []
        assert run_audit.emit_calls == []
        assert audit.append_calls == []
        assert claim_owner.persist_calls == []

        class _OnTimeClaimNode:
            def execute(self, passed_ctx, passed_state):
                assert isinstance(passed_ctx, ClaimCapableExecutionContext)
                passed_ctx.run.run_manifest.status = "on_time"
                passed_ctx.run.run_manifest.errors[0]["nested"]["events"].append("on_time")
                passed_ctx.store.put_json({"on_time": True}, object())
                passed_ctx.run.emit("on-time", "ON_TIME")
                passed_ctx.run._audit_sink.emit({"on_time": "audit"})
                passed_ctx.audit.append(action="on_time")
                passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="on_time")
                return _ok_outcome(passed_state)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            result = execute_with_retry_sync(
                _OnTimeClaimNode(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.5,
                alias="on-time-claim",
            )
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

        assert result.status == "ok"
        assert run.run_manifest.status == "on_time"
        assert run.run_manifest.errors == [{"nested": {"events": ["on_time"]}}]
        assert store.put_json_calls
        assert run.emit_calls
        assert run_audit.emit_calls
        assert audit.append_calls
        assert claim_owner.persist_calls == [{"ledger": "on_time"}]

    def test_claim_capable_execute_preserves_real_run_sinks_on_time(self, state, monkeypatch):
        class _RecordingStore:
            def put_json(self, payload: object, options: object) -> object:
                return object()

        class _RecordingTrace:
            def __init__(self) -> None:
                self.emit_calls: list[object] = []

            def emit(self, record: object) -> None:
                self.emit_calls.append(record)

        class _RecordingAuditSink:
            def __init__(self) -> None:
                self.emit_calls: list[object] = []

            def emit(self, record: object) -> None:
                self.emit_calls.append(record)

            def close(self) -> None:
                return None

        class _RecordingClaimOwner:
            def persist_candidate_ledger(self, **kwargs: object) -> object:
                return object()

        store = _RecordingStore()
        trace = _RecordingTrace()
        audit_sink = _RecordingAuditSink()
        run = RunContext(
            store=store,
            trace=trace,
            run_manifest=RunManifest(
                run_id="run",
                registry_bundle=ArtifactRef(
                    artifact_id="sha256:" + "0" * 64,
                    kind="registry",
                    media_type="application/json",
                ),
            ),
            _audit_sink=audit_sink,
        )
        ctx = ClaimCapableExecutionContext(
            store=store,
            run=run,
            logger=MagicMock(),
            claim_ledger_owner=_RecordingClaimOwner(),
        )
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry._can_use_forked_timeout_worker",
            lambda: False,
        )
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.engine.retry.get_shared_executor",
            lambda: executor,
        )

        class _OnTimeRunNode:
            def execute(self, passed_ctx, passed_state):
                assert isinstance(passed_ctx, ClaimCapableExecutionContext)
                passed_ctx.run.emit("on-time", "ON_TIME")
                return _ok_outcome(passed_state)

        try:
            result = execute_with_retry_sync(
                _OnTimeRunNode(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.5,
                alias="on-time-run",
            )
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

        assert result.status == "ok"
        assert len(trace.emit_calls) == 1
        assert len(audit_sink.emit_calls) == 1

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

    def test_timeout_revokes_late_state_and_owner_writes(self, ctx, state, monkeypatch):
        """A timed-out thread cannot publish after its caller stops waiting."""

        class _RecordingStore:
            def __init__(self) -> None:
                self.put_json_calls: list[object] = []

            def put_json(self, payload: object, options: object) -> object:
                self.put_json_calls.append((payload, options))
                return object()

        class _RecordingRun:
            def __init__(self) -> None:
                self.emit_calls: list[tuple[object, ...]] = []

            def emit(self, *args: object, **kwargs: object) -> None:
                self.emit_calls.append((*args, kwargs))

        class _RecordingAudit:
            def __init__(self) -> None:
                self.append_calls: list[dict[str, object]] = []

            def append(self, **kwargs: object) -> None:
                self.append_calls.append(kwargs)

            def close(self) -> None:
                return None

        class _RecordingClaimOwner:
            def __init__(self) -> None:
                self.persist_calls: list[dict[str, object]] = []

            def persist_candidate_ledger(self, **kwargs: object) -> object:
                self.persist_calls.append(kwargs)
                return object()

        recording_store = _RecordingStore()
        recording_run = _RecordingRun()
        recording_run.run_manifest = type("_Manifest", (), {"status": "running"})()
        recording_audit = _RecordingAudit()
        recording_claim_owner = _RecordingClaimOwner()
        ctx.store = recording_store
        ctx.run = recording_run
        ctx.audit = recording_audit
        ctx.claim_ledger_owner = recording_claim_owner

        started = threading.Event()
        release = threading.Event()
        completed = threading.Event()

        class _LateAuthorityNode:
            def execute(self, passed_ctx, passed_state):
                started.set()
                release.wait(timeout=1.0)
                passed_state.params["late_write"] = "unauthorised"
                passed_ctx.run.run_manifest.status = "late"
                passed_ctx.store.put_json({"late": "write"}, object())
                passed_ctx.run.emit("late-authority", "LATE_WRITE")
                passed_ctx.audit.append(run_id="run", actor="node", action="late")
                passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="late")
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
                    _LateAuthorityNode(),
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

        assert state.params == {}
        assert recording_run.run_manifest.status == "running"
        assert recording_store.put_json_calls == []
        assert recording_run.emit_calls == []
        assert recording_audit.append_calls == []
        assert recording_claim_owner.persist_calls == []

        class _SuccessfulAuthorityNode:
            def execute(self, passed_ctx, passed_state):
                passed_state.params["on_time"] = True
                passed_ctx.run.run_manifest.status = "on_time"
                passed_ctx.store.put_json({"on_time": True}, object())
                passed_ctx.run.emit("on-time", "ON_TIME")
                passed_ctx.audit.append(run_id="run", actor="node", action="on_time")
                passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="on_time")
                return _ok_outcome(passed_state)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            result = execute_with_retry_sync(
                _SuccessfulAuthorityNode(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.5,
                alias="on-time",
            )
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

        assert result.status == "ok"
        assert recording_run.run_manifest.status == "on_time"
        assert recording_store.put_json_calls
        assert recording_run.emit_calls
        assert recording_audit.append_calls
        assert recording_claim_owner.persist_calls

    @pytest.mark.asyncio
    async def test_async_timeout_revokes_late_owner_writes(self, ctx, state):
        """A non-cooperative async attempt loses write authority on timeout."""

        class _RecordingStore:
            def __init__(self) -> None:
                self.put_json_calls: list[object] = []

            def put_json(self, payload: object, options: object) -> object:
                self.put_json_calls.append((payload, options))
                return object()

        class _RecordingRun:
            def __init__(self) -> None:
                self.emit_calls: list[tuple[object, ...]] = []
                self.run_manifest = type("_Manifest", (), {"status": "running"})()

            def emit(self, *args: object, **kwargs: object) -> None:
                self.emit_calls.append((*args, kwargs))

        class _RecordingAudit:
            def __init__(self) -> None:
                self.append_calls: list[dict[str, object]] = []

            def append(self, **kwargs: object) -> None:
                self.append_calls.append(kwargs)

            def close(self) -> None:
                return None

        class _RecordingClaimOwner:
            def __init__(self) -> None:
                self.persist_calls: list[dict[str, object]] = []

            def persist_candidate_ledger(self, **kwargs: object) -> object:
                self.persist_calls.append(kwargs)
                return object()

        recording_store = _RecordingStore()
        recording_run = _RecordingRun()
        recording_audit = _RecordingAudit()
        recording_claim_owner = _RecordingClaimOwner()
        ctx.store = recording_store
        ctx.run = recording_run
        ctx.audit = recording_audit
        ctx.claim_ledger_owner = recording_claim_owner

        started = asyncio.Event()
        release = asyncio.Event()
        completed = asyncio.Event()

        class _LateAsyncAuthorityNode:
            async def execute_async(self, passed_ctx, passed_state):
                started.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
                passed_state.params["late_write"] = "unauthorised"
                passed_ctx.run.run_manifest.status = "late"
                passed_ctx.store.put_json({"late": "write"}, object())
                passed_ctx.run.emit("late-authority", "LATE_WRITE")
                passed_ctx.audit.append(run_id="run", actor="node", action="late")
                passed_ctx.claim_ledger_owner.persist_candidate_ledger(ledger="late")
                completed.set()
                return _ok_outcome(passed_state)

        result_task = asyncio.create_task(
            execute_with_retry_async(
                _LateAsyncAuthorityNode(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.01,
                alias="late-async-write",
            )
        )

        async def _release_later() -> None:
            await asyncio.sleep(0.05)
            release.set()

        release_task = asyncio.create_task(_release_later())
        await started.wait()
        assert started.is_set()
        with pytest.raises(NodeTimeoutError):
            await result_task
        await release_task
        await asyncio.wait_for(completed.wait(), timeout=0.5)

        assert state.params == {}
        assert recording_run.run_manifest.status == "running"
        assert recording_store.put_json_calls == []
        assert recording_run.emit_calls == []
        assert recording_audit.append_calls == []
        assert recording_claim_owner.persist_calls == []

    def test_timeout_path_uses_shared_executor(self, ctx, state, monkeypatch):
        class _FakeExecutor:
            def __init__(self) -> None:
                self.submissions: list[tuple[object, tuple[object, ...]]] = []

            def submit(self, fn, *args):
                self.submissions.append((fn, args))
                future = concurrent.futures.Future()
                future.set_result(fn(*args))
                return future

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
        assert submitted_fn.__self__ is not None
        assert len(submitted_args) == 3
        assert submitted_args[1] is not ctx
        assert submitted_args[2] is not state
        assert submitted_args[0] is node.execute

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


class TestRetryTimeoutWorker:
    def test_timeout_worker_does_not_swallow_system_exit(self, ctx, state):
        node = MagicMock()
        node.execute.side_effect = SystemExit("stop-now")
        result_queue = MagicMock()

        with pytest.raises(SystemExit, match="stop-now"):
            _node_execute_worker(node, ctx, state, result_queue)

        result_queue.put.assert_not_called()


class _PayloadTransportNode:
    """Return a deterministic result large enough to exercise Queue backpressure."""

    def __init__(self, payload_size: int) -> None:
        self.payload_size = payload_size

    def execute(self, _ctx, passed_state):
        result_state = passed_state.model_copy(deep=True)
        result_state.params["payload"] = "x" * self.payload_size
        return _ok_outcome(result_state)


@pytest.mark.skipif(
    "fork" not in mp.get_all_start_methods(), reason="actual fork worker unavailable"
)
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("payload_size", [64, 1024 * 1024], ids=["small", "one-mib"])
def test_fork_transport_drains_small_and_large_outcomes(ctx, state, mode, payload_size) -> None:
    """A fork worker delivers results without joining before Queue drain."""
    node = _PayloadTransportNode(payload_size)
    kwargs = {"retry_policy": RetryPolicy(), "timeout_s": 2.0, "alias": "payload-wire"}

    if mode == "sync":
        result = execute_with_retry_sync(node, ctx, state, **kwargs)
    else:
        result = asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))

    assert result.status == "ok"
    assert result.state.params["payload"] == "x" * payload_size


class _BrokenResultQueue:
    """A result channel that fails every send; success must never be fabricated."""

    def __init__(self) -> None:
        self.attempts = 0

    def put(self, _value) -> None:
        self.attempts += 1
        raise OSError("result channel closed")


def test_worker_send_failure_is_fail_closed(ctx, state) -> None:
    node = _PayloadTransportNode(64)
    result_queue = _BrokenResultQueue()

    with pytest.raises(RuntimeError, match="failed to send result"):
        _node_execute_worker(node, ctx, state, result_queue)

    assert result_queue.attempts >= 2


class _SerializationFailureOutcome:
    def model_dump(self, *, mode: str):
        raise TypeError(f"cannot serialize in {mode} mode")


class _SerializationFailureNode:
    def execute(self, _ctx, _state):
        return _SerializationFailureOutcome()


def test_serialization_failure_is_not_reported_as_success(ctx, state) -> None:
    """A worker serialization error reaches the caller as a transport failure."""
    with pytest.raises(RuntimeError, match="TypeError: cannot serialize"):
        retry_module._execute_with_timeout_process(
            _SerializationFailureNode(),
            ctx,
            state,
            timeout_s=2.0,
        )


class _ExitedWorker:
    """Minimal process double for a result arriving after the compute window."""

    def is_alive(self) -> bool:
        return False


class _StoppedProcessHandle:
    def is_alive(self) -> bool:
        return False

    def join(self, *, timeout: float) -> None:
        _ = timeout


def test_unknown_process_group_cleanup_is_not_reported_complete() -> None:
    """A stopped worker without a group cannot prove descendants are gone."""
    assert retry_module._terminate_owned_process(_StoppedProcessHandle(), None) is False


class _ImmediateResultQueue:
    def get(self, *, timeout: float):
        _ = timeout
        return ("ok", {})

    def get_nowait(self):
        return ("ok", {})


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_late_worker_completion_is_not_delivery_success(mode) -> None:
    """A dead worker alone cannot prove computation met its deadline."""
    process = _ExitedWorker()
    result_queue = _ImmediateResultQueue()
    compute_deadline = _time.monotonic() - 1.0

    if mode == "sync":
        with pytest.raises(retry_module._WorkerComputeTimeout):
            retry_module._drain_result_sync(
                process,
                result_queue,
                compute_deadline=compute_deadline,
            )
    else:
        with pytest.raises(retry_module._WorkerComputeTimeout):
            asyncio.run(
                retry_module._drain_result_async(
                    process,
                    result_queue,
                    compute_deadline=compute_deadline,
                )
            )


class _DescendantProcessNode:
    """Keep an owned descendant alive long enough to exercise group cleanup."""

    def __init__(self, pid_path) -> None:
        self.pid_path = pid_path

    def execute(self, _ctx, _state):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.pid_path.write_text(str(child.pid))
        _time.sleep(30)
        raise AssertionError("timeout should terminate the worker first")


def _execute_retry_mode(mode, node, ctx, state, **kwargs):
    if mode == "sync":
        return execute_with_retry_sync(node, ctx, state, **kwargs)
    return asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))


@pytest.mark.skipif(
    "fork" not in mp.get_all_start_methods(), reason="actual fork worker unavailable"
)
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_timeout_cleans_owned_process_descendant(tmp_path, ctx, state, mode) -> None:
    """Timeout cleanup owns the worker group and does not leave descendants."""
    pid_path = tmp_path / "descendant-pid"
    node = _DescendantProcessNode(pid_path)
    descendant_pid: int | None = None
    kwargs = {
        "retry_policy": RetryPolicy(),
        "timeout_s": 0.5,
        "alias": "descendant-cleanup",
    }

    try:
        with pytest.raises(NodeTimeoutError):
            _execute_retry_mode(mode, node, ctx, state, **kwargs)
        assert pid_path.exists()
        descendant_pid = int(pid_path.read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(descendant_pid, 0)
    finally:
        if descendant_pid is not None:
            try:
                os.kill(descendant_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


class _ExitedWorkerWithDescendantNode:
    """Exit the worker while leaving a descendant in its owned process group."""

    def __init__(self, pid_path) -> None:
        self.pid_path = pid_path

    def execute(self, _ctx, _state):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.pid_path.write_text(str(child.pid))
        os._exit(0)


@pytest.mark.skipif(
    "fork" not in mp.get_all_start_methods(), reason="actual fork worker unavailable"
)
def test_cleanup_kills_descendant_after_worker_exit(tmp_path, ctx, state) -> None:
    """Cleanup must still reap an owned group after its worker has exited."""
    pid_path = tmp_path / "exited-worker-descendant-pid"
    node = _ExitedWorkerWithDescendantNode(pid_path)
    descendant_pid: int | None = None

    try:
        with pytest.raises(NodeTimeoutError):
            retry_module._execute_with_timeout_process(
                node,
                ctx,
                state,
                timeout_s=0.5,
            )
        assert pid_path.exists()
        descendant_pid = int(pid_path.read_text())
        for _ in range(20):
            try:
                os.kill(descendant_pid, 0)
            except ProcessLookupError:
                break
            _time.sleep(0.05)
        else:
            pytest.fail("owned descendant survived worker cleanup")
    finally:
        if descendant_pid is not None:
            try:
                os.kill(descendant_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


class _GrandchildProcessNode:
    """Create two TERM-resistant generations in the owned worker group."""

    def __init__(self, pid_path, late_path, escape_group=False) -> None:
        self.pid_path = pid_path
        self.late_path = late_path
        self.escape_group = escape_group

    def execute(self, _ctx, _state):
        grandchild_code = (
            "import pathlib,signal,time; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "time.sleep(1.5); "
            f"pathlib.Path({str(self.late_path)!r}).write_text('unauthorized late write'); "
            "time.sleep(30)"
        )
        child_code = (
            "import os,pathlib,signal,subprocess,sys,time; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            f"child=subprocess.Popen([sys.executable, '-c', {grandchild_code!r}]); "
            f"pathlib.Path({str(self.pid_path)!r}).write_text(str(os.getpid())+' '+str(child.pid)); "
            "time.sleep(30)"
        )
        subprocess.Popen([sys.executable, "-c", child_code], start_new_session=self.escape_group)
        _time.sleep(30)
        raise AssertionError("timeout must terminate the owned computation")


@pytest.mark.skipif(sys.platform != "linux", reason="process-local Linux subreaper contract")
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("escape_group", [False, True], ids=["owned-group", "new-session"])
def test_timeout_reaps_term_resistant_grandchildren_before_refusal(
    tmp_path, ctx, state, mode, escape_group
):
    """Both descendant generations are reaped and cannot write after refusal."""
    pid_path = tmp_path / "grandchild-pids"
    late_path = tmp_path / "late-write"
    node = _GrandchildProcessNode(pid_path, late_path, escape_group)
    kwargs = {"retry_policy": RetryPolicy(), "timeout_s": 0.5, "alias": "grandchild-cleanup"}
    with pytest.raises(NodeTimeoutError, match=r"^Node exceeded timeout of 0.5s$"):
        _execute_retry_mode(mode, node, ctx, state, **kwargs)
    for pid in map(int, pid_path.read_text().split()):
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    _time.sleep(1.0)
    assert not late_path.exists()


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "linux", reason="process-local Linux subreaper contract")
async def test_cancelled_process_wait_reaps_descendants(tmp_path, ctx, state):
    """Cancelling the async caller also waits for its owned process cleanup."""
    pid_path = tmp_path / "cancelled-descendant-pid"
    task = asyncio.create_task(
        execute_with_retry_async(
            _DescendantProcessNode(pid_path),
            ctx,
            state,
            retry_policy=RetryPolicy(),
            timeout_s=30.0,
            alias="cancelled-descendant",
        )
    )
    for _ in range(100):
        if pid_path.exists():
            break
        await asyncio.sleep(0.02)
    assert pid_path.exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_path.read_text()), 0)


@pytest.mark.skipif(sys.platform != "linux", reason="process-local Linux subreaper contract")
def test_supervisor_setup_failure_cannot_publish_success(ctx, state, monkeypatch):
    """A real supervisor startup fault returns failure rather than a node result."""

    def _fail_setup():
        raise OSError("subreaper setup failed")

    monkeypatch.setattr(retry_module, "_enable_linux_child_subreaper", _fail_setup)
    with pytest.raises(
        RuntimeError, match="worker supervision failed: OSError: subreaper setup failed"
    ):
        retry_module._execute_with_timeout_process(
            _PayloadTransportNode(64), ctx, state, timeout_s=2.0
        )


@pytest.mark.skipif("fork" not in mp.get_all_start_methods(), reason="fork worker required")
def test_process_start_failure_retains_original_exception(ctx, state, monkeypatch):
    """Closing an unstarted handle must not replace the actual startup fault."""

    def _fail_start(_process):
        raise OSError("owned process start failed")

    monkeypatch.setattr(mp.get_context("fork").Process, "start", _fail_start)
    with pytest.raises(OSError, match="owned process start failed"):
        retry_module._execute_with_timeout_process(
            _PayloadTransportNode(64), ctx, state, timeout_s=2.0
        )


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper status available")
def test_timeout_supervisor_does_not_change_caller_subreaper_status(ctx, state):
    """The kernel flag belongs to the disposable supervisor, not this caller."""
    import ctypes

    def _caller_status() -> int:
        status = ctypes.c_int()
        assert ctypes.CDLL(None).prctl(37, ctypes.byref(status), 0, 0, 0) == 0
        return status.value

    before = _caller_status()
    result = retry_module._execute_with_timeout_process(
        _PayloadTransportNode(64), ctx, state, timeout_s=2.0
    )
    assert result.status == "ok"
    assert _caller_status() == before


@pytest.mark.parametrize("mode", ["direct", "thread", "fork", "async"])
def test_concurrent_request_contexts_match_across_retry_routes(ctx, state, mode, monkeypatch):
    """Two real request contexts keep their own marker in every supported route."""
    import concurrent.futures
    import contextvars

    if mode == "fork" and "fork" not in mp.get_all_start_methods():
        pytest.skip("actual fork worker unavailable")
    scope = contextvars.ContextVar("request_context", default=None)

    class _ContextNode:
        def execute(self, _ctx, passed_state):
            _time.sleep(0.02)
            result_state = passed_state.model_copy(deep=True)
            result_state.params["request_context"] = scope.get()
            return _ok_outcome(result_state)

    class _AsyncContextNode:
        async def execute_async(self, _ctx, passed_state):
            await asyncio.sleep(0.02)
            result_state = passed_state.model_copy(deep=True)
            result_state.params["request_context"] = scope.get()
            return _ok_outcome(result_state)

    if mode == "thread":
        monkeypatch.setattr(retry_module, "_can_use_forked_timeout_worker", lambda: False)

    def _request(marker):
        token = scope.set(marker)
        try:
            if mode == "async":
                result = asyncio.run(
                    execute_with_retry_async(
                        _AsyncContextNode(),
                        ctx,
                        state,
                        retry_policy=RetryPolicy(),
                        timeout_s=2.0,
                        alias="context-async",
                    )
                )
            else:
                result = execute_with_retry_sync(
                    _ContextNode(),
                    ctx,
                    state,
                    retry_policy=RetryPolicy(),
                    timeout_s=None if mode == "direct" else 2.0,
                    alias="context-sync",
                )
            return result.state.params["request_context"]
        finally:
            scope.reset(token)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as callers:
        assert list(callers.map(_request, ["request-A", "request-B"])) == [
            "request-A",
            "request-B",
        ]
    assert scope.get() is None
    assert state.params == {}


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
