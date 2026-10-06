"""Native queue and readiness consumers with real CAS effects and lineage."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    resolve_latest_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.metrics_protocol import NoopEngineMetrics
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _spec(alias: str, reads: list[str], writes: list[str]) -> NodeSpec:
    return NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse(f"scientist.admission_{alias}@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name=alias,
            description="Native execution admission consumer",
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_reads=reads,
        state_writes=writes,
    )


def _context(tmp_path: Path, *, metrics=None) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="R_admission")
    return ExecutionContext(
        store=store, run=run, logger=logging.getLogger("native-admission"), metrics=metrics
    )


class _Node:
    def __init__(self, alias: str, *, reads: list[str] | None = None, writes=None) -> None:
        self.alias = alias
        self.spec = _spec(alias, reads or [], writes or [f"reports_index.{alias}"])
        self.calls = 0
        self.started = asyncio.Event()
        self.finished = asyncio.Event()
        self.release: asyncio.Event | None = None
        self.fail = False
        self.refs: list[ArtifactRef] = []
        self.inputs: list[dict] = []
        self.overlap = False

    def execute(self, ctx, state):
        del ctx, state
        raise AssertionError("The actual native admission fixture must use its async provider")

    async def execute_async(self, ctx, state):
        self.calls += 1
        self.started.set()
        inputs = [
            InputRef(
                artifact_id=state.reports_index[key].artifact_id,
                manifest_profile_sha256=state.reports_index[key].manifest_profile_sha256,
                role=key,
            )
            for key in ("a", "b")
            if key in state.reports_index
        ]
        payload = {
            "alias": self.alias,
            "ordinal": self.calls,
            "seed": state.params.get("seed"),
            "c_input": state.params.get("c_input"),
        }
        self.inputs.append(payload)
        effect = ctx.store.put_json(
            payload,
            PutOptions(
                kind="scientist.admission_effect",
                media_type="application/json",
                producer=ProducerInfo(
                    component=str(self.spec.metadata.component_id), version="1.0.0"
                ),
                inputs=inputs,
            ),
        )
        self.refs.append(effect)
        if self.release is not None:
            await self.release.wait()
        if self.fail:
            return NodeOutcome(
                status="fail",
                state=state,
                artifacts=[effect],
                error=NodeError(code="admission.fail", message="Native first producer failure"),
            )
        state.reports_index[self.alias] = effect
        if self.alias == "seed":
            state.params["seed"] = 7
        elif self.alias == "a":
            state.params["a"] = "done"
            state.params["c_input"] = "from-a"
        elif self.alias == "b":
            state.params["b"] = "done"
            if self.overlap:
                state.params["c_input"] = "from-b"
        self.finished.set()
        return NodeOutcome(status="ok", state=state, artifacts=[effect])


class _MetricFailure(NoopEngineMetrics):
    def __init__(self):
        self.failures = 0

    def record_semaphore_wait(self, **kwargs):
        del kwargs
        self.failures += 1
        raise RuntimeError("Actual optional telemetry callback failed after acquisition")


def _registry(*nodes):
    registry = NodeRegistry()
    for node in nodes:
        registry.register(node)
    return registry


async def _until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0)


def _read_effects(ctx, nodes):
    reopened = FileSystemCAS(ctx.store.root)
    for node in nodes:
        assert len(node.refs) == node.calls
        for ref, payload in zip(node.refs, node.inputs, strict=True):
            assert reopened.verify(ref).ok
            assert json.loads(reopened.get_bytes(ref)) == payload
            assert reopened.get_manifest(ref).producer.component == node.spec.metadata.component_id


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["fail_fast", "continue", "cancel"])
async def test_native_queued_admission_preserves_slots_and_completed_prefix(
    tmp_path, monkeypatch, mode
):
    metrics = _MetricFailure() if mode == "continue" else None
    ctx = _context(tmp_path, metrics=metrics)
    seed = _Node("seed", writes=["params.seed", "reports_index.seed"])
    first, second, third = (
        _Node(alias, reads=["params.seed"]) for alias in ("first", "second", "third")
    )
    first.fail = True
    first.release = asyncio.Event()
    nodes = [seed, first, second, third]
    hook = CASCheckpointHook(
        store=ctx.store, run_dir=Path(ctx.store.root) / "runs" / ctx.run.run_manifest.run_id
    )
    executor = AsyncWorkflowExecutor(
        ctx, _registry(*nodes), max_parallelism=1, checkpoint_hook=hook
    )
    workflow = WorkflowSpec(
        workflow_id="native_queue",
        error_policy="continue" if mode == "continue" else "fail_fast",
        nodes=[
            NodeInvocation(
                alias=node.alias,
                node_id=node.spec.metadata.component_id,
                depends_on=[] if node is seed else ["seed"],
            )
            for node in nodes
        ],
    )
    semaphores: list[asyncio.Semaphore] = []
    original_semaphore = asyncio.Semaphore

    def observe_real_semaphore(*args, **kwargs):
        semaphore = original_semaphore(*args, **kwargs)
        semaphores.append(semaphore)
        return semaphore

    monkeypatch.setattr(asyncio, "Semaphore", observe_real_semaphore)
    task = asyncio.create_task(executor.execute(workflow, ExperimentState(run_id="R_admission")))
    try:
        await asyncio.wait_for(first.started.wait(), timeout=5)
        await _until(lambda: any(len(semaphore._waiters or ()) == 2 for semaphore in semaphores))
        semaphore = next(s for s in semaphores if len(s._waiters or ()) == 2)
        assert semaphore._value == 0
        # Guarantee the existing >1ms telemetry branch is actually entered;
        # this is a gated fixture input, not a worker/process quota.
        await asyncio.sleep(0.01)
        if mode == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            first.release.set()
            result = await task
            assert result.report.status == "fail"
            assert result.state.params == {"seed": 7}
            statuses = {record.alias: record.status for record in result.report.nodes}
            assert statuses == {
                "seed": "ok",
                "first": "fail",
                "second": "ok" if mode == "continue" else "skip",
                "third": "ok" if mode == "continue" else "skip",
            }
            assert ctx.store.verify(result.state.reports_index["workflow_report"]).ok
        assert first.calls == 1
        assert second.calls == third.calls == (1 if mode == "continue" else 0)
        assert semaphore._value == 1
        assert not semaphore._waiters
        if metrics is not None:
            assert metrics.failures >= 2
        resolved = resolve_latest_checkpoint(FileSystemCAS(ctx.store.root), "R_admission")
        assert resolved is not None
        assert ctx.store.verify(resolved[0].checkpoint_ref).ok
        assert resolved[1].metadata.completed_nodes == (
            ["seed", "second", "third"] if mode == "continue" else ["seed"]
        )
        _read_effects(ctx, nodes)
    finally:
        first.release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["independent", "dependency", "overlap"])
async def test_native_readiness_preserves_real_inputs_methods_and_artifact_lineage(tmp_path, mode):
    ctx = _context(tmp_path)
    a = _Node("a", writes=["params.a", "params.c_input", "reports_index.a"])
    b = _Node(
        "b",
        writes=["params.b", "reports_index.b"] + (["params.c_input"] if mode == "overlap" else []),
    )
    b.overlap = mode == "overlap"
    b.release = asyncio.Event()
    c = _Node(
        "c",
        reads=["params.c_input", "reports_index.a"]
        + (["reports_index.b"] if mode != "independent" else []),
    )
    nodes = [a, b, c]
    workflow = WorkflowSpec(
        workflow_id="native_readiness",
        error_policy="continue",
        nodes=[
            NodeInvocation(alias="a", node_id=a.spec.metadata.component_id),
            NodeInvocation(alias="b", node_id=b.spec.metadata.component_id),
            NodeInvocation(
                alias="c",
                node_id=c.spec.metadata.component_id,
                depends_on=["a", "b"] if mode == "dependency" else ["a"],
            ),
        ],
    )
    task = asyncio.create_task(
        AsyncWorkflowExecutor(ctx, _registry(*nodes), max_parallelism=2).execute(
            workflow, ExperimentState(run_id="R_admission", params={"seed": 7})
        )
    )
    try:
        await asyncio.wait_for(b.started.wait(), timeout=5)
        await asyncio.wait_for(a.finished.wait(), timeout=5)
        if mode == "independent":
            await asyncio.wait_for(c.finished.wait(), timeout=5)
            assert not b.finished.is_set()
            assert ctx.store.verify(c.refs[0]).ok
            assert c.inputs[0] == {"alias": "c", "ordinal": 1, "seed": 7, "c_input": "from-a"}
            assert [edge.artifact_id for edge in ctx.store.get_manifest(c.refs[0]).inputs] == [
                a.refs[0].artifact_id
            ]
        else:
            await _until(
                lambda: any(
                    event.get("phase") == "scientist.node.a" and event.get("event") == "NODE_OK"
                    for event in (
                        json.loads(line) for line in ctx.run.trace_path.read_text().splitlines()
                    )
                )
            )
            assert not c.started.is_set()
            assert c.refs == []
        b.release.set()
        result = await task
        if mode == "overlap":
            # The existing ERROR merge policy refuses the conflicting tier;
            # scheduling C early would publish an inadmissible partial input.
            assert result.report.status == "fail"
            assert [node.calls for node in nodes] == [1, 1, 0]
            assert c.refs == []
            assert {record.error.code for record in result.report.nodes if record.error} == {
                "node.parallel_merge_conflict"
            }
            assert result.state.params == {"seed": 7}
            _read_effects(ctx, nodes)
            return
        assert result.report.status == "ok"
        assert [node.calls for node in nodes] == [1, 1, 1]
        assert c.inputs[0]["seed"] == 7
        assert c.inputs[0]["c_input"] == ("from-b" if mode == "overlap" else "from-a")
        assert result.state.params["a"] == result.state.params["b"] == "done"
        edges = ctx.store.get_manifest(c.refs[0]).inputs
        expected = [a.refs[0]] if mode == "independent" else [a.refs[0], b.refs[0]]
        assert [(edge.artifact_id, edge.manifest_profile_sha256) for edge in edges] == [
            (ref.artifact_id, ref.manifest_profile_sha256) for ref in expected
        ]
        assert [edge.role for edge in edges] == (["a"] if mode == "independent" else ["a", "b"])
        assert ctx.store.verify(result.state.reports_index["workflow_report"]).ok
        _read_effects(ctx, nodes)
    finally:
        b.release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
