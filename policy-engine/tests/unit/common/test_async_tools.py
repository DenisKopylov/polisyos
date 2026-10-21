from __future__ import annotations

import asyncio
import concurrent.futures
import gc
import subprocess
import sys
import threading
import time
import weakref
from collections.abc import Iterator
from contextvars import ContextVar
from typing import get_type_hints

import pytest

from polisyos.common.async_tools import (
    get_shared_executor,
    run_blocking_async,
    run_coro_sync,
    run_shared_executor_sync,
)


def test_function_type_parameters_resolve_without_module_typevar() -> None:
    """All four helpers resolve their own generic identities after cleanup."""
    from collections.abc import Awaitable, Callable

    from polisyos.common import async_tools

    helpers = (
        async_tools._await_awaitable,
        async_tools._run_coro_in_fresh_loop,
        async_tools.run_coro_sync,
        async_tools.run_blocking_async,
    )
    for helper in helpers:
        (parameter,) = helper.__type_params__
        hints = get_type_hints(
            helper,
            globalns={**vars(async_tools), "Awaitable": Awaitable, "Callable": Callable},
            localns={"T": parameter},
        )
        assert hints["return"] is parameter
    assert len({helper.__type_params__[0] for helper in helpers}) == 4
    assert not hasattr(async_tools, "T")
    assert not hasattr(async_tools, "TypeVar")


def test_shared_executor_queue_is_finite_fifo_and_queued_cancel_never_starts() -> None:
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=1, max_queued=1)
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    first = executor.submit_cancellable(
        lambda: (first_started.set(), release_first.wait(timeout=3), "first")[2]
    )
    assert first_started.wait(timeout=2)
    second = executor.submit_cancellable(lambda: (second_started.set(), "second")[1])

    with pytest.raises(async_tools.SharedExecutorBackpressureError) as raised:
        executor.submit_cancellable(lambda: "third")
    assert raised.value.retryable is True
    assert raised.value.code == "shared_executor_queue_full"
    assert raised.value.queue_capacity == 1
    assert second.cancel() is True
    with pytest.raises(async_tools.SharedExecutorBackpressureError):
        executor.submit_cancellable(lambda: "hidden-tombstone-overflow")

    release_first.set()
    first_completion = first.result(timeout=2)
    assert first_completion.status == "completed"
    assert first_completion.value == "first"
    with pytest.raises(concurrent.futures.CancelledError):
        second.result(timeout=0.1)

    # Cancellation leaves a bounded reservation until the cancelled queue
    # tombstone is dequeued, so repeated cancel/submit cannot hide queue growth.
    deadline = time.monotonic() + 2
    third = None
    while time.monotonic() < deadline:
        try:
            third = executor.submit_cancellable(lambda: "third")
            break
        except async_tools.SharedExecutorBackpressureError:
            time.sleep(0.005)
    assert third is not None
    assert third.result(timeout=2).value == "third"
    assert second_started.is_set() is False
    executor.shutdown(wait=True, cancel_futures=True)


def test_shared_executor_runs_queued_jobs_in_fifo_order() -> None:
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=1, max_queued=2)
    first_started = threading.Event()
    release_first = threading.Event()
    execution_order: list[str] = []

    def first_job() -> str:
        first_started.set()
        release_first.wait(timeout=3)
        execution_order.append("first")
        return "first"

    first = executor.submit_cancellable(first_job)
    assert first_started.wait(timeout=2)
    second = executor.submit_cancellable(lambda: (execution_order.append("second"), "second")[1])
    third = executor.submit_cancellable(lambda: (execution_order.append("third"), "third")[1])
    try:
        release_first.set()
        assert first.result(timeout=2).value == "first"
        assert second.result(timeout=2).value == "second"
        assert third.result(timeout=2).value == "third"
        assert execution_order == ["first", "second", "third"]
    finally:
        release_first.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_running_shared_handle_timeout_retains_physical_slot_until_worker_returns() -> None:
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    started = threading.Event()
    release = threading.Event()
    running = executor.submit_cancellable(
        lambda: (started.set(), release.wait(timeout=3), "done")[2]
    )
    assert started.wait(timeout=2)

    with pytest.raises(async_tools.SharedExecutorWaitTimeoutError) as raised:
        running.result(timeout=0.01)
    assert raised.value.cancelled_before_start is False
    assert raised.value.running_slot_retained is True
    assert raised.value.retryable is False
    with pytest.raises(async_tools.SharedExecutorBackpressureError):
        executor.submit_cancellable(lambda: "must-wait")

    release.set()
    assert running.result(timeout=2).value == "done"
    executor.shutdown(wait=True, cancel_futures=True)


