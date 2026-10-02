# ruff: noqa: E402
# Optional Temporal imports follow the intentional importorskip dependency guard.
from __future__ import annotations

import logging
from pathlib import Path

import pytest

temporalio = pytest.importorskip("temporalio")

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    resolve_latest_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner import (
    _activity_worker as activity_worker_module,
)
from polisyos.scientist.orchestration.engine.runner import temporal_runner as temporal_runner_module
from polisyos.scientist.orchestration.engine.runner.serialization import (
    deserialize_state,
    serialize_outcome,
    serialize_state,
)
from polisyos.scientist.orchestration.engine.runner.temporal_runner import (
    ScientistWorkflow,
    TemporalWorkflowRunner,
    execute_node_activity,
    execute_node_outcome_activity,
    merge_checkpoint_tier_activity,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _meta(raw: str, name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(raw),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=name,
        description=f"{name} test node",
        tags=["test"],
        capabilities=Capability.SCIENTIST_NODE,
    )


class TemporalLeftNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_temporal_left@1.0.0", "TemporalLeft"),
        state_writes=["params.left"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        new_state = state.model_copy(deep=True)
        new_state.params["left"] = 1
        return NodeOutcome(status="ok", state=new_state)


class TemporalRightNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_temporal_right@1.0.0", "TemporalRight"),
        state_writes=["params.right"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        new_state = state.model_copy(deep=True)
        new_state.params["right"] = 2
        return NodeOutcome(status="ok", state=new_state)


class TemporalFinalizeNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_temporal_finalize@1.0.0", "TemporalFinalize"),
        state_reads=["params.left", "params.right"],
        state_writes=["params.final"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        new_state = state.model_copy(deep=True)
        new_state.params["final"] = int(new_state.params.get("left", 0)) + int(
            new_state.params.get("right", 0)
        )
        return NodeOutcome(status="ok", state=new_state)


class TemporalJournalProducerNode:
    _spec = NodeSpec(
        metadata=_meta(
            "scientist.node_temporal_journal_producer@1.0.0",
            "TemporalJournalProducer",
        ),
        state_writes=["params.accepted"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        del ctx
        state.params["accepted"] = True
        return NodeOutcome(status="ok", state=state)


def _registry() -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(TemporalLeftNode())
    registry.register(TemporalRightNode())
    registry.register(TemporalFinalizeNode())
    return registry


def _workflow() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="wf_temporal_runner_checkpoint_merge",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="left",
                node_id=ComponentId.parse("scientist.node_temporal_left@1.0.0"),
            ),
            NodeInvocation(
                alias="right",
                node_id=ComponentId.parse("scientist.node_temporal_right@1.0.0"),
            ),
            NodeInvocation(
                alias="final",
                node_id=ComponentId.parse("scientist.node_temporal_finalize@1.0.0"),
                depends_on=["left", "right"],
            ),
        ],
    )


def _context(store: FileSystemCAS, run_id: str) -> tuple[ExecutionContext, object]:
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.temporal.runner"))
    return ctx, bundle.bundle_ref


@pytest.mark.asyncio
async def test_temporal_runner_executes_remote_checkpoint_merge_activity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_temporal_remote_merge"
    workflow = _workflow()
    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        params={"seed": 11},
    )
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )
    task_queue = "scientist-temporal-test"
    runner = TemporalWorkflowRunner(
        server_url="unused-by-test-environment",
        task_queue=task_queue,
        max_parallelism=2,
    )

    def _discover_nodes(registry: NodeRegistry) -> None:
        registry.register(TemporalLeftNode())
        registry.register(TemporalRightNode())
        registry.register(TemporalFinalizeNode())

    merge_calls: list[list[str]] = []
    original_merge = activity_worker_module.run_merge_checkpoint_tier_in_worker

    async def _recording_merge(payload: dict[str, object]) -> dict[str, object]:
        merge_calls.append(list(payload["tier_aliases"]))  # type: ignore[index]
        return await original_merge(payload)

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
        _discover_nodes,
    )
    monkeypatch.setattr(
        activity_worker_module,
        "run_merge_checkpoint_tier_in_worker",
        _recording_merge,
    )

    download_dir = tmp_path / "temporal-test-server"
    download_dir.mkdir(parents=True, exist_ok=True)
    env = await WorkflowEnvironment.start_time_skipping(download_dest_dir=str(download_dir))
    try:
        runner._client = env.client
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[ScientistWorkflow],
            activities=[
                execute_node_activity,
                execute_node_outcome_activity,
                merge_checkpoint_tier_activity,
            ],
            workflow_runner=UnsandboxedWorkflowRunner(),
        ):
            result = await runner.execute_workflow(
                workflow,
                state,
                ctx,
                _registry(),
                checkpoint_hook=hook,
            )
    finally:
        await env.shutdown()

    assert result.report.status == "ok"
    assert [node.status for node in result.report.nodes] == ["ok", "ok", "ok"]
    assert result.state.params["left"] == 1
    assert result.state.params["right"] == 2
    assert result.state.params["final"] == 3
    assert result.state.last_checkpoint_ref is not None
    assert merge_calls == [["left", "right"], ["final"]]

    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    head, checkpoint_artifact = resolved
    assert head.sequence_number == 2
    assert checkpoint_artifact.metadata.completed_nodes == ["left", "right", "final"]
    assert checkpoint_artifact.state is not None
    assert checkpoint_artifact.state["params"]["left"] == 1
    assert checkpoint_artifact.state["params"]["right"] == 2
    assert checkpoint_artifact.state["params"]["final"] == 3


