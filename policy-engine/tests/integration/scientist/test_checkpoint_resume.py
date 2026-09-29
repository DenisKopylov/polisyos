from __future__ import annotations

import json
import logging
import multiprocessing
import os
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointError,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner.local_runner import LocalWorkflowRunner
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

pytestmark = pytest.mark.integration


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


class StepOneNode:
    calls = 0
    _spec = NodeSpec(
        metadata=_meta("scientist.node_step_one@1.0.0", "StepOne"),
        state_reads=["params.seed"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        StepOneNode.calls += 1
        new_state = state.model_copy(deep=True)
        new_state.params["step1"] = 1
        return NodeOutcome(status="ok", state=new_state)


class StepTwoNode:
    calls = 0
    _spec = NodeSpec(
        metadata=_meta("scientist.node_step_two@1.0.0", "StepTwo"),
        state_reads=["params.step1"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        StepTwoNode.calls += 1
        new_state = state.model_copy(deep=True)
        new_state.params["step2"] = int(new_state.params.get("step1", 0)) + 1
        return NodeOutcome(status="ok", state=new_state)


class FlakyFinalNode:
    calls = 0
    fail_once = True
    _spec = NodeSpec(
        metadata=_meta("scientist.node_flaky_final@1.0.0", "FlakyFinal"),
        state_reads=["params.step2"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        FlakyFinalNode.calls += 1
        if FlakyFinalNode.fail_once:
            FlakyFinalNode.fail_once = False
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.flaky", message="simulated crash"),
            )

        new_state = state.model_copy(deep=True)
        new_state.params["final"] = True
        return NodeOutcome(status="ok", state=new_state)


class ParallelLeftNode:
    calls = 0
    _spec = NodeSpec(
        metadata=_meta("scientist.node_parallel_left@1.0.0", "ParallelLeft"),
        state_writes=["params.left"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        ParallelLeftNode.calls += 1
        new_state = state.model_copy(deep=True)
        new_state.params["left"] = 1
        return NodeOutcome(status="ok", state=new_state)


class ParallelRightNode:
    calls = 0
    _spec = NodeSpec(
        metadata=_meta("scientist.node_parallel_right@1.0.0", "ParallelRight"),
        state_writes=["params.right"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        ParallelRightNode.calls += 1
        new_state = state.model_copy(deep=True)
        new_state.params["right"] = 2
        return NodeOutcome(status="ok", state=new_state)


class FlakyAfterParallelNode:
    calls = 0
    fail_once = True
    _spec = NodeSpec(
        metadata=_meta("scientist.node_parallel_final@1.0.0", "ParallelFinal"),
        state_reads=["params.left", "params.right"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        FlakyAfterParallelNode.calls += 1
        if FlakyAfterParallelNode.fail_once:
            FlakyAfterParallelNode.fail_once = False
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.flaky", message="parallel simulated crash"),
            )

        new_state = state.model_copy(deep=True)
        new_state.params["final"] = True
        return NodeOutcome(status="ok", state=new_state)


def _registry() -> NodeRegistry:
    reg = NodeRegistry()
    reg.register(StepOneNode())
    reg.register(StepTwoNode())
    reg.register(FlakyFinalNode())
    return reg


def _parallel_registry() -> NodeRegistry:
    reg = NodeRegistry()
    reg.register(ParallelLeftNode())
    reg.register(ParallelRightNode())
    reg.register(FlakyAfterParallelNode())
    return reg


def _workflow() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="wf_checkpoint_resume",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="step1",
                node_id=ComponentId.parse("scientist.node_step_one@1.0.0"),
            ),
            NodeInvocation(
                alias="step2",
                node_id=ComponentId.parse("scientist.node_step_two@1.0.0"),
                depends_on=["step1"],
            ),
            NodeInvocation(
                alias="final",
                node_id=ComponentId.parse("scientist.node_flaky_final@1.0.0"),
                depends_on=["step2"],
            ),
        ],
    )


def _parallel_workflow() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="wf_parallel_checkpoint_resume",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="left",
                node_id=ComponentId.parse("scientist.node_parallel_left@1.0.0"),
            ),
            NodeInvocation(
                alias="right",
                node_id=ComponentId.parse("scientist.node_parallel_right@1.0.0"),
            ),
            NodeInvocation(
                alias="final",
                node_id=ComponentId.parse("scientist.node_parallel_final@1.0.0"),
                depends_on=["left", "right"],
            ),
        ],
    )


def _context(
    store: FileSystemCAS,
    run_id: str,
    *,
    tenant_id: str | None = None,
    cell_id: str | None = None,
) -> tuple[ExecutionContext, object]:
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("checkpoint_resume_test"))
    return ctx, bundle.bundle_ref


def _truncate_trace_without_cache_stores(trace_path: Path) -> None:
    records = []
    for line in trace_path.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        evt = json.loads(line)
        if evt.get("event") == "NODE_CACHE_STORE":
            continue
        records.append(evt)
    trace_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=True) for item in records) + "\n",
        encoding="utf-8",
    )


