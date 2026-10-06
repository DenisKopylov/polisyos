"""Behavioral cache and process-wire checks for declared state operations."""

from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing
import threading
import time
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner.serialization import (
    deserialize_state,
    serialize_state,
)
from polisyos.scientist.orchestration.engine.runner.state_merge import merge_tier_outcomes
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_NODE_ID = "scientist.node_state_operations@1.0.0"


class _StateOperationsNode:
    """A pure node that explicitly assigns an equal value and deletes a key."""

    def __init__(self) -> None:
        self.calls = 0
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(_NODE_ID),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="State operations",
                description="Pure assignment/deletion fixture",
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


class _StatusNode(_StateOperationsNode):
    def __init__(self, alias: str, status: str = "ok") -> None:
        super().__init__()
        self.alias = alias
        self.status = status
        self.spec = self.spec.model_copy(
            update={
                "metadata": self.spec.metadata.model_copy(
                    update={"component_id": ComponentId.parse(f"scientist.node_{alias}@1.0.0")}
                ),
                "state_reads": [],
                "state_writes": [f"params.{alias}"],
            }
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        self.calls += 1
        if self.status == "fail":
            # Keep the slot occupied until all peers have queued for admission.
            time.sleep(0.05)
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="expected_failure", message="Intentional queue control"),
            )
        if self.status == "skip":
            return NodeOutcome(status="skip", state=state)
        state.params[self.alias] = True
        return NodeOutcome(status="ok", state=state)


def _context(root: Path, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(root)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))


def _state(run_id: str, *, current: bool) -> ExperimentState:
    return ExperimentState(
        run_id=run_id,
        params={
            "seed": 7,
            "same": 9 if current else 4,
            "nullable": "new" if current else None,
            "stale": 2 if current else 1,
            "unrelated": "new" if current else "old",
        },
    )


def _assert_operations(state: ExperimentState) -> None:
    assert state.params == {"seed": 7, "same": 4, "nullable": None, "unrelated": "new"}


@pytest.mark.parametrize("error_policy", ["fail_fast", "continue"])
def test_real_cas_fail_fast_rechecks_queued_work_and_continue_commits_peers(
    tmp_path: Path, error_policy: str
) -> None:
    """The real executor/store route preserves admission and durable state semantics."""
    nodes = [_StatusNode("first", "fail"), *[_StatusNode(alias) for alias in ("b", "c", "d")]]
    registry = NodeRegistry()
    for node in nodes:
        registry.register(node)
    run_id = "queue_" + error_policy
    ctx = _context(tmp_path / "cas", run_id)
    workflow = WorkflowSpec(
        workflow_id="queued_admission",
        error_policy=error_policy,
        nodes=[
            NodeInvocation(alias=node.alias, node_id=node.spec.metadata.component_id)
            for node in nodes
        ],
    )
    hook = CASCheckpointHook(store=ctx.store, run_dir=ctx.store.root / "runs" / run_id)
    result = asyncio.run(
        AsyncWorkflowExecutor(ctx, registry, max_parallelism=1, checkpoint_hook=hook).execute(
            workflow, ExperimentState(run_id=run_id)
        )
    )
    assert result.report.status == "fail"
    checkpoint = resolve_latest_checkpoint(ctx.store, run_id)
    if error_policy == "fail_fast":
        assert [node.calls for node in nodes] == [1, 0, 0, 0]
        assert [record.status for record in result.report.nodes] == ["fail", "skip", "skip", "skip"]
        assert checkpoint is None
        assert result.state.params == {}
    else:
        assert [node.calls for node in nodes] == [1, 1, 1, 1]
        assert checkpoint is not None
        assert checkpoint[1].metadata.completed_nodes == ["b", "c", "d"]
        assert (
            checkpoint[1].state["params"]
            == result.state.params
            == {"b": True, "c": True, "d": True}
        )


