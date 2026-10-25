from __future__ import annotations

import json
import logging

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, artifact_ref_identity_key
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.skip_blockers import SKIP_BLOCKER_REQUIRED_FIELDS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run import context as run_context
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.builtins import builtin_nodes
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import CycleDetectedError, UnknownNodeError
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutor,
)
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
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


class AlwaysSkipAnalyticNode:
    def __init__(self) -> None:
        metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_run_causal_queries_test@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Skip Causal",
            description="Skips a causal analytic node",
            capabilities=Capability.SCIENTIST_NODE,
        )
        self._spec = NodeSpec(metadata=metadata)

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return NodeOutcome(
            status="skip",
            state=state,
            events=[
                NodeEvent(
                    level="info",
                    code="causal_query_missing",
                    message="No params.causal_query; skip causal query execution.",
                    attrs={
                        "skip_reason": "missing_causal_query",
                        "missing_input": "params.causal_query",
                    },
                )
            ],
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


class SelectedArtifactOutputNode:
    """Test node that persists an artifact and selects it in workflow state."""

    def __init__(
        self,
        *,
        node_name: str = "selected_output",
        payload: object | None = None,
        declared_refs: list[ArtifactRef] | None = None,
        selected_refs: dict[str, ArtifactRef] | None = None,
        status: str = "ok",
    ) -> None:
        self.payload = payload
        self.declared_refs = declared_refs
        self.selected_refs = selected_refs
        self.status = status
        self.calls = 0
        self._spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(f"scientist.node_{node_name}@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Selected output test",
                description="Persists and returns a selected output artifact",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_writes=["artifacts_index"],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        persisted_ref = None
        if self.payload is not None:
            persisted_ref = ctx.store.put_json(
                self.payload,
                PutOptions(
                    kind="test.selected_output",
                    media_type="application/json",
                    schema=SchemaInfo(name="test.SelectedOutput", version="1.0"),
                ),
                return_selected_profile=True,
            )
        declared_refs = self.declared_refs
        if declared_refs is None:
            declared_refs = [persisted_ref] if persisted_ref is not None else []
        selected_refs = self.selected_refs
        if selected_refs is None and persisted_ref is not None:
            selected_refs = {"selected_output": persisted_ref}
        next_state = state.model_copy(deep=True)
        for key, ref in (selected_refs or {}).items():
            next_state.artifacts_index[key] = ref
        if self.status == "fail":
            return NodeOutcome(
                status="fail",
                state=next_state,
                artifacts=declared_refs,
                error=NodeError(code="node.test_failure", message="expected test failure"),
            )
        return NodeOutcome(status="ok", state=next_state, artifacts=declared_refs)


class FailingProvenanceDag:
    def record_node_execution(self, **kwargs) -> None:
        raise OSError("provenance unavailable")

    def record_node_failure(self, **kwargs) -> None:
        raise OSError("provenance unavailable")

    def finalize(self) -> None:
        return None

    def to_prov_json(self) -> dict[str, object]:
        return {"records": []}


def _ctx_and_registry(tmp_path, *, return_selected_profile=False):
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store, return_selected_profile=return_selected_profile)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="R_test")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test"))
    registry = NodeRegistry()
    for node in builtin_nodes():
        registry.register(node)
    return store, bundle, ctx, registry


def test_executor_runs_dag_and_emits_trace(tmp_path):
    store, bundle, ctx, registry = _ctx_and_registry(tmp_path, return_selected_profile=True)

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

    # The public executor records its exact per-attempt basis through the run
    # owner, and a fresh method call reloads that chain from the persisted trace.
    attempts = run_context._read_runtime_invocation_attempts(
        store, ctx.run.trace_path, run_id=state.run_id
    )
    assert {attempt.basis.node_alias for attempt in attempts} == {"set", "emit", "noop"}
    invocations_by_alias = {inv.alias: inv for inv in workflow.nodes}
    for attempt in attempts:
        assert attempt.outcome is not None
        assert attempt.outcome.status == "ok"
        assert attempt.basis.workflow_spec_ref.manifest_profile_sha256 is not None
        assert attempt.basis.input_state_ref.manifest_profile_sha256 is not None
        persisted_workflow = WorkflowSpec.model_validate_json(
            store.get_bytes(attempt.basis.workflow_spec_ref)
        )
        persisted_input = ExperimentState.model_validate_json(
            store.get_bytes(attempt.basis.input_state_ref)
        )
        assert persisted_workflow.workflow_id == workflow.workflow_id
        assert attempt.basis.node_alias in invocations_by_alias
        assert attempt.basis.component_id == str(
            invocations_by_alias[attempt.basis.node_alias].node_id
        )
        assert persisted_input.run_id == state.run_id


