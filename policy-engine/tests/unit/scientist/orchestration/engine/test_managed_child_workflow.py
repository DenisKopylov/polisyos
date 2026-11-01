"""Real Core/CAS tests for the synchronous managed sub-workflow bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from concurrent.futures import Future
from decimal import Decimal
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.run import read_runtime_invocation_attempts, read_terminal_run
from polisyos.core.run.context import RunContext, _run_manifest_write_options
from polisyos.core.run.manifest import RunInvocationCompleted, RunInvocationStarted, RunManifest
from polisyos.core.trace import TraceRecord
from polisyos.scientist.orchestration.engine import (
    child_workflow as child_workflow_module,
)
from polisyos.scientist.orchestration.engine import sub_workflow as sub_workflow_module
from polisyos.scientist.orchestration.engine.builtins.noop import NoopNode
from polisyos.scientist.orchestration.engine.child_workflow import (
    ChildWorkflowOutcomeUnknownError,
    _ChildBinding,
    _ManagedSubWorkflowDispatch,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.execution_admission import WorkflowExecutionAdmission
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutionResult,
    WorkflowExecutor,
    WorkflowReport,
    _WorkflowResumeFrontierUnreconciledError,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner.local_runner import LocalWorkflowRunner
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.sub_workflow import (
    StateMapping,
    SubWorkflowConfig,
    SubWorkflowNode,
)
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from tests._helpers.execution_admission import AdmissionNode, ChangedAdmissionNode

_SUB = "scientist.node_sub_workflow@1.0.0"
_LEAF = "test.managed_child_leaf@1.0.0"


class _Leaf:
    def __init__(self, calls: list[int]) -> None:
        self.calls = calls

    @property
    def spec(self) -> NodeSpec:
        return NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(_LEAF),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Managed child leaf",
                description="Produces a value and checks the node lifecycle boundary",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.value"],
            state_writes=["params.result"],
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        for name in ("add_input", "add_output", "finalize", "suspend_for_resume"):
            with pytest.raises(AttributeError):
                getattr(ctx.run, name)
        self.calls.append(1)
        state.params["result"] = state.params["value"] + 1
        return NodeOutcome(status="ok", state=state)


def _registry(node: object) -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(node)  # type: ignore[arg-type]
    return registry


def _bundle(store: FileSystemCAS):
    refs = {
        name: store.put_json(
            {}, PutOptions(kind=f"test.registry.{name}", media_type="application/json")
        )
        for name in ("slot", "merge", "constraint", "mechanism", "trust")
    }
    return store.put_json(
        {f"{name}_registry": ref.model_dump(mode="json") for name, ref in refs.items()},
        PutOptions(kind="core.registry.bundle", media_type="application/json"),
        return_selected_profile=True,
    )


def _setup(tmp_path: Path, *, timeout: float | None = None, serious: bool = False):
    store = FileSystemCAS(tmp_path / "cas")
    bundle = _bundle(store)
    run_dir = tmp_path / "runs" / "parent"
    run = RunContext.start(store, bundle, run_dir=run_dir, run_id="parent")
    calls: list[int] = []
    inputs = [StateMapping(source_path="params.value", target_path="params.value")]
    if serious:
        inputs.append(
            StateMapping(
                source_path="params.requested_execution_profile",
                target_path="params.requested_execution_profile",
            )
        )
    leaf_workflow = WorkflowSpec(
        workflow_id="leaf_workflow",
        nodes=[NodeInvocation(alias="leaf", node_id=_LEAF)],
    )
    inner = SubWorkflowNode(
        SubWorkflowConfig(
            workflow=leaf_workflow,
            input_mappings=inputs,
            output_mappings=[
                StateMapping(source_path="params.result", target_path="params.answer")
            ],
        ),
        _registry(_Leaf(calls)),
        alias="inner",
    )
    middle_workflow = WorkflowSpec(
        workflow_id="middle_workflow",
        nodes=[NodeInvocation(alias="inner", node_id=_SUB)],
    )
    outer = SubWorkflowNode(
        SubWorkflowConfig(
            workflow=middle_workflow,
            input_mappings=inputs,
            output_mappings=[
                StateMapping(source_path="params.answer", target_path="params.answer")
            ],
        ),
        _registry(inner),
        alias="outer",
    )
    workflow = WorkflowSpec(
        workflow_id="parent_workflow",
        nodes=[NodeInvocation(alias="outer", node_id=_SUB, timeout_s=timeout)],
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.child"))
    return store, bundle, run_dir, ctx, _registry(outer), workflow, calls


def _fresh_manifest(store: FileSystemCAS, ref):
    fresh = FileSystemCAS(store.root)
    assert fresh.verify(ref).ok
    return RunManifest.model_validate(from_canonical_bytes(fresh.get_bytes(ref)))


def _terminal_count(run_dir: Path) -> int:
    return sum(
        1
        for line in (run_dir / "trace.jsonl").read_text().splitlines()
        if json.loads(line).get("event") == "RUN_FINALIZED"
    )


def test_default_local_runner_executes_real_nested_children(tmp_path: Path) -> None:
    store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    result = asyncio.run(
        LocalWorkflowRunner(max_parallelism=1).execute_workflow(
            workflow, ExperimentState(run_id="parent", params={"value": 4}), ctx, registry
        )
    )
    assert result.report.status == "ok"
    assert result.state.params["answer"] == 5
    assert calls == [1]
    outer_ref = next(
        ref for ref in result.report.nodes[0].artifacts if ref.kind == "core.run_manifest"
    )
    outer_manifest = _fresh_manifest(store, outer_ref)
    assert outer_manifest.parent_run_id == "parent"
    fresh = FileSystemCAS(store.root)
    outer_report_ref = next(
        ref for ref in outer_manifest.outputs if ref.kind == "scientist.workflow_report"
    )
    outer_report = WorkflowReport.model_validate(
        from_canonical_bytes(fresh.get_bytes(outer_report_ref))
    )
    inner_ref = next(
        ref for ref in outer_report.nodes[0].artifacts if ref.kind == "core.run_manifest"
    )
    inner_manifest = _fresh_manifest(store, inner_ref)
    assert inner_manifest.parent_run_id == outer_manifest.run_id
    outer_dir = run_dir / "children" / outer_manifest.run_id
    inner_dir = outer_dir / "children" / inner_manifest.run_id
    assert [_terminal_count(path) for path in (run_dir, outer_dir, inner_dir)] == [1, 1, 1]


def test_default_local_runner_refuses_timed_child_before_producer(tmp_path: Path) -> None:
    _store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path, timeout=1.0)
    result = asyncio.run(
        LocalWorkflowRunner(max_parallelism=1).execute_workflow(
            workflow, ExperimentState(run_id="parent", params={"value": 4}), ctx, registry
        )
    )
    assert result.report.status == "fail"
    assert result.report.nodes[0].error is not None
    assert result.report.nodes[0].error.code == "node.timeout_worker_unsupported"
    assert (
        result.report.nodes[0].error.details["reason"] == "managed_child_async_profile_unsupported"
    )
    assert calls == []
    assert not (run_dir / "children").exists()


def test_default_local_runner_refuses_child_budget_before_producer(tmp_path: Path) -> None:
    _store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    result = asyncio.run(
        LocalWorkflowRunner(max_parallelism=1).execute_workflow(
            workflow,
            ExperimentState(run_id="parent", params={"value": 4}, budgets={"cost": Decimal("0")}),
            ctx,
            registry,
        )
    )
    assert result.report.status == "fail"
    assert result.report.nodes[0].error is not None
    assert (
        result.report.nodes[0].error.code == "sub_workflow.child_budget_settlement_not_established"
    )
    assert calls == []
    assert not (run_dir / "children").exists()


@pytest.mark.parametrize("has_owner_check", [False, True])
def test_default_local_runner_refuses_untransported_job_scope_before_producer(
    tmp_path: Path, has_owner_check: bool
) -> None:
    from polisyos.common.job_execution_interrupt import (
        JobExecutionInterrupt,
        job_execution_interrupt_scope,
    )

    _store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    signal = JobExecutionInterrupt(
        job_id="scoped_job",
        worker_id="scoped_worker",
        attempt=1,
        lost=Event(),
        current_owner_check=(lambda: None) if has_owner_check else None,
    )
    with job_execution_interrupt_scope(signal):
        result = asyncio.run(
            LocalWorkflowRunner(max_parallelism=1).execute_workflow(
                workflow, ExperimentState(run_id="parent", params={"value": 4}), ctx, registry
            )
        )
    assert result.report.status == "fail"
    assert result.report.nodes[0].error is not None
    assert result.report.nodes[0].error.code == "sub_workflow.control_job_fence_not_established"
    assert calls == []
    assert not (run_dir / "children").exists()


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_default_local_runner_cancel_keeps_owner_until_child_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cleanup_failure: bool
) -> None:
    store, bundle, run_dir, ctx, registry, workflow, _calls = _setup(tmp_path)
    database = tmp_path / "cancelled_child_effect.sqlite3"
    started, release, finished = Event(), Event(), Event()
    late_write_outcomes: list[str] = []

    def gated_leaf(_self, node_ctx, state):
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS effects(value INTEGER)")
            connection.execute("INSERT INTO effects VALUES (1)")
        started.set()
        try:
            if not release.wait(timeout=10):
                raise TimeoutError("test did not release child producer")
            try:
                node_ctx.store.put_json(
                    {"late": True},
                    PutOptions(
                        kind="test.cancelled_child_late_write", media_type="application/json"
                    ),
                    return_selected_profile=True,
                )
            except RuntimeError as exc:
                late_write_outcomes.append(str(getattr(exc, "code", "unexpected")))
            else:
                late_write_outcomes.append("accepted")
            state.params["result"] = state.params["value"] + 1
            return NodeOutcome(status="ok", state=state)
        finally:
            finished.set()

    monkeypatch.setattr(_Leaf, "execute", gated_leaf)
    if cleanup_failure:
        original_suspend = ctx.run.suspend_for_resume

        def fail_after_suspend():
            original_suspend()
            raise RuntimeError("simulated parent cleanup failure")

        monkeypatch.setattr(ctx.run, "suspend_for_resume", fail_after_suspend)

    async def run_and_cancel() -> None:
        runner = LocalWorkflowRunner(max_parallelism=1)
        task = asyncio.create_task(
            runner.execute_workflow(
                workflow, ExperimentState(run_id="parent", params={"value": 4}), ctx, registry
            )
        )

        async def wait_for_start_or_exit() -> None:
            while not started.is_set() and not task.done():
                await asyncio.sleep(0.01)

        cancel_requested = False
        try:
            await asyncio.wait_for(wait_for_start_or_exit(), timeout=10)
            assert started.is_set()
            task.cancel()
            cancel_requested = True
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=2)
            except asyncio.CancelledError:
                if cleanup_failure:
                    with pytest.raises(asyncio.CancelledError) as primary:
                        await task
                    assert any(
                        "simulated parent cleanup failure" in note
                        for note in getattr(primary.value, "__notes__", ())
                    )
            except TimeoutError:
                pytest.fail("cancellation did not propagate while the child producer was blocked")
            else:
                pytest.fail("cancelled runner returned while its child producer was blocked")

            try:
                reopened = RunContext.resume(
                    store,
                    run_id="parent",
                    run_dir=run_dir,
                    registry_bundle=bundle,
                    producer=None,
                    env=None,
                    access_scope=None,
                )
            except ValueError as exc:
                assert "run_execution_lease_busy" in str(exc)
            else:
                reopened.suspend_for_resume()
                pytest.fail("parent run was reopenable while its child producer was live")
        finally:
            release.set()
            if started.is_set():
                assert await asyncio.to_thread(finished.wait, 10)
            if not task.done() and not cancel_requested:
                task.cancel()
            try:
                await asyncio.wait_for(task, timeout=10)
            except asyncio.CancelledError:
                pass

    asyncio.run(run_and_cancel())
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effects").fetchone() == (1,)
    assert late_write_outcomes == ["attempt_write_revoked"]


def test_default_local_runner_submit_error_cannot_start_late_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.common import async_tools

    _store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    original_submit = async_tools.submit_shared_executor_cancellable
    submitted = []

    def enqueue_then_fail(fn):
        handle = original_submit(fn)
        submitted.append(handle)
        raise OSError("submission failed after enqueue")

    monkeypatch.setattr(async_tools, "submit_shared_executor_cancellable", enqueue_then_fail)

    async def run_after_submit_error() -> None:
        result = await LocalWorkflowRunner(max_parallelism=1).execute_workflow(
            workflow, ExperimentState(run_id="parent", params={"value": 4}), ctx, registry
        )
        assert result.report.status == "fail"
        assert len(submitted) == 1
        completion = await submitted[0].result_async(timeout=10)
        assert completion.status == "completed"

    asyncio.run(run_after_submit_error())
    assert calls == []
    assert not (run_dir / "children").exists()


def test_default_local_runner_cancel_before_child_admission_stops_producer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.common import async_tools

    store, bundle, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    database = tmp_path / "late_child_effect.sqlite3"
    before_admission, release = Event(), Event()
    cancel_completion_entered, release_parent_completion = Event(), Event()
    submitted = []
    worker_completions = []
    monitor_errors: list[BaseException] = []
    original_add_input = RunContext.add_input
    original_complete = RunContext._record_runtime_invocation_completed
    original_submit = async_tools.submit_shared_executor_cancellable
    original_leaf = _Leaf.execute

    def pause_before_admission(run, ref):
        original_add_input(run, ref)
        if run.run_manifest.parent_run_id == "parent" and ref.kind == "scientist.experiment_state":
            before_admission.set()
            if not release.wait(timeout=10):
                raise TimeoutError("test did not release child admission")

    def record_submit(fn):
        handle = original_submit(fn)
        submitted.append(handle)
        return handle

    def pause_parent_completion(run, *args, **kwargs):
        if run.run_manifest.run_id == "parent" and kwargs.get("status") == "unknown":
            cancel_completion_entered.set()
            if not release_parent_completion.wait(timeout=10):
                raise TimeoutError("test did not release parent attempt completion")
        return original_complete(run, *args, **kwargs)

    def effectful_leaf(leaf, node_ctx, state):
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS effects(value INTEGER)")
            connection.execute("INSERT INTO effects VALUES (1)")
        return original_leaf(leaf, node_ctx, state)

    monkeypatch.setattr(RunContext, "add_input", pause_before_admission)
    monkeypatch.setattr(RunContext, "_record_runtime_invocation_completed", pause_parent_completion)
    monkeypatch.setattr(async_tools, "submit_shared_executor_cancellable", record_submit)
    monkeypatch.setattr(_Leaf, "execute", effectful_leaf)

    async def cancel_before_admission() -> None:
        task = asyncio.create_task(
            LocalWorkflowRunner(max_parallelism=1).execute_workflow(
                workflow, ExperimentState(run_id="parent", params={"value": 4}), ctx, registry
            )
        )

        async def wait_for_barrier_or_exit() -> None:
            while not before_admission.is_set() and not task.done():
                await asyncio.sleep(0.01)

        monitor: Thread | None = None
        try:
            await asyncio.wait_for(wait_for_barrier_or_exit(), timeout=10)
            assert before_admission.is_set()
            assert len(submitted) == 1

            def release_child_after_revocation() -> None:
                try:
                    if not cancel_completion_entered.wait(timeout=10):
                        raise TimeoutError("parent cancellation did not reach attempt completion")
                    try:
                        reopened = RunContext.resume(
                            store,
                            run_id="parent",
                            run_dir=run_dir,
                            registry_bundle=bundle,
                            producer=None,
                            env=None,
                            access_scope=None,
                        )
                    except ValueError as exc:
                        assert "run_execution_lease_busy" in str(exc)
                    else:
                        reopened.suspend_for_resume()
                        raise AssertionError("parent reopened while child admission was blocked")
                    release.set()
                    worker_completions.append(submitted[0].result(timeout=10))
                except BaseException as exc:
                    monitor_errors.append(exc)
                finally:
                    release.set()
                    release_parent_completion.set()

            monitor = Thread(target=release_child_after_revocation, daemon=True)
            monitor.start()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), timeout=10)
            assert cancel_completion_entered.is_set()
            assert not monitor_errors
            assert len(worker_completions) == 1 and worker_completions[0].status == "completed"
        finally:
            release.set()
            release_parent_completion.set()
            if submitted:
                completion = await submitted[0].result_async(timeout=10)
                assert completion.status == "completed"
            if monitor is not None:
                await asyncio.to_thread(monitor.join, 10)
                assert not monitor.is_alive()
            if not task.done():
                task.cancel()
            try:
                await asyncio.wait_for(task, timeout=10)
            except asyncio.CancelledError:
                pass

    asyncio.run(cancel_before_admission())
    assert calls == []
    assert not database.exists()


def test_async_child_inline_owner_callback_refuses_without_deadlock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.common import async_tools

    store, bundle, run_dir, ctx, registry, _workflow, calls = _setup(tmp_path)
    node = registry.get(_SUB)
    assert isinstance(node, SubWorkflowNode)
    dispatch = _ManagedSubWorkflowDispatch(node, ctx, alias="outer", timeout_s=None)
    state = ExperimentState(run_id="parent", params={"value": 4})
    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    executor.shutdown(wait=True)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", executor)
    observed: list[object] = []

    def call_in_owner_slot() -> None:
        try:
            observed.append(
                executor.run_callback_sync(
                    lambda: asyncio.run(dispatch.execute_managed_async(ctx, state))
                )
            )
        except BaseException as exc:
            observed.append(exc)

    thread = Thread(target=call_in_owner_slot, daemon=True)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive(), "inline shared callback deadlocked on the admission gate"
    assert len(observed) == 1 and isinstance(observed[0], NodeOutcome)
    assert observed[0].status == "fail"
    assert observed[0].error is not None
    assert observed[0].error.code == "sub_workflow.async_reentrant_worker_not_supported"
    assert calls == []
    assert not (run_dir / "children").exists()
    ctx.run.suspend_for_resume()
    resumed = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    resumed.suspend_for_resume()


def test_async_child_failed_completion_releases_pin_without_guessing_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.common import async_tools

    store, bundle, run_dir, ctx, registry, _workflow, calls = _setup(tmp_path)
    node = registry.get(_SUB)
    assert isinstance(node, SubWorkflowNode)
    dispatch = _ManagedSubWorkflowDispatch(node, ctx, alias="outer", timeout_s=None)
    future: Future = Future()
    future.set_exception(RuntimeError("worker completion transport failed"))
    handle = async_tools.SharedExecutionHandle(future)
    monkeypatch.setattr(async_tools, "submit_shared_executor_cancellable", lambda _fn: handle)
    with pytest.raises(ChildWorkflowOutcomeUnknownError, match="child_async_completion_unknown"):
        asyncio.run(
            dispatch.execute_managed_async(
                ctx, ExperimentState(run_id="parent", params={"value": 4})
            )
        )
    assert calls == []
    assert not (run_dir / "children").exists()
    ctx.run.suspend_for_resume()
    resumed = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    resumed.suspend_for_resume()


def test_async_child_cancelled_in_queue_releases_pin_without_starting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.common import async_tools

    store, bundle, run_dir, ctx, registry, _workflow, calls = _setup(tmp_path)
    node = registry.get(_SUB)
    assert isinstance(node, SubWorkflowNode)
    dispatch = _ManagedSubWorkflowDispatch(node, ctx, alias="outer", timeout_s=None)
    executor = async_tools._SharedExecutor(max_workers=1, max_queued=1)
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", executor)
    occupied, release_blocker, queued = Event(), Event(), Event()

    def hold_worker() -> None:
        occupied.set()
        if not release_blocker.wait(timeout=10):
            raise TimeoutError("test did not release the shared worker")

    blocker = executor.submit(hold_worker)
    original_submit = async_tools.submit_shared_executor_cancellable
    submitted = []

    def record_submit(fn):
        handle = original_submit(fn)
        submitted.append(handle)
        queued.set()
        return handle

    monkeypatch.setattr(async_tools, "submit_shared_executor_cancellable", record_submit)

    async def cancel_queued() -> None:
        task = asyncio.create_task(
            dispatch.execute_managed_async(
                ctx, ExperimentState(run_id="parent", params={"value": 4})
            )
        )

        async def wait_for_queue_or_exit() -> None:
            while not queued.is_set() and not task.done():
                await asyncio.sleep(0.01)

        await asyncio.wait_for(wait_for_queue_or_exit(), timeout=10)
        assert queued.is_set() and len(submitted) == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        ctx.run.suspend_for_resume()
        resumed = RunContext.resume(
            store,
            run_id="parent",
            run_dir=run_dir,
            registry_bundle=bundle,
            producer=None,
            env=None,
            access_scope=None,
        )
        resumed.suspend_for_resume()

    try:
        assert occupied.wait(timeout=10)
        asyncio.run(cancel_queued())
    finally:
        release_blocker.set()
        blocker.result(timeout=10)
        executor.shutdown(wait=True)
    assert calls == []
    assert not (run_dir / "children").exists()


@pytest.mark.parametrize("owner_pair", ["sync_sync", "sync_async", "async_sync"])
def test_same_run_context_rejects_overlapping_workflow_owners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owner_pair: str
) -> None:
    _store, _bundle_ref, run_dir, ctx, registry, workflow, _calls = _setup(tmp_path)
    database = tmp_path / "overlap_effect.sqlite3"
    started, release = Event(), Event()

    def gated_leaf(_self, _node_ctx, state):
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS effects(value INTEGER)")
            connection.execute("INSERT INTO effects VALUES (1)")
        started.set()
        if not release.wait(timeout=10):
            raise TimeoutError("test did not release the first workflow owner")
        state.params["result"] = state.params["value"] + 1
        return NodeOutcome(status="ok", state=state)

    monkeypatch.setattr(_Leaf, "execute", gated_leaf)
    state = ExperimentState(run_id="parent", params={"value": 4})
    results: list[object] = []

    def first_sync() -> None:
        try:
            results.append(WorkflowExecutor(ctx, registry).execute(workflow, state))
        except BaseException as exc:
            results.append(exc)

    if owner_pair in {"sync_sync", "sync_async"}:
        thread = Thread(target=first_sync, daemon=True)
        thread.start()
        try:
            assert started.wait(timeout=10)
            if owner_pair == "sync_sync":
                with pytest.raises(ValueError, match="run_workflow_execution_busy"):
                    WorkflowExecutor(ctx, registry).execute(workflow, state)
            else:
                with pytest.raises(ValueError, match="run_workflow_execution_busy"):
                    asyncio.run(
                        LocalWorkflowRunner(max_parallelism=1).execute_workflow(
                            workflow, state, ctx, registry
                        )
                    )
        finally:
            release.set()
            thread.join(timeout=10)
            assert not thread.is_alive()
    else:

        async def first_async() -> None:
            task = asyncio.create_task(
                LocalWorkflowRunner(max_parallelism=1).execute_workflow(
                    workflow, state, ctx, registry
                )
            )
            try:
                assert await asyncio.to_thread(started.wait, 10)
                with pytest.raises(ValueError, match="run_workflow_execution_busy"):
                    WorkflowExecutor(ctx, registry).execute(workflow, state)
            finally:
                release.set()
                results.append(await asyncio.wait_for(task, timeout=10))

        asyncio.run(first_async())
    assert len(results) == 1 and isinstance(results[0], WorkflowExecutionResult)
    assert results[0].report.status == "ok"
    assert _terminal_count(run_dir) == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effects").fetchone() == (1,)


def test_external_suspend_keeps_owner_lease_until_sync_producer_stops(tmp_path: Path) -> None:
    store, bundle, run_dir, ctx, _registry_unused, _workflow_unused, _calls_unused = _setup(
        tmp_path
    )
    database = tmp_path / "suspend_effect.sqlite3"
    started, release = Event(), Event()
    late_writes: list[str] = []
    results: list[object] = []

    class BlockingNode(AdmissionNode):
        def execute(self, node_ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE IF NOT EXISTS effects(value INTEGER)")
                connection.execute("INSERT INTO effects VALUES (1)")
            started.set()
            if not release.wait(timeout=10):
                raise TimeoutError("test did not release the producer")
            try:
                node_ctx.run.emit("test", "LATE_WRITE")
            except ValueError as exc:
                late_writes.append(str(exc))
            else:
                late_writes.append("unexpectedly accepted")
            return NodeOutcome(status="ok", state=state)

    node = BlockingNode(database)
    registry = _registry(node)
    workflow = WorkflowSpec(
        workflow_id="external_suspend",
        nodes=[NodeInvocation(alias="step", node_id=node.spec.metadata.component_id)],
    )

    def run_first() -> None:
        try:
            results.append(
                WorkflowExecutor(ctx, registry).execute(workflow, ExperimentState(run_id="parent"))
            )
        except BaseException as exc:
            results.append(exc)

    worker = Thread(target=run_first, daemon=True)
    worker.start()
    try:
        assert started.wait(timeout=10)
        ctx.run.suspend_for_resume()
        with pytest.raises(ValueError, match="run_execution_lease_busy"):
            RunContext.resume(
                store,
                run_id="parent",
                run_dir=run_dir,
                registry_bundle=bundle,
                producer=None,
                env=None,
                access_scope=None,
            )
    finally:
        release.set()
        worker.join(timeout=10)
        assert not worker.is_alive()
    assert late_writes == ["run_context_writer_closed"]
    assert len(results) == 1 and isinstance(results[0], BaseException)
    resumed = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    resumed_ctx = ExecutionContext(store=store, run=resumed, logger=logging.getLogger("test.child"))
    with pytest.raises(_WorkflowResumeFrontierUnreconciledError):
        WorkflowExecutor(resumed_ctx, registry).execute(workflow, ExperimentState(run_id="parent"))
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effects").fetchone() == (1,)


@pytest.mark.parametrize("serious", [False, True], ids=["ordinary", "normalized-memory"])
def test_two_real_child_levels_are_linked_and_parent_finalizes_once(
    tmp_path: Path, serious: bool
) -> None:
    store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path, serious=serious)
    params: dict[str, int | str] = {"value": 4}
    if serious:
        params["requested_execution_profile"] = "research"
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id="parent", params=params)
    )
    assert result.report.status == "ok"
    assert result.state.params["answer"] == 5
    assert calls == [1]
    outer_ref = next(
        ref for ref in result.report.nodes[0].artifacts if ref.kind == "core.run_manifest"
    )
    outer_manifest = _fresh_manifest(store, outer_ref)
    assert outer_manifest.parent_run_id == "parent"
    fresh = FileSystemCAS(store.root)
    outer_report_ref = next(
        ref for ref in outer_manifest.outputs if ref.kind == "scientist.workflow_report"
    )
    assert fresh.verify(outer_report_ref).ok
    outer_report = WorkflowReport.model_validate(
        from_canonical_bytes(fresh.get_bytes(outer_report_ref))
    )
    inner_ref = next(
        ref for ref in outer_report.nodes[0].artifacts if ref.kind == "core.run_manifest"
    )
    inner_manifest = _fresh_manifest(store, inner_ref)
    assert inner_manifest.parent_run_id == outer_manifest.run_id
    assert (
        outer_manifest.registry_bundle
        == inner_manifest.registry_bundle
        == ctx.run.run_manifest.registry_bundle
    )
    outer_dir = run_dir / "children" / outer_manifest.run_id
    inner_dir = outer_dir / "children" / inner_manifest.run_id
    assert [_terminal_count(path) for path in (run_dir, outer_dir, inner_dir)] == [1, 1, 1]
    for selected_dir, selected_run in (
        (run_dir, "parent"),
        (outer_dir, outer_manifest.run_id),
        (inner_dir, inner_manifest.run_id),
    ):
        attempts = read_runtime_invocation_attempts(
            fresh, selected_dir / "trace.jsonl", run_id=selected_run
        )
        assert len(attempts) == 1
        basis = attempts[0].basis
        admission_ref = basis.workflow_execution_admission_ref
        assert admission_ref is not None and admission_ref.manifest_profile_sha256 is not None
        assert fresh.verify(admission_ref).ok
        source_admission = WorkflowExecutionAdmission.model_validate(
            from_canonical_bytes(fresh.get_bytes(admission_ref))
        )
        assert source_admission.run_id == selected_run
        assert source_admission.workflow_spec_ref == basis.workflow_spec_ref
        assert source_admission.authority == "candidate_execution_continuity"
        assert basis.execution_budget_contract == "admitted_workflow_budget_v1"
        assert basis.budget_middleware_active is False
        assert basis.execution_deadline_at is None
    if serious:
        for manifest in (outer_manifest, inner_manifest):
            admission_ref = next(
                ref
                for ref in manifest.inputs
                if ref.kind == "scientist.child_workflow_input_admission"
            )
            admission = json.loads(fresh.get_bytes(admission_ref))
            assert admission["requested_sha256"] != admission["admitted_sha256"]


def test_mutable_instance_cannot_capture_the_engine_child_callback(tmp_path: Path) -> None:
    _store, _bundle_ref, _run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    original_node = registry.get(_SUB)
    captured = []

    def hostile_admitted(_ctx, _state, callback):
        captured.append(callback)
        raise AssertionError("mutable instance received privileged child callback")

    original_node._execute_admitted = hostile_admitted  # type: ignore[attr-defined,method-assign]
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id="parent", params={"value": 4})
    )
    assert result.report.status == "ok"
    assert captured == []
    assert calls == [1]


def test_caller_cannot_appoint_an_unbound_original_admission(tmp_path: Path) -> None:
    store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    offered = store.put_json(
        {"candidate": "unbound"},
        PutOptions(kind="scientist.workflow_execution_admission", media_type="application/json"),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="workflow_execution_admission_owner_binding_mismatch"):
        WorkflowExecutor(ctx, registry, workflow_execution_admission_ref=offered).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert calls == []
    assert not (run_dir / "children").exists()


def test_mismatched_state_run_cannot_gain_owner_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.scientist.orchestration.engine import execution_admission

    _store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    original = execution_admission.persist_workflow_execution_admission
    captured = []

    def capture(*args, **kwargs):
        captured.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(execution_admission, "persist_workflow_execution_admission", capture)
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id="different_run", params={"value": 4})
    )
    assert result.report.status == "fail"
    assert result.report.nodes[0].error is not None
    assert result.report.nodes[0].error.message == "child_parent_state_run_mismatch"
    assert captured == []
    assert calls == []
    assert not (run_dir / "children").exists()


def test_legacy_profileless_registry_remains_candidate_without_a_new_admission(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "legacy_cas")
    bundle = _bundle(store).model_copy(update={"manifest_profile_sha256": None})
    run = RunContext.start(store, bundle, run_dir=tmp_path / "legacy_run", run_id="legacy")
    node = NoopNode()
    workflow = WorkflowSpec(
        workflow_id="legacy_candidate",
        nodes=[NodeInvocation(alias="step", node_id=node.spec.metadata.component_id)],
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.legacy"))
    result = WorkflowExecutor(ctx, _registry(node)).execute(
        workflow, ExperimentState(run_id="legacy")
    )
    assert result.report.status == "ok"
    assert run._runtime_invocation_tail_ref is not None
    completed = RunInvocationCompleted.model_validate(
        from_canonical_bytes(store.get_bytes(run._runtime_invocation_tail_ref))
    )
    started = RunInvocationStarted.model_validate(
        from_canonical_bytes(store.get_bytes(completed.basis_ref))
    )
    assert started.workflow_execution_admission_ref is None


def test_legacy_profileless_truncated_attempt_history_cannot_dispatch(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "legacy_cas")
    bundle = _bundle(store).model_copy(update={"manifest_profile_sha256": None})
    run_dir = tmp_path / "legacy_run"
    run = RunContext.start(store, bundle, run_dir=run_dir, run_id="legacy")
    database = tmp_path / "must_not_run.sqlite3"
    node = AdmissionNode(database)
    registry = _registry(node)
    workflow = WorkflowSpec(
        workflow_id="legacy_truncated",
        nodes=[NodeInvocation(alias="step", node_id=node.spec.metadata.component_id)],
    )
    state = ExperimentState(run_id="legacy")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.legacy"))
    executor = WorkflowExecutor(ctx, registry)
    workflow_ref = executor._persist_workflow_spec(workflow, return_selected_profile=True)
    state_ref = executor._persist_state(state, return_selected_profile=True)
    trace_path = run_dir / "trace.jsonl"
    original_trace = trace_path.read_bytes()
    run._record_runtime_invocation_started(
        attempt_id=str(uuid4()),
        attempt_number=1,
        workflow_spec_ref=workflow_ref,
        node_alias="step",
        component_id=str(node.spec.metadata.component_id),
        input_state_ref=state_ref,
    )
    assert run._runtime_invocation_tail_ref is not None
    trace_path.write_bytes(original_trace)
    with pytest.raises(ValueError, match="run_owner_snapshot_tail_mismatch"):
        executor.execute(workflow, state)
    assert not database.exists()
    with pytest.raises(ValueError, match="run_resume_registry_profile_not_established"):
        RunContext.resume(
            store,
            run_id="legacy",
            run_dir=run_dir,
            registry_bundle=bundle,
            producer=None,
            env=None,
            access_scope=None,
        )


@pytest.mark.parametrize("mode", ["pending", "durable_only", "reconciled"])
def test_partial_worker_receipt_refuses_dispatch_until_reconciled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    _store, _bundle_ref, _run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    run = ctx.run
    owner_ref = run._owner_snapshot_ref
    assert owner_ref is not None
    events = [
        TraceRecord(run_id="parent", phase="worker", event="candidate_0"),
        TraceRecord(run_id="parent", phase="worker", event="candidate_1"),
    ]
    sink = run.trace
    original_emit_many = sink.emit_many

    def partial_receipt(records):
        original_emit_many(records[:2])
        raise OSError("partial worker receipt")

    monkeypatch.setattr(sink, "emit_many", partial_receipt)
    with pytest.raises(OSError, match="partial worker receipt"):
        run.merge_worker_events(
            invocation_id="b" * 64,
            dispatch_sha256="2" * 64,
            owner_snapshot_ref=owner_ref,
            records=events,
        )
    monkeypatch.setattr(sink, "emit_many", original_emit_many)
    if mode == "durable_only":
        # A missing in-memory marker must not make an incomplete durable
        # receipt look complete to the next real workflow dispatch.
        run._worker_receipt_recovery_required = False
        run._worker_receipt_recovery_invocation_id = None
    reason = (
        "worker_receipt_incomplete"
        if mode == "durable_only"
        else "worker_receipt_recovery_required"
    )
    for read in (
        run._read_active_runtime_owner_trace,
        run._read_active_runtime_invocation_attempts,
    ):
        with pytest.raises(ValueError, match=reason):
            read()
    if mode == "reconciled":
        run.merge_worker_events(
            invocation_id="b" * 64,
            dispatch_sha256="2" * 64,
            owner_snapshot_ref=owner_ref,
            records=events,
        )
        result = WorkflowExecutor(ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
        assert result.report.status == "ok"
        assert calls == [1]
    else:
        try:
            with pytest.raises(ValueError, match=reason):
                WorkflowExecutor(ctx, registry).execute(
                    workflow, ExperimentState(run_id="parent", params={"value": 4})
                )
            assert calls == []
        finally:
            if mode == "durable_only" and not run._closed:
                run._worker_receipt_recovery_required = True
                run._worker_receipt_recovery_invocation_id = "b" * 64
                run.merge_worker_events(
                    invocation_id="b" * 64,
                    dispatch_sha256="2" * 64,
                    owner_snapshot_ref=owner_ref,
                    records=events,
                )
                run.suspend_for_resume()


def test_resumed_empty_owner_chain_does_not_mint_a_new_original_admission(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "resumed_cas")
    bundle = _bundle(store)
    run_dir = tmp_path / "resumed_run"
    run = RunContext.start(store, bundle, run_dir=run_dir, run_id="resumed")
    run.suspend_for_resume()
    resumed = RunContext.resume(
        store,
        run_id="resumed",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    node = NoopNode()
    workflow = WorkflowSpec(
        workflow_id="resumed_empty_owner",
        nodes=[NodeInvocation(alias="step", node_id=node.spec.metadata.component_id)],
    )
    ctx = ExecutionContext(store=store, run=resumed, logger=logging.getLogger("test.resumed"))
    result = WorkflowExecutor(ctx, _registry(node)).execute(
        workflow, ExperimentState(run_id="resumed")
    )
    assert result.report.status == "ok"
    attempts = read_runtime_invocation_attempts(store, run_dir / "trace.jsonl", run_id="resumed")
    assert len(attempts) == 1
    assert attempts[0].basis.workflow_execution_admission_ref is None


@pytest.mark.parametrize("changed", ["source", "history", "unresolved", "implicit"])
def test_resumed_workflow_refuses_unreconciled_admission_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    store, bundle, run_dir, ctx, _registry_unused, _workflow_unused, _calls_unused = _setup(
        tmp_path
    )
    database = tmp_path / "admission_effects.sqlite3"
    original_node = AdmissionNode(database, value=7)
    registry = _registry(original_node)
    workflow = WorkflowSpec(
        workflow_id="admission_source_guard",
        nodes=[NodeInvocation(alias="step", node_id=original_node.spec.metadata.component_id)],
    )
    original_complete = RunContext._record_runtime_invocation_completed

    def lost_completion(*_args, **_kwargs):
        raise KeyboardInterrupt("lost completion")

    monkeypatch.setattr(RunContext, "_record_runtime_invocation_completed", lost_completion)
    with pytest.raises(KeyboardInterrupt, match="lost completion"):
        WorkflowExecutor(ctx, registry).execute(workflow, ExperimentState(run_id="parent"))
    monkeypatch.setattr(RunContext, "_record_runtime_invocation_completed", original_complete)
    attempts = read_runtime_invocation_attempts(store, run_dir / "trace.jsonl", run_id="parent")
    assert len(attempts) == 1
    admission_ref = attempts[0].basis.workflow_execution_admission_ref
    assert admission_ref is not None
    admission = WorkflowExecutionAdmission.model_validate(
        from_canonical_bytes(store.get_bytes(admission_ref))
    )
    assert admission.nodes[0].status == "recomputed"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effects").fetchone() == (1,)
    resumed = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    expected_error = "execution_admission_residual_definition_changed"
    if changed == "source":
        registry.register(ChangedAdmissionNode(database, value=7), override=True)
    elif changed == "history":
        conflicting_workflow = workflow.model_copy(update={"error_policy": "continue"})
        conflicting_ref = store.put_json(
            conflicting_workflow.model_dump(),
            PutOptions(
                kind="scientist.workflow_spec",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.WorkflowSpec", version="1.0"
                ),
            ),
            return_selected_profile=True,
        )
        resumed._record_runtime_invocation_started(
            attempt_id=str(uuid4()),
            attempt_number=1,
            workflow_spec_ref=conflicting_ref,
            node_alias="step",
            component_id=str(original_node.spec.metadata.component_id),
            input_state_ref=attempts[0].basis.input_state_ref,
            execution_budget_contract="admitted_workflow_budget_v1",
            budget_middleware_active=False,
            workflow_execution_admission_ref=admission_ref,
        )
        resumed.suspend_for_resume()
        resumed = RunContext.resume(
            store,
            run_id="parent",
            run_dir=run_dir,
            registry_bundle=bundle,
            producer=None,
            env=None,
            access_scope=None,
        )
        expected_error = "workflow_execution_admission_history_mismatch"
    else:
        expected_error = "workflow_execution_admission_frontier_not_reconciled"
    resumed_ctx = ExecutionContext(store=store, run=resumed, logger=logging.getLogger("test.child"))
    try:
        with pytest.raises(ValueError, match=expected_error) as rejection:
            WorkflowExecutor(
                resumed_ctx,
                registry,
                workflow_execution_admission_ref=None if changed == "implicit" else admission_ref,
            ).execute(workflow, ExperimentState(run_id="parent"))
        if changed == "implicit":
            assert isinstance(rejection.value, _WorkflowResumeFrontierUnreconciledError)
            assert rejection.value.run_id == "parent"
            assert rejection.value.run_dir == run_dir
            assert rejection.value.attempt_id == attempts[0].basis.attempt_id
            assert rejection.value.basis_ref == attempts[0].basis_ref
    finally:
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT COUNT(*) FROM effects").fetchone() == (1,)


def test_legacy_started_without_attempt_history_cannot_replay_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, bundle, run_dir, ctx, _registry_unused, _workflow_unused, _calls_unused = _setup(
        tmp_path
    )
    database = tmp_path / "legacy_effects.sqlite3"
    node = AdmissionNode(database, value=7)
    registry = _registry(node)
    workflow = WorkflowSpec(
        workflow_id="legacy_started",
        nodes=[NodeInvocation(alias="step", node_id=node.spec.metadata.component_id)],
    )
    unrecorded_ref = store.put_json(
        {"legacy": "unrecorded"},
        PutOptions(kind="test.legacy_unrecorded_basis", media_type="application/json"),
        return_selected_profile=True,
    )
    original_start = RunContext._record_runtime_invocation_started
    original_complete = RunContext._record_runtime_invocation_completed

    def legacy_unrecorded_start(_run, **_kwargs):
        return unrecorded_ref

    def lost_completion(_run, **_kwargs):
        raise KeyboardInterrupt("legacy completion lost")

    monkeypatch.setattr(RunContext, "_record_runtime_invocation_started", legacy_unrecorded_start)
    monkeypatch.setattr(RunContext, "_record_runtime_invocation_completed", lost_completion)
    with pytest.raises(KeyboardInterrupt, match="legacy completion lost"):
        WorkflowExecutor(ctx, registry).execute(workflow, ExperimentState(run_id="parent"))
    monkeypatch.setattr(RunContext, "_record_runtime_invocation_started", original_start)
    monkeypatch.setattr(RunContext, "_record_runtime_invocation_completed", original_complete)
    assert read_runtime_invocation_attempts(store, run_dir / "trace.jsonl", run_id="parent") == []
    assert any(
        json.loads(line).get("event") == "NODE_STARTED"
        for line in (run_dir / "trace.jsonl").read_text().splitlines()
    )
    resumed = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    resumed_ctx = ExecutionContext(store=store, run=resumed, logger=logging.getLogger("test.child"))
    with pytest.raises(_WorkflowResumeFrontierUnreconciledError) as rejection:
        WorkflowExecutor(resumed_ctx, registry).execute(workflow, ExperimentState(run_id="parent"))
    assert rejection.value.run_id == "parent"
    assert rejection.value.trace_path == run_dir / "trace.jsonl"
    assert rejection.value.attempt_id is None and rejection.value.basis_ref is None
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effects").fetchone() == (1,)


def test_removing_child_dispatch_refuses_before_producer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)

    def without_child_owner(self, node_ctx, state):
        return self._node.execute(node_ctx, state)

    monkeypatch.setattr(_ManagedSubWorkflowDispatch, "execute", without_child_owner)
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id="parent", params={"value": 4})
    )
    assert result.report.status == "fail"
    assert result.report.nodes[0].error is not None
    assert result.report.nodes[0].error.code == "sub_workflow.owner_not_established"
    assert calls == []
    assert not (run_dir / "children").exists()


def test_invalid_admission_view_refuses_before_child_producer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _bundle_ref, _run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    original_put = store.put_json
    corrupted_admissions = []

    def corrupted_put(obj, opts, canon_spec=None, *, return_selected_profile=False):
        ref = original_put(
            obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )
        if opts.kind == "scientist.child_workflow_input_admission":
            corrupted_admissions.append(ref)
            return ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
        return ref

    monkeypatch.setattr(store, "put_json", corrupted_put)
    with pytest.raises(ChildWorkflowOutcomeUnknownError):
        WorkflowExecutor(ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert len(corrupted_admissions) == 1
    assert calls == []


def test_child_cleanup_cannot_replace_original_unknown_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store, _bundle_ref, _run_dir, ctx, registry, workflow, _calls = _setup(tmp_path)
    original_suspend = RunContext.suspend_for_resume
    original_unknown = ChildWorkflowOutcomeUnknownError(
        run_id="unknown_child", run_dir=tmp_path / "unknown_child", reason="outcome_unknown"
    )

    def unknown_child(_self, _ctx, _state):
        raise original_unknown

    def interrupted_cleanup(run):
        if run.run_manifest.parent_run_id is not None:
            raise KeyboardInterrupt("cleanup interrupted")
        original_suspend(run)

    monkeypatch.setattr(_Leaf, "execute", unknown_child)
    monkeypatch.setattr(RunContext, "suspend_for_resume", interrupted_cleanup)
    with pytest.raises(ChildWorkflowOutcomeUnknownError) as raised:
        WorkflowExecutor(ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert raised.value is original_unknown
    assert raised.value.run_id == "unknown_child"
    assert any("cleanup interrupted" in note for note in raised.value.__notes__)


@pytest.mark.parametrize("forgery", ["running", "provenance", "foreign_trace"])
def test_fresh_terminal_reader_rejects_valid_selected_forged_manifest(
    tmp_path: Path, forgery: str
) -> None:
    store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id="parent", params={"value": 4})
    )
    assert result.report.status == "ok"
    original_ref = next(
        ref for ref in result.report.nodes[0].artifacts if ref.kind == "core.run_manifest"
    )
    manifest = _fresh_manifest(store, original_ref)
    child_dir = run_dir / "children" / manifest.run_id
    assert (
        read_terminal_run(store, child_dir, run_id=manifest.run_id, access_scope=None).run_ref
        == original_ref
    )
    if forgery == "running":
        forged = manifest.model_copy(update={"status": "running", "finished_at": None})
        expected_error = "run_terminal_state_not_established"
    elif forgery == "provenance":
        forged = manifest.model_copy(update={"seed": 123456})
        expected_error = "run_terminal_provenance_mismatch"
    else:
        foreign_trace = store.put_bytes(
            b'{"event":"unrelated"}\n',
            PutOptions(kind="core.trace.jsonl", media_type="application/jsonl"),
            return_selected_profile=True,
        )
        assert store.verify(foreign_trace).ok
        forged = manifest.model_copy(update={"trace_ref": foreign_trace})
        expected_error = "run_terminal_trace_artifact_mismatch"
    forged_ref = store.put_json(
        forged, _run_manifest_write_options(forged), return_selected_profile=True
    )
    assert store.verify(forged_ref).ok
    trace_path = child_dir / "trace.jsonl"
    lines = trace_path.read_text().splitlines()
    terminal = json.loads(lines[-1])
    assert terminal["event"] == "RUN_FINALIZED"
    terminal["refs"]["outputs"] = [forged_ref.model_dump(mode="json")]
    lines[-1] = json.dumps(terminal)
    trace_path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match=expected_error):
        read_terminal_run(store, child_dir, run_id=manifest.run_id, access_scope=None)
    assert calls == [1]


@pytest.mark.parametrize("unsupported", ["timeout", "budget"])
def test_unsupported_routes_refuse_before_child_producer(tmp_path: Path, unsupported: str) -> None:
    store, _bundle_ref, run_dir, ctx, registry, workflow, calls = _setup(
        tmp_path, timeout=1.0 if unsupported == "timeout" else None
    )
    budgets = {"cost": Decimal("0")} if unsupported == "budget" else {}
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id="parent", params={"value": 4}, budgets=budgets)
    )
    assert result.report.status == "fail"
    assert result.report.nodes[0].error is not None
    assert result.report.nodes[0].error.code == (
        "sub_workflow.timeout_worker_not_supported"
        if unsupported == "timeout"
        else "sub_workflow.child_budget_settlement_not_established"
    )
    assert calls == []
    assert not (run_dir / "children").exists()


def test_lost_reply_recovers_same_terminal_child_without_reexecution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, bundle, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    original_execute = WorkflowExecutor.execute
    lost = False

    def lose_reply_once(self, selected_workflow, state):
        nonlocal lost
        result = original_execute(self, selected_workflow, state)
        if self._ctx.depth == 1 and not lost:
            lost = True
            raise OSError("lost child reply after finalization")
        return result

    monkeypatch.setattr(WorkflowExecutor, "execute", lose_reply_once)
    with pytest.raises(ChildWorkflowOutcomeUnknownError) as error:
        WorkflowExecutor(ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert error.value.run_dir.exists()
    assert calls == [1]
    original_attempts = read_runtime_invocation_attempts(
        store, run_dir / "trace.jsonl", run_id="parent"
    )
    assert len(original_attempts) == 1
    assert original_attempts[0].outcome is not None
    assert original_attempts[0].outcome.status == "unknown"
    original_admission = original_attempts[0].basis.workflow_execution_admission_ref
    assert original_admission is not None
    wrong_input = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    wrong_ctx = ExecutionContext(
        store=store, run=wrong_input, logger=logging.getLogger("test.child")
    )
    with pytest.raises(ChildWorkflowOutcomeUnknownError, match="child_recovery_not_established"):
        WorkflowExecutor(wrong_ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 5})
        )
    assert calls == [1]

    original_spec = vars(SubWorkflowNode)["spec"]
    altered_spec_calls: list[int] = []

    def altered_spec(_self):
        altered_spec_calls.append(1)
        raise AssertionError("changed spec must not run before source verification")

    monkeypatch.setattr(SubWorkflowNode, "spec", property(altered_spec))
    changed_spec = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    changed_spec_ctx = ExecutionContext(
        store=store, run=changed_spec, logger=logging.getLogger("test.child")
    )
    with pytest.raises(ChildWorkflowOutcomeUnknownError, match="child_recovery_not_established"):
        WorkflowExecutor(changed_spec_ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert altered_spec_calls == []
    assert calls == [1]
    monkeypatch.setattr(SubWorkflowNode, "spec", original_spec)

    original_write = sub_workflow_module._write_to_state
    altered_mapping_calls: list[int] = []

    def altered_write(*_args, **_kwargs):
        altered_mapping_calls.append(1)
        raise AssertionError("changed mapping must not run before source verification")

    monkeypatch.setattr(sub_workflow_module, "_write_to_state", altered_write)
    changed_code = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    changed_code_ctx = ExecutionContext(
        store=store, run=changed_code, logger=logging.getLogger("test.child")
    )
    with pytest.raises(ChildWorkflowOutcomeUnknownError, match="child_recovery_not_established"):
        WorkflowExecutor(changed_code_ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert altered_mapping_calls == []
    assert calls == [1]

    # Removal control: retain the original selected definition but replace the
    # live observer. The substituted mapping is now actually reached, which
    # distinguishes the source check from an unrelated preflight refusal.
    terminal = read_terminal_run(
        store, error.value.run_dir, run_id=error.value.run_id, access_scope=None
    )
    binding_ref = next(
        ref
        for ref in terminal.run_manifest.inputs
        if ref.kind == "scientist.child_workflow_binding"
    )
    original_binding = _ChildBinding.model_validate(
        from_canonical_bytes(store.get_bytes(binding_ref))
    )
    original_capture = child_workflow_module.capture_managed_subworkflow_definition
    monkeypatch.setattr(
        child_workflow_module,
        "capture_managed_subworkflow_definition",
        lambda _node: original_binding.wrapper_definition,
    )
    removed_observer = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    removed_observer_ctx = ExecutionContext(
        store=store, run=removed_observer, logger=logging.getLogger("test.child")
    )
    with pytest.raises(ChildWorkflowOutcomeUnknownError, match="child_recovery_not_established"):
        WorkflowExecutor(removed_observer_ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert altered_mapping_calls == [1]
    assert calls == [1]
    monkeypatch.setattr(
        child_workflow_module, "capture_managed_subworkflow_definition", original_capture
    )
    monkeypatch.setattr(sub_workflow_module, "_write_to_state", original_write)

    composite = registry.get(_SUB)
    assert isinstance(composite, SubWorkflowNode)
    original_config = composite._config
    composite._config = original_config.model_copy(
        update={
            "output_mappings": [
                StateMapping(source_path="params.answer", target_path="params.changed")
            ]
        },
        deep=True,
    )
    changed_mapping = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    changed_ctx = ExecutionContext(
        store=store, run=changed_mapping, logger=logging.getLogger("test.child")
    )
    with pytest.raises(ChildWorkflowOutcomeUnknownError, match="child_recovery_not_established"):
        WorkflowExecutor(changed_ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert calls == [1]
    composite._config = original_config
    # The terminal child is read from its selected artifacts; its completed
    # implementations need not still be present in the current registry.
    composite._registry.clear()
    assert composite._registry.count == 0

    resumed = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    resumed_ctx = ExecutionContext(store=store, run=resumed, logger=logging.getLogger("test.child"))
    result = WorkflowExecutor(resumed_ctx, registry).execute(
        workflow, ExperimentState(run_id="parent", params={"value": 4})
    )
    assert result.report.status == "ok"
    assert result.state.params["answer"] == 5
    assert "changed" not in result.state.params
    assert calls == [1]
    assert _terminal_count(run_dir) == 1
    final_attempts = read_runtime_invocation_attempts(
        store, run_dir / "trace.jsonl", run_id="parent"
    )
    # Mismatched recoveries and the removal control ran before any new attempt.
    assert len(final_attempts) == 2
    assert all(
        attempt.basis.workflow_execution_admission_ref in (None, original_admission)
        for attempt in final_attempts
    )
    recovered_attempt = final_attempts[-1].outcome
    assert recovered_attempt is not None and recovered_attempt.status == "ok"
    assert final_attempts[-1].basis.node_alias == original_attempts[0].basis.node_alias == "outer"
    assert final_attempts[-1].basis_ref != original_attempts[0].basis_ref
    recovered_child_ref = next(
        ref for ref in recovered_attempt.output_refs if ref.kind == "core.run_manifest"
    )
    recovered_child = _fresh_manifest(store, recovered_child_ref)
    assert recovered_child.run_id == error.value.run_id
    assert (
        read_terminal_run(
            FileSystemCAS(store.root),
            error.value.run_dir,
            run_id=error.value.run_id,
            access_scope=None,
        ).run_ref
        == recovered_child_ref
    )
    binding_ref = next(
        ref for ref in recovered_child.inputs if ref.kind == "scientist.child_workflow_binding"
    )
    fresh = FileSystemCAS(store.root)
    binding_schema = fresh.get_manifest(binding_ref).artifact_schema
    assert binding_schema is not None and binding_schema.version == "1.2"
    binding = from_canonical_bytes(fresh.get_bytes(binding_ref))
    assert ArtifactRef.model_validate(binding["parent_basis_ref"]) == original_attempts[0].basis_ref


def test_incomplete_multi_node_child_never_restarts_an_unknown_producer(tmp_path: Path) -> None:
    store, bundle, run_dir, ctx, _registry_unused, _workflow_unused, _calls_unused = _setup(
        tmp_path
    )
    invocations: list[str] = []
    second_id = "test.managed_child_second@1.0.0"

    class _InterruptingLeaf(_Leaf):
        def __init__(self, component_id: str) -> None:
            super().__init__([])
            self.component_id = component_id

        @property
        def spec(self) -> NodeSpec:
            original = super().spec
            return original.model_copy(
                update={
                    "metadata": original.metadata.model_copy(
                        update={"component_id": ComponentId.parse(self.component_id)}
                    )
                }
            )

        def execute(self, node_ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            del node_ctx
            invocations.append(self.component_id)
            if len(invocations) == 2:
                raise KeyboardInterrupt("lost reply after unknown effect")
            state.params["result"] = state.params["value"] + 1
            return NodeOutcome(status="ok", state=state)

    child_workflow = WorkflowSpec(
        workflow_id="multi_node_child",
        nodes=[
            NodeInvocation(alias="first", node_id=_LEAF),
            NodeInvocation(alias="second", node_id=second_id, depends_on=["first"]),
        ],
    )
    child_registry = NodeRegistry()
    child_registry.register(_InterruptingLeaf(_LEAF))
    child_registry.register(_InterruptingLeaf(second_id))
    composite = SubWorkflowNode(
        SubWorkflowConfig(
            workflow=child_workflow,
            input_mappings=[StateMapping(source_path="params.value", target_path="params.value")],
            output_mappings=[
                StateMapping(source_path="params.result", target_path="params.answer")
            ],
        ),
        child_registry,
    )
    registry = _registry(composite)
    workflow = WorkflowSpec(
        workflow_id="multi_node_parent",
        nodes=[NodeInvocation(alias="child", node_id=_SUB)],
    )
    with pytest.raises(KeyboardInterrupt, match="unknown effect"):
        WorkflowExecutor(ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert invocations == [_LEAF, second_id]
    child_dir = next((run_dir / "children").iterdir())
    attempts = read_runtime_invocation_attempts(
        store, child_dir / "trace.jsonl", run_id=child_dir.name
    )
    assert [
        (item.basis.node_alias, item.outcome.status if item.outcome is not None else None)
        for item in attempts
    ] == [("first", "ok"), ("second", "unknown")]
    attempt_refs = [(item.basis_ref, item.outcome_ref) for item in attempts]
    resumed = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    resumed_ctx = ExecutionContext(store=store, run=resumed, logger=logging.getLogger("test.child"))
    with pytest.raises(ChildWorkflowOutcomeUnknownError, match="child_recovery_not_established"):
        WorkflowExecutor(resumed_ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert invocations == [_LEAF, second_id]
    after = read_runtime_invocation_attempts(
        store, child_dir / "trace.jsonl", run_id=child_dir.name
    )
    assert [(item.basis_ref, item.outcome_ref) for item in after] == attempt_refs


@pytest.mark.parametrize("ordinary_prefix", [False, True])
def test_terminal_child_recovery_never_replays_ordinary_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ordinary_prefix: bool
) -> None:
    store, bundle, run_dir, ctx, registry, workflow, calls = _setup(tmp_path)
    database = tmp_path / "ordinary_effect.sqlite3"
    ordinary = AdmissionNode(database, value=7)
    registry.register(ordinary)
    original_child = workflow.nodes[0]
    ordinary_invocation = NodeInvocation(
        alias="ordinary", node_id=ordinary.spec.metadata.component_id
    )
    if ordinary_prefix:
        nodes = [
            ordinary_invocation,
            original_child.model_copy(update={"depends_on": ["ordinary"]}),
        ]
    else:
        nodes = [original_child, ordinary_invocation.model_copy(update={"depends_on": ["outer"]})]
    workflow = workflow.model_copy(update={"nodes": nodes})
    original_execute = WorkflowExecutor.execute
    lost = False

    def lose_child_reply_once(self, selected_workflow, state):
        nonlocal lost
        result = original_execute(self, selected_workflow, state)
        if self._ctx.depth == 1 and not lost:
            lost = True
            raise OSError("lost child reply after finalization")
        return result

    monkeypatch.setattr(WorkflowExecutor, "execute", lose_child_reply_once)
    with pytest.raises(ChildWorkflowOutcomeUnknownError):
        WorkflowExecutor(ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
    assert calls == [1]
    resumed = RunContext.resume(
        store,
        run_id="parent",
        run_dir=run_dir,
        registry_bundle=bundle,
        producer=None,
        env=None,
        access_scope=None,
    )
    resumed_ctx = ExecutionContext(store=store, run=resumed, logger=logging.getLogger("test.child"))
    if ordinary_prefix:
        with pytest.raises(_WorkflowResumeFrontierUnreconciledError):
            WorkflowExecutor(resumed_ctx, registry).execute(
                workflow, ExperimentState(run_id="parent", params={"value": 4})
            )
    else:
        result = WorkflowExecutor(resumed_ctx, registry).execute(
            workflow, ExperimentState(run_id="parent", params={"value": 4})
        )
        assert result.report.status == "ok"
        assert result.state.params["answer"] == 5
    assert calls == [1]
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effects").fetchone() == (1,)
