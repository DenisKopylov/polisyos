from __future__ import annotations

import json
import logging

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.builtins import builtin_nodes
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import CycleDetectedError, UnknownNodeError
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


class AlwaysFailNode:
    def __init__(self) -> None:
        metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_fail@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
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


class MutatesNestedDeclaredWriteNode:
    def __init__(self) -> None:
        metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_mutate_nested@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Mutate Nested",
            description="Mutates a declared nested write path",
            capabilities=Capability.SCIENTIST_NODE,
        )
        self._spec = NodeSpec(
            metadata=metadata,
            state_reads=["params.nested"],
            state_writes=["params.nested.items"],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        state.params["nested"]["items"].append("node")
        return NodeOutcome(status="ok", state=state)


class CacheableSuccessNode:
    def __init__(self) -> None:
        metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_cacheable_success@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Cacheable Success",
            description="Succeeds and remains cache-enabled",
            capabilities=Capability.SCIENTIST_NODE,
        )
        self._spec = NodeSpec(metadata=metadata)

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return NodeOutcome(status="ok", state=state)


class BindFailNode:
    def __init__(self) -> None:
        metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_bind_fail@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Bind Fail",
            description="Raises during bind",
            capabilities=Capability.SCIENTIST_NODE,
        )
        self._spec = NodeSpec(metadata=metadata)

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def bind(self, params):
        raise RuntimeError(f"bind exploded for {sorted(params)}")

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        raise AssertionError("execute should not be called when bind fails")


class ExecuteLookupFailNode:
    def __init__(self) -> None:
        metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_execute_lookup_fail@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Execute Lookup Fail",
            description="Raises LookupError during execute",
            capabilities=Capability.SCIENTIST_NODE,
        )
        self._spec = NodeSpec(metadata=metadata)

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        raise KeyError("missing dependency")


class FailingProvenanceDag:
    def record_node_execution(self, **kwargs) -> None:
        raise OSError("provenance unavailable")

    def record_node_failure(self, **kwargs) -> None:
        raise OSError("provenance unavailable")

    def finalize(self) -> None:
        return None

    def to_prov_json(self) -> dict[str, object]:
        return {"records": []}


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


def test_executor_branch_state_isolates_declared_nested_writes(tmp_path):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    registry.register(MutatesNestedDeclaredWriteNode())

    workflow = WorkflowSpec(
        workflow_id="branch_state",
        nodes=[
            NodeInvocation(
                alias="mutate",
                node_id=ComponentId.parse("scientist.node_mutate_nested@1.0.0"),
            )
        ],
    )
    state = ExperimentState(
        run_id="R_test",
        inputs={"registry_bundle_ref": bundle.bundle_ref},
        params={"nested": {"items": ["base"]}},
    )

    executor = WorkflowExecutor(ctx, registry)
    result = executor.execute(workflow, state)

    assert result.state.params["nested"]["items"] == ["base", "node"]
    assert state.params["nested"]["items"] == ["base"]


def test_executor_logs_cache_write_bypass_as_node_event(tmp_path, monkeypatch, caplog):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    registry.register(CacheableSuccessNode())

    workflow = WorkflowSpec(
        workflow_id="cache_bypass_warning",
        nodes=[
            NodeInvocation(
                alias="cacheable",
                node_id=ComponentId.parse("scientist.node_cacheable_success@1.0.0"),
            )
        ],
    )
    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})

    def _raise_put(self, key, node_id, outcome):
        raise OSError("cache store unavailable")

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.idempotency.NodeResultCache.put",
        _raise_put,
    )

    executor = WorkflowExecutor(ctx, registry)
    with caplog.at_level(logging.WARNING, logger="test"):
        result = executor.execute(workflow, state)

    assert result.report.status == "ok"
    assert any(
        "Node result cache write bypassed" in record.getMessage() for record in caplog.records
    )


def test_executor_logs_provenance_recording_degraded_as_node_event(tmp_path, caplog):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    registry.register(CacheableSuccessNode())

    workflow = WorkflowSpec(
        workflow_id="provenance_warning",
        nodes=[
            NodeInvocation(
                alias="cacheable",
                node_id=ComponentId.parse("scientist.node_cacheable_success@1.0.0"),
            )
        ],
    )
    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})

    executor = WorkflowExecutor(ctx, registry, provenance_dag=FailingProvenanceDag())
    with caplog.at_level(logging.WARNING, logger="test"):
        result = executor.execute(workflow, state)

    assert result.report.status == "ok"
    assert any(
        "Node provenance recording degraded" in record.getMessage() for record in caplog.records
    )


def test_executor_reports_bind_failure_as_typed_node_error(tmp_path):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    node = BindFailNode()
    registry.register(node)

    workflow = WorkflowSpec(
        workflow_id="bind_failure",
        nodes=[
            NodeInvocation(
                alias="bind_fail",
                node_id=ComponentId.parse("scientist.node_bind_fail@1.0.0"),
                params={"country": "UA"},
            )
        ],
        error_policy="continue",
    )
    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})

    executor = WorkflowExecutor(ctx, registry)
    result = executor.execute(workflow, state)

    assert result.report.status == "fail"
    record = result.report.nodes[0]
    assert record.status == "fail"
    assert record.error is not None
    assert record.error.code == "node.bind_failed"
    assert record.error.details["type"] == "RuntimeError"
    assert state.params == {}


def test_executor_reports_lookup_runtime_failure_as_typed_node_error(tmp_path):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    registry.register(ExecuteLookupFailNode())

    workflow = WorkflowSpec(
        workflow_id="execute_lookup_failure",
        nodes=[
            NodeInvocation(
                alias="lookup_fail",
                node_id=ComponentId.parse("scientist.node_execute_lookup_fail@1.0.0"),
            )
        ],
        error_policy="continue",
    )
    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})

    executor = WorkflowExecutor(ctx, registry)
    result = executor.execute(workflow, state)

    assert result.report.status == "fail"
    record = result.report.nodes[0]
    assert record.status == "fail"
    assert record.error is not None
    assert record.error.code == "node.exception"
    assert record.error.details["type"] == "KeyError"
    assert result.state.params == {}
