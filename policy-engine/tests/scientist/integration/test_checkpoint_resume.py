from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.checkpoint import (
    CASCheckpointHook,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.executor import WorkflowExecutor
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.core.artifacts.store import FileSystemCAS


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
    _spec = NodeSpec(metadata=_meta("scientist.node_step_one@1.0.0", "StepOne"), state_reads=["params.seed"])

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


def _registry() -> NodeRegistry:
    reg = NodeRegistry()
    reg.register(StepOneNode())
    reg.register(StepTwoNode())
    reg.register(FlakyFinalNode())
    return reg


def _workflow() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="wf_checkpoint_resume",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(alias="step1", node_id=ComponentId.parse("scientist.node_step_one@1.0.0")),
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


def _context(store: FileSystemCAS, run_id: str) -> tuple[ExecutionContext, object]:
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
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