@pytest.mark.asyncio
async def test_temporal_no_checkpoint_branch_preserves_skip_and_ok_statuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_spec = WorkflowSpec(
        workflow_id="wf_temporal_status_without_checkpoint",
        required_binds=["run_id"],
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="skipped",
                node_id=ComponentId.parse("scientist.node_temporal_left@1.0.0"),
            ),
            NodeInvocation(
                alias="accepted",
                node_id=ComponentId.parse("scientist.node_temporal_journal_producer@1.0.0"),
            ),
            NodeInvocation(
                alias="forged",
                node_id=ComponentId.parse("scientist.node_temporal_left@1.0.0"),
            ),
        ],
    )
    base_state = ExperimentState(run_id="R_temporal_status_without_checkpoint")
    merge_payloads: list[dict[str, object]] = []

    def _discover_nodes(registry: NodeRegistry) -> None:
        registry.register(TemporalLeftNode())
        registry.register(TemporalRightNode())
        registry.register(TemporalFinalizeNode())
        registry.register(TemporalJournalProducerNode())

    async def _execute_node(payload: dict[str, object]) -> bytes:
        state = deserialize_state(payload["state_bytes"])
        alias = str(payload["alias"])
        if alias == "skipped":
            return serialize_outcome(NodeOutcome(status="skip", state=state))
        if alias == "forged":
            forged_state = branch_state(
                state,
                write_paths=("artifacts_index.injected",),
            ).state
            forged_state.artifacts_index["injected"] = ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="test.untrusted",
                media_type="application/json",
            )
            return serialize_outcome(NodeOutcome(status="ok", state=forged_state))
        return await activity_worker_module.run_node_in_worker(
            {
                **payload,
                "context_meta": {
                    "run_id": base_state.run_id,
                    "store_config": {"backend": "filesystem", "root": str(tmp_path)},
                },
            }
        )

    async def _execute_activity(activity_fn, payload, **kwargs):
        del kwargs
        if activity_fn is temporal_runner_module.merge_checkpoint_tier_activity:
            merge_payloads.append(payload)
            return await activity_worker_module.run_merge_checkpoint_tier_in_worker(payload)
        return await activity_fn(payload)

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
        _discover_nodes,
    )
    monkeypatch.setattr(temporal_runner_module.workflow, "patched", lambda _patch: True)
    monkeypatch.setattr(
        temporal_runner_module.workflow,
        "execute_activity",
        _execute_activity,
    )
    monkeypatch.setattr(
        temporal_runner_module,
        "execute_node_outcome_activity",
        _execute_node,
    )

    result = await ScientistWorkflow().run(
        {
            "workflow_spec_json": workflow_spec.model_dump(mode="json"),
            "initial_state_bytes": serialize_state(base_state),
            "context_meta": {
                "run_id": base_state.run_id,
                "store_config": {"backend": "filesystem", "root": str(tmp_path)},
            },
            "max_parallelism": 2,
            "merge_conflict_policy": "error",
        }
    )

    assert isinstance(result, dict)
    merged_state = deserialize_state(result["state_bytes"])
    assert merged_state.params == {"accepted": True}
    assert merged_state.artifacts_index == {}
    assert len(merge_payloads) == 1
    assert merge_payloads[0]["checkpoint_hook_meta"] is None
    assert merge_payloads[0]["result_format"] == "node_outcome"
    reports = result["node_reports_by_alias"]
    assert reports["skipped"]["status"] == "skip"
    assert reports["accepted"]["status"] == "ok"
    assert reports["forged"]["status"] == "ok"
    assert "state" not in reports["skipped"]


