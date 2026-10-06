"""Tests for polisyos.scientist.orchestration.engine.retry — RetryPolicy + wrappers."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import threading
import time as _time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import BoundedLivenessConfig
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

    def test_timeout_path_uses_shared_executor(self, tmp_path, ctx, state, monkeypatch):
        from polisyos.common.async_tools import _SharedExecutor

        effects = tmp_path / "worker-thread"
        caller = threading.get_ident()

        class Node:
            def execute(self, passed_ctx, passed_state):
                assert passed_ctx is not ctx
                assert passed_state is not state
                effects.write_text(str(threading.get_ident()))
                return _ok_outcome(passed_state)

        with _SharedExecutor(max_workers=4) as executor:
            monkeypatch.setattr(retry_module, "_can_use_forked_timeout_worker", lambda: False)
            monkeypatch.setattr(retry_module, "get_shared_executor", lambda: executor)
            result = execute_with_retry_sync(
                Node(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=0.5,
                alias="actual-shared-thread",
            )
        assert result.status == "ok"
        assert int(effects.read_text()) != caller

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

    def invoke():
        if mode == "sync":
            retry_module._drain_result_sync(
                process,
                result_queue,
                compute_deadline=compute_deadline,
            )
        else:
            asyncio.run(
                retry_module._drain_result_async(
                    process,
                    result_queue,
                    compute_deadline=compute_deadline,
                )
            )

    with pytest.raises(retry_module._WorkerComputeTimeout):
        invoke()


class _DescendantProcessNode:
    """Keep an owned descendant alive long enough to exercise group cleanup."""

    def __init__(self, pid_path) -> None:
        self.pid_path = pid_path

    def execute(self, _ctx, _state):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.pid_path.write_text(str(child.pid))
        _time.sleep(30)
        raise AssertionError("timeout should terminate the worker first")


@pytest.mark.skipif(
    "fork" not in mp.get_all_start_methods(), reason="actual fork worker unavailable"
)
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_timeout_cleans_owned_process_descendant(tmp_path, ctx, state, mode) -> None:
    """Timeout cleanup owns the worker group and does not leave descendants."""
    pid_path = tmp_path / "descendant-pid"
    node = _DescendantProcessNode(pid_path)
    descendant_pid: int | None = None

    try:

        def invoke():
            kwargs = {
                "retry_policy": RetryPolicy(),
                "timeout_s": 0.5,
                "alias": "descendant-cleanup",
            }
            if mode == "sync":
                execute_with_retry_sync(node, ctx, state, **kwargs)
            else:
                asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))

        with pytest.raises(NodeTimeoutError):
            invoke()
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


class _OwnedProcessTreeNode:
    """Run a real new-session, TERM-resistant grandchild with observable writes."""

    def __init__(self, directory, *, finish):
        self.directory = directory
        self.finish = finish

    def execute(self, _ctx, state):
        effects = self.directory / "grandchild-effects.txt"
        identities = self.directory / "process-identities.json"
        leaf = (
            "import os,signal,time\n"
            "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
            f"f=open({str(effects)!r},'a',buffering=1)\n"
            "while True:\n f.write('effect\\n')\n time.sleep(.002)\n"
        )
        ancestor = (
            "import json,os,signal,subprocess,sys,time; "
            "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
            f"p=subprocess.Popen([sys.executable,'-c',{leaf!r}],start_new_session=True); "
            f"open({str(identities)!r},'w').write(json.dumps([os.getppid(),os.getpid(),p.pid])); "
            "time.sleep(30)"
        )
        subprocess.Popen([sys.executable, "-c", ancestor], start_new_session=True)
        deadline = _time.monotonic() + 2
        while not effects.exists() or not effects.stat().st_size:
            if _time.monotonic() >= deadline:
                raise RuntimeError("real grandchild did not enter its filesystem effect")
            _time.sleep(0.001)
        if self.finish:
            return _ok_outcome(state)
        _time.sleep(30)
        return _ok_outcome(state)


def _assert_real_tree_reaped(directory):
    import json

    pids = json.loads((directory / "process-identities.json").read_text())
    assert len(pids) == 3 and len(set(pids)) == 3
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    effects = directory / "grandchild-effects.txt"
    observed = effects.read_bytes()
    assert observed.startswith(b"effect\n")
    _time.sleep(0.02)
    assert effects.read_bytes() == observed


def _caller_subreaper_flag():
    import ctypes

    flag = ctypes.c_int()
    assert ctypes.CDLL(None).prctl(37, ctypes.byref(flag), 0, 0, 0) == 0
    return flag.value


@pytest.fixture
def owned_tree_dir(tmp_path):
    """Keep failed negative controls from leaving running effect producers."""
    import json

    try:
        yield tmp_path
    finally:
        identities = tmp_path / "process-identities.json"
        if identities.exists():
            for pid in reversed(json.loads(identities.read_text())):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child subreaper contract")
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("finish", [True, False], ids=["returned", "expired"])
def test_owned_supervisor_reaps_real_new_session_grandchild(
    owned_tree_dir, ctx, state, mode, finish
):
    tmp_path = owned_tree_dir
    original_flag = _caller_subreaper_flag()
    node = _OwnedProcessTreeNode(tmp_path, finish=finish)
    kwargs = {"retry_policy": RetryPolicy(), "timeout_s": 0.3, "alias": "actual-tree"}
    if finish:
        outcome = (
            execute_with_retry_sync(node, ctx, state, **kwargs)
            if mode == "sync"
            else asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))
        )
        assert outcome.status == "ok"
    else:

        def invoke():
            if mode == "sync":
                return execute_with_retry_sync(node, ctx, state, **kwargs)
            return asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))

        with pytest.raises(NodeTimeoutError) as expired:
            invoke()
    _assert_real_tree_reaped(tmp_path)
    if not finish:
        assert expired.value.details["execution_state"] == "owned_processes_reaped"
        assert expired.value.details["cleanup_complete"] is True
    assert _caller_subreaper_flag() == original_flag


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child subreaper contract")
def test_owned_supervisor_reaps_tree_on_async_caller_cancellation(owned_tree_dir, ctx, state):
    tmp_path = owned_tree_dir
    original_flag = _caller_subreaper_flag()

    async def exercise():
        task = asyncio.create_task(
            execute_with_retry_async(
                _OwnedProcessTreeNode(tmp_path, finish=False),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=5,
                alias="cancel-tree",
            )
        )
        deadline = _time.monotonic() + 2
        effects = tmp_path / "grandchild-effects.txt"
        while not effects.exists() or not effects.stat().st_size:
            assert _time.monotonic() < deadline
            await asyncio.sleep(0.002)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    _assert_real_tree_reaped(tmp_path)
    assert _caller_subreaper_flag() == original_flag


def test_framed_result_reader_never_blocks_on_an_actual_partial_pipe():
    channel = retry_module._WorkerResultChannel(mp.get_context("fork"))
    try:
        os.write(channel._writer.fileno(), (100).to_bytes(8, "big") + b"abc")
        started = _time.monotonic()
        with pytest.raises(retry_module.queue.Empty):
            channel.get_nowait()
        assert _time.monotonic() - started < 0.05
        channel.close_writer()
        with pytest.raises(EOFError):
            channel.get_nowait()
    finally:
        channel.close()


def test_real_process_start_failure_preserves_original_error_and_no_body_effect(
    tmp_path, ctx, state, monkeypatch
):
    entered = tmp_path / "entered.txt"

    class Node:
        def execute(self, _ctx, passed_state):
            entered.write_text("physical body")
            return _ok_outcome(passed_state)

    def denied(_process):
        raise OSError("actual process start denied")

    monkeypatch.setattr(mp.get_context("fork").Process, "start", denied)
    with pytest.raises(OSError, match="actual process start denied"):
        retry_module._execute_with_timeout_process(Node(), ctx, state, timeout_s=0.1)
    assert not entered.exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child subreaper contract")
def test_supervisor_setup_failure_is_transported_without_starting_node(
    tmp_path, ctx, state, monkeypatch
):
    entered = tmp_path / "entered.txt"

    class Node:
        def execute(self, _ctx, passed_state):
            entered.write_text("physical body")
            return _ok_outcome(passed_state)

    def denied():
        raise OSError("subreaper capability denied")

    monkeypatch.setattr(retry_module, "_enable_child_subreaper", denied)
    before = _caller_subreaper_flag()
    with pytest.raises(RuntimeError, match="subreaper capability denied"):
        retry_module._execute_with_timeout_process(Node(), ctx, state, timeout_s=0.5)
    assert not entered.exists()
    assert _caller_subreaper_flag() == before


@pytest.mark.skipif(sys.platform != "linux", reason="actual Linux RLIMIT descriptor oracle")
@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("preparation", ["cold", "synchronize", "shared"])
def test_worker_setup_fault_closes_real_pipe_descriptors(tmp_path, mode, preparation):
    """Every preparation failure releases owned Pipe ends, with traceback retained."""
    effects = tmp_path / "node.effects"
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("_retry_setup_probe.py")),
            mode,
            preparation,
            str(effects),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert observed["failure"]["type"] == "OSError", observed
    assert observed["failure"]["errno"] == 24, observed
    assert observed["retained_exception"] is True, observed
    assert observed["new_descriptors"] == [], observed
    assert observed["after"] == observed["before"], observed
    assert observed["body_effect"] is False, observed
    assert not effects.exists()


_BOUNDARY_ROUTES = [
    "sync",
    "async-sync",
    "sync-thread",
    "async-thread",
    "sync-fork",
    "async-fork",
    "genuine-async",
]


def _invoke_boundary(route, node, ctx, state, **kwargs):
    if route.startswith("async") or route == "genuine-async":
        return asyncio.run(execute_with_retry_async(node, ctx, state, **kwargs))
    return execute_with_retry_sync(node, ctx, state, **kwargs)


@pytest.mark.parametrize("route", _BOUNDARY_ROUTES)
@pytest.mark.parametrize(
    "kind",
    [
        "permanent",
        "provider_timeout",
        "returned_permanent",
        "custom_transient",
        "filtered_transient",
    ],
)
def test_canonical_retry_boundary_uses_actual_attempt_files(
    tmp_path, ctx, state, monkeypatch, route, kind
):
    """Error shape and boundary preserve category/code and actual retry count."""
    import contextvars

    attempt_file = tmp_path / "attempts.txt"
    owner = contextvars.ContextVar("run_boundary_owner", default="missing")
    token = owner.set("captured-owner")

    class ProviderError(ConnectionError):
        code = "provider.transient"

    class Node:
        def execute(self, passed_ctx, passed_state):
            with attempt_file.open("a") as stream:
                stream.write(owner.get() + "\n")
            attempt = len(attempt_file.read_text().splitlines())
            if attempt == 1:
                if kind == "permanent":
                    raise ValueError("same diagnostic")
                if kind == "provider_timeout":
                    raise TimeoutError("same diagnostic")
                if kind == "returned_permanent":
                    return _fail_outcome(passed_state, code="node.invalid_state")
                if kind in {"custom_transient", "filtered_transient"}:
                    raise ProviderError("same diagnostic")
            return _ok_outcome(passed_state)

    class AsyncNode(Node):
        async def execute_async(self, passed_ctx, passed_state):
            return self.execute(passed_ctx, passed_state)

    monkeypatch.setattr(
        retry_module, "_can_use_forked_timeout_worker", lambda: route.endswith("fork")
    )
    kwargs = dict(
        retry_policy=RetryPolicy(
            max_retries=1,
            backoff_base_s=0.1,
            jitter="none",
            retry_on=["provider.transient"] if kind == "custom_transient" else ["node.exception"],
        ),
        timeout_s=None if route in {"sync", "async-sync"} else 1.0,
        alias="canonical-boundary",
    )
    node = (AsyncNode if route == "genuine-async" else Node)()
    try:
        if kind in {"permanent", "filtered_transient"}:
            with pytest.raises(RetryExhaustedError):
                _invoke_boundary(route, node, ctx, state, **kwargs)
        else:
            outcome = _invoke_boundary(route, node, ctx, state, **kwargs)
            assert outcome.status == ("fail" if kind == "returned_permanent" else "ok")
    finally:
        owner.reset(token)
    expected = 2 if kind in {"provider_timeout", "custom_transient"} else 1
    assert attempt_file.read_text().splitlines() == ["captured-owner"] * expected


@pytest.mark.parametrize(
    "route", ["sync-thread", "async-thread", "sync-fork", "async-fork", "genuine-async"]
)
def test_whole_invocation_deadline_includes_retry_backoff(tmp_path, ctx, state, monkeypatch, route):
    """A retry cannot enter user code after its one invocation budget expired."""
    attempts = tmp_path / "attempts.txt"

    class Node:
        def execute(self, passed_ctx, passed_state):
            with attempts.open("a") as stream:
                stream.write("attempt\n")
            if len(attempts.read_text().splitlines()) == 1:
                raise ConnectionError("retryable provider failure")
            return _ok_outcome(passed_state)

    class AsyncNode(Node):
        async def execute_async(self, passed_ctx, passed_state):
            return self.execute(passed_ctx, passed_state)

    monkeypatch.setattr(
        retry_module, "_can_use_forked_timeout_worker", lambda: route.endswith("fork")
    )
    start = _time.monotonic()
    with pytest.raises(NodeTimeoutError):
        _invoke_boundary(
            route,
            (AsyncNode if route == "genuine-async" else Node)(),
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=2, backoff_base_s=1.0, jitter="none"),
            timeout_s=0.5,
            alias="single-deadline",
        )
    assert attempts.read_text().splitlines() == ["attempt"]
    assert _time.monotonic() - start < 1.2


def test_unconfigured_sync_bridge_has_no_implicit_timeout(ctx, state, monkeypatch):
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_DEFAULT_TIMEOUT_SECONDS", 0.005)

    class Node:
        def execute(self, passed_ctx, passed_state):
            _time.sleep(0.02)
            return _ok_outcome(passed_state)

    result = asyncio.run(
        execute_with_retry_async(
            Node(),
            ctx,
            state,
            retry_policy=RetryPolicy(),
            timeout_s=None,
            alias="explicit-unbounded",
        )
    )
    assert result.status == "ok"


def test_event_loop_block_cannot_publish_owned_write_after_deadline(tmp_path, ctx, state):
    effects = tmp_path / "owned.json"

    class Store:
        def put_json(self, payload, options):
            effects.write_text(json.dumps(payload))

    ctx.store = Store()

    class Node:
        async def execute_async(self, passed_ctx, passed_state):
            _time.sleep(0.04)
            passed_ctx.store.put_json({"late": True}, None)
            return _ok_outcome(passed_state)

    with pytest.raises(NodeTimeoutError):
        asyncio.run(
            execute_with_retry_async(
                Node(), ctx, state, retry_policy=RetryPolicy(), timeout_s=0.01, alias="blocked-loop"
            )
        )
    assert not effects.exists()


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_absolute_deadline_refuses_admission_after_expiry(tmp_path, ctx, state, mode):
    effects = tmp_path / "physical-body"

    class Node:
        def execute(self, passed_ctx, passed_state):
            effects.write_text("body")
            return _ok_outcome(passed_state)

    with pytest.raises(NodeTimeoutError):
        _invoke_boundary(
            mode,
            Node(),
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=1),
            timeout_s=1.0,
            deadline_monotonic=_time.monotonic() - 0.001,
            alias="expired-before-admission",
        )
    assert not effects.exists()


@pytest.mark.parametrize("termination", ["deadline", "cancellation"])
@pytest.mark.asyncio
async def test_queued_async_thread_attempt_never_enters_body_after_termination(
    tmp_path, ctx, state, monkeypatch, termination
):
    from polisyos.common.async_tools import _SharedExecutor

    executor = _SharedExecutor(max_workers=4)
    occupied = threading.Barrier(5)
    release = threading.Event()
    effects = tmp_path / "physical-body"

    def blocker():
        occupied.wait(timeout=2)
        release.wait(timeout=2)

    blockers = [executor.submit(blocker) for _ in range(4)]
    occupied.wait(timeout=2)
    monkeypatch.setattr(retry_module, "get_shared_executor", lambda: executor)
    monkeypatch.setattr(retry_module, "_can_use_forked_timeout_worker", lambda: False)

    class Node:
        def execute(self, passed_ctx, passed_state):
            effects.write_text("physical execution after owner return")
            return _ok_outcome(passed_state)

    try:
        task = asyncio.create_task(
            execute_with_retry_async(
                Node(),
                ctx,
                state,
                retry_policy=RetryPolicy(max_retries=2),
                timeout_s=0.03 if termination == "deadline" else 1.0,
                alias="queued",
            )
        )
        if termination == "cancellation":
            # Admit the real queued job before cancelling its async owner.
            for _ in range(100):
                if executor._work_queue.qsize() > 0:
                    break
                await asyncio.sleep(0.001)
            assert executor._work_queue.qsize() > 0
            task.cancel()
        with pytest.raises(
            NodeTimeoutError if termination == "deadline" else asyncio.CancelledError
        ):
            await task
        # Same-turn release falsifies deferred asyncio-only Future cancellation.
        release.set()
        for future in blockers:
            future.result(timeout=2)
        executor.shutdown(wait=True, cancel_futures=True)
        assert not effects.exists()
    finally:
        release.set()
        executor.shutdown(wait=True, cancel_futures=True)


@pytest.mark.parametrize("control", ["SystemExit", "KeyboardInterrupt", "SystemExitUnsupported"])
@pytest.mark.parametrize("mode", ["sync", "async"])
def test_real_process_preserves_control_exception_without_retry(tmp_path, mode, control):
    effects = tmp_path / "attempts"
    script = """import asyncio,json,multiprocessing,sys