@pytest.mark.parametrize("independent_peer", [False, True], ids=["width_one", "width_two"])
def test_native_skip_has_same_persisted_completion_and_resume_semantics_at_each_width(
    tmp_path: Path, independent_peer: bool
) -> None:
    """Adding an independent peer never promotes skipped work to a completed producer."""
    skipped = _StatusNode("skipped", "skip")
    after = _StatusNode("after")
    peer = _StatusNode("peer")
    nodes = [skipped, after, *([peer] if independent_peer else [])]
    registry = NodeRegistry()
    for node in nodes:
        registry.register(node)
    run_id = "skip_width_" + str(int(independent_peer))
    ctx = _context(tmp_path / "cas", run_id)
    workflow = WorkflowSpec(
        workflow_id="skip_completion_width",
        nodes=[
            NodeInvocation(alias="skipped", node_id=skipped.spec.metadata.component_id),
            *(
                [NodeInvocation(alias="peer", node_id=peer.spec.metadata.component_id)]
                if independent_peer
                else []
            ),
            NodeInvocation(
                alias="after",
                node_id=after.spec.metadata.component_id,
                depends_on=["skipped", *(["peer"] if independent_peer else [])],
            ),
        ],
    )
    hook = CASCheckpointHook(store=ctx.store, run_dir=ctx.store.root / "runs" / run_id)
    result = asyncio.run(
        AsyncWorkflowExecutor(ctx, registry, checkpoint_hook=hook).execute(
            workflow, ExperimentState(run_id=run_id)
        )
    )
    assert result.report.status == "ok"
    checkpoint = resolve_latest_checkpoint(ctx.store, run_id)
    assert checkpoint is not None
    assert checkpoint[1].metadata.completed_nodes == [
        *(["peer"] if independent_peer else []),
        "after",
    ]
    assert "skipped" not in checkpoint[1].state["params"]
    resumed = resume_from_checkpoint(ctx.store, run_id, workflow=workflow, registry=registry)
    assert [(record.alias, record.status) for record in resumed.report.nodes] == [
        ("skipped", "skip")
    ]
    assert skipped.calls == 2
    assert after.calls == 1
    assert peer.calls == int(independent_peer)


@pytest.mark.parametrize("backend", ["sync", "async"])
def test_reopened_cache_matches_cold_assign_delete_and_unrelated_state(
    tmp_path: Path, backend: str
) -> None:
    """Warm replay preserves exactly the same operations as a cold invocation."""
    workflow = WorkflowSpec(
        workflow_id="pure_state_operations",
        nodes=[NodeInvocation(alias="writer", node_id=ComponentId.parse(_NODE_ID))],
    )
    node = _StateOperationsNode()
    registry = NodeRegistry()
    registry.register(node)
    run_id = "state-replay-" + backend

    def execute(root: Path, state: ExperimentState):
        ctx = _context(root, state.run_id)
        if backend == "async":
            return asyncio.run(AsyncWorkflowExecutor(ctx, registry).execute(workflow, state))
        return WorkflowExecutor(ctx, registry).execute(workflow, state)

    first = execute(tmp_path / "warm", _state(run_id, current=False))
    assert first.report.status == "ok"
    assert node.calls == 1
    replay = execute(tmp_path / "warm", _state(run_id, current=True))
    assert replay.report.status == "ok"
    assert node.calls == 1  # Real cold-index recovery and CAS hit, no producer rerun.
    _assert_operations(replay.state)

    cold = execute(tmp_path / "cold", _state(run_id + "-cold", current=True))
    assert cold.report.status == "ok"
    assert node.calls == 2
    _assert_operations(cold.state)