def test_executor_emits_memory_authority_before_serious_run_nodes(tmp_path):
    store, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="serious_memory_authority",
        required_binds=["run_id"],
        nodes=[
            NodeInvocation(
                alias="noop",
                node_id=ComponentId.parse("scientist.node_noop@1.0.0"),
                params={},
            ),
        ],
    )
    state = ExperimentState(
        run_id="R_test",
        execution_profile="production",
        inputs={"registry_bundle_ref": bundle.bundle_ref},
        params={
            "tenant_id": "tenant-wave35g",
            "cell_id": "cell-wave35g",
            "prompt_authority_refs": {
                "serious_run_prompt": "tests/fixtures/policy_design_case/serious_prompt.md"
            },
        },
    )

    result = WorkflowExecutor(ctx, registry).execute(workflow, state)

    record = result.state.params.get("memory_authority_record")
    assert isinstance(record, dict)
    assert record["authority_kind"] == "no_memory_abstention"
    assert record["runtime_owned"] is True
    assert record["memory_used"] is False
    assert record["replay_surface_empty"] is True
    assert record["emitted_before_serious_output_influence"] is True
    assert record["tenant_scope"] == {
        "tenant_id": "tenant-wave35g",
        "cell_id": "cell-wave35g",
    }
    assert (
        record["prompt_authority_refs"]["serious_run_prompt"]
        == "tests/fixtures/policy_design_case/serious_prompt.md"
    )
    assert "workflow_executor" in record["tool_authority_refs"]

    trace_ref = ctx.run.run_manifest.trace_ref
    assert trace_ref is not None
    trace_data = store.get_bytes(trace_ref.artifact_id).decode("utf-8")
    events = [json.loads(line) for line in trace_data.splitlines() if line.strip()]
    memory_event_index = next(
        index
        for index, event in enumerate(events)
        if event.get("event") == "MEMORY_AUTHORITY_RECORDED"
    )
    first_node_start_index = next(
        index for index, event in enumerate(events) if event.get("event") == "NODE_STARTED"
    )
    assert memory_event_index < first_node_start_index


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
    store, bundle, ctx, registry = _ctx_and_registry(tmp_path)
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

    assert result.run_ref is not None
    finalized = json.loads(store.get_bytes(result.run_ref.artifact_id))
    assert finalized["errors"] == [{"node": "fail", "code": "node.fail", "message": "boom"}]


def test_executor_persists_typed_skip_blocker_for_skipped_analytic_node(tmp_path):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path)
    registry.register(AlwaysSkipAnalyticNode())

    workflow = WorkflowSpec(
        workflow_id="skip_blocker_report",
        nodes=[
            NodeInvocation(
                alias="run_causal_queries",
                node_id=ComponentId.parse("scientist.node_run_causal_queries_test@1.0.0"),
            ),
        ],
    )
    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})
    executor = WorkflowExecutor(ctx, registry)
    result = executor.execute(workflow, state)

    record = result.report.nodes[0]

    assert record.status == "skip"
    assert record.skip_blocker is not None
    payload = record.skip_blocker.model_dump(mode="json")
    assert set(SKIP_BLOCKER_REQUIRED_FIELDS) <= set(payload)
    assert payload["reason"] == "missing_causal_query"
    assert payload["missing_input"] == "params.causal_query"
    assert payload["scorecard_blocking_policy"] == "blocks_scorecard_pass"


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


