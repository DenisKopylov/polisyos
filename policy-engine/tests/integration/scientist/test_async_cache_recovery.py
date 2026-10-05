"""Real filesystem cold-seed responsiveness, deadline and admission witnesses."""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import threading
import time
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, ArtifactTenantContextInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import (
    AsyncWorkflowExecutor,
    WorkflowTimeoutError,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    resolve_latest_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_READ_CONTEXT = contextvars.ContextVar("cold_seed_read_context", default="unset")


class _OperationsNode:
    def __init__(self) -> None:
        self.calls = 0
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_cold_seed@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Cold seed operations",
                description="Assignment/deletion recovery witness",
                tags=["test"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.seed"],
            state_writes=["params"],
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        self.calls += 1
        state.params["same"] = 4
        state.params["nullable"] = None
        state.params.pop("stale", None)
        return NodeOutcome(status="ok", state=state)


def _context(root: Path, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(root)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))


def _state(run_id: str, *, current: bool = True) -> ExperimentState:
    return ExperimentState(
        run_id=run_id,
        params={
            "seed": 7,
            "same": 9,
            "nullable": "new",
            "stale": 2,
            "unrelated": "new" if current else "old",
        },
    )


async def _persisted_case(root: Path, mode: str):
    run_id = "cold-seed-" + mode
    node = _OperationsNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="cold_seed",
        nodes=[NodeInvocation(alias="writer", node_id=node.spec.metadata.component_id)],
    )
    first_ctx = _context(root, run_id)
    hook = CASCheckpointHook(store=first_ctx.store, run_dir=root / "runs" / run_id)
    first = await AsyncWorkflowExecutor(first_ctx, registry, checkpoint_hook=hook).execute(
        workflow, _state(run_id, current=False)
    )
    assert first.report.status == "ok" and node.calls == 1
    checkpoint = resolve_latest_checkpoint(first_ctx.store, run_id)
    assert checkpoint is not None
    refs = checkpoint[1].metadata.cache_entry_refs
    assert len(refs) == 1
    trace = [json.loads(line) for line in first_ctx.run.trace_path.read_text().splitlines()]
    emitted = [
        ArtifactRef.model_validate(ref)
        for record in trace
        if record.get("event") == "NODE_CACHE_STORE"
        for ref in record["refs"]["outputs"]
    ]
    assert emitted == refs
    ctx = _context(root, run_id)  # Reopen the filesystem store and its cold cache index.
    if mode == "checkpoint":
        ctx.run.trace_path.write_text("")
    return node, registry, workflow, ctx, refs


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["trace", "checkpoint"])
@pytest.mark.parametrize("kind", ["responsive", "deadline", "cancel"])
async def test_cold_seed_yields_and_never_admits_late_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, kind: str
) -> None:
    node, registry, workflow, ctx, refs = await _persisted_case(tmp_path / "cas", mode)
    executor = AsyncWorkflowExecutor(
        ctx,
        registry,
        checkpoint_cache_seed_refs=refs if mode == "checkpoint" else [],
        workflow_timeout_s=0.04 if kind == "deadline" else None,
    )
    entered, released = threading.Event(), threading.Event()
    loop_thread = threading.get_ident()
    read_threads, contexts, later_reads = [], [], []
    real_get = ctx.store.get_bytes
    real_manifest = ctx.store.get_manifest
    first_read = True
    backend_read = threading.local()

    def gated_get(ref):
        nonlocal first_read
        if ref == refs[0].artifact_id and first_read:
            first_read = False
            read_threads.append(threading.get_ident())
            contexts.append(_READ_CONTEXT.get())
            entered.set()
            assert released.wait(3), "watchdog did not release real CAS read"
        elif released.is_set():
            later_reads.append("bytes")
        backend_read.active = True
        try:
            return real_get(ref)
        finally:
            backend_read.active = False

    def observed_manifest(ref):
        # get_bytes internally resolves its manifest. That already-entered
        # synchronous backend operation cannot be interrupted by this boundary.
        if released.is_set() and not getattr(backend_read, "active", False):
            later_reads.append("manifest")
        return real_manifest(ref)

    monkeypatch.setattr(ctx.store, "get_bytes", gated_get)
    monkeypatch.setattr(ctx.store, "get_manifest", observed_manifest)
    loop = asyncio.get_running_loop()
    done = asyncio.Event()
    ticks = 0
    token = _READ_CONTEXT.set("cold-owner")

    async def neighbor():
        nonlocal ticks
        while not done.is_set():
            await asyncio.sleep(0.001)
            if entered.is_set() and not released.is_set():
                ticks += 1

    task = asyncio.create_task(executor.execute(workflow, _state(ctx.run.run_manifest.run_id)))

    def watchdog():
        assert entered.wait(3), "native cache recovery read not reached"
        if kind == "cancel":
            loop.call_soon_threadsafe(task.cancel)
        time.sleep(0.12)
        released.set()

    watcher = threading.Thread(target=watchdog)
    watcher.start()
    ready = asyncio.create_task(neighbor())
    try:
        if kind == "responsive":
            result = await task
            assert result.report.status == "ok"
            assert result.state.params == {
                "seed": 7,
                "same": 4,
                "nullable": None,
                "unrelated": "new",
            }
            assert node.calls == 1
            assert executor._cache is not None and executor._cache.size == 1
        else:
            error = WorkflowTimeoutError if kind == "deadline" else asyncio.CancelledError
            with pytest.raises(error):
                await task
            assert not released.is_set(), "cold recovery outlived cancellation/deadline"
            assert executor._cache is None
            # A worker from the old attempt cannot mutate or replace a new owner's cache.
            replacement = NodeResultCache(ctx.store, run_id="next-owner")
            executor._cache = replacement
        await asyncio.to_thread(watcher.join)
        await asyncio.sleep(0.03)  # Let the physical read and private worker finish.
        assert read_threads and all(thread != loop_thread for thread in read_threads)
        assert contexts == ["cold-owner"]  # Existing shared boundary propagates ContextVar.
        assert ticks > 0, "ready coroutine made no progress during actual CAS recovery read"
        assert node.calls == 1
        if kind != "responsive":
            assert executor._cache is replacement and replacement.size == 0
            if kind == "deadline":
                assert later_reads == [], "expired worker issued another CAS read"
        print(
            {
                "source": mode,
                "kind": kind,
                "ready_ticks": ticks,
                "worker_read": read_threads[0] != loop_thread,
                "producer_calls": node.calls,
            }
        )
    finally:
        released.set()
        done.set()
        await ready
        await asyncio.to_thread(watcher.join)
        _READ_CONTEXT.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("negative", ["scope", "permission", "tamper"])
