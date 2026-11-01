"""Behavioral checks for blocking-call completion and event-loop delivery."""

from __future__ import annotations

import asyncio
import threading
import time
from contextvars import ContextVar

import pytest

from polisyos.common import async_tools
from polisyos.common.async_tools import run_blocking_async


async def _wait_for_thread_event(event: threading.Event, *, timeout: float = 2.0) -> None:
    """Wait for a real worker-thread event without blocking the event loop."""
    deadline = asyncio.get_running_loop().time() + timeout
    while not event.is_set():
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("worker event did not arrive")
        await asyncio.sleep(0.001)


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["blocking_helper", "completion_handle"])
async def test_completed_shared_work_does_not_block_loop_during_saturated_delivery(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
) -> None:
    """Completion registration must not wait for an unrelated occupied worker."""
    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    original_submit = executor.submit
    started = threading.Event()
    release = threading.Event()
    heartbeat = threading.Event()
    forced_release = threading.Event()
    calls: list[str] = []
    blocker_future = None

    def work() -> int:
        calls.append("work")
        return 42

    def block() -> None:
        started.set()
        assert release.wait(timeout=3)

    def occupy_after_completion() -> None:
        nonlocal blocker_future
        with executor._capacity_changed:
            assert executor._capacity_changed.wait_for(lambda: executor._outstanding_jobs == 0, 2)
        blocker_future = original_submit(block)
        assert started.wait(timeout=2)

    def watchdog() -> None:
        if not heartbeat.wait(timeout=0.5):
            forced_release.set()
            release.set()

    if route == "completion_handle":
        handle = executor.submit_cancellable(work)
        assert handle.result(timeout=2).value == 42
        occupy_after_completion()
    else:
        submitted = False

        def complete_before_return(fn, /, *args, **kwargs):
            nonlocal submitted
            result = original_submit(fn, *args, **kwargs)
            if not submitted:
                submitted = True
                result.result(timeout=2)
                occupy_after_completion()
            return result

        monkeypatch.setattr(executor, "submit", complete_before_return)

    watcher = threading.Thread(target=watchdog)
    watcher.start()
    asyncio.get_running_loop().call_soon(heartbeat.set)
    try:
        if route == "completion_handle":
            result = await handle.result_async(timeout=2)
            assert result.status == "completed" and result.value == 42
        else:
            assert await run_blocking_async(work, timeout_seconds=2) == 42
        assert heartbeat.is_set() and not forced_release.is_set()
        assert not release.is_set() and calls == ["work"]
        with executor._admission_lock:
            assert executor._physical_workers == 1 and executor._outstanding_jobs == 1
    finally:
        release.set()
        watcher.join(timeout=2)
        if blocker_future is not None:
            blocker_future.result(timeout=2)
        executor.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
