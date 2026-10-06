"""Real CAS/head/history consumers of one checkpoint publication budget."""

from __future__ import annotations

import asyncio
import os
import threading
import time
from pathlib import Path

import pytest

from polisyos.common import async_tools
from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.orchestration.engine import checkpoint
from polisyos.scientist.orchestration.engine.errors import WorkflowTimeoutError
from polisyos.scientist.orchestration.engine.state import ExperimentState
from tests.unit.scientist.orchestration.engine.test_workflow_deadline_custody import (
    _events,
    _setup,
)


def _budget(seconds):
    task = asyncio.current_task()
    baseline = task.cancelling()
    return checkpoint.CheckpointPublicationBudget(
        deadline_monotonic=time.monotonic() + seconds if seconds is not None else None,
        owner_is_current=lambda: True,
        caller_cancelled=lambda: task.cancelling() > baseline,
    )


async def _native_input(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    ctx, node, workflow, executor = _setup(store, timeout=2)
    outcome = await node.execute_async(
        ctx, ExperimentState(run_id="R_deadline", params={"seed": 7})
    )
    hook = checkpoint.CASCheckpointHook(store=store, run_dir=ctx.run.trace_path.parent)
    kwargs = {
        "state": outcome.state,
        "alias": "compute",
        "node_id": str(node.spec.metadata.component_id),
        "completed_nodes": ["compute"],
        "workflow_id": workflow.workflow_id,
        "workflow_fingerprint": checkpoint.compute_workflow_fingerprint(workflow),
        "cache_entry_ref": None,
    }
    return store, ctx, node, workflow, executor, hook, kwargs


def _verified_generation(store, run_dir):
    reopened = FileSystemCAS(store.root)
    resolved = checkpoint.resolve_latest_checkpoint(reopened, "R_deadline", run_dir=run_dir)
    assert resolved is not None
    head, dto = resolved
    assert reopened.verify(head.checkpoint_ref).ok
    assert dto.metadata.completed_nodes == ["compute"]
    assert dto.state["params"] == {"seed": 7, "result": 14}
    history = checkpoint.load_checkpoint_history(run_dir)
    assert history.entries[-1].checkpoint_ref == head.checkpoint_ref
    return head


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["artifact", "head", "gc"])
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("workflow_timeout", [None, 2])
async def test_native_workflow_budget_replaces_hidden_helper_default(
    tmp_path, monkeypatch, stage, wrapped, workflow_timeout
):
    store = FileSystemCAS(tmp_path / "cas")
    ctx, node, workflow, executor = _setup(store, timeout=workflow_timeout)
    hook = checkpoint.CASCheckpointHook(store=store, run_dir=ctx.run.trace_path.parent)
    monkeypatch.setattr(async_tools, "_DEFAULT_TIMEOUT_SECONDS", 0.01)
    entered = []
    if stage == "artifact":
        original = store.put_bytes

        def delayed(data, opts):
            if opts.kind == checkpoint.CHECKPOINT_KIND:
                entered.append(threading.get_ident())
                time.sleep(0.04)
            return original(data, opts)

        monkeypatch.setattr(store, "put_bytes", delayed)
    else:
        name = "update_checkpoint_head" if stage == "head" else "gc_checkpoints"
        original = getattr(checkpoint, name)

        def delayed(*args, **kwargs):
            entered.append(threading.get_ident())
            time.sleep(0.04)
            return original(*args, **kwargs)

        monkeypatch.setattr(checkpoint, name, delayed)
    if wrapped:

        class FixedSignatureWrapper:
            async def on_node_complete_async(
                self,
                *,
                state,
                alias,
                node_id,
                completed_nodes,
                workflow_id,
                workflow_fingerprint,
                cache_entry_ref,
            ):
                return await hook.on_node_complete_async(
                    state=state,
                    alias=alias,
                    node_id=node_id,
                    completed_nodes=completed_nodes,
                    workflow_id=workflow_id,
                    workflow_fingerprint=workflow_fingerprint,
                    cache_entry_ref=cache_entry_ref,
                )

        executor._checkpoint_hook = FixedSignatureWrapper()
    else:
        executor._checkpoint_hook = hook
    result = await executor.execute(
        workflow, ExperimentState(run_id="R_deadline", params={"seed": 7})
    )
    assert result.report.status == "ok"
    assert entered and all(ident != threading.get_ident() for ident in entered)
    assert node.calls == 1
    head = _verified_generation(store, ctx.run.trace_path.parent)
    assert result.state.last_checkpoint_ref == head.checkpoint_ref
    assert sum(row.get("event") == "RUN_FINALIZED" for row in _events(ctx)) == 1


