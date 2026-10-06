from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import inspect
import json
import logging
import multiprocessing
import os
from pathlib import Path
from typing import Any, Literal

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointError,
    _build_resume_workflow_spec,
    compute_workflow_fingerprint,
    load_checkpoint,
    load_checkpoint_head,
    load_checkpoint_history,
    materialize_checkpoint_state,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutor,
    _merge_cached_outcome_state,
)
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeCacheEntry,
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeOutcome,
    NodeSpec,
    decode_node_outcome,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner.local_runner import (
    LocalWorkflowRunner,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import (
    NodeInvocation,
    WorkflowSpec,
)

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


class FailOnceParallelRightNode:
    """Fail its first call so checkpoint policies can be observed across resume."""

    calls = 0
    fail_once = True
    _spec = NodeSpec(
        metadata=_meta("scientist.node_parallel_right@1.0.0", "FlakyParallelRight"),
        state_writes=["params.right"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        type(self).calls += 1
        if type(self).fail_once:
            type(self).fail_once = False
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.flaky", message="simulated peer failure"),
            )

        new_state = state.model_copy(deep=True)
        new_state.params["right"] = 2
        return NodeOutcome(status="ok", state=new_state)


def _seeded_parallel_workflow(
    *, error_policy: Literal["fail_fast", "continue"] = "fail_fast"
) -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="wf_seeded_parallel_checkpoint_resume",
        required_binds=["run_id"],
        error_policy=error_policy,
        nodes=[
            NodeInvocation(
                alias="seed",
                node_id=ComponentId.parse("scientist.node_step_one@1.0.0"),
            ),
            NodeInvocation(
                alias="left",
                node_id=ComponentId.parse("scientist.node_parallel_left@1.0.0"),
                depends_on=["seed"],
            ),
            NodeInvocation(
                alias="right",
                node_id=ComponentId.parse("scientist.node_parallel_right@1.0.0"),
                depends_on=["seed"],
            ),
            NodeInvocation(
                alias="final",
                node_id=ComponentId.parse("scientist.node_parallel_final@1.0.0"),
                depends_on=["left", "right"],
            ),
        ],
    )


def _seeded_parallel_registry(*, right_node: Any | None = None) -> NodeRegistry:
    registry = NodeRegistry()
    for node in (
        StepOneNode(),
        ParallelLeftNode(),
        right_node or ParallelRightNode(),
        FlakyAfterParallelNode(),
    ):
        registry.register(node)
    return registry


def _seed_parallel_checkpoint(
    store: FileSystemCAS,
    *,
    run_id: str,
    workflow: WorkflowSpec,
) -> tuple[ExecutionContext, ArtifactRef, ExperimentState]:
    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        params={"seed": 29},
    )
    StepOneNode.calls = 0
    seeded = StepOneNode().execute(ctx, state)
    hook = CASCheckpointHook(
        store=store,
        run_dir=Path(store.root) / "runs" / run_id,
        checkpoint_policy="strict",
    )
    hook.mark_completed_node_status_established(prior_completed_nodes=[])
    hook.on_node_complete(
        state=seeded.state,
        alias="seed",
        node_id=str(workflow.nodes[0].node_id),
        completed_nodes=["seed"],
        workflow_id=workflow.workflow_id,
        workflow_fingerprint=compute_workflow_fingerprint(workflow),
        cache_entry_ref=None,
    )
    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    _, checkpoint = resolved
    assert checkpoint.state is not None
    assert checkpoint.metadata.completed_nodes == ["seed"]
    assert checkpoint.state["params"] == {"seed": 29, "step1": 1}
    return ctx, bundle_ref, seeded.state