@pytest.mark.asyncio
async def test_temporal_status_history_without_bound_scope_marker_keeps_inline_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_spec = WorkflowSpec(
        workflow_id="wf_temporal_status_history_before_bound_scope",
        required_binds=["run_id"],
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="left",
                node_id=ComponentId.parse("scientist.node_temporal_left@1.0.0"),
            )
        ],
    )
    base_state = ExperimentState(run_id="R_temporal_status_history_before_bound_scope")

    async def _recorded_status_activity(payload: dict[str, object]) -> bytes:
        state = deserialize_state(payload["state_bytes"])
        state.params["left"] = 1
        return serialize_outcome(NodeOutcome(status="ok", state=state))

    async def _execute_activity(activity_fn, payload, **kwargs):
        del kwargs
        if activity_fn is temporal_runner_module.merge_checkpoint_tier_activity:
            raise AssertionError("recorded status history scheduled a new merge activity")
        return await activity_fn(payload)

    monkeypatch.setattr(
        temporal_runner_module.workflow,
        "patched",
        lambda patch: patch == "distributed-node-outcome-status-v1",
    )
    monkeypatch.setattr(
        temporal_runner_module.workflow,
        "execute_activity",
        _execute_activity,
    )
    monkeypatch.setattr(
        temporal_runner_module,
        "execute_node_outcome_activity",
        _recorded_status_activity,
    )

    result = await ScientistWorkflow().run(
        {
            "workflow_spec_json": workflow_spec.model_dump(mode="json"),
            "initial_state_bytes": serialize_state(base_state),
            "context_meta": {},
            "max_parallelism": 1,
            "merge_conflict_policy": "error",
        }
    )

    assert isinstance(result, dict)
    assert deserialize_state(result["state_bytes"]).params == {"left": 1}
    assert result["node_reports_by_alias"]["left"]["status"] == "ok"


@pytest.mark.asyncio
async def test_temporal_pre_patch_history_keeps_state_only_activity_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_spec = WorkflowSpec(
        workflow_id="wf_temporal_legacy_status_history",
        required_binds=["run_id"],
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="legacy",
                node_id=ComponentId.parse("scientist.node_temporal_left@1.0.0"),
            )
        ],
    )
    base_state = ExperimentState(run_id="R_temporal_legacy_status_history")
    legacy_merge_payloads: list[dict[str, object]] = []

    async def _legacy_state_activity(payload: dict[str, object]) -> bytes:
        state = deserialize_state(payload["state_bytes"])
        state.params["legacy"] = True
        return serialize_state(state)

    async def _execute_activity(activity_fn, payload, **kwargs):
        del kwargs
        if activity_fn is temporal_runner_module.merge_checkpoint_tier_activity:
            legacy_merge_payloads.append(payload)
            return {
                "state_bytes": payload["result_bytes_by_alias"]["legacy"],
                "completed_nodes": [*payload["completed_nodes"], "legacy"],
                "checkpoint_hook_meta": payload["checkpoint_hook_meta"],
            }
        return await activity_fn(payload)

    monkeypatch.setattr(temporal_runner_module.workflow, "patched", lambda _patch: False)
    monkeypatch.setattr(
        temporal_runner_module.workflow,
        "execute_activity",
        _execute_activity,
    )
    monkeypatch.setattr(
        temporal_runner_module,
        "execute_node_activity",
        _legacy_state_activity,
    )

    result = await ScientistWorkflow().run(
        {
            "workflow_spec_json": workflow_spec.model_dump(mode="json"),
            "initial_state_bytes": serialize_state(base_state),
            "context_meta": {},
            "max_parallelism": 1,
            "merge_conflict_policy": "error",
            "checkpoint_hook_meta": {"completed_nodes": []},
        }
    )

    assert isinstance(result, bytes)
    assert deserialize_state(result).params == {"legacy": True}
    assert len(legacy_merge_payloads) == 1
    assert "result_format" not in legacy_merge_payloads[0]


@pytest.mark.asyncio
async def test_temporal_pre_patch_history_report_does_not_claim_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_temporal_legacy_report_status"
    workflow = _workflow()
    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
    )
    replayed_state = state.model_copy(deep=True)
    replayed_state.params["legacy"] = True

    class LegacyHistoryClient:
        async def execute_workflow(self, *_args, **_kwargs):
            return serialize_state(replayed_state)

    runner = TemporalWorkflowRunner(server_url="unused://temporal")
    monkeypatch.setattr(runner, "_get_client", lambda: _get_client())

    async def _get_client():
        return LegacyHistoryClient()

    result = await runner.execute_workflow(workflow, state, ctx, _registry())

    assert result.state.params["legacy"] is True
    assert result.report.status == "not_established"
    assert result.report.nodes == []


def test_temporal_inject_trace_carrier_records_degraded_path_on_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polisyos.core.observability as observability

    degraded: list[dict[str, object]] = []

    monkeypatch.setattr(
        temporal_runner_module,
        "emit_degraded_path",
        lambda **kwargs: degraded.append(kwargs) or {"reason": kwargs["reason"]},
    )

    def _boom(_carrier: dict[str, str]) -> None:
        raise RuntimeError("trace carrier failure")

    monkeypatch.setattr(observability, "inject_headers", _boom)

    carrier = temporal_runner_module._inject_trace_carrier()

    assert carrier == {}
    assert any(item["reason"] == "trace_carrier_injection_failed" for item in degraded)


@pytest.mark.asyncio
async def test_temporal_health_check_returns_unhealthy_on_probe_error() -> None:
    runner = TemporalWorkflowRunner(server_url="unused://temporal")

    async def _boom():
        raise RuntimeError("probe unavailable")

    runner._get_client = _boom  # type: ignore[method-assign]

    health = await runner.health_check()

    assert health.backend == "temporal"
    assert health.healthy is False
    assert "probe unavailable" in health.message
