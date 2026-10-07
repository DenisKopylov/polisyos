"""Independent filesystem oracle for the workflow-owned checkpoint deadline."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path

import pytest

import polisyos.common.async_tools as async_tools
import polisyos.core.artifacts.async_store as async_store
import polisyos.scientist.orchestration.engine.async_executor as executor_module
import polisyos.scientist.orchestration.engine.checkpoint as checkpoint_module
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    load_checkpoint_head,
    resolve_latest_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


class _DurableNode:
    """A real registered producer whose output is consumed after reopen."""

    def __init__(self) -> None:
        self.calls = 0
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.deadline_oracle@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Deadline oracle",
                description="Real CAS checkpoint deadline consumer",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_writes=["params.answer", "reports_index.answer"],
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx, state
        raise AssertionError("This consumer requires the genuine async producer")

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        state.params["answer"] = 7
        state.reports_index["answer"] = ctx.store.put_json(
            {"answer": 7, "producer_calls": self.calls},
            PutOptions(kind="scientist.deadline_oracle", media_type="application/json"),
        )
        return NodeOutcome(status="ok", state=state)


def _source_observation() -> dict[str, object]:
    observed: dict[str, object] = {}
    expected = os.environ.get("E02_ORACLE_PRODUCT_ROOT")
    for module in (async_tools, async_store, executor_module, checkpoint_module):
        path = Path(module.__file__).resolve()
        if expected is not None:
            assert path.is_relative_to(Path(expected).resolve())
        observed[module.__name__] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return observed


async def _wait_event(event: threading.Event, *, timeout: float = 10) -> None:
    async with asyncio.timeout(timeout):
        while not event.is_set():
            await asyncio.sleep(0.001)


def _execution(
    tmp_path: Path, *, deadline: float
) -> tuple[FileSystemCAS, Path, _DurableNode, AsyncWorkflowExecutor, WorkflowSpec]:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="R_budget")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("deadline-oracle"))
    node = _DurableNode()
    registry = NodeRegistry()
    registry.register(node)
    run_dir = store.root / "runs" / "R_budget"
    hook = CASCheckpointHook(store=store, run_dir=run_dir)
    executor = AsyncWorkflowExecutor(
        ctx, registry, checkpoint_hook=hook, workflow_timeout_s=deadline
    )
    workflow = WorkflowSpec(
        workflow_id="deadline_oracle",
        nodes=[NodeInvocation(alias="answer", node_id=node.spec.metadata.component_id)],
    )
    return store, run_dir, node, executor, workflow


@pytest.mark.asyncio
async def test_real_atomic_head_35_seconds_fits_original_60_second_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real replace waits 35s; the owner permits it for 60s, not 30s."""
    sources = _source_observation()
    store, run_dir, node, executor, workflow = _execution(tmp_path, deadline=60)
    entered, completed = threading.Event(), threading.Event()
    original_replace = os.replace
    observed: dict[str, object] = {"sources": sources, "delay_seconds": 35, "budget_seconds": 60}

    def delayed_real_replace(source: str | Path, destination: str | Path) -> None:
        if Path(destination) == run_dir / "checkpoint_head.json":
            entered.set()
            # Real filesystem latency is injected at the actual atomic operation.
            # Its delegated replacement, fsync and history write remain canonical.
            threading.Event().wait(35)
        original_replace(source, destination)
        if Path(destination) == run_dir / "checkpoint_head.json":
            completed.set()

    monkeypatch.setattr(os, "replace", delayed_real_replace)
    started = time.perf_counter()
    result = None
    error: BaseException | None = None
    try:
        result = await executor.execute(workflow, ExperimentState(run_id="R_budget"))
    except BaseException as exc:
        error = exc
    observed.update(
        elapsed_to_return=time.perf_counter() - started,
        entered=entered.is_set(),
        physical_complete_at_return=completed.is_set(),
        error_type=type(error).__name__ if error is not None else None,
        error_message=str(error) if error is not None else None,
        head_at_return=load_checkpoint_head(run_dir) is not None,
        physical_workers_at_return=async_tools.get_shared_executor()._physical_workers,
        reserved_jobs_at_return=async_tools.get_shared_executor()._outstanding_jobs,
        result_status=result.report.status if result is not None else None,
    )
    # Finish the actual entered I/O before teardown; late physical completion
    # remains a separate observation from an accepted workflow frontier.
    await _wait_event(completed, timeout=40)
    await asyncio.sleep(0)
    reopened = FileSystemCAS(store.root)
    resolved = resolve_latest_checkpoint(reopened, "R_budget", run_dir=run_dir)
    assert resolved is not None
    assert resolved[1].state is not None
    observed.update(
        elapsed_physical_complete=time.perf_counter() - started,
        reopened_checkpoint_verified=reopened.verify(resolved[0].checkpoint_ref).ok,
        reopened_completed_nodes=resolved[1].metadata.completed_nodes,
        reopened_answer=resolved[1].state["params"]["answer"],
        producer_calls=node.calls,
    )
    print("CHECKPOINT_BUDGET_ORACLE=" + json.dumps(observed, sort_keys=True), flush=True)
    assert error is None, observed
    assert result is not None and result.report.status == "ok", observed
    assert node.calls == 1 and result.state.last_checkpoint_ref == resolved[0].checkpoint_ref
    assert observed["reopened_checkpoint_verified"] is True
    assert observed["reopened_answer"] == 7