@pytest.mark.asyncio
async def test_cancelled_checkpoint_cannot_adopt_reused_executor_owner(tmp_path, monkeypatch):
    store = FileSystemCAS(tmp_path / "cas")
    ctx, node, workflow, executor = _setup(store)
    executor._checkpoint_hook = checkpoint.CASCheckpointHook(
        store=store, run_dir=ctx.run.trace_path.parent
    )
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original_fsync = checkpoint.os.fsync

    def held_fsync(fd):
        if ".checkpoint_head_" not in os.readlink(f"/proc/self/fd/{fd}"):
            return original_fsync(fd)
        entered.set()
        try:
            assert release.wait(5)
            return original_fsync(fd)
        finally:
            finished.set()

    monkeypatch.setattr(checkpoint.os, "fsync", held_fsync)
    old_task = asyncio.create_task(
        executor.execute(workflow, ExperimentState(run_id="R_deadline", params={"seed": 7}))
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        old_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await old_task
        old_owner = executor._cache_seed_owner
        executor._checkpoint_hook = None
        current = await executor.execute(
            workflow, ExperimentState(run_id="R_deadline", params={"seed": 7})
        )
        assert current.report.status == "ok"
        assert executor._cache_seed_owner is not old_owner
        assert executor._workflow_task is asyncio.current_task()
        assert executor._workflow_cancelling == 0 and old_task.cancelling() == 1
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
        for _ in range(500):
            if not list(ctx.run.trace_path.parent.glob(".checkpoint_head_*.tmp")):
                break
            await asyncio.sleep(0.002)
    assert checkpoint.resolve_latest_checkpoint(FileSystemCAS(store.root), "R_deadline") is None
    assert not list(ctx.run.trace_path.parent.glob(".checkpoint_head_*.tmp"))
    assert node.calls == 1  # The later actual invocation reuses verified native cache.
    assert len(node.refs) == 1 and FileSystemCAS(store.root).verify(node.refs[0]).ok


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deadline", "cancel"])
async def test_real_head_fsync_fence_keeps_previous_generation(tmp_path, monkeypatch, mode):
    store, ctx, _, _, _, hook, kwargs = await _native_input(tmp_path)
    old = await hook.on_node_complete_async(**kwargs)
    run_dir = ctx.run.trace_path.parent
    old_head = (run_dir / checkpoint.CHECKPOINT_HEAD_FILENAME).read_bytes()
    old_history = (run_dir / checkpoint.CHECKPOINT_HISTORY_FILENAME).read_bytes()
    original = checkpoint.os.fsync
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def held_fsync(fd):
        if ".checkpoint_head_" in os.readlink(f"/proc/self/fd/{fd}"):
            entered.set()
            try:
                assert release.wait(5)
                return original(fd)
            finally:
                finished.set()
        return original(fd)

    monkeypatch.setattr(checkpoint.os, "fsync", held_fsync)

    async def publish():
        return await hook.on_node_complete_with_budget_async(
            publication_budget=_budget(0.15 if mode == "deadline" else None), **kwargs
        )

    task = asyncio.create_task(publish())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if mode == "cancel":
            task.cancel()
        with pytest.raises(WorkflowTimeoutError if mode == "deadline" else asyncio.CancelledError):
            await task
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
        # Join the publication worker through its owned temporary-file cleanup.
        for _ in range(500):
            if not list(run_dir.glob(".checkpoint_head_*.tmp")):
                break
            await asyncio.sleep(0.002)
    assert (run_dir / checkpoint.CHECKPOINT_HEAD_FILENAME).read_bytes() == old_head
    assert (run_dir / checkpoint.CHECKPOINT_HISTORY_FILENAME).read_bytes() == old_history
    assert not list(run_dir.glob(".checkpoint_head_*.tmp"))
    assert _verified_generation(store, run_dir).checkpoint_ref == old.checkpoint_ref
    assert hook._sequence == 1


@pytest.mark.asyncio
async def test_entered_head_replace_finishes_history_but_has_no_ack_or_gc(tmp_path, monkeypatch):
    store, ctx, _, _, _, hook, kwargs = await _native_input(tmp_path)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = checkpoint.os.replace
    gc_calls = []

    def held_replace(source, target):
        if Path(target).name == checkpoint.CHECKPOINT_HEAD_FILENAME:
            entered.set()
            try:
                assert release.wait(5)
                return original(source, target)
            finally:
                finished.set()
        return original(source, target)

    original_gc = checkpoint.gc_checkpoints

    def observed_gc(*args, **kwargs):
        gc_calls.append(True)
        return original_gc(*args, **kwargs)

    monkeypatch.setattr(checkpoint.os, "replace", held_replace)
    monkeypatch.setattr(checkpoint, "gc_checkpoints", observed_gc)
    task = asyncio.create_task(
        hook.on_node_complete_with_budget_async(publication_budget=_budget(0.15), **kwargs)
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        with pytest.raises(WorkflowTimeoutError) as failure:
            await task
        assert failure.value.details["execution_state"] == "unknown"
        assert not (ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HEAD_FILENAME).exists()
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
        for _ in range(500):
            if (ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HISTORY_FILENAME).exists():
                break
            await asyncio.sleep(0.002)
    _verified_generation(store, ctx.run.trace_path.parent)
    assert gc_calls == []
    assert hook._sequence == 0


@pytest.mark.asyncio
async def test_expired_budget_refuses_actual_cas_worker_before_artifact(tmp_path):
    store, ctx, _, _, _, hook, kwargs = await _native_input(tmp_path)
    before = {str(identity) for identity in store.iter_artifact_ids()}
    with pytest.raises(WorkflowTimeoutError):
        await hook.on_node_complete_with_budget_async(publication_budget=_budget(-1), **kwargs)
    assert {str(identity) for identity in store.iter_artifact_ids()} == before
    assert not (ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HEAD_FILENAME).exists()


@pytest.mark.asyncio
async def test_explicit_adapter_limit_is_one_budget_across_artifact_and_head(tmp_path, monkeypatch):
    store, ctx, _, _, _, hook, kwargs = await _native_input(tmp_path)
    hook._async_store = AsyncArtifactStoreAdapter(store, timeout_seconds=0.08)
    original_put = store.put_bytes
    original_head = checkpoint.update_checkpoint_head
    finished = threading.Event()

    def delayed_put(data, opts):
        if opts.kind == checkpoint.CHECKPOINT_KIND:
            time.sleep(0.05)
        return original_put(data, opts)

    def delayed_head(*args, **kwargs):
        try:
            time.sleep(0.05)
            return original_head(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(store, "put_bytes", delayed_put)
    monkeypatch.setattr(checkpoint, "update_checkpoint_head", delayed_head)
    with pytest.raises(WorkflowTimeoutError):
        await hook.on_node_complete_with_budget_async(publication_budget=_budget(2), **kwargs)
    assert await asyncio.to_thread(finished.wait, 5)
    assert not (ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HEAD_FILENAME).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deadline", "cancel"])
async def test_real_gc_read_cannot_admit_expired_history_rewrite(tmp_path, monkeypatch, mode):
    store, ctx, _, _, _, hook, kwargs = await _native_input(tmp_path)
    for _ in range(4):
        result = await hook.on_node_complete_async(**kwargs)
    run_dir = ctx.run.trace_path.parent
    before = (run_dir / checkpoint.CHECKPOINT_HISTORY_FILENAME).read_bytes()
    assert len(checkpoint.load_checkpoint_history(run_dir).entries) == 4
    hook._gc_policy = checkpoint.CheckpointGCPolicy(max_checkpoints=1)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original_load = checkpoint.load_checkpoint_history
    original_gc = checkpoint.gc_checkpoints

    def held_load(path):
        entered.set()
        assert release.wait(5)
        return original_load(path)

    def observed_gc(*args, **kwargs):
        try:
            return original_gc(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(checkpoint, "load_checkpoint_history", held_load)
    monkeypatch.setattr(checkpoint, "gc_checkpoints", observed_gc)

    async def trim():
        return await hook._gc_after_checkpoint_async(
            result,
            run_id="R_deadline",
            publication_budget=_budget(0.15 if mode == "deadline" else None),
        )

    task = asyncio.create_task(trim())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if mode == "cancel":
            task.cancel()
        with pytest.raises(WorkflowTimeoutError if mode == "deadline" else asyncio.CancelledError):
            await task
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
        monkeypatch.setattr(checkpoint, "load_checkpoint_history", original_load)
    assert (run_dir / checkpoint.CHECKPOINT_HISTORY_FILENAME).read_bytes() == before
    assert len(checkpoint.load_checkpoint_history(run_dir).entries) == 4
    _verified_generation(store, run_dir)


@pytest.mark.asyncio
async def test_budgeted_tier_preserves_fixed_signature_subclass_override(tmp_path):
    store, ctx, _, _, _, _, kwargs = await _native_input(tmp_path)

    class StopAfterTier(checkpoint.CASCheckpointHook):
        async def on_tier_complete_async(
            self,
            *,
            state,
            alias,
            node_id,
            completed_nodes,
            workflow_id,
            workflow_fingerprint,
            cache_entry_refs,
        ):
            await super().on_tier_complete_async(
                state=state,
                alias=alias,
                node_id=node_id,
                completed_nodes=completed_nodes,
                workflow_id=workflow_id,
                workflow_fingerprint=workflow_fingerprint,
                cache_entry_refs=cache_entry_refs,
            )
            raise RuntimeError("intentional interrupt after durable tier")

    hook = StopAfterTier(store=store, run_dir=ctx.run.trace_path.parent)
    kwargs.pop("cache_entry_ref")
    with pytest.raises(RuntimeError, match="intentional interrupt"):
        await hook.on_tier_complete_with_budget_async(
            publication_budget=_budget(2), cache_entry_refs=[], **kwargs
        )
    _verified_generation(store, ctx.run.trace_path.parent)
