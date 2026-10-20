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

    def test_parent_receipt_route_merges_staged_run_events(self, tmp_path, monkeypatch) -> None:
        """A bound local task returns through the caller's active RunContext writer."""
        import logging
        from dataclasses import replace

        from polisyos.core.artifacts.manifest import SchemaInfo
        from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
        from polisyos.core.components import (
            Capability,
            ComponentId,
            ComponentKind,
            ComponentMetadata,
        )
        from polisyos.core.registry import build_default_registry_bundle
        from polisyos.core.run.context import RunContext
        from polisyos.core.security import tenant_scope
        from polisyos.core.trace.record import TraceRecord
        from polisyos.scientist.orchestration.engine.context import ExecutionContext
        from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
        from polisyos.scientist.orchestration.engine.runner.local_pool import LocalWorkerPool
        from polisyos.scientist.orchestration.engine.runner.serialization import (
            serialize_state,
            serialize_timeout_context,
            worker_dispatch_sha256,
        )
        from polisyos.scientist.orchestration.engine.state import ExperimentState

        tenant_id = "tenant-local-parent-receipt"
        cell_id = "cell-local-parent-receipt"
        run_id = "R_local_parent_receipt"
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            store = FileSystemCAS(
                tmp_path / "cas",
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            bundle = build_default_registry_bundle(
                store,
                return_selected_profile=True,
            )
            run = RunContext.start(
                store=store,
                registry_bundle=bundle.bundle_ref,
                run_id=run_id,
                run_dir=store.root / "runs" / run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
            )
            parent_context = ExecutionContext(
                store=store,
                run=run,
                logger=logging.getLogger("test.local_parent_receipt"),
            )
            input_ref = store.put_json(
                {"input": "worker"},
                PutOptions(
                    kind="scientist.test.local_parent_input",
                    media_type="application/json",
                    schema=SchemaInfo(name="scientist.test.LocalParentInput", version="1.0"),
                ),
                return_selected_profile=True,
            )
            output_ref = store.put_json(
                {"output": "worker"},
                PutOptions(
                    kind="scientist.test.local_parent_output",
                    media_type="application/json",
                    schema=SchemaInfo(name="scientist.test.LocalParentOutput", version="1.0"),
                ),
                return_selected_profile=True,
            )
            orphan_payload = {"output": "persisted-before-failure", "run_id": run_id}
            orphan_refs = []

            class ReceiptNode:
                spec = NodeSpec(
                    metadata=ComponentMetadata(
                        component_id=ComponentId.parse("scientist.test.local_parent@1.0.0"),
                        kind=ComponentKind.SCIENTIST_NODE,
                        abi_targets={"world_abi": "1.x"},
                        capabilities=Capability.SCIENTIST_NODE,
                        display_name="Local parent receipt test",
                        description="Exercises the worker receipt consumer route.",
                    ),
                    state_reads=["params"],
                    state_writes=["params"],
                )

                def execute(self, worker_context, worker_state):
                    worker_context.run.emit(
                        "scientist.node.local-parent-receipt",
                        "NODE_LOCAL_PARENT_RECEIPT_EMITTED",
                    )
                    worker_context.run.add_input(input_ref)
                    worker_context.run.add_output(output_ref)
                    worker_state.params["worker_value"] = "from-worker"
                    return NodeOutcome(status="ok", state=worker_state, events=[], artifacts=[])

            node = ReceiptNode()
            nonlocal_node = [node]
            from polisyos.scientist.orchestration.engine import registry as registry_module

            monkeypatch.setattr(
                registry_module,
                "discover_nodes",
                lambda actual, **_kwargs: actual.register(nonlocal_node[0]),
            )
            state_bytes = serialize_state(ExperimentState(run_id=run_id))
            context_meta = serialize_timeout_context(parent_context, expected_run_id=run_id)
            dispatch = {
                "node_id": str(node.spec.metadata.component_id),
                "alias": "local-parent-receipt",
                "params": {},
                "state_bytes": state_bytes,
                "trace_carrier": {},
                "timeout_s": None,
                "max_retries": 0,
                "context_meta": context_meta,
            }
            task = _make_task(
                **{key: value for key, value in dispatch.items() if key != "max_retries"},
                worker_invocation_id="a" * 64,
                worker_dispatch_sha256=worker_dispatch_sha256(**dispatch),
            )
            pool = LocalWorkerPool(max_workers=1)
            from polisyos.scientist.orchestration.engine.runner.task_router import TaskRouter

            router = TaskRouter({"cpu": pool})
            assert run.trace_path is not None
            before_dispatch = run.trace_path.read_bytes()

            async def _run() -> bytes:
                with pytest.raises(
                    ValueError,
                    match="worker_task_parent_dispatch_binding_invalid",
                ):
                    await pool.submit_with_parent_context(
                        replace(task, params={"tampered": True}),
                        parent_context,
                    )
                with pytest.raises(
                    ValueError,
                    match="worker_task_parent_receipt_timeout_unsupported",
                ):
                    await pool.submit_with_parent_context(
                        replace(task, timeout_s=1.0),
                        parent_context,
                    )
                assert run.trace_path.read_bytes() == before_dispatch
                with pytest.raises(
                    RuntimeError, match="worker_task_parent_receipt_context_required"
                ):
                    await router.submit(task)
                result = await router.submit_with_parent_context(task, parent_context)

                class PutThenFailNode:
                    spec = NodeSpec(
                        metadata=ComponentMetadata(
                            component_id=ComponentId.parse(
                                "scientist.test.local_parent_put_then_fail@1.0.0"
                            ),
                            kind=ComponentKind.SCIENTIST_NODE,
                            abi_targets={"world_abi": "1.x"},
                            capabilities=Capability.SCIENTIST_NODE,
                            display_name="Local parent receipt failure test",
                            description="Observes a persisted artifact without a staged output receipt.",
                        ),
                        state_reads=["params"],
                        state_writes=["params"],
                    )

                    def execute(self, worker_context, worker_state):
                        ref = worker_context.store.put_json(
                            orphan_payload,
                            PutOptions(
                                kind="scientist.test.local_parent_orphan",
                                media_type="application/json",
                                schema=SchemaInfo(
                                    name="scientist.test.LocalParentOrphan",
                                    version="1.0",
                                ),
                            ),
                            return_selected_profile=True,
                        )
                        orphan_refs.append(ref)
                        raise RuntimeError("failure-after-worker-cas-put")

                nonlocal_node[0] = PutThenFailNode()
                from polisyos.scientist.orchestration.engine.state import ExperimentState

                failure_dispatch = {
                    "node_id": str(nonlocal_node[0].spec.metadata.component_id),
                    "alias": "local-parent-put-then-fail",
                    "params": {},
                    "state_bytes": serialize_state(ExperimentState(run_id=run_id)),
                    "trace_carrier": {},
                    "timeout_s": None,
                    "max_retries": 0,
                    "context_meta": serialize_timeout_context(
                        parent_context,
                        expected_run_id=run_id,
                    ),
                }
                failure_task = _make_task(
                    **{
                        key: value
                        for key, value in failure_dispatch.items()
                        if key != "max_retries"
                    },
                    worker_invocation_id="c" * 64,
                    worker_dispatch_sha256=worker_dispatch_sha256(**failure_dispatch),
                )
                with pytest.raises(RuntimeError, match="failure-after-worker-cas-put"):
                    await router.submit_with_parent_context(failure_task, parent_context)
                await pool.shutdown()
                return result

            try:
                result_bytes = asyncio.run(_run())
                from polisyos.scientist.orchestration.engine.runner.serialization import (
                    deserialize_outcome,
                )

                outcome = deserialize_outcome(result_bytes)
                assert outcome.status == "ok"
                assert outcome.state.params["worker_value"] == "from-worker"
                assert input_ref in run.run_manifest.inputs
                assert output_ref in run.run_manifest.outputs
                assert run.read_runtime_owner_output_refs() == (output_ref,)
                assert len(orphan_refs) == 1
                orphan_ref = orphan_refs[0]
                assert store.verify(orphan_ref).ok
                assert orphan_ref not in run.run_manifest.outputs
                assert orphan_ref not in run.read_runtime_owner_output_refs()
                assert run.trace_path is not None
                trace = [
                    TraceRecord.model_validate_json(line)
                    for line in run.trace_path.read_text(encoding="utf-8").splitlines()
                ]
                assert sum(record.event == "RUN_STARTED" for record in trace) == 1
                assert (
                    sum(record.event == "NODE_LOCAL_PARENT_RECEIPT_EMITTED" for record in trace)
                    == 1
                )
                assert sum(record.event == "WORKER_INVOCATION_STARTED" for record in trace) == 2
                assert sum(record.event == "WORKER_INVOCATION_COMPLETED" for record in trace) == 2
                assert [
                    record.refs.outputs[0] for record in trace if record.event == "RUN_OUTPUT_ADDED"
                ] == [output_ref]
                assert all(
                    record.worker_invocation_id in {"a" * 64, "c" * 64}
                    for record in trace
                    if record.event.startswith("WORKER_INVOCATION_")
                )
                assert all(
                    record.worker_invocation_id == "a" * 64
                    for record in trace
                    if record.event
                    in {
                        "NODE_LOCAL_PARENT_RECEIPT_EMITTED",
                        "RUN_INPUT_ADDED",
                        "RUN_OUTPUT_ADDED",
                    }
                )
                from polisyos.core.run.worker_lifecycle import WorkerLifecycleCapability

                WorkerLifecycleCapability.for_parent(run).snapshot()
            finally:
                if not run._closed and not run._suspended:
                    run.suspend_for_resume()

    def test_parent_receipt_maps_core_factory_type_refusal_to_legacy_error(self) -> None:
        """Keep the legacy refusal only for the Core factory's exact type error."""
        import logging
        from typing import Any, cast

        from polisyos.scientist.orchestration.engine.context import ExecutionContext
        from polisyos.scientist.orchestration.engine.runner.local_pool import (
            _prepare_parent_receipt,
        )

        parent = ExecutionContext(
            store=cast("Any", object()),
            run=cast("Any", object()),
            logger=logging.getLogger("test.local_parent_receipt_type_refusal"),
        )
        with pytest.raises(ValueError, match="^worker_task_parent_run_not_active$"):
            _prepare_parent_receipt(_make_task(), parent)

    def test_parent_receipt_propagates_other_core_factory_errors_unchanged(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Do not translate lifecycle/owner errors or ValueError subclasses."""
        import logging
        from typing import Any, cast

        from polisyos.core.run.worker_lifecycle import WorkerLifecycleCapability
        from polisyos.scientist.orchestration.engine.context import ExecutionContext
        from polisyos.scientist.orchestration.engine.runner.local_pool import (
            _prepare_parent_receipt,
        )

        class LifecycleRefusal(ValueError):
            pass

        failures = (
            ValueError("worker_lifecycle_parent_run_not_active"),
            LifecycleRefusal("worker_lifecycle_core_run_required"),
        )
        parent = ExecutionContext(
            store=cast("Any", object()),
            run=cast("Any", object()),
            logger=logging.getLogger("test.local_parent_receipt_factory_refusal"),
        )
        for failure in failures:

            def reject_factory(
                _cls: type[WorkerLifecycleCapability],
                _run: Any,
                *,
                error: ValueError = failure,
            ) -> WorkerLifecycleCapability:
                raise error

            monkeypatch.setattr(
                WorkerLifecycleCapability,
                "for_parent",
                classmethod(reject_factory),
            )
            with pytest.raises(type(failure)) as caught:
                _prepare_parent_receipt(_make_task(), parent)
            assert caught.value is failure

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