def test_async_shared_handle_timeout_keeps_running_worker_slot() -> None:
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    started = threading.Event()
    release = threading.Event()
    running = executor.submit_cancellable(
        lambda: (started.set(), release.wait(timeout=3), "done")[2]
    )
    assert started.wait(timeout=2)

    async def _wait_then_check_capacity() -> None:
        with pytest.raises(async_tools.SharedExecutorWaitTimeoutError) as raised:
            await running.result_async(timeout=0.01)
        assert raised.value.running_slot_retained is True
        assert raised.value.retryable is False
        with pytest.raises(async_tools.SharedExecutorBackpressureError):
            executor.submit_cancellable(lambda: "must-wait")

    try:
        asyncio.run(_wait_then_check_capacity())
        release.set()
        assert running.result(timeout=2).value == "done"
    finally:
        release.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_queued_shared_handle_timeout_is_retryable_after_cancel_before_start() -> None:
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=1, max_queued=1)
    started = threading.Event()
    release = threading.Event()
    first = executor.submit_cancellable(
        lambda: (started.set(), release.wait(timeout=3), "first")[2]
    )
    assert started.wait(timeout=2)
    queued_started = threading.Event()
    queued = executor.submit_cancellable(lambda: queued_started.set())

    with pytest.raises(async_tools.SharedExecutorWaitTimeoutError) as raised:
        queued.result(timeout=0.01)
    assert raised.value.cancelled_before_start is True
    assert raised.value.running_slot_retained is False
    assert raised.value.retryable is True
    release.set()
    assert first.result(timeout=2).value == "first"
    with pytest.raises(concurrent.futures.CancelledError):
        queued.result(timeout=0.1)
    assert queued_started.is_set() is False
    executor.shutdown(wait=True, cancel_futures=True)


def test_cancellable_completion_drops_exception_traceback_and_array_arguments() -> None:
    import numpy as np

    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    large_array = np.ones(250_000, dtype=np.float64)
    array_ref = weakref.ref(large_array)

    class _FailWithArrayFrame:
        def __init__(self, payload: np.ndarray) -> None:
            self.payload = payload

        def __call__(self) -> None:
            raise ValueError("bounded failure", self.payload)

    fail_with_array_frame = _FailWithArrayFrame(large_array)

    handle = executor.submit_cancellable(fail_with_array_frame)
    del large_array
    del fail_with_array_frame

    completion = handle.result(timeout=2)
    executor.shutdown(wait=True, cancel_futures=True)
    gc.collect()
    assert completion.status == "failed"
    assert completion.failure is not None
    assert completion.failure.exception_type.endswith("ValueError")
    assert completion.failure.message_excerpt == "bounded failure"
    assert array_ref() is None


def test_run_coro_sync_returns_result_without_running_loop() -> None:
    assert run_coro_sync(asyncio.sleep(0, result=7)) == 7


def test_run_coro_sync_works_inside_running_loop() -> None:
    async def _wrapper() -> int:
        return run_coro_sync(asyncio.sleep(0.01, result=11))

    assert asyncio.run(_wrapper()) == 11


def test_run_coro_sync_preserves_context_inside_running_loop() -> None:
    owner_scope: ContextVar[str | None] = ContextVar("owner_scope", default=None)

    async def _read_scope() -> str | None:
        return owner_scope.get()

    async def _wrapper() -> str | None:
        token = owner_scope.set("tenant-owner")
        try:
            return run_coro_sync(_read_scope())
        finally:
            owner_scope.reset(token)

    assert asyncio.run(_wrapper()) == "tenant-owner"


def test_run_coro_sync_times_out_instead_of_hanging() -> None:
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="did not complete within"):
        run_coro_sync(asyncio.sleep(1), timeout_seconds=0.05)
    assert time.monotonic() - started < 0.5


def test_run_blocking_async_keeps_event_loop_responsive() -> None:
    async def _exercise() -> bool:
        ticked = False

        async def _ticker() -> None:
            nonlocal ticked
            await asyncio.sleep(0.01)
            ticked = True

        ticker = asyncio.create_task(_ticker())
        await run_blocking_async(time.sleep, 0.05)
        await ticker
        return ticked

    assert run_coro_sync(_exercise()) is True


def test_run_blocking_async_times_out() -> None:
    async def _exercise() -> None:
        await run_blocking_async(time.sleep, 1.0, timeout_seconds=0.05)

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="Blocking call did not complete within"):
        run_coro_sync(_exercise())
    assert time.monotonic() - started < 0.5


def test_run_blocking_async_preserves_inner_timeout_message() -> None:
    def _raise_inner_timeout() -> None:
        raise TimeoutError("inner worker timeout")

    async def _exercise() -> None:
        await run_blocking_async(_raise_inner_timeout, timeout_seconds=5.0)

    with pytest.raises(TimeoutError, match=r"^inner worker timeout$"):
        asyncio.run(_exercise())