@pytest.mark.asyncio
async def test_cancelled_async_cache_write_finishes_without_recovery_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A late complete CAS write is not admitted as a successful cached attempt."""
    run_id = "cancelled_state_replay"
    node = _StateOperationsNode()
    registry = NodeRegistry()
    registry.register(node)
    ctx = _context(tmp_path / "cas", run_id)
    workflow = WorkflowSpec(
        workflow_id="cancelled_cache_publication",
        nodes=[NodeInvocation(alias="writer", node_id=ComponentId.parse(_NODE_ID))],
    )
    entered = threading.Event()
    release = threading.Event()
    original_put_json = ctx.store.put_json

    def blocked_cache_put(value, options, **kwargs):
        if options.kind == "scientist.node_cache_entry":
            entered.set()
            assert release.wait(timeout=10), "test did not release the actual CAS writer"
        return original_put_json(value, options, **kwargs)

    monkeypatch.setattr(ctx.store, "put_json", blocked_cache_put)
    task = asyncio.create_task(
        AsyncWorkflowExecutor(ctx, registry).execute(workflow, _state(run_id, current=False))
    )
    try:
        assert await asyncio.to_thread(entered.wait, 10)
        task.cancel()
        await asyncio.sleep(0)  # Deliver cancellation while the physical writer is blocked.
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    entries = [
        artifact_id
        for artifact_id in ctx.store.iter_artifact_ids()
        if ctx.store.get_manifest(artifact_id).kind == "scientist.node_cache_entry"
    ]
    assert len(entries) == 1
    # The actual backend write finished atomically; cancellation does not mean
    # physical erasure. The entry is nevertheless absent from the recovery log.
    assert ctx.store.get_bytes(entries[0])
    assert ctx.run.trace_path is not None
    cancelled_events = [
        json.loads(line)["event"] for line in ctx.run.trace_path.read_text().splitlines()
    ]
    assert "NODE_CACHE_STORE" not in cancelled_events

    reopened = _context(tmp_path / "cas", run_id)
    result = await AsyncWorkflowExecutor(reopened, registry).execute(
        workflow, _state(run_id, current=True)
    )
    assert result.report.status == "ok"
    assert node.calls == 2
    _assert_operations(result.state)


def _produce_worker_wire(
    root: str, input_path: str, output_path: str, remove_journal: bool
) -> None:
    """Run the actual worker with a fixture node resolved through its registry."""
    import polisyos.scientist.orchestration.engine.registry as registry_module
    from polisyos.scientist.orchestration.engine.runner import _activity_worker
    from polisyos.scientist.orchestration.engine.state_branching import snapshot_state

    def discover_fixture(registry: NodeRegistry) -> None:
        registry.register(_StateOperationsNode())

    # Discovery is the only fixture seam; context/store, branching, retry,
    # outcome transport and tier merge remain their production implementations.
    registry_module.discover_nodes = discover_fixture
    if remove_journal:
        original_serialize = _activity_worker.serialize_outcome

        def omit_journal(outcome: NodeOutcome) -> bytes:
            return original_serialize(
                outcome.model_copy(update={"state": snapshot_state(outcome.state)})
            )

        _activity_worker.serialize_outcome = omit_journal
    wire = _activity_worker.run_node_in_worker_sync(
        {
            "node_id": _NODE_ID,
            "alias": "writer",
            "state_bytes": Path(input_path).read_bytes(),
            "context_meta": {
                "run_id": "process-state-replay",
                "store_backend": "filesystem",
                "store_root": root,
            },
        }
    )
    Path(output_path).write_bytes(wire)


@pytest.mark.parametrize("remove_journal", [False, True], ids=["native", "removed-property"])
def test_spawned_worker_wire_rebases_operations_and_detects_removed_journal(
    tmp_path: Path, remove_journal: bool
) -> None:
    """A real process boundary preserves operations; a plain snapshot does not."""
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "outcome.json"
    original = _state("process-state-replay", current=False)
    input_path.write_bytes(serialize_state(original))
    process = multiprocessing.get_context("spawn").Process(
        target=_produce_worker_wire,
        args=(str(tmp_path / "cas"), str(input_path), str(output_path), remove_journal),
    )
    process.start()
    try:
        process.join(timeout=60)
        assert not process.is_alive(), "worker did not complete within measured safety timeout"
        assert process.exitcode == 0
        current = _state("process-state-replay", current=True)
        merged = merge_tier_outcomes(
            serialize_state(current),
            {"writer": output_path.read_bytes()},
            requested_aliases=["writer"],
            write_specs={"writer": ["params"]},
        )
        state = deserialize_state(merged.state_bytes)
        if remove_journal:
            # Native ok/status, payload state and wire decoding all survive.
            # The semantic oracle still catches the lost write/delete intents.
            assert merged.node_outcomes["writer"].status == "ok"
            assert state.params["unrelated"] == "old"
            with pytest.raises(AssertionError):
                _assert_operations(state)
        else:
            _assert_operations(state)
        assert original.params["stale"] == 1
        assert current.params["unrelated"] == "new"
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
