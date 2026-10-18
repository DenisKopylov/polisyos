"""Behavioral checks for cache-worker timeout and cancellation ownership."""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_NODE_ID = "test.blocking_cache_writer@1.0.0"
_RUN_ID = "blocking-cache-writer-run"


class _CacheWriterNode:
    def __init__(self) -> None:
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(_NODE_ID),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Blocking cache writer test node",
                description="Produces one cacheable state mutation.",
                tags=["test"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.seed"],
            state_writes=["params.result"],
            produces=[],
        )
        self.calls = 0

    def execute(self, ctx, state):
        del ctx
        self.calls += 1
        state.params["result"] = self.calls
        return NodeOutcome(status="ok", state=state)

    async def execute_async(self, ctx, state):
        """Use the declared async node route so cache timeout tests reach the cache."""
        return self.execute(ctx, state)


def _make_executor(tmp_path: Path, *, workflow_timeout_s: float | None = None):
    store = FileSystemCAS(tmp_path / "cas")
    run = MagicMock()
    run.trace_path = None
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    node = _CacheWriterNode()
    registry = NodeRegistry()
    registry.register(node)
    executor = AsyncWorkflowExecutor(ctx, registry, workflow_timeout_s=workflow_timeout_s)
    cache = NodeResultCache(store, run_id=_RUN_ID)
    executor._cache = cache
    invocation = NodeInvocation(alias="cached", node_id=_NODE_ID)
    workflow = WorkflowSpec(workflow_id="blocking_cache_writer", nodes=[invocation])
    state = ExperimentState(run_id=_RUN_ID, params={"seed": 1})
    cache_key = compute_idempotency_key(
        spec=node.spec,
        state=state,
        bind_params=invocation.params,
    )
    return store, run, executor, cache, invocation, workflow, state, cache_key


def _event_types(run) -> list[str]:
    return [call.args[1] for call in run.emit.call_args_list if len(call.args) >= 2]


def _cache_entry_ids(store: FileSystemCAS) -> set[str]:
    return {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "scientist.node_cache_entry"
    }


async def _wait_for_thread_event(event: threading.Event) -> None:
    async def poll() -> None:
        while not event.is_set():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(poll(), timeout=3.0)


def _hold_cache_entry_write(store: FileSystemCAS, cache: NodeResultCache, cache_key: str):
    entered = threading.Event()
    release = threading.Event()
    write_finished = threading.Event()
    worker_discarded = threading.Event()
    index_admitted = threading.Event()
    worker_ident: int | None = None
    original_put_json = store.put_json
    original_discard = cache.discard
    original_index_set = cache._index.set

    def delayed_put_json(obj, opts, canon_spec=None, *, return_selected_profile=False):
        nonlocal worker_ident
        if str(getattr(opts, "kind", "")) == "scientist.node_cache_entry":
            worker_ident = threading.get_ident()
            entered.set()
            release.wait()
            try:
                return original_put_json(
                    obj,
                    opts,
                    canon_spec=canon_spec,
                    return_selected_profile=return_selected_profile,
                )
            finally:
                write_finished.set()
        return original_put_json(
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )

    def recording_discard(key: str) -> None:
        original_discard(key)
        if worker_ident is not None and threading.get_ident() == worker_ident:
            worker_discarded.set()

    def recording_index_set(key: str, value) -> None:
        original_index_set(key, value)
        if key == cache_key:
            index_admitted.set()

    store.put_json = delayed_put_json
    cache.discard = recording_discard
    cache._index.set = recording_index_set
    return entered, release, write_finished, worker_discarded, index_admitted


def test_cache_timeout_returns_before_writer_finishes_and_refuses_late_cache_admission(
    tmp_path: Path,
) -> None:
    """Timeout fences the cache ref/event though immutable CAS I/O may finish later."""
    store, run, executor, cache, invocation, workflow, state, cache_key = _make_executor(
        tmp_path,
        workflow_timeout_s=0.25,
    )
    entered, release, write_finished, worker_discarded, index_admitted = _hold_cache_entry_write(
        store, cache, cache_key
    )

    async def scenario() -> None:
        result_task = asyncio.create_task(
            executor._execute_node("cached", invocation, state, workflow)
        )
        release_watchdog = threading.Timer(2.0, release.set)
        release_watchdog.start()
        try:
            await _wait_for_thread_event(entered)
            done, _pending = await asyncio.wait({result_task}, timeout=0.75)
            assert result_task in done, "cache timeout owner waited for the physical writer"
            result = result_task.result()
            assert result[0].status == "ok"
            assert any(event.code == "node.cache_bypass" for event in result[0].events)
            assert not release.is_set()
            assert not write_finished.is_set()
            assert not index_admitted.is_set()
            assert "NODE_CACHE_STORE" not in _event_types(run)
        finally:
            release.set()
            release_watchdog.cancel()
            if not result_task.done():
                await asyncio.gather(result_task, return_exceptions=True)

        await _wait_for_thread_event(write_finished)
        await _wait_for_thread_event(worker_discarded)
        assert not index_admitted.is_set()
        assert not cache._pending_io
        assert cache.size == 0
        assert cache.has(cache_key) is False
        assert "NODE_CACHE_STORE" not in _event_types(run)
        # A FileSystemCAS object is immutable and may remain after refusal; only
        # the current cache index and owner event are fenced by this path.
        assert len(_cache_entry_ids(store)) == 1

    asyncio.run(scenario())


@pytest.mark.asyncio
async def test_caller_cancellation_waits_for_cache_writer_then_reconciles(tmp_path: Path) -> None:
    """Cancellation waits for a running writer, then removes its current cache key."""
    store, run, executor, cache, invocation, workflow, state, cache_key = _make_executor(tmp_path)
    entered, release, write_finished, worker_discarded, index_admitted = _hold_cache_entry_write(
        store, cache, cache_key
    )
    task = asyncio.create_task(executor._execute_node("cached", invocation, state, workflow))
    try:
        await _wait_for_thread_event(entered)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert not write_finished.is_set()
        assert not index_admitted.is_set()
        assert "NODE_CACHE_STORE" not in _event_types(run)
    finally:
        release.set()

    with pytest.raises(asyncio.CancelledError):
        await task
    await _wait_for_thread_event(write_finished)
    await _wait_for_thread_event(worker_discarded)
    assert not cache._pending_io
    assert cache.size == 0
    assert cache.has(cache_key) is False
    assert "NODE_CACHE_STORE" not in _event_types(run)
    assert len(_cache_entry_ids(store)) == 1


@pytest.mark.asyncio
async def test_completed_cache_writer_publishes_current_ref_and_owner_event(tmp_path: Path) -> None:
    """The ordinary success path admits the cache entry only after the writer returns."""
    store, run, executor, cache, invocation, workflow, state, cache_key = _make_executor(tmp_path)

    outcome, _duration_ms, cache_hit, _cache_ref = await executor._execute_node(
        "cached", invocation, state, workflow
    )

    assert outcome.status == "ok"
    assert cache_hit is False
    assert cache.has(cache_key)
    assert cache.size == 1
    assert not cache._pending_io
    assert "NODE_CACHE_STORE" in _event_types(run)
    assert len(_cache_entry_ids(store)) == 1