def test_shared_executor_uses_one_explicit_candidate_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    profile = async_tools.SharedExecutorProfile(capacity=2, revision="r4-test-profile-v1")
    async_tools.configure_shared_executor_profile(profile)

    executor = async_tools.get_shared_executor()
    try:
        assert executor._max_workers == 2
        assert async_tools.get_shared_executor_profile() == profile
        assert profile.authority == "candidate"
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_shared_executor_rejects_a_conflicting_second_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    first = async_tools.SharedExecutorProfile(capacity=1, revision="profile-a")
    second = async_tools.SharedExecutorProfile(capacity=2, revision="profile-b")

    async_tools.configure_shared_executor_profile(first)
    executor = async_tools.get_shared_executor()
    try:
        with pytest.raises(async_tools.SharedExecutorConfigurationError, match="profile_conflict"):
            async_tools.configure_shared_executor_profile(second)

        assert async_tools.get_shared_executor_profile() == first
        assert async_tools.get_shared_executor() is executor
        assert executor._max_workers == 1
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_shared_executor_rejects_live_queue_capacity_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    first = async_tools.SharedExecutorProfile(
        capacity=1,
        revision="queue-capacity-fixed-v1",
        queue_capacity=0,
    )
    second = async_tools.SharedExecutorProfile(
        capacity=1,
        revision="queue-capacity-fixed-v1",
        queue_capacity=1,
    )
    async_tools.configure_shared_executor_profile(first)
    executor = async_tools.get_shared_executor()
    try:
        with pytest.raises(async_tools.SharedExecutorConfigurationError):
            async_tools.configure_shared_executor_profile(second)
        assert executor._max_workers == 1
        assert executor._max_queued == 0
        assert async_tools.get_shared_executor_profile() == first
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_legacy_shared_executor_profile_is_candidate_only_and_host_derived(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools.os, "cpu_count", lambda: 8)
    profile = async_tools.resolve_shared_executor_profile()

    assert profile.capacity == 8
    assert profile.revision == "legacy-host-derived-v1"
    assert profile.source == "legacy_host_fallback"
    assert profile.authority == "candidate"


def test_reading_fallback_profile_does_not_pin_it_before_runtime_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    monkeypatch.setattr(async_tools.os, "cpu_count", lambda: 8)

    fallback = async_tools.get_shared_executor_profile()
    explicit = async_tools.SharedExecutorProfile(capacity=2, revision="runtime-config-v1")
    async_tools.configure_shared_executor_profile(explicit)

    assert fallback.source == "legacy_host_fallback"
    assert async_tools.get_shared_executor_profile() == explicit


@pytest.mark.parametrize("capacity", [0, -1, 1.5, True])
def test_shared_executor_profile_requires_a_positive_integer_capacity(capacity: object) -> None:
    from polisyos.common import async_tools

    with pytest.raises(async_tools.SharedExecutorConfigurationError, match="capacity"):
        async_tools.SharedExecutorProfile(
            capacity=capacity,  # type: ignore[arg-type]
            revision="invalid-capacity-test",
        )