def _install_b73_left_frontier_removal() -> dict[str, Any]:
    """Omit one completed peer in the spawned child, pinned to the owner source."""
    executor_module = importlib.import_module(
        "polisyos.scientist.orchestration.engine.async_executor"
    )
    executor_class = executor_module.AsyncWorkflowExecutor
    if executor_class is not AsyncWorkflowExecutor:
        raise AssertionError("B73 removal probe loaded a different executor class")

    module_path = Path(executor_module.__file__).resolve()
    class_path = Path(inspect.getsourcefile(executor_class) or "").resolve()
    code_path = Path(executor_class.execute.__code__.co_filename).resolve()
    if class_path != module_path or code_path != module_path:
        raise AssertionError("B73 removal probe executor source origin changed")
    source_bytes = module_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != ("ba199986b9ca60cd2b110af6d03ccdf679c9321426a01538ea0034e7898be66b"):
        raise AssertionError("B73 removal probe executor source digest changed")

    source_tree = ast.parse(source_bytes.decode("utf-8"), filename=str(module_path))
    executor_classes = [
        node
        for node in source_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AsyncWorkflowExecutor"
    ]
    if len(executor_classes) != 1:
        raise AssertionError("B73 removal probe found an unexpected executor class count")
    execute_methods = [
        node
        for node in executor_classes[0].body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "execute"
    ]
    if len(execute_methods) != 1 or execute_methods[0].decorator_list:
        raise AssertionError("B73 removal probe found an unexpected execute method")

    def is_completed_frontier_extend(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "extend"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "completed_nodes"
            and len(node.args) == 1
            and not node.keywords
        )

    def has_original_frontier_argument(node: ast.Call) -> bool:
        return isinstance(node.args[0], ast.Name) and node.args[0].id == "tier_completed"

    all_frontier_extends = [
        node for node in ast.walk(source_tree) if is_completed_frontier_extend(node)
    ]
    if len(all_frontier_extends) != 1 or not has_original_frontier_argument(
        all_frontier_extends[0]
    ):
        raise AssertionError("B73 removal probe found an unexpected frontier producer count")

    original_method = copy.deepcopy(execute_methods[0])
    mutant_method = copy.deepcopy(execute_methods[0])
    mutant_frontier_extends = [
        node for node in ast.walk(mutant_method) if is_completed_frontier_extend(node)
    ]
    if len(mutant_frontier_extends) != 1:
        raise AssertionError("B73 removal probe could not isolate the frontier producer")
    original_argument = copy.deepcopy(mutant_frontier_extends[0].args[0])
    alias = "b73_frontier_alias"
    mutant_frontier_extends[0].args[0] = ast.GeneratorExp(
        elt=ast.Name(id=alias, ctx=ast.Load()),
        generators=[
            ast.comprehension(
                target=ast.Name(id=alias, ctx=ast.Store()),
                iter=ast.Name(id="tier_completed", ctx=ast.Load()),
                ifs=[
                    ast.Compare(
                        left=ast.Name(id=alias, ctx=ast.Load()),
                        ops=[ast.NotEq()],
                        comparators=[ast.Constant(value="left")],
                    )
                ],
                is_async=0,
            )
        ],
    )

    restored_method = copy.deepcopy(mutant_method)
    restored_frontier_extends = [
        node for node in ast.walk(restored_method) if is_completed_frontier_extend(node)
    ]
    if len(restored_frontier_extends) != 1:
        raise AssertionError("B73 removal probe restoration lost the frontier producer")
    restored_frontier_extends[0].args[0] = original_argument
    if ast.dump(restored_method, include_attributes=False) != ast.dump(
        original_method, include_attributes=False
    ):
        raise AssertionError("B73 removal probe changed AST outside the target argument")

    mutated_expression = ast.unparse(mutant_frontier_extends[0])
    compiled_module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__",
                names=[ast.alias(name="annotations")],
                level=0,
            ),
            mutant_method,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(compiled_module)
    namespace = dict(executor_module.__dict__)
    exec(  # noqa: S102 - hash-pinned native AST property-removal control
        compile(compiled_module, filename=str(module_path), mode="exec"),
        namespace,
    )
    replacement = namespace.get("execute")
    if replacement is None or not inspect.iscoroutinefunction(replacement):
        raise AssertionError("B73 removal probe did not compile the async owner method")
    if Path(replacement.__code__.co_filename).resolve() != module_path:
        raise AssertionError("B73 removal probe replacement lost source identity")
    executor_class.execute = replacement
    return {
        "source_sha256": source_sha256,
        "method": "AsyncWorkflowExecutor.execute",
        "original_expression": "completed_nodes.extend(tier_completed)",
        "mutated_expression": mutated_expression,
        "mutant_installed": True,
    }