from pathlib import Path
from unittest.mock import MagicMock
from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_sync, execute_with_retry_async
from polisyos.scientist.orchestration.engine.state import ExperimentState
path=Path(sys.argv[1]); mode, control=sys.argv[2:]
class Node:
 def execute(self,ctx,state):
  with path.open('a') as stream:stream.write('attempt\\n')
  if control=='SystemExit':raise SystemExit(17)
  if control=='SystemExitUnsupported':raise SystemExit(object())
  raise KeyboardInterrupt()
kwargs=dict(retry_policy=RetryPolicy(max_retries=2),timeout_s=.5,alias='actual-control')
try:
 if mode=='sync':execute_with_retry_sync(Node(),MagicMock(),ExperimentState(run_id='R_control'),**kwargs)
 else:asyncio.run(execute_with_retry_async(Node(),MagicMock(),ExperimentState(run_id='R_control'),**kwargs))
except BaseException as exc:
 print(json.dumps(dict(type=type(exc).__name__,code=getattr(exc,'code',None),cause_code=getattr(exc.__cause__,'code',None),cause_category=getattr(exc.__cause__,'category',None),attempts=len(path.read_text().splitlines()),live_children=[p.pid for p in multiprocessing.active_children()])))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(effects), mode, control],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    if control == "SystemExitUnsupported":
        assert observed["type"] == "RetryExhaustedError", observed
        assert observed["cause_code"] == "node.control_unsupported", observed
        assert observed["cause_category"] == "fatal", observed
    else:
        assert observed["type"] == control, observed
        assert observed["code"] == (17 if control == "SystemExit" else None), observed
    assert observed["attempts"] == 1
    assert observed["live_children"] == []