async def test_cold_seed_preserves_real_read_and_custody_checks(tmp_path: Path, negative: str):
    _node, _registry, _workflow, ctx, refs = await _persisted_case(tmp_path / "cas", "trace")
    positive = NodeResultCache(ctx.store, run_id=ctx.run.run_manifest.run_id)
    assert positive.seed_from_entry_refs(refs) == 1
    tenant = ArtifactTenantContextInfo(tenant_id="foreign", cell_id="foreign")
    cache = NodeResultCache(
        ctx.store,
        run_id=ctx.run.run_manifest.run_id,
        tenant_context=tenant if negative == "scope" else None,
    )
    payload = ctx.store._paths(refs[0].artifact_id)[0]
    original, permissions = payload.read_bytes(), payload.stat().st_mode
    try:
        if negative == "permission":
            payload.chmod(0)
            with pytest.raises(PermissionError):
                ctx.store.get_bytes(refs[0].artifact_id)
        elif negative == "tamper":
            payload.write_bytes(original + b" ")
            assert not ctx.store.verify(refs[0].artifact_id).ok
        assert cache.seed_from_entry_refs(refs) == 0 and cache.size == 0
    finally:
        payload.chmod(permissions)
        payload.write_bytes(original)


@pytest.mark.asyncio
async def test_cold_seed_respects_read_budget_before_recovery_io(tmp_path: Path, monkeypatch):
    node, registry, workflow, ctx, _refs = await _persisted_case(tmp_path / "cas", "trace")
    budget = BudgetMiddleware(
        BudgetState(
            limits={"read": BudgetLimit(key="read", max_usd=Decimal("1"))},
            spent={"read": Decimal("1")},
        )
    )
    reads = []
    actual = ctx.store.get_bytes

    def observed(ref):
        reads.append(ref)
        return actual(ref)

    monkeypatch.setattr(ctx.store, "get_bytes", observed)
    result = await AsyncWorkflowExecutor(ctx, registry, budget_middleware=budget).execute(
        workflow, _state(ctx.run.run_manifest.run_id)
    )
    assert result.report.status == "fail" and node.calls == 1
    assert result.report.nodes[0].error.details["budget_key"] == "read"
    assert reads == []