def test_resume_uses_checkpoint_cache_refs_when_trace_is_truncated(tmp_path: Path) -> None:
    StepOneNode.calls = 0
    StepTwoNode.calls = 0
    FlakyFinalNode.calls = 0
    FlakyFinalNode.fail_once = True

    store = FileSystemCAS(tmp_path)
    workflow = _workflow()
    run_id = "R_checkpoint_resume"

    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        params={"seed": 7},
    )
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )

    first = WorkflowExecutor(ctx, _registry(), checkpoint_hook=hook).execute(workflow, state)
    assert first.report.status == "fail"
    assert StepOneNode.calls == 1
    assert StepTwoNode.calls == 1
    assert FlakyFinalNode.calls == 1

    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    head, checkpoint_artifact = resolved
    assert head.sequence_number == 1
    assert checkpoint_artifact.metadata.completed_nodes == ["step1", "step2"]
    assert len(checkpoint_artifact.metadata.cache_entry_refs) >= 2

    trace_path = tmp_path / "runs" / run_id / "trace.jsonl"
    _truncate_trace_without_cache_stores(trace_path)

    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=_registry(),
        registry_bundle_ref=bundle_ref,
        checkpoint_policy="strict",
    )

    assert resumed.report.status == "ok"
    assert resumed.state.params.get("final") is True

    # step1/step2 should be skipped via cache warm-up from checkpoint metadata
    assert StepOneNode.calls == 1
    assert StepTwoNode.calls == 1
    assert FlakyFinalNode.calls == 2


@pytest.mark.parametrize(
    ("resume_tenant_id", "resume_cell_id"),
    [("tenant-b", "cell-a"), ("tenant-a", "cell-b")],
)
def test_resume_rejects_mismatched_tenant_or_cell_before_protected_action(
    tmp_path: Path,
    resume_tenant_id: str,
    resume_cell_id: str,
) -> None:
    StepOneNode.calls = 0
    StepTwoNode.calls = 0
    FlakyFinalNode.calls = 0
    FlakyFinalNode.fail_once = True

    store = FileSystemCAS(tmp_path)
    workflow = _workflow()
    run_id = "R_checkpoint_tenant_scope"
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        ctx, bundle_ref = _context(
            store,
            run_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
        )
        state = ExperimentState(
            run_id=run_id,
            inputs={"registry_bundle_ref": bundle_ref},
            params={"seed": 13},
        )
        hook = CASCheckpointHook(
            store=store,
            run_dir=tmp_path / "runs" / run_id,
            checkpoint_policy="strict",
        )
        first = WorkflowExecutor(ctx, _registry(), checkpoint_hook=hook).execute(workflow, state)

    assert first.report.status == "fail"
    protected_calls_before = (
        StepOneNode.calls,
        StepTwoNode.calls,
        FlakyFinalNode.calls,
    )
    trace_path = tmp_path / "runs" / run_id / "trace.jsonl"
    trace_before = trace_path.read_bytes()

    with (
        tenant_scope(None, tenant_id=resume_tenant_id, cell_id=resume_cell_id),
        pytest.raises(CheckpointError, match="scope mismatch"),
    ):
        resume_from_checkpoint(
            store,
            run_id,
            workflow=workflow,
            registry=_registry(),
            registry_bundle_ref=bundle_ref,
            checkpoint_policy="strict",
        )

    assert (
        StepOneNode.calls,
        StepTwoNode.calls,
        FlakyFinalNode.calls,
    ) == protected_calls_before
    assert trace_path.read_bytes() == trace_before

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        resumed = resume_from_checkpoint(
            store,
            run_id,
            workflow=workflow,
            registry=_registry(),
            registry_bundle_ref=bundle_ref,
            checkpoint_policy="strict",
        )

    assert resumed.report.status == "ok"
    assert resumed.state.params.get("final") is True
    assert StepOneNode.calls == 1
    assert StepTwoNode.calls == 1
    assert FlakyFinalNode.calls == 2


