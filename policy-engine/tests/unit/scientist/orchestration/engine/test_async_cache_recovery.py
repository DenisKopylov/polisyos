"""Real CAS recovery admission, trace publication, and deadline consumers."""

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

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    resolve_latest_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import WorkflowTimeoutError
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_CALLER_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "recovery_test", default="unset"
)


class RecoveryNode:
    def __init__(self) -> None:
        self.calls = 0
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.recovery_consumer@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Recovery consumer",
                description="Assignment, explicit same-value assignment, delete and null consumer",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.seed"],
            state_writes=["params"],
        )

    def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        state.params["result"] = state.params["seed"] * 2
        state.params["same"] = 4
        state.params.pop("deleted", None)
        state.params["nullable"] = None
        return NodeOutcome(status="ok", state=state)


class GatedCAS(FileSystemCAS):
    """Pause one actual immutable cache read; continue through the real backend."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.target: str | None = None
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.target_reads = 0
        self.read_thread: int | None = None
        self.read_context: str | None = None

    def get_bytes(self, artifact_id):
        content_id = str(
            artifact_id.artifact_id if isinstance(artifact_id, ArtifactRef) else artifact_id
        )
        if self.target is not None and content_id == self.target:
            self.target_reads += 1
            if self.target_reads == 1:
                self.read_thread = threading.get_ident()
                self.read_context = _CALLER_CONTEXT.get()
                self.entered.set()
                try:
                    if not self.release.wait(3):
                        raise RuntimeError("physical read watchdog exhausted")
                    return super().get_bytes(artifact_id)
                finally:
                    self.finished.set()
        return super().get_bytes(artifact_id)


def context(store: FileSystemCAS, run_id: str, run_dir: Path) -> ExecutionContext:
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store, bundle.bundle_ref, run_id=run_id, run_dir=run_dir)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger("recovery_consumer"))


def workflow(node: RecoveryNode) -> tuple[WorkflowSpec, NodeRegistry]:
    registry = NodeRegistry()
    registry.register(node)
    return WorkflowSpec(
        workflow_id="cache_recovery",
        nodes=[NodeInvocation(alias="compute", node_id=node.spec.metadata.component_id)],
    ), registry


def state(run_id: str, *, current: bool = False) -> ExperimentState:
    return ExperimentState(
        run_id=run_id,
        params={
            "seed": 7,
            "same": 9 if current else 4,
            "deleted": "remove",
            "nullable": "replace",
            "unrelated": "new" if current else "old",
        },
    )


async def cold_setup(tmp_path: Path, seed_source: str):
    store = GatedCAS(tmp_path / "cas")
    node = RecoveryNode()
    spec, registry = workflow(node)
    run_dir = tmp_path / "run"
    ctx = context(store, "R_cache_recovery", run_dir)
    hook = CASCheckpointHook(store=store, run_dir=run_dir)
    first = AsyncWorkflowExecutor(ctx, registry, checkpoint_hook=hook)
    await first.execute(spec, state(ctx.run.run_manifest.run_id))
    resolved = resolve_latest_checkpoint(store, ctx.run.run_manifest.run_id, run_dir=run_dir)
    assert resolved is not None
    assert resolved[1].metadata.completed_nodes == ["compute"]
    refs = resolved[1].metadata.cache_entry_refs
    assert len(refs) == 1 and store.verify(refs[0].artifact_id).ok
    # A source-issued trace input isolates startup's trace inlet from the
    # separate native executor publication test below.
    ctx.run.trace_path.write_text("", encoding="utf-8")
    if seed_source == "trace":
        ctx.run.emit("scientist.node.compute", "NODE_CACHE_STORE", outputs=refs)
        checkpoint_refs = []
    else:
        checkpoint_refs = refs
    reopened = context(store, ctx.run.run_manifest.run_id, run_dir)
    store.target = str(refs[0].artifact_id)
    executor = AsyncWorkflowExecutor(reopened, registry, checkpoint_cache_seed_refs=checkpoint_refs)
    return store, executor, node, spec, refs


@pytest.mark.parametrize("seed_source", ["trace", "checkpoint"])
@pytest.mark.asyncio
async def test_cold_seed_is_off_loop_and_replays_real_operations(tmp_path: Path, seed_source: str):
    store, executor, node, spec, refs = await cold_setup(tmp_path, seed_source)
    loop_thread = threading.get_ident()
    ticks = 0
    stop = False

    async def neighbor():
        nonlocal ticks
        while not stop:
            if store.entered.is_set() and not store.release.is_set():
                ticks += 1
            await asyncio.sleep(0.002)

    def physical_release():
        assert store.entered.wait(3)
        time.sleep(0.12)
        store.release.set()

    releaser = threading.Thread(target=physical_release)
    releaser.start()
    token = _CALLER_CONTEXT.set("caller-scope")
    peer = asyncio.create_task(neighbor())
    try:
        result = await executor.execute(spec, state("R_cache_recovery", current=True))
    finally:
        _CALLER_CONTEXT.reset(token)
        stop = True
        await peer
        releaser.join(3)
    assert store.read_thread != loop_thread
    assert store.read_context == "caller-scope"
    assert ticks > 0
    assert node.calls == 1
    assert result.report.nodes[0].status == "ok"
    assert result.state.params == {
        "seed": 7,
        "same": 4,
        "nullable": None,
        "unrelated": "new",
        "result": 14,
    }
    assert executor._cache is not None
    key = compute_idempotency_key(node.spec, state("R_cache_recovery", current=True))
    assert executor._cache.get(key) is not None
    assert store.verify(refs[0].artifact_id).ok


@pytest.mark.parametrize("seed_source", ["trace", "checkpoint"])
@pytest.mark.parametrize("end", ["deadline", "cancel"])
@pytest.mark.asyncio
async def test_cold_seed_late_read_cannot_publish_cache(tmp_path: Path, seed_source: str, end: str):
    store, executor, node, spec, _refs = await cold_setup(tmp_path, seed_source)
    # The configured budget includes startup. The physical read remains held
    # beyond its expiry, avoiding a scheduler-speed assertion.
    executor._workflow_timeout_s = 0.5 if end == "deadline" else None
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(executor.execute(spec, state("R_cache_recovery", current=True)))

    def interrupt_then_release():
        assert store.entered.wait(3)
        if end == "cancel":
            loop.call_soon_threadsafe(task.cancel)
        time.sleep(0.75)
        store.release.set()

    helper = threading.Thread(target=interrupt_then_release)
    helper.start()
    try:
        with pytest.raises(WorkflowTimeoutError if end == "deadline" else asyncio.CancelledError):
            await task
        assert not store.release.is_set(), "caller returned only after physical read completed"
        assert executor._cache is None
    finally:
        store.release.set()
        helper.join(3)
        assert await asyncio.to_thread(store.finished.wait, 3)
    # Inspect after the uncancellable worker actually exits: a naive off-loop
    # mutation of self._cache would publish here despite the earlier return.
    await asyncio.sleep(0.02)
    assert executor._cache is None
    assert node.calls == 1
    if end == "deadline":
        assert store.target_reads == 1


@pytest.mark.asyncio
async def test_successful_native_publication_restores_trace_hit_after_reopen(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    node = RecoveryNode()
    spec, registry = workflow(node)
    run_dir = tmp_path / "run"
    first_ctx = context(store, "R_trace_reopen", run_dir)
    await AsyncWorkflowExecutor(first_ctx, registry).execute(spec, state("R_trace_reopen"))
    events = [json.loads(line) for line in first_ctx.run.trace_path.read_text().splitlines()]
    publications = [event for event in events if event["event"] == "NODE_CACHE_STORE"]
    assert len(publications) == 1
    entry_ref = ArtifactRef.model_validate(publications[0]["refs"]["outputs"][0])
    assert store.verify(entry_ref.artifact_id).ok
    # A new store and execution context consume the trace's actual CAS bytes.
    fresh_store = FileSystemCAS(tmp_path / "cas")
    fresh_ctx = context(fresh_store, "R_trace_reopen", run_dir)
    second = await AsyncWorkflowExecutor(fresh_ctx, registry).execute(
        spec, state("R_trace_reopen", current=True)
    )
    assert node.calls == 1
    assert second.report.nodes[0].status == "ok"
    assert second.state.params == {
        "seed": 7,
        "same": 4,
        "nullable": None,
        "unrelated": "new",
        "result": 14,
    }
    cache = NodeResultCache(fresh_store, run_id="R_trace_reopen")
    assert cache.load_entry(entry_ref)
    key = compute_idempotency_key(node.spec, state("R_trace_reopen", current=True))
    assert cache.get(key) is not None


@pytest.mark.parametrize("seed_source", ["trace", "checkpoint"])
@pytest.mark.parametrize("exhausted", ["run", "read"])
@pytest.mark.asyncio
async def test_recovery_respects_read_budget_and_warm_hit_skips_compute_budget(
    tmp_path: Path, seed_source: str, exhausted: str
):
    store, executor, node, spec, _refs = await cold_setup(tmp_path, seed_source)
    store.release.set()
    executor._budget_middleware = BudgetMiddleware(
        BudgetState(
            limits={
                key: BudgetLimit(key=key, max_usd=Decimal(0 if key == exhausted else 1))
                for key in ("run", "read")
            }
        )
    )
    result = await executor.execute(spec, state("R_cache_recovery", current=True))
    assert node.calls == 1
    if exhausted == "read":
        assert store.target_reads == 0
        assert result.report.status == "fail"
        assert result.report.nodes[0].error.code == "node.budget_exhausted"
        assert result.report.nodes[0].error.details == {"budget_key": "read"}
        assert result.state.params["same"] == 9
    else:
        assert store.target_reads > 0
        assert result.report.status == "ok"
        assert result.state.params == {
            "seed": 7,
            "same": 4,
            "nullable": None,
            "unrelated": "new",
            "result": 14,
        }


@pytest.mark.parametrize("seed_source", ["trace", "checkpoint"])
def test_seed_deadline_prevents_any_following_real_read(tmp_path: Path, seed_source: str):
    store = GatedCAS(tmp_path / "cas")
    node = RecoveryNode()
    original = state("R_seed_deadline")
    from polisyos.scientist.orchestration.engine.state_branching import branch_state

    outcome = node.execute(None, branch_state(original, write_paths=("params",)).state)
    key = compute_idempotency_key(node.spec, original)
    ref = NodeResultCache(store, run_id=original.run_id).put(
        key, node_id=str(node.spec.metadata.component_id), outcome=outcome
    )
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        json.dumps(
            {"event": "NODE_CACHE_STORE", "refs": {"outputs": [ref.model_dump(mode="json")]}}
        )
        + "\n"
    )
    store.target = str(ref.artifact_id)
    cache = NodeResultCache(store, run_id=original.run_id)
    deadline = time.perf_counter() + 0.05

    def release():
        assert store.entered.wait(3)
        time.sleep(0.12)
        store.release.set()

    worker = threading.Thread(target=release)
    worker.start()
    try:
        seed = cache.seed_from_trace if seed_source == "trace" else cache.seed_from_entry_refs
        inputs = trace_path if seed_source == "trace" else [ref, ref]
        with pytest.raises(TimeoutError):
            seed(inputs, deadline_monotonic=deadline)
    finally:
        store.release.set()
        worker.join(3)
    assert store.target_reads == 1
    assert cache.size == 0
    assert cache.get(key) is None
