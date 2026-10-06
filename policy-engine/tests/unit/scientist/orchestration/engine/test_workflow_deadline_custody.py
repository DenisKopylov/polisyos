"""Real CAS owner-deadline admission, local publication and retry consumers."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from pathlib import Path

import pytest

from polisyos.common import async_tools
from polisyos.core.artifacts.async_store import (
    AsyncArtifactStoreAdapter,
    AsyncFileSystemArtifactStore,
    ensure_async_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import WorkflowTimeoutError
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


class _WriteGateCAS(FileSystemCAS):
    def __init__(self, root: Path):
        super().__init__(root)
        self.target: str | None = None
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.published: ArtifactRef | None = None
        self.thread: int | None = None

    def put_bytes(self, data, opts):
        if opts.kind != self.target:
            return super().put_bytes(data, opts)
        self.thread = threading.get_ident()
        self.entered.set()
        try:
            if not self.release.wait(5):
                raise RuntimeError("actual CAS publication watchdog expired")
            self.published = super().put_bytes(data, opts)
            return self.published
        finally:
            self.finished.set()


class _ReadGateCAS(FileSystemCAS):
    def __init__(self, root: Path):
        super().__init__(root)
        self.target: str | None = None
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.reads = 0
        self.gate_read = 1

    def get_bytes(self, ref):
        identity = str(ref.artifact_id if isinstance(ref, ArtifactRef) else ref)
        if identity != self.target:
            return super().get_bytes(ref)
        self.reads += 1
        if self.reads != self.gate_read:
            return super().get_bytes(ref)
        self.entered.set()
        try:
            if not self.release.wait(5):
                raise RuntimeError("actual CAS read watchdog expired")
            return super().get_bytes(ref)
        finally:
            self.finished.set()


class _Node:
    def __init__(self):
        self.calls = 0
        self.refs: list[ArtifactRef] = []
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.deadline_consumer@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Deadline consumer",
                description="Actual method and immutable artifact admission",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.seed"],
            state_writes=["params.result"],
        )

    def execute(self, ctx, state):
        raise AssertionError("Native async provider required")

    async def execute_async(self, ctx, state):
        self.calls += 1
        ref = ctx.store.put_json(
            {"seed": state.params["seed"], "ordinal": self.calls},
            PutOptions(kind="scientist.deadline_effect", media_type="application/json"),
        )
        self.refs.append(ref)
        state.params["result"] = state.params["seed"] * 2
        return NodeOutcome(status="ok", state=state, artifacts=[ref])


def _setup(store, *, timeout=None):
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store, bundle.bundle_ref, run_id="R_deadline")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("deadline-consumer"))
    node = _Node()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="owned_deadline",
        nodes=[NodeInvocation(alias="compute", node_id=node.spec.metadata.component_id)],
    )
    executor = AsyncWorkflowExecutor(ctx, registry, workflow_timeout_s=timeout)
    return ctx, node, workflow, executor


def _events(ctx):
    return [json.loads(line) for line in ctx.run.trace_path.read_text().splitlines()]


def _release_after_enter(store, seconds):
    def release():
        assert store.entered.wait(5)
        time.sleep(seconds)
        store.release.set()

    thread = threading.Thread(target=release)
    thread.start()
    return thread


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type", [AsyncArtifactStoreAdapter, AsyncFileSystemArtifactStore])
@pytest.mark.parametrize("mode", ["omitted", "explicit_none", "unbounded"])
async def test_real_cas_bridge_preserves_legacy_limit_and_explicit_unbounded(
    tmp_path, monkeypatch, adapter_type, mode
):
    store = _ReadGateCAS(tmp_path / "cas")
    ref = store.put_json(
        {"value": 7}, PutOptions(kind="deadline.bridge", media_type="application/json")
    )
    store.target = str(ref.artifact_id)
    # A named fixture helper default proves default-vs-unbounded policy without
    # making each positive test wait the production default of thirty seconds.
    assert async_tools._DEFAULT_TIMEOUT_SECONDS == 30
    monkeypatch.setattr(async_tools, "_DEFAULT_TIMEOUT_SECONDS", 0.05)
    kwargs = {"unbounded": True} if mode == "unbounded" else {}
    if mode == "explicit_none":
        kwargs["timeout_seconds"] = None
    adapter = adapter_type(store, **kwargs)
    assert ensure_async_artifact_store(adapter) is adapter
    release = _release_after_enter(store, 0.12)
    try:
        if mode == "unbounded":
            assert json.loads(await adapter.get_bytes(ref)) == {"value": 7}
        else:
            with pytest.raises(TimeoutError, match="Blocking call did not complete within"):
                await adapter.get_bytes(ref)
            assert not store.release.is_set()
    finally:
        store.release.set()
        release.join(5)
        assert await asyncio.to_thread(store.finished.wait, 5)
    assert FileSystemCAS(store.root).verify(ref).ok
    assert json.loads(FileSystemCAS(store.root).get_bytes(ref)) == {"value": 7}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["scientist.workflow_spec", "scientist.experiment_state", "scientist.workflow_report"]
)
@pytest.mark.parametrize("end", ["deadline", "cancel"])
async def test_workflow_cas_wait_cannot_admit_late_ref_or_next_producer(tmp_path, kind, end):
    store = _WriteGateCAS(tmp_path / "cas")
    ctx, node, workflow, executor = _setup(store, timeout=0.5 if end == "deadline" else None)
    state = ExperimentState(run_id="R_deadline", params={"seed": 7})
    store.target = kind
    loop_thread = threading.get_ident()
    task = asyncio.create_task(executor.execute(workflow, state))
    if end == "deadline":
        release = _release_after_enter(store, 0.8)
    else:
        release = None
    try:
        assert await asyncio.to_thread(store.entered.wait, 5)
        if end == "cancel":
            task.cancel()
        with pytest.raises(WorkflowTimeoutError if end == "deadline" else asyncio.CancelledError):
            await task
        assert not store.release.is_set(), (
            "owner wait refreshed or entered I/O was treated as cancelled"
        )
        assert store.thread != loop_thread
        assert node.calls == (1 if kind == "scientist.workflow_report" else 0)
        if kind != "scientist.workflow_report":
            assert executor._cache is None
        assert ctx.run.run_manifest.outputs == []
        assert len(ctx.run.run_manifest.inputs) == (
            0
            if kind == "scientist.workflow_spec"
            else 1
            if kind == "scientist.experiment_state"
            else 2
        )
        before = _events(ctx)
        assert not any(event.get("event") == "RUN_FINALIZED" for event in before)
    finally:
        store.release.set()
        if release:
            release.join(5)
        assert await asyncio.to_thread(store.finished.wait, 5)
        await asyncio.gather(task, return_exceptions=True)
    assert store.published is not None
    reopened = FileSystemCAS(store.root)
    assert reopened.verify(store.published).ok
    assert reopened.get_manifest(store.published).kind == kind
    # An immutable artifact may survive entered I/O. It grants no late input,
    # output, finalized run or next-method admission to the abandoned owner.
    assert _events(ctx) == before
    assert all(ref != store.published for ref in ctx.run.run_manifest.inputs)
    assert all(ref != store.published for ref in ctx.run.run_manifest.outputs)
    assert state.params == {"seed": 7}


@pytest.mark.asyncio
async def test_workflow_without_owner_deadline_uses_explicit_unbounded_cas(tmp_path, monkeypatch):
    store = _WriteGateCAS(tmp_path / "cas")
    ctx, node, workflow, executor = _setup(store)
    assert async_tools._DEFAULT_TIMEOUT_SECONDS == 30
    monkeypatch.setattr(async_tools, "_DEFAULT_TIMEOUT_SECONDS", 0.05)
    store.target = "scientist.workflow_spec"
    release = _release_after_enter(store, 0.12)
    try:
        result = await executor.execute(
            workflow, ExperimentState(run_id="R_deadline", params={"seed": 7})
        )
    finally:
        store.release.set()
        release.join(5)
    assert result.report.status == "ok"
    assert node.calls == 1
    reopened = FileSystemCAS(store.root)
    assert reopened.verify(result.run_ref).ok
    assert json.loads(reopened.get_bytes(node.refs[0])) == {"seed": 7, "ordinal": 1}
    assert result.state.params == {"seed": 7, "result": 14}


@pytest.mark.asyncio
async def test_expired_native_cache_lookup_cannot_refresh_provider_admission(tmp_path):
    store = _ReadGateCAS(tmp_path / "cas")
    ctx, node, workflow, executor = _setup(store)
    state = ExperimentState(run_id="R_deadline", params={"seed": 7})
    first = await executor.execute(workflow, state)
    assert first.report.status == "ok"
    events = _events(ctx)
    cache_ref = ArtifactRef.model_validate(
        next(event for event in events if event.get("event") == "NODE_CACHE_STORE")["refs"][
            "outputs"
        ][0]
    )
    assert store.verify(cache_ref).ok
    store.target = str(cache_ref.artifact_id)
    # One seed read remains healthy; the second native lookup consumes the
    # node's absolute deadline before the miss can reach the actual provider.
    store.gate_read = 2
    workflow.nodes[0].timeout_s = 0.2
    release = _release_after_enter(store, 0.4)
    try:
        result = await executor.execute(workflow, state)
        assert not store.release.is_set()
        assert result.report.status == "fail"
        assert result.report.nodes[0].error.code == "node.timeout"
        assert node.calls == 1
        assert result.report.nodes[0].error.details["execution_state"] == "not_admitted"
        assert result.state.params == {"seed": 7}
    finally:
        store.release.set()
        release.join(5)
        assert await asyncio.to_thread(store.finished.wait, 5)
    assert node.calls == 1
    assert store.reads == 2
    assert len(node.refs) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["checkpoint", "run.finalize"])
async def test_entered_mutable_publication_is_unacknowledged_unknown_not_rollback(
    tmp_path, monkeypatch, operation
):
    from polisyos.scientist.orchestration.engine import checkpoint

    store = _WriteGateCAS(tmp_path / "cas")
    ctx, node, workflow, executor = _setup(store, timeout=0.5)
    head_entered = threading.Event()
    head_release = threading.Event()
    head_finished = threading.Event()
    if operation == "checkpoint":
        original_replace = checkpoint.os.replace

        def held_replace(source, target):
            if Path(target).name != checkpoint.CHECKPOINT_HEAD_FILENAME:
                return original_replace(source, target)
            head_entered.set()
            try:
                assert head_release.wait(5)
                return original_replace(source, target)
            finally:
                head_finished.set()

        # The original budget fence has admitted this atomic replacement.
        # Once this real syscall enters, expiry cannot claim rollback; required
        # head durability and history must complete without a caller ACK.
        monkeypatch.setattr(checkpoint.os, "replace", held_replace)
        executor._checkpoint_hook = checkpoint.CASCheckpointHook(
            store=store, run_dir=ctx.run.trace_path.parent
        )

        def release_head():
            assert head_entered.wait(5)
            time.sleep(0.8)
            head_release.set()

        release = threading.Thread(target=release_head)
        release.start()
    else:
        store.target = "core.run_manifest"
        release = _release_after_enter(store, 0.8)
    try:
        with pytest.raises(WorkflowTimeoutError) as failure:
            await executor.execute(
                workflow, ExperimentState(run_id="R_deadline", params={"seed": 7})
            )
        assert failure.value.details["execution_state"] == "unknown"
        assert failure.value.details["publication_operation"] == operation
        assert node.calls == 1
        if operation == "checkpoint":
            assert head_entered.is_set() and not head_release.is_set()
            assert (
                checkpoint.resolve_latest_checkpoint(FileSystemCAS(store.root), "R_deadline")
                is None
            )
            assert ctx.run.run_manifest.outputs == []
        else:
            assert store.finished.is_set()
            assert store.published is not None
            reopened = FileSystemCAS(store.root)
            assert reopened.verify(store.published).ok
            manifest = json.loads(reopened.get_bytes(store.published))
            assert manifest["status"] == "ok"
            assert len(manifest["outputs"]) == 2
            assert sum(event.get("event") == "RUN_FINALIZED" for event in _events(ctx)) == 1
    finally:
        head_release.set()
        store.release.set()
        release.join(5)
    if operation == "checkpoint":
        assert await asyncio.to_thread(head_finished.wait, 5)
        reopened = FileSystemCAS(store.root)
        resolved = checkpoint.resolve_latest_checkpoint(reopened, "R_deadline")
        assert resolved is not None
        head, dto = resolved
        assert reopened.verify(head.checkpoint_ref).ok
        assert dto.metadata.completed_nodes == ["compute"]
        assert dto.state["params"] == {"seed": 7, "result": 14}
        assert len(dto.metadata.cache_entry_refs) == 1
        assert reopened.verify(dto.metadata.cache_entry_refs[0]).ok
        assert not any(event.get("event") == "RUN_FINALIZED" for event in _events(ctx))
    assert node.calls == 1
    assert FileSystemCAS(store.root).verify(node.refs[0]).ok


@pytest.mark.asyncio
async def test_suppressed_checkpoint_cancellation_cannot_admit_new_owner_publication(tmp_path):
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.scientist.orchestration.engine.checkpoint import (
        CASCheckpointHook,
        resolve_latest_checkpoint,
    )
    from polisyos.scientist.orchestration.engine.idempotency import NodeCacheEntry, NodeResultCache

    store = FileSystemCAS(tmp_path / "cas")
    ctx, node, workflow, executor = _setup(store)
    entered = asyncio.Event()
    real = CASCheckpointHook(store=store, run_dir=ctx.run.trace_path.parent)
    completed = []

    class SuppressingHook:
        async def on_node_complete_async(self, **kwargs):
            entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                completed.append("cancelled")
            result = await asyncio.to_thread(real.on_node_complete, **kwargs)
            completed.append("physically_completed")
            return result

    executor._checkpoint_hook = SuppressingHook()
    task = asyncio.create_task(
        executor.execute(workflow, ExperimentState(run_id="R_deadline", params={"seed": 7}))
    )
    await asyncio.wait_for(entered.wait(), 5)
    before = _events(ctx)
    task.cancel()
    with pytest.raises(asyncio.CancelledError, match="execution_state=not_admitted"):
        await task
    assert task.cancelling() == 1
    assert completed == ["cancelled"]
    assert node.calls == 1
    assert _events(ctx) == before
    assert ctx.run.run_manifest.outputs == []
    reopened = FileSystemCAS(store.root)
    resolved = resolve_latest_checkpoint(reopened, "R_deadline")
    assert resolved is None
    assert not (ctx.run.trace_path.parent / "checkpoint_head.json").exists()
    assert not (ctx.run.trace_path.parent / "checkpoint_history.json").exists()
    cache_refs = [
        ArtifactRef.model_validate(ref)
        for row in before
        if row["event"] == "NODE_CACHE_STORE"
        for ref in row["refs"]["outputs"]
    ]
    assert len(cache_refs) == 1 and reopened.verify(cache_refs[0]).ok
    entry = NodeCacheEntry.model_validate(from_canonical_bytes(reopened.get_bytes(cache_refs[0])))
    assert entry.run_id == "R_deadline" and entry.node_id == str(node.spec.metadata.component_id)
    cache = NodeResultCache(reopened, "R_deadline")
    assert cache.load_entry(cache_refs[0])
    cached = cache.get(entry.idempotency_key)
    assert cached is not None and cached.state.params == {"seed": 7, "result": 14}
    assert cached.artifacts == node.refs
    assert reopened.verify(node.refs[0]).ok