def test_resume_falls_back_to_local_runner_when_distributed_backend_is_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "temporal")

    StepOneNode.calls = 0
    StepTwoNode.calls = 0
    FlakyFinalNode.calls = 0
    FlakyFinalNode.fail_once = True

    store = FileSystemCAS(tmp_path)
    workflow = _workflow()
    run_id = "R_checkpoint_resume_temporal_config"

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

    first = WorkflowExecutor(ctx, _registry(), checkpoint_hook=hook).execute(workflow, state)
    assert first.report.status == "fail"
    assert StepOneNode.calls == 1
    assert StepTwoNode.calls == 1
    assert FlakyFinalNode.calls == 1

    trace_path = tmp_path / "runs" / run_id / "trace.jsonl"
    _truncate_trace_without_cache_stores(trace_path)

    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=_registry(),
        registry_bundle_ref=bundle_ref,
        checkpoint_policy="strict",
    )

    assert resumed.report.status == "ok"
    assert resumed.state.params.get("final") is True
    assert StepOneNode.calls == 1
    assert StepTwoNode.calls == 1
    assert FlakyFinalNode.calls == 2


def test_resume_uses_configured_distributed_runner_with_pruned_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "temporal")
    monkeypatch.setenv("POLISYOS_TEMPORAL_SERVER_URL", "grpc://unused")

    StepOneNode.calls = 0
    StepTwoNode.calls = 0
    FlakyFinalNode.calls = 0
    FlakyFinalNode.fail_once = True

    store = FileSystemCAS(tmp_path)
    workflow = _workflow()
    run_id = "R_checkpoint_resume_distributed_pruned"

    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        params={"seed": 17},
    )
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )

    first = WorkflowExecutor(ctx, _registry(), checkpoint_hook=hook).execute(workflow, state)
    assert first.report.status == "fail"
    assert StepOneNode.calls == 1
    assert StepTwoNode.calls == 1
    assert FlakyFinalNode.calls == 1

    trace_path = tmp_path / "runs" / run_id / "trace.jsonl"
    _truncate_trace_without_cache_stores(trace_path)

    class _CapturingRunner:
        def __init__(self) -> None:
            self.workflow_aliases: list[str] = []
            self.cache_seed_refs = None
            self.calls = 0

        async def execute_workflow(
            self,
            workflow,
            state,
            ctx,
            registry,
            *,
            checkpoint_hook=None,
            checkpoint_cache_seed_refs=None,
            max_parallelism=None,
        ):
            self.calls += 1
            self.workflow_aliases = [inv.alias for inv in workflow.nodes]
            self.cache_seed_refs = list(checkpoint_cache_seed_refs or [])
            return await AsyncWorkflowExecutor(
                ctx,
                registry,
                checkpoint_hook=checkpoint_hook,
                checkpoint_cache_seed_refs=checkpoint_cache_seed_refs,
                max_parallelism=max_parallelism or 4,
            ).execute(workflow, state)

    capturing_runner = _CapturingRunner()
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.runner.config.build_workflow_runner",
        lambda config: capturing_runner,
    )

    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=_registry(),
        registry_bundle_ref=bundle_ref,
        checkpoint_policy="strict",
    )

    assert resumed.report.status == "ok"
    assert resumed.state.params.get("final") is True
    assert capturing_runner.calls == 1
    assert capturing_runner.workflow_aliases == ["final"]
    assert StepOneNode.calls == 1
    assert StepTwoNode.calls == 1
    assert FlakyFinalNode.calls == 2

    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    _, checkpoint_artifact = resolved
    assert checkpoint_artifact.metadata.completed_nodes == ["step1", "step2", "final"]