def test_executor_publishes_only_verified_selected_node_output_views(tmp_path):
    store, bundle, ctx, registry = _ctx_and_registry(tmp_path, return_selected_profile=True)
    node = SelectedArtifactOutputNode(payload={"outcome": "selected"})
    registry.register(node)
    state = ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref})
    workflow = WorkflowSpec(
        workflow_id="selected_output_publish",
        nodes=[NodeInvocation(alias="produce", node_id=node.spec.metadata.component_id)],
    )

    result = WorkflowExecutor(ctx, registry).execute(workflow, state)

    assert result.report.status == "ok"
    produced_ref = result.report.nodes[0].artifacts[0]
    assert produced_ref.manifest_profile_sha256 is not None
    assert store.verify(produced_ref).ok
    output_identities = [artifact_ref_identity_key(ref) for ref in ctx.run.run_manifest.outputs]
    assert output_identities.count(artifact_ref_identity_key(produced_ref)) == 1


def test_executor_refuses_nonexistent_and_wrong_selected_profile_outputs(tmp_path):
    store, bundle, ctx, registry = _ctx_and_registry(tmp_path, return_selected_profile=True)
    options_v1 = PutOptions(
        kind="test.selected_output",
        media_type="application/json",
        schema=SchemaInfo(name="test.SelectedOutput", version="1.0"),
    )
    options_v2 = PutOptions(
        kind="test.selected_output",
        media_type="application/json",
        schema=SchemaInfo(name="test.SelectedOutput", version="2.0"),
    )
    payload = {"same_blob": True}
    selected_ref = store.put_json(payload, options_v1, return_selected_profile=True)
    wrong_profile_ref = store.put_json(payload, options_v2, return_selected_profile=True)
    assert selected_ref.artifact_id == wrong_profile_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 != wrong_profile_ref.manifest_profile_sha256

    profile_node = SelectedArtifactOutputNode(
        node_name="wrong_profile",
        declared_refs=[wrong_profile_ref],
        selected_refs={"selected_output": selected_ref},
    )
    registry.register(profile_node)
    workflow = WorkflowSpec(
        workflow_id="reject_unbound_outputs",
        nodes=[
            NodeInvocation(alias="wrong_profile", node_id=profile_node.spec.metadata.component_id),
        ],
    )

    result = WorkflowExecutor(ctx, registry).execute(
        workflow,
        ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref}),
    )

    assert result.report.status == "ok"
    output_identities = {artifact_ref_identity_key(ref) for ref in ctx.run.run_manifest.outputs}
    assert artifact_ref_identity_key(selected_ref) not in output_identities
    assert artifact_ref_identity_key(wrong_profile_ref) not in output_identities


def test_executor_rejects_nonexistent_node_output_before_manifest_mapping(tmp_path):
    _, bundle, ctx, registry = _ctx_and_registry(tmp_path, return_selected_profile=True)
    fake_ref = ArtifactRef(
        artifact_id="sha256:" + "ab" * 32,
        kind="test.selected_output",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "cd" * 32,
    )
    node = SelectedArtifactOutputNode(
        node_name="nonexistent_output",
        declared_refs=[fake_ref],
        selected_refs={"nonexistent": fake_ref},
    )
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="reject_nonexistent_node_output",
        nodes=[NodeInvocation(alias="nonexistent", node_id=node.spec.metadata.component_id)],
    )

    result = WorkflowExecutor(ctx, registry).execute(
        workflow,
        ExperimentState(run_id="R_test", inputs={"registry_bundle_ref": bundle.bundle_ref}),
    )

    assert result.report.status == "fail"
    assert result.report.nodes[0].status == "fail"
    assert artifact_ref_identity_key(fake_ref) not in {
        artifact_ref_identity_key(ref) for ref in ctx.run.run_manifest.outputs
    }


