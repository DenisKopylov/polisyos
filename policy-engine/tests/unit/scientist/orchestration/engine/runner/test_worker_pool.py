"""Tests for WorkerPool protocol and LocalWorkerPool."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from polisyos.scientist.orchestration.engine.runner.worker_pool import (
    NodeTask,
    PoolCapacity,
    ResourceRequirements,
)


def _make_task(**overrides) -> NodeTask:
    defaults = {
        "node_id": "test_node",
        "alias": "test",
        "params": {},
        "state_bytes": b"{}",
        "trace_carrier": {},
    }
    defaults.update(overrides)
    return NodeTask(**defaults)


class TestNodeTask:
    def test_frozen(self) -> None:
        task = _make_task()
        with pytest.raises(AttributeError):
            task.node_id = "changed"  # type: ignore[misc]

    def test_default_resource_requirements(self) -> None:
        task = _make_task()
        assert task.resource_requirements is None
        assert task.priority == 0
        assert task.queue_weight == 1.0

    def test_with_resource_requirements(self) -> None:
        req = ResourceRequirements(cpu_cores=2.0, memory_mb=1024, gpu=True)
        task = _make_task(resource_requirements=req)
        assert task.resource_requirements is not None
        assert task.resource_requirements.gpu is True


class TestPoolCapacity:
    def test_model_creation(self) -> None:
        cap = PoolCapacity(
            total_workers=8,
            idle_workers=5,
            active_tasks=3,
            queue_depth=2,
        )
        assert cap.total_workers == 8
        assert cap.idle_workers == 5

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            PoolCapacity(
                total_workers=1,
                idle_workers=1,
                active_tasks=0,
                queue_depth=0,
                extra=True,
            )


class TestLocalWorkerPool:
    def test_capacity_defaults(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=4)
        cap = asyncio.run(pool.current_capacity())
        assert cap.total_workers == 4
        assert cap.idle_workers == 4
        assert cap.active_tasks == 0
        assert cap.queue_depth == 0

    def test_scale_to_changes_capacity(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=2)

        async def _test() -> None:
            await pool.scale_to(8)
            cap = await pool.current_capacity()
            assert cap.total_workers == 8

        asyncio.run(_test())

    def test_scale_down_does_not_release_old_permits(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=5)

        async def _test() -> None:
            active = 0
            after_shrink_active = 0
            shrink_started = False
            first_batch_started = asyncio.Event()
            release_first_batch = asyncio.Event()
            release_after_shrink = asyncio.Event()
            lock = asyncio.Lock()

            async def _run_node(payload):
                nonlocal active, after_shrink_active
                del payload
                async with lock:
                    active += 1
                    if shrink_started:
                        after_shrink_active += 1
                    if active == 5:
                        first_batch_started.set()
                try:
                    if shrink_started:
                        await release_after_shrink.wait()
                    else:
                        await release_first_batch.wait()
                    return b"{}"
                finally:
                    async with lock:
                        active -= 1

            with patch(
                "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                side_effect=_run_node,
            ):
                futures = [await pool.submit(_make_task(alias=f"task_{idx}")) for idx in range(10)]
                await asyncio.wait_for(first_batch_started.wait(), timeout=2.0)
                shrink_started = True
                await pool.scale_to(1)
                release_first_batch.set()

                deadline = asyncio.get_running_loop().time() + 2.0
                while after_shrink_active == 0 and asyncio.get_running_loop().time() < deadline:
                    await asyncio.sleep(0.01)

                await asyncio.sleep(0.05)
                assert after_shrink_active == 1
                release_after_shrink.set()
                results = await asyncio.gather(*futures, return_exceptions=True)
                assert results == [b"{}"] * 10
                cap = await pool.current_capacity()
                assert cap.active_tasks == 0
                assert cap.queue_depth == 0

        asyncio.run(_test())

    def test_shutdown_rejects_new_tasks(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=2)

        async def _test() -> None:
            await pool.shutdown()
            with pytest.raises(RuntimeError, match="shut down"):
                await pool.submit(_make_task())

        asyncio.run(_test())

    def test_priority_queue_runs_high_priority_submission_first(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=1)

        async def _test() -> None:
            started: list[str] = []
            release_first = asyncio.Event()

            async def _run_node(payload):
                started.append(payload["alias"])
                if payload["alias"] == "low":
                    await release_first.wait()
                return payload["alias"].encode("utf-8")

            with patch(
                "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                side_effect=_run_node,
            ):
                low = await pool.submit(_make_task(alias="low", priority=0))
                medium = await pool.submit(_make_task(alias="medium", priority=1))
                high = await pool.submit(_make_task(alias="high", priority=10))
                await asyncio.sleep(0.05)
                assert started == ["low"]
                release_first.set()
                results = await asyncio.gather(low, medium, high)
                assert results == [b"low", b"medium", b"high"]
                assert started == ["low", "high", "medium"]

        asyncio.run(_test())

    def test_worker_runtime_error_surfaces_on_future(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=1)

        async def _test() -> None:
            async def _run_node(_payload):
                raise RuntimeError("worker exploded")

            with patch(
                "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                side_effect=_run_node,
            ):
                future = await pool.submit(_make_task(alias="boom"))
                with pytest.raises(RuntimeError, match="worker exploded"):
                    await future

        asyncio.run(_test())


    def test_unlisted_worker_exceptions_settle_future_and_release_queued_sibling(self) -> None:
        from polisyos.scientist.orchestration.engine.errors import RetryExhaustedError
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        errors = (
            RuntimeError("runtime failure"),
            ValueError("invalid worker payload"),
            RetryExhaustedError("retry sequence exhausted"),
        )

        def _worker_for(error, failure_started, release_failure, sibling_started):
            async def _run_node(payload):
                if payload["alias"] == "fails":
                    failure_started.set()
                    await release_failure.wait()
                    raise error
                sibling_started.set()
                return b"sibling"

            return _run_node

        async def _wait_for_queued_sibling(pool) -> None:
            while (await pool.current_capacity()).queue_depth != 1:
                await asyncio.sleep(0)

        async def _test() -> None:
            for error in errors:
                pool = LocalWorkerPool(max_workers=1)
                failure_started = asyncio.Event()
                release_failure = asyncio.Event()
                sibling_started = asyncio.Event()
                worker = _worker_for(error, failure_started, release_failure, sibling_started)
                try:
                    with patch(
                        "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                        side_effect=worker,
                    ):
                        failed = await pool.submit(_make_task(alias="fails"))
                        await asyncio.wait_for(failure_started.wait(), timeout=2.0)
                        sibling = await pool.submit(_make_task(alias="sibling"))
                        await asyncio.wait_for(_wait_for_queued_sibling(pool), timeout=2.0)
                        release_failure.set()
                        with pytest.raises(type(error)) as raised:
                            await asyncio.wait_for(failed, timeout=2.0)
                        assert raised.value is error
                        assert await asyncio.wait_for(sibling, timeout=2.0) == b"sibling"
                        assert sibling_started.is_set()
                        capacity = await pool.current_capacity()
                        assert capacity.active_tasks == 0
                        assert capacity.queue_depth == 0
                finally:
                    release_failure.set()
                    await pool.shutdown()

        asyncio.run(_test())

    def test_host_fatal_signal_settles_future_and_remains_visible_on_runner(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        class HostFatalSignal(BaseException):
            pass

        fatal = HostFatalSignal("host signal")
        pool = LocalWorkerPool(max_workers=1)

        async def _test() -> None:
            async def _run_node(_payload):
                raise fatal

            with patch(
                "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                side_effect=_run_node,
            ):
                future = await pool.submit(_make_task(alias="fatal"))
                runner = next(iter(pool._runner_tasks))
                with pytest.raises(HostFatalSignal) as future_error:
                    await future
                with pytest.raises(HostFatalSignal) as runner_error:
                    await runner
                assert future_error.value is fatal
                assert runner_error.value is fatal
                capacity = await pool.current_capacity()
                assert capacity.active_tasks == 0
                assert capacity.queue_depth == 0

        asyncio.run(_test())

    def test_cancelled_caller_future_keeps_running_worker_slot_until_completion(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=1)

        async def _test() -> None:
            first_started = asyncio.Event()
            release_first = asyncio.Event()
            sibling_started = asyncio.Event()

            async def _run_node(payload):
                if payload["alias"] == "first":
                    first_started.set()
                    await release_first.wait()
                    return b"first"
                sibling_started.set()
                return b"sibling"

            with patch(
                "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                side_effect=_run_node,
            ):
                first = await pool.submit(_make_task(alias="first"))
                await asyncio.wait_for(first_started.wait(), timeout=2.0)
                sibling = await pool.submit(_make_task(alias="sibling"))

                async def _wait_for_queued_sibling() -> None:
                    while (await pool.current_capacity()).queue_depth != 1:
                        await asyncio.sleep(0)

                await asyncio.wait_for(_wait_for_queued_sibling(), timeout=2.0)
                first.cancel()
                await asyncio.sleep(0)
                capacity = await pool.current_capacity()
                assert first.cancelled()
                assert capacity.active_tasks == 1
                assert capacity.queue_depth == 1
                assert not sibling_started.is_set()

                release_first.set()
                assert await asyncio.wait_for(sibling, timeout=2.0) == b"sibling"
                assert sibling_started.is_set()
                capacity = await pool.current_capacity()
                assert capacity.active_tasks == 0
                assert capacity.queue_depth == 0

        asyncio.run(_test())

    def test_nongraceful_shutdown_cancels_accepted_futures_and_releases_capacity(self) -> None:
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool

        pool = LocalWorkerPool(max_workers=1)

        async def _test() -> None:
            first_started = asyncio.Event()
            release_first = asyncio.Event()

            async def _run_node(payload):
                if payload["alias"] == "first":
                    first_started.set()
                    await release_first.wait()
                return b"done"

            with patch(
                "polisyos.scientist.orchestration.engine.runner._activity_worker.run_node_in_worker",
                side_effect=_run_node,
            ):
                active = await pool.submit(_make_task(alias="first"))
                await asyncio.wait_for(first_started.wait(), timeout=2.0)
                queued = await pool.submit(_make_task(alias="queued"))

                async def _wait_for_queued() -> None:
                    while (await pool.current_capacity()).queue_depth != 1:
                        await asyncio.sleep(0)

                await asyncio.wait_for(_wait_for_queued(), timeout=2.0)
                await pool.shutdown(graceful=False)
                assert active.cancelled()
                assert queued.cancelled()
                capacity = await pool.current_capacity()
                assert capacity.active_tasks == 0
                assert capacity.queue_depth == 0

        asyncio.run(_test())