def test_nested_sync_method_dispatch_runs_inline_on_the_current_shared_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    profile = async_tools.SharedExecutorProfile(capacity=1, revision="inline-r4-test")
    async_tools.configure_shared_executor_profile(profile)
    executor = async_tools.get_shared_executor()
    try:
        assert not async_tools.is_current_shared_executor_worker()

        def _nested_identity() -> tuple[int, int]:
            assert async_tools.is_current_shared_executor_worker()
            outer_thread = threading.get_ident()
            inner_thread = async_tools.run_shared_executor_sync(threading.get_ident)
            return outer_thread, inner_thread

        outer_and_inner = executor.submit(_nested_identity)

        outer_thread, inner_thread = outer_and_inner.result(timeout=2)
        assert inner_thread == outer_thread
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_precompletion_callback_at_capacity_one_keeps_and_uses_owner_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-registered callback runs before the worker releases its only slot."""
    from polisyos.common import async_tools

    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", executor)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    work_started = threading.Event()
    release_work = threading.Event()
    callback_started = threading.Event()
    release_callback = threading.Event()
    callback_finished = threading.Event()
    worker_threads: list[int] = []
    callback_worker_flags: list[bool] = []
    nested_threads: list[int] = []

    def work() -> int:
        worker_threads.append(threading.get_ident())
        work_started.set()
        assert release_work.wait(timeout=3)
        return 7

    future = executor.submit(work)
    assert work_started.wait(timeout=2)

    def callback(completed: concurrent.futures.Future[int]) -> None:
        callback_worker_flags.append(async_tools.is_current_shared_executor_worker())
        assert completed.result() == 7
        nested_threads.append(async_tools.run_shared_executor_sync(threading.get_ident))
        callback_started.set()
        assert release_callback.wait(timeout=3)
        callback_finished.set()

    future.add_done_callback(callback)
    try:
        release_work.set()
        assert callback_started.wait(timeout=2)
        assert future.result(timeout=1) == 7
        assert callback_worker_flags == [True]
        assert nested_threads == worker_threads
        with pytest.raises(async_tools.SharedExecutorBackpressureError):
            executor.submit(lambda: 9)
    finally:
        release_work.set()
        release_callback.set()

    assert callback_finished.wait(timeout=2)
    deadline = time.monotonic() + 2
    followup = None
    while time.monotonic() < deadline:
        try:
            followup = executor.submit(lambda: 11)
            break
        except async_tools.SharedExecutorBackpressureError:
            time.sleep(0.005)
    try:
        assert followup is not None
        assert followup.result(timeout=2) == 11
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


@pytest.mark.parametrize("capacity", [1, 2])
def test_late_callback_body_runs_on_bounded_owner_workers_and_preserves_context(
    monkeypatch: pytest.MonkeyPatch,
    capacity: int,
) -> None:
    """Concurrent late callback bodies run under the owner physical capacity."""
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_SHUTDOWN", False, raising=False)
    async_tools.configure_shared_executor_profile(
        async_tools.SharedExecutorProfile(
            capacity=capacity,
            revision=f"late-callback-capacity-{capacity}",
            queue_capacity=capacity,
        )
    )
    executor = get_shared_executor()
    completed = executor.submit(lambda: "already-complete")
    assert completed.result(timeout=2) == "already-complete"

    owner_scope: ContextVar[str | None] = ContextVar(
        f"late_callback_owner_{capacity}", default=None
    )
    dispatch_release = threading.Event()
    dispatch_condition = threading.Condition()
    active_callbacks = 0
    peak_callbacks = 0
    callbacks_started = 0
    callback_worker_flags: list[bool] = []
    dispatch_worker_flags: list[bool] = []
    results: list[str | None] = []
    errors: list[BaseException] = []

    def dispatch() -> str | None:
        dispatch_worker_flags.append(async_tools.is_current_shared_executor_worker())
        return owner_scope.get()

    def callback(future: concurrent.futures.Future[str]) -> None:
        nonlocal active_callbacks, callbacks_started, peak_callbacks
        try:
            assert future.result() == "already-complete"
            callback_worker_flags.append(async_tools.is_current_shared_executor_worker())
            with dispatch_condition:
                active_callbacks += 1
                callbacks_started += 1
                peak_callbacks = max(peak_callbacks, active_callbacks)
                dispatch_condition.notify_all()
            if not dispatch_release.wait(timeout=3):
                raise TimeoutError("test callback release was not signalled")
            results.append(run_shared_executor_sync(dispatch))
        except BaseException as exc:
            errors.append(exc)
        finally:
            with dispatch_condition:
                active_callbacks -= 1
                dispatch_condition.notify_all()

    def register_late_callback(owner: str) -> None:
        token = owner_scope.set(owner)
        try:
            completed.add_done_callback(callback)
        finally:
            owner_scope.reset(token)

    registrar_count = capacity * 2
    registrars = [
        threading.Thread(target=register_late_callback, args=(f"tenant-{index}",))
        for index in range(registrar_count)
    ]
    try:
        for registrar in registrars:
            registrar.start()
        with dispatch_condition:
            assert dispatch_condition.wait_for(lambda: callbacks_started >= capacity, timeout=2)
            observed_peak_while_blocked = peak_callbacks
            assert active_callbacks == capacity
            assert callbacks_started == capacity
        dispatch_release.set()
        for registrar in registrars:
            registrar.join(timeout=3)

        assert all(not registrar.is_alive() for registrar in registrars)
        assert callbacks_started == registrar_count
        assert observed_peak_while_blocked == capacity
        assert peak_callbacks == capacity
        assert callback_worker_flags == [True] * registrar_count
        assert dispatch_worker_flags == [True] * registrar_count
        assert sorted(results) == [f"tenant-{index}" for index in range(registrar_count)]
        assert errors == []
    finally:
        dispatch_release.set()
        for registrar in registrars:
            if registrar.ident is not None:
                registrar.join(timeout=3)


def test_shutdown_from_worker_runs_cancel_callback_inline_without_child_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A worker-triggered drain invokes queued callbacks inline on its owner slot."""
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_SHUTDOWN", False, raising=False)
    async_tools.configure_shared_executor_profile(
        async_tools.SharedExecutorProfile(
            capacity=1,
            revision="worker-shutdown-callback-r4-test",
            queue_capacity=1,
        )
    )
    executor = get_shared_executor()
    allow_shutdown = threading.Event()
    worker_started = threading.Event()
    callback_done = threading.Event()
    callback_worker_flags: list[bool] = []
    nested_thread_ids: list[tuple[int, int]] = []
    submit_errors: list[str] = []
    should_not_run: list[bool] = []

    def shutdown_from_worker() -> None:
        worker_started.set()
        assert allow_shutdown.wait(timeout=2)
        executor.shutdown(wait=False, cancel_futures=True)

    shutdown_work = executor.submit(shutdown_from_worker)
    assert worker_started.wait(timeout=2)
    queued = executor.submit(should_not_run.append, True)

    def cancelled_callback(future: concurrent.futures.Future[None]) -> None:
        assert future.cancelled()
        callback_worker_flags.append(async_tools.is_current_shared_executor_worker())
        current_thread = threading.get_ident()
        nested_thread_ids.append(
            (current_thread, async_tools.run_shared_executor_sync(threading.get_ident))
        )
        try:
            executor.submit(lambda: None)
        except RuntimeError as exc:
            submit_errors.append(type(exc).__name__)
        callback_done.set()

    queued.add_done_callback(cancelled_callback)
    allow_shutdown.set()
    try:
        shutdown_work.result(timeout=3)
        assert callback_done.wait(timeout=2)
        assert queued.cancelled()
        assert callback_worker_flags == [True]
        assert nested_thread_ids[0][0] == nested_thread_ids[0][1]
        assert submit_errors == ["RuntimeError"]
        assert should_not_run == []
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        executor.shutdown(wait=True, cancel_futures=True)


