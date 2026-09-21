"""Regression witnesses for RES-02 tier frontier and checkpoint semantics."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import ComponentId
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


def _ref(tag: str, *, kind: str = "scientist.node_cache_entry") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{tag * 64}",
        kind=kind,
        media_type="application/json",
    )


def _context() -> ExecutionContext:
    store = MagicMock()
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = _ref("f", kind="scientist.run")
    return ExecutionContext(store=store, run=run, logger=MagicMock())


def _node(*, node_id: str, write_path: str) -> MagicMock:
    node = MagicMock(spec=NodeSpec)
    node.spec.state_writes = [write_path]
    node.spec.state_reads = []
    node.spec.node_id = node_id
    return node


class _RecordingCheckpointHook:
    def __init__(self) -> None:
        self.node_calls: list[dict[str, Any]] = []
        self.tier_calls: list[dict[str, Any]] = []

    async def on_node_complete_async(self, **kwargs: Any) -> None:
        self.node_calls.append(kwargs)

    async def on_tier_complete_async(self, **kwargs: Any) -> None:
        self.tier_calls.append(kwargs)


def _executor(
    workflow: WorkflowSpec,
    outcomes: dict[str, NodeOutcome],
    cache_refs: dict[str, ArtifactRef | None],
    hook: _RecordingCheckpointHook,
) -> AsyncWorkflowExecutor:
    ctx = _context()
    registry = MagicMock(spec=NodeRegistry)

    def _get_node(node_id: object) -> MagicMock:
        label = str(node_id).split("@", 1)[0].rsplit(".", 1)[-1]
        return _node(node_id=str(node_id), write_path=f"params.{label.removeprefix('node_')}")

    registry.get.side_effect = _get_node
    executor = AsyncWorkflowExecutor(ctx, registry, checkpoint_hook=hook, max_parallelism=2)

    async def _persist_workflow_spec(workflow_spec: WorkflowSpec) -> ArtifactRef:
        return _ref("a", kind="scientist.workflow_spec")

    async def _persist_state(state: ExperimentState) -> ArtifactRef:
        return _ref("b", kind="scientist.experiment_state")

    async def _persist_report(report: Any) -> ArtifactRef:
        return _ref("c", kind="scientist.workflow_report")

    async def _execute_node(
        alias: str,
        inv: NodeInvocation,
        state: ExperimentState,
        workflow_spec: WorkflowSpec,
        *,
        tier_index: int = 0,
    ) -> tuple[NodeOutcome, int, bool, ArtifactRef | None]:
        del inv, workflow_spec, tier_index
        return outcomes[alias], 1, False, cache_refs.get(alias)

    executor._persist_workflow_spec = _persist_workflow_spec  # type: ignore[method-assign]
    executor._persist_state = _persist_state  # type: ignore[method-assign]
    executor._persist_report = _persist_report  # type: ignore[method-assign]
    executor._execute_node = _execute_node  # type: ignore[method-assign]
    return executor


def _workflow(*aliases: str, error_policy: str = "fail_fast") -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="res_02_regression",
        error_policy=error_policy,
        nodes=[
            NodeInvocation(
                alias=alias,
                node_id=ComponentId.parse(f"scientist.node_{alias}@1.0.0"),
            )
            for alias in aliases
        ],
    )


def test_single_skip_is_not_added_to_checkpoint_completed_set() -> None:
    state = ExperimentState(run_id="res-02-single-skip")
    hook = _RecordingCheckpointHook()
    workflow = WorkflowSpec(
        workflow_id="res_02_single_skip",
        nodes=[
            NodeInvocation(
                alias="skipped",
                node_id=ComponentId.parse("scientist.node_skipped@1.0.0"),
            ),
            NodeInvocation(
                alias="after",
                node_id=ComponentId.parse("scientist.node_after@1.0.0"),
                depends_on=["skipped"],
            ),
        ],
    )
    outcomes = {
        "skipped": NodeOutcome(status="skip", state=state),
        "after": NodeOutcome(
            status="ok",
            state=state.model_copy(update={"params": {"after": True}}),
        ),
    }
    executor = _executor(workflow, outcomes, {"after": _ref("d")}, hook)

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "ok"
    assert [call["completed_nodes"] for call in hook.node_calls] == [["after"]]


def test_parallel_tier_publishes_one_checkpoint_with_full_completed_set_and_cache_refs() -> None:
    state = ExperimentState(run_id="res-02-tier-atomic")
    left = state.model_copy(update={"params": {"left": 1}})
    right = state.model_copy(update={"params": {"right": 2}})
    hook = _RecordingCheckpointHook()
    workflow = _workflow("left", "right")
    executor = _executor(
        workflow,
        {
            "left": NodeOutcome(status="ok", state=left, artifacts=[_ref("e")]),
            "right": NodeOutcome(status="ok", state=right, artifacts=[_ref("f")]),
        },
        {"left": _ref("1"), "right": _ref("2")},
        hook,
    )

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "ok"
    assert result.state.params == {"left": 1, "right": 2}
    assert len(hook.tier_calls) == 1
    assert hook.tier_calls[0]["completed_nodes"] == ["left", "right"]
    assert hook.tier_calls[0]["cache_entry_refs"] == [_ref("1"), _ref("2")]
    assert hook.node_calls == []


def test_fail_fast_discards_parallel_tier_without_checkpoint_but_keeps_output_record() -> None:
    state = ExperimentState(run_id="res-02-tier-rollback")
    hook = _RecordingCheckpointHook()
    workflow = _workflow("left", "right")
    output = _ref("3", kind="scientist.output")
    executor = _executor(
        workflow,
        {
            "left": NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"left": 1}}),
                artifacts=[output],
            ),
            "right": NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.expected", message="expected failure"),
            ),
        },
        {"left": _ref("4"), "right": None},
        hook,
    )

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "fail"
    assert result.state.params == {}
    assert hook.tier_calls == []
    assert result.report.nodes[0].artifacts == [output]


def test_continue_checkpoints_successes_and_preserves_their_outputs() -> None:
    state = ExperimentState(run_id="res-02-tier-continue")
    hook = _RecordingCheckpointHook()
    workflow = _workflow("left", "right", error_policy="continue")
    output = _ref("5", kind="scientist.output")
    executor = _executor(
        workflow,
        {
            "left": NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"left": 1}}),
                artifacts=[output],
            ),
            "right": NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.expected", message="expected failure"),
            ),
        },
        {"left": _ref("6"), "right": None},
        hook,
    )

    result = asyncio.run(executor.execute(workflow, state))

    assert result.report.status == "fail"
    assert result.state.params == {"left": 1}
    assert len(hook.tier_calls) == 1
    assert hook.tier_calls[0]["completed_nodes"] == ["left"]
    assert hook.tier_calls[0]["cache_entry_refs"] == [_ref("6")]
    assert result.report.nodes[0].artifacts == [output]