def test_expired_retry_budget_preserves_spend_without_failed_branch(
    tmp_path, ctx, state, monkeypatch
):
    from decimal import Decimal
    from types import SimpleNamespace

    effects = tmp_path / "attempts"

    class Node:
        spec = SimpleNamespace(
            metadata=SimpleNamespace(component_id="actual-costed-retry"),
            state_writes=["params", "budgets"],
        )

        def execute(self, passed_ctx, passed_state):
            with effects.open("a") as stream:
                stream.write("attempt\n")
            passed_state.params["failed_change"] = True
            passed_state.budgets["run_spent_usd"] = Decimal("0.25")
            return _fail_outcome(passed_state)

    monkeypatch.setattr(retry_module, "_can_use_forked_timeout_worker", lambda: False)
    with pytest.raises(NodeTimeoutError):
        execute_with_retry_sync(
            Node(),
            ctx,
            state,
            retry_policy=RetryPolicy(max_retries=2, backoff_base_s=0.1, jitter="none"),
            timeout_s=0.03,
            alias="spent-without-continuation",
        )
    assert effects.read_text().splitlines() == ["attempt"]
    assert state.params == {}
    assert state.budgets["run_spent_usd"] == Decimal("0.25")


@pytest.mark.asyncio
async def test_unbounded_thread_cancellation_revokes_owned_writes_but_cannot_stop_raw_effects(
    tmp_path, ctx, state, monkeypatch
):
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=4)
    monkeypatch.setattr(async_tools, "get_shared_executor", lambda: executor)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    raw = tmp_path / "raw-effect"
    owned = tmp_path / "owned-effect"

    class Store:
        def put_json(self, payload, options):
            owned.write_text("owner write admitted")

    ctx.store = Store()

    class Node:
        def execute(self, passed_ctx, passed_state):
            started.set()
            release.wait(timeout=2)
            raw.write_text("already running arbitrary user effect")
            passed_ctx.store.put_json({}, None)
            finished.set()
            return _ok_outcome(passed_state)

    try:
        task = asyncio.create_task(
            execute_with_retry_async(
                Node(),
                ctx,
                state,
                retry_policy=RetryPolicy(),
                timeout_s=None,
                alias="unbounded-cancel",
            )
        )
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.001)
        assert started.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        assert finished.wait(timeout=2)
        assert raw.read_text() == "already running arbitrary user effect"
        assert not owned.exists()
    finally:
        release.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_completed_provider_error_cannot_emit_retry_after_publication_deadline(tmp_path, state):
    from polisyos.core.trace.record import TraceRecord
    from polisyos.core.trace.sink import JsonlTraceSink
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    trace_path = tmp_path / "trace.jsonl"
    run = RunContext(
        store=MagicMock(),
        trace=JsonlTraceSink(trace_path),
        run_manifest=RunManifest(
            run_id="R_late_error",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64, kind="registry", media_type="application/json"
            ),
        ),
    )
    context = ExecutionContext(store=run.store, run=run, logger=MagicMock())

    class Node:
        async def execute_async(self, passed_ctx, passed_state):
            # The provider finishes on time. Its consumer wakes only after this
            # real event-loop callback has consumed the publication budget.
            asyncio.get_running_loop().call_soon(_time.sleep, 0.04)
            raise ConnectionError("provider completed before blocked delivery")

    with pytest.raises(NodeTimeoutError):
        asyncio.run(
            execute_with_retry_async(
                Node(),
                context,
                state,
                retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1),
                timeout_s=0.01,
                alias="late-error",
            )
        )
    records = (
        [TraceRecord.model_validate_json(line) for line in trace_path.read_text().splitlines()]
        if trace_path.exists()
        else []
    )
    assert [record for record in records if record.event == "NODE_RETRY"] == []


@pytest.mark.parametrize(
    "payload", [{"kind": "unknown"}, {}, {"kind": "SystemExit", "code": {"opaque": True}}]
)
def test_real_framed_control_reject_is_typed_terminal(payload):
    channel = retry_module._WorkerResultChannel(mp.get_context("fork"))
    try:
        channel.put(("control", payload))
        status, received = channel.get(timeout=0.1)
        assert status == "control"
        error = retry_module._worker_control_error(received)
        assert isinstance(error, RuntimeError)
        assert error.category == "fatal"
        assert error.code == "node.control_protocol"
        assert (
            retry_module._should_retry_exception(
                error, RetryPolicy(max_retries=1, retry_on=["node.control_protocol"])
            )
            is False
        )
    finally:
        channel.close()
