"""Real CAS frontier and compensation consumer for a failed parallel tier."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Literal

import pytest

import polisyos.scientist.orchestration.engine.async_executor as executor_module
import polisyos.scientist.orchestration.engine.checkpoint as checkpoint_module
import polisyos.scientist.orchestration.engine.compensation as compensation_module
import polisyos.scientist.orchestration.engine.idempotency as cache_module
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    load_checkpoint_history,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
)
from polisyos.scientist.orchestration.engine.compensation import RollbackCompensationEvent
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.idempotency import NodeCacheEntry
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

pytestmark = pytest.mark.integration
_Alias = Literal["seed", "a", "b", "final"]


class _Producer:
    def __init__(self, alias: _Alias, *, fail_once: bool = False) -> None:
        self.alias = alias
        self.fail_once = fail_once
        self.calls = 0
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(f"scientist.b73_compensation_{alias}@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name=f"B73 {alias}",
                description="Real parallel frontier and compensation consumer",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=(
                ["params.seed"]
                if alias == "seed"
                else ["params.a", "params.b"]
                if alias == "final"
                else ["params.seeded"]
            ),
            state_writes=(
                ["params.seeded"]
                if alias == "seed"
                else ["params.a", "reports_index.a"]
                if alias == "a"
                else [f"params.{alias}"]
            ),
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx, state
        raise AssertionError("This fixture requires the real async producer inlet")

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        if self.alias == "b" and self.fail_once:
            self.fail_once = False
            state.params["b"] = 999
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.transient", message="Observed first B failure"),
            )
        if self.alias == "seed":
            state.params["seeded"] = 1
        elif self.alias == "a":
            state.params["a"] = 1
            effect = ctx.store.put_json(
                {"a": 1, "seed": state.params["seed"]},
                PutOptions(kind="scientist.b73_effect", media_type="application/json"),
            )
            state.reports_index["a"] = effect
            return NodeOutcome(status="ok", state=state, artifacts=[effect])
        elif self.alias == "b":
            state.params["b"] = 2
        else:
            state.params["final"] = state.params["a"] + state.params["b"]
        return NodeOutcome(status="ok", state=state)


class _CompensationConsumer:
    def __init__(self) -> None:
        self.observed: list[tuple[RollbackCompensationEvent, dict[str, object]]] = []

    def on_tier_rollback(
        self, *, event: RollbackCompensationEvent, restored_state: ExperimentState
    ) -> None:
        self.observed.append((event, restored_state.model_dump(mode="json")))


def _registry(*, fail_b: bool) -> tuple[NodeRegistry, dict[_Alias, _Producer]]:
    aliases: tuple[_Alias, ...] = ("seed", "a", "b", "final")
    nodes = {alias: _Producer(alias, fail_once=fail_b and alias == "b") for alias in aliases}
    registry = NodeRegistry()
    for node in nodes.values():
        registry.register(node)
    return registry, nodes


def _sources() -> dict[str, object]:
    observed: dict[str, object] = {}
    expected = os.environ.get("E02_ORACLE_PRODUCT_ROOT")
    for module in (executor_module, checkpoint_module, compensation_module, cache_module):
        path = Path(module.__file__).resolve()
        if expected is not None:
            assert path.is_relative_to(Path(expected).resolve())
        observed[module.__name__] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return observed


@pytest.mark.parametrize("error_policy", ["fail_fast", "continue"])
def test_parallel_compensation_matches_committed_frontier_and_retained_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_policy: Literal["fail_fast", "continue"],
) -> None:
    sources = _sources()
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    monkeypatch.setenv("POLISYOS_RUNNER_MAX_PARALLELISM", "2")
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store)
    run_id = f"R_b73_compensation_{error_policy}"
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("b73-compensation"))
    registry, nodes = _registry(fail_b=True)
    workflow = WorkflowSpec(
        workflow_id="b73_parallel_compensation",
        error_policy=error_policy,
        nodes=[
            NodeInvocation(alias="seed", node_id=nodes["seed"].spec.metadata.component_id),
            NodeInvocation(
                alias="a", node_id=nodes["a"].spec.metadata.component_id, depends_on=["seed"]
            ),
            NodeInvocation(
                alias="b", node_id=nodes["b"].spec.metadata.component_id, depends_on=["seed"]
            ),
            NodeInvocation(
                alias="final",
                node_id=nodes["final"].spec.metadata.component_id,
                depends_on=["a", "b"],
            ),
        ],
    )
    state = ExperimentState(
        run_id=run_id, params={"seed": 29}, inputs={"registry_bundle_ref": bundle.bundle_ref}
    )
    consumer = _CompensationConsumer()
    first = asyncio.run(
        AsyncWorkflowExecutor(
            ctx,
            registry,
            checkpoint_hook=CASCheckpointHook(store=store, run_dir=store.root / "runs" / run_id),
            compensation_hook=consumer,
            max_parallelism=2,
        ).execute(workflow, state)
    )
    reopened = FileSystemCAS(store.root)
    resolved = resolve_latest_checkpoint(reopened, run_id)
    assert resolved is not None and resolved[1].state is not None
    head, checkpoint = resolved
    a_record = next(record for record in first.report.nodes if record.alias == "a")
    assert a_record.status == "ok" and len(a_record.artifacts) == 1
    effect_ref = a_record.artifacts[0]
    assert reopened.verify(effect_ref).ok
    assert from_canonical_bytes(reopened.get_bytes(effect_ref)) == {"a": 1, "seed": 29}
    trace = (store.root / "runs" / run_id / "trace.jsonl").read_text()
    cache_refs: list[ArtifactRef] = []
    for raw_event in trace.splitlines():
        event = json.loads(raw_event)
        if event["event"] == "NODE_CACHE_STORE" and event["phase"] == "scientist.node.a":
            cache_refs.extend(ArtifactRef.model_validate(raw) for raw in event["refs"]["outputs"])
    assert len(cache_refs) == 1 and reopened.verify(cache_refs[0]).ok
    entry = NodeCacheEntry.model_validate(from_canonical_bytes(reopened.get_bytes(cache_refs[0])))
    assert entry.node_id == str(nodes["a"].spec.metadata.component_id)
    assert entry.run_id == run_id
    expected_params = {"seed": 29, "seeded": 1}
    expected_completed = ["seed"]
    if error_policy == "continue":
        expected_params["a"] = 1
        expected_completed.append("a")
    assert first.report.status == "fail"
    assert first.state.params == expected_params
    assert checkpoint.state["params"] == expected_params
    assert checkpoint.metadata.completed_nodes == expected_completed
    assert {alias: node.calls for alias, node in nodes.items()} == {
        "seed": 1,
        "a": 1,
        "b": 1,
        "final": 0,
    }
    if error_policy == "fail_fast":
        assert len(consumer.observed) == 1
        event, restored_state = consumer.observed[0]
        assert isinstance(event, RollbackCompensationEvent)
        assert event.run_id == run_id and event.workflow_id == workflow.workflow_id
        assert event.tier_index == 1 and event.reason == "parallel_tier_fail_fast"
        assert event.failed_aliases == ("b",)
        assert event.completed_before_tier == ("seed",)
        assert restored_state["params"] == expected_params
        assert "a" not in restored_state["reports_index"]
    else:
        assert consumer.observed == []
        assert checkpoint.state["reports_index"]["a"] == effect_ref.model_dump(mode="json")
    fresh_registry, fresh_nodes = _registry(fail_b=False)
    resumed = resume_from_checkpoint(
        reopened,
        run_id,
        workflow=workflow,
        registry=fresh_registry,
        registry_bundle_ref=bundle.bundle_ref,
        checkpoint_policy="strict",
    )
    assert resumed.report.status == "ok"
    assert resumed.state.params == {"seed": 29, "seeded": 1, "a": 1, "b": 2, "final": 3}
    assert {alias: node.calls for alias, node in fresh_nodes.items()} == {
        "seed": 0,
        "a": 0,
        "b": 1,
        "final": 1,
    }
    assert resumed.state.reports_index["a"] == effect_ref
    assert reopened.verify(effect_ref).ok and reopened.verify(cache_refs[0]).ok
    final_resolved = resolve_latest_checkpoint(reopened, run_id)
    assert final_resolved is not None and final_resolved[1].state is not None
    assert final_resolved[1].metadata.completed_nodes == ["seed", "a", "b", "final"]
    assert final_resolved[1].state["params"] == resumed.state.params
    history = load_checkpoint_history(store.root / "runs" / run_id)
    assert history is not None
    print(
        "B73_PARALLEL_COMPENSATION_ORACLE="
        + json.dumps(
            {
                "sources": sources,
                "error_policy": error_policy,
                "compensation": [
                    {"event": asdict(e), "restored_params": s["params"]}
                    for e, s in consumer.observed
                ],
                "first_params": dict(first.state.params),
                "first_completed": checkpoint.metadata.completed_nodes,
                "first_head_verified": reopened.verify(head.checkpoint_ref).ok,
                "retained_output": effect_ref.model_dump(mode="json"),
                "retained_cache": cache_refs[0].model_dump(mode="json"),
                "resumed_params": dict(resumed.state.params),
                "resumed_calls": {alias: node.calls for alias, node in fresh_nodes.items()},
                "final_completed": final_resolved[1].metadata.completed_nodes,
                "history_generations": len(history.entries),
            },
            sort_keys=True,
        ),
        flush=True,
    )