async def test_blocking_helper_deadline_includes_pre_admission_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A consumed invocation budget cannot start the callable with a new deadline."""
    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    calls: list[str] = []
    delay = threading.Event()

    def delayed_executor():
        delay.wait(timeout=0.12)
        return executor

    monkeypatch.setattr(async_tools, "_get_shared_executor", delayed_executor)
    try:
        with pytest.raises(TimeoutError, match="Blocking call did not complete within"):
            await run_blocking_async(calls.append, "must-not-start", timeout_seconds=0.03)
        assert calls == []
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "route", ["helper_cancel", "helper_timeout", "handle_cancel", "handle_timeout"]
)
async def test_async_cancellation_routes_do_not_wait_for_queued_user_callbacks(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
) -> None:
    """Cancellation and timeout return while a queued source's worker is occupied."""
    executor = async_tools._SharedExecutor(max_workers=1, max_queued=1)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    started = threading.Event()
    release = threading.Event()
    heartbeat = threading.Event()
    forced_release = threading.Event()
    callback_finished = threading.Event()
    calls: list[str] = []
    sources = []

    def block() -> None:
        started.set()
        assert release.wait(timeout=3)

    def user_callback(_future) -> None:
        calls.append("callback")
        callback_finished.set()

    def watchdog() -> None:
        if not heartbeat.wait(timeout=0.5):
            forced_release.set()
            release.set()

    running = executor.submit(block)
    assert started.wait(timeout=2)
    is_timeout = route.endswith("timeout")
    if route.startswith("handle"):
        handle = executor.submit_cancellable(lambda: calls.append("must-not-run"))
        source = handle._future
        source.add_done_callback(user_callback)
        task = asyncio.create_task(handle.result_async(timeout=0.03 if is_timeout else 2))
    else:
        original_submit = executor.submit

        def attach_before_return(fn, /, *args, **kwargs):
            source = original_submit(fn, *args, **kwargs)
            source.add_done_callback(user_callback)
            sources.append(source)
            return source

        monkeypatch.setattr(executor, "submit", attach_before_return)
        task = asyncio.create_task(
            run_blocking_async(
                calls.append, "must-not-run", timeout_seconds=0.03 if is_timeout else 2
            )
        )
    await asyncio.sleep(0)
    if not route.startswith("handle"):
        assert len(sources) == 1
        source = sources[0]
    assert not source.done()
    watcher = threading.Thread(target=watchdog)
    watcher.start()
    try:
        if is_timeout:
            asyncio.get_running_loop().call_later(0.08, heartbeat.set)
            with pytest.raises(TimeoutError):
                await task
        else:
            task.cancel()
            asyncio.get_running_loop().call_soon(heartbeat.set)
            with pytest.raises(asyncio.CancelledError):
                await task
        await asyncio.sleep(0.1)
        assert heartbeat.is_set() and not forced_release.is_set()
        assert not release.is_set() and calls == []
        with executor._admission_lock:
            assert executor._physical_workers == 1 and executor._outstanding_jobs == 2
    finally:
        release.set()
        watcher.join(timeout=2)
        running.result(timeout=2)
        assert callback_finished.wait(timeout=2)
        executor.shutdown(wait=True, cancel_futures=True)
    assert source.cancelled() and calls == ["callback"]
    assert executor._outstanding_jobs == 0