@pytest.mark.asyncio
async def test_async_executor_resume_uses_checkpoint_cache_refs_when_trace_is_truncated(
    tmp_path: Path,
) -> None:
    StepOneNode.calls = 0
    StepTwoNode.calls = 0
    FlakyFinalNode.calls = 0
    FlakyFinalNode.fail_once = True

    store = FileSystemCAS(tmp_path)
    workflow = _workflow()
    run_id = "R_async_checkpoint_resume"

    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        params={"seed": 7},
    )
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )

    first = await AsyncWorkflowExecutor(
        ctx,
        _registry(),
        checkpoint_hook=hook,
    ).execute(workflow, state)
    assert first.report.status == "fail"
    assert StepOneNode.calls == 1
    assert StepTwoNode.calls == 1
    assert FlakyFinalNode.calls == 1

    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    head, checkpoint_artifact = resolved
    assert head.sequence_number == 1
    assert checkpoint_artifact.metadata.completed_nodes == ["step1", "step2"]
    assert len(checkpoint_artifact.metadata.cache_entry_refs) >= 2

    trace_path = tmp_path / "runs" / run_id / "trace.jsonl"
    _truncate_trace_without_cache_stores(trace_path)

    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=_registry(),
        registry_bundle_ref=bundle_ref,
        checkpoint_policy="strict",
    )

    assert resumed.report.status == "ok"
    assert resumed.state.params.get("final") is True
    assert StepOneNode.calls == 1
    assert StepTwoNode.calls == 1
    assert FlakyFinalNode.calls == 2



class _SimulatedWorkerStopError(RuntimeError):
    """Stop immediately after a checkpoint becomes the durable head."""


class _StopAfterTierCheckpoint(CASCheckpointHook):
    async def on_tier_complete_async(
        self,
        *,
        state: ExperimentState,
        alias: str,
        node_id: str,
        completed_nodes: list[str],
        workflow_id: str,
        workflow_fingerprint: str,
        cache_entry_refs: list[ArtifactRef],
    ) -> None:
        await super().on_tier_complete_async(
            state=state,
            alias=alias,
            node_id=node_id,
            completed_nodes=completed_nodes,
            workflow_id=workflow_id,
            workflow_fingerprint=workflow_fingerprint,
            cache_entry_refs=cache_entry_refs,
        )
        raise _SimulatedWorkerStopError("worker stopped after checkpoint publication")


class _NodeOnlyCASCheckpointHook:
    """Expose only the single-node callback of the real CAS checkpoint owner."""

    def __init__(self, delegate: CASCheckpointHook) -> None:
        self._delegate = delegate
        self.calls = 0

    async def on_node_complete_async(self, **kwargs: Any) -> Any:
        self.calls += 1
        return await self._delegate.on_node_complete_async(**kwargs)


def _resume_parallel_tier_in_fresh_process(
    cas_root: str,
    run_id: str,
    bundle_ref_payload: dict[str, Any],
    result_queue: Any,
) -> None:
    """Read and resume a durable tier head without the writer's process state."""
    ParallelLeftNode.calls = 0
    ParallelRightNode.calls = 0
    FlakyAfterParallelNode.calls = 0
    FlakyAfterParallelNode.fail_once = False

    reopened_store = FileSystemCAS(Path(cas_root))
    resolved = resolve_latest_checkpoint(reopened_store, run_id)
    assert resolved is not None
    head, checkpoint_artifact = resolved
    assert checkpoint_artifact.state is not None

    resumed = resume_from_checkpoint(
        reopened_store,
        run_id,
        workflow=_parallel_workflow(),
        registry=_parallel_registry(),
        registry_bundle_ref=ArtifactRef.model_validate(bundle_ref_payload),
        checkpoint_policy="strict",
    )
    result_queue.put(
        {
            "pid": os.getpid(),
            "sequence_number": head.sequence_number,
            "completed_nodes": checkpoint_artifact.metadata.completed_nodes,
            "checkpoint_params": checkpoint_artifact.state["params"],
            "report_status": resumed.report.status,
            "resumed_params": resumed.state.params,
            "peer_calls": [ParallelLeftNode.calls, ParallelRightNode.calls],
            "final_calls": FlakyAfterParallelNode.calls,
        }
    )


@pytest.mark.asyncio
async def test_parallel_tier_rejects_node_only_hook_before_any_side_effect(
    tmp_path: Path,
) -> None:
    ParallelLeftNode.calls = 0
    ParallelRightNode.calls = 0
    FlakyAfterParallelNode.calls = 0

    store = FileSystemCAS(tmp_path)
    workflow = _parallel_workflow()
    run_id = "R_async_parallel_node_only_hook_refused"
    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        params={"seed": 31},
    )
    hook = _NodeOnlyCASCheckpointHook(
        CASCheckpointHook(
            store=store,
            run_dir=tmp_path / "runs" / run_id,
            checkpoint_policy="strict",
        )
    )

    with pytest.raises(CheckpointError, match="parallel_tier_requires_atomic_checkpoint_hook"):
        await LocalWorkflowRunner(max_parallelism=2).execute_workflow(
            workflow,
            state,
            ctx,
            _parallel_registry(),
            checkpoint_hook=hook,  # type: ignore[arg-type]
        )

    assert ParallelLeftNode.calls == 0
    assert ParallelRightNode.calls == 0
    assert FlakyAfterParallelNode.calls == 0
    assert hook.calls == 0
    assert resolve_latest_checkpoint(store, run_id) is None


