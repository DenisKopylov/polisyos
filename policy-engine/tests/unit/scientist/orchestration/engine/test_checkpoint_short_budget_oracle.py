"""Real filesystem phase barriers for one checkpoint publication owner."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
from pathlib import Path

import pytest

import polisyos.common.async_tools as async_tools
import polisyos.scientist.orchestration.engine.checkpoint as checkpoint_module
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointGCPolicy,
    compute_workflow_fingerprint,
    create_checkpoint,
    load_checkpoint_head,
    load_checkpoint_history,
    resolve_latest_checkpoint,
    update_checkpoint_head,
)
from polisyos.scientist.orchestration.engine.errors import WorkflowTimeoutError
from polisyos.scientist.orchestration.engine.state import ExperimentState

from .test_checkpoint_deadline_budget_oracle import _execution, _source_observation, _wait_event


@pytest.mark.asyncio
async def test_real_checkpoint_healthy_control(tmp_path: Path) -> None:
    sources = _source_observation()
    store, run_dir, node, executor, workflow = _execution(tmp_path, deadline=20)
    result = await executor.execute(workflow, ExperimentState(run_id="R_budget"))
    reopened = FileSystemCAS(store.root)
    resolved = resolve_latest_checkpoint(reopened, "R_budget", run_dir=run_dir)
    assert resolved is not None and resolved[1].state is not None
    observed = {
        "sources": sources,
        "report_status": result.report.status,
        "producer_calls": node.calls,
        "verified": reopened.verify(resolved[0].checkpoint_ref).ok,
        "completed_nodes": resolved[1].metadata.completed_nodes,
        "answer": resolved[1].state["params"]["answer"],
    }
    print("CHECKPOINT_HEALTHY_ORACLE=" + json.dumps(observed, sort_keys=True), flush=True)
    assert result.report.status == "ok" and node.calls == 1
    assert observed["verified"] is True and observed["answer"] == 7
    assert result.state.last_checkpoint_ref == resolved[0].checkpoint_ref


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage,stop",
    [
        ("artifact", "deadline"),
        ("head_fsync", "deadline"),
        ("head_fsync", "cancel"),
        ("head_return", "deadline"),
        ("gc_read", "deadline"),
    ],
)
async def test_original_budget_refuses_new_phases_and_retains_entered_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, stop: str
) -> None:
    sources = _source_observation()
    store, run_dir, node, executor, workflow = _execution(tmp_path, deadline=2)
    # GC receives actual complete CAS checkpoints and their canonical history,
    # not fabricated marker files. Their state is fixture input, not authority.
    if stage == "gc_read":
        fingerprint = compute_workflow_fingerprint(workflow)
        for sequence in range(3):
            created = create_checkpoint(
                store,
                run_id="R_budget",
                state=ExperimentState(run_id="R_budget", params={"seed": sequence}).model_dump(),
                sequence_number=sequence,
                completed_node_alias="fixture",
                completed_node_id=str(node.spec.metadata.component_id),
                completed_nodes=[],
                workflow_id=workflow.workflow_id,
                workflow_fingerprint=fingerprint,
                fsm_phase="UNKNOWN",
                cache_entry_refs=[],
            )
            update_checkpoint_head(
                run_dir,
                run_id="R_budget",
                checkpoint_ref=created.checkpoint_ref,
                sequence_number=sequence,
                node_alias="fixture",
                writer_pid=os.getpid(),
                writer_hostname="fixture",
            )
        hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            sequence_start=3,
            gc_policy=CheckpointGCPolicy(max_checkpoints=1),
        )
        executor = AsyncWorkflowExecutor(
            executor._ctx, executor._registry, checkpoint_hook=hook, workflow_timeout_s=2
        )

    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    original_put = store.put_json
    original_head = checkpoint_module.update_checkpoint_head
    original_gc = checkpoint_module.gc_checkpoints
    original_mkstemp, original_fsync, original_replace = tempfile.mkstemp, os.fsync, os.replace
    original_read = Path.read_bytes
    original_read_text = Path.read_text
    head_fds: set[int] = set()
    gc_thread: list[int] = []
    counts = {"checkpoint_put": 0, "head_replace": 0, "gc_entered": 0}
    history_path = run_dir / "checkpoint_history.json"
    history_at_gate: list[bytes] = []

    def barrier() -> None:
        entered.set()
        if not release.wait(15):
            raise TimeoutError("Independent fixture watchdog expired before release")

    def observed_put(obj: object, opts: object, **kwargs: object):
        if opts.kind == "scientist.checkpoint":
            counts["checkpoint_put"] += 1
            if stage == "artifact":
                barrier()
        try:
            return original_put(obj, opts, **kwargs)
        finally:
            if stage == "artifact" and opts.kind == "scientist.checkpoint":
                completed.set()

    def observed_head(*args: object, **kwargs: object) -> None:
        try:
            original_head(*args, **kwargs)
            if stage == "head_return":
                barrier()
        finally:
            if stage in {"head_fsync", "head_return"}:
                completed.set()

    def observed_gc(*args: object, **kwargs: object) -> int:
        counts["gc_entered"] += 1
        gc_thread.append(threading.get_ident())
        try:
            return original_gc(*args, **kwargs)
        finally:
            if stage == "gc_read":
                completed.set()

    def observed_mkstemp(*args: object, **kwargs: object):
        fd, path = original_mkstemp(*args, **kwargs)
        if Path(path).parent == run_dir and Path(path).name.startswith(".checkpoint_head_"):
            head_fds.add(fd)
        return fd, path

    def observed_fsync(fd: int) -> None:
        if stage == "head_fsync" and fd in head_fds:
            barrier()
        original_fsync(fd)

    def observed_replace(source: str | Path, destination: str | Path) -> None:
        if Path(destination) == run_dir / "checkpoint_head.json":
            counts["head_replace"] += 1
        original_replace(source, destination)

    def observed_read_text(path: Path, *args: object, **kwargs: object) -> str:
        if stage == "gc_read" and path == history_path and threading.get_ident() in gc_thread:
            history_at_gate.append(original_read(path))
            barrier()
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(store, "put_json", observed_put)
    monkeypatch.setattr(checkpoint_module, "update_checkpoint_head", observed_head)
    monkeypatch.setattr(checkpoint_module, "gc_checkpoints", observed_gc)
    monkeypatch.setattr(tempfile, "mkstemp", observed_mkstemp)
    monkeypatch.setattr(os, "fsync", observed_fsync)
    monkeypatch.setattr(os, "replace", observed_replace)
    monkeypatch.setattr(Path, "read_text", observed_read_text)
    task = asyncio.create_task(executor.execute(workflow, ExperimentState(run_id="R_budget")))
    error: BaseException | None = None
    result = None
    try:
        await _wait_event(entered)
        if stop == "cancel":
            task.cancel()
        try:
            result = await task
        except BaseException as exc:
            error = exc
        observed = {
            "sources": sources,
            "stage": stage,
            "stop": stop,
            "budget_seconds": 2,
            "error_type": type(error).__name__ if error is not None else None,
            "error_details": dict(error.details)
            if isinstance(error, WorkflowTimeoutError)
            else None,
            "accepted_result": result is not None,
            "head_at_return": load_checkpoint_head(run_dir) is not None,
            "physical_workers_at_return": async_tools.get_shared_executor()._physical_workers,
            "reserved_jobs_at_return": async_tools.get_shared_executor()._outstanding_jobs,
            "physical_finished_at_return": completed.is_set(),
            "counts_at_return": dict(counts),
        }
    finally:
        release.set()
        await _wait_event(completed)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    # A completed Future is not enough: observe the canonical physical worker
    # and reservation retiring after the actual delegated operation returns.
    async with asyncio.timeout(10):
        while async_tools.get_shared_executor()._physical_workers:
            await asyncio.sleep(0.001)
    reopened = FileSystemCAS(store.root)
    head = load_checkpoint_head(run_dir)
    observed.update(
        counts_after_physical_return=dict(counts),
        physical_workers_after=async_tools.get_shared_executor()._physical_workers,
        reserved_jobs_after=async_tools.get_shared_executor()._outstanding_jobs,
        head_after_physical_return=head is not None,
        producer_calls=node.calls,
        history_unchanged_after_gc_read=(
            original_read(history_path) == history_at_gate[0] if history_at_gate else None
        ),
        history_entries=(len(load_checkpoint_history(run_dir).entries) if head else 0),
    )
    if head is not None:
        resolved = resolve_latest_checkpoint(reopened, "R_budget", run_dir=run_dir)
        assert resolved is not None and resolved[1].state is not None
        observed["reopened_answer"] = resolved[1].state["params"].get("answer")
        observed["checkpoint_verified"] = reopened.verify(head.checkpoint_ref).ok
    print("CHECKPOINT_SHORT_ORACLE=" + json.dumps(observed, sort_keys=True), flush=True)
    assert result is None and error is not None, observed
    assert observed["physical_workers_at_return"] == observed["reserved_jobs_at_return"] == 1
    assert observed["physical_finished_at_return"] is False
    assert observed["physical_workers_after"] == observed["reserved_jobs_after"] == 0
    if stop == "deadline":
        assert isinstance(error, WorkflowTimeoutError), observed
        assert observed["error_details"]["execution_state"] == "unknown", observed
    else:
        assert isinstance(error, asyncio.CancelledError), observed
    if stage in {"artifact", "head_fsync"}:
        assert head is None and counts["head_replace"] == counts["gc_entered"] == 0, observed
    else:
        # The head published on time remains valid; expiry is not rollback.
        assert head is not None and observed["checkpoint_verified"] is True, observed
        assert observed["reopened_answer"] == 7, observed
        if stage == "head_return":
            assert counts["gc_entered"] == 0, observed
        else:
            assert observed["history_unchanged_after_gc_read"] is True, observed