@pytest.mark.asyncio
async def test_completed_work_survives_delayed_future_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timely callable result is not lost when Future delivery arrives late."""
    loop = asyncio.get_running_loop()
    executor = async_tools._SharedExecutor(max_workers=1)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    await run_blocking_async(lambda: "warm", timeout_seconds=1.0)
    original_call_soon_threadsafe = loop.call_soon_threadsafe
    worker_started = threading.Event()
    worker_finished = threading.Event()
    callback_intercepted = threading.Event()
    delivery_scheduled = asyncio.Event()
    delivery_attempted = asyncio.Event()
    worker_finished_at: list[float] = []
    returned_at: list[float] = []
    budget_s = 0.15
    worker_delay_s = 0.02
    delivery_delay_s = 0.30
    started_at = time.monotonic()

    def delay_future_delivery(callback, *args, context=None):
        if (
            not callback_intercepted.is_set()
            and getattr(callback, "__name__", "") == "_set_state"
            and threading.current_thread() is not threading.main_thread()
        ):
            callback_intercepted.set()

            def schedule_delivery() -> None:
                delivery_scheduled.set()

                def deliver() -> None:
                    delivery_attempted.set()
                    callback(*args)

                loop.call_later(delivery_delay_s, deliver, context=context)

            return original_call_soon_threadsafe(schedule_delivery, context=context)
        return original_call_soon_threadsafe(callback, *args, context=context)

    loop.call_soon_threadsafe = delay_future_delivery

    def work() -> str:
        worker_started.set()
        time.sleep(worker_delay_s)
        worker_finished_at.append(time.monotonic())
        worker_finished.set()
        return "computed-before-deadline"

    try:
        try:
            result = await asyncio.wait_for(
                run_blocking_async(work, timeout_seconds=budget_s),
                timeout=budget_s + 0.1,
            )
            returned_at.append(time.monotonic())
        finally:
            loop.call_soon_threadsafe = original_call_soon_threadsafe

        assert result == "computed-before-deadline"
        assert worker_started.is_set()
        assert worker_finished.is_set()
        assert callback_intercepted.is_set()
        assert worker_finished_at[0] - started_at < budget_s
        assert returned_at[0] - started_at < budget_s + 0.1
        await asyncio.wait_for(delivery_scheduled.wait(), timeout=0.2)
        await asyncio.wait_for(delivery_attempted.wait(), timeout=0.5)
        assert time.monotonic() - started_at > budget_s
    finally:
        loop.call_soon_threadsafe = original_call_soon_threadsafe
        executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_real_running_work_can_finish_after_timeout_without_being_claimed_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A helper timeout does not pretend to preempt a running thread callable."""
    executor = async_tools._SharedExecutor(max_workers=1)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    finished_at: list[float] = []

    def work() -> str:
        started.set()
        release.wait(timeout=2.0)
        finished_at.append(time.monotonic())
        finished.set()
        return "completed-after-refusal"

    task = asyncio.create_task(run_blocking_async(work, timeout_seconds=0.04))
    try:
        await _wait_for_thread_event(started)
        with pytest.raises(TimeoutError, match="Blocking call did not complete within"):
            await task
        refused_at = time.monotonic()
        assert not finished.is_set()
        release.set()
        await _wait_for_thread_event(finished)
        assert finished_at[0] > refused_at
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_timeout_cancels_unstarted_work_in_shared_executor_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real shared-executor class removes queued work on helper timeout."""
    executor = async_tools._SharedExecutor(max_workers=1)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    blocker_started = threading.Event()
    release_blocker = threading.Event()
    queued_calls: list[str] = []

    def blocker() -> None:
        blocker_started.set()
        release_blocker.wait(timeout=2.0)

    blocker_future = executor.submit(blocker)
    try:
        await _wait_for_thread_event(blocker_started)
        with pytest.raises(TimeoutError, match="Blocking call did not complete within"):
            await run_blocking_async(queued_calls.append, "must-not-run", timeout_seconds=0.04)
    finally:
        release_blocker.set()
        try:
            blocker_future.result(timeout=2.0)
        finally:
            executor.shutdown(wait=True)

    assert queued_calls == []
    assert executor._outstanding_jobs == 0


@pytest.mark.asyncio
async def test_success_preserves_arguments_kwargs_and_captured_context() -> None:
    """The worker still receives its call arguments and submit-time context."""
    owner_context: ContextVar[str] = ContextVar("blocking_owner_context", default="unset")
    token = owner_context.set("owner-value")
    try:
        result = await run_blocking_async(
            lambda first, *, second: (first, second, owner_context.get()),
            "one",
            second="two",
            timeout_seconds=1.0,
        )
    finally:
        owner_context.reset(token)

    assert result == ("one", "two", "owner-value")


@pytest.mark.asyncio
async def test_callable_timeout_exception_is_preserved() -> None:
    """A timely worker TimeoutError keeps its original exception message."""

    def work() -> None:
        raise TimeoutError("inner worker timeout")

    with pytest.raises(TimeoutError, match=r"^inner worker timeout$"):
        await run_blocking_async(work, timeout_seconds=1.0)


@pytest.mark.asyncio
async def test_caller_cancellation_cancels_queued_shared_executor_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caller cancellation removes a queued callable before its worker starts."""
    executor = async_tools._SharedExecutor(max_workers=1)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    blocker_started = threading.Event()
    release_blocker = threading.Event()
    queued_calls: list[str] = []

    def blocker() -> None:
        blocker_started.set()
        release_blocker.wait(timeout=2.0)

    blocker_future = executor.submit(blocker)
    try:
        await _wait_for_thread_event(blocker_started)
        task = asyncio.create_task(
            run_blocking_async(queued_calls.append, "must-not-run", timeout_seconds=1.0)
        )
        deadline = asyncio.get_running_loop().time() + 0.5
        while executor._outstanding_jobs < 2:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError("queued helper submission was not admitted")
            await asyncio.sleep(0.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release_blocker.set()
        try:
            blocker_future.result(timeout=2.0)
        finally:
            executor.shutdown(wait=True)

    assert queued_calls == []
    assert executor._outstanding_jobs == 0


@pytest.mark.asyncio
async def test_cpython_overdue_wait_timeout_rejects_late_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CPython overdue-timeout path rejects work completed after its deadline."""
    loop = asyncio.get_running_loop()
    executor = async_tools._SharedExecutor(max_workers=1)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    await run_blocking_async(lambda: "warm", timeout_seconds=1.0)
    original_call_soon_threadsafe = loop.call_soon_threadsafe
    worker_started = threading.Event()
    worker_finished = threading.Event()
    future_delivery_queued = threading.Event()
    worker_finished_at: list[float] = []
    budget_s = 0.08
    work_delay_s = 0.15
    loop_block_s = 0.32
    started_at = time.monotonic()

    def observe_future_delivery(callback, *args, context=None):
        if (
            getattr(callback, "__name__", "") == "_set_state"
            and threading.current_thread() is not threading.main_thread()
        ):
            result = original_call_soon_threadsafe(callback, *args, context=context)
            future_delivery_queued.set()
            return result
        return original_call_soon_threadsafe(callback, *args, context=context)

    loop.call_soon_threadsafe = observe_future_delivery

    def work() -> str:
        worker_started.set()
        time.sleep(work_delay_s)
        worker_finished_at.append(time.monotonic())
        worker_finished.set()
        return "finished-after-deadline"

    task = asyncio.create_task(run_blocking_async(work, timeout_seconds=budget_s))
    try:
        await _wait_for_thread_event(worker_started)
        # This exercises CPython's overdue wait-timeout path, not the helper's
        # post-await normal-return timestamp guard. The real worker queues its
        # wrapped-Future callback after its deadline before the loop resumes.
        time.sleep(loop_block_s)
        assert future_delivery_queued.is_set()
        assert worker_finished.is_set()
        assert worker_finished_at[0] > started_at + budget_s
        with pytest.raises(TimeoutError, match="Blocking call did not complete within"):
            await task
    finally:
        loop.call_soon_threadsafe = original_call_soon_threadsafe
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_timely_non_timeout_error_survives_delayed_future_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timely worker error keeps its original type and message after delay."""
    loop = asyncio.get_running_loop()
    executor = async_tools._SharedExecutor(max_workers=1)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    await run_blocking_async(lambda: "warm", timeout_seconds=1.0)
    original_call_soon_threadsafe = loop.call_soon_threadsafe
    worker_started = threading.Event()
    worker_finished = threading.Event()
    callback_intercepted = threading.Event()
    delivery_scheduled = asyncio.Event()
    delivery_attempted = asyncio.Event()
    worker_finished_at: list[float] = []
    budget_s = 0.15
    worker_delay_s = 0.02
    delivery_delay_s = 0.30
    started_at = time.monotonic()

    def delay_future_delivery(callback, *args, context=None):
        if (
            not callback_intercepted.is_set()
            and getattr(callback, "__name__", "") == "_set_state"
            and threading.current_thread() is not threading.main_thread()
        ):
            callback_intercepted.set()

            def schedule_delivery() -> None:
                delivery_scheduled.set()

                def deliver() -> None:
                    delivery_attempted.set()
                    callback(*args)

                loop.call_later(delivery_delay_s, deliver, context=context)

            return original_call_soon_threadsafe(schedule_delivery, context=context)
        return original_call_soon_threadsafe(callback, *args, context=context)

    loop.call_soon_threadsafe = delay_future_delivery

    def work() -> str:
        worker_started.set()
        time.sleep(worker_delay_s)
        worker_finished_at.append(time.monotonic())
        worker_finished.set()
        raise ValueError("original worker failure")

    try:
        with pytest.raises(ValueError, match=r"^original worker failure$"):
            await run_blocking_async(work, timeout_seconds=budget_s)
    finally:
        loop.call_soon_threadsafe = original_call_soon_threadsafe
        executor.shutdown(wait=True)

    assert worker_started.is_set()
    assert worker_finished.is_set()
    assert callback_intercepted.is_set()
    assert worker_finished_at[0] - started_at < budget_s
    await asyncio.wait_for(delivery_scheduled.wait(), timeout=0.2)
    await asyncio.wait_for(delivery_attempted.wait(), timeout=0.5)