@pytest.mark.parametrize("capacity", [1, 2])
def test_after_shutdown_late_callback_bodies_share_draining_physical_slot_guard(
    monkeypatch: pytest.MonkeyPatch,
    capacity: int,
) -> None:
    """Callbacks registered after shutdown remain inside the shared slot cap."""
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_SHUTDOWN", False, raising=False)
    async_tools.configure_shared_executor_profile(
        async_tools.SharedExecutorProfile(
            capacity=capacity,
            revision=f"after-shutdown-callback-capacity-{capacity}",
            queue_capacity=capacity,
        )
    )
    executor = get_shared_executor()
    completed = executor.submit(lambda: "already-complete")
    assert completed.result(timeout=2) == "already-complete"
    executor.shutdown(wait=True)

    registration_count = capacity * 2
    release = threading.Event()
    condition = threading.Condition()
    active = 0
    peak = 0
    callbacks_started = 0
    callback_owner_flags: list[bool] = []
    registrar_threads: list[int] = []
    errors: list[BaseException] = []

    def callback(future: concurrent.futures.Future[str]) -> None:
        nonlocal active, callbacks_started, peak
        try:
            assert future.result() == "already-complete"
            callback_owner_flags.append(async_tools.is_current_shared_executor_worker())
            with condition:
                active += 1
                callbacks_started += 1
                peak = max(peak, active)
                condition.notify_all()
            if not release.wait(timeout=3):
                raise TimeoutError("shutdown callback release was not signalled")
            callback_thread = threading.get_ident()
            assert async_tools.run_shared_executor_sync(threading.get_ident) == callback_thread
        except BaseException as exc:
            errors.append(exc)
        finally:
            with condition:
                active -= 1
                condition.notify_all()

    def register() -> None:
        registrar_threads.append(threading.get_ident())
        completed.add_done_callback(callback)

    registrars = [threading.Thread(target=register) for _ in range(registration_count)]
    try:
        for registrar in registrars:
            registrar.start()
        with condition:
            assert condition.wait_for(lambda: callbacks_started >= capacity, timeout=2)
            observed_peak = peak
            assert active == capacity
            assert callbacks_started == capacity
        release.set()
        for registrar in registrars:
            registrar.join(timeout=3)
        assert all(not registrar.is_alive() for registrar in registrars)
        assert callbacks_started == registration_count
        assert observed_peak == capacity
        assert peak == capacity
        # The callback remains on its registering thread after shutdown, while
        # the active physical slot guard prevents callback-body overcommit.
        assert callback_owner_flags == [False] * registration_count
        assert errors == []
    finally:
        release.set()
        for registrar in registrars:
            if registrar.ident is not None:
                registrar.join(timeout=3)