def _b73_pause_writer_at_owner_phase(
    cas_root: str,
    run_id: str,
    bundle_ref_payload: dict[str, Any],
    cut: Literal["after_artifact_before_head", "after_head_before_history"],
    remove_left_from_frontier: bool,
    phase_queue: Any,
    release_event: Any,
) -> None:
    os.environ["POLISYOS_RUNNER_BACKEND"] = "local"
    os.environ["POLISYOS_RUNNER_MAX_PARALLELISM"] = "2"
    ParallelLeftNode.calls = 0
    ParallelRightNode.calls = 0
    FlakyAfterParallelNode.calls = 0
    FlakyAfterParallelNode.fail_once = False

    store = FileSystemCAS(Path(cas_root))
    bundle_ref = ArtifactRef.model_validate(bundle_ref_payload)
    workflow = _seeded_parallel_workflow()
    checkpoint_module = importlib.import_module(
        "polisyos.scientist.orchestration.engine.checkpoint"
    )
    mutation_receipt: dict[str, Any] | None = None
    if remove_left_from_frontier:
        if cut != "after_artifact_before_head":
            raise AssertionError("B73 removal probe is limited to the first publication cut")
        mutation_receipt = _install_b73_left_frontier_removal()

    if cut == "after_artifact_before_head":
        original_update_head = checkpoint_module.update_checkpoint_head

        def pause_before_head(run_dir: Path, **kwargs: Any) -> Any:
            checkpoint_ref = kwargs["checkpoint_ref"]
            phase_queue.put(
                {
                    "phase": cut,
                    "mutation_receipt": mutation_receipt,
                    "checkpoint_ref": checkpoint_ref.model_dump(mode="json"),
                    "sequence_number": kwargs["sequence_number"],
                    "left_calls": ParallelLeftNode.calls,
                    "right_calls": ParallelRightNode.calls,
                    "final_calls": FlakyAfterParallelNode.calls,
                }
            )
            release_event.wait(180)
            return original_update_head(run_dir, **kwargs)

        checkpoint_module.update_checkpoint_head = pause_before_head
    elif cut == "after_head_before_history":
        original_append_history = checkpoint_module.append_checkpoint_history

        def pause_before_history(run_dir: Path, head: Any) -> None:
            phase_queue.put(
                {
                    "phase": cut,
                    "mutation_receipt": mutation_receipt,
                    "checkpoint_ref": head.checkpoint_ref.model_dump(mode="json"),
                    "sequence_number": head.sequence_number,
                    "left_calls": ParallelLeftNode.calls,
                    "right_calls": ParallelRightNode.calls,
                    "final_calls": FlakyAfterParallelNode.calls,
                }
            )
            release_event.wait(180)
            original_append_history(run_dir, head)

        checkpoint_module.append_checkpoint_history = pause_before_history
    else:  # pragma: no cover - the process target receives only the two declared cuts.
        raise AssertionError(f"unknown checkpoint cut: {cut}")

    resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=_seeded_parallel_registry(),
        registry_bundle_ref=bundle_ref,
        checkpoint_policy="strict",
    )


def _assert_tier_cache_entries_bind_node_identity_and_content(
    store: FileSystemCAS,
    *,
    run_id: str,
    workflow: WorkflowSpec,
    completed_nodes: list[str],
    checkpoint_state: dict[str, Any],
    cache_entry_refs: list[ArtifactRef],
) -> tuple[str, ...]:
    """Resolve and verify cache entries for exactly the committed peer nodes."""
    peer_values = {"left": 1, "right": 2}
    expected_invocations = {
        invocation.alias: invocation
        for invocation in workflow.nodes
        if invocation.alias in peer_values and invocation.alias in completed_nodes
    }
    assert len(cache_entry_refs) == len(expected_invocations)
    artifact_ids = [str(ref.artifact_id) for ref in cache_entry_refs]
    assert len(artifact_ids) == len(set(artifact_ids))

    invocations_by_node_id = {
        str(invocation.node_id): invocation for invocation in expected_invocations.values()
    }
    observed_aliases: set[str] = set()
    proof_reader = NodeResultCache(store, run_id=run_id)
    peer_input_state = ExperimentState.model_validate(checkpoint_state)
    for alias in peer_values:
        peer_input_state.params.pop(alias, None)
    assert peer_input_state.params == {"seed": 29, "step1": 1}
    registry = _seeded_parallel_registry()
    for ref in cache_entry_refs:
        assert ref.kind == "scientist.node_cache_entry"
        assert ref.media_type == "application/json"
        assert store.verify(ref).ok
        manifest = store.get_manifest(ref)
        assert manifest.artifact_id == ref.artifact_id
        assert manifest.kind == ref.kind
        assert manifest.media_type == ref.media_type
        data = store.get_bytes(ref)
        assert hashlib.sha256(data).hexdigest() == ref.artifact_id.hex
        assert manifest.integrity.sha256 == ref.artifact_id.hex
        payload = from_canonical_bytes(data)
        entry = NodeCacheEntry.model_validate(payload)
        assert entry.schema_version == "2.0"
        assert entry.run_id == run_id
        invocation = invocations_by_node_id.get(entry.node_id)
        assert invocation is not None
        assert invocation.alias not in observed_aliases
        expected_key = compute_idempotency_key(
            spec=registry.get(invocation.node_id).spec,
            state=peer_input_state,
            bind_params=invocation.params,
        )
        assert entry.idempotency_key == expected_key
        assert entry.outcome_payload is not None
        assert entry.outcome_ref is None
        outcome = decode_node_outcome(entry.outcome_payload)
        assert outcome.status == "ok"
        assert outcome.state.run_id == run_id
        assert outcome.state.params.get(invocation.alias) == peer_values[invocation.alias]
        # The existing cache reader verifies CAS integrity, manifest profile,
        # run binding, and the versioned replay proof including the cache key.
        assert entry.state_mutations_version == "1.0"
        assert entry.replay_epoch == "2.1"
        assert [(op.path, op.operation, op.value) for op in entry.state_mutations] == [
            ("params." + invocation.alias, "set", peer_values[invocation.alias])
        ]
        assert entry.journal_proof is not None
        assert entry.journal_proof.manifest_schema == manifest.artifact_schema
        assert entry.journal_proof.manifest_producer == manifest.producer
        assert proof_reader.seed_from_entry_refs([ref]) == 1
        loaded = proof_reader.get(expected_key)
        assert loaded is not None
        base = peer_input_state.model_copy(deep=True)
        base.params["unrelated"] = "current"
        applied = _merge_cached_outcome_state(
            alias=invocation.alias,
            node=registry.get(invocation.node_id),
            base_state=base,
            outcome=loaded,
        )
        assert applied.params == {
            "seed": 29,
            "step1": 1,
            "unrelated": "current",
            invocation.alias: peer_values[invocation.alias],
        }
        observed_aliases.add(invocation.alias)

    assert observed_aliases == set(expected_invocations)
    return tuple(sorted(observed_aliases))


