"""Real CAS/head/history consumers of one checkpoint publication budget."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pytest

from polisyos.common import async_tools
from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine import checkpoint
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import WorkflowTimeoutError
from polisyos.scientist.orchestration.engine.state import ExperimentState
from tests._helpers.run_lifecycle import resume_same_run
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


def _track_checkpoint_head_temp_fds(monkeypatch: pytest.MonkeyPatch) -> set[int]:
    """Track checkpoint-head descriptors without relying on platform fd paths."""
    head_fds: set[int] = set()
    original_mkstemp = checkpoint.tempfile.mkstemp

    def _tracked_mkstemp(*args, **kwargs):
        fd, path = original_mkstemp(*args, **kwargs)
        if kwargs.get("prefix") == ".checkpoint_head_":
            head_fds.add(fd)
        return fd, path

    monkeypatch.setattr(checkpoint.tempfile, "mkstemp", _tracked_mkstemp)
    return head_fds


def _track_checkpoint_writer_files(
    monkeypatch: pytest.MonkeyPatch,
    run_dir: Path,
) -> dict[tuple[int, int], str]:
    """Identify the exact temporary files and run lock passed to ``os.write``."""
    files: dict[tuple[int, int], str] = {}
    original_mkstemp = checkpoint.tempfile.mkstemp
    original_open = checkpoint.os.open

    def _remember(fd: int, purpose: str) -> None:
        stat = checkpoint.os.fstat(fd)
        files[(stat.st_dev, stat.st_ino)] = purpose

    def _tracked_mkstemp(*args, **kwargs):
        fd, path = original_mkstemp(*args, **kwargs)
        prefix = kwargs.get("prefix")
        if prefix in {".checkpoint_head_", ".checkpoint_history_"}:
            _remember(fd, prefix)
        return fd, path

    def _tracked_open(path, *args, **kwargs):
        fd = original_open(path, *args, **kwargs)
        if Path(path) == run_dir / checkpoint.RUN_LOCK_FILENAME:
            _remember(fd, "run-lock")
        return fd

    monkeypatch.setattr(checkpoint.tempfile, "mkstemp", _tracked_mkstemp)
    monkeypatch.setattr(checkpoint.os, "open", _tracked_open)
    return files


def _checkpoint_ref(digest_char: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{digest_char * 64}",
        kind=checkpoint.CHECKPOINT_KIND,
        media_type="application/json",
    )


def test_atomic_checkpoint_head_and_history_complete_positive_short_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "runs" / "R_short_writes"
    file_purposes = _track_checkpoint_writer_files(monkeypatch, run_dir)
    original_write = checkpoint.os.write
    write_counts: dict[str, int] = {}

    def _short_write(fd: int, payload: bytes | memoryview) -> int:
        stat = checkpoint.os.fstat(fd)
        purpose = file_purposes.get((stat.st_dev, stat.st_ino))
        if purpose not in {".checkpoint_head_", ".checkpoint_history_"}:
            return original_write(fd, payload)
        count = max(1, len(payload) // 2)
        write_counts[purpose] = write_counts.get(purpose, 0) + 1
        return original_write(fd, payload[:count])

    monkeypatch.setattr(checkpoint.os, "write", _short_write)
    checkpoint.update_checkpoint_head(
        run_dir,
        run_id="R_short_writes",
        checkpoint_ref=_checkpoint_ref("1"),
        sequence_number=1,
        node_alias="first",
        writer_pid=123,
        writer_hostname="localhost",
    )

    head = checkpoint.load_checkpoint_head(run_dir)
    history = checkpoint.load_checkpoint_history(run_dir)
    assert head is not None and head.sequence_number == 1
    assert history is not None and [entry.sequence_number for entry in history.entries] == [1]
    assert write_counts[".checkpoint_head_"] > 1
    assert write_counts[".checkpoint_history_"] > 1


@pytest.mark.parametrize("file_purpose", ["head", "history"], ids=["head", "history"])
@pytest.mark.parametrize("failure_mode", ["zero", "error"], ids=["zero", "error"])
def test_atomic_checkpoint_write_failure_preserves_previous_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    file_purpose: str,
    failure_mode: str,
) -> None:
    run_dir = tmp_path / "runs" / "R_write_failure"
    checkpoint.update_checkpoint_head(
        run_dir,
        run_id="R_write_failure",
        checkpoint_ref=_checkpoint_ref("2"),
        sequence_number=1,
        node_alias="first",
        writer_pid=123,
        writer_hostname="localhost",
    )
    head_path = run_dir / checkpoint.CHECKPOINT_HEAD_FILENAME
    history_path = run_dir / checkpoint.CHECKPOINT_HISTORY_FILENAME
    prior_head_bytes = head_path.read_bytes()
    prior_history_bytes = history_path.read_bytes()
    prior_head = checkpoint.load_checkpoint_head(run_dir)
    prior_history = checkpoint.load_checkpoint_history(run_dir)
    assert prior_head is not None and prior_history is not None

    file_purposes = _track_checkpoint_writer_files(monkeypatch, run_dir)
    target = ".checkpoint_head_" if file_purpose == "head" else ".checkpoint_history_"
    original_write = checkpoint.os.write
    target_attempts = 0

    def _partial_then_fail(fd: int, payload: bytes | memoryview) -> int:
        nonlocal target_attempts
        stat = checkpoint.os.fstat(fd)
        if file_purposes.get((stat.st_dev, stat.st_ino)) != target:
            return original_write(fd, payload)
        target_attempts += 1
        if target_attempts == 1:
            return original_write(fd, payload[: max(1, len(payload) // 2)])
        if failure_mode == "zero":
            return 0
        raise OSError("controlled checkpoint temporary write failure")

    monkeypatch.setattr(checkpoint.os, "write", _partial_then_fail)
    if file_purpose == "head":
        with pytest.raises(OSError):
            checkpoint.update_checkpoint_head(
                run_dir,
                run_id="R_write_failure",
                checkpoint_ref=_checkpoint_ref("3"),
                sequence_number=2,
                node_alias="second",
                writer_pid=124,
                writer_hostname="localhost",
            )
    else:
        next_head = prior_head.model_copy(
            update={
                "checkpoint_ref": _checkpoint_ref("3"),
                "sequence_number": 2,
                "node_alias": "second",
                "writer_pid": 124,
            }
        )
        next_entry = checkpoint.CheckpointHistoryEntry.model_validate(
            next_head.model_dump(mode="python")
        )
        replacement_history = checkpoint.CheckpointHistory(
            entries=[*prior_history.entries, next_entry]
        )
        with pytest.raises(OSError):
            checkpoint.write_checkpoint_history(run_dir, replacement_history)

    assert target_attempts == 2
    assert head_path.read_bytes() == prior_head_bytes
    assert history_path.read_bytes() == prior_history_bytes
    assert checkpoint.load_checkpoint_head(run_dir) == prior_head
    assert checkpoint.load_checkpoint_history(run_dir) == prior_history
    assert not list(run_dir.glob(".checkpoint_*.tmp"))


@pytest.mark.parametrize("write_mode", ["short", "zero"], ids=["short", "zero"])
def test_run_lock_metadata_write_preserves_flock_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_mode: str,
) -> None:
    run_dir = tmp_path / "runs" / "R_lock_metadata"
    file_purposes = _track_checkpoint_writer_files(monkeypatch, run_dir)
    original_write = checkpoint.os.write
    zero_injected = False

    def _short_or_zero(fd: int, payload: bytes | memoryview) -> int:
        nonlocal zero_injected
        stat = checkpoint.os.fstat(fd)
        if file_purposes.get((stat.st_dev, stat.st_ino)) != "run-lock":
            return original_write(fd, payload)
        if write_mode == "zero" and not zero_injected:
            zero_injected = True
            return 0
        if write_mode == "short":
            return original_write(fd, payload[: max(1, len(payload) // 2)])
        return original_write(fd, payload)

    monkeypatch.setattr(checkpoint.os, "write", _short_or_zero)
    holder = checkpoint.acquire_run_lock(
        run_dir,
        run_id="R_lock_metadata",
        mode="test",
    )
    try:
        metadata = checkpoint.read_run_lock_metadata(run_dir / checkpoint.RUN_LOCK_FILENAME)
        if write_mode == "short":
            assert metadata == holder.metadata
        else:
            assert metadata is None
        with pytest.raises(checkpoint.RunLockError, match="already active"):
            checkpoint.acquire_run_lock(
                run_dir,
                run_id="R_lock_metadata",
                mode="contender",
            )
    finally:
        holder.release()

    reacquired = checkpoint.acquire_run_lock(
        run_dir,
        run_id="R_lock_metadata",
        mode="after-release",
    )
    reacquired.release()
    assert checkpoint.read_run_lock_metadata(run_dir / checkpoint.RUN_LOCK_FILENAME) == (
        reacquired.metadata
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

        def delayed(data, opts, *, return_selected_profile=False):
            if opts.kind == checkpoint.CHECKPOINT_KIND:
                entered.append(threading.get_ident())
                time.sleep(0.04)
            return original(data, opts, return_selected_profile=return_selected_profile)

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
    setup_ctx, node, workflow, setup_executor = _setup(store)
    run_id = "R_cancelled_checkpoint_resume"
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run = RunContext.start(store, registry_bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=setup_ctx.logger)
    executor = AsyncWorkflowExecutor(ctx, setup_executor._registry)
    executor._checkpoint_hook = checkpoint.CASCheckpointHook(
        store=store, run_dir=ctx.run.trace_path.parent
    )
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original_fsync = checkpoint.os.fsync
    checkpoint_head_fds = _track_checkpoint_head_temp_fds(monkeypatch)

    def held_fsync(fd):
        if fd not in checkpoint_head_fds:
            return original_fsync(fd)
        entered.set()
        try:
            assert release.wait(5)
            return original_fsync(fd)
        finally:
            finished.set()

    monkeypatch.setattr(checkpoint.os, "fsync", held_fsync)
    old_task = asyncio.create_task(
        executor.execute(workflow, ExperimentState(run_id=run_id, params={"seed": 7}))
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        old_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await old_task
        old_owner = executor._cache_seed_owner
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
        for _ in range(500):
            if not list(ctx.run.trace_path.parent.glob(".checkpoint_head_*.tmp")):
                break
            await asyncio.sleep(0.002)
    assert checkpoint.resolve_latest_checkpoint(FileSystemCAS(store.root), run_id) is None
    assert not list(ctx.run.trace_path.parent.glob(".checkpoint_head_*.tmp"))

    resumed_run = resume_same_run(store, ctx.run)
    resumed_ctx = ExecutionContext(store=store, run=resumed_run, logger=ctx.logger)
    resumed_executor = AsyncWorkflowExecutor(resumed_ctx, executor._registry)
    current = await resumed_executor.execute(
        workflow, ExperimentState(run_id=run_id, params={"seed": 7})
    )
    assert current.report.status == "ok"
    assert resumed_executor._cache_seed_owner is not old_owner
    assert resumed_executor._workflow_task is asyncio.current_task()
    assert resumed_executor._workflow_cancelling == 0 and old_task.cancelling() == 1
    assert node.calls == 1  # The later actual invocation reuses verified native cache.
    assert len(node.refs) == 1 and FileSystemCAS(store.root).verify(node.refs[0]).ok


@pytest.mark.asyncio
async def test_entered_native_head_cancel_reports_unknown_and_completes_generation(
    tmp_path, monkeypatch
):
    store = FileSystemCAS(tmp_path / "cas")
    ctx, node, workflow, executor = _setup(store)
    hook = checkpoint.CASCheckpointHook(store=store, run_dir=ctx.run.trace_path.parent)
    executor._checkpoint_hook = hook
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = checkpoint.os.replace

    def held_replace(source, target):
        if Path(target).name != checkpoint.CHECKPOINT_HEAD_FILENAME:
            return original(source, target)
        entered.set()
        try:
            assert release.wait(5)
            return original(source, target)
        finally:
            finished.set()

    monkeypatch.setattr(checkpoint.os, "replace", held_replace)
    task = asyncio.create_task(
        executor.execute(workflow, ExperimentState(run_id="R_deadline", params={"seed": 7}))
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        before = _events(ctx)
        task.cancel()
        with pytest.raises(asyncio.CancelledError, match="execution_state=unknown") as failure:
            await task
        assert "publication_operation=checkpoint_head" in str(failure.value)
        assert task.cancelling() == 1 and node.calls == 1
        assert not (ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HEAD_FILENAME).exists()
        assert ctx.run.run_manifest.outputs == [] and _events(ctx) == before
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
        for _ in range(500):
            if (ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HISTORY_FILENAME).exists():
                break
            await asyncio.sleep(0.002)
    _verified_generation(store, ctx.run.trace_path.parent)
    assert hook._sequence == 0 and not any(row["event"] == "RUN_FINALIZED" for row in _events(ctx))
    assert ctx.run.run_manifest.outputs == []
    assert FileSystemCAS(store.root).verify(node.refs[0]).ok


@pytest.mark.asyncio
async def test_queued_native_cas_cancel_reports_not_admitted_without_publication(
    tmp_path, monkeypatch
):
    store, ctx, _, _, _, hook, kwargs = await _native_input(tmp_path)
    before = {str(identity) for identity in store.iter_artifact_ids()}
    # This private product executor has one physical slot to distinguish a real
    # queued operation. It does not restrict cloud tests or other executor pools.
    pool = async_tools._SharedExecutor(max_workers=1)
    occupied, release = threading.Event(), threading.Event()

    def hold_slot():
        occupied.set()
        assert release.wait(5)

    blocker = pool.submit(hold_slot)
    assert await asyncio.to_thread(occupied.wait, 5)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: pool)

    async def publish():
        return await hook.on_node_complete_with_budget_async(
            publication_budget=_budget(None), **kwargs
        )

    task = asyncio.create_task(publish())
    try:
        for _ in range(500):
            if pool._work_queue.qsize() > 0:
                break
            await asyncio.sleep(0.002)
        assert pool._work_queue.qsize() == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError, match="execution_state=not_admitted") as failure:
            await task
        assert "publication_operation=checkpoint_artifact" in str(failure.value)
    finally:
        release.set()
        await asyncio.to_thread(blocker.result, 5)
        await asyncio.to_thread(pool.shutdown, wait=True)
    assert {str(identity) for identity in store.iter_artifact_ids()} == before
    assert not (ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HEAD_FILENAME).exists()
    assert not (ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HISTORY_FILENAME).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deadline", "cancel"])
async def test_real_head_fsync_fence_keeps_previous_generation(tmp_path, monkeypatch, mode):
    store, ctx, _, _, _, hook, kwargs = await _native_input(tmp_path)
    old = await hook.on_node_complete_async(**kwargs)
    run_dir = ctx.run.trace_path.parent
    old_head = (run_dir / checkpoint.CHECKPOINT_HEAD_FILENAME).read_bytes()
    old_history = (run_dir / checkpoint.CHECKPOINT_HISTORY_FILENAME).read_bytes()
    original = checkpoint.os.fsync
    checkpoint_head_fds = _track_checkpoint_head_temp_fds(monkeypatch)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def held_fsync(fd):
        if fd in checkpoint_head_fds:
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

    def delayed_put(data, opts, *, return_selected_profile=False):
        if opts.kind == checkpoint.CHECKPOINT_KIND:
            time.sleep(0.05)
        return original_put(data, opts, return_selected_profile=return_selected_profile)

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