def test_late_callback_body_backpressure_error_does_not_retry_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A callback's own backpressure exception is delivered after one invocation."""
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_SHUTDOWN", False, raising=False)
    async_tools.configure_shared_executor_profile(
        async_tools.SharedExecutorProfile(
            capacity=1, revision="callback-body-backpressure-once-r5", queue_capacity=1
        )
    )
    executor = get_shared_executor()
    completed = executor.submit(lambda: "already-complete")
    assert completed.result(timeout=2) == "already-complete"
    callback_side_effects: list[int] = []

    def callback(future: concurrent.futures.Future[str]) -> None:
        assert future.result() == "already-complete"
        callback_side_effects.append(threading.get_ident())
        if len(callback_side_effects) == 1:
            raise async_tools.SharedExecutorBackpressureError(
                queue_depth=1, queue_capacity=1, capacity=1
            )

    try:
        completed.add_done_callback(callback)
        assert len(callback_side_effects) == 1
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_late_callback_runtime_error_after_shutdown_does_not_retry_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown racing callback failure cannot cause a second callback invocation."""
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_SHUTDOWN", False, raising=False)
    async_tools.configure_shared_executor_profile(
        async_tools.SharedExecutorProfile(
            capacity=1, revision="callback-body-runtime-error-once-r5", queue_capacity=1
        )
    )
    executor = get_shared_executor()
    completed = executor.submit(lambda: "already-complete")
    assert completed.result(timeout=2) == "already-complete"
    callback_started = threading.Event()
    release_callback = threading.Event()
    callback_side_effects: list[int] = []

    def callback(future: concurrent.futures.Future[str]) -> None:
        assert future.result() == "already-complete"
        callback_side_effects.append(threading.get_ident())
        callback_started.set()
        if not release_callback.wait(timeout=3):
            raise TimeoutError("callback release was not signalled")
        raise RuntimeError("callback body failure")

    registrar = threading.Thread(target=completed.add_done_callback, args=(callback,))
    try:
        registrar.start()
        assert callback_started.wait(timeout=2)
        executor.shutdown(wait=False, cancel_futures=False)
        release_callback.set()
        registrar.join(timeout=3)
        assert not registrar.is_alive()
        assert len(callback_side_effects) == 1
    finally:
        release_callback.set()
        if registrar.ident is not None:
            registrar.join(timeout=3)
        executor.shutdown(wait=True, cancel_futures=True)


def test_shutdown_does_not_reopen_a_second_physical_executor_while_old_work_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_SHUTDOWN", False, raising=False)
    async_tools.configure_shared_executor_profile(
        async_tools.SharedExecutorProfile(capacity=1, revision="shutdown-r4-test")
    )
    executor = async_tools.get_shared_executor()
    started = threading.Event()
    release = threading.Event()
    running = executor.submit(lambda: (started.set(), release.wait(timeout=3))[1])
    assert started.wait(timeout=2)

    try:
        async_tools.shutdown_run_coro_sync_executor()
        assert async_tools._RUN_CORO_SYNC_EXECUTOR is executor
        with pytest.raises(RuntimeError, match="shared executor is shut down"):
            async_tools.get_shared_executor()
    finally:
        release.set()
        assert running.result(timeout=2)


def test_run_blocking_async_reuses_shared_executor_soak_smoke() -> None:
    async def _exercise() -> set[int]:
        executor_ids: set[int] = set()
        for _ in range(32):
            executor_ids.add(id(get_shared_executor()))
            assert await run_blocking_async(lambda: "ok") == "ok"
        executor_ids.add(id(get_shared_executor()))
        return executor_ids

    assert run_coro_sync(_exercise()) == {id(get_shared_executor())}


def test_run_blocking_async_concurrent_soak_smoke() -> None:
    async def _exercise() -> tuple[list[int], set[int]]:
        async def _run_one(index: int) -> int:
            return await run_blocking_async(lambda: index)

        results = await asyncio.gather(*(_run_one(index) for index in range(24)))
        return results, {id(get_shared_executor())}

    results, executor_ids = run_coro_sync(_exercise())
    assert results == list(range(24))
    assert executor_ids == {id(get_shared_executor())}


@pytest.fixture
def capacity_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[concurrent.futures.ThreadPoolExecutor]:
    """Use the actual shared producer at its supported four-worker minimum."""
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_SHUTDOWN", False)
    monkeypatch.setattr(async_tools.os, "cpu_count", lambda: 4)
    executor = get_shared_executor()
    try:
        yield executor
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_done_callbacks_hold_physical_capacity_and_refuse_nested_work(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    """Completed Futures do not free workers still inside their callbacks."""
    executor = capacity_executor
    work_gate = threading.Event()
    callback_gate = threading.Event()
    entered = threading.Barrier(5)
    decided = threading.Barrier(5)
    errors: list[BaseException] = []
    actual_inner_calls: list[int] = []

    def callback(future: concurrent.futures.Future[int]) -> None:
        assert future.result() == 7
        entered.wait(timeout=3)
        try:
            executor.submit(actual_inner_calls.append, 42).result(timeout=0.15)
        except BaseException as exc:
            errors.append(exc)
        finally:
            decided.wait(timeout=3)
            callback_gate.wait(timeout=3)

    futures = [executor.submit(lambda: (work_gate.wait(timeout=3), 7)[1]) for _ in range(4)]
    for future in futures:
        future.add_done_callback(callback)
    try:
        work_gate.set()
        entered.wait(timeout=3)
        decided.wait(timeout=3)
        assert all(future.done() and future.result() == 7 for future in futures)
        assert actual_inner_calls == []
        assert [type(exc).__name__ for exc in errors] == ["SharedExecutorReentrancyError"] * 4
    finally:
        work_gate.set()
        callback_gate.set()
    executor.shutdown(wait=True)
    assert actual_inner_calls == []


def test_worker_body_refuses_nested_work_when_physically_full(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    entered = threading.Barrier(4)
    decided = threading.Barrier(5)
    release = threading.Event()
    inner_calls: list[int] = []
    results: list[str] = []

    def outer() -> str:
        entered.wait(timeout=3)
        try:
            capacity_executor.submit(inner_calls.append, 42).result(timeout=0.15)
        except BaseException as exc:
            result = type(exc).__name__
        else:
            result = "accepted"
        results.append(result)
        decided.wait(timeout=3)
        release.wait(timeout=3)
        return result

    futures = [capacity_executor.submit(outer) for _ in range(4)]
    try:
        decided.wait(timeout=3)
        assert results == ["SharedExecutorReentrancyError"] * 4
    finally:
        release.set()
    assert [future.result(timeout=3) for future in futures] == ["SharedExecutorReentrancyError"] * 4
    capacity_executor.shutdown(wait=True)
    assert inner_calls == []


def test_nested_callback_uses_an_actual_spare_worker(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    gate = threading.Event()
    finished = threading.Event()
    result: list[int] = []
    worker_ids: list[int] = []

    def inner() -> int:
        worker_ids.append(threading.get_ident())
        return 42

    def callback(future: concurrent.futures.Future[int]) -> None:
        worker_ids.append(threading.get_ident())
        assert future.result() == 7
        result.append(capacity_executor.submit(inner).result(timeout=2))
        finished.set()

    future = capacity_executor.submit(lambda: (gate.wait(timeout=3), 7)[1])
    future.add_done_callback(callback)
    gate.set()
    assert finished.wait(timeout=3)
    assert result == [42]
    assert len(set(worker_ids)) == 2


def test_late_callback_refuses_nested_work_under_new_full_workers(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    finished = capacity_executor.submit(lambda: 7)
    assert finished.result(timeout=3) == 7
    started = threading.Barrier(5)
    worker_gates = [threading.Event() for _ in range(4)]
    inner_calls: list[int] = []
    errors: list[BaseException] = []
    callback_threads: list[int] = []
    callback_started = threading.Event()
    registration_returned = threading.Event()
    caller_thread = threading.get_ident()

    def blocker(index: int) -> None:
        started.wait(timeout=3)
        worker_gates[index].wait(timeout=3)

    def callback(future: concurrent.futures.Future[int]) -> None:
        callback_threads.append(threading.get_ident())
        callback_started.set()
        assert future.result() == 7
        try:
            capacity_executor.submit(inner_calls.append, 42).result(timeout=0.15)
        except BaseException as exc:
            errors.append(exc)

    blockers = [capacity_executor.submit(blocker, index) for index in range(4)]
    registration = threading.Thread(
        target=lambda: (finished.add_done_callback(callback), registration_returned.set())
    )
    try:
        started.wait(timeout=3)
        registration.start()
        assert not registration_returned.wait(timeout=0.05)
        worker_gates[0].set()
        assert callback_started.wait(timeout=3)
        registration.join(timeout=3)
        assert not registration.is_alive()
        assert registration_returned.is_set()
        assert len(callback_threads) == 1
        assert callback_threads[0] != caller_thread
        assert [type(exc).__name__ for exc in errors] == ["SharedExecutorReentrancyError"]
        assert inner_calls == []
    finally:
        for gate in worker_gates:
            gate.set()
        if registration.ident is not None:
            registration.join(timeout=3)
    for future in blockers:
        future.result(timeout=3)
    capacity_executor.shutdown(wait=True)
    assert inner_calls == []


def test_proxy_queue_cancellation_notifies_waiters_and_never_executes(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    gate = threading.Event()
    started = threading.Barrier(5)
    cancel_finished = threading.Event()
    calls: list[int] = []
    callbacks: list[tuple[bool, int]] = []

    def blocker() -> None:
        started.wait(timeout=3)
        gate.wait(timeout=3)

    blockers = [capacity_executor.submit(blocker) for _ in range(4)]
    try:
        started.wait(timeout=3)
        queued = capacity_executor.submit(calls.append, 42)
        assert not queued.running() and not queued.done()
        queued.add_done_callback(
            lambda future: callbacks.append((future.cancelled(), threading.get_ident()))
        )
        cancel_result: list[bool] = []

        def cancel_queued() -> None:
            cancel_result.extend((queued.cancel(), queued.cancel()))
            cancel_finished.set()

        cancel_thread = threading.Thread(target=cancel_queued)
        caller_thread = threading.get_ident()
        cancel_thread.start()
        assert queued.cancelled() and queued.done() and not queued.running()
        assert not cancel_finished.wait(timeout=0.05)
        gate.set()
        assert cancel_finished.wait(timeout=3)
        cancel_thread.join(timeout=3)
        assert not cancel_thread.is_alive()
        assert cancel_result == [True, True]
        assert len(callbacks) == 1
        assert callbacks[0][0] is True
        assert callbacks[0][1] != caller_thread
        done, pending = concurrent.futures.wait([queued], timeout=0.1)
        assert done == {queued} and not pending
        with pytest.raises(concurrent.futures.CancelledError):
            queued.result()
    finally:
        gate.set()
    for future in blockers:
        future.result(timeout=3)
    assert calls == []


def test_proxy_callback_order_exception_context_and_late_registration(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
    caplog: pytest.LogCaptureFixture,
) -> None:
    gate = threading.Event()
    callbacks_finished = threading.Event()
    seen: list[tuple[str, int]] = []
    worker_ids: list[int] = []

    def work() -> int:
        worker_ids.append(threading.get_ident())
        gate.wait(timeout=3)
        return 42

    def first(future: concurrent.futures.Future[int]) -> None:
        assert future.result() == 42
        seen.append(("first", threading.get_ident()))
        raise ValueError("callback sentinel")

    def second(future: concurrent.futures.Future[int]) -> None:
        seen.append(("second", threading.get_ident()))
        callbacks_finished.set()

    future = capacity_executor.submit(work)
    assert isinstance(future, concurrent.futures.Future)
    future.add_done_callback(first)
    future.add_done_callback(second)
    gate.set()
    assert future.result(timeout=3) == 42
    assert callbacks_finished.wait(timeout=3)
    assert seen == [("first", worker_ids[0]), ("second", worker_ids[0])]
    assert "callback sentinel" in caplog.text
    future.add_done_callback(lambda _: seen.append(("late", threading.get_ident())))
    assert seen[-1][0] == "late"
    assert seen[-1][1] in worker_ids
    assert capacity_executor.submit(lambda: 43).result(timeout=3) == 43


@pytest.mark.asyncio
async def test_proxy_future_preserves_asyncio_result_exception_and_context(
    capacity_executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    scope: ContextVar[str | None] = ContextVar("callback_scope", default=None)
    token = scope.set("request-A")
    try:
        assert await asyncio.wrap_future(capacity_executor.submit(scope.get)) == "request-A"
    finally:
        scope.reset(token)
    assert await asyncio.wrap_future(capacity_executor.submit(scope.get)) is None
    error = ValueError("producer sentinel")

    def fail() -> None:
        raise error

    failed = capacity_executor.submit(fail)
    with pytest.raises(ValueError, match="producer sentinel") as captured:
        await asyncio.wrap_future(failed)
    assert captured.value is error and failed.exception() is error


def test_shutdown_cancel_callback_uses_shared_slot_guard_without_a_lock_cycle() -> None:
    """Shutdown cancellation waits for a guarded callback body without deadlock."""
    script = """