def _b73_trace_records(store: FileSystemCAS, run_id: str) -> list[dict[str, Any]]:
    trace = Path(store.root) / "runs" / run_id / "trace.jsonl"
    return [json.loads(line) for line in trace.read_text().splitlines()]


def _b73_trace_cache_snapshot(
    store: FileSystemCAS,
    *,
    run_id: str,
    workflow: WorkflowSpec,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve actual published peer cache bytes independently of the durable frontier."""
    peer_node_ids = {
        str(inv.node_id): inv.alias for inv in workflow.nodes if inv.alias in {"left", "right"}
    }
    refs: dict[str, ArtifactRef] = {}
    for record in records:
        if record["event"] != "NODE_CACHE_STORE":
            continue
        for raw in record.get("refs", {}).get("outputs", []):
            ref = ArtifactRef.model_validate(raw)
            if ref.kind != "scientist.node_cache_entry":
                continue
            entry = NodeCacheEntry.model_validate(from_canonical_bytes(store.get_bytes(ref)))
            alias = peer_node_ids.get(entry.node_id)
            if alias is not None:
                assert record["phase"] == "scientist.node." + alias
                if alias in refs:
                    assert refs[alias] == ref
                refs[alias] = ref
    aliases = _assert_tier_cache_entries_bind_node_identity_and_content(
        store,
        run_id=run_id,
        workflow=workflow,
        completed_nodes=["seed", *refs],
        checkpoint_state={"run_id": run_id, "params": {"seed": 29, "step1": 1}},
        cache_entry_refs=list(refs.values()),
    )
    return {
        "aliases": list(aliases),
        "refs": {alias: ref.model_dump(mode="json") for alias, ref in refs.items()},
    }


def _b73_cache_hit_aliases(records: list[dict[str, Any]]) -> list[str]:
    hits = []
    for record in records:
        if record["event"] == "NODE_CACHE_HIT" and record["phase"] in {
            "scientist.node.left",
            "scientist.node.right",
        }:
            assert record["metrics"]["cache_hit"] == 1
            hits.append(record["phase"].rsplit(".", 1)[1])
    return sorted(hits)


def _b73_fresh_reader_then_resume(
    cas_root: str,
    run_id: str,
    bundle_ref_payload: dict[str, Any],
    result_queue: Any,
) -> None:
    """Reopen, verify committed peer entries, and resume from a new process."""
    os.environ["POLISYOS_RUNNER_BACKEND"] = "local"
    os.environ["POLISYOS_RUNNER_MAX_PARALLELISM"] = "2"
    ParallelLeftNode.calls = 0
    ParallelRightNode.calls = 0
    FlakyAfterParallelNode.calls = 0
    FlakyAfterParallelNode.fail_once = False

    store = FileSystemCAS(Path(cas_root))
    bundle_ref = ArtifactRef.model_validate(bundle_ref_payload)
    workflow = _seeded_parallel_workflow()
    before = resolve_latest_checkpoint(store, run_id)
    if before is None:
        raise AssertionError("fresh reader did not resolve a committed checkpoint")
    head, checkpoint = before
    assert checkpoint.state is not None
    verified_cache_aliases = _assert_tier_cache_entries_bind_node_identity_and_content(
        store,
        run_id=run_id,
        workflow=workflow,
        completed_nodes=checkpoint.metadata.completed_nodes,
        checkpoint_state=checkpoint.state,
        cache_entry_refs=checkpoint.metadata.cache_entry_refs,
    )
    before_records = _b73_trace_records(store, run_id)
    trace_cache = _b73_trace_cache_snapshot(
        store, run_id=run_id, workflow=workflow, records=before_records
    )
    before_resume = {
        "sequence_number": head.sequence_number,
        "checkpoint_ref": str(head.checkpoint_ref.artifact_id),
        "completed_nodes": list(checkpoint.metadata.completed_nodes),
        "params": dict(checkpoint.state["params"]),
        "cache_entry_refs": [str(ref.artifact_id) for ref in checkpoint.metadata.cache_entry_refs],
        "cache_aliases": list(verified_cache_aliases),
        "trace_cache": trace_cache,
        "workflow_fingerprint": checkpoint.metadata.workflow_fingerprint,
        "origin_workflow_fingerprint": checkpoint.metadata.origin_workflow_fingerprint,
    }

    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=_seeded_parallel_registry(),
        registry_bundle_ref=bundle_ref,
        checkpoint_policy="strict",
    )
    result_queue.put(
        {
            "pid": os.getpid(),
            "before_resume": before_resume,
            "report_status": resumed.report.status,
            "resumed_params": dict(resumed.state.params),
            "peer_calls": [ParallelLeftNode.calls, ParallelRightNode.calls],
            "cache_hit_aliases": _b73_cache_hit_aliases(
                _b73_trace_records(store, run_id)[len(before_records) :]
            ),
            "final_calls": FlakyAfterParallelNode.calls,
        }
    )


def test_seeded_checkpoint_publication_cuts_reopen_old_or_complete_frontier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh reader follows only the atomic head's committed tier frontier."""
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    monkeypatch.setenv("POLISYOS_RUNNER_MAX_PARALLELISM", "2")
    process_context = multiprocessing.get_context("spawn")
    for cut in ("after_artifact_before_head", "after_head_before_history"):
        store = FileSystemCAS(tmp_path / cut)
        workflow = _seeded_parallel_workflow()
        run_id = f"R_b73_seeded_publication_cut_{cut}"
        _, bundle_ref, _ = _seed_parallel_checkpoint(store, run_id=run_id, workflow=workflow)
        run_dir = Path(store.root) / "runs" / run_id
        seed_head = load_checkpoint_head(run_dir)
        assert seed_head is not None
        seed_checkpoint = load_checkpoint(store, seed_head.checkpoint_ref)
        seed_completed_nodes = list(seed_checkpoint.metadata.completed_nodes)
        assert seed_completed_nodes == ["seed"]
        expected_origin_fingerprint = compute_workflow_fingerprint(workflow)
        expected_residual_fingerprint = compute_workflow_fingerprint(
            _build_resume_workflow_spec(
                workflow,
                completed_nodes=seed_completed_nodes,
            )
        )
        phase_queue = process_context.Queue()
        release_event = process_context.Event()
        writer = process_context.Process(
            target=_b73_pause_writer_at_owner_phase,
            args=(
                str(store.root),
                run_id,
                bundle_ref.model_dump(mode="json"),
                cut,
                os.environ.get("POLISYOS_B73_REMOVE_LEFT_FRONTIER") == "1"
                and cut == "after_artifact_before_head",
                phase_queue,
                release_event,
            ),
        )
        try:
            writer.start()
            observed = phase_queue.get(timeout=60)
            assert observed["phase"] == cut
            remove_left_for_cut = (
                os.environ.get("POLISYOS_B73_REMOVE_LEFT_FRONTIER") == "1"
                and cut == "after_artifact_before_head"
            )
            if remove_left_for_cut:
                assert observed["mutation_receipt"] == {
                    "source_sha256": (
                        "ba199986b9ca60cd2b110af6d03ccdf679c9321426a01538ea0034e7898be66b"
                    ),
                    "method": "AsyncWorkflowExecutor.execute",
                    "original_expression": "completed_nodes.extend(tier_completed)",
                    "mutated_expression": (
                        "completed_nodes.extend(("
                        "b73_frontier_alias for b73_frontier_alias "
                        "in tier_completed if b73_frontier_alias != 'left'))"
                    ),
                    "mutant_installed": True,
                }
            else:
                assert observed["mutation_receipt"] is None
            assert observed["left_calls"] == 1
            assert observed["right_calls"] == 1
            assert observed["final_calls"] == 0

            observed_ref = ArtifactRef.model_validate(observed["checkpoint_ref"])
            history = load_checkpoint_history(run_dir)
            history_refs = (
                []
                if history is None
                else [str(entry.checkpoint_ref.artifact_id) for entry in history.entries]
            )
            if cut == "after_artifact_before_head":
                current_head = load_checkpoint_head(run_dir)
                assert current_head == seed_head
                assert str(observed_ref.artifact_id) not in history_refs
                uncommitted = load_checkpoint(store, observed_ref)
                uncommitted_state = materialize_checkpoint_state(store, observed_ref)
                assert (
                    uncommitted.metadata.completed_node_status_contract == "native_node_outcome_v1"
                )
                assert uncommitted_state["params"] == {
                    "seed": 29,
                    "step1": 1,
                    "left": 1,
                    "right": 2,
                }
                _assert_tier_cache_entries_bind_node_identity_and_content(
                    store,
                    run_id=run_id,
                    workflow=workflow,
                    completed_nodes=["seed", "left", "right"],
                    checkpoint_state=uncommitted_state,
                    cache_entry_refs=uncommitted.metadata.cache_entry_refs,
                )
                assert uncommitted.metadata.completed_nodes == ["seed", "left", "right"]
                expected_before_resume = ["seed"]
                # The killed writer already published both verified cache journals.
                # The old durable frontier still rolls back, while the fresh executor replays them.
                expected_peer_calls = [0, 0]
            else:
                current_head = load_checkpoint_head(run_dir)
                assert current_head is not None
                assert current_head.checkpoint_ref == observed_ref
                assert current_head.sequence_number == observed["sequence_number"]
                assert str(observed_ref.artifact_id) not in history_refs
                expected_before_resume = ["seed", "left", "right"]
                expected_peer_calls = [0, 0]

            writer.terminate()
            writer.join(timeout=5)
            assert not writer.is_alive()
            assert writer.exitcode != 0
        finally:
            if writer.is_alive():
                writer.terminate()
                writer.join(timeout=5)
            phase_queue.close()

        result_queue = process_context.Queue()
        reader = process_context.Process(
            target=_b73_fresh_reader_then_resume,
            args=(
                str(store.root),
                run_id,
                bundle_ref.model_dump(mode="json"),
                result_queue,
            ),
        )
        try:
            reader.start()
            reader.join(timeout=60)
            result = result_queue.get(timeout=5)
            assert reader.exitcode == 0, result
        finally:
            if reader.is_alive():
                reader.terminate()
                reader.join(timeout=5)
            result_queue.close()

        assert result["pid"] != os.getpid()
        assert result["before_resume"]["origin_workflow_fingerprint"] == (
            expected_origin_fingerprint
        )
        expected_current_fingerprint = (
            expected_origin_fingerprint
            if cut == "after_artifact_before_head"
            else expected_residual_fingerprint
        )
        assert result["before_resume"]["workflow_fingerprint"] == (expected_current_fingerprint)
        assert result["before_resume"]["completed_nodes"] == expected_before_resume
        if cut == "after_head_before_history":
            assert result["before_resume"]["params"] == {
                "seed": 29,
                "step1": 1,
                "left": 1,
                "right": 2,
            }
            assert result["before_resume"]["cache_aliases"] == ["left", "right"]
        else:
            assert result["before_resume"]["params"] == {"seed": 29, "step1": 1}
            assert result["before_resume"]["cache_entry_refs"] == []
            assert result["before_resume"]["cache_aliases"] == []
        assert result["report_status"] == "ok"
        assert result["resumed_params"] == {
            "seed": 29,
            "step1": 1,
            "left": 1,
            "right": 2,
            "final": True,
        }
        assert result["before_resume"]["trace_cache"]["aliases"] == ["left", "right"]
        assert result["cache_hit_aliases"] == (
            ["left", "right"] if cut == "after_artifact_before_head" else []
        )
        assert result["peer_calls"] == expected_peer_calls
        assert result["final_calls"] == 1


def _b73_failure_policy_writer(
    cas_root: str,
    run_id: str,
    bundle_ref_payload: dict[str, Any],
    error_policy: Literal["fail_fast", "continue"],
    result_queue: Any,
) -> None:
    """Run the first failed tier attempt through the actual resume owner."""
    os.environ["POLISYOS_RUNNER_BACKEND"] = "local"
    os.environ["POLISYOS_RUNNER_MAX_PARALLELISM"] = "2"
    StepOneNode.calls = 0
    ParallelLeftNode.calls = 0
    FailOnceParallelRightNode.calls = 0
    FailOnceParallelRightNode.fail_once = True
    FlakyAfterParallelNode.calls = 0
    FlakyAfterParallelNode.fail_once = False

    store = FileSystemCAS(Path(cas_root))
    bundle_ref = ArtifactRef.model_validate(bundle_ref_payload)
    workflow = _seeded_parallel_workflow(error_policy=error_policy)
    first = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=_seeded_parallel_registry(right_node=FailOnceParallelRightNode()),
        registry_bundle_ref=bundle_ref,
        checkpoint_policy="strict",
    )
    resolved = resolve_latest_checkpoint(store, run_id)
    if resolved is None:
        raise AssertionError("writer did not resolve a checkpoint after first attempt")
    head, checkpoint = resolved
    if checkpoint.state is None:
        raise AssertionError("writer checkpoint omitted state")
    result_queue.put(
        {
            "pid": os.getpid(),
            "report_status": first.report.status,
            "sequence_number": head.sequence_number,
            "checkpoint_ref": str(head.checkpoint_ref.artifact_id),
            "completed_nodes": list(checkpoint.metadata.completed_nodes),
            "params": dict(checkpoint.state["params"]),
            "cache_entry_refs": [
                str(ref.artifact_id) for ref in checkpoint.metadata.cache_entry_refs
            ],
            "peer_calls": [ParallelLeftNode.calls, FailOnceParallelRightNode.calls],
        }
    )