@pytest.mark.asyncio
async def test_parallel_tier_checkpoint_survives_stop_without_reapplying_any_peer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ParallelLeftNode.calls = 0
    ParallelRightNode.calls = 0
    FlakyAfterParallelNode.calls = 0
    FlakyAfterParallelNode.fail_once = True

    store = FileSystemCAS(tmp_path)
    workflow = _parallel_workflow()
    run_id = "R_async_parallel_stop_after_tier_checkpoint"
    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        params={"seed": 29},
    )
    hook = _StopAfterTierCheckpoint(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )

    with pytest.raises(_SimulatedWorkerStopError):
        await LocalWorkflowRunner(max_parallelism=2).execute_workflow(
            workflow,
            state,
            ctx,
            _parallel_registry(),
            checkpoint_hook=hook,
        )

    assert ParallelLeftNode.calls == 1
    assert ParallelRightNode.calls == 1
    assert FlakyAfterParallelNode.calls == 0

    assert isinstance(bundle_ref, ArtifactRef)
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    process_context = multiprocessing.get_context("spawn")
    result_queue = process_context.Queue()
    child = process_context.Process(
        target=_resume_parallel_tier_in_fresh_process,
        args=(str(tmp_path), run_id, bundle_ref.model_dump(mode="json"), result_queue),
    )
    try:
        child.start()
        child.join(timeout=60)
        assert child.exitcode == 0
        observed = result_queue.get(timeout=5)
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=5)
        result_queue.close()

    assert observed["pid"] != os.getpid()
    assert observed["completed_nodes"] == ["left", "right"]
    assert observed["checkpoint_params"] == {"seed": 29, "left": 1, "right": 2}
    assert observed["sequence_number"] == 1
    assert observed["report_status"] == "ok"
    assert observed["resumed_params"] == {
        "seed": 29,
        "left": 1,
        "right": 2,
        "final": True,
    }
    assert observed["peer_calls"] == [0, 0]
    assert observed["final_calls"] == 1
    assert ParallelLeftNode.calls == 1
    assert ParallelRightNode.calls == 1
    assert FlakyAfterParallelNode.calls == 0


@pytest.mark.asyncio
async def test_async_executor_parallel_tier_checkpoints_merged_state_for_resume(
    tmp_path: Path,
) -> None:
    ParallelLeftNode.calls = 0
    ParallelRightNode.calls = 0
    FlakyAfterParallelNode.calls = 0
    FlakyAfterParallelNode.fail_once = True

    store = FileSystemCAS(tmp_path)
    workflow = _parallel_workflow()
    run_id = "R_async_parallel_resume"

    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        params={"seed": 3},
    )
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )

    first = await AsyncWorkflowExecutor(
        ctx,
        _parallel_registry(),
        checkpoint_hook=hook,
        max_parallelism=2,
    ).execute(workflow, state)
    assert first.report.status == "fail"
    assert ParallelLeftNode.calls == 1
    assert ParallelRightNode.calls == 1
    assert FlakyAfterParallelNode.calls == 1

    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    head, checkpoint_artifact = resolved
    assert head.sequence_number == 1
    assert checkpoint_artifact.metadata.completed_nodes == ["left", "right"]
    assert checkpoint_artifact.state is not None
    assert checkpoint_artifact.state["params"]["left"] == 1
    assert checkpoint_artifact.state["params"]["right"] == 2
    assert "final" not in checkpoint_artifact.state["params"]
    assert len(checkpoint_artifact.metadata.cache_entry_refs) >= 2

    trace_path = tmp_path / "runs" / run_id / "trace.jsonl"
    _truncate_trace_without_cache_stores(trace_path)

    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=_parallel_registry(),
        registry_bundle_ref=bundle_ref,
        checkpoint_policy="strict",
    )

    assert resumed.report.status == "ok"
    assert resumed.state.params["left"] == 1
    assert resumed.state.params["right"] == 2
    assert resumed.state.params["final"] is True
    assert ParallelLeftNode.calls == 1
    assert ParallelRightNode.calls == 1
    assert FlakyAfterParallelNode.calls == 2
