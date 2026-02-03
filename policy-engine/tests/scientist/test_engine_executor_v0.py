from __future__ import annotations

import json
import logging

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.errors import CycleDetectedError, UnknownNodeError
from polisyos.scientist.engine.executor import WorkflowExecutor
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.engine.builtins import builtin_nodes
from polisyos.core.components import Capability, ComponentId, ComponentMetadata


class AlwaysFailNode:
    def __init__(self) -> None:
        metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_fail@1.0.0"),
            display_name="Fail",
            description="Always fails",
            capabilities=Capability.SCIENTIST_NODE,
        )
        self._spec = NodeSpec(metadata=metadata)

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(code="node.fail", message="boom"),
        )


def _ctx_and_registry(tmp_path):
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="R_test")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test"))
    registry = NodeRegistry()
    for node in builtin_nodes():
        registry.register(node)
    return store, bundle, ctx, registry


def test_executor_runs_dag_and_emits_trace(tmp_path):
    store, bundle, ctx, registry = _ctx_and_registry(tmp_path)

    workflow = WorkflowSpec(
        workflow_id="engine_smoke",
        required_binds=["run_id"],
        nodes=[
            NodeInvocation(
                alias="set",
                node_id=ComponentId.parse("scientist.node_set_state@1.0.0"),
                params={"key": "foo", "value": "bar"},
            ),
            NodeInvocation(
                alias="emit",
                node_id=ComponentId.parse("scientist.node_emit_artifact@1.0.0"),
                params={"key": "dummy", "payload": {"ok": True}},
                depends_on=["set"],
            ),
            NodeInvocation(
                alias="noop",
                node_id=ComponentId.parse("scientist.node_noop@1.0.0"),
                params={},
                depends_on=["emit"],
            ),
        ],
    )

    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})
    executor = WorkflowExecutor(ctx, registry)
    result = executor.execute(workflow, state)

    assert result.state.params.get("foo") == "bar"
    assert "dummy" in result.state.artifacts_index
    assert [rec.alias for rec in result.report.nodes] == ["set", "emit", "noop"]

    trace_ref = ctx.run.run_manifest.trace_ref
    assert trace_ref is not None
    trace_data = store.get_bytes(trace_ref.artifact_id).decode("utf-8")
    events = [json.loads(line) for line in trace_data.splitlines() if line.strip()]
    node_events = [evt for evt in events if evt.get("phase", "").startswith("scientist.node.")]
    aliases = {evt["phase"].split(".")[-1] for evt in node_events}
    assert {"set", "emit", "noop"}.issubset(aliases)


def test_executor_unknown_node(tmp_path):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="unknown_node",
        nodes=[
            NodeInvocation(
                alias="missing",
                node_id=ComponentId.parse("scientist.node_missing@1.0.0"),
            )
        ],
    )
    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})
    executor = WorkflowExecutor(ctx, registry)
    with pytest.raises(UnknownNodeError):
        executor.execute(workflow, state)


def test_executor_cycle_detected(tmp_path):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="cycle",
        nodes=[
            NodeInvocation(
                alias="a",
                node_id=ComponentId.parse("scientist.node_noop@1.0.0"),
                depends_on=["b"],
            ),
            NodeInvocation(
                alias="b",
                node_id=ComponentId.parse("scientist.node_noop@1.0.0"),
                depends_on=["a"],
            ),
        ],
    )
    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})
    executor = WorkflowExecutor(ctx, registry)
    with pytest.raises(CycleDetectedError):
        executor.execute(workflow, state)


def test_skip_propagation_continue_policy(tmp_path):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    registry.register(AlwaysFailNode())

    workflow = WorkflowSpec(
        workflow_id="continue",
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="fail",
                node_id=ComponentId.parse("scientist.node_fail@1.0.0"),
            ),
            NodeInvocation(
                alias="downstream",
                node_id=ComponentId.parse("scientist.node_noop@1.0.0"),
                depends_on=["fail"],
            ),
        ],
    )
    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})
    executor = WorkflowExecutor(ctx, registry)
    result = executor.execute(workflow, state)

    statuses = {rec.alias: rec.status for rec in result.report.nodes}
    assert statuses["fail"] == "fail"
    assert statuses["downstream"] == "skip"
    downstream = next(rec for rec in result.report.nodes if rec.alias == "downstream")
    assert downstream.skip_reason == "upstream_failed"