def test_executor_publishes_selected_successful_refs_including_replayed_input(tmp_path):
    store, bundle, ctx, registry = _ctx_and_registry(tmp_path, return_selected_profile=True)
    preseed_only_ref = store.put_json(
        {"preseed": True},
        PutOptions(kind="test.selected_output", media_type="application/json"),
        return_selected_profile=True,
    )
    replayed_ref = store.put_json(
        {"replayed": True},
        PutOptions(kind="test.selected_output", media_type="application/json"),
        return_selected_profile=True,
    )
    unselected_ref = store.put_json(
        {"unselected": True},
        PutOptions(kind="test.selected_output", media_type="application/json"),
        return_selected_profile=True,
    )
    successful = SelectedArtifactOutputNode(
        node_name="successful_sibling",
        payload={"sibling": "committed"},
    )
    replayed = SelectedArtifactOutputNode(
        node_name="successful_replayed_input",
        declared_refs=[replayed_ref],
        selected_refs={"replayed_output": replayed_ref},
    )
    unselected = SelectedArtifactOutputNode(
        node_name="unselected_intermediate",
        declared_refs=[unselected_ref],
        selected_refs={},
    )
    failed = SelectedArtifactOutputNode(
        node_name="failed_sibling",
        declared_refs=[preseed_only_ref],
        selected_refs={"failed_output": preseed_only_ref},
        status="fail",
    )
    for node in (successful, replayed, unselected, failed):
        registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="successful_output_survives_failed_sibling",
        error_policy="continue",
        nodes=[
            NodeInvocation(alias="successful", node_id=successful.spec.metadata.component_id),
            NodeInvocation(alias="replayed", node_id=replayed.spec.metadata.component_id),
            NodeInvocation(alias="unselected", node_id=unselected.spec.metadata.component_id),
            NodeInvocation(alias="failed", node_id=failed.spec.metadata.component_id),
        ],
    )
    initial_state = ExperimentState(
        run_id="R_test",
        inputs={"registry_bundle_ref": bundle.bundle_ref},
        artifacts_index={
            "preseed_only": preseed_only_ref,
            "replayed_input": replayed_ref,
        },
    )

    result = WorkflowExecutor(ctx, registry).execute(workflow, initial_state)

    assert result.report.status == "fail"
    output_identities = {artifact_ref_identity_key(ref) for ref in ctx.run.run_manifest.outputs}
    selected_ref = result.report.nodes[0].artifacts[0]
    assert artifact_ref_identity_key(selected_ref) in output_identities
    assert artifact_ref_identity_key(replayed_ref) in output_identities
    assert artifact_ref_identity_key(preseed_only_ref) not in output_identities
    assert artifact_ref_identity_key(unselected_ref) not in output_identities


def test_executor_publishes_selected_outputs_from_verified_cache_hit(tmp_path):
    store, bundle, ctx, registry = _ctx_and_registry(tmp_path, return_selected_profile=True)
    node = SelectedArtifactOutputNode(node_name="cached_output")
    registry.register(node)
    state = ExperimentState(
        run_id="R_test",
        inputs={"registry_bundle_ref": bundle.bundle_ref},
        params={"seed": "cache-output"},
    )
    produced_ref = store.put_json(
        {"cached": "producer-output"},
        PutOptions(
            kind="test.selected_output",
            media_type="application/json",
            schema=SchemaInfo(name="test.SelectedOutput", version="1.0"),
        ),
        return_selected_profile=True,
    )
    cached_state = branch_state(state, write_paths=("artifacts_index",)).state
    cached_state.artifacts_index["selected_output"] = produced_ref
    cached_outcome = NodeOutcome(
        status="ok",
        state=cached_state,
        artifacts=[produced_ref],
    )
    cache_key = compute_idempotency_key(node.spec, state, {})
    cache_entry_ref = NodeResultCache(store, run_id=state.run_id).put(
        cache_key,
        node_id=str(node.spec.metadata.component_id),
        outcome=cached_outcome,
    )

    result = WorkflowExecutor(
        ctx,
        registry,
        checkpoint_cache_seed_refs=[cache_entry_ref],
    ).execute(
        WorkflowSpec(
            workflow_id="cache_selected_output",
            nodes=[NodeInvocation(alias="cached", node_id=node.spec.metadata.component_id)],
        ),
        state,
    )

    assert result.report.status == "ok"
    assert node.calls == 0
    output_identities = [artifact_ref_identity_key(ref) for ref in ctx.run.run_manifest.outputs]
    assert output_identities.count(artifact_ref_identity_key(produced_ref)) == 1