@pytest.mark.asyncio
async def test_workflow_body_receives_only_deadline_remaining_after_startup(tmp_path: Path):
    node = _OperationsNode()
    registry = NodeRegistry()
    registry.register(node)
    ctx = _context(tmp_path / "cas", "residual-deadline")
    executor = AsyncWorkflowExecutor(ctx, registry, workflow_timeout_s=0.4)
    workflow = WorkflowSpec(
        workflow_id="residual_deadline",
        nodes=[
            NodeInvocation(alias="uncached", node_id=node.spec.metadata.component_id),
        ],
    )
    started = time.perf_counter()
    original_persist = executor._persist_workflow_spec

    async def delayed_persist(spec):
        await asyncio.sleep(0.2)
        return await original_persist(spec)

    # Real persistence followed by a readiness body deliberately longer than the residue.
    executor._persist_workflow_spec = delayed_persist
    entered = asyncio.Event()

    async def body(*args, **kwargs):
        entered.set()
        await asyncio.sleep(0.25)
        return NodeOutcome(status="ok", state=args[2]), 0, False, None

    executor._execute_node = body
    with pytest.raises(WorkflowTimeoutError):
        await executor.execute(workflow, _state(ctx.run.run_manifest.run_id))
    assert entered.is_set()
    assert time.perf_counter() - started < 0.65


@pytest.mark.asyncio
async def test_expired_startup_never_starts_recovery_or_producer(tmp_path: Path, monkeypatch):
    node = _OperationsNode()
    registry = NodeRegistry()
    registry.register(node)
    ctx = _context(tmp_path / "cas", "expired-startup")
    executor = AsyncWorkflowExecutor(ctx, registry, workflow_timeout_s=0.03)
    workflow = WorkflowSpec(
        workflow_id="expired_startup",
        nodes=[
            NodeInvocation(alias="writer", node_id=node.spec.metadata.component_id),
        ],
    )
    original = executor._persist_workflow_spec

    async def slow_persist(spec):
        await asyncio.sleep(0.05)
        return await original(spec)

    executor._persist_workflow_spec = slow_persist
    reads = []
    actual_get = ctx.store.get_bytes

    def observed(ref):
        reads.append(ref)
        return actual_get(ref)

    monkeypatch.setattr(ctx.store, "get_bytes", observed)
    with pytest.raises(WorkflowTimeoutError):
        await executor.execute(workflow, _state(ctx.run.run_manifest.run_id))
    assert executor._cache is None and node.calls == 0 and reads == []


@pytest.mark.asyncio
async def test_bounded_read_timeout_without_workflow_deadline_quarantines_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from polisyos.common import async_tools

    node, registry, _workflow, ctx, _refs = await _persisted_case(tmp_path / "cas", "trace")
    executor = AsyncWorkflowExecutor(ctx, registry)
    entered, released, finished = threading.Event(), threading.Event(), threading.Event()
    actual_get = ctx.store.get_bytes

    def gated(ref):
        entered.set()
        assert released.wait(3)
        try:
            return actual_get(ref)
        finally:
            finished.set()

    monkeypatch.setattr(ctx.store, "get_bytes", gated)
    # Exercise the existing helper's bounded read wait without pretending its
    # default is a configured workflow deadline or waiting thirty seconds.
    monkeypatch.setattr(async_tools, "_DEFAULT_TIMEOUT_SECONDS", 0.03)
    try:
        await executor._seed_cache(run_id=ctx.run.run_manifest.run_id, workflow_id="read_wait")
        assert entered.is_set() and not released.is_set()
        assert executor._workflow_deadline is None
        exposed = executor._cache
        assert exposed is not None and exposed.size == 0
    finally:
        released.set()
    assert await asyncio.to_thread(finished.wait, 3)
    await asyncio.sleep(0.02)
    assert executor._cache is exposed and exposed.size == 0 and node.calls == 1


@pytest.mark.asyncio
async def test_superseded_recovery_cannot_replace_current_owner_cache(tmp_path: Path, monkeypatch):
    _node, registry, _workflow, ctx, _refs = await _persisted_case(tmp_path / "cas", "trace")
    executor = AsyncWorkflowExecutor(ctx, registry)
    entered, released = threading.Event(), threading.Event()
    actual_get = ctx.store.get_bytes
    first = True

    def gated(ref):
        nonlocal first
        if first:
            first = False
            entered.set()
            assert released.wait(3)
        return actual_get(ref)

    monkeypatch.setattr(ctx.store, "get_bytes", gated)
    old = asyncio.create_task(
        executor._seed_cache(run_id=ctx.run.run_manifest.run_id, workflow_id="old_attempt")
    )
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        await executor._seed_cache(run_id="current-owner", workflow_id="current_attempt")
        current = executor._cache
        assert current is not None and current.run_id == "current-owner" and current.size == 0
        released.set()
        with pytest.raises(RuntimeError, match="superseded"):
            await old
        assert executor._cache is current and current.size == 0
    finally:
        released.set()
        await asyncio.gather(old, return_exceptions=True)