def _b73_failure_policy_fresh_reader(
    cas_root: str,
    run_id: str,
    bundle_ref_payload: dict[str, Any],
    error_policy: Literal["fail_fast", "continue"],
    expected_current_fingerprint: str,
    right_fails_once: bool,
    result_queue: Any,
) -> None:
    """Retry a failed tier from CAS with a fresh process and explicit transient control."""
    os.environ["POLISYOS_RUNNER_BACKEND"] = "local"
    os.environ["POLISYOS_RUNNER_MAX_PARALLELISM"] = "2"
    StepOneNode.calls = 0
    ParallelLeftNode.calls = 0
    FailOnceParallelRightNode.calls = 0
    # The first process consumed the transient failure. Set the reader behavior
    # explicitly rather than depending on process-local class state inheritance.
    FailOnceParallelRightNode.fail_once = right_fails_once
    FlakyAfterParallelNode.calls = 0
    FlakyAfterParallelNode.fail_once = False

    store = FileSystemCAS(Path(cas_root))
    bundle_ref = ArtifactRef.model_validate(bundle_ref_payload)
    workflow = _seeded_parallel_workflow(error_policy=error_policy)
    before = resolve_latest_checkpoint(store, run_id)
    if before is None:
        raise AssertionError("fresh failure-policy reader found no checkpoint")
    head, checkpoint = before
    if checkpoint.state is None:
        raise AssertionError("fresh failure-policy checkpoint omitted state")
    cache_aliases = _assert_tier_cache_entries_bind_node_identity_and_content(
        store,
        run_id=run_id,
        workflow=workflow,
        completed_nodes=checkpoint.metadata.completed_nodes,
        checkpoint_state=checkpoint.state,
        cache_entry_refs=checkpoint.metadata.cache_entry_refs,
    )
    origin_fingerprint = compute_workflow_fingerprint(workflow)
    current_fingerprint = checkpoint.metadata.workflow_fingerprint
    if checkpoint.metadata.origin_workflow_fingerprint != origin_fingerprint:
        raise AssertionError("reopened checkpoint origin workflow fingerprint changed")
    if current_fingerprint != expected_current_fingerprint:
        raise AssertionError("reopened checkpoint residual workflow fingerprint changed")

    before_records = _b73_trace_records(store, run_id)
    trace_cache = _b73_trace_cache_snapshot(
        store, run_id=run_id, workflow=workflow, records=before_records
    )
    resumed = resume_from_checkpoint(
        store,
        run_id,
        workflow=workflow,
        registry=_seeded_parallel_registry(right_node=FailOnceParallelRightNode()),
        registry_bundle_ref=bundle_ref,
        checkpoint_policy="strict",
    )
    result_queue.put(
        {
            "pid": os.getpid(),
            "before_resume": {
                "sequence_number": head.sequence_number,
                "checkpoint_ref": str(head.checkpoint_ref.artifact_id),
                "completed_nodes": list(checkpoint.metadata.completed_nodes),
                "params": dict(checkpoint.state["params"]),
                "cache_entry_refs": [
                    str(ref.artifact_id) for ref in checkpoint.metadata.cache_entry_refs
                ],
                "cache_aliases": list(cache_aliases),
                "trace_cache": trace_cache,
                "workflow_fingerprint": current_fingerprint,
                "origin_workflow_fingerprint": (checkpoint.metadata.origin_workflow_fingerprint),
            },
            "report_status": resumed.report.status,
            "resumed_params": dict(resumed.state.params),
            "peer_calls": [ParallelLeftNode.calls, FailOnceParallelRightNode.calls],
            "cache_hit_aliases": _b73_cache_hit_aliases(
                _b73_trace_records(store, run_id)[len(before_records) :]
            ),
            "new_cache_publications": _b73_trace_cache_snapshot(
                store,
                run_id=run_id,
                workflow=workflow,
                records=_b73_trace_records(store, run_id)[len(before_records) :],
            ),
            "final_calls": FlakyAfterParallelNode.calls,
        }
    )