import json, os, threading
from polisyos.common import async_tools
async_tools.os.cpu_count = lambda: 4
executor = async_tools.get_shared_executor()
gate = threading.Event()
entered = threading.Barrier(5)
callback_done = threading.Event()
errors = []
calls = []
def block():
    entered.wait(timeout=2)
    gate.wait(timeout=3)
blockers = [executor.submit(block) for _ in range(4)]
entered.wait(timeout=2)
queued = executor.submit(calls.append, 42)
def callback(future):
    try:
        executor.submit(calls.append, 43)
    except RuntimeError as error:
        errors.append(type(error).__name__)
    callback_done.set()
queued.add_done_callback(callback)
shutdown = threading.Thread(target=lambda: executor.shutdown(wait=False, cancel_futures=True))
shutdown.start()
shutdown.join(timeout=.3)
blocked_inside_shared_capacity = shutdown.is_alive() and not callback_done.is_set()
gate.set()
shutdown.join(timeout=2)
observation = {'shutdown_blocked_inside_capacity': blocked_inside_shared_capacity, 'shutdown_finished': not shutdown.is_alive(), 'callback_finished': callback_done.is_set(), 'queued_cancelled': queued.cancelled(), 'calls': calls, 'errors': errors}
print(json.dumps(observation), flush=True)
if shutdown.is_alive():
    os._exit(73)
executor.shutdown(wait=True)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=5
    )
    import json

    observed = json.loads(completed.stdout)
    assert observed == {
        "shutdown_blocked_inside_capacity": True,
        "shutdown_finished": True,
        "callback_finished": True,
        "queued_cancelled": True,
        "calls": [],
        "errors": ["RuntimeError"],
    }, completed.stdout + completed.stderr
    assert completed.returncode == 0


@pytest.mark.asyncio
async def test_explicit_unbounded_owner_does_not_inherit_helper_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_DEFAULT_TIMEOUT_SECONDS", 0.01)
    assert await run_blocking_async(lambda: (time.sleep(0.03), 42)[1], unbounded=True) == 42
    with pytest.raises(TimeoutError, match="Blocking call did not complete"):
        await run_blocking_async(time.sleep, 0.03)


@pytest.mark.asyncio
async def test_unbounded_and_float_timeout_are_rejected_before_admission() -> None:
    calls: list[int] = []
    with pytest.raises(ValueError, match="unbounded cannot be combined"):
        await run_blocking_async(calls.append, 42, unbounded=True, timeout_seconds=1)
    assert calls == []
