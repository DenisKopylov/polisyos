from __future__ import annotations

import json
import logging

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.executor import WorkflowExecutor
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.core.artifacts.store import FileSystemCAS


_CACHED_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Cached Counter",
    description="Test node for idempotency cache recovery",
    tags=["test"],
    capabilities=Capability.SCIENTIST_NODE,
)

_CACHED_SPEC = NodeSpec(
    metadata=_CACHED_METADATA,
    state_reads=["params.seed"],
    state_writes=["params.cached_counter"],
)

_FAIL_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_always_fail@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Always Fail",
    description="Test fail node for retry verification",
    tags=["test"],
    capabilities=Capability.SCIENTIST_NODE,
)

_FAIL_SPEC = NodeSpec(metadata=_FAIL_METADATA)


class CachedCounterNode:
    calls = 0

    @property
    def spec(self) -> NodeSpec:
        return _CACHED_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        CachedCounterNode.calls += 1
        new_state = state.model_copy(deep=True)
        new_state.params["cached_counter"] = CachedCounterNode.calls
        return NodeOutcome(status="ok", state=new_state)


class AlwaysFailNode:
    calls = 0

    @property
    def spec(self) -> NodeSpec:
        return _FAIL_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        AlwaysFailNode.calls += 1
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(code="node.fail", message="expected failure"),
        )


def _build_context(store: FileSystemCAS, run_id: str) -> tuple[ExecutionContext, NodeRegistry]:
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("idempotency_test"))
    registry = NodeRegistry()
    registry.register(CachedCounterNode())
    registry.register(AlwaysFailNode())
    return ctx, registry


def _load_trace_events(store: FileSystemCAS, ctx: ExecutionContext) -> list[dict[str, object]]:
    trace_ref = ctx.run.run_manifest.trace_ref
    assert trace_ref is not None
    payload = store.get_bytes(trace_ref.artifact_id).decode("utf-8")
    return [json.loads(line) for line in payload.splitlines() if line.strip()]


def test_executor_cache_hit_after_restart_same_run_id(tmp_path) -> None:
    CachedCounterNode.calls = 0
    store = FileSystemCAS(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="cache_restart",
        nodes=[
            NodeInvocation(
                alias="cached",
                node_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
            ),
        ],
    )
    initial_state = ExperimentState(run_id="R_cache_restart", params={"seed": 7})

    ctx_a, registry_a = _build_context(store, "R_cache_restart")
    result_a = WorkflowExecutor(ctx_a, registry_a).execute(workflow, initial_state)
    assert result_a.report.status == "ok"
    assert CachedCounterNode.calls == 1
    assert result_a.state.params["cached_counter"] == 1

    ctx_b, registry_b = _build_context(store, "R_cache_restart")
    result_b = WorkflowExecutor(ctx_b, registry_b).execute(workflow, initial_state)
    assert result_b.report.status == "ok"
    assert CachedCounterNode.calls == 1
    assert result_b.state.params["cached_counter"] == 1

    events = _load_trace_events(store, ctx_b)
    hit_events = [evt for evt in events if evt.get("event") == "NODE_CACHE_HIT"]
    assert len(hit_events) == 1


def test_executor_resume_retries_failed_node_and_reuses_cached_ok_node(tmp_path) -> None:
    CachedCounterNode.calls = 0
    AlwaysFailNode.calls = 0
    store = FileSystemCAS(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="cache_resume_fail",
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="cached",
                node_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
            ),
            NodeInvocation(
                alias="failing",
                node_id=ComponentId.parse("scientist.node_always_fail@1.0.0"),
                depends_on=["cached"],
            ),
        ],
    )
    initial_state = ExperimentState(run_id="R_cache_resume", params={"seed": 42})

    ctx_a, registry_a = _build_context(store, "R_cache_resume")
    result_a = WorkflowExecutor(ctx_a, registry_a).execute(workflow, initial_state)
    assert result_a.report.status == "fail"
    assert CachedCounterNode.calls == 1
    assert AlwaysFailNode.calls == 1

    ctx_b, registry_b = _build_context(store, "R_cache_resume")
    result_b = WorkflowExecutor(ctx_b, registry_b).execute(workflow, initial_state)
    assert result_b.report.status == "fail"
    assert CachedCounterNode.calls == 1
    assert AlwaysFailNode.calls == 2

    cached_record = next(rec for rec in result_b.report.nodes if rec.alias == "cached")
    failing_record = next(rec for rec in result_b.report.nodes if rec.alias == "failing")
    assert cached_record.status == "ok"
    assert failing_record.status == "fail"

    events = _load_trace_events(store, ctx_b)
    assert any(evt.get("event") == "NODE_CACHE_HIT" for evt in events)