def test_parallel_resume_fail_fast_rolls_back_and_continue_commits_only_successful_peer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh readers retry only the peers absent from the durable frontier."""
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    monkeypatch.setenv("POLISYOS_RUNNER_MAX_PARALLELISM", "2")
    process_context = multiprocessing.get_context("spawn")

    error_policies: tuple[Literal["fail_fast", "continue"], ...] = ("fail_fast", "continue")
    for error_policy in error_policies:
        store = FileSystemCAS(tmp_path / error_policy)
        workflow = _seeded_parallel_workflow(error_policy=error_policy)
        run_id = f"R_b73_failure_policy_{error_policy}"
        _, bundle_ref, _ = _seed_parallel_checkpoint(store, run_id=run_id, workflow=workflow)
        seed = resolve_latest_checkpoint(store, run_id)
        assert seed is not None
        _, seed_checkpoint = seed
        assert seed_checkpoint.state is not None
        expected_origin_fingerprint = compute_workflow_fingerprint(workflow)
        expected_residual_fingerprint = compute_workflow_fingerprint(
            _build_resume_workflow_spec(
                workflow,
                completed_nodes=list(seed_checkpoint.metadata.completed_nodes),
            )
        )
        expected_current_fingerprint = (
            expected_origin_fingerprint
            if error_policy == "fail_fast"
            else expected_residual_fingerprint
        )

        writer_queue = process_context.Queue()
        writer = process_context.Process(
            target=_b73_failure_policy_writer,
            args=(
                str(store.root),
                run_id,
                bundle_ref.model_dump(mode="json"),
                error_policy,
                writer_queue,
            ),
        )
        try:
            writer.start()
            writer.join(timeout=60)
            assert writer.exitcode == 0
            first = writer_queue.get(timeout=5)
        finally:
            if writer.is_alive():
                writer.terminate()
                writer.join(timeout=5)
            writer_queue.close()

        assert first["pid"] != os.getpid()
        assert first["report_status"] == "fail"
        assert first["peer_calls"] == [1, 1]
        if error_policy == "fail_fast":
            assert first["completed_nodes"] == ["seed"]
            assert first["params"] == {"seed": 29, "step1": 1}
            assert first["cache_entry_refs"] == []
        else:
            assert first["completed_nodes"] == ["seed", "left"]
            assert first["params"] == {"seed": 29, "step1": 1, "left": 1}
            assert len(first["cache_entry_refs"]) == 1

        reader_queue = process_context.Queue()
        reader = process_context.Process(
            target=_b73_failure_policy_fresh_reader,
            args=(
                str(store.root),
                run_id,
                bundle_ref.model_dump(mode="json"),
                error_policy,
                expected_current_fingerprint,
                False,
                reader_queue,
            ),
        )
        try:
            reader.start()
            reader.join(timeout=60)
            assert reader.exitcode == 0
            retried = reader_queue.get(timeout=5)
        finally:
            if reader.is_alive():
                reader.terminate()
                reader.join(timeout=5)
            reader_queue.close()

        assert retried["pid"] != first["pid"]
        before = retried["before_resume"]
        assert before["origin_workflow_fingerprint"] == expected_origin_fingerprint
        assert before["workflow_fingerprint"] == expected_current_fingerprint
        assert retried["report_status"] == "ok"
        assert retried["resumed_params"] == {
            "seed": 29,
            "step1": 1,
            "left": 1,
            "right": 2,
            "final": True,
        }
        assert before["trace_cache"]["aliases"] == ["left"]
        assert retried["cache_hit_aliases"] == (["left"] if error_policy == "fail_fast" else [])
        assert retried["new_cache_publications"]["aliases"] == ["right"]
        assert (
            retried["new_cache_publications"]["refs"]["right"]
            not in before["trace_cache"]["refs"].values()
        )
        assert retried["peer_calls"] == [0, 1]
        assert retried["final_calls"] == 1
        if error_policy == "fail_fast":
            assert before["completed_nodes"] == ["seed"]
            assert before["params"] == {"seed": 29, "step1": 1}
            assert before["cache_entry_refs"] == []
            assert before["cache_aliases"] == []
        else:
            assert before["completed_nodes"] == ["seed", "left"]
            assert before["params"] == {"seed": 29, "step1": 1, "left": 1}
            assert before["cache_aliases"] == ["left"]
            assert len(before["cache_entry_refs"]) == 1
